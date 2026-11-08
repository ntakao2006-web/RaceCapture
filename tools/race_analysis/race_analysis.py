"""Ver.2ロガーの記録（本体のCSV）とLTEの記録（5BのJSON Lines）から、レース1回分の解析をまとめる。

2026-11-08 SUGO 120分耐久のために作った（SG-5-3）。大会ごとに変わる決めごと（コントロールライン・
決勝と予選の周・スティント・ピット・出来事のあった周・トレッド）は設定ファイルに書く（例：sugo_20261108.json）。
タイヤの滑り（車体の横滑り角・後輪の空転・前輪のロックぎみ）は、舵角が無くても出せるオーバーステアの向きだけを見る。

  python tools/race_analysis/race_analysis.py tools/race_analysis/sugo_20261108.json

出力（位置を含むので drive_logs/ の下へ出す。リポジトリには入らない）：
  <out_dir>/detail/*.csv  … 中間の表（周・スティント・ピット・ギア・油圧の出来事など）
  <out_dir>/pub/*.csv     … レポートのページに載せる11個の表（facts・laps・temps・water・track・
                            corners・compare・gg・press・logger・slides）
読むのは写しだけで、本体・5Bには触らない。出来事の周を探すときは lap_survey.py を先に使う。
"""
import json, glob, os, sys
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.signal import find_peaks

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CFG = json.load(open(sys.argv[1], encoding='utf-8'))
RP = lambda p: p if os.path.isabs(p) else os.path.join(REPO, p)
OUT = os.path.join(RP(CFG['out_dir']), 'detail'); os.makedirs(OUT, exist_ok=True)
PUB = os.path.join(RP(CFG['out_dir']), 'pub'); os.makedirs(PUB, exist_ok=True)
LAT0, LON0 = CFG['line']                        # コントロールライン
V0 = None                                      # 油圧0 kPaの電圧（エンジン停止・Defi通電の中央値）
RACE_LAPS = range(CFG['race_laps'][0], CFG['race_laps'][1] + 1)
QUALI_LAPS = range(CFG['quali_laps'][0], CFG['quali_laps'][1] + 1)
STINTS = CFG['stints']                         # [[最初の周, 最後の周（ピットの周）], ...]
STINT_OF = lambda n: next(i + 1 for i, (a, b) in enumerate(STINTS) if a <= n <= b)
PIT_LAPS = {n: i + 1 for i, n in enumerate(CFG['pit_laps'])}
PIT_OUT = tuple(CFG['pit_out_laps'])
START_LAP, LAST_LAP = CFG['race_laps']
INCIDENT = tuple(CFG['incident_laps'])         # 一か所で大きく減速・停止した周（lap_survey.pyで確かめる）
SLOW_PAIRS = [tuple(p) for p in CFG['slow_all_laps']]
SLOW_ALL = tuple(n for a, b in SLOW_PAIRS for n in range(a, b + 1))   # 全区間で一様に遅い周
PRE_PIT = [tuple(p) for p in CFG['pre_pit_slow']]                    # ピットの前の遅い周（出来事の周から）
JST = 'Asia/Tokyo'
DAY = CFG['date']
W0, W1 = (pd.Timestamp(f"{DAY} {t}", tz=JST) for t in CFG['window'])
facts = []
def mmss(v):
    m = int(v // 60); return f'{m}:{v - 60 * m:06.3f}'
def fact(key, value, label):
    facts.append({'key': key, 'value': value, 'label': label})

def xy(lat, lon):
    return ((lon - LON0) * np.cos(np.radians(LAT0)) * 111320.0, (lat - LAT0) * 110540.0)

KEEP = set(('seq mcu_ms host_utc Speed GPSSpeed RPM Throttle Lat Lon Altitude Yaw GPSFix GPSSats GNSSHz AccelX AccelY AccelZ '
            'LongAccel LatAccel Distance WaterTemp gnss_utc gnss_hacc_m LapCount CurrentLap LapTime BestLap ElapsedTime RaceTime '
            'Sector LastSector SectorTime WheelFrontA WheelFrontB WheelRearA WheelRearB IntakeTemp FuelLevelRaw ClutchDisengaged '
            'OilTemp PressVolt PressVoltState Temp1Volt Temp2Volt WaterTempDefi GyroZ').split())
def load(path):
    path = RP(path)
    cache = os.path.join(RP(CFG['out_dir']), 'cache', os.path.basename(path) + '.pkl')
    want = {c for c in pd.read_csv(path, nrows=0).columns if c in KEEP} - {'host_utc'}
    d = None
    if os.path.exists(cache) and os.path.getmtime(cache) > os.path.getmtime(path):
        d = pd.read_pickle(cache)
        if not want <= set(d.columns): d = None    # KEEPに列を足したら読み直す
    if d is None:
        d = pd.read_csv(path, usecols=lambda c: c in KEEP, low_memory=False)
        d['t'] = pd.to_datetime(d.host_utc, format='ISO8601'); d = d.drop(columns=['host_utc'])
        os.makedirs(os.path.dirname(cache), exist_ok=True); d.to_pickle(cache)
    d['lap'] = d.LapCount + 1                  # 今走っている周（CurrentLap）
    d['ts'] = d.mcu_ms / 1000.0
    d['x'], d['y'] = xy(d.Lat.values, d.Lon.values)
    return d

race, quali = load(CFG['race_csv']), load(CFG['quali_csv'])

# ---------- 油温・油圧の有効な行 ----------
off = race[(race.RPM.fillna(-1) == 0) & (race.PressVolt.between(0.4, 1.0))]
V0 = float(off.PressVolt.median())
for d in (race, quali):
    ok = d.PressVoltState.eq(0) & d.PressVolt.ge(0.3)
    ok = ok.astype(float).rolling(601, center=True, min_periods=1).min().astype(bool)   # 通電の前後3秒も外す
    d['defi_ok'] = ok
    d['oil'] = d.OilTemp.where(ok)
    d['wdefi'] = d.WaterTempDefi.where(ok)
    d['kpa'] = (250.0 * (d.PressVolt - V0)).where(ok)
fact('v0', round(V0, 2), '油圧0 kPaの電圧（V）')
bad_oil = race[(race.OilTemp > 150)]
fact('oil_bogus_max', round(float(bad_oil.OilTemp.max()), 0), 'Defiの電源が切れている間の見かけの油温の最高（℃）')

# ---------- 周 ----------
def lap_table(d, session):
    first = d.groupby('LapCount').first()
    lt = (first.LapTime * 60.0)               # LapCount==N の行のLapTimeが第N周のタイム
    rows = []
    for n, g in d.groupby('lap'):
        if n not in lt.index: continue
        mv = g[g.GPSSpeed > 2]
        rows.append({'session': session, 'lap': int(n),
                     'start_jst': g.t.iloc[0].tz_convert(JST).strftime('%H:%M:%S'),
                     'lap_s': round(float(lt.loc[n]), 3),
                     'stopped_s': round(float((g.GPSSpeed < 2).sum() / 100), 1),
                     'engine_off_s': round(float((g.RPM.isna() | (g.RPM < 300)).sum() / 100), 1),
                     'vmax': round(float(g.GPSSpeed.max()), 1),
                     'oil_max': round(float(g.oil.max()), 1) if g.oil.notna().any() else None,
                     'oil_avg': round(float(mv.oil.mean()), 1) if mv.oil.notna().any() else None,
                     'water_max': float(g.WaterTemp.max()) if g.WaterTemp.notna().any() else None,
                     'wdefi_max': round(float(g.wdefi.max()), 1) if g.wdefi.notna().any() else None,
                     'press_min': round(float(g.kpa[g.RPM > 3000].min()), 0) if (g.RPM > 3000).any() else None,
                     'fuel': round(float(mv.FuelLevelRaw.median()), 1) if mv.FuelLevelRaw.notna().any() else None,
                     'rpm_max': round(float(g.RPM.max()), 0) if g.RPM.notna().any() else None})
    return pd.DataFrame(rows)

def sector_table(d):
    ch = d[(d.Sector.diff() != 0) & d.LastSector.notna() & d.SectorTime.notna()]
    recs = {}
    for _, r in ch.iterrows():
        k = int(r.LastSector); n = int(r.lap) - (1 if k == 4 else 0)
        recs.setdefault(n, {})[f's{k}'] = round(float(r.SectorTime) * 60, 3)
    return pd.DataFrame([{'lap': n, **v} for n, v in recs.items()])

laps_r = lap_table(race, '決勝').merge(sector_table(race), on='lap', how='left')
laps_q = lap_table(quali, '予選').merge(sector_table(quali), on='lap', how='left')
laps_r = laps_r[laps_r.lap.isin(RACE_LAPS)].copy()
laps_q = laps_q[laps_q.lap.isin(QUALI_LAPS)].copy()     # アウトの周・ピットインの周は設定で外す
laps_r['stint'] = laps_r.lap.map(STINT_OF)
laps_q['stint'] = 0
med = laps_r[~laps_r.lap.isin(PIT_LAPS)].groupby('stint').lap_s.median()

def kind(r):
    if r.session == '予選':
        return '予選'
    if r.lap in PIT_LAPS: return 'ピット'
    if r.lap in PIT_OUT: return 'ピット明け'
    if r.lap == START_LAP: return 'スタート'
    if r.lap in INCIDENT: return '一か所で減速'
    if r.lap in SLOW_ALL: return '全体に遅い'
    if r.lap == LAST_LAP: return '最後の周'
    if r.lap_s > med[r.stint] * 1.06: return '遅い周'
    return '通常'
laps = pd.concat([laps_q, laps_r], ignore_index=True)
laps['kind'] = laps.apply(kind, axis=1)
laps['lap_in_stint'] = laps.groupby(['session', 'stint']).cumcount() + 1
laps_r = laps[laps.session == '決勝'].copy(); laps_q = laps[laps.session == '予選'].copy()
clean = laps[laps.kind.isin(['通常', '予選'])]
best = laps_r.loc[laps_r.lap_s.idxmin()]
REF = int(best.lap)
laps['to_best'] = (laps.lap_s - best.lap_s).round(3)
for k in ('s1', 's2', 's3', 's4'):
    laps[k + '_best'] = laps[k] == clean[k].min()
laps['sum_sec'] = laps[['s1', 's2', 's3', 's4']].sum(axis=1, min_count=4).round(3)

fact('best_lap', round(float(best.lap_s), 3), '決勝のベスト（秒）')
fact('best_lap_no', REF, 'ベストの周')
fact('best_lap_jst', best.start_jst, 'ベストの周の始まり')
qb = laps_q.loc[laps_q.lap_s.idxmin()]
fact('q_best', round(float(qb.lap_s), 3), '予選のベスト（秒）'); fact('q_best_no', int(qb.lap), '予選のベストの周')
theo = sum(float(clean[k].min()) for k in ('s1', 's2', 's3', 's4'))
fact('theo_best', round(theo, 3), 'セクターのベストの和（秒）')
fact('theo_gap', round(float(best.lap_s) - theo, 3), 'ベストとセクターのベストの和の差（秒）')
fact('race_laps', len(laps_r), '決勝で走った周')
fact('race_start', laps_r.start_jst.iloc[0], 'スタートでラインを通った時刻')
fin = race[race.lap == LAST_LAP + 1].t.iloc[0].tz_convert(JST).strftime('%H:%M:%S')
fact('race_finish', fin, 'チェッカーでラインを通った時刻')
fact('clean_laps', int((laps.kind == '通常').sum()), '決勝の通常の周の数')
sec_sum_err = (laps_r.lap_s - laps_r[['s1', 's2', 's3', 's4']].sum(axis=1, min_count=4)).abs()
fact('sector_sum_err', round(float(sec_sum_err.max()), 3), 'セクターの和とラップの差の最大（秒）')

# ---------- スティント ----------
st = []
for s, g in laps_r.groupby('stint'):
    c = g[g.kind == '通常']
    slope = np.polyfit(c.lap_in_stint, c.lap_s, 1)[0] if len(c) > 3 else np.nan
    w = c[c.lap_in_stint >= 3]
    oil_rise = np.polyfit(w.lap_in_stint, w.oil_avg, 1)[0] if len(w) > 3 else np.nan
    st.append({'stint': int(s), 'name': f'スティント{s}', 'first': int(g.lap.min()), 'last': int(g.lap.max()),
               'laps': len(g), 'clean': len(c), 'best': round(float(c.lap_s.min()), 3),
               'best_lap': int(c.loc[c.lap_s.idxmin()].lap), 'median': round(float(c.lap_s.median()), 3),
               'slope': round(float(slope), 3), 'oil_rise': round(float(oil_rise), 2),
               'oil_max': round(float(g.oil_max.max()), 1), 'press_min': float(c.press_min.min()),
               'start_jst': g.start_jst.iloc[0]})
stints = pd.DataFrame(st)
for r in stints.itertuples():
    fact(f'st{r.stint}_best', r.best, f'スティント{r.stint}のベスト（秒）')
    fact(f'st{r.stint}_median', r.median, f'スティント{r.stint}の通常の周の中央値（秒）')
    fact(f'st{r.stint}_slope', r.slope, f'スティント{r.stint}の1周ごとのタイムの伸び（秒/周）')
    fact(f'st{r.stint}_oilrise', r.oil_rise, f'スティント{r.stint}の油温の上がり方（℃/周）')
    fact(f'st{r.stint}_oilmax', r.oil_max, f'スティント{r.stint}の油温の最高（℃）')

# ---------- ピット ----------
pits = []
for lap, no in PIT_LAPS.items():
    g = race[race.lap == lap]
    stop = g[g.GPSSpeed < 2]
    s = stints.set_index('stint').loc[STINT_OF(lap), 'median']
    lt = float(laps_r.set_index('lap').loc[lap, 'lap_s'])
    pits.append({'pit': no, 'lap': lap, 'stop_from': stop.t.iloc[0].tz_convert(JST).strftime('%H:%M:%S'),
                 'stop_to': stop.t.iloc[-1].tz_convert(JST).strftime('%H:%M:%S'),
                 'stopped_s': round(len(stop) / 100, 0), 'engine_off_s': round(float((stop.RPM.isna() | (stop.RPM < 300)).sum() / 100), 0),
                 'lap_s': round(lt, 1), 'loss_s': round(lt - s, 1), 'moving_loss_s': round(lt - s - len(stop) / 100, 1)})
pits = pd.DataFrame(pits)
for r in pits.itertuples():
    fact(f'pit{r.pit}_stop', r.stopped_s, f'ピット{r.pit}で止まっていた秒')
    fact(f'pit{r.pit}_stopmin', round(r.stopped_s / 60, 1), f'ピット{r.pit}で止まっていた分')
    fact(f'pit{r.pit}_off', r.engine_off_s, f'ピット{r.pit}でエンジンが止まっていた秒')
    fact(f'pit{r.pit}_offmin', round(r.engine_off_s / 60, 1), f'ピット{r.pit}でエンジンが止まっていた分')
    fact(f'pit{r.pit}_moving', r.moving_loss_s, f'ピット{r.pit}の止まっていた時間を除いた損失（秒）')
    fact(f'pit{r.pit}_from', r.stop_from, f'ピット{r.pit}で止まった時刻'); fact(f'pit{r.pit}_to', r.stop_to, f'ピット{r.pit}で動き出した時刻')

# ピット前の遅い周
slow = []
for a, b in PRE_PIT:
    g = laps_r[laps_r.lap.between(a, b)]
    s = stints.set_index('stint').loc[STINT_OF(a), 'median']
    before = laps_r.set_index('lap').loc[a - 1]
    slow.append({'from': a, 'to': b, 'lost_s': round(float((g.lap_s - s).sum()), 1),
                 'oil_before': before.oil_max, 'oil_after': float(g.oil_avg.iloc[-1])})
for i, r in enumerate(slow, 1):
    fact(f'slow{i}_lost', r['lost_s'], f'ピット{i}の前の遅い3周で失った秒（通常の周の中央値と比べて）')
    fact(f'slow{i}_oilbefore', r['oil_before'], f'ピット{i}の前の遅い周に入る前の周の油温の最高（℃）')
    fact(f'slow{i}_oilafter', round(r['oil_after'], 1), f'ピット{i}の前の遅い周の最後の周の油温の平均（℃）')

# ---------- 油温・水温の時系列（10秒ごと） ----------
r = race[race.t >= W0].copy()
r['bin'] = r.t.dt.floor('10s')
tl = r.groupby('bin').agg(oil=('oil', 'mean'), water=('WaterTemp', 'mean'), wdefi=('wdefi', 'mean'),
                          kpa=('kpa', 'mean'), speed=('GPSSpeed', 'mean'), rpm=('RPM', 'mean'), lap=('lap', 'last')).reset_index()
tl['time_jst'] = tl.bin.dt.tz_convert(JST).dt.strftime('%H:%M:%S')
tl = tl.drop(columns='bin').round(1)
on = race[race.lap.isin(RACE_LAPS) & (race.GPSSpeed > 20)]
for lim in (110, 120):
    fact(f'oil_over{lim}_s', round(float((on.oil >= lim).sum() / 100), 0), f'決勝で走っている間に油温が{lim}℃以上だった秒')
fact('oil_race_max', round(float(on.oil.max()), 1), '決勝で走っている間の油温の最高（℃）')
fact('water_race_max', float(on.WaterTemp.max()), '決勝で走っている間の水温（車のCAN）の最高（℃）')
fact('wdefi_race_max', round(float(on.wdefi.max()), 1), '決勝で走っている間の水温（Defi）の最高（℃）')
# 水温：CAN vs Defi
wc = race[race.defi_ok & race.WaterTemp.notna() & race.wdefi.notna() & (race.RPM > 500)]
wv = wc.groupby('WaterTemp').agg(defi=('wdefi', 'median'), defi_lo=('wdefi', lambda s: s.quantile(.1)),
                                  defi_hi=('wdefi', lambda s: s.quantile(.9)), n=('wdefi', 'size')).reset_index()
wv = wv[wv.n >= 500].round(1)
hot = wc[wc.WaterTemp >= 85]
fact('water_offset', round(float((hot.wdefi - hot.WaterTemp).median()), 1), '水温85℃以上でのDefi−車のCANの差の中央値（℃）')
cold = wc[wc.WaterTemp <= 75]
fact('water_offset_cold', round(float((cold.wdefi - cold.WaterTemp).median()), 1) if len(cold) else None, '水温75℃以下でのDefi−車のCANの差の中央値（℃）')
oilw = race[race.defi_ok & (race.GPSSpeed > 20) & race.WaterTemp.notna() & race.lap.isin(RACE_LAPS)]
fact('oil_minus_water', round(float((oilw.oil - oilw.WaterTemp).median()), 1), '走っている間の油温−水温の中央値（℃）')

# ---------- 基準の周（ベスト）で道のりを決める ----------
def gnss_points(g):
    m = (g.Lat.diff() != 0) | (g.Lon.diff() != 0)
    return g[m & g.Lat.notna()]

refg = gnss_points(race[race.lap == REF])
P = np.c_[refg.x.values, refg.y.values]
seg = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
L = float(seg[-1] + np.hypot(*(P[0] - P[-1])))
dense_s = np.arange(0, seg[-1], 0.5)
DX = np.interp(dense_s, seg, P[:, 0]); DY = np.interp(dense_s, seg, P[:, 1])
tree = cKDTree(np.c_[DX, DY])
fact('track_len', round(L, 0), '基準の周で測ったコースの長さ（m）')

def project(g):
    """各行の道のり s（m、ラインから）。GNSSの点を基準の線へ投影し、時刻で全行へ補間。"""
    pts = gnss_points(g)
    if len(pts) < 50: return None
    dist, idx = tree.query(np.c_[pts.x.values, pts.y.values], k=40, distance_upper_bound=60)
    out = np.full(len(pts), np.nan); prev = 0.0; tprev = pts.ts.values[0]
    for i in range(len(pts)):
        ok = np.isfinite(dist[i])
        if not ok.any(): continue
        cand = dense_s[idx[i][ok]]; dd = dist[i][ok]
        pred = prev + max(pts.GPSSpeed.values[i], 0) / 3.6 * (pts.ts.values[i] - tprev)
        cand = np.where(cand - pred > L / 2, cand - L, cand)       # ライン直後で末尾側に吸われないように
        near = dd <= dd.min() + 6
        j = np.argmin(np.abs(cand[near] - pred))
        out[i] = cand[near][j]; prev = out[i]; tprev = pts.ts.values[i]
    s = pd.Series(out).interpolate(limit_direction='both').values
    s = np.maximum.accumulate(np.clip(s, -50, L + 50))
    return np.interp(g.ts.values, pts.ts.values, s)

lapdata = {}
def lap_rows(d, n):
    g = d[d.lap == n].copy()
    s = project(g)
    if s is None: return None
    g['s'] = s; g['tl'] = g.ts - g.ts.iloc[0]
    return g
ref = lap_rows(race, REF); lapdata[('決勝', REF)] = ref
grid = np.arange(0, int(L), 5.0)
def at(g, col, sgrid=grid):
    gg = g[[col, 's']].dropna().drop_duplicates('s')
    return np.interp(sgrid, gg.s.values, gg[col].values)
ref_t = at(ref, 'tl')

# 走りの比べる周：決勝の全周＋予選
for sess, d, rng in (('決勝', race, list(RACE_LAPS)), ('予選', quali, list(QUALI_LAPS))):
    for n in rng:
        if (sess, n) not in lapdata:
            g = lap_rows(d, n)
            if g is not None: lapdata[(sess, n)] = g

# ギア：km/h÷(rpm/1000)。205/50R16・ファイナル4.100・6MTの比から計算した値を、データの山に合わせて縮める
RATIOS = [3.815, 2.260, 1.640, 1.177, 1.000, 0.832]
circ = 2 * np.pi * 0.3057
theory = np.array([1000 / (g_ * 4.1) * circ * 60 / 1000 for g_ in RATIOS])
rr = race[(race.Speed > 30) & (race.RPM > 2000) & (race.ClutchDisengaged == 0) & (race.Throttle > 30)]
k = (rr.Speed / (rr.RPM / 1000)).values
scale = np.median([np.median(k[np.abs(k / t - np.median(k[np.abs(k / t - 1) < .06] / t)) < .03]) / t for t in theory[[1, 2, 3]]])
gears_k = theory * scale
def gear_of(df):
    kk = (df.Speed / (df.RPM / 1000)).values
    gi = np.argmin(np.abs(kk[:, None] / gears_k[None, :] - 1), axis=1)
    err = np.abs(kk / gears_k[gi] - 1)
    out = np.where((err < 0.04) & (df.Speed.values > 8) & (df.ClutchDisengaged.values == 0), gi + 1, 0)
    return out
fact('gear_scale', round(float(scale), 3), '車速の換算の縮め（データ÷計算）')
normal_laps = set(laps[laps.kind == '通常'].lap)
on = race[race.lap.isin(normal_laps)].copy()
on['gear'] = gear_of(on)
fact('rev_s_per_lap', round(float((on.RPM >= 7800).sum() / 100 / len(normal_laps)), 1), '通常の周で7800rpm以上だった秒（1周あたり）')
fact('gear4_top', round(float(on.Speed[on.gear == 4].quantile(.999)), 0), '4速での最高速（km/h、上位0.1%）')
fact('gear4_top_rpm', round(float(on.RPM[on.gear == 4].quantile(.999)), 0), '4速での最高回転（rpm、上位0.1%）')
fact('gear5_top_rpm', round(float(on.Speed[on.gear == 4].quantile(.999) / gears_k[4] * 1000), 0), 'その速度を5速で走ったときの回転（rpm）')
gs = []
for gi in range(1, 7):
    m = on.gear == gi
    shift_up = on[(on.gear.shift(-1) == gi + 1)]
    gs.append({'gear': gi, 'name': f'{gi}速', 'kmh_per_1000': round(float(gears_k[gi - 1]), 2),
               'share': round(float(m.sum() / max((on.gear > 0).sum(), 1)), 4),
               'rpm_med': round(float(on.RPM[m].median()), 0) if m.any() else None,
               'vmax': round(float(on.Speed[m].quantile(.995)), 0) if m.sum() > 100 else None})
gears = pd.DataFrame(gs)
# シフトアップの回転：あるギアが0.5秒以上続いたあと、次のギアへ（クラッチを切る直前の回転）
ups = []
gv = on.gear.values; rpm = on.RPM.values; ts = on.ts.values
cur = 0; cur_t = 0; last_rpm = np.nan
for i in range(1, len(gv)):
    if gv[i] > 0:
        if gv[i] != cur:
            if cur > 0 and gv[i] == cur + 1 and ts[i] - cur_t > 0.5 and ts[i] - last_t < 1.5:
                ups.append({'from': cur, 'to': gv[i], 'rpm': last_rpm})
            cur = gv[i]; cur_t = ts[i]
        last_rpm = rpm[i]; last_t = ts[i]
ups = pd.DataFrame(ups)
up_tab = ups.groupby(['from', 'to']).rpm.agg(['count', 'median', lambda s: s.quantile(.1), lambda s: s.quantile(.9)]).reset_index()
up_tab.columns = ['from', 'to', 'count', 'rpm_med', 'rpm_p10', 'rpm_p90']
up_tab['name'] = up_tab['from'].astype(str) + '→' + up_tab['to'].astype(str) + '速'
up_tab = up_tab[up_tab['count'] >= 10].round(0)
fact('rpm_race_max', round(float(on.RPM.quantile(.999)), 0), '決勝の回転の上位0.1%（rpm）')
fact('gear5_share', round(float(gears.set_index('gear').loc[5, 'share']) * 100, 1), '5速で走っていた時間の割合（%）')
fact('gear6_share', round(float(gears.set_index('gear').loc[6, 'share']) * 100, 1), '6速で走っていた時間の割合（%）')
fact('gear2_share', round(float(gears.set_index('gear').loc[2, 'share']) * 100, 1), '2速で走っていた時間の割合（%）')

# ---------- コースの線（基準の周、5mごと） ----------
ref['gear'] = gear_of(ref)
tr = pd.DataFrame({'s': grid})
tr['x'] = at(ref, 'x'); tr['y'] = at(ref, 'y')
for c in ('Speed', 'Throttle', 'RPM', 'LatAccel', 'LongAccel', 'kpa', 'oil'):
    tr[c] = at(ref, c)
tr['gear'] = np.round(np.interp(grid, ref.s.values, ref.gear.values.astype(float)))
# コーナー：基準の周の速度の谷
v = pd.Series(tr.Speed).rolling(5, center=True, min_periods=1).mean().values
pk, pr = find_peaks(-v, prominence=12, distance=16)
corners = pd.DataFrame({'corner': np.arange(1, len(pk) + 1), 's': grid[pk], 'vmin_ref': v[pk].round(1),
                        'x': tr.x.values[pk].round(1), 'y': tr.y.values[pk].round(1)})
corners['name'] = 'C' + corners.corner.astype(str)
# 区間：コーナーとコーナーの間の速度の山で区切る
bounds = [0.0]
for a, b in zip(pk[:-1], pk[1:]):
    bounds.append(float(grid[a + np.argmax(v[a:b])]))
bounds.append(float(grid[-1]))
corners['seg_from'] = bounds[:-1]; corners['seg_to'] = bounds[1:]
corners.loc[0, 'seg_from'] = 0.0
tr['corner'] = np.searchsorted(np.array(bounds[1:-1]), grid, side='right') + 1
fact('n_corners', len(corners), '基準の周の速度の谷（ブレーキを踏むコーナー）の数')

# ---------- 周ごとの道のりの比較 ----------
cmp_rows = []; seg_rows = []; corner_rows = []; ggp = []
def lap_label(sess, n):
    return ('予選' if sess == '予選' else '') + f'{n}周目'
for (sess, n), g in lapdata.items():
    lt = laps[(laps.session == sess) & (laps.lap == n)]
    if lt.empty: continue
    lt = lt.iloc[0]
    if g.s.max() < L * 0.97: continue
    t = at(g, 'tl'); vv = at(g, 'Speed')
    dt = t - ref_t
    # 区間ごとの時間
    for c in corners.itertuples():
        i0 = int(c.seg_from // 5); i1 = min(int(c.seg_to // 5), len(grid) - 1)
        seg_rows.append({'session': sess, 'lap': n, 'kind': lt.kind, 'stint': lt.stint, 'corner': c.corner,
                         'seg_s': round(float(t[i1] - t[i0]), 3)})
        w = (grid >= c.s - 60) & (grid <= c.s + 60)
        # ブレーキ：コーナーの手前300mで-0.3G以下が続いた区間の始まり
        prev_s = corners.s[corners.corner == c.corner - 1]
        lo = max(c.s - 300, float(prev_s.iloc[0]) + 30) if len(prev_s) else c.s - 300
        gg = g[(g.s > lo) & (g.s < c.s + 20)]
        br = gg.LongAccel.rolling(10, center=True, min_periods=1).mean().values < -0.3
        brake_m = None
        if br.any():
            j = np.where(br)[0]
            runs = np.split(j, np.where(np.diff(j) > 5)[0] + 1)
            run = max(runs, key=len)
            if len(run) > 20: brake_m = float(c.s - gg.s.values[run[0]])
        ga = g[(g.s > c.s) & (g.s < c.s + 250)]
        thr = ga[ga.Throttle > 55]
        corner_rows.append({'session': sess, 'lap': n, 'kind': lt.kind, 'stint': lt.stint, 'corner': c.corner,
                            'vmin': round(float(vv[w].min()), 1), 'brake_m': None if brake_m is None else round(brake_m, 0),
                            'throttle_m': round(float(thr.s.iloc[0] - c.s), 0) if len(thr) else None})
    if lt.kind in ('通常', '予選') or n == REF:
        step = 2   # 10mごと
        for i in range(0, len(grid), step):
            cmp_rows.append({'session': sess, 'lap': n, 'label': lap_label(sess, n), 'stint': lt.stint, 's': grid[i],
                             'speed': round(float(vv[i]), 1), 'delta': round(float(dt[i]), 3)})
    # G-G：周ごとの上位5%の合成G
    if lt.kind in ('通常', '予選', 'ピット明け'):
        m = g.GPSSpeed > 40
        comb = np.hypot(g.LatAccel[m], g.LongAccel[m])
        ggp.append({'session': sess, 'lap': n, 'stint': lt.stint, 'kind': lt.kind,
                    'g95': round(float(comb.quantile(.95)), 3), 'lat95': round(float(g.LatAccel[m].abs().quantile(.95)), 3),
                    'brake95': round(float((-g.LongAccel[m]).quantile(.98)), 3)})
cmp = pd.DataFrame(cmp_rows); segs = pd.DataFrame(seg_rows); crn = pd.DataFrame(corner_rows); ggl = pd.DataFrame(ggp)
laps = laps.merge(ggl[['session', 'lap', 'g95', 'lat95', 'brake95']], on=['session', 'lap'], how='left')

# 区間ごとの「その区間のベスト」との差を、スティントごとに平均
base = segs[segs.kind.isin(['通常', '予選'])]
segbest = base.groupby('corner').seg_s.min()
fact('theo_seg', round(float(segbest.sum()), 3), '区間（コーナーごと）のベストの和（秒）')
loss = base.assign(loss=lambda x: x.seg_s - x.corner.map(segbest))
seg_loss = loss.groupby(['stint', 'corner']).loss.mean().unstack(0).round(3)
seg_loss.columns = ['q' if c == 0 else f'st{c}' for c in seg_loss.columns]
seg_loss = seg_loss.reset_index().merge(corners[['corner', 'name', 's', 'vmin_ref', 'seg_from', 'seg_to']], on='corner')
refseg = segs[(segs.session == '決勝') & (segs.lap == REF)].set_index('corner').seg_s
seg_loss['ref'] = (refseg - segbest).round(3).values
seg_loss['best_s'] = segbest.round(3).values
seg_loss['best_lap'] = [lap_label(*base.loc[base[base.corner == c].seg_s.idxmin(), ['session', 'lap']]) for c in seg_loss.corner]
# コーナーごとの走り（スティントごとの中央値）
cb = crn[crn.kind.isin(['通常', '予選'])]
csum = cb.groupby(['corner', 'stint']).agg(vmin=('vmin', 'median'), brake_m=('brake_m', 'median'), throttle_m=('throttle_m', 'median')).reset_index()
cref = crn[(crn.session == '決勝') & (crn.lap == REF)][['corner', 'vmin', 'brake_m', 'throttle_m']].rename(columns=lambda c: c if c == 'corner' else c + '_ref')
cw = csum.pivot(index='corner', columns='stint')
cw.columns = [f'{a}_q' if b == 0 else f'{a}_st{b}' for a, b in cw.columns]
cw = cw.reset_index().merge(cref, on='corner').merge(corners[['corner', 'name', 's']], on='corner').round(1)
worst = seg_loss.assign(m=seg_loss[['st1', 'st2', 'st3']].mean(axis=1)).sort_values('m', ascending=False)
for i, r in enumerate(worst.head(3).itertuples(), 1):
    fact(f'loss{i}_name', r.name, f'通常の周で区間のベストから最も遅れている区間（{i}番目）')
    fact(f'loss{i}_s', round(float(r.m), 2), f'その区間の平均の遅れ（秒、3スティントの平均）')
fact('seg_loss_total', round(float(worst.m.sum()), 2), '通常の周の区間のベストの和からの遅れの合計（秒、3スティントの平均）')

# 比べる周の一覧
pick = {('決勝', REF): 'ベスト'}
for r in stints.itertuples():
    if r.best_lap != REF: pick[('決勝', r.best_lap)] = f'スティント{r.stint}のベスト'
pick[('予選', int(qb.lap))] = '予選のベスト'
# 決勝の通常の周で中央値に最も近い周
cl = laps[(laps.kind == '通常')]
mid = cl.iloc[(cl.lap_s - cl.lap_s.median()).abs().argsort().iloc[0]]
pick[('決勝', int(mid.lap))] = 'ふつうの周（中央値に近い）'
cmp['role'] = [pick.get((a, b), '') for a, b in zip(cmp.session, cmp.lap)]
cmp_sel = cmp[cmp.role != ''].copy()
cmp_sel['label'] = cmp_sel.label + '（' + cmp_sel.role + '）'
fact('mid_lap', int(mid.lap), 'ふつうの周（中央値に近い周）')
fact('mid_lap_s', float(mid.lap_s), 'ふつうの周のタイム（秒）')

# G-G（基準の周、0.1秒ごと）
ggref = ref.iloc[::10][['s', 'LatAccel', 'LongAccel', 'Speed']].dropna().round(3)
fact('ref_g95', float(ggl[(ggl.session == '決勝') & (ggl.lap == REF)].g95.iloc[0]), 'ベストの周の合成Gの上位5%（G）')
for r in stints.itertuples():
    q = ggl[(ggl.stint == r.stint) & (ggl.kind == '通常')]
    fact(f'st{r.stint}_g95', round(float(q.g95.median()), 3), f'スティント{r.stint}の通常の周の合成G（上位5%の中央値、G）')
lr = race[(race.GPSSpeed > 60) & race.lap.isin(RACE_LAPS)]
fact('lat_max_pos', round(float(lr.LatAccel.quantile(.999)), 2), '横Gの＋側の上位0.1%（G）')
fact('lat_max_neg', round(float(-lr.LatAccel.quantile(.001)), 2), '横Gの−側の上位0.1%（G）')

# ---------- 油圧 × G ----------
rp = race[race.lap.isin(RACE_LAPS) & race.kpa.notna() & race.RPM.notna() & (race.RPM > 1500) & (race.oil > 85)].copy()
rp = rp[rp.PressVolt.diff() != 0]               # 油圧が新しく届いた行だけ（約9回/秒）
rp['rpm_bin'] = (rp.RPM // 250 * 250).astype(int)
calm = rp[np.hypot(rp.LatAccel, rp.LongAccel) < 0.3]
curve = calm.groupby('rpm_bin').kpa.agg(['median', 'size']).query('size >= 30')['median']
rp['expect'] = np.interp(rp.RPM, curve.index + 125, curve.values)
rp['ratio'] = rp.kpa / rp.expect
press_rpm = calm.groupby('rpm_bin').kpa.agg(med='median', p10=lambda s: s.quantile(.1), p90=lambda s: s.quantile(.9), n='size').query('n >= 30').reset_index().round(0)
rp['lat_bin'] = (rp.LatAccel / 0.1).round() / 10
rp['long_bin'] = (rp.LongAccel / 0.1).round() / 10
pl = rp[rp.RPM > 3500].groupby('lat_bin').ratio.agg(med='median', p05=lambda s: s.quantile(.05), n='size').query('n >= 40').reset_index().round(3)
plong = rp[rp.RPM > 3500].groupby('long_bin').ratio.agg(med='median', p05=lambda s: s.quantile(.05), n='size').query('n >= 40').reset_index().round(3)
fact('press_6000', float(curve.loc[curve.index[np.argmin(np.abs(curve.index - 6000))]]), '6000rpm・Gが小さいときの油圧の中央値（kPa）')
fact('press_3000', float(curve.loc[curve.index[np.argmin(np.abs(curve.index - 3000))]]), '3000rpm・Gが小さいときの油圧の中央値（kPa）')
# 油圧が下がった出来事：期待の70%未満が0.3秒以上、3000rpm以上
rp = rp.sort_values('ts')
low = (rp.ratio < 0.7) & (rp.RPM > 3000)
ev = []
grp = (low != low.shift()).cumsum()
for _, g in rp[low].groupby(grp[low]):
    if g.ts.iloc[-1] - g.ts.iloc[0] < 0.25: continue
    i = g.kpa.idxmin(); r0 = g.loc[i]
    w = race[(race.ts >= g.ts.iloc[0] - 0.5) & (race.ts <= g.ts.iloc[-1] + 0.2)]
    ev.append({'time_jst': r0.t.tz_convert(JST).strftime('%H:%M:%S'), 'lap': int(r0.lap), 'stint': STINT_OF(int(r0.lap)),
               'kpa': round(float(r0.kpa), 0), 'expect': round(float(r0.expect), 0), 'ratio': round(float(r0.ratio), 2),
               'rpm': round(float(r0.RPM), 0), 'lat': round(float(w.LatAccel.mean()), 2), 'long': round(float(w.LongAccel.mean()), 2),
               'speed': round(float(r0.Speed), 0), 'dur_s': round(float(g.ts.iloc[-1] - g.ts.iloc[0] + 0.11), 2),
               'x': round(float(r0.x), 1), 'y': round(float(r0.y), 1), 'oil': round(float(r0.oil), 0)})
pev = pd.DataFrame(ev)
if len(pev):
    _, ii = cKDTree(np.c_[tr.x, tr.y]).query(np.c_[pev.x, pev.y])
    pev['s'] = tr.s.values[ii]; pev['corner'] = tr.corner.values[ii]
    pev['name'] = 'C' + pev.corner.astype(str)
    pev['id'] = pev.time_jst
fact('press_events', len(pev), '油圧が期待の7割を0.25秒以上下回った回数（3000rpm以上）')
if len(pev):
    top = pev.name.value_counts()
    fact('press_ev_corner', top.index[0], '油圧が下がった回数が最も多いコーナー')
    fact('press_ev_corner_n', int(top.iloc[0]), 'そのコーナーでの回数')
    fact('press_ev_min', float(pev.kpa.min()), '油圧が下がったときの最低（kPa）')
    fact('press_ev_latsign', round(float((np.sign(pev.lat) == np.sign(pev.lat.median())).mean() * 100), 0), '油圧が下がったときの横Gが同じ向きだった割合（%）')
    fact('press_ev_lat_med', round(float(pev.lat.abs().median()), 2), '油圧が下がったときの横Gの大きさの中央値（G）')

# ---------- 一か所で減速した周 ----------
for n in INCIDENT:
    g = lapdata[('決勝', n)]
    gg = g[(g.s > 50) & (g.s < L - 300)]
    i = gg.GPSSpeed.idxmin(); r0 = gg.loc[i]
    ci = int(tr.corner.values[np.argmin(np.abs(tr.s.values - r0.s))])
    fact(f'inc{n}_v', round(float(r0.GPSSpeed), 0), f'{n}周目でいちばん遅くなった速度（km/h）')
    fact(f'inc{n}_s', round(float(r0.s), -1), f'{n}周目でいちばん遅くなった道のり（m）')
    fact(f'inc{n}_c', f'C{ci}', f'{n}周目でいちばん遅くなった区間')
    fact(f'inc{n}_jst', r0.t.tz_convert(JST).strftime('%H:%M:%S'), f'{n}周目でいちばん遅くなった時刻')
    fact(f'inc{n}_stop', round(float((g.GPSSpeed < 2).sum() / 100), 1), f'{n}周目に止まっていた秒')
    fact(f'inc{n}_lost', round(float(laps.set_index(['session', 'lap']).loc[('決勝', n), 'lap_s'] - med[STINT_OF(n)]), 1), f'{n}周目に通常の周の中央値から遅れた秒')
for a, b in SLOW_PAIRS:
    r_ = laps[(laps.session == '決勝') & laps.lap.between(a, b)]
    fact(f'slowall{a}_ratio', round(float((r_.lap_s / med[STINT_OF(a)]).mean() * 100 - 100), 0), f'{a}・{b}周目が通常の周の中央値より遅かった割合（%）')

# ---------- 燃料 ----------
fuel = laps_r[['lap', 'fuel', 'stint']].copy()
fact('fuel_last', float(race[race.lap == LAST_LAP + 1].FuelLevelRaw.median()), 'チェッカーのあとの燃料の値（%）')
fl = laps_r[laps_r.fuel <= round(float(race.FuelLevelRaw.min()), 1) + 0.05]
fact('fuel_floor_lap', int(fl.lap.min()), '周の中央値が下限の値になった最初の周')
fact('fuel_floor', round(float(race.FuelLevelRaw.min()), 2), '燃料の値の下限（%）')
for s in range(1, len(STINTS)):
    g = fuel[(fuel.stint == s) & ~fuel.lap.isin(PIT_LAPS)]
    fact(f'fuel_rate{s}', round(float(-np.polyfit(g.lap, g.fuel, 1)[0]), 2), f'スティント{s}の燃料の値の減り方（%/周）')

# ---------- ロガー自体 ----------
rl = race[race.t.between(W0, W1)].copy()
dt_ms = rl.mcu_ms.diff()
fact('emmc_gap_n', int((dt_ms > 100).sum()), f'記録の行の間が0.1秒より開いた回数（{CFG["window"][0]}〜{CFG["window"][1]}）')
fact('emmc_gap_max', round(float(dt_ms.max() / 1000), 2), '記録の行の間の最大（秒）')
fact('emmc_rate', round(float(len(rl) / ((rl.mcu_ms.iloc[-1] - rl.mcu_ms.iloc[0]) / 1000)), 1), '記録の行の数（行/秒）')
run_on = rl[(rl.GPSSpeed > 5)]
fact('can1_missing_moving', round(float(run_on.RPM.isna().mean() * 100), 2), '走っている間に車のCANの値が無かった割合（%）')
fact('can2_lost_s', round(float((rl.PressVoltState == 4).sum() / 100), 1), 'センサーハブ（CAN2）の通信途絶の秒')
c2 = rl[rl.PressVoltState == 4]
fact('can2_lost_n', int(((rl.PressVoltState == 4).astype(int).diff() == 1).sum()), 'センサーハブの通信途絶の回数')
fact('gnss_full', round(float((run_on.GNSSHz >= 9.5).mean() * 100), 1), '走っている間にGNSSが10Hzだった割合（%）')
fact('gnss_sats', float(run_on.GPSSats.median()), '走っている間の衛星の数の中央値')
fact('gnss_hacc', round(float(run_on.gnss_hacc_m.median()), 2), '走っている間の水平の精度の中央値（m）')
fact('gnss_hacc95', round(float(run_on.gnss_hacc_m.quantile(.95)), 2), '水平の精度の上位5%（m）')
# 1分ごと
rl['min'] = rl.t.dt.floor('1min')
lg = rl.groupby('min').agg(gnss_hz=('GNSSHz', 'mean'), sats=('GPSSats', 'median'), hacc=('gnss_hacc_m', 'median'),
                           speed=('GPSSpeed', 'mean'), can1=('RPM', lambda s: s.notna().mean()),
                           can2_lost=('PressVoltState', lambda s: (s == 4).mean())).reset_index()
# LTE（5Bに届いたもの）
LTE_FILES = sorted(glob.glob(os.path.join(RP(CFG['lte_dir']), '*.jsonl')))
def lte_samples(path):
    """サーバーのJSON Lines（meta＋samples）。各点は値の並び＋どの値があるかのビットマスク（race_csv.pyと同じ読み方）。"""
    names = None
    for line in open(path, encoding='utf-8'):
        entry = json.loads(line)
        if 'meta' in entry: names = [m['nm'] for m in entry['meta']]
        for row in entry.get('samples', []) or []:
            n = (len(names) + 31) // 32
            values, masks = row[:-n], row[-n:]
            k = 0; utc = None
            for i, name in enumerate(names):
                if int(masks[i // 32]) >> (i % 32) & 1:
                    if name == 'Utc': utc = values[k]; break
                    k += 1
            if utc is not None: yield entry['recv_ms'], utc
lte = []
for f in LTE_FILES:
    lte.extend(lte_samples(f))
lte = pd.DataFrame(lte, columns=['recv_ms', 'utc_ms']).drop_duplicates('utc_ms')
lte['t'] = pd.to_datetime(lte.utc_ms, unit='ms', utc=True)
lte['delay'] = (lte.recv_ms - lte.utc_ms) / 1000
lte['min'] = lte.t.dt.floor('1min')
lm = lte.groupby('min').agg(lte_n=('utc_ms', 'size'), lte_delay=('delay', 'median'), lte_delay95=('delay', lambda s: s.quantile(.95))).reset_index()
lg = lg.merge(lm, on='min', how='left')
lg['lte_n'] = lg.lte_n.fillna(0)
lg['time_jst'] = lg['min'].dt.tz_convert(JST).dt.strftime('%H:%M')
lg = lg.drop(columns='min').round(3)
R0 = race[race.lap == START_LAP].t.iloc[0]; R1 = race[race.lap == LAST_LAP + 1].t.iloc[0]   # スタートからチェッカーまで
win = lte[lte.t.between(R0, R1)].sort_values('utc_ms')
dur = (R1 - R0).total_seconds()
fact('lte_rate', round(len(win) / dur, 2), '決勝の間にLTEで届いた点の数（点/秒）')
gaps = np.diff(win.utc_ms.values) / 1000
fact('lte_gap_max', round(float(gaps.max()), 0), '決勝の間でLTEの点が途切れた最長（秒）')
fact('lte_gap30_n', int((gaps > 30).sum()), '決勝の間でLTEが30秒より長く途切れた回数')
fact('lte_gap30_total', round(float(gaps[gaps > 30].sum() / 60), 1), 'その途切れの合計（分）')
fact('lte_delay_med', round(float(win.delay.median()), 1), 'LTEの遅れの中央値（秒）')
fact('lte_delay95', round(float(win.delay.quantile(.95)), 1), 'LTEの遅れの上位5%（秒）')
fact('lte_files', len(LTE_FILES), '5Bに残ったその日の受信のファイルの数（つなぎ直すたびに増える）')
# 周の通過がLTEで届いたか（ピットのタイム表）
crossings = race[race.LapCount.diff() == 1][['t']].copy()
crossings['ms'] = ((crossings.t - pd.Timestamp('1970-01-01', tz='UTC')).dt.total_seconds() * 1000).round()
got = [((win.utc_ms > m - 0) & (win.utc_ms < m + 15000)).any() for m in crossings.ms]
fact('lte_lap_seen', round(float(np.mean(got) * 100), 0), 'ラインを通ってから15秒以内にLTEで点が届いた周の割合（%）')

# ---------- タイヤの滑り（車の向きと進む向き・四輪の車輪速） ----------
# 車の向きは GyroZ（左回りが正、deg/s）を足し合わせて出し、進む向きは GNSS の位置から出す。その差が車体の横滑り角β。
# ログの Yaw の列は GNSS の進む向き（方位）で、車の向きではないので使えない。
# 舵角が無いと前のタイヤの滑り角が出せないので、アンダーステアは出せない。出せるのは「後ろが出た」向き（βが大きい）だけ。
# 四輪の車輪速はタイヤの前後の滑り（立ち上がりの後輪の空転・ブレーキで前輪がロックしかけた所）に使う。
TREAD_F, TREAD_R = CFG.get('tread_m', [1.490, 1.495])      # 前後のトレッド（m）
SLIDE_DEG = 8.0          # これを超えたら「後ろが出た」とする横滑り角（ふつうのコーナーの最大は中央値5°前後）
LOCK_PCT = 10.0          # ブレーキで前輪が車の速さよりこれ以上遅ければ「ロックぎみ」
def tire_slip():
    d = race
    dt = d.ts.diff().fillna(0).clip(0, 0.05)
    v = (d.GPSSpeed / 3.6).clip(lower=5)
    psi_raw = np.cumsum(d.GyroZ.fillna(0) * dt)
    g = gnss_points(d).copy()
    g['cog'] = np.degrees(np.unwrap(np.arctan2(g.y.shift(-1) - g.y.shift(1), g.x.shift(-1) - g.x.shift(1)).bfill().ffill()))
    st = g.lap.isin(normal_laps) & (g.GPSSpeed > 60) & (g.LatAccel.abs() < 0.05) & (g.GyroZ.abs() < 2)
    fact('yaw_vs_cog', round(float(((g.Yaw - (90 - g.cog) + 180) % 360 - 180)[st].median()), 2), 'Yawの列とGNSSの進む向きの差（直線の中央値、°）。0ならYawは車の向きではない')
    # コーナー：|横G|>0.3 が1.5秒以上。入る1秒前と出た1秒後で、向きの変化を比べる
    g['in'] = (g.LatAccel.abs() > 0.3) & (g.GPSSpeed > 50)
    g['grp'] = (g['in'] != g['in'].shift()).cumsum()
    spans = []
    gts = g.ts.values
    for _, s in g[g['in']].groupby('grp'):
        t0, t1 = s.ts.iloc[0], s.ts.iloc[-1]
        if t1 - t0 < 1.5: continue
        i0 = np.searchsorted(gts, t0 - 1.0, side='right') - 1; i1 = np.searchsorted(gts, t1 + 1.0)
        if i0 < 0 or i1 >= len(g): continue
        pre, post = g.iloc[i0], g.iloc[i1]                    # 入る1秒前・出た1秒後のGNSSの点
        if not (pre.lap in normal_laps and post.lap in normal_laps) or post.ts - pre.ts > t1 - t0 + 2.6: continue
        spans.append((s, pre, post))
    dpsi = np.array([psi_raw[p2.name] - psi_raw[p1.name] for _, p1, p2 in spans])
    dcog = np.array([p2.cog - p1.cog for _, p1, p2 in spans])
    K = float(dpsi @ dcog / (dpsi @ dpsi))          # GyroZの倍率（取り付けの傾き・センサーの誤差）
    psi = psi_raw * K
    # GNSSを使わない出し方：β の変化 = 回る速さ − 横G÷速さ（向きを照らす用）
    bimu = np.degrees(np.cumsum((np.radians(d.GyroZ.fillna(0) * K) - (-d.LatAccel.fillna(0) * 9.81) / v) * dt))
    ev = []
    for s, pre, post in spans:
        turn = 1.0 if s.GyroZ.mean() > 0 else -1.0
        beta = ((psi[s.index] - psi[pre.name]) - (s.cog - pre.cog)) * turn      # 頭が進む向きより内を向くと正
        close = ((psi[post.name] - psi[pre.name]) - (post.cog - pre.cog)) * turn # 出たあと戻りきらない分＝誤差の目安
        im = beta.idxmax(); r0 = s.loc[im]
        after = d.loc[im: im + 150]                                              # βが最大になってから1.5秒
        ev.append({'id': r0.t.tz_convert(JST).strftime('%H:%M:%S'), 'time_jst': r0.t.tz_convert(JST).strftime('%H:%M:%S'),
                   'lap': int(r0.lap), 'stint': STINT_OF(int(r0.lap)), 'turn': '左' if turn > 0 else '右',
                   'x': round(float(r0.x), 1), 'y': round(float(r0.y), 1),
                   'speed': round(float(r0.GPSSpeed), 0), 'lat_max': round(float(s.LatAccel.abs().max()), 2),
                   'throttle': round(float(r0.Throttle), 0), 'beta_med': round(float(beta.median()), 1),
                   'beta_max': round(float(beta.max()), 1), 'beta_imu': round(float((bimu[im] - bimu[pre.name]) * turn), 1),
                   'yaw_back': round(float(max(0.0, -(after.GyroZ * K * turn).min())), 0), 'err': round(float(close), 1)})
    ev = pd.DataFrame(ev)
    _, ii = cKDTree(np.c_[tr.x, tr.y]).query(np.c_[ev.x, ev.y])
    ev['s'] = tr.s.values[ii]; ev['corner'] = tr.corner.values[ii]; ev['name'] = 'C' + ev.corner.astype(str)
    ev['ok'] = (ev.err.abs() < 3).astype(int)                                   # 戻りきらない分が3°未満なら確か
    ev['slide'] = ((ev.ok == 1) & (ev.beta_max > SLIDE_DEG) & (ev.beta_imu > 0.6 * ev.beta_max)).astype(int)
    mv = g[g.lap.isin(normal_laps) & (g.GPSSpeed > 60)]
    fact('gnss_pos_rate', round(float(len(mv) / mv.groupby('lap').ts.agg(lambda t: t.iloc[-1] - t.iloc[0]).sum()), 1), '走っている間（60km/h超）に記録の位置が変わった回数（回/秒）')
    fact('bal_k', round(K, 3), 'GyroZの倍率（コーナーの前後の向きの変化をGNSSに合わせた）')
    fact('bal_err', round(float(ev.err.abs().median()), 1), 'コーナーを出たあと向きが戻りきらない角度の中央値（°）＝横滑り角の誤差の目安')
    fact('bal_n', len(ev), '横滑り角を出したコーナーの数（通常の周、横G0.3超が1.5秒以上）')
    fact('bal_beta_med', round(float(ev.beta_med.median()), 1), 'コーナー中の横滑り角の中央値（°、頭が内向きが正）')
    fact('bal_beta_max_med', round(float(ev[ev.ok == 1].beta_max.median()), 1), 'コーナーごとの横滑り角の最大の中央値（°）')
    fact('slide_th', SLIDE_DEG, '「後ろが出た」とした横滑り角（°）')
    fact('slide_n', int(ev.slide.sum()), '後ろが出たコーナーの数（2つの出し方がそろったもの）')
    sl = ev[ev.slide == 1].sort_values('beta_max', ascending=False)
    for i, r in enumerate(sl.head(2).itertuples(), 1):
        for k_, v_, lab in (('lap', r.lap, '周'), ('jst', r.time_jst, '時刻'), ('c', r.name, '区間'), ('turn', r.turn, '向き'),
                            ('beta', r.beta_max, '横滑り角の最大（°、GNSS）'), ('imu', r.beta_imu, '横滑り角（°、GNSSを使わない出し方）'),
                            ('v', r.speed, '速度（km/h）'), ('back', r.yaw_back, '直後に逆へ回った速さ（deg/s）')):
            fact(f'slide{i}_{k_}', v_, f'{i}番目に大きく後ろが出た所：{lab}')
    # ---- 四輪の車輪速 ----
    W = pd.concat([lapdata[('決勝', n)] for n in sorted(normal_laps) if ('決勝', n) in lapdata])
    W = W[W.GPSSpeed > 60].copy()
    W['corner'] = np.searchsorted(np.array(bounds[1:-1]), W.s.values, side='right') + 1
    fl, fr, rl, rr_ = (W[k_] / 3.6 for k_ in ('WheelFrontA', 'WheelFrontB', 'WheelRearA', 'WheelRearB'))
    cn = W.LatAccel.abs() > 0.6
    fact('wheel_yaw_front', round(float((np.degrees((fr - fl) / TREAD_F) / (W.GyroZ * K))[cn].median()), 2), '前輪の左右差から出した回る速さ÷本当の回る速さ（横G0.6超）')
    fact('wheel_yaw_rear', round(float((np.degrees((rr_ - rl) / TREAD_R) / (W.GyroZ * K))[cn].median()), 2), '後輪の左右差から出した回る速さ÷本当の回る速さ（横G0.6超）')
    front = (fl + fr) / 2; rear = (rl + rr_) / 2
    t_off, t_full = W.Throttle.quantile(.05), W.Throttle.quantile(.99)
    coast = (W.Throttle <= t_off + 1) & (W.LongAccel.abs() < 0.05) & (W.LatAccel.abs() < 0.1)
    base = float((rear / front - 1)[coast].median())
    W['slip'] = (rear / front - 1 - base) * 100
    W['inner'] = ((rr_ - rl) - np.radians(W.GyroZ * K) * TREAD_R) * -np.sign(W.GyroZ) * 3.6
    ex = (W.Throttle >= t_full - 1) & (W.LatAccel.abs() > 0.4)
    fact('rear_base', round(base * 100, 2), '惰性の直線での後輪÷前輪−1（%、タイヤの径の差。空転はここから数える）')
    fact('rear_exit_med', round(float(W.slip[ex].median()), 1), '立ち上がり（全開・横G0.4超）の後輪の空転の中央値（%）')
    fact('rear_exit_p95', round(float(W.slip[ex].quantile(.95)), 1), '立ち上がりの後輪の空転の上位5%（%）')
    fact('inner_med', round(float(W.inner[ex].median()), 1), '立ち上がりで内側の後輪が本来より速く回った分の中央値（km/h）')
    # GNSSの速さは遅れて出るので、前輪の平均に合うようにずらしてからロックを数える
    m = race.lap.isin(normal_laps).values & (race.GPSSpeed > 60).values
    fv = ((race.WheelFrontA + race.WheelFrontB) / 2).values; gv = race.GPSSpeed.values
    lags = list(range(0, 41, 2))
    errs = [np.nanmedian(np.abs(fv[m][:-40] - np.roll(gv, -L_)[m][:-40])) for L_ in lags]
    lag = lags[int(np.argmin(errs))]
    vl = pd.Series(np.roll(gv, -lag), index=race.index).loc[W.index]
    steady = (W.LongAccel.abs() < 0.05) & (W.LatAccel.abs() < 0.1)
    fb = float((front * 3.6 / vl)[steady].median())
    W['lock'] = (np.minimum(W.WheelFrontA, W.WheelFrontB) / vl / fb - 1) * 100
    br = W.LongAccel < -0.6
    lk = br & (W.lock < -LOCK_PCT)
    fact('gnss_speed_lag', lag * 10, 'GNSSの速さの遅れ（ms、前輪の速さに合わせて求めた）')
    fact('lock_s', round(float(lk.sum() / 100), 1), f'ブレーキ（0.6G超）でどちらかの前輪が{LOCK_PCT:.0f}%以上遅かった秒（通常の周の合計）')
    fact('lock_laps', int(W.lap[lk].nunique()), 'それがあった周の数')
    fact('lock_th', LOCK_PCT, 'ロックぎみとした前輪の遅れ（%）')
    # コーナーごと
    rows = []
    for ci in sorted(corners.corner):
        e = ev[(ev.corner == ci) & (ev.ok == 1)]; w = W[W.corner == ci]
        rows.append({'corner': ci, 'beta_n': len(e),
                     'beta_med': round(float(e.beta_med.median()), 1) if len(e) else None,
                     'beta_p90': round(float(e.beta_max.quantile(.9)), 1) if len(e) else None,
                     'slides': int(ev[(ev.corner == ci)].slide.sum()),
                     'slip_med': round(float(w.slip[ex.loc[w.index]].median()), 1) if ex.loc[w.index].sum() > 50 else None,
                     'slip_p95': round(float(w.slip[ex.loc[w.index]].quantile(.95)), 1) if ex.loc[w.index].sum() > 50 else None,
                     'lock_s': round(float(lk.loc[w.index].sum() / 100), 1)})
    return ev, pd.DataFrame(rows)
slides, bal_corner = tire_slip()

# ---------- 書き出し ----------
laps_out = laps.drop(columns=['s1_best', 's2_best', 's3_best', 's4_best']).copy()
for k in ('s1', 's2', 's3', 's4'):
    laps_out[k + '_isbest'] = laps[k + '_best'].astype(int)
laps_out['key'] = laps_out.session + '-' + laps_out.lap.astype(str)
laps_out['lap_txt'] = [mmss(v) if v < 600 else f'{v / 60:.1f}分' for v in laps_out.lap_s]
laps_out['to_best_txt'] = ['' if v > 600 else f'+{v:.3f}' if v > 0 else ('ベスト' if v == 0 else f'{v:.3f}') for v in laps_out.to_best]
laps_out['name'] = laps_out.session + ' ' + laps_out.lap.astype(str) + '周目'
laps_out.to_csv(os.path.join(OUT, 'laps.csv'), index=False)
stints.to_csv(os.path.join(OUT, 'stints.csv'), index=False)
pits.to_csv(os.path.join(OUT, 'pits.csv'), index=False)
tl.to_csv(os.path.join(OUT, 'temps.csv'), index=False)
wv.to_csv(os.path.join(OUT, 'water.csv'), index=False)
tr.round(2).to_csv(os.path.join(OUT, 'track.csv'), index=False)
corners.to_csv(os.path.join(OUT, 'corners.csv'), index=False)
cmp_sel.to_csv(os.path.join(OUT, 'compare.csv'), index=False)
seg_loss.to_csv(os.path.join(OUT, 'segloss.csv'), index=False)
cw.to_csv(os.path.join(OUT, 'cornerdrive.csv'), index=False)
ggref.to_csv(os.path.join(OUT, 'gg.csv'), index=False)
gears.to_csv(os.path.join(OUT, 'gears.csv'), index=False)
up_tab.to_csv(os.path.join(OUT, 'shifts.csv'), index=False)
press_rpm.to_csv(os.path.join(OUT, 'press_rpm.csv'), index=False)
pl.to_csv(os.path.join(OUT, 'press_lat.csv'), index=False)
plong.to_csv(os.path.join(OUT, 'press_long.csv'), index=False)
pev.to_csv(os.path.join(OUT, 'press_events.csv'), index=False)
lg.to_csv(os.path.join(OUT, 'logger.csv'), index=False)
slides.to_csv(os.path.join(OUT, 'slides.csv'), index=False)
bal_corner.to_csv(os.path.join(OUT, 'balance_corner.csv'), index=False)
LAPKEYS = {'best_lap', 'q_best', 'theo_best', 'theo_seg', 'mid_lap_s', 'st1_best', 'st2_best', 'st3_best', 'st1_median', 'st2_median', 'st3_median'}
def mmss(v):
    m = int(v // 60); return f'{m}:{v - 60 * m:06.3f}'
def txt(k, v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return '—'
    if k in LAPKEYS: return mmss(float(v))
    if isinstance(v, str): return v
    v = float(v)
    if abs(v - round(v)) < 1e-9: return f'{int(round(v)):,}'
    return f'{v:,.2f}'.rstrip('0').rstrip('.') if abs(v) < 10 else f'{v:,.1f}'.rstrip('0').rstrip('.')
F = pd.DataFrame(facts); F['text'] = [txt(k, v) for k, v in zip(F.key, F.value)]
F['value'] = F.value.astype(str)
F[['key', 'text', 'value', 'label']].to_csv(os.path.join(OUT, 'facts.csv'), index=False)
print(pd.DataFrame(facts).to_string())

# ---------- レポートのページに載せる表へまとめる ----------
F=pd.read_csv(os.path.join(OUT, 'facts.csv'), dtype=str)
add=[]
g=pd.read_csv(os.path.join(OUT, 'gears.csv'))
for r in g.itertuples(): add.append((f'gear{r.gear}_share', f'{r.share*100:.0f}', str(r.share), f'{r.name}で走っていた時間の割合（通常の周、%）'))
sh=pd.read_csv(os.path.join(OUT, 'shifts.csv'))
for r in sh.itertuples():
    add += [(f'up{r._1}{r.to}_rpm', f'{int(r.rpm_med):,}', str(r.rpm_med), f'{r.name}へ上げたときの回転の中央値（rpm）'),
            (f'up{r._1}{r.to}_n', f'{int(r.count)}', str(r.count), f'{r.name}へ上げた回数（通常の周）')]
ev=pd.read_csv(os.path.join(OUT, 'press_events.csv'))
for c,lab in [('time_jst','時刻'),('lap','周'),('kpa','油圧（kPa）'),('expect','その回転での普段の油圧（kPa）'),('rpm','回転（rpm）'),('lat','横G'),('speed','速度（km/h）'),('dur_s','続いた秒'),('x','地図のx（m）'),('y','地図のy（m）')]:
    v=ev[c].iloc[0]; t=f'{int(v):,}' if c in ('kpa','expect','rpm','speed','lap') else (f'{abs(v):.2f}' if c=='lat' else str(v))
    add.append((f'pev_{c}', t, str(v), '油圧が下がったとき：'+lab))
st=pd.read_csv(os.path.join(OUT, 'stints.csv'))
for r in st.itertuples():
    add += [(f'st{r.stint}_range', f'{r.first}〜{r.last}', f'{r.first}-{r.last}', f'スティント{r.stint}の周'), (f'st{r.stint}_bestlap', str(r.best_lap), str(r.best_lap), f'スティント{r.stint}のベストの周'), (f'st{r.stint}_start', r.start_jst, r.start_jst, f'スティント{r.stint}の始まり')]
F=pd.concat([F, pd.DataFrame(add, columns=['key','text','value','label'])], ignore_index=True)
F = F.drop_duplicates('key', keep='last')      # ギアの割合は通常の周で数えた方を残す
F.to_csv(os.path.join(PUB, 'facts.csv'), index=False)
L=pd.read_csv(os.path.join(OUT, 'laps.csv'))
L.to_csv(os.path.join(PUB, 'laps.csv'), index=False)
pd.read_csv(os.path.join(OUT, 'temps.csv')).to_csv(os.path.join(PUB, 'temps.csv'), index=False)
pd.read_csv(os.path.join(OUT, 'water.csv')).to_csv(os.path.join(PUB, 'water.csv'), index=False)
pd.read_csv(os.path.join(OUT, 'track.csv')).to_csv(os.path.join(PUB, 'track.csv'), index=False)
c=pd.read_csv(os.path.join(OUT, 'corners.csv')).merge(pd.read_csv(os.path.join(OUT, 'segloss.csv')).drop(columns=['name','s','vmin_ref','seg_from','seg_to']), on='corner').merge(pd.read_csv(os.path.join(OUT, 'cornerdrive.csv')).drop(columns=['name','s']+[x for x in pd.read_csv(os.path.join(OUT, 'cornerdrive.csv')).columns if x.startswith('throttle')]), on='corner')
c['loss_avg']=c[['st1','st2','st3']].mean(axis=1).round(3)
c = c.rename(columns={'vmin_ref_x': 'vmin_line', 'vmin_ref_y': 'vmin_ref'})
c = c.merge(pd.read_csv(os.path.join(OUT, 'balance_corner.csv')), on='corner', how='left')
c.to_csv(os.path.join(PUB, 'corners.csv'), index=False)
cm=pd.read_csv(os.path.join(OUT, 'compare.csv')); cm.to_csv(os.path.join(PUB, 'compare.csv'), index=False)
pd.read_csv(os.path.join(OUT, 'gg.csv')).to_csv(os.path.join(PUB, 'gg.csv'), index=False)
a=pd.read_csv(os.path.join(OUT, 'press_rpm.csv')).rename(columns={'rpm_bin':'x','p10':'lo','p90':'hi'}).assign(kind='rpm')
b=pd.read_csv(os.path.join(OUT, 'press_lat.csv')).rename(columns={'lat_bin':'x','p05':'lo'}).assign(kind='lat')
d=pd.read_csv(os.path.join(OUT, 'press_long.csv')).rename(columns={'long_bin':'x','p05':'lo'}).assign(kind='long')
pr=pd.concat([a,b,d], ignore_index=True)[['kind','x','med','lo','hi','n']]; pr['key']=pr.kind+':'+pr.x.astype(str)
pr.to_csv(os.path.join(PUB, 'press.csv'), index=False)
pd.read_csv(os.path.join(OUT, 'logger.csv')).to_csv(os.path.join(PUB, 'logger.csv'), index=False)
pd.read_csv(os.path.join(OUT, 'slides.csv')).drop(columns=['x', 'y']).to_csv(os.path.join(PUB, 'slides.csv'), index=False)
print(pd.read_csv(os.path.join(PUB, 'facts.csv')).to_string())
