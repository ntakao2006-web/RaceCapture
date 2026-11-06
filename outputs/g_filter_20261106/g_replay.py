import sys, numpy as np, json
sys.path.insert(0, r'C:\Users\ntaka\Documents\ClaudeCode\RaceCapture\EcoCapture-Web')
from imu_mount import ImuMount
d=np.genfromtxt('g_0414.csv',delimiter=',',names=True)
m=ImuMount()
# the logger's own calibration at the start of this log (imu_mount column), forward already learned
m.load({'up':[-0.15412,0.01631,0.98792],'g':9.6883,'forward_sum':[-177.7491,13.03744,-24.45071],'forward_weight':181.6353})
# start from the same calibration the logger had: level from the first still rows, forward taken from logged outputs is not available,
# so compare against the logger's own LongAccel/LatAccel only via shape: project with the logged axes estimate
acc=np.c_[d['AccelX'],d['AccelY'],d['AccelZ']]; gy=np.c_[d['GyroX'],d['GyroY'],d['GyroZ']]
out=[]
for i in range(len(d)):
    c=m.add(list(acc[i]),list(gy[i]),d['Speed'][i],int(d['mcu_ms'][i]))
    out.append(c if c else (np.nan,)*3)
out=np.array(out); spd=d['Speed']; mov=spd>20; idle=(spd==0)
def jit(y):
    s=y[mov]; k=101; h=np.hanning(k); h/=h.sum(); r=np.convolve(s,h,'same'); return np.nanstd((s-r)[::10])
for j,nm in enumerate(('LongAccel','LatAccel','VertAccel')):
    old=d[nm]; new=out[:,j]
    print(f'{nm}: shake on screen (10 Hz pick, moving)  old {jit(old):.3f} G -> new {jit(new):.3f} G | idle std old {np.nanstd(old[idle][::10]):.3f} new {np.nanstd(new[idle][::10]):.3f} | p99.9 |G| moving old {np.nanpercentile(abs(old[mov]),99.9):.2f} new {np.nanpercentile(abs(new[mov]),99.9):.2f}')
print(json.dumps(m.public(),ensure_ascii=False)[:300])
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams['font.family']=['Yu Gothic','Meiryo','sans-serif']
t=(d['mcu_ms']-d['mcu_ms'][0])/1000
# pick a 30 s stretch with the largest lateral G spread while moving
best=None
for s in range(0,len(t)-3000,500):
    if (spd[s:s+3000]>20).all():
        v=np.nanstd(out[s:s+3000,1]); best=(v,s) if best is None or v>best[0] else best
s=best[1]; e=s+3000; sl=slice(s,e,10)
fig,ax=plt.subplots(1,3,figsize=(15,4.8),gridspec_kw={'width_ratios':[2,2,1.3]})
for a,j,nm in ((ax[0],1,'左右G (LatAccel)'),(ax[1],0,'前後G (LongAccel)')):
    a.plot(t[sl]-t[s],d[['LongAccel','LatAccel'][1-j]][sl] if False else d[['LongAccel','LatAccel'][j]][sl],color='#bbbbbb',lw=1,label='いま（約0.1秒ごとに1行を拾う）')
    a.plot(t[sl]-t[s],out[sl,j],color='#c0392b',lw=1.8,label='フィルター後（2Hz）')
    a.set_title(nm);a.set_xlabel('秒');a.set_ylabel('G');a.grid(alpha=.3);a.legend(fontsize=8,loc='upper right')
ax[2].plot(d['LatAccel'][sl],d['LongAccel'][sl],color='#bbbbbb',lw=.8)
ax[2].plot(out[sl,1],out[sl,0],color='#c0392b',lw=1.5)
ax[2].set_aspect('equal');ax[2].set_title('Gボールの軌跡（同じ30秒）');ax[2].set_xlabel('左右G');ax[2].set_ylabel('前後G');ax[2].grid(alpha=.3)
fig.suptitle(f'NCEC 2026-11-06 走行中（{np.nanmean(spd[s:e]):.0f} km/h前後）の画面に出る値：灰＝いま、赤＝フィルター後')
fig.tight_layout();fig.savefig(r'C:\Users\ntaka\Documents\ClaudeCode\RaceCapture\outputs\g_filter_20261106\g_filter_before_after.png',dpi=110)
print('saved',s)
