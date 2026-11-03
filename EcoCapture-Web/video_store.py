"""Onboard video store (~/ecocapture-v2-data/video): what may be deleted, in which order, and how
long the recorder can still record. The recorder (tools/unoq_overlay_enc/video_store.h) applies the
same rules; both are run on the scenarios in tools/unoq_overlay_enc/testdata/video_store/
(unoq_video_check_procedure.md 5-17).

Files (GoPro style: one recording = a session, split into chapters every 10 minutes):
  <session>_<NN>.ts / .csv   a chapter and its 1 s time sidecar; session = start time YYYYMMDD_HHMMSS
                             (GNSS time once known). Older files are YYYYMMDD_HHMMSS.ts (one per session)
  <chapter>.ts.ok            "size sha256 utc": the PC collector checked its copy against the device
  <session>.keep             protected by the user: never deleted unless collected
  <session>.session          boot_id, start time and clock of the session (written by the recorder)
  .recording                 the recorder's state: boot_id, session, file being written, bt (boot time)
  deleted.log                one line per deleted chapter (who, collected or not)

Deletion order when space is low: 1. collected chapters, oldest first; 2. uncollected chapters of
other sessions that are not protected, oldest first. Never the file being written, the session being
recorded (it continues across a camera reconnect within GAP_S) or a protected session's uncollected
chapters. Then the recorder stops (exit 3) rather than delete them.
"""
import os
import re
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

CHAPTER_RE = re.compile(r'^(\d{8}_\d{6})_(\d{2,4})\.ts$')
LEGACY_RE = re.compile(r'^(\d{8}_\d{6})\.ts$')
ACTIVE_S = 30      # the recorder rewrites .recording every 5 s while it writes
GAP_S = 300        # a recording restarted within this (camera unplugged) continues the session
MIN_FREE_MB = 2048  # the recorder's default floor (OVERLAY_MIN_FREE_MB); it stops below this
MBPS = 10.0        # default bit rate (OVERLAY_BITRATE_MBPS)
TS_OVERHEAD = 1.03  # MPEG-TS packets and tables on top of the H.264 bit rate (measured 770 MB / 10 min at 10 Mbps)
LOG_NAME = 'deleted.log'


def boot_id():
    try:
        return Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    except OSError:
        return ''


def boottime():
    return time.clock_gettime(time.CLOCK_BOOTTIME) if hasattr(time, 'CLOCK_BOOTTIME') else time.monotonic()


def parse_kv(text):
    out = {}
    for line in (text or '').splitlines():
        key, sep, value = line.partition('=')
        if sep:
            out[key.strip()] = value.strip()
    return out


def session_of(name):
    """(session, chapter number) of a .ts name; legacy and other names are their own session (chapter 0)."""
    m = CHAPTER_RE.match(name)
    if m:
        return m.group(1), int(m.group(2))
    return name[:-3], 0


class Chapter:
    def __init__(self, name, size, mtime_ns):
        self.name, self.size, self.mtime_ns = name, size, mtime_ns
        self.mtime = mtime_ns / 1e9
        self.session, self.number = session_of(name)
        self.collected = self.active = self.current = self.kept = False

    @property
    def state(self):
        if self.active:
            return 'recording'
        if self.collected:
            return 'collected'
        if self.current:
            return 'current'
        if self.kept:
            return 'kept'
        return 'uncollected'

    def as_dict(self):
        return {'name': self.name, 'size': self.size, 'mtime': self.mtime, 'session': self.session,
                'chapter': self.number, 'state': self.state}


class Store:
    """A snapshot of the folder. entries: {name: (size, mtime in ns)} of every regular file; texts: contents of
    .recording, *.session and *.ts.ok (small files). boot and now_bt: this boot's id and boot time (s)."""
    def __init__(self, entries, texts, boot, now_bt):
        self.recording = parse_kv(texts.get('.recording'))
        rec_ok = bool(boot) and self.recording.get('boot_id') == boot
        try:
            age = now_bt - float(self.recording.get('bt', 'nan'))
        except ValueError:
            age = float('nan')
        self.alive = rec_ok and age < ACTIVE_S          # NaN compares false
        self.active_file = (self.recording.get('file') or None) if self.alive else None
        self.current_session = (self.recording.get('session') or None) if rec_ok and age < GAP_S else None
        self.chapters = []
        for name, (size, mtime_ns) in entries.items():
            if not name.endswith('.ts'):
                continue
            c = Chapter(name, size, mtime_ns)
            ok = (texts.get(name + '.ok') or '').split()
            c.collected = bool(ok) and ok[0] == str(size) and name != self.active_file
            c.active = name == self.active_file
            c.current = c.session == self.current_session
            c.kept = c.session + '.keep' in entries
            self.chapters.append(c)
        self.chapters.sort(key=lambda c: (c.mtime_ns, c.name))
        self.sessions = {n[:-8]: parse_kv(t) for n, t in texts.items() if n.endswith('.session')}

    def deletion_order(self):
        first = [c for c in self.chapters if c.collected]
        then = [c for c in self.chapters if not c.collected and not c.active and not c.current and not c.kept]
        return first + then

    def deletable_bytes(self):
        return sum(c.size for c in self.deletion_order())

    def minutes_left(self, free_bytes, min_free_mb=None, mbps=None, other_bytes_per_min=0):
        """Minutes the recorder can still record before it stops (free space plus what it may delete).
        other_bytes_per_min: what else fills the same storage meanwhile (EcoCapture's log while it records)."""
        try:
            min_free_mb = float(self.recording.get('min_free_mb') or MIN_FREE_MB) if min_free_mb is None else min_free_mb
            mbps = float(self.recording.get('mbps') or MBPS) if mbps is None else mbps
        except ValueError:
            min_free_mb, mbps = MIN_FREE_MB, MBPS
        room = free_bytes - min_free_mb * 1048576 + self.deletable_bytes()
        return max(0.0, room) / (mbps * 1e6 / 8 * 60 * TS_OVERHEAD + other_bytes_per_min)


SMALL = ('.recording',)


def scan(folder, boot=None, now_bt=None):
    folder = Path(folder)
    entries, texts = {}, {}
    try:
        names = os.listdir(folder)
    except OSError:
        names = []
    for name in names:
        path = folder / name
        try:
            st = path.lstat()
        except OSError:
            continue  # removed while we look
        if not path.is_file() or path.is_symlink():
            continue
        entries[name] = (st.st_size, st.st_mtime_ns)
        if name in SMALL or name.endswith('.ts.ok') or name.endswith('.session'):
            try:
                texts[name] = path.read_text(encoding='utf-8', errors='replace')[:4096]
            except OSError:
                pass
    return Store(entries, texts, boot_id() if boot is None else boot, boottime() if now_bt is None else now_bt)


def log_line(by, chapter, boot=''):
    utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return '\t'.join([utc, by, chapter.name, str(chapter.size), 'collected' if chapter.collected else 'uncollected',
                      (boot or '')[:8]]) + '\n'


def parse_log(text):
    rows = []
    for line in (text or '').splitlines():
        f = line.split('\t')
        if len(f) >= 5:
            rows.append({'utc': f[0], 'by': f[1], 'name': f[2], 'size': int(f[3]) if f[3].isdigit() else 0,
                         'collected': f[4] == 'collected', 'boot': f[5] if len(f) > 5 else ''})
    return rows


def delete(folder, chapter, by, boot=None):
    """Remove a chapter, its sidecar and marker, log it, and drop the session's files once it has no chapter."""
    folder = Path(folder)
    try:
        (folder / chapter.name).unlink()
    except FileNotFoundError:
        return False
    for extra in (chapter.name[:-3] + '.csv', chapter.name + '.ok'):
        with suppress(OSError):
            (folder / extra).unlink()
    with suppress(OSError), open(folder / LOG_NAME, 'a', encoding='utf-8') as f:
        f.write(log_line(by, chapter, boot_id() if boot is None else boot))
    try:
        left = any(n.endswith('.ts') and session_of(n)[0] == chapter.session for n in os.listdir(folder))
    except OSError:
        left = True
    if not left:
        for extra in (chapter.session + '.session', chapter.session + '.keep'):
            with suppress(OSError):
                (folder / extra).unlink()
    return True


def make_room(folder, enough, free, by, boot=None, now_bt=None):
    """Delete in deletion order until free() >= enough. Returns the deleted chapters."""
    done, failed = [], set()
    while True:
        order = [c for c in scan(folder, boot, now_bt).deletion_order() if c.name not in failed]
        if not order or free() >= enough:  # free() only when there is something to delete
            break
        try:
            if delete(folder, order[0], by, boot):
                done.append(order[0])
            else:
                failed.add(order[0].name)
        except OSError:  # cannot be removed: try the next one
            failed.add(order[0].name)
    return done
