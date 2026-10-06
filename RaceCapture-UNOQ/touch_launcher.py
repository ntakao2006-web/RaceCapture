#!/usr/bin/python3
"""Touch-friendly physical-display switcher for RaceCapture and EcoCapture."""
import ctypes
import atexit
import os
import re
import signal
import subprocess
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkX11, GLib, Gtk
from display_load_control import resume_all, set_paused

DISPLAY = os.environ.get("DISPLAY", ":2")
BAR_HEIGHT = 64

x11 = ctypes.CDLL("libX11.so.6")
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
x11.XDisplayWidth.argtypes = [ctypes.c_void_p, ctypes.c_int]
x11.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
x11.XMoveResizeWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
x11.XMapRaised.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
x11.XRaiseWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
x11.XFlush.argtypes = [ctypes.c_void_p]
xdisplay = x11.XOpenDisplay(DISPLAY.encode())
if not xdisplay:
    raise SystemExit("cannot open X display")
screen = x11.XDefaultScreen(xdisplay)


def dimensions():
    return x11.XDisplayWidth(xdisplay, screen), x11.XDisplayHeight(xdisplay, screen)


def window_tree():
    return subprocess.run(
        ["/usr/bin/xwininfo", "-display", DISPLAY, "-root", "-tree"],
        text=True, capture_output=True, check=False,
    ).stdout


def find_window(kind):
    for line in window_tree().splitlines():
        lower = line.lower()
        if kind == "racecapture" and '("race_capture" "race_capture")' not in lower:
            continue
        if kind == "ecocapture" and '("ecocapture-native" "ecocapture-native")' not in lower:
            continue
        match = re.match(r"\s*(0x[0-9a-f]+)", lower)
        if match:
            return int(match.group(1), 16)
    return None


def place(kind, raise_window=True):
    window = find_window(kind)
    if not window:
        return False
    width, height = dimensions()
    x11.XMoveResizeWindow(xdisplay, window, 0, BAR_HEIGHT, width, height - BAR_HEIGHT)
    if raise_window:
        x11.XMapRaised(xdisplay, window)
    x11.XFlush(xdisplay)
    return True


class Launcher(Gtk.Window):
    def __init__(self):
        super().__init__(title="Logger display switcher")
        self.panel_xid = None
        self.race_running = False
        self.race_pending = False
        self.state_polling = False
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_skip_taskbar_hint(True)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        width, _ = dimensions()
        self.set_default_size(width, BAR_HEIGHT)
        self.move(0, 0)

        css = Gtk.CssProvider()
        css.load_from_data(b"""
            window { background: #07151d; }
            button { font-size: 22px; font-weight: bold; color: #edf7fb; background: #163544; border: 1px solid #2da9d2; border-radius: 8px; margin: 5px; padding: 4px 24px; }
            button.active { background: #087ca7; }
            label { color: #b8d5df; font-size: 16px; padding-left: 18px; }
        """)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.race = Gtk.Button(label="RaceCapture")
        self.eco = Gtk.Button(label="EcoCapture")
        self.power = Gtk.Button(label="状態確認中…")
        self.power.set_sensitive(False)
        self.power.connect("clicked", self.toggle_racecapture)
        self.status = Gtk.Label(label="RaceCapture")
        self.race.set_size_request(240, BAR_HEIGHT)
        self.eco.set_size_request(240, BAR_HEIGHT)
        self.race.connect("clicked", self.show_racecapture)
        self.eco.connect("clicked", self.show_ecocapture)
        box.pack_start(self.race, False, False, 0)
        box.pack_start(self.eco, False, False, 0)
        box.pack_start(self.power, False, False, 0)
        box.pack_start(self.status, True, True, 0)
        self.add(box)
        self.connect("realize", self.on_realize)
        self.connect("destroy", self.on_destroy)
        self.set_active(self.race)
        GLib.timeout_add(500, self.keep_above)
        GLib.timeout_add(2000, self.poll_racecapture)
        self.poll_racecapture()

    def poll_racecapture(self):
        if self.state_polling or self.race_pending:
            return True
        self.state_polling = True
        def worker():
            try:
                state = subprocess.run(["/usr/bin/systemctl", "is-active", "racecapture-app.service"],
                                       capture_output=True, text=True, timeout=5).stdout.strip()
            except Exception:
                state = "unknown"
            GLib.idle_add(self.apply_race_state, state)
        threading.Thread(target=worker, daemon=True).start()
        return True

    def apply_race_state(self, state):
        self.state_polling = False
        if self.race_pending:
            return False
        self.race_running = state in ("active", "activating", "reloading")
        self.power.set_label("RaceCapture 停止" if self.race_running else "RaceCapture 起動")
        self.power.set_sensitive(state in ("active", "inactive", "failed"))
        self.race.set_sensitive(state == "active")
        context = self.power.get_style_context()
        if self.race_running:
            context.add_class("active")
        else:
            context.remove_class("active")
        return False

    def toggle_racecapture(self, _button):
        if self.race_pending:
            return
        action = "stop" if self.race_running else "start"
        self.race_pending = True
        self.power.set_sensitive(False)
        self.race.set_sensitive(False)
        self.power.set_label("停止中…" if action == "stop" else "起動中…")
        self.show_ecocapture(None)
        if action == "stop":
            # A stopped process cannot handle systemd's SIGTERM promptly.
            set_paused("racecapture-app", False)
        def worker():
            try:
                result = subprocess.run(["/usr/bin/sudo", "-n", "/usr/bin/systemctl", action,
                                         "racecapture-app.service"], capture_output=True, timeout=60)
                ok = result.returncode == 0
            except Exception:
                ok = False
            GLib.idle_add(self.finish_race_toggle, action, ok)
        threading.Thread(target=worker, daemon=True).start()

    def finish_race_toggle(self, action, ok):
        self.race_pending = False
        if not ok:
            self.status.set_text("切替失敗：状態を確認してください")
        elif action == "start":
            self.show_racecapture(None)
        else:
            self.status.set_text("EcoCapture · RaceCapture停止中")
        self.poll_racecapture()
        return False

    def on_realize(self, _widget):
        gdk_window = self.get_window()
        gdk_window.set_override_redirect(True)
        self.panel_xid = GdkX11.X11Window.get_xid(gdk_window)
        place("racecapture")
        set_paused("racecapture-app", False)
        set_paused("ecocapture-native", True)

    def on_destroy(self, _widget):
        resume_all()
        Gtk.main_quit()

    def set_active(self, button):
        self.race.get_style_context().remove_class("active")
        self.eco.get_style_context().remove_class("active")
        button.get_style_context().add_class("active")

    def keep_above(self):
        if self.panel_xid:
            x11.XRaiseWindow(xdisplay, self.panel_xid)
            x11.XFlush(xdisplay)
        return True

    def show_racecapture(self, _button):
        set_paused("racecapture-app", False)
        place("racecapture")
        set_paused("ecocapture-native", True)
        self.status.set_text("RaceCapture")
        self.set_active(self.race)
        self.keep_above()

    def show_ecocapture(self, _button):
        set_paused("ecocapture-native", False)
        self.status.set_text("EcoCapture")
        self.set_active(self.eco)
        self.eco_attempts = 0
        GLib.timeout_add(500, self.place_ecocapture)

    def place_ecocapture(self):
        self.eco_attempts += 1
        found = place("ecocapture")
        if found:
            set_paused("racecapture-app", True)
        self.keep_above()
        return not found and self.eco_attempts < 40


launcher = Launcher()
atexit.register(resume_all)
def shutdown(_signum, _frame):
    resume_all()
    GLib.idle_add(Gtk.main_quit)
signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)
launcher.show_all()
Gtk.main()
