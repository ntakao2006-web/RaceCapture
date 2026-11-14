"""「走行を見る」の走行の行から、解析アプリ（別のリポジトリ ecologger-analysis、SP-10）で開く（SP-10-8、2026-11-14）。

    1. その走行を ecorun の形に書き出す（tools/analysis_export/export_session.py）。置き場は drive_logs/sessions/<走行のid>.ecorun。
       動画も入れるときは <走行のid>_video.ecorun（動画はキーフレームの所で切って写すので、走行の長さぶんの大きさになる）。
       書き出しが走行記録より新しければ、書き出し直さない。測位はシールドのSD（v2_sd）にその時間の解があればそこから取る
       （10Hz全部の解）。SDは別の日に回収したカードに残っていることがあるので（SUGO 11/8 の解は 11/11 に回収したSD）、
       その走行のフォルダーのSD、その日より後に回収したSDの順に、書き出しの道具へ渡す（道具が時間の合うものを選ぶ）。
    2. 解析アプリを起こし、書き出した走行を渡す。解析アプリがもう開いていれば、アプリの側でそちらへ渡して窓を前に出す。

解析アプリの場所（上から順に探す）：
    環境変数 ECOLOGGER_ANALYSIS                       exe か、リポジトリのフォルダー
    %USERPROFILE%\\.ecologger\\analysis_app.txt          1行目に、exe か、リポジトリのフォルダー
    %USERPROFILE%\\.ecologger\\EcoLogger-Analysis\\      配る zip を広げた所（EcoLogger-Analysis.exe）
    このリポジトリの隣の EcoLogger-Analysis\\          開発の手元（.venv があればそのソースを、無ければ dist の exe を）
%LOCALAPPDATA% は Claude のアプリから動かしたときだけ振り替えられるので使わない（CLAUDE.md）。
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXPORTER = REPO / 'tools' / 'analysis_export' / 'export_session.py'
APP_NAME = 'EcoLogger-Analysis'
VIDEO_MB_PER_MIN = 76.0          # 焼き込み動画の大きさの目安（SUGO 11/8：443MB／5分48秒）
NOT_FOUND = (f'解析アプリが見つかりません。配る zip（{APP_NAME}-<版>-win64.zip）を %USERPROFILE%\\.ecologger\\ に広げるか、'
             '%USERPROFILE%\\.ecologger\\analysis_app.txt の1行目に exe かリポジトリのフォルダーを書いてください')


def _from_place(p):
    """exe・リポジトリのフォルダー・zip を広げたフォルダーから、起こし方 (argv, cwd) を作る。使えなければ None"""
    p = Path(p).expanduser()
    if p.is_file() and p.suffix.lower() == '.exe':
        return [str(p)], str(p.parent)
    if not p.is_dir():
        return None
    venv = p / '.venv' / 'Scripts' / 'pythonw.exe'
    if venv.is_file() and (p / 'ecoanalysis' / '__init__.py').is_file():
        return [str(venv), '-m', 'ecoanalysis'], str(p)
    for exe in (p / f'{APP_NAME}.exe', p / 'dist' / APP_NAME / f'{APP_NAME}.exe'):
        if exe.is_file():
            return [str(exe)], str(exe.parent)
    return None


def find_app(home=None, repo=REPO, env=None):
    """解析アプリの起こし方 (argv, cwd, どこで見つけたか)。見つからなければ None"""
    home = Path(home or Path.home())
    env = os.environ if env is None else env
    places = []
    if env.get('ECOLOGGER_ANALYSIS'):
        places.append((env['ECOLOGGER_ANALYSIS'], '環境変数 ECOLOGGER_ANALYSIS'))
    txt = home / '.ecologger' / 'analysis_app.txt'
    try:
        line = txt.read_text(encoding='utf-8').strip().splitlines()[0].strip().strip('"')
        if line:
            places.append((line, str(txt)))
    except (OSError, IndexError):
        pass
    places.append((home / '.ecologger' / APP_NAME, f'%USERPROFILE%\\.ecologger\\{APP_NAME}'))
    places.append((Path(repo).parent / APP_NAME, f'リポジトリの隣の {APP_NAME}'))
    for place, where in places:
        got = _from_place(place)
        if got:
            return got[0], got[1], where
    return None


def session_dir(drive_logs, run, video):
    return Path(drive_logs) / 'sessions' / f'{run["id"]}{"_video" if video else ""}.ecorun'


def log_path(drive_logs, run):
    return Path(drive_logs) / run['log']


def is_fresh(out, csv):
    """書き出しが走行記録より新しければ True（書き出し直さない）"""
    meta = Path(out) / 'session.json'
    try:
        return meta.stat().st_mtime >= Path(csv).stat().st_mtime
    except OSError:
        return False


def sd_folders(drive_logs, csv, limit=6):
    """測位を探すSDのフォルダー：その走行の v2_sd、その日以後に回収した v2_sd（日の古い順）。走行記録は drive_logs/<日>/runNN_*/v2_emmc/"""
    csv = Path(csv)
    own = csv.parent.parent / 'v2_sd'
    day = csv.parent.parent.parent.name
    out = [own] if own.is_dir() else []
    for sd in sorted(Path(drive_logs).glob('*/run*/v2_sd')):
        if sd.is_dir() and sd.parent.parent.name >= day and sd.resolve() != own.resolve():
            out.append(sd)
    return out[:limit]


def export_argv(csv, out, video, sds=(), python=None):
    argv = [python or sys.executable, '-u', str(EXPORTER), str(csv), '--out', str(out)]   # -u：進み具合の行を溜めずに渡す
    for sd in sds:
        argv += ['--sd', str(sd)]
    if video:
        argv.append('--video')
    return argv


def video_mb(run):
    return round((run.get('video_minutes') or 0) * VIDEO_MB_PER_MIN)


def run_export(argv, on_line=None, timeout=3600):
    """書き出しの道具を動かし、出力の行を on_line へ渡す。失敗したら RuntimeError（最後の数行つき）"""
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                         env=env, cwd=str(REPO), creationflags=flags)
    lines = []
    try:
        for line in p.stdout:
            line = line.rstrip()
            if line:
                lines.append(line)
                if on_line:
                    on_line(line)
        p.wait(timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        raise RuntimeError('書き出しが終わらない（1時間）')
    finally:
        p.stdout.close()
    if p.returncode:
        raise RuntimeError('書き出しに失敗：' + ' / '.join(lines[-3:])[:400])
    return lines


def launch(app, out):
    """解析アプリを、このアプリと切り離して起こす（このアプリを閉じても解析アプリは残る）"""
    argv, cwd, _ = app
    flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    subprocess.Popen(argv + [str(out)], cwd=cwd, creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_run(drive_logs, run, video, on_line=None, app=None, python=None):
    """走行を書き出して（要るときだけ）解析アプリで開く。{out, exported, sd, app, where}"""
    app = app or find_app()
    if not app:
        raise RuntimeError(NOT_FOUND)
    csv = log_path(drive_logs, run)
    if not csv.is_file():
        raise RuntimeError(f'走行記録が無い：{run["log"]}')
    out = session_dir(drive_logs, run, video)
    exported = False
    if not is_fresh(out, csv):
        need = video_mb(run) * 1.2e6 if video else 0
        free = shutil.disk_usage(drive_logs).free
        if need > free:
            raise RuntimeError(f'PCの空きが足りません（動画に約{need / 1e9:.1f}GB要るのに、空きは{free / 1e9:.1f}GB）。動画なしで開いてください')
        sds = sd_folders(drive_logs, csv)
        try:
            run_export(export_argv(csv, out, video, sds, python), on_line)
        except RuntimeError:
            if not sds:
                raise
            if on_line:
                on_line('SDを読むところで止まったので、本体の記録の測位で書き出し直します')
            run_export(export_argv(csv, out, video, (), python), on_line)
        exported = True
    launch(app, out)
    return {'out': str(out), 'exported': exported, 'gnss': gnss_source(out), 'where': app[2]}


def gnss_source(out):
    """書き出した走行の測位の出どころ（'sd'・'logger'。読めなければ ''）"""
    import json
    try:
        return (json.loads((Path(out) / 'session.json').read_text(encoding='utf-8')).get('gnss') or {}).get('source', '')
    except (OSError, ValueError):
        return ''
