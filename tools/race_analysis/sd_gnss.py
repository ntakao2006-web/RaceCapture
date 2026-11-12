"""シールドのSDカード（EL*.BIN）に残ったGNSSの解（NAV-PVT、10Hz全部）で、本体のCSVのGNSSの列を置き換える。

2026-11-09より前の本体の記録（eMMCのCSV）は、EcoCaptureが状態を0.1秒以上あけて読んでいたため、
位置が変わるのが1秒に約6回だった（SG-5-3）。SDには受信機の解が全部残っているので、
同じSTM32の時計（mcu_ms）で行を合わせ、各行に「その行より前に届いた最新の解（1秒以内）」を入れ直す。
入れ方は2026-11-09以降のhardware.py（解をrowsで全部受け取る形）と同じ。CANの列・ラップ・セクターなど、
本体が記録したほかの列はそのまま使う。

  単体で確かめる： python tools/race_analysis/sd_gnss.py <SDのフォルダ> <本体のCSV>
  解析では設定ファイルに "sd_dir" を書くと race_analysis.py がこれを使う。

読むのは写しだけ。SDの解は <キャッシュ> に1回だけ読み出して保存する（1,400ファイルで約1分）。
"""
import glob, os, struct, sys
import numpy as np, pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'EcoCapture-Web'))
from sd_decode import records  # noqa: E402

COLS = ['Lat', 'Lon', 'Altitude', 'GPSSpeed', 'Yaw', 'GPSFix', 'GPSSats', 'GNSSHz', 'gnss_hacc_m', 'gnss_utc', 'gnss_itow_ms']


def scan(sd_dir, cache=None):
    """SDのNAV-PVTを全部、ファイルの番号の順に並べた表。boot はSTM32が起動し直すたびに増える番号。"""
    files = sorted(glob.glob(os.path.join(sd_dir, 'EL*.BIN')))
    if cache and os.path.exists(cache) and os.path.getmtime(cache) > max(os.path.getmtime(f) for f in files):
        return pd.read_pickle(cache)
    rows = []
    for fi, f in enumerate(files):
        try:
            with open(f, 'rb') as s:
                for kind, stamp, data in records(s):
                    if kind == 2 and len(data) == 92: rows.append((fi, stamp, data))
        except ValueError:
            pass  # 書きかけの最後のブロックなど。そこまでの解は使う
    n = len(rows)
    raw = np.frombuffer(b''.join(r[2] for r in rows), dtype=np.uint8).reshape(n, 92)
    u = lambda off, t: raw[:, off:off + np.dtype(t).itemsize].copy().view(t).ravel()
    nav = pd.DataFrame({'file': [r[0] for r in rows], 'stamp': np.array([r[1] for r in rows], dtype=np.int64)})
    nav['itow'] = u(0, '<u4').astype(np.int64)
    nav['valid'] = raw[:, 11]; nav['fix'] = raw[:, 20]; nav['flags'] = raw[:, 21]; nav['sats'] = raw[:, 23]
    nav['lon'] = u(24, '<i4') * 1e-7; nav['lat'] = u(28, '<i4') * 1e-7; nav['alt'] = u(36, '<i4') / 1000
    nav['hacc'] = u(40, '<u4') / 1000; nav['gspeed'] = u(60, '<i4') * .0036; nav['head'] = u(64, '<i4') * 1e-5
    nav['utc'] = [f'{y:04}-{mo:02}-{d:02}T{h:02}:{mi:02}:{s:02}Z' if v & 3 == 3 else None
                  for y, mo, d, h, mi, s, v in zip(u(4, '<u2'), raw[:, 6], raw[:, 7], raw[:, 8], raw[:, 9], raw[:, 10], raw[:, 11])]
    nav['boot'] = np.cumsum(np.r_[0, np.diff(nav.stamp.values) < -60000])  # 時計が1分以上戻った所＝起動し直した
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True); nav.to_pickle(cache)
    return nav


def replace(d, nav):
    """d（本体のCSVを読んだ表、mcu_ms・gnss_itow_ms・host_utcの時刻 t がある）のGNSSの列をSDの解で置き換える。
    返す値は (置き換えた表, 確かめた数字の辞書)。"""
    # どの起動の解か：本体の行のitowが、同じmcu_msより前（1秒以内）のSDの解に見つかる数がいちばん多い起動
    probe = d[d.gnss_itow_ms.notna()].iloc[::500]
    best, hits = None, -1
    for b, g in nav.groupby('boot'):
        at = dict(zip(g.itow.values.tolist(), g.stamp.values.tolist()))   # その起動の中で itow → 届いた時刻
        n = sum(1 for it, ms in zip(probe.gnss_itow_ms.values, probe.mcu_ms.values)
                if int(it) in at and 0 <= ms - at[int(it)] < 1000)
        if n > hits: best, hits = b, n
    g = nav[nav.boot == best].reset_index(drop=True)
    ms = d.mcu_ms.values.astype(np.int64)
    i = np.searchsorted(g.stamp.values, ms, side='right') - 1
    have = (i >= 0) & ((ms - g.stamp.values[np.maximum(i, 0)]) < 1000)
    i = np.maximum(i, 0)
    fix = have & (g['fix'].values[i] >= 3) & (g['flags'].values[i] & 1 == 1)
    old_itow = d.gnss_itow_ms.values
    out = d.copy()
    pick = lambda col: np.where(fix, g[col].values[i], np.nan)
    out['Lat'], out['Lon'], out['Altitude'] = pick('lat'), pick('lon'), pick('alt')
    out['GPSSpeed'], out['Yaw'], out['gnss_hacc_m'] = pick('gspeed'), pick('head'), pick('hacc')
    out['GPSFix'] = np.where(have, g['fix'].values[i], np.nan); out['GPSSats'] = np.where(have, g.sats.values[i], np.nan)
    out['gnss_itow_ms'] = np.where(have, g.itow.values[i], np.nan)
    out['gnss_utc'] = np.where(have, g.utc.values[i], None)
    dt = np.diff(g.itow.values) % 604800000
    hz = pd.Series(np.r_[np.nan, np.where((dt > 0) & (dt <= 1000), 1000 / np.maximum(dt, 1), np.nan)]).rolling(20, min_periods=1).max().values
    out['GNSSHz'] = np.where(have, hz[i], np.nan)
    both = np.isfinite(old_itow) & have
    lag = (out.gnss_itow_ms.values[both] - old_itow[both]) % 604800000
    run = (d.GPSSpeed > 60).values          # 走っている行（100行/秒）で、解が変わった行の数を秒あたりに
    rate = lambda it: round(float(np.r_[False, np.diff(it) != 0][run].sum() / (run.sum() / 100)), 2) if run.sum() > 100 else None
    check = {'boot': int(best), 'probe_hits': f'{hits}/{len(probe)}', 'rows_with_sd_fix': round(float(fix.mean() * 100), 2),
             # 前の読み方は、状態の最新の解をその回の行の全部（解が届く前の行も）へ入れていたので、SDのほうが古い行もある
             'same_itow_pct': round(float((lag == 0).mean() * 100), 1), 'sd_newer_pct': round(float(((lag > 0) & (lag < 302400000)).mean() * 100), 1),
             'emmc_pos_rate': rate(old_itow), 'sd_pos_rate': rate(out.gnss_itow_ms.values)}
    return out, check


if __name__ == '__main__':
    sd, csv = sys.argv[1], sys.argv[2]
    nav = scan(sd, os.path.join(os.environ.get('TEMP', '/tmp'), 'sd_gnss_' + os.path.basename(os.path.normpath(sd)) + '.pkl'))
    print(f'SDの解 {len(nav)}個、起動 {nav.boot.nunique()}回、{nav.utc.dropna().iloc[0]} 〜 {nav.utc.dropna().iloc[-1]}')
    d = pd.read_csv(csv, usecols=['mcu_ms', 'host_utc', 'Lat', 'GPSSpeed', 'gnss_itow_ms'], low_memory=False)
    print(replace(d, nav)[1])
