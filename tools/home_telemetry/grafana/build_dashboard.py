"""Builds ecorun-live.json, the pit's Grafana dashboard (race layout, 2026-10-23).

  python build_dashboard.py      -> rewrites ecorun-live.json next to this file

Top: lap, race time, time left, average speeds, speed. Middle: map and speed graph.
Then the line passes for the timing sheet (start / control / goal times, from
live_bridge.py's Pace). Bottom: acceleration and every channel. The map panel keeps
its HTML from the previous ecorun-live.json. No talk panel and no best lap
(2026-10-23: the pit talks on Discord, and eco-run is not about the fastest lap).
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / 'ecorun-live.json'
VM = {'type': 'prometheus', 'uid': 'ecorun-vm'}
LIVE = {'type': 'datasource', 'uid': 'grafana'}
ROOM = 'room="$room"'


def last(metric, scale=None):
    expr = f'last_over_time(ecorun_{metric}{{{ROOM}}}[10m])'   # keeps the last value through a short dropout
    # Minutes to seconds, rounded: dthms truncates, so a 58 s lap (0.96666 min) read 57.
    return f'round({expr} * {scale})' if scale else expr


def target(expr, ref='A', legend=None, instant=True, fmt=None):
    t = {'refId': ref, 'datasource': VM, 'expr': expr, 'instant': instant, 'range': not instant}
    if legend:
        t['legendFormat'] = legend
    if fmt:
        t['format'] = fmt
    return t


def stat(title, targets, pos, unit=None, decimals=None, description='', thresholds=None, no_value='—',
         color_mode='none', text_size=None):
    defaults = {'noValue': no_value}
    if unit:
        defaults['unit'] = unit
    if decimals is not None:
        defaults['decimals'] = decimals
    if thresholds:
        defaults['thresholds'] = {'mode': 'absolute', 'steps': thresholds}
        defaults['color'] = {'mode': 'thresholds'}
    options = {'reduceOptions': {'calcs': ['lastNotNull'], 'fields': ''}, 'graphMode': 'none',
               'colorMode': color_mode, 'textMode': 'value_and_name' if len(targets) > 1 else 'value',
               'justifyMode': 'center'}
    if text_size:
        options['text'] = {'valueSize': text_size}
    return {'type': 'stat', 'title': title, 'gridPos': pos, 'datasource': VM, 'targets': targets,
            'fieldConfig': {'defaults': defaults, 'overrides': []}, 'options': options, 'description': description}


def oil_temp(at):
    """Oil temperature with the sensor hub's state; blank for a vehicle without one (Super Cub)."""
    p = stat('油温', [target(last('OilTemp'), 'A', '油温'), target(last('OilTempState'), 'B', '状態')], at,
             unit='celsius', decimals=0, color_mode='value',
             thresholds=[{'color': 'blue', 'value': None}, {'color': 'green', 'value': 60},
                         {'color': 'orange', 'value': 110}, {'color': 'red', 'value': 125}],
             description='センサーハブの油温。状態が「正常」以外のときは温度が出ない')
    p['fieldConfig']['overrides'] = [{'matcher': {'id': 'byName', 'options': '状態'}, 'properties': [
        {'id': 'unit', 'value': 'none'},
        {'id': 'mappings', 'value': [{'type': 'value', 'options': {
            '0': {'text': '正常', 'color': 'green'}, '1': {'text': 'オープン', 'color': 'red'},
            '2': {'text': '短絡', 'color': 'red'}, '3': {'text': 'データ異常', 'color': 'red'},
            '4': {'text': '通信途絶', 'color': 'red'}}}]}]}]
    return p


def pos(x, y, w, h):
    return {'x': x, 'y': y, 'w': w, 'h': h}


def build(old):
    # Panels carried over are found by what they show, not by title, so the
    # builder runs again on its own output.
    def find(kind, text):
        return next(p for p in old['panels'] if p['type'] == kind and text in json.dumps(p, ensure_ascii=False))
    map_panel = find('text', '/live/map')
    live_speed = find('stat', 'stream/ecorun/')
    speed_graph = find('timeseries', 'ecorun_Speed{')
    accel = find('timeseries', 'ecorun_LongAccel')
    table = find('table', '__name__=~')

    panels = []
    y = 0
    # --- top: the numbers the pit reads first --------------------------------
    panels += [
        stat('周回', [target(last('CurrentLap'), 'A', '走行中'), target(last('LapsLeft'), 'B', '残り')],
             pos(0, y, 5, 6), decimals=0, description='走行中の周（スタートから最初のコントロールまでが1周目）と残り周回（規定周回数を入れたとき）'),
        stat('経過時間', [target(last('RaceTime', 60))], pos(5, y, 4, 6), unit='dthms',
             description='スタートからの経過（ゴール後はレース時間で止まる）'),
        stat('残り時間', [target(f'({last("RaceTime", -60)} + $limit_min * 60) and on() (vector($limit_min) > 0)')],
             pos(9, y, 4, 6), unit='dthms', no_value='規定時間を上で入力',
             thresholds=[{'color': 'red', 'value': None}, {'color': 'orange', 'value': 300}, {'color': 'green', 'value': 900}],
             color_mode='value', description='上の「規定時間（分）」−経過時間。5分を切ると赤'),
        stat('平均速度（スタートから）', [target(last('RaceAvgSpeed'))], pos(13, y, 4, 6), unit='velocitykmh', decimals=1,
             description='自宅サーバーで速度を時間で積算して出した値（live_bridge.py）'),
        stat('この周の平均 ／ 前の周', [target(last('LapAvgSpeed'), 'A', 'この周'), target(last('LastLapAvgSpeed'), 'B', '前の周')],
             pos(17, y, 4, 6), unit='velocitykmh', decimals=1),
    ]
    live_speed = dict(live_speed, title='速度', gridPos=pos(21, y, 3, 6))
    live_speed['options'] = dict(live_speed['options'], graphMode='none')
    panels.append(live_speed)
    y += 6
    # --- second row: lap times and whether the data is good ------------------
    panels += [
        stat('前回ラップ', [target(last('LapTime', 60))], pos(0, y, 4, 4), unit='dthms'),
        stat('この周の経過', [target(last('ElapsedTime', 60))], pos(4, y, 4, 4), unit='dthms'),
        stat('GPS衛星数', [target(last('GPSSats'))], pos(8, y, 3, 4), decimals=0,
             thresholds=[{'color': 'red', 'value': None}, {'color': 'orange', 'value': 6}, {'color': 'green', 'value': 10}],
             color_mode='value'),
        stat('GNSS精度', [target(last('GPSAcc'))], pos(11, y, 4, 4), unit='lengthm', decimals=1,
             thresholds=[{'color': 'green', 'value': None}, {'color': 'orange', 'value': 3}, {'color': 'red', 'value': 8}],
             color_mode='value', description='受信機が出す水平精度（大きいほど悪い）。ライン幅の判定にも足している'),
        oil_temp(pos(15, y, 4, 4)),
        stat('最終受信', [target(f'time() - timestamp(ecorun_Speed{{{ROOM}}})')], pos(19, y, 5, 4), unit='s', decimals=1,
             thresholds=[{'color': 'green', 'value': None}, {'color': 'orange', 'value': 3}, {'color': 'red', 'value': 10}],
             color_mode='background', no_value='受信なし', description='最後にロガーのデータが届いてからの秒数'),
    ]
    y += 4
    # --- middle: map and speed ----------------------------------------------
    panels.append(dict(map_panel, title='', gridPos=pos(0, y, 12, 14)))
    panels.append(dict(speed_graph, title='速度', gridPos=pos(12, y, 12, 14)))
    y += 14
    # --- line passes for the timing sheet, and talk --------------------------
    passes = {
        'type': 'table', 'title': '通過時刻（スタート・コントロール・ゴール）', 'gridPos': pos(0, y, 24, 9), 'datasource': VM,
        'description': 'ロガーが判定した各ラインの通過時刻。live_bridge.pyが周回の切り替わりから出す。'
                       '「レース」はスタート時刻（同じ部屋で何度か走ったときの区別）',
        'targets': [target(f'last_over_time(ecorun_lap_at{{{ROOM}}}[24h])', 'A', fmt='table')],
        'transformations': [
            {'id': 'organize', 'options': {
                'excludeByName': {'Time': True, 'room': True, '__name__': True},
                'indexByName': {'race': 0, 'lap': 1, 'kind': 2, 'Value': 3, 'seconds': 4, 'avg': 5},
                'renameByName': {'race': 'レース', 'lap': '周', 'kind': 'ライン', 'Value': '通過時刻',
                                 'seconds': 'ラップ（秒）', 'avg': '平均速度（km/h）'}}},
            {'id': 'sortBy', 'options': {'sort': [{'field': '通過時刻', 'desc': True}]}},
        ],
        'fieldConfig': {'defaults': {'custom': {'align': 'center'}}, 'overrides': [
            {'matcher': {'id': 'byName', 'options': '通過時刻'},
             'properties': [{'id': 'unit', 'value': 'time:HH:mm:ss'}]},
            {'matcher': {'id': 'byName', 'options': 'ライン'},
             'properties': [{'id': 'mappings', 'value': [{'type': 'value', 'options': {
                 'start': {'text': 'スタート'}, 'control': {'text': 'コントロール'}, 'goal': {'text': 'ゴール'}}}]}]},
        ]},
        'options': {'showHeader': True, 'cellHeight': 'sm'},
    }
    panels.append(passes)
    y += 9
    # --- bottom: detail --------------------------------------------------------
    panels.append(dict(accel, title='加速度', gridPos=pos(0, y, 24, 6)))
    y += 6
    panels.append(dict(table, title='全チャンネル（最新）', gridPos=pos(0, y, 24, 7)))

    for i, p in enumerate(panels, 1):
        p['id'] = i
    dash = {k: v for k, v in old.items() if k != 'panels'}
    dash['panels'] = panels
    variables = [v for v in old['templating']['list'] if v['name'] != 'limit_min']
    variables.append({'name': 'limit_min', 'label': '規定時間（分）', 'type': 'textbox', 'query': '0',
                      'current': {'text': '0', 'value': '0'},
                      'description': '0なら残り時間を出さない'})
    dash['templating'] = {'list': variables}
    return dash


if __name__ == '__main__':
    old = json.loads(OUT.read_text(encoding='utf-8'))
    old = old.get('dashboard', old)
    OUT.write_text(json.dumps(build(old), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'wrote {OUT}')
