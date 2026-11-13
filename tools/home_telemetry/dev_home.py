"""表紙（home.html）をPCの中だけで動かして確かめるための、作りものの車と中継（SP-6-1・SP-6-3、2026-11-13）。

本物のロガー・自宅のサーバーには何もつながない。次の2つを1つの道具で動かす。

  1. 車：ecorun-logger-server が書くのと同じ形のファイル（<dir>/<room>/<開始>.jsonl）へ、0.5秒ごとに5行ずつ書き足す。
     live_bridge.py はこれを本物と同じように読む。1周110秒でぐるぐる回り、油温・水温がゆっくり上がる。
  2. 中継とロガー：ws://127.0.0.1:3010/ws/audio/<room> で命令（logger.config の command）を受け、
     本体と同じ確かめ方（EcoCapture-Web/remote_command.py の RemoteCommands）で署名・使い回し・時刻を確かめて返事を返す。
     ラップのリセット・周回数の直し・計測の開始は、1の車の周回に効く。
     コースを選ぶ（course_list・course_select）は、本体と同じ部品（lap.py の LapTimer）で <dir>/logger/lap.json を書き換える。
     選べるコースは作りものの2つ（dev-east・dev-west。実在の場所ではない）。

  python tools/home_telemetry/dev_home.py --dir <一時フォルダー>            # 合言葉を作って表示する
  python tools/home_telemetry/live_bridge.py --dir <同じフォルダー> --db <一時>/map.db --listen 127.0.0.1:3002 --grafana-token-file <無いファイル>
  → http://127.0.0.1:3002/home?room=dev&relay=ws://127.0.0.1:3010/ws/audio/dev

場面を変える（<dir> にファイルを置く／消す）：
  <dir>/pause  … 車が値を送らなくなる（「値が届いていません」）
  <dir>/stop   … 車が止まる（速度0。操作に4桁の確認が出なくなる）
  <dir>/hot    … 油温が高い（警告の色）
  <dir>/deaf   … ロガーが命令に返事をしない（「返事がありません」）

`websockets` が要る（live_bridge.py と同じ）。
"""
import argparse
import asyncio
import json
import math
import os
import secrets
import sys
import time
from pathlib import Path

import websockets

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'EcoCapture-Web'))
from lap import LapLine, LapTimer  # noqa: E402  線の持ち方も本体と同じ
from remote_command import RemoteCommands  # noqa: E402  本体と同じ確かめ方

NAMES = ['Interval', 'Utc', 'Latitude', 'Longitude', 'Speed', 'GPSSats', 'RaceTime', 'ElapsedTime', 'LapCount',
         'CurrentLap', 'LapTime', 'BestLap', 'OilTemp', 'WaterTemp']
LAP_S = 110.0
CENTER = (35.0000, 139.0000)   # 作りものの場所（実在のコースではない）


class Car:
    """周回する作りものの車。ラップの値は本体と同じ単位（時間は分）で出す。"""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.count = 3
        self.race_start = time.time() - 3 * LAP_S - 40
        self.lap_start = time.time() - 40
        self.last_lap, self.best = 111.84, 110.37
        self.logging = True
        root = self.folder / 'logger'
        courses = root / 'setups' / 'courses'
        courses.mkdir(parents=True, exist_ok=True)
        for name, title, east in (('dev-east', '作りもの（東の線）', 0.004), ('dev-west', '作りもの（西の線）', -0.004)):
            line = {'enabled': True, 'lat': CENTER[0], 'lon': CENTER[1] + east, 'bearing': 0.0, 'width_m': 40.0,
                    'sectors': [{'lat': CENTER[0] + 0.003, 'lon': CENTER[1], 'bearing': 270.0, 'width_m': 30.0}] if east > 0 else []}
            (courses / f'{name}.json').write_text(json.dumps({'id': name, 'name': title, 'line': line}, ensure_ascii=False), encoding='utf-8')
        self.timer = LapTimer(root)
        if not self.timer.line.enabled:   # はじめは、どのコースの設定とも違う線
            self.timer.configure(LapLine(enabled=True, lat=CENTER[0], lon=CENTER[1] + 0.0041, bearing=0.0, width_m=40.0))

    def flag(self, name):
        return (self.folder / name).exists()

    def row(self, now):
        stopped = self.flag('stop')
        if self.lap_start is not None and not stopped and now - self.lap_start >= LAP_S:
            self.last_lap = round(LAP_S + math.sin(now) * 1.2, 2)
            self.best = self.last_lap if self.best is None else min(self.best, self.last_lap)
            self.count += 1
            self.lap_start = now
        phase = ((now - self.lap_start) / LAP_S if self.lap_start else 0) * 2 * math.pi
        values = {
            'Interval': 100, 'Utc': round(now * 1000),
            'Latitude': CENTER[0] + 0.003 * math.sin(phase), 'Longitude': CENTER[1] + 0.004 * math.cos(phase),
            'Speed': 0.0 if stopped else 120 + 35 * math.sin(phase * 3), 'GPSSats': 19,
            'LapCount': self.count, 'CurrentLap': self.count + 1 if self.lap_start is not None else 0,
            'OilTemp': 123.0 if self.flag('hot') else 104 + 3 * math.sin(now / 60), 'WaterTemp': 91 + 2 * math.sin(now / 45),
        }
        if self.last_lap is not None:   # 値が無い項目は、その行のビットを落として詰める（本体と同じ）
            values['LapTime'] = self.last_lap / 60
        if self.best is not None:
            values['BestLap'] = self.best / 60
        if self.race_start is not None:
            values['RaceTime'] = (now - self.race_start) / 60
        if self.lap_start is not None:
            values['ElapsedTime'] = (now - self.lap_start) / 60
        present = [n for n in NAMES if n in values]
        mask = sum(1 << i for i, n in enumerate(NAMES) if n in values)
        return [*(values[n] for n in present), mask]

    # ---- RemoteCommands が使う「本体」の形
    @property
    def line(self):
        return self.timer.line

    @property
    def path(self):
        return self.timer.path

    def configure(self, line):   # 線が動いたら、本体と同じく走っている周を捨てる（次に計測を始めるまでスタート前）
        self.timer.state['lap_start_ms'] = 1 if self.lap_start is not None else None
        self.timer.configure(line)
        if self.timer.state['lap_start_ms'] is None:
            self.lap_start = None

    @property
    def laps(self):
        return self

    @property
    def state(self):
        return {'lap_start_ms': None if self.lap_start is None else round(self.lap_start * 1000), 'finished': False}

    def values(self):
        return {'LapCount': self.count, 'CurrentLap': self.count + 1,
                'RaceTime': None if self.race_start is None else (time.time() - self.race_start) / 60}

    def status(self):
        return {'logging': {'active': self.logging, 'elapsed_s': 754}, 'receive_hz': 99.8,
                'hardware': {'sd_logging': True}, 'video': {'recording': True}}

    def reset(self):   # 本体（lap.py の reset）と同じく、ベストも忘れる
        self.count, self.race_start, self.lap_start, self.last_lap, self.best = 0, None, None, None, None

    def set_count(self, n):
        self.count = n

    def start_now(self):
        if self.lap_start is not None:
            raise ValueError('a lap is already running')
        self.race_start = self.lap_start = time.time()


async def feed(car, room):
    folder = car.folder / room
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / time.strftime('%Y%m%d-%H%M%SZ.jsonl', time.gmtime())
    with open(path, 'w', encoding='utf-8') as f:
        f.write(json.dumps({'recv_ms': round(time.time() * 1000), 'meta': [{'nm': n} for n in NAMES]}) + '\n')
        f.flush()
        while True:
            await asyncio.sleep(0.5)
            if car.flag('pause'):
                continue
            now = time.time()
            packed = [car.row(now - 0.4 + k * 0.1) for k in range(5)]
            f.write(json.dumps({'recv_ms': round(now * 1000), 'samples': packed}) + '\n')
            f.flush()


async def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')   # ファイルへ流すとWindowsの文字コードで止まるため（2026-11-13）
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--dir', required=True, help='作りもののデータを書くフォルダー（live_bridge.py の --dir と同じ）')
    ap.add_argument('--room', default='dev')
    ap.add_argument('--relay-listen', default='127.0.0.1:3010')
    args = ap.parse_args()
    car = Car(args.dir)
    private = Path(args.dir) / 'logger' / 'private'
    private.mkdir(parents=True, exist_ok=True)
    secret_file = private / 'remote_command.json'
    if not secret_file.exists():
        secret_file.write_text(json.dumps({'secret': secrets.token_hex(32)}), encoding='utf-8')
    secret = json.loads(secret_file.read_text(encoding='utf-8'))['secret']
    commands = RemoteCommands(Path(args.dir) / 'logger', car, gnss_ms=lambda: round(time.time() * 1000))

    async def log_start():
        car.logging = True
    commands.actions['log_start'] = log_start

    async def relay(ws):
        if not ws.request.path.startswith(f'/ws/audio/{args.room}'):
            await ws.close()
            return
        async for raw in ws:
            if not isinstance(raw, str):
                continue
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            command = (event.get('data') or {}).get('command') if isinstance(event, dict) and event.get('type') == 'logger.config' else None
            if command is None:
                continue
            if car.flag('deaf'):
                print(f'命令 {command.get("op")}: 返事をしない（deaf）', flush=True)
                continue
            await asyncio.sleep(1.5)   # LTEの往復のつもり
            result = await commands.run(command)
            print(f'命令 {command.get("op")} {command.get("arg")}: {"OK" if result["ok"] else "断った"} — {result["message"]}', flush=True)
            await ws.send(json.dumps({'type': 'logger.config', 'data': {'command_result': result}}))

    host, port = args.relay_listen.rsplit(':', 1)
    print(f'合言葉（作りもの。この場かぎり）: {secret}', flush=True)
    print(f'表紙: http://127.0.0.1:3002/home?room={args.room}&relay=ws://{host}:{port}/ws/audio/{args.room}', flush=True)
    async with websockets.serve(relay, host, int(port)):
        await feed(car, args.room)


if __name__ == '__main__':
    asyncio.run(main())
