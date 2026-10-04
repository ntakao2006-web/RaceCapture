"""Explicit UNO Q driving-log cleanup. Run only while recording/services stopped."""
from pathlib import Path
import json,sqlite3

ROOT=Path('/home/arduino')
assert ROOT.resolve()==ROOT
targets=[]
for name in ('logs','demo-logs','sd-journals'):
    directory=ROOT/'ecocapture-v2-data'/name
    if directory.exists():
        assert directory.resolve().is_relative_to(ROOT/'ecocapture-v2-data')
        targets.extend(p for p in directory.rglob('*') if p.is_file())
for dirname in ('Downloads','recovery-20261004','hardware-check-20261003'):
    directory=ROOT/dirname
    if directory.exists():
        for p in directory.iterdir():
            if p.is_file() and (p.name.startswith('EL') and p.suffix.upper()=='.BIN'
                               or p.suffix=='.csv' or p.name.endswith('.csv.can.jsonl')
                               or p.name.endswith('-validation.jsonl')
                               or dirname=='hardware-check-20261003' and p.suffix=='.json'
                               or p.name in ('dashboard-recording.png','dashboard-stopped.png','podium-controls.png')):
                targets.append(p)
targets.append(ROOT/'ecocapture-v2-data/public/telemetry.json')
targets=[p for p in targets if p.exists()]
for p in targets:
    assert not p.is_symlink() and p.resolve().is_relative_to(ROOT)
print(json.dumps({'files':len(targets),'bytes':sum(p.stat().st_size for p in targets)}),flush=True)
for p in targets:p.unlink()
db=ROOT/'.config/racecapture/datastore.sq3'
with sqlite3.connect(db) as c:
    tables=('datapoint','sample','channel','lap','lap_aggregate','video_data','session')
    print({t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in tables},flush=True)
    for t in tables:c.execute('DELETE FROM '+t)
    c.commit();c.execute('VACUUM')
print('Driving-log cleanup complete; configuration, keys, source, firmware preserved.',flush=True)

# Avoid an independent, unbounded second recorder in the display-only app.
prefs=ROOT/'.config/racecapture/prefs.json'
settings=json.loads(prefs.read_text())
settings['general_prefs']['preferences']['record_session']='0'
temporary=prefs.with_suffix('.json.tmp')
temporary.write_text(json.dumps(settings,ensure_ascii=False,indent=2))
temporary.replace(prefs)
print('RaceCapture duplicate session recording disabled; LoggerV2 SD recording is unaffected.')
