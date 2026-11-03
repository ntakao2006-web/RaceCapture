"""PIC v8のDefi電圧入力（CAN2・標準ID 0x580）をVer.2の信号に登録する（SG-4-3）。

引継ぎ（Lintarohさん、2026-11-01）: lintaroh_answer_20261101_defi_volt.md
登録するのは PressVolt・Temp1Volt・Temp2Volt（単位V、公称5V換算＝ADC×5/4095）の3つだけ。
ほかの信号（NCECの12信号、旧式の油温 OilTemp＝0x600）はそのまま残す。
電圧は未校正（プルアップ抵抗値・油圧の特性が未確定）なので、℃やkPaへは換算しない。
本体のEcoCaptureが換算「defi_volt」を知っている版（2026-11-03以降）でないと登録できない。

既定は確かめるだけで、本体は何も変えない。--apply を付けたときだけ次を行う:
  1. 今の設定を本体の中で config.json.bak-<日時>-before-defivolt へ写し、PCにも残す
     （PCは other/uno_q_tools/config-backups/<日時>/config.json。どちらも上書きしない。--remove のときは -before-defivolt-remove）
  2. 記録中なら記録を止める（設定は記録中に変えられない）
  3. 3つの信号を足す（同じ名前があれば置き換える）
  4. 止めた記録を再開する
--remove で3つの信号を外す（元へ戻すとき。同じく記録を止めて再開する）。

つなぎ方: 既定は ssh unoq（Pixelのテザリング）。--adb でUSBのadb（ドックを外してPCへ直接つないだとき）。
  python defi_volt_setup.py            # 確かめるだけ
  python defi_volt_setup.py --apply    # 登録する
  python defi_volt_setup.py --remove   # 外す
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sugo_setup
from sugo_setup import DATA, api

LOCAL_BACKUPS = Path(__file__).resolve().parents[2] / 'other' / 'uno_q_tools' / 'config-backups'

# 引継ぎの「CANパケット」の表: 0–1 PRESS、2–3 TEMP1、4–5 TEMP2（12bit ADC、uint16 LE）。
# 並びはmodels.Signalの項目順に合わせ、本体から読んだものとそのまま比べられるようにする。
DEFI_SIGNALS = [{'channel': 2, 'name': name, 'unit': 'V', 'can_id': 0x580, 'extended': False,
                 'byte_offset': offset, 'data_type': 'uint16', 'endian': 'little', 'scale': 5.0 / 4095.0,
                 'offset': 0.0, 'bit_mask': None, 'conversion': 'defi_volt', 'pullup_ohm': None, 'ntc_points': []}
                for name, offset in (('PressVolt', 0), ('Temp1Volt', 2), ('Temp2Volt', 4))]
NAMES = [s['name'] for s in DEFI_SIGNALS]


def registered(config):
    """DEFI_SIGNALSの各信号が 未登録 / 登録済み / 設定が違う のどれか"""
    signals = {s['name']: s for s in config['signals']}
    return {t['name']: '未登録' if t['name'] not in signals else
            '登録済み' if all(signals[t['name']].get(k) == v for k, v in t.items()) else '★設定が違う'
            for t in DEFI_SIGNALS}


def check(run):
    """登録に関わるところを読んで表示し、(設定, 状態) を返す"""
    config, status = api(run, '/api/config'), api(run, '/api/status')
    names = [s['name'] for s in config['signals']]
    print(f"車両の信号: プリセット {config['profile']}、{len(names)}信号")
    oil = next((s for s in config['signals'] if s['name'] == 'OilTemp'), None)
    print('旧式の油温 OilTemp: ' + ('なし' if oil is None else
          f"あり（CAN{oil['channel']} 0x{oil['can_id']:03X}、{oil.get('conversion')}）。この道具では変えない"))
    for name, state in registered(config).items():
        print(f'  {name}: {state}')
    counts = status.get('hardware', {}).get('can_counts', [0, 0])
    print(f'CAN2の受信: {counts[1]} フレーム（PIC v8がつながっていなければ0のまま）')
    sample = api(run, '/api/telemetry').get('sample') or {}
    for name in NAMES:
        state = (sample.get('can_states') or {}).get(name)
        if state:
            value = (sample.get('can_signals') or {}).get(name)
            print(f"  {name}: {'—' if value is None else f'{value:.3f} V'}（{state['label']}）")
    print(f"記録: {'記録中' if status['logging']['active'] else '停止中'}")
    return config, status


def save(run, config, status, signals, label):
    """設定を退避してから信号の一覧を signals に置き換える。記録中なら止めて、あとで再開する"""
    stamp = f'{datetime.now():%Y%m%d_%H%M%S}'
    local, n = LOCAL_BACKUPS / stamp, 1
    while local.exists():  # 同じ秒にもう一度保存しても、前の退避を上書きしない
        n += 1; local = LOCAL_BACKUPS / f'{stamp}-{n}'
    local.mkdir(parents=True)
    backup = f'config.json.bak-{local.name}-{label}'
    run(f'cd {DATA} || exit 1; [ -e {backup} ] || cp -p config.json {backup}; ls -l {backup}')
    (local / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'今の設定を本体の {backup} と、PCの {local / "config.json"} へ退避しました')
    recording = status['logging']['active']
    if recording:
        api(run, '/api/log/stop', {}, wait=50)
        print('記録を止めました')
    try:
        api(run, '/api/config', {**config, 'signals': signals})
        print('設定を保存しました')
    finally:
        if recording:
            # 止めたあとSDのファイルに時刻を付け終わるまでは、記録を始められない（server.pyのstart_log）
            for _ in range(60):
                if not api(run, '/api/status').get('sd_copy', {}).get('active'):
                    break
                time.sleep(1)
            api(run, '/api/log/start', {}, wait=50)
            print('記録を再開しました')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='3つの電圧の信号を登録する（付けなければ確かめるだけ）')
    parser.add_argument('--remove', action='store_true', help='3つの電圧の信号を外す')
    parser.add_argument('--adb', action='store_true', help='sshでなくUSBのadbでつなぐ')
    parser.add_argument('--host', default='unoq', help='sshの接続先（既定 unoq）')
    args = parser.parse_args(argv)
    run = sugo_setup.runner(args.adb, args.host)
    config, status = check(run)
    others = [s for s in config['signals'] if s['name'] not in NAMES]
    if args.remove:
        if len(others) == len(config['signals']):
            print('電圧の信号は登録されていないので、何もしません')
            return 0
        save(run, config, status, others, 'before-defivolt-remove')
    elif args.apply:
        if set(registered(config).values()) == {'登録済み'}:
            print('3つとも登録済みなので、何もしません')
            return 0
        if len(others) + len(DEFI_SIGNALS) > 64:
            print('★信号が64を超えるので登録できません')
            return 1
        try:
            save(run, config, status, others + DEFI_SIGNALS, 'before-defivolt')
        except RuntimeError as error:
            if 'defi_volt' in str(error) or 'HTTP 422' in str(error):
                print('★本体のEcoCaptureが「defi_volt」を知らない版です。先に EcoCapture-Web/Update-UNOQ.ps1 で更新してください')
            raise
    else:
        print('（確かめただけで、本体は変えていません。登録するときは --apply）')
        return 0
    config, _ = check(run)
    return 0 if set(registered(config).values()) == {'未登録' if args.remove else '登録済み'} else 1


if __name__ == '__main__':
    sys.exit(main())
