"""Kivy module that shortens RaceCapture Dashboard slide transitions."""
from kivy.uix.screenmanager import SlideTransition
from kivy.logger import Logger

_original_init = SlideTransition.__init__
_installed = False


def _fast_init(self, *args, **kwargs):
    kwargs.setdefault("duration", 0.10)
    _original_init(self, *args, **kwargs)


def start(_window, _context):
    global _installed
    if not _installed:
        SlideTransition.__init__ = _fast_init
        _installed = True
        Logger.info("FastNav: Dashboard slide duration set to 0.10 seconds")


def stop(_window, _context):
    global _installed
    if _installed:
        SlideTransition.__init__ = _original_init
        _installed = False
