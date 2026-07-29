#!/usr/bin/env python3
"""
RaceCapture (RCP) Mock Device
==============================

実機なしで RaceCapture のファームウェア(デバイス側)の挙動を最低限エミュレートし、
公式アプリ(RaceCapture App)と接続させて JSON プロトコルのやり取りをログに残すためのスクリプト。

プロトコル仕様は autosportlabs/RaceCapture-Pro_firmware のソースコード
(src/logger/loggerApi.c, src/logger/connectivityTask.c) を解析した結果に基づく:

  - 1メッセージ = 1行の JSON + CRLF ("\r\n") 終端
  - コマンドはトップレベルのキー名で判別 (例: {"getVer":{}})
  - サンプルデータは {"s": {"t": <tick>, "d": [v1, v2, ..., <bitmask>]}} 形式
  - 最初のサンプル(tick==0)や一定間隔ごとに "meta" 配列を "s" の中に同送し、
    チャンネル定義 (nm/ut/min/max/prec/sr) を伝える

使い方:
  1. 仮想シリアルポートのペアを用意する (socat や com0com)
  2. 公式アプリを片方のポートに接続させる
  3. このスクリプトをもう片方のポートに向けて起動する
       python3 rcp_mock_device.py --port /tmp/rcp_virtual2 --baud 115200
  4. やり取りはすべて ./rcp_capture.jsonl に記録される (方向・タイムスタンプ付き)

未知のコマンドが来た場合は内容をログに出すだけで、通信は落とさない
(アプリが次に何を要求してくるか観察できるようにするため)。
"""

import argparse
import json
import time
import threading
import sys
from datetime import datetime, timezone

try:
    import serial
except ImportError:
    print("pyserial が必要です: pip install pyserial --break-system-packages", file=sys.stderr)
    raise

LOG_PATH = "rcp_capture.jsonl"
_log_lock = threading.Lock()


def log_event(direction: str, raw: str, parsed=None):
    """direction: 'RX' (app -> device) or 'TX' (device -> app)"""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "dir": direction,
        "raw": raw,
    }
    if parsed is not None:
        entry["parsed"] = parsed
    line = json.dumps(entry, ensure_ascii=False)
    with _log_lock:
        print(f"[{direction}] {raw}")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# ---------------------------------------------------------------------------
# ダミーのチャンネル定義。実機の getMeta / "s" の meta 配列と同じキー名。
# nm=チャンネル名, ut=単位, min/max=範囲, prec=小数桁数, sr=サンプルレート(Hz)
# ---------------------------------------------------------------------------
CHANNELS = [
    {"nm": "RPM",      "ut": "rpm",  "min": 0,    "max": 10000, "prec": 0, "sr": 10},
    {"nm": "Speed",    "ut": "mph",  "min": 0,    "max": 200,   "prec": 1, "sr": 10},
    {"nm": "WaterTemp", "ut": "F",   "min": 0,    "max": 300,   "prec": 0, "sr": 5},
    {"nm": "OilPress", "ut": "psi",  "min": 0,    "max": 150,   "prec": 1, "sr": 5},
    {"nm": "Lat",      "ut": "deg",  "min": -90,  "max": 90,    "prec": 6, "sr": 10},
    {"nm": "Lon",      "ut": "deg",  "min": -180, "max": 180,   "prec": 6, "sr": 10},
]


def make_ver_response():
    return {
        "ver": {
            "name": "RCPMK3",
            "fname": "RaceCapture/Pro MK3 (mock)",
            "major": 2,
            "minor": 16,
            "bugfix": 1,
            "serial": "MOCK0001",
            "git_info": "mock-build",
            "release_type": "release",
        }
    }


ANALOG_CHANNEL_COUNT = 1  # 0-8: getAnalogCfg/setAnalogCfg疎通確認用に1chだけ有効化
# reference/RaceCapture-Pro_firmware の include/api/api.h より (0ではなく1が成功)
API_SUCCESS = 1


def make_capabilities_response():
    # チャンネル数やtracksを0以外にすると has_analog/has_gpio/has_pwm/has_timer/
    # has_can_channel/trackDb等の条件分岐が真になり、対応するgetXCfgコマンドが
    # 追加で要求されてしまう。0-8でanalogのみ疎通確認するため analog だけ非0にし、
    # 他は最小限の接続シーケンスのまま全て0にする。
    return {
        "capabilities": {
            "flags": [],
            "channels": {
                "analog": ANALOG_CHANNEL_COUNT,
                "imu": 0,
                "gpio": 0,
                "timer": 0,
                "pwm": 0,
                "can": 0,
                "obd2": 0,
                "canChan": 0,
            },
            "sampleRates": {"gps": 50, "sensor": 1000},
            "db": {"tracks": 0, "sectors": 0},
        }
    }


def make_default_analog_cfg(index: int):
    """reference/RaceCapture-Pro_firmware の test/json_api_files/*AnalogCfg*.json
    で確認した実機フィールド構成に合わせたデフォルト値。"""
    return {
        "nm": f"Analog{index}",
        "ut": "Volts",
        "min": 0.0,
        "max": 5.0,
        "sr": 10,
        "prec": 2,
        "scalMod": 0,
        "scaling": 1.0,
        "offset": 0.0,
        "alpha": 0.0,
        "cal": 0.0,
        "map": {
            "raw": [0, 1.25, 2.5, 3.75, 5],
            "scal": [0, 1.25, 2.5, 3.75, 5],
        },
    }


def make_meta_response():
    return {"meta": CHANNELS}


def make_status_response():
    return {
        "status": {
            "system": {
                "model": "RaceCapture/Pro MK3 (mock)",
                "ver_major": 2, "ver_minor": 16, "ver_bugfix": 1,
                "uptime": int(time.time()),
            },
            "GPS": {"init": 3, "qual": 1, "lat": 35.83, "lon": 139.41, "sats": 8, "DOP": 100},
            "logging": {"status": 0, "dur": 0},
            "track": {"status": 0, "valid": False, "trackId": 0, "inLap": 0, "armed": 0},
        }
    }


class MockRcpDevice:
    def __init__(self, ser: serial.Serial, stream_hz: float = 10.0):
        self.ser = ser
        self.stream_hz = stream_hz
        self.tick = 0
        self.streaming = False
        self._stop = threading.Event()
        # setAnalogCfgで書き込まれた値をgetAnalogCfgで読み返せるよう保持する
        self.analog_cfg = {i: make_default_analog_cfg(i) for i in range(ANALOG_CHANNEL_COUNT)}

    # -- 送信ヘルパ ---------------------------------------------------
    def send(self, obj: dict):
        raw = json.dumps(obj, separators=(",", ":")) + "\r\n"
        self.ser.write(raw.encode("utf-8"))
        log_event("TX", raw.strip(), obj)

    # -- 受信コマンドのディスパッチ ------------------------------------
    def handle_command(self, obj: dict):
        if "getVer" in obj:
            self.send(make_ver_response())
        elif "getCapabilities" in obj:
            self.send(make_capabilities_response())
        elif "getMeta" in obj:
            self.send(make_meta_response())
        elif "getStatus" in obj:
            self.send(make_status_response())
        elif "getLapCfg" in obj:
            # 公式アプリはこの応答が来ないと接続シーケンス全体をタイムアウト扱いにして
            # 切断する。フィールドは全て jsonCfg.get() ベースで省略可能なので空でよい。
            self.send({"lapCfg": {}})
        elif "getTrackCfg" in obj:
            self.send({"trackCfg": {}})
        elif "getCanCfg" in obj:
            self.send({"canCfg": {}})
        elif "getObd2Cfg" in obj:
            self.send({"obd2Cfg": {}})
        elif "getConnCfg" in obj:
            self.send({"connCfg": {}})
        elif "getAnalogCfg" in obj:
            self.handle_get_analog_cfg(obj.get("getAnalogCfg"))
        elif "setAnalogCfg" in obj:
            self.handle_set_analog_cfg(obj.get("setAnalogCfg"))
        elif "flashCfg" in obj:
            # Writeボタン押下後、アプリが設定確定(NVSコミット相当)のため送ってくる。
            # 応答がないと "Timeout waiting for 'flashCfg'" でWriteがエラー扱いになる。
            self.send({"flashCfg": {"rc": API_SUCCESS}})
        elif "s" in obj:
            # 単発のサンプル要求。meta:1 が指定されていればメタ同梱。
            want_meta = False
            val = obj.get("s")
            if isinstance(val, dict) and val.get("meta"):
                want_meta = True
            self.send_sample(with_meta=want_meta)
        elif "log" in obj:
            self.streaming = bool(obj.get("log"))
            self.send({"logStart" if self.streaming else "logEnd": 1})
        else:
            # 未知のコマンド: 内容をログに残すだけで、通信は継続する。
            # これがまさに「アプリが最低限何を要求してくるか」を洗い出す部分。
            print(f"[!] 未知のコマンド: {obj}")

    # -- センサーキャリブレーション設定 (0-8) -----------------------------
    def handle_get_analog_cfg(self, index):
        """index が None (JSONの null) なら全chをまとめて返す。実機の
        getAnalogCfg3.json相当。int指定ならそのchのみ (getAnalogCfg1/2.json相当)。"""
        if index is None:
            indices = list(self.analog_cfg.keys())
        else:
            indices = [int(index)]
        result = {}
        for i in indices:
            cfg = self.analog_cfg.get(i)
            if cfg is not None:
                result[str(i)] = cfg
        self.send({"analogCfg": result})

    def handle_set_analog_cfg(self, payload):
        """payload: {"<index>": {フィールドの部分更新}, ...}
        実機同様、送られてきたフィールドだけを既存設定にマージして保存する。"""
        if isinstance(payload, dict):
            for idx_str, fields in payload.items():
                try:
                    idx = int(idx_str)
                except (TypeError, ValueError):
                    continue
                if idx not in self.analog_cfg or not isinstance(fields, dict):
                    continue
                cfg = self.analog_cfg[idx]
                for key, value in fields.items():
                    if key == "map" and isinstance(value, dict):
                        cfg["map"].update(value)
                    else:
                        cfg[key] = value
        self.send({"setAnalogCfg": {"rc": API_SUCCESS}})

    # -- サンプルストリーミング -----------------------------------------
    def sample_values(self):
        import math
        t = time.time()
        return [
            int(3000 + 2000 * math.sin(t / 3)),   # RPM
            round(60 + 40 * math.sin(t / 5), 1),  # Speed
            int(180 + 10 * math.sin(t / 7)),      # WaterTemp
            round(40 + 5 * math.sin(t / 4), 1),   # OilPress
            round(35.830000 + 0.0001 * math.sin(t), 6),  # Lat
            round(139.410000 + 0.0001 * math.cos(t), 6), # Lon
        ]

    def send_sample(self, with_meta: bool):
        values = self.sample_values()
        bitmask = (1 << len(values)) - 1  # 全チャンネル有効
        s = {"t": self.tick, "d": values + [bitmask]}
        if with_meta:
            s["meta"] = CHANNELS
        self.send({"s": s})
        self.tick += 1

    def stream_loop(self):
        interval = 1.0 / self.stream_hz
        meta_interval_ticks = 50  # 定期的にメタも再送 (実機同様)
        while not self._stop.is_set():
            if self.streaming:
                with_meta = (self.tick == 0) or (self.tick % meta_interval_ticks == 0)
                self.send_sample(with_meta=with_meta)
            time.sleep(interval)

    def stop(self):
        self._stop.set()


def read_lines(ser: serial.Serial):
    """行区切り(\\r または \\n、どちらか一方でも可)で行を読み続けるジェネレータ。
    実機アプリは \\r のみで終端することが実測で判明したため、\\r と \\n の
    どちらか一文字でも区切りとして扱う。
    生バイトが届いた時点で(行が完成していなくても)即座にRAWログに残す。
    """
    buf = b""
    while True:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            log_event("RAW", repr(chunk))
            buf += chunk
            while True:
                idx = min((i for i in (buf.find(b"\r"), buf.find(b"\n")) if i != -1), default=-1)
                if idx == -1:
                    break
                line, buf = buf[:idx], buf[idx + 1:]
                if line:
                    yield line.decode("utf-8", errors="replace")
        else:
            time.sleep(0.01)


def main():
    parser = argparse.ArgumentParser(description="RaceCapture mock device")
    parser.add_argument("--port", required=True, help="仮想シリアルポート (例: /tmp/rcp_virtual2 や COM11)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--stream-hz", type=float, default=10.0,
                         help="サンプルストリーミングのレート (Hz)")
    parser.add_argument("--always-stream", action="store_true",
                         help="'log' コマンドを待たずに最初からストリーミングを開始する")
    args = parser.parse_args()

    ser = serial.Serial(args.port, args.baud, timeout=0.1)
    device = MockRcpDevice(ser, stream_hz=args.stream_hz)
    device.streaming = args.always_stream

    t = threading.Thread(target=device.stream_loop, daemon=True)
    t.start()

    print(f"Mock RCP device listening on {args.port} @ {args.baud}bps")
    print(f"Logging all traffic to {LOG_PATH}")

    try:
        for line in read_lines(ser):
            log_event("RX", line)
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                print(f"[!] JSONとして解釈できない行: {line!r}")
                continue
            device.handle_command(obj)
    except KeyboardInterrupt:
        pass
    finally:
        device.stop()
        ser.close()


if __name__ == "__main__":
    main()
