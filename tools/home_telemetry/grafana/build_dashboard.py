"""Builds ecorun-live.json, the pit's Grafana dashboard (race layout, 2026-10-23).

  python build_dashboard.py      -> rewrites ecorun-live.json next to this file

Top: lap, the race clock (clock.html: elapsed and time left, run on the browser's clock),
average speeds, speed. Middle: map and the G-G circle (gg.html), side by side, both
served by live_bridge.py. Then the line passes for the timing sheet (start / control /
goal times, from live_bridge.py's Pace), and a collapsed row with the speed graph and
every channel (no queries until opened: the pit's link at Motegi was slow). The map panel keeps
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
    every = old['panels'] + [q for p in old['panels'] for q in p.get('panels', [])]   # also inside collapsed rows

    def find(kind, text):
        return next(p for p in every if p['type'] == kind and text in json.dumps(p, ensure_ascii=False))
    map_panel = find('text', '/live/map')
    live_speed = find('stat', 'stream/ecorun/')
    speed_graph = find('timeseries', 'ecorun_Speed{')
    table = find('table', '__name__=~')

    panels = []
    y = 0
    # --- top: the numbers the pit reads first --------------------------------
    # The elapsed and remaining time are a clock page, not polled panels (2026-10-24): at
    # Motegi the pit's link was so slow that these panels fell ~30 s behind and the team
    # nearly ran out of time. The page gets the start time once and runs on the browser's
    # clock. The time limit and margin still come from the logger (or the phone app).
    panels += [
        stat('周回', [target(last('CurrentLap'), 'A', '走行中'), target(last('LapsLeft'), 'B', '残り')],
             pos(0, y, 5, 6), decimals=0, description='走行中の周（スタートから最初のコントロールまでが1周目）と残り周回（規定周回数を入れたとき）'),
        {'type': 'text', 'title': '経過・残り時間', 'gridPos': pos(5, y, 8, 6),
         'description': 'スタート時刻だけを受け取り、この端末の時計で進める（回線が詰まっても止まらない）。'
                        '規定まで＝規定時間−経過。目標まで＝さらに余裕だけ早くゴールする時刻まで。5分を切ると赤。'
                        '規定時間・余裕はロガー（二輪はアプリ）から届いたもの。'
                        '一番下は、この画面が持っている最新データの古さ（ロガー→サーバー→この画面）。10秒を超えると赤',
         'options': {'mode': 'html', 'content':
                     '<iframe src="/live/clock?room=$room" '
                     'style="width:100%;height:100%;border:0;display:block"></iframe>'}},
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
        # Was "最終受信" (2026-10-24: nobody could tell what it measured). It is how old the
        # newest data on the server is, so it says nothing about a pit screen that has stopped
        # updating; the clock panel shows that.
        stat('サーバー到着までの遅れ', [target(f'time() - timestamp(ecorun_Interval{{{ROOM}}})')], pos(19, y, 5, 4), unit='s', decimals=1,
             thresholds=[{'color': 'green', 'value': None}, {'color': 'orange', 'value': 3}, {'color': 'red', 'value': 10}],
             color_mode='background', no_value='受信なし',
             description='ロガーが測った時刻（GNSS）から、そのデータがサーバーに届いて検索できるようになるまでの秒数。'
                         'ロガーのLTE・サーバーの遅れで、この画面の回線の遅れは含まない（そちらは「経過・残り時間」の一番下）'),
    ]
    y += 4
    # --- middle: map and the G-G circle (replaced the acceleration time series,
    # 2026-10-23: direction matters, and motorsport people read the circle) --------
    panels.append(dict(map_panel, title='', gridPos=pos(0, y, 14, 14)))
    panels.append({'type': 'text', 'title': 'G（前後・左右）', 'gridPos': pos(14, y, 10, 14),
                   'description': '上が加速、下が減速、左右が横G。点が今、線が直近3秒。外側の輪が0.5G',
                   'options': {'mode': 'html', 'content':
                               '<iframe src="/live/gg?room=$room" '
                               'style="width:100%;height:100%;border:0;display:block"></iframe>'}})
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
    # --- bottom: speed over time and every channel, in a collapsed row: a collapsed row's
    # panels send no queries (2026-10-24: the speed graph alone was ~1000 points a refresh) --
    detail = [dict(speed_graph, title='速度の推移', gridPos=pos(0, y + 1, 24, 6)),
              dict(table, title='全チャンネル（最新）', gridPos=pos(0, y + 7, 24, 7))]
    panels.append({'type': 'row', 'title': '詳細（速度の推移・全チャンネル）　開くと通信量が増えます', 'collapsed': True,
                   'gridPos': pos(0, y, 24, 1), 'panels': detail})

    n = 0
    for p in panels + detail:
        n += 1
        p['id'] = n
    dash = {k: v for k, v in old.items() if k != 'panels'}
    dash['panels'] = panels
    # 5 s (2026-10-24, was 2 s): the pit at Motegi chose 5 s itself, and still saw queries
    # cancelled by the next refresh. The clock, speed (Grafana Live), map and G-G are pushed.
    dash['refresh'] = '5s'
    # The hand-typed time limit (limit_min, then limit and margin) is gone: the logger has it.
    variables = [v for v in old['templating']['list'] if v['name'] not in ('limit_min', 'limit', 'margin')]
    dash['templating'] = {'list': variables}
    return dash


if __name__ == '__main__':
    old = json.loads(OUT.read_text(encoding='utf-8'))
    old = old.get('dashboard', old)
    OUT.write_text(json.dumps(build(old), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'wrote {OUT}')
