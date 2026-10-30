// UNO Q：GPUの完了待ち（glFinish）そのものにかかる時間を測る（unoq_video_check_procedure.md 5-13）
//   何も描かずに待つ／64x64を塗って待つ、を100回ずつ。引数で呼ぶ間隔（ms）を空けられる
//   （焼き込みは1枚ごとにカメラを待つので、GPUが休んでから呼ばれる。そのときの待ちを見る）
// ビルド(UNO Q上): gcc -O2 -o gpu_latency gpu_latency.c -lEGL -lGLESv2
// 実行: ./gpu_latency [間隔ms=0]
#define _GNU_SOURCE
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static int cmp(const void *a, const void *b) { double x = *(const double *)a, y = *(const double *)b; return x < y ? -1 : x > y; }
static void stat(const char *nm, double *v, int n) {
    qsort(v, n, sizeof *v, cmp);
    printf("%-28s min=%.2f med=%.2f p90=%.2f max=%.2f ms\n", nm, v[0] * 1e3, v[n / 2] * 1e3, v[n * 9 / 10] * 1e3, v[n - 1] * 1e3);
}

int main(int argc, char **argv) {
    int gap_ms = argc > 1 ? atoi(argv[1]) : 0;
    PFNEGLGETPLATFORMDISPLAYEXTPROC getdpy = (void *)eglGetProcAddress("eglGetPlatformDisplayEXT");
    EGLDisplay d = getdpy(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
    eglInitialize(d, NULL, NULL); eglBindAPI(EGL_OPENGL_ES_API);
    EGLint ca[] = { EGL_CONTEXT_MAJOR_VERSION, 3, EGL_NONE };
    EGLContext c = eglCreateContext(d, EGL_NO_CONFIG_KHR, EGL_NO_CONTEXT, ca);
    eglMakeCurrent(d, EGL_NO_SURFACE, EGL_NO_SURFACE, c);
    GLuint t, f;
    glGenTextures(1, &t); glBindTexture(GL_TEXTURE_2D, t); glTexStorage2D(GL_TEXTURE_2D, 1, GL_RGBA8, 64, 64);
    glGenFramebuffers(1, &f); glBindFramebuffer(GL_FRAMEBUFFER, f);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, t, 0);
    glViewport(0, 0, 64, 64);
    enum { N = 100 };
    double v[N];
    for (int i = 0; i < N; i++) { if (gap_ms) usleep(gap_ms * 1000); double a = now(); glFinish(); v[i] = now() - a; }
    stat("empty glFinish", v, N);
    for (int i = 0; i < N; i++) {
        if (gap_ms) usleep(gap_ms * 1000);
        double a = now(); glClearColor(i & 1, 0, 0, 1); glClear(GL_COLOR_BUFFER_BIT); glFinish(); v[i] = now() - a;
    }
    stat("clear 64x64 + glFinish", v, N);
    return 0;
}
