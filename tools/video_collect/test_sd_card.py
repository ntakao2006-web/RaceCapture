"""sd_card.py の試験。一時フォルダを「カード」にする（Windowsのドライブの情報は差し替える）。"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import sd_card  # noqa: E402

FAT32 = {'label': 'ECOLOGGER', 'fs': 'FAT32', 'total': 16 << 30, 'free': 8 << 30, 'cluster': 32768, 'sector': 512, 'removable': True}


def block(n):
    """1本分の中身（先頭にその本の番号が入る。実物も最初のブロックにSTM32の時刻が入る）"""
    return (b'ELB2' + n.to_bytes(4, 'little')) * (1 << 13) + bytes(1 << 16)


class SdCardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.card, self.out = base / 'card', base / 'drive_logs'
        self.card.mkdir()
        self.out.mkdir()
        for n in (1, 2, 3):
            (self.card / f'EL{n:06}.BIN').write_bytes(block(n))
        (self.card / 'notes.txt').write_text('x')
        self.drive = str(self.card)
        self.vol = patch.object(sd_card, 'volume', side_effect=lambda d: {**FAT32, 'drive': d})
        self.vol.start()

    def tearDown(self):
        self.vol.stop()
        self.tmp.cleanup()

    def job(self):
        import video_collect
        return video_collect.Job('test')

    def test_find_check_collect_and_empty(self):
        cards = sd_card.find_cards([self.drive])
        self.assertEqual([(c['files'], c['first'], c['last'], c['problem']) for c in cards], [(3, 'EL000001.BIN', 'EL000003.BIN', '')])
        self.assertEqual(sd_card.check(self.drive, self.out, self.job())['uncollected'], 3)
        self.assertEqual(sd_card.collect(self.drive, self.out, self.job()), 3)
        copies = sorted(p.name for p in self.out.glob('*/run01_*/v2_sd/*.BIN'))
        self.assertEqual(copies, ['EL000001.BIN', 'EL000002.BIN', 'EL000003.BIN'])
        self.assertEqual(sd_card.check(self.drive, self.out, self.job())['uncollected'], 0)
        (self.card / 'EL000004.BIN').write_bytes(block(4))  # まだ回収していない
        self.assertEqual(sd_card.empty(self.drive, self.out, self.job()), 1)
        self.assertEqual(sorted(p.name for p in self.card.iterdir()), ['EL000004.BIN', 'notes.txt'])

    def test_a_renumbered_card_is_not_mistaken_for_the_old_one(self):
        sd_card.collect(self.drive, self.out, self.job())
        sd_card.empty(self.drive, self.out, self.job())
        (self.card / 'EL000001.BIN').write_bytes(block(101))  # 空にしたあと、STM32は EL000001 から付け直す（大きさも同じ）
        r = sd_card.check(self.drive, self.out, self.job())
        self.assertEqual((r['collected'], r['uncollected']), (0, 1))
        self.assertEqual(sd_card.collect(self.drive, self.out, self.job()), 1)
        self.assertEqual(sd_card.empty(self.drive, self.out, self.job()), 0)

    def test_a_copy_that_changed_on_the_pc_keeps_the_card_file(self):
        sd_card.collect(self.drive, self.out, self.job())
        copy = next(self.out.glob('*/run01_*/v2_sd/EL000002.BIN'))
        data = bytearray(copy.read_bytes())
        data[-1] ^= 1  # 先頭は同じで、後ろが違う
        copy.write_bytes(bytes(data))
        self.assertEqual(sd_card.empty(self.drive, self.out, self.job()), 1)
        self.assertEqual(sorted(p.name for p in self.card.glob('*.BIN')), ['EL000002.BIN'])

    def test_unusable_card_is_reported(self):
        self.vol.stop()
        with patch.object(sd_card, 'volume', side_effect=lambda d: {**FAT32, 'drive': d, 'fs': 'exFAT'}):
            self.assertIn('exFAT', sd_card.find_cards([self.drive])[0]['problem'])
        self.vol.start()

    def test_format_only_a_removable_card_with_nothing_uncollected(self):
        letter = 'Q:'
        with patch.object(sd_card, 'el_files', side_effect=lambda d: sorted(self.card.glob('EL*.BIN'))):
            with self.assertRaisesRegex(OSError, '回収していないファイルが 3 本'):
                sd_card.format_card(letter, self.out, self.job(), run=lambda *a, **k: None)
            sd_card.collect(self.drive, self.out, self.job())
            self.vol.stop()
            with patch.object(sd_card, 'volume', side_effect=lambda d: {**FAT32, 'drive': d, 'removable': False}):
                with self.assertRaisesRegex(OSError, '取り外せる'):
                    sd_card.format_card(letter, self.out, self.job(), run=lambda *a, **k: None)
            self.vol.start()
            calls = []

            def fake_run(argv, **kw):  # 管理者のPowerShellの代わり：スクリプトの結果のファイルに OK を書く
                calls.append(argv)
                script = re.search(r'-File "([^"]+)"', argv[-1]).group(1)
                result = re.search(r"\$result = '([^']+)'", Path(script).read_text(encoding='utf-8-sig')).group(1)
                self.assertIn("-DriveLetter $letter", Path(script).read_text(encoding='utf-8-sig'))
                self.assertIn("$letter = 'Q'", Path(script).read_text(encoding='utf-8-sig'))
                Path(result).write_text('OK', encoding='utf-8')
            self.assertEqual(sd_card.format_card(letter, self.out, self.job(), run=fake_run)['fs'], 'FAT32')
            self.assertIn('-Verb RunAs', calls[0][-1])
        with self.assertRaisesRegex(OSError, 'できない'):
            sd_card.format_card(Path.home().drive or 'C:', self.out, self.job(), run=lambda *a, **k: None)


if __name__ == '__main__':
    unittest.main(verbosity=2)
