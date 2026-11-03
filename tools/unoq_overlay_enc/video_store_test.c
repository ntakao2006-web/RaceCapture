// video_store_test.c：video_store.h（空きが足りないときに消す動画とその順番）を testdata/video_store/ の場面で確かめる。
//   同じ場面を EcoCapture-Web/test_video_store.py でも確かめ、録画とEcoCaptureが同じ順に消すことを見る（手順書5-17）
// ビルド・実行（WSLか本体）: gcc -O2 -Wall -o video_store_test video_store_test.c -lm && ./video_store_test testdata/video_store
//   場面のファイル（1行に1つ。#から後は説明）：
//     boot <起動の番号>  now <起動からの秒>  recording <鍵=値 …>（.recording へ1行ずつ）
//     file <名前> <大きさ> <更新時刻(秒)>（中身はx）  ok <章> <印に書く大きさ>  keep <走行>
//     expect <消す順の章 …>  bytes <消してよい大きさの合計>
//     delete <数>（その数だけ消す順の先頭を消す）  left <残ったファイル …（deleted.log以外、名前の順）>  logged <deleted.logの行数>
#include <sys/time.h>
#include "video_store.h"

static int fails;
#define CHECK(cond, ...) do { if (!(cond)) { fails++; printf("NG %s: ", name); printf(__VA_ARGS__); printf("\n"); } } while (0)

static double no_space(void) { return 0; }

static int cmp_str(const void *a, const void *b) { return strcmp(*(char *const *)a, *(char *const *)b); }

// 空白で区切った語を並べ直した文字列（比べる用）
static void join_dir(const char *dir, char *out, size_t n) {
    char *names[512]; int k = 0; DIR *d = opendir(dir); struct dirent *e;
    while (d && (e = readdir(d)) && k < 512)
        if (strcmp(e->d_name, ".") && strcmp(e->d_name, "..") && strcmp(e->d_name, VS_LOG)) names[k++] = strdup(e->d_name);
    if (d) closedir(d);
    qsort(names, k, sizeof *names, cmp_str);
    out[0] = 0;
    for (int i = 0; i < k; i++) { if (i) strncat(out, " ", n - strlen(out) - 1); strncat(out, names[i], n - strlen(out) - 1); free(names[i]); }
}

static void run(const char *path, const char *name) {
    FILE *f = fopen(path, "r"); if (!f) { printf("NG %s: 開けない\n", name); fails++; return; }
    char dir[] = "/tmp/vs_test_XXXXXX"; if (!mkdtemp(dir)) { perror("mkdtemp"); exit(1); }
    char boot[64] = "", line[2048], p[1024]; double now_bt = 0;
    while (fgets(line, sizeof line, f)) {
        char *hash = strchr(line, '#'); if (hash) *hash = 0;
        vs_trim(line); if (!line[0]) continue;
        char cmd[32] = ""; int off = 0; sscanf(line, "%31s%n", cmd, &off);
        char *rest = line + off; while (*rest == ' ') rest++;
        if (!strcmp(cmd, "boot")) snprintf(boot, sizeof boot, "%s", rest);
        else if (!strcmp(cmd, "now")) now_bt = atof(rest);
        else if (!strcmp(cmd, "recording")) {
            snprintf(p, sizeof p, "%s/.recording", dir); FILE *o = fopen(p, "w");
            for (char *t = strtok(rest, " "); t; t = strtok(NULL, " ")) fprintf(o, "%s\n", t);
            fclose(o);
        } else if (!strcmp(cmd, "file")) {
            char fn[256]; long long size; long long mt;
            sscanf(rest, "%255s %lld %lld", fn, &size, &mt);
            snprintf(p, sizeof p, "%s/%s", dir, fn); FILE *o = fopen(p, "w");
            for (long long i = 0; i < size; i++) fputc('x', o);
            fclose(o);
            struct timeval tv[2] = { { mt, 0 }, { mt, 0 } }; utimes(p, tv);
        } else if (!strcmp(cmd, "ok")) {
            char fn[256]; long long size; sscanf(rest, "%255s %lld", fn, &size);
            snprintf(p, sizeof p, "%s/%s.ok", dir, fn); FILE *o = fopen(p, "w");
            fprintf(o, "%lld 0000000000000000000000000000000000000000000000000000000000000000 2026-11-08T00:00:00Z\n", size); fclose(o);
        } else if (!strcmp(cmd, "keep")) {
            snprintf(p, sizeof p, "%s/%s.keep", dir, rest); FILE *o = fopen(p, "w"); fclose(o);
        } else if (!strcmp(cmd, "expect") || !strcmp(cmd, "bytes")) {
            struct vs_store s; vs_scan(dir, boot, now_bt, &s);
            int *idx = malloc((s.n ? s.n : 1) * sizeof *idx), k = vs_order(&s, idx);
            if (!strcmp(cmd, "expect")) {
                char got[4096] = "";
                for (int i = 0; i < k; i++) { if (i) strcat(got, " "); strcat(got, s.ch[idx[i]].name); }
                CHECK(!strcmp(got, rest), "消す順 「%s」（正解「%s」）", got, rest);
            } else CHECK(vs_deletable(&s) == atoll(rest), "消してよい大きさ %lld（正解 %s）", vs_deletable(&s), rest);
            free(idx); vs_free(&s);
        } else if (!strcmp(cmd, "delete")) {
            for (int i = 0; i < atoi(rest); i++) {
                struct vs_store s; vs_scan(dir, boot, now_bt, &s);
                int *idx = malloc((s.n ? s.n : 1) * sizeof *idx), k = vs_order(&s, idx);
                if (k) vs_delete(dir, &s.ch[idx[0]], "test", boot);
                free(idx); vs_free(&s);
            }
        } else if (!strcmp(cmd, "left")) {
            char got[8192]; join_dir(dir, got, sizeof got);
            CHECK(!strcmp(got, rest), "残ったファイル 「%s」（正解「%s」）", got, rest);
        } else if (!strcmp(cmd, "logged")) {
            snprintf(p, sizeof p, "%s/" VS_LOG, dir); FILE *o = fopen(p, "r"); int lines = 0, ch;
            if (o) { while ((ch = fgetc(o)) != EOF) lines += ch == '\n'; fclose(o); }
            CHECK(lines == atoi(rest), "消した記録 %d 行（正解 %s）", lines, rest);
        } else { printf("NG %s: 知らない行 %s\n", name, cmd); fails++; }
    }
    fclose(f);
    char cmdline[1100]; snprintf(cmdline, sizeof cmdline, "rm -rf '%s'", dir); if (system(cmdline)) {}
}

int main(int argc, char **argv) {
    const char *dir = argc > 1 ? argv[1] : "testdata/video_store";
    DIR *d = opendir(dir); if (!d) { perror(dir); return 1; }
    char *names[256]; int k = 0; struct dirent *e;
    while ((e = readdir(d)) && k < 256) { size_t l = strlen(e->d_name); if (l > 4 && !strcmp(e->d_name + l - 4, ".txt")) names[k++] = strdup(e->d_name); }
    closedir(d);
    qsort(names, k, sizeof *names, cmp_str);
    for (int i = 0; i < k; i++) { char p[1024]; snprintf(p, sizeof p, "%s/%s", dir, names[i]); run(p, names[i]); free(names[i]); }
    // 走行の名前の読み方
    const char *name = "名前";
    char s[256]; int n;
    vs_session_of("20261108_130205_03.ts", s, sizeof s, &n); CHECK(!strcmp(s, "20261108_130205") && n == 3, "章 %s %d", s, n);
    vs_session_of("20261108_130205_1234.ts", s, sizeof s, &n); CHECK(!strcmp(s, "20261108_130205") && n == 1234, "4桁 %s %d", s, n);
    vs_session_of("20261108_130205_1.ts", s, sizeof s, &n); CHECK(!strcmp(s, "20261108_130205_1") && n == 0, "1桁 %s %d", s, n);
    vs_session_of("20261030_211950.ts", s, sizeof s, &n); CHECK(!strcmp(s, "20261030_211950") && n == 0, "前の形 %s %d", s, n);
    // 空きが足りなくなったときの消し方（録画が使う形）：今の走行は消さずに止める
    char dir2[] = "/tmp/vs_room_XXXXXX"; if (!mkdtemp(dir2)) return 1;
    char boot[64]; vs_boot_id(boot, sizeof boot); CHECK(strlen(boot) == 36, "起動の番号 %s", boot);
    const double bt = vs_boottime();
    const char *files[] = { "20261108_090000_01.ts", "20261108_090000_02.ts", "20261108_130205_01.ts" };
    for (int i = 0; i < 3; i++) {
        char p[1024]; snprintf(p, sizeof p, "%s/%s", dir2, files[i]); FILE *o = fopen(p, "w"); fputs("xxxxxxxxxx", o); fclose(o);
        struct timeval tv[2] = { { 10 + i, 0 }, { 10 + i, 0 } }; utimes(p, tv);
    }
    { char p[1024]; snprintf(p, sizeof p, "%s/.recording", dir2); FILE *o = fopen(p, "w");
      fprintf(o, "boot_id=%s\nsession=20261108_130205\nfile=20261108_130205_01.ts\nbt=%.3f\n", boot, bt); fclose(o); }
    int removed = vs_make_room(dir2, 1, no_space, "recorder", boot, vs_boottime());
    char left[1024]; join_dir(dir2, left, sizeof left);
    CHECK(removed == 2 && !strcmp(left, ".recording 20261108_130205_01.ts"), "空き作り %d 件、残り「%s」", removed, left);
    { char c[1100]; snprintf(c, sizeof c, "rm -rf '%s'", dir2); if (system(c)) {} }
    printf("場面 %d 件。%s\n", k, fails ? "NG" : "すべてOK");
    return fails != 0;
}
