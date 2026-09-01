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

# サンプル要求とステータス要求は必要なレートが全く違うため、独立した間隔で送る。
# 当初は1本のタイマーで両者を交互に0.5秒間隔で送っていたが、それだとサンプルの
# 実効レートが1Hzに落ち、ゲージの値が1秒に1回しか変化しない(実測0.99Hz)。
# レーシングダッシュとしては使いものにならないため分離した。10Hzは公式アプリが
# 実機に対して行っているサンプルポーリングと同じレート(ARCHITECTURE.md 1-4-6)。
DEFAULT_SAMPLE_HZ = 10.0  # {"s":0} の送信レート
DEFAULT_STATUS_HZ = 1.0  # getStatus の送信レート(接続状態の表示用途なので低くてよい)
MAX_SELECT_TIMEOUT = 0.2  # メインループのselect待ち上限(秒)
# Espressif の USB VID。ESP32-C3内蔵のUSB-JTAG/serialディスクリプタがこれを名乗る。
DEFAULT_ESP32_VID = "303a"
REOPEN_INTERVAL = 1.0  # 実機が居ないときに再探索する間隔(秒)


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
    def __init__(self, device, baudrate, links,
                 sample_hz=DEFAULT_SAMPLE_HZ, status_hz=DEFAULT_STATUS_HZ,
                 vid=DEFAULT_ESP32_VID):
        self.device = device  # Noneならvidで自動探索する
        self.vid = vid
        self.real_path = None
        self.baudrate = baudrate
        self.sample_interval = 1.0 / sample_hz
        self.status_interval = 1.0 / status_hz
        self.real_ser = None
        self.real_buf = LineBuffer()
        self.cache = {}  # 応答キー -> 実機から得た最新の値

        self.consumers = {}  # master_fd -> LineBuffer
        for link_path in links:
            master_fd, slave_path = create_virtual_port(link_path)
            self.consumers[master_fd] = LineBuffer()
            print("virtual port ready: {} -> {}".format(link_path, slave_path), flush=True)

        self._initial_idx = 0
        self._next_send_time = 0.0
        self._next_sample_time = 0.0
        self._next_status_time = 0.0
        self._next_open_attempt = 0.0
        # 実機が無くても起動する。仮想ポートは既に作ってあるので、race_capture側は
        # 接続だけは確立でき、実機が挿されるまで値が来ないだけの状態になる。
        # (実機必須にすると、ロガーのUSBが抜けているだけでダッシュも録画も一切
        #  立ち上がらない。詳細はdashcam_launch_rock5b.shの起動条件のコメント参照)
        self._try_open_real_port()

    # -- 実機との接続 ---------------------------------------------------
    def find_real_device(self):
        """VIDが一致する/dev/ttyACM*を探す。--deviceが明示指定ならそれを優先。"""
        if self.device:
            return self.device if os.path.exists(self.device) else None
        for name in sorted(os.listdir("/dev")):
            if not name.startswith("ttyACM"):
                continue
            path = "/dev/" + name
            try:
                with open("/sys/class/tty/%s/device/../idVendor" % name) as f:
                    if f.read().strip().lower() == self.vid.lower():
                        return path
            except OSError:
                continue
        return None

    def _try_open_real_port(self):
        """開けたらTrue。実機が無ければ黙ってFalseを返す(例外を投げない)。"""
        path = self.find_real_device()
        if path is None:
            return False
        try:
            self.real_ser = serial.Serial(path, baudrate=self.baudrate, timeout=0)
        except (serial.SerialException, OSError) as e:
            print("real port open failed: {}".format(e), flush=True)
            return False
        self.real_path = path
        self._initial_idx = 0
        self._next_send_time = 0.0
        self._next_sample_time = 0.0
        self._next_status_time = 0.0
        print("real port opened: {}".format(path), flush=True)
        return True

    def _drop_real_port(self, why):
        try:
            if self.real_ser is not None:
                self.real_ser.close()
        except Exception:
            pass
        if self.real_ser is not None:
            print("real port lost ({}). will keep looking...".format(why), flush=True)
        self.real_ser = None

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
        if self.real_ser is None:
            # 実機不在。一定間隔で挿し直し/後挿しを探しに行く。ここでブロックしては
            # いけない(consumerへの応答が止まる)ので、1回試して戻る。
            if now >= self._next_open_attempt:
                self._next_open_attempt = now + REOPEN_INTERVAL
                self._try_open_real_port()
            return
        try:
            if self._initial_idx < len(INITIAL_REQUESTS):
                if now < self._next_send_time:
                    return
                cmd = INITIAL_REQUESTS[self._initial_idx]
                self.send_to_real({cmd: None})
                self._initial_idx += 1
                self._next_send_time = now + INITIAL_REQUEST_INTERVAL
                return
            if now >= self._next_sample_time:
                self.send_to_real({"s": 0})
                self._next_sample_time = now + self.sample_interval
            if now >= self._next_status_time:
                self.send_to_real({"getStatus": None})
                self._next_status_time = now + self.status_interval
        except serial.SerialException as e:
            self._drop_real_port("write error: {}".format(e))

    def _select_timeout(self, now):
        # 次に実機へ要求を送るべき時刻までしか待たない。固定0.2秒待ちのままだと
        # サンプル間隔(0.1秒)より粗くなり、せっかく上げたレートが頭打ちになる。
        if self.real_ser is None:
            next_send = self._next_open_attempt
        elif self._initial_idx < len(INITIAL_REQUESTS):
            next_send = self._next_send_time
        else:
            next_send = min(self._next_sample_time, self._next_status_time)
        return max(0.0, min(MAX_SELECT_TIMEOUT, next_send - now))

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

            real_fd = self.real_ser.fileno() if self.real_ser is not None else None
            rlist = list(self.consumers.keys())
            if real_fd is not None:
                rlist.append(real_fd)
            try:
                ready, _, _ = select.select(rlist, [], [], self._select_timeout(now))
            except (OSError, ValueError):
                break

            for fd in ready:
                if fd == real_fd:
                    try:
                        chunk = self.real_ser.read(4096)
                    except (serial.SerialException, OSError) as e:
                        self._drop_real_port("read error: {}".format(e))
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
    parser.add_argument("--device", default=None,
                        help="実ポートを明示指定する (例: /dev/ttyACM0)。"
                             "省略時は--vidに一致する/dev/ttyACM*を自動探索し、"
                             "見つからなければ挿されるまで待ち続ける")
    parser.add_argument("--vid", default=DEFAULT_ESP32_VID,
                        help="自動探索するUSB VID (既定: %s = Espressif)" % DEFAULT_ESP32_VID)
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument(
        "--link",
        action="append",
        required=True,
        help="仮想ポートのリンク先パス。複数指定可 (例: --link /tmp/rc_vport1 --link /tmp/rc_vport2)",
    )
    parser.add_argument(
        "--sample-hz",
        type=float,
        default=DEFAULT_SAMPLE_HZ,
        help="実機へ{{\"s\":0}}を送るレート(Hz)。ゲージの更新レートがこれで決まる (既定: {})".format(DEFAULT_SAMPLE_HZ),
    )
    parser.add_argument(
        "--status-hz",
        type=float,
        default=DEFAULT_STATUS_HZ,
        help="実機へgetStatusを送るレート(Hz) (既定: {})".format(DEFAULT_STATUS_HZ),
    )
    args = parser.parse_args()

    bridge = Bridge(args.device, args.baudrate, args.link,
                    sample_hz=args.sample_hz, status_hz=args.status_hz, vid=args.vid)
    print("polling rates: sample={} Hz, status={} Hz".format(args.sample_hz, args.status_hz), flush=True)
    try:
        bridge.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
