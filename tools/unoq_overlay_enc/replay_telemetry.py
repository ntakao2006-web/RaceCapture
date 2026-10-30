"""焼き込み録画の試験用：Ver.2の走行記録（本体のeMMCのCSV）を、EcoCaptureの /api/telemetry と同じ形で流し直す。

overlay_rec を OVERLAY_TELEMETRY_PORT=<port> で動かすと、今のカメラの景色に、その走行のときの計器が重なる
（手順書 unoq_video_check_procedure.md 5-15）。
- 記録の行の時刻（mcu_ms）どおり、実際の時間の速さで進める（--speed で速く）。最後まで行ったら最後の行のまま（--loop で最初から）
- gnss_utc・gnss_itow_ms は記録のまま、host_utc は今の本体の時計で返す。overlay_rec はこの差から各コマの時刻を走行のときの
  時刻に直すので、録画のファイル名と .csv も走行のときの時刻になる（本物のGNSSの時刻での確かめにもなる）
- 緯度・経度は返さない（計器に使わない）

本体の走行記録は大きい（数百MB〜1GB）ので、先にPCで必要な区間だけを抜き出して本体へ送る:
  python replay_telemetry.py --excerpt 走行記録.csv 抜き出し.csv --from 2026-10-24T03:19:40 --seconds 200 [--every 5]
    --from：GNSSの時刻（UTC、日付から）。--every 5 で5行に1行（100Hz→20Hz。overlay_recは約10Hzで読む）。緯度・経度は空にする
本体で流す:
  python3 replay_telemetry.py 抜き出し.csv [--port 18081] [--speed 1] [--loop]
"""
import argparse
import bisect
import csv
import json
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

# EcoCapture-Web/models.py の CHANNELS・LAP_CHANNELS（記録の列の名前）
CHANNELS = ['Speed', 'GPSSpeed', 'RPM', 'Throttle', 'BatteryVolt', 'Lat', 'Lon', 'Altitude', 'Yaw', 'GPSFix', 'GPSSats',
            'GNSSHz', 'AccelX', 'AccelY', 'AccelZ', 'GyroX', 'GyroY', 'GyroZ', 'Roll', 'Pitch', 'LongAccel', 'LatAccel',
            'VertAccel', 'Distance', 'WaterTemp']
LAP_CHANNELS = ['LapCount', 'CurrentLap', 'LapTime', 'BestLap', 'ElapsedTime', 'RaceTime', 'LapsLeft', 'TimeLimit', 'Margin']
HIDDEN = {'Lat', 'Lon'}


def num(text):
    try:
        return float(text) if text not in ('', 'None', 'null') else None
    except ValueError:
        return None


def excerpt(src, dst, start, seconds, every):
    """走行記録から、GNSSの時刻 start（UTC、2026-10-24T03:19:40 の形）から seconds 秒を every 行に1行で抜き出す"""
    csv.field_size_limit(1 << 24)
    with open(src, newline='', encoding='utf-8') as f, open(dst, 'w', newline='', encoding='utf-8') as g:
        r = csv.reader(f)
        head = next(r)
        ix = {k: i for i, k in enumerate(head)}
        w = csv.writer(g)
        w.writerow(head)
        t0, n, kept = None, 0, 0
        for row in r:
            if t0 is None:
                gnss = row[ix['gnss_utc']]
                if len(gnss) < 19 or gnss[:19] < start:
                    continue
                t0 = int(row[ix['mcu_ms']])
            if (int(row[ix['mcu_ms']]) - t0) / 1000 > seconds:
                break
            n += 1
            if (n - 1) % every:
                continue
            for k in HIDDEN:
                row[ix[k]] = ''
            w.writerow(row)
            kept += 1
    if t0 is None:
        sys.exit(f'GNSSの時刻 {start} 以降の行がありません')
    print(f'{dst}: {kept}行（{n}行から）')


class Replay:
    def __init__(self, path, speed, loop):
        csv.field_size_limit(1 << 24)
        with open(path, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            self.rows = [self.sample(row) for row in r]
        self.times = [s.pop('_t') for s in self.rows]
        self.speed, self.loop, self.start = speed, loop, time.time()

    @staticmethod
    def sample(row):
        can = {}
        if row.get('can_signals'):
            try:
                can = json.loads(row['can_signals'])
            except ValueError:
                pass
        gnss = row.get('gnss_utc') or None
        itow = num(row.get('gnss_itow_ms', ''))
        return {
            '_t': int(row['mcu_ms']) / 1000,
            'schema': 1, 'source': 'replay', 'demo': False,
            'gnss_utc': gnss, 'gnss_itow_ms': int(itow) if itow is not None else None,
            'values': {k: (None if k in HIDDEN else num(row.get(k, ''))) for k in CHANNELS},
            'can_signals': can,
            'lap': {k: num(row.get(k, '')) for k in LAP_CHANNELS},
        }

    def now_sample(self):
        t = (time.time() - self.start) * self.speed
        span = self.times[-1] - self.times[0]
        if self.loop and span > 0:
            t %= span
        i = max(0, bisect.bisect_right(self.times, self.times[0] + t) - 1)
        s = dict(self.rows[i])
        s['host_utc'] = datetime.now(timezone.utc).isoformat()
        return s


def serve(replay, port):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({'type': 'telemetry', 'status': {'source': 'replay', 'demo': False},
                               'sample': replay.now_sample()}, separators=(',', ':')).encode()  # EcoCaptureと同じく空白なし
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    print(f'{len(replay.rows)}行（{replay.times[-1] - replay.times[0]:.0f}秒）を 127.0.0.1:{port} で流します', flush=True)
    HTTPServer(('127.0.0.1', port), Handler).serve_forever()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('csv')
    ap.add_argument('out', nargs='?', help='--excerpt のときの書き出し先')
    ap.add_argument('--excerpt', action='store_true', help='PCで区間を抜き出す')
    ap.add_argument('--from', dest='start', default='0000-00-00T00:00:00', help='GNSSの時刻（UTC、2026-10-24T03:19:40 の形）')
    ap.add_argument('--seconds', type=float, default=300)
    ap.add_argument('--every', type=int, default=5)
    ap.add_argument('--port', type=int, default=18081)
    ap.add_argument('--speed', type=float, default=1.0)
    ap.add_argument('--loop', action='store_true')
    args = ap.parse_args()
    if args.excerpt:
        if not args.out:
            sys.exit('書き出し先を指定してください')
        excerpt(args.csv, args.out, args.start, args.seconds, max(1, args.every))
        return
    serve(Replay(args.csv, args.speed, args.loop), args.port)


if __name__ == '__main__':
    main()
