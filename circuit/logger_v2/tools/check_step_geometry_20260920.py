from pathlib import Path
import csv,json
import FreeCAD as App
import Part
P=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((P/'output/部品選定_20260920.csv').open(encoding='utf-8-sig')))
# STEP paths are project-local, one per assigned footprint.
import re
models=set()
for r in rows:
    lib,fp=r['Footprint'].split(':')
    text=(P/(lib+'.pretty')/(fp+'.kicad_mod')).read_text(encoding='utf8')
    models.update(re.findall(r'\(\s*model\s+"([^"]+)"',text))
result=[]
for path in sorted(models):
    file=Path(path.replace('${KIPRJMOD}',str(P)))
    s=Part.Shape();s.read(str(file));bb=s.BoundBox
    assert not s.isNull() and len(s.Faces)>0,file
    result.append({'file':file.name,'valid':s.isValid(),'faces':len(s.Faces),'solids':len(s.Solids),'size_mm':[bb.XLength,bb.YLength,bb.ZLength]})
(P/'output/selection_step_geometry.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('Assigned STEP files with geometry:',len(result),'valid:',sum(x['valid'] for x in result))
