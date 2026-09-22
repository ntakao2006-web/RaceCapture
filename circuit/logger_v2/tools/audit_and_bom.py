"""Independently compare manufacturing board pads to fresh schematic XML."""
from design_board import *
import csv,collections,hashlib
b=p.LoadBoard(str(P/'logger_v2.kicad_pcb'))
tree=ET.parse(XML); comps={c.get('ref'):c for c in tree.findall('components/comp')}
expected={}
for n in tree.findall('nets/net'):
    for a in n.findall('node'): expected[(a.get('ref'),a.get('pin'))]=n.get('name')
actual={};issues=[]
F={f.GetReference():f for f in b.GetFootprints()}
for ref,f in F.items():
    if ref.startswith('MH'): continue
    for a in f.Pads():
        if a.GetNumber():actual[(ref,a.GetNumber())]=a.GetNetname()
    if ref not in comps:issues.append(['extra footprint',ref]);continue
    c=comps[ref]
    if f.GetValue()!=c.findtext('value'):issues.append(['value',ref,f.GetValue(),c.findtext('value')])
    if f.GetFPIDAsString()!=c.findtext('footprint'):issues.append(['footprint',ref])
    if f.IsDNP()!=(c.find("property[@name='dnp']") is not None):issues.append(['DNP',ref])
for key,net in expected.items():
    if actual.get(key)!=net:issues.append(['connectivity',key,net,actual.get(key)])
for key,net in actual.items():
    if key not in expected and net:issues.append(['unexpected connection',key,net])
baseline=json.loads((O/'baseline_board.json').read_text())
for a in baseline['footprints']:
    ref=a['ref']
    if ref.startswith('J') or ref.startswith('MH'):
        f=F[ref]
        if xy(f)!=tuple(a['pos']) or f.GetOrientationDegrees()!=a['angle']:issues.append(['mechanics',ref])
        oldpads=collections.Counter((q['num'],q['x'],q['y']) for q in a['pads'])
        newpads=collections.Counter((q.GetNumber(),*xy(q)) for q in f.Pads())
        if oldpads!=newpads:issues.append(['connector pad mechanics',ref])
bottom=[ref for ref,f in F.items() if f.GetLayer()!=p.F_Cu]
if bottom:issues.append(['bottom components',bottom])
report={'footprints':len(F),'schematic_components':len(comps),'expected_physical_pin_entries':len(expected),'mismatch_count':len(issues),'mismatches':issues,'all_components_on_top':not bottom,'tracks':sum(not isinstance(t,p.PCB_VIA) for t in b.GetTracks()),'vias':sum(isinstance(t,p.PCB_VIA) for t in b.GetTracks()),'board_sha256':hashlib.sha256((P/'logger_v2.kicad_pcb').read_bytes()).hexdigest(),'schematic_sha256':hashlib.sha256((P/'logger_v2.kicad_sch').read_bytes()).hexdigest()}
(O/'electrical_mechanical_audit.json').write_text(json.dumps(report,indent=2),encoding='utf8')
M=P/'manufacturing_20260907';M.mkdir(exist_ok=True)
rows=[];manual=[]
for ref,c in comps.items():
    f=F[ref];data={a.get('name'):a.text or '' for a in c.findall('fields/field')}
    dnp=f.IsDNP();lcsc=data.get('LCSC','');mpn=data.get('MPN',c.findtext('value'))
    assembly_type='DNP' if dnp else ('Manual; top mounted' if not lcsc or f.IsExcludedFromPosFiles() else 'JLCPCB Top SMT')
    requirement={'U3':'AE-BNO055-BO module; elevated top mounting; check underside clearance',
                 'J1':'S-037-TGG; retain horizontal SMA orientation',
                 'J2':'1x10 UNO shield stacking header, 2.54 mm; long lower pins',
                 'J3':'1x08 UNO shield stacking header, 2.54 mm; long lower pins',
                 'J4':'1x06 UNO shield stacking header, 2.54 mm; long lower pins',
                 'J5':'1x08 UNO shield stacking header, 2.54 mm; long lower pins',
                 'J6':'Molex 43045-0400; right angle; 5V pin is unprotected output',
                 'J7':'Molex 43045-0400; right angle; pin 1 NC'}.get(ref,'')
    row={'Comment':mpn,'Designator':ref,'Footprint':f.GetFPIDAsString().split(':',1)[1],'LCSC Part #':lcsc,'JLCPCB Class':data.get('JLCPCB_Class',''),'Value':f.GetValue(),'DNP':dnp,'Assembly':assembly_type,'Requirement':requirement,'Mid X':round(xy(f)[0]-100,4),'Mid Y':round(100-xy(f)[1],4),'Layer':'Top','Rotation':f.GetOrientationDegrees()%360}
    rows.append(row)
    if not dnp and (not lcsc or f.IsExcludedFromPosFiles()):manual.append(row)
def writecsv(name,items,columns):
    with (M/name).open('w',newline='',encoding='utf-8-sig') as out:
        w=csv.DictWriter(out,columns,extrasaction='ignore');w.writeheader();w.writerows(items)
assembly=[r for r in rows if not r['DNP'] and r not in manual]
groups={}
for r in assembly:
    k=(r['Comment'],r['Footprint'],r['LCSC Part #'])
    if k not in groups:groups[k]=dict(r)
    else:groups[k]['Designator']+=','+r['Designator']
writecsv('JLCPCB_BOM.csv',list(groups.values()),['Comment','Designator','Footprint','LCSC Part #'])
writecsv('JLCPCB_CPL.csv',assembly,['Designator','Mid X','Mid Y','Layer','Rotation'])
writecsv('Complete_BOM.csv',rows,['Designator','Value','Comment','Footprint','LCSC Part #','JLCPCB Class','DNP','Assembly'])
writecsv('Manual_Assembly.csv',manual,['Designator','Value','Comment','Footprint','Assembly','Requirement'])
report['pcba_components']=len(assembly);report['manual_components']=[r['Designator'] for r in manual]
report['pcba_class_counts']=dict(collections.Counter(r['JLCPCB Class'] for r in assembly))
report['pcba_unique_parts']=len(groups)
(O/'electrical_mechanical_audit.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2))
if issues:sys.exit(1)
