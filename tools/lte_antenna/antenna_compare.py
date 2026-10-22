"""Compare LTE antennas on the logger: radio quality, time to connect, telemetry rate (2026-10-21).

Runs on the UNO Q host, with the antenna under test fitted and the logger left in place:
    python3 antenna_compare.py <label> [seconds]      e.g.  python3 antenna_compare.py old 180
Switches the send link to LTE (from power-off of the modem, so registration is timed too),
samples /api/podium every 2 s for `seconds` after the first frame, then restores the link.
Each run is appended to ~/antenna_compare/results.jsonl and all runs so far are tabulated.

Radio values come from the modem (AT+CPSI? / AT+CSQ, read about every 25 sends):
RSRP is signal power (dBm, higher is better; -100 or below is weak), SINR is signal to
noise (dB, higher is better), RSRQ is quality (dB). Frames/s is capped by the UNO Q's own
Bridge, not the radio (EcoCapture-Web/LTE_PODIUM.md 2026-10-19), so it is not expected to move.
"""
import json
import os
import statistics
import sys
import time
import urllib.request

API = 'http://127.0.0.1:8080/api/podium'
OUT = os.path.expanduser('~/antenna_compare')


def call(path='', body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(API + path, data, {'Content-Type': 'application/json', 'X-EcoCapture': '1'})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def summary(values):
    return None if not values else {'median': statistics.median(values), 'min': min(values), 'max': max(values), 'n': len(values)}


def run(label, seconds):
    before = call()['config']['link']
    if before == 'lte':
        # Restart the LTE session so the connect phases are measured from modem power-on.
        call(body={'link': 'wifi'}); time.sleep(5)
    t0 = time.monotonic()
    call(body={'link': 'lte'})
    start_frames = None   # frame count once the LTE session is up; Wi-Fi frames before it do not count
    print(f'[{label}] LTE送信に切り替えました。接続を待っています（最長5分）', flush=True)
    first = None; radios = {}; rates = []; last = None; status = {}
    try:
        while True:
            time.sleep(2)
            status = call()['status']
            now = time.monotonic()
            radio = status.get('radio') or {}
            # Before registration CPSI reports zeros and CSQ 99 (unknown); those are not readings.
            if radio.get('at') and radio['at'] not in radios and radio.get('csq') != 99 and radio.get('rsrp', -1) < 0:
                radios[radio['at']] = radio
                print(f"  {now - t0:5.0f}s  RSRP {radio.get('rsrp')} dBm  SINR {radio.get('sinr')} dB"
                      f"  RSRQ {radio.get('rsrq')} dB  CSQ {radio.get('csq')}  {radio.get('band', '')}", flush=True)
            if first is None:
                if now - t0 > 300:
                    print('  5分以内に送信が始まりませんでした', flush=True); break
                if status.get('active_link') != 'lte': continue
                if start_frames is None: start_frames = status.get('frames', 0); start_reconnects = status.get('reconnects', 0)
                if status.get('frames', 0) > start_frames:
                    first = now - t0; last = (now, status['frames'])
                    print(f'  最初の送信まで {first:.0f} 秒  段階ごと {status.get("phases")}', flush=True)
                continue
            rates.append((status['frames'] - last[1]) / (now - last[0])); last = (now, status['frames'])
            if now - t0 - first >= seconds: break
    finally:
        call(body={'link': before})
    pick = lambda k: [r[k] for r in radios.values() if isinstance(r.get(k), int)]
    result = {
        'label': label, 'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'seconds': seconds,
        'first_frame_s': None if first is None else round(first, 1), 'phases': status.get('phases'),
        'band': next((r['band'] for r in radios.values() if r.get('band')), None),
        **{k: summary(pick(k)) for k in ('rsrp', 'sinr', 'rsrq', 'rssi', 'csq')},
        'frames_per_s': None if not rates else round(statistics.mean(rates), 2),
        'reconnects': None if first is None else status.get('reconnects', 0) - start_reconnects,
        'last_failure': status.get('last_failure_reason'),
        'cpsi': [r.get('cpsi') for r in radios.values()],
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'results.jsonl'), 'a') as f:
        f.write(json.dumps(result, ensure_ascii=False) + '\n')
    return result


def table():
    rows = [json.loads(l) for l in open(os.path.join(OUT, 'results.jsonl'))]
    med = lambda r, k: '-' if not r.get(k) else f"{r[k]['median']:g} ({r[k]['min']:g}〜{r[k]['max']:g})"
    print('\nラベル  時刻                 接続までの秒  RSRP中央値(範囲)    SINR中央値(範囲)  RSRQ中央値   CSQ     件数/秒  再接続')
    for r in rows:
        print(f"{r['label']:<7} {r['time']}  {r['first_frame_s'] or '-':>8}     {med(r, 'rsrp'):<18} {med(r, 'sinr'):<16} "
              f"{med(r, 'rsrq'):<11} {med(r, 'csq'):<7} {r['frames_per_s'] or '-':>6}  {r['reconnects']}")


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    run(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 180)
    table()
