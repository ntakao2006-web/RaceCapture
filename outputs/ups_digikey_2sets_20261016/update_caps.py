from pathlib import Path
import sys,re,json,shutil
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'ups_revision_20261016'))
from inspect_design import blocks,props
out=Path(__file__).resolve().parent
root=out.parents[1]; project=root/'circuit/logger_v2_ups'
backup=out/'backup';backup.mkdir(exist_ok=True)
old='HP-2R7-J106UY_LR_D10_L25_P5_Horizontal'
name='Eaton_HVH1025-2R7106-R_D10_L25_P5_Horizontal'
fp='logger_v2_ups:'+name
url='https://www.digikey.jp/en/products/detail/eaton-electronics-division/HVH1025-2R7106-R/28140105'
ds='https://www.eaton.com/content/dam/eaton/products/electronic-components/resources/data-sheet/eaton-hvh-supercapacitors-cylindrical-cells-high-density-data-sheet-elx1538-en.pdf'
upd={'MPN':'HVH1025-2R7106-R','Manufacturer':'Eaton - Electronics Division','Supplier':'DigiKey','Supplier_URL':url,'DigiKey':'283-HVH1025-2R7106-R-ND','DigiKey_URL':url,'Datasheet':ds,'Description':'Polarized electric double layer capacitor','Rating':'10F +/-20%; 2.7V; ESR DC max90mohm / 1kHz max60mohm; -40..70C; D10(+0.5) L25(+/-2) P5(+/-0.5)mm','Assembly':'90deg lead forming; body setback 3mm; pin1 positive; nominal STEP reused, allow D10.5 L27 maximum','Stock_checked':'2026-10-16','Stock_snapshot':'168'}
refs={'C6','C7','C8','C12','C13','C14'}
def setprop(b,key,value,pcb):
    v=value.replace('\\','\\\\').replace('"','\\"')
    pat=r'(\(property "'+re.escape(key)+r'" ")((?:[^"\\]|\\.)*)(")'
    if re.search(pat,b):return re.sub(pat,lambda m:m[1]+v+m[3],b,count=1)
    xy=re.search(r'\(at ([\d.-]+) ([\d.-]+)',b)
    at='0 0 0' if pcb else f'{xy[1]} {xy[2]} 0'
    p=f'\n\t\t(property "{key}" "{v}" (at {at})'
    p+=' (layer "F.Fab") (hide yes) (effects (font (size 1 1) (thickness 0.15))))' if pcb else ' (effects (font (size 1.27 1.27)) (hide yes)))'
    return b[:-1]+p+'\n\t)'
def courtyard(b):
    return re.sub(r'\((start|end) (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)\)',lambda m:f'({m[1]} '+{'-2.8':'-3','7.8':'8'}.get(m[2],m[2])+' '+{'28.3':'30.25'}.get(m[3],m[3])+')',b)
sources={}
for ext in ['kicad_sch','kicad_pcb','net']:
    p=project/('logger_v2_ups.'+ext)
    assert not (backup/p.name).exists(),'Backup already exists'
    shutil.copy2(p,backup/p.name);sources[ext]=p.read_text(encoding='utf8')
for ext,kind in [('kicad_sch','symbol'),('kicad_pcb','footprint')]:
    s=sources[ext]
    for a,z,b in reversed(list(blocks(s,kind))):
        if props(b).get('Reference') not in refs:continue
        for k,v in upd.items():b=setprop(b,k,v,ext=='kicad_pcb')
        if ext=='kicad_sch':b=setprop(b,'Footprint',fp,False)
        else:
            b=b.replace('logger_v2_ups:'+old,fp)
            for ga,gz,g in reversed(list(blocks(b,'fp_line',2))):
                if '(layer "F.CrtYd")' in g:b=b[:ga]+courtyard(g)+b[gz:]
            b=re.sub(r'\(descr "[^"\n]*"\)','(descr "Eaton HVH1025-2R7106-R; nominal D10 L25 P5; courtyard includes D10.5 L27 maximum; pin1 positive")',b)
        s=s[:a]+b+s[z:]
    (project/('logger_v2_ups.'+ext)).write_text(s,encoding='utf8',newline='\n')
lib=(project/'logger_v2_ups.pretty'/(old+'.kicad_mod')).read_text(encoding='utf8')
lib=lib.replace('(footprint "'+old+'"','(footprint "'+name+'"').replace('(property "Value" "HP-2R7-J106UY LR"','(property "Value" "HVH1025-2R7106-R"')
lib=re.sub(r'\(descr "[^"\n]*"\)','(descr "Eaton HVH1025-2R7106-R; nominal D10 L25 P5; courtyard includes D10.5 L27 maximum; pin1 positive")',lib)
lib='\n'.join(courtyard(line) if '(layer "F.CrtYd")' in line else line for line in lib.split('\n'))
(project/'logger_v2_ups.pretty'/(name+'.kicad_mod')).write_text(lib,encoding='utf8')
rows=json.loads((out.parent/'ups_revision_20261016/bom_data.json').read_text(encoding='utf8'))
for r in rows:
    if r['MPN']=='HP-2R7-J106UY LR':
        r.update(Manufacturer=upd['Manufacturer'],MPN=upd['MPN'],Footprint=fp,Supplier='DigiKey',Supplier_Part_Number=upd['DigiKey'],Rating=upd['Rating'],Stock=168,Stock_Checked='2026-10-16',URL=url,Stock_Source=url,Notes='横置き・リード90度曲げ。容量下限8F（旧品9F）、実機保持時間未検証。公称STEP流用。')
    r['Required_2sets']=r['Quantity']*2
    r['Spare']=2 if r['References'].startswith(('R','Q')) or ('MLCC' in r['Rating']) else 0
    r['Order_Quantity']=r['Required_2sets']+r['Spare']
assert sum(r['Required_2sets'] for r in rows)==80
assert sum(r['Spare'] for r in rows)==38
assert all(r['Supplier']=='DigiKey' and r['Stock']>=r['Order_Quantity'] for r in rows)
(out/'bom_data.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
(out/'selection.json').write_text(json.dumps({'refs':sorted(refs),'updates':upd,'footprint':fp},ensure_ascii=False,indent=2),encoding='utf8')
print('Updated 6 capacitors; 27 BOM lines, required80 + spare38 =118.')
