"""ピット（PC）からLTE経由でVer.2へ決まった命令を送る（2026-11-06、SUGO向け）。

本体はLTEで自宅の5Bの中継サーバーにつながったままなので、その中継へPCからつなぎ、
`logger.config` に署名つきの命令を載せて送る。本体は EcoCapture-Web/remote_command.py で
署名を確かめて実行し、結果と今の状態を中継経由で返す。中継サーバーは変えていない。

命令は次の7つだけ（シェルは動かせない。設定のうち変えられるのはラップの線だけ）:
    python remote_command_pc.py status          # 状態を聞く（記録・周回・測位など）
    python remote_command_pc.py lap-reset       # ラップを0周に戻す（ラインはそのまま）
    python remote_command_pc.py lap-count 12    # 完了した周回数を12に直す
    python remote_command_pc.py lap-start       # いまから計測を始める（スタートを取り逃したとき）
    python remote_command_pc.py log-start       # 記録を始める（記録が始まっていないとき）
    python remote_command_pc.py course-select sugo   # 本体に入れてあるコースの設定を選ぶ（名前だけ送る。記録は止まらない）
    python remote_command_pc.py line-set sugo        # PCの tools/setups/courses/ の線そのものを送る（ファイルの場所でもよい）

線を変える2つは、走っている間も本体は断らない（SPEC.md 7-5）。本体は変える前の lap.json を1つ控え
（lap.json.bak-remote）、新しい線を次に通った所からラップを数え直し、読み直した線を返事に入れる。
送る前に変わる所を見せて4桁を入れてもらう確認は画面の仕事で、このコマンド行には無い。

はじめに1回だけ、本体をUSB（またはテザリング）でつないで合言葉を作って入れる:
    python remote_command_pc.py setup
    python remote_command_pc.py setup --new     # 合言葉を作り直す（前に渡したスマホからは送れなくなる）

スマホへ合言葉を渡すQRは phone_key.py（Phone-Key.cmd）。

合言葉と中継のURLはPCの %USERPROFILE%\\.ecologger\\remote_command.json と本体の
private/remote_command.json にだけ置く（リポジトリには入れない）。合言葉そのものは送らず、
命令ごとの署名（HMAC-SHA256）だけが流れる。同じ命令は2回効かない。
"""
import argparse
import base64
import json
import os
import secrets
import socket
import ssl
import struct
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'EcoCapture-Web'))
sys.path.insert(0, str(REPO / 'tools' / 'video_collect'))
sys.path.insert(0, str(REPO / 'tools' / 'collect_logs'))
sys.path.insert(0, str(REPO / 'tools' / 'setups'))

from remote_command import sign  # noqa: E402  本体と同じ署名の作り方

# PCの置き場はホームの下。%LOCALAPPDATA% は Claude のアプリから動かしたときだけアプリ専用の場所へ振り替えられ、
# setup をそこで済ませるとデスクトップのショートカットから開いたメニューには合言葉が見えなかった（2026-11-07）
LOCAL = Path.home() / '.ecologger' / 'remote_command.json'
OLD_LOCALS = [Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'EcoLogger' / 'remote_command.json']
DEVICE_PRIVATE = '/home/arduino/ecocapture-v2-data/private'
OPS = {'status': 'status', 'lap-reset': 'lap_reset', 'lap-count': 'lap_count', 'lap-start': 'lap_start', 'log-start': 'log_start',
       'course-select': 'course_select', 'line-set': 'line_set'}
OP_LABEL = {'status': '状態を聞く', 'lap_reset': 'ラップを0周に戻す', 'lap_count': '周回数を直す',
            'lap_start': 'いまから計測を始める', 'log_start': '記録を始める',
            'course_select': 'コースを選ぶ', 'line_set': '線を入れる'}
REFUSED = {'bad signature': '署名が合いません（PCと本体の合言葉が違う。setupをやり直す）',
           'no secret on the logger': '本体に合言葉がありません（setupをする）',
           'already used': 'この命令はもう使われています',
           'too old or from the future': '命令の時刻が本体のGNSSの時刻と10分以上ずれています（PCの時計を確かめる）',
           'no GNSS time yet': '本体がまだ測位していません',
           'a lap is already running': 'すでに計測中です（周回数を直すならlap-count）',
           'no lap line': 'ラップのラインがありません',
           'already logging': 'もう記録中です',
           'bad course name': 'コースの設定の名前が使えません（英小文字・数字・_・- で32文字まで）',
           'bad line': '線の形になっていません',
           'line set': '線を入れました',
           'line was already set': '本体の線はもう同じでした（何も変えていません）',
           'line set, but it could not be read back': '線は入れましたが、本体から読み直せませんでした（statusで確かめる）',
           'the line before the change could not be kept; nothing changed': '変える前の線を本体に控えられなかったので、何も変えていません'}


# ---------------------------------------------------------------- 設定
def load_local():
    for path in (LOCAL, *OLD_LOCALS):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if path != LOCAL:  # 前の置き場にだけあれば、新しい置き場へ移す
            try:
                save_local(data)
            except OSError:
                pass
        return data
    return {}


def save_local(data):
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    LOCAL.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


def setup(log=print, new=False):
    """合言葉を作り（あればそのまま。new なら作り直す）、本体へ入れ、本体が使っている中継のURLを覚える"""
    import video_collect
    link = video_collect.find_link('unoq', log=lambda *a, **k: None)
    if not link:
        raise SystemExit('本体が見つかりません（USBのケーブル、またはPCと本体が同じテザリングにいるか）')
    log(f'本体: {link.label()}')
    local = load_local()
    if new and local.pop('secret', None):
        log('合言葉を作り直します。前の合言葉を渡したスマホからは送れなくなります（QRを渡し直す）')
    local.setdefault('secret', secrets.token_hex(32))
    podium = json.loads(link.run('curl -s -m 8 http://127.0.0.1:8080/api/podium'))['config']
    url = podium.get('server_url')
    if not url:
        raise SystemExit('本体に中継サーバーのURLがありません（LTEの送り先が中継サーバーになっているか）')
    local['url'] = url
    body = json.dumps({'secret': local['secret']})
    link.run(f"umask 077; mkdir -p {DEVICE_PRIVATE}; printf '%s' '{body}' > {DEVICE_PRIVATE}/remote_command.json.tmp"
             f" && mv {DEVICE_PRIVATE}/remote_command.json.tmp {DEVICE_PRIVATE}/remote_command.json"
             f" && ls -l {DEVICE_PRIVATE}/remote_command.json")
    save_local(local)
    log(f'合言葉を本体とPC（{LOCAL}）に入れました。中継: {urlparse(url).hostname}（ルーム {url.rsplit("/", 1)[-1]}）')
    return local


# ---------------------------------------------------------------- 小さなWebSocket
class WebSocket:
    def __init__(self, url, timeout=15):
        u = urlparse(url)
        port = u.port or (443 if u.scheme == 'wss' else 80)
        sock = socket.create_connection((u.hostname, port), timeout=timeout)
        if u.scheme == 'wss':
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=u.hostname)
        self.sock, self.buffer = sock, b''
        key = base64.b64encode(os.urandom(16)).decode()
        path = (u.path or '/') + (f'?{u.query}' if u.query else '')
        sock.sendall((f'GET {path} HTTP/1.1\r\nHost: {u.hostname}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                      f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        while b'\r\n\r\n' not in self.buffer:
            self.buffer += self._recv()
        head, self.buffer = self.buffer.split(b'\r\n\r\n', 1)
        if b' 101 ' not in head.split(b'\r\n', 1)[0]:
            raise OSError('中継サーバーが受け付けませんでした: ' + head.split(b'\r\n', 1)[0].decode(errors='replace'))

    def _recv(self):
        data = self.sock.recv(65536)
        if not data:
            raise OSError('中継サーバーとの接続が切れました')
        return data

    def _frame(self, opcode, payload):
        mask = os.urandom(4)
        n = len(payload)
        head = bytes([0x80 | opcode]) + (bytes([0x80 | n]) if n < 126 else
                                          bytes([0x80 | 126]) + struct.pack('>H', n) if n < 65536 else
                                          bytes([0x80 | 127]) + struct.pack('>Q', n))
        return head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

    def send_json(self, data):
        self.sock.sendall(self._frame(1, json.dumps(data, separators=(',', ':')).encode()))

    def _take(self, n):
        while len(self.buffer) < n:
            self.buffer += self._recv()
        out, self.buffer = self.buffer[:n], self.buffer[n:]
        return out

    def receive(self):
        """次のテキストのフレーム（文字列）。ping には pong を返し、音声などのバイナリは読み捨てる"""
        while True:
            b0, b1 = self._take(2)
            n = b1 & 0x7f
            if n == 126:
                n = struct.unpack('>H', self._take(2))[0]
            elif n == 127:
                n = struct.unpack('>Q', self._take(8))[0]
            mask = self._take(4) if b1 & 0x80 else None
            payload = self._take(n)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            opcode = b0 & 0x0f
            if opcode == 1:
                return payload.decode('utf-8', errors='replace')
            if opcode == 8:
                raise OSError('中継サーバーが接続を閉じました')
            if opcode == 9:
                self.sock.sendall(self._frame(10, payload))

    def close(self):
        try:
            self.sock.sendall(self._frame(8, b''))
            self.sock.close()
        except OSError:
            pass


# ---------------------------------------------------------------- 送る
def make_command(secret, op, arg=None):
    command_id = secrets.token_hex(8)
    t = int(time.time() * 1000)
    return {'id': command_id, 't': t, 'op': op, 'arg': arg, 'sig': sign(secret, command_id, t, op, arg)}


def send(op, arg=None, timeout=30, url=None, log=print):
    """命令を送り、本体の返事（command_result）を返す。返事が来なければ None"""
    local = load_local()
    if not local.get('secret'):
        raise SystemExit('合言葉がありません。本体をUSBでつないで `remote_command_pc.py setup` を1回してください')
    url = url or local.get('url')
    command = make_command(local['secret'], op, arg)
    ws = WebSocket(url)
    try:
        ws.send_json({'type': 'hello', 'client_id': 'ecologger-pit-command', 'protocol': 2, 'audio_formats': []})
        ws.send_json({'type': 'logger.config', 'data': {'command': command}})
        log(f'{OP_LABEL[op]}{arg_label(op, arg)}を送りました。本体の返事を待っています（最大{timeout}秒、LTEだと数秒かかる）…')
        ws.sock.settimeout(2)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                text = ws.receive()
            except (socket.timeout, TimeoutError):
                continue
            try:
                event = json.loads(text)
            except ValueError:
                continue
            result = (event.get('data') or {}).get('command_result') if isinstance(event, dict) and event.get('type') == 'logger.config' else None
            if isinstance(result, dict) and result.get('id') == command['id']:
                return result
        return None
    finally:
        ws.close()


def course_line(source):
    """line-set で送る線。source はPCのコースの設定の名前（tools/setups/courses/）か、ファイルの場所
    （コースの設定、または本体から取った lap.json）。形は本体の lap.json の line と同じ。
    読めない・形が違うものは ValueError"""
    import setups
    if setups.NAME.match(source or ''):
        return dict(setups.load('course', source)['line'])   # 形がおかしければ SetupError（ValueError）
    try:
        data = json.loads(Path(source).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'{source} を読めません（{exc}）')
    line = data.get('line') if isinstance(data, dict) else None
    if not isinstance(line, dict) or line.get('lat') is None or line.get('lon') is None:
        raise ValueError(f'{source} に線（line の lat・lon）がありません')
    return {key: value for key, value in line.items() if key not in ('set_at', 'enabled')}


def arg_label(op, arg):
    """送った中身の短い言い方（線そのものは長いので、場所と本数だけ）"""
    if arg is None:
        return ''
    if op == 'course_select':
        return f"（{arg.get('name')}）"
    if op == 'line_set':
        return f"（コントロールライン {arg.get('lat')}, {arg.get('lon')}・セクターの線{len(arg.get('sectors') or [])}本）"
    return f'（{arg}）'


def describe_message(result):
    """本体の返事の1行（英語の決まり文句）を日本語にする"""
    message = str(result.get('message'))
    if message in REFUSED:
        return REFUSED[message]
    words = message.split()
    if message.startswith('no course '):
        have = result.get('courses') or []
        return f"本体に「{words[2]}」というコースの設定がありません（入っているのは {'・'.join(have) if have else 'なし'}）"
    if message.startswith('course ') and message.endswith(' was already set'):
        return f'本体の線はもう「{words[1]}」でした（何も変えていません）'
    if message.startswith('course ') and message.endswith(' set'):
        return f'コースを「{words[1]}」にしました'
    if message.startswith('course ') and message.endswith(' cannot be read'):
        return f'本体の「{words[1]}」の設定のファイルが読めません（USB・テザリングで入れ直す）'
    if message.startswith('course ') and message.endswith(' is not a course file'):
        return f'本体の「{words[1]}」のファイルがコースの設定の形ではありません（USB・テザリングで入れ直す）'
    if message.startswith('bad line: '):
        return '線の値が本体の決まりの外です（' + message[len('bad line: '):] + '）'
    return message


def describe_line(line):
    """本体から読み直した線（返事の line）を数行にする"""
    def gate(g):
        if not g:
            return 'なし'
        lat, lon, bearing, width = g
        return f"{lat}, {lon}・向き {'通ったときに覚える' if bearing is None else f'{bearing:g}°'}・幅 {width:g} m"
    name = f"「{line['name']}」と同じ" if line.get('name') else '本体に入っているどのコースの設定とも違う'
    out = [f"  本体から読み直した線：コントロールライン {gate(line.get('control'))}・セクターの線 {line.get('sectors')}本"
           f"・スタート {gate(line.get('start'))}・ゴール {gate(line.get('goal'))}",
           f"  設定の名前：{name}（線の番号 {line.get('id')}）"]
    if line.get('changed'):
        out.append('  変える前の線は本体に控えました。走っている途中なら、新しい線を次に通った所からラップを数え直します')
    return out


def describe(result):
    """返事を日本語の数行にする"""
    if result is None:
        return ['★ 返事がありませんでした。本体がLTEで中継につながっていないかもしれません'
                '（電源・電波・本体の送信ON）。命令が届いて効いている場合もあるので、statusで確かめてください']
    op = result.get('op')
    lines = [f"{'OK' if result.get('ok') else '★ できませんでした'}: {OP_LABEL.get(op, op)} — {describe_message(result)}"]
    if isinstance(result.get('line'), dict):
        lines += describe_line(result['line'])
    s = result.get('status')
    if s:
        lap = s.get('lap') or {}
        log_s = s.get('log_s') or 0
        lines.append(f"  記録 {'中 ' + f'{log_s // 60}分' if s.get('logging') else '★止まっている'}"
                     f"・SD {'記録中' if s.get('sd') else '★記録していない'}・受信 {s.get('hz')} Hz"
                     f"・測位 {'あり' if s.get('gnss') else '★なし'}・録画 {'中' if s.get('video') else 'していない'}")
        if lap.get('enabled'):
            race = '' if lap.get('race_min') is None else f"・レース経過 {lap['race_min']}分"
            lines.append(f"  ラップ 完了{lap.get('count')}周・いま{lap.get('current')}周目"
                         f"（{'計測中' if lap.get('running') else '終了' if lap.get('finished') else '★スタート前'}）{race}")
        else:
            lines.append('  ラップ ★ラインがありません')
    return lines


def command_arg(ap, op, value):
    """コマンド行の2つ目の言葉を、命令の引数にする"""
    if op == 'lap-count':
        if value is None or not value.isdigit():
            ap.error('lap-count には周回数が要ります（例: lap-count 12）')
        return int(value)
    if op == 'course-select':
        import setups
        if not setups.NAME.match(value or ''):
            ap.error('course-select には本体に入れてあるコースの設定の名前が要ります（例: course-select sugo）')
        return {'name': value}
    if op == 'line-set':
        if not value:
            ap.error('line-set にはコースの設定の名前かファイルが要ります（例: line-set sugo）')
        try:
            return course_line(value)
        except ValueError as exc:
            ap.error(str(exc))
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('op', choices=['setup', *OPS])
    ap.add_argument('value', nargs='?', help='lap-count は周回数、course-select は本体に入れてあるコースの設定の名前、'
                    'line-set はPCのコースの設定の名前かファイル')
    ap.add_argument('--timeout', type=float, default=30)
    ap.add_argument('--url', help='中継のURL（既定はsetupで覚えたもの）')
    ap.add_argument('--new', action='store_true', help='setup のとき、合言葉を作り直す（渡しすぎた・スマホを無くしたとき）')
    args = ap.parse_args(argv)
    if args.op == 'setup':
        setup(new=args.new)
        return 0
    result = send(OPS[args.op], command_arg(ap, args.op, args.value), args.timeout, args.url)
    for line in describe(result):
        print(line)
    return 0 if result and result.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
