from pathlib import Path
import sexpdata as sx, re, copy, datetime, json, csv

P=Path(__file__).resolve().parents[1]
S=sx.Symbol
def ch(x,k): return [a for a in x if isinstance(a,list) and a and str(a[0])==k]
def one(x,k): return ch(x,k)[0]
def props(x): return {str(a[1]):a[2] for a in ch(x,'property')}
def spans(t):
    depth=0; quoted=False; escape=False
    for i,c in enumerate(t):
        if quoted:
            if escape: escape=False
            elif c=='\\': escape=True
            elif c=='"': quoted=False
        elif c=='"': quoted=True
        elif c=='(':
            if depth==1: start=i
            depth+=1
        elif c==')':
            depth-=1
            if depth==1: yield start,i+1

def selection(fp,mpn,maker,supplier,code,url,spec,note,ds='~'):
    return dict(Footprint=fp,MPN=mpn,Manufacturer=maker,Supplier=supplier,SupplierCode=code,SupplierURL=url,Specification=spec,SelectionNote=note,Datasheet=ds,LCSC='',JLCPCB_Class='',Description=spec)
rules={
 'C7':selection('logger_v2_expansion:CP_EIA-7343-31_Kemet-D','T520D337M006ATE015','KEMET','DigiKey','399-4052-1-ND','https://www.digikey.jp/ja/products/detail/kemet/T520D337M006ATE015/818913','330uF 6.3V polymer tantalum, ESR 15mOhm, 7343-31','Pad 1 positive (+3V8); pad 2 negative (GND).','https://yageogroup.com/download/specsheet/T520D337M006ATE015'),
 'L1':selection('logger_v2_expansion:L_Bourns_SRN6045TA','SRN6045TA-2R2Y','Bourns','DigiKey','','https://www.digikey.com/en/products/detail/bourns-inc/SRN6045TA-2R2Y/6155102','2.2uH power inductor, 6A Irms, 9.5A typical Isat','V1 has no equivalent power inductor; preserve selected power part.','https://www.bourns.com/docs/product-datasheets/srn6045ta.pdf'),
 'L2':selection('logger_v2_custom:L_0603_1608Metric','LQW18AN27NJ00D','Murata','DigiKey','','https://www.digikey.jp/ja/products/detail/murata-electronics/LQW18AN27NJ00D/584382','27nH RF wirewound, 440mA, DCR 0.21ohm max, SRF 3.7GHz min','Same MPN and nominal footprint as LoggerV1 L1.','https://pim.murata.com/asset/pim4/inductor/JELF243A-0024_PDF_INDUCTOR'),
}
for r in ['C15','C23']:
    rules[r]=selection('logger_v2_custom:C_0805_2012Metric','C2012X7R1H105KT000N','TDK','秋月電子通商','115331','https://akizukidenshi.com/catalog/g/g115331/','1uF 50V X7R, 0805 (2012 metric)','Same footprint as V1 1uF. V1 does not specify an exact MPN.')
for r in ['C16','C18']:
    rules[r]=selection('logger_v2_custom:C_0603_1608Metric','CC0603CRNPO9BN1R0','YAGEO','DigiKey','311-1049-1-ND','https://www.digikey.jp/ja/products/detail/yageo/CC0603CRNPO9BN1R0/302783','1pF +/-0.25pF 50V C0G, 0603 (1608 metric)','Preserve 1p value and footprint; replace copied 100nF purchasing metadata.','https://www.yageogroup.com/download/specsheet/CC0603CRNPO9BN1R0')
expected={'C7':'330u','L1':'2.2u','L2':'0.027u','C15':'1u','C23':'1u','C16':'1p','C18':'1p'}

def property_update(t,d):
    x=sx.loads(t); existing=props(x)
    for k,v in d.items():
        if k in existing:
            pat=r'(\(property\s+"'+re.escape(k)+r'"\s+)"(?:\\.|[^"\\])*"'
            t,n=re.subn(pat,lambda m:m[1]+sx.dumps(v),t)
            assert n==1,(k,n)
        else:
            at=one(x,'at')[1:3]
            layer=' (layer "F.Fab")' if str(x[0])=='footprint' else ''
            t=t[:-1]+f'\n(property {sx.dumps(k)} {sx.dumps(v)} (at {at[0]} {at[1]} 0){layer} (effects (font (size 1.27 1.27)) (hide yes)))\n)'
    return t

geometry={'fp_line','fp_arc','fp_circle','fp_rect','fp_poly','fp_text','model','pad','descr','tags','attr','fp_text_box'}
def replace_geometry(t,fp):
    old=sx.loads(t); lib,name=fp.split(':'); template=sx.loads((P/(lib+'.pretty')/(name+'.kicad_mod')).read_text(encoding='utf8'))
    angle=one(old,'at')[3] if len(one(old,'at'))>3 else 0
    oldpads={a[1]:a for a in ch(old,'pad')}; additions=[]
    assert set(oldpads)=={a[1] for a in ch(template,'pad')}
    for a in template:
        if not isinstance(a,list) or not a or str(a[0]) not in geometry: continue
        a=copy.deepcopy(a); tag=str(a[0])
        if tag=='fp_text' and str(a[1]) in ['reference','value']:continue
        if tag=='pad':
            op=oldpads[a[1]]; at=one(a,'at'); local=at[3] if len(at)>3 else 0
            if angle or local:at[3:]=[(angle+local)%360]
            for key in ['net','pinfunction','pintype','uuid','clearance','zone_connect','thermal_bridge_width','thermal_gap']:
                a[:]=[v for v in a if not (isinstance(v,list) and v and str(v[0])==key)]
                a.extend(copy.deepcopy(ch(op,key)))
        # Footprint graphic IDs from library must not be duplicated on the board.
        elif tag.startswith('fp_'):
            a[:]=[v for v in a if not (isinstance(v,list) and v and str(v[0])=='uuid')]
        additions.append(sx.dumps(a))
    for a,b in reversed(list(spans(t))):
        z=sx.loads(t[a:b])
        if str(z[0]) in geometry:t=t[:a]+t[b:]
    t=re.sub(r'^(\(footprint\s+)"[^"]*"',lambda m:m[1]+sx.dumps(fp),t)
    return t[:-1]+'\n'+'\n'.join(additions)+'\n)'

backup=P/'logger_v2-backups'/('before_passive_footprints_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir(); plans=[]; report=[]
for suffix,tag in [('kicad_sch','symbol'),('kicad_pcb','footprint')]:
    f=P/('logger_v2.'+suffix); raw=f.read_bytes(); t=raw.decode('utf8'); old=sx.loads(t); seen=set(); edits=[]
    for a,b in spans(t):
        x=sx.loads(t[a:b])
        if str(x[0])!=tag:continue
        p=props(x); r=p.get('Reference')
        if r not in rules:continue
        seen.add(r); assert p['Value']==expected[r],(r,p)
        d=rules[r].copy(); block=t[a:b]; oldfp=p.get('Footprint',x[1])
        if tag=='footprint':
            d.pop('Footprint')
            if oldfp!=rules[r]['Footprint']:block=replace_geometry(block,rules[r]['Footprint'])
        block=property_update(block,d); y=sx.loads(block)
        # Only explicitly selected metadata and footprint geometry may change.
        def invariant(z):
            z=copy.deepcopy(z)
            z[:]=[v for v in z if not (isinstance(v,list) and v and ((str(v[0])=='property' and str(v[1]) in d) or (tag=='footprint' and str(v[0]) in geometry)))]
            if tag=='footprint': z[1]='allowed_footprint_change'
            return z
        assert invariant(x)==invariant(y),r
        if tag=='footprint':
            def connections(z):return {v[1]:[ch(v,k) for k in ['net','pintype','pinfunction','uuid','clearance']] for v in ch(z,'pad')}
            assert connections(x)==connections(y),r
            for m in ch(y,'model'):assert Path(m[1].replace('${KIPRJMOD}',str(P))).exists(),m
        edits.append((a,b,block)); report.append(dict(file=f.name,ref=r,value=p['Value'],old=oldfp,new=rules[r]['Footprint']))
    assert seen==set(rules)
    for a,b,block in reversed(edits):t=t[:a]+block+t[b:]
    new=sx.loads(t)
    def untouched(z):return [a for a in z if not (isinstance(a,list) and a and str(a[0])==tag and props(a).get('Reference') in rules)]
    assert untouched(old)==untouched(new),'Outside-scope change'
    (backup/f.name).write_bytes(raw);plans.append((f,raw,t.encode('utf8')))
for f,raw,new in plans:assert f.read_bytes()==raw,'File concurrently changed'
for f,raw,new in plans:f.write_bytes(new)
(P/'output/passive_footprints_20260922.json').write_text(json.dumps({'backup':str(backup),'changes':report,'invariants':'All other components, placements, values, wiring, tracks/vias/zones, pad nets and IDs unchanged'},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2))
print('Backup:',backup)
