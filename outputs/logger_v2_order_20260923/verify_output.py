from pathlib import Path
import zipfile,xml.etree.ElementTree as E,json,hashlib,csv
p=Path(__file__).resolve().parent
d=json.loads((p/'bom_data.json').read_text(encoding='utf8'))
z=zipfile.ZipFile(p/'logger_v2_DigiKey_BOM.xlsx')
assert z.testzip() is None
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
strings=[''.join(i.itertext()) for i in E.fromstring(z.read('xl/sharedStrings.xml'))]
print('Molex string:',[s for s in strings if '0430450400' in s])
for n in z.namelist():
 if n.startswith('xl/worksheets/sheet') and n.endswith('.xml'):
  assert not [c for c in E.fromstring(z.read(n)).findall('.//s:c',ns) if c.get('t')=='e']
rows=list(csv.DictReader((p/'DigiKey_upload.csv').open(encoding='utf-8-sig')))
assert len(rows)==31 and sum(int(r['Quantity']) for r in rows)==189
root=p.parents[1]/'circuit/logger_v2'
assert all(hashlib.sha256((root/f).read_bytes()).hexdigest()==h for f,h in d['hashes'].items())
assert {r['Customer Reference']:r['Quantity'] for r in rows if r['Customer Reference'] in ['D2','D3']}=={'D2':'3','D3':'3'}
print('XLSX integrity/formulas, CSV 31 lines/189pcs, D2/D3 assignments, and unchanged schematic/PCB hashes: PASS')
