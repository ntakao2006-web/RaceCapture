from pathlib import Path
import json,copy
P=Path(__file__).resolve().parents[1]
path=P/'logger_v2.kicad_pro'
a=json.loads(path.read_text())
r=a['board']['design_settings']['rules']
r.update(min_clearance=.15,min_track_width=.20,min_via_diameter=.6,min_through_hole_diameter=.3,min_via_annular_width=.15,min_copper_edge_clearance=.3,min_hole_clearance=.25,min_hole_to_hole=.25,min_silk_clearance=.15)
d=a['net_settings']['classes'][0]
d.update(clearance=.2,track_width=.25,via_diameter=.6,via_drill=.3)
classes=[d]
for name,width,clearance in [('Power',.5,.2),('RF_50R',1.5,.3)]:
    v=copy.deepcopy(d);v.update(name=name,track_width=width,clearance=clearance,priority=len(classes));classes.append(v)
a['net_settings']['classes']=classes
a['net_settings']['netclass_patterns']=[{'netclass':'Power','pattern':'+3V3'},{'netclass':'Power','pattern':'+5V'},{'netclass':'RF_50R','pattern':'/GNSS_RF'}]
a['board']['design_settings']['track_widths']=[.2,.25,.3,.5,1.0,1.5]
a['board']['design_settings']['via_dimensions']=[{'diameter':.6,'drill':.3}]
path.write_text(json.dumps(a,indent=2)+'\n')
(P/'logger_v2.kicad_dru').write_text('''(version 1)
(rule "RF nominal gap"
 (condition "A.NetName == '/GNSS_RF' || B.NetName == '/GNSS_RF'")
 (constraint clearance (min 0.3mm)))
(rule "RF miniature ESD package"
 (condition "A.MemberOfFootprint('D11') && B.MemberOfFootprint('D11')")
 (constraint clearance (min 0.15mm)))
''')
print('Updated fabrication and routing rules; RF zone gap 0.3 mm, ordinary clearance 0.2 mm.')
