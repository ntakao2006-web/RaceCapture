// 音（カメラ内蔵のマイク等）を録ってMP2（MPEG-1 Layer II）にし、録画のTSへ混ぜるまでためておく
//   arecord（alsa-utils）の生PCM（S16_LE・48kHz・モノラル）をパイプで読み、twolame で固める（既定128kbps＝映像10Mbpsの約1.3%）。
//   1フレーム（1152サンプル＝24ms）ごとに、その頭の CLOCK_MONOTONIC の時刻を付ける。映像のカメラの時刻と同じ時計なので、そのまま並べられる
//   時刻の付け方：「読み終えた時刻 − それまでに読んだサンプル数÷48000」を録り始めの時刻の見積もりとし、一番早いもの（遅れが一番少ないもの）を使う。
//   最初の5秒はそれまでの一番早いもの、その後は5秒ごとの一番早いものへ半分ずつ寄せる（マイクの時計と本体の時計のずれ、数十ppm＝2時間で約0.3秒を追う）。
//   見積もりが動いても、各フレームの時刻は前のフレーム＋24msから±1%しか動かさない（音のPTSが重なったり空いたりしない。0.5秒より大きく飛んだら合わせ直す）。
//   録り始め（やり直しも）の1秒は、見積もりが落ち着くまで捨てる
//   録れなくなったら（マイクが抜けた・arecordが落ちた等）待ってやり直す。どの場合も映像の録画は止めない
//   twolame は実行時に libtwolame.so.0 を読む（本体にはヘッダーが無く、実行用の libtwolame0 だけ入れればよい。無ければ音なしで録る）
//   使う前に quit（止めるとき1）と now()（CLOCK_MONOTONICの秒）が要る。組み立て：-ldl（glibc 2.34以降は無くてもよい）
#pragma once
#include <errno.h>
#include <math.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/wait.h>
#include <dlfcn.h>
#include <unistd.h>

// twolame（0.3・0.4）の使う所だけ。twolame.h と同じ形・同じ値（TWOLAME_MONO＝3）
typedef struct twolame_options_struct twolame_options;
static struct {
    twolame_options *(*init)(void);
    int (*set_num_channels)(twolame_options *, int), (*set_mode)(twolame_options *, int), (*set_in_samplerate)(twolame_options *, int),
        (*set_out_samplerate)(twolame_options *, int), (*set_bitrate)(twolame_options *, int), (*init_params)(twolame_options *),
        (*encode_buffer_interleaved)(twolame_options *, const short *, int, unsigned char *, int);
    void (*close)(twolame_options **);
} twl;
#define AC_TWOLAME_MONO 3
static int tl_load(void) {
    void *h = dlopen("libtwolame.so.0", RTLD_NOW);
    if (!h) return 0;
#define TL(f) (*(void **)&twl.f = dlsym(h, "twolame_" #f)) != NULL
    return TL(init) && TL(set_num_channels) && TL(set_mode) && TL(set_in_samplerate) && TL(set_out_samplerate) && TL(set_bitrate) &&
           TL(init_params) && TL(encode_buffer_interleaved) && TL(close);
#undef TL
}

#define AC_RATE 48000
#define AC_SPF 1152   // MP2の1フレームのサンプル数
#define AC_Q 256      // ためておけるフレーム（約6秒）。あふれたら古いものから捨てる
#define AC_GROUP 4    // これだけたまったら1つのPESにまとめて書く（約0.1秒。小分けにするとTSの詰め物が増える）
struct ac_frame { double t; int n; uint8_t b[1152]; };  // MP2のフレームは48kHz・384kbpsでも1152バイト
static struct ac_frame ac_q[AC_Q];
static int ac_head, ac_count;
static pthread_mutex_t ac_mu = PTHREAD_MUTEX_INITIALIZER;
static int ac_kbps = 128;
static char ac_cmd[600];
static long ac_frames, ac_dropped, ac_restarts, ac_written;

// MP2にする前の処理（手順書5-23）。走行中はエンジン・路面・風の低い唸り（20〜100Hz）が音の力の9割以上を占め、
// そのまま大きく録ると割れる（11/6の章で7.7%のサンプルが上限に張りついた）。
//   1. 低音カット：2次のバターワース（OVERLAY_AUDIO_HPF Hz、既定100。0で無し。30Hzは約−21dB、200Hzはほぼそのまま）
//   2. 音量：OVERLAY_AUDIO_GAIN_DB（既定0。割れはカメラの中で起きるので、下げるならまずマイクの音量＝run-video.shのmic_volume）
//   3. リミッター：上限の0.7（−3dB）を超えそうな所だけ瞬時に下げ、0.3秒かけて戻す（OVERLAY_AUDIO_LIMIT=0で無し）。
//      MP2にしたあとで上限を超えて割れないようにする。カメラの中で割れた音は元に戻せない
static double ac_hpf_hz = 100, ac_gain_db = 0;
static int ac_limit = 1;
struct ac_dsp { double b0, b1, b2, a1, a2, x1, x2, y1, y2, env, rel, g; int hpf; };
static void ac_dsp_init(struct ac_dsp *d) {
    memset(d, 0, sizeof *d);
    d->g = pow(10, ac_gain_db / 20);
    d->rel = exp(-1.0 / (0.3 * AC_RATE));
    if (ac_hpf_hz > 0 && ac_hpf_hz < AC_RATE / 4) {  // RBJの式、Q=1/√2
        const double w = 2 * M_PI * ac_hpf_hz / AC_RATE, c = cos(w), al = sin(w) / (2 * M_SQRT1_2), a0 = 1 + al;
        d->b0 = (1 + c) / 2 / a0; d->b1 = -(1 + c) / a0; d->b2 = d->b0; d->a1 = -2 * c / a0; d->a2 = (1 - al) / a0; d->hpf = 1;
    }
}
static void ac_dsp_run(struct ac_dsp *d, short *p, int n) {
    const double T = 0.7;
    for (int i = 0; i < n; i++) {
        double x = p[i] / 32768.0, y = x;
        if (d->hpf) { y = d->b0 * x + d->b1 * d->x1 + d->b2 * d->x2 - d->a1 * d->y1 - d->a2 * d->y2; d->x2 = d->x1; d->x1 = x; d->y2 = d->y1; d->y1 = y; }
        y *= d->g;
        if (ac_limit) { const double a = fabs(y); d->env = a > d->env ? a : d->env * d->rel; if (d->env > T) y *= T / d->env; }
        y = y > 0.999 ? 0.999 : y < -0.999 ? -0.999 : y;
        p[i] = (short)lrint(y * 32767);
    }
}

static int ac_on;
static volatile pid_t ac_pid;
static pthread_t ac_th;

// MP2のフレームの長さ（頭が正しくなければ0）。MPEG-1 Layer IIだけ
static int mp2_len(const uint8_t *h) {
    static const int br[16] = { 0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0 };
    static const int sr[4] = { 44100, 48000, 32000, 0 };
    if (h[0] != 0xff || (h[1] & 0xfe) != 0xfc) return 0;  // 同期・MPEG-1・Layer II
    const int b = br[h[2] >> 4], s = sr[h[2] >> 2 & 3];
    return b && s ? 144 * b * 1000 / s + (h[2] >> 1 & 1) : 0;
}

static void ac_push(double t, const uint8_t *b, int n) {
    if (n <= 0 || n > (int)sizeof ac_q[0].b) return;
    pthread_mutex_lock(&ac_mu);
    if (ac_count == AC_Q) { ac_head = (ac_head + 1) % AC_Q; ac_count--; ac_dropped++; }
    struct ac_frame *f = &ac_q[(ac_head + ac_count) % AC_Q];
    f->t = t; f->n = n; memcpy(f->b, b, n); ac_count++; ac_frames++;
    pthread_mutex_unlock(&ac_mu);
}

// たまった音を書く。t0：映像の最初の枚のカメラの時刻（これより前の音は捨てる）。force：AC_GROUPに足りなくても全部書く。
// write(es, n, t)：MP2を続けたものと、その頭の時刻（CLOCK_MONOTONIC）。映像を書くのと同じスレッドから呼ぶ（ファイルの切り替えと取り合わない）
static void ac_drain(double t0, int force, void (*write)(const uint8_t *, size_t, double)) {
    static uint8_t buf[AC_GROUP * 2 * sizeof ac_q[0].b];
    for (;;) {
        size_t n = 0; double t = 0; int k = 0;
        pthread_mutex_lock(&ac_mu);
        while (ac_count && ac_q[ac_head].t < t0) { ac_head = (ac_head + 1) % AC_Q; ac_count--; }
        if (ac_count >= AC_GROUP || (force && ac_count)) {
            t = ac_q[ac_head].t;
            while (ac_count && k < 2 * AC_GROUP) {
                const struct ac_frame *f = &ac_q[ac_head];
                if (k && fabs(f->t - (t + k * (double)AC_SPF / AC_RATE)) > 0.002) break;  // 時刻が飛んだ所（録り直し）で分ける
                memcpy(buf + n, f->b, f->n); n += f->n; k++;
                ac_head = (ac_head + 1) % AC_Q; ac_count--;
            }
        }
        pthread_mutex_unlock(&ac_mu);
        if (!n) return;
        write(buf, n, t); ac_written += k;
    }
}

static int ac_spawn(void) {
    int p[2]; if (pipe(p)) return -1;
    pid_t pid = fork();
    if (pid < 0) { close(p[0]); close(p[1]); return -1; }
    if (!pid) {  // 子：録画プログラムが落ちたら一緒に終わる。カメラ・エンコーダ等のfdは持っていかない
        prctl(PR_SET_PDEATHSIG, SIGKILL);
        setpgid(0, 0);
        dup2(p[1], 1);
        for (int fd = 3; fd < 1024; fd++) close(fd);
        execl("/bin/sh", "sh", "-c", ac_cmd, (char *)NULL);
        _exit(127);
    }
    close(p[1]); ac_pid = pid;
    return p[0];
}

static void ac_kill(void) {
    pid_t pid = ac_pid;
    if (pid > 0) { kill(-pid, SIGKILL); kill(pid, SIGKILL); }
}

static void *ac_loop(void *arg) {
    (void)arg;
    static short pcm[AC_SPF];
    static uint8_t mp2[16384];
    int wait_s = 2, said = 0;
    while (!quit) {
        twolame_options *tw = twl.init();
        if (tw) {
            twl.set_num_channels(tw, 1); twl.set_mode(tw, AC_TWOLAME_MONO);
            twl.set_in_samplerate(tw, AC_RATE); twl.set_out_samplerate(tw, AC_RATE);
            twl.set_bitrate(tw, ac_kbps);
        }
        const int fd = !tw || twl.init_params(tw) ? -1 : ac_spawn();
        struct ac_dsp dsp; ac_dsp_init(&dsp);
        double start = NAN, t_first = 0, blk = INFINITY, last = NAN; long long got = 0, fo = 0; size_t have = 0; int nb = 0;
        const double D = (double)AC_SPF / AC_RATE;
        while (fd >= 0 && !quit) {
            ssize_t r = read(fd, (char *)pcm + have, sizeof pcm - have);
            if (r < 0 && errno == EINTR) continue;
            if (r <= 0) break;
            have += r;
            if (have < sizeof pcm) continue;
            have = 0;
            const double t = now(); got += AC_SPF;
            const double est = t - got / (double)AC_RATE;  // 録り始めの時刻の見積もり（実際より遅れる側にだけぶれる）
            if (got <= 5 * AC_RATE) { if (isnan(start) || est < start) start = est; }
            else if (blk = fmin(blk, est), ++nb >= 5 * AC_RATE / AC_SPF) { start += (blk - start) * 0.5; blk = INFINITY; nb = 0; }
            if (got == AC_SPF) { t_first = t; if (!said++) { printf("audio: first data (%s)\n", ac_cmd); fflush(stdout); } }
            ac_dsp_run(&dsp, pcm, AC_SPF);
            const int n = twl.encode_buffer_interleaved(tw, pcm, AC_SPF, mp2, sizeof mp2);
            for (int o = 0; n > 0 && o + 4 <= n;) {
                const int L = mp2_len(mp2 + o);
                if (!L || o + L > n) break;
                double ft = start + fo * D;
                if (got >= AC_RATE) {  // 始めの1秒は捨てる（録り始めの遅れの見積もりが落ち着くまで）
                    if (!isnan(last) && fabs(ft - (last + D)) < 0.5) ft = fmin(fmax(ft, last + D * 0.99), last + D * 1.01);
                    ac_push(ft, mp2 + o, L); last = ft;
                }
                fo++; o += L;
            }
            if (t - t_first > 60) wait_s = 2;  // 1分録れたら、次に落ちたときはまた2秒で
        }
        if (fd >= 0) close(fd);
        ac_kill();
        if (ac_pid > 0) { waitpid(ac_pid, NULL, 0); ac_pid = 0; }
        if (tw) twl.close(&tw);
        if (quit) break;
        ac_restarts++;
        if (ac_restarts <= 5 || ac_restarts % 50 == 0) {
            fprintf(stderr, "audio: no data from \"%s\" (%ld), retry in %d s\n", ac_cmd, ac_restarts, wait_s); fflush(stderr);
        }
        for (int i = 0; i < wait_s * 10 && !quit; i++) usleep(100000);
        if (wait_s < 30) wait_s *= 2;  // マイクが無いときに何度もやり直さない
    }
    return NULL;
}

// 音を録り始める。OVERLAY_AUDIO_CMD（S16_LE・48kHz・モノラルの生PCMを標準出力へ出すコマンド。試験用）か、
// OVERLAY_AUDIO（ALSAの名前。例 plughw:CARD=Camera,DEV=0。空か off なら録らない）。OVERLAY_AUDIO_KBPS で速さ（既定128）。
// 録るなら1（このときPMTに音を載せる）。マイクが本当に音を出すかはここでは待たない
static int ac_start(void) {
    const char *cmd = getenv("OVERLAY_AUDIO_CMD"), *dev = getenv("OVERLAY_AUDIO");
    if (getenv("OVERLAY_AUDIO_KBPS")) ac_kbps = atoi(getenv("OVERLAY_AUDIO_KBPS"));
    const char *e;
    if ((e = getenv("OVERLAY_AUDIO_HPF")) && *e) ac_hpf_hz = atof(e);
    if ((e = getenv("OVERLAY_AUDIO_GAIN_DB")) && *e) ac_gain_db = atof(e);
    if ((e = getenv("OVERLAY_AUDIO_LIMIT")) && *e) ac_limit = atoi(e) != 0;
    if (cmd && *cmd) snprintf(ac_cmd, sizeof ac_cmd, "%s", cmd);
    else if (dev && *dev && strcmp(dev, "off") && !strchr(dev, '\'')) {
        // OVERLAY_AUDIO_PRE：arecord の前に毎回動かすコマンド（マイクの音量を決める mic-volume.sh。カメラを挿し直すと音量が元に戻るため）。
        // 標準出力は音のパイプなので、出力は標準エラー（journal）へ回す
        const char *pre = getenv("OVERLAY_AUDIO_PRE");
        snprintf(ac_cmd, sizeof ac_cmd, "%s%s%sexec arecord -q -D '%s' -f S16_LE -r %d -c 1 -t raw --buffer-time=500000 --period-time=50000",
                 pre && *pre ? "{ " : "", pre && *pre ? pre : "", pre && *pre ? "; } 1>&2; " : "", dev, AC_RATE);
    } else return 0;
    if (!tl_load()) {
        fprintf(stderr, "audio: libtwolame.so.0 not found, recording without audio (apt-get install libtwolame0)\n"); fflush(stderr);
        return 0;
    }
    if (pthread_create(&ac_th, NULL, ac_loop, NULL)) return 0;
    ac_on = 1;
    printf("audio: MP2 %d kbps from %s\n", ac_kbps, ac_cmd);
    printf("audio: highpass %g Hz, gain %g dB, limiter %s\n", ac_hpf_hz, ac_gain_db, ac_limit ? "on" : "off"); fflush(stdout);
    return 1;
}

static void ac_stop(void) {  // quit を1にしてから呼ぶ
    if (!ac_on) return;
    ac_kill();
    pthread_join(ac_th, NULL);
    ac_on = 0;
}
