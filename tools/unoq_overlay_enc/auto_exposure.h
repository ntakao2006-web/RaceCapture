// 録画プログラム（overlay_rec.c）が自分でカメラの露出を決める（手順書5-21）
//   カメラ任せの自動露出は画面全体の平均で明るさを決めるので、下半分の暗い車内に引っぱられ、明るい日の窓の外が白く飛ぶ
//   （2026-11-06の走行で、明るい場面の窓の範囲の7割以上が飛んだ）。そこで窓の範囲（roi）だけを測り、
//   その平均と明るい側（上位hi_pct%の値）が目標に入るように、露出時間とゲインを手動の値としてカメラへ送る。
//   ・露出時間は max_ms（既定30ms）まで。それより暗いときはゲインで補う（夜もコマ数を落とさない。手順書5-13・5-19）
//   ・10ms以上の露出は、蛍光灯・トンネルの照明のちらつき（flicker_hz、東日本は100Hz）の周期の倍数にそろえ、端数はゲインで補う
//   ・変えたら period コマ待ってから測り直す（カメラに効くまで数コマかかる）。1回で変えるのは±1段（2倍）まで
// 設定ファイル（exposure.ini、無ければ既定の値）の書き方は ae_parse の前のコメント。この部品はV4L2を触らない（PCで試験する）
// 試験：gcc -O2 -Wall -o auto_exposure_test auto_exposure_test.c -lm && ./auto_exposure_test
#ifndef AUTO_EXPOSURE_H
#define AUTO_EXPOSURE_H
#include <ctype.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct ae_cfg {
    int own;          // 1：録画プログラムが決める 0：カメラ任せ（前と同じ）
    float roi[4];     // 測る範囲（カメラの絵の左・上・右・下、0〜1）
    float target;     // 範囲の平均の目標（0〜255）
    float hi_pct;     // 明るい側として見る順位（%、95なら明るいほうから5%の所）
    float hi_target;  // その値の上限（これを超えると暗くする）
    float clip;       // 明るい側がこの値以上なら飛んでいるとみなし、必ず暗くする（このカメラの白は240前後で頭打ち。255にはならない）
    float max_ms;     // 露出時間の上限（ms）。33より長いとコマ数が落ちる
    float flicker_hz; // 照明のちらつきの周波数（0は合わせない）
    float gain_stops; // ゲインを最小から最大まで上げたときに明るくなる段数（カメラごとの見込み。外れていても繰り返しで合う）
    int period;       // 測り直すまでのコマ数
};

static void ae_defaults(struct ae_cfg *c) {
    c->own = 1;
    c->roi[0] = .05f; c->roi[1] = .25f; c->roi[2] = .95f; c->roi[3] = .62f;  // ロードスターに付けたときのフロントガラス
    c->target = 115; c->hi_pct = 95; c->hi_target = 225;  // 11/6のトンネル内（よく写っていた）で平均約118・上位5%約218
    c->clip = 236;  // 11/6夜の本体：飛んだ所は239〜242で止まった（250にはならないので、前の「250以上」は一度も効かなかった）
    c->max_ms = 30; c->flicker_hz = 100; c->gain_stops = 3; c->period = 4;
}

// 設定ファイル：1行に「名前 = 値」。#から後ろは注釈。書かなかった名前は既定の値
//   mode = own | camera     own：録画プログラムが決める（既定）、camera：カメラ任せ
//   roi = 0.05 0.25 0.95 0.62   target = 115   hi_pct = 95   hi_target = 225   clip = 236
//   max_ms = 30   flicker_hz = 100   gain_stops = 3   period = 4
// 読めない行・範囲の外の値があれば err に書いて0を返す（そのときcは変えない）
static int ae_parse(struct ae_cfg *out, const char *text, char *err, size_t errn) {
    struct ae_cfg c = *out;
    int line = 0;
    for (const char *p = text; *p;) {
        const char *e = strchr(p, '\n'); size_t n = e ? (size_t)(e - p) : strlen(p);
        char buf[256]; line++;
        if (n >= sizeof buf) { snprintf(err, errn, "%d行目が長すぎる", line); return 0; }
        memcpy(buf, p, n); buf[n] = 0; p += n + (e ? 1 : 0);
        char *h = strchr(buf, '#'); if (h) *h = 0;
        char *q = buf; while (isspace((unsigned char)*q)) q++;
        if (!*q) continue;
        char *eq = strchr(q, '=');
        if (!eq) { snprintf(err, errn, "%d行目に=が無い", line); return 0; }
        *eq = 0; char *k = q, *v = eq + 1;
        for (char *t = eq - 1; t >= k && isspace((unsigned char)*t); t--) *t = 0;
        while (isspace((unsigned char)*v)) v++;
        for (char *t = v + strlen(v) - 1; t >= v && isspace((unsigned char)*t); t--) *t = 0;
        char *end; double x = strtod(v, &end); int num = end != v && !*end;
        if (!strcmp(k, "mode")) {
            if (!strcmp(v, "own")) c.own = 1; else if (!strcmp(v, "camera")) c.own = 0;
            else { snprintf(err, errn, "mode は own か camera（%.40s）", v); return 0; }
        } else if (!strcmp(k, "roi")) {
            float r[4]; if (sscanf(v, "%f %f %f %f", &r[0], &r[1], &r[2], &r[3]) != 4 ||
                            !(r[0] >= 0 && r[1] >= 0 && r[2] <= 1 && r[3] <= 1 && r[2] - r[0] >= .05f && r[3] - r[1] >= .05f)) {
                snprintf(err, errn, "roi は 左 上 右 下（0〜1、幅・高さ0.05以上）（%.40s）", v); return 0;
            }
            memcpy(c.roi, r, sizeof r);
        } else if (!num) { snprintf(err, errn, "%.20s の値が数でない（%.40s）", k, v); return 0;
        } else if (!strcmp(k, "target") && x >= 20 && x <= 230) c.target = x;
        else if (!strcmp(k, "hi_pct") && x >= 50 && x <= 99.9) c.hi_pct = x;
        else if (!strcmp(k, "hi_target") && x >= 100 && x <= 254) c.hi_target = x;
        else if (!strcmp(k, "clip") && x >= 150 && x <= 255) c.clip = x;
        else if (!strcmp(k, "max_ms") && x >= 1 && x <= 200) c.max_ms = x;
        else if (!strcmp(k, "flicker_hz") && (x == 0 || (x >= 50 && x <= 120))) c.flicker_hz = x;
        else if (!strcmp(k, "gain_stops") && x >= .5 && x <= 8) c.gain_stops = x;
        else if (!strcmp(k, "period") && x >= 2 && x <= 30) c.period = (int)x;
        else { snprintf(err, errn, "%.20s = %.40s は知らない名前か範囲の外", k, v); return 0; }
    }
    *out = c;
    return 1;
}

struct ae_stats { float mean, hi; int n; };

// 輝度の面（y、1行 stride バイト、w×h）の roi を8画素おきに見て、平均と上位 hi_pct% の値を出す
static void ae_measure(const uint8_t *y, int stride, int w, int h, const struct ae_cfg *c, struct ae_stats *s) {
    uint32_t hist[256] = {0}; uint64_t sum = 0; int n = 0;
    const int x0 = (int)(c->roi[0] * w), x1 = (int)(c->roi[2] * w), y0 = (int)(c->roi[1] * h), y1 = (int)(c->roi[3] * h);
    for (int j = y0; j < y1; j += 8) {
        const uint8_t *r = y + (size_t)j * stride;
        for (int i = x0; i < x1; i += 8) { hist[r[i]]++; sum += r[i]; n++; }
    }
    s->n = n;
    if (!n) { s->mean = s->hi = 0; return; }
    s->mean = (float)sum / n;
    const uint32_t lim = (uint32_t)(n * (1 - c->hi_pct / 100.0));  // 明るいほうから数えてこの数を超えた所
    uint32_t acc = 0; int v = 255;
    for (; v > 0; v--) { acc += hist[v]; if (acc > lim) break; }
    s->hi = v;
}

// カメラの値の範囲（露出は100µs単位、V4L2の exposure_time_absolute）
struct ae_cam { int exp_min, exp_max, gain_min, gain_max; };

struct ae_state {
    int exp, gain;   // いまカメラへ送ってある値
    double total;    // 露出×ゲインの明るさ（100µs単位の露出に直した値）
    float last_ratio;  // 最後に求めた「何倍明るくしたいか」（状態の表示用）
};

static double ae_gain_factor(const struct ae_cfg *c, const struct ae_cam *k, int gain) {
    if (k->gain_max <= k->gain_min) return 1;
    return pow(2, (double)(gain - k->gain_min) / (k->gain_max - k->gain_min) * c->gain_stops);
}

// 明るさ total を露出時間とゲインに分ける（露出を優先し、上限・ちらつきの周期で切った端数をゲインで補う）
static void ae_split(struct ae_state *st, const struct ae_cfg *c, const struct ae_cam *k, double total) {
    int emax = (int)(c->max_ms * 10); if (emax > k->exp_max) emax = k->exp_max; if (emax < k->exp_min) emax = k->exp_min;
    double e = total < emax ? total : emax;
    if (e < k->exp_min) e = k->exp_min;
    const int q = c->flicker_hz > 0 ? (int)(10000 / c->flicker_hz + .5) : 0;  // ちらつきの周期（100µs単位、100Hzなら100）
    int ei = (int)(e + .5);
    if (q && ei >= q && emax >= q) ei = ei / q * q;  // 周期の倍数へ切り下げ（上限も周期の倍数より短くはしない）
    if (ei < k->exp_min) ei = k->exp_min;
    double gf = total / ei; if (gf < 1) gf = 1;
    int g = k->gain_min;
    if (k->gain_max > k->gain_min) {
        g = k->gain_min + (int)lround(log2(gf) / c->gain_stops * (k->gain_max - k->gain_min));
        if (g > k->gain_max) g = k->gain_max;
        if (g < k->gain_min) g = k->gain_min;
    }
    st->exp = ei; st->gain = g;
    st->total = ei * ae_gain_factor(c, k, g);
}

static void ae_init(struct ae_state *st, const struct ae_cfg *c, const struct ae_cam *k, int exp) {
    memset(st, 0, sizeof *st);
    ae_split(st, c, k, exp > 0 ? exp : 100);
}

// 測った値から次の露出・ゲインを決める。変えたら1
static int ae_update(struct ae_state *st, const struct ae_cfg *c, const struct ae_cam *k, const struct ae_stats *s) {
    if (s->n < 16) return 0;
    double r = c->target / (s->mean > 1 ? s->mean : 1);
    const double rh = c->hi_target / (s->hi > 1 ? s->hi : 1);
    if (rh < r) r = rh;
    double l = log2(r);
    if (s->hi >= c->clip && l > -.25) l = -.25;  // 明るい側が飛んでいるあいだは必ず暗くする（飛ぶと値が頭打ちになり、比だけでは暗くし足りない）
    st->last_ratio = (float)pow(2, l);
    if (fabs(l) < .12) return 0;  // 約8%以内なら変えない（行ったり来たりしないように）
    l *= .7;  // カメラの遅れ・飛んだ値の見誤りで行き過ぎないように控えめに
    if (l > 1) l = 1;
    if (l < -1) l = -1;
    double emax = c->max_ms * 10; if (emax > k->exp_max) emax = k->exp_max;
    const double tmax = emax * ae_gain_factor(c, k, k->gain_max), tmin = k->exp_min;
    double t = st->total * pow(2, l);
    if (t > tmax) t = tmax;
    if (t < tmin) t = tmin;
    const int pe = st->exp, pg = st->gain;
    ae_split(st, c, k, t);
    if (st->exp == pe && st->gain == pg) {  // 露出が短い（数目盛り）と丸めで変わらないので、1目盛りずつ動かす
        int ex = pe, g = pg;
        if (l < 0) { if (g > k->gain_min) g--; else if (ex > k->exp_min) ex--; }
        else { if (ex < emax) ex++; else if (g < k->gain_max) g++; }
        st->exp = ex; st->gain = g; st->total = ex * ae_gain_factor(c, k, g);
    }
    return st->exp != pe || st->gain != pg;
}
#endif
