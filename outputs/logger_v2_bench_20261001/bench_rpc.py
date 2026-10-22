import socket,json,sys,time,msgpack
method='bench.command' if len(sys.argv)>1 else 'bench.read'
params=[int(sys.argv[1],0)] if len(sys.argv)>1 else []
s=socket.socket(socket.AF_UNIX);s.settimeout(5);s.connect('/var/run/arduino-router.sock')
s.sendall(msgpack.packb([0,1,method,params]));u=msgpack.Unpacker(raw=False)
while True:
 b=s.recv(8192)
 if not b:raise RuntimeError('router disconnected')
 u.feed(b)
 for r in u:
  if r[0:2]==[1,1]:
   if r[2] is not None:raise RuntimeError(str(r[2]))
   print(r[3]);sys.exit(0)
