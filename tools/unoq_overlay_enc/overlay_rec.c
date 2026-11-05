// UNO Q：走行映像に走行データ（車速・回転数・水温・油温・ラップ・G・時刻）を焼き込んで保存する（試作）
//   カメラ（UVC、MJPEG 1280x720）→ 展開スレッド（libjpeg-turbo）→ GPUと共有するメモリへ写す
//   → GPUで1920x1080へ拡大し計器を重ね描き → エンコーダ（venus）の入力バッファへdmabufで直接NV12を書く → H.264
//   GPUはY（輝度）面とUV（色差）面へ直接描く。RGBの中間画面は作らず、計器は面ごとに1回の描画にまとめる（手順書5-13）
//   保存はMPEG-TS（.ts）。1枚ごとにカメラの時刻を付ける。途中で電源が切れても、そこまでは再生できる
//   数値はEcoCaptureのAPI（http://127.0.0.1:8080/api/telemetry）を別スレッドで約10Hzで読む
//   土台は overlay_enc_test.c（mode=1・thr=1、unoq_video_check_procedure.md 5-11）。計器の文字は
//   make_font_atlas.py で作る文字の一覧表（hud_font_64.pgm、DejaVu Sans Mono Bold）をGPUで貼る
//   計器の項目・位置・大きさ・色は設定ファイル（hud.ini、組み立ては hud_layout.h）で決める。OVERLAY_HUD のファイルがあればそれを、
//   無いか読めなければ OVERLAY_HUD_DEFAULT（既定は文字の一覧表と同じ場所の hud_default.ini）を使う。録画中も約1秒ごとに見て、
//   書き換わっていれば次のコマから新しい配置で描く（誤りがあれば前の配置のまま）。読んだ結果は OVERLAY_HUD_STATUS のファイルへ書く
//   PCでの見た目の確認と本体への送り方は tools/video_hud/（手順書5-14）
//   ベストとの差（calc.Delta 等）とコース図の線は、走行データの位置・ラップから lap_ref.h で作る。ベストの周の軌跡は
//   OVERLAY_LAPREF のファイルへ書き、録画をやり直しても lap.BestLap と同じ時間なら続きから使う（手順書5-16）
// ビルド(UNO Q上): gcc -O2 -o overlay_rec overlay_rec.c -lEGL -lGLESv2 -ljpeg -lm -lpthread（hud_layout.h・lap_ref.h・video_store.h を同じ場所に置く）
// 実行: ./overlay_rec <入力> <出力> [seconds=60、0は止めるまで] [font=hud_font_64.pgm]
//   入力：/dev/videoN（カメラ）か file:xxx.jpg（同じJPEGを30fpsで繰り返す。カメラ無しで試す用）
//   出力：xxx.ts（MPEG-TS）か xxx.h264（素のH.264、時刻なし）。%を含むとき（本番は <置き場>/%Y%m%d_%H%M%S.ts）はGoProと同じく、
//         1回の録画を1つの走行とし、OVERLAY_SEGMENT_MIN分（既定10）ごとにキーフレームの所で次の章のファイルへ切り替える。
//         名前は「走行の録り始めの時刻（%の書式）_章の番号」（例 20261108_130205_01.ts、_02 …）。カメラが抜けて録画をやり直しても、
//         前の録画が止まってからVS_GAP_S（300秒）以内なら同じ走行の続きの章にする（手順書5-17）
//   出力の横に xxx.csv（1秒ごとに「ファイル内の枚目・動画内の秒・UTC・どの時計か・本体の時計のUTC」）を書く。走行データと時刻を合わせる用。
//   時刻は走行データのGNSSの時刻に合わせる（本体の時計は車の中では合っていないことがある）。GNSSの時刻が分かるまでは
//   本体の時計で名前を付け、分かったら、その走行のファイルをすべてGNSSの時刻の走行の名前へ付け直す
//   置き場には、録画の今の状態 .recording（起動の番号・走行・書いているファイル・起動からの秒。5秒ごとに書き直す）と、
//   走行ごとの <走行>.session を書く。EcoCaptureとPCの回収アプリはこれで書いている途中のファイルと今の走行を見分ける
//   ビットレートはOVERLAY_BITRATE_MBPS（既定10。1分で約77MB、空き約13GBで約2時間45分。12だと約2時間19分。手順書5-13）
//   空きがOVERLAY_MIN_FREE_MB（既定1024）を切ったら、ドラレコと同じく video_store.h の順に動画と走行記録（置き場の隣の logs/、
//   OVERLAY_LOGS_DIR で変えられる）をまとめて消して空ける：①回収済み（PCで中身を確かめた印のあるもの）を古い順 ②ほかを古い順
//   （今の走行の古い章も）。書いているファイル・EcoCaptureが記録中の走行記録・保護して回収していないものは消さず、
//   消せるものが無くなったときだけ記録を止めて終わる（終了コード3）。消したものは deleted.log に書く。
//   EcoCaptureも空きが1GiBを切ると同じ順で消す。走行記録はシールドのSDにも残る（手順書5-13・5-17・5-18）
//   SIGINT/SIGTERMで止めると、エンコーダに残った分を書き出してから終わる
//   OVERLAY_OUT=720 のときは1280x720で保存する（既定は1920x1080。計器は同じ配置のまま縮む）
//   OVERLAY_DEMO=1 のときは作り物の値で描く（見た目と警告の色の確認用。画面にDEMOと出る）。位置とラップは架空のコースを
//   周ごとに違う速さで走らせたもので、ベストとの差・コース図も動く（ベストの周はファイルへ書かない）。
//   OVERLAY_DEMO_START 秒（既定250＝2周半）走った所から始める
//   OVERLAY_PROFILE=1 のときは工程ごとにGPUの完了を待って時間を測る（その分遅くなる）
//   OVERLAY_NOHUD=1 のときは計器を描かない（時間の比較用）
#define _GNU_SOURCE
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <GLES2/gl2ext.h>
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>  // jpeglib.h より前に要る
#include <jpeglib.h>
#include <linux/videodev2.h>
#include <math.h>
#include <netinet/in.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <dirent.h>
#include <drm/drm.h>
#include <drm/msm_drm.h>
#include <time.h>
#include <unistd.h>
#include "hud_layout.h"
#include "lap_ref.h"
#include "video_store.h"
#include "ts_mux.h"

#define W 1920  // 計器を描く座標の大きさ（出力の既定の大きさでもある）
#define H 1080
#define NOUT 4
#define NCAP 4
#define CAM_W 1280
#define CAM_H 720
#define NCAM 4
#define FOURCC(a, b, c, d) ((uint32_t)(a) | ((uint32_t)(b) << 8) | ((uint32_t)(c) << 16) | ((uint32_t)(d) << 24))
#define DRM_FORMAT_R8 FOURCC('R', '8', ' ', ' ')
#define DRM_FORMAT_GR88 FOURCC('G', 'R', '8', '8')

static int ow = W, oh = H;  // 出力の大きさ（OVERLAY_OUT=720で1280x720）
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static double wall(void) { struct timespec t; clock_gettime(CLOCK_REALTIME, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
#define DIE(...) do { fprintf(stderr, __VA_ARGS__); fprintf(stderr, " (errno=%d %s)\n", errno, strerror(errno)); exit(1); } while (0)

static int xioctl(int fd, unsigned long req, void *arg) {
    int r; do { r = ioctl(fd, req, arg); } while (r < 0 && errno == EINTR); return r;
}

static volatile sig_atomic_t quit;
static void on_signal(int s) { (void)s; quit = 1; }
#include "audio_cap.h"  // quit・now() を使う

// ---------------------------------------------------------------- 走行データ（EcoCaptureのAPI）
struct tele {
    time_t utc; int utc_ok;
    double got;  // 最後に読めた時刻（now()）
};
static struct tele tl = { 0, 0, -1e9 };
static pthread_mutex_t tmu = PTHREAD_MUTEX_INITIALIZER;
// 計器の設定（hud.ini）。差し替えるのは描画のスレッドだけ。走行データのスレッドが値の名前を写すときと、値（tvals）はtmuで守る
static struct hud *hud_cur;
static int hud_gen;  // 差し替えるたびに増やす（前の設定の順で読んだ値を捨てる）
static double tvals[HUD_REFS];  // 値（hud_cur->ref の順。無ければNAN）
static int api_port = 8080;  // OVERLAY_TELEMETRY_PORTで変えられる（時刻合わせの試験で、作り物の値を返す相手へ向ける）
// ベストとの差・コース図の線（lap_ref.h）。lr は走行データのスレッド（DEMOのときは描画のスレッド）だけが触る。
// 線は ttrk に写してtmuで守る。計算した値は「calc.名前」で計器から使える（calc_value）
static struct lap_ref lr;
static struct hud_track ttrk;
static int demo;  // OVERLAY_DEMO=1：作り物の値で描く（走行データのスレッドは差の計算をしない）

// calc.Delta（ベストとの差、秒）・calc.SpeedDelta（速度の差、km/h）・calc.BestLapNo（ベストの周の番号）・
// calc.Predicted（予想ラップ、分）・calc.GTotal（横Gと前後Gを合わせた大きさ）。無い名前・無いときはNAN
static double calc_value(const char *name, double lat_g, double long_g) {
    if (!strcmp(name, "Delta")) return lr.delta;
    if (!strcmp(name, "SpeedDelta")) return lr.sdelta;
    if (!strcmp(name, "BestLapNo")) return lr.best_no;
    if (!strcmp(name, "Predicted")) return lr.pred;
    if (!strcmp(name, "GTotal")) return hypot(lat_g, long_g);
    return NAN;
}

// ---- 時刻（GNSS）
// 本体（Linux）の時計は、車の中ではネットにつながらず合っていないことがある（電池付きの時計が無く、前に止めたときの
// 時刻から動き出す。LTEはSTM32側なのでLinuxの時計合わせには使えない）。そこで、走行データのGNSSの時刻と、
// その行を本体が受け取った時刻（host_utc）の差から「GNSSの時刻 − CLOCK_MONOTONIC」を求め、各コマの時刻に使う。
// 受け取りまでの遅れ（数十〜100ms）があるので、直近30秒で一番遅れの小さい（差が大きい）値を使う
#define CLK_N 128
static struct { double est, at; } clk[CLK_N];
static int clk_i;
static double gnss_off, gnss_at = -1e9;  // GNSSの時刻 − CLOCK_MONOTONIC と、それを最後に求めた時刻（now()）。tmuで守る

static void clock_sample(double est) {  // tmuを持って呼ぶ
    double t = now(), best = -1e18;
    clk[clk_i].est = est; clk[clk_i].at = t; clk_i = (clk_i + 1) % CLK_N;
    for (int i = 0; i < CLK_N; i++) if (clk[i].at > t - 30 && clk[i].est > best) best = clk[i].est;
    gnss_off = best; gnss_at = t;
}

// GNSSの時刻が分かっていれば1（1分以上来ていなければ0）
static int gnss_offset(double *off) {
    pthread_mutex_lock(&tmu);
    int ok = now() - gnss_at < 60; *off = gnss_off;
    pthread_mutex_unlock(&tmu);
    return ok;
}

static int http_get(const char *path, char *buf, int cap) {
    int s = socket(AF_INET, SOCK_STREAM, 0); if (s < 0) return -1;
    struct timeval tv = { 0, 500000 };
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof tv); setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof tv);
    struct sockaddr_in a = { .sin_family = AF_INET, .sin_port = htons(api_port), .sin_addr.s_addr = htonl(INADDR_LOOPBACK) };
    if (connect(s, (struct sockaddr *)&a, sizeof a)) { close(s); return -1; }
    char req[256];
    int n = snprintf(req, sizeof req, "GET %s HTTP/1.0\r\nHost: 127.0.0.1\r\nX-EcoCapture: 1\r\nConnection: close\r\n\r\n", path);
    if (send(s, req, n, 0) != n) { close(s); return -1; }
    int len = 0;
    for (;;) { int r = recv(s, buf + len, cap - 1 - len, 0); if (r <= 0) break; len += r; if (len >= cap - 1) break; }
    close(s); buf[len] = 0;
    return len;
}

// JSONの中から "key": 数値 を探す（section の後ろで最初に出てくるもの）。nullや無いときはNAN
static double jnum(const char *js, const char *section, const char *key) {
    char k[64];
    if (section) { snprintf(k, sizeof k, "\"%s\":", section); js = strstr(js, k); if (!js) return NAN; }
    snprintf(k, sizeof k, "\"%s\":", key);
    const char *q = strstr(js, k); if (!q) return NAN;
    q += strlen(k); while (*q == ' ') q++;
    char *e; double v = strtod(q, &e);
    return e == q ? NAN : v;
}

// "2026-10-29T13:50:42.577141+00:00" → time_t（UTC）
// "key": "…" の文字列の中身の先頭（無い・nullならNULL。コロンのあとの空白は読み飛ばす）
static const char *jstr(const char *js, const char *key) {
    char k[64]; snprintf(k, sizeof k, "\"%s\":", key);
    const char *q = strstr(js, k); if (!q) return NULL;
    q += strlen(k); while (*q == ' ') q++;
    return *q == '"' ? q + 1 : NULL;
}

static int jtime(const char *js, const char *key, time_t *out) {
    const char *q = jstr(js, key); if (!q) return 0;
    struct tm t = {0};
    if (sscanf(q, "%d-%d-%dT%d:%d:%d", &t.tm_year, &t.tm_mon, &t.tm_mday, &t.tm_hour, &t.tm_min, &t.tm_sec) != 6) return 0;
    t.tm_year -= 1900; t.tm_mon -= 1; *out = timegm(&t); return 1;
}

// 同じく秒の小数まで（UTC）。無ければ0
static double jtime_frac(const char *js, const char *key) {
    const char *q = jstr(js, key); if (!q) return 0;
    struct tm t = {0}; int n = 0;
    if (sscanf(q, "%d-%d-%dT%d:%d:%d%n", &t.tm_year, &t.tm_mon, &t.tm_mday, &t.tm_hour, &t.tm_min, &t.tm_sec, &n) != 6) return 0;
    t.tm_year -= 1900; t.tm_mon -= 1;
    return timegm(&t) + (q[n] == '.' ? strtod(q + n, NULL) : 0);
}

// 値の名前（"values.Speed|values.GPSSpeed" の形）を | の前から順に探し、最初に数値だったもの。無ければNAN
static double jref(const char *js, const char *spec) {
    char alt[HUD_REF_LEN];
    for (const char *p = spec; *p;) {
        size_t n = strcspn(p, "|"); if (n >= sizeof alt) n = sizeof alt - 1;
        memcpy(alt, p, n); alt[n] = 0; p += n; if (*p == '|') p++;
        char *dot = strchr(alt, '.');
        double v;
        if (dot && dot - alt == 4 && !strncmp(alt, "calc", 4))  // calc.〜：ここで計算した値
            v = calc_value(dot + 1, jnum(js, "values", "LatAccel"), jnum(js, "values", "LongAccel"));
        else if (dot) { *dot = 0; v = jnum(js, alt, dot + 1); } else v = jnum(js, NULL, alt);
        if (!isnan(v)) return v;
    }
    return NAN;
}

// DEMOの値：位置・速度・ラップは作り物の走行（lap_ref.h の lr_demo）、calc.〜 は計算した値、ほかは hud_demo
static double demo_ref(const char *spec, const struct lr_demo *d, double lat, double lon, double ph) {
    char k[HUD_REF_LEN]; snprintf(k, sizeof k, "%s", spec);
    k[strcspn(k, "|")] = 0;
    const char *n = strchr(k, '.') ? strchr(k, '.') + 1 : k;
    if (!strncmp(k, "calc.", 5)) return calc_value(n, hud_demo("LatAccel", ph), hud_demo("LongAccel", ph));
    if (!strcmp(n, "Lat")) return lat;
    if (!strcmp(n, "Lon")) return lon;
    if (!strcmp(n, "Speed") || !strcmp(n, "GPSSpeed")) return lr_demo_v0(d, d->s) * lr_demo_factor(d->lap);
    if (!strcmp(n, "CurrentLap")) return d->lap;
    if (!strcmp(n, "LapCount")) return d->count;
    if (!strcmp(n, "ElapsedTime")) return (d->t - d->lap_start) / 60;
    if (!strcmp(n, "LapTime")) return d->last / 60;
    if (!strcmp(n, "BestLap")) return d->best / 60;
    return hud_demo(spec, ph);
}

static void *telemetry(void *arg) {
    (void)arg;
    static char buf[1 << 16], refs[HUD_REFS][HUD_REF_LEN];
    static struct hud_track trk;
    while (!quit) {
        double a = now();
        if (http_get("/api/telemetry", buf, sizeof buf) > 0 && strstr(buf, "\"sample\"")) {
            const char *js = strstr(buf, "\"sample\"");
            int nref = 0, gen;
            pthread_mutex_lock(&tmu);
            gen = hud_gen;
            if (hud_cur) { nref = hud_cur->nref; memcpy(refs, hud_cur->ref, sizeof refs[0] * nref); }
            pthread_mutex_unlock(&tmu);
            if (!demo) {  // ベストとの差・コース図の線を進めてから、calc.〜 の値を読む
                const double lat = jnum(js, "values", "Lat"), lon = jnum(js, "values", "Lon");
                lr_update(&lr, lat, lon, jref(js, "values.Speed|values.GPSSpeed"), jnum(js, "lap", "CurrentLap"),
                          jnum(js, "lap", "ElapsedTime"), jnum(js, "lap", "LapTime"), jnum(js, "lap", "BestLap"));
                lr_track(&lr, lat, lon, &trk);
                pthread_mutex_lock(&tmu); ttrk.n = trk.n;
                memcpy(ttrk.lat, trk.lat, sizeof trk.lat[0] * trk.n); memcpy(ttrk.lon, trk.lon, sizeof trk.lon[0] * trk.n);
                pthread_mutex_unlock(&tmu);
            }
            double v[HUD_REFS];
            for (int i = 0; i < nref; i++) v[i] = jref(js, refs[i]);
            struct tele t;
            t.utc_ok = jtime(js, "gnss_utc", &t.utc) || jtime(js, "host_utc", &t.utc);
            t.got = now();
            // gnss_utcは秒まで。秒の小数はiTOW（GPSの時刻。UTCとの差は整数秒なので小数は同じ）から取る
            const double host = jtime_frac(js, "host_utc"), gnss = jtime_frac(js, "gnss_utc"), itow = jnum(js, NULL, "gnss_itow_ms");
            pthread_mutex_lock(&tmu);
            tl = t;
            if (gen == hud_gen) memcpy(tvals, v, sizeof v[0] * nref);  // 読んでいる間に設定が差し替わったら捨てる
            if (host > 0 && gnss > 0 && !isnan(itow)) clock_sample(gnss + fmod(itow, 1000) / 1000 - (host - (wall() - now())));
            pthread_mutex_unlock(&tmu);
        }
        double r = 0.1 - (now() - a);
        if (r > 0) usleep(r * 1e6);
    }
    return NULL;
}

// ---------------------------------------------------------------- GL
static GLuint shader(GLenum type, const char *src) {
    GLuint s = glCreateShader(type); glShaderSource(s, 1, &src, NULL); glCompileShader(s);
    GLint ok; glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) { char log[2048]; glGetShaderInfoLog(s, sizeof log, NULL, log); fprintf(stderr, "shader: %s\n", log); exit(1); }
    return s;
}
static GLuint program(const char *vs, const char *fs) {
    GLuint p = glCreateProgram();
    glAttachShader(p, shader(GL_VERTEX_SHADER, vs)); glAttachShader(p, shader(GL_FRAGMENT_SHADER, fs));
    glLinkProgram(p); GLint ok; glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) { char log[2048]; glGetProgramInfoLog(p, sizeof log, NULL, log); fprintf(stderr, "link: %s\n", log); exit(1); }
    return p;
}
static GLuint tex(GLenum ifmt, int w, int h, GLint filter) {
    GLuint t; glGenTextures(1, &t); glBindTexture(GL_TEXTURE_2D, t);
    glTexStorage2D(GL_TEXTURE_2D, 1, ifmt, w, h);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, filter);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, filter);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    return t;
}
static GLuint fbo_for(GLuint t) {
    GLuint f; glGenFramebuffers(1, &f); glBindFramebuffer(GL_FRAMEBUFFER, f);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, t, 0);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) DIE("fbo incomplete");
    return f;
}

static const char *VS_FULL =
    "#version 300 es\n"
    "void main(){ vec2 p=vec2((gl_VertexID<<1)&2, gl_VertexID&2); gl_Position=vec4(p*2.0-1.0,0.0,1.0); }\n";
// カメラの絵（JPEGを展開したY/Cb/Cr、BT.601 full range、色差は間引かれたまま）を出力の大きさ（os）へ拡大して、
// エンコーダのY面（R8）・UV面（GR88、R=Cb・G=Cr）へ直接書く。limited rangeへ直す（Y=16+219/255・C=128+224/255）
static const char *FS_CAM_Y =
    "#version 300 es\nprecision highp float; uniform sampler2D ty; uniform vec2 sy; uniform vec2 os; out vec4 o;\n"
    "void main(){ o=vec4(0.0627+0.8588*texture(ty,gl_FragCoord.xy/os*sy).r,0.0,0.0,1.0); }\n";
static const char *FS_CAM_UV =
    "#version 300 es\nprecision highp float; uniform sampler2D tu; uniform sampler2D tv; uniform vec2 sc; uniform vec2 os; out vec4 o;\n"
    "void main(){ vec2 q=gl_FragCoord.xy/os*sc;\n"
    "  o=vec4(0.5+0.8784*(texture(tu,q).r-0.5), 0.5+0.8784*(texture(tv,q).r-0.5), 0.0, 1.0); }\n";
// レンズの歪みの補正＋ズーム（lens.json があるときだけこちらを使う。PCの tools/lens_view/lens_view.py と同じ計算で、
// OpenCVの initUndistortRectifyMap の k1・k2 だけのモデル）。出力の点 p（0〜1、上が0）から、カメラの絵のどこを取るかを求める。
// lk=(k1, k2, f, zoom)・lc=(カメラの幅, 高さ, shift_x, shift_y)。f は画素。絵の外は黒（Y=16・UV=128）
#define LENS_GLSL \
    "uniform vec4 lk; uniform vec4 lc;\n" \
    "bool lens(vec2 p, out vec2 s){ vec2 c=lc.xy*0.5-lc.zw*lc.xy*lk.w; vec2 n=(p*lc.xy-c)/(lk.z*lk.w);\n" \
    "  float r2=dot(n,n); n*=1.0+lk.x*r2+lk.y*r2*r2; s=(n*lk.z+lc.xy*0.5)/lc.xy;\n" \
    "  return s.x>=0.0 && s.y>=0.0 && s.x<=1.0 && s.y<=1.0; }\n"
static const char *FS_CAM_Y_LENS =
    "#version 300 es\nprecision highp float; uniform sampler2D ty; uniform vec2 sy; uniform vec2 os; out vec4 o;\n" LENS_GLSL
    "void main(){ vec2 s; float y=lens(gl_FragCoord.xy/os,s) ? texture(ty,s*sy).r : 0.0; o=vec4(0.0627+0.8588*y,0.0,0.0,1.0); }\n";
static const char *FS_CAM_UV_LENS =
    "#version 300 es\nprecision highp float; uniform sampler2D tu; uniform sampler2D tv; uniform vec2 sc; uniform vec2 os; out vec4 o;\n" LENS_GLSL
    "void main(){ vec2 s; if(!lens(gl_FragCoord.xy/os,s)){ o=vec4(0.5,0.5,0.0,1.0); return; } vec2 q=s*sc;\n"
    "  o=vec4(0.5+0.8784*(texture(tu,q).r-0.5), 0.5+0.8784*(texture(tv,q).r-0.5), 0.0, 1.0); }\n";
// 画角を決めるときのプレビュー（tools/lens_view/lens_preview.py が頼んでいる間だけ）。録る絵（エンコーダのY面・UV面、
// 計器込み）を小さくしてRGBに戻す。pp=(幅, 高さ, 映像の行数/面の行数)。面の行0が絵の上端
static const char *FS_PREVIEW =
    "#version 300 es\nprecision highp float; uniform sampler2D py; uniform sampler2D puv; uniform vec3 pp; out vec4 o;\n"
    "void main(){ vec2 p=gl_FragCoord.xy/pp.xy; p.y*=pp.z; float y=1.1644*(texture(py,p).r-0.0627); vec2 c=texture(puv,p).rg-0.5;\n"
    "  o=vec4(y+1.596*c.y, y-0.392*c.x-0.813*c.y, y+2.017*c.x, 1.0); }\n";
#define PV_W 640
#define PV_H 360
#define PV_REQ "/dev/shm/ecologger-preview.req"   // プレビューが1秒ごとに触る。4秒触られなければ書き出しをやめる
#define PV_OUT "/dev/shm/ecologger-preview.rgba"  // "EPV1"・幅・高さ（各4バイト）・通し番号（4バイト）＋RGBA
// 計器（1920x1080の上での座標・上端が0。出力が720pでもそのまま縮む）。1枚分の四角形をためて、面ごとに1回で描く。
// 頂点ごとに色を持ち、一覧表の座標が負なら塗りつぶし、そうでなければ一覧表の濃さを不透明度にする（文字）。
// 色はRGBで持ち、描く面（plane：0=Y、1=UV）の値（BT.601 limited range）へここで直す。YもUVもRGBの一次式なので、
// 半透明の重ねも面ごとに正しく混ざる
static const char *VS_HUD =
    "#version 300 es\nlayout(location=0) in vec2 a; layout(location=1) in vec2 t; layout(location=2) in vec4 c;\n"
    "out vec2 uv; out vec4 col;\n"
    "void main(){ uv=t; col=c; gl_Position=vec4(a.x/960.0-1.0, a.y/540.0-1.0, 0.0, 1.0); }\n";
static const char *FS_HUD =
    "#version 300 es\nprecision mediump float; uniform sampler2D atlas; uniform int plane; in vec2 uv; in vec4 col; out vec4 o;\n"
    "void main(){ float al=col.a*(uv.x<0.0 ? 1.0 : texture(atlas,uv).r);\n"
    "  o = plane==0 ? vec4(0.0627+dot(col.rgb,vec3(0.257,0.504,0.098)), 0.0, 0.0, al)\n"
    "               : vec4(0.5+dot(col.rgb,vec3(-0.148,-0.291,0.439)), 0.5+dot(col.rgb,vec3(0.439,-0.368,-0.071)), 0.0, al); }\n";

// ---------------------------------------------------------------- 計器の描画（組み立ては hud_layout.h）
static GLuint p_hud, vao_hud, vbo_hud, t_atlas;
static GLint u_plane;

// 文字の一覧表を読み、寸法を hud_layout.h の cell_w 等へ入れてGPUへ送る
static void load_font(const char *path) {
    FILE *f = fopen(path, "rb"); if (!f) DIE("open %s", path);
    char line[256]; int w = 0, h = 0, maxv = 0;
    if (!fgets(line, sizeof line, f) || strncmp(line, "P5", 2)) DIE("%s: not P5", path);
    while (fgets(line, sizeof line, f)) {
        if (line[0] == '#') { sscanf(line, "# atlas %d %d %d %d %d", &cell_w, &cell_h, &first_ch, &n_ch, &atlas_cols); continue; }
        if (!w) { sscanf(line, "%d %d", &w, &h); continue; }
        sscanf(line, "%d", &maxv); break;
    }
    if (!cell_w || !w || maxv != 255) DIE("%s: header", path);
    uint8_t *px = malloc((size_t)w * h);
    if (fread(px, 1, (size_t)w * h, f) != (size_t)w * h) DIE("%s: short", path);
    fclose(f);
    atlas_w = w; atlas_h = h;
    t_atlas = tex(GL_R8, w, h, GL_LINEAR);
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RED, GL_UNSIGNED_BYTE, px);
    free(px);
    printf("font %s: %dx%d cell %dx%d\n", path, w, h, cell_w, cell_h);
}

// ---- 計器の設定（hud.ini）を選んで読む。録画中も約1秒ごとに呼び、書き換わっていれば読み直す
static const char *hud_path, *hud_default_path, *hud_status_path;
static char hud_loaded[512], hud_bad[512];  // 今の配置を読んだファイル・読めなかったファイル（直されるまで読み直さない）
static struct stat hud_st, hud_bad_st;
static int hud_nofile;

static int same_file(const struct stat *a, const struct stat *b) {
    return a->st_ino == b->st_ino && a->st_size == b->st_size && a->st_mtim.tv_sec == b->st_mtim.tv_sec && a->st_mtim.tv_nsec == b->st_mtim.tv_nsec;
}

// 読んだ結果を OVERLAY_HUD_STATUS のファイルへ書く（tools/video_hud/hud_apply.py が読む）。
// loaded・ino・size は今の配置を読んだファイル、bad・bad_ino・bad_size は読めなかったファイル（無ければ空と0）
static void hud_write_status(const char *error) {
    if (!hud_status_path) return;
    char tmp[600]; snprintf(tmp, sizeof tmp, "%s.tmp", hud_status_path);
    FILE *f = fopen(tmp, "w"); if (!f) return;
    time_t t = time(NULL); struct tm lt; localtime_r(&t, &lt);
    char at[40]; strftime(at, sizeof at, "%Y-%m-%dT%H:%M:%S%z", &lt);
    // version：2 ＝ 針のメーター・弧・コース図・calc.〜 に対応（2026-11-04）。無ければ1（hud_apply.py が見る）
    fprintf(f, "version=2\nat=%s\nloaded=%s\nino=%llu\nsize=%lld\nitems=%d\nbad=%s\nbad_ino=%llu\nbad_size=%lld\nerror=%s\n", at, hud_loaded,
            (unsigned long long)hud_st.st_ino, (long long)hud_st.st_size, hud_cur ? hud_cur->n : 0, hud_bad,
            hud_bad[0] ? (unsigned long long)hud_bad_st.st_ino : 0ULL, hud_bad[0] ? (long long)hud_bad_st.st_size : 0LL, error ? error : "");
    fclose(f); rename(tmp, hud_status_path);
}

static int hud_load(const char *path, const struct stat *st, char *err, size_t errn) {
    if (st->st_size > 256 << 10) { snprintf(err, errn, "%s: 大きすぎる", path); return 0; }
    FILE *f = fopen(path, "rb"); if (!f) { snprintf(err, errn, "%s: 開けない", path); return 0; }
    char *src = calloc(1, st->st_size + 1);
    size_t n = fread(src, 1, st->st_size, f); fclose(f); src[n] = 0;
    struct hud *h = malloc(sizeof *h);
    char e[400];
    int ok = hud_parse(src, h, e, sizeof e);
    free(src);
    if (!ok) { snprintf(err, errn, "%s %s", path, e); free(h); return 0; }
    pthread_mutex_lock(&tmu);
    struct hud *old = hud_cur; hud_cur = h; hud_gen++;
    for (int i = 0; i < HUD_REFS; i++) tvals[i] = NAN;
    pthread_mutex_unlock(&tmu);
    free(old);
    snprintf(hud_loaded, sizeof hud_loaded, "%s", path); hud_st = *st;
    printf("hud %s: %d items, %d values\n", path, h->n, h->nref); fflush(stdout);
    return 1;
}

// OVERLAY_HUD のファイルがあればそれ、無ければ OVERLAY_HUD_DEFAULT。前に読んだときから変わっていれば読み直す
static void hud_check(void) {
    struct stat st; const char *path = NULL;
    if (hud_path && !stat(hud_path, &st)) path = hud_path;
    else if (hud_default_path && !stat(hud_default_path, &st)) path = hud_default_path;
    if (!path) {
        if (!hud_cur && !hud_nofile) { hud_nofile = 1; fprintf(stderr, "hud: 設定ファイルが無い\n"); hud_write_status("設定ファイルが無い（計器を描かずに録っている）"); }
        return;
    }
    if (!strcmp(path, hud_loaded) && same_file(&st, &hud_st)) return;  // 今のまま
    if (!strcmp(path, hud_bad) && same_file(&st, &hud_bad_st)) return;  // 前に読めなかったまま
    char err[1200];
    if (hud_load(path, &st, err, sizeof err)) { hud_bad[0] = 0; hud_write_status(NULL); return; }
    fprintf(stderr, "hud: %s\n", err);
    snprintf(hud_bad, sizeof hud_bad, "%s", path); hud_bad_st = st;
    if (hud_cur) strcat(err, "（前の配置のまま）");
    else if (path == hud_path && hud_default_path && !stat(hud_default_path, &st)) {
        char e2[600];
        if (hud_load(hud_default_path, &st, e2, sizeof e2)) strcat(err, "（元の配置 hud_default.ini を使っている）");
        else { fprintf(stderr, "hud: %s\n", e2); strcat(err, "（元の配置も読めないので、計器を描かずに録っている）"); }
    } else strcat(err, "（計器を描かずに録っている）");
    hud_write_status(err);
}

// ---- レンズの歪みの補正＋ズーム（OVERLAY_LENS の lens.json。PCの tools/lens_view/ で決めて保存したもの）。
// ファイルが無い・読めない・値が範囲の外なら補正しない（今までと同じ描き方）。録画中も約1秒ごとに見て、変われば次のコマから
static const char *lens_path;
static struct stat lens_st;
static int lens_on, lens_seen, lens_missing;  // lens_seen：前に見たときファイルがあったか・lens_missing：無いことを書いた
static float lens_k[4], lens_c[4];  // シェーダーの lk・lc

static int lens_load(const char *path, char *msg, size_t n) {
    char js[2048]; FILE *f = fopen(path, "r");
    if (!f) { snprintf(msg, n, "開けない"); return 0; }
    size_t len = fread(js, 1, sizeof js - 1, f); fclose(f); js[len] = 0;
    const double k1 = jnum(js, NULL, "k1"), k2 = jnum(js, NULL, "k2"), zoom = jnum(js, NULL, "zoom"),
                 fr = jnum(js, NULL, "f_ratio"), sx = jnum(js, NULL, "shift_x"), sy = jnum(js, NULL, "shift_y");
    if (!(k1 >= -1 && k1 <= 1 && k2 >= -1 && k2 <= 1 && zoom >= 1 && zoom <= 4 && fr >= .2 && fr <= 3 &&
          sx >= -.5 && sx <= .5 && sy >= -.5 && sy <= .5)) {
        snprintf(msg, n, "値が無いか範囲の外（k1=%g k2=%g zoom=%g f_ratio=%g shift=%g,%g）", k1, k2, zoom, fr, sx, sy);
        return 0;
    }
    lens_k[0] = k1; lens_k[1] = k2; lens_k[2] = fr * CAM_W; lens_k[3] = zoom;
    lens_c[0] = CAM_W; lens_c[1] = CAM_H; lens_c[2] = sx; lens_c[3] = sy;
    snprintf(msg, n, "k1=%.3f k2=%.3f zoom=%.2f f_ratio=%.2f shift=%.2f,%.2f", k1, k2, zoom, fr, sx, sy);
    return 1;
}

// 読んだ結果を <lens.json>.status へ書く（PCの Apply-Lens.cmd が、送ったファイルを読めたかをこれで確かめる）
static void lens_write_status(const struct stat *st, const char *msg) {
    char sp[600]; snprintf(sp, sizeof sp, "%s.status", lens_path);
    FILE *f = fopen(sp, "w"); if (!f) return;
    time_t t = time(NULL); char at[32]; strftime(at, sizeof at, "%Y-%m-%d %H:%M:%S", localtime(&t));
    fprintf(f, "on=%d\nino=%lu\nsize=%lld\nat=%s\nmsg=%s\n", lens_on,
            st ? (unsigned long)st->st_ino : 0UL, st ? (long long)st->st_size : -1LL, at, msg);
    fclose(f);
}

static void lens_check(void) {
    struct stat st;
    if (!lens_path) return;
    if (stat(lens_path, &st)) {
        if (lens_seen || lens_on) fprintf(stderr, "lens: %s が無いので補正しない\n", lens_path);
        if (!lens_missing) { lens_missing = 1; lens_seen = lens_on = 0; lens_write_status(NULL, "ファイルが無い（補正しない）"); }
        return;
    }
    lens_missing = 0;
    if (lens_seen && same_file(&st, &lens_st)) return;
    lens_seen = 1; lens_st = st;
    char msg[256];
    lens_on = lens_load(lens_path, msg, sizeof msg);
    fprintf(stderr, "lens: %s %s\n", lens_on ? "補正する" : "補正しない：", msg);
    lens_write_status(&st, msg);
}

// ---------------------------------------------------------------- 保存（MPEG-TS／素のH.264）と1秒ごとの時刻
static FILE *csv;  // out（.tsの書き出し先）と put・ts_frame 等は ts_mux.h
static const char *out_pat;
static char out_name[512];
static int ts_mode, seg_on, low_space, seg_frames, encoded, idr_count, header_inserted;
static double seg_len = 600, seg_t0, min_free_mb = 1024, bitrate_mbps = 10;
static int64_t seg_us0;
static uint8_t seq_hdr[256];
static size_t seq_len;
// エンコーダへ渡した時刻（µs）→ その枚のカメラの時刻（CLOCK_MONOTONIC）と、本体の時計でのUTC
static struct { int64_t us; double mono, host; } stamps[64];
// 走行（%の書式のとき）：置き場・名前の書式（拡張子を除く）と拡張子・今の走行の名前・章の番号・起動の番号
static char vdir[512], ldir[600], name_pat[256], name_ext[16] = ".ts", sess[64], boot_id[64];  // ldir：走行記録の置き場
static int chapter, sess_gnss, clock_announced;  // sess_gnss：走行の名前がGNSSの時刻か
static double rec_cam_t0;  // 映像の最初の枚のカメラの時刻（CLOCK_MONOTONIC）。音の時刻をこれからの秒にする
static double sess_mono, rec_written = -1e9;      // 走行の最初の枚の時刻（CLOCK_MONOTONIC。同じ起動なら別の録画とも比べられる）

// その枚のUTC。GNSSの時刻が分かっていればそれで（*gnss=1）、無ければ本体の時計で。*hostは本体の時計でのUTC
static double frame_utc(int64_t us, int *gnss, double *host, double *mono_out) {
    double mono = now(), off; *host = wall();
    for (int i = 0; i < 64; i++) if (stamps[i].us == us) { mono = stamps[i].mono; *host = stamps[i].host; break; }
    if (mono_out) *mono_out = mono;
    *gnss = gnss_offset(&off);
    return *gnss ? mono + off : *host;
}

static void iso_utc(double u, char *b, size_t n) {
    time_t s = (time_t)floor(u); struct tm g; gmtime_r(&s, &g);
    char t[32]; strftime(t, sizeof t, "%Y-%m-%dT%H:%M:%S", &g);
    snprintf(b, n, "%s.%03dZ", t, (int)((u - s) * 1000));
}

// 出力名の拡張子を.csvにした名前
static void csv_name(const char *ts, char *b, size_t n) {
    snprintf(b, n, "%s", ts);
    char *dot = strrchr(b, '.'); if (dot && !strchr(dot, '/')) *dot = 0;
    strncat(b, ".csv", n - strlen(b) - 1);
}

// 録画の今の状態を置き場の .recording へ（一時ファイルから置き換えるので、読む側が書きかけを見ることはない）。
// EcoCapture・PCの回収アプリは、起動の番号とbt（起動からの秒）で、書いている途中のファイルと今の走行を見分ける（video_store.h）
static void rec_state(void) {
    if (!seg_on || !sess[0]) return;
    char p[600], t[610]; snprintf(p, sizeof p, "%s/.recording", vdir); snprintf(t, sizeof t, "%s.tmp", p);
    FILE *f = fopen(t, "w"); if (!f) return;
    const char *base = strrchr(out_name, '/');
    fprintf(f, "boot_id=%s\nsession=%s\nfile=%s\nbt=%.3f\npid=%d\nmbps=%g\nmin_free_mb=%g\nsegment_min=%g\n",
            boot_id, sess, base ? base + 1 : out_name, vs_boottime(), (int)getpid(), bitrate_mbps, min_free_mb, seg_len / 60);
    if (fclose(f) == 0) rename(t, p);
    rec_written = now();
}

// <走行>.session：その走行の起動の番号・最初の枚の時刻（CLOCK_MONOTONIC）・名前の時計（gnss/host）
static void sess_write(void) {
    char p[600]; snprintf(p, sizeof p, "%s/%s.session", vdir, sess);
    FILE *f = fopen(p, "w"); if (!f) return;
    fprintf(f, "boot_id=%s\nstart_mono=%.3f\nclock=%s\n", boot_id, sess_mono, sess_gnss ? "gnss" : "host");
    fclose(f);
}

static void sess_name(double u, char *b, size_t n) { time_t s = (time_t)u; struct tm lt; localtime_r(&s, &lt); strftime(b, n, name_pat, &lt); }

// その名前の走行が置き場にもうあるか（.session か、その名前で始まる章）
static int sess_exists(const char *name) {
    char p[600]; struct stat st; snprintf(p, sizeof p, "%s/%s.session", vdir, name);
    if (!lstat(p, &st)) return 1;
    DIR *d = opendir(vdir); struct dirent *e; int found = 0; size_t l = strlen(name);
    while (d && !found && (e = readdir(d))) found = !strncmp(e->d_name, name, l) && e->d_name[l] == '_';
    if (d) closedir(d);
    return found;
}

// 起動したとき：前の録画が同じ起動で、止まってからVS_GAP_S以内なら（カメラの抜き差し）、その走行の次の章から続ける
static void sess_resume(void) {
    char p[600], text[4096], v[256], s[256];
    snprintf(p, sizeof p, "%s/.recording", vdir); vs_read(p, text, sizeof text);
    vs_kv(text, "boot_id", v, sizeof v); if (!boot_id[0] || strcmp(v, boot_id)) return;
    vs_kv(text, "bt", v, sizeof v); char *end; double bt = strtod(v, &end);
    if (!v[0] || *end || !(vs_boottime() - bt < VS_GAP_S)) return;
    vs_kv(text, "session", s, sizeof s); if (!s[0] || strlen(s) >= sizeof sess) return;
    snprintf(p, sizeof p, "%s/%s.session", vdir, s); if (!vs_read(p, text, sizeof text)) return;
    vs_kv(text, "start_mono", v, sizeof v); sess_mono = atof(v);
    vs_kv(text, "clock", v, sizeof v); sess_gnss = !strcmp(v, "gnss");
    snprintf(sess, sizeof sess, "%s", s);
    DIR *d = opendir(vdir); struct dirent *e; chapter = 0;
    while (d && (e = readdir(d))) {
        size_t l = strlen(e->d_name); char ss[256]; int k;
        if (l < 3 || strcmp(e->d_name + l - 3, ".ts")) continue;
        vs_session_of(e->d_name, ss, sizeof ss, &k);
        if (!strcmp(ss, sess) && k > chapter) chapter = k;
    }
    if (d) closedir(d);
    printf("session %s continues from chapter %d (restarted within %d s)\n", sess, chapter + 1, VS_GAP_S); fflush(stdout);
}

// 次の章（と時刻のcsv）を開く。usはそのファイルの最初の枚（キーフレーム）の時刻。新しい走行なら、その枚の時刻で走行の名前を決める
static void seg_open(int64_t us) {
    if (out) fclose(out);
    if (csv) fclose(csv);
    csv = NULL;
    int g; double host, mono, u = frame_utc(us, &g, &host, &mono);
    if (seg_on) {
        if (!sess[0]) {  // 同じ名前の走行があれば（同じ秒にやり直した等）1秒ずつずらす
            sess_mono = mono; sess_gnss = g; chapter = 0;
            for (int k = 0; k < 60; k++) { sess_name(u + k, sess, sizeof sess); if (!sess_exists(sess)) break; }
            sess_write();
        }
        chapter++;
        snprintf(out_name, sizeof out_name, "%s/%s_%02d%s", vdir, sess, chapter, name_ext);
    } else snprintf(out_name, sizeof out_name, "%s", out_pat);
    out = fopen(out_name, "wb"); if (!out) DIE("open %s", out_name);
    char cn[sizeof out_name + 8]; csv_name(out_name, cn, sizeof cn);
    // utc：その秒の頭の枚の時刻（GNSSの時刻、まだ分からなければ本体の時計）。clock：どちらで付けたか。host_utc：本体の時計
    csv = fopen(cn, "w"); if (csv) fprintf(csv, "frame,video_s,utc,clock,host_utc\n");
    seg_t0 = now(); seg_us0 = us; seg_frames = 0;
    printf("file %s\n", out_name); fflush(stdout);
    rec_state();
}

// GNSSの時刻が分かったら、本体の時計で名前を付けた走行のファイル（前の録画の章も、書いている途中の章も）を、
// GNSSの時刻の走行の名前へ付け直す（章の番号・.csv・印・.session・.keep もそのまま）
static void rename_by_gnss(void) {
    double off;
    if (!seg_on || !sess[0] || sess_gnss || !gnss_offset(&off)) return;
    sess_gnss = 1;  // 付け直せなくても（同じ名前の走行がある等）もう試さない
    char nn[64]; sess_name(sess_mono + off, nn, sizeof nn);
    if (strcmp(nn, sess) && !sess_exists(nn)) {
        char names[512][256]; int k = 0; const size_t l = strlen(sess);
        DIR *d = opendir(vdir); struct dirent *e;
        while (d && k < 512 && (e = readdir(d)))
            if (!strncmp(e->d_name, sess, l) && (e->d_name[l] == '_' || e->d_name[l] == '.') && strlen(e->d_name) < sizeof names[0])
                snprintf(names[k++], sizeof names[0], "%s", e->d_name);
        if (d) closedir(d);
        const char *cur = strrchr(out_name, '/'); cur = cur ? cur + 1 : out_name;
        char renamed_cur[512] = "";
        for (int i = 0; i < k; i++) {
            char a[1024], b[1024]; snprintf(a, sizeof a, "%s/%s", vdir, names[i]); snprintf(b, sizeof b, "%s/%s%s", vdir, nn, names[i] + l);
            if (rename(a, b)) continue;
            if (!strcmp(names[i], cur)) snprintf(renamed_cur, sizeof renamed_cur, "%s", b);
        }
        printf("renamed session %s -> %s (GNSS time, %d files)\n", sess, nn, k); fflush(stdout);
        if (renamed_cur[0]) snprintf(out_name, sizeof out_name, "%s", renamed_cur);
        snprintf(sess, sizeof sess, "%s", nn);
    }
    sess_write(); rec_state();
}

static double free_mb(void) {
    struct statvfs sv;
    return fstatvfs(fileno(out), &sv) ? 1e18 : (double)sv.f_bavail * sv.f_frsize / 1048576.0;
}

// 音（audio_cap.h）をTSへ。t：その頭の時刻（CLOCK_MONOTONIC）。映像と同じく、最初の枚からの時刻＋0.5秒をPTSにする
static void ac_write(const uint8_t *es, size_t n, double t) {
    if (out) ts_audio_pes(es, n, (uint64_t)llround((t - rec_cam_t0) * 90000) + 45000);
}

// エンコーダから出た1枚分。キーフレームの所でファイルの切り替え・書き出しの促し・空きの確認・時刻の記録をする
static void emit(const uint8_t *p, size_t n, int64_t us) {
    int has_sps = 0, idr = 0, slice = 0;
    for (size_t i = 0; i + 3 < n; i++) {
        if (p[i] || p[i + 1] || p[i + 2] != 1) continue;
        int t = p[i + 3] & 0x1f;
        if (t == 7) has_sps = 1;
        if (t == 7 && !seq_len) {  // 最初のSPSからスライスの手前（無ければ最後）までを控える
            size_t s = i > 0 && p[i - 1] == 0 ? i - 1 : i, e = i + 3;
            while (e + 3 < n && !(p[e] == 0 && p[e + 1] == 0 && p[e + 2] == 1 && ((p[e + 3] & 0x1f) == 5 || (p[e + 3] & 0x1f) == 1))) e++;
            if (e + 3 >= n) e = n;
            if (e > s && e - s <= sizeof seq_hdr) { memcpy(seq_hdr, p + s, e - s); seq_len = e - s; if (seq_hdr[seq_len - 1] == 0) seq_len--; }
        }
        if (t == 5) idr = 1;
        if (t == 5 || t == 1) slice = 1;
    }
    if (!slice) return;  // SPS・PPSだけの入れ物（最初の1回）。控えたので捨てる
    encoded++;
    if (idr) {
        idr_count++;
        if (!out || (seg_on && now() - seg_t0 >= seg_len)) seg_open(us);
        else { fflush(out); sync_file_range(fileno(out), 0, 0, SYNC_FILE_RANGE_WRITE); }  // 待たずに書き出しを始めさせる
        if (now() - rec_written >= 5) rec_state();
        if (seg_on && free_mb() < min_free_mb) vs_make_room(vdir, ldir, min_free_mb, free_mb, "recorder", boot_id, vs_boottime(), wall());
        if (free_mb() < min_free_mb) { low_space = 1; quit = 1; }
        int g; double host, u = frame_utc(us, &g, &host, NULL);
        if (csv) {
            char a[40], b[40]; iso_utc(u, a, sizeof a); iso_utc(host, b, sizeof b);
            fprintf(csv, "%d,%.3f,%s,%s,%s\n", seg_frames, (us - seg_us0) / 1e6, a, g ? "gnss" : "host", b);
            fflush(csv);
        }
        if (g && !clock_announced) {
            clock_announced = 1;
            printf("clock: GNSS time found (the host clock is off by %+.3f s)\n", host - u); fflush(stdout);
        }
        rename_by_gnss();
        if (ts_mode) ts_tables();
    }
    if (!out) return;
    static uint8_t tmp[4 << 20];
    if (idr && !has_sps && seq_len && n + seq_len <= sizeof tmp) {  // SPS・PPSが付いていないIDRには控えを前に付ける
        memcpy(tmp, seq_hdr, seq_len); memcpy(tmp + seq_len, p, n); p = tmp; n += seq_len; header_inserted++;
    }
    if (ts_audio) ac_drain(rec_cam_t0, 0, ac_write);  // たまった音を、この枚の前に書く
    if (ts_mode) { uint64_t t90 = (uint64_t)us * 9 / 100; ts_frame(p, n, t90 + 45000, t90, idr); }  // PTSはPCRより0.5秒先
    else put(p, n);
    seg_frames++;
}

// ---------------------------------------------------------------- エンコーダ
struct vbuf { void *p; size_t len; };
static int fd, t1 = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE, t2 = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
static struct vbuf ob[NOUT], cb[NCAP];
static int freeidx[NOUT], nfree, eos;
static double s_emit;

static void drain(int block) {
    struct pollfd pf = { .fd = fd, .events = POLLIN | POLLOUT };
    if (poll(&pf, 1, block ? 1000 : 0) <= 0) return;
    for (;;) {
        struct v4l2_plane pl[1] = {0};
        struct v4l2_buffer b = { .type = t2, .memory = V4L2_MEMORY_MMAP, .length = 1, .m.planes = pl };
        if (xioctl(fd, VIDIOC_DQBUF, &b)) break;
        // エンコーダのバッファはCPUのキャッシュが効かないので、1バイトずつ読むと遅い（50KBで約4ms）。先にまとめて写す
        static uint8_t es[1 << 20];
        double a = now();
        size_t n = pl[0].bytesused < sizeof es ? pl[0].bytesused : sizeof es;
        if (n) { memcpy(es, cb[b.index].p, n); emit(es, n, (int64_t)b.timestamp.tv_sec * 1000000 + b.timestamp.tv_usec); }
        s_emit += now() - a;
        if (b.flags & V4L2_BUF_FLAG_LAST) { eos = 1; break; }
        xioctl(fd, VIDIOC_QBUF, &b);
    }
    for (;;) {
        struct v4l2_plane pl[1] = {0};
        struct v4l2_buffer b = { .type = t1, .memory = V4L2_MEMORY_MMAP, .length = 1, .m.planes = pl };
        if (xioctl(fd, VIDIOC_DQBUF, &b)) break;
        freeidx[nfree++] = b.index;
    }
}

static void set_ctrl(uint32_t id, int value, const char *name) {
    struct v4l2_control c = { .id = id, .value = value };
    if (xioctl(fd, VIDIOC_S_CTRL, &c)) fprintf(stderr, "warn: %s not set (errno=%d)\n", name, errno);
}

static int open_by_name(const char *name) {
    char path[32];
    for (int i = 0; i < 64; i++) {
        snprintf(path, sizeof path, "/dev/video%d", i);
        int f = open(path, O_RDWR | O_NONBLOCK); if (f < 0) continue;
        struct v4l2_capability cap = {0};
        if (!xioctl(f, VIDIOC_QUERYCAP, &cap) && !strcmp((char *)cap.card, name)) { printf("%s: %s\n", name, path); return f; }
        close(f);
    }
    DIE("%s が見つからない", name);
}

// ---------------------------------------------------------------- カメラ（UVC・MJPEG）と展開スレッド
static int cfd = -1;
static struct vbuf camb[NCAM];
static uint8_t *src_jpeg; static size_t src_len;  // file: のときのJPEG
static struct jpeg_decompress_struct jd;
static struct jpeg_error_mgr jerr;
static uint8_t *scratch[3];  // 展開先（成分ごと、幅・高さは8の倍数へ切り上げ。CPUのキャッシュが効く普通のメモリ）
// GPUと共有するメモリ（2枚を交互に使う）。展開した絵をここへ写すと、GPUはそのまま読める（glTexSubImageの転送が要らない）。
// msmのGEMを書き込み結合（WC）で確保し、dmabufにしてLINEARで取り込む。展開を直接ここへしないのは、libjpegの書き方
// （8バイトずつ行をまたぐ）がWCのメモリでは遅いため。まとめて写すほうが速い
static int rfd = -1;
static uint8_t *slot[2][3];
static int slot_fd[2][3];
static double slot_ts[2], slot_utc[2];  // その枚のカメラの時刻（CLOCK_MONOTONIC）とUTC
static int pw[3], ph[3];
static float chroma_w, chroma_h;  // 色差の大きさ（最初の1枚で控える。jdはGPU側から読まない）

static uint8_t *gem_alloc(size_t size, int *dmafd) {
    struct drm_msm_gem_new gn = { .size = size, .flags = MSM_BO_WC };
    if (xioctl(rfd, DRM_IOCTL_MSM_GEM_NEW, &gn)) DIE("MSM_GEM_NEW");
    struct drm_msm_gem_info gi = { .handle = gn.handle, .info = MSM_INFO_GET_OFFSET };
    if (xioctl(rfd, DRM_IOCTL_MSM_GEM_INFO, &gi)) DIE("MSM_GEM_INFO");
    uint8_t *p = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, rfd, gi.value);
    if (p == MAP_FAILED) DIE("mmap gem");
    struct drm_prime_handle pr = { .handle = gn.handle, .flags = DRM_CLOEXEC | DRM_RDWR };
    if (xioctl(rfd, DRM_IOCTL_PRIME_HANDLE_TO_FD, &pr)) DIE("PRIME_HANDLE_TO_FD");
    *dmafd = pr.fd;
    return p;
}

static void cam_open(const char *dev) {
    if (!strncmp(dev, "file:", 5)) {
        FILE *f = fopen(dev + 5, "rb"); if (!f) DIE("open %s", dev + 5);
        fseek(f, 0, SEEK_END); src_len = ftell(f); fseek(f, 0, SEEK_SET);
        src_jpeg = malloc(src_len);
        if (fread(src_jpeg, 1, src_len, f) != src_len) DIE("read %s", dev + 5);
        fclose(f);
    } else {
        cfd = open(dev, O_RDWR); if (cfd < 0) DIE("open %s", dev);
        struct v4l2_format f = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE };
        f.fmt.pix.width = CAM_W; f.fmt.pix.height = CAM_H; f.fmt.pix.pixelformat = V4L2_PIX_FMT_MJPEG;
        if (xioctl(cfd, VIDIOC_S_FMT, &f)) DIE("camera S_FMT");
        if (f.fmt.pix.width != CAM_W || f.fmt.pix.height != CAM_H || f.fmt.pix.pixelformat != V4L2_PIX_FMT_MJPEG)
            DIE("カメラが %dx%d MJPEG を受け付けない", CAM_W, CAM_H);
        struct v4l2_streamparm sp = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE };
        sp.parm.capture.timeperframe.numerator = 1; sp.parm.capture.timeperframe.denominator = 30;
        xioctl(cfd, VIDIOC_S_PARM, &sp);
        struct v4l2_requestbuffers rq = { .count = NCAM, .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP };
        if (xioctl(cfd, VIDIOC_REQBUFS, &rq)) DIE("camera REQBUFS");
        for (unsigned i = 0; i < rq.count && i < NCAM; i++) {
            struct v4l2_buffer b = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP, .index = i };
            if (xioctl(cfd, VIDIOC_QUERYBUF, &b)) DIE("camera QUERYBUF");
            camb[i].len = b.length; camb[i].p = mmap(NULL, b.length, PROT_READ | PROT_WRITE, MAP_SHARED, cfd, b.m.offset);
            if (camb[i].p == MAP_FAILED) DIE("camera mmap");
            if (xioctl(cfd, VIDIOC_QBUF, &b)) DIE("camera QBUF");
        }
        int t = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        if (xioctl(cfd, VIDIOC_STREAMON, &t)) DIE("camera STREAMON");
    }
    jd.err = jpeg_std_error(&jerr); jpeg_create_decompress(&jd);
}

static void cam_frame(int s, double *t_wait, double *t_dec, double *t_copy) {
    uint8_t **pln = scratch;
    double a = now(), ts;
    struct v4l2_buffer b = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP };
    const uint8_t *jp = src_jpeg; size_t jn = src_len;
    if (cfd >= 0) {
        if (xioctl(cfd, VIDIOC_DQBUF, &b)) DIE("camera DQBUF");
        jp = camb[b.index].p; jn = b.bytesused;
        // UVCはCLOCK_MONOTONICで時刻を付ける（そうでなければ受け取った時刻で代える）
        ts = (b.flags & V4L2_BUF_FLAG_TIMESTAMP_MASK) == V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC
             ? b.timestamp.tv_sec + b.timestamp.tv_usec * 1e-6 : now();
    } else {  // file: は30fpsの刻みに合わせて出す
        static double t0; static long k;
        if (!t0) t0 = a;
        ts = t0 + k++ / 30.0;
        if (ts > a) usleep((ts - a) * 1e6);
    }
    double c = now(); *t_wait += c - a;
    slot_ts[s] = ts; slot_utc[s] = wall() - (c - ts);
    jpeg_mem_src(&jd, jp, jn);  // UVCのMJPEGはハフマン表を省くが、libjpeg-turboが標準表で補う
    jpeg_read_header(&jd, TRUE);
    jd.raw_data_out = TRUE; jd.do_fancy_upsampling = FALSE; jd.dct_method = JDCT_IFAST;
    jpeg_start_decompress(&jd);
    if (!scratch[0]) {
        if (jd.output_width != CAM_W || jd.output_height != CAM_H) DIE("JPEGが %dx%d ではない", CAM_W, CAM_H);
        for (int i = 0; i < 3; i++) {
            pw[i] = jd.comp_info[i].width_in_blocks * DCTSIZE; ph[i] = jd.comp_info[i].height_in_blocks * DCTSIZE;
            if (pw[i] % 64) DIE("JPEGの幅 %d がGPUで読める並び（64の倍数）でない", pw[i]);
            scratch[i] = malloc((size_t)pw[i] * (ph[i] + 16 * DCTSIZE));
            for (int k = 0; k < 2; k++) slot[k][i] = gem_alloc(((size_t)pw[i] * ph[i] + 4095) & ~(size_t)4095, &slot_fd[k][i]);
        }
        chroma_w = (float)CAM_W * jd.comp_info[1].h_samp_factor / jd.max_h_samp_factor;
        chroma_h = (float)CAM_H * jd.comp_info[1].v_samp_factor / jd.max_v_samp_factor;
    }
    JSAMPROW rows[3][16 * DCTSIZE]; JSAMPARRAY arr[3] = { rows[0], rows[1], rows[2] };
    const int step = jd.max_v_samp_factor * DCTSIZE;
    while (jd.output_scanline < jd.output_height) {
        for (int i = 0; i < 3; i++) {
            int n = jd.comp_info[i].v_samp_factor * DCTSIZE, y0 = jd.output_scanline / step * n;
            for (int r = 0; r < n; r++) rows[i][r] = pln[i] + (size_t)(y0 + r) * pw[i];
        }
        jpeg_read_raw_data(&jd, arr, step);
    }
    jpeg_finish_decompress(&jd);
    if (cfd >= 0 && xioctl(cfd, VIDIOC_QBUF, &b)) DIE("camera QBUF");
    double d = now(); *t_dec += d - c;
    for (int i = 0; i < 3; i++) memcpy(slot[s][i], scratch[i], (size_t)pw[i] * ph[i]);
    *t_copy += now() - d;
}

static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cv = PTHREAD_COND_INITIALIZER;
static int filled[2], dec_frames;
static double d_wait, d_dec, d_copy;
static void *decoder(void *arg) {
    (void)arg;
    for (int f = 0; (!dec_frames || f < dec_frames) && !quit; f++) {
        int s = f & 1;
        pthread_mutex_lock(&mu); while (filled[s] && !quit) pthread_cond_wait(&cv, &mu); pthread_mutex_unlock(&mu);
        if (quit) break;
        cam_frame(s, &d_wait, &d_dec, &d_copy);
        pthread_mutex_lock(&mu); filled[s] = 1; pthread_cond_broadcast(&cv); pthread_mutex_unlock(&mu);
    }
    return NULL;
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s </dev/videoN|file:x.jpg> <out.ts|out.h264|%%Y%%m%%d_%%H%%M%%S.ts> [seconds=60] [font=hud_font_64.pgm]\n", argv[0]); return 1; }
    const int frames = (argc > 3 ? atoi(argv[3]) : 60) * 30;  // 0は止めるまで
    const char *font = argc > 4 ? argv[4] : "hud_font_64.pgm";
    if (getenv("OVERLAY_OUT") && atoi(getenv("OVERLAY_OUT")) == 720) { ow = 1280; oh = 720; }
    demo = getenv("OVERLAY_DEMO") && atoi(getenv("OVERLAY_DEMO"));
    lr_init(&lr, demo ? NULL : getenv("OVERLAY_LAPREF"));  // ベストの周を書くファイル（録画をやり直しても続きから使う）
    static struct lr_demo dd;
    double demo_t0 = 0;  // DEMOは架空のコースを OVERLAY_DEMO_START 秒（既定250＝2周半）走った所から始める（ベストとの差がすぐ出る）
    if (demo) {
        lr_demo_init(&dd);
        demo_t0 = getenv("OVERLAY_DEMO_START") ? atof(getenv("OVERLAY_DEMO_START")) : 250;
        for (double t = 0; t < demo_t0; t += .1) {
            lr_demo_step(&dd, t);
            double lat, lon; lr_demo_pos(&dd, dd.s, &lat, &lon);
            lr_update(&lr, lat, lon, lr_demo_v0(&dd, dd.s) * lr_demo_factor(dd.lap), dd.lap, (dd.t - dd.lap_start) / 60, dd.last / 60, dd.best / 60);
        }
    }
    const int profile = getenv("OVERLAY_PROFILE") && atoi(getenv("OVERLAY_PROFILE"));
    if (getenv("OVERLAY_SEGMENT_MIN")) seg_len = atof(getenv("OVERLAY_SEGMENT_MIN")) * 60;
    if (getenv("OVERLAY_MIN_FREE_MB")) min_free_mb = atof(getenv("OVERLAY_MIN_FREE_MB"));
    if (getenv("OVERLAY_BITRATE_MBPS")) bitrate_mbps = atof(getenv("OVERLAY_BITRATE_MBPS"));
    if (getenv("OVERLAY_TELEMETRY_PORT")) api_port = atoi(getenv("OVERLAY_TELEMETRY_PORT"));
    hud_path = getenv("OVERLAY_HUD"); hud_status_path = getenv("OVERLAY_HUD_STATUS");
    static char def_path[512];  // 既定の配置：OVERLAY_HUD_DEFAULT、無ければ文字の一覧表と同じ場所の hud_default.ini
    if (getenv("OVERLAY_HUD_DEFAULT")) snprintf(def_path, sizeof def_path, "%s", getenv("OVERLAY_HUD_DEFAULT"));
    else { const char *sl = strrchr(font, '/'); snprintf(def_path, sizeof def_path, "%.*shud_default.ini", sl ? (int)(sl - font + 1) : 0, font); }
    hud_default_path = def_path;
    for (int i = 0; i < CLK_N; i++) clk[i].at = -1e9;
    for (int i = 0; i < 64; i++) stamps[i].us = -1;  // まだ使っていない枠（0は最初の枚の時刻なので区別する）
    out_pat = argv[2]; seg_on = strchr(out_pat, '%') != NULL;
    const size_t ol = strlen(out_pat); ts_mode = !(ol > 5 && !strcmp(out_pat + ol - 5, ".h264"));
    signal(SIGINT, on_signal); signal(SIGTERM, on_signal);
    setenv("TZ", "Asia/Tokyo", 0); tzset();
    if (seg_on) {  // <置き場>/<名前の書式><拡張子> に分ける。走行の続きかどうかは .recording で見る
        const char *sl = strrchr(out_pat, '/');
        snprintf(vdir, sizeof vdir, "%.*s", sl ? (int)(sl - out_pat) : 1, sl ? out_pat : ".");
        snprintf(name_pat, sizeof name_pat, "%s", sl ? sl + 1 : out_pat);
        char *dot = strrchr(name_pat, '.'); if (dot) { snprintf(name_ext, sizeof name_ext, "%s", dot); *dot = 0; }
        if (getenv("OVERLAY_LOGS_DIR")) snprintf(ldir, sizeof ldir, "%s", getenv("OVERLAY_LOGS_DIR"));
        else snprintf(ldir, sizeof ldir, "%s/../logs", vdir);
        vs_boot_id(boot_id, sizeof boot_id);
        sess_resume();
    }

    rfd = open("/dev/dri/renderD128", O_RDWR | O_CLOEXEC); if (rfd < 0) DIE("open renderD128");
    cam_open(argv[1]);
    hud_check();  // 走行データのスレッドが値の名前を使うので、その前に読む
    lens_path = getenv("OVERLAY_LENS"); lens_check();
    ts_audio = ts_mode && ac_start();  // 音（OVERLAY_AUDIO。run-video.sh がカメラのマイクを探して渡す）。録れなくても映像は録る
    pthread_t tel_th; pthread_create(&tel_th, NULL, telemetry, NULL);

    // ---- EGL（画面を使わない surfaceless）
    PFNEGLGETPLATFORMDISPLAYEXTPROC getdpy = (void *)eglGetProcAddress("eglGetPlatformDisplayEXT");
    EGLDisplay dpy = getdpy(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
    if (!eglInitialize(dpy, NULL, NULL)) DIE("eglInitialize");
    eglBindAPI(EGL_OPENGL_ES_API);
    EGLint cattr[] = { EGL_CONTEXT_MAJOR_VERSION, 3, EGL_NONE };
    EGLContext ctx = eglCreateContext(dpy, EGL_NO_CONFIG_KHR, EGL_NO_CONTEXT, cattr);
    if (ctx == EGL_NO_CONTEXT || !eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, ctx)) DIE("egl context");

    GLuint p_cy = program(VS_FULL, FS_CAM_Y), p_cuv = program(VS_FULL, FS_CAM_UV);
    glUseProgram(p_cy); glUniform1i(glGetUniformLocation(p_cy, "ty"), 0);
    const GLint u_sy = glGetUniformLocation(p_cy, "sy"), u_osy = glGetUniformLocation(p_cy, "os");
    glUseProgram(p_cuv); glUniform1i(glGetUniformLocation(p_cuv, "tu"), 1); glUniform1i(glGetUniformLocation(p_cuv, "tv"), 2);
    const GLint u_sc = glGetUniformLocation(p_cuv, "sc"), u_osuv = glGetUniformLocation(p_cuv, "os");
    // 歪みの補正つき（lens.json があるときだけ使う）。テクスチャの番号は上と同じ
    GLuint pl_y = program(VS_FULL, FS_CAM_Y_LENS), pl_uv = program(VS_FULL, FS_CAM_UV_LENS);
    glUseProgram(pl_y); glUniform1i(glGetUniformLocation(pl_y, "ty"), 0);
    const GLint ul_sy = glGetUniformLocation(pl_y, "sy"), ul_osy = glGetUniformLocation(pl_y, "os"),
                ul_ky = glGetUniformLocation(pl_y, "lk"), ul_cy = glGetUniformLocation(pl_y, "lc");
    glUseProgram(pl_uv); glUniform1i(glGetUniformLocation(pl_uv, "tu"), 1); glUniform1i(glGetUniformLocation(pl_uv, "tv"), 2);
    const GLint ul_sc = glGetUniformLocation(pl_uv, "sc"), ul_osuv = glGetUniformLocation(pl_uv, "os"),
                ul_kuv = glGetUniformLocation(pl_uv, "lk"), ul_cuv = glGetUniformLocation(pl_uv, "lc");
    p_hud = program(VS_HUD, FS_HUD); u_plane = glGetUniformLocation(p_hud, "plane");
    glUseProgram(p_hud); glUniform1i(glGetUniformLocation(p_hud, "atlas"), 3);
    GLuint t_c[2][3] = {{0}};  // カメラの絵（共有メモリをそのまま取り込む。2組を交互に使う）
    glGenVertexArrays(1, &vao_hud); glBindVertexArray(vao_hud);
    glGenBuffers(1, &vbo_hud); glBindBuffer(GL_ARRAY_BUFFER, vbo_hud);
    glEnableVertexAttribArray(0); glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 32, 0);
    glEnableVertexAttribArray(1); glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 32, (void *)8);
    glEnableVertexAttribArray(2); glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 32, (void *)16);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    load_font(font);
    glActiveTexture(GL_TEXTURE3); glBindTexture(GL_TEXTURE_2D, t_atlas); glActiveTexture(GL_TEXTURE0);  // 文字の一覧表は3番に置いたまま

    // ---- エンコーダ
    fd = open_by_name("Qualcomm Venus video encoder");
    struct v4l2_format cf = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE };
    cf.fmt.pix_mp.width = ow; cf.fmt.pix_mp.height = oh; cf.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_H264;
    cf.fmt.pix_mp.num_planes = 1; cf.fmt.pix_mp.plane_fmt[0].sizeimage = 1 << 20;  // 大きいとDQBUF・QBUFのたびのキャッシュ操作が重い
    if (xioctl(fd, VIDIOC_S_FMT, &cf)) DIE("S_FMT capture");
    struct v4l2_format of = { .type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE };
    of.fmt.pix_mp.width = ow; of.fmt.pix_mp.height = oh; of.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_NV12;
    of.fmt.pix_mp.num_planes = 1;
    if (xioctl(fd, VIDIOC_S_FMT, &of)) DIE("S_FMT output");
    const int bpl = of.fmt.pix_mp.plane_fmt[0].bytesperline, osz = of.fmt.pix_mp.plane_fmt[0].sizeimage;
    const int ah = (oh + 31) & ~31;  // 輝度面の行数（1080pなら1088）
    if (bpl != ow || osz < bpl * ah * 3 / 2) DIE("想定外のバッファ配置（bytesperline=%d sizeimage=%d）", bpl, osz);
    // 映像の本当の大きさを伝える（無いと1080pのSPSが1088行になり、下に8行の帯が出る）
    struct v4l2_selection sel = { .type = V4L2_BUF_TYPE_VIDEO_OUTPUT, .target = V4L2_SEL_TGT_CROP, .r = { 0, 0, ow, oh } };
    if (xioctl(fd, VIDIOC_S_SELECTION, &sel)) fprintf(stderr, "warn: crop not set (errno=%d)\n", errno);
    else printf("crop %ux%u\n", sel.r.width, sel.r.height);
    struct v4l2_streamparm sp = { .type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE };
    sp.parm.output.timeperframe.numerator = 1; sp.parm.output.timeperframe.denominator = 30;
    if (xioctl(fd, VIDIOC_S_PARM, &sp)) DIE("S_PARM");  // これが無いとクロックが上がらない（手順書5-5①）
    set_ctrl(V4L2_CID_MPEG_VIDEO_BITRATE, (int)(bitrate_mbps * 1e6), "bitrate");
    struct v4l2_control br = { .id = V4L2_CID_MPEG_VIDEO_BITRATE };
    if (!xioctl(fd, VIDIOC_G_CTRL, &br)) printf("bitrate %d\n", br.value);
    set_ctrl(V4L2_CID_MPEG_VIDEO_GOP_SIZE, 30, "gop_size");
    set_ctrl(V4L2_CID_MPEG_VIDEO_H264_I_PERIOD, 30, "h264_i_frame_period");

    struct v4l2_requestbuffers rq = { .count = NOUT, .type = t1, .memory = V4L2_MEMORY_MMAP };
    if (xioctl(fd, VIDIOC_REQBUFS, &rq)) DIE("REQBUFS out");
    const int nout = rq.count < NOUT ? rq.count : NOUT;
    PFNEGLCREATEIMAGEKHRPROC mkimg = (void *)eglGetProcAddress("eglCreateImageKHR");
    PFNGLEGLIMAGETARGETTEXTURE2DOESPROC img2tex = (void *)eglGetProcAddress("glEGLImageTargetTexture2DOES");
    GLuint f_dy[NOUT], f_duv[NOUT], t_dy[NOUT], t_duv[NOUT];
    for (int i = 0; i < nout; i++) {
        struct v4l2_plane pl[1] = {0};
        struct v4l2_buffer b = { .type = t1, .memory = V4L2_MEMORY_MMAP, .index = i, .length = 1, .m.planes = pl };
        if (xioctl(fd, VIDIOC_QUERYBUF, &b)) DIE("QUERYBUF out");
        ob[i].len = pl[0].length;
        struct v4l2_exportbuffer eb = { .type = t1, .index = i, .plane = 0, .flags = O_RDWR };
        if (xioctl(fd, VIDIOC_EXPBUF, &eb)) DIE("EXPBUF");
        for (int p = 0; p < 2; p++) {
            // modifierをLINEARと明示する（Mesa 25.2は指定が無いと断る。手順書5-11）
            EGLint at[] = { EGL_WIDTH, p ? ow / 2 : ow, EGL_HEIGHT, p ? ah / 2 : ah,
                            EGL_LINUX_DRM_FOURCC_EXT, p ? DRM_FORMAT_GR88 : DRM_FORMAT_R8,
                            EGL_DMA_BUF_PLANE0_FD_EXT, eb.fd, EGL_DMA_BUF_PLANE0_OFFSET_EXT, p ? bpl * ah : 0,
                            EGL_DMA_BUF_PLANE0_PITCH_EXT, bpl,
                            EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT, 0, EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT, 0, EGL_NONE };
            EGLImageKHR im = mkimg(dpy, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, NULL, at);
            if (im == EGL_NO_IMAGE_KHR) DIE("eglCreateImage plane%d err=0x%x", p, eglGetError());
            GLuint t; glGenTextures(1, &t); glBindTexture(GL_TEXTURE_2D, t); img2tex(GL_TEXTURE_2D, im);
            // プレビューで読むとき用（描く先としては使わない設定）。既定のミップマップ付きのままだと読めない
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            if (p) { t_duv[i] = t; f_duv[i] = fbo_for(t); } else { t_dy[i] = t; f_dy[i] = fbo_for(t); }
        }
        // 下の余りの行（と最初の中身）を黒にしておく。毎回描くのは映像の行だけ
        glBindFramebuffer(GL_FRAMEBUFFER, f_dy[i]); glViewport(0, 0, ow, ah);
        glClearColor(16 / 255.f, 0, 0, 1); glClear(GL_COLOR_BUFFER_BIT);
        glBindFramebuffer(GL_FRAMEBUFFER, f_duv[i]); glViewport(0, 0, ow / 2, ah / 2);
        glClearColor(.5f, .5f, 0, 1); glClear(GL_COLOR_BUFFER_BIT);
    }
    // プレビュー（頼まれている間だけ、10コマに1回＝約3枚/秒、PV_OUTへ書く。頼まれていなければ何もしない）
    GLuint p_pv = program(VS_FULL, FS_PREVIEW);
    glUseProgram(p_pv); glUniform1i(glGetUniformLocation(p_pv, "py"), 4); glUniform1i(glGetUniformLocation(p_pv, "puv"), 5);
    const GLint u_pp = glGetUniformLocation(p_pv, "pp");
    const GLuint f_pv = fbo_for(tex(GL_RGBA8, PV_W, PV_H, GL_NEAREST));
    uint8_t *pv_buf = malloc(16 + PV_W * PV_H * 4);
    uint32_t pv_seq = 0;
    int pv_on = 0;
    glFinish();
    rq = (struct v4l2_requestbuffers){ .count = NCAP, .type = t2, .memory = V4L2_MEMORY_MMAP };
    if (xioctl(fd, VIDIOC_REQBUFS, &rq)) DIE("REQBUFS cap");
    const int ncap = rq.count < NCAP ? rq.count : NCAP;
    for (int i = 0; i < ncap; i++) {
        struct v4l2_plane pl[1] = {0};
        struct v4l2_buffer b = { .type = t2, .memory = V4L2_MEMORY_MMAP, .index = i, .length = 1, .m.planes = pl };
        if (xioctl(fd, VIDIOC_QUERYBUF, &b)) DIE("QUERYBUF cap");
        cb[i].len = pl[0].length; cb[i].p = mmap(NULL, pl[0].length, PROT_READ | PROT_WRITE, MAP_SHARED, fd, pl[0].m.mem_offset);
        if (cb[i].p == MAP_FAILED) DIE("mmap cap");
        if (xioctl(fd, VIDIOC_QBUF, &b)) DIE("QBUF cap");
    }
    if (xioctl(fd, VIDIOC_STREAMON, &t1) || xioctl(fd, VIDIOC_STREAMON, &t2)) DIE("STREAMON");

    nfree = nout; for (int i = 0; i < nout; i++) freeidx[i] = i;
    double s_up = 0, s_draw = 0, s_conv = 0, s_wait = 0, s_cam = 0, s_q = 0, s_dr = 0;
    pthread_t dec_th; dec_frames = frames; pthread_create(&dec_th, NULL, decoder, NULL);

    double t0 = now(), cam_t0 = 0;
    int64_t last_us = -1;
    int f = 0;
    for (; (!frames || f < frames) && !quit; f++) {
        double a = now();
        while (nfree == 0) drain(1);
        s_wait += now() - a;
        int bi = freeidx[--nfree];

        // ① 展開スレッドが slot[s] を埋めるのを待ってGPUへ送る
        const int s = f & 1;
        a = now();
        pthread_mutex_lock(&mu); while (!filled[s] && !quit) pthread_cond_wait(&cv, &mu); pthread_mutex_unlock(&mu);
        if (quit) { freeidx[nfree++] = bi; break; }
        s_cam += now() - a;
        a = now();
        for (int i = 0; i < 3 && !t_c[s][i]; i++) {  // 最初の1回だけ、共有メモリをテクスチャとして取り込む
            EGLint at[] = { EGL_WIDTH, pw[i], EGL_HEIGHT, ph[i], EGL_LINUX_DRM_FOURCC_EXT, DRM_FORMAT_R8,
                            EGL_DMA_BUF_PLANE0_FD_EXT, slot_fd[s][i], EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0,
                            EGL_DMA_BUF_PLANE0_PITCH_EXT, pw[i],
                            EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT, 0, EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT, 0, EGL_NONE };
            EGLImageKHR im = mkimg(dpy, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, NULL, at);
            if (im == EGL_NO_IMAGE_KHR) DIE("eglCreateImage camera%d err=0x%x", i, eglGetError());
            glGenTextures(1, &t_c[s][i]); glBindTexture(GL_TEXTURE_2D, t_c[s][i]); img2tex(GL_TEXTURE_2D, im);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        }
        const double cam_ts = slot_ts[s], cam_utc = slot_utc[s];
        // 工程ごとの完了待ちは時間を測るときだけ（待つとCPUとGPUの間にすき間ができて遅くなる）
        if (profile) glFinish();
        double b1 = now(); s_up += b1 - a;

        if (f && f % 30 == 0) { hud_check(); lens_check(); }  // 設定ファイルが書き換わっていれば読み直す（約1秒ごと）
        struct tele t; double v[HUD_REFS];
        pthread_mutex_lock(&tmu); t = tl; memcpy(v, tvals, sizeof v); pthread_mutex_unlock(&tmu);
        static struct hud_track trk;
        if (demo) {  // 見た目と警告の色を机の上で確かめるための作り物の値（画面にDEMOと出す）。架空のコースを走り、差・コース図も動かす
            lr_demo_step(&dd, demo_t0 + f / 30.0);
            double lat, lon; lr_demo_pos(&dd, dd.s, &lat, &lon);
            if (f % 3 == 0)  // 走行データと同じ約10Hz
                lr_update(&lr, lat, lon, lr_demo_v0(&dd, dd.s) * lr_demo_factor(dd.lap), dd.lap, (dd.t - dd.lap_start) / 60, dd.last / 60, dd.best / 60);
            lr_track(&lr, lat, lon, &trk);
            for (int i = 0; hud_cur && i < hud_cur->nref; i++) v[i] = demo_ref(hud_cur->ref[i], &dd, lat, lon, f / 30.0);
            t.got = now();
        } else {
            pthread_mutex_lock(&tmu); trk.n = ttrk.n;
            memcpy(trk.lat, ttrk.lat, sizeof trk.lat[0] * trk.n); memcpy(trk.lon, ttrk.lon, sizeof trk.lon[0] * trk.n);
            pthread_mutex_unlock(&tmu);
        }
        const double age = now() - t.got;
        hn = 0;  // 計器の形を1枚分ためて、まとめてGPUへ送る（面ごとに同じものを描く）
        if (!getenv("OVERLAY_NOHUD")) {
            if (hud_cur) hud_draw(hud_cur, v, t.utc_ok, t.utc, age, &trk);
            else text(40, 26, .6f, RED, "HUD CONFIG ERROR");  // 設定ファイルが無い・読めない（録画は続ける）
        }
        if (demo) text(40, 470, .6f, YELLOW, "DEMO");  // どちらの配置の計器とも重ならない所
        glBindBuffer(GL_ARRAY_BUFFER, vbo_hud);
        glBufferData(GL_ARRAY_BUFFER, sizeof(float) * 8 * hn, hv, GL_STREAM_DRAW);

        // ② エンコーダのY面・UV面へ、カメラの絵を拡大して書き、計器を重ねる
        for (int plane = 0; plane < 2; plane++) {
            glBindFramebuffer(GL_FRAMEBUFFER, plane ? f_duv[bi] : f_dy[bi]);
            glViewport(0, 0, plane ? ow / 2 : ow, plane ? oh / 2 : oh);
            glDisable(GL_BLEND);
            if (!plane) {
                if (lens_on) {
                    glUseProgram(pl_y); glUniform2f(ul_sy, (float)CAM_W / pw[0], (float)CAM_H / ph[0]); glUniform2f(ul_osy, ow, oh);
                    glUniform4fv(ul_ky, 1, lens_k); glUniform4fv(ul_cy, 1, lens_c);
                } else {
                    glUseProgram(p_cy); glUniform2f(u_sy, (float)CAM_W / pw[0], (float)CAM_H / ph[0]); glUniform2f(u_osy, ow, oh);
                }
                glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, t_c[s][0]);
            } else {
                if (lens_on) {
                    glUseProgram(pl_uv); glUniform2f(ul_sc, chroma_w / pw[1], chroma_h / ph[1]); glUniform2f(ul_osuv, ow / 2, oh / 2);
                    glUniform4fv(ul_kuv, 1, lens_k); glUniform4fv(ul_cuv, 1, lens_c);
                } else {
                    glUseProgram(p_cuv); glUniform2f(u_sc, chroma_w / pw[1], chroma_h / ph[1]); glUniform2f(u_osuv, ow / 2, oh / 2);
                }
                glActiveTexture(GL_TEXTURE1); glBindTexture(GL_TEXTURE_2D, t_c[s][1]);
                glActiveTexture(GL_TEXTURE2); glBindTexture(GL_TEXTURE_2D, t_c[s][2]);
                glActiveTexture(GL_TEXTURE0);
            }
            glDrawArrays(GL_TRIANGLES, 0, 3);
            glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
            glUseProgram(p_hud); glUniform1i(u_plane, plane);
            glBindVertexArray(vao_hud); glDrawArrays(GL_TRIANGLES, 0, hn);
            if (profile && !plane) { glFinish(); double c = now(); s_draw += c - b1; b1 = c; }
        }
        glDisable(GL_BLEND);
        if (f % 10 == 0) {  // プレビューを頼まれているか（lens_preview.py が1秒ごとに PV_REQ を触る）
            struct stat ps;
            pv_on = !stat(PV_REQ, &ps) && time(NULL) - ps.st_mtime < 4;
        }
        const int pv_now = pv_on && f % 10 == 0;
        if (pv_now) {  // 録る絵（計器込み）を小さくしてRGBへ
            glBindFramebuffer(GL_FRAMEBUFFER, f_pv); glViewport(0, 0, PV_W, PV_H);
            glUseProgram(p_pv); glUniform3f(u_pp, PV_W, PV_H, (float)oh / ah);
            glActiveTexture(GL_TEXTURE4); glBindTexture(GL_TEXTURE_2D, t_dy[bi]);
            glActiveTexture(GL_TEXTURE5); glBindTexture(GL_TEXTURE_2D, t_duv[bi]);
            glActiveTexture(GL_TEXTURE0);
            glDrawArrays(GL_TRIANGLES, 0, 3);
        }
        glFinish();  // エンコーダへ渡す前にGPUの書き込みを終わらせる
        pthread_mutex_lock(&mu); filled[s] = 0; pthread_cond_broadcast(&cv); pthread_mutex_unlock(&mu);  // GPUが読み終えたので展開スレッドへ返す
        if (pv_now) {  // 書きかけを読まれないよう、別の名前で書いてから入れ替える
            glReadPixels(0, 0, PV_W, PV_H, GL_RGBA, GL_UNSIGNED_BYTE, pv_buf + 16);
            uint32_t hdr[4] = { 0x31565045u /* "EPV1" */, PV_W, PV_H, ++pv_seq };
            memcpy(pv_buf, hdr, 16);
            FILE *pf = fopen(PV_OUT ".tmp", "wb");
            if (pf) {
                const int ok = fwrite(pv_buf, 1, 16 + PV_W * PV_H * 4, pf) == 16 + PV_W * PV_H * 4;
                if (!fclose(pf) && ok) rename(PV_OUT ".tmp", PV_OUT);
            }
        }
        double bd = now(); s_conv += bd - b1;

        // ③ エンコーダへ。時刻はカメラの時刻（最初の枚からのµs）
        if (!f) cam_t0 = rec_cam_t0 = cam_ts;
        int64_t us = llround((cam_ts - cam_t0) * 1e6);
        if (us <= last_us) us = last_us + 1;
        last_us = us;
        stamps[f & 63].us = us; stamps[f & 63].mono = cam_ts; stamps[f & 63].host = cam_utc;
        struct v4l2_plane pl[1] = {{ .bytesused = osz, .length = ob[bi].len }};
        struct v4l2_buffer b = { .type = t1, .memory = V4L2_MEMORY_MMAP, .index = bi, .length = 1, .m.planes = pl };
        b.timestamp.tv_sec = us / 1000000; b.timestamp.tv_usec = us % 1000000;
        // 1秒ごとにIDR（途中から再生を始められるキーフレーム）を出させる。I_PERIODだけでは
        // IDRでないIフレームになり、途中から読めない（手順書5-11）。IDRの前にはemitがSPS・PPSを確かめる
        if (f && f % 30 == 0) set_ctrl(V4L2_CID_MPEG_VIDEO_FORCE_KEY_FRAME, 1, "force_key_frame");
        if (xioctl(fd, VIDIOC_QBUF, &b)) DIE("QBUF out");
        double bq = now(); s_q += bq - bd;
        drain(0);
        s_dr += now() - bq;
    }
    quit = 1;
    pthread_mutex_lock(&mu); pthread_cond_broadcast(&cv); pthread_mutex_unlock(&mu);
    struct v4l2_encoder_cmd ec = { .cmd = V4L2_ENC_CMD_STOP };
    xioctl(fd, VIDIOC_ENCODER_CMD, &ec);
    double tend = now() + 3; while (!eos && now() < tend) drain(1);
    ac_stop();
    if (ts_audio && out) ac_drain(rec_cam_t0, 1, ac_write);  // 残りの音
    double el = now() - t0;
    if (out) fclose(out);
    if (csv) fclose(csv);
    rec_state();  // 止まった時刻を残す（ここからVS_GAP_S以内にやり直せば同じ走行の続き）
    pthread_join(dec_th, NULL); pthread_join(tel_th, NULL);

    printf("output %dx%d\n", ow, oh);
    printf("frames=%d encoded=%d bytes=%zu elapsed=%.2fs fps=%.1f idr=%d sps_pps_inserted=%d video_s=%.2f\n",
           f, encoded, bytes, el, f / el, idr_count, header_inserted, last_us / 1e6);
    if (f) printf("per-frame ms: wait_decoded=%.2f upload=%.2f draw_y=%.2f draw_uv+finish=%.2f queue=%.2f drain=%.2f wait_encoder=%.2f"
                  " emit=%.2f (decoder: wait_camera=%.2f jpeg_decode=%.2f copy=%.2f)\n",
                  s_cam / f * 1e3, s_up / f * 1e3, s_draw / f * 1e3, s_conv / f * 1e3, s_q / f * 1e3, s_dr / f * 1e3,
                  s_wait / f * 1e3, s_emit / f * 1e3, d_wait / f * 1e3, d_dec / f * 1e3, d_copy / f * 1e3);
    struct rusage ru; getrusage(RUSAGE_SELF, &ru);
    double cpu = ru.ru_utime.tv_sec + ru.ru_utime.tv_usec * 1e-6 + ru.ru_stime.tv_sec + ru.ru_stime.tv_usec * 1e-6;
    printf("process CPU: %.1f%% of one core\n", cpu / el * 100);
    if (ts_audio) printf("audio: frames=%ld written=%ld dropped=%ld restarts=%ld\n", ac_frames, ac_written, ac_dropped, ac_restarts);
    if (low_space) { fprintf(stderr, "空きが%.0fMBを切ったので止めた\n", min_free_mb); return 3; }
    return 0;
}
