import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path

from lap import LapLine, LapTimer
from remote_command import COMMAND_WINDOW_MS, RemoteCommands, sign, write_private

SECRET = '00112233445566778899aabbccddeeff' * 2
NOW_MS = 1_794_000_000_000


class FakeRuntime:
    def __init__(self, root):
        self.laps = LapTimer(root)
        self.laps.configure(LapLine(enabled=True, lat=38.14, lon=140.77, bearing=97.5, width_m=50))
        self.logging = False

    def status(self):
        return {'logging': {'active': self.logging, 'elapsed_s': 12.4 if self.logging else 0}, 'receive_hz': 99.5,
                'hardware': {'sd_logging': self.logging}, 'video': {'recording': True}}


def command(op, arg=None, command_id='0123456789abcdef', t=NOW_MS, secret=SECRET):
    return {'id': command_id, 't': t, 'op': op, 'arg': arg, 'sig': sign(secret, command_id, t, op, arg)}


class RemoteCommandTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        write_private(self.root / 'private' / 'remote_command.json', {'secret': SECRET})
        self.runtime = FakeRuntime(self.root)
        self.gnss = NOW_MS
        self.remote = RemoteCommands(self.root, self.runtime, lambda: self.gnss)

        async def start():
            self.runtime.logging = True
        self.remote.actions['log_start'] = start

    def tearDown(self):
        self.dir.cleanup()

    def run_command(self, cmd, remote=None):
        return asyncio.run((remote or self.remote).run(cmd))

    def test_status_answers_with_the_lap_and_logging(self):
        result = self.run_command(command('status'))
        self.assertTrue(result['ok'])
        self.assertEqual(result['status']['lap']['count'], 0)
        self.assertFalse(result['status']['logging'])
        self.assertLess(len(json.dumps(result)), 400)  # small: it goes back up the LTE link

    def test_lap_count_is_corrected_and_kept(self):
        result = self.run_command(command('lap_count', 7))
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['status']['lap']['count'], 7)
        self.assertEqual(LapTimer(self.root).state['count'], 7)  # saved

    def test_lap_count_out_of_range_is_refused(self):
        self.assertFalse(self.run_command(command('lap_count', -1))['ok'])
        self.assertFalse(self.run_command(command('lap_count', '3', command_id='1123456789abcdef'))['ok'])

    def test_lap_reset(self):
        self.runtime.laps.set_count(5)
        self.assertEqual(self.run_command(command('lap_reset'))['status']['lap']['count'], 0)

    def test_lap_start_needs_gnss_time_and_does_not_restart_a_running_lap(self):
        self.assertFalse(self.run_command(command('lap_start'))['ok'])  # no fix seen by the lap timer yet
        self.runtime.laps.latest_utc = (NOW_MS, time.monotonic())
        result = self.run_command(command('lap_start', command_id='2123456789abcdef'))
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['status']['lap']['running'])
        self.assertEqual(result['status']['lap']['current'], 1)
        self.assertEqual(self.runtime.laps.state['race_start_ms'], self.runtime.laps.state['lap_start_ms'])
        again = self.run_command(command('lap_start', command_id='3123456789abcdef'))
        self.assertFalse(again['ok'])
        self.assertIn('already running', again['message'])

    def test_log_start(self):
        result = self.run_command(command('log_start'))
        self.assertTrue(result['ok'])
        self.assertTrue(result['status']['logging'])
        self.assertEqual(self.run_command(command('log_start', command_id='4123456789abcdef'))['message'], 'already logging')

    def test_wrong_secret_or_changed_argument_is_refused(self):
        self.assertEqual(self.run_command(command('lap_reset', secret='ff' * 32))['message'], 'bad signature')
        cmd = command('lap_count', 3, command_id='5123456789abcdef')
        cmd['arg'] = 30
        self.assertEqual(self.run_command(cmd)['message'], 'bad signature')
        self.assertEqual(self.runtime.laps.state['count'], 0)

    def test_a_command_runs_once_even_after_a_restart(self):
        self.runtime.laps.set_count(4)
        cmd = command('lap_reset')
        self.assertTrue(self.run_command(cmd)['ok'])
        self.runtime.laps.set_count(4)
        again = RemoteCommands(self.root, self.runtime, lambda: self.gnss)
        self.assertEqual(self.run_command(cmd, again)['message'], 'already used')
        self.assertEqual(self.runtime.laps.state['count'], 4)

    def test_old_commands_are_refused_only_when_gnss_time_is_known(self):
        old = command('status', t=NOW_MS - COMMAND_WINDOW_MS - 1)
        self.assertEqual(self.run_command(old)['message'], 'too old or from the future')
        self.gnss = None  # no fix: the id and the signature still protect
        self.assertTrue(self.run_command(command('status', command_id='6123456789abcdef', t=NOW_MS - COMMAND_WINDOW_MS - 1))['ok'])

    def test_no_secret_on_the_logger(self):
        (self.root / 'private' / 'remote_command.json').unlink()
        self.assertEqual(self.run_command(command('status'))['message'], 'no secret on the logger')

    def test_unknown_or_malformed_commands(self):
        self.assertEqual(self.run_command(command('shell', 'rm -rf /'))['message'], 'unknown op shell')
        self.assertEqual(self.run_command({'id': 'x'})['message'], 'bad command')
        self.assertEqual(self.run_command('lap_reset')['message'], 'bad command')

    def test_finished_race_counts_again_after_a_correction(self):
        laps = self.runtime.laps
        laps.state.update(finished=True, count=7, race_end_ms=NOW_MS)
        self.assertTrue(self.run_command(command('lap_count', 6))['ok'])
        self.assertFalse(laps.state['finished'])


class PodiumRelayTests(unittest.TestCase):
    def test_command_goes_through_the_relay_and_the_answer_comes_back(self):
        from podium import PodiumSender

        class FakeWs:
            def __init__(self):
                self.sent = []

            async def send_json(self, data):
                self.sent.append(data)

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_private(root / 'private' / 'remote_command.json', {'secret': SECRET})
            runtime = FakeRuntime(root)
            runtime.remote = RemoteCommands(root, runtime, lambda: NOW_MS)
            sender = PodiumSender(root, runtime)
            sender.relay_message(json.dumps({'type': 'logger.config', 'session_id': 3,
                                             'data': {'command': command('lap_count', 2)}}), None, False)
            ws = FakeWs()
            asyncio.run(sender.run_remote(ws))
            self.assertEqual(len(ws.sent), 1)
            answer = ws.sent[0]
            self.assertEqual(answer['type'], 'logger.config')
            self.assertTrue(answer['data']['command_result']['ok'])
            self.assertEqual(runtime.laps.state['count'], 2)
            self.assertEqual(sender.remote_pending, [])
            self.assertNotIn('sig', json.dumps(answer))


if __name__ == '__main__':
    unittest.main()
