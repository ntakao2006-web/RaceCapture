import unittest
from bridge_patch import patch_update_loop, ORIGINAL, PREVIOUS, PATCHED
STARTUP='client = new RPCClient(*transport);\nserver = new RPCServer(*transport);\nupd_tid = k_thread_create(...);\n'


class BridgePatchTests(unittest.TestCase):
    def test_original_and_previous_patch_become_sleeping_unconditional_update(self):
        for body in (ORIGINAL,PREVIOUS):
            with self.subTest(body=body):
                outside=STARTUP+'// another block\n'+ORIGINAL+'\n'
                source=outside+'inline void updateEntryPoint(void *, void *, void *){\n    while (true) {\n'+body+'\n    }\n}\n'
                fixed=patch_update_loop(source)
                self.assertTrue(fixed.startswith(outside))
                self.assertIn(PATCHED,fixed)
                self.assertEqual(patch_update_loop(fixed),fixed)

    def test_unknown_updater_is_rejected(self):
        with self.assertRaises(ValueError):
            patch_update_loop(STARTUP+'inline void updateEntryPoint(){\n    do_something_else();\n}\n')

    def test_changed_rpc_initialization_order_is_rejected(self):
        source=STARTUP.replace('client = new RPCClient(*transport);\n','')
        source+='client = new RPCClient(*transport);\n'
        source+='inline void updateEntryPoint(){\n'+ORIGINAL+'\n}\n'
        with self.assertRaises(ValueError): patch_update_loop(source)


if __name__=='__main__': unittest.main()
