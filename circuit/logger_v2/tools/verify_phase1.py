from pathlib import Path
import sexpdata as sx
import json,xml.etree.ElementTree as ET,hashlib,csv
P=Path(__file__).resolve().parents[1]
def ch(a,k):return [z for z in a if isinstance(z,list) and str(z[0])==k]
def one(a,k):return ch(a,k)[0]
def prop(a,k):return next(z for z in ch(a,'property') if z[1]==k)
sch=sx.loads((P/'logger_v2.kicad_sch').read_text(encoding='utf-8'))
libs={v[1]:v for v in ch(one(sch,'lib_symbols'),'symbol')}
parts=[v for v in ch(sch,'symbol') if not prop(v,'Reference')[2].startswith('#')]
exp=json.loads((P/'output/expected_connectivity.json').read_text())
r=ET.parse(P/'output/logger_v2.xml').getroot();actual={};groups={}
for n in r.findall('./nets/net'):
    name=n.attrib['name'].lstrip('/')
    keys={z.attrib['ref']+'.'+z.attrib['pin'] for z in n.findall('node') if not z.attrib['ref'].startswith('#')}
    groups[name]=keys
    for k in keys:actual[k]=name
for k,v in exp.items():
    assert k in actual,('missing pin',k)
    if v is not None:assert actual[k]==v,(k,v,actual[k])
    else:assert actual[k].startswith('unconnected-'),('Unexpected connection',k,actual[k])
for name in set(v for v in exp.values() if v):
    expected={k for k,v in exp.items() if v==name}
    assert groups[name]==expected,(name,groups[name]^expected)
rows=[]
for c in parts:
    ref=prop(c,'Reference')[2];lib=libs[one(c,'lib_id')[1]]
    pins=[one(v,'number')[1] for z in ch(lib,'symbol') for v in ch(z,'pin')]
    assert len(pins)==len(set(pins)),ref
    fp=prop(c,'Footprint')[2];name=fp.split(':')[1]
    f=sx.loads((P/'logger_v2_custom.pretty'/(name+'.kicad_mod')).read_text(encoding='utf-8'))
    pads={v[1] for v in ch(f,'pad') if v[1]}
    assert set(pins)==pads,(ref,set(pins)^pads)
    models=ch(f,'model');assert len(models)==1
    path=Path(models[0][1].replace('${KIPRJMOD}',str(P)))
    assert path.exists() and path.stat().st_size>1000,(ref,path)
    assert path.read_bytes().startswith(b'ISO-10303-21;'),(ref,'Not actual STEP',path)
    rows.append({'Reference':ref,'Value':prop(c,'Value')[2],'DNP':str(one(c,'dnp')[1]),'Footprint':fp,'Model':path.name,'Pin_count':len(pins),'Pad_numbers':','.join(sorted(pads,key=lambda v:int(v)))})
erc=json.loads((P/'output/erc.json').read_text(encoding='utf-8'))
violations=[v for sh in erc.get('sheets',[]) for v in sh['violations']]
assert not violations,[v['type'] for v in violations]
baseline=P/'logger_v2-backups/phase1_source/logger_v2.kicad_pcb'
assert baseline.read_bytes()==(P/'logger_v2.kicad_pcb').read_bytes(),'Existing PCB modified'
with (P/'output/parts_and_models.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(sorted(rows,key=lambda r:(r['Reference'][0],int(r['Reference'][1:]))))
report={'parts':len(parts),'physical_pins':len(exp),'unique_footprints':len({v['Footprint'] for v in rows}),'all_pin_pad_sets_match':True,'all_nets_match':True,'all_models_are_local_STEP':True,'erc_violations':len(violations),'PCB_unchanged':True,'DNP':[v['Reference'] for v in rows if v['DNP']=='yes']}
(P/'output/validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
