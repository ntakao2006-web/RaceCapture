from pathlib import Path
import json,csv,hashlib
import sexpdata as sx
import pymupdf as fitz
P=Path(__file__).resolve().parents[1];B=P/'logger_v2-backups/before_direct_uart_parts_20260921'
def ch(a,k):return [x for x in a if isinstance(x,list) and x and str(x[0])==k]
def one(a,k):return ch(a,k)[0]
def pr(a,k):return next((x[2] for x in ch(a,'property') if x[1]==k),'')
def read(p):return sx.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report=json.loads((P/'output/parts_preparation_20260921.json').read_text(encoding='utf8'));removed={x['uuid'] for x in report['deleted']}
rows=[];models=set();counts={}
for name in ['logger_v2.kicad_sch','logger_v2_lte_sd.kicad_sch']:
    old=read(B/name);new=read(P/name);parts=ch(new,'symbol');byid={one(x,'uuid')[1]:x for x in parts};cache={x[1]:x for x in ch(one(new,'lib_symbols'),'symbol')}
    for x in ch(old,'symbol'):
        if one(x,'uuid')[1] not in removed:assert byid[one(x,'uuid')[1]]==x
    for k in ['wire','junction','label','global_label','hierarchical_label','sheet','no_connect']:assert ch(old,k)==ch(new,k)
    count=0
    for c in parts:
        if pr(c,'Reference').startswith('#'):continue
        sym=cache[one(c,'lib_id')[1]];pins={one(q,'number')[1] for unit in ch(sym,'symbol') for q in ch(unit,'pin')}
        assert pins=={q[1] for q in ch(c,'pin')},pr(c,'Reference')
        lib,fp=pr(c,'Footprint').split(':');f=read(P/(lib+'.pretty')/(fp+'.kicad_mod'))
        assert pins=={q[1] for q in ch(f,'pad') if q[1]},pr(c,'Reference')
        assert ch(f,'model')
        for m in ch(f,'model'):
            file=Path(m[1].replace('${KIPRJMOD}',str(P)));assert file.is_file() and file.read_bytes().lstrip().startswith(b'ISO-10303-21'),file;models.add(str(file))
        row={'Sheet':name,'Reference':pr(c,'Reference'),'UUID':one(c,'uuid')[1],'Value':pr(c,'Value'),'Footprint':pr(c,'Footprint'),'MPN':pr(c,'MPN'),'Role':pr(c,'Role'),'Supplier':pr(c,'Supplier'),'SupplierCode':pr(c,'SupplierCode'),'SupplierURL':pr(c,'SupplierURL'),'DNP':str(one(c,'dnp')[1])}
        rows.append(row);count+=1
    counts[name]=count
for name in ['logger_v2.kicad_sch','logger_v2.kicad_pcb','logger_v2.kicad_pro']:assert sha(P/name)==sha(B/name)
assert counts=={'logger_v2.kicad_sch':59,'logger_v2_lte_sd.kicad_sch':38}
with (P/'output/現在部品一覧_20260921.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
svg=fitz.open(P/'output/parts_preparation_svg/logger_v2_lte_sd.svg');doc=fitz.open('pdf',svg.convert_to_pdf());page=doc[0]
page.get_pixmap(matrix=fitz.Matrix(2,2)).save(P/'output/parts_preparation_20260921.png')
page.get_pixmap(matrix=fitz.Matrix(2.5,2.5),clip=fitz.Rect(0,160*72/25.4,420*72/25.4,290*72/25.4)).save(P/'output/parts_preparation_detail_20260921.png')
report.update({'counts':counts,'all_pins_match_pads':True,'model_files':sorted(models),'all_step_files_present':True,'existing_symbols_byte_structurally_preserved':True})
(P/'output/parts_preparation_20260921.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('Verified',sum(counts.values()),'parts,',len(models),'STEP files. Kept parts, wiring and root/PCB/project unchanged.')
