from pathlib import Path
import json,uuid,copy,math,xml.etree.ElementTree as ET
import sexpdata as sx
P=Path(__file__).resolve().parents[1];S=sx.Symbol
def n(k,*v):return [S(k),*v]
def ch(a,k):return [z for z in a if isinstance(z,list) and z and str(z[0])==k]
def one(a,k):return ch(a,k)[0]
def prop(a,k):return next(z for z in ch(a,'property') if z[1]==k)
def write(p,a):p.write_text(sx.dumps(a,pretty_print=True)+'\n',encoding='utf-8')
a=sx.loads((P/'logger_v2.kicad_sch').read_text(encoding='utf-8'))
parts={prop(z,'Reference')[2]:z for z in ch(a,'symbol')}
def meta(ref,**fields):
    c=parts[ref]
    for k,v in fields.items():
        p=[z for z in ch(c,'property') if z[1]==k]
        if p:p[0][2]=v
        else:c.append(n('property',k,v,n('at',*one(c,'at')[1:3],0),n('effects',n('font',n('size',1,1)),n('hide',S('yes')))))

# Quantize geometry to the original 0.01mm precision before the file loader
# converts coordinates to integers; avoid binary float 146.04999999999998.
def quantize(v):
    if isinstance(v,list):
        if v and str(v[0]) in ['at','xy','start','end','center','mid']:
            for i in range(1,len(v)):
                if isinstance(v[i],float):v[i]=round(v[i],6)
        for z in v:quantize(z)
quantize(a)
# Explicitly split the GND vertical at the new Y1 case pin.
for w in list(ch(a,'wire')):
    pts=ch(one(w,'pts'),'xy')
    if [p[1:] for p in pts]==[[148.59,129.54],[148.59,137.16]]:
        pts[1][2]=133.35
        b=copy.deepcopy(w);one(b,'uuid')[1]=str(uuid.uuid4())
        bp=ch(one(b,'pts'),'xy');bp[0][2]=133.35;bp[1][2]=137.16;a.append(b)
# Case pins are both grounded, independently of any graphic segment splitting.
if not any(z[1]=='GND' and one(z,'at')[1:3]==[148.59,133.35] for z in ch(a,'label')):
    a.append(n('label','GND',n('at',148.59,133.35,0),n('effects',n('font',n('size',0.95,0.95)),n('justify',S('left'))),n('uuid',str(uuid.uuid4()))))

for ref in ['C1','C4','C5','C6','C7','C8','C9','C10','C12']:
    meta(ref,MPN='CC0603KRX7R9BB104',Manufacturer='Yageo',LCSC='C14663',JLCPCB_Class='Basic',Specification='100nF X7R 50V 0603')
meta('C11',MPN='CL10A105KB8NNNC',Manufacturer='Samsung',LCSC='C15849',JLCPCB_Class='Basic',Specification='1uF X5R 50V 0603')
for ref in ['C13','C14']:meta(ref,MPN='CL21A106KAYNNNE',Manufacturer='Samsung',LCSC='C15850',JLCPCB_Class='Basic',Specification='10uF X5R 25V 0805')
for ref in ['C2','C3']:meta(ref,MPN='CL10C180JB8NNNC',Manufacturer='Samsung',LCSC='C1647',JLCPCB_Class='Basic',Specification='18pF C0G 50V 5%; 20MHz CL12pF crystal')
for ref in ['R18','R19','R20']:meta(ref,MPN='0603WAF4702T5E',Manufacturer='UNI-ROYAL',LCSC='C25819',JLCPCB_Class='Basic')
for ref in ['R1','R2','R3','R4','R6','R8','R9','R11']:
    meta(ref,MPN='0603WAF6800T5E',Manufacturer='UNI-ROYAL',LCSC='C23228',JLCPCB_Class='Basic')
    for key in ['Reference','Value']:one(one(prop(parts[ref],key),'effects'),'font')[1]=n('size',1.0,1.0)

for l in ch(a,'label'):
    if l[1]=='GNSS_RF' and one(l,'at')[1:3]==[172.72,31.75]:one(l,'at')[3]=180
for key,y in [('Reference',41.91),('Value',44.45)]:one(prop(parts['D11'],key),'at')[1:]=[195.58,y,90]
meta('D11',Value='RF ESD')
meta('R7',Value='27R 1W',MPN='25121WJ0270T4E',Manufacturer='UNI-ROYAL',LCSC='C25478',JLCPCB_Class='Extended',Specification='27ohm 5% 1W; verify antenna supply under load')
meta('U4',Value='ATA6561-GAQW',MPN='ATA6561-GAQW')
meta('L1',LCSC='C12669',JLCPCB_Class='Extended')
meta('U2',MPN='NEO-M9N-00B',Manufacturer='u-blox',LCSC='C5119087',JLCPCB_Class='Extended; Standard PCBA only')
for ref in ['R5','R10','R12','R17']:meta(ref,MPN='0603WAF1002T5E',Manufacturer='UNI-ROYAL',LCSC='C25804',JLCPCB_Class='Basic')
for ref in ['R15','R16']:meta(ref,MPN='0603WAF4701T5E',Manufacturer='UNI-ROYAL',LCSC='C23162',JLCPCB_Class='Basic')
for ref in ['R13','R14']:meta(ref,MPN='0603WAF1200T5E',Manufacturer='UNI-ROYAL',LCSC='C22787',JLCPCB_Class='Basic')

# Final visual cleanup, preserving exactly the already verified net groups.
for l in list(ch(a,'label')):
    if l[1]=='GND' and one(l,'at')[1:3]==[148.59,133.35]:a.remove(l)
    if l[1]=='GND' and one(l,'at')[1:3]==[138.43,133.35]:one(l,'at')[1:]=[135.89,133.35,0]
    if l[1]=='GNSS_RF' and one(l,'at')[1:3]==[172.72,31.75]:a.remove(l)
def ensure_wire(p,q):
    if any({tuple(z[1:]) for z in ch(one(w,'pts'),'xy')}=={tuple(p),tuple(q)} for w in ch(a,'wire')):return
    a.append(n('wire',n('pts',n('xy',*p),n('xy',*q)),n('stroke',n('width',0),n('type',S('default'))),n('uuid',str(uuid.uuid4()))))
ensure_wire((135.89,133.35),(138.43,133.35))
ensure_wire((172.72,31.75),(172.72,40.64))
ensure_wire((172.72,40.64),(187.96,40.64))

write(P/'logger_v2.kicad_sch',a)
rows=[]
for ref,c in parts.items():
    if ref.startswith('#'):continue
    row={'Reference':ref,'Value':prop(c,'Value')[2],'Footprint':prop(c,'Footprint')[2],'DNP':str(one(c,'dnp')[1])=='yes'}
    for key in ['MPN','Manufacturer','LCSC','Function','Specification','JLCPCB_Class']:
        p=[z for z in ch(c,'property') if z[1]==key]
        if p:row[key]=p[0][2]
    rows.append(row)
(P/'output/design_review_20260907/reviewed_parts_metadata.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print('Metadata completed; Y1 case GND segment made explicit')
