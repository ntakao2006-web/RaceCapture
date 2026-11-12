"""Freeze a stored race at one moment, moved to now, to look at the pit pages on a PC (2026-10-25, ER-13).

Writes <out_dir>/<room>/<name>.jsonl holding the race file's rows up to <race_s> seconds after
<start_utc_ms>, with every time (Utc, recv_ms) shifted so that moment is now. A live_bridge.py
started with --dir <out_dir> then shows that moment as if the car were on the course: the clock
page runs on from there. Nothing is sent anywhere; the stored race is only read.

  python -I snapshot.py <race.jsonl> <start_utc_ms> <race_s> <out_dir> <room>
"""
import json
import os
import sys
import time


def main():
    path, start, race_s, out_dir, room = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5]
    until = start + race_s * 1000
    shift = int(time.time() * 1000 - until)
    os.makedirs(os.path.join(out_dir, room), exist_ok=True)
    names, kept = None, 0
    with open(path, encoding='utf-8') as src, \
            open(os.path.join(out_dir, room, f'snapshot-{int(race_s)}.jsonl'), 'w', encoding='utf-8', newline='\n') as out:
        for line in src:
            entry = json.loads(line)
            if 'meta' in entry:
                names = [m['nm'] for m in entry['meta']]
                out.write(line if line.endswith('\n') else line + '\n')
                continue
            n = (len(names) + 31) // 32
            utc_bit = names.index('Utc')
            rows = []
            for row in entry.get('samples', []):
                masks = row[-n:]
                if not int(masks[utc_bit // 32]) >> (utc_bit % 32) & 1:
                    continue
                # Utc's place among the packed values: the set bits before it.
                at = sum(1 for i in range(utc_bit) if int(masks[i // 32]) >> (i % 32) & 1)
                if row[at] > until:
                    continue
                row = list(row)
                row[at] += shift
                rows.append(row)
            if rows:
                entry['samples'] = rows
                entry['recv_ms'] = entry.get('recv_ms', 0) + shift
                out.write(json.dumps(entry, separators=(',', ':')) + '\n')
                kept += len(rows)
    print(f'{room}: {kept} rows up to {race_s:.0f} s into the race, shifted {shift / 3_600_000:.1f} h')


if __name__ == '__main__':
    main()
