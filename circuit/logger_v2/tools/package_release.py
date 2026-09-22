"""Package only the verified Rev A sources and manufacture/review outputs."""
from pathlib import Path
import json,csv,shutil,zipfile,hashlib
P=Path(__file__).resolve().parents[1];O=P/'output/design_review_20260907';M=P/'manufacturing_20260907'
erc=json.loads((O/'reviewed_erc.json').read_text(encoding='utf8'))
drc=json.loads((O/'final_drc.json').read_text(encoding='utf8'))
audit=json.loads((O/'electrical_mechanical_audit.json').read_text(encoding='utf8'))
mfg=json.loads((O/'manufacturing_validation.json').read_text(encoding='utf8'))
assert not any(s['violations'] for s in erc['sheets'])
assert not drc['violations'] and not drc['unconnected_items'] and not drc['schematic_parity']
assert audit['mismatch_count']==0 and not mfg['issues']
board_hash=hashlib.sha256((P/'logger_v2.kicad_pcb').read_bytes()).hexdigest()
assert audit['board_sha256']==mfg['board_sha256']==board_hash
assert audit['schematic_sha256']==hashlib.sha256((P/'logger_v2.kicad_sch').read_bytes()).hexdigest()
V=M/'validation';V.mkdir(exist_ok=True)
for name in ['reviewed_erc.json','final_drc.json','electrical_mechanical_audit.json','manufacturing_validation.json','schematic_connectivity_validation.json','rf_impedance_estimate.json','cpl_rotation_geometry.json','jlc_hole_clearance_audit.json']:
    assert (O/name).exists(),name
    shutil.copy2(O/name,V/name)
for name in ['schematic_changes.md','rf_parts_review.md','parts_sourcing.csv','cpl_rotation_review.md']:
    assert (O/name).exists(),name
    shutil.copy2(O/name,M/name)
shutil.copy2(O/'reviewed_schematic.pdf',M/'Schematic.pdf')
shutil.copy2(P/'PCB_DESIGN_REVIEW_20260907.md',M/'README.md')
with zipfile.ZipFile(M/'Gerber_JLCPCB.zip','w',zipfile.ZIP_DEFLATED) as z:
    for path in sorted((M/'gerbers').iterdir()):
        if path.suffix in ['.gtl','.gbl','.gtp','.gto','.gbo','.gts','.gbs','.gm1','.gbrjob','.drl']:z.write(path,path.name)
source_files=[P/name for name in ['logger_v2.kicad_pro','logger_v2.kicad_sch','logger_v2.kicad_pcb','logger_v2.kicad_dru','logger_v2.net','fp-lib-table','sym-lib-table','logger_v1_custom.kicad_sym','logger_v2_custom.kicad_sym','mimi88_symbols.kicad_sym','PCB_DESIGN_REVIEW_20260907.md']]
for folder in ['logger_v2_custom.pretty','Arduino_MountingHole.pretty','3dmodels']:
    source_files.extend(path for path in (P/folder).rglob('*') if path.is_file())
with zipfile.ZipFile(M/'KiCad_RevA_Source.zip','w',zipfile.ZIP_DEFLATED) as z:
    for path in source_files:z.write(path,'logger_v2/'+path.relative_to(P).as_posix())
outputs=[path for path in M.rglob('*') if path.is_file() and path.name not in ['SHA256SUMS.txt','PCBA_Review_Package.zip']]
(M/'SHA256SUMS.txt').write_text('\n'.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(M).as_posix()}' for path in sorted(outputs))+'\n',encoding='utf8')
with zipfile.ZipFile(M/'PCBA_Review_Package.zip','w',zipfile.ZIP_DEFLATED) as z:
    for path in sorted([*outputs,M/'SHA256SUMS.txt']):z.write(path,path.relative_to(M).as_posix())
with zipfile.ZipFile(M/'Gerber_JLCPCB.zip') as z:
    assert z.testzip() is None and len(z.namelist())==11
with zipfile.ZipFile(M/'PCBA_Review_Package.zip') as z:assert z.testzip() is None
print(json.dumps({'board_sha256':board_hash,'pcba_parts':audit['pcba_components'],'gerber_zip':str(M/'Gerber_JLCPCB.zip'),'package':str(M/'PCBA_Review_Package.zip')},indent=2))
