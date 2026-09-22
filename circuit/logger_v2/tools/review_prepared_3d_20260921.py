from pathlib import Path
import pcbnew as p
P=Path(__file__).resolve().parents[1];b=p.BOARD()
for name,ref,x in [('L_Bourns_SRN6045TA','L2',20),('CP_EIA-7343-31_Kemet-D','C15',33),('Prisemi_DFN1006_2L','D12',44),('R_0805_2012Metric','R22',49)]:
 f=p.FootprintLoad(str(P/'logger_v2_expansion.pretty'),name);assert f
 f.SetReference(ref);f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(23)));b.Add(f)
for a,c in [((12,15),(55,15)),((55,15),(55,32)),((55,32),(12,32)),((12,32),(12,15))]:
 s=p.PCB_SHAPE();s.SetShape(p.SHAPE_T_SEGMENT);s.SetStart(p.VECTOR2I(*[p.FromMM(t) for t in a]));s.SetEnd(p.VECTOR2I(*[p.FromMM(t) for t in c]));s.SetLayer(p.Edge_Cuts);s.SetWidth(p.FromMM(.05));b.Add(s)
out=P/'output/prepared_parts_review.kicad_pcb';p.SaveBoard(str(out),b)
out.write_text(out.read_text(encoding='utf8').replace('${KIPRJMOD}/3dmodels/','${KIPRJMOD}/../3dmodels/'),encoding='utf8')
