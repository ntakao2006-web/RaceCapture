"""Pit stand-in on the relay for end-to-end voice tests (ER-10-4, ER-10-6, ER-10-9).

Joins wss://<relay>/ws/audio/<room> as an ordinary participant, talks (holds
audio.ptt and sends 60 ms 8 kHz Opus, like the browser call page), then listens
and saves whatever voice the room sends back. Runs on the UNO Q host (libopus via
voice_agent.Opus, standard library only otherwise):

  python3 agent_check.py ...  # not needed; the logger itself is the other end
  python3 pit_sim.py wss://rock-5b.tail5a9705.ts.net/ws/audio/voice-test pit.wav 20 heard.wav
"""
import base64
import ctypes
import json
import os
import socket
import ssl
import sys
import time
import wave
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

sys.path.insert(0, str(Path.home() / 'EcoCapture-Web'))
import voice_agent as va   # noqa: E402

FRAME = 480   # 60 ms at 8 kHz: what the relay's own codec uses


class WS:
    def __init__(self, url):
        u = urlparse(url)
        raw = socket.create_connection((u.hostname, u.port or 443), timeout=10)
        self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=u.hostname)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f'GET {u.path} HTTP/1.1\r\nHost: {u.hostname}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                           f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        head = b''
        while b'\r\n\r\n' not in head:
            head += self.sock.recv(1)
        assert head.startswith(b'HTTP/1.1 101'), head[:40]
        self.buf = b''

    def send(self, opcode, payload):
        mask = os.urandom(4)
        n = len(payload)
        head = bytes([0x80 | opcode]) + (bytes([0x80 | n]) if n < 126 else bytes([0xfe]) + n.to_bytes(2, 'big'))
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def json(self, data):
        self.send(1, json.dumps(data).encode())

    def recv(self, timeout):
        """[(opcode, payload)] that arrived within `timeout` s."""
        self.sock.settimeout(timeout)
        try:
            self.buf += self.sock.recv(65536)
        except (socket.timeout, ssl.SSLWantReadError):
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


def opus_frames(name, opus):
    w = wave.open(name)
    pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    pcm = np.pad(pcm, (0, -len(pcm) % FRAME))
    out = []
    for at in range(0, len(pcm), FRAME):
        frame = np.ascontiguousarray(pcm[at:at + FRAME])
        n = opus.lib.opus_encode(opus.enc, frame.ctypes.data, FRAME, opus.out, len(opus.out))
        out.append(opus.out.raw[:n])
    return out


def main(url, say, listen_s, heard):
    opus = va.Opus()
    opus.lib.opus_encoder_ctl(opus.enc, opus.SET_BITRATE, 12000)   # like the browser page
    ws = WS(url)
    ws.json({'type': 'hello', 'client_id': 'pit-sim', 'protocol': 1,
             'audio_formats': [{'sample_rate': 8000, 'channels': 1, 'frame_ms': 60}]})
    for op, payload in ws.recv(1):
        if op == 1:
            print('relay:', payload[:200].decode('utf-8', 'replace'))
    frames = opus_frames(say, opus)
    print(f'pit talks: {len(frames)} packets ({len(frames) * 0.06:.1f} s)')
    ws.json({'type': 'audio.ptt', 'active': True})
    start = time.monotonic()
    for i, packet in enumerate(frames):
        ws.send(2, packet)
        ws.recv(0.001)
        time.sleep(max(0, start + (i + 1) * 0.06 - time.monotonic()))
    time.sleep(0.3)
    ws.json({'type': 'audio.ptt', 'active': False})
    print(f'pit listens {listen_s} s ...')
    pcm, events, end = [], [], time.monotonic() + listen_s
    dec = va.Opus()
    while time.monotonic() < end:
        for op, payload in ws.recv(0.2):
            if op == 2:
                buf = np.zeros(960, dtype=np.int16)
                n = dec.lib.opus_decode(dec.dec, payload, len(payload), buf.ctypes.data, 960, 0)
                if n > 0:
                    pcm.append(buf[:n].copy())
            elif op == 1:
                event = json.loads(payload)
                if event.get('type') == 'room.state':
                    talking = [p.get('client_id') or p.get('session_id') for p in event.get('participants', []) if p.get('ptt')]
                    events.append((round(listen_s - (end - time.monotonic()), 1), talking))
    pcm = np.concatenate(pcm) if pcm else np.zeros(0, dtype=np.int16)
    with wave.open(heard, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(pcm.tobytes())
    print(f'heard {len(pcm) / 8000:.1f} s of voice from the room; talking events: {events}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4])
