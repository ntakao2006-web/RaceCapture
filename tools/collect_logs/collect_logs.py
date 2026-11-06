"""走行後のログ回収（ER-5-1）。Ver.1・Ver.2・スマホ組を走行回ごとのフォルダへまとめる。

集めるもの（どれも元のファイルは消さない・書き換えない）:
  - Ver.1（ESP32-S3）のSDカード: logs フォルダの CSV・_can.csv・.meta.json・.end.json
  - Ver.2（UNO Q）のシールドSDカード: ELxxxxxx.BIN（CSVへ変換も行う）。回収済みかは中身（先頭64KiBのSHA-256）で見る
    （カードを空にするとSTM32は EL000001 から付け直し、どれも1MBなので、名前と大きさでは前のファイルと取り違えるため。
    一覧は drive_logs/v2_sd_index.json）
  - Ver.2 本体（eMMC）: WebのAPIからCSV・メタデータ・CAN生ログ。USB（adb転送）か、
    同じWi-Fi（テザリング）上の uno-q.local で届いた方から取る。取ったら本体にSHA-256を送り、本体が中身を確かめて
    回収済みの印（LOG_….csv.ok）を付ける。本体は空きが要るとき回収済みから消す（EcoCapture-Web/video_store.py）
  - Ver.2 本体の走行映像（焼き込み録画、~/ecocapture-v2-data/video の .ts と .csv）: 回収アプリ（tools/video_collect、
    Collect-Video.cmd）と同じ処理で、USBのadbで吸い出して本体とPCで中身が同じか（SHA-256）を確かめ、本体に回収済みの印を付ける。
    1本約770MB（10分）で、Wi-Fiでは遅すぎるのでUSBのときだけ。録画中のファイルは取らない。置き場は run フォルダでなく
    drive_logs/v2_video/<走行>/（走行ごと）。本体から消すのは回収アプリの画面から
  - スマホ組（Androidロガー）: USBの「ファイル転送」でつないだ端末の Download/EcoLogger の EL_*.csv

出力: drive_logs/<回収日>/run<NN>_<時刻>/{v1_sd,v2_sd,v2_emmc,phone}/ と、動画は drive_logs/v2_video/<走行>/
前回までに回収したファイル（名前と大きさが同じもの）は drive_logs/collected.json で覚えておき、
もう一度は取らない。新しいものが1つも無ければフォルダを作らない。

使い方: Collect-Logs.cmd をダブルクリック。
  python collect_logs.py [--drives E: F:] [--url URL ...] [--no-emmc] [--no-video] [--no-phone] [--phone-dir DIR] [--out DIR] [--config FILE]
  --config にロガーの config.json（/api/config）を渡すと、SDのCSVに油温などCAN信号の列が付く。
"""
import argparse
import ctypes
import hashlib
import json
import re
import shutil
import string
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'EcoCapture-Web'))

V1_NAME = re.compile(r'^(.+_)?L[0-9A-F]{8}_\d{4}(_can\.csv|\.csv|\.meta\.json|\.end\.json)$', re.I)
V2_SD_NAME = re.compile(r'^EL\d{6}\.BIN$', re.I)
PHONE_NAME = re.compile(r'^EL_[A-Za-z0-9_-]+_\d{8}_\d{6}\.csv$')
DEFAULT_URLS = ['http://127.0.0.1:8080/', 'http://uno-q.local:8080/']
def local_appdata_dirs():
    """%LOCALAPPDATA% と、Claude のアプリが振り替えて使っている同じ場所。
    Claude のアプリ（デスクトップ版）の中から入れたもの（Android SDK など）は、Windows がアプリ専用の
    Packages\\Claude_*\\LocalCache\\Local に置き、アプリの中からだけ %LOCALAPPDATA% の下に見える。
    デスクトップのショートカットから開いた道具からは見えず、adb が無いことになって USB を飛ばしていた（2026-11-07）"""
    local = Path(os.environ.get('LOCALAPPDATA', ''))
    return [local, *sorted(local.glob('Packages/Claude_*/LocalCache/Local'))]


ADB_CANDIDATES = [d / sub / 'platform-tools' / 'adb.exe' for d in local_appdata_dirs()
                  for sub in ('Android/Sdk', 'AndroidSdkTools')] + \
                 [REPO / 'other' / 'uno_q_tools' / 'platform-tools' / 'adb.exe']


def candidate_drives():
    """Every drive letter except the system drive; SD readers are not always reported as removable."""
    system = Path.home().drive.upper()
    if sys.platform != 'win32':
        return []
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    return [f'{letter}:' for i, letter in enumerate(string.ascii_uppercase)
            if mask >> i & 1 and f'{letter}:' != system and letter not in 'AB']


def find_sources(drives):
    found = []
    for drive in drives:
        root = Path(drive + '\\') if re.fullmatch(r'[A-Za-z]:', drive) else Path(drive)
        try:
            v1 = [p for p in (root / 'logs').iterdir() if p.is_file() and V1_NAME.match(p.name)] if (root / 'logs').is_dir() else []
            v2 = [p for p in root.iterdir() if p.is_file() and V2_SD_NAME.match(p.name)]
        except OSError:
            continue  # empty card reader, locked drive, etc.
        if v1:
            found.append(('v1_sd', drive, sorted(v1)))
        if v2:
            found.append(('v2_sd', drive, sorted(v2)))
    return found


def load_manifest(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_manifest(path, manifest):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    temp.replace(path)


class Run:
    """The run folder is created only when the first new file arrives."""
    def __init__(self, out):
        now = datetime.now()
        day = out / now.strftime('%Y%m%d')
        existing = [int(m.group(1)) for p in day.glob('run*') if (m := re.match(r'run(\d+)_', p.name))] if day.is_dir() else []
        self.path = day / f'run{max(existing, default=0) + 1:02}_{now:%H%M}'
        self.count = 0

    def folder(self, kind):
        target = self.path / kind
        target.mkdir(parents=True, exist_ok=True)
        return target


def sha256_of(path, limit=None):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        left = limit
        while chunk := f.read(8 << 20 if left is None else min(8 << 20, left)):
            h.update(chunk)
            if left is not None:
                left -= len(chunk)
                if not left:
                    break
    return h.hexdigest()


HEAD = 64 << 10  # SDのファイルの見分けに使う先頭（最初のブロックにSTM32の時刻が入るので、別のファイルとは必ず違う）


class SdIndex:
    """Ver.2のSDのファイルを中身で見分ける（drive_logs/v2_sd_index.json）。鍵は「名前/大きさ/先頭64KiBのSHA-256」、
    値はPCに置いた場所（drive_logs からの相対）と、分かっていれば全体のSHA-256"""
    def __init__(self, root):
        self.root, self.path = Path(root), Path(root) / 'v2_sd_index.json'
        try:
            self.entries = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.entries = {}

    def save(self):
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.entries, ensure_ascii=False, indent=1), encoding='utf-8')
        temp.replace(self.path)

    def key(self, path):
        return f'{path.name}/{path.stat().st_size}/{sha256_of(path, HEAD)}'

    def copy_of(self, src, manifest=None, key=None):
        """PCにある同じファイル（Path）か None。前の名前と大きさだけの記録（collected.json）は、先頭が同じときだけ同じとみなす"""
        key = key or self.key(src)
        e = self.entries.get(key)
        if e and (self.root / e['path']).is_file():
            return self.root / e['path']
        old = (manifest or {}).get(f'v2_sd/{src.name}/{src.stat().st_size}')
        if old:
            pc = self.root / old.replace('\\', '/')
            if pc.is_file() and pc.stat().st_size == src.stat().st_size and sha256_of(pc, HEAD) == key.rsplit('/', 1)[1]:
                self.entries[key] = {'path': pc.relative_to(self.root).as_posix(), 'sha256': None}
                return pc
        return None

    def add(self, key, dest, sha):
        self.entries[key] = {'path': dest.relative_to(self.root).as_posix(), 'sha256': sha}


def collect_sd(run, manifest, kind, files, log, config=None, index=None):
    decoder = None  # one decoder across the sorted files keeps CAN values continuous at file boundaries
    if kind == 'v2_sd' and config is not None:
        from sd_decode import new_decoder
        decoder = new_decoder()
    for src in files:
        key = f'{kind}/{src.name}/{src.stat().st_size}'
        if kind == 'v2_sd' and index is not None:
            ikey = index.key(src)
            if index.copy_of(src, manifest, ikey):
                continue
        elif key in manifest:
            continue
        dest = run.folder(kind) / src.name
        shutil.copy2(src, dest)
        if dest.stat().st_size != src.stat().st_size:
            raise OSError(f'コピーの大きさが一致しません: {src}')
        if kind == 'v2_sd' and index is not None:
            sha = sha256_of(src)
            if sha256_of(dest) != sha:
                dest.unlink()
                raise OSError(f'コピーの中身が一致しません: {src}')
            index.add(ikey, dest, sha)
        manifest.setdefault(key, str(dest.relative_to(run.path.parents[1])))
        run.count += 1
        log(f'  {kind}: {src.name}')
        if kind == 'v2_sd':
            try:
                from sd_decode import convert
                convert(dest, dest.with_suffix('.csv'), config, decoder)
            except Exception as exc:  # keep the raw file; decoding can be redone later
                log(f'    （CSVへの変換に失敗。BINはコピー済み）{exc}')


def http_get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def http_post(url, body, timeout=600):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'X-EcoCapture': '1'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def mark_collected(url, name, csv_path, log):
    """本体に「PCに写した」と知らせる。本体が自分のファイルのSHA-256と比べ、同じなら回収済みの印を付ける"""
    can = csv_path.with_name(csv_path.name + '.can.jsonl')
    body = {'sha256': sha256_of(csv_path), 'can_sha256': sha256_of(can) if can.is_file() else None}
    try:
        http_post(urllib.parse.urljoin(url, f'api/logs/{urllib.parse.quote(name)}/collected'), body)
        return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:  # 印を付けられない前の版のEcoCapture
            return False
        raise OSError(f'{name}：本体に回収済みの印を付けられません（{exc.code} {exc.read().decode("utf-8", "replace")[:120]}）')


def find_adb():
    return shutil.which('adb') or next((str(p) for p in ADB_CANDIDATES if p.is_file()), None)


def _uno_q_serial():
    sys.path.insert(0, str(REPO / 'tools' / 'video_collect'))
    import video_collect
    link = video_collect.find_link(None)
    return link.serial if link else None


def adb_command():
    """USBでつないだUNO Qへの adb の頭（[adb, '-s', 番号]）。見つからなければ None。
    HUD・レンズ・露出・SUGOの道具の --adb が使う（11/4の回収アプリの作り直しで一度消えて、--adb が動かなくなっていた。
    スマホもadbにつながっていることがあるので、番号を付けてUNO Qを選ぶ）"""
    adb, serial = find_adb(), _uno_q_serial()
    return [adb, '-s', serial] if adb and serial else None


def list_uno_q_videos(adb=None):
    """(UNO Qの番号, None, None)。前の版と同じ形（呼ぶ側は番号だけ使う）"""
    return _uno_q_serial(), None, None


def video_link():
    """動画を吸い出す相手（USBのadbでつないだUNO Qだけ。試験では差し替える）"""
    import video_collect
    return video_collect.find_link(None)


def collect_video(out, log):
    """回収アプリ（tools/video_collect）と同じ処理で未回収の動画を吸い出す。取った本数を返す"""
    sys.path.insert(0, str(REPO / 'tools' / 'video_collect'))
    import video_collect
    link = video_link()
    if not link:
        log('  USBでつないだUNO Qが見つかりません（動画はUSBのときだけ回収。ドックを外してPCへ直接つなぐ）。')
        return 0
    pc = video_collect.PcStore(out / 'v2_video')
    job = video_collect.Job('吸い出し')
    job.log = lambda text: log('  v2_video: ' + text)
    n = video_collect.collect(link, video_collect.list_device(link), pc, None, job)
    for problem in job.problems:
        log(f'  【要確認】{problem}')
    after = video_collect.list_device(link)
    log(f'  v2_video: 本体の空き {after.free / 1e9:.1f}GB、あと約{after.minutes_left():.0f}分録れる'
        f'（回収済みは、空きが要るときに本体が先に消す。すぐ消すときは Collect-Video.cmd の画面から）')
    return n


def reach_uno_q(urls, log):
    """Return the first URL that answers. A localhost URL is retried after setting up the adb forward."""
    for url in urls:
        status = urllib.parse.urljoin(url, 'api/status')
        try:
            http_get(status, timeout=3)
            return url
        except (urllib.error.URLError, OSError):
            pass
        parsed = urllib.parse.urlparse(url)
        adb = find_adb()
        if parsed.hostname not in ('127.0.0.1', 'localhost') or not adb:
            continue
        try:
            subprocess.run([adb, 'forward', f'tcp:{parsed.port or 80}', 'tcp:8080'], capture_output=True, timeout=15, check=True)
            http_get(status, timeout=5)
            return url
        except (OSError, subprocess.SubprocessError, urllib.error.URLError):
            pass
    log('  UNO Qに接続できません（USBケーブル・電源、またはPCとUNO Qが同じテザリングにいるかを確認）。本体の記録は今回は回収しません。')
    return None


def stage_phones(staging, log):
    """Copy phone CSVs over MTP into staging; returns [(device, [files])]."""
    try:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                 '-File', str(Path(__file__).with_name('phone_mtp.ps1')), '-Dest', str(staging)],
                                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
    except (OSError, subprocess.SubprocessError) as exc:
        log(f'  スマホを調べられませんでした: {exc}')
        return []
    for line in result.stdout.splitlines():
        if line.startswith('FAILED '):
            log(f'  コピーに失敗: {line[7:]}')
    if result.returncode:
        log(f'  スマホを調べられませんでした: {result.stderr.strip()[:200]}')
    return list_phone_dirs(staging)


def list_phone_dirs(root):
    if not root.is_dir():
        return []
    found = []
    for folder in [root, *sorted(p for p in root.iterdir() if p.is_dir())]:
        files = sorted(p for p in folder.iterdir() if p.is_file() and PHONE_NAME.match(p.name))
        if files:
            found.append((folder.name, files))
    return found


def collect_emmc(run, manifest, url, log):
    logs = json.loads(http_get(urllib.parse.urljoin(url, 'api/logs')))
    for item in logs:
        if item.get('active'):
            log(f'  v2_emmc: {item["name"]} は記録中のため回収しません（記録停止後にもう一度実行）')
            continue
        if item.get('demo'):
            continue
        key = f'v2_emmc/{item["name"]}/{item["size"]}'
        if key in manifest:
            pc = run.path.parents[1] / manifest[key].replace('\\', '/')
            if not item.get('collected') and 'collected' in item and pc.is_file():
                if mark_collected(url, item['name'], pc, log):
                    log(f'  v2_emmc: {item["name"]} 前に回収した写しと同じなので、本体に回収済みの印を付けた')
            continue
        name = urllib.parse.quote(item['name'])
        target = run.folder('v2_emmc')
        parts = [(f'api/logs/{name}/download', item['name'], True),
                 (f'api/logs/{name}/metadata', item['name'] + '.meta.json', False),
                 (f'api/logs/{name}/can', item['name'] + '.can.jsonl', False)]
        for path, filename, required in parts:
            try:
                (target / filename).write_bytes(http_get(urllib.parse.urljoin(url, path), timeout=120))
            except urllib.error.HTTPError:
                if required:
                    raise
        manifest[key] = str((target / item['name']).relative_to(run.path.parents[1]))
        run.count += 1
        marked = mark_collected(url, item['name'], target / item['name'], log)
        log(f'  v2_emmc: {item["name"]}' + ('（本体に回収済みの印）' if marked else ''))


def main(argv=None):
    parser = argparse.ArgumentParser(description='走行ログを2台分まとめて回収する')
    parser.add_argument('--drives', nargs='*', help='調べるドライブ（省略時はCドライブ以外すべて）')
    parser.add_argument('--url', nargs='+', default=DEFAULT_URLS, help='UNO QのWeb（上から順に試す。127.0.0.1はadb転送）')
    parser.add_argument('--no-emmc', action='store_true', help='UNO Q本体からは回収しない')
    parser.add_argument('--no-video', action='store_true', help='UNO Q本体の走行映像は回収しない')
    parser.add_argument('--no-phone', action='store_true', help='スマホからは回収しない')
    parser.add_argument('--phone-dir', type=Path, help='スマホのEcoLoggerフォルダを手でコピーした場所（USBの自動コピーの代わり）')
    parser.add_argument('--out', type=Path, default=REPO / 'drive_logs')
    parser.add_argument('--config', type=Path, help='ロガーのconfig.json。SDのCSVにCAN信号の列を付ける')
    args = parser.parse_args(argv)
    log = print
    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / 'collected.json'
    manifest = load_manifest(manifest_path)
    run = Run(args.out)
    config = None
    if args.config:
        from sd_decode import load_config
        config = load_config(args.config)
    problems, videos = [], 0
    sd_index = SdIndex(args.out)
    try:
        sources = find_sources(args.drives if args.drives is not None else candidate_drives())
        if not sources:
            log('SDカードのログは見つかりませんでした。')
        for kind, drive, files in sources:
            log(f'{drive} {"Ver.1 SD" if kind == "v1_sd" else "Ver.2 SD"}（{len(files)} ファイル）')
            try:
                collect_sd(run, manifest, kind, files, log, config if kind == 'v2_sd' else None, sd_index)
            except OSError as exc:
                problems.append(f'{drive}: {exc}')
        if not args.no_emmc:
            log('Ver.2 本体（eMMC）')
            url = reach_uno_q(args.url, log)
            if url:
                try:
                    collect_emmc(run, manifest, url, log)
                except (urllib.error.URLError, OSError, ValueError) as exc:
                    problems.append(f'UNO Q: {exc}')
        if not args.no_video:
            log('Ver.2 本体（走行映像、USBのみ）')
            try:
                videos = collect_video(args.out, log)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                problems.append(f'UNO Qの動画: {exc}')
        if not args.no_phone:
            log('スマホ（Androidロガー）')
            with tempfile.TemporaryDirectory() as staging:
                phones = list_phone_dirs(args.phone_dir) if args.phone_dir else stage_phones(Path(staging), log)
                if not phones:
                    log('  スマホのログは見つかりませんでした（USBを「ファイル転送」にしてつなぐ）。')
                for device, files in phones:
                    log(f'  {device}（{len(files)} ファイル）')
                    try:
                        collect_sd(run, manifest, 'phone', files, log)
                    except OSError as exc:
                        problems.append(f'{device}: {exc}')
    finally:  # 動画の回収（video_collect）も同じファイルへ書くので、読み直して足す
        save_manifest(manifest_path, {**load_manifest(manifest_path), **manifest})
        sd_index.save()
    log('')
    if run.count:
        log(f'新しいログ {run.count} 件を回収しました: {run.path}')
    if videos:
        log(f'走行映像 {videos} 本を回収しました: {args.out / "v2_video"}（走行ごとのフォルダ）')
    if not run.count and not videos:
        log('新しいログはありませんでした（前回までに回収済み）。')
    for problem in problems:
        log(f'【要確認】{problem}')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
