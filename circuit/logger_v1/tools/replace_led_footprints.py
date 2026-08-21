import sys
from pathlib import Path


KICAD_PYTHON = Path(sys.executable)
if "KiCad\\9.0\\bin" not in str(KICAD_PYTHON):
    raise SystemExit("Run with KiCad 9 bundled python.exe so that pcbnew is available")

import pcbnew  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
BOARD_PATH = ROOT / "logger_v1.kicad_pcb"
LIBRARY_PATH = ROOT / "logger_v1_custom.pretty"
FOOTPRINT_NAME = "LED_D3.0mm_JLCPCB"
REFERENCES = tuple(f"D{number}" for number in range(4, 12))


def copy_field_appearance(old_fp, new_fp):
    for old_field in old_fp.GetFields():
        new_field = new_fp.GetFieldByName(old_field.GetName())
        if new_field is None:
            continue
        new_field.SetPosition(old_field.GetPosition())
        new_field.SetTextAngle(old_field.GetTextAngle())
        new_field.SetTextSize(old_field.GetTextSize())
        new_field.SetTextThickness(old_field.GetTextThickness())
        new_field.SetLayer(old_field.GetLayer())
        new_field.SetVisible(old_field.IsVisible())


def make_template_uuids_unique(footprint, steps):
    items = [footprint]
    items.extend(footprint.GetFields())
    items.extend(footprint.GraphicalItems())
    items.extend(footprint.FindPadByNumber(number) for number in ("1", "2"))
    for item in items:
        for _ in range(steps):
            item.m_Uuid.Increment()


def main():
    template = pcbnew.FootprintLoad(str(LIBRARY_PATH), FOOTPRINT_NAME)
    if template is None:
        raise SystemExit(f"Could not load {FOOTPRINT_NAME}")

    board = pcbnew.LoadBoard(str(BOARD_PATH))
    if board is None:
        raise SystemExit(f"Could not load {BOARD_PATH}")

    replaced = []
    for reference in REFERENCES:
        old_fp = board.FindFootprintByReference(reference)
        if old_fp is None:
            raise SystemExit(f"Missing footprint {reference}")

        old_pads = {number: old_fp.FindPadByNumber(number) for number in ("1", "2")}
        if any(pad is None for pad in old_pads.values()) or old_fp.GetUniquePadCount() != 2:
            actual_count = old_fp.GetUniquePadCount()
            raise SystemExit(f"{reference}: expected exactly pads 1 and 2, got {actual_count} unique pads")

        new_fp = pcbnew.FOOTPRINT(template)

        new_fp.SetFPIDAsString(f"logger_v1_custom:{FOOTPRINT_NAME}")
        new_fp.SetPosition(old_fp.GetPosition())
        new_fp.SetOrientation(old_fp.GetOrientation())
        new_fp.SetLayer(old_fp.GetLayer())
        new_fp.SetPath(old_fp.GetPath())
        new_fp.SetFields({field.GetName(): field.GetText() for field in old_fp.GetFields()})
        copy_field_appearance(old_fp, new_fp)
        make_template_uuids_unique(new_fp, len(replaced) + 1)

        for number in ("1", "2"):
            new_pad = new_fp.FindPadByNumber(number)
            old_pad = old_pads[number]
            new_pad.SetNet(old_pad.GetNet())

        board.Remove(old_fp)
        board.Add(new_fp)
        replaced.append(reference)

    pcbnew.SaveBoard(str(BOARD_PATH), board)
    print(f"Replaced {', '.join(replaced)} with logger_v1_custom:{FOOTPRINT_NAME}")


if __name__ == "__main__":
    main()
