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


COURSE = Path(__file__).resolve().parents[1] / 'tools' / 'setups' / 'courses' / 'sugo.json'
LINE = {'lat': 36.5331, 'lon': 140.2267, 'bearing': 180.0, 'width_m': 20,
        'sectors': [{'lat': 36.53, 'lon': 140.23, 'bearing': 90, 'width_m': 25}]}


class LineCommandTests(RemoteCommandTests):
    """course_select and line_set (2026-11-13). The tests above run again with a course file in place."""
    def setUp(self):
        super().setUp()
        folder = self.root / 'setups' / 'courses'
        folder.mkdir(parents=True)
        (folder / 'sugo.json').write_bytes(COURSE.read_bytes())
        self.course = json.loads(COURSE.read_text(encoding='utf-8'))
        self.kept = self.root / 'lap.json.bak-remote'
        self.runtime.logging = True
        self.started = []

        async def start():
            self.started.append(1)
        self.remote.actions['log_start'] = start

    def saved_line(self):
        return json.loads((self.root / 'lap.json').read_text(encoding='utf-8'))['line']

    def test_log_start(self):  # the parent's version starts from a stopped recording
        self.assertEqual(self.run_command(command('log_start'))['message'], 'already logging')

    def test_status_answers_with_the_lap_and_logging(self):
        result = self.run_command(command('status'))
        self.assertTrue(result['status']['logging'])
        self.assertNotIn('line', result)  # only the line commands carry it
        self.assertLess(len(json.dumps(result)), 400)

    def test_course_select_sets_the_line_and_answers_with_what_was_read_back(self):
        before = self.saved_line()
        cmd = command('course_select', {'name': 'sugo'})
        result = self.run_command(cmd)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['message'], 'course sugo set')
        want = self.course['line']
        self.assertEqual(result['line']['name'], 'sugo')
        self.assertEqual(result['line']['control'], [want['lat'], want['lon'], want['bearing'], want['width_m']])
        self.assertEqual((result['line']['sectors'], result['line']['start'], result['line']['goal']), (3, None, None))
        self.assertTrue(result['line']['changed'])
        saved = self.saved_line()
        self.assertEqual({k: saved[k] for k in want}, want)  # the whole line of the course file, as lap.json holds it
        self.assertEqual(LapTimer(self.root).line.sectors, self.runtime.laps.line.sectors)
        self.assertEqual(json.loads(self.kept.read_text(encoding='utf-8'))['line'], before)  # the line before is kept
        self.assertTrue(result['status']['logging'])  # the recording was not touched
        self.assertEqual(self.started, [])
        self.assertLess(len(json.dumps({'type': 'logger.config', 'data': {'command': cmd}}, separators=(',', ':'))), 300)
        self.assertLess(len(json.dumps({'type': 'logger.config', 'data': {'command_result': result}}, separators=(',', ':'))), 700)

    def test_course_select_takes_only_the_name_of_a_course_on_the_logger(self):
        before = self.saved_line()
        (self.root / 'outside.json').write_bytes(COURSE.read_bytes())
        bad = ['../outside', 'setups/courses/sugo', 'SUGO', 'sugo.json', '', 'a' * 33, 5, None]
        for i, name in enumerate(bad):
            with self.subTest(name=name):
                result = self.run_command(command('course_select', {'name': name}, command_id=f'{i:016x}'))
                self.assertEqual((result['ok'], result['message']), (False, 'bad course name'))
        for i, arg in enumerate(['sugo', None, {}, {'name': 'sugo', 'vehicle': 'ncec'}, ['sugo']]):
            with self.subTest(arg=arg):
                result = self.run_command(command('course_select', arg, command_id=f'{i:015x}f'))
                self.assertEqual((result['ok'], result['message']), (False, 'bad course name'))
        missing = self.run_command(command('course_select', {'name': 'motegi'}, command_id='a' * 16))
        self.assertEqual((missing['ok'], missing['message'], missing['courses']), (False, 'no course motegi', ['sugo']))
        self.assertNotIn('line', missing)
        self.assertEqual(self.saved_line(), before)
        self.assertFalse(self.kept.exists())

    def test_course_file_that_is_not_one_is_refused(self):
        folder = self.root / 'setups' / 'courses'
        (folder / 'other.json').write_bytes(COURSE.read_bytes())  # its id says sugo
        (folder / 'broken.json').write_text('{', encoding='utf-8')
        wide = {**self.course, 'id': 'wide', 'line': {**self.course['line'], 'width_m': 500}}
        (folder / 'wide.json').write_text(json.dumps(wide), encoding='utf-8')
        before = self.saved_line()
        self.assertEqual(self.run_command(command('course_select', {'name': 'other'}))['message'], 'course other is not a course file')
        self.assertEqual(self.run_command(command('course_select', {'name': 'broken'}, command_id='b' * 16))['message'], 'course broken cannot be read')
        self.assertIn('bad line: width_m', self.run_command(command('course_select', {'name': 'wide'}, command_id='c' * 16))['message'])
        self.assertEqual(self.saved_line(), before)

    def test_line_commands_are_signed_like_the_others(self):
        before = self.saved_line()
        self.assertEqual(self.run_command(command('course_select', {'name': 'sugo'}, secret='ff' * 32))['message'], 'bad signature')
        cmd = command('line_set', LINE, command_id='5123456789abcdef')
        cmd['arg'] = {**LINE, 'lat': 36.6}
        self.assertEqual(self.run_command(cmd)['message'], 'bad signature')
        self.assertTrue(self.run_command(command('line_set', LINE, command_id='6123456789abcdef'))['ok'])
        again = self.run_command(command('line_set', {**LINE, 'lat': 36.6}, command_id='6123456789abcdef'))
        self.assertEqual(again['message'], 'already used')
        old = command('course_select', {'name': 'sugo'}, command_id='7123456789abcdef', t=NOW_MS - COMMAND_WINDOW_MS - 1)
        self.assertEqual(self.run_command(old)['message'], 'too old or from the future')
        self.assertEqual(self.saved_line()['lat'], LINE['lat'])
        self.assertEqual(json.loads(self.kept.read_text(encoding='utf-8'))['line'], before)

    def test_line_set_puts_the_lines_in_and_keeps_the_race_options(self):
        laps = self.runtime.laps
        laps.configure(LapLine.model_validate({**laps.line.model_dump(), 'min_lap_s': 90, 'total_laps': 7,
                                               'goal': {'lat': 38.15, 'lon': 140.78, 'bearing': 10, 'width_m': 30}}))
        result = self.run_command(command('line_set', LINE))
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['line']['control'], [36.5331, 140.2267, 180.0, 20.0])
        self.assertEqual((result['line']['sectors'], result['line']['goal'], result['line']['name']), (1, None, None))
        saved = self.saved_line()
        self.assertEqual((saved['min_lap_s'], saved['total_laps'], saved['goal'], saved['enabled']), (90, 7, None, True))
        self.assertEqual(saved['sectors'][0]['width_m'], 25)
        self.assertEqual(self.started, [])
        learned = self.run_command(command('line_set', {'lat': 36.5, 'lon': 140.2}, command_id='1' * 16))
        self.assertEqual(learned['line']['control'], [36.5, 140.2, None, 30.0])  # heading learned on the first pass
        self.assertEqual(learned['line']['sectors'], 0)

    def test_line_set_out_of_range_is_refused_and_nothing_changes(self):
        before = self.saved_line()
        bad = [{**LINE, 'lat': 99}, {**LINE, 'width_m': 1000}, {**LINE, 'bearing': 360}, {**LINE, 'shell': 'x'},
               {**LINE, 'sectors': [{'lat': 36.53, 'lon': 140.23}]}, {**LINE, 'sectors': [LINE['sectors'][0]] * 10},
               {**LINE, 'start': {'lat': 36.5, 'lon': 999}}, {**LINE, 'min_lap_s': 1}, {**LINE, 'lat': float('nan')},
               {**LINE, 'enabled': False}, {**LINE, 'set_at': 'x'}, {'bearing': 90}, 'sugo', None, [36.5, 140.2]]
        for i, arg in enumerate(bad):
            with self.subTest(arg=arg):
                result = self.run_command(command('line_set', arg, command_id=f'{i:016x}'))
                self.assertFalse(result['ok'], result)
                self.assertTrue(result['message'].startswith('bad line'), result)
                self.assertLess(len(result['message']), 300)
                self.assertNotIn('http', result['message'])
        self.assertEqual(self.saved_line(), before)
        self.assertFalse(self.kept.exists())

    def test_laps_count_from_the_next_pass_of_the_new_line(self):
        laps = self.runtime.laps
        laps.crossed(NOW_MS)
        laps.crossed(NOW_MS + 100_000)  # one lap in, the second running on the old line
        self.assertEqual((laps.state['count'], laps.state['lap_start_ms']), (1, NOW_MS + 100_000))
        result = self.run_command(command('course_select', {'name': 'sugo'}))
        self.assertEqual(result['status']['lap'], {**result['status']['lap'], 'count': 1, 'current': 0, 'running': False})
        self.assertEqual(len(laps.state['laps']), 1)  # what was recorded stays
        laps.crossed(NOW_MS + 150_000)  # first pass of the new line: starts a lap, ends none
        self.assertEqual((laps.state['count'], laps.state['lap_start_ms']), (1, NOW_MS + 150_000))
        laps.crossed(NOW_MS + 250_000)
        self.assertEqual((laps.state['count'], laps.state['last_s']), (2, 100.0))
        self.assertEqual(LapTimer(self.root).state['count'], 2)

    def test_the_same_line_again_changes_nothing_and_keeps_the_first_copy(self):
        before = self.saved_line()
        self.assertTrue(self.run_command(command('course_select', {'name': 'sugo'}))['ok'])
        self.runtime.laps.crossed(NOW_MS)
        again = self.run_command(command('course_select', {'name': 'sugo'}, command_id='1' * 16))
        self.assertEqual((again['ok'], again['message'], again['line']['changed']), (True, 'course sugo was already set', False))
        self.assertEqual(self.runtime.laps.state['lap_start_ms'], NOW_MS)  # the running lap goes on
        typed = self.run_command(command('line_set', {k: v for k, v in self.course['line'].items() if k != 'enabled'}, command_id='2' * 16))
        self.assertEqual((typed['message'], typed['line']['name']), ('line was already set', 'sugo'))
        self.assertEqual(json.loads(self.kept.read_text(encoding='utf-8'))['line'], before)

    def test_only_the_race_options_changed_keeps_the_running_lap(self):
        self.assertTrue(self.run_command(command('course_select', {'name': 'sugo'}))['ok'])
        self.runtime.laps.crossed(NOW_MS)
        line = {**self.course['line'], 'min_lap_s': 75}
        result = self.run_command(command('line_set', line, command_id='1' * 16))
        self.assertEqual((result['ok'], result['line']['changed'], result['line']['name']), (True, True, None))
        self.assertEqual(self.runtime.laps.state['lap_start_ms'], NOW_MS)
        self.assertEqual(self.saved_line()['min_lap_s'], 75)

    def test_the_whole_course_line_fits_one_message(self):
        cmd = command('line_set', self.course['line'])
        size = len(json.dumps({'type': 'logger.config', 'session_id': 3, 'data': {'command': cmd}}, separators=(',', ':')))
        self.assertLess(size, 1000)  # control line + pit lane + 3 sector lines; the relay socket takes frames up to 65536
        self.assertTrue(self.run_command(cmd)['ok'])


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
