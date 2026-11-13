"""焼き込み録画の露出（明るさの決め方）を見る・切り替える（Exposure.cmd、手順書5-21）。

本体の録画（overlay_rec）は、窓の範囲の明るさを見て自分で露出を決める（own）。合わないときは
カメラ任せ（camera、11/6までと同じ）へ戻せる。明るさの目標（target、既定115）も上げ下げできる。
設定は本体の /home/arduino/ecologger-video/exposure.ini（別の名前で書いてから入れ替える）。
録画は約1秒ごとにこのファイルを見て、変われば次のコマから従う（再起動は要らない）。今の値は exposure.ini.status。

  python exposure_apply.py              # 状態を見てから、番号で選ぶ
  python exposure_apply.py --status     # 見るだけ
  python exposure_apply.py --own        # 録画プログラムが決める
  python exposure_apply.py --camera     # カメラ任せに戻す
  python exposure_apply.py --brighter   # 目標を15明るく（--darker で15暗く）
つなぎ方は Apply-HUD.cmd と同じ（既定は ssh unoq、--adb でUSBのadb）。
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'video_hud'))
sys.path.insert(0, str(HERE.parent / 'collect_logs'))

REMOTE_DIR = '/home/arduino/ecologger-video'
REMOTE = f'{REMOTE_DIR}/exposure.ini'
STATUS = f'{REMOTE}.status'
RECORDER = '/opt/ecologger-video/overlay_rec'
DEFAULT_TARGET = 115  # auto_exposure.h の ae_defaults と同じ
TARGET_RANGE = (40, 200)  # ここでは控えめに（ae_parse は20〜230を受け付ける）
STEP = 15
WAIT_S = 8


def get_value(text, key):
    """exposure.ini の中の key の値（無ければ None）"""
    for line in text.splitlines():
        m = re.match(r'\s*' + re.escape(key) + r'\s*=\s*([^#]*?)\s*(#.*)?$', line)
        if m:
            return m.group(1)
    return None


def set_value(text, key, value):
    """exposure.ini の key の行を書き換える（無ければ末尾に足す）。ほかの行・注釈はそのまま"""
    lines, done = [], False
    for line in text.splitlines():
        if re.match(r'\s*' + re.escape(key) + r'\s*=', line):
            if not done:
                lines.append(f'{key} = {value}')
                done = True
            continue  # 同じ名前が2行あれば1つにする
        lines.append(line)
    if not done:
        lines.append(f'{key} = {value}')
    return '\n'.join(lines) + '\n'


def new_target(text, delta):
    cur = get_value(text, 'target')
    try:
        t = float(cur) if cur is not None else DEFAULT_TARGET
    except ValueError:
        t = DEFAULT_TARGET
    lo, hi = TARGET_RANGE
    return int(min(hi, max(lo, t + delta)))


def parse_status(text):
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)


def describe(st):
    if not st:
        return '本体の録画は、まだ露出の状態を書いていません（新しい版が入っていないか、カメラ待ち）'
    mode = '録画プログラムが決めている（own）' if st.get('mode') == 'own' else 'カメラ任せ（camera）'
    return (f'露出：{mode}　露出時間 {st.get("exposure_ms", "?")}ms・ゲイン {st.get("gain", "?")}'
            f'（範囲 {st.get("gain_range", "?")}）\n'
            f'  窓の範囲の明るさ：平均 {st.get("roi_mean", "?")}・明るい側 {st.get("roi_hi", "?")}'
            f'（{st.get("at", "")}、{st.get("msg", "")}）')


def device_state(run):
    """(新しい版が入っているか, 録画が動いているか, exposure.ini の中身, exposure.ini.status)"""
    out = run(f'if grep -q OVERLAY_EXPOSURE {RECORDER} 2>/dev/null; then echo @@R1; else echo @@R0; fi; '
              f'if pgrep -x overlay_rec >/dev/null; then echo @@A1; else echo @@A0; fi; '
              f'echo @@I; cat {REMOTE} 2>/dev/null; echo @@S; cat {STATUS} 2>/dev/null; true')
    ini = out.split('@@I', 1)[1].split('@@S', 1)[0].strip('\n') if '@@I' in out else ''
    st = parse_status(out.split('@@S', 1)[1]) if '@@S' in out else {}
    return '@@R1' in out, '@@A1' in out, ini, st


def write_ini(run, text):
    out = run(f'mkdir -p {REMOTE_DIR} && cat > {REMOTE}.tmp && chmod 644 {REMOTE}.tmp && mv -f {REMOTE}.tmp {REMOTE} && '
              f'if [ "$(id -u)" = 0 ]; then chown -R arduino:arduino {REMOTE_DIR}; fi; echo ok', text.encode('utf-8'))
    return 'ok' in out


def choose():
    print('\n  1：録画プログラムが決める（own、白飛び対策）')
    print('  2：カメラ任せに戻す（camera、11/6までと同じ）')
    print(f'  3：明るくする（目標 +{STEP}）')
    print(f'  4：暗くする（目標 -{STEP}）')
    print('  何も入れずにEnter：見るだけで終わる')
    return {'1': 'own', '2': 'camera', '3': 'brighter', '4': 'darker'}.get(input('番号：').strip())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    for opt in ('status', 'own', 'camera', 'brighter', 'darker'):
        g.add_argument(f'--{opt}', action='store_true')
    ap.add_argument('--adb', action='store_true', help='USBのadbだけでつなぐ（付けなければ USB → テザリングの順に探す）')
    ap.add_argument('--host', default='unoq')
    args = ap.parse_args(argv)
    try:
        from hud_apply import runner
        run = runner(args.adb, args.host)
        ready, active, ini, st = device_state(run)
        print(f'録画：{"録っている" if active else "止まっている（カメラ待ち等）"}')
        if not ready:
            print('★本体の録画は、まだ露出を決める仕組みが入っていない版です（カメラ任せで録っています）')
            return 2
        print(describe(st))
        print(f'目標の明るさ：{get_value(ini, "target") or f"{DEFAULT_TARGET}（既定）"}')
        action = next((a for a in ('own', 'camera', 'brighter', 'darker') if getattr(args, a)), None)
        if args.status:
            return 0
        if action is None:
            action = choose()
            if action is None:
                return 0
        if action in ('own', 'camera'):
            text = set_value(ini, 'mode', action)
        else:
            # 目標が効くのは own のときだけなので、一緒に own にする
            text = set_value(set_value(ini, 'mode', 'own'), 'target', new_target(ini, STEP if action == 'brighter' else -STEP))
        if not write_ini(run, text):
            print('★本体へ書けませんでした')
            return 3
        print(f'本体へ送りました：{REMOTE}\n' + text.strip().replace('\n', '\n  ').join(['  ', '']))
        if not active:
            print('録画は今は止まっています。次に録画が始まったときから、この設定で録ります')
            return 0
        before = st.get('at')
        for _ in range(WAIT_S * 2):
            time.sleep(.5)
            _, _, _, st = device_state(run)
            if st.get('at') != before and st.get('msg', '').startswith('設定ファイル'):
                break
        print(describe(st))
        if 'の誤り' in st.get('msg', ''):
            return 4
        want = action if action in ('own', 'camera') else 'own'
        if st.get('mode') != want:
            print(f'★まだ {want} になっていません。数秒あとに「見るだけ」でもう一度確かめてください')
            return 4
        print('反映されました')
        return 0
    except (RuntimeError, subprocess.SubprocessError) as e:
        print(e if type(e).__name__ == 'NoLink' else f'本体でのコマンドが失敗しました：{e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
