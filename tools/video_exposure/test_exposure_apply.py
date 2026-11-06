"""exposure_apply.py の試験（本体につながずに）。python -m unittest test_exposure_apply"""
import unittest

import exposure_apply as ea


class FakeDevice:
    """本体の代わり。exposure.ini を受け取ると、録画と同じように status を書き直す"""

    def __init__(self, ini='', ready=True):
        self.ini, self.ready, self.n = ini, ready, 0
        self.status = 'at=2026-11-06 18:00:00\nmode=own\nexposure_ms=0.7\ngain=3\ngain_range=0-100\nroi_mean=118\nroi_hi=220\nmsg=設定ファイルが無いので既定の値\n'

    def run(self, cmd, data=None):
        if data is not None:
            self.ini = data.decode('utf-8')
            self.n += 1
            mode = ea.get_value(self.ini, 'mode') or 'own'
            self.status = f'at=2026-11-06 18:00:{self.n:02d}\nmode={mode}\nexposure_ms=0.7\ngain=3\nmsg=設定ファイルを読んだ\n'
            return 'ok\n'
        return (f'@@R{int(self.ready)}\n@@A1\n@@I\n{self.ini}\n@@S\n{self.status}')


class Test(unittest.TestCase):
    def test_set_value(self):
        self.assertEqual(ea.set_value('', 'mode', 'camera'), 'mode = camera\n')
        t = '# 注釈\nmode = own  # 既定\ntarget = 100\nmode=camera\n'
        self.assertEqual(ea.set_value(t, 'mode', 'camera'), '# 注釈\nmode = camera\ntarget = 100\n')
        self.assertEqual(ea.get_value(t, 'target'), '100')
        self.assertEqual(ea.get_value('mode = own  # 既定', 'mode'), 'own')
        self.assertIsNone(ea.get_value(t, 'roi'))

    def test_target(self):
        self.assertEqual(ea.new_target('', 15), 130)
        self.assertEqual(ea.new_target('target = 195', 15), 200)
        self.assertEqual(ea.new_target('target = 45', -15), 40)
        self.assertEqual(ea.new_target('target = x', -15), 100)

    def _main(self, dev, *args):
        orig = ea.time.sleep
        ea.time.sleep = lambda s: None
        import hud_apply
        orig_runner = hud_apply.runner
        hud_apply.runner = lambda use_adb, host: dev.run
        try:
            return ea.main(list(args))
        finally:
            ea.time.sleep = orig
            hud_apply.runner = orig_runner

    def test_switch(self):
        dev = FakeDevice()
        self.assertEqual(self._main(dev, '--camera'), 0)
        self.assertEqual(dev.ini, 'mode = camera\n')
        self.assertEqual(self._main(dev, '--brighter'), 0)
        self.assertEqual(ea.get_value(dev.ini, 'mode'), 'own')
        self.assertEqual(ea.get_value(dev.ini, 'target'), '130')
        self.assertEqual(self._main(dev, '--status'), 0)
        self.assertEqual(dev.n, 2)

    def test_old_recorder(self):
        dev = FakeDevice(ready=False)
        self.assertEqual(self._main(dev, '--camera'), 2)
        self.assertEqual(dev.n, 0)


if __name__ == '__main__':
    unittest.main()
