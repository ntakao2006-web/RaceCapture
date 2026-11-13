"""本体（Ver.2、UNO Q）とのつなぎ方を決める、PCの道具の共通の部品（2026-11-13、SP-3-2、`SPEC.md` 6章）。

速い順に **USB（adb）→ テザリング（ssh）** を自分で探し、つながらなければ「なぜ・どう直すか」を返す。
道具ごとに `--adb` を付けたり外したりしなくてよい。LTEは本体でコマンドを動かす道ではないので、
「LTEなら決まった命令だけ送れる」と案内するだけ（確かめるのは `lte_answers()`）。

    import unoq_link
    link = unoq_link.connect()            # 見つからなければ unoq_link.NoLink（str() が理由と直し方）
    out = link.run('uptime')              # sh のスクリプトを本体で動かして標準出力を返す
    link.put(local, remote); link.get(remote, local)
    head = link.argv                      # 自前で subprocess を呼ぶ道具は link.argv(command) を使う

    link, notes = unoq_link.survey()      # 画面に理由を並べたいとき。notes は Note（way・ok・text・fix）の一覧

もとは回収アプリ（tools/video_collect/video_collect.py）の中にあった Link・find_link。そちらからも同じ名前で使える。
"""
import base64
import contextlib
import shlex
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import namedtuple
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

DATA_DIR = '/home/arduino/ecocapture-v2-data'
API_PORT = 8080            # 本体のEcoCapture
PROBE = 'test -d "$D/.." && echo EcoLoggerV2'   # 動画の置き場がある端末＝ロガー

Note = namedtuple('Note', 'way ok text fix')   # way: 'USB'・'テザリング'・'LTE'


def q(s):
    return shlex.quote(str(s))


def find_adb():
    import collect_logs   # adb の置き場の候補はそちらが持っている
    return collect_logs.find_adb()


class Link:
    """本体とのつなぎ（USBのadbか、テザリングのssh）。run は sh のスクリプトを本体で動かして標準出力を返す"""
    kind = ''
    speed = 30e6  # 吸い出しの速さの目安（B/s、待ち時間の上限に使う）

    def __init__(self, root=DATA_DIR, boot_file='/proc/sys/kernel/random/boot_id'):
        self.root, self.boot_file = root, boot_file

    @property
    def video_dir(self):
        return self.root + '/video'

    def prelude(self):
        return f'D={q(self.video_dir)}; LOGS={q(self.root + "/logs")}; BOOTF={q(self.boot_file)}\n'

    def command(self, script):
        """本体で script を動かすときの、こちら側のコマンド（base64で渡すので引用符を気にしなくてよい）"""
        return 'echo ' + base64.b64encode((self.prelude() + script).encode()).decode() + ' | base64 -d | sh'

    def run(self, script, timeout=60):
        r = subprocess.run(self.argv(self.command(script)), capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=timeout)
        if r.returncode:
            raise OSError(f'本体でのコマンドが失敗（{r.returncode}）: {(r.stderr or r.stdout).strip()[:300]}')
        return r.stdout

    def argv(self, command, tty=False):
        """本体で command（シェルの1行）を動かす、こちら側の引数の並び。tty は本体の画面つきの道具を動かすとき"""
        raise NotImplementedError

    def pull_argv(self, remote, local):
        raise NotImplementedError

    def push_argv(self, local, remote):
        raise NotImplementedError

    def get(self, remote, local, timeout=120):
        """本体のファイルをPCへ。取れたら True"""
        return subprocess.run(self.pull_argv(remote, local), capture_output=True, stdin=subprocess.DEVNULL, timeout=timeout).returncode == 0

    def put(self, local, remote, timeout=120):
        """PCのファイルを本体へ。失敗は CalledProcessError"""
        subprocess.run(self.push_argv(local, remote), check=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=timeout)

    def label(self):
        return self.kind

    @contextlib.contextmanager
    def api_url(self):
        """本体のEcoCapture（8080番）へPCから届くURL。走行記録の回収（collect_logs.collect_emmc）が使う"""
        port, close = self.open_forward()
        try:
            url = f'http://127.0.0.1:{port}/'
            end = time.time() + 20
            while True:
                try:
                    with urllib.request.urlopen(url + 'api/status', timeout=3):
                        break
                except (OSError, urllib.error.URLError):
                    if time.time() > end:
                        raise OSError('本体のEcoCaptureに届かない（本体が起動しきっていないかもしれない。少し待ってもう一度）')
                    time.sleep(1)
            yield url
        finally:
            close()

    def open_forward(self):
        raise NotImplementedError


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class AdbLink(Link):
    kind = 'USB'
    speed = 30e6

    def __init__(self, adb, serial, **kw):
        super().__init__(**kw)
        self.adb, self.serial = adb, serial

    def argv(self, command, tty=False):
        return [*self.adb, '-s', self.serial, 'shell', command]

    def pull_argv(self, remote, local):
        return [*self.adb, '-s', self.serial, 'pull', remote, str(local)]

    def push_argv(self, local, remote):
        return [*self.adb, '-s', self.serial, 'push', str(local), remote]

    def label(self):
        return f'USB（{self.serial}）'

    def open_forward(self):
        port = free_port()
        head = [*self.adb, '-s', self.serial, 'forward']
        subprocess.run([*head, f'tcp:{port}', f'tcp:{API_PORT}'], capture_output=True, timeout=15, check=True)
        return port, lambda: subprocess.run([*head, '--remove', f'tcp:{port}'], capture_output=True, timeout=15)


class SshLink(Link):
    kind = 'テザリング'
    speed = 1e6

    def __init__(self, host, **kw):
        super().__init__(**kw)
        self.host = host

    def argv(self, command, tty=False):
        import unoq_ssh  # 名前が引けないときはIPで探す（tools/collect_logs/unoq_ssh.py）
        options = ['-t'] if tty else ['-o', 'BatchMode=yes']
        return [*unoq_ssh.ssh_cmd(self.host, *options, '-o', 'ConnectTimeout=8'), command]

    def pull_argv(self, remote, local):
        import unoq_ssh
        return ['scp', '-q', '-o', 'BatchMode=yes', *unoq_ssh.target_opts(self.host), f'{self.host}:{remote}', str(local)]

    def push_argv(self, local, remote):
        import unoq_ssh
        return ['scp', '-q', '-o', 'BatchMode=yes', *unoq_ssh.target_opts(self.host), str(local), f'{self.host}:{remote}']

    def label(self):
        return f'テザリング（ssh {self.host}、遅いので短い区間だけ）'

    def open_forward(self):
        import unoq_ssh
        port = free_port()
        proc = subprocess.Popen(unoq_ssh.ssh_cmd(self.host, '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes', '-N',
                                                 '-L', f'127.0.0.1:{port}:127.0.0.1:{API_PORT}'),
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def close():
            proc.kill()
            proc.wait()
        return port, close


# ---------------------------------------------------------------- 探す
USB_FIX = ('ケーブルが充電専用でないか確かめて挿し直す。ドックをつないだまま起動した本体はUSBでつながらないので、'
           'ドックを外し、PCとつないだまま本体の電源を入れ直す')
ADB_STATES = {'unauthorized': 'PCからの操作を本体が許していません', 'offline': '機器が返事をしません',
              'no permissions': 'PCに機器を使う権限がありません'}


def usb_devices(adb=None):
    """adb に見えている機器の [(番号, 状態)]。adb が無い・動かないときは None"""
    adb = adb or find_adb()
    if not adb:
        return None
    try:
        lines = subprocess.run([adb, 'devices'], capture_output=True, text=True, timeout=15).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return None
    return [(p[0], ' '.join(p[1:])) for p in (line.split() for line in lines[1:]) if len(p) >= 2]


def usb_ready():
    """USBのadbに、使える機器が出ているか（テザリングの間に、速いUSBへ替えるかを見る。0.1秒ほど）"""
    return any(state == 'device' for _, state in usb_devices() or [])


def survey_usb():
    """(AdbLink か None, Note)"""
    adb = find_adb()
    if not adb:
        return None, Note('USB', False, 'adb がPCに入っていません', 'USBでつなぐなら、adb（Androidのplatform-tools）を入れる')
    devices = usb_devices(adb)
    if devices is None:
        return None, Note('USB', False, 'adb が動きません', 'PCを再起動して、もう一度試す')
    if not devices:
        return None, Note('USB', False, 'USBに機器が見えません', USB_FIX)
    others = []
    for serial, state in devices:
        if state != 'device':
            others.append(f'{serial}：{ADB_STATES.get(state, state)}')
            continue
        link = AdbLink([adb], serial)
        try:
            if 'EcoLoggerV2' in link.run(PROBE, timeout=20):
                return link, Note('USB', True, f'つながりました（{serial}）', '')
            others.append(f'{serial}：ロガーではありません（スマホなど）')
        except OSError:   # 確かめのコマンドが「無い」で終わった＝ロガーの置き場が無い機器
            others.append(f'{serial}：ロガーではありません（スマホなど）')
        except subprocess.SubprocessError as exc:
            others.append(f'{serial}：返事がありません（{type(exc).__name__}）')
    return None, Note('USB', False, 'USBの機器の中にロガーがありません（' + '、'.join(others) + '）', USB_FIX)


def survey_ssh(host):
    """(SshLink か None, Note)"""
    if not shutil.which('ssh'):
        return None, Note('テザリング', False, 'ssh がPCに入っていません', 'Windowsの「OpenSSH クライアント」を入れる')
    import unoq_ssh
    if unoq_ssh._found.get(host, []) is None:
        # unoq_ssh は「1回のプログラムで1回だけ探す」。開きっぱなしの画面では、見つからなかった結果を忘れて探し直す
        unoq_ssh._found.pop(host, None)
    link = SshLink(host)
    try:
        if 'EcoLoggerV2' in link.run(PROBE, timeout=20):
            return link, Note('テザリング', True, f'つながりました（ssh {host}）', '')
        return None, Note('テザリング', False, f'ssh {host} の相手はロガーではありません', '~/.ssh/config の Host の行き先を確かめる')
    except subprocess.TimeoutExpired:
        return None, Note('テザリング', False, f'ssh {host} が返事をしません', 'PCと本体が同じテザリング（Pixel）にいるか、本体の電源を確かめる')
    except (OSError, subprocess.SubprocessError) as exc:
        text = str(exc)
        if 'Permission denied' in text:
            return None, Note('テザリング', False, '本体には届きましたが、鍵が合わず入れません', 'このPCの鍵を本体へ登録する（~/.ssh/config の Host unoq と鍵）')
        if 'Host key verification failed' in text or 'REMOTE HOST IDENTIFICATION' in text:
            return None, Note('テザリング', False, '覚えている本体の鍵と違う機械が返事をしました', '本体を交換したなら、~/.ssh/known_hosts の古い行を消す')
        return None, Note('テザリング', False, f'ssh {host} でつながりません', 'PCと本体が同じテザリング（Pixel）にいるか、本体の電源を確かめる')


def survey(ssh_host='unoq', usb=True):
    """USB → テザリングの順に探す。(Link か None, [Note, ...])。つながった所で止める（遅いほうは試さない）"""
    notes = []
    if usb:
        link, note = survey_usb()
        notes.append(note)
        if link:
            return link, notes
    if ssh_host:
        link, note = survey_ssh(ssh_host)
        notes.append(note)
        if link:
            return link, notes
    return None, notes


def find_link(ssh_host='unoq', log=print):
    """USBでつないだUNO Qを探す。無ければテザリングのssh。見つからなければ None（理由が要るときは survey）"""
    return survey(ssh_host)[0]


class NoLink(RuntimeError):
    """本体につながらなかった。str() は、道ごとの理由と直し方（そのまま画面に出せる）"""

    def __init__(self, notes):
        self.notes = notes
        lines = ['本体につながりませんでした。'] + [f'  {n.way}：{n.text} → {n.fix}' for n in notes if not n.ok]
        lines.append('  LTE：決まった命令（状態を聞く・ラップの操作）だけなら、つながっていなくても送れます（操作メニュー・ピットの表紙）')
        super().__init__('\n'.join(lines))


def connect(use_adb=False, host='unoq'):
    """道具の入口。USB → テザリングの順に探してつなぐ。use_adb（--adb）なら USB だけ。見つからなければ NoLink"""
    link, notes = survey(None if use_adb else host)
    if not link:
        raise NoLink(notes)
    return link


def lte_answers(timeout=20):
    """LTE経由で本体が「状態を聞く」に答えるか。Note を返す（合言葉が無い・返事が無いも Note で）"""
    sys.path.insert(0, str(REPO / 'tools' / 'remote_command'))
    import remote_command_pc as rc
    if not rc.load_local().get('secret'):
        return Note('LTE', False, 'PCに合言葉がありません', '本体をUSBかテザリングでつないで、合言葉の準備（setup）を1回する')
    try:
        result = rc.send('status', timeout=timeout, log=lambda *a: None)
    except (OSError, SystemExit) as exc:
        return Note('LTE', False, f'中継のサーバーへ送れません（{exc}）', 'PCがインターネットにつながっているか確かめる')
    if result is None:
        return Note('LTE', False, '本体から返事がありません', '本体の電源・電波・LTEの送信ONを確かめる')
    if not result.get('ok'):
        return Note('LTE', False, f"本体が断りました（{rc.REFUSED.get(str(result.get('message')), result.get('message'))}）", '合言葉の準備（setup）をやり直す')
    return Note('LTE', True, '本体が答えました（決まった命令だけ送れます）', '')
