// lap_ref_test.c：lap_ref.h（ベストとの差・コース図の線）の試験。作り物の走行（lr_demo）を約10Hzで流して確かめる
// ビルド・実行（WSLか本体）: gcc -O2 -Wall -o lap_ref_test lap_ref_test.c -lm && ./lap_ref_test
//   周 k の速さは基本×f(k) なので、ベストの周 b との差の正解は 経過秒×(1 − f(k)/f(b))、速度の差は 速度×(1 − f(b)/f(k))
#include "lap_ref.h"

static int fails;
#define CHECK(cond, ...) do { if (!(cond)) { fails++; printf("NG: "); printf(__VA_ARGS__); printf("\n"); } } while (0)

static unsigned rng = 12345;
static double noise_m(double a) { rng = rng * 1103515245u + 12345u; return a * (((rng >> 8) & 0xffff) / 32767.5 - 1); }

static struct lap_ref L, L2;
static struct lr_demo d;
static struct hud_track trk;

// 走行データ1行分を作って lr_update へ。noise：位置のぶれ（m）、off：横へずらす（m）
static void feed(struct lap_ref *l, double t, double noise, double off) {
    lr_demo_step(&d, t);
    double lat, lon; lr_demo_pos(&d, d.s, &lat, &lon);
    lat += (noise_m(noise) + off) / 111320.0;
    lon += noise_m(noise) / (111320.0 * cos(lat * M_PI / 180));
    double spd = lr_demo_v0(&d, d.s) * lr_demo_factor(d.lap);
    double el = (t - d.lap_start) / 60, last = d.last / 60, best = d.best / 60;
    lr_update(l, lat, lon, spd, d.lap, el, last, best);
}

// ベストの周の番号（作り物の走行の、終わった周の中で一番速い周）
static int best_lap_no(int count) {
    int b = 1;
    for (int k = 2; k <= count; k++) if (lr_demo_factor(k) > lr_demo_factor(b)) b = k;
    return b;
}

int main(void) {
    const char *path = "/tmp/lap_ref_test.txt";
    remove(path);
    lr_demo_init(&d);
    lr_init(&L, path);
    printf("作り物のコース 1周 %.0f m\n", d.len);

    // 1. 何周か走らせ、2周目以降は差と速度の差を正解と比べる。8周目までは位置のぶれ無し、12周目までは±1.5mのぶれ
    double t = 0, laps[16] = { 0 };
    for (int pass = 0; pass < 2; pass++) {
        const double noise = pass ? 1.5 : 0;
        double maxe = 0, maxs = 0, sse = 0; int n = 0, nan_after_ref = 0;
        for (; d.count < (pass ? 12 : 8); t += .1) {
            feed(&L, t, noise, 0);
            if (d.count) laps[d.count] = d.last;
            if (d.count >= 1) {
                int b = best_lap_no(d.count);
                CHECK(L.ref_ok && L.best_no == b, "t=%.1f ベストの周 %g（正解 %d）", t, L.best_no, b);
                if (isnan(L.delta)) { nan_after_ref++; continue; }
                double el = t - d.lap_start, fk = lr_demo_factor(d.lap), fb = lr_demo_factor(b);
                double want = el * (1 - fk / fb), spd = lr_demo_v0(&d, d.s) * fk, swant = spd * (1 - fb / fk);
                maxe = fmax(maxe, fabs(L.delta - want)); maxs = fmax(maxs, fabs(L.sdelta - swant)); n++;
                sse += (L.delta - want) * (L.delta - want);
                CHECK(fabs(L.pred - (d.best / 60 + L.delta / 60)) < 1e-9, "予想ラップ");
            } else CHECK(isnan(L.delta) && isnan(L.best_no), "1周目は差が出ない");
        }
        printf("1. %s：差の誤差 最大 %.3f 秒・二乗平均 %.3f 秒、速度の差の誤差 最大 %.2f km/h（%d行、差が出なかった行 %d）\n",
               pass ? "9〜12周目（±1.5mのぶれ）" : "1〜8周目（ぶれ無し）", maxe, sqrt(sse / n), maxs, n, nan_after_ref);
        CHECK(maxe < (pass ? .4 : .03), "差の誤差が大きい %.3f", maxe);
        CHECK(sqrt(sse / n) < (pass ? .1 : .01), "差の誤差の二乗平均が大きい");
        CHECK(maxs < (pass ? 3 : .5), "速度の差の誤差が大きい %.2f", maxs);
        CHECK(nan_after_ref == 0, "差が出ない行がある %d", nan_after_ref);
    }
    for (int k = 1; k <= 12; k++) printf("   %d周目 %.2f 秒%s\n", k, laps[k], k == best_lap_no(12) ? "（ベスト）" : "");

    // 2. コース図の線：300点以内、ベストの周を使う
    lr_track(&L, NAN, NAN, &trk);
    CHECK(trk.n == HUD_TRACK_MAX, "コース図の点 %d", trk.n);
    CHECK(trk.lat[0] == L.ref.lat[0] && trk.lat[trk.n - 1] == L.ref.lat[L.ref.n - 1], "コース図はベストの周の頭から終わりまで");

    // 3. コースから60m離れると差を出さない（戻れば出る）
    for (double t1 = t + 3; t < t1; t += .1) feed(&L, t, 0, 60);
    CHECK(isnan(L.delta), "コース外で差が出ている %.2f", L.delta);
    for (double t1 = t + 3; t < t1; t += .1) feed(&L, t, 0, 0);
    CHECK(!isnan(L.delta), "コースへ戻っても差が出ない");

    // 4. 録画をやり直した（ファイルから読む）：BestLapが同じならすぐ差が出る。途中の周から始めても全体から探す
    lr_init(&L2, path);
    CHECK(L2.have_ref && L2.ref.n == L.ref.n && L2.ref.no == L.ref.no, "ファイルから読めない");
    for (double t1 = t + 1; t < t1; t += .1) feed(&L2, t, 1.5, 0);
    CHECK(L2.ref_ok && !isnan(L2.delta) && fabs(L2.delta - L.delta) < .2, "読み直した後の差 %.3f / %.3f", L2.delta, L.delta);
    lr_track(&L2, NAN, NAN, &trk);
    CHECK(trk.n == HUD_TRACK_MAX, "読み直した後のコース図");

    // 5. ラップのリセット（BestLapが無い・違う）：差は出さないが、近くにいればコース図はファイルの線を使う
    lr_init(&L2, path);
    double lat, lon; lr_demo_pos(&d, d.s, &lat, &lon);
    lr_update(&L2, lat, lon, 100, 0, NAN, NAN, NAN);
    CHECK(!L2.ref_ok && isnan(L2.delta) && isnan(L2.best_no), "リセット後に差が出ている");
    lr_track(&L2, lat, lon, &trk);
    CHECK(trk.n == HUD_TRACK_MAX, "リセット後、近くならファイルの線");
    lr_track(&L2, lat + .05, lon, &trk);  // 約5.6km離れた（別のコース）
    CHECK(trk.n == 0, "別の場所ではファイルの線を出さない（%d点）", trk.n);
    lr_update(&L2, lat, lon, 100, 1, .5, NAN, 9.0);  // 違うベスト
    CHECK(!L2.ref_ok, "違うベストで差に使っている");

    // 6. 途中から始めた周（頭が録れていない）は使わない。その間もコース図は今の周（ここまで）。次の周からは使う
    remove(path);
    for (; t - d.lap_start < 20; t += .1) lr_demo_step(&d, t);  // 周の20秒目まで（録画はまだ）
    const int c0 = d.count;
    lr_init(&L2, path);
    for (int checked = 0; d.count < c0 + 1; t += .1) {
        feed(&L2, t, 0, 0);
        if (!checked && t - d.lap_start > 40) {
            lr_track(&L2, NAN, NAN, &trk);
            CHECK(trk.n >= 2 && trk.n == (L2.cur.n < HUD_TRACK_MAX ? L2.cur.n : HUD_TRACK_MAX), "途中の周でもコース図（今の周）が出る（%d点）", trk.n);
            checked = 1;
        }
    }
    CHECK(!L2.have_ref && !L2.have_last, "途中からの周を使った");
    for (; d.count < c0 + 2; t += .1) feed(&L2, t, 0, 0);
    CHECK(L2.have_last && L2.last.no == c0 + 2, "次の周（通して録れた）がある");
    printf("6. 途中から始めた後：最後の周 %d周目、ベストの周 %s（BestLapは%d周目）\n", L2.last.no,
           L2.ref_ok ? "あり" : "なし（BestLapは録画を始める前の周）", best_lap_no(d.count));

    // 7. 1周がLR_MAX点を超えたら使わない（ピットで長く止まった周など）
    lr_init(&L2, NULL);
    for (int k = 0; k < LR_MAX + 5; k++) lr_update(&L2, 36.0 + k * 1e-7, 140.0, 0, 5, k * .1 / 60, NAN, NAN);
    CHECK(L2.cur.n == LR_MAX / 2 + 5 && L2.cur.lat[L2.cur.n - 1] == 36.0 + (LR_MAX + 4) * 1e-7, "あふれたら古い半分を捨てて続ける（%d点）", L2.cur.n);
    lr_update(&L2, 36.0, 140.0, 0, 6, 0, 13.7 / 60 * 60, 13.7);
    CHECK(!L2.have_last && !L2.have_ref, "点が多すぎる周を使った");

    printf(fails ? "NG %d件\n" : "すべてOK\n", fails);
    return fails != 0;
}
