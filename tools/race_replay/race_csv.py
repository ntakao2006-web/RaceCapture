"""Turn a stored race (the server's JSON Lines, drive_logs/) into CSV for replay tests (2026-10-25, ER-13).

  speed: t_s,speed_kmh once a second from the start (no position), small enough to commit
         as a test fixture: android-logger PaceTest replays the 2026-10-25 Super Cub race.
  fixes: utc_ms,lat,lon,acc_m,speed_kmh for each new fix, for the LapTimer replay test, which
         runs only where drive_logs/ is (positions stay out of the repository).

  python -I race_csv.py speed <race.jsonl> <start_utc_ms> <end_utc_ms> <out.csv>
  python -I race_csv.py fixes <race.jsonl> <from_utc_ms> <to_utc_ms> <out.csv>
"""
import json
import sys


def rows(path):
    names = None
    for line in open(path, encoding='utf-8'):
        entry = json.loads(line)
        if 'meta' in entry:
            names = [m['nm'] for m in entry['meta']]
        for row in entry.get('samples', []):
            n = (len(names) + 31) // 32
            values, masks = row[:-n], row[-n:]
            out, k = {}, 0
            for i, name in enumerate(names):
                if int(masks[i // 32]) >> (i % 32) & 1:
                    out[name] = values[k]
                    k += 1
            yield out


def main():
    mode, path, lo, hi, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    by_t = {}
    for r in rows(path):
        t = r.get('Utc')
        if t is not None and lo <= t <= hi and r.get('Speed') is not None:
            by_t[int(t)] = r
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        if mode == 'speed':
            f.write('t_s,speed_kmh\n')
            ts = sorted(by_t)
            for s in range((hi - lo) // 1000 + 1):
                at = lo + s * 1000
                near = min(ts, key=lambda t: abs(t - at))   # rows are 0.1 s apart
                f.write(f'{s},{by_t[near]["Speed"]}\n')
        else:
            f.write('utc_ms,lat,lon,acc_m,speed_kmh\n')
            prev = None
            for t in sorted(by_t):
                r = by_t[t]
                fix = (r.get('Latitude'), r.get('Longitude'), r.get('GPSAcc'), r.get('Speed'))
                if fix != prev and None not in fix[:2]:
                    f.write(f'{t},{fix[0]},{fix[1]},{fix[2] if fix[2] is not None else ""},{fix[3]}\n')
                prev = fix


if __name__ == '__main__':
    main()
