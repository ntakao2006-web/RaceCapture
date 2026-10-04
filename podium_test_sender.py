"""Podiumライブテレメトリーの疎通テスト（PCから直接送る）

ロガーを介さずにPCから telemetry.podium.live へ認証・meta・ダミー値を送り、
「Podium側（キー・アカウント）の問題」と「ロガー側（実装・モデム）の問題」を切り分ける。
プロトコルは podium_connect_notes.md 3章・9章。

使い方:
    python podium_test_sender.py            # キーは画面に表示されない入力で聞かれる
    python podium_test_sender.py --seconds 120

ストリーミングキーはファイル・ログ・引数に残さない（getpassで入力する）。
"""
import argparse
import getpass
import json
import math
import socket
import time

HOST = "telemetry.podium.live"
PORT = 8080

# 地図表示用に純正RaceCaptureと同じ名前にしておく（podium_connect_notes.md 9.2）
META = [
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=60, help="ダミー値を送り続ける秒数")
    args = ap.parse_args()

    key = getpass.getpass("ストリーミングキー（表示されません）: ").strip()
    if not key:
        print("キーが空です")
        return

    print(f"[1] 接続: {HOST}:{PORT}")
    sock = socket.create_connection((HOST, PORT), timeout=10)
    print("    TCP接続OK")

    print("[2] 認証を送信")
    send(sock, {"cmd": {"schemaVer": 2, "auth": {"deviceId": key}}})
    try:
        reply = read_line(sock, 10)
    except socket.timeout:
        print("    ×10秒待っても応答なし（改行が抜けている等。PCからなら通常起きない）")
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
            round(CENTER_LAT + 0.0027 * math.sin(ang), 6),
            round(CENTER_LON + 0.0033 * math.cos(ang), 6),
            round(110 + 20 * math.sin(ang * 3), 2),
            int(4000 + 2000 * math.sin(ang * 5)),
        ]
        bitmask = (1 << len(META)) - 1  # 全チャンネルに値あり
        send(sock, {"s": {"d": values + [bitmask]}})
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
