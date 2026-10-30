"""Ver.2をSUGO 120分耐久（2026-11-08、NCEC）用の設定へ切り替える（SG-1-2・SG-1-3）。

2026-10-30に本体を読んで確かめた結果、切り替えで変えるのはラップのラインだけ:
  - 車両の信号：NCECのプリセットと同じ＋油温（OilTemp、センサーハブ）。CAN1は受信専用で有効 → そのまま
  - LTE：送り先は自宅の5Bだけ。油温・ラップの値はPodiumへ自動で足される → そのまま
  - ラップのライン：エコラン会場の3本（スタート・コントロール・ゴール）と7周・規定時間 → SUGOのコントロールライン1本へ

既定は確かめるだけで、本体は何も変えない。--apply を付けたときだけ次を行う:
  1. 今の lap.json を本体の中で lap.json.bak-<日付>-ecorun へ写す（同じ名前があれば上書きしない）
  2. ラインをSUGOのコントロールラインにする（POST /api/lap。記録は止めなくてよい）
  3. ラップの記録を消す（POST /api/lap/reset）。決勝の前（予選のあと）にもう一度リセットする
--restore <本体のファイル名> で、退避した lap.json のラインへ戻す（エコラン用へ戻すとき）。
--reset でラップの記録だけを消す（予選のあと決勝の前。Reset-Laps.cmd がこれを呼ぶ）。
  レース経過（SessionTime）はリセットのあと最初にコントロールラインを通った時から数える。

つなぎ方: 既定は ssh unoq（Pixelのテザリング）。--adb でUSBのadb（ドックを外してPCへ直接つないだとき）。
  python sugo_setup.py            # 確かめるだけ
  python sugo_setup.py --apply    # SUGO用へ切り替える
  python sugo_setup.py --reset    # ラップの記録を消す
  python sugo_setup.py --restore lap.json.bak-20261102-ecorun
"""
import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collect_logs'))

DATA = '/home/arduino/ecocapture-v2-data'
API = 'http://127.0.0.1:8080'

# task_sugo_20261108_breakdown.md SG-1-3（2026-10-25、OpenStreetMapのコースと航空写真から）。
# 幅50mはピットレーンを通った周も数えるため。給油で長くなる周があるので最長ラップは既定の1時間のまま。
SUGO_LINE = {
    'enabled': True, 'lat': 38.1423587, 'lon': 140.7770000, 'bearing': 97.5, 'width_m': 50.0,
    'min_lap_s': 60.0, 'max_lap_s': 3600.0,
    'start': None, 'goal': None, 'total_laps': None, 'time_limit_s': None, 'margin_s': None,
}


def runner(use_adb, host):
    """本体でシェルのコマンドを1つ実行して標準出力を返す関数"""
    if use_adb:
        from collect_logs import adb_command
        adb = adb_command()
        if not adb:
            sys.exit('adbが見つかりません')
        head = [*adb, 'shell']
    else:
        head = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', host]

    def run(command):
        done = subprocess.run([*head, command], capture_output=True, text=True, encoding='utf-8', timeout=60)
        if done.returncode:
            raise RuntimeError(f'本体でのコマンドが失敗しました: {done.stderr.strip() or done.stdout.strip()}')
        return done.stdout
    return run


def api(run, path, body=None):
    """本体のEcoCaptureのAPIを本体の中から呼ぶ（外へ口を開けない）"""
    command = f'curl -s -m 15 -w "\\n%{{http_code}}" {API}{path}'
    if body is not None:  # 書き込みはEcoCaptureの操作ヘッダーが要る（server.pyのlocal_requests）
        command += (" -X POST -H 'X-EcoCapture: 1' -H 'Content-Type: application/json'"
                    f" --data-binary {shlex.quote(json.dumps(body))}")
    text, _, code = run(command).rstrip().rpartition('\n')
    if code != '200':
        raise RuntimeError(f'{path}: HTTP {code} {text[:200]}')
    return json.loads(text)


def line_changes(now, target=SUGO_LINE):
    """(項目, 今, 切り替え後) のうち違うもの"""
    return [(key, now.get(key), value) for key, value in target.items() if now.get(key) != value]


def check(run):
    """切り替えに関わるところを読んで表示し、今のラップのラインを返す"""
    config, preset = api(run, '/api/config'), api(run, '/api/can/ncec')
    names = [s['name'] for s in config['signals']]
    expected = [s['name'] for s in preset['signals']]
    same = [s for s in config['signals'] if s['name'] in expected] == preset['signals']
    print(f"車両の信号: プリセット {config['profile']}、NCECの{len(expected)}信号 {'一致' if same else '★プリセットと違う'}、"
          f"油温 {'あり' if 'OilTemp' in names else '★なし'}")
    hardware = api(run, '/api/status').get('hardware', {})
    print(f"CAN1: {'受信専用で有効' if hardware.get('can1_ready') else '★準備できていない'}（{hardware.get('result', '')}）")
    podium = api(run, '/api/podium')['config']
    print(f"LTE: 送信{'ON' if podium.get('enabled') else '★OFF'}、回線 {podium.get('link')}、送り先 {podium.get('destination')}、"
          f"予備の送り先 {len(podium.get('backup_server_urls') or [])}件")
    lap = api(run, '/api/lap')
    changes = line_changes(lap['line'])
    print(f"ラップ: 完了{lap['values'].get('LapCount')}周、ラインの設定日時 {lap['line'].get('set_at')}")
    if not changes:
        print('ラップのライン: SUGOのコントロールラインになっている')
    for key, now, after in changes:
        print(f'  {key}: {json.dumps(now, ensure_ascii=False)} → {json.dumps(after, ensure_ascii=False)}')
    return lap['line'], changes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='SUGO用へ切り替える（付けなければ確かめるだけ）')
    parser.add_argument('--restore', metavar='FILE', help='本体の ecocapture-v2-data にある退避した lap.json のラインへ戻す')
    parser.add_argument('--reset', action='store_true', help='ラップの記録だけを消す（ラインはそのまま）')
    parser.add_argument('--adb', action='store_true', help='sshでなくUSBのadbでつなぐ')
    parser.add_argument('--host', default='unoq', help='sshの接続先（既定 unoq）')
    args = parser.parse_args(argv)
    run = runner(args.adb, args.host)
    line, changes = check(run)
    if args.reset:
        if changes:
            print('★ラインがSUGOのコントロールラインではありません。先に --apply で切り替えてください')
            return 1
        api(run, '/api/lap/reset', {})
        lap = api(run, '/api/lap')
        print(f"ラップの記録を消しました（完了{lap['values'].get('LapCount')}周）。レース経過は次にラインを通った時から数えます")
        return 0
    if args.restore:
        name = Path(args.restore).name
        saved = json.loads(run(f'cat {DATA}/{shlex.quote(name)}'))['line']
        print(f'{name} のラインへ戻します')
        api(run, '/api/lap', saved)
        api(run, '/api/lap/reset', {})
        check(run)
        return 0
    if not args.apply:
        print('（確かめただけで、本体は変えていません。切り替えるときは --apply）')
        return 0
    if not changes:
        print('ラインは切り替え済みなので、何もしません（ラップのリセットは /api/lap/reset か画面から）')
        return 0
    backup = f"lap.json.bak-{datetime.now():%Y%m%d}-ecorun"
    run(f'cd {DATA} || exit 1; [ -e {backup} ] || cp -p lap.json {backup}; ls -l {backup}')
    print(f'今のラインを本体の {backup} へ退避しました')
    api(run, '/api/lap', SUGO_LINE)
    api(run, '/api/lap/reset', {})
    print('SUGOのコントロールラインにして、ラップの記録を消しました')
    _, left = check(run)
    return 1 if left else 0


if __name__ == '__main__':
    sys.exit(main())
