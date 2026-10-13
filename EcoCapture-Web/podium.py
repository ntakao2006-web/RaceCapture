"""Sensor-only Podium NDJSON. No CAN frames, files, camera or replay queue."""
import asyncio
import json
import math
import os
import re
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
          'BatteryVolt':(0,20),'LapCount':(0,10000),'CurrentLap':(0,10000),
          'LapTime':(0,60),'BestLap':(0,60),'ElapsedTime':(0,60)}

class PodiumConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    # 'lte': SIM7070 via STM32. 'wifi': the UNO Q's own Linux network (bench tests).
    link: Literal['lte','wifi'] = 'lte'
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
        if self.enabled and not self.device_id:raise ValueError('Key required')
        if self.enabled and self.link=='lte' and not (self.hardware_ready and self.apn):raise ValueError('SIM, antenna and APN required')
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
             'LapCount':0,'CurrentLap':0,'LapTime':4,'BestLap':4,'ElapsedTime':4}

# Auth values confirmed against next-generation Podium on 2026-10-04: these are
# what the official RaceCapture app 2.19.0 sends. The older
# {'schemaVer':2,'auth':{...}} form is answered without 'lt'.
AUTH = {'apiVer':1.1,'device':'RC_APP (RCPMK3)','ver':'2.19.0 (2.16.1)','sn':'C3PROTO01'}

class Encoder:
    def __init__(self,channels,tick=0):self.channels=channels;self.tick=tick
    def auth(self,key):return line({'cmd':{'auth':{'deviceId':key,**AUTH}}})
    def meta(self):
        # Podium recognizes position by its canonical channel names, not our
        # local UI abbreviations. Values/mask ordering stays unchanged.
        names={'Lat':'Latitude','Lon':'Longitude'}
        return line({'s':{'meta':[{'nm':names.get(s.name,s.name),'ut':s.unit,'sr':10,'min':s.low,'max':s.high,
                                   'prec':PRECISION.get(s.name,2)} for s in self.channels]}})
    def sample(self,sample):
        if not sample or sample.get('source')!='logger-v2-hardware' or sample.get('demo') is not False:return None
        values=[];masks=[0]*((len(self.channels)+31)//32)
        for i,ch in enumerate(self.channels):
            value=sample.get('values',{}).get(ch.name,sample.get('can_signals',{}).get(ch.name))
            if ch.name in LAP_CHANNELS:value=(sample.get('lap') or {}).get(ch.name)
            if ch.name=='Utc':value=utc_milliseconds(sample)
            if ch.name=='Interval':value=sample.get('mcu_ms')
            if ch.name=='Speed' and value is None:value=sample.get('values',{}).get('GPSSpeed')
            if type(value) in (int,float) and math.isfinite(value):
                values.append(round(value,6));masks[i//32]|=1<<(i%32)
        # 't' is echoed back by the server as 'lt' in auth/heartbeat replies.
        data=line({'s':{'d':values+masks,'t':self.tick}});self.tick+=1
        return data

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
    def __init__(self):self.reader=None;self.writer=None;self.phase='idle';self.operation='idle'
    async def connect(self,config):
        self.phase='podium_tcp_connect';self.operation='connect'
        try:self.reader,self.writer=await asyncio.wait_for(asyncio.open_connection(config.host,config.port,limit=4096),20)
        except (OSError,asyncio.TimeoutError):raise OSError('Socket open failed')
        self.phase='podium_authentication'
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

LINK_LABEL={'lte':'LTE','wifi':'Wi-Fi'}

class PodiumSender:
    def __init__(self,root,runtime):
        self.store=ConfigStore(root);self.runtime=runtime
        self.state={'state':'off','message':'Podium送信OFF','frames':0,'bytes':0,'reconnects':0,'skipped':0,'last_sent_age_ms':None}
        self.sent_at=0;self.blocked_revision=None

    def status(self):
        return {**self.state,'target_hz':10,'last_sent_age_ms':round((time.monotonic()-self.sent_at)*1000) if self.sent_at else None,
                'link':self.store.config.link,
                'transport':'SIM7070G TCP / STM32 UART' if self.store.config.link=='lte' else 'Linux TCP (Wi-Fi)','configured':bool(self.store.config.device_id),'enabled':self.store.config.enabled}

    def set_state(self,name,message):self.state.update(state=name,message=message)

    def sd_busy(self,config=None):
        # Only the LTE path shares the MCU RPC link with SD reads/copies.
        if config is not None and config.link!='lte':return False
        # Timestamp-only directory edits are serialized by the bridge and do
        # not require disconnecting telemetry after every recording stop.
        return self.runtime.sd.status.get('active') and self.runtime.sd.status.get('operation')!='timestamp'

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
            updated=sensors(config,self.runtime.config)
            current=[(c.name,c.unit,c.low,c.high) for c in updated]
            if current!=fingerprint:
                encoder=Encoder(updated,encoder.tick);await transport.send(encoder.meta());fingerprint=current
            now=time.monotonic();sample=self.runtime.sample
            fresh=sample is not None and now-self.runtime.received_at<.5
            payload=encoder.sample(sample) if fresh and sample['seq']!=last_seq else None
            if payload:
                await transport.send(payload)
                self.state['frames']+=1;self.state['bytes']+=len(payload);self.sent_at=time.monotonic();last_seq=sample['seq']
            else:self.state['skipped']+=1
            # Never build a backlog or burst historical samples after a slow send.
            deadline=max(deadline+.1,time.monotonic())
            await asyncio.sleep(max(0,deadline-time.monotonic()))

    async def run(self):
        from sim7070 import SIM7070
        retry=0;seen_revision=-1
        while True:
            config=self.store.config;revision=self.store.revision
            if revision!=seen_revision:retry=0;seen_revision=revision
            if not config.enabled:
                self.set_state('off','Podium送信OFF');await asyncio.sleep(.5);continue
            if self.blocked_revision==revision:
                self.set_state('auth_failed','認証失敗。送信キーを修正して保存してください。');await asyncio.sleep(.5);continue
            if not self.runtime.bridge or not self.runtime.status()['connected'] or self.sd_busy(config):
                self.set_state('waiting','MCU通信またはSD操作完了を待っています');await asyncio.sleep(.5);continue
            transport=SIM7070(self.runtime.bridge) if config.link=='lte' else SocketTransport()
            try:
                await self.session(transport,config,revision)
                retry=0
            except AuthenticationError:
                self.blocked_revision=revision
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
                    'Podium auth response timeout','SD operation'}
                self.state['last_failure_reason']=str(exc) if str(exc) in safe_reasons else 'Transport error'
                self.set_state('retry',f'{LINK_LABEL[config.link]}またはPodiumへの接続に失敗。再接続を待っています。')
                retry=min(5,retry+1)
            finally:
                with __import__('contextlib').suppress(Exception):await transport.close()
            if retry:
                until=time.monotonic()+min(30,2**retry)
                while self.store.revision==revision and time.monotonic()<until:await asyncio.sleep(.2)
