"""回収アプリのSDカードの部分：Ver.2のシールドのSDカード（STM32が走行の生データ EL######.BIN を書く）を、
PCのカードリーダーに挿して確かめ・回収・空にする・フォーマットする（Windows）。

  - 本体経由でSDを読むと1MBに約60秒かかるので、カードはロガーの電源を切ってから抜き、PCで読む
  - 回収済みかは中身で見る（collect_logs.SdIndex。カードを空にするとSTM32は EL000001 から付け直すため）
  - 回収：Collect-Logs.cmd と同じ（run フォルダの v2_sd/ へ写してSHA-256で確かめ、CSVにも直す）
  - 空にする：PCの写しとSHA-256が同じファイルだけを消す。フォーマットはせず、ロガーが使える形（FAT32）のまま
  - フォーマット：ロガーが使えない形のカード（exFAT等）か、回収していないファイルが無いカードだけ。取り外せるドライブで
    64GB以下・MBRのものに限り、管理者の確認（UAC）を出して FAT32（32KBの区切り、名前 ECOLOGGER）にする
STM32が読めるのは、MBRの区画が FAT32（種類 0x0B/0x0C）で1区切り512バイトのもの（firmware/ecologger_v2/sd_logger.h の mountCard）。
"""
import ctypes
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'tools' / 'collect_logs'))
import collect_logs  # noqa: E402

EL = re.compile(r'^EL\d{6}\.BIN$', re.I)
MAX_FORMAT = 64 << 30


def volume(drive):
    """ドライブの情報（Windows）。drive は 'E:'"""
    root = drive.rstrip('\\') + '\\'
    info = {'drive': drive, 'label': '', 'fs': '', 'total': 0, 'free': 0, 'cluster': 0, 'sector': 0, 'removable': False}
    if os.name != 'nt':
        return info
    k32 = ctypes.windll.kernel32
    label, fs = ctypes.create_unicode_buffer(261), ctypes.create_unicode_buffer(261)
    if k32.GetVolumeInformationW(root, label, 261, None, None, None, fs, 261):
        info['label'], info['fs'] = label.value, fs.value
    avail, total, free = ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_ulonglong()
    if k32.GetDiskFreeSpaceExW(root, ctypes.byref(avail), ctypes.byref(total), ctypes.byref(free)):
        info['total'], info['free'] = total.value, free.value
    spc, bps, fc, tc = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong()
    if k32.GetDiskFreeSpaceW(root, ctypes.byref(spc), ctypes.byref(bps), ctypes.byref(fc), ctypes.byref(tc)):
        info['cluster'], info['sector'] = spc.value * bps.value, bps.value
    info['removable'] = k32.GetDriveTypeW(root) == 2
    return info


def el_files(drive):
    root = Path(drive.rstrip('\\') + '\\')
    try:
        return sorted(p for p in root.iterdir() if p.is_file() and EL.match(p.name))
    except OSError:
        return []


def usable(info):
    """ロガーがこのまま使えるか（使えない理由。使えるなら空）"""
    if info['fs'] != 'FAT32':
        return f'形式が {info["fs"] or "不明"}（ロガーは FAT32 だけ読める）'
    if info['sector'] and info['sector'] != 512:
        return f'1区切りが {info["sector"]} バイト（ロガーは512だけ）'
    return ''


def find_cards(drives=None):
    """ロガーのSDらしいドライブ：ELのファイルがある・名前が ECOLOGGER・取り外せて64GB以下のもの"""
    out = []
    for drive in drives if drives is not None else collect_logs.candidate_drives():
        info = volume(drive)
        files = el_files(drive)
        if not (files or info['label'].upper() == 'ECOLOGGER' or (info['removable'] and 0 < info['total'] <= MAX_FORMAT)):
            continue
        info.update(files=len(files), first=files[0].name if files else '', last=files[-1].name if files else '',
                    bytes=sum(p.stat().st_size for p in files), problem=usable(info))
        out.append(info)
    return out


def check(drive, out_root, job):
    """カードのファイルが回収済みか（中身の先頭で）を数える"""
    files = el_files(drive)
    index, manifest = collect_logs.SdIndex(out_root), collect_logs.load_manifest(Path(out_root) / 'collected.json')
    job.total, done, new = len(files), 0, []
    for f in files:
        if job.cancel:
            raise InterruptedError
        job.file = f.name
        if not index.copy_of(f, manifest):
            new.append(f.name)
        done += 1
        job.done = done
    index.save()
    return {'files': len(files), 'collected': len(files) - len(new), 'uncollected': len(new),
            'uncollected_first': new[0] if new else '', 'uncollected_last': new[-1] if new else ''}


def collect(drive, out_root, job, config=None):
    """回収していないファイルを run フォルダの v2_sd/ へ（Collect-Logs.cmd と同じ）。取った数を返す"""
    out_root = Path(out_root)
    files = el_files(drive)
    run = collect_logs.Run(out_root)
    manifest_path = out_root / 'collected.json'
    manifest, index = collect_logs.load_manifest(manifest_path), collect_logs.SdIndex(out_root)
    todo = [f for f in files if not index.copy_of(f, manifest)]
    job.total = sum(f.stat().st_size for f in todo)
    need = job.total * 2 + (1 << 30)  # BINとCSV
    if shutil.disk_usage(out_root).free < need:
        raise OSError(f'PCの空きが足りない（要る約{need / 1e9:.1f}GB）')
    try:
        for f in todo:
            if job.cancel:
                raise InterruptedError
            job.file = f.name
            collect_logs.collect_sd(run, manifest, 'v2_sd', [f], lambda t: None, config, index)
            job.done += f.stat().st_size
    finally:
        collect_logs.save_manifest(manifest_path, {**collect_logs.load_manifest(manifest_path), **manifest})
        index.save()
    job.log(f'SDから {run.count} 本回収した' + (f'：{run.path}' if run.count else ''))
    return run.count


def empty(drive, out_root, job):
    """PCの写しとSHA-256が同じファイルだけをカードから消す。残った（回収していない）数を返す"""
    out_root = Path(out_root)
    files = el_files(drive)
    manifest, index = collect_logs.load_manifest(out_root / 'collected.json'), collect_logs.SdIndex(out_root)
    job.total = sum(f.stat().st_size for f in files)
    kept = 0
    for f in files:
        if job.cancel:
            raise InterruptedError
        job.file = f.name
        size = f.stat().st_size
        pc = index.copy_of(f, manifest)
        if pc is not None and collect_logs.sha256_of(f) == collect_logs.sha256_of(pc):
            f.unlink()
        else:
            kept += 1
        job.done += size
    index.save()
    job.log(f'SDのファイルを消した（PCの写しと同じだったもの）。回収していないので残したもの {kept} 本')
    return kept


FORMAT_PS = r'''
$ErrorActionPreference = 'Stop'
$letter = '{letter}'
$result = '{result}'
try {{
  $p = Get-Partition -DriveLetter $letter
  $d = Get-Disk -Number $p.DiskNumber
  if (@('SD', 'USB', 'MMC') -notcontains [string]$d.BusType) {{ throw "取り外せるカードではない（$($d.BusType)）" }}
  if ($d.Size -gt {max_bytes}) {{ throw "64GBより大きい" }}
  if ([string]$d.PartitionStyle -ne 'MBR') {{ throw "区画の形が $($d.PartitionStyle)（ロガーはMBRだけ読む。SD Card Formatterで初期化してから）" }}
  if ($p.MbrType -ne 12) {{ Set-Partition -DriveLetter $letter -MbrType 12 }}
  Format-Volume -DriveLetter $letter -FileSystem FAT32 -AllocationUnitSize 32768 -NewFileSystemLabel ECOLOGGER -Force -Confirm:$false | Out-Null
  'OK' | Set-Content -Encoding UTF8 $result
}} catch {{
  ('NG ' + $_.Exception.Message) | Set-Content -Encoding UTF8 $result
}}
'''


def format_card(drive, out_root, job, run=subprocess.run):
    """管理者の確認（UAC）を出して FAT32 にする。回収していないファイルがあれば断る"""
    letter = drive.rstrip(':\\').upper()
    if len(letter) != 1 or letter not in string.ascii_uppercase or f'{letter}:' == Path.home().drive.upper():
        raise OSError('そのドライブはフォーマットできない')
    info = volume(f'{letter}:')
    if not info['removable'] or not 0 < info['total'] <= MAX_FORMAT:
        raise OSError('取り外せる64GB以下のカードだけフォーマットできる')
    index, manifest = collect_logs.SdIndex(out_root), collect_logs.load_manifest(Path(out_root) / 'collected.json')
    left = [f for f in el_files(f'{letter}:') if not index.copy_of(f, manifest)]
    if left:
        raise OSError(f'回収していないファイルが {len(left)} 本ある（先に回収する）')
    with tempfile.TemporaryDirectory() as tmp:
        script, result = Path(tmp) / 'format.ps1', Path(tmp) / 'result.txt'
        script.write_text(FORMAT_PS.format(letter=letter, result=result, max_bytes=MAX_FORMAT), encoding='utf-8-sig')
        job.log('管理者の確認（UAC）が出たら「はい」を押してください')
        run(['powershell', '-NoProfile', '-Command',
             f"Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"{script}\"'"],
            capture_output=True, timeout=600)
        text = result.read_text(encoding='utf-8-sig').strip() if result.exists() else 'NG 管理者の確認がされなかった'
    if not text.startswith('OK'):
        raise OSError(f'フォーマットできなかった：{text[3:]}')
    after = volume(f'{letter}:')
    if usable(after):
        raise OSError(f'フォーマットしたが、まだ使えない形：{usable(after)}')
    job.log(f'{letter}: をロガー用（FAT32・名前 ECOLOGGER）にした')
    return after
