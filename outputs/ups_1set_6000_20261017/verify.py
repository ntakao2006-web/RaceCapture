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
    assert row['Required']==row['Quantity']==len(rr)
    assert row['Order_Quantity']>=row['Required']
    assert row['Spare']==row['Order_Quantity']-row['Required']
    assert row['Stock'] >= row.get('Order_Units',row['Order_Quantity'])
    for ref in rr:
        assert ref not in refs
        refs.add(ref)
        assert symbols[ref]['MPN']==row['Design_MPN'],(ref,symbols[ref]['MPN'])
        assert symbols[ref]['Footprint']==row['Footprint']
assert refs==set(symbols) and len(refs)==40
for r in data['DigiKey']:
    price=[p for threshold,p in r['Price_Tiers'] if threshold<=r['Order_Quantity']][-1]
    assert price==r['Unit_Price'],r['References']
assert sum(r['Line_Total'] for r in data['DigiKey'])==6014
assert sum(r['Line_Total'] for r in data['Akizuki'])==745
with (out/'DigiKey_upload_1set.csv').open(encoding='utf-8-sig',newline='') as f:dk=list(csv.DictReader(f))
assert len(dk)==20 and sum(int(r['Quantity']) for r in dk)==115
assert [(r['DigiKey Part Number'],int(r['Quantity']),r['Customer Reference']) for r in dk]==[(r['Supplier_Part_Number'],r['Order_Quantity'],r['References']) for r in data['DigiKey']]
with (out/'Akizuki_Akihabara_1set.csv').open(encoding='utf-8-sig',newline='') as f:ak=list(csv.DictReader(f))
assert len(ak)==7 and sum(int(r['購入個数']) for r in ak)==89
assert sum(int(r['税込小計円']) for r in ak)==745
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(out/'UNO_Q_UPS_1set_6000yen.xlsx') as z:
    for path,expected in [('xl/worksheets/sheet1.xml',{'B4':6014,'D4':6615,'H4':7360,'D30':30,'E30':115,'F30':85,'H30':6014}),('xl/worksheets/sheet2.xml',{'H4':745,'F17':10,'G17':79,'H17':745})]:
        tree=ET.fromstring(z.read(path));cells={c.attrib['r']:c for c in tree.findall('.//m:c',ns)}
        for key,value in expected.items():assert float(cells[key].find('m:v',ns).text)==value,(path,key)
        assert not [c.attrib['r'] for c in cells.values() if c.attrib.get('t')=='e']
report={**data['totals'],'schematic_references':40,'schematic_MPN_and_footprints_reconciled':True,'price_tiers_verified':True,'exported_formula_cache_verified':True,'csv_verified':True,'akihabara_stock_sufficient_at_check':True}
(out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
