"""周の動画を、アプリの中で見られる形にする（2026-11-13、SP-5-3、`SPEC.md` 4章 A-2）。

録画の .ts（映像 H.264・音 MP2）は、ブラウザではそのまま再生できない。周を選んで「見る」を押したら、
その周のぶんだけを録画から抜き出し（映像は作り直さないので画質はそのまま・速い）、音だけAACに直した MP4 を作る。
切り出しそのものは 1周の動画の道具（tools/lap_video/lap_video.py）の部品を使う：キーフレームの所で切り、
章（10分ごとのファイル）をまたぐ周はつなぐ。

    clip = make(root, run, lap, out_dir)      # {'file', 'lead_in_s', 'seconds', 'partial'}。もう作ってあればそれを返す

- 置き場は drive_logs/runs_cache/clips/（見るための一時の写し。消してよい。元の録画は変えない）
- 周の始まりの LEAD_S 秒前から、終わりの TAIL_S 秒後まで。lead_in_s は「動画の頭から何秒の所が周の始まりか」
- 動画が周の一部しか無いときは、ある所だけを出して partial を True にする。全く無ければ NoVideo
- ffmpeg が要る（PATH か winget の Gyan.FFmpeg）。無ければ NoFfmpeg
風切りを下げた公開用の動画は、今までどおり lap_video.py clip で作る（回転数の記録と numpy・scipy が要るため）。
"""
import csv
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools' / 'lap_video'))

LEAD_S, TAIL_S = 3.0, 2.0
CLIP_DIR = Path('runs_cache') / 'clips'


class NoVideo(RuntimeError):
    """その周の動画がPCに無い"""


class NoFfmpeg(RuntimeError):
    """ffmpeg が見つからない"""


def chapter_rows(root, video):
    """lap_video.cut_plan が使う章の形 (ts, csv, 頭の時刻, 終わりの時刻, [(video_s, utc)])。時刻は測位の時計の行だけ"""
    import lap_video
    ts = Path(root) / video['path']
    rows = []
    with open(ts.with_suffix('.csv'), encoding='utf-8', errors='replace', newline='') as f:
        for r in csv.DictReader(f):
            if r.get('clock') == 'gnss':
                try:
                    rows.append((float(r['video_s']), lap_video.ts_of(r['utc'])))
                except (KeyError, ValueError, TypeError):
                    continue
    return (str(ts), str(ts.with_suffix('.csv')), rows[0][1], rows[-1][1], rows) if len(rows) >= 2 else None


def clip_name(run, lap, index):
    t = lap['time_s'] or 0
    return f"{run['id']}_{index + 1:03d}_lap{lap['lap']}_{int(t // 60)}m{t % 60:06.3f}s.mp4".replace(':', '')


def make(root, run, index, lap, out_dir=None, ffmpeg=None):
    """run（run_index の1つ）の、周の表の index 番目の周 lap の動画を作る"""
    import lap_video
    if lap.get('start') is None or lap.get('end') is None:
        raise NoVideo('この周は始まりと終わりの時刻が分からないので、動画を結べません')
    root = Path(root)
    out_dir = Path(out_dir) if out_dir else root / CLIP_DIR
    out = out_dir / clip_name(run, lap, index)
    t0, t1 = lap['start'] - LEAD_S, lap['end'] + TAIL_S
    chapters = [c for c in (chapter_rows(root, v) for v in run.get('videos', [])) if c]
    use = [c for c in chapters if c[3] >= t0 and c[2] <= t1]
    if not use:
        raise NoVideo('その周の時間の動画がPCにありません（録画していなかった・まだ回収していない・本体で入れ替わって消えた、のどれかです）')
    partial = use[0][2] > lap['start'] or use[-1][3] < lap['end']
    if out.is_file() and out.stat().st_size > 0:
        info = out.with_suffix('.json')
        try:
            import json
            return json.loads(info.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass   # 覚え書きが無ければ作り直す
    try:
        ffmpeg = ffmpeg or lap_video.ffbin('ffmpeg')
    except SystemExit as exc:
        raise NoFfmpeg(f'{exc}。動画を見るには ffmpeg が要ります') from None
    try:
        plan, start_utc = lap_video.cut_plan(use, t0, t1)
    except SystemExit as exc:
        raise NoVideo(str(exc)) from None
    if not plan or start_utc is None:
        raise NoVideo('録画の中に切り出せる所が見つかりません（録画のファイルが壊れているかもしれません）')
    out_dir.mkdir(parents=True, exist_ok=True)
    cut = out.with_suffix('.cut.ts')
    try:
        lap_video.write_cut(plan, cut)
        done = subprocess.run([str(ffmpeg), '-hide_banner', '-v', 'error', '-y', '-i', str(cut), '-map', '0:v:0', '-map', '0:a:0?',
                               '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart',
                               '-avoid_negative_ts', 'make_zero', str(out.with_suffix('.part.mp4'))],
                              capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
        if done.returncode:
            raise OSError(f'ffmpeg が失敗しました：{done.stderr.strip()[:300]}')
        out.with_suffix('.part.mp4').replace(out)
    finally:
        cut.unlink(missing_ok=True)
        out.with_suffix('.part.mp4').unlink(missing_ok=True)
    import json
    result = {'file': out.name, 'lead_in_s': round(max(0.0, lap['start'] - start_utc), 2),
              'seconds': round(lap['end'] - lap['start'], 2), 'partial': partial, 'bytes': out.stat().st_size}
    out.with_suffix('.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    return result


# ---------------------------------------------------------------- 残す（名前を付けて置く・公開用）
KEEP_DIR = Path('v2_video') / 'laps'     # 1周の動画の置き場（tools/lap_video/lap_video.py と同じ）


def keep_name(run, lap):
    """残すときの名前：<走った日>_<周>周目_<タイム>（lap_video.py clip と同じ付け方）"""
    t = lap['time_s'] or 0
    return f"{run['day'].replace('-', '')}_{lap['lap']}周目_{int(t // 60)}分{int(t % 60):02d}秒{int(round((t % 1) * 1000)) % 1000:03d}"


def keep(root, run, index, lap, clean=False, out_dir=None, clip_dir=None, ffmpeg=None):
    """周の動画を、名前を付けて drive_logs/v2_video/laps/ に残す。clean なら、風切りを下げた公開用も作る。
    返り値：{'folder', 'file', 'public'（公開用の名前か None）, 'audio'（風切りを下げたときの情報）}
    公開用は、走行記録の回転数に合わせてエンジンの音の倍音だけを残す（tools/lap_video/wind_reduce.py。numpy・scipy が要る）"""
    import json
    import shutil
    import tempfile
    import lap_video
    root = Path(root)
    clip = make(root, run, index, lap, out_dir=clip_dir, ffmpeg=ffmpeg)
    src = (Path(clip_dir) if clip_dir else root / CLIP_DIR) / clip['file']
    out_dir = Path(out_dir) if out_dir else root / KEEP_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    name = keep_name(run, lap)
    mp4 = out_dir / f'{name}.mp4'
    if not mp4.is_file() or mp4.stat().st_size != src.stat().st_size:
        shutil.copy2(src, mp4)
    result = {'folder': str(out_dir), 'file': mp4.name, 'public': None, 'audio': None, 'partial': clip['partial']}
    if not clean:
        return result
    try:
        import numpy as np
        import wind_reduce
    except ImportError as exc:
        raise NoFfmpeg(f'公開用の音を作る部品（numpy・scipy）がありません：{exc}') from None
    ff = ffmpeg or lap_video.ffbin('ffmpeg')
    pub = out_dir / f'{name}_公開用.mp4'
    start_utc = lap['start'] - clip['lead_in_s']       # 動画の頭の時刻（測位の時計）
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / 'src.wav'
        lap_video.run(ff, '-hide_banner', '-v', 'error', '-y', '-i', mp4, '-map', '0:a', '-af', 'aresample=async=1:first_pts=0',
                      '-ar', '48000', '-ac', '1', wav)
        x, sr = lap_video.read_wav(wav)
        a_start = lap_video.audio_start(mp4)
        rt, rp = lap_video.read_rpm([str(root / run['log'])], start_utc - 15, start_utc + len(x) / sr + 15)
        if len(rt) < 100:
            raise NoVideo('その時間の回転数が走行記録に無いので、公開用（風切りを下げた音）は作れません。動画そのものは残しました')
        y, info = wind_reduce.process(x, sr, np.array(rt) - (start_utc + a_start), np.array(rp))
        cleaned = Path(tmp) / 'clean.wav'
        lap_video.write_wav(cleaned, y, sr)
        lap_video.run(ff, '-hide_banner', '-v', 'error', '-y', '-i', mp4, '-itsoffset', f'{a_start:.4f}', '-i', cleaned,
                      '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=7', '-ar', '48000',
                      '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', pub)
    (out_dir / f'{name}.json').write_text(json.dumps({'lap': lap, 'start_utc': start_utc, 'lead_in_s': clip['lead_in_s'], 'audio': info},
                                                      ensure_ascii=False, indent=1), encoding='utf-8')
    result.update(public=pub.name, audio=info)
    return result
