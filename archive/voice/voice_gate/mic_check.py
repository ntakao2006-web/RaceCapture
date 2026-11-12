"""Where does the driver's voice get spoiled? (2026-10-22: garbled and quiet on Discord, on Wi-Fi too)

Runs on the UNO Q host. Takes a raw recording of the microphone (S16_LE, 48 kHz, 1 or 2 channels)
and puts it through the same steps as voice_agent.py, writing one WAV per step to listen to:

  1_mic.wav      what the microphone gives (48 kHz)
  2_rnnoise.wav  after the high-pass and RNNoise (48 kHz)
  3_sent.wav     after the gate, 8 kHz and the Leveller's gain (what Opus is given)
  4_opus.wav     3 through Opus at BITRATE and back (what the pit hears, before the relay)

  python3 mic_check.py <raw> <channels> <out dir>   (voice_agent.py from /opt/ecocapture-voice)
mic_check.sh records and calls this.
"""
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, '/opt/ecocapture-voice')
import voice_agent as va  # noqa: E402


def dbfs(x):
    x = np.asarray(x, dtype=np.float64)
    rms = np.sqrt(np.mean(x ** 2)) if len(x) else 0
    peak = np.abs(x).max() if len(x) else 0
    to_db = lambda v: round(20 * np.log10(v / 32768), 1) if v > 0 else None
    return f'rms {to_db(rms)} dBFS, peak {to_db(peak)} dBFS'


def write(path, pcm, rate):
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.clip(pcm, -32768, 32767).astype(np.int16).tobytes())


def main(raw, channels, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    x = np.fromfile(raw, dtype=np.int16).reshape(-1, channels)
    mic = x.mean(axis=1)   # what arecord -c 1 (plughw) makes of a stereo device
    mic = mic[:len(mic) // va.FRAME * va.FRAME]
    rn, gate, down, opus = va.RNNoise(), va.Gate(), va.Downsampler(), va.Opus()
    highpass, leveller = va.HighPass(), va.Leveller()
    clean_all, sent, probs, talking = [], [], [], 0
    for i in range(0, len(mic), va.FRAME):
        clean, prob = rn.process(highpass.process(mic[i:i + va.FRAME]))
        clean_all.append(clean)
        probs.append(prob)
        for f in gate.process(clean, prob):
            sent.append(down.process(f))
        talking += gate.talking
    clean_all = np.concatenate(clean_all)
    sent = np.concatenate(sent) if sent else np.zeros(0, dtype=np.float32)
    sent = sent[:len(sent) // va.PACKET * va.PACKET]
    loud = np.concatenate([leveller.process(sent[i:i + va.PACKET]) for i in range(0, len(sent), va.PACKET)]
                          or [sent])
    clipped = int(np.count_nonzero(np.abs(loud) >= 32767))
    decoded = []
    for i in range(0, len(loud) - va.PACKET + 1, va.PACKET):
        packet = opus.encode(loud[i:i + va.PACKET].astype(np.int16))
        pcm = opus.decode(packet) if packet else None
        if pcm is not None:
            decoded.append(pcm)
    decoded = np.concatenate(decoded) if decoded else np.zeros(0, dtype=np.int16)
    if channels == 2:
        print('L/R', 'identical' if np.array_equal(x[:, 0], x[:, 1]) else
              f'corr {np.corrcoef(x[:, 0], x[:, 1])[0, 1]:.3f}')
    print('1 mic     ', dbfs(mic))
    print('2 rnnoise ', dbfs(clean_all))
    print(f'  gate open {100 * talking / max(len(probs), 1):.0f}% of the time, '
          f'speech prob >= {va.OPEN_PROB}: {100 * np.mean(np.array(probs) >= va.OPEN_PROB):.0f}%')
    print(f'3 sent     {dbfs(loud)}  (gain now {20 * np.log10(leveller.gain):.0f} dB, clipped samples {clipped}'
          f' = {100 * clipped / max(len(loud), 1):.2f}%)')
    print('4 opus    ', dbfs(decoded), f'({va.BITRATE} bps)')
    write(out / '1_mic.wav', mic, va.IN_RATE)
    write(out / '2_rnnoise.wav', clean_all, va.IN_RATE)
    write(out / '3_sent.wav', loud, va.OUT_RATE)
    write(out / '4_opus.wav', decoded, va.OUT_RATE)


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3])
