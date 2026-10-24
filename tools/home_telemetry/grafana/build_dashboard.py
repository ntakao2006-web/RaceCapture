"""Builds ecorun-live.json, the pit's Grafana dashboard (race layout, 2026-10-23).

  python build_dashboard.py      -> rewrites ecorun-live.json next to this file

Top: the race clock (clock.html: laps "1 / 3", elapsed and time left, margin, the lap
being driven, the line passes and averages, run on the browser's clock) beside the map,
both pushed by live_bridge.py. Then speed and the data-quality numbers, and a collapsed
row with the old polled lap panels, the line passes kept 24 h, the speed graph and every
channel (no queries until opened: the pit's link at Motegi was slow). No G-G circle
(2026-10-24 night: eco-run does not need it; gg.html is still served). The map panel keeps
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
    # --- top: the race clock and the map, both pushed (2026-10-24 night) ------
    # At Motegi the pit's phone link was so slow that polled panels fell ~30 s behind: first
    # the elapsed time (the team nearly ran out of time), then the lap times the pit used to
    # pace the riders. The clock page now carries the laps, the line passes and the margin
    # too, and runs on the browser's clock. The G-G circle is gone (eco-run does not need it)
    # and the lap / average panels moved into the collapsed row, so fewer queries share the link.
    panels.append({'type': 'text', 'title': '周回・時間（この端末の時計で進む）', 'gridPos': pos(0, y, 14, 12),
                   'description': 'スタート時刻と各ラインの通過だけを受け取り、この端末の時計で進める（回線が詰まっても止まらない）。'
                                  '周回は「走行中の周 / 規定周回数」。規定まで＝規定時間−経過。目標まで＝さらに余裕だけ早くゴールする時刻まで。'
                                  '5分を切ると赤。規定時間・余裕はロガー（二輪はアプリ）から届いたもの。'
                                  'この周＝最後のライン通過からの時間。平均速度はサーバーで速度を積算した値。'
                                  '一番下は、この画面が持っている最新データの古さ（ロガー→サーバー→この画面）。10秒を超えると赤',
                   'options': {'mode': 'html', 'content':
                               '<iframe src="/live/clock?room=$room" '
                               'style="width:100%;height:100%;border:0;display:block"></iframe>'}})
    panels.append(dict(map_panel, title='', gridPos=pos(14, y, 10, 12)))
    y += 12   # 12, was 17 (2026-10-24 night): the dashboard did not fit the pit's screen
    # --- second row: speed and whether the data is good (polled every 5 s is fine here) --
    live_speed = dict(live_speed, title='速度', gridPos=pos(0, y, 4, 3))
    live_speed['options'] = dict(live_speed['options'], graphMode='none')
    panels += [
        live_speed,
        stat('GPS衛星数', [target(last('GPSSats'))], pos(4, y, 4, 3), decimals=0,
             thresholds=[{'color': 'red', 'value': None}, {'color': 'orange', 'value': 6}, {'color': 'green', 'value': 10}],
             color_mode='value'),
        stat('GNSS精度', [target(last('GPSAcc'))], pos(8, y, 4, 3), unit='lengthm', decimals=1,
             thresholds=[{'color': 'green', 'value': None}, {'color': 'orange', 'value': 3}, {'color': 'red', 'value': 8}],
             color_mode='value', description='受信機が出す水平精度（大きいほど悪い）。ライン幅の判定にも足している'),
        oil_temp(pos(12, y, 4, 3)),
        # Was "最終受信" (2026-10-24: nobody could tell what it measured). It is how old the
        # newest data on the server is, so it says nothing about a pit screen that has stopped
        # updating; the clock panel shows that.
        stat('サーバー到着までの遅れ', [target(f'time() - timestamp(ecorun_Interval{{{ROOM}}})')], pos(16, y, 8, 3), unit='s', decimals=1,
             thresholds=[{'color': 'green', 'value': None}, {'color': 'orange', 'value': 3}, {'color': 'red', 'value': 10}],
             color_mode='background', no_value='受信なし',
             description='ロガーが測った時刻（GNSS）から、そのデータがサーバーに届いて検索できるようになるまでの秒数。'
                         'ロガーのLTE・サーバーの遅れで、この画面の回線の遅れは含まない（そちらは「周回・時間」の一番下）'),
    ]
    y += 3
    # --- bottom, collapsed (a collapsed row's panels send no queries): the old polled lap
    # panels as a cross-check, the line passes kept 24 h, speed over time, every channel ------
    passes = {
        'type': 'table', 'title': '通過時刻（24時間分。サーバーの記録）', 'gridPos': pos(0, y + 5, 24, 9), 'datasource': VM,
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
    detail = [
        stat('前回ラップ', [target(last('LapTime', 60))], pos(0, y + 1, 6, 4), unit='dthms'),
        stat('この周の経過', [target(last('ElapsedTime', 60))], pos(6, y + 1, 6, 4), unit='dthms'),
        stat('平均速度（スタートから）', [target(last('RaceAvgSpeed'))], pos(12, y + 1, 6, 4), unit='velocitykmh', decimals=1,
             description='自宅サーバーで速度を時間で積算して出した値（live_bridge.py）'),
        stat('この周の平均 ／ 前の周', [target(last('LapAvgSpeed'), 'A', 'この周'), target(last('LastLapAvgSpeed'), 'B', '前の周')],
             pos(18, y + 1, 6, 4), unit='velocitykmh', decimals=1),
        passes,
        dict(speed_graph, title='速度の推移', gridPos=pos(0, y + 14, 24, 6)),
        dict(table, title='全チャンネル（最新）', gridPos=pos(0, y + 20, 24, 7)),
    ]
    panels.append({'type': 'row', 'title': '詳細（問い合わせ方式の周回・通過時刻・速度の推移・全チャンネル）　開くと通信量が増えます',
                   'collapsed': True, 'gridPos': pos(0, y, 24, 1), 'panels': detail})

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
