"""Stop and confirm closure, eject safely, resume, or download a closed SD log."""
import argparse
import json
import os
import time
from pathlib import Path
from rcp_client import Client
from serial.tools import list_ports


def select_port():
    ports = list(list_ports.comports())
    # Prefer the separate programmer so RaceCapture may keep using native USB.
    for vid, pid in ((0x1A86, 0x55D4), (0x303A, 0x4001)):
        matches = [p.device for p in ports if p.vid == vid and p.pid == pid]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise RuntimeError('Multiple matching devices; select --port explicitly')
    raise RuntimeError('Logger not found. Connect the programmer or USB-OTG.')


def download_file(client, name, destination):
    if Path(name).name != name or '..' in name:
        raise ValueError('Expected a filename, not a path')
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / name
    part = destination / (name + '.partial')
    if target.exists() or part.exists():
        raise FileExistsError('Refusing to overwrite an existing download')
    offset = 0
    with part.open('xb') as f:
        while True:
            result = client.query({'readLog': {'name': name, 'offset': offset}})['logData']
            if 'error' in result:
                raise RuntimeError(result['error'])
            data = result['data'].encode('utf-8')
            if result['offset'] != offset or result['next'] != offset + len(data):
                raise RuntimeError('Readback offset mismatch')
            f.write(data)
            offset += len(data)
            if result['eof']:
                if offset != result['size']:
                    raise RuntimeError('Incomplete readback')
                break
            if not data:
                raise RuntimeError('Readback made no progress')
        f.flush()
        os.fsync(f.fileno())
    part.rename(target)
    return target


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['status', 'stop', 'eject', 'resume', 'list', 'download'])
    p.add_argument('--port', default='auto')
    p.add_argument('--name')
    p.add_argument('--output', type=Path, default=Path('downloaded_logs'))
    args = p.parse_args()
    c = Client(select_port() if args.port == 'auto' else args.port)
    try:
        if args.action in ('stop', 'eject', 'resume'):
            cmd = {'prepareSdRemoval': None} if args.action == 'eject' else {'setLogging': args.action == 'resume'}
            reply = c.query(cmd)
            if reply[next(iter(cmd))].get('rc') != 1:
                raise RuntimeError(reply)
            deadline = time.monotonic()+15
            while True:
                state = c.query({'getStatus': None})['status']['logging']
                done = (state.get('safeToRemove') if args.action == 'eject' else
                        state.get('closed') if args.action == 'stop' else state['status'] == 1)
                if done:
                    print(json.dumps(state, indent=2))
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('No confirmation: do NOT remove the SD card')
                time.sleep(.25)
        elif args.action == 'list':
            offset = 0
            while offset is not None:
                result = c.query({'listLogs': {'offset': offset}})['logs']
                if 'error' in result:
                    raise RuntimeError(result['error'])
                for f in result['files']:
                    print(f['name'], f.get('bytes', '?'))
                offset = result.get('next')
        elif args.action == 'download':
            if not args.name:
                p.error('--name required')
            print(download_file(c, args.name, args.output))
        else:
            print(json.dumps(c.query({'getStatus': None}), indent=2))
    finally:
        c.close()


if __name__ == '__main__':
    main()
