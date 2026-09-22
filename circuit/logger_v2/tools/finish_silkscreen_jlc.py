"""Logger v2: text-only 1.0 mm / 0.15 mm JLC legend finish.

Input is read-only; output must be different. No geometry, placement, copper,
footprint ID or graphical silk is changed. Rear references are mirrored for
normal readability from the back. Project limits are verified externally.
"""
from pathlib import Path
import argparse, hashlib, json
import pcbnew as p
from finish_silkscreen import parse_sexpr, serialize, V, xy

LED_REFS=[f'D{i}' for i in range(1,9)]
BACK_REFS=set(LED_REFS+['C13','C14','L1','R18','R19','R20'])
REF_OFFSETS={'C6':(0,-2.3),'C1':(2.5,0)}

def digest(board):
    def keep(a):
        if not isinstance(a,list): return a
        if a and a[0]=='property' and len(a)>1 and a[1]=='"Reference"': return None
        layers=[x[1] for x in a if isinstance(x,list) and x and x[0]=='layer']
        if a and a[0] in ['gr_text','fp_text'] and layers and layers[0] in ['"F.SilkS"','"B.SilkS"','"F.Silkscreen"','"B.Silkscreen"']: return None
        return [k for x in a if (k:=keep(x)) is not None]
    return hashlib.sha256(json.dumps(keep(parse_sexpr(serialize(board))),separators=(',',':')).encode()).hexdigest()

def state(t):
    return {'uuid':t.m_Uuid.AsString(),'text':t.GetText(),'position':xy(t),'layer':t.GetLayerName(),
            'size_mm':(p.ToMM(t.GetTextWidth()),p.ToMM(t.GetTextHeight())),
            'thickness_mm':p.ToMM(t.GetTextThickness()),'mirrored':t.IsMirrored(),
            'angle':t.GetTextAngleDegrees(),'visible':t.IsVisible()}

def finish(board):
    protected=digest(board); changes=[]; fs={f.GetReference():f for f in board.GetFootprints()}
    for ref,f in sorted(fs.items()):
        t=f.Reference()
        if not t.IsVisible(): continue
        before=state(t)
        t.SetTextSize(V(1,1));t.SetTextThickness(p.FromMM(.15))
        if ref in BACK_REFS:
            t.SetLayer(p.B_SilkS);t.SetMirrored(True);t.SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T))
            x,y=xy(f);t.SetPosition(V(x,y))
        elif ref in REF_OFFSETS:
            x,y=xy(f);dx,dy=REF_OFFSETS[ref];t.SetPosition(V(x+dx,y+dy))
        changes.append({'reference':ref,'before':before,'after':state(t)})
    front_positions={'ECOLOGGER V2':(146.8,82.8),'UNO Q SENSOR SHIELD':(146.8,84.2)}
    for t in board.GetDrawings():
        if t.GetClass()!='PCB_TEXT' or t.GetLayer() not in [p.F_SilkS,p.B_SilkS]: continue
        before=state(t);size=max(1.,p.ToMM(t.GetTextHeight()))
        t.SetTextSize(V(size,size));t.SetTextThickness(p.FromMM(.15))
        t.SetMirrored(t.GetLayer()==p.B_SilkS)
        if t.GetText() in front_positions:t.SetPosition(V(*front_positions[t.GetText()]))
        changes.append({'board_text':t.GetText(),'before':before,'after':state(t)})
    assert digest(board)==protected,'Non-text board data changed'
    return {'geometry_unchanged':True,'protected_geometry_sha256':protected,'changes':changes}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('input',type=Path);ap.add_argument('output',type=Path)
    args=ap.parse_args();assert args.input.resolve()!=args.output.resolve()
    input_sha=hashlib.sha256(args.input.read_bytes()).hexdigest()
    board=p.LoadBoard(str(args.input));report=finish(board)
    p.SaveBoard(str(args.output),board)
    assert digest(p.LoadBoard(str(args.output)))==report['protected_geometry_sha256']
    assert hashlib.sha256(args.input.read_bytes()).hexdigest()==input_sha
    report.update(input=str(args.input.resolve()),output=str(args.output.resolve()),input_sha256=input_sha)
    args.output.with_suffix('.text_finish.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'changes':len(report['changes']),'geometry_unchanged':True,'output':str(args.output)}))

if __name__=='__main__':main()
