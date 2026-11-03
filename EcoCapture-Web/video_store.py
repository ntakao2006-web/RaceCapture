"""The logger's storage on the UNO Q (~/ecocapture-v2-data), dashcam style: the onboard videos
(video/) and the drive logs (logs/) share the space, and when it runs low the oldest are deleted so
recording never stops and the most recent hours are always there. The recorder
(tools/unoq_overlay_enc/video_store.h) applies the same rules; both are run on the scenarios in
tools/unoq_overlay_enc/testdata/video_store/ (unoq_video_check_procedure.md 5-17, 5-18).

video/ (GoPro style: one recording = a session, split into chapters every 10 minutes):
  <session>_<NN>.ts / .csv   a chapter and its 1 s time sidecar; session = start time YYYYMMDD_HHMMSS
                             (GNSS time once known). Older files are YYYYMMDD_HHMMSS.ts (one per session)
  <chapter>.ts.ok            "size sha256 utc": the PC collector checked its copy against the device
  <session>.keep             protected by the user: never deleted unless collected
  <session>.session          boot_id, start time and clock of the session (written by the recorder)
  .recording                 the recorder's state: boot_id, session, file being written, bt (boot time)
  deleted.log                one line per deleted chapter or log (who, collected or not)
logs/ (EcoCapture):
  LOG_<utc>_<id>.csv with .meta.json, .can.jsonl, .sd-journal.jsonl   one drive log (deleted together; sizes
                             added up, its time is the CSV's)
  LOG_….csv.ok               "csv_size csv_sha256 …": Collect-Logs.cmd checked its copy (EcoCapture wrote it)
  LOG_….csv.keep             protected (the collector app marks the logs of a protected video session)
  .recording                 EcoCapture's state: boot_id, file being written, bt

Deletion order when space is low: 1. collected videos and logs, oldest first; 2. the other videos and
logs, oldest first (the session being recorded too: its oldest chapters go before recording stops).
Never the video or log being written, nor anything protected that is not collected. The recorder
stops (exit 3) only when nothing else is left. The drive logs are also on the shield's SD card
(written by the STM32), so an old log deleted here can still be decoded from the card.
"""
import os
import re
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

CHAPTER_RE = re.compile(r'^(\d{8}_\d{6})_(\d{2,4})\.ts$')
LOG_RE = re.compile(r'^(?:LOG|DEMO)_\d{8}T\d{6}Z_[0-9a-f]{8}\.csv$')
LOG_PARTS = ('', '.meta.json', '.can.jsonl', '.sd-journal.jsonl')  # one log = these files (sizes added up)
ACTIVE_S = 30      # the recorder and EcoCapture rewrite .recording every 5 s while they write
GAP_S = 300        # a recording restarted within this (camera unplugged) continues the session
RECENT_S = 120     # a log written within this is never deleted, whatever .recording says
MIN_FREE_MB = 1024  # both the recorder (OVERLAY_MIN_FREE_MB) and EcoCapture keep this much free
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


class Item:
    kind = ''

    def __init__(self, name, size, mtime_ns):
        self.name, self.size, self.mtime_ns = name, size, mtime_ns
        self.mtime = mtime_ns / 1e9
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


class Chapter(Item):
    kind = 'video'

    def __init__(self, name, size, mtime_ns):
        super().__init__(name, size, mtime_ns)
        self.session, self.number = session_of(name)

    def as_dict(self):
        return {'name': self.name, 'size': self.size, 'mtime': self.mtime, 'session': self.session,
                'chapter': self.number, 'state': self.state}


class Log(Item):
    kind = 'log'

    def as_dict(self):
        return {'name': self.name, 'size': self.size, 'mtime': self.mtime, 'state': self.state}


def _state(text, boot, now_bt):
    """(state, the writer is alive, its file was written within GAP_S) of a .recording"""
    rec = parse_kv(text)
    ok = bool(boot) and rec.get('boot_id') == boot
    try:
        age = now_bt - float(rec.get('bt', 'nan'))
    except ValueError:
        age = float('nan')
    return rec, ok and age < ACTIVE_S, ok and age < GAP_S  # NaN compares false


class Store:
    """A snapshot. entries: {name: (size, mtime in ns)} of every regular file in video/; texts: contents of
    .recording, *.session and *.ts.ok there. log_entries / log_texts: the same for logs/ (.recording,
    *.csv.ok). boot, now_bt: this boot's id and boot time (s); now_wall: the clock (s, for RECENT_S)."""
    def __init__(self, entries, texts, boot, now_bt, log_entries=None, log_texts=None, now_wall=None):
        self.recording, self.alive, recent = _state(texts.get('.recording'), boot, now_bt)
        self.active_file = (self.recording.get('file') or None) if self.alive else None
        self.current_session = (self.recording.get('session') or None) if recent else None
        self.chapters = []
        for name, (size, mtime_ns) in entries.items():
            if not name.endswith('.ts'):
                continue
            c = Chapter(name, size, mtime_ns)
            ok = (texts.get(name + '.ok') or '').split()
            c.active = name == self.active_file
            c.collected = bool(ok) and ok[0] == str(size) and not c.active
            c.current = c.session == self.current_session
            c.kept = c.session + '.keep' in entries
            self.chapters.append(c)
        self.chapters.sort(key=lambda c: (c.mtime_ns, c.name))
        self.sessions = {n[:-8]: parse_kv(t) for n, t in texts.items() if n.endswith('.session')}

        log_entries, log_texts = log_entries or {}, log_texts or {}
        self.log_recording, log_alive, _ = _state(log_texts.get('.recording'), boot, now_bt)
        self.active_log = (self.log_recording.get('file') or None) if log_alive else None
        now_wall = time.time() if now_wall is None else now_wall
        self.logs = []
        for name, (size, mtime_ns) in log_entries.items():
            if not LOG_RE.match(name):
                continue
            parts = [log_entries.get(name + p) for p in LOG_PARTS]
            g = Log(name, sum(p[0] for p in parts if p), mtime_ns)  # ordered by the CSV's time
            ok = (log_texts.get(name + '.ok') or '').split()
            g.active = name == self.active_log or now_wall - mtime_ns / 1e9 < RECENT_S
            g.collected = bool(ok) and ok[0] == str(size) and not g.active
            g.kept = name + '.keep' in log_entries
            self.logs.append(g)
        self.logs.sort(key=lambda g: (g.mtime_ns, g.name))
        self.items = sorted(self.chapters + self.logs, key=lambda i: (i.mtime_ns, i.name))

    def deletion_order(self):
        first = [i for i in self.items if i.collected]
        then = [i for i in self.items if not i.collected and not i.active and not i.kept]
        return first + then

    def deletable_bytes(self):
        return sum(i.size for i in self.deletion_order())

    def minutes_left(self, free_bytes, min_free_mb=None, mbps=None, other_bytes_per_min=0):
        """Minutes the recorder keeps the most recent recording for: the free space plus what may be deleted.
        other_bytes_per_min: what else fills the same storage meanwhile (EcoCapture's log while it records)."""
        try:
            min_free_mb = float(self.recording.get('min_free_mb') or MIN_FREE_MB) if min_free_mb is None else min_free_mb
            mbps = float(self.recording.get('mbps') or MBPS) if mbps is None else mbps
        except ValueError:
            min_free_mb, mbps = MIN_FREE_MB, MBPS
        room = free_bytes - min_free_mb * 1048576 + self.deletable_bytes()
        return max(0.0, room) / (mbps * 1e6 / 8 * 60 * TS_OVERHEAD + other_bytes_per_min)


def _list(folder, small):
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
        if small(name):
            try:
                texts[name] = path.read_text(encoding='utf-8', errors='replace')[:4096]
            except OSError:
                pass
    return entries, texts


def logs_of(folder):
    return Path(folder).parent / 'logs'


def scan(folder, boot=None, now_bt=None, logs=None, now_wall=None):
    """folder: video/; logs: logs/ (default: next to it)"""
    folder = Path(folder)
    entries, texts = _list(folder, lambda n: n == '.recording' or n.endswith('.ts.ok') or n.endswith('.session'))
    log_entries, log_texts = _list(Path(logs) if logs else logs_of(folder),
                                   lambda n: n == '.recording' or n.endswith('.csv.ok'))
    return Store(entries, texts, boot_id() if boot is None else boot, boottime() if now_bt is None else now_bt,
                 log_entries, log_texts, now_wall)


def log_line(by, item, boot=''):
    utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return '\t'.join([utc, by, item.name, str(item.size), 'collected' if item.collected else 'uncollected',
                      (boot or '')[:8]]) + '\n'


def parse_log(text):
    rows = []
    for line in (text or '').splitlines():
        f = line.split('\t')
        if len(f) >= 5:
            rows.append({'utc': f[0], 'by': f[1], 'name': f[2], 'size': int(f[3]) if f[3].isdigit() else 0,
                         'collected': f[4] == 'collected', 'boot': f[5] if len(f) > 5 else '',
                         'kind': 'log' if LOG_RE.match(f[2]) else 'video'})
    return rows


def delete(folder, item, by, boot=None, logs=None):
    """Remove a chapter (with its sidecar and marker; the session's files once it has no chapter) or a log
    (with its metadata, CAN log, SD journal and markers), and write it to deleted.log."""
    folder = Path(folder)
    if item.kind == 'log':
        ldir = Path(logs) if logs else logs_of(folder)
        try:
            (ldir / item.name).unlink()
        except FileNotFoundError:
            return False
        for extra in [item.name + p for p in LOG_PARTS[1:]] + [item.name + '.ok', item.name + '.keep']:
            with suppress(OSError):
                (ldir / extra).unlink()
        with suppress(OSError):
            (ldir.parent / 'sd-journals' / (item.name + '.timestamps.jsonl')).unlink()
    else:
        try:
            (folder / item.name).unlink()
        except FileNotFoundError:
            return False
        for extra in (item.name[:-3] + '.csv', item.name + '.ok'):
            with suppress(OSError):
                (folder / extra).unlink()
    with suppress(OSError), open(folder / LOG_NAME, 'a', encoding='utf-8') as f:
        f.write(log_line(by, item, boot_id() if boot is None else boot))
    if item.kind == 'video':
        try:
            left = any(n.endswith('.ts') and session_of(n)[0] == item.session for n in os.listdir(folder))
        except OSError:
            left = True
        if not left:
            for extra in (item.session + '.session', item.session + '.keep'):
                with suppress(OSError):
                    (folder / extra).unlink()
    return True


def make_room(folder, enough, free, by, boot=None, now_bt=None, logs=None, now_wall=None):
    """Delete in deletion order until free() >= enough. Returns what was deleted."""
    done, failed = [], set()
    while True:
        order = [i for i in scan(folder, boot, now_bt, logs, now_wall).deletion_order() if i.name not in failed]
        if not order or free() >= enough:  # free() only when there is something to delete
            break
        try:
            if delete(folder, order[0], by, boot, logs):
                done.append(order[0])
            else:
                failed.add(order[0].name)
        except OSError:  # cannot be removed: try the next one
            failed.add(order[0].name)
    return done
