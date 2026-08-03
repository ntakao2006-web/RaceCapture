"""
OBD2等で並行取得できる既知の値（車速・回転数等の時系列）と、生CANログ中の
候補バイト列（`can_raw_logger.py`が記録した特定CAN IDのバイト値）との相関を
線形回帰で検証するツール。
task_phase2_breakdown.md 2-4-5。

例えば「ID `4B0`のこのバイトはホイールスピードではないか」という仮説を、
OBD2 PID `010D`(車速)の実測値と時系列で突き合わせ、相関係数・回帰式を
算出することで裏付ける（または否定する）ために使う。

想定する入力:
    --ref: 基準となる既知値の時系列CSV。ヘッダー行 `timestamp,value` を持ち、
           timestampはUNIXエポック秒（float）。例えばELM327での`010D`
           ポーリング結果を `time.time(), 速度kph` の形で記録したもの。
    --can-log: `can_raw_logger.py`が出力したCSV/JSON Linesログ。
    --can-id: 相関を調べたいCAN ID（16進数）。

タイムスタンプの整合について：生CANログの`ts_us`はESP32起動からの相対時刻
（マイクロ秒）であり、`--ref`側のUNIXエポック秒とは基準点が異なる。この
ツールでは両ログをほぼ同時にリアルタイム収録した前提で、生CANログ側の
受信時刻`host_ts`（PCの壁時計、UTC ISO8601）をUNIXエポック秒に変換して
時刻合わせに使う（シリアル遅延数msは通常の車速・回転数程度の変化速度
なら無視できる想定。より高速に変化する信号では別途対応が必要）。

候補バイト列は、指定CAN IDのDLC分から自動生成する：
    - 各バイト単独（符号なし8bit）
    - 隣接2バイトの組み合わせ（Big-Endian / Little-Endianそれぞれ）
候補ごとに基準時系列へ線形補間し、ピアソン相関係数・線形回帰（傾き・
切片）・決定係数R^2を算出し、|相関係数|の大きい順に上位N件を表示する。

実車・実CANハードウェア（2-1）がまだ無く、実際のOBD2ログ・生CANログでの
検証はまだできていない。合成データでのロジック検証はtask_phase2_breakdown.md
2-4-5参照。

使い方:
    python can_correlation_check.py --ref ref_speed.csv --can-log raw_can_log.csv --can-id 4B0 --top 5
"""
import argparse
import csv
import json
from datetime import datetime, timezone


def load_ref_series(path):
    """--ref CSV(timestamp,value)を読み込み、(timestamp, value)のリスト（時刻昇順）を返す"""
    series = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            series.append((float(row["timestamp"]), float(row["value"])))
    series.sort(key=lambda x: x[0])
    return series


def _iso_to_epoch(iso_str):
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).timestamp()


def load_can_series(path, can_id):
    """can_raw_logger.pyの出力から指定can_idのフレームだけを抽出し、
    (host_ts_epoch, data_bytes)のリスト（時刻昇順）を返す"""
    can_id = can_id.upper()
    frames = []
    if path.endswith(".jsonl") or path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec["can_id"].upper() != can_id:
                    continue
                data = tuple(int(b, 16) for b in rec["data_hex"].split()) if rec.get("data_hex") else tuple()
                frames.append((_iso_to_epoch(rec["host_ts"]), data))
    else:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["can_id"].upper() != can_id:
                    continue
                data_hex = row.get("data_hex", "")
                data = tuple(int(b, 16) for b in data_hex.split()) if data_hex else tuple()
                frames.append((_iso_to_epoch(row["host_ts"]), data))
    frames.sort(key=lambda x: x[0])
    return frames


def generate_candidates(dlc):
    """DLCから候補の(名前, byte_indicesと変換方法)を生成する"""
    candidates = []
    for i in range(dlc):
        candidates.append((f"byte{i}", (i,), "u8"))
    for i in range(dlc - 1):
        candidates.append((f"byte{i}-{i+1}_BE", (i, i + 1), "u16be"))
        candidates.append((f"byte{i}-{i+1}_LE", (i, i + 1), "u16le"))
    return candidates


def extract_value(data, indices, mode):
    if mode == "u8":
        return data[indices[0]]
    b0, b1 = data[indices[0]], data[indices[1]]
    if mode == "u16be":
        return (b0 << 8) | b1
    return (b1 << 8) | b0  # u16le


def linear_interp(x_target, xs, ys):
    """xs(昇順)・ys上で、x_target時点の値を線形補間する。範囲外はNoneを返す（外挿しない）"""
    if not xs or x_target < xs[0] or x_target > xs[-1]:
        return None
    lo, hi = 0, len(xs) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if xs[mid] < x_target:
            lo = mid + 1
        else:
            hi = mid
    if xs[lo] == x_target or lo == 0:
        return ys[lo]
    x0, x1 = xs[lo - 1], xs[lo]
    y0, y1 = ys[lo - 1], ys[lo]
    if x1 == x0:
        return y0
    t = (x_target - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


def pearson_and_regression(xs, ys):
    """xs(候補バイト値)とys(基準値)からピアソン相関係数r・回帰の傾き/切片・R^2を返す。
    サンプル不足や分散ゼロの場合はNoneを返す"""
    n = len(xs)
    if n < 3:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    cov_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    r = cov_xy / (var_x ** 0.5 * var_y ** 0.5)
    slope = cov_xy / var_x
    intercept = mean_y - slope * mean_x
    r2 = r * r
    return {"n": n, "r": r, "slope": slope, "intercept": intercept, "r2": r2}


def evaluate_candidates(ref_series, can_frames, dlc):
    """基準時系列とCANフレーム列から、候補ごとの相関結果をr2降順で返す"""
    ref_xs = [t for t, _ in ref_series]
    ref_ys = [v for _, v in ref_series]

    results = []
    for name, indices, mode in generate_candidates(dlc):
        cand_xs = []
        cand_ys = []
        for ts, data in can_frames:
            ref_value = linear_interp(ts, ref_xs, ref_ys)
            if ref_value is None:
                continue
            cand_xs.append(extract_value(data, indices, mode))
            cand_ys.append(ref_value)
        stats = pearson_and_regression(cand_xs, cand_ys)
        if stats is None:
            continue
        stats["candidate"] = name
        results.append(stats)

    results.sort(key=lambda s: s["r2"], reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", required=True, help="基準値の時系列CSV（timestamp,value）")
    parser.add_argument("--can-log", required=True, help="can_raw_logger.pyの出力ログ")
    parser.add_argument("--can-id", required=True, help="相関を調べたいCAN ID（16進数、例: 4B0）")
    parser.add_argument("--top", type=int, default=5, help="表示する上位候補数（既定: 5）")
    args = parser.parse_args()

    ref_series = load_ref_series(args.ref)
    can_frames = load_can_series(args.can_log, args.can_id)
    if not can_frames:
        print(f"[!] CAN ID {args.can_id} のフレームがログ中に見つかりませんでした")
        return
    dlc = len(can_frames[0][1])

    results = evaluate_candidates(ref_series, can_frames, dlc)
    if not results:
        print("[!] 基準値の時間範囲とCANログの時刻が重ならないため、比較できるサンプルがありません")
        return

    print(f"CAN ID {args.can_id.upper()} (DLC={dlc}) の候補上位{min(args.top, len(results))}件:")
    for stats in results[: args.top]:
        print(
            f"  {stats['candidate']}: r={stats['r']:.4f} r2={stats['r2']:.4f} "
            f"value ≈ {stats['slope']:.4f} * byte + {stats['intercept']:.4f}  (n={stats['n']})"
        )


if __name__ == "__main__":
    main()
