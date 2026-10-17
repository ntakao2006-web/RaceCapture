"""Bench check of voice_agent.py on the UNO Q, without the relay (ER-10-4, ER-10-9).

Stands in for podium.py on /run/ecocapture-voice/podium.sock (stop Podium voice first):

  python3 agent_check.py play pit.wav        # 8 kHz mono WAV -> Opus -> agent -> earphone
  python3 agent_check.py listen 20 out.wav   # ask for uplink 20 s, save what the agent sent
"""
import json
import socket
import sys
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.home() / 'EcoCapture-Web'))
import voice_agent as va   # noqa: E402

DIR = Path('/run/ecocapture-voice')
AGENT = str(DIR / 'agent.sock')


def bind():
    path = DIR / 'podium.sock'
    if path.exists():
        path.unlink()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(str(path))
    return sock


def play(name):
    w = wave.open(name)
    assert w.getframerate() == va.OUT_RATE and w.getnchannels() == 1
    pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    pcm = np.pad(pcm, (0, -len(pcm) % va.PACKET))
    opus, sock = va.Opus(), bind()
    start = time.monotonic()
    for i, at in enumerate(range(0, len(pcm), va.PACKET)):
        sock.sendto(b'P' + opus.encode(pcm[at:at + va.PACKET]), AGENT)
        time.sleep(max(0, start + (i + 1) * 0.12 - time.monotonic()))
    print(f'sent {i + 1} packets ({(i + 1) * 0.12:.1f} s)')


def listen(seconds, name):
    opus, sock = va.Opus(), bind()
    sock.settimeout(0.1)
    end, asked, packets, events, status = time.monotonic() + seconds, 0, [], [], None
    while time.monotonic() < end:
        if time.monotonic() - asked >= 1:
            asked = time.monotonic()
            sock.sendto(b'S1', AGENT)
        try:
            data = sock.recv(4096)
        except socket.timeout:
            continue
        t = round(seconds - (end - time.monotonic()), 2)
        if data[:1] == b'U':
            packets.append(data[1:])
        elif data[:1] == b'T':
            events.append((t, 'talk' if data[1:] == b'1' else 'quiet'))
        elif data[:1] == b'A':
            status = json.loads(data[1:])
    pcm = np.concatenate([opus.decode(p) for p in packets]) if packets else np.zeros(0, dtype=np.int16)
    with wave.open(name, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(va.OUT_RATE)
        w.writeframes(pcm.astype(np.int16).tobytes())
    size = sum(len(p) for p in packets)
    print(f'{len(packets)} packets, {size} bytes, {len(pcm) / va.OUT_RATE:.1f} s of voice in {seconds} s '
          f'({size * 8 / max(len(pcm) / va.OUT_RATE, 1e-9) / 1000:.1f} kbps while talking)')
    print('events', events)
    print('agent', status)


if __name__ == '__main__':
    if sys.argv[1] == 'play':
        play(sys.argv[2])
    else:
        listen(float(sys.argv[2]), sys.argv[3])
