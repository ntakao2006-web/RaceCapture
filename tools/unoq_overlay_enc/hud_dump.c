// hud_dump.c：hud.ini と値から、1枚分の計器の頂点を書き出す（GLは使わない）。
//   PCの見た目の確認（tools/video_hud/hud_layout.py）が本体と同じ形を組み立てているかの突き合わせ用。
//   突き合わせの元の数字 tools/video_hud/testdata/*.golden はこれで作る（手順書5-14）
// ビルド: gcc -O2 -o hud_dump hud_dump.c -lm（hud_layout.h を同じ場所に置く）
// 実行:   ./hud_dump <hud.ini> <hud_font_64.pgm> <state.txt>
//   state.txt は1行に「名前 = 値」。名前は値の名前（values.RPM 等。| でつないだものは前から順に探す）か、
//   utc（UNIX秒。書かなければ時刻は出さない）・age（最後に数値を受け取ってからの秒。既定0）。書いていない値は無し（NAN）
// 出力：1行目に「quads 四角形の数」、続けて1行に1頂点「x y u v r g b a」。設定の誤りは標準エラーへ出して終了コード2
#define _GNU_SOURCE
#include "hud_layout.h"

static char *slurp(const char *path) {
    FILE *f = fopen(path, "rb"); if (!f) { perror(path); exit(1); }
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *s = calloc(1, n + 1);
    if (fread(s, 1, n, f) != (size_t)n) { perror(path); exit(1); }
    fclose(f);
    return s;
}

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage: %s <hud.ini> <hud_font_64.pgm> <state.txt>\n", argv[0]); return 1; }
    setenv("TZ", "Asia/Tokyo", 1); tzset();

    FILE *f = fopen(argv[2], "rb"); if (!f) { perror(argv[2]); return 1; }
    char line[512];
    while (fgets(line, sizeof line, f)) {
        if (line[0] == '#') { sscanf(line, "# atlas %d %d %d %d %d", &cell_w, &cell_h, &first_ch, &n_ch, &atlas_cols); continue; }
        if (line[0] != 'P') { sscanf(line, "%d %d", &atlas_w, &atlas_h); break; }
    }
    fclose(f);
    if (!cell_w || !atlas_w) { fprintf(stderr, "%s: header\n", argv[2]); return 1; }

    char *src = slurp(argv[1]);
    struct hud *h = malloc(sizeof *h);
    char err[600];
    if (!hud_parse(src, h, err, sizeof err)) { fprintf(stderr, "%s\n", err); return 2; }

    static char names[256][HUD_REF_LEN]; double vals[256]; int nn = 0;
    time_t utc = 0; int utc_ok = 0; double age = 0;
    char *st = slurp(argv[3]);
    for (char *l = strtok(st, "\n"); l; l = strtok(NULL, "\n")) {
        char *eq = strchr(l, '='); if (!eq || l[0] == '#') continue;
        *eq = 0;
        char *k = hud_trim(l), *v = hud_trim(eq + 1);
        if (!strcmp(k, "utc")) { utc = (time_t)atoll(v); utc_ok = 1; }
        else if (!strcmp(k, "age")) age = atof(v);
        else if (nn < 256) { snprintf(names[nn], HUD_REF_LEN, "%s", k); vals[nn++] = atof(v); }
    }
    double v[HUD_REFS];
    for (int i = 0; i < h->nref; i++) {
        v[i] = NAN;
        char b[HUD_REF_LEN]; snprintf(b, sizeof b, "%s", h->ref[i]);
        for (char *p = b, *a; isnan(v[i]) && (a = strsep(&p, "|"));)
            for (int j = 0; j < nn; j++) if (!strcmp(names[j], a)) { v[i] = vals[j]; break; }
    }

    (void)hud_demo;  // 本体のDEMO用。ここでは使わない
    hn = 0;
    hud_draw(h, v, utc_ok, utc, age);
    printf("quads %d\n", hn / 6);
    for (int i = 0; i < hn; i++) {
        const float *p = hv + 8 * i;
        printf("%.4f %.4f %.6f %.6f %.4f %.4f %.4f %.4f\n", p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7]);
    }
    return 0;
}
