// Linux側：spidev0.0 から32bitの連番を流し続ける（試験ファーム unoq_spi_sd_test の受け側で欠落・化けを検査する）
// ビルド: gcc -O2 -o spi_stream spi_stream.c
// 実行:   ./spi_stream <速度Hz> <送信MB> [1メッセージのバイト=65536] [目標レートKB/s=0(全速)]
//   spidev は bufsiz を広げて読み込み直しておくこと（unoq_video_to_shield_sd_study.md 5-2章）
#include <fcntl.h>
#include <linux/spi/spidev.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s hz MB [chunk] [rateKBps]\n", argv[0]); return 1; }
    uint32_t hz = strtoul(argv[1], NULL, 10);
    double mb = atof(argv[2]);
    int chunk = argc > 3 ? atoi(argv[3]) : 65536;
    double rate = argc > 4 ? atof(argv[4]) * 1000 : 0;
    int fd = open("/dev/spidev0.0", O_RDWR);
    if (fd < 0) { perror("open"); return 1; }
    uint8_t mode = SPI_MODE_0, bits = 8;
    ioctl(fd, SPI_IOC_WR_MODE, &mode); ioctl(fd, SPI_IOC_WR_BITS_PER_WORD, &bits);
    ioctl(fd, SPI_IOC_WR_MAX_SPEED_HZ, &hz);
    uint32_t *buf = malloc(chunk), ctr = 0;
    long n = (long)(mb * 1024 * 1024 / chunk);
    double t0 = now();
    for (long i = 0; i < n; i++) {
        for (int k = 0; k < chunk / 4; k++) buf[k] = ctr++;
        struct spi_ioc_transfer tr = { .tx_buf = (uintptr_t)buf, .len = chunk, .speed_hz = hz, .bits_per_word = 8 };
        if (ioctl(fd, SPI_IOC_MESSAGE(1), &tr) < 0) { perror("xfer"); return 1; }
        if (rate > 0) { double due = t0 + (double)(i + 1) * chunk / rate, r = due - now(); if (r > 0) usleep(r * 1e6); }
    }
    double el = now() - t0;
    printf("sent %ld x %d B = %.1f MB in %.2fs = %.2f MB/s, last_word=%u\n", n, chunk, n * (double)chunk / 1e6, el,
           n * (double)chunk / el / 1e6, ctr - 1);
    return 0;
}
