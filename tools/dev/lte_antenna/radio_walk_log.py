"""Log LTE radio quality against position while carrying the logger (course walk, 2026-10-23).

Runs on the UNO Q host, started before the walk and left running in the background:
    nohup python3 radio_walk_log.py 60 > /dev/null 2>&1 &      (60 = minutes, then it stops)
Touching ~/radio_walk/stop ends it early. The logger software is not changed: this only
switches the send link to LTE (radio values are read by the modem only while sending over
LTE; on Wi-Fi the modem is off), reads /api/podium and /api/telemetry every 2 s, and
restores the previous link at the end.
LTE use while it runs is the normal telemetry, about 4 MB per hour (LTE_PODIUM.md 2026-10-19).

Output: ~/radio_walk/walk_<time>.csv, one row per 2 s. Radio columns are blank until the
first reading after registration and when the newest reading is older than 15 s.
Radio values come from the modem about every 25 sends (sim7070.py read_radio):
RSRP dBm (higher is better, -110 or below is weak), SINR dB, RSRQ dB, PCI = cell number.
"""
import csv
import json
import os
import signal
import sys
import time
import urllib.request

BASE = 'http://127.0.0.1:8080'
OUT = os.path.expanduser('~/radio_walk')
STOP = os.path.join(OUT, 'stop')
FIELDS = ['time', 'lat', 'lon', 'fix', 'sats', 'speed_kmh', 'rsrp', 'sinr', 'rsrq', 'csq', 'pci', 'band',
          'radio_age_s', 'link', 'state', 'frames', 'reconnects']


def call(path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data, {'Content-Type': 'application/json', 'X-EcoCapture': '1'})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def row(podium, telemetry):
    s = podium['status']
    v = ((telemetry or {}).get('sample') or {}).get('values') or {}
    out = {'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'lat': v.get('Lat'), 'lon': v.get('Lon'),
           'fix': v.get('GPSFix'), 'sats': v.get('GPSSats'), 'speed_kmh': v.get('GPSSpeed'),
           'link': s.get('active_link'), 'state': s.get('state'), 'frames': s.get('frames'),
           'reconnects': s.get('reconnects')}
    radio = s.get('radio') or {}
    age = time.time() - radio['at'] if radio.get('at') else None
    # Before registration CPSI reports zeros and CSQ 99 (unknown); those are not readings.
    if age is not None and age <= 15 and radio.get('csq') != 99 and radio.get('rsrp', -1) < 0:
        fields = (radio.get('cpsi') or '').split(',')
        out.update(rsrp=radio.get('rsrp'), sinr=radio.get('sinr'), rsrq=radio.get('rsrq'), csq=radio.get('csq'),
                   pci=fields[5] if len(fields) >= 14 else None, band=radio.get('band'), radio_age_s=round(age))
    return out


def main(minutes):
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(STOP): os.remove(STOP)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    before = call('/api/podium')['config']['link']
    if before != 'lte': call('/api/podium', {'link': 'lte'})
    path = os.path.join(OUT, time.strftime('walk_%Y%m%d_%H%M%S.csv'))
    end = time.monotonic() + minutes * 60
    try:
        with open(path, 'w', newline='') as f:
            w = csv.DictWriter(f, FIELDS); w.writeheader()
            while time.monotonic() < end and not os.path.exists(STOP):
                try: w.writerow(row(call('/api/podium'), call('/api/telemetry')))
                except OSError: w.writerow({'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'state': 'web not answering'})
                f.flush(); os.fsync(f.fileno())
                time.sleep(2)
    finally:
        if before != 'lte':
            try: call('/api/podium', {'link': before})
            except OSError: pass
    print(path)


if __name__ == '__main__':
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 60)
