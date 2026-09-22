from pathlib import Path
import pcbnew as b,json
P=Path(__file__).resolve().parents[1]
rows=json.loads((P/'output/lte_sd_models_20260919.json').read_text())
rows.insert(0,{'footprint':'logger_v2_custom:MAX_M10M_00B_LCC18','model':'u-blox_MAX-M10M-00B.step'})
board=b.BOARD();board.SetFileName(str(P/'output/lte_sd_model_catalog.kicad_pcb'))
for i,row in enumerate(rows):
    lib,name=row['footprint'].split(':');f=b.FootprintLoad(str(P/(lib+'.pretty')),name);assert f,name
    x=25+(i%5)*40;y=25+(i//5)*40
    f.SetPosition(b.VECTOR2I(b.FromMM(x),b.FromMM(y)));f.SetReference('P'+str(i+1));f.SetValue(name)
    for m in f.Models():m.m_Filename=m.m_Filename.replace('${KIPRJMOD}',str(P).replace('\\','/'))
    board.Add(f)
    t=b.PCB_TEXT(board);t.SetText(str(i+1));t.SetPosition(b.VECTOR2I(b.FromMM(x-12),b.FromMM(y-14)));t.SetTextSize(b.VECTOR2I(b.FromMM(2),b.FromMM(2)));t.SetLayer(b.F_SilkS);board.Add(t)
for a,c in [((4,4),(206,4)),((206,4),(206,165)),((206,165),(4,165)),((4,165),(4,4))]:
    l=b.PCB_SHAPE();l.SetShape(b.SHAPE_T_SEGMENT);l.SetLayer(b.Edge_Cuts);l.SetStart(b.VECTOR2I(b.FromMM(a[0]),b.FromMM(a[1])));l.SetEnd(b.VECTOR2I(b.FromMM(c[0]),b.FromMM(c[1])));l.SetWidth(b.FromMM(.05));board.Add(l)
b.SaveBoard(str(P/'output/lte_sd_model_catalog.kicad_pcb'),board)
path=P/'output/lte_sd_model_catalog.kicad_pcb'
path.write_text(path.read_text(encoding='utf8').replace('${KIPRJMOD}/3dmodels/','${KIPRJMOD}/../3dmodels/'),encoding='utf8')
print('Catalog saved:',len(rows),'packages')
