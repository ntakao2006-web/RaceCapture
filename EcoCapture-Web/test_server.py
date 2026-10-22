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
        space=iter([0,0,0,self.s.KEEP_FREE_BYTES])
        with patch.object(self.s.shutil,"disk_usage",side_effect=lambda _:type("Space",(),{"free":next(space,self.s.KEEP_FREE_BYTES)})()):
            self.assertGreaterEqual(self.s.runtime.recorder.make_room(),self.s.KEEP_FREE_BYTES)
        left={p.name for p in self.s.LOGS.glob('LOG_*.csv')}
        self.assertNotIn(names[0],left);self.assertNotIn(names[1],left);self.assertNotIn(names[2],left)
        self.assertIn(names[3],left);self.assertIn(current,left)
        self.assertEqual(len(list(self.s.LOGS.glob('*.meta.json'))),3)
        with patch.object(self.s.shutil,"disk_usage",return_value=type("Space",(),{"free":0})()):
            self.s.runtime.recorder.make_room()
        self.assertEqual({p.name for p in self.s.LOGS.glob('LOG_*.csv')},{current})

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
        self.assertEqual(self.client.delete(f"/api/logs/{name}", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get(f"/api/logs/{name}/download").status_code, 404)

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
        response=self.client.post('/api/podium',headers=self.headers,json={'device_id':'private-key','password':'private-apn'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['config']['key_configured'])
        for path in ('/api/podium','/api/status','/api/config'):
            self.assertNotIn('private-',self.client.get(path).text)
        response=self.client.post('/api/podium',headers=self.headers,json={'enabled':True,'device_id':'private-bad-key'})
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
