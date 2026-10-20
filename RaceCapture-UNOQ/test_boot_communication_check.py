import unittest
from unittest.mock import patch,MagicMock
import boot_communication_check as b
class Tests(unittest.TestCase):
    def test_recover_only_initial_missing_method(self):
        s={'received':0,'error':'Arduino Router: method logger.status not available','logging':{'active':False}}
        self.assertTrue(b.can_recover(s))
        self.assertFalse(b.can_recover(dict(s,received=1)))
        self.assertFalse(b.can_recover(dict(s,logging={'active':True})))
        self.assertFalse(b.can_recover(dict(s,hardware={'sd_logging':1})))
        self.assertFalse(b.can_recover(dict(s,error='timeout')))
        self.assertFalse(b.can_recover(None))
    def test_healthy_boot_no_reset(self):
        marker=MagicMock();marker.exists.return_value=False
        with patch.object(b,'MARKER',marker),patch.object(b,'wait_received',return_value={'connected':True,'received':10}),patch.object(b.subprocess,'run') as run:
            b.main();run.assert_not_called();marker.write_text.assert_called_once()
    def test_recovery_is_bounded(self):
        marker=MagicMock();marker.exists.return_value=False
        bad={'received':0,'error':'method logger.status not available'}
        with patch.object(b,'MARKER',marker),patch.object(b,'wait_received',return_value=bad),patch.object(b.subprocess,'run') as run:
            with self.assertRaises(SystemExit):b.main()
            self.assertEqual(run.call_count,6)
            self.assertNotIn('stty',[call[0][0][0] for call in run.call_args_list])
    def fake_clock(self):
        now=[0.0]
        def sleep(s):now[0]+=s
        return patch.object(b.time,'monotonic',lambda:now[0]),patch.object(b.time,'sleep',sleep),now
    def test_missing_method_gives_up_after_10_s_not_40(self):
        bad={'received':0,'error':'method logger.status not available','logging':{'active':False}}
        mono,sleep,now=self.fake_clock()
        with mono,sleep,patch.object(b,'read_status',return_value=bad):
            self.assertEqual(b.wait_received(),bad)
        self.assertLessEqual(now[0],11)
    def test_web_not_answering_still_waits_the_full_time(self):
        mono,sleep,now=self.fake_clock()
        with mono,sleep,patch.object(b,'read_status',return_value=None):
            self.assertIsNone(b.wait_received())
        self.assertGreaterEqual(now[0],40)
    def test_slow_but_healthy_start_is_not_cut_short(self):
        bad={'received':0,'error':'method logger.status not available','logging':{'active':False}}
        good={'connected':True,'received':5}
        replies=iter([bad]*6+[good])
        mono,sleep,now=self.fake_clock()
        with mono,sleep,patch.object(b,'read_status',side_effect=lambda:next(replies)):
            self.assertEqual(b.wait_received(),good)
if __name__=='__main__':unittest.main()
