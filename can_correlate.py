#!/usr/bin/env python3
"""
OBD2 PID で並行取得できる既知の値（車速・回転数など）と、生CANキャプチャ中の
候補バイト列（例: 2-0-8 で観測した 0x4B0 のホイールスピード疑い）との相関を
線形回帰で検証するツール。
task_phase2_breakdown.md 2-4-5。

入力:
    --can FILE : can_capture_logger.py（2-4-2）の CSV
                 host_iso,t_us,can_id,ext,rtr,dlc,data_hex
    --ref FILE : 基準値の時系列 CSV。既定では先頭2列を (時刻, 値) として読む
                 （ヘッダに t,value があればそれを使う）。時刻の単位は --ref-time-unit。
                 ELM327 併用ログでも、生CANログ中の 7E8 応答をデコードしたものでも、
                 とにかく「時刻付きの基準値列」であれば何でもよい。

各 CAN ID について、各バイト位置・幅(1/2バイト)・エンディアンで数値化した系列を作り、
基準値のサンプル時刻ごとに「直近のCAN値」(ゼロ次ホールド)を取って (x, ref) ペアを作り、
ref ≒ a*x + b の最小二乗回帰の決定係数 R² で順位付けする。

CAN側の時刻は ESP32 起動からの相対マイクロ秒なので、基準値の時計とは原点がずれる。
--time-offset で秒単位の下駄をはかせるか、--auto-lag で粗く探索する。

使い方:
    python can_correlate.py --can run1.csv --ref speed_from_obd2.csv --ref-name speed_kmh \\
        --candidate-id 0x4B0 --auto-lag -2:2:0.1

    python can_correlate.py --selftest      # 実機・実車不要
"""
import argparse
import csv
import io
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


# ---- 入力読み込み ---------------------------------------------------------
def load_can(path, time_offset_s=0.0):
    """{can_id: [(t_s, data_bytes), ...]} を返す。"""
    by_id = defaultdict(list)
    with open(path, newline="", encoding="utf-8", errors="backslashreplace") as f:
        for d in csv.DictReader(f):
            try:
                t_s = int(d["t_us"]) / 1_000_000 + time_offset_s
                cid = int(d["can_id"], 16)
                raw = (d.get("data_hex") or "").strip()
                data = bytes.fromhex(raw) if raw else b""
            except (ValueError, KeyError):
                continue
            if data:
                by_id[cid].append((t_s, data))
    for cid in by_id:
        by_id[cid].sort()
    return by_id


def load_ref(path, time_unit="s"):
    """[(t_s, value), ...] を時刻昇順で返す。"""
    div = {"s": 1.0, "ms": 1e3, "us": 1e6}[time_unit]
    rows = []
    with open(path, newline="", encoding="utf-8", errors="backslashreplace") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        ti, vi = 0, 1
        if header:
            low = [h.strip().lower() for h in header]
            if "t" in low and "value" in low:
                ti, vi = low.index("t"), low.index("value")
                is_header = True
            else:
                # 先頭行が数値なら header ではなくデータ
                try:
                    float(header[0]); float(header[1])
                    is_header = False
                except (ValueError, IndexError):
                    is_header = True
            if not is_header:
                rows.append((float(header[ti]) / div, float(header[vi])))
        for r in reader:
            if len(r) <= max(ti, vi):
                continue
            try:
                rows.append((float(r[ti]) / div, float(r[vi])))
            except ValueError:
                continue
    rows.sort()
    return rows


# ---- 数値化 -------------------------------------------------------------
def decode_series(frames, offset, width, endian):
    """frames: [(t_s, data)] -> [(t_s, x)]  (data が短いフレームは飛ばす)"""
    out = []
    for t_s, data in frames:
        if len(data) < offset + width:
            continue
        chunk = data[offset:offset + width]
        x = int.from_bytes(chunk, "big" if endian == "big" else "little")
        out.append((t_s, x))
    return out


def zoh_pairs(decoded, ref, max_hold_s):
    """基準値の各時刻に対し、直近(<=)のCAN値をゼロ次ホールドで対応付ける。"""
    pairs = []
    j = 0
    n = len(decoded)
    for t_ref, v in ref:
        while j + 1 < n and decoded[j + 1][0] <= t_ref:
            j += 1
        if j < n and decoded[j][0] <= t_ref and (t_ref - decoded[j][0]) <= max_hold_s:
            pairs.append((decoded[j][1], v))
    return pairs


def linregress(pairs):
    """(x, y) の最小二乗。 (slope, intercept, r2, n) を返す。"""
    n = len(pairs)
    if n < 2:
        return None
    sx = sum(x for x, _ in pairs)
    sy = sum(y for _, y in pairs)
    sxx = sum(x * x for x, _ in pairs)
    sxy = sum(x * y for x, y in pairs)
    syy = sum(y * y for _, y in pairs)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None  # x が定数
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    ss_tot = syy - sy * sy / n
    ss_res = syy - intercept * sy - slope * sxy
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    return slope, intercept, r2, n


# ---- 相関スキャン ------------------------------------------------------
def scan(by_id, ref, candidate_ids, widths, endians, min_samples, max_hold_s):
    results = []
    ids = candidate_ids if candidate_ids else sorted(by_id)
    for cid in ids:
        frames = by_id.get(cid)
        if not frames:
            continue
        maxlen = max(len(d) for _t, d in frames)
        for width in widths:
            for offset in range(0, maxlen - width + 1):
                for endian in (endians if width > 1 else ["big"]):
                    decoded = decode_series(frames, offset, width, endian)
                    if len(decoded) < min_samples:
                        continue
                    xs = {x for _t, x in decoded}
                    if len(xs) < 2:
                        continue
                    pairs = zoh_pairs(decoded, ref, max_hold_s)
                    if len(pairs) < min_samples:
                        continue
                    lr = linregress(pairs)
                    if lr is None:
                        continue
                    slope, intercept, r2, n = lr
                    results.append({
                        "can_id": cid, "offset": offset, "width": width,
                        "endian": endian if width > 1 else "-",
                        "slope": slope, "intercept": intercept, "r2": r2, "n": n,
                    })
    results.sort(key=lambda d: d["r2"], reverse=True)
    return results


def best_r2(results):
    return results[0]["r2"] if results else -1.0


def frange(spec):
    lo, hi, step = (float(x) for x in spec.split(":"))
    vals, v = [], lo
    while v <= hi + 1e-9:
        vals.append(round(v, 6))
        v += step
    return vals


def print_table(results, ref_name, top):
    print(f"  {'can_id':>7} {'off':>3} {'w':>1} {'end':>6} {'n':>5} "
          f"{'slope':>14} {'intercept':>12} {'R^2':>8}   ({ref_name} ≒ slope*x + intercept)")
    for r in results[:top]:
        print(f"  0x{r['can_id']:03X}   {r['offset']:>3} {r['width']:>1} {r['endian']:>6} "
              f"{r['n']:>5} {r['slope']:>14.6g} {r['intercept']:>12.6g} {r['r2']:>8.5f}")


# ---- 自己テスト -------------------------------------------------------
def _tri(t, period=40.0, peak=100.0):
    """0→peak→0 の三角波"""
    x = (t % period) / period
    return peak * (2 * x if x < 0.5 else 2 * (1 - x))


def run_selftest() -> int:
    # 真の関係: 0x4B0 の byte0-1(BE u16) = round(speed_kmh / 0.01)
    # 基準値(ref)は 1Hz の speed_kmh。CAN 側の時刻は ref より 0.3s 進んでいる設定。
    true_slope = 0.01
    lag = 0.3
    can_rows = []
    t = 0.0
    while t < 60.0:
        speed = _tri(t)
        raw = max(0, min(0xFFFF, round(speed / true_slope)))
        b = raw.to_bytes(2, "big") + b"\x00\x00" + (int(t * 13) & 0xFF).to_bytes(1, "big") + b"\x00\x00\x00"
        can_rows.append((t + lag, 0x4B0, b))
        # 無関係な ID 0x201: それらしい RPM を別波形で
        rpm = 800 + 3000 * ((t * 0.7) % 3.0) / 3.0
        can_rows.append((t + lag, 0x201, int(rpm).to_bytes(2, "big") + b"\x00\x00\x00\x00\x00\x00"))
        t += 0.02  # 50Hz

    ref_rows = []
    t = 0.0
    while t < 60.0:
        ref_rows.append((t, _tri(t)))
        t += 1.0

    # CSV 文字列にして通常の読み込み経路を通す
    can_csv = io.StringIO()
    w = csv.writer(can_csv)
    w.writerow(["host_iso", "t_us", "can_id", "ext", "rtr", "dlc", "data_hex"])
    for t_s, cid, data in can_rows:
        w.writerow(["", int(t_s * 1_000_000), f"0x{cid:X}", 0, 0, len(data), data.hex().upper()])
    ref_csv = io.StringIO()
    w = csv.writer(ref_csv)
    w.writerow(["t", "value"])
    for t_s, v in ref_rows:
        w.writerow([f"{t_s:.3f}", f"{v:.4f}"])

    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp(prefix="cancorr_st_"))
    (tmp / "can.csv").write_text(can_csv.getvalue(), encoding="utf-8")
    (tmp / "ref.csv").write_text(ref_csv.getvalue(), encoding="utf-8")

    ref = load_ref(str(tmp / "ref.csv"), "s")

    ok = True

    def check(cond, msg):
        nonlocal ok
        if not cond:
            ok = False
        print(f"  [{'OK  ' if cond else 'FAIL'}] {msg}")

    # 1) time-offset を知らずに素で回すと相関は低いはず
    by_id0 = load_can(str(tmp / "can.csv"), time_offset_s=0.0)
    res0 = scan(by_id0, ref, [], [1, 2], ["big", "little"], 10, 2.0)
    print("素の回帰（lag補正なし）上位:")
    print_table(res0, "speed_kmh", 3)
    print()

    # 2) auto-lag 探索
    best = None
    for cand_lag in frange("-2:2:0.1"):
        by_id = load_can(str(tmp / "can.csv"), time_offset_s=cand_lag)
        res = scan(by_id, ref, [], [1, 2], ["big", "little"], 10, 2.0)
        if best is None or best_r2(res) > best[1]:
            best = (cand_lag, best_r2(res), res)
    chosen_lag, chosen_r2, res = best
    print(f"auto-lag 選択: time_offset = {chosen_lag:+.2f}s  (best R^2 = {chosen_r2:.5f})")
    print_table(res, "speed_kmh", 5)
    print()

    top = res[0]
    check(top["can_id"] == 0x4B0 and top["offset"] == 0 and top["width"] == 2
          and top["endian"] == "big", "最良候補が 0x4B0 offset0 width2 big")
    check(top["r2"] > 0.99, f"最良候補の R^2 > 0.99 (got {top['r2']:.5f})")
    check(abs(top["slope"] - true_slope) / true_slope < 0.05,
          f"slope が真値 0.01 の±5%以内 (got {top['slope']:.5f})")
    check(abs(chosen_lag - (-lag)) < 0.2,
          f"選択された time_offset が真の -{lag}s 付近 (got {chosen_lag:+.2f})")
    check(best_r2(res0) < top["r2"],
          f"lag補正で R^2 が改善 ({best_r2(res0):.3f} -> {top['r2']:.3f})")

    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ---- main -----------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="既知値と候補バイト列の相関検証 (2-4-5)")
    p.add_argument("--can", help="2-4-2形式のキャプチャCSV")
    p.add_argument("--ref", help="基準値の時系列CSV (先頭2列 or t,value)")
    p.add_argument("--ref-name", default="ref", help="基準値の名前（表示用、例: speed_kmh）")
    p.add_argument("--ref-time-unit", choices=["s", "ms", "us"], default="s")
    p.add_argument("--candidate-id", action="append", default=[],
                   help="対象CAN ID（16進、例 0x4B0）。省略時は全ID")
    p.add_argument("--widths", default="1,2", help="試すバイト幅（例: 1,2）")
    p.add_argument("--endian", choices=["big", "little", "both"], default="both")
    p.add_argument("--time-offset", type=float, default=0.0,
                   help="CAN側時刻に加える秒数（基準値の時計へ合わせる）")
    p.add_argument("--auto-lag", help="time-offsetの粗探索 lo:hi:step（秒、例 -2:2:0.1）")
    p.add_argument("--max-hold", type=float, default=2.0,
                   help="ゼロ次ホールドで許容する最大保持秒数")
    p.add_argument("--min-samples", type=int, default=10)
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--json", action="store_true")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()

    if args.selftest:
        sys.exit(run_selftest())
    if not args.can or not args.ref:
        p.error("--can と --ref が必要です（または --selftest）")

    widths = [int(x) for x in args.widths.split(",")]
    endians = ["big", "little"] if args.endian == "both" else [args.endian]
    cand = [int(x, 16) for x in args.candidate_id]
    ref = load_ref(args.ref, args.ref_time_unit)
    if len(ref) < args.min_samples:
        p.error(f"基準値のサンプルが少なすぎます ({len(ref)}本)")

    if args.auto_lag:
        best = None
        for lag in frange(args.auto_lag):
            by_id = load_can(args.can, time_offset_s=lag)
            res = scan(by_id, ref, cand, widths, endians, args.min_samples, args.max_hold)
            if best is None or best_r2(res) > best[1]:
                best = (lag, best_r2(res), res)
        lag, _r2, results = best
        print(f"[*] auto-lag 選択: --time-offset {lag:+.3f}  (best R^2={_r2:.5f})")
    else:
        by_id = load_can(args.can, time_offset_s=args.time_offset)
        results = scan(by_id, ref, cand, widths, endians, args.min_samples, args.max_hold)

    print(f"=== correlate: can={args.can}  ref={args.ref} ({args.ref_name}) ===")
    if not results:
        print("  相関を評価できる候補がありませんでした")
    else:
        print_table(results, args.ref_name, args.top)
    if args.json:
        import json
        print(json.dumps([{**r, "can_id": f"0x{r['can_id']:03X}"} for r in results[:args.top]],
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
