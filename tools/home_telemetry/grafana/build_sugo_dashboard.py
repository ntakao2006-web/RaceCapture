"""Builds sugo-live.json, the pit's Grafana dashboard for the SUGO 120-minute endurance
(2026-11-08, roadster NCEC; task_sugo_20261108_breakdown.md SG-1-5).

  python build_sugo_dashboard.py      -> writes sugo-live.json next to this file

The eco-run dashboard (ecorun-live.json) is about a time limit and average speeds; an endurance
at a circuit is about lap times and keeping the engine alive, so this one is laid out anew and
the eco-run one is left as it is:

  top     the timing sheet (laps.html: every lap as it comes, with its highest oil and water
          temperatures and speed, the race time and the temperatures with the team's limits)
          beside the map, fixed on the whole circuit. Both pushed by live_bridge.py and run
          on the browser's clock, as the eco-run clock (the pit's link at Motegi made polled
          panels ~30 s late).
  middle  G-G with this lap's points and the one before (gg.html ?lap=1), the oil and water
          temperatures over the last 30 minutes (polled; 15 s steps keep it small on the
          pit's phone), GNSS satellites and how late the data reaches the server.
  bottom  collapsed (no queries until opened): speed and revs over time, every channel.

The vehicle list is the NCEC's rooms only (vehicles.py, 2026-11-04): the roadster is its own
vehicle, not the eco-run car whose logger it borrows.

The limits are the driver dash's (RaceCapture-UNOQ/configure_sugo_dashboard.py) from
ncec-roadster track/thermal-limits.md, provisional: when t960 changes them, change OIL/WATER
here and there.
"""
import json
from pathlib import Path

import vehicles
from build_dashboard import VM, ROOM, last, pos, stat, target

HERE = Path(__file__).parent
LIVE = HERE / 'ecorun-live.json'
OUT = HERE / 'sugo-live.json'
RACE_MIN = 120
OIL = (110, 120, 130)     # caution, start cooling, pit in (°C)
WATER = (100, 110, 120)
# The whole circuit (OpenStreetMap ways 107580358/107580877/107581644/107581031, 1.08 x 0.53 km)
MAP_CENTER = (38.14042, 140.77666)
MAP_ZOOM = 15.75
G_MAX = 1.25


def frame(src):
    return {'mode': 'html', 'content': f'<iframe src="{src}" style="width:100%;height:100%;border:0;display:block"></iframe>'}


def csv(values):
    return ','.join(str(v) for v in values)


def temperatures(at):
    """Oil and water over the dashboard's 30 minutes, dashed lines at the oil limits."""
    steps = [{'color': 'green', 'value': None}] + [{'color': c, 'value': v} for c, v in zip(('yellow', 'orange', 'red'), OIL)]
    return {
        'type': 'timeseries', 'title': '油温・水温（30分）', 'gridPos': at, 'datasource': VM,
        'interval': '15s',   # one point per 15 s: ~120 per line, small on the pit's phone
        'description': f'点線は油温の注意{OIL[0]}℃・クーリング開始{OIL[1]}℃・ピットイン{OIL[2]}℃'
                       f'（水温はそれぞれ10℃下：{WATER[0]}・{WATER[1]}・{WATER[2]}℃）。問い合わせ方式なので回線が遅いと遅れる',
        'targets': [target(f'ecorun_OilTemp{{{ROOM}}}', 'A', '油温', instant=False),
                    target(f'ecorun_WaterTemp{{{ROOM}}}', 'B', '水温', instant=False)],
        # soft limits: 60-140 at least, wider when the oil is still cold before the start (a hard
        # 60 hid the 5B demo's 54 °C oil, 2026-11-04)
        'fieldConfig': {'defaults': {'unit': 'celsius', 'decimals': 0,
                                     'thresholds': {'mode': 'absolute', 'steps': steps},
                                     'custom': {'axisSoftMin': 60, 'axisSoftMax': 140,
                                                'thresholdsStyle': {'mode': 'dashed'}, 'lineWidth': 2,
                                                'spanNulls': 60000, 'showPoints': 'never'}},
                        'overrides': [
                            {'matcher': {'id': 'byName', 'options': '油温'},
                             'properties': [{'id': 'color', 'value': {'mode': 'fixed', 'fixedColor': 'orange'}}]},
                            {'matcher': {'id': 'byName', 'options': '水温'},
                             'properties': [{'id': 'color', 'value': {'mode': 'fixed', 'fixedColor': 'blue'}}]}]},
        'options': {'legend': {'displayMode': 'list', 'placement': 'bottom'}, 'tooltip': {'mode': 'multi'}},
    }


def gps(at):
    """Satellites and the receiver's horizontal accuracy as ±m, one above the other (2026-11-04,
    user: the count alone says little). GPSAcc is added to the Podium rows by podium.py itself."""
    p = stat('GPS', [target(last('GPSSats'), 'A', '衛星数'), target(last('GPSAcc'), 'B', '位置の誤差（m）')], at,
             color_mode='value',
             description='衛星数と、受信機が自分で見積もった水平方向の位置の誤差（±m、小さいほど良い）。'
                         'Ver.2の受信機（MAX-M10M）は10/25のもてぎで±0.1〜0.3mと出ていて、カタログの精度（約1.5m）より'
                         '楽観的。値そのものより、急に大きくなったら受信が悪くなったと見る（屋内では±96m）。'
                         'ラップの判定のライン幅50mに対しては数mでも十分。LTEで約1秒に1回')
    p['fieldConfig']['overrides'] = [
        {'matcher': {'id': 'byName', 'options': '衛星数'}, 'properties': [
            {'id': 'decimals', 'value': 0},
            {'id': 'thresholds', 'value': {'mode': 'absolute', 'steps': [
                {'color': 'red', 'value': None}, {'color': 'orange', 'value': 6}, {'color': 'green', 'value': 10}]}}]},
        {'matcher': {'id': 'byName', 'options': '位置の誤差（m）'}, 'properties': [
            {'id': 'unit', 'value': 'prefix:±'}, {'id': 'decimals', 'value': 1},
            {'id': 'thresholds', 'value': {'mode': 'absolute', 'steps': [   # as ecorun-live's GNSS精度
                {'color': 'green', 'value': None}, {'color': 'orange', 'value': 3}, {'color': 'red', 'value': 8}]}}]},
    ]
    p['fieldConfig']['defaults']['color'] = {'mode': 'thresholds'}
    p['options']['orientation'] = 'vertical'   # stacked in the narrow panel
    return p


def build(live):
    every = live['panels'] + [q for p in live['panels'] for q in p.get('panels', [])]
    table = next(p for p in every if p['type'] == 'table' and '__name__=~' in json.dumps(p))

    laps_src = (f'/live/laps?room=$room&race_min={RACE_MIN}&oil={csv(OIL)}&water={csv(WATER)}')
    map_src = f'/live/map?room=$room&zoom={MAP_ZOOM}&follow=0&center={MAP_CENTER[0]},{MAP_CENTER[1]}'
    panels = [
        {'type': 'text', 'title': 'ラップタイム（この端末の時計で進む）', 'gridPos': pos(0, 0, 13, 11),
         'description': '周ごとのラップタイム（新しい周が上）。ベストは紫、ベストより1割以上遅い周（ピット・給油・黄旗など）は灰色。'
                        '油温・水温・最高速はその周に届いた値の最大（LTEで約1秒に1回なので、最高速は数km/h低く出ることがある）。'
                        '「通信切れ」はその周の通過が届かなかった周（ロガーは記録している）。'
                        f'経過・残りは、ラップのリセット後に最初にコントロールラインを通ってから{RACE_MIN}分で数える。'
                        f'油温{OIL[0]}℃で黄（注意）・{OIL[1]}℃でオレンジ（クーリング開始）・{OIL[2]}℃で赤（ピットイン）、'
                        f'水温は{WATER[0]}・{WATER[1]}・{WATER[2]}℃',
         'options': frame(laps_src)},
        {'type': 'text', 'title': '', 'transparent': True, 'gridPos': pos(13, 0, 11, 11),
         'description': 'コース全体を表示（ドラッグ・拡大で動かせる。「追従する」で車を追いかける）',
         'options': {'mode': 'html', 'content': f'<iframe allow="geolocation" src="{map_src}" '
                                                'style="width:100%;height:100%;border:0;display:block"></iframe>'}},
        {'type': 'text', 'title': 'G（この周の点・灰色は前の周）', 'gridPos': pos(0, 11, 8, 5),
         'description': '前後・左右の加速度。下が加速・上が減速。この周に届いた点を全部残す（灰色は前の周）。'
                        'LTEで約1秒に1回なので、短いピークは拾えず最大は低めに出る',
         'options': frame(f'/live/gg?room=$room&lap=1&max={G_MAX}')},
        temperatures(pos(8, 11, 10, 5)),
        gps(pos(18, 11, 3, 5)),
        stat('サーバー到着までの遅れ', [target(f'time() - timestamp(ecorun_Interval{{{ROOM}}})')], pos(21, 11, 3, 5),
             unit='s', decimals=1,
             thresholds=[{'color': 'green', 'value': None}, {'color': 'orange', 'value': 3}, {'color': 'red', 'value': 10}],
             color_mode='background', no_value='受信なし',
             description='ロガーが測った時刻（GNSS）から、そのデータがサーバーに届くまでの秒数。'
                         'この画面の回線の遅れは含まない（そちらはラップタイムの一番下）'),
    ]
    detail = [
        {'type': 'timeseries', 'title': '速度・回転数（30分）', 'gridPos': pos(0, 17, 24, 7), 'datasource': VM, 'interval': '5s',
         'targets': [target(f'ecorun_Speed{{{ROOM}}}', 'A', '速度', instant=False),
                     target(f'ecorun_RPM{{{ROOM}}}', 'B', '回転数', instant=False)],
         'fieldConfig': {'defaults': {'custom': {'lineWidth': 1, 'showPoints': 'never', 'spanNulls': 60000}},
                         'overrides': [{'matcher': {'id': 'byName', 'options': '回転数'}, 'properties': [
                             {'id': 'custom.axisPlacement', 'value': 'right'}, {'id': 'unit', 'value': 'rotrpm'}]},
                             {'matcher': {'id': 'byName', 'options': '速度'}, 'properties': [
                                 {'id': 'unit', 'value': 'velocitykmh'}]}]},
         'options': {'legend': {'displayMode': 'list', 'placement': 'bottom'}, 'tooltip': {'mode': 'multi'}}},
        dict(table, title='全チャンネル（最新）', gridPos=pos(0, 24, 24, 7)),
    ]
    panels.append({'type': 'row', 'title': '詳細（速度・回転数の推移・全チャンネル）　開くと通信量が増えます',
                   'collapsed': True, 'gridPos': pos(0, 16, 24, 1), 'panels': detail})
    for n, p in enumerate(panels + detail, 1):
        p['id'] = n
    return {
        'uid': 'sugo-live', 'title': 'SUGO 120分耐久 Live', 'tags': ['ecorun', 'sugo'],
        'timezone': 'browser', 'editable': False, 'graphTooltip': 1,
        'time': {'from': 'now-30m', 'to': 'now'},
        # 10 s: the polled panels here change slowly; the laps, map and G are pushed.
        'refresh': '10s', 'timepicker': live.get('timepicker', {}),
        'schemaVersion': live.get('schemaVersion', 39),
        # The NCEC's own rooms only (vehicles.py), not the eco-run cars'
        'templating': {'list': [vehicles.sugo_variable()]},
        'links': vehicles.links('sugo-live'),
        'panels': panels,
    }


if __name__ == '__main__':
    live = json.loads(LIVE.read_text(encoding='utf-8'))
    OUT.write_text(json.dumps(build(live.get('dashboard', live)), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'wrote {OUT}')
