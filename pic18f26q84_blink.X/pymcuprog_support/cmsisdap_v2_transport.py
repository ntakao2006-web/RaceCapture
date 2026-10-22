"""CMSIS-DAP v2 bulk transport adapter for Microchip pymcuprog.

pymcuprog 3.19 uses a HID-only transport factory.  Current MPLAB Snap
CMSIS-DAP firmware uses the standard CMSIS-DAP v2 bulk endpoints instead.
This adapter preserves pymcuprog's transport API while replacing only the
USB framing layer.
"""

import usb.core
import usb.util
import logging

from pyedbglib.hidtransport.hidtransportbase import HidTool, HidTransportBase


SNAP_VENDOR_ID = 0x04D8
SNAP_CMSIS_DAP_V2_PRODUCT_ID = 0x90B1
CMSIS_DAP_INTERFACE = 0
CMSIS_DAP_OUT_ENDPOINT = 0x01
CMSIS_DAP_IN_ENDPOINT = 0x82
CMSIS_DAP_PACKET_SIZE = 512
USB_TIMEOUT_MS = 4000


class CyHidApiTransport(HidTransportBase):
    """Expose CMSIS-DAP v2 bulk transfers through pymcuprog's HID API."""

    def __init__(self):
        self.usb_device = None
        self.interface_claimed = False
        self.transfer_count = 0
        self.trace_logger = logging.getLogger("snap_bulk_trace")
        super().__init__()

    def detect_devices(self):
        for usb_device in usb.core.find(
            find_all=True,
            idVendor=SNAP_VENDOR_ID,
            idProduct=SNAP_CMSIS_DAP_V2_PRODUCT_ID,
        ):
            serial_number = usb.util.get_string(usb_device, usb_device.iSerialNumber) or ""
            manufacturer = usb.util.get_string(usb_device, usb_device.iManufacturer) or "Microchip"
            detected = HidTool(
                SNAP_VENDOR_ID,
                SNAP_CMSIS_DAP_V2_PRODUCT_ID,
                serial_number,
                "MPLAB Snap",
                manufacturer,
            )
            detected.set_packet_size(CMSIS_DAP_PACKET_SIZE)
            self.devices.append(detected)
        return len(self.devices)

    def connect(self, serial_number=None, product=None):
        if self.connected:
            return True

        matching = self.get_matching_tools(serial_number, product)
        if len(matching) != 1:
            self.logger.error("Expected one Snap CMSIS-DAP v2 device, found %d", len(matching))
            return False

        self.device = matching[0]
        self.hid_connect(self.device)
        self.device.set_packet_size(CMSIS_DAP_PACKET_SIZE)
        self.connected = True
        self.hid_info()
        return True

    def hid_connect(self, device):
        self.usb_device = usb.core.find(
            idVendor=device.vendor_id,
            idProduct=device.product_id,
        )
        if self.usb_device is None:
            raise IOError("Snap CMSIS-DAP v2 USB device disappeared")

        self.usb_device.set_configuration()
        usb.util.claim_interface(self.usb_device, CMSIS_DAP_INTERFACE)
        self.interface_claimed = True
        # A cancelled programming session can leave one completed response in
        # the bulk IN queue.  HID reopen implicitly discards that state, while
        # WinUSB/libusb does not, so explicitly start from a clean boundary.
        self._drain_in_endpoint()
        return device

    def _drain_in_endpoint(self):
        while True:
            try:
                stale = self.usb_device.read(
                    CMSIS_DAP_IN_ENDPOINT,
                    CMSIS_DAP_PACKET_SIZE,
                    timeout=20,
                )
                self.trace_logger.debug(
                    "Discarded stale USB IN len=%d head=%s",
                    len(stale),
                    bytes(stale[:16]).hex(" "),
                )
            except usb.core.USBTimeoutError:
                return

    def hid_disconnect(self):
        if self.usb_device is None:
            return
        if self.interface_claimed:
            usb.util.release_interface(self.usb_device, CMSIS_DAP_INTERFACE)
            self.interface_claimed = False
        usb.util.dispose_resources(self.usb_device)
        self.usb_device = None

    def hid_info(self):
        self.logger.info("Manufacturer: %s", self.device.manufacturer_string)
        self.logger.info("Product: Snap CMSIS-DAP v2")
        self.logger.info("Serial Number: %s", self.device.serial_number)

    @staticmethod
    def _pad_packet(data):
        packet = bytearray(data)
        if len(packet) > CMSIS_DAP_PACKET_SIZE:
            raise ValueError("CMSIS-DAP packet exceeds 512 bytes")
        packet.extend(b"\x00" * (CMSIS_DAP_PACKET_SIZE - len(packet)))
        return packet

    def hid_write(self, data_send):
        self.transfer_count += 1
        self.trace_logger.debug(
            "USB OUT #%d len=%d head=%s",
            self.transfer_count,
            len(data_send),
            bytes(data_send[:16]).hex(" "),
        )
        packet = self._pad_packet(data_send)
        return self.usb_device.write(
            CMSIS_DAP_OUT_ENDPOINT,
            packet,
            timeout=USB_TIMEOUT_MS,
        )

    def hid_read(self):
        response = bytearray(
            self.usb_device.read(
                CMSIS_DAP_IN_ENDPOINT,
                CMSIS_DAP_PACKET_SIZE,
                timeout=USB_TIMEOUT_MS,
            )
        )
        self.trace_logger.debug(
            "USB IN  #%d len=%d head=%s",
            self.transfer_count,
            len(response),
            bytes(response[:16]).hex(" "),
        )
        return response

    def hid_transfer(self, data_send):
        self.hid_write(data_send)
        return self.hid_read()


def bulk_transport():
    """Factory compatible with pyedbglib.hid_transport()."""

    # Microchip's PIC device-support scripts identify an already-initialized
    # standalone transport by this upstream class name.
    return CyHidApiTransport()
