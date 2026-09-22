"""Bounded sourcing update. Preserve wiring, symbol placement, DNP and PCB.
Run once only; snapshot is deliberately not overwritten.
"""
from pathlib import Path
import copy, hashlib, json, shutil, uuid, csv
import sexpdata as sx
P=Path(__file__).resolve().parents[1]
K=Path('C:/Users/lintaroh/AppData/Local/Programs/KiCad/9.0/share/kicad')
S=sx.Symbol
def n(k,*a):return [S(k),*a]
def ch(a,k):return [x for x in a if isinstance(x,list) and x and str(x[0])==k]
def one(a,k):return ch(a,k)[0]
def prop(a,k):return next(x for x in ch(a,'property') if x[1]==k)
def spans(text):
    depth=0;quoted=False;escaped=False;start=0
    for i,c in enumerate(text):
        if quoted:
            if escaped:escaped=False
            elif c=='\\':escaped=True
            elif c=='"':quoted=False
        elif c=='"':quoted=True
        elif c=='(':
            if depth==1:start=i
            depth+=1
        elif c==')':
            depth-=1
            if depth==1:yield start,i+1
def insert(text,expr):
    i=text.rfind(')');return text[:i]+sx.dumps(expr,pretty_print=True)+'\n'+text[i:]
def field(a,k,v):
    found=[x for x in ch(a,'property') if x[1]==k]
    if found:found[0][2]=v
    else:
        at=one(a,'at')[1:3]
        a.append(n('property',k,v,n('at',*at,0),n('effects',n('font',n('size',1.27,1.27)),n('hide',S('yes')))))
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()

paths=['logger_v2.kicad_sch','logger_v2_lte_sd.kicad_sch','logger_v2_custom.kicad_sym','logger_v2_expansion.kicad_sym','logger_v2.kicad_pcb','実装方針.md']
B=P/'logger_v2-backups/before_akizuki_selection_20260920'
assert not B.exists(),'Already applied: do not overwrite snapshot'
B.mkdir(parents=True)
for f in paths:shutil.copy2(P/f,B/f)
before={f:sha(P/f) for f in paths}
root=sx.loads((P/paths[0]).read_text(encoding='utf8'))
v1=sx.loads((P.parent/'logger_v1/logger_v1.kicad_sch').read_text(encoding='utf8'))

# SD: exact V1 symbol, footprint, model. Four mechanical pads share shield pin 9.
sdname='Micro_SD_Card_Molex_47219-2001'
sd=copy.deepcopy(next(x for x in ch(one(v1,'lib_symbols'),'symbol') if x[1]=='logger_v1_custom:'+sdname))
sd[1]='logger_v2_expansion:'+sdname
prop(sd,'Footprint')[2]='logger_v2_expansion:Molex_47219-2001'
prop(sd,'Datasheet')[2]='https://www.molex.com/en-us/products/part-detail/472192001'
for relative in ['logger_v1_custom.pretty/Molex_47219-2001.kicad_mod','3dmodels/Molex_47219-2001.step']:
    dst=relative.replace('logger_v1_custom.pretty','logger_v2_expansion.pretty')
    shutil.copy2(P.parent/'logger_v1'/relative,P/dst)
    target=P/dst
    if target.suffix=='.step' and target.stat().st_size<200:
        pointer=target.read_text()
        if pointer.startswith('version https://git-lfs.github.com/spec/v1'):
            oid=next(x.split(':',1)[1] for x in pointer.splitlines() if x.startswith('oid sha256:'))
            blob=P.parents[1]/'.git/lfs/objects'/oid[:2]/oid[2:4]/oid
            assert sha(blob)==oid
            shutil.copy2(blob,target)
libpath=P/'logger_v2_expansion.kicad_sym'
libsd=copy.deepcopy(sd);libsd[1]=sdname
libpath.write_text(insert(libpath.read_text(encoding='utf8'),libsd),encoding='utf8')

# Toshiba AF has 5.3 mm body, not Nexperia 3.9 mm SOIC. Keep pin locations.
uname='TC74HC595AF';fpname='Toshiba_SOP16_P300_1.27A'
u=copy.deepcopy(next(x for x in ch(one(root,'lib_symbols'),'symbol') if x[1]=='74xx:74HC595'))
u[1]='logger_v2_custom:'+uname
for x in ch(u,'symbol'):x[1]=x[1].replace('74HC595',uname)
prop(u,'Value')[2]=uname;prop(u,'Footprint')[2]='logger_v2_custom:'+fpname
prop(u,'Datasheet')[2]='https://akizukidenshi.com/goodsaffix/TC74HC595AP_datasheet_ja_20140301.pdf'
libpath=P/'logger_v2_custom.kicad_sym';libu=copy.deepcopy(u);libu[1]=uname
libpath.write_text(insert(libpath.read_text(encoding='utf8'),libu),encoding='utf8')
fp=sx.loads((K/'footprints/Package_SO.pretty/SOIC-16W_5.3x10.2mm_P1.27mm.kicad_mod').read_text(encoding='utf8'))
fp[1]=fpname
one(fp,'descr')[1]='Toshiba TC74HC595AF SOP16-P-300-1.27A; body 5.3x10.3, span 7.8, pitch 1.27 mm; generic IPC lands'
for poly in ch(fp,'fp_poly'):
    if one(poly,'layer')[1]=='F.Fab':
        for xy in ch(one(poly,'pts'),'xy'):
            if abs(xy[2])==5.1:xy[2]=5.15 if xy[2]>0 else -5.15
prop(fp,'Value')[2]=uname
one(fp,'model')[1]='${KIPRJMOD}/3dmodels/TC74HC595AF_nominal.step'
(P/'logger_v2_custom.pretty'/f'{fpname}.kicad_mod').write_text(sx.dumps(fp,pretty_print=True)+'\n',encoding='utf8')

selection={}
def add(refs,mpn,code='',value=None,note='',source=''):
    for ref in refs.split():selection[ref]={'MPN':mpn,'Supplier':'秋月電子通商' if code else '他社調達','SupplierCode':code,'SupplierURL':f'https://akizukidenshi.com/catalog/g/g{code}/' if code else source,'SelectionNote':note,'value':value}
add('U1',uname,'110077',uname)
add('U2','MAX-M10M-00B','131778')
add('U3','AE-BNO055-BO','116996',note='IMUのみモジュール実装の例外')
add('U4','ATA6561-GAQW-N','130008')
add('U5','MCP25625T-E/SS','112663')
add('D1 D2 D3 D4 D5 D6 D7 D8','OSG80805C1C','106421',note='黄緑570nm、2012、VF typ 2V')
add('D9 D10','PEC3824C2A-AU_R1_000A1','129497','PEC3824C2A-AU',note='CAN用24V双方向TVS、1/2=bus、3=GND')
add('Y1','20M10PB/XT324-10/80','130244','20MHz CL10pF',note='C2/C3=15pF; stray 2.5pF仮定、発振余裕と周波数を実機確認')
add('R1 R2 R3 R4 R6 R8 R9 R11','RK73B1JTTD102J','130351','1k',note='LED電流 約1.3mA @3.3V、VF=2V')
add('R5 R10 R12 R17','RK73B1JTTD103J','130355')
add('R15 R16','RK73B1JTTD472J','130353',note='IMUプルアップ、必須実装。DNPではない')
add('R18 R19 R20','RC0603J47K','129458',note='リール販売')
add('R13 R14','RC0603J120R','130332',note='リール販売。CAN終端定格は別途確認、現在の1608を維持')
add('C2 C3','CC0603N150J500','113312','15pF')
add('C4 C5 C6 C7 C8 C9 C10 C12','GRM188R72A104KA35D','114559')
add('C11','GRM188B31H105KAAL','116994',note='B特性、-25～85℃。車載温度保証ではない')
add('C13 C14','GRM21BR71A106KE51','117593')
add('C1','GRM188B11H103KA01','113387','10nF',note='RF給電バイパス。B特性、-25～85℃')
add('J1','S-037-TGG','102569')
add('J2','FH105-1x10SG','107199',note='10mm長ピン。既存3Dは汎用モデル、スタック高さは実物確認')
add('J3 J5','FH105-1x8SG/RH','104046',note='10mm長ピン。既存3Dは汎用モデル、スタック高さは実物確認')
add('J4','FH105-1x6SG/RH','104045',note='10mm長ピン。既存3Dは汎用モデル、スタック高さは実物確認')
add('J6 J7','43045-0400',note='既存ケーブルとの嵌合を維持する例外',source='https://www.molex.com/en-us/products/part-detail/430450400')
add('L1','LQG15HS27NJ02D',note='27nH 5%、300mA、DCRmax0.46Ω、SRFmin1.7GHz。メーカー推奨LQG15H系',source='https://www.murata.com/en-global/products/productdetail?partno=LQG15HS27NJ02%23')
add('D11','PESD5V0F1BL-Q',note='RF用双方向TVS、VRWM5.5V、Ctyp0.4pF / max0.55pF',source='https://www.nexperia.com/product/PESD5V0F1BL-Q')
add('R7','CRCW251227R0JNEG',note='27Ω 5% 1W、短絡時最悪約0.468W。基板温度・放熱を確認',source='https://www.vishay.com/docs/20035/dcrcwe3.pdf')

child={}
def cadd(value,mpn,code='',note='',source=''):
    child[value]={'MPN':mpn,'Supplier':'秋月電子通商' if code else '他社調達','SupplierCode':code,'SupplierURL':f'https://akizukidenshi.com/catalog/g/g{code}/' if code else source,'SelectionNote':note,'value':None}
cadd('DM3AT-SF-PEJM5','47219-2001',note='ユーザー指定：V1と同一。独立した挿入検出接点なし',source='https://www.molex.com/en-us/products/part-detail/472192001')
cadd('2452796-1','2452796-1',note='ユーザー指定RS 286-8822、維持',source='https://jp.rs-online.com/web/p/memory-card-connectors/2868822')
cadd('LTE service 1x06','PH-1x6SG/RH','101669')
cadd('U.FL-R-SMT-1(10)','U.FL-R-SMT-1(10)','115417')
cadd('2N7002','2N7002','103919')
cadd('SIM7070G','SIM7070G',note='指定部品、秋月制約の対象外',source='https://en.simcom.com/product/SIM7070G.html')
cadd('TPS62130RGTR','TPS62130RGTR',note='5V→3.8V、3A級。秋月の適合裸IC未確認、維持',source='https://www.ti.com/product/TPS62130')
cadd('TXU0204PWR','TXU0204PWR',note='2Mbps UART 1.8/3.3V変換用。旧案の2個目は購入数量から除く',source='https://www.ti.com/product/TXU0204')
cadd('USBLC6-4SC6','USBLC6-4SC6',note='SIM/SD用低容量ESD。秋月適合品未確認、維持',source='https://www.st.com/en/protection-devices/usblc6-4.html')
cadd('SC16IS750IPW','SC16IS750IPW',note='旧SPI-UART案。現在の実装方針では不使用、購入不要')
cadd('14.7456MHz CL12pF','14.7456MHz CL12pF',note='旧SPI-UART案の水晶。現在の方針では不使用、購入不要')

rows=[];counts={}
def structural(tree):
    keep=[]
    for x in tree:
        if isinstance(x,list) and x:
            key=str(x[0])
            if key=='lib_symbols':continue
            if key=='symbol':
                # Properties/library/pins may change; all physical placement and flags must not.
                keep.append([y for y in x if not(isinstance(y,list) and y and str(y[0]) in ['property','lib_id','pin'])])
                continue
        keep.append(x)
    return keep
for name,lookup,newcache in [(paths[0],selection,u),(paths[1],child,sd)]:
    text=(P/name).read_text(encoding='utf8');old=sx.loads(text);edits=[];count=0
    for a,b in spans(text):
        expr=sx.loads(text[a:b]);key=str(expr[0])
        if key=='lib_symbols':edits.append((a,b,insert(text[a:b],newcache)))
        if key!='symbol':continue
        ref=prop(expr,'Reference')[2];value=prop(expr,'Value')[2]
        if ref.startswith('#'):continue
        data=lookup.get(ref if name==paths[0] else value)
        assert data is not None,(name,ref,value)
        old_at=copy.deepcopy(one(expr,'at'));old_property_at={x[1]:copy.deepcopy(ch(x,'at')) for x in ch(expr,'property')}
        for k,v in data.items():
            if k!='value':field(expr,k,v)
        if data['value']:prop(expr,'Value')[2]=data['value']
        if name==paths[0] and ref=='U1':
            one(expr,'lib_id')[1]=u[1];prop(expr,'Footprint')[2]=prop(u,'Footprint')[2];prop(expr,'Datasheet')[2]=prop(u,'Datasheet')[2]
        if name==paths[1] and value=='DM3AT-SF-PEJM5':
            one(expr,'lib_id')[1]=sd[1];prop(expr,'Value')[2]='47219-2001';prop(expr,'Footprint')[2]=prop(sd,'Footprint')[2];prop(expr,'Datasheet')[2]=prop(sd,'Datasheet')[2]
            oldpins={x[1]:x for x in ch(expr,'pin')}
            expr[:]=[x for x in expr if not(isinstance(x,list) and x and str(x[0])=='pin')]
            for num in map(str,range(1,10)):expr.append(oldpins.get(num,n('pin',num,n('uuid',str(uuid.uuid4())))))
        assert old_at==one(expr,'at')
        assert all(ch(prop(expr,k),'at')==v for k,v in old_property_at.items())
        edits.append((a,b,sx.dumps(expr,pretty_print=True)));count+=1
        rows.append({'Sheet':name,'Reference':ref,'UUID':one(expr,'uuid')[1],'Value':prop(expr,'Value')[2],'MPN':data['MPN'],'Footprint':prop(expr,'Footprint')[2],'DNP':str(one(expr,'dnp')[1]),'Supplier':data['Supplier'],'Code':data['SupplierCode'],'URL':data['SupplierURL'],'Notes':data['SelectionNote']})
    for a,b,v in sorted(edits,reverse=True):text=text[:a]+v+text[b:]
    new=sx.loads(text);assert structural(old)==structural(new)
    (P/name).write_text(text,encoding='utf8');counts[name]=count
assert sha(P/'logger_v2.kicad_pcb')==before['logger_v2.kicad_pcb']
assert counts=={paths[0]:59,paths[1]:13},counts
assert str(one(next(x for x in ch(sx.loads((P/paths[0]).read_text(encoding='utf8')),'symbol') if prop(x,'Reference')[2]=='R15'),'dnp')[1])=='no'
with (P/'output/部品選定_20260920.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(P/'output/akizuki_selection_verification.json').write_text(json.dumps({'counts':counts,'wires_labels_positions_flags_unchanged':True,'pcb_unchanged':True,'before_sha256':before,'after_sha256':{f:sha(P/f) for f in paths}},indent=2),encoding='utf8')
print(json.dumps(counts));print('Wires, labels, placements, DNP flags and PCB preserved.')
