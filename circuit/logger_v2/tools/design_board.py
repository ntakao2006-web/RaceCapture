"""Rebuild the reviewed PCB from the immutable pre-design board and fresh XML.

Run with KiCad's Python. Does not edit the schematic. Connector mechanics are
asserted against the original before every save. Review intermediate DRC before
using any generated board for fabrication.
"""
from pathlib import Path
import json, sys, math, xml.etree.ElementTree as ET
import wx
wx.DisableAsserts()
import pcbnew as p

P = Path(__file__).resolve().parents[1]
O = P / 'output/design_review_20260907'
BASE = P / 'logger_v2-backups/pcb_design_20260907/logger_v2.kicad_pcb'
XML = O / 'reviewed_netlist.xml'
mm = p.ToMM
def V(x, y): return p.VECTOR2I(p.FromMM(x), p.FromMM(y))
def xy(a): return (mm(a.GetPosition().x), mm(a.GetPosition().y))

PLACEMENT = {
    'U2': (123.5,84.1,0), 'U3': (158.0,57.0,-90),
    'U4': (126.5,58.5,180), 'U5': (128.5,69.5,0),
    'U1': (147.2,76.8,90),
    'D10': (117,58.5,90), 'D9': (117,71,90),
    'R14': (120.5,57.5,90), 'R13': (115.5,66.3,0),
    'Y1': (120.8,67.3,0), 'C2': (121.0,64.4,0), 'C3': (121.0,70.3,0),
    'R7': (112.0,82.0,180), 'C1': (111.0,85.6,180),
    'L1': (111.0,88.5,90), 'D11': (110.0,91.4,90),
    'R10': (132.0,91.0,90), 'R5': (113.5,78.0,0),
    'R12': (136.2,68.1,90), 'R15': (143.0,60.0,0),
    'R16': (143.0,62.5,0), 'R17': (159.5,69.6,0),
    'C4': (140.0,73.9,180), 'C5': (132.0,57.865,0),
    'C6': (122.0,54.8,90), 'C7': (126.5,63.0,0),
    'C8': (136.4,71.8,0), 'C9': (135.8,64.6,0),
    'C10': (133.0,77.0,90), 'C11': (136.0,77.0,90),
    'C12': (133.0,80.0,0), 'C13': (132.5,94.5,0),
    'C14': (136.5,94.5,0),
    'R18': (144.5,70.5,90), 'R19': (147.0,70.5,90),
    'R20': (149.5,70.5,90),
}
for i,r in enumerate(['R1','R2','R3','R4','R6','R8','R9','R11']):
    PLACEMENT[r]=(137.0+2.8*i,87.7,-90)
    PLACEMENT[f'D{i+1}']=(137.0+2.8*i,91.0,90)

def field(f,name,text):
    q=f.GetFieldByName(name)
    if q is None:
        q=p.PCB_FIELD(f,f.GetNextFieldId(),name); f.Add(q)
    q.SetText(text); q.SetVisible(False)

def load_reviewed():
    b=p.LoadBoard(str(BASE)); old={f.GetReference():f for f in b.GetFootprints()}
    for t in list(b.GetTracks()): b.Remove(t)
    for z in list(b.Zones()): b.Remove(z)
    tree=ET.parse(XML)
    pins={}
    for n in tree.findall('nets/net'):
        name=n.get('name'); net=b.FindNet(name)
        if not net: net=p.NETINFO_ITEM(b,name); b.Add(net)
        for a in n.findall('node'): pins[(a.get('ref'),a.get('pin'))]=net
    for c in tree.findall('components/comp'):
        ref=c.get('ref'); fid=c.findtext('footprint'); lib,name=fid.split(':',1)
        libpath=P / (lib+'.pretty')
        if not libpath.exists():
            libpath=Path(r'C:/Users/lintaroh/AppData/Local/Programs/KiCad/9.0/share/kicad/footprints')/(lib+'.pretty')
        f=p.FootprintLoad(str(libpath),name)
        assert f is not None, (ref,fid)
        f.SetFPID(p.LIB_ID(lib,name)); f.SetReference(ref); f.SetValue(c.findtext('value'))
        if ref in old:
            prev=old[ref]; pos=xy(prev); angle=prev.GetOrientationDegrees()
            f.SetPath(prev.GetPath()); b.Remove(prev)
        else:
            pos=(150,85); angle=0
            path=p.KIID_PATH(); path.push_back(p.KIID(c.findtext('tstamps').split()[0])); f.SetPath(path)
        x,y,angle=PLACEMENT.get(ref,(*pos,angle))
        f.SetPosition(V(x,y)); f.SetOrientationDegrees(angle)
        f.SetDNP(c.find("property[@name='dnp']") is not None)
        for a in c.findall('fields/field'): field(f,a.get('name'),a.text or '')
        if ref.startswith('J') or ref=='U3': f.SetExcludedFromPosFiles(True)
        for a in f.Pads():
            net=pins.get((ref,a.GetNumber()))
            if net: a.SetNet(net)
            if ref in ['U5','L1','D11']: a.SetLocalClearance(p.FromMM(.20))
        b.Add(f)
    b.BuildListOfNets(); b.SynchronizeNetsAndNetClasses(False)
    return b

def styling(b):
    for f in b.GetFootprints():
        f.Value().SetVisible(False)
        r=f.Reference(); r.SetTextSize(V(.85,.85)); r.SetTextThickness(p.FromMM(.13))
        r.SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T)); r.SetKeepUpright(True)
        if f.GetReference().startswith('MH'): r.SetVisible(False); f.SetExcludedFromBOM(True); f.SetExcludedFromPosFiles(True)
        elif f.GetReference().startswith('D') and f.GetReference()[1:].isdigit() and int(f.GetReference()[1:])<=8:
            r.SetPosition(V(xy(f)[0],93.1))
        elif f.GetReference().startswith('R') and f.GetReference() in ['R1','R2','R3','R4','R6','R8','R9','R11']:
            r.SetPosition(V(xy(f)[0],85.65))
        elif f.GetReference().startswith('J'):
            r.SetVisible(False)
    for text,x,y,size in [('ECOLOGGER V2',146.5,83.3,1.2),('UNO Q SENSOR SHIELD',148,95.0,.8),('CAN1 / RX',108.5,53.5,.9),('CAN2',107.5,66,.9),('GNSS',105.0,96,.9),('IMU',154.2,54,.9)]:
        t=p.PCB_TEXT(b);t.SetText(text);t.SetPosition(V(x,y));t.SetTextSize(V(size,size));t.SetTextThickness(p.FromMM(.14));t.SetLayer(p.F_SilkS);b.Add(t)

def zones(b):
    for layer in [p.F_Cu,p.B_Cu]:
        z=p.ZONE(b);z.SetLayer(layer);z.SetNet(b.FindNet('GND'));z.SetLocalClearance(p.FromMM(.3));z.SetMinThickness(p.FromMM(.2));z.SetThermalReliefGap(p.FromMM(.3));z.SetThermalReliefSpokeWidth(p.FromMM(.3));z.SetPadConnection(p.ZONE_CONNECTION_THT_THERMAL)
        poly=z.Outline();poly.NewOutline()
        for x,y in [(99,45),(170,45),(170,101),(99,101)]:poly.Append(p.FromMM(x),p.FromMM(y))
        b.Add(z)
    # Keep RF's bottom reference plane free of signal tracks and signal vias.
    z=p.ZONE(b);z.SetLayer(p.B_Cu);z.SetIsRuleArea(True);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True);z.SetDoNotAllowCopperPour(False);z.SetDoNotAllowPads(False)
    poly=z.Outline();poly.NewOutline()
    for x,y in [(104,88.9),(118.5,88.9),(118.5,91.1),(104,91.1)]:poly.Append(p.FromMM(x),p.FromMM(y))
    b.Add(z)

def save_checked(b,name='logger_v2.kicad_pcb'):
    baseline=json.loads((O/'baseline_board.json').read_text())
    initial={a['ref']:a for a in baseline['footprints']}
    current={f.GetReference():f for f in b.GetFootprints()}
    for ref,a in initial.items():
        if ref.startswith('J') or ref.startswith('MH'):
            f=current[ref]; assert xy(f)==tuple(a['pos']) and f.GetOrientationDegrees()==a['angle'], ref
    assert all(f.GetLayer()==p.F_Cu for f in b.GetFootprints())
    b.BuildConnectivity();p.SaveBoard(str(P/name),b)
    (O/'placement.json').write_text(json.dumps({f.GetReference():{'position':xy(f),'angle':f.GetOrientationDegrees(),'value':f.GetValue(),'footprint':f.GetFPIDAsString(),'pads':[{ 'pin':a.GetNumber(),'net':a.GetNetname(),'position':xy(a)} for a in f.Pads()]} for f in b.GetFootprints()},indent=2),encoding='utf8')
    print('Saved', P/name, 'footprints',len(b.GetFootprints()),'tracks',len(b.GetTracks()))

if __name__=='__main__':
    b=load_reviewed();styling(b);zones(b);save_checked(b)
