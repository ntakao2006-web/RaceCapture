"""PIC18F26Q84 programming model derived from Microchip's PIC18F57Q84 model.

PIC18F-Q_DFP 1.30.487 declares PIC18F26Q84 as cloned from PIC18F57Q84.
The programming model is therefore identical; only the displayed device name
and silicon device ID differ.
"""

from pic18f57q84pds import DeviceDefinition as Pic18f57q84DeviceDefinition


class DeviceDefinition(Pic18f57q84DeviceDefinition):
    """PIC18F26Q84 device-specific identity."""

    DISPLAY_NAME = "PIC18F26Q84"
    DEVICE_ID = 0xA300

