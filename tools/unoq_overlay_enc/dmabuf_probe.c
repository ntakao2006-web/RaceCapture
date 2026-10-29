// UNO Q：どのdmabufをGPU（msm）が取り込めるかを調べる（焼き込みのdmabuf方式が新しい基板で失敗する件、unoq_video_check_procedure.md 5-10）
//   ① エンコーダ（venus）の入力バッファをEXPBUF ② カメラ（uvcvideo）のバッファをEXPBUF ③ dma-heapで確保したバッファ
//   それぞれを /dev/dri/renderD128 へ DRM_IOCTL_PRIME_FD_TO_HANDLE で取り込み、成否とerrnoを出す。
//   ④ dma-heapのバッファをエンコーダの入力へ V4L2_MEMORY_DMABUF で渡せるか（逆向きの共有）も見る。
// ビルド(UNO Q上): gcc -O2 -o dmabuf_probe dmabuf_probe.c
// 実行: ./dmabuf_probe [/dev/videoN（カメラ、省略可）]
#define _GNU_SOURCE
#include <drm/drm.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/dma-heap.h>
#include <linux/videodev2.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

static int xioctl(int fd, unsigned long req, void *arg) {
    int r; do { r = ioctl(fd, req, arg); } while (r < 0 && errno == EINTR); return r;
}

static int open_by_name(const char *name) {
    char path[32];
    for (int i = 0; i < 64; i++) {
        snprintf(path, sizeof path, "/dev/video%d", i);
        int f = open(path, O_RDWR | O_NONBLOCK); if (f < 0) continue;
        struct v4l2_capability cap = {0};
        if (!xioctl(f, VIDIOC_QUERYCAP, &cap) && !strcmp((char *)cap.card, name)) return f;
        close(f);
    }
    return -1;
}

static void try_import(int gpu, int dfd, const char *what) {
    off_t size = lseek(dfd, 0, SEEK_END); lseek(dfd, 0, SEEK_SET);
    struct drm_prime_handle h = { .fd = dfd };
    int r = xioctl(gpu, DRM_IOCTL_PRIME_FD_TO_HANDLE, &h);
    printf("%-40s dmabuf size=%lld -> GPU import %s", what, (long long)size, r ? "FAILED" : "ok");
    if (r) printf(" (errno=%d %s)", errno, strerror(errno));
    printf("\n");
    if (!r) { struct drm_gem_close c = { .handle = h.handle }; xioctl(gpu, DRM_IOCTL_GEM_CLOSE, &c); }
}

int main(int argc, char **argv) {
    int gpu = open("/dev/dri/renderD128", O_RDWR);
    if (gpu < 0) { perror("renderD128"); return 1; }

    // ① エンコーダの入力（OUTPUT_MPLANE、NV12 1920x1080）
    int enc = open_by_name("Qualcomm Venus video encoder");
    if (enc < 0) { printf("encoder not found\n"); return 1; }
    struct v4l2_format cf = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE };
    cf.fmt.pix_mp.width = 1920; cf.fmt.pix_mp.height = 1080; cf.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_H264;
    cf.fmt.pix_mp.num_planes = 1; cf.fmt.pix_mp.plane_fmt[0].sizeimage = 4 << 20;
    xioctl(enc, VIDIOC_S_FMT, &cf);
    struct v4l2_format of = { .type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE };
    of.fmt.pix_mp.width = 1920; of.fmt.pix_mp.height = 1080; of.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_NV12;
    of.fmt.pix_mp.num_planes = 1;
    if (xioctl(enc, VIDIOC_S_FMT, &of)) perror("enc S_FMT");
    struct v4l2_requestbuffers rq = { .count = 2, .type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE, .memory = V4L2_MEMORY_MMAP };
    if (xioctl(enc, VIDIOC_REQBUFS, &rq)) perror("enc REQBUFS");
    struct v4l2_exportbuffer eb = { .type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE, .index = 0, .plane = 0, .flags = O_RDWR };
    if (xioctl(enc, VIDIOC_EXPBUF, &eb)) printf("encoder EXPBUF failed (errno=%d %s)\n", errno, strerror(errno));
    else try_import(gpu, eb.fd, "(1) encoder input buffer (venus)");
    rq.count = 0; xioctl(enc, VIDIOC_REQBUFS, &rq);

    // ② カメラ（MJPEG 1280x720）
    if (argc > 1) {
        int cam = open(argv[1], O_RDWR);
        struct v4l2_format f = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE };
        f.fmt.pix.width = 1280; f.fmt.pix.height = 720; f.fmt.pix.pixelformat = V4L2_PIX_FMT_MJPEG;
        xioctl(cam, VIDIOC_S_FMT, &f);
        struct v4l2_requestbuffers cr = { .count = 2, .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP };
        xioctl(cam, VIDIOC_REQBUFS, &cr);
        struct v4l2_exportbuffer ce = { .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .index = 0, .flags = O_RDWR };
        if (xioctl(cam, VIDIOC_EXPBUF, &ce)) printf("camera EXPBUF failed (errno=%d %s)\n", errno, strerror(errno));
        else try_import(gpu, ce.fd, "(2) camera buffer (uvcvideo)");
        cr.count = 0; xioctl(cam, VIDIOC_REQBUFS, &cr); close(cam);
    }

    // ③ dma-heap（system）で確保したバッファ
    const char *heaps[] = { "/dev/dma_heap/system", "/dev/dma_heap/linux,cma", "/dev/dma_heap/reserved" };
    for (unsigned i = 0; i < sizeof heaps / sizeof *heaps; i++) {
        int hp = open(heaps[i], O_RDWR); if (hp < 0) { printf("%s: not present\n", heaps[i]); continue; }
        struct dma_heap_allocation_data a = { .len = 3145728, .fd_flags = O_RDWR | O_CLOEXEC };
        if (xioctl(hp, DMA_HEAP_IOCTL_ALLOC, &a)) { printf("%s alloc failed (errno=%d %s)\n", heaps[i], errno, strerror(errno)); close(hp); continue; }
        char what[64]; snprintf(what, sizeof what, "(3) dma-heap %s", heaps[i] + 14);
        try_import(gpu, a.fd, what);

        // ④ そのバッファをエンコーダの入力へDMABUFで渡せるか（REQBUFS＋QBUFまで）
        int e2 = open_by_name("Qualcomm Venus video encoder");
        xioctl(e2, VIDIOC_S_FMT, &cf); xioctl(e2, VIDIOC_S_FMT, &of);
        struct v4l2_requestbuffers dr = { .count = 1, .type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE, .memory = V4L2_MEMORY_DMABUF };
        if (xioctl(e2, VIDIOC_REQBUFS, &dr)) printf("    (4) encoder REQBUFS(DMABUF) failed (errno=%d %s)\n", errno, strerror(errno));
        else {
            struct v4l2_plane pl[1] = {{ .m.fd = a.fd, .length = 3145728, .bytesused = 3145728 }};
            struct v4l2_buffer b = { .type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE, .memory = V4L2_MEMORY_DMABUF, .index = 0, .length = 1, .m.planes = pl };
            int r = xioctl(e2, VIDIOC_QBUF, &b);
            printf("    (4) encoder REQBUFS(DMABUF) ok, QBUF with this buffer %s", r ? "FAILED" : "ok");
            if (r) printf(" (errno=%d %s)", errno, strerror(errno));
            printf("\n");
        }
        close(e2); close(a.fd); close(hp);
    }
    return 0;
}
