import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import display_load_control as load
import hdmi_display


XRANDR = """Screen 0: minimum 320 x 200, current 1920 x 1080
DP-1 connected primary 1920x1080+0+0
   1920x1080     60.00*+
   1280x800      59.91
   1280x720      60.00
HDMI-1 disconnected
"""


class DisplayMitigationTests(unittest.TestCase):
    def test_prefers_bounded_hdmi_mode(self):
        modes = hdmi_display.parse_modes(XRANDR)
        self.assertEqual(modes, ["1920x1080", "1280x800", "1280x720"])
        self.assertEqual(hdmi_display.choose_mode(modes), "1280x800")

    def test_falls_back_to_largest_bounded_mode(self):
        self.assertEqual(hdmi_display.choose_mode(["1920x1080", "1024x600", "800x480"]), "1024x600")

    def test_signals_only_display_service_cgroup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            group = root / "ecocapture-native.service"
            group.mkdir()
            (group / "cgroup.procs").write_text("123\n456\n")
            with patch.object(load, "CGROUP_ROOT", root), patch.object(load.os, "kill") as kill:
                self.assertEqual(load.set_paused("ecocapture-native", True), 2)
            kill.assert_any_call(123, signal.SIGSTOP)
            kill.assert_any_call(456, signal.SIGSTOP)
            with self.assertRaises(ValueError):
                load.set_paused("ecocapture-web-start", True)


if __name__ == "__main__":
    unittest.main()
