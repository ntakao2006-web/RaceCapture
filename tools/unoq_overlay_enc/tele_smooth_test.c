// tele_smooth_test.c：針の補間（tele_smooth.h）の試験（PC・WSL）。手順書5-24
//   ビルド: gcc -O2 -Wall -o tele_smooth_test tele_smooth_test.c -lm
//   実行:   ./tele_smooth_test                 … 試験（作り物の回転数で、通れば最後に OK）
//           ./tele_smooth_test <抜き出し.csv>  … 走行記録（列 mcu_ms,RPM。100Hz）を流し、1コマごとの「景色の時刻の本当の値・前の描き方・補間」を標準出力へ
//   本体での流れを真似る：STM32が10msごとにサンプル → EcoCaptureが約50ms（＋0〜15ms）ごとにまとめて受け取り、最後の1つを
//   /api/telemetry に出す（受け取りまで2〜8ms）→ overlay_rec が読む（前は0.1秒ごと、今は0.04秒ごと。読むのに2〜6ms）→ 30コマ/秒で描く。
//   カメラの絵は、描く時刻より「カメラの遅れ」だけ前に撮られている（本体では未測定なので、いくつかの値で試す）。
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
static double tt_of(double mono) { return (mono - OFF0) / DRIFT; }  // 本体の時計 → STM32の時刻

struct result { int frames, frozen; double max_jump, max_truth_jump, lag, rms, behind; };

// seconds 秒流し、poll 秒ごとに読み、dmax（待つ秒の上限）で補間して描く。dmax<0 なら前の描き方（読んだ値のまま）。
// cam_lat：カメラの遅れ（描く時刻 − 撮った時刻）。lag は「景色（撮った時刻）より針が何秒遅れているか」（負なら針が先）
static struct result run(double seconds, double poll, double dmax, double cam_lat, double *disp_out) {
    static struct tsm m; tsm_reset(&m);
    double eco_t = 0.05 + OFF0, eco_ready = 0, eco_val = NAN, eco_mcu = NAN;  // EcoCaptureが出している最後のサンプル
    double next_poll = OFF0 + 0.013, held = NAN, last_mcu = NAN;
    struct result r = { 0 };
    const int nf = seconds * 30;
    double *disp = disp_out ? disp_out : malloc(sizeof(double) * nf), *cam_t = malloc(sizeof(double) * nf);
    const double t0 = OFF0 + 1.0;  // 1秒たってから描き始める
    for (int f = 0; f < nf; f++) {
        const double ft = t0 + f / 30.0 + rnd() * 0.004;  // 描く時刻（ばらつき4ms）
        const double cam = ft - cam_lat - rnd() * 0.004;  // その絵を撮った時刻
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
        if (dmax >= 0) { tsm_frame(&m, cam, ft, dmax, &v, 1); r.behind += m.behind; }
        disp[f] = v; cam_t[f] = cam;
    }
    r.behind /= nf;
    // 滑らかさ：本当の値が動いているのに針が止まったコマ、1コマで動いた量の最大
    for (int f = 1; f < nf; f++) {
        const double d = fabs(disp[f] - disp[f - 1]), dt = fabs(signal(tt_of(cam_t[f])) - signal(tt_of(cam_t[f - 1])));
        r.frames++;
        if (d < 1e-9 && dt > 5) r.frozen++;
        if (d > r.max_jump) r.max_jump = d;
        if (dt > r.max_truth_jump) r.max_truth_jump = dt;
    }
    // 遅れ：景色の時刻の本当の値をずらして一番よく重なるずれ（−200〜300ms、1ms刻み）と、そのときの誤差
    r.rms = 1e18;
    for (int lag = -200; lag <= 300; lag++) {
        double e = 0; int n = 0;
        for (int f = 0; f < nf; f++) if (!isnan(disp[f])) { double x = disp[f] - signal(tt_of(cam_t[f] - lag / 1000.0)); e += x * x; n++; }
        e = sqrt(e / n);
        if (e < r.rms) { r.rms = e; r.lag = lag / 1000.0; }
    }
    if (!disp_out) free(disp);
    free(cam_t);
    return r;
}

static void unit_tests(void) {
    static struct tsm m; double v, out[2];
    tsm_reset(&m);
    tsm_frame(&m, 10, 10, 0.15, out, 1); CHECK(isnan(out[0]), "空ならNAN");
    v = 100; CHECK(tsm_push(&m, 1.00, 11.00, &v, 1) == 1, "1つ目");
    CHECK(tsm_push(&m, 1.00, 11.04, &v, 1) == 0, "同じ時刻は足さない");
    v = 200; tsm_push(&m, 1.05, 11.06, &v, 1);  // 遅れ 10.00・10.01 → 時計の差は約10.00
    tsm_value(&m, 1.025, out, 1); CHECK(fabs(out[0] - 150) < 1e-6, "真ん中で150: %f", out[0]);
    tsm_value(&m, 2.0, out, 1); CHECK(out[0] == 200, "先は新しい値のまま（行き過ぎない）: %f", out[0]);
    tsm_value(&m, 0.5, out, 1); CHECK(out[0] == 100, "前は古い値: %f", out[0]);
    // 撮った時刻の値が届いていれば、その時刻の値（針は景色より遅れない）
    tsm_frame(&m, 11.025, 11.07, 0.15, out, 1);
    CHECK(fabs(out[0] - 150) < 1 && m.behind == 0, "撮った時刻の値: %f behind %f", out[0], m.behind);
    // 撮った時刻の値がまだ無ければ、「今 − 待つ秒」まで戻す（行き過ぎない）
    tsm_frame(&m, 11.07, 11.08, 0.15, out, 1);  // 待つ秒は 11.08−10.00−1.05＝0.03 → 11.08−0.035
    CHECK(fabs(m.wait - 0.03) < 1e-3 && fabs(m.behind - 0.025) < 1e-3, "待つ: wait %f behind %f", m.wait, m.behind);
    CHECK(out[0] > 150 && out[0] < 200, "途中の値: %f", out[0]);
    // 待つ秒は上限で止まり、ゆっくり縮む
    tsm_frame(&m, 12.0, 13.0, 0.15, out, 1); CHECK(fabs(m.wait - 0.15) < 1e-9, "上限: %f", m.wait);
    v = 300; tsm_push(&m, 2.00, 13.005, &v, 1);
    tsm_frame(&m, 13.0, 15.0, 0.15, out, 1);  // 2秒後でも値が来ていない → 上限のまま
    v = 400; tsm_push(&m, 4.00, 15.005, &v, 1);
    tsm_frame(&m, 14.9, 15.01, 0.15, out, 1); CHECK(fabs(m.wait - 0.15) < 1e-3, "来た直後: %f", m.wait);
    tsm_frame(&m, 14.9, 16.01, 0.15, out, 1); CHECK(fabs(m.wait - 0.15) < 1e-3, "来ないまま1秒は上限: %f", m.wait);
    // 上限0は前の描き方（いちばん新しい値）
    tsm_frame(&m, 11.0, 16.0, 0, out, 1); CHECK(out[0] == 400 && m.behind == 0, "上限0: %f", out[0]);
    // 途切れ：0.5秒より離れていれば補間しない（2.00→4.00）
    tsm_value(&m, 2.9, out, 1); CHECK(out[0] == 300, "途切れの前半は前の値: %f", out[0]);
    tsm_value(&m, 3.1, out, 1); CHECK(out[0] == 400, "途切れの後半は後の値: %f", out[0]);
    // 片方が無い（NAN）
    double w[2] = { 5, NAN }; tsm_push(&m, 4.10, 15.11, w, 2);
    double w2[2] = { 7, 9 }; tsm_push(&m, 4.20, 15.21, w2, 2);
    tsm_value(&m, 4.16, out, 2);
    CHECK(fabs(out[0] - 6.2) < 1e-6 && out[1] == 9, "NANの側は近い方: %f %f", out[0], out[1]);
    // STM32の再起動（時刻が戻る）：ためたものを捨てる
    v = 42; CHECK(tsm_push(&m, 0.01, 16.0, &v, 1) == 1, "戻った時刻も足す");
    CHECK(m.n == 1 && fabs(m.off - 15.99) < 1e-9 && m.wait == 0, "始め直す: n=%d off=%f wait=%f", m.n, m.off, m.wait);
    // 輪：TSM_N より多く足しても新しいものが残る
    tsm_reset(&m);
    for (int i = 0; i < 100; i++) { v = i; tsm_push(&m, i * 0.05, 3 + i * 0.05, &v, 1); }
    CHECK(m.n == TSM_N, "n=%d", m.n);
    tsm_value(&m, 98.5 * 0.05, out, 1); CHECK(fabs(out[0] - 98.5) < 1e-6, "輪の中の補間: %f", out[0]);
}

static void show(const char *name, struct result r) {
    printf("  %-22s 止まったコマ %5d/%d (%2.0f%%)、1コマの最大の動き %4.0frpm（本当の値は%3.0f）、針が景色より %+4.0fms、誤差 %3.0frpm\n",
           name, r.frozen, r.frames, 100.0 * r.frozen / r.frames, r.max_jump, r.max_truth_jump, r.lag * 1000, r.rms);
}

int main(int argc, char **argv) {
    if (argc > 1) {  // 走行記録で、1コマごとの値を書き出す（カメラの遅れ60ms）
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
        const double secs = rec_t[rec_n - 1] - 2, lat = 0.06;
        const int nf = secs * 30;
        double *old = malloc(sizeof(double) * nf), *neu = malloc(sizeof(double) * nf);
        rs = 1; struct result a = run(secs, 0.1, -1, lat, old);
        rs = 1; struct result b = run(secs, 0.04, 0.15, lat, neu);
        printf("frame,t,truth_at_camera,old,smooth\n");
        for (int i = 0; i < nf; i++) printf("%d,%.4f,%.1f,%.1f,%.1f\n", i, i / 30.0, signal(tt_of(OFF0 + 1.0 + i / 30.0 - lat)), old[i], neu[i]);
        fprintf(stderr, "前の描き方: 止まったコマ %d/%d、1コマの最大の動き %.0f、針が景色より %+.0fms\n", a.frozen, a.frames, a.max_jump, a.lag * 1000);
        fprintf(stderr, "補間:       止まったコマ %d/%d、1コマの最大の動き %.0f、針が景色より %+.0fms\n", b.frozen, b.frames, b.max_jump, b.lag * 1000);
        return 0;
    }
    unit_tests();
    const double lats[] = { 0.02, 0.06, 0.10, 0.15 };
    for (int i = 0; i < 4; i++) {
        printf("カメラの遅れ %.0fms：\n", lats[i] * 1000);
        rs = 7; struct result a = run(300, 0.1, -1, lats[i], NULL);    // 前：0.1秒ごとに読んで、そのまま描く
        rs = 7; struct result b = run(300, 0.04, 0.15, lats[i], NULL); // 今：0.04秒ごとに読み、撮った時刻で補間
        show("前（10Hz・そのまま）", a);
        show("今（25Hz・撮った時刻）", b);
        printf("  （今の針が待ちのために景色より遅れた平均 %.0fms）\n", b.behind * 1000);
        // 止まるのは、値がいつもより遅れて届いた間だけ（先を当て推量しないので、その間は届いている所で待つ）
        CHECK(b.frozen < b.frames / 500, "補間で止まるコマはほぼ無い: %d", b.frozen);
        CHECK(b.max_jump < b.max_truth_jump * 1.6, "1コマの動きは本当の値の動きと同じくらい: %.0f / %.0f", b.max_jump, b.max_truth_jump);
        // カメラの遅れが短いと、値が届くのを待つ分だけ針が遅れる（前より遅れはしない）。前はカメラの遅れが長いと針が景色より先に出ていた
        if (lats[i] < 0.10) CHECK(b.lag <= a.lag + 0.002, "前より遅れない: %.0f / %.0fms", b.lag * 1000, a.lag * 1000);
        CHECK(b.rms < a.rms, "本当の値との誤差は小さくなる: %.0f / %.0f", b.rms, a.rms);
        if (lats[i] >= 0.10) CHECK(fabs(b.lag) < 0.015, "カメラの遅れが待つ秒より長ければ、景色とほぼ揃う: %.0fms", b.lag * 1000);
        if (i == 1) CHECK(a.frozen > a.frames / 2, "前の描き方は半分以上のコマで止まっていたはず: %d", a.frozen);
    }
    // 読み取りが遅いとき（10Hzのまま）でも、補間なら止まらない
    rs = 7; struct result c = run(120, 0.1, 0.2, 0.06, NULL);
    printf("10Hzで読んで補間（上限0.2秒）：止まったコマ %d/%d、最大の動き %.0f、針が景色より %+.0fms\n", c.frozen, c.frames, c.max_jump, c.lag * 1000);
    CHECK(c.frozen < c.frames / 200, "10Hzでも、ほぼ止まらない: %d", c.frozen);
    if (fails) { printf("%d 件 NG\n", fails); return 1; }
    printf("OK\n");
    return 0;
}
