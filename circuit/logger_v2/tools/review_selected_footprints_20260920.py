from pathlib import Path
import pcbnew as p
P=Path(__file__).resolve().parents[1]
b=p.BOARD()
for lib,name,ref,x,y in [('logger_v2_custom','Toshiba_SOP16_P300_1.27A','U1',25,25),('logger_v2_expansion','Molex_47219-2001','SD',48,25)]:
    f=p.FootprintLoad(str(P/(lib+'.pretty')),name)
    assert f is not None
    f.SetReference(ref);f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));b.Add(f)
for a,c in [((12,12),(65,12)),((65,12),(65,40)),((65,40),(12,40)),((12,40),(12,12))]:
    s=p.PCB_SHAPE();s.SetShape(p.SHAPE_T_SEGMENT);s.SetStart(p.VECTOR2I(*[p.FromMM(t) for t in a]));s.SetEnd(p.VECTOR2I(*[p.FromMM(t) for t in c]));s.SetLayer(p.Edge_Cuts);s.SetWidth(p.FromMM(.05));b.Add(s)
out=P/'output/selected_footprints_review.kicad_pcb'
p.SaveBoard(str(out),b)
text=out.read_text(encoding='utf8').replace('${KIPRJMOD}/3dmodels/','${KIPRJMOD}/../3dmodels/')
out.write_text(text,encoding='utf8')
print(out)
