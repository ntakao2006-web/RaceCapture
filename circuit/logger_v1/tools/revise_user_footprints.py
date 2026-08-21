"""Apply the user's final package choices to logger_v1.kicad_sch."""

from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[1]
SCH = ROOT / "logger_v1.kicad_sch"
BACKUP = ROOT / "logger_v1.pre-user-revision.kicad_sch"

FP_R_1608 = "Resistor_SMD:R_0603_1608Metric"
FP_R_AXIAL = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
FP_C_SMALL = "Capacitor_THT:C_Disc_D4.3mm_W1.9mm_P5.00mm"
FP_RV = "Potentiometer_THT:Potentiometer_Runtron_RM-065_Vertical"
FP_BATTERY = "logger_v1_custom:BatteryHolder_CH004-2032LF"


def block_end(text: str, start: int) -> int:
    depth = 0
    quoted = False
    escaped = False
    for pos in range(start, len(text)):
        ch = text[pos]
        if quoted:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return pos + 1
    raise ValueError(f"Unterminated block at {start}")


def property_value(block: str, name: str) -> str:
    match = re.search(rf'\(property "{re.escape(name)}" "([^"]*)"', block)
    if not match:
        raise ValueError(f"Property {name} not found")
    return match.group(1)


def replace_property(block: str, name: str, value: str) -> str:
    pattern = rf'(\(property "{re.escape(name)}" ")[^"]*(")'
    changed, count = re.subn(pattern, lambda m: m.group(1) + value + m.group(2), block, count=1)
    if count != 1:
        raise ValueError(f"Property {name} not found")
    return changed


def edit_instance(ref: str, block: str) -> str:
    value = property_value(block, "Value")

    if re.fullmatch(r"R\d+", ref):
        fp = FP_R_1608 if value in {"10k", "49.9k"} else FP_R_AXIAL
        block = replace_property(block, "Footprint", fp)
    elif re.fullmatch(r"C\d+", ref) and value in {"0.1u", "1n", "22p"}:
        block = replace_property(block, "Footprint", FP_C_SMALL)
    elif ref == "RV1":
        block = replace_property(block, "Value", "4.7k (TSR-065-472-R)")
        block = replace_property(block, "Footprint", FP_RV)
        block = replace_property(block, "Datasheet", "https://akizukidenshi.com/catalog/g/g106062/")
    elif ref == "BT1":
        block = replace_property(block, "Value", "CH004-2032LF")
        block = replace_property(block, "Footprint", FP_BATTERY)
        block = replace_property(block, "Datasheet", "https://akizukidenshi.com/catalog/g/g111255/")
    return block


def main() -> None:
    if not BACKUP.exists():
        shutil.copy2(SCH, BACKUP)
    text = SCH.read_text(encoding="utf-8")
    starts = [m.start() + 1 for m in re.finditer(r'\n\t\(symbol\n\t\t\(lib_id ', text)]
    changed = 0
    for start in reversed(starts):
        end = block_end(text, start)
        block = text[start:end]
        ref_match = re.search(r'\(property "Reference" "([^"]+)"', block)
        if not ref_match:
            continue
        edited = edit_instance(ref_match.group(1), block)
        if edited != block:
            changed += 1
            text = text[:start] + edited + text[end:]
    SCH.write_text(text, encoding="utf-8", newline="\n")
    print(f"Updated {changed} schematic symbol instances")


if __name__ == "__main__":
    main()
