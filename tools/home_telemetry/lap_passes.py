#!/usr/bin/env python3
"""List, check and remove the line passes the bridge wrote to VictoriaMetrics (ecorun_lap_at).

Each pass is its own series ecorun_lap_at{room,lap,kind,race,seconds,avg} with one sample at the
pass time (live_bridge.py). A cluster reconnect replays the peer's history into a room's open
file, and before Bridge.only_new (2026-10-25) the bridge counted those old rows as laps. Passes
made that way show up as:
  overlap  a pass of race R after a later start of another race (one vehicle runs one race)
  repeat   the same lap time three or more laps in a row (a stuck value, e.g. 381.7 s each lap)
Flags only point at what to look at; deciding which passes are false is left to a person.

  python3 lap_passes.py list --room majesta --since 2026-10-24T15:00:00Z
  python3 lap_passes.py delete --room majesta --since 2026-10-24T15:00:00Z --until 2026-10-25T00:00:00Z

delete first saves the passes it removes (VictoriaMetrics export lines) to --backup, which
`curl --data-binary @<file> http://127.0.0.1:8428/api/v1/import` puts back.
"""
import argparse
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request

JST = dt.timezone(dt.timedelta(hours=9))


def stamp(text):
    return int(dt.datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp() * 1000)


def export(vm, room):
    """Every pass of the room, each with all the sample times of its series."""
    body = urllib.parse.urlencode({'match[]': f'ecorun_lap_at{{room="{room}"}}', 'start': '0'}).encode()
    with urllib.request.urlopen(f'{vm}/api/v1/export', body, timeout=60) as r:
        lines = [l for l in r.read().decode().splitlines() if l.strip()]
    passes = []
    for line in lines:
        series = json.loads(line)
        for t in series['timestamps']:
            passes.append({'t': t, 'metric': series['metric'], 'line': line, 'all': series['timestamps']})
    return sorted(passes, key=lambda p: p['t'])


def flag(passes):
    """Mark overlap / repeat (see the module docstring)."""
    race = None
    for p in passes:
        m = p['metric']
        p['flags'] = []
        if m.get('kind') == 'start':
            race = m.get('race')
        elif race is not None and m.get('race') != race:
            p['flags'].append('overlap')
    by_race = {}
    for p in passes:
        if p['metric'].get('kind') != 'start':
            by_race.setdefault(p['metric'].get('race'), []).append(p)
    for laps in by_race.values():
        run = []
        for p in laps + [None]:
            if p is not None and run and p['metric'].get('seconds') == run[-1]['metric'].get('seconds'):
                run.append(p)
                continue
            if len(run) >= 3:
                for q in run:
                    q['flags'].append('repeat')
            run = [p] if p is not None else []
    return passes


def show(passes):
    for p in passes:
        m = p['metric']
        at = dt.datetime.fromtimestamp(p['t'] / 1000, JST).strftime('%m/%d %H:%M:%S')
        print(f"{at}  race {m.get('race'):>5}  lap {m.get('lap'):>2}  {m.get('kind'):<7}"
              f"  {m.get('seconds'):>6} s  avg {m.get('avg'):>5}  {' '.join(p['flags'])}")
    print(f'{len(passes)} passes, {sum(1 for p in passes if p["flags"])} flagged')


def delete(vm, passes, backup, start, end):
    # delete_series removes a whole series; one that also has a sample outside the window
    # (same labels on another day) is left alone.
    shared = [p for p in passes if any(not start <= t < end for t in p['all'])]
    for p in shared:
        print(f"skipped (series also has samples outside the window): {p['metric']}")
    passes = [p for p in passes if p not in shared]
    with open(backup, 'a', encoding='utf-8') as f:
        for line in dict.fromkeys(p['line'] for p in passes):
            f.write(line + '\n')
    for p in passes:
        labels = ','.join(f'{k}="{v}"' for k, v in sorted(p['metric'].items()) if k != '__name__')
        body = urllib.parse.urlencode({'match[]': f'ecorun_lap_at{{{labels}}}'}).encode()
        urllib.request.urlopen(f'{vm}/api/v1/admin/tsdb/delete_series', body, timeout=60).read()
    print(f'deleted {len(passes)} passes; saved to {backup}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=('list', 'delete'))
    ap.add_argument('--room', required=True)
    ap.add_argument('--since', required=True, help='RFC 3339, e.g. 2026-10-24T15:00:00Z')
    ap.add_argument('--until')
    ap.add_argument('--race', action='append', help='only these race labels (repeatable)')
    ap.add_argument('--vm', default='http://127.0.0.1:8428')
    ap.add_argument('--backup', default='lap_passes_deleted.jsonl')
    args = ap.parse_args()
    start = stamp(args.since)
    end = stamp(args.until) if args.until else float('inf')
    passes = [p for p in flag(export(args.vm, args.room)) if start <= p['t'] < end]
    if args.race:
        passes = [p for p in passes if p['metric'].get('race') in args.race]
    show(passes)
    if args.action == 'delete':
        if args.until is None:
            sys.exit('delete needs --until')
        delete(args.vm, passes, args.backup, start, end)


if __name__ == '__main__':
    main()
