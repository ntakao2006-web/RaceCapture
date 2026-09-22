from pathlib import Path
import sexpdata as sx,copy,csv,json,shutil
P=Path(__file__).resolve().parents[1];K=Path('C:/Users/lintaroh/AppData/Local/Programs/KiCad/9.0/share/kicad')
def ch(a,k):return [x for x in a if isinstance(x,list) and x and str(x[0])==k]
def one(a,k):return ch(a,k)[0]
def pr(a,k):return next(x for x in ch(a,'property') if x[1]==k)
def read(f):return sx.loads(f.read_text(encoding='utf8'))
def spans(t):
 d=0;q=False;e=False;start=0
 for i,c in enumerate(t):
  if q:
   if e:e=False
   elif c=='\\':e=True
   elif c=='"':q=False
  elif c=='"':q=True
  elif c=='(':
   if d==1:start=i
   d+=1
  elif c==')':
   d-=1
   if d==1:yield start,i+1
def insert(t,e):
 i=t.rfind(')');return t[:i]+sx.dumps(e,pretty_print=True)+'\n'+t[i:]
fp=read(K/'footprints/Resistor_SMD.pretty/R_0805_2012Metric.kicad_mod')
one(fp,'model')[1]='${KIPRJMOD}/3dmodels/R_0805_2012Metric.step'
(P/'logger_v2_expansion.pretty/R_0805_2012Metric.kicad_mod').write_text(sx.dumps(fp,pretty_print=True)+'\n',encoding='utf8')
shutil.copy2(K/'3dmodels/Resistor_SMD.3dshapes/R_0805_2012Metric.step',P/'3dmodels/R_0805_2012Metric.step')
lp=P/'logger_v2_expansion.kicad_sym';lt=lp.read_text(encoding='utf8');lib=sx.loads(lt)
z=copy.deepcopy(next(x for x in ch(lib,'symbol') if x[1]=='RC0603FR-07100KL'));old=z[1];z[1]='RG2012N-104-B-T5'
for u in ch(z,'symbol'):u[1]=u[1].replace(old,z[1])
pr(z,'Value')[2]='100k 0.1%';pr(z,'Footprint')[2]='logger_v2_expansion:R_0805_2012Metric';pr(z,'Datasheet')[2]='https://akizukidenshi.com/catalog/g/g111798/'
lp.write_text(insert(lt,z),encoding='utf8');z=copy.deepcopy(z);z[1]='logger_v2_expansion:'+z[1]
f=P/'logger_v2_lte_sd.kicad_sch';t=f.read_text(encoding='utf8');edits=[]
updates={'Value':'100k 0.1%','MPN':'RG2012N-104-B-T5','Footprint':'logger_v2_expansion:R_0805_2012Metric','Supplier':'秋月電子通商','SupplierCode':'111798','SupplierURL':'https://akizukidenshi.com/catalog/g/g111798/','Datasheet':'https://akizukidenshi.com/catalog/g/g111798/','SelectionNote':'秋月の0.1%精密抵抗、2012サイズ'}
for a,b in spans(t):
 e=sx.loads(t[a:b])
 if str(e[0])=='lib_symbols':edits.append((a,b,insert(t[a:b],z)))
 if str(e[0])=='symbol' and pr(e,'Reference')[2]=='R22':
  one(e,'lib_id')[1]=z[1]
  for k,v in updates.items():pr(e,k)[2]=v
  edits.append((a,b,sx.dumps(e,pretty_print=True)))
for a,b,v in sorted(edits,reverse=True):t=t[:a]+v+t[b:]
f.write_text(t,encoding='utf8')
file=P/'output/追加部品_20260921.csv';rows=list(csv.DictReader(file.open(encoding='utf-8-sig')))
for r in rows:
 if r['Reference']=='R22':
  for k in ['Value','MPN','Footprint','SupplierCode']:r[k]=updates[k]
  r['URL']=updates['SupplierURL'];r['Notes']=updates['SelectionNote']
with file.open('w',encoding='utf-8-sig',newline='') as out:
 w=csv.DictWriter(out,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
file=P/'output/parts_preparation_20260921.json';r=json.loads(file.read_text(encoding='utf8'));r['added']=rows;file.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
print('R22 switched to Akizuki 111798, 0.1%, 2012; 24 of 28 new parts from Akizuki.')
