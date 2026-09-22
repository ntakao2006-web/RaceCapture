"""Read-only nominal geometry audit: plated holes to different-net tracks."""
from pathlib import Path
import math,json,hashlib,collections
import wx
wx.DisableAsserts()
import pcbnew
P=Path(__file__).resolve().parents[1];path=P/'logger_v2.kicad_pcb';O=P/'output/design_review_20260907'
data=path.read_bytes();b=pcbnew.LoadBoard(str(path))
def pt(p):return (p.x/1e6,p.y/1e6)
def point_segment_distance(p,a,c):
    vx,vy=c[0]-a[0],c[1]-a[1];wx,wy=p[0]-a[0],p[1]-a[1]
    q=vx*vx+vy*vy
    t=max(0,min(1,(wx*vx+wy*vy)/q)) if q else 0
    return math.hypot(p[0]-a[0]-t*vx,p[1]-a[1]-t*vy)
tracks=[];vias=[]
for t in b.GetTracks():
    kind=t.GetClass()
    if kind=='PCB_TRACK':tracks.append({'start':pt(t.GetStart()),'end':pt(t.GetEnd()),'width_mm':t.GetWidth()/1e6,'netcode':t.GetNetCode(),'net':t.GetNetname(),'layer':b.GetLayerName(t.GetLayer()),'uuid':str(t.m_Uuid.AsString())})
    elif kind=='PCB_VIA':vias.append({'kind':'via','id':str(t.m_Uuid.AsString()),'position':pt(t.GetPosition()),'hole_mm':t.GetDrillValue()/1e6,'netcode':t.GetNetCode(),'net':t.GetNetname(),'copper_diameter_mm':t.GetWidth(pcbnew.F_Cu)/1e6})
    else:raise ValueError('Unsupported copper track shape: '+kind)
holes=[];rings=[]
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetAttribute()!=pcbnew.PAD_ATTRIB_PTH:continue
        dx,dy=p.GetDrillSize().x/1e6,p.GetDrillSize().y/1e6
        assert p.GetDrillShape()==pcbnew.PAD_DRILL_SHAPE_CIRCLE and dx==dy,'Audit requires round PTH drills'
        assert p.GetOffset().x==0 and p.GetOffset().y==0,'Audit requires concentric copper and drill'
        assert p.GetShape() in [pcbnew.PAD_SHAPE_CIRCLE,pcbnew.PAD_SHAPE_RECT,pcbnew.PAD_SHAPE_OVAL,pcbnew.PAD_SHAPE_ROUNDRECT],'Unsupported PTH copper pad shape'
        h={'kind':'PTH','id':f.GetReference()+'.'+p.GetNumber(),'position':pt(p.GetPosition()),'hole_mm':dx,'netcode':p.GetNetCode(),'net':p.GetNetname()}
        holes.append(h)
        sx,sy=p.GetSize().x/1e6,p.GetSize().y/1e6
        rings.append({**h,'pad_size_mm':[sx,sy],'annular_ring_mm':(min(sx,sy)-dx)/2})
def minimum_pairs(items):
    result=[]
    for h in items:
        best=None
        for t in tracks:
            if t['netcode']==h['netcode']:continue
            gap=point_segment_distance(h['position'],t['start'],t['end'])-h['hole_mm']/2-t['width_mm']/2
            pair={'hole':h,'track':t,'clearance_mm':gap}
            if best is None or gap<best['clearance_mm']:best=pair
        if best:result.append(best)
    return sorted(result,key=lambda r:r['clearance_mm'])
hp=minimum_pairs(holes);vp=minimum_pairs(vias);rings.sort(key=lambda r:r['annular_ring_mm'])
report={'pcb_sha256':hashlib.sha256(data).hexdigest(),'copper_layers':b.GetCopperLayerCount(),'track_segments':len(tracks),'PTH_holes':len(holes),'vias':len(vias),'source':'https://jlcpcb.com/capabilities/pcb-capabilities','scope':'Nominal CAD hole edge to track copper edge, different nets, both copper layers; excludes zones, pads, same-net connections and manufacturing tolerances. All drills circular and concentric, and all tracks straight; checked explicitly.',
    'PTH_to_track':{'minimum_mm':hp[0]['clearance_mm'],'requirement_mm':0.28,'recommended_mm':0.35,'passes':hp[0]['clearance_mm']>=0.28,'closest':hp[0],'violations':[r for r in hp if r['clearance_mm']<0.28]},
    'via_hole_to_track':{'minimum_mm':vp[0]['clearance_mm'],'requirement_mm':0.2,'passes':vp[0]['clearance_mm']>=0.2,'closest':vp[0],'violations':[r for r in vp if r['clearance_mm']<0.2]},
    'PTH_annular_ring_2layer_1oz':{'minimum_mm':rings[0]['annular_ring_mm'],'absolute_requirement_mm':0.18,'recommended_mm':0.25,'passes':rings[0]['annular_ring_mm']>=0.18,'minimum_pads':[r for r in rings if abs(r['annular_ring_mm']-rings[0]['annular_ring_mm'])<1e-8],'violations':[r for r in rings if r['annular_ring_mm']<0.18]},
    'closest_PTH_by_hole':hp[:12],'closest_vias_by_hole':vp[:12]}
(O/'jlc_hole_clearance_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if not k.startswith('closest_')},ensure_ascii=False,indent=2))
