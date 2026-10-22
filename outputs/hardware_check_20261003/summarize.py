import json,struct,collections,hashlib
from pathlib import Path
p=Path(__file__).parent;r=json.loads((p/'can_sd.json').read_text())
tests=r['can'];states=[s for t in tests for s in t['states']];first=tests[0]['before'];last=tests[-1]['after']
nav=[bytes.fromhex(s['nav']) for s in states if s['nav']]
summary={
 'can':{'frames':sum(t['received'] for t in tests),'expected':1200*len(tests),'matched':sum(t['unique_matched'] for t in tests),'missing':sum(len(t['missing']) for t in tests),'bad':sum(len(t['bad']) for t in tests),'duplicates':sum(t['duplicates'] for t in tests),'rates':sorted(set(t['rate'] for t in tests)),'rounds':len(tests),'overflow_delta':[last['can_overflow'][i]-first['can_overflow'][i] for i in range(2)]},
 'duration_s':(last['mcu_ms']-first['mcu_ms'])/1000,
 'imu_hz':(last['seq']-first['seq'])/((last['mcu_ms']-first['mcu_ms'])/1000),
 'errors_delta':{k:last[k]-first[k] for k in ['imu_errors','gnss_errors','dropped','sd_errors','sd_queue_dropped','lte_overflows']},
 'gnss':{'fixes':sorted(set(n[20] for n in nav)),'valid_all':all(n[21]&1 for n in nav),'sats_min':min(n[23] for n in nav),'sats_max':max(n[23] for n in nav),'hacc_min_m':min(struct.unpack_from('<I',n,40)[0]/1000 for n in nav),'hacc_max_m':max(struct.unpack_from('<I',n,40)[0]/1000 for n in nav)},
 'sd_geometry':r['sd_geometry'],'sd_verified':r['sd_verified'],'sd_matches_live_can':r['sd_matches_live_can'],
 'lte':[{'attempt':t['attempt'],'passed':t.get('passed',False),'connect_seconds':t.get('connect_seconds'),'error':t.get('error'),'last_command':t.get('last_command'),'radio':t.get('radio'),'http_responses':len(t.get('responses',[]))} for t in r['lte']],
 'independent':{k:r['independent_after'][k]-r['independent_before'][k] for k in ['mcu_ms','seq','sd_blocks','sd_errors','sd_queue_dropped','dropped']},
}
(p/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
