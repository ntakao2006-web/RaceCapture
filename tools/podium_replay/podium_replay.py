"""Replays a recorded run to Podium as if the EcoLogger app were sending it.

For checking what Podium shows (map, speed) without driving. Sends the same
lines as the Android app's direct mode (PodiumDirect.kt / PodiumEncoder.kt):
auth, the app's channel table, then one row every 100 ms, with the recorded
1 Hz track interpolated to 10 Hz and stamped with the current time.

The streaming key is read from the EcoLogger app on the phone over USB
(adb run-as) and is never printed or saved. Do not run this while the phone
(or a server holding the same key) is sending: two senders on one key collide.

Input CSV (no header): unix time [s], speed [km/h], engine temp, lon, lat
(the team's cleaned_trajectory_cut_comma-v2.csv, Motegi 2025).

    python podium_replay.py <csv> --serial 57141JEBF13732 --seconds 300

Where this PC cannot reach Podium's port 8080 (the lab Wi-Fi blocks it), run it
on the UNO Q and hand the key over a pipe (it then stays off disk and argv):

    python podium_replay.py --print-key --serial 57141JEBF13732 | adb -s <unoq> shell python3 /tmp/podium_replay.py /tmp/track.csv --key-stdin
"""
import argparse
import csv
import json
import math
import re
import socket
import subprocess
import sys
import threading
import time

HOST, PORT = "telemetry.podium.live", 8080
ADB = r"C:\Users\ntaka\AppData\Local\Android\Sdk\platform-tools\adb.exe"
AUTH = {"apiVer": 1.1, "device": "RC_APP (RCPMK3)", "ver": "2.19.0 (2.16.1)", "sn": "C3PROTO01"}

# Same order, names, units, ranges and decimals as PodiumEncoder.CHANNELS in the app.
CHANNELS = [
    ("Interval", "Interval", "ms", 0, 0, 0), ("Utc", "Utc", "ms", 0, 0, 0),
    ("Lat", "Latitude", "deg", -90, 90, 6), ("Lon", "Longitude", "deg", -180, 180, 6),
    ("Altitude", "Altitude", "m", -500, 9000, 2), ("GPSSpeed", "GPSSpeed", "km/h", 0, 300, 2),
    ("Speed", "Speed", "km/h", 0, 300, 2), ("Yaw", "Yaw", "deg", 0, 360, 2),
    ("GPSFix", "GPSFix", "", 0, 5, 0), ("GPSSats", "GPSSats", "", 0, 64, 0),
    ("AccelX", "AccelX", "m/s^2", -1000, 1000, 2), ("AccelY", "AccelY", "m/s^2", -1000, 1000, 2),
    ("AccelZ", "AccelZ", "m/s^2", -1000, 1000, 2), ("GyroX", "GyroX", "deg/s", -1000, 1000, 2),
    ("GyroY", "GyroY", "deg/s", -1000, 1000, 2), ("GyroZ", "GyroZ", "deg/s", -1000, 1000, 2),
    ("LongAccel", "LongAccel", "g", -8, 8, 3), ("LatAccel", "LatAccel", "g", -8, 8, 3),
    ("VertAccel", "VertAccel", "g", -8, 8, 3),
    ("LapCount", "LapCount", "", 0, 10000, 0), ("CurrentLap", "CurrentLap", "", 0, 10000, 0),
    ("LapTime", "LapTime", "Min", 0, 60, 4), ("BestLap", "BestLap", "Min", 0, 60, 4),
    ("ElapsedTime", "ElapsedTime", "Min", 0, 60, 4), ("RaceTime", "RaceTime", "Min", 0, 600, 4),
    ("LapsLeft", "LapsLeft", "", 0, 1000, 0),
]


def line(obj):
    return (json.dumps(obj, separators=(",", ":")) + "\n").encode("ascii")


def row(values):
    out, masks = [], [0] * ((len(CHANNELS) + 31) // 32)
    for i, (key, _, _, _, _, prec) in enumerate(CHANNELS):
        v = values.get(key)
        if v is None or not math.isfinite(v):
            continue
        out.append(int(round(v)) if prec == 0 else round(v, prec))
        masks[i // 32] |= 1 << (i % 32)
    return out + masks


def key_from_phone(serial):
    """The key saved in the EcoLogger app's settings (never printed)."""
    xml = subprocess.run([ADB, "-s", serial, "exec-out", "run-as", "jp.ecorun.logger", "cat", "shared_prefs/settings.xml"],
                         capture_output=True, text=True, encoding="utf-8").stdout
    m = re.search(r'name="podiumKey">([^<]+)<', xml)
    if not m:
        sys.exit("No Podium key saved in the app on the phone")
    return m.group(1)


def phone_is_recording(serial):
    out = subprocess.run([ADB, "-s", serial, "shell", "dumpsys", "activity", "services", "jp.ecorun.logger"],
                         capture_output=True, text=True, encoding="utf-8").stdout
    return "ServiceRecord" in out


def track(path):
    pts = []
    with open(path, encoding="utf-8") as f:
        for r in csv.reader(f):
            if len(r) >= 5:
                pts.append((float(r[0]), float(r[1]), float(r[3]), float(r[4])))  # t, km/h, lon, lat
    return pts


def at(pts, t):
    """Linear interpolation of speed and position at t seconds into the track, plus heading."""
    t0 = pts[0][0] + t
    for a, b in zip(pts, pts[1:]):
        if a[0] <= t0 <= b[0]:
            f = (t0 - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0
            lat = a[3] + (b[3] - a[3]) * f; lon = a[2] + (b[2] - a[2]) * f
            dx = (b[2] - a[2]) * math.cos(math.radians(lat)); dy = b[3] - a[3]
            yaw = (math.degrees(math.atan2(dx, dy)) + 360) % 360 if (dx or dy) else None
            return a[1] + (b[1] - a[1]) * f, lat, lon, yaw
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--serial", help="adb serial of the phone holding the key")
    ap.add_argument("--seconds", type=float, default=300)
    ap.add_argument("--key-stdin", action="store_true", help="read the key from the first line of stdin")
    ap.add_argument("--print-key", action="store_true", help="only write the phone's key to stdout, for a pipe")
    args = ap.parse_args()
    if args.key_stdin:
        key = sys.stdin.readline().strip()
    else:
        if not args.serial:
            sys.exit("--serial is needed to read the key from the phone")
        if phone_is_recording(args.serial):
            sys.exit("The phone is recording (it may be sending with the same key): stop it first")
        key = key_from_phone(args.serial)
        if args.print_key:
            sys.stdout.write(key + "\n"); return
    pts = track(args.csv)
    s = socket.create_connection((HOST, PORT), timeout=10)
    s.sendall(line({"cmd": {"auth": {"deviceId": key, **AUTH}}}))
    del key
    f = s.makefile("r", encoding="ascii")
    while True:
        reply = f.readline()
        if not reply:
            sys.exit("Podium closed the connection (wrong key?)")
        if '"status"' in reply:
            if '"ok"' not in reply:
                sys.exit("Podium refused the key")
            break
    print("auth ok", flush=True)
    s.sendall(line({"s": {"meta": [{"nm": n, "ut": u, "sr": 10, "min": lo, "max": hi, "prec": p}
                                   for _, n, u, lo, hi, p in CHANNELS]}}))
    last_lt = [None]

    def heartbeats():
        try:
            for raw in f:
                m = re.search(r'"lt":(\d+)', raw)
                if m:
                    last_lt[0] = int(m.group(1))
        except OSError:
            pass
    threading.Thread(target=heartbeats, daemon=True).start()

    start = time.monotonic(); utc0 = time.time()
    span = min(args.seconds, pts[-1][0] - pts[0][0])
    tick = 0
    while True:
        el = tick / 10
        if el > span:
            break
        p = at(pts, el)
        if p:
            kmh, lat, lon, yaw = p
            s.sendall(line({"s": {"d": row({"Interval": el * 1000, "Utc": (utc0 + el) * 1000, "Lat": lat, "Lon": lon,
                                            "GPSSpeed": kmh, "Speed": kmh, "Yaw": yaw, "GPSFix": 3}), "t": tick}}))
        tick += 1
        if tick % 100 == 0:
            print(f"{el:5.0f} s  sent t={tick - 1}  Podium heartbeat lt={last_lt[0]}", flush=True)
        time.sleep(max(0.0, start + tick / 10 - time.monotonic()))
    time.sleep(6)
    print(f"done: {tick} rows over {span:.0f} s, last heartbeat lt={last_lt[0]}", flush=True)
    s.close()


if __name__ == "__main__":
    main()
