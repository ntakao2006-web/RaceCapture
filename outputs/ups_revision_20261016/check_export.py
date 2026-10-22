from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import json,csv
p=Path(__file__).parent
with ZipFile(p/'UNO_Q_UPS_BOM.xlsx') as z:
    assert z.testzip() is None
    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    sheet=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    cells={c.attrib['r']:c for c in sheet.findall('.//m:c',ns)}
    assert cells['B35'].find('m:f',ns).text=='SUM(B8:B34)'
    assert float(cells['B35'].find('m:v',ns).text)==40
    date=cells['I8'];assert date.attrib.get('t')=='d' and date.find('m:v',ns).text.startswith('2026-10-16')
    values=[int(cells[f'B{i}'].find('m:v',ns).text) for i in range(8,35)]
    assert sum(values)==40
with (p/'DigiKey_upload.csv').open(encoding='utf-8-sig',newline='') as f:
    rows=list(csv.DictReader(f));assert len(rows)==26
    assert sum(int(r['Quantity']) for r in rows)==34
print('Export verified: XLSX ZIP/XML, quantities, total formula/cache, typed dates and DigiKey CSV.')
