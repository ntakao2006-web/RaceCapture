"""SUGOのピット画面（Grafana「SUGO 120分耐久 Live」）へLTEで届ける設定を確かめる・直す（SG-1-5、2026-11-04）。

車両（部屋）：ピット画面の「車両」は、ロガーが送る中継サーバーの部屋（送り先 wss://<サーバー>/ws/audio/<部屋> の最後）。
同じVer.2でも、エコランカーでは`majesta`（エコランの画面`ecorun-live`）、NCECでは`ncec`（SUGOの画面`sugo-live`）で送る
（2026-11-04ユーザー判断：NCECはエコランカーではないので画面を分ける。対応は tools/home_telemetry/grafana/vehicles.py）。
部屋はサーバーに登録が要る（5Bは`ncec`を登録済み）。予備の送り先も同じ部屋にそろえる。

ピット画面が使う値：位置（Lat・Lon）・速度（Speed）・GPS衛星数（GPSSats）・水温（WaterTemp）・油温（OilTemp）・
前後と左右の加速度（LongAccel・LatAccel）・回転数（RPM、たたんだ行のグラフ）。時刻・GNSSの精度・周回の値は
podium.pyが自動で足す。

⚠️ 2026-11-03にOilTempをDefiの温度（換算ntc）へ差し替えたので、podium.pyの「センサーハブの油温
（sensorhub_oiltemp）は自動で足す」に当たらなくなった。送る項目にOilTempを入れないと、油温がピットへ届かない。

既定は確かめるだけで、本体は何も変えない。
  --apply   SUGO用にする：部屋を`ncec`へ、足りない項目（OilTempなど）を足す。ほかの項目・送信のON/OFFはそのまま
  --slim    --applyと一緒に。ピット画面が使わない項目（生の加速度・角速度・姿勢・高度・GNSSの速度など）を外し、
            上の9項目だけにする。車載CANを流しているとLTEは1行の文字数で律速される（EcoCapture-Web/LTE_PODIUM.md、
            10/19の実測で約1.25行/秒）ので、1行が約200→約140バイトになり、1秒あたりの行数が増える見込み（未実測）。
            本体の記録（SD・eMMC）は全項目のまま
  --room R  部屋をRにする（エコランカーへ戻すときは --room majesta）
  --set A,B,...  送る項目をこの並びにする（元へ戻すとき。変える前に今の並びを表示する）
送信をONにするのはこの道具ではしない（本体のLTEの画面か /api/podium の enabled）。

つなぎ方は sugo_setup.py と同じ（既定 ssh unoq、--adb でUSBのadb）。
  python podium_channels_setup.py                # 確かめるだけ
  python podium_channels_setup.py --apply        # NCECの部屋にして油温を足す
  python podium_channels_setup.py --apply --slim # さらにピット画面の分だけにする
  python podium_channels_setup.py --room majesta --set <元の並び>   # エコランカーへ戻す
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sugo_setup import api, runner  # noqa: E402

PIT = ['Lat', 'Lon', 'Speed', 'GPSSats', 'RPM', 'WaterTemp', 'OilTemp', 'LongAccel', 'LatAccel']
NEEDED = ['OilTemp', 'LongAccel', 'LatAccel', 'WaterTemp']
ROOM = 'ncec'   # the NCEC's room (tools/home_telemetry/grafana/vehicles.py)
ROOM_ID = re.compile(r'[A-Za-z0-9_-]{1,64}')   # the server's rule (ecorun-logger-server config.rs)
RELAY = re.compile(r'(wss?://[^/]+/ws/audio/)([A-Za-z0-9_-]{1,64})')


def room_of(url):
    m = RELAY.fullmatch(url or '')
    return m.group(2) if m else None


def check(run):
    """今の設定を表示して返す（送り先のサーバー名は出さない）"""
    podium = api(run, '/api/podium')
    config, allowed = podium['config'], {c['name'] for c in podium['channels']}
    channels = config['channels']
    print(f"LTE: 送信{'ON' if config.get('enabled') else 'OFF'}、回線 {config.get('link')}、送り先 {config.get('destination')}")
    if config.get('destination') == 'server':
        backups = [room_of(u) or '?' for u in config.get('backup_server_urls', [])]
        print(f"車両（部屋）: {room_of(config.get('server_url')) or '?'}" + (f"（予備 {','.join(backups)}）" if backups else ''))
    print(f"送る項目（{len(channels)}）: {','.join(channels)}")
    missing = [n for n in NEEDED if n not in channels]
    print('ピット画面の項目: ' + ('そろっている' if not missing else '★足りない ' + ','.join(missing)))
    unknown = [n for n in PIT if n not in allowed]
    if unknown:
        print('★本体に無い項目: ' + ','.join(unknown))
    return config, allowed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='SUGO用にする（付けなければ確かめるだけ）')
    parser.add_argument('--slim', action='store_true', help='--applyと一緒に：ピット画面の項目だけにする')
    parser.add_argument('--room', metavar='R', help=f'部屋をRにする（--applyは{ROOM}）')
    parser.add_argument('--set', metavar='A,B,...', help='送る項目をこの並びにする（元へ戻すとき）')
    parser.add_argument('--adb', action='store_true', help='USBのadbだけでつなぐ（付けなければ USB → テザリングの順に探す）')
    parser.add_argument('--host', default='unoq', help='sshの接続先（既定 unoq）')
    args = parser.parse_args(argv)
    run = runner(args.adb, args.host)
    config, allowed = check(run)
    channels = config['channels']
    if not (args.apply or args.set or args.room):
        print('（確かめただけで、本体は変えていません。直すときは --apply）')
        return 0
    body = {}
    if args.set:
        target = [n for n in args.set.split(',') if n]
    elif args.apply:
        target = list(PIT) if args.slim else channels + [n for n in NEEDED if n not in channels]
    else:
        target = channels
    bad = [n for n in target if n not in allowed]
    if bad:
        print('★本体に無い項目なので変えません: ' + ','.join(bad))
        return 1
    if target != channels:
        body['channels'] = target
    room = args.room or (ROOM if args.apply else None)
    if room:
        if not ROOM_ID.fullmatch(room):
            print(f'★部屋の名前に使えない文字があるので変えません: {room}（英数字・_・- の64文字まで）')
            return 1
        urls = [config.get('server_url', '')] + list(config.get('backup_server_urls', []))
        if config.get('destination') != 'server' or any(room_of(u) is None for u in urls):
            print('★送り先が中継サーバー（…/ws/audio/<部屋>）ではないので、部屋は変えません')
            return 1
        if room_of(urls[0]) != room or any(room_of(u) != room for u in urls[1:]):
            body['server_url'] = RELAY.sub(lambda m: m.group(1) + room, urls[0])
            body['backup_server_urls'] = [RELAY.sub(lambda m: m.group(1) + room, u) for u in urls[1:]]
    if not body:
        print('変えるところはありません')
        return 0
    print(f"元に戻すとき: --room {room_of(config.get('server_url')) or '?'} --set {','.join(channels)}")
    api(run, '/api/podium', body)
    after, _ = check(run)
    ok = after['channels'] == target and (not room or room_of(after.get('server_url')) == room)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
