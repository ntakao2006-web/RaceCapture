// video_store.h：録画の置き場（~/ecocapture-v2-data/video）で、空きが足りないときにどれを消してよいかとその順番（手順書5-17）
//   EcoCapture-Web/video_store.py と同じ決まり。testdata/video_store/ の場面を両方で確かめる（video_store_test.c・test_video_store.py）
//   ファイル（GoProと同じく、1回の録画＝1つの走行を10分ごとの章に分ける）：
//     <走行>_<NN>.ts・.csv … 章と1秒ごとの時刻。走行の名前は録り始めの時刻 YYYYMMDD_HHMMSS（GNSSの時刻が分かったらそれ）
//     <章>.ts.ok … PCの回収アプリが、PCの写しと本体の中身が同じ（SHA-256）と確かめた印「大きさ sha256 時刻」
//     <走行>.keep … 保護の印（回収するまで自動では消さない）。<走行>.session … その走行の起動の番号・始まり・時計
//     .recording … 録画の今の状態（boot_id・走行・書いているファイル・bt＝起動からの秒）。deleted.log … 消した記録
//   消す順番：①回収済み（印の大きさが合うもの）を古い順 ②回収していない、ほかの走行の、保護していないものを古い順。
//   書いているファイル・今録っている走行（カメラを抜き差ししてもVS_GAP_S以内なら続き）・保護した走行の未回収は消さない
#include <dirent.h>
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define VS_ACTIVE_S 30   // 録画は書いている間 .recording を5秒ごとに書き直す
#define VS_GAP_S 300     // これより短い間に録画をやり直したら（カメラの抜き差し）同じ走行の続き
#define VS_LOG "deleted.log"

struct vs_ch { char name[256], session[256]; long long size, mtime_ns; int number, collected, active, current, kept; };
struct vs_store {
    struct vs_ch *ch; int n, cap;
    int alive;                                  // 録画が今書いている
    char active_file[256], current_session[256];  // 書いているファイル・今の走行（無ければ空）
};

static void vs_boot_id(char *b, size_t n) {
    b[0] = 0;
    FILE *f = fopen("/proc/sys/kernel/random/boot_id", "r");
    if (!f) return;
    if (fgets(b, (int)n, f)) b[strcspn(b, " \t\r\n")] = 0;
    fclose(f);
}

static double vs_boottime(void) { struct timespec t; clock_gettime(CLOCK_BOOTTIME, &t); return t.tv_sec + t.tv_nsec * 1e-9; }

static int vs_digits(const char *s, int n) { for (int i = 0; i < n; i++) if (s[i] < '0' || s[i] > '9') return 0; return 1; }

// .ts の名前の走行と章の番号。YYYYMMDD_HHMMSS_NN.ts（NNは2〜4桁）でなければ、名前そのものが1つの走行（章0）
static void vs_session_of(const char *name, char *session, size_t n, int *number) {
    size_t l = strlen(name);
    *number = 0;
    if (l >= 21 && l <= 23 && vs_digits(name, 8) && name[8] == '_' && vs_digits(name + 9, 6) && name[15] == '_' &&
        vs_digits(name + 16, (int)l - 19) && !strcmp(name + l - 3, ".ts")) {
        snprintf(session, n, "%.15s", name);
        *number = atoi(name + 16);
        return;
    }
    snprintf(session, n, "%.*s", l >= 3 ? (int)l - 3 : 0, name);
}

static void vs_trim(char *s) {
    size_t a = strspn(s, " \t\r\n\f\v"), l = strlen(s);
    while (l > a && strchr(" \t\r\n\f\v", s[l - 1])) l--;
    memmove(s, s + a, l - a); s[l - a] = 0;
}

// 「key=value」の行から値を取る（無ければ空）。Pythonの parse_kv と同じく、同じ鍵が何度あれば最後のもの
static void vs_kv(const char *text, const char *key, char *out, size_t n) {
    out[0] = 0;
    for (const char *p = text; *p;) {
        const char *e = strchr(p, '\n'); size_t len = e ? (size_t)(e - p) : strlen(p);
        char line[512]; snprintf(line, sizeof line, "%.*s", (int)(len < sizeof line ? len : sizeof line - 1), p);
        char *eq = strchr(line, '=');
        if (eq) { *eq = 0; vs_trim(line); if (!strcmp(line, key)) { vs_trim(eq + 1); snprintf(out, n, "%s", eq + 1); } }
        p += len + (e ? 1 : 0);
    }
}

// 普通のファイル（シンボリックリンクでない）なら1
static int vs_regular(const char *path, struct stat *st) { return !lstat(path, st) && S_ISREG(st->st_mode); }

static size_t vs_read(const char *path, char *b, size_t n) {
    b[0] = 0; struct stat st;
    if (!vs_regular(path, &st)) return 0;
    FILE *f = fopen(path, "rb"); if (!f) return 0;
    size_t r = fread(b, 1, n - 1, f); fclose(f); b[r] = 0;
    return r;
}

static int vs_cmp(const void *a, const void *b) {
    const struct vs_ch *x = a, *y = b;
    if (x->mtime_ns != y->mtime_ns) return x->mtime_ns < y->mtime_ns ? -1 : 1;
    return strcmp(x->name, y->name);
}

static void vs_free(struct vs_store *s) { free(s->ch); memset(s, 0, sizeof *s); }

// 置き場を調べる。boot：今の起動の番号、now_bt：今の起動からの秒（CLOCK_BOOTTIME）
static void vs_scan(const char *dir, const char *boot, double now_bt, struct vs_store *s) {
    memset(s, 0, sizeof *s);
    char path[1024], text[4096], v[256];
    snprintf(path, sizeof path, "%s/.recording", dir); vs_read(path, text, sizeof text);
    vs_kv(text, "boot_id", v, sizeof v);
    const int rec_ok = boot[0] && !strcmp(v, boot);
    vs_kv(text, "bt", v, sizeof v);
    char *end; double bt = strtod(v, &end);
    if (!v[0] || *end || end == v) bt = NAN;
    const double age = now_bt - bt;
    s->alive = rec_ok && age < VS_ACTIVE_S;  // NaNとの比較は偽
    if (s->alive) vs_kv(text, "file", s->active_file, sizeof s->active_file);
    if (rec_ok && age < VS_GAP_S) vs_kv(text, "session", s->current_session, sizeof s->current_session);
    DIR *d = opendir(dir); if (!d) return;
    struct dirent *e;
    while ((e = readdir(d))) {
        size_t l = strlen(e->d_name); struct stat st;
        if (l < 3 || strcmp(e->d_name + l - 3, ".ts") || l >= sizeof s->ch[0].name) continue;
        snprintf(path, sizeof path, "%s/%s", dir, e->d_name);
        if (!vs_regular(path, &st)) continue;
        if (s->n == s->cap) { s->cap = s->cap ? s->cap * 2 : 64; s->ch = realloc(s->ch, s->cap * sizeof *s->ch); if (!s->ch) { s->n = s->cap = 0; break; } }
        struct vs_ch *c = &s->ch[s->n++]; memset(c, 0, sizeof *c);
        snprintf(c->name, sizeof c->name, "%s", e->d_name);
        vs_session_of(c->name, c->session, sizeof c->session, &c->number);
        c->size = st.st_size; c->mtime_ns = (long long)st.st_mtim.tv_sec * 1000000000LL + st.st_mtim.tv_nsec;
        c->active = s->active_file[0] && !strcmp(c->name, s->active_file);
        snprintf(path, sizeof path, "%s/%s.ok", dir, c->name); vs_read(path, text, sizeof text);
        char tok[64] = "", sz[32]; sscanf(text, "%63s", tok); snprintf(sz, sizeof sz, "%lld", c->size);
        c->collected = tok[0] && !strcmp(tok, sz) && !c->active;
        c->current = s->current_session[0] && !strcmp(c->session, s->current_session);
        snprintf(path, sizeof path, "%s/%s.keep", dir, c->session); c->kept = vs_regular(path, &st);
    }
    closedir(d);
    qsort(s->ch, s->n, sizeof *s->ch, vs_cmp);
}

// 消してよい章を消す順に idx へ（数を返す）。idx は s->n 個入る大きさ
static int vs_order(const struct vs_store *s, int *idx) {
    int k = 0;
    for (int i = 0; i < s->n; i++) if (s->ch[i].collected) idx[k++] = i;
    for (int i = 0; i < s->n; i++) {
        const struct vs_ch *c = &s->ch[i];
        if (!c->collected && !c->active && !c->current && !c->kept) idx[k++] = i;
    }
    return k;
}

__attribute__((unused)) static long long vs_deletable(const struct vs_store *s) {
    long long b = 0;
    for (int i = 0; i < s->n; i++) {
        const struct vs_ch *c = &s->ch[i];
        if (c->collected || (!c->active && !c->current && !c->kept)) b += c->size;
    }
    return b;
}

// 章を消す（横の.csvと印も）。消した記録を deleted.log へ書き、走行の章が無くなったら .session・.keep も消す。
// 消せたら1、もう無かったら0、消せなかったら-1
static int vs_delete(const char *dir, const struct vs_ch *c, const char *by, const char *boot) {
    char p[1024];
    snprintf(p, sizeof p, "%s/%s", dir, c->name);
    if (unlink(p)) return errno == ENOENT ? 0 : -1;
    snprintf(p, sizeof p, "%s/%.*s.csv", dir, (int)strlen(c->name) - 3, c->name); unlink(p);
    snprintf(p, sizeof p, "%s/%s.ok", dir, c->name); unlink(p);
    snprintf(p, sizeof p, "%s/" VS_LOG, dir);
    FILE *f = fopen(p, "a");
    if (f) {
        time_t t = time(NULL); struct tm g; gmtime_r(&t, &g); char u[32]; strftime(u, sizeof u, "%Y-%m-%dT%H:%M:%SZ", &g);
        fprintf(f, "%s\t%s\t%s\t%lld\t%s\t%.8s\n", u, by, c->name, c->size, c->collected ? "collected" : "uncollected", boot);
        fclose(f);
    }
    DIR *d = opendir(dir); int left = 0; struct dirent *e;
    if (d) {
        while (!left && (e = readdir(d))) {
            size_t l = strlen(e->d_name); char ss[256]; int nn;
            if (l < 3 || strcmp(e->d_name + l - 3, ".ts")) continue;
            vs_session_of(e->d_name, ss, sizeof ss, &nn); left = !strcmp(ss, c->session);
        }
        closedir(d);
    }
    if (d && !left) {
        snprintf(p, sizeof p, "%s/%s.session", dir, c->session); unlink(p);
        snprintf(p, sizeof p, "%s/%s.keep", dir, c->session); unlink(p);
    }
    return 1;
}

// 空き（free_fn）が enough になるまで、消す順に消す。消した数を返す
static int vs_make_room(const char *dir, double enough, double (*free_fn)(void), const char *by, const char *boot, double now_bt) {
    int done = 0; char failed[16][256]; int nf = 0;
    while (free_fn() < enough) {
        struct vs_store s; vs_scan(dir, boot, now_bt, &s);
        int *idx = malloc((s.n ? s.n : 1) * sizeof *idx), k = vs_order(&s, idx), pick = -1;
        for (int j = 0; j < k && pick < 0; j++) {
            int skip = 0;
            for (int q = 0; q < nf; q++) if (!strcmp(failed[q], s.ch[idx[j]].name)) skip = 1;
            if (!skip) pick = idx[j];
        }
        int r = pick < 0 ? 0 : vs_delete(dir, &s.ch[pick], by, boot);
        if (pick >= 0 && r <= 0 && nf < 16) snprintf(failed[nf++], sizeof failed[0], "%s", s.ch[pick].name);
        if (r > 0) { done++; printf("removed %s (free space, %s)\n", s.ch[pick].name, s.ch[pick].collected ? "collected" : "uncollected"); fflush(stdout); }
        free(idx); vs_free(&s);
        if (pick < 0 || (r <= 0 && nf >= 16)) break;
    }
    return done;
}
