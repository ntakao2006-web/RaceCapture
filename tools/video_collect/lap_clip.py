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
