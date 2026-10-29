// UNO Q：走行映像に走行データ（車速・回転数・水温・油温・ラップ・G・時刻）を焼き込んでH.264で保存する（試作）
//   カメラ（UVC、MJPEG 1280x720）→ 展開スレッド（libjpeg-turbo）→ GPUで1920x1080へ拡大し計器を重ね描き
//   → エンコーダ（venus）の入力バッファへdmabufで直接NV12を書く（コピー無し）→ H.264（.h264のまま保存）
//   数値はEcoCaptureのAPI（http://127.0.0.1:8080/api/telemetry）を別スレッドで約10Hzで読む
//   土台は overlay_enc_test.c（mode=1・thr=1、unoq_video_check_procedure.md 5-11）。計器の文字は
//   make_font_atlas.py で作る文字の一覧表（hud_font_64.pgm、DejaVu Sans Mono Bold）をGPUで貼る
// ビルド(UNO Q上): gcc -O2 -o overlay_rec overlay_rec.c -lEGL -lGLESv2 -ljpeg -lm -lpthread
// 実行: ./overlay_rec /dev/videoN out.h264 [seconds=60] [font=hud_font_64.pgm]
//   SIGINT/SIGTERMで止めると、エンコーダに残った分を書き出してから終わる
//   OVERLAY_DEMO=1 のときは作り物の値で描く（見た目と警告の色の確認用。画面にDEMOと出る）
//   OVERLAY_PROFILE=1 のときは工程ごとにGPUの完了を待って時間を測る（その分遅くなる）
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
#include <time.h>
#include <unistd.h>

#define W 1920
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

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
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
// JPEGを展開したY/Cb/Cr（BT.601 full range、色差は間引かれたまま）→ RGB、1920x1080へ拡大
static const char *FS_JPEG2RGB =
    "#version 300 es\nprecision mediump float;\n"
    "uniform sampler2D ty; uniform sampler2D tu; uniform sampler2D tv; uniform vec2 sy; uniform vec2 sc; out vec4 o;\n"
    "void main(){ vec2 q=gl_FragCoord.xy/vec2(1920.0,1080.0);\n"
    "  float y=texture(ty,q*sy).r; float u=texture(tu,q*sc).r-0.5; float v=texture(tv,q*sc).r-0.5;\n"
    "  o=vec4(y+1.402*v, y-0.344*u-0.714*v, y+1.772*u, 1.0); }\n";
// 重ね描き（ピクセル座標・上端が0）
static const char *VS_OVL =
    "#version 300 es\nlayout(location=0) in vec2 a;\n"
    "void main(){ gl_Position=vec4(a.x/960.0-1.0, a.y/540.0-1.0, 0.0, 1.0); }\n";
static const char *FS_COL =
    "#version 300 es\nprecision mediump float; uniform vec4 col; out vec4 o; void main(){ o=col; }\n";
// 文字：位置（ピクセル）と一覧表の座標。一覧表の濃さをそのまま不透明度にする
static const char *VS_TXT =
    "#version 300 es\nlayout(location=0) in vec2 a; layout(location=1) in vec2 t; out vec2 uv;\n"
    "void main(){ uv=t; gl_Position=vec4(a.x/960.0-1.0, a.y/540.0-1.0, 0.0, 1.0); }\n";
static const char *FS_TXT =
    "#version 300 es\nprecision mediump float; uniform sampler2D atlas; uniform vec4 col; in vec2 uv; out vec4 o;\n"
    "void main(){ o=vec4(col.rgb, col.a*texture(atlas,uv).r); }\n";
// GPUの描いた絵（RGB）をエンコーダのNV12（Y=R8、UV=GR88）へ直接書く
static const char *FS_Y =
    "#version 300 es\nprecision highp float; uniform sampler2D t; out vec4 o;\n"
    "void main(){ ivec2 p=ivec2(gl_FragCoord.xy); float y=0.0625;\n"
    "  if(p.y<1080) y+=dot(texelFetch(t,p,0).rgb,vec3(0.257,0.504,0.098)); o=vec4(y,0.0,0.0,1.0); }\n";
static const char *FS_UV =
    "#version 300 es\nprecision highp float; uniform sampler2D t; out vec4 o;\n"
    "void main(){ ivec2 p=ivec2(gl_FragCoord.xy); vec2 uv=vec2(0.5);\n"
    "  if(p.y<540){ vec3 c=texture(t,(vec2(p*2)+1.0)/vec2(1920.0,1080.0)).rgb;\n"
    "    uv=vec2(0.5+dot(c,vec3(-0.148,-0.291,0.439)), 0.5+dot(c,vec3(0.439,-0.368,-0.071))); }\n"
    "  o=vec4(uv,0.0,1.0); }\n";

// ---------------------------------------------------------------- 計器の描画
static GLuint p_col, p_txt, vao_col, vbo_col, vao_txt, vbo_txt, t_atlas;
static GLint u_col, u_tcol;
static int cell_w, cell_h, first_ch, n_ch, atlas_cols, atlas_w, atlas_h;
static float vtx[6 * 4 * 64];

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

static void rect(float x0, float y0, float x1, float y1, const float c[4]) {
    float v[] = { x0, y0, x1, y0, x0, y1, x1, y0, x1, y1, x0, y1 };
    glUseProgram(p_col); glUniform4fv(u_col, 1, c);
    glBindVertexArray(vao_col); glBindBuffer(GL_ARRAY_BUFFER, vbo_col);
    glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof v, v); glDrawArrays(GL_TRIANGLES, 0, 6);
}

static void lines(const float *pts, int n, GLenum mode, const float c[4]) {
    glUseProgram(p_col); glUniform4fv(u_col, 1, c);
    glBindVertexArray(vao_col); glBindBuffer(GL_ARRAY_BUFFER, vbo_col);
    glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof(float) * 2 * n, pts); glDrawArrays(mode, 0, n);
}

// 文字列を (x, y)（左上）から描く。s＝倍率（1.0で1文字 cell_w×cell_h）。戻り値は右端
static float text(float x, float y, float s, const float c[4], const char *str) {
    int n = 0;
    for (const char *p = str; *p && n < 64; p++, n++) {
        int i = (unsigned char)*p - first_ch; if (i < 0 || i >= n_ch) i = 0;
        float u0 = (float)(i % atlas_cols) * cell_w / atlas_w, v0 = (float)(i / atlas_cols) * cell_h / atlas_h;
        float u1 = u0 + (float)cell_w / atlas_w, v1 = v0 + (float)cell_h / atlas_h;
        float x0 = x + n * cell_w * s, x1 = x0 + cell_w * s, y1 = y + cell_h * s;
        float q[] = { x0, y, u0, v0, x1, y, u1, v0, x0, y1, u0, v1, x1, y, u1, v0, x1, y1, u1, v1, x0, y1, u0, v1 };
        memcpy(vtx + n * 24, q, sizeof q);
    }
    glUseProgram(p_txt); glUniform4fv(u_tcol, 1, c);
    glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, t_atlas);
    glBindVertexArray(vao_txt); glBindBuffer(GL_ARRAY_BUFFER, vbo_txt);
    glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof(float) * 24 * n, vtx); glDrawArrays(GL_TRIANGLES, 0, 6 * n);
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
    for (int k = 1; k < 8; k++) { float x = 40 + 1840 * k * 1000 / RPM_MAX; float tick[] = { x, 828, x, 852 }; lines(tick, 2, GL_LINES, panel); }

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
    float ring[2 * 48];
    for (int i = 0; i < 48; i++) { ring[2 * i] = cx + r * cosf(i * 2 * M_PI / 48); ring[2 * i + 1] = cy + r * sinf(i * 2 * M_PI / 48); }
    lines(ring, 48, GL_LINE_LOOP, GREY);
    float cross[] = { cx - r, cy, cx + r, cy, cx, cy - r, cx, cy + r };
    lines(cross, 4, GL_LINES, DIM);
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

// ---------------------------------------------------------------- エンコーダ
struct vbuf { void *p; size_t len; };
static int fd, t1 = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE, t2 = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
static struct vbuf ob[NOUT], cb[NCAP];
static int freeidx[NOUT], nfree, encoded, eos, idr_count, header_inserted;
static size_t bytes;
static FILE *out;
static uint8_t seq_hdr[256]; static size_t seq_len;

// 出てきたH.264をファイルへ。最初のSPS・PPSを控え、以後のIDRの前に付いていなければ付け足す
// （エンコーダは先頭にしか出さないので、途中から読めるように。手順書5-11）
static void write_es(const uint8_t *p, size_t n) {
    size_t i = 0; int has_sps = 0;
    while (i + 4 < n) {
        if (p[i] == 0 && p[i + 1] == 0 && p[i + 2] == 1) {
            int t = p[i + 3] & 0x1f;
            if (t == 7) has_sps = 1;
            if (t == 7 && !seq_len) {  // SPSからIDRかスライスの手前までを控える
                size_t s = i > 0 && p[i - 1] == 0 ? i - 1 : i, e = i + 3;
                while (e + 3 < n && !(p[e] == 0 && p[e + 1] == 0 && p[e + 2] == 1 && ((p[e + 3] & 0x1f) == 5 || (p[e + 3] & 0x1f) == 1))) e++;
                if (e > s && e - s <= sizeof seq_hdr) { memcpy(seq_hdr, p + s, e - s); seq_len = e - s; if (seq_hdr[seq_len - 1] == 0) seq_len--; }
            }
            if (t == 5) {
                idr_count++;
                if (!has_sps && seq_len) { fwrite(seq_hdr, 1, seq_len, out); bytes += seq_len; header_inserted++; has_sps = 1; }
            }
            i += 3;
        } else i++;
    }
    fwrite(p, 1, n, out); bytes += n;
}

static void drain(int block) {
    struct pollfd pf = { .fd = fd, .events = POLLIN | POLLOUT };
    if (poll(&pf, 1, block ? 1000 : 0) <= 0) return;
    for (;;) {
        struct v4l2_plane pl[1] = {0};
        struct v4l2_buffer b = { .type = t2, .memory = V4L2_MEMORY_MMAP, .length = 1, .m.planes = pl };
        if (xioctl(fd, VIDIOC_DQBUF, &b)) break;
        write_es(cb[b.index].p, pl[0].bytesused);
        if (pl[0].bytesused) encoded++;
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
static struct jpeg_decompress_struct jd;
static struct jpeg_error_mgr jerr;
static uint8_t *slot[2][3];  // 展開先（2枚を交互に使う。成分ごと、幅・高さは8の倍数へ切り上げ）
static int pw[3], ph[3];
static float chroma_w, chroma_h;  // 色差の大きさ（最初の1枚で控える。jdはGPU側から読まない）

static void cam_open(const char *dev) {
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
    jd.err = jpeg_std_error(&jerr); jpeg_create_decompress(&jd);
}

static void cam_frame(int s, double *t_wait, double *t_dec) {
    uint8_t **pln = slot[s];
    double a = now();
    struct v4l2_buffer b = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP };
    if (xioctl(cfd, VIDIOC_DQBUF, &b)) DIE("camera DQBUF");
    double c = now(); *t_wait += c - a;
    jpeg_mem_src(&jd, camb[b.index].p, b.bytesused);  // UVCのMJPEGはハフマン表を省くが、libjpeg-turboが標準表で補う
    jpeg_read_header(&jd, TRUE);
    jd.raw_data_out = TRUE; jd.do_fancy_upsampling = FALSE; jd.dct_method = JDCT_IFAST;
    jpeg_start_decompress(&jd);
    if (!slot[0][0]) {
        for (int i = 0; i < 3; i++) {
            pw[i] = jd.comp_info[i].width_in_blocks * DCTSIZE; ph[i] = jd.comp_info[i].height_in_blocks * DCTSIZE;
            for (int k = 0; k < 2; k++) slot[k][i] = malloc((size_t)pw[i] * (ph[i] + 16 * DCTSIZE));
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
    if (xioctl(cfd, VIDIOC_QBUF, &b)) DIE("camera QBUF");
    *t_dec += now() - c;
}

static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cv = PTHREAD_COND_INITIALIZER;
static int filled[2], dec_frames;
static double d_wait, d_dec;
static void *decoder(void *arg) {
    (void)arg;
    for (int f = 0; f < dec_frames && !quit; f++) {
        int s = f & 1;
        pthread_mutex_lock(&mu); while (filled[s] && !quit) pthread_cond_wait(&cv, &mu); pthread_mutex_unlock(&mu);
        if (quit) break;
        cam_frame(s, &d_wait, &d_dec);
        pthread_mutex_lock(&mu); filled[s] = 1; pthread_cond_broadcast(&cv); pthread_mutex_unlock(&mu);
    }
    return NULL;
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s /dev/videoN out.h264 [seconds=60] [font=hud_font_64.pgm]\n", argv[0]); return 1; }
    const int frames = (argc > 3 ? atoi(argv[3]) : 60) * 30;
    const char *font = argc > 4 ? argv[4] : "hud_font_64.pgm";
    const int demo = getenv("OVERLAY_DEMO") && atoi(getenv("OVERLAY_DEMO"));
    const int profile = getenv("OVERLAY_PROFILE") && atoi(getenv("OVERLAY_PROFILE"));
    signal(SIGINT, on_signal); signal(SIGTERM, on_signal);
    setenv("TZ", "Asia/Tokyo", 0); tzset();

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

    GLuint p_jpg = program(VS_FULL, FS_JPEG2RGB), p_dy = program(VS_FULL, FS_Y), p_duv = program(VS_FULL, FS_UV);
    p_col = program(VS_OVL, FS_COL); u_col = glGetUniformLocation(p_col, "col");
    p_txt = program(VS_TXT, FS_TXT); u_tcol = glGetUniformLocation(p_txt, "col");
    glUseProgram(p_txt); glUniform1i(glGetUniformLocation(p_txt, "atlas"), 0);
    GLuint t_rgb = tex(GL_RGBA8, W, H, GL_LINEAR), f_rgb = fbo_for(t_rgb), t_c[3] = {0};
    glGenVertexArrays(1, &vao_col); glBindVertexArray(vao_col);
    glGenBuffers(1, &vbo_col); glBindBuffer(GL_ARRAY_BUFFER, vbo_col);
    glBufferData(GL_ARRAY_BUFFER, sizeof(float) * 2 * 256, NULL, GL_STREAM_DRAW);
    glEnableVertexAttribArray(0); glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, 0);
    glGenVertexArrays(1, &vao_txt); glBindVertexArray(vao_txt);
    glGenBuffers(1, &vbo_txt); glBindBuffer(GL_ARRAY_BUFFER, vbo_txt);
    glBufferData(GL_ARRAY_BUFFER, sizeof vtx, NULL, GL_STREAM_DRAW);
    glEnableVertexAttribArray(0); glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 16, 0);
    glEnableVertexAttribArray(1); glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 16, (void *)8);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glLineWidth(3.0f);
    load_font(font);

    // ---- エンコーダ
    fd = open_by_name("Qualcomm Venus video encoder");
    struct v4l2_format cf = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE };
    cf.fmt.pix_mp.width = W; cf.fmt.pix_mp.height = H; cf.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_H264;
    cf.fmt.pix_mp.num_planes = 1; cf.fmt.pix_mp.plane_fmt[0].sizeimage = 4 << 20;
    if (xioctl(fd, VIDIOC_S_FMT, &cf)) DIE("S_FMT capture");
    struct v4l2_format of = { .type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE };
    of.fmt.pix_mp.width = W; of.fmt.pix_mp.height = H; of.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_NV12;
    of.fmt.pix_mp.num_planes = 1;
    if (xioctl(fd, VIDIOC_S_FMT, &of)) DIE("S_FMT output");
    const int bpl = of.fmt.pix_mp.plane_fmt[0].bytesperline, osz = of.fmt.pix_mp.plane_fmt[0].sizeimage;
    const int ah = (H + 31) & ~31;  // 輝度面の行数（1088）
    if (bpl != W || osz < bpl * ah * 3 / 2) DIE("想定外のバッファ配置（bytesperline=%d sizeimage=%d）", bpl, osz);
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
            EGLint at[] = { EGL_WIDTH, p ? W / 2 : W, EGL_HEIGHT, p ? ah / 2 : ah,
                            EGL_LINUX_DRM_FOURCC_EXT, p ? DRM_FORMAT_GR88 : DRM_FORMAT_R8,
                            EGL_DMA_BUF_PLANE0_FD_EXT, eb.fd, EGL_DMA_BUF_PLANE0_OFFSET_EXT, p ? bpl * ah : 0,
                            EGL_DMA_BUF_PLANE0_PITCH_EXT, bpl,
                            EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT, 0, EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT, 0, EGL_NONE };
            EGLImageKHR im = mkimg(dpy, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, NULL, at);
            if (im == EGL_NO_IMAGE_KHR) DIE("eglCreateImage plane%d err=0x%x", p, eglGetError());
            GLuint t; glGenTextures(1, &t); glBindTexture(GL_TEXTURE_2D, t); img2tex(GL_TEXTURE_2D, im);
            if (p) f_duv[i] = fbo_for(t); else f_dy[i] = fbo_for(t);
        }
    }
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

    out = fopen(argv[2], "wb"); if (!out) DIE("open out");
    nfree = nout; for (int i = 0; i < nout; i++) freeidx[i] = i;
    double s_up = 0, s_draw = 0, s_conv = 0, s_wait = 0, s_cam = 0;
    pthread_t dec_th; dec_frames = frames; pthread_create(&dec_th, NULL, decoder, NULL);

    double t0 = now();
    int f = 0;
    for (; f < frames && !quit; f++) {
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
        for (int i = 0; i < 3; i++) {
            if (!t_c[i]) t_c[i] = tex(GL_R8, pw[i], ph[i], GL_LINEAR);
            glBindTexture(GL_TEXTURE_2D, t_c[i]);
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, pw[i], ph[i], GL_RED, GL_UNSIGNED_BYTE, slot[s][i]);
        }
        pthread_mutex_lock(&mu); filled[s] = 0; pthread_cond_broadcast(&cv); pthread_mutex_unlock(&mu);
        // 工程ごとの完了待ちは時間を測るときだけ（待つとCPUとGPUの間にすき間ができて遅くなる）
        if (profile) glFinish();
        double b1 = now(); s_up += b1 - a;

        // ② カメラの絵をRGBで1920x1080へ → 計器を重ね描き
        glBindFramebuffer(GL_FRAMEBUFFER, f_rgb); glViewport(0, 0, W, H);
        glDisable(GL_BLEND);
        glUseProgram(p_jpg);
        const char *nm[3] = { "ty", "tu", "tv" };
        for (int i = 0; i < 3; i++) {
            glActiveTexture(GL_TEXTURE0 + i); glBindTexture(GL_TEXTURE_2D, t_c[i]);
            glUniform1i(glGetUniformLocation(p_jpg, nm[i]), i);
        }
        glUniform2f(glGetUniformLocation(p_jpg, "sy"), (float)CAM_W / pw[0], (float)CAM_H / ph[0]);
        glUniform2f(glGetUniformLocation(p_jpg, "sc"), chroma_w / pw[1], chroma_h / ph[1]);
        glDrawArrays(GL_TRIANGLES, 0, 3);
        glActiveTexture(GL_TEXTURE0);
        struct tele t; pthread_mutex_lock(&tmu); t = tl; pthread_mutex_unlock(&tmu);
        if (demo) {  // 見た目と警告の色を机の上で確かめるための作り物の値（画面にDEMOと出す）
            double ph = f / 30.0;
            t.speed = 90 + 70 * sin(ph * .4); t.rpm = 4500 + 3400 * sin(ph * .9); t.water = 98 + 14 * sin(ph * .15);
            t.oil = t.water + 10; t.lat_g = 1.1 * sin(ph * .7); t.long_g = .8 * cos(ph * .7);
            t.lap_no = 3; t.lap_run = fmod(ph, 95) / 60; t.lap_last = 96.37 / 60; t.lap_best = 94.85 / 60;
            t.got = now();
        }
        glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
        draw_hud(&t, now() - t.got);
        if (demo) text(40, 26, .6f, YELLOW, "DEMO");
        glDisable(GL_BLEND);
        if (profile) glFinish();
        double bd = now(); s_draw += bd - b1;

        // ③ エンコーダのバッファへ直接NV12を書く
        glBindTexture(GL_TEXTURE_2D, t_rgb);
        glBindFramebuffer(GL_FRAMEBUFFER, f_dy[bi]); glViewport(0, 0, W, ah);
        glUseProgram(p_dy); glUniform1i(glGetUniformLocation(p_dy, "t"), 0); glDrawArrays(GL_TRIANGLES, 0, 3);
        glBindFramebuffer(GL_FRAMEBUFFER, f_duv[bi]); glViewport(0, 0, W / 2, ah / 2);
        glUseProgram(p_duv); glUniform1i(glGetUniformLocation(p_duv, "t"), 0); glDrawArrays(GL_TRIANGLES, 0, 3);
        glFinish();
        s_conv += now() - bd;

        struct v4l2_plane pl[1] = {{ .bytesused = osz, .length = ob[bi].len }};
        struct v4l2_buffer b = { .type = t1, .memory = V4L2_MEMORY_MMAP, .index = bi, .length = 1, .m.planes = pl };
        b.timestamp.tv_sec = f / 30; b.timestamp.tv_usec = (f % 30) * 33333;
        // 1秒ごとにIDR（途中から再生を始められるキーフレーム）を出させる。I_PERIODだけでは
        // IDRでないIフレームになり、途中から読めない（手順書5-11）。IDRの前にはwrite_esがSPS・PPSを足す
        if (f && f % 30 == 0) set_ctrl(V4L2_CID_MPEG_VIDEO_FORCE_KEY_FRAME, 1, "force_key_frame");
        if (xioctl(fd, VIDIOC_QBUF, &b)) DIE("QBUF out");
        drain(0);
    }
    quit = 1;
    pthread_mutex_lock(&mu); pthread_cond_broadcast(&cv); pthread_mutex_unlock(&mu);
    struct v4l2_encoder_cmd ec = { .cmd = V4L2_ENC_CMD_STOP };
    xioctl(fd, VIDIOC_ENCODER_CMD, &ec);
    double tend = now() + 3; while (!eos && now() < tend) drain(1);
    double el = now() - t0;
    fclose(out);
    pthread_join(dec_th, NULL); pthread_join(tel_th, NULL);

    printf("frames=%d encoded=%d bytes=%zu elapsed=%.2fs fps=%.1f idr=%d sps_pps_inserted=%d\n",
           f, encoded, bytes, el, f / el, idr_count, header_inserted);
    if (f) printf("per-frame ms: wait_decoded=%.2f upload=%.2f draw=%.2f convert=%.2f wait_encoder=%.2f"
                  " (decoder: wait_camera=%.2f jpeg_decode=%.2f)\n",
                  s_cam / f * 1e3, s_up / f * 1e3, s_draw / f * 1e3, s_conv / f * 1e3, s_wait / f * 1e3,
                  d_wait / f * 1e3, d_dec / f * 1e3);
    struct rusage ru; getrusage(RUSAGE_SELF, &ru);
    double cpu = ru.ru_utime.tv_sec + ru.ru_utime.tv_usec * 1e-6 + ru.ru_stime.tv_sec + ru.ru_stime.tv_usec * 1e-6;
    printf("process CPU: %.1f%% of one core\n", cpu / el * 100);
    return 0;
}
