import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from racecapture_guard import RecoveryPolicy
from setup_racecapture_dashboard import configure

class RecoveryTests(unittest.TestCase):
    def test_acquisition_recovers_on_its_own(self):
        p=RecoveryPolicy(20)
        self.assertFalse(p.observe(0,1,True))
        self.assertFalse(p.observe(2,2,True))
        self.assertFalse(p.observe(3,2,False))
        self.assertFalse(p.observe(30,2,True))
        self.assertFalse(p.observe(34,3,True))
        self.assertFalse(p.observe(36,4,True))
    def test_stalled_after_usb_returns(self):
        p=RecoveryPolicy(20)
        p.observe(0,1,True);p.observe(2,2,True)
        self.assertFalse(p.observe(30,2,False))
        self.assertFalse(p.observe(31,2,True))
        self.assertTrue(p.observe(36,2,True))
        p.restarted(36)
        self.assertFalse(p.observe(80,2,True))
    def test_recording_off_and_no_data_never_restart(self):
        p=RecoveryPolicy(20)
        self.assertFalse(p.observe(0,1,True))
        self.assertFalse(p.observe(100,1,True))
        p.observe(101,2,True)
        self.assertFalse(p.observe(130,2,True,False))
        self.assertFalse(p.observe(170,None,True,False))
    def test_restart_limit(self):
        p=RecoveryPolicy(20);p.restarts=[0,100,200]
        p.observe(201,1,True);p.observe(202,2,True)
        self.assertFalse(p.observe(250,2,True))
        self.assertTrue(p.observe(650,2,True))
    def test_dashboard_retains_existing(self):
        old={'dash_name':'Mine','gauges':[{'config':{'Gauge Type':{'gauge':'Digital'}}}]}
        p={'dashboard':{'old':old},'general_prefs':{'dashboard_preferences':{},'preferences':{}}}
        configure(p)
        self.assertEqual(p['dashboard']['old'],old)
        names=[g['config']['Channel']['channel'] for g in p['dashboard']['dashboard_logger_v1_gnss_imu']['gauges']]
        self.assertIn('Lat',names);self.assertIn('Lon',names)

if __name__=='__main__':unittest.main()
