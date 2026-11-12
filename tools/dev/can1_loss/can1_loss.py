"""車載CAN（CAN1）の取りこぼしを、読むだけで数える（本体の設定・ファームは何も変えない）。

調べた結果と直し方の案: lintaroh_share_20261104_can1.md

数え方は2つ。
  1. NCECの0x211のbyte7は1フレームごとに+1するカウンタ（ncec_can_spec.md）。飛んだ数＝取りこぼし（正確）
  2. 周期が一定のIDごとに、間隔が周期の1.5倍を超えたところを数える（全IDの見積もり）
本体ではさらに、STM32の can_counts・can_overflow の増え方と、eMMCのCAN生ログの行数を比べる。

  python can1_loss.py                     # 本体（ssh unoq）で60秒はかる
  python can1_loss.py --seconds 180
  python can1_loss.py --dir ../../../drive_logs/20261024   # PCに回収したCAN生ログ（*.can.jsonl）を数える
"""
import argparse
import collections
import glob
import json
import os
import statistics
import subprocess
import sys
import time


def read_rows(path, tail_bytes=None):
    """CAN生ログの行を (mcu_ms, channel, id, data) で返す。eMMC（配列）とSDの復元（辞書）の両方を読む。"""
    with open(path, "rb") as f:
        if tail_bytes:
            f.seek(max(0, os.path.getsize(path) - tail_bytes))
        lines = f.read().decode(errors="replace").splitlines()[1 if tail_bytes else 0:]
    rows = []
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append((r["mcu_ms"], r["channel"], r["id"], r["data"]))
        else:
            rows.append((r[0], r[1], r[2], r[5]))
    return rows


def counter_steps(rows):
    """0x211のbyte7（0〜255で一周）の飛び。2〜20は欠け、0は同じ行の重複、21以上は記録の途切れとして別に数える。"""
    vals = [int(r[3][14:16], 16) for r in rows if r[1] == 1 and r[2] == 0x211 and len(r[3]) >= 16]
    return len(vals), collections.Counter((b - a) % 256 for a, b in zip(vals, vals[1:]))


def gap_loss(rows):
    """周期が一定のIDごとに (件数, 周期ms, 抜けた数の見積もり)。周期が揃わないIDは数えない。"""
    byid = collections.defaultdict(list)
    for r in rows:
        if r[1] == 1:
            byid[r[2]].append(r[0])
    out = {}
    for cid, ts in sorted(byid.items()):
        if len(ts) < 20:
            continue
        d = [b - a for a, b in zip(ts, ts[1:])]
        per = statistics.median(d)
        if per <= 0 or sum(1 for x in d if 0.5 * per <= x <= 1.5 * per) < 0.8 * len(d):
            continue
        out[cid] = (len(ts), per, sum(round(x / per) - 1 for x in d if 1.5 * per < x < 20 * per))
    return out


def report(rowsets):
    """ファイル（または測った区間）ごとに数えて足す。つなぎ目の時刻の飛びは欠けに数えない。"""
    got = ch1 = 0
    span = 0.0
    steps = collections.Counter()
    per_id = collections.defaultdict(lambda: [0, 0.0, 0])
    for rows in rowsets:
        c1 = [r for r in rows if r[1] == 1]
        if len(c1) < 200:
            continue
        ch1 += len(c1)
        span += (c1[-1][0] - c1[0][0]) / 1000
        n, s = counter_steps(rows)
        got += n
        steps.update(s)
        for cid, (cnt, per, miss) in gap_loss(rows).items():
            per_id[cid][0] += cnt
            per_id[cid][1] = per
            per_id[cid][2] += miss
    if ch1 < 1000 or not span:
        print("CAN1のフレームが少なすぎます（%d件）" % ch1)
        return
    if got:
        lost = sum((k - 1) * n for k, n in steps.items() if 2 <= k <= 20)
        other = {k: n for k, n in sorted(steps.items()) if k == 0 or k > 20}
        print("0x211のカウンタ: 受信 %d / 欠け %d（%.3f%%） 飛び+2〜+20の内訳 %s%s" % (
            got, lost, 100 * lost / (got + lost), {k: n for k, n in sorted(steps.items()) if 2 <= k <= 20},
            "（重複0・途切れ21以上: %s）" % other if other else ""))
    total = sum(v[2] for v in per_id.values())
    print("全IDの見積もり: %.0f秒 CAN1 %.1f件/秒、欠け %d件（%.2f%%）" % (span, ch1 / span, total, 100 * total / (ch1 + total)))
    print("  ID     件数   周期ms  欠け")
    for cid, (n, per, miss) in sorted(per_id.items()):
        print("  0x%03x %7d %7.1f %5d（%.1f%%）" % (cid, n, per, miss, 100 * miss / (n + miss)))


def on_device(seconds):
    """本体の中で動く部分。/api/status を前後で読み、その間のeMMCのCAN生ログを数える。"""
    import urllib.request

    def hw():
        with urllib.request.urlopen("http://127.0.0.1:8080/api/status", timeout=10) as r:
            return json.load(r)["hardware"]

    s0 = hw()
    time.sleep(seconds)
    s1 = hw()
    time.sleep(6)  # EcoCaptureがその間の行を書き終えるのを待つ
    path = sorted(glob.glob(os.path.expanduser("~/ecocapture-v2-data/logs/*.can.jsonl")), key=os.path.getmtime)[-1]
    rows = [r for r in read_rows(path, 60 * 800 * (seconds + 30)) if s0["mcu_ms"] <= r[0] <= s1["mcu_ms"]]
    counts = [b - a for a, b in zip(s0["can_counts"], s1["can_counts"])]
    over = [b - a for a, b in zip(s0["can_overflow"], s1["can_overflow"])]
    print("%s の %.0f秒" % (os.path.basename(path), (s1["mcu_ms"] - s0["mcu_ms"]) / 1000))
    print("STM32: can_counts +%s / can_overflow +%s" % (counts, over))
    print("eMMCの行: CAN1 %d / CAN2 %d（can_countsと同じなら、Linuxへ渡す枠では落ちていない）"
          % (sum(1 for r in rows if r[1] == 1), sum(1 for r in rows if r[1] == 2)))
    report([rows])


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--on-device":
        on_device(int(sys.argv[2]))
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=int, default=60, help="本体ではかる長さ（秒）")
    ap.add_argument("--dir", help="PCに回収したCAN生ログのフォルダー（*.can.jsonl を下の階層まで探す）")
    ap.add_argument("--host", default="unoq", help="sshの接続先（既定 unoq）")
    args = ap.parse_args()
    if args.dir:
        files = sorted(glob.glob(os.path.join(args.dir, "**", "*.can.jsonl"), recursive=True))
        if not files:
            sys.exit("*.can.jsonl が見つかりません: " + args.dir)
        print("%d本のファイル" % len(files))
        report(read_rows(p) for p in files)
        return
    with open(__file__, "rb") as f:
        code = f.read()
    cmd = ["ssh", "-o", "ConnectTimeout=10", args.host, "python3", "-I", "-", "--on-device", str(args.seconds)]
    sys.exit(subprocess.run(cmd, input=code).returncode)


if __name__ == "__main__":
    main()
