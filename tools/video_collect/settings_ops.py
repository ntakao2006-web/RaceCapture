"""PCのアプリの「設定」の段：焼き込みの見た目を1画面で見る・変える・前へ戻す（2026-11-13、SP-3-8、`SPEC.md` 4章 S-1、7-5）。

  見る      本体のいまの中身を読む（段を開いたときと「読み直す」を押したときだけ。8秒ごとの見張りには足さない）。
            本体がつながっていなくても、PCにある設定のファイル（tools/video_hud/hud.ini・tools/lens_view/lens.json）は見られる
  変える    いまの道具の関数をそのまま呼ぶ（別のプロセスは起こさない）。道具が print で出す文は受け取って画面へ出す
              計器の配置  hud_apply.apply・back_to_default（重すぎる配置は送らない、の決まりもそのまま）
              レンズ      lens_apply.send・turn_off
              露出        exposure_apply.change（白飛び対策／カメラ任せ／明るく／暗く）
              音          本体の audio.ini の項目を書き換える（run-video.sh が録画の起動時に読む。手順書5-23）
              針の補間    本体の smooth_ms・telemetry_hz（数字1つのファイル。同じく録画の起動時に読む。手順書5-24）
  前へ戻す  送る前に、本体のいまのファイルを本体の prev/ へ1つだけ控える（無かったときは「無かった」の印を置く）。
            「前の値へ戻す」は、控えといまを入れ替える（もう一度押すと、戻す前に戻る）
  開く      PCで絵を見る道具・本体のモニターでレンズを決める道具は、別の窓で開くだけ（操作メニューの launch と同じ）

本体のファイルはどれも /home/arduino/ecologger-video/ にある（録画のソフト tools/unoq_overlay_enc/run-video.sh が決めている）：
  hud.ini・hud_status.txt      計器の配置と、録画が読んだ結果（録画中も約1秒ごとに見る）
  lens.json・lens.json.status  レンズ（同じ）
  exposure.ini・exposure.ini.status  露出（同じ）
  audio.ini・audio_off・audio  音（録画の起動時だけ読む＝書いても、次に録画が始まるまで効かない）
  smooth_ms・telemetry_hz      針の補間（同じく起動時だけ）
  prev/                        このアプリが置く控え（録画のソフトは見ない）

録画・カメラを止める操作は無い。音と針の補間は「次に録画が始まったとき（本体の電源を入れ直したとき）から効く」と画面に出す
（録画の入れ直しは root の作業で、このアプリからはしない）。

操作の決まり（7-5）は app_ops.Ops の begin・finish・background をそのまま使う：同じバー、送ったあと本体から読み直した値、
使えないときは理由と直し方（Refused）。
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from app_ops import Refused

REPO = Path(__file__).resolve().parents[2]
HUD_DIR, LENS_DIR, EXPO_DIR = REPO / 'tools' / 'video_hud', REPO / 'tools' / 'lens_view', REPO / 'tools' / 'video_exposure'
for _dir in (HUD_DIR, LENS_DIR, EXPO_DIR, REPO / 'tools' / 'collect_logs'):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

PC_HUD = HUD_DIR / 'hud.ini'
PC_LENS = LENS_DIR / 'lens.json'
PC_HUD_DEFAULT = REPO / 'tools' / 'unoq_overlay_enc' / 'hud_default.ini'   # 本体の元の配置と同じはずのもの（重さの目安に使う）

REMOTE = '/home/arduino/ecologger-video'
PREV = 'prev'                       # 控えの置き場（REMOTE の中）
OWNER = f'if [ "$(id -u)" = 0 ]; then chown -R arduino:arduino {REMOTE}; fi'   # いまの道具と同じ（USBはrootで入るため）

# まとまりごとの、本体のファイル（控える・戻すはこの単位）
GROUPS = {'hud': ('hud.ini',), 'lens': ('lens.json',), 'exposure': ('exposure.ini',), 'audio': ('audio.ini',),
          'smooth': ('smooth_ms', 'telemetry_hz')}
NAMES = {'hud': '計器の配置', 'lens': 'レンズ', 'exposure': '露出', 'audio': '音', 'smooth': '針の補間'}
ALL_FILES = tuple(f for files in GROUPS.values() for f in files)

# 音（run-video.sh の既定。書いていない項目はこの値で録る）と、このアプリで入れられる範囲
AUDIO_DEFAULTS = {'mic_volume': '-15dB', 'mic_agc': '', 'highpass_hz': '100', 'gain_db': '0', 'limiter': '1'}
AUDIO_LABELS = {'mic_volume': 'マイクの音量', 'mic_agc': 'カメラの自動の音量調整', 'highpass_hz': '低音カット',
                'gain_db': '録画で足す音量', 'limiter': 'リミッター'}
MIC_DB = (-95, 0)          # 本体のカメラ（ELP）のマイクは −95〜0dB（手順書5-23）
HIGHPASS_HZ = (0, 1000)    # 録画のソフトは12000未満を受け付ける。ここでは低音カットとして意味のある所まで
GAIN_DB = (-40, 20)        # 録画のソフトに上限は無い。ここでは控えめに
# 針の補間（overlay_rec.c の既定と受け付ける範囲）
SMOOTH_DEFAULT, HZ_DEFAULT = 150, 25
SMOOTH_MS = (0, 300)       # 0で補間しない。300は針が景色より遅れた（手順書5-24）ので、ここまで
TELEMETRY_HZ = (1, 100)    # overlay_rec.c が 1〜100 に丸める
LATER = '効くのは、次に録画が始まったとき（本体の電源を入れ直したとき）からです。いまの録画は、始まったときの値のままです。'
NO_LINK = ('本体がつながっていないので{what}。本体をUSBかテザリングでつないで、上の帯が「つながっています」になってから、'
           'もう一度押してください（焼き込みの設定は、LTEでは送れません）')

# 別の窓で開く道具：(名前, .cmd, 要るPythonの部品, 本体が要るか)
TOOLS = {
    'hud_preview': ('計器の配置をPCで見る', HUD_DIR / 'Preview-HUD.cmd', ('PIL', 'numpy'), False),
    'lens_view': ('レンズをPCで見る', LENS_DIR / 'Lens-View.cmd', ('cv2', 'numpy'), False),
    'lens_preview': ('レンズを本体のモニターで決める', LENS_DIR / 'Lens-Preview.cmd', (), True),
}
PIP_NAMES = {'PIL': 'pillow', 'cv2': 'opencv-python', 'numpy': 'numpy'}


def tools():
    """いまの道具（関数を呼ぶ）。(hud_apply, hud_layout, lens_apply, exposure_apply)"""
    import exposure_apply
    import hud_apply
    import hud_layout
    import lens_apply
    return hud_apply, hud_layout, lens_apply, exposure_apply


def make_run(link):
    """つないでいる本体でコマンドを1つ動かす関数 run(command, data=None)。いまの道具の runner が作るものと同じ形"""
    def run(command, data=None):
        done = subprocess.run(link.argv(command), input=data, capture_output=True, timeout=60)
        out, err = done.stdout.decode('utf-8', 'replace'), done.stderr.decode('utf-8', 'replace')
        if done.returncode:
            raise RuntimeError(f'本体でのコマンドが失敗しました: {err.strip() or out.strip()}')
        return out.replace('\r\n', '\n')
    return run


def launch(path, args):
    """道具の .cmd を新しい窓で開く（tools/ecologger_menu/ecologger_menu.py の launch と同じやり方）"""
    subprocess.Popen(['cmd', '/c', str(path), *args], cwd=str(path.parent), creationflags=subprocess.CREATE_NEW_CONSOLE)


def missing_parts(parts):
    """このPCのPythonに入っていない部品（中へは読み込まず、あるかだけ見る）"""
    return [p for p in parts if importlib.util.find_spec(p) is None]


# ---------------------------------------------------------------- 本体で動かすコマンド（1行。いまの道具と同じ書き方）
def read_command():
    """本体の設定のファイルと控えを、まとめて読む"""
    files = ' '.join((*ALL_FILES, 'audio', *(f'{PREV}/{f}' for f in ALL_FILES)))
    marks = ' '.join(('audio_off', *(f'{PREV}/{f}.none' for f in ALL_FILES)))
    return (f'cd {REMOTE} 2>/dev/null || {{ echo @@NODIR; echo @@END; exit 0; }}; '
            f'for f in {files}; do if [ -f $f ]; then echo "@@F $f $(stat -c %Y $f)"; cat $f; echo; fi; done; '
            f'for f in {marks}; do if [ -e $f ]; then echo "@@N $f $(stat -c %Y $f)"; fi; done; echo @@END')


def parse_read(out):
    """read_command の出力 → ({ファイル名: (中身, 時刻)}, {印の名前: 時刻})。終わりの印が無ければ ValueError"""
    if '@@END' not in out:
        raise ValueError('本体からの返事が途中で切れました')
    files, marks, name, body = {}, {}, None, []

    def close():
        if name is not None:
            files[name[0]] = ('\n'.join(body), name[1])
    for line in out.replace('\r\n', '\n').split('\n'):
        if line.startswith('@@'):
            close()
            name, body = None, []
            parts = line.split()
            if parts[0] == '@@F' and len(parts) >= 3:
                name = (parts[1], int(parts[2]) if parts[2].isdigit() else 0)
            elif parts[0] == '@@N' and len(parts) >= 3:
                marks[parts[1]] = int(parts[2]) if parts[2].isdigit() else 0
            elif parts[0] == '@@END':
                break
        elif name is not None:
            body.append(line)
    return files, marks


def keep_command(files):
    """送る前に、いまのファイルを控える（1世代。前の控えは捨てる）。無いファイルは「無かった」の印を置く"""
    names = ' '.join(files)
    return (f'mkdir -p {REMOTE}/{PREV} && cd {REMOTE} && for f in {names}; do rm -f {PREV}/$f {PREV}/$f.none; '
            f'if [ -f $f ]; then cp $f {PREV}/$f || exit 1; else : > {PREV}/$f.none || exit 1; fi; done; {OWNER}; echo KEPT')


def have_command(files):
    """控えがあるか（HAVE か NOPREV）"""
    names = ' '.join(files)
    return (f'cd {REMOTE} 2>/dev/null || {{ echo NOPREV; exit 0; }}; for f in {names}; do '
            f'if [ ! -e {PREV}/$f ] && [ ! -e {PREV}/$f.none ]; then echo NOPREV; exit 0; fi; done; echo HAVE')


def swap_command(files):
    """控えといまを入れ替える（＝前の値へ戻す。もう一度すると、戻す前に戻る）。
    いまのファイルは別の名前で書いてから入れ替える（録画が書きかけを読まない）。出力：ファイルごとに「@@S 名前 inode 大きさ」
    （戻した結果ファイルが無くなったときは「@@S 名前 -」）、最後に SWAPPED。控えが無ければ NOPREV（何も変えない）"""
    names = ' '.join(files)
    return (f'cd {REMOTE} 2>/dev/null || {{ echo NOPREV; exit 0; }}; for f in {names}; do '
            f'if [ ! -e {PREV}/$f ] && [ ! -e {PREV}/$f.none ]; then echo NOPREV; exit 0; fi; done; '
            f'for f in {names}; do rm -f {PREV}/$f.new {PREV}/$f.new.none; '
            f'if [ -f $f ]; then cp $f {PREV}/$f.new || exit 1; else : > {PREV}/$f.new.none || exit 1; fi; '
            f'if [ -f {PREV}/$f ]; then cp {PREV}/$f $f.tmp && chmod 644 $f.tmp && mv -f $f.tmp $f || exit 1; else rm -f $f; fi; '
            f'rm -f {PREV}/$f {PREV}/$f.none; '
            f'if [ -f {PREV}/$f.new ]; then mv {PREV}/$f.new {PREV}/$f; else mv {PREV}/$f.new.none {PREV}/$f.none; fi; done; {OWNER}; '
            f'for f in {names}; do if [ -f $f ]; then echo "@@S $f $(stat -c "%i %s" $f)"; else echo "@@S $f -"; fi; done; echo SWAPPED')


def write_command(name):
    """標準入力の中身を、本体の設定のファイル name へ書く（別の名前で書いてから入れ替える）"""
    path = f'{REMOTE}/{name}'
    return f'mkdir -p {REMOTE} && cat > {path}.tmp && chmod 644 {path}.tmp && mv -f {path}.tmp {path} && {OWNER}; echo ok'


# ---------------------------------------------------------------- 値の確かめ（音・針の補間）
def number(text, lo, hi, what, whole=False):
    """範囲の中の数を、書く形（文字）にして返す。だめなら ValueError（どう入れればよいかつき）"""
    try:
        value = float(str(text).strip())
    except ValueError:
        raise ValueError(f'{what}は、{lo}〜{hi}の数字で入れてください（入っていたもの：{text!r}）')
    if value != value or not lo <= value <= hi or (whole and value != int(value)):
        raise ValueError(f'{what}は、{lo}〜{hi}の{"整数" if whole else "数字"}で入れてください（入っていたもの：{text!r}）')
    return f'{value:g}'


def clean_audio(values):
    """画面から来た音の値 → audio.ini へ書く {項目: 文字}。来ていない項目は入れない（＝変えない）"""
    out = {}
    if values.get('mic_volume') not in (None, ''):
        text = str(values['mic_volume']).strip().replace('ｄＢ', 'dB')
        m = re.fullmatch(r'(-?\d+(?:\.\d+)?)\s*(?:dB|db|DB)?', text)
        if not m:
            raise ValueError(f'マイクの音量は、-15 や -21 のようにdBの数字で入れてください（入っていたもの：{text!r}）')
        out['mic_volume'] = number(m.group(1), *MIC_DB, 'マイクの音量（dB）') + 'dB'
    if values.get('highpass_hz') not in (None, ''):
        out['highpass_hz'] = number(values['highpass_hz'], *HIGHPASS_HZ, '低音カット（Hz）')
    if values.get('gain_db') not in (None, ''):
        out['gain_db'] = number(values['gain_db'], *GAIN_DB, '録画で足す音量（dB）')
    if values.get('limiter') not in (None, ''):
        if str(values['limiter']) not in ('0', '1'):
            raise ValueError('リミッターは、入れる（1）か切る（0）で選んでください')
        out['limiter'] = str(values['limiter'])
    if not out:
        raise ValueError('変える値がありません。欄の値を変えてから押してください')
    return out


def clean_smooth(values):
    """画面から来た針の補間の値 → {ファイル名: 文字}"""
    out = {}
    if values.get('smooth_ms') not in (None, ''):
        out['smooth_ms'] = number(values['smooth_ms'], *SMOOTH_MS, '値を待つ長さ（ミリ秒）')
    if values.get('telemetry_hz') not in (None, ''):
        out['telemetry_hz'] = number(values['telemetry_hz'], *TELEMETRY_HZ, '走行データを読む回数（1秒あたり）')
    if not out:
        raise ValueError('変える値がありません。欄の値を変えてから押してください')
    return out


# ---------------------------------------------------------------- 見せる文を作る
def hud_summary(data):
    """hud.ini の中身 → {'ok', 'items', 'level', 'lines'}（PCの道具 hud_apply.py が送る前に出すものと同じ確かめ）"""
    _, hud_layout, _, _ = tools()
    try:
        hud = hud_layout.parse(data.decode('utf-8') if isinstance(data, bytes) else data)
    except UnicodeDecodeError:
        return {'ok': False, 'lines': ['文字コードがUTF-8ではありません']}
    except hud_layout.HudError as exc:
        return {'ok': False, 'lines': [f'誤りがあります：{exc}']}
    screens, ms, level = hud_layout.estimate(hud, hud_layout.load_font())
    return {'ok': True, 'items': len(hud.items), 'level': level, 'need': hud_layout.needed_version(hud),
            'lines': [f'計器{len(hud.items)}個・値{len(hud.refs)}種類。誤りはありません', '重さ：' + hud_layout.describe_estimate(screens, ms, level)]}


def lens_text(js):
    return f"k1={js.get('k1')}　k2={js.get('k2')}　ズーム={js.get('zoom')}　ずらし=({js.get('shift_x')}, {js.get('shift_y')})"


def lens_summary(data):
    _, _, lens_apply, _ = tools()
    err = lens_apply.check(data if isinstance(data, bytes) else data.encode('utf-8'))
    if err:
        return {'ok': False, 'lines': [f'誤りがあります：{err}']}
    js = json.loads(data)
    return {'ok': True, 'lines': [lens_text(js) + (f"（{js['saved_at']}に決めた値）" if js.get('saved_at') else '')]}


def stamp(t):
    return f'{datetime.fromtimestamp(t):%m/%d %H:%M}' if t else '?'


def same_text(a, b):
    """改行の違い（Windowsで保存したファイルの CR）だけなら同じとみなす"""
    def norm(x):
        return (x.decode('utf-8', 'replace') if isinstance(x, bytes) else x).replace('\r', '').rstrip('\n')
    return norm(a) == norm(b)


def pc_view():
    """PCにある設定のファイルと、別の窓で開く道具が使えるか。本体が無くても出せる"""
    out = {'hud': {'path': str(PC_HUD), 'lines': []}, 'lens': {'path': str(PC_LENS), 'lines': []}, 'tools': {}}
    try:
        info = hud_summary(PC_HUD.read_bytes())
        out['hud'].update(ok=info['ok'], level=info.get('level'), lines=info['lines'], saved=stamp(PC_HUD.stat().st_mtime))
    except OSError:
        out['hud'].update(ok=False, lines=['PCに hud.ini がありません'])
    try:
        info = lens_summary(PC_LENS.read_bytes())
        out['lens'].update(ok=info['ok'], lines=info['lines'])
    except OSError:
        out['lens'].update(ok=False, lines=['PCに lens.json がまだありません（「レンズをPCで見る」か「本体のモニターで決める」で決めると出来ます）'])
    for key, (label, path, parts, need_link) in TOOLS.items():
        lack = missing_parts(parts)
        out['tools'][key] = {'label': label, 'lack': [PIP_NAMES[p] for p in lack], 'need_link': need_link}
    return out


def prev_text(group, files, marks):
    """控えの説明（無ければ ''）"""
    _, _, _, exposure_apply = tools()
    names = GROUPS[group]
    have = [f for f in names if f'{PREV}/{f}' in files]
    none = [f for f in names if f'{PREV}/{f}.none' in marks]
    if len(have) + len(none) < len(names):
        return ''
    at = max([files[f'{PREV}/{f}'][1] for f in have] + [marks[f'{PREV}/{f}.none'] for f in none])
    head = f'控えがあります（本体の時計で {stamp(at)} に、送る前の値を控えた）：'
    if group == 'hud':
        if not have:
            return head + '自分の配置は無く、元の配置でした'
        info = hud_summary(files[f'{PREV}/hud.ini'][0])
        return head + (f"計器{info['items']}個の自分の配置" if info['ok'] else '自分の配置（PCでは読めない中身）')
    if group == 'lens':
        if not have:
            return head + 'レンズの値は無く、補正なしでした'
        try:
            return head + lens_text(json.loads(files[f'{PREV}/lens.json'][0]))
        except ValueError:
            return head + 'レンズの値（PCでは読めない中身）'
    if group == 'exposure':
        if not have:
            return head + '設定のファイルは無く、既定（録画プログラムが決める・目標115）でした'
        ini = files[f'{PREV}/exposure.ini'][0]
        mode = exposure_apply.get_value(ini, 'mode') or 'own'
        return head + f"{'カメラ任せ' if mode == 'camera' else '録画プログラムが決める'}・目標 {exposure_apply.get_value(ini, 'target') or '115（既定）'}"
    if group == 'audio':
        if not have:
            return head + '音の設定のファイルは無く、どれも既定でした'
        return head + '、'.join(audio_lines(files[f'{PREV}/audio.ini'][0], short=True))
    values = {f: (files[f'{PREV}/{f}'][0].strip() if f in have else None) for f in names}
    return head + f"値を待つ長さ {values['smooth_ms'] or f'{SMOOTH_DEFAULT}（既定）'} ミリ秒・読む回数 {values['telemetry_hz'] or f'{HZ_DEFAULT}（既定）'} 回"


def audio_values(ini):
    """audio.ini の中身 → {項目: (値, 既定のままか)}（run-video.sh と同じ読み方：書いていない項目は既定）"""
    _, _, _, exposure_apply = tools()
    out = {}
    for key, default in AUDIO_DEFAULTS.items():
        value = exposure_apply.get_value(ini or '', key)
        out[key] = (default, True) if value is None else (value, False)
    return out


def audio_lines(ini, short=False):
    v = audio_values(ini)
    mark = lambda key: '（既定）' if v[key][1] else ''  # noqa: E731
    lines = [f"マイクの音量 {v['mic_volume'][0] or '触らない'}{mark('mic_volume')}",
             f"低音カット {v['highpass_hz'][0]} Hz{mark('highpass_hz')}" + ('' if short or v['highpass_hz'][0] != '0' else '（削らない）'),
             f"録画で足す音量 {v['gain_db'][0]} dB{mark('gain_db')}",
             f"リミッター {'入' if v['limiter'][0] != '0' else '切'}{mark('limiter')}"]
    if v['mic_agc'][0]:
        lines.append(f"カメラの自動の音量調整 {v['mic_agc'][0]}")
    return lines


def device_view(run):
    """本体のいまの中身を読んで、まとまりごとの見せる文にする"""
    hud_apply, _, lens_apply, exposure_apply = tools()
    files, marks = parse_read(run(read_command()))
    hud_ready, active, hud_status, version = hud_apply.device_state(run)
    lens_ready, _, lens_status = lens_apply.device_state(run)
    expo_ready, _, expo_ini, expo_status = exposure_apply.device_state(run)
    text = lambda name: files[name][0] if name in files else None  # noqa: E731
    past = '' if active else '最後に録画したときの記録：'
    out = {'recording': active}

    # 計器の配置
    lines, own = [], text('hud.ini')
    if not hud_ready:
        lines.append('★本体の録画プログラムは、まだ計器の設定ファイルに対応していない版です（元の配置で描いています）')
    else:
        lines.append(past + hud_apply.describe(hud_status))
    which = ('own' if hud_status.get('loaded') == hud_apply.REMOTE_INI else
             'default' if hud_status.get('loaded') == hud_apply.DEFAULT_ON_DEVICE else '')
    weight = None
    if own is not None:
        info = hud_summary(own)
        weight = info.get('level')
        lines.append('本体にある自分の配置（hud.ini）：' + '　'.join(info['lines']))
    else:
        lines.append('本体に自分の配置（hud.ini）はありません（元の配置で描きます）')
        try:
            info = hud_summary(PC_HUD_DEFAULT.read_bytes())
            weight = info.get('level')
            lines.append('元の配置（PCにある hud_default.ini で見積もり）：' + '　'.join(info['lines']))
        except OSError:
            pass
    same = None
    try:
        same = own is not None and same_text(own, PC_HUD.read_bytes())
        lines.append('PCの hud.ini と同じ中身です' if same else 'PCの hud.ini とは違う中身です' if own is not None else '')
    except OSError:
        pass
    out['hud'] = {'ready': hud_ready, 'which': which, 'file': own is not None, 'same_as_pc': same, 'level': weight,
                  'version': hud_apply.VERSION_NAMES[min(version, 3)], 'lines': [ln for ln in lines if ln],
                  'prev': prev_text('hud', files, marks)}

    # レンズ
    lines, own = [], text('lens.json')
    lines.append(past + lens_apply.describe(lens_status) if lens_ready
                 else '★本体の録画は、まだ補正に対応していない版です（補正せずに描いています）')
    same = None
    if own is not None:
        try:
            lines.append('本体にあるレンズの値（lens.json）：' + lens_text(json.loads(own)))
        except ValueError:
            lines.append('本体にあるレンズの値（lens.json）は、PCでは読めない中身です')
        try:
            same = same_text(own, PC_LENS.read_bytes())
            lines.append('PCの lens.json と同じ中身です' if same else 'PCの lens.json とは違う中身です')
        except OSError:
            pass
    else:
        lines.append('本体にレンズの値（lens.json）はありません（補正なし）')
    out['lens'] = {'ready': lens_ready, 'file': own is not None, 'same_as_pc': same, 'lines': lines, 'prev': prev_text('lens', files, marks)}

    # 露出
    lines = []
    if not expo_ready:
        lines.append('★本体の録画は、まだ露出を決める仕組みが入っていない版です（カメラ任せで録っています）')
    else:
        lines += (past + exposure_apply.describe(expo_status)).split('\n  ')
    target = exposure_apply.get_value(expo_ini, 'target')
    mode = exposure_apply.get_value(expo_ini, 'mode')
    wanted = 'camera' if mode == 'camera' else 'own'   # 設定のファイルが決めている決め方（書いていなければ own）
    lines.append('設定のファイル（exposure.ini）：' + ('ありません（既定の値）' if text('exposure.ini') is None else
                                              ('カメラ任せ' if wanted == 'camera' else '録画プログラムが決める')
                                              + f"・目標の明るさ {target or f'{exposure_apply.DEFAULT_TARGET}（既定）'}"))
    if not active and expo_ready and expo_status.get('mode') not in (None, wanted):
        lines.append('録画が止まっているので、上の記録は前の決め方のままです。次に録画が始まったときから、設定のファイルに従います')
    out['exposure'] = {'ready': expo_ready, 'mode': wanted, 'target': target, 'lines': lines,
                       'prev': prev_text('exposure', files, marks)}

    # 音
    ini = text('audio.ini')
    lines = audio_lines(ini)
    lines.append('本体に音の設定のファイル（audio.ini）はありません（どれも既定）' if ini is None else '')
    if 'audio_off' in marks:
        lines.append('★音は録らない設定になっています（本体に audio_off というファイルがある）')
    if text('audio'):
        lines.append(f"マイクは、決め打ちの名前を使います：{text('audio').strip()}")
    lines.append('ここに出しているのは設定のファイルの中身です。録画は、始まったときに読んだ値で録っています。')
    v = audio_values(ini)
    out['audio'] = {'file': ini is not None, 'lines': [ln for ln in lines if ln], 'prev': prev_text('audio', files, marks),
                    'values': {'mic_volume': v['mic_volume'][0], 'highpass_hz': v['highpass_hz'][0], 'gain_db': v['gain_db'][0],
                               'limiter': '0' if v['limiter'][0] == '0' else '1'}}

    # 針の補間
    ms, hz = text('smooth_ms'), text('telemetry_hz')
    ms, hz = (ms or '').strip() or None, (hz or '').strip() or None
    lines = [f"値を待つ長さの上限：{ms or f'{SMOOTH_DEFAULT}（既定。ファイルなし）'} ミリ秒" + ('（補間しない）' if ms == '0' else ''),
             f"走行データを読む回数：{hz or f'{HZ_DEFAULT}（既定。ファイルなし）'} 回／秒",
             'ここに出しているのは設定のファイルの中身です。録画は、始まったときに読んだ値で描いています。']
    out['smooth'] = {'lines': lines, 'prev': prev_text('smooth', files, marks),
                     'values': {'smooth_ms': ms or str(SMOOTH_DEFAULT), 'telemetry_hz': hz or str(HZ_DEFAULT)}}
    return out


class Settings:
    """「設定」の段の操作。ops は app_ops.Ops（同じバー・1つずつ動かす決まりを使う）"""

    def __init__(self, ops, sleep=time.sleep):
        self.ops, self.app, self.sleep = ops, ops.app, sleep

    # ---- 共通
    def link_or_refuse(self, what):
        link = self.ops.connected_link()
        if link is None:
            raise Refused(NO_LINK.format(what=what))
        return link

    def read(self, link=None):
        """PCの設定と、つながっていれば本体のいまの中身。app.now['settings'] にも置く（画面はそこから描く）"""
        link = link if link is not None else self.ops.connected_link()
        view = {'read_at': time.time(), 'connected': link is not None, 'via': link.kind if link is not None else '',
                'pc': pc_view(), 'device': None, 'error': ''}
        if link is None:
            view['error'] = '本体がつながっていないので読めません（PCにある設定のファイルは下に出しています）'
        else:
            try:
                view['device'] = device_view(make_run(link))
            except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
                view['error'] = f'本体から読めませんでした（{exc}）。少し待って「読み直す」を押してください'
        self.app.now['settings'] = view
        return view

    def start(self, group, name, seconds, work, link=None):
        """本体を変える操作を1つ始める。work(run, log) → うまくいったか。終わったら読み直した値を結果に足す"""
        link = link if link is not None else self.link_or_refuse(f'{NAMES[group]}を変えられません')
        self.ops.begin(name, link.kind, seconds)
        self.app.now['op']['kind'] = 'settings'

        def body():
            lines = []
            ok = bool(work(make_run(link), lambda text: lines.extend(str(text).splitlines())))   # 道具の文は行ごとに
            view = self.read(link)
            if view['device'] is None:
                return False, lines + ['★' + view['error']]
            part = view['device'][group]
            return ok, lines + ['本体から読み直した値：'] + ['　' + ln for ln in part['lines']] + ([part['prev']] if part['prev'] else [])
        self.ops.background(body)

    def keep(self, run, log, group):
        """送る前の値を控える。控えられなければ RuntimeError（＝何も変えずに終わる）"""
        try:
            done = 'KEPT' in run(keep_command(GROUPS[group]))
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f'送る前の値を本体に控えられなかったので、何も変えていません（{exc}）')
        if not done:
            raise RuntimeError('送る前の値を本体に控えられなかったので、何も変えていません')
        log(f'送る前の値を、本体の {REMOTE}/{PREV}/ に控えました（「前の値へ戻す」で戻せます）')

    # ---- 計器の配置
    def hud(self, what):
        hud_apply, hud_layout, _, _ = tools()
        if what == 'default':
            def work(run, log):
                ready, _, _, _ = hud_apply.device_state(run)
                if ready and 'yes' not in run(f'[ -f {hud_apply.REMOTE_INI} ] && echo yes; true'):
                    log('本体に自分の配置はありません。もう元の配置です（何も変えていません）')
                    return True
                if ready:
                    self.keep(run, log, 'hud')
                return hud_apply.back_to_default(run, log=log, sleep=self.sleep) == 0
            return self.start('hud', '計器を元の配置へ戻す', 20, work)
        if what != 'send':
            raise KeyError(what)
        try:
            data = PC_HUD.read_bytes()
        except OSError:
            raise Refused(f'PCに {PC_HUD.name} がありません（{PC_HUD.parent}）')
        info = hud_summary(data)
        if not info['ok']:
            raise Refused(f"送っていません。PCの hud.ini に{info['lines'][0]}。「計器の配置をPCで見る」で確かめて直してから、もう一度押してください")
        if info['level'] == 'heavy':
            raise Refused('送っていません。この配置は重すぎます（録画が毎秒30コマを切ります）。' + info['lines'][1]
                                    + '。大きな四角や後ろに敷く四角を小さく・少なくしてから、もう一度押してください')

        def work(run, log):
            log('PCの hud.ini：' + '　'.join(info['lines']))
            ready, _, _, version = hud_apply.device_state(run)
            if ready and version >= info['need']:   # 送らずに止まる場合（本体の版が古い）は、控えも取らない
                if same_text(run(f'cat {hud_apply.REMOTE_INI} 2>/dev/null; true'), data):
                    log('本体の自分の配置は、もうPCの hud.ini と同じ中身です（何も変えていません）')
                    return True
                self.keep(run, log, 'hud')
            code = hud_apply.apply(run, data, log=log, sleep=self.sleep, need=info['need'])
            if code == 3:
                log('「前の値へ戻す」で、送る前の配置へ戻せます')
            return code == 0
        self.start('hud', '計器の配置を本体へ送る', 25, work)

    # ---- レンズ
    def lens(self, what):
        _, _, lens_apply, _ = tools()
        if what not in ('send', 'off'):
            raise KeyError(what)
        data = None
        if what == 'send':
            try:
                data = PC_LENS.read_bytes()
            except OSError:
                raise Refused('PCに lens.json がまだありません。「レンズをPCで見る」か「レンズを本体のモニターで決める」で値を決めてから、もう一度押してください')
            err = lens_apply.check(data)
            if err:
                raise Refused(f'送っていません。PCの lens.json：{err}')

        def work(run, log):
            ready, active, _ = lens_apply.device_state(run)
            if not ready:
                log('★本体の録画が、まだ補正に対応していない版です（何も送っていません）。新しい版を入れる必要があります')
                return False
            now = run(f'cat {lens_apply.REMOTE} 2>/dev/null; true')
            if what == 'off':
                if not now.strip():
                    log('本体にレンズの値はありません。もう補正なしです（何も変えていません）')
                    return True
                self.keep(run, log, 'lens')
                return lens_apply.turn_off(run, active, log=log) == 0
            if same_text(now, data):
                log('本体のレンズの値は、もうPCの lens.json と同じ中身です（何も変えていません）')
                return True
            log('PCの lens.json：' + lens_text(json.loads(data)))
            self.keep(run, log, 'lens')
            return lens_apply.send(run, data, active, log=log) == 0
        self.start('lens', 'レンズの値を本体へ送る' if what == 'send' else 'レンズの補正をやめる', 25, work)

    # ---- 露出
    def exposure(self, what):
        _, _, _, exposure_apply = tools()
        labels = {'own': '露出を、録画プログラムが決める（白飛び対策）にする', 'camera': '露出を、カメラ任せにする',
                  'brighter': '露出の目標を明るくする', 'darker': '露出の目標を暗くする'}
        if what not in labels:
            raise KeyError(what)

        def work(run, log):
            ready, active, ini, st = exposure_apply.device_state(run)
            if not ready:
                log('★本体の録画は、まだ露出を決める仕組みが入っていない版です（何も送っていません）')
                return False
            if what in ('own', 'camera') and exposure_apply.get_value(ini, 'mode') == what:
                log('本体の露出の設定は、もうその決め方です（何も変えていません）')
                return True
            if what in ('brighter', 'darker'):
                lo, hi = exposure_apply.TARGET_RANGE
                step = exposure_apply.STEP if what == 'brighter' else -exposure_apply.STEP
                if exposure_apply.get_value(ini, 'mode') == 'own' and str(exposure_apply.new_target(ini, step)) == exposure_apply.get_value(ini, 'target'):
                    log(f'目標の明るさは、もう{"上" if step > 0 else "下"}の端です（{lo}〜{hi}。何も変えていません）')
                    return True
            self.keep(run, log, 'exposure')
            return exposure_apply.change(run, what, active, ini, st, log=log, sleep=self.sleep) == 0
        self.start('exposure', labels[what], 25, work)

    # ---- 音・針の補間（録画の起動時に読むファイルを書くだけ）
    def audio(self, values):
        _, _, _, exposure_apply = tools()
        try:
            new = clean_audio(values or {})
        except ValueError as exc:
            raise Refused(f'送っていません。{exc}')

        def work(run, log):
            path = f'{REMOTE}/audio.ini'
            now = run(f'cat {path} 2>/dev/null; true')
            text = now
            for key, value in new.items():
                text = exposure_apply.set_value(text, key, value)
            if same_text(now, text):
                log('本体の音の設定は、もうその値です（何も変えていません）')
                return True
            self.keep(run, log, 'audio')
            if 'ok' not in run(write_command('audio.ini'), text.encode('utf-8')):
                log('★本体へ書けませんでした')
                return False
            log('本体の audio.ini に書きました：' + '、'.join(f'{AUDIO_LABELS[k]} {v}' for k, v in new.items()))
            log(LATER)
            return True
        self.start('audio', '音の設定を本体へ書く', 20, work)

    def smooth(self, values):
        try:
            new = clean_smooth(values or {})
        except ValueError as exc:
            raise Refused(f'送っていません。{exc}')

        def work(run, log):
            now = {name: run(f'cat {REMOTE}/{name} 2>/dev/null; true').strip() for name in new}
            change = {name: value for name, value in new.items() if now[name] != value}
            if not change:
                log('本体の針の補間の設定は、もうその値です（何も変えていません）')
                return True
            self.keep(run, log, 'smooth')
            for name, value in change.items():
                if 'ok' not in run(write_command(name), (value + '\n').encode()):
                    log(f'★本体へ書けませんでした（{name}）')
                    return False
            log('本体に書きました：' + '、'.join(f'{name} = {value}' for name, value in change.items()))
            log(LATER)
            return True
        self.start('smooth', '針の補間の設定を本体へ書く', 20, work)

    # ---- 前へ戻す
    def restore(self, group):
        if group not in GROUPS:
            raise KeyError(group)
        hud_apply, _, lens_apply, exposure_apply = tools()
        link = self.link_or_refuse(f'{NAMES[group]}を前の値へ戻せません')
        if (self.app.now.get('op') or {}).get('running'):
            raise Refused('ほかの操作の返事を待っている途中です。終わってからもう一度押してください')
        try:
            have = 'HAVE' in make_run(link)(have_command(GROUPS[group]))
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            raise Refused(f'本体の控えを確かめられませんでした（{exc}）。少し待って、もう一度押してください')
        if not have:
            raise Refused(f'{NAMES[group]}は、まだ控えがありません。控えは、このアプリから送る・変えるたびに、変える前の値を1つだけ本体に残します')

        def work(run, log):
            before = exposure_apply.device_state(run)[3].get('at') if group == 'exposure' else None
            out = run(swap_command(GROUPS[group]))
            if 'SWAPPED' not in out:
                log('まだ控えがありません（何も変えていません）' if 'NOPREV' in out else '★本体で入れ替えられませんでした')
                return False
            log('控えていた前の値を、本体へ入れ直しました（いままでの値は、代わりに控えました。もう一度押すと、戻す前に戻ります）')
            now = {}   # 入れ直したあとのファイル：{名前: (inode, 大きさ) か None}
            for line in out.splitlines():
                parts = line.split()
                if parts[:1] == ['@@S'] and len(parts) >= 3:
                    now[parts[1]] = (parts[2], parts[3]) if len(parts) >= 4 else None
            if group in ('audio', 'smooth'):
                log(LATER)
                return True
            if group == 'hud':
                _, active, _, _ = hud_apply.device_state(run)
                if not active:
                    log('録画は今は止まっています。次に録画が始まったときに、戻した配置で描きます')
                    return True
                at = now.get('hud.ini')
                if at is None:
                    status, ok = hud_apply.wait_for(run, lambda s: s.get('loaded') == hud_apply.DEFAULT_ON_DEVICE, self.sleep)
                    log('録画は、元の配置で描いています' if ok else '★元の配置に戻ったことを確かめられませんでした')
                    return ok
                mine = lambda s: s.get('loaded') == hud_apply.REMOTE_INI and (s.get('ino'), s.get('size')) == at  # noqa: E731
                bad = lambda s: s.get('bad') == hud_apply.REMOTE_INI and (s.get('bad_ino'), s.get('bad_size')) == at  # noqa: E731
                status, ok = hud_apply.wait_for(run, lambda s: mine(s) or bad(s), self.sleep)
                if ok and mine(status):
                    log(f'録画は、戻した配置で描いています（計器{status.get("items")}個）')
                    return True
                log(f'★本体が戻した配置を読めませんでした：{status.get("error")}' if ok else '★本体が戻した配置を読んだことを確かめられませんでした')
                return False
            if group == 'lens':
                _, active, _ = lens_apply.device_state(run)
                if not active:
                    log('録画は今は止まっています。次に録画が始まったときから、戻した値で描きます')
                    return True
                at = now.get('lens.json')
                done = (lambda s: s.get('on') == '0' and s.get('size') == '-1') if at is None else (lambda s: (s.get('ino'), s.get('size')) == at)
                status, ok = self.wait(lambda: lens_apply.device_state(run)[2], done)
                log(('録画は、戻した値で' + ('補正して描いています' if status.get('on') == '1' else '補正せずに描いています')) if ok
                    else '★本体が戻した値を読んだことを確かめられませんでした')
                return ok
            _, active, ini, st = exposure_apply.device_state(run)   # 露出
            if not active:
                log('録画は今は止まっています。次に録画が始まったときから、戻した設定で録ります')
                return True
            want = exposure_apply.get_value(ini, 'mode') or 'own'
            st, ok = self.wait(lambda: exposure_apply.device_state(run)[3],
                               lambda s: s.get('at') != before and s.get('mode') == want and 'の誤り' not in s.get('msg', ''))
            log('録画は、戻した設定で録っています' if ok else '★本体が戻した設定に従ったことを確かめられませんでした。数秒あとに「読み直す」で確かめてください')
            return ok
        self.start(group, f'{NAMES[group]}を前の値へ戻す', 25, work, link)

    def wait(self, read, done, timeout=8):
        """read() が done を満たすまで待つ。(最後に読んだもの, 満たしたか)"""
        t = 0.0
        while True:
            status = read()
            if done(status) or t >= timeout:
                return status, bool(done(status))
            self.sleep(.5)
            t += .5

    # ---- 別の窓で開く道具
    def open(self, tool):
        if tool not in TOOLS:
            raise KeyError(tool)
        label, path, parts, need_link = TOOLS[tool]
        if os.name != 'nt':
            raise Refused(f'「{label}」は、Windowsでだけ開けます')
        lack = missing_parts(parts)
        if lack:
            names = ' '.join(PIP_NAMES[p] for p in lack)
            raise Refused(f'「{label}」は、このPCのPythonに {names} が入っていないので開けません。'
                                    f'入れるには、黒い窓（コマンド プロンプト）で python -m pip install {names} と打ちます')
        args = []
        if need_link:
            link = self.link_or_refuse(f'「{label}」を開けません（本体のモニターに絵を出す道具です）')
            args = ['--adb'] if link.kind == 'USB' else []
        launch(path, args)
        return {'opened': f'「{label}」を別の窓で開きました。' + ('決めた値は、閉じたときにPCの lens.json へ写ります。' if tool == 'lens_preview' else
                                                    's キーで保存すると、PCの lens.json が変わります。' if tool == 'lens_view' else
                                                    'hud.ini を保存するたびに描き直します。')}

    # ---- 画面から
    def action(self, path, body):
        """/api/op/set_… を受ける。知らない道は KeyError"""
        what = path[len('/api/op/set_'):]
        if what == 'read':
            if (self.app.now.get('op') or {}).get('running'):
                raise Refused('操作の途中です。終わると、読み直した値が出ます')
            self.read()
            return {}
        if what == 'open':
            return self.open(str(body.get('tool')))
        if what == 'hud':
            return self.hud(str(body.get('what')))
        if what == 'lens':
            return self.lens(str(body.get('what')))
        if what == 'exposure':
            return self.exposure(str(body.get('what')))
        if what == 'audio':
            return self.audio(body.get('values'))
        if what == 'smooth':
            return self.smooth(body.get('values'))
        if what == 'restore':
            return self.restore(str(body.get('group')))
        raise KeyError(path)

