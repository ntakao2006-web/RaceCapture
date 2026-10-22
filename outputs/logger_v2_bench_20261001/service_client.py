import socket,time,json,msgpack,sys
class Client:
 def __init__(self):
  self.s=socket.socket(socket.AF_UNIX);self.s.settimeout(15);self.s.connect('/var/run/arduino-router.sock');self.u=msgpack.Unpacker(raw=False,max_buffer_size=200000);self.seq=0
 def rpc(self,method,*params):
  self.seq+=1;self.s.sendall(msgpack.packb([0,self.seq,method,list(params)]))
  while True:
   b=self.s.recv(32768)
   if not b:raise RuntimeError('router disconnected')
   self.u.feed(b)
   for r in self.u:
    if r[0:2]==[1,self.seq]:
     if r[2] is not None:raise RuntimeError(str(r[2]))
     return r[3]
 def state(self):return json.loads(self.rpc('bench.read'))
 def command(self,text,timeout=30):
  before=self.state()['completed'];r=self.rpc('diag.tx',text)
  if r!=0:raise RuntimeError('service busy')
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   state=self.state()
   if state['completed']>before:return state
   time.sleep(.08)
  raise TimeoutError('command completion timeout')
 def receive(self,lane):return bytes.fromhex(self.rpc('diag.rx',lane))
if __name__=='__main__':
 c=Client()
 if len(sys.argv)>1:print(json.dumps(c.command(sys.argv[1]),ensure_ascii=False))
 else:print(json.dumps(c.state(),ensure_ascii=False));print('UART:',c.receive(1).decode(errors='replace'));print('GNSS:',c.receive(0).hex()[:100])
