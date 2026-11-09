// hud_layout.h：走行映像に焼き込む計器を、設定ファイル（hud.ini）のとおりに組み立てる（GLを使わない部分）
//   overlay_rec.c と、PCの見た目の確認（tools/video_hud/hud_layout.py）との突き合わせ用の hud_dump.c から使う。
//   hud_layout.py は同じ規則をPythonで持つ。規則を変えたら両方を直し、tools/video_hud/test_hud_layout.py を通す
//   （突き合わせの元の数字 tools/video_hud/testdata/*.golden は hud_dump で作り直す）
//   座標は1920x1080・左上が0。1枚分の四角形を hv[] にためる（頂点ごとに x, y, u, v, r, g, b, a。uが負なら塗りつぶし）
//   書き方の説明は tools/video_hud/hud.ini の頭にある
#pragma once
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <time.h>

// ---------------------------------------------------------------- 四角形をためる
// 文字の一覧表（hud_font_64.pgm）の寸法。読み込む側（overlay_rec.c の load_font 等）が入れる
static int cell_w, cell_h, first_ch, n_ch, atlas_cols, atlas_w, atlas_h;
#define HUD_MAX 12000  // 1枚にためる頂点の数の上限（四角形1つで6）
static float hv[8 * HUD_MAX];  // 頂点（x, y, u, v, r, g, b, a）
static int hn;

// 四角形（頂点4つ：p0 p1 p2 p3 の順に回る）を三角形2つでためる。u0<0なら塗りつぶし
static void quad4(const float x[4], const float y[4], float u0, float v0, float u1, float v1, const float c[4]) {
    if (hn + 6 > HUD_MAX) return;
    const float u[4] = { u0, u1, u1, u0 }, v[4] = { v0, v0, v1, v1 };
    static const int ord[6] = { 0, 1, 3, 1, 2, 3 };
    for (int k = 0; k < 6; k++) {
        float *p = hv + 8 * hn++; int i = ord[k];
        p[0] = x[i]; p[1] = y[i]; p[2] = u[i]; p[3] = v[i]; memcpy(p + 4, c, 4 * sizeof(float));
    }
}

static void rect(float x0, float y0, float x1, float y1, const float c[4]) {
    const float x[4] = { x0, x1, x1, x0 }, y[4] = { y0, y0, y1, y1 };
    quad4(x, y, -1, -1, -1, -1, c);
}

// 太さwの線分
static void seg(float x0, float y0, float x1, float y1, float w, const float c[4]) {
    float dx = x1 - x0, dy = y1 - y0, l = sqrtf(dx * dx + dy * dy); if (l <= 0) return;
    float nx = -dy / l * w / 2, ny = dx / l * w / 2;
    const float x[4] = { x0 + nx, x1 + nx, x1 - nx, x0 - nx }, y[4] = { y0 + ny, y1 + ny, y1 - ny, y0 - ny };
    quad4(x, y, -1, -1, -1, -1, c);
}

// 文字列を (x, y)（左上）から描く。s＝倍率（1.0で1文字 cell_w×cell_h）。戻り値は右端
static float text(float x, float y, float s, const float c[4], const char *str) {
    int n = 0;
    for (const char *p = str; *p && n < 64; p++, n++) {
        int i = (unsigned char)*p - first_ch; if (i < 0 || i >= n_ch) i = 0;
        float u0 = (float)(i % atlas_cols) * cell_w / atlas_w, v0 = (float)(i / atlas_cols) * cell_h / atlas_h;
        float u1 = u0 + (float)cell_w / atlas_w, v1 = v0 + (float)cell_h / atlas_h;
        float x0 = x + n * cell_w * s, x1 = x0 + cell_w * s, y1 = y + cell_h * s;
        const float qx[4] = { x0, x1, x1, x0 }, qy[4] = { y, y, y1, y1 };
        quad4(qx, qy, u0, v0, u1, v1, c);
    }
    return x + n * cell_w * s;
}
static float text_w(float s, const char *str) { return strlen(str) * cell_w * s; }

// 円の上の点。角度は度で、0が真上・時計回り
static void polar(float cx, float cy, double r, double deg, float *x, float *y) {
    double a = deg * M_PI / 180;
    *x = cx + r * sin(a); *y = cy - r * cos(a);
}

// 半径 r0〜r1 の帯を角度 a0〜a1 まで、n 個の四角形で（r0 = 0 なら扇形）
static void band_n(float cx, float cy, double r0, double r1, double a0, double a1, int n, const float c[4]) {
    for (int k = 0; k < n; k++) {
        double b0 = a0 + (a1 - a0) * k / n, b1 = a0 + (a1 - a0) * (k + 1) / n;
        float x[4], y[4];
        polar(cx, cy, r1, b0, &x[0], &y[0]); polar(cx, cy, r1, b1, &x[1], &y[1]);
        polar(cx, cy, r0, b1, &x[2], &y[2]); polar(cx, cy, r0, b0, &x[3], &y[3]);
        quad4(x, y, -1, -1, -1, -1, c);
    }
}
static void band(float cx, float cy, double r0, double r1, double a0, double a1, const float c[4]) {  // 5度ごと
    if (a1 != a0) band_n(cx, cy, r0, r1, a0, a1, (int)ceil(fabs(a1 - a0) / 5), c);
}

static void fmt_laptime(char *b, size_t n, double minutes, int decimals) {
    if (isnan(minutes) || minutes < 0) { snprintf(b, n, decimals == 1 ? "-:--.-" : "-:--.--"); return; }
    double sec = minutes * 60; int m = (int)(sec / 60); double s = sec - m * 60;
    if (decimals == 1) snprintf(b, n, "%d:%04.1f", m, s); else snprintf(b, n, "%d:%05.2f", m, s);
}

static const float WHITE[4] = { .95f, .97f, 1, 1 }, GREY[4] = { .65f, .7f, .75f, 1 }, DIM[4] = { .55f, .6f, .65f, 1 };
static const float YELLOW[4] = { 1, .8f, 0, 1 }, RED[4] = { 1, .2f, .15f, 1 }, GREEN[4] = { .25f, .9f, .35f, 1 };
static const float PANEL[4] = { 0, 0, 0, .55f }, TRACK[4] = { .2f, .2f, .22f, .7f }, BLACK[4] = { 0, 0, 0, 1 };
static const float OUTLINE[4] = { 0, 0, 0, .6f };

// ---------------------------------------------------------------- 設定（hud.ini）
#define HUD_ITEMS 64
#define HUD_REFS 32
#define HUD_REF_LEN 96
#define HUD_STR 48
#define HUD_COLORS 32
#define HUD_SECS 80
#define HUD_KVS 48
#define HUD_LINE 1024
#define HUD_VAL 160

#define HUD_TRACK_MAX 300  // コース図の線の点の数の上限
#define HUD_MAP_MIN_M 100.0  // コース図の線の広がりがこれ（m）より小さければ描かない

enum { HT_BOX, HT_TEXT, HT_VALUE, HT_BAR, HT_GBALL, HT_CLOCK, HT_DIAL, HT_ARC, HT_MAP };
enum { HS_ALWAYS, HS_NODATA, HS_NEVER };
enum { HD_RIGHT, HD_LEFT, HD_UP, HD_DOWN };
enum { HF_NUMBER, HF_LAPTIME, HF_SIGNED };

struct hud_item {
    int type, show, right, fmt, decimals, dir, flip_x, flip_y, has_box, rings;  // right：0 左寄せ・1 右寄せ・2 真ん中。fmt は HF_ の値
    int ref, ref2;  // 値の番号（hud.ref の添字）。無ければ-1
    float x, y, size, rect[4], box[4], tick_width, radius, line_width, dot;
    float width, tick_length, label_size, needle_width, outline_width;
    float color[4], missing[4], warn_c[4], alarm_c[4], box_c[4], track_c[4], tick_c[4], ring_c[4], cross_c[4];
    float needle_c[4], face_c[4], outline_c[4];
    double warn_at, alarm_at, warn_below, alarm_below, scale, offset, min, max, tick_every, full;
    double origin, start, sweep, minor_every, label_every, label_scale, rotate;
    char text[HUD_STR], prefix[HUD_STR], unit[HUD_STR];
};
// コース図の線（緯度・経度。本体では lap_ref.h が走行中に作る）
struct hud_track { int n; double lat[HUD_TRACK_MAX], lon[HUD_TRACK_MAX]; };
struct hud {
    int n, nref;
    double nodata_after;  // 数値がこの秒数来なければ show = nodata の計器を出す
    struct hud_item it[HUD_ITEMS];
    char ref[HUD_REFS][HUD_REF_LEN];  // 値の名前（"values.Speed|values.GPSSpeed" の形のまま）
};

struct hud_kv { char key[32], val[HUD_VAL]; int line; };
struct hud_sec { char name[40]; int line, nkv; struct hud_kv kv[HUD_KVS]; };
struct hud_color { char name[32]; float c[4]; };

// どの種類で使えるキーか（どの種類にも type show box box_color が使える）
#define HUD_NTYPES 9
#define HUD_TYPE_LIST "box text value bar gball clock dial arc map"
static const char *HUD_TYPES[HUD_NTYPES] = { "box", "text", "value", "bar", "gball", "clock", "dial", "arc", "map" };
static const char *HUD_KEYS[HUD_NTYPES] = {
    "rect color",
    "x y size color align text",
    "x y size color align value scale offset decimals prefix unit format missing_color"
    " warn_at alarm_at warn_below alarm_below warn_color alarm_color",
    "rect value scale offset min max origin direction color warn_at alarm_at warn_below alarm_below warn_color alarm_color"
    " track_color tick_every tick_color tick_width",
    "center radius full rings x_value y_value flip_x flip_y ring_color cross_color color dot line_width",
    "x y size color align",
    "center radius value scale offset min max start sweep tick_every minor_every tick_length tick_width"
    " label_every label_scale label_size decimals color needle_color needle_width face_color ring_color line_width"
    " warn_at alarm_at warn_color alarm_color",
    "center radius width value scale offset min max start sweep color warn_at alarm_at warn_below alarm_below"
    " warn_color alarm_color track_color tick_every tick_color tick_width",
    "rect color dot track_color line_width outline_color outline_width rotate",
};
static const char *HUD_NEED[HUD_NTYPES] = { "rect", "x y text", "x y value", "rect value max", "center radius", "x y",
                                            "center radius value max", "center radius value max", "rect" };

static int hud_err(char *err, size_t n, int line, const char *fmt, ...) {
    va_list ap; va_start(ap, fmt);
    int k = line > 0 ? snprintf(err, n, "%d行目: ", line) : 0;
    if (k < 0 || (size_t)k >= n) k = 0;
    vsnprintf(err + k, n - k, fmt, ap);
    va_end(ap);
    return 0;
}

static char *hud_trim(char *s) {
    while (*s == ' ' || *s == '\t' || *s == '\r') s++;
    size_t n = strlen(s);
    while (n && (s[n - 1] == ' ' || s[n - 1] == '\t' || s[n - 1] == '\r')) s[--n] = 0;
    return s;
}

// 空白で区切った語の並び list に w があるか
static int hud_word(const char *list, const char *w) {
    size_t n = strlen(w);
    for (const char *p = list; (p = strstr(p, w)); p += n)
        if ((p == list || p[-1] == ' ') && (p[n] == ' ' || !p[n])) return 1;
    return 0;
}

static int hud_ident(const char *s, const char *extra) {  // 英数字と_（と extra の文字）だけ
    if (!*s) return 0;
    for (; *s; s++)
        if (!((*s >= 'a' && *s <= 'z') || (*s >= 'A' && *s <= 'Z') || (*s >= '0' && *s <= '9') || *s == '_' || (extra && *s && strchr(extra, *s)))) return 0;
    return 1;
}

// 数値（1, -2.5, .5, 1e3 の形だけ。0x10・inf・nan は受けない）
static int hud_num(const char *s, double *out) {
    if (!*s || strspn(s, "+-.0123456789eE") != strlen(s)) return 0;
    char *e; *out = strtod(s, &e);
    return *e == 0 && e != s && isfinite(*out);
}

// 空白かカンマで区切った数をちょうど n 個
static int hud_nums(const char *s, double *out, int n) {
    char b[HUD_VAL]; snprintf(b, sizeof b, "%s", s);
    int k = 0;
    for (char *t = strtok(b, " \t,"); t; t = strtok(NULL, " \t,")) { if (k >= n || !hud_num(t, &out[k])) return 0; k++; }
    return k == n;
}

static int hud_color(const char *s, const struct hud_color *uc, int nuc, float c[4]) {
    if (*s == '#') {
        size_t n = strlen(s + 1);
        if ((n != 6 && n != 8) || strspn(s + 1, "0123456789abcdefABCDEF") != n) return 0;
        for (size_t i = 0; i < n / 2; i++) { char h[3] = { s[1 + 2 * i], s[2 + 2 * i], 0 }; c[i] = strtol(h, NULL, 16) / 255.0f; }
        if (n == 6) c[3] = 1;
        return 1;
    }
    if ((*s >= 'a' && *s <= 'z') || (*s >= 'A' && *s <= 'Z')) {
        for (int i = 0; i < nuc; i++) if (!strcasecmp(s, uc[i].name)) { memcpy(c, uc[i].c, sizeof uc[i].c); return 1; }
        static const struct { const char *name; const float *c; } B[] = {
            { "white", WHITE }, { "grey", GREY }, { "gray", GREY }, { "dim", DIM }, { "yellow", YELLOW }, { "red", RED },
            { "green", GREEN }, { "panel", PANEL }, { "track", TRACK }, { "black", BLACK } };
        for (size_t i = 0; i < sizeof B / sizeof B[0]; i++) if (!strcasecmp(s, B[i].name)) { memcpy(c, B[i].c, 4 * sizeof(float)); return 1; }
        return 0;
    }
    double d[4];
    if (hud_nums(s, d, 4)) {} else if (hud_nums(s, d, 3)) d[3] = 1; else return 0;
    for (int i = 0; i < 4; i++) { if (d[i] < 0 || d[i] > 1) return 0; c[i] = (float)d[i]; }
    return 1;
}

// 文字（"…" で囲んでもよい）。一覧表にある文字（英数字と記号）と「°」「℃」だけ。
// 「°」は一覧表の127番目（HUD_DEG）に置いてあり、UTF-8の「°」はその1バイトに、「℃」は「°C」の2バイトに直す
#define HUD_DEG 127
static int hud_str(const char *s, char out[HUD_STR]) {
    size_t n = strlen(s), m = 0;
    if (n >= 2 && s[0] == '"' && s[n - 1] == '"') { s++; n -= 2; }
    for (size_t i = 0; i < n; i++) {
        const unsigned char *p = (const unsigned char *)s + i;
        char c[2]; int k = 1;
        if (i + 1 < n && p[0] == 0xC2 && p[1] == 0xB0) { c[0] = (char)HUD_DEG; i += 1; }
        else if (i + 2 < n && p[0] == 0xE2 && p[1] == 0x84 && p[2] == 0x83) { c[0] = (char)HUD_DEG; c[1] = 'C'; k = 2; i += 2; }
        else if (p[0] < 32 || p[0] > 126) return 0;
        else c[0] = (char)p[0];
        if (m + k >= HUD_STR) return 0;
        memcpy(out + m, c, k); m += k;
    }
    out[m] = 0;
    return 1;
}

static int hud_add_ref(struct hud *h, const char *spec) {
    for (int i = 0; i < h->nref; i++) if (!strcmp(h->ref[i], spec)) return i;
    if (h->nref >= HUD_REFS) return -2;
    snprintf(h->ref[h->nref], HUD_REF_LEN, "%s", spec);
    return h->nref++;
}

// 値の名前：「区分.名前」か「名前」を | でつないだもの
static int hud_refspec(const char *s) {
    if (strlen(s) >= HUD_REF_LEN || !hud_ident(s, ".|")) return 0;
    char b[HUD_REF_LEN]; snprintf(b, sizeof b, "%s", s);
    if (b[0] == '|' || b[strlen(b) - 1] == '|' || strstr(b, "||")) return 0;
    for (char *t = strtok(b, "|"); t; t = strtok(NULL, "|")) {
        char *d = strchr(t, '.');
        if (d && (d == t || !d[1] || strchr(d + 1, '.'))) return 0;
    }
    return 1;
}

static const struct hud_kv *hud_get(const struct hud_sec *s, const char *key) {
    for (int i = 0; i < s->nkv; i++) if (!strcmp(s->kv[i].key, key)) return &s->kv[i];
    return NULL;
}

// 1つの計器の節を組み立てる
static int hud_item(struct hud *h, const struct hud_sec *s, const struct hud_color *uc, int nuc, char *err, size_t errn) {
    const struct hud_kv *tk = hud_get(s, "type");
    if (!tk) return hud_err(err, errn, s->line, "[%s] に type が無い（" HUD_TYPE_LIST " のどれか）", s->name);
    int type = -1;
    for (int i = 0; i < HUD_NTYPES; i++) if (!strcmp(tk->val, HUD_TYPES[i])) type = i;
    if (type < 0) return hud_err(err, errn, tk->line, "type「%s」は無い（" HUD_TYPE_LIST " のどれか）", tk->val);
    if (h->n >= HUD_ITEMS) return hud_err(err, errn, s->line, "計器が多すぎる（%d個まで）", HUD_ITEMS);
    struct hud_item *it = &h->it[h->n];
    memset(it, 0, sizeof *it);
    it->type = type; it->ref = it->ref2 = -1; it->size = 1; it->scale = 1; it->max = NAN;
    it->warn_at = it->alarm_at = it->warn_below = it->alarm_below = NAN;
    it->decimals = -1; it->full = 1.5; it->rings = 1; it->dot = 18; it->line_width = 3; it->tick_width = 3;
    it->origin = NAN; it->start = -135; it->sweep = 270; it->label_every = NAN; it->label_scale = 1;
    it->width = 20; it->tick_length = NAN; it->label_size = .4f; it->needle_width = 6;
    if (type == HT_DIAL) it->line_width = 0;  // 針のメーターの外周の線は、line_width を書いたときだけ
    if (type == HT_MAP) it->line_width = 4;
    memcpy(it->color, type == HT_BAR || type == HT_ARC ? GREEN : type == HT_GBALL ? YELLOW : type == HT_MAP ? RED : WHITE, sizeof it->color);
    memcpy(it->warn_c, YELLOW, sizeof it->warn_c); memcpy(it->alarm_c, RED, sizeof it->alarm_c);
    memcpy(it->box_c, PANEL, sizeof it->box_c); memcpy(it->track_c, type == HT_MAP ? WHITE : TRACK, sizeof it->track_c);
    memcpy(it->tick_c, PANEL, sizeof it->tick_c); memcpy(it->ring_c, GREY, sizeof it->ring_c); memcpy(it->cross_c, DIM, sizeof it->cross_c);
    memcpy(it->needle_c, RED, sizeof it->needle_c); memcpy(it->outline_c, OUTLINE, sizeof it->outline_c);  // face_c は透明（描かない）
    int has_missing = 0, has_box_c = 0;
    const char *ref1 = type == HT_GBALL ? "values.LatAccel" : type == HT_MAP ? "values.Lat" : NULL;
    const char *ref2 = type == HT_GBALL ? "values.LongAccel" : type == HT_MAP ? "values.Lon" : NULL;

    for (int i = 0; i < s->nkv; i++) {
        const struct hud_kv *kv = &s->kv[i];
        const char *k = kv->key, *v = kv->val;
        double d[4];
        if (!strcmp(k, "type")) continue;
        if (!hud_word("show box box_color", k) && !hud_word(HUD_KEYS[type], k))
            return hud_err(err, errn, kv->line, "%s に「%s」は使えない（使えるのは：type show box box_color %s）", HUD_TYPES[type], k, HUD_KEYS[type]);
#define NUM(field) do { if (!hud_num(v, &d[0])) return hud_err(err, errn, kv->line, "%s は数で書く（「%s」）", k, v); field = d[0]; } while (0)
#define COLOR(field) do { if (!hud_color(v, uc, nuc, field)) return hud_err(err, errn, kv->line, "%s の色「%s」が分からない", k, v); } while (0)
        if (!strcmp(k, "show")) {
            if (!strcmp(v, "always")) it->show = HS_ALWAYS; else if (!strcmp(v, "nodata")) it->show = HS_NODATA;
            else if (!strcmp(v, "never")) it->show = HS_NEVER;
            else return hud_err(err, errn, kv->line, "show は always nodata never のどれか（「%s」）", v);
        } else if (!strcmp(k, "box")) {
            if (!hud_nums(v, d, 4)) return hud_err(err, errn, kv->line, "box は「左 上 右 下」の4つの数（「%s」）", v);
            for (int j = 0; j < 4; j++) it->box[j] = d[j];
            it->has_box = 1;
        } else if (!strcmp(k, "box_color")) { COLOR(it->box_c); has_box_c = 1; }
        else if (!strcmp(k, "rect")) {
            if (!hud_nums(v, d, 4)) return hud_err(err, errn, kv->line, "rect は「左 上 右 下」の4つの数（「%s」）", v);
            if (d[2] <= d[0] || d[3] <= d[1]) return hud_err(err, errn, kv->line, "rect は右が左より、下が上より大きい数（「%s」）", v);
            for (int j = 0; j < 4; j++) it->rect[j] = d[j];
        } else if (!strcmp(k, "center")) {
            if (!hud_nums(v, d, 2)) return hud_err(err, errn, kv->line, "center は「x y」の2つの数（「%s」）", v);
            it->x = d[0]; it->y = d[1];
        } else if (!strcmp(k, "x")) NUM(it->x);
        else if (!strcmp(k, "y")) NUM(it->y);
        else if (!strcmp(k, "size")) { NUM(it->size); if (!(it->size > 0)) return hud_err(err, errn, kv->line, "size は0より大きい数"); }
        else if (!strcmp(k, "radius")) { NUM(it->radius); if (!(it->radius > 0)) return hud_err(err, errn, kv->line, "radius は0より大きい数"); }
        else if (!strcmp(k, "full")) { NUM(it->full); if (!(it->full > 0)) return hud_err(err, errn, kv->line, "full は0より大きい数"); }
        else if (!strcmp(k, "dot")) { NUM(it->dot); if (!(it->dot > 0)) return hud_err(err, errn, kv->line, "dot は0より大きい数"); }
        else if (!strcmp(k, "line_width")) { NUM(it->line_width); if (!(it->line_width > 0)) return hud_err(err, errn, kv->line, "line_width は0より大きい数"); }
        else if (!strcmp(k, "tick_width")) { NUM(it->tick_width); if (!(it->tick_width > 0)) return hud_err(err, errn, kv->line, "tick_width は0より大きい数"); }
        else if (!strcmp(k, "width")) { NUM(it->width); if (!(it->width > 0)) return hud_err(err, errn, kv->line, "width は0より大きい数"); }
        else if (!strcmp(k, "tick_length")) { NUM(it->tick_length); if (!(it->tick_length > 0)) return hud_err(err, errn, kv->line, "tick_length は0より大きい数"); }
        else if (!strcmp(k, "label_size")) { NUM(it->label_size); if (!(it->label_size > 0)) return hud_err(err, errn, kv->line, "label_size は0より大きい数"); }
        else if (!strcmp(k, "needle_width")) { NUM(it->needle_width); if (!(it->needle_width > 0)) return hud_err(err, errn, kv->line, "needle_width は0より大きい数"); }
        else if (!strcmp(k, "outline_width")) { NUM(it->outline_width); if (!(it->outline_width > 0)) return hud_err(err, errn, kv->line, "outline_width は0より大きい数"); }
        else if (!strcmp(k, "tick_every")) { NUM(it->tick_every); if (it->tick_every < 0) return hud_err(err, errn, kv->line, "tick_every は0以上（0で目盛り無し）"); }
        else if (!strcmp(k, "minor_every")) { NUM(it->minor_every); if (it->minor_every < 0) return hud_err(err, errn, kv->line, "minor_every は0以上（0で細かい目盛り無し）"); }
        else if (!strcmp(k, "label_every")) { NUM(it->label_every); if (it->label_every < 0) return hud_err(err, errn, kv->line, "label_every は0以上（0で数字無し）"); }
        else if (!strcmp(k, "rings")) {
            if (!hud_num(v, &d[0]) || d[0] != floor(d[0]) || d[0] < 1 || d[0] > 4) return hud_err(err, errn, kv->line, "rings は1〜4の整数（「%s」）", v);
            it->rings = (int)d[0];
        } else if (!strcmp(k, "sweep")) {
            NUM(it->sweep);
            if (it->sweep == 0 || fabs(it->sweep) > 360) return hud_err(err, errn, kv->line, "sweep は0でない-360〜360の数（度）");
        }
        else if (!strcmp(k, "start")) NUM(it->start);
        else if (!strcmp(k, "origin")) NUM(it->origin);
        else if (!strcmp(k, "label_scale")) NUM(it->label_scale);
        else if (!strcmp(k, "rotate")) NUM(it->rotate);
        else if (!strcmp(k, "scale")) NUM(it->scale);
        else if (!strcmp(k, "offset")) NUM(it->offset);
        else if (!strcmp(k, "min")) NUM(it->min);
        else if (!strcmp(k, "max")) NUM(it->max);
        else if (!strcmp(k, "warn_at")) NUM(it->warn_at);
        else if (!strcmp(k, "alarm_at")) NUM(it->alarm_at);
        else if (!strcmp(k, "warn_below")) NUM(it->warn_below);
        else if (!strcmp(k, "alarm_below")) NUM(it->alarm_below);
        else if (!strcmp(k, "decimals")) {
            if (!hud_num(v, &d[0]) || d[0] != floor(d[0]) || d[0] < 0 || d[0] > 6) return hud_err(err, errn, kv->line, "decimals は0〜6の整数（「%s」）", v);
            it->decimals = (int)d[0];
        } else if (!strcmp(k, "flip_x") || !strcmp(k, "flip_y")) {
            if (strcmp(v, "0") && strcmp(v, "1")) return hud_err(err, errn, kv->line, "%s は0か1（「%s」）", k, v);
            if (k[5] == 'x') it->flip_x = *v == '1'; else it->flip_y = *v == '1';
        } else if (!strcmp(k, "align")) {
            if (!strcmp(v, "left")) it->right = 0; else if (!strcmp(v, "right")) it->right = 1; else if (!strcmp(v, "center")) it->right = 2;
            else return hud_err(err, errn, kv->line, "align は left right center のどれか（「%s」）", v);
        } else if (!strcmp(k, "format")) {
            if (!strcmp(v, "number")) it->fmt = HF_NUMBER; else if (!strcmp(v, "laptime")) it->fmt = HF_LAPTIME;
            else if (!strcmp(v, "signed")) it->fmt = HF_SIGNED;
            else return hud_err(err, errn, kv->line, "format は number laptime signed のどれか（「%s」）", v);
        } else if (!strcmp(k, "direction")) {
            if (!strcmp(v, "right")) it->dir = HD_RIGHT; else if (!strcmp(v, "left")) it->dir = HD_LEFT;
            else if (!strcmp(v, "up")) it->dir = HD_UP; else if (!strcmp(v, "down")) it->dir = HD_DOWN;
            else return hud_err(err, errn, kv->line, "direction は right left up down のどれか（「%s」）", v);
        } else if (!strcmp(k, "text") || !strcmp(k, "prefix") || !strcmp(k, "unit")) {
            char *dst = k[0] == 't' ? it->text : k[0] == 'p' ? it->prefix : it->unit;
            if (!hud_str(v, dst)) return hud_err(err, errn, kv->line, "%s は英数字と記号と°（℃）だけ・%d文字まで（日本語は出せない）（「%s」）", k, HUD_STR - 1, v);
        } else if (!strcmp(k, "value") || !strcmp(k, "x_value") || !strcmp(k, "y_value")) {
            if (!hud_refspec(v)) return hud_err(err, errn, kv->line, "%s の値の名前「%s」の形が違う（例：values.RPM、values.Speed|values.GPSSpeed）", k, v);
            if (k[0] == 'y') ref2 = v; else ref1 = v;
        } else if (!strcmp(k, "color")) COLOR(it->color);
        else if (!strcmp(k, "missing_color")) { COLOR(it->missing); has_missing = 1; }
        else if (!strcmp(k, "warn_color")) COLOR(it->warn_c);
        else if (!strcmp(k, "alarm_color")) COLOR(it->alarm_c);
        else if (!strcmp(k, "track_color")) COLOR(it->track_c);
        else if (!strcmp(k, "tick_color")) COLOR(it->tick_c);
        else if (!strcmp(k, "ring_color")) COLOR(it->ring_c);
        else if (!strcmp(k, "cross_color")) COLOR(it->cross_c);
        else if (!strcmp(k, "needle_color")) COLOR(it->needle_c);
        else if (!strcmp(k, "face_color")) COLOR(it->face_c);
        else if (!strcmp(k, "outline_color")) COLOR(it->outline_c);
#undef NUM
#undef COLOR
    }
    // 無いと困るキー
    char need[64]; snprintf(need, sizeof need, "%s", HUD_NEED[type]);
    for (char *w = strtok(need, " "); w; w = strtok(NULL, " "))
        if (!hud_get(s, w)) return hud_err(err, errn, s->line, "[%s]（%s）に %s が無い", s->name, HUD_TYPES[type], w);
    if (has_box_c && !it->has_box) return hud_err(err, errn, hud_get(s, "box_color")->line, "box_color は box と一緒に書く");
    if (!has_missing) memcpy(it->missing, it->color, sizeof it->missing);
    if (type == HT_TEXT && !it->text[0]) return hud_err(err, errn, hud_get(s, "text")->line, "text が空");
    if (type == HT_VALUE) {
        if (it->decimals < 0) it->decimals = it->fmt == HF_LAPTIME ? 2 : 0;
        if (it->fmt == HF_LAPTIME && it->decimals != 1 && it->decimals != 2) return hud_err(err, errn, hud_get(s, "decimals")->line, "format = laptime の decimals は1か2");
    }
    if (type == HT_DIAL && it->decimals < 0) it->decimals = 0;
    if (type == HT_BAR || type == HT_DIAL || type == HT_ARC) {
        if (!(it->max > it->min)) return hud_err(err, errn, hud_get(s, "max")->line, "max は min（既定0）より大きい数");
        if (it->tick_every > 0 && (it->max - it->min) / it->tick_every > 200) return hud_err(err, errn, hud_get(s, "tick_every")->line, "目盛りが多すぎる（200本まで）");
        if (it->minor_every > 0 && (it->max - it->min) / it->minor_every > 200) return hud_err(err, errn, hud_get(s, "minor_every")->line, "細かい目盛りが多すぎる（200本まで）");
    }
    if (type == HT_DIAL) {
        if (isnan(it->label_every)) it->label_every = it->tick_every;
        if (it->label_every > 0 && (it->max - it->min) / it->label_every > 50) return hud_err(err, errn, hud_get(s, "label_every") ? hud_get(s, "label_every")->line : hud_get(s, "tick_every")->line, "目盛りの数字が多すぎる（50個まで）");
    }
    if (ref1 && (it->ref = hud_add_ref(h, ref1)) < 0) return hud_err(err, errn, s->line, "値の名前が多すぎる（%d種類まで）", HUD_REFS);
    if (ref2 && (it->ref2 = hud_add_ref(h, ref2)) < 0) return hud_err(err, errn, s->line, "値の名前が多すぎる（%d種類まで）", HUD_REFS);
    h->n++;
    return 1;
}

// hud.ini の中身（UTF-8）を読む。誤りがあれば0を返し、err に「N行目: …」を入れる
static int hud_parse(const char *src, struct hud *h, char *err, size_t errn) {
    memset(h, 0, sizeof *h);
    h->nodata_after = 1.5;
    struct hud_sec *sec = calloc(HUD_SECS, sizeof *sec);
    struct hud_color uc[HUD_COLORS];
    int ns = 0, nuc = 0, line = 0, ok = 0;
    const char *p = src;
    if (!strncmp(p, "\xEF\xBB\xBF", 3)) p += 3;  // メモ帳が付けることがある印（BOM）
    while (*p) {
        line++;
        const char *e = strchr(p, '\n');
        size_t len = e ? (size_t)(e - p) : strlen(p);
        char buf[HUD_LINE];
        if (len >= sizeof buf) { hud_err(err, errn, line, "1行が長すぎる"); goto out; }
        memcpy(buf, p, len); buf[len] = 0; p += len + (e ? 1 : 0);
        char *s = hud_trim(buf);
        if (!*s || *s == '#' || *s == ';') continue;
        if (*s == '[') {
            char *q = strchr(s, ']');
            if (!q || q[1]) { hud_err(err, errn, line, "[名前] の形になっていない"); goto out; }
            *q = 0; s = hud_trim(s + 1);
            if (strlen(s) >= sizeof sec[0].name || !hud_ident(s, NULL)) { hud_err(err, errn, line, "[%s]：名前は英数字と _ で39文字まで", s); goto out; }
            for (int i = 0; i < ns; i++) if (!strcmp(sec[i].name, s)) { hud_err(err, errn, line, "[%s] が2つある（%d行目にもある）", s, sec[i].line); goto out; }
            if (ns >= HUD_SECS) { hud_err(err, errn, line, "[名前] が多すぎる（%d個まで）", HUD_SECS); goto out; }
            snprintf(sec[ns].name, sizeof sec[ns].name, "%s", s); sec[ns].line = line; ns++;
            continue;
        }
        char *eq = strchr(s, '=');
        if (!eq) { hud_err(err, errn, line, "「キー = 値」の形になっていない（説明の行は頭に # を付ける）"); goto out; }
        if (!ns) { hud_err(err, errn, line, "最初の [名前] より前に書いてある"); goto out; }
        *eq = 0;
        char *k = hud_trim(s), *v = hud_trim(eq + 1);
        struct hud_sec *cs = &sec[ns - 1];
        if (!*k || strlen(k) >= sizeof cs->kv[0].key) { hud_err(err, errn, line, "キーが空か長すぎる"); goto out; }
        if (strlen(v) >= sizeof cs->kv[0].val) { hud_err(err, errn, line, "値が長すぎる（%d文字まで）", HUD_VAL - 1); goto out; }
        if (!*v) { hud_err(err, errn, line, "%s の値が空", k); goto out; }
        const struct hud_kv *dup = hud_get(cs, k);
        if (dup) { hud_err(err, errn, line, "[%s] に %s が2つある（%d行目にもある）", cs->name, k, dup->line); goto out; }
        if (cs->nkv >= HUD_KVS) { hud_err(err, errn, line, "[%s] のキーが多すぎる", cs->name); goto out; }
        struct hud_kv *kv = &cs->kv[cs->nkv++];
        snprintf(kv->key, sizeof kv->key, "%s", k); snprintf(kv->val, sizeof kv->val, "%s", v); kv->line = line;
    }
    // 先に [colors]（どこに書いてあっても、どの計器からも使える）と [hud]
    for (int i = 0; i < ns; i++) {
        if (!strcmp(sec[i].name, "colors")) {
            for (int j = 0; j < sec[i].nkv; j++) {
                const struct hud_kv *kv = &sec[i].kv[j];
                if (!hud_ident(kv->key, NULL)) { hud_err(err, errn, kv->line, "色の名前は英数字と _（「%s」）", kv->key); goto out; }
                if (nuc >= HUD_COLORS) { hud_err(err, errn, kv->line, "色が多すぎる（%d個まで）", HUD_COLORS); goto out; }
                if (!hud_color(kv->val, uc, nuc, uc[nuc].c)) { hud_err(err, errn, kv->line, "色「%s」が分からない", kv->val); goto out; }
                snprintf(uc[nuc].name, sizeof uc[nuc].name, "%s", kv->key); nuc++;
            }
        } else if (!strcmp(sec[i].name, "hud")) {
            for (int j = 0; j < sec[i].nkv; j++) {
                const struct hud_kv *kv = &sec[i].kv[j];
                if (strcmp(kv->key, "nodata_after")) { hud_err(err, errn, kv->line, "[hud] に「%s」は使えない（使えるのは nodata_after）", kv->key); goto out; }
                if (!hud_num(kv->val, &h->nodata_after) || !(h->nodata_after > 0)) { hud_err(err, errn, kv->line, "nodata_after は0より大きい数（秒）"); goto out; }
            }
        }
    }
    for (int i = 0; i < ns; i++) {
        if (!strcmp(sec[i].name, "colors") || !strcmp(sec[i].name, "hud") || !strcmp(sec[i].name, "preview")) continue;  // preview はPCの確認用
        if (!hud_item(h, &sec[i], uc, nuc, err, errn)) goto out;
    }
    ok = 1;
out:
    free(sec);
    return ok;
}

// ---------------------------------------------------------------- 1枚分を組み立てる
static double hud_val(const struct hud_item *it, const double *v, int ref) {
    if (ref < 0) return NAN;
    double x = v[ref];
    return isnan(x) ? x : x * it->scale + it->offset;
}

static const float *hud_pick(const struct hud_item *it, double x) {
    if (isnan(x)) return it->missing;
    if ((!isnan(it->alarm_at) && x >= it->alarm_at) || (!isnan(it->alarm_below) && x < it->alarm_below)) return it->alarm_c;
    if ((!isnan(it->warn_at) && x >= it->warn_at) || (!isnan(it->warn_below) && x < it->warn_below)) return it->warn_c;
    return it->color;
}

static void hud_text(const struct hud_item *it, const char *s, const float *c) {
    text(it->right == 1 ? it->x - text_w(it->size, s) : it->right == 2 ? it->x - text_w(it->size, s) / 2 : it->x, it->y, it->size, c, s);
}

// 針のメーター・弧のゲージで、値 x の角度（度。min〜max の外は端に止める）
static double hud_angle(const struct hud_item *it, double x) {
    return it->start + it->sweep * fmin(fmax((x - it->min) / (it->max - it->min), 0), 1);
}

// コース図：線を緯度・経度から平面へ直し（北が上、rotate 度だけ時計回りに回す）、rect の中へ縦横比を保って収める
static void hud_map(const struct hud_item *it, const struct hud_track *trk, double lat, double lon) {
    if (!trk || trk->n < 2) return;
    double la0 = trk->lat[0], la1 = la0, lo0 = trk->lon[0], lo1 = lo0;
    for (int i = 1; i < trk->n; i++) {
        la0 = fmin(la0, trk->lat[i]); la1 = fmax(la1, trk->lat[i]); lo0 = fmin(lo0, trk->lon[i]); lo1 = fmax(lo1, trk->lon[i]);
    }
    const double lac = (la0 + la1) / 2, loc = (lo0 + lo1) / 2, k = cos(lac * M_PI / 180);
    // 線の広がりが HUD_MAP_MIN_M 未満なら描かない（止まっている車のGNSSのぶれを、図いっぱいに広げて描かない）
    if (fmax((la1 - la0) * 111320.0, (lo1 - lo0) * 111320.0 * k) < HUD_MAP_MIN_M) return;
    const double cr = cos(it->rotate * M_PI / 180), sr = sin(it->rotate * M_PI / 180);
    static double px[HUD_TRACK_MAX], py[HUD_TRACK_MAX];
    double x0 = 0, x1 = 0, y0 = 0, y1 = 0;
    for (int i = 0; i < trk->n; i++) {
        double X = (trk->lon[i] - loc) * k, Y = -(trk->lat[i] - lac);
        px[i] = X * cr - Y * sr; py[i] = X * sr + Y * cr;
        if (!i || px[i] < x0) x0 = px[i];
        if (!i || px[i] > x1) x1 = px[i];
        if (!i || py[i] < y0) y0 = py[i];
        if (!i || py[i] > y1) y1 = py[i];
    }
    const float *r = it->rect;
    const double lw = it->line_width + 2 * it->outline_width, m = fmax(it->dot, lw) / 2 + 2;
    const double aw = r[2] - r[0] - 2 * m, ah = r[3] - r[1] - 2 * m;
    if (aw <= 0 || ah <= 0 || (x1 <= x0 && y1 <= y0)) return;
    const double s = fmin(x1 > x0 ? aw / (x1 - x0) : INFINITY, y1 > y0 ? ah / (y1 - y0) : INFINITY);
    const double ox = (r[0] + r[2]) / 2.0 - s * (x0 + x1) / 2, oy = (r[1] + r[3]) / 2.0 - s * (y0 + y1) / 2;
    if (it->outline_width > 0)
        for (int i = 0; i + 1 < trk->n; i++) seg(ox + s * px[i], oy + s * py[i], ox + s * px[i + 1], oy + s * py[i + 1], lw, it->outline_c);
    for (int i = 0; i + 1 < trk->n; i++) seg(ox + s * px[i], oy + s * py[i], ox + s * px[i + 1], oy + s * py[i + 1], it->line_width, it->track_c);
    if (!isnan(lat) && !isnan(lon)) {
        double X = (lon - loc) * k, Y = -(lat - lac);
        band_n(ox + s * (X * cr - Y * sr), oy + s * (X * sr + Y * cr), 0, it->dot / 2, 0, 360, 16, it->color);
    }
}

// v：値（h->ref の順、無ければNAN）。vs：針のメーター・弧・棒・Gボールに使う値（コマの時刻で補間したもの、tele_smooth.h。NULLなら v）。
// utc_ok・utc：時刻。age：最後に数値を受け取ってからの秒。trk：コース図の線（無ければNULL）
static void hud_draw(const struct hud *h, const double *v, const double *vs, int utc_ok, time_t utc, double age, const struct hud_track *trk) {
    char b[3 * HUD_STR + 32];
    if (!vs) vs = v;
    const int nodata = age > h->nodata_after;
    for (int i = 0; i < h->n; i++) {
        const struct hud_item *it = &h->it[i];
        if (it->show == HS_NEVER || (it->show == HS_NODATA && !nodata) || (it->type == HT_CLOCK && !utc_ok)) continue;
        if (it->has_box) rect(it->box[0], it->box[1], it->box[2], it->box[3], it->box_c);
        const float *r = it->rect;
        switch (it->type) {
        case HT_BOX: rect(r[0], r[1], r[2], r[3], it->color); break;
        case HT_TEXT: hud_text(it, it->text, it->color); break;
        case HT_VALUE: {
            double x = hud_val(it, v, it->ref);
            if (it->fmt == HF_LAPTIME) {
                char t[32]; fmt_laptime(t, sizeof t, x, it->decimals);
                snprintf(b, sizeof b, "%s%s%s", it->prefix, t, isnan(x) || x < 0 ? "" : it->unit);
            } else if (isnan(x)) snprintf(b, sizeof b, "%s--", it->prefix);
            else if (it->fmt == HF_SIGNED) snprintf(b, sizeof b, "%s%+.*f%s", it->prefix, it->decimals, x, it->unit);
            else snprintf(b, sizeof b, "%s%.*f%s", it->prefix, it->decimals, x, it->unit);
            hud_text(it, b, hud_pick(it, x));
            break;
        }
        case HT_BAR: {
            const float w = r[2] - r[0], hh = r[3] - r[1];
            rect(r[0], r[1], r[2], r[3], it->track_c);
            double x = hud_val(it, vs, it->ref);
            if (!isnan(x) && !isnan(it->origin)) {  // origin から値まで（値が origin より小さければ逆向きに伸びる）
                double f0 = fmin(fmax((it->origin - it->min) / (it->max - it->min), 0), 1);
                double f1 = fmin(fmax((x - it->min) / (it->max - it->min), 0), 1), lo = fmin(f0, f1), hi = fmax(f0, f1);
                const float *c = hud_pick(it, x);
                if (hi > lo) {
                    if (it->dir == HD_RIGHT) rect(r[0] + w * lo, r[1], r[0] + w * hi, r[3], c);
                    else if (it->dir == HD_LEFT) rect(r[2] - w * hi, r[1], r[2] - w * lo, r[3], c);
                    else if (it->dir == HD_UP) rect(r[0], r[3] - hh * hi, r[2], r[3] - hh * lo, c);
                    else rect(r[0], r[1] + hh * lo, r[2], r[1] + hh * hi, c);
                }
            } else if (!isnan(x)) {
                double f = fmin(fmax((x - it->min) / (it->max - it->min), 0), 1);
                const float *c = hud_pick(it, x);
                if (it->dir == HD_RIGHT) rect(r[0], r[1], r[0] + w * f, r[3], c);
                else if (it->dir == HD_LEFT) rect(r[2] - w * f, r[1], r[2], r[3], c);
                else if (it->dir == HD_UP) rect(r[0], r[3] - hh * f, r[2], r[3], c);
                else rect(r[0], r[1], r[2], r[1] + hh * f, c);
            }
            for (int k = 1; it->tick_every > 0; k++) {
                double tv = it->min + k * it->tick_every;
                if (tv >= it->max - 1e-9 * (it->max - it->min)) break;
                double f = (tv - it->min) / (it->max - it->min);
                if (it->dir == HD_RIGHT || it->dir == HD_LEFT) {
                    float tx = it->dir == HD_RIGHT ? r[0] + w * f : r[2] - w * f;
                    seg(tx, r[1], tx, r[3], it->tick_width, it->tick_c);
                } else {
                    float ty = it->dir == HD_UP ? r[3] - hh * f : r[1] + hh * f;
                    seg(r[0], ty, r[2], ty, it->tick_width, it->tick_c);
                }
            }
            break;
        }
        case HT_GBALL: {  // 外周＝full（G）。flipが無ければ、x_valueは右が正、y_valueは下が正
            const float cx = it->x, cy = it->y, rr = it->radius, lw = it->line_width;
            for (int j = 1; j <= it->rings; j++) {  // 外周（rings が2以上なら、内側にも等間隔の輪）
                const float ri = rr * j / it->rings;
                for (int k = 0; k < 48; k++) {
                    float a0 = k * 2 * M_PI / 48, a1 = (k + 1) * 2 * M_PI / 48;
                    seg(cx + ri * cosf(a0), cy + ri * sinf(a0), cx + ri * cosf(a1), cy + ri * sinf(a1), lw, it->ring_c);
                }
            }
            seg(cx - rr, cy, cx + rr, cy, lw, it->cross_c); seg(cx, cy - rr, cx, cy + rr, lw, it->cross_c);
            double gx = hud_val(it, vs, it->ref), gy = hud_val(it, vs, it->ref2);
            if (!isnan(gx) && !isnan(gy)) {
                if (it->flip_x) gx = -gx;
                if (it->flip_y) gy = -gy;
                float px = cx + rr * fmax(fmin(gx / it->full, 1), -1), py = cy + rr * fmax(fmin(gy / it->full, 1), -1), d = it->dot / 2;
                rect(px - d, py - d, px + d, py + d, it->color);
            }
            break;
        }
        case HT_CLOCK: {  // 日本時間（TZ=Asia/Tokyo）
            struct tm lt; time_t u = utc; localtime_r(&u, &lt);
            snprintf(b, sizeof b, "%02d:%02d:%02d", lt.tm_hour, lt.tm_min, lt.tm_sec);
            hud_text(it, b, it->color);
            break;
        }
        case HT_DIAL: {  // 針のメーター：盤 → 外周の線 → 黄・赤の帯 → 目盛り → 数字 → 針
            const float cx = it->x, cy = it->y, rr = it->radius;
            const double tl = isnan(it->tick_length) ? rr * .12 : it->tick_length, span = it->max - it->min;
            const double a0 = it->start, a1 = it->start + it->sweep;
            if (it->face_c[3] > 0) band(cx, cy, 0, rr, 0, 360, it->face_c);
            if (it->line_width > 0) band(cx, cy, rr - it->line_width, rr, a0, a1, it->ring_c);
            if (!isnan(it->warn_at) && it->warn_at < it->max)
                band(cx, cy, rr - tl * .45, rr, hud_angle(it, it->warn_at), hud_angle(it, isnan(it->alarm_at) ? it->max : fmax(it->alarm_at, it->warn_at)), it->warn_c);
            if (!isnan(it->alarm_at) && it->alarm_at < it->max) band(cx, cy, rr - tl * .45, rr, hud_angle(it, it->alarm_at), a1, it->alarm_c);
            for (int k = 0; it->minor_every > 0; k++) {
                double tv = it->min + k * it->minor_every;
                if (tv > it->max + 1e-9 * span) break;
                if (it->tick_every > 0 && fabs(remainder(tv - it->min, it->tick_every)) < 1e-6 * span) continue;
                float xa, ya, xb, yb; double a = hud_angle(it, tv);
                polar(cx, cy, rr, a, &xa, &ya); polar(cx, cy, rr - tl * .55, a, &xb, &yb);
                seg(xa, ya, xb, yb, it->tick_width * .6f, it->color);
            }
            for (int k = 0; it->tick_every > 0; k++) {
                double tv = it->min + k * it->tick_every;
                if (tv > it->max + 1e-9 * span) break;
                float xa, ya, xb, yb; double a = hud_angle(it, tv);
                polar(cx, cy, rr, a, &xa, &ya); polar(cx, cy, rr - tl, a, &xb, &yb);
                seg(xa, ya, xb, yb, it->tick_width, it->color);
            }
            for (int k = 0; it->label_every > 0; k++) {  // 数字の箱の外側の端が、目盛りの内側から4ピクセル内に来るように置く
                double tv = it->min + k * it->label_every;
                if (tv > it->max + 1e-9 * span) break;
                snprintf(b, sizeof b, "%.*f", it->decimals, tv * it->label_scale);
                double a = hud_angle(it, tv) * M_PI / 180, w = text_w(it->label_size, b), lh = cell_h * it->label_size;
                double rl = rr - tl - 4 - .5 * (fabs(sin(a)) * w + fabs(cos(a)) * lh);
                text(cx + rl * sin(a) - w / 2, cy - rl * cos(a) - lh / 2, it->label_size, it->color, b);
            }
            double x = hud_val(it, vs, it->ref);
            if (!isnan(x)) {
                float xt, yt; polar(cx, cy, rr - tl * .2, hud_angle(it, x), &xt, &yt);
                seg(cx, cy, xt, yt, it->needle_width, it->needle_c);
                rect(cx - it->needle_width, cy - it->needle_width, cx + it->needle_width, cy + it->needle_width, it->needle_c);
            }
            break;
        }
        case HT_ARC: {  // 弧のゲージ：地の帯 → 値までの帯 → 区切り
            const float cx = it->x, cy = it->y, rr = it->radius;
            const double r0 = fmax(rr - it->width, 0), span = it->max - it->min;
            band(cx, cy, r0, rr, it->start, it->start + it->sweep, it->track_c);
            double x = hud_val(it, vs, it->ref);
            if (!isnan(x)) band(cx, cy, r0, rr, it->start, hud_angle(it, x), hud_pick(it, x));
            for (int k = 1; it->tick_every > 0; k++) {
                double tv = it->min + k * it->tick_every;
                if (tv >= it->max - 1e-9 * span) break;
                float xa, ya, xb, yb; double a = hud_angle(it, tv);
                polar(cx, cy, rr, a, &xa, &ya); polar(cx, cy, r0, a, &xb, &yb);
                seg(xa, ya, xb, yb, it->tick_width, it->tick_c);
            }
            break;
        }
        case HT_MAP: hud_map(it, trk, hud_val(it, v, it->ref), hud_val(it, v, it->ref2)); break;
        }
    }
}

// 机の上で見た目と警告の色を確かめるための作り物の値（OVERLAY_DEMO=1）。値の名前（最初の候補の . の後ろ）で決める
static double hud_demo(const char *ref, double ph) {
    char k[HUD_REF_LEN]; snprintf(k, sizeof k, "%s", ref);
    k[strcspn(k, "|")] = 0;
    const char *n = strchr(k, '.') ? strchr(k, '.') + 1 : k;
    if (!strcmp(n, "Speed") || !strcmp(n, "GPSSpeed")) return 90 + 70 * sin(ph * .4);
    if (!strcmp(n, "RPM")) return 4500 + 3400 * sin(ph * .9);
    if (!strcmp(n, "WaterTemp")) return 98 + 14 * sin(ph * .15);
    if (!strcmp(n, "OilTemp")) return 108 + 14 * sin(ph * .15);
    if (!strcmp(n, "LatAccel")) return 1.1 * sin(ph * .7);
    if (!strcmp(n, "LongAccel")) return .8 * cos(ph * .7);
    if (!strcmp(n, "CurrentLap")) return 3;
    if (!strcmp(n, "ElapsedTime")) return fmod(ph, 95) / 60;
    if (!strcmp(n, "LapTime")) return 96.37 / 60;
    if (!strcmp(n, "BestLap")) return 94.85 / 60;
    return 50 + 50 * sin(ph * .3);
}
