"""Send the driver's voice only while they are talking (ER-10-9).

The driver is always connected (no push-to-talk button), so the logger itself
decides when to send: RNNoise (https://github.com/xiph/rnnoise, BSD) removes
background noise and gives, for each 10 ms frame at 48 kHz, the probability
that it holds speech. The gate opens on speech, keeps a short pre-roll so the
first syllable is not cut, and closes a little after the voice stops.

    gate = VoiceGate(RNNoise('/path/to/librnnoise.so'))
    for frame in frames_of_480_samples_48k:     # int16 values as floats
        for out in gate.process(frame):          # denoised frames to send (may be several)
            ...
        gate.talking                             # -> audio.ptt on/off

librnnoise.so is built from the xiph sources with gcc (see README.md here).
"""
import ctypes
from collections import deque

FRAME = 480            # 10 ms at 48 kHz, fixed by RNNoise


class RNNoise:
    def __init__(self, path):
        self.lib = ctypes.CDLL(path)
        self.lib.rnnoise_create.restype = ctypes.c_void_p
        self.lib.rnnoise_create.argtypes = [ctypes.c_void_p]
        self.lib.rnnoise_process_frame.restype = ctypes.c_float
        self.lib.rnnoise_process_frame.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float),
                                                   ctypes.POINTER(ctypes.c_float)]
        self.lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
        self.state = self.lib.rnnoise_create(None)
        self.inp = (ctypes.c_float * FRAME)()
        self.out = (ctypes.c_float * FRAME)()

    def process(self, frame):
        """frame: FRAME int16-range values -> (denoised list, speech probability 0..1)"""
        self.inp[:] = frame
        prob = self.lib.rnnoise_process_frame(self.state, self.out, self.inp)
        return list(self.out), prob

    def close(self):
        if self.state:
            self.lib.rnnoise_destroy(self.state)
            self.state = None


class VoiceGate:
    def __init__(self, rnnoise, open_prob=0.6, hold_ms=400, preroll_ms=100, min_frames=2):
        self.rnnoise = rnnoise
        self.open_prob = open_prob
        self.hold = hold_ms // 10
        self.min_frames = min_frames          # this many speech frames in a row to open (ignores clicks)
        self.preroll = deque(maxlen=preroll_ms // 10)
        self.talking = False
        self.quiet = 0
        self.run = 0

    def process(self, frame):
        clean, prob = self.rnnoise.process(frame)
        self.run = self.run + 1 if prob >= self.open_prob else 0
        if not self.talking:
            self.preroll.append(clean)
            if self.run >= self.min_frames:
                self.talking, self.quiet = True, 0
                out = list(self.preroll)
                self.preroll.clear()
                return out
            return []
        self.quiet = 0 if prob >= self.open_prob else self.quiet + 1
        if self.quiet > self.hold:
            self.talking = False
            return []
        return [clean]
