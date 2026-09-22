"""Bounded schematic/library update from the immutable 2026-09-19 snapshot.

Never reads an old phase-1 baseline. Existing PCB is deliberately not modified.
Re-running restores the SAME snapshot; do not use after subsequent user edits.
"""
from pathlib import Path
import copy, json, shutil, uuid, hashlib
import sexpdata as sx

P=Path(__file__).resolve().parents[1]
K=Path.home()/'AppData/Local/Programs/KiCad/9.0/share/kicad'
B=P/'logger_v2-backups/before_lte_sd_20260919'
S=sx.Symbol
def n(k,*v):return [S(k),*v]
def ch(a,k):return [v for v in a if isinstance(v,list) and v and str(v[0])==k]
def one(a,k):return ch(a,k)[0]
def prop(a,k):return next(v for v in ch(a,'property') if v[1]==k)
def uid():return str(uuid.uuid4())
def write(p,a):p.write_text(sx.dumps(a,pretty_print=True)+'\n',encoding='utf8')
def read(p):return sx.loads(p.read_text(encoding='utf8'))
def fx(size=1.27):return n('effects',n('font',n('size',size,size)))
def pin(num,name,kind,x,y,angle):return n('pin',S(kind),S('line'),n('at',x,y,angle),n('length',5.08),n('name',name,fx()),n('number',str(num),fx()))
def simple(name,reference,w,h,left,right,top=(),bottom=(),ds=''):
    a=n('symbol',name,n('pin_names',n('offset',1.016)),n('exclude_from_sim',S('no')),n('in_bom',S('yes')),n('on_board',S('yes')),
        n('property','Reference',reference,n('at',0,h+7.62,0),fx()),n('property','Value',name,n('at',0,h+5.08,0),fx()),
        n('property','Footprint','',n('at',0,0,0),fx(),n('hide',S('yes'))),n('property','Datasheet',ds,n('at',0,0,0),fx(),n('hide',S('yes'))),
        n('symbol',name+'_0_1',n('rectangle',n('start',-w,h),n('end',w,-h),n('stroke',n('width',.254),n('type',S('default'))),n('fill',n('type',S('background'))))))
    p=n('symbol',name+'_1_1')
    for side,items in [('l',left),('r',right)]:
        for i,(num,label,kind) in enumerate(items):
            p.append(pin(num,label,kind,(-1 if side=='l' else 1)*(w+5.08),round((len(items)-1)*1.27-i*2.54,2),0 if side=='l' else 180))
    for side,items in [('t',top),('b',bottom)]:
        for i,(num,label,kind) in enumerate(items):p.append(pin(num,label,kind,round(-(len(items)-1)*1.27+i*2.54,2),(h+5.08)*(1 if side=='t' else -1),270 if side=='t' else 90))
    a.append(p);return a

# New portable footprint library: copy established package geometry and models.
fpdir=P/'logger_v2_expansion.pretty';fpdir.mkdir(exist_ok=True)
models=P/'3dmodels';models.mkdir(exist_ok=True)
manifest={}
def footprint(libname):
    lib,name=libname.split(':')
    if name in manifest:return 'logger_v2_expansion:'+name
    f=read(K/'footprints'/(lib+'.pretty')/(name+'.kicad_mod'))
    m=one(f,'model');src=Path(m[1].replace('${KICAD9_3DMODEL_DIR}',str(K/'3dmodels')))
    generated=False
    if not src.exists() and name=='VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm':
        src=models/'TI_TPS62130_RGT16_mechanical.step';generated=True
    assert src.exists(),src
    if src.parent!=models:
        dst=models/src.name
        if dst.exists():assert dst.read_bytes()==src.read_bytes(),('Existing model differs',dst)
        else:shutil.copyfile(src,dst)
    m[1]='${KIPRJMOD}/3dmodels/'+src.name
    write(fpdir/(name+'.kicad_mod'),f)
    manifest[name]={'footprint':'logger_v2_expansion:'+name,'model':src.name,'source':'KiCad 9 '+libname,'model_kind':'TI nominal RGT16 geometry; simplified STEP' if generated else 'matching package STEP'}
    return 'logger_v2_expansion:'+name

simfp='SIMCom_SIM7070G_LCC68_24x24mm_P1mm'
f=n('footprint',simfp,n('version',20241229),n('generator','pcbnew'),n('layer','F.Cu'),n('descr','SIM7070G (not HP): SIMCom Hardware Design V1.03 pp12,18,19; 68 perimeter lands, 2.0x0.6mm; 24x24x2.3mm'),
    n('attr',S('smd')),n('property','Reference','REF**',n('at',0,-14.5),n('layer','F.SilkS'),fx(1)),n('property','Value','SIM7070G',n('at',0,14.5),n('layer','F.Fab'),fx(1)))
for layer,half,width in [('F.Fab',12,.1),('F.CrtYd',13.5,.05)]:
    f.append(n('fp_rect',n('start',-half,-half),n('end',half,half),n('stroke',n('width',width),n('type',S('solid'))),n('fill',S('none')),n('layer',layer)))
for x,y in [(-12.4,-12.4),(12.4,-12.4),(12.4,12.4),(-12.4,12.4)]:
    for dx,dy in [(1.5 if x<0 else -1.5,0),(0,1.5 if y<0 else -1.5)]:f.append(n('fp_line',n('start',x,y),n('end',x+dx,y+dy),n('stroke',n('width',.12),n('type',S('solid'))),n('layer','F.SilkS')))
f.append(n('fp_circle',n('center',-13.5,-8),n('end',-13.2,-8),n('stroke',n('width',.12),n('type',S('solid'))),n('fill',S('solid')),n('layer','F.SilkS')))
for i in range(17):
    for num,x,y,ang in [(1+i,-12,-8+i,0),(18+i,-8+i,12,90),(35+i,12,8-i,0),(52+i,8-i,-12,90)]:
        f.append(n('pad',str(num),S('smd'),S('oval'),n('at',x,y,ang),n('size',2,.6),n('layers','F.Cu','F.Paste','F.Mask')))
# The two 2.4mm manufacturer keepouts. Not electrical/thermal pads.
for x,y in [(-10.9,-9.2),(1.3,1.9)]:
    f.append(n('zone',n('net',0),n('net_name',''),n('layer','F.Cu'),n('uuid',uid()),n('hatch',S('edge'),.5),
        n('connect_pads',n('clearance',0)),n('min_thickness',.25),n('keepout',n('tracks',S('not_allowed')),n('vias',S('not_allowed')),n('pads',S('not_allowed')),n('copperpour',S('not_allowed')),n('footprints',S('allowed'))),
        n('fill',n('thermal_gap',.3),n('thermal_bridge_width',.3)),n('polygon',n('pts',n('xy',x,y),n('xy',x+2.4,y),n('xy',x+2.4,y+2.4),n('xy',x,y+2.4)))))
f.append(n('model','${KIPRJMOD}/3dmodels/SIMCom_SIM7070G_mechanical.step',n('offset',n('xyz',0,0,0)),n('scale',n('xyz',1,1,1)),n('rotate',n('xyz',0,0,0))))
write(fpdir/(simfp+'.kicad_mod'),f)
manifest[simfp]={'footprint':'logger_v2_expansion:'+simfp,'model':'SIMCom_SIM7070G_mechanical.step','source':'SIMCom Hardware Design V1.03 pp18-19 and Compatible Design V1.01 p12','model_kind':'dimension-based simplified mechanical STEP; shield details omitted'}

# Flatten inherited standard symbols so the new local library is self-contained.
cache={}
def standard(lib,name):
    if lib not in cache:cache[lib]={v[1]:v for v in ch(read(K/'symbols'/(lib+'.kicad_sym')),'symbol')}
    a=copy.deepcopy(cache[lib][name]);ext=ch(a,'extends')
    if ext:
        parent=standard(lib,ext[0][1]);parentname=parent[1]
        for v in ch(parent,'symbol'):v[1]=name+v[1][len(parentname):]
        for v in ch(a,'property'):
            matches=[q for q in ch(parent,'property') if q[1]==v[1]]
            if matches:parent.remove(matches[0])
            parent.append(v)
        parent[1]=name;a=parent
    return a

names='PWRKEY GND UART1_DTR UART1_RI UART1_DCD BOOT_CFG UART1_CTS UART1_RTS UART1_TXD UART1_RXD PCM_CLK PCM_SYNC PCM_DIN PCM_DOUT VDD_EXT NC GND GND GPIO1 GPIO2 GPIO3 DEBUG_RXD DEBUG_TXD USB_VBUS ADC NC USB_DP USB_DM GND SIM_VDD SIM_DATA SIM_CLK SIM_RST GPIO4 NC NC I2C_SDA I2C_SCL GND NC NC NC NC NC GND GND NC GPIO5 UART3_RXD UART3_TXD NC NETLIGHT GNSS_ANT GND VBAT VBAT VBAT GND GND RF_ANT GND GND GND GND GND STATUS GPIO6 GPIO7'.split()
assert len(names)==68
outs={4,5,7,9,11,12,14,23,32,33,38,50,52,66};ins={1,3,6,8,10,13,22,24,25,49,53}
def simpin(num):
    name=names[num-1];kind='power_in' if name in ['GND','VBAT'] else 'power_out' if num in [15,30] else 'no_connect' if name=='NC' else 'output' if num in outs else 'input' if num in ins else 'bidirectional'
    return num,name,kind
left=[1,3,4,5,7,8,9,10,6,66,52,15,24,27,28,22,23,49,50,11,12,13,14,25,16]
right=[30,31,32,33,60,53,19,20,21,34,48,67,68,37,38,26,35,36,40,41,42,43,44,47,51]
ground=[i+1 for i,v in enumerate(names) if v=='GND']
sim=simple('SIM7070G','U',33.02,35.56,list(map(simpin,left)),list(map(simpin,right)),list(map(simpin,[55,56,57])),list(map(simpin,ground)),ds='https://en.simcom.com/product/SIM7070G.html')
txu=simple('TXU0204PWR','U',12.7,12.7,[(2,'A1','input'),(3,'A2','input'),(4,'A3Y','output'),(5,'A4Y','output'),(8,'OE','input')],[(13,'B1Y','output'),(12,'B2Y','output'),(11,'B3','input'),(10,'B4','input'),(6,'NC','no_connect'),(9,'NC','no_connect')],[(1,'VCCA','power_in'),(14,'VCCB','power_in')],[(7,'GND','power_in')],ds='https://www.ti.com/lit/ds/symlink/txu0204.pdf')
simslot=simple('NSIM-2-C','J',15.24,12.7,[(1,'VCC','power_in'),(2,'RST','input'),(3,'CLK','input'),(7,'I/O','bidirectional'),(6,'VPP/NC','passive')],[('CD','DETECT','passive')],[],[(5,'GND/CD_COM','passive'),('SH','SHIELD','passive')],ds='https://www.sameskydevices.com/product/resource/nsim-2-c.pdf')
lib=n('kicad_symbol_lib',n('version',20241209),n('generator','kicad_symbol_editor'),sim,txu,simslot)
local={x[1]:x for x in ch(lib,'symbol')}
def getsym(name):
    if ':' in name:
        cat,key=name.split(':')
        if key not in local:
            z=standard(cat,key);lib.append(z);local[key]=z
        return local[key]
    return local[name]

# GNSS only: reuse v1 symbol/footprint/model; reconnect corresponding functions.
root=read(B/'logger_v2.kicad_sch');before=copy.deepcopy(root)
parts={prop(c,'Reference')[2]:c for c in ch(root,'symbol')}
maxsym=copy.deepcopy(next(z for z in ch(read(P.parent/'logger_v1/logger_v1_custom.kicad_sym'),'symbol') if z[1]=='MAX-M10M-00B'))
prop(maxsym,'Footprint')[2]='logger_v2_custom:MAX_M10M_00B_LCC18'
custom=read(B/'logger_v2_custom.kicad_sym');custom.append(maxsym);write(P/'logger_v2_custom.kicad_sym',custom)
embedded=copy.deepcopy(maxsym);embedded[1]='logger_v2_custom:MAX-M10M-00B';one(root,'lib_symbols').append(embedded)
shutil.copyfile(P.parent/'logger_v1/logger_v1_custom.pretty/MAX_M10M_00B_LCC18.kicad_mod',P/'logger_v2_custom.pretty/MAX_M10M_00B_LCC18.kicad_mod')
maxdata=(P.parent/'logger_v1/3dmodels/u-blox_MAX-M10M-00B.step').read_bytes()
if maxdata.startswith(b'version https://git-lfs.github.com/spec/v1'):
    oid=next(line.split(':',1)[1] for line in maxdata.decode().splitlines() if line.startswith('oid sha256:'))
    maxdata=(P.parents[1]/'.git/lfs/objects'/oid[:2]/oid[2:4]/oid).read_bytes()
    assert hashlib.sha256(maxdata).hexdigest()==oid
(models/'u-blox_MAX-M10M-00B.step').write_bytes(maxdata)
def move(c,dx,dy):
    for at in [one(c,'at')]+[one(q,'at') for q in ch(c,'property')]:at[1]=round(at[1]+dx,4);at[2]=round(at[2]+dy,4)
u=parts['U2'];move(u,0,-5.08);one(u,'lib_id')[1]='logger_v2_custom:MAX-M10M-00B';prop(u,'Value')[2]='MAX-M10M-00B';prop(u,'Footprint')[2]=prop(maxsym,'Footprint')[2];prop(u,'Datasheet')[2]=prop(maxsym,'Datasheet')[2]
for q in ch(u,'property'):
    if q[1]=='MPN':q[2]='MAX-M10M-00B'
one(prop(u,'Reference'),'at')[1:3]=[136,19.05];one(prop(u,'Value'),'at')[1:3]=[137,21.59]
u[:]=[q for q in u if not(isinstance(q,list) and str(q[0])=='pin')]
for sub in ch(maxsym,'symbol'):
    for pi in ch(sub,'pin'):u.append(n('pin',one(pi,'number')[1],n('uuid',uid())))
def xy(v):return tuple(one(v,'at')[1:3])
def wire(a,b):root.append(n('wire',n('pts',n('xy',*a),n('xy',*b)),n('stroke',n('width',0),n('type',S('default'))),n('uuid',uid())))
def nc(pt):root.append(n('no_connect',n('at',*pt),n('uuid',uid())))
def label(name,pt):root.append(n('label',name,n('at',*pt,0),n('effects',n('font',n('size',1.27,1.27)),n('justify',S('left'),S('bottom'))),n('uuid',uid())))
removed=[]
for v in list(root):
    if not isinstance(v,list):continue
    typ=str(v[0]);delete=False
    if typ=='wire':
        pts=[tuple(q[1:]) for q in ch(one(v,'pts'),'xy')]
        delete=(all(118<=x<=126 and 63<=y<=65 for x,y in pts) or one(v,'uuid')[1] in ['02d2eeb2-7d93-4bd6-ae07-3268582f769a','042a3a6f-307c-4ea8-bb0f-5d0e3844da08','58a15c8b-16a2-4f0f-9c1b-503384ef2850','0634361d-0310-47ef-b8df-cdc0eff2d10b'])
    elif typ=='junction':delete=118<=xy(v)[0]<=126 and xy(v)[1]==63.5
    elif typ=='no_connect':delete=xy(v)[0] in [99.06,144.78] and 25<=xy(v)[1]<=60
    elif typ=='symbol':delete=prop(v,'Reference')[2] in ['#PWR039','#PWR040']
    if delete:removed.append(one(v,'uuid')[1]);root.remove(v)
# Extend existing RF, LNA_EN and reset leads to the smaller MAX body.
for v in ch(root,'wire'):
    for q in ch(one(v,'pts'),'xy'):
        if q[1:]==[99.06,40.64]:q[1]=104.14
        if q[1] ==144.78 and q[2] in [33.02,35.56]:q[1]=139.7
for y in [30.48,33.02,35.56]:wire((99.06,y),(104.14,y))
wire((119.38,21.59),(119.38,22.86));wire((119.38,22.86),(119.38,25.4))
wire((119.38,22.86),(121.92,22.86));wire((121.92,22.86),(124.46,22.86))
wire((121.92,22.86),(121.92,25.4));wire((124.46,22.86),(124.46,25.4))
for pt in [(119.38,22.86),(121.92,22.86)]:root.append(n('junction',n('at',*pt),n('diameter',0),n('color',0,0,0,0),n('uuid',uid())))
move(parts['#PWR016'],0,-11.43)
wire((119.38,50.8),(119.38,53.34));wire((119.38,53.34),(121.92,53.34));wire((121.92,50.8),(121.92,53.34));wire((124.46,50.8),(124.46,53.34));wire((124.46,53.34),(121.92,53.34))
root.append(n('junction',n('at',121.92,53.34),n('diameter',0),n('color',0,0,0,0),n('uuid',uid())))
for pt in [(104.14,38.1),(104.14,43.18),(104.14,45.72),(139.7,38.1),(139.7,40.64),(139.7,43.18)]:nc(pt)
# Preserve R7=27R/1W and the RF bias tee; use external +3V3, not 50mA VCC_RF.
label('+3V3',(156.21,38.1))

# Additional hierarchical sheet. It contains zero wires, labels or power symbols.
sheetid=uid();childid=uid();rootid=one(root,'uuid')[1]
sheet=n('sheet',n('at',215.9,101.6),n('size',55.88,25.4),n('stroke',n('width',.1524),n('type',S('default'))),n('fill',n('color',0,0,0,0)),n('uuid',sheetid),
    n('property','Sheetname','LTE + microSD (unwired)',n('at',215.9,100.888,0),n('effects',n('font',n('size',1.27,1.27)),n('justify',S('left'),S('bottom')))),
    n('property','Sheetfile','logger_v2_lte_sd.kicad_sch',n('at',215.9,127.712,0),n('effects',n('font',n('size',1.27,1.27)),n('justify',S('left'),S('top')))),
    n('instances',n('project','logger_v2',n('path','/'+rootid,n('page','2')))))
root.append(sheet)
child=n('kicad_sch',n('version',20250114),n('generator','eeschema'),n('uuid',childid),n('paper','A3'),n('title_block',n('title','Logger v2 - LTE / microSD parts (UNWIRED)'),n('date','2026-09-19'),n('rev','A')),n('lib_symbols'))
rows=[]
def place(sym,ref,value,fp,x,y,role):
    z=getsym(sym);key=z[1];libid='logger_v2_expansion:'+key
    prop(z,'Footprint')[2]=fp
    if not any(q[1]==libid for q in ch(one(child,'lib_symbols'),'symbol')):
        e=copy.deepcopy(z);e[1]=libid;one(child,'lib_symbols').append(e)
    c=n('symbol',n('lib_id',libid),n('at',x,y,0),n('unit',1),n('exclude_from_sim',S('no')),n('in_bom',S('yes')),n('on_board',S('yes')),n('dnp',S('no')),n('uuid',uid()))
    for q in ch(z,'property'):
        if q[1].startswith('ki_'):continue
        v=copy.deepcopy(q);at=one(v,'at');at[1],at[2]=round(x+at[1],4),round(y-at[2],4)
        if v[1]=='Reference':v[2]=ref
        if v[1]=='Value':v[2]=value
        if v[1] in ['Reference','Value']:at[3]=0
        c.append(v)
    if ref[0] in ['R','L','Y']:
        for key,dy in [('Reference',-2.54),('Value',0)]:
            q=prop(c,key);one(q,'at')[1:]=[x+5.08,y+dy,0]
            e=one(q,'effects');e[:]=[v for v in e if not(isinstance(v,list) and str(v[0])=='justify')];e.append(n('justify',S('left')))
    if ref=='J10':
        q=prop(c,'Value');one(q,'at')[1:]=[x+5.08,y,0];one(q,'effects').append(n('justify',S('left')))
    c.append(n('property','Role',role,n('at',x,y,0),fx(),n('hide',S('yes'))))
    for sub in ch(z,'symbol'):
        for pi in ch(sub,'pin'):c.append(n('pin',one(pi,'number')[1],n('uuid',uid())))
    c.append(n('instances',n('project','logger_v2',n('path','/'+rootid+'/'+sheetid,n('reference',ref),n('unit',1)))))
    child.append(c);rows.append({'ref':ref,'value':value,'footprint':fp,'role':role})
def add(sym,ref,value,fp,x,y,role):place(sym,ref,value,footprint(fp),x,y,role)
place('SIM7070G','U6','SIM7070G','logger_v2_expansion:'+simfp,62.23,80.01,'LTE Cat-M/NB; VBAT 3.8V, UART/SIM 1.8V')
add('Interface_UART:SC16IS750xPW','U7','SC16IS750IPW','Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm',154.94,67.31,'SPI2 to LTE UART; 8 auxiliary GPIO')
add('TXU0204PWR','U8','TXU0204PWR','Package_SO:TSSOP-14_4.4x5mm_P0.65mm',215.9,66.04,'TX/RX/RTS/CTS 3.3V to 1.8V')
add('TXU0204PWR','U10','TXU0204PWR','Package_SO:TSSOP-14_4.4x5mm_P0.65mm',276.86,66.04,'Auxiliary DTR, RI, STATUS; one spare output')
add('NSIM-2-C','J8','NSIM-2-C','Connector_Card:nanoSIM_Hinged_CUI_NSIM-2-C',353.06,60.96,'1.8V nanoSIM; hinged socket with detect')
add('Connector:Micro_SD_Card_Det_Hirose_DM3AT','J9','DM3AT-SF-PEJM5','Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5',355.6,130.81,'3.3V microSD SPI; card detect')
add('Connector:Conn_Coaxial','J10','U.FL-R-SMT-1(10)','Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical',45.72,152.4,'LTE antenna, 50 ohm RF path')
add('Regulator_Switching:TPS62130','U9','TPS62130RGTR','Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm',154.94,130.81,'5V to 3.8V LTE buck; MCU-controlled EN')
add('Device:Crystal_GND24','Y2','14.7456MHz CL12pF','Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm',215.9,124.46,'UART bridge oscillator; 921600 baud at divisor 1')
add('Transistor_FET:2N7002','Q1','2N7002','Package_TO_SOT_SMD:SOT-23',274.32,125.73,'Open-drain PWRKEY; do not drive PWRKEY high')
for ref,x,role in [('U11',320.04,'SIM ESD: VDD/CLK/RST/DATA'),('U12',381,'microSD ESD: CLK/CS/MOSI/MISO')]:add('Power_Protection:USBLC6-4SC6',ref,'USBLC6-4SC6','Package_TO_SOT_SMD:SOT-23-6',x,175.26,role)
add('Connector_Generic:Conn_01x06','J11','LTE service 1x06','Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical',78.74,153.67,'USB VBUS/DP/DM/GND + BOOT_CFG/VDD_EXT service header')
add('Device:L','L2','2.2uH / SRN6045TA-2R2Y','Inductor_SMD:L_Bourns_SRN6045TA',116.84,182.88,'LTE buck power inductor; Irms 6A, Isat 9.5A typical')
add('Device:C_Polarized','C15','330uF 6.3V polymer','Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D',160.02,182.88,'LTE VBAT bulk; low ESR <= 0.1 ohm')
# Main decoupling, oscillator/reset, SIM and SD passives. All remain unconnected.
passives=[('C16','22uF 10V','C_0805_2012Metric','Buck VIN'),('C17','22uF 10V','C_0805_2012Metric','Buck VOUT'),('C18','100nF','C_0603_1608Metric','LTE VBAT'),('C19','100nF','C_0603_1608Metric','SIM_VDD'),('C20','10uF 6.3V','C_0805_2012Metric','microSD supply'),('C21','100nF','C_0603_1608Metric','microSD supply'),('C22','100nF','C_0603_1608Metric','SC16 VDD'),('C23','100nF','C_0603_1608Metric','U8 VCCA'),('C24','100nF','C_0603_1608Metric','U8 VCCB'),('C25','100nF','C_0603_1608Metric','U10 VCCA'),('C26','100nF','C_0603_1608Metric','U10 VCCB'),('C27','18pF','C_0603_1608Metric','Y2 load; tune to actual crystal'),('C28','18pF','C_0603_1608Metric','Y2 load; tune to actual crystal'),('C29','3.3nF','C_0603_1608Metric','Buck soft start'),('C30','100nF','C_0603_1608Metric','Bridge reset RC')]
for i,(ref,val,fp,role) in enumerate(passives):add('Device:C',ref,val,'Capacitor_SMD:'+fp,22.86+(i%8)*48.26,210.82+(i//8)*27.94,role)
res=[('R21','374k 1%','Buck feedback upper: 0.8*(1+374/100)=3.792V'),('R22','100k 1%','Buck feedback lower'),('R23','100k','Buck EN pulldown'),('R24','100k','PWRKEY gate pulldown'),('R25','10k','Bridge reset pullup'),('R26','10k','Bridge CS pullup'),('R27','10k','Bridge IRQ pullup'),('R28','47k','SD CS pullup'),('R29','47k','SD MISO pullup'),('R30','10k','SD detect pullup'),('R31','22R','SIM CLK series'),('R32','22R','SIM RST series'),('R33','22R','SIM DATA series'),('R34','0R','LTE RF matching series')]
for i,(ref,val,role) in enumerate(res):add('Device:R',ref,val,'Resistor_SMD:R_0603_1608Metric',22.86+(i%7)*38.1,260.35+(i//7)*15.24,role)
def text_at(message,x,y,size=1.27):child.append(n('text',message,n('at',x,y,0),n('effects',n('font',n('size',size,size)),n('justify',S('left'))),n('uuid',uid())))
text_at('LTE / microSD: SYMBOL PLACEMENT ONLY - ALL NEW PARTS UNWIRED',15.24,15.24,2.0)
text_at('U6: VBAT 3.8V / UART 1.8V. U7 shares existing SPI2. No header reassignment made.',15.24,21.59)
text_at('LTE module',20.32,29.21,1.6);text_at('UART bridge',134.62,29.21,1.6);text_at('1.8V translators',203.2,29.21,1.6);text_at('SIM / microSD sockets',322.58,29.21,1.6)
text_at('Antenna / USB service',17.78,135.89,1.5);text_at('5V -> 3.8V power / clock / PWRKEY',119.38,103,1.5)
text_at('Power and local decoupling (not wired)',15.24,197,1.5)
# Keep cache and local-library defaults identical even when passive instances
# use different footprints. Instance Footprint fields remain per component.
container=one(child,'lib_symbols')
for i,e in enumerate(container):
    if isinstance(e,list) and str(e[0])=='symbol':
        v=copy.deepcopy(local[e[1].split(':')[1]]);v[1]=e[1];container[i]=v
write(P/'logger_v2_expansion.kicad_sym',lib);write(P/'logger_v2_lte_sd.kicad_sch',child);write(P/'logger_v2.kicad_sch',root)
for table,kind,path in [('sym-lib-table','KiCad','logger_v2_expansion.kicad_sym'),('fp-lib-table','KiCad','logger_v2_expansion.pretty')]:
    a=read(B/table);a.append(n('lib',n('name','logger_v2_expansion'),n('type',kind),n('uri','${KIPRJMOD}/'+path),n('options',''),n('descr','Portable LTE and microSD expansion parts')));write(P/table,a)
(P/'output/lte_sd_parts_20260919.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
(P/'output/lte_sd_models_20260919.json').write_text(json.dumps(list(manifest.values()),ensure_ascii=False,indent=2),encoding='utf8')
# Structural scope guard: all pre-existing non-GNSS objects must be identical.
allowed=set(removed)
allowed.update(one(v,'uuid')[1] for v in ch(before,'symbol') if prop(v,'Reference')[2] in ['U2','#PWR01','#PWR040','#PWR016'])
allowed.update(['5b161c12-cc6d-4acd-93da-2cf1f1eac2e2','0bfb810a-2b0a-4590-a2b6-e12a74d70513','f872fbb3-16ef-45db-a9ab-f30e3c8dcb03'])
after={one(v,'uuid')[1]:v for v in root if isinstance(v,list) and ch(v,'uuid')}
checked=0
for v in before:
    if not isinstance(v,list) or not ch(v,'uuid'):continue
    key=one(v,'uuid')[1]
    if key not in allowed:assert after.get(key)==v,('Out-of-scope edit',key);checked+=1
assert (P/'logger_v2.kicad_pcb').read_bytes()==(B/'logger_v2.kicad_pcb').read_bytes()
assert not ch(child,'wire') and not ch(child,'label') and not ch(child,'global_label')
print('Existing objects preserved:',checked,'; new parts:',len(rows),'; new packages:',len(manifest))
