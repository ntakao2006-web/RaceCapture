"""レンズの歪みの補正＋ズームの値（lens.json）を本体の録画へ送る（Apply-Lens.cmd）。

lens.json は Lens-View.cmd（lens_view.py）で決めて s キーで保存したもの。本体では
/home/arduino/ecologger-video/lens.json に置く（別の名前で書いてから入れ替えるので、録画が書きかけを読むことは無い）。
録画（overlay_rec）は約1秒ごとにこのファイルを見ていて、変われば次のコマから補正して描く。読んだ結果は lens.json.status。

  python lens_apply.py            # lens.json を送る
  python lens_apply.py --off      # 本体から消して、補正しない元の映像に戻す
  python lens_apply.py --status   # 本体が今どう描いているかを見るだけ
つなぎ方は Apply-HUD.cmd と同じ（既定は ssh unoq、--adb でUSBのadb）。
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'video_hud'))
sys.path.insert(0, str(HERE.parent / 'collect_logs'))
from hud_apply import parse_status, runner  # noqa: E402

REMOTE_DIR = '/home/arduino/ecologger-video'
REMOTE = f'{REMOTE_DIR}/lens.json'
STATUS = f'{REMOTE}.status'
RECORDER = '/opt/ecologger-video/overlay_rec'
RUNNER = '/opt/ecologger-video/run-video.sh'
WAIT_S = 8

# 本体の録画（overlay_rec.c の lens_load）が受け付ける範囲と同じ
RANGES = {'k1': (-1, 1), 'k2': (-1, 1), 'zoom': (1, 4), 'f_ratio': (.2, 3), 'shift_x': (-.5, .5), 'shift_y': (-.5, .5)}


def check(data):
    """lens.json の中身を確かめ、誤りの文（無ければ None）を返す"""
    try:
        js = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as e:
        return f'JSONとして読めません（{e}）'
    for key, (lo, hi) in RANGES.items():
        v = js.get(key)
        if not isinstance(v, (int, float)) or not lo <= v <= hi:
            return f'{key} が無いか範囲（{lo}〜{hi}）の外です：{v!r}'
    size = js.get('size')
    if size and list(size) != [1280, 720]:
        return f'カメラ {size[0]}x{size[1]} で決めた値です。本体の録画は1280x720なので、Lens-View.cmd を --size 1280x720（既定）で開いて決め直してください'
    return None


def device_state(run):
    """(本体の録画が補正に対応しているか, 録画が動いているか, lens.json.status の中身)"""
    out = run(f'if grep -q OVERLAY_LENS {RECORDER} 2>/dev/null && grep -q OVERLAY_LENS {RUNNER} 2>/dev/null; '
              f'then echo READY=1; else echo READY=0; fi; '
              f'if pgrep -x overlay_rec >/dev/null; then echo ACTIVE=1; else echo ACTIVE=0; fi; cat {STATUS} 2>/dev/null; true')
    lines = out.splitlines()
    status = parse_status('\n'.join(ln for ln in lines if not ln.startswith(('READY=', 'ACTIVE='))))
    return 'READY=1' in lines, 'ACTIVE=1' in lines, status


def describe(status):
    if not status:
        return '本体はまだ補正の設定を一度も読んでいません'
    head = '補正して描いています' if status.get('on') == '1' else '補正せずに描いています'
    return f'本体の録画は{head}（{status.get("msg", "")}、{status.get("at", "")}に読んだ）'


def wait_for(run, done, timeout=WAIT_S):
    t, status = 0.0, {}
    while True:
        _, _, status = device_state(run)
        if done(status) or t >= timeout:
            return status, done(status)
        time.sleep(.5)
        t += .5


def turn_off(run, active, log=print):
    """本体の lens.json を消して、補正しない元の映像に戻す。0：戻った（か、次の録画から戻る）、4：確かめられなかった"""
    run(f'rm -f {REMOTE}')
    log('本体の lens.json を消しました')
    if not active:
        log('録画は今は止まっています。次に録画が始まったときから、補正せずに描きます')
        return 0
    status, ok = wait_for(run, lambda s: s.get('on') == '0' and s.get('size') == '-1')
    log('元の映像（補正なし）に戻りました' if ok else '★戻ったことを確かめられませんでした。\n  ' + describe(status))
    return 0 if ok else 4


def send(run, data, active, log=print):
    """lens.json を本体へ置き、録画が読んだかを確かめる。0：反映された（か、次の録画から）、3：本体が使わなかった、4：確かめられなかった"""
    out = run(f'mkdir -p {REMOTE_DIR} && cat > {REMOTE}.tmp && chmod 644 {REMOTE}.tmp && mv -f {REMOTE}.tmp {REMOTE} && '
              f'if [ "$(id -u)" = 0 ]; then chown -R arduino:arduino {REMOTE_DIR}; fi; stat -c "%i %s" {REMOTE}', data)
    ino, size = out.split()[-2:]
    log(f'本体へ送りました：{REMOTE}（{size}バイト）')
    if not active:
        log('録画は今は止まっています。次に録画が始まったときから、この値で補正して描きます')
        return 0
    status, ok = wait_for(run, lambda s: s.get('ino') == ino and s.get('size') == size)
    if ok and status.get('on') == '1':
        log('反映されました。録画は次のコマから補正して描いています')
        return 0
    if ok:
        log(f'★本体がこの値を使いませんでした（補正せずに描いています）：{status.get("msg")}')
        return 3
    log('★本体が読んだことを確かめられませんでした。\n  ' + describe(status))
    return 4


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('json', nargs='?', default=str(HERE / 'lens.json'))
    ap.add_argument('--off', action='store_true', help='本体から消して、補正しない元の映像に戻す')
    ap.add_argument('--status', action='store_true', help='本体が今どう描いているかを見るだけ')
    ap.add_argument('--adb', action='store_true', help='USBのadbだけでつなぐ（付けなければ USB → テザリングの順に探す）')
    ap.add_argument('--host', default='unoq')
    args = ap.parse_args(argv)

    data = None
    if not args.off and not args.status:
        path = Path(args.json)
        if not path.exists():
            print(f'{path} がありません。Lens-View.cmd で値を決めて s キーで保存してから送ってください')
            return 1
        data = path.read_bytes()
        err = check(data)
        if err:
            print(f'{path.name}：{err}（何も送っていません）')
            return 1
        js = json.loads(data)
        print(f'{path.name}：k1={js["k1"]} k2={js["k2"]} zoom={js["zoom"]} shift=({js["shift_x"]},{js["shift_y"]})。誤りはありません')

    try:
        run = runner(args.adb, args.host)
        ready, active, status = device_state(run)
        if args.status:
            print(f'録画：{"録っている" if active else "止まっている（カメラ待ち等）"}')
            print(describe(status) if ready else '本体の録画は、まだ補正に対応していない版です（補正せずに描いている）')
            return 0
        if not ready:
            print('★本体の録画が、まだ補正に対応していない版です（何も送っていません）。新しい版を入れる必要があります')
            return 2
        if args.off:
            return turn_off(run, active)
        return send(run, data, active)
    except (RuntimeError, subprocess.SubprocessError) as e:
        print(e if type(e).__name__ == 'NoLink' else f'本体でのコマンドが失敗しました：{e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
