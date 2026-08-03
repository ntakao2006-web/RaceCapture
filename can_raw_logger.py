"""
生CANロガーモード（2-4-1、ファームウェア側で今後実装予定）が出力する
生CANフレームをPC側で受信・記録するツール。
task_phase2_breakdown.md 2-4-2。

2-0-8で判明したELM327の限界（UART速度38400bpsがボトルネックで`BUFFER FULL`が
頻発、タイムスタンプも無い）を解消するため、自作ロガー（ESP32 + MCP2562FD、
2-1）のTWAI(CAN)ペリフェラルで直接受信したフレームをマイクロ秒精度の
タイムスタンプ付きでシリアル出力させ、それをこのツールで記録する。

想定する入力行フォーマット（2-4-1のファームウェア実装が守るべき仕様）:
    <timestamp_us>,<can_id_hex>,<dlc>,<data_hex>
    例: 1234567,200,8,AA BB CC DD EE FF 00 11
    - timestamp_us: ESP32起動からの経過マイクロ秒（esp_timer_get_time()）の整数
    - can_id_hex: 標準11bit CAN IDを16進数で（"0x"無し、大文字小文字問わず）
    - dlc: データ長 0-8
    - data_hex: dlcバイト分を空白区切りの16進数で（dlc=0なら空文字列）

ハードウェア（2-1のCANトランシーバ回路）が未調達のため、このツール自体は
実車ログでの検証がまだできていない。オフライン検証用に、実際のシリアル
ポートの代わりにテキストファイル/標準入力から同じ行フォーマットを読み込む
`--replay`モードを用意し、パース・記録ロジックはハードウェア非依存で
テスト済み（詳細はtask_phase2_breakdown.md 2-4-2参照）。

使い方:
    # 実機から記録する場合（2-4-1のファームウェア実装後）
    python can_raw_logger.py --port COM7 --baud 921600 --out raw_can_log.csv

    # オフライン検証・既存キャプチャの再フォーマット用
    python can_raw_logger.py --replay sample_lines.txt --out raw_can_log.jsonl --format jsonl
"""
import argparse
import csv
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone

DEFAULT_BAUDRATE = 921600  # フルスピードCAN(500kbps)のフレームを取りこぼさないための高速シリアル想定


def parse_can_line(line: str):
    """1行分の生CANログをパースする。不正な行は None を返す（例外は投げない）。"""
    line = line.strip()
    if not line:
        return None
    parts = line.split(",")
    if len(parts) != 4:
        return None
    ts_str, can_id_str, dlc_str, data_str = parts
    try:
        ts_us = int(ts_str, 10)
        can_id = int(can_id_str, 16)
        dlc = int(dlc_str, 10)
    except ValueError:
        return None
    if not (0 <= dlc <= 8):
        return None
    data_str = data_str.strip()
    data_bytes = []
    if data_str:
        for tok in data_str.split():
            try:
                b = int(tok, 16)
            except ValueError:
                return None
            if not (0 <= b <= 0xFF):
                return None
            data_bytes.append(b)
    if len(data_bytes) != dlc:
        return None
    return {
        "ts_us": ts_us,
        "can_id": can_id,
        "dlc": dlc,
        "data": data_bytes,
    }


def format_record_csv_row(record, host_ts_iso):
    return [
        record["ts_us"],
        format(record["can_id"], "X"),
        record["dlc"],
        " ".join(format(b, "02X") for b in record["data"]),
        host_ts_iso,
    ]


CSV_HEADER = ["ts_us", "can_id", "dlc", "data_hex", "host_ts"]


@contextmanager
def open_serial_source(port, baud):
    import serial  # 実機接続時のみ必要（オフライン検証ではpyserial不要にするため遅延import）

    ser = serial.Serial(port, baud, timeout=1.0)
    try:
        def lines():
            buf = b""
            while True:
                chunk = ser.read(ser.in_waiting or 1)
                if not chunk:
                    continue
                buf += chunk
                while b"\n" in buf:
                    raw_line, buf = buf.split(b"\n", 1)
                    yield raw_line.decode("ascii", errors="backslashreplace")

        yield lines()
    finally:
        ser.close()


@contextmanager
def open_replay_source(path):
    if path == "-":
        yield (line.rstrip("\n") for line in sys.stdin)
        return
    with open(path, "r", encoding="utf-8") as f:
        yield (line.rstrip("\n") for line in f)


def run(line_source, out_path, fmt, max_lines=None, on_record=None, on_malformed=None):
    """line_source から行を読み続け、パースできたレコードを out_path へ逐次書き込む。
    戻り値: (記録件数, 不正行件数)"""
    recorded = 0
    malformed = 0
    with open(out_path, "w", encoding="utf-8", newline="") as out_f:
        writer = None
        if fmt == "csv":
            writer = csv.writer(out_f)
            writer.writerow(CSV_HEADER)
        for line in line_source:
            record = parse_can_line(line)
            if record is None:
                malformed += 1
                if on_malformed:
                    on_malformed(line)
                if max_lines is not None and recorded + malformed >= max_lines:
                    break
                continue
            host_ts_iso = datetime.now(timezone.utc).isoformat()
            if fmt == "csv":
                writer.writerow(format_record_csv_row(record, host_ts_iso))
            else:
                json_record = dict(record)
                json_record["can_id"] = format(record["can_id"], "X")
                json_record["data_hex"] = " ".join(format(b, "02X") for b in record["data"])
                json_record["host_ts"] = host_ts_iso
                out_f.write(json.dumps(json_record, ensure_ascii=False) + "\n")
            out_f.flush()
            recorded += 1
            if on_record:
                on_record(record)
            if max_lines is not None and recorded + malformed >= max_lines:
                break
    return recorded, malformed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src_group = parser.add_mutually_exclusive_group(required=True)
    src_group.add_argument("--port", help="実機シリアルポート（例: COM7）")
    src_group.add_argument("--replay", help="オフライン検証用の入力ファイル（'-'で標準入力）")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUDRATE, help=f"シリアルボーレート（既定: {DEFAULT_BAUDRATE}）")
    parser.add_argument("--out", required=True, help="出力ファイルパス")
    parser.add_argument("--format", choices=["csv", "jsonl"], default="csv", help="出力形式（既定: csv）")
    parser.add_argument("--max-lines", type=int, default=None, help="この行数（正常+不正合計）を処理したら終了する（主にテスト用）")
    args = parser.parse_args()

    def on_malformed(line):
        print(f"[warn] 不正な行をスキップ: {line!r}", file=sys.stderr)

    if args.port:
        source_cm = open_serial_source(args.port, args.baud)
    else:
        source_cm = open_replay_source(args.replay)

    with source_cm as lines:
        recorded, malformed = run(lines, args.out, args.format, max_lines=args.max_lines, on_malformed=on_malformed)

    print(f"[*] 記録件数: {recorded}, 不正行スキップ: {malformed} → {args.out}")


if __name__ == "__main__":
    main()
