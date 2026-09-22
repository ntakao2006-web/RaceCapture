from pathlib import Path
import sexpdata as sx
import copy, uuid, math, json, datetime, xml.etree.ElementTree as ET

P=Path(__file__).resolve().parents[1]
S=sx.Symbol
def node(k,*v): return [S(k),*v]
def children(a,k): return [v for v in a if isinstance(v,list) and v and str(v[0])==k]
def one(a,k): return children(a,k)[0]
def prop(a,k): return next(v for v in children(a,'property') if v[1]==k)
def write(path,obj): path.write_text(sx.dumps(obj,pretty_print=True)+'\n',encoding='utf-8')
def uid(): return str(uuid.uuid4())
BASE=P/'logger_v2-backups'/'phase1_source'
if not BASE.exists():
    BASE.mkdir()
    for name in ['logger_v2.kicad_sch','logger_v2.kicad_pcb','logger_v2.kicad_pro','logger_v2_custom.kicad_sym','fp-lib-table','sym-lib-table']:
        (BASE/name).write_bytes((P/name).read_bytes())
src=sx.loads((BASE/'logger_v2.kicad_sch').read_text(encoding='utf-8'))
oldlib={v[1]:v for v in children(one(src,'lib_symbols'),'symbol')}
parts={prop(c,'Reference')[2]:copy.deepcopy(c) for c in children(src,'symbol') if not prop(c,'Reference')[2].startswith('#')}
root=one(src,'uuid')[1]
libs={}
for ref,c in parts.items():
    oldid=one(c,'lib_id')[1]
    name=oldid.split(':')[-1]
    # Give the UNO headers their own labels so the MCU pin identity is visible.
    if ref in ['J2','J3','J4','J5']: name='UNO_Q_'+ref
    if name not in libs:
        lib=copy.deepcopy(oldlib[oldid]);lib[1]=name
        for z in children(lib,'symbol'): z[1]=z[1].replace(oldid.split(':')[-1],name,1)
        libs[name]=lib
    one(c,'lib_id')[1]='logger_v2_custom:'+name
    for k in ['mirror','at']: c[:]=[v for v in c if not (isinstance(v,list) and str(v[0])==k)]
    one(c,'dnp')[1]=S('yes' if ref in ['R10','R13','R14','R15','R16'] else 'no')

# Datasheet-defined header names; the original connector pad order is retained.
header_names={
 'J2':{1:'D21_I2C2_SCL',2:'D20_I2C2_SDA',3:'AREF',4:'GND',5:'D13_SPI2_SCK',6:'D12_SPI2_MISO',7:'D11_SPI2_MOSI',8:'D10_SPI2_SS',9:'D9',10:'D8'},
 'J3':{1:'BOOT',2:'IOREF',3:'RESET_N',4:'+3V3',5:'+5V',6:'GND',7:'GND',8:'VIN'},
 'J4':{1:'A0_D14',2:'A1_D15',3:'A2_D16',4:'A3_D17',5:'A4_D18_I2C3_SDA',6:'A5_D19_I2C3_SCL'},
 'J5':{1:'D7',2:'D6',3:'D5_FDCAN1_RX',4:'D4_FDCAN1_TX',5:'D3',6:'D2',7:'D1_USART1_TX',8:'D0_USART1_RX'}}
for ref,names in header_names.items():
    lib=libs['UNO_Q_'+ref]
    # Place pin names outside the narrow connector body.
    lib[:]=[z for z in lib if not (isinstance(z,list) and str(z[0])=='pin_names')]
    lib.insert(2,node('pin_names',node('offset',1.016)))
    for sub in children(lib,'symbol'):
        for pin in children(sub,'pin'): one(pin,'name')[1]=names[int(one(pin,'number')[1])]

netroot=ET.parse(P/'logger_v2-backups'/'baseline_implementation.xml').getroot()
netmap={}
for net in netroot.findall('./nets/net'):
    name=net.attrib['name'].lstrip('/')
    for n in net.findall('node'):netmap[(n.attrib['ref'],n.attrib['pin'])]=None if name.startswith('unconnected-') else name
rename={'CAN1_RxD':'CAN1_RXD','CAN2_CS':'CAN2_CS_N','CAN2_INT':'CAN2_INT_N','CAN2_MISO':'SPI2_MISO','CAN2_MOSI':'SPI2_MOSI','CAN2_SCK':'SPI2_SCK','CAN2_RESET':'CAN2_RESET_N','GNSS_RxD':'GNSS_TXD','GNSS_TxD':'GNSS_RXD','GNSS_RESET':'GNSS_RESET_N','GNSS_PPS':'GNSS_TIMEPULSE','IMU_RESET':'IMU_RESET_N','STATUS_OUT':'STATUS_LATCH','VCC':'VIN',
 'Net-(D9-LINE1)':'CAN2_H','Net-(D9-LINE2)':'CAN2_L','Net-(D10-LINE1)':'CAN1_H','Net-(D10-LINE2)':'CAN1_L','Net-(J1-In)':'GNSS_RF','Net-(U2-VCC_RF)':'GNSS_VCC_RF','Net-(C1-Pad1)':'GNSS_ANT_BIAS','Net-(U2-LNA_EN)':'GNSS_LNA_EN','Net-(U5-OSC1)':'CAN2_OSC1','Net-(U5-OSC2)':'CAN2_OSC2','Net-(U5-R_{XD})':'CAN2_RX_LINK','Net-(U5-T_{XD})':'CAN2_TX_LINK'}
for i,ch in enumerate('ABCDEFGH'): rename[f'Net-(U1-Q{ch})']=f'STATUS_Q{i}'
for i in range(1,9):rename[f'Net-(D{i}-A)']=f'LED{i}_A'
for k,v in list(netmap.items()):netmap[k]=rename.get(v,v)
def nets(ref,d):
    for n,v in d.items():netmap[(ref,str(n))]=v
nets('J2',{1:'IMU_SCL',2:'IMU_SDA',3:None,4:'GND',5:'SPI2_SCK',6:'SPI2_MISO',7:'SPI2_MOSI',8:'CAN2_CS_N',9:'CAN2_INT_N',10:'CAN2_RESET_N'})
nets('J5',{1:'STATUS_LATCH',2:'GNSS_TIMEPULSE',3:'CAN1_RXD',4:None,5:'GNSS_RESET_N',6:'IMU_RESET_N',7:'GNSS_RXD',8:'GNSS_TXD'})
nets('J3',{1:None,2:None,3:None,8:None})
nets('J4',{1:None,2:None,3:None,4:None,5:None,6:None})
nets('U2',{7:'GND'});nets('U4',{1:'+3V3'});nets('J7',{1:None});nets('L1',{2:'GNSS_ANT_BIAS'})
prop(parts['C1'],'Value')[2]='100nF X7R 16V'
prop(parts['R7'],'Value')[2]='22R 1W'
prop(parts['R7'],'Footprint')[2]='Resistor_SMD:R_2512_6332Metric'
prop(parts['R7'],'Datasheet')[2]='https://www.vishay.com/docs/20035/dcrcwe3.pdf'
prop(parts['U2'],'Footprint')[2]='RF_GPS:ublox_NEO'
prop(parts['U3'],'Value')[2]='AE-BNO055-BO'
for i in range(1,9):prop(parts['D'+str(i)],'Value')[2]='LED 3mm'
prop(parts['U5'],'Datasheet')[2]='https://ww1.microchip.com/downloads/en/DeviceDoc/MCP25625-CAN-Controller-Data-Sheet-20005282C.pdf'
for ref,val in [('J2','UNO Q D8-D13 / I2C2'),('J3','UNO Q POWER'),('J4','UNO Q A0-A5 / I2C3'),('J5','UNO Q D0-D7')]:prop(parts[ref],'Value')[2]=val

def effects(size=1.0,justify=None):return node('effects',node('font',node('size',size,size)),*([node('justify',S(justify))] if justify else []))
def field(c,name,value):
    c.append(node('property',name,value,node('at',0,0,0),node('effects',node('font',node('size',1,1)),node('hide',S('yes')))))
field(parts['R7'],'MPN','CRCW251222R0FKEG')
field(parts['R13'],'Assembly','DNP default; fit 120R only at CAN2 bus end')
field(parts['R14'],'Assembly','DNP: existing vehicle bus termination')
for r in ['R10','R15','R16']:field(parts[r],'Assembly','DNP: optional only')

out=[S('kicad_sch'),node('version',20250114),node('generator','eeschema'),node('generator_version','9.0'),node('uuid',root),node('paper','A3'),node('title_block',node('title','EcoLogger v2 - Phase 1'),node('date','2026-09-07'),node('rev','Phase1'),node('comment',1,'UNO Q shield / +5V, +3V3 / local net labels'))]
items=[]; pinloc={}; direct=set()
def wire(a,b):
    if a==b:return
    items.append(node('wire',node('pts',node('xy',*a),node('xy',*b)),node('stroke',node('width',0),node('type',S('default'))),node('uuid',uid())))
def label(name,x,y,angle=0):items.append(node('label',name,node('at',x,y,0 if angle==180 else 90 if angle==270 else angle),effects(1.0,'right' if angle in [180,270] else 'left'),node('uuid',uid())))
def text(s,x,y,size=1.27):items.append(node('text',s,node('at',x,y,0),effects(size,'left'),node('uuid',uid())))
def nc(x,y):items.append(node('no_connect',node('at',x,y),node('uuid',uid())))
def junction(x,y):items.append(node('junction',node('at',x,y),node('diameter',0),node('color',0,0,0,0),node('uuid',uid())))
def place(ref,x,y,angle=0,mirror=False):
    c=parts[ref];c.insert(2,node('at',x,y,angle))
    if mirror:c.insert(3,node('mirror',S('y')))
    for f in children(c,'property'):
        k=f[1];f[:]=[v for v in f if not(isinstance(v,list) and str(v[0]) in ['at','effects'])]
        if k in ['Reference','Value']:
            if ref.startswith('U'):fx,fy=x-(20.32 if ref=='U2' else 12.7 if ref in ['U1','U5'] else 10.16 if ref=='U3' else 0),y+(25 if ref=='U2' else 31 if ref=='U5' else 22 if ref=='U1' else 17)
            elif ref in header_names:fx,fy=x,y-(18 if ref=='J2' else 15)
            elif ref in ['J6','J7']:fx,fy=x,y-8
            elif ref in ['D9','D10']:fx,fy=x+12.7,y
            elif ref.startswith(('R','C','L')) and angle%180==0:fx,fy=x+5.08,y-1.27
            else:fx,fy=x,y-4.0
            fy+=1.8 if k=='Value' else 0
            f.extend([node('at',fx,fy,angle%180),effects(1.0,'left' if (ref.startswith(('R','C','L')) and angle%180==0) or ref in ['D9','D10'] else None)])
        else:f.extend([node('at',x,y,0),node('effects',node('font',node('size',1,1)),node('hide',S('yes')))])
    lib=libs[one(c,'lib_id')[1].split(':')[-1]]
    for sub in children(lib,'symbol'):
        for pin in children(sub,'pin'):
            px,py,pa=one(pin,'at')[1:];n=one(pin,'number')[1]
            if mirror:px=-px;pa=(180-pa)%360
            r=math.radians(angle); rx=px*math.cos(r)-py*math.sin(r);ry=px*math.sin(r)+py*math.cos(r)
            px,py=round(x+rx,5),round(y-ry,5);pa=(pa+angle)%360
            pinloc[(ref,n)]=(px,py,pa)
    items.append(c)

for r,xy in {'J3':(36.83,43.18),'J4':(36.83,96.52),'J2':(105.41,43.18),'J5':(105.41,96.52),'U2':(205.74,60.96),'U1':(330.2,60.96),'U4':(63.5,175.26),'U5':(223.52,187.96),'U3':(353.06,162.56),'J1':(276.86,50.8),'J7':(121.92,175.26),'J6':(292.1,157.48),'D10':(109.22,201.93),'D9':(283.21,180.34),'R5':(163.83,95.25),'R10':(248.92,111.76),'R12':(162.56,226.06),'R17':(185.42,226.06),'R13':(295.91,207.01),'R14':(78.74,201.93),'R15':(342.9,215.9),'R16':(374.65,215.9)}.items():place(r,*xy)
# Bias-T uses short visible wires to make the series limiter unambiguous.
place('R7',246.38,86.36,90);place('L1',260.35,67.31);place('C1',260.35,96.52)
place('Y1',274.32,224.79,180);place('C2',266.7,237.49);place('C3',281.94,237.49)
for i,r in enumerate(['R1','R2','R3','R4','R6','R8','R9','R11']):
    y=35.56+i*10.16;place(r,373.38,y,90);place('D'+str(i+1),391.16,y,180)
    for key in [(r,'2'),('D'+str(i+1),'2')]:direct.add(key)
    a=pinloc[(r,'2')][:2];b=pinloc[('D'+str(i+1),'2')][:2];wire(a,b);label(f'LED{i+1}_A',a[0]+2.54,a[1])

# Connect RF center, bias inductor, current-limiting resistor and filter capacitor.
for key in [('U2','11'),('J1','1'),('L1','1'),('L1','2'),('R7','2'),('C1','1')]:direct.add(key)
a=pinloc[('U2','11')][:2];b=pinloc[('J1','1')][:2]
rf=(260.35,a[1]);wire(a,rf);wire(rf,b);wire(pinloc[('L1','1')][:2],rf);junction(*rf);label('GNSS_RF',rf[0],rf[1])
bias=(260.35,86.36);wire(pinloc[('L1','2')][:2],bias);wire(pinloc[('R7','2')][:2],bias);wire(bias,pinloc[('C1','1')][:2]);junction(*bias);label('GNSS_ANT_BIAS',*bias)
for key in [('Y1','1'),('Y1','2'),('C2','1'),('C3','1')]:direct.add(key)
for yp,cp,name in [('2','C2','CAN2_OSC1'),('1','C3','CAN2_OSC2')]:
    a=pinloc[('Y1',yp)][:2];b=pinloc[(cp,'1')][:2];bend=(b[0],a[1]);wire(a,bend);wire(bend,b);label(name,*bend,180 if cp=='C2' else 0)

# Local labels are intentionally used throughout this single sheet.
for key,(x,y,a) in pinloc.items():
    if key in direct:continue
    net=netmap[key]
    if net is None:nc(x,y);continue
    dx,dy={0:(-2.54,0),180:(2.54,0),90:(0,2.54),270:(0,-2.54)}[a]
    end=(round(x+dx,5),round(y+dy,5));wire((x,y),end)
    label(net,*end,270 if a==90 else 90 if a==270 else (180 if a==0 else 0))

# External UNO Q rails are the only supply inputs on the shield.
power=sx.loads((Path.home()/'AppData/Local/Programs/KiCad/9.0/share/kicad/symbols/power.kicad_sym').read_text(encoding='utf-8'))
flag=copy.deepcopy(next(v for v in children(power,'symbol') if v[1]=='PWR_FLAG'));flag[1]='power:PWR_FLAG'
for i,(net,x) in enumerate([('+3V3',30.48),('+5V',55.88),('GND',81.28)]):
    c=node('symbol',node('lib_id','power:PWR_FLAG'),node('at',x,246.38,0),node('unit',1),node('in_bom',S('no')),node('on_board',S('yes')),node('dnp',S('no')),node('uuid',uid()),node('property','Reference',f'#FLG0{i+1}',node('at',x,246.38,0),node('effects',node('font',node('size',1,1)),node('hide',S('yes')))),node('property','Value','PWR_FLAG',node('at',x,242.57,0),effects()),node('instances',node('project','logger_v2',node('path','/'+root,node('reference',f'#FLG0{i+1}'),node('unit',1)))))
    items.append(c);wire((x,246.38),(x,248.92));label(net,x,248.92)

for s,x,y in [('UNO Q / 3.3 V I/O',15,15),('GNSS / NEO-M9N',152,15),('STATUS / SPI2 shared',292,15),('CAN1 / VEHICLE RECEIVE ONLY',15,133),('CAN2 / MCP25625',152,133),('IMU / I2C2',322,133)]:text(s,x,y,1.8)
text('Official UNO Q pinout: D4 = TX, D5 = RX\nCAN1_RXD -> D5; GNSS_RESET_N -> D3\nD4 not connected. D20/D21 separate from A4/A5.',16,116,1.1)
text('V_USB = GND (USB unused)\nR7: 22R / 1W; R10: DNP\nRF trace: 50 ohm, short; RF ESD to add at PCB design.',152,119,1.1)
text('U4 TXD = +3V3; STBY = GND\nJ7 pin 1: NC. R14: DNP\nFirmware: bus monitoring / listen-only.',16,222,1.1)
text('R13: DNP default; fit only at CAN2 bus end\nJ6 pin 1 supplies +5V to sensor CAN bus.',156,260,1.1)
text('R15/R16: DNP, module has pull-ups\nINT and VOUT unused.',320,237,1.1)
text('PHASE 1: Decoupling and local bulk capacitors deferred per implementation policy.\nAdd to schematic/BOM before PCB manufacture. No PCB routing performed.',16,271,1.1)

embedded=[]
for name,lib in libs.items():
    e=copy.deepcopy(lib);e[1]='logger_v2_custom:'+name;embedded.append(e)
out.append(node('lib_symbols',*embedded,flag));out.extend(items);out.extend([node('sheet_instances',node('path','/',node('page','1'))),node('embedded_fonts',S('no'))])
write(P/'logger_v2.kicad_sch',out)
write(P/'logger_v2_custom.kicad_sym',node('kicad_symbol_lib',node('version',20241209),node('generator','kicad_symbol_editor'),*libs.values()))
(P/'output'/'expected_connectivity.json').write_text(json.dumps({r+'.'+n:v for (r,n),v in netmap.items()},indent=2),encoding='utf-8')
print(f'Wrote {len(parts)} components and {len(pinloc)} pins on one A3 sheet.')
