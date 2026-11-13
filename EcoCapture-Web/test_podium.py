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
from podium import ConfigStore,Encoder,Sensor,PodiumConfig,PodiumSender,SocketTransport,WebSocket,VoiceGuard,VoiceLink,sensors,parse_server_url,DIRECT_REMOVED
from models import Configuration,CHANNELS,Signal
from sim7070 import SIM7070,LTEUART

RELAY='wss://car.example.ts.net/ws/audio/main'

class ProtocolTests(unittest.TestCase):
    def test_no_direct_destination_in_the_settings(self):
        # SP-9-4: the logger no longer connects to Podium itself, so nothing can name it.
        for data in ({'host':'telemetry.podium.live'},{'port':8080},{'device_id':'k'},{'fallback_direct':True},{'destination':'podium'}):
            with self.assertRaises(ValueError):PodiumConfig(**data)
        self.assertEqual(PodiumConfig().destination,'server')
    def test_mask_multiple_words_missing_and_nonfinite(self):
        encoder=Encoder([Sensor('V'+str(i),'',0,100) for i in range(65)])
        sample={'source':'logger-v2-hardware','demo':False,'values':{'V0':1,'V31':31,'V32':32,'V64':64,'V5':float('nan'),'V7':None}}
        self.assertEqual(encoder.row(sample),[1,31,32,64,0x80000001,1,1])
        sample['demo']=True;self.assertIsNone(encoder.row(sample))
    def test_ascii_meta_order_and_no_private_fields(self):
        encoder=Encoder(sensors(PodiumConfig(),Configuration()))
        meta=encoder.meta_list()
        names={'Lat':'Latitude','Lon':'Longitude'}
        self.assertEqual([c['nm'] for c in meta],['Interval','Utc']+[names.get(n,n) for n in PodiumConfig().channels]+['Speed','GPSAcc']+['LapCount','CurrentLap','LapTime','BestLap','ElapsedTime','RaceTime','LapsLeft','TimeLimit','Margin','Sector','LastSector','SectorTime'])
        self.assertEqual(meta[2]['ut'],'deg');self.assertEqual(meta[2]['prec'],6)
        data={'source':'logger-v2-hardware','demo':False,'values':{'Lat':35},'password':'secret','imu_raw':'private','can_frames':['private']}
        self.assertNotIn('private',json.dumps(encoder.row(data)))
    def test_empty_sample_sends_all_mask_words(self):
        encoder=Encoder([Sensor('V'+str(i),'',0,1) for i in range(65)])
        self.assertEqual(encoder.row({'source':'logger-v2-hardware','demo':False,'values':{}}),[0,0,0])
    def test_required_context_and_gnss_utc_milliseconds(self):
        encoder=Encoder(sensors(PodiumConfig(channels=['RPM']),Configuration()))
        self.assertEqual([c['nm'] for c in encoder.meta_list()],['Interval','Utc','RPM','Latitude','Longitude','Speed','GPSAcc']+['LapCount','CurrentLap','LapTime','BestLap','ElapsedTime','RaceTime','LapsLeft','TimeLimit','Margin','Sector','LastSector','SectorTime'])
        sample={'source':'logger-v2-hardware','demo':False,'values':{'Lat':35.123456789,'Lon':139.123456789,'GPSSpeed':12.5},'gnss_utc':'1970-01-01T00:00:01Z','gnss_itow_ms':1234}
        self.assertEqual(encoder.row(sample),[1234,35.123457,139.123457,12.5,58])
        sample['gnss_utc']='bad';sample['values']={}
        self.assertEqual(encoder.row(sample),[0])
    def test_gnss_accuracy_always_and_oil_temperature_only_with_a_sensor_hub(self):
        cub=[c.name for c in sensors(PodiumConfig(),Configuration())]
        self.assertIn('GPSAcc',cub);self.assertFalse([n for n in cub if n.startswith('OilTemp')])
        car=Configuration(signals=[Signal(name='OilTemp',unit='°C',channel=2,can_id=0x600,byte_offset=0,data_type='int16',scale=.01,conversion='sensorhub_oiltemp')])
        encoder=Encoder(sensors(PodiumConfig(),car));names=[c.name for c in encoder.channels]
        self.assertEqual(names[-14:-12],['OilTemp','OilTempState'])
        sample={'source':'logger-v2-hardware','demo':False,'values':{},'gnss_hacc_m':1.234,
                'can_signals':{'OilTemp':87.456,'OilTempState':0}}
        d=encoder.row(sample)
        self.assertEqual(d[:3],[1.2,87.46,0])
        self.assertEqual(d[3],1<<names.index('GPSAcc')|1<<names.index('OilTemp')|1<<names.index('OilTempState'))
    def test_lap_values_come_from_lap_timer(self):
        encoder=Encoder(sensors(PodiumConfig(channels=['GPSSats']),Configuration()))
        names=[c.name for c in encoder.channels]
        sample={'source':'logger-v2-hardware','demo':False,'values':{'LapCount':99},'lap':{'LapCount':3,'LapTime':1.5}}
        d=encoder.row(sample)
        self.assertEqual(d[:2],[3,1.5]);self.assertEqual(d[2],1<<names.index('LapCount')|1<<names.index('LapTime'))
        self.assertEqual(encoder.meta_list()[names.index('LapTime')]['ut'],'Min')
    def test_race_options_go_out_every_ten_seconds_or_on_change(self):
        encoder=Encoder(sensors(PodiumConfig(channels=['GPSSats']),Configuration()))
        names=[c.name for c in encoder.channels]
        sample={'source':'logger-v2-hardware','demo':False,'values':{},'lap':{'TimeLimit':2360.11,'Margin':30.0}}
        bits=1<<names.index('TimeLimit')|1<<names.index('Margin')
        self.assertEqual(encoder.row(sample),[2360.11,30.0,bits])
        for _ in range(99):self.assertEqual(encoder.row(sample),[0])
        self.assertEqual(encoder.row(sample),[2360.11,30.0,bits])
        sample['lap']['Margin']=45.0
        self.assertEqual(encoder.row(sample),[45.0,1<<names.index('Margin')])
    def test_interval_comes_from_the_mcu_clock(self):
        encoder=Encoder([Sensor('Interval','ms',0,0),Sensor('V','',0,1)])
        self.assertEqual(encoder.row({'source':'logger-v2-hardware','demo':False,'mcu_ms':12300,'values':{'V':1}}),[12300,1,3])
    def test_secrets_file_permissions_and_preserve_blank(self):
        with tempfile.TemporaryDirectory() as root:
            store=ConfigStore(root);store.update({'password':'private-pass'},CHANNELS)
            self.assertNotIn('private-',json.dumps(store.public()))
            store.update({'enabled':False,'password':''},CHANNELS)
            self.assertEqual(ConfigStore(root).config.password,'private-pass')
            store.update({'clear_password':True},CHANNELS)
            self.assertFalse(store.public()['password_configured'])
            self.assertEqual(stat.S_IMODE(store.path.stat().st_mode),0o600)
    def test_enable_requires_hardware_apn_and_relay_url_and_rejects_injection(self):
        for data in ({'enabled':True},{'enabled':True,'hardware_ready':True,'apn':'test.apn'},{'apn':'x"\rAT'},{'password':'x"\rAT'},{'channels':['Lat','Lat']}):
            with self.assertRaises(ValueError):PodiumConfig(**data)
        self.assertTrue(PodiumConfig(enabled=True,hardware_ready=True,apn='test.apn',server_url=RELAY).enabled)
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):ConfigStore(root).update({'channels':['Unknown']},CHANNELS)
    def test_wifi_enable_needs_only_the_relay_url(self):
        self.assertTrue(PodiumConfig(link='wifi',enabled=True,server_url=RELAY).enabled)
        for data in ({'link':'wifi','enabled':True},{'link':'lte','enabled':True,'server_url':RELAY},{'link':'usb'}):
            with self.assertRaises(ValueError):PodiumConfig(**data)
    def test_saved_config_without_link_loads_as_lte(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'private'/'podium.json';path.parent.mkdir()
            path.write_text(json.dumps({k:v for k,v in PodiumConfig().model_dump().items() if k!='link'}))
            store=ConfigStore(root);self.assertIsNone(store.error);self.assertEqual(store.config.link,'lte')
    def test_relay_url_is_parsed_and_validated(self):
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
            if command in ('AT+CNMP?','AT+CMNB?'):
                response=f'+{command[3:7]}: {getattr(self,"mode",{}).get(command,2 if command=="AT+CNMP?" else 3)}\r\n'
            if command.startswith('AT+CAOPEN='):
                self.outgoing.extend(b'\r\nOK\r\n+CAOPEN: 0,0\r\n');continue
            if command.startswith('AT+CARECV='):
                # By default only 11 bytes per read (fragmentation); recv_cap=None honours the length asked.
                asked=int(command.split(',')[1]);cap=getattr(self,'recv_cap',11)
                n=min(asked if cap is None else cap,len(self.network));payload=bytes(self.network[:n]);del self.network[:n]
                self.outgoing.extend(f'\r\n+CARECV: {n},'.encode()+payload+b'\r\nOK\r\n');continue
            if command=='AT+CASTATE?':response='+CASTATE: 0,1\r\n'
            if command=='AT+CPSI?':response='+CPSI: LTE CAT-M1,Online,440-10,0x1A2B,12345678,123,EUTRAN-BAND19,6150,3,3,-11,-97,-68,7\r\n'
            if command=='AT+CSQ':response='+CSQ: 17,99\r\n'
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
    async def test_auto_link_prefers_wifi_only_while_it_is_up(self):
        class Runtime:
            config=Configuration();sample=None;received_at=0;up=None
            class sd:status={'active':False}
            async def wifi_connected(self):return self.up
        with tempfile.TemporaryDirectory() as root:
            runtime=Runtime();sender=PodiumSender(root,runtime)
            auto=PodiumConfig(link='auto',apn='test.apn',hardware_ready=True)
            self.assertEqual(await sender.choose_link(auto),'wifi')          # unknown: try Wi-Fi
            runtime.up=False;self.assertEqual(await sender.choose_link(auto),'lte')
            runtime.up=True;self.assertEqual(await sender.choose_link(auto),'wifi')
            sender.wifi_skip_until=time.monotonic()+30
            self.assertEqual(await sender.choose_link(auto),'lte')           # Wi-Fi just failed
            self.assertEqual(await sender.choose_link(PodiumConfig(link='wifi')),'wifi')
            with self.assertRaises(ValueError):PodiumConfig(link='auto',enabled=True,server_url=RELAY)  # LTE fallback needs APN
            Runtime.sd.status={'active':True,'operation':'copy'}  # 'auto' may end up on LTE, which shares the MCU link
            self.assertTrue(sender.sd_busy(auto));self.assertFalse(sender.sd_busy(PodiumConfig(link='wifi')))
            Runtime.sd.status={'active':False}

    async def test_unreadable_wifi_state_counts_as_lost(self):
        class Runtime:
            config=Configuration();sample=None;received_at=0
            class sd:status={'active':False}
            async def wifi_connected(self):return None
        with tempfile.TemporaryDirectory() as root, patch('podium.WIFI_CHECK_S',0):
            sender=PodiumSender(root,Runtime());sender.watch_wifi=True
            await sender.check_wifi()  # one unreadable answer is tolerated
            with self.assertRaisesRegex(ConnectionError,'Wi-Fi state unknown'):await sender.check_wifi()

    @unittest.skipUnless(hasattr(__import__('socket'),'TCP_USER_TIMEOUT'),'Linux only (runs in the UNO Q image)')
    async def test_auto_wifi_socket_gives_up_on_unacknowledged_data(self):
        import socket
        server=await asyncio.start_server(lambda r,w:None,'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
        async with server:
            transport=SocketTransport(8,5000)
            await transport.connect(PodiumConfig(),('127.0.0.1',port,False))
            sock=transport.writer.get_extra_info('socket')
            self.assertEqual(sock.getsockopt(socket.IPPROTO_TCP,socket.TCP_USER_TIMEOUT),5000)
            await transport.close()

    async def test_auto_link_leaves_wifi_when_it_drops_mid_stream(self):
        log=[]
        server=await asyncio.start_server(lambda r,w:fake_relay(r,w,log,[]),'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
        class Runtime:
            config=Configuration();sample=None;received_at=0;up=True
            class sd:status={'active':False}
            async def wifi_connected(self):return self.up
        with tempfile.TemporaryDirectory() as root, patch('podium.WIFI_CHECK_S',0):
            runtime=Runtime();sender=PodiumSender(root,runtime);sender.watch_wifi=True
            config=PodiumConfig(link='wifi',destination='server',server_url=f'ws://127.0.0.1:{port}/ws/audio/main')
            async with server:
                task=asyncio.create_task(sender.relay_session(SocketTransport(),config,0))
                await asyncio.sleep(.3);self.assertFalse(task.done())
                runtime.up=False
                with self.assertRaisesRegex(ConnectionError,'Wi-Fi lost'):await asyncio.wait_for(task,2)

    async def test_auto_link_falls_back_to_lte_without_backoff(self):
        closed=await asyncio.start_server(lambda r,w:w.close(),'127.0.0.1',0);port=closed.sockets[0].getsockname()[1];closed.close();await closed.wait_closed()
        class Runtime:
            config=Configuration();sample=None;received_at=0;bridge=object()
            class sd:status={'active':False}
            def status(self):return {'connected':True}
            async def wifi_connected(self):return True
        with tempfile.TemporaryDirectory() as root:
            sender=PodiumSender(root,Runtime())
            sender.store.config=PodiumConfig(link='auto',apn='test.apn',hardware_ready=True,enabled=True,destination='server',
                                             server_url=f'ws://127.0.0.1:{port}/ws/audio/main')
            task=asyncio.create_task(sender.run())
            for _ in range(40):
                await asyncio.sleep(.05)
                if sender.active_link=='lte':break
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
            events=sender.events()
        self.assertEqual(sender.active_link,'lte');self.assertGreater(sender.wifi_skip_until,time.monotonic())
        self.assertEqual(sender.status()['active_link'],'lte');self.assertIn('SIM7070G',sender.status()['transport'])
        self.assertEqual([(e['event'],e.get('link')) for e in events[:3]],[('session_start','wifi'),('session_end','wifi'),('session_start','lte')])
        self.assertEqual(events[1]['reason'],'Socket open failed')
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
    async def test_relay_without_podium_key_keeps_streaming(self):
        # The relay is the team's own pit display first; a missing Podium key there is only reported.
        log=[];err=b'{"type":"error","code":"podium_not_configured","message":"x"}'
        server=await asyncio.start_server(lambda r,w:fake_relay(r,w,log,[err]),'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
        class Runtime:
            config=Configuration();sample=None;received_at=0
            class sd:status={'active':False}
        with tempfile.TemporaryDirectory() as root:
            runtime=Runtime();sender=PodiumSender(root,runtime)
            config=PodiumConfig(link='wifi',destination='server',server_url=f'ws://127.0.0.1:{port}/ws/audio/main',enabled=True)
            async with server:
                task=asyncio.create_task(sender.relay_session(SocketTransport(),config,0))
                for seq in range(25):
                    runtime.sample={'source':'logger-v2-hardware','demo':False,'seq':seq,'mcu_ms':seq*100,'values':{'Lat':35.5},
                                    'gnss_utc':'2026-10-14T00:00:00Z','gnss_itow_ms':seq*100}
                    runtime.received_at=time.monotonic();await asyncio.sleep(.1)
                self.assertFalse(task.done())
                self.assertEqual(sender.state['relay_error'],'podium_not_configured');self.assertIn('Podiumには出ません',sender.state['message'])
                self.assertGreaterEqual(sender.state['frames'],15)
                sender.store.revision+=1;await asyncio.wait_for(task,2)
    async def test_lte_relay_enables_modem_tls_with_sni(self):
        uart=FakeUART();modem=SIM7070(uart=uart)
        config=PodiumConfig(apn='test.apn',hardware_ready=True)
        await modem.connect(config,('car.example.ts.net',443,True))
        self.assertIn('AT+CSSLCFG="SNI",0,"car.example.ts.net"',uart.commands)
        self.assertIn('AT+CASSLCFG=0,"SSL",1',uart.commands)
        self.assertEqual(uart.commands[-1],'AT+CAOPEN=0,0,"TCP","car.example.ts.net",443')
        uart.network.extend(b'abc');self.assertEqual(await modem.read_some(),b'abc')

    async def test_lte_poll_drains_a_backlog_in_full_reads(self):
        # 2026-11-06: the relay sent ~1 kB/s while one 512-byte read per 2 s poll took
        # ~256 B/s, so pongs waited behind the backlog and the link dropped every ~20 s.
        uart=FakeUART();uart.recv_cap=None;modem=SIM7070(uart=uart)
        await modem.connect(PodiumConfig(apn='test.apn',hardware_ready=True),('car.example.ts.net',443,True))
        backlog=bytes(range(256))*16+b'\r\nOK\r\n'*3   # 4114 bytes, binary, with OK inside
        uart.network.extend(backlog);uart.commands.clear()
        self.assertEqual(await modem.read_some(),backlog)        # 1460+1460+1194 in one poll
        self.assertEqual(uart.commands,['AT+CARECV=0,1460']*4)   # the 4th found it empty
        uart.network.extend(b'x'*7000);uart.commands.clear()
        self.assertEqual(len(await modem.read_some()),4*1460)     # bounded: at most 4 reads a poll
        self.assertEqual(len(uart.commands),4)
        self.assertEqual(len(await modem.read_some()),7000-4*1460)
        uart.commands.clear();self.assertEqual(await modem.read_some(),b'')   # idle: one read
        self.assertEqual(uart.commands,['AT+CARECV=0,1460'])
        # The real modem returns about one TCP segment per read (~1 kB), short of the 1460 asked.
        uart.recv_cap=1000;uart.network.extend(b'y'*3000)
        self.assertEqual(await modem.read_some(),b'y'*3000)

    async def test_connect_records_phase_times_and_modem_mode(self):
        uart=FakeUART();modem=SIM7070(uart=uart)
        await modem.connect(PodiumConfig(apn='test.apn',hardware_ready=True),('car.example.ts.net',443,True))
        self.assertEqual(modem.modem,{'cnmp':2,'cmnb':3,'cnmp_set':38,'cmnb_set':1})
        self.assertLess(uart.commands.index('AT+CFUN=0'),uart.commands.index('AT+CNMP=38'))
        self.assertLess(uart.commands.index('AT+CMNB=1'),uart.commands.index('AT+CFUN=1'))
        for phase in ('modem_initialization','sim_ready','network_registration','pdp_activation','relay_connect'):
            self.assertIn(phase,modem.timings)
        self.assertGreaterEqual(modem.timings['network_registration'],1)   # one 1 s wait for CGATT
        self.assertEqual({k:modem.radio[k] for k in ('band','rsrq','rsrp','rssi','sinr','csq')},
                         {'band':'EUTRAN-BAND19','rsrq':-11,'rsrp':-97,'rssi':-68,'sinr':7,'csq':17})
        self.assertLess(uart.commands.index('AT+CPSI?'),uart.commands.index('AT+CPSMS=0'))

    async def test_lte_m_only_is_not_rewritten_once_set(self):
        uart=FakeUART();uart.mode={'AT+CNMP?':38,'AT+CMNB?':1};modem=SIM7070(uart=uart)
        await modem.connect(PodiumConfig(apn='test.apn',hardware_ready=True),('car.example.ts.net',443,True))
        self.assertEqual(modem.modem,{'cnmp':38,'cmnb':1})
        self.assertFalse([c for c in uart.commands if c.startswith(('AT+CNMP=','AT+CMNB='))])

    async def test_full_modem_connect_send_and_shutdown(self):
        uart=FakeUART();modem=SIM7070(uart=uart)
        config=PodiumConfig(apn='test.apn',hardware_ready=True,enabled=True,server_url=RELAY)
        await modem.connect(config,('car.example.ts.net',443,True))
        encoder=Encoder(sensors(config,Configuration()))
        row=json.dumps(encoder.row({'source':'logger-v2-hardware','demo':False,'values':{'Lat':35,'AccelX':1}})).encode()
        await modem.send(row)
        self.assertEqual(json.loads(b''.join(uart.messages)),[35,1,516])
        self.assertLess(uart.commands.index('AT+CFUN=0'),uart.commands.index('AT+CFUN=1'))
        self.assertGreaterEqual(uart.sim_queries,2)
        self.assertLess(uart.commands.index('AT+CGATT?'),uart.commands.index('AT+CPSMS=0'))
        await modem.close();self.assertFalse(uart.powered)
    async def test_large_meta_splits_tcp_payload_without_extra_newlines(self):
        uart=FakeUART();modem=SIM7070(uart=uart)
        data=json.dumps(Encoder([Sensor('V'+str(i),'',0,1) for i in range(65)]).meta_list()).encode()
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
    async def test_relay_sends_each_sample_once_and_nothing_stale(self):
        log=[]
        server=await asyncio.start_server(lambda r,w:fake_relay(r,w,log,[]),'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
        class Runtime:
            config=Configuration();sample=None;received_at=0
            class sd:status={'active':False}
        def rows():return sum(len(json.loads(p)['samples']) for op,p in log[1:] if op==1 and json.loads(p)['type']=='podium.samples')
        with tempfile.TemporaryDirectory() as root:
            runtime=Runtime();sender=PodiumSender(root,runtime)
            config=PodiumConfig(link='wifi',server_url=f'ws://127.0.0.1:{port}/ws/audio/main')
            async with server:
                task=asyncio.create_task(sender.relay_session(SocketTransport(),config,0))
                sample={'source':'logger-v2-hardware','demo':False,'seq':1,'mcu_ms':100,'values':{'AccelX':1}}
                for _ in range(15):   # the same sample seen again and again goes out once
                    runtime.sample=sample;runtime.received_at=time.monotonic();await asyncio.sleep(.1)
                self.assertEqual(rows(),1)
                for seq in range(2,12):   # new samples that are already old are never sent late
                    runtime.sample={**sample,'seq':seq};runtime.received_at=time.monotonic()-3;await asyncio.sleep(.1)
                await asyncio.sleep(.3);self.assertEqual(rows(),1)
                sender.store.revision+=1;await asyncio.wait_for(task,2)
    async def test_wifi_socket_refused_is_safe_reason(self):
        with self.assertRaisesRegex(OSError,'Socket open failed'):await SocketTransport().connect(PodiumConfig(link='wifi'),('127.0.0.1',1,False))
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


# What the logger's private/podium.json looked like before SP-9-4 (every field of the
# old model). The logger in the car has one of these; it must keep working.
OLD_RELAY={'enabled':True,'link':'auto','destination':'server','server_url':RELAY,
           'backup_server_urls':['wss://spare.example.ts.net/ws/audio/main'],'fallback_direct':True,
           'voice_receive':True,'voice_send':False,'hardware_ready':True,'host':'telemetry.podium.live','port':8080,
           'apn':'test.apn','username':'user','password':'private-pass','device_id':'private-key','channels':['Lat','Lon','RPM']}
OLD_DIRECT={**OLD_RELAY,'destination':'podium','fallback_direct':False,'backup_server_urls':[]}

def saved(root,data):
    path=Path(root)/'private'/'podium.json';path.parent.mkdir();path.write_text(json.dumps(data));return path

class OldSettingsTests(unittest.IsolatedAsyncioTestCase):
    def test_old_relay_file_keeps_its_relay_settings(self):
        with tempfile.TemporaryDirectory() as root:
            path=saved(root,OLD_RELAY);before=path.read_bytes()
            store=ConfigStore(root);config=store.config
            self.assertIsNone(store.error)
            for name in ('enabled','link','server_url','backup_server_urls','voice_receive','voice_send','hardware_ready','apn','username','password','channels'):
                self.assertEqual(getattr(config,name),OLD_RELAY[name],name)
            sender=PodiumSender(root,None)
            self.assertEqual(sender.targets(config),[RELAY,'wss://spare.example.ts.net/ws/audio/main'])   # no direct last resort
            self.assertTrue(sender.status()['enabled']);self.assertTrue(sender.status()['configured'])
            self.assertEqual(path.read_bytes(),before)   # reading alone rewrites nothing: an older build can still read it
            public=json.dumps(store.public())
            for word in ('private-','device_id','key_configured','telemetry.podium.live','fallback_direct'):self.assertNotIn(word,public)

    def test_old_direct_file_loads_switched_off_with_the_reason(self):
        for old in (OLD_DIRECT,{**OLD_DIRECT,'server_url':''},{k:v for k,v in OLD_DIRECT.items() if k!='destination'}):
            with tempfile.TemporaryDirectory() as root:
                saved(root,old);store=ConfigStore(root)
                self.assertEqual(store.error,DIRECT_REMOVED);self.assertFalse(store.config.enabled)
                self.assertEqual((store.config.link,store.config.apn,store.config.channels),('auto','test.apn',['Lat','Lon','RPM']))
                self.assertEqual(store.public()['error'],DIRECT_REMOVED)
                self.assertEqual(PodiumSender(root,None).status()['message'],DIRECT_REMOVED)

    async def test_old_direct_file_never_opens_a_connection(self):
        opened=[]
        class Runtime:
            config=Configuration();sample=None;received_at=0;bridge=object()
            class sd:status={'active':False}
            def status(self):return {'connected':True}
        class Transport:
            def __init__(self,*a):opened.append(a)
        with tempfile.TemporaryDirectory() as root,patch('sim7070.SIM7070',Transport),patch('podium.SocketTransport',Transport),\
             patch('asyncio.open_connection',side_effect=AssertionError('no connection expected')):
            saved(root,OLD_DIRECT);sender=PodiumSender(root,Runtime())
            task=asyncio.create_task(sender.run());await asyncio.sleep(1.2)
            self.assertFalse(task.done());self.assertEqual(opened,[])
            status=sender.status()
            self.assertEqual((status['state'],status['message'],status['enabled']),('off',DIRECT_REMOVED,False))
            self.assertEqual(sender.events(),[])
            # Entering the relay and switching on again is an ordinary save.
            sender.store.update({'link':'wifi','server_url':RELAY,'enabled':True},CHANNELS)
            self.assertIsNone(sender.store.error);self.assertTrue(sender.store.config.enabled)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task

    def test_saving_drops_the_direct_settings_and_stays_readable(self):
        with tempfile.TemporaryDirectory() as root:
            path=saved(root,OLD_RELAY);store=ConfigStore(root)
            store.update({'voice_send':True},CHANNELS)
            data=json.loads(path.read_text())
            for name in ('host','port','device_id','fallback_direct'):self.assertNotIn(name,data)
            self.assertNotIn('private-key',path.read_text())
            # 'destination' stays written: the build before SP-9-4 defaults to direct without it.
            self.assertEqual(data['destination'],'server');self.assertEqual(data['server_url'],RELAY)
            again=ConfigStore(root);self.assertIsNone(again.error);self.assertTrue(again.config.enabled);self.assertTrue(again.config.voice_send)

    def test_clients_written_for_the_old_settings_can_still_save(self):
        with tempfile.TemporaryDirectory() as root:
            store=ConfigStore(root)
            # The old settings page and the native screen send these along with every save.
            store.update({'link':'wifi','server_url':RELAY,'enabled':True,'host':'telemetry.podium.live','port':8080,
                          'device_id':'private-key','fallback_direct':False,'clear_key':True},CHANNELS)
            self.assertTrue(store.config.enabled);self.assertNotIn('private-key',store.path.read_text())
            # Asking for the direct path itself is refused, not quietly turned into something else.
            for body in ({'destination':'podium'},{'fallback_direct':True}):
                with self.assertRaises(ValueError):store.update(body,CHANNELS)
            self.assertTrue(ConfigStore(root).config.enabled)

    def test_unreadable_file_is_off_and_says_so(self):
        for text in ('{not json','[]',json.dumps({**OLD_RELAY,'unknown_setting':1}),json.dumps({**OLD_RELAY,'server_url':'https://bad'})):
            with tempfile.TemporaryDirectory() as root:
                path=Path(root)/'private'/'podium.json';path.parent.mkdir();path.write_text(text)
                sender=PodiumSender(root,None)
                self.assertFalse(sender.store.config.enabled);self.assertIn('読めません',sender.store.error)
                self.assertEqual(sender.status()['message'],sender.store.error)

async def silent_after_ping_relay(reader,writer):
    """Completes the handshake, sends one ping, then never answers (a dead mobile link)."""
    head=await reader.readuntil(b'\r\n\r\n')
    key=re.search(rb'(?im)^sec-websocket-key:\s*(\S+)',head)[1]
    accept=base64.b64encode(hashlib.sha1(key+WebSocket.GUID).digest())
    writer.write(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n')
    writer.write(bytes([0x89,2])+b'hi');await writer.drain()
    with __import__('contextlib').suppress(Exception):
        while await reader.read(4096):pass

async def pong_relay(reader,writer,log):
    """Like fake_relay, but answers every client ping with a pong."""
    head=await reader.readuntil(b'\r\n\r\n')
    key=re.search(rb'(?im)^sec-websocket-key:\s*(\S+)',head)[1]
    log.append(head.split(b'\r\n')[0])
    accept=base64.b64encode(hashlib.sha1(key+WebSocket.GUID).digest())
    writer.write(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n')
    await writer.drain()
    while True:
        try:b0,b1=await reader.readexactly(2)
        except asyncio.IncompleteReadError:return
        n=b1&0x7f
        if n==126:n=int.from_bytes(await reader.readexactly(2),'big')
        mask=await reader.readexactly(4);payload=bytes(b^mask[i%4] for i,b in enumerate(await reader.readexactly(n)))
        log.append((b0&0x0f,payload))
        if b0&0x0f==9:writer.write(bytes([0x8a,len(payload)])+payload);await writer.drain()

class FailoverTests(unittest.IsolatedAsyncioTestCase):
    def test_backup_urls_are_validated_and_only_relays_are_targets(self):
        ok=PodiumConfig(link='wifi',destination='server',server_url='wss://a.example/ws/audio/x',
                        backup_server_urls=['wss://b.example/ws/audio/x'],enabled=True)
        sender=PodiumSender(tempfile.mkdtemp(),None)
        self.assertEqual(sender.targets(ok),['wss://a.example/ws/audio/x','wss://b.example/ws/audio/x'])
        self.assertEqual(sender.targets(PodiumConfig()),[])
        with self.assertRaises(ValueError):PodiumConfig(backup_server_urls=['http://b.example/x'])

    async def test_dead_primary_moves_to_backup_without_backoff(self):
        closed=await asyncio.start_server(lambda r,w:w.close(),'127.0.0.1',0);dead=closed.sockets[0].getsockname()[1];closed.close();await closed.wait_closed()
        log=[]
        backup=await asyncio.start_server(lambda r,w:pong_relay(r,w,log),'127.0.0.1',0);port=backup.sockets[0].getsockname()[1]
        class Runtime:
            config=Configuration();sample=None;received_at=0;bridge=object()
            class sd:status={'active':False}
            def status(self):return {'connected':True}
        with tempfile.TemporaryDirectory() as root:
            sender=PodiumSender(root,Runtime())
            sender.store.config=PodiumConfig(link='wifi',enabled=True,destination='server',
                server_url=f'ws://127.0.0.1:{dead}/ws/audio/main',backup_server_urls=[f'ws://127.0.0.1:{port}/ws/audio/main'])
            async with backup:
                task=asyncio.create_task(sender.run())
                for _ in range(40):
                    await asyncio.sleep(.05)
                    if log:break
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):await task
            events=sender.events()
        self.assertEqual(log[0],b'GET /ws/audio/main HTTP/1.1')   # reached the backup within 2 s
        self.assertEqual(sender.status()['target']['index'],1)
        self.assertEqual([(e['event'],e.get('target')) for e in events[:2]],[('session_start',None),('session_end','127.0.0.1')])

    async def test_silent_relay_is_dropped_and_answering_relay_is_kept(self):
        class Runtime:
            config=Configuration();sample=None;received_at=0
            class sd:status={'active':False}
        silent=await asyncio.start_server(silent_after_ping_relay,'127.0.0.1',0);sport=silent.sockets[0].getsockname()[1]
        log=[]
        alive=await asyncio.start_server(lambda r,w:pong_relay(r,w,log),'127.0.0.1',0);aport=alive.sockets[0].getsockname()[1]
        limits={'RELAY_PING_S':{'wifi':.1,'lte':.1},'RELAY_SILENT_S':{'wifi':.5,'lte':.5},'RELAY_POLL_S':{'wifi':.05,'lte':.05}}
        with tempfile.TemporaryDirectory() as root,patch.multiple('podium',**limits):
            sender=PodiumSender(root,Runtime())
            async with silent:
                config=PodiumConfig(link='wifi',destination='server',server_url=f'ws://127.0.0.1:{sport}/ws/audio/main')
                with self.assertRaisesRegex(ConnectionError,'Relay not responding'):
                    await asyncio.wait_for(sender.relay_session(SocketTransport(),config,0),3)
            async with alive:
                config=PodiumConfig(link='wifi',destination='server',server_url=f'ws://127.0.0.1:{aport}/ws/audio/main')
                task=asyncio.create_task(sender.relay_session(SocketTransport(),config,0))
                await asyncio.sleep(1.2);self.assertFalse(task.done())   # well past the 0.5 s silent limit
                sender.store.revision+=1;await asyncio.wait_for(task,2)
        self.assertGreaterEqual(sum(1 for x in log[1:] if x[0]==9),5)


class VoiceGuardTests(unittest.TestCase):
    def feed(self,guard,start,seconds,rows=5,every=.5,delay=.5):
        t=start
        while t<start+seconds:
            result=guard.batch_sent(rows,delay,t)
            if result:return t,result
            t+=every
        return t,None
    def test_waits_for_a_baseline_then_starts(self):
        guard=VoiceGuard('lte')
        self.assertIsNone(guard.want(True,0))                 # no telemetry measured yet
        t,_=self.feed(guard,0,4)
        self.assertEqual(guard.want(True,t),'on');self.assertAlmostEqual(guard.baseline,10,delta=.5)
        self.assertIsNone(guard.want(True,t+1))
        self.assertEqual(guard.want(False,t+2),'off');self.assertIsNone(guard.reason)
    def test_late_batch_pauses_voice(self):
        guard=VoiceGuard('lte');t,_=self.feed(guard,0,4);guard.want(True,t)
        self.assertEqual(guard.batch_sent(5,2.5,t+.5),'off')
        self.assertEqual(guard.reason,'telemetry_delay');self.assertFalse(guard.on)
        self.assertIsNone(guard.want(True,t+10))                # still paused
        self.assertEqual(guard.want(True,t+31),'on')
    def test_fewer_rows_per_second_pauses_voice(self):
        guard=VoiceGuard('wifi');t,_=self.feed(guard,0,4);guard.want(True,t)
        t,result=self.feed(guard,t+.5,10,rows=3)                 # 6 rows/s against 10
        self.assertEqual(result,'off');self.assertEqual(guard.reason,'telemetry_rate')
    def test_lte_accepts_the_drop_voice_costs(self):
        # Measured 2026-10-19: ~7 rows/s without voice, ~5 while the driver talks.
        guard=VoiceGuard('lte');t,_=self.feed(guard,0,4,rows=7,every=1);guard.want(True,t)
        _,result=self.feed(guard,t+1,30,rows=5,every=1)
        self.assertIsNone(result);self.assertTrue(guard.on)
        _,result=self.feed(guard,t+31,10,rows=3,every=1)       # 3 of 7 is more than voice may take
        self.assertEqual(result,'off');self.assertEqual(guard.reason,'telemetry_rate')
    def test_steady_telemetry_keeps_voice(self):
        guard=VoiceGuard('lte');t,_=self.feed(guard,0,4);guard.want(True,t)
        _,result=self.feed(guard,t+.5,30)
        self.assertIsNone(result);self.assertTrue(guard.on)
    def test_tripping_again_soon_doubles_the_pause(self):
        guard=VoiceGuard('lte');t,_=self.feed(guard,0,4);guard.want(True,t)
        guard.batch_sent(5,3,t+1);first=guard.pause
        guard.want(True,guard.paused_until);guard.batch_sent(5,3,guard.paused_until+1)
        self.assertEqual(guard.pause,first*2)

async def voice_relay(reader,writer,log,uplink=None,say=()):
    """Answers pings and streams binary 'voice' frames while the client's hello asks for it.
    say: text messages (dicts) the pit sends to the logger right after its first hello."""
    head=await reader.readuntil(b'\r\n\r\n')
    key=re.search(rb'(?im)^sec-websocket-key:\s*(\S+)',head)[1]
    accept=base64.b64encode(hashlib.sha1(key+WebSocket.GUID).digest())
    writer.write(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n')
    await writer.drain()
    streaming=asyncio.Event()
    async def talk():
        while True:
            await streaming.wait()
            writer.write(bytes([0x82,80])+bytes(80));await writer.drain();await asyncio.sleep(.12)
    talker=asyncio.create_task(talk())
    try:
        while True:
            try:b0,b1=await reader.readexactly(2)
            except asyncio.IncompleteReadError:return
            n=b1&0x7f
            if n==126:n=int.from_bytes(await reader.readexactly(2),'big')
            mask=await reader.readexactly(4);payload=bytes(b^mask[i%4] for i,b in enumerate(await reader.readexactly(n)))
            if b0&0x0f==9:writer.write(bytes([0x8a,len(payload)])+payload);await writer.drain()
            if b0&0x0f==2 and uplink is not None:uplink.append(('opus',payload))
            if b0&0x0f==1:
                message=json.loads(payload)
                if message['type']=='audio.ptt' and uplink is not None:uplink.append(('ptt',message['active']))
                if message['type']=='logger.config' and uplink is not None:uplink.append(('config',message['data']))
                if message['type']=='hello' and say:
                    for text in say:
                        data=json.dumps(text).encode();writer.write(bytes([0x81,len(data)])+data)
                    await writer.drain();say=()
                if message['type']=='hello':
                    log.append(message['audio_formats'])
                    streaming.set() if message['audio_formats'] else streaming.clear()
    finally:talker.cancel()

class VoiceRelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_voice_is_taken_and_dropped_when_telemetry_lags(self):
        log=[]
        server=await asyncio.start_server(lambda r,w:voice_relay(r,w,log),'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
        class Runtime:
            config=Configuration();sample=None;received_at=0;played=[]
            class sd:status={'active':False}
            def play_voice(self,packet):self.played.append(packet)
        # The window must hold at least 2 batches (sent every .5 s), or the rate reads 0 on a slow CPU (UNO Q).
        with tempfile.TemporaryDirectory() as root,patch.object(VoiceGuard,'WINDOW_S',1.2),patch.object(VoiceGuard,'PAUSE_S',60):
            runtime=Runtime();sender=PodiumSender(root,runtime)
            config=PodiumConfig(link='wifi',destination='server',server_url=f'ws://127.0.0.1:{port}/ws/audio/main',voice_receive=True)
            async with server:
                task=asyncio.create_task(sender.relay_session(SocketTransport(),config,0))
                async def run(seconds,start):
                    for seq in range(start,start+int(seconds*10)):
                        runtime.sample={'source':'logger-v2-hardware','demo':False,'seq':seq,'mcu_ms':seq*100,'values':{'Lat':35.5},
                                        'gnss_utc':'2026-10-14T00:00:00Z','gnss_itow_ms':seq*100}
                        runtime.received_at=time.monotonic();await asyncio.sleep(.1)
                await run(2.5,0)
                self.assertEqual(sender.state['voice'],'on')
                self.assertGreater(sender.state['voice_packets'],3);self.assertEqual(len(runtime.played),sender.state['voice_packets'])
                # Samples stop: the open batch waits past the limit, so voice must yield.
                with patch.dict(VoiceGuard.MAX_DELAY_S,{'wifi':.3}):
                    real=sender.sent
                    def slow(frames,size):real(frames,size);time.sleep(.4)
                    sender.sent=slow;await run(1,100);sender.sent=real
                await run(.5,200)
                self.assertEqual(sender.state['voice'],'paused');self.assertEqual(sender.state['voice_reason'],'telemetry_delay')
                packets=sender.state['voice_packets'];await run(1,300)
                self.assertEqual(sender.state['voice_packets'],packets)   # nothing taken while paused
                sender.store.revision+=1;await asyncio.wait_for(task,2)
            self.assertTrue(any(e['event']=='voice_paused' for e in sender.events()))
        self.assertEqual(log[0],[]);self.assertEqual(log[1],[{'sample_rate':8000,'channels':1,'frame_ms':120}]);self.assertEqual(log[2],[])

    async def test_voice_stays_off_unless_enabled(self):
        log=[]
        server=await asyncio.start_server(lambda r,w:voice_relay(r,w,log),'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
        class Runtime:
            config=Configuration();sample=None;received_at=0
            class sd:status={'active':False}
        with tempfile.TemporaryDirectory() as root,patch.object(VoiceGuard,'WINDOW_S',.6):
            runtime=Runtime();sender=PodiumSender(root,runtime)
            config=PodiumConfig(link='wifi',destination='server',server_url=f'ws://127.0.0.1:{port}/ws/audio/main')
            async with server:
                task=asyncio.create_task(sender.relay_session(SocketTransport(),config,0))
                for seq in range(20):
                    runtime.sample={'source':'logger-v2-hardware','demo':False,'seq':seq,'mcu_ms':seq*100,'values':{'Lat':35.5},
                                    'gnss_utc':'2026-10-14T00:00:00Z','gnss_itow_ms':seq*100}
                    runtime.received_at=time.monotonic();await asyncio.sleep(.1)
                sender.store.revision+=1;await asyncio.wait_for(task,2)
        self.assertEqual(log,[[]]);self.assertEqual(sender.state['voice_packets'],0)

    async def test_driver_voice_goes_up_after_ptt_and_stops_when_telemetry_lags(self):
        log=[];uplink=[]
        server=await asyncio.start_server(lambda r,w:voice_relay(r,w,log,uplink),'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
        class Runtime:
            config=Configuration();sample=None;received_at=0
            class sd:status={'active':False}
        class Link:
            # Stands in for voice_agent.py: the driver talks for 3 packets whenever asked.
            def __init__(self):self.asked=0;self.queue=[]
            def want_uplink(self):
                self.asked+=1
                if self.asked==1:self.queue+=[('A',b'{"card_present":true}'),('T',b'1'),('U',b''*20),('U',b''*20),('U',b''*20),('T',b'0')]
                elif self.asked==2:self.queue+=[('T',b'1'),('U',b''*20)]   # still talking when telemetry lags
                return True
            def receive(self):out,self.queue=self.queue,[];return out
            def play(self,packet):pass
        with tempfile.TemporaryDirectory() as root,patch.object(VoiceGuard,'WINDOW_S',1.2),patch.object(VoiceGuard,'PAUSE_S',60):
            runtime=Runtime();sender=PodiumSender(root,runtime);sender.voice_link=link=Link()
            config=PodiumConfig(link='wifi',destination='server',server_url=f'ws://127.0.0.1:{port}/ws/audio/main',voice_send=True)
            async with server:
                task=asyncio.create_task(sender.relay_session(SocketTransport(),config,0))
                async def run(seconds,start):
                    for seq in range(start,start+int(seconds*10)):
                        runtime.sample={'source':'logger-v2-hardware','demo':False,'seq':seq,'mcu_ms':seq*100,'values':{'Lat':35.5},
                                        'gnss_utc':'2026-10-14T00:00:00Z','gnss_itow_ms':seq*100}
                        runtime.received_at=time.monotonic();await asyncio.sleep(.1)
                await run(3.5,0)
                self.assertEqual(sender.state['voice'],'on');self.assertEqual(sender.state['voice_sent'],4)
                self.assertTrue(sender.state['voice_talking']);self.assertEqual(sender.state['voice_agent'],{'card_present':True})
                with patch.dict(VoiceGuard.MAX_DELAY_S,{'wifi':.3}):
                    real=sender.sent
                    def slow(frames,size):real(frames,size);time.sleep(.4)
                    sender.sent=slow;await run(1,100);sender.sent=real
                await run(.5,200)
                self.assertEqual(sender.state['voice'],'paused');self.assertFalse(sender.state['voice_talking'])
                asked=link.asked;await run(1.5,300)
                self.assertEqual(link.asked,asked)   # microphone not asked for while paused
                sender.store.revision+=1;await asyncio.wait_for(task,2)
        # Only sending: the relay is never asked for the pit mix.
        self.assertTrue(all(f==[] for f in log))
        self.assertEqual(uplink,[('ptt',True),('opus',b''*20),('opus',b''*20),('opus',b''*20),('ptt',False),
                                 ('ptt',True),('opus',b''*20),('ptt',False)])


class LoggerConfigTests(unittest.IsolatedAsyncioTestCase):
    async def test_pit_settings_reach_the_agent_and_its_answer_goes_back(self):
        log=[];uplink=[]
        pit={'type':'logger.config','session_id':7,'data':{'voice':{'level_db':-12}}}
        server=await asyncio.start_server(lambda r,w:voice_relay(r,w,log,uplink,say=[pit]),'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
        class Runtime:
            config=Configuration();sample=None;received_at=0
            class sd:status={'active':False}
        class Link:
            # Stands in for voice_agent.py: answers b'C' with its status, settings included.
            def __init__(self):self.got=[];self.queue=[]
            def send(self,data):
                self.got.append(data)
                self.queue.append(('A',json.dumps({'settings':{'level_db':-12.0},'gain_db':20.0,'device':'Audio','mic':True,'route':'usb'}).encode()))
                return True
            def want_uplink(self):return True
            def receive(self):out,self.queue=self.queue,[];return out
            def play(self,packet):pass
        with tempfile.TemporaryDirectory() as root:
            runtime=Runtime();sender=PodiumSender(root,runtime);sender.voice_link=link=Link()
            config=PodiumConfig(link='wifi',destination='server',server_url=f'ws://127.0.0.1:{port}/ws/audio/main')
            async with server:
                task=asyncio.create_task(sender.relay_session(SocketTransport(),config,0))
                for seq in range(10):
                    runtime.sample={'source':'logger-v2-hardware','demo':False,'seq':seq,'mcu_ms':seq*100,'values':{'Lat':35.5},
                                    'gnss_utc':'2026-10-14T00:00:00Z','gnss_itow_ms':seq*100}
                    runtime.received_at=time.monotonic();await asyncio.sleep(.1)
                sender.store.revision+=1;await asyncio.wait_for(task,2)
        self.assertEqual(link.got,[b'C{"level_db": -12}'])
        self.assertEqual(uplink,[('config',{'voice':{'level_db':-12.0},'gain_db':20.0,'device':'Audio','mic':True,'route':'usb'})])


class VoiceLinkTests(unittest.TestCase):
    def test_no_agent_is_harmless(self):
        with tempfile.TemporaryDirectory() as root:
            link=VoiceLink(root)
            link.play(b'x');self.assertFalse(link.want_uplink());self.assertEqual(link.receive(),[])


if __name__=='__main__':unittest.main()
