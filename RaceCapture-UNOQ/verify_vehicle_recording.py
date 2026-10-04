"""Run on UNO Q: bounded real-data recording test, retaining the resulting log."""
import argparse
import csv
import json
import time
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--seconds', type=int, default=300)
args = parser.parse_args()
base = 'http://127.0.0.1:8080'

def request(path, post=False):
    req = urllib.request.Request(base + path, data=b'{}' if post else None,
                                 headers={'Content-Type': 'application/json', 'X-EcoCapture': '1'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)

first = request('/api/status')
if not first['connected']:
    raise SystemExit('FAIL: no current MCU samples')
if first['logging']['active']:
    raise SystemExit('FAIL: existing recording is active; do not interfere')
started = request('/api/log/start', True)
print(json.dumps({'started': started}), flush=True)
samples = []
try:
    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline:
        status = request('/api/status')
        hardware = status['hardware']
        snap = {key: status.get(key) for key in ('connected', 'age_ms', 'receive_hz', 'bridge_errors', 'mcu_resets')}
        snap.update({key: hardware.get(key) for key in ('mcu_ms', 'seq', 'can_counts', 'can_overflow', 'sd_logging', 'sd_errors', 'sd_queue_dropped', 'sd_bytes', 'dropped')})
        snap['rows'] = status['logging']['rows']
        samples.append(snap)
        print(json.dumps(snap), flush=True)
        if not status['connected']:
            raise RuntimeError('MCU data stopped during recording')
        time.sleep(5)
finally:
    print(json.dumps({'stopped': request('/api/log/stop', True)}), flush=True)

path = Path('/home/arduino/ecocapture-v2-data/logs') / started['name']
with path.open() as stream:
    rows = list(csv.DictReader(stream))
summary = {'file': str(path), 'rows': len(rows),
           'seq_gaps': sum(int(b['seq']) != int(a['seq']) + 1 for a, b in zip(rows, rows[1:])),
           'rpm_present': sum(row.get('RPM', '') != '' for row in rows),
           'first': samples[0], 'last': samples[-1]}
print(json.dumps({'summary': summary}), flush=True)
if not rows or summary['seq_gaps'] or samples[-1]['bridge_errors'] != samples[0]['bridge_errors']:
    raise SystemExit('FAIL: recording continuity')
for name in ('sd_errors', 'sd_queue_dropped', 'dropped'):
    if samples[-1][name] != samples[0][name]:
        raise SystemExit('FAIL: ' + name)
if samples[-1]['can_overflow'] != samples[0]['can_overflow']:
    raise SystemExit('FAIL: CAN receive loss')
print('PASS: bounded recording test; inspect SD CRC separately', flush=True)
