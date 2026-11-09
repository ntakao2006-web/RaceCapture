"""スピン・コースアウト・後ろが出た所を走行記録から拾い、焼き込み映像の切り抜きを1本につなぐ（2026-11-09、ユーザー依頼）

  python tools/lap_video/incidents.py find  tools/lap_video/incidents_sugo_20261107-08.json   候補の一覧
  python tools/lap_video/incidents.py build tools/lap_video/incidents_sugo_20261107-08.json   設定の clips から1本の動画

流れ：find で候補を出す → 候補の映像を見て（sheet でコマを並べた画像も作れる）本物だけを設定ファイルの
sections[].clips に書く → build。記録だけで決めると誤りがあるので、選ぶのは人（かClaude）が映像を見てから。

候補の拾い方（どれも速度40km/h超。手順書 unoq_video_check_procedure.md 5-26）：
  - 後ろが出た：横滑り角（IMUだけで出す。β' = 回る速さ×K − 横G÷速さ、1.5秒で忘れる積分）が9°超。
    Kは横G0.3超・60km/h超のコーナーで回る速さを横G÷速さに合わせた倍率。ふだんは99%が5°以下
  - スピン：その中で横滑り角が大きく（30°超）、速度が大きく落ちたもの
  - ラインから外れた：その位置から3m以内を通ったほかの周が1つ以下（設定の全部の走行で数える）。
    40〜60km/hのものはピットレーンなので外す
  - 止まりかけた：直前5秒に90km/h超で、35km/hを切った
  - 路面の振動（AccelZの8Hzより上）が強いだけのものは、毎周同じ縁石で出るので候補にしない
出力：drive_logs/v2_video/incidents/（位置を含むのでGit管理外）
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).parent))
import lap_video as lv  # noqa: E402

ROOT = lv.ROOT
OUTDIR = lv.VIDEO / 'incidents'
JST = 'Asia/Tokyo'
COLS = ['host_utc', 'gnss_utc', 'mcu_ms', 'GPSSpeed', 'Speed', 'GyroZ', 'LatAccel', 'AccelZ', 'Lat', 'Lon', 'LapCount']
FONT = 'C\\:/Windows/Fonts/YuGothB.ttc'
SLIDE_DEG, SPIN_DEG = 9.0, 30.0


# ---------------------------------------------------------------- 記録
def load(sess):
    d = pd.read_csv(ROOT / sess['log'], usecols=lambda c: c in COLS, low_memory=False)
    h = pd.to_datetime(d.host_utc, format='ISO8601')
    g = pd.to_datetime(d.gnss_utc, format='ISO8601', errors='coerce')
    corr = (h - g).dt.total_seconds().rolling(2001, min_periods=50, center=True).median().bfill().ffill() - 0.5
    d['t'] = h - pd.to_timedelta(corr.fillna(0), unit='s')       # 本体の時計を測位で直す（lap_video と同じ）
    a, b = (pd.Timestamp(x, tz=JST) for x in sess['window'])
    d = d[(d.t >= a) & (d.t <= b)].reset_index(drop=True)
    d['ts'] = d.mcu_ms / 1000.0
    d['x'] = (d.Lon - 140.78) * np.cos(np.radians(38.14)) * 111320.0
    d['y'] = (d.Lat - 38.14) * 110540.0
    d['v'] = d.Speed.fillna(d.GPSSpeed).interpolate().fillna(0)
    return d


def add_signals(d):
    dt = d.ts.diff().fillna(0.01).clip(0, 0.05).values
    v = d.v.values / 3.6
    vc = np.clip(v, 5, None)
    ay = (-d.LatAccel.fillna(0) * 9.81).values
    r = np.radians(d.GyroZ.fillna(0).values)
    st = (d.LatAccel.abs() > 0.3).values & (v > 60 / 3.6)
    K = float((r[st] @ (ay[st] / vc[st])) / (r[st] @ r[st])) if st.sum() > 100 else 1.0
    bd = r * K - ay / vc
    beta = np.zeros(len(d))
    for i in range(1, len(d)):
        beta[i] = beta[i - 1] * (1 - dt[i] / 1.5) + bd[i] * dt[i]
    d['beta'] = np.degrees(beta) * (v > 30 / 3.6)
    sos = butter(2, 8, 'highpass', fs=100, output='sos')
    az = d.AccelZ.interpolate().fillna(0).values
    d['vib'] = np.sqrt(pd.Series(sosfiltfilt(sos, az) ** 2).rolling(30, center=True, min_periods=1).mean())
    return K


def add_others(ds):
    """その位置から3m以内を通ったほかの周の数（全部の走行で）"""
    pts = []
    for k, (name, d) in enumerate(ds.items()):
        mv = d[((d.Lat.diff() != 0) | (d.Lon.diff() != 0)) & (d.GPSSpeed > 40)]
        pts.append(pd.DataFrame({'x': mv.x, 'y': mv.y, 'p': k * 1000 + mv.LapCount.fillna(0).astype(int), 's': name, 'i': mv.index}))
    P = pd.concat(pts, ignore_index=True)
    nb = cKDTree(np.c_[P.x, P.y]).query_ball_point(np.c_[P.x, P.y], r=3.0)
    p = P.p.values
    P['n'] = [len(set(p[j]) - {p[i]}) for i, j in enumerate(nb)]
    for name, d in ds.items():
        q = P[P.s == name].set_index('i').n
        d['others'] = q.reindex(d.index).ffill(limit=30)


def spans(mask, ts, gap=3.0, minlen=0.0):
    idx = np.where(mask)[0]
    out = []
    if not len(idx):
        return out
    s = p = idx[0]
    for i in idx[1:]:
        if ts[i] - ts[p] > gap:
            if ts[p] - ts[s] >= minlen:
                out.append((s, p))
            s = i
        p = i
    if ts[p] - ts[s] >= minlen:
        out.append((s, p))
    return out


def find(cfg):
    ds = {s['name']: load(s) for s in cfg['sessions']}
    for name, d in ds.items():
        K = add_signals(d)
        print(f'{name}: {len(d)}行、K {K:.3f}、横滑り角の99% {d.beta.abs().quantile(.99):.1f}°', file=sys.stderr)
    add_others(ds)
    rows = []
    for name, d in ds.items():
        ts, v = d.ts.values, d.v.values
        kinds = {'slide': (d.beta.abs() > SLIDE_DEG).values & (v > 40),
                 'line': (d.others <= 1).values & (v > 60),
                 'slow': (pd.Series(v).rolling(500, min_periods=1).max().values > 90) & (v < 35)}
        for k, m in kinds.items():
            for a, b in spans(m, ts, minlen=0.0 if k == 'slide' else 0.2):
                w = d.iloc[a:min(len(d), b + 600)]
                pk = w.beta.abs().idxmax()
                rows.append({'session': name, 'kind': k, 't': d.t[a], 'peak': d.t[pk], 'lap': int(d.LapCount[a]) + 1 if pd.notna(d.LapCount[a]) else None,
                             'beta': round(float(d.beta[pk]), 1), 'v0': round(float(v[a])), 'vmin': round(float(w.v.min())),
                             'others': None if pd.isna(d.others[a]) else int(d.others[a])})
    E = pd.DataFrame(rows).sort_values('t')
    E['grp'] = ((E.t.diff().dt.total_seconds() > 10) | (E.session != E.session.shift())).cumsum()
    out = []
    for _, g in E.groupby('grp'):
        kinds = set(g.kind)
        r = g.loc[g.beta.abs().idxmax()]
        spin = abs(r.beta) > SPIN_DEG and g.vmin.min() < 0.5 * g.v0.iloc[0]
        label = 'スピン' if spin else ('止まりかけた' if 'slow' in kinds else ('ラインから外れた' if 'line' in kinds else '後ろが出た'))
        out.append({'session': r.session, 'at': g.t.iloc[0].tz_convert(JST).strftime('%Y-%m-%d %H:%M:%S'),
                    'peak': r.peak.tz_convert(JST).strftime('%Y-%m-%d %H:%M:%S.%f')[:23], 'lap': r.lap, 'guess': label,
                    'kinds': ','.join(sorted(kinds)), 'beta_max': float(r.beta), 'v0': int(g.v0.iloc[0]), 'vmin': int(g.vmin.min())})
    return out, ds


# ---------------------------------------------------------------- 動画
def ff(*args, cwd=None):
    subprocess.run([lv.ffbin('ffmpeg'), '-hide_banner', '-v', 'error', '-y', *map(str, args)], check=True, cwd=cwd)


def card(tmp, name, lines, sec=2.5):
    """黒地に文字の見出し（映像の切り抜きと同じ形式：1920x1080・30コマ・H.264、音は無音のAAC）"""
    vf = []
    for k, (text, size) in enumerate(lines):
        (Path(tmp) / f'{name}_{k}.txt').write_text(text, encoding='utf-8')
        y = f'(h/2)-{(len(lines) - 1) * 40}+{k * 80}-text_h/2'
        vf.append(f"drawtext=fontfile='{FONT}':expansion=none:textfile={name}_{k}.txt:fontsize={size}:fontcolor=white:x=(w-text_w)/2:y={y}")
    ff('-f', 'lavfi', '-i', f'color=c=black:s=1920x1080:r=30:d={sec}', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono',
       '-vf', ','.join(vf), '-t', str(sec), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
       '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '1', f'{name}.mp4', cwd=tmp)
    return Path(tmp) / f'{name}.mp4'


def clip_facts(d, at, post):
    w = d[(d.t >= at - pd.Timedelta(seconds=1)) & (d.t <= at + pd.Timedelta(seconds=post))]
    if not len(w):
        return None
    pk = w.loc[w.beta.abs().idxmax()]
    return {'beta_max': round(abs(float(pk.beta)), 0), 'v0': int(round(w.v.iloc[0])), 'vmin': int(round(w.v.min())),
            'lap': int(w.LapCount.iloc[0]) + 1 if pd.notna(w.LapCount.iloc[0]) else None}


def build(cfg, cfg_path):
    ds = {s['name']: load(s) for s in cfg['sessions']}
    for d in ds.values():
        add_signals(d)
    chs = lv.chapters()
    out = ROOT / cfg['out']
    out.parent.mkdir(parents=True, exist_ok=True)
    n_all = sum(len(s['clips']) for s in cfg['sections'])
    with tempfile.TemporaryDirectory() as tmp:
        parts, chapters, pos, no = [], [(0.0, 'はじめ')], 0.0, 0   # 最初の章は0秒からでないとプレーヤーが0秒へずらす
        parts.append(card(tmp, 'title', [(x, 56) for x in cfg['title'].split('\n')] + [(f'{n_all}場面', 40)], 3.0))
        pos += 3.0
        for si, sec in enumerate(cfg['sections']):
            parts.append(card(tmp, f's{si}', [(sec['title'], 60), (sec.get('note', ''), 36)], 2.5))
            pos += 2.5
            for c in sec['clips']:
                no += 1
                at = pd.Timestamp(c['at'], tz=JST)
                pre, post = c.get('pre', 6), c.get('post', 6)
                fx = clip_facts(ds[c['session']], at, post) or {}
                lap = c.get('lap') or fx.get('lap')
                t0, t1 = at.timestamp() - pre, at.timestamp() + post
                plan, st = lv.cut_plan(chs, t0 - 1, t1 + 1)
                tsf = Path(tmp) / f'c{no}.ts'
                lv.write_cut(plan, tsf)
                line1 = f"No.{no}（全{n_all}）　{c['session']}　{lap}周目　{at:%H:%M:%S}　{c['label']}"
                line2 = c.get('note') or (f"横滑り角 最大{fx['beta_max']:.0f}°　速度 {fx['v0']}→{fx['vmin']} km/h" if fx else '')
                (Path(tmp) / f'c{no}_1.txt').write_text(line1, encoding='utf-8')
                (Path(tmp) / f'c{no}_2.txt').write_text(line2, encoding='utf-8')
                box = 'box=1:boxcolor=black@0.6:boxborderw=12'
                vf = (f"drawtext=fontfile='{FONT}':expansion=none:textfile=c{no}_1.txt:fontsize=44:fontcolor=white:{box}:x=(w-text_w)/2:y=118,"
                      f"drawtext=fontfile='{FONT}':expansion=none:textfile=c{no}_2.txt:fontsize=34:fontcolor=yellow:{box}:x=(w-text_w)/2:y=186")
                ff('-ss', f'{t0 - st:.3f}', '-i', tsf.name, '-t', f'{pre + post:.3f}', '-map', '0:v:0', '-map', '0:a:0',
                   '-vf', vf, '-fps_mode', 'cfr', '-r', '30', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
                   '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '1', f'c{no}.mp4', cwd=tmp)
                tsf.unlink()
                parts.append(Path(tmp) / f'c{no}.mp4')
                chapters.append((pos, f"{no}. {c['session']} {lap}周目 {c['label']}"))
                pos += pre + post
                print(f'  {line1}　{line2}')
        (Path(tmp) / 'list.txt').write_text(''.join(f"file '{p.name}'\n" for p in parts), encoding='utf-8')
        meta = [';FFMETADATA1']
        for k, (a, title) in enumerate(chapters):
            b = chapters[k + 1][0] if k + 1 < len(chapters) else pos
            meta += ['[CHAPTER]', 'TIMEBASE=1/1000', f'START={int(a * 1000)}', f'END={int(b * 1000)}', f'title={title}']
        (Path(tmp) / 'chapters.txt').write_text('\n'.join(meta) + '\n', encoding='utf-8')
        ff('-f', 'concat', '-safe', '0', '-i', 'list.txt', '-i', 'chapters.txt', '-map_metadata', '1', '-map_chapters', '1',
           '-c', 'copy', '-movflags', '+faststart', 'all.mp4', cwd=tmp)
        shutil.move(str(Path(tmp) / 'all.mp4'), out)
    idx = out.with_suffix('.txt')
    idx.write_text('\n'.join(f'{int(a // 60)}:{int(a % 60):02d}  {t}' for a, t in chapters) + '\n', encoding='utf-8')
    print(f'{out}（{out.stat().st_size / 1e6:.0f}MB、{pos / 60:.1f}分）\n目次：{idx}')


def sheet(cfg, at, session=None):
    """候補の前後のコマ（−2・0・+1・+2・+3・+5秒）を並べた画像（選ぶときに見る用）"""
    import cv2
    t = pd.Timestamp(at, tz=JST).timestamp()
    plan, st = lv.cut_plan(lv.chapters(), t - 4, t + 8)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tsf = Path(tmp) / 'c.ts'
        lv.write_cut(plan, tsf)
        tiles = []
        for off in (-2, 0, 1, 2, 3, 5):
            jp = Path(tmp) / 'f.jpg'
            ff('-ss', f'{t - st + off:.2f}', '-i', tsf, '-frames:v', '1', '-vf', 'scale=640:-1', jp)
            im = cv2.imread(str(jp))
            cv2.putText(im, f'{off:+d}s', (10, 350), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
            tiles.append(im)
    p = OUTDIR / f"sheet_{at.replace(':', '').replace(' ', '_')}.jpg"
    cv2.imwrite(str(p), np.vstack([np.hstack(tiles[:3]), np.hstack(tiles[3:])]), [cv2.IMWRITE_JPEG_QUALITY, 80])
    print(p)


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('find', 'build'):
        s = sub.add_parser(name)
        s.add_argument('config')
    s = sub.add_parser('sheet', help='候補の前後のコマを並べた画像')
    s.add_argument('config')
    s.add_argument('at', help='"YYYY-MM-DD HH:MM:SS"（日本時間）')
    a = p.parse_args(argv)
    cfg = json.loads(Path(a.config).read_text(encoding='utf-8'))
    if a.cmd == 'find':
        cands, _ = find(cfg)
        OUTDIR.mkdir(parents=True, exist_ok=True)
        jp = OUTDIR / (Path(a.config).stem + '_candidates.json')
        jp.write_text(json.dumps(cands, ensure_ascii=False, indent=1), encoding='utf-8')
        for c in cands:
            print(f"{c['session']}  {c['at'][11:]}  {c['lap']}周目  {c['guess']:8s}  横滑り角{c['beta_max']:+6.1f}°  "
                  f"{c['v0']}→{c['vmin']}km/h  [{c['kinds']}]")
        print(f'{len(cands)}件 → {jp}')
    elif a.cmd == 'build':
        build(cfg, a.config)
    else:
        sheet(cfg, a.at)


if __name__ == '__main__':
    main()
