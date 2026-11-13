"""PCのアプリの「コースと線」の段（2026-11-13、SP-4-4・SP-4-10・SP-4-11 のうちコースと線の分。`SPEC.md` 4章 T-5、7-5）。

本体のラップの線（コントロールライン・スタート・ゴール・セクターの終わり）を、航空写真の上で見る・引き直す・本体へ入れる。
ここは、読む・比べる・確かめるだけの部品（本体やLTEへは送らない。送るのは app_ops.py）。

  pc_courses()            PCにあるコースの設定（tools/setups/courses/）。読むだけで、書き換えない
  clean(line)             画面から来た線を、本体の lap.json の line と同じ平らな形にそろえる
  problems(line)          形のおかしい所の一覧（本体の決まり EcoCapture-Web/lap.py の LapLine と同じ範囲。無ければ空）
  changes(now, new)       変わる所（どの線が何m動くか・幅・向き・足す／消す）を、確認の画面に出す文にする
  match(line, courses)    線が、PCのどのコースの設定と同じか（名前。無ければ None）
  speed(telemetry)        本体の /api/telemetry から車速（km/h。分からなければ None）
  device_view(...)        見張り（now_status.py）が読んだ値から、この段に出す「本体のいま」を作る
  view(app)               画面へ渡すまとめ（/api/state の course）

線の形：コントロールラインは line の直下（lat・lon・bearing・width_m）、start・goal は線1本か None、sectors は線の並び。
本体は線を「矢印の向きに横切ったときだけ」数える（lap.py の crossing_point）。両方向で数える仕組みは本体に無いので、
画面にも「両方向」は出していない。
"""
import math
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools' / 'setups'))

GATE_KEYS = ('lat', 'lon', 'bearing', 'width_m')
# 線のほかに、コースの設定が持っている値（PCの設定をそのまま入れるときだけ一緒に送る）：(言い方, 下限, 上限)
RACE_KEYS = {
    'min_lap_s': ('1周の最短（秒）', 5, 7200), 'max_lap_s': ('1周の最長（秒）', 10, 86400),
    'total_laps': ('走る周の数', 1, 1000), 'time_limit_s': ('規定時間（秒）', 0, 86400), 'margin_s': ('余裕（秒）', 0, 3600),
    'pit_offset_m': ('ピットレーンまでの横の離れ（m）', -100, 100), 'pit_max_kmh': ('ピットレーンとみなす速さ（km/h）', 0, 300),
}
MAX_SECTORS = 9             # 本体の決まり（lap.py の MAX_SECTOR_LINES）
WIDTH_M = (5, 200)          # 本体の決まり（lap.py の width_m）
DEFAULT_WIDTH_M = 30
DEFAULT_RACING_KMH = 60     # コースの設定が分からないときの目安（確認を1つ増やす速さ）
SAME_PLACE_M = 0.005        # これより近ければ「場所は同じ」
M_PER_DEG = 111320.0
COURSES_KEEP_S = 5
_courses = (0.0, [])


def setups():
    import setups as module
    return module


def pc_courses():
    """PCにあるコースの設定。[{id, name, line, racing_speed_kmh}]。形のおかしいファイルは {id, name, error}"""
    global _courses
    made, found = _courses
    if time.time() - made < COURSES_KEEP_S:
        return found
    s, found = setups(), []
    for name in s.names('course'):
        try:
            course = s.load('course', name)
            found.append({'id': name, 'name': course['name'], 'line': course['line'],
                          'racing_speed_kmh': course['confirm']['racing_speed_kmh']})
        except s.SetupError as exc:
            found.append({'id': name, 'name': name, 'error': str(exc)})
    _courses = (time.time(), found)
    return found


def course(name):
    return next((c for c in pc_courses() if c['id'] == name and 'line' in c), None)


def number(value, low=None, high=None):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and \
        (low is None or value >= low) and (high is None or value <= high)


# ---------------------------------------------------------------- 形をそろえる・確かめる
def clean_gate(gate):
    if not isinstance(gate, dict):
        return gate   # 形になっていないものは problems が拾う
    return {'lat': gate.get('lat'), 'lon': gate.get('lon'), 'bearing': gate.get('bearing'),
            'width_m': gate.get('width_m', DEFAULT_WIDTH_M)}


def clean(line):
    """画面から来た線を、本体へ送る形にそろえる。線はまるごと（start・goal・sectors は、無ければ「無し」として送る）。
    知らない項目と set_at（本体が付ける）は落とす。線でないものは ValueError"""
    if not isinstance(line, dict):
        raise ValueError('線の形になっていません')
    out = {'enabled': True, **clean_gate(line)}
    for key in ('start', 'goal'):
        out[key] = None if line.get(key) is None else clean_gate(line[key])
    sectors = line.get('sectors') or []
    out['sectors'] = [clean_gate(g) for g in sectors] if isinstance(sectors, list) else sectors
    for key in RACE_KEYS:
        if key in line:
            out[key] = line[key]
    return out


def gate_problems(gate, label, need_bearing=False):
    if not isinstance(gate, dict):
        return [f'{label}：線の形（場所・向き・幅）になっていません']
    out = []
    if not number(gate.get('lat'), -90, 90) or not number(gate.get('lon'), -180, 180):
        out.append(f'{label}：場所（緯度・経度）が入っていないか、範囲の外です')
    bearing = gate.get('bearing')
    if bearing is None:
        if need_bearing:
            out.append(f'{label}：進む向きが要ります（セクターの線は、向きを自分で覚えません）')
    elif not number(bearing, 0, 360) or bearing >= 360:
        out.append(f'{label}：進む向きが 0〜359.5° の外です')
    if not number(gate.get('width_m'), *WIDTH_M):
        out.append(f'{label}：幅が {WIDTH_M[0]}〜{WIDTH_M[1]} m の外です')
    return out


def problems(line):
    """形のおかしい所の一覧（無ければ空）。line は clean したもの"""
    if line.get('lat') is None and line.get('lon') is None:
        out = ['コントロールライン（周を数える線）がありません。1本要ります']
    else:
        out = gate_problems(line, 'コントロールライン')
    for key, label in (('start', 'スタートの線'), ('goal', 'ゴールの線')):
        if line.get(key) is not None:
            out += gate_problems(line[key], label)
    sectors = line.get('sectors')
    if not isinstance(sectors, list):
        return out + ['セクターの線の並びになっていません']
    if len(sectors) > MAX_SECTORS:
        out.append(f'セクターの線が{len(sectors)}本あります（本体は{MAX_SECTORS}本まで）')
    for i, gate in enumerate(sectors):
        out += gate_problems(gate, f'セクター{i + 1}の終わりの線', need_bearing=True)
    for key, (label, low, high) in RACE_KEYS.items():
        value = line.get(key)
        if key in ('min_lap_s', 'max_lap_s') and key in line and value is None:
            out.append(f'{label}が入っていません')
        elif value is not None and (not number(value, low, high) or (key == 'total_laps' and not isinstance(value, int))
                                    or (key in ('time_limit_s', 'pit_max_kmh') and value <= 0)):
            out.append(f'{label}が {low}〜{high} の外です')
    if number(line.get('min_lap_s')) and number(line.get('max_lap_s')) and line['max_lap_s'] <= line['min_lap_s']:
        out.append('1周の最長が、最短より長くなっていません')
    return out


# ---------------------------------------------------------------- 比べる
def control(line):
    """コントロールラインを線1本の形で（無ければ None）"""
    if not isinstance(line, dict) or not line.get('enabled') or line.get('lat') is None or line.get('lon') is None:
        return None
    return {key: line.get(key) for key in GATE_KEYS}


def gates(line):
    """[(名前, 線か None)]：コントロールライン・スタート・ゴール。セクターは sector_gates"""
    line = line if isinstance(line, dict) else {}
    return [('コントロールライン', control(line)), ('スタート', line.get('start') if line.get('enabled') else None),
            ('ゴール', line.get('goal') if line.get('enabled') else None)]


def sector_gates(line):
    return list(line.get('sectors') or []) if isinstance(line, dict) and line.get('enabled') else []


def count(line):
    return sum(1 for _, g in gates(line) if g) + len(sector_gates(line))


def moved_m(a, b):
    """a から b へ、(動いた長さm, 方角の言葉)"""
    north = (b['lat'] - a['lat']) * M_PER_DEG
    east = (b['lon'] - a['lon']) * M_PER_DEG * math.cos(math.radians(a['lat']))
    words = ['北', '北東', '東', '南東', '南', '南西', '西', '北西']
    return math.hypot(north, east), words[round(math.degrees(math.atan2(east, north)) / 45) % 8]


def deg(value):
    return '通ったときに覚える' if value is None else f'{value:g}°'


def gate_text(gate):
    return f"幅 {gate.get('width_m'):g} m・向き {deg(gate.get('bearing'))}"


def gate_change(name, a, b):
    """線1本の変わる所（文。変わらなければ None）"""
    if a is None and b is None:
        return None
    if a is None:
        return f"足す：{name}（{b['lat']:.7f}, {b['lon']:.7f}・{gate_text(b)}）"
    if b is None:
        return f'消す：{name}'
    parts = []
    distance, way = moved_m(a, b)
    if distance >= SAME_PLACE_M:
        parts.append(f'{way}へ {distance:.2f} m 動かす')
    if not same_number(a.get('width_m'), b.get('width_m')):
        parts.append(f"幅 {a.get('width_m'):g} → {b.get('width_m'):g} m")
    if not same_number(a.get('bearing'), b.get('bearing')):
        parts.append(f"向き {deg(a.get('bearing'))} → {deg(b.get('bearing'))}")
    return f"{name}：{'・'.join(parts)}" if parts else None


def same_number(a, b):
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def changes(now, new):
    """本体のいまの線 now を new にすると変わる所。(文の一覧, セクターの線が変わるか)。
    一覧が空なら、変わる所は無い。new に入っていない「線のほかの値」は、本体のものをそのまま残すので比べない"""
    out = []
    for (name, a), (_, b) in zip(gates(now), gates(new)):
        text = gate_change(name, a, b)
        if text:
            out.append(text)
    old, want = sector_gates(now), sector_gates(new)
    sector_changed = False
    for i in range(max(len(old), len(want))):
        text = gate_change(f'セクター{i + 1}の終わり', old[i] if i < len(old) else None, want[i] if i < len(want) else None)
        if text:
            out.append(text)
            sector_changed = True
    for key, (label, _, _) in RACE_KEYS.items():
        if key in new and not same_number((now or {}).get(key), new[key]):
            show = lambda v: '無し' if v is None else f'{v:g}'  # noqa: E731
            out.append(f'{label}：{show((now or {}).get(key))} → {show(new[key])}')
    if out:
        out.insert(0, f'線 {count(now)}本 → {count(new)}本')
    return out, sector_changed


def lines_moved(now, new):
    """線そのもの（場所・幅・向き・本数）が変わるか。「線のほかの値」だけの違いは数えない"""
    pairs = list(zip(gates(now), gates(new)))
    old, want = sector_gates(now), sector_gates(new)
    return any(gate_change(name, a, b) for (name, a), (_, b) in pairs) or len(old) != len(want) or \
        any(gate_change('', a, b) for a, b in zip(old, want))


def describe(line):
    """線の一覧を文にする（本体のいまの線が分からないときに「送る線」として出す）"""
    out = [f'線 {count(line)}本']
    for name, gate in gates(line):
        if gate:
            out.append(f"{name}：{gate['lat']:.7f}, {gate['lon']:.7f}・{gate_text(gate)}")
    for i, gate in enumerate(sector_gates(line)):
        out.append(f"セクター{i + 1}の終わり：{gate['lat']:.7f}, {gate['lon']:.7f}・{gate_text(gate)}")
    return out


def match(line, courses=None):
    """線が、PCのどのコースの設定と同じか（名前。同じものが無ければ None）"""
    if not isinstance(line, dict):
        return None
    s = setups()
    for c in pc_courses() if courses is None else courses:
        if 'line' in c and not s.diff_course({'line': c['line']}, line):
            return c['id']
    return None


def racing_kmh(*course_ids):
    """確認を1つ増やす速さ。(km/h, どこから決めたかの言葉)。はじめに見つかったコースの設定を使う"""
    for name in course_ids:
        c = course(name) if name else None
        if c:
            return c['racing_speed_kmh'], f"コースの設定「{name}」のレーシングスピード {c['racing_speed_kmh']:g} km/h"
    return DEFAULT_RACING_KMH, f'コースの設定が分からないので、{DEFAULT_RACING_KMH} km/h を目安にしています'


# ---------------------------------------------------------------- 本体から読んだ値
def sample_values(telemetry):
    sample = (telemetry or {}).get('sample') if isinstance(telemetry, dict) else None
    values = sample.get('values') if isinstance(sample, dict) else None
    return values if isinstance(values, dict) else {}


def speed(telemetry):
    """本体の /api/telemetry から車速（km/h）。車の信号の Speed と GNSSの GPSSpeed のうち、読めているものの大きい方。
    どちらも読めなければ None（測位していない・値が届いていない）"""
    values = sample_values(telemetry)
    found = [values[key] for key in ('Speed', 'GPSSpeed') if number(values.get(key), 0, 1000)]
    return max(found) if found else None


def position(telemetry):
    """車のいまの位置。{'lat', 'lon', 'yaw', 'speed_kmh', 'hacc_m'}。測位していなければ None"""
    values = sample_values(telemetry)
    if not number(values.get('GPSFix'), 3) or not number(values.get('Lat'), -90, 90) or not number(values.get('Lon'), -180, 180):
        return None
    hacc = (telemetry.get('sample') or {}).get('gnss_hacc_m')
    return {'lat': values['Lat'], 'lon': values['Lon'], 'yaw': values['Yaw'] if number(values.get('Yaw'), 0, 360) else None,
            'speed_kmh': values['GPSSpeed'] if number(values.get('GPSSpeed'), 0) else None, 'hacc_m': hacc if number(hacc, 0) else None}


def vehicle_view(config):
    """本体が読んでいる信号が、PCにある車の設定と同じか（setups.diff_vehicle）。本体は車の名前を持っていないので、中身で比べる。
    いちばん違いの少ない設定について {id, name, same, count, diffs（はじめの数個の文）}。比べられなければ None"""
    if not isinstance(config, dict):
        return None
    s, best = setups(), None
    for name in s.names('vehicle'):
        try:
            vehicle = s.load('vehicle', name)
            found = s.diff_vehicle(vehicle, config)
        except (ValueError, KeyError, TypeError):
            continue
        if best is None or len(found) < best['count']:
            best = {'id': name, 'name': vehicle['name'], 'same': not found, 'count': len(found),
                    'diffs': [f'{item}：本体 {now} → 設定 {want}' for item, now, want in found[:6]]}
    return best


def device_view(lap, telemetry=None, config=None):
    """見張りが読んだ /api/lap・/api/telemetry・/api/config から、「本体のいま」を作る。線が読めなければ None"""
    if not isinstance(lap, dict) or not isinstance(lap.get('line'), dict):
        return None
    return {'line': lap['line'], 'running': bool(lap.get('running')), 'laps': (lap.get('values') or {}).get('LapCount'),
            'speed_kmh': speed(telemetry), 'vehicle': vehicle_view(config), 'read_at': time.time(), 'sent': False}


def view(app):
    """画面へ渡すまとめ。device は本体の線（つながっていない間は、最後に分かっているもの。live が偽）"""
    now = getattr(app, 'now', None) or {}
    connected = now.get('phase') == 'connected'
    courses = pc_courses()
    device = now.get('course')
    if device:
        device = {**device, 'match': match(device['line'], courses), 'live': connected and not device.get('sent')}
    return {'connected': connected, 'via': now.get('via') or '', 'device': device, 'courses': courses,
            'default_racing_kmh': DEFAULT_RACING_KMH}
