import os
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = [('LOG_20261023T130936Z_d32dc26b.csv.drift.npz', '10/23 公道（約9°傾けて取付、停車34回）'),
        ('majesta_20261025_本番.csv.drift.npz', '10/25 エコラン本番（ほぼ水平、40分止まらず）')]
SURF, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df'
NOW, FIX = '#eb6834', '#2a78d6'
plt.rcParams.update({'font.family': ['Yu Gothic', 'Meiryo'], 'font.size': 11, 'axes.edgecolor': GRID,
                     'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2})

fig, axes = plt.subplots(2, 1, figsize=(10, 6.6), facecolor=SURF, sharey=True)
for ax, (name, title) in zip(axes, RUNS):
    d = np.load(os.path.join(HERE, name))
    t = (d['t'] - d['t'][0]) / 60
    moving = (d['v'] > 3) & (abs(d['ref']) < 1.2)
    ax.set_facecolor(SURF)
    for key, color, label in (('a_ndof', NOW, '今：BNO055が推定した重力を引いた前後G'), ('a_fixed', FIX, '案：止まっているときの重力の向きで固定して引いた前後G')):
        e = pd.Series(np.where(moving, d[key] - d['ref'], np.nan)).rolling(1000, min_periods=600, center=True).mean()
        ax.plot(t, e, color=color, lw=1.8, label=label, solid_capstyle='round')
        rms = np.sqrt(np.nanmean((d[key] - d['ref'])[moving] ** 2))
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_ylim(-0.3, 0.3); ax.set_yticks([-0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3])
    ax.grid(axis='y', color=GRID, lw=0.8); ax.set_axisbelow(True)
    for s in ('top', 'right'): ax.spines[s].set_visible(False)
    ax.set_title(title, loc='left', color=INK, fontsize=12, pad=6)
    ax.set_ylabel('ずれ [G]')
    ax.set_xlim(0, t[-1])
axes[-1].set_xlabel('記録開始からの時間 [分]（走っている間だけ。10秒ごとの平均）')
axes[0].legend(loc='upper right', frameon=False, fontsize=10, labelcolor=INK)
fig.suptitle('V2の前後Gのずれ（速度の変化から求めた本当の前後Gとの差）', x=0.06, ha='left', color=INK, fontsize=14, y=0.995)
fig.tight_layout(rect=(0, 0, 1, 0.97))
out = r'C:\Users\ntaka\Documents\ClaudeCode\RaceCapture\outputs\imu_gravity_review_20261104\v2_longaccel_drift.png'
os.makedirs(os.path.dirname(out), exist_ok=True)
fig.savefig(out, dpi=130, facecolor=SURF)
print(out)
