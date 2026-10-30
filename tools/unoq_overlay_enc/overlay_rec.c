// UNO Q：走行映像に走行データ（車速・回転数・水温・油温・ラップ・G・時刻）を焼き込んで保存する（試作）
//   カメラ（UVC、MJPEG 1280x720）→ 展開スレッド（libjpeg-turbo）→ GPUと共有するメモリへ写す
//   → GPUで1920x1080へ拡大し計器を重ね描き → エンコーダ（venus）の入力バッファへdmabufで直接NV12を書く → H.264
//   GPUはY（輝度）面とUV（色差）面へ直接描く。RGBの中間画面は作らず、計器は面ごとに1回の描画にまとめる（手順書5-13）
//   保存はMPEG-TS（.ts）。1枚ごとにカメラの時刻を付ける。途中で電源が切れても、そこまでは再生できる
//   数値はEcoCaptureのAPI（http://127.0.0.1:8080/api/telemetry）を別スレッドで約10Hzで読む
//   土台は overlay_enc_test.c（mode=1・thr=1、unoq_video_check_procedure.md 5-11）。計器の文字は
//   make_font_atlas.py で作る文字の一覧表（hud_font_64.pgm、DejaVu Sans Mono Bold）をGPUで貼る
// ビルド(UNO Q上): gcc -O2 -o overlay_rec overlay_rec.c -lEGL -lGLESv2 -ljpeg -lm -lpthread
// 実行: ./overlay_rec <入力> <出力> [seconds=60、0は止めるまで] [font=hud_font_64.pgm]
//   入力：/dev/videoN（カメラ）か file:xxx.jpg（同じJPEGを30fpsで繰り返す。カメラ無しで試す用）
//   出力：xxx.ts（MPEG-TS）か xxx.h264（素のH.264、時刻なし）。%を含むときはstrftimeの書式とみなし、
//         OVERLAY_SEGMENT_MIN分（既定10）ごとに、キーフレームの所で新しいファイルへ切り替える
//   出力の横に xxx.csv（1秒ごとに「ファイル内の枚目・動画内の秒・UTC」）を書く。走行データと時刻を合わせる用
//   空きがOVERLAY_MIN_FREE_MB（既定1024）を切ったら記録を止めて終わる（終了コード3）
//   SIGINT/SIGTERMで止めると、エンコーダに残った分を書き出してから終わる
//   OVERLAY_OUT=720 のときは1280x720で保存する（既定は1920x1080。計器は同じ配置のまま縮む）
//   OVERLAY_DEMO=1 のときは作り物の値で描く（見た目と警告の色の確認用。画面にDEMOと出る）
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
#include <sys/statvfs.h>
#include <drm/drm.h>
#include <drm/msm_drm.h>
#include <time.h>
#include <unistd.h>

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

// 計器の目安（ダッシュの警告と同じ。ncec-roadster track/thermal-limits.md、configure_sugo_dashboard.py）
#define RPM_MAX 8000.0
#define RPM_YELLOW 6000.0
#define RPM_RED 7000.0
static const double WATER_LIMITS[2] = { 100, 110 }, OIL_LIMITS[2] = { 110, 120 };  // 黄・赤
#define G_FULL 1.5  // Gボールの外周

static int ow = W, oh = H;  // 出力の大きさ（OVERLAY_OUT=720で1280x720）
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static double wall(void) { struct timespec t; clock_gettime(CLOCK_REALTIME, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
#define DIE(...) do { fprintf(stderr, __VA_ARGS__); fprintf(stderr, " (errno=%d %s)\n", errno, strerror(errno)); exit(1); } while (0)

static int xioctl(int fd, unsigned long req, void *arg) {
    int r; do { r = ioctl(fd, req, arg); } while (r < 0 && errno == EINTR); return r;
}

static volatile sig_atomic_t quit;
static void on_signal(int s) { (void)s; quit = 1; }

// ---------------------------------------------------------------- 走行データ（EcoCaptureのAPI）
struct tele {
    double speed, rpm, water, oil, lat_g, long_g, lap_no, lap_run, lap_last, lap_best;  // 無ければNAN
    time_t utc; int utc_ok;
    double got;  // 最後に読めた時刻（now()）
};
static struct tele tl = { NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, 0, 0, -1e9 };
static pthread_mutex_t tmu = PTHREAD_MUTEX_INITIALIZER;

static int http_get(const char *path, char *buf, int cap) {
    int s = socket(AF_INET, SOCK_STREAM, 0); if (s < 0) return -1;
    struct timeval tv = { 0, 500000 };
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof tv); setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof tv);
    struct sockaddr_in a = { .sin_family = AF_INET, .sin_port = htons(8080), .sin_addr.s_addr = htonl(INADDR_LOOPBACK) };
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
static int jtime(const char *js, const char *key, time_t *out) {
    char k[64]; snprintf(k, sizeof k, "\"%s\":\"", key);
    const char *q = strstr(js, k); if (!q) return 0;
    struct tm t = {0};
    if (sscanf(q + strlen(k), "%d-%d-%dT%d:%d:%d", &t.tm_year, &t.tm_mon, &t.tm_mday, &t.tm_hour, &t.tm_min, &t.tm_sec) != 6) return 0;
    t.tm_year -= 1900; t.tm_mon -= 1; *out = timegm(&t); return 1;
}

static void *telemetry(void *arg) {
    (void)arg;
    static char buf[1 << 16];
    while (!quit) {
        double a = now();
        if (http_get("/api/telemetry", buf, sizeof buf) > 0 && strstr(buf, "\"sample\"")) {
            const char *js = strstr(buf, "\"sample\"");
            struct tele t;
            t.speed = jnum(js, "values", "Speed");
            if (isnan(t.speed)) t.speed = jnum(js, "values", "GPSSpeed");
            t.rpm = jnum(js, "values", "RPM");
            t.water = jnum(js, "values", "WaterTemp");
            t.oil = jnum(js, "can_signals", "OilTemp");
            t.lat_g = jnum(js, "values", "LatAccel");
            t.long_g = jnum(js, "values", "LongAccel");
            t.lap_no = jnum(js, "lap", "CurrentLap");
            t.lap_run = jnum(js, "lap", "ElapsedTime");  // 分
            t.lap_last = jnum(js, "lap", "LapTime");
            t.lap_best = jnum(js, "lap", "BestLap");
            t.utc_ok = jtime(js, "gnss_utc", &t.utc) || jtime(js, "host_utc", &t.utc);
            t.got = now();
            pthread_mutex_lock(&tmu); tl = t; pthread_mutex_unlock(&tmu);
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

// ---------------------------------------------------------------- 計器の描画
static GLuint p_hud, vao_hud, vbo_hud, t_atlas;
static GLint u_plane;
static int cell_w, cell_h, first_ch, n_ch, atlas_cols, atlas_w, atlas_h;
#define HUD_MAX 6000
static float hv[8 * HUD_MAX];  // 頂点（x, y, u, v, r, g, b, a）
static int hn;

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

static const float *temp_color(double v, const double lim[2]) {
    return isnan(v) ? DIM : v >= lim[1] ? RED : v >= lim[0] ? YELLOW : WHITE;
}

static void draw_hud(const struct tele *t, double age) {
    char b[64];
    const float panel[4] = { 0, 0, 0, .55f }, track[4] = { .2f, .2f, .22f, .7f };
    rect(0, 860, W, H, panel);

    // 回転数のバー（パネルの上）
    rect(40, 828, 1880, 852, track);
    if (!isnan(t->rpm)) {
        double f = fmin(fmax(t->rpm / RPM_MAX, 0), 1);
        const float *c = t->rpm >= RPM_RED ? RED : t->rpm >= RPM_YELLOW ? YELLOW : GREEN;
        rect(40, 828, 40 + 1840 * f, 852, c);
    }
    for (int k = 1; k < 8; k++) { float x = 40 + 1840 * k * 1000 / RPM_MAX; seg(x, 828, x, 852, 3, panel); }

    // 車速
    text(40, 870, .42f, GREY, "SPEED km/h");
    if (isnan(t->speed)) snprintf(b, sizeof b, "--"); else snprintf(b, sizeof b, "%.0f", t->speed);
    text(300 - text_w(1.8f, b), 905, 1.8f, WHITE, b);
    // 回転数
    text(360, 870, .42f, GREY, "RPM");
    if (isnan(t->rpm)) snprintf(b, sizeof b, "--"); else snprintf(b, sizeof b, "%.0f", t->rpm);
    text(660 - text_w(1.8f, b), 905, 1.8f, isnan(t->rpm) ? WHITE : t->rpm >= RPM_RED ? RED : WHITE, b);
    // 水温・油温
    text(720, 885, .5f, GREY, "WATER");
    if (isnan(t->water)) snprintf(b, sizeof b, "--"); else snprintf(b, sizeof b, "%.0fC", t->water);
    text(1000 - text_w(1.0f, b), 870, 1.0f, temp_color(t->water, WATER_LIMITS), b);
    text(720, 975, .5f, GREY, "OIL");
    if (isnan(t->oil)) snprintf(b, sizeof b, "--"); else snprintf(b, sizeof b, "%.0fC", t->oil);
    text(1000 - text_w(1.0f, b), 960, 1.0f, temp_color(t->oil, OIL_LIMITS), b);
    // ラップ
    if (isnan(t->lap_no)) snprintf(b, sizeof b, "LAP --"); else snprintf(b, sizeof b, "LAP %.0f", t->lap_no);
    text(1060, 870, .5f, GREY, b);
    fmt_laptime(b, sizeof b, t->lap_run, 1);
    text(1060, 915, 1.45f, WHITE, b);
    text(1440, 885, .45f, GREY, "LAST");
    fmt_laptime(b, sizeof b, t->lap_last, 2); text(1540, 875, .6f, WHITE, b);
    text(1440, 975, .45f, GREY, "BEST");
    fmt_laptime(b, sizeof b, t->lap_best, 2); text(1540, 965, .6f, GREEN, b);

    // Gボール（外周＝G_FULL。横Gは右が正、前後Gは加速が下・減速が上）
    const float cx = 1815, cy = 965, r = 72;
    for (int i = 0; i < 48; i++) {
        float a0 = i * 2 * M_PI / 48, a1 = (i + 1) * 2 * M_PI / 48;
        seg(cx + r * cosf(a0), cy + r * sinf(a0), cx + r * cosf(a1), cy + r * sinf(a1), 3, GREY);
    }
    seg(cx - r, cy, cx + r, cy, 3, DIM); seg(cx, cy - r, cx, cy + r, 3, DIM);
    if (!isnan(t->lat_g) && !isnan(t->long_g)) {
        float gx = cx + r * fmax(fmin(t->lat_g / G_FULL, 1), -1), gy = cy + r * fmax(fmin(t->long_g / G_FULL, 1), -1);
        rect(gx - 9, gy - 9, gx + 9, gy + 9, YELLOW);
    }

    // 時刻（右上、日本時間）
    if (t->utc_ok) {
        struct tm lt; time_t u = t->utc; localtime_r(&u, &lt);
        snprintf(b, sizeof b, "%02d:%02d:%02d", lt.tm_hour, lt.tm_min, lt.tm_sec);
        rect(1650, 20, 1900, 80, panel);
        text(1665, 26, .6f, WHITE, b);
    }
    // 数値が来ていない
    if (age > 1.5) { rect(20, 20, 330, 80, panel); text(35, 26, .6f, RED, "NO DATA"); }
}

// ---------------------------------------------------------------- 保存（MPEG-TS／素のH.264）と1秒ごとの時刻
#define PID_PMT 0x1000
#define PID_VID 0x0100
static FILE *out, *csv;
static const char *out_pat;
static char out_name[512];
static int ts_mode, seg_on, low_space, seg_frames, encoded, idr_count, header_inserted;
static double seg_len = 600, seg_t0, min_free_mb = 1024;
static int64_t seg_us0;
static size_t bytes;
static uint8_t seq_hdr[256], cc_pat, cc_pmt, cc_vid;
static size_t seq_len;
static struct { int64_t us; double utc; } stamps[64];  // エンコーダへ渡した時刻（µs）→ その枚のUTC

static void put(const void *p, size_t n) { fwrite(p, 1, n, out); bytes += n; }

static uint32_t crc32_mpeg(const uint8_t *p, int n) {
    uint32_t c = 0xffffffff;
    while (n--) { c ^= (uint32_t)*p++ << 24; for (int k = 0; k < 8; k++) c = c & 0x80000000 ? (c << 1) ^ 0x04c11db7 : c << 1; }
    return c;
}

static void ts_section(int pid, uint8_t *cc, uint8_t *sec, int n) {  // secの最後の4バイトにCRCを入れて1パケットで出す
    uint32_t c = crc32_mpeg(sec, n - 4);
    sec[n - 4] = c >> 24; sec[n - 3] = c >> 16; sec[n - 2] = c >> 8; sec[n - 1] = c;
    uint8_t pk[188]; memset(pk, 0xff, sizeof pk);
    pk[0] = 0x47; pk[1] = 0x40 | pid >> 8; pk[2] = pid & 0xff; pk[3] = 0x10 | ((*cc)++ & 0x0f);
    pk[4] = 0;  // pointer_field
    memcpy(pk + 5, sec, n); put(pk, sizeof pk);
}

// PAT・PMT（番組1つ、H.264が1本）。キーフレームの前に毎回出し、途中から読んでも分かるようにする
static void ts_tables(void) {
    uint8_t pat[16] = { 0x00, 0xb0, 13, 0x00, 0x01, 0xc1, 0x00, 0x00, 0x00, 0x01, 0xe0 | PID_PMT >> 8, PID_PMT & 0xff };
    uint8_t pmt[21] = { 0x02, 0xb0, 18, 0x00, 0x01, 0xc1, 0x00, 0x00, 0xe0 | PID_VID >> 8, PID_VID & 0xff, 0xf0, 0x00,
                        0x1b, 0xe0 | PID_VID >> 8, PID_VID & 0xff, 0xf0, 0x00 };
    ts_section(0, &cc_pat, pat, sizeof pat);
    ts_section(PID_PMT, &cc_pmt, pmt, sizeof pmt);
}

// 1枚（アクセスユニット）をPES（PTSのみ。Bフレームは無い）にしてTSのパケットへ。pts・pcrは90kHz
static void ts_frame(const uint8_t *es, size_t n, uint64_t pts, uint64_t pcr, int key) {
    const uint8_t hd[20] = { 0, 0, 1, 0xe0, 0, 0, 0x80, 0x80, 5,
        0x21 | (pts >> 29 & 0x0e), pts >> 22 & 0xff, 0x01 | (pts >> 14 & 0xfe), pts >> 7 & 0xff, 0x01 | (pts << 1 & 0xfe),
        0, 0, 0, 1, 0x09, 0xf0 };  // PESの頭＋AUD（区切りのNAL。TSのH.264では付ける決まり）
    size_t total = sizeof hd + n, off = 0;
    for (int first = 1; off < total; first = 0) {
        uint8_t pk[188], af[184]; size_t L = 0; int has_af = 0;
        if (first) {  // 1枚目のパケットにPCR（とキーフレームの印）
            af[L++] = (key ? 0x40 : 0) | 0x10;
            af[L++] = pcr >> 25; af[L++] = pcr >> 17; af[L++] = pcr >> 9; af[L++] = pcr >> 1;
            af[L++] = (pcr & 1) << 7 | 0x7e; af[L++] = 0;
            has_af = 1;
        }
        size_t cap = has_af ? 183 - L : 184, left = total - off;
        if (left < cap) {  // 最後のパケットは詰め物で188バイトにする
            size_t s = cap - left;
            if (!has_af) { has_af = 1; s--; if (s) { af[L++] = 0x00; s--; } }
            memset(af + L, 0xff, s); L += s; cap = left;
        }
        pk[0] = 0x47; pk[1] = (first ? 0x40 : 0) | PID_VID >> 8; pk[2] = PID_VID & 0xff;
        pk[3] = (has_af ? 0x30 : 0x10) | (cc_vid++ & 0x0f);
        size_t p = 4;
        if (has_af) { pk[p++] = L; memcpy(pk + p, af, L); p += L; }
        size_t a = off, m = cap;
        if (a < sizeof hd) { size_t c = sizeof hd - a < m ? sizeof hd - a : m; memcpy(pk + p, hd + a, c); p += c; a += c; m -= c; }
        if (m) memcpy(pk + p, es + (a - sizeof hd), m);
        put(pk, sizeof pk); off += cap;
    }
}

static double utc_of(int64_t us) {
    for (int i = 0; i < 64; i++) if (stamps[i].us == us) return stamps[i].utc;
    return wall();
}

// 新しいファイル（と時刻のcsv）を開く。usはそのファイルの最初の枚（キーフレーム）の時刻
static void seg_open(int64_t us) {
    if (out) fclose(out);
    if (csv) fclose(csv);
    csv = NULL;
    if (seg_on) { time_t u = (time_t)utc_of(us); struct tm lt; localtime_r(&u, &lt); strftime(out_name, sizeof out_name, out_pat, &lt); }
    else snprintf(out_name, sizeof out_name, "%s", out_pat);
    out = fopen(out_name, "wb"); if (!out) DIE("open %s", out_name);
    char cn[sizeof out_name + 8]; snprintf(cn, sizeof cn, "%s", out_name);
    char *dot = strrchr(cn, '.'); if (dot && !strchr(dot, '/')) *dot = 0;
    strcat(cn, ".csv");
    csv = fopen(cn, "w"); if (csv) fprintf(csv, "frame,video_s,utc\n");
    seg_t0 = now(); seg_us0 = us; seg_frames = 0;
    printf("file %s\n", out_name); fflush(stdout);
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
        struct statvfs sv;
        if (!fstatvfs(fileno(out), &sv) && (double)sv.f_bavail * sv.f_frsize < min_free_mb * 1048576.0) { low_space = 1; quit = 1; }
        if (csv) {
            double u = utc_of(us); time_t s = (time_t)u; struct tm g; gmtime_r(&s, &g);
            char ts[32]; strftime(ts, sizeof ts, "%Y-%m-%dT%H:%M:%S", &g);
            fprintf(csv, "%d,%.3f,%s.%03dZ\n", seg_frames, (us - seg_us0) / 1e6, ts, (int)((u - s) * 1000));
            fflush(csv);
        }
        if (ts_mode) ts_tables();
    }
    if (!out) return;
    static uint8_t tmp[4 << 20];
    if (idr && !has_sps && seq_len && n + seq_len <= sizeof tmp) {  // SPS・PPSが付いていないIDRには控えを前に付ける
        memcpy(tmp, seq_hdr, seq_len); memcpy(tmp + seq_len, p, n); p = tmp; n += seq_len; header_inserted++;
    }
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
    const int demo = getenv("OVERLAY_DEMO") && atoi(getenv("OVERLAY_DEMO"));
    const int profile = getenv("OVERLAY_PROFILE") && atoi(getenv("OVERLAY_PROFILE"));
    if (getenv("OVERLAY_SEGMENT_MIN")) seg_len = atof(getenv("OVERLAY_SEGMENT_MIN")) * 60;
    if (getenv("OVERLAY_MIN_FREE_MB")) min_free_mb = atof(getenv("OVERLAY_MIN_FREE_MB"));
    out_pat = argv[2]; seg_on = strchr(out_pat, '%') != NULL;
    const size_t ol = strlen(out_pat); ts_mode = !(ol > 5 && !strcmp(out_pat + ol - 5, ".h264"));
    signal(SIGINT, on_signal); signal(SIGTERM, on_signal);
    setenv("TZ", "Asia/Tokyo", 0); tzset();

    rfd = open("/dev/dri/renderD128", O_RDWR | O_CLOEXEC); if (rfd < 0) DIE("open renderD128");
    cam_open(argv[1]);
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
    set_ctrl(V4L2_CID_MPEG_VIDEO_BITRATE, 12000000, "bitrate");
    set_ctrl(V4L2_CID_MPEG_VIDEO_GOP_SIZE, 30, "gop_size");
    set_ctrl(V4L2_CID_MPEG_VIDEO_H264_I_PERIOD, 30, "h264_i_frame_period");

    struct v4l2_requestbuffers rq = { .count = NOUT, .type = t1, .memory = V4L2_MEMORY_MMAP };
    if (xioctl(fd, VIDIOC_REQBUFS, &rq)) DIE("REQBUFS out");
    const int nout = rq.count < NOUT ? rq.count : NOUT;
    PFNEGLCREATEIMAGEKHRPROC mkimg = (void *)eglGetProcAddress("eglCreateImageKHR");
    PFNGLEGLIMAGETARGETTEXTURE2DOESPROC img2tex = (void *)eglGetProcAddress("glEGLImageTargetTexture2DOES");
    GLuint f_dy[NOUT], f_duv[NOUT];
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
            if (p) f_duv[i] = fbo_for(t); else f_dy[i] = fbo_for(t);
        }
        // 下の余りの行（と最初の中身）を黒にしておく。毎回描くのは映像の行だけ
        glBindFramebuffer(GL_FRAMEBUFFER, f_dy[i]); glViewport(0, 0, ow, ah);
        glClearColor(16 / 255.f, 0, 0, 1); glClear(GL_COLOR_BUFFER_BIT);
        glBindFramebuffer(GL_FRAMEBUFFER, f_duv[i]); glViewport(0, 0, ow / 2, ah / 2);
        glClearColor(.5f, .5f, 0, 1); glClear(GL_COLOR_BUFFER_BIT);
    }
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

        struct tele t; pthread_mutex_lock(&tmu); t = tl; pthread_mutex_unlock(&tmu);
        if (demo) {  // 見た目と警告の色を机の上で確かめるための作り物の値（画面にDEMOと出す）
            double ph = f / 30.0;
            t.speed = 90 + 70 * sin(ph * .4); t.rpm = 4500 + 3400 * sin(ph * .9); t.water = 98 + 14 * sin(ph * .15);
            t.oil = t.water + 10; t.lat_g = 1.1 * sin(ph * .7); t.long_g = .8 * cos(ph * .7);
            t.lap_no = 3; t.lap_run = fmod(ph, 95) / 60; t.lap_last = 96.37 / 60; t.lap_best = 94.85 / 60;
            t.got = now();
        }
        const double age = now() - t.got;
        hn = 0;  // 計器の形を1枚分ためて、まとめてGPUへ送る（面ごとに同じものを描く）
        if (!getenv("OVERLAY_NOHUD")) draw_hud(&t, age);
        if (demo) text(40, 26, .6f, YELLOW, "DEMO");
        glBindBuffer(GL_ARRAY_BUFFER, vbo_hud);
        glBufferData(GL_ARRAY_BUFFER, sizeof(float) * 8 * hn, hv, GL_STREAM_DRAW);

        // ② エンコーダのY面・UV面へ、カメラの絵を拡大して書き、計器を重ねる
        for (int plane = 0; plane < 2; plane++) {
            glBindFramebuffer(GL_FRAMEBUFFER, plane ? f_duv[bi] : f_dy[bi]);
            glViewport(0, 0, plane ? ow / 2 : ow, plane ? oh / 2 : oh);
            glDisable(GL_BLEND);
            if (!plane) {
                glUseProgram(p_cy); glUniform2f(u_sy, (float)CAM_W / pw[0], (float)CAM_H / ph[0]); glUniform2f(u_osy, ow, oh);
                glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, t_c[s][0]);
            } else {
                glUseProgram(p_cuv); glUniform2f(u_sc, chroma_w / pw[1], chroma_h / ph[1]); glUniform2f(u_osuv, ow / 2, oh / 2);
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
        glFinish();  // エンコーダへ渡す前にGPUの書き込みを終わらせる
        pthread_mutex_lock(&mu); filled[s] = 0; pthread_cond_broadcast(&cv); pthread_mutex_unlock(&mu);  // GPUが読み終えたので展開スレッドへ返す
        double bd = now(); s_conv += bd - b1;

        // ③ エンコーダへ。時刻はカメラの時刻（最初の枚からのµs）
        if (!f) cam_t0 = cam_ts;
        int64_t us = llround((cam_ts - cam_t0) * 1e6);
        if (us <= last_us) us = last_us + 1;
        last_us = us;
        stamps[f & 63].us = us; stamps[f & 63].utc = cam_utc;
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
    double el = now() - t0;
    if (out) fclose(out);
    if (csv) fclose(csv);
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
    if (low_space) { fprintf(stderr, "空きが%.0fMBを切ったので止めた\n", min_free_mb); return 3; }
    return 0;
}
