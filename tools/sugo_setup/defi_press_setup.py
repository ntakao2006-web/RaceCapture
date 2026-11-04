"""PIC v8のDefi油圧の電圧（CAN2 0x580のPRESS、0〜1バイト目）を kPa の信号 OilPress にする（SG-4-3の④）。

車載ダッシュ（EcoCapture DASH・スマホの予備画面）は OilPress（kPa）と回転数で油圧の警告を出す。
換算は今ある「defi_volt」（1フレームを丸ごと検証し、通信途絶・データ異常は値なし）の倍率と足し算だけで行うので、
ロガーのプログラムは変えない。電圧の信号 PressVolt はそのまま残す（0点や傾きを見直すときに使う）。

Defiの油圧センサー（PDF00703S）は P[kPa] ＝ 250 ×（V − V0）のほぼ直線（defi_sensor_curves_research.md 2章。
傾きは2つの出どころで一致、0点は0.57 Vと0.48 Vで食い違う）。V はDefiの5 Vを基準にした電圧で、
PICは自分の電源を基準に測る（公称5 V換算）。2つの5 Vの比は、温度の換算で求めたDefiの電圧
（defi_temp_setup.BIAS_V、公称5 V換算で5.544 V）を使う。よって公称5 V換算の PressVolt からは
  OilPress[kPa] ＝ 250 × 5 / 5.544 ×（PressVolt − ZERO）   ＝ 約225.5 kPa/V
ZERO は公称5 V換算の0点。測るまでは海外フォーラムの実測0.570 Vを公称へ直した値（約0.632 V）を使う。
**0点はエンジンを止めてDefiに電気が来ている状態（IG ON）で測る**（--zero-now）。傾きは、エンジンをかけて
Defiの油圧計と見比べて合わせる（--meter）。

安全のため、すでに OilPress があるときは、その0点と傾きを引き継ぐ（--apply だけで測った値が消えない）。

既定は確かめるだけ。--apply を付けたときだけ、設定を本体とPCへ退避 → 記録を止める → 登録 → 記録を再開する
（defi_volt_setup.py と同じ手順）。
  python defi_press_setup.py                         # 確かめるだけ（今の電圧と、換算するとどうなるか）
  python defi_press_setup.py --apply                 # 登録する（0点は今の値、まだ無ければ仮の値）
  python defi_press_setup.py --apply --zero-now      # エンジン停止・IG ONで、今の電圧を0点にして登録する
  python defi_press_setup.py --apply --meter 300     # エンジンをかけて、Defiの油圧計が300 kPaのときに傾きを合わせる
  python defi_press_setup.py --apply --zero 0.62 --slope 250
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import defi_temp_setup
import defi_volt_setup
import sugo_setup
from sugo_setup import api

SLOPE_KPA_PER_V = 250.0  # Defiの5 Vを基準にした電圧1 Vあたり（2つの出どころで一致）
SUPPLY_V = defi_temp_setup.BIAS_V  # Defiの5 Vが公称5 V換算で何Vに見えるか（温度の換算で求めた値）
ZERO_V = round(0.570 * SUPPLY_V / 5, 3)  # 仮の0点（公称5 V換算）。海外フォーラムの実測0 psi＝0.570 V
ZERO_RANGE = (0.3, 1.0)  # 0点として受け付ける電圧（公称5 V換算）。これより外はセンサーにつながっていない
SAMPLES = 10
SPREAD_V = {'zero': 0.03, 'meter': 0.2}  # 測る間の揺れの上限（エンジン停止はほぼ動かない、アイドリングは脈を打つ）
STOPPED_RPM = 50


def per_volt(slope=SLOPE_KPA_PER_V, supply=SUPPLY_V):
    """公称5 V換算の1 Vあたりの kPa"""
    return slope * 5 / supply


def press_signal(zero=ZERO_V, kpa_per_v=None):
    """OilPress の信号（PRESS、0〜1バイト目）。並びはmodels.Signalの項目順"""
    k = per_volt() if kpa_per_v is None else kpa_per_v
    return {'channel': 2, 'name': 'OilPress', 'unit': 'kPa', 'can_id': 0x580, 'extended': False,
            'byte_offset': 0, 'data_type': 'uint16', 'endian': 'little', 'scale': k * 5 / 4095,
            'offset': -k * zero, 'bit_mask': None, 'conversion': 'defi_volt', 'pullup_ohm': None, 'ntc_points': []}


def params(signal):
    """登録済みの OilPress から (公称1 Vあたりの kPa, 0点 V)"""
    k = signal['scale'] * 4095 / 5
    return k, -signal['offset'] / k


def average(run, name='PressVolt', count=SAMPLES):
    """今の値を count 回読んで (平均, 最小, 最大, 回転数) を返す。読めないときは平均が None"""
    values, rpm = [], None
    for i in range(count):
        sample = api(run, '/api/telemetry').get('sample') or {}
        can, states = sample.get('can_signals') or {}, sample.get('can_states') or {}
        if name in can and can[name] is not None and (states.get(name) or {}).get('code') == 0:
            values.append(can[name])
        for source in (can, sample.get('values') or {}):
            if isinstance(source.get('RPM'), (int, float)):
                rpm = max(rpm or 0.0, source['RPM'])
                break
        if i + 1 < count:
            time.sleep(0.3)
    if not values:
        return None, None, None, rpm
    return sum(values) / len(values), min(values), max(values), rpm


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='OilPress を登録する（付けなければ確かめるだけ）')
    parser.add_argument('--zero', type=float, help='0点 V（公称5 V換算の PressVolt）')
    parser.add_argument('--zero-now', action='store_true', help='今の PressVolt を0点にする（エンジン停止・IG ONで）')
    parser.add_argument('--slope', type=float, help=f'傾き kPa/V（Defiの5 V基準、既定 {SLOPE_KPA_PER_V:.0f}）')
    parser.add_argument('--supply', type=float, default=SUPPLY_V, help=f'Defiの5 Vが公称5 V換算で何Vか（既定 {SUPPLY_V}）')
    parser.add_argument('--meter', type=float, metavar='KPA', help='エンジンをかけて、Defiの油圧計の今の値に傾きを合わせる')
    parser.add_argument('--adb', action='store_true', help='sshでなくUSBのadbでつなぐ')
    parser.add_argument('--host', default='unoq', help='sshの接続先（既定 unoq）')
    args = parser.parse_args(argv)
    if args.zero_now and args.meter is not None:
        parser.error('--zero-now（エンジン停止）と --meter（エンジン回転中）は別々に行ってください')

    run = sugo_setup.runner(args.adb, args.host)
    config, status = api(run, '/api/config'), api(run, '/api/status')
    now = {s['name']: s for s in config['signals']}
    old = now.get('OilPress')
    if 'PressVolt' not in now:
        print('★PressVolt が登録されていません（先に defi_volt_setup.py --apply）')
        return 1
    # 0点と傾き：登録済みの値 → 引数の順に決める（--apply だけで測った値を消さない）
    k, zero = params(old) if old and old.get('conversion') == 'defi_volt' else (per_volt(supply=args.supply), ZERO_V)
    if args.slope is not None or args.supply != SUPPLY_V:
        k = per_volt(args.slope if args.slope is not None else SLOPE_KPA_PER_V, args.supply)
    if args.zero is not None:
        zero = args.zero

    volt, low, high, rpm = average(run)
    shown = '読めない（PRESSが通信途絶・データ異常・下限付近か、PICが来ていない）' if volt is None else \
        f'{volt:.3f} V（{low:.3f}〜{high:.3f}、{SAMPLES}回）'
    print(f"PressVolt: {shown}　回転数: {'—' if rpm is None else f'{rpm:.0f} rpm'}")
    if args.zero_now or args.meter is not None:
        if volt is None or high - low > SPREAD_V['zero' if args.zero_now else 'meter']:
            print('★電圧が読めないか揺れているので、決められません')
            return 1
    if args.zero_now:
        if rpm is None or rpm > STOPPED_RPM:
            print('★エンジンが止まっていない（回転数が0でない・読めない）ので、0点を測れません')
            return 1
        zero = round(volt, 3)
    if not ZERO_RANGE[0] <= zero <= ZERO_RANGE[1]:
        print(f'★0点 {zero:.3f} V はセンサーの0 kPaの出力としておかしい（{ZERO_RANGE[0]}〜{ZERO_RANGE[1]} V）。'
              'ハーネス・Defiの電源を確かめてください')
        return 1
    if args.meter is not None:
        if rpm is None or rpm < 500:
            print('★エンジンがかかっていない（回転数が読めない・500 rpm未満）ので、傾きを合わせられません')
            return 1
        if args.meter < 100 or volt - zero < 0.3:
            print('★圧力が低すぎて傾きを合わせられません（100 kPa以上・0点より0.3 V以上で）')
            return 1
        k = args.meter / (volt - zero)
    target = press_signal(zero, k)
    slope_real = k * args.supply / 5
    print(f'換算: OilPress = {k:.1f} ×（PressVolt − {zero:.3f}）kPa'
          f'（Defiの5 V基準で {slope_real:.1f} kPa/V、Defiの5 V＝公称 {args.supply:.3f} V）')
    if volt is not None:
        print(f'  今の電圧なら {k * (volt - zero):.0f} kPa')
    state = ('未登録' if old is None else '登録済み' if all(old.get(f) == v for f, v in target.items()) else
             '★違う（今は ' + ('%.1f ×（PressVolt − %.3f）' % params(old) if old.get('conversion') == 'defi_volt'
                             else f"{old.get('conversion')}") + '）')
    print(f'OilPress: {state}')
    if not 150 <= slope_real <= 350:
        print(f'★傾き {slope_real:.0f} kPa/V は、Defiのセンサー（250 kPa/V）から離れすぎています。見直してください')
        return 1
    if not args.apply:
        print('（確かめただけで、本体は変えていません。登録するときは --apply）')
        return 0
    signals = defi_temp_setup.replaced(config['signals'], [target])
    if signals == config['signals']:
        print('登録済みなので、何もしません')
        return 0
    if len(signals) > 64:
        print('★信号が64を超えるので登録できません')
        return 1
    defi_volt_setup.save(run, config, status, signals, 'before-defipress')
    sample = api(run, '/api/telemetry').get('sample') or {}
    value = (sample.get('can_signals') or {}).get('OilPress')
    print(f"  OilPress: {'—' if value is None else f'{value:.0f} kPa'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
