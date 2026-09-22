from pathlib import Path
import json
import FreeCAD as App
import Part
P=Path(__file__).resolve().parents[1]
r=json.loads((P/'output/parts_preparation_20260921.json').read_text(encoding='utf8'));rows=[]
for file in r['model_files']:
 s=Part.Shape();s.read(file);assert not s.isNull() and s.isValid(),file
 rows.append({'file':Path(file).name,'valid':True,'faces':len(s.Faces)})
(P/'output/prepared_step_check_20260921.json').write_text(json.dumps(rows,indent=2),encoding='utf8');print(len(rows),'valid STEP geometries')
