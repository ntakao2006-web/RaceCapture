#!/usr/bin/python3
"""EcoCapture DASH: the driver screen on the UNO Q's HDMI (Xorg :2), drawn from EcoCapture's telemetry.

Runs as ecocapture-dash.service in place of the RaceCapture app: the two units conflict, so
starting one stops the other (dash_switch.sh). Acquisition, eMMC/SD recording and RCP are not
touched; the EcoCapture admin window underneath is paused as touch_launcher.py does. What is
shown is worked out in dash_model.py. Settings: ~/.config/ecocapture-dash.json (dash_model.DEFAULTS).

  ecocapture_dash.py                    the dash
  ecocapture_dash.py --demo             a made-up drive (laps, the gap, a pit stop, oil heating up to 130 C,
                                        two oil pressure drops: one alone, one with the temperatures)
  ecocapture_dash.py --state warn       one fixed screen: normal start pit pitbox warn warnpress warn2 warn3
                                        lost stale (warn2: oil pressure + oil, warn3: all three warnings)
  ecocapture_dash.py --sound warn       play the warning sound once and exit (--volume 0.3)
  --size 1920x1080 --snapshot out.png   window size, and save the first frame as PNG then exit
  --no-pause                            leave the other display apps alone (checking on a running UNO Q)
"""
from __future__ import annotations

import argparse
import atexit
import json
import math
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dash_model import DashModel, load_config, tone_wav  # noqa: E402

CONFIG_PATH = Path.home() / '.config' / 'ecocapture-dash.json'
LAPREF_PATH = Path.home() / '.cache' / 'ecocapture-dash' / 'lapref.json'
FONT_NUM = "'DejaVu Sans', 'Noto Sans CJK JP', sans-serif"
FONT_TEXT = "'Noto Sans CJK JP', 'DejaVu Sans', sans-serif"
WARN_SCALE = {1: 1.0, 2: 0.75, 3: 0.55}  # the warnings in the band, by how many are on (they share its width)
FLASH_PERIOD_S = 0.5  # bright and dark red twice a second while flashing (under 3 a second: photosensitivity)


class Sound:
    """Plays the warning WAVs with aplay (on the UNO Q: HDMI to the monitor's speaker)."""

    def __init__(self, config):
        self.config = config['sound']
        self.proc = None
        for control in self.config.get('route', []) if self.config.get('enabled', True) else []:
            # the mixer path to the speaker (dash_model.DEFAULTS)
            try:
                subprocess.run(['amixer', '-q', '-c', self.config.get('card', '0'), 'cset', f'name={control}', '1'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except (OSError, subprocess.SubprocessError):
                pass
        self.folder = Path(tempfile.mkdtemp(prefix='ecocapture-dash-'))
        atexit.register(shutil.rmtree, self.folder, True)
        self.files = {}
        for kind in ('warn',):
            path = self.folder / f'{kind}.wav'
            path.write_bytes(tone_wav(kind, self.config.get('volume', 0.8), repeat=self.config.get('repeat', 6)))
            self.files[kind] = path

    def play(self, kind):
        if not self.config.get('enabled', True) or kind not in self.files:
            return None
        if self.proc and self.proc.poll() is None:
            return None
        command = [part.format(device=self.config.get('device', 'default'), file=self.files[kind])
                   for part in self.config.get('command', ['aplay', '-q', '-D', '{device}', '{file}'])]
        try:
            self.proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            self.proc = None
        return self.proc


def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=1.0) as response:
            return json.loads(response.read())
    except (OSError, ValueError):
        return None


class DemoFeed:
    """A made-up drive on a 2.5 km circle (not a real course): laps of about 1:53, the oil
    heating from 95 C to 133 C over eight minutes, a pit lap every seventh lap, and in every ten minutes
    two six-second oil pressure drops (at 200 s alone, at 440 s with the oil and water over their limits)."""
    LAT0, LON0, RADIUS = 38.14, 140.77, 400.0

    def __init__(self, start):
        self.t0 = start

    @staticmethod
    def lap_s(k):
        return 2 * math.pi * DemoFeed.RADIUS / (22.2 * (1 + .015 * math.sin(1.3 * k + 2.5)))

    def frame(self, now):
        t = now - self.t0 - 5.0  # five seconds waiting for the start
        lap = {'CurrentLap': 0, 'LapCount': 0, 'ElapsedTime': None, 'LapTime': None, 'BestLap': None,
               'RaceTime': None, 'LapDiffS': None, 'LastLapPit': None}
        lat, lon = self.LAT0 - self.RADIUS / 111320.0, self.LON0
        if t >= 0:
            k, begin, times = 1, 0.0, []
            while begin + self.lap_s(k) <= t:
                times.append(self.lap_s(k)); begin += self.lap_s(k); k += 1
            into = t - begin
            angle = 2 * math.pi * into / self.lap_s(k) - math.pi / 2
            lat = self.LAT0 + self.RADIUS * math.sin(angle) / 111320.0
            lon = self.LON0 + self.RADIUS * math.cos(angle) / (111320.0 * math.cos(math.radians(self.LAT0)))
            pit = lambda n: n % 7 in (0, 1) and n > 1
            lap.update(CurrentLap=k, LapCount=k - 1, ElapsedTime=into / 60, RaceTime=t / 60, LapStartPit=pit(k) and pit(k - 1))
            if times:
                lap.update(LapTime=times[-1] / 60, BestLap=min(times) / 60, LastLapPit=pit(k - 1))
                if len(times) >= 2 and not pit(k - 1) and not pit(k - 2):
                    lap['LapDiffS'] = round(times[-1] - times[-2], 3)
        cycle = (now - self.t0) % 600
        oil = 95 + 38 * cycle / 480 if cycle < 480 else 133 - 30 * (cycle - 480) / 120
        rpm = 4800 + 1600 * math.sin(now - self.t0)
        press = 70.0 if 200 <= cycle < 206 or 440 <= cycle < 446 else min(480.0, 60 + 0.07 * rpm)
        return {'status': {'connected': True, 'logging': {'active': True},
                           'video': {'recording': True, 'minutes_left': max(0, 150 - (now - self.t0) / 60)}},
                'sample': {'values': {'Lat': lat, 'Lon': lon, 'GPSSpeed': 80.0, 'RPM': rpm},
                           'can_signals': {'OilTemp': oil, 'WaterTemp': oil - 10, 'OilPress': press},
                           'gnss_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'lap': lap}}


def fixed_state(config, name):
    """One screen for checking the layout (the gap is filled in by hand: it needs a best lap's track)."""
    lap = {'CurrentLap': 23, 'LapCount': 22, 'ElapsedTime': 72.3 / 60, 'LapTime': 112.34 / 60, 'BestLap': 111.12 / 60,
           'RaceTime': 2175 / 60, 'LapDiffS': 0.41, 'LastLapPit': False}
    # oil C, water C, oil pressure kPa (at 5200 rpm; idling in the box): warn is the oil alone,
    # warnpress the pressure alone, warn2 pressure and oil, warn3 all three
    temps = {'normal': (98, 88, 420), 'start': (92, 84, 430), 'pit': (101, 91, 410), 'pitbox': (101, 91, 150),
             'warn': (122, 104, 400), 'warnpress': (104, 94, 85), 'warn2': (124, 105, 150), 'warn3': (128, 113, 140),
             'lost': (None, 93, 420), 'stale': (98, 88, 420)}[name]
    if name == 'start':
        lap.update(CurrentLap=0, LapCount=0, ElapsedTime=None, LapTime=None, BestLap=None, RaceTime=None, LapDiffS=None, LastLapPit=None)
    if name in ('pit', 'pitbox'):  # the in lap was a pit lap, the running lap started in the pit lane
        lap.update(ElapsedTime=21.4 / 60, LapTime=221.07 / 60, LapDiffS=None, LastLapPit=True, LapStartPit=True)
    # before the start the video light is yellow: 108 minutes left is short of the race
    frame = {'status': {'connected': True, 'logging': {'active': True},
                        'video': {'recording': True, 'minutes_left': 108 if name == 'start' else 150}},
             'sample': {'values': {'Lat': 38.1423, 'Lon': 140.777, 'GPSSpeed': 0.0 if name == 'pitbox' else 120.0,
                                   'RPM': 900.0 if name == 'pitbox' else 5200.0},
                        'can_signals': {'OilTemp': temps[0], 'WaterTemp': temps[1], 'OilPress': temps[2]},
                        'gnss_utc': '2026-11-08T02:16:15Z', 'lap': lap}}
    model = DashModel(config)
    for k in range(80):  # past the warning hold time
        state, _ = model.update(frame, 100.0 + k * 0.1)
    if name == 'stale':
        state, _ = model.update(None, 100.0 + 8 + 12)
    if name not in ('start', 'stale', 'pit', 'pitbox'):
        state.update(delta='−0.84', delta_kind='faster', delta_frac=-0.42)
    return state


def css_for(w, h):
    big = int(min(0.195 * h, 0.11 * w))
    mid, small = int(big * 0.6), int(big * 0.44)
    cap, chip = int(max(16, 0.042 * h)), int(max(16, 0.036 * h))
    rad, cp = int(0.012 * h), int(0.012 * h)
    return f"""
    window, .root {{ background-color: #000000; }}
    .cell {{ background-color: #151515; border-radius: {rad}px; padding: {cp}px {int(cp * 1.6)}px; }}
    .cap {{ color: #a8a8a8; font-family: {FONT_TEXT}; font-size: {cap}px; }}
    .note {{ font-family: {FONT_NUM}; font-size: {int(cap * 1.25)}px; font-weight: bold; }}
    .num {{ color: #f4f4f4; font-family: {FONT_NUM}; font-weight: bold; }}
    .big {{ font-size: {big}px; }}
    .mid {{ font-size: {mid}px; }}
    .small {{ font-size: {small}px; }}
    .waiting {{ font-family: {FONT_TEXT}; font-size: {int(small * 0.8)}px; color: #ffd060; }}
    .faster {{ color: #38e05a; }}
    .slower {{ color: #ff4a4a; }}
    .even {{ color: #f4f4f4; }}
    .pitnote {{ color: #5aaeff; }}
    .bar-bg {{ background-color: #2c2c2c; }}
    .bar-mid {{ background-color: #9a9a9a; }}
    .bar-faster {{ background-color: #2fc64c; }}
    .bar-slower {{ background-color: #e83a3a; }}
    .chip {{ font-family: {FONT_TEXT}; font-size: {chip}px; font-weight: bold; padding: 2px {int(chip * 0.5)}px; border-radius: {rad}px; }}
    .chip-ok {{ color: #38e05a; background-color: #0f2a14; }}
    .chip-warn {{ color: #1c1000; background-color: #ffb020; }}
    .chip-bad {{ color: #ffffff; background-color: #d81e1e; }}
    .notice {{ font-family: {FONT_TEXT}; font-size: {int(mid * 0.55)}px; font-weight: bold; border-radius: {rad}px; }}
    .notice-none {{ background-color: transparent; color: transparent; }}
    .notice-pit {{ background-color: #1f64c8; color: #ffffff; }}
    .banner {{ background-color: #e01414; border-radius: {rad}px; }}
    .banner.banner-dim {{ background-color: #520808; }}
    .banner label {{ color: #ffffff; font-weight: bold; }}
    .banner .warn-name {{ font-family: {FONT_TEXT}; }}
    .banner .warn-val {{ font-family: {FONT_NUM}; }}
    {''.join(f'.banner .warn-name.n{n} {{ font-size: {int(mid * 0.9 * k)}px; }} .banner .warn-val.n{n} {{ font-size: {int(big * k)}px; }} '
             for n, k in WARN_SCALE.items())}
    .stale {{ background-color: #1a1a1a; }}
    .stale label {{ color: #d8d8d8; font-family: {FONT_TEXT}; }}
    .stale-big {{ font-size: {int(mid * 0.6)}px; font-weight: bold; }}
    .stale-sub {{ font-size: {cap}px; }}
    """.encode()


def run_gui(args, config):
    import warnings
    warnings.filterwarnings('ignore', category=DeprecationWarning)  # Gdk.Screen.get_width / get_height
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, GLib, Gtk, Pango

    def label(text, *classes, xalign=0.0):
        widget = Gtk.Label(label=text)
        widget.set_xalign(xalign)
        widget.set_ellipsize(Pango.EllipsizeMode.END)
        for name in classes:
            widget.get_style_context().add_class(name)
        return widget

    def classes(widget, *names, keep=()):
        context = widget.get_style_context()
        for name in context.list_classes():
            if name not in keep and name not in names:
                context.remove_class(name)
        for name in names:
            context.add_class(name)

    def box(vertical=False, *children, spacing=0, cls=None):
        widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL, spacing=spacing)
        for child in children:
            widget.pack_start(child, False, False, 0)
        if cls:
            widget.get_style_context().add_class(cls)
        return widget

    class Dash(Gtk.Window):
        def __init__(self):
            super().__init__(title='EcoCapture DASH')
            self.set_decorated(False)
            screen = self.get_screen()
            if args.size:
                self.size = tuple(int(v) for v in args.size.lower().split('x'))
            else:  # one X screen, one output: the screen is what to cover (deprecated in GTK 3.22, still there)
                self.size = (screen.get_width(), screen.get_height())
            self.set_default_size(*self.size)
            self.move(0, 0)
            self.css = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_screen(screen, self.css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.build()
            self.apply_size(*self.size)
            self.connect('realize', self.on_realize)
            self.connect('configure-event', self.on_configure)
            screen.connect('size-changed', self.on_screen)  # the HDMI mode set again after a reconnect
            self.connect('destroy', lambda _w: Gtk.main_quit())

        def build(self):
            self.lap_now = label('--', 'num', 'big')
            self.delta = label('--', 'num', 'big')
            self.bar = Gtk.Fixed()
            self.bar_bg, self.bar_fill, self.bar_mid = Gtk.Box(), Gtk.Box(), Gtk.Box()
            self.bar_bg.get_style_context().add_class('bar-bg')
            self.bar_mid.get_style_context().add_class('bar-mid')
            for part in (self.bar_bg, self.bar_fill, self.bar_mid):
                self.bar.put(part, 0, 0)
            # A normal pit stop is information, not a warning: a blue strip under the running lap.
            # Always there (empty when nothing to say), so the numbers never move.
            self.notice = label('', 'notice', 'notice-none', xalign=0.5)
            self.cell_now = box(True, label('今の周', 'cap'), self.lap_now, self.notice, cls='cell')
            self.bar_holder = box(True)  # as tall as the strip, so the two big numbers stay level
            self.bar_holder.pack_start(self.bar, True, False, 0)
            self.bar.set_valign(Gtk.Align.CENTER)
            self.cell_delta = box(True, label('ベスト比', 'cap'), self.delta, self.bar_holder, cls='cell')
            self.row1 = Gtk.Box(spacing=0, homogeneous=True)
            self.row1.pack_start(self.cell_now, True, True, 0)
            self.row1.pack_start(self.cell_delta, True, True, 0)

            self.last = label('--', 'num', 'mid')
            self.last_note = label('', 'note')
            self.best = label('--', 'num', 'mid')
            self.lap_no = label('--', 'num', 'mid')
            cap_last = box(False, label('前周', 'cap'), self.last_note)
            self.cell_last = box(True, cap_last, self.last, cls='cell')
            self.cell_best = box(True, label('ベスト', 'cap'), self.best, cls='cell')
            self.cell_lap = box(True, label('周', 'cap'), self.lap_no, cls='cell')
            self.row2 = box(False, self.cell_last, self.cell_best, self.cell_lap)
            for cell, value in ((self.cell_now, self.lap_now), (self.cell_delta, self.delta), (self.cell_last, self.last),
                                (self.cell_best, self.best), (self.cell_lap, self.lap_no)):
                cell.set_child_packing(value, True, True, 0, Gtk.PackType.START)  # the number centred below its caption
            # The warnings: a red band over the middle row, each warning that is on side by side with its
            # value big (oil pressure first). The running lap, the gap and the bottom row stay readable
            # (never the whole screen: the pit must see the rest).
            self.warn_items = []
            self.warn_row = Gtk.Box(homogeneous=True)
            for _ in range(len(WARN_SCALE)):
                name, value = label('', 'warn-name'), label('', 'warn-val')
                for widget in (name, value):
                    widget.set_ellipsize(Pango.EllipsizeMode.NONE)
                    widget.set_valign(Gtk.Align.CENTER)
                item = box(False, name, value)
                item.set_halign(Gtk.Align.CENTER)
                self.warn_row.pack_start(item, True, True, 0)
                self.warn_items.append((item, name, value))
            self.banner = box(False, cls='banner')
            self.banner.set_center_widget(self.warn_row)
            self.stack = Gtk.Stack()
            self.stack.add_named(self.row2, 'normal')
            self.stack.add_named(self.banner, 'banner')

            self.elapsed = label('--', 'num', 'small')
            self.clock = label('--', 'num', 'small')
            self.chip_rec = label('記録', 'chip', xalign=0.5)
            self.chip_gnss = label('GNSS', 'chip', xalign=0.5)
            self.chip_oil = label('油温センサー', 'chip', xalign=0.5)
            for widget in (self.elapsed, self.clock):
                widget.set_ellipsize(Pango.EllipsizeMode.NONE)  # the lights give way, never the numbers
            self.row3 = Gtk.Box(spacing=0)
            self.row3.get_style_context().add_class('cell')
            self.cap_elapsed, self.cap_clock = label('経過', 'cap'), label('時刻', 'cap')
            for widget in (self.cap_elapsed, self.elapsed, self.cap_clock, self.clock):
                widget.set_valign(Gtk.Align.CENTER)
                self.row3.pack_start(widget, False, False, 0)
            for chip in (self.chip_oil, self.chip_gnss, self.chip_rec):
                chip.set_valign(Gtk.Align.CENTER)
                self.row3.pack_end(chip, False, False, 0)

            self.root = box(True, self.row1, self.stack, self.row3, cls='root')
            self.stale_big = label('', 'stale-big', xalign=0.5)
            self.stale_sub = label('', 'stale-sub', xalign=0.5)
            self.stale = box(True, cls='stale')
            self.stale.set_center_widget(box(True, self.stale_big, self.stale_sub, spacing=12))
            self.overlay = Gtk.Overlay()
            self.overlay.add(self.root)
            self.overlay.add_overlay(self.stale)
            self.add(self.overlay)

        def apply_size(self, w, h):
            self.size = (w, h)
            try:
                self.css.load_from_data(css_for(w, h))
            except GLib.Error as exc:  # an older GTK without a property: keep going with the rest
                print('css:', exc, file=sys.stderr)
            pad, gap = int(0.015 * h), int(0.011 * h)
            inner_w, inner_h = w - 2 * pad, h - 2 * pad - 2 * gap
            self.root.set_spacing(gap)
            self.root.set_margin_top(pad); self.root.set_margin_bottom(pad)
            self.root.set_margin_start(pad); self.root.set_margin_end(pad)
            self.row1.set_spacing(gap); self.row2.set_spacing(gap)
            r1, r2 = int(inner_h * 0.45), int(inner_h * 0.33)
            self.row1.set_size_request(inner_w, r1)
            self.stack.set_size_request(inner_w, r2)
            self.row3.set_size_request(inner_w, inner_h - r1 - r2)
            avail = inner_w - 2 * gap
            for cell, share in ((self.cell_last, .42), (self.cell_best, .34), (self.cell_lap, .24)):
                cell.set_size_request(int(avail * share), r2)
            self.row3.set_spacing(int(0.012 * w))
            self.cap_clock.set_margin_start(int(0.03 * w))
            for chip in (self.chip_rec, self.chip_gnss):
                chip.set_margin_start(int(0.006 * w))
            cell_pad = int(0.012 * h) * 1.6
            self.bar_w = int((inner_w - gap) / 2 - 2 * cell_pad)
            self.bar_h = max(10, int(0.028 * h))
            self.bar.set_size_request(self.bar_w, self.bar_h)
            strip_h = int(0.105 * h)
            self.notice.set_size_request(-1, strip_h)
            self.bar_holder.set_size_request(-1, strip_h)
            self.bar_bg.set_size_request(self.bar_w, self.bar_h)
            self.bar_mid.set_size_request(max(2, int(0.003 * w)), self.bar_h + 0)
            self.bar.move(self.bar_mid, self.bar_w // 2 - max(2, int(0.003 * w)) // 2, 0)

        def on_configure(self, _widget, event):
            if (event.width, event.height) != self.size and not args.size:
                self.apply_size(event.width, event.height)
            return False

        def on_screen(self, screen):
            if not args.size:
                self.resize(screen.get_width(), screen.get_height())
                self.apply_size(screen.get_width(), screen.get_height())

        def on_realize(self, _widget):
            window = self.get_window()
            if not args.size:
                window.set_override_redirect(True)  # no window manager on :2; cover the whole screen
            window.set_cursor(Gdk.Cursor.new_for_display(window.get_display(), Gdk.CursorType.BLANK_CURSOR))

        def keep_above(self):
            window = self.get_window()
            if window:
                window.raise_()
            return True

        def show_state(self, s):
            self.stale.set_visible(bool(s['stale']))
            if s['stale']:
                waited = s.get('stale_s')
                self.stale_big.set_text('ロガーの値を待っています' if waited is None else 'ロガーの値が来ていません')
                self.stale_sub.set_text('' if waited is None else f'最後に受け取ってから {int(waited)} 秒')
            warns = s['warns'][:len(self.warn_items)]
            self.stack.set_visible_child_name('banner' if warns else 'normal')
            # flashing just after a warning comes on: dark red half the time, the white text stays
            dim = bool(s.get('warn_flash')) and time.monotonic() % FLASH_PERIOD_S >= FLASH_PERIOD_S / 2
            classes(self.banner, 'banner', *(('banner-dim',) if dim else ()))
            n, w = max(1, len(warns)), self.size[0]
            self.warn_row.set_spacing(int(0.04 * w))
            for k, (item, name, value) in enumerate(self.warn_items):
                item.set_visible(k < len(warns))
                if k >= len(warns):
                    continue
                item.set_spacing(int(0.025 * w * WARN_SCALE[n]))
                name.set_text(warns[k]['label'])
                # the unit smaller, as the s of the gap: the number is the thing to read
                value.set_markup(f"{warns[k]['value']}<span size=\"60%\">{warns[k]['unit']}</span>")
                classes(name, 'warn-name', f'n{n}')
                classes(value, 'warn-val', f'n{n}')
            self.notice.set_text(s['notice'])
            classes(self.notice, 'notice', 'notice-pit' if s['notice'] else 'notice-none')

            self.lap_now.set_text(s['lap_now'])
            if s['delta_kind']:  # a number: say it is seconds, smaller, so the number stays the thing to read
                self.delta.set_markup(f"{s['delta']}<span size=\"55%\">s</span>")
            else:
                self.delta.set_text(s['delta'])
            classes(self.delta, 'num', 'big', s['delta_kind'] or 'even')
            frac = s['delta_frac']
            half = self.bar_w // 2
            if frac is None or abs(frac) < 1e-3:
                self.bar_fill.set_visible(False)
            else:
                width = max(2, int(half * abs(frac)))
                self.bar_fill.set_size_request(width, self.bar_h)
                self.bar.move(self.bar_fill, half - width if frac < 0 else half, 0)
                classes(self.bar_fill, 'bar-faster' if frac < 0 else 'bar-slower')
                self.bar_fill.set_visible(True)
            self.last.set_text(s['last'])
            self.last_note.set_text(('　' + s['last_note']) if s['last_note'] else '')
            classes(self.last_note, 'note', {'pit': 'pitnote', 'slower': 'slower', 'faster': 'faster'}.get(s['last_note_kind'], 'even'))
            self.best.set_text(s['best'])
            self.lap_no.set_text(s['lap_no'])
            waiting = s['elapsed'] == 'スタート待ち'
            self.elapsed.set_text(s['elapsed'])
            classes(self.elapsed, *(('waiting',) if waiting else ('num', 'small')))
            self.clock.set_text(s['clock'])
            # One light for recording (the row has no room for a fourth: the oil warning must stay readable):
            # the log stopped, else the burnt-in video short of time or not recording, else all well
            if not s['rec']:
                self.chip_rec.set_text('記録停止')
                classes(self.chip_rec, 'chip', 'chip-bad')
            elif s.get('video_kind') == 'warn':
                self.chip_rec.set_text(s['video'])
                classes(self.chip_rec, 'chip', 'chip-warn')
            else:
                self.chip_rec.set_text('記録中')
                classes(self.chip_rec, 'chip', 'chip-ok')
            self.chip_gnss.set_text('GNSS' if s['gnss'] else 'GNSS未測位')
            classes(self.chip_gnss, 'chip', 'chip-ok' if s['gnss'] else 'chip-warn')
            # the oil sensors (the oil pressure only once it has come): yellow when one is lost
            # (the water temperature still warns for a lost oil temperature)
            text, ok = s['sensor']
            self.chip_oil.set_text(text)
            classes(self.chip_oil, 'chip', 'chip-ok' if ok else 'chip-warn')

    dash = Dash()
    dash.show_all()
    dash.stale.set_visible(False)
    sound = None if args.state or args.snapshot else Sound(config)  # a layout check never makes a sound
    lock = threading.Lock()
    latest = {}

    if args.state:
        latest['state'] = fixed_state(config, args.state)
    else:
        model = DashModel(config, None if args.demo else LAPREF_PATH)
        demo = DemoFeed(time.monotonic()) if args.demo else None

        def poll():
            while True:
                started = time.monotonic()
                frame = demo.frame(started) if demo else fetch(config['api'])
                state, kind = model.update(frame, time.monotonic())
                if kind and sound:
                    sound.play(kind)
                with lock:
                    latest['state'] = state
                time.sleep(max(.02, .1 - (time.monotonic() - started)))
        threading.Thread(target=poll, daemon=True).start()

    def tick():
        with lock:
            state = latest.get('state')
        if state:
            dash.show_state(state)
        return True

    if not args.no_pause and not args.snapshot:  # the covered admin window, as touch_launcher.py does
        try:
            from display_load_control import set_paused
            set_paused('ecocapture-native', True)
            atexit.register(set_paused, 'ecocapture-native', False)
        except Exception:
            pass

    def stop(*_args):
        GLib.idle_add(Gtk.main_quit)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    GLib.timeout_add(100, tick)  # the values come at most 10 times a second
    GLib.timeout_add(1000, dash.keep_above)
    if args.snapshot:
        def snap():
            tick()
            while Gtk.events_pending():
                Gtk.main_iteration()
            window = dash.get_window()
            pixbuf = Gdk.pixbuf_get_from_window(window, 0, 0, *dash.size)
            pixbuf.savev(args.snapshot, 'png', [], [])
            Gtk.main_quit()
            return False
        GLib.timeout_add(1500, snap)
    Gtk.main()


def main(argv=None):
    parser = argparse.ArgumentParser(description='EcoCapture DASH')
    parser.add_argument('--config', default=str(CONFIG_PATH))
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--state', choices=['normal', 'start', 'pit', 'pitbox', 'warn', 'warnpress', 'warn2', 'warn3',
                                            'lost', 'stale'])
    parser.add_argument('--sound', choices=['warn'])
    parser.add_argument('--size')
    parser.add_argument('--snapshot')
    parser.add_argument('--no-pause', action='store_true')
    parser.add_argument('--volume', type=float, help='with --sound: 0 (silent, checks the path) to 1')
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.sound:
        sound = {**config['sound'], 'enabled': True}
        if args.volume is not None:
            sound['volume'] = args.volume
        proc = Sound({**config, 'sound': sound}).play(args.sound)
        return 0 if proc is not None and proc.wait() == 0 else 1
    run_gui(args, config)
    return 0


if __name__ == '__main__':
    sys.exit(main())
