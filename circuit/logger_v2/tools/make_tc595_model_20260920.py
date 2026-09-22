"""Nominal mechanical proxy from Toshiba SOP16-P-300-1.27A dimensions.
Not a manufacturer STEP or a solder-joint tolerance model.
"""
from pathlib import Path
import FreeCAD as App
import Part
P=Path(__file__).resolve().parents[1]
body=Part.makeBox(5.3,10.3,1.5,App.Vector(-2.65,-5.15,.2))
# Shallow pin-1 dot, no exterior-envelope change.
body=body.cut(Part.makeCylinder(.23,.08,App.Vector(-1.85,4.35,1.63)))
parts=[body]
for i in range(8):
    y=-4.445+i*1.27
    for sign in [-1,1]:
        # Bent lead represented by joined vertical and horizontal rectangular sections.
        x=2.65 if sign==1 else -3.9
        foot=Part.makeBox(1.25,.4,.2,App.Vector(x,y-.2,0))
        riser=Part.makeBox(.2,.4,.65,App.Vector(2.65 if sign==1 else -2.85,y-.2,.15))
        parts.append(foot.fuse(riser))
shape=Part.makeCompound(parts)
assert shape.isValid()
shape.exportStep(str(P/'3dmodels/TC74HC595AF_nominal.step'))
r=Part.Shape();r.read(str(P/'3dmodels/TC74HC595AF_nominal.step'))
assert r.isValid()
print('Nominal TC74HC595AF STEP:',r.BoundBox)
