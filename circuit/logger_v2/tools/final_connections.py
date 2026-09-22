from design_board import *
b=p.LoadBoard(str(P/'logger_v2.kicad_pcb'))
def seg(net,a,c,w=.25,layer=p.F_Cu):
    t=p.PCB_TRACK(b);t.SetStart(V(*a));t.SetEnd(V(*c));t.SetWidth(p.FromMM(w));t.SetLayer(layer);t.SetNet(b.FindNet(net));t.SetLocked(True);b.Add(t)
def via(net,q,width=.6,drill=.3):
    v=p.PCB_VIA(b);v.SetPosition(V(*q));v.SetWidth(p.FromMM(width));v.SetDrill(p.FromMM(drill));v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetViaType(p.VIATYPE_THROUGH);v.SetNet(b.FindNet(net));v.SetLocked(True);b.Add(v)
original=list(b.GetTracks())
for t in original:
    if isinstance(t,p.PCB_VIA) and t.GetNetname()=='+3V3' and math.dist(xy(t),(115.6759,79.2491))<.001:b.Remove(t)
    if not isinstance(t,p.PCB_VIA) and t.GetNetname()=='/SPI2_MISO' and t.GetLayer()==p.F_Cu:
        if min(mm(t.GetStart().y),mm(t.GetEnd().y))>=71.7986:b.Remove(t)
for a,c,w in [((129.7806,71.7987),(130.9169,72.935),.25),((130.9169,72.935),(131.86,72.935),.2),((131.86,72.935),(132,73.075),.2)]:seg('/SPI2_MISO',a,c,w)
for a in json.loads((O/'route_can1/route_can1_added.json').read_text()):
    if a['type']=='via':via(a['net'],a['position'],a['width'],a['drill'])
    else:seg(a['net'],a['start'],a['end'],a['width'],p.F_Cu if a['layer']=='F.Cu' else p.B_Cu)
via('GND',(133.6,58.35))
seg('GND',(132.775,57.865),(133.115,57.865))
seg('GND',(133.115,57.865),(133.6,58.35))
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());save_checked(b)
