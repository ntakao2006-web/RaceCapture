#!/usr/bin/python3
"""Capture UART evidence without opening ttyHS1 or changing GPIO/reset state.

Run on the UNO Q before/after a failure: python3 mcu_diagnostics.py --output file.json
Output stays local; it may contain system log details. No MCU command is sent.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess

MAX_BYTES=65536
TTY_DRIVERS=Path('/proc/tty/driver')
POWER_PATHS=[Path('/sys/bus/platform/devices/4a88000.serial')/suffix/'power/control'
             for suffix in ('','4a88000.serial:0','4a88000.serial:0/4a88000.serial:0.0')]


def read_bounded(path):
    try:
        with path.open('rb') as stream: return stream.read(MAX_BYTES).decode(errors='replace')
    except OSError as error:
        return {'error':str(error)}


def command(args):
    try:
        result=subprocess.run(args,capture_output=True,timeout=3)
        return {'exit':result.returncode,'stdout':result.stdout[-MAX_BYTES:].decode(errors='replace'),
                'stderr':result.stderr[-4096:].decode(errors='replace')}
    except (OSError,subprocess.SubprocessError) as error:
        return {'error':str(error)}


def collect():
    try:
        files=[p for p in sorted(TTY_DRIVERS.iterdir()) if p.is_file()][:16]
        drivers={p.name:read_bounded(p) for p in files}
    except OSError as error:
        drivers={'error':str(error)}
    kernel=command(['dmesg','--color=never'])
    if 'stdout' in kernel:
        kernel['stdout']='\n'.join(line for line in kernel['stdout'].splitlines()
                                   if any(term in line.lower() for term in ('geni','ttyhs','uart','serial engine')))[-MAX_BYTES:]
    return {'schema':1,'utc':datetime.now(timezone.utc).isoformat(),'kernel':platform.release(),
            'tty_drivers':drivers,'power_control':{str(p):read_bounded(p) for p in POWER_PATHS},
            'kernel_uart_events':kernel,
            'router':command(['systemctl','show','arduino-router',
                              '--property=ActiveState,SubState,MainPID,Result','--no-pager']),
            'router_journal':command(['journalctl','-u','arduino-router','--since=-2min',
                                      '--lines=80','--output=short-monotonic','--no-pager']),
            'scope':'No tty open, GPIO read/write, reset, MCU halt, or driver rebind.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(collect(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__': main()
