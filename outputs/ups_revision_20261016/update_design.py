from inspect_design import *
import shutil,hashlib,xml.etree.ElementTree as ET
project=root/'circuit/logger_v2_ups'
backup=out/'backup'
backup.mkdir(exist_ok=True)
selected=[
 ('R1','30.1k','ERJ-6ENF3012V','Panasonic Industry','P30.1KCCT-ND','panasonic-industry/ERJ-6ENF3012V/111568',93300,'0805; 30.1kOhm; +/-1%; 0.125W'),
 ('R2','12.1k','RC0805FR-0712K1L','YAGEO','311-12.1KCRCT-ND','yageo/RC0805FR-0712K1L/730517',1138,'0805; 12.1kOhm; +/-1%; 0.125W'),
 ('R3','332k','RC0805FR-07332KL','YAGEO','311-332KCRCT-ND','yageo/RC0805FR-07332KL/727869',9171,'0805; 332kOhm; +/-1%; 0.125W'),
 ('R5','12.4k','RC0805FR-0712K4L','YAGEO','311-12.4KCRCT-ND','yageo/RC0805FR-0712K4L/727572',21359,'0805; 12.4kOhm; +/-1%; 0.125W'),
 ('R7','49.9k','RC0805FR-0749K9L','YAGEO','311-49.9KCRCT-ND','yageo/RC0805FR-0749K9L/730932',910370,'0805; 49.9kOhm; +/-1%; 0.125W'),
 ('R9','2.74M','RC0603FR-072M74L','YAGEO','13-RC0603FR-072M74LCT-ND','yageo/RC0603FR-072M74L/12707882',7807,'0603; 2.74MOhm; +/-1%; 0.1W'),
 ('R14','10k','ERJ-3EKF1002V','Panasonic Industry','P10.0KHCT-ND','panasonic-industry/ERJ-3EKF1002V/198102',2135987,'0603; 10kOhm; +/-1%; 0.1W'),
 ('R15','2.37M','RC0603FR-072M37L','YAGEO','13-RC0603FR-072M37LCT-ND','yageo/RC0603FR-072M37L/5918308',7582,'0603; 2.37MOhm; +/-1%; 0.1W')
]
updates={}
for ref,val,mpn,mfr,dk,url,stock,rating in selected:
    updates[ref]={'Value':val,'MPN':mpn,'Manufacturer':mfr,'DigiKey':dk,'DigiKey_URL':'https://www.digikey.jp/en/products/detail/'+url,'Rating':rating,'Stock_checked':'2026-10-16','Stock_snapshot':str(stock),'Datasheet':('https://yageogroup.com/component-documentation/download/specsheet/'+mpn if mfr=='YAGEO' else 'https://industrial.panasonic.com/ww/products/pt/general-purpose-chip-resistors/models/'+mpn)}
updates['U2']={'DigiKey':'LTC1440IMS8#TRPBFCT-ND','Stock_checked':'2026-10-16','Stock_snapshot':'348','Rating':'Comparator with 1.182V reference; MSOP-8 3x3mm P0.65mm; 2..11V supply'}
def esc(v):return v.replace('\\','\\\\').replace('"','\\"')
def setprop(b,key,value,pcb=False):
    pat=r'(\(property "'+re.escape(key)+r'" ")((?:[^"\\]|\\.)*)(")'
    if re.search(pat,b):return re.sub(pat,lambda m:m[1]+esc(value)+m[3],b,count=1)
    coord=re.search(r'\(at ([\d.-]+) ([\d.-]+)',b)
    x,y=('0','0') if pcb else (coord[1],coord[2])
    if pcb:
        p=f'\n\t\t(property "{key}" "{esc(value)}"\n\t\t\t(at 0 0 0)\n\t\t\t(layer "F.Fab")\n\t\t\t(hide yes)\n\t\t\t(effects (font (size 1 1) (thickness 0.15)))\n\t\t)'
    else:
        p=f'\n\t\t(property "{key}" "{esc(value)}"\n\t\t\t(at {x} {y} 0)\n\t\t\t(effects (font (size 1.27 1.27)) (hide yes))\n\t\t)'
    return b[:-1]+p+'\n\t)'
original={}
for ext in ['kicad_sch','kicad_pcb','net']:
    p=project/('logger_v2_ups.'+ext)
    assert not (backup/p.name).exists(),'Backup exists; refusing overwrite'
    shutil.copy2(p,backup/p.name)
    original[ext]=p.read_bytes()
sch=original['kicad_sch'].decode('utf-8')
schprops={props(b).get('Reference'):props(b) for _,_,b in blocks(sch,'symbol')}
changes=[]
for ext,kind in [('kicad_sch','symbol'),('kicad_pcb','footprint')]:
    s=original[ext].decode('utf-8')
    for start,end,b in reversed(list(blocks(s,kind))):
        pr=props(b);ref=pr.get('Reference');new=b
        for key,value in updates.get(ref,{}).items():
            new=setprop(new,key,value,ext=='kicad_pcb')
        if ext=='kicad_pcb' and ref in ['J1','J2','J3','J4']:
            # Match the existing project-local assignment without replacing any geometry.
            new=re.sub(r'^\(footprint "[^"]+"',lambda m:'(footprint "'+schprops[ref]['Footprint']+'"',new,count=1)
        if new!=b:
            changes.append({'file':ext,'ref':ref,'fields':{k:{'before':pr.get(k),'after':v} for k,v in updates.get(ref,{}).items() if pr.get(k)!=v},'footprint_alias_aligned':ref in ['J1','J2','J3','J4']})
            s=s[:start]+new+s[end:]
    p=project/('logger_v2_ups.'+ext)
    assert p.read_bytes()==original[ext],'Source changed externally'
    p.write_bytes(s.encode('utf-8'))
(out/'changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'selection.json').write_text(json.dumps(updates,ensure_ascii=False,indent=2),encoding='utf-8')
print('Updated',len(changes),'component records. Backup:',backup)
