from pathlib import Path
import re,json,sys
out=Path(__file__).resolve().parent;root=out.parents[1];project=root/'circuit/logger_v2_ups'
sys.path.insert(0,str(out.parent/'ups_revision_20261016'))
from inspect_design import blocks,props
old='Eaton_HVH1025-2R7106-R_D10_L25_P5_Horizontal'
name='Eaton_HVH1020-2R7705-R_D10_L20_P5_Horizontal'
fp='logger_v2_ups:'+name
sel=json.loads((out/'selection.json').read_text(encoding='utf8'));upd=sel['updates']
upd.update(Value='7F(2.7V)',MPN='HVH1020-2R7705-R',DigiKey='283-HVH1020-2R7705-R-ND',Stock_snapshot='4000',Rating='7F +/-20%; 2.7V; ESR DC max113mohm / 1kHz max75mohm; -40..70C; D10(+0.5) L20(+/-2) P5(+/-0.5)mm',Assembly='90deg lead forming; body setback 3mm; pin1 positive; nominal model; allow D10.5 L22 maximum')
for k in ['Supplier_URL','DigiKey_URL']:upd[k]='https://www.digikey.jp/ja/products/detail/eaton-electronics-division/HVH1020-2R7705-R/28140394'
def changegraphics(g):
    return re.sub(r'\((start|end) (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)\)',lambda m:f'({m[1]} {m[2]} '+{'28':'23','28.15':'23.15','30.25':'25.25'}.get(m[3],m[3])+')',g)
model='${KIPRJMOD}/logger_v2_ups.3dshapes/Eaton_HVH1020-2R7705-R_nominal.step'
for ext,kind in [('kicad_sch','symbol'),('kicad_pcb','footprint')]:
    p=project/('logger_v2_ups.'+ext);s=p.read_text(encoding='utf8')
    for a,z,b in reversed(list(blocks(s,kind))):
        if props(b).get('Reference') not in sel['refs']:continue
        for k,v in upd.items():
            pat=r'(\(property "'+re.escape(k)+r'" ")[^"\n]*(")'
            assert re.search(pat,b),k
            b=re.sub(pat,lambda m:m[1]+v+m[2],b,count=1)
        b=b.replace(old,name)
        if kind=='footprint':
            for ga,gz,g in reversed(list(blocks(b,'fp_line',2))):b=b[:ga]+changegraphics(g)+b[gz:]
            b=re.sub(r'\(descr "[^"\n]*"\)','(descr "Eaton HVH1020-2R7705-R; nominal D10 L20 P5; courtyard D10.5 L22 maximum; pin1 positive")',b)
            b=re.sub(r'(\(model ")[^"]+"',lambda m:m[1]+model+'"',b)
        s=s[:a]+b+s[z:]
    p.write_text(s,encoding='utf8',newline='\n')
lib=(project/'logger_v2_ups.pretty'/(old+'.kicad_mod')).read_text(encoding='utf8').replace(old,name).replace('HVH1025-2R7106-R','HVH1020-2R7705-R').replace('D10 L25','D10 L20').replace('D10.5 L27','D10.5 L22')
lib=changegraphics(lib)
lib=re.sub(r'(\(model ")[^"]+"',lambda m:m[1]+model+'"',lib)
lib=lib.replace('(at 2.5 30 0)','(at 2.5 27 0)').replace('(at 2.5 15.5 90)','(at 2.5 13 90)')
(project/'logger_v2_ups.pretty'/(name+'.kicad_mod')).write_text(lib,encoding='utf8')
sel.update(updates=upd,footprint=fp)
(out/'selection.json').write_text(json.dumps(sel,ensure_ascii=False,indent=2),encoding='utf8')
rows=json.loads((out/'bom_data.json').read_text(encoding='utf8'))
for r in rows:
    if r['MPN']=='HVH1025-2R7106-R':
        r.update(Value=upd['Value'],MPN=upd['MPN'],Footprint=fp,Supplier_Part_Number=upd['DigiKey'],Rating=upd['Rating'],Stock=4000,URL=upd['DigiKey_URL'],Stock_Source=upd['DigiKey_URL'],Notes='価格優先で7F採用。旧10F比で公称エネルギー70%。横置き・90度リード曲げ、実機保持時間未検証。')
(out/'bom_data.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print('Selected 7F, 12pcs x JPY137.8 ex tax = JPY1818.96 incl10% tax, excluding freight.')
