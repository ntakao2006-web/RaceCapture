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
    def test_backup_retention_keeps_three_sessions(self):
        for _ in range(5):
            self.s.runtime.recorder.start(Configuration());self.s.runtime.recorder.stop()
        self.assertEqual(len(list(self.s.LOGS.glob('LOG_*.csv'))),3)
        self.assertEqual(len(list(self.s.LOGS.glob('*.meta.json'))),3)
        self.assertEqual(len(list(self.s.LOGS.glob('*.can.jsonl'))),3)

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

    def test_start_requires_sd_and_stop_does_not_claim_unconfirmed_save(self):
        from unittest.mock import AsyncMock
        from fastapi import HTTPException
        self.connected()
        self.s.runtime.bridge=AsyncMock()
        with self.assertRaises(HTTPException):asyncio.run(self.s.start_log())
        self.assertIsNone(self.s.runtime.recorder.file)
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
