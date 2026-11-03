"""SUGOのピット画面（Grafana「SUGO 120分耐久 Live」）へLTEで届ける項目を確かめる・直す（SG-1-5、2026-11-04）。

ピット画面が使う値：位置（Lat・Lon）・速度（Speed）・GPS衛星数（GPSSats）・水温（WaterTemp）・油温（OilTemp）・
前後と左右の加速度（LongAccel・LatAccel）・回転数（RPM、たたんだ行のグラフ）。時刻・GNSSの精度・周回の値は
podium.pyが自動で足す。

⚠️ 2026-11-03にOilTempをDefiの温度（換算ntc）へ差し替えたので、podium.pyの「センサーハブの油温
（sensorhub_oiltemp）は自動で足す」に当たらなくなった。送る項目にOilTempを入れないと、油温がピットへ届かない。

既定は確かめるだけで、本体は何も変えない。
  --apply   足りない項目（OilTempなど）だけを足す。ほかの項目・送信のON/OFF・送り先はそのまま
  --slim    --applyと一緒に。ピット画面が使わない項目（生の加速度・角速度・姿勢・高度・GNSSの速度など）を外し、
            上の8項目だけにする。車載CANを流しているとLTEは1行の文字数で律速される（EcoCapture-Web/LTE_PODIUM.md、
            10/19の実測で約1.25行/秒）ので、1行が約200→約140バイトになり、1秒あたりの行数が増える見込み（未実測）。
            本体の記録（SD・eMMC）は全項目のまま
  --set A,B,...  送る項目をこの並びにする（元へ戻すとき。確かめたときに今の並びを表示する）
送信をONにするのはこの道具ではしない（本体のLTEの画面か /api/podium の enabled）。

つなぎ方は sugo_setup.py と同じ（既定 ssh unoq、--adb でUSBのadb）。
  python podium_channels_setup.py                # 確かめるだけ
  python podium_channels_setup.py --apply        # 油温を足す
  python podium_channels_setup.py --apply --slim # ピット画面の分だけにする
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sugo_setup import api, runner  # noqa: E402

PIT = ['Lat', 'Lon', 'Speed', 'GPSSats', 'RPM', 'WaterTemp', 'OilTemp', 'LongAccel', 'LatAccel']
NEEDED = ['OilTemp', 'LongAccel', 'LatAccel', 'WaterTemp']


def check(run):
    """今の送る項目を表示して返す"""
    podium = api(run, '/api/podium')
    config, allowed = podium['config'], {c['name'] for c in podium['channels']}
    channels = config['channels']
    print(f"LTE: 送信{'ON' if config.get('enabled') else 'OFF'}、回線 {config.get('link')}、送り先 {config.get('destination')}")
    print(f"送る項目（{len(channels)}）: {','.join(channels)}")
    missing = [n for n in NEEDED if n not in channels]
    print('ピット画面の項目: ' + ('そろっている' if not missing else '★足りない ' + ','.join(missing)))
    unknown = [n for n in PIT if n not in allowed]
    if unknown:
        print('★本体に無い項目: ' + ','.join(unknown))
    return channels, allowed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='足りない項目を足す（付けなければ確かめるだけ）')
    parser.add_argument('--slim', action='store_true', help='--applyと一緒に：ピット画面の項目だけにする')
    parser.add_argument('--set', metavar='A,B,...', help='送る項目をこの並びにする（元へ戻すとき）')
    parser.add_argument('--adb', action='store_true', help='sshでなくUSBのadbでつなぐ')
    parser.add_argument('--host', default='unoq', help='sshの接続先（既定 unoq）')
    args = parser.parse_args(argv)
    run = runner(args.adb, args.host)
    channels, allowed = check(run)
    if args.set:
        target = [n for n in args.set.split(',') if n]
    elif args.apply:
        target = list(PIT) if args.slim else channels + [n for n in NEEDED if n not in channels]
    else:
        print('（確かめただけで、本体は変えていません。直すときは --apply）')
        return 0
    bad = [n for n in target if n not in allowed]
    if bad:
        print('★本体に無い項目なので変えません: ' + ','.join(bad))
        return 1
    if target == channels:
        print('変えるところはありません')
        return 0
    print(f'元の並び（戻すときは --set に渡す）: {",".join(channels)}')
    api(run, '/api/podium', {'channels': target})
    after, _ = check(run)
    return 0 if after == target else 1


if __name__ == '__main__':
    sys.exit(main())
