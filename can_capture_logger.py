#!/usr/bin/env python3
"""
firmware/can_logger（生CANリードオンリーロガー、2-4-1）のUSBシリアル出力を
PC側で受信し、CSV / JSON Lines へ記録するツール。
task_phase2_breakdown.md 2-4-2。

can_logger の出力形式（この形式を入力インターフェースの前提にする）:
  - フレーム行 : t_us,id_hex,ext,rtr,dlc,data_hex
                 例) 123456789,201,0,0,8,0011223344556677
                 dlc=0 や rtr=1 のときは data_hex 部が空（末尾カンマのみ）
  - ステータス行: '#' 始まり
                 例) # stat t=... total=... rate=.../s drop_rb=... rx_missed=...
                     rx_overrun=... buserr=... tec=... rec=... state=RUNNING alerts=0x0
                 起動直後のバナー（'# ===== ...' 等）も '#' 始まりでここに含める

使い方:
    # 実機から受信して記録（COM5, 115200bps）
    python can_capture_logger.py --port COM5 --out capture_run1

    # 取り込み経路の確認用に10秒だけ回す
    python can_capture_logger.py --port COM5 --out probe --limit-seconds 10

    # 既存のテキストダンプ（pio device monitor の保存等）を変換
    python can_capture_logger.py --replay samples/can_logger_sample.txt --out sample --format both

    # 合成データによる自己テスト（実機・実車不要）
    python can_capture_logger.py --selftest

出力ファイル（--out <prefix> に対して）:
    <prefix>.csv        フレーム行   host_iso,t_us,can_id,ext,rtr,dlc,data_hex
    <prefix>.jsonl      フレーム行   {"host_iso":..,"t_us":..,"can_id":"0x201",..,"data":".."}
    <prefix>.status.log ステータス行 host_iso <TAB> 生のステータス行

host_iso は「PC側でその行を受信・処理した時刻」(ISO8601)。--replay 時は変換実行時刻に
なるため相対時刻としては使えない点に注意（フレーム間隔は t_us 列を使う）。
"""
import argparse
import io
import json
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def _host_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CaptureWriter:
    """フレーム行 / ステータス行を受け取り、CSV・JSONL・statusログへ振り分ける。"""

    def __init__(self, prefix: str, fmt: str, echo: bool = False):
        self.prefix = prefix
        self.want_csv = fmt in ("csv", "both")
        self.want_jsonl = fmt in ("jsonl", "both")
        self.echo = echo

        self.csv_f = None
        self.jsonl_f = None
        self.status_f = open(f"{prefix}.status.log", "w", encoding="utf-8")
        if self.want_csv:
            self.csv_f = open(f"{prefix}.csv", "w", encoding="utf-8", newline="")
            self.csv_f.write("host_iso,t_us,can_id,ext,rtr,dlc,data_hex\n")
        if self.want_jsonl:
            self.jsonl_f = open(f"{prefix}.jsonl", "w", encoding="utf-8")

        # 統計
        self.frames = 0
        self.parse_errors = 0
        self.status_lines = 0
        self.id_counts = Counter()
        self.first_t_us = None
        self.last_t_us = None
        self.max_drop_rb = 0
        self.max_rx_missed = 0
        self.max_rx_overrun = 0
        self.max_buserr = 0
        self.last_state = None
        self._err_samples = []

    # -- 1行を処理 -------------------------------------------------------
    def feed_line(self, raw: str) -> None:
        line = raw.strip()
        if not line:
            return
        if line.startswith("#"):
            self._handle_status(line)
        else:
            self._handle_frame(line)

    def _handle_status(self, line: str) -> None:
        self.status_lines += 1
        self.status_f.write(f"{_host_iso()}\t{line}\n")
        if self.echo:
            print(line)
        # '# stat key=value ...' のトークンを拾えるだけ拾う
        toks = {}
        for tok in line.lstrip("#").split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                toks[k] = v
        self.max_drop_rb = max(self.max_drop_rb, _safe_int(toks.get("drop_rb")))
        self.max_rx_missed = max(self.max_rx_missed, _safe_int(toks.get("rx_missed")))
        self.max_rx_overrun = max(self.max_rx_overrun, _safe_int(toks.get("rx_overrun")))
        self.max_buserr = max(self.max_buserr, _safe_int(toks.get("buserr")))
        if "state" in toks:
            self.last_state = toks["state"]

    def _handle_frame(self, line: str) -> None:
        # t_us,id_hex,ext,rtr,dlc,data_hex   (data_hex は無いこともある)
        parts = line.split(",")
        if len(parts) < 5:
            self._record_error(line)
            return
        try:
            t_us = int(parts[0])
            can_id = int(parts[1], 16)
            ext = int(parts[2])
            rtr = int(parts[3])
            dlc = int(parts[4])
            data_hex = parts[5].strip().upper() if len(parts) >= 6 else ""
        except ValueError:
            self._record_error(line)
            return
        if ext not in (0, 1) or rtr not in (0, 1) or not (0 <= dlc <= 8):
            self._record_error(line)
            return
        # data_hex の桁数チェック（rtr フレームはデータ無し）
        expect_hex = 0 if rtr else dlc * 2
        if len(data_hex) != expect_hex or (data_hex and not _is_hex(data_hex)):
            # 桁ずれは捨てずに記録するが、エラーカウントは立てる
            self._record_error(line, keep=True)

        self.frames += 1
        self.id_counts[can_id] += 1
        if self.first_t_us is None:
            self.first_t_us = t_us
        self.last_t_us = t_us

        can_id_s = f"0x{can_id:X}"
        host = _host_iso()
        if self.csv_f:
            self.csv_f.write(f"{host},{t_us},{can_id_s},{ext},{rtr},{dlc},{data_hex}\n")
        if self.jsonl_f:
            self.jsonl_f.write(json.dumps({
                "host_iso": host, "t_us": t_us, "can_id": can_id_s,
                "ext": ext, "rtr": rtr, "dlc": dlc, "data": data_hex,
            }) + "\n")
        if self.echo:
            print(f"{t_us} {can_id_s} dlc={dlc} {data_hex}")

    def _record_error(self, line: str, keep: bool = False) -> None:
        self.parse_errors += 1
        if len(self._err_samples) < 5:
            self._err_samples.append(line)
        if not keep:
            pass  # フレームには数えない

    # -- 後始末・サマリ -------------------------------------------------
    def close(self) -> None:
        for f in (self.csv_f, self.jsonl_f, self.status_f):
            if f:
                f.close()

    def summary(self) -> str:
        span_s = None
        if self.first_t_us is not None and self.last_t_us is not None:
            span_s = (self.last_t_us - self.first_t_us) / 1_000_000
        lines = []
        lines.append("==== capture summary ====")
        lines.append(f"frames            : {self.frames}")
        if span_s and span_s > 0:
            lines.append(f"t_us span         : {span_s:.3f} s  ({self.frames / span_s:.1f} frame/s)")
        lines.append(f"unique CAN IDs     : {len(self.id_counts)}")
        for cid, cnt in self.id_counts.most_common(20):
            lines.append(f"    0x{cid:03X} : {cnt}")
        lines.append(f"status lines       : {self.status_lines}  (last state={self.last_state})")
        lines.append(f"max drop_rb        : {self.max_drop_rb}")
        lines.append(f"max rx_missed      : {self.max_rx_missed}")
        lines.append(f"max rx_overrun     : {self.max_rx_overrun}")
        lines.append(f"max buserr         : {self.max_buserr}")
        lines.append(f"parse errors       : {self.parse_errors}")
        for s in self._err_samples:
            lines.append(f"    ! {s!r}")
        return "\n".join(lines)


def _safe_int(v) -> int:
    try:
        return int(str(v), 0)
    except (ValueError, TypeError):
        return 0


def _is_hex(s: str) -> bool:
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


# ---- 入力ソース -----------------------------------------------------------
def run_replay(path: str, writer: CaptureWriter) -> None:
    with open(path, "r", encoding="utf-8", errors="backslashreplace") as f:
        for line in f:
            writer.feed_line(line)


def run_serial(port: str, baud: int, writer: CaptureWriter, limit_seconds: float) -> None:
    import serial  # 遅延import（--replay/--selftest では pyserial 不要）

    deadline = time.monotonic() + limit_seconds if limit_seconds > 0 else None
    buf = b""
    first_line_dropped = False  # 接続時に途中から拾った端数行は捨てる
    print(f"[*] {port} @ {baud}bps を受信中... (Ctrl+C で停止)", flush=True)
    with serial.Serial(port, baud, timeout=0.2) as ser:
        try:
            while True:
                if deadline and time.monotonic() >= deadline:
                    print("[*] --limit-seconds に到達、停止します。", flush=True)
                    break
                chunk = ser.read(4096)
                if chunk:
                    buf += chunk
                    while b"\n" in buf:
                        raw, buf = buf.split(b"\n", 1)
                        if not first_line_dropped:
                            first_line_dropped = True
                            continue
                        writer.feed_line(raw.decode("utf-8", errors="backslashreplace"))
                else:
                    time.sleep(0.02)
        except KeyboardInterrupt:
            print("\n[*] Ctrl+C、停止します。", flush=True)
        # 端数（先頭端数を捨てる前なら、これも端数なので捨てる）
        if buf.strip() and first_line_dropped:
            writer.feed_line(buf.decode("utf-8", errors="backslashreplace"))


# ---- 自己テスト ---------------------------------------------------------
SELFTEST_INPUT = """

# ===== CAN read-only logger (LISTEN_ONLY / no bus injection) =====
# bitrate=500k, RX=GPIO20
# line format: t_us,id_hex,ext,rtr,dlc,data_hex   (lines starting with '#' are status)
# TWAI started in LISTEN_ONLY. logging...
1000000,201,0,0,8,00112233445566DD
1002000,4B0,0,0,8,0102030405060708
1002500,201,0,0,8,00112233445566DE
1003000,231,0,0,2,0200
1003200,7E8,0,0,8,0641050000000000
1004000,100,0,1,0,
1004500,3FF,0,0,0,
# stat t=2000000 total=6 rate=6/s drop_rb=0 rx_missed=0 rx_overrun=0 buserr=0 tec=0 rec=0 state=RUNNING alerts=0x0
1005000,201,0,0,8,00112233445566DF
9999,GARBAGE,line,here
2000000,201,0,0,8,00112233445566E0
# stat t=3000000 total=9 rate=3/s drop_rb=2 rx_missed=1 rx_overrun=0 buserr=0 tec=0 rec=0 state=RUNNING alerts=0x0
"""


def run_selftest() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="cancap_selftest_"))
    prefix = str(tmp / "st")
    w = CaptureWriter(prefix, "both")
    for line in io.StringIO(SELFTEST_INPUT):
        w.feed_line(line)
    w.close()

    ok = True

    def check(cond, msg):
        nonlocal ok
        mark = "OK  " if cond else "FAIL"
        if not cond:
            ok = False
        print(f"  [{mark}] {msg}")

    csv_lines = Path(f"{prefix}.csv").read_text(encoding="utf-8").splitlines()
    jsonl_lines = Path(f"{prefix}.jsonl").read_text(encoding="utf-8").splitlines()
    status_lines = Path(f"{prefix}.status.log").read_text(encoding="utf-8").splitlines()

    # 有効フレーム: 8個（201×4, 4B0, 231, 7E8, 100(rtr), 3FF(dlc0)）= 9個 だが
    # "9999,GARBAGE,.." は5フィールドあるが数値変換で弾かれる → 9個
    check(w.frames == 9, f"frames == 9 (got {w.frames})")
    check(len(csv_lines) == 1 + 9, f"CSV 行数 == ヘッダ+9 (got {len(csv_lines)})")
    check(len(jsonl_lines) == 9, f"JSONL 行数 == 9 (got {len(jsonl_lines)})")
    check(w.parse_errors == 1, f"parse_errors == 1 (GARBAGE行のみ) (got {w.parse_errors})")
    check(w.id_counts[0x201] == 4, f"0x201 のカウント == 4 (got {w.id_counts[0x201]})")
    check(len(w.id_counts) == 6, f"unique ID == 6 (got {len(w.id_counts)})")
    check(w.status_lines == 6, f"status行 == バナー4+stat2 == 6 (got {w.status_lines})")
    check(w.max_drop_rb == 2, f"max drop_rb == 2 (got {w.max_drop_rb})")
    check(w.max_rx_missed == 1, f"max rx_missed == 1 (got {w.max_rx_missed})")
    check(w.last_state == "RUNNING", f"last state == RUNNING (got {w.last_state})")

    # rtr フレームは data 空、dlc=0 も空
    rtr_row = [l for l in csv_lines if ",0x100," in l][0]
    check(rtr_row.endswith(",1,0,"), f"rtr行の data_hex 空 (got {rtr_row!r})")
    j0 = json.loads(jsonl_lines[0])
    check(j0["can_id"] == "0x201" and j0["dlc"] == 8 and j0["data"] == "00112233445566DD",
          f"JSONL先頭のデコード (got {j0})")

    print()
    print(w.summary())
    print()
    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ---- main -------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description="can_logger 出力の受信・記録ツール (2-4-2)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--port", help="シリアルポート (例: COM5)")
    src.add_argument("--replay", help="既存テキストダンプを変換")
    src.add_argument("--selftest", action="store_true", help="合成データで自己テスト")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--out", help="出力ファイルの接頭辞 (例: capture_run1)")
    p.add_argument("--format", choices=["csv", "jsonl", "both"], default="csv")
    p.add_argument("--limit-seconds", type=float, default=0, help=">0 でその秒数後に自動停止")
    p.add_argument("--echo", action="store_true", help="受信行を標準出力にも表示")
    args = p.parse_args()

    if args.selftest:
        sys.exit(run_selftest())

    if not args.out:
        p.error("--port / --replay 時は --out が必須です")

    writer = CaptureWriter(args.out, args.format, echo=args.echo)
    try:
        if args.replay:
            run_replay(args.replay, writer)
        else:
            run_serial(args.port, args.baud, writer, args.limit_seconds)
    finally:
        writer.close()
    print()
    print(writer.summary())
    print()
    print(f"[*] 保存: {args.out}.csv / .jsonl / .status.log （--format={args.format}）")


if __name__ == "__main__":
    main()
