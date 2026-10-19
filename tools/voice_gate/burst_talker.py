"""Logger stand-in that sends its voice the way the UNO Q does on LTE: half a second at a time (ER-10-9).

podium.py bundles 0.5 s of 120 ms Opus packets into one AT+CASEND, so the relay receives four
packets at once every ~0.5 s. Run next to pit_loop.py (the listener) on the relay host to see
how much of it reaches the pit:

  python3 burst_talker.py ws://127.0.0.1:3100/ws/audio/burst-test driver_reply_norm.wav 20

Standard library + libopus only (the home server has no numpy).
"""
import sys
import time

import pit_loop as pl

PACKET = 960   # 120 ms at 8 kHz: the logger's uplink packet
BUNDLE = 4     # packets per modem send (VOICE_UP_FLUSH_S = 0.5 on LTE)


def main(url, say, seconds, bundle=BUNDLE):
    """`bundle` packets per send; 8 stands for two modem sends arriving together."""
    voice = pl.frames(say, frame=PACKET, bitrate=6000)   # like voice_agent.py
    ws = pl.WS(url)
    ws.json({'type': 'hello', 'client_id': 'burst-talker', 'protocol': 2, 'role': 'logger', 'audio_formats': []})
    ws.json({'type': 'audio.ptt', 'active': True})
    start, i = time.monotonic(), 0
    while time.monotonic() - start < seconds:
        for _ in range(bundle):
            ws.send(2, voice[i % len(voice)])
            i += 1
        ws.drain()
        time.sleep(max(0, start + i * PACKET / 8000 - time.monotonic()))
    ws.json({'type': 'audio.ptt', 'active': False})
    time.sleep(1)
    print(f'burst talker sent {i} packets ({i * 0.12:.1f} s of voice) in bundles of {bundle}', flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else BUNDLE)
