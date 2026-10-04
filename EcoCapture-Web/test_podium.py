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
from podium import ConfigStore,Encoder,Sensor,PodiumConfig,PodiumSender,AuthenticationError,sensors,authenticate
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
        self.assertEqual([c['nm'] for c in meta],[names.get(n,n) for n in PodiumConfig().channels]+['Speed','Utc'])
        self.assertEqual(meta[0]['ut'],'deg')
        data={'source':'logger-v2-hardware','demo':False,'values':{'Lat':35},'password':'secret','imu_raw':'private','can_frames':['private']}
        self.assertNotIn('private',encoder.sample(data).decode())
        self.assertEqual(encoder.auth('key'),b'{"cmd":{"schemaVer":2,"auth":{"deviceId":"key"}}}\n')
    def test_empty_sample_sends_all_mask_words(self):
        encoder=Encoder([Sensor('V'+str(i),'',0,1) for i in range(65)])
        self.assertEqual(json.loads(encoder.sample({'source':'logger-v2-hardware','demo':False,'values':{}})),{'s':{'d':[0,0,0]}})
    def test_required_context_and_gnss_utc_milliseconds(self):
        encoder=Encoder(sensors(PodiumConfig(channels=['RPM']),Configuration()))
        self.assertEqual([c['nm'] for c in json.loads(encoder.meta())['s']['meta']],['RPM','Latitude','Longitude','Speed','Utc'])
        sample={'source':'logger-v2-hardware','demo':False,'values':{'Lat':35.123456789,'Lon':139.123456789,'GPSSpeed':12.5},'gnss_utc':'1970-01-01T00:00:01Z','gnss_itow_ms':1234}
        self.assertEqual(json.loads(encoder.sample(sample))['s']['d'],[35.123457,139.123457,12.5,1234,30])
        sample['gnss_utc']='bad';sample['values']={}
        self.assertEqual(json.loads(encoder.sample(sample))['s']['d'],[0])
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

class AsyncTests(unittest.IsolatedAsyncioTestCase):
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
        self.assertEqual(json.loads(wire[2])['s']['d'],[35,1,129])
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
