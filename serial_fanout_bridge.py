#!/usr/bin/env python3
"""
ESP32実機の1本のUSBシリアルポートを、race_captureの複数インスタンスが
同時に使えるようにするfan-outブリッジ。

RCPプロトコルはrace_capture側(クライアント)が約1Hzで`getStatus`/`{"s":0}`を
ポーリングし、ESP32(デバイス)がそれに応答するpull型(HANDOFF.md参照)。
そのため単純な読み取り専用の複製では、誰もポーリングを送らずESP32が
沈黙してしまい機能しない。

このブリッジは以下の二役を1プロセスで担う:
  1. 実ポート(例: /dev/ttyACM0)に対する唯一のRCPクライアント。
     起動時に接続シーケンス(getVer/getCapabilities/getMeta/各種getXCfg)を
     一度実行し、以後はgetStatusと{"s":0}を交互に約1Hzでポーリングし続ける。
     応答は全てキャッシュする。
  2. 各consumer(race_captureの各インスタンス)に対する疑似デバイス。
     仮想ポート(pty)経由で届く各インスタンス自身のポーリング要求には、
     実ポートへは一切転送せず、1.で得たキャッシュから直接応答する。
     これにより実ポートへの書き込みはブリッジの1箇所に一元化され、
     複数インスタンスが同時に実ポートを取り合うことによる書き込み競合・
     データ破損(SampleMetaException等)を避けられる。

使い方:
  python3 serial_fanout_bridge.py --device /dev/ttyACM0 \\
      --link /tmp/rc_vport1 --link /tmp/rc_vport2

  race_capture側の接続先(last_known_device等)には/tmp/rc_vport1・
  /tmp/rc_vport2を指定する。

書き込み系コマンド(setXCfg/flashCfg等)には未対応(ログに残すのみ)。
表示専用用途(本プロジェクトのダッシュカム構想)では発生しない想定。
"""
import argparse
import errno
import json
import os
import select
import sys
import time

import serial

# 実機への要求(トップレベルキー) -> 応答のトップレベルキー
RESPONSE_KEY = {
    "getVer": "ver",
    "getCapabilities": "capabilities",
    "getMeta": "meta",
    "getLapCfg": "lapCfg",
    "getTrackCfg": "trackCfg",
    "getCanCfg": "canCfg",
    "getObd2Cfg": "obd2Cfg",
    "getConnCfg": "connCfg",
    "getStatus": "status",
    "getAnalogCfg": "analogCfg",
}

# ブリッジ起動直後、実機に対して一度だけ順番に要求する項目
# (HANDOFF.mdの接続シーケンス7項目 + getMeta + getAnalogCfg)
# getAnalogCfgはrcpapi.pyのcmdSequenceで常にchannelId=None(全ch一括)で
# 呼ばれるため、他の項目と同様にnullリクエスト1回のキャッシュで足りる。
INITIAL_REQUESTS = [
    "getVer", "getCapabilities", "getMeta", "getLapCfg",
    "getTrackCfg", "getCanCfg", "getObd2Cfg", "getConnCfg", "getAnalogCfg",
]

INITIAL_REQUEST_INTERVAL = 0.15  # 実機への初期要求の送信間隔(秒)
POLL_INTERVAL = 0.5  # getStatus/{"s":0}を交互に送る間隔(秒) → 各々約1Hz


def create_virtual_port(link_path):
    master_fd, slave_fd = os.openpty()
    slave_path = os.ttyname(slave_fd)
    if os.path.islink(link_path) or os.path.exists(link_path):
        os.remove(link_path)
    os.symlink(slave_path, link_path)
    return master_fd, slave_path


class LineBuffer:
    """\\r または \\n 区切りで1行ずつ取り出すための受信バッファ。"""

    def __init__(self):
        self._buf = b""

    def feed(self, chunk: bytes):
        self._buf += chunk

    def pop_lines(self):
        lines = []
        while True:
            candidates = [i for i in (self._buf.find(b"\r"), self._buf.find(b"\n")) if i != -1]
            if not candidates:
                break
            idx = min(candidates)
            line, self._buf = self._buf[:idx], self._buf[idx + 1:]
            if line:
                lines.append(line)
        return lines


class Bridge:
    def __init__(self, device, baudrate, links):
        self.device = device
        self.baudrate = baudrate
        self.real_ser = None
        self.real_buf = LineBuffer()
        self.cache = {}  # 応答キー -> 実機から得た最新の値

        self.consumers = {}  # master_fd -> LineBuffer
        for link_path in links:
            master_fd, slave_path = create_virtual_port(link_path)
            self.consumers[master_fd] = LineBuffer()
            print("virtual port ready: {} -> {}".format(link_path, slave_path), flush=True)

        self._initial_idx = 0
        self._poll_toggle = False
        self._next_send_time = 0.0
        self._open_real_port()

    # -- 実機との接続 ---------------------------------------------------
    def _open_real_port(self):
        self.real_ser = serial.Serial(self.device, baudrate=self.baudrate, timeout=0)
        self._initial_idx = 0
        self._next_send_time = 0.0
        print("real port opened: {}".format(self.device), flush=True)

    def _reconnect_real_port(self):
        try:
            if self.real_ser is not None:
                self.real_ser.close()
        except Exception:
            pass
        self.real_ser = None
        while self.real_ser is None:
            try:
                self._open_real_port()
            except serial.SerialException as e:
                print("real port reopen failed: {}. retrying in 1s...".format(e), flush=True)
                time.sleep(1)

    def send_to_real(self, obj):
        raw = json.dumps(obj, separators=(",", ":")) + "\r"
        self.real_ser.write(raw.encode("utf-8"))

    def send_to_consumer(self, fd, obj):
        raw = json.dumps(obj, separators=(",", ":")) + "\r\n"
        try:
            os.write(fd, raw.encode("utf-8"))
        except OSError as e:
            # consumer側がまだポートを開いていない(EIO)場合等は無視して継続。
            if e.errno not in (errno.EIO, errno.EAGAIN):
                print("write to consumer fd {} failed: {}".format(fd, e), flush=True)

    # -- 実機に対するRCPクライアント役 -----------------------------------
    def tick_real_device_client(self, now):
        if now < self._next_send_time:
            return
        try:
            if self._initial_idx < len(INITIAL_REQUESTS):
                cmd = INITIAL_REQUESTS[self._initial_idx]
                self.send_to_real({cmd: None})
                self._initial_idx += 1
                self._next_send_time = now + INITIAL_REQUEST_INTERVAL
                return
            if self._poll_toggle:
                self.send_to_real({"getStatus": None})
            else:
                self.send_to_real({"s": 0})
            self._poll_toggle = not self._poll_toggle
            self._next_send_time = now + POLL_INTERVAL
        except serial.SerialException as e:
            print("real port write error: {}".format(e), flush=True)
            self._reconnect_real_port()

    def handle_real_line(self, line: bytes):
        try:
            obj = json.loads(line.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return
        if not isinstance(obj, dict):
            return
        for key, value in obj.items():
            self.cache[key] = value

    # -- 各consumerに対する疑似デバイス役 ---------------------------------
    def handle_consumer_line(self, fd, line: bytes):
        try:
            obj = json.loads(line.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return
        if not isinstance(obj, dict):
            return
        for req_key, value in obj.items():
            if req_key == "s":
                cached = self.cache.get("s")
                if cached is None:
                    continue
                payload = dict(cached)
                if isinstance(value, dict) and value.get("meta"):
                    meta = self.cache.get("meta")
                    if meta is not None:
                        payload["meta"] = meta
                self.send_to_consumer(fd, {"s": payload})
                continue

            resp_key = RESPONSE_KEY.get(req_key)
            if resp_key is None:
                print("[!] consumer fd={} からの未対応コマンド: {}".format(fd, req_key), flush=True)
                continue
            cached = self.cache.get(resp_key)
            if cached is None:
                # 実機からまだ一度も取得できていない。consumer側は
                # タイムアウト後に自動で再送してくるので、ここでは無応答のままでよい。
                continue
            self.send_to_consumer(fd, {resp_key: cached})

    # -- メインループ -----------------------------------------------------
    def run(self):
        print("bridge running. waiting for initial data from real device...", flush=True)
        while True:
            now = time.monotonic()
            self.tick_real_device_client(now)

            rlist = [self.real_ser.fileno()] + list(self.consumers.keys())
            try:
                ready, _, _ = select.select(rlist, [], [], 0.2)
            except (OSError, ValueError):
                break

            for fd in ready:
                if fd == self.real_ser.fileno():
                    try:
                        chunk = self.real_ser.read(4096)
                    except serial.SerialException as e:
                        print("real port read error: {}".format(e), flush=True)
                        self._reconnect_real_port()
                        continue
                    if chunk:
                        self.real_buf.feed(chunk)
                        for line in self.real_buf.pop_lines():
                            self.handle_real_line(line)
                else:
                    try:
                        chunk = os.read(fd, 4096)
                    except OSError:
                        chunk = b""
                    if chunk:
                        buf = self.consumers[fd]
                        buf.feed(chunk)
                        for line in buf.pop_lines():
                            self.handle_consumer_line(fd, line)


def main():
    parser = argparse.ArgumentParser(description="ESP32シリアルポートのfan-outブリッジ")
    parser.add_argument("--device", required=True, help="実ポート (例: /dev/ttyACM0)")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument(
        "--link",
        action="append",
        required=True,
        help="仮想ポートのリンク先パス。複数指定可 (例: --link /tmp/rc_vport1 --link /tmp/rc_vport2)",
    )
    args = parser.parse_args()

    bridge = Bridge(args.device, args.baudrate, args.link)
    try:
        bridge.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
