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

    # 運転中に手を出せない無人キャプチャ（can_obd_logger のポーリングを時刻で自動切替）
    #   passive=ポーリング停止('p') / poll=再開('r') / mark=印だけ
    #   区切りは status ログへ残り、can_split_phases.py でフェーズ別CSVへ分割できる
    python can_capture_logger.py --port COM5 --out run1 --limit-seconds 3660 \
        --phase-plan "0:passive:ig_on,480:poll:idle_obd,780:poll:drive,3000:passive:drive_passive"

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

    # -- 明示フラッシュ（無人キャプチャ中の取りこぼし対策） ---------------
    def flush(self) -> None:
        """開いている出力ファイルをすべてOSへ書き出す。

        車載で放置したままキャプチャする運用では、PCのスリープ・電源断・
        プロセス強制終了で Python 側のバッファが失われうる。定期的に呼ぶことで
        失う範囲を直近の数秒だけに抑える。
        """
        for f in (self.csv_f, self.jsonl_f, self.status_f):
            if f is not None:
                f.flush()

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


# ---- フェーズ計画（無人セッションの自動進行） -----------------------------
# can_obd_logger のランタイムキー（firmware/can_obd_logger/src/main.cpp）:
#   'p' … OBD2 PIDポーリング停止（完全受動の観測へ。ただしACKは返る）
#   'r' … ポーリング再開
PHASE_ACTIONS = {
    "passive": b"p",   # ポーリング停止
    "poll":    b"r",   # ポーリング再開
    "probe":   b"d",   # mode 22 のDIDプローブを1回実行（読み出しのみ）
    "scan":    b"s",   # mode 22 のDIDスキャン 0x0000-0x0FFF（読み出しのみ、約3分）
    "watch":   b"w",   # mode 22 の未知DIDを3分間くり返し読む（読み出しのみ）
    "mark":    None,   # キーは送らず、区切りマーカーだけ残す
}


class PhasePlan:
    """`--phase-plan` の指定に従い、経過秒で計測フェーズを自動で切り替える。

    運転中はキーボードを触れないため、「出発前は受動観測 → 走り出したらOBD
    ポーリング → 終盤にもう一度受動」といった進行をホスト側のタイマーで行う。
    切替のたびに status ログへ `# host: phase ...` を残すので、後から
    can_split_phases.py でフェーズごとのCSVへ分割できる。

    指定形式は "SEC:ACTION[:LABEL]" のカンマ区切り（SECはキャプチャ開始からの経過秒）。
        例) "0:passive:ig_on,180:poll:idle,300:poll:drive,2700:passive:drive_passive"
    """

    def __init__(self, entries):
        self.entries = entries      # [(sec, action, label), ...] secの昇順
        self.next_idx = 0
        self.applied = None         # 直近に適用したエントリ（再接続時の再送用）

    @classmethod
    def parse(cls, spec: str) -> "PhasePlan":
        entries = []
        for i, item in enumerate(spec.split(",")):
            item = item.strip()
            if not item:
                continue
            parts = item.split(":", 2)
            if len(parts) < 2:
                raise ValueError(f"フェーズ指定 {item!r} は SEC:ACTION[:LABEL] 形式で書く")
            try:
                sec = float(parts[0])
            except ValueError:
                raise ValueError(f"フェーズ指定 {item!r} の秒数が数値でない")
            if sec < 0:
                raise ValueError(f"フェーズ指定 {item!r} の秒数が負")
            action = parts[1].strip().lower()
            if action not in PHASE_ACTIONS:
                raise ValueError(
                    f"フェーズ指定 {item!r} の動作 {action!r} は "
                    f"{'/'.join(PHASE_ACTIONS)} のいずれかにする")
            label = parts[2].strip() if len(parts) >= 3 and parts[2].strip() else f"phase{i + 1}"
            label = label.replace(" ", "_").replace("\t", "_")
            entries.append((sec, action, label))
        if not entries:
            raise ValueError("フェーズ指定が空")
        entries.sort(key=lambda e: e[0])
        return cls(entries)

    def total_seconds(self) -> float:
        return self.entries[-1][0]

    def due(self, elapsed: float):
        """期限が来て未消化のエントリを古い順に返す（返した分は消化済みにする）。"""
        out = []
        while self.next_idx < len(self.entries) and self.entries[self.next_idx][0] <= elapsed:
            out.append(self.entries[self.next_idx])
            self.next_idx += 1
        if out:
            self.applied = out[-1]
        return out

    def resume_entry(self):
        """再接続直後に状態を作り直すためのエントリ（直近に適用したもの）。

        USBが抜き差しされてESP32がリセットされると poll=on の初期状態へ戻るため、
        受動フェーズの途中なら 'p' を送り直す必要がある。
        """
        return self.applied


def _apply_phase(ser, writer: CaptureWriter, entry, elapsed: float, resumed: bool = False) -> None:
    sec, action, label = entry
    key = PHASE_ACTIONS[action]
    sent = "-"
    if key is not None and ser is not None:
        # ser.flush()（送信完了待ち）は呼ばない。Windowsの実装では write_timeout が
        # 効かず、相手が読まないと無限に待つため、ここでキャプチャ全体が止まる。
        try:
            ser.write(key)
            sent = key.decode()
        except Exception as e:                  # noqa: BLE001 送信失敗でキャプチャは止めない
            sent = f"ERR({e.__class__.__name__})"
            print(f"[!] フェーズキー '{key.decode()}' の送信に失敗しました（{e}）。"
                  f"記録は継続します（区切りマーカーは残るので後処理では区別できます）。",
                  flush=True)
    tag = "phase-resume" if resumed else "phase"
    writer.feed_line(
        f"# host: {tag} t={elapsed:.1f}s at={sec:g}s action={action} key={sent} label={label}")
    writer.flush()
    print(f"[*] {elapsed:7.0f}s フェーズ {action:7s} key={sent:3s} {label}", flush=True)


# ---- 入力ソース -----------------------------------------------------------
def run_replay(path: str, writer: CaptureWriter) -> None:
    with open(path, "r", encoding="utf-8", errors="backslashreplace") as f:
        for line in f:
            writer.feed_line(line)


def run_serial(port: str, baud: int, writer: CaptureWriter, limit_seconds: float,
               reconnect: bool = True, flush_interval: float = 2.0,
               plan=None) -> None:
    """シリアルからライブ受信する。

    車載で走り出してから放置する運用を想定し、次の2点を備える。
      - 自動再接続：段差でのコネクタ揺れやUSBの一時的な切断でキャプチャ全体を
        落とさない。切断のたびに `# host: serial ...` 行を status ログへ残すので、
        後から「どこで途切れたか」を追える。
      - 定期フラッシュ：PCのスリープ・強制終了で失う範囲を直近数秒に抑える。

    `plan`（PhasePlan）を渡すと、経過秒に応じて can_obd_logger のポーリングを
    自動で停止／再開し（'p'/'r'）、status ログにフェーズの区切りを書き残す。
    運転中に手を出さずに計測メニューを消化するための機能。
    """
    import serial  # 遅延import（--replay/--selftest では pyserial 不要）
    from serial import SerialException

    started = time.monotonic()
    deadline = started + limit_seconds if limit_seconds > 0 else None
    next_flush = started + flush_interval
    attempt = 0
    print(f"[*] {port} @ {baud}bps を受信中... (Ctrl+C で停止)", flush=True)

    try:
        while True:
            if deadline and time.monotonic() >= deadline:
                print("[*] --limit-seconds に到達、停止します。", flush=True)
                return

            buf = b""
            first_line_dropped = False  # 接続時に途中から拾った端数行は捨てる
            try:
                # write_timeout は必須。ESP32-C3のUSB Serial/JTAGは相手が読まないと
                # ホスト側の書き込みが詰まるため、無指定だとフェーズ送信でハングする。
                with serial.Serial(port, baud, timeout=0.2, write_timeout=0.5) as ser:
                    if attempt:
                        msg = f"# host: serial reconnected to {port} (attempt {attempt})"
                        print(f"[*] {port} へ再接続しました (試行{attempt}回目)", flush=True)
                        writer.feed_line(msg)
                    attempt = 0
                    if plan is not None:
                        # 期限が来ている分をまず消化し、その後で現在のフェーズを
                        # 送り直す（再接続でESP32がリセットされていた場合の復旧）。
                        elapsed = time.monotonic() - started
                        for entry in plan.due(elapsed):
                            _apply_phase(ser, writer, entry, elapsed)
                        resume = plan.resume_entry()
                        if resume is not None:
                            _apply_phase(ser, writer, resume, elapsed, resumed=True)
                    while True:
                        now = time.monotonic()
                        if deadline and now >= deadline:
                            print("[*] --limit-seconds に到達、停止します。", flush=True)
                            return
                        if now >= next_flush:
                            writer.flush()
                            next_flush = now + flush_interval
                        if plan is not None:
                            elapsed = now - started
                            for entry in plan.due(elapsed):
                                _apply_phase(ser, writer, entry, elapsed)
                        chunk = ser.read(4096)
                        if chunk:
                            buf += chunk
                            while b"\n" in buf:
                                raw, buf = buf.split(b"\n", 1)
                                if not first_line_dropped:
                                    first_line_dropped = True
                                    continue
                                writer.feed_line(
                                    raw.decode("utf-8", errors="backslashreplace"))
                        else:
                            time.sleep(0.02)
            except SerialException as e:
                # 端数は捨てる（切断で途中まで届いた行の可能性が高い）
                writer.feed_line(f"# host: serial lost ({e.__class__.__name__}: {e})")
                writer.flush()
                if not reconnect:
                    print(f"[!] シリアルが切断されました: {e}", flush=True)
                    return
                attempt += 1
                if attempt == 1:
                    print(f"[!] シリアルが切断されました: {e}", flush=True)
                    print("[*] 再接続を試行中...（--no-reconnect で無効化）", flush=True)
                time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[*] Ctrl+C、停止します。", flush=True)
    finally:
        writer.flush()


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

    # ---- フェーズ計画（--phase-plan）の検証 ----
    print()
    print("  -- PhasePlan --")
    plan = PhasePlan.parse("300:poll:drive,0:passive:ig_on,180:poll, 600:mark:halfway ")
    check([e[0] for e in plan.entries] == [0, 180, 300, 600],
          f"秒の昇順に並べ替える (got {[e[0] for e in plan.entries]})")
    check(plan.entries[1][2] == "phase3",
          f"ラベル省略時は phaseN (got {plan.entries[1][2]!r})")
    check(plan.entries[3][2] == "halfway",
          f"前後の空白を落とす (got {plan.entries[3][2]!r})")
    check(plan.total_seconds() == 600, f"total_seconds == 600 (got {plan.total_seconds()})")

    for bad in ("", "abc:poll", "-5:poll", "100:sleep", "100"):
        try:
            PhasePlan.parse(bad)
            check(False, f"不正指定 {bad!r} で ValueError")
        except ValueError:
            check(True, f"不正指定 {bad!r} で ValueError")

    check([e[2] for e in plan.due(0)] == ["ig_on"], "t=0 で最初のフェーズだけ期限到来")
    check(plan.due(10) == [], "t=10 では追加なし（消化済みは再送しない）")
    check([e[2] for e in plan.due(350)] == ["phase3", "drive"],
          "飛び越した分も古い順にまとめて消化する")
    check(plan.resume_entry()[2] == "drive", "resume_entry は直近に適用したフェーズ")

    class _FakeSerial:
        """_apply_phase がキーを書き出すかを見るためのダミー。"""

        def __init__(self):
            self.written = b""

        def write(self, b):
            self.written += b

        def flush(self):
            pass

    tmp2 = Path(tempfile.mkdtemp(prefix="cancap_phase_"))
    w2 = CaptureWriter(str(tmp2 / "ph"), "csv")
    ser = _FakeSerial()
    _apply_phase(ser, w2, (0, "passive", "ig_on"), 0.0)
    _apply_phase(ser, w2, (180, "poll", "idle"), 181.2)
    _apply_phase(ser, w2, (600, "mark", "halfway"), 600.0)
    _apply_phase(ser, w2, (180, "poll", "idle"), 900.0, resumed=True)
    w2.close()
    check(ser.written == b"prr", f"passive->p / poll->r / mark->送信なし (got {ser.written!r})")
    ph_log = Path(f"{tmp2 / 'ph'}.status.log").read_text(encoding="utf-8")
    check(ph_log.count("# host: phase ") == 3,
          f"フェーズマーカーが3行 (got {ph_log.count('# host: phase ')})")
    check("# host: phase-resume " in ph_log, "再接続時のマーカーは phase-resume")
    check("action=passive key=p label=ig_on" in ph_log,
          "マーカーに action / key / label が載る")

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
    p.add_argument("--phase-plan",
                   help="経過秒で計測フェーズを自動切替する（--port 時のみ）。"
                        "SEC:ACTION[:LABEL] のカンマ区切り。ACTIONは "
                        "passive(=ポーリング停止p) / poll(=再開r) / mark(=印だけ)。"
                        "例: 0:passive:ig_on,180:poll:idle,300:poll:drive")
    p.add_argument("--no-reconnect", action="store_true",
                   help="切断時に自動再接続せず終了する（既定は再接続する）")
    args = p.parse_args()

    if args.selftest:
        sys.exit(run_selftest())

    if not args.out:
        p.error("--port / --replay 時は --out が必須です")

    plan = None
    if args.phase_plan:
        if not args.port:
            p.error("--phase-plan は --port（ライブ受信）でのみ使えます")
        try:
            plan = PhasePlan.parse(args.phase_plan)
        except ValueError as e:
            p.error(str(e))
        print("[*] フェーズ計画:")
        for sec, action, label in plan.entries:
            print(f"      {sec:7.0f}s  {action:7s}  {label}")
        if args.limit_seconds and plan.total_seconds() > args.limit_seconds:
            print(f"[!] 最終フェーズ({plan.total_seconds():.0f}s)が "
                  f"--limit-seconds({args.limit_seconds:.0f}s)より後です。到達しません。")

    writer = CaptureWriter(args.out, args.format, echo=args.echo)
    try:
        if args.replay:
            run_replay(args.replay, writer)
        else:
            run_serial(args.port, args.baud, writer, args.limit_seconds,
                       reconnect=not args.no_reconnect, plan=plan)
    finally:
        writer.close()
    print()
    print(writer.summary())
    print()
    print(f"[*] 保存: {args.out}.csv / .jsonl / .status.log （--format={args.format}）")


if __name__ == "__main__":
    main()
