"""overlay_rec の時刻合わせの試験用：EcoCaptureの /api/telemetry の代わりに、GNSSの時刻をわざとずらした値を返す。

  python3 fake_telemetry.py [port=18080] [gnss_offset_s=3600.3] [no_gnss_s=15]
  OVERLAY_TELEMETRY_PORT=18080 ./overlay_rec file:test_720p.jpg 'ret/%Y%m%d_%H%M%S.ts' 40

- 本当のGNSSの時刻 ＝ 本体の時計 ＋ gnss_offset_s とみなす
- 最初の no_gnss_s 秒は gnss_utc を null にする（測位前。ファイル名の付け直しを確かめる）
- 各行のGNSSの時刻は、受け取りより20〜100ms前の解（受け取りの遅れ）にする。overlay_recは遅れの一番小さい値を使うので、
  .csvのutcは「本体の時計 ＋ gnss_offset_s − 約0.02秒」になるはず
"""
import json
import math
import random
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 18080
OFFSET = float(sys.argv[2]) if len(sys.argv) > 2 else 3600.3
NO_GNSS = float(sys.argv[3]) if len(sys.argv) > 3 else 15
START = time.time()
GPS_UTC_LEAP = 18  # iTOWはGPSの時刻（UTCより18秒進んでいる）


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        now = time.time()
        sample = {'host_utc': datetime.fromtimestamp(now, timezone.utc).isoformat(), 'gnss_utc': None, 'gnss_itow_ms': None,
                  'values': {'Speed': 88.0, 'RPM': 5200.0, 'WaterTemp': 92.0, 'LatAccel': 0.3, 'LongAccel': -0.2},
                  'can_signals': {'OilTemp': 101.0}, 'lap': {'CurrentLap': 2, 'ElapsedTime': 0.5, 'LapTime': 1.6, 'BestLap': 1.58}}
        if now - START >= NO_GNSS:
            solution = now - random.uniform(0.02, 0.1) + OFFSET
            solution = math.floor(solution * 10) / 10  # 10Hzの解は100msの区切り（受け取りより後にはならない）
            sample['gnss_utc'] = datetime.fromtimestamp(int(solution), timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            sample['gnss_itow_ms'] = int(round((solution + GPS_UTC_LEAP) * 1000)) % (7 * 86400 * 1000)
        body = json.dumps({'sample': sample}, separators=(',', ':')).encode()  # EcoCaptureと同じく空白なし
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


HTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
