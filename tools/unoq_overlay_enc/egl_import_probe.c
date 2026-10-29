// UNO Q：エンコーダ（venus）の入力バッファを、どの幅・ピッチならMesa（freedreno）がEGLImageとして受け取るかを調べる
//   （dmabuf_probeでカーネルの取り込みは通ったので、Mesa側の条件を探す。unoq_video_check_procedure.md 5-10）
// ビルド(UNO Q上): gcc -O2 -o egl_import_probe egl_import_probe.c -lEGL -lGLESv2
#define _GNU_SOURCE
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define FOURCC(a, b, c, d) ((uint32_t)(a) | ((uint32_t)(b) << 8) | ((uint32_t)(c) << 16) | ((uint32_t)(d) << 24))

static int open_by_name(const char *name) {
    char path[32];
    for (int i = 0; i < 64; i++) {
        snprintf(path, sizeof path, "/dev/video%d", i);
        int f = open(path, O_RDWR | O_NONBLOCK); if (f < 0) continue;
        struct v4l2_capability cap = {0};
        if (!ioctl(f, VIDIOC_QUERYCAP, &cap) && !strcmp((char *)cap.card, name)) return f;
        close(f);
    }
    return -1;
}

int main(void) {
    int enc = open_by_name("Qualcomm Venus video encoder");
    struct v4l2_format cf = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE };
    cf.fmt.pix_mp.width = 1920; cf.fmt.pix_mp.height = 1080; cf.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_H264;
    cf.fmt.pix_mp.num_planes = 1; cf.fmt.pix_mp.plane_fmt[0].sizeimage = 4 << 20;
    ioctl(enc, VIDIOC_S_FMT, &cf);
    struct v4l2_format of = { .type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE };
    of.fmt.pix_mp.width = 1920; of.fmt.pix_mp.height = 1080; of.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_NV12;
    of.fmt.pix_mp.num_planes = 1;
    ioctl(enc, VIDIOC_S_FMT, &of);
    printf("encoder NV12 bytesperline=%u sizeimage=%u\n", of.fmt.pix_mp.plane_fmt[0].bytesperline, of.fmt.pix_mp.plane_fmt[0].sizeimage);
    struct v4l2_requestbuffers rq = { .count = 1, .type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE, .memory = V4L2_MEMORY_MMAP };
    ioctl(enc, VIDIOC_REQBUFS, &rq);
    struct v4l2_exportbuffer eb = { .type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE, .index = 0, .plane = 0, .flags = O_RDWR };
    if (ioctl(enc, VIDIOC_EXPBUF, &eb)) { perror("EXPBUF"); return 1; }

    PFNEGLGETPLATFORMDISPLAYEXTPROC getdpy = (void *)eglGetProcAddress("eglGetPlatformDisplayEXT");
    EGLDisplay dpy = getdpy(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
    eglInitialize(dpy, NULL, NULL);
    PFNEGLCREATEIMAGEKHRPROC mkimg = (void *)eglGetProcAddress("eglCreateImageKHR");
    PFNEGLDESTROYIMAGEKHRPROC rmimg = (void *)eglGetProcAddress("eglDestroyImageKHR");

    struct { const char *nm; uint32_t fourcc; int cpp; } fmts[] = {
        { "R8", FOURCC('R', '8', ' ', ' '), 1 }, { "GR88", FOURCC('G', 'R', '8', '8'), 2 },
        { "ARGB8888", FOURCC('A', 'R', '2', '4'), 4 } };
    int pitches[] = { 1920, 2048 };
    int heights[] = { 1088, 544, 64, 16 };
    for (unsigned f = 0; f < 3; f++)
        for (unsigned p = 0; p < 2; p++)
            for (unsigned h = 0; h < 4; h++) {
                int w = pitches[p] / fmts[f].cpp;
                if (pitches[p] == 2048) w = 1920 / fmts[f].cpp;  // 同じ幅でピッチだけ広げる
                EGLint at[] = { EGL_WIDTH, w, EGL_HEIGHT, heights[h], EGL_LINUX_DRM_FOURCC_EXT, fmts[f].fourcc,
                                EGL_DMA_BUF_PLANE0_FD_EXT, eb.fd, EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0,
                                EGL_DMA_BUF_PLANE0_PITCH_EXT, pitches[p], EGL_NONE };
                EGLImageKHR im = mkimg(dpy, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, NULL, at);
                printf("%-9s width=%4d height=%4d pitch=%4d -> %s", fmts[f].nm, w, heights[h], pitches[p],
                       im == EGL_NO_IMAGE_KHR ? "FAIL" : "ok");
                if (im == EGL_NO_IMAGE_KHR) printf(" (0x%x)", eglGetError()); else rmimg(dpy, im);
                printf("\n");
            }
    // 並び方（modifier）をLINEAR（0）と明示して取り込めるか
    for (unsigned f = 0; f < 3; f++) {
        EGLint at[] = { EGL_WIDTH, 1920 / fmts[f].cpp, EGL_HEIGHT, 1088, EGL_LINUX_DRM_FOURCC_EXT, fmts[f].fourcc,
                        EGL_DMA_BUF_PLANE0_FD_EXT, eb.fd, EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0, EGL_DMA_BUF_PLANE0_PITCH_EXT, 1920,
                        EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT, 0, EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT, 0, EGL_NONE };
        EGLImageKHR im = mkimg(dpy, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, NULL, at);
        printf("%-9s 1920 bytes x 1088, modifier=LINEAR -> %s", fmts[f].nm, im == EGL_NO_IMAGE_KHR ? "FAIL" : "ok");
        if (im == EGL_NO_IMAGE_KHR) printf(" (0x%x)", eglGetError()); else rmimg(dpy, im);
        printf("\n");
    }
    // 比較：カメラ（uvcvideo）のバッファ（MJPEGの受け皿だが、ただのメモリとしてR8で取り込めるかを見る）
    int cam = open("/dev/video0", O_RDWR);
    struct v4l2_format cfm = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE };
    cfm.fmt.pix.width = 1280; cfm.fmt.pix.height = 720; cfm.fmt.pix.pixelformat = V4L2_PIX_FMT_MJPEG;
    ioctl(cam, VIDIOC_S_FMT, &cfm);
    struct v4l2_requestbuffers crq = { .count = 1, .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP };
    ioctl(cam, VIDIOC_REQBUFS, &crq);
    struct v4l2_exportbuffer ce = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .index = 0, .flags = O_RDWR };
    if (!ioctl(cam, VIDIOC_EXPBUF, &ce))
        for (int mod = 0; mod < 2; mod++) {
            EGLint at[] = { EGL_WIDTH, 1024, EGL_HEIGHT, 256, EGL_LINUX_DRM_FOURCC_EXT, FOURCC('R', '8', ' ', ' '),
                            EGL_DMA_BUF_PLANE0_FD_EXT, ce.fd, EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0, EGL_DMA_BUF_PLANE0_PITCH_EXT, 1024,
                            mod ? EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT : EGL_NONE, 0, EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT, 0, EGL_NONE };
            EGLImageKHR im = mkimg(dpy, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, NULL, at);
            printf("camera buffer R8 1024x256%s -> %s", mod ? " modifier=LINEAR" : "", im == EGL_NO_IMAGE_KHR ? "FAIL" : "ok");
            if (im == EGL_NO_IMAGE_KHR) printf(" (0x%x)", eglGetError()); else rmimg(dpy, im);
            printf("\n");
        }
    // NV12として1枚で取り込めるか（GPUでサンプルする用途。描画先にはできない）
    EGLint nv[] = { EGL_WIDTH, 1920, EGL_HEIGHT, 1080, EGL_LINUX_DRM_FOURCC_EXT, FOURCC('N', 'V', '1', '2'),
                    EGL_DMA_BUF_PLANE0_FD_EXT, eb.fd, EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0, EGL_DMA_BUF_PLANE0_PITCH_EXT, 1920,
                    EGL_DMA_BUF_PLANE1_FD_EXT, eb.fd, EGL_DMA_BUF_PLANE1_OFFSET_EXT, 1920 * 1088, EGL_DMA_BUF_PLANE1_PITCH_EXT, 1920,
                    EGL_NONE };
    EGLImageKHR im = mkimg(dpy, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, NULL, nv);
    printf("NV12 1920x1080 pitch=1920 -> %s\n", im == EGL_NO_IMAGE_KHR ? "FAIL" : "ok");
    return 0;
}
