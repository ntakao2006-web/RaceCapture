// tele_smooth.h：走行データの値を、描くコマ（カメラがその絵を撮った時刻）に合わせて前後のサンプルの間で直線に補間する（手順書5-24）
//   overlay_rec.c は30コマ/秒で描くが、値（EcoCaptureの /api/telemetry）は飛び飛びに届く。届いた値をそのまま描くと、
//   針が何コマか止まっては跳ぶ（2026-11-07まで：約10Hzで読み、3コマ同じ角度→跳ぶ。読む間隔とEcoCaptureの更新が
//   揃わないので、2コマ・4コマのこともあった）。
//   ここでは届いたサンプルを、サンプル自身の時刻（mcu_ms。STM32の時計なので受け取りのばらつきが乗らない）と一緒にためておき、
//   そのコマの絵をカメラが撮った時刻の値を、前後のサンプルから直線で求める（tsm_frame）。こうすると景色と針の時刻が揃う。
//   ただし撮った時刻の値がまだ届いていないこと（カメラの絵が届くのが値より速いとき）がある。先を当て推量すると行き過ぎるので、
//   そのときは「今 − 待つ秒」まで戻す。待つ秒は「今 − いちばん新しいサンプルの時刻」の最近の最大（＝値が届くまでの最悪の遅れ）で、
//   本体で動きながら自分で測る（ゆっくり縮め、上限は dmax）。その分だけ針が景色より遅れる（前の描き方の平均の遅れ約0.1秒より短い）。
//   STM32の時計と本体の時計（CLOCK_MONOTONIC）の差は「受け取った時刻 − サンプルの時刻」の一番小さいもの（遅れの一番少ないもの）とし、
//   時計の進みの違い（水晶のずれ）に付いていくよう、1秒に TSM_RELAX 秒ずつ大きい側へゆるめる。この一番小さい遅れ（STM32→本体、
//   数ms〜十数ms）の分だけは、針が景色より古いままになる。
//   使うのは針のメーター・弧・棒・Gボールだけ（hud_draw の vs）。数字・ラップ・コース図は届いた値をそのまま描く。
// PCの試験：tele_smooth_test.c
#ifndef TELE_SMOOTH_H
#define TELE_SMOOTH_H
#include <math.h>
#include <string.h>

#ifndef TSM_MAXV
#define TSM_MAXV 32
#endif
#define TSM_N 16          // ためるサンプルの数（約20個/秒で0.8秒。待つ秒の上限より十分長い）
#define TSM_RELAX 0.0005  // 時計の差を1秒にこれだけ大きい側へゆるめる（水晶のずれは多くて1秒に0.0001秒。大きいほど針が景色より遅れる）
#define TSM_GAP 0.5       // 前後のサンプルがこれより離れていれば補間しない（途切れのあと。近い方の値を使う）
#define TSM_SHRINK 0.05   // 待つ秒を1秒にこれだけ縮める（たまの大きな遅れのあと、約数秒で戻る）
#define TSM_MARGIN 0.005  // 待つ秒に足す余裕

struct tsm_s { double t; double v[TSM_MAXV]; };
struct tsm {
    int n, head;          // 入っている数・いちばん新しいものの位置
    int has_off; double off, off_got;  // 本体の時計 − サンプルの時刻（いちばん遅れの少ないもの）と、それを求めた受け取り時刻
    double wait, wait_at;  // 待つ秒（値が届くまでの最近の最悪の遅れ）と、それを最後に直した時刻
    double behind;         // 最後のコマで、針が景色より遅れた秒（0なら撮った時刻の値）
    struct tsm_s s[TSM_N];
};

static void tsm_reset(struct tsm *m) { m->n = 0; m->head = 0; m->has_off = 0; m->wait = 0; m->wait_at = 0; m->behind = 0; }

static const struct tsm_s *tsm_at(const struct tsm *m, int i) {  // i=0 がいちばん古い
    return &m->s[(m->head - (m->n - 1) + i + TSM_N) % TSM_N];
}

// 届いたサンプルを足す。t：サンプルの時刻（秒。mcu_ms/1000。分からなければNAN→受け取った時刻を使う）、got：受け取った時刻（now()）。
// 前と同じ時刻なら（同じサンプルを読み直しただけ）足さずに0を返す。時刻が戻ったら（STM32の再起動）ためたものを捨てて始め直す
static int tsm_push(struct tsm *m, double t, double got, const double *v, int nv) {
    if (isnan(t)) t = got;
    if (nv > TSM_MAXV) nv = TSM_MAXV;
    if (m->n) {
        const double last = m->s[m->head].t;
        if (t == last) return 0;
        if (t < last) tsm_reset(m);
    }
    const double e = got - t;
    if (!m->has_off) { m->off = e; m->has_off = 1; }
    else m->off = fmin(e, m->off + (got - m->off_got) * TSM_RELAX);
    m->off_got = got;
    m->head = m->n ? (m->head + 1) % TSM_N : 0;
    if (m->n < TSM_N) m->n++;
    struct tsm_s *s = &m->s[m->head];
    s->t = t;
    for (int i = 0; i < TSM_MAXV; i++) s->v[i] = i < nv ? v[i] : NAN;
    return 1;
}

// サンプルの時刻 tq（STM32の時計）の値を out へ。まだ何も無ければNAN。tq がいちばん新しいものより先なら、それのまま（行き過ぎない）
static void tsm_value(const struct tsm *m, double tq, double *out, int nv) {
    if (nv > TSM_MAXV) nv = TSM_MAXV;
    if (!m->n) { for (int i = 0; i < nv; i++) out[i] = NAN; return; }
    const struct tsm_s *hi = &m->s[m->head];
    if (tq >= hi->t || m->n == 1) { memcpy(out, hi->v, sizeof out[0] * nv); return; }
    const struct tsm_s *lo = tsm_at(m, 0);
    if (tq <= lo->t) { memcpy(out, lo->v, sizeof out[0] * nv); return; }
    for (int k = m->n - 2; k >= 0; k--) {
        lo = tsm_at(m, k); hi = tsm_at(m, k + 1);
        if (lo->t <= tq) break;
    }
    const double span = hi->t - lo->t, a = span > 0 ? (tq - lo->t) / span : 1;
    for (int i = 0; i < nv; i++) {
        const double x = lo->v[i], y = hi->v[i];
        if (span > TSM_GAP || isnan(x) || isnan(y)) out[i] = a < .5 ? x : y;  // 途切れ・片方が無い：近い方
        else out[i] = x + (y - x) * a;
    }
}

// 1コマ分の値を out へ。cam：そのコマの絵をカメラが撮った時刻、now：今（どちらも本体の時計）。dmax：待つ秒の上限
// （0以下なら補間せず、いちばん新しい値＝前の描き方）。描画のスレッドから毎コマ1回呼ぶ
static void tsm_frame(struct tsm *m, double cam, double now, double dmax, double *out, int nv) {
    if (dmax <= 0 || !m->n) { tsm_value(m, INFINITY, out, nv); m->behind = 0; return; }
    // 値が届くまでの遅れ：今 − いちばん新しいサンプルの時刻（本体の時計で）。最近の最大を覚え、ゆっくり縮める
    const double gap = now - m->off - m->s[m->head].t;
    // 途切れ（値が来ない間）で大きくなっても上限で止める（戻るのに何十秒もかからないように）
    m->wait = fmin(m->wait_at > 0 ? fmax(gap, m->wait - (now - m->wait_at) * TSM_SHRINK) : gap, dmax);
    m->wait_at = now;
    const double w = fmin(fmax(m->wait + TSM_MARGIN, 0), dmax), safe = now - w;
    const double t = fmin(cam, safe);  // 撮った時刻。その値がまだ届いていなければ、届いている所まで
    m->behind = cam - t;
    tsm_value(m, t - m->off, out, nv);
}
#endif
