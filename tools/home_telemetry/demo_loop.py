"""Loop a recorded race into the bridge as if it were being run now (demo, 2026-10-30).

For the school festival: anyone opening the dashboard sees the 2026-10-25 Motegi race being
driven, over and over. The race as the server stored it that day (its JSON Lines files) is cut
to a time window and written, at its own pace, into a new session file under
<dir>/<room>/, the layout ecorun-logger-server uses. live_bridge.py follows that directory, so
VictoriaMetrics, Grafana, the map and the clock page show it like a live run; the server itself
never reads the directory, so nothing reaches the server, its database or the cluster peer.

  python3 demo_loop.py --dir ~/ecorun-logger-server/data/telemetry --room demo-majesta \\
      --from 2026-10-25T12:15:30+09:00 --to 2026-10-25T12:56:00+09:00 majesta/2026*.jsonl

What changes from the stored rows:
  - `Utc` and `recv_ms` are moved by the same amount, so the race runs now (the logger's
    delays to the server stay as they were);
  - `SourceUtc` is added: the row's original time (ms). A page playing the race's video
    beside the dashboard follows it to stay in step (the bridge sends it like any channel).
Rows outside the window, and rows not newer than the last one (history the server replayed
into a file when the cluster peer reconnected), are left out. The source files' sessions are
joined into one stream; the gaps between them (the logger reconnecting over LTE) stay.

Each loop starts right after the last one. A new file is started at a loop's start once the
current one is --rotate-min old, and files older than --keep-min are deleted (the eMMC is
small; a race the length of majesta's writes ~6 MB an hour).
"""
import argparse
import datetime
import glob
import json
import math
import os
import time

UTC_MIN_MS = 1_500_000_000_000   # as live_bridge.py: Utc=0 / uptime-like values are not times


def decode_row(names, row):
    """[(name, value)] for the channels present in a packed row (live_bridge.decode_row)."""
    n_masks = (len(names) + 31) // 32
    if n_masks == 0 or len(row) < n_masks:
        return None
    values, masks = row[:-n_masks], row[-n_masks:]
    out, k = [], 0
    for i, name in enumerate(names):
        if int(masks[i // 32]) >> (i % 32) & 1:
            if k >= len(values):
                return None
            out.append((name, values[k]))
            k += 1
    return out


def encode_row(names, values):
    """Pack {name: value} in `names` order followed by the bitmask words (podium.py Encoder.row)."""
    out, masks = [], [0] * ((len(names) + 31) // 32)
    for i, name in enumerate(names):
        if name in values:
            out.append(values[name])
            masks[i // 32] |= 1 << (i % 32)
    return out + masks


def load(paths, start_ms, end_ms):
    """(meta, [(recv_ms, [(src_ms, {name: value})])]) for the rows inside the window.
    The meta is the first file's; a file with other channels is refused (one stream)."""
    meta, batches, newest = None, [], 0
    for path in paths:
        names = []
        with open(path, 'rb') as f:
            for raw in f:
                try:
                    entry = json.loads(raw)
                except ValueError:
                    continue
                if 'meta' in entry:
                    names = [m.get('nm', '') for m in entry['meta']]
                    if meta is None:
                        meta = entry['meta']
                    elif names != [m.get('nm', '') for m in meta]:
                        raise SystemExit(f'{path}: channels differ from the first file')
                    continue
                recv_ms = int(entry.get('recv_ms', 0))
                rows = []
                for row in entry.get('samples', []):
                    pairs = decode_row(names, row) if names else None
                    if not pairs:
                        continue
                    values = dict(pairs)
                    utc = values.get('Utc')
                    src = int(utc) if isinstance(utc, (int, float)) and utc > UTC_MIN_MS else recv_ms
                    if start_ms <= src <= end_ms and src > newest:
                        rows.append((src, values))
                        newest = src
                if rows:
                    batches.append((recv_ms, rows))
    if meta is None or not batches:
        raise SystemExit('no rows inside the window')
    return meta, batches


class Writer:
    """The room's current session file, named like the server's (<YYYYMMDD-HHMMSS>Z.jsonl)."""

    def __init__(self, room_dir, meta, rotate_s, keep_s):
        self.room_dir, self.meta = room_dir, meta
        self.rotate_s, self.keep_s = rotate_s, keep_s
        self.file, self.opened = None, 0.0
        os.makedirs(room_dir, exist_ok=True)

    def loop_start(self, recv_ms):
        if self.file is None or time.time() - self.opened >= self.rotate_s:
            if self.file:
                self.file.close()
            stamp = datetime.datetime.fromtimestamp(recv_ms / 1000, datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')
            path, n = os.path.join(self.room_dir, f'{stamp}Z.jsonl'), 1
            while os.path.exists(path):
                path, n = os.path.join(self.room_dir, f'{stamp}Z-{n}.jsonl'), n + 1
            self.file, self.opened = open(path, 'a', encoding='utf-8'), time.time()
            self.write({'recv_ms': recv_ms, 'meta': self.meta})
            print(f'writing {path}', flush=True)
        self.clean()

    def clean(self):
        cutoff = time.time() - self.keep_s
        for path in glob.glob(os.path.join(self.room_dir, '*.jsonl')):
            if path != self.file.name and os.path.getmtime(path) < cutoff:
                os.remove(path)
                print(f'deleted {path}', flush=True)

    def write(self, entry):
        # One whole line per write, so the bridge never reads half a row
        self.file.write(json.dumps(entry, separators=(',', ':')) + '\n')
        self.file.flush()


def play(writer, meta, batches, names, speed=1.0):
    """One pass of the race, starting now. Returns when its last batch is written.
    `speed` only hurries the writing (tests); the times written are the real-time ones."""
    first_recv = batches[0][0]
    t0 = time.time() * 1000
    shift = round(t0 - first_recv)
    writer.loop_start(first_recv + shift)
    for recv_ms, rows in batches:
        due = (t0 + (recv_ms - first_recv) / speed) / 1000
        wait = due - time.time()
        if wait > 0:
            time.sleep(wait)
        samples = []
        for src, values in rows:
            v = dict(values)
            if isinstance(v.get('Utc'), (int, float)) and v['Utc'] > UTC_MIN_MS:
                v['Utc'] = int(v['Utc']) + shift
            v['SourceUtc'] = src
            samples.append(encode_row(names, v))
        writer.write({'recv_ms': recv_ms + shift, 'samples': samples})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+', help="the server's JSON Lines files of the race, in session order")
    ap.add_argument('--dir', required=True, help='the directory live_bridge.py follows (--dir there)')
    ap.add_argument('--room', required=True, help='room to write as (keep it apart from real rooms, e.g. demo-majesta)')
    ap.add_argument('--from', dest='start', required=True, type=datetime.datetime.fromisoformat,
                    help='window start, ISO 8601 with offset')
    ap.add_argument('--to', dest='end', required=True, type=datetime.datetime.fromisoformat, help='window end')
    ap.add_argument('--pause', type=float, default=5.0, help='seconds between loops')
    ap.add_argument('--rotate-min', type=float, default=120.0)
    ap.add_argument('--keep-min', type=float, default=240.0)
    ap.add_argument('--loops', type=int, default=0, help='stop after this many (0: forever)')
    ap.add_argument('--speed', type=float, default=1.0, help=argparse.SUPPRESS)   # tests only
    args = ap.parse_args()

    meta, batches = load(sorted(args.files), args.start.timestamp() * 1000, args.end.timestamp() * 1000)
    names = [m.get('nm', '') for m in meta]
    if 'SourceUtc' not in names:
        meta = meta + [{'nm': 'SourceUtc', 'ut': 'ms', 'sr': 10, 'min': 0, 'max': 0, 'prec': 0}]
        names.append('SourceUtc')
    rows = sum(len(r) for _, r in batches)
    span = (batches[-1][0] - batches[0][0]) / 1000
    print(f'{args.room}: {rows} rows, {math.floor(span / 60)} min {span % 60:.0f} s a loop', flush=True)
    writer = Writer(os.path.join(args.dir, args.room), meta, args.rotate_min * 60, args.keep_min * 60)
    n = 0
    while True:
        play(writer, meta, batches, names, args.speed)
        n += 1
        print(f'{args.room}: loop {n} done', flush=True)
        if args.loops and n >= args.loops:
            break
        time.sleep(args.pause / args.speed)


if __name__ == '__main__':
    main()
