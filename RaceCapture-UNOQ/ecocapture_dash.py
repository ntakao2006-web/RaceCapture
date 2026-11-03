#!/usr/bin/python3
"""EcoCapture DASH: the driver screen on the UNO Q's HDMI (Xorg :2), drawn from EcoCapture's telemetry.

Runs as ecocapture-dash.service in place of the RaceCapture app: the two units conflict, so
starting one stops the other (dash_switch.sh). Acquisition, eMMC/SD recording and RCP are not
touched; the EcoCapture admin window underneath is paused as touch_launcher.py does. What is
shown is worked out in dash_model.py. Settings: ~/.config/ecocapture-dash.json (dash_model.DEFAULTS).

  ecocapture_dash.py                    the dash
  ecocapture_dash.py --demo             a made-up drive (laps, the gap, a pit stop, oil heating up to 130 C)
  ecocapture_dash.py --state warn120    one fixed screen: normal start pit warn110 warn120 warn130 lost stale
  ecocapture_dash.py --sound warn       play one warning sound and exit (warn / pit)
  --size 1920x1080 --snapshot out.png   window size, and save the first frame as PNG then exit
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


class Sound:
    """Plays the warning WAVs with aplay (on the UNO Q: HDMI to the monitor's speaker)."""

    def __init__(self, config):
        self.config = config['sound']
        self.proc = None
        self.folder = Path(tempfile.mkdtemp(prefix='ecocapture-dash-'))
        atexit.register(shutil.rmtree, self.folder, True)
        self.files = {}
        for kind in ('warn', 'pit'):
            path = self.folder / f'{kind}.wav'
            path.write_bytes(tone_wav(kind, self.config.get('volume', 0.8)))
            self.files[kind] = path

    def play(self, kind):
        if not self.config.get('enabled', True) or kind not in self.files:
            return None
        if self.proc and self.proc.poll() is None:
            if kind != 'pit':
                return None
            self.proc.terminate()  # the 130 C alarm cuts a running caution beep
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
    heating from 95 C to 133 C over eight minutes, a pit lap every seventh lap."""
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
        oil = 95 + 38 * ((now - self.t0) % 600) / 480 if (now - self.t0) % 600 < 480 else 133 - 30 * ((now - self.t0) % 600 - 480) / 120
        return {'status': {'connected': True, 'logging': {'active': True}},
                'sample': {'values': {'Lat': lat, 'Lon': lon, 'GPSSpeed': 80.0},
                           'can_signals': {'OilTemp': oil, 'WaterTemp': oil - 10},
                           'gnss_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'lap': lap}}


def fixed_state(config, name):
    """One screen for checking the layout (the gap is filled in by hand: it needs a best lap's track)."""
    lap = {'CurrentLap': 23, 'LapCount': 22, 'ElapsedTime': 72.3 / 60, 'LapTime': 112.34 / 60, 'BestLap': 111.12 / 60,
           'RaceTime': 2175 / 60, 'LapDiffS': 0.41, 'LastLapPit': False}
    temps = {'normal': (98, 88), 'start': (92, 84), 'pit': (101, 91), 'warn110': (112, 101), 'warn120': (122, 111),
             'warn130': (131, 120), 'lost': (None, 93), 'stale': (98, 88)}[name]
    if name == 'start':
        lap.update(CurrentLap=0, LapCount=0, ElapsedTime=None, LapTime=None, BestLap=None, RaceTime=None, LapDiffS=None, LastLapPit=None)
    if name == 'pit':  # just out of the pit lane: the in lap was a pit lap, the running lap is the out lap
        lap.update(ElapsedTime=21.4 / 60, LapTime=221.07 / 60, LapDiffS=None, LastLapPit=True, LapStartPit=True)
    frame = {'status': {'connected': True, 'logging': {'active': True}},
             'sample': {'values': {'Lat': 38.1423, 'Lon': 140.777, 'GPSSpeed': 120.0},
                        'can_signals': {'OilTemp': temps[0], 'WaterTemp': temps[1]},
                        'gnss_utc': '2026-11-08T02:16:15Z', 'lap': lap}}
    model = DashModel(config)
    for k in range(80):  # past the warning hold time
        state, _ = model.update(frame, 100.0 + k * 0.1)
    if name == 'stale':
        state, _ = model.update(None, 100.0 + 8 + 12)
    if name not in ('start', 'stale', 'pit'):
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
    .pitnote, .pittag {{ color: #5aaeff; }}
    .pittag {{ font-family: {FONT_TEXT}; font-size: {int(cap * 1.25)}px; font-weight: bold; }}
    .bar-bg {{ background-color: #2c2c2c; }}
    .bar-mid {{ background-color: #9a9a9a; }}
    .bar-faster {{ background-color: #2fc64c; }}
    .bar-slower {{ background-color: #e83a3a; }}
    .chip {{ font-family: {FONT_TEXT}; font-size: {chip}px; font-weight: bold; padding: 2px {int(chip * 0.5)}px; border-radius: {rad}px; }}
    .chip-ok {{ color: #38e05a; background-color: #0f2a14; }}
    .chip-warn {{ color: #1c1000; background-color: #ffb020; }}
    .chip-bad {{ color: #ffffff; background-color: #d81e1e; }}
    .banner {{ background-color: #e01414; border-radius: {rad}px; }}
    .banner label {{ color: #ffffff; font-family: {FONT_TEXT}; font-weight: bold; }}
    .pit {{ background-color: #e00000; border-radius: {rad}px; }}
    .pit-dark {{ background-color: #2a0000; border-radius: {rad}px; }}
    .pit label {{ color: #ffffff; font-family: {FONT_TEXT}; font-weight: bold; }}
    .pit-dark label {{ color: #ff6060; font-family: {FONT_TEXT}; font-weight: bold; }}
    .banner .warn-act {{ font-size: {int(mid * 0.85)}px; }}
    .banner .warn-name, .pit .warn-name, .pit-dark .warn-name {{ font-size: {int(cap * 1.3)}px; }}
    .banner .warn-val {{ font-family: {FONT_NUM}; font-size: {int(mid * 1.2)}px; }}
    .pit .warn-val, .pit-dark .warn-val {{ font-family: {FONT_NUM}; font-size: {int(big * 0.95)}px; }}
    .pit .pit-act, .pit-dark .pit-act {{ font-size: {int(mid * 0.9)}px; }}
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
            # A normal pit stop is information, not a warning: a blue tag, never red.
            self.lap_tag = label('', 'pittag')
            self.cell_now = box(True, box(False, label('今の周', 'cap'), self.lap_tag, spacing=int(0.015 * self.size[0])),
                                self.lap_now, cls='cell')
            self.cell_delta = box(True, label('ベスト比', 'cap'), self.delta, self.bar, cls='cell')
            # 130 C: the alarm takes the running lap's place only, so the rest stays readable in the pit.
            # The temperature first (what is wrong), then what to do.
            self.pit_name, self.pit_value = label('', 'warn-name'), label('', 'warn-val')
            pit_temp = box(False, self.pit_name, self.pit_value, spacing=int(0.015 * self.size[0]))
            pit_temp.set_halign(Gtk.Align.CENTER)
            self.pit = box(True, cls='pit')
            self.pit.set_center_widget(box(True, pit_temp, label('ピットイン', 'pit-act', xalign=0.5)))
            self.lap_stack = Gtk.Stack()
            self.lap_stack.add_named(self.cell_now, 'lap')
            self.lap_stack.add_named(self.pit, 'pit')
            self.row1 = Gtk.Box(spacing=0, homogeneous=True)
            self.row1.pack_start(self.lap_stack, True, True, 0)
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
            # The words small, the temperature big: what to do, then how hot.
            self.banner_name, self.banner_value = label('', 'warn-name'), label('', 'warn-val')
            self.banner = box(False, cls='banner')
            self.banner.set_center_widget(box(False, label('クーリング開始', 'warn-act'), self.banner_name, self.banner_value,
                                              spacing=int(0.02 * self.size[0])))
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
            self.bar.set_margin_top(int(0.01 * h))
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
            self.flash = args.state or int(time.monotonic() * 2) % 2 == 0  # the 130 C alarm flashes once a second
            self.stale.set_visible(bool(s['stale']))
            if s['stale']:
                waited = s.get('stale_s')
                self.stale_big.set_text('ロガーの値を待っています' if waited is None else 'ロガーの値が来ていません')
                self.stale_sub.set_text('' if waited is None else f'最後に受け取ってから {int(waited)} 秒')
            level = s['warn_level']
            self.lap_stack.set_visible_child_name('pit' if level >= 3 else 'lap')
            if level >= 3:
                classes(self.pit, 'pit' if self.flash else 'pit-dark')
                self.pit_name.set_text(s['warn_label'] or '')
                self.pit_value.set_text(s['warn_value'] or '')
            self.stack.set_visible_child_name('banner' if level == 2 else 'normal')
            if level == 2:
                self.banner_name.set_text(s['warn_label'] or '')
                self.banner_value.set_text(s['warn_value'] or '')

            self.lap_now.set_text(s['lap_now'])
            self.lap_tag.set_text(s.get('lap_tag', ''))
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
            self.chip_rec.set_text('記録中' if s['rec'] else '記録停止')
            classes(self.chip_rec, 'chip', 'chip-ok' if s['rec'] else 'chip-bad')
            self.chip_gnss.set_text('GNSS' if s['gnss'] else 'GNSS未測位')
            classes(self.chip_gnss, 'chip', 'chip-ok' if s['gnss'] else 'chip-warn')
            if level == 1:
                self.chip_oil.set_text(f"{s['warn_label']} {s['warn_value']}")
                classes(self.chip_oil, 'chip', 'chip-warn')
            elif s['oil_sensor']:
                self.chip_oil.set_text('油温センサー')
                classes(self.chip_oil, 'chip', 'chip-ok')
            else:
                self.chip_oil.set_text('油温センサー途絶')  # the water temperature still warns
                classes(self.chip_oil, 'chip', 'chip-warn')

    dash = Dash()
    dash.show_all()
    dash.stale.set_visible(False)
    sound = Sound(config)
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
                if kind:
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

    try:  # the covered admin window, as touch_launcher.py does (no-op off the UNO Q)
        from display_load_control import resume_all, set_paused
        set_paused('ecocapture-native', True)
        atexit.register(resume_all)
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
    parser.add_argument('--state', choices=['normal', 'start', 'pit', 'warn110', 'warn120', 'warn130', 'lost', 'stale'])
    parser.add_argument('--sound', choices=['warn', 'pit'])
    parser.add_argument('--size')
    parser.add_argument('--snapshot')
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.sound:
        proc = Sound({**config, 'sound': {**config['sound'], 'enabled': True}}).play(args.sound)
        return 0 if proc is not None and proc.wait() == 0 else 1
    run_gui(args, config)
    return 0


if __name__ == '__main__':
    sys.exit(main())
