import socket,json,sys,time,msgpack,pathlib
duration=int(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.parent.mkdir(parents=True,exist_ok=True)
s=socket.socket(socket.AF_UNIX);s.settimeout(5);s.connect('/var/run/arduino-router.sock');u=msgpack.Unpacker(raw=False)
def rpc(method,params):
 rpc.seq+=1;s.sendall(msgpack.packb([0,rpc.seq,method,params]))
 while True:
  b=s.recv(8192)
  if not b:raise RuntimeError('router disconnected')
  u.feed(b)
  for r in u:
   if r[0:2]==[1,rpc.seq]:
    if r[2] is not None:raise RuntimeError(str(r[2]))
    return r[3]
rpc.seq=0
if len(sys.argv)>3:print(rpc('bench.command',[int(sys.argv[3])]),flush=True);time.sleep(.5)
start=time.monotonic();rows=[]
with out.open('w') as f:
 while time.monotonic()-start<duration:
  r=json.loads(rpc('bench.read',[]));r['host_elapsed_s']=round(time.monotonic()-start,3);rows.append(r);f.write(json.dumps(r)+'\n');f.flush();time.sleep(.2)
first,last=rows[0],rows[-1];keys=['mcu_ms','bytes','i2c_errors','nmea_ok','ubx_ok','nav_count','pps']
summary={'rows':len(rows),'elapsed_s':last['host_elapsed_s']-first['host_elapsed_s'],'delta':{k:last[k]-first[k] for k in keys},'fix_values':sorted(set(r['fix'] for r in rows)),'sats_min':min(r['sats'] for r in rows),'sats_max':max(r['sats'] for r in rows),'hacc_mm_min':min(r['hacc_mm'] for r in rows),'hacc_mm_max':max(r['hacc_mm'] for r in rows),'last':last}
out.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
