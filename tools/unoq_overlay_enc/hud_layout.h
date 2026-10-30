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

static void fmt_laptime(char *b, size_t n, double minutes, int decimals) {
    if (isnan(minutes) || minutes < 0) { snprintf(b, n, decimals == 1 ? "-:--.-" : "-:--.--"); return; }
    double sec = minutes * 60; int m = (int)(sec / 60); double s = sec - m * 60;
    if (decimals == 1) snprintf(b, n, "%d:%04.1f", m, s); else snprintf(b, n, "%d:%05.2f", m, s);
}

static const float WHITE[4] = { .95f, .97f, 1, 1 }, GREY[4] = { .65f, .7f, .75f, 1 }, DIM[4] = { .55f, .6f, .65f, 1 };
static const float YELLOW[4] = { 1, .8f, 0, 1 }, RED[4] = { 1, .2f, .15f, 1 }, GREEN[4] = { .25f, .9f, .35f, 1 };
static const float PANEL[4] = { 0, 0, 0, .55f }, TRACK[4] = { .2f, .2f, .22f, .7f }, BLACK[4] = { 0, 0, 0, 1 };

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

enum { HT_BOX, HT_TEXT, HT_VALUE, HT_BAR, HT_GBALL, HT_CLOCK };
enum { HS_ALWAYS, HS_NODATA, HS_NEVER };
enum { HD_RIGHT, HD_LEFT, HD_UP, HD_DOWN };

struct hud_item {
    int type, show, right, laptime, decimals, dir, flip_x, flip_y, has_box;
    int ref, ref2;  // 値の番号（hud.ref の添字）。無ければ-1
    float x, y, size, rect[4], box[4], tick_width, radius, line_width, dot;
    float color[4], missing[4], warn_c[4], alarm_c[4], box_c[4], track_c[4], tick_c[4], ring_c[4], cross_c[4];
    double warn_at, alarm_at, warn_below, alarm_below, scale, offset, min, max, tick_every, full;
    char text[HUD_STR], prefix[HUD_STR], unit[HUD_STR];
};
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
static const char *HUD_TYPES[] = { "box", "text", "value", "bar", "gball", "clock" };
static const char *HUD_KEYS[] = {
    "rect color",
    "x y size color align text",
    "x y size color align value scale offset decimals prefix unit format missing_color"
    " warn_at alarm_at warn_below alarm_below warn_color alarm_color",
    "rect value scale offset min max direction color warn_at alarm_at warn_below alarm_below warn_color alarm_color"
    " track_color tick_every tick_color tick_width",
    "center radius full x_value y_value flip_x flip_y ring_color cross_color color dot line_width",
    "x y size color align",
};
static const char *HUD_NEED[] = { "rect", "x y text", "x y value", "rect value max", "center radius", "x y" };

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

// 文字（"…" で囲んでもよい）。一覧表にある文字（英数字と記号）だけ
static int hud_str(const char *s, char out[HUD_STR]) {
    size_t n = strlen(s);
    if (n >= 2 && s[0] == '"' && s[n - 1] == '"') { s++; n -= 2; }
    if (n >= HUD_STR) return 0;
    for (size_t i = 0; i < n; i++) if ((unsigned char)s[i] < 32 || (unsigned char)s[i] > 126) return 0;
    memcpy(out, s, n); out[n] = 0;
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
    if (!tk) return hud_err(err, errn, s->line, "[%s] に type が無い（box text value bar gball clock のどれか）", s->name);
    int type = -1;
    for (int i = 0; i < 6; i++) if (!strcmp(tk->val, HUD_TYPES[i])) type = i;
    if (type < 0) return hud_err(err, errn, tk->line, "type「%s」は無い（box text value bar gball clock のどれか）", tk->val);
    if (h->n >= HUD_ITEMS) return hud_err(err, errn, s->line, "計器が多すぎる（%d個まで）", HUD_ITEMS);
    struct hud_item *it = &h->it[h->n];
    memset(it, 0, sizeof *it);
    it->type = type; it->ref = it->ref2 = -1; it->size = 1; it->scale = 1; it->max = NAN;
    it->warn_at = it->alarm_at = it->warn_below = it->alarm_below = NAN;
    it->decimals = -1; it->full = 1.5; it->dot = 18; it->line_width = 3; it->tick_width = 3;
    memcpy(it->color, type == HT_BAR ? GREEN : type == HT_GBALL ? YELLOW : WHITE, sizeof it->color);
    memcpy(it->warn_c, YELLOW, sizeof it->warn_c); memcpy(it->alarm_c, RED, sizeof it->alarm_c);
    memcpy(it->box_c, PANEL, sizeof it->box_c); memcpy(it->track_c, TRACK, sizeof it->track_c);
    memcpy(it->tick_c, PANEL, sizeof it->tick_c); memcpy(it->ring_c, GREY, sizeof it->ring_c); memcpy(it->cross_c, DIM, sizeof it->cross_c);
    int has_missing = 0, has_box_c = 0;
    const char *ref1 = type == HT_GBALL ? "values.LatAccel" : NULL, *ref2 = type == HT_GBALL ? "values.LongAccel" : NULL;

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
        else if (!strcmp(k, "tick_every")) { NUM(it->tick_every); if (it->tick_every < 0) return hud_err(err, errn, kv->line, "tick_every は0以上（0で目盛り無し）"); }
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
            if (!strcmp(v, "left")) it->right = 0; else if (!strcmp(v, "right")) it->right = 1;
            else return hud_err(err, errn, kv->line, "align は left か right（「%s」）", v);
        } else if (!strcmp(k, "format")) {
            if (!strcmp(v, "number")) it->laptime = 0; else if (!strcmp(v, "laptime")) it->laptime = 1;
            else return hud_err(err, errn, kv->line, "format は number か laptime（「%s」）", v);
        } else if (!strcmp(k, "direction")) {
            if (!strcmp(v, "right")) it->dir = HD_RIGHT; else if (!strcmp(v, "left")) it->dir = HD_LEFT;
            else if (!strcmp(v, "up")) it->dir = HD_UP; else if (!strcmp(v, "down")) it->dir = HD_DOWN;
            else return hud_err(err, errn, kv->line, "direction は right left up down のどれか（「%s」）", v);
        } else if (!strcmp(k, "text") || !strcmp(k, "prefix") || !strcmp(k, "unit")) {
            char *dst = k[0] == 't' ? it->text : k[0] == 'p' ? it->prefix : it->unit;
            if (!hud_str(v, dst)) return hud_err(err, errn, kv->line, "%s は英数字と記号だけ・%d文字まで（日本語は出せない）（「%s」）", k, HUD_STR - 1, v);
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
        if (it->decimals < 0) it->decimals = it->laptime ? 2 : 0;
        if (it->laptime && it->decimals != 1 && it->decimals != 2) return hud_err(err, errn, hud_get(s, "decimals")->line, "format = laptime の decimals は1か2");
    }
    if (type == HT_BAR) {
        if (!(it->max > it->min)) return hud_err(err, errn, hud_get(s, "max")->line, "max は min（既定0）より大きい数");
        if (it->tick_every > 0 && (it->max - it->min) / it->tick_every > 200) return hud_err(err, errn, hud_get(s, "tick_every")->line, "目盛りが多すぎる（200本まで）");
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
    text(it->right ? it->x - text_w(it->size, s) : it->x, it->y, it->size, c, s);
}

// v：値（h->ref の順、無ければNAN）。utc_ok・utc：時刻。age：最後に数値を受け取ってからの秒
static void hud_draw(const struct hud *h, const double *v, int utc_ok, time_t utc, double age) {
    char b[3 * HUD_STR + 32];
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
            if (it->laptime) {
                char t[32]; fmt_laptime(t, sizeof t, x, it->decimals);
                snprintf(b, sizeof b, "%s%s%s", it->prefix, t, isnan(x) || x < 0 ? "" : it->unit);
            } else if (isnan(x)) snprintf(b, sizeof b, "%s--", it->prefix);
            else snprintf(b, sizeof b, "%s%.*f%s", it->prefix, it->decimals, x, it->unit);
            hud_text(it, b, hud_pick(it, x));
            break;
        }
        case HT_BAR: {
            const float w = r[2] - r[0], hh = r[3] - r[1];
            rect(r[0], r[1], r[2], r[3], it->track_c);
            double x = hud_val(it, v, it->ref);
            if (!isnan(x)) {
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
            for (int k = 0; k < 48; k++) {
                float a0 = k * 2 * M_PI / 48, a1 = (k + 1) * 2 * M_PI / 48;
                seg(cx + rr * cosf(a0), cy + rr * sinf(a0), cx + rr * cosf(a1), cy + rr * sinf(a1), lw, it->ring_c);
            }
            seg(cx - rr, cy, cx + rr, cy, lw, it->cross_c); seg(cx, cy - rr, cx, cy + rr, lw, it->cross_c);
            double gx = hud_val(it, v, it->ref), gy = hud_val(it, v, it->ref2);
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
