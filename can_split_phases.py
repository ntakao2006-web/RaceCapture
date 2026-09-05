#!/usr/bin/env python3
"""
can_capture_logger.py の `--phase-plan` で記録した長回しキャプチャを、
フェーズごとのCSVへ切り分けるツール。

無人（運転中）のキャプチャは1本の長いCSVになるが、解析は
「IG ON停車・受動」「アイドル・OBDポーリング」「走行」…といった区間ごとに
かけたい。`--phase-plan` を使うと status ログに

    2026-09-05T01:23:45+00:00\t# host: phase t=0.0s at=0s action=passive key=p label=ig_on

という区切り行が残るので、その host 時刻でフレームCSVを分割する。

使い方:
    # capture_ux.csv / capture_ux.status.log を読んでフェーズ別CSVを書き出す
    python can_split_phases.py --capture capture_ux

    # can_diff.py へ渡す用に、自分が出したOBD要求と応答を落とす
    python can_split_phases.py --capture capture_ux --exclude-ids 7E0,7E8 --suffix _passive

    # 中身を見るだけ（ファイルは書かない）
    python can_split_phases.py --capture capture_ux --list

    # 合成データによる自己テスト（実機・実車不要）
    python can_split_phases.py --selftest

出力:
    <prefix>_p1_<label>.csv, <prefix>_p2_<label>.csv, ...
    （入力と同じ列 host_iso,t_us,can_id,ext,rtr,dlc,data_hex。そのまま
      can_diff.py / can_correlate.py / can_obd_extract.py へ渡せる）
"""
import argparse
import csv
import json
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

PHASE_RE = re.compile(
    r"#\s*host:\s*(?P<tag>phase|phase-resume)\s+"
    r"t=(?P<t>[-\d.]+)s\s+at=(?P<at>[-\d.]+)s\s+"
    r"action=(?P<action>\w+)\s+key=(?P<key>\S+)\s+label=(?P<label>.+?)\s*$"
)


def _parse_iso(s: str):
    """status ログ／CSV の host_iso をdatetimeへ。失敗したらNone。"""
    try:
        return datetime.fromisoformat(s.strip())
    except (ValueError, AttributeError):
        return None


def read_phases(status_path: Path):
    """status ログからフェーズ区切りを読む。

    戻り値: [{"host": datetime, "action": str, "label": str, "at": float}, ...]
    `phase-resume`（再接続時の状態復旧）は新しい区間の開始ではないため無視する。
    """
    phases = []
    with open(status_path, "r", encoding="utf-8", errors="backslashreplace") as f:
        for line in f:
            if "# host: phase" not in line:
                continue
            host_s, _, body = line.partition("\t")
            m = PHASE_RE.search(body if body else line)
            if not m:
                continue
            if m.group("tag") != "phase":
                continue
            host = _parse_iso(host_s)
            if host is None:
                continue
            phases.append({
                "host": host,
                "at": float(m.group("at")),
                "action": m.group("action"),
                "label": m.group("label"),
            })
    phases.sort(key=lambda p: p["host"])
    return phases


def _safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)[:40] or "phase"


def split_capture(csv_path: Path, phases, out_prefix: str, exclude_ids=(),
                  write: bool = True, suffix: str = ""):
    """フレームCSVをフェーズ境界で分割する。

    最初のフェーズより前の行は `p0_pre` へ入れる（キャプチャ開始直後の数行）。
    """
    exclude = {int(x, 16) for x in exclude_ids}

    buckets = []
    if phases and True:
        buckets.append({"name": "p0_pre", "label": "pre", "start": None,
                        "end": phases[0]["host"], "action": "-", "at": None})
    for i, ph in enumerate(phases):
        end = phases[i + 1]["host"] if i + 1 < len(phases) else None
        buckets.append({
            "name": f"p{i + 1}_{_safe_name(ph['label'])}",
            "label": ph["label"], "start": ph["host"], "end": end,
            "action": ph["action"], "at": ph["at"],
        })
    if not phases:
        buckets = [{"name": "p1_all", "label": "all", "start": None, "end": None,
                    "action": "-", "at": None}]

    for b in buckets:
        b["rows"] = 0
        b["excluded"] = 0
        b["ids"] = Counter()
        b["t_first"] = None
        b["t_last"] = None
        b["writer"] = None
        b["file"] = None
        b["path"] = Path(f"{out_prefix}_{b['name']}{suffix}.csv")

    header = None
    idx = 0                       # 現在の bucket（host_iso は単調増加のはず）
    with open(csv_path, "r", encoding="utf-8", errors="backslashreplace", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if header is None:
                header = row
                continue
            if len(row) < 7:
                continue
            host = _parse_iso(row[0])
            if host is not None:
                while (idx + 1 < len(buckets) and buckets[idx]["end"] is not None
                       and host >= buckets[idx]["end"]):
                    idx += 1
            b = buckets[idx]
            try:
                can_id = int(row[2], 16) if row[2].lower().startswith("0x") else int(row[2], 16)
                t_us = int(row[1])
            except ValueError:
                continue
            if can_id in exclude:
                b["excluded"] += 1
                continue
            b["rows"] += 1
            b["ids"][can_id] += 1
            if b["t_first"] is None:
                b["t_first"] = t_us
            b["t_last"] = t_us
            if write:
                if b["writer"] is None:
                    b["file"] = open(b["path"], "w", encoding="utf-8", newline="")
                    b["writer"] = csv.writer(b["file"], lineterminator="\n")
                    b["writer"].writerow(header)
                b["writer"].writerow(row)

    for b in buckets:
        if b["file"]:
            b["file"].close()
    return buckets


def format_summary(buckets, wrote: bool) -> str:
    lines = ["==== phase split summary ===="]
    for b in buckets:
        span = ""
        if b["t_first"] is not None and b["t_last"] is not None:
            sec = (b["t_last"] - b["t_first"]) / 1_000_000
            rate = b["rows"] / sec if sec > 0 else 0
            span = f"  {sec:7.1f}s  {rate:6.1f} frame/s"
        at = f"@{b['at']:.0f}s" if b["at"] is not None else "@-"
        lines.append(f"  {b['name']:<28} {at:>8} action={b['action']:<7} "
                     f"frames={b['rows']:<7} ids={len(b['ids']):<4}{span}")
        top = ", ".join(f"0x{cid:03X}:{n}" for cid, n in b["ids"].most_common(8))
        if top:
            lines.append(f"      {top}")
        if b["excluded"]:
            lines.append(f"      (除外 {b['excluded']} 行)")
        if wrote and b["rows"]:
            lines.append(f"      -> {b['path']}")
    return "\n".join(lines)


# ---- 自己テスト -----------------------------------------------------------
SELFTEST_STATUS = """2026-09-05T01:00:00+00:00\t# ===== CAN raw logger + OBD2 poller =====
2026-09-05T01:00:00.500000+00:00\t# host: phase t=0.0s at=0s action=passive key=p label=ig_on
2026-09-05T01:00:02+00:00\t# stat t=2000000 total=3 rate=3/s drop_rb=0 rx_missed=0 rx_overrun=0 buserr=0 tec=0 rec=0 state=RUNNING alerts=0x0
2026-09-05T01:00:03+00:00\t# host: phase t=3.0s at=3s action=poll key=r label=idle_obd
2026-09-05T01:00:04+00:00\t# host: phase-resume t=4.0s at=3s action=poll key=r label=idle_obd
2026-09-05T01:00:06+00:00\t# host: phase t=6.0s at=6s action=mark key=- label=drive
"""

SELFTEST_CSV = """host_iso,t_us,can_id,ext,rtr,dlc,data_hex
2026-09-05T01:00:00.100000+00:00,100000,0x201,0,0,8,0011223344556601
2026-09-05T01:00:01+00:00,1000000,0x201,0,0,8,0011223344556602
2026-09-05T01:00:02+00:00,2000000,0x4B0,0,0,8,0102030405060708
2026-09-05T01:00:03.200000+00:00,3200000,0x7E0,0,0,8,02010C5555555555
2026-09-05T01:00:03.300000+00:00,3300000,0x7E8,0,0,8,04410C0BB0000000
2026-09-05T01:00:04.500000+00:00,4500000,0x201,0,0,8,0011223344556603
2026-09-05T01:00:07+00:00,7000000,0x201,0,0,8,0011223344556604
2026-09-05T01:00:08+00:00,8000000,0x4B0,0,0,8,0102030405060709
"""


def run_selftest() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="cansplit_selftest_"))
    (tmp / "cap.status.log").write_text(SELFTEST_STATUS, encoding="utf-8")
    (tmp / "cap.csv").write_text(SELFTEST_CSV, encoding="utf-8")

    ok = True

    def check(cond, msg):
        nonlocal ok
        if not cond:
            ok = False
        print(f"  [{'OK  ' if cond else 'FAIL'}] {msg}")

    phases = read_phases(tmp / "cap.status.log")
    check(len(phases) == 3, f"phase行を3つ読む（phase-resumeは除く） (got {len(phases)})")
    check([p["label"] for p in phases] == ["ig_on", "idle_obd", "drive"],
          f"ラベルの順序 (got {[p['label'] for p in phases]})")
    check(phases[1]["action"] == "poll", f"action の読み取り (got {phases[1]['action']})")

    b = split_capture(tmp / "cap.csv", phases, str(tmp / "cap"))
    names = [x["name"] for x in b]
    check(names == ["p0_pre", "p1_ig_on", "p2_idle_obd", "p3_drive"],
          f"バケット名 (got {names})")
    counts = {x["name"]: x["rows"] for x in b}
    # 01:00:00.100 は最初のphase(00.500)より前 → p0_pre
    check(counts["p0_pre"] == 1, f"最初のフェーズより前は p0_pre へ (got {counts['p0_pre']})")
    check(counts["p1_ig_on"] == 2, f"受動区間は2行 (got {counts['p1_ig_on']})")
    check(counts["p2_idle_obd"] == 3, f"ポーリング区間は3行 (got {counts['p2_idle_obd']})")
    check(counts["p3_drive"] == 2, f"走行区間は2行 (got {counts['p3_drive']})")
    body = (tmp / "cap_p2_idle_obd.csv").read_text(encoding="utf-8").splitlines()
    check(body[0].startswith("host_iso,"), "分割後CSVにヘッダが付く")
    check(len(body) == 4, f"分割後CSVの行数=ヘッダ+3 (got {len(body)})")

    b2 = split_capture(tmp / "cap.csv", phases, str(tmp / "cap_x"),
                       exclude_ids=("7E0", "7E8"), suffix="_nx")
    c2 = {x["name"]: x["rows"] for x in b2}
    e2 = {x["name"]: x["excluded"] for x in b2}
    check(c2["p2_idle_obd"] == 1, f"--exclude-ids でOBD往復が落ちる (got {c2['p2_idle_obd']})")
    check(e2["p2_idle_obd"] == 2, f"除外カウント (got {e2['p2_idle_obd']})")
    check((tmp / "cap_x_p2_idle_obd_nx.csv").exists(), "--suffix がファイル名に付く")

    b3 = split_capture(tmp / "cap.csv", [], str(tmp / "cap_n"))
    check(len(b3) == 1 and b3[0]["rows"] == 8,
          f"phase行が無ければ全部を1本にまとめる (got {[x['rows'] for x in b3]})")

    print()
    print(format_summary(b, wrote=True))
    print()
    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> None:
    ap = argparse.ArgumentParser(
        description="--phase-plan 付きキャプチャをフェーズごとのCSVへ分割する")
    ap.add_argument("--capture", help="キャプチャの接頭辞（<prefix>.csv と <prefix>.status.log を読む）")
    ap.add_argument("--csv", help="フレームCSVを個別指定する場合")
    ap.add_argument("--status", help="statusログを個別指定する場合")
    ap.add_argument("--out", help="出力の接頭辞（既定: 入力CSVから拡張子を除いたもの）")
    ap.add_argument("--suffix", default="", help="出力ファイル名の末尾に付ける文字列")
    ap.add_argument("--exclude-ids", default="",
                    help="除外するCAN ID（16進カンマ区切り。例: 7E0,7E8）。"
                         "can_diff.py へ渡す前に自分のOBD往復を落とす用")
    ap.add_argument("--list", action="store_true", help="集計を表示するだけでファイルを書かない")
    ap.add_argument("--json", action="store_true", help="集計をJSONでも出力")
    ap.add_argument("--selftest", action="store_true", help="合成データで自己テスト")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(run_selftest())

    if args.capture:
        csv_path = Path(f"{args.capture}.csv")
        status_path = Path(f"{args.capture}.status.log")
    else:
        if not args.csv or not args.status:
            ap.error("--capture、または --csv と --status の両方を指定してください")
        csv_path = Path(args.csv)
        status_path = Path(args.status)

    for pth in (csv_path, status_path):
        if not pth.exists():
            ap.error(f"ファイルが見つかりません: {pth}")

    out_prefix = args.out or str(csv_path.with_suffix(""))
    exclude = [x.strip() for x in args.exclude_ids.split(",") if x.strip()]

    phases = read_phases(status_path)
    if not phases:
        print("[!] status ログに `# host: phase` 行がありません。"
              "--phase-plan 無しのキャプチャとして全体を1本に扱います。")
    buckets = split_capture(csv_path, phases, out_prefix,
                            exclude_ids=exclude, write=not args.list,
                            suffix=args.suffix)
    print(format_summary(buckets, wrote=not args.list))
    if args.json:
        print(json.dumps([{
            "name": b["name"], "label": b["label"], "action": b["action"],
            "at_s": b["at"], "frames": b["rows"], "excluded": b["excluded"],
            "unique_ids": len(b["ids"]),
            "ids": {f"0x{cid:03X}": n for cid, n in b["ids"].most_common()},
            "path": str(b["path"]) if (not args.list and b["rows"]) else None,
        } for b in buckets], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
