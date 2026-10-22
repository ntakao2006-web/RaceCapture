from service_client import Client
import time,json,pathlib
c=Client();report={'tests':[],'external_uart':'USART1 PB6/PB7 verified from installed core device tree'}
def drain(seconds):
 b=bytearray();end=time.monotonic()+seconds
 while time.monotonic()<end:
  b.extend(c.receive(1));c.receive(0);time.sleep(.08)
 return b.hex()
try:
 c.command('OFF');time.sleep(2);c.command('B115200');c.command('RTS0');c.receive(1);report['on']=c.command('ON');report['boot_hex']=drain(10)
 for baud in [115200,9600,19200,38400,57600,230400,460800,921600,2000000]:
  c.command('B'+str(baud));drain(.2);c.command('TAT');rx=drain(1.2)
  row={'baud':baud,'rx_hex':rx,'state':c.state()};report['tests'].append(row);print(json.dumps(row),flush=True)
  if b'OK' in bytes.fromhex(rx):
   c.command('TAT+CFUN=0');report['cfun0_hex']=drain(2);break
 c.command('B115200');c.command('RTS1');c.command('TAT');report['rts_high_rx_hex']=drain(2)
finally:
 report['left_off']=c.command('OFF');c.command('RTS0');c.command('B115200')
 pathlib.Path('/data/bench-20261001/lte_baud_scan.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
