import json
import shlex
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import podium_channels_setup as tool
import sugo_setup

# Ver.2's list on 2026-11-03 (from the meta it sent to the 5B): the defaults and six more
NOW = ['Lat', 'Lon', 'Altitude', 'GPSSpeed', 'Yaw', 'GPSFix', 'GPSSats', 'AccelX', 'AccelY', 'AccelZ', 'GyroX', 'GyroY',
       'GyroZ', 'Roll', 'Pitch', 'Speed', 'RPM', 'Throttle', 'WaterTemp', 'LongAccel', 'LatAccel']
ALLOWED = NOW + ['OilTemp', 'WaterTempDefi', 'PressVolt']


class FakeUnoQ:
    """本体の代わり：/api/podium だけを真似る（書き込みは操作ヘッダーが無ければ断る）"""
    def __init__(self):
        self.config = {'enabled': False, 'link': 'lte', 'destination': 'relay', 'channels': list(NOW)}
        self.posts = []

    def __call__(self, command):
        words = shlex.split(command)
        assert words[0] == 'curl' and any(w == sugo_setup.API + '/api/podium' for w in words), command
        if '--data-binary' in words:
            if 'X-EcoCapture: 1' not in words:
                return '{"detail":"操作ヘッダーが必要です"}\n403'
            body = json.loads(words[words.index('--data-binary') + 1])
            self.posts.append(body)
            self.config = {**self.config, **body}
        return json.dumps({'config': self.config, 'channels': [{'name': n} for n in ALLOWED]}) + '\n200'


class PodiumChannelsTest(unittest.TestCase):
    def run_tool(self, *argv):
        fake = FakeUnoQ()
        orig = tool.runner
        tool.runner = lambda adb, host: fake
        try:
            code = tool.main(list(argv))
        finally:
            tool.runner = orig
        return code, fake

    def test_check_changes_nothing(self):
        code, fake = self.run_tool()
        self.assertEqual(code, 0)
        self.assertEqual(fake.posts, [])

    def test_apply_adds_only_the_oil(self):
        code, fake = self.run_tool('--apply')
        self.assertEqual(code, 0)
        self.assertEqual(fake.posts, [{'channels': NOW + ['OilTemp']}])   # nothing else: not enabled, not the server
        self.assertFalse(fake.config['enabled'])

    def test_slim_keeps_what_the_pit_shows(self):
        code, fake = self.run_tool('--apply', '--slim')
        self.assertEqual(code, 0)
        self.assertEqual(fake.config['channels'], tool.PIT)
        self.assertTrue(set(tool.NEEDED) <= set(tool.PIT))

    def test_set_restores_and_refuses_unknown_names(self):
        code, fake = self.run_tool('--set', ','.join(NOW))
        self.assertEqual((code, fake.posts), (0, []))   # already so
        code, fake = self.run_tool('--set', 'Lat,Lon,NoSuch')
        self.assertEqual((code, fake.posts), (1, []))


if __name__ == '__main__':
    unittest.main()
