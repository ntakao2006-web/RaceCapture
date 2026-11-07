"""Versioned V2 configuration; channel names deliberately match EcoCapture where possible."""
import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

# An NTC reading outside this range is not a temperature but a lost bias: the Defi
# unit is powered with the ignition while the logger and PIC v8 stay on, so after the
# engine is switched off its thermistor voltage reads about 0 V (1 ADC count = 2513 °C,
# heard as an oil temperature alarm on 2026-11-06), and a short circuit does the same.
# No oil or coolant gets near 200 °C (Defi's oil gauge ends at 150 °C), so a real
# overheat still passes and keeps its warning.
NTC_VALID_C = (-40.0, 200.0)

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
    # 'ntc': the scaled value is the ADC ratio V/Vref (0..1) of an NTC thermistor
    # below a pull-up to the same reference (sensor hub analog frame bytes 2-3).
    # 'defi_volt': one ADC input of the PIC v8 frame (CAN2 0x580, version 1); the
    # whole frame is validated (hardware.defivolt_packet), scale 5/4095 gives volts.
    conversion: Literal["linear", "ntc", "sensorhub_oiltemp", "defi_volt"] = "linear"
    pullup_ohm: float | None = Field(default=None, gt=0, le=1e7)
    ntc_points: list[tuple[float, float]] = Field(default_factory=list, max_length=16)  # (°C, Ω)

    @model_validator(mode="after")
    def valid_layout(self):
        if not self.extended and self.can_id > 0x7FF:
            raise ValueError("標準CAN IDは0x7FFまでです")
        width = int(self.data_type.removeprefix("uint").removeprefix("int")) // 8
        if self.byte_offset + width > 8:
            raise ValueError("信号が8バイトを超えています")
        if self.bit_mask is not None and self.data_type != 'uint8':
            raise ValueError('ビットマスクはuint8のみ対応します')
        if self.conversion == 'sensorhub_oiltemp':
            if (self.channel != 2 or self.extended or self.byte_offset != 0
                    or self.data_type != 'int16' or self.endian != 'little'
                    or self.scale != .01 or self.offset != 0 or self.bit_mask is not None):
                raise ValueError('PIC油温はCAN2・標準ID・先頭int16 LE・倍率0.01で設定してください')
        if self.conversion == 'defi_volt':
            if (self.channel != 2 or self.extended or self.byte_offset not in (0, 2, 4)
                    or self.data_type != 'uint16' or self.endian != 'little'
                    or not self.scale > 0 or self.bit_mask is not None):
                raise ValueError('Defi電圧入力はCAN2・標準ID・0/2/4バイト目のuint16 LE・正の倍率で設定してください')
        if self.conversion == "ntc":
            points = sorted(self.ntc_points)
            if self.pullup_ohm is None or len(points) < 2:
                raise ValueError("サーミスタ換算にはプルアップ抵抗値と2点以上の校正値が必要です")
            if any(r <= 0 or t <= -273 for t, r in points) or any(b[0] <= a[0] or b[1] >= a[1] for a, b in zip(points, points[1:])):
                raise ValueError("校正値は温度が上がるほど抵抗が下がる組で入力してください")
            if self.bit_mask is not None:
                raise ValueError("サーミスタ換算とビットマスクは併用できません")
        return self

    def ntc_celsius(self, ratio):
        """Ratio -> °C, interpolating ln(R) linearly in 1/T between calibration points (beta model)."""
        if not 0 < ratio < 1:
            return None  # open / shorted sensor
        resistance = self.pullup_ohm * ratio / (1 - ratio)
        points = sorted(self.ntc_points)
        pairs = list(zip(points, points[1:]))
        lo, hi = next(((a, b) for a, b in pairs if resistance >= b[1]), pairs[-1])
        x = lambda t: 1 / (t + 273.15)
        f = (math.log(resistance) - math.log(lo[1])) / (math.log(hi[1]) - math.log(lo[1]))
        celsius = 1 / (x(lo[0]) + f * (x(hi[0]) - x(lo[0]))) - 273.15
        return celsius if NTC_VALID_C[0] <= celsius <= NTC_VALID_C[1] else None  # sensor unpowered / shorted / open

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
        names = {s.name for s in self.signals}
        for sig in self.signals:
            if sig.conversion == 'sensorhub_oiltemp' and names & {sig.name+'State', sig.name+'Open'}:
                raise ValueError('油温の自動状態チャンネル名と重複しています')
            if sig.conversion == 'defi_volt' and sig.name+'State' in names:
                raise ValueError('電圧入力の自動状態チャンネル名と重複しています')
        return self

# Conversions whose decoder also reports <name>State (hardware.STATE_LABELS).
STATE_CONVERSIONS = ('sensorhub_oiltemp', 'defi_volt')

def signal_columns(config):
    """One log column per CAN signal; PIC packets add <name>State (oil temperature's Open is the same as State 1)."""
    names = []
    for sig in config.signals:
        names.append(sig.name)
        if sig.conversion in STATE_CONVERSIONS:
            names.append(sig.name + 'State')
    return names

def log_value(value):
    """Drop float noise such as 6016*.01 -> 60.160000000000004 when writing a log."""
    return round(value, 9) if isinstance(value, float) else value

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

# Computed on Linux by lap.py, outside the MCU sample. Names and the minute
# unit follow RaceCapture so Podium can show them.
LAP_CHANNELS = {
    "LapCount": ("完了周回数", ""), "CurrentLap": ("走行中の周", ""),
    "LapTime": ("前回ラップ", "Min"), "BestLap": ("ベストラップ", "Min"),
    "ElapsedTime": ("現在ラップ経過", "Min"),
    "RaceTime": ("スタートからの経過", "Min"), "LapsLeft": ("残り周回数", ""),
    "TimeLimit": ("規定時間", "Sec"), "Margin": ("余裕", "Sec"),
    # Sectors (lap.py, 2026-11-07): the one being driven, and the one just completed with its time
    "Sector": ("走行中のセクター", ""), "LastSector": ("前のセクター", ""), "SectorTime": ("前のセクターのタイム", "Min")
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
