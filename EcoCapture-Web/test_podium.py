import asyncio
import json
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import msgpack
import re
import base64
import hashlib
from podium import ConfigStore,Encoder,Sensor,PodiumConfig,PodiumSender,AuthenticationError,SocketTransport,WebSocket,sensors,authenticate,parse_server_url
from models import Configuration,CHANNELS
from sim7070 import SIM7070,LTEUART

class ProtocolTests(unittest.TestCase):
    def test_lte_destination_is_podium_only(self):
        for data in ({'host':'example.com'},{'port':443}):
            with self.assertRaises(ValueError):PodiumConfig(**data)
    def test_mask_multiple_words_missing_and_nonfinite(self):
        encoder=Encoder([Sensor('V'+str(i),'',0,100) for i in range(65)])
        sample={'source':'logger-v2-hardware','demo':False,'values':{'V0':1,'V31':31,'V32':32,'V64':64,'V5':float('nan'),'V7':None}}
        self.assertEqual(json.loads(encoder.sample(sample))['s']['d'],[1,31,32,64,0x80000001,1,1])
        sample['demo']=True;self.assertIsNone(encoder.sample(sample))
    def test_ascii_meta_order_and_no_private_fields(self):
        encoder=Encoder(sensors(PodiumConfig(),Configuration()))
        meta=json.loads(encoder.meta())['s']['meta']
        names={'Lat':'Latitude','Lon':'Longitude'}
        self.assertEqual([c['nm'] for c in meta],['Interval','Utc']+[names.get(n,n) for n in PodiumConfig().channels]+['Speed']+['LapCount','CurrentLap','LapTime','BestLap','ElapsedTime'])
        self.assertEqual(meta[2]['ut'],'deg');self.assertEqual(meta[2]['prec'],6)
        data={'source':'logger-v2-hardware','demo':False,'values':{'Lat':35},'password':'secret','imu_raw':'private','can_frames':['private']}
        self.assertNotIn('private',encoder.sample(data).decode())
        self.assertEqual(json.loads(encoder.auth('key')),{'cmd':{'auth':{'deviceId':'key','apiVer':1.1,'device':'RC_APP (RCPMK3)','ver':'2.19.0 (2.16.1)','sn':'C3PROTO01'}}})
    def test_empty_sample_sends_all_mask_words(self):
        encoder=Encoder([Sensor('V'+str(i),'',0,1) for i in range(65)])
        self.assertEqual(json.loads(encoder.sample({'source':'logger-v2-hardware','demo':False,'values':{}})),{'s':{'d':[0,0,0],'t':0}})
    def test_required_context_and_gnss_utc_milliseconds(self):
        encoder=Encoder(sensors(PodiumConfig(channels=['RPM']),Configuration()))
        self.assertEqual([c['nm'] for c in json.loads(encoder.meta())['s']['meta']],['Interval','Utc','RPM','Latitude','Longitude','Speed']+['LapCount','CurrentLap','LapTime','BestLap','ElapsedTime'])
        sample={'source':'logger-v2-hardware','demo':False,'values':{'Lat':35.123456789,'Lon':139.123456789,'GPSSpeed':12.5},'gnss_utc':'1970-01-01T00:00:01Z','gnss_itow_ms':1234}
        self.assertEqual(json.loads(encoder.sample(sample))['s']['d'],[1234,35.123457,139.123457,12.5,58])
        sample['gnss_utc']='bad';sample['values']={}
        self.assertEqual(json.loads(encoder.sample(sample))['s']['d'],[0])
    def test_lap_values_come_from_lap_timer(self):
        encoder=Encoder(sensors(PodiumConfig(channels=['GPSSats']),Configuration()))
        names=[c.name for c in encoder.channels]
        sample={'source':'logger-v2-hardware','demo':False,'values':{'LapCount':99},'lap':{'LapCount':3,'LapTime':1.5}}
        d=json.loads(encoder.sample(sample))['s']['d']
        self.assertEqual(d[:2],[3,1.5]);self.assertEqual(d[2],1<<names.index('LapCount')|1<<names.index('LapTime'))
        self.assertEqual(json.loads(encoder.meta())['s']['meta'][names.index('LapTime')]['ut'],'Min')
    def test_sample_counter_and_interval(self):
        encoder=Encoder([Sensor('Interval','ms',0,0),Sensor('V','',0,1)])
        first=json.loads(encoder.sample({'source':'logger-v2-hardware','demo':False,'mcu_ms':12300,'values':{'V':1}}))['s']
        self.assertEqual(first,{'d':[12300,1,3],'t':0})
        self.assertEqual(json.loads(encoder.sample({'source':'logger-v2-hardware','demo':False,'values':{}}))['s']['t'],1)
        self.assertEqual(Encoder(encoder.channels,encoder.tick).tick,2)
    def test_secrets_file_permissions_and_preserve_blank(self):
        with tempfile.TemporaryDirectory() as root:
            store=ConfigStore(root);store.update({'device_id':'private-key','password':'private-pass'},CHANNELS)
            self.assertNotIn('private-',json.dumps(store.public()))
            self.assertEqual(stat.S_IMODE(store.path.stat().st_mode),0o600)
            store.update({'enabled':False,'device_id':''},CHANNELS)
            self.assertEqual(ConfigStore(root).config.device_id,'private-key')
            store.update({'clear_key':True,'clear_password':True},CHANNELS)
            self.assertFalse(store.public()['key_configured'])
    def test_enable_requires_hardware_apn_and_key_and_rejects_injection(self):
        for data in ({'enabled':True},{'apn':'x"\rAT'},{'password':'x"\rAT'},{'channels':['Lat','Lat']}):
            with self.assertRaises(ValueError):PodiumConfig(**data)
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):ConfigStore(root).update({'channels':['Unknown']},CHANNELS)
    def test_wifi_enable_needs_only_key(self):
        self.assertTrue(PodiumConfig(link='wifi',enabled=True,device_id='k').enabled)
        for data in ({'link':'wifi','enabled':True},{'link':'lte','enabled':True,'device_id':'k'},{'link':'usb'}):
            with self.assertRaises(ValueError):PodiumConfig(**data)
    def test_saved_config_without_link_loads_as_lte(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'private'/'podium.json';path.parent.mkdir()
            path.write_text(json.dumps({k:v for k,v in PodiumConfig().model_dump().items() if k!='link'}))
            store=ConfigStore(root);self.assertIsNone(store.error);self.assertEqual(store.config.link,'lte')
    def test_relay_destination_needs_url_not_key(self):
        config=PodiumConfig(link='wifi',destination='server',server_url='wss://car.example.ts.net/ws/audio/main',enabled=True)
        self.assertEqual(parse_server_url(config.server_url),(True,'car.example.ts.net',443,'/ws/audio/main'))
        self.assertEqual(parse_server_url('ws://10.0.0.5:3000/ws/audio/x'),(False,'10.0.0.5',3000,'/ws/audio/x'))
        for url in ('https://h/ws','wss://h"x/ws','wss://h/ws a','wss://h',''):
            with self.assertRaises(ValueError):PodiumConfig(link='wifi',destination='server',server_url=url,enabled=True)
    def test_values_rounded_to_podium_precision(self):
        encoder=Encoder([Sensor('Lat','deg',-90,90),Sensor('RPM','rpm',0,1),Sensor('AccelX','G',0,1)])
        row=encoder.row({'source':'logger-v2-hardware','demo':False,'values':{'Lat':35.12345678,'RPM':812.6,'AccelX':0.123456}})
        self.assertEqual(row,[35.123457,813,0.12,7]);self.assertIs(type(row[1]),int)
    def test_rpc_chunk_fits_worst_message_id(self):
        self.assertLessEqual(len(msgpack.packb([0,0xffffffff,'logger.ltex',['ff'*18]])),64)

class FakeUART:
    """Length-delimited CASEND, asynchronous CAOPEN and fragmented CARECV data."""
    def __init__(self):
        self.incoming=bytearray();self.outgoing=bytearray();self.expected=0;self.messages=[];self.commands=[];self.powered=False;self.attach=0;self.network=bytearray();self.sim_queries=0
    async def power(self,on):self.powered=on
    async def read(self):
        # Arbitrary split boundaries, including auth JSON and trailing OK.
        n=min(len(self.outgoing),7);data=bytes(self.outgoing[:n]);del self.outgoing[:n];return data
    async def write(self,data):
        self.incoming.extend(data)
        while self.incoming:
            if self.expected:
                if len(self.incoming)<self.expected:return
                payload=bytes(self.incoming[:self.expected]);del self.incoming[:self.expected];self.expected=0
                self.messages.append(payload);self.outgoing.extend(b'\r\nOK\r\n')
                if b'"auth"' in payload:self.network.extend(b'{"status":"ok","utc":123}\n')
                continue
            if b'\r' not in self.incoming:return
            end=self.incoming.index(b'\r');command=self.incoming[:end].decode();del self.incoming[:end+1];self.commands.append(command)
            response=''
            if command.startswith('AT+CASEND='):
                self.expected=int(command.split(',')[1]);self.outgoing.extend(b'\r\n> ');continue
            if command=='AT+CPIN?':
                self.sim_queries+=1
                if self.sim_queries==1:
                    self.outgoing.extend(b'\r\nERROR\r\n');continue
                response='+CPIN: '+('NOT READY' if self.sim_queries==2 else 'READY')+'\r\n'
            if command in ('AT+CPSMS=0','AT+CEDRXS=0') and self.attach<2:
                self.outgoing.extend(b'\r\nERROR\r\n');continue
            if command=='AT+CGATT?':self.attach+=1;response=f'+CGATT: {int(self.attach>1)}\r\n'
            if command=='AT+CNACT?':response='+CNACT: 0,1,"10.1.2.3"\r\n'
            if command.startswith('AT+CAOPEN='):
                self.outgoing.extend(b'\r\nOK\r\n+CAOPEN: 0,0\r\n');continue
            if command.startswith('AT+CARECV='):
                n=min(11,len(self.network));payload=bytes(self.network[:n]);del self.network[:n]
                self.outgoing.extend(f'\r\n+CARECV: {n},'.encode()+payload+b'\r\nOK\r\n');continue
            if command=='AT+CASTATE?':response='+CASTATE: 0,1\r\n'
            self.outgoing.extend(('\r\n'+response+'OK\r\n').encode())

async def fake_relay(reader,writer,log,replies=()):
    """Accept one WebSocket client, record its JSON messages, send `replies`."""
    head=await reader.readuntil(b'\r\n\r\n')
    key=re.search(rb'(?im)^sec-websocket-key:\s*(\S+)',head)[1]
    log.append(head.split(b'\r\n')[0])
    accept=base64.b64encode(hashlib.sha1(key+WebSocket.GUID).digest())
    writer.write(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n')
    for reply in replies:writer.write(bytes([0x81,len(reply)])+reply)
    writer.write(bytes([0x89,2])+b'hi')
    await writer.drain()
    while True:
        try:b0,b1=await reader.readexactly(2)
        except asyncio.IncompleteReadError:return
        assert b1&0x80,'client frames must be masked'
        n=b1&0x7f
        if n==126:n=int.from_bytes(await reader.readexactly(2),'big')
        mask=await reader.readexactly(4);payload=bytes(b^mask[i%4] for i,b in enumerate(await reader.readexactly(n)))
        log.append((b0&0x0f,payload))

class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_relay_hello_meta_and_batched_samples_over_websocket(self):
        log=[];status=b'{"type":"podium.status","room_id":"main","state":"streaming","lt":4}'
        server=await asyncio.start_server(lambda r,w:fake_relay(r,w,log,[status]),'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
        class Runtime:
            config=Configuration();sample=None;received_at=0
            class sd:status={'active':False}
        with tempfile.TemporaryDirectory() as root:
            runtime=Runtime();sender=PodiumSender(root,runtime)
            config=PodiumConfig(link='wifi',destination='server',server_url=f'ws://127.0.0.1:{port}/ws/audio/main',enabled=True)
            async with server:
                task=asyncio.create_task(sender.relay_session(SocketTransport(),config,0))
                for seq in range(12):
                    runtime.sample={'source':'logger-v2-hardware','demo':False,'seq':seq,'mcu_ms':seq*100,'values':{'Lat':35.5,'AccelX':0.123456},
                                    'gnss_utc':'2026-10-14T00:00:00Z','gnss_itow_ms':seq*100}
                    runtime.received_at=time.monotonic();await asyncio.sleep(.1)
                sender.store.revision+=1;await task
                await asyncio.sleep(.1)
        self.assertEqual(log[0],b'GET /ws/audio/main HTTP/1.1')
        texts=[json.loads(p) for op,p in log[1:] if op==1]
        self.assertIn((10,b'hi'),log[1:])
        self.assertEqual(texts[0],{'type':'hello','client_id':'ecologger-v2','protocol':2,'audio_formats':[]})
        self.assertEqual(texts[1]['type'],'podium.meta');self.assertEqual(texts[1]['meta'][2]['nm'],'Latitude')
        batches=[t['samples'] for t in texts[2:]]
        self.assertTrue(batches and all(t['type']=='podium.samples' for t in texts[2:]))
        self.assertEqual(len(batches[0]),5)
        names=[m['nm'] for m in texts[1]['meta']]
        first=batches[0][0];self.assertEqual(first[2],35.5);self.assertEqual(first[1]-first[0],1791936000000)
        self.assertIn(0.12,batches[0][0])
        self.assertEqual(sender.state['relay_lt'],4);self.assertIn('Podium受信 4 件目',sender.state['message'])
    async def test_relay_without_podium_key_is_reported(self):
        log=[];err=b'{"type":"error","code":"podium_not_configured","message":"x"}'
        server=await asyncio.start_server(lambda r,w:fake_relay(r,w,log,[err]),'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
        class Runtime:
            config=Configuration();sample=None;received_at=0
            class sd:status={'active':False}
        with tempfile.TemporaryDirectory() as root:
            sender=PodiumSender(root,Runtime())
            config=PodiumConfig(link='wifi',destination='server',server_url=f'ws://127.0.0.1:{port}/ws/audio/main',enabled=True)
            async with server:
                with self.assertRaisesRegex(ConnectionError,'Relay has no Podium key'):
                    await asyncio.wait_for(sender.relay_session(SocketTransport(),config,0),5)
    async def test_lte_relay_enables_modem_tls_with_sni(self):
        uart=FakeUART();modem=SIM7070(uart=uart)
        config=PodiumConfig(apn='test.apn',hardware_ready=True)
        await modem.connect(config,('car.example.ts.net',443,True))
        self.assertIn('AT+CSSLCFG="SNI",0,"car.example.ts.net"',uart.commands)
        self.assertIn('AT+CASSLCFG=0,"SSL",1',uart.commands)
        self.assertEqual(uart.commands[-1],'AT+CAOPEN=0,0,"TCP","car.example.ts.net",443')
        uart.network.extend(b'abc');self.assertEqual(await modem.read_some(),b'abc')

    async def test_auth_ignores_unexpected_lines_before_ok(self):
        class Transport:
            replies=iter([b'notice\n',b'[]\n',b'{"message":"hello"}\n',b'{"status":"ok"}\n'])
            async def readline(self):return next(self.replies)
        self.assertEqual(await authenticate(Transport()),{'status':'ok'})
    async def test_auth_unexpected_lines_are_time_bounded(self):
        class Transport:
            async def readline(self):
                await asyncio.sleep(.01)
                return b'{}\n'
        with self.assertRaises(TimeoutError):await authenticate(Transport(),.04)
    async def test_full_modem_auth_meta_sample_and_shutdown(self):
        uart=FakeUART();modem=SIM7070(uart=uart)
        config=PodiumConfig(apn='test.apn',device_id='test-key',hardware_ready=True,enabled=True)
        await modem.connect(config)
        encoder=Encoder(sensors(config,Configuration()))
        await modem.send(encoder.auth(config.device_id))
        self.assertEqual(json.loads(await modem.readline())['status'],'ok')
        await modem.send(encoder.meta())
        await modem.send(encoder.sample({'source':'logger-v2-hardware','demo':False,'values':{'Lat':35,'AccelX':1}}))
        wire=b''.join(uart.messages).splitlines()
        self.assertIn('auth',json.loads(wire[0])['cmd']);self.assertIn('meta',json.loads(wire[1])['s'])
        self.assertEqual(json.loads(wire[2])['s']['d'],[35,1,516])
        self.assertLess(uart.commands.index('AT+CFUN=0'),uart.commands.index('AT+CFUN=1'))
        self.assertGreaterEqual(uart.sim_queries,2)
        self.assertLess(uart.commands.index('AT+CGATT?'),uart.commands.index('AT+CPSMS=0'))
        await modem.close();self.assertFalse(uart.powered)
    async def test_large_meta_splits_tcp_payload_without_extra_newlines(self):
        uart=FakeUART();modem=SIM7070(uart=uart)
        data=Encoder([Sensor('V'+str(i),'',0,1) for i in range(65)]).meta()
        await modem.send(data)
        self.assertGreater(len(uart.messages),1);self.assertEqual(b''.join(uart.messages),data)
    async def test_modem_error_and_closed_socket_abort(self):
        for reply in (b'\r\nERROR\r\n',b'\r\n+CASTATE: 0,0\r\n'):
            uart=FakeUART();uart.outgoing.extend(reply);modem=SIM7070(uart=uart)
            with self.assertRaises(OSError):await modem.wait(b'never',.5)
    async def test_uart_backpressure_and_overflow(self):
        class Bridge:
            def __init__(self):self.requests=[];self.reject=True;self.over=0
            async def call(self,method,args=None):
                if method=='logger.lter':return json.dumps({'overflows':self.over,'rx':'41'})
                self.requests.append(args[0])
                if self.reject:self.reject=False;return -1
                return 0
        bridge=Bridge();uart=LTEUART(bridge);await uart.write(bytes(range(50)))
        self.assertEqual(bytes.fromhex(''.join(bridge.requests[1:])),bytes(range(50)))
        self.assertEqual(await uart.read(),b'A');bridge.over=1
        with self.assertRaises(OSError):await uart.read()
    async def test_sender_auth_failure_never_sends_meta(self):
        class Runtime:
            config=Configuration()
        class Transport:
            def __init__(self):self.messages=[]
            async def connect(self,c):pass
            async def send(self,data):self.messages.append(data)
            async def readline(self):return b'{"status":"bad"}\n'
        with tempfile.TemporaryDirectory() as root:
            sender=PodiumSender(root,Runtime());transport=Transport()
            with self.assertRaises(AuthenticationError):await sender.session(transport,PodiumConfig(device_id='test'),0)
            self.assertEqual(len(transport.messages),1)
    async def test_sender_latest_only_stale_skip_and_ten_hz(self):
        class Runtime:
            config=Configuration();sample={'source':'logger-v2-hardware','demo':False,'seq':1,'values':{'AccelX':1}}
            received_at=time.monotonic()
            class sd:status={'active':False}
        class Transport:
            def __init__(self):self.messages=[];self.times=[]
            async def connect(self,c):pass
            async def readline(self):return b'{"status":"ok"}\n'
            async def send(self,data):
                self.messages.append(data)
                if 'd' in json.loads(data).get('s',{}):self.times.append(time.monotonic())
        with tempfile.TemporaryDirectory() as root:
            runtime=Runtime();sender=PodiumSender(root,runtime);transport=Transport()
            started=time.monotonic()
            task=asyncio.create_task(sender.session(transport,PodiumConfig(device_id='test'),0))
            for seq in range(100):
                runtime.sample={**runtime.sample,'seq':seq};runtime.received_at=time.monotonic();await asyncio.sleep(.01)
            duration=time.monotonic()-started
            runtime.received_at-=3;count=len(transport.times);await asyncio.sleep(.25)
            self.assertEqual(len(transport.times),count)
            sender.store.revision+=1;await task
            self.assertTrue(8.5<=count/duration<=11.5,(count,duration))
            self.assertTrue(all(b-a>=.085 for a,b in zip(transport.times,transport.times[1:])))
    async def test_wifi_socket_auth_meta_sample(self):
        received=[]
        async def handle(reader,writer):
            received.append(await reader.readline())
            writer.write(b'{"status":"ok","lt":0}\n');await writer.drain()
            received.append(await reader.readline());received.append(await reader.readline())
            writer.close()
        server=await asyncio.start_server(handle,'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
        config=PodiumConfig.model_construct(**{**PodiumConfig(link='wifi',device_id='k').model_dump(),'host':'127.0.0.1','port':port})
        transport=SocketTransport();encoder=Encoder(sensors(config,Configuration()))
        async with server:
            await transport.connect(config)
            await transport.send(encoder.auth('k'))
            self.assertEqual((await authenticate(transport))['status'],'ok')
            await transport.send(encoder.meta())
            await transport.send(encoder.sample({'source':'logger-v2-hardware','demo':False,'values':{'Lat':35}}))
            await asyncio.sleep(.1);await transport.close()
        self.assertIn('auth',json.loads(received[0])['cmd']);self.assertIn('meta',json.loads(received[1])['s'])
        self.assertIn('d',json.loads(received[2])['s'])
    async def test_wifi_socket_refused_is_safe_reason(self):
        config=PodiumConfig.model_construct(**{**PodiumConfig(link='wifi').model_dump(),'host':'127.0.0.1','port':1})
        with self.assertRaisesRegex(OSError,'Socket open failed'):await SocketTransport().connect(config)
    async def test_wifi_ignores_sd_operations_lte_does_not(self):
        class Runtime:
            class sd:status={'active':True,'operation':'copy'}
        with tempfile.TemporaryDirectory() as root:
            sender=PodiumSender(root,Runtime())
            self.assertFalse(sender.sd_busy(PodiumConfig(link='wifi')))
            self.assertTrue(sender.sd_busy(PodiumConfig(link='lte')))
    async def test_disabled_does_not_touch_uart(self):
        with tempfile.TemporaryDirectory() as root:
            sender=PodiumSender(root,object())
            task=asyncio.create_task(sender.run());await asyncio.sleep(.1)
            self.assertEqual(sender.status()['state'],'off');task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task

    async def test_auth_failure_blocks_retries_until_configuration_changes(self):
        class Runtime:
            config=Configuration();bridge=object()
            class sd:status={'active':False}
            def status(self):return {'connected':True}
        class Reject:
            attempts=0
            def __init__(self,*a):pass
            async def connect(self,c):Reject.attempts+=1
            async def send(self,data):pass
            async def readline(self):return b'{"status":"denied"}\n'
            async def close(self):pass
        with tempfile.TemporaryDirectory() as root,patch('sim7070.SIM7070',Reject):
            sender=PodiumSender(root,Runtime())
            sender.store.update({'enabled':True,'hardware_ready':True,'apn':'test','device_id':'test'},CHANNELS)
            task=asyncio.create_task(sender.run());await asyncio.sleep(.65)
            self.assertEqual(Reject.attempts,1);self.assertEqual(sender.status()['state'],'auth_failed')
            sender.store.update({'device_id':'changed'},CHANNELS);await asyncio.sleep(.55)
            self.assertEqual(Reject.attempts,2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task

if __name__=='__main__':unittest.main()
