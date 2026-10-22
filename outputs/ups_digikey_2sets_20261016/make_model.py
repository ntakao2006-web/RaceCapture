import FreeCAD,Part
from FreeCAD import Vector
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'circuit/logger_v2_ups/logger_v2_ups.3dshapes/Eaton_HVH1020-2R7705-R_nominal.step'
body=Part.makeCylinder(5,20,Vector(2.5,-3,5.2),Vector(0,-1,0))
shape=Part.makeCompound([body]+[Part.makeCylinder(.3,6.7,Vector(x,0,-1.5),Vector(0,0,1)) for x in (0,5)]+[Part.makeCylinder(.3,3,Vector(x,0,5.2),Vector(0,-1,0)) for x in (0,5)])
shape.exportStep(str(p))
check=Part.Shape();check.read(str(p))
assert check.isValid() and len(check.Solids)==5
assert abs(body.BoundBox.YLength-20)<1e-6 and abs(body.BoundBox.XLength-10)<1e-6
print('Valid nominal STEP: D10 L20 P5, five solids, body setback3, height10.2. Not manufacturer mechanical model.')
