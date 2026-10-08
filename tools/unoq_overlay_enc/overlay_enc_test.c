// UNO Q 焼き込みパイプライン試験（カメラ無し）
//   カメラ代わりのNV12 → GPUへアップロード → RGB化 → プロット重ね描き → GPUでNV12へ変換
//   → V4L2エンコーダ(venus)の入力バッファへ → H.264
// 目的: 「合成した絵をCPU色変換なしでエンコーダへ渡し、1080p30が回るか」を測る（unoq_video_check_procedure.md 5-6）
//
// ビルド(UNO Q上): gcc -O2 -o overlay_enc_test overlay_enc_test.c -lEGL -lGLESv2 -lm
// 実行: ./overlay_enc_test <src_2s.nv12> <out.h264> [frames=900] [pace=0|1] [mode=0|1]
//   pace=1 で30fpsに合わせて流す（実運用相当のCPU負荷を見る）。0 は全速（上限性能を見る）
//   mode=0: GPUの結果をglReadPixelsでエンコーダのバッファへコピー
//   mode=1: エンコーダのバッファをdmabufでGPUへ共有し、GPUが直接NV12を書く（コピー無し）
#define _GNU_SOURCE
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <GLES2/gl2ext.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <math.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define W 1920
#define H 1080
#define NOUT 4
#define NCAP 4
#define NPTS 600
#define NTRACE 4
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

    // カメラ代わりの素材（1920x1080 NV12 を詰めたもの）
    int sfd = open(argv[1], O_RDONLY); if (sfd < 0) DIE("open src");
    struct stat st; fstat(sfd, &st);
    const size_t fsz = W * H * 3 / 2; int nsrc = st.st_size / fsz;
    uint8_t *src = mmap(NULL, st.st_size, PROT_READ, MAP_PRIVATE | MAP_POPULATE, sfd, 0);
    if (src == MAP_FAILED || nsrc < 1) DIE("mmap src");

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
    fd = open("/dev/video0", O_RDWR | O_NONBLOCK); if (fd < 0) DIE("open /dev/video0");
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
                EGLint at[] = { EGL_WIDTH, pl ? W / 2 : W, EGL_HEIGHT, pl ? ah / 2 : ah,
                                EGL_LINUX_DRM_FOURCC_EXT, pl ? DRM_FORMAT_GR88 : DRM_FORMAT_R8,
                                EGL_DMA_BUF_PLANE0_FD_EXT, eb.fd, EGL_DMA_BUF_PLANE0_OFFSET_EXT, pl ? bpl * ah : 0,
                                EGL_DMA_BUF_PLANE0_PITCH_EXT, bpl, EGL_NONE };
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
    double s_up = 0, s_draw = 0, s_conv = 0, s_read = 0, s_wait = 0;
    float *pts = malloc(sizeof(float) * 2 * NPTS * NTRACE);
    const float tc[4][4] = { {1, .3f, .2f, 1}, {.2f, 1, .3f, 1}, {.3f, .6f, 1, 1}, {1, 1, .2f, 1} };

    double t0 = now(), next = t0;
    for (int f = 0; f < frames; f++) {
        double a = now();
        while (nfree == 0) drain(1);
        s_wait += now() - a;
        int bi = freeidx[--nfree];

        // ① カメラ映像のアップロード（実カメラでもV4L2から受けた画をGPUへ渡す分に相当）
        a = now();
        const uint8_t *fr = src + (size_t)(f % nsrc) * fsz;
        glBindTexture(GL_TEXTURE_2D, t_y);  glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, W, H, GL_RED, GL_UNSIGNED_BYTE, fr);
        glBindTexture(GL_TEXTURE_2D, t_uv); glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, W / 2, H / 2, GL_RG, GL_UNSIGNED_BYTE, fr + W * H);
        glFinish();
        double b1 = now(); s_up += b1 - a;

        // ② RGB化 → 重ね描き（下部の半透明パネル・4本の時系列・バー4本）
        glBindFramebuffer(GL_FRAMEBUFFER, f_rgb); glViewport(0, 0, W, H);
        glDisable(GL_BLEND); glUseProgram(p_rgb);
        glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, t_y);
        glActiveTexture(GL_TEXTURE1); glBindTexture(GL_TEXTURE_2D, t_uv);
        glUniform1i(glGetUniformLocation(p_rgb, "ty"), 0); glUniform1i(glGetUniformLocation(p_rgb, "tuv"), 1);
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
    printf("mode=%d pace=%d per-frame ms: upload=%.2f draw=%.2f convert=%.2f readback=%.2f wait_encoder=%.2f\n", mode, pace,
           s_up / frames * 1e3, s_draw / frames * 1e3, s_conv / frames * 1e3, s_read / frames * 1e3, s_wait / frames * 1e3);
    return 0;
}
