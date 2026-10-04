"""Public surface has no administrative operations, even via direct API requests."""
import importlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from fastapi.testclient import TestClient


class PublicTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();os.environ['ECOCAPTURE_PUBLIC_DATA']=self.temp.name
        import public_server
        self.server=importlib.reload(public_server);self.client=TestClient(self.server.app)
    def tearDown(self):self.client.close();self.temp.cleanup()
    def test_admin_routes_not_available(self):
        for path in ['/api/podium','/api/config','/api/device/wifi','/api/device/system','/api/device/sharing','/api/logs','/docs','/openapi.json','/app.js','/device.js','/server.py','/../web/index.html']:
            self.assertEqual(self.client.get(path).status_code,404,path)
        for path in ['/api/device/wifi/connect','/api/log/start','/api/config','/api/device/sharing']:
            self.assertEqual(self.client.post(path,json={'enabled':True},headers={'X-EcoCapture':'1'}).status_code,403,path)
        self.assertEqual(self.client.delete('/api/logs/a').status_code,403)
    def test_static_document_has_no_admin_controls(self):
        result=self.client.get('/');self.assertEqual(result.status_code,200)
        for text in ['wifi-password','start-log','config-form','device.js','Settings / CAN','UNO Q / 管理']:
            self.assertNotIn(text,result.text)
        self.assertIn('viewer.js',result.text)
    def test_stale_export_invalidates_values(self):
        path=Path(self.temp.name)/'telemetry.json'
        sample={'type':'telemetry','status':{'connected':True,'receive_hz':20,'logging':{'active':True}},'sample':{'seq':1},'_exported_monotonic':time.monotonic()}
        path.write_text(json.dumps(sample));self.assertIsNotNone(self.client.get('/api/telemetry').json()['sample'])
        sample['_exported_monotonic']-=5;path.write_text(json.dumps(sample));result=self.client.get('/api/telemetry').json();self.assertIsNone(result['sample']);self.assertFalse(result['status']['connected']);self.assertIsNone(result['status']['logging']['active'])
    def test_missing_export_reports_disconnected(self):
        self.assertFalse(self.client.get('/api/telemetry').json()['status']['connected'])

if __name__=='__main__':unittest.main(verbosity=2)
