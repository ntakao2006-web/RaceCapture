"""Driver voice on the UNO Q host (ER-10-4, ER-10-9). Runs as `arduino` (audio group).

The Web container has no sound devices, so this small helper owns the USB audio
interface and talks to podium.py over Unix datagrams in /run/ecocapture-voice:

  podium -> agent  b'P'+opus   pit voice to play (8 kHz mono Opus, the relay's logger mix)
                   b'S1'       uplink wanted (repeat at least every UPLINK_HOLD_S)
  agent -> podium  b'U'+opus   driver voice, 8 kHz mono, one 120 ms Opus packet
                   b'T1'/b'T0' driver started / stopped talking (relay audio.ptt)
                   b'A'+json   status, answered to every b'S1' and b'C'
  podium -> agent  b'C'+json   new settings from the pit (SETTINGS keys, any subset)

The driver has no push-to-talk button: RNNoise (v0.1.1, see tools/voice_gate)
says per 10 ms whether it is speech, and only speech is encoded and sent. The
microphone is read only while uplink is wanted, so it costs nothing otherwise.
Devices are chosen like a phone does (Agent.router, re-checked every
ROUTE_CHECK_S): a connected Bluetooth headset first, otherwise the USB audio
card. Bluetooth goes through PipeWire. Its microphone (HFP) is only used on a
USB Bluetooth adapter: the UNO Q's built-in WCN3990 sends call audio to its PCM
pins, never to Linux (measured 2026-10-17: 1,888 SCO packets out, 0 back), so
with the built-in radio the headset is ears only (A2DP) and the USB microphone
stays in use. Any USB audio device is used, whatever its name (the race earphones
need not be the bench ones), and a re-plugged or reset dock comes back on its own.
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

# ALSA card name to prefer; otherwise the first USB audio device with a microphone
# (and a speaker, for the USB route) is used. The bench lavalier was "Pro", the
# USB-C earphone adapter of 2026-10-22 is "Audio": a fixed name missed it.
CARD = os.environ.get('ECOVOICE_CARD', '')
ASOUND = Path('/proc/asound')
SOCKET_DIR = Path(os.environ.get('ECOVOICE_DIR', '/run/ecocapture-voice'))
RNNOISE = os.environ.get('ECOVOICE_RNNOISE', '/opt/ecocapture-voice/librnnoise_old.so')
VOLUME = os.environ.get('ECOVOICE_VOLUME', '80%')   # 40 % (the device default) was inaudible on 2026-10-17
BITRATE = int(os.environ.get('ECOVOICE_BITRATE', '6000'))
# Make-up gain after RNNoise (it has already removed the background, so this does
# not raise the noise). Microphones differ by 20 dB and more: the lavalier peaked at
# -30 dBFS (2026-10-17), the USB-C earphone's speech sat near -50 dBFS (2026-10-22).
# So the gain follows the driver's speech level (Leveller): it starts at GAIN and
# moves within MIN_GAIN..MAX_GAIN towards TARGET_DBFS (RMS of speech, 8 kHz).
GAIN = 10 ** (float(os.environ.get('ECOVOICE_GAIN_DB', '14')) / 20)
MIN_GAIN, MAX_GAIN = 1.0, 10 ** (30 / 20)
TARGET_DBFS = -16.0      # -20 needed the volume raised in Discord (2026-10-22)
# Below this the microphone is cut before RNNoise: the USB-C earphone adapter gave a
# 29 Hz hum with harmonics (95 % of its signal, 2026-10-22) and RNNoise then took
# no speech for speech at all (0 % of frames; 14 % once cut, like a clean mic).
# 250 Hz rather than 150 also takes most wind noise, which came through loudly at a
# jog; the pit hears 8 kHz telephone band (300-3400 Hz) anyway.
HIGHPASS_HZ = 250

IN_RATE = 48000          # RNNoise works on 48 kHz, 10 ms frames
FRAME = 480
OUT_RATE = 8000          # what the relay decodes
PACKET = OUT_RATE * 120 // 1000   # 120 ms per Opus packet: fewest packets per second on LTE
OPEN_PROB, MIN_FRAMES, HOLD_FRAMES, PREROLL = 0.6, 2, 40, 10   # same rules as voice_gate.py
UPLINK_HOLD_S = 3.0
PLAY_IDLE_S = 2.0        # close the player after this long without pit voice
PLAY_PREBUFFER = 2       # packets queued before playback starts (240 ms against jitter)
LOW_WATER_S = 0.04       # only fill with silence once this little sound is left in ALSA
GAP = OUT_RATE // 50     # 20 ms of silence per fill
ROUTE_CHECK_S = 2.0
RECONNECT_S = 15.0        # first call; doubles after each miss up to RECONNECT_MAX_S
RECONNECT_MAX_S = 300.0
RECENT_FILE = Path(os.environ.get('STATE_DIRECTORY', '/var/lib/ecocapture-voice')) / 'recent_headsets.json'
SETTINGS_FILE = RECENT_FILE.with_name('settings.json')
# What the pit may change over the relay (logger.config, 2026-10-22: "a little quiet",
# "wind noise" had to be fixed by hand on the UNO Q). Name: (lowest, highest).
SETTINGS = {'level_db': (-30, -6), 'max_gain_db': (0, 40), 'lowcut_hz': (0, 400),
            'bitrate': (6000, 16000), 'volume': (0, 100)}
HFP, A2DP = 'headset-head-unit', 'a2dp-sink'
PW_ENV = {**os.environ, 'XDG_RUNTIME_DIR': os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')}

log = logging.getLogger('voice')


def usb_card(playback=True):
    """ALSA name of the USB audio device to use, or None."""
    found = []
    for card in sorted(ASOUND.glob('card[0-9]*'), key=lambda p: int(p.name[4:])):
        try:
            name = (card / 'id').read_text().strip()
        except OSError:
            continue
        if (card / 'usbid').exists() and any(card.glob('pcm*c')) and (not playback or any(card.glob('pcm*p'))):
            found.append(name)
    return CARD if CARD in found else found[0] if found else None


def settings():
    return {'level_db': TARGET_DBFS, 'max_gain_db': round(float(20 * np.log10(MAX_GAIN)), 1), 'lowcut_hz': HIGHPASS_HZ,
            'bitrate': BITRATE, 'volume': int(VOLUME.rstrip('%'))}


def apply_settings(new):
    """Takes the known keys of new, each clamped to its range; returns the settings in use."""
    global TARGET_DBFS, MAX_GAIN, HIGHPASS_HZ, BITRATE, VOLUME
    clean = {}
    for key, value in (new or {}).items():
        if key in SETTINGS and isinstance(value, (int, float)) and not isinstance(value, bool):
            low, high = SETTINGS[key]
            clean[key] = min(max(value, low), high)
    if 'level_db' in clean:
        TARGET_DBFS = float(clean['level_db'])
    if 'max_gain_db' in clean:
        MAX_GAIN = 10 ** (clean['max_gain_db'] / 20)
    if 'lowcut_hz' in clean:
        HIGHPASS_HZ = int(clean['lowcut_hz'])
    if 'bitrate' in clean:
        BITRATE = int(clean['bitrate'])
    if 'volume' in clean:
        VOLUME = f"{int(clean['volume'])}%"
    return settings()


def load_settings():
    try:
        apply_settings(json.loads(SETTINGS_FILE.read_text()))
    except (OSError, ValueError, AttributeError):
        pass


def save_settings():
    try:
        SETTINGS_FILE.write_text(json.dumps(settings()))
    except OSError:
        pass


def set_volume(route):
    if route['speaker'][0] == 'alsa':
        for control in ('Speaker', 'PCM', 'Headphone'):   # what the volume is called differs per device
            if subprocess.run(['amixer', '-q', '-c', route['speaker'][1], 'set', control, VOLUME, 'unmute'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0:
                break
    else:   # Bluetooth came up at 40-50 % here, which was inaudible (2026-10-17)
        subprocess.run(['wpctl', 'set-volume', str(route['speaker_id']), '1.0'], env=PW_ENV,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def pipewire_objects():
    try:
        out = subprocess.run(['pw-dump'], env=PW_ENV, capture_output=True, timeout=3, check=False).stdout
        return json.loads(out or b'[]')
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []


def usb_adapter(props):
    """True when the headset hangs off a USB Bluetooth adapter (call audio reaches Linux)."""
    hci = re.search(r'hci\d+', ' '.join(str(props.get(k, '')) for k in ('api.bluez5.path', 'api.bluez5.adapter')))
    return '/usb' in os.path.realpath(f'/sys/class/bluetooth/{hci.group(0) if hci else "hci0"}/device')


def bluetooth_route(objects):
    """(route, None) for a connected headset ready to use, (None, (device id, profile index))
    when its profile must change first, or (None, None) when there is none."""
    for dev in objects:
        props = dev.get('info', {}).get('props', {})
        if not dev.get('type', '').endswith(':Device') or props.get('device.api') != 'bluez5':
            continue
        params = dev['info'].get('params', {})
        profiles = {p.get('name'): p.get('index') for p in params.get('EnumProfile', [])}
        active = (params.get('Profile') or [{}])[0].get('name')
        hfp = usb_adapter(props) and HFP in profiles
        want = HFP if hfp else A2DP if A2DP in profiles else None
        if want is None:
            continue
        if active != want:
            return None, (dev['id'], profiles[want])
        nodes = [o for o in objects if o.get('type', '').endswith(':Node')
                 and o.get('info', {}).get('props', {}).get('device.id') == dev['id']]
        sink = next((n for n in nodes if n['info']['props'].get('media.class') == 'Audio/Sink'), None)
        source = next((n for n in nodes if str(n['info']['props'].get('media.class', '')).startswith('Audio/Source')), None)
        if sink is None:
            continue
        card = None if hfp and source else usb_card(playback=False)
        mic = ('pw', source['info']['props']['node.name']) if hfp and source else ('alsa', card) if card else None
        return {'kind': 'bluetooth-hfp' if hfp else 'bluetooth-a2dp', 'name': props.get('device.description', 'Bluetooth'),
                'address': str(props.get('api.bluez5.address', '')).upper(),
                'speaker': ('pw', sink['info']['props']['node.name']), 'speaker_id': sink['id'], 'mic': mic}, None
    return None, None


def choose_route():
    """Where pit voice plays and the driver is heard: Bluetooth headset, else USB card, else None."""
    route, change = bluetooth_route(pipewire_objects())
    if change:
        subprocess.run(['wpctl', 'set-profile', str(change[0]), str(change[1])], env=PW_ENV,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        time.sleep(1.5)
        route, _ = bluetooth_route(pipewire_objects())
    if route:
        return route
    card = usb_card()
    if card:
        return {'kind': 'usb', 'name': card, 'speaker': ('alsa', card), 'speaker_id': None, 'mic': ('alsa', card)}
    return None


def recent_headsets():
    """Headset addresses, most recently used first (kept across restarts)."""
    try:
        return [m for m in json.loads(RECENT_FILE.read_text()) if re.fullmatch(r'[0-9A-F:]{17}', m)]
    except (OSError, ValueError, TypeError):
        return []


def remember_headset(mac):
    recent = [mac] + [m for m in recent_headsets() if m != mac]
    try:
        RECENT_FILE.write_text(json.dumps(recent[:10]))
    except OSError:
        pass


def reconnect_order(paired, recent):
    """Like a phone: the headset used last first, then other recently used ones, then the rest."""
    return [m for m in recent if m in paired] + [m for m in paired if m not in recent]


def reconnect_headsets():
    """Call paired, trusted headsets until one connects (most headsets connect on
    their own when taken out of the case; this covers the ones that wait to be called)."""
    try:
        paired = subprocess.run(['bluetoothctl', 'devices', 'Paired'], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return
    for mac in reconnect_order(re.findall(r'Device ([0-9A-F:]{17})', paired), recent_headsets()):
        try:
            info = subprocess.run(['bluetoothctl', 'info', mac], capture_output=True, text=True, timeout=5).stdout
            if 'Trusted: yes' not in info or 'Audio Sink' not in info:
                continue
            if 'Connected: yes' in info:
                return
            subprocess.run(['bluetoothctl', '--timeout', '6', 'connect', mac], capture_output=True, timeout=10)
            if 'Connected: yes' in subprocess.run(['bluetoothctl', 'info', mac], capture_output=True, text=True, timeout=5).stdout:
                return
        except (OSError, subprocess.TimeoutExpired):
            pass


def player_command(speaker):
    kind, target = speaker
    if kind == 'alsa':
        # Start on the first samples (not when the whole buffer is full), so the
        # player's clock knows how much is still queued in ALSA.
        return ['aplay', '-q', '-D', f'plughw:CARD={target},DEV=0', '-f', 'S16_LE', '-r', str(OUT_RATE),
                '-c', '1', '-t', 'raw', '--buffer-time=500000', '--start-delay=20000']
    return ['pw-cat', '--playback', '-a', '--target', target, '--rate', str(OUT_RATE), '--channels', '1',
            '--format', 's16', '--latency', '60ms', '-']


def recorder_command(mic):
    kind, target = mic
    if kind == 'alsa':
        return ['arecord', '-q', '-D', f'plughw:CARD={target},DEV=0', '-f', 'S16_LE', '-r', str(IN_RATE), '-c', '1', '-t', 'raw']
    return ['pw-cat', '--record', '-a', '--target', target, '--rate', str(IN_RATE), '--channels', '1', '--format', 's16', '-']


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

    def set_bitrate(self, bitrate):
        self.lib.opus_encoder_ctl(self.enc, self.SET_BITRATE, bitrate)

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


class HighPass:
    """Linear-phase FIR high-pass (HIGHPASS_HZ) on 10 ms frames, by FFT (overlap-save):
    -75 dB at 100 Hz, -22 dB at 200 Hz, flat from 300 Hz, about 7 % of one UNO Q core
    (the same filter by np.convolve took 22 %). Delay 16 ms."""
    def __init__(self, taps=1569, size=2048):
        self.hz = HIGHPASS_HZ
        n = np.arange(taps) - (taps - 1) / 2
        h = np.sinc(2 * HIGHPASS_HZ / IN_RATE * n) * np.blackman(taps)
        h = -h / h.sum()
        h[(taps - 1) // 2] += 1
        self.H = np.fft.rfft(h, size)
        self.buf = np.zeros(size, dtype=np.float32)

    def process(self, x):
        if not self.hz:
            return np.asarray(x, dtype=np.float32)
        self.buf = np.concatenate([self.buf[len(x):], np.asarray(x, dtype=np.float32)])
        return np.fft.irfft(np.fft.rfft(self.buf) * self.H, len(self.buf))[-len(x):].astype(np.float32)


class Leveller:
    """Gain that brings the driver's speech to TARGET_DBFS, learnt from sent packets only
    (the gate has already left out the silence). Kept across talk spurts."""
    def __init__(self, gain=GAIN):
        self.gain = min(max(gain, MIN_GAIN), MAX_GAIN)

    def process(self, pcm):
        pcm = np.asarray(pcm, dtype=np.float32)
        rms = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2))) if len(pcm) else 0.0
        if rms > 3:   # not the padded silence at the end of a spurt
            want = min(max(32768 * 10 ** (TARGET_DBFS / 20) / rms, MIN_GAIN), MAX_GAIN)
            # 120 ms packets: louder comes down within a packet or two, quieter goes up over ~1 s
            self.gain += (want - self.gain) * (0.5 if want < self.gain else 0.12)
        # A shout right after quiet talk must not clip while the gain is still coming down.
        peak = float(np.abs(pcm).max()) if len(pcm) else 0.0
        gain = min(self.gain, 0.9 * 32767 / peak) if peak else self.gain
        return np.clip(pcm * gain, -32768, 32767)


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


def stop_recorder(proc, timeout=2.0):
    """End a recorder whose pipe nobody reads any more. Our end is closed first:
    arecord retries a write that SIGTERM interrupts, so with a full pipe
    terminate() + wait() alone waits forever (2026-10-23: the microphone was
    dead for 2 hours after the first uplink pause)."""
    for stop in (proc.stdout.close, proc.terminate):
        try:
            stop()
        except OSError:
            pass
    try:
        proc.wait(timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


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
        self.route = None
        self.stats = {'played': 0, 'sent': 0, 'talking': False, 'capturing': False, 'playing': False, 'mic_errors': 0, 'gaps': 0,
                      'gain_db': round(20 * np.log10(GAIN), 1)}
        self.leveller = Leveller()

    def tell(self, data):
        try:
            self.sock.sendto(data, self.podium)
        except OSError:
            pass   # podium.py not running: nothing to tell

    def status(self):
        route = self.route or {}
        return {**self.stats, 'card': usb_card(playback=False), 'card_present': usb_card(playback=False) is not None, 'route': route.get('kind'),
                'device': route.get('name'), 'mic': bool(route.get('mic')), 'settings': settings()}

    def configure(self, new):
        if not new:
            return   # the pit only asked what is in use
        apply_settings(new)
        with self.opus_lock:
            self.opus.set_bitrate(BITRATE)
        if self.route and 'volume' in (new or {}):
            set_volume(self.route)   # heard at once, not only at the next pit message
        save_settings()
        log.info('settings from the pit: %s', settings())

    def router(self):
        """Follow the devices like a phone: a headset that connects takes over, one that drops gives way."""
        called, wait = 0.0, RECONNECT_S
        while True:
            self.use(choose_route())   # follow a drop at once; calling the headset back comes after
            if self.route is not None and self.route['kind'].startswith('bluetooth'):
                called, wait = time.monotonic(), RECONNECT_S   # first call back RECONNECT_S after a drop
            elif time.monotonic() - called > wait:
                # A headset left in its case cannot answer; calling it every few seconds all
                # night preceded a hung built-in radio (2026-10-18), so back off.
                called, wait = time.monotonic(), min(RECONNECT_MAX_S, wait * 2)
                reconnect_headsets()
                self.use(choose_route())
            time.sleep(ROUTE_CHECK_S)

    def use(self, route):
        if route != self.route:
            if route and route.get('address'):
                remember_headset(route['address'])
            log.info('audio route: %s', route and f"{route['kind']} ({route['name']}), mic {route['mic']}")
            self.route = route

    # --- pit voice -> earphone -------------------------------------------------
    def player(self):
        while True:
            self.play_event.wait()
            self.play_event.clear()
            if len(self.play_queue) < PLAY_PREBUFFER:
                time.sleep(0.12)
                if not self.play_queue:
                    continue
            route = self.route
            if not route:
                self.play_queue.clear()
                continue
            set_volume(route)
            proc = subprocess.Popen(player_command(route['speaker']), env=PW_ENV,
                                    stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.stats['playing'] = True
            idle_since, started, written = None, time.monotonic(), 0.0
            gap = np.zeros(GAP, dtype=np.int16).tobytes()
            try:
                while self.route == route:   # a headset came or went: reopen on the new device
                    queued = written - (time.monotonic() - started)   # seconds of sound still in ALSA
                    if self.play_queue:
                        with self.opus_lock:
                            pcm = self.opus.decode(self.play_queue.popleft())
                        data = pcm.tobytes() if pcm is not None else np.zeros(PACKET, dtype=np.int16).tobytes()
                        idle_since = None
                        self.stats['played'] += 1
                    else:
                        idle_since = idle_since or time.monotonic()
                        if time.monotonic() - idle_since > PLAY_IDLE_S:
                            break
                        if queued > LOW_WATER_S:
                            time.sleep(0.01)   # the next packet may still arrive in time
                            continue
                        # About to run dry: a little silence keeps the device fed (no clicks).
                        data = gap
                        if self.stats['playing'] and idle_since and time.monotonic() - idle_since < 0.5:
                            self.stats['gaps'] += 1
                    if queued < 0:   # it ran dry anyway; restart the clock from now
                        started, written = time.monotonic(), 0.0
                    proc.stdin.write(data)
                    proc.stdin.flush()
                    written += len(data) / 2 / OUT_RATE
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
            route = self.route
            if time.monotonic() > self.uplink_until or not route or not route['mic']:
                time.sleep(0.3)
                continue
            proc = subprocess.Popen(recorder_command(route['mic']), env=PW_ENV,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.stats['capturing'] = True
            gate, down, pending = Gate(), Downsampler(), np.zeros(0, dtype=np.float32)
            highpass = HighPass()
            try:
                while time.monotonic() <= self.uplink_until and self.route == route:
                    raw = proc.stdout.read(FRAME * 2)
                    if len(raw) < FRAME * 2:
                        self.stats['mic_errors'] += 1
                        break
                    if highpass.hz != HIGHPASS_HZ:   # changed from the pit
                        highpass = HighPass()
                    clean, prob = rnnoise.process(highpass.process(np.frombuffer(raw, dtype=np.int16)))
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
                stop_recorder(proc)
            time.sleep(0.5)

    def send_packet(self, pcm):
        with self.opus_lock:
            packet = self.opus.encode(self.leveller.process(pcm).astype(np.int16))
            self.stats['gain_db'] = round(20 * np.log10(self.leveller.gain), 1)
        if packet:
            self.tell(b'U' + packet)
            self.stats['sent'] += 1

    # --- messages from podium.py ----------------------------------------------
    def serve(self):
        self.route = choose_route()
        threading.Thread(target=self.router, daemon=True).start()
        threading.Thread(target=self.player, daemon=True).start()
        threading.Thread(target=self.capture, daemon=True).start()
        log.info('voice agent ready on %s (USB card %s)', self.path, usb_card(playback=False))
        while True:
            data = self.sock.recv(4096)
            if data[:1] == b'P' and len(data) > 1:
                self.play_queue.append(data[1:])
                self.play_event.set()
            elif data == b'S1':
                self.uplink_until = time.monotonic() + UPLINK_HOLD_S
                self.tell(b'A' + json.dumps(self.status()).encode())
            elif data[:1] == b'C':
                try:
                    new = json.loads(data[1:])
                except ValueError:
                    new = None
                if isinstance(new, dict):
                    self.configure(new)
                self.tell(b'A' + json.dumps(self.status()).encode())


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    load_settings()
    Agent().serve()
