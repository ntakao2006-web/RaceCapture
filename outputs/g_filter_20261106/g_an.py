import numpy as np, sys
d=np.genfromtxt('g_0414.csv',delimiter=',',names=True)
t=d['mcu_ms']/1000; spd=d['Speed']; rpm=d['RPM']
L=d['LongAccel']; T=d['LatAccel']; V=d['VertAccel']
ok=np.isfinite(L)
print('rows',len(t),'min',(t[-1]-t[0])/60, 'calib ok',ok.mean())
dt=np.diff(t)*1000
print('dt ms pct', np.percentile(dt,[1,5,50,95,99,99.9]), 'gaps>30ms',(dt>30).sum())
def psd(x,fs=100,n=512):
    x=x[np.isfinite(x)]; m=len(x)//n
    if m==0: return None,None
    x=x[:m*n].reshape(m,n); x=x-x.mean(1,keepdims=True)
    w=np.hanning(n); P=(np.abs(np.fft.rfft(x*w,axis=1))**2).mean(0)
    f=np.fft.rfftfreq(n,1/fs); return f,P
for name,sel in [('idle',(spd==0)&(rpm>500)),('engine off',(spd==0)&(rpm<100)),('moving>20',spd>20),('moving>60',spd>60)]:
    sel&=ok
    print(f'\n== {name}: {sel.sum()/100/60:.1f} min')
    if sel.sum()<1000: continue
    for nm,x in (('Long',L),('Lat',T),('Vert',V)):
        xs=x[sel]
        # noise = deviation from 1 s moving average
        k=np.ones(100)/100; base=np.convolve(xs,k,'same'); n=xs-base
        f,P=psd(xs)
        band=lambda a,b: P[(f>=a)&(f<b)].sum()/P[f>0.5].sum()
        top=f[np.argsort(P*(f>1))[-3:]]
        print(f'{nm:5} std {xs.std():.3f}  noise(-1s avg) std {n[100:-100].std():.3f} p99 {np.percentile(abs(n[100:-100]),99):.3f}  power 0.5-3Hz {band(.5,3):.2f} 3-10 {band(3,10):.2f} 10-50 {band(10,50.1):.2f}  peaks {np.round(top,1)}')
    print('rpm median', np.median(rpm[sel]), '-> 2nd order Hz', np.median(rpm[sel])/60*2)
