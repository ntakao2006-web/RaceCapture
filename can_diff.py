#!/usr/bin/env python3
"""
停車状態で決まった単一操作（ウィンカー／ヘッドライト／ドア開閉／ブレーキ等）を
OFF→ON と切り替えながら取得した2本以上のキャプチャを比較し、操作前後で
変化した CAN ID・バイト位置を自動検出するツール。
task_phase2_breakdown.md 2-4-3。

入力は can_capture_logger.py（2-4-2）が出力した CSV:
    host_iso,t_us,can_id,ext,rtr,dlc,data_hex

使い方:
    # baseline(操作OFF) と test(操作ON) を比較
    python can_diff.py --base off.csv --test on.csv

    # 複数の test を一度に（例: ウィンカー左/右）
    python can_diff.py --base off.csv --test left.csv --test right.csv

    # 合成データによる自己テスト（実機・実車不要）
    python can_diff.py --selftest

判定の考え方:
    - STRONG : そのバイトが base では固定値 A、test では固定値 B(≠A)。
               → 操作に対応している可能性が高い。
    - MEDIUM : base では固定値だったバイトが test で複数値を取り始めた
               （新しい値が base に一度も出ていない）。
    - WEAK   : base でも変動していたが、test で base に無い値域へ広がった。
    - counter: base・test の両方で値の種類が非常に多いバイト
               （ローリングカウンタとみなしノイズ扱い、STRONGからは除外）。
    - IDそのものの出現/消滅も報告する。
"""
import argparse
import csv
import io
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

COUNTER_DISTINCT_MIN = 32     # このバイトが取る値の種類がこれ以上なら「カウンタ疑い」
COUNTER_RATIO = 0.4           # かつ フレーム数 * この比率 以上の種類があれば確定でカウンタ扱い


def load_capture_csv(path):
    """2-4-2形式CSVを読み、[(t_us, can_id_int, dlc, data_bytes), ...] を返す。"""
    rows = []
    with open(path, newline="", encoding="utf-8", errors="backslashreplace") as f:
        r = csv.DictReader(f)
        for d in r:
            try:
                t_us = int(d["t_us"])
                can_id = int(d["can_id"], 16)   # "0x201" も "201" も可
                dlc = int(d["dlc"])
                raw = (d.get("data_hex") or "").strip()
                data = bytes.fromhex(raw) if raw else b""
            except (ValueError, KeyError):
                continue
            rows.append((t_us, can_id, dlc, data))
    return rows


class IdModel:
    """1つのCAN IDについて、各バイト位置が取った値の集合を保持する。"""

    def __init__(self):
        self.frames = 0
        self.byte_values = defaultdict(set)   # offset -> {int, ...}
        self.max_len = 0

    def add(self, data: bytes):
        self.frames += 1
        self.max_len = max(self.max_len, len(data))
        for i, b in enumerate(data):
            self.byte_values[i].add(b)

    def is_counter(self, offset: int) -> bool:
        n = len(self.byte_values.get(offset, ()))
        return n >= COUNTER_DISTINCT_MIN and n >= self.frames * COUNTER_RATIO

    def const_value(self, offset: int):
        vs = self.byte_values.get(offset)
        if vs and len(vs) == 1:
            return next(iter(vs))
        return None


def build_models(rows):
    models = defaultdict(IdModel)
    for _t, can_id, _dlc, data in rows:
        models[can_id].add(data)
    return models


def diff_models(base, test, min_frames):
    """base/test は {can_id: IdModel}。所見のリストを返す。"""
    findings = []
    base_ids = set(base)
    test_ids = set(test)

    for cid in sorted(test_ids - base_ids):
        m = test[cid]
        findings.append({
            "kind": "ID_APPEARED", "level": "STRONG", "can_id": cid,
            "detail": f"test でのみ出現 (frames={m.frames})",
        })
    for cid in sorted(base_ids - test_ids):
        m = base[cid]
        findings.append({
            "kind": "ID_DISAPPEARED", "level": "STRONG", "can_id": cid,
            "detail": f"base でのみ出現 (frames={m.frames})",
        })

    for cid in sorted(base_ids & test_ids):
        b, t = base[cid], test[cid]
        if b.frames < min_frames or t.frames < min_frames:
            continue
        for off in sorted(set(b.byte_values) | set(t.byte_values)):
            bvs = b.byte_values.get(off, set())
            tvs = t.byte_values.get(off, set())
            if not bvs or not tvs or bvs == tvs:
                continue
            is_counter = b.is_counter(off) or t.is_counter(off)
            bc, tc = b.const_value(off), t.const_value(off)
            new_vals = tvs - bvs

            if bc is not None and tc is not None and bc != tc:
                level = "counter" if is_counter else "STRONG"
                detail = f"byte{off}: base 固定=0x{bc:02X} → test 固定=0x{tc:02X}"
            elif bc is not None and tc is None and new_vals:
                level = "counter" if is_counter else "MEDIUM"
                detail = (f"byte{off}: base 固定=0x{bc:02X} → test で複数値 "
                          f"{{{_fmt_set(tvs)}}} (新規: {_fmt_set(new_vals)})")
            elif new_vals:
                level = "counter" if is_counter else "WEAK"
                detail = (f"byte{off}: test で base に無い値が出現 "
                          f"(新規: {_fmt_set(new_vals)}; base種類={len(bvs)} test種類={len(tvs)})")
            else:
                # test の値域が base の部分集合（縮小）: 弱い手がかりとして残す
                level = "counter" if is_counter else "WEAK"
                detail = (f"byte{off}: test の値域が縮小 "
                          f"(base種類={len(bvs)} → test種類={len(tvs)})")

            findings.append({
                "kind": "BYTE_CHANGE", "level": level, "can_id": cid,
                "offset": off, "detail": detail,
            })
    return findings


def _fmt_set(s):
    xs = sorted(s)
    if len(xs) > 8:
        return ", ".join(f"0x{x:02X}" for x in xs[:8]) + ", ..."
    return ", ".join(f"0x{x:02X}" for x in xs)


LEVEL_ORDER = {"STRONG": 0, "MEDIUM": 1, "WEAK": 2, "counter": 3}


def print_report(base_path, test_path, findings):
    print(f"=== diff: base={base_path}  test={test_path} ===")
    if not findings:
        print("  変化なし（検出された差分は0件）")
        return
    findings = sorted(findings, key=lambda f: (LEVEL_ORDER.get(f["level"], 9),
                                               f["can_id"], f.get("offset", -1)))
    for f in findings:
        print(f"  [{f['level']:<7}] 0x{f['can_id']:03X}  {f['detail']}")


# ---- 自己テスト -------------------------------------------------------
def _mk_csv(rows):
    """rows: [(t_us, can_id_int, data_bytes)] -> CSV文字列 (2-4-2形式)"""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["host_iso", "t_us", "can_id", "ext", "rtr", "dlc", "data_hex"])
    for t, cid, data in rows:
        w.writerow(["", t, f"0x{cid:X}", 0, 0, len(data), data.hex().upper()])
    return buf.getvalue()


def run_selftest() -> int:
    t = 0
    base_rows, test_rows = [], []
    for i in range(200):
        t += 1000
        # 0x100: byte2 固定 00→01 (STRONG)
        base_rows.append((t, 0x100, bytes([0x00, 0x00, 0x00, 0x00])))
        test_rows.append((t, 0x100, bytes([0x00, 0x00, 0x01, 0x00])))
        # 0x200: byte7 ローリングカウンタ（両方）→ STRONGにしない
        c = i & 0xFF
        base_rows.append((t, 0x200, bytes([0xAA, 0, 0, 0, 0, 0, 0, c])))
        test_rows.append((t, 0x200, bytes([0xAA, 0, 0, 0, 0, 0, 0, (c + 7) & 0xFF])))
        # 0x120: byte0 固定10 → test で {10,11} (MEDIUM)
        base_rows.append((t, 0x120, bytes([0x10, 0x00])))
        test_rows.append((t, 0x120, bytes([0x10 + (i % 2), 0x00])))
        # 0x130: 完全に同一（所見なし）
        base_rows.append((t, 0x130, bytes([0x55, 0x66])))
        test_rows.append((t, 0x130, bytes([0x55, 0x66])))
        # 0x300: base のみ / 0x310: test のみ
        base_rows.append((t, 0x300, bytes([0x01])))
        test_rows.append((t, 0x310, bytes([0x02])))

    base = build_models([(r[0], r[1], len(r[2]), r[2]) for r in base_rows])
    test = build_models([(r[0], r[1], len(r[2]), r[2]) for r in test_rows])
    findings = diff_models(base, test, min_frames=5)
    print_report("<synthetic-off>", "<synthetic-on>", findings)
    print()

    ok = True

    def check(cond, msg):
        nonlocal ok
        if not cond:
            ok = False
        print(f"  [{'OK  ' if cond else 'FAIL'}] {msg}")

    def find(kind, cid, off=None):
        return [f for f in findings if f["kind"] == kind and f["can_id"] == cid
                and (off is None or f.get("offset") == off)]

    f100 = find("BYTE_CHANGE", 0x100, 2)
    check(bool(f100) and f100[0]["level"] == "STRONG", "0x100 byte2 が STRONG")
    f200 = find("BYTE_CHANGE", 0x200, 7)
    check(bool(f200) and f200[0]["level"] == "counter", "0x200 byte7 は counter 扱い（STRONG除外）")
    f120 = find("BYTE_CHANGE", 0x120, 0)
    check(bool(f120) and f120[0]["level"] == "MEDIUM", "0x120 byte0 が MEDIUM")
    check(not find("BYTE_CHANGE", 0x130), "0x130 は所見なし")
    check(bool(find("ID_DISAPPEARED", 0x300)), "0x300 の消滅を検出")
    check(bool(find("ID_APPEARED", 0x310)), "0x310 の出現を検出")
    # STRONG の筆頭が 0x100 byte2 であること
    strong = [f for f in sorted(findings, key=lambda f: (LEVEL_ORDER[f["level"]], f["can_id"]))
              if f["level"] == "STRONG"]
    check(strong and strong[0]["can_id"] == 0x100, "STRONG の筆頭が 0x100")

    print()
    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ---- main -----------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="操作前後のCAN差分検出 (2-4-3)")
    p.add_argument("--base", help="baseline(操作OFF)のキャプチャCSV")
    p.add_argument("--test", action="append", default=[], help="操作ONのキャプチャCSV（複数可）")
    p.add_argument("--min-frames", type=int, default=5, help="この本数未満のIDは比較対象外")
    p.add_argument("--selftest", action="store_true", help="合成データで自己テスト")
    p.add_argument("--json", action="store_true", help="所見をJSONでも出力")
    args = p.parse_args()

    if args.selftest:
        sys.exit(run_selftest())
    if not args.base or not args.test:
        p.error("--base と少なくとも1つの --test が必要です（または --selftest）")

    base = build_models(load_capture_csv(args.base))
    all_json = []
    for test_path in args.test:
        test = build_models(load_capture_csv(test_path))
        findings = diff_models(base, test, args.min_frames)
        print_report(args.base, test_path, findings)
        print()
        if args.json:
            all_json.append({"base": args.base, "test": test_path,
                             "findings": [{**f, "can_id": f"0x{f['can_id']:03X}"} for f in findings]})
    if args.json:
        import json
        print(json.dumps(all_json, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
