"""車・コースの設定（setups.py と vehicles/・courses/ のファイル）の試験。

設定ファイルは、いまの道具（tools/sugo_setup/）と本体のコードが持っている値と同じでなければならない
（道具をしまうまでは、どちらかだけを直すと食い違う。その見張り）。"""
import ast
import copy
import json
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'tools' / 'sugo_setup'))
sys.path.insert(0, str(REPO / 'RaceCapture-UNOQ'))

import setups  # noqa: E402


def ncec_fields():
    """EcoCapture-Web/ncec.py の FIELDS（車載CANの12信号）。本体のコードは pydantic が要るので、式だけを読む"""
    source = (REPO / 'EcoCapture-Web' / 'ncec.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == 'FIELDS')
    return eval(compile(ast.Expression(node.value), 'ncec.py', 'eval'), {})


class FilesTest(unittest.TestCase):
    def test_every_file_loads(self):
        self.assertIn('ncec', setups.names('vehicle'))
        self.assertIn('sugo', setups.names('course'))
        for kind in ('vehicle', 'course'):
            for name in setups.names(kind):
                self.assertEqual(setups.load(kind, name)['id'], name)

    def test_ncec_can_signals_are_the_loggers_preset(self):
        signals = {s['name']: s for s in setups.load('vehicle', 'ncec')['logger']['signals']}
        fields = ncec_fields()
        self.assertEqual(len(fields), 12)
        for name, unit, can_id, offset, data_type, scale, add, mask in fields:
            want = {'channel': 1, 'name': name, 'unit': unit, 'can_id': can_id, 'extended': False, 'byte_offset': offset,
                    'data_type': data_type, 'endian': 'big', 'scale': scale, 'offset': add, 'bit_mask': mask,
                    'conversion': 'linear', 'pullup_ohm': None, 'ntc_points': []}
            self.assertTrue(setups.same(signals[name], want), name)

    def test_ncec_defi_signals_are_what_the_tools_register(self):
        import defi_temp_setup
        import defi_volt_setup
        signals = {s['name']: s for s in setups.load('vehicle', 'ncec')['logger']['signals']}
        for want in [*defi_volt_setup.DEFI_SIGNALS, *defi_temp_setup.temp_signals()]:
            self.assertTrue(setups.same(signals[want['name']], want), want['name'])
        self.assertEqual(len(signals), 12 + 5)

    def test_ncec_send_and_dash_match_the_tools_and_the_dash(self):
        import dash_model
        import podium_channels_setup
        vehicle, course = setups.load('vehicle', 'ncec'), setups.load('course', 'sugo')
        self.assertEqual(vehicle['send'], {'room': podium_channels_setup.ROOM, 'channels': podium_channels_setup.PIT})
        self.assertEqual(setups.diff_dash(vehicle, course, dash_model.DEFAULTS), [])

    def test_sugo_line_is_the_tools_line(self):
        import sugo_setup
        self.assertEqual(setups.diff_course(setups.load('course', 'sugo'), sugo_setup.SUGO_LINE), [])
        self.assertEqual(set(setups.load('course', 'sugo')['line']), set(sugo_setup.SUGO_LINE))

    def test_analysis_settings_agree(self):
        vehicle, course = setups.load('vehicle', 'ncec'), setups.load('course', 'sugo')
        for path in (REPO / 'tools' / 'race_analysis').glob('sugo_*.json'):
            analysis = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(analysis['line'], [course['line']['lat'], course['line']['lon']], path.name)
            if 'tread_m' in analysis:
                self.assertEqual(analysis['tread_m'], vehicle['analysis']['tread_m'], path.name)

    def test_analysis_can_name_the_course_and_vehicle_instead(self):
        filled = setups.fill_analysis({'name': 'x', 'course': 'sugo', 'vehicle': 'ncec'})
        self.assertEqual(filled['line'], [38.1423181, 140.7779443])
        self.assertEqual(filled['tread_m'], [1.490, 1.495])
        self.assertEqual(setups.fill_analysis({'line': [1, 2], 'course': 'sugo'})['line'], [1, 2])   # じかに書いた値が勝つ
        self.assertNotIn('line', setups.fill_analysis({'name': 'old'}))

    def test_built_in_channel_names_follow_the_logger(self):
        source = (REPO / 'EcoCapture-Web' / 'models.py').read_text(encoding='utf-8')
        names = set()
        for block in re.findall(r'^(?:LAP_)?CHANNELS = \{(.*?)^\}', source, re.S | re.M):
            names |= set(re.findall(r'"([A-Za-z]+)": \(', block))
        self.assertEqual(names, setups.BUILT_IN_CHANNELS)


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self.vehicle = setups.load('vehicle', 'ncec')
        self.course = setups.load('course', 'sugo')

    def test_vehicle_problems_are_named(self):
        cases = [
            (lambda v: v['logger']['signals'].append(copy.deepcopy(v['logger']['signals'][0])), '同じ名前が2つ'),
            (lambda v: v['logger']['signals'][0].pop('endian'), '項目が足りません（endian）'),
            (lambda v: v['logger']['signals'][12].update(pullup_ohm=None), '換算 ntc には'),
            (lambda v: v['send']['channels'].append('Boost'), '「Boost」は'),
            (lambda v: v['send'].update(room='ncec room'), 'send.room'),
            (lambda v: v['dash'].update(shift_rpm=9000), 'rpm_bar_start < shift_rpm ≦ limit_rpm'),
            (lambda v: v['dash'].pop('oil_warn'), 'dash.oil_warn がありません'),
            (lambda v: v['logger'].update(can_bitrate=800000), 'can_bitrate'),
        ]
        for change, text in cases:
            with self.subTest(text):
                data = copy.deepcopy(self.vehicle)
                change(data)
                self.assertTrue(any(text in p for p in setups.validate_vehicle(data)), setups.validate_vehicle(data))

    def test_course_problems_are_named(self):
        cases = [
            (lambda c: c['line'].update(bearing=400), 'コントロールライン：向き'),
            (lambda c: c['line']['sectors'][1].update(width_m=0), 'セクター2の終わりの線：幅'),
            (lambda c: c['line'].update(start={'lat': 38.1, 'lon': 140.7}), 'スタートの線：向き'),
            (lambda c: c['line'].pop('pit_offset_m'), 'line の項目が足りません（pit_offset_m）'),
            (lambda c: c['confirm'].pop('racing_speed_kmh'), 'racing_speed_kmh'),
            (lambda c: c['line'].update(min_lap_s=4000), 'min_lap_s と max_lap_s'),
        ]
        for change, text in cases:
            with self.subTest(text):
                data = copy.deepcopy(self.course)
                change(data)
                self.assertTrue(any(text in p for p in setups.validate_course(data)), setups.validate_course(data))

    def test_load_refuses_bad_names_and_missing_files(self):
        for name in ('../ncec', 'NCEC', '', 'nothing'):
            with self.assertRaises(setups.SetupError):
                setups.load('vehicle', name)


class DiffTest(unittest.TestCase):
    def setUp(self):
        self.vehicle = setups.load('vehicle', 'ncec')
        self.course = setups.load('course', 'sugo')
        self.config = {'schema': 1, 'device_name': 'EcoLogger V2', 'auto_record': True, **copy.deepcopy(self.vehicle['logger'])}

    def test_same_device_has_no_differences_even_after_a_json_round_trip(self):
        self.config['signals'][0]['scale'] = float(repr(0.25 + 1e-17))
        self.assertEqual(setups.diff_vehicle(self.vehicle, json.loads(json.dumps(self.config))), [])
        self.assertEqual(setups.diff_course(self.course, {**self.course['line'], 'set_at': '2026-11-08T06:46+09:00'}), [])

    def test_vehicle_differences(self):
        self.config['signals'] = [s for s in self.config['signals'] if s['name'] != 'WaterTempDefi']
        self.config['signals'][12]['pullup_ohm'] = 2060.0
        self.config['signals'].append({**self.config['signals'][0], 'name': 'Boost'})
        self.config['can_bitrate'] = 250000
        items = [item for item, _, _ in setups.diff_vehicle(self.vehicle, self.config)]
        self.assertEqual(items, ['can_bitrate', '信号 OilTemp の pullup_ohm', '信号 WaterTempDefi', '信号 Boost'])

    def test_order_is_reported(self):
        self.config['signals'][0], self.config['signals'][1] = self.config['signals'][1], self.config['signals'][0]
        self.assertEqual([item for item, _, _ in setups.diff_vehicle(self.vehicle, self.config)], ['信号の並び'])

    def test_course_differences(self):
        line = copy.deepcopy(self.course['line'])
        line['lat'] += 0.0001
        line['sectors'].pop()
        self.assertEqual([item for item, _, _ in setups.diff_course(self.course, line)], ['line.lat', 'line.sectors'])

    def test_cli_check_with_files(self):
        import contextlib
        import io
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            config, lap = Path(folder) / 'config.json', Path(folder) / 'lap.json'
            config.write_text(json.dumps(self.config), encoding='utf-8')
            lap.write_text(json.dumps({'line': self.course['line'], 'state': {}}), encoding='utf-8')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = setups.main(['check', '--vehicle', 'ncec', '--course', 'sugo', '--config', str(config), '--lap', str(lap)])
            self.assertEqual(code, 0)
            self.assertIn('本体は変えていません', out.getvalue())
            self.config['can_bitrate'] = 250000
            config.write_text(json.dumps(self.config), encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(setups.main(['check', '--vehicle', 'ncec', '--config', str(config)]), 1)


if __name__ == '__main__':
    unittest.main()
