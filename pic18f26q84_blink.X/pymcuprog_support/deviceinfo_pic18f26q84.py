"""pymcuprog memory description for PIC18F26Q84.

The addresses and sizes are taken from Microchip PIC18F-Q_DFP 1.30.487.
PIC18F26Q84 is cloned from PIC18F57Q84 and differs here in device identity
and program-flash size (64 KiB instead of 128 KiB).
"""

from pymcuprog.deviceinfo.devices.pic18f57q84 import DEVICE_INFO as BASE_DEVICE_INFO


DEVICE_INFO = dict(BASE_DEVICE_INFO)
DEVICE_INFO.update(
    {
        "name": "pic18f26q84",
        "device_id": 0xA300,
        "flash_size_bytes": 64 * 1024,
    }
)
