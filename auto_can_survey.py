"""
車両接続時の自動データ収集スクリプト（方法A：複数戦略ループ）。
task_phase2_breakdown.md 2-0-19。

運転中など対話的な確認ができない間、一定時間にわたって複数の収集戦略
（OBD2標準PIDスキャン／生CAN長時間モニタリング／未知ID集中サンプリング）
を自動で繰り返し、結果をログファイルへ蓄積する。車種依存のデコード式は
一切含まない汎用スクリプトなので、車種が変わっても再利用できる。

安全上の原則：本スクリプトは読み取り専用のPIDリクエストとATMA(生CAN
モニタリング)のみを行い、車両側の設定を書き換えるコマンドは一切送らない。

使い方:
    python auto_can_survey.py COM11 lexus_ux 30
    (第1引数=COMポート、第2引数=車両識別名、第3引数=収集を続ける分数)

停車後の呼び出し方の想定:
    「一旦停車しました」と言われたら、<車両名>_auto_survey.json と
    <車両名>_auto_survey_log.txt を読み込んで、新規に見つかったCAN ID・
    PID対応状況を解析・報告し、能動的な差分実験（ウィンカー等）を提案する。
"""
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone

import serial

BAUDRATE = 38400
TIMEOUT_SEC = 5.0

# 標準OBD2 PID群（サポート状況に関わらず全て試す。車種によって対応可否が異なる）
CANDIDATE_PIDS = [
    "0101", "0103", "0104", "0105", "0106", "0107", "010B", "010C", "010D",
    "010E", "010F", "0110", "0111", "0113", "0115", "011C", "011F",
    "0121", "012C", "012E", "0130", "0131", "0133", "0134",
    "0141", "0142", "0143", "0144", "0145", "0147", "0149", "014A", "014C",
    "015C",  # 油温(サポート外の車種が多いが毎回試す)
]


def send(ser, cmd, timeout=TIMEOUT_SEC):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode("ascii"))
    deadline = time.monotonic() + timeout
    buf = b""
    while time.monotonic() < deadline:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            if b">" in buf:
                break
        else:
            time.sleep(0.05)
    return buf.decode("ascii", errors="backslashreplace").strip().strip(">").strip()


def strategy_obd2_scan(ser, log):
    """戦略1: 標準OBD2 PIDを片っ端からリクエストし、応答があったものを記録する"""
    send(ser, "ATH0")
    for pid in CANDIDATE_PIDS:
        resp = send(ser, pid, timeout=4.0)
        entry = {"ts": time.time(), "pid": pid, "resp": resp}
        log["obd2_samples"].append(entry)
        if "NO DATA" not in resp and "SEARCHING" not in resp and resp:
            log["obd2_supported"].setdefault(pid, []).append(resp)
    # プロトコル種別も記録
    proto = send(ser, "ATDPN")
    log["protocol_observations"].append({"ts": time.time(), "proto": proto})


def strategy_can_monitor(ser, log, rounds=10, round_sec=2.2):
    """戦略2: 生CANをATMAで無差別モニタリングし、CAN IDごとにサンプルを蓄積する"""
    send(ser, "ATH1")
    send(ser, "ATS1")
    for _ in range(rounds):
        ser.reset_input_buffer()
        ser.write(b"ATMA\r")
        time.sleep(round_sec)
        data = ser.read(ser.in_waiting or 1)
        while ser.in_waiting:
            data += ser.read(ser.in_waiting)
            time.sleep(0.03)
        ser.write(b"\r")
        time.sleep(0.2)
        ser.read(ser.in_waiting or 1)
        text = data.decode("ascii", errors="backslashreplace")
        for m in re.finditer(r'\b([0-9A-F]{3})((?:\s[0-9A-F]{2}){1,8})', text):
            can_id, payload = m.group(1), m.group(2).strip()
            log["can_id_counts"][can_id] = log["can_id_counts"].get(can_id, 0) + 1
            log["can_id_samples"].setdefault(can_id, []).append({"ts": time.time(), "payload": payload})


def strategy_focus_unknown(ser, log, rounds=6, round_sec=2.2):
    """戦略3: これまでの収集で出現回数が少ない(低頻度=未解明の可能性が高い)IDに絞って追加サンプリングする"""
    counts = log["can_id_counts"]
    if not counts:
        return
    # 出現回数が少ない順に上位を「注目ID」とみなす(閾値: 中央値以下)
    sorted_ids = sorted(counts.items(), key=lambda kv: kv[1])
    focus_ids = {cid for cid, _ in sorted_ids[: max(1, len(sorted_ids) // 3)]}
    send(ser, "ATH1")
    send(ser, "ATS1")
    for _ in range(rounds):
        ser.reset_input_buffer()
        ser.write(b"ATMA\r")
        time.sleep(round_sec)
        data = ser.read(ser.in_waiting or 1)
        while ser.in_waiting:
            data += ser.read(ser.in_waiting)
            time.sleep(0.03)
        ser.write(b"\r")
        time.sleep(0.2)
        ser.read(ser.in_waiting or 1)
        text = data.decode("ascii", errors="backslashreplace")
        for m in re.finditer(r'\b([0-9A-F]{3})((?:\s[0-9A-F]{2}){1,8})', text):
            can_id, payload = m.group(1), m.group(2).strip()
            log["can_id_counts"][can_id] = log["can_id_counts"].get(can_id, 0) + 1
            log["can_id_samples"].setdefault(can_id, []).append({"ts": time.time(), "payload": payload})
            if can_id in focus_ids:
                log["focus_samples"].setdefault(can_id, []).append({"ts": time.time(), "payload": payload})


def main():
    if len(sys.argv) != 4:
        print(f"usage: python {sys.argv[0]} <COMポート> <車両識別名> <収集分数>")
        sys.exit(1)

    port, vehicle, minutes = sys.argv[1], sys.argv[2], float(sys.argv[3])
    out_json = f"{vehicle}_auto_survey.json"
    out_log = f"{vehicle}_auto_survey_log.txt"

    log = {
        "vehicle": vehicle,
        "start_ts": datetime.now(timezone.utc).isoformat(),
        "port": port,
        "obd2_samples": [],
        "obd2_supported": {},
        "protocol_observations": [],
        "can_id_counts": {},
        "can_id_samples": {},
        "focus_samples": {},
        "cycles_completed": 0,
    }

    def flush():
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    def logline(msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line)
        with open(out_log, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    end_time = time.monotonic() + minutes * 60
    logline(f"自動収集開始: vehicle={vehicle} port={port} duration={minutes}min")

    with serial.Serial(port, BAUDRATE, timeout=TIMEOUT_SEC) as ser:
        time.sleep(1.0)
        send(ser, "ATE0")

        cycle = 0
        while time.monotonic() < end_time:
            cycle += 1
            logline(f"--- サイクル{cycle}開始 ---")

            logline("戦略1: OBD2 PIDスキャン中...")
            strategy_obd2_scan(ser, log)
            logline(f"  対応PID数: {len(log['obd2_supported'])}")

            logline("戦略2: 生CANモニタリング中...")
            strategy_can_monitor(ser, log, rounds=10)
            logline(f"  観測CAN ID種類数: {len(log['can_id_counts'])}")

            logline("戦略3: 低頻度IDへの集中サンプリング中...")
            strategy_focus_unknown(ser, log, rounds=6)

            log["cycles_completed"] = cycle
            flush()
            logline(f"--- サイクル{cycle}完了、保存済み ---")

            remaining = end_time - time.monotonic()
            if remaining <= 0:
                break

    logline(f"自動収集終了: 合計{log['cycles_completed']}サイクル完了")
    logline(f"最終結果: {out_json} / ログ: {out_log}")


if __name__ == "__main__":
    main()
