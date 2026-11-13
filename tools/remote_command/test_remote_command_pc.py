"""PC側の命令の道具の試験。偽の中継（WebSocketの握手をして、届いた命令を本体と同じ
RemoteCommands で実行して返すだけ）に向けて、送る→署名の確認→返事の受け取りを通す。"""
import asyncio
import base64
import hashlib
import json
import socket
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import remote_command_pc as pc
from remote_command import RemoteCommands, write_private

SECRET = 'ab' * 32


class FakeLaps:
    def __init__(self):
        self.state = {'count': 3, 'lap_start_ms': 1, 'finished': False}
        self.line = type('Line', (), {'enabled': True})()

    def values(self):
        return {'LapCount': self.state['count'], 'CurrentLap': self.state['count'] + 1, 'RaceTime': 12.34}

    def reset(self):
        self.state['count'] = 0

    def set_count(self, n):
        self.state['count'] = n


class FakeRuntime:
    laps = FakeLaps()

    def status(self):
        return {'logging': {'active': True, 'elapsed_s': 600}, 'receive_hz': 99.0, 'hardware': {'sd_logging': 1},
                'video': {'recording': True}}


def frame(text, opcode=1):
    data = text.encode() if isinstance(text, str) else text
    n = len(data)
    head = bytes([0x80 | opcode]) + (bytes([n]) if n < 126 else bytes([126]) + struct.pack('>H', n))
    return head + data


def read_frame(conn, buffer):
    def take(n):
        nonlocal buffer
        while len(buffer) < n:
            buffer += conn.recv(65536)
        out, buffer = buffer[:n], buffer[n:]
        return out
    b0, b1 = take(2)
    n = b1 & 0x7f
    if n == 126:
        n = struct.unpack('>H', take(2))[0]
    mask = take(4)
    payload = bytes(b ^ mask[i % 4] for i, b in enumerate(take(n)))
    return b0 & 0x0f, payload, buffer


class FakeRelay(threading.Thread):
    """1回の接続だけ受ける中継の代わり。間に音声・pingを混ぜ、命令には本体と同じ処理で答える"""

    def __init__(self, logger):
        super().__init__(daemon=True)
        self.logger = logger
        self.server = socket.socket()
        self.server.bind(('127.0.0.1', 0))
        self.server.listen(1)
        self.port = self.server.getsockname()[1]
        self.seen = []

    def run(self):
        conn, _ = self.server.accept()
        buffer = b''
        while b'\r\n\r\n' not in buffer:
            buffer += conn.recv(4096)
        head, buffer = buffer.split(b'\r\n\r\n', 1)
        key = [l.split(b': ')[1] for l in head.split(b'\r\n') if l.lower().startswith(b'sec-websocket-key')][0]
        accept = base64.b64encode(hashlib.sha1(key + b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest())
        conn.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                     b'Sec-WebSocket-Accept: ' + accept + b'\r\n\r\n')
        conn.sendall(frame(json.dumps({'type': 'hello', 'protocol': 2, 'session_id': 9})))
        while True:
            opcode, payload, buffer = read_frame(conn, buffer)
            if opcode == 8:
                break
            event = json.loads(payload)
            self.seen.append(event)
            if event.get('type') == 'logger.config':
                conn.sendall(frame(b'\x01\x02voice', opcode=2) + frame(b'hi', opcode=9))
                conn.sendall(frame(json.dumps({'type': 'telemetry', 'data': {'x': 1}})))
                result = asyncio.run(self.logger.run(event['data']['command']))
                conn.sendall(frame(json.dumps({'type': 'logger.config', 'session_id': 1, 'data': {'command_result': result}})))
        conn.close()


class SendTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        write_private(root / 'private' / 'remote_command.json', {'secret': SECRET})
        self.logger = RemoteCommands(root, FakeRuntime(), lambda: None)
        local = root / 'pc.json'
        local.write_text(json.dumps({'secret': SECRET, 'url': 'ws://unused/ws/audio/ncec'}), encoding='utf-8')
        self.patch = mock.patch.object(pc, 'LOCAL', local)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.dir.cleanup()

    def send(self, op, arg=None):
        relay = FakeRelay(self.logger)
        relay.start()
        result = pc.send(op, arg, timeout=10, url=f'ws://127.0.0.1:{relay.port}/ws/audio/ncec', log=lambda *a: None)
        relay.join(5)
        return result, relay

    def test_lap_count_goes_through_and_the_answer_is_read(self):
        result, relay = self.send('lap_count', 8)
        self.assertTrue(result['ok'], result)
        self.assertEqual(FakeRuntime.laps.state['count'], 8)
        self.assertEqual(relay.seen[0]['type'], 'hello')
        self.assertEqual(relay.seen[0]['audio_formats'], [])  # the pit command client takes no voice
        self.assertNotIn(SECRET, json.dumps(relay.seen))  # only the signature travels
        text = '\n'.join(pc.describe(result))
        self.assertIn('完了8周', text)
        self.assertIn('記録 中 10分', text)

    def test_wrong_secret_is_explained(self):
        self.logger.secret = lambda: 'cd' * 32
        result, _ = self.send('status')
        self.assertFalse(result['ok'])
        self.assertIn('合言葉が違う', pc.describe(result)[0])

    def test_no_answer_is_explained(self):
        self.assertIn('返事がありませんでした', pc.describe(None)[0])


STATUS = {'logging': True, 'log_s': 600, 'hz': 99.0, 'gnss': True, 'sd': True, 'video': True,
          'lap': {'enabled': True, 'count': 3, 'current': 0, 'running': False, 'finished': False, 'race_min': 12.3}}
SUGO_LINE = {'name': 'sugo', 'control': [38.1423181, 140.7779443, 97.5, 50.0], 'start': None, 'goal': None,
             'sectors': 3, 'id': '662D', 'at': None, 'changed': True}


class CannedLogger:
    """本体の代わり。署名だけ本物と同じに確かめ、決めておいた返事を返す（線の中身の確かめは本体側の試験）"""

    def __init__(self, answer):
        self.answer, self.commands = answer, []

    async def run(self, command):
        self.commands.append(command)
        signed = pc.sign(SECRET, command['id'], command['t'], command['op'], command['arg']) == command['sig']
        return {'id': command['id'], 'op': command['op'], **(self.answer if signed else {'ok': False, 'message': 'bad signature'})}


class LineTests(unittest.TestCase):
    """コースを選ぶ・線を入れる（2026-11-13）"""
    setUp, tearDown = SendTests.setUp, SendTests.tearDown

    def main(self, argv):
        """コマンド行から偽の中継まで通す。(終わりの値, 画面に出た文)"""
        real = pc.send

        def send(op, arg, timeout, url):
            relay = FakeRelay(self.logger)
            relay.start()
            return real(op, arg, timeout=10, url=f'ws://127.0.0.1:{relay.port}/ws/audio/ncec', log=lambda *a: None)
        with mock.patch.object(pc, 'send', side_effect=send), mock.patch('builtins.print') as shown:
            code = pc.main(argv)
        return code, '\n'.join(call.args[0] for call in shown.call_args_list)

    def canned(self, **answer):
        self.logger = CannedLogger(answer)
        return self.logger

    def test_course_select_sends_only_the_name_and_reads_the_line_back(self):
        logger = self.canned(ok=True, message='course sugo set', line=SUGO_LINE, status=STATUS)
        code, text = self.main(['course-select', 'sugo'])
        self.assertEqual(code, 0)
        self.assertEqual((logger.commands[0]['op'], logger.commands[0]['arg']), ('course_select', {'name': 'sugo'}))
        self.assertIn('OK: コースを選ぶ — コースを「sugo」にしました', text)
        self.assertIn('コントロールライン 38.1423181, 140.7779443・向き 97.5°・幅 50 m・セクターの線 3本', text)
        self.assertIn('「sugo」と同じ', text)
        self.assertIn('次に通った所からラップを数え直します', text)
        self.assertIn('記録 中 10分', text)   # 記録は止まっていない

    def test_line_set_sends_the_line_of_the_pc_course_file(self):
        logger = self.canned(ok=True, message='line set', line={**SUGO_LINE, 'name': None}, status=STATUS)
        course = json.loads((pc.REPO / 'tools' / 'setups' / 'courses' / 'sugo.json').read_text(encoding='utf-8'))
        code, text = self.main(['line-set', 'sugo'])
        self.assertEqual(code, 0)
        sent = logger.commands[0]
        self.assertEqual((sent['op'], sent['arg']), ('line_set', course['line']))
        self.assertEqual(len(sent['arg']['sectors']), 3)
        self.assertLess(len(json.dumps({'type': 'logger.config', 'data': {'command': sent}}, separators=(',', ':'))), 1000)
        self.assertIn('OK: 線を入れる — 線を入れました', text)
        self.assertIn('本体に入っているどのコースの設定とも違う', text)

    def test_line_set_reads_a_file_too(self):
        folder = Path(self.dir.name)
        lap = folder / 'lap.json'   # 本体から取った lap.json の形
        lap.write_text(json.dumps({'line': {'enabled': True, 'lat': 36.5, 'lon': 140.2, 'bearing': None, 'width_m': 30,
                                            'set_at': '2026-11-13T10:00+09:00'}, 'state': {'count': 4}}), encoding='utf-8')
        self.assertEqual(pc.course_line(str(lap)), {'lat': 36.5, 'lon': 140.2, 'bearing': None, 'width_m': 30})
        (folder / 'empty.json').write_text('{"line": {}}', encoding='utf-8')
        for source in (str(folder / 'empty.json'), str(folder / 'none.json'), 'motegi-not-here'):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    pc.course_line(source)

    def test_bad_names_are_not_sent(self):
        with mock.patch.object(pc, 'send') as send, mock.patch('sys.stderr'):
            for argv in (['course-select'], ['course-select', '../sugo'], ['course-select', 'SUGO'], ['line-set'],
                         ['line-set', 'motegi-not-here'], ['lap-count'], ['lap-count', 'sugo']):
                with self.subTest(argv=argv):
                    with self.assertRaises(SystemExit):
                        pc.main(argv)
        send.assert_not_called()

    def test_refusals_of_the_line_commands_are_explained(self):
        missing = {'op': 'course_select', 'ok': False, 'message': 'no course motegi', 'courses': ['sugo', 'fuji'], 'status': STATUS}
        self.assertIn('本体に「motegi」というコースの設定がありません（入っているのは sugo・fuji）', pc.describe(missing)[0])
        bad = {'op': 'line_set', 'ok': False, 'message': 'bad line: width_m: Input should be less than or equal to 200'}
        self.assertIn('線の値が本体の決まりの外です（width_m:', pc.describe(bad)[0])
        same = {'op': 'course_select', 'ok': True, 'message': 'course sugo was already set', 'line': {**SUGO_LINE, 'changed': False}}
        text = '\n'.join(pc.describe(same))
        self.assertIn('もう「sugo」でした', text)
        self.assertNotIn('数え直します', text)
        learned = {'op': 'line_set', 'ok': True, 'message': 'line set',
                   'line': {**SUGO_LINE, 'control': [36.5, 140.2, None, 30.0], 'goal': [36.6, 140.3, 10.0, 20.0], 'sectors': 0}}
        text = '\n'.join(pc.describe(learned))
        self.assertIn('向き 通ったときに覚える・幅 30 m', text)
        self.assertIn('ゴール 36.6, 140.3・向き 10°・幅 20 m', text)

    def test_the_old_commands_still_take_their_arguments(self):
        with mock.patch.object(pc, 'send', return_value={'ok': True, 'op': 'lap_count', 'message': 'lap count set to 12'}) as send, \
                mock.patch('builtins.print'):
            self.assertEqual(pc.main(['lap-count', '12']), 0)
            self.assertEqual(send.call_args.args[:2], ('lap_count', 12))
            pc.main(['status'])
            self.assertEqual(send.call_args.args[:2], ('status', None))


if __name__ == '__main__':
    unittest.main()
