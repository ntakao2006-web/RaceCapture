import tempfile
import unittest
from pathlib import Path
from compare_sources import snapshot, differences


class SourceComparisonTests(unittest.TestCase):
    def test_crlf_is_ignored_but_source_changes_and_missing_files_are_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / 'repo', Path(folder) / 'board'
            a.mkdir(); b.mkdir()
            (a / 'logger_impl.h').write_bytes(b'Bridge.begin(921600);\n')
            (b / 'logger_impl.h').write_bytes(b'Bridge.begin(921600);\r\n')
            self.assertEqual(differences(snapshot(a), snapshot(b)), [])
            (b / 'logger_impl.h').write_bytes(b'Bridge.begin(460800);\n')
            (a / 'sd_logger.h').write_bytes(b'log\n')
            (b / 'lte_uart.h').write_bytes(b'uart\n')
            self.assertEqual({row['file']: row['status'] for row in differences(snapshot(a), snapshot(b))},
                             {'logger_impl.h': 'different', 'sd_logger.h': 'missing_snapshot', 'lte_uart.h': 'missing_local'})


if __name__ == '__main__':
    unittest.main()
