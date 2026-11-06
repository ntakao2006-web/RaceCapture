import numpy as np, math
d=np.genfromtxt('g_0414.csv',delimiter=',',names=True)
spd=d['Speed']; rpm=d['RPM']; L=d['LongAccel']; T=d['LatAccel']
def bw2(x,fc,fs=100,stages=1):
    # bilinear 2nd-order Butterworth, direct form
    for _ in range(stages):
        K=math.tan(math.pi*fc/fs); q=math.sqrt(2); n=1/(1+q*K+K*K)
        b0=K*K*n; b1=2*b0; b2=b0; a1=2*(K*K-1)*n; a2=(1-q*K+K*K)*n
        y=np.empty_like(x); x1=x2=y1=y2=x[0]
        for i,v in enumerate(x):
            o=b0*v+b1*x1+b2*x2-a1*y1-a2*y2; x2,x1=x1,v; y2,y1=y1,o; y[i]=o
        x=y
    return x
def ref(x,fc=1.0):  # zero-phase reference of the "true" motion
    k=int(100/fc/2)*2+1; h=np.hanning(k); h/=h.sum(); return np.convolve(x,h,'same')
idle=(spd==0)&(rpm>500); mov=spd>20
print('filter        delay   idle Long/Lat std(display)   moving: Long/Lat jitter vs smooth(display)   peak |Lat| p99.9')
for name,fn,delay in [('raw',lambda x:x,0),('BW 5Hz',lambda x:bw2(x,5),45),('BW 3Hz',lambda x:bw2(x,3),75),('BW 2Hz',lambda x:bw2(x,2),112),('BW 1.5Hz',lambda x:bw2(x,1.5),150),('avg 0.25s',lambda x:np.convolve(x,np.ones(25)/25,'full')[:len(x)],125)]:
    out=[]
    yl=fn(L); yt=fn(T)
    for y,x in ((yl,L),(yt,T)):
        s=y[::10]  # what a 10 Hz reader sees
        out.append(np.nanstd(y[idle][::10]))
    jit=[]
    for y in (yl,yt):
        # jitter = displayed minus a slow version of the displayed signal (what the eye reads as shaking)
        s=y[mov]; r=ref(s,1.0); jit.append(np.std((s-r)[::10]))
    pk=np.percentile(abs(yt[mov]),99.9)
    print(f'{name:10} {delay:4d}ms   {out[0]:.3f} / {out[1]:.3f}                {jit[0]:.3f} / {jit[1]:.3f}                         {pk:.2f}')
