"""Pit stand-in that keeps talking for a long time, for LTE voice tests while the UNO Q is away (ER-10-6).

Standard library + libopus only (the home server has no numpy). Joins the relay's room as an ordinary
participant, holds audio.ptt and loops an 8 kHz mono WAV as 60 ms Opus at 12 kbps (like the browser
call page), and counts the voice the room sends back (the logger's uplink):

  python3 pit_loop.py ws://127.0.0.1:3000/ws/audio/voice-test pit_test.wav 1500
"""
import array
import ctypes
import ctypes.util
import json
import os
import socket
import sys
import time
import wave
from urllib.parse import urlparse

FRAME = 480   # 60 ms at 8 kHz


class WS:
    def __init__(self, url):
        u = urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port or 80), timeout=10)
        key = __import__('base64').b64encode(os.urandom(16)).decode()
        self.sock.sendall((f'GET {u.path} HTTP/1.1\r\nHost: {u.hostname}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                           f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        head = b''
        while b'\r\n\r\n' not in head:
            head += self.sock.recv(1)
        assert head.startswith(b'HTTP/1.1 101'), head[:40]
        self.buf = b''
        self.sock.setblocking(False)

    def send(self, opcode, payload):
        mask = os.urandom(4)
        n = len(payload)
        head = bytes([0x80 | opcode]) + (bytes([0x80 | n]) if n < 126 else bytes([0xfe]) + n.to_bytes(2, 'big'))
        self.sock.setblocking(True)
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
        self.sock.setblocking(False)

    def json(self, data):
        self.send(1, json.dumps(data).encode())

    def drain(self):
        try:
            while True:
                data = self.sock.recv(65536)
                if not data:
                    raise ConnectionError('relay closed')
                self.buf += data
        except BlockingIOError:
            pass
        out = []
        while len(self.buf) >= 2:
            n, at = self.buf[1] & 0x7f, 2
            if n == 126:
                if len(self.buf) < 4:
                    break
                n, at = int.from_bytes(self.buf[2:4], 'big'), 4
            if len(self.buf) < at + n:
                break
            op, payload, self.buf = self.buf[0] & 0x0f, self.buf[at:at + n], self.buf[at + n:]
            if op == 9:
                self.send(10, payload)
            out.append((op, payload))
        return out


def frames(name, frame=FRAME, bitrate=12000):
    """Opus packets of `frame` samples from an 8 kHz mono WAV (default: the browser page's 60 ms, 12 kbps)."""
    lib = ctypes.CDLL(ctypes.util.find_library('opus') or 'libopus.so.0')
    lib.opus_encoder_create.restype = ctypes.c_void_p
    lib.opus_encode.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int32]
    lib.opus_encoder_ctl.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int32]
    err = ctypes.c_int()
    enc = lib.opus_encoder_create(8000, 1, 2048, ctypes.byref(err))
    lib.opus_encoder_ctl(enc, 4002, bitrate)
    w = wave.open(name)
    assert w.getframerate() == 8000 and w.getnchannels() == 1 and w.getsampwidth() == 2
    pcm = array.array('h', w.readframes(w.getnframes()))
    pcm.extend([0] * (-len(pcm) % frame))
    out, buf = [], ctypes.create_string_buffer(400)
    for at in range(0, len(pcm), frame):
        chunk = pcm[at:at + frame]
        addr, _ = chunk.buffer_info()
        n = lib.opus_encode(enc, addr, frame, buf, len(buf))
        out.append(buf.raw[:n])
    return out


def main(url, say, seconds):
    packets = frames(say)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            ws = WS(url)
            ws.json({'type': 'hello', 'client_id': 'pit-loop', 'protocol': 1,
                     'audio_formats': [{'sample_rate': 8000, 'channels': 1, 'frame_ms': 60}]})
            ws.json({'type': 'audio.ptt', 'active': True})
            start, i, heard, last = time.monotonic(), 0, 0, time.monotonic()
            while time.monotonic() < end:
                ws.send(2, packets[i % len(packets)])
                i += 1
                heard += sum(1 for op, _ in ws.drain() if op == 2)
                if time.monotonic() - last >= 10:
                    print(f"{time.strftime('%H:%M:%S')} pit sent {i} pkt, logger voice heard {heard} pkt", flush=True)
                    last = time.monotonic()
                time.sleep(max(0, start + i * 0.06 - time.monotonic()))
        except (OSError, ConnectionError, AssertionError) as e:
            print(f"{time.strftime('%H:%M:%S')} reconnect: {e}", flush=True)
            time.sleep(2)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]))
