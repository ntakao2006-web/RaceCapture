#!/usr/bin/env python3
"""Capture source hashes, or compare a saved UNO Q source directory/manifest.

No device access and no source replacement. SHA256 LF hashes ignore CRLF only.
Exit 0: snapshot/equal; 1: different/missing files; 2: invalid input.
"""
import argparse
import hashlib
import json
from pathlib import Path


def snapshot(root):
    files = sorted(p for p in root.iterdir() if p.is_file() and
                   (p.suffix in ('.h', '.ino') or p.name in ('build.sh', 'compact_symbols.py')))
    if not files or not (root / 'logger_impl.h').is_file():
        raise ValueError('Expected an ecologger_v2 source directory with logger_impl.h')
    return {'schema': 'ecologger-v2-source-v1', 'files': {
        p.name: {'bytes': len(p.read_bytes()),
                 'sha256_raw': hashlib.sha256(p.read_bytes()).hexdigest(),
                 'sha256_lf': hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()}
        for p in files}}


def differences(a, b):
    return [{'file': name, 'status': 'missing_local' if name not in a['files'] else
             'missing_snapshot' if name not in b['files'] else 'different',
             'local_sha256_lf': a['files'].get(name, {}).get('sha256_lf'),
             'snapshot_sha256_lf': b['files'].get(name, {}).get('sha256_lf')}
            for name in sorted(a['files'].keys() | b['files'].keys())
            if a['files'].get(name, {}).get('sha256_lf') != b['files'].get(name, {}).get('sha256_lf')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('saved', nargs='?', type=Path, help='UNO Q source directory or JSON manifest')
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', type=Path, help='Write JSON to this path')
    args = parser.parse_args()
    try:
        current = snapshot(args.source)
        result = current
        if args.saved:
            saved = snapshot(args.saved) if args.saved.is_dir() else json.loads(args.saved.read_text())
            if saved.get('schema') != current['schema'] or not isinstance(saved.get('files'), dict):
                raise ValueError('Unsupported source manifest')
            for row in saved['files'].values():
                if not isinstance(row, dict) or not isinstance(row.get('sha256_lf'), str) or len(row['sha256_lf']) != 64:
                    raise ValueError('Invalid source hash')
            delta = differences(current, saved)
            result = {'equal_ignoring_crlf': not delta, 'differences': delta}
        text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding='utf-8')
        else:
            print(text, end='')
        return 1 if args.saved and result['differences'] else 0
    except (OSError, ValueError, TypeError, AttributeError) as error:
        parser.exit(2, f'{error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
