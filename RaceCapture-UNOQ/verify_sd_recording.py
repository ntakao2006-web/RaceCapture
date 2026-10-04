"""Run on UNO Q after stopping: read back one SD log and verify every block."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('index', type=int)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, '/home/arduino/EcoCapture-Web')
from sd_decode import records

base = 'http://127.0.0.1:8080'
with urllib.request.urlopen(base + '/api/status', timeout=15) as response:
    status = json.load(response)
if status['logging']['active'] or status['hardware'].get('sd_logging'):
    raise SystemExit('FAIL: stop recording before SD readback')
with urllib.request.urlopen(base + f'/api/sd/logs/{args.index}/download', timeout=180) as response:
    expected_size = int(response.headers['Content-Length'])
    with args.output.open('xb') as target:
        while block := response.read(16384):
            target.write(block)
if args.output.stat().st_size != expected_size:
    raise SystemExit('FAIL: incomplete download')
counts = Counter()
first = last = None
with args.output.open('rb') as stream:
    for kind, stamp, payload in records(stream):
        counts[kind] += 1
        if first is None:
            first = stamp
        last = stamp
if not counts[3]:
    raise SystemExit('FAIL: no raw CAN records')
print(json.dumps({'result': 'PASS', 'file': str(args.output),
                  'bytes': expected_size, 'blocks': expected_size // 512,
                  'crc_and_block_sequence': 'all_valid', 'record_counts': dict(counts),
                  'first_mcu_ms': first, 'last_mcu_ms': last,
                  'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}), flush=True)
