"""Builds ecorun-demo.json from ecorun-live.json: the pit's dashboard for the race replayed
by demo_loop.py (school festival, 2026-10-30).

  python build_demo_dashboard.py      -> writes ecorun-demo.json next to this file

Same panels as the pit's, moved down under a banner that says it is a replay, and the room
picked from the three demo rooms (never a real one) by the vehicle's name. The pit's
dashboard is left as it is.
"""
import copy
import json
from pathlib import Path

HERE = Path(__file__).parent
LIVE = HERE / 'ecorun-live.json'
OUT = HERE / 'ecorun-demo.json'
BANNER_H = 3
VEHICLES = [   # (label, room)
    ('majesta（エコランカー・7周）', 'demo-majesta'),
    ('スーパーカブ（ガソリン二輪・3周）', 'demo-super-cub'),
    ('aubergine（電動二輪・3周）', 'demo-aubergine'),
]
BANNER = ('**2026年10月25日 Honda エコ マイレッジ チャレンジ（モビリティリゾートもてぎ）本番の再生です。**'
          '　当日ピットで見ていた画面に、車から届いたデータを当日と同じ間隔で流し直しています'
          '（スタートからゴールまでを繰り返し）。左上の「車両」で3台を切り替えられます。'
          '　地図は自動で車を追いかけます。')


def build(live):
    dash = copy.deepcopy(live)
    dash['uid'] = 'ecorun-demo'
    dash['title'] = 'EcoRun デモ（10/25 もてぎ本番の再生）'
    dash['tags'] = ['ecorun', 'demo']
    for p in dash['panels']:
        p['gridPos']['y'] += BANNER_H
        for q in p.get('panels', []):
            q['gridPos']['y'] += BANNER_H
    dash['panels'].insert(0, {'type': 'text', 'title': '', 'gridPos': {'x': 0, 'y': 0, 'w': 24, 'h': BANNER_H},
                              'options': {'mode': 'markdown', 'content': BANNER}})
    n = 0
    for p in dash['panels'] + [q for p in dash['panels'] for q in p.get('panels', [])]:
        n += 1
        p['id'] = n
    query = ', '.join(f'{label} : {room}' for label, room in VEHICLES)
    label, room = VEHICLES[0]
    dash['templating'] = {'list': [{
        'name': 'room', 'label': '車両', 'type': 'custom', 'query': query,
        'current': {'text': label, 'value': room},
        'options': [{'text': lb, 'value': r, 'selected': r == room} for lb, r in VEHICLES],
    }]}
    return dash


if __name__ == '__main__':
    live = json.loads(LIVE.read_text(encoding='utf-8'))
    OUT.write_text(json.dumps(build(live.get('dashboard', live)), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'wrote {OUT}')
