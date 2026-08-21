#!/usr/bin/env python3
"""Raise visible KiCad silkscreen strokes and text to JLCPCB minima."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SILK_LAYERS = ('F.SilkS', 'B.SilkS')
GRAPHIC_HEADS = {'fp_line', 'fp_arc', 'fp_circle', 'fp_rect', 'fp_poly',
                 'gr_line', 'gr_arc', 'gr_circle', 'gr_rect', 'gr_poly'}
TEXT_HEADS = {'fp_text', 'gr_text', 'fp_text_box', 'gr_text_box', 'property'}


def nodes(text: str):
    """Yield (head, start, end) for every S-expression in source order."""
    stack = []
    in_string = False
    escape = False
    comment = False
    i = 0
    while i < len(text):
        c = text[i]
        if comment:
            if c in '\r\n':
                comment = False
            i += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == '"':
                in_string = False
            i += 1
            continue
        if c == ';':
            comment = True
        elif c == '"':
            in_string = True
        elif c == '(':
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            k = j
            while k < len(text) and not text[k].isspace() and text[k] not in '()':
                k += 1
            stack.append((text[j:k], i))
        elif c == ')':
            head, start = stack.pop()
            yield head, start, i + 1
        i += 1
    if stack:
        raise ValueError('unbalanced S-expression')


def numeric_edits(block: str, base: int, pattern: re.Pattern, minimum: float, count: int | None = None):
    edits = []
    for match in pattern.finditer(block):
        spans = range(1, match.lastindex + 1)
        numeric_groups = [group for group in spans if match.group(group) is not None]
        for group in numeric_groups[:count]:
            value = float(match.group(group))
            if value < minimum - 1e-12:
                start, end = match.span(group)
                edits.append((base + start, base + end, f'{minimum:g}'))
    return edits


WIDTH_RE = re.compile(r'\(width\s+([-+]?(?:\d+(?:\.\d*)?|\.\d+))\)')
SIZE_RE = re.compile(r'\(size\s+([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s+([-+]?(?:\d+(?:\.\d*)?|\.\d+))\)')
THICK_RE = re.compile(r'\(thickness\s+([-+]?(?:\d+(?:\.\d*)?|\.\d+))\)')


def fix(path: Path):
    with path.open('r', encoding='utf-8', newline='') as stream:
        text = stream.read()
    edits = []
    graphic_count = 0
    text_size_count = 0
    text_thickness_count = 0

    for head, start, end in nodes(text):
        if head not in GRAPHIC_HEADS and head not in TEXT_HEADS:
            continue
        block = text[start:end]
        if not any(f'(layer "{layer}")' in block for layer in SILK_LAYERS):
            continue
        if re.search(r'\(hide(?:\s+yes)?\)', block):
            continue
        if head in GRAPHIC_HEADS:
            found = numeric_edits(block, start, WIDTH_RE, 0.15, count=1)
            graphic_count += len(found)
            edits.extend(found)
        else:
            found_size = numeric_edits(block, start, SIZE_RE, 1.0, count=2)
            found_thick = numeric_edits(block, start, THICK_RE, 0.15, count=1)
            text_size_count += len(found_size)
            text_thickness_count += len(found_thick)
            edits.extend(found_size)
            edits.extend(found_thick)

    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]

    if edits:
        with path.open('w', encoding='utf-8', newline='') as stream:
            stream.write(text)
    return {
        'path': str(path),
        'silk_strokes_raised': graphic_count,
        'text_size_dimensions_raised': text_size_count,
        'text_thicknesses_raised': text_thickness_count,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', type=Path, nargs='+')
    args = ap.parse_args()
    for path in args.paths:
        print(fix(path))


if __name__ == '__main__':
    main()
