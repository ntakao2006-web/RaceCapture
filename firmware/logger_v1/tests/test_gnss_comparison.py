import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from compare_gnss_profiles import analyze_rows, summarize
from gnss_profile import select


def rows(period=100, stop_ms=None, no_fix=False, wrap=False):
    result=[]
    for tick in range(0,10000,10):
        epoch=(min(tick,stop_ms) if stop_ms is not None else tick)//period*period
        result.append({'monotonic_us':str(tick*1000),'GPSTow':str((epoch+(604799000 if wrap else 0))%604800000),
            'GNSSAge':str(tick-epoch),'GPSFix':'0' if no_fix else '3',
            'Lat':'' if no_fix else '35.60','Lon':'' if no_fix else '139.74',
            'GPSSats':'12','GPSHAcc':'3.5'})
    return result


class AnalysisTests(unittest.TestCase):
    def test_held_rows_are_not_100hz_gnss(self):
        result=analyze_rows(rows(),100,True)
        self.assertEqual(result['epochs'],100)
        self.assertAlmostEqual(result['valid_fix_hz'],10,delta=.02)
        self.assertGreater(result['epoch_delivery_pct'],99)
        self.assertEqual(result['fresh_fix_pct'],100)
        self.assertEqual(result['static_scatter_p95_m'],0)
        self.assertEqual(result['hacc_estimate_p95_m'],3.5)

    def test_silent_tail_fails_even_if_fix_flag_held(self):
        result=analyze_rows(rows(stop_ms=4900),100)
        self.assertLess(result['epoch_delivery_pct'],51)
        self.assertLess(result['fresh_fix_pct'],53)
        self.assertGreater(result['longest_no_fresh_fix_s'],4.8)

    def test_no_fix_is_not_no_pvt(self):
        result=analyze_rows(rows(no_fix=True),100,True)
        self.assertGreater(result['epoch_delivery_pct'],99)
        self.assertEqual(result['fresh_fix_pct'],0)
        self.assertIsNone(result['static_scatter_p95_m'])
        self.assertIsNone(result['hacc_estimate_p95_m'])

    def test_week_rollover_and_noninteger_rate(self):
        result=analyze_rows(rows(period=67,wrap=True),67)
        self.assertEqual(result['max_epoch_step_ms'],67)
        self.assertGreater(result['epoch_delivery_pct'],99)
        self.assertAlmostEqual(result['configured_hz'],14.925373,places=5)

    def test_reboot_or_reordered_csv_rejected(self):
        source=rows(); source[10]['monotonic_us']='0'
        with self.assertRaises(ValueError): analyze_rows(source,100)

    def test_one_trial_never_selects_a_winner(self):
        result=summarize([dict(profile='four_10',quality_gate=True,fresh_fix_pct=100,
                               epoch_delivery_pct=100,configured_hz=10)])
        self.assertIsNone(result['selected_profile'])
        self.assertFalse(result['profiles'][0]['repeated_quality_pass'])


class FakeClient:
    def __init__(self): self.calls=[]; self.logging=True
    def query(self,command):
        self.calls.append(command)
        key=next(iter(command))
        if key=='getGnssProfiles': return {key:{'profiles':[{'id':'four_10','supported':True}]}}
        if key=='getStatus': return {'status':{'logging':{'status':1 if self.logging else 0,
            'closed':not self.logging,'file':'test.csv' if self.logging else ''}}}
        if key=='setLogging': self.logging=command[key]; return {key:{'rc':1}}
        if key=='setGnssProfile':
            assert not self.logging
            return {key:{'rc':1}}
        if key=='getGnssDiagnostics': return {key:{'configuration':{'verified':True,'profileId':'four_10'}}}
        raise AssertionError(command)


class SelectionTests(unittest.TestCase):
    def test_selection_closes_and_restores_sd_without_persisting(self):
        c=FakeClient(); cfg=select(c,'four_10')
        self.assertEqual(cfg['profileId'],'four_10'); self.assertTrue(c.logging)
        keys=[next(iter(x)) for x in c.calls]
        self.assertLess(keys.index('setLogging'),keys.index('setGnssProfile'))
        self.assertNotIn('flashCfg',keys); self.assertNotIn('clearSd',keys)

    def test_timeout_restores_logging(self):
        c=FakeClient()
        with self.assertRaises(TimeoutError): select(c,'four_10',timeout=0)
        self.assertTrue(c.logging)

    def test_unsupported_profile_does_not_stop_logging(self):
        c=FakeClient()
        with self.assertRaises(ValueError): select(c,'invalid')
        self.assertEqual(len(c.calls),1); self.assertTrue(c.logging)


if __name__=='__main__': unittest.main()
