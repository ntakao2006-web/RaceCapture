"""
車両のOBD2プロトコル・対応PIDを調査するスクリプト。
task_phase2_breakdown.md 2-0-3〜2-0-5(NCロードスター)/2-0-6(レクサスUX)用。

使い方:
    python obd2_survey.py COM11 nc_roadster

車両側のイグニッションがOFFのままだとECUが応答せず"UNABLE TO CONNECT"等が
返るので、ACC以上(できればON)にしてから実行すること。
"""
import json
import sys
import time
from datetime import datetime, timezone

import serial

BAUDRATE = 38400
TIMEOUT_SEC = 5.0
FIRST_PID_TIMEOUT_SEC = 12.0  # 初回のプロトコル自動探索は数秒かかることがあるため長めに確保

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

# 0100/0120/0140は「サポートPID一覧」。010C以降は代表的な基本PID。
PID_REQUESTS = [
    ("0120", "サポートPID 21-40"),
    ("0140", "サポートPID 41-60"),
    ("010C", "エンジン回転数(RPM)"),
    ("010D", "車速(km/h)"),
    ("0105", "冷却水温(degC)"),
    ("0111", "スロットル開度(%)"),
    ("0104", "エンジン負荷(%)"),
]


def send_command(ser: serial.Serial, command: str, timeout: float = TIMEOUT_SEC) -> str:
    ser.reset_input_buffer()
    ser.write((command + "\r").encode("ascii"))
    deadline = time.monotonic() + timeout
    buf = b""
    while time.monotonic() < deadline:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            if b">" in buf:
                break
        else:
            time.sleep(0.05)
    return buf.decode("ascii", errors="backslashreplace").strip().strip(">").strip()


def main() -> None:
    if len(sys.argv) != 3:
        print(f"usage: python {sys.argv[0]} <COMポート> <車両識別名>  (例: COM11 nc_roadster)")
        sys.exit(1)

    port, vehicle = sys.argv[1], sys.argv[2]
    log = {
        "vehicle": vehicle,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "port": port,
        "results": [],
    }

    print(f"[*] {port} へ接続します（車両: {vehicle}）...")
    with serial.Serial(port, BAUDRATE, timeout=TIMEOUT_SEC) as ser:
        time.sleep(1.0)

        for cmd in ["ATZ", "ATE0", "ATH0", "ATSP0"]:
            resp = send_command(ser, cmd)
            print(f"  > {cmd}\n  < {resp!r}")
            log["results"].append({"cmd": cmd, "resp": resp})

        print("[*] 0100を送信してプロトコル自動探索を行います（数秒かかる場合があります）...")
        resp = send_command(ser, "0100", timeout=FIRST_PID_TIMEOUT_SEC)
        print(f"  > 0100 (サポートPID 01-20、プロトコル確定用)\n  < {resp!r}")
        log["results"].append({"cmd": "0100", "desc": "supported PIDs 01-20", "resp": resp})

        proto = send_command(ser, "ATDPN")
        print(f"  > ATDPN (確定プロトコル種別)\n  < {proto!r}")
        log["protocol_number"] = proto

        for pid, desc in PID_REQUESTS:
            resp = send_command(ser, pid)
            print(f"  > {pid} ({desc})\n  < {resp!r}")
            log["results"].append({"cmd": pid, "desc": desc, "resp": resp})

    out_path = f"obd2_survey_{vehicle}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"[*] 結果を {out_path} へ保存しました。")


if __name__ == "__main__":
    main()
