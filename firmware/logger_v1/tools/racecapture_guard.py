"""Windows RaceCapture recovery launcher. Never opens the logger's serial port.

After observed acquisition stops, wait for USB to return, request a normal app
close, then restart. No forced termination or system-wide USB/power changes.
Closing RaceCapture yourself ends this helper as well.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time


class RecoveryPolicy:
    def __init__(self, timeout=25):
        self.timeout = timeout
        self.last_id = None
        self.last_progress = None
        self.port_since = None
        self.armed = False
        self.restarts = []

    def observe(self, now, sample_id, port_present, recording=True):
        if not recording:
            self.armed = False
            self.last_progress = now
        if sample_id is not None and sample_id != self.last_id:
            if self.last_id is not None and recording:
                self.armed = True
            self.last_id = sample_id
            self.last_progress = now
        if not port_present:
            self.port_since = None
            return False
        if self.port_since is None:
            self.port_since = now
        self.restarts = [x for x in self.restarts if now-x < 600]
        return (recording and self.armed and self.last_progress is not None and
                now-self.last_progress >= self.timeout and now-self.port_since >= 5 and
                len(self.restarts) < 3)

    def restarted(self, now):
        self.restarts.append(now)
        self.armed = False
        self.last_id = None
        self.last_progress = now


def latest_sample(database):
    try:
        with sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True, timeout=.2) as c:
            row = c.execute('SELECT id FROM datapoint ORDER BY id DESC LIMIT 1').fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        return None


def recording_enabled(prefs):
    try:
        obj = json.loads(prefs.read_text(encoding='utf-8'))
        return obj['general_prefs']['preferences'].get('record_session') == '1'
    except (OSError, ValueError, KeyError):
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe', type=Path, default=Path(r'C:\Program Files (x86)\RaceCapture\racecapture.exe'))
    p.add_argument('--pid', type=int, help='Attach to this existing RaceCapture instance')
    p.add_argument('--port', default='COM10')
    p.add_argument('--log', type=Path, required=True)
    p.add_argument('--timeout', type=float, default=25)
    args = p.parse_args()
    if os.name != 'nt':
        p.error('Windows only')
    from ctypes import wintypes as w
    k, u = ctypes.WinDLL('kernel32', use_last_error=True), ctypes.WinDLL('user32', use_last_error=True)
    k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]; k.OpenProcess.restype=w.HANDLE
    k.CloseHandle.argtypes=[w.HANDLE]
    k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD]
    k.CreateMutexW.argtypes=[ctypes.c_void_p,w.BOOL,w.LPCWSTR];k.CreateMutexW.restype=w.HANDLE
    k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)]
    k.QueryDosDeviceW.argtypes=[w.LPCWSTR,w.LPWSTR,w.DWORD]
    u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
    callback_type=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    u.EnumWindows.argtypes=[callback_type,w.LPARAM]
    u.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
    mutex=k.CreateMutexW(None,False,'Local\\LoggerV1RaceCaptureGuard')
    if not mutex or ctypes.get_last_error()==183:
        p.error('Recovery helper already running')
    args.log.parent.mkdir(parents=True,exist_ok=True)
    def log(event, **info):
        with args.log.open('a',encoding='utf-8') as f:
            f.write(json.dumps(dict(time=time.strftime('%Y-%m-%dT%H:%M:%S%z'),event=event,**info))+'\n')
    def attach(pid):
        handle=k.OpenProcess(0x100000|0x1000,False,pid)
        if not handle:raise OSError('Cannot open app process')
        path=ctypes.create_unicode_buffer(32768); size=w.DWORD(len(path))
        if not k.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)) or Path(path.value).resolve()!=args.exe.resolve():
            k.CloseHandle(handle);raise ValueError('PID does not belong to the selected RaceCapture executable')
        return handle
    def launch():
        proc=subprocess.Popen([str(args.exe)],cwd=args.exe.parent)
        return proc.pid, attach(proc.pid)
    def present():
        # QueryDosDevice does not claim/open the COM port used by RaceCapture.
        buf=ctypes.create_unicode_buffer(4096)
        return bool(k.QueryDosDeviceW(args.port,buf,len(buf)))
    data=Path.home()/'AppData/Roaming/racecapture'
    pid,handle=(args.pid,attach(args.pid)) if args.pid else launch()
    policy=RecoveryPolicy(args.timeout); log('started',app_pid=pid,port=args.port)
    try:
        while k.WaitForSingleObject(handle,0)==258:
            current=latest_sample(data/'datastore.sq3')
            if current is not None and policy.observe(time.monotonic(),current,present(),recording_enabled(data/'prefs.json')):
                log('acquisition_stalled',sample_id=current)
                @callback_type
                def close_window(hwnd,_):
                    owner=w.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
                    if owner.value==pid:u.PostMessageW(hwnd,0x10,0,0)
                    return True
                u.EnumWindows(close_window,0)
                deadline=time.monotonic()+15
                while k.WaitForSingleObject(handle,0)==258 and time.monotonic()<deadline:
                    time.sleep(.25)
                if k.WaitForSingleObject(handle,0)==258:
                    log('normal_close_failed_no_force_kill');break
                k.CloseHandle(handle);handle=None
                pid,handle=launch();policy.restarted(time.monotonic());log('restarted',app_pid=pid)
            time.sleep(2)
        log('stopped')
    finally:
        if handle:k.CloseHandle(handle)
        k.CloseHandle(mutex)


if __name__=='__main__':
    main()
