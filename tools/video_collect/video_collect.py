"""走行映像の回収アプリ（Collect-Video.cmd）。Ver.2（UNO Q）の焼き込み録画を、ネットを使わずにPCへ吸い出す。

ダブルクリックするとPCのブラウザに画面が開く（PCの中だけで動く。止めるときは黒い窓を閉じる）。
  - 本体とのつなぎ方：普段はUSB直結（adb。ドックを外し本体のUSB-CをPCへ。約37MB/s）。見つからなければ
    予備にテザリング越しのssh（`ssh unoq`。約1.4MB/sなので短い区間だけ）
  - 本体の動画を走行ごと（GoProと同じく1回の録画＝1つの走行、10分ごとの章）に一覧し、状態（未回収・回収済み・
    録画中・今の走行・保護）、本体の空きと、あと何分録れるか（video_store.py の消し方で消せる分も足す）を出す
  - 吸い出すと1本ごとに、本体とPCで中身が同じか（SHA-256）を確かめ、同じなら本体に「回収済み」の印（<章>.ts.ok）を付ける。
    本体は空きが足りなくなると回収済みから消す（録画・EcoCaptureとも。手順書5-17）
  - 「本体から消す」で消せるのは、印があり、PCの写しをもう一度確かめて同じだったものだけ。PCのファイルは自動では消さない
  - 保存先は drive_logs/v2_video/<走行>/（章の .ts・.csv と、続けて再生する <走行>.m3u8）。一覧は index.json
  - 「1本につなげる」：章を画質を落とさずに1つの .ts へ（時刻の .csv もつなげる）
  - 控え：別のフォルダ（外付けのディスク等）か ssh:<ホスト>:<フォルダ>（家の5B等）へもう1部写し、SHA-256で確かめる
  - 本体の走行記録（logs/）も、動画と一緒に古い順に消える側として数え、走行を保護するとその時間の走行記録も保護する
  - SDカード（シールドのSD、PCのカードリーダーに挿す）：確かめる・回収・空にする・フォーマット（sd_card.py）

  python video_collect.py                  # 画面を開く
  python video_collect.py --collect-all    # 画面なしで未回収をすべて吸い出す（Collect-Logs.cmd から使う）
"""
import argparse
import base64
import contextlib
import hashlib
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'EcoCapture-Web'))
sys.path.insert(0, str(REPO / 'tools' / 'collect_logs'))
import video_store as vs  # noqa: E402
import collect_logs  # noqa: E402
from collect_logs import find_adb, load_manifest, save_manifest  # noqa: E402
import sd_card  # noqa: E402

DATA_DIR = '/home/arduino/ecocapture-v2-data'
API_PORT = 8080            # 本体のEcoCapture
JST = timezone(timedelta(hours=9))
MARGIN = 1 << 30           # PCの空きはこれだけ残す
LOG_BYTES_PER_MIN = 5e6    # 走行記録（EcoCaptureのログ）は記録中に約0.3GB/hずつ増える（2026-11-03の実測）
PAGE = Path(__file__).with_name('video_collect.html')

# 本体で動かす一覧のスクリプト。D・LOGS・BOOTF は Link が先頭に付ける
LIST_SCRIPT = r'''
echo "BOOT|$(cat "$BOOTF" 2>/dev/null)"
echo "UP|$(cut -d' ' -f1 /proc/uptime)"
echo "NOW|$(date +%s)"
echo "FREE|$(df -B1 --output=avail "$D/.." 2>/dev/null | tail -1 | tr -d ' ')"
if cd "$LOGS" 2>/dev/null; then
  for f in LOG_* DEMO_*; do [ -f "$f" ] && [ ! -L "$f" ] && stat -c 'G|%n|%s|%.9Y' "$f"; done
  for f in .recording LOG_*.csv.ok DEMO_*.csv.ok; do [ -f "$f" ] && [ ! -L "$f" ] && { echo "U|$f"; head -c 4096 "$f" | sed 's/^/|/'; echo; }; done
fi
cd "$D" 2>/dev/null || exit 0
echo "DIR|"
for f in * .recording; do [ -f "$f" ] && [ ! -L "$f" ] && stat -c 'F|%n|%s|%.9Y' "$f"; done
for f in .recording *.session *.ts.ok; do [ -f "$f" ] && [ ! -L "$f" ] && { echo "T|$f"; head -c 4096 "$f" | sed 's/^/|/'; echo; }; done
for f in *.csv; do [ -f "$f" ] && echo "C|$f|$(sed -n 2p "$f")|$(tail -n 1 "$f")"; done
[ -f deleted.log ] && tail -n 300 deleted.log | sed 's/^/L|/'
exit 0
'''


def q(s):
    return shlex.quote(str(s))


class Link:
    """本体とのつなぎ（USBのadbか、テザリングのssh）。run は sh のスクリプトを本体で動かして標準出力を返す"""
    kind = ''
    speed = 30e6  # 吸い出しの速さの目安（B/s、待ち時間の上限に使う）

    def __init__(self, root=DATA_DIR, boot_file='/proc/sys/kernel/random/boot_id'):
        self.root, self.boot_file = root, boot_file

    @property
    def video_dir(self):
        return self.root + '/video'

    def prelude(self):
        return f'D={q(self.video_dir)}; LOGS={q(self.root + "/logs")}; BOOTF={q(self.boot_file)}\n'

    def command(self, script):
        """本体で script を動かすときの、こちら側のコマンド（base64で渡すので引用符を気にしなくてよい）"""
        return 'echo ' + base64.b64encode((self.prelude() + script).encode()).decode() + ' | base64 -d | sh'

    def run(self, script, timeout=60):
        r = subprocess.run(self.argv(self.command(script)), capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=timeout)
        if r.returncode:
            raise OSError(f'本体でのコマンドが失敗（{r.returncode}）: {(r.stderr or r.stdout).strip()[:300]}')
        return r.stdout

    def pull_argv(self, remote, local):
        raise NotImplementedError

    def label(self):
        return self.kind

    @contextlib.contextmanager
    def api_url(self):
        """本体のEcoCapture（8080番）へPCから届くURL。走行記録の回収（collect_logs.collect_emmc）が使う"""
        port, close = self.open_forward()
        try:
            url = f'http://127.0.0.1:{port}/'
            end = time.time() + 20
            while True:
                try:
                    with urllib.request.urlopen(url + 'api/status', timeout=3):
                        break
                except (OSError, urllib.error.URLError):
                    if time.time() > end:
                        raise OSError('本体のEcoCaptureに届かない（本体が起動しきっていないかもしれない。少し待ってもう一度）')
                    time.sleep(1)
            yield url
        finally:
            close()

    def open_forward(self):
        raise NotImplementedError


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class AdbLink(Link):
    kind = 'USB'
    speed = 30e6

    def __init__(self, adb, serial, **kw):
        super().__init__(**kw)
        self.adb, self.serial = adb, serial

    def argv(self, command):
        return [*self.adb, '-s', self.serial, 'shell', command]

    def pull_argv(self, remote, local):
        return [*self.adb, '-s', self.serial, 'pull', remote, str(local)]

    def label(self):
        return f'USB（{self.serial}）'

    def open_forward(self):
        port = free_port()
        head = [*self.adb, '-s', self.serial, 'forward']
        subprocess.run([*head, f'tcp:{port}', f'tcp:{API_PORT}'], capture_output=True, timeout=15, check=True)
        return port, lambda: subprocess.run([*head, '--remove', f'tcp:{port}'], capture_output=True, timeout=15)


class SshLink(Link):
    kind = 'テザリング'
    speed = 1e6

    def __init__(self, host, **kw):
        super().__init__(**kw)
        self.host = host

    def argv(self, command):
        import unoq_ssh  # 名前が引けないときはIPで探す（tools/collect_logs/unoq_ssh.py）
        return [*unoq_ssh.ssh_cmd(self.host, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8'), command]

    def pull_argv(self, remote, local):
        import unoq_ssh
        return ['scp', '-q', '-o', 'BatchMode=yes', *unoq_ssh.target_opts(self.host), f'{self.host}:{remote}', str(local)]

    def label(self):
        return f'テザリング（ssh {self.host}、遅いので短い区間だけ）'

    def open_forward(self):
        import unoq_ssh
        port = free_port()
        proc = subprocess.Popen(unoq_ssh.ssh_cmd(self.host, '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes', '-N',
                                                 '-L', f'127.0.0.1:{port}:127.0.0.1:{API_PORT}'),
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def close():
            proc.kill()
            proc.wait()
        return port, close


def find_link(ssh_host='unoq', log=print):
    """USBでつないだUNO Q（動画の置き場がある端末）を探す。無ければテザリングのssh"""
    probe = 'test -d "$D/.." && echo EcoLoggerV2'
    adb = find_adb()
    if adb:
        try:
            lines = subprocess.run([adb, 'devices'], capture_output=True, text=True, timeout=15).stdout.splitlines()
        except (OSError, subprocess.SubprocessError):
            lines = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == 'device':
                link = AdbLink([adb], parts[0])
                try:
                    if 'EcoLoggerV2' in link.run(probe, timeout=20):
                        return link
                except (OSError, subprocess.SubprocessError):
                    pass
    if ssh_host:
        link = SshLink(ssh_host)
        try:
            if 'EcoLoggerV2' in link.run(probe, timeout=20):
                return link
        except (OSError, subprocess.SubprocessError):
            pass
    return None


# ---------------------------------------------------------------- 本体の一覧
def parse_utc(text):
    try:
        return datetime.strptime(text[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc).timestamp() + float('0' + text[19:23])
    except (ValueError, TypeError):
        return None


class DeviceState:
    def __init__(self, text):
        self.boot = self.uptime = ''
        self.free = self.now = 0
        self.has_dir = False
        entries, texts, self.csv, self.deleted, self.sizes = {}, {}, {}, [], {}
        log_entries, log_texts = {}, {}
        current = None
        for line in text.splitlines():
            if current is not None and line.startswith('|'):
                current[0][current[1]] += line[1:] + '\n'
                continue
            current = None
            tag, _, rest = line.partition('|')
            if tag == 'BOOT':
                self.boot = rest.strip()
            elif tag == 'UP':
                self.uptime = float(rest or 0)
            elif tag == 'NOW':
                self.now = int(rest or 0)
            elif tag == 'FREE':
                self.free = int(rest) if rest.strip().isdigit() else 0
            elif tag == 'DIR':
                self.has_dir = True
            elif tag == 'F':
                name, size, mtime = rest.rsplit('|', 2)
                entries[name] = (int(size), int(round(float(mtime) * 1e9)))
                self.sizes[name] = int(size)
            elif tag in ('T', 'U'):
                current = (texts if tag == 'T' else log_texts, rest)
                current[0][rest] = ''
            elif tag == 'C':
                name, first, last = rest.split('|', 2)
                f, l = first.split(','), last.split(',')
                self.csv[name[:-4]] = (parse_utc(f[2]) if len(f) > 2 else None, f[3] if len(f) > 3 else '',
                                       parse_utc(l[2]) if len(l) > 2 else None)
            elif tag == 'G':
                name, size, mtime = rest.rsplit('|', 2)
                log_entries[name] = (int(size), int(round(float(mtime) * 1e9)))
            elif tag == 'L':
                self.deleted.extend(vs.parse_log(rest))
        self.store = vs.Store(entries, texts, self.boot, self.uptime or 0, log_entries, log_texts, self.now or None)
        self.chapters = {c.name: c for c in self.store.chapters}
        self.markers = {}
        for name, body in texts.items():
            if name.endswith('.ts.ok'):
                tok = body.split()
                if len(tok) >= 2:
                    self.markers[name[:-3]] = (tok[0], tok[1])

    def marker_sha(self, chapter):
        m = self.markers.get(chapter.name)
        return m[1] if m and m[0] == str(chapter.size) else None

    def minutes_left(self):
        return self.store.minutes_left(self.free, other_bytes_per_min=LOG_BYTES_PER_MIN)


def list_device(link):
    return DeviceState(link.run(LIST_SCRIPT, timeout=60))


# ---------------------------------------------------------------- PCの保存先
def sha256_file(path, cancel=None):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8 << 20):
            if cancel and cancel():
                raise InterruptedError
            h.update(chunk)
    return h.hexdigest()


class PcStore:
    """drive_logs/v2_video/。index.json：章の名前 → 大きさ・SHA-256・置いた場所・控え。drive_logs/collected.json にも書く
    （Collect-Logs.cmd がもう一度取らないように）"""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / 'index.json'
        self.manifest_path = self.root.parent / 'collected.json'
        self.settings_path = self.root / 'settings.json'
        try:
            self.index = json.loads(self.index_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.index = {}
        try:
            self.settings = json.loads(self.settings_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.settings = {}

    def save(self):
        temp = self.index_path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.index, ensure_ascii=False, indent=1), encoding='utf-8')
        temp.replace(self.index_path)

    def save_settings(self):
        self.settings_path.write_text(json.dumps(self.settings, ensure_ascii=False, indent=1), encoding='utf-8')

    def path(self, entry):
        return self.root / entry['path']

    def find(self, name, size, sha=None):
        """PCにある写し（名前と大きさ、または中身のSHA-256が同じもの。GNSSで名前が変わった章も見つける）"""
        e = self.index.get(name)
        if e and e['size'] == size and (sha is None or e['sha256'] == sha):
            return e
        if sha:
            return next((e for e in self.index.values() if e['sha256'] == sha and e['size'] == size), None)
        return None

    def present(self, entry):
        p = self.path(entry)
        return p.is_file() and p.stat().st_size == entry['size']

    def older_copy(self, name, size):
        """Collect-Logs.cmd が前に run フォルダへ取った写し（collected.json）"""
        rel = load_manifest(self.manifest_path).get(f'v2_video/{name}/{size}')
        if rel:
            p = self.root.parent / rel.replace('\\', '/')
            if p.is_file() and p.stat().st_size == size:
                return p
        return None

    def add(self, name, size, sha, path, session):
        self.index[name] = {'size': size, 'sha256': sha, 'path': path.relative_to(self.root).as_posix(), 'session': session,
                            'collected_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                            'backup': self.index.get(name, {}).get('backup', {})}
        self.save()
        manifest = load_manifest(self.manifest_path)
        manifest[f'v2_video/{name}/{size}'] = str(path.relative_to(self.root.parent))
        save_manifest(self.manifest_path, manifest)


# ---------------------------------------------------------------- 走行ごとの見え方
def fmt_jst(t, with_date=True):
    if t is None:
        return '?'
    return datetime.fromtimestamp(t, JST).strftime('%m/%d %H:%M' if with_date else '%H:%M')


def group_sessions(state):
    """走行ごとにまとめる。前の形（1本ずつ別の名前）の動画は、時刻が続いているものを1つにまとめて見せる"""
    by = {}
    for c in state.store.chapters:
        by.setdefault(c.session, []).append(c)
    groups = []
    for sid in sorted(by, key=lambda s: (state.csv.get(by[s][0].name[:-3], (None,))[0] or by[s][0].mtime, s)):
        chs = sorted(by[sid], key=lambda c: (c.number, c.name))
        legacy = chs[0].number == 0
        prev = groups[-1] if groups else None
        if legacy and prev and prev['legacy']:
            last = state.csv.get(prev['chapters'][-1].name[:-3], (None, '', None))[2]
            first = state.csv.get(chs[0].name[:-3], (None, '', None))[0]
            if last is not None and first is not None and 0 <= first - last <= 5:
                prev['chapters'] += chs
                prev['members'].append(sid)
                continue
        groups.append({'id': sid, 'members': [sid], 'legacy': legacy, 'chapters': chs})
    return groups


def log_start(name):
    m = re.match(r'^(?:LOG|DEMO)_(\d{8}T\d{6})Z_', name)
    return datetime.strptime(m.group(1), '%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc).timestamp() if m else None


def logs_during(state, start, end):
    """その時間に記録していた走行記録の名前（保護するときに一緒に保護する）"""
    if start is None or end is None:
        return []
    return [g.name for g in state.store.logs if log_start(g.name) is not None and log_start(g.name) <= end and g.mtime >= start]


def describe(state, pc):
    """画面に出す一覧"""
    out = []
    deleted = {r['name'] for r in state.deleted}
    for g in group_sessions(state):
        chapters, total, counts = [], 0, {}
        for c in g['chapters']:
            sha = state.marker_sha(c)
            entry = pc.find(c.name, c.size, sha) if pc else None
            on_pc = bool(entry and pc.present(entry))
            st = c.state
            if st == 'collected' and not on_pc:
                st = 'collected_elsewhere'  # 印はあるがこのPCには無い（別のPCで回収した等）
            elif st in ('uncollected', 'current', 'kept') and on_pc:
                st = 'on_pc_unmarked'  # PCにはあるが本体に印が無い（吸い出すと確かめて印を付ける）
            counts[st] = counts.get(st, 0) + 1
            total += c.size
            t = state.csv.get(c.name[:-3], (None, '', None))
            chapters.append({**c.as_dict(), 'state': st, 'on_pc': on_pc, 'start': fmt_jst(t[0]), 'end': fmt_jst(t[2], False),
                             'seconds': (t[2] - t[0] + 1) if t[0] is not None and t[2] is not None else None})
        first = state.csv.get(g['chapters'][0].name[:-3], (None, '', None))
        last = state.csv.get(g['chapters'][-1].name[:-3], (None, '', None))
        missing = []
        if not g['legacy']:
            have = {c.number for c in g['chapters']}
            missing = [n for n in range(1, max(have) + 1) if n not in have]
        out.append({
            'id': g['id'], 'members': g['members'], 'legacy': g['legacy'],
            'title': f'{fmt_jst(first[0])}〜{fmt_jst(last[2], False)}', 'clock': first[1],
            'seconds': sum(ch['seconds'] or 0 for ch in chapters), 'bytes': total, 'counts': counts,
            'kept': any(c.kept for c in g['chapters']), 'current': any(c.current for c in g['chapters']),
            'logs': logs_during(state, first[0], last[2]),
            'chapters': chapters,
            'missing': [{'number': n, 'deleted': any(re.fullmatch(re.escape(g['id']) + rf'_0*{n}\.ts', d) for d in deleted)}
                        for n in missing],
            'pc_folder': str(pc.root / g['id']) if pc else '',
        })
    return out


# ---------------------------------------------------------------- 仕事（吸い出し・消す・保護・つなげる・控え）
class Job:
    def __init__(self, name, total=0):
        self.name, self.total, self.done = name, total, 0
        self.file, self.started, self.running, self.cancel = '', time.time(), True, False
        self.messages, self.problems = [], []
        self.step, self.result = '', None  # 「回収する」の今の段と、終わったときのまとめ

    def log(self, text):
        self.messages.append(f'{datetime.now():%H:%M:%S} {text}')
        del self.messages[:-200]

    def snapshot(self):
        el = time.time() - self.started
        rate = self.done / el if el > 1 and self.done else 0
        return {'name': self.name, 'running': self.running, 'done': self.done, 'total': self.total, 'file': self.file,
                'rate': rate, 'eta': (self.total - self.done) / rate if rate else None, 'messages': self.messages[-40:],
                'problems': self.problems, 'step': self.step, 'result': self.result}


def pull(link, remote, dest, size, job, base_done):
    """remote を dest（.partで受けてから置き換える）へ。進み具合は受けているファイルの大きさで見る"""
    part = dest.with_name(dest.name + '.part')
    part.unlink(missing_ok=True)
    err = tempfile.TemporaryFile()
    proc = subprocess.Popen(link.pull_argv(remote, part), stdout=subprocess.DEVNULL, stderr=err)
    limit = time.time() + 300 + size / (link.speed / 4)
    try:
        while proc.poll() is None:
            time.sleep(0.3)
            job.done = base_done + (part.stat().st_size if part.exists() else 0)
            if job.cancel or time.time() > limit:
                proc.kill()
                proc.wait()
                raise InterruptedError if job.cancel else TimeoutError(f'{remote} の吸い出しが終わらない')
        if proc.returncode:
            err.seek(0)
            raise OSError(f'{remote} を吸い出せない: {err.read().decode("utf-8", "replace").strip()[:200]}')
        got = part.stat().st_size if part.exists() else -1
        if got != size:
            raise OSError(f'{remote} の大きさが合わない（本体 {size}、PC {got}）')
        return part
    except BaseException:
        if proc.poll() is None:
            proc.kill()
        part.unlink(missing_ok=True)
        raise
    finally:
        err.close()


def device_sha(link, name):
    out = link.run(f'cd "$D" && sha256sum -- {q(name)}', timeout=600)
    return out.split()[0] if out.split() else ''


def write_marker(link, name, size, sha):
    utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    link.run(f'cd "$D" && [ "$(stat -c %s -- {q(name)})" = {size} ] && printf "%s %s %s\\n" {size} {sha} {utc} > {q(name + ".ok.tmp")}'
             f' && mv -- {q(name + ".ok.tmp")} {q(name + ".ok")}', timeout=30)


def write_playlist(folder, session):
    names = sorted(p.name for p in folder.glob('*.ts') if not p.name.endswith('_all.ts'))
    if names:
        (folder / f'{session}.m3u8').write_text('#EXTM3U\n' + ''.join(f'{n}\n' for n in names), encoding='utf-8')


def collect(link, state, pc, group_ids, job):
    """選んだ走行（Noneはすべて）の未回収の章を吸い出し、確かめて印を付ける。印があってもこのPCに無いものも取る"""
    todo = []
    for g in group_sessions(state):
        if group_ids is not None and g['id'] not in group_ids:
            continue
        for c in g['chapters']:
            if c.active:
                job.log(f'{c.name} は録画中なので取らない')
                continue
            entry = pc.find(c.name, c.size, state.marker_sha(c))
            if entry and pc.present(entry) and c.collected:
                continue
            todo.append((g['id'], c, entry if entry and pc.present(entry) else None))
    need = sum(c.size for _, c, e in todo if not e)
    job.total = need
    free = shutil.disk_usage(pc.root).free
    if need + MARGIN > free:
        raise OSError(f'PCの空きが足りない（要る {need / 1e9:.1f}GB＋余裕1GB、空き {free / 1e9:.1f}GB）')
    done = 0
    for gid, c, entry in todo:
        if job.cancel:
            raise InterruptedError
        job.file = c.name
        folder = pc.root / gid
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / c.name
        csv = c.name[:-3] + '.csv'
        old = None if entry else pc.older_copy(c.name, c.size)
        if entry or old:  # PCにはある：本体の中身と同じか確かめて印だけ付ける（GNSSで名前が変わった章・前に Collect-Logs.cmd で取ったもの）
            src = pc.path(entry) if entry else old
            job.log(f'{c.name}：PCにある写し（{src}）と本体を比べる')
            sha_pc = entry['sha256'] if entry else sha256_file(old, lambda: job.cancel)
            if device_sha(link, c.name) != sha_pc:
                raise OSError(f'{c.name}：本体とPCで中身が違う')
            if old:  # run フォルダの写しはそのまま残し、走行のフォルダへも写す
                shutil.copy2(old, dest)
                if old.with_suffix('.csv').is_file():
                    shutil.copy2(old.with_suffix('.csv'), folder / csv)
            else:
                dest = src
        else:
            job.log(f'{c.name}（{c.size / 1e6:.0f}MB）を吸い出す')
            part = pull(link, f'{link.video_dir}/{c.name}', dest, c.size, job, done)
            result = {}
            t = threading.Thread(target=lambda: result.setdefault('sha', device_sha(link, c.name)))
            t.start()
            try:
                sha_pc = sha256_file(part, lambda: job.cancel)
            finally:
                t.join()
            if result.get('sha') != sha_pc:
                part.unlink(missing_ok=True)
                raise OSError(f'{c.name}：本体とPCで中身が違う（もう一度吸い出す）')
            part.replace(dest)
            done += c.size
            if csv in state.sizes:
                try:
                    pull(link, f'{link.video_dir}/{csv}', folder / csv, state.sizes[csv], job, done).replace(folder / csv)
                except (OSError, TimeoutError) as exc:
                    job.problems.append(f'{csv}：{exc}')
        pc.add(c.name, c.size, sha_pc, dest, gid)
        write_marker(link, c.name, c.size, sha_pc)
        write_playlist(folder, gid)
        job.log(f'{c.name}：本体とPCで同じ（SHA-256 {sha_pc[:12]}…）。本体に回収済みの印を付けた')
    if pc.settings.get('backup'):
        backup(pc, job)
    return len(todo)


def delete_on_device(link, state, pc, group_ids, job):
    """回収済みの印があり、PCの写しをもう一度確かめて同じだった章だけを本体から消す（deleted.log に by=pc で書く）"""
    picks = []
    for g in group_sessions(state):
        if group_ids is not None and g['id'] not in group_ids:
            continue
        for c in g['chapters']:
            sha = state.marker_sha(c)
            entry = pc.find(c.name, c.size, sha) if sha else None
            if c.collected and entry and pc.present(entry):
                picks.append((g, c, entry))
    job.total = sum(c.size for _, c, _ in picks)
    ok, sessions = [], set()
    for g, c, entry in picks:
        if job.cancel:
            raise InterruptedError
        job.file = c.name
        if sha256_file(pc.path(entry), lambda: job.cancel) != entry['sha256']:
            job.problems.append(f'{c.name}：PCの写しが変わっている（消さない）')
            continue
        ok.append(c)
        sessions.add(c.session)
        job.done += c.size
    if not ok:
        return 0
    lines = ['cd "$D" || exit 1', 'B=$(cut -c1-8 "$BOOTF" 2>/dev/null)',
             'del() { [ "$(stat -c %s -- "$1" 2>/dev/null)" = "$2" ] && [ -f "$1.ok" ] || { echo "SKIP|$1"; return; }; '
             'rm -f -- "$1" "${1%.ts}.csv" "$1.ok" && printf "%s\\tpc\\t%s\\t%s\\tcollected\\t%s\\n" '
             '"$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" "$B" >> deleted.log && echo "DEL|$1"; }']
    lines += [f'del {q(c.name)} {c.size}' for c in ok]
    for s in sorted(sessions):  # その走行の章が無くなったら .session・.keep も消す
        lines.append(f'n=0; for f in {q(s)}_*.ts {q(s)}.ts; do [ -e "$f" ] && n=1; done; '
                     f'[ $n = 1 ] || rm -f -- {q(s + ".session")} {q(s + ".keep")}')
    out = link.run('\n'.join(lines) + '\n', timeout=120)
    removed = [l[4:] for l in out.splitlines() if l.startswith('DEL|')]
    for l in out.splitlines():
        if l.startswith('SKIP|'):
            job.problems.append(f'{l[5:]}：本体で大きさか印が変わっていたので消さなかった')
    job.log(f'本体から {len(removed)} 本消した（{sum(c.size for c in ok if c.name in removed) / 1e9:.1f}GB）')
    return len(removed)


def set_keep(link, members, on, logs=()):
    """走行（とその時間の走行記録）を保護する・やめる"""
    cmds = ['cd "$D" || exit 1'] + [(f': > {q(s + ".keep")}' if on else f'rm -f -- {q(s + ".keep")}') for s in members]
    cmds += [(f': > "$LOGS"/{q(n + ".keep")}' if on else f'rm -f -- "$LOGS"/{q(n + ".keep")}') for n in logs]
    link.run('\n'.join(cmds) + '\n', timeout=30)


# MPEG-TSの映像の最初と最後のPTS（90kHz）。録画は188バイトのパケットだけを書く（overlay_rec.c の ts_frame）
def _pts_in(buf):
    found = []
    for i in range(0, len(buf) - 187, 188):
        p = buf[i:i + 188]
        if p[0] != 0x47 or not p[1] & 0x40:
            continue
        off = 4 + (1 + p[4] if p[3] & 0x20 else 0)
        if off + 14 > 188 or p[off:off + 3] != b'\x00\x00\x01' or p[off + 3] != 0xe0 or not p[off + 7] & 0x80:
            continue
        b = p[off + 9:off + 14]
        found.append((b[0] >> 1 & 7) << 30 | b[1] << 22 | (b[2] >> 1) << 15 | b[3] << 7 | b[4] >> 1)
    return found


def ts_pts_range(path):
    size = path.stat().st_size
    with open(path, 'rb') as f:
        head = _pts_in(f.read(1 << 18))
        f.seek(max(0, size - (2 << 20)) // 188 * 188)
        tail = _pts_in(f.read())
    return (head[0], tail[-1]) if head and tail else (None, None)


def join_session(pc, group_id, job):
    """走行の章を1つの .ts へ（画質はそのまま、つなぐだけ）。時刻の .csv も、つないだ動画の中の秒に直してつなぐ"""
    folder = pc.root / group_id
    parts = sorted(p for p in folder.glob('*.ts') if not p.name.endswith('_all.ts'))
    if not parts:
        raise OSError('PCにこの走行の章が無い（先に吸い出す）')
    total = sum(p.stat().st_size for p in parts)
    if total + MARGIN > shutil.disk_usage(folder).free:
        raise OSError('PCの空きが足りない')
    job.total = total
    out_ts, out_csv = folder / f'{group_id}_all.ts', folder / f'{group_id}_all.csv'
    tmp = out_ts.with_name(out_ts.name + '.part')
    rows, offset, base_pts, base_off, prev_end, jumps = [], 0.0, None, 0.0, None, 0
    with open(tmp, 'wb') as w:
        for k, p in enumerate(parts):
            first, last = ts_pts_range(p)
            if first is not None:
                if base_pts is None or prev_end is None or first <= prev_end:  # 録画をやり直した所（PTSが戻る）
                    if base_pts is not None:
                        jumps += 1
                    base_pts, base_off = first, offset
                offset = base_off + (first - base_pts) / 90000
                prev_end = last
            csv = p.with_suffix('.csv')
            if csv.is_file():
                for line in csv.read_text(encoding='utf-8').splitlines()[1:]:
                    f = line.split(',')
                    if len(f) >= 5:
                        rows.append(f'{p.stem},{f[0]},{offset + float(f[1]):.3f},{f[2]},{f[3]},{f[4]}')
            with open(p, 'rb') as r:
                while chunk := r.read(8 << 20):
                    if job.cancel:
                        raise InterruptedError
                    w.write(chunk)
                    job.done += len(chunk)
            if last is not None and first is not None:
                offset += (last - first) / 90000 + 1 / 30
    tmp.replace(out_ts)
    out_csv.write_text('chapter,frame,video_s,utc,clock,host_utc\n' + ''.join(r + '\n' for r in rows), encoding='utf-8')
    job.log(f'{out_ts.name}（{len(parts)}本、{total / 1e9:.1f}GB）にした' +
            (f'。録画をやり直した所が{jumps}か所あり、再生ソフトによってはそこで時間の表示が飛ぶ' if jumps else ''))
    return out_ts


def backup(pc, job):
    """控え（別のフォルダか ssh:<ホスト>:<フォルダ>）へまだ写していない章を写し、SHA-256で確かめる"""
    target = (pc.settings.get('backup') or '').strip()
    if not target:
        raise OSError('控えの写し先が決まっていない')
    todo = [(n, e) for n, e in sorted(pc.index.items()) if target not in e.get('backup', {}) and pc.present(e)]
    job.total, job.done = sum(e['size'] for _, e in todo), 0
    m = re.fullmatch(r'ssh:([^:]+):(.+)', target)
    if not m:
        try:
            free = shutil.disk_usage(Path(target).anchor or target).free
        except OSError:
            raise OSError(f'控えの写し先 {target} が見つからない（ディスクをつないだか）')
        if job.total + MARGIN > free:
            raise OSError(f'控えの写し先の空きが足りない（要る {job.total / 1e9:.1f}GB、空き {free / 1e9:.1f}GB）')
    for name, e in todo:
        if job.cancel:
            raise InterruptedError
        job.file = name
        src = pc.path(e)
        if m:
            host, base = m.groups()
            rdir = f'{base.rstrip("/")}/{e["session"]}'
            subprocess.run(['ssh', '-o', 'BatchMode=yes', host, f'mkdir -p {q(rdir)}'], check=True, capture_output=True, timeout=60)
            subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', str(src), f'{host}:{rdir}/{name}.part'], check=True,
                           capture_output=True, timeout=300 + e['size'] / 2e6)
            out = subprocess.run(['ssh', '-o', 'BatchMode=yes', host, f'sha256sum {q(rdir + "/" + name + ".part")}'],
                                 check=True, capture_output=True, text=True, timeout=600).stdout.split()
            if not out or out[0] != e['sha256']:
                raise OSError(f'{name}：控えの中身が違う')
            subprocess.run(['ssh', '-o', 'BatchMode=yes', host, f'mv {q(rdir + "/" + name + ".part")} {q(rdir + "/" + name)}'],
                           check=True, capture_output=True, timeout=60)
            csv = src.with_suffix('.csv')
            if csv.is_file():
                subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', str(csv), f'{host}:{rdir}/{csv.name}'], capture_output=True, timeout=120)
        else:
            dest = Path(target) / e['path']
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_name(dest.name + '.part')
            shutil.copyfile(src, part)
            if sha256_file(part, lambda: job.cancel) != e['sha256']:
                part.unlink(missing_ok=True)
                raise OSError(f'{name}：控えの中身が違う')
            part.replace(dest)
            csv = src.with_suffix('.csv')
            if csv.is_file():
                shutil.copyfile(csv, dest.with_suffix('.csv'))
            write_playlist(dest.parent, e['session'])
        e.setdefault('backup', {})[target] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        pc.save()
        job.done += e['size']
    job.log(f'控え（{target}）へ {len(todo)} 本写して確かめた')
    return len(todo)


def collect_everything(link, pc, job, sd_drives=None):
    """「回収する」ボタン：つながっているものから、まだPCに無いものをすべて取る。どれも消さない。
      - 本体の走行記録（eMMC）：Collect-Logs.cmd と同じ（EcoCaptureのAPIから。取ったら本体に回収済みの印）
      - 本体の動画：USBのときだけ（テザリングでは1本約9分かかる）。回収済みの印を付け、本体が空きの要るときに消す
      - PCに挿したSDカード（Ver.2のEL*.BIN、Ver.1のlogs）：写してSHA-256で確かめる。カードからは消さない
    本体の走行記録とSDは同じ run フォルダ（drive_logs/<日付>/runNN_<時刻>/）へ。1つ失敗しても残りは続ける"""
    root = pc.root.parent  # drive_logs
    run = collect_logs.Run(root)
    result = {'logs': 0, 'videos': 0, 'sd': 0, 'folder': '', 'video_folder': str(pc.root), 'notes': []}

    def step(name, fn):
        job.step, job.total, job.done, job.file = name, 0, 0, ''
        job.log(f'── {name}')
        try:
            fn()
        except InterruptedError:
            raise
        except Exception as exc:  # 次の段へ進む（画面の【要確認】に出す）
            job.problems.append(f'{name}：{exc}')
            job.log(f'{name}：失敗 {exc}')

    def logs():
        manifest_path = root / 'collected.json'
        manifest, before = load_manifest(manifest_path), run.count
        try:
            with link.api_url() as url:
                collect_logs.collect_emmc(run, manifest, url, job.log)
        finally:
            save_manifest(manifest_path, {**load_manifest(manifest_path), **manifest})
            result['logs'] = run.count - before

    def videos():
        result['videos'] = collect(link, list_device(link), pc, None, job)

    def card(drive):
        result['sd'] += sd_card.collect(drive, root, job, run=run)

    def old_cards(sources):
        manifest_path = root / 'collected.json'
        manifest, before = load_manifest(manifest_path), run.count
        try:
            for _, drive, files in sources:
                collect_logs.collect_sd(run, manifest, 'v1_sd', files, job.log)
        finally:
            save_manifest(manifest_path, {**load_manifest(manifest_path), **manifest})
            result['sd'] += run.count - before

    if link:
        step('本体の走行記録', logs)
        if link.kind == 'USB':
            step('本体の動画', videos)
        else:
            result['notes'].append('動画はUSBのときだけ取る（テザリングでは遅すぎる）。今回は取っていない')
    else:
        result['notes'].append('本体がつながっていないので、本体の走行記録と動画は取っていない')
    cards = [c for c in sd_card.find_cards(sd_drives) if c['files']]
    for c in cards:
        step(f'SDカード {c["drive"]}', lambda d=c['drive']: card(d))
    drives = sd_drives if sd_drives is not None else collect_logs.candidate_drives()
    v1 = [s for s in collect_logs.find_sources(drives) if s[0] == 'v1_sd']
    if v1:
        step('Ver.1のSDカード', lambda: old_cards(v1))
    if not cards and not v1:
        result['notes'].append('SDカードは挿さっていなかった')
    job.step = ''
    result['folder'] = str(run.path) if run.path.is_dir() else ''
    job.result = result
    job.log(f'回収した：走行記録 {result["logs"]} 本・動画 {result["videos"]} 本・SDカード {result["sd"]} 本')
    return result


def collect_phones(pc, job):
    """スマホ（Androidロガー、USBの「ファイル転送」）の EL_*.csv を取る（Collect-Logs.cmd と同じ）"""
    root = pc.root.parent
    run = collect_logs.Run(root)
    manifest_path = root / 'collected.json'
    manifest = load_manifest(manifest_path)
    try:
        with tempfile.TemporaryDirectory() as staging:
            phones = collect_logs.stage_phones(Path(staging), job.log)
            if not phones:
                job.log('スマホのログは見つからなかった（USBを「ファイル転送」にしてつなぐ）')
            for device, files in phones:
                collect_logs.collect_sd(run, manifest, 'phone', files, job.log)
    finally:
        save_manifest(manifest_path, {**load_manifest(manifest_path), **manifest})
    job.result = {'logs': 0, 'videos': 0, 'sd': 0, 'phone': run.count, 'folder': str(run.path) if run.count else '',
                  'video_folder': str(pc.root), 'notes': []}
    job.log(f'スマホから {run.count} 本回収した')
    return run.count


# ---------------------------------------------------------------- 画面（127.0.0.1だけ）
class App:
    def __init__(self, pc, ssh_host='unoq', link=None, sd_drives=None):
        self.pc, self.ssh_host, self.sd_drives = pc, ssh_host, sd_drives
        self.sd = {'cards': [], 'checked': {}}  # PCに挿したSDカード、確かめた結果
        self.link, self.state, self.error, self.job, self.listed_at = link, None, '', None, 0
        self.lock = threading.Lock()

    def refresh(self):
        try:
            if self.link is None:
                self.link = find_link(self.ssh_host)
            self.state = list_device(self.link) if self.link else None
            self.error = '' if self.link else 'UNO Qが見つからない（ドックを外し、本体のUSB-CをPCへ直接つないで起動する）'
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            self.link, self.state, self.error = None, None, f'本体を読めない: {exc}'
        self.listed_at = time.time()

    def snapshot(self):
        with self.lock:
            st, pc = self.state, self.pc
            free_pc = shutil.disk_usage(pc.root).free
            device = None
            if st:
                device = {'link': self.link.label(), 'kind': self.link.kind, 'free': st.free, 'minutes_left': round(st.minutes_left()),
                          'videos_uncollected': sum(1 for c in st.store.chapters if not c.active and not
                                                    ((e := pc.find(c.name, c.size, st.marker_sha(c))) and pc.present(e) and c.collected)),
                          'recording': st.store.alive, 'recording_file': st.store.active_file, 'current_session': st.store.current_session,
                          'logs_bytes': sum(g.size for g in st.store.logs), 'logs_files': len(st.store.logs),
                          'logs_collected': sum(1 for g in st.store.logs if g.collected), 'logs_recording': st.store.active_log,
                          'deleted': list(reversed(st.deleted))[:100], 'has_dir': st.has_dir}
            return {'device': device, 'error': self.error, 'sessions': describe(st, pc) if st else [],
                    'pc': {'root': str(pc.root), 'free': free_pc, 'backup': pc.settings.get('backup', ''),
                           'not_backed_up': sum(1 for e in pc.index.values() if pc.settings.get('backup') and
                                                pc.settings['backup'] not in e.get('backup', {}))},
                    'job': self.job.snapshot() if self.job else None, 'listed_at': self.listed_at, 'sd': self.sd}

    def find_sd(self):
        self.sd['cards'] = sd_card.find_cards(self.sd_drives)
        drives = {c['drive'] for c in self.sd['cards']}
        self.sd['checked'] = {d: r for d, r in self.sd['checked'].items() if d in drives}

    def sd_job(self, name, drive, fn):
        """SDの作業。終わったらカードを探し直し、確かめ直す"""
        def work(job):
            try:
                fn(job)
            finally:
                if Path(drive.rstrip('\\') + '\\').exists():
                    job.total = job.done = 0
                    self.sd['checked'][drive] = sd_card.check(drive, self.pc.root.parent, job)
                self.find_sd()
        if drive not in {c['drive'] for c in self.sd['cards']}:
            raise RuntimeError('そのSDカードが見つからない（「カードを探す」を押す）')
        self.start(name, work)

    def start(self, name, fn):
        with self.lock:
            if self.job and self.job.running:
                raise RuntimeError('ほかの作業の途中')
            job = self.job = Job(name)

        def work():
            try:
                fn(job)
                job.log(f'{name}：終わり')
            except InterruptedError:
                job.log(f'{name}：止めた')
            except Exception as exc:  # 画面に出す（窓にも）
                job.problems.append(str(exc))
                job.log(f'{name}：失敗 {exc}')
            finally:
                with self.lock:
                    self.refresh()
                job.running = False
        threading.Thread(target=work, daemon=True).start()

    def need_device(self):
        if not self.state:
            raise RuntimeError('本体がつながっていない')
        return self.link, self.state

    def action(self, path, body):
        groups = body.get('sessions')
        if path == '/api/everything':
            def everything(job):
                job.step = '本体とSDカードを探す'
                with self.lock:  # 押す直前につないだ本体・挿したカードも拾う
                    self.link = None
                    self.refresh()
                    self.find_sd()
                    link = self.link if self.state else None
                collect_everything(link, self.pc, job, self.sd_drives)
            self.start('回収', everything)
        elif path == '/api/phone':
            self.start('スマホから回収', lambda job: collect_phones(self.pc, job))
        elif path == '/api/refresh':
            with self.lock:
                self.link = None
                self.refresh()
        elif path == '/api/collect':
            link, state = self.need_device()
            self.start('吸い出し', lambda job: collect(link, state, self.pc, groups, job))
        elif path == '/api/delete':
            link, state = self.need_device()
            self.start('本体から消す', lambda job: delete_on_device(link, state, self.pc, groups, job))
        elif path == '/api/keep':
            link, state = self.need_device()
            g = next(s for s in describe(state, self.pc) if s['id'] == body['session'])
            with self.lock:
                set_keep(link, g['members'], bool(body.get('on')), g['logs'])
                self.refresh()
        elif path == '/api/join':
            self.start('1本につなげる', lambda job: join_session(self.pc, body['session'], job))
        elif path == '/api/backup':
            self.start('控えへ写す', lambda job: backup(self.pc, job))
        elif path == '/api/settings':
            with self.lock:
                self.pc.settings['backup'] = str(body.get('backup', '')).strip()
                self.pc.save_settings()
        elif path == '/api/cancel':
            if self.job:
                self.job.cancel = True
        elif path == '/api/sd/find':
            self.find_sd()
        elif path == '/api/sd/check':
            self.sd_job('SDを確かめる', body['drive'], lambda job: None)
        elif path == '/api/sd/collect':
            self.sd_job('SDから回収', body['drive'], lambda job: sd_card.collect(body['drive'], self.pc.root.parent, job))
        elif path == '/api/sd/empty':
            self.sd_job('SDを空にする', body['drive'], lambda job: sd_card.empty(body['drive'], self.pc.root.parent, job))
        elif path == '/api/sd/format':
            self.sd_job('SDをフォーマット', body['drive'], lambda job: sd_card.format_card(body['drive'], self.pc.root.parent, job))
        elif path == '/api/open':
            folder = self.pc.root / body.get('session', '')
            folder = folder if folder.is_dir() else self.pc.root
            if body.get('path'):  # 「回収する」の保存先（drive_logs の中だけ）
                p = Path(body['path']).resolve()
                if p.is_dir() and p.is_relative_to(self.pc.root.parent.resolve()):
                    folder = p
            if hasattr(os, 'startfile'):
                os.startfile(folder)
        else:
            raise KeyError(path)


def make_server(app, port):
    class Handler(BaseHTTPRequestHandler):
        def send(self, code, body, ctype='application/json; charset=utf-8'):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def host_ok(self):
            return self.headers.get('Host', '') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def do_GET(self):
            if not self.host_ok():
                return self.send(403, {'error': 'host'})
            if self.path == '/':
                return self.send(200, PAGE.read_bytes(), 'text/html; charset=utf-8')
            if self.path == '/api/state':
                return self.send(200, app.snapshot())
            self.send(404, {'error': 'not found'})

        def do_POST(self):
            # ほかのページから押されないように、この画面だけが付ける印と、127.0.0.1あての名前を確かめる
            raw = self.rfile.read(min(int(self.headers.get('Content-Length') or 0), 1 << 20))
            if not self.host_ok() or self.headers.get('X-Video-Collect') != '1':
                return self.send(403, {'error': '操作の印が無い'})
            try:
                body = json.loads(raw or b'{}')
                app.action(self.path, body)
                self.send(200, {'ok': True})
            except KeyError:
                self.send(404, {'error': 'not found'})
            except (RuntimeError, OSError, StopIteration, ValueError) as exc:
                self.send(409, {'error': str(exc) or type(exc).__name__})

        def log_message(self, *args):
            pass

    try:
        return OnlyServer(('127.0.0.1', port), Handler)
    except OSError:
        return OnlyServer(('127.0.0.1', 0), Handler)


class OnlyServer(ThreadingHTTPServer):
    """同じ番号で2つ目が待てないようにする。Windowsは「使い回し可」にすると、
    もう開いている回収アプリと同じ番号で2つ目も待ててしまい、画面の読み込みやボタンが
    回収中でない方へ届く（2026-11-11、SDの回収中に2つ目を開いて起きた）"""
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def running_app(port):
    """この番号で回収アプリがもう開いていれば、そのURL"""
    url = f'http://127.0.0.1:{port}/'
    try:
        with urllib.request.urlopen(url + 'api/state', timeout=3) as r:
            state = json.loads(r.read())
    except (OSError, ValueError):
        return None
    return url if isinstance(state, dict) and 'job' in state and 'sd' in state else None


def serve(app, port, open_browser=True):
    server = make_server(app, port)
    url = f'http://127.0.0.1:{server.server_port}/'
    print(f'回収アプリ: {url} （止めるときはこの窓を閉じる）')
    if open_browser:
        webbrowser.open(url)
    server.serve_forever()


def collect_cli(out, log=print, ssh_host=None):
    """画面なしで未回収をすべて吸い出す（Collect-Logs.cmd から。USBのときだけ）。取った本数を返す"""
    link = find_link(ssh_host, log)
    if not link:
        log('  USBでつないだUNO Qが見つかりません（動画はUSBのときだけ回収。ドックを外してPCへ直接つなぐ）。')
        return 0
    pc = PcStore(out)
    state = list_device(link)
    job = Job('吸い出し')
    job.log = lambda text: log('  v2_video: ' + text)
    n = collect(link, state, pc, None, job)
    for problem in job.problems:
        log(f'  【要確認】{problem}')
    after = list_device(link)
    log(f'  v2_video: 本体の空き {after.free / 1e9:.1f}GB、あと約{after.minutes_left():.0f}分録れる（回収済みは本体が空きの要るときに消す）')
    return n


def main(argv=None):
    parser = argparse.ArgumentParser(description='Ver.2の走行映像をPCへ吸い出す（ネット不要）')
    parser.add_argument('--out', type=Path, default=REPO / 'drive_logs' / 'v2_video')
    parser.add_argument('--ssh', default='unoq', help='USBで見つからないときに使うsshの名前（空でsshを使わない）')
    parser.add_argument('--port', type=int, default=8791)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--collect-all', action='store_true', help='画面なしで未回収をすべて吸い出す')
    args = parser.parse_args(argv)
    if args.collect_all:
        try:
            collect_cli(args.out, ssh_host=args.ssh or None)
            return 0
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            print(f'【要確認】{exc}')
            return 1
    url = running_app(args.port)
    if url:
        print(f'回収アプリはもう開いています。その画面を開きます: {url}')
        print('（回収中ならそのまま続いています。この窓は閉じてかまいません）')
        if not args.no_browser:
            webbrowser.open(url)
        return 0
    app = App(PcStore(args.out), args.ssh or None)
    print('本体を探しています…')
    app.refresh()
    app.find_sd()
    print(app.error or f'見つかった: {app.link.label()}')
    serve(app, args.port, not args.no_browser)
    return 0


if __name__ == '__main__':
    sys.exit(main())
