"""One-time bounded replacement using TE C-2452796 Rev C and manufacturer STEP.
Preserves unrelated schematic expressions verbatim. Never modifies the PCB.
"""
from pathlib import Path
import copy, hashlib, json, shutil, uuid
import sexpdata as sx
P=Path(__file__).resolve().parents[1]
S=sx.Symbol
def n(k,*a):return [S(k),*a]
def ch(a,k):return [x for x in a if isinstance(x,list) and x and str(x[0])==k]
def one(a,k):return ch(a,k)[0]
def prop(a,k):return next(x for x in ch(a,'property') if x[1]==k)
def write(p,a):p.write_text(sx.dumps(a,pretty_print=True)+'\n',encoding='utf8')
def spans(text):
    depth=0; quoted=False; escaped=False; start=0
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
def insert(text,expr):return text[:text.rfind(')')]+sx.dumps(expr,pretty_print=True)+'\n'+text[text.rfind(')'):]
fpname='nanoSIM_TE_2452796-1_Hinge'
symname='TE_2452796-1'
ds='https://www.te.com/en/product-2452796-1.html'
paths=['logger_v2.kicad_sch','logger_v2_lte_sd.kicad_sch','logger_v2_expansion.kicad_sym','logger_v2.kicad_pcb']
B=P/'logger_v2-backups/before_te_sim_20260920'
assert not B.exists(),'Snapshot exists; do not re-run against later user edits'
B.mkdir(parents=True)
for f in paths:shutil.copy2(P/f,B/f)
before={f:hashlib.sha256((P/f).read_bytes()).hexdigest() for f in paths}
libtext=(P/paths[2]).read_text(encoding='utf8');lib=sx.loads(libtext)
sym=copy.deepcopy(next(x for x in ch(lib,'symbol') if x[1]=='NSIM-2-C'))
sym[1]=symname
for x in ch(sym,'symbol'):x[1]=x[1].replace('NSIM-2-C',symname)
prop(sym,'Value')[2]='2452796-1';prop(sym,'Footprint')[2]='logger_v2_expansion:'+fpname;prop(sym,'Datasheet')[2]=ds
mapping={'1':'1','2':'2','3':'3','7':'6','6':'5','CD':'7','5':'4','SH':'8'}
pins=one(next(x for x in ch(sym,'symbol') if x[1].endswith('_1_1')),'pin')
unit=next(x for x in ch(sym,'symbol') if x[1].endswith('_1_1'))
for pin in ch(unit,'pin'):
    old=one(pin,'number')[1];one(pin,'number')[1]=mapping[old]
    if old=='CD':one(pin,'name')[1]='SW'
    if old=='5':one(pin,'name')[1]='GND/C5';one(pin,'at')[1]=-3.81
    if old=='SH':one(pin,'name')[1]='SHIELD';one(pin,'at')[1]=-1.27
shield=next(x for x in ch(unit,'pin') if one(x,'number')[1]=='8')
for number,x in [('9',1.27),('10',3.81)]:
    pin=copy.deepcopy(shield);one(pin,'number')[1]=number;one(pin,'at')[1]=x;unit.append(pin)
(P/paths[2]).write_text(insert(libtext,sym),encoding='utf8')
text=(P/paths[1]).read_text(encoding='utf8');original=sx.loads(text);edits=[];found=0
for a,b in spans(text):
    expr=sx.loads(text[a:b]);key=str(expr[0])
    if key=='lib_symbols':
        cache=copy.deepcopy(sym);cache[1]='logger_v2_expansion:'+symname
        edits.append((a,b,insert(text[a:b],cache)))
    if key=='symbol' and one(expr,'lib_id')[1]=='logger_v2_expansion:NSIM-2-C':
        found+=1;one(expr,'lib_id')[1]='logger_v2_expansion:'+symname
        prop(expr,'Value')[2]='2452796-1';prop(expr,'Footprint')[2]='logger_v2_expansion:'+fpname;prop(expr,'Datasheet')[2]=ds
        for pin in ch(expr,'pin'):pin[1]=mapping[pin[1]]
        for num in ['9','10']:expr.append(n('pin',num,n('uuid',str(uuid.uuid4()))))
        edits.append((a,b,sx.dumps(expr,pretty_print=True)))
assert found==1
for a,b,value in sorted(edits,reverse=True):text=text[:a]+value+text[b:]
(P/paths[1]).write_text(text,encoding='utf8')

def fx(size=1):return n('effects',n('font',n('size',size,size)))
fp=n('footprint',fpname,n('version',20241229),n('generator','pcbnew'),n('layer','F.Cu'),n('descr','TE 2452796-1; C-2452796 Rev C pp2-3, component-side PCB view; manufacturer numbered pads 1-10; official STEP transformed to PCB axes'),n('tags','nanoSIM hinge TE 2452796-1'),n('attr',S('smd')),
 n('property','Reference','REF**',n('at',0,-9),n('layer','F.SilkS'),fx()),n('property','Value','2452796-1',n('at',0,8.5),n('layer','F.Fab'),fx()))
def line(x1,y1,x2,y2,layer,width=.1):fp.append(n('fp_line',n('start',x1,y1),n('end',x2,y2),n('stroke',n('width',width),n('type',S('solid'))),n('layer',layer)))
def rect(x1,y1,x2,y2,layer,width=.1):fp.append(n('fp_rect',n('start',x1,y1),n('end',x2,y2),n('stroke',n('width',width),n('type',S('solid'))),n('fill',S('none')),n('layer',layer)))
# Figure p2: signal pad centre y=0, body bottom y=14; shift by -7 mm.
for num,x in zip(['1','4','2','5','3','6'],[-3.175,-1.905,-.635,.635,1.905,3.175]):
    fp.append(n('pad',num,S('smd'),S('rect'),n('at',x,-7),n('size',.8,1),n('layers','F.Cu','F.Paste','F.Mask')))
for num,x,y in [('7',-5.85,6),('8',5.85,6),('9',-5.85,-2.8),('10',5.85,-2.8)]:
    fp.append(n('pad',num,S('smd'),S('rect'),n('at',x,y),n('size',1.3,1.8),n('layers','F.Cu','F.Paste','F.Mask')))
# Dimensioned body and upper recess, visible on non-printing fabrication layer.
outline=[(-5.77,-7),(-4.15,-7),(-4.15,-6),(4,-6),(4,-7),(5.77,-7),(5.77,7),(-5.77,7),(-5.77,-7)]
for a,b in zip(outline,outline[1:]):line(*a,*b,'F.Fab')
rect(-6.75,-7.75,6.75,7.4,'F.CrtYd',.05)
# Sparse silkscreen, clear of all pads; pin 1 marker.
for x in [-6.22,6.22]:
    line(x,-6.7,x,-3.95,'F.SilkS',.12);line(x,-1.65,x,4.85,'F.SilkS',.12)
line(-4.75,7.15,4.75,7.15,'F.SilkS',.12)
fp.append(n('fp_circle',n('center',-3.175,-8.0),n('end',-3.025,-8.0),n('stroke',n('width',.12),n('type',S('solid'))),n('fill',S('solid')),n('layer','F.SilkS')))
# Six specified no-pattern / no-via areas. Lower left includes the switch contact.
keepouts=[(-2.54,-2.71,1.05),(0,-2.71,1.05),(2.54,-2.71,1.05),(-2.72,4.61,1.45),(0,4.61,1.05),(2.54,4.61,1.05)]
for x,y,w in keepouts:
    x1,x2=x-w/2,x+w/2;y1,y2=y-.7,y+.7
    rect(x1,y1,x2,y2,'Dwgs.User',.05)
    fp.append(n('zone',n('net',0),n('net_name',''),n('layer','F.Cu'),n('uuid',str(uuid.uuid4())),n('hatch',S('edge'),.25),n('connect_pads',n('clearance',0)),n('min_thickness',.25),n('keepout',n('tracks',S('not_allowed')),n('vias',S('not_allowed')),n('pads',S('not_allowed')),n('copperpour',S('not_allowed')),n('footprints',S('allowed'))),n('fill',n('thermal_gap',.3),n('thermal_bridge_width',.3)),n('polygon',n('pts',n('xy',x1,y1),n('xy',x2,y1),n('xy',x2,y2),n('xy',x1,y2)))))
fp.append(n('model','${KIPRJMOD}/3dmodels/TE_2452796-1.step',n('offset',n('xyz',0,0,0)),n('scale',n('xyz',1,1,1)),n('rotate',n('xyz',0,0,0))))
write(P/'logger_v2_expansion.pretty'/(fpname+'.kicad_mod'),fp)
after=sx.loads(text)
def unrelated(tree):return [x for x in tree if not (isinstance(x,list) and x and (str(x[0])=='lib_symbols' or (str(x[0])=='symbol' and ch(x,'lib_id') and one(x,'lib_id')[1] in ['logger_v2_expansion:NSIM-2-C','logger_v2_expansion:'+symname])))]
assert unrelated(original)==unrelated(after)
for f in ['logger_v2.kicad_sch','logger_v2.kicad_pcb']:assert before[f]==hashlib.sha256((P/f).read_bytes()).hexdigest()
assert {one(x,'number')[1] for x in ch(unit,'pin')}=={x[1] for x in ch(fp,'pad')}==set(map(str,range(1,11)))
report={'manufacturer':'TE Connectivity','part':'2452796-1','drawing':'C-2452796 Rev C','symbol':symname,'footprint':fpname,'pins':{one(x,'number')[1]:one(x,'name')[1] for x in ch(unit,'pin')},'pads':[{'number':x[1],'at':one(x,'at')[1:],'size':one(x,'size')[1:]} for x in ch(fp,'pad')],'keepout_count':len(keepouts),'unrelated_schematic_unchanged':True,'root_schematic_and_pcb_byte_unchanged':True,'before_sha256':before}
(P/'output/TE_2452796-1_verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print('Replaced one SIM slot. Unrelated schematic elements and original PCB unchanged.')
