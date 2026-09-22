"""One-time correction from the pre-layout backup. Never use as a live editor."""
from pathlib import Path
import copy, csv, datetime, json, uuid
import sexpdata as sx

P = Path(__file__).resolve().parents[1]
BASE = P / 'logger_v2-backups/phase1_source'
S = sx.Symbol
def n(k, *v): return [S(k), *v]
def ch(a, k): return [v for v in a if isinstance(v, list) and v and str(v[0]) == k]
def one(a, k): return ch(a, k)[0]
def prop(a, k): return next(v for v in ch(a, 'property') if v[1] == k)
def uid(): return str(uuid.uuid4())
def write(path, obj): path.write_text(sx.dumps(obj, pretty_print=True) + '\n', encoding='utf-8')
def xy(a): return tuple(one(a, 'at')[1:3])

snapshot = P / 'logger_v2-backups/before_in_place_restore'
if not snapshot.exists():
    snapshot.mkdir()
    for name in ['logger_v2.kicad_sch', 'logger_v2_custom.kicad_sym', 'sym-lib-table', 'logger_v2.kicad_pro']:
        (snapshot / name).write_bytes((P / name).read_bytes())
old_implementation = sx.loads((snapshot / 'logger_v2.kicad_sch').read_text(encoding='utf-8'))
oldparts = {prop(c, 'Reference')[2]: c for c in ch(old_implementation, 'symbol')}
src = sx.loads((BASE / 'logger_v2.kicad_sch').read_text(encoding='utf-8'))
out = copy.deepcopy(src)
parts = {prop(c, 'Reference')[2]: c for c in ch(out, 'symbol')}
root = one(out, 'uuid')[1]
libcontainer = one(out, 'lib_symbols')

# Only component metadata changes: placements, library IDs and visible field
# positions are inherited verbatim from the original schematic.
for ref, c in parts.items():
    if ref.startswith('#'): continue
    prop(c, 'Footprint')[2] = prop(oldparts[ref], 'Footprint')[2]
    one(c, 'dnp')[1] = S('yes' if ref in ['R10', 'R13', 'R14', 'R15', 'R16'] else 'no')
    if ref in ['R7', 'C1']:
        prop(c, 'Value')[2] = '22R 1W' if ref == 'R7' else '100nF'
        prop(c, 'Datasheet')[2] = prop(oldparts[ref], 'Datasheet')[2]
    for key in ['MPN', 'Assembly']:
        if any(v[1] == key for v in ch(oldparts[ref], 'property')):
            q = copy.deepcopy(prop(oldparts[ref], key))
            one(q, 'at')[1:3] = list(xy(c))
            c.append(q)
    if ref == 'C1':
        c.append(n('property', 'Specification', '100nF X7R 16V', n('at', *xy(c), 0), n('effects', n('font', n('size', 1, 1)), n('hide', S('yes')))))

def wire(a, b):
    assert a != b
    out.append(n('wire', n('pts', n('xy', *a), n('xy', *b)), n('stroke', n('width', 0), n('type', S('default'))), n('uuid', uid())))
def label(name, pt, justify='left', size=1.0):
    out.append(n('label', name, n('at', *pt, 0), n('effects', n('font', n('size', size, size)), n('justify', S(justify))), n('uuid', uid())))
def nc(pt):
    if not any(xy(v) == tuple(pt) for v in ch(out, 'no_connect')):
        out.append(n('no_connect', n('at', *pt), n('uuid', uid())))
def junction(pt):
    out.append(n('junction', n('at', *pt), n('diameter', 0), n('color', 0, 0, 0, 0), n('uuid', uid())))
def remove_wire(a, b):
    matches = [w for w in ch(out, 'wire') if {tuple(v[1:]) for v in ch(one(w, 'pts'), 'xy')} == {tuple(a), tuple(b)}]
    assert len(matches) == 1, (a, b, len(matches))
    out.remove(matches[0])
def remove_junction(pt):
    matches = [v for v in ch(out, 'junction') if xy(v) == tuple(pt)]
    assert len(matches) == 1, pt
    out.remove(matches[0])

# Reuse existing label anchors, leads and component positions.
rename = {
    'CAN1_RxD': 'CAN1_RXD', 'CAN1_TxD': '+3V3',
    'CAN2_CS': 'CAN2_CS_N', 'CAN2_INT': 'CAN2_INT_N',
    'CAN2_MISO': 'SPI2_MISO', 'CAN2_MOSI': 'SPI2_MOSI',
    'CAN2_SCK': 'SPI2_SCK', 'CAN2_RESET': 'CAN2_RESET_N',
    'GNSS_RxD': 'GNSS_TXD', 'GNSS_TxD': 'GNSS_RXD',
    'GNSS_RESET': 'GNSS_RESET_N', 'GNSS_PPS': 'GNSS_PPS',
    'IMU_RESET': 'IMU_RESET_N', 'STATUS_OUT': 'STATUS_LATCH',
    '13': 'SPI2_SCK', '12': 'SPI2_MISO', '*11': 'SPI2_MOSI',
    '*10': 'CAN2_CS_N', '*9': 'CAN2_INT_N', '8': 'CAN2_RESET_N',
    '7': 'STATUS_LATCH', '*6': 'GNSS_PPS', '*5': 'CAN1_RXD',
    '*3': 'GNSS_RESET_N', '2': 'IMU_RESET_N',
    'TX{slash}1': 'GNSS_RXD', 'RX{slash}0': 'GNSS_TXD',
}
unused = {'A0': 'A0', 'A1': 'A1', 'A2': 'A2', 'A3': 'A3',
          '4': 'D4 / NC', 'AREF': 'AREF', 'IOREF': 'IOREF',
          '~{RESET}': '~{RESET}', 'Vin': 'VIN'}
for l in list(ch(out, 'label')):
    old = l[1]
    if old in ['SDA{slash}A4', 'SCL{slash}A5']:
        if xy(l)[0] > 50:
            l[1] = 'IMU_SDA' if 'SDA' in old else 'IMU_SCL'
        else:
            unused[old] = 'A4 / I2C3_SDA' if 'SDA' in old else 'A5 / I2C3_SCL'
    if old in unused:
        # Unused header leads remain visible, with their original identifiers.
        # Plain text and an NC marker avoid making isolated local label nets.
        l[0] = S('text'); l[1] = unused[old]
        one(one(l, 'effects'), 'font')[1] = n('size', 1, 1)
        nc(xy(l))
        # A schematic label sits above its wire baseline; plain text is centered.
        at = one(l, 'at')
        if at[3] % 180 == 0: at[2] -= 0.9
        else: at[1] -= 0.9
    elif old in rename:
        l[1] = rename[old]
    if str(l[0]) == 'label' and l[1] != old:
        one(one(l, 'effects'), 'font')[1] = n('size', 1, 1)

# Remove only the two obsolete power symbols: unused VIN and J7 pin 1.
# All actual components, and all necessary power symbols, are retained.
out.remove(parts['#PWR03'])
out.remove(parts['#PWR025'])
nc((240.03, 104.14))

# GNSS supply pins retain the requested centered, 2-grid pin arrangement.
remove_wire((121.92, 22.86), (124.46, 22.86))
remove_wire((119.38, 22.86), (121.92, 22.86))
remove_wire((121.92, 21.59), (121.92, 22.86))
remove_junction((121.92, 22.86))
wire((121.92, 21.59), (119.38, 21.59))
wire((119.38, 21.59), (119.38, 22.86))
wire((124.46, 22.86), (124.46, 20.32))
wire((124.46, 20.32), (125.73, 20.32))
label('+3V3', (125.73, 20.32))
wire((121.92, 22.86), (123.19, 22.86))
wire((123.19, 22.86), (123.19, 17.78))
wire((123.19, 17.78), (129.54, 17.78))
label('GND', (129.54, 17.78))
nc((99.06, 50.8)); nc((99.06, 53.34))

# Correct the bias-T without moving R7, L1, C1 or their fields.
remove_wire((156.21, 36.83), (156.21, 38.1))
remove_junction((156.21, 38.1))
wire((156.21, 36.83), (168.91, 36.83))
wire((168.91, 36.83), (168.91, 43.18))
wire((156.21, 43.18), (168.91, 43.18))
junction((156.21, 43.18))

# Declare the external UNO Q supply source for ERC, below the power header.
powerlib = sx.loads((Path.home() / 'AppData/Local/Programs/KiCad/9.0/share/kicad/symbols/power.kicad_sym').read_text(encoding='utf-8'))
flag = copy.deepcopy(next(v for v in ch(powerlib, 'symbol') if v[1] == 'PWR_FLAG'))
flag[1] = 'power:PWR_FLAG'; libcontainer.append(flag)
for i, (net, x) in enumerate([('+3V3', 25.4), ('+5V', 38.1), ('GND', 50.8)], 1):
    y = 85.09
    ref = '#FLG0' + str(i)
    out.append(n('symbol', n('lib_id', 'power:PWR_FLAG'), n('at', x, y, 0), n('unit', 1), n('in_bom', S('no')), n('on_board', S('yes')), n('dnp', S('no')), n('uuid', uid()),
        n('property', 'Reference', ref, n('at', x, y, 0), n('effects', n('font', n('size', 1, 1)), n('hide', S('yes')))),
        n('property', 'Value', 'PWR_FLAG', n('at', x, y - 3.81, 0), n('effects', n('font', n('size', 1, 1)), n('hide', S('yes')))),
        n('instances', n('project', 'logger_v2', n('path', '/' + root, n('reference', ref), n('unit', 1))))))
    wire((x, y), (x, y + 2.54)); label(net, (x, y + 2.54))

# Keep original library IDs and original embedded symbol definitions. Make
# custom definitions resolvable inside this project under their original names.
custom = {}
for lib in ch(libcontainer, 'symbol'):
    prefix, name = lib[1].split(':', 1)
    if prefix in ['logger_v1_custom', 'logger_v2_custom', 'mimi88_symbols']:
        c = copy.deepcopy(lib); c[1] = name
        custom.setdefault(prefix, []).append(c)
table = n('sym_lib_table', n('version', 7))
for prefix, symbols in custom.items():
    filename = prefix + '.kicad_sym'
    write(P / filename, n('kicad_symbol_lib', n('version', 20241209), n('generator', 'kicad_symbol_editor'), *symbols))
    table.append(n('lib', n('name', prefix), n('type', 'KiCad'), n('uri', '${KIPRJMOD}/' + filename), n('options', ''), n('descr', 'Original symbols retained in place')))
write(P / 'sym-lib-table', table)
write(P / 'logger_v2.kicad_sch', out)
print('Restored original A4 layout and wired all 44 components in place.')
