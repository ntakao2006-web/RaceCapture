"""Finish Logger v2 front silk without changing physical/electrical geometry.

Run with KiCad 9's Python. Input and output MUST differ. This is deliberately a
post-placement operation: it follows the actual LED/resistor X coordinates, so
the 2.8/3.0 mm pitch revision does not require changing reference coordinates.

Only reference text, existing front board text, and three narrowly identified
front-silk outline treatments are changed. A semantic digest verifies every
remaining board object before saving. No DRC rules or exclusions are edited.
"""
from pathlib import Path
import argparse, hashlib, json, re, tempfile
import wx
wx.DisableAsserts()
import pcbnew as p

def V(x, y): return p.VECTOR2I(p.FromMM(x), p.FromMM(y))
def xy(q): return (p.ToMM(q.GetPosition().x), p.ToMM(q.GetPosition().y))
def uid(q): return q.m_Uuid.AsString()

# Physical board serialization, stripped only of the explicitly allowed ink.
def parse_sexpr(text):
    stack = [[]]
    for tok in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text):
        if tok == '(':
            a=[]; stack[-1].append(a); stack.append(a)
        elif tok == ')': stack.pop()
        else: stack[-1].append(tok)
    assert len(stack)==1
    return stack[0][0]

def serialize(q):
    # Format(BOARD) aborts in this KiCad Windows binding. SaveBoard is the
    # supported serializer and writes only a private disposable file.
    with tempfile.TemporaryDirectory(prefix='logger_silk_digest_') as work:
        path=Path(work)/'digest.kicad_pcb'
        p.SaveBoard(str(path),q)
        return path.read_text(encoding='utf-8')

def protected_digest(board):
    tree=parse_sexpr(serialize(board))
    def keep(a):
        if not isinstance(a,list): return a
        if a and a[0]=='property' and len(a)>1 and a[1]=='"Reference"': return None
        layers=[x[1] for x in a if isinstance(x,list) and x and x[0]=='layer']
        if layers and layers[0] in ['"F.SilkS"','"F.Silkscreen"']:
            if a[0] in ['fp_line','fp_arc','fp_rect','fp_poly','fp_circle','fp_text','gr_text']:
                return None
        return [k for x in a if (k:=keep(x)) is not None]
    return hashlib.sha256(json.dumps(keep(tree),separators=(',',':')).encode()).hexdigest()

LED_REFS=[f'D{i}' for i in range(1,9)]
LED_R=['R1','R2','R3','R4','R6','R8','R9','R11']
# Offsets follow the parts, while annotation rows stay visibly aligned.
OFFSETS={
    'U1':(0,4.6), 'U2':(-8.9,-9.2), 'U3':(4.1,3.8),
    'U4':(0,-3.5), 'U5':(0,-6.0),
    'D9':(0,2.6), 'D10':(0,-2.5), 'D11':(2.5,1.0),
    'R5':(0,-1.5), 'R7':(0,-2.6), 'R10':(2.4,0),
    'R12':(2.4,0), 'R13':(0,-1.5), 'R14':(0,2.0),
    'R15':(0,-1.5), 'R16':(0,1.5), 'R17':(3.0,.0),
    'R18':(0,-2.0), 'R19':(0,-2.0), 'R20':(2.6,0),
    'C1':(2.2,0), 'C2':(0,-1.5), 'C3':(0,1.5),
    'C4':(0,-1.6), 'C5':(0,-1.5), 'C6':(0,-1.9),
    'C7':(-2.5,0), 'C8':(0,1.5), 'C9':(0,-1.5),
    'C10':(0,-2.0), 'C11':(0,-2.0), 'C12':(0,1.5),
    'C13':(0,-1.4), 'C14':(2.8,0), 'L1':(0,-1.45),
    'Y1':(-3.1,0),
    'J1':(0,4.7), 'J2':(0,2.4), 'J3':(-2.4,0),
    'J4':(-2.4,0), 'J5':(0,2.4), 'J6':(2.7,-8.4), 'J7':(2.7,-8.4),
}

def ref_state(t):
    return {'position':xy(t),'size':(p.ToMM(t.GetTextWidth()),p.ToMM(t.GetTextHeight())),
            'angle':t.GetTextAngleDegrees(),'visible':t.IsVisible(),'layer':t.GetLayerName()}

def finish(board):
    before=protected_digest(board); fs={f.GetReference():f for f in board.GetFootprints()}; changes=[]
    for ref,f in sorted(fs.items()):
        r=f.Reference(); old=ref_state(r)
        if ref.startswith('MH'):
            # Retain the existing invisible mounting-hole identifiers.
            continue
        assert f.GetLayer()==p.F_Cu, f'{ref}: expected top-mounted part'
        size=.82; angle=0; x,y=xy(f)
        if ref in LED_REFS: dy=2.15; dx=0; size=.80
        elif ref in LED_R: dy=-2.05; dx=0
        else:
            assert ref in OFFSETS, f'Unreviewed reference {ref}; add its annotation offset'
            dx,dy=OFFSETS[ref]
        r.SetLayer(p.F_SilkS); r.SetVisible(True); r.SetMirrored(False)
        r.SetTextSize(V(size,size)); r.SetTextThickness(p.FromMM(.12))
        r.SetTextAngle(p.EDA_ANGLE(angle,p.DEGREES_T)); r.SetKeepUpright(True)
        r.SetPosition(V(x+dx,y+dy))
        changes.append({'reference':ref,'before':old,'after':ref_state(r)})

    # Each LED retains the two cathode-side bars; its horizontal end-cap is
    # opened to give the aligned D1..D8 row actual clearance above C14.
    for ref in LED_REFS:
        f=fs[ref]; x,y=xy(f)
        for g in list(f.GraphicalItems()):
            if g.GetLayer()!=p.F_SilkS or g.GetClass()!='PCB_SHAPE' or g.GetShape()!=p.SHAPE_T_SEGMENT: continue
            a,c=g.GetStart(),g.GetEnd()
            if abs(p.ToMM(a.y)-y-1.685)<.002 and abs(p.ToMM(c.y)-y-1.685)<.002:
                old_uuid=uid(g)
                g.SetEnd(V(p.ToMM(a.x)+.2,p.ToMM(a.y)))
                changes.append({'reference':ref,'silk':'Shortened cathode end-cap below LED','uuid':old_uuid})

    # Clip the upper-right header ink to match the existing board chamfer.
    f=fs['J5']; x,y=xy(f); assert abs(f.GetOrientationDegrees()-90)<.01
    top_right=(x+18.27,y-1.33); corner=(x+19.11,y-.49)
    needs_diagonal=False
    for g in f.GraphicalItems():
        if g.GetLayer()!=p.F_SilkS or g.GetClass()!='PCB_SHAPE': continue
        a,c=g.GetStart(),g.GetEnd(); ax,ay,cx,cy=[p.ToMM(z) for z in (a.x,a.y,c.x,c.y)]
        if abs(ax-x-1.27)<.002 and abs(ay-y+1.33)<.002 and abs(cy-ay)<.002 and cx>x+18.3:
            g.SetEnd(V(*top_right)); needs_diagonal=True
        if abs(ax-x-19.11)<.002 and abs(cx-ax)<.002 and cy<y-.5:
            g.SetEnd(V(*corner)); needs_diagonal=True
    if needs_diagonal:
        g=p.PCB_SHAPE(f);g.SetShape(p.SHAPE_T_SEGMENT);g.SetLayer(p.F_SilkS)
        g.SetWidth(p.FromMM(.12));g.SetStart(V(*top_right));g.SetEnd(V(*corner));f.Add(g)
        changes.append({'reference':'J5','silk':'Chamfered only front outline; board edge and pads unchanged'})

    # The elevated IMU module is allowed to cover R17. Leave an intentional
    # break in its lower-right ink instead of printing across the R17 lands.
    f=fs['U3']; x,y=xy(f)
    for g in f.GraphicalItems():
        if g.GetLayer()!=p.F_SilkS or g.GetClass()!='PCB_SHAPE': continue
        a,c=g.GetStart(),g.GetEnd(); ax,ay,cx,cy=[p.ToMM(z) for z in (a.x,a.y,c.x,c.y)]
        if abs(ax-x-1.69)<.002 and abs(cx-ax)<.002 and cy>y+11.5:
            g.SetEnd(V(cx,y+10.9)); changes.append({'reference':'U3','silk':'Shortened right outline before R17'})
        if abs(ay-y-12.81)<.002 and abs(cy-ay)<.002 and ax>x-.1:
            g.SetStart(V(x-1.6,ay)); g.SetEnd(V(x-7.0,ay))
            changes.append({'reference':'U3','silk':'Opened lower outline around R17 and R20'})

    led_x=sum(xy(fs[r])[0] for r in LED_REFS)/8
    label_layout={
        'ECOLOGGER V2':(led_x,83.3,1.10),
        'UNO Q SENSOR SHIELD':(led_x,95.3,.82),
        'UNO Q SHIELD':(led_x,95.3,.82),
        'CAN1 / RX':(xy(fs['J7'])[0]-3.5,xy(fs['J7'])[1]-7.8,.9),
        'CAN2':(xy(fs['J6'])[0]-3.5,xy(fs['J6'])[1]-7.8,.9),
        'GNSS':(xy(fs['J1'])[0],xy(fs['J1'])[1]+6.25,.9),
        'IMU':(xy(fs['U3'])[0]+4.1,xy(fs['U3'])[1]-2.6,.9),
    }
    for t in board.GetDrawings():
        if t.GetClass()!='PCB_TEXT' or t.GetLayer()!=p.F_SilkS: continue
        if t.GetText() not in label_layout: continue
        x,y,size=label_layout[t.GetText()];t.SetPosition(V(x,y));t.SetTextSize(V(size,size))
        if t.GetText()=='UNO Q SENSOR SHIELD': t.SetText('UNO Q SHIELD')
        t.SetTextThickness(p.FromMM(.13));t.SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T));t.SetMirrored(False)
        changes.append({'board_text':t.GetText(),'position':(x,y),'size':size})
    after=protected_digest(board)
    assert before==after,'Protected board geometry changed; refusing to save'
    return {'protected_geometry_sha256':before,'geometry_unchanged':True,'changes':changes}

def export_reviewed_library(board, destination):
    """Export review candidates only; no source library or board ID is changed.

    J5 must use a distinct variant because J3 shares the original 1x08 header.
    Its schematic Footprint field and board FPID must be updated together by
    the integrator after copying the candidate into the project library.
    """
    destination.mkdir(parents=True,exist_ok=True)
    fs={f.GetReference():f for f in board.GetFootprints()}
    names={'D1':'LED_0805_2012Metric','U3':'AE_BNO055_BO',
           'J5':'PinSocket_1x08_P2.54mm_Vertical_ShieldCorner'}
    io=p.PCB_IO_KICAD_SEXPR(); exported=[]
    for ref,name in names.items():
        q=fs[ref].Duplicate();q.SetPosition(V(0,0));q.SetOrientation(p.EDA_ANGLE(0,p.DEGREES_T))
        q.SetReference('REF**');q.SetValue(name);q.SetFPID(p.LIB_ID('logger_v2_custom',name))
        io.FootprintSave(str(destination.resolve()),q)
        exported.append(str((destination/(name+'.kicad_mod')).resolve()))
    return exported

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input',type=Path);ap.add_argument('output',type=Path)
    ap.add_argument('--report',type=Path)
    ap.add_argument('--library-out',type=Path,help='Optional separate .pretty directory for three reviewed silk candidates')
    args=ap.parse_args()
    assert args.input.resolve()!=args.output.resolve(),'Input/output must differ; original is read-only'
    source_hash=hashlib.sha256(args.input.read_bytes()).hexdigest()
    board=p.LoadBoard(str(args.input));report=finish(board)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    p.SaveBoard(str(args.output),board)
    loaded=p.LoadBoard(str(args.output))
    assert protected_digest(loaded)==report['protected_geometry_sha256'],'Saved board changed protected geometry'
    assert hashlib.sha256(args.input.read_bytes()).hexdigest()==source_hash,'Input board changed during processing'
    report.update(input=str(args.input.resolve()),output=str(args.output.resolve()),input_sha256=source_hash)
    if args.library_out:
        project_library=Path(__file__).resolve().parents[1]/'logger_v2_custom.pretty'
        assert args.library_out.resolve()!=project_library.resolve(),'Export only to a review directory, not the live library'
        report['reviewed_library_candidates']=export_reviewed_library(loaded,args.library_out)
    report_path=args.report or args.output.with_suffix('.silk.json')
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(args.output),'changes':len(report['changes']),'geometry_unchanged':True}))

if __name__=='__main__': main()
