"""Read back exported drill/outline/CPL files against the saved PCB."""
from design_board import *
import csv,collections,re,hashlib
b=p.LoadBoard(str(P/'logger_v2.kicad_pcb')); old=p.LoadBoard(str(BASE))
M=P/'manufacturing_20260907';G=M/'gerbers';issues=[]
def outline(board):
    out=[]
    for g in board.GetDrawings():
        if g.GetLayer()!=p.Edge_Cuts: continue
        item=[int(g.GetShape()),g.GetStart().x,g.GetStart().y,g.GetEnd().x,g.GetEnd().y,g.GetWidth()]
        if g.GetShape()==p.SHAPE_T_ARC: item.extend([g.GetArcMid().x,g.GetArcMid().y])
        out.append(tuple(item))
    return collections.Counter(out)
if outline(b)!=outline(old):issues.append('Original Edge.Cuts changed')
expected={'PTH':collections.Counter(),'NPTH':collections.Counter()}
def key(d,x,y):return (round(d,3),round(x-100,6),round(100-y,6))
for t in b.GetTracks():
    if isinstance(t,p.PCB_VIA): expected['PTH'][key(mm(t.GetDrillValue()),*xy(t))]+=1
for f in b.GetFootprints():
    for a in f.Pads():
        d=a.GetDrillSize()
        if d.x:
            assert d.x==d.y,'Oval drill requires extended audit'
            typ='NPTH' if a.GetAttribute()==p.PAD_ATTRIB_NPTH else 'PTH'
            expected[typ][key(mm(d.x),*xy(a))]+=1
drill_counts={};drill_errors=[]
for typ in ['PTH','NPTH']:
    text=(G/f'logger_v2-{typ}.drl').read_text();sizes={};hits=collections.Counter();tool=None
    for line in text.splitlines():
        q=re.fullmatch(r'T(\d+)C([\d.]+)',line)
        if q:sizes[q[1]]=float(q[2]);continue
        q=re.fullmatch(r'T(\d+)',line)
        if q:tool=q[1];continue
        q=re.fullmatch(r'X(-?[\d.]+)Y(-?[\d.]+)',line)
        if q:hits[(sizes[tool],float(q[1]),float(q[2]))]+=1
    # Excellon exports 0.001 mm resolution; match each hole one-to-one at half a digit.
    remaining=list(hits.elements())
    for d,x,y in expected[typ].elements():
        matched=next((i for i,(ad,ax,ay) in enumerate(remaining) if ad==d and max(abs(ax-x),abs(ay-y))<=.000501),None)
        if matched is None: issues.append([typ,'missing or displaced drill',d,x,y])
        else:
            ad,ax,ay=remaining.pop(matched);drill_errors.append(max(abs(ax-x),abs(ay-y)))
    if remaining: issues.append([typ,'extra drills',remaining])
    drill_counts[typ]=sum(hits.values())
edge=(G/'logger_v2-Edge_Cuts.gm1').read_text()
coords=[(int(x)/1e6,int(y)/1e6) for x,y in re.findall(r'X(-?\d+)Y(-?\d+)D0[12]',edge)]
dims=[round(max(v[i] for v in coords)-min(v[i] for v in coords),3) for i in [0,1]]
if dims!=[68.58,53.34]:issues.append(f'Exported outline size {dims}')
F={f.GetReference():f for f in b.GetFootprints()}
rows=list(csv.DictReader((M/'JLCPCB_CPL.csv').open(encoding='utf-8-sig')))
for r in rows:
    f=F[r['Designator']];x,y=xy(f)
    if abs(float(r['Mid X'])-(x-100))>.0001 or abs(float(r['Mid Y'])-(100-y))>.0001:issues.append(['CPL coordinate',r['Designator']])
    if float(r['Rotation'])!=f.GetOrientationDegrees()%360 or r['Layer']!='Top':issues.append(['CPL rotation/layer',r['Designator']])
bom=list(csv.DictReader((M/'JLCPCB_BOM.csv').open(encoding='utf-8-sig')))
bom_designators=[ref.strip() for r in bom for ref in r['Designator'].split(',')]
if collections.Counter(bom_designators)!=collections.Counter(r['Designator'] for r in rows):issues.append('BOM/CPL sets differ')
if len(rows)!=48 or len({r['Designator'] for r in rows})!=48:issues.append('PCBA component count differs')
if any(not r['LCSC Part #'] for r in bom):issues.append('PCBA BOM missing LCSC identifier')
zones=[z for z in b.Zones() if z.GetNetname()=='GND' and z.GetLayer()==p.B_Cu and not z.GetIsRuleArea()]
samples=[V(107+i*.1,89.3+j*.1) for i in range(106) for j in range(15)]
miss=[(mm(q.x),mm(q.y)) for q in samples if not any(z.GetFilledPolysList(p.B_Cu).Contains(q) for z in zones)]
if miss:issues.append(['RF back ground sampling',miss[:10],len(miss)])
via_pad_min=1e9
for v in b.GetTracks():
    if not isinstance(v,p.PCB_VIA): continue
    for f in b.GetFootprints():
        for a in f.Pads():
            if a.GetAttribute()!=p.PAD_ATTRIB_SMD: continue
            vx,vy=xy(v);ax,ay=xy(a);theta=math.radians(a.GetOrientationDegrees())
            dx=(vx-ax)*math.cos(theta)-(vy-ay)*math.sin(theta);dy=(vx-ax)*math.sin(theta)+(vy-ay)*math.cos(theta)
            size=a.GetSize();gap=math.hypot(max(abs(dx)-mm(size.x)/2,0),max(abs(dy)-mm(size.y)/2,0))-mm(v.GetDrillValue())/2
            via_pad_min=min(via_pad_min,gap)
            if gap<.099:issues.append(['Via hole approaches SMD pad',f.GetReference(),a.GetNumber(),gap])
report={'issues':issues,'original_edge_cuts_unchanged':outline(b)==outline(old),'outline_mm':dims,'drill_holes':drill_counts,'max_drill_export_rounding_mm':round(max(drill_errors),6),'bom_cpl_components':len(rows),'rf_back_ground_sample_count':len(samples),'rf_back_ground_misses':len(miss),'board_sha256':hashlib.sha256((P/'logger_v2.kicad_pcb').read_bytes()).hexdigest()}
report['min_via_drill_to_smd_pad_rect_bound_mm']=round(via_pad_min,6)
(O/'manufacturing_validation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2));sys.exit(bool(issues))
