"""Exercise real IMU-only fusion stops; preserve SD files, GNSS and MCU uptime.

Requires explicit --exercise-recovery. Run with A105 UART, without RaceCapture
holding --download-port. Deliberate missing IMU samples are retained in SD CSV.
"""
import argparse
import csv
import json
import time
from pathlib import Path
from rcp_client import Client, decode_sample
from sd_control import download_file
from verify_sd_session import files, wait_state


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', default='COM8')
    p.add_argument('--download-port', default='COM10')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--exercise-recovery', action='store_true', required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'checks': {}, 'cycles': []}
    c = Client(args.port)
    try:
        before = c.query({'getStatus': None})['status']
        assert before['logging']['status'] == 1 and before['IMU']['status'] == 5
        report['files_before'] = files(c)
        c.query({'rotateLog': None})
        before = wait_state(c, lambda s: s['logging']['file'] != before['logging']['file'])
        report['before'] = before
        active = before['logging']['file'].rsplit('/', 1)[-1]
        for _ in range(3):
            prior = c.query({'getStatus': None})['status']
            reply = c.query({'testImuRecovery': {'confirm': 'LOGGER_IMU_ONLY'}})
            assert reply['testImuRecovery']['rc'] == 1, reply
            start = time.monotonic()
            cycle = {'before': prior, 'samples': []}
            while time.monotonic() - start < 10:
                state = c.query({'getStatus': None})['status']
                values, _ = decode_sample(c.query({'s': {'meta': True}}), [])
                cycle['samples'].append({'elapsed': time.monotonic() - start,
                                        'IMU': state['IMU'], 'IMULink': values.get('IMULink'),
                                        'IMUHz': values.get('IMUHz'),
                                        'GForceX': values.get('GForceX')})
                if (state['IMU']['recoveries'] > prior['IMU']['recoveries'] and
                        state['IMU']['status'] == 5 and values.get('IMULink') == 1 and
                        values.get('IMUHz', 0) >= 98):
                    cycle['after'] = state
                    break
            assert 'after' in cycle, cycle
            assert state['IMU']['diagnostic'] == 2
            assert state['IMU']['invalidSamples'] >= prior['IMU']['invalidSamples'] + 10
            assert state['IMU']['recoveries'] == prior['IMU']['recoveries'] + 1
            assert state['imuSamples'] > prior['imuSamples']
            assert state['gnssSamples'] > prior['gnssSamples']
            assert state['logging']['file'].rsplit('/', 1)[-1] == active
            report['cycles'].append(cycle)
            print('IMU recovered in %.2f seconds; valid rate %.1f Hz' %
                  (cycle['samples'][-1]['elapsed'], values['IMUHz']), flush=True)
        time.sleep(5)
        after = c.query({'getStatus': None})['status']
        report['after'] = after
        checks = report['checks']
        checks['three_imu_only_recoveries'] = len(report['cycles']) == 3
        checks['no_extra_recovery_after_test'] = after['IMU']['recoveries'] == report['cycles'][-1]['after']['IMU']['recoveries']
        checks['mcu_not_rebooted'] = after['system']['uptime'] > before['system']['uptime']
        checks['gnss_continued'] = after['gnssSamples'] > before['gnssSamples'] + 100
        checks['sd_continued_same_file'] = after['logging']['file'] == before['logging']['file'] and after['logging']['rows'] > before['logging']['rows'] + 500
        checks['no_sd_errors_or_drops'] = all(after['logging'][k] == before['logging'][k] for k in ('errors', 'drops'))
        c.query({'rotateLog': None})
        wait_state(c, lambda s: s['logging']['file'] != after['logging']['file'])
        c.close()
        c = Client(args.download_port)
        csv_path = download_file(c, active, args.output)
        end_path = download_file(c, active[:-4] + '.end.json', args.output)
        with csv_path.open(newline='') as f:
            rows = list(csv.DictReader(f))
        end = json.loads(end_path.read_text())
        ticks = [int(r['monotonic_us']) for r in rows]
        rate = (len(ticks)-1) * 1e6 / (ticks[-1]-ticks[0])
        missing = [r for r in rows if not r['GForceX']]
        checks['csv_100hz_during_imu_reset'] = 98 <= rate <= 102
        checks['invalid_imu_is_blank'] = bool(missing) and all(not r[k] for r in missing for k in ('AccelX','GyroX','GForceY'))
        checks['csv_imu_returns_after_gap'] = all(r['GForceX'] and r['IMULink'] == '1' for r in rows[-100:])
        checks['closed_csv_matches_end'] = end['clean_close'] and end['rows'] == len(rows)
        report['csv'] = {'file': active, 'rows': len(rows), 'hz': rate, 'missing_imu_rows': len(missing),
                         'max_gap_us': max(b-a for a,b in zip(ticks,ticks[1:]))}
        after_files = files(c)
        # Only the previously active CSV could grow; all old closed files remain.
        checks['existing_files_preserved'] = all(n in after_files and after_files[n] >= size for n,size in report['files_before'].items())
        print(json.dumps({'checks': checks, 'csv': report['csv']}, indent=2), flush=True)
        assert all(checks.values()), checks
    finally:
        c.close()
        (args.output / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
