"""
ELM327ミニ(Bluetooth SPP)との疎通確認用スクリプト。
task_phase2_breakdown.md 2-0-2。

使い方:
    python elm327_probe.py COM11

ELM327の電源(=車両のOBD2ポートへの接続、またはUSB電源等)が入っていない状態だと
Bluetooth接続自体はできてもATコマンドへの応答がない点に注意。
"""
import sys
import time

import serial

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

BAUDRATE = 38400  # ELM327クローンの多くはこのデフォルト値。応答が無ければ9600/115200も試す
TIMEOUT_SEC = 2.0

# 疎通確認・初期化に使う基本ATコマンド群
INIT_COMMANDS = [
    "ATZ",   # リセット
    "ATE0",  # エコーオフ(以後の応答から送信コマンドの反響を除く)
    "ATI",   # ELM327のバージョン情報
    "ATSP0", # OBD2プロトコル自動選択
]


def send_command(ser: serial.Serial, command: str) -> tuple[bytes, str]:
    ser.reset_input_buffer()
    ser.write((command + "\r").encode("ascii"))
    time.sleep(0.2)
    deadline = time.monotonic() + TIMEOUT_SEC
    buf = b""
    while time.monotonic() < deadline:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            if b">" in buf:  # ELM327のプロンプト文字で応答終端を判定
                break
        else:
            time.sleep(0.05)
    text = buf.decode("ascii", errors="backslashreplace").strip().strip(">").strip()
    return buf, text


def main() -> None:
    if len(sys.argv) != 2:
        print(f"usage: python {sys.argv[0]} <COMポート番号>  (例: COM11)")
        sys.exit(1)

    port = sys.argv[1]
    print(f"[*] {port} へ {BAUDRATE}bps で接続します...")
    with serial.Serial(port, BAUDRATE, timeout=TIMEOUT_SEC) as ser:
        time.sleep(1.0)  # Bluetooth SPPの接続確立待ち
        for cmd in INIT_COMMANDS:
            raw, resp = send_command(ser, cmd)
            print(f"  > {cmd}")
            print(f"  < raw={raw!r}")
            print(f"  < text={resp!r}")
        print("[*] 完了。ATIの応答にELM327のバージョン文字列(例: 'ELM327 v1.5')が"
              "含まれていれば疎通成功です。")


if __name__ == "__main__":
    main()
