"""Start / collect the course-walk radio log on the UNO Q from the pit PC (2026-10-23).

    python radio_walk_pc.py start [minutes]   start radio_walk_log.py in the background (default 30 min)
    python radio_walk_pc.py fetch             stop it and copy the newest CSV to drive_logs/<date>/radio_walk/
Reaches the UNO Q over USB (adb) or, during the walk, the same tethering (ssh unoq),
whichever answers first. The CSV holds positions, so it goes under drive_logs/ (not in git).
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = '/home/arduino/antenna_compare/radio_walk_log.py'
ADB_CANDIDATES = [Path(os.environ.get('LOCALAPPDATA', '')) / 'Android' / 'Sdk' / 'platform-tools' / 'adb.exe']


def adb_shell():
    adb = shutil.which('adb') or next((str(p) for p in ADB_CANDIDATES if p.is_file()), None)
    if not adb: return None
    out = subprocess.run([adb, 'devices'], capture_output=True, text=True, timeout=15).stdout
    # The UNO Q's serial is all digits; a phone over Wi-Fi debugging shows a long name.
    serial = next((l.split()[0] for l in out.splitlines()[1:] if l.endswith('\tdevice') and l.split()[0].isdigit()), None)
    return [adb, '-s', serial, 'shell'] if serial else None


def ssh_shell():
    try:
        ok = subprocess.run(['ssh', '-o', 'ConnectTimeout=6', '-o', 'BatchMode=yes', 'unoq', 'true'], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return None
    return ['ssh', 'unoq'] if ok else None


def connect():
    shell = adb_shell() or ssh_shell()
    if not shell:
        sys.exit('UNO Qに接続できません。USBでつなぐか、PCをUNO Qと同じテザリングにつないで、もう一度実行してください。')
    print('接続：' + ('USB（adb）' if 'adb' in shell[0].lower() else 'テザリング（ssh）'))
    return shell


def run(shell, command):
    return subprocess.run(shell + [command], capture_output=True, text=True, encoding='utf-8', timeout=60)


def start(minutes):
    shell = connect()
    if 'ok' not in run(shell, f'test -f {SCRIPT} && echo ok').stdout:
        sys.exit(f'UNO Qに {SCRIPT} がありません。')
    # The pattern is bracketed so that pgrep does not match the shell running this line.
    if 'running' in run(shell, 'pgrep -f "[r]adio_walk_log.py" >/dev/null && echo running').stdout:
        print('もう記録中です（そのまま歩いてよい）。'); return
    run(shell, f'setsid nohup python3 {SCRIPT} {minutes} >/dev/null 2>&1 < /dev/null &')
    time.sleep(3)
    if 'running' not in run(shell, 'pgrep -f "[r]adio_walk_log.py" >/dev/null && echo running').stdout:
        sys.exit('記録を始められませんでした。UNO QのWebが起動しているか確かめて、もう一度実行してください。')
    print(f'電波の記録を始めました（{minutes:g}分で自動で止まります。LTEで送信するので約4MB/時を使います）。')
    print('UNO Qをつないだまま歩き始めてよい。')


def fetch():
    shell = connect()
    run(shell, 'mkdir -p ~/radio_walk && touch ~/radio_walk/stop')
    time.sleep(4)   # the logger checks the stop file every 2 s and then restores the send link
    name = run(shell, 'ls -t ~/radio_walk/walk_*.csv 2>/dev/null | head -1').stdout.strip()
    if not name:
        sys.exit('UNO Qに電波の記録が見つかりません。')
    # adb shell turns the CSV's CRLF into CR CR LF; keep one LF per row whichever way it came.
    raw = subprocess.run(shell + [f'cat {name}'], capture_output=True, timeout=60).stdout
    data = '\n'.join(l for l in raw.decode('utf-8').replace('\r', '').split('\n') if l) + '\n'
    out = REPO / 'drive_logs' / time.strftime('%Y-%m-%d') / 'radio_walk'
    out.mkdir(parents=True, exist_ok=True)
    dest = out / Path(name).name
    dest.write_text(data, encoding='utf-8', newline='')
    rows = [l.split(',') for l in data.splitlines()[1:]]
    with_pos = sum(1 for r in rows if len(r) > 6 and r[1] and r[6])
    print(f'止めて回収しました：{dest}')
    print(f'{len(rows)}行（約{round(len(rows) * 2 / 60)}分）、うち位置と電波の両方がある行 {with_pos}')


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in ('start', 'fetch'): sys.exit(__doc__)
    start(float(sys.argv[2]) if len(sys.argv) > 2 else 30) if sys.argv[1] == 'start' else fetch()
