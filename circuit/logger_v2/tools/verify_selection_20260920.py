from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET
import sexpdata as sx
import pymupdf as fitz
P=Path(__file__).resolve().parents[1]
B=P/'logger_v2-backups/before_akizuki_selection_20260920'
def ch(a,k):return [x for x in a if isinstance(x,list) and x and str(x[0])==k]
def one(a,k):return ch(a,k)[0]
def prop(a,k):return next(x for x in ch(a,'property') if x[1]==k)[2]
def read(f):return sx.loads(f.read_text(encoding='utf8'))
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
result={'sheets':{},'pcb_byte_unchanged':sha(P/'logger_v2.kicad_pcb')==sha(B/'logger_v2.kicad_pcb')}
assert result['pcb_byte_unchanged']
for name in ['logger_v2.kicad_sch','logger_v2_lte_sd.kicad_sch']:
    old=read(B/name);new=read(P/name)
    for k in ['wire','junction','label','global_label','hierarchical_label','no_connect','sheet','text']:assert ch(old,k)==ch(new,k),(name,k)
    a={one(x,'uuid')[1]:x for x in ch(old,'symbol')};b={one(x,'uuid')[1]:x for x in ch(new,'symbol')};assert a.keys()==b.keys()
    for uid,x in a.items():
        for k in ['at','dnp','unit','instances','in_bom','on_board']:assert ch(x,k)==ch(b[uid],k),(uid,k)
    lib={x[1]:x for x in ch(one(new,'lib_symbols'),'symbol')}
    count=0;fps=set();models=set()
    for x in ch(new,'symbol'):
        if prop(x,'Reference').startswith('#'):continue
        symbol=lib[one(x,'lib_id')[1]]
        pins={one(q,'number')[1] for s in ch(symbol,'symbol') for q in ch(s,'pin')}
        assert pins=={q[1] for q in ch(x,'pin')},prop(x,'Reference')
        lname,fname=prop(x,'Footprint').split(':');file=P/(lname+'.pretty')/(fname+'.kicad_mod');f=read(file)
        pads={q[1] for q in ch(f,'pad') if q[1]}
        assert pins==pads,(prop(x,'Reference'),pins,pads)
        assert ch(f,'model'),file
        for m in ch(f,'model'):
            model=Path(m[1].replace('${KIPRJMOD}',str(P)));assert model.is_file(),model
            assert model.read_bytes().lstrip().startswith(b'ISO-10303-21'),('Not STEP geometry',model)
            models.add(str(model))
        count+=1;fps.add(str(file))
    result['sheets'][name]={'parts':count,'unique_footprints':len(fps),'unique_models':len(models),'pin_pad_match':True,'models_resolve':True,'placement_and_wiring_unchanged':True}
def violations(file):
    d=json.loads(file.read_text(encoding='utf8'));return [(s['path'],s['violations']) for s in d['sheets']]
assert violations(P/'output/selection_erc_before.json')==violations(P/'output/selection_erc_after.json')
result['erc']='Unchanged: one existing root STATUS_LATCH dangling label; child remains separate unconnected schematic'
def partition(file):
    return {frozenset((q.attrib['ref'],q.attrib['pin']) for q in net.findall('node')) for net in ET.parse(file).getroot().find('nets')}
assert partition(P/'output/v2_compare_20260920.xml')==partition(P/'output/selection_after.xml')
result['root_all_net_partitions_unchanged']=True
for directory,filename in [('selection_svg','logger_v2'),('selection_child_svg','logger_v2_lte_sd')]:
    svg=fitz.open(P/'output'/directory/(filename+'.svg'));pdf=fitz.open('pdf',svg.convert_to_pdf());page=pdf[0]
    page.get_pixmap(matrix=fitz.Matrix(2,2)).save(P/'output'/(filename+'_selection.png'))
    if filename=='logger_v2':
        for label,box in [('gnss',(110,15,230,90)),('led',(225,130,335,230))]:
            page.get_pixmap(matrix=fitz.Matrix(3,3),clip=fitz.Rect(*[v*72/25.4 for v in box])).save(P/'output'/('selection_'+label+'.png'))
(P/'output/selection_final_verification.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result,indent=2))
