"""走行映像の計器の設定（hud.ini）を本体へ送る（Apply-HUD.cmd）。

送る前にPCで読み、誤りがあれば送らない。本体では /home/arduino/ecologger-video/hud.ini に置く
（いったん別の名前で書いてから入れ替えるので、録画が書きかけを読むことは無い）。録画（overlay_rec）は約1秒ごとに
このファイルを見ていて、書き換わっていれば次のコマから新しい配置で描く。本体が読んだ結果（hud_status.txt）を見て、
新しい配置が使われたかを知らせる。本体で読めなかったときは、本体は前の配置のまま録り続ける。

本体の録画が設定ファイルに対応した版（2026-10-30以降の overlay_rec。/opt/ecologger-video/hud_default.ini がある）で
ないときは、何も送らずに止める（手順書 unoq_video_check_procedure.md 5-14）。針のメーター・弧・コース図・calc.〜 などを
使う設定は、それに対応した版（2026-11-04以降、手順書5-16）でないと送らない。

つなぎ方：既定は ssh unoq（Pixelのテザリング）。--adb でUSBのadb（ドックを外してPCへ直接つないだとき）。
  python hud_apply.py              # hud.ini を送る
  python hud_apply.py 別の.ini
  python hud_apply.py --default    # 自分の配置を本体から消して、元の配置（hud_default.ini）へ戻す
  python hud_apply.py --status     # 本体が今どの配置で描いているかを見るだけ
重さの見積もり（hud_layout.estimate）が「重すぎる」（毎秒30コマを切る）ときは送らない。それでも送るときは --force
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'collect_logs'))
import hud_layout  # noqa: E402

REMOTE_DIR = '/home/arduino/ecologger-video'
REMOTE_INI = f'{REMOTE_DIR}/hud.ini'
STATUS = f'{REMOTE_DIR}/hud_status.txt'
DEFAULT_ON_DEVICE = '/opt/ecologger-video/hud_default.ini'
RECORDER = '/opt/ecologger-video/overlay_rec'
V2_MARK = 'lapref 1'  # 2026-11-04以降の録画プログラム（lap_ref.h のファイルの書式）にある文字
WAIT_S = 8  # 録画は約1秒ごとに見る。カメラの枚数が落ちていると少し遅れる


def runner(use_adb, host):
    """本体でシェルのコマンドを1つ実行して標準出力を返す関数 run(command, data=None)。data は標準入力へ渡す"""
    if use_adb:
        from collect_logs import adb_command, list_uno_q_videos
        adb = adb_command()
        if not adb:
            sys.exit('adbが見つかりません')
        serial, _, _ = list_uno_q_videos(adb)
        if not serial:
            sys.exit('USBでつないだUNO Qが見つかりません（ドックを外してPCへ直接つなぎ、本体を再起動してから）')
        head = [*adb, '-s', serial, 'shell']
    else:
        import unoq_ssh  # 名前が引けないときはIPで探す（tools/collect_logs/unoq_ssh.py）
        head = unoq_ssh.ssh_cmd(host, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8')

    def run(command, data=None):
        done = subprocess.run([*head, command], input=data, capture_output=True, timeout=60)
        out, err = done.stdout.decode('utf-8', 'replace'), done.stderr.decode('utf-8', 'replace')
        if done.returncode:
            raise RuntimeError(f'本体でのコマンドが失敗しました: {err.strip() or out.strip()}')
        return out
    return run


def parse_status(text):
    status = {}
    for line in text.splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            status[k] = v
    return status


def device_state(run):
    """(新しい録画が入っているか, 録画プログラムが録っているか, hud_status.txt の中身, 録画プログラムの版)。
    サービスが動いていても、カメラが無い間は run-video.sh が待っているだけで、録画プログラム（overlay_rec）は動いていない。
    版：2 ＝ 針のメーター・弧・コース図・calc.〜 に対応（2026-11-04以降）、1 ＝ それより前"""
    out = run(f'if [ -f {DEFAULT_ON_DEVICE} ]; then echo READY=1; else echo READY=0; fi; '
              f'if grep -q "{V2_MARK}" {RECORDER} 2>/dev/null; then echo VERSION=2; else echo VERSION=1; fi; '
              f'if pgrep -x overlay_rec >/dev/null; then echo ACTIVE=active; else echo ACTIVE=inactive; fi; '
              f'cat {STATUS} 2>/dev/null; true')
    lines = out.splitlines()
    ready = 'READY=1' in lines
    active = any(ln == 'ACTIVE=active' for ln in lines)
    version = 2 if 'VERSION=2' in lines else 1
    status = parse_status('\n'.join(ln for ln in lines if not ln.startswith(('READY=', 'ACTIVE=', 'VERSION='))))
    return ready, active, status, version


def describe(status):
    if not status:
        return '本体はまだ一度も計器の設定を読んでいません（録画が始まっていない）'
    loaded = status.get('loaded', '')
    which = ('自分の配置（hud.ini）' if loaded == REMOTE_INI else
             '元の配置（hud_default.ini）' if loaded == DEFAULT_ON_DEVICE else loaded or '（無し）')
    text = f'本体の録画は {which} で描いています（計器{status.get("items", "?")}個、{status.get("at", "")}に読んだ）'
    if status.get('error'):
        text += f'\n  ★本体が読めなかったファイルがあります：{status["error"]}'
    return text


def wait_for(run, done, sleep=time.sleep, timeout=WAIT_S):
    """hud_status.txt が done(status) を満たすまで待つ。満たした status、時間切れなら最後の status と False"""
    status, t = {}, 0.0
    while True:
        _, _, status, _ = device_state(run)
        if done(status):
            return status, True
        if t >= timeout:
            return status, False
        sleep(.5)
        t += .5


def push(run, data):
    """hud.ini を書き込み、置いたファイルの (inode, 大きさ) を返す"""
    out = run(f'mkdir -p {REMOTE_DIR} && cat > {REMOTE_INI}.tmp && chmod 644 {REMOTE_INI}.tmp && '
              f'mv -f {REMOTE_INI}.tmp {REMOTE_INI} && '
              f'if [ "$(id -u)" = 0 ]; then chown -R arduino:arduino {REMOTE_DIR}; fi; stat -c "%i %s" {REMOTE_INI}',
              data)
    ino, size = out.split()[-2:]
    return ino, size


def apply(run, data, log=print, sleep=time.sleep, need=1):
    """0：反映された（か、次の録画から反映される）、2：本体が対応していない、3：本体が読めなかった、4：確かめられなかった。
    need：この設定に要る録画プログラムの版（hud_layout.needed_version）"""
    ready, active, _, version = device_state(run)
    if not ready:
        log('★本体の録画プログラムが、まだ計器の設定ファイルに対応していません（何も送っていません）。'
            '新しい版を入れる必要があります（手順書5-14の「本体へ入れる」）')
        return 2
    if version < need:
        log('★この設定は針のメーター・弧・コース図・ベストとの差（calc.〜）などを使っていますが、本体の録画プログラムが'
            'まだ対応していない版です（何も送っていません）。新しい版を入れる必要があります（手順書5-16の「本体へ入れる」）')
        return 2
    ino, size = push(run, data)
    log(f'本体へ送りました：{REMOTE_INI}（{size}バイト）')
    if not active:
        log('録画は今は止まっています（カメラがつながっていない等）。次に録画が始まったときに、この配置で描きます'
            '（PCでの確かめは通っている。本体が読めたかは、録画が始まってから Apply-HUD.cmd --status で見られる）')
        return 0
    # 送ったファイル（inodeと大きさで見分ける）を読めたか、読めなかったかが hud_status.txt に出るまで待つ
    mine = lambda s: s.get('loaded') == REMOTE_INI and s.get('ino') == ino and s.get('size') == size  # noqa: E731
    bad = lambda s: s.get('bad') == REMOTE_INI and s.get('bad_ino') == ino and s.get('bad_size') == size  # noqa: E731
    status, ok = wait_for(run, lambda s: mine(s) or bad(s), sleep)
    if ok and mine(status):
        log(f'反映されました。録画は次のコマから新しい配置で描いています（計器{status.get("items")}個）')
        return 0
    if ok:
        log(f'★本体がこのファイルを読めませんでした（本体は前の配置のまま録っています）：\n  {status["error"]}')
        return 3
    log('★本体が新しい配置を読んだことを確かめられませんでした。')
    log('  ' + describe(status).replace('\n', '\n  '))
    return 4


def back_to_default(run, log=print, sleep=time.sleep):
    ready, active, _, _ = device_state(run)
    if not ready:
        log('★本体の録画プログラムが、まだ計器の設定ファイルに対応していません（何もしていません）')
        return 2
    run(f'rm -f {REMOTE_INI}')
    log('本体の自分の配置（hud.ini）を消しました')
    if not active:
        log('録画は今は動いていません。次に録画が始まったときに、元の配置で描きます')
        return 0
    status, ok = wait_for(run, lambda s: s.get('loaded') == DEFAULT_ON_DEVICE, sleep)
    if ok:
        log('元の配置（hud_default.ini）に戻りました')
        return 0
    log('★元の配置に戻ったことを確かめられませんでした。\n  ' + describe(status))
    return 4


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('ini', nargs='?', default=str(HERE / 'hud.ini'))
    parser.add_argument('--default', action='store_true', help='自分の配置を本体から消して、元の配置へ戻す')
    parser.add_argument('--status', action='store_true', help='本体が今どの配置で描いているかを見るだけ')
    parser.add_argument('--force', action='store_true', help='重さの見積もりが「重すぎる」でも送る')
    parser.add_argument('--adb', action='store_true', help='sshでなくUSBのadbでつなぐ')
    parser.add_argument('--host', default='unoq', help='sshの接続先（既定 unoq）')
    args = parser.parse_args(argv)

    data, need = None, 1
    if not args.default and not args.status:
        path = Path(args.ini)
        try:
            data = path.read_bytes()
            hud = hud_layout.parse(data.decode('utf-8'))
        except FileNotFoundError:
            print(f'{path} が見つかりません')
            return 1
        except UnicodeDecodeError:
            print(f'{path.name} の文字コードがUTF-8ではありません（何も送っていません）')
            return 1
        except hud_layout.HudError as e:
            print(f'{path.name} の {e}（何も送っていません。Preview-HUD.cmd で確かめてから送ってください）')
            return 1
        print(f'{path.name}：計器{len(hud.items)}個・値{len(hud.refs)}種類。誤りはありません')
        need = hud_layout.needed_version(hud)
        screens, ms, level = hud_layout.estimate(hud, hud_layout.load_font())
        print(hud_layout.describe_estimate(screens, ms, level))
        if level == 'heavy' and not args.force:
            print('★重すぎるので送りません（録画が毎秒30コマを切ります）。それでも送るときは --force')
            return 1

    try:
        run = runner(args.adb, args.host)
        if args.status:
            ready, active, status, version = device_state(run)
            print(f'録画：{"録っている" if active else "止まっている（カメラ待ち等）"}'
                  f'（録画プログラムは{"針のメーター・コース図に対応した版" if version >= 2 else "針のメーター・コース図に未対応の版"}）')
            if not ready:
                print('本体の録画プログラムは、まだ計器の設定ファイルに対応していない版です（元の配置で描いている）')
            else:  # 止まっているときの hud_status.txt は、最後に録画したときのもの
                print(('' if active else '最後に録画したときの記録：') + describe(status))
            return 0
        if args.default:
            return back_to_default(run)
        return apply(run, data, need=need)
    except (RuntimeError, subprocess.SubprocessError) as e:
        print(f'本体につながりませんでした：{e}')
        print('（ssh unoq はPixelのテザリングでつながっているときだけ。USBで直接つないだときは --adb）')
        return 1


if __name__ == '__main__':
    sys.exit(main())
