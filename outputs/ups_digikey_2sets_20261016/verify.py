from pathlib import Path
import sys,re,json,csv,xml.etree.ElementTree as ET,zipfile,hashlib
out=Path(__file__).resolve().parent;root=out.parents[1];project=root/'circuit/logger_v2_ups'
sys.path.insert(0,str(out.parent/'ups_revision_20261016'))
from inspect_design import blocks,props
sel=json.loads((out/'selection.json').read_text(encoding='utf8'));refs=set(sel['refs']);report={}
def lex(s):return re.findall(r'"(?:[^"\\]|\\.)*"|[^\s()]+|[()]',s)
for ext,kind in [('kicad_sch','symbol'),('kicad_pcb','footprint')]:
    before=(out/'backup'/('logger_v2_ups.'+ext)).read_text(encoding='utf8');after=(project/('logger_v2_ups.'+ext)).read_text(encoding='utf8')
    def scrub(s):
        for a,z,b in reversed(list(blocks(s,kind))):
            if props(b).get('Reference') not in refs:continue
            for pa,pz,p in reversed(list(blocks(b,'property',2))):
                m=re.match(r'\(property\s+"([^"]+)"',p)
                if not m:continue
                key=m[1]
                if key in set(sel['updates'])|{'Footprint'}:b=b[:pa]+b[pz:]
            if kind=='footprint':
                for obj in ['fp_line','model','descr']:
                    for pa,pz,p in reversed(list(blocks(b,obj,2))):b=b[:pa]+b[pz:]
                b=re.sub(r'^\(footprint "[^"]+"','(footprint "CAP"',b)
            s=s[:a]+b+s[z:]
        return lex(s)
    assert scrub(before)==scrub(after),ext
    report[ext+'_only_cap_properties_outlines_model_changed']=True
def nets(p):
    return sorted((n.attrib['name'],tuple(sorted((v.attrib['ref'],v.attrib['pin']) for v in n.findall('node')))) for n in ET.parse(p).findall('./nets/net'))
assert nets(out/'after.xml')==nets(out.parent/'ups_revision_20261016/after.xml')
report['netlist_connectivity_unchanged']=True
def erc(p):return sorted(json.dumps(v,sort_keys=True) for s in json.loads(p.read_text(encoding='utf8'))['sheets'] for v in s['violations'])
assert erc(out/'erc_after.json')==erc(out.parent/'ups_revision_20261016/erc_after.json')
report['ERC']={'existing':28,'new':0}
drc=json.loads((out/'drc_after.json').read_text(encoding='utf8'))
assert all(not drc[k] for k in ['violations','unconnected_items','schematic_parity'])
report['DRC']={'violations':0,'unconnected':0,'schematic_parity':0}
sch=(project/'logger_v2_ups.kicad_sch').read_text(encoding='utf8');pcb=(project/'logger_v2_ups.kicad_pcb').read_text(encoding='utf8')
ss={props(b)['Reference']:props(b) for _,_,b in blocks(sch,'symbol') if props(b).get('Reference','').startswith(('C','R','Q','L','J','U'))}
pp={props(b).get('Reference'):(props(b),re.match(r'\(footprint "([^"]+)"',b)[1],b) for _,_,b in blocks(pcb,'footprint')}
for ref,p in ss.items():
    q,fp,b=pp[ref]
    assert p['Footprint']==fp
    for k in ['Value','MPN','DigiKey','Rating','Manufacturer','Datasheet']:assert p.get(k)==q.get(k),(ref,k)
report['schematic_pcb_metadata_parity']=True
rows=json.loads((out/'bom_data.json').read_text(encoding='utf8'))
for r in rows:
    for ref in r['References'].split(', '):
        assert ss[ref]['MPN']==r['MPN'] and ss[ref]['DigiKey']==r['Supplier_Part_Number']
        assert ss[ref]['Footprint']==r['Footprint']
with (out/'DigiKey_upload_2sets_spares.csv').open(encoding='utf-8-sig',newline='') as f:order=list(csv.DictReader(f))
assert len(order)==27 and sum(int(r['Quantity']) for r in order)==118
for r,o in zip(rows,order):assert o['DigiKey Part Number']==r['Supplier_Part_Number'] and int(o['Quantity'])==r['Order_Quantity']
with zipfile.ZipFile(out/'UNO_Q_UPS_DigiKey_2sets_spares.xlsx') as z:
    e=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    cells={c.attrib['r']:c for c in e.findall('.//s:c',ns)}
    for cell,v in [('D36',40),('E36',80),('F36',38),('G36',118),('G41',1818.96),('G44',581.04)]:assert abs(float(cells[cell].find('s:v',ns).text)-v)<.0001,(cell,v)
    assert not any(c.attrib.get('t')=='e' for c in cells.values())
report['BOM']={'lines':27,'required':80,'spares':38,'order':118,'all_DigiKey':True,'exported_csv_xlsx_verified':True}
report['cap_bank']={'nominal_F':10.5,'minimum_initial_F':8.4,'nominal_energy_ratio_vs_previous':.7,'hold_time_hardware_verified':False}
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2))
