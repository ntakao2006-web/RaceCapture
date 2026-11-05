// MPEG-TS の書き出し（overlay_rec.c と、PCで試す audio_mux_test.c で同じものを使う）
//   番組1つ。映像（H.264、PID 0x100、PCRもここ）と、ts_audio のときは音（MPEG-1 Layer II、PID 0x101）
//   書き出す先は out（188バイトのパケットだけを書く。回収アプリ video_collect.py の ts_pts_range もこれを前提に読む）
#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define PID_PMT 0x1000
#define PID_VID 0x0100
#define PID_AUD 0x0101
static FILE *out;
static size_t bytes;
static int ts_audio;  // PMTに音を載せるか（録り始める前に決める）
static uint8_t cc_pat, cc_pmt, cc_vid, cc_aud;

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

// PAT・PMT（番組1つ。H.264が1本と、ts_audio なら MPEG-1 Audio が1本）。キーフレームの前に毎回出し、途中から読んでも分かるようにする
static void ts_tables(void) {
    uint8_t pat[16] = { 0x00, 0xb0, 13, 0x00, 0x01, 0xc1, 0x00, 0x00, 0x00, 0x01, 0xe0 | PID_PMT >> 8, PID_PMT & 0xff };
    uint8_t pmt[26] = { 0x02, 0xb0, 0, 0x00, 0x01, 0xc1, 0x00, 0x00, 0xe0 | PID_VID >> 8, PID_VID & 0xff, 0xf0, 0x00,
                        0x1b, 0xe0 | PID_VID >> 8, PID_VID & 0xff, 0xf0, 0x00,
                        0x03, 0xe0 | PID_AUD >> 8, PID_AUD & 0xff, 0xf0, 0x00 };
    const int n = ts_audio ? 26 : 21;  // 音が無いときは最後の5バイトの所へCRCが入る（前の版と同じ中身）
    pmt[2] = n - 3;
    ts_section(0, &cc_pat, pat, sizeof pat);
    ts_section(PID_PMT, &cc_pmt, pmt, n);
}

static void ts_put_pts(uint8_t *b, uint64_t pts) {  // PESの頭のPTS（5バイト、PTSだけの形）
    b[0] = 0x21 | (pts >> 29 & 0x0e); b[1] = pts >> 22 & 0xff; b[2] = 0x01 | (pts >> 14 & 0xfe); b[3] = pts >> 7 & 0xff; b[4] = 0x01 | (pts << 1 & 0xfe);
}

// PES（頭 hd ＋中身 es）をTSのパケットへ。pcr が0以上なら1枚目のパケットにPCR（と key ならキーフレームの印）
static void ts_pes(int pid, uint8_t *cc, const uint8_t *hd, size_t hn, const uint8_t *es, size_t n, int64_t pcr, int key) {
    size_t total = hn + n, off = 0;
    for (int first = 1; off < total; first = 0) {
        uint8_t pk[188], af[184]; size_t L = 0; int has_af = 0;
        if (first && pcr >= 0) {
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
        pk[0] = 0x47; pk[1] = (first ? 0x40 : 0) | pid >> 8; pk[2] = pid & 0xff;
        pk[3] = (has_af ? 0x30 : 0x10) | ((*cc)++ & 0x0f);
        size_t p = 4;
        if (has_af) { pk[p++] = L; memcpy(pk + p, af, L); p += L; }
        size_t a = off, m = cap;
        if (a < hn) { size_t c = hn - a < m ? hn - a : m; memcpy(pk + p, hd + a, c); p += c; a += c; m -= c; }
        if (m) memcpy(pk + p, es + (a - hn), m);
        put(pk, sizeof pk); off += cap;
    }
}

// 映像の1枚（アクセスユニット）。PTSのみ（Bフレームは無い）。pts・pcrは90kHz
static void ts_frame(const uint8_t *es, size_t n, uint64_t pts, uint64_t pcr, int key) {
    uint8_t hd[20] = { 0, 0, 1, 0xe0, 0, 0, 0x80, 0x80, 5, 0, 0, 0, 0, 0,
                       0, 0, 0, 1, 0x09, 0xf0 };  // PESの頭＋AUD（区切りのNAL。TSのH.264では付ける決まり）
    ts_put_pts(hd + 9, pts);
    ts_pes(PID_VID, &cc_vid, hd, sizeof hd, es, n, (int64_t)pcr, key);
}

// 音（MP2のフレームをいくつか続けたもの）。ptsは最初のフレームの頭（90kHz）
static void ts_audio_pes(const uint8_t *es, size_t n, uint64_t pts) {
    const size_t len = 8 + n;  // PES_packet_length：この後ろのバイト数（音では0にしない）
    uint8_t hd[14] = { 0, 0, 1, 0xc0, len >> 8 & 0xff, len & 0xff, 0x80, 0x80, 5 };
    ts_put_pts(hd + 9, pts);
    ts_pes(PID_AUD, &cc_aud, hd, sizeof hd, es, n, -1, 0);
}
