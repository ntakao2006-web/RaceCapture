import json,csv,zipfile,xml.etree.ElementTree as ET,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
out=Path(__file__).parent
sys.path.insert(0,str(root/'outputs/ups_revision_20261016'))
from inspect_design import blocks,props
data=json.loads((out/'selection.json').read_text(encoding='utf-8'))
sch=(root/'circuit/logger_v2_ups/logger_v2_ups.kicad_sch').read_text(encoding='utf-8')
symbols={p['Reference']:p for _,_,b in blocks(sch,'symbol') if (p:=props(b)).get('Reference','').startswith(('C','J','L','Q','R','U'))}
refs=set()
for row in data['DigiKey']+data['Akizuki']:
    rr=[s.strip() for s in row['References'].split(',')]
    assert row['Quantity']==len(rr)
    assert row['Required_2sets']==2*len(rr)
    for ref in rr:
        assert ref not in refs
        refs.add(ref)
        assert symbols[ref]['MPN']==row.get('Design_MPN',row['MPN']),(ref,symbols[ref]['MPN'])
        assert symbols[ref]['Footprint']==row['Footprint']
assert refs==set(symbols),(refs^set(symbols))
with (out/'DigiKey_upload_2sets.csv').open(encoding='utf-8-sig',newline='') as f:
    dk=list(csv.DictReader(f))
assert len(dk)==22 and sum(int(r['Quantity']) for r in dk)==192
with (out/'Akizuki_shopping_2sets.csv').open(encoding='utf-8-sig',newline='') as f:
    ak=list(csv.DictReader(f))
assert len(ak)==5 and sum(int(r['購入個数']) for r in ak)==58
assert sum(int(r['税込小計円']) for r in ak)==550
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(out/'UNO_Q_UPS_2sets_DigiKey_Akizuki.xlsx') as z:
    for path,expected in [('xl/worksheets/sheet1.xml',{'D31':33,'E31':66,'F31':192,'G31':126}),('xl/worksheets/sheet2.xml',{'E14':14,'H14':58,'I14':44,'K14':550})]:
        tree=ET.fromstring(z.read(path));cells={c.attrib['r']:c for c in tree.findall('.//m:c',ns)}
        for key,value in expected.items():assert float(cells[key].find('m:v',ns).text)==value,(path,key)
        assert not [c.attrib['r'] for c in cells.values() if c.attrib.get('t')=='e']
report={'schematic_references':len(refs),'required_parts':80,'DigiKey_lines':22,'DigiKey_order_pieces':192,'Akizuki_lines':5,'Akizuki_order_pieces':58,'Akizuki_tax_included_yen':550,'spare_pieces':170,'schematic_MPN_and_footprint_reconciled':True,'exported_formula_cache_verified':True}
(out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
