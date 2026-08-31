"""MAX-M10M-00B high-clock provisioning, ONLY through gnss_maintenance_main.cpp.

Default mode is read-only. --apply requires an exact confirmation and creates an
exclusive, fsynced attempt journal BEFORE transmitting either OTP frame. Never
retry an uncertain OTP attempt. Restore the normal logger image after servicing.
Source: UBX-22038241 R03, section 2.1.7, table 8 (pages 14-15).
"""
import argparse
import hashlib
import json
import os
import struct
import time
from pathlib import Path
import serial

OTP = [bytes.fromhex(x) for x in (
    'B5 62 06 41 10 00 03 00 04 1F 54 5E 79 BF 28 EF 12 05 FD FF FF FF 8F 0D',
    'B5 62 06 41 1C 00 04 01 A4 10 BD 34 F9 12 28 EF 12 05 05 00 A4 40 00 B0 71 0B 0A 00 A4 40 00 D8 B8 05 DE AE',
)]
VERIFY = bytes.fromhex('B5 62 06 8B 14 00 00 04 00 00 01 00 A4 40 03 00 A4 40 05 00 A4 40 0A 00 A4 40 4C 15')
EXPECTED = bytes.fromhex('B5 62 06 8B 24 00 01 04 00 00 01 00 A4 40 00 B0 71 0B 03 00 A4 40 00 B0 71 0B 05 00 A4 40 00 B0 71 0B 0A 00 A4 40 00 D8 B8 05 76 81')


def ubx(cls, ident, payload=b''):
    body = bytes((cls, ident)) + struct.pack('<H', len(payload)) + payload
    a = b = 0
    for c in body:
        a = (a + c) & 255
        b = (b + a) & 255
    return b'\xb5\x62' + body + bytes((a, b))


def valid(frame):
    return len(frame) >= 8 and frame == ubx(frame[2], frame[3], frame[6:-2]) and struct.unpack_from('<H', frame, 4)[0] + 8 == len(frame)


class NakError(RuntimeError):
    def __init__(self, frame):
        self.frame = frame
        super().__init__('GNSS NAK: ' + frame.hex())


class Bridge:
    def __init__(self, port):
        self.s = serial.Serial(None, baudrate=115200, timeout=.1, write_timeout=2)
        self.s.dtr = self.s.rts = False
        self.s.port = port
        self.s.open()
        self.wire = bytearray()
        self.frames = []
        self.command('?', 'GNSS_SERVICE_V1 NO_AUTOMATIC_WRITES')

    def line(self):
        text = self.s.readline().decode('ascii', errors='replace').strip()
        if text.startswith('R') and len(text) > 1:
            try:
                self.wire.extend(bytes.fromhex(text[1:]))
            except ValueError:
                return text
            while len(self.wire) >= 8:
                p = self.wire.find(b'\xb5\x62')
                if p < 0:
                    self.wire[:] = self.wire[-1:]
                    break
                if p:
                    del self.wire[:p]
                if len(self.wire) < 8:
                    break
                n = struct.unpack_from('<H', self.wire, 4)[0] + 8
                if n > 4096:
                    del self.wire[0]
                    continue
                if len(self.wire) < n:
                    break
                f = bytes(self.wire[:n])
                if valid(f):
                    self.frames.append(f)
                    del self.wire[:n]
                else:
                    del self.wire[0]
            self.frames = self.frames[-256:]
        return text

    def command(self, text, expected, timeout=3):
        self.s.write(text.encode('ascii') + b'\n')
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            line = self.line()
            if line == expected:
                return
            if line.startswith('ERR '):
                raise RuntimeError(line)
        raise TimeoutError('Bridge command acknowledgement missing; do not retry OTP')

    def baud(self, rate):
        self.command('B' + str(rate), 'OK B')
        self.frames.clear()
        self.wire.clear()

    def send(self, frame):
        assert valid(frame)
        self.command('T' + frame.hex(), 'OK T')

    def wait(self, cls, ident, timeout=3):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for i, f in enumerate(self.frames):
                if f[2:4] == bytes((cls, ident)):
                    return self.frames.pop(i)
                if f[2:4] == b'\x05\x00':
                    self.frames.pop(i)
                    raise NakError(f)
            self.line()
        raise TimeoutError(f'No UBX {cls:02x}/{ident:02x}; do not retry OTP')

    def poll(self, frame):
        self.frames.clear()
        self.send(frame)
        return self.wait(frame[2], frame[3])

    def discover(self):
        for rate in (115200, 9600, 38400, 57600):
            self.baud(rate)
            try:
                return rate, self.poll(ubx(0x0a, 4))
            except TimeoutError:
                pass
        raise RuntimeError('No GNSS MON-VER response')


def version_strings(frame):
    p = frame[6:-2]
    assert len(p) >= 40 and (len(p) - 40) % 30 == 0
    return [p[:30].split(b'\0')[0].decode('ascii'), p[30:40].split(b'\0')[0].decode('ascii')] + [p[i:i+30].split(b'\0')[0].decode('ascii') for i in range(40, len(p), 30)]


def journal(file, event):
    file.write(json.dumps({'time': time.time(), **event}) + '\n')
    file.flush()
    os.fsync(file.fileno())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', default='COM8')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--confirm', default='')
    p.add_argument('--journal', type=Path)
    args = p.parse_args()
    for frame in [*OTP, VERIFY, EXPECTED]:
        assert valid(frame), 'Documented UBX frame/checksum transcription error'
    if args.apply and (args.confirm != 'MAX-M10M-00B_25HZ_PERMANENT' or args.journal is None):
        p.error('--apply requires exact --confirm and --journal')
    bridge = Bridge(args.port)
    report = {'mode': 'apply' if args.apply else 'read-only', 'otp_transmissions': 0}
    try:
        baud, ver = bridge.discover()
        report.update(baud=baud, version_hex=ver.hex(), version=version_strings(ver))
        try:
            clock = bridge.poll(VERIFY)
            report['before_clock_hex'] = clock.hex()
            report['already_high'] = clock == EXPECTED
        except NakError as e:
            # These factory-layer keys need not exist before the documented
            # configuration is installed. Only accept the specific VALGET NAK.
            if e.frame != ubx(5, 0, b'\x06\x8b'):
                raise
            report['before_clock_nak_hex'] = e.frame.hex()
            report['already_high'] = False
        uid = bridge.poll(ubx(0x27, 3))
        assert len(uid) == 18 and uid[6] == 2, 'Unexpected unique chip ID format'
        report['unique_id_hex'] = uid.hex()
        report['rom_patch_info_hex'] = bridge.poll(ubx(0x0a, 0x27)).hex()
        report['sequence_sha256'] = hashlib.sha256(b''.join(OTP)).hexdigest()
        print(json.dumps(report, indent=2), flush=True)
        if not args.apply or report['already_high']:
            return
        assert any(x == 'FWVER=SPG 5.10' for x in report['version']), 'Unsupported GNSS firmware'
        assert 'MOD=MAX-M10M' in report['version'], 'Unsupported GNSS module'
        assert 'PROTVER=34.10' in report['version'], 'Unsupported GNSS protocol'
        # Create before the first irreversible byte, and refuse an existing journal.
        with args.journal.open('x', encoding='utf-8') as log:
            journal(log, {'event': 'attempt_started', 'preflight': report})
            for i, frame in enumerate(OTP):
                journal(log, {'event': 'about_to_send', 'index': i, 'hex': frame.hex()})
                bridge.frames.clear()
                bridge.send(frame)  # Intentionally exactly once: no retry.
                report['otp_transmissions'] += 1
                ack = bridge.wait(5, 1)
                assert ack == ubx(5, 1, b'\x06\x41'), 'Unexpected ACK'
                journal(log, {'event': 'acknowledged', 'index': i, 'hex': ack.hex()})
            # Hardware reset through CFG-RST, with no BBR clear (hot start mask).
            bridge.send(ubx(6, 4, b'\x00\x00\x00\x00'))
            time.sleep(1)
            baud, ver = bridge.discover()
            report['after_baud'] = baud
            report['after_version'] = version_strings(ver)
            after = bridge.poll(VERIFY)
            report['after_clock_hex'] = after.hex()
            report['verified_high_after_hardware_reset'] = after == EXPECTED
            journal(log, {'event': 'after_reset', 'result': report})
            assert after == EXPECTED, 'Clock verification mismatch. Do not repeat OTP.'
            print(json.dumps(report, indent=2), flush=True)
    finally:
        bridge.s.close()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
