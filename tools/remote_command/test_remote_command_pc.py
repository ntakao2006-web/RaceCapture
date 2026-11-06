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


if __name__ == '__main__':
    unittest.main()
