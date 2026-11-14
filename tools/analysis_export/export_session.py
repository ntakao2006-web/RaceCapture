"""走行記録を、解析アプリ（別リポジトリ ecologger-analysis）が読む形式「ecorun」に書き出す（2026-11-14、SP-10-2）。

形式の文書は解析アプリのリポジトリの docs/format.md（境目はこの形式だけ）。ここから出すのは物理量になった値と、
本体が出した周のタイムだけ。CANの読み方（IDや式）・線の判断・通信の中身は出さない。

    python tools/analysis_export/export_session.py <走行記録のCSV>                        走行の全部（動画なし）
    python tools/analysis_export/export_session.py <CSV> --laps 31-33 --video            31〜33周と、その時間の動画
    python tools/analysis_export/export_session.py <CSV> --laps 31-33 --sd drive_logs/20261111/run02_2049/v2_sd

  --sd     シールドのSDのフォルダー。測位をSDに残った受信機の解（10Hz全部）から取る（無ければ本体の記録から拾う。
           11/9より前の本体の記録は1秒に約6回しか位置が変わらない）。SDの読み出しは drive_logs/runs_cache/ に覚える
  --video  その時間の焼き込み動画（drive_logs/v2_video/）をキーフレームの所で切り、MP4にして入れる。ffmpeg が要る
  --rate   チャンネルを書く間隔（Hz、既定50）。本体は100行/秒
出力：drive_logs/sessions/<コース>_<日付>_<周>.ecorun/（位置を含むのでGit管理外）

時刻は全部、本体の時計（host_utc）を測位の時計（gnss_utc）で直したもの（tools/video_collect/run_index.py と同じ直し方を、
行ごとに前後の中央値で）。測位の点だけは、受信機が解を出した時刻（itow）に置く。周は run_laps.py と同じく
LapCount が増えた行で見つけ、タイムは本体の LapTime を使う。ただし周が増えた行は線を越えたあと本体が判断した時刻で、
周ごとに −20〜+190ms 遅れる（SUGO 11/8）。そこで周の始まり・終わりは、測位の点からコースの線を越えた時刻を
本体（EcoCapture-Web/lap.py）と同じ計算で出し直して置く。続いた周は境目が同じ時刻になる。出し直したタイムが
本体のタイムと SNAP_TOL 以上違う周（線が本体と違う・測位が抜けた）は、周が増えた行の時刻のまま残す。
"""
import argparse
import gzip
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'video_collect'))
import run_index  # noqa: E402

FORMAT_VERSION = 1
TOOL = f'EcoLogger export_session {FORMAT_VERSION}'
GPS_EPOCH = 315964800   # 1980-01-06 のUNIX秒
LEAP = 18               # GPSとUTCの差（秒）
MAX_HACC = 25.0         # これより粗い解は捨てる（EcoCapture-Web/lap.py と同じ）
HOLD_S = 1.0            # チャンネルの値をこの秒数まで持ち続ける（それより古ければ空欄）
CLOCK_WINDOW = 1001     # 時計の直しの中央値をとる行数（100行/秒で約10秒）
EARTH_M_PER_DEG = 111320.0   # EcoCapture-Web/lap.py と同じ
MAX_FIX_GAP_S = 1.0     # これより離れた2点のあいだでは線を越えたと見ない（lap.py と同じ）
SNAP_BEFORE, SNAP_AFTER = 1.0, 0.5   # 周が増えた行のこれだけ前〜後の、線を越えた時刻を探す
SNAP_TOL = 0.02         # 出し直したタイムと本体のタイムの差がこれ以内なら、出し直した時刻を使う（秒）

# 書き出さない列：位置と周（測位・周は別に書く）、本体の中の数え方・状態、生のバイト列
SKIP = {
    'schema', 'demo', 'source', 'host_utc', 'seq', 'mcu_ms',
    'Lat', 'Lon', 'Altitude', 'Yaw', 'GPSSpeed', 'GPSFix', 'GPSSats', 'GNSSHz', 'Distance',
    'gnss_utc', 'gnss_itow_ms', 'gnss_hacc_m', 'imu_raw', 'imu_calibration', 'quaternion', 'imu_mount',
    'LapCount', 'CurrentLap', 'LapTime', 'BestLap', 'ElapsedTime', 'RaceTime', 'LapsLeft', 'TimeLimit', 'Margin',
    'Sector', 'LastSector', 'SectorTime',
}
STATE = {'ClutchDisengaged'}
LABEL = {
    'Speed': '車速', 'RPM': '回転数', 'Throttle': 'アクセル', 'BatteryVolt': '電圧',
    'LongAccel': '前後G', 'LatAccel': '横G', 'VertAccel': '上下G', 'GyroZ': 'ヨーレート',
    'WaterTemp': '水温', 'OilTemp': '油温', 'IntakeTemp': '吸気温', 'FuelLevelRaw': '燃料',
    'WheelFrontA': '車輪速 前A', 'WheelFrontB': '車輪速 前B', 'WheelRearA': '車輪速 後A', 'WheelRearB': '車輪速 後B',
    'ClutchDisengaged': 'クラッチを切った',
}
LAP_COLS = ['LapCount', 'LapTime', 'LastSector', 'SectorTime']
GNSS_COLS = ['gnss_utc', 'gnss_itow_ms', 'Lat', 'Lon', 'Altitude', 'GPSSpeed', 'Yaw', 'GPSFix', 'GPSSats', 'gnss_hacc_m']


# ---------------------------------------------------------------- 読む
def utc_seconds(series):
    """ISO 8601 の文字列の列 → UTCの秒（読めない所は NaN）"""
    t = pd.to_datetime(pd.Series(series), utc=True, format='ISO8601', errors='coerce')
    return (t - pd.Timestamp(0, tz='UTC')).dt.total_seconds().values.astype(float)


def read_units(csv_path):
    try:
        meta = json.loads(Path(str(csv_path) + '.meta.json').read_text(encoding='utf-8'))
        return dict(meta.get('units') or {}), meta.get('config', {}).get('device_name')
    except (OSError, ValueError, AttributeError):
        return {}, None


def channel_names(header, units):
    """書き出すチャンネル（記録の列の順）。単位の分かる列のうち、SKIP と状態の印（…State）を除いたもの"""
    return [c for c in header if c in units and c not in SKIP and not c.endswith('State')]


def read_log(csv_path, channels):
    head = pd.read_csv(csv_path, nrows=0).columns.tolist()
    use = ['host_utc'] + [c for c in GNSS_COLS + LAP_COLS + channels if c in head and c != 'host_utc']
    df = pd.read_csv(csv_path, usecols=use, low_memory=False, on_bad_lines='skip')
    for c in use:
        if c not in ('host_utc', 'gnss_utc'):
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


# ---------------------------------------------------------------- 時計
def corrected_time(host, gnss):
    """各行の時刻（UTCの秒）。本体の時計を、前後 CLOCK_WINDOW 行の (host − gnss) の中央値 − 0.5 秒で直す。
    gnss_utc は秒の切り捨てなので、合っていれば差の中央値は約+0.5秒（run_index.clock_correction と同じ考え）。
    返す値は (時刻, 'gnss'|'host')。測位の行が無ければ本体の時計のまま"""
    diff = pd.Series(host - gnss)
    have = diff.notna()
    if have.sum() < 10:
        return host.copy(), 'host'
    med = diff[have].rolling(CLOCK_WINDOW, center=True, min_periods=1).median()
    corr = med.reindex(diff.index).ffill().bfill().values - 0.5
    return host - corr, 'gnss'


def fix_time(utc_s, itow_ms):
    """受信機が解を出した時刻：週の頭からの itow を、秒の切り捨ての gnss_utc で週を決めて UTC にする"""
    week = np.round((utc_s + LEAP - itow_ms / 1000 - GPS_EPOCH) / 604800)
    return GPS_EPOCH + week * 604800 + itow_ms / 1000 - LEAP


# ---------------------------------------------------------------- 周
def find_laps(t, df):
    """周の一覧 [{lap, start, end, time_s, sectors}]（時刻はUTCの秒）。run_laps.laps_of と同じ数え方"""
    if 'LapCount' not in df:
        return []
    lc = df['LapCount'].values
    lt = df['LapTime'].values if 'LapTime' in df else np.full(len(df), np.nan)
    ls = df['LastSector'].values if 'LastSector' in df else np.full(len(df), np.nan)
    st = df['SectorTime'].values if 'SectorTime' in df else np.full(len(df), np.nan)
    laps, count, sectors, last_key = [], None, {}, None
    for i in np.flatnonzero(np.isfinite(lc) | (np.isfinite(ls) & np.isfinite(st))):
        if np.isfinite(ls[i]) and np.isfinite(st[i]) and (ls[i], st[i]) != last_key:
            last_key = (ls[i], st[i])
            sectors[int(ls[i])] = round(float(st[i]) * 60, 3)
        now = lc[i]
        if not np.isfinite(now):
            continue
        if count is not None and now > count:
            if np.isfinite(lt[i]) and np.isfinite(t[i]):
                time_s = round(float(lt[i]) * 60, 3)
                laps.append({'lap': int(now), 'start': float(t[i]) - time_s, 'end': float(t[i]), 'time_s': time_s,
                             'sectors': [sectors.get(k) for k in sorted(sectors)]})
            sectors = {}
        elif count is not None and now < count:      # 途中でラップを0周に戻した
            sectors = {}
        count = now
    return laps


def line_crossings(g, line):
    """測位の点（列 utc・lat・lon）が線を前向きに越えた時刻（UTCの秒）の配列。lap.py の crossing_point・line_crossing と同じ計算"""
    if not len(g) or not line or not all(k in line for k in ('lat', 'lon', 'bearing', 'width_m')):
        return np.array([])
    lat0, lon0 = line['lat'], line['lon']
    x = (g.lon.values - lon0) * EARTH_M_PER_DEG * math.cos(math.radians(lat0))
    y = (g.lat.values - lat0) * EARTH_M_PER_DEG
    rad = math.radians(line['bearing'])
    nx, ny = math.sin(rad), math.cos(rad)
    d = x * nx + y * ny                       # 線から進む向きへの距離
    side = x * ny - y * nx                    # 線の中心から横への距離（+が進む向きの右）
    t = g.utc.values
    out = []
    for i in np.flatnonzero((d[:-1] < 0) & (d[1:] >= 0) & (np.diff(t) <= MAX_FIX_GAP_S) & (np.diff(t) > 0)):
        f = -d[i] / (d[i + 1] - d[i])
        if abs(side[i] + (side[i + 1] - side[i]) * f) <= line['width_m'] / 2:
            out.append(t[i] + (t[i + 1] - t[i]) * f)
    return np.array(out)


def snap_laps(laps, crossings):
    """周の始まり・終わりを、線を越えた時刻に置き直す。返す値は置き直した周の数。
    周が増えた行（end）の SNAP_BEFORE 前〜SNAP_AFTER 後にある越えた時刻を終わり、始まりも同じように探し、
    その差が本体のタイムと SNAP_TOL 以内のときだけ置き直す（タイムは本体の値のまま）"""
    if not len(crossings):
        return 0

    def near(at):
        k = np.flatnonzero((crossings >= at - SNAP_BEFORE) & (crossings <= at + SNAP_AFTER))
        return float(crossings[k[np.argmin(abs(crossings[k] - at))]]) if len(k) else None

    done = 0
    for x in laps:
        ce, cs = near(x['end']), near(x['start'])
        if ce is not None and cs is not None and abs((ce - cs) - x['time_s']) <= SNAP_TOL:
            x['start'], x['end'], x['snapped'] = cs, ce, True
            done += 1
    return done


def parse_laps(text):
    a, _, b = str(text).partition('-')
    a = int(a)
    return a, int(b) if b else a


# ---------------------------------------------------------------- 測位
def gnss_from_log(df):
    """本体の記録から本物の解だけ：itow が変わった最初の行の値を、その解の時刻に置く"""
    if 'gnss_itow_ms' not in df or 'Lat' not in df:
        return pd.DataFrame()
    itow = df['gnss_itow_ms'].values
    gu = utc_seconds(df['gnss_utc']) if 'gnss_utc' in df else np.full(len(df), np.nan)
    ok = np.isfinite(itow) & np.isfinite(gu) & np.isfinite(df['Lat'].values) & np.isfinite(df['Lon'].values)
    if 'GPSFix' in df:
        ok &= df['GPSFix'].values >= 3
    if 'gnss_hacc_m' in df:
        h = df['gnss_hacc_m'].values
        ok &= ~(h > MAX_HACC)
    idx = np.flatnonzero(ok)
    if not len(idx):
        return pd.DataFrame()
    tf = fix_time(gu[idx], itow[idx])
    g = pd.DataFrame({'utc': tf, 'lat': df['Lat'].values[idx], 'lon': df['Lon'].values[idx],
                      'alt_m': df['Altitude'].values[idx] if 'Altitude' in df else np.nan,
                      'speed_kmh': df['GPSSpeed'].values[idx] if 'GPSSpeed' in df else np.nan,
                      'heading_deg': df['Yaw'].values[idx] if 'Yaw' in df else np.nan,
                      'sats': df['GPSSats'].values[idx] if 'GPSSats' in df else np.nan,
                      'hacc_m': df['gnss_hacc_m'].values[idx] if 'gnss_hacc_m' in df else np.nan})
    return g.drop_duplicates('utc', keep='first').sort_values('utc').reset_index(drop=True)


def gnss_from_sd(sd_dir, t0, t1):
    """シールドのSDに残った NAV-PVT（10Hz全部）から [t0, t1] の解"""
    sys.path.insert(0, str(ROOT / 'tools' / 'race_analysis'))
    import sd_gnss
    where = Path(sd_dir).resolve()
    try:
        where = where.relative_to(ROOT)
    except ValueError:
        pass
    key = ''.join(ch if ch.isalnum() else '_' for ch in str(where))[-80:]
    nav = sd_gnss.scan(str(sd_dir), str(ROOT / 'drive_logs' / 'runs_cache' / f'sd_nav_{key}.pkl'))
    nav = nav[nav.utc.notna()]
    gu = utc_seconds(nav.utc)
    tf = fix_time(gu, nav.itow.values.astype(float))
    ok = (tf >= t0 - 1) & (tf <= t1 + 1) & (nav['fix'].values >= 3) & (nav['flags'].values & 1 == 1) & (nav.hacc.values <= MAX_HACC)
    n = nav[ok]
    g = pd.DataFrame({'utc': tf[ok], 'lat': n.lat.values, 'lon': n.lon.values, 'alt_m': n.alt.values,
                      'speed_kmh': n.gspeed.values, 'heading_deg': n['head'].values, 'sats': n.sats.values, 'hacc_m': n.hacc.values})
    return g.drop_duplicates('utc', keep='first').sort_values('utc').reset_index(drop=True)


# ---------------------------------------------------------------- チャンネル
def resample(t_src, values, grid):
    """値のある行だけを使い、grid の各時刻に「その時刻までの最新の値」（HOLD_S より古ければ NaN）"""
    ok = np.isfinite(t_src) & np.isfinite(values)
    ts, vs = t_src[ok], values[ok]
    if not len(ts):
        return np.full(len(grid), np.nan)
    order = np.argsort(ts, kind='stable')
    ts, vs = ts[order], vs[order]
    i = np.searchsorted(ts, grid, side='right') - 1
    out = vs[np.maximum(i, 0)].astype(float)
    out[(i < 0) | (grid - ts[np.maximum(i, 0)] > HOLD_S)] = np.nan
    return out


def as_text(values, spec):
    """数の列 → 文字の列（spec は '.3f' や '.6g'。NaN は空欄）"""
    v = np.asarray(values, dtype=float)
    out = np.char.mod('%' + spec, np.nan_to_num(v)).astype(object)
    out[~np.isfinite(v)] = ''
    return out


def write_csv_gz(path, header, columns, specs):
    table = pd.DataFrame({h: as_text(c, s) for h, c, s in zip(header, columns, specs)}, columns=header)
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as f:
        table.to_csv(f, index=False, lineterminator='\n')


# ---------------------------------------------------------------- 動画
def sync_pairs(rows, key_utc, video_start, duration, t0):
    """動画の横の .csv の (video_s, utc) を、切り出したMP4の [動画の秒, t] にする。
    key_utc は切り出しの頭（キーフレーム）の時刻、video_start はMP4の映像の始まりの秒（ffprobe）"""
    us = [u for _, u in rows]
    vs = [v for v, _ in rows]
    key_vs = float(np.interp(key_utc, us, vs))
    out = []
    for v, u in rows:
        mv = v - key_vs + video_start
        if -0.5 <= mv <= duration + 0.5:
            out.append([round(mv, 3), round(u - t0, 3)])
    return out


def probe(mp4):
    sys.path.insert(0, str(ROOT / 'tools' / 'lap_video'))
    import lap_video
    r = subprocess.run([lap_video.ffbin('ffprobe'), '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=start_time,duration', '-of', 'json', str(mp4)], capture_output=True, text=True, check=True)
    s = json.loads(r.stdout)['streams'][0]
    return float(s.get('start_time') or 0), float(s.get('duration') or 0)


def export_videos(out_dir, t_start, t_end, t0):
    """[t_start, t_end]（UTCの秒）に重なる動画の章を、章ごとに1本のMP4にする"""
    sys.path.insert(0, str(ROOT / 'tools' / 'lap_video'))
    import lap_video
    chs = [c for c in lap_video.chapters() if c[3] >= t_start and c[2] <= t_end]
    vids = []
    if not chs:
        return vids
    (out_dir / 'video').mkdir(exist_ok=True)
    ff = lap_video.ffbin('ffmpeg')
    with tempfile.TemporaryDirectory() as tmp:
        for k, ch in enumerate(chs, 1):
            plan, key_utc = lap_video.cut_plan([ch], max(t_start, ch[2]), min(t_end, ch[3]))
            if not plan or key_utc is None:
                continue
            ts = Path(tmp) / f'{k:02d}.ts'
            lap_video.write_cut(plan, ts)
            mp4 = out_dir / 'video' / f'{k:02d}.mp4'
            lap_video.run(ff, '-hide_banner', '-v', 'error', '-y', '-i', ts, '-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'copy',
                          '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-avoid_negative_ts', 'make_zero', mp4)
            v0, dur = probe(mp4)
            pairs = sync_pairs(ch[4], key_utc, v0, dur, t0)
            if len(pairs) >= 2:
                vids.append({'file': f'video/{k:02d}.mp4', 'sync': pairs})
                print(f'  動画 {mp4.name}：{dur:.0f}秒（{Path(ch[0]).name} から）')
    return vids


# ---------------------------------------------------------------- コース
def course_info(lat, lon):
    courses = run_index.load_courses()
    cid = run_index.course_of(lat, lon, courses)
    if not cid:
        return None, None
    try:
        c = json.loads((ROOT / 'tools' / 'setups' / 'courses' / f'{cid}.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return cid, None
    pick = lambda x: {k: x[k] for k in ('lat', 'lon', 'bearing', 'width_m') if k in x}   # noqa: E731
    line = c.get('line') or {}
    return cid, {'name': c.get('name', cid), 'line': pick(line), 'sectors': [pick(s) for s in line.get('sectors') or []]}


# ---------------------------------------------------------------- 本体
def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def export(csv_path, out=None, laps=None, sd=None, video=False, rate=50.0, lead=5.0, tail=5.0, log=print):
    csv_path = Path(csv_path)
    units, device = read_units(csv_path)
    header = pd.read_csv(csv_path, nrows=0).columns.tolist()
    channels = channel_names(header, units)
    log(f'{csv_path.name} を読んでいます（チャンネル {len(channels)} 本）')
    df = read_log(csv_path, channels)
    host = utc_seconds(df['host_utc'])
    gnss_s = utc_seconds(df['gnss_utc']) if 'gnss_utc' in df else np.full(len(df), np.nan)
    t, clock = corrected_time(host, gnss_s)
    all_laps = find_laps(t, df)

    if laps:
        a, b = laps
        first = next((x for x in all_laps if x['lap'] == a), None)
        last = next((x for x in all_laps if x['lap'] == b), None)
        if not first or not last:
            raise SystemExit(f'{a}〜{b}周が記録に無い（ある周：{all_laps[0]["lap"]}〜{all_laps[-1]["lap"]}）' if all_laps else '記録に周が無い')
        t_start, t_end = first['start'] - lead, last['end'] + tail
    else:
        fin = t[np.isfinite(t)]
        t_start, t_end = float(fin.min()), float(fin.max())
    t0 = math.floor(t_start * 1000) / 1000
    grid = np.arange(0.0, t_end - t0 + 1e-9, 1.0 / rate)

    if sd:
        g = gnss_from_sd(sd, t_start, t_end)
        gsrc = 'sd'
    else:
        g = gnss_from_log(df)
        gsrc = 'logger'
    g = g[(g.utc >= t_start) & (g.utc <= t_end)] if len(g) else g

    cid, course = course_info(*(g[['lat', 'lon']].iloc[-1].tolist() if len(g) else (None, None)))
    snap_laps(all_laps, line_crossings(g, course and course.get('line')))
    day = datetime.fromtimestamp(t0, run_index.JST).strftime('%Y%m%d')
    name = f"{cid or 'run'}_{day}_{f'{laps[0]}-{laps[1]}' if laps else 'all'}"
    out_dir = Path(out) if out else ROOT / 'drive_logs' / 'sessions' / f'{name}.ecorun'
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    cols = [grid]
    chans = []
    for c in channels:
        v = resample(t, df[c].values.astype(float), grid + t0)
        if not np.isfinite(v).any():
            continue
        cols.append(v)
        ch = {'name': c, 'unit': units.get(c, ''), 'kind': 'state' if c in STATE else 'number'}
        if c in LABEL:
            ch['label'] = LABEL[c]
        chans.append(ch)
    write_csv_gz(out_dir / 'channels.csv.gz', ['t'] + [c['name'] for c in chans], cols, ['.3f'] + ['.6g'] * len(chans))

    meta_gnss = None
    if len(g):
        gc = ['lat', 'lon', 'alt_m', 'speed_kmh', 'heading_deg', 'sats', 'hacc_m']
        write_csv_gz(out_dir / 'gnss.csv.gz', ['t'] + gc, [g.utc.values - t0] + [g[c].values.astype(float) for c in gc],
                     ['.3f', '.8f', '.8f', '.2f', '.2f', '.2f', '.0f', '.2f'])
        dt = np.diff(g.utc.values)
        meta_gnss = {'source': gsrc, 'rate_hz': round(float(1 / np.median(dt)), 1) if len(dt) else None}

    lap_out = [{'lap': x['lap'], 'start': round(x['start'] - t0, 3), 'end': round(x['end'] - t0, 3), 'time_s': x['time_s'],
                'sectors': x['sectors']} for x in all_laps if x['start'] >= t_start - 1e-6 and x['end'] <= t_end + 1e-6]
    vids = export_videos(out_dir, t_start, t_end, t0) if video else []
    kept = [x for x in all_laps if x['start'] >= t_start - 1e-6 and x['end'] <= t_end + 1e-6]
    unsnapped = [x['lap'] for x in kept if not x.get('snapped')]
    if not kept:
        lap_note = []
    elif not unsnapped:
        lap_note = ['周の始まり・終わりは、測位からコースの線を越えた時刻を出し直したもの（続いた周は境目が同じ時刻）']
    else:
        lap_note = [f'周の始まり・終わりは、測位からコースの線を越えた時刻を出し直したもの。ただし {", ".join(map(str, unsnapped))}周目は'
                    '出し直せず（線が本体と違う・測位が抜けた）、本体が周を数えた時刻のまま（数十〜百数十ms遅い）']

    title = f"{course['name'] if course else '走行'} {datetime.fromtimestamp(t0, run_index.JST).strftime('%Y-%m-%d')}"
    title += f' {laps[0]}〜{laps[1]}周' if laps else ''
    session = {
        'format': 'ecorun', 'version': FORMAT_VERSION,
        'created_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'created_by': TOOL,
        'title': title, 't0_utc': iso(t0), 'duration_s': round(float(grid[-1]), 3), 'clock': clock,
        'source': {'device': device or 'EcoLogger', 'log': csv_path.stem},
        **({'course': course} if course else {}),
        'channels_file': 'channels.csv.gz', 'channels': chans, 'rate_hz': rate,
        **({'gnss_file': 'gnss.csv.gz', 'gnss': meta_gnss} if meta_gnss else {}),
        'laps': lap_out, 'videos': vids,
        'notes': ['周のタイムは本体が走りながら数えたもの（公式の計測ではない）'] + lap_note +
                 (['測位はシールドのSDに残った受信機の解'] if gsrc == 'sd' else []),
    }
    (out_dir / 'session.json').write_text(json.dumps(session, ensure_ascii=False, indent=1), encoding='utf-8')
    log(f'書き出し：{out_dir}')
    log(f'  {len(grid)}行×{len(chans)}チャンネル、測位 {len(g)}点（{gsrc}）、周 {len(lap_out)}'
        f'（線を越えた時刻に置いた周 {len(lap_out) - len(unsnapped)}）、動画 {len(vids)}本、時計 {clock}')
    return out_dir, session


def main(argv=None):
    ap = argparse.ArgumentParser(description='走行記録を ecorun 形式に書き出す（解析アプリ用）')
    ap.add_argument('csv', help='本体の走行記録（drive_logs/<日付>/runNN_*/v2_emmc/LOG_*.csv）')
    ap.add_argument('--laps', type=parse_laps, help='周の範囲（例 31-33 または 31）。無ければ全部')
    ap.add_argument('--sd', help='シールドのSDのフォルダー（測位を10Hz全部の解から取る）')
    ap.add_argument('--video', action='store_true', help='その時間の動画を入れる')
    ap.add_argument('--rate', type=float, default=50.0, help='チャンネルを書く間隔（Hz）')
    ap.add_argument('--lead', type=float, default=5.0, help='周の前に足す秒')
    ap.add_argument('--tail', type=float, default=5.0, help='周の後に足す秒')
    ap.add_argument('--out', help='出力のフォルダー（既定 drive_logs/sessions/<名前>.ecorun）')
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    export(a.csv, a.out, a.laps, a.sd, a.video, a.rate, a.lead, a.tail)
    return 0


if __name__ == '__main__':
    sys.exit(main())
