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

    class FakeUsb(unoq_link.AdbLink):
        def run(self, script, timeout=60):
            if flag('hang'):
                time.sleep(3600)
            if not flag('usb'):
                raise OSError('抜けた')
            return f"@@S\n{json.dumps(BAD if flag('bad') else GOOD)}\n@@L\n{json.dumps(LAP)}\n@@C\n1\n"

    class FakeSsh(unoq_link.SshLink):
        def run(self, script, timeout=60):
            if flag('hang'):
                time.sleep(3600)
            if not flag('tether') or flag('usb'):
                raise OSError('切れた')
            return f"@@S\n{json.dumps(BAD if flag('bad') else GOOD)}\n@@L\n{json.dumps(LAP)}\n@@C\n0\n"

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
        return {'ok': True, 'op': op, 'message': 'done', 'status': {
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
        return {'values': {'LapCount': laps['count']}, 'line': {'enabled': True}}
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
