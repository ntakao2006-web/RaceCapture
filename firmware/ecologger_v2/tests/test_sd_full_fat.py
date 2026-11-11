"""SDがいっぱいになって古いファイルを消したあとのカードを、ふつうのFAT32の読み手（pyfatfs）で読む。
test_sd_full.cpp が書いた像（15本書いて9本消した後、残りは10〜15の6本）を渡す。
2つ目は目次が2区画へ伸びたカード（ほかのファイル15個＋15〜20の6本）:
    python tests/test_sd_full_fat.py <image.bin> [grown.bin]
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'EcoCapture-Web' / 'vendor'))
from pyfatfs.PyFatFS import PyFatFS  # noqa: E402


def check(image, first, last, others=0):
    data = image.read_bytes()
    part = struct.unpack_from('<I', data, 446 + 8)[0]
    part_image = image.with_suffix('.part')
    part_image.write_bytes(data[part * 512:])
    fs = PyFatFS(str(part_image), read_only=True)
    try:
        listed = fs.listdir('/')
        names = sorted(n for n in listed if n.upper().startswith('EL'))
        assert names == [f'EL{i:06d}.BIN' for i in range(first, last + 1)], names
        assert sum(n.upper().startswith('OTHER') for n in listed) == others, listed
        for name in names:
            body = fs.readbytes('/' + name)
            assert len(body) == 1024 * 1024, (name, len(body))
            assert body.startswith(f'file {int(name[2:8])}'.encode()), name
        print(f'PASS: pyfatfs reads {len(names)} files EL{first:06d}-EL{last:06d}, each 1 MiB with its own contents'
              + (f', and {others} other files' if others else ''))
    finally:
        fs.close()
        part_image.unlink()


check(Path(sys.argv[1]), 10, 15)
if len(sys.argv) > 2:  # the root directory grew into a second cluster (2026-11-11)
    check(Path(sys.argv[2]), 15, 20, others=15)
