import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import incident_monitor as monitor


class IncidentMonitorTests(unittest.TestCase):
    def test_classifies_first_clean_unclean_and_same_boot(self):
        self.assertEqual(monitor.classify_previous(None, "new"), "none")
        self.assertEqual(
            monitor.classify_previous({"boot_id": "old", "clean_shutdown": True}, "new"),
            "clean_reboot",
        )
        self.assertEqual(
            monitor.classify_previous({"boot_id": "old", "clean_shutdown": False}, "new"),
            "unclean_reboot",
        )
        self.assertEqual(
            monitor.classify_previous({"boot_id": "new", "clean_shutdown": False}, "new"),
            "same_boot_restart",
        )

    def test_atomic_json_replaces_complete_document(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "state" / "current.json"
            monitor.atomic_write_json(target, {"boot_id": "one"})
            monitor.atomic_write_json(target, {"boot_id": "two", "clean_shutdown": False})
            self.assertEqual(
                json.loads(target.read_text()),
                {"boot_id": "two", "clean_shutdown": False},
            )
            self.assertEqual(list(target.parent.glob("*.tmp")), [])

    def test_api_failure_is_bounded_and_nonfatal(self):
        with patch.object(monitor.urllib.request, "urlopen", side_effect=TimeoutError("late")):
            status = monitor.read_api_status()
        self.assertFalse(status["available"])
        self.assertIn("TimeoutError", status["error"])


if __name__ == "__main__":
    unittest.main()
