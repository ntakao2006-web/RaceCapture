"""Sensor-only Podium NDJSON. No CAN frames, files, camera or replay queue.

Two destinations: straight to Podium (plain TCP, key on the logger), or via the
team's ecorun-logger-server, which owns the Podium session and key; the logger
then sends batched Podium rows over that server's /ws/audio/{room} WebSocket.
"""
import asyncio
import base64
import hashlib
import json
import math
import os
import re
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from models import CHANNELS, LAP_CHANNELS

DEFAULT_CHANNELS = ['Lat','Lon','Altitude','GPSSpeed','Yaw','GPSFix','GPSSats',
                    'AccelX','AccelY','AccelZ','GyroX','GyroY','GyroZ','Roll','Pitch']
RANGES = {'Lat':(-90,90),'Lon':(-180,180),'Altitude':(-500,9000),
          'GPSSpeed':(0,300),'Speed':(0,300),'Yaw':(0,360),'GPSFix':(0,5),
          'GPSSats':(0,64),'RPM':(0,10000),'Throttle':(0,100),'WaterTemp':(-40,150),
          'BatteryVolt':(0,20),'OilTemp':(-40,200),'LapCount':(0,10000),'CurrentLap':(0,10000),
          'LapTime':(0,60),'BestLap':(0,60),'ElapsedTime':(0,60),
          'RaceTime':(0,600),'LapsLeft':(0,1000)}

# wss://host[:port]/ws/audio/<room>. The character set also keeps the host safe
# inside AT command quotes.
SERVER_URL = re.compile(r'(wss?)://([A-Za-z0-9][A-Za-z0-9.-]{0,252})(?::(\d{1,5}))?(/[A-Za-z0-9._~/%-]{1,200})')

def parse_server_url(url):
    scheme,host,port,path=SERVER_URL.fullmatch(url).groups()
    tls=scheme=='wss'
    return tls,host,int(port) if port else 443 if tls else 80,path

class PodiumConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    # 'lte': SIM7070 via STM32. 'wifi': the UNO Q's own Linux network (bench tests).
    # 'auto': Wi-Fi while the UNO Q has it (pit, tethering), otherwise LTE. On
    # track the car is out of Wi-Fi range, so a forgotten Wi-Fi setting can no
    # longer leave the stream silent.
    link: Literal['lte','wifi','auto'] = 'lte'
    # 'podium': direct TCP to Podium. 'server': ecorun-logger-server relays to Podium.
    destination: Literal['podium','server'] = 'podium'
    server_url: str = Field(default='', max_length=300)
    # Relay failover: tried in order after server_url when a relay cannot be
    # reached, drops, or stops answering pings. The last resort can be Podium
    # itself (needs the key on the logger).
    backup_server_urls: list[str] = Field(default_factory=list, max_length=3)
    fallback_direct: bool = False
    hardware_ready: bool = False
    host: str = Field(default='telemetry.podium.live', pattern=r'^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$')
    port: int = Field(default=8080, ge=1, le=65535)
    apn: str = Field(default='', pattern=r'^[A-Za-z0-9._-]{0,100}$')
    username: str = Field(default='', max_length=64)
    password: str = Field(default='', max_length=64, repr=False)
    device_id: str = Field(default='', max_length=128, repr=False)
    channels: list[str] = Field(default_factory=lambda:list(DEFAULT_CHANNELS), min_length=1, max_length=90)

    @model_validator(mode='after')
    def valid(self):
        if self.host != 'telemetry.podium.live' or self.port != 8080:
            raise ValueError('LTE is restricted to the Podium telemetry endpoint')
        if len(set(self.channels))!=len(self.channels):raise ValueError('Duplicate channels')
        if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,31}',n) for n in self.channels):raise ValueError('ASCII names required')
        for s in (self.username,self.password):
            if any(ord(c)<32 or ord(c)>126 or c in '"\\' for c in s):raise ValueError('Invalid AT credentials')
        if any(ord(c)<33 or ord(c)>126 for c in self.device_id):raise ValueError('Invalid key')
        if self.server_url and not SERVER_URL.fullmatch(self.server_url):raise ValueError('Invalid relay server URL')
        if any(not SERVER_URL.fullmatch(u) for u in self.backup_server_urls):raise ValueError('Invalid backup relay server URL')
        if self.fallback_direct and not self.device_id:raise ValueError('Key required for direct fallback')
        if self.enabled and self.destination=='podium' and not self.device_id:raise ValueError('Key required')
        if self.enabled and self.destination=='server' and not self.server_url:raise ValueError('Relay server URL required')
        if self.enabled and self.link!='wifi' and not (self.hardware_ready and self.apn):raise ValueError('SIM, antenna and APN required')
        return self

class ConfigStore:
    def __init__(self,root):
        self.path=Path(root)/'private'/'podium.json'
        self.error=None
        try:self.config=PodiumConfig.model_validate_json(self.path.read_text()) if self.path.exists() else PodiumConfig()
        except (ValueError,OSError):self.config=PodiumConfig();self.error='保存設定を読めません。送信はOFFです。'
        self.revision=0

    def public(self):
        data=self.config.model_dump(exclude={'password','device_id'})
        data.update(key_configured=bool(self.config.device_id),password_configured=bool(self.config.password),error=self.error)
        return data

    def update(self,body,allowed):
        data=dict(body)
        clear_key=data.pop('clear_key',False);clear_password=data.pop('clear_password',False)
        data={**self.config.model_dump(),**data}
        if not data.get('device_id'):data['device_id']=self.config.device_id
        if not data.get('password'):data['password']=self.config.password
        if clear_key:data['device_id']=''
        if clear_password:data['password']=''
        config=PodiumConfig.model_validate(data)
        if not set(config.channels)<=set(allowed):raise ValueError('Unknown sensor')
        self.path.parent.mkdir(mode=0o700,exist_ok=True)
        os.chmod(self.path.parent,0o700)
        temp=self.path.with_suffix('.tmp')
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            os.fchmod(f.fileno(),0o600)
            json.dump(config.model_dump(),f,allow_nan=False);f.flush();os.fsync(f.fileno())
        temp.replace(self.path)
        self.config=config;self.revision+=1;self.error=None
        return self.public()

def line(data):
    return (json.dumps(data,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')

@dataclass(frozen=True)
class Sensor:
    name: str
    unit: str
    low: float
    high: float

def sensors(config,vehicle):
    custom={s.name:s.unit for s in vehicle.signals}
    result=[]
    for name in config.channels:
        if name not in CHANNELS and name not in custom and name not in LAP_CHANNELS:raise ValueError('Unknown sensor')
        unit=CHANNELS[name][1] if name in CHANNELS else LAP_CHANNELS[name][1] if name in LAP_CHANNELS else custom[name]
        unit=unit.replace('°','deg').replace('²','^2')
        unit=unit.encode('ascii','replace').decode('ascii')
        low,high=RANGES.get(name,(-1000,1000))
        result.append(Sensor(name,unit,low,high))
    # These wire channels provide Podium's position/speed/time context even
    # when the optional sensor selection does not include them.
    for name in ('Lat','Lon','Speed'):
        if name not in config.channels:
            low,high=RANGES[name]
            result.append(Sensor(name,'deg' if name in ('Lat','Lon') else 'km/h',low,high))
    # Lap channels (lap.py) are always offered; they are masked out until a line is set.
    for name,(_,unit) in LAP_CHANNELS.items():
        if name not in config.channels:
            low,high=RANGES[name];result.append(Sensor(name,unit,low,high))
    # The official RaceCapture app always leads with these two system channels
    # (hardware_share_20261004_podium.md, measured 2026-10-04).
    return [Sensor('Interval','ms',0,0),Sensor('Utc','ms',0,0)]+result

def utc_milliseconds(sample):
    # Only receiver-validated UTC; never substitute the PC/Linux wall clock.
    try:
        text=sample.get('gnss_utc')
        if not isinstance(text,str):return None
        stamp=datetime.fromisoformat(text.replace('Z','+00:00'))
        if stamp.tzinfo is None:return None
        itow=sample.get('gnss_itow_ms')
        fraction=itow%1000 if type(itow) is int else 0
        return int(stamp.timestamp())*1000+fraction
    except (ValueError,OverflowError):return None

PRECISION = {'Lat':6,'Lon':6,'Interval':0,'Utc':0,'RPM':0,'GPSFix':0,'GPSSats':0,
             'LapCount':0,'CurrentLap':0,'LapTime':4,'BestLap':4,'ElapsedTime':4,
             'RaceTime':4,'LapsLeft':0}

# Auth values confirmed against next-generation Podium on 2026-10-04: these are
# what the official RaceCapture app 2.19.0 sends. The older
# {'schemaVer':2,'auth':{...}} form is answered without 'lt'.
AUTH = {'apiVer':1.1,'device':'RC_APP (RCPMK3)','ver':'2.19.0 (2.16.1)','sn':'C3PROTO01'}

class Encoder:
    def __init__(self,channels,tick=0):self.channels=channels;self.tick=tick
    def auth(self,key):return line({'cmd':{'auth':{'deviceId':key,**AUTH}}})
    def meta_list(self):
        # Podium recognizes position by its canonical channel names, not our
        # local UI abbreviations. Values/mask ordering stays unchanged.
        names={'Lat':'Latitude','Lon':'Longitude'}
        return [{'nm':names.get(s.name,s.name),'ut':s.unit,'sr':10,'min':s.low,'max':s.high,
                 'prec':PRECISION.get(s.name,2)} for s in self.channels]
    def meta(self):return line({'s':{'meta':self.meta_list()}})
    def sample(self,sample):
        row=self.row(sample)
        if row is None:return None
        # 't' is echoed back by the server as 'lt' in auth/heartbeat replies.
        data=line({'s':{'d':row,'t':self.tick}});self.tick+=1
        return data
    def row(self,sample):
        """Podium 'd' array (values in meta order, then bitmasks), or None."""
        if not sample or sample.get('source')!='logger-v2-hardware' or sample.get('demo') is not False:return None
        values=[];masks=[0]*((len(self.channels)+31)//32)
        for i,ch in enumerate(self.channels):
            value=sample.get('values',{}).get(ch.name,sample.get('can_signals',{}).get(ch.name))
            if ch.name in LAP_CHANNELS:value=(sample.get('lap') or {}).get(ch.name)
            if ch.name=='Utc':value=utc_milliseconds(sample)
            if ch.name=='Interval':value=sample.get('mcu_ms')
            if ch.name=='Speed' and value is None:value=sample.get('values',{}).get('GPSSpeed')
            if type(value) in (int,float) and math.isfinite(value):
                # Podium shows 'prec' decimals anyway; dropping the rest shortens
                # the LTE stream, which is limited by bytes through the MCU RPC.
                prec=PRECISION.get(ch.name,2)
                values.append(int(round(value)) if prec==0 else round(value,prec));masks[i//32]|=1<<(i%32)
        return values+masks

class AuthenticationError(Exception):pass

async def authenticate(transport,timeout=20):
    deadline=time.monotonic()+timeout
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Podium auth response timeout')
        raw=await asyncio.wait_for(transport.readline(),remaining)
        try:response=json.loads(raw)
        except (ValueError,UnicodeError):continue
        if not isinstance(response,dict) or 'status' not in response:continue
        if response['status']!='ok':raise AuthenticationError()
        return response

class SocketTransport:
    """Plain TCP over the Linux network (Wi-Fi). Same NDJSON stream as the LTE path."""
    def __init__(self,connect_timeout=20,user_timeout_ms=None):
        self.reader=None;self.writer=None;self.phase='idle';self.operation='idle'
        self.connect_timeout=connect_timeout;self.user_timeout_ms=user_timeout_ms
    async def connect(self,config,endpoint=None):
        # endpoint=(host,port,tls) for the relay server; default is Podium itself.
        host,port,tls=endpoint or (config.host,config.port,False)
        self.phase='relay_connect' if endpoint else 'podium_tcp_connect';self.operation='connect'
        context=ssl.create_default_context() if tls else None
        try:self.reader,self.writer=await asyncio.wait_for(asyncio.open_connection(host,port,limit=4096,ssl=context,server_hostname=host if tls else None),self.connect_timeout)
        except (OSError,asyncio.TimeoutError):raise OSError('Socket open failed')
        # Linux aborts the connection when sent data stays unacknowledged this
        # long, so a Wi-Fi link that is still "associated" but no longer passes
        # data (weak signal leaving the pit) fails within seconds instead of
        # filling the kernel send buffer for minutes.
        sock=self.writer.get_extra_info('socket')
        if self.user_timeout_ms and sock is not None and hasattr(socket,'TCP_USER_TIMEOUT'):
            sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_USER_TIMEOUT,self.user_timeout_ms)
        self.phase='relay_handshake' if endpoint else 'podium_authentication'
    async def read_some(self,wait=.01):
        """Whatever has arrived (b'' if nothing within `wait`)."""
        self.operation='read'
        try:data=await asyncio.wait_for(self.reader.read(4096),wait)
        except asyncio.TimeoutError:return b''
        if not data:raise ConnectionError('Socket no longer connected')
        return data
    async def send(self,data):
        self.operation='send'
        self.writer.write(data)
        try:await asyncio.wait_for(self.writer.drain(),10)
        except (OSError,asyncio.TimeoutError):raise ConnectionError('Socket no longer connected')
    async def readline(self):
        self.operation='readline'
        try:raw=await asyncio.wait_for(self.reader.readline(),20)
        except asyncio.TimeoutError:raise TimeoutError('Podium auth response timeout')
        except ValueError:raise ValueError('Podium response too large')
        if not raw:raise ConnectionError('Socket no longer connected')
        return raw
    async def close(self):
        if self.writer:
            self.writer.close()
            with __import__('contextlib').suppress(Exception):await asyncio.wait_for(self.writer.wait_closed(),2)

class WebSocket:
    """Minimal RFC 6455 client over any byte transport (Linux socket or SIM7070).

    Kept dependency-free so the LTE path, where TLS runs inside the modem and
    bytes go through AT commands, uses exactly the same framing as Wi-Fi.
    """
    GUID=b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    MAX_PAYLOAD=65536
    def __init__(self,transport):self.transport=transport;self.buffer=bytearray();self.heard_at=time.monotonic()
    async def ping(self):await self.transport.send(self.frame(9,b'ecologger'))
    async def handshake(self,host,port,path,tls,timeout=20):
        key=base64.b64encode(os.urandom(16))
        default=443 if tls else 80
        authority=host if port==default else f'{host}:{port}'
        await self.transport.send((f'GET {path} HTTP/1.1\r\nHost: {authority}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key.decode()}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode('ascii'))
        deadline=time.monotonic()+timeout
        while b'\r\n\r\n' not in self.buffer:
            if time.monotonic()>deadline:raise TimeoutError('Relay handshake timeout')
            if len(self.buffer)>8192:raise ValueError('Relay handshake too large')
            self.buffer.extend(await self.transport.read_some())
        end=self.buffer.index(b'\r\n\r\n')+4
        head=bytes(self.buffer[:end]).decode('latin-1');del self.buffer[:end]
        if not re.match(r'HTTP/1\.1 101\b',head):raise ConnectionError('Relay refused WebSocket')
        accept=base64.b64encode(hashlib.sha1(key+self.GUID).digest()).decode()
        if not re.search(r'(?im)^sec-websocket-accept:\s*'+re.escape(accept)+r'\s*$',head):raise ConnectionError('Relay refused WebSocket')
    @staticmethod
    def frame(opcode,payload):
        # Client frames must be masked (RFC 6455 5.3).
        mask=os.urandom(4);n=len(payload)
        head=bytes([0x80|opcode])+(bytes([0x80|n]) if n<126 else bytes([0xfe])+n.to_bytes(2,'big') if n<65536 else bytes([0xff])+n.to_bytes(8,'big'))
        return head+mask+bytes(b^mask[i%4] for i,b in enumerate(payload))
    async def send_json(self,data):
        await self.transport.send(self.frame(1,json.dumps(data,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')))
    async def poll(self,wait=.01):
        """Text messages that have fully arrived. Answers pings, raises on close."""
        self.buffer.extend(await self.transport.read_some(wait))
        messages=[]
        while len(self.buffer)>=2:
            opcode=self.buffer[0]&0x0f;n=self.buffer[1]&0x7f;at=2
            if self.buffer[1]&0x80:raise ValueError('Relay sent a masked frame')
            if n==126:
                if len(self.buffer)<4:break
                n=int.from_bytes(self.buffer[2:4],'big');at=4
            elif n==127:
                if len(self.buffer)<10:break
                n=int.from_bytes(self.buffer[2:10],'big');at=10
            if n>self.MAX_PAYLOAD:raise ValueError('Relay frame too large')
            if len(self.buffer)<at+n:break
            payload=bytes(self.buffer[at:at+n]);del self.buffer[:at+n]
            self.heard_at=time.monotonic()
            if opcode==8:raise ConnectionError('Relay closed WebSocket')
            if opcode==9:await self.transport.send(self.frame(10,payload))
            elif opcode==1:messages.append(payload.decode('utf-8','replace'))
            # Binary (room voice) and pong frames are ignored.
        return messages

LINK_LABEL={'lte':'LTE','wifi':'Wi-Fi'}
# Automatic link: how often Wi-Fi is re-checked while streaming over it, how
# long Wi-Fi is skipped after it failed, and a short connect timeout so a
# hotspot without internet falls back to LTE quickly.
WIFI_CHECK_S=2.0
WIFI_SKIP_S=30.0
AUTO_WIFI_CONNECT_S=8
AUTO_WIFI_USER_TIMEOUT_MS=5000
# Wi-Fi state unreadable this many checks in a row counts as lost (LTE is always acceptable).
WIFI_UNKNOWN_LIMIT=2
EVENTS_MAX_BYTES=1_000_000
# Rows per WebSocket message to the relay: fewer AT+CASEND round trips on LTE.
RELAY_BATCH=5
# Polling the relay costs an AT+CARECV on LTE, so do it rarely there.
RELAY_POLL_S={'lte':2.0,'wifi':.2}
# Relay liveness: a WebSocket ping goes out this often and the relay must have
# sent something (pong, status) within the silent limit, or the link counts as
# dead and the next relay is tried. LTE polls rarely, so its limits are longer.
RELAY_PING_S={'lte':5.0,'wifi':3.0}
RELAY_SILENT_S={'lte':15.0,'wifi':8.0}
RELAY_STATE={'idle':'待機','waiting_meta':'定義待ち','connecting':'Podiumへ接続中','streaming':'Podiumへ送信中','error':'Podium接続エラー'}

TRANSPORT_LABEL={'lte':'SIM7070G TCP / STM32 UART','wifi':'Linux TCP (Wi-Fi)','auto':'自動（Wi-Fi／LTE）'}

class PodiumSender:
    def __init__(self,root,runtime):
        self.store=ConfigStore(root);self.runtime=runtime
        self.state={'state':'off','message':'Podium送信OFF','frames':0,'bytes':0,'reconnects':0,'skipped':0,'last_sent_age_ms':None}
        self.sent_at=0;self.blocked_revision=None
        self.active_link=None;self.watch_wifi=False;self.wifi_checked=0;self.wifi_skip_until=0;self.wifi_unknown=0
        self.session_frames=0
        # Relay failover: position in targets() and failures in a row without a frame sent.
        self.target_index=0;self.target_failures=0;self.active_target=None
        # Link changes and first/last frames with wall-clock times, to measure
        # how long the stream pauses when it moves from Wi-Fi to LTE.
        self.events_path=Path(root)/'podium-events.jsonl'

    def status(self):
        return {**self.state,'target_hz':10,'last_sent_age_ms':round((time.monotonic()-self.sent_at)*1000) if self.sent_at else None,
                'link':self.store.config.link,'active_link':self.active_link,'destination':self.store.config.destination,
                'transport':TRANSPORT_LABEL[self.active_link or self.store.config.link]+(' → 中継サーバー' if self.store.config.destination=='server' else ''),
                'configured':bool(self.store.config.server_url if self.store.config.destination=='server' else self.store.config.device_id),'enabled':self.store.config.enabled,
                'target':self.active_target}

    def targets(self,config):
        '''[(kind, url)] in failover order: ('server', url)..., then ('podium', None).'''
        if config.destination!='server':return [('podium',None)]
        result=[('server',u) for u in [config.server_url,*config.backup_server_urls] if u]
        if config.fallback_direct and config.device_id:result.append(('podium',None))
        return result

    def set_state(self,name,message):self.state.update(state=name,message=message)

    def event(self,kind,**fields):
        try:
            if self.events_path.exists() and self.events_path.stat().st_size>EVENTS_MAX_BYTES:
                self.events_path.replace(self.events_path.with_suffix('.jsonl.1'))
            with self.events_path.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'t':round(time.time(),3),'event':kind,**fields},ensure_ascii=False)+'\n')
        except OSError:pass

    def events(self,limit=100):
        try:lines=self.events_path.read_text(encoding='utf-8').splitlines()[-limit:]
        except OSError:return []
        result=[]
        for line in lines:
            try:result.append(json.loads(line))
            except ValueError:pass
        return result

    def sent(self,frames,size):
        self.state['frames']+=frames;self.state['bytes']+=size;self.sent_at=time.monotonic()
        if self.session_frames==0:self.event('first_frame',link=self.active_link)
        self.session_frames+=frames

    def sd_busy(self,config=None):
        # Only the LTE path shares the MCU RPC link with SD reads/copies ('auto' may become LTE).
        if config is not None and config.link=='wifi':return False
        # Timestamp-only directory edits are serialized by the bridge and do
        # not require disconnecting telemetry after every recording stop.
        return self.runtime.sd.status.get('active') and self.runtime.sd.status.get('operation')!='timestamp'

    async def wifi_connected(self):
        """True/False from the UNO Q's NetworkManager; None when unknown (no agent, bench)."""
        check=getattr(self.runtime,'wifi_connected',None)
        if check is None:return None
        try:return await check()
        except Exception:return None

    async def choose_link(self,config):
        if config.link!='auto':return config.link
        if time.monotonic()<self.wifi_skip_until:return 'lte'
        return 'lte' if await self.wifi_connected() is False else 'wifi'

    async def check_wifi(self):
        """In automatic mode, leave Wi-Fi as soon as it drops (the car went out on track)."""
        if not self.watch_wifi or time.monotonic()-self.wifi_checked<WIFI_CHECK_S:return
        self.wifi_checked=time.monotonic()
        up=await self.wifi_connected()
        if up is False:raise ConnectionError('Wi-Fi lost')
        self.wifi_unknown=0 if up else self.wifi_unknown+1
        if self.wifi_unknown>=WIFI_UNKNOWN_LIMIT:raise ConnectionError('Wi-Fi state unknown')

    async def session(self,transport,config,revision):
        encoder=Encoder(sensors(config,self.runtime.config))
        self.set_state('connecting',f'{LINK_LABEL[config.link]}でPodiumへ接続中')
        await transport.connect(config)
        self.set_state('authenticating','Podium認証中')
        await transport.send(encoder.auth(config.device_id))
        await authenticate(transport)
        await transport.send(encoder.meta())
        self.set_state('streaming','センサ値を送信中')
        fingerprint=[(c.name,c.unit,c.low,c.high) for c in encoder.channels]
        deadline=time.monotonic();last_seq=None
        while self.store.revision==revision:
            if self.sd_busy(config):
                raise ConnectionError('SD operation')
            await self.check_wifi()
            updated=sensors(config,self.runtime.config)
            current=[(c.name,c.unit,c.low,c.high) for c in updated]
            if current!=fingerprint:
                encoder=Encoder(updated,encoder.tick);await transport.send(encoder.meta());fingerprint=current
            now=time.monotonic();sample=self.runtime.sample
            fresh=sample is not None and now-self.runtime.received_at<.5
            payload=encoder.sample(sample) if fresh and sample['seq']!=last_seq else None
            # Next-generation Podium (2026-09) ignores a stream until it carries a
            # GPS-derived timestamp (Utc); show this instead of a silent blank screen.
            if fresh:
                if utc_milliseconds(sample) is None:self.set_state('waiting_gps','GPS測位待ち（測位するまでPodium画面には表示されません）')
                else:self.set_state('streaming','センサ値を送信中')
            if payload:
                await transport.send(payload)
                self.sent(1,len(payload));last_seq=sample['seq']
            else:self.state['skipped']+=1
            # Never build a backlog or burst historical samples after a slow send.
            deadline=max(deadline+.1,time.monotonic())
            await asyncio.sleep(max(0,deadline-time.monotonic()))

    async def relay_session(self,transport,config,revision):
        """Batched Podium rows to ecorun-logger-server, which talks to Podium."""
        tls,host,port,path=parse_server_url(config.server_url)
        self.set_state('connecting',f'{LINK_LABEL[config.link]}で中継サーバーへ接続中')
        await transport.connect(config,(host,port,tls))
        ws=WebSocket(transport)
        await ws.handshake(host,port,path,tls)
        transport.phase='relay_streaming'
        # No playable audio formats: the room's voice is not pushed down the metered LTE link.
        await ws.send_json({'type':'hello','client_id':'ecologger-v2','protocol':2,'audio_formats':[]})
        encoder=Encoder(sensors(config,self.runtime.config))
        await ws.send_json({'type':'podium.meta','meta':encoder.meta_list()})
        self.set_state('streaming','中継サーバーへ送信中')
        fingerprint=[(c.name,c.unit,c.low,c.high) for c in encoder.channels]
        deadline=time.monotonic();last_seq=None;rows=[];first_at=0;polled=pinged=ws.heard_at=time.monotonic()
        while self.store.revision==revision:
            if self.sd_busy(config):
                raise ConnectionError('SD operation')
            await self.check_wifi()
            updated=sensors(config,self.runtime.config)
            current=[(c.name,c.unit,c.low,c.high) for c in updated]
            if current!=fingerprint:
                rows=[];encoder=Encoder(updated);await ws.send_json({'type':'podium.meta','meta':encoder.meta_list()});fingerprint=current
            now=time.monotonic();sample=self.runtime.sample
            fresh=sample is not None and now-self.runtime.received_at<.5
            row=encoder.row(sample) if fresh and sample['seq']!=last_seq else None
            if fresh and utc_milliseconds(sample) is None:
                self.set_state('waiting_gps','GPS測位待ち（測位するまでPodium画面には表示されません）')
            if row is not None:
                if not rows:first_at=now
                rows.append(row);last_seq=sample['seq']
            else:self.state['skipped']+=1
            # A partial batch still goes out if samples stall, so nothing waits long.
            if len(rows)>=RELAY_BATCH or rows and now-first_at>=1:
                await ws.send_json({'type':'podium.samples','samples':rows})
                self.sent(len(rows),len(json.dumps(rows)));rows=[]
            if time.monotonic()-pinged>=RELAY_PING_S[config.link]:
                pinged=time.monotonic();await ws.ping()
            if time.monotonic()-polled>=RELAY_POLL_S[config.link]:
                polled=time.monotonic()
                for text in await ws.poll():self.relay_message(text,sample,fresh)
                if time.monotonic()-ws.heard_at>RELAY_SILENT_S[config.link]:raise ConnectionError('Relay not responding')
            deadline=max(deadline+.1,time.monotonic())
            await asyncio.sleep(max(0,deadline-time.monotonic()))

    def relay_message(self,text,sample,fresh):
        try:event=json.loads(text)
        except ValueError:return
        if not isinstance(event,dict):return
        if event.get('type')=='error' and str(event.get('code','')).startswith('podium_'):
            if event.get('code')=='podium_not_configured':raise ConnectionError('Relay has no Podium key')
            self.state['relay_error']=event.get('code')
        elif event.get('type')=='podium.status':
            state=event.get('state');self.state['relay_state']=state;self.state['relay_lt']=event.get('lt')
            if fresh and utc_milliseconds(sample) is None:return
            label=RELAY_STATE.get(state,str(state))
            self.set_state('streaming' if state=='streaming' else 'relay_'+str(state),f'中継サーバー経由：{label}'+(f'（Podium受信 {event["lt"]} 件目）' if isinstance(event.get('lt'),int) else ''))

    async def run(self):
        from sim7070 import SIM7070
        retry=0;seen_revision=-1
        while True:
            config=self.store.config;revision=self.store.revision
            if revision!=seen_revision:retry=0;seen_revision=revision;self.target_index=0;self.target_failures=0
            if not config.enabled:
                self.set_state('off','Podium送信OFF');await asyncio.sleep(.5);continue
            if self.blocked_revision==revision:
                self.set_state('auth_failed','認証失敗。送信キーを修正して保存してください。');await asyncio.sleep(.5);continue
            if not self.runtime.bridge or not self.runtime.status()['connected'] or self.sd_busy(config):
                self.set_state('waiting','MCU通信またはSD操作完了を待っています');await asyncio.sleep(.5);continue
            auto=config.link=='auto'
            link=await self.choose_link(config)
            self.active_link=link;self.watch_wifi=auto and link=='wifi';self.wifi_checked=time.monotonic();self.wifi_unknown=0
            self.session_frames=0;self.event('session_start',link=link,mode=config.link,destination=config.destination)
            targets=self.targets(config);kind,url=targets[self.target_index%len(targets)]
            self.active_target={'kind':kind,'host':parse_server_url(url)[1] if url else config.host,
                                'index':self.target_index%len(targets),'count':len(targets)}
            session_config=config.model_copy(update={'link':link,**({'server_url':url} if url else {})})
            transport=(SIM7070(self.runtime.bridge) if link=='lte' else
                       SocketTransport(AUTO_WIFI_CONNECT_S,AUTO_WIFI_USER_TIMEOUT_MS) if auto else SocketTransport())
            try:
                await (self.relay_session if kind=='server' else self.session)(transport,session_config,revision)
                retry=0
            except AuthenticationError:
                if config.destination=='podium':self.blocked_revision=revision
                else:self.target_index+=1;self.set_state('retry','Podiumへの直接送信の認証に失敗。中継サーバーへ戻ります。')
            except asyncio.CancelledError:raise
            except Exception as exc:
                # Modem responses / exceptions may contain key or carrier credentials.
                self.state['reconnects']+=1
                self.state['last_failure_stage']=transport.phase
                self.state['last_failure_type']=type(exc).__name__
                self.state['last_failure_operation']=getattr(transport,'operation','unknown')
                safe_reasons={'Modem rejected operation','Podium response too large','Modem response timeout',
                    'Cellular connection closed','LTE receive overflow',
                    'LTE UART transmit rejected','Socket open failed',
                    'Socket no longer connected','Network registration timeout',
                    'Podium auth response timeout','SD operation',
                    'Relay handshake timeout','Relay refused WebSocket','Relay closed WebSocket',
                    'Relay has no Podium key','Relay frame too large','Wi-Fi lost','Wi-Fi state unknown',
                    'Relay not responding'}
                self.state['last_failure_reason']=str(exc) if str(exc) in safe_reasons else 'Transport error'
                self.event('session_end',link=link,target=self.active_target['host'],reason=self.state['last_failure_reason'],frames=self.session_frames,
                           last_sent_age_s=round(time.monotonic()-self.sent_at,3) if self.sent_at else None)
                target='中継サーバー' if kind=='server' else 'Podium'
                if auto and link=='wifi':
                    # Straight over to LTE, no back-off: the stream must not pause on track.
                    self.wifi_skip_until=time.monotonic()+WIFI_SKIP_S
                    self.set_state('retry','Wi-Fiが使えないためLTEへ切り替えます')
                else:
                    # Next target straight away; back off only once every target failed in a row.
                    self.target_failures=0 if self.session_frames else self.target_failures+1
                    self.target_index+=1
                    if len(targets)>1 and self.target_failures<len(targets):
                        nxt=targets[self.target_index%len(targets)][0]
                        self.set_state('retry',f'{target}への送信が途切れたため、'+('Podiumへ直接' if nxt=='podium' else '次の中継サーバー')+'へ切り替えます')
                    else:
                        self.target_failures=0
                        self.set_state('retry',f'{LINK_LABEL[link]}または{target}への接続に失敗。再接続を待っています。')
                        retry=min(5,retry+1)
            finally:
                with __import__('contextlib').suppress(Exception):await transport.close()
            if retry:
                until=time.monotonic()+min(30,2**retry)
                while self.store.revision==revision and time.monotonic()<until:await asyncio.sleep(.2)
