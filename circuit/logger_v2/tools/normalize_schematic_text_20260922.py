from pathlib import Path
from decimal import Decimal
import sexpdata as sx, re, copy, hashlib, json, datetime
P=Path(__file__).resolve().parents[1]
def ch(a,k):return [x for x in a if isinstance(x,list) and x and str(x[0])==k]
def one(a,k):return ch(a,k)[0]
def props(a):return {x[1]:x[2] for x in ch(a,'property')}
def spans(t):
 depth=0;quoted=False;escape=False;start=0
 for i,c in enumerate(t):
  if quoted:
   if escape:escape=False
   elif c=='\\':escape=True
   elif c=='"':quoted=False
  elif c=='"':quoted=True
  elif c=='(':
   if depth==1:start=i
   depth+=1
  elif c==')':
   depth-=1
   if depth==1:yield start,i+1
def value(ref,v):
 if ref.startswith(('C','L')):
  m=re.fullmatch(r'([\d.]+)([pnumuµμ]?)([FH])',v)
  if m:
   number=Decimal(m[1]);prefix=m[2].replace('µ','u').replace('μ','u')
   if prefix=='n':number/=1000;prefix='u'
   return format(number.normalize(),'f')+prefix,None
 if ref.startswith('R'):
  m=re.fullmatch(r'([\d.]+)(?:R|Ω|ohm)(?:\s+([\d.]+W))?',v)
  if m:return m[1],m[2]
 return v,None
main=sx.loads((P/'logger_v2.kicad_sch').read_text(encoding='utf8'))
r31=next(z for z in ch(main,'symbol') if props(z).get('Reference')=='R31')
refprop=next(x for x in ch(r31,'property') if x[1]=='Reference');size=one(one(one(refprop,'effects'),'font'),'size')[1:]
assert size==[1.27,1.27],size
backup=P/'logger_v2-backups'/('before_text_normalization_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));backup.mkdir()
fontpat=r'(\(font\s*\(size\s+)([-\d.]+)(\s+)([-\d.]+)(\s*\))'
plans=[];changes=[];fontchanges=0
def clean(a):
 a=copy.deepcopy(a)
 def walk(x):
  if not isinstance(x,list) or not x:return
  if str(x[0])=='font':one(x,'size')[1:]=[1.27,1.27]
  for y in x:walk(y)
 walk(a)
 for z in ch(a,'symbol'):
  d=props(z);nv,rating=value(d['Reference'],d['Value'])
  for pp in ch(z,'property'):
   if pp[1]=='Value':pp[2]=nv
  # Rating moved from Value to metadata is the only permitted non-font addition.
  z[:]=[x for x in z if not (isinstance(x,list) and x and str(x[0])=='property' and x[1]=='PowerRating' and x[2]=='1W')]
 return a
for fn in ['logger_v2.kicad_sch','logger_v2_lte_sd.kicad_sch']:
 f=P/fn;raw=f.read_bytes();t=raw.decode('utf8');old=sx.loads(t);edits=[]
 for a,b in spans(t):
  z=sx.loads(t[a:b])
  if str(z[0])!='symbol':continue
  d=props(z);nv,rating=value(d['Reference'],d['Value'])
  if nv==d['Value']:continue
  block=re.sub(r'(\(property\s+"Value"\s+)"[^"]*"',lambda m:m[1]+'"'+nv+'"',t[a:b])
  if rating:
   assert not d.get('PowerRating') or d['PowerRating']==rating
   if not d.get('PowerRating'):
    x,y=one(z,'at')[1:3];at=block.rfind(')')
    block=block[:at]+f'\n(property "PowerRating" "{rating}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'+block[at:]
  edits.append((a,b,block));changes.append({'file':fn,'ref':d['Reference'],'old':d['Value'],'new':nv,'power_rating':rating})
 for a,b,block in reversed(edits):t=t[:a]+block+t[b:]
 def fontsub(m):
  global fontchanges
  if [float(m[2]),float(m[4])]!=size:fontchanges+=1
  return m[1]+'1.27'+m[3]+'1.27'+m[5]
 t=re.sub(fontpat,fontsub,t)
 assert clean(old)==clean(sx.loads(t)), 'Unexpected non-format change'
 (backup/fn).write_bytes(raw);plans.append((f,raw,t.encode('utf8')))
pcb=P/'logger_v2.kicad_pcb';pcbhash=hashlib.sha256(pcb.read_bytes()).hexdigest()
for f,raw,new in plans:assert f.read_bytes()==raw,'Concurrent save detected'
for f,raw,new in plans:f.write_bytes(new)
assert hashlib.sha256(pcb.read_bytes()).hexdigest()==pcbhash
report={'text_size_mm':size,'font_changes':fontchanges,'values':changes,'only_format_changes_verified':True,'pcb_unchanged':True,'backup':str(backup)}
(P/'output/text_normalization_20260922.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2))
