from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET
import sexpdata as sx
P=Path(__file__).resolve().parents[1];O=P/'output/design_review_20260907'
def ch(a,k):return [z for z in a if isinstance(z,list) and z and str(z[0])==k]
def one(a,k):return ch(a,k)[0]
def prop(a,k):return next(z for z in ch(a,'property') if z[1]==k)
old=ET.parse(O/'circuit_review_source.xml').getroot();new=ET.parse(O/'reviewed_netlist.xml').getroot()
refs={z.attrib['ref'] for z in old.findall('./components/comp')}
om={};nm={};groups={}
for net in old.findall('./nets/net'):
    keys={(z.attrib['ref'],'3' if z.attrib['ref']=='Y1' and z.attrib['pin']=='2' else z.attrib['pin']) for z in net.findall('node')}
    for k in keys:om[k]=keys
for net in new.findall('./nets/net'):
    keys={(z.attrib['ref'],z.attrib['pin']) for z in net.findall('node')};groups[net.attrib['name']]=keys
    filtered={k for k in keys if k[0] in refs and k not in {('Y1','2'),('Y1','4')}}
    for k in filtered:nm[k]=filtered
assert om==nm,'Old component net connectivity changed'
assert {('Y1','2'),('Y1','4'),('C2','2'),('C3','2')} <= groups['GND']
assert {('D11','2'),('J1','1'),('L1','1'),('U2','11')} == groups['/GNSS_RF']
expected_rails={'C4':'+3V3','C5':'+5V','C6':'+3V3','C7':'+3V3','C8':'+3V3','C9':'+5V','C10':'+3V3','C11':'+3V3','C12':'+3V3','C13':'+3V3','C14':'+5V'}
for ref,rail in expected_rails.items():assert (ref,'1') in groups[rail] and (ref,'2') in groups['GND'],ref
for ref,net in [('R18','/SPI2_MOSI'),('R19','/SPI2_SCK'),('R20','/STATUS_LATCH')]:assert (ref,'1') in groups[net] and (ref,'2') in groups['GND'],ref
a=sx.loads((P/'logger_v2.kicad_sch').read_text(encoding='utf-8'))
lib={z[1]:z for z in ch(one(a,'lib_symbols'),'symbol')}
parts={prop(z,'Reference')[2]:z for z in ch(a,'symbol') if not prop(z,'Reference')[2].startswith('#')}
models=set()
for ref,c in parts.items():
    sym=lib[one(c,'lib_id')[1]]
    pins={one(pin,'number')[1] for sub in ch(sym,'symbol') for pin in ch(sub,'pin')}
    fp=prop(c,'Footprint')[2];prefix,name=fp.split(':',1)
    f=sx.loads((P/(prefix+'.pretty')/(name+'.kicad_mod')).read_text(encoding='utf-8'))
    pads={z[1] for z in ch(f,'pad') if z[1]}
    assert pins==pads,(ref,pins,pads)
    for model in ch(f,'model'):
        assert model[1].startswith('${KIPRJMOD}/'),(ref,model[1])
        path=Path(model[1].replace('${KIPRJMOD}',str(P)));assert path.is_file(),(ref,path);models.add(str(path.relative_to(P)))
erc=json.loads((O/'reviewed_erc.json').read_text(encoding='utf-8'))
violations=[v for sheet in erc.get('sheets',[]) for v in sheet.get('violations',[])]
assert not violations,violations
report={'schematic_sha256':hashlib.sha256((P/'logger_v2.kicad_sch').read_bytes()).hexdigest(),'old_component_count':len(refs),'new_component_count':len(parts),'new_components':sorted(set(parts)-refs),'old_net_groups_preserved':True,'Y1_pin_mapping':'old pin2 -> new pin3; case pins2/4 grounded','Y1_ground_case_pins_verified':True,'new_caps_and_pulldowns_verified':True,'RF_ESD_verified':True,'all_symbol_pin_sets_match_footprint_pad_sets':True,'portable_models_verified':len(models),'erc_violations':0,'DNP':sorted(ref for ref,c in parts.items() if str(one(c,'dnp')[1])=='yes')}
(O/'schematic_connectivity_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
