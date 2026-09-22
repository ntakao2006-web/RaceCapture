from pathlib import Path
import copy, json, uuid, shutil
import sexpdata as sx

P=Path(__file__).resolve().parents[1]
K=Path.home()/'AppData/Local/Programs/KiCad/9.0/share/kicad'
S=sx.Symbol
def n(k,*v):return [S(k),*v]
def ch(a,k):return [z for z in a if isinstance(z,list) and z and str(z[0])==k]
def one(a,k):return ch(a,k)[0]
def prop(a,k):return next(z for z in ch(a,'property') if z[1]==k)
def uid():return str(uuid.uuid4())
def write(p,a):p.write_text(sx.dumps(a,pretty_print=True)+'\n',encoding='utf-8')
def eff(size=1,hide=False):return n('effects',n('font',n('size',size,size)),*([n('hide',S('yes'))] if hide else []))
source=P/'logger_v2-backups/pcb_design_20260907/logger_v2.kicad_sch'
a=sx.loads(source.read_text(encoding='utf-8'))
lc=one(a,'lib_symbols');root=one(a,'uuid')[1]
parts={prop(z,'Reference')[2]:z for z in ch(a,'symbol')}
initial_refs=set(parts)
def setprop(c,key,val):
    existing=[z for z in ch(c,'property') if z[1]==key]
    if existing:existing[0][2]=val
    else:c.append(n('property',key,val,n('at',*one(c,'at')[1:3],0),eff(hide=True)))
def meta(ref,**fields):
    for key,val in fields.items():setprop(parts[ref],key,str(val))
def addlib(library,name):
    key=library+':'+name
    existing=[z for z in ch(lc,'symbol') if z[1]==key]
    if existing:return existing[0]
    doc=sx.loads((K/'symbols'/f'{library}.kicad_sym').read_text(encoding='utf-8'))
    c=copy.deepcopy(next(z for z in ch(doc,'symbol') if z[1]==name));c[1]=key;lc.append(c);return c
def copyfp(lib,name):
    f=sx.loads((K/'footprints'/f'{lib}.pretty'/f'{name}.kicad_mod').read_text(encoding='utf-8'))
    for m in ch(f,'model'):
        modelpath=m[1].split('}/',1)[1]
        src=K/'3dmodels'/modelpath
        dest=P/'3dmodels'/src.name
        shutil.copy2(src,dest);m[1]='${KIPRJMOD}/3dmodels/'+src.name
    write(P/'logger_v2_custom.pretty'/f'{name}.kicad_mod',f)
    return 'logger_v2_custom:'+name
fps={
'U1':copyfp('Package_SO','SOIC-16_3.9x9.9mm_P1.27mm'),
'LED':copyfp('LED_SMD','LED_0805_2012Metric'),
'Y1':copyfp('Crystal','Crystal_SMD_3225-4Pin_3.2x2.5mm'),
'L1':copyfp('Inductor_SMD','L_0402_1005Metric'),
'D11':copyfp('Diode_SMD','D_SOD-882'),
'BULK':copyfp('Capacitor_SMD','C_0805_2012Metric')}
for ref,fields in {
'U1':dict(Value='74HC595D,118',MPN='74HC595D,118',Manufacturer='Nexperia',LCSC='C5947',JLCPCB_Class='Basic',Footprint=fps['U1'],Datasheet='https://assets.nexperia.com/documents/data-sheet/74HC_HCT595.pdf'),
'U4':dict(MPN='ATA6561-GAQW-N',Manufacturer='Microchip',LCSC='C2929602',JLCPCB_Class='Extended'),
'U5':dict(Value='MCP25625-E/SS',MPN='MCP25625-E/SS',Manufacturer='Microchip',LCSC='C184944',JLCPCB_Class='Extended'),
'L1':dict(Value='27nH',MPN='LQG15HS27NJ02D',Manufacturer='Murata',Footprint=fps['L1']),
'Y1':dict(Value='20MHz 12pF',MPN='XC2EL89COO-114YLC-20M',Manufacturer='YXC',LCSC='C18213008',JLCPCB_Class='Extended',Footprint=fps['Y1'],Load_Capacitance='12pF',Datasheet='https://www.lcsc.com/product-detail/C18213008.html'),
'D9':dict(Value='NUP2105LT1G',MPN='NUP2105LT1G',Manufacturer='onsemi',LCSC='C14486',JLCPCB_Class='Extended',Datasheet='https://www.onsemi.com/pdf/datasheet/nup2105l-d.pdf'),
'D10':dict(Value='NUP2105LT1G',MPN='NUP2105LT1G',Manufacturer='onsemi',LCSC='C14486',JLCPCB_Class='Extended',Datasheet='https://www.onsemi.com/pdf/datasheet/nup2105l-d.pdf'),
}.items():meta(ref,**fields)
for i in range(1,9):meta(f'D{i}',Value='GREEN 0805',MPN='KT-0805G',Manufacturer='Hubei KENTO Elec',LCSC='C2297',JLCPCB_Class='Basic',Footprint=fps['LED'])
for ref in ['R1','R2','R3','R4','R6','R8','R9','R11']:meta(ref,Value='680R')
for ref in ['C2','C3']:meta(ref,Value='18pF',Specification='18pF C0G/NP0 50V; CL12pF crystal initial load')

# Restore the unchanged pin geometry from the installed standard symbol.
std=sx.loads((K/'symbols/74xx.kicad_sym').read_text(encoding='utf-8'))
u=copy.deepcopy(next(z for z in ch(std,'symbol') if z[1]=='74HC595'));u[1]='74xx:74HC595'
old=next(z for z in ch(lc,'symbol') if z[1]=='74xx:74HC595');lc[lc.index(old)]=u

def wire(p,q):a.append(n('wire',n('pts',n('xy',*p),n('xy',*q)),n('stroke',n('width',0),n('type',S('default'))),n('uuid',uid())))
def label(name,pt,angle=0):a.append(n('label',name,n('at',*pt,angle),n('effects',n('font',n('size',0.95,0.95)),n('justify',S('left'))),n('uuid',uid())))
def text(t,pt,size=1):a.append(n('text',t,n('at',*pt,0),eff(size),n('uuid',uid())))
def junction(pt):a.append(n('junction',n('at',*pt),n('diameter',0),n('color',0,0,0,0),n('uuid',uid())))
def component(ref,libid,value,x,y,fp,angle=0):
    library,name=libid.split(':',1);lib=addlib(library,name)
    c=n('symbol',n('lib_id',libid),n('at',x,y,angle),n('unit',1),n('exclude_from_sim',S('no')),n('in_bom',S('yes')),n('on_board',S('yes')),n('dnp',S('no')),n('uuid',uid()),
        n('property','Reference',ref,n('at',x+3.81,y-1.27,0),eff()),n('property','Value',value,n('at',x+3.81,y+1.27,0),eff()),
        n('property','Footprint',fp,n('at',x,y,0),eff(hide=True)),n('property','Datasheet','~',n('at',x,y,0),eff(hide=True)),
        n('instances',n('project','logger_v2',n('path','/'+root,n('reference',ref),n('unit',1)))))
    for unit in ch(lib,'symbol'):
        for pin in ch(unit,'pin'):c.append(n('pin',one(pin,'number')[1],n('uuid',uid())))
    a.append(c);parts[ref]=c;return c

# Expand the existing oscillator block by 12.7mm to give the new case pins space.
addlib('Device','Crystal_GND24');one(parts['Y1'],'lib_id')[1]='Device:Crystal_GND24'
for z in ch(parts['Y1'],'pin'):
    if z[1]=='2':z[1]='3'
parts['Y1'].extend([n('pin','2',n('uuid',uid())),n('pin','4',n('uuid',uid()))])
for ref in ['Y1','C2','C3']:
    c=parts[ref];one(c,'at')[1]+=12.7
    for p in ch(c,'property'):one(p,'at')[1]+=12.7
for w in ch(a,'wire'):
    pts=ch(one(w,'pts'),'xy')
    if all(129<=p[1]<=136 and 129<=p[2]<=139 for p in pts):
        for p in pts:
            if p[1]>130:p[1]=round(p[1]+12.7,2)
for z in ch(a,'junction'):
    at=one(z,'at')
    if 130<at[1]<=136 and 129<=at[2]<=139:at[1]=round(at[1]+12.7,2)
for ref,c in parts.items():
    if ref.startswith('#') and one(c,'at')[1:3]==[135.89,138.43]:
        one(c,'at')[1]+=12.7
        for p in ch(c,'property'):one(p,'at')[1]+=12.7
label('GND',(138.43,133.35),180);junction((148.59,133.35))

caps=[
('C4','100nF','+3V3',20.32,170.18,'U1.16 VCC'),
('C5','100nF','+5V',45.72,170.18,'U4.3 VCC'),
('C6','100nF','+3V3',71.12,170.18,'U4.5 VIO'),
('C7','100nF','+3V3',96.52,170.18,'U5.1 VIO'),
('C8','100nF','+3V3',121.92,170.18,'U5.19 VDD'),
('C9','100nF','+5V',147.32,170.18,'U5.27 VDDA'),
('C10','100nF','+3V3',20.32,191.77,'U2.23 VCC'),
('C11','1uF','+3V3',45.72,191.77,'U2.23 VCC bulk'),
('C12','100nF','+3V3',71.12,191.77,'U2.22 V_BCKP'),
('C13','10uF','+3V3',109.22,191.77,'J3.4 3V3 bulk'),
('C14','10uF','+5V',147.32,191.77,'CAN 5V bulk')]
for ref,value,net,x,y,function in caps:
    fp=fps['BULK'] if value=='10uF' else 'logger_v2_custom:C_0603_1608Metric'
    component(ref,'Device:C_Small',value,x,y,fp)
    wire((x,y-2.54),(x,y-5.08));label(net,(x,y-5.08))
    wire((x,y+2.54),(x,y+5.08));label('GND',(x,y+5.08))
    text(function,(x+3.81,y-8.89),0.9)
    meta(ref,Function=function,Specification=value+' X7R '+('10V' if value=='10uF' else '16V minimum'))
for ref,net,x in [('R18','SPI2_MOSI',205.74),('R19','SPI2_SCK',232.41),('R20','STATUS_LATCH',259.08)]:
    component(ref,'Device:R_Small_US','47k',x,76.2,'logger_v2_custom:R_0603_1608Metric')
    wire((x,73.66),(x,71.12));label(net,(x,71.12),90)
    wire((x,78.74),(x,81.28));label('GND',(x,81.28))
    meta(ref,Function='MCU startup pulldown')
component('D11','Device:D_TVS_Small','PESD5V0F1BL',187.96,43.18,fps['D11'],90)
label('GNSS_RF',(172.72,31.75));label('GNSS_RF',(187.96,40.64))
label('GND',(187.96,45.72))
meta('D11',MPN='PESD5V0F1BL,315',Manufacturer='Nexperia',LCSC='C45961',JLCPCB_Class='Extended',Datasheet='https://assets.nexperia.com/documents/data-sheet/PESD5V0F1BL.pdf',Function='SMA RF ESD protection')

# Fix historical labels without touching their electrical anchors.
tb=one(a,'title_block') if ch(a,'title_block') else None
if tb:
    for key,val in [('title','Logger v2 - UNO Q Sensor / CAN Shield'),('date','2026-09-07'),('rev','PCB review A')]:
        if ch(tb,key):one(tb,key)[1]=val
        else:tb.append(n(key,val))
write(P/'logger_v2.kicad_sch',a)
rows=[]
for ref,c in parts.items():
    if ref.startswith('#'):continue
    row={'Reference':ref,'New':ref not in initial_refs,'Value':prop(c,'Value')[2],'Footprint':prop(c,'Footprint')[2],'DNP':str(one(c,'dnp')[1])=='yes'}
    for key in ['MPN','Manufacturer','LCSC','Function','Specification','JLCPCB_Class']:
        p=[z for z in ch(c,'property') if z[1]==key]
        if p:row[key]=p[0][2]
    rows.append(row)
(P/'output/design_review_20260907/reviewed_parts_metadata.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print('Wrote reviewed schematic:',len(rows),'parts; new refs:',[z['Reference'] for z in rows if z['New']])
