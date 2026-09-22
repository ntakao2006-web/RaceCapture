#!/usr/bin/env python3
"""NCEC: NOPRO メカフィーリングスロットルマップの同定.

`ncec_sweep`（エンジン停止・IG ON でペダル全域を掃引）の OBD 基準値から、
アクセルペダル開度 → 実スロットル開度の伝達特性を求める。

    python ncec_throttle_map.py

入力: ncec_sweep_ref_49_accel_d.csv  (0x49 アクセルペダル開度)
      ncec_sweep_ref_11_throttle.csv (0x11 実スロットル開度)
"""
import bisect
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
JOIN_TOL_US = 120_000  # 9.28 Hz なので半周期 54ms より広く、1周期より狭く取る


def load(name):
    with open(os.path.join(HERE, name), newline="") as f:
        return sorted((int(r["t_us"]), float(r["value"])) for r in csv.DictReader(f))


def join(pedal, thr):
    """ペダル各点に最近傍のスロットル値を突き合わせる。"""
    ts = [t for t, _ in thr]
    out = []
    for t_us, pv in pedal:
        i = bisect.bisect_left(ts, t_us)
        j = min((k for k in (i - 1, i) if 0 <= k < len(ts)),
                key=lambda k: abs(ts[k] - t_us))
        if abs(ts[j] - t_us) <= JOIN_TOL_US:
            out.append((t_us, pv, thr[j][1]))
    return out


def linfit(xy):
    n = len(xy)
    sx = sum(x for x, _ in xy)
    sy = sum(y for _, y in xy)
    a = (n * sum(x * y for x, y in xy) - sx * sy) / (n * sum(x * x for x, _ in xy) - sx * sx)
    b = (sy - a * sx) / n
    ybar = sy / n
    ss_res = sum((y - (a * x + b)) ** 2 for x, y in xy)
    ss_tot = sum((y - ybar) ** 2 for _, y in xy)
    return a, b, 1 - ss_res / ss_tot


def main():
    rec = join(load("ncec_sweep_ref_49_accel_d.csv"),
               load("ncec_sweep_ref_11_throttle.csv"))
    pmin, pmax = min(r[1] for r in rec), max(r[1] for r in rec)
    tmin, tmax = min(r[2] for r in rec), max(r[2] for r in rec)
    print(f"joined {len(rec)} points")
    print(f"  pedal    {pmin:6.2f} .. {pmax:6.2f} %  (span {pmax - pmin:.2f} pt)")
    print(f"  throttle {tmin:6.2f} .. {tmax:6.2f} %  (span {tmax - tmin:.2f} pt)")
    print(f"  生ポイント比で見た「見かけのゲイン」の下駄 = {(tmax - tmin) / (pmax - pmin):.3f}")

    # 実効ストロークを 0-100% に正規化してから比較する
    nrm = [((p - pmin) / (pmax - pmin) * 100, (t - tmin) / (tmax - tmin) * 100)
           for _, p, t in rec]

    a, b, r2 = linfit([(p, t) for p, t in nrm if 8 <= p <= 70])
    knee = (100 - b) / a
    resid = [abs(t - (a * p + b)) for p, t in nrm if 8 <= p <= 70]
    print(f"\n線形区間フィット (ペダル 8-70%): throttle = {a:.4f} * pedal {b:+.2f}")
    print(f"  R^2 = {r2:.5f}   平均残差 = {sum(resid) / len(resid):.2f} pt"
          f"   最大残差 = {max(resid):.2f} pt")
    print(f"  全開到達ペダル開度 = {knee:.1f} %")

    dead = [p for p, t in nrm if t <= 0.5]
    print(f"  不感帯: ペダル {max(dead):.1f}% までスロットル 0.5% 以下")

    print("\nペダル% → スロットル% (5%ビン)")
    bins = {}
    for p, t in nrm:
        bins.setdefault(min(int(p // 5), 19), []).append(t)
    for k in sorted(bins):
        v = bins[k]
        print(f"  {k * 5:3d}-{k * 5 + 5:3d}%   {sum(v) / len(v):6.2f}%   n={len(v)}")


if __name__ == "__main__":
    main()
