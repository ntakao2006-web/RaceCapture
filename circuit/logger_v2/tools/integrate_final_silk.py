"""Integrate the reviewed 1 mm text candidate without changing copper geometry."""
from design_board import *
from finish_silkscreen_jlc import digest
candidate=O/'silkscreen_jlc_1mm/candidate.kicad_pcb'
original=p.LoadBoard(str(P/'logger_v2.kicad_pcb'));b=p.LoadBoard(str(candidate))
assert digest(original)==digest(b),'Candidate changed non-text data'
F={f.GetReference():f for f in b.GetFootprints()}
F['U5'].Reference().SetPosition(V(129.2,63.4))
for ref,x in [('R18',143.95),('R19',147),('R20',150.05)]:F[ref].Reference().SetPosition(V(x,70.5))
assert digest(original)==digest(b)
save_checked(b)
pro=P/'logger_v2.kicad_pro';data=json.loads(pro.read_text(encoding='utf-8-sig'))
data['board']['design_settings']['rules'].update(min_text_height=1.0,min_text_thickness=.15)
pro.write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')
(O/'final_silk_validation.json').write_text(json.dumps({'non_text_geometry_unchanged':True,'minimum_visible_text_height_mm':1.0,'minimum_visible_text_stroke_mm':.15,'non_text_sha256':digest(b)},indent=2))
