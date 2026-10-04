"""Podiumライブテレメトリーの疎通テスト（PCから直接送る）

ロガーを介さずにPCから telemetry.podium.live へ認証・meta・ダミー値を送り、
「Podium側（キー・アカウント）の問題」と「ロガー側（実装・モデム）の問題」を切り分ける。
プロトコルは podium_connect_notes.md 3章・9章。

使い方:
    python podium_test_sender.py            # キーは画面に表示されない入力で聞かれる
    python podium_test_sender.py --seconds 120

ストリーミングキーはファイル・ログ・引数に残さない（実行時に貼り付けて入力する）。
"""
import argparse

import glob
import json
import math
import os
import re
import socket
import time

HOST = "telemetry.podium.live"
PORT = 8080

# 地図表示用に純正RaceCaptureと同じ名前にしておく（podium_connect_notes.md 9.2）
# 先頭のInterval/Utcは公式RaceCaptureアプリ経由の送信（2026-10-04実測）でも先頭に入っていたシステムチャンネル。
# 純正ファームは常にこの2つを持つ（loggerConfig.h DEFAULT_UPTIME_CONFIG / DEFAULT_UTC_MILLIS_CONFIG）
META = [
    {"nm": "Interval", "ut": "ms", "sr": 10, "min": 0, "max": 0, "prec": 0},
    {"nm": "Utc", "ut": "ms", "sr": 10, "min": 0, "max": 0, "prec": 0},
    {"nm": "Latitude", "ut": "Degrees", "sr": 10, "min": -180, "max": 180, "prec": 6},
    {"nm": "Longitude", "ut": "Degrees", "sr": 10, "min": -180, "max": 180, "prec": 6},
    {"nm": "Speed", "ut": "", "sr": 10, "min": 0, "max": 150, "prec": 2},
    {"nm": "RPM", "ut": "rpm", "sr": 10, "min": 0, "max": 8000, "prec": 0},
]

# ダミー走行の中心（鈴鹿サーキット付近）。半径約300mの円を回る
CENTER_LAT, CENTER_LON = 34.8431, 136.5410


def send(sock, obj):
    sock.sendall((json.dumps(obj, separators=(",", ":")) + "\n").encode("ascii"))


def read_line(sock, timeout):
    sock.settimeout(timeout)
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = sock.recv(4096)
        if not chunk:
            return None if not buf else buf.decode("ascii", "replace")
        buf += chunk
    return buf.decode("ascii", "replace").strip()


def key_from_app_log():
    """公式RaceCaptureアプリのログに残る認証メッセージから、最後に使われたキーを取り出す"""
    logs = sorted(glob.glob(os.path.expanduser("~/.kivy/logs/kivy_*.txt")), key=os.path.getmtime)
    for path in reversed(logs):
        with open(path, encoding="utf-8", errors="replace") as f:
            found = re.findall(r'"auth": \{"deviceId": "([^"]+)"', f.read())
        if found:
            return found[-1]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=60, help="ダミー値を送り続ける秒数")
    ap.add_argument("--from-app-log", action="store_true",
                    help="キーを手入力せず、公式RaceCaptureアプリのログ(~/.kivy/logs)から最後に使われたものを読む")
    args = ap.parse_args()

    if args.from_app_log:
        key = key_from_app_log()
        if not key:
            print("公式アプリのログからキーが見つかりませんでした")
            return
        print("公式RaceCaptureアプリが最後に使ったキーを使います")
    else:
        # getpassはこのPCのターミナルで貼り付けが1文字しか取れなかったため、表示ありの入力にしている
        key = input("ストリーミングキーを貼り付けてEnter（画面に表示されます）: ").strip()
        if not key:
            print("キーが空です")
            return
    # キー本体は出さず、取り違え確認用に長さと先頭・末尾2文字だけ表示する
    print(f"キー: {len(key)}文字 / {key[:2]}...{key[-2:]}")

    print(f"[1] 接続: {HOST}:{PORT}")
    sock = socket.create_connection((HOST, PORT), timeout=10)
    print("    TCP接続OK")

    print("[2] 認証を送信")
    # 2026-10-04: 次世代Podiumは旧アプリ形式({"schemaVer":2,"auth":{"deviceId":..}})だと無言で切断する。
    # 公式RaceCapture App 2.19.0が実際に送っている形式(apiVer/device/ver/sn付き)に合わせる
    send(sock, {"cmd": {"auth": {
        "deviceId": key,
        "apiVer": 1.1,
        "device": "RC_APP (RCPMK3)",
        "ver": "2.19.0 (2.16.1)",
        "sn": "C3PROTO01",
    }}})
    try:
        reply = read_line(sock, 30)
    except socket.timeout:
        print("    ×30秒待っても応答なし（改行が抜けている等。PCからなら通常起きない）")
        return
    if reply is None:
        print("    ×応答なしで切断された → キーが無効（Podium側に登録されていない／旧システムのキー）")
        return
    print(f"    応答: {reply}")
    try:
        status = json.loads(reply).get("status")
    except ValueError:
        status = None
    if status != "ok":
        print("    ×認証失敗")
        return
    print("    ○認証OK")

    print("[3] meta送信")
    send(sock, {"s": {"meta": META}})

    print(f"[4] ダミー値を10Hzで{args.seconds}秒送信（Podiumのライブ画面を確認してください）")
    sock.settimeout(0.0)
    start = time.time()
    n = 0
    while time.time() - start < args.seconds:
        t = time.time() - start
        ang = t / 60.0 * 2 * math.pi  # 1周60秒
        values = [
            int(t * 1000),                 # Interval: 送信開始からのms
            int(time.time() * 1000),       # Utc: UNIX時刻のms
            round(CENTER_LAT + 0.0027 * math.sin(ang), 6),
            round(CENTER_LON + 0.0033 * math.cos(ang), 6),
            round(110 + 20 * math.sin(ang * 3), 2),
            int(4000 + 2000 * math.sin(ang * 5)),
        ]
        bitmask = (1 << len(META)) - 1  # 全チャンネルに値あり
        send(sock, {"s": {"d": values + [bitmask], "t": n}})
        n += 1
        try:
            extra = sock.recv(4096)
            if extra == b"":
                print(f"    ×{n}回目の送信後にサーバーから切断された")
                return
            print(f"    サーバーから: {extra.decode('ascii', 'replace').strip()}")
        except BlockingIOError:
            pass
        time.sleep(0.1)
    print(f"    送信完了（{n}回）")
    sock.close()


if __name__ == "__main__":
    main()
