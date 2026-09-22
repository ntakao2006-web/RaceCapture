"""Run with FreeCAD Python. Preserve manufacturer geometry; normalize PCB axes."""
from pathlib import Path
import FreeCAD as App
import Part
import json
P=Path(__file__).resolve().parents[1]
s=Part.Shape()
s.read(str(P/'refs/TE_2452796-1_original.step'))
volume=s.Volume
s.rotate(App.Vector(0,0,0),App.Vector(1,0,0),90)
s.translate(App.Vector(0,-7,.695))
assert s.isValid() and abs(s.Volume-volume)<1e-6
s.exportStep(str(P/'3dmodels/TE_2452796-1.step'))
reopened=Part.Shape();reopened.read(str(P/'3dmodels/TE_2452796-1.step'))
assert reopened.isValid() and abs(reopened.Volume-volume)/volume<2e-5
v,f=reopened.tessellate(.035)
(P/'output/TE_2452796-1_mesh.json').write_text(json.dumps({'vertices':[[a.x,a.y,a.z] for a in v],'faces':f}))
report=P/'output/TE_2452796-1_verification.json'
r=json.loads(report.read_text());bb=reopened.BoundBox
r['model']={'source':'TE Customer View Model CVM_2452796-1 Rev A','transform':'Rx +90 degrees, translation (0,-7,+0.695) mm','valid':True,'solids':len(reopened.Solids),'size_mm':[bb.XLength,bb.YLength,bb.ZLength],'z_min_mm':bb.ZMin,'rigid_transform_only':True,'step_roundtrip_volume_relative_error':abs(reopened.Volume-volume)/volume,'render':'TE_2452796-1_3D.png'}
report.write_text(json.dumps(r,indent=2),encoding='utf8')
print('Manufacturer STEP geometry preserved; normalized model valid:',bb)
