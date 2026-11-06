import numpy as np
d=np.genfromtxt('g_0414.csv',delimiter=',',names=True)
spd=d['Speed']; rpm=d['RPM']; L=d['LongAccel']; T=d['LatAccel']
n=256; f=np.fft.rfftfreq(n,1/100); w=np.hanning(n)
# per 2.56 s window: rpm mean, peak freq
res={}
for i in range(0,len(L)-n,n):
    r=rpm[i:i+n]; 
    if not np.isfinite(r).all() or r.std()>60 or spd[i:i+n].min()<5: continue
    for nm,x in (('L',L),('T',T)):
        x=x[i:i+n]-x[i:i+n].mean(); P=np.abs(np.fft.rfft(x*w))**2
        res.setdefault(int(r.mean()//250*250),[]).append((nm,P))
print('rpm  2nd-order  alias  | Long: frac power <8Hz, top peaks | Lat: same')
for k in sorted(res):
    o2=(k+125)/60*2; al=abs(o2-100*round(o2/100))
    line=f'{k:5d} {o2:6.1f}Hz {al:5.1f}Hz |'
    for nm in 'LT':
        Ps=[P for m,P in res[k] if m==nm]
        if len(Ps)<4: line+=' -';continue
        P=np.mean(Ps,0); 
        lo=P[(f>0.5)&(f<8)].sum()/P[f>0.5].sum()
        top=f[np.argsort(P*(f>3))[-3:]][::-1]
        line+=f' {lo:.2f} {np.round(top,1)} |'
    print(line, len(res[k])//2)
