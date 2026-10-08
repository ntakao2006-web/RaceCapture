// UNO Q 内部SPI（Linux spidev0.0 → STM32 SPI3）の送信側だけの速度試験
//   STM32側が受け取っていなくても、Linux側がどれだけの速度で送り出せるかを測る（unoq_video_to_shield_sd_study.md 5章）
// ビルド(UNO Q上): gcc -O2 -o spi_tx_test spi_tx_test.c
// 実行: ./spi_tx_test <速度Hz> [送信MB=8] [1回の転送バイト=4096] [転送ごとに速度指定=1|0] [ビット/語=8] [1メッセージの転送数=1]
//   1回の転送はspidevのbufsiz（既定4096）以下にする
#include <fcntl.h>
#include <linux/spi/spidev.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s hz [MB] [chunk]\n", argv[0]); return 1; }
    uint32_t hz = strtoul(argv[1], NULL, 10);
    double mb = argc > 2 ? atof(argv[2]) : 8;
    int chunk = argc > 3 ? atoi(argv[3]) : 4096;
    int per_xfer = argc > 4 ? atoi(argv[4]) : 1;  // 0 = 転送ごとには速度を指定せず、デバイスの既定値（WR_MAX_SPEED_HZ）に任せる
    int bpw = argc > 5 ? atoi(argv[5]) : 8;
    int nx = argc > 6 ? atoi(argv[6]) : 1;  // 1メッセージに入れる転送数（合計がbufsiz以下になるよう chunk を割る）
    if (nx < 1 || nx > 8) nx = 1;
    int fd = open("/dev/spidev0.0", O_RDWR);
    if (fd < 0) { perror("open"); return 1; }
    uint8_t mode = SPI_MODE_0, bits = bpw;
    ioctl(fd, SPI_IOC_WR_MODE, &mode); ioctl(fd, SPI_IOC_WR_BITS_PER_WORD, &bits);
    if (ioctl(fd, SPI_IOC_WR_MAX_SPEED_HZ, &hz)) { perror("speed"); return 1; }
    uint8_t *buf = malloc(chunk);
    for (int i = 0; i < chunk; i++) buf[i] = i * 37 + 11;
    struct spi_ioc_transfer tr[8];
    memset(tr, 0, sizeof tr);
    for (int k = 0; k < nx; k++) {
        tr[k].tx_buf = (uintptr_t)(buf + k * (chunk / nx)); tr[k].len = chunk / nx;
        tr[k].speed_hz = per_xfer ? hz : 0; tr[k].bits_per_word = bpw;
    }
    long n = (long)(mb * 1024 * 1024 / chunk);
    struct rusage r0, r1; getrusage(RUSAGE_SELF, &r0);
    double t0 = now();
    for (long i = 0; i < n; i++)
        if (ioctl(fd, SPI_IOC_MESSAGE(nx), tr) < 0) { perror("xfer"); return 1; }
    double el = now() - t0;
    getrusage(RUSAGE_SELF, &r1);
    double cpu = (r1.ru_utime.tv_sec - r0.ru_utime.tv_sec) + (r1.ru_utime.tv_usec - r0.ru_utime.tv_usec) * 1e-6
               + (r1.ru_stime.tv_sec - r0.ru_stime.tv_sec) + (r1.ru_stime.tv_usec - r0.ru_stime.tv_usec) * 1e-6;
    double bytes = (double)n * chunk;
    printf("bpw=%2d nx=%d per_xfer=%d set=%5.1fMHz chunk=%5d  %6.2f MB/s = %5.1f Mbps  (line-rate %4.0f%%)  CPU %3.0f%%\n",
           bpw, nx, per_xfer, hz / 1e6, chunk, bytes / el / 1e6, bytes * 8 / el / 1e6, bytes * 8 / el / hz * 100, cpu / el * 100);
    return 0;
}
