from pathlib import Path
import sexpdata as sx
import json, xml.etree.ElementTree as ET, csv

P = Path(__file__).resolve().parents[1]
def ch(a,k): return [v for v in a if isinstance(v,list) and v and str(v[0])==k]
def one(a,k): return ch(a,k)[0]
def prop(a,k): return next(v for v in ch(a,'property') if v[1]==k)
def read(p): return sx.loads(p.read_text(encoding='utf-8'))
base=read(P/'logger_v2-backups/phase1_source/logger_v2.kicad_sch')
sch=read(P/'logger_v2.kicad_sch')
old={prop(v,'Reference')[2]:v for v in ch(base,'symbol')}
new={prop(v,'Reference')[2]:v for v in ch(sch,'symbol')}
physical={r:v for r,v in old.items() if not r.startswith('#')}
assert set(physical)=={r for r in new if not r.startswith('#')}
assert one(base,'paper')==one(sch,'paper')
assert one(base,'title_block')==one(sch,'title_block')
for ref,c in old.items():
    if ref in ['#PWR03','#PWR025']:
        assert ref not in new
        continue
    d=new[ref]
    for key in ['uuid','at','mirror','unit','lib_id','pin','instances']:
        assert ch(c,key)==ch(d,key),(ref,key)
    for p in ch(c,'property'):
        q=prop(d,p[1])
        assert p[3:]==q[3:],(ref,p[1],'display geometry changed')
        if p[1] not in ['Footprint','Datasheet'] and not(ref in ['R7','C1'] and p[1]=='Value'):
            assert p[2]==q[2],(ref,p[1],'unexpected value change')
oldlibs={v[1]:v for v in ch(one(base,'lib_symbols'),'symbol')}
libs={v[1]:v for v in ch(one(sch,'lib_symbols'),'symbol')}
for name,lib in oldlibs.items():
    assert lib==libs[name],(name,'symbol definition changed')
oldwires={one(w,'uuid')[1]:w for w in ch(base,'wire')}
newwires={one(w,'uuid')[1]:w for w in ch(sch,'wire')}
assert len(set(oldwires)-set(newwires))==4
for key in set(oldwires)&set(newwires):
    assert oldwires[key]==newwires[key],('Original wire edited',key)

exp=json.loads((P/'output/expected_connectivity.json').read_text())
actual={}; groups={}
for net in ET.parse(P/'output/logger_v2.xml').getroot().findall('./nets/net'):
    name=net.attrib['name'].lstrip('/')
    keys={v.attrib['ref']+'.'+v.attrib['pin'] for v in net.findall('node') if not v.attrib['ref'].startswith('#')}
    if not keys: continue
    groups[name]=keys
    for k in keys: actual[k]=name
assert set(actual)==set(exp),(set(actual)^set(exp))
for key,name in exp.items():
    expected={key} if name is None else {k for k,v in exp.items() if v==name}
    assert groups[actual[key]]==expected,(key,name,actual[key],sorted(groups[actual[key]]^expected))

rows=[]
for ref,c in physical.items():
    d=new[ref]; lib=libs[one(d,'lib_id')[1]]
    pins=[one(v,'number')[1] for sub in ch(lib,'symbol') for v in ch(sub,'pin')]
    assert len(pins)==len(set(pins)),ref
    fp=prop(d,'Footprint')[2]
    f=read(P/'logger_v2_custom.pretty'/(fp.split(':',1)[1]+'.kicad_mod'))
    pads={v[1] for v in ch(f,'pad') if v[1]}
    assert set(pins)==pads,(ref,set(pins)^pads)
    models=ch(f,'model'); assert len(models)==1
    path=Path(models[0][1].replace('${KIPRJMOD}',str(P)))
    assert path.exists() and path.stat().st_size>1000,(ref,path)
    assert path.read_bytes().startswith(b'ISO-10303-21;'),ref
    rows.append({'Reference':ref,'Value':prop(d,'Value')[2],'DNP':str(one(d,'dnp')[1]),'Footprint':fp,'Model':path.name,'Pin_count':len(pins),'Pad_numbers':','.join(sorted(pads,key=lambda v:int(v)))})
erc=json.loads((P/'output/erc.json').read_text(encoding='utf-8'))
violations=[v for sh in erc.get('sheets',[]) for v in sh['violations']]
assert not [v for v in violations if v['severity']=='error'],violations
assert all(v['type']=='lib_symbol_mismatch' and len(v['items'])==1 and v['items'][0]['uuid']==one(new['U1'],'uuid')[1] for v in violations),violations
baseline_erc=json.loads((P/'output/original_erc.json').read_text(encoding='utf-8'))
assert any(v['type']=='lib_symbol_mismatch' and any(i['uuid']==one(old['U1'],'uuid')[1] for i in v['items']) for sh in baseline_erc['sheets'] for v in sh['violations'])
assert (P/'logger_v2-backups/phase1_source/logger_v2.kicad_pcb').read_bytes()==(P/'logger_v2.kicad_pcb').read_bytes()
assert (P/'logger_v2-backups/phase1_source/logger_v2.kicad_pro').read_bytes()==(P/'logger_v2.kicad_pro').read_bytes()
with (P/'output/parts_and_models.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(sorted(rows,key=lambda r:(r['Reference'][0],int(r['Reference'][1:]))))
report={'paper':'A4','original_components_retained':len(physical),'original_component_positions_rotations_UUIDs_and_fields_unchanged':True,'original_symbol_definitions_unchanged':True,'retained_power_symbols':len(old)-len(physical)-2,'removed_obsolete_power_symbols':['#PWR03 (unused VIN)','#PWR025 (J7 pin 1 +5V)'],'original_wires_retained_unchanged':len(set(oldwires)&set(newwires)),'original_wire_segments_replaced':4,'physical_pins':len(exp),'all_pin_connectivity_groups_match':True,'unique_footprints':len({v['Footprint'] for v in rows}),'all_pin_pad_sets_match':True,'all_models_are_local_STEP':True,'erc_errors':0,'erc_warnings':len(violations),'erc_warning_details':[v['description'] for v in violations],'only_ERC_warning_also_present_in_original':True,'PCB_unchanged':True,'project_settings_unchanged':True,'DNP':sorted([v['Reference'] for v in rows if v['DNP']=='yes'])}
(P/'output/validation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
