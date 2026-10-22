from gnss_service import Gnss,preflight,ubx
import pathlib,json,os,time,hashlib
OTP=[bytes.fromhex(s) for s in [
 'B5 62 06 41 10 00 03 00 04 1F 54 5E 79 BF 28 EF 12 05 FD FF FF FF 8F 0D',
 'B5 62 06 41 1C 00 04 01 A4 10 BD 34 F9 12 28 EF 12 05 05 00 A4 40 00 B0 71 0B 0A 00 A4 40 00 D8 B8 05 DE AE']]
EXPECTED='b562068b2400010400000100a44000b0710b0300a44000b0710b0500a44000b0710b0a00a44000d8b8057681'
g=Gnss();report=preflight(g);report['authorization']='User approved permanent high-performance clock on 2026-10-01';report['otp_transmissions']=0
for f in OTP:assert f==ubx(f[2],f[3],f[6:-2])
assert all(v in report['version_text'] for v in ['MOD=MAX-M10M','FWVER=SPG 5.10','PROTVER=34.10'])
assert len(bytes.fromhex(report['unique_id']))==18
if report.get('clock')==EXPECTED:
 report['already_high']=True
else:
 assert report.get('clock_nak')=='NAK:'+ubx(5,0,b'\x06\x8b').hex(),report
 journal=pathlib.Path('/data/bench-20261001/gnss_otp_attempt_'+report['unique_id']+'.jsonl')
 def log(f,row):f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
 with journal.open('x') as f:
  log(f,{'event':'preflight','report':report,'sequence_sha256':hashlib.sha256(b''.join(OTP)).hexdigest()})
  try:
   for i,frame in enumerate(OTP):
    log(f,{'event':'about_to_send','index':i,'hex':frame.hex()});g.drain();g.frames=[];g.send(frame);report['otp_transmissions']+=1
    ack=g.wait(5,1,ack=b'\x06\x41');log(f,{'event':'ack','index':i,'hex':ack.hex()})
   time.sleep(.3);g.c.command('RESETG');time.sleep(1)
   after=preflight(g);report['after']=after;report['verified_after_reset']=after.get('clock')==EXPECTED;log(f,{'event':'readback','report':report})
   assert report['verified_after_reset'],'Uncertain clock result: NEVER repeat OTP'
  except BaseException as e:report['error']=str(e);log(f,{'event':'error','report':report});raise
  finally:pathlib.Path('/data/bench-20261001/gnss_clock_apply.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2),flush=True)
