from pathlib import Path
import pcbnew as b,json
P=Path(__file__).resolve().parents[1]
board=b.BOARD();board.SetFileName(str(P/'output/model_catalog.kicad_pcb'))
data=json.loads((P/'output/model_sources.json').read_text())
for i,v in enumerate(data):
    name=v['footprint'].split(':')[1]
    f=b.FootprintLoad(str(P/'logger_v2_custom.pretty'),name)
    assert f
    x=20+(i%5)*32;y=20+(i//5)*36
    f.SetPosition(b.VECTOR2I(b.FromMM(x),b.FromMM(y)));f.SetReference(str(i+1));f.SetValue(name)
    for model in f.Models():model.m_Filename=model.m_Filename.replace('${KIPRJMOD}',str(P).replace('\\','/'))
    board.Add(f)
    text=b.PCB_TEXT(board);text.SetText(str(i+1));text.SetPosition(b.VECTOR2I(b.FromMM(x-9),b.FromMM(y-8)));text.SetLayer(b.F_SilkS);board.Add(text)
for a,c in [((3,3),(163,3)),((163,3),(163,154)),((163,154),(3,154)),((3,154),(3,3))]:
    line=b.PCB_SHAPE();line.SetShape(b.SHAPE_T_SEGMENT);line.SetLayer(b.Edge_Cuts);line.SetStart(b.VECTOR2I(b.FromMM(a[0]),b.FromMM(a[1])));line.SetEnd(b.VECTOR2I(b.FromMM(c[0]),b.FromMM(c[1])));line.SetWidth(b.FromMM(.05));board.Add(line)
b.SaveBoard(str(P/'output/model_catalog.kicad_pcb'),board)
path=P/'output/model_catalog.kicad_pcb'
path.write_text(path.read_text(encoding='utf-8').replace('${KIPRJMOD}/3dmodels/','${KIPRJMOD}/../3dmodels/'),encoding='utf-8')
print('Saved model catalog:',len(data),'packages')
