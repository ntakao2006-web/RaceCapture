#!/usr/bin/env python3
"""Audit KiCad PCB dimensions against JLCPCB rigid-PCB capability limits.

This complements KiCad DRC by checking simple dimensional constraints that are
not all represented by the project's ordinary electrical design rules.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def tokenize(text: str):
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == ';':
            i = text.find('\n', i)
            if i < 0:
                return
        elif c in '()':
            yield c
            i += 1
        elif c == '"':
            i += 1
            value = []
            while i < n:
                c = text[i]
                if c == '\\' and i + 1 < n:
                    value.append(text[i + 1])
                    i += 2
                elif c == '"':
                    i += 1
                    break
                else:
                    value.append(c)
                    i += 1
            yield ''.join(value)
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '();':
                j += 1
            yield text[i:j]
            i = j


def parse(text: str):
    stack = []
    root = None
    for token in tokenize(text):
        if token == '(':
            node = []
            if stack:
                stack[-1].append(node)
            stack.append(node)
        elif token == ')':
            root = stack.pop()
        else:
            stack[-1].append(token)
    if stack:
        raise ValueError('unbalanced S-expression')
    return root


def children(node, name):
    return [item for item in node[1:] if isinstance(item, list) and item and item[0] == name]


def child(node, name):
    found = children(node, name)
    return found[0] if found else None


def nums(node):
    if node is None:
        return []
    out = []
    for value in node[1:]:
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            pass
    return out


def val(node, name, default=None):
    item = child(node, name)
    return item[1] if item and len(item) > 1 else default


def at_xy(node, parent_at=None):
    at = nums(child(node, 'at'))
    x = at[0] if at else 0.0
    y = at[1] if len(at) > 1 else 0.0
    if parent_at is None:
        return x, y
    px, py, angle = parent_at
    # KiCad board coordinates use a downward-positive Y axis, so footprint
    # rotations have the opposite sign from the usual Cartesian transform.
    a = math.radians(angle)
    return px + x * math.cos(a) + y * math.sin(a), py - x * math.sin(a) + y * math.cos(a)


def footprint_at(node):
    at = nums(child(node, 'at'))
    return (at[0], at[1], at[2] if len(at) > 2 else 0.0)


def layer_of(node):
    layer = child(node, 'layer')
    return layer[1] if layer and len(layer) > 1 else None


def layers_of(node):
    layers = child(node, 'layers')
    return layers[1:] if layers else []


def uuid_of(node):
    return val(node, 'uuid', '')


def ref_of(fp):
    for prop in children(fp, 'property'):
        if len(prop) > 2 and prop[1] == 'Reference':
            return prop[2]
    return '?'


def stroke_width(node):
    stroke = child(node, 'stroke')
    values = nums(child(stroke, 'width')) if stroke else []
    return values[0] if values else None


def text_metrics(node):
    effects = child(node, 'effects')
    font = child(effects, 'font') if effects else None
    size = nums(child(font, 'size')) if font else []
    thick = nums(child(font, 'thickness')) if font else []
    return (size[0] if size else None, size[1] if len(size) > 1 else None,
            thick[0] if thick else None)


def round6(value):
    return round(value, 6)


def point_segment_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def orientation(ax, ay, bx, by, cx, cy):
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def segment_distance(a, b):
    a1x, a1y, a2x, a2y = a['points']
    b1x, b1y, b2x, b2y = b['points']
    o1 = orientation(a1x, a1y, a2x, a2y, b1x, b1y)
    o2 = orientation(a1x, a1y, a2x, a2y, b2x, b2y)
    o3 = orientation(b1x, b1y, b2x, b2y, a1x, a1y)
    o4 = orientation(b1x, b1y, b2x, b2y, a2x, a2y)
    if ((o1 == 0 or o2 == 0 or (o1 < 0) != (o2 < 0)) and
            (o3 == 0 or o4 == 0 or (o3 < 0) != (o4 < 0))):
        return 0.0
    return min(
        point_segment_distance(a1x, a1y, b1x, b1y, b2x, b2y),
        point_segment_distance(a2x, a2y, b1x, b1y, b2x, b2y),
        point_segment_distance(b1x, b1y, a1x, a1y, a2x, a2y),
        point_segment_distance(b2x, b2y, a1x, a1y, a2x, a2y),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pcb', type=Path)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--output', type=Path,
                    help='write the complete JSON audit to this file')
    args = ap.parse_args()

    root = parse(args.pcb.read_text(encoding='utf-8'))
    violations = []
    advisories = []
    stats = Counter()
    distributions = defaultdict(Counter)

    def report(rule, description, **data):
        violations.append({'rule': rule, 'description': description, **data})

    def advise(rule, description, **data):
        advisories.append({'rule': rule, 'description': description, **data})

    signal_layers = [x for x in child(root, 'layers')[1:] if isinstance(x, list) and len(x) > 2 and x[2] == 'signal']
    stats['signal_layers'] = len(signal_layers)
    net_names = {
        item[1]: item[2]
        for item in children(root, 'net')
        if len(item) > 2
    }

    drilled_pads = []
    vias = []
    tracks = []

    route_nodes = [node for node in root[1:] if isinstance(node, list) and node and node[0] in ('segment', 'via', 'zone')]
    stats['route_nodes'] = len(route_nodes)
    stats['zones'] = sum(1 for node in route_nodes if node[0] == 'zone')
    footprint_pad_nodes = []

    for node in root[1:]:
        if not isinstance(node, list) or not node:
            continue
        kind = node[0]
        if kind == 'segment':
            stats['tracks'] += 1
            width = float(val(node, 'width'))
            distributions['track_width_mm'][round6(width)] += 1
            start = nums(child(node, 'start'))
            end = nums(child(node, 'end'))
            tracks.append({'points': (*start[:2], *end[:2]), 'width': width,
                           'layer': val(node, 'layer'), 'net': val(node, 'net'),
                           'uuid': uuid_of(node)})
            if width < 0.10 - 1e-9:
                report('track_width', f'track width {width:.3f} mm is below 0.10 mm', uuid=uuid_of(node))
        elif kind == 'via':
            stats['vias'] += 1
            size = float(val(node, 'size'))
            drill = float(val(node, 'drill'))
            x, y = at_xy(node)
            vias.append({'x': x, 'y': y, 'drill': drill, 'uuid': uuid_of(node)})
            distributions['via_size_drill_mm'][f'{size:g}/{drill:g}'] += 1
            if drill < 0.15 - 1e-9:
                report('via_drill', f'via drill {drill:.3f} mm is below 0.15 mm', x=x, y=y, uuid=uuid_of(node))
            if size < 0.25 - 1e-9:
                report('via_diameter', f'via diameter {size:.3f} mm is below 0.25 mm', x=x, y=y, uuid=uuid_of(node))
            if size - drill < 0.10 - 1e-9:
                report('via_diameter_over_drill', f'via diameter exceeds drill by only {size-drill:.3f} mm; 0.10 mm required', x=x, y=y, uuid=uuid_of(node))
            if drill in (0.15, 0.20, 0.25) and size < 0.45 - 1e-9:
                advise('small_via_cost', f'{size:.3f}/{drill:.3f} mm via may trigger the small-via option/cost', x=x, y=y, uuid=uuid_of(node))

        if kind in ('gr_line', 'gr_arc', 'gr_circle', 'gr_rect', 'gr_poly') and layer_of(node) in ('F.SilkS', 'B.SilkS'):
            stats['silk_graphics'] += 1
            width = stroke_width(node)
            if width is not None:
                distributions['silk_line_width_mm'][round6(width)] += 1
                fill = val(node, 'fill', 'none')
                if width < 0.15 - 1e-9 and fill != 'yes':
                    report('silk_line_width', f'{kind} stroke {width:.3f} mm is below 0.15 mm', layer=layer_of(node), uuid=uuid_of(node))
        elif kind == 'gr_text' and layer_of(node) in ('F.SilkS', 'B.SilkS'):
            stats['silk_texts'] += 1
            sx, sy, thick = text_metrics(node)
            if sy is not None and sy < 1.0 - 1e-9:
                report('silk_text_height', f'text height {sy:.3f} mm is below 1.0 mm', layer=layer_of(node), text=node[1], uuid=uuid_of(node))
            if thick is not None and thick < 0.15 - 1e-9:
                report('silk_text_width', f'text thickness {thick:.3f} mm is below 0.15 mm', layer=layer_of(node), text=node[1], uuid=uuid_of(node))

        if kind != 'footprint':
            continue
        stats['footprints'] += 1
        ref = ref_of(node)
        fp_at = footprint_at(node)
        for item in node[1:]:
            if not isinstance(item, list) or not item:
                continue
            ikind = item[0]
            ilayer = layer_of(item)
            if ikind == 'pad':
                footprint_pad_nodes.append([ref, item])
                stats['pads'] += 1
                ptype = item[2] if len(item) > 2 else ''
                size = nums(child(item, 'size'))
                drill_node = child(item, 'drill')
                drill = nums(drill_node)
                x, y = at_xy(item, fp_at)
                if ptype == 'smd' and len(size) >= 2:
                    distributions['smd_min_dimension_mm'][round6(min(size[:2]))] += 1
                    if min(size[:2]) < 0.25 - 1e-9:
                        report('smd_pad_size', f'{ref} pad {item[1]} minimum dimension {min(size[:2]):.3f} mm is below 0.25 mm', ref=ref, pad=item[1], x=x, y=y, uuid=uuid_of(item))
                if drill:
                    dmin = min(drill)
                    shape = drill_node[1] if len(drill_node) > 1 and drill_node[1] == 'oval' else 'circle'
                    distributions[f'{ptype}_drill_mm'][str(tuple(round6(d) for d in drill))] += 1
                    drilled_pads.append({'x': x, 'y': y, 'drill': dmin, 'type': ptype, 'ref': ref, 'pad': item[1], 'uuid': uuid_of(item)})
                    if ptype == 'np_thru_hole':
                        limit = 1.0 if shape == 'oval' else 0.5
                        if dmin < limit - 1e-9:
                            report('npth_size', f'{ref} NPTH {dmin:.3f} mm is below {limit:.2f} mm', ref=ref, x=x, y=y, uuid=uuid_of(item))
                    elif ptype == 'thru_hole':
                        if dmin < 0.15 - 1e-9:
                            report('pth_drill', f'{ref} pad {item[1]} drill {dmin:.3f} mm is below 0.15 mm', ref=ref, pad=item[1], x=x, y=y, uuid=uuid_of(item))
                        if shape == 'oval' and dmin < 0.5 - 1e-9:
                            report('plated_slot_width', f'{ref} pad {item[1]} slot width {dmin:.3f} mm is below 0.50 mm', ref=ref, pad=item[1], x=x, y=y, uuid=uuid_of(item))
                        if len(size) >= 2:
                            ring = (min(size[:2]) - dmin) / 2
                            distributions['pth_annular_ring_mm'][round6(ring)] += 1
                            if ring < 0.18 - 1e-9:
                                report('pth_annular_ring', f'{ref} pad {item[1]} annular ring {ring:.3f} mm is below 0.18 mm', ref=ref, pad=item[1], x=x, y=y, uuid=uuid_of(item))
            elif ikind in ('fp_line', 'fp_arc', 'fp_circle', 'fp_rect', 'fp_poly') and ilayer in ('F.SilkS', 'B.SilkS'):
                stats['silk_graphics'] += 1
                width = stroke_width(item)
                if width is not None:
                    distributions['silk_line_width_mm'][round6(width)] += 1
                    fill = val(item, 'fill', 'none')
                    if width < 0.15 - 1e-9 and fill != 'yes':
                        report('silk_line_width', f'{ref} {ikind} stroke {width:.3f} mm is below 0.15 mm', ref=ref, layer=ilayer, uuid=uuid_of(item))
            elif ikind == 'fp_text' and ilayer in ('F.SilkS', 'B.SilkS'):
                stats['silk_texts'] += 1
                sx, sy, thick = text_metrics(item)
                if sy is not None and sy < 1.0 - 1e-9:
                    report('silk_text_height', f'{ref} {item[1]} text height {sy:.3f} mm is below 1.0 mm', ref=ref, layer=ilayer, uuid=uuid_of(item))
                if thick is not None and thick < 0.15 - 1e-9:
                    report('silk_text_width', f'{ref} {item[1]} text thickness {thick:.3f} mm is below 0.15 mm', ref=ref, layer=ilayer, uuid=uuid_of(item))
            elif ikind == 'property' and ilayer in ('F.SilkS', 'B.SilkS') and child(item, 'hide') is None:
                stats['silk_texts'] += 1
                sx, sy, thick = text_metrics(item)
                label = item[1] if len(item) > 1 else 'property'
                text = item[2] if len(item) > 2 else ''
                if sy is not None and sy < 1.0 - 1e-9:
                    report('silk_text_height', f'{ref} {label} text height {sy:.3f} mm is below 1.0 mm', ref=ref, layer=ilayer, text=text, uuid=uuid_of(item))
                if thick is not None and thick < 0.15 - 1e-9:
                    report('silk_text_width', f'{ref} {label} text thickness {thick:.3f} mm is below 0.15 mm', ref=ref, layer=ilayer, text=text, uuid=uuid_of(item))

    for index, a in enumerate(vias):
        for b in vias[index + 1:]:
            gap = math.hypot(a['x'] - b['x'], a['y'] - b['y']) - (a['drill'] + b['drill']) / 2
            if gap < 0.20 - 1e-9:
                report('via_hole_spacing', f'via hole edge spacing {gap:.3f} mm is below 0.20 mm', a_uuid=a['uuid'], b_uuid=b['uuid'])

    for index, a in enumerate(drilled_pads):
        for b in drilled_pads[index + 1:]:
            gap = math.hypot(a['x'] - b['x'], a['y'] - b['y']) - (a['drill'] + b['drill']) / 2
            if gap < 0.45 - 1e-9:
                report('pad_hole_spacing', f"{a['ref']}:{a['pad']} to {b['ref']}:{b['pad']} hole edge spacing {gap:.3f} mm is below 0.45 mm", a_uuid=a['uuid'], b_uuid=b['uuid'])

    for index, a in enumerate(tracks):
        for b in tracks[index + 1:]:
            if a['layer'] != b['layer'] or not a['net'] or a['net'] != b['net']:
                continue
            center_gap = segment_distance(a, b)
            # Intersecting/touching segments intentionally form one conductor.
            if center_gap < 1e-9:
                continue
            copper_gap = center_gap - (a['width'] + b['width']) / 2
            # Overlapping copper is already one continuous same-net feature,
            # so there is no etched gap whose width must be controlled.
            if copper_gap <= 0:
                continue
            if copper_gap < 0.25 - 1e-9:
                report(
                    'same_net_track_spacing',
                    f'same-net track copper spacing {copper_gap:.3f} mm is below 0.25 mm',
                    net=a['net'], net_name=net_names.get(a['net'], ''),
                    layer=a['layer'], gap_mm=round6(copper_gap),
                    a_points=[round6(value) for value in a['points']],
                    b_points=[round6(value) for value in b['points']],
                    a_uuid=a['uuid'], b_uuid=b['uuid'],
                )

    result = {
        'board': str(args.pcb),
        'basis': 'JLCPCB rigid 2-layer FR-4, 1 oz, routed outline; absolute capability limits',
        'stats': dict(stats),
        'route_signature_sha256': hashlib.sha256(json.dumps(route_nodes, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest(),
        'footprint_pad_signature_sha256': hashlib.sha256(json.dumps(footprint_pad_nodes, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest(),
        'distributions': {key: dict(sorted(value.items(), key=lambda x: str(x[0]))) for key, value in distributions.items()},
        'violation_count': len(violations),
        'violation_rules': dict(Counter(item['rule'] for item in violations)),
        'violations': violations,
        'advisory_count': len(advisories),
        'advisory_rules': dict(Counter(item['rule'] for item in advisories)),
        'advisories': advisories,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({k: result[k] for k in ('basis', 'stats', 'violation_count', 'violation_rules', 'advisory_count', 'advisory_rules')}, ensure_ascii=False, indent=2))
        for item in violations:
            print(f"VIOLATION {item['rule']}: {item['description']}")
        for item in advisories:
            print(f"ADVISORY {item['rule']}: {item['description']}")


if __name__ == '__main__':
    main()
