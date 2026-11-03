// video_store.h：本体の置き場（~/ecocapture-v2-data）を、ドラレコと同じく動画（video/）と走行記録（logs/）で分け合い、
//   空きが足りなくなったら古いものから消して、録画を止めずに直近の時間を残す。消してよいものとその順番（手順書5-17・5-18）
//   EcoCapture-Web/video_store.py と同じ決まり。testdata/video_store/ の場面を両方で確かめる（video_store_test.c・test_video_store.py）
//   video/（GoProと同じく、1回の録画＝1つの走行を10分ごとの章に分ける）：
//     <走行>_<NN>.ts・.csv … 章と1秒ごとの時刻。走行の名前は録り始めの時刻 YYYYMMDD_HHMMSS（GNSSの時刻が分かったらそれ）
//     <章>.ts.ok … PCの回収アプリが、PCの写しと本体の中身が同じ（SHA-256）と確かめた印「大きさ sha256 時刻」
//     <走行>.keep … 保護の印（回収するまで自動では消さない）。<走行>.session … その走行の起動の番号・始まり・時計
//     .recording … 録画の今の状態（boot_id・走行・書いているファイル・bt＝起動からの秒）。deleted.log … 消した記録（動画も走行記録も）
//   logs/（EcoCapture）：LOG_<UTC>_<id>.csv と .meta.json・.can.jsonl・.sd-journal.jsonl で1つの走行記録（まとめて消す）。
//     .csv.ok … Collect-Logs.cmd が写しを確かめた印（EcoCaptureが書く）。.csv.keep … 保護。.recording … EcoCaptureの今の状態
//   消す順番：①回収済み（動画・走行記録とも、印の大きさが合うもの）を古い順 ②ほかの動画・走行記録を古い順（今の走行の古い章も）。
//   書いている動画・記録中の走行記録（と、書いてVS_RECENT_S以内の走行記録）・保護して回収していないものは消さない
#include <dirent.h>
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define VS_ACTIVE_S 30   // 録画とEcoCaptureは書いている間 .recording を5秒ごとに書き直す
#define VS_GAP_S 300     // これより短い間に録画をやり直したら（カメラの抜き差し）同じ走行の続き
#define VS_RECENT_S 120  // 書いてこれより新しい走行記録は、.recording が何であれ消さない
#define VS_LOG "deleted.log"

enum { VS_VIDEO, VS_DRIVELOG };
struct vs_ch { char name[256], session[256]; long long size, mtime_ns; int kind, number, collected, active, current, kept; };
struct vs_store {
    struct vs_ch *ch; int n, cap;
    int alive;                                  // 録画が今書いている
    char active_file[256], current_session[256], active_log[256];  // 書いている動画・今の走行・記録中の走行記録（無ければ空）
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

// 走行記録の名前か（LOG_ か DEMO_ ＋ YYYYMMDDTHHMMSSZ_ ＋ 小文字の16進8桁 ＋ .csv。EcoCaptureの log_path と同じ）
static int vs_is_log(const char *s) {
    const char *p = !strncmp(s, "LOG_", 4) ? s + 4 : !strncmp(s, "DEMO_", 5) ? s + 5 : NULL;
    if (!p || strlen(p) != 29 || !vs_digits(p, 8) || p[8] != 'T' || !vs_digits(p + 9, 6) || p[15] != 'Z' || p[16] != '_') return 0;
    for (int i = 17; i < 25; i++) if (!((p[i] >= '0' && p[i] <= '9') || (p[i] >= 'a' && p[i] <= 'f'))) return 0;
    return !strcmp(p + 25, ".csv");
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

static long long vs_ns(const struct stat *st) { return (long long)st->st_mtim.tv_sec * 1000000000LL + st->st_mtim.tv_nsec; }

static int vs_cmp(const void *a, const void *b) {
    const struct vs_ch *x = a, *y = b;
    if (x->mtime_ns != y->mtime_ns) return x->mtime_ns < y->mtime_ns ? -1 : 1;
    return strcmp(x->name, y->name);
}

static void vs_free(struct vs_store *s) { free(s->ch); memset(s, 0, sizeof *s); }

static struct vs_ch *vs_add(struct vs_store *s) {
    if (s->n == s->cap) {
        int cap = s->cap ? s->cap * 2 : 64; struct vs_ch *p = realloc(s->ch, cap * sizeof *p);
        if (!p) return NULL;
        s->ch = p; s->cap = cap;
    }
    struct vs_ch *c = &s->ch[s->n++]; memset(c, 0, sizeof *c);
    return c;
}

// .recording を読む。書いている側が生きていれば *alive、VS_GAP_S以内に書かれていれば *recent
static void vs_state(const char *dir, const char *boot, double now_bt, char *text, size_t n, int *alive, int *recent) {
    char path[1024], v[256];
    snprintf(path, sizeof path, "%s/.recording", dir); vs_read(path, text, n);
    vs_kv(text, "boot_id", v, sizeof v);
    const int ok = boot[0] && !strcmp(v, boot);
    vs_kv(text, "bt", v, sizeof v);
    char *end; double bt = strtod(v, &end);
    if (!v[0] || *end || end == v) bt = NAN;
    const double age = now_bt - bt;
    *alive = ok && age < VS_ACTIVE_S;  // NaNとの比較は偽
    *recent = ok && age < VS_GAP_S;
}

// 置き場を調べる。vdir：動画、ldir：走行記録（NULLなら見ない）、boot：今の起動の番号、now_bt：起動からの秒、now_wall：時計（秒）
static void vs_scan(const char *vdir, const char *ldir, const char *boot, double now_bt, double now_wall, struct vs_store *s) {
    memset(s, 0, sizeof *s);
    char path[1024], text[4096]; int recent, log_alive, log_recent;
    vs_state(vdir, boot, now_bt, text, sizeof text, &s->alive, &recent);
    if (s->alive) vs_kv(text, "file", s->active_file, sizeof s->active_file);
    if (recent) vs_kv(text, "session", s->current_session, sizeof s->current_session);
    DIR *d = opendir(vdir); struct dirent *e;
    while (d && (e = readdir(d))) {
        size_t l = strlen(e->d_name); struct stat st;
        if (l < 3 || strcmp(e->d_name + l - 3, ".ts") || l >= sizeof s->ch[0].name) continue;
        snprintf(path, sizeof path, "%s/%s", vdir, e->d_name);
        if (!vs_regular(path, &st)) continue;
        struct vs_ch *c = vs_add(s); if (!c) break;
        snprintf(c->name, sizeof c->name, "%s", e->d_name); c->kind = VS_VIDEO;
        vs_session_of(c->name, c->session, sizeof c->session, &c->number);
        c->size = st.st_size; c->mtime_ns = vs_ns(&st);
        c->active = s->active_file[0] && !strcmp(c->name, s->active_file);
        snprintf(path, sizeof path, "%s/%s.ok", vdir, c->name); vs_read(path, text, sizeof text);
        char tok[64] = "", sz[32]; sscanf(text, "%63s", tok); snprintf(sz, sizeof sz, "%lld", c->size);
        c->collected = tok[0] && !strcmp(tok, sz) && !c->active;
        c->current = s->current_session[0] && !strcmp(c->session, s->current_session);
        snprintf(path, sizeof path, "%s/%s.keep", vdir, c->session); c->kept = vs_regular(path, &st);
    }
    if (d) closedir(d);
    if (ldir) {
        vs_state(ldir, boot, now_bt, text, sizeof text, &log_alive, &log_recent);
        if (log_alive) vs_kv(text, "file", s->active_log, sizeof s->active_log);
        d = opendir(ldir);
        while (d && (e = readdir(d))) {
            struct stat st;
            if (!vs_is_log(e->d_name)) continue;
            snprintf(path, sizeof path, "%s/%s", ldir, e->d_name);
            if (!vs_regular(path, &st)) continue;
            struct vs_ch *c = vs_add(s); if (!c) break;
            snprintf(c->name, sizeof c->name, "%s", e->d_name); c->kind = VS_DRIVELOG;
            const long long csv_size = st.st_size, csv_ns = vs_ns(&st);
            c->size = csv_size; c->mtime_ns = csv_ns;
            static const char *parts[] = { ".meta.json", ".can.jsonl", ".sd-journal.jsonl" };
            for (int i = 0; i < 3; i++) {
                struct stat ps; snprintf(path, sizeof path, "%s/%s%s", ldir, c->name, parts[i]);
                if (!vs_regular(path, &ps)) continue;
                c->size += ps.st_size;  // 並びは.csvの時刻で決める
            }
            c->active = (s->active_log[0] && !strcmp(c->name, s->active_log)) || now_wall - csv_ns / 1e9 < VS_RECENT_S;
            snprintf(path, sizeof path, "%s/%s.ok", ldir, c->name); vs_read(path, text, sizeof text);
            char tok[64] = "", sz[32]; sscanf(text, "%63s", tok); snprintf(sz, sizeof sz, "%lld", csv_size);
            c->collected = tok[0] && !strcmp(tok, sz) && !c->active;
            snprintf(path, sizeof path, "%s/%s.keep", ldir, c->name); c->kept = vs_regular(path, &st);
        }
        if (d) closedir(d);
    }
    qsort(s->ch, s->n, sizeof *s->ch, vs_cmp);
}

// 消してよいものを消す順に idx へ（数を返す）。idx は s->n 個入る大きさ
static int vs_order(const struct vs_store *s, int *idx) {
    int k = 0;
    for (int i = 0; i < s->n; i++) if (s->ch[i].collected) idx[k++] = i;
    for (int i = 0; i < s->n; i++) {
        const struct vs_ch *c = &s->ch[i];
        if (!c->collected && !c->active && !c->kept) idx[k++] = i;
    }
    return k;
}

__attribute__((unused)) static long long vs_deletable(const struct vs_store *s) {
    long long b = 0;
    for (int i = 0; i < s->n; i++) {
        const struct vs_ch *c = &s->ch[i];
        if (c->collected || (!c->active && !c->kept)) b += c->size;
    }
    return b;
}

// 消す（章は横の.csvと印も、走行記録は一式と印も）。消した記録を動画の置き場の deleted.log へ書き、
// 走行の章が無くなったら .session・.keep も消す。消せたら1、もう無かったら0、消せなかったら-1
static int vs_delete(const char *vdir, const char *ldir, const struct vs_ch *c, const char *by, const char *boot) {
    char p[1024];
    const char *dir = c->kind == VS_DRIVELOG ? ldir : vdir;
    if (!dir) return -1;
    snprintf(p, sizeof p, "%s/%s", dir, c->name);
    if (unlink(p)) return errno == ENOENT ? 0 : -1;
    if (c->kind == VS_DRIVELOG) {
        static const char *extra[] = { ".meta.json", ".can.jsonl", ".sd-journal.jsonl", ".ok", ".keep" };
        for (int i = 0; i < 5; i++) { snprintf(p, sizeof p, "%s/%s%s", ldir, c->name, extra[i]); unlink(p); }
        snprintf(p, sizeof p, "%s/../sd-journals/%s.timestamps.jsonl", ldir, c->name); unlink(p);
    } else {
        snprintf(p, sizeof p, "%s/%.*s.csv", vdir, (int)strlen(c->name) - 3, c->name); unlink(p);
        snprintf(p, sizeof p, "%s/%s.ok", vdir, c->name); unlink(p);
    }
    snprintf(p, sizeof p, "%s/" VS_LOG, vdir);
    FILE *f = fopen(p, "a");
    if (f) {
        time_t t = time(NULL); struct tm g; gmtime_r(&t, &g); char u[32]; strftime(u, sizeof u, "%Y-%m-%dT%H:%M:%SZ", &g);
        fprintf(f, "%s\t%s\t%s\t%lld\t%s\t%.8s\n", u, by, c->name, c->size, c->collected ? "collected" : "uncollected", boot);
        fclose(f);
    }
    if (c->kind == VS_DRIVELOG) return 1;
    DIR *d = opendir(vdir); int left = 0; struct dirent *e;
    if (d) {
        while (!left && (e = readdir(d))) {
            size_t l = strlen(e->d_name); char ss[256]; int nn;
            if (l < 3 || strcmp(e->d_name + l - 3, ".ts")) continue;
            vs_session_of(e->d_name, ss, sizeof ss, &nn); left = !strcmp(ss, c->session);
        }
        closedir(d);
    }
    if (d && !left) {
        snprintf(p, sizeof p, "%s/%s.session", vdir, c->session); unlink(p);
        snprintf(p, sizeof p, "%s/%s.keep", vdir, c->session); unlink(p);
    }
    return 1;
}

// 空き（free_fn）が enough になるまで、消す順に消す。消した数を返す
static int vs_make_room(const char *vdir, const char *ldir, double enough, double (*free_fn)(void), const char *by, const char *boot,
                        double now_bt, double now_wall) {
    int done = 0; char failed[16][256]; int nf = 0;
    while (free_fn() < enough) {
        struct vs_store s; vs_scan(vdir, ldir, boot, now_bt, now_wall, &s);
        int *idx = malloc((s.n ? s.n : 1) * sizeof *idx), k = vs_order(&s, idx), pick = -1;
        for (int j = 0; j < k && pick < 0; j++) {
            int skip = 0;
            for (int q = 0; q < nf; q++) if (!strcmp(failed[q], s.ch[idx[j]].name)) skip = 1;
            if (!skip) pick = idx[j];
        }
        int r = pick < 0 ? 0 : vs_delete(vdir, ldir, &s.ch[pick], by, boot);
        if (pick >= 0 && r <= 0 && nf < 16) snprintf(failed[nf++], sizeof failed[0], "%s", s.ch[pick].name);
        if (r > 0) { done++; printf("removed %s (free space, %s)\n", s.ch[pick].name, s.ch[pick].collected ? "collected" : "uncollected"); fflush(stdout); }
        free(idx); vs_free(&s);
        if (pick < 0 || (r <= 0 && nf >= 16)) break;
    }
    return done;
}
