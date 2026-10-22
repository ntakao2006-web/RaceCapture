import json,re
from pathlib import Path
p=Path(__file__).parent
groups=[]
retry=json.loads((p/'network_retry.json').read_text())
responses=[]
for x in retry['steps']:
 if x['command'].startswith('AT+CARECV='):
  m=re.search(r'\+CARECV:\s*(\d+),',x['response'])
  if m and 'HTTP/1.' in x['response']:responses.append(int(m[1]))
groups.append({'run':'manual TCP retry','requests':len(responses),'rx_http_bytes':sum(responses)})
for fn,key in [('transport.json','attempts'),('can_sd_third.json','lte'),('can_sd.json','lte')]:
 data=json.loads((p/fn).read_text());res=[v for t in data[key] for v in t.get('responses',[])]
 groups.append({'run':fn,'requests':len(res),'rx_http_bytes':sum(len(x.encode('ascii')) for x in res)})
count=sum(x['requests'] for x in groups);rx=sum(x['rx_http_bytes'] for x in groups)
report={'groups':groups,'head_requests':count,'tx_http_bytes':count*62,'rx_http_bytes':rx,'application_total_bytes':count*62+rx,'scope':'HTTP application payload only; excludes DNS, TCP/IP headers, retransmissions, carrier accounting, and any unlogged traffic. No HTTP bodies or sensor telemetry transmitted.'}
(p/'traffic.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
