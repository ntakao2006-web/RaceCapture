"""Assign the policy's explicit references; no automatic spatial annotation."""
from pathlib import Path
import sexpdata as sx, re, copy, json, hashlib, datetime
P=Path(__file__).resolve().parents[1]
def ch(a,k):return [x for x in a if isinstance(x,list) and x and str(x[0])==k]
def one(a,k):return ch(a,k)[0]
def props(a):return {x[1]:x[2] for x in ch(a,'property')}
def spans(t):
 d=0;q=False;esc=False;start=0
 for i,c in enumerate(t):
  if q:
   if esc:esc=False
   elif c=='\\':esc=True
   elif c=='"':q=False
  elif c=='"':q=True
  elif c=='(':
   if d==1:start=i
   d+=1
  elif c==')':
   d-=1
   if d==1:yield start,i+1
mapping={'SIM7070G':'U6','TXU0204PWR':'U7','AP63301WU-7':'U8','2N7002':'Q1','2452796-1':'J8','47219-2001':'J9','LTE service 1x06':'J10','U.FL-R-SMT-1(10)':'J11'}
def desired(d):
 if d['Value']=='USBLC6-4SC6':
  assert d.get('Role','').startswith(('SIM ','microSD '))
  return 'U9' if d['Role'].startswith('SIM ') else 'U10'
 return mapping.get(d['Value'],d['Reference'])
def normalize(a):
 a=copy.deepcopy(a)
 def walk(x):
  if not isinstance(x,list):return
  if x and str(x[0])=='property' and x[1]=='Reference':x[2]='REFERENCE'
  elif x and str(x[0])=='reference':x[1]='REFERENCE'
  for y in x:walk(y)
 walk(a);return a
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S');backup=P/'logger_v2-backups'/('before_policy_annotation_'+stamp);backup.mkdir()
plans=[];report=[]
pcbhash=hashlib.sha256((P/'logger_v2.kicad_pcb').read_bytes()).hexdigest()
for filename in ['logger_v2.kicad_sch','logger_v2_lte_sd.kicad_sch']:
 f=P/filename;raw=f.read_bytes();t=raw.decode('utf8');old=sx.loads(t);edits=[]
 for a,b in spans(t):
  e=sx.loads(t[a:b])
  if str(e[0])!='symbol':continue
  d=props(e)
  if d['Reference'].startswith('#'):continue
  ref=desired(d);block=t[a:b]
  block=re.sub(r'(\(property\s+"Reference"\s+)"[^"]*"',lambda m:m[1]+'"'+ref+'"',block)
  block=re.sub(r'(\(reference\s+)"[^"]*"',lambda m:m[1]+'"'+ref+'"',block)
  if block!=t[a:b]:
   edits.append((a,b,block));report.append({'file':filename,'value':d['Value'],'role':d.get('Role',''),'old':d['Reference'],'new':ref})
 for a,b,block in reversed(edits):t=t[:a]+block+t[b:]
 new=sx.loads(t);assert normalize(old)==normalize(new),'Change outside annotation'
 refs=[]
 for e in ch(new,'symbol'):
  d=props(e)
  if d['Reference'].startswith('#'):continue
  assert d['Reference']==desired(d)
  assert '?' not in d['Reference'];refs.append(d['Reference'])
 assert len(refs)==len(set(refs)), 'Duplicate references'
 (backup/filename).write_bytes(raw)
 plans.append((f,raw,t.encode('utf8')))
for f,raw,new in plans:assert f.read_bytes()==raw,'Concurrent edit: '+f.name
for f,raw,new in plans:f.write_bytes(new)
assert hashlib.sha256((P/'logger_v2.kicad_pcb').read_bytes()).hexdigest()==pcbhash
result={'changes':report,'reference_only_verified':True,'no_duplicates_or_unannotated_parts':True,'pcb_unchanged':True,'backup':str(backup)}
(P/'output/annotation_policy_20260922.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))
