"""Passive GNSS/IMU/SD acceptance; rotates logs but never deletes or resets.

Close RaceCapture before using the native USB download port. UTC validity is
reported separately: a position fix does not guarantee resolved UTC.
"""
import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from rcp_client import Client, decode_sample
from sd_control import download_file
from verify_sd_session import files, wait_state


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', default='COM8')
    p.add_argument('--download-port', default='COM10')
    p.add_argument('--seconds', type=float, default=60)
    p.add_argument('--comparison-report', action='store_true',
                   help='Keep a completed measurement even when fix/rate checks fail; not an acceptance pass')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'checks': {}, 'samples': [], 'requested_seconds': args.seconds,
              'comparison_mode': args.comparison_report}
    c = Client(args.port)
    try:
        report['version'] = c.query({'getVer': None})
        report['config'] = c.query({'getLoggerCfg': None})['loggerCfg']
        report['configuration'] = c.query({'getGnssDiagnostics': None})['getGnssDiagnostics'].get('configuration')
        report['files_before'] = files(c)
        before = c.query({'getStatus': None})['status']
        assert before['logging']['status'] == 1
        c.query({'rotateLog': None})
        before = wait_state(c, lambda s: s['logging']['file'] != before['logging']['file'])
        report['before'] = before
        active = before['logging']['file'].rsplit('/', 1)[-1]
        end = time.monotonic() + args.seconds
        metadata = []
        while time.monotonic() < end:
            reply = c.query({'s': {'meta': not bool(metadata)}})
            values, metadata = decode_sample(reply, metadata)
            diag = c.query({'getGnssDiagnostics': None})['getGnssDiagnostics']
            report['samples'].append({'us': reply['s']['monotonic_us'], 'values': values, 'diagnostics': diag})
            time.sleep(.4)
        after = c.query({'getStatus': None})['status']
        report['after'] = after
        c.query({'rotateLog': None})
        wait_state(c, lambda s: s['logging']['file'] != after['logging']['file'])
        c.close()
        c = Client(args.download_port)
        print('Reading closed SD log', active, flush=True)
        path = download_file(c, active, args.output)
        report['csv_file'] = path.name
        ending = json.loads(download_file(c, active[:-4] + '.end.json', args.output).read_text())
        meta = json.loads(download_file(c, active[:-4] + '.meta.json', args.output).read_text())
        with path.open(newline='') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)
        ticks = [int(r['monotonic_us']) for r in rows]
        intervals = [b-a for a,b in zip(ticks, ticks[1:])]
        tow = [int(r['GPSTow']) for r in rows if r['GPSTow']]
        steps = [(b-a) % 604800000 for a,b in zip(tow, tow[1:]) if b != a]
        hz = (len(ticks)-1)*1e6/(ticks[-1]-ticks[0])
        checks = report['checks']
        checks['sd_100hz'] = 98 <= hz <= 102 and all(0 < dt <= 20000 for dt in intervals)
        checks['sd_clean_close'] = ending['clean_close'] and ending['rows'] == len(rows)
        checks['metadata_matches_columns'] = [x['name'] for x in meta['columns']] == headers
        expected_ms = (report.get('configuration') or {}).get('periodMs')
        if expected_ms is None:
            expected_ms = {8:125, 10:100, 15:67, 18:56, 20:50, 25:40}[report['config']['gnssHz']]
        checks['gnss_configured_rate_no_missing_epochs'] = bool(steps) and all(abs(x-expected_ms) <= 1 for x in steps) and abs(statistics.mean(steps)-expected_ms) < .1
        if report.get('configuration') is not None:
            checks['gnss_configuration_readback_verified'] = bool(report['samples']) and all(s['diagnostics']['configuration']['verified'] for s in report['samples'])
            initial_profile = report['configuration'].get('profileId')
            if initial_profile is not None:
                checks['gnss_profile_unchanged'] = all(s['diagnostics']['configuration'].get('profileId') == initial_profile for s in report['samples'])
            report['configuration'] = report['samples'][-1]['diagnostics']['configuration'] if report['samples'] else None
            # Report what was actually used; enabled constellations are not proof
            # that their satellites are visible or suitable at this location.
            report['satellite_systems_max_used'] = {}
            for sample in report['samples']:
                for system in sample['diagnostics'].get('satellites', {}).get('systems', []):
                    name = system['name']
                    report['satellite_systems_max_used'][name] = max(system['used'], report['satellite_systems_max_used'].get(name, 0))
        checks['imu_100hz_valid'] = all(float(r['IMUHz'] or 0) >= 98 and r['IMULink'] == '1' and all(r[k] for k in ('GForceX','GForceY','GForceZ')) for r in rows)
        checks['position_fix_continues'] = all(r['GPSFix'] == '3' and r['Lat'] and r['Lon'] for r in rows)
        diagnostic_columns = ('GNSSAcq','GNSSTrack','GNSSCNoMax','GNSSCNoTop4','RFNoise','RFAGC','RFJam','RFCW','GNSSRetry','GNSSAge','GNSSBad')
        checks['diagnostics_in_every_sd_row'] = all(all(r.get(k, '') for k in diagnostic_columns) for r in rows)
        checks['diagnostic_replies_fresh'] = all(all(s['diagnostics'][k] for k in ('satellitesFresh','radioFresh','pvtFresh')) for s in report['samples'])
        checks['no_sd_errors_or_drops'] = all(after['logging'][k] == before['logging'][k] for k in ('errors','drops'))
        checks['no_gnss_retries_or_errors'] = all(after['GPS'][k] == before['GPS'][k] for k in ('retries','badFrames','duplicateEpochs'))
        report['files_after'] = files(c)
        checks['existing_files_preserved'] = all(n in report['files_after'] and report['files_after'][n] >= size for n,size in report['files_before'].items())
        report['sd'] = {'rows': len(rows), 'hz': hz, 'max_gap_us': max(intervals)}
        report['gnss'] = {'unique_epochs': len(steps)+1, 'periods_ms': sorted(set(steps)), 'hz': 1000/statistics.mean(steps) if steps else 0}
        report['utc'] = {'valid_rows': sum(bool(r['utc_us']) for r in rows), 'total_rows': len(rows)}
        print(json.dumps({k: report[k] for k in ('checks','sd','gnss','utc','after')}, indent=2), flush=True)
        report['acceptance_passed'] = all(checks.values())
        if not args.comparison_report:
            assert report['acceptance_passed'], ', '.join(k for k,v in checks.items() if not v)
    finally:
        c.close()
        (args.output/'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
