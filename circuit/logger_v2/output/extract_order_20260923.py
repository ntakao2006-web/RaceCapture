from pathlib import Path
import re,json,collections,hashlib
P=Path(__file__).resolve().parents[1]
def parse(path):
 s=[[]]
 for t in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',path.read_text(encoding='utf8')):
  if t=='(': a=[];s[-1].append(a);s.append(a)
  elif t==')': s.pop()
  else:s[-1].append(json.loads(t) if t.startswith('"') else t)
 return s[0][0]
def childs(a,k):return [v for v in a if isinstance(v,list) and v and v[0]==k]
def val(a,k,default=''):
 x=childs(a,k);return x[0][1] if x else default
root=parse(P/'logger_v2.kicad_sch');pcb=parse(P/'logger_v2.kicad_pcb')
rows=[]
for s in childs(root,'symbol'):
 p={a[1]:a[2] for a in childs(s,'property')}
 if p.get('Reference','').startswith('#'):continue
 p['DNP']=val(s,'dnp');p['in_bom']=val(s,'in_bom');rows.append(p)
rows.sort(key=lambda r:(re.sub(r'\d','',r['Reference']),int(re.sub(r'\D','',r['Reference']))))
(P/'output/order_source_20260923.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
for p in rows: print(' | '.join(str(p.get(k,'')) for k in ['Reference','Value','MPN','Footprint','DNP','Specification']))
print('COUNT',len(rows))
f={val(s,'Reference'):s for s in []}
for s in childs(pcb,'footprint'):
 p={a[1]:a[2] for a in childs(s,'property')}
 matches=[r for r in rows if r['Reference']==p.get('Reference')]
 if matches:
  r=matches[0]
  if r['Value']!=p.get('Value') or r['Footprint']!=s[1]:print('PCB_MISMATCH',p.get('Reference'),p.get('Value'),s[1])
print('PCB footprint count',len(childs(pcb,'footprint')))
