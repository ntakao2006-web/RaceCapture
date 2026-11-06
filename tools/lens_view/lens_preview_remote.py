"""PCから、本体のモニターに画角のプレビュー（lens_preview.py）を出す（Lens-Preview.cmd）。

1. lens_preview.py を本体の /home/arduino/ecologger-video/ へ送る
2. 本体に lens.json がまだ無く、PCに tools/lens_view/lens.json（Lens-View.cmd で s 保存したもの）があれば、それを最初の値として送る
3. 本体のモニターにプレビューを出す（閉じるまで待つ。PC側でCtrl+Cでも閉じる＝開いたときの値は残したまま）
4. 閉じたら、本体の lens.json をPCの tools/lens_view/lens.json へ写して控える

つなぎ方は Apply-HUD.cmd と同じ（既定は ssh unoq、--adb でUSBのadb）。
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'video_hud'))
sys.path.insert(0, str(HERE.parent / 'collect_logs'))
from hud_apply import runner  # noqa: E402
from lens_apply import check, device_state  # noqa: E402

REMOTE_DIR = '/home/arduino/ecologger-video'
REMOTE_PY = f'{REMOTE_DIR}/lens_preview.py'
REMOTE_LENS = f'{REMOTE_DIR}/lens.json'
LOCAL_LENS = HERE / 'lens.json'


def head_command(use_adb, host):
    if use_adb:
        from collect_logs import adb_command, list_uno_q_videos
        adb = adb_command()
        serial, _, _ = list_uno_q_videos(adb)
        return [*adb, '-s', serial, 'shell']
    import unoq_ssh  # 名前が引けないときはIPで探す（tools/collect_logs/unoq_ssh.py）
    return unoq_ssh.ssh_cmd(host, '-t', '-o', 'ConnectTimeout=8')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--adb', action='store_true', help='sshでなくUSBのadbでつなぐ')
    ap.add_argument('--host', default='unoq')
    args = ap.parse_args(argv)
    try:
        run = runner(args.adb, args.host)
        ready, active, _ = device_state(run)
        if not ready:
            print('★本体の録画が、まだ補正・プレビューに対応していない版です。先に新しい版を入れる必要があります')
            return 2
        if not active:
            print('（録画が今は止まっています。カメラがつながると、プレビューに絵が出ます）')
        run(f'mkdir -p {REMOTE_DIR} && cat > {REMOTE_PY}.tmp && mv -f {REMOTE_PY}.tmp {REMOTE_PY}',
            (HERE / 'lens_preview.py').read_bytes())
        has = run(f'[ -f {REMOTE_LENS} ] && echo YES || echo NO').strip().endswith('YES')
        if not has and LOCAL_LENS.exists() and not check(LOCAL_LENS.read_bytes()):
            run(f'cat > {REMOTE_LENS}.tmp && mv -f {REMOTE_LENS}.tmp {REMOTE_LENS}', LOCAL_LENS.read_bytes())
            print('PCの lens.json（Lens-View.cmd で保存した値）を、最初の値として本体へ送りました')
        print('本体のモニターにプレビューを出します。終わるときは、モニターの「決定して閉じる」かEnter、やめるときはEsc')
        cmd = f'DISPLAY=:2 python3 {REMOTE_PY}'
        try:
            subprocess.run([*head_command(args.adb, args.host), cmd])
        except KeyboardInterrupt:
            print('PCから閉じました（本体はDASHに戻ります）')
        data = run(f'cat {REMOTE_LENS} 2>/dev/null; true')
        if data.strip():
            LOCAL_LENS.write_text(data, encoding='utf-8')
            print(f'本体の値をPCへ控えました：{LOCAL_LENS}')
        return 0
    except (RuntimeError, subprocess.SubprocessError) as e:
        print(f'本体につながりませんでした：{e}')
        print('（ssh unoq はPixelのテザリングでつながっているときだけ。USBで直接つないだときは --adb）')
        return 1


if __name__ == '__main__':
    sys.exit(main())
