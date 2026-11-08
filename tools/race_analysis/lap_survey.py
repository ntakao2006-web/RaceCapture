"""周ごとの「どこで遅れたか」を一覧にして、設定ファイルの incident_laps・slow_all_laps を決める下調べ（SG-5-3）。

  python tools/race_analysis/lap_survey.py tools/race_analysis/sugo_20261108.json [周 ...]

周を指定しなければ、決勝の周のうちタイムが中央値より6%以上遅い周を出す。各周について：
  - 基準の線（race_analysis.pyが出すdetailのtrack.csv。無ければ先にrace_analysis.pyを流す）から最も離れた距離
  - 5km/h未満だった秒・最低速度
  - 250mごとの平均速度（その周 / ベストの周）
一か所だけ大きく落ちている周 → incident_laps、全区間がそろって遅い周 → slow_all_laps の目安。
"""
import json, os, sys
import numpy as np, pandas as pd
from scipy.spatial import cKDTree

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CFG = json.load(open(sys.argv[1], encoding='utf-8'))
P = lambda p: p if os.path.isabs(p) else os.path.join(REPO, p)
LAT0, LON0 = CFG['line']
cache = os.path.join(P(CFG['out_dir']), 'cache', os.path.basename(CFG['race_csv']) + '.pkl')
d = pd.read_pickle(cache) if os.path.exists(cache) else pd.read_csv(P(CFG['race_csv']), low_memory=False)
d['lap'] = d.LapCount + 1
d['x'] = (d.Lon - LON0) * np.cos(np.radians(LAT0)) * 111320
d['y'] = (d.Lat - LAT0) * 110540
tr = pd.read_csv(os.path.join(P(CFG['out_dir']), 'detail', 'track.csv'))
tree = cKDTree(np.c_[tr.x, tr.y])
lt = d.groupby('LapCount').LapTime.first() * 60
a, b = CFG['race_laps']
laps = [int(x) for x in sys.argv[2:]] or [n for n in range(a, b + 1) if n in lt.index and lt[n] > lt.loc[a:b].median() * 1.06]
ref = tr.groupby(tr.s // 250 * 250).Speed.mean()
for n in laps:
    g = d[d.lap == n].iloc[::10]
    dist, i = tree.query(np.c_[g.x, g.y]); g = g.assign(off=dist, s=tr.s.values[i])
    print(f'{n}周目 {lt.get(n, float("nan")):.1f}秒: 線から最大{dist.max():.0f}m（{g.s.iloc[dist.argmax()]:.0f}m地点）, '
          f'5km/h未満{(g.GPSSpeed < 5).sum() / 10:.1f}秒, 最低{g.GPSSpeed.min():.0f}km/h')
    v = g.groupby(g.s // 250 * 250).GPSSpeed.mean()
    print('   ', ' '.join(f'{int(k)}:{v[k]:.0f}/{ref.get(k, 0):.0f}' for k in v.index))
