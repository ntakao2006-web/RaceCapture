"""PCのアプリの「いまの様子」に載せる操作（2026-11-13、SP-3-4、`SPEC.md` 4章 T-3、7-5）。

  ラップを0周に戻す      つながっている（USB・テザリング）ときは本体へ直接。つながっていないときはLTEで
  LTEの命令              状態を聞く・ラップを0周に戻す・周回数を直す・いまから計測を始める・記録を始める
  合言葉の準備・作り直し  本体がつながっているときだけ（PCと本体に同じ合言葉を入れる）
  スマホへ合言葉を渡す    QRの絵を作って画面へ渡す（合言葉そのものは画面へ渡さない）

操作の決まり（7-5）：
  - 1つずつ動かし、進み具合（何を・どの道で・最大何秒）と結果を app.now['op'] に置く。画面は同じバーで出す
  - 変えたあとは、本体から読み直した値を結果に入れる（「送りました」だけで終わらせない）
  - 使えないときは黙って断らず、理由と「どうすれば使えるか」を返す（Refused）
"""
import json
import shlex
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools' / 'remote_command'))
sys.path.insert(0, str(REPO / 'tools' / 'collect_logs'))

API = 'http://127.0.0.1:8080'
LTE_WAIT_S = 30
KEY_SHOW_S = 120          # QRを画面に出しておく長さ（出しっぱなしにしない）
LTE_OPS = ('status', 'lap_reset', 'lap_count', 'lap_start', 'log_start')
NEED_SETUP = 'PCに合言葉がありません。本体をUSBかテザリングでつないで、下の「合言葉の準備」を1回してください'


class Refused(RuntimeError):
    """いまは使えない。str() が理由と、どうすれば使えるか"""


def rc():
    import remote_command_pc
    return remote_command_pc


def device_api(link, path, body=None, wait=15):
    """本体のEcoCaptureのAPIを本体の中から呼ぶ（tools/sugo_setup/sugo_setup.py の api と同じ送り方）"""
    command = f'curl -s -m {wait} -w "\\n%{{http_code}}" {API}{path}'
    if body is not None:  # 書き込みはEcoCaptureの操作ヘッダーが要る
        command += (" -X POST -H 'X-EcoCapture: 1' -H 'Content-Type: application/json'"
                    f" --data-binary {shlex.quote(json.dumps(body))}")
    text, _, code = link.run(command, timeout=wait + 15).rstrip().rpartition('\n')
    if code != '200':
        raise OSError(f'{path}: HTTP {code} {text[:200]}')
    return json.loads(text)


def lap_line(lap):
    values, line = lap.get('values') or {}, lap.get('line') or {}
    return f"本体から読み直した値：完了 {values.get('LapCount', '?')}周（線は{'あり' if line.get('enabled') else '★なし'}）"


class Ops:
    def __init__(self, app):
        self.app = app
        self.lock = threading.Lock()

    # ---- 共通
    def begin(self, name, via, seconds):
        """操作を1つ始める（ほかが動いていれば断る）"""
        app = self.app
        with self.lock:
            if (app.now.get('op') or {}).get('running'):
                raise Refused('ほかの操作の返事を待っている途中です。終わってからもう一度押してください')
            if app.job and app.job.running:
                raise Refused('回収などの作業の途中です。終わってから（または「止める」を押してから）もう一度押してください')
            app.now['op'] = {'running': True, 'name': name, 'via': via, 'started': time.time(), 'seconds': seconds}

    def finish(self, ok, lines):
        op = self.app.now.get('op') or {}
        self.app.now['op'] = {**op, 'running': False, 'ok': ok, 'lines': lines, 'ended': time.time()}

    def background(self, work):
        def run():
            try:
                ok, lines = work()
            except Exception as exc:  # noqa: BLE001  画面に出す
                ok, lines = False, [f'失敗しました：{exc}']
            except SystemExit as exc:  # 道具が理由つきで止まったとき
                ok, lines = False, [str(exc)]
            self.finish(ok, lines)
        threading.Thread(target=run, daemon=True).start()

    def connected_link(self):
        app = self.app
        return app.link if app.now.get('phase') == 'connected' and app.link is not None else None

    # ---- ラップ・LTE
    def lap_reset(self):
        """ラップを0周に戻す。つながっていれば直接、いなければLTE"""
        link = self.connected_link()
        if link is None:
            return self.lte('lap_reset')
        self.begin('ラップを0周に戻す', link.kind, 20)

        def work():
            device_api(link, '/api/lap/reset', {})
            return True, ['ラップの記録を消して、0周に戻しました（線はそのまま）。', lap_line(device_api(link, '/api/lap'))]
        self.background(work)

    def lte(self, op, arg=None):
        if op not in LTE_OPS:
            raise Refused(f'知らない命令です：{op}')
        if op == 'lap_count' and not (isinstance(arg, int) and 0 <= arg <= 999):
            raise Refused('周回数は0〜999の数字で入れてください')
        cmd = rc()
        if not cmd.load_local().get('secret'):
            raise Refused(NEED_SETUP)
        label = cmd.OP_LABEL[op] + ('' if arg is None else f'（{arg}周）')
        self.begin(label, 'LTE', LTE_WAIT_S)

        def work():
            result = cmd.send(op, arg if op == 'lap_count' else None, timeout=LTE_WAIT_S, log=lambda *a: None)
            lines = cmd.describe(result)
            if result and result.get('status'):   # 読み直した値を「LTEで聞いた様子」にも出す
                import now_status
                found, extra = now_status.checks_lte(result['status'])
                self.app.now['lte'] = {'checks': found, 'extra': extra, 'read_at': time.time()}
            return bool(result and result.get('ok')), lines
        self.background(work)

    # ---- 合言葉
    def setup(self, new=False):
        link = self.connected_link()
        if link is None:
            raise Refused('合言葉の準備は、本体がUSBかテザリングでつながっているときにできます（PCと本体の両方に同じ合言葉を入れるため）。本体をつないでから、もう一度押してください')
        self.begin('合言葉を作り直す' if new else '合言葉の準備', link.kind, 30)

        def work():
            lines = []
            cmd = rc()
            # remote_command_pc.setup は自分で本体を探す。ここでは、いまつながっている道をそのまま使わせる
            import video_collect
            original, video_collect.find_link = video_collect.find_link, lambda *a, **k: link
            try:
                cmd.setup(log=lines.append, new=new)
            finally:
                video_collect.find_link = original
            if new:
                lines.append('前の合言葉を渡したスマホからは送れなくなりました。「スマホへ合言葉を渡す」でQRを読み直してください')
            return True, lines
        self.background(work)

    def phone_key(self):
        """QRの絵を app.now['key'] に置く（合言葉・アドレスそのものは置かない）"""
        import phone_key
        import qr
        local = rc().load_local()
        try:
            matrix, where = qr.make(phone_key.pair_url(local).encode()), phone_key.describe(local)
        except ValueError as exc:
            raise Refused(str(exc).replace('`remote_command_pc.py setup` を1回する', '下の「合言葉の準備」を1回する'))
        self.app.now['key'] = {'matrix': [''.join(map(str, row)) for row in matrix], 'where': where, 'until': time.time() + KEY_SHOW_S}

    def hide_key(self):
        self.app.now['key'] = None

    def expire(self):
        """時間の過ぎたQRを消す（画面が読むたびに呼ぶ）"""
        key = self.app.now.get('key')
        if key and time.time() > key['until']:
            self.app.now['key'] = None

    # ---- 画面から
    def action(self, path, body):
        """/api/op/… を受ける。知らない道は KeyError"""
        if path == '/api/op/lap_reset':
            self.lap_reset()
        elif path == '/api/op/lte':
            self.lte(str(body.get('op')), body.get('arg'))
        elif path == '/api/op/setup':
            self.setup(new=bool(body.get('new')))
        elif path == '/api/op/phone_key':
            self.phone_key()
        elif path == '/api/op/hide_key':
            self.hide_key()
        else:
            raise KeyError(path)
