"""Versioned V2 configuration; channel names deliberately match EcoCapture where possible."""
import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Signal(BaseModel):
    channel: Literal[1,2] = 1
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
    unit: str = Field(default="", max_length=16)
    can_id: int = Field(ge=0, le=0x1FFFFFFF)
    extended: bool = False
    byte_offset: int = Field(ge=0, le=7)
    data_type: Literal["uint8", "int8", "uint16", "int16", "uint32", "int32"] = "uint16"
    endian: Literal["little", "big"] = "little"
    scale: float = 1
    offset: float = 0
    bit_mask: int | None = Field(default=None, ge=1, le=255)

    @model_validator(mode="after")
    def valid_layout(self):
        if not self.extended and self.can_id > 0x7FF:
            raise ValueError("標準CAN IDは0x7FFまでです")
        width = int(self.data_type.removeprefix("uint").removeprefix("int")) // 8
        if self.byte_offset + width > 8:
            raise ValueError("信号が8バイトを超えています")
        if self.bit_mask is not None and self.data_type != 'uint8':
            raise ValueError('ビットマスクはuint8のみ対応します')
        return self

class Configuration(BaseModel):
    model_config = ConfigDict(extra="forbid", serialize_by_alias=True, validate_by_name=True)
    schema_version: Literal[1] = Field(default=1, alias="schema")
    device_name: str = Field(default="EcoLogger V2", min_length=1, max_length=48)
    profile: Literal["no-can", "demo-vehicle", "ncec-2005-mt"] = "no-can"
    can_bitrate: Literal[125000, 250000, 500000, 1000000] = 500000
    auto_record: bool = True
    signals: list[Signal] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def unique_names(self):
        if len({s.name for s in self.signals}) != len(self.signals):
            raise ValueError("信号名が重複しています")
        return self

CHANNELS = {
    "Speed": ("車速", "km/h"), "GPSSpeed": ("GNSS速度", "km/h"), "RPM": ("回転数", "rpm"),
    "Throttle": ("スロットル", "%"), "BatteryVolt": ("バッテリー", "V"),
    "Lat": ("緯度", "°"), "Lon": ("経度", "°"), "Altitude": ("標高", "m"),
    "Yaw": ("方位", "°"), "GPSFix": ("測位状態", ""), "GPSSats": ("衛星数", ""),
    "GNSSHz": ("生成周期", "Hz"), "AccelX": ("加速度 X", "m/s²"), "AccelY": ("加速度 Y", "m/s²"),
    "AccelZ": ("加速度 Z", "m/s²"), "GyroX": ("角速度 X", "°/s"), "GyroY": ("角速度 Y", "°/s"),
    "GyroZ": ("角速度 Z", "°/s"), "Roll": ("ロール", "°"), "Pitch": ("ピッチ", "°"),
    "LongAccel": ("前後加速度", "g"), "LatAccel": ("左右加速度", "g"), "VertAccel": ("上下加速度", "g"),
    "Distance": ("累積距離", "km"), "WaterTemp": ("水温", "°C")
}

def validate_sample(value):
    if not isinstance(value, dict) or value.get("source") not in ("stm32-dummy", "logger-v2-hardware") or value.get("demo") is not (value.get("source")=="stm32-dummy") or value.get("schema") != 1:
        raise ValueError("Unexpected MCU telemetry source/schema")
    for key in ("seq", "mcu_ms"):
        if type(value.get(key)) is not int or not 0 <= value[key] <= 0xFFFFFFFF:
            raise ValueError("Invalid MCU sequence/timestamp")
    values = value.get("values", {})
    if set(values) != set(CHANNELS) or any(x is not None and (type(x) not in (int, float) or not math.isfinite(x)) for x in values.values()):
        raise ValueError("Invalid MCU channels")
    return value
