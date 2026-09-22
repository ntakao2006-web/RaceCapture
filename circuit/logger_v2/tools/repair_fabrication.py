from design_board import *
b=p.LoadBoard(str(P/'logger_v2.kicad_pcb'))
original_tracks=list(b.GetTracks())
for t in original_tracks:
    if isinstance(t,p.PCB_VIA):
        t.SetDrill(p.FromMM(.3))
        if t.GetNetname()=='GND' and any(math.dist(xy(t),q)<.001 for q in [(166,60),(138,52)]):b.Remove(t)
    elif t.GetWidth()<p.FromMM(.2):t.SetWidth(p.FromMM(.2))
def distline(q,a,c):
    d=(c[0]-a[0],c[1]-a[1]);ll=d[0]*d[0]+d[1]*d[1]
    if not ll:return math.dist(q,a)
    f=max(0,min(1,((q[0]-a[0])*d[0]+(q[1]-a[1])*d[1])/ll));return math.dist(q,(a[0]+f*d[0],a[1]+f*d[1]))
def distbox(q,a):
    v=a.GetBoundingBox();bb=[mm(v.GetLeft()),mm(v.GetTop()),mm(v.GetRight()),mm(v.GetBottom())]
    return math.hypot(max(bb[0]-q[0],0,q[0]-bb[2]),max(bb[1]-q[1],0,q[1]-bb[3]))
def room(q):
    margin=999
    for f in b.GetFootprints():
        for a in f.Pads():
            gap=.35 if a.GetNetname()=='GND' and a.GetAttribute()==p.PAD_ATTRIB_SMD else .51
            margin=min(margin,distbox(q,a)-gap)
    for t in b.GetTracks():
        if t.GetNetname()=='GND' and not isinstance(t,p.PCB_VIA):continue
        a=(mm(t.GetStart().x),mm(t.GetStart().y));c=(mm(t.GetEnd().x),mm(t.GetEnd().y))
        margin=min(margin,distline(q,a,c)-mm(t.GetWidth())/2-.51)
    return margin
zones=[b.GetArea(i) for i in range(b.GetAreaCount())]
zf=next(z for z in zones if z.GetNetname()=='GND' and z.GetLayer()==p.F_Cu)
zb=next(z for z in zones if z.GetNetname()=='GND' and z.GetLayer()==p.B_Cu)
front=zf.GetFilledPolysList(p.F_Cu);back=zb.GetFilledPolysList(p.B_Cu)
main_back=max(range(back.OutlineCount()),key=lambda i:back.COutline(i).Area())
placed=[]
for index in range(front.OutlineCount()):
    if any(isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND' and front.Contains(t.GetPosition(),index) for t in b.GetTracks()):continue
    bbox=front.COutline(index).BBox();poss=[]
    for ix in range(math.ceil(mm(bbox.GetLeft())*5),math.floor(mm(bbox.GetRight())*5)+1):
        for iy in range(math.ceil(mm(bbox.GetTop())*5),math.floor(mm(bbox.GetBottom())*5)+1):
            q=(ix/5,iy/5)
            if front.Contains(V(*q),index) and back.Contains(V(*q),main_back):
                m=room(q)
                if m>=0:poss.append((m,q))
    if poss:
        _,q=max(poss);v=p.PCB_VIA(b);v.SetPosition(V(*q));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetViaType(p.VIATYPE_THROUGH);v.SetNet(b.FindNet('GND'));v.SetLocked(True);b.Add(v);placed.append((index,q))
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());save_checked(b)
print('Ground island bridges',placed)
