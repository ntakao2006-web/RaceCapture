"""Dimension-based models; no claimed manufacturer STEP provenance."""
from pathlib import Path
import FreeCAD as A, Part
P=Path(__file__).resolve().parents[1]
V=A.Vector
def box(x,y,z,l,w,h):return Part.makeBox(l,w,h,V(x,y,z))
def save(name,shapes):
    shape=Part.makeCompound(shapes);assert shape.isValid()
    shape.exportStep(str(P/'3dmodels'/name))
    b=shape.BoundBox;print(name,'solids',len(shape.Solids),'dimensions',b.XLength,b.YLength,b.ZLength)
# SIM7070G nominal 24 x 24 x 2.3 mm. Lands 0.6 wide, 1.0 pitch;
# CAD Y axis is opposite KiCad pad Y. Pin 1 is upper left in top PCB view.
shapes=[box(-12,-12,.06,24,24,.74),box(-11.25,-11.25,.8,22.5,22.5,1.5)]
for i in range(17):
    t=-8+i
    shapes.extend([box(-12,t-.3,0,1,.6,.8),box(11,t-.3,0,1,.6,.8),box(t-.3,-12,0,.6,1,.8),box(t-.3,11,0,.6,1,.8)])
save('SIMCom_SIM7070G_mechanical.step',shapes)
# TI RGT16: 3x3 body, 0.5 pitch, 1.68 EP; nominal 0.9 high.
shapes=[box(-1.5,-1.5,.02,3,3,.88),box(-.84,-.84,0,1.68,1.68,.02)]
for i in range(4):
    t=-.75+i*.5
    shapes.extend([box(-1.5,t-.125,0,.4,.25,.2),box(1.1,t-.125,0,.4,.25,.2),box(t-.125,-1.5,0,.25,.4,.2),box(t-.125,1.1,0,.25,.4,.2)])
save('TI_TPS62130_RGT16_mechanical.step',shapes)
