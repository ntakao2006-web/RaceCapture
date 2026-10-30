"""走行映像に焼き込む計器の設定（hud.ini）を読み、1枚分の四角形を組み立てる。

本体の録画（tools/unoq_overlay_enc/overlay_rec.c）は hud_layout.h で同じことをする。これはその写しで、
PCの見た目の確認（hud_preview.py）と、本体へ送る前の確かめ（hud_apply.py）が使う。
規則を変えたら hud_layout.h と両方を直し、test_hud_layout.py を通す
（testdata/*.golden は本体の hud_dump で作った頂点。手順書 unoq_video_check_procedure.md 5-14）。

座標は1920x1080・左上が0。四角形は (x[4], y[4], u0, v0, u1, v1, 色) で、u0が負なら塗りつぶし、
そうでなければ文字の一覧表（hud_font_64.pgm）の (u0, v0)〜(u1, v1) を貼る。
"""
import math
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONT = HERE.parent / 'unoq_overlay_enc' / 'hud_font_64.pgm'
DEFAULT_INI = HERE.parent / 'unoq_overlay_enc' / 'hud_default.ini'

HUD_ITEMS, HUD_REFS, HUD_REF_LEN, HUD_STR, HUD_COLORS = 64, 32, 96, 48, 32
HUD_SECS, HUD_KVS, HUD_LINE, HUD_VAL = 80, 48, 1024, 160
QUADS_MAX = 12000 // 6


def f32(v):
    """Cのfloatに入れたときの値"""
    return struct.unpack('f', struct.pack('f', v))[0]


def c4(*v):
    return tuple(f32(x) for x in v)


WHITE, GREY, DIM = c4(.95, .97, 1, 1), c4(.65, .7, .75, 1), c4(.55, .6, .65, 1)
YELLOW, RED, GREEN = c4(1, .8, 0, 1), c4(1, .2, .15, 1), c4(.25, .9, .35, 1)
PANEL, TRACK, BLACK = c4(0, 0, 0, .55), c4(.2, .2, .22, .7), c4(0, 0, 0, 1)
BUILTIN_COLORS = {'white': WHITE, 'grey': GREY, 'gray': GREY, 'dim': DIM, 'yellow': YELLOW, 'red': RED,
                  'green': GREEN, 'panel': PANEL, 'track': TRACK, 'black': BLACK}

TYPES = ['box', 'text', 'value', 'bar', 'gball', 'clock']
KEYS = [
    'rect color',
    'x y size color align text',
    'x y size color align value scale offset decimals prefix unit format missing_color'
    ' warn_at alarm_at warn_below alarm_below warn_color alarm_color',
    'rect value scale offset min max direction color warn_at alarm_at warn_below alarm_below warn_color alarm_color'
    ' track_color tick_every tick_color tick_width',
    'center radius full x_value y_value flip_x flip_y ring_color cross_color color dot line_width',
    'x y size color align',
]
NEED = ['rect', 'x y text', 'x y value', 'rect value max', 'center radius', 'x y']


class HudError(Exception):
    def __init__(self, line, msg):
        super().__init__(f'{line}行目: {msg}' if line > 0 else msg)
        self.line, self.msg = line, msg


@dataclass
class Item:
    name: str
    type: str
    line: int
    show: str = 'always'
    right: bool = False
    laptime: bool = False
    decimals: int = -1
    dir: str = 'right'
    flip_x: bool = False
    flip_y: bool = False
    box: tuple = None
    ref: int = -1
    ref2: int = -1
    x: float = 0.0
    y: float = 0.0
    size: float = 1.0
    rect: tuple = (0.0, 0.0, 0.0, 0.0)
    tick_width: float = 3.0
    radius: float = 0.0
    line_width: float = 3.0
    dot: float = 18.0
    color: tuple = WHITE
    missing: tuple = None
    warn_c: tuple = YELLOW
    alarm_c: tuple = RED
    box_c: tuple = PANEL
    track_c: tuple = TRACK
    tick_c: tuple = PANEL
    ring_c: tuple = GREY
    cross_c: tuple = DIM
    warn_at: float = math.nan
    alarm_at: float = math.nan
    warn_below: float = math.nan
    alarm_below: float = math.nan
    scale: float = 1.0
    offset: float = 0.0
    min: float = 0.0
    max: float = math.nan
    tick_every: float = 0.0
    full: float = 1.5
    text: str = ''
    prefix: str = ''
    unit: str = ''


@dataclass
class Hud:
    items: list = field(default_factory=list)
    refs: list = field(default_factory=list)  # 値の名前（"values.Speed|values.GPSSpeed" の形のまま）
    nodata_after: float = 1.5
    preview: dict = field(default_factory=dict)  # [preview] の仮の値（PCの確認だけで使う）


def _ident(s, extra=''):
    return bool(s) and all(c.isascii() and (c.isalnum() or c == '_' or c in extra) for c in s)


def _num(s):
    if not s or any(c not in '+-.0123456789eE' for c in s):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _nums(s, n):
    parts = [p for p in re.split(r'[ \t,]+', s) if p]
    if len(parts) != n:
        return None
    out = [_num(p) for p in parts]
    return None if any(v is None for v in out) else out


def _color(s, user):
    if s.startswith('#'):
        h = s[1:]
        if len(h) not in (6, 8) or any(c not in '0123456789abcdefABCDEF' for c in h):
            return None
        v = [f32(int(h[i:i + 2], 16) / 255.0) for i in range(0, len(h), 2)]
        return tuple(v + [1.0]) if len(v) == 3 else tuple(v)
    if s[:1].isascii() and s[:1].isalpha():
        return user.get(s.lower()) or BUILTIN_COLORS.get(s.lower())
    d = _nums(s, 4)
    if d is None:
        d = _nums(s, 3)
        if d is None:
            return None
        d.append(1.0)
    if any(v < 0 or v > 1 for v in d):
        return None
    return tuple(f32(v) for v in d)


def _str(s):
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1]
    if len(s) >= HUD_STR or any(not (32 <= ord(c) <= 126) for c in s):
        return None
    return s


def _refspec(s):
    if len(s) >= HUD_REF_LEN or not _ident(s, '.|') or s.startswith('|') or s.endswith('|') or '||' in s:
        return False
    for alt in s.split('|'):
        if '.' in alt:
            d = alt.index('.')
            if d == 0 or d == len(alt) - 1 or '.' in alt[d + 1:]:
                return False
    return True


def _blen(s):
    return len(s.encode('utf-8'))


def _read_sections(text):
    if text.startswith('﻿'):  # メモ帳が付けることがある印（BOM）
        text = text[1:]
    secs = []
    raw_lines = text.split('\n')
    if raw_lines and raw_lines[-1] == '':
        raw_lines.pop()
    for line, raw in enumerate(raw_lines, 1):
        if _blen(raw) >= HUD_LINE:
            raise HudError(line, '1行が長すぎる')
        s = raw.strip(' \t\r')
        if not s or s[0] in '#;':
            continue
        if s[0] == '[':
            q = s.find(']')
            if q < 0 or q != len(s) - 1:
                raise HudError(line, '[名前] の形になっていない')
            name = s[1:q].strip(' \t\r')
            if _blen(name) >= 40 or not _ident(name):
                raise HudError(line, f'[{name}]：名前は英数字と _ で39文字まで')
            for other in secs:
                if other['name'] == name:
                    raise HudError(line, f'[{name}] が2つある（{other["line"]}行目にもある）')
            if len(secs) >= HUD_SECS:
                raise HudError(line, f'[名前] が多すぎる（{HUD_SECS}個まで）')
            secs.append({'name': name, 'line': line, 'kv': {}})
            continue
        eq = s.find('=')
        if eq < 0:
            raise HudError(line, '「キー = 値」の形になっていない（説明の行は頭に # を付ける）')
        if not secs:
            raise HudError(line, '最初の [名前] より前に書いてある')
        k, v = s[:eq].strip(' \t\r'), s[eq + 1:].strip(' \t\r')
        cs = secs[-1]
        if not k or _blen(k) >= 32:
            raise HudError(line, 'キーが空か長すぎる')
        if _blen(v) >= HUD_VAL:
            raise HudError(line, f'値が長すぎる（{HUD_VAL - 1}文字まで）')
        if not v:
            raise HudError(line, f'{k} の値が空')
        if k in cs['kv']:
            raise HudError(line, f'[{cs["name"]}] に {k} が2つある（{cs["kv"][k][1]}行目にもある）')
        if len(cs['kv']) >= HUD_KVS:
            raise HudError(line, f'[{cs["name"]}] のキーが多すぎる')
        cs['kv'][k] = (v, line)
    return secs


def _add_ref(hud, spec):
    if spec in hud.refs:
        return hud.refs.index(spec)
    if len(hud.refs) >= HUD_REFS:
        return -2
    hud.refs.append(spec)
    return len(hud.refs) - 1


def _item(hud, sec, user):
    kv = sec['kv']
    if 'type' not in kv:
        raise HudError(sec['line'], f'[{sec["name"]}] に type が無い（box text value bar gball clock のどれか）')
    tval, tline = kv['type']
    if tval not in TYPES:
        raise HudError(tline, f'type「{tval}」は無い（box text value bar gball clock のどれか）')
    if len(hud.items) >= HUD_ITEMS:
        raise HudError(sec['line'], f'計器が多すぎる（{HUD_ITEMS}個まで）')
    ti = TYPES.index(tval)
    it = Item(sec['name'], tval, sec['line'])
    it.color = GREEN if tval == 'bar' else YELLOW if tval == 'gball' else WHITE
    ref1, ref2 = ('values.LatAccel', 'values.LongAccel') if tval == 'gball' else (None, None)
    has_missing = has_box_c = False
    allowed = KEYS[ti].split()

    for k, (v, line) in kv.items():
        if k == 'type':
            continue
        if k not in ('show', 'box', 'box_color') and k not in allowed:
            raise HudError(line, f'{tval} に「{k}」は使えない（使えるのは：type show box box_color {KEYS[ti]}）')

        def num():
            d = _num(v)
            if d is None:
                raise HudError(line, f'{k} は数で書く（「{v}」）')
            return d

        def positive():
            d = num()
            if not d > 0:
                raise HudError(line, f'{k} は0より大きい数')
            return d

        def color():
            c = _color(v, user)
            if c is None:
                raise HudError(line, f'{k} の色「{v}」が分からない')
            return c

        if k == 'show':
            if v not in ('always', 'nodata', 'never'):
                raise HudError(line, f'show は always nodata never のどれか（「{v}」）')
            it.show = v
        elif k in ('box', 'rect'):
            d = _nums(v, 4)
            if d is None:
                raise HudError(line, f'{k} は「左 上 右 下」の4つの数（「{v}」）')
            if k == 'rect' and (d[2] <= d[0] or d[3] <= d[1]):
                raise HudError(line, f'rect は右が左より、下が上より大きい数（「{v}」）')
            setattr(it, k, tuple(f32(x) for x in d))
        elif k == 'box_color':
            it.box_c, has_box_c = color(), True
        elif k == 'center':
            d = _nums(v, 2)
            if d is None:
                raise HudError(line, f'center は「x y」の2つの数（「{v}」）')
            it.x, it.y = f32(d[0]), f32(d[1])
        elif k in ('x', 'y'):
            setattr(it, k, f32(num()))
        elif k in ('size', 'radius', 'dot', 'line_width', 'tick_width'):
            setattr(it, k, f32(positive()))
        elif k == 'full':
            it.full = positive()
        elif k == 'tick_every':
            it.tick_every = num()
            if it.tick_every < 0:
                raise HudError(line, 'tick_every は0以上（0で目盛り無し）')
        elif k in ('scale', 'offset', 'min', 'max', 'warn_at', 'alarm_at', 'warn_below', 'alarm_below'):
            setattr(it, k, num())
        elif k == 'decimals':
            d = _num(v)
            if d is None or d != math.floor(d) or d < 0 or d > 6:
                raise HudError(line, f'decimals は0〜6の整数（「{v}」）')
            it.decimals = int(d)
        elif k in ('flip_x', 'flip_y'):
            if v not in ('0', '1'):
                raise HudError(line, f'{k} は0か1（「{v}」）')
            setattr(it, k, v == '1')
        elif k == 'align':
            if v not in ('left', 'right'):
                raise HudError(line, f'align は left か right（「{v}」）')
            it.right = v == 'right'
        elif k == 'format':
            if v not in ('number', 'laptime'):
                raise HudError(line, f'format は number か laptime（「{v}」）')
            it.laptime = v == 'laptime'
        elif k == 'direction':
            if v not in ('right', 'left', 'up', 'down'):
                raise HudError(line, f'direction は right left up down のどれか（「{v}」）')
            it.dir = v
        elif k in ('text', 'prefix', 'unit'):
            s = _str(v)
            if s is None:
                raise HudError(line, f'{k} は英数字と記号だけ・{HUD_STR - 1}文字まで（日本語は出せない）（「{v}」）')
            setattr(it, k, s)
        elif k in ('value', 'x_value', 'y_value'):
            if not _refspec(v):
                raise HudError(line, f'{k} の値の名前「{v}」の形が違う（例：values.RPM、values.Speed|values.GPSSpeed）')
            if k == 'y_value':
                ref2 = v
            else:
                ref1 = v
        elif k == 'color':
            it.color = color()
        elif k == 'missing_color':
            it.missing, has_missing = color(), True
        elif k == 'warn_color':
            it.warn_c = color()
        elif k == 'alarm_color':
            it.alarm_c = color()
        elif k == 'track_color':
            it.track_c = color()
        elif k == 'tick_color':
            it.tick_c = color()
        elif k == 'ring_color':
            it.ring_c = color()
        elif k == 'cross_color':
            it.cross_c = color()

    for w in NEED[ti].split():
        if w not in kv:
            raise HudError(sec['line'], f'[{sec["name"]}]（{tval}）に {w} が無い')
    if has_box_c and it.box is None:
        raise HudError(kv['box_color'][1], 'box_color は box と一緒に書く')
    if not has_missing:
        it.missing = it.color
    if tval == 'text' and not it.text:
        raise HudError(kv['text'][1], 'text が空')
    if tval == 'value':
        if it.decimals < 0:
            it.decimals = 2 if it.laptime else 0
        if it.laptime and it.decimals not in (1, 2):
            raise HudError(kv['decimals'][1], 'format = laptime の decimals は1か2')
    if tval == 'bar':
        if not it.max > it.min:
            raise HudError(kv['max'][1], 'max は min（既定0）より大きい数')
        if it.tick_every > 0 and (it.max - it.min) / it.tick_every > 200:
            raise HudError(kv['tick_every'][1], '目盛りが多すぎる（200本まで）')
    for attr, spec in (('ref', ref1), ('ref2', ref2)):
        if spec:
            i = _add_ref(hud, spec)
            if i < 0:
                raise HudError(sec['line'], f'値の名前が多すぎる（{HUD_REFS}種類まで）')
            setattr(it, attr, i)
    hud.items.append(it)


def parse(text):
    """hud.ini の中身を読む。誤りがあれば HudError（「N行目: …」）"""
    secs = _read_sections(text)
    hud = Hud()
    user = {}
    for sec in secs:
        if sec['name'] == 'colors':
            for k, (v, line) in sec['kv'].items():
                if not _ident(k):
                    raise HudError(line, f'色の名前は英数字と _（「{k}」）')
                if len(user) >= HUD_COLORS:
                    raise HudError(line, f'色が多すぎる（{HUD_COLORS}個まで）')
                c = _color(v, user)
                if c is None:
                    raise HudError(line, f'色「{v}」が分からない')
                user.setdefault(k.lower(), c)
        elif sec['name'] == 'hud':
            for k, (v, line) in sec['kv'].items():
                if k != 'nodata_after':
                    raise HudError(line, f'[hud] に「{k}」は使えない（使えるのは nodata_after）')
                d = _num(v)
                if d is None or not d > 0:
                    raise HudError(line, 'nodata_after は0より大きい数（秒）')
                hud.nodata_after = d
    for sec in secs:
        if sec['name'] in ('colors', 'hud'):
            continue
        if sec['name'] == 'preview':  # 本体は読まない。PCの確認用の仮の値
            for k, (v, line) in sec['kv'].items():
                d = _num(v)
                if not _refspec(k) or '|' in k or d is None:
                    raise HudError(line, f'[preview] は「値の名前 = 数」で書く（「{k} = {v}」）')
                hud.preview[k] = d
            continue
        _item(hud, sec, user)
    return hud


def load(path):
    return parse(Path(path).read_text(encoding='utf-8'))


# ---------------------------------------------------------------- 1枚分を組み立てる
@dataclass
class Font:
    cell_w: int
    cell_h: int
    first: int
    count: int
    cols: int
    width: int
    height: int
    pixels: bytes = b''


def load_font(path=FONT):
    data = Path(path).read_bytes()
    meta, pos = {}, 0
    lines = []
    while len(lines) < 4:  # P5 / # atlas … / w h / 255
        end = data.index(b'\n', pos)
        lines.append(data[pos:end].decode('ascii'))
        pos = end + 1
    cw, ch, first, count, cols = (int(x) for x in lines[1].split()[2:7])
    w, h = (int(x) for x in lines[2].split())
    meta = Font(cw, ch, first, count, cols, w, h, data[pos:pos + w * h])
    return meta


class Builder:
    """hud_layout.h の quad4・rect・seg・text と同じ形で四角形をためる"""

    def __init__(self, font):
        self.font, self.quads = font, []

    def quad4(self, xs, ys, u0, v0, u1, v1, c):
        if len(self.quads) >= QUADS_MAX:
            return
        self.quads.append((tuple(xs), tuple(ys), u0, v0, u1, v1, c))

    def rect(self, x0, y0, x1, y1, c):
        self.quad4((x0, x1, x1, x0), (y0, y0, y1, y1), -1, -1, -1, -1, c)

    def seg(self, x0, y0, x1, y1, w, c):
        dx, dy = x1 - x0, y1 - y0
        ln = math.sqrt(dx * dx + dy * dy)
        if ln <= 0:
            return
        nx, ny = -dy / ln * w / 2, dx / ln * w / 2
        self.quad4((x0 + nx, x1 + nx, x1 - nx, x0 - nx), (y0 + ny, y1 + ny, y1 - ny, y0 - ny), -1, -1, -1, -1, c)

    def text(self, x, y, s, c, string):
        f = self.font
        for n, ch in enumerate(string[:64]):
            i = ord(ch) - f.first
            if i < 0 or i >= f.count:
                i = 0
            u0, v0 = (i % f.cols) * f.cell_w / f.width, (i // f.cols) * f.cell_h / f.height
            u1, v1 = u0 + f.cell_w / f.width, v0 + f.cell_h / f.height
            x0 = x + n * f.cell_w * s
            x1, y1 = x0 + f.cell_w * s, y + f.cell_h * s
            self.quad4((x0, x1, x1, x0), (y, y, y1, y1), u0, v0, u1, v1, c)

    def text_w(self, s, string):
        return len(string) * self.font.cell_w * s


def fmt_laptime(minutes, decimals):
    if math.isnan(minutes) or minutes < 0:
        return '-:--.-' if decimals == 1 else '-:--.--'
    sec = minutes * 60
    m = int(sec / 60)
    s = sec - m * 60
    return f'{m}:{s:04.1f}' if decimals == 1 else f'{m}:{s:05.2f}'


def _val(it, v, ref):
    if ref < 0:
        return math.nan
    x = v[ref]
    return x if math.isnan(x) else x * it.scale + it.offset


def _pick(it, x):
    if math.isnan(x):
        return it.missing
    if (not math.isnan(it.alarm_at) and x >= it.alarm_at) or (not math.isnan(it.alarm_below) and x < it.alarm_below):
        return it.alarm_c
    if (not math.isnan(it.warn_at) and x >= it.warn_at) or (not math.isnan(it.warn_below) and x < it.warn_below):
        return it.warn_c
    return it.color


def build(hud, font, values, utc=None, age=0.0):
    """1枚分の四角形。values：hud.refs の順の値（無ければNaN）。utc：UNIX秒（Noneなら時刻を出さない）。
    age：最後に数値を受け取ってからの秒"""
    b = Builder(font)

    def put_text(it, s, c):
        b.text(it.x - b.text_w(it.size, s) if it.right else it.x, it.y, it.size, c, s)

    nodata = age > hud.nodata_after
    for it in hud.items:
        if it.show == 'never' or (it.show == 'nodata' and not nodata) or (it.type == 'clock' and utc is None):
            continue
        if it.box:
            b.rect(*it.box, it.box_c)
        r = it.rect
        if it.type == 'box':
            b.rect(*r, it.color)
        elif it.type == 'text':
            put_text(it, it.text, it.color)
        elif it.type == 'value':
            x = _val(it, values, it.ref)
            if it.laptime:
                s = it.prefix + fmt_laptime(x, it.decimals) + ('' if math.isnan(x) or x < 0 else it.unit)
            elif math.isnan(x):
                s = it.prefix + '--'
            else:
                s = f'{it.prefix}{x:.{it.decimals}f}{it.unit}'
            put_text(it, s, _pick(it, x))
        elif it.type == 'bar':
            w, hh = r[2] - r[0], r[3] - r[1]
            b.rect(*r, it.track_c)
            x = _val(it, values, it.ref)
            if not math.isnan(x):
                f = min(max((x - it.min) / (it.max - it.min), 0), 1)
                c = _pick(it, x)
                if it.dir == 'right':
                    b.rect(r[0], r[1], r[0] + w * f, r[3], c)
                elif it.dir == 'left':
                    b.rect(r[2] - w * f, r[1], r[2], r[3], c)
                elif it.dir == 'up':
                    b.rect(r[0], r[3] - hh * f, r[2], r[3], c)
                else:
                    b.rect(r[0], r[1], r[2], r[1] + hh * f, c)
            k = 1
            while it.tick_every > 0:
                tv = it.min + k * it.tick_every
                if tv >= it.max - 1e-9 * (it.max - it.min):
                    break
                f = (tv - it.min) / (it.max - it.min)
                if it.dir in ('right', 'left'):
                    tx = r[0] + w * f if it.dir == 'right' else r[2] - w * f
                    b.seg(tx, r[1], tx, r[3], it.tick_width, it.tick_c)
                else:
                    ty = r[3] - hh * f if it.dir == 'up' else r[1] + hh * f
                    b.seg(r[0], ty, r[2], ty, it.tick_width, it.tick_c)
                k += 1
        elif it.type == 'gball':
            cx, cy, rr, lw = it.x, it.y, it.radius, it.line_width
            for k in range(48):
                a0, a1 = f32(k * 2 * math.pi / 48), f32((k + 1) * 2 * math.pi / 48)
                b.seg(cx + rr * math.cos(a0), cy + rr * math.sin(a0), cx + rr * math.cos(a1), cy + rr * math.sin(a1),
                      lw, it.ring_c)
            b.seg(cx - rr, cy, cx + rr, cy, lw, it.cross_c)
            b.seg(cx, cy - rr, cx, cy + rr, lw, it.cross_c)
            gx, gy = _val(it, values, it.ref), _val(it, values, it.ref2)
            if not math.isnan(gx) and not math.isnan(gy):
                gx, gy = -gx if it.flip_x else gx, -gy if it.flip_y else gy
                px = cx + rr * max(min(gx / it.full, 1), -1)
                py = cy + rr * max(min(gy / it.full, 1), -1)
                d = it.dot / 2
                b.rect(px - d, py - d, px + d, py + d, it.color)
        elif it.type == 'clock':  # 日本時間
            t = int(utc) + 9 * 3600
            put_text(it, f'{t // 3600 % 24:02d}:{t // 60 % 60:02d}:{t % 60:02d}', it.color)
    return b.quads


# ---------------------------------------------------------------- PCの確認で使う値
def values_from(hud, table):
    """値の名前 → 値 の表から、hud.refs の順の値（| でつないだものは前から順に探す。無ければNaN）"""
    out = []
    for spec in hud.refs:
        out.append(next((table[a] for a in spec.split('|') if a in table), math.nan))
    return out


def alarm_table(hud, base):
    """どの計器も赤（alarm）になる値にした表。しきい値の無いものは base のまま"""
    table = dict(base)
    for it in hud.items:
        for ref in (it.ref, it.ref2):
            if ref < 0 or not it.scale:
                continue
            if not math.isnan(it.alarm_at):
                shown = it.alarm_at
            elif not math.isnan(it.alarm_below):
                shown = it.alarm_below - 1
            else:
                continue
            table[hud.refs[ref].split('|')[0]] = (shown - it.offset) / it.scale
    return table
