#!/usr/bin/env python3
"""Synchronize footprint metadata and population from a KiCad XML netlist.

This intentionally does not touch tracks, vias, zones, board drawings, or board text.
Existing schematic-linked footprints keep their placement. New parts reuse an obsolete
part's placement only when that mapping is unambiguous; otherwise they are staged.
"""

from __future__ import annotations

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import pcbnew


@dataclass(frozen=True)
class Component:
    ref: str
    value: str
    footprint: str
    path: str


def fpid_string(footprint: pcbnew.FOOTPRINT) -> str:
    fpid = footprint.GetFPID()
    return f"{fpid.GetLibNickname()}:{fpid.GetLibItemName()}"


def parse_netlist(path: Path) -> tuple[list[Component], dict[tuple[str, str], str]]:
    root = ET.parse(path).getroot()
    components: list[Component] = []
    for node in root.findall("./components/comp"):
        footprint = node.findtext("footprint", default="").strip()
        if not footprint:
            raise RuntimeError(f"{node.attrib['ref']}: footprint is not assigned")
        stamp = node.findtext("tstamps", default="").strip().strip("/")
        if not stamp:
            raise RuntimeError(f"{node.attrib['ref']}: schematic UUID is missing")
        components.append(
            Component(
                ref=node.attrib["ref"],
                value=node.findtext("value", default=""),
                footprint=footprint,
                path=f"/{stamp}",
            )
        )

    pin_nets: dict[tuple[str, str], str] = {}
    for net in root.findall("./nets/net"):
        name = net.attrib["name"]
        for node in net.findall("node"):
            pin_nets[(node.attrib["ref"], node.attrib["pin"])] = name
    return components, pin_nets


def footprint_library_dir(project_dir: Path, nickname: str) -> Path:
    if nickname == "logger_v1_custom":
        return project_dir / "logger_v1_custom.pretty"
    configured_root = os.environ.get("KICAD9_FOOTPRINT_DIR", "").strip()
    if configured_root:
        standard_root = Path(configured_root)
    else:
        standard_root = (
            Path(sys.executable).resolve().parent.parent
            / "share"
            / "kicad"
            / "footprints"
        )
    return standard_root / f"{nickname}.pretty"


def load_footprint(project_dir: Path, fpid: str) -> pcbnew.FOOTPRINT:
    try:
        nickname, item_name = fpid.split(":", 1)
    except ValueError as exc:
        raise RuntimeError(f"Invalid footprint ID: {fpid}") from exc
    library_dir = footprint_library_dir(project_dir, nickname)
    if not library_dir.is_dir():
        raise RuntimeError(f"Footprint library directory does not exist: {library_dir}")
    try:
        footprint = pcbnew.FootprintLoad(str(library_dir), item_name)
    except Exception as exc:
        raise RuntimeError(f"Cannot load {fpid} from {library_dir}") from exc
    if footprint is None:
        raise RuntimeError(f"Cannot load {fpid} from {library_dir}")
    footprint.SetFPID(pcbnew.LIB_ID(nickname, item_name))
    return footprint


def ensure_net(board: pcbnew.BOARD, name: str) -> pcbnew.NETINFO_ITEM:
    net = board.FindNet(name)
    if net is None:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
    return net


def assign_pad_nets(
    board: pcbnew.BOARD,
    footprint: pcbnew.FOOTPRINT,
    ref: str,
    pin_nets: dict[tuple[str, str], str],
) -> None:
    for pad in footprint.Pads():
        net_name = pin_nets.get((ref, str(pad.GetNumber())))
        if net_name:
            pad.SetNet(ensure_net(board, net_name))
        else:
            pad.SetNetCode(0)


def stage_position(index: int) -> pcbnew.VECTOR2I:
    x_mm = 230.0 + (index % 4) * 15.0
    y_mm = 20.0 + (index // 4) * 15.0
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("board", type=Path)
    parser.add_argument("netlist", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--refresh-all",
        action="store_true",
        help="Reload every front-side footprint from its assigned library",
    )
    args = parser.parse_args()

    project_dir = args.board.resolve().parent
    board = pcbnew.LoadBoard(str(args.board))
    components, pin_nets = parse_netlist(args.netlist)
    schematic_paths = {component.path for component in components}

    original_footprints = list(board.GetFootprints())
    original_tracks = len(board.GetTracks())
    original_zones = len(board.Zones())
    original_drawings = len(board.GetDrawings())

    by_path = {fp.GetPath().AsString(): fp for fp in original_footprints if fp.GetPath().AsString()}
    obsolete = [
        fp
        for fp in original_footprints
        if not fp.GetReference().startswith("H") and fp.GetPath().AsString() not in schematic_paths
    ]
    obsolete_by_ref = {fp.GetReference(): fp for fp in obsolete}
    used_obsolete_positions: set[str] = set()

    # TUSB320 replaces the obsolete CD74HC4053 position; the other one-to-one
    # replacements can be recovered safely by matching their reference.
    explicit_position_source = {"U10": "U8"}

    for fp in obsolete:
        board.Remove(fp)

    updated: list[str] = []
    replaced: list[str] = []
    added: list[str] = []
    staged: list[str] = []

    for component in components:
        current = by_path.get(component.path)
        if current is not None:
            same_fpid = fpid_string(current) == component.footprint
            preserve_existing = same_fpid and (
                not args.refresh_all or current.GetLayer() == pcbnew.B_Cu
            )
            if preserve_existing:
                current.SetReference(component.ref)
                current.SetValue(component.value)
                current.SetPath(pcbnew.KIID_PATH(component.path))
                current.SetSheetname("/")
                current.SetSheetfile(args.board.with_suffix(".kicad_sch").name)
                assign_pad_nets(board, current, component.ref, pin_nets)
                updated.append(component.ref)
                continue

            if current.GetLayer() == pcbnew.B_Cu:
                raise RuntimeError(
                    f"Refusing to replace back-side footprint {current.GetReference()} automatically"
                )
            position = current.GetPosition()
            orientation = current.GetOrientationDegrees()
            board.Remove(current)
            replacement = load_footprint(project_dir, component.footprint)
            replacement.SetPosition(position)
            replacement.SetOrientationDegrees(orientation)
            replacement.SetReference(component.ref)
            replacement.SetValue(component.value)
            replacement.SetPath(pcbnew.KIID_PATH(component.path))
            replacement.SetSheetname("/")
            replacement.SetSheetfile(args.board.with_suffix(".kicad_sch").name)
            board.Add(replacement)
            assign_pad_nets(board, replacement, component.ref, pin_nets)
            replaced.append(component.ref)
            continue

        source_ref = component.ref if component.ref in obsolete_by_ref else explicit_position_source.get(component.ref)
        source = obsolete_by_ref.get(source_ref) if source_ref else None
        new_footprint = load_footprint(project_dir, component.footprint)
        if source is not None and source_ref not in used_obsolete_positions:
            new_footprint.SetPosition(source.GetPosition())
            new_footprint.SetOrientationDegrees(source.GetOrientationDegrees())
            used_obsolete_positions.add(source_ref)
        else:
            new_footprint.SetPosition(stage_position(len(staged)))
            staged.append(component.ref)
        new_footprint.SetReference(component.ref)
        new_footprint.SetValue(component.value)
        new_footprint.SetPath(pcbnew.KIID_PATH(component.path))
        new_footprint.SetSheetname("/")
        new_footprint.SetSheetfile(args.board.with_suffix(".kicad_sch").name)
        board.Add(new_footprint)
        assign_pad_nets(board, new_footprint, component.ref, pin_nets)
        added.append(component.ref)

    board.BuildListOfNets()
    board.RemoveUnusedNets(None)

    if len(board.GetTracks()) != original_tracks:
        raise RuntimeError("Track or via count changed")
    if len(board.Zones()) != original_zones:
        raise RuntimeError("Zone count changed")
    if len(board.GetDrawings()) != original_drawings:
        raise RuntimeError("Board drawing count changed")

    actual_refs = {fp.GetReference() for fp in board.GetFootprints()}
    expected_refs = {component.ref for component in components}
    if actual_refs != expected_refs:
        raise RuntimeError(
            f"Reference mismatch: missing={sorted(expected_refs - actual_refs)}, "
            f"extra={sorted(actual_refs - expected_refs)}"
        )

    print(f"updated={len(updated)} replaced={replaced} added={added}")
    print(f"removed={[fp.GetReference() for fp in obsolete]}")
    print(f"staged={staged}")
    print(
        f"tracks={len(board.GetTracks())} zones={len(board.Zones())} "
        f"drawings={len(board.GetDrawings())} footprints={len(board.GetFootprints())}"
    )

    if args.output:
        pcbnew.SaveBoard(str(args.output), board)
        print(f"saved={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
