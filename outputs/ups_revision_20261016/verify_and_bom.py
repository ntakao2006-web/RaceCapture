from inspect_design import *
import xml.etree.ElementTree as ET,hashlib,csv,collections
project=root/'circuit/logger_v2_ups'
backup=out/'backup'
updates=json.loads((out/'selection.json').read_text(encoding='utf-8'))
ds='https://industrial.panasonic.com/cdbs/www-data/pdf/RDA0000/AOA0000C304.pdf'
# Replace the two product landing pages by the verified manufacturer PDF.
for ext in ['kicad_sch','kicad_pcb']:
    p=project/('logger_v2_ups.'+ext);s=p.read_bytes().decode('utf-8')
    for mpn in ['ERJ-6ENF3012V','ERJ-3EKF1002V']:
        s=s.replace('https://industrial.panasonic.com/ww/products/pt/general-purpose-chip-resistors/models/'+mpn,ds)
    p.write_bytes(s.encode('utf-8'))
for r in ['R1','R14']:updates[r]['Datasheet']=ds
(out/'selection.json').write_text(json.dumps(updates,indent=2),encoding='utf-8')
def lex(s):return re.findall(r'"(?:[^"\\]|\\.)*"|[^\s()]+|[()]',s)
report={}
for ext,kind in [('kicad_sch','symbol'),('kicad_pcb','footprint')]:
    before=(backup/('logger_v2_ups.'+ext)).read_text(encoding='utf-8')
    after=(project/('logger_v2_ups.'+ext)).read_text(encoding='utf-8')
    def scrub(s):
        for a,z,b in reversed(list(blocks(s,kind))):
            ref=props(b).get('Reference');fields=updates.get(ref,{})
            for pa,pz,pb in reversed(list(blocks(b,'property',2))):
                match=re.match(r'\(property "([^"]+)"',pb)
                if not match:continue
                key=match[1]
                if key in fields:b=b[:pa]+b[pz:]
            if ext=='kicad_pcb' and ref in ['J1','J2','J3','J4']:
                b=re.sub(r'^\(footprint "[^"]+"','(footprint "HEADER_ALIAS"',b)
            s=s[:a]+b+s[z:]
        return lex(s)
    assert scrub(before)==scrub(after),ext+' unintended geometry/content change'
    report[ext+'_only_authorized_properties_changed']=True
def nets(path):
    e=ET.parse(path)
    return sorted((n.attrib['name'],tuple(sorted((x.attrib['ref'],x.attrib['pin']) for x in n.findall('node')))) for n in e.findall('./nets/net'))
assert nets(out/'before.xml')==nets(out/'after.xml')
report['netlist_connectivity_unchanged']=True
def violations(path):
    j=json.loads(path.read_text(encoding='utf-8'));return sorted(json.dumps(v,sort_keys=True,ensure_ascii=False) for s in j['sheets'] for v in s['violations'])
assert violations(out/'erc_before.json')==violations(out/'erc_after.json')
report['erc_unchanged']={'errors':27,'warnings':1,'new':0}
sch=(project/'logger_v2_ups.kicad_sch').read_text(encoding='utf-8')
pcb=(project/'logger_v2_ups.kicad_pcb').read_text(encoding='utf-8')
ss={props(b).get('Reference'):props(b) for _,_,b in blocks(sch,'symbol') if props(b).get('Reference','').startswith(('R','C','J','U','L','Q'))}
pp={props(b).get('Reference'):(props(b),re.match(r'\(footprint "([^"]+)"',b)[1],b) for _,_,b in blocks(pcb,'footprint')}
for r,p in ss.items():
    q,fp,b=pp[r]
    assert p['Footprint']==fp,(r,'Footprint')
    for key in ['Value','MPN','DigiKey','Manufacturer','Rating','Datasheet']:
        assert p.get(key,'')==q.get(key,''),(r,key)
    for key,v in updates.get(r,{}).items():assert p[key]==v,(r,key)
    lib,name=fp.split(':')
    libdir=project/(lib+'.pretty') if lib=='logger_v2_ups' else Path('C:/Users/lintaroh/AppData/Local/Programs/KiCad/9.0/share/kicad/footprints')/(lib+'.pretty')
    assert (libdir/(name+'.kicad_mod')).exists(),fp
report['schematic_pcb_value_mpn_footprint_parity']=True
# Physical connector pads match the project-local footprint; do not replace copper.
def pad_signature(s,indent):
    result=[]
    for _,_,b in blocks(s,'pad',indent):
        head=re.match(r'\(pad "([^"]*)" (\S+) (\S+)',b).groups()
        attrs=[]
        for k in ['at','size','drill']:
            m=re.search(r'\('+k+r' ([^)]+)\)',b)
            nums=m[1].split() if m else []
            if k=='at':nums=nums[:2]
            attrs.append(tuple(float(x) for x in nums))
        if head[2]=='oval' and attrs[1][0]==attrs[1][1]:head=(head[0],head[1],'circle')
        result.append((head,tuple(attrs)))
    return sorted(result)
for r in ['J1','J2','J3','J4']:
    q,fp,b=pp[r];name=fp.split(':')[1]
    local=(project/'logger_v2_ups.pretty'/(name+'.kicad_mod')).read_text(encoding='utf-8')
    assert pad_signature(b,2)==pad_signature(local,1),(r,'header pad mismatch')
report['header_local_library_pad_geometry_matches']=True
stock={'25SVPF47M':48305,'EMK316BB7226ML-T':78721,'C0805C105K5RACTU':141160,'C0805C222J5GACTU':22273,'C0805C474K5RACTU':114052,'C0603C104K5RACTU':4527702,'C0603C103K5RACTU':6334222,'SSW-110-01-T-S':347,'SSW-108-01-T-S':1689,'SSW-106-01-T-S':1910,'744355147':5892,'2N7002K-7-W':5766,'MAX38890AATE+':2405,'RC0805FR-071KL':884480,'RC0603FR-0725K5L':31790,'RC0603FR-07100KL':14675,'RC0603FR-071ML':2048080}
for r,p in updates.items():stock[ss[r]['MPN']]=int(p['Stock_snapshot'])
source_us={'ERJ-6ENF3012V','RC0805FR-0712K4L','RC0805FR-0749K9L','RC0603FR-072M74L','RC0603FR-072M37L','LTC1440IMS8#TRPBF','C0805C222J5GACTU','C0805C474K5RACTU','SSW-110-01-T-S','SSW-106-01-T-S'}
def refkey(r):return re.match(r'[A-Z]+',r)[0],int(re.search(r'\d+',r)[0])
groups={}
for r,p in sorted(ss.items(),key=lambda x:refkey(x[0])):
    key=(p['MPN'],p['Footprint'])
    groups.setdefault(key,[]).append(r)
rows=[]
for (mpn,fp),refs in groups.items():
    p=ss[refs[0]];dk=p.get('DigiKey','');supplier='DigiKey' if dk else p.get('Supplier','')
    url=p.get('DigiKey_URL',p.get('Supplier_URL',''))
    source=url.replace('www.digikey.jp','www.digikey.com') if mpn in source_us else url
    val='1M' if mpn=='RC0603FR-071ML' else ' / '.join(dict.fromkeys(ss[r]['Value'] for r in refs))
    note=''
    if supplier!='DigiKey':note='引継ぎ指定品を維持。秋月で別途調達。在庫未確認。リードを90度曲げて実装。'
    elif any(r in ['R14','R15'] for r in refs):note='誤登録の100kΩ品を修正'
    elif any(r in updates for r in refs):note='抵抗値変更' if refs[0]!='U2' else 'DigiKey注文番号を補完'
    rows.append({'References':', '.join(refs),'Quantity':len(refs),'Value':val,'Manufacturer':p['Manufacturer'],'MPN':mpn,'Footprint':fp,'Supplier':supplier,'Supplier_Part_Number':dk if dk else '104251','Rating':p.get('Rating',''),'Stock':stock.get(mpn),'Stock_Checked':'2026-10-16' if mpn in stock else '未確認','URL':url,'Stock_Source':source,'Notes':note})
assert sum(r['Quantity'] for r in rows)==40
assert all(r['Stock']>=r['Quantity'] for r in rows if r['Supplier']=='DigiKey')
report['BOM']={'positions':40,'lines':len(rows),'digikey_positions':sum(r['Quantity'] for r in rows if r['Supplier']=='DigiKey'),'akizuki_positions':6}
with (out/'BOM_full.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
with (out/'DigiKey_upload.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['DigiKey Part Number','Quantity','Customer Reference'])
    for r in rows:
        if r['Supplier']=='DigiKey':w.writerow([r['Supplier_Part_Number'],r['Quantity'],r['References']])
(out/'bom_data.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
report['hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [project/'logger_v2_ups.kicad_sch',project/'logger_v2_ups.kicad_pcb']}
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
