import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import device_agent as agent


class DeviceTests(unittest.TestCase):
    def test_nmcli_escaped_network_names(self):
        self.assertEqual(agent.nm_fields(r'*:Network\: A:82:WPA2'),['*','Network: A','82','WPA2'])
    def test_wifi_secret_not_in_arguments_and_failed_profile_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);keep=path/'existing.nmconnection';keep.write_text('existing')
            calls=[]
            def run(args,timeout=12):
                calls.append(args)
                if 'up' in args:raise ValueError('Connection failure')
                return ''
            with patch.object(agent,'NM_DIR',path),patch.object(agent,'command',side_effect=run),patch.object(agent.subprocess,'run'):
                with self.assertRaises(ValueError):agent.wifi_connect({'ssid':'test ssid','password':'test passphrase','security':'wpa-psk'})
            self.assertEqual(list(path.iterdir()),[keep])
            self.assertNotIn('test passphrase',str(calls))
    def test_wifi_success_uses_restricted_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            with patch.object(agent,'NM_DIR',path),patch.object(agent,'command',return_value=''),patch.object(agent,'wifi_status',return_value={'addresses':['192.0.2.2']}):
                result=agent.wifi_connect({'ssid':'test ssid','password':'test passphrase','security':'wpa-psk'})
            self.assertTrue(result['connected']);self.assertNotIn('password',json.dumps(result))
            text=next(path.iterdir()).read_text();self.assertIn('psk=test\\spassphrase',text);self.assertIn('autoconnect=true',text)
    def test_wifi_validation(self):
        for value in [{'ssid':'','password':'abcdefgh'},{'ssid':'x','password':'short'},{'ssid':'x','security':'enterprise'},{'ssid':'x'*33,'security':'open'}]:
            with self.assertRaises(ValueError):agent.wifi_connect(value)
    def test_metrics_cpu_memory_and_process_deltas(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);proc=root/'proc';proc.mkdir();(proc/'123').mkdir();(root/'sys/class/thermal').mkdir(parents=True)
            (proc/'meminfo').write_text('MemTotal: 1000 kB\nMemAvailable: 400 kB\nSwapTotal: 200 kB\nSwapFree: 180 kB\n');(proc/'uptime').write_text('10.0 5.0')
            def stat(ticks):
                parts=['0']*22;parts[0]='S';parts[11]=str(ticks);parts[12]='0';parts[19]='12345';parts[21]='10';return '123 (worker) '+' '.join(parts)
            (proc/'stat').write_text('cpu 100 0 100 800 0 0 0 0');(proc/'123/stat').write_text(stat(10))
            with patch.object(agent,'Path',side_effect=lambda p:root/str(p).lstrip('/')),patch.object(agent.os,'sysconf',side_effect=lambda name:100 if name=='SC_CLK_TCK' else 4096,create=True),patch.object(agent.os,'getloadavg',return_value=(0,0,0),create=True),patch.object(agent.shutil,'disk_usage',return_value=type('Disk',(),{'total':1000,'free':500})()),patch.object(agent.time,'monotonic',side_effect=[10,13,13]):
                metrics=agent.Metrics();metrics.sample();(proc/'stat').write_text('cpu 120 0 120 860 0 0 0 0');(proc/'123/stat').write_text(stat(20));metrics.sample();value=metrics.get()
            self.assertEqual(value['cpu_percent'],40);self.assertEqual(value['memory_used'],600*1024);self.assertEqual(value['processes'][0]['rss_bytes'],40960);self.assertEqual(value['processes'][0]['cpu_percent'],3.3)

if __name__=='__main__':unittest.main(verbosity=2)
