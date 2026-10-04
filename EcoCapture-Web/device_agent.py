"""Small root-owned UNO Q helper. Unix socket only; no TCP listener, shell or arbitrary commands."""
import json
import os
import re
import shutil
import socket
import socketserver
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler
from pathlib import Path

SOCKET_DIR=Path('/run/ecocapture-admin')
STATE_DIR=Path('/var/lib/ecocapture-admin')
NM_DIR=Path('/etc/NetworkManager/system-connections')
network_lock=threading.Lock()


def command(args, timeout=12):
    result=subprocess.run(args, capture_output=True, text=True, timeout=timeout, env={**os.environ,'LC_ALL':'C'})
    if result.returncode:
        raise ValueError(result.stderr.strip() or 'Command failed')
    return result.stdout.strip()


def nm_fields(line):
    fields=[];value='';escaped=False
    for c in line:
        if escaped:value+=c;escaped=False
        elif c=='\\':escaped=True
        elif c==':':fields.append(value);value=''
        else:value+=c
    fields.append(value)
    return fields


def wifi_status():
    values={}
    output=command(['nmcli','-t','-f','GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS,IP4.GATEWAY','device','show','wlan0'])
    for line in output.splitlines():
        key,_,value=line.partition(':');values[key]=value
    addresses=[v.split('/')[0] for k,v in values.items() if k.startswith('IP4.ADDRESS')]
    return {'state':values.get('GENERAL.STATE','unknown'),'connection':values.get('GENERAL.CONNECTION',''),
            'addresses':addresses,'viewer_urls':[f'http://{ip}:8081/' for ip in addresses]}


def wifi_scan():
    if not network_lock.acquire(blocking=False):raise ValueError('Wi-Fi接続処理中です')
    try:
        command(['nmcli','radio','wifi','on'])
        out=command(['nmcli','-t','-e','yes','-f','IN-USE,SSID,SIGNAL,SECURITY','device','wifi','list','ifname','wlan0','--rescan','yes'],20)
        found={}
        for line in out.splitlines():
            fields=nm_fields(line)
            if len(fields)!=4 or not fields[1]:continue
            active,ssid,signal,security=fields
            entry={'ssid':ssid,'signal':int(signal or 0),'security':security,'connected':active=='*'}
            if ssid not in found or entry['signal']>found[ssid]['signal']:found[ssid]=entry
        return sorted(found.values(),key=lambda x:-x['signal'])
    finally:network_lock.release()


def keyfile_escape(value):
    return value.replace('\\','\\\\').replace('\n','\\n').replace('\r','\\r').replace('\t','\\t').replace(' ','\\s')


def wifi_connect(data):
    ssid=data.get('ssid','');password=data.get('password','');security=data.get('security','wpa-psk')
    if not isinstance(ssid,str) or not 1<=len(ssid.encode('utf-8'))<=32 or '\0' in ssid:raise ValueError('SSIDを確認してください')
    if security not in ('open','wpa-psk','sae'):raise ValueError('対応していないWi-Fi認証です')
    if not isinstance(password,str) or any(c in password for c in '\0\n\r'):raise ValueError('パスワードの形式を確認してください')
    if security!='open' and not (8<=len(password.encode('utf-8'))<=63 or re.fullmatch('[0-9A-Fa-f]{64}',password)):raise ValueError('Wi-Fiパスワードを確認してください')
    if not network_lock.acquire(blocking=False):raise ValueError('Wi-Fi処理中です')
    identity=str(uuid.uuid4());path=NM_DIR/f'EcoCapture-{identity}.nmconnection'
    try:
        command(['nmcli','radio','wifi','on'])
        # Password is never part of argv, an HTTP response, telemetry or application logs.
        text=f'[connection]\nid=EcoCapture-{identity[:8]}\nuuid={identity}\ntype=wifi\ninterface-name=wlan0\nautoconnect=true\n\n[wifi]\nmode=infrastructure\nssid='+''.join(f'{b};' for b in ssid.encode('utf-8'))+'\n'
        if security!='open':text+=f'\n[wifi-security]\nkey-mgmt={security}\npsk={keyfile_escape(password)}\n'
        text+='\n[ipv4]\nmethod=auto\n\n[ipv6]\nmethod=auto\n'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as stream:stream.write(text)
        command(['nmcli','connection','load',str(path)])
        command(['nmcli','--wait','35','connection','up','uuid',identity],42)
        return {'connected':True,'network':wifi_status()}
    except Exception:
        # Only remove the new profile owned by this attempt, never existing networks.
        subprocess.run(['nmcli','connection','delete','uuid',identity],capture_output=True,timeout=8)
        path.unlink(missing_ok=True)
        raise ValueError('接続できませんでした。SSID・パスワード・電波状態を確認してください。')
    finally:network_lock.release()


class Metrics:
    def __init__(self):self.last_cpu=None;self.last_process={};self.snapshot={};self.lock=threading.Lock();self.interested_until=0
    def sample(self):
        now=time.monotonic();raw=Path('/proc/stat').read_text().splitlines()[0].split()[1:9];cpu=[int(v) for v in raw];total=sum(cpu);idle=cpu[3]+cpu[4]
        usage=0 if self.last_cpu is None else 100*(1-(idle-self.last_cpu[1])/max(1,total-self.last_cpu[0]));self.last_cpu=(total,idle)
        mem={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
        ticks=os.sysconf('SC_CLK_TCK');page=os.sysconf('SC_PAGE_SIZE');current={};processes=[]
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():continue
            try:
                stat=(entry/'stat').read_text();start=stat.index('(');end=stat.rindex(')');parts=stat[end+2:].split();key=(int(entry.name),parts[19]);used=int(parts[11])+int(parts[12]);old=self.last_process.get(key);percent=100*(used-old[0])/ticks/max(.001,now-old[1]) if old else 0
                current[key]=(used,now);processes.append({'pid':key[0],'name':stat[start+1:end],'cpu_percent':round(percent,1),'rss_bytes':max(0,int(parts[21]))*page})
            except (OSError,ValueError,IndexError,ProcessLookupError):pass
        self.last_process=current
        temperatures=[]
        for p in Path('/sys/class/thermal').glob('thermal_zone*/temp'):
            try:temperatures.append(int(p.read_text())/1000)
            except (OSError,ValueError):pass
        disk=shutil.disk_usage('/home/arduino')
        result={'cpu_percent':round(max(0,min(100,usage)),1),'cpu_cores':os.cpu_count(),'memory_total':mem['MemTotal'],'memory_used':mem['MemTotal']-mem.get('MemAvailable',0),'swap_used':mem.get('SwapTotal',0)-mem.get('SwapFree',0),'uptime_s':float(Path('/proc/uptime').read_text().split()[0]),'load_average':list(os.getloadavg()),'temperature_c':max(temperatures) if temperatures else None,'disk_total':disk.total,'disk_free':disk.free,'process_count':len(processes),'processes':sorted(processes,key=lambda x:(-x['cpu_percent'],-x['rss_bytes']))[:15],'sampled_monotonic':now,'sample_interval_s':3}
        with self.lock:self.snapshot=result
    def loop(self):
        while True:
            try:
                if time.monotonic()<self.interested_until:self.sample()
            except Exception:pass
            time.sleep(3)
    def get(self):
        self.interested_until=time.monotonic()+10
        if not self.snapshot:self.sample()
        with self.lock:return dict(self.snapshot)


class Sharing:
    def __init__(self):
        self.process=None;self.url=None;self.lock=threading.RLock();self.next_retry=0
        self.file=STATE_DIR/'sharing.json';self.log=STATE_DIR/'tunnel.log'
        try:self.enabled=bool(json.loads(self.file.read_text()).get('enabled'))
        except (OSError,ValueError):self.enabled=False
    def set(self,enabled):
        with self.lock:
            self.enabled=enabled;self.file.write_text(json.dumps({'enabled':enabled}));self.file.chmod(0o600)
            if not enabled and self.process:
                self.process.terminate()
                try:self.process.wait(5)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
                self.process=None;self.url=None
            self.next_retry=0
        return self.status()
    def loop(self):
        while True:
            with self.lock:
                if self.enabled:
                    if (not self.process or self.process.poll() is not None) and time.monotonic()>self.next_retry:
                        self.url=None;self.next_retry=time.monotonic()+30
                        binary=Path('/opt/ecocapture-admin/cloudflared')
                        if binary.exists():
                            try:
                                with self.log.open('w') as stream:
                                    self.process=subprocess.Popen([str(binary),'tunnel','--no-autoupdate','--protocol','http2','--metrics','127.0.0.1:49312','--url','http://127.0.0.1:8081'],stdout=stream,stderr=subprocess.STDOUT,user=1000,group=1000,extra_groups=[],env={'PATH':'/usr/bin:/bin','HOME':'/home/arduino'},start_new_session=True)
                            except OSError:self.process=None
                    if self.process and self.process.poll() is None:
                        try:
                            with self.log.open('rb') as stream:
                                stream.seek(0,os.SEEK_END);size=stream.tell();stream.seek(max(0,size-32000))
                                tail=stream.read(32000).decode('utf-8',errors='replace')
                            match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',tail)
                            if match:self.url=match.group()
                        except OSError:pass
            time.sleep(3)
    def status(self):
        with self.lock:return {'enabled':self.enabled,'url':self.url if self.process and self.process.poll() is None else None,'running':bool(self.process and self.process.poll() is None),'temporary_url':True,'service':'Cloudflare Quick Tunnel'}


metrics=Metrics();sharing=None
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send_data(self,status,data):
        body=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        try:
            if self.path=='/system':result=metrics.get()
            elif self.path=='/wifi':result=wifi_status()
            elif self.path=='/sharing':result=sharing.status()
            else:self.send_data(404,{'detail':'Not found'});return
            self.send_data(200,result)
        except Exception:self.send_data(503,{'detail':'UNO Qの状態を取得できませんでした'})
    def do_POST(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=4096:raise ValueError('Invalid request size')
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError('Invalid request')
            if self.path=='/wifi/scan':result=wifi_scan()
            elif self.path=='/wifi/connect':result=wifi_connect(data)
            elif self.path=='/wifi/disconnect':
                with network_lock:command(['nmcli','device','disconnect','wlan0'])
                result=wifi_status()
            elif self.path=='/sharing':
                if type(data.get('enabled')) is not bool:raise ValueError('Invalid sharing setting')
                result=sharing.set(data['enabled'])
            else:self.send_data(404,{'detail':'Not found'});return
            self.send_data(200,result)
        except ValueError as exc:self.send_data(400,{'detail':str(exc)})
        except Exception:self.send_data(503,{'detail':'UNO Qの処理に失敗しました'})


if __name__=='__main__':
    class Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):daemon_threads=True
    SOCKET_DIR.mkdir(mode=0o750,exist_ok=True);os.chown(SOCKET_DIR,0,1000);SOCKET_DIR.chmod(0o750)
    STATE_DIR.mkdir(mode=0o700,exist_ok=True);sharing=Sharing()
    path=SOCKET_DIR/'agent.sock';path.unlink(missing_ok=True)
    threading.Thread(target=metrics.loop,daemon=True).start();threading.Thread(target=sharing.loop,daemon=True).start()
    with Server(str(path),Handler) as server:
        os.chown(path,0,1000);path.chmod(0o660);server.serve_forever()
