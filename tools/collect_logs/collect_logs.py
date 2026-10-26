"""走行後のログ回収（ER-5-1）。Ver.1・Ver.2・スマホ組を走行回ごとのフォルダへまとめる。

集めるもの（どれも元のファイルは消さない・書き換えない）:
  - Ver.1（ESP32-S3）のSDカード: logs フォルダの CSV・_can.csv・.meta.json・.end.json
  - Ver.2（UNO Q）のシールドSDカード: ELxxxxxx.BIN（CSVへ変換も行う）
  - Ver.2 本体（eMMC）: WebのAPIからCSV・メタデータ・CAN生ログ。USB（adb転送）か、
    同じWi-Fi（テザリング）上の uno-q.local で届いた方から取る
  - スマホ組（Androidロガー）: USBの「ファイル転送」でつないだ端末の Download/EcoLogger の EL_*.csv

出力: drive_logs/<回収日>/run<NN>_<時刻>/{v1_sd,v2_sd,v2_emmc,phone}/
前回までに回収したファイル（名前と大きさが同じもの）は drive_logs/collected.json で覚えておき、
もう一度は取らない。新しいものが1つも無ければフォルダを作らない。

使い方: Collect-Logs.cmd をダブルクリック。
  python collect_logs.py [--drives E: F:] [--url URL ...] [--no-emmc] [--no-phone] [--phone-dir DIR] [--out DIR] [--config FILE]
  --config にロガーの config.json（/api/config）を渡すと、SDのCSVに油温などCAN信号の列が付く。
"""
import argparse
import ctypes
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
ADB_CANDIDATES = [Path(os.environ.get('LOCALAPPDATA', '')) / 'Android' / 'Sdk' / 'platform-tools' / 'adb.exe',
                  REPO / 'other' / 'uno_q_tools' / 'platform-tools' / 'adb.exe']


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


def collect_sd(run, manifest, kind, files, log, config=None):
    decoder = None  # one decoder across the sorted files keeps CAN values continuous at file boundaries
    if kind == 'v2_sd' and config is not None:
        from sd_decode import new_decoder
        decoder = new_decoder()
    for src in files:
        key = f'{kind}/{src.name}/{src.stat().st_size}'
        if key in manifest:
            continue
        dest = run.folder(kind) / src.name
        shutil.copy2(src, dest)
        if dest.stat().st_size != src.stat().st_size:
            raise OSError(f'コピーの大きさが一致しません: {src}')
        manifest[key] = str(dest.relative_to(run.path.parents[1]))
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


def find_adb():
    return shutil.which('adb') or next((str(p) for p in ADB_CANDIDATES if p.is_file()), None)


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
        log(f'  v2_emmc: {item["name"]}')


def main(argv=None):
    parser = argparse.ArgumentParser(description='走行ログを2台分まとめて回収する')
    parser.add_argument('--drives', nargs='*', help='調べるドライブ（省略時はCドライブ以外すべて）')
    parser.add_argument('--url', nargs='+', default=DEFAULT_URLS, help='UNO QのWeb（上から順に試す。127.0.0.1はadb転送）')
    parser.add_argument('--no-emmc', action='store_true', help='UNO Q本体からは回収しない')
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
    problems = []
    try:
        sources = find_sources(args.drives if args.drives is not None else candidate_drives())
        if not sources:
            log('SDカードのログは見つかりませんでした。')
        for kind, drive, files in sources:
            log(f'{drive} {"Ver.1 SD" if kind == "v1_sd" else "Ver.2 SD"}（{len(files)} ファイル）')
            try:
                collect_sd(run, manifest, kind, files, log, config if kind == 'v2_sd' else None)
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
    finally:
        save_manifest(manifest_path, manifest)
    log('')
    if run.count:
        log(f'新しいログ {run.count} 件を回収しました: {run.path}')
    else:
        log('新しいログはありませんでした（前回までに回収済み）。')
    for problem in problems:
        log(f'【要確認】{problem}')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
