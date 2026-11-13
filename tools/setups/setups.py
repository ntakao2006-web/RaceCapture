"""車の設定とコースの設定（2026-11-13、SP-4-1・SP-4-2、`SPEC.md` 4章 P-1〜P-3）。

これまで「SUGO用にする」は道具を5本（tools/sugo_setup/）順に流す形で、設定の中身が道具のコードの中に散っていた。
ここでは設定を2種類のファイルに分けて持つ。**いまは確かめるだけ**で、本体へ入れる道具は展示のあと（SP-4-3）。

  vehicles/<名前>.json   車で決まるもの
      logger    本体が読む信号と換算（EcoCaptureの config.json と同じ形：profile・can_bitrate・signals）
      send      LTEでピットへ送る項目（channels）と、中継の部屋の名前（room）
      dash      車載画面の警告としきい値（油温・水温・油圧・シフトの回転数）
      analysis  解析が使う車の値（トレッドなど）
  courses/<名前>.json    コースで決まるもの
      line      コントロールライン・スタート・ゴール・セクターの線（本体の lap.json の line と同じ形）
      dash      車載画面の、コースで決まる値（ピットレーンの制限速度）
      confirm   線を変えるときに確認を1つ増やす速さ（racing_speed_kmh。SPEC.md 7-5）

  python setups.py list                                   # 入っている車・コース
  python setups.py check --vehicle ncec --course sugo     # ファイルの形を確かめる
  python setups.py check --vehicle ncec --course sugo --config <config.json> --lap <lap.json>
                                                          # 本体から取った設定（控え）と比べる
  python setups.py check --vehicle ncec --course sugo --device
                                                          # つないだ本体のいまの設定と比べる（読むだけ。何も変えない）

車の切り替えは信号が入れ替わるので走行記録のファイルが分かれ、コースの切り替えは記録を止めずにできる（SPEC.md 7-5）。
この分け方は、そのまま「どちらの設定に何を入れるか」の線引きになっている。
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = {'vehicle': HERE / 'vehicles', 'course': HERE / 'courses'}
NAME = re.compile(r'^[a-z0-9][a-z0-9_-]{0,31}$')            # 設定の名前（LTEで「名前だけ」送るので短い英数字）
SIGNAL_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]{0,31}$')   # EcoCapture-Web/models.py の Signal.name と同じ
SIGNAL_KEYS = ['channel', 'name', 'unit', 'can_id', 'extended', 'byte_offset', 'data_type', 'endian', 'scale', 'offset',
               'bit_mask', 'conversion', 'pullup_ohm', 'ntc_points']
LINE_KEYS = ['enabled', 'lat', 'lon', 'bearing', 'width_m', 'min_lap_s', 'max_lap_s', 'start', 'goal', 'total_laps',
             'time_limit_s', 'margin_s', 'pit_offset_m', 'pit_max_kmh', 'sectors']
GATE_KEYS = ['lat', 'lon', 'bearing', 'width_m']
VEHICLE_DASH = ['oil_warn', 'water_warn', 'oil_press_warn', 'oil_press_min_rpm', 'rpm_bar_start', 'shift_rpm', 'rpm_segments', 'limit_rpm']
COURSE_DASH = ['pit_speed_limit_kmh', 'pit_speed_warn_kmh', 'pit_lane_max_kmh']


class SetupError(ValueError):
    """設定ファイルの中身がおかしい。str() が、どのファイルの何が、どうおかしいか"""


def names(kind):
    return sorted(p.stem for p in KINDS[kind].glob('*.json'))


def load(kind, name):
    """設定を読んで、形を確かめて返す。おかしければ SetupError"""
    if not NAME.match(name or ''):
        raise SetupError(f'設定の名前「{name}」が使えません（英小文字・数字・_・- で32文字まで）')
    path = KINDS[kind] / f'{name}.json'
    if not path.is_file():
        raise SetupError(f'{path.name} がありません（あるのは {"・".join(names(kind)) or "なし"}）')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except ValueError as exc:
        raise SetupError(f'{path.name}：JSONとして読めません（{exc}）')
    problems = (validate_vehicle if kind == 'vehicle' else validate_course)(data)
    if data.get('id') != name:
        problems.insert(0, f'id が「{data.get("id")}」で、ファイルの名前「{name}」と違います')
    if problems:
        raise SetupError(f'{path.name}：' + '／'.join(problems))
    return data


def _number(value, low=None, high=None):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and \
        (low is None or value >= low) and (high is None or value <= high)


def validate_vehicle(data):
    """車の設定のおかしい所の一覧（無ければ空）"""
    out = []
    if data.get('format') != 1:
        out.append('format が 1 ではありません')
    logger = data.get('logger') or {}
    signals = logger.get('signals')
    if logger.get('can_bitrate') not in (125000, 250000, 500000, 1000000):
        out.append('logger.can_bitrate が 125000・250000・500000・1000000 のどれでもありません')
    if not isinstance(signals, list) or not signals:
        return out + ['logger.signals（本体が読む信号）がありません']
    if len(signals) > 64:
        out.append(f'信号が{len(signals)}個あります（本体は64個まで）')
    seen = set()
    for i, s in enumerate(signals):
        label = f'信号{i + 1}（{s.get("name")}）'
        if not SIGNAL_NAME.match(str(s.get('name') or '')):
            out.append(f'{label}：名前が使えません')
        if s.get('name') in seen:
            out.append(f'{label}：同じ名前が2つあります')
        seen.add(s.get('name'))
        missing = [k for k in SIGNAL_KEYS if k not in s]
        if missing:
            out.append(f'{label}：項目が足りません（{"・".join(missing)}）')
            continue
        if s['channel'] not in (1, 2) or not _number(s['can_id'], 0, 0x1FFFFFFF) or not _number(s['byte_offset'], 0, 7):
            out.append(f'{label}：channel・can_id・byte_offset の値が範囲の外です')
        if s['conversion'] == 'ntc' and not (s['pullup_ohm'] and len(s['ntc_points']) >= 2):
            out.append(f'{label}：換算 ntc には pullup_ohm と ntc_points（2点以上）が要ります')
    send = data.get('send') or {}
    known = seen | BUILT_IN_CHANNELS
    for ch in send.get('channels') or []:
        if ch not in known:
            out.append(f'send.channels の「{ch}」は、信号にも本体が自分で持つ値にもありません')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', str(send.get('room') or '')):
        out.append('send.room（中継の部屋の名前）が使えません')
    dash = data.get('dash') or {}
    for key in VEHICLE_DASH:
        if key not in dash:
            out.append(f'dash.{key} がありません')
    if all(_number(dash.get(k)) for k in ('rpm_bar_start', 'shift_rpm', 'limit_rpm')) and \
            not dash['rpm_bar_start'] < dash['shift_rpm'] <= dash['limit_rpm']:
        out.append('dash の回転数が rpm_bar_start < shift_rpm ≦ limit_rpm の順になっていません')
    return out


# 本体が信号の設定とは別に自分で持っている値（GNSS・IMU・ラップなど）。LTEで送る項目に書ける。
# EcoCapture-Web/models.py の CHANNELS・LAP_CHANNELS と同じ名前（試験 test_setups.py が食い違いを見張る）
BUILT_IN_CHANNELS = {
    'Speed', 'GPSSpeed', 'RPM', 'Throttle', 'BatteryVolt', 'Lat', 'Lon', 'Altitude', 'Yaw', 'GPSFix', 'GPSSats', 'GNSSHz',
    'AccelX', 'AccelY', 'AccelZ', 'GyroX', 'GyroY', 'GyroZ', 'Roll', 'Pitch', 'LongAccel', 'LatAccel', 'VertAccel',
    'Distance', 'WaterTemp',
    'LapCount', 'CurrentLap', 'LapTime', 'BestLap', 'ElapsedTime', 'RaceTime', 'LapsLeft', 'TimeLimit', 'Margin',
    'Sector', 'LastSector', 'SectorTime'}


def _gate_problems(gate, label):
    if not isinstance(gate, dict):
        return [f'{label}：線の形（lat・lon・bearing・width_m）になっていません']
    out = []
    if not _number(gate.get('lat'), -90, 90) or not _number(gate.get('lon'), -180, 180):
        out.append(f'{label}：場所（lat・lon）が範囲の外です')
    if not _number(gate.get('bearing'), 0, 360):
        out.append(f'{label}：向き（bearing）が 0〜360 の外です')
    if not _number(gate.get('width_m'), 1, 500):
        out.append(f'{label}：幅（width_m）が 1〜500 m の外です')
    return out


def validate_course(data):
    """コースの設定のおかしい所の一覧（無ければ空）"""
    out = []
    if data.get('format') != 1:
        out.append('format が 1 ではありません')
    line = data.get('line')
    if not isinstance(line, dict):
        return out + ['line（コントロールライン）がありません']
    missing = [k for k in LINE_KEYS if k not in line]
    if missing:
        out.append(f'line の項目が足りません（{"・".join(missing)}）')
    out += _gate_problems(line, 'コントロールライン')   # 周を数える線は必ず1本（本体の lap.py と同じ）
    for key, label in (('start', 'スタートの線'), ('goal', 'ゴールの線')):   # あれば1本ずつ
        if line.get(key) is not None:
            out += _gate_problems(line[key], label)
    for i, gate in enumerate(line.get('sectors') or []):
        out += _gate_problems(gate, f'セクター{i + 1}の終わりの線')
    if _number(line.get('min_lap_s')) and _number(line.get('max_lap_s')) and not 0 < line['min_lap_s'] < line['max_lap_s']:
        out.append('line の min_lap_s と max_lap_s の大小がおかしい')
    for key in COURSE_DASH:
        if key not in (data.get('dash') or {}):
            out.append(f'dash.{key} がありません')
    if not _number((data.get('confirm') or {}).get('racing_speed_kmh'), 1, 400):
        out.append('confirm.racing_speed_kmh（線を変えるときに確認を増やす速さ）がありません')
    return out


# ---------------------------------------------------------------- 比べる
def same(a, b):
    """数は丸めの差を許して比べる（本体はJSONを読み書きするので、末尾の桁がずれることがある）"""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b


def diff_vehicle(vehicle, config):
    """車の設定と、本体の設定（config.json・/api/config）の違い。[(項目, 本体のいま, 設定ファイル)]"""
    logger, out = vehicle['logger'], []
    for key in ('profile', 'can_bitrate'):
        if key in logger and not same(config.get(key), logger[key]):
            out.append((key, config.get(key), logger[key]))
    now = {s['name']: s for s in config.get('signals') or []}
    want = {s['name']: s for s in logger['signals']}
    for name in want:
        if name not in now:
            out.append((f'信号 {name}', '（無い）', '読む'))
            continue
        for key in SIGNAL_KEYS:
            if not same(now[name].get(key), want[name].get(key)):
                out.append((f'信号 {name} の {key}', now[name].get(key), want[name].get(key)))
    for name in now:
        if name not in want:
            out.append((f'信号 {name}', '読んでいる', '（設定ファイルに無い）'))
    if [s['name'] for s in config.get('signals') or [] if s['name'] in want] != [n for n in want if n in now]:
        out.append(('信号の並び', '違う', '設定ファイルの順'))
    return out


def diff_course(course, line):
    """コースの設定と、本体の線（lap.json の line・/api/lap の line）の違い"""
    return [(f'line.{key}', line.get(key), value) for key, value in course['line'].items() if not same(line.get(key), value)]


def diff_dash(vehicle, course, defaults):
    """車・コースの設定と、車載画面の既定値（RaceCapture-UNOQ/dash_model.py の DEFAULTS）の違い"""
    want = {**vehicle['dash'], **course['dash']}
    return [(f'dash.{key}', defaults.get(key), value) for key, value in want.items() if not same(defaults.get(key), value)]


def fill_analysis(cfg):
    """解析の設定（tools/race_analysis/*.json）に、コース・車の設定から線とトレッドを足して返す。
    "course": "sugo" と書けば line（コントロールラインの中心）を、"vehicle": "ncec" と書けば tread_m を、ここから読む。
    解析の設定に line・tread_m がじかに書いてあれば、そちらを使う（古い設定はそのまま動く）"""
    out = dict(cfg)
    if 'line' not in out and out.get('course'):
        line = load('course', out['course'])['line']
        out['line'] = [line['lat'], line['lon']]
    if 'tread_m' not in out and out.get('vehicle'):
        out['tread_m'] = load('vehicle', out['vehicle'])['analysis']['tread_m']
    return out


def read_device():
    """つないだ本体から、いまの設定と線を読む（読むだけ）。(config, line)"""
    sys.path.insert(0, str(REPO / 'tools' / 'collect_logs'))
    import unoq_link
    link = unoq_link.connect()
    print(f'本体: {link.label()}')
    api = 'http://127.0.0.1:8080'
    config = json.loads(link.run(f'curl -s -m 10 {api}/api/config', timeout=30))
    lap = json.loads(link.run(f'curl -s -m 10 {api}/api/lap', timeout=30))
    return config, lap.get('line') or {}


def show(title, changes):
    if not changes:
        print(f'○ {title}：同じ')
        return 0
    print(f'× {title}：違う所が{len(changes)}つ')
    for item, now, want in changes:
        print(f'    {item}: いま {json.dumps(now, ensure_ascii=False)} → 設定ファイル {json.dumps(want, ensure_ascii=False)}')
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('command', choices=['list', 'check'])
    ap.add_argument('--vehicle')
    ap.add_argument('--course')
    ap.add_argument('--config', type=Path, help='本体から取った config.json（控え）')
    ap.add_argument('--lap', type=Path, help='本体から取った lap.json（控え）')
    ap.add_argument('--device', action='store_true', help='つないだ本体のいまの設定と比べる（読むだけ）')
    args = ap.parse_args(argv)
    if args.command == 'list':
        for kind, label in (('vehicle', '車'), ('course', 'コース')):
            for name in names(kind):
                try:
                    print(f'{label}  {name}  {load(kind, name)["name"]}')
                except SetupError as exc:
                    print(f'{label}  {name}  ★{exc}')
        return 0
    try:
        vehicle = load('vehicle', args.vehicle) if args.vehicle else None
        course = load('course', args.course) if args.course else None
    except SetupError as exc:
        print(f'★ {exc}')
        return 2
    for kind, data in (('車', vehicle), ('コース', course)):
        if data:
            print(f'○ {kind}の設定「{data["id"]}」（{data["name"]}）：形は合っている')
    config = line = None
    if args.device:
        config, line = read_device()
    if args.config:
        config = json.loads(args.config.read_text(encoding='utf-8'))
    if args.lap:
        line = json.loads(args.lap.read_text(encoding='utf-8')).get('line') or {}
    bad = 0
    if vehicle and config is not None:
        bad += show('本体の信号の設定', diff_vehicle(vehicle, config))
    if course and line is not None:
        bad += show('本体の線', diff_course(course, line))
    if not args.device and config is None and line is None:
        print('（ファイルの形を確かめただけです。本体と比べるには --device か --config・--lap）')
    else:
        print('（確かめただけで、本体は変えていません）')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
