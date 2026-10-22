from pathlib import Path
import re,json
def parse(path):
 s=[[]]
 for t in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',path.read_text(encoding='utf8')):
  if t=='(': a=[];s[-1].append(a);s.append(a)
  elif t==')': s.pop()
  else: s[-1].append(json.loads(t) if t.startswith('"') else t)
 return s[0][0]
def children(a,k):return [v for v in a if isinstance(v,list) and v and v[0]==k]
root=parse(Path('circuit/logger_v2/logger_v2.kicad_pcb'))
for fp in children(root,'footprint'):
 p={a[1]:a[2] for a in children(fp,'property')};ref=p.get('Reference','')
 if ref in ['J1','J2','J3','J4','U8','U4','U5','U7'] or ref in ['D'+str(n) for n in range(5,13)] or ref in ['R'+str(n) for n in range(23,31)]:
  print(ref,p.get('Value'), 'at',children(fp,'at'))
  for pad in children(fp,'pad'):print(' ',pad[1],children(pad,'net'))
