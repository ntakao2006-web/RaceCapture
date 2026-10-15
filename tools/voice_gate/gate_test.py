"""Bench test of voice_gate.py with synthetic car noise (ER-10-9).

Lays speech clips (48 kHz mono 16-bit WAV) at random times over 120 s of
synthetic in-car noise (engine harmonics + rumble + wind) at several levels, and
reports per level:
  - tx      : share of time the gate sends (what the LTE pays for)
  - speech  : share of speech frames that were sent (should be ~100 %)
  - false   : share of noise-only time sent anyway (mostly the hold after each phrase)
  - stray   : share of time more than 1 s away from any speech that was sent (noise triggers)
compared with a plain loudness gate, plus RNNoise's CPU time per 10 ms frame.

    python3 gate_test.py --lib ~/rnnoise-build/librnnoise.so --out /tmp/gated clip*.wav
"""
import argparse
import array
import math
import random
import sys
import time
import wave

from voice_gate import FRAME, RNNoise, VoiceGate

RATE = 48000
SECONDS = 120


def read_wav(path):
    with wave.open(path) as w:
        assert w.getframerate() == RATE and w.getnchannels() == 1 and w.getsampwidth() == 2, path
        return array.array('h', w.readframes(w.getnframes()))


def car_noise(n, level, rng):
    """Engine (~2400 rpm, 4-cyl firing at 80 Hz + harmonics), road rumble, wind."""
    out = array.array('f', bytes(4 * n))
    brown = wind = lp = 0.0
    rpm_wobble = 0.0
    phase = 0.0
    for i in range(n):
        rpm_wobble += (rng.random() - 0.5) * 0.002
        rpm_wobble *= 0.9999
        phase += 2 * math.pi * 80 * (1 + rpm_wobble) / RATE
        engine = math.sin(phase) + 0.5 * math.sin(2 * phase) + 0.3 * math.sin(3 * phase) + 0.15 * math.sin(5 * phase)
        brown = 0.995 * brown + (rng.random() - 0.5) * 0.4
        white = rng.random() - 0.5
        lp += 0.15 * (white - lp)
        wind = white - lp                           # crude high-pass hiss
        out[i] = level * (0.35 * engine + 1.2 * brown + 0.5 * wind)
    return out


def speech_mask(clip):
    """10 ms frames of a clean clip that actually hold voice (TTS adds silence around it)."""
    mask = []
    for f in range(len(clip) // FRAME):
        seg = clip[f * FRAME:(f + 1) * FRAME]
        rms = math.sqrt(sum(v * v for v in seg) / FRAME)
        mask.append(rms > 300)
    return mask


def build(clips, rng):
    n = SECONDS * RATE
    voice = array.array('f', bytes(4 * n))
    truth = [False] * (n // FRAME)
    t = 2 * RATE
    order = clips * 2
    rng.shuffle(order)
    for clip in order:
        if t + len(clip) >= n:
            break
        for i, v in enumerate(clip):
            voice[t + i] = v
        for f, on in enumerate(speech_mask(clip)):
            if on:
                truth[t // FRAME + f] = True
        t += len(clip) + int(rng.uniform(4, 12) * RATE)
    return voice, truth


def run_gate(signal, gate_frames):
    sent = [False] * (len(signal) // FRAME)
    gate_frames(signal, sent)
    return sent


def rnnoise_gate(lib, out_path):
    def go(signal, sent):
        rn = RNNoise(lib)
        gate = VoiceGate(rn)
        cost = 0.0
        pending = 0                       # pre-roll frames handed back late
        result = []
        for f in range(len(sent)):
            frame = [max(-32768.0, min(32767.0, v)) for v in signal[f * FRAME:(f + 1) * FRAME]]
            t0 = time.perf_counter()
            out = gate.process(frame)
            cost += time.perf_counter() - t0
            if out:
                for k in range(len(out)):
                    sent[f - (len(out) - 1) + k] = True
            if out_path is not None:
                result.append(out[-1] if out else [0.0] * FRAME)
        rn.close()
        go.cost_us = cost / len(sent) * 1e6
        if out_path:
            with wave.open(out_path, 'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
                w.writeframes(array.array('h', (int(max(-32768, min(32767, v))) for fr in result for v in fr)).tobytes())
    return go


def loudness_gate(signal, sent):
    """Plain gate: 6 dB over the noise floor (learned from the quietest 20 % of frames), 400 ms hold."""
    rms = [math.sqrt(sum(v * v for v in signal[f * FRAME:(f + 1) * FRAME]) / FRAME) for f in range(len(sent))]
    floor = sorted(rms)[len(rms) // 5]
    hold = 0
    for f, r in enumerate(rms):
        hold = 40 if r > floor * 2 else hold - 1
        sent[f] = hold > 0


def score(sent, truth):
    speech = sum(1 for s, t in zip(sent, truth) if t)
    hit = sum(1 for s, t in zip(sent, truth) if s and t)
    noise = sum(1 for t in truth if not t)
    false = sum(1 for s, t in zip(sent, truth) if s and not t)
    near = [False] * len(truth)
    for f, t in enumerate(truth):
        if t:
            for k in range(max(0, f - 100), min(len(truth), f + 101)):
                near[k] = True
    far = sum(1 for n in near if not n)
    stray = sum(1 for s, n in zip(sent, near) if s and not n)
    return (100 * sum(sent) / len(sent), 100 * hit / max(speech, 1), 100 * false / max(noise, 1),
            100 * stray / max(far, 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lib', required=True)
    ap.add_argument('--out', help='prefix for the gated+denoised WAVs (to listen to)')
    ap.add_argument('clips', nargs='+')
    args = ap.parse_args()
    rng = random.Random(1)
    clips = [read_wav(p) for p in args.clips]
    voice, truth = build(clips, rng)
    talk = 100 * sum(truth) / len(truth)
    vpeak = math.sqrt(sum(v * v for v, t in zip(voice[::FRAME], [x for x in truth]) if t) / max(1, sum(truth)))
    print(f'{SECONDS} s, speech {talk:.1f} % of the time')
    print('noise    SNR   | RNNoise gate: tx  speech  false stray | loudness gate: tx  speech  false stray')
    for name, level in (('quiet', 300), ('loud', 1000), ('v.loud', 2500)):
        noise = car_noise(len(voice), level, random.Random(2))
        nrms = math.sqrt(sum(v * v for v in noise[::97]) / len(noise[::97]))
        snr = 20 * math.log10(vpeak / nrms)
        signal = array.array('f', (a + b for a, b in zip(voice, noise)))
        g = rnnoise_gate(args.lib, f'{args.out}_{name}.wav' if args.out else None)
        r = score(run_gate(signal, g), truth)
        l = score(run_gate(signal, loudness_gate), truth)
        print(f'{name:7s} {snr:5.1f}dB |  {r[0]:5.1f}% {r[1]:6.1f}% {r[2]:5.1f}% {r[3]:5.1f}% |'
              f'  {l[0]:5.1f}% {l[1]:6.1f}% {l[2]:5.1f}% {l[3]:5.1f}%'
              f'   (RNNoise {g.cost_us:.0f} us/10ms frame)')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
