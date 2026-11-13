"""Run in the UNO Q image; isolated temporary storage and no hardware mutations."""
import csv
import asyncio
import importlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from models import CHANNELS, Configuration, Signal, validate_sample


class ServerTests(unittest.TestCase):
    def test_emmc_retention_deletes_oldest_finished_logs_only_when_space_is_low(self):
        for n in range(5):
            self.s.runtime.recorder.start(Configuration());self.s.runtime.recorder.stop()
            path=self.s.LOGS/self.s.runtime.recorder.name;os.utime(path,(1000+n,1000+n))
        self.assertEqual(len(list(self.s.LOGS.glob('LOG_*.csv'))),5)
        names=[p.name for p in sorted(self.s.LOGS.glob('LOG_*.csv'),key=lambda p:p.stat().st_mtime)]
        self.s.runtime.recorder.start(Configuration());current=self.s.runtime.recorder.name
        space=iter([0,0,0,0,self.s.KEEP_FREE_BYTES])
        with patch.object(self.s.shutil,"disk_usage",side_effect=lambda _:type("Space",(),{"free":next(space,self.s.KEEP_FREE_BYTES)})()):
            self.assertGreaterEqual(self.s.runtime.recorder.make_room(),self.s.KEEP_FREE_BYTES)
        left={p.name for p in self.s.LOGS.glob('LOG_*.csv')}
        self.assertNotIn(names[0],left);self.assertNotIn(names[1],left);self.assertNotIn(names[2],left)
        self.assertIn(names[3],left);self.assertIn(current,left)
        self.assertEqual(len(list(self.s.LOGS.glob('*.meta.json'))),3)
        with patch.object(self.s.shutil,"disk_usage",return_value=type("Space",(),{"free":0})()):
            self.s.runtime.recorder.make_room()
        self.assertEqual({p.name for p in self.s.LOGS.glob('LOG_*.csv')},{current})

    def test_emmc_retention_deletes_videos_and_logs_together_oldest_first(self):
        for n in range(2):
            self.s.runtime.recorder.start(Configuration());self.s.runtime.recorder.stop()
            os.utime(self.s.LOGS/self.s.runtime.recorder.name,(500+n,500+n))
        logs={p.name for p in self.s.LOGS.glob('LOG_*.csv')}
        old_logs=[p.name for p in sorted(self.s.LOGS.glob('LOG_*.csv'),key=lambda p:p.stat().st_mtime)]
        self.s.VIDEOS.mkdir()
        for n in range(3):
            for ext in ('.ts','.csv'):
                path=self.s.VIDEOS/f'2026103{n}_120000_01{ext}';path.write_bytes(b'x');os.utime(path,(1000+n,1000+n))
        (self.s.VIDEOS/'20261032_120000_01.ts.ok').write_text('1 '+'0'*64+' 2026-11-04T00:00:00Z\n')  # collected: first
        (self.s.VIDEOS/'20261031_120000.keep').write_bytes(b'')  # protected and uncollected: never
        recording=self.s.VIDEOS/'20261031_130000_02.ts';recording.write_bytes(b'x')
        earlier=self.s.VIDEOS/'20261031_130000_01.ts';earlier.write_bytes(b'x')  # the session being recorded: its old chapters go too
        (self.s.VIDEOS/'.recording').write_text('boot_id=B\nsession=20261031_130000\nfile=20261031_130000_02.ts\nbt=99\n')
        self.s.runtime.recorder.start(Configuration());current=self.s.runtime.recorder.name
        space=iter([0,0,self.s.KEEP_FREE_BYTES])
        with patch.object(self.s.video_store,'boot_id',return_value='B'),patch.object(self.s.video_store,'boottime',return_value=100):
            with patch.object(self.s.shutil,"disk_usage",side_effect=lambda _:type("Space",(),{"free":next(space,self.s.KEEP_FREE_BYTES)})()):
                self.assertGreaterEqual(self.s.runtime.recorder.make_room(),self.s.KEEP_FREE_BYTES)
            self.assertNotIn('20261032_120000_01.ts',{p.name for p in self.s.VIDEOS.iterdir()})
            self.assertIn('20261030_120000_01.ts',{p.name for p in self.s.VIDEOS.iterdir()})
            self.assertEqual({p.name for p in self.s.LOGS.glob('LOG_*.csv')},logs|{current})
            with patch.object(self.s.shutil,"disk_usage",return_value=type("Space",(),{"free":0})()):
                self.s.runtime.recorder.make_room()
                video=self.s.video_status()
        self.assertEqual({p.name for p in self.s.VIDEOS.iterdir()},
                         {'20261031_120000_01.ts','20261031_120000_01.csv','20261031_120000.keep',recording.name,
                          '.recording','deleted.log'})
        self.assertEqual({p.name for p in self.s.LOGS.glob('LOG_*.csv')},{current})  # the log being written stays
        self.assertEqual([(r['by'],r['name'],r['collected']) for r in self.s.video_store.parse_log((self.s.VIDEOS/'deleted.log').read_text())],
                         [('ecocapture','20261032_120000_01.ts',True),('ecocapture',old_logs[0],False),('ecocapture',old_logs[1],False),
                          ('ecocapture','20261030_120000_01.ts',False),('ecocapture',earlier.name,False)])
        self.assertEqual((video['recording'],video['session'],video['minutes_left'],video['uncollected'],video['kept_sessions'],video['logs']),
                         (True,'20261031_130000',0,1,1,1))

    def test_the_log_being_written_is_named_for_the_recorder_and_a_checked_copy_is_marked(self):
        import hashlib
        self.connected()
        name=self.client.post("/api/log/start", headers=self.headers).json()["name"]
        state=self.s.video_store.parse_kv((self.s.LOGS/'.recording').read_text())
        self.assertEqual((state['file'],state['boot_id']),(name,self.s.video_store.boot_id()))
        self.s.runtime.recorder.append(self.sample())
        self.assertEqual(self.client.post(f"/api/logs/{name}/collected",headers=self.headers,json={"sha256":"0"*64}).status_code,409)
        self.client.post("/api/log/stop", headers=self.headers)
        self.assertFalse((self.s.LOGS/'.recording').exists())
        csv_path=self.s.LOGS/name;can=self.s.LOGS/(name+'.can.jsonl')
        sha=hashlib.sha256(csv_path.read_bytes()).hexdigest();can_sha=hashlib.sha256(can.read_bytes()).hexdigest()
        self.assertEqual(self.client.post(f"/api/logs/{name}/collected",headers=self.headers,json={"sha256":sha}).status_code,409)  # the CAN log too
        self.assertEqual(self.client.post(f"/api/logs/{name}/collected",headers=self.headers,
                                          json={"sha256":sha,"can_sha256":"1"*64}).status_code,409)
        self.assertEqual(self.client.post(f"/api/logs/{name}/collected",json={"sha256":sha,"can_sha256":can_sha}).status_code,403)
        self.assertEqual(self.client.post(f"/api/logs/{name}/collected",headers=self.headers,
                                          json={"sha256":sha,"can_sha256":can_sha}).status_code,200)
        mark=(self.s.LOGS/(name+'.ok')).read_text().split()
        self.assertEqual(mark[:2],[str(csv_path.stat().st_size),sha])
        store=self.s.video_store.scan(self.s.VIDEOS,now_wall=time.time()+600)
        self.assertEqual([(g.name,g.collected) for g in store.logs],[(name,True)])

    def test_removed_sd_closes_backup_without_claiming_sd_saved(self):
        from unittest.mock import AsyncMock
        from fastapi import HTTPException
        self.s.runtime.recorder.start(Configuration())
        self.s.runtime.bridge=AsyncMock()
        self.s.runtime.bridge.command.return_value='stopped'
        self.s.runtime.bridge.call.return_value=json.dumps({'sd_logging':0,'sd_errors':1})
        self.s.runtime.record_sd_first=1
        with self.assertRaises(HTTPException):asyncio.run(self.s.stop_log())
        self.assertIsNone(self.s.runtime.recorder.file)
        self.assertIsNone(self.s.runtime.record_sd_first)
        self.assertTrue(self.s.runtime.auto_started)

    def test_boot_start_uses_verified_sd_start(self):
        from unittest.mock import AsyncMock
        self.connected()
        self.s.runtime.hardware={'sd_mounted':1}
        self.s.runtime.bridge=AsyncMock()
        self.s.runtime.bridge.command.return_value='recording'
        self.s.runtime.bridge.call.return_value=json.dumps({'sd_logging':1,'sd_file':7})
        asyncio.run(self.s.runtime.start_on_boot())
        self.assertIsNotNone(self.s.runtime.recorder.file)
        self.assertEqual(self.s.runtime.record_sd_first,7)

    def test_wifi_state_from_host_agent(self):
        class Response:
            def __init__(self,data,code=200):self.data=data;self.status_code=code
            def json(self):return self.data
        def client(answer):
            class Client:
                def __init__(self,**kw):pass
                async def __aenter__(self):return self
                async def __aexit__(self,*a):return False
                async def get(self,path):
                    if isinstance(answer,Exception):raise answer
                    return answer
            return Client
        cases=[(Response({'state':'100 (connected)','addresses':['192.168.1.5']}),True),
               (Response({'state':'30 (disconnected)','addresses':[]}),False),
               (Response({'state':'70 (connecting (getting IP configuration))','addresses':[]}),False),
               (Response({'state':'unknown','addresses':['10.0.0.2']}),True),
               (Response({'state':'unknown','addresses':[]}),False),
               (Response({'detail':'x'},503),None),
               (self.s.httpx.ConnectError('no agent'),None)]
        for answer,expected in cases:
            with patch.object(self.s.httpx,'AsyncClient',client(answer)):
                self.assertEqual(asyncio.run(self.s.runtime.wifi_connected()),expected,answer)

    def test_missing_sd_still_records_emmc_with_warning(self):
        from unittest.mock import AsyncMock
        self.connected()
        self.s.runtime.bridge=AsyncMock()
        self.s.runtime.hardware={'sd_mounted':0}
        log=asyncio.run(self.s.start_log())
        self.assertTrue(log['active']);self.assertIn('SDカードが認識されていません',log['sd_warning'])
        self.s.runtime.bridge.command.assert_not_called()
        self.assertIsNone(self.s.runtime.record_sd_first)
        self.s.runtime.bridge.command.side_effect=RuntimeError('bridge down')
        log=asyncio.run(self.s.stop_log())
        self.assertFalse(log['active']);self.assertIsNone(self.s.runtime.status()['logging']['sd_warning'])

    def test_failed_sd_start_keeps_emmc_recording(self):
        from unittest.mock import AsyncMock
        self.connected()
        self.s.runtime.bridge=AsyncMock()
        self.s.runtime.hardware={'sd_mounted':1}
        self.s.runtime.bridge.call.return_value=json.dumps({'sd_logging':0,'sd_file':3})
        self.s.runtime.bridge.command.return_value='rejected'
        log=asyncio.run(self.s.start_log())
        self.assertTrue(log['active']);self.assertIn('本体（eMMC）にだけ',log['sd_warning'])
        self.assertIsNone(self.s.runtime.record_sd_first)

    def test_sd_lost_while_recording_is_warned(self):
        from unittest.mock import AsyncMock
        self.connected()
        self.s.runtime.bridge=AsyncMock()
        self.s.runtime.hardware={'sd_mounted':1,'sd_logging':1}
        self.s.runtime.recorder.start(Configuration());self.s.runtime.record_sd_first=1
        self.assertIsNone(self.s.runtime.status()['logging']['sd_warning'])
        self.s.runtime.hardware={'sd_mounted':1,'sd_logging':0,'sd_errors':1}
        self.assertIn('eMMC',self.s.runtime.status()['logging']['sd_warning'])

    def test_stop_does_not_claim_unconfirmed_sd_save(self):
        from unittest.mock import AsyncMock
        from fastapi import HTTPException
        self.connected()
        self.s.runtime.bridge=AsyncMock()
        self.s.runtime.hardware={'sd_mounted':1,'sd_logging':1}
        self.s.runtime.recorder.start(self.s.runtime.config)
        self.s.runtime.bridge.command.return_value='stopped'
        self.s.runtime.bridge.call.return_value=json.dumps({'sd_logging':1})
        with self.assertRaises(HTTPException):asyncio.run(self.s.stop_log())
        self.assertIsNotNone(self.s.runtime.recorder.file)

    def test_sd_listing_single_flight_and_new_file_invalidates_cache(self):
        from unittest.mock import AsyncMock
        async def check():
            bridge = AsyncMock()
            bridge.command.return_value = json.dumps([{'index': 1, 'size': 512}])
            self.s.runtime.bridge = bridge
            self.s.runtime.hardware = {'sd_logging': 0, 'sd_file': 1, 'sd_bytes': 512}
            first, second = await asyncio.gather(self.s.sd_logs(), self.s.sd_logs())
            self.assertEqual(first, second)
            self.assertEqual(bridge.command.await_count, 1)
            await self.s.sd_logs()
            self.assertEqual(bridge.command.await_count, 1)
            self.s.runtime.hardware['sd_file'] = 2
            await self.s.sd_logs()
            self.assertEqual(bridge.command.await_count, 2)
        asyncio.run(check())

    def test_field_link_gives_key_urls_and_qr(self):
        from unittest.mock import AsyncMock
        with patch.object(self.s, 'device_request', AsyncMock(return_value={'addresses': ['192.168.43.20']})):
            data = self.client.get('/api/field/link').json()
        token = (Path(self.temp.name) / 'field_token').read_text().strip()
        self.assertEqual(data['urls'], [f'http://uno-q.local:8082/?k={token}', f'http://192.168.43.20:8082/?k={token}'])
        self.assertIn('<svg', data['svg'])
        self.assertEqual(data['qr_url'], f'http://192.168.43.20:8082/?k={token}')
        # The admin UI stays localhost-only: the key is not handed to the LAN from here.
        self.assertEqual(self.client.get('/api/field/link', headers={'host': 'uno-q.local:8080'}).status_code, 403)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.environ["ECOCAPTURE_DATA"] = self.temp.name
        import server
        self.s = importlib.reload(server)
        self.client = TestClient(self.s.app)
        self.headers = {"X-EcoCapture": "1"}

    def tearDown(self):
        self.s.runtime.recorder.stop()
        self.client.close()
        self.temp.cleanup()

    def sample(self):
        return {"schema": 1, "demo": False, "source": "logger-v2-hardware", "seq": 1, "mcu_ms": 20,
                "values": {k: 0 for k in CHANNELS}, "host_utc": "2026-09-06T00:00:00Z"}

    def connected(self):
        self.s.runtime.sample = self.sample()
        self.s.runtime.received_at = time.monotonic()

    def test_lap_line_api_and_csv_columns(self):
        from models import LAP_CHANNELS
        self.assertEqual(self.client.post('/api/lap/here', headers=self.headers).status_code, 409)
        self.assertEqual(self.client.get('/api/lap/code').status_code, 409)  # no control line yet
        self.connected()
        self.s.runtime.sample['values'].update(Lat=None, Lon=None)
        self.assertEqual(self.client.post('/api/lap/here', headers=self.headers).status_code, 409)
        self.s.runtime.sample['values'].update(Lat=36.5, Lon=140.2, GPSSpeed=0)
        line = self.client.post('/api/lap/here', headers=self.headers, json={'width_m': 40}).json()['line']
        self.assertTrue(line['enabled']); self.assertEqual(line['width_m'], 40); self.assertIsNone(line['bearing'])
        self.assertEqual(self.client.post('/api/lap', headers=self.headers, json={'min_lap_s': 1}).status_code, 400)
        self.assertEqual(self.client.post('/api/lap', headers=self.headers, json={'min_lap_s': 90}).json()['line']['min_lap_s'], 90)
        self.assertEqual(self.client.post('/api/lap', headers=self.headers, json={'bearing': 90}).json()['line']['bearing'], 90)
        self.assertIsNone(self.client.post('/api/lap', headers=self.headers, json={'bearing': None}).json()['line']['bearing'])
        line = self.client.post('/api/lap', headers=self.headers, json={'start': {'lat': 36.49, 'lon': 140.2, 'bearing': None}, 'total_laps': 7}).json()['line']
        self.assertEqual((line['start']['lat'], line['start']['width_m'], line['total_laps']), (36.49, 30, 7))
        self.assertIsNone(self.client.post('/api/lap', headers=self.headers, json={'start': None}).json()['line']['start'])
        self.assertEqual(self.client.post('/api/lap', headers=self.headers, json={'goal': {'lat': 99, 'lon': 0}}).status_code, 400)
        self.s.runtime.sample['values'].update(GPSSpeed=12, Yaw=90)
        goal = self.client.post('/api/lap/here', headers=self.headers, json={'target': 'goal'}).json()['line']['goal']
        self.assertEqual((goal['lat'], goal['bearing']), (36.5, 90))
        code = self.client.get('/api/lap/code').json()  # the QR for the Android loggers
        self.assertTrue(code['text'].startswith('ECOLINES1|c=36.5000000,140.2000000,-,40|s=-|g=36.5000000,140.2000000,90.0,30|'))
        self.assertTrue(code['text'].endswith('|id=' + code['id']))
        self.assertTrue(code['svg'].startswith('<svg'))
        self.assertEqual(code['unknown_bearing'], ['コントロール'])
        self.assertEqual(self.client.post('/api/lap/here', headers=self.headers, json={'target': 'pit'}).status_code, 400)
        self.assertEqual(self.client.post('/api/lap/reset', headers=self.headers).json()['values']['LapCount'], 0)
        self.assertEqual(self.client.post('/api/lap/reset').status_code, 403)
        self.s.runtime.recorder.start(Configuration())
        sample = self.sample(); sample['lap'] = {'LapCount': 2, 'LapTime': 1.25}
        self.s.runtime.recorder.append(sample); self.s.runtime.recorder.stop()
        with (self.s.LOGS / self.s.runtime.recorder.name).open(encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]['LapCount'], '2'); self.assertEqual(rows[0]['LapTime'], '1.25'); self.assertEqual(rows[0]['BestLap'], '')
        self.assertTrue(set(LAP_CHANNELS) <= set(rows[0]))

    def test_imu_mount_column_api_and_saved_file(self):
        mount = self.s.runtime.mount
        self.assertEqual(self.client.post('/api/imu/mount/level', headers=self.headers).status_code, 409)  # no MCU yet
        self.connected()
        self.assertEqual(self.client.post('/api/imu/mount/level', headers=self.headers).status_code, 409)  # no 2 s of rows
        for _ in range(200): mount.add([0, 0, 9.80665], [0, 0, 0], None)
        data = self.client.post('/api/imu/mount/level', headers=self.headers).json()
        self.assertEqual((data['up'], data['manual'], data['tilt_deg']), ([0, 0, 1.0], True, 0.0))
        self.assertEqual(json.loads((Path(self.temp.name) / 'imu_mount.json').read_text())['up'], [0, 0, 1.0])
        self.assertEqual(self.client.get('/api/status').json()['imu_mount']['message'][:10], '1G：手動で取った値')
        self.s.runtime.recorder.start(Configuration(), mount.state())
        first = self.sample(); first['imu_mount'] = mount.state()
        same = self.sample(); same['imu_mount'] = mount.state()          # unchanged: the same object, not written again
        self.s.runtime.recorder.append(first); self.s.runtime.recorder.append(same)
        self.client.post('/api/imu/mount/reset', headers=self.headers)
        later = self.sample(); later['imu_mount'] = mount.state()
        self.s.runtime.recorder.append(later); name = self.s.runtime.recorder.name; self.s.runtime.recorder.stop()
        with (self.s.LOGS / name).open(encoding='utf-8', newline='') as f:
            cells = [row['imu_mount'] for row in csv.DictReader(f)]
        self.assertEqual(json.loads(cells[0])['up'], [0, 0, 1.0]); self.assertEqual(cells[1], ''); self.assertIsNone(json.loads(cells[2])['up'])
        meta = json.loads((self.s.LOGS / (name + '.meta.json')).read_text(encoding='utf-8'))
        self.assertEqual(meta['imu_mount']['up'], [0, 0, 1.0]); self.assertIn('LatAccel (+ right)', meta['imu_axes'])
        self.assertIsNone(json.loads((Path(self.temp.name) / 'imu_mount.json').read_text())['up'])

    def test_sd_decoder_download_carries_imu_mount(self):
        import io, zipfile
        response = self.client.get('/api/sd/decoder')
        self.assertEqual(sorted(zipfile.ZipFile(io.BytesIO(response.content)).namelist()), ['imu_mount.py', 'sd_decode.py'])

    def test_can_signals_are_one_column_each(self):
        oil = Signal(name='OilTemp', unit='°C', channel=2, can_id=0x600, byte_offset=0, data_type='int16', scale=.01, conversion='sensorhub_oiltemp')
        rpm = Signal(name='RPM', unit='rpm', can_id=0x201, byte_offset=0, scale=.25)          # a fixed channel: written in RPM, not twice
        seq = Signal(name='seq', can_id=0x300, byte_offset=0)                                 # clashes with a base column
        boost = Signal(name='Boost', unit='kPa', channel=2, can_id=0x500, byte_offset=0)
        self.s.runtime.recorder.start(Configuration(signals=[oil, rpm, seq, boost]))
        sample = self.sample(); sample['values']['RPM'] = 1000.0
        sample['can_signals'] = {'OilTemp': 6016 * .01, 'OilTempState': 0, 'OilTempOpen': 0, 'RPM': 1000.0, 'seq': 5}
        self.s.runtime.recorder.append(sample); name = self.s.runtime.recorder.name; self.s.runtime.recorder.stop()
        with (self.s.LOGS / name).open(encoding='utf-8', newline='') as f:
            header = next(csv.reader(f)); f.seek(0); row = next(csv.DictReader(f))
        self.assertNotIn('can_signals', header)
        self.assertEqual(header[-4:], ['OilTemp', 'OilTempState', 'CAN_seq', 'Boost'])
        self.assertEqual(header.count('RPM'), 1)
        self.assertEqual((row['OilTemp'], row['OilTempState'], row['CAN_seq'], row['Boost'], row['RPM']), ('60.16', '0', '5', '', '1000.0'))
        meta = json.loads((self.s.LOGS / (name + '.meta.json')).read_text(encoding='utf-8'))
        self.assertEqual((meta['units']['OilTemp'], meta['units']['Boost']), ('°C', 'kPa'))

    def test_stale_data_cleared_and_no_disconnected_recording(self):
        self.connected()
        self.assertIsNotNone(self.client.get("/api/telemetry").json()["sample"])
        self.s.runtime.received_at -= 2
        self.assertIsNone(self.client.get("/api/telemetry").json()["sample"])
        self.assertEqual(self.client.post("/api/log/start", headers=self.headers).status_code, 409)

    def test_csv_lifecycle_active_protection_and_metadata(self):
        self.connected()
        response = self.client.post("/api/log/start", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        name = response.json()["name"]
        self.s.runtime.recorder.append(self.sample())
        self.assertEqual(self.client.delete(f"/api/logs/{name}", headers=self.headers).status_code, 409)
        self.assertEqual(self.client.get(f"/api/logs/{name}/download").status_code, 409)
        self.assertEqual(self.client.post("/api/config", headers=self.headers, json=Configuration().model_dump()).status_code, 409)
        self.client.post("/api/log/stop", headers=self.headers)
        content = self.client.get(f"/api/logs/{name}/download").text
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["demo"], "0")
        self.assertEqual(rows[0]["source"], "logger-v2-hardware")
        meta = self.client.get(f"/api/logs/{name}/metadata").json()
        self.assertEqual(meta["state"], "closed")
        self.assertEqual(meta["rows"], 1)
        self.assertTrue((self.s.LOGS / (name + ".can.jsonl")).exists())
        self.assertEqual(self.client.delete(f"/api/logs/{name}", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get(f"/api/logs/{name}/download").status_code, 404)
        # the CAN log (often the bigger file) goes with it, so deleting a log really frees the space
        self.assertEqual([p.name for p in self.s.LOGS.iterdir() if p.name.startswith(name)], [])

    def test_config_validation_and_persistence(self):
        data = Configuration().model_dump()
        data["signals"] = [{"name": "TestRPM", "can_id": 512, "byte_offset": 0, "scale": 0.25}]
        self.assertEqual(self.client.post("/api/config", headers=self.headers, json=data).status_code, 200)
        self.assertEqual(self.s.Runtime().config.signals[0].scale, 0.25)
        data["signals"][0]["can_id"] = 2048
        self.assertEqual(self.client.post("/api/config", headers=self.headers, json=data).status_code, 422)
        data["signals"][0]["can_id"] = 512
        data["signals"][0]["byte_offset"] = 7
        self.assertEqual(self.client.post("/api/config", headers=self.headers, json=data).status_code, 422)
        self.assertFalse(self.client.get("/api/can/channels").json()["applied"])

    def test_cross_origin_operations_rejected(self):
        self.assertEqual(self.client.post("/api/log/stop").status_code, 403)
        self.assertEqual(self.client.post("/api/log/stop", headers={**self.headers, "Origin": "https://untrusted.example"}).status_code, 403)
        self.assertEqual(self.client.post("/api/log/stop", headers={**self.headers, "Origin": "http://testserver"}).status_code, 200)

    def test_podium_secret_redaction_and_recording_independence(self):
        self.connected();self.s.runtime.recorder.start(Configuration())
        # device_id (the removed direct path's key, SP-9-4) may still come from an old client: dropped, not kept.
        response=self.client.post('/api/podium',headers=self.headers,json={'device_id':'private-key','password':'private-apn'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['config']['password_configured'])
        self.assertNotIn('key_configured',response.json()['config'])
        self.assertNotIn('private-key',(self.s.ROOT/'private'/'podium.json').read_text())
        for path in ('/api/podium','/api/status','/api/config'):
            self.assertNotIn('private-',self.client.get(path).text)
        response=self.client.post('/api/podium',headers=self.headers,json={'enabled':True,'password':'private-bad'})
        self.assertEqual(response.status_code,400);self.assertNotIn('private-',response.text)
        response=self.client.post('/api/podium',headers=self.headers,json={'destination':'podium','device_id':'private-key'})
        self.assertEqual(response.status_code,400);self.assertNotIn('private-',response.text)
        self.assertTrue(self.s.runtime.recorder.file)
        self.assertNotIn('private-',json.dumps(self.s.public_snapshot()))

    def test_lte_check_stays_rf_off_and_cleans_up(self):
        commands=[]
        class Bridge:
            async def call(self,*a):return json.dumps({'power':0,'overflows':0,'rx_bytes':100,'tx_bytes':50})
        class Modem:
            def __init__(self,*a):self.uart=self
            async def power(self,on):commands.append('POWER'+str(on))
            async def command(self,text,*a):
                commands.append(text)
                return b'+CAOPEN +CASEND +CARECV SIMCOM_SIM7070\r\nOK\r\n'
            async def close(self):await self.power(False)
        self.s.runtime.bridge=Bridge()
        with patch('sim7070.SIM7070',Modem):
            response=self.client.post('/api/podium/check',headers=self.headers,json={})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['power_off'])
        self.assertIn('AT+CFUN=0',commands);self.assertNotIn('AT+CFUN=1',commands)
        self.assertEqual(commands.count('AT+CSQ'),20);self.assertEqual(commands[-1],'POWERFalse')

    def test_usb_admin_rejects_nonlocal_hostname(self):
        self.assertEqual(self.client.get('/api/config',headers={'Host':'untrusted.example'}).status_code,403)

    def test_admin_page_can_only_be_framed_by_local_racecapture(self):
        policy=self.client.get('/').headers['content-security-policy']
        self.assertIn('frame-ancestors http://127.0.0.1:6080 http://localhost:6080',policy)
        self.assertNotIn('frame-ancestors *',policy)

    def test_public_export_only_contains_allowed_fields(self):
        self.connected()
        self.s.runtime.sample['password']='private-example'
        self.s.runtime.config_error='private-error'
        self.s.runtime.recorder.name='private-log-path'
        snapshot=self.s.public_snapshot()
        self.assertNotIn('private-',json.dumps(snapshot))
        self.assertNotIn('storage_free_bytes',snapshot['status'])
        self.assertNotIn('config_error',snapshot['status'])
        self.assertNotIn('name',snapshot['status']['logging'])

    def test_storage_full_stops_recorder(self):
        self.connected()
        self.s.runtime.recorder.start(Configuration())
        with patch.object(self.s.shutil, "disk_usage", return_value=type("Space", (), {"free": 0})()):
            self.s.runtime.recorder.append(self.sample())
        self.assertFalse(self.s.runtime.recorder.status()["active"])
        self.assertIn("reserve", self.s.runtime.recorder.error)

    def test_path_and_invalid_data_rejected(self):
        for name in ("../config.json", "/etc/passwd", "something.csv"):
            with self.assertRaises(Exception):
                self.s.log_path(name)
        good = self.sample()
        validate_sample(good)
        good["values"]["Speed"] = float("nan")
        with self.assertRaises(ValueError): validate_sample(good)
        with self.assertRaises(ValueError): validate_sample({"demo": False})
        with self.assertRaises(ValidationError): Signal(name="A", can_id=1, byte_offset=0, scale=float("inf"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
