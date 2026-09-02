"""
MAZDA2 現地バス生死判定スクリプト（ELM327経由 / 読み取り専用）。

mazda2_field_procedure.md「明日の順序」ステップ1専用。実車1回目で自作ロガーが
frames=0 / buserr=0 の完全無音となり、自作側（回路・ハーネス・IG・勘合）は全て
検証済みで白と確定した。残る未実施の操作が「送信」だけなので、独立した既知良品
（ELM327）でOBD 6番/14番へ送信し、以下の3点を1回の実行で切り分ける。

  (1) ELM327自体が生きているか                     … ATI
  (2) 6/14番のバスが生きていてECUが応答するか      … ATSP0 + 0100 + ATDPN
  (3) DLCにブロードキャストが出ているか            … ATH1 + ATMA

(3)が最重要。(2)がOKでも(3)が無音なら「DLCはリクエストが来るまで誰も喋らない
スタブ」＝受動キャプチャが0なのは正常で、OBD2ポーリング方式へ切り替える判断になる。
逆に(3)でフレームが見えるなら、自作ロガーが0だった理由は車両側では説明できない。

送信するのはELM327のAT設定コマンドとOBD2 mode 01（現在値の読み取り）のみ。
車両側の設定を書き換えるコマンドは一切含まない。

使い方:
    python mazda2_bus_check.py --port COM11
    python mazda2_bus_check.py --port COM11 --monitor-seconds 30
    python mazda2_bus_check.py --selftest      # 実機不要の自己テスト

出力: mazda2_bus_check.json（既定。--out で変更可）
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

BAUDRATE = 38400          # ELM327クローンの既定値（2-0-2でv1.5の応答を確認済み）
TIMEOUT_SEC = 5.0
FIRST_PID_TIMEOUT_SEC = 15.0   # ATSP0後の初回リクエストはプロトコル自動探索で数秒かかる
MONITOR_SECONDS = 20.0

# ELM327のプロトコル番号（ATDPNの応答）。先頭の'A'は自動探索で確定したことを表す。
PROTOCOL_NAMES = {
    "1": "SAE J1850 PWM (41.6k)",
    "2": "SAE J1850 VPW (10.4k)",
    "3": "ISO 9141-2",
    "4": "ISO 14230-4 KWP (5baud init)",
    "5": "ISO 14230-4 KWP (fast init)",
    "6": "ISO 15765-4 CAN (11bit, 500k)",
    "7": "ISO 15765-4 CAN (29bit, 500k)",
    "8": "ISO 15765-4 CAN (11bit, 250k)",
    "9": "ISO 15765-4 CAN (29bit, 250k)",
    "A": "SAE J1939 CAN (29bit, 250k)",
}

# ELM327が返すエラー系の応答。いずれかを含めばそのコマンドは失敗扱い。
ERROR_TOKENS = (
    "UNABLE TO CONNECT", "NO DATA", "CAN ERROR", "BUS ERROR", "BUS INIT: ERROR",
    "ERROR", "STOPPED",
)

# ATMAの1行からCAN IDを取り出す（ATH1でヘッダ表示ON時: "7E8 03 41 0D 00" 等）。
_MA_LINE = re.compile(r"^([0-9A-F]{3}|[0-9A-F]{8})[\s]+([0-9A-F\s]+)$")


def _is_error(text):
    up = text.upper()
    return any(tok in up for tok in ERROR_TOKENS)


def send_command(ser, command, timeout=TIMEOUT_SEC):
    """1コマンド送ってプロンプト'>'までを読み、装飾を落としたテキストを返す。"""
    ser.reset_input_buffer()
    ser.write((command + "\r").encode("ascii"))
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


def monitor_all(ser, seconds):
    """ATMA(Monitor All)で生CANを受動監視する。ELM327は何か1文字送ると監視を止める。"""
    ser.reset_input_buffer()
    ser.write(b"ATMA\r")
    deadline = time.monotonic() + seconds
    buf = b""
    while time.monotonic() < deadline:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
        else:
            time.sleep(0.02)
    ser.write(b"\r")           # 監視停止
    stop_deadline = time.monotonic() + 2.0
    while time.monotonic() < stop_deadline:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            if b">" in buf:
                break
        else:
            time.sleep(0.05)
    return buf.decode("ascii", errors="backslashreplace")


def parse_monitor(text):
    """ATMAの生出力からCAN IDごとの件数と、ELM327側のエラー行を集計する。"""
    ids = {}
    errors = {}
    lines = 0
    for raw in text.replace("\r", "\n").split("\n"):
        line = raw.strip().strip(">").strip()
        if not line or line.upper() in ("ATMA", "OK"):
            continue
        lines += 1
        up = line.upper()
        if any(tok in up for tok in ("BUFFER FULL", "DATA ERROR", "CAN ERROR", "STOPPED", "<")):
            key = "BUFFER FULL" if "BUFFER FULL" in up else (
                "DATA ERROR" if "DATA ERROR" in up else (
                    "CAN ERROR" if "CAN ERROR" in up else "OTHER"))
            errors[key] = errors.get(key, 0) + 1
            continue
        m = _MA_LINE.match(up)
        if m:
            ids[m.group(1)] = ids.get(m.group(1), 0) + 1
        else:
            errors["UNPARSED"] = errors.get("UNPARSED", 0) + 1
    return {"lines": lines, "ids": ids, "errors": errors}


def judge(result):
    """3つの観測から現地での次アクションを決める。"""
    elm_alive = "ELM327" in result.get("ati", "").upper()
    pid_ok = result["pid_0100"].get("positive", False)
    ids = result["monitor"]["ids"] if result.get("monitor") else {}
    # 7E8〜7EF は自分のリクエストへの応答なので、ブロードキャストの証拠にはならない。
    broadcast_ids = {k: v for k, v in ids.items()
                     if not (len(k) == 3 and k.startswith("7E"))}

    if not elm_alive:
        return ("ELM327が応答しない",
                "ELM327のLED点灯（pin16の12V）とBluetooth接続を確認。"
                "COMポート違い／ボーレート違い（9600・115200）も疑う。"
                "これが解決しないと車両側の判定は一切できない。")
    if not pid_ok:
        return ("6/14番でOBD2応答なし",
                "手順書ステップ3へ。OBDコネクタ内の圧着端子を 6→3番 / 14→11番 へ移設し、"
                "can_logger の -125k ビルドで受動キャプチャ（MS-CAN狙い）。"
                "★3番と6番、11番と14番を絶対に導通させない★")
    if broadcast_ids:
        return ("バス生存・ブロードキャストあり",
                "DLCに生CANが出ている。自作ロガーの frames=0 は車両側では説明できないので、"
                "同じIG ON状態のまま can_logger を焼き直して再度キャプチャし、"
                "ELM327と自作側で何が違うか（結線の実接触・終端抵抗の外し忘れ等）をその場で比較する。")
    return ("バス生存・ブロードキャストなし",
            "DLCはリクエストが来るまで喋らないスタブ構成。受動キャプチャが0なのは正常。"
            "手順書ステップ2へ切替：can_obd_logger を焼いてOBD2ポーリングをデータ源にする"
            "（生CAN逆解析はDLCからは不可と判断する）。")


def run_check(ser, monitor_seconds, verbose=True):
    def say(*a):
        if verbose:
            print(*a)

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vehicle": "mazda2",
        "commands": [],
    }

    say("[1/3] ELM327の疎通確認")
    for cmd in ["ATZ", "ATE0", "ATH1", "ATI"]:
        resp = send_command(ser, cmd)
        say(f"  > {cmd}\n  < {resp!r}")
        result["commands"].append({"cmd": cmd, "resp": resp})
        if cmd == "ATI":
            result["ati"] = resp

    say("\n[2/3] プロトコル自動探索とECU応答（ATSP0 → 0100 → ATDPN）")
    resp = send_command(ser, "ATSP0")
    say(f"  > ATSP0\n  < {resp!r}")
    result["commands"].append({"cmd": "ATSP0", "resp": resp})

    resp = send_command(ser, "0100", timeout=FIRST_PID_TIMEOUT_SEC)
    say(f"  > 0100 (サポートPID 01-20 / プロトコル確定用)\n  < {resp!r}")
    positive = ("4100" in resp.upper().replace(" ", "")) and not _is_error(resp)
    result["pid_0100"] = {"resp": resp, "positive": positive}
    say(f"    => 肯定応答: {'あり' if positive else 'なし'}")

    dpn = send_command(ser, "ATDPN")
    say(f"  > ATDPN\n  < {dpn!r}")
    key = dpn.strip().upper().lstrip("A").strip()
    result["protocol"] = {"dpn": dpn, "name": PROTOCOL_NAMES.get(key, "不明")}
    say(f"    => {result['protocol']['name']}")

    for pid, desc in (("010C", "エンジン回転数"), ("010D", "車速")):
        resp = send_command(ser, pid)
        say(f"  > {pid} ({desc})\n  < {resp!r}")
        result["commands"].append({"cmd": pid, "desc": desc, "resp": resp})

    say(f"\n[3/3] 生CANブロードキャストの有無（ATMA {monitor_seconds:.0f}秒）")
    raw = monitor_all(ser, monitor_seconds)
    mon = parse_monitor(raw)
    result["monitor"] = mon
    result["monitor_raw_tail"] = raw[-4000:]
    if mon["ids"]:
        for cid, cnt in sorted(mon["ids"].items(), key=lambda kv: -kv[1]):
            say(f"    {cid}: {cnt}件")
    else:
        say("    フレームなし（無音）")
    if mon["errors"]:
        say(f"    ELM327側の異常行: {mon['errors']}")

    verdict, action = judge(result)
    result["verdict"] = verdict
    result["next_action"] = action
    say("\n" + "=" * 60)
    say(f"判定: {verdict}")
    say(f"次にやること: {action}")
    say("=" * 60)
    return result


# ---------------------------------------------------------------- selftest
class _FakeElm:
    """実機なしで全経路を通すための偽ELM327。scenarioで応答を切り替える。"""

    def __init__(self, scenario):
        self.scenario = scenario
        self._out = b""
        self._monitoring = False

    # serial.Serial 互換の最小インタフェース
    @property
    def in_waiting(self):
        return len(self._out)

    def reset_input_buffer(self):
        self._out = b""

    def read(self, n=1):
        chunk, self._out = self._out[:n], self._out[n:]
        return chunk

    def write(self, data):
        cmd = data.decode("ascii").strip().upper()
        if self._monitoring:
            self._monitoring = False
            self._out += b"STOPPED\r\r>"
            return len(data)
        self._out += self._reply(cmd)
        return len(data)

    def _reply(self, cmd):
        dead = self.scenario == "dead"
        if self.scenario == "no_elm":
            return b""
        if cmd == "ATZ":
            return b"ELM327 v1.5\r\r>"
        if cmd in ("ATE0", "ATH1", "ATSP0"):
            return b"OK\r\r>"
        if cmd == "ATI":
            return b"ELM327 v1.5\r\r>"
        if cmd == "0100":
            return b"NO DATA\r\r>" if dead else b"7E8 06 41 00 BE 3F A8 13\r\r>"
        if cmd == "ATDPN":
            return b"\r>" if dead else b"A6\r\r>"
        if cmd.startswith("01"):
            return b"NO DATA\r\r>" if dead else b"7E8 04 41 0C 0B B8\r\r>"
        if cmd == "ATMA":
            self._monitoring = True
            if self.scenario == "broadcast":
                return (b"200 00 00 00 00 00 00 00 00\r"
                        b"4B0 12 34 12 34 12 34 12 34\r"
                        b"200 00 00 00 00 00 00 00 01\r"
                        b"7E8 04 41 0C 0B B8 00 00 00\r")
            return b""
        return b"?\r\r>"


def selftest():
    cases = [
        ("broadcast", "バス生存・ブロードキャストあり", {"200", "4B0"}),
        ("stub", "バス生存・ブロードキャストなし", set()),
        ("dead", "6/14番でOBD2応答なし", set()),
        ("no_elm", "ELM327が応答しない", set()),
    ]
    ok = fail = 0

    def check(label, cond):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  [OK  ] {label}")
        else:
            fail += 1
            print(f"  [FAIL] {label}")

    for scenario, expect_verdict, expect_bcast in cases:
        print(f"--- scenario: {scenario} ---")
        res = run_check(_FakeElm(scenario), monitor_seconds=0.3, verbose=False)
        check(f"{scenario}: 判定が '{expect_verdict}' (got '{res['verdict']}')",
              res["verdict"] == expect_verdict)
        got_bcast = {k for k in res["monitor"]["ids"] if not k.startswith("7E")}
        check(f"{scenario}: ブロードキャストID {expect_bcast or 'なし'} (got {got_bcast or 'なし'})",
              got_bcast == expect_bcast)
        check(f"{scenario}: next_action が空でない", bool(res["next_action"]))

    # 7E8系をブロードキャストと誤認しないこと（自分の応答なので除外されるべき）
    res = run_check(_FakeElm("stub"), monitor_seconds=0.3, verbose=False)
    check("7E8応答のみでは 'ブロードキャストあり' と判定しない",
          res["verdict"] == "バス生存・ブロードキャストなし")
    # プロトコル名の解決
    res = run_check(_FakeElm("broadcast"), monitor_seconds=0.3, verbose=False)
    check("ATDPN 'A6' を ISO 15765-4 CAN(11bit,500k) と解決",
          "11bit, 500k" in res["protocol"]["name"])
    # ATMAのパーサ
    mon = parse_monitor("200 11 22 33\rBUFFER FULL\r4B0 01 02\r200 11 22 34\r")
    check("parse_monitor: ID件数 (200=2, 4B0=1)",
          mon["ids"] == {"200": 2, "4B0": 1})
    check("parse_monitor: BUFFER FULL を異常行として計上",
          mon["errors"].get("BUFFER FULL") == 1)

    print(f"\nSELFTEST: {'PASS' if fail == 0 else 'FAIL'}  ({ok} ok / {fail} fail)")
    return 0 if fail == 0 else 1


def main():
    ap = argparse.ArgumentParser(description="MAZDA2 現地バス生死判定 (ELM327経由・読み取り専用)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--port", help="ELM327のCOMポート (例: COM11)")
    src.add_argument("--selftest", action="store_true", help="実機不要の自己テスト")
    ap.add_argument("--baud", type=int, default=BAUDRATE)
    ap.add_argument("--monitor-seconds", type=float, default=MONITOR_SECONDS,
                    help=f"ATMAで生CANを監視する秒数 (既定: {MONITOR_SECONDS:.0f})")
    ap.add_argument("--out", default="mazda2_bus_check.json")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    import serial  # 実機実行時のみ必要

    print(f"[*] {args.port} へ {args.baud}bps で接続します...")
    with serial.Serial(args.port, args.baud, timeout=TIMEOUT_SEC) as ser:
        time.sleep(1.0)  # Bluetooth SPPの接続確立待ち
        result = run_check(ser, args.monitor_seconds)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[*] 結果を {args.out} へ保存しました。")


if __name__ == "__main__":
    main()
