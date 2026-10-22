from service_client import Client
import time,struct,json,pathlib,sys
def ubx(cls,id,p=b''):
 body=bytes([cls,id])+struct.pack('<H',len(p))+p;a=b=0
 for v in body:a=(a+v)&255;b=(b+a)&255
 return b'\xb5\x62'+body+bytes([a,b])
class Gnss:
 def __init__(self):self.c=Client();self.buf=bytearray();self.frames=[]
 def send(self,f):
  assert f==ubx(f[2],f[3],f[6:-2])
  r=self.c.command('G'+f.hex());assert r['result']=='GNSS sent',r
 def drain(self):
  self.buf.extend(self.c.receive(0))
  while True:
   i=self.buf.find(b'\xb5\x62')
   if i<0:
    self.buf=self.buf[-1:];return
   if i:del self.buf[:i]
   if len(self.buf)<6:return
   n=struct.unpack_from('<H',self.buf,4)[0]+8
   if n>4096:del self.buf[:2];continue
   if len(self.buf)<n:return
   f=bytes(self.buf[:n]);del self.buf[:n]
   if f==ubx(f[2],f[3],f[6:-2]):self.frames.append(f)
 def wait(self,cls,id,timeout=4,ack=None):
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   self.drain()
   for f in list(self.frames):
    if f[2:4]==bytes([cls,id]) and (ack is None or f[6:-2]==ack):self.frames.remove(f);return f
    if f[2:4]==b'\x05\x00' and (ack is None or f[6:-2]==ack):self.frames.remove(f);raise RuntimeError('NAK:'+f.hex())
   time.sleep(.04)
  raise TimeoutError(f'GNSS {cls:02x}/{id:02x} timeout')
 def poll(self,cls,id,p=b''):
  self.drain();self.frames=[];self.send(ubx(cls,id,p));return self.wait(cls,id)
def preflight(g):
 out={};out['mon_ver']=g.poll(10,4).hex();out['version_text']=g.poll(10,4)[6:-2].replace(b'\0',b' ').decode(errors='replace')
 out['unique_id']=g.poll(0x27,3).hex()
 q=b'\0\x04\0\0'+struct.pack('<4I',0x40a40001,0x40a40003,0x40a40005,0x40a4000a)
 try:out['clock']=g.poll(6,0x8b,q).hex()
 except RuntimeError as e:out['clock_nak']=str(e)
 return out
if __name__=='__main__':
 g=Gnss();out=preflight(g);print(json.dumps(out,indent=2),flush=True);pathlib.Path('/data/bench-20261001/gnss_clock_preflight.json').write_text(json.dumps(out,indent=2))
