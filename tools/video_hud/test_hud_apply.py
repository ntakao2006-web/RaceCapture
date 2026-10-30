"""hud_apply.py の試験。本体の代わりに、録画（overlay_rec の hud_check）が hud.ini を読み直して hud_status.txt を書く動きを真似る"""
import shlex
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hud_apply  # noqa: E402
import hud_layout  # noqa: E402

GOOD = (HERE / 'hud.ini').read_bytes()


class FakeUnoQ:
    """hud_apply が組み立てたシェルのコマンドを読んで、ファイルと録画の読み直しを真似る"""

    def __init__(self, ready=True, active=True, c_accepts=True, recorder_alive=True):
        self.ready, self.active, self.c_accepts, self.alive = ready, active, c_accepts, recorder_alive
        self.files, self.ino, self.commands = {}, 100, []
        self.loaded = None  # (path, ino, size)
        self.bad = None
        self.status = ''

    def recorder_tick(self):
        """録画が約1秒ごとにすること（overlay_rec.c の hud_check）"""
        if not (self.active and self.alive):
            return
        path = hud_apply.REMOTE_INI if hud_apply.REMOTE_INI in self.files else hud_apply.DEFAULT_ON_DEVICE
        ino, data = self.files.get(path, (1, b'x' * 10))
        key = (path, str(ino), str(len(data)))
        if key in (self.loaded, self.bad):
            return
        if self.c_accepts or path != hud_apply.REMOTE_INI:
            self.loaded, self.bad, error = key, None, ''
        else:
            self.bad, error = key, f'{path} 3行目: だめ（前の配置のまま）'
        loaded = self.loaded or ('', '0', '0')
        bad = self.bad or ('', '0', '0')
        self.status = (f'at=2026-10-30T20:00:00+0900\nloaded={loaded[0]}\nino={loaded[1]}\nsize={loaded[2]}\nitems=19\n'
                       f'bad={bad[0]}\nbad_ino={bad[1]}\nbad_size={bad[2]}\nerror={error}\n')

    def __call__(self, command, data=None):
        self.commands.append(command)
        if command.startswith('if [ -f'):
            return (f'READY={int(self.ready)}\nACTIVE={"active" if self.active else "inactive"}\n' + self.status)
        if 'cat >' in command:
            self.ino += 1
            self.files[hud_apply.REMOTE_INI] = (self.ino, data)
            return f'{self.ino} {len(data)}\n'
        if command.startswith('rm -f'):
            self.files.pop(shlex.split(command)[-1], None)
            return ''
        raise AssertionError(command)


def sleeper(fake):
    def sleep(_):
        fake.recorder_tick()
    return sleep


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.log = []

    def test_applied(self):
        fake = FakeUnoQ()
        fake.recorder_tick()  # 録画は元の配置で動いている
        self.assertEqual(hud_apply.apply(fake, GOOD, self.log.append, sleeper(fake)), 0)
        self.assertIn('反映されました', self.log[-1])
        self.assertEqual(fake.files[hud_apply.REMOTE_INI][1], GOOD)
        self.assertTrue(any('mv -f' in c for c in fake.commands))  # 別の名前で書いてから入れ替える

    def test_same_content_twice_is_still_confirmed(self):
        fake = FakeUnoQ()
        fake.recorder_tick()
        hud_apply.apply(fake, GOOD, self.log.append, sleeper(fake))
        self.assertEqual(hud_apply.apply(fake, GOOD, self.log.append, sleeper(fake)), 0)

    def test_old_recorder_gets_nothing(self):
        fake = FakeUnoQ(ready=False)
        self.assertEqual(hud_apply.apply(fake, GOOD, self.log.append, sleeper(fake)), 2)
        self.assertEqual(fake.files, {})

    def test_recorder_stopped(self):
        fake = FakeUnoQ(active=False)
        self.assertEqual(hud_apply.apply(fake, GOOD, self.log.append, sleeper(fake)), 0)
        self.assertIn('次に録画が始まったとき', self.log[-1])

    def test_device_rejects(self):
        fake = FakeUnoQ(c_accepts=False)
        fake.recorder_tick()
        self.assertEqual(hud_apply.apply(fake, GOOD, self.log.append, sleeper(fake)), 3)
        self.assertIn('前の配置のまま', self.log[-1])

    def test_old_error_does_not_count_for_new_file(self):
        """前に送って断られたファイルの誤りが残っていても、新しいファイルの結果を待つ"""
        fake = FakeUnoQ(c_accepts=False)
        fake.recorder_tick()
        hud_apply.apply(fake, b'bad', self.log.append, sleeper(fake))
        fake.c_accepts = True
        self.assertEqual(hud_apply.apply(fake, GOOD, self.log.append, sleeper(fake)), 0)

    def test_not_confirmed(self):
        fake = FakeUnoQ(recorder_alive=False)
        self.assertEqual(hud_apply.apply(fake, GOOD, self.log.append, lambda _: None), 4)

    def test_back_to_default(self):
        fake = FakeUnoQ()
        fake.recorder_tick()
        hud_apply.apply(fake, GOOD, self.log.append, sleeper(fake))
        self.assertEqual(hud_apply.back_to_default(fake, self.log.append, sleeper(fake)), 0)
        self.assertNotIn(hud_apply.REMOTE_INI, fake.files)
        self.assertEqual(fake.loaded[0], hud_apply.DEFAULT_ON_DEVICE)

    def test_main_refuses_bad_file_without_connecting(self):
        bad = HERE / 'testdata' / 'bad' / '06_bad_color.ini'
        called = []
        orig = hud_apply.runner
        hud_apply.runner = lambda *a: called.append(a)
        try:
            self.assertEqual(hud_apply.main([str(bad)]), 1)
        finally:
            hud_apply.runner = orig
        self.assertEqual(called, [])

    def test_main_refuses_heavy_layout_without_force(self):
        heavy = HERE / 'testdata' / '_heavy_tmp.ini'
        heavy.write_text(GOOD.decode('utf-8') + ''.join(
            f'[full{i}]\ntype = box\nrect = 0 0 1920 1080\ncolor = 0 0 0 0.06\n\n' for i in range(3)), encoding='utf-8')
        called = []
        orig = hud_apply.runner
        hud_apply.runner = lambda *a: called.append(a) or FakeUnoQ(ready=False)
        try:
            self.assertEqual(hud_apply.main([str(heavy)]), 1)
            self.assertEqual(called, [])
            self.assertEqual(hud_apply.main([str(heavy), '--force']), 2)  # 送ろうとする（偽の本体は古い版なので2）
            self.assertEqual(len(called), 1)
        finally:
            hud_apply.runner = orig
            heavy.unlink()

    def test_hud_ini_is_valid(self):
        hud_layout.parse(GOOD.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
