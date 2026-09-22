from pathlib import Path
import FreeCAD as A,Part,json
P=Path(__file__).resolve().parents[1]
V=A.Vector
def box(x,y,z,l,w,h):return Part.makeBox(l,w,h,V(x,y,z))
def export(name,shapes):
    shape=Part.makeCompound(shapes)
    assert shape.isValid()
    shape.exportStep(str(P/'3dmodels'/name))
    b=shape.BoundBox
    print(name,tuple(round(v,3) for v in (b.XMin,b.XMax,b.YMin,b.YMax,b.ZMin,b.ZMax)),len(shape.Solids))
# Actual NEO-M9N package envelope, nominal height 2.4 mm, castellated land pattern.
pins=[]
ys=[7,5.9,4.8,3.7,2.6,1.5,-1.5,-2.6,-3.7,-4.8,-5.9,-7]
for x in [-6.1,5.1]:
    for y in ys:
        pad=box(x,y-.4,0,1,.8,.82)
        pad=pad.cut(Part.makeCylinder(.25,1,V(-6.1 if x<0 else 6.1,y,-.05)))
        pins.append(pad)
export('u-blox_NEO-M9N-00B_mechanical.step',[box(-6.1,-8,.04,12.2,16,.78),box(-5.7,-7.6,.82,11.4,15.2,1.58),*pins])
# S-037-TGG: body 7x7, horizontal overall length 15, RF axis 6.4 above board.
# Thread is represented by its major-diameter envelope; small chamfers omitted.
body=box(-3.5,-3.5,2.9,7,7,7)
barrel=Part.makeCylinder(3.175,8,V(3.5,0,6.4),V(1,0,0))
bore=Part.makeCylinder(2.3,4,V(7.6,0,6.4),V(1,0,0))
barrel=barrel.cut(bore)
insulator=Part.makeCylinder(2.25,3.0,V(8.3,0,6.4),V(1,0,0)).cut(Part.makeCylinder(.5,3.1,V(8.25,0,6.4),V(1,0,0)))
legs=[box(x-.51,y-.51,-3.9,1.02,1.02,6.8) for x in [-2.54,2.54] for y in [-2.54,2.54]]
signal=Part.makeCylinder(.635,6.8,V(0,0,-3.9))
export('COSMTEC_S-037-TGG_mechanical.step',[body,barrel,insulator,signal,*legs])
# Module mechanical envelope. PCB outline/pin pitches are dimensioned by Akizuki;
# board thickness, component heights and header standoff are nominal visualization.
shapes=[box(-5.19,-9.31,3,18,11,1.6),box(-.6,-6.3,4.6,5.2,3.8,1.2)]
for y in [0,-7.62]:
    shapes.append(box(-1.27,y-1.27,.46,10.16,2.54,2.54))
    for x in [0,2.54,5.08,7.62]:shapes.append(box(x-.25,y-.25,-3,.5,.5,8.1))
export('Akizuki_AE-BNO055-BO_mechanical.step',shapes)
