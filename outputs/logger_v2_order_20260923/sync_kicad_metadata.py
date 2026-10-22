from pathlib import Path
import re,json,uuid,hashlib,datetime,sexpdata

out=Path(__file__).resolve().parent
root=out.parents[1]/'circuit/logger_v2'
bom=json.loads((out/'bom_data.json').read_text(encoding='utf8'))
rows={ref:r for r in bom['rows'] for ref in r['refs']}
makers=dict(zip(['samsung-electro-mechanics','murata-electronics','panasonic-industry','yageo','tdk-corporation','stmicroelectronics','liteon','molex','te-connectivity-linx','onsemi','bourns-inc','vishay-dale','stackpole-electronics-inc','diodes-incorporated','texas-instruments','microchip-technology','simcom-wireless-solutions-limited','toshiba-semiconductor-and-storage','abracon-llc','littelfuse-inc','mcc-micro-commercial-components'],['Samsung Electro-Mechanics','Murata Electronics','Panasonic Industry','Yageo','TDK','STMicroelectronics','Lite-On','Molex','TE Connectivity','onsemi','Bourns','Vishay Dale','Stackpole Electronics','Diodes Incorporated','Texas Instruments','Microchip Technology','SIMCom','Toshiba','Abracon','Littelfuse','MCC']))
docs={}
for refs,url in json.loads((out/'verification.json').read_text(encoding='utf8'))['manufacturerSources']:
 for ref in refs.split('/'):docs[ref]=url
docs.update({ref:'https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/8939/SpecSheet_CL21B106KPQNFN_20260623.pdf' for ref in rows if rows[ref]['mpn']=='CL21B106KPQNFNE'})
docs['L1']='https://www.murata.com/~/media/webrenewal/products/inductor/chip/tokoproducts/wirewoundmetalalloychiptype/m_dfe252012f.ashx'

class Node:
 def __init__(self,start): self.start=start;self.end=0;self.items=[]
def parse(text):
 stack=[];result=None
 for m in re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text):
  t=m.group()
  if t=='(':
   n=Node(m.start())
   if stack:stack[-1].items.append(n)
   stack.append(n)
  elif t==')':
   n=stack.pop();n.end=m.end()
   if not stack:result=n
  else:stack[-1].items.append((json.loads(t) if t.startswith('"') else t,m.start(),m.end()))
 assert not stack
 return result
def tag(n):return n.items[0][0]
def children(n,name):return [x for x in n.items if isinstance(x,Node) and tag(x)==name]
allowed={'MPN','Manufacturer','Supplier','SupplierCode','SupplierURL','Specification','SelectionNote','LCSC','JLCPCB_Class','Datasheet'}
def strip(tree):
 if not isinstance(tree,list):return tree
 return [strip(x) for x in tree if not (isinstance(x,list) and len(x)>2 and str(x[0])=='property' and x[1] in allowed)]
backup=out/('kicad_metadata_backup_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir()
library_hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*.kicad_mod')}
report={};plans=[]
for filename,kind in [('logger_v2.kicad_sch','symbol'),('logger_v2.kicad_pcb','footprint')]:
 path=root/filename;raw=path.read_bytes();text=raw.decode('utf8');tree=parse(text)
 if kind=='symbol':assert not children(tree,'sheet'),'Unexpected hierarchical sheet; inspect before editing'
 edits=[];seen=set();changes=[]
 for n in children(tree,kind):
  props={x.items[1][0]:x for x in children(n,'property')}
  ref=props.get('Reference');ref=ref.items[2][0] if ref else ''
  if ref not in rows:continue
  assert ref not in seen;seen.add(ref);r=rows[ref]
  old={k:v.items[2][0] for k,v in props.items()}
  fp=old.get('Footprint') if kind=='symbol' else n.items[1][0]
  assert fp in r['footprint'].split('; '),(ref,fp,r['footprint'])
  fields={'MPN':r['mpn'],'Manufacturer':makers[r['url'].split('/detail/')[1].split('/')[0]],'Supplier':r['supplier'],'SupplierCode':r['dk'],'SupplierURL':r['url'],'Specification':r['description']+'; '+r['package'],'SelectionNote':r['note'],'LCSC':'','JLCPCB_Class':''}
  fields['Datasheet']=docs.get(ref,old.get('Datasheet','') if old.get('MPN')==r['mpn'] else '')
  changes.append({'ref':ref,'before':{k:old.get(k) for k in fields},'after':fields})
  added=[]
  for k,v in fields.items():
   encoded=json.dumps(v,ensure_ascii=False)
   if k in props:
    atom=props[k].items[2];edits.append((atom[1],atom[2],encoded))
   else:
    layer=' (layer "F.Fab") (hide yes) (uuid "'+str(uuid.uuid4())+'")' if kind=='footprint' else ''
    hidden='' if kind=='footprint' else ' (hide yes)'
    added.append('\n\t\t(property '+json.dumps(k)+' '+encoded+' (at 0 0 0)'+layer+' (effects (font (size 1.27 1.27))'+hidden+'))')
  if added:edits.append((n.end-1,n.end-1,''.join(added)+'\n\t'))
 assert seen==set(rows),(filename,set(rows)-seen)
 updated=text
 for a,b,v in sorted(edits,reverse=True):updated=updated[:a]+v+updated[b:]
 before=sexpdata.loads(text);after=sexpdata.loads(updated)
 assert strip(before)==strip(after),'Non-metadata change detected'
 # Verify every intended field in the resulting document.
 for n in children(parse(updated),kind):
  props={x.items[1][0]:x.items[2][0] for x in children(n,'property')}
  ref=props.get('Reference')
  if ref in rows:
   expected=next(x['after'] for x in changes if x['ref']==ref)
   assert all(props.get(k)==v for k,v in expected.items()),ref
 plans.append((path,raw,updated.encode('utf8')))
 report[filename]={'updated_components':len(seen),'metadata_only_verified':True,'before_sha256':hashlib.sha256(raw).hexdigest(),'after_sha256':hashlib.sha256(updated.encode('utf8')).hexdigest(),'changes':changes}
for path,raw,updated in plans:
 (backup/path.name).write_bytes(raw)
 assert path.read_bytes()==raw,'File changed during operation'
 path.write_bytes(updated)
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in library_hashes.items())
report['footprint_libraries_unchanged']=len(library_hashes)
report['backup']=str(backup)
(out/'kicad_metadata_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'components_per_file':79,'metadata_only':True,'footprint_libraries_unchanged':len(library_hashes),'backup':str(backup)},ensure_ascii=False))
