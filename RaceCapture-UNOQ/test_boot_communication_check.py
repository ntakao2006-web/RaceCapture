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
if __name__=='__main__':unittest.main()
