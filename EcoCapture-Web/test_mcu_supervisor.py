"""No device access: check recovery decisions and delegation to the locked helper."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('mcu_supervisor',Path(__file__).with_name('mcu-supervisor.py'))
supervisor=importlib.util.module_from_spec(spec); spec.loader.exec_module(supervisor)


class EndMonitor(Exception): pass


class SupervisorTests(unittest.TestCase):
    def states(self,values,attempt=True,flashing=False,limit=30,cooldown=120,backoff=600):
        clock=[0]; calls=[]
        def sleep(seconds):
            if seconds==0: return
            clock[0]+=seconds
            if clock[0]>=len(values)*5: raise EndMonitor()
        def recover():
            calls.append(clock[0])
            if isinstance(attempt,Exception): raise attempt
            return attempt
        with patch.object(supervisor,'STARTUP_GRACE_S',0), patch.object(supervisor,'DOWN_LIMIT_S',limit), \
             patch.object(supervisor,'COOLDOWN_S',cooldown), patch.object(supervisor,'BACKOFF_S',backoff), \
             patch.object(supervisor.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(supervisor.time,'sleep',side_effect=sleep), \
             patch.object(supervisor,'link_state',side_effect=values), \
             patch.object(supervisor,'flashing',return_value=flashing), \
             patch.object(supervisor,'recover',side_effect=recover), patch.object(supervisor,'log'):
            with self.assertRaises(EndMonitor): supervisor.main()
        return calls

    def test_continuous_disconnect_needs_full_threshold_even_at_monotonic_zero(self):
        self.assertEqual(self.states(['down']*8),[30])

    def test_reconnect_or_unknown_status_clears_disconnect_timer(self):
        self.assertEqual(self.states(['down']*5+['up']+['down']*5),[])
        self.assertEqual(self.states(['down']*5+[None]+['down']*5),[])

    def test_flashing_and_unreachable_web_do_not_reset(self):
        self.assertEqual(self.states(['down']*10,flashing=True),[])
        self.assertEqual(self.states([None]*10),[])

    def test_busy_lock_is_deferred_without_counting_failed_recoveries(self):
        self.assertEqual(self.states(['down']*15,attempt=False),[30,65])

    def test_attempts_back_off_after_three_unconfirmed_recoveries(self):
        self.assertEqual(self.states(['down']*13,limit=5,cooldown=10,backoff=30),[5,15,25,55])

    def test_recovery_error_does_not_crash_monitor(self):
        self.assertEqual(self.states(['down']*8,attempt=RuntimeError('reset failed')),[30])

    def test_status_requires_boolean_connected(self):
        for data,want in (({'connected':True},'up'),({'connected':False},'down'),
                          ({},None),({'connected':'false'},None),([],None),(None,None)):
            with self.subTest(data=data), patch.object(supervisor.urllib.request,'urlopen',
                                                     return_value=io.BytesIO(json.dumps(data).encode())):
                self.assertEqual(supervisor.link_state(),want)

    def test_unreachable_status_is_unknown(self):
        with patch.object(supervisor.urllib.request,'urlopen',side_effect=OSError('offline')):
            self.assertIsNone(supervisor.link_state())

    def test_recovery_delegates_to_common_helper_and_propagates_errors(self):
        for code,want in ((0,True),(75,False),(1,None)):
            result=subprocess.CompletedProcess([],code,'','failure')
            with self.subTest(code=code),patch.object(supervisor.subprocess,'run',return_value=result) as run:
                if want is None:
                    with self.assertRaises(RuntimeError): supervisor.recover()
                else: self.assertEqual(supervisor.recover(),want)
                self.assertEqual(run.call_args.args[0],['sh','/home/arduino/EcoCapture-Web/flash-mcu.sh','--recover'])
                self.assertEqual(run.call_args.kwargs['timeout'],180)


if __name__=='__main__': unittest.main()
