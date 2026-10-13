import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import mcu_diagnostics as diagnostics


class DiagnosticTests(unittest.TestCase):
    def test_capture_is_bounded_and_only_uses_read_only_commands(self):
        calls=[]
        def run(args,**kwargs):
            calls.append(args)
            text=b'other unrelated event\nserial engine reports 0 RX bytes in!\n' if args[0]=='dmesg' else b'active\n'
            return subprocess.CompletedProcess(args,0,text,b'')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'msm_geni_serial').write_bytes(b'X'*(diagnostics.MAX_BYTES+100))
            with patch.object(diagnostics,'TTY_DRIVERS',root),patch.object(diagnostics,'POWER_PATHS',[]), \
                 patch.object(diagnostics.subprocess,'run',side_effect=run):
                result=diagnostics.collect()
        self.assertEqual(len(result['tty_drivers']['msm_geni_serial']),diagnostics.MAX_BYTES)
        self.assertIn('0 RX bytes',result['kernel_uart_events']['stdout'])
        self.assertNotIn('unrelated',result['kernel_uart_events']['stdout'])
        self.assertEqual([c[0] for c in calls],['dmesg','systemctl','journalctl'])
        self.assertEqual(calls[1][1],'show')

    def test_missing_proc_and_command_timeouts_are_reported_without_crashing(self):
        with patch.object(diagnostics,'TTY_DRIVERS',Path('/does-not-exist')), \
             patch.object(diagnostics,'POWER_PATHS',[]), \
             patch.object(diagnostics.subprocess,'run',side_effect=subprocess.TimeoutExpired('read',3)):
            result=diagnostics.collect()
        self.assertIn('error',result['tty_drivers'])
        self.assertIn('error',result['router'])


if __name__=='__main__': unittest.main()
