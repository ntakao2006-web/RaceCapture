"""Replay a decoded drive log (drive_logs/.../decoded/EL*.csv) to ecorun-logger-server
as if a logger were driving now. For testing storage and the live view without the car.

Sends the same messages as EcoCapture-Web/podium.py in relay mode:
hello (audio_formats: []), podium.meta, then podium.samples in 5-row batches at 10 Hz.
`Utc` is rewritten to "now" so the live dashboard shows it as current.

  python3 replay_sender.py EL000016.csv ws://127.0.0.1:3000/ws/audio/home-test [--speed 2]

Needs the `websockets` package (Debian: python3-websockets).
"""
import argparse
import asyncio
import csv
import json
import time

import websockets

CHANNELS = [  # (csv column, Podium name, unit, min, max, prec)
    (None, 'Interval', 'ms', 0, 0, 0),
    (None, 'Utc', 'ms', 0, 0, 0),
    ('Lat', 'Latitude', 'deg', -90, 90, 6),
    ('Lon', 'Longitude', 'deg', -180, 180, 6),
    ('GPSSpeed', 'Speed', 'km/h', 0, 200, 1),
    ('Altitude', 'Altitude', 'm', -100, 3000, 1),
    ('LongAccel', 'LongAccel', 'G', -2, 2, 2),
    ('LatAccel', 'LatAccel', 'G', -2, 2, 2),
    ('GPSSats', 'GPSSats', '', 0, 50, 0),
]


def rows_10hz(path):
    """Yield (mcu_ms, {column: float}) every 100 ms, carrying GNSS columns forward."""
    last = {}
    next_ms = None
    with open(path, newline='') as f:
        for rec in csv.DictReader(f):
            for col, *_ in CHANNELS:
                if col and rec.get(col):
                    last[col] = float(rec[col])
            ms = int(rec['mcu_ms'])
            if next_ms is None:
                next_ms = ms
            if ms >= next_ms and 'Lat' in last:
                yield ms, dict(last)
                next_ms = ms + 100


def packed_row(interval_ms, utc_ms, values):
    out, mask = [], 0
    for i, (col, name, _u, _lo, _hi, prec) in enumerate(CHANNELS):
        v = interval_ms if name == 'Interval' else utc_ms if name == 'Utc' else values.get(col)
        if v is not None:
            out.append(int(round(v)) if prec == 0 else round(v, prec))
            mask |= 1 << i
    return out + [mask]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csv')
    ap.add_argument('url')
    ap.add_argument('--speed', type=float, default=1.0, help='playback speed factor')
    args = ap.parse_args()

    async with websockets.connect(args.url) as ws:
        await ws.send(json.dumps({'type': 'hello', 'protocol': 2, 'client_id': 'replay', 'audio_formats': []}))
        meta = [{'nm': n, 'ut': u, 'sr': 10, 'min': lo, 'max': hi, 'prec': p} for _c, n, u, lo, hi, p in CHANNELS]
        await ws.send(json.dumps({'type': 'podium.meta', 'meta': meta}))

        async def drain():
            async for msg in ws:
                if isinstance(msg, str) and '"error"' in msg and 'podium_not_configured' not in msg:
                    print('server:', msg)
        reader = asyncio.create_task(drain())

        batch, first_ms, t0, sent = [], None, time.time(), 0
        for ms, values in rows_10hz(args.csv):
            first_ms = first_ms if first_ms is not None else ms
            elapsed = (ms - first_ms) / 1000 / args.speed
            await asyncio.sleep(max(0.0, t0 + elapsed - time.time()))
            batch.append(packed_row(ms - first_ms, int(time.time() * 1000), values))
            if len(batch) == 5:
                await ws.send(json.dumps({'type': 'podium.samples', 'samples': batch}))
                sent += len(batch)
                batch = []
        if batch:
            await ws.send(json.dumps({'type': 'podium.samples', 'samples': batch}))
            sent += len(batch)
        reader.cancel()
        print(f'sent {sent} rows')


if __name__ == '__main__':
    asyncio.run(main())
