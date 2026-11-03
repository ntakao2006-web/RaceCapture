// lap_ref.h：ベストラップとの差（デルタ）と、コース図の線を走行データから作る（GLを使わない部分）
//   overlay_rec.c が走行データ（EcoCaptureの /api/telemetry、約10Hz）を読むたびに lr_update を呼ぶ。
//   各周の軌跡（緯度・経度・その周の経過秒・速度）をため、周が終わってその周がベスト（lap.BestLap と同じ時間）なら、
//   その軌跡を「ベストの周」として持つ。走行中は、今の位置に一番近いベストの周の線の上の点を探し（前回の近くから先へ探す）、
//     差 ＝ 今の周の経過秒 − ベストの周でそこを通った経過秒（マイナスならベストより速い）
//   とする。速度の差も同じ点で比べる。予想ラップ ＝ ベスト ＋ 差。
//   ベストの周はファイル（OVERLAY_LAPREF）にも書き、録画をやり直しても lap.BestLap と同じ時間ならそのまま使う。
//   違えば（ラップのリセット後など）差には使わず、新しいベストが出たら置き換える。
//   コース図の線は、ベストの周（ファイルから読んだものは、今の位置が近いときだけ）→ 最後に終わった周 → 今の周（ここまで）の順
//   試験：lap_ref_test.c（WSLか本体のgccで）。手順書 unoq_video_check_procedure.md 5-16
#pragma once
#include "hud_layout.h"

#define LR_MAX 8192            // 1周にためる点の数の上限（約10Hzで13分。超えたら古い半分を捨て、その周はベストに使わない）
#define LR_MATCH_M 40.0        // ベストの周の線からこれより離れていたら差を出さない（ピットの奥・コース外）
#define LR_MAP_NEAR_M 300.0    // ファイルから読んだベストの周は、今の位置がこれより近いときだけコース図に使う（別のコースの線を出さない）
#define LR_EDGE_S 3.0          // 周の頭と終わりがこの秒数以内まで録れていれば、1周を通して録れたとみなす

struct lr_lap { int n, no, dropped; double time_s;  // dropped：あふれて頭を捨てた
                double lat[LR_MAX], lon[LR_MAX]; float el[LR_MAX], spd[LR_MAX]; };
struct lap_ref {
    struct lr_lap cur, last, ref;  // 今の周（ここまで）、最後に通して録れた周、ベストの周
    int cur_no;                    // 今ためている周の番号（lap.CurrentLap。-1は無し）
    int idx;                       // ベストの周の中で、前に一番近かった区間
    int have_last, have_ref, ref_ok;  // ref_ok：ベストの周が今の lap.BestLap と同じ時間（差に使える）
    double delta, sdelta, best_no, pred;  // 差（秒）、速度の差（km/h）、ベストの周の番号、予想ラップ（分）。無ければNAN
    const char *path;              // ベストの周を書くファイル（NULLなら書かない）
};

static double lr_dist_m(double la0, double lo0, double la1, double lo1) {
    double kx = cos(la0 * M_PI / 180) * 111320.0, dx = (lo1 - lo0) * kx, dy = (la1 - la0) * 111320.0;
    return sqrt(dx * dx + dy * dy);
}

static int lr_save(const struct lap_ref *L) {
    if (!L->path) return 0;
    char tmp[600]; snprintf(tmp, sizeof tmp, "%s.tmp", L->path);
    FILE *f = fopen(tmp, "w"); if (!f) return 0;
    const struct lr_lap *r = &L->ref;
    fprintf(f, "lapref 1 %d %.3f %d\n", r->no, r->time_s, r->n);
    for (int i = 0; i < r->n; i++) fprintf(f, "%.8f %.8f %.3f %.2f\n", r->lat[i], r->lon[i], r->el[i], r->spd[i]);
    int ok = !ferror(f);
    if (fclose(f) || !ok) { remove(tmp); return 0; }
    return rename(tmp, L->path) == 0;
}

static int lr_load(struct lap_ref *L) {
    if (!L->path) return 0;
    FILE *f = fopen(L->path, "r"); if (!f) return 0;
    struct lr_lap *r = &L->ref;
    int ver = 0, ok = fscanf(f, "lapref %d %d %lf %d", &ver, &r->no, &r->time_s, &r->n) == 4 && ver == 1 && r->n >= 2 && r->n <= LR_MAX;
    for (int i = 0; ok && i < r->n; i++) ok = fscanf(f, "%lf %lf %f %f", &r->lat[i], &r->lon[i], &r->el[i], &r->spd[i]) == 4;
    fclose(f);
    L->have_ref = ok;
    if (!ok) r->n = 0;
    return ok;
}

static void lr_init(struct lap_ref *L, const char *path) {
    memset(L, 0, sizeof *L);
    L->cur_no = -1; L->path = path;
    L->delta = L->sdelta = L->best_no = L->pred = NAN;
    lr_load(L);
}

// 区間 lo〜hi-1 のうち、(lat, lon) に一番近い区間 i と、その中の位置 u（0〜1）、距離（m）。
// 最初の区間は手前へ、最後の区間は先へ1区間分まで延ばす（周の頭で、ベストの周の最初の点より手前にいるとき）
static double lr_nearest(const struct lr_lap *r, double lat, double lon, int lo, int hi, int *bi, double *bu) {
    const double kx = cos(lat * M_PI / 180) * 111320.0, ky = 111320.0;
    double best = INFINITY;
    for (int i = lo; i < hi && i + 1 < r->n; i++) {
        double bx = (r->lon[i + 1] - r->lon[i]) * kx, by = (r->lat[i + 1] - r->lat[i]) * ky;
        double px = (lon - r->lon[i]) * kx, py = (lat - r->lat[i]) * ky, l2 = bx * bx + by * by;
        double u = l2 > 0 ? fmin(fmax((px * bx + py * by) / l2, i == 0 ? -1 : 0), i + 2 == r->n ? 2 : 1) : 0;
        double dx = px - u * bx, dy = py - u * by, d = sqrt(dx * dx + dy * dy);
        if (d < best) { best = d; *bi = i; *bu = u; }
    }
    return best;
}

// 走行データ1行分。lat・lon：位置（度、無ければNAN）、spd：速度（km/h）、cur：lap.CurrentLap、
// el_min：lap.ElapsedTime（分）、last_min：lap.LapTime（分）、best_min：lap.BestLap（分）。無いものはNAN
static void lr_update(struct lap_ref *L, double lat, double lon, double spd, double cur, double el_min, double last_min, double best_min) {
    if (lat == 0 && lon == 0) lat = lon = NAN;  // 測位前に0が来ることがある
    const double el = el_min * 60, best = best_min * 60;
    const int no = isnan(cur) ? -1 : (int)cur;
    if (no != L->cur_no) {  // 周が変わった
        struct lr_lap *c = &L->cur;
        const double t = last_min * 60;
        if (L->cur_no > 0 && no == L->cur_no + 1 && !isnan(t) && c->n >= 20 && !c->dropped
            && c->el[0] <= LR_EDGE_S && fabs(c->el[c->n - 1] - t) <= LR_EDGE_S) {  // 1周を通して録れた
            c->no = L->cur_no; c->time_s = t;
            memcpy(&L->last, c, sizeof *c); L->have_last = 1;
            if (!isnan(best) && fabs(t - best) < .01) {  // この周がベスト
                memcpy(&L->ref, c, sizeof *c); L->have_ref = 1;
                lr_save(L);
            }
        }
        c->n = c->dropped = 0; L->cur_no = no; L->idx = 0;
    }
    struct lr_lap *c = &L->cur;
    if (!isnan(lat) && !isnan(lon) && (!c->n || isnan(el) || isnan(c->el[c->n - 1]) || el > c->el[c->n - 1])) {
        if (c->n == LR_MAX) {  // あふれたら古い半分を捨てる（ラップ計測が無いときも、コース図は新しい方の線になる）
            const int h = LR_MAX / 2;
            memmove(c->lat, c->lat + h, sizeof c->lat[0] * h); memmove(c->lon, c->lon + h, sizeof c->lon[0] * h);
            memmove(c->el, c->el + h, sizeof c->el[0] * h); memmove(c->spd, c->spd + h, sizeof c->spd[0] * h);
            c->n = h; c->dropped = 1;
        }
        c->lat[c->n] = lat; c->lon[c->n] = lon; c->el[c->n] = el; c->spd[c->n] = spd; c->n++;
    }

    const struct lr_lap *r = &L->ref;
    L->ref_ok = L->have_ref && !isnan(best) && fabs(r->time_s - best) < .05;
    L->best_no = L->ref_ok ? r->no : NAN;
    L->delta = L->sdelta = L->pred = NAN;
    if (!L->ref_ok || isnan(lat) || isnan(lon) || isnan(el) || r->n < 2) return;
    int i = 0; double u = 0;
    int lo = L->idx > 10 ? L->idx - 10 : 0, hi = L->idx + 150 < r->n ? L->idx + 150 : r->n;
    double d = lr_nearest(r, lat, lon, lo, hi, &i, &u);
    if (d > LR_MATCH_M) d = lr_nearest(r, lat, lon, 0, r->n, &i, &u);  // 前回の近くに無い（録画のやり直し・飛び）ときは全体から
    if (d > LR_MATCH_M) return;
    L->idx = i;
    L->delta = el - (r->el[i] + u * (r->el[i + 1] - r->el[i]));
    if (!isnan(spd) && !isnan(r->spd[i]) && !isnan(r->spd[i + 1])) L->sdelta = spd - (r->spd[i] + u * (r->spd[i + 1] - r->spd[i]));
    L->pred = best_min + L->delta / 60;
}

// コース図の線（HUD_TRACK_MAX点まで間引く）。lat・lon：今の位置（ファイルから読んだベストの周を使うかの判断用）
static void lr_track(const struct lap_ref *L, double lat, double lon, struct hud_track *out) {
    const struct lr_lap *src = NULL;
    if (L->have_ref && L->ref_ok) src = &L->ref;
    else if (L->have_ref && !isnan(lat) && !isnan(lon)) {
        for (int i = 0; i < L->ref.n; i += 4)
            if (lr_dist_m(lat, lon, L->ref.lat[i], L->ref.lon[i]) < LR_MAP_NEAR_M) { src = &L->ref; break; }
    }
    if (!src && L->have_last) src = &L->last;
    if (!src && L->cur.n >= 2) src = &L->cur;
    out->n = 0;
    if (!src) return;
    const int n = src->n < HUD_TRACK_MAX ? src->n : HUD_TRACK_MAX;
    for (int j = 0; j < n; j++) {
        int i = n == src->n ? j : (int)lround((double)j * (src->n - 1) / (n - 1));
        out->lat[j] = src->lat[i]; out->lon[j] = src->lon[i];
    }
    out->n = n;
}

// ---------------------------------------------------------------- 机の上の確かめ用の作り物の走行（OVERLAY_DEMO=1・試験）
// 架空のコース（tools/video_hud/hud_layout.py の DEMO_POINTS と同じ点。実在のコースではない）を、周ごとに少しずつ違う速さで走る。
// 周 k の速さは基本の速さ×f(k) なので、同じ場所での経過秒は 1/f(k) に比例し、ベストの周 b との差は 経過秒×(1 − f(k)/f(b)) になる
#define LR_DEMO_BASE_LAT 36.0
#define LR_DEMO_BASE_LON 140.0
static const double LR_DEMO_PTS[][2] = { { 0, 0 }, { 520, -10 }, { 700, 40 }, { 760, 170 }, { 690, 280 }, { 540, 260 }, { 470, 330 },
                                         { 500, 450 }, { 420, 530 }, { 230, 500 }, { 150, 380 }, { -30, 330 }, { -130, 220 }, { -120, 80 } };
#define LR_DEMO_NP ((int)(sizeof LR_DEMO_PTS / sizeof LR_DEMO_PTS[0]))
#define LR_DEMO_N 1400  // 線を細かく分けた点の数

struct lr_demo {
    double e[LR_DEMO_N], nn[LR_DEMO_N], cum[LR_DEMO_N + 1], len;  // 点（東・北のm）と、そこまでの道のり
    double s, t, lap_start, last, best;  // 道のり、時刻、周の始まり、前の周・ベスト（秒、無ければNAN）
    int lap, count;                      // 走行中の周、終わった周の数
};

static void lr_demo_init(struct lr_demo *d) {
    memset(d, 0, sizeof *d);
    for (int j = 0; j < LR_DEMO_N; j++) {
        double u = (double)j * LR_DEMO_NP / LR_DEMO_N, t = u - floor(u);
        int i = (int)u;
        const double *p0 = LR_DEMO_PTS[(i + LR_DEMO_NP - 1) % LR_DEMO_NP], *p1 = LR_DEMO_PTS[i];
        const double *p2 = LR_DEMO_PTS[(i + 1) % LR_DEMO_NP], *p3 = LR_DEMO_PTS[(i + 2) % LR_DEMO_NP];
        double q[2];
        for (int k = 0; k < 2; k++)
            q[k] = .5 * (2 * p1[k] + (p2[k] - p0[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t * t
                         + (3 * p1[k] - p0[k] - 3 * p2[k] + p3[k]) * t * t * t);
        d->e[j] = q[0]; d->nn[j] = q[1];
    }
    for (int j = 0; j < LR_DEMO_N; j++) {
        int k = (j + 1) % LR_DEMO_N;
        d->cum[j + 1] = d->cum[j] + hypot(d->e[k] - d->e[j], d->nn[k] - d->nn[j]);
    }
    d->len = d->cum[LR_DEMO_N];
    d->lap = 1; d->last = d->best = NAN;
}

static double lr_demo_factor(int lap) { return 1 + .04 * sin(1.3 * lap + 2.5); }  // 周ごとの速さの倍率（1→3→4周目とベストが更新される）
static double lr_demo_v0(const struct lr_demo *d, double s) { return 105 + 55 * sin(2 * M_PI * 3 * s / d->len); }  // km/h

// 道のり s の位置（緯度・経度）
static void lr_demo_pos(const struct lr_demo *d, double s, double *lat, double *lon) {
    s = fmod(s, d->len);
    int lo = 0, hi = LR_DEMO_N;
    while (hi - lo > 1) { int m = (lo + hi) / 2; if (d->cum[m] <= s) lo = m; else hi = m; }
    int k = (lo + 1) % LR_DEMO_N;
    double f = (s - d->cum[lo]) / (d->cum[lo + 1] - d->cum[lo]);
    double e = d->e[lo] + f * (d->e[k] - d->e[lo]), n = d->nn[lo] + f * (d->nn[k] - d->nn[lo]);
    *lat = LR_DEMO_BASE_LAT + n / 111320.0;
    *lon = LR_DEMO_BASE_LON + e / (111320.0 * cos(LR_DEMO_BASE_LAT * M_PI / 180));
}

// 時刻 t（秒）まで走らせる（1ステップ5ms以下に刻む）。周を回ったら前の周・ベストを更新する
static void lr_demo_step(struct lr_demo *d, double t) {
    while (d->t < t) {
        double dt = fmin(.005, t - d->t), v = lr_demo_v0(d, d->s) * lr_demo_factor(d->lap) / 3.6;
        double s1 = d->s + v * dt, end = d->len * d->lap;
        if (s1 >= end) {  // ラインを通った時刻を補間する
            double tc = d->t + (end - d->s) / v, lap_s = tc - d->lap_start;
            d->last = lap_s; d->best = isnan(d->best) ? lap_s : fmin(d->best, lap_s);
            d->count = d->lap; d->lap++; d->lap_start = tc;
        }
        d->s = s1; d->t += dt;
    }
}
