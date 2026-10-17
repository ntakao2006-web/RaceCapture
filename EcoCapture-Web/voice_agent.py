"""Driver voice on the UNO Q host (ER-10-4, ER-10-9). Runs as `arduino` (audio group).

The Web container has no sound devices, so this small helper owns the USB audio
interface and talks to podium.py over Unix datagrams in /run/ecocapture-voice:

  podium -> agent  b'P'+opus   pit voice to play (8 kHz mono Opus, the relay's logger mix)
                   b'S1'       uplink wanted (repeat at least every UPLINK_HOLD_S)
  agent -> podium  b'U'+opus   driver voice, 8 kHz mono, one 120 ms Opus packet
                   b'T1'/b'T0' driver started / stopped talking (relay audio.ptt)
                   b'A'+json   status, answered to every b'S1'

The driver has no push-to-talk button: RNNoise (v0.1.1, see tools/voice_gate)
says per 10 ms whether it is speech, and only speech is encoded and sent. The
microphone is read only while uplink is wanted, so it costs nothing otherwise.
Devices are found by ALSA card name every time, so a re-plugged or reset dock
comes back on its own.
"""
import collections
import ctypes
import ctypes.util
import json
import logging
import os
import re
import socket
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

CARD = os.environ.get('ECOVOICE_CARD', 'Pro')
SOCKET_DIR = Path(os.environ.get('ECOVOICE_DIR', '/run/ecocapture-voice'))
RNNOISE = os.environ.get('ECOVOICE_RNNOISE', '/opt/ecocapture-voice/librnnoise_old.so')
VOLUME = os.environ.get('ECOVOICE_VOLUME', '80%')   # 40 % (the device default) was inaudible on 2026-10-17
BITRATE = int(os.environ.get('ECOVOICE_BITRATE', '6000'))
# The lavalier at full capture volume peaked at only -30 dBFS after RNNoise when
# spoken to normally (2026-10-17), too quiet for the pit. RNNoise has already
# removed the background, so a fixed make-up gain does not raise the noise.
GAIN = 10 ** (float(os.environ.get('ECOVOICE_GAIN_DB', '14')) / 20)

IN_RATE = 48000          # RNNoise works on 48 kHz, 10 ms frames
FRAME = 480
OUT_RATE = 8000          # what the relay decodes
PACKET = OUT_RATE * 120 // 1000   # 120 ms per Opus packet: fewest packets per second on LTE
OPEN_PROB, MIN_FRAMES, HOLD_FRAMES, PREROLL = 0.6, 2, 40, 10   # same rules as voice_gate.py
UPLINK_HOLD_S = 3.0
PLAY_IDLE_S = 2.0        # close the player after this long without pit voice
PLAY_PREBUFFER = 2       # packets queued before playback starts (240 ms against jitter)

log = logging.getLogger('voice')


def card_present(name=CARD):
    try:
        return re.search(r'\[' + re.escape(name) + r'\s*\]', Path('/proc/asound/cards').read_text()) is not None
    except OSError:
        return False


def set_volume():
    subprocess.run(['amixer', '-q', '-c', CARD, 'set', 'Speaker', VOLUME, 'unmute'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


class Opus:
    """libopus through ctypes (the UNO Q has libopus.so.0 but no headers)."""
    VOIP, SET_BITRATE = 2048, 4002

    def __init__(self):
        self.lib = ctypes.CDLL(ctypes.util.find_library('opus') or 'libopus.so.0')
        self.lib.opus_encoder_create.restype = ctypes.c_void_p
        self.lib.opus_decoder_create.restype = ctypes.c_void_p
        self.lib.opus_encode.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int32]
        self.lib.opus_decode.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        self.lib.opus_encoder_ctl.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int32]
        err = ctypes.c_int()
        self.enc = self.lib.opus_encoder_create(OUT_RATE, 1, self.VOIP, ctypes.byref(err))
        self.lib.opus_encoder_ctl(self.enc, self.SET_BITRATE, BITRATE)
        self.dec = self.lib.opus_decoder_create(OUT_RATE, 1, ctypes.byref(err))
        self.out = ctypes.create_string_buffer(1275)
        self.pcm = np.zeros(PACKET, dtype=np.int16)

    def encode(self, pcm):
        pcm = np.ascontiguousarray(pcm, dtype=np.int16)
        n = self.lib.opus_encode(self.enc, pcm.ctypes.data, len(pcm), self.out, len(self.out))
        return self.out.raw[:n] if n > 0 else None

    def decode(self, packet):
        n = self.lib.opus_decode(self.dec, packet, len(packet), self.pcm.ctypes.data, PACKET, 0)
        return self.pcm[:n].copy() if n > 0 else None


class Downsampler:
    """48 kHz -> 8 kHz: 3.4 kHz windowed-sinc low-pass, then every 6th sample."""
    def __init__(self, taps=97):
        n = np.arange(taps) - (taps - 1) / 2
        h = np.sinc(2 * 3400 / IN_RATE * n) * np.hamming(taps)
        self.h = (h / h.sum()).astype(np.float32)
        self.tail = np.zeros(taps - 1, dtype=np.float32)
        self.phase = 0

    def process(self, x):
        buf = np.concatenate([self.tail, np.asarray(x, dtype=np.float32)])
        y = np.convolve(buf, self.h, mode='valid')
        self.tail = buf[-(len(self.h) - 1):]
        out = y[self.phase::6]
        self.phase = (self.phase - len(y)) % 6
        return out


class RNNoise:
    def __init__(self, path=RNNOISE):
        self.lib = ctypes.CDLL(path)
        self.lib.rnnoise_create.restype = ctypes.c_void_p
        self.lib.rnnoise_create.argtypes = [ctypes.c_void_p]
        self.lib.rnnoise_process_frame.restype = ctypes.c_float
        self.lib.rnnoise_process_frame.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        self.lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
        self.state = self.lib.rnnoise_create(None)
        self.out = np.zeros(FRAME, dtype=np.float32)

    def process(self, frame):
        x = np.ascontiguousarray(frame, dtype=np.float32)
        prob = self.lib.rnnoise_process_frame(self.state, self.out.ctypes.data, x.ctypes.data)
        return self.out.copy(), prob


class Gate:
    """VoiceGate of tools/voice_gate/voice_gate.py over a speech probability."""
    def __init__(self):
        self.pre = collections.deque(maxlen=PREROLL)
        self.talking = False
        self.run = self.quiet = 0

    def process(self, clean, prob):
        self.run = self.run + 1 if prob >= OPEN_PROB else 0
        if not self.talking:
            self.pre.append(clean)
            if self.run >= MIN_FRAMES:
                self.talking, self.quiet = True, 0
                out = list(self.pre)
                self.pre.clear()
                return out
            return []
        self.quiet = 0 if prob >= OPEN_PROB else self.quiet + 1
        if self.quiet > HOLD_FRAMES:
            self.talking = False
            return []
        return [clean]


class Agent:
    def __init__(self, directory=SOCKET_DIR):
        self.path = directory / 'agent.sock'
        self.podium = str(directory / 'podium.sock')
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        if self.path.exists():
            self.path.unlink()
        self.sock.bind(str(self.path))
        os.chmod(self.path, 0o660)
        self.opus = Opus()
        self.opus_lock = threading.Lock()
        self.play_queue = collections.deque(maxlen=25)
        self.play_event = threading.Event()
        self.uplink_until = 0.0
        self.stats = {'played': 0, 'sent': 0, 'talking': False, 'capturing': False, 'playing': False, 'mic_errors': 0}

    def tell(self, data):
        try:
            self.sock.sendto(data, self.podium)
        except OSError:
            pass   # podium.py not running: nothing to tell

    def status(self):
        return {**self.stats, 'card': CARD, 'card_present': card_present()}

    # --- pit voice -> earphone -------------------------------------------------
    def player(self):
        while True:
            self.play_event.wait()
            self.play_event.clear()
            if len(self.play_queue) < PLAY_PREBUFFER:
                time.sleep(0.12)
                if not self.play_queue:
                    continue
            if not card_present():
                self.play_queue.clear()
                continue
            set_volume()
            proc = subprocess.Popen(['aplay', '-q', '-D', f'plughw:CARD={CARD},DEV=0', '-f', 'S16_LE', '-r', str(OUT_RATE),
                                     '-c', '1', '-t', 'raw', '--buffer-time=360000'],
                                    stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.stats['playing'] = True
            idle_since = None
            silence = np.zeros(PACKET, dtype=np.int16).tobytes()
            try:
                while True:
                    if self.play_queue:
                        with self.opus_lock:
                            pcm = self.opus.decode(self.play_queue.popleft())
                        data = pcm.tobytes() if pcm is not None else silence
                        idle_since = None
                        self.stats['played'] += 1
                    else:
                        idle_since = idle_since or time.monotonic()
                        if time.monotonic() - idle_since > PLAY_IDLE_S:
                            break
                        data = silence   # keep the device fed between words: no clicks
                    proc.stdin.write(data)   # blocks at real-time pace once ALSA's buffer is full
                    proc.stdin.flush()
            except (BrokenPipeError, OSError):
                log.warning('player stopped (device gone?)')
            finally:
                self.stats['playing'] = False
                for stop in (proc.stdin.close, proc.terminate):
                    try:
                        stop()
                    except OSError:
                        pass
                proc.wait()

    # --- driver microphone -> relay -------------------------------------------
    def capture(self):
        rnnoise = RNNoise()
        while True:
            if time.monotonic() > self.uplink_until or not card_present():
                time.sleep(0.3)
                continue
            proc = subprocess.Popen(['arecord', '-q', '-D', f'plughw:CARD={CARD},DEV=0', '-f', 'S16_LE', '-r', str(IN_RATE),
                                     '-c', '1', '-t', 'raw'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.stats['capturing'] = True
            gate, down, pending = Gate(), Downsampler(), np.zeros(0, dtype=np.float32)
            try:
                while time.monotonic() <= self.uplink_until:
                    raw = proc.stdout.read(FRAME * 2)
                    if len(raw) < FRAME * 2:
                        self.stats['mic_errors'] += 1
                        break
                    clean, prob = rnnoise.process(np.frombuffer(raw, dtype=np.int16))
                    was = gate.talking
                    frames = gate.process(clean, prob)
                    if gate.talking and not was:
                        self.tell(b'T1')
                    for f in frames:
                        pending = np.concatenate([pending, down.process(f)])
                    while len(pending) >= PACKET:
                        self.send_packet(pending[:PACKET])
                        pending = pending[PACKET:]
                    if was and not gate.talking:
                        if len(pending):
                            self.send_packet(np.pad(pending, (0, PACKET - len(pending))))
                        pending = np.zeros(0, dtype=np.float32)
                        down = Downsampler()
                        self.tell(b'T0')
                    self.stats['talking'] = gate.talking
            finally:
                if gate.talking:
                    self.tell(b'T0')
                self.stats.update(capturing=False, talking=False)
                proc.terminate()
                proc.wait()
            time.sleep(0.5)

    def send_packet(self, pcm):
        with self.opus_lock:
            packet = self.opus.encode(np.clip(pcm * GAIN, -32768, 32767).astype(np.int16))
        if packet:
            self.tell(b'U' + packet)
            self.stats['sent'] += 1

    # --- messages from podium.py ----------------------------------------------
    def serve(self):
        threading.Thread(target=self.player, daemon=True).start()
        threading.Thread(target=self.capture, daemon=True).start()
        log.info('voice agent ready on %s (card %s)', self.path, CARD)
        while True:
            data = self.sock.recv(4096)
            if data[:1] == b'P' and len(data) > 1:
                self.play_queue.append(data[1:])
                self.play_event.set()
            elif data == b'S1':
                self.uplink_until = time.monotonic() + UPLINK_HOLD_S
                self.tell(b'A' + json.dumps(self.status()).encode())


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    Agent().serve()
