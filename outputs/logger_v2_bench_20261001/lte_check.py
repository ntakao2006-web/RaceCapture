from service_client import Client
import time,json,pathlib,re
initial_baud=57600;host_ratio=1
c=Client();report={'tests':[],'hardware_condition':'TVS D3 removed after user reported rail resistance rose from 0.07 ohm to about 0.2 Mohm','radio_policy':'SIM/antenna absent; CFUN=0 requested immediately after first AT response'}
def drain(duration):
 end=time.monotonic()+duration;b=bytearray()
 while time.monotonic()<end:
  b.extend(c.receive(1));c.receive(0);time.sleep(.05)
 return b.decode(errors='replace')
def at(cmd,timeout=3):
 c.receive(1);c.command('T'+cmd);s='';end=time.monotonic()+timeout
 while time.monotonic()<end:
  s+=c.receive(1).decode(errors='replace');c.receive(0)
  if '\r\nOK\r\n' in s or '\r\nERROR\r\n' in s or '+CME ERROR:' in s:break
  time.sleep(.05)
 row={'command':cmd,'response':s,'state':c.state()};report['tests'].append(row);print(json.dumps(row),flush=True);return s
try:
 report['before']=c.state();c.command('B'+str(initial_baud));c.command('RTS0');report['power_on']=c.command('ON');report['boot_uart']=drain(3)
 s=at('AT')
 if 'OK' not in s:
  s=at('AT',5)
 if 'OK' not in s:raise RuntimeError('No AT acknowledgement at '+str(initial_baud))
 assert 'OK' in at('AT+CFUN=0')
 for cmd in ['ATE0','AT+CMEE=2','ATI','AT+GMM','AT+CGMR','AT+CFUN?','AT+CPIN?','AT+CBC','AT+IPR?','AT+IPR=?','AT+IFC?']:
  at(cmd)
 ipr=next(r['response'] for r in report['tests'] if r['command']=='AT+IPR?');m=re.search(r'\+IPR:\s*(\d+)',ipr)
 module_baud=int(m.group(1)) if m else 0
 if module_baud in [initial_baud,initial_baud*2]:host_ratio=module_baud//initial_baud
 report['baud_mapping']={'mcu_configured':initial_baud,'module_reported':module_baud,'inferred_ratio':host_ratio}
 # Module RTS input must hold outbound UART traffic while high.
 if 'OK' in at('AT+IFC=2,2'):
  c.command('RTS1');c.receive(1);c.command('TAT');held=drain(.6)
  c.command('RTS0');released=drain(.6)
  report['rts_hold']={'held_response':held,'released_response':released,'gated_as_expected':not held and 'OK' in released}
  at('AT+IFC=0,0')
 rates=next((r['response'] for r in report['tests'] if r['command']=='AT+IPR=?'),'')
 for baud in [921600,2000000]:
  if not re.search(r'(?<!\d)'+str(baud)+r'(?!\d)',rates):continue
  s=at(f'AT+IPR={baud}');assert 'OK' in s;c.command('B'+str(baud//host_ratio));replies=[at('AT',1.5) for _ in range(5)]
  report.setdefault('baud_tests',[]).append({'baud':baud,'ok':sum('OK' in r for r in replies),'attempts':len(replies)})
  assert all('OK' in r for r in replies),'High baud failed; modem baud may need recovery'
  at('AT+IPR='+str(module_baud or initial_baud));c.command('B'+str(initial_baud));assert 'OK' in at('AT')
 report['normal_powerdown']=at('AT+CPOWD=1',3);report['power_off']=c.command('OFF');report['off_uart']=drain(.5)
 c.command('ON');drain(3);report['second_boot_at']=at('AT');at('AT+CFUN=0');at('AT+CPOWD=1',3);c.command('OFF')
except Exception as e:
 report['error']=str(e);print('ERROR:',e,flush=True)
finally:
 try:report['left_off']=c.command('OFF')
 except Exception as e:report['poweroff_error']=str(e)
 p=pathlib.Path('/data/bench-20261001/lte_after_tvs_removal.json');p.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
