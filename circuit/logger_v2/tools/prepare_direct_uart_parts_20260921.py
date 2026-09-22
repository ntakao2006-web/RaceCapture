"""Apply current policy to placed parts only. Never wire or move retained parts."""
from pathlib import Path
import copy,hashlib,json,shutil,uuid,csv
import sexpdata as sx
P=Path(__file__).resolve().parents[1];S=sx.Symbol
def n(k,*a):return [S(k),*a]
def ch(a,k):return [x for x in a if isinstance(x,list) and x and str(x[0])==k]
def one(a,k):return ch(a,k)[0]
def pr(a,k):return next(x for x in ch(a,'property') if x[1]==k)
def read(p):return sx.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def uid():return str(uuid.uuid4())
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
def insert(t,x):
    i=t.rfind(')');return t[:i]+sx.dumps(x,pretty_print=True)+'\n'+t[i:]
def field(a,k,v):
    found=[x for x in ch(a,'property') if x[1]==k]
    if found:found[0][2]=v
    else:a.append(n('property',k,v,n('at',*one(a,'at')[1:3],0),n('effects',n('font',n('size',1.27,1.27)),n('hide',S('yes')))))
B=P/'logger_v2-backups/before_direct_uart_parts_20260921'
assert not B.exists(),'Do not rerun over user changes'
B.mkdir(parents=True)
files=['logger_v2.kicad_sch','logger_v2_lte_sd.kicad_sch','logger_v2_expansion.kicad_sym','logger_v2.kicad_pcb','logger_v2.kicad_pro','実装方針.md']
for f in files:shutil.copy2(P/f,B/f)
before={f:sha(P/f) for f in files}
name='logger_v2_lte_sd.kicad_sch';text=(P/name).read_text(encoding='utf8');old=read(P/name)
libtext=(P/'logger_v2_expansion.kicad_sym').read_text(encoding='utf8');lib=read(P/'logger_v2_expansion.kicad_sym')
defs={x[1]:x for x in ch(lib,'symbol')}
remove={'4742a84a-08ca-45e8-884b-04598b36c983','a7db9ccd-1307-457f-947c-d433adeaf376','c3164fbf-8087-4442-b420-f22b387513b3'}
assert remove <= {one(x,'uuid')[1] for x in ch(old,'symbol')}
rows=[];newdefs={};instances=[]
def add(ref,base,value,mpn,fp,x,y,role,code='',source='',note=''):
    global libtext
    symbolname=mpn.replace('/','_')
    if symbolname not in newdefs:
        z=copy.deepcopy(defs[base]);oldname=z[1];z[1]=symbolname
        for unit in ch(z,'symbol'):unit[1]=unit[1].replace(oldname,symbolname)
        pr(z,'Value')[2]=value;pr(z,'Footprint')[2]=fp
        pr(z,'Datasheet')[2]=source or (f'https://akizukidenshi.com/catalog/g/g{code}/' if code else '')
        newdefs[symbolname]=z;libtext=insert(libtext,z)
    z=newdefs[symbolname];libid='logger_v2_expansion:'+symbolname
    c=n('symbol',n('lib_id',libid),n('at',x,y,0),n('unit',1),n('exclude_from_sim',S('no')),n('in_bom',S('yes')),n('on_board',S('yes')),n('dnp',S('no')),n('uuid',uid()))
    for k,v,dy in [('Reference',ref,-2.54),('Value',value,0)]:
        c.append(n('property',k,v,n('at',round(x+3.81,4),round(y+dy,4),0),n('effects',n('font',n('size',1.27,1.27)),n('justify',S('left')))))
    for k,v in [('Footprint',fp),('Datasheet',pr(z,'Datasheet')[2]),('MPN',mpn),('Role',role),('Supplier','秋月電子通商' if code else '他社調達'),('SupplierCode',code),('SupplierURL',f'https://akizukidenshi.com/catalog/g/g{code}/' if code else source),('SelectionNote',note)]:field(c,k,v)
    for unit in ch(z,'symbol'):
        for p in ch(unit,'pin'):c.append(n('pin',one(p,'number')[1],n('uuid',uid())))
    # This file is currently a standalone schematic. Do not recreate the deleted parent sheet.
    c.append(n('instances',n('project','logger_v2_lte_sd',n('path','/'+one(old,'uuid')[1],n('reference',ref),n('unit',1)))))
    instances.append(c);rows.append({'Reference':ref,'Value':value,'MPN':mpn,'Footprint':fp,'Role':role,'SupplierCode':code,'URL':f'https://akizukidenshi.com/catalog/g/g{code}/' if code else source,'Notes':note,'UUID':one(c,'uuid')[1]})

# Manufacturer land pattern: pad 0.4 x 0.6, total span 1.1 mm.
fp=read(P/'logger_v2_custom.pretty/D_SOD-882.kicad_mod');fp[1]='Prisemi_DFN1006_2L'
one(fp,'descr')[1]='PESDHC2FD4V5B Rev06.6 p5; 0.4x0.6 pads, 1.1mm outer span'
fp[:]=[x for x in fp if not(isinstance(x,list) and x and str(x[0])=='pad' and x[1]=='')]
for pad in ch(fp,'pad'):
    one(pad,'size')[1:]=[.4,.6];one(pad,'layers')[1:]=['F.Cu','F.Paste','F.Mask']
    pad[:]=[x for x in pad if not(isinstance(x,list) and x and str(x[0])=='solder_paste_margin')]
(P/'logger_v2_expansion.pretty/Prisemi_DFN1006_2L.kicad_mod').write_text(sx.dumps(fp,pretty_print=True)+'\n',encoding='utf8')
root=read(P/'logger_v2.kicad_sch')
defs['D_TVS_Small']=copy.deepcopy(next(x for x in ch(one(root,'lib_symbols'),'symbol') if x[1]=='Device:D_TVS_Small'))
defs['D_TVS_Small'][1]='D_TVS_Small'
add('L2','L','2.2uH','SRN6045TA-2R2Y','logger_v2_expansion:L_Bourns_SRN6045TA',124.46,182.88,'TPS62130 SW -> LTE_VBAT; power inductor',source='https://www.bourns.com/docs/product-datasheets/srn6045ta.pdf',note='秋月で適合する裸SMD品を確認できず。Irms 6A, Isat 9.5A typ; loop stability needs validation')
add('C15','C_Polarized','330uF 6.3V','T520D337M006ATE015','logger_v2_expansion:CP_EIA-7343-31_Kemet-D',180.34,182.88,'LTE_VBAT bulk near module',source='https://docs.rs-online.com/d8c4/0900766b81710abb.pdf',note='低ESRポリマー15mΩ。秋月の82uF SMD OS-CONは販売終了のため除外。汎用Dケース3D')
add('D12','D_TVS_Small','4.5V TVS','PESDHC2FD4V5B','logger_v2_expansion:Prisemi_DFN1006_2L',243.84,182.88,'LTE_VBAT to GND; SIMCom recommended transient protection',source='https://cdn.semikey.com/upload/pdfs/59/58/5958b6a05c58e8fad55bac421952aaf3.pdf',note='SIMCom Hardware Design Table8推奨。秋月未確認。DC過電圧遮断器ではない')
Csmall='logger_v2_expansion:C_0603_1608Metric';Clarge='logger_v2_expansion:C_0805_2012Metric';Rsmall='logger_v2_expansion:R_0603_1608Metric'
caps=[
 ('C16','10uF','GRM21BR71A106KE51',Clarge,'TPS62130 VIN to GND, input capacitor A','117593'),
 ('C17','10uF','GRM21BR71A106KE51',Clarge,'TPS62130 VIN to GND, input capacitor B; parallel C16','117593'),
 ('C18','10uF','GRM21BR71A106KE51',Clarge,'Buck output ceramic A; parallel C19/C20','117593'),
 ('C19','10uF','GRM21BR71A106KE51',Clarge,'Buck output ceramic B; parallel C18/C20','117593'),
 ('C20','10uF','GRM21BR71A106KE51',Clarge,'Buck output ceramic C; 30uF nominal total','117593'),
 ('C21','100nF','GRM188R72A104KA35D',Csmall,'TPS62130 AVIN local bypass','114559'),
 ('C22','100nF','GRM188R72A104KA35D',Csmall,'SIM7070G VBAT local bypass','114559'),
 ('C23','1uF','GRM188B31H105KAAL',Csmall,'SIM7070G VBAT local bypass, parallel C15/C22','116994'),
 ('C24','100nF','GRM188R72A104KA35D',Csmall,'SIM_VDD bypass at nanoSIM socket','114559'),
 ('C25','10uF','GRM21BR71A106KE51',Clarge,'microSD 3.3V supply bulk','117593'),
 ('C26','100nF','GRM188R72A104KA35D',Csmall,'microSD 3.3V local bypass','114559'),
 ('C27','100nF','GRM188R72A104KA35D',Csmall,'TXU0204 VCCA 3.3V local bypass','114559'),
 ('C28','100nF','GRM188R72A104KA35D',Csmall,'TXU0204 VCCB VDD_EXT 1.8V local bypass','114559'),
 ('C29','10nF','GRM188B11H103KA01',Csmall,'TPS62130 SS/TR soft-start to GND','113387')]
for i,(ref,val,mpn,fp,role,code) in enumerate(caps):add(ref,'C',val,mpn,fp,round(22.86+(i%7)*53.34,4),round(210.82+(i//7)*25.4,4),role,code,note='B特性品は-25～85℃。MLCC実効容量・電源応答は実装時に検証')
res=[
 ('R21','374k 1%','RC0603FR-07374KL','FB upper: LTE_VBAT to FB; nominal Vout=3.792V','','https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/pyu-rc-group_51_rohs_l.pdf'),
 ('R22','100k 0.1%','RG2012N-104-B-T5','FB lower: FB to AGND; paired with R21','111798',''),
 ('R23','100k','RK73B1JTTD104J','TPS62130 EN pulldown to GND','130357',''),
 ('R24','100k','RK73B1JTTD104J','2N7002 gate pulldown; PWRKEY released at MCU reset','130357',''),
 ('R25','1k','RK73B1JTTD102J','MCU LTE_PWRKEY to 2N7002 gate, series','130351',''),
 ('R26','47k','RC0603J47K','microSD CS pullup to 3.3V','129458',''),
 ('R27','47k','RC0603J47K','microSD MISO/DAT0 pullup to 3.3V','129458',''),
 ('R28','22R','RK73B1JTTD220J','SIM_CLK series between module and socket','130343',''),
 ('R29','22R','RK73B1JTTD220J','SIM_RST series between module and socket','130343',''),
 ('R30','22R','RK73B1JTTD220J','SIM_DATA series; no external pullup','130343',''),
 ('R31','0R','RK73Z1JTTD','LTE RF series matching placeholder; 50-ohm trace','111619','')]
for i,(ref,val,mpn,role,code,url) in enumerate(res):add(ref,'R',val,mpn,'logger_v2_expansion:R_0805_2012Metric' if ref=='R22' else Rsmall,round(22.86+(i%7)*38.1,4),round(260.35+(i//7)*20.32,4),role,code,url,note='電圧設定精度のため1%品を他社調達' if ref=='R21' else '')

edits=[];deleted=[]
for a,b in spans(text):
    e=sx.loads(text[a:b]);key=str(e[0])
    if key=='symbol' and one(e,'uuid')[1] in remove:
        deleted.append({'uuid':one(e,'uuid')[1],'value':pr(e,'Value')[2],'reason':pr(e,'Role')[2]});edits.append((a,b,''))
    elif key=='lib_symbols':
        cache=text[a:b]
        for z in newdefs.values():
            z=copy.deepcopy(z);z[1]='logger_v2_expansion:'+z[1];cache=insert(cache,z)
        edits.append((a,b,cache))
    elif key=='text':
        if e[1].startswith('U6: VBAT'):
            e[1]='SIM7070G: direct MCU UART via TXU0204. GNSS uses I2C in the wiring plan. ALL ADDED PARTS UNWIRED.'
        elif e[1]=='UART bridge':e[1]='SPI-UART bridge removed'
        elif e[1]=='1.8V translators':e[1]='UART TX/RX/RTS/CTS translator'
        elif e[1]=='5V -> 3.8V power / clock / PWRKEY':e[1]='5V -> 3.8V power / PWRKEY'
        edits.append((a,b,sx.dumps(e,pretty_print=True)))
for a,b,v in sorted(edits,reverse=True):text=text[:a]+v+text[b:]
for e in instances:text=insert(text,e)
for message,x,y in [('Power inductor / VBAT bulk / protection',110.49,167.64),('Power, SIM, SD and UART bypass capacitors (see Role field)',15.24,198.12),('Power control, SIM series and SD pullups (see Role field)',15.24,248.92)]:
    text=insert(text,n('text',message,n('at',x,y,0),n('effects',n('font',n('size',1.27,1.27)),n('justify',S('left'))),n('uuid',uid())))
new=sx.loads(text);retained={one(x,'uuid')[1]:x for x in ch(new,'symbol')}
for e in ch(old,'symbol'):
    if one(e,'uuid')[1] not in remove:assert retained[one(e,'uuid')[1]]==e
for k in ['wire','junction','label','global_label','hierarchical_label','no_connect','sheet']:assert ch(old,k)==ch(new,k)
assert len(instances)==28 and len(deleted)==3
for f in ['logger_v2.kicad_sch','logger_v2.kicad_pcb','logger_v2.kicad_pro']:assert before[f]==sha(P/f)
(P/name).write_text(text,encoding='utf8');(P/'logger_v2_expansion.kicad_sym').write_text(libtext,encoding='utf8')
with (P/'output/追加部品_20260921.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
(P/'output/parts_preparation_20260921.json').write_text(json.dumps({'deleted':deleted,'added':rows,'retained_parts_unchanged':True,'root_pcb_project_unchanged':True,'wiring_unchanged':True,'before_sha256':before,'new_child_count':len(ch(new,'symbol'))},ensure_ascii=False,indent=2),encoding='utf8')
print('Removed 3 obsolete parts; added',len(instances),'unwired parts;',sum(bool(x['SupplierCode']) for x in rows),'Akizuki sourced.')
