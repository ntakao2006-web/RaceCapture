"""
停車状態で決まった単一操作をON/OFFしながら記録した複数の生CANログを比較し、
操作前後で値が変化するCAN ID・バイト位置を自動検出するツール。
task_phase2_breakdown.md 2-4-3。

入力は `can_raw_logger.py`（2-4-2）が出力したログファイル（CSVまたはJSON
Lines）を、操作の状態（フェーズ）ごとに複数指定する。例えばウィンカーの
ON/OFF比較なら「消灯中」「点灯中」の2フェーズ、パワーウィンドウなら
「窓閉」「窓開」「窓閉(2回目)」のように3フェーズでもよい。

検出ルール（確信度の高い順）：
    1. あるCAN IDが特定フェーズにしか出現しない → フェーズ限定ID
    2. 同一CAN ID・同一DLCで、あるバイト位置の値の集合が2フェーズ間で
       重複しない（disjoint） → 最有力候補（フラグビット等の離散値向き）
    3. 値の集合は重複するが、最頻値（モード）がフェーズ間で異なる →
       弱い候補（アナログ値の緩やかな変化等も拾うため）

実車・実CANハードウェア（2-1）がまだ無いため、このツール自体はまだ実際の
車両ログでは検証できていない。合成データでのロジック検証は
task_phase2_breakdown.md 2-4-3参照。

使い方:
    python can_diff_detect.py --phase off=log_off.csv --phase on=log_on.csv --out diff_report.json
"""
import argparse
import csv
import json
from collections import Counter, defaultdict


def load_log(path):
    """can_raw_logger.py が出力したCSV/JSON Linesログを読み込み、
    can_id(大文字16進文字列) -> [data_bytes(tuple[int]), ...] の辞書を返す。"""
    frames = defaultdict(list)
    if path.endswith(".jsonl") or path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                can_id = rec["can_id"].upper()
                data_hex = rec.get("data_hex", "")
                data = tuple(int(b, 16) for b in data_hex.split()) if data_hex else tuple()
                frames[can_id].append(data)
    else:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                can_id = row["can_id"].upper()
                data_hex = row.get("data_hex", "")
                data = tuple(int(b, 16) for b in data_hex.split()) if data_hex else tuple()
                frames[can_id].append(data)
    return frames


def detect(phase_logs):
    """phase_logs: {phase_name: {can_id: [data_tuple, ...]}}
    戻り値: 確信度順にソートされた候補リスト（各要素はdict）"""
    all_ids = set()
    for log in phase_logs.values():
        all_ids.update(log.keys())

    phase_names = list(phase_logs.keys())
    findings = []

    for can_id in sorted(all_ids):
        presence = {p: (can_id in phase_logs[p] and len(phase_logs[p][can_id]) > 0) for p in phase_names}
        present_phases = [p for p, present in presence.items() if present]
        absent_phases = [p for p, present in presence.items() if not present]

        if present_phases and absent_phases:
            findings.append({
                "confidence": "high",
                "kind": "phase_exclusive_id",
                "can_id": can_id,
                "present_in": present_phases,
                "absent_in": absent_phases,
            })
            # フェーズ限定IDはバイト単位比較の対象外（そもそも比較できるフェーズが揃わない）
            continue

        # 全フェーズに出現するIDのみバイト単位で比較する
        per_phase_frames = {p: phase_logs[p][can_id] for p in phase_names}
        dlcs = {len(frames[0]) for frames in per_phase_frames.values() if frames}
        if len(dlcs) != 1:
            continue  # フェーズ間でDLCが揺れているIDは単純バイト比較の対象外
        dlc = next(iter(dlcs))

        for byte_idx in range(dlc):
            value_sets = {p: {frame[byte_idx] for frame in per_phase_frames[p]} for p in phase_names}
            # 2フェーズの組み合わせごとに重複判定する
            for i in range(len(phase_names)):
                for j in range(i + 1, len(phase_names)):
                    p1, p2 = phase_names[i], phase_names[j]
                    s1, s2 = value_sets[p1], value_sets[p2]
                    if not s1 or not s2:
                        continue
                    if s1.isdisjoint(s2):
                        findings.append({
                            "confidence": "high",
                            "kind": "disjoint_byte_values",
                            "can_id": can_id,
                            "byte_offset": byte_idx,
                            "phases": [p1, p2],
                            "values": {p1: sorted(s1), p2: sorted(s2)},
                        })
                    else:
                        mode1 = Counter(per_phase_frames[p1][k][byte_idx] for k in range(len(per_phase_frames[p1]))).most_common(1)[0][0]
                        mode2 = Counter(per_phase_frames[p2][k][byte_idx] for k in range(len(per_phase_frames[p2]))).most_common(1)[0][0]
                        if mode1 != mode2:
                            findings.append({
                                "confidence": "low",
                                "kind": "mode_shift",
                                "can_id": can_id,
                                "byte_offset": byte_idx,
                                "phases": [p1, p2],
                                "mode_values": {p1: mode1, p2: mode2},
                            })

    confidence_rank = {"high": 0, "low": 1}
    findings.sort(key=lambda f: (confidence_rank[f["confidence"]], f["can_id"], f.get("byte_offset", -1)))
    return findings


def format_report_text(findings):
    if not findings:
        return "候補は見つかりませんでした。"
    lines = []
    for f in findings:
        if f["kind"] == "phase_exclusive_id":
            lines.append(f"[{f['confidence']}] ID {f['can_id']}: {f['present_in']}のみ出現（{f['absent_in']}では未観測）")
        elif f["kind"] == "disjoint_byte_values":
            lines.append(
                f"[{f['confidence']}] ID {f['can_id']} byte{f['byte_offset']}: "
                f"{f['phases'][0]}={f['values'][f['phases'][0]]} と {f['phases'][1]}={f['values'][f['phases'][1]]} が重複なし"
            )
        else:
            lines.append(
                f"[{f['confidence']}] ID {f['can_id']} byte{f['byte_offset']}: "
                f"最頻値が {f['phases'][0]}={f['mode_values'][f['phases'][0]]} → {f['phases'][1]}={f['mode_values'][f['phases'][1]]} で変化"
            )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phase", action="append", required=True, metavar="NAME=PATH",
                        help="フェーズ名=ログファイルパス（2つ以上指定する）")
    parser.add_argument("--out", help="結果をJSONとしても書き出すファイルパス（省略可）")
    args = parser.parse_args()

    if len(args.phase) < 2:
        parser.error("--phase は2つ以上指定してください")

    phase_logs = {}
    for entry in args.phase:
        if "=" not in entry:
            parser.error(f"--phase は NAME=PATH 形式で指定してください: {entry!r}")
        name, path = entry.split("=", 1)
        phase_logs[name] = load_log(path)

    findings = detect(phase_logs)
    print(format_report_text(findings))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(findings, f, ensure_ascii=False, indent=2)
        print(f"\n[*] JSON形式でも保存: {args.out}")


if __name__ == "__main__":
    main()
