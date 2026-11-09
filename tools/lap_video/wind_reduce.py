"""車載動画の音から風切りを下げる（2026-11-09、SUGO決勝のベストラップでユーザーが「8番」に決めた設定）

風切りはエンジンの音と同じ帯域に重なっていて、エンジンの倍音もその周波数で風切りより約3dBしか大きくない。
ふつうの雑音取り（highpass・afftdn）や「音程・瞬間・雑音で分ける」だけでは区別できなかった。
そこで走行記録の回転数を使い、エンジンの倍音（回転数の整数倍の周波数）は残し、その間を下げる。

  1. 記録と音の時刻のずれを、2次の倍音がいちばん立つずれで合わせる（find_offset）
  2. 回転数を音で±4%微調整する（refine_rpm）
  3. 倍音の間を −15dB、3kHzより上は −5dB（こもらないように軽く）、倍音の幅は次数σ0.09（reduce）
     ・倍音から外れていても風切りより14dB以上大きい音程の音（スキール等）は残す
     ・回転が急に動く所（シフト・ブリッピング、2500rpm/秒以上の前後0.3秒）は、回転数を音で細かく追い、
       倍音の幅をσ0.14に広げ、瞬間の音（ガコッ）を守る。元の音のまま通すと風切りが「ゴワっ」と戻る
  4. その所だけ、処理後/元の音量比を前後1.5秒の比にそろえる（下げるだけ、level_shifts）

却下したもの（手順書 unoq_video_check_procedure.md 5-25）：倍音だけを残す（−24dB）とこもって不自然で、
シフトの音・スキールも消える。1周（約2分）で数分かかり、メモリーを1〜2GB使う。長い動画は1周ずつ。
"""
import numpy as np
from scipy.ndimage import median_filter, uniform_filter1d
from scipy.signal import butter, sosfiltfilt

# 8番の設定
BETWEEN_DB = -15.0     # 倍音の間（2kHzまで）
HIGH_DB = -5.0         # 3kHzより上（2〜3kHzはなめらかにつなぐ）
SIGMA = 0.09           # 倍音の幅（次数のσ）
SHIFT_SIGMA = 0.14     # 回転が急に動く所の倍音の幅
SHIFT_RATE = 2500.0    # 回転が急に動く所とみなす速さ（rpm/秒、0.2秒の差で見る）
SHIFT_PAD = 0.3        # その前後に広げる秒
TONAL_FROM = 12.0      # 風切りの何倍（パワー）から音程の音を残し始めるか（2倍の値で全部残す）
TRANS_FROM = 6.0       # 同じく瞬間の音（回転が急に動く所だけ）


def _stft(x, N, H):
    win = np.sqrt(np.hanning(N + 1)[:-1])
    pad = np.concatenate([np.zeros(N), x, np.zeros(N)])
    nf = (len(pad) - N) // H + 1
    spec = np.stack([np.fft.rfft(pad[i * H:i * H + N] * win) for i in range(nf)])
    return spec, win, pad, nf


def _istft(spec, win, N, H, n_pad, n_out):
    out = np.zeros(n_pad)
    for i in range(len(spec)):
        out[i * H:i * H + N] += np.fft.irfft(spec[i], N) * win
    return out[N:N + n_out] / (np.sum(win ** 2) / H)


def _shift_mask(t, rpm_at, sr_frames):
    """回転が急に動く所（0〜1、なめらか）。rpm_at：その時刻の記録の回転数"""
    st = max(1, int(round(0.2 * sr_frames)))
    dr = np.abs(np.r_[rpm_at[st:] - rpm_at[:-st], np.zeros(st)]) / 0.2
    pad = int(round(SHIFT_PAD * sr_frames))
    sh = np.convolve((dr > SHIFT_RATE).astype(float), np.ones(2 * pad + 1), 'same') > 0
    return uniform_filter1d(sh.astype(float), max(1, int(round(0.2 * sr_frames))))


def find_offset(x, sr, rpm_t, rpm, search=1.0, step=0.05):
    """記録の時刻に足すずれ（秒）。2次の倍音がまわりの次数よりいちばん立つずれ"""
    N, H = 8192, 1024
    win = np.hanning(N)
    fr = np.lib.stride_tricks.sliding_window_view(x, N)[::H] * win
    P = 20 * np.log10(np.abs(np.fft.rfft(fr, axis=1)) + 1e-9)
    f = np.fft.rfftfreq(N, 1 / sr)
    tc = (np.arange(len(P)) * H + N / 2) / sr
    orders = np.arange(0.25, 12.01, 0.05)
    best = (-1e9, 0.0)
    for off in np.arange(-search, search + 1e-9, step):
        f1 = np.interp(tc + off, rpm_t, rpm) / 60
        prof = np.array([np.interp(orders * a, f, row) for a, row in zip(f1, P)]).mean(0)
        score = np.interp(2.0, orders, prof) - np.median(prof)
        if score > best[0]:
            best = (score, float(off))
    return round(best[1], 2), round(best[0], 1)


def refine_rpm(x, sr, rpm_t, rpm, offset):
    """回転数を音で±4%微調整（1〜8次の倍音の強さの和がいちばん大きい倍率）。返り値：(時刻, 記録, 微調整後)"""
    N, H = 4096, 1024
    spec, _, _, nf = _stft(x, N, H)
    f = np.fft.rfftfreq(N, 1 / sr)
    tc = (np.arange(nf) * H + N / 2 - N) / sr
    rl = np.interp(tc + offset, rpm_t, rpm)
    L = np.log(np.abs(spec) + 1e-9)
    scales = np.linspace(0.96, 1.04, 41)
    rr = np.empty(nf)
    for i in range(nf):
        fq = rl[i] / 60 * scales[:, None] * np.arange(1, 9)[None, :]
        rr[i] = rl[i] * scales[np.argmax(np.interp(fq, f, L[i]).sum(1))]
    return tc, rl, median_filter(rr, 5)


def reduce(x, sr, rpm_t, rpm, offset, refined):
    """風切りを下げた音（ピークを0.8にそろえる前の値）。refined：refine_rpm の返り値"""
    N, H = 4096, 512
    spec, win, pad, nf = _stft(x, N, H)
    P = np.abs(spec) ** 2
    f = np.fft.rfftfreq(N, 1 / sr)
    tc = (np.arange(nf) * H + N / 2 - N) / sr
    rl = np.interp(tc + offset, rpm_t, rpm)
    # 回転が急に動く所だけ、記録の±10%を音で細かく追う（30msの中央値）
    Ls = uniform_filter1d(np.log(P + 1e-12), 3, axis=1)
    scales = np.linspace(0.90, 1.10, 81)
    fine = np.empty(nf)
    for i in range(nf):
        fq = rl[i] / 60 * scales[:, None] * np.arange(1, 9)[None, :]
        fine[i] = rl[i] * scales[np.argmax(np.interp(fq, f, Ls[i]).sum(1))]
    fine = median_filter(fine, 3)
    sh = _shift_mask(tc, rl, sr / H)
    t_r, _, rr = refined
    r_use = np.interp(tc, t_r, rr) * (1 - sh) + fine * sh
    o = f[None, :] / (r_use[:, None] / 60)
    on = np.round(o)
    d = np.abs(o - on)
    fb = np.clip((f - 2000) / 1000, 0, 1)
    floor = 10 ** ((BETWEEN_DB * (1 - fb) + HIGH_DB * fb) / 20)[None, :]
    low = f < 50
    # ふだん
    G = floor + (1 - floor) * np.exp(-0.5 * (d / SIGMA) ** 2) * (on >= 1)
    G[:, low] = 10 ** (BETWEEN_DB / 20)
    Hm = median_filter(P, size=(9, 1))
    fl_est = np.exp(median_filter(np.log(P + 1e-12), size=(61, 9)))
    tonal = np.clip((Hm / fl_est - TONAL_FROM) / TONAL_FROM, 0, 1)
    G = np.maximum(G, tonal)
    # 回転が急に動く所
    Gs = floor + (1 - floor) * np.exp(-0.5 * (d / SHIFT_SIGMA) ** 2) * (on >= 1)
    Gs[:, low] = 10 ** (BETWEEN_DB / 20)
    Pm = median_filter(P, size=(1, 17))
    trans = np.clip((Pm / fl_est - TRANS_FROM) / TRANS_FROM, 0, 1)
    Gs = np.maximum(np.maximum(Gs, tonal), trans)
    G = G * (1 - sh[:, None]) + Gs * sh[:, None]
    G = uniform_filter1d(uniform_filter1d(G, 5, axis=0), 3, axis=1)   # ちらつき（ミュージカルノイズ）を抑える
    return _istft(spec * G, win, N, H, len(pad), len(x))


def level_shifts(x0, y, sr, rpm_t, rpm, offset):
    """回転が急に動く所だけ、処理後/元の音量比（150〜2500Hz）を前後1.5秒の比にそろえる（下げるだけ）"""
    n = min(len(x0), len(y))
    x0, y = x0[:n], y[:n]
    sos = butter(4, [150, 2500], 'bandpass', fs=sr, output='sos')
    hop = int(0.01 * sr)

    def env(s):
        b = sosfiltfilt(sos, s) ** 2
        m = len(b) // hop
        return uniform_filter1d(b[:m * hop].reshape(m, hop).mean(1), 5)
    e0, e1 = env(x0), env(y)
    t = (np.arange(len(e0)) + 0.5) * hop / sr
    ratio = e1 / (e0 + 1e-12)
    sh = _shift_mask(t, np.interp(t + offset, rpm_t, rpm), 100) > 0
    g = np.ones(len(t))
    W = 150
    for i in np.where(sh)[0]:
        a, b = max(0, i - W), min(len(t), i + W)
        ref = ratio[a:b][~sh[a:b]]
        if len(ref) > 20:
            g[i] = min(1.0, np.sqrt(np.median(ref) / ratio[i]))
    g = uniform_filter1d(uniform_filter1d(g, 9), 9)
    return y * np.interp(np.arange(n) / sr, t, g), float(g.min())


def process(x, sr, rpm_t, rpm):
    """一式。x：元の音（−1〜1、モノラル）、rpm_t：xの頭からの秒、rpm：記録の回転数。返り値：(音, 情報)"""
    offset, prom = find_offset(x, sr, rpm_t, rpm)
    refined = refine_rpm(x, sr, rpm_t, rpm, offset)
    y = reduce(x, sr, rpm_t, rpm, offset, refined)
    y, gmin = level_shifts(x, y, sr, rpm_t, rpm, offset)
    y = y / max(1e-9, np.abs(y).max()) * 0.8
    return y, {'offset_s': offset, 'order2_prominence_db': prom, 'shift_min_gain_db': round(20 * np.log10(gmin), 1)}
