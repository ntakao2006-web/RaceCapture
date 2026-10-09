#!/usr/bin/env python3
"""Report ELF32 sketch image size and static SHF_ALLOC sections (no hardware).

Allocated section totals are a lower bound, not proof of LLEXT loadability:
the loader needs alignment, bookkeeping, symbol/relocation and heap space too.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def audit(path):
    data = path.read_bytes()
    if len(data) < 52 or data[:6] != b'\x7fELF\x01\x01':
        raise ValueError('Expected a little-endian ELF32 sketch image')
    h = struct.unpack_from('<16sHHIIIIIHHHHHH', data)
    offset, entry_size, count, names_index = h[6], h[11], h[12], h[13]
    if entry_size != 40 or not count or names_index >= count or offset + count * 40 > len(data):
        raise ValueError('Invalid ELF32 section table')
    sections = [struct.unpack_from('<10I', data, offset + i * 40) for i in range(count)]
    names = sections[names_index]
    if names[4] + names[5] > len(data):
        raise ValueError('Invalid section names')
    strings = data[names[4]:names[4]+names[5]]
    allocated = [{'name': strings[s[0]:].split(b'\0', 1)[0].decode('ascii', errors='replace'),
                  'bytes': s[5], 'alignment': s[8], 'zero_fill': s[1] == 8}
                 for s in sections if s[2] & 2 and s[5]]
    total = sum(row['bytes'] for row in allocated)
    return {'image_bytes': len(data), 'image_sha256': hashlib.sha256(data).hexdigest(),
            'partition_bytes': 65536, 'partition_remaining_bytes': 65536-len(data),
            'static_allocated_bytes': total, 'llext_heap_bytes_reference': 128*1024,
            'heap_remaining_before_loader_overhead_bytes': 128*1024-total,
            'sections': allocated,
            'scope': 'Static sections only; loader overhead and runtime heap growth are not included.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.image)
        text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding='utf-8')
        else:
            print(text, end='')
        return 1 if result['partition_remaining_bytes'] < 0 else 0
    except (OSError, ValueError, struct.error) as error:
        parser.exit(2, f'{error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
