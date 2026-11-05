"""音の混ぜ方の試験用（audio_mux_test.c）：マイクの代わりに、S16_LE・48kHz・モノラルの生PCMを実時間で標準出力へ出す。
CLOCK_MONOTONIC の毎秒の頭から0.1秒だけ1kHzのピッを鳴らす（ほかは小さな雑音）。出した時刻＝そのサンプルの時刻とする。
録画の音の時刻の付け方が合っていれば、出来た .ts の中のピッの頭のPTSは、映像の最初の枚の時刻（t0）からの毎秒の頭に来る。
"""
import math
import os
import random
import struct
import sys
import time

RATE, CHUNK = 48000, 480  # 10msずつ
out = sys.stdout.buffer
stop_after = float(os.environ.get('BEEP_STOP_AFTER', 'inf'))  # この秒数で終わる（マイクが抜けたときの試験）
start = time.monotonic()
i = 0
try:
    while i < stop_after * RATE:
        due = start + i / RATE
        d = due - time.monotonic()
        if d > 0:
            time.sleep(d)
        buf = bytearray()
        for k in range(CHUNK):
            t = start + (i + k) / RATE
            v = 12000 * math.sin(2 * math.pi * 1000 * t) if t % 1.0 < 0.1 else random.uniform(-200, 200)
            buf += struct.pack('<h', int(v))
        out.write(buf)
        out.flush()
        i += CHUNK
except (BrokenPipeError, KeyboardInterrupt):
    pass
