"""Deliberate fixed RF, oscillator, decoupling, and aligned LED routing."""
from design_board import *

b=p.LoadBoard(str(P/'logger_v2.kicad_pcb'))
F={f.GetReference():f for f in b.GetFootprints()}
def pad(ref,num):return next(a for a in F[ref].Pads() if a.GetNumber()==str(num))
def seg(net,points,width=.25,layer=p.F_Cu):
    for a,c in zip(points,points[1:]):
        if math.dist(a,c)<.00001:continue
        t=p.PCB_TRACK(b);t.SetStart(V(*a));t.SetEnd(V(*c));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNet(b.FindNet(net));t.SetLocked(True);b.Add(t)
def link(r1,n1,r2,n2,width=.25,points=None,layer=p.F_Cu):
    a,c=pad(r1,n1),pad(r2,n2);assert a.GetNetname()==c.GetNetname(),(r1,n1,r2,n2)
    seg(a.GetNetname(),[xy(a)]+(points or [])+[xy(c)],width,layer)
def chamfer(a,c,vertical=True):
    dx=c[0]-a[0];dy=c[1]-a[1];d=min(abs(dx),abs(dy));sx=1 if dx>=0 else -1;sy=1 if dy>=0 else -1
    middle=(a[0],c[1]-sy*d) if abs(dy)>=abs(dx) else (c[0]-sx*d,a[1])
    return [a,middle,c]
def direct(r1,n1,r2,n2,w=.25,vertical=True):
    a,c=pad(r1,n1),pad(r2,n2);assert a.GetNetname()==c.GetNetname(),(r1,n1,r2,n2)
    seg(a.GetNetname(),chamfer(xy(a),xy(c),vertical),w)
def via(net,pos,diameter=.6):
    v=p.PCB_VIA(b);v.SetPosition(V(*pos));v.SetWidth(p.FromMM(diameter));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(b.FindNet(net));v.SetLocked(True);b.Add(v)

# Straight 50-ohm nominal GCPW; no signal vias in its 12.5 mm path.
rf=pad('J1',1).GetNetname()
seg(rf,[(105,90),(114.5,90)],1.5)
seg(rf,[(114.5,90),(117.5,90)],.8)
z=p.ZONE(b);z.SetLayer(p.F_Cu);z.SetNet(b.FindNet(rf));z.SetLocalClearance(p.FromMM(.3));z.SetMinThickness(p.FromMM(.1));z.SetPadConnection(p.ZONE_CONNECTION_FULL);z.SetAssignedPriority(10)
poly=z.Outline();poly.NewOutline()
for x,y in [(114.3,89.25),(114.8,89.25),(116.6,89.6),(117.5,89.6),(117.5,90.4),(116.6,90.4),(114.8,90.75),(114.3,90.75)]:poly.Append(p.FromMM(x),p.FromMM(y))
b.Add(z)
for ref in ['L1','D11']:
    a=next(q for q in F[ref].Pads() if q.GetNetname()==rf)
    seg(rf,[xy(a),(xy(a)[0],90)],.3)
# Bias feed is local; series resistor's RF supply remains on the module side.
direct('R7',2,'C1',1,.4)
direct('C1',1,'L1',2,.3)
link('U2',9,'R7',1,.4,[(115.5,87.8),(115.5,82.5375)])

# Regular row of light indicators, each with a vertical series resistor.
res=['R1','R2','R3','R4','R6','R8','R9','R11']
outputs=[15,1,2,3,4,5,6,7]
for i,(r,n) in enumerate(zip(res,outputs),1):
    direct(r,2,f'D{i}',2,.25)
    a,c=xy(pad('U1',n)),xy(pad(r,1))
    if i==1:
        seg(pad(r,1).GetNetname(),[a,(a[0],a[1]-1.3),(138.5,a[1]-1.3),(138,73.525),(138,c[1]-1),c],.25)
    else:
        # Straight fan-out with a single 45-degree bend before the resistor row.
        seg(pad(r,1).GetNetname(),chamfer(a,c,True),.25)

# Decoupling pins connect into their capacitor before joining the rail.
caps=[('C4','U1',16),('C5','U4',3),('C6','U4',5),('C7','U5',1),('C8','U5',19),('C9','U5',27),('C10','U2',23),('C11','C10',1),('C12','U2',22)]
for cap,ic,n in caps:direct(ic,n,cap,1,.3,False)

save_checked(b)
print('Critical routes fixed; ground stitching and final zone fill follow residual routing.')
