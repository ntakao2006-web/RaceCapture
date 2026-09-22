from pathlib import Path
import sexpdata as sx, copy, shutil, uuid, hashlib, json, csv
P=Path(__file__).resolve().parents[1]
K=Path('C:/Users/lintaroh/AppData/Local/Programs/KiCad/9.0/share/kicad')
S=sx.Symbol
def n(k,*v):return [S(k),*v]
def ch(a,k):return [x for x in a if isinstance(x,list) and x and str(x[0])==k]
def one(a,k):return ch(a,k)[0]
def props(a):return {x[1]:x[2] for x in ch(a,'property')}
def field(a,k,v):
 f=[x for x in ch(a,'property') if x[1]==k]
 if f:f[0][2]=v
 else:a.append(n('property',k,v,n('at',*one(a,'at')[1:3],0),n('effects',n('font',n('size',1.27,1.27)),n('hide',S('yes')))))
def spans(t):
 d=0;q=False;e=False;st=0
 for i,c in enumerate(t):
  if q:
   if e:e=False
   elif c=='\\':e=True
   elif c=='"':q=False
  elif c=='"':q=True
  elif c=='(':
   if d==1:st=i
   d+=1
  elif c==')':
   d-=1
   if d==1:yield st,i+1
def insert(t,x):
 i=t.rfind(')');return t[:i]+sx.dumps(x,pretty_print=True)+'\n'+t[i:]
def digest(f):return hashlib.sha256(f.read_bytes()).hexdigest()
B=P/'logger_v2-backups/before_AP63301_20260922';B.mkdir(exist_ok=True)
files=['logger_v2.kicad_sch','logger_v2_lte_sd.kicad_sch','logger_v2_expansion.kicad_sym','logger_v2.kicad_pcb','logger_v2.kicad_pro','実装方針.md']
for f in files:
 if (B/f).exists():assert digest(P/f)==digest(B/f),'Already modified: '+f
 else:shutil.copy2(P/f,B/f)
name='AP63301WU-7';fpname='Diodes_TSOT26';ds='https://www.diodes.com/assets/Datasheets/AP63300-AP63301.pdf'
url='https://www.digikey.jp/ja/products/detail/diodes-incorporated/AP63301WU-7/10491607'
z=sx.loads(f'''(symbol "{name}" (pin_names (offset 0.635)) (in_bom yes) (on_board yes)
 (property "Reference" "U" (at 0 10.16 0) (effects (font (size 1.27 1.27))))
 (property "Value" "{name}" (at 0 7.62 0) (effects (font (size 1.27 1.27))))
 (property "Footprint" "logger_v2_expansion:{fpname}" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
 (property "Datasheet" "{ds}" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
 (property "Description" "3A synchronous buck, 3.8-32V input, forced PWM 500kHz, TSOT26" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
 (symbol "{name}_0_1" (rectangle (start -7.62 5.08) (end 7.62 -5.08) (stroke (width 0.254) (type default)) (fill (type background)))))''')
unit=n('symbol',name+'_1_1')
for num,pn,ty,x,y,rot in [('1','FB','input',10.16,-2.54,180),('2','EN','input',-10.16,-2.54,0),('3','VIN','power_in',-10.16,2.54,0),('4','GND','power_in',0,-7.62,90),('5','SW','output',10.16,0,180),('6','BST','passive',10.16,2.54,180)]:
 unit.append(n('pin',S(ty),S('line'),n('at',x,y,rot),n('length',2.54),n('name',pn,n('effects',n('font',n('size',1.27,1.27)))),n('number',num,n('effects',n('font',n('size',1.27,1.27))))))
z.append(unit)
lp=P/'logger_v2_expansion.kicad_sym';lp.write_text(insert(lp.read_text(encoding='utf8'),z),encoding='utf8')
fp=sx.loads((K/'footprints/Package_TO_SOT_SMD.pretty/TSOT-23-6.kicad_mod').read_text(encoding='utf8'));fp[1]=fpname
one(fp,'descr')[1]='Diodes TSOT26; DS42002 p21 recommended land pattern; no exposed pad'
for prop in ch(fp,'property'):
 if prop[1]=='Value':prop[2]=fpname
for pad in ch(fp,'pad'):
 a=one(pad,'at');a[1]=1.0995 if a[1]>0 else -1.0995
 one(pad,'size')[1:]=[1.0,.7]
one(fp,'model')[1]='${KIPRJMOD}/3dmodels/TSOT-23-6.step'
(P/f'logger_v2_expansion.pretty/{fpname}.kicad_mod').write_text(sx.dumps(fp,pretty_print=True)+'\n',encoding='utf8')
shutil.copy2(K/'3dmodels/Package_TO_SOT_SMD.3dshapes/TSOT-23-6.step',P/'3dmodels/TSOT-23-6.step')
f=P/'logger_v2_lte_sd.kicad_sch';t=f.read_text(encoding='utf8');old=sx.loads(t);edits=[];changed=[]
cap=next(x for x in ch(old,'symbol') if props(x).get('Reference')=='C21')
for a,b in spans(t):
 e=sx.loads(t[a:b]);original=copy.deepcopy(e)
 if str(e[0])=='lib_symbols':
  cache=copy.deepcopy(z);cache[1]='logger_v2_expansion:'+name
  edits.append((a,b,insert(t[a:b],cache)));continue
 if str(e[0])!='symbol':continue
 d=props(e);ref=d['Reference']
 if d.get('MPN')=='TPS62130RGTR':
  one(e,'lib_id')[1]='logger_v2_expansion:'+name
  for k,v in {'Value':name,'MPN':name,'Footprint':'logger_v2_expansion:'+fpname,'Datasheet':ds,'Description':'3A synchronous buck, forced PWM 500kHz, TSOT26','Supplier':'DigiKey','SupplierCode':'31-AP63301WU-7CT-ND','SupplierURL':url,'SelectionNote':'0.95mm pitch, no exposed pad; DigiKey stock confirmed 2026-09-22'}.items():field(e,k,v)
  e=[x for x in e if not (isinstance(x,list) and x and str(x[0])=='pin')]
  for i in range(1,7):e.append(n('pin',str(i),n('uuid',str(uuid.uuid4()))))
 elif ref=='C29':
  one(e,'lib_id')[1]=one(cap,'lib_id')[1]
  for k in ['Value','MPN','Footprint','Datasheet','Supplier','SupplierCode','SupplierURL']:field(e,k,props(cap)[k])
  field(e,'Role','AP63301 BST pin 6 to SW pin 5; bootstrap capacitor')
  field(e,'SelectionNote','100nF X7R; replaces former TPS62130 soft-start capacitor; do not connect to GND')
 elif ref=='C21':field(e,'Role','AP63301 VIN pin 3 to GND pin 4; local bypass')
 elif ref=='R22':field(e,'Role','FB lower: FB pin 1 to GND pin 4; paired with R21')
 for prop in ch(e,'property'):
  if prop[1]=='Role':prop[2]=prop[2].replace('TPS62130','AP63301')
 if e!=original:edits.append((a,b,sx.dumps(e,pretty_print=True)));changed.append(one(e,'uuid')[1])
for a,b,v in sorted(edits,reverse=True):t=t[:a]+v+t[b:]
f.write_text(t,encoding='utf8');new=sx.loads(t)
oldsy={one(x,'uuid')[1]:x for x in ch(old,'symbol')};newsy={one(x,'uuid')[1]:x for x in ch(new,'symbol')}
assert oldsy.keys()==newsy.keys()
for uid,x in oldsy.items():
 assert one(x,'at')==one(newsy[uid],'at')
 if uid not in changed:assert x==newsy[uid]
for k in ['wire','junction','label','global_label','hierarchical_label','no_connect','sheet','text']:assert ch(old,k)==ch(new,k),k
for fn in ['logger_v2.kicad_sch','logger_v2.kicad_pcb','logger_v2.kicad_pro']:assert digest(P/fn)==digest(B/fn)
rows=[]
for fn in ['logger_v2.kicad_sch','logger_v2_lte_sd.kicad_sch']:
 for e in ch(sx.loads((P/fn).read_text(encoding='utf8')),'symbol'):
  d=props(e)
  if d.get('Reference','').startswith('#'):continue
  rows.append({'Sheet':fn,**{k:d.get(k,'') for k in ['Reference','Value','MPN','Footprint','Supplier','SupplierCode','SupplierURL','Role']}})
with (P/'output/現在部品一覧_20260922.csv').open('w',encoding='utf-8-sig',newline='') as out:
 w=csv.DictWriter(out,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
report={'changed_uuids':changed,'all_positions_preserved':True,'all_wiring_preserved':True,'root_and_pcb_unchanged':True,'parts':len(rows),'pin_map':{one(x,'number')[1]:one(x,'name')[1] for x in ch(unit,'pin')},'model':'3dmodels/TSOT-23-6.step','model_kind':'KiCad nominal package model, not manufacturer exact model'}
(P/'output/buck_replacement_20260922.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False))
