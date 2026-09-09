"""Provision the board for NCEC raw-CAN logging. Never burns GNSS OTP, never formats SD.

Enables the hardcoded NCEC profile (0x201 RPM/Speed, 0x240 WaterTemp/Load/Throttle/IntakeTemp)
and forces passive acquisition, because can.cpp decodes that profile only while OBD polling and
Toyota steering are both off. Reads the settings back after flashCfg so a silent persistence
failure cannot pass. With --seconds the tool also samples live channels, which is only meaningful
while the board is connected to a running vehicle.
"""
import argparse
import json
import time
from pathlib import Path

from rcp_client import Client, decode_sample

NCEC_CHANNELS = ('RPM', 'Speed', 'WaterTemp', 'IntakeTemp')
# Load and Throttle are decoded with an unconfirmed x100/255 scale; see
# ncec_next_session_checklist.md item B. They are reported but never judged.
ADVISORY_CHANNELS = ('EngineLoad', 'Throttle')


def ok(response, command):
    return int(response.get(command, {}).get('rc', -1)) == 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', default='COM8')
    p.add_argument('--seconds', type=float, default=0,
                   help='Sample live channels for this long. Only meaningful on a running vehicle.')
    p.add_argument('--output', type=Path)
    p.add_argument('--dry-run', action='store_true', help='Report current settings without writing')
    args = p.parse_args()

    report = {}
    failures = []
    client = Client(args.port)
    try:
        version = client.query({'getVer': None})['ver']
        report['version'] = version
        print(f"build   : {version.get('git_info', version)}")

        status = client.query({'getStatus': None})['status']
        report['status_before'] = status
        sd = status.get('logging', {})
        print(f"logging : status={sd.get('status')} file={sd.get('file')} rows={sd.get('rows')}")
        if not sd.get('status'):
            failures.append('SD is not logging; check the card before leaving for the vehicle')

        before = client.query({'getLoggerCfg': None})['loggerCfg']
        acquisition = client.query({'getVehicleAcquisition': None})['vehicleAcquisition']
        report['logger_cfg_before'] = before
        report['acquisition_before'] = acquisition
        print(f"before  : ncProfile={before.get('ncProfile')} "
              f"obdEnabled={acquisition.get('obdEnabled')} "
              f"toyotaSteering={acquisition.get('toyotaSteering')} "
              f"mappings={len(before.get('mappings', []))}")

        if args.dry_run:
            print('dry-run : no settings written')
        else:
            # Passive first: leaving OBD enabled would silently suppress the NCEC decode.
            response = client.query({'setVehicleAcquisition': {'obdEnabled': False,
                                                               'toyotaSteering': False}})
            if not ok(response, 'setVehicleAcquisition'):
                failures.append(f'setVehicleAcquisition rejected: {response}')

            response = client.query({'setLoggerCfg': {'ncProfile': True}})
            if not ok(response, 'setLoggerCfg'):
                failures.append(f'setLoggerCfg rejected: {response}')

            response = client.query({'flashCfg': None})
            if not ok(response, 'flashCfg'):
                failures.append(f'flashCfg rejected: {response}')

        after = client.query({'getLoggerCfg': None})['loggerCfg']
        acquisition = client.query({'getVehicleAcquisition': None})['vehicleAcquisition']
        report['logger_cfg_after'] = after
        report['acquisition_after'] = acquisition
        print(f"after   : ncProfile={after.get('ncProfile')} "
              f"obdEnabled={acquisition.get('obdEnabled')} "
              f"toyotaSteering={acquisition.get('toyotaSteering')}")
        if not args.dry_run:
            if not after.get('ncProfile'):
                failures.append('ncProfile did not persist')
            if acquisition.get('obdEnabled') or acquisition.get('toyotaSteering'):
                failures.append('Acquisition is not passive; the NCEC decode stays disabled')

        if args.seconds:
            seen = {}
            metadata = []
            end = time.monotonic() + args.seconds
            while time.monotonic() < end:
                response = client.query({'s': {'meta': not bool(metadata)}})
                decoded, metadata = decode_sample(response, metadata)
                for name, value in decoded.items():
                    seen.setdefault(name, []).append(value)
                time.sleep(.2)
            report['samples'] = {k: {'count': len(v), 'min': min(v), 'max': max(v)}
                                 for k, v in seen.items()}
            for name in NCEC_CHANNELS + ADVISORY_CHANNELS:
                values = seen.get(name)
                mark = 'advisory' if name in ADVISORY_CHANNELS else 'required'
                if values:
                    print(f"channel : {name} n={len(values)} min={min(values)} max={max(values)} [{mark}]")
                else:
                    print(f"channel : {name} MISSING [{mark}]")
                    if mark == 'required':
                        failures.append(f'{name} produced no samples; the vehicle CAN decode is not reaching channels')
    finally:
        client.close()
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

    if failures:
        print('\nFAIL')
        for item in failures:
            print(f'  - {item}')
        return 1
    print('\nPASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
