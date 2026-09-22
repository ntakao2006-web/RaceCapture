"""Local ground returns, regular stitching and unbroken RF reference plane."""
from design_board import *
b=p.LoadBoard(str(P/'logger_v2.kicad_pcb'))
ground=b.FindNet('GND'); outline=p.SHAPE_POLY_SET();assert b.GetBoardPolygonOutlines(outline)
pads=[a for f in b.GetFootprints() for a in f.Pads()]
tracks=list(b.GetTracks())
def distpt(a,u,v):
    dx=v[0]-u[0];dy=v[1]-u[1];ll=dx*dx+dy*dy
    if ll==0:return math.dist(a,u)
    f=max(0,min(1,((a[0]-u[0])*dx+(a[1]-u[1])*dy)/ll))
    return math.dist(a,(u[0]+f*dx,u[1]+f*dy))
def box(a):
    r=a.GetBoundingBox();return(mm(r.GetLeft()),mm(r.GetTop()),mm(r.GetRight()),mm(r.GetBottom()))
def distbox(pt,bb):
    return math.hypot(max(bb[0]-pt[0],0,pt[0]-bb[2]),max(bb[1]-pt[1],0,pt[1]-bb[3]))
def allowed(pt):
    if not all(outline.Contains(V(pt[0]+dx,pt[1]+dy)) for dx,dy in [(-.65,0),(.65,0),(0,-.65),(0,.65)]):return False
    if 103.65<pt[0]<118.85 and 88.55<pt[1]<91.45:return False
    for a in pads:
        if distbox(pt,box(a))<.50:return False
    for t in tracks:
        a=(mm(t.GetStart().x),mm(t.GetStart().y));c=(mm(t.GetEnd().x),mm(t.GetEnd().y))
        req=mm(t.GetWidth())/2+.3+(.3 if t.GetNetname()=='/GNSS_RF' else .2)
        if distpt(pt,a,c)<req-.000001:return False
    return True
def addvia(pt):
    v=p.PCB_VIA(b);v.SetPosition(V(*pt));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(ground);v.SetLocked(True);b.Add(v);tracks.append(v)
def pathclear(a,c):
    for step in range(1,11):
        pt=(a[0]+(c[0]-a[0])*step/10,a[1]+(c[1]-a[1])*step/10)
        for q in pads:
            if q.GetNetname()!='GND' and distbox(pt,box(q))<.35:return False
        for t in tracks:
            if t.GetNetname()=='GND':continue
            u=(mm(t.GetStart().x),mm(t.GetStart().y));v=(mm(t.GetEnd().x),mm(t.GetEnd().y))
            if distpt(pt,u,v)<mm(t.GetWidth())/2+.35:return False
    return True
local=0;stitch=0
for a in pads:
    if a.GetNetname()!='GND' or a.GetAttribute()!=p.PAD_ATTRIB_SMD:continue
    x,y=xy(a)
    options=[(x+dx,y+dy) for d in [1.2,1.6,2.0] for dx,dy in [(d,0),(-d,0),(0,d),(0,-d)]]
    for pt in options:
        if allowed(pt) and pathclear((x,y),pt):
            addvia(pt);t=p.PCB_TRACK(b);t.SetStart(V(x,y));t.SetEnd(V(*pt));t.SetWidth(p.FromMM(.3));t.SetLayer(p.F_Cu);t.SetNet(ground);t.SetLocked(True);b.Add(t);tracks.append(t);local+=1;break
for y in [88.1,91.9]:
    for x in [109.5,111.5,113.5,115.5,117.5]:
        if allowed((x,y)):addvia((x,y));stitch+=1
for x in range(102,167,4):
    for y in range(48,99,4):
        if allowed((x,y)):addvia((x,y));stitch+=1
for f in b.GetFootprints():
    if f.GetReference()=='J1':
        for a in f.Pads():
            if a.GetNetname()=='GND':a.SetLocalZoneConnection(p.ZONE_CONNECTION_FULL)
for z in b.Zones():
    if not z.GetIsRuleArea():
        z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS)
b.BuildConnectivity();filler=p.ZONE_FILLER(b);filler.Fill(b.Zones());save_checked(b)
print('Local ground vias',local,'regular/RF stitching',stitch)
