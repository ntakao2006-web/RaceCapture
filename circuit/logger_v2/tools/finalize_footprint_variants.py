"""Save reviewed silk variants and keep all copper/connector geometry unchanged."""
from design_board import *
import collections
b=p.LoadBoard(str(P/'logger_v2.kicad_pcb'))
F={f.GetReference():f for f in b.GetFootprints()}
def geometry():
    return {f.GetReference():(xy(f),f.GetOrientationDegrees(),[(a.GetNumber(),xy(a),a.GetNetname()) for a in f.Pads()]) for f in b.GetFootprints()}
before=geometry()
for t in b.GetDrawings():
    if isinstance(t,p.PCB_TEXT) and t.GetText()=='UNO Q SENSOR SHIELD':
        t.SetPosition(V(xy(t)[0],84.45))
for i in range(1,9):
    f=F[f'D{i}']; f.Reference().SetPosition(V(xy(f)[0],93.1))
    # Keep references centered in their columns and shorten only the cathode ink.
    for g in f.GraphicalItems():
        if g.GetLayer()!=p.F_SilkS or g.GetClass()!='PCB_SHAPE': continue
        a,c=g.GetStart(),g.GetEnd()
        if min(abs(p.ToMM(a.y)-k) for k in (92.685,92.485))<.001: g.SetStart(V(p.ToMM(a.x),92.4))
        if min(abs(p.ToMM(c.y)-k) for k in (92.685,92.485))<.001: g.SetEnd(V(p.ToMM(c.x),92.4))
variants={
    'LED_0805_2012Metric_ShieldSilk':[f'D{i}' for i in range(1,9)],
    'AE_BNO055_BO_ShieldSilk':['U3'],
    'PinSocket_1x08_P2.54mm_Vertical_ShieldSilk':['J5'],
}
for name,refs in variants.items():
    f=F[refs[0]]
    clone=f.Duplicate()
    clone.SetOrientationDegrees(0)
    clone.SetPosition(V(0,0))
    clone.SetReference('REF**')
    clone.SetValue(name)
    clone.SetFPID(p.LIB_ID('logger_v2_custom',name))
    clone.SetPath(p.KIID_PATH())
    for a in clone.Pads(): a.SetNetCode(0)
    p.FootprintSave(str(P/'logger_v2_custom.pretty'),clone)
    assert (P/'logger_v2_custom.pretty'/f'{name}.kicad_mod').exists()
    for ref in refs:
        F[ref].SetFPID(p.LIB_ID('logger_v2_custom',name))
        field(F[ref],'Footprint',f'logger_v2_custom:{name}')
assert geometry()==before
tb=b.GetTitleBlock();tb.SetTitle('EcoLogger V2 - Arduino UNO Q Sensor Shield');tb.SetDate('2026-09-07');tb.SetRevision('A')
save_checked(b)
print('Three library variants saved. Copper and connector geometry unchanged.')
