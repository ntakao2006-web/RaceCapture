"""Home test server: telemetry files -> VictoriaMetrics + smooth live feed (ER-8-4).

ecorun-logger-server stores what loggers send as JSON Lines (one file per room/session):
  {"recv_ms":...,"meta":[{"nm":"Speed",...},...]}
  {"recv_ms":...,"samples":[[v...,mask...],...]}
A row holds only the channels whose bit is set, packed in meta order, followed by
ceil(len(meta)/32) bitmask words (EcoCapture-Web/podium.py Encoder.row).

This process follows those files and
  1. writes every sample to VictoriaMetrics (history for Grafana), as
     `ecorun_<Channel>{room="..."}`;
  2. replays the samples at their own 10 Hz spacing after a small fixed delay
     (loggers send 5 rows at once every 0.5 s, which looks jerky if shown as is)
     and sends each one to
       - browsers on ws://<host>:3002/ws?room=<room>  (the live map page), and
       - Grafana Live (channel stream/ecorun/<room>, Speed only) when a token file exists.
     A page names the channels it draws (`&fields=`), so a phone at the pit gets ~60 bytes a
     row instead of the whole ~650-byte row;
  3. sends the race clock (start time, limits, laps and line passes) once a second to the
     clock page, which runs the clock on the browser's own time so it keeps going when the
     pit's link stalls.
It also serves the map page at http://<host>:3002/map?room=<room> (G-G at /gg, the
clock at /clock), and over the
same WebSocket
  - keeps shapes people draw on the map (lines, circles, markers...) per room in
    SQLite, so every viewer sees the same course notes, and
  - relays the positions of viewers who chose to share theirs (pit crew walking
    the course), so everyone can see who is where.
A browser stops sending its position once the page is in the background, so the
pit crew can also share through the OwnTracks app (Android/iOS, keeps running in
the background). That needs plain HTTP POST, which the WebSocket server above
cannot take, so a second small listener (--owntracks-listen, published at
/owntracks) serves
  GET  /            a page that issues a personal setup link (owntracks:///config?inline=...)
  POST /register    {room, name} -> {token, tid}; the token is the app's password
  POST /pub         what the app sends (Basic auth: name / token)
and the positions join the same viewer list as the browsers'.

Time is the logger's GNSS `Utc` when present, else the server receive time.
Not part of the team server.
"""
import argparse
import asyncio
import base64
import glob
import json
import math
import os
import re
import secrets
import sqlite3
import time
import uuid
import urllib.parse
import urllib.request
from collections import deque
from http import HTTPStatus

from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.http11 import Response

UTC_MIN_MS = 1_500_000_000_000  # reject Utc=0 / uptime-like values
HISTORY = 3000                  # points per room sent to a newly opened map (5 min at 10 Hz)
REBUILD_S = 6 * 3600            # on start, files written to this recently rebuild the laps (Bridge.rebuild)
VIEWER_STALE_S = 60             # a shared viewer position disappears after this long
APP_STALE_S = 15 * 60           # ...but an OwnTracks phone standing still may report only every few minutes
MAX_HTTP_BODY = 16_000          # one OwnTracks message
MAX_SHAPE_BYTES = 200_000       # one drawn shape as GeoJSON
HERE = os.path.dirname(os.path.abspath(__file__))


def decode_row(names, row):
    """Return {channel: value} for the channels present in a packed row."""
    n_masks = (len(names) + 31) // 32
    if n_masks == 0 or len(row) < n_masks:
        return {}
    values, masks = row[:-n_masks], row[-n_masks:]
    out, k = {}, 0
    for i, name in enumerate(names):
        if int(masks[i // 32]) >> (i % 32) & 1:
            if k >= len(values):
                return {}  # malformed row; drop rather than misalign
            out[name] = values[k]
            k += 1
    return out


def pick(ts, fields, names):
    """One live row for a page: only the channels it asked for (all when None), rounded."""
    if names is None:
        return {'t': ts, **fields}
    return {'t': ts, **{k: round(fields[k], 6 if k in ('Latitude', 'Longitude') else 3)
                        for k in names if k in fields}}


def clean_name(name):
    return re.sub(r'[^A-Za-z0-9_]', '_', name)


def to_points(names, entry):
    """[(ts_ms, {channel: float})] for one stored samples entry."""
    recv_ms = int(entry.get('recv_ms', 0))
    points = []
    for row in entry.get('samples', []):
        raw = decode_row(names, row)
        utc = raw.get('Utc')
        ts = int(utc) if isinstance(utc, (int, float)) and utc > UTC_MIN_MS else recv_ms
        fields = {clean_name(k): float(v) for k, v in raw.items()
                  if k != 'Utc' and isinstance(v, (int, float)) and math.isfinite(v)}
        if fields and ts:
            points.append((ts, fields))
    return points


class Pace:
    """Average speeds for the pit (2026-10-23): eco-run is judged on average speed, and
    the logger sends no distance, so speed is integrated over time here.

    Adds to each point RaceAvgSpeed (since the start, from RaceTime), LapAvgSpeed (the lap
    being driven, from ElapsedTime) and LastLapAvgSpeed (the lap before), all km/h.
    A new race (RaceTime going back) or lap (ElapsedTime going back) starts over.
    A gap in the data longer than MAX_GAP_S is bridged with the mean of the speeds on either
    side (2026-10-24 night: the Super Cub's phone sent almost nothing for 4 minutes, and
    leaving the gap out read 19.9 km/h for a race run at 25.6 km/h; eco-run speeds are
    steady enough for this). Gaps beyond MAX_BRIDGE_S are still left out."""
    MAX_GAP_S = 5.0
    MAX_BRIDGE_S = 900.0
    # A race or lap first seen this long after its line (2026-10-25: a phone reports the start
    # ~6 s late) still counts from the line, at the speed of that first point.
    HEAD_S = 30.0

    def __init__(self):
        self.last_ts = None
        self.last_speed = None
        self.race = self.lap = None   # [km, minutes at the start of the integration]
        self.race_min = self.lap_min = None
        self.last_lap_avg = None
        self.count = None
        self.start_ms = None
        self.events = []   # line passes for the timing sheet, taken by Bridge.follow
        self.passes = []   # this race's line passes, kept for the clock page
        self.latest = {}   # last value of the channels the pit clock shows (TimeLimit/Margin come sparse)

    def clock(self):
        """The pit clock (clock.html, 2026-10-24): the start time, not the elapsed time, so the
        browser keeps the clock running on its own when the pit's link stalls. A race is on
        while RaceTime and ElapsedTime are sent, finished when only RaceTime is (frozen).
        The line passes come along too (2026-10-24 night): Grafana's polled lap panels fell
        ~30 s behind at Motegi and the pit gave the riders a wrong pace from them. They make
        `lap_start` (the lap being driven runs on the browser's clock too) and the lap table.
        `total` is LapCount + LapsLeft: both the logger and the app count LapsLeft as the
        laps not yet completed, so it read 3 on lap 1 of 3 (the pit expected 2)."""
        on = self.race_min is not None and self.start_ms is not None
        finished = on and self.lap_min is None
        count, left = self.latest.get('LapCount'), self.latest.get('LapsLeft')
        passes = self.passes if on else []
        return {'start': self.start_ms if on else None,
                'end': round(self.start_ms + self.race_min * 60000) if finished else None,
                'limit': self.latest.get('TimeLimit'), 'margin': self.latest.get('Margin'),
                'lap': self.latest.get('CurrentLap'), 'count': count,
                'total': None if count is None or left is None else round(count + left),
                # From ElapsedTime rather than the last pass, so it holds after a bridge restart
                'lap_start': round(self.last_ts - self.lap_min * 60000) if on and not finished else None,
                'last_lap': None if self.latest.get('LapTime') is None else round(self.latest['LapTime'] * 60, 1),
                'passes': passes,
                'lap_avg': self.latest.get('LapAvgSpeed') if on and not finished else None,
                'race_avg': self.latest.get('RaceAvgSpeed') if on else None,
                'data_t': self.last_ts}

    def head(self, minutes, speed):
        """A new race or lap integration [km, minutes it starts from]: from its line when
        that was at most HEAD_S ago, else from here (left out of the averages)."""
        if speed is not None and minutes * 60 <= self.HEAD_S:
            return [speed * minutes / 60, 0.0]
        return [0.0, minutes]

    @staticmethod
    def whole(acc):
        """Integrated from the start of its race or lap: one picked up midway (the bridge
        restarted, or a test replay) would divide part of the distance by the whole time."""
        return acc is not None and acc[1] < 0.1

    def event(self, lap, kind, at_ms, lap_s=None, avg=None):
        """One line pass: lap 0 is the start; kind start/control/goal."""
        self.events.append({'lap': lap, 'kind': kind, 'at_ms': int(at_ms), 'lap_s': lap_s, 'avg': avg,
                            'race': time.strftime('%H:%M', time.localtime(self.start_ms / 1000))})
        if kind == 'start':
            self.passes = []
        self.passes.append({'n': lap, 'k': kind, 't': int(at_ms),
                            's': None if lap_s is None else round(lap_s, 1),
                            'v': None if avg is None else round(avg, 1)})

    def add(self, ts_ms, fields):
        speed = fields.get('Speed', fields.get('GPSSpeed'))
        race_min, lap_min = fields.get('RaceTime'), fields.get('ElapsedTime')
        for name in ('TimeLimit', 'Margin', 'CurrentLap', 'LapsLeft', 'LapCount', 'LapTime'):
            if name in fields:
                self.latest[name] = fields[name]
        dt = (ts_ms - self.last_ts) / 1000 if self.last_ts is not None else None
        self.last_ts = ts_ms
        step = 0.0
        if speed is not None and dt is not None and 0 < dt <= self.MAX_GAP_S:
            step = speed * dt / 3600
        elif speed is not None and self.last_speed is not None and dt is not None and 0 < dt <= self.MAX_BRIDGE_S:
            step = (speed + self.last_speed) / 2 * dt / 3600
        if speed is not None:
            self.last_speed = speed
        # A completed lap (or the goal): the pass time is when the new lap's clock started,
        # or for the goal, the start plus the final race time. Checked before the lap
        # integration below starts over, so the finished lap's distance is still there.
        # A step that spans the pass (a gap in the data around the line) is split at the
        # pass time: the part before ends this lap, the part after starts the next.
        count = fields.get('LapCount')
        after, lap_done = 0.0, False
        if count is not None and self.count is not None and count > self.count and self.start_ms is not None:
            finished = race_min is not None and lap_min is None
            at = self.start_ms + race_min * 60000 if finished else ts_ms - (lap_min or 0) * 60000
            if step and dt:
                after = step * min(1.0, max(0.0, (ts_ms - at) / 1000 / dt))
            if self.lap is not None:
                self.lap[0] += step - after
                lap_done = True
            lap_s = fields['LapTime'] * 60 if fields.get('LapTime') is not None else None
            # Several laps at once (2026-10-25): a control line missed (the phone's recording
            # stopped across it) makes the next pass count k laps sharing the time evenly, and
            # LapTime is one share. The distance covers all k, so it is shared the same way.
            k = max(1, round(count - self.count))
            avg = self.lap[0] / (k * lap_s / 3600) if self.whole(self.lap) and lap_s else None
            for i in range(k - 1):
                n = int(self.count) + 1 + i
                self.event(n, 'control', at - (k - 1 - i) * lap_s * 1000 if lap_s else at, lap_s, avg)
            self.event(int(count), 'goal' if finished else 'control', at, lap_s, avg)
            if avg is not None:
                self.last_lap_avg = avg   # the goal lap too, which has no next lap to start
        if count is not None:
            self.count = count
        if race_min is None:
            self.race = None
        elif self.race is None or self.race_min is None or race_min < self.race_min - 0.05:   # 3 s of jitter is not a new race
            self.race = self.head(race_min, speed)
            new_start = ts_ms - race_min * 60000
            if self.start_ms is None or abs(new_start - self.start_ms) > 2000:   # not just the bridge restarting
                self.start_ms = new_start
                self.event(0, 'start', new_start)
        elif race_min > self.race_min:   # frozen after the goal: driving to the paddock does not count
            self.race[0] += step
        if lap_min is None:
            self.lap = None
        elif self.lap is None or self.lap_min is None or lap_min < self.lap_min - 0.05:
            if self.whole(self.lap) and self.lap_min is not None and self.lap_min > self.lap[1]:
                self.last_lap_avg = self.lap[0] / ((self.lap_min - self.lap[1]) / 60)
            self.lap = [after, 0.0] if after else self.head(lap_min, speed)
        elif not lap_done:
            self.lap[0] += step
        self.race_min, self.lap_min = race_min, lap_min
        for name, acc, now in (('RaceAvgSpeed', self.race, race_min), ('LapAvgSpeed', self.lap, lap_min)):
            if self.whole(acc) and now - acc[1] > 0.1:   # 6 s in: too early is only noise
                fields[name] = acc[0] / ((now - acc[1]) / 60)
            self.latest[name] = fields.get(name)
        if self.last_lap_avg is not None and self.race is not None:
            fields['LastLapAvgSpeed'] = self.last_lap_avg
        return fields


def line_protocol(measurement, tags, fields, ts_ms):
    tag = ''.join(f',{k}={re.sub(r"([ ,=])", r"\\\1", v)}' for k, v in tags.items())
    body = ','.join(f'{k}={v!r}' for k, v in fields.items())
    return f'{measurement}{tag} {body} {ts_ms * 1_000_000}'


def http_post(url, body, token=None):
    req = urllib.request.Request(url, data=body.encode(), method='POST')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    with urllib.request.urlopen(req, timeout=5) as resp:
        resp.read()


class Follower:
    """Tail one session file, remembering its channel list."""

    def __init__(self, path, from_start):
        self.path = path
        self.room = os.path.basename(os.path.dirname(path))
        self.names = []
        self.pos = 0
        self.buf = b''
        if not from_start:
            with open(path, 'rb') as f:
                self._handle(f.readline())  # the meta line
                f.seek(0, os.SEEK_END)
                self.pos = f.tell()

    def _handle(self, raw):
        try:
            entry = json.loads(raw)
        except ValueError:
            return []
        if 'meta' in entry:
            self.names = [m.get('nm', '') for m in entry['meta']]
            return []
        return to_points(self.names, entry) if self.names else []

    def poll(self):
        with open(self.path, 'rb') as f:
            f.seek(self.pos)
            data = f.read()
            self.pos = f.tell()
        self.buf += data
        *complete, self.buf = self.buf.split(b'\n')
        points = []
        for raw in complete:
            points += self._handle(raw)
        return points


class Playout:
    """Re-space a room's points at their own timestamps, delayed by a learned lag.

    The lag is how late (server clock vs sample time) the oldest row of each batch
    arrives; tracking its recent maximum lets every row play on time, so the feed
    is evenly spaced instead of 5 rows at once.
    """

    def __init__(self, room, emit):
        self.room = room
        self.emit = emit
        self.queue = asyncio.Queue()
        self.lags = deque(maxlen=20)
        self.history = deque(maxlen=HISTORY)

    def add(self, points):
        if not points:
            return
        now = time.time() * 1000
        self.lags.append(now - points[0][0])
        for p in points:
            self.queue.put_nowait(p)

    def delay_ms(self):
        return (max(self.lags) if self.lags else 0) + 100

    async def run(self):
        while True:
            ts, fields = await self.queue.get()
            due = ts + self.delay_ms()
            wait = (due - time.time() * 1000) / 1000
            if 0 < wait < 5:
                await asyncio.sleep(wait)
            self.history.append((ts, fields))
            await self.emit(self.room, ts, fields)


class Shapes:
    """Drawn map shapes per room: GeoJSON Features keyed by an id the browser picks."""

    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS shapes (room TEXT, id TEXT, feature TEXT, updated REAL, '
                        'PRIMARY KEY (room, id))')
        self.db.commit()

    def all(self, room):
        rows = self.db.execute('SELECT feature FROM shapes WHERE room=? ORDER BY updated', (room,))
        return [json.loads(f) for (f,) in rows]

    def save(self, room, feature):
        self.db.execute('INSERT OR REPLACE INTO shapes VALUES (?,?,?,?)',
                        (room, feature['id'], json.dumps(feature), time.time()))
        self.db.commit()

    def delete(self, room, shape_id):
        self.db.execute('DELETE FROM shapes WHERE room=? AND id=?', (room, shape_id))
        self.db.commit()


class AppUsers:
    """OwnTracks phones: one random token per person, issued by the setup page."""

    def __init__(self, db):
        self.db = db
        self.db.execute('CREATE TABLE IF NOT EXISTS app_users (token TEXT PRIMARY KEY, room TEXT, name TEXT, '
                        'tid TEXT, created REAL)')
        self.db.commit()

    def register(self, room, name):
        token, tid = secrets.token_urlsafe(18), make_tid(name)
        self.db.execute('INSERT INTO app_users VALUES (?,?,?,?,?)', (token, room, name, tid, time.time()))
        self.db.commit()
        return token, tid

    def lookup(self, token):
        row = self.db.execute('SELECT room, name, tid FROM app_users WHERE token=?', (token,)).fetchone()
        return dict(zip(('room', 'name', 'tid'), row)) if row else None


def make_tid(name):
    """OwnTracks shows a 2-character 'tracker id' in its own map; take it from the name."""
    letters = re.sub(r'[^A-Za-z0-9]', '', name)
    return (letters[:2] or name[:2] or '??').upper()


def basic_auth(headers):
    """(user, password) from an Authorization: Basic header, or (None, None)."""
    kind, _, value = headers.get('authorization', '').partition(' ')
    if kind.lower() != 'basic':
        return None, None
    try:
        user, _, password = base64.b64decode(value).decode().partition(':')
    except ValueError:
        return None, None
    return user, password


def valid_feature(feature):
    return (isinstance(feature, dict) and feature.get('type') == 'Feature'
            and isinstance(feature.get('id'), str) and 0 < len(feature['id']) <= 64
            and isinstance(feature.get('geometry'), dict)
            and len(json.dumps(feature)) <= MAX_SHAPE_BYTES)


class Bridge:
    def __init__(self, args):
        self.args = args
        self.shapes = Shapes(args.db)
        self.app_users = AppUsers(self.shapes.db)
        self.viewers = {}  # websocket (or 'app:<token>') -> {id, room, name, lat, lon, acc, at[, app]}
        self.followers = {}
        self.playouts = {}
        self.paces = {}   # room -> Pace
        self.clients = {}  # websocket -> room
        self.client_opts = {}  # websocket -> {kind, fields} (see client)
        self.started = time.time()
        self.token = None
        if os.path.exists(args.grafana_token_file):
            with open(args.grafana_token_file) as f:
                self.token = f.read().strip() or None
        print(f'Grafana Live push: {"on" if self.token else "off (no token file)"}', flush=True)

    # --- input -----------------------------------------------------------
    def rebuild(self):
        """Rebuild each room's laps from the files written in the last REBUILD_S (2026-10-25):
        a bridge restarted mid-race used to pick up the files at their end, so the line passes
        and averages from before the restart were gone. A room's files are read in name order
        (the server names them by session start), only into Pace: VictoriaMetrics already has
        the rows and the lap marks, and the map's trail is not replayed. The files are then
        followed from where this read stopped."""
        cutoff, rows = time.time() - REBUILD_S, 0
        for path in sorted(glob.glob(os.path.join(self.args.dir, '*', '*.jsonl'))):
            try:
                if os.path.getmtime(path) < cutoff:
                    continue
                f = Follower(path, from_start=True)
                points = f.poll()
            except OSError:
                continue
            pace = self.paces.setdefault(f.room, Pace())
            for ts, fields in points:
                pace.add(ts, fields)
            pace.events.clear()
            self.followers[path] = f
            rows += len(points)
        for room, pace in sorted(self.paces.items()):
            c = pace.clock()
            print(f'rebuilt {room}: lap {c["lap"]}, {len(c["passes"])} passes', flush=True)
        print(f'rebuild: {rows} rows from the last {REBUILD_S // 3600} h', flush=True)

    async def follow(self):
        vm_batch, last_vm = [], time.time()
        self.rebuild()
        while True:
            for path in glob.glob(os.path.join(self.args.dir, '*', '*.jsonl')):
                if path not in self.followers:
                    new = os.path.getctime(path) >= self.started
                    self.followers[path] = Follower(path, from_start=new)
            for f in self.followers.values():
                try:
                    points = f.poll()
                except OSError:
                    continue
                if points:
                    pace = self.paces.setdefault(f.room, Pace())
                    points = [(ts, pace.add(ts, fl)) for ts, fl in points]
                    # Line passes as ecorun_lap_at{room,lap,kind,race,seconds,avg} = pass time (ms), one
                    # sample each. Lap time and average are labels so one query gives one row per pass.
                    for e in pace.events:
                        tags = {'room': f.room, 'lap': f"{e['lap']:02d}", 'kind': e['kind'], 'race': e['race'],
                                'seconds': '-' if e['lap_s'] is None else f"{e['lap_s']:.1f}",
                                'avg': '-' if e['avg'] is None else f"{e['avg']:.1f}"}
                        vm_batch.append(line_protocol('ecorun_lap', tags, {'at': float(e['at_ms'])}, e['at_ms']))
                        print(f'{f.room}: {e}', flush=True)
                    pace.events.clear()
                    vm_batch +=[line_protocol('ecorun', {'room': f.room}, fl, ts) for ts, fl in points]
                    self.playout(f.room).add(points)
            if vm_batch and time.time() - last_vm >= 0.5:
                batch, vm_batch, last_vm = vm_batch, [], time.time()
                try:
                    await asyncio.to_thread(http_post, self.args.vm_url, '\n'.join(batch) + '\n')
                except OSError as error:
                    print(f'VictoriaMetrics push failed ({error}); {len(batch)} points dropped', flush=True)
            await asyncio.sleep(0.05)

    def playout(self, room):
        if room not in self.playouts:
            p = self.playouts[room] = Playout(room, self.emit)
            asyncio.get_running_loop().create_task(p.run())
        return self.playouts[room]

    # --- output ----------------------------------------------------------
    async def emit(self, room, ts, fields):
        msgs = {}   # one encoding per field list asked for
        for ws, r in list(self.clients.items()):
            opts = self.client_opts.get(ws, {})
            if r != room or opts.get('kind') == 'clock':
                continue
            key = opts.get('fields')
            if key not in msgs:
                msgs[key] = json.dumps(pick(ts, fields, key))
            try:
                await ws.send(msgs[key])
            except Exception:
                self.clients.pop(ws, None)
        if self.token and 'Speed' in fields:
            # The measurement becomes the last part of the channel stream/ecorun/<room>.
            # Only Speed: it is all the Grafana panel shows, and every viewer gets the whole row
            # (2026-10-24: ~30 channels 10 times a second crowded the pit's slow link at Motegi).
            body = line_protocol(re.sub(r'[^A-Za-z0-9_.-]', '_', room), {}, {'Speed': fields['Speed']}, ts)
            asyncio.get_running_loop().run_in_executor(None, self.grafana_push, body)

    def grafana_push(self, body):
        try:
            http_post(self.args.grafana_url, body, self.token)
        except OSError as error:
            print(f'Grafana Live push failed: {error}', flush=True)

    # --- browser side ----------------------------------------------------
    def http(self, connection, request):
        path, _, query = request.path.partition('?')
        if path == '/ws':
            return None  # continue with the WebSocket handshake
        # gg: the G-G circle (2026-10-23); clock: the race clock (2026-10-24)
        pages = {'/map': 'map.html', '/gg': 'gg.html', '/clock': 'clock.html'}
        if path.rstrip('/') in pages:
            with open(os.path.join(HERE, pages[path.rstrip('/')]), 'rb') as f:
                body = f.read()
            return Response(HTTPStatus.OK, 'OK', Headers({
                'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store',
                'Content-Length': str(len(body))}), body)
        return connection.respond(HTTPStatus.NOT_FOUND, 'not found\n')

    async def room_send(self, room, msg, kind=None):
        """To the room's map pages (shapes, viewers); the clock and G-G pages do not draw them."""
        text = json.dumps(msg)
        for ws, r in list(self.clients.items()):
            if r == room and self.client_opts.get(ws, {}).get('kind') == kind:
                try:
                    await ws.send(text)
                except Exception:
                    self.clients.pop(ws, None)

    def viewer_list(self, room):
        now = time.time()
        return [{k: v[k] for k in ('id', 'name', 'lat', 'lon', 'acc')} | {'age': round(now - v['at']), 'app': 'app' in v}
                for v in self.viewers.values()
                if v['room'] == room and now - v['at'] < (APP_STALE_S if 'app' in v else VIEWER_STALE_S)]

    async def push_viewers(self):
        """Everyone's shared position, every 2 s (a handful of phones: negligible load)."""
        while True:
            await asyncio.sleep(2)
            for room in {r for ws, r in self.clients.items() if self.client_opts.get(ws, {}).get('kind') != 'clock'}:
                await self.room_send(room, {'viewers': self.viewer_list(room)}, kind=None)

    def clock_msg(self, room):
        pace = self.paces.get(room)
        return json.dumps({'clock': pace.clock() if pace else None, 'now': round(time.time() * 1000)})

    async def push_clock(self):
        """The pit clock's state once a second: ~200 bytes, whatever the link."""
        while True:
            await asyncio.sleep(1)
            for ws, opts in list(self.client_opts.items()):
                if opts.get('kind') == 'clock' and ws in self.clients:
                    try:
                        await ws.send(self.clock_msg(self.clients[ws]))
                    except Exception:
                        self.clients.pop(ws, None)

    async def handle(self, ws, room, msg):
        kind = msg.get('type')
        if kind == 'shape.save' and valid_feature(msg.get('feature')):
            self.shapes.save(room, msg['feature'])
            await self.room_send(room, {'shape': msg['feature']})
        elif kind == 'shape.delete' and isinstance(msg.get('id'), str):
            self.shapes.delete(room, msg['id'])
            await self.room_send(room, {'shape_deleted': msg['id']})
        elif kind == 'viewer.pos':
            try:
                lat, lon = float(msg['lat']), float(msg['lon'])
                acc = min(float(msg.get('acc') or 0), 10_000)
            except (KeyError, TypeError, ValueError):
                return
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return
            v = self.viewers.setdefault(ws, {'id': uuid.uuid4().hex[:8]})
            v.update(room=room, name=str(msg.get('name') or '?')[:20], lat=lat, lon=lon, acc=acc, at=time.time())
        elif kind == 'viewer.stop':
            self.viewers.pop(ws, None)

    # --- OwnTracks app side ------------------------------------------------
    async def app_http(self, reader, writer):
        """One request per connection (Connection: close); enough for a few phones."""
        status, ctype, body = 400, 'text/plain', b'bad request\n'
        try:
            head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 10)
            line, *fields = head.decode('latin-1').split('\r\n')
            method, target, _ = line.split(' ', 2)
            headers = {k.strip().lower(): v.strip() for k, _, v in (f.partition(':') for f in fields if f)}
            length = int(headers.get('content-length') or 0)
            if 0 <= length <= MAX_HTTP_BODY:
                data = await asyncio.wait_for(reader.readexactly(length), 10) if length else b''
                status, ctype, body = await self.app_route(method, target.partition('?')[0], headers, data)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError,
                ValueError, AttributeError, TypeError, OSError):
            pass
        reason = HTTPStatus(status).phrase
        writer.write(f'HTTP/1.1 {status} {reason}\r\nContent-Type: {ctype}\r\nContent-Length: {len(body)}\r\n'
                     f'Cache-Control: no-store\r\nConnection: close\r\n\r\n'.encode() + body)
        try:
            await writer.drain()
            writer.close()
        except OSError:
            pass

    async def app_route(self, method, path, headers, data):
        if method == 'GET' and path in ('/', '/index.html'):
            with open(os.path.join(HERE, 'owntracks.html'), 'rb') as f:
                return 200, 'text/html; charset=utf-8', f.read()
        if method == 'POST' and path == '/register':
            msg = json.loads(data or b'{}')
            room = str(msg.get('room') or '').strip()[:64]
            name = str(msg.get('name') or '').strip()[:20]
            if not room or not name:
                return 400, 'text/plain', b'room and name are required\n'
            token, tid = self.app_users.register(room, name)
            print(f'OwnTracks: registered {name!r} in room {room!r}', flush=True)
            return 200, 'application/json', json.dumps({'token': token, 'tid': tid, 'name': name}).encode()
        if method == 'POST' and path == '/pub':
            user = self.app_users.lookup(basic_auth(headers)[1] or '')
            if not user:
                return 401, 'text/plain', b'unknown token\n'
            msg = json.loads(data) if data.strip() else {}
            if isinstance(msg, dict) and msg.get('_type') == 'location':
                self.app_position(user, msg)
            return 200, 'application/json', json.dumps(self.app_reply(user)).encode()
        return 404, 'text/plain', b'not found\n'

    def app_position(self, user, msg):
        try:
            lat, lon = float(msg['lat']), float(msg['lon'])
            acc = min(float(msg.get('acc') or 0), 10_000)
        except (KeyError, TypeError, ValueError):
            return
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return
        key = 'app:' + user['tid'] + ':' + user['name']
        v = self.viewers.setdefault(key, {'id': uuid.uuid4().hex[:8], 'app': True})
        v.update(room=user['room'], name=user['name'], lat=lat, lon=lon, acc=acc, at=time.time())

    def app_reply(self, user):
        """Everyone else in the room, so the OwnTracks app's own map shows the team too."""
        now, out = time.time(), []
        for v in self.viewer_list(user['room']):
            if v['name'] == user['name']:
                continue
            tid = make_tid(v['name'])
            out.append({'_type': 'card', 'tid': tid, 'name': v['name']})
            out.append({'_type': 'location', 'tid': tid, 'lat': v['lat'], 'lon': v['lon'],
                        'acc': round(v['acc']), 'tst': int(now - v['age']), 'topic': f'owntracks/ecorun/{v["id"]}'})
        return out

    async def client(self, ws):
        """/ws?room=<room>[&kind=clock|gg][&fields=A,B][&history=<s>]: a page asks only for the
        channels it draws and as much history as it keeps (2026-10-24, for the pit's slow link:
        the whole rows were ~650 bytes each, and a new map got 5 minutes of them, ~2 MB)."""
        query = urllib.parse.parse_qs(ws.request.path.partition('?')[2])
        room = query.get('room', [''])[0]
        kind = query.get('kind', [None])[0]
        fields = query.get('fields', [None])[0]
        fields = tuple(sorted(f for f in fields.split(',') if f)) if fields else None
        try:
            keep_ms = float(query['history'][0]) * 1000 if 'history' in query else None
        except ValueError:
            keep_ms = None
        self.clients[ws] = room
        self.client_opts[ws] = {'kind': kind, 'fields': fields}
        try:
            if kind == 'clock':
                await ws.send(self.clock_msg(room))
            else:
                history = list(self.playouts[room].history) if room in self.playouts else []
                if keep_ms is not None and history:
                    history = [p for p in history if p[0] >= history[-1][0] - keep_ms]
                await ws.send(json.dumps({'history': [pick(ts, fl, fields) for ts, fl in history]}))
            if kind is None:
                await ws.send(json.dumps({'shapes': self.shapes.all(room), 'viewers': self.viewer_list(room)}))
            async for raw in ws:
                if isinstance(raw, str) and len(raw) <= MAX_SHAPE_BYTES + 1000:
                    try:
                        msg = json.loads(raw)
                    except ValueError:
                        continue
                    if isinstance(msg, dict):
                        await self.handle(ws, room, msg)
        except Exception:
            pass
        finally:
            self.clients.pop(ws, None)
            self.client_opts.pop(ws, None)
            self.viewers.pop(ws, None)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True, help='ECORUN_TELEMETRY_DIR of the server')
    ap.add_argument('--vm-url', default='http://127.0.0.1:8428/write')
    ap.add_argument('--grafana-url', default='http://127.0.0.1:3001/api/live/push/ecorun')
    ap.add_argument('--grafana-token-file', default='/etc/ecorun-grafana-token')
    ap.add_argument('--listen', default='0.0.0.0:3002')
    ap.add_argument('--db', default=os.path.join(HERE, 'map.db'), help='SQLite file for drawn shapes')
    ap.add_argument('--owntracks-listen', default='127.0.0.1:3003', help='HTTP for the OwnTracks app')
    args = ap.parse_args()

    bridge = Bridge(args)
    host, port = args.listen.rsplit(':', 1)
    app_host, app_port = args.owntracks_listen.rsplit(':', 1)
    app_server = await asyncio.start_server(bridge.app_http, app_host, int(app_port))
    async with app_server, serve(bridge.client, host, int(port), process_request=bridge.http,
                                 max_size=MAX_SHAPE_BYTES + 1000):
        asyncio.get_running_loop().create_task(bridge.push_viewers())
        asyncio.get_running_loop().create_task(bridge.push_clock())
        await bridge.follow()


if __name__ == '__main__':
    asyncio.run(main())
