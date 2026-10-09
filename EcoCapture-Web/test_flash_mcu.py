"""Exercise flashing failure boundaries with fake commands, without hardware (Linux/WSL)."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

STUB = '''#!/usr/bin/python3
import json, os, socket, subprocess, sys
from pathlib import Path
name=Path(sys.argv[0]).name; args=sys.argv[1:]
with open(os.environ['EVENTS'],'a') as f: f.write(json.dumps([name,*args])+'\\n')
fail=os.environ.get('FAIL','')
if name=='timeout':
    raise SystemExit(subprocess.call(args[1:]))
if name=='sleep': raise SystemExit(0)
if name=='docker':
    if args[0]=='run':
        offset=args.index('--')
        raise SystemExit(subprocess.call(args[offset+1:]))
    raise SystemExit(1 if fail=='web-stop' and args[0]=='stop' else 0)
if name=='systemctl':
    action=args[0]
    if fail=='router-stop' and action=='stop': raise SystemExit(124)
    if fail=='router-start' and action=='start': raise SystemExit(1)
    if action=='show':
        print(('active' if fail=='router-still-running' else 'inactive')
              if 'ActiveState' in args else ('42' if fail=='router-still-running' else '0'))
    if action=='start':
        s=socket.socket(socket.AF_UNIX); s.bind(os.environ['SOCKET']); s.close()
    if action=='is-active' and fail=='router-not-ready': raise SystemExit(1)
    raise SystemExit(0)
if name=='arduino-flash.sh' and fail=='flash': raise SystemExit(7)
if name=='openocd' and fail=='reset': raise SystemExit(8)
raise SystemExit(0)
'''


class FlashOrderTests(unittest.TestCase):
    def run_flash(self, fail='', size=1024):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); commands=root/'bin'; commands.mkdir()
            for name in ('timeout','sleep','docker','systemctl','install','arduino-flash.sh','openocd'):
                p=commands/name; p.write_text(STUB); p.chmod(0o755)
            installer=root/'install-router.sh'
            installer.write_text((Path(__file__).parent/'install-router.sh').read_text()
                                 .replace('/etc/systemd/system/arduino-router.service.d',str(root/'service')))
            script=root/'flash-mcu.sh'
            script.write_text((Path(__file__).parent/'flash-mcu.sh').read_text()
                              .replace('/opt/openocd/bin/arduino-flash.sh',str(commands/'arduino-flash.sh'))
                              .replace('/opt/openocd/bin/openocd',str(commands/'openocd'))
                              .replace('/home/arduino/EcoCapture-Web/install-router.sh',str(installer))
                              .replace('/var/run/arduino-router.sock',str(root/'router.sock')))
            image=root/'image with spaces.bin'; image.write_bytes(b'X'*size)
            env={**os.environ,'PATH':str(commands)+':'+os.environ['PATH'],
                 'EVENTS':str(root/'events'),'SOCKET':str(root/'router.sock'),'FAIL':fail}
            result=subprocess.run(['sh',str(script),str(image)],env=env,capture_output=True,text=True,timeout=10)
            events=[json.loads(line) for line in (root/'events').read_text().splitlines()] if (root/'events').exists() else []
            return result,events

    def test_success_order_and_image_path(self):
        result,events=self.run_flash()
        self.assertEqual(result.returncode,0,result.stderr)
        steps=[]
        for e in events:
            if e[0]=='docker' and e[1] in ('stop','start'): steps.append('web-'+e[1])
            elif e[0]=='systemctl' and e[1] in ('stop','start','restart'): steps.append('router-'+e[1])
            elif e[0] in ('arduino-flash.sh','openocd'): steps.append(e[0])
        self.assertEqual(steps,['web-stop','router-stop','arduino-flash.sh','router-start','openocd','web-start'])
        self.assertTrue(next(e for e in events if e[0]=='arduino-flash.sh')[1].endswith('image with spaces.bin'))

    def test_oversized_image_is_rejected_before_stop(self):
        result,events=self.run_flash(size=65537)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(events,[])

    def test_web_stop_and_router_shutdown_failures_never_flash(self):
        for fail in ('web-stop','router-stop','router-still-running'):
            with self.subTest(fail=fail):
                result,events=self.run_flash(fail)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(any(e[0] in ('arduino-flash.sh','openocd') for e in events))
                self.assertFalse(any(e[:2]==['docker','start'] for e in events))

    def test_flash_failure_preserves_error_and_never_starts_router(self):
        result,events=self.run_flash('flash')
        self.assertEqual(result.returncode,7)
        self.assertFalse(any(e[:2]==['systemctl','start'] for e in events))
        self.assertFalse(any(e[:2]==['docker','start'] for e in events))

    def test_router_start_and_readiness_failures_never_reset(self):
        for fail in ('router-start','router-not-ready'):
            with self.subTest(fail=fail):
                result,events=self.run_flash(fail)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(any(e[0]=='openocd' for e in events))
                self.assertFalse(any(e[:2]==['docker','start'] for e in events))

    def test_reset_failure_never_restarts_web(self):
        result,events=self.run_flash('reset')
        self.assertEqual(result.returncode,8)
        self.assertFalse(any(e[:2]==['docker','start'] for e in events))


if __name__=='__main__':
    unittest.main()
