"""Device choice of voice_agent.py (runs on the UNO Q host: python3 test_voice_agent.py)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import voice_agent as va

A, B, C = '40:DE:17:B6:15:45', '11:22:33:44:55:66', 'AA:BB:CC:DD:EE:FF'


def headset(dev_id=58, profile='a2dp-sink', with_source=False, mac=A):
    dev = {'id': dev_id, 'type': 'PipeWire:Interface:Device',
           'info': {'props': {'device.api': 'bluez5', 'device.description': 'Sudio N2 Pro', 'api.bluez5.address': mac,
                              'api.bluez5.path': '/org/bluez/hci0/dev_' + mac.replace(':', '_')},
                    'params': {'EnumProfile': [{'index': 0, 'name': 'off'}, {'index': 131073, 'name': 'a2dp-sink'},
                                               {'index': 196865, 'name': 'headset-head-unit'}],
                               'Profile': [{'index': 0, 'name': profile}]}}}
    nodes = [{'id': 62, 'type': 'PipeWire:Interface:Node',
              'info': {'props': {'device.id': dev_id, 'media.class': 'Audio/Sink', 'node.name': 'bluez_output.x.1'}}}]
    if with_source:
        nodes.append({'id': 43, 'type': 'PipeWire:Interface:Node',
                      'info': {'props': {'device.id': dev_id, 'media.class': 'Audio/Source/Internal', 'node.name': 'bluez_input_internal.x.0'}}})
    return [dev, *nodes]


class RouteTests(unittest.TestCase):
    def test_built_in_radio_gives_ears_only_and_keeps_the_usb_microphone(self):
        with patch.object(va, 'usb_adapter', return_value=False), patch.object(va, 'usb_card', return_value='Audio'):
            route, change = va.bluetooth_route(headset())
        self.assertIsNone(change)
        self.assertEqual(route['kind'], 'bluetooth-a2dp')
        self.assertEqual(route['speaker'], ('pw', 'bluez_output.x.1'))
        self.assertEqual(route['mic'], ('alsa', 'Audio'))
        self.assertEqual(route['address'], A)

    def test_usb_adapter_switches_to_the_headset_profile_and_uses_its_microphone(self):
        with patch.object(va, 'usb_adapter', return_value=True), patch.object(va, 'usb_card', return_value=None):
            route, change = va.bluetooth_route(headset())
            self.assertEqual((route, change), (None, (58, 196865)))
            route, change = va.bluetooth_route(headset(profile='headset-head-unit', with_source=True))
        self.assertEqual(route['kind'], 'bluetooth-hfp')
        self.assertEqual(route['mic'], ('pw', 'bluez_input_internal.x.0'))

    def test_no_headset_falls_back_to_usb_card(self):
        with patch.object(va, 'pipewire_objects', return_value=[]), patch.object(va, 'usb_card', return_value='Audio'):
            self.assertEqual(va.choose_route()['kind'], 'usb')
        with patch.object(va, 'pipewire_objects', return_value=[]), patch.object(va, 'usb_card', return_value=None):
            self.assertIsNone(va.choose_route())


class UsbCardTests(unittest.TestCase):
    def make(self, root, index, name, usb=True, capture=True, playback=True):
        card = Path(root) / f'card{index}'
        card.mkdir()
        (card / 'id').write_text(name + '\n')
        if usb:
            (card / 'usbid').write_text('0572:1b08\n')
        if capture:
            (card / 'pcm0c').mkdir()
        if playback:
            (card / 'pcm0p').mkdir()

    def test_any_usb_device_is_found_whatever_its_name(self):
        with tempfile.TemporaryDirectory() as root, patch.object(va, 'ASOUND', Path(root)), patch.object(va, 'CARD', ''):
            self.make(root, 0, 'ArduinoImolaHPH', usb=False)   # the board's own codec
            self.assertIsNone(va.usb_card())
            self.make(root, 1, 'Audio')
            self.assertEqual(va.usb_card(), 'Audio')

    def test_microphone_only_device_is_used_for_the_microphone_not_the_ears(self):
        with tempfile.TemporaryDirectory() as root, patch.object(va, 'ASOUND', Path(root)), patch.object(va, 'CARD', ''):
            self.make(root, 1, 'Mic', playback=False)
            self.assertIsNone(va.usb_card())
            self.assertEqual(va.usb_card(playback=False), 'Mic')

    def test_named_card_is_preferred_when_present(self):
        with tempfile.TemporaryDirectory() as root, patch.object(va, 'ASOUND', Path(root)):
            self.make(root, 1, 'Audio')
            self.make(root, 2, 'Pro')
            with patch.object(va, 'CARD', 'Pro'):
                self.assertEqual(va.usb_card(), 'Pro')
            with patch.object(va, 'CARD', 'Gone'):
                self.assertEqual(va.usb_card(), 'Audio')


class ReconnectTests(unittest.TestCase):
    def test_last_used_headset_is_called_first(self):
        self.assertEqual(va.reconnect_order([A, B, C], [C, A]), [C, A, B])
        self.assertEqual(va.reconnect_order([A, B], ['00:00:00:00:00:00']), [A, B])

    def test_recent_list_survives_and_moves_the_latest_to_the_front(self):
        with tempfile.TemporaryDirectory() as root, patch.object(va, 'RECENT_FILE', Path(root) / 'recent.json'):
            va.remember_headset(A)
            va.remember_headset(B)
            va.remember_headset(A)
            self.assertEqual(va.recent_headsets(), [A, B])
            (Path(root) / 'recent.json').write_text('not json')
            self.assertEqual(va.recent_headsets(), [])


if __name__ == '__main__':
    unittest.main()
