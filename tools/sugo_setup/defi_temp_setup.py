"""PIC v8のDefi温度の電圧（CAN2 0x580）を℃の信号にする（SG-4-3の④）。

PIC v8はDefiがサーミスタへ内部の抵抗越しにかけている電圧を横から測るだけなので、
電圧の比 → 抵抗 → ℃ を既存の換算「ntc」で行う（ロガーのプログラムは変えない）。
  TEMP1（0x580の2〜3バイト目、赤黒っぽいカプラー）＝水温 → WaterTempDefi（ECUの WaterTemp とは別に持つ）
  TEMP2（0x580の4〜5バイト目、ピンクのカプラー）  ＝油温 → OilTemp（旧0x600の定義を置き換える。名前を変えないので、
                                                       車載ダッシュの油温ゲージ・警告・焼き込み録画がそのまま使える）
サーミスタはDefiの温度センサーの表（datasheet/defi_temp_sensor_rt.csv）。表は -1℃ 27.6 kΩ と 97℃ 1.145 kΩ の2点の
β式そのもの（全99行で差0.015℃以内）なので、校正点はこの2点だけでよい（97℃より上は同じ式を延ばす）。
Defi側の回路は「電圧 BIAS_V を抵抗 PULLUP_OHM 越しにかけている」と見る。BIAS_V はPICの公称5 V換算での値で、
PICの電源（ADCの基準）とDefiの電源の差や入力までの回路の倍率もここに入る（ADC×5/4095 を BIAS_V で割った比が換算の比）。
2026-11-04にDefiのメーターと並べて読んだ7点（水温32.5・36・70.75・88℃、油温72・85・86℃）へ当てはめた値で、
ずれは1.2℃以内。初めの「5 V・2060 Ω」（85〜90℃の点だけから逆算）は、水温36℃で7℃低く出ていた。
メーターと合わせ直したら --bias・--pullup で変える。

既定は確かめるだけ。--apply を付けたときだけ、設定を本体とPCへ退避 → 記録を止める → 置き換え → 記録を再開する
（defi_volt_setup.py と同じ手順）。電圧の信号（PressVolt・Temp1Volt・Temp2Volt）はそのまま残す。
  python defi_temp_setup.py                  # 確かめるだけ
  python defi_temp_setup.py --apply          # 登録する
  python defi_temp_setup.py --apply --bias 5.6 --pullup 2500
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import defi_volt_setup
import sugo_setup
from sugo_setup import api

BIAS_V = 5.544  # 公称5 V換算
PULLUP_OHM = 2441.0
DEFI_POINTS = [[-1.0, 27600.0], [97.0, 1145.0]]  # (℃, Ω)。JSONで返る形に合わせてリストにする


def temp_signals(pullup=PULLUP_OHM, bias=BIAS_V):
    """(水温, 油温) の信号。並びはmodels.Signalの項目順"""
    def signal(name, offset):
        return {'channel': 2, 'name': name, 'unit': '°C', 'can_id': 0x580, 'extended': False,
                'byte_offset': offset, 'data_type': 'uint16', 'endian': 'little', 'scale': 5 / (4095 * bias),
                'offset': 0.0, 'bit_mask': None, 'conversion': 'ntc', 'pullup_ohm': pullup,
                'ntc_points': DEFI_POINTS}
    return signal('WaterTempDefi', 2), signal('OilTemp', 4)


def replaced(signals, targets):
    """同じ名前の信号はその位置で置き換え、無いものは最後に足す（ほかの信号と並びは変えない）"""
    by_name = {t['name']: t for t in targets}
    out = [by_name.pop(s['name'], s) for s in signals]
    return out + [t for t in targets if t['name'] in by_name]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='℃の信号を登録する（付けなければ確かめるだけ）')
    parser.add_argument('--bias', type=float, default=BIAS_V, help=f'Defiがかけている電圧 V、公称5 V換算（既定 {BIAS_V}）')
    parser.add_argument('--pullup', type=float, default=PULLUP_OHM, help=f'Defi内部の抵抗 Ω（既定 {PULLUP_OHM:.0f}）')
    parser.add_argument('--adb', action='store_true', help='USBのadbだけでつなぐ（付けなければ USB → テザリングの順に探す）')
    parser.add_argument('--host', default='unoq', help='sshの接続先（既定 unoq）')
    args = parser.parse_args(argv)
    run = sugo_setup.runner(args.adb, args.host)
    config, status = api(run, '/api/config'), api(run, '/api/status')
    targets = temp_signals(args.pullup, args.bias)
    now = {s['name']: s for s in config['signals']}
    for t in targets:
        old = now.get(t['name'])
        state = ('未登録' if old is None else '登録済み' if all(old.get(k) == v for k, v in t.items())
                 else f"★違う（今は CAN{old['channel']} 0x{old['can_id']:03X}・{old.get('conversion')}"
                      f"{'・%.3f V・%.0fΩ' % (5 / 4095 / old['scale'], old['pullup_ohm']) if old.get('pullup_ohm') else ''}）")
        print(f"{t['name']}: {state}")
    if not args.apply:
        print('（確かめただけで、本体は変えていません。登録するときは --apply）')
        return 0
    signals = replaced(config['signals'], targets)
    if signals == config['signals']:
        print('登録済みなので、何もしません')
        return 0
    if len(signals) > 64:
        print('★信号が64を超えるので登録できません')
        return 1
    defi_volt_setup.save(run, config, status, signals, 'before-defitemp')
    sample = api(run, '/api/telemetry').get('sample') or {}
    for t in targets:
        value = (sample.get('can_signals') or {}).get(t['name'])
        print(f"  {t['name']}: {'—' if value is None else f'{value:.1f}℃'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
