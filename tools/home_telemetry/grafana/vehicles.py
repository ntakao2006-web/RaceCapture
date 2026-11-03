"""Which pit screen each vehicle uses (2026-11-04, user's call: the NCEC is not an eco-run car,
so it gets its own screen even though the logger is the same Ver.2).

A vehicle is a room on the server: the last part of the logger's relay URL
(wss://<server>/ws/audio/<room>). The Ver.2 sends as `majesta` in the eco-run car and as
`ncec` in the roadster (tools/sugo_setup/podium_channels_setup.py --room). The server only
takes rooms it has registered (ecorun.sqlite3, table rooms).

  ecorun-live  every room that has data, except the ones below (and the phones' rooms)
  sugo-live    only the rooms below, listed even before any data has come (the variable
               does not depend on VictoriaMetrics, so the pages connect at once)

A new vehicle for the circuit screen is one more line in SUGO; rebuild both dashboards.
"""
import re

SUGO = [   # (room, label on the screen)
    ('ncec', 'NCEC（ロードスター）'),
]
SCREENS = [   # (uid, title of the link to it)
    ('ecorun-live', 'エコランの画面'),
    ('sugo-live', 'NCEC・SUGOの画面'),
]


def ecorun_regex():
    """Grafana's variable regex: drop the SUGO rooms from the eco-run list."""
    names = '|'.join(re.escape(room) for room, _ in SUGO)
    return f'/^(?!(?:{names})$).*$/'


def sugo_variable():
    room, label = SUGO[0]
    return {'name': 'room', 'label': '車両', 'type': 'custom',
            'query': ', '.join(f'{lb} : {r}' for r, lb in SUGO),
            'current': {'text': label, 'value': room},
            'options': [{'text': lb, 'value': r, 'selected': r == room} for r, lb in SUGO]}


def links(here):
    """Links in the dashboard's top bar to the other screens (hidden in kiosk mode)."""
    return [{'type': 'link', 'title': title, 'url': f'/grafana/d/{uid}', 'icon': 'dashboard',
             'targetBlank': False, 'keepTime': False, 'includeVars': False, 'asDropdown': False, 'tags': []}
            for uid, title in SCREENS if uid != here]
