import socket,time,subprocess
s=socket.create_connection(('127.0.0.1',7500));s.settimeout(.5)
subprocess.run(['/opt/openocd/bin/arduino-reset.sh'])
end=time.monotonic()+12
while time.monotonic()<end:
 try:
  b=s.recv(8192)
  if b:print(b.decode(errors='replace'),end='',flush=True)
 except socket.timeout:pass
