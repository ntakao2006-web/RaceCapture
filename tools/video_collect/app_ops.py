"""PCのアプリの「いまの様子」に載せる操作（2026-11-13、SP-3-4、`SPEC.md` 4章 T-3、7-5）。

  ラップを0周に戻す      つながっている（USB・テザリング）ときは本体へ直接。つながっていないときはLTEで
  LTEの命令              状態を聞く・ラップを0周に戻す・周回数を直す・いまから計測を始める・記録を始める
  合言葉の準備・作り直し  本体がつながっているときだけ（PCと本体に同じ合言葉を入れる）
  スマホへ合言葉を渡す    QRの絵を作って画面へ渡す（合言葉そのものは画面へ渡さない）
  線を入れる（「コースと線」の段。2026-11-13、SP-4-10・SP-4-11）
                          つながっているときは本体へ直接（入れる前の線を本体に控え、入れたあと読み直す）。
                          つながっていないときはLTEで（線まるごと line_set か、本体に入れてある設定の名前だけ course_select）。
                          断らない。LTEのときと、車がそのコースのレーシングスピード以上のときは、画面で4桁の確認を
                          済ませてから（confirmed）でないと送らない。形のおかしい線は、どこがおかしいかを返して送らない

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
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools' / 'remote_command'))
sys.path.insert(0, str(REPO / 'tools' / 'collect_logs'))

API = 'http://127.0.0.1:8080'
LTE_WAIT_S = 30
KEY_SHOW_S = 120          # QRを画面に出しておく長さ（出しっぱなしにしない）
LINE_WAIT_S = 40          # 直接、線を入れるときの最大（控える・送る・読み直す）
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

    # ---- コースと線
    def line_from(self, body):
        """画面から来た線を、送る形にして確かめる。(線, おかしい所の一覧)"""
        import course_lines as cl
        if body.get('by_name'):   # 名前だけ送るときは、PCにある同じ名前の設定の線を「送る線」として扱う
            course = cl.course(str(body['by_name']))
            if not course:
                raise Refused(f"PCに「{body['by_name']}」というコースの設定がありません")
            return cl.clean(course['line']), []
        try:
            line = cl.clean(body.get('line'))
        except ValueError as exc:
            return None, [str(exc)]
        return line, cl.problems(line)

    def line_read(self, link):
        """送る直前に、本体のいまの線と車速を読む。(本体の /api/lap, 車速 km/h か None)"""
        import course_lines as cl
        try:
            lap = device_api(link, '/api/lap')
        except (OSError, ValueError) as exc:
            raise Refused(f'本体のいまの線を読めませんでした（{exc}）。少し待って、もう一度押してください')
        try:
            telemetry = device_api(link, '/api/telemetry')
        except (OSError, ValueError):
            telemetry = None   # 車速が分からないときは、止まっているものとして扱う（SPEC.md 7-5）
        return lap, cl.speed(telemetry)

    def line_plan(self, body):
        """送る前の確認に出すもの。本体へは何も送らない（直接のときは、いまの線と車速を読むだけ）。
        形がおかしければ {'problems': [...]}。そうでなければ
        {'via', 'direct', 'need_code', 'title', 'changes', 'same', 'notes', 'by_name'}"""
        import course_lines as cl
        line, bad = self.line_from(body)
        if bad:
            return {'problems': bad}
        link = self.connected_link()
        notes, by_name = [], None
        if link is not None:
            lap, v = self.line_read(link)
            now = lap.get('line') or {}
            limit, why = cl.racing_kmh(cl.match(now), body.get('course'))
            found, sector_changed = cl.changes(now, line)
            need = v is not None and v >= limit
            title = (f'走行中（{v:.0f} km/h）に線を変えます。変わる所を確かめてください。' if need
                     else f'{link.kind}で、本体へ線を入れます。変わる所を確かめてください。')
            if v is None:
                notes.append('車速が分かりません（測位していない・値が届いていない）。止まっているものとして扱います。')
            elif need:
                notes.append(f'レーシングスピード以上で走っているので、確認の数字を入れてから送ります（{why}）。')
            elif v >= 1:
                notes.append(f'車は動いています（{v:.0f} km/h）。')
            if lap.get('running') and cl.lines_moved(now, line):
                notes.append('★いま1周を数えている途中です。USB・テザリングから変えると、いまの本体のソフトは走っている周を捨てないので、'
                             'この1周だけ、古い線から新しい線までのタイムになります（次の周からは新しい線で数えます。'
                             'LTEで送ったときは、走っている周を捨てて、新しい線を次に通った所から数え直します）。')
            notes.append('入れる前の線は、本体に控えます。入れたあと、本体から読み直して図と数字を出します。')
        else:
            if not rc().load_local().get('secret'):
                raise Refused(NEED_SETUP)
            known = self.app.now.get('course') or {}
            need, title = True, 'LTEで線を変えます。変わる所を確かめてください。'
            if known.get('line'):
                found, sector_changed = cl.changes(known['line'], line)
                found = found or ['最後に分かっている本体の線と同じです（本体がいまも同じなら、何も変わりません）']
                notes.append('本体のいまの線は、LTEでは読めません。変わる所は、最後に分かっている本体の線'
                             f"（{datetime.fromtimestamp(known['read_at']):%H:%M}）と比べています。")
            else:
                found, sector_changed = cl.describe(line), False
                notes.append('本体のいまの線は、LTEでは読めません。上は「送る線」です（本体から読み直した線は、送ったあとの返事に出ます）。')
            notes.append('LTEで送ります。ロガーが走っているかどうかはここからは分からないので、確認の数字を入れてから送ります。')
            notes.append('走っている途中で変えたときは、新しい線を次に通った所からラップを数え直します。変える前の線は、本体に控えます。')
            by_name = cl.match(line)   # PCの設定と同じ線なら、名前だけ送る道も選べる
        if sector_changed:
            notes.append('セクターの線が変わるので、セクターのタイムとベストは消えます（周回数とラップタイムは残ります）。')
        same = link is not None and not found
        return {'via': link.kind if link is not None else 'LTE', 'direct': link is not None, 'need_code': need and not same,
                'title': title, 'changes': found or ['変わる所はありません（本体の線は、もう同じです）'], 'same': same,
                'notes': notes, 'by_name': by_name}

    def line_set(self, body):
        """線を入れる。つながっていれば直接、いなければLTE"""
        import course_lines as cl
        line, bad = self.line_from(body)
        if bad:
            raise Refused('送っていません。線の形がおかしい所があります：' + '／'.join(bad))
        confirmed = body.get('confirmed') is True
        link = self.connected_link()
        if link is None:
            return self.line_lte(line, body.get('by_name'), confirmed)
        lap, v = self.line_read(link)
        limit, why = cl.racing_kmh(cl.match(lap.get('line')), body.get('course'))
        if v is not None and v >= limit and not confirmed:
            raise Refused(f'送っていません。車がレーシングスピード以上で走っています（{v:.0f} km/h。{why}）。'
                          'もう一度「本体へ入れる」を押して、確認の数字を入れてください')
        self.begin('線を入れる', link.kind, LINE_WAIT_S)
        self.app.now['op']['kind'] = 'line'

        def work():
            before = lap.get('line') or {}
            found, _ = cl.changes(before, line)
            if not found:
                return True, ['本体の線は、もう同じでした（何も変えていません）。']
            backup = f'lap.json.bak-{datetime.now():%Y%m%d-%H%M%S}'   # tools/sugo_setup/sugo_setup.py --apply と同じ控え方
            try:
                kept = link.run(f'cd {shlex.quote(link.root)} || exit 1\n[ -f lap.json ] || {{ echo NONE; exit 0; }}\n'
                                f'[ -e {backup} ] || cp -p lap.json {backup} || exit 1\necho KEPT\n', timeout=30)
            except Exception as exc:  # noqa: BLE001
                return False, [f'入れる前の線を本体に控えられなかったので、何も変えていません（{exc}）。']
            device_api(link, '/api/lap', line)
            back = device_api(link, '/api/lap')   # 読み直す
            old = self.app.now.get('course') or {}
            self.app.now['course'] = {**old, **(cl.device_view(back) or {}), 'speed_kmh': v, 'vehicle': old.get('vehicle')}
            left, _ = cl.changes(back.get('line') or {}, line)
            name = cl.match(back.get('line'))
            return not left, [
                '入れました。本体から読み直して確かめました：' + ('送った線と同じです。' if not left else '★送った線と違う所があります。'),
                *(left[1:] if left else cl.describe(back.get('line') or {})),
                'コースの設定：' + (f'「{name}」と同じ線' if name else 'PCにあるどの設定とも違う線（設定に無い線）'),
                f'入れる前の線は、本体の {backup} に控えました。' if 'KEPT' in kept else '入れる前の本体には線のファイルが無かったので、控えはありません。']
        self.background(work)

    def line_lte(self, line, by_name, confirmed):
        import course_lines as cl
        cmd = rc()
        if not cmd.load_local().get('secret'):
            raise Refused(NEED_SETUP)
        if not confirmed:
            raise Refused('送っていません。LTEで線を変えるときは、変わる所を見て、確認の数字を入れてから送ります。もう一度「本体へ入れる」を押してください')
        op, arg = ('course_select', {'name': by_name}) if by_name else ('line_set', {k: v for k, v in line.items() if k != 'enabled'})
        self.begin(cmd.OP_LABEL[op] + (f'（{by_name}）' if by_name else ''), 'LTE', LTE_WAIT_S)
        self.app.now['op']['kind'] = 'line'

        def short(gate):
            return None if gate is None else [round(gate['lat'], 7), round(gate['lon'], 7), gate.get('bearing'), gate.get('width_m')]

        def work():
            result = cmd.send(op, arg, timeout=LTE_WAIT_S, log=lambda *a: None)
            lines = cmd.describe(result)
            ok = bool(result and result.get('ok'))
            if result and str(result.get('message', '')).startswith('no course '):
                lines.append('名前だけ送る道は、本体にその設定のファイルが入っているときに使えます。「送る（線まるごと）」なら、本体に設定が無くても入ります。')
            back = result.get('line') if result else None
            if ok and isinstance(back, dict):   # 返事に入っている「本体から読み直した線」を、送った線と比べる
                want = [short(g) for _, g in cl.gates(line)] + [len(line['sectors'])]
                ok = [back.get('control'), back.get('start'), back.get('goal'), back.get('sectors')] == want
                lines.insert(1, '本体から読み直した線は、送った線と同じでした。' if ok else '★本体から読み直した線が、送った線と違います。下の値を確かめてください。')
                if ok:   # つながるまでの間、図には「最後に分かっている本体の線」としてこれを出す
                    self.app.now['course'] = {**(self.app.now.get('course') or {}), 'line': {**line, 'set_at': back.get('at')},
                                              'read_at': time.time(), 'sent': True, 'speed_kmh': None}
            if result and result.get('status'):
                import now_status
                found, extra = now_status.checks_lte(result['status'])
                self.app.now['lte'] = {'checks': found, 'extra': extra, 'read_at': time.time()}
            return ok, lines
        self.background(work)

    def car_here(self):
        """車のいまの位置と向き（線のエディターの「車のいまの位置と向きを使う」）。本体は変えない"""
        import course_lines as cl
        link = self.connected_link()
        if link is None:
            raise Refused('車のいまの位置は、本体がUSBかテザリングでつながっているときに読めます（LTEでは読めません）。つないでから、もう一度押してください')
        try:
            here = cl.position(device_api(link, '/api/telemetry'))
        except (OSError, ValueError) as exc:
            raise Refused(f'本体から位置を読めませんでした（{exc}）。少し待って、もう一度押してください')
        if here is None:
            raise Refused('本体がまだ測位していません。空の見える所で数分待ってから、もう一度押してください')
        return here

    # ---- 画面から
    def action(self, path, body):
        """/api/op/… を受ける。知らない道は KeyError。返すものがあれば、画面への返事に入る"""
        if path == '/api/op/line_plan':
            return self.line_plan(body)
        if path == '/api/op/line_set':
            return self.line_set(body)
        if path == '/api/op/car_here':
            return self.car_here()
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
