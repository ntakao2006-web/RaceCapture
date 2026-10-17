/* ドライバーの声の無音判定をUNO Qで実時間に回す試験（ER-10-9）。
 *
 * arecord の生PCM（S16_LE・48kHz・モノラル）を標準入力で受け、10msごとに
 * RNNoise（v0.1.1）で「声らしさ」を出し、voice_gate.py の VoiceGate と同じ規則
 * （2フレーム連続で0.6以上で開く・前100msを付ける・400ms途切れたら閉じる）で判定する。
 * 1秒ごとに、処理時間（平均・最大）、声らしさの最大、開いていた割合を標準エラーへ出す。
 * 第1引数を渡すと、送る（ゲートが開いている）区間だけの雑音除去後の音を生PCMで書き出す。
 *
 *   gcc -O2 -I$RN/include voice_gate_live.c $RN/src/{denoise,rnn,rnn_data,pitch,kiss_fft,celt_lpc}.c -lm -o voice_gate_live
 *   arecord -D plughw:CARD=Pro,DEV=0 -f S16_LE -r 48000 -c 1 -t raw | ./voice_gate_live sent.raw
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "rnnoise.h"

#define FRAME 480
#define OPEN_PROB 0.6f
#define MIN_FRAMES 2
#define HOLD_FRAMES 40
#define PREROLL 10

static double now_ms(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1e3 + t.tv_nsec / 1e6;
}

static void write_frame(FILE *f, const float *x)
{
    short s[FRAME];
    for (int i = 0; i < FRAME; i++) {
        float v = x[i];
        s[i] = v > 32767 ? 32767 : v < -32768 ? -32768 : (short)v;
    }
    fwrite(s, sizeof s, 1, f);
}

int main(int argc, char **argv)
{
    FILE *out = argc > 1 ? fopen(argv[1], "wb") : NULL;
    DenoiseState *st = rnnoise_create(NULL);
    short pcm[FRAME];
    float in[FRAME], clean[FRAME], pre[PREROLL][FRAME];
    int npre = 0, talking = 0, run = 0, quiet = 0;
    long frames = 0, open_total = 0, opens = 0;
    double sum_ms = 0, max_ms = 0, all_max_ms = 0, all_sum_ms = 0;
    float max_prob = 0;
    int open_sec = 0;

    while (fread(pcm, sizeof pcm, 1, stdin) == 1) {
        for (int i = 0; i < FRAME; i++) in[i] = pcm[i];
        double t0 = now_ms();
        float prob = rnnoise_process_frame(st, clean, in);
        double dt = now_ms() - t0;
        sum_ms += dt;
        all_sum_ms += dt;
        if (dt > max_ms) max_ms = dt;
        if (dt > all_max_ms) all_max_ms = dt;
        if (prob > max_prob) max_prob = prob;

        run = prob >= OPEN_PROB ? run + 1 : 0;
        if (!talking) {
            if (npre == PREROLL) { memmove(pre[0], pre[1], sizeof(pre[0]) * (PREROLL - 1)); npre--; }
            memcpy(pre[npre++], clean, sizeof clean);
            if (run >= MIN_FRAMES) {
                talking = 1; quiet = 0; opens++;
                if (out) for (int i = 0; i < npre; i++) write_frame(out, pre[i]);
                npre = 0;
            }
        } else {
            quiet = prob >= OPEN_PROB ? 0 : quiet + 1;
            if (quiet > HOLD_FRAMES) talking = 0;
            else if (out) write_frame(out, clean);
        }
        if (talking) { open_total++; open_sec++; }

        if (++frames % 100 == 0) {
            fprintf(stderr, "t=%3lds  処理 平均%.2fms 最大%.2fms  声らしさ最大%.2f  開%3d%%%s\n",
                    frames / 100, sum_ms / 100, max_ms, max_prob, open_sec, talking ? "  ●送信中" : "");
            sum_ms = max_ms = 0; max_prob = 0; open_sec = 0;
        }
    }
    if (frames)
        fprintf(stderr, "合計 %.1fs  処理 平均%.3fms（10msに対し%.1f%%） 最大%.2fms  開いた回数%ld  送った時間%.1f%%\n",
                frames / 100.0, all_sum_ms / frames, all_sum_ms / frames * 10, all_max_ms, opens,
                100.0 * open_total / frames);
    rnnoise_destroy(st);
    if (out) fclose(out);
    return 0;
}
