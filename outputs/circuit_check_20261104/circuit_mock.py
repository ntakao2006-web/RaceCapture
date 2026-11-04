"""Stand-in for the Ver.2 logger's course-walk server on the PC, for the Android circuit screen on
the emulator: EcoCapture-Web field.py's real app, fed with ecocapture_dash.DemoFeed (sped up).

The mode file (one word) changes what it sends while it runs:
  normal | mcu (the logger has no MCU: connected false) | nodash (an EcoCapture before the circuit
  screen: no dash block) | stop (speed 0) | oil=125 (the oil temperature)
  | press=70 (the oil pressure, kPa; DemoFeed runs 4800+-1600 rpm, so under 200 kPa warns)
  | water=113 | nopress (no oil pressure: not wired)
Values can be put together with commas: oil=125,press=70 (two warnings side by side), or
oil=128,water=113,press=70 (all three).
"""
import argparse
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(r'C:\Users\ntaka\Documents\ClaudeCode\RaceCapture')
sys.path[:0] = [str(ROOT / 'EcoCapture-Web'), str(ROOT / 'EcoCapture-Web' / 'vendor'), str(ROOT / 'RaceCapture-UNOQ')]

import uvicorn  # noqa: E402

import field  # noqa: E402
from ecocapture_dash import DemoFeed  # noqa: E402
from lap import LapTimer  # noqa: E402


class Runtime:
    def __init__(self, root, speed, mode_file):
        self.laps = LapTimer(root)
        self.t0 = time.monotonic()
        self.feed = DemoFeed(self.t0)
        self.speed, self.mode_file = speed, Path(mode_file)

    def mode(self):
        try:
            return self.mode_file.read_text().strip()
        except OSError:
            return 'normal'

    def frame(self):
        return self.feed.frame(self.t0 + (time.monotonic() - self.t0) * self.speed)

    def status(self):
        st = dict(self.frame()['status'])
        st['connected'] = self.mode() != 'mcu'
        return st

    @property
    def sample(self):
        s = self.frame()['sample']
        s['values'].update(GPSFix=3, GPSSats=14)
        names = {'oil': 'OilTemp', 'water': 'WaterTemp', 'press': 'OilPress'}
        for m in self.mode().split(','):
            key, _, value = m.strip().partition('=')
            if key in names and value:
                s['can_signals'][names[key]] = float(value)
            if key == 'nopress':
                s['can_signals'].pop('OilPress', None)
            if key == 'stop':
                s['values']['GPSSpeed'] = 0.0
        return s


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--speed', type=float, default=5.0)
    p.add_argument('--mode-file', default=str(Path(__file__).with_name('circuit_mode.txt')))
    p.add_argument('--port', type=int, default=8082)
    args = p.parse_args()
    root = Path(tempfile.mkdtemp(prefix='circuit-mock-'))
    (root / 'field_token').write_text('circuit-test-key')
    runtime = Runtime(root, args.speed, args.mode_file)
    live = field.live_frame

    def frame(rt):
        f = live(rt)
        if rt.mode() == 'nodash':
            f.pop('dash', None)
        return f
    field.live_frame = frame
    print('key', field.load_token(root), flush=True)
    uvicorn.run(field.create_app(runtime, field.load_token(root)), host='127.0.0.1', port=args.port, log_level='warning')


if __name__ == '__main__':
    main()
