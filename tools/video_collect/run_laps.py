"""走行1本の、周ごとの表（2026-11-13、SP-5-1、`SPEC.md` 4章 A-1・7-5）。

走行記録（本体のCSV）を頭から最後まで読み、周回数（LapCount）が増えた行を周の終わりとして、周ごとに
  タイム・ベストとの差・セクターのタイム・最高速・警告の印（油温・水温がしきい値を超えた）・動画の有無
を出す。**油温・水温の数字は出さない**（周ごとの1つの数字では意味が伝わらないため。警告が出た周に印だけ。SPEC.md 7-5）。

    table = laps_of(Path(走行記録), chapters, warn={'OilTemp': 120, 'WaterTemp': 110})
    table = cached(root, run, warn)      # 結果を drive_logs/runs_cache/<走行>.laps.json に覚える（記録が変わったら読み直す）

走行記録は大きい（120分で約500 MB）ので、初めて開くときは数十秒かかる。2回目からは覚えた結果を返す。
タイムは本体が数えたもの（LapTime、単位は分）をそのまま使う。公式の計測ではない。
"""
import csv
import json
from pathlib import Path

import run_index

CACHE_DIR = 'runs_cache'
VERSION = 3   # 2：周の時刻を測位の時計で直す　3：止まっていた秒（stop_s）を足した
NEEDED = ('host_utc', 'gnss_utc', 'LapCount', 'LapTime', 'LastSector', 'SectorTime', 'Speed', 'GPSSpeed', 'OilTemp', 'WaterTemp')
WARN_LABEL = {'OilTemp': '油温', 'WaterTemp': '水温'}
STOP_KMH = 5.0        # これ未満を「止まっていた」と数える（レポートの下書きでピットの周を見分けるのに使う。report_draft.py）
WARN_HOLD_S = 5.0     # この長さ続いたら警告の印（車載画面の hold_on_s と同じ。キーを切るときの一瞬の跳ねを拾わない）


def number(text):
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if value == value else None   # NaN は無いものとして扱う


def laps_of(path, chapters=(), warn=None, progress=None):
    """走行記録を読んで {'laps': [...], 'best': 周の番号, 'rows': 読んだ行数} を返す。
    laps の1つ：{'lap', 'time_s', 'start', 'end', 'sectors': [秒...], 'vmax', 'stop_s', 'warn': ['油温', ...], 'video': 'all'|'part'|'none'}
    stop_s は、その周のうち STOP_KMH 未満だった秒（ピットで止まった周の目安）"""
    warn = warn or {}
    laps, rows = [], 0
    count = None          # いまの LapCount
    lap_start = None      # いまの周が始まった時刻（前の周の終わり）
    vmax, sectors, over, warned = None, {}, {}, set()
    last_sector_key = None
    stop_s, last_t = 0.0, None
    clock = []            # 直近の (本体の時計, 測位の時計)。周の終わりの時刻を測位の時計で直すのに使う
    with open(path, encoding='utf-8', errors='replace', newline='') as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return {'laps': [], 'best': None, 'rows': 0}
        col = {name: header.index(name) for name in NEEDED if name in header}
        width = len(header)
        while True:
            try:
                r = next(reader)
            except StopIteration:
                break
            except csv.Error:
                continue            # 壊れた行（電源断の書きかけなど）は飛ばす
            if len(r) != width:
                continue
            rows += 1
            if progress and rows % 50000 == 0:
                progress(f.tell())
            t = run_index.parse_utc(r[col['host_utc']]) if 'host_utc' in col else None
            if t is not None and 'gnss_utc' in col and r[col['gnss_utc']]:
                clock.append((t, run_index.parse_utc(r[col['gnss_utc']])))
                if len(clock) > 800:
                    del clock[:400]
            get = lambda name: number(r[col[name]]) if name in col else None  # noqa: E731
            speed = get('Speed')
            if speed is None:
                speed = get('GPSSpeed')
            if speed is not None and (vmax is None or speed > vmax):
                vmax = speed
            if t is not None:
                if speed is not None and speed < STOP_KMH and last_t is not None and 0 < t - last_t <= 1.0:
                    stop_s += t - last_t
                last_t = t
            for name, limit in warn.items():   # しきい値以上が WARN_HOLD_S 続いたら、その周に印
                value = get(name)
                if value is not None and value >= limit and t is not None:
                    over.setdefault(name, t)
                    if t - over[name] >= WARN_HOLD_S:
                        warned.add(WARN_LABEL.get(name, name))
                else:
                    over.pop(name, None)
            sector, sector_time = get('LastSector'), get('SectorTime')
            if sector is not None and sector_time is not None and (sector, sector_time) != last_sector_key:
                last_sector_key = (sector, sector_time)
                sectors[int(sector)] = round(sector_time * 60, 3)
            now = get('LapCount')
            if now is None:
                continue
            if count is not None and now > count:      # 周が終わった
                time_min = get('LapTime')
                time_s = None if time_min is None else round(time_min * 60, 3)
                # 本体の時計は測位で合うまでずれていることがあるので、直近の差で直す（run_index.clock_correction）
                corr = run_index.clock_correction(clock[-400:]) or 0.0
                end = None if t is None else t - corr
                start = None if end is None or time_s is None else end - time_s
                laps.append({'lap': int(now), 'time_s': time_s, 'start': None if start is None else round(start, 1),
                             'end': None if end is None else round(end, 1),
                             'sectors': [sectors.get(k) for k in sorted(sectors)], 'vmax': None if vmax is None else round(vmax),
                             'stop_s': round(stop_s, 1),
                             'warn': sorted(warned)})
                lap_start, vmax, sectors, warned, stop_s = t, None, {}, set(), 0.0
            elif count is not None and now < count:    # 途中でラップを0周に戻した：それまでの周は残し、数え直す
                vmax, sectors, warned, stop_s = None, {}, set(), 0.0
            count = now
    for lap in laps:
        if lap['start'] is None or lap['end'] is None or not chapters:
            lap['video'] = 'none'
            continue
        covered, _ = run_index.cover(lap['start'], lap['end'], chapters)
        lap['video'] = 'none' if covered <= 0 else 'all' if covered >= (lap['end'] - lap['start']) - 1 else 'part'
    timed = [lap for lap in laps if lap['time_s']]
    best = min(timed, key=lambda lap: lap['time_s'])['lap'] if timed else None
    return {'laps': laps, 'best': best, 'rows': rows}


def cached(root, run, warn=None, progress=None):
    """走行（run_index の1つ）の周の表。覚えた結果があればそれを返す"""
    root = Path(root)
    log = root / run['log']
    stamp = run_index.stamp(log)
    key = {'version': VERSION, 'stamp': stamp, 'warn': warn or {}, 'videos': [[c['start'], c['end']] for c in run.get('videos', [])]}
    path = root / CACHE_DIR / (run['id'] + '.laps.json')
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
        if saved.get('key') == key:
            return saved['table']
    except (OSError, ValueError, AttributeError):
        pass
    table = laps_of(log, run.get('videos', []), warn, progress)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps({'key': key, 'table': table}, ensure_ascii=False), encoding='utf-8')
        temp.replace(path)
    except OSError:
        pass
    return table
