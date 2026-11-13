"""PCのアプリの「いまの様子」の段（2026-11-13、SP-3-3、`SPEC.md` 4章 P-4・T-4、6章、7-5）。

ロガーが無くてもアプリは開き、ここが裏で本体を探し続ける（USB → テザリング。tools/collect_logs/unoq_link.py）。
つながったら自分で読み始め、記録・測位・SD・録画・LTE を「良い／直す所がある／分からない」で返す。
つながらない間は、道ごとの理由と直し方を返す。LTEだけ届くときは、押したときにだけ「状態を聞く」を送って同じ形で返す。

  checks(status, lap)   本体の /api/status・/api/lap から、合否の一覧を作る（試験しやすいように、読むのと分けてある）
  checks_lte(s)         LTEの「状態を聞く」の返事から、同じ形の一覧を作る
  Watcher(app)          回収アプリ（App）の裏で動く見張り。app.now に結果を置く

本体は読むだけで、何も変えない。回収などの作業の間は読まない（作業のじゃまをしない）。
"""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools' / 'collect_logs'))
sys.path.insert(0, str(REPO / 'tools' / 'remote_command'))
import unoq_link  # noqa: E402

API = 'http://127.0.0.1:8080'
READ_EVERY_S = 8       # つながっている間に読む間隔
SEARCH_EVERY_S = 5     # つながらない間に探す間隔（探すこと自体に数秒〜十数秒かかる）
STATUS_SCRIPT = f'''
echo '@@S'; curl -s -m 6 {API}/api/status
echo; echo '@@L'; curl -s -m 6 {API}/api/lap
echo; echo '@@C'; ls /sys/class/udc 2>/dev/null | wc -l
exit 0
'''


def sections(text):
    """'@@X' で区切られた出力を {'X': 中身} にする"""
    out, key = {}, None
    for line in text.splitlines():
        if line.startswith('@@') and len(line) == 3:
            key = line[2]
            out[key] = []
        elif key:
            out[key].append(line)
    return {k: '\n'.join(v).strip() for k, v in out.items()}


def load_json(text):
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def duration(s):
    s = int(s or 0)
    return f'{s // 3600}時間{s % 3600 // 60:02d}分' if s >= 3600 else f'{s // 60}分{s % 60:02d}秒'


def gib(n):
    return '?' if n is None else f'{n / 2**30:.1f} GiB'


def item(name, state, text, fix=''):
    """state: 'ok'（良い）・'bad'（直す所がある）・'unknown'（分からない）"""
    return {'name': name, 'state': state, 'text': text, 'fix': '' if state == 'ok' else fix}


def checks(status, lap=None):
    """本体の状態から、(合否の一覧, そのほかの行 [(項目, 値)]) を作る"""
    if not status:
        why = '本体のEcoCaptureが答えません'
        fix = '本体が起動しきっていないかもしれません。1分待っても変わらなければ、本体の電源を入れ直す'
        return [item(n, 'unknown', why, fix) for n in ('記録', '測位', 'SDカード', '録画', 'LTE')], []
    sensors, log = status.get('sensors') or {}, status.get('logging') or {}
    video, podium = status.get('video') or {}, status.get('podium') or {}
    hz = status.get('receive_hz') or 0
    out = []
    if not status.get('connected'):
        out.append(item('記録', 'bad', '基板から値が届いていません', '本体の電源を入れ直す。直らなければ、基板（シールド）の差し込みを確かめる'))
    elif not log.get('active'):
        out.append(item('記録', 'bad', '止まっています' + (f"（{log['error']}）" if log.get('error') else ''),
                        '本体の電源を入れ直すと記録が始まります。LTEが届いていれば「記録を始める」も送れます'))
    elif hz < 80:
        out.append(item('記録', 'bad', f"記録中ですが、値が少ない（{hz} Hz。ふつうは100）", '続くようなら、本体の電源を入れ直す'))
    else:
        out.append(item('記録', 'ok', f"記録中 {duration(log.get('elapsed_s'))}（{log.get('name') or '?'}・{hz} Hz）"))
    gnss = str(sensors.get('gnss') or '?')
    out.append(item('測位', 'ok' if gnss == '測位中' else 'bad', gnss,
                    'アンテナの線を確かめる' if gnss == '未受信' else '空の見える所で数分待つ。変わらなければアンテナの線を確かめる'))
    warn = log.get('sd_warning')
    out.append(item('SDカード', 'bad' if warn else 'ok', str(warn or sensors.get('sd') or '?'),
                    'SDカードを挿し直して、本体の電源を入れ直す（走行記録の控えがSDに残りません）'))
    if video.get('recording'):
        left = video.get('minutes_left')
        tight = isinstance(left, (int, float)) and left < 30
        text = f"録画中（カメラ {sensors.get('camera', '?')}・あと約{left if left is not None else '?'}分・未回収 {video.get('uncollected', '?')}本）"
        out.append(item('録画', 'bad' if tight else 'ok', text, '空きが少ないので、回収してから走る（回収済みの動画は本体が古い順に入れ替えます）'))
    else:
        out.append(item('録画', 'bad', f"録画していません（カメラ {sensors.get('camera', '?')}）", 'カメラのUSBを確かめる。ドックは本体の電源を入れる前につなぐ'))
    radio = podium.get('radio') or {}
    signal = f"（電波 RSRP {radio['rsrp']} dBm）" if radio.get('rsrp') is not None else ''
    if not podium.get('enabled'):
        out.append(item('LTE', 'bad', '送信がOFFです', '本体の設定の画面で、送信をONにする'))
    elif podium.get('state') in ('streaming', 'waiting_gps'):
        out.append(item('LTE', 'ok', str(podium.get('message') or '送信中') + signal))
    else:
        out.append(item('LTE', 'bad', str(podium.get('message') or podium.get('state') or '?') + signal,
                        'アンテナとSIMを確かめる。電波の弱い所では、しばらく待つとつながり直します'))
    extra = [('本体の空き', gib(status.get('storage_free_bytes')))]
    if lap:
        line, values = lap.get('line') or {}, lap.get('values') or {}
        extra.insert(0, ('ラップ', f"完了 {values.get('LapCount', '?')}周（線は{'あり' if line.get('enabled') else '★なし'}）"))
    return out, extra


def checks_lte(s):
    """LTEの「状態を聞く」の返事（remote_command.py の status()）から、同じ形の一覧を作る"""
    lap = s.get('lap') or {}
    out = [
        item('記録', 'ok' if s.get('logging') else 'bad', f"記録中 {duration(s.get('log_s'))}（{s.get('hz')} Hz）" if s.get('logging') else '止まっています',
             '「記録を始める」を送る'),
        item('測位', 'ok' if s.get('gnss') else 'bad', '測位中' if s.get('gnss') else '測位していません', '空の見える所で数分待つ'),
        item('SDカード', 'ok' if s.get('sd') else 'bad', '記録中' if s.get('sd') else '記録していません', 'SDカードを挿し直して、本体の電源を入れ直す'),
        item('録画', 'ok' if s.get('video') else 'bad', '録画中' if s.get('video') else '録画していません', 'カメラのUSBを確かめる'),
        item('LTE', 'ok', '本体が答えました'),
    ]
    extra = [('ラップ', f"完了 {lap.get('count')}周・いま{lap.get('current')}周目" if lap.get('enabled') else '★線がありません')]
    return out, extra


def read(link):
    """つないだ本体から読む。{'checks', 'extra', 'usb_hint'}"""
    parts = sections(link.run(STATUS_SCRIPT, timeout=30))
    found, extra = checks(load_json(parts.get('S')), load_json(parts.get('L')))
    hint = ''
    if isinstance(link, unoq_link.SshLink) and parts.get('C', '').strip() == '0':
        # 本体のUSB-Cは、起動したときにドックがあれば「ドックの機器を使う側」になり、あとでPCへつないでも替わらない
        hint = 'この本体は、いまPCとUSBでつなげない状態です（ドックをつないだまま起動したため）。USBで使うには、ドックを外し、PCとつないだまま本体の電源を入れ直す'
    return {'checks': found, 'extra': extra, 'usb_hint': hint}


def note_dict(n):
    return {'way': n.way, 'ok': n.ok, 'text': n.text, 'fix': n.fix}


class Watcher:
    """回収アプリの裏で、本体を探す・読むを続ける。結果は app.now（画面が読む）"""

    def __init__(self, app, survey=None, reader=read, sleep=time.sleep):
        self.app, self.reader, self.sleep = app, reader, sleep
        self.survey = survey or (lambda: unoq_link.survey(app.ssh_host))
        app.now = {'phase': 'searching', 'notes': [], 'checks': [], 'extra': [], 'usb_hint': '', 'read_at': 0, 'via': '', 'lte': None, 'op': None, 'key': None}

    def start(self):
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while True:
            try:
                wait = self.step()
            except Exception as exc:  # noqa: BLE001  見張りは止めない（次の回でやり直す）
                self.app.now.update(phase='searching', notes=[{'way': 'アプリ', 'ok': False, 'text': f'読み取りで失敗しました（{type(exc).__name__}: {exc}）', 'fix': '続くようなら、アプリを開き直す'}])
                wait = SEARCH_EVERY_S
            self.sleep(wait)

    def step(self):
        """1回ぶん。次まで待つ秒数を返す"""
        app, now = self.app, self.app.now
        if app.job and app.job.running:
            now['paused'] = True   # 回収などの間は読まない
            return 2
        now['paused'] = False
        if app.link is not None and isinstance(app.link, unoq_link.SshLink) and unoq_link.usb_ready():
            with app.lock:           # テザリングの間にUSBが見えたら、速いUSBへ替える
                app.link = None
        if app.link is None:
            link, notes = self.survey()
            now['notes'] = [note_dict(n) for n in notes]
            if not link:
                now.update(phase='waiting', checks=[], extra=[], usb_hint='', via='')
                return SEARCH_EVERY_S
            with app.lock:
                app.link = link
                app.refresh()        # 回収の段の一覧も読む
        link = app.link
        if link is None:
            return SEARCH_EVERY_S
        try:
            result = self.reader(link)
        except (OSError, subprocess.SubprocessError) as exc:
            with app.lock:
                if app.link is link:
                    app.link, app.state, app.error = None, None, f'本体を読めなくなった: {exc}'
            now.update(phase='searching', via='')
            return 1
        now.update(phase='connected', via=link.kind, label=link.label(), read_at=time.time(), lte=None, **result)
        return READ_EVERY_S

    def ask_lte(self):
        """LTEで「状態を聞く」を1回送る（画面のボタンから）。結果は app.now['lte']"""
        now = self.app.now
        now['lte'] = {'running': True}
        sys.path.insert(0, str(REPO / 'tools' / 'remote_command'))
        import remote_command_pc as rc
        try:
            if not rc.load_local().get('secret'):
                now['lte'] = {'error': 'PCに合言葉がありません。本体をUSBかテザリングでつないで、合言葉の準備を1回してください'}
                return
            result = rc.send('status', timeout=30, log=lambda *a: None)
        except (OSError, SystemExit) as exc:
            now['lte'] = {'error': f'中継のサーバーへ送れませんでした（{exc}）。PCがインターネットにつながっているか確かめてください'}
            return
        if result is None:
            now['lte'] = {'error': '本体から返事がありません（30秒待ちました）。本体の電源・電波・LTEの送信ONを確かめてください'}
        elif not result.get('ok') or not result.get('status'):
            now['lte'] = {'error': '本体が断りました：' + str(rc.REFUSED.get(str(result.get('message')), result.get('message')))}
        else:
            found, extra = checks_lte(result['status'])
            now['lte'] = {'checks': found, 'extra': extra, 'read_at': time.time()}
