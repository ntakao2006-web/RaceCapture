// UNO Q 焼き込みパイプライン試験（カメラ無し）
//   カメラ代わりのNV12 → GPUへアップロード → RGB化 → プロット重ね描き → GPUでNV12へ変換
//   → V4L2エンコーダ(venus)の入力バッファへ → H.264
// 目的: 「合成した絵をCPU色変換なしでエンコーダへ渡し、1080p30が回るか」を測る（unoq_video_check_procedure.md 5-6）
//
// ビルド(UNO Q上): gcc -O2 -o overlay_enc_test overlay_enc_test.c -lEGL -lGLESv2 -ljpeg -lm -lpthread
// 実行: ./overlay_enc_test <src_2s.nv12> <out.h264> [frames=900] [pace=0|1] [mode=0|1] [thr=0|1]
//   pace=1 で30fpsに合わせて流す（実運用相当のCPU負荷を見る）。0 は全速（上限性能を見る）
//   mode=0: GPUの結果をglReadPixelsでエンコーダのバッファへコピー
//   mode=1: エンコーダのバッファをdmabufでGPUへ共有し、GPUが直接NV12を書く（コピー無し）
//   thr=1: 実カメラのJPEG展開を別スレッドで行い、GPUの作業と重ねる（展開先は2枚を交互に使う）
// 実カメラ: src に /dev/videoN（UVC・MJPEG）を渡すと、カメラの画をCPU(libjpeg-turbo)で展開して入力にする
//   カメラの解像度は CAM_W x CAM_H（1080pでなければGPUで1920x1080へ拡大）。カメラのfpsで律速されるので pace は不要
//   エンコーダはデバイス名で探す（カメラを挿すと /dev/video0 がカメラに取られるため）
#define _GNU_SOURCE
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <GLES2/gl2ext.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>  // jpeglib.h より前に要る
#include <jpeglib.h>
#include <linux/videodev2.h>
#include <math.h>
#include <poll.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define W 1920
#define H 1080
#define NOUT 4
#define NCAP 4
#define NPTS 600
#define NTRACE 4
#define CAM_W 1280
#define CAM_H 720
#define NCAM 4
#define FOURCC(a, b, c, d) ((uint32_t)(a) | ((uint32_t)(b) << 8) | ((uint32_t)(c) << 16) | ((uint32_t)(d) << 24))
#define DRM_FORMAT_R8 FOURCC('R', '8', ' ', ' ')
#define DRM_FORMAT_GR88 FOURCC('G', 'R', '8', '8')

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
#define DIE(...) do { fprintf(stderr, __VA_ARGS__); fprintf(stderr, " (errno=%d %s)\n", errno, strerror(errno)); exit(1); } while (0)

static int xioctl(int fd, unsigned long req, void *arg) {
    int r; do { r = ioctl(fd, req, arg); } while (r < 0 && errno == EINTR); return r;
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

// 画面全体を覆う三角形（頂点IDから生成）
static const char *VS_FULL =
    "#version 300 es\n"
    "void main(){ vec2 p=vec2((gl_VertexID<<1)&2, gl_VertexID&2); gl_Position=vec4(p*2.0-1.0,0.0,1.0); }\n";

// NV12(BT.601 limited) → RGB。行0=画像の上端で統一する
static const char *FS_YUV2RGB =
    "#version 300 es\nprecision mediump float;\n"
    "uniform sampler2D ty; uniform sampler2D tuv; out vec4 o;\n"
    "void main(){ ivec2 p=ivec2(gl_FragCoord.xy);\n"
    "  float y=(texelFetch(ty,p,0).r-0.0625)*1.164; vec2 c=texelFetch(tuv,p/2,0).rg-0.5;\n"
    "  o=vec4(y+1.596*c.y, y-0.392*c.x-0.813*c.y, y+2.017*c.x, 1.0); }\n";

// 実カメラ用：JPEGを展開したY/Cb/Cr（JFIF＝BT.601 full range、色差は間引かれたまま）→ RGB、1920x1080へ拡大
// sc＝テクスチャのうち画像が入っている割合（展開バッファは8/16の倍数に切り上がっているため）
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

// mode=0 用：RGBA8の1画素にY4個を詰める（幅480）。glReadPixelsのRGBA読み出しがそのままYプレーンになる
static const char *FS_PACK_Y =
    "#version 300 es\nprecision highp float; uniform sampler2D t; out vec4 o;\n"
    "float Y(ivec2 p){ if(p.y>=1080) return 0.0625; vec3 c=texelFetch(t,p,0).rgb; return 0.0625+dot(c,vec3(0.257,0.504,0.098)); }\n"
    "void main(){ ivec2 p=ivec2(gl_FragCoord.xy); int x=p.x*4;\n"
    "  o=vec4(Y(ivec2(x,p.y)),Y(ivec2(x+1,p.y)),Y(ivec2(x+2,p.y)),Y(ivec2(x+3,p.y))); }\n";

// mode=0 用：UV（2x2平均＝線形補間で中心を1回サンプル）。1画素に U0 V0 U1 V1（幅480・高さ544）
static const char *FS_PACK_UV =
    "#version 300 es\nprecision highp float; uniform sampler2D t; out vec4 o;\n"
    "vec2 UV(int cx,int cy){ if(cy>=540) return vec2(0.5); vec3 c=texture(t,(vec2(cx*2,cy*2)+1.0)/vec2(1920.0,1080.0)).rgb;\n"
    "  return vec2(0.5+dot(c,vec3(-0.148,-0.291,0.439)), 0.5+dot(c,vec3(0.439,-0.368,-0.071))); }\n"
    "void main(){ ivec2 p=ivec2(gl_FragCoord.xy); o=vec4(UV(p.x*2,p.y),UV(p.x*2+1,p.y)); }\n";

// mode=1 用：R8（Y）・GR88（UV）のテクスチャへ直接書く
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

// ---------------------------------------------------------------- V4L2
struct vbuf { void *p; size_t len; };
static int fd, t1 = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE, t2 = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
static struct vbuf ob[NOUT], cb[NCAP];
static int freeidx[NOUT], nfree, encoded, eos;
static size_t bytes;
static FILE *out;

// /dev/video* からデバイス名（VIDIOC_QUERYCAPのcard）で探す
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

// ---------------------------------------------------------------- 実カメラ（UVC・MJPEG）
static int cfd = -1;
static struct vbuf camb[NCAM];
static struct jpeg_decompress_struct jd;
static struct jpeg_error_mgr jerr;
static uint8_t *slot[2][3];  // 展開先（2枚を交互に使う。成分ごと、幅・高さは8の倍数へ切り上げ）
static int pw[3], ph[3];
// 色差の間引き方（最初の1枚で控える）。jdのcomp_infoは1枚ごとに作り直されて解放されるので、
// thr=1のときGPU側のスレッドから読むと解放済みのメモリを読むことになる（5分試験の異常終了の原因）
static float chroma_w, chroma_h;

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

// 1枚待って slot[s] へ展開する。展開は色変換・色差の補間をせず成分のまま取り出す（raw_data_out）
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
            printf("jpeg comp%d: %dx%d (h%d v%d)\n", i, pw[i], ph[i], jd.comp_info[i].h_samp_factor, jd.comp_info[i].v_samp_factor);
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

// thr=1：展開スレッド。slot[s]が空くのを待って次の1枚を展開し、埋まったことをGPU側へ知らせる
static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cv = PTHREAD_COND_INITIALIZER;
static int filled[2], dec_frames;
static double d_wait, d_dec;
static void *decoder(void *arg) {
    (void)arg;
    for (int f = 0; f < dec_frames; f++) {
        int s = f & 1;
        pthread_mutex_lock(&mu); while (filled[s]) pthread_cond_wait(&cv, &mu); pthread_mutex_unlock(&mu);
        cam_frame(s, &d_wait, &d_dec);
        pthread_mutex_lock(&mu); filled[s] = 1; pthread_cond_broadcast(&cv); pthread_mutex_unlock(&mu);
    }
    return NULL;
}

// capture側を取り出してファイルへ。outputの返却も回収する
static void drain(int block) {
    struct pollfd pf = { .fd = fd, .events = POLLIN | POLLOUT };
    if (poll(&pf, 1, block ? 1000 : 0) <= 0) return;
    for (;;) {
        struct v4l2_plane pl[1] = {0};
        struct v4l2_buffer b = { .type = t2, .memory = V4L2_MEMORY_MMAP, .length = 1, .m.planes = pl };
        if (xioctl(fd, VIDIOC_DQBUF, &b)) break;
        fwrite(cb[b.index].p, 1, pl[0].bytesused, out); bytes += pl[0].bytesused;
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

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s src.nv12 out.h264 [frames] [pace] [mode]\n", argv[0]); return 1; }
    int frames = argc > 3 ? atoi(argv[3]) : 900;
    int pace = argc > 4 ? atoi(argv[4]) : 0;
    int mode = argc > 5 ? atoi(argv[5]) : 0;
    int thr = argc > 6 ? atoi(argv[6]) : 0;

    // 入力：実カメラ（/dev/videoN）か、カメラ代わりの素材（1920x1080 NV12 を詰めたもの）
    const int cam = !strncmp(argv[1], "/dev/video", 10);
    const size_t fsz = W * H * 3 / 2; int nsrc = 0;
    uint8_t *src = NULL;
    if (cam) {
        cam_open(argv[1]);
    } else {
        int sfd = open(argv[1], O_RDONLY); if (sfd < 0) DIE("open src");
        struct stat st; fstat(sfd, &st);
        nsrc = st.st_size / fsz;
        src = mmap(NULL, st.st_size, PROT_READ, MAP_PRIVATE | MAP_POPULATE, sfd, 0);
        if (src == MAP_FAILED || nsrc < 1) DIE("mmap src");
    }

    // ---- EGL（画面を使わない surfaceless）
    PFNEGLGETPLATFORMDISPLAYEXTPROC getdpy = (void *)eglGetProcAddress("eglGetPlatformDisplayEXT");
    EGLDisplay dpy = getdpy(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
    if (!eglInitialize(dpy, NULL, NULL)) DIE("eglInitialize");
    eglBindAPI(EGL_OPENGL_ES_API);
    EGLint cattr[] = { EGL_CONTEXT_MAJOR_VERSION, 3, EGL_NONE };
    EGLContext ctx = eglCreateContext(dpy, EGL_NO_CONFIG_KHR, EGL_NO_CONTEXT, cattr);
    if (ctx == EGL_NO_CONTEXT || !eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, ctx)) DIE("egl context");
    printf("GL_RENDERER: %s\n", glGetString(GL_RENDERER));

    GLuint p_rgb = program(VS_FULL, FS_YUV2RGB), p_col = program(VS_OVL, FS_COL);
    GLuint p_y = program(VS_FULL, FS_PACK_Y), p_uv = program(VS_FULL, FS_PACK_UV);
    GLuint p_dy = program(VS_FULL, FS_Y), p_duv = program(VS_FULL, FS_UV);
    GLuint p_jpg = program(VS_FULL, FS_JPEG2RGB), t_c[3] = {0};
    GLuint t_y = tex(GL_R8, W, H, GL_NEAREST), t_uv = tex(GL_RG8, W / 2, H / 2, GL_NEAREST);
    GLuint t_rgb = tex(GL_RGBA8, W, H, GL_LINEAR);
    GLuint t_py = tex(GL_RGBA8, W / 4, 1088, GL_NEAREST), t_puv = tex(GL_RGBA8, W / 4, 544, GL_NEAREST);
    GLuint f_rgb = fbo_for(t_rgb), f_py = fbo_for(t_py), f_puv = fbo_for(t_puv);
    GLuint vao, vbo; glGenVertexArrays(1, &vao); glBindVertexArray(vao);
    glGenBuffers(1, &vbo); glBindBuffer(GL_ARRAY_BUFFER, vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof(float) * 2 * (NPTS * NTRACE + 64), NULL, GL_STREAM_DRAW);
    glEnableVertexAttribArray(0); glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, 0);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1); glPixelStorei(GL_PACK_ALIGNMENT, 1);
    glLineWidth(3.0f);

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
    const int ah = (H + 31) & ~31;  // 輝度面の行数＝高さを32の倍数へ切り上げ（1088）。sizeimageは末尾に余白を含むので割り算では出せない
    printf("encoder input: %ux%u planes=%d bytesperline=%d sizeimage=%d luma_rows=%d\n",
           of.fmt.pix_mp.width, of.fmt.pix_mp.height, of.fmt.pix_mp.num_planes, bpl, osz, ah);
    if (bpl != W || osz < bpl * ah * 3 / 2) DIE("想定外のバッファ配置（bytesperline=%d sizeimage=%d）", bpl, osz);

    struct v4l2_streamparm sp = { .type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE };
    sp.parm.output.timeperframe.numerator = 1; sp.parm.output.timeperframe.denominator = 30;
    if (xioctl(fd, VIDIOC_S_PARM, &sp)) DIE("S_PARM");  // これが無いとクロックが上がらない（手順書5-5①）
    struct v4l2_control bc = { .id = V4L2_CID_MPEG_VIDEO_BITRATE, .value = 12000000 };
    if (xioctl(fd, VIDIOC_S_CTRL, &bc)) fprintf(stderr, "warn: bitrate not set\n");

    struct v4l2_requestbuffers rq = { .count = NOUT, .type = t1, .memory = V4L2_MEMORY_MMAP };
    if (xioctl(fd, VIDIOC_REQBUFS, &rq)) DIE("REQBUFS out");
    int nout = rq.count < NOUT ? rq.count : NOUT;
    for (int i = 0; i < nout; i++) {
        struct v4l2_plane pl[1] = {0};
        struct v4l2_buffer b = { .type = t1, .memory = V4L2_MEMORY_MMAP, .index = i, .length = 1, .m.planes = pl };
        if (xioctl(fd, VIDIOC_QUERYBUF, &b)) DIE("QUERYBUF out");
        ob[i].len = pl[0].length; ob[i].p = mmap(NULL, pl[0].length, PROT_READ | PROT_WRITE, MAP_SHARED, fd, pl[0].m.mem_offset);
        if (ob[i].p == MAP_FAILED) DIE("mmap out");
    }

    // mode=1: エンコーダの入力バッファをdmabufとして取り出し、GPUの描画先（Y=R8, UV=GR88）にする
    GLuint f_dy[NOUT], f_duv[NOUT];
    if (mode == 1) {
        PFNEGLCREATEIMAGEKHRPROC mkimg = (void *)eglGetProcAddress("eglCreateImageKHR");
        PFNGLEGLIMAGETARGETTEXTURE2DOESPROC img2tex = (void *)eglGetProcAddress("glEGLImageTargetTexture2DOES");
        for (int i = 0; i < nout; i++) {
            struct v4l2_exportbuffer eb = { .type = t1, .index = i, .plane = 0, .flags = O_RDWR };
            if (xioctl(fd, VIDIOC_EXPBUF, &eb)) DIE("EXPBUF");
            for (int pl = 0; pl < 2; pl++) {
                // modifierをLINEARと明示する。Mesa 25.2（2026-10-21交換後の基板）は、指定が無いと
                // eglCreateImageをEGL_BAD_ALLOCで断る（tools/unoq_overlay_enc/egl_import_probe.c、手順書5-10）
                EGLint at[] = { EGL_WIDTH, pl ? W / 2 : W, EGL_HEIGHT, pl ? ah / 2 : ah,
                                EGL_LINUX_DRM_FOURCC_EXT, pl ? DRM_FORMAT_GR88 : DRM_FORMAT_R8,
                                EGL_DMA_BUF_PLANE0_FD_EXT, eb.fd, EGL_DMA_BUF_PLANE0_OFFSET_EXT, pl ? bpl * ah : 0,
                                EGL_DMA_BUF_PLANE0_PITCH_EXT, bpl,
                                EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT, 0, EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT, 0, EGL_NONE };
                EGLImageKHR im = mkimg(dpy, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, NULL, at);
                if (im == EGL_NO_IMAGE_KHR) DIE("eglCreateImage plane%d err=0x%x", pl, eglGetError());
                GLuint t; glGenTextures(1, &t); glBindTexture(GL_TEXTURE_2D, t); img2tex(GL_TEXTURE_2D, im);
                if (pl) f_duv[i] = fbo_for(t); else f_dy[i] = fbo_for(t);
            }
        }
        printf("dmabuf: エンコーダの入力バッファ%d枚をGPUの描画先として共有\n", nout);
    }

    rq = (struct v4l2_requestbuffers){ .count = NCAP, .type = t2, .memory = V4L2_MEMORY_MMAP };
    if (xioctl(fd, VIDIOC_REQBUFS, &rq)) DIE("REQBUFS cap");
    int ncap = rq.count < NCAP ? rq.count : NCAP;
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
    double s_up = 0, s_draw = 0, s_conv = 0, s_read = 0, s_wait = 0, s_cam = 0, s_dec = 0;
    float *pts = malloc(sizeof(float) * 2 * NPTS * NTRACE);
    const float tc[4][4] = { {1, .3f, .2f, 1}, {.2f, 1, .3f, 1}, {.3f, .6f, 1, 1}, {1, 1, .2f, 1} };

    pthread_t dec_th;
    if (cam && thr) { dec_frames = frames; pthread_create(&dec_th, NULL, decoder, NULL); }
    double t0 = now(), next = t0;
    for (int f = 0; f < frames; f++) {
        double a = now();
        while (nfree == 0) drain(1);
        s_wait += now() - a;
        int bi = freeidx[--nfree];

        // ① カメラ映像のアップロード（素材のときはV4L2から受けた画をGPUへ渡す分に相当）
        const int s = thr ? f & 1 : 0;
        if (cam && thr) {  // 展開スレッドが slot[s] を埋めるのを待つ（待った時間をカメラ待ちとして数える）
            a = now();
            pthread_mutex_lock(&mu); while (!filled[s]) pthread_cond_wait(&cv, &mu); pthread_mutex_unlock(&mu);
            s_cam += now() - a;
        } else if (cam) {
            cam_frame(0, &s_cam, &s_dec);
        }
        a = now();
        if (cam) {
            for (int i = 0; i < 3; i++) {
                if (!t_c[i]) t_c[i] = tex(GL_R8, pw[i], ph[i], GL_LINEAR);
                glBindTexture(GL_TEXTURE_2D, t_c[i]);
                glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, pw[i], ph[i], GL_RED, GL_UNSIGNED_BYTE, slot[s][i]);
            }
            if (thr) { pthread_mutex_lock(&mu); filled[s] = 0; pthread_cond_broadcast(&cv); pthread_mutex_unlock(&mu); }
        } else {
            const uint8_t *fr = src + (size_t)(f % nsrc) * fsz;
            glBindTexture(GL_TEXTURE_2D, t_y);  glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, W, H, GL_RED, GL_UNSIGNED_BYTE, fr);
            glBindTexture(GL_TEXTURE_2D, t_uv); glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, W / 2, H / 2, GL_RG, GL_UNSIGNED_BYTE, fr + W * H);
        }
        glFinish();
        double b1 = now(); s_up += b1 - a;

        // ② RGB化 → 重ね描き（下部の半透明パネル・4本の時系列・バー4本）
        glBindFramebuffer(GL_FRAMEBUFFER, f_rgb); glViewport(0, 0, W, H);
        glDisable(GL_BLEND);
        if (cam) {
            glUseProgram(p_jpg);
            const char *nm[3] = { "ty", "tu", "tv" };
            for (int i = 0; i < 3; i++) {
                glActiveTexture(GL_TEXTURE0 + i); glBindTexture(GL_TEXTURE_2D, t_c[i]);
                glUniform1i(glGetUniformLocation(p_jpg, nm[i]), i);
            }
            // テクスチャは上端が行0。描画先も行0＝上端で扱っている（素材の経路と同じ）
            glUniform2f(glGetUniformLocation(p_jpg, "sy"), (float)CAM_W / pw[0], (float)CAM_H / ph[0]);
            glUniform2f(glGetUniformLocation(p_jpg, "sc"), chroma_w / pw[1], chroma_h / ph[1]);
        } else {
            glUseProgram(p_rgb);
            glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, t_y);
            glActiveTexture(GL_TEXTURE1); glBindTexture(GL_TEXTURE_2D, t_uv);
            glUniform1i(glGetUniformLocation(p_rgb, "ty"), 0); glUniform1i(glGetUniformLocation(p_rgb, "tuv"), 1);
        }
        glDrawArrays(GL_TRIANGLES, 0, 3);
        glActiveTexture(GL_TEXTURE0);

        glUseProgram(p_col); GLint ucol = glGetUniformLocation(p_col, "col");
        glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
        float panel[] = { 0, 760, 1920, 760, 0, 1080, 1920, 760, 1920, 1080, 0, 1080 };
        glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof panel, panel);
        glUniform4f(ucol, 0, 0, 0, 0.55f); glDrawArrays(GL_TRIANGLES, 0, 6);
        for (int k = 0; k < NTRACE; k++)
            for (int i = 0; i < NPTS; i++) {
                float x = 40 + i * (1840.0f / NPTS), ph = (f + i) * 0.03f * (k + 1);
                pts[(k * NPTS + i) * 2] = x;
                pts[(k * NPTS + i) * 2 + 1] = 800 + k * 70 + 30 * sinf(ph) + 10 * sinf(ph * 3.7f);
            }
        glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof(float) * 2 * NPTS * NTRACE, pts);
        for (int k = 0; k < NTRACE; k++) { glUniform4fv(ucol, 1, tc[k]); glDrawArrays(GL_LINE_STRIP, k * NPTS, NPTS); }
        for (int k = 0; k < 4; k++) {
            float h = 150 + 120 * sinf(f * 0.05f + k), x0 = 1600 + k * 70, y1 = 700, y0 = y1 - h;
            float bar[] = { x0, y0, x0 + 50, y0, x0, y1, x0 + 50, y0, x0 + 50, y1, x0, y1 };
            glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof bar, bar);
            glUniform4fv(ucol, 1, tc[k]); glDrawArrays(GL_TRIANGLES, 0, 6);
        }
        glDisable(GL_BLEND);
        glFinish();
        double bd = now(); s_draw += bd - b1;

        // ③ GPUでNV12へ
        glBindTexture(GL_TEXTURE_2D, t_rgb);
        uint8_t *dst = ob[bi].p;
        if (mode == 1) {  // エンコーダのバッファへ直接書く（コピー無し）
            glBindFramebuffer(GL_FRAMEBUFFER, f_dy[bi]); glViewport(0, 0, W, ah);
            glUseProgram(p_dy); glUniform1i(glGetUniformLocation(p_dy, "t"), 0); glDrawArrays(GL_TRIANGLES, 0, 3);
            glBindFramebuffer(GL_FRAMEBUFFER, f_duv[bi]); glViewport(0, 0, W / 2, ah / 2);
            glUseProgram(p_duv); glUniform1i(glGetUniformLocation(p_duv, "t"), 0); glDrawArrays(GL_TRIANGLES, 0, 3);
            glFinish();
            s_conv += now() - bd;
        } else {  // RGBA8へ詰めてから glReadPixels でコピー
            glBindFramebuffer(GL_FRAMEBUFFER, f_py); glViewport(0, 0, W / 4, 1088);
            glUseProgram(p_y); glUniform1i(glGetUniformLocation(p_y, "t"), 0); glDrawArrays(GL_TRIANGLES, 0, 3);
            glBindFramebuffer(GL_FRAMEBUFFER, f_puv); glViewport(0, 0, W / 4, 544);
            glUseProgram(p_uv); glUniform1i(glGetUniformLocation(p_uv, "t"), 0); glDrawArrays(GL_TRIANGLES, 0, 3);
            glFinish();
            double b2 = now(); s_conv += b2 - bd;
            glBindFramebuffer(GL_FRAMEBUFFER, f_py);  glReadPixels(0, 0, W / 4, 1088, GL_RGBA, GL_UNSIGNED_BYTE, dst);
            glBindFramebuffer(GL_FRAMEBUFFER, f_puv); glReadPixels(0, 0, W / 4, 544, GL_RGBA, GL_UNSIGNED_BYTE, dst + W * 1088);
            s_read += now() - b2;
        }

        struct v4l2_plane pl[1] = {{ .bytesused = osz, .length = ob[bi].len }};
        struct v4l2_buffer b = { .type = t1, .memory = V4L2_MEMORY_MMAP, .index = bi, .length = 1, .m.planes = pl };
        b.timestamp.tv_sec = f / 30; b.timestamp.tv_usec = (f % 30) * 33333;
        if (xioctl(fd, VIDIOC_QBUF, &b)) DIE("QBUF out");
        drain(0);

        if (pace) { next += 1.0 / 30; double r = next - now(); if (r > 0) usleep(r * 1e6); }
    }
    struct v4l2_encoder_cmd ec = { .cmd = V4L2_ENC_CMD_STOP };
    xioctl(fd, VIDIOC_ENCODER_CMD, &ec);
    double tend = now() + 3; while (!eos && now() < tend) drain(1);
    double el = now() - t0;
    fclose(out);

    printf("frames_in=%d encoded=%d bytes=%zu elapsed=%.2fs fps=%.1f\n", frames, encoded, bytes, el, frames / el);
    if (cam && thr) pthread_join(dec_th, NULL);
    printf("mode=%d pace=%d thr=%d per-frame ms: upload=%.2f draw=%.2f convert=%.2f readback=%.2f wait_encoder=%.2f\n", mode, pace, thr,
           s_up / frames * 1e3, s_draw / frames * 1e3, s_conv / frames * 1e3, s_read / frames * 1e3, s_wait / frames * 1e3);
    if (cam && thr) printf("camera per-frame ms: wait_decoded=%.2f (decoder thread: wait_camera=%.2f jpeg_decode=%.2f)\n",
                           s_cam / frames * 1e3, d_wait / frames * 1e3, d_dec / frames * 1e3);
    else if (cam) printf("camera per-frame ms: wait_camera=%.2f jpeg_decode=%.2f\n", s_cam / frames * 1e3, s_dec / frames * 1e3);
    struct rusage ru; getrusage(RUSAGE_SELF, &ru);
    double cpu = ru.ru_utime.tv_sec + ru.ru_utime.tv_usec * 1e-6 + ru.ru_stime.tv_sec + ru.ru_stime.tv_usec * 1e-6;
    printf("process CPU: %.1f%% of one core (user+sys %.2fs / %.2fs)\n", cpu / el * 100, cpu, el);
    return 0;
}
