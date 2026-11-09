"""走行映像から1周だけを切り出し、風切りを下げた公開用のMP4を作る（2026-11-09、ユーザー依頼）

  python tools/lap_video/lap_video.py laps 20261108              その日の周の一覧（タイム・時刻・映像の有無）
  python tools/lap_video/lap_video.py clip 20261108 --best       その日のベストラップ
  python tools/lap_video/lap_video.py clip 20261108 --lap 31     周を指定（周の番号はロガーの通し）

読むもの（どちらもPCに回収済みであること。位置を含むのでGit管理外）：
  - 本体の走行記録  drive_logs/<日付>/*/v2_emmc/LOG_*.csv（Collect-Logs.cmd）
  - 焼き込み映像    drive_logs/v2_video/<走行>/<走行>_NN.ts と .csv（Collect-Video.cmd）
出力（drive_logs/v2_video/laps/）：
  - <日付>_<周>周目_<タイム>.ts        切り出したそのもの（画質そのまま）
  - 同 .mp4                            音をAACにしただけ
  - 同 _公開用.mp4                     風切りを下げた音（wind_reduce.py。--no-clean で作らない）

周の数え方は tools/race_analysis と同じ：LapCount が N になった行の LapTime が第N周のタイム（分）。
その行の時刻が周の終わり、そこからタイムを引いた時刻が周の始まり。
切り出しは録画のキーフレーム（1秒ごと。その前に毎回PAT・PMTがある）の所で、周の始まりの前 --lead 秒から
終わりの後 --tail 秒まで。章（10分ごとの .ts）をまたぐときはつなぐ。ffmpeg は PATH か winget の Gyan.FFmpeg。
手順書：unoq_video_check_procedure.md 5-25
"""
import argparse
import bisect
import csv
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / 'drive_logs'
VIDEO = LOGS / 'v2_video'
OUT = VIDEO / 'laps'
JST = timezone(timedelta(hours=9))
PID_VID = 0x100


def ts_of(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()


def jst(t):
    return datetime.fromtimestamp(t, JST).strftime('%H:%M:%S')


def mmss(sec):
    return f"{int(sec // 60)}'{sec % 60:06.3f}"


# ---------------------------------------------------------------- 周
def read_laps(paths):
    """記録から周を拾う。返り値：[{lap, time_s, end, start, log}]（同じ周が続きの記録に重ねて出ても1つ）"""
    laps = {}
    for path in paths:
        prev, diffs, rows = None, [], []
        with open(path, newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                lc = r.get('LapCount')
                if r.get('gnss_utc') and r.get('host_utc'):
                    diffs.append(ts_of(r['host_utc']) - ts_of(r['gnss_utc']))
                    if len(diffs) > 4000:
                        diffs = diffs[-2000:]
                if lc and prev is not None and lc != prev and r.get('LapTime'):
                    try:
                        n, lt = int(float(lc)), float(r['LapTime']) * 60
                    except ValueError:
                        n = None
                    if n is not None and int(float(prev)) == n - 1:
                        rows.append((n, lt, ts_of(r['host_utc']), list(diffs[-400:])))
                if lc:
                    prev = lc
        for n, lt, host, d in rows:
            # 本体の時計が測位でまだ合っていないことがある（11/8の朝は13分半ずれていた）。
            # gnss_utc は秒の切り捨てなので、合っていれば host − gnss の中央値は約+0.5秒
            corr = 0.0
            if d:
                med = sorted(d)[len(d) // 2]
                corr = med - 0.5
            end = host - corr
            laps.setdefault(n, {'lap': n, 'time_s': lt, 'end': end, 'start': end - lt, 'log': str(path)})
    return [laps[k] for k in sorted(laps)]


def day_logs(date):
    return sorted(glob.glob(str(LOGS / date / '*' / 'v2_emmc' / 'LOG_*.csv')))


def read_rpm(paths, t0, t1):
    """[t0, t1] の回転数（時刻は本体の時計を測位で直したもの）"""
    out = []
    lo = datetime.fromtimestamp(t0 - 3600, timezone.utc).isoformat()[:19]   # 時計のずれ（最大で十数分）を見込んで広めに
    hi = datetime.fromtimestamp(t1 + 3600, timezone.utc).isoformat()[:19]
    for path in paths:
        diffs, corr, k = [], None, 0
        with open(path, newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                h = r.get('host_utc') or ''
                if not (lo <= h[:19] <= hi):
                    continue
                if r.get('gnss_utc'):
                    diffs.append(ts_of(h) - ts_of(r['gnss_utc']))
                    k += 1
                    if len(diffs) > 400:
                        diffs = diffs[-400:]
                    if corr is None or k % 100 == 0:
                        corr = sorted(diffs)[len(diffs) // 2] - 0.5
                if not r.get('RPM') or corr is None:
                    continue
                t = ts_of(h) - corr
                if t0 <= t <= t1:
                    out.append((t, float(r['RPM'])))
    out.sort()
    ts, rp, last = [], [], None
    for t, v in out:
        if t != last:
            ts.append(t)
            rp.append(v)
            last = t
    return ts, rp


# ---------------------------------------------------------------- 映像
def chapters():
    """[(ts, csv, 頭の時刻, 終わりの時刻, [(video_s, utc)])]（時刻は測位の時計の行だけ）"""
    out = []
    for c in sorted(glob.glob(str(VIDEO / '*' / '*_[0-9][0-9].csv'))):
        tsf = c[:-4] + '.ts'
        if not os.path.isfile(tsf):
            continue
        rows = []
        with open(c, encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                if r.get('clock') == 'gnss':
                    rows.append((float(r['video_s']), ts_of(r['utc'])))
        if len(rows) >= 2:
            out.append((tsf, c, rows[0][1], rows[-1][1], rows))
    return out


def vs_of(rows, u):
    """その時刻の映像の秒（章の中）"""
    us = [b for _, b in rows]
    i = min(max(bisect.bisect_left(us, u), 1), len(rows) - 1)
    (a, ua), (b, ub) = rows[i - 1], rows[i]
    return a + (b - a) * (u - ua) / (ub - ua)


def utc_of(rows, v):
    vs = [a for a, _ in rows]
    i = min(max(bisect.bisect_left(vs, v), 1), len(rows) - 1)
    (a, ua), (b, ub) = rows[i - 1], rows[i]
    return ua + (ub - ua) * (v - a) / (b - a)


def scan_keys(path):
    """(最初の映像のPTS, [(キーフレームのPTS, その前のPATの位置)], 大きさ)"""
    pat_pos, keys, first = 0, [], None
    with open(path, 'rb') as f:
        pos = 0
        while chunk := f.read(188 * 50000):
            for i in range(0, len(chunk) - 187, 188):
                pk = chunk[i:i + 188]
                if pk[0] != 0x47:
                    continue
                pid = (pk[1] & 0x1f) << 8 | pk[2]
                if pid == 0:
                    pat_pos = pos + i
                    continue
                if pid != PID_VID or not pk[1] & 0x40:
                    continue
                off = 4 + (1 + pk[4] if pk[3] & 0x20 else 0)
                if off + 14 > 188 or pk[off:off + 3] != b'\x00\x00\x01':
                    continue
                b = pk[off + 9:off + 14]
                pts = (b[0] >> 1 & 7) << 30 | b[1] << 22 | (b[2] >> 1) << 15 | b[3] << 7 | b[4] >> 1
                if first is None:
                    first = pts
                if pk[3] & 0x20 and pk[4] and pk[5] & 0x40:   # random_access_indicator
                    keys.append((pts, pat_pos))
            pos += len(chunk)
    return first, keys, pos


def cut_plan(chs, t0, t1):
    """[t0, t1] を含む章の切り出し範囲 [(ts, 頭のバイト, 終わりのバイト)] と、切り出しの頭の時刻"""
    use = [c for c in chs if c[3] >= t0 and c[2] <= t1]
    if not use:
        raise SystemExit('その時間の映像がPCに無い（Collect-Video.cmd で吸い出す）')
    if use[0][2] > t0 or use[-1][3] < t1:
        print('注意：映像がその周の全部を含んでいない（章の切れ目か録画の止まり）', file=sys.stderr)
    plan, start_utc = [], None
    for k, (tsf, _, u0, u1, rows) in enumerate(use):
        first, keys, size = scan_keys(tsf)
        if not keys:
            continue
        a, b = 0, size
        if k == 0:
            p0 = first + vs_of(rows, max(t0, u0)) * 90000
            key = max((x for x in keys if x[0] <= p0), default=keys[0])
            a = key[1]
            start_utc = utc_of(rows, (key[0] - first) / 90000)
        if k == len(use) - 1:
            p1 = first + vs_of(rows, min(t1, u1)) * 90000
            after = [x for x in keys if x[0] > p1]
            b = after[0][1] if after else size
        plan.append((tsf, a, b))
    return plan, start_utc


def write_cut(plan, out):
    with open(out, 'wb') as w:
        for tsf, a, b in plan:
            with open(tsf, 'rb') as f:
                f.seek(a)
                n = b - a
                while n > 0:
                    c = f.read(min(n, 8 << 20))
                    w.write(c)
                    n -= len(c)


# ---------------------------------------------------------------- ffmpeg
def ffbin(name):
    p = shutil.which(name)
    if p:
        return p
    pats = [os.path.expanduser(rf'~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\{name}.exe'),
            os.path.expanduser(rf'~\AppData\Local\Packages\Claude_*\LocalCache\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\{name}.exe')]
    for pat in pats:
        hit = sorted(glob.glob(pat))
        if hit:
            return hit[-1]
    raise SystemExit(f'{name} が見つからない（winget install --id Gyan.FFmpeg -e）')


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def audio_start(mp4):
    r = subprocess.run([ffbin('ffprobe'), '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=start_time',
                        '-of', 'csv=p=0', str(mp4)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip() or 0)


def read_wav(p):
    import numpy as np
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768, w.getframerate()


def write_wav(p, y, sr):
    import numpy as np
    with wave.open(str(p), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- コマンド
def cmd_laps(a):
    laps = read_laps(day_logs(a.date))
    if not laps:
        raise SystemExit(f'drive_logs/{a.date}/*/v2_emmc/ に周の記録が無い')
    chs = chapters()
    best = min((x for x in laps if x['time_s'] > 30), key=lambda x: x['time_s'], default=None)
    for x in laps:
        has = any(c[2] <= x['start'] and c[3] >= x['end'] for c in chs)
        part = not has and any(c[3] >= x['start'] and c[2] <= x['end'] for c in chs)
        mark = '★' if best and x['lap'] == best['lap'] else ' '
        print(f"{mark}{x['lap']:3d}周目  {mmss(x['time_s']):>10s}  {jst(x['start'])}〜{jst(x['end'])}  "
              f"映像{'あり' if has else ('一部' if part else 'なし')}")


def cmd_clip(a):
    logs = day_logs(a.date)
    laps = read_laps(logs)
    if a.best:
        cand = [x for x in laps if x['time_s'] > 30 and any(c[2] <= x['start'] and c[3] >= x['end'] for c in chapters())]
        if not cand:
            raise SystemExit('映像のある周が無い')
        lap = min(cand, key=lambda x: x['time_s'])
    else:
        lap = next((x for x in laps if x['lap'] == a.lap), None)
        if not lap:
            raise SystemExit(f'{a.lap}周目が記録に無い（laps で一覧）')
    t0, t1 = lap['start'] - a.lead, lap['end'] + a.tail
    print(f"{lap['lap']}周目 {mmss(lap['time_s'])}（{jst(lap['start'])}〜{jst(lap['end'])}）を切り出す")
    plan, start_utc = cut_plan(chapters(), t0, t1)
    OUT.mkdir(parents=True, exist_ok=True)
    t = lap['time_s']
    name = f"{a.date}_{lap['lap']}周目_{int(t // 60)}分{int(t % 60):02d}秒{int(round((t % 1) * 1000)) % 1000:03d}"
    ts_out, mp4, pub = OUT / f'{name}.ts', OUT / f'{name}.mp4', OUT / f'{name}_公開用.mp4'
    write_cut(plan, ts_out)
    ff = ffbin('ffmpeg')
    run(ff, '-hide_banner', '-v', 'error', '-y', '-i', ts_out, '-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-avoid_negative_ts', 'make_zero', mp4)
    lead_in = lap['start'] - start_utc
    print(f'  {ts_out.name}（{ts_out.stat().st_size / 1e6:.0f}MB）、周の始まりは頭から{lead_in:.1f}秒')
    print(f'  {mp4.name}')
    if a.no_clean:
        return
    sys.path.insert(0, str(Path(__file__).parent))
    import numpy as np
    import wind_reduce
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / 'src.wav'
        run(ff, '-hide_banner', '-v', 'error', '-y', '-i', mp4, '-map', '0:a', '-af', 'aresample=async=1:first_pts=0',
            '-ar', '48000', '-ac', '1', src)
        x, sr = read_wav(src)
        a_start = audio_start(mp4)
        rt, rp = read_rpm(logs, start_utc - 15, start_utc + len(x) / sr + 15)
        if len(rt) < 100:
            raise SystemExit('その時間の回転数が記録に無い（--no-clean で音はそのまま）')
        rpm_t = np.array(rt) - (start_utc + a_start)
        y, info = wind_reduce.process(x, sr, rpm_t, np.array(rp))
        cl = Path(tmp) / 'clean.wav'
        write_wav(cl, y, sr)
        run(ff, '-hide_banner', '-v', 'error', '-y', '-i', mp4, '-itsoffset', f'{a_start:.4f}', '-i', cl,
            '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=7', '-ar', '48000',
            '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', pub)
    print(f"  {pub.name}（記録と音のずれ {info['offset_s']:+.2f}秒、2次の倍音の立ち {info['order2_prominence_db']}dB、"
          f"シフトの所の下げ 最大{-info['shift_min_gain_db']:.1f}dB）")
    (OUT / f'{name}.json').write_text(json.dumps({'lap': lap, 'start_utc': start_utc, 'lead_in_s': lead_in,
                                                  'audio': info, 'chapters': [p[0] for p in plan]},
                                                 ensure_ascii=False, indent=1), encoding='utf-8')


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    p =argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('laps', help='その日の周の一覧')
    s.add_argument('date', help='YYYYMMDD（drive_logs/<日付>/）')
    s.set_defaults(fn=cmd_laps)
    s = sub.add_parser('clip', help='1周を切り出して公開用のMP4を作る')
    s.add_argument('date')
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument('--lap', type=int, help='周の番号（ロガーの通し）')
    g.add_argument('--best', action='store_true', help='映像のある周でいちばん速い周')
    s.add_argument('--lead', type=float, default=3.0, help='周の始まりの前に入れる秒（既定3）')
    s.add_argument('--tail', type=float, default=2.0, help='周の終わりの後に入れる秒（既定2）')
    s.add_argument('--no-clean', action='store_true', help='風切りを下げた公開用を作らない')
    s.set_defaults(fn=cmd_clip)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == '__main__':
    main()
