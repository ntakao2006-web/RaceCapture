"""選んだ車・コースの設定を本体（Ver.2）へ入れる（2026-11-13、SP-4-3、`SPEC.md` 4章 P-1〜P-3）。

    python setups_apply.py --vehicle ncec --course sugo            # 確かめるだけ（本体は何も変えない）
    python setups_apply.py --vehicle ncec --course sugo --apply    # 違う所だけ入れる
    python setups_apply.py --course sugo --apply                   # コースだけ（記録を止めない）

これまで tools/sugo_setup/ の道具を順に流していたことを、設定ファイル（tools/setups/）から1回でする。入れるのは違う所だけ：

  コース（**記録を止めない**）
    1. PCにあるコースの設定を全部、本体の <データ>/setups/courses/ へ置く（LTEで「名前だけ送って選ぶ」ための元。同じなら置かない）
    2. 線が違えば、今の lap.json を本体の中で lap.json.bak-<日時> へ控えてから、コースの線を入れ、本体から読み直して比べる
       ラップの記録（周回数・ラップタイム）は消さない。0周に戻すのは別の操作（アプリの「ラップを0周に戻す」）
  車（**信号が変わるときは、記録を止めて入れ直す＝走行記録のファイルがそこで分かれる**）
    3. 読む信号・換算が違えば、今の設定を本体（config.json.bak-<日時>-before-setup）とPC（%USERPROFILE%\\.ecologger\\config-backups\\）へ控え、
       記録中なら止め、入れて、記録を再開する
    4. LTEで送る項目と、中継の部屋の名前が違えば入れる（送り先のサーバーの名前は表示しない。送信のON/OFFは変えない）
  入れないもの：車載画面のしきい値（dash）。いまは車載画面のソフトの中の値を使っている（設定から読む形にするのは SP-7-1 の後半）

つなぎ方は、USB → テザリングの順に自分で探す（tools/collect_logs/unoq_link.py）。
"""
import argparse
import base64
import json
import re
import shlex
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / 'collect_logs'))

import setups  # noqa: E402

DATA = '/home/arduino/ecocapture-v2-data'
API = 'http://127.0.0.1:8080'
COURSE_DIR = f'{DATA}/setups/courses'
LOCAL_BACKUPS = Path.home() / '.ecologger' / 'config-backups'
RELAY = re.compile(r'(wss?://[^/]+/ws/audio/)([A-Za-z0-9_-]{1,64})')


def api(run, path, body=None, wait=15):
    """本体のEcoCaptureのAPIを本体の中から呼ぶ（tools/sugo_setup/sugo_setup.py の api と同じ送り方）"""
    command = f'curl -s -m {wait} -w "\\n%{{http_code}}" {API}{path}'
    if body is not None:  # 書き込みはEcoCaptureの操作ヘッダーが要る
        command += (" -X POST -H 'X-EcoCapture: 1' -H 'Content-Type: application/json'"
                    f" --data-binary {shlex.quote(json.dumps(body))}")
    text, _, code = run(command).rstrip().rpartition('\n')
    if code != '200':
        raise RuntimeError(f'{path}: HTTP {code} {text[:200]}')
    return json.loads(text)


def connect():
    """本体でシェルのコマンドを1つ実行して標準出力を返す関数"""
    import subprocess
    import unoq_link
    link = unoq_link.connect()
    print(f'本体: {link.label()}')

    def run(command):
        done = subprocess.run(link.argv(command), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=450)
        if done.returncode:
            raise RuntimeError(f'本体でのコマンドが失敗しました: {done.stderr.strip() or done.stdout.strip()}')
        return done.stdout
    return run


# ---------------------------------------------------------------- コース
def course_files(run, apply):
    """PCのコースの設定を本体へ置く。[(名前, 'same'|'new'|'changed')] を返す"""
    out = []
    for name in setups.names('course'):
        text = json.dumps(setups.load('course', name), ensure_ascii=False, indent=1)
        have = run(f'cat {COURSE_DIR}/{name}.json 2>/dev/null; true')
        try:
            state = 'same' if json.loads(have) == json.loads(text) else 'changed'
        except ValueError:
            state = 'new'
        out.append((name, state))
        if apply and state != 'same':
            encoded = base64.b64encode(text.encode()).decode()
            run(f'mkdir -p {COURSE_DIR} && echo {encoded} | base64 -d > {COURSE_DIR}/{name}.json.tmp'
                f' && mv {COURSE_DIR}/{name}.json.tmp {COURSE_DIR}/{name}.json')
    return out


def apply_line(run, course, apply):
    """線を比べ、apply なら控えて入れて読み直す。残った違いの数を返す"""
    changes = setups.diff_course(course, api(run, '/api/lap').get('line') or {})
    bad = setups.show(f'本体の線（コース {course["id"]}）', changes)
    if not changes or not apply:
        return bad
    backup = f'lap.json.bak-{datetime.now():%Y%m%d-%H%M%S}'
    run(f'cd {DATA} || exit 1; [ -e {backup} ] || cp -p lap.json {backup}; ls -l {backup}')
    print(f'  今の線を本体の {backup} へ控えました')
    api(run, '/api/lap', course['line'])
    left = setups.diff_course(course, api(run, '/api/lap').get('line') or {})
    print('  線を入れ、本体から読み直しました：' + ('設定と同じ' if not left else f'★まだ違う所が{len(left)}つ'))
    print('  （ラップの記録は消していません。0周に戻すときは、アプリの「ラップを0周に戻す」）')
    return 1 if left else 0


# ---------------------------------------------------------------- 車
def save_config(run, config, new_config, vehicle_id):
    """信号の設定を入れる。控える → 記録中なら止める → 入れる → 記録を再開する（tools/sugo_setup/defi_volt_setup.py の save と同じ手順）"""
    stamp = f'{datetime.now():%Y%m%d_%H%M%S}'
    local, n = LOCAL_BACKUPS / stamp, 1
    while local.exists():
        n += 1
        local = LOCAL_BACKUPS / f'{stamp}-{n}'
    local.mkdir(parents=True)
    backup = f'config.json.bak-{local.name}-before-setup-{vehicle_id}'
    run(f'cd {DATA} || exit 1; [ -e {backup} ] || cp -p config.json {backup}; ls -l {backup}')
    (local / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'  今の設定を本体の {backup} と、PCの {local / "config.json"} へ控えました')
    recording = api(run, '/api/status')['logging']['active']
    try:
        if recording:
            api(run, '/api/log/stop', {}, wait=420)   # SDのファイルに時刻を付け終わるまで返らない（3分を超えることがある）
            print('  記録を止めました（走行記録のファイルは、ここで分かれます）')
        api(run, '/api/config', new_config)
        print('  信号の設定を入れました')
    finally:
        if recording and not api(run, '/api/status')['logging']['active']:
            for _ in range(180):   # 止めたあとSDのファイルに時刻を付け終わるまでは、記録を始められない
                if not api(run, '/api/status').get('sd_copy', {}).get('active'):
                    break
                time.sleep(1)
            api(run, '/api/log/start', {}, wait=50)
            print('  記録を再開しました')


def apply_signals(run, vehicle, apply):
    config = api(run, '/api/config')
    changes = setups.diff_vehicle(vehicle, config)
    bad = setups.show(f'本体の信号の設定（車 {vehicle["id"]}）', changes)
    if not changes or not apply:
        return bad
    logger = vehicle['logger']
    save_config(run, config, {**config, 'profile': logger.get('profile', config.get('profile')),
                              'can_bitrate': logger['can_bitrate'], 'signals': logger['signals']}, vehicle['id'])
    left = setups.diff_vehicle(vehicle, api(run, '/api/config'))
    print('  本体から読み直しました：' + ('設定と同じ' if not left else f'★まだ違う所が{len(left)}つ'))
    return 1 if left else 0


def room_of(url):
    m = RELAY.fullmatch(url or '')
    return m.group(2) if m else None


def apply_send(run, vehicle, apply):
    """LTEで送る項目と、中継の部屋。送り先のサーバーの名前は表示しない"""
    podium = api(run, '/api/podium')
    config, allowed = podium['config'], {c['name'] for c in podium['channels']}
    want = vehicle['send']
    urls = [config.get('server_url', '')] + list(config.get('backup_server_urls', []))
    rooms = [room_of(u) for u in urls]
    changes = []
    if config.get('channels') != want['channels']:
        changes.append(('LTEで送る項目', config.get('channels'), want['channels']))
    if any(r != want['room'] for r in rooms):
        changes.append(('中継の部屋', [r or '?' for r in rooms], want['room']))
    bad = setups.show('LTEで送る項目と部屋', changes)
    if not changes or not apply:
        return bad
    unknown = [n for n in want['channels'] if n not in allowed]
    if unknown:
        print('  ★本体に無い項目があるので変えません（先に信号の設定を入れる）: ' + ','.join(unknown))
        return 1
    body = {}
    if config.get('channels') != want['channels']:
        body['channels'] = want['channels']
    if any(r != want['room'] for r in rooms):
        if config.get('destination') != 'server' or any(r is None for r in rooms):
            print('  ★送り先が中継サーバー（…/ws/audio/<部屋>）ではないので、部屋は変えません')
            return 1
        body['server_url'] = RELAY.sub(lambda m: m.group(1) + want['room'], urls[0])
        body['backup_server_urls'] = [RELAY.sub(lambda m: m.group(1) + want['room'], u) for u in urls[1:]]
    api(run, '/api/podium', body)
    after = api(run, '/api/podium')['config']
    ok = after.get('channels') == want['channels'] and all(
        room_of(u) == want['room'] for u in [after.get('server_url', '')] + list(after.get('backup_server_urls', [])))
    print('  入れて、本体から読み直しました：' + ('設定と同じ' if ok else '★まだ違う'))
    return 0 if ok else 1


def main(argv=None, run=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--vehicle')
    ap.add_argument('--course')
    ap.add_argument('--apply', action='store_true', help='違う所を本体へ入れる（付けなければ確かめるだけ）')
    args = ap.parse_args(argv)
    if not args.vehicle and not args.course:
        ap.error('--vehicle か --course を指定してください（python setups.py list で一覧）')
    try:
        vehicle = setups.load('vehicle', args.vehicle) if args.vehicle else None
        course = setups.load('course', args.course) if args.course else None
    except setups.SetupError as exc:
        print(f'★ {exc}')
        return 2
    try:
        run = run or connect()
        bad = 0
        if course:
            files = course_files(run, args.apply)
            todo = [name for name, state in files if state != 'same']
            print(('○ 本体のコースの設定のファイル：PCと同じ' if not todo else
                   ('  コースの設定を本体へ置きました: ' if args.apply else '× 本体に無い・違うコースの設定: ') + '・'.join(todo)))
            bad += 0 if args.apply or not todo else 1
            bad += apply_line(run, course, args.apply)
        if vehicle:
            bad += apply_signals(run, vehicle, args.apply)
            bad += apply_send(run, vehicle, args.apply)
            print('（車載画面のしきい値は、この道具では入れません。いまは車載画面のソフトの中の値です）')
    except RuntimeError as exc:
        print(f'★ {exc}')
        return 1
    if not args.apply:
        print('（確かめただけで、本体は変えていません。入れるときは --apply）')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
