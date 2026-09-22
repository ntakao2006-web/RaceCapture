from design_board import *
b=p.LoadBoard(str(P/'logger_v2.kicad_pcb'));F={f.GetReference():f for f in b.GetFootprints()}
for c in ET.parse(XML).findall('components/comp'):
    ref=c.get('ref');f=F[ref]
    assert f.GetFPIDAsString()==c.findtext('footprint'),ref
    f.SetValue(c.findtext('value'));f.SetDNP(c.find("property[@name='dnp']") is not None)
    for a in c.findall('fields/field'):field(f,a.get('name'),a.text or '')
b.GetDesignSettings().SetAuxOrigin(V(100,100))
save_checked(b)
