#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OBD2応答(0x7E8..0x7EF)の抽出・物理値デコードツール (2-2-1 / 2-4-5)

`firmware/can_obd_logger` で採取し `can_capture_logger.py` で記録したキャプチャCSVから、
OBD2 mode 01 の肯定応答フレームだけを拾い出し、SAE標準の変換式で物理値へ直して
PIDごとの時系列CSV(`t_us,value`)を書き出す。

出力はそのまま `can_correlate.py --ref` に食わせられる形式になっている。

    # 1) 実車で採取
    python can_capture_logger.py --port COM5 --out run1
    # 2) OBD2応答を基準値の時系列へ変換
    python can_obd_extract.py --can run1.csv --out run1_ref
    # 3) 生CAN候補バイトとの相関を検証
    python can_correlate.py --can run1.csv --ref run1_ref_0D_speed.csv \
                            --ref-name speed_kmh --ref-time-unit us

★ --time-offset / --auto-lag は不要 ★
   生CANフレームもOBD2応答も、同じ基板の同じ esp_timer_get_time() で
   タイムスタンプされているため、両者の時間軸は最初から一致している。
   (ELM327を併用する構成では PC時計 と ESP32起動相対時刻 の原点がズレるため
    ラグ推定が必要だった。can_obd_logger はその問題自体を消すために作られている)

依存: 標準ライブラリのみ (can_diff.py / can_correlate.py と同じ方針)
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict

OBD_RESP_LO = 0x7E8
OBD_RESP_HI = 0x7EF


# ---------------------------------------------------------------------------
# PIDデコード表
#   nbytes: 応答データ部の必要バイト数
#   fn    : データ部(bytes)を物理値(float)へ変換する関数
#   SAE J1979 の標準式。NCロードスターの対応PIDは OBD2_SURVEY.md「対応PID一覧」参照。
# ---------------------------------------------------------------------------
def _a(d):        return d[0]
def _a_40(d):     return d[0] - 40
def _pct(d):      return d[0] * 100.0 / 255.0
def _u16(d):      return (d[0] << 8) | d[1]

PID_DECODERS = {
    0x04: ("load",      "%",     1, _pct),
    0x05: ("coolant",   "degC",  1, _a_40),
    0x06: ("stft1",     "%",     1, lambda d: d[0] / 1.28 - 100.0),
    0x07: ("ltft1",     "%",     1, lambda d: d[0] / 1.28 - 100.0),
    0x0B: ("map",       "kPa",   1, _a),
    0x0C: ("rpm",       "rpm",   2, lambda d: _u16(d) / 4.0),
    0x0D: ("speed",     "km/h",  1, _a),
    0x0E: ("timing",    "deg",   1, lambda d: d[0] / 2.0 - 64.0),
    0x0F: ("iat",       "degC",  1, _a_40),
    0x10: ("maf",       "g/s",   2, lambda d: _u16(d) / 100.0),
    0x11: ("throttle",  "%",     1, _pct),
    0x1F: ("runtime",   "s",     2, _u16),
    0x21: ("mil_dist",  "km",    2, _u16),
    0x2C: ("egr_cmd",   "%",     1, _pct),
    0x2E: ("evap_cmd",  "%",     1, _pct),
    0x2F: ("fuel_lvl",  "%",     1, _pct),
    0x31: ("dist_clr",  "km",    2, _u16),
    0x33: ("baro",      "kPa",   1, _a),
    0x42: ("batt",      "V",     2, lambda d: _u16(d) / 1000.0),
    0x43: ("abs_load",  "%",     2, lambda d: _u16(d) * 100.0 / 255.0),
    0x45: ("rel_thr",   "%",     1, _pct),
    0x46: ("ambient",   "degC",  1, _a_40),
    0x47: ("thr_b",     "%",     1, _pct),
    0x49: ("accel_d",   "%",     1, _pct),
    0x4A: ("accel_e",   "%",     1, _pct),
    0x4C: ("thr_cmd",   "%",     1, _pct),
    # 2-0-6 のレクサスUX(2022年式)実測で応答が確認できたPID（OBD2_SURVEY.md）
    0x34: ("o2_wr_lam",  "-",    2, lambda d: _u16(d) / 32768.0),   # 広域O2の当量比(先頭2バイト)
    0x44: ("equiv_ratio", "-",   2, lambda d: _u16(d) / 32768.0),   # 燃料/空気当量比の指令値
    0x5C: ("oil_temp",  "degC",  1, _a_40),                         # エンジン油温
}


def decode_response(data: bytes):
    """OBD2応答フレームのデータ部から (pid, name, unit, value) を返す。対象外なら None。

    肯定応答の並び: [0]=長さ(PCI) [1]=0x41 [2]=PID [3..]=データ
    """
    if len(data) < 3:
        return None
    if data[1] != 0x41:          # 0x41 = 0x40 + mode 01。否定応答(0x7F)等はここで弾く
        return None
    pid = data[2]
    dec = PID_DECODERS.get(pid)
    if dec is None:
        return None
    name, unit, nbytes, fn = dec

    # PCIの長さフィールドから有効データ長を求める(mode/PIDの2バイトを除く)
    avail = min(len(data) - 3, max(0, data[0] - 2))
    if avail < nbytes:
        return None
    try:
        value = float(fn(data[3:3 + nbytes]))
    except (IndexError, ZeroDivisionError, ValueError):
        return None
    return pid, name, unit, value


# ---------------------------------------------------------------------------
def parse_capture(path):
    """2-4-2形式のキャプチャCSVを読み、OBD2応答を (t_us, pid, name, unit, value) で列挙する。"""
    rows = []
    stats = {"total": 0, "obd_frames": 0, "decoded": 0, "undecoded_pids": defaultdict(int),
             "negative": 0, "bad_rows": 0}
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            stats["total"] += 1
            try:
                t_us = int(r["t_us"])
                can_id = int(str(r["can_id"]), 16) if not str(r["can_id"]).lower().startswith("0x") \
                    else int(str(r["can_id"]), 16)
                data = bytes.fromhex(r.get("data_hex") or "")
            except (KeyError, ValueError, TypeError):
                stats["bad_rows"] += 1
                continue
            if not (OBD_RESP_LO <= can_id <= OBD_RESP_HI):
                continue
            stats["obd_frames"] += 1
            if len(data) >= 3 and data[1] == 0x7F:
                stats["negative"] += 1
                continue
            got = decode_response(data)
            if got is None:
                if len(data) >= 3 and data[1] == 0x41:
                    stats["undecoded_pids"][data[2]] += 1
                continue
            pid, name, unit, value = got
            rows.append((t_us, pid, name, unit, value))
            stats["decoded"] += 1
    rows.sort(key=lambda x: x[0])
    return rows, stats


def write_series(rows, out_prefix, only_pids=None):
    """PIDごとに `<prefix>_<PID>_<name>.csv` (t_us,value) を書き出す。"""
    by_pid = defaultdict(list)
    for t_us, pid, name, unit, value in rows:
        if only_pids and pid not in only_pids:
            continue
        by_pid[(pid, name, unit)].append((t_us, value))

    written = []
    out_dir = os.path.dirname(os.path.abspath(out_prefix))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    for (pid, name, unit), series in sorted(by_pid.items()):
        path = "%s_%02X_%s.csv" % (out_prefix, pid, name)
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t_us", "value"])       # can_correlate.py --ref がそのまま読める形式
            for t_us, value in series:
                w.writerow([t_us, "%.6g" % value])
        written.append((path, pid, name, unit, len(series),
                        min(v for _, v in series), max(v for _, v in series)))
    return written


def summarize(rows, stats, written):
    out = []
    out.append("==== OBD2 extract summary ====")
    out.append("capture rows        : %d" % stats["total"])
    out.append("OBD2 response frames: %d  (0x%03X-0x%03X)" % (stats["obd_frames"], OBD_RESP_LO, OBD_RESP_HI))
    out.append("decoded samples     : %d" % stats["decoded"])
    out.append("negative responses  : %d  (0x7F = そのPIDは非対応/一時拒否)" % stats["negative"])
    if stats["bad_rows"]:
        out.append("unparsable rows     : %d" % stats["bad_rows"])
    if stats["undecoded_pids"]:
        items = ", ".join("0x%02X(x%d)" % (p, c) for p, c in sorted(stats["undecoded_pids"].items()))
        out.append("PIDs without decoder: %s" % items)
    if written:
        out.append("")
        out.append("written series:")
        for path, pid, name, unit, n, vmin, vmax in written:
            out.append("  %-38s PID 0x%02X %-9s n=%-6d range=%.6g..%.6g %s"
                       % (os.path.basename(path), pid, name, n, vmin, vmax, unit))
    else:
        out.append("")
        out.append("!! 出力なし。OBD2応答が1件も取れていない。")
        out.append("   確認: can_obd_logger(NORMAL)で採取したか / '# obd ... resp=' が増えていたか /")
        out.append("        OBD2コネクタが刺さっていたか / イグニッションONだったか")
    return "\n".join(out)


# ---------------------------------------------------------------------------
SELFTEST_CSV = """host_iso,t_us,can_id,ext,rtr,dlc,data_hex
2026-01-01T00:00:00+00:00,1000000,0x7E0,0,0,8,02010D5555555555
2026-01-01T00:00:00+00:00,1005000,0x7E8,0,0,8,41 0D 34 00 00 00 00
2026-01-01T00:00:00+00:00,1100000,0x7E8,0,0,8,0341 0D3400000000
2026-01-01T00:00:00+00:00,1200000,0x7E8,0,0,8,04410C1F4000000000
2026-01-01T00:00:00+00:00,1300000,0x7E8,0,0,8,0341055C00000000
2026-01-01T00:00:00+00:00,1400000,0x7E8,0,0,8,037F01120000000000
2026-01-01T00:00:00+00:00,1500000,0x7E8,0,0,8,0341992200000000
2026-01-01T00:00:00+00:00,1600000,0x201,0,0,8,0011223344556677
2026-01-01T00:00:00+00:00,1700000,0x7E8,0,0,8,0341116600000000
2026-01-01T00:00:00+00:00,1800000,0x7E9,0,0,8,03410D2800000000
"""


def selftest():
    import tempfile
    ok = True
    results = []

    def check(cond, label):
        nonlocal ok
        results.append(("PASS" if cond else "FAIL", label))
        if not cond:
            ok = False

    # data_hex に空白が混じる行は bytes.fromhex が拾えないので、事前に整形されている前提。
    # ここでは can_capture_logger.py の実出力(空白なし)に合わせたデータで検証する。
    clean = SELFTEST_CSV.replace("41 0D 34 00 00 00 00", "03410D3400000000") \
                        .replace("0341 0D3400000000", "03410D3400000000")

    with tempfile.TemporaryDirectory() as td:
        cap = os.path.join(td, "cap.csv")
        with open(cap, "w", encoding="utf-8", newline="") as f:
            f.write(clean)

        rows, stats = parse_capture(cap)

        check(stats["obd_frames"] == 8, "0x7E8/0x7E9 応答を8件検出 (got %d)" % stats["obd_frames"])
        check(stats["negative"] == 1, "否定応答(0x7F)を1件計上 (got %d)" % stats["negative"])
        check(0x99 in stats["undecoded_pids"], "デコーダ未定義PID 0x99 を記録")

        # 同じPIDが複数サンプルあるので「最初の1件」で比較する(辞書化すると最後の値になる)
        vals = {}
        for _t, pid, name, _u, v in rows:
            vals.setdefault((pid, name), v)
        check(vals.get((0x0D, "speed")) == 52.0, "PID 0x0D 車速 0x34=52 km/h (got %r)" % vals.get((0x0D, "speed")))
        check(abs(vals.get((0x0C, "rpm"), 0) - 2000.0) < 1e-6,
              "PID 0x0C 回転数 0x1F40/4=2000 rpm (got %r)" % vals.get((0x0C, "rpm")))
        check(vals.get((0x05, "coolant")) == 52.0, "PID 0x05 水温 0x5C-40=52 degC (got %r)" % vals.get((0x05, "coolant")))
        check(decode_response(bytes([0x03, 0x41, 0x5C, 0x7B])) == (0x5C, "oil_temp", "degC", 83.0),
              "PID 0x5C 油温 0x7B-40=83 degC (got %r)" % (decode_response(bytes([0x03, 0x41, 0x5C, 0x7B])),))
        check(abs(vals.get((0x11, "throttle"), 0) - (0x66 * 100.0 / 255.0)) < 1e-6, "PID 0x11 スロットル")

        # 0x7E9 (ECU#2) も応答レンジとして受理されること
        speeds = [v for _t, pid, _n, _u, v in rows if pid == 0x0D]
        check(len(speeds) == 3, "0x7E8x2 + 0x7E9x1 の車速3サンプル (got %d)" % len(speeds))

        # 生CANフレーム(0x201)は混入しないこと
        check(all(pid in PID_DECODERS for _t, pid, _n, _u, _v in rows), "生CANフレームを取り込んでいない")

        # 時刻昇順
        ts = [r[0] for r in rows]
        check(ts == sorted(ts), "出力が時刻昇順")

        out_prefix = os.path.join(td, "ref")
        written = write_series(rows, out_prefix)
        check(len(written) == 4, "PIDごとに4ファイル出力 (got %d)" % len(written))

        spd_path = "%s_0D_speed.csv" % out_prefix
        check(os.path.exists(spd_path), "車速ファイルが生成される")
        with open(spd_path, encoding="utf-8") as f:
            head = f.readline().strip()
            first = f.readline().strip()
        check(head == "t_us,value", "ヘッダが can_correlate.py --ref 互換 't_us,value' (got %r)" % head)
        check(first.startswith("1005000,"), "先頭行が最初の応答時刻 (got %r)" % first)

    print("==== can_obd_extract.py selftest ====")
    for status, label in results:
        print("  [%s] %s" % (status, label))
    print("  => %s (%d/%d)" % ("ALL PASS" if ok else "FAILED",
                               sum(1 for s, _ in results if s == "PASS"), len(results)))
    return 0 if ok else 1


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="OBD2応答の抽出・物理値デコード (2-2-1 / 2-4-5)")
    ap.add_argument("--can", help="2-4-2形式のキャプチャCSV (can_capture_logger.py の出力)")
    ap.add_argument("--out", help="出力接頭辞 (例: run1_ref → run1_ref_0D_speed.csv)")
    ap.add_argument("--pid", help="抽出するPIDを絞る (16進カンマ区切り、例: 0C,0D)")
    ap.add_argument("--list", action="store_true", help="含まれるPIDを一覧するだけで書き出さない")
    ap.add_argument("--json", action="store_true", help="サマリをJSONで出力")
    ap.add_argument("--selftest", action="store_true", help="合成データで自己テスト")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.can:
        ap.error("--can か --selftest が必要")

    only = None
    if args.pid:
        only = set()
        for tok in args.pid.split(","):
            tok = tok.strip()
            if tok:
                only.add(int(tok, 16))

    rows, stats = parse_capture(args.can)

    if args.list:
        seen = defaultdict(int)
        for _t, pid, name, unit, _v in rows:
            seen[(pid, name, unit)] += 1
        print("==== PIDs in %s ====" % args.can)
        for (pid, name, unit), n in sorted(seen.items()):
            print("  0x%02X %-9s %-5s n=%d" % (pid, name, unit, n))
        if not seen:
            print("  (OBD2応答なし)")
        return 0

    if not args.out:
        ap.error("--out が必要 (--list で一覧のみ確認可)")

    written = write_series(rows, args.out, only)

    if args.json:
        print(json.dumps({
            "capture_rows": stats["total"],
            "obd_frames": stats["obd_frames"],
            "decoded": stats["decoded"],
            "negative": stats["negative"],
            "undecoded_pids": {"0x%02X" % p: c for p, c in stats["undecoded_pids"].items()},
            "series": [{"path": p, "pid": pid, "name": n, "unit": u,
                        "samples": cnt, "min": mn, "max": mx}
                       for p, pid, n, u, cnt, mn, mx in written],
        }, ensure_ascii=False, indent=2))
    else:
        print(summarize(rows, stats, written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
