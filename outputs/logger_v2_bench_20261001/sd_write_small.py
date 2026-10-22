from service_client import Client
import pathlib,json,struct,hashlib
c=Client();base=pathlib.Path('/data/bench-20261001');sector=526344;original=(base/f'sd_scratch_sector_{sector}_backup.bin').read_bytes();report={}
def read():
 r=c.command('R'+str(sector));assert r['result'].startswith('data:');return bytes.fromhex(r['result'][5:])
def write(b):
 for offset in range(0,512,64):assert c.command('H'+str(offset)+':'+b[offset:offset+64].hex())['result']=='loaded'
 r=c.command('W'+str(sector));assert 'accepted=1 busy_done=1' in r['result'],r;return r['result']
try:
 report['init']=c.command('SD')['result'];assert 'ready=1' in report['init'];report['before_matches_backup']=read()==original
 if not report['before_matches_backup']:report['recovery_write']=write(original);assert read()==original
 pattern=b''.join(hashlib.sha256(b'Logger_V2 SD check 20261001'+struct.pack('<I',i)).digest() for i in range(16))
 report['test_write']=write(pattern);report['test_readback_matches']=read()==pattern;assert report['test_readback_matches']
finally:
 try:report['restore_write']=write(original);report['original_restored']=read()==original
 except Exception as e:report['restore_error']=str(e)
 (base/'sd_write_small.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
