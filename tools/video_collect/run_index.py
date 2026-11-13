"""回収した走行の索引（2026-11-13、SP-3-6・SP-5-1、`SPEC.md` 4章 C-3・A-1）。

PCに回収したものは、走行記録が drive_logs/<回収した日>/runNN_<時刻>/v2_emmc/、動画が drive_logs/v2_video/<録画の回>/ と
別々の場所にあり、「この走行の動画はどれか」を結ぶものが無かった（時刻で照らし合わせる処理は lap_video の中だけ）。
ここでは**ファイルは動かさず**、走行記録1本（＝本体の電源ONから切るまで）を「走行」として、同じ時刻の動画を結んだ索引を作る。

    index = build(Path('drive_logs'))          # 走行の一覧（新しい順）。前の結果を drive_logs/runs_index.json に覚え、変わった所だけ読む
    python run_index.py [drive_logs]            # 件数だけを表示する（位置や値は出さない）

走行1つの中身：
    id            走行記録のファイルの名前（LOG_<開始のUTC>Z_<番号>）
    day           走った日（日本時間。**回収した日ではない**）
    start・end    走行記録の最初と最後の時刻（UTC、秒。測位の時計で直したもの）。minutes はその長さ
    clock         'gnss'＝時刻を測位の時計で直せた／'host'＝測位していない走行で、本体の時計のまま（ずれていることがある）
    laps          この走行で増えた周回数（走行記録の最後の LapCount − 走り始めの値。線が無い・数えていないときは None）
    course        コースの設定の名前（最後に測位した場所が、tools/setups/courses の線から3 km以内のもの。分からなければ None）
    log           走行記録の場所（drive_logs からの相対）
    videos        その時間に重なる動画の章 [{path, start, end}]（時刻は動画の横の .csv のUTC）
    video         'all'（走行の9割以上に動画がある）・'part'（一部）・'none'
    video_minutes 動画が重なっている長さ
    gaps          動画が無い区間 [(start, end)]（60秒より長いものだけ）

走行記録は数百MB〜1GBを超えるので、頭の1行と末尾だけを読む（全部は読まない）。
"""
import csv
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
INDEX_NAME = 'runs_index.json'
LOG_NAME = re.compile(r'^(LOG|DEMO)_(\d{8}T\d{6})Z_[0-9a-f]+\.csv$')
TAIL_BYTES = 256 << 10      # 末尾から読む量（1行は数百バイト。最後の測位・周回数を拾うのに十分）
COURSE_KM = 3.0
FULL_COVER = 0.9            # 走行のこの割合より多く動画があれば「あり」
GAP_S = 60                  # これより長い「動画が無い区間」を一覧に出す
VERSION = 2   # 2：時刻を測位の時計で直す（本体の時計がずれている走行があるため）


def parse_utc(text):
    """'2026-11-08T03:31:22.772Z' や '+00:00' つきの時刻 → UTCの秒。読めなければ None"""
    try:
        return datetime.fromisoformat(str(text).strip().replace('Z', '+00:00')).astimezone(timezone.utc).timestamp()
    except ValueError:
        return None


def clock_correction(pairs):
    """本体の時計（host_utc）が測位の時計（gnss_utc）からどれだけ進んでいるか（秒）。pairs は (host, gnss) の並び。
    本体は時計用の電池が無く、測位や回線で合うまでずれている（数分〜数時間ずれた走行が実際にある）。
    gnss_utc は秒の切り捨てなので、合っていれば host − gnss の中央値は約+0.5秒（tools/lap_video/lap_video.py と同じ直し方）。
    測位の行が無ければ None（直せない）"""
    diffs = sorted(h - g for h, g in pairs if h is not None and g is not None)
    return diffs[len(diffs) // 2] - 0.5 if diffs else None


def tail_lines(path, size=TAIL_BYTES):
    """ファイルの末尾の行（最初の欠けた1行は捨てる）"""
    with open(path, 'rb') as f:
        f.seek(0, 2)
        end = f.tell()
        f.seek(max(0, end - size))
        data = f.read()
    lines = data.decode('utf-8', 'replace').splitlines()
    return lines[1:] if end > size else lines


def read_log(path):
    """走行記録1本から {start, end, laps, lat, lon, clock}。読めなければ None。
    時刻は測位の時計で直す（clock が 'gnss'）。測位していない走行は本体の時計のまま（'host'。ずれていることがある）"""
    m = LOG_NAME.match(path.name)
    if not m:
        return None
    start = datetime.strptime(m.group(2), '%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc).timestamp()
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            header = next(csv.reader([f.readline()]))
            head = f.read(64 << 10).splitlines()[:-1]   # 頭の数十行（走り始めの周回数を知るため）
        rows = []
        for line in tail_lines(path):   # 値の中にカンマを含む列があるので csv で読む。壊れた行は捨てる
            try:
                rows.append(next(csv.reader([line])))
            except (csv.Error, StopIteration):
                continue
    except (OSError, StopIteration):
        return None
    col = {name: i for i, name in enumerate(header)}
    rows = [r for r in rows if len(r) == len(header) and r[0] != header[0]]   # 書きかけの最後の行・頭の行は除く

    def last(name, convert=float):
        i = col.get(name)
        for r in reversed(rows):
            if i is not None and i < len(r) and r[i] not in ('', 'None', 'nan'):
                try:
                    return convert(r[i])
                except ValueError:
                    continue
        return None
    end = last('host_utc', parse_utc) or start
    # 終わりの時刻は、末尾の行の「本体の時計と測位の時計の差」で直す。始まりは、基板の時計（mcu_ms）で測った長さを引いて出す
    # （ファイルの名前の時刻は本体の時計なので、途中で時計が合った走行では当てにならない）
    hi, gi, mi = col.get('host_utc'), col.get('gnss_utc'), col.get('mcu_ms')
    corr = clock_correction([(parse_utc(r[hi]), parse_utc(r[gi])) for r in rows if r[gi]] if hi is not None and gi is not None else [])
    clock = 'host'
    if corr is not None:
        clock = 'gnss'
        length = end - start
        try:
            first_ms = next(float(r[mi]) for r in (next(csv.reader([line])) for line in head) if len(r) == len(header) and r[mi])
            length = ((float(rows[-1][mi]) - first_ms) % 2**32) / 1000   # mcu_ms は 2^32 で一周する
        except (StopIteration, ValueError, TypeError, IndexError, csv.Error):
            pass
        end -= corr
        start = end - max(0.0, length)
    laps = last('LapCount')
    # 周回数は電源を切っても本体が覚えているので、走り始めの値を引いて「この走行で増えた周」にする
    # （途中でラップを0周に戻した走行は、引くと負になるので、最後の値をそのまま使う）
    first = None
    for line in head:
        try:
            r = next(csv.reader([line]))
            if len(r) == len(header) and r[col['LapCount']] not in ('', 'None', 'nan'):
                first = float(r[col['LapCount']])
                break
        except (csv.Error, StopIteration, KeyError, ValueError):
            continue
    if laps is not None and first is not None and laps >= first:
        laps -= first
    lat, lon = None, None
    for r in reversed(rows):   # 最後に測位していた行の場所
        try:
            if float(r[col['GPSFix']]) > 0:
                lat, lon = float(r[col['Lat']]), float(r[col['Lon']])
                break
        except (KeyError, ValueError, IndexError):
            continue
    return {'start': start, 'end': max(end, start), 'laps': None if laps is None else int(laps), 'lat': lat, 'lon': lon, 'clock': clock}


def read_chapter(ts_path):
    """動画の章の時刻（横の .csv の最初と最後のUTC）。{start, end} か None"""
    csv = ts_path.with_suffix('.csv')
    try:
        with open(csv, encoding='utf-8', errors='replace') as f:
            f.readline()
            first = f.readline()
        lines = [x for x in tail_lines(csv, 8 << 10) if x.strip()]
    except OSError:
        return None

    def utc(line):
        parts = line.split(',')
        return parse_utc(parts[2]) if len(parts) > 2 else None
    start = utc(first)
    end = next((t for t in (utc(x) for x in reversed(lines)) if t is not None), None)
    return {'start': start, 'end': end} if start is not None and end is not None and end >= start else None


def km(lat1, lon1, lat2, lon2):
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    return 6371.0 * math.hypot(x, math.radians(lat2 - lat1))


def load_courses():
    """コースの設定の {名前: (lat, lon)}"""
    folder = Path(__file__).resolve().parents[1] / 'setups' / 'courses'
    out = {}
    for path in sorted(folder.glob('*.json')):
        try:
            line = json.loads(path.read_text(encoding='utf-8'))['line']
            out[path.stem] = (float(line['lat']), float(line['lon']))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return out


def course_names():
    """コースの設定の {名前: 画面に出す名前}"""
    folder = Path(__file__).resolve().parents[1] / 'setups' / 'courses'
    out = {}
    for path in sorted(folder.glob('*.json')):
        try:
            out[path.stem] = str(json.loads(path.read_text(encoding='utf-8'))['name'])
        except (OSError, ValueError, KeyError):
            continue
    return out


def course_of(lat, lon, courses):
    if lat is None or lon is None:
        return None
    near = [(km(lat, lon, *where), name) for name, where in courses.items()]
    return min(near)[1] if near and min(near)[0] <= COURSE_KM else None


def cover(start, end, chapters):
    """走行の時間のうち、動画が重なっている秒数と、無い区間"""
    spans = sorted((max(start, c['start']), min(end, c['end'])) for c in chapters if c['end'] > start and c['start'] < end)
    covered, gaps, at = 0.0, [], start
    for a, b in spans:
        if a > at:
            gaps.append((at, a))
        if b > at:
            covered += b - max(a, at)
            at = b
    if end > at:
        gaps.append((at, end))
    return covered, [[round(a), round(b)] for a, b in gaps if b - a > GAP_S]


def stamp(path):
    st = path.stat()
    return [st.st_size, st.st_mtime_ns]


def build(root, save=True):
    """drive_logs を読んで走行の一覧を作る（新しい順）。ファイルは動かさない。索引は root/runs_index.json"""
    root = Path(root)
    index_path = root / INDEX_NAME
    try:
        old = json.loads(index_path.read_text(encoding='utf-8'))
        cache = old.get('cache', {}) if old.get('version') == VERSION else {}
    except (OSError, ValueError, AttributeError):
        cache = {}
    new_cache = {}

    def cached(path, reader):
        key = path.relative_to(root).as_posix()
        mark = stamp(path)
        hit = cache.get(key)
        value = hit['value'] if hit and hit['stamp'] == mark else reader(path)
        new_cache[key] = {'stamp': mark, 'value': value}
        return value

    chapters = []
    video_root = root / 'v2_video'
    for ts in sorted(video_root.glob('*/*.ts')) if video_root.is_dir() else []:
        if not re.match(r'^\d{8}_\d{6}$', ts.parent.name):   # 録画の回のフォルダーだけ（切り出した動画などは除く）
            continue
        span = cached(ts, read_chapter)
        if span:
            chapters.append({'path': ts.relative_to(root).as_posix(), **span})
    courses = load_courses()
    seen, runs = set(), []
    for log in sorted(root.glob('*/run*/v2_emmc/*.csv')):
        if log.name in seen:      # 同じ走行記録を2回回収していたら、先に見つけた1本だけ
            continue
        info = cached(log, read_log)
        if not info:
            continue
        seen.add(log.name)
        mine = [c for c in chapters if c['end'] > info['start'] and c['start'] < info['end']]
        seconds = info['end'] - info['start']
        covered, gaps = cover(info['start'], info['end'], mine)
        runs.append({
            'id': log.name[:-4], 'day': datetime.fromtimestamp(info['start'], JST).strftime('%Y-%m-%d'),
            'start': round(info['start']), 'end': round(info['end']), 'minutes': round(seconds / 60, 1),
            'laps': info['laps'], 'course': course_of(info['lat'], info['lon'], courses), 'clock': info.get('clock', 'host'),
            'log': log.relative_to(root).as_posix(), 'videos': mine,
            'video': 'none' if not mine else 'all' if seconds > 0 and covered / seconds >= FULL_COVER else 'part',
            'video_minutes': round(covered / 60, 1), 'gaps': gaps,
        })
    runs.sort(key=lambda r: r['start'], reverse=True)
    if save:
        try:
            temp = index_path.with_suffix('.tmp')
            temp.write_text(json.dumps({'version': VERSION, 'built_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                        'runs': runs, 'cache': new_cache}, ensure_ascii=False), encoding='utf-8')
            temp.replace(index_path)
        except OSError:
            pass   # 索引を書けなくても一覧は返す（次も読み直すだけ）
    return runs


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[0]) if argv else Path(__file__).resolve().parents[2] / 'drive_logs'
    runs = build(root, save='--no-save' not in argv)
    days = sorted({r['day'] for r in runs})
    print(f'走行 {len(runs)} 本・{len(days)} 日ぶん（{days[0]}〜{days[-1]}）' if runs else '走行はありません')
    for kind, label in (('all', '動画あり'), ('part', '動画が一部'), ('none', '動画なし')):
        print(f'  {label}: {sum(1 for r in runs if r["video"] == kind)} 本')
    print(f'  コースが分かったもの: {sum(1 for r in runs if r["course"])} 本・周回数があるもの: {sum(1 for r in runs if r["laps"])} 本')
    return 0


if __name__ == '__main__':
    sys.exit(main())
