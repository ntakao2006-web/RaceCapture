"""Add presentation entities only. Original STEP geometry entities remain byte-identical."""
from pathlib import Path
import re,json,datetime,hashlib
P=Path(__file__).resolve().parents[1];geom=json.loads((P/'output/model_color_geometry.json').read_text())
backup=P/'logger_v2-backups'/('before_model_colors_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));backup.mkdir()
colors={'resin':(.10,.11,.12),'metal':(.65,.67,.70),'gold':(.78,.61,.25),'pcb':(.07,.27,.15),'insulator':(.84,.81,.68)}
def material(name,solid,face):
 x,y,z=face['center'];b=face['box']
 if name.startswith('TC74'):return 'resin' if solid==0 else 'metal'
 if name.startswith('Akizuki'):return 'pcb' if solid==0 else ('resin' if solid in [1,2,7] else 'gold')
 if name.startswith('SIMCom'):return 'pcb' if solid==0 else ('metal' if solid==1 else 'gold')
 if name.startswith('COSMTEC'):return 'insulator' if solid==2 else 'gold'
 if name.startswith('Molex_43045'):return 'metal' if b[5]<-4.9551 or (y<-4.9 and abs(x)<4) else 'resin'
 if name.startswith('Molex_47219'):
  if z<-5.6 and abs(x)<5 and -.9<y<-.3:return 'gold'
  return 'metal' if y>-.28 or abs(x)>6.4 else 'resin'
 if name.startswith('TE_'):
  if z>.75 or abs(x)>5.2:return 'metal'
  return 'gold' if abs(x)<3.1 and z>.20 else 'resin'
 raise ValueError(name)
report=[]
for name,g in geom.items():
 f=P/'3dmodels'/name;raw=f.read_bytes();t=raw.decode('latin1');assert not re.search(r'COLOUR_RGB\s*\(',t)
 ent={int(i):v for i,v in re.findall(r'#(\d+)\s*=\s*(.*?);',t,re.S)}
 shells=[(i,[int(k) for k in re.findall(r'#(\d+)',v)]) for i,v in ent.items() if re.match(r'(?:CLOSED|OPEN)_SHELL\s*\(',v)]
 faceids=[i for _,ids in shells for i in ids];assert len(faceids)==len(g['allfaces'])
 context=next(i for i,v in ent.items() if 'GEOMETRIC_REPRESENTATION_CONTEXT' in v)
 nxt=max(ent)+1;lines=[]
 def add(body):
  global nxt
  i=nxt;nxt+=1;lines.append(f'#{i}={body};');return i
 styles={}
 for cname,rgb in colors.items():
  c=add("COLOUR_RGB('',"+','.join(str(x) for x in rgb)+')')
  fill=add(f"FILL_AREA_STYLE_COLOUR('',#{c})")
  fa=add(f"FILL_AREA_STYLE('',(#{fill}))")
  surf=add(f'SURFACE_STYLE_FILL_AREA(#{fa})')
  side=add(f"SURFACE_SIDE_STYLE('',(#{surf}))")
  use=add(f'SURFACE_STYLE_USAGE(.BOTH.,#{side})')
  styles[cname]=add(f'PRESENTATION_STYLE_ASSIGNMENT((#{use}))')
 solidindices=[]
 for index,solid in enumerate(g['solids']):solidindices.extend([index]*len(solid['faces']))
 assert len(solidindices)==len(faceids)
 items=[];counts={}
 for fid,face,solid in zip(faceids,g['allfaces'],solidindices):
  assert re.match(r'ADVANCED_FACE\s*\(',ent[fid])
  mat=material(name,solid,face);counts[mat]=counts.get(mat,0)+1
  items.append(add(f"STYLED_ITEM('',(#{styles[mat]}),#{fid})"))
 add("MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',("+','.join('#'+str(i) for i in items)+f'),#{context})')
 end=t.rfind('ENDSEC;');new=t[:end]+'\n'+'\n'.join(lines)+'\n'+t[end:]
 check={int(i):v for i,v in re.findall(r'#(\d+)\s*=\s*(.*?);',new,re.S)}
 assert all(check[i]==v for i,v in ent.items())
 (backup/name).write_bytes(raw);assert f.read_bytes()==raw;f.write_bytes(new.encode('latin1'))
 report.append({'file':name,'faces':len(faceids),'materials':counts,'original_entities_unchanged':True})
(P/'output/model_colors_20260922.json').write_text(json.dumps({'backup':str(backup),'models':report,'colors':'Material visualization approximation, not measured manufacturer colors'},indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
