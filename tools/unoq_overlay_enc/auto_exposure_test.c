// auto_exposure.h の試験。カメラの模型（露出・ゲインが2コマ遅れて効く、明るさはガンマ2.2、白=255か、本物と同じ240で頭打ち）を相手に、
// 明るい日・もっと明るい日・トンネルの出入り・夜で、収まるまでの速さ・行ったり来たりしないこと・白飛びの量を見る
// ビルド・実行（WSLか本体）: gcc -O2 -Wall -o auto_exposure_test auto_exposure_test.c -lm && ./auto_exposure_test
#include "auto_exposure.h"

static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("NG: "); printf(__VA_ARGS__); printf("\n"); } } while (0)

#define IW 1280
#define IH 720
static uint8_t img[IW * IH];
static float scene[IW * IH];  // 窓の範囲の明るさの分布（道=1、空=6、ミラー=0.15、白い車=4）

static void make_scene(void) {
    unsigned s = 12345;
    for (int i = 0; i < IW * IH; i++) {
        s = s * 1103515245 + 12345; int r = (s >> 16) % 100;
        scene[i] = r < 60 ? 1.f : r < 80 ? 6.f : r < 95 ? .15f : 4.f;
    }
}

// 明るさ S の景色を、明るさ total（100µs単位の露出×ゲイン）で写した絵
static double white = 255;  // カメラの白（本物のELPは240前後で頭打ち）
static void shoot(double S, double total) {
    for (int i = 0; i < IW * IH; i++) {
        double lin = scene[i] * S * total * .018;  // 道（1）が total=10（1ms）のとき0.18 → 117
        double v = white * pow(lin > 1 ? 1 : lin, 1 / 2.2);
        img[i] = (uint8_t)(v > 255 ? 255 : v);
    }
}

struct run { int changes_last60, frames_to_settle; float mean, hi, clip; int exp, gain; };

// 明るさSの景色をframes枚写す。st は前の場面から続ける
static struct run run_scene(struct ae_state *st, const struct ae_cfg *c, const struct ae_cam *k, double S, int frames) {
    struct run R = {0}; R.frames_to_settle = -1;
    double applied[3]; for (int i = 0; i < 3; i++) applied[i] = st->total;  // カメラに効いている値（2コマ遅れ）
    int last_change = 0;
    for (int f = 0; f < frames; f++) {
        shoot(S, applied[0]);
        applied[0] = applied[1]; applied[1] = applied[2]; applied[2] = st->total;
        if (f % c->period == 0) {
            struct ae_stats s; ae_measure(img, IW, IW, IH, c, &s);
            if (ae_update(st, c, k, &s)) { last_change = f; if (f >= frames - 60) R.changes_last60++; }
            R.mean = s.mean; R.hi = s.hi;
        }
        CHECK(st->exp <= c->max_ms * 10 && st->exp >= k->exp_min, "露出 %d が範囲の外", st->exp);
        if (c->flicker_hz > 0 && st->exp >= 100) CHECK(st->exp % 100 == 0, "露出 %d が10msの倍数でない", st->exp);
    }
    R.frames_to_settle = last_change;
    int clip = 0, n = 0;
    for (int j = (int)(c->roi[1] * IH); j < (int)(c->roi[3] * IH); j++)
        for (int i = (int)(c->roi[0] * IW); i < (int)(c->roi[2] * IW); i++) { clip += img[j * IW + i] >= white - 2; n++; }
    R.clip = 100.f * clip / n; R.exp = st->exp; R.gain = st->gain;
    return R;
}

static void show(const char *name, struct run R) {
    printf("%-28s 露出=%5.1fms ゲイン=%3d 平均=%5.1f 上位5%%=%5.1f 白飛び=%4.1f%% 最後に変えたコマ=%d 終わり60コマの変更=%d\n",
           name, R.exp / 10.0, R.gain, R.mean, R.hi, R.clip, R.frames_to_settle, R.changes_last60);
}

static void sequence(const struct ae_cfg *cp, const struct ae_cam *kp) {
    const struct ae_cfg c = *cp; const struct ae_cam k = *kp;
    printf("-- カメラの白=%.0f\n", white);
    struct ae_state st; ae_init(&st, &c, &k, 300);  // 始めは30ms（屋内の明るさ）
    struct run R;
    R = run_scene(&st, &c, &k, 1, 150); show("明るい日（道に1ms）", R);
    CHECK(R.frames_to_settle >= 0 && R.frames_to_settle < 60, "明るい日に収まるのが遅い（%dコマ目）", R.frames_to_settle);
    CHECK(R.changes_last60 == 0, "明るい日に行ったり来たり（%d回）", R.changes_last60);
    CHECK(R.clip < 6, "明るい日の白飛び %.1f%%", R.clip);
    CHECK(R.mean > 80 && R.mean < 140, "明るい日の平均 %.1f", R.mean);
    R = run_scene(&st, &c, &k, 4, 150); show("とても明るい日（×4）", R);
    CHECK(R.frames_to_settle < 60 && R.changes_last60 == 0 && R.clip < 6, "とても明るい日");
    R = run_scene(&st, &c, &k, 1 / 40.0, 150); show("トンネル（÷40）", R);
    CHECK(R.frames_to_settle < 90 && R.changes_last60 == 0, "トンネルで収まらない");
    CHECK(R.exp == 300 || R.exp % 100 == 0, "トンネルの露出 %d", R.exp);
    CHECK(R.mean > 80 && R.mean < 140, "トンネルの平均 %.1f", R.mean);
    R = run_scene(&st, &c, &k, 1, 150); show("トンネルの出口（×40）", R);
    CHECK(R.frames_to_settle < 60 && R.changes_last60 == 0 && R.clip < 6, "トンネルの出口");
    R = run_scene(&st, &c, &k, 1 / 2000.0, 150); show("夜（÷2000、足りなくて暗い）", R);
    CHECK(R.exp == 300 && R.gain == 100, "夜は露出30ms・ゲイン最大のはず（%d・%d）", R.exp, R.gain);

}

int main(void) {
    make_scene();
    struct ae_cfg c; ae_defaults(&c);
    const struct ae_cam k = { 1, 5000, 0, 100 };

    // ---- 測り方：決まった絵で平均と上位の値
    memset(img, 100, sizeof img);
    for (int j = 0; j < IH; j++) for (int i = 0; i < IW; i++) if ((i / 8 + j / 8) % 10 == 0) img[j * IW + i] = 250;  // 1割を250
    struct ae_stats s; ae_measure(img, IW, IW, IH, &c, &s);
    CHECK(s.n > 4000, "測った点が少ない %d", s.n);
    CHECK(fabsf(s.mean - 115) < 2, "平均 %.1f（115のはず）", s.mean);
    CHECK(s.hi == 250, "上位5%%の値 %.0f（250のはず）", s.hi);

    // ---- 場面の続き：屋内から出て、明るい日→とても明るい日→トンネル→出口→夜（白=255と、本物と同じ240）
    white = 255; sequence(&c, &k);
    white = 240; sequence(&c, &k);

    struct ae_state st; struct run R;
    // ---- ゲインが無いカメラ、ちらつき合わせ無し
    struct ae_cam k2 = { 1, 5000, 0, 0 }; struct ae_cfg c2 = c; c2.flicker_hz = 0;
    ae_init(&st, &c2, &k2, 50);
    R = run_scene(&st, &c2, &k2, 1 / 10.0, 150); show("ゲイン無し・暗め（÷10）", R);
    CHECK(R.changes_last60 == 0 && R.gain == 0 && R.mean > 80 && R.mean < 140, "ゲイン無し");

    // ---- 設定ファイル
    struct ae_cfg p; ae_defaults(&p); char err[128];
    CHECK(ae_parse(&p, "# 注釈\nmode = camera\nroi = 0.1 0.2 0.9 0.6  # 窓\r\ntarget=100\n\nmax_ms = 20\n", err, sizeof err), "読めない：%s", err);
    CHECK(!p.own && p.roi[0] == .1f && p.roi[3] == .6f && p.target == 100 && p.max_ms == 20 && p.hi_target == 225, "読んだ値が違う");
    struct ae_cfg q = p;
    CHECK(!ae_parse(&q, "target = 300\n", err, sizeof err) && q.target == 100, "範囲の外を受け付けた");
    CHECK(!ae_parse(&q, "speed = 1\n", err, sizeof err), "知らない名前を受け付けた");
    CHECK(!ae_parse(&q, "roi = 0.5 0.5 0.4 0.9\n", err, sizeof err), "逆さのroiを受け付けた");
    CHECK(!ae_parse(&q, "mode = auto\n", err, sizeof err), "mode=autoを受け付けた");

    printf(fails ? "NG %d件\n" : "全部OK\n", fails);
    return fails != 0;
}
