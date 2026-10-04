"""Bounded live Podium and acquisition evidence; never print private config."""
import json
import time
import urllib.request

def status():
    with urllib.request.urlopen('http://127.0.0.1:8080/api/status', timeout=10) as response:
        return json.load(response)

deadline = time.monotonic() + 200
while True:
    current = status()
    print(json.dumps({'state': current['podium']['state'],
                      'connected': current['connected']}), flush=True)
    if current['podium']['state'] == 'streaming':
        break
    if time.monotonic() > deadline:
        raise SystemExit('FAIL: streaming timeout')
    time.sleep(5)
first = current
started = time.monotonic()
for _ in range(6):
    time.sleep(5)
    current = status()
    print(json.dumps({key: current.get(key) for key in
                     ('connected', 'receive_hz', 'bridge_errors', 'mcu_resets', 'podium', 'logging')}), flush=True)
    assert current['connected'] and current['podium']['state'] == 'streaming'
elapsed = time.monotonic() - started
sent = current['podium']['frames'] - first['podium']['frames']
assert sent > 0
assert current['bridge_errors'] == first['bridge_errors']
print(json.dumps({'result': 'PASS', 'elapsed_s': elapsed, 'frames_sent': sent,
                  'observed_send_hz': sent / elapsed,
                  'payload_bytes': current['podium']['bytes'] - first['podium']['bytes']}), flush=True)
