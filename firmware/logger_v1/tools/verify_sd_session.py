"""Non-destructive SD session verification; no CAN transmit, formatting or deletion.

Briefly stops recording and logically ejects/remounts the inserted SD card.
Run without RaceCapture holding the selected COM port.
"""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import time
from rcp_client import Client, decode_sample
from sd_control import download_file


def files(client):
    result = {}
    offset = 0
    while offset is not None:
        page = client.query({'listLogs': {'offset': offset}})['logs']
        if 'error' in page:
            raise RuntimeError(page['error'])
        result.update((f['name'], f.get('bytes')) for f in page['files'])
        offset = page.get('next')
    return result


def wait_state(client, predicate, timeout=20):
    end = time.monotonic()+timeout
    while time.monotonic() < end:
        state = client.query({'getStatus': None})['status']
        if predicate(state):
            return state
        time.sleep(.15)
    raise TimeoutError('Storage state did not reach expected state')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', default='COM10')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    report = {'checks': {}}
    c = Client(args.port)
    try:
        before = c.query({'getStatus': None})['status']; report['before'] = before
        assert before['logging']['status'] == 1
        report['files_before'] = files(c)
        active = before['logging']['file'].rsplit('/',1)[-1]
        assert c.query({'setLogging': False})['setLogging']['rc'] == 1
        stopped = wait_state(c, lambda s: s['logging']['closed'] and not s['logging']['file'])
        report['stopped'] = stopped
        csv_path = download_file(c, active, args.output)
        meta_path = download_file(c, active[:-4]+'.meta.json', args.output)
        end_path = download_file(c, active[:-4]+'.end.json', args.output)
        meta = json.loads(meta_path.read_text()); end = json.loads(end_path.read_text())
        with csv_path.open(newline='') as f:
            reader = csv.DictReader(f); headers = reader.fieldnames; row_count = sum(1 for _ in reader)
        checks = report['checks']
        checks['metadata_matches_columns'] = [x['name'] for x in meta['columns']] == headers
        checks['clean_close_matches_rows'] = end['clean_close'] and row_count == end['rows']
        checks['imu_axes_explicit'] = 'not configured' in meta['imu_axes']
        boot = meta.get('estimated_boot_utc_us')
        expected = dt.datetime.fromtimestamp(boot/1e6,dt.timezone(dt.timedelta(hours=9))).strftime('%Y%m%d_%H%M%S_JST_') if boot else None
        checks['jst_filename_matches_metadata'] = bool(expected and active.startswith(expected))
        assert c.query({'prepareSdRemoval': None})['prepareSdRemoval']['rc'] == 1
        ejected = wait_state(c, lambda s: s['logging']['safeToRemove'])
        report['ejected'] = ejected
        for command in ({'prepareSdRemoval': None},{'setLogging': False}):
            c.query(command)
            assert c.query({'getStatus': None})['status']['logging']['safeToRemove']
        checks['eject_retry_is_idempotent'] = True
        time.sleep(.7)
        paused = c.query({'getStatus': None})['status']
        checks['no_writes_after_eject'] = paused['logging']['rows'] == ejected['logging']['rows']
        checks['sensors_continue_while_ejected'] = paused['imuSamples'] > ejected['imuSamples'] and paused['gnssSamples'] > ejected['gnssSamples']
        assert c.query({'setLogging': True})['setLogging']['rc'] == 1
        resumed = wait_state(c,lambda s: s['logging']['status']==1 and s['logging']['rows']>paused['logging']['rows']+50)
        checks['resume_new_file'] = resumed['logging']['file'].rsplit('/',1)[-1] != active
        after_files = files(c)
        checks['existing_files_preserved'] = all(after_files.get(n)==size for n,size in report['files_before'].items() if n not in (active,active[:-4]+'_can.csv'))
        report['transport_cycles'] = []
        for _ in range(5):
            c.close();time.sleep(.4);c=Client(args.port)
            sample=c.query({'s': {'meta':True}});decoded,_=decode_sample(sample,[])
            report['transport_cycles'].append({'gps_fix':decoded.get('GPSFix'),'imu_hz':decoded.get('IMUHz')})
        after = c.query({'getStatus': None})['status'];report['after']=after
        checks['usb_port_reopen_five_times'] = all(x['gps_fix'] in (2,3,4) and x['imu_hz']>=98 for x in report['transport_cycles'])
        checks['sd_continues_without_pc'] = after['logging']['rows'] > resumed['logging']['rows']+100
        checks['no_new_errors_or_drops'] = all(after['logging'][k]==before['logging'][k] for k in ('errors','drops'))
        report['csv_rows'] = row_count
        print(json.dumps({'checks':checks,'file':active,'csv_rows':row_count},indent=2))
        if not all(checks.values()):
            raise AssertionError('Failed: '+','.join(k for k,v in checks.items() if not v))
    finally:
        # Leave the actual logger recording even if an assertion fails.
        try:
            if not c.serial.is_open:c=Client(args.port)
            state=c.query({'getStatus':None})['status']['logging']
            if state['status']!=1:c.query({'setLogging':True})
        finally:
            c.close();(args.output/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()
