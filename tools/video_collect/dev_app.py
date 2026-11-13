"""PCのアプリの「いまの様子」を、本体なしで見るための道具（2026-11-13、SP-3-3）。

本物の本体・adb・ssh・LTEは使わない。作りものの「探した結果」と「読んだ値」で画面を動かす。
回収の段は、空の保存先で開く（本体が無いときの見え方）。

  python tools/video_collect/dev_app.py --dir <一時フォルダー> [--port 8795]
  → http://127.0.0.1:8795/

場面を変える（<dir> にファイルを置く／消す）：
  （何も無い）  … ロガーを待っています（USB・テザリングの理由が出る）
  usb          … USBでつながった（すべて良好）
  tether       … テザリングでつながった（USBでつなげない状態の案内つき）
  bad          … 直す所がある（測位待ち・録画していない・LTEつなぎ直し）。usb か tether と一緒に置く
  hang         … つながっているが読めなくなった（値が古くなる）。usb か tether と一緒に置く
  deaf         … LTEの命令に返事が無い
操作は作りもの（LTEへは送らない）。「合言葉の準備」をすると <dir>/secret.json ができ、消すと「合言葉が無い」場面になる。

「コースと線」の段（2026-11-13、SP-4-10・SP-4-11）：線の読み書きも作りもの。はじめの本体の線は tools/setups/courses/ の1つめ
（usb も tether も無ければ「LTEだけ」の場面。合言葉があれば、線はLTEの作りもので入る）
  moving       … 車が動いている（38 km/h。レーシングスピードより下）
  racing       … レーシングスピードで走っている（132 km/h。直接でも4桁の確認が出る）
  nofix        … 測位していない（車速が分からない＝止まっているものとして扱う、と出る）
  lapidle      … 1周を数えている途中ではない（置かなければ、数えている途中）
  othercar     … 本体が読んでいる信号が、車の設定と違う
  nocourse     … LTEで名前だけ送ったとき、本体にその設定が入っていない（断られる）
  noline／otherline … 起動の前に置く。本体に線が無い／PCのどの設定とも違う線（コントロールラインを東へ約30 m）
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import now_status  # noqa: E402
import unoq_link  # noqa: E402
import video_collect  # noqa: E402

GOOD = {
    'connected': True, 'receive_hz': 99.8, 'storage_free_bytes': 20 * 2**30,
    'logging': {'active': True, 'elapsed_s': 754, 'name': 'LOG_20261113_101500', 'error': None, 'sd_warning': None},
    'sensors': {'gnss': '測位中', 'sd': '記録中', 'camera': '接続'},
    'video': {'recording': True, 'minutes_left': 412, 'uncollected': 3},
    'podium': {'enabled': True, 'state': 'streaming', 'message': '送信中', 'radio': {'rsrp': -97}},
}
BAD = {**GOOD, 'sensors': {'gnss': '測位待ち', 'sd': '記録中', 'camera': '未接続'}, 'video': {'recording': False},
       'podium': {'enabled': True, 'state': 'reconnecting', 'message': 'つなぎ直しています', 'radio': {'rsrp': -118}}}
LAP = {'values': {'LapCount': 12}, 'line': {'enabled': True}}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--dir', type=Path, required=True)
    ap.add_argument('--port', type=int, default=8795)
    args = ap.parse_args()
    args.dir.mkdir(parents=True, exist_ok=True)
    flag = lambda name: (args.dir / name).exists()  # noqa: E731

    # 「コースと線」の作りものの本体：線（lap.json の line と同じ形）と、車速・位置・読んでいる信号
    import course_lines
    import setups
    courses = [c for c in course_lines.pc_courses() if 'line' in c]
    base = json.loads(json.dumps(courses[0]['line'])) if courses else {'enabled': False, 'lat': None, 'lon': None}
    if flag('noline'):
        base = {**base, 'enabled': False, 'lat': None, 'lon': None, 'start': None, 'goal': None, 'sectors': []}
    elif flag('otherline') and base.get('enabled'):
        base['lon'] += 0.00034
    device = {'line': {**base, 'set_at': None}}
    vehicles = setups.names('vehicle')
    logger = setups.load('vehicle', vehicles[0])['logger'] if vehicles else {'signals': []}

    def lap_public():
        return {'line': device['line'], 'values': {'LapCount': laps['count']}, 'running': not flag('lapidle'), 'finished': False}

    def telemetry():
        home = courses[0]['line'] if courses else {'lat': 36.0, 'lon': 138.0}
        kmh = 132.0 if flag('racing') else 38.0 if flag('moving') else 0.0
        values = {'Speed': None, 'GPSFix': 0, 'GPSSats': 0} if flag('nofix') else {
            'Speed': kmh, 'GPSSpeed': kmh, 'GPSFix': 3, 'GPSSats': 19, 'Lat': home['lat'] - 0.00012, 'Lon': home['lon'] - 0.00031, 'Yaw': 101.0}
        return {'type': 'telemetry', 'status': {}, 'sample': {'values': values, 'gnss_hacc_m': None if flag('nofix') else 0.9}}

    def config():
        signals = logger['signals'][:-1] if flag('othercar') else logger['signals']
        return {**{k: v for k, v in logger.items() if k != 'signals'}, 'signals': signals}

    def answer(script, usb_count):
        if 'lap.json.bak-' in script:   # 線を入れる前の控え（本体の中で lap.json を写す）
            return 'KEPT\n' if device['line'].get('enabled') else 'NONE\n'
        return (f"@@S\n{json.dumps(BAD if flag('bad') else GOOD)}\n@@L\n{json.dumps(lap_public())}\n@@C\n{usb_count}\n"
                f"@@T\n{json.dumps(telemetry())}\n@@G\n{json.dumps(config())}\n")

    class FakeUsb(unoq_link.AdbLink):
        def run(self, script, timeout=60):
            if flag('hang'):
                time.sleep(3600)
            if not flag('usb'):
                raise OSError('抜けた')
            return answer(script, 1)

    class FakeSsh(unoq_link.SshLink):
        def run(self, script, timeout=60):
            if flag('hang'):
                time.sleep(3600)
            if not flag('tether') or flag('usb'):
                raise OSError('切れた')
            return answer(script, 0)

    def survey():
        time.sleep(1.5)
        if flag('usb'):
            return FakeUsb(['adb'], '2954148814'), [unoq_link.Note('USB', True, 'つながりました', '')]
        notes = [unoq_link.Note('USB', False, 'USBに機器が見えません', unoq_link.USB_FIX)]
        if flag('tether'):
            return FakeSsh('unoq'), notes + [unoq_link.Note('テザリング', True, 'つながりました', '')]
        return None, notes + [unoq_link.Note('テザリング', False, 'ssh unoq でつながりません', 'PCと本体が同じテザリング（Pixel）にいるか、本体の電源を確かめる')]

    app = video_collect.App(video_collect.PcStore(args.dir / 'v2_video'), None)
    app.refresh = lambda: None                       # 回収の段は本体を読まない
    unoq_link.usb_ready = lambda: flag('usb')
    app.watcher = now_status.Watcher(app, survey=survey)
    # 操作も作りもの：LTEは2秒で返事（deaf があれば返事なし）、直接のリセットは周回を0にする、合言葉は <dir>/secret.json
    import app_ops
    import remote_command_pc as rc
    laps = {'count': 12}
    secret_file = args.dir / 'secret.json'
    rc.load_local = lambda: json.loads(secret_file.read_text()) if secret_file.exists() else {}

    def fake_send(op, arg=None, timeout=30, url=None, log=print):
        time.sleep(timeout if flag('deaf') else 2)
        if flag('deaf'):
            return None
        if op == 'lap_reset':
            laps['count'] = 0
        if op == 'lap_count':
            laps['count'] = arg
        extra, message = {}, 'done'
        if op in ('course_select', 'line_set'):   # 本体の remote_command.py と同じ形の返事を作る
            if op == 'course_select':
                found = None if flag('nocourse') else course_lines.course(arg['name'])
                if not found:
                    return {'ok': False, 'op': op, 'message': f"no course {arg['name']}", 'courses': []}
                new = dict(found['line'])
            else:
                new = {**device['line'], 'bearing': None, 'width_m': 30, 'start': None, 'goal': None, 'sectors': [], **arg, 'enabled': True}
            changed = bool(course_lines.changes(device['line'], new)[0])
            device['line'] = {**new, 'set_at': time.strftime('%Y-%m-%dT%H:%M+09:00')}
            short = lambda g: None if g is None else [round(g['lat'], 7), round(g['lon'], 7), g.get('bearing'), g.get('width_m')]  # noqa: E731
            message = (f"course {arg['name']} set" if changed else f"course {arg['name']} was already set") if op == 'course_select' \
                else 'line set' if changed else 'line was already set'
            extra = {'line': {'name': course_lines.match(new), 'control': short(new), 'start': short(new.get('start')), 'goal': short(new.get('goal')),
                              'sectors': len(new.get('sectors') or []), 'id': 'DEV0', 'at': device['line']['set_at'], 'changed': changed}}
        return {'ok': True, 'op': op, 'message': message, **extra, 'status': {
            'logging': True, 'log_s': 754, 'hz': 99.8, 'gnss': True, 'sd': True, 'video': not flag('bad'),
            'lap': {'enabled': True, 'count': laps['count'], 'current': laps['count'] + 1, 'running': True, 'race_min': 18.4}}}

    def fake_setup(log=print, new=False):
        time.sleep(1.5)
        secret_file.write_text(json.dumps({'secret': 'ab' * 32, 'url': 'wss://relay.example/ws/audio/dev'}))
        log('合言葉を本体とPCに入れました（作りもの）。中継: relay.example（ルーム dev）')

    def fake_api(link, path, body=None, wait=15):
        time.sleep(1)
        if path == '/api/lap/reset':
            laps['count'] = 0
        if path == '/api/telemetry':
            return telemetry()
        if path == '/api/lap' and body is not None:   # 本体と同じく、いまの線に送られた分を重ねる
            device['line'] = {**device['line'], **body, 'set_at': time.strftime('%Y-%m-%dT%H:%M+09:00')}
        return lap_public()
    rc.send, rc.setup, app_ops.device_api, app_ops.LTE_WAIT_S = fake_send, fake_setup, fake_api, 8
    LAP['values'] = laps_view = {'LapCount': 12}
    app.ops = app_ops.Ops(app)
    _reader = now_status.read

    def reader(link):
        laps_view['LapCount'] = laps['count']
        return _reader(link)
    app.watcher.reader = reader
    app.watcher.start()
    video_collect.serve(app, args.port, open_browser=False)


if __name__ == '__main__':
    main()
