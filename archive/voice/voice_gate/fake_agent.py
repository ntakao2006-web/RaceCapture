"""Stand-in for voice_agent.py that "talks" from a WAV, for LTE capacity tests without a mic (ER-10-9).

podium.py sends to /run/ecocapture-voice/agent.sock. Move the real agent's socket aside first
(it keeps working from the renamed path once moved back), then run this on the UNO Q host:

  mv /run/ecocapture-voice/agent.sock /run/ecocapture-voice/agent.sock.real
  python3 fake_agent.py driver_reply.wav 4 6     # talk 4 s, silent 6 s, repeat (0 = always talking)
  mv /run/ecocapture-voice/agent.sock.real /run/ecocapture-voice/agent.sock

Packets are the agent's own format (8 kHz mono Opus at ECOVOICE_BITRATE, 120 ms), sent only while
podium.py keeps asking for uplink (b'S1'). Pit voice (b'P') is counted and dropped: nothing plays.
"""
import json
import os
import socket
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.home() / 'EcoCapture-Web'))
import voice_agent as va   # noqa: E402

DIR = Path('/run/ecocapture-voice')


def packets(name, opus):
    w = wave.open(name)
    assert w.getframerate() == va.OUT_RATE and w.getnchannels() == 1, 'needs an 8 kHz mono WAV'
    pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    pcm = np.pad(pcm, (0, -len(pcm) % va.PACKET))
    return [opus.encode(pcm[at:at + va.PACKET]) for at in range(0, len(pcm), va.PACKET)]


def main(name, talk_s, quiet_s):
    path = DIR / 'agent.sock'
    if path.exists():
        sys.exit('agent.sock still exists: move the real one aside first')
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(str(path))
    os.chmod(path, 0o660)
    podium = str(DIR / 'podium.sock')
    voice = packets(name, va.Opus())
    stats = {'sent': 0, 'bytes': 0, 'played': 0, 'talking': False}
    want = [0.0]

    def tell(data):
        try:
            sock.sendto(data, podium)
        except OSError:
            pass

    def talker():
        i, since = 0, time.monotonic()
        while True:
            now = time.monotonic()
            if now > want[0]:
                if stats['talking']:
                    tell(b'T0')
                    stats['talking'] = False
                time.sleep(0.2)
                since = now
                continue
            phase = (now - since) % (talk_s + quiet_s) if talk_s else 0
            on = not talk_s or phase < talk_s
            if on != stats['talking']:
                tell(b'T1' if on else b'T0')
                stats['talking'] = on
            if on:
                packet = voice[i % len(voice)]
                i += 1
                tell(b'U' + packet)
                stats['sent'] += 1
                stats['bytes'] += len(packet)
            time.sleep(va.PACKET / va.OUT_RATE)

    def report():
        last = dict(stats)
        while True:
            time.sleep(5)
            print(f"{time.strftime('%H:%M:%S')} up {stats['sent'] - last['sent']:3d} pkt "
                  f"({(stats['bytes'] - last['bytes']) * 8 / 5000:.1f} kbps)  pit voice in {stats['played'] - last['played']:3d} pkt  "
                  f"uplink wanted {'yes' if time.monotonic() < want[0] else 'no'}", flush=True)
            last = dict(stats)

    threading.Thread(target=talker, daemon=True).start()
    threading.Thread(target=report, daemon=True).start()
    print(f'fake agent: {len(voice)} packets from {name}, talk {talk_s} s / quiet {quiet_s} s', flush=True)
    try:
        while True:
            data = sock.recv(4096)
            if data[:1] == b'P':
                stats['played'] += 1
            elif data == b'S1':
                want[0] = time.monotonic() + va.UPLINK_HOLD_S
                tell(b'A' + json.dumps({'fake': True, 'sent': stats['sent'], 'talking': stats['talking']}).encode())
    finally:
        path.unlink(missing_ok=True)


if __name__ == '__main__':
    main(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]))
