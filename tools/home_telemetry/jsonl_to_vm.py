"""Follow ecorun-logger-server telemetry files and push them to VictoriaMetrics.

The server stores what loggers send as JSON Lines (one file per room/session):
  {"recv_ms":...,"meta":[{"nm":"Speed",...},...]}
  {"recv_ms":...,"samples":[[v...,mask...],...]}
A row holds only the channels whose bit is set, packed in meta order, followed
by ceil(len(meta)/32) bitmask words (EcoCapture-Web/podium.py Encoder.row).

Each sample becomes one InfluxDB line-protocol point, measurement `ecorun`,
tag `room`, which VictoriaMetrics stores as `ecorun_<Channel>{room="..."}`.
Time is the logger's GNSS `Utc` when present, else the server receive time.

Home test server only (ER-8-4); not part of the team server.

  python3 jsonl_to_vm.py --dir ~/ecorun-logger-server/data/telemetry
  python3 jsonl_to_vm.py --dir ... --replay FILE   # push one whole file and exit
"""
import argparse
import glob
import json
import math
import os
import re
import sys
import time
import urllib.request

UTC_MIN_MS = 1_500_000_000_000  # reject Utc=0 / uptime-like values


def decode_row(names, row):
    """Return {channel: value} for the channels present in a packed row."""
    n_masks = (len(names) + 31) // 32
    if n_masks == 0 or len(row) < n_masks:
        return {}
    values, masks = row[:-n_masks], row[-n_masks:]
    out, k = {}, 0
    for i, name in enumerate(names):
        if int(masks[i // 32]) >> (i % 32) & 1:
            if k >= len(values):
                return {}  # malformed row; drop rather than misalign
            out[name] = values[k]
            k += 1
    return out


def tag_escape(text):
    return re.sub(r'([ ,=\\])', r'\\\1', text)


def to_lines(room, names, entry):
    lines = []
    recv_ms = int(entry.get('recv_ms', 0))
    for row in entry.get('samples', []):
        point = decode_row(names, row)
        utc = point.get('Utc')
        ts_ms = int(utc) if isinstance(utc, (int, float)) and utc > UTC_MIN_MS else recv_ms
        fields = ','.join(f'{re.sub(r"[^A-Za-z0-9_]", "_", k)}={float(v)!r}' for k, v in point.items()
                          if k != 'Utc' and isinstance(v, (int, float)) and math.isfinite(v))
        if fields and ts_ms:
            lines.append(f'ecorun,room={tag_escape(room)} {fields} {ts_ms * 1_000_000}')
    return lines


def push(url, lines):
    if not lines:
        return
    body = ('\n'.join(lines) + '\n').encode()
    req = urllib.request.Request(url, data=body, method='POST')
    with urllib.request.urlopen(req, timeout=5) as resp:
        resp.read()


class Follower:
    """Tail one session file, remembering its channel list."""

    def __init__(self, path, from_start):
        self.path = path
        self.room = os.path.basename(os.path.dirname(path))
        self.names = []
        self.pos = 0
        self.buf = b''
        if not from_start:
            # Joining mid-session: still need the meta line at the top.
            with open(path, 'rb') as f:
                first = f.readline()
                self._handle(first)
                f.seek(0, os.SEEK_END)
                self.pos = f.tell()

    def _handle(self, raw):
        try:
            entry = json.loads(raw)
        except ValueError:
            return []
        if 'meta' in entry:
            self.names = [m.get('nm', '') for m in entry['meta']]
            return []
        return to_lines(self.room, self.names, entry) if self.names else []

    def poll(self):
        with open(self.path, 'rb') as f:
            f.seek(self.pos)
            data = f.read()
            self.pos = f.tell()
        self.buf += data
        *complete, self.buf = self.buf.split(b'\n')
        lines = []
        for raw in complete:
            lines += self._handle(raw)
        return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True, help='ECORUN_TELEMETRY_DIR of the server')
    ap.add_argument('--url', default='http://127.0.0.1:8428/write')
    ap.add_argument('--interval', type=float, default=0.25)
    ap.add_argument('--replay', help='push this one file from the start and exit')
    args = ap.parse_args()

    if args.replay:
        f = Follower(args.replay, from_start=True)
        lines = f.poll()
        for i in range(0, len(lines), 5000):
            push(args.url, lines[i:i + 5000])
        print(f'pushed {len(lines)} points from {args.replay}')
        return

    followers = {}
    started = time.time()
    while True:
        for path in glob.glob(os.path.join(args.dir, '*', '*.jsonl')):
            if path not in followers:
                # Files created after we started are new sessions: read them whole.
                new = os.path.getmtime(path) >= started and os.path.getctime(path) >= started
                followers[path] = Follower(path, from_start=new)
        batch = []
        for f in followers.values():
            try:
                batch += f.poll()
            except OSError:
                pass
        try:
            push(args.url, batch)
        except OSError as error:
            print(f'push failed ({error}); {len(batch)} points dropped', file=sys.stderr)
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
