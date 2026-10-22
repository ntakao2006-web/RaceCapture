"""Install the tested OilTemp decoder without flashing the logger MCU."""
import json
import pathlib
import subprocess
import urllib.request

root=pathlib.Path('/home/arduino/sensorhub-oiltemp-backup-20261019')
def run(*args): return subprocess.run(args,check=True,text=True,capture_output=True).stdout
def api(path,data=None):
    req=urllib.request.Request('http://127.0.0.1:8080'+path,
        data=None if data is None else json.dumps(data).encode(),
        headers={'Content-Type':'application/json','X-EcoCapture':'1'})
    with urllib.request.urlopen(req,timeout=45) as response:return json.load(response)

before=api('/api/status')
(root/'status-before-install.json').write_text(json.dumps(before,indent=2))
if before['logging']['active'] or before['hardware'].get('sd_logging'):
    api('/api/log/stop',{})
spec=json.loads(run('docker','inspect','ecocapture-web'))[0]
(root/'container-before.json').write_text(json.dumps(spec,indent=2))
config_path=pathlib.Path('/home/arduino/ecocapture-v2-data/config.json')
config=json.loads(config_path.read_text())
config['signals']=[s for s in config['signals'] if s['name']!='OilTemp']
config['signals'].append(dict(channel=2,name='OilTemp',unit='°C',can_id=0x600,
    extended=False,byte_offset=0,data_type='int16',endian='little',scale=.01,
    offset=0,bit_mask=None,conversion='sensorhub_oiltemp',pullup_ohm=None,ntc_points=[]))
(root/'config-after.json').write_text(json.dumps(config,ensure_ascii=False,indent=2))
# Validate the exact persisted configuration with the candidate image first.
run('docker','run','--rm','--network=none','--entrypoint','python3',
    '-v',str(root/'config-after.json')+':/candidate.json:ro',
    'ecocapture-web:oiltemp-20261019','-c',
    'from models import Configuration; Configuration.model_validate_json(open("/candidate.json").read())')
run('docker','stop','-t','15','ecocapture-web')
run('docker','rename','ecocapture-web','ecocapture-web-before-oiltemp-20261019')
temp=config_path.with_suffix('.oiltemp.tmp');temp.write_text(json.dumps(config,ensure_ascii=False,indent=2));temp.replace(config_path)
args=['docker','run','-d','--name','ecocapture-web','--restart','unless-stopped',
      '--user',spec['Config']['User'],'--cap-drop','ALL','--security-opt','no-new-privileges']
for mount in spec['Mounts']:
    assert mount['Type']=='bind',mount['Type']
    args+=['-v',mount['Source']+':'+mount['Destination']+('' if mount['RW'] else ':ro')]
for port,entries in spec['HostConfig']['PortBindings'].items():
    for entry in entries:args+=['-p',entry['HostIp']+':'+entry['HostPort']+':'+port]
for key,value in spec['HostConfig']['LogConfig'].get('Config',{}).items():args+=['--log-opt',key+'='+value]
args+=['ecocapture-web:oiltemp-20261019']
print(run(*args).strip())
run('docker','tag','ecocapture-web:oiltemp-20261019','ecocapture-web:0.2.0')
def root_run(*args):
    return run('docker','run','--rm','--privileged','--pid=host','--user','0',
        '--entrypoint','/usr/bin/nsenter','ecocapture-web:oiltemp-20261019',
        '-t','1','-m','-p','--',*args)
root_run('install','-m','755',str(root/'ecocapture-native.new'),'/opt/logger-v2-racecapture/ecocapture-native.next')
root_run('mv','/opt/logger-v2-racecapture/ecocapture-native.next','/opt/logger-v2-racecapture/ecocapture-native')
root_run('install','-m','644','/home/arduino/RaceCapture-UNOQ/rcp_bridge.py','/opt/logger-v2-racecapture/rcp_bridge.py')
root_run('systemctl','restart','logger-v2-rcp','ecocapture-native')
print('Installed OilTemp config, decoder, RCP metadata, and native display.')
