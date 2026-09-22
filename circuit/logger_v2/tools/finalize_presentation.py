"""Configure reproducible fabrication plots and rear connector legends."""
from design_board import *
b=p.LoadBoard(str(P/'logger_v2.kicad_pcb'))
opts=b.GetPlotOptions()
layers=p.LSET()
for layer in [p.F_Cu,p.B_Cu,p.F_Paste,p.F_SilkS,p.B_SilkS,p.F_Mask,p.B_Mask,p.Edge_Cuts]: layers.AddLayer(layer)
opts.SetLayerSelection(layers)
opts.SetUseGerberProtelExtensions(True); opts.SetUseAuxOrigin(True)
opts.SetOutputDirectory('manufacturing_20260907/gerbers/')
b.SetPlotOptions(opts)
legends=[
('ECOLOGGER V2 / REV A',134,72,1.2),
('J6: 1=+5V OUT  2=CANH  3=CANL  4=GND',134,75,.8),
('5V OUT: UNPROTECTED / NO POWER INPUT',134,77,.8),
('J7: 1=NC  2=CANH  3=CANL  4=GND',134,80,.8),
('CAN1 RX ONLY / 3.3V LOGIC',134,83,.9),
]
existing={t.GetText() for t in b.GetDrawings() if isinstance(t,p.PCB_TEXT)}
for text,x,y,size in legends:
    if text in existing: continue
    t=p.PCB_TEXT(b);t.SetText(text);t.SetLayer(p.B_SilkS);t.SetPosition(V(x,y));t.SetTextSize(V(size,size));t.SetTextThickness(p.FromMM(.13));t.SetMirrored(True);b.Add(t)
save_checked(b)
