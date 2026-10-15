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
       - Grafana Live (channel stream/ecorun/<room>) when a token file exists.
It also serves the map page at http://<host>:3002/map?room=<room>, and over the
same WebSocket
  - keeps shapes people draw on the map (lines, circles, markers...) per room in
    SQLite, so every viewer sees the same course notes, and
  - relays the positions of viewers who chose to share theirs (pit crew walking
    the course), so everyone can see who is where.

Time is the logger's GNSS `Utc` when present, else the server receive time.
Not part of the team server.
"""
import argparse
import asyncio
import glob
import json
import math
import os
import re
import sqlite3
import time
import uuid
import urllib.request
from collections import deque
from http import HTTPStatus

from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.http11 import Response

UTC_MIN_MS = 1_500_000_000_000  # reject Utc=0 / uptime-like values
HISTORY = 3000                  # points per room sent to a newly opened map (5 min at 10 Hz)
VIEWER_STALE_S = 60             # a shared viewer position disappears after this long
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


def valid_feature(feature):
    return (isinstance(feature, dict) and feature.get('type') == 'Feature'
            and isinstance(feature.get('id'), str) and 0 < len(feature['id']) <= 64
            and isinstance(feature.get('geometry'), dict)
            and len(json.dumps(feature)) <= MAX_SHAPE_BYTES)


class Bridge:
    def __init__(self, args):
        self.args = args
        self.shapes = Shapes(args.db)
        self.viewers = {}  # websocket -> {id, room, name, lat, lon, acc, at}
        self.followers = {}
        self.playouts = {}
        self.clients = {}  # websocket -> room
        self.started = time.time()
        self.token = None
        if os.path.exists(args.grafana_token_file):
            with open(args.grafana_token_file) as f:
                self.token = f.read().strip() or None
        print(f'Grafana Live push: {"on" if self.token else "off (no token file)"}', flush=True)

    # --- input -----------------------------------------------------------
    async def follow(self):
        vm_batch, last_vm = [], time.time()
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
                    vm_batch += [line_protocol('ecorun', {'room': f.room}, fl, ts) for ts, fl in points]
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
        msg = json.dumps({'t': ts, **fields})
        for ws, r in list(self.clients.items()):
            if r == room:
                try:
                    await ws.send(msg)
                except Exception:
                    self.clients.pop(ws, None)
        if self.token:
            # The measurement becomes the last part of the channel stream/ecorun/<room>.
            body = line_protocol(re.sub(r'[^A-Za-z0-9_.-]', '_', room), {}, fields, ts)
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
        if path in ('/map', '/map/'):
            with open(os.path.join(HERE, 'map.html'), 'rb') as f:
                body = f.read()
            return Response(HTTPStatus.OK, 'OK', Headers({
                'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store',
                'Content-Length': str(len(body))}), body)
        return connection.respond(HTTPStatus.NOT_FOUND, 'not found\n')

    async def room_send(self, room, msg):
        text = json.dumps(msg)
        for ws, r in list(self.clients.items()):
            if r == room:
                try:
                    await ws.send(text)
                except Exception:
                    self.clients.pop(ws, None)

    def viewer_list(self, room):
        now = time.time()
        return [{k: v[k] for k in ('id', 'name', 'lat', 'lon', 'acc')} | {'age': round(now - v['at'])}
                for v in self.viewers.values() if v['room'] == room and now - v['at'] < VIEWER_STALE_S]

    async def push_viewers(self):
        """Everyone's shared position, every 2 s (a handful of phones: negligible load)."""
        while True:
            await asyncio.sleep(2)
            for room in {r for r in self.clients.values()}:
                await self.room_send(room, {'viewers': self.viewer_list(room)})

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

    async def client(self, ws):
        query = ws.request.path.partition('?')[2]
        room = dict(p.split('=', 1) for p in query.split('&') if '=' in p).get('room', '')
        self.clients[ws] = room
        try:
            history = list(self.playouts[room].history) if room in self.playouts else []
            await ws.send(json.dumps({'history': [{'t': ts, **fl} for ts, fl in history]}))
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
            self.viewers.pop(ws, None)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True, help='ECORUN_TELEMETRY_DIR of the server')
    ap.add_argument('--vm-url', default='http://127.0.0.1:8428/write')
    ap.add_argument('--grafana-url', default='http://127.0.0.1:3001/api/live/push/ecorun')
    ap.add_argument('--grafana-token-file', default='/etc/ecorun-grafana-token')
    ap.add_argument('--listen', default='0.0.0.0:3002')
    ap.add_argument('--db', default=os.path.join(HERE, 'map.db'), help='SQLite file for drawn shapes')
    args = ap.parse_args()

    bridge = Bridge(args)
    host, port = args.listen.rsplit(':', 1)
    async with serve(bridge.client, host, int(port), process_request=bridge.http, max_size=MAX_SHAPE_BYTES + 1000):
        asyncio.get_running_loop().create_task(bridge.push_viewers())
        await bridge.follow()


if __name__ == '__main__':
    asyncio.run(main())
