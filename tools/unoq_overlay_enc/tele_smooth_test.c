// tele_smooth_test.c：針の補間（tele_smooth.h）の試験（PC・WSL）。手順書5-24
//   ビルド: gcc -O2 -Wall -o tele_smooth_test tele_smooth_test.c -lm
//   実行:   ./tele_smooth_test                 … 試験（作り物の回転数で、通れば最後に OK）
//           ./tele_smooth_test <抜き出し.csv>  … 走行記録（列 mcu_ms,RPM。100Hz）を流し、1コマごとの「本当の値・前の描き方・補間」を標準出力へ
//   本体での流れを真似る：STM32が10msごとにサンプル → EcoCaptureが約50ms（＋0〜15ms）ごとにまとめて受け取り、最後の1つを
//   /api/telemetry に出す（受け取りまで2〜8ms）→ overlay_rec が読む（前は0.1秒ごと、今は0.04秒ごと。読むのに2〜6ms）→ 30コマ/秒で描く。
//   STM32の時計は本体の時計より 1秒に100μs 速く、差は5秒（どちらも本物より大きくして試す）
#include <stdio.h>
#include <stdlib.h>
#include "tele_smooth.h"

static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("NG %s:%d ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

static unsigned rs = 12345;
static double rnd(void) { rs = rs * 1103515245u + 12345u; return ((rs >> 8) & 0xffff) / 65536.0; }

// 作り物の回転数：1000〜7000rpmを行き来し、細かい揺れも乗せる（ttはSTM32の時刻、秒）
static double *rec_t, *rec_v; static int rec_n;
static double signal(double tt) {
    if (rec_n) {  // 記録：直前の行の値（STM32が持っている値は次の行まで変わらない）
        int lo = 0, hi = rec_n - 1;
        if (tt <= rec_t[0]) return rec_v[0];
        while (hi - lo > 1) { int m = (lo + hi) / 2; if (rec_t[m] <= tt) lo = m; else hi = m; }
        return rec_v[lo];
    }
    return 4000 + 3000 * sin(tt * 0.9) + 300 * sin(tt * 7.3);
}

#define DRIFT 1.0001
#define OFF0 5.0
static double mono_of(double tt) { return tt * DRIFT + OFF0; }   // STM32の時刻 → 本体の時計
static double tt_of(double mono) { return (mono - OFF0) / DRIFT; }

struct result { int frames, frozen; double max_jump, max_truth_jump, lag, rms; };

// seconds 秒流し、poll 秒ごとに読み、delay で補間して（delay<0 なら前の描き方：読んだ値のまま）描く
static struct result run(double seconds, double poll, double delay, int dump, double *disp_out) {
    static struct tsm m; tsm_reset(&m);
    double eco_t = 0.05 + OFF0, eco_ready = 0, eco_val = NAN, eco_mcu = NAN;  // EcoCaptureが出している最後のサンプル
    double next_poll = OFF0 + 0.013, held = NAN, last_mcu = NAN;
    struct result r = { 0 };
    const int nf = seconds * 30;
    double *disp = disp_out ? disp_out : malloc(sizeof(double) * nf), *frame_t = malloc(sizeof(double) * nf);
    const double t0 = OFF0 + 1.0;  // 1秒たってから描き始める
    for (int f = 0; f < nf; f++) {
        const double ft = t0 + f / 30.0 + rnd() * 0.004;  // コマの時刻（ばらつき4ms）
        // ft までの、EcoCaptureの受け取りと overlay_rec の読み取りを順に進める
        for (;;) {
            const double t_next = fmin(eco_t, next_poll);
            if (t_next > ft) break;
            if (eco_t <= next_poll) {  // EcoCapture：logger.take。いまSTM32にある最後の10msのサンプル
                const double tt = floor(tt_of(eco_t - 0.002 - rnd() * 0.006) * 100) / 100;
                eco_mcu = round(tt * 1000); eco_val = signal(tt); eco_ready = eco_t;
                eco_t += 0.05 + rnd() * 0.015;
            } else {  // overlay_rec：/api/telemetry を読む
                const double got = next_poll + 0.002 + rnd() * 0.004;
                if (eco_ready > 0) {
                    held = eco_val;
                    if (eco_mcu != last_mcu) { double v = eco_val; tsm_push(&m, eco_mcu / 1000, got, &v, 1); last_mcu = eco_mcu; }
                }
                next_poll += poll;
            }
        }
        double v = held;
        if (delay >= 0) tsm_get(&m, ft, delay, &v, 1);
        disp[f] = v; frame_t[f] = ft;
    }
    // 滑らかさ：本当の値が動いているのに針が止まったコマ、1コマで動いた量の最大
    for (int f = 1; f < nf; f++) {
        const double d = fabs(disp[f] - disp[f - 1]), dt = fabs(signal(tt_of(frame_t[f])) - signal(tt_of(frame_t[f - 1])));
        r.frames++;
        if (d < 1e-9 && dt > 5) r.frozen++;
        if (d > r.max_jump) r.max_jump = d;
        if (dt > r.max_truth_jump) r.max_truth_jump = dt;
    }
    // 遅れ：本当の値をずらして一番よく重なるずれ（0〜300ms、1ms刻み）と、そのときの誤差
    r.rms = 1e18;
    for (int lag = 0; lag <= 300; lag++) {
        double e = 0; int n = 0;
        for (int f = 0; f < nf; f++) if (!isnan(disp[f])) { double x = disp[f] - signal(tt_of(frame_t[f] - lag / 1000.0)); e += x * x; n++; }
        e = sqrt(e / n);
        if (e < r.rms) { r.rms = e; r.lag = lag / 1000.0; }
    }
    if (dump) {
        printf("frame,t,truth,displayed\n");
        for (int f = 0; f < nf; f++) printf("%d,%.4f,%.1f,%.1f\n", f, frame_t[f] - t0, signal(tt_of(frame_t[f])), disp[f]);
    }
    if (!disp_out) free(disp);
    free(frame_t);
    return r;
}

static void unit_tests(void) {
    static struct tsm m; double v, out[2];
    tsm_reset(&m);
    tsm_get(&m, 10, 0.1, out, 1); CHECK(isnan(out[0]), "空ならNAN");
    v = 100; CHECK(tsm_push(&m, 1.00, 11.00, &v, 1) == 1, "1つ目");
    CHECK(tsm_push(&m, 1.00, 11.04, &v, 1) == 0, "同じ時刻は足さない");
    v = 200; tsm_push(&m, 1.05, 11.06, &v, 1);  // 遅れ 10.00・10.01 → 差は10.00
    tsm_get(&m, 11.125, 0.1, out, 1); CHECK(fabs(out[0] - 150) < 1, "真ん中で150: %f", out[0]);
    tsm_get(&m, 12.0, 0.1, out, 1); CHECK(out[0] == 200, "先は新しい値のまま（行き過ぎない）: %f", out[0]);
    tsm_get(&m, 10.0, 0.1, out, 1); CHECK(out[0] == 100, "前は古い値: %f", out[0]);
    tsm_get(&m, 11.125, 0, out, 1); CHECK(out[0] == 200, "delay 0 は届いた値のまま: %f", out[0]);
    // 途切れ：0.5秒より離れていれば補間しない
    v = 1000; tsm_push(&m, 2.05, 12.06, &v, 1);
    tsm_get(&m, 11.40, 0.1, out, 1); CHECK(out[0] == 200, "途切れの前半は前の値: %f", out[0]);
    tsm_get(&m, 11.80, 0.1, out, 1); CHECK(out[0] == 1000, "途切れの後半は後の値: %f", out[0]);
    // 片方が無い（NAN）
    double w[2] = { 5, NAN }; tsm_push(&m, 2.10, 12.11, w, 2);
    double w2[2] = { 7, 9 }; tsm_push(&m, 2.20, 12.21, w2, 2);
    tsm_get(&m, 12.26, 0.1, out, 2);  // tq = 2.16 → 6割の所
    CHECK(fabs(out[0] - 6.2) < 0.1 && out[1] == 9, "NANの側は近い方: %f %f", out[0], out[1]);
    // STM32の再起動（時刻が戻る）：ためたものを捨てる
    v = 42; CHECK(tsm_push(&m, 0.01, 13.0, &v, 1) == 1, "戻った時刻も足す");
    CHECK(m.n == 1 && fabs(m.off - 12.99) < 1e-9, "始め直す: n=%d off=%f", m.n, m.off);
    // 輪：TSM_N より多く足しても新しいものが残る
    tsm_reset(&m);
    for (int i = 0; i < 100; i++) { v = i; tsm_push(&m, i * 0.05, 3 + i * 0.05, &v, 1); }
    CHECK(m.n == TSM_N, "n=%d", m.n);
    tsm_get(&m, 3 + 99 * 0.05 - 0.025 + 0.1, 0.1, out, 1); CHECK(fabs(out[0] - 98.5) < 1e-6, "輪の中の補間: %f", out[0]);
}

int main(int argc, char **argv) {
    if (argc > 1) {  // 走行記録で、1コマごとの値を書き出す
        FILE *f = fopen(argv[1], "r"); if (!f) { perror(argv[1]); return 1; }
        char line[256]; int cap = 1 << 16; rec_t = malloc(sizeof(double) * cap); rec_v = malloc(sizeof(double) * cap);
        if (!fgets(line, sizeof line, f)) return 1;
        while (fgets(line, sizeof line, f)) {
            double t, x; if (sscanf(line, "%lf,%lf", &t, &x) != 2) continue;
            if (rec_n == cap) { cap *= 2; rec_t = realloc(rec_t, sizeof(double) * cap); rec_v = realloc(rec_v, sizeof(double) * cap); }
            rec_t[rec_n] = t / 1000; rec_v[rec_n] = x; rec_n++;
        }
        fclose(f);
        const double t0 = rec_t[0]; for (int i = 0; i < rec_n; i++) rec_t[i] -= t0;
        const double secs = rec_t[rec_n - 1] - 2;
        const int nf = secs * 30;
        double *old = malloc(sizeof(double) * nf), *neu = malloc(sizeof(double) * nf);
        rs = 1; struct result a = run(secs, 0.1, -1, 0, old);
        rs = 1; struct result b = run(secs, 0.04, 0.1, 0, neu);
        printf("frame,t,truth,old,smooth\n");
        for (int i = 0; i < nf; i++) printf("%d,%.4f,%.1f,%.1f,%.1f\n", i, i / 30.0, signal(i / 30.0 + 1.0), old[i], neu[i]);
        fprintf(stderr, "前の描き方: 止まったコマ %d/%d、1コマの最大の動き %.0f、遅れ %.0fms\n", a.frozen, a.frames, a.max_jump, a.lag * 1000);
        fprintf(stderr, "補間:       止まったコマ %d/%d、1コマの最大の動き %.0f、遅れ %.0fms\n", b.frozen, b.frames, b.max_jump, b.lag * 1000);
        return 0;
    }
    unit_tests();
    // 前の描き方（0.1秒ごとに読んで、そのまま描く）
    rs = 7; struct result a = run(600, 0.1, -1, 0, NULL);
    // 補間（0.04秒ごとに読み、0.1秒遅らせて補間）
    rs = 7; struct result b = run(600, 0.04, 0.1, 0, NULL);
    printf("前の描き方: 止まったコマ %d/%d (%.0f%%)、1コマの最大の動き %.0frpm（本当の値は%.0f）、遅れ %.0fms、誤差 %.0frpm\n",
           a.frozen, a.frames, 100.0 * a.frozen / a.frames, a.max_jump, a.max_truth_jump, a.lag * 1000, a.rms);
    printf("補間:       止まったコマ %d/%d (%.0f%%)、1コマの最大の動き %.0frpm（本当の値は%.0f）、遅れ %.0fms、誤差 %.0frpm\n",
           b.frozen, b.frames, 100.0 * b.frozen / b.frames, b.max_jump, b.max_truth_jump, b.lag * 1000, b.rms);
    CHECK(a.frozen > a.frames / 2, "前の描き方は半分以上のコマで止まっていたはず: %d", a.frozen);
    CHECK(b.frozen == 0, "補間で止まるコマは無い: %d", b.frozen);
    CHECK(b.max_jump < a.max_jump / 2, "1コマの動きは半分より小さい: %.0f / %.0f", b.max_jump, a.max_jump);
    CHECK(b.max_jump < b.max_truth_jump * 1.6, "1コマの動きは本当の値の動きと同じくらい: %.0f / %.0f", b.max_jump, b.max_truth_jump);
    CHECK(fabs(b.lag - a.lag) < 0.04, "平均の遅れは前と同じくらい: %.0f / %.0fms", b.lag * 1000, a.lag * 1000);
    CHECK(b.rms < a.rms, "本当の値との誤差は小さくなる: %.0f / %.0f", b.rms, a.rms);
    // 読み取りが遅いとき（10Hzのまま）でも、補間なら止まらない
    rs = 7; struct result c = run(120, 0.1, 0.15, 0, NULL);
    printf("10Hzで読んで補間（delay 0.15）: 止まったコマ %d/%d、最大の動き %.0f、遅れ %.0fms\n", c.frozen, c.frames, c.max_jump, c.lag * 1000);
    CHECK(c.frozen < c.frames / 50, "10Hzでも、ほぼ止まらない: %d", c.frozen);
    if (fails) { printf("%d 件 NG\n", fails); return 1; }
    printf("OK\n");
    return 0;
}
