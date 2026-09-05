"""Bounded RCP diagnostics; opening a port never toggles DTR/RTS intentionally."""
import argparse
import json
import time
import os
from pathlib import Path
import serial
from serial.tools import list_ports


class Client:
    def __init__(self, port):
        self.serial = serial.Serial(port=None, baudrate=115200, timeout=.1, write_timeout=2)
        device = next((p for p in list_ports.comports() if p.device.upper() == port.upper()), None)
        self.serial.dtr = bool(device and device.vid == 0x303A and device.pid == 0x4001)
        self.serial.rts = False
        self.serial.port = port
        self.serial.open()
        self.buffer = bytearray()

    def close(self):
        self.serial.close()

    def query(self, command, timeout=5):
        name = next(iter(command))
        expected = {'getVer': 'ver', 'getStatus': 'status', 'getMeta': 'meta',
                    'getLoggerCfg': 'loggerCfg', 'getTrackCfg': 'trackCfg',
                    'getLevelCalibration': 'levelCalibration',
                    'getVehicleAcquisition': 'vehicleAcquisition',
                    'getObd2Cfg': 'obd2Cfg', 'getCanCfg': 'canCfg',
                    'getScriptCfg': 'scriptCfg', 'getCapabilities': 'capabilities',
                    'listLogs': 'logs', 'readLog': 'logData'}.get(name, name)
        self.serial.write(json.dumps(command, separators=(',', ':')).encode() + b'\r\n')
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.buffer.extend(self.serial.read(max(1, self.serial.in_waiting)))
            while b'\n' in self.buffer:
                line, _, self.buffer = self.buffer.partition(b'\n')
                if os.getenv('DEBUG_RCP'):
                    print('RAW', repr(line), flush=True)
                # UART console boot messages may precede a complete JSON line.
                start = line.find(b'{')
                if start < 0:
                    continue
                try:
                    result = json.loads(line[start:])
                except (ValueError, UnicodeError):
                    continue
                if expected in result:
                    return result
            if len(self.buffer) > 131072:
                self.buffer.clear()
        raise TimeoutError(f'No {expected} response from {self.serial.port}; pending={self.buffer[:200]!r}')


def decode_sample(response, metadata):
    sample = response['s']
    metadata = sample.get('meta', metadata)
    count = len(metadata)
    masks = (count + 31) // 32
    data = sample['d']
    assert masks and masks <= len(data) <= masks + count
    values, bitmap = data[:-masks], data[-masks:]
    assert len(values) == sum(int(x).bit_count() for x in bitmap)
    i = 0
    decoded = {}
    for channel, meta in enumerate(metadata):
        if int(bitmap[channel // 32]) & (1 << (channel % 32)):
            decoded[meta['nm']] = values[i]
            i += 1
    return decoded, metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM8')
    parser.add_argument('--seconds', type=float, default=0)
    parser.add_argument('--command', action='append', default=[])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    client = Client(args.port)
    results = []
    try:
        commands = [json.loads(x) for x in args.command] if args.command else [
            {'getVer': None}, {'getStatus': None}, {'s': {'meta': True}}]
        metadata = []
        for cmd in commands:
            response = client.query(cmd)
            if 's' in response:
                response['decoded'], metadata = decode_sample(response, metadata)
            results.append(response)
            print(json.dumps(response, ensure_ascii=True), flush=True)
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            response = client.query({'s': {'meta': not bool(metadata)}})
            response['decoded'], metadata = decode_sample(response, metadata)
            results.append(response)
            print(json.dumps(response['decoded'], ensure_ascii=True), flush=True)
            time.sleep(.2)
        if args.seconds:
            results.append(client.query({'getStatus': None}))
    finally:
        client.close()
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
