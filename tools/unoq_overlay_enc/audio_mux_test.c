// 音の混ぜ方（audio_cap.h・ts_mux.h）の試験。カメラ・GPU・エンコーダ無しで、PC（WSL等）でも動く
//   録った .ts の映像を、録ったときと同じ速さで録画プログラムと同じ書き方で書き直し、そこへ音（OVERLAY_AUDIO_CMD の出す生PCM）を混ぜる。
//   音は録画プログラムと同じく別スレッドで読み、映像の1枚ごとにたまった分を書く。映像の最初の枚の「カメラの時刻」は書き始めた時刻とする
// ビルド: gcc -O2 -o audio_mux_test audio_mux_test.c -lm -lpthread -ldl（実行には libtwolame.so.0 が要る）
// 実行:   OVERLAY_AUDIO_CMD='python3 audio_beep.py' ./audio_mux_test <入力.ts> <出力.ts> [秒=20]
//   最後に「t0=<映像の最初の枚のCLOCK_MONOTONIC>」を出す。audio_mux_check.py が、ピッ（audio_beep.py が CLOCK_MONOTONIC の毎秒の頭に鳴らす）の
//   位置から、音の時刻が合っているかを見る
#define _GNU_SOURCE
#include <math.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "ts_mux.h"
static volatile sig_atomic_t quit;
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
#include "audio_cap.h"

static double rec_cam_t0;
static void ac_write(const uint8_t *es, size_t n, double t) { ts_audio_pes(es, n, (uint64_t)llround((t - rec_cam_t0) * 90000) + 45000); }

static uint8_t pes[4 << 20];
static size_t pes_n;
static int pes_key, frames;
static double t_end, latency = 0.06;  // エンコーダから出てくるまでの遅れ（本体で約2コマ）
static int64_t pts0 = -1;

static void flush_pes(void) {
    if (pes_n < 14 || pes[0] || pes[1] || pes[2] != 1 || !(pes[7] & 0x80)) { pes_n = 0; return; }
    const uint8_t *b = pes + 9;
    int64_t pts = (int64_t)(b[0] >> 1 & 7) << 30 | b[1] << 22 | (b[2] >> 1) << 15 | b[3] << 7 | b[4] >> 1;
    size_t h = 9 + pes[8];
    const uint8_t *es = pes + h; size_t n = pes_n - h;
    if (n >= 6 && !memcmp(es, "\0\0\0\1\x09", 5)) { es += 6; n -= 6; }  // 録画が付けたAUDは ts_frame がまた付ける
    if (pts0 < 0) { pts0 = pts; rec_cam_t0 = now(); }
    const double cam = rec_cam_t0 + (pts - pts0) / 90000.0;  // この枚のカメラの時刻
    while (now() < cam + latency) usleep(1000);
    if (pes_key) ts_tables();
    if (ts_audio) ac_drain(rec_cam_t0, 0, ac_write);
    const uint64_t t90 = (uint64_t)(pts - pts0);
    ts_frame(es, n, t90 + 45000, t90, pes_key);
    frames++; pes_n = 0;
    if (now() > t_end) quit = 1;
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s in.ts out.ts [seconds]\n", argv[0]); return 2; }
    FILE *in = fopen(argv[1], "rb"); out = fopen(argv[2], "wb");
    if (!in || !out) { perror("open"); return 1; }
    ts_audio = ac_start();
    if (!ts_audio) { fprintf(stderr, "audio did not start (OVERLAY_AUDIO_CMD?)\n"); return 1; }
    t_end = now() + (argc > 3 ? atof(argv[3]) : 20);
    uint8_t pk[188];
    while (!quit && fread(pk, 1, 188, in) == 188) {
        if (pk[0] != 0x47 || ((pk[1] & 0x1f) << 8 | pk[2]) != PID_VID || !(pk[3] & 0x10)) continue;
        size_t o = 4; int key = 0;
        if (pk[3] & 0x20) { if (pk[4] && (pk[5] & 0x40)) key = 1; o += 1 + pk[4]; }
        if (o >= 188) continue;
        if (pk[1] & 0x40) { if (pes_n) flush_pes(); pes_key = key; }
        if (pes_n + 188 - o <= sizeof pes) { memcpy(pes + pes_n, pk + o, 188 - o); pes_n += 188 - o; }
    }
    if (!quit && pes_n) flush_pes();
    quit = 1;
    ac_stop();
    ac_drain(rec_cam_t0, 1, ac_write);
    fclose(out);
    printf("frames=%d audio_frames=%ld written=%ld dropped=%ld restarts=%ld bytes=%zu\n", frames, ac_frames, ac_written, ac_dropped, ac_restarts, bytes);
    printf("t0=%.6f\n", rec_cam_t0);
    return 0;
}
