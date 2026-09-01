"""Read-only process measurements using built-in Windows APIs; no extra package."""
import ctypes
from ctypes import wintypes
import time


class Counters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ("peak_working", "working", "peak_paged", "paged",
                                           "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile", "private")]


class WindowsMetrics:
    def __init__(self, pid):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.psapi = ctypes.WinDLL("psapi", use_last_error=True)
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self.psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        self.handle = self.kernel.OpenProcess(0x410, False, pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.start = time.monotonic()
        self.peak_working = self.peak_private = self.cpu = 0

    def sample(self):
        counters = Counters(cb=ctypes.sizeof(Counters))
        if self.psapi.GetProcessMemoryInfo(self.handle, ctypes.byref(counters), counters.cb):
            self.peak_working = max(self.peak_working, counters.peak_working)
            self.peak_private = max(self.peak_private, counters.private)
        times = [wintypes.FILETIME() for _ in range(4)]
        if self.kernel.GetProcessTimes(self.handle, *[ctypes.byref(t) for t in times]):
            self.cpu = sum((t.dwHighDateTime << 32) | t.dwLowDateTime for t in times[2:]) / 10_000_000

    def finish(self):
        self.sample()
        elapsed = time.monotonic() - self.start
        self.kernel.CloseHandle(self.handle)
        return {"peak_working_set_mib": round(self.peak_working / 2**20, 1),
                "peak_private_mib": round(self.peak_private / 2**20, 1),
                "cpu_seconds": round(self.cpu, 2), "elapsed_seconds": round(elapsed, 2),
                "mean_cpu_percent_of_one_core": round(self.cpu / elapsed * 100, 1),
                "note": "Windows process during full UI QA, including startup and screenshots; not ARM hardware performance."}
