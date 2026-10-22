import json,struct,sys
from pathlib import Path
eco=Path('/home/arduino/EcoCapture-Web')
if not eco.is_dir():eco=Path(__file__).resolve().parents[2]/'EcoCapture-Web'
sys.path.insert(0,str(eco))
from sd_decode import records
root=Path('/home/arduino/ecocapture-v2-data/bench-20261001/production')
if not root.is_dir():root=Path(__file__).resolve().parent/'production'
source=root/(sys.argv[1] if len(sys.argv)>1 else 'EL000026.BIN')
with source.open('rb') as f:nav=[data for kind,stamp,data in records(f) if kind==2]
itow=[struct.unpack_from('<I',n)[0] for n in nav];gaps=[(b-a)%604800000 for a,b in zip(itow,itow[1:])]
fix=[n[20]>=3 and bool(n[21]&1) for n in nav];sats=[n[23] for n in nav]
hz=(len(nav)-1)*1000/sum(gaps)
assert len(nav)>300 and all(99<=g<=101 for g in gaps) and 9.99<hz<10.01 and all(fix),(len(nav),set(gaps),sum(fix),hz)
from collections import Counter
report={'passed':True,'file':source.name,'records':len(nav),'nominal_period_ms':100,'period_ms_min':min(gaps),'period_ms_max':max(gaps),'period_counts':dict(Counter(gaps)),'recorded_hz':hz,'fix_3d_records':sum(fix),'used_satellites_min':min(sats),'used_satellites_max':max(sats),'antenna':'passive antenna outdoors','calibration':'deferred by user'}
(root/'gnss_outdoor_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
