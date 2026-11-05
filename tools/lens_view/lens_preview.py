#!/usr/bin/env python3
"""画角（ズーム・位置）を、車に付けたカメラの絵を本体のモニターで見ながら決める（UNO Q上で動かす）。

録画（overlay_rec）が録っている絵そのもの（歪みの補正・ズーム・計器込み）を、約3枚/秒でモニターに全画面で出す。
動かした値は /home/arduino/ecologger-video/lens.json へすぐ書き、録画は約1秒で新しい値で録り始める（録画は止めない）。
開いている間はEcoCapture DASHを止め、閉じるとDASHに戻す。10分さわらなければ、その時点の値のまま閉じる。

PCからは tools/lens_view/Lens-Preview.cmd で起動する（本体へこのファイルを送って、モニターに出す）。
本体で直接：  DISPLAY=:2 python3 lens_preview.py

操作（USBのマウス・キーボード。画面下のボタンでも同じことができる）
  マウスのホイール / ＋ － キー   : ズーム
  マウスの左ボタンで引っぱる / 矢印キー : 見る位置を動かす
  [ ]                               : 歪みの補正（k1）を弱める・強める
  G : 格子    0 : ズームと位置を元へ（1.00倍・中央）
  Enter : 決定して閉じる     Esc : やめる（開いたときの値に戻して閉じる）
"""
import fcntl
import json
import os
import signal
import subprocess
import sys
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

LENS = os.environ.get('OVERLAY_LENS', '/home/arduino/ecologger-video/lens.json')
PV_REQ = '/dev/shm/ecologger-preview.req'
PV_OUT = '/dev/shm/ecologger-preview.rgba'
LOCK = '/dev/shm/ecologger-preview.lock'
DASH = 'ecocapture-dash.service'
IDLE_CLOSE_S = 600

DEFAULT = {'model': 'opencv_radial_k1k2', 'f_ratio': 0.8, 'size': [1280, 720],
           'k1': -0.20, 'k2': 0.0, 'zoom': 1.0, 'shift_x': 0.0, 'shift_y': 0.0}
LIMITS = {'k1': (-0.80, 0.30), 'k2': (-0.30, 0.30), 'zoom': (1.0, 3.0), 'shift_x': (-0.40, 0.40), 'shift_y': (-0.40, 0.40)}

CSS = b"""
window, .bg { background-color: #000000; }
.info { background-color: rgba(0,0,0,0.65); color: #ffffff; font-size: 22px; padding: 10px 16px; }
.wait { color: #ffd34d; font-size: 34px; font-weight: bold; background-color: rgba(0,0,0,0.65); padding: 16px; }
.bar { background-color: rgba(0,0,0,0.65); padding: 8px; }
.bar button { font-size: 24px; padding: 8px 18px; }
.bar button.ok { background-image: none; background-color: #2e7d32; color: #ffffff; }
.bar button.cancel { background-image: none; background-color: #8e2b2b; color: #ffffff; }
"""


def systemctl(*args):
    try:
        return subprocess.run(['sudo', '-n', '/usr/bin/systemctl', *args], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def dash_active():
    try:
        return subprocess.run(['systemctl', 'is-active', '--quiet', DASH], timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def recorder_running():
    try:
        return subprocess.run(['pgrep', '-x', 'overlay_rec'], capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def read_lens():
    try:
        with open(LENS, 'rb') as fp:
            raw = fp.read()
        js = json.loads(raw)
        vals = dict(DEFAULT)
        vals.update({k: js[k] for k in DEFAULT if k in js})
        return vals, raw
    except (OSError, ValueError):
        return dict(DEFAULT), None


def write_lens(vals):
    os.makedirs(os.path.dirname(LENS), exist_ok=True)
    data = dict(vals)
    for k in ('k1', 'k2'):
        data[k] = round(data[k], 3)
    for k in ('zoom', 'shift_x', 'shift_y'):
        data[k] = round(data[k], 2)
    data['saved_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    data['saved_by'] = 'lens_preview.py'
    tmp = LENS + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
    os.replace(tmp, LENS)


def touch_request():
    try:
        with open(PV_REQ, 'a'):
            pass
        os.utime(PV_REQ, None)
    except OSError:
        pass


class Preview(Gtk.Window):
    def __init__(self, start_vals, start_raw, on_close):
        super().__init__(title='EcoLogger lens preview')
        self.vals, self.start_vals, self.start_raw, self.on_close = dict(start_vals), dict(start_vals), start_raw, on_close
        self.pixbuf, self.seq, self.last_frame = None, None, 0.0
        self.grid, self.dirty, self.drag = True, False, None
        self.last_input = time.monotonic()
        self.opened = time.monotonic()
        self.set_decorated(False)
        screen = self.get_screen()
        self.size = (screen.get_width(), screen.get_height())
        self.set_default_size(*self.size)
        self.move(0, 0)
        css = Gtk.CssProvider()
        css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(screen, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.area = Gtk.DrawingArea()
        self.area.get_style_context().add_class('bg')
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                             Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.SCROLL_MASK)
        self.area.connect('draw', self.on_draw)
        self.area.connect('scroll-event', self.on_scroll)
        self.area.connect('button-press-event', self.on_press)
        self.area.connect('button-release-event', self.on_release)
        self.area.connect('motion-notify-event', self.on_motion)

        self.info = Gtk.Label(xalign=0)
        self.info.get_style_context().add_class('info')
        self.info.set_halign(Gtk.Align.START)
        self.info.set_valign(Gtk.Align.START)
        self.wait = Gtk.Label(label='')
        self.wait.get_style_context().add_class('wait')
        self.wait.set_halign(Gtk.Align.CENTER)
        self.wait.set_valign(Gtk.Align.CENTER)

        bar = Gtk.Box(spacing=8)
        bar.get_style_context().add_class('bar')
        bar.set_halign(Gtk.Align.CENTER)
        bar.set_valign(Gtk.Align.END)
        for text, fn, cls in (('ズーム −', lambda: self.nudge('zoom', -0.05), None),
                              ('ズーム ＋', lambda: self.nudge('zoom', +0.05), None),
                              ('←', lambda: self.nudge('shift_x', -0.01), None),
                              ('→', lambda: self.nudge('shift_x', +0.01), None),
                              ('↑', lambda: self.nudge('shift_y', -0.01), None),
                              ('↓', lambda: self.nudge('shift_y', +0.01), None),
                              ('格子', self.toggle_grid, None),
                              ('決定して閉じる', self.finish, 'ok'),
                              ('やめる', self.cancel, 'cancel')):
            b = Gtk.Button(label=text)
            b.set_can_focus(False)
            if cls:
                b.get_style_context().add_class(cls)
            b.connect('clicked', lambda _b, f=fn: (self.touched(), f()))
            bar.pack_start(b, False, False, 0)

        overlay = Gtk.Overlay()
        overlay.add(self.area)
        overlay.add_overlay(self.info)
        overlay.add_overlay(self.wait)
        overlay.add_overlay(bar)
        self.add(overlay)
        self.connect('realize', self.on_realize)
        self.connect('map-event', self.on_map)
        self.connect('key-press-event', self.on_key)
        self.connect('destroy', lambda _w: Gtk.main_quit())
        self.update_info()
        GLib.timeout_add(150, self.poll_frame)
        GLib.timeout_add(1000, self.tick)

    # ---- window
    def on_realize(self, _w):
        self.get_window().set_override_redirect(True)  # no window manager on :2: cover the whole screen

    def on_map(self, *_a):
        win = self.get_window()
        win.raise_()
        try:  # override-redirect windows get no focus on their own: take the keyboard
            Gdk.Display.get_default().get_default_seat().grab(win, Gdk.SeatCapabilities.KEYBOARD, False, None, None, None)
        except Exception:
            pass
        return False

    def tick(self):
        touch_request()
        win = self.get_window()
        if win:
            win.raise_()
        if time.monotonic() - self.last_input > IDLE_CLOSE_S:
            print('10分さわらなかったので、今の値のまま閉じます')
            self.finish()
            return False
        return True

    # ---- frames from the recorder
    def poll_frame(self):
        try:
            with open(PV_OUT, 'rb') as fp:
                head = fp.read(16)
                if len(head) == 16 and head[:4] == b'EPV1':
                    w, h, seq = (int.from_bytes(head[i:i + 4], 'little') for i in (4, 8, 12))
                    if seq != self.seq:
                        data = fp.read(w * h * 4)
                        if len(data) == w * h * 4:
                            self.pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
                                GLib.Bytes.new(data), GdkPixbuf.Colorspace.RGB, True, 8, w, h, w * 4)
                            self.seq, self.last_frame = seq, time.monotonic()
                            self.area.queue_draw()
        except OSError:
            pass
        stale = time.monotonic() - max(self.last_frame, self.opened)
        if stale > 4:
            if recorder_running():
                msg = 'カメラの絵を待っています…\n（録画プログラムが古い版だと、ここに絵が出ません）'
            else:
                msg = '録画が止まっています（カメラがつながっていない？）\nつながると約5秒で絵が出ます'
            self.wait.set_text(msg)
            self.wait.show()
        else:
            self.wait.hide()
        return True

    def on_draw(self, _area, cr):
        w, h = self.area.get_allocated_width(), self.area.get_allocated_height()
        cr.set_source_rgb(0, 0, 0)
        cr.paint()
        if self.pixbuf is None:
            return False
        pw, ph = self.pixbuf.get_width(), self.pixbuf.get_height()
        s = min(w / pw, h / ph)
        ox, oy = (w - pw * s) / 2, (h - ph * s) / 2
        cr.save()
        cr.translate(ox, oy)
        cr.scale(s, s)
        Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
        cr.paint()
        cr.restore()
        if self.grid:
            cr.set_source_rgba(1, 0.9, 0, 0.55)
            cr.set_line_width(1.5)
            for i in range(1, 8):
                x = ox + pw * s * i / 8
                cr.move_to(x, oy)
                cr.line_to(x, oy + ph * s)
            for j in range(1, 6):
                y = oy + ph * s * j / 6
                cr.move_to(ox, y)
                cr.line_to(ox + pw * s, y)
            cr.stroke()
        self.view = (ox, oy, pw * s, ph * s)
        return False

    # ---- changing the values
    def touched(self):
        self.last_input = time.monotonic()

    def set_val(self, key, value):
        lo, hi = LIMITS[key]
        self.vals[key] = min(hi, max(lo, value))
        self.update_info()
        if not self.dirty:
            self.dirty = True
            GLib.timeout_add(250, self.flush)

    def nudge(self, key, step):
        self.set_val(key, self.vals[key] + step)

    def flush(self):
        self.dirty = False
        try:
            write_lens(self.vals)
        except OSError as e:
            print(f'lens.json を書けませんでした: {e}', file=sys.stderr)
        return False

    def toggle_grid(self):
        self.grid = not self.grid
        self.area.queue_draw()

    def update_info(self):
        v = self.vals
        self.info.set_text(
            f"画角の調整（録画にすぐ反映。約1秒遅れて映ります）\n"
            f"ズーム {v['zoom']:.2f}倍   位置 左右 {v['shift_x']:+.2f}・上下 {v['shift_y']:+.2f}   歪みの補正 k1 {v['k1']:+.3f}\n"
            f"ホイール／＋−：ズーム　左ボタンで引っぱる／矢印：位置　[ ]：歪み　G：格子　0：元へ\n"
            f"Enter：決定して閉じる　Esc：やめる（開いたときの値へ戻す）")

    def on_scroll(self, _w, ev):
        self.touched()
        if ev.direction == Gdk.ScrollDirection.UP:
            self.nudge('zoom', +0.05)
        elif ev.direction == Gdk.ScrollDirection.DOWN:
            self.nudge('zoom', -0.05)
        return True

    def on_press(self, _w, ev):
        self.touched()
        if ev.button == 1:
            self.drag = (ev.x, ev.y, self.vals['shift_x'], self.vals['shift_y'])
        return True

    def on_release(self, _w, _ev):
        self.drag = None
        return True

    def on_motion(self, _w, ev):
        if not self.drag or not getattr(self, 'view', None):
            return False
        self.touched()
        x0, y0, sx0, sy0 = self.drag
        _, _, vw, vh = self.view
        z = self.vals['zoom']
        # the picture follows the pointer: dragging right shows what is further left
        self.set_val('shift_x', sx0 - (ev.x - x0) / vw / z)
        self.set_val('shift_y', sy0 - (ev.y - y0) / vh / z)
        return True

    def on_key(self, _w, ev):
        self.touched()
        k = Gdk.keyval_name(ev.keyval) or ''
        steps = {'plus': ('zoom', .05), 'KP_Add': ('zoom', .05), 'equal': ('zoom', .05),
                 'minus': ('zoom', -.05), 'KP_Subtract': ('zoom', -.05),
                 'Left': ('shift_x', -.01), 'Right': ('shift_x', .01), 'Up': ('shift_y', -.01), 'Down': ('shift_y', .01),
                 'bracketleft': ('k1', .01), 'bracketright': ('k1', -.01)}
        if k in steps:
            self.nudge(*steps[k])
        elif k in ('g', 'G'):
            self.toggle_grid()
        elif k == '0':
            self.set_val('zoom', 1.0)
            self.set_val('shift_x', 0.0)
            self.set_val('shift_y', 0.0)
        elif k in ('Return', 'KP_Enter'):
            self.finish()
        elif k == 'Escape':
            self.cancel()
        return True

    # ---- closing
    def finish(self):
        self.flush()
        print('決定: ' + json.dumps({k: self.vals[k] for k in LIMITS}, ensure_ascii=False))
        self.on_close()
        Gtk.main_quit()

    def cancel(self):
        try:
            if self.start_raw is None:
                if os.path.exists(LENS):
                    os.remove(LENS)
            else:
                tmp = LENS + '.tmp'
                with open(tmp, 'wb') as fp:
                    fp.write(self.start_raw)
                os.replace(tmp, LENS)
        except OSError as e:
            print(f'元の値に戻せませんでした: {e}', file=sys.stderr)
        print('やめました（開いたときの値に戻しました）')
        self.on_close()
        Gtk.main_quit()


def main():
    lock = open(LOCK, 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print('プレビューはもう開いています')
        return 1
    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ':2'
    touch_request()
    had_dash = dash_active()
    if had_dash:
        if not systemctl('stop', DASH):
            print('★DASHを止められませんでした（DASHの上に重ねて出します）', file=sys.stderr)
    closed = []

    def restore():
        if closed:
            return
        closed.append(1)
        try:
            os.remove(PV_REQ)
        except OSError:
            pass
        if had_dash:
            print('DASHに戻します' if systemctl('start', DASH) else '★DASHを起動し直せませんでした（sudo systemctl start ecocapture-dash）')

    def on_signal(*_a):
        restore()
        GLib.idle_add(Gtk.main_quit)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, on_signal)

    try:
        vals, raw = read_lens()
        print('開いたときの値: ' + json.dumps({k: vals[k] for k in LIMITS}, ensure_ascii=False)
              + ('' if raw is not None else '（lens.json が無かったので仮の値で補正を始める。やめると補正なしに戻す）'))
        if raw is None:  # what is on the screen must be what the numbers say
            write_lens(vals)
        win = Preview(vals, raw, restore)
        win.show_all()
        Gtk.main()
    finally:
        restore()
    return 0


if __name__ == '__main__':
    sys.exit(main())
