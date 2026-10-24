#!/usr/bin/env python3
"""Check that telemetry replicates between the primary (senpai) and secondary (5B) servers.

Both servers expose GET /api/rooms/<room>/telemetry?since=&until= (received_at, UTC,
at most 5000 events per call). Each event_id starts with the node that created it
(maruo-primary / takao-secondary); this counts, per 10 minutes (JST), how many events
one node created and how many of them the other server also holds.

  python compare_replication.py majesta --minutes 30
"""
import argparse
import collections
import datetime as dt
import json
import sys
import urllib.request

SERVERS = {'maruo-primary': 'https://ecorun.marusoftware.net',
           'takao-secondary': 'https://rock-5b.tail5a9705.ts.net'}
LABEL = {'maruo-primary': '先輩', 'takao-secondary': '5B'}


def fetch(host, room, start, end, step=dt.timedelta(minutes=5)):
    events = {}
    t = start
    while t < end:
        n = min(t + step, end)
        url = f'{host}/api/rooms/{room}/telemetry?since={t:%Y-%m-%dT%H:%M:%SZ}&until={n:%Y-%m-%dT%H:%M:%SZ}'
        rows = json.load(urllib.request.urlopen(url, timeout=60))
        if len(rows) >= 5000:
            print(f'warning: {host} {t} hit the 5000-event limit', file=sys.stderr)
        for e in rows:
            events[e['event_id']] = e
        t = n
    return events


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('room')
    ap.add_argument('--minutes', type=int, default=30, help='how far back to look')
    args = ap.parse_args()
    end = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    start = end - dt.timedelta(minutes=args.minutes)
    held = {node: fetch(host, args.room, start, end) for node, host in SERVERS.items()}
    for node, other in (('maruo-primary', 'takao-secondary'), ('takao-secondary', 'maruo-primary')):
        made = collections.Counter()
        arrived = collections.Counter()
        for event_id, e in held[node].items():
            if not event_id.startswith(node + ':'):
                continue
            jst = dt.datetime.fromisoformat(e['received_at']) + dt.timedelta(hours=9)
            key = jst.strftime('%H:%M')[:4] + '0'
            made[key] += 1
            arrived[key] += event_id in held[other]
        print(f'{LABEL[node]} → {LABEL[other]}（{LABEL[node]}で受けた分のうち、{LABEL[other]}にもある数）')
        if not made:
            print('  この時間に受けたデータなし')
        for key in sorted(made):
            print(f'  {key}〜  {arrived[key]:5d} / {made[key]:5d}')


if __name__ == '__main__':
    main()
