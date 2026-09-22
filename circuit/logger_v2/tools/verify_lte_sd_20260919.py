from pathlib import Path
import json,hashlib,collections,xml.etree.ElementTree as ET
import sexpdata as sx
P=Path(__file__).resolve().parents[1]
B=P/'logger_v2-backups/before_lte_sd_20260919'
def ch(a,k):return [v for v in a if isinstance(v,list) and v and str(v[0])==k]
def one(a,k):return ch(a,k)[0]
def prop(a,k):return next(v for v in ch(a,'property') if v[1]==k)
def read(p):return sx.loads(p.read_text(encoding='utf8'))
before=read(B/'logger_v2.kicad_sch');after=read(P/'logger_v2.kicad_sch');child=read(P/'logger_v2_lte_sd.kicad_sch')
old={prop(x,'Reference')[2]:x for x in ch(before,'symbol')};new={prop(x,'Reference')[2]:x for x in ch(after,'symbol')}
physical=[r for r in old if not r.startswith('#') and r!='U2']
for r in physical:assert old[r]==new[r],r
for file in ['logger_v2.kicad_pcb','logger_v2.kicad_pro']:assert (P/file).read_bytes()==(B/file).read_bytes(),file
assert not any(ch(child,t) for t in ['wire','label','global_label','hierarchical_label','junction','no_connect'])
parts=ch(child,'symbol');assert len(parts)==44
assert all('power:' not in one(x,'lib_id')[1] for x in parts)
libs={x[1]:x for x in ch(one(child,'lib_symbols'),'symbol')}
for c in parts:
    symbol=libs[one(c,'lib_id')[1]];pins={one(x,'number')[1] for sub in ch(symbol,'symbol') for x in ch(sub,'pin')}
    lib,fp=prop(c,'Footprint')[2].split(':');f=read(P/(lib+'.pretty')/(fp+'.kicad_mod'));pads={x[1] for x in ch(f,'pad') if x[1]}
    assert pads==pins,(prop(c,'Reference')[2],pads-pins,pins-pads)
    for m in ch(f,'model'):assert Path(m[1].replace('${KIPRJMOD}',str(P))).is_file(),m[1]
# Verify physical pin count, complete SIM map and geometric orientation/pitch.
sim=libs['logger_v2_expansion:SIM7070G'];mapping={int(one(p,'number')[1]):one(p,'name')[1] for sub in ch(sim,'symbol') for p in ch(sub,'pin')}
assert len(mapping)==68 and set(mapping)==set(range(1,69))
assert {k:mapping[k] for k in [1,3,7,8,9,10,30,31,32,33,53,55,56,57,60]}=={1:'PWRKEY',3:'UART1_DTR',7:'UART1_CTS',8:'UART1_RTS',9:'UART1_TXD',10:'UART1_RXD',30:'SIM_VDD',31:'SIM_DATA',32:'SIM_CLK',33:'SIM_RST',53:'GNSS_ANT',55:'VBAT',56:'VBAT',57:'VBAT',60:'RF_ANT'}
fp=read(P/'logger_v2_expansion.pretty/SIMCom_SIM7070G_LCC68_24x24mm_P1mm.kicad_mod');pads={int(x[1]):one(x,'at')[1:3] for x in ch(fp,'pad')}
assert len(pads)==68 and pads[1]==[-12,-8] and pads[17]==[-12,8] and pads[18]==[-8,12] and pads[34]==[8,12] and pads[35]==[12,8] and pads[51]==[12,-8] and pads[52]==[8,-12] and pads[68]==[-8,-12]
def nets(file):
    r=ET.parse(P/'output'/file).getroot();return {n.attrib['name']:{(x.attrib['ref'],x.attrib['pin']) for x in n.findall('node')} for n in r.find('nets')}
a=nets('before_lte_sd_20260919.xml');b=nets('after_lte_sd_20260919.xml')
frozen=set(physical)-{'R7'}
def partition(nets):return {frozenset(v for v in nodes if v[0] in frozen) for nodes in nets.values() if any(v[0] in frozen for v in nodes)}
assert partition(a)==partition(b),'Existing non-GNSS connectivity changed'
checks={'+3V3':{'6','7','8'},'GND':{'1','10','12'},'/GNSS_TXD':{'2'},'/GNSS_RXD':{'3'},'/GNSS_PPS':{'4'},'/GNSS_RESET_N':{'9'},'/GNSS_RF':{'11'},'Net-(U2-LNA_EN)':{'13'}}
for net,pins in checks.items():assert {pin for ref,pin in b[net] if ref=='U2'}==pins,(net,b.get(net))
assert ('R7','1') in b['+3V3']
assert any(nodes=={('U2','14')} for nodes in b.values())
for nodes in b.values():assert not(any(ref in {prop(x,'Reference')[2] for x in parts} for ref,pin in nodes) and len({ref for ref,pin in nodes})>1),('Unexpected additional connectivity',nodes)
erc=json.loads((P/'output/after_lte_sd_erc.json').read_text());counts={}
for sheet in erc['sheets']:
    counts[sheet['path']]=dict(collections.Counter(v['type'] for v in sheet['violations']))
    if sheet['path']=='/':assert counts[sheet['path']]=={'label_dangling':1},counts
    else:assert set(counts[sheet['path']])<= {'pin_not_connected','pin_not_driven','power_pin_not_driven'},counts
result={'existing_physical_symbols_preserved':len(physical),'existing_non_GNSS_net_partition_unchanged':True,'pcb_and_project_byte_identical':True,'new_unwired_parts':len(parts),'all_new_pins_match_footprint_pads':True,'all_model_paths_exist':True,'gnss_functional_pin_mapping_verified':True,'erc':counts}
(P/'output/lte_sd_verification_20260919.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False,indent=2))
