#!/usr/bin/env python3
"""Extract focused board-review evidence from a KiCad PCB and audit JSON."""

from __future__ import annotations

import argparse
import heapq
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_jlcpcb import at_xy, child, children, footprint_at, layer_of, nums, parse, ref_of, uuid_of, val  # noqa: E402


def prop(fp, name, default=""):
    for item in children(fp, "property"):
        if len(item) > 2 and item[1] == name:
            return item[2]
    return default


def pad_record(pad, fp_at, net_names):
    net = child(pad, "net")
    net_id = net[1] if net and len(net) > 1 else ""
    net_name = net[2] if net and len(net) > 2 else net_names.get(net_id, "")
    size = nums(child(pad, "size"))
    drill = nums(child(pad, "drill"))
    x, y = at_xy(pad, fp_at)
    return {
        "number": pad[1] if len(pad) > 1 else "",
        "type": pad[2] if len(pad) > 2 else "",
        "shape": pad[3] if len(pad) > 3 else "",
        "x": round(x, 6),
        "y": round(y, 6),
        "size_mm": [round(v, 6) for v in size[:2]],
        "drill_mm": [round(v, 6) for v in drill],
        "net_id": net_id,
        "net_name": net_name,
    }


def marker_between(a, b):
    # This review only needs a stable marker near the two segment centers.
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return [
        round((ax1 + ax2 + bx1 + bx2) / 4, 6),
        round((ay1 + ay2 + by1 + by2) / 4, 6),
    ]


def point_key(x, y):
    return (round(float(x), 6), round(float(y), 6))


def shortest_local_path(tracks, net, layer, excluded, start_points, end_points):
    graph = {}
    for track in tracks:
        if track["net"] != net or track["layer"] != layer or track["uuid"] in excluded:
            continue
        x1, y1, x2, y2 = track["points"]
        a, b = point_key(x1, y1), point_key(x2, y2)
        length = math.hypot(x2 - x1, y2 - y1)
        graph.setdefault(a, []).append((b, length))
        graph.setdefault(b, []).append((a, length))
    targets = {point_key(*p) for p in end_points}
    heap = [(0.0, point_key(*p)) for p in start_points]
    best = {node: 0.0 for _, node in heap}
    heapq.heapify(heap)
    while heap:
        distance, node = heapq.heappop(heap)
        if distance != best.get(node):
            continue
        if node in targets:
            return distance
        if distance > 20.0:
            continue
        for nxt, edge in graph.get(node, []):
            nd = distance + edge
            if nd < best.get(nxt, float("inf")):
                best[nxt] = nd
                heapq.heappush(heap, (nd, nxt))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcb", type=Path)
    ap.add_argument("audit", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    root = parse(args.pcb.read_text(encoding="utf-8"))
    net_names = {
        item[1]: item[2]
        for item in children(root, "net")
        if len(item) > 2
    }

    tracks = []
    for node in children(root, "segment"):
        start = nums(child(node, "start"))
        end = nums(child(node, "end"))
        tracks.append({
            "uuid": uuid_of(node),
            "net": val(node, "net"),
            "layer": val(node, "layer"),
            "points": [*start[:2], *end[:2]],
        })

    footprints = {}
    for fp in children(root, "footprint"):
        ref = ref_of(fp)
        fp_at = footprint_at(fp)
        footprints[ref] = {
            "reference": ref,
            "footprint": fp[1] if len(fp) > 1 else "",
            "value": prop(fp, "Value"),
            "layer": layer_of(fp),
            "at": [round(v, 6) for v in fp_at],
            "pads": [pad_record(p, fp_at, net_names) for p in children(fp, "pad")],
            "models": [m[1] for m in children(fp, "model") if len(m) > 1],
        }

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    spacing = []
    for item in audit["violations"]:
        if item["rule"] != "same_net_track_spacing":
            continue
        a = item["a_points"]
        b = item["b_points"]
        endpoint_gap = min(
            math.hypot(ax - bx, ay - by)
            for ax, ay in ((a[0], a[1]), (a[2], a[3]))
            for bx, by in ((b[0], b[1]), (b[2], b[3]))
        )
        local_path = shortest_local_path(
            tracks,
            str(item["net"]),
            item["layer"],
            {item["a_uuid"], item["b_uuid"]},
            ((a[0], a[1]), (a[2], a[3])),
            ((b[0], b[1]), (b[2], b[3])),
        )
        marker = marker_between(a, b)
        nearby_pads = []
        for fp_ref, fp in footprints.items():
            for pad in fp["pads"]:
                distance = math.hypot(pad["x"] - marker[0], pad["y"] - marker[1])
                if distance <= 1.5:
                    nearby_pads.append({
                        "ref": fp_ref,
                        "pad": pad["number"],
                        "net_name": pad["net_name"],
                        "distance_mm": round(distance, 6),
                        "size_mm": pad["size_mm"],
                    })
        spacing.append({
            **item,
            "marker": marker,
            "nearest_endpoint_distance_mm": round(endpoint_gap, 6),
            "alternate_local_path_mm": round(local_path, 6) if local_path is not None else None,
            "nearby_pads": sorted(nearby_pads, key=lambda x: x["distance_mm"]),
        })

    selected = [
        "C33", "U10", "J2", "J3", "J4", "J5", "J6", "J7",
        "U11", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11",
    ]
    result = {
        "board": str(args.pcb),
        "selected_footprints": {ref: footprints.get(ref) for ref in selected},
        "backside_smd_footprints": [
            {
                "reference": fp["reference"],
                "value": fp["value"],
                "footprint": fp["footprint"],
                "at": fp["at"],
            }
            for fp in sorted(footprints.values(), key=lambda x: x["reference"])
            if fp["layer"] == "B.Cu" and any(pad["type"] == "smd" for pad in fp["pads"])
        ],
        "spacing_summary": {
            "count": len(spacing),
            "minimum_gap_mm": min((x["gap_mm"] for x in spacing), default=None),
            "below_0_10_mm": sum(x["gap_mm"] < 0.10 for x in spacing),
            "from_0_10_to_0_20_mm": sum(0.10 <= x["gap_mm"] < 0.20 for x in spacing),
            "from_0_20_to_0_25_mm": sum(0.20 <= x["gap_mm"] < 0.25 for x in spacing),
            "short_local_corner_count": sum(
                x["alternate_local_path_mm"] is not None and x["alternate_local_path_mm"] <= 2.0
                for x in spacing
            ),
        },
        "spacing_violations": spacing,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
