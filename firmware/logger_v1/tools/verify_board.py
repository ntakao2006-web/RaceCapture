"""Verify real acquisition and SD readback. Never burns GNSS OTP or formats SD."""
import argparse
import csv
import io
import json
import statistics
import time
from pathlib import Path
from rcp_client import Client, decode_sample


def download(client, name):
    offset = 0
    pieces = []
    while True:
        part = client.query({'readLog': {'name': name, 'offset': offset}})['logData']
        if 'error' in part:
            raise RuntimeError(part['error'])
        assert part['offset'] == offset
        data = part['data']
        assert part['next'] == offset + len(data.encode('utf-8'))
        pieces.append(data)
        offset = part['next']
        if part['eof']:
            return ''.join(pieces)
        if not data or offset > 2_000_000:
            raise RuntimeError('Readback limit exceeded')


def rotate(client):
    old = client.query({'getStatus': None})['status']['logging']['file']
    client.query({'rotateLog': None})
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        time.sleep(.1)
        new = client.query({'getStatus': None})['status']['logging']['file']
        if new and new != old:
            return new
    raise TimeoutError('Storage did not confirm log rotation')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', default='COM8')
    p.add_argument('--seconds', type=float, default=15)
    p.add_argument('--wait-fix', type=float, default=0, help='Wait this many seconds for valid position/UTC before measuring')
    p.add_argument('--desk-can-loop', action='store_true', help='Requires CAN1 physically wired to CAN2, no car')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    client = Client(args.port)
    report = {'port': args.port, 'checks': {}, 'samples': []}
    try:
        report['version'] = client.query({'getVer': None})
        assert 'real-sensor' in report['version']['ver']['fname']
        report['before'] = client.query({'getStatus': None})['status']
        deadline = time.monotonic() + args.wait_fix
        while args.wait_fix and (report['before']['GPS']['qual'] not in (2, 3, 4) or not report['before']['GPS']['utcValid']):
            if time.monotonic() >= deadline:
                raise TimeoutError('GNSS position/UTC acquisition timeout')
            print('Waiting for GNSS:', report['before']['GPS']['sats'], 'satellites', flush=True)
            time.sleep(5)
            report['before'] = client.query({'getStatus': None})['status']
        assert report['before']['logging']['status'] == 1
        report['config'] = client.query({'getLoggerCfg': None})
        session = rotate(client)
        print('Capturing', session, flush=True)
        end = time.monotonic() + args.seconds
        metadata = []
        while time.monotonic() < end:
            s = client.query({'s': {'meta': not bool(metadata)}})
            decoded, metadata = decode_sample(s, metadata)
            report['samples'].append({'us': s['s']['monotonic_us'], 'values': decoded})
            time.sleep(.1)
        if args.desk_can_loop:
            reply = client.query({'testCanLoop': {'confirm': 'DESK_CAN1_CAN2_LOOP'}})
            assert reply['testCanLoop']['rc'] == 1
            time.sleep(.4)
            report['can_bench'] = client.query({'getStatus': None})['status']['CAN']
            report['checks']['can_loop'] = report['can_bench']['benchStatus'] == 2
        rotate(client)
        report['after'] = client.query({'getStatus': None})['status']
        name = session.rsplit('/', 1)[-1]
        csv_text = download(client, name)
        (args.output / name).write_text(csv_text, encoding='utf-8', newline='')
        raw_name = name[:-4] + '_can.csv'
        raw = download(client, raw_name)
        (args.output / raw_name).write_text(raw, encoding='utf-8', newline='')
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        assert len(rows) > 100
        assert set(rows[0]) == {'monotonic_us', 'utc_us'} | {x['nm'] for x in metadata}
        assert not any(None in row or None in row.values() for row in rows)
        ticks = [int(r['monotonic_us']) for r in rows]
        intervals = [b-a for a, b in zip(ticks, ticks[1:])]
        rate = (len(ticks)-1) * 1e6 / (ticks[-1]-ticks[0])
        report['sd'] = {'rows': len(rows), 'hz': rate, 'max_gap_us': max(intervals),
                        'median_gap_us': statistics.median(intervals), 'can_rows': len(list(csv.DictReader(io.StringIO(raw))))}
        report['checks']['sd_100hz'] = 98 <= rate <= 102 and all(x > 0 for x in intervals)
        report['checks']['no_drops'] = report['after']['logging']['drops'] == report['before']['logging']['drops']
        report['checks']['imu_100hz'] = all(x['values'].get('IMUHz', 0) >= 98 for x in report['samples'][10:])
        report['checks']['imu_data_valid'] = all(x['values'].get('IMULink') == 1 and all(k in x['values'] for k in ('GForceX', 'GForceY', 'GForceZ')) for x in report['samples'][10:])
        report['checks']['sd_imu_no_false_missing'] = all(r['IMULink'] == '1' and all(r[k] for k in ('GForceX', 'GForceY', 'GForceZ')) for r in rows)
        report['checks']['gps_updates'] = len({r['GPSTow'] for r in rows if r['GPSTow']}) > 20
        tow = [int(row['GPSTow']) for row in rows if row['GPSTow']]
        steps = [(b-a) % 604800000 for a, b in zip(tow, tow[1:]) if b != a]
        expected_ms = {8:125, 10:100, 15:67, 18:56, 20:50, 25:40}[report['config']['loggerCfg']['gnssHz']]
        report['gnss'] = {'unique_updates': len(steps) + 1, 'periods_ms': sorted(set(steps)), 'expected_ms': expected_ms,
                          'hz_from_tow': 1000 / statistics.mean(steps) if steps else 0}
        # iTOW is integer milliseconds. Receiver clock alignment can yield an
        # adjacent 55/57 ms pair at a 56 ms measurement rate. Reject missing
        # epochs (112 ms), not this 1 ms quantization/alignment variation.
        report['checks']['gnss_max_normal_cadence'] = bool(steps) and all(abs(x - expected_ms) <= 1 for x in steps) and abs(statistics.mean(steps) - expected_ms) <= .1
        report['checks']['gps_utc_fraction_preserved'] = any(x['values'].get('GPSUTC', 0) % 1 != 0 for x in report['samples'])
        report['checks']['no_sd_errors'] = report['after']['logging']['errors'] == report['before']['logging']['errors']
        report['checks']['gnss_fix'] = any(x['values'].get('GPSFix', 0) in (2, 3, 4) for x in report['samples'])
        report['checks']['vehicle_listen_only'] = report['after']['CAN']['vehicleListenOnly'] is True
        report['checks']['no_dummy_rpm'] = all('RPM' not in x['values'] for x in report['samples'])
        print(json.dumps({'checks': report['checks'], 'sd': report['sd'], 'after': report['after']}, indent=2), flush=True)
        if not all(report['checks'].values()):
            raise AssertionError('Failed checks: ' + ', '.join(k for k, v in report['checks'].items() if not v))
    finally:
        client.close()
        (args.output / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
