"""install_sectors.py を、PCの上の偽の本体（一時フォルダとGit Bash）で通す。

本体の道具（docker・curl・systemctl・python3）は偽物で、deploy.sh は「通った」か「落ちた」だけを返す。
確かめること: 知らない版は入れない・控えを作る・deploy.sh が落ちたらファイルを戻す・DASHを入れて再起動する。
  python -m unittest test_install_sectors      （Git Bash の bash が要る）
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import install_sectors as ins  # noqa: E402

BASH = shutil.which('bash')
FAKE_TOOLS = {
    # AS_ROOT is "docker run ... -- /bin/sh -c '<command>'": run the command; "docker tag" and "docker ps" say ok
    'docker': '#!/bin/sh\nif [ "$1" = run ]; then while [ "$1" != -c ]; do shift; done; shift; exec sh -c "$1"; fi\n'
              'if [ "$1" = ps ]; then echo "Up 3 seconds"; fi\nexit 0\n',
    'curl': '#!/bin/sh\necho \'{"line": {"sectors": []}, "values": {"Sector": null}}\'\n',
    'systemctl': '#!/bin/sh\ncase "$*" in *is-active*) echo active;; *restart*) echo restarted >> "$FAKE_LOG";; esac\n',
    'python3': f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" "$@"\n',
}


@unittest.skipUnless(BASH, 'Git Bash の bash が無い')
class InstallTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.bin = self.root / 'bin'; self.bin.mkdir()
        for name, body in FAKE_TOOLS.items():
            (self.bin / name).write_text(body, encoding='utf-8', newline='\n')
        self.web, self.dash = self.root / 'web', self.root / 'opt'
        self.web.mkdir(); self.dash.mkdir()
        self.log = self.root / 'log.txt'
        self.saved = (ins.WEB, ins.DASH_DIR, ins.sugo_setup.main)
        ins.WEB, ins.DASH_DIR = self.posix(self.web), self.posix(self.dash)
        self.line_calls = []
        ins.sugo_setup.main = lambda args: self.line_calls.append(args) or 0
        # the unit has the versions before this change (HEAD's), CRLF on one of them as on the real unit
        for name in ins.WEB_FILES:
            data = self.git_head(f'EcoCapture-Web/{name}')
            (self.web / name).write_bytes(data.replace(b'\n', b'\r\n') if name == 'podium.py' else data)
        for name in ins.DASH_FILES:
            (self.dash / name).write_bytes(self.git_head(f'RaceCapture-UNOQ/{name}'))
        self.deploy_ok(True)

    def tearDown(self):
        ins.WEB, ins.DASH_DIR, ins.sugo_setup.main = self.saved
        shutil.rmtree(self.root, ignore_errors=True)

    @staticmethod
    def git_head(rel):
        return subprocess.run(['git', '-C', str(ins.REPO), 'show', f'HEAD~0:{rel}'], capture_output=True, check=True).stdout

    @staticmethod
    def posix(path):
        return subprocess.run([BASH, '-c', f'cygpath -u "{path}"'], capture_output=True, text=True).stdout.strip()

    def deploy_ok(self, ok):
        (self.web / 'deploy.sh').write_text('echo tests\n' + ('exit 0\n' if ok else 'echo FAILED; exit 1\n'),
                                            encoding='utf-8', newline='\n')

    def device(self):
        test = self

        class Fake:
            def run(self, command, timeout=200):
                command = command.replace('/tmp/sectors-', test.posix(test.root) + '/stage-')
                env = {'PATH': f'{test.posix(test.bin)}:/usr/bin:/bin', 'FAKE_LOG': test.posix(test.log)}
                done = subprocess.run([BASH, '-c', command], capture_output=True, text=True, env={**__import__('os').environ, **env})
                return done.returncode, (done.stdout + done.stderr).strip()

            def put(self, local, remote):
                remote = remote.replace('/tmp/sectors-', test.posix(test.root) + '/stage-')
                win = subprocess.run([BASH, '-c', f'cygpath -w "{remote}"'], capture_output=True, text=True).stdout.strip()
                shutil.copyfile(local, win)
        return Fake()

    def test_check_accepts_the_versions_before(self):
        dev = self.device()
        self.assertTrue(ins.check_files('', dev.run, self.pairs()))

    def pairs(self):
        return ([(ins.REPO / 'EcoCapture-Web' / n, f'{ins.WEB}/{n}') for n in ins.WEB_FILES] +
                [(ins.REPO / 'RaceCapture-UNOQ' / n, f'{ins.DASH_DIR}/{n}') for n in ins.DASH_FILES])

    def test_an_unknown_version_is_not_accepted(self):
        (self.web / 'lap.py').write_bytes(b'# edited on the unit\n')
        self.assertFalse(ins.check_files('', self.device().run, self.pairs()))

    def test_install_backs_up_deploys_and_puts_the_dash_in(self):
        ins.device_pairs = self.pairs
        self.assertEqual(ins.install_device(self.device(), 'T', True, False, 'unoq'), 0)
        for name in ins.WEB_FILES:
            self.assertEqual((self.web / name).read_bytes(), (ins.REPO / 'EcoCapture-Web' / name).read_bytes())
            self.assertEqual(ins.norm_hash((self.web / '.bak-sectors-T' / name).read_bytes()),
                             ins.norm_hash(self.git_head(f'EcoCapture-Web/{name}')))
        for name in ins.DASH_FILES:
            self.assertEqual((self.dash / name).read_bytes(), (ins.REPO / 'RaceCapture-UNOQ' / name).read_bytes())
            self.assertTrue((self.dash / f'{name}.pre-sectors-T').exists())
        self.assertEqual(self.log.read_text().split(), ['restarted'])
        self.assertEqual(self.line_calls, [['--apply', '--host', 'unoq']])
        self.assertTrue(ins.check_files('', self.device().run, self.pairs()))  # now the new versions

    def test_a_failed_deploy_puts_the_files_back(self):
        self.deploy_ok(False)
        before = {n: (self.web / n).read_bytes() for n in ins.WEB_FILES}
        with self.assertRaises(SystemExit):
            ins.install_device(self.device(), 'T', True, False, 'unoq')
        self.assertEqual({n: (self.web / n).read_bytes() for n in ins.WEB_FILES}, before)
        self.assertEqual(self.line_calls, [])
        self.assertFalse(self.log.exists())  # the dash was not touched


if __name__ == '__main__':
    unittest.main()
