import json
import unittest

import ecologger_menu as m


def output(status=None, lap=None, screen='ecocapture-dash: active (power-on: enabled)\nracecapture-app: inactive (power-on: disabled)',
           temps='47800\n52100', uptime='891.16 2424.02'):
    return (f"@@S\n{json.dumps(status) if status else ''}\n@@L\n{json.dumps(lap) if lap else ''}\n"
            f"@@D\n{screen}\n@@H\n{temps}\n@@U\n{uptime}\n")


STATUS = {
    'connected': True, 'receive_hz': 99.6, 'storage_free_bytes': 5 * 2**30,
    'sensors': {'imu': '正常', 'gnss': '3D 12衛星', 'can': 'CAN1 0', 'sd': '記録中 EL1.BIN', 'camera': '接続'},
    'logging': {'active': True, 'name': 'LOG_x.csv', 'elapsed_s': 3725, 'sd_warning': None},
    'video': {'recording': True, 'minutes_left': 190, 'uncollected': 2, 'uncollected_bytes': 3 * 2**30},
    'podium': {'enabled': True, 'state': 'streaming', 'message': '中継サーバーへ送信中', 'radio': {'rsrp': -98}},
}
LAP = {'values': {'LapCount': 12}, 'line': {'enabled': True}}


class SummarizeTests(unittest.TestCase):
    def rows(self, **kw):
        return {name: (value, warn) for name, value, warn in m.summarize(output(**kw))}

    def test_all_well_has_no_warnings(self):
        rows = self.rows(status=STATUS, lap=LAP)
        self.assertEqual([k for k, (_, w) in rows.items() if w], [])
        self.assertEqual(rows['記録'][0], '記録中 1時間02分（LOG_x.csv）')
        self.assertEqual(rows['ラップ'][0], '12周（ライン 有効）')
        self.assertEqual(rows['HDMIの画面'][0], 'EcoCapture DASH')
        self.assertEqual(rows['本体の温度'][0], '52℃')
        self.assertIn('RSRP -98 dBm', rows['LTE'][0])

    def test_stopped_logging_and_no_gps_are_warned(self):
        status = {**STATUS, 'logging': {'active': False, 'error': None},
                  'sensors': {**STATUS['sensors'], 'gnss': '測位待ち'}}
        rows = self.rows(status=status, lap=LAP)
        self.assertTrue(rows['記録'][1])
        self.assertTrue(rows['測位'][1])

    def test_no_answer_from_ecocapture(self):
        rows = self.rows(status=None, lap=None, screen='')
        self.assertTrue(rows['EcoCapture'][1])
        self.assertTrue(rows['HDMIの画面'][1])

    def test_racecapture_screen(self):
        rows = self.rows(status=STATUS, lap=LAP,
                         screen='ecocapture-dash: inactive (power-on: disabled)\nracecapture-app: active (power-on: enabled)')
        self.assertEqual(rows['HDMIの画面'], ('RaceCaptureアプリ', False))


if __name__ == '__main__':
    unittest.main()
