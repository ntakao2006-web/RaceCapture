"""Assign the procurement footprints for logger_v1.

This is intentionally a one-shot, structure-aware editor for the current KiCad 9
schematic.  It only rewrites top-level symbol instances and the two custom symbol
definitions that need electrical/package corrections.
"""

from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[1]
SCH = ROOT / "logger_v1.kicad_sch"
CUSTOM_SYM = ROOT / "logger_v1_custom.kicad_sym"
DEVICE_SYM = Path.home() / "AppData/Local/Programs/KiCad/9.0/share/kicad/symbols/Device.kicad_sym"


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


def named_block(text: str, marker: str) -> tuple[int, int, str]:
    start = text.index(marker)
    end = block_end(text, start)
    return start, end, text[start:end]


def replace_property(block: str, name: str, value: str) -> str:
    pattern = rf'(\(property "{re.escape(name)}" ")[^"]*(")'
    changed, count = re.subn(pattern, lambda m: m.group(1) + value + m.group(2), block, count=1)
    if count != 1:
        raise ValueError(f"Property {name} not found")
    return changed


def replace_top_level_instances(text: str, callback) -> str:
    starts = [m.start() + 1 for m in re.finditer(r'\n\t\(symbol\n\t\t\(lib_id ', text)]
    for start in reversed(starts):
        end = block_end(text, start)
        block = text[start:end]
        ref_match = re.search(r'\(property "Reference" "([^"]+)"', block)
        if ref_match:
            text = text[:start] + callback(ref_match.group(1), block) + text[end:]
    return text


def remove_top_level_uuid(text: str, uuid: str) -> str:
    starts = [m.start() + 1 for m in re.finditer(r'\n\t\((?:wire|label|symbol)\b', text)]
    for start in reversed(starts):
        end = block_end(text, start)
        if f'"{uuid}"' in text[start:end]:
            return text[:start] + text[end:]
    raise ValueError(f"Top-level UUID {uuid} not found")


fixed_resistor_fp = "Resistor_SMD:R_0603_1608Metric"
axial_resistor_fp = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
footprints = {
    "BT1": "logger_v1_custom:BatteryHolder_CH004-2032LF",
    "C1": "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm",
    "C4": "Capacitor_THT:C_Disc_D6.0mm_W4.4mm_P5.00mm",
    "C5": "Capacitor_THT:C_Disc_D7.5mm_W4.4mm_P5.00mm",
    "C8": "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm",
    "C12": "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm",
    "C14": "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm",
    "C16": "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm",
    "C29": "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm",
    "D1": "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal",
    "D13": "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal",
    "D14": "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal",
    "J1": "Connector_PinSocket_2.54mm:PinSocket_1x06_P2.54mm_Vertical",
    "J3": "logger_v1_custom:Molex_47219-2001",
    "J4": "Connector_JST:JST_VH_B4PS-VH_1x04_P3.96mm_Horizontal",
    "J6": "Connector_JST:JST_VH_B4PS-VH_1x04_P3.96mm_Horizontal",
    "J7": "logger_v1_custom:SMA_S-037-TGG_Horizontal",
    "RV1": "Potentiometer_THT:Potentiometer_Runtron_RM-065_Vertical",
    "SW1": "Button_Switch_THT:SW_PUSH_6mm",
    "SW2": "Button_Switch_THT:SW_PUSH_6mm",
    "U1": "Package_TO_SOT_SMD:TO-252-3_TabPin2",
    "U8": "Package_DIP:DIP-16_W7.62mm",
    "U11": "logger_v1_custom:AE_BNO055_BO",
    "Y1": "Crystal:Crystal_HC49-4H_Vertical",
}

for num in range(2, 32):
    ref = f"C{num}"
    if ref not in footprints:
        footprints[ref] = ""  # filled by value below
for num in range(1, 44):
    footprints[f"R{num}"] = ""  # filled by value below
for num in list(range(2, 6)) + list(range(9, 13)):
    footprints[f"D{num}"] = "logger_v1_custom:DF2S23P2CTC_CST2C"

polarized_caps = {"C1", "C8", "C12", "C14", "C16", "C29"}


def edit_instance(ref: str, block: str) -> str:
    value_match = re.search(r'\(property "Value" "([^"]*)"', block)
    value = value_match.group(1) if value_match else ""

    fp = footprints.get(ref)
    if ref.startswith("R") and not fp:
        fp = fixed_resistor_fp if value in {"10k", "49.9k"} else axial_resistor_fp
    if ref.startswith("C") and not fp:
        if value in {"0.1u", "1n", "22p"}:
            fp = "Capacitor_THT:C_Disc_D4.3mm_W1.9mm_P5.00mm"
        elif value == "1u":
            fp = "Capacitor_THT:C_Disc_D6.0mm_W4.4mm_P5.00mm"
    if fp:
        block = replace_property(block, "Footprint", fp)

    if ref in polarized_caps:
        block = re.sub(r'\(lib_id "Device:C_Small"\)', '(lib_id "Device:C_Polarized_Small")', block, count=1)
        block = replace_property(block, "Description", "Polarized capacitor, small symbol")
    if ref == "J3":
        block = re.sub(r'\(lib_id "[^"]+"\)', '(lib_id "logger_v1_custom:Micro_SD_Card_Molex_47219-2001")', block, count=1)
        block = replace_property(block, "Value", "47219-2001")
        block = replace_property(block, "Datasheet", "https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/productspecificationpdf/472/47219/PS-47219-001-001.pdf")
        for pin_no in ("10", "11"):
            for match in reversed(list(re.finditer(rf'\(pin "{pin_no}"\s', block))):
                pin_start = match.start()
                pin_end = block_end(block, pin_start)
                block = block[:pin_start] + block[pin_end:]
    if ref in {"J4", "J6"}:
        block = replace_property(block, "Value", "B4PS-VH(LF)(SN)")
    if ref == "J7":
        block = replace_property(block, "Value", "S-037-TGG")
        block = replace_property(block, "Datasheet", "https://akizukidenshi.com/goodsaffix/S-037-TGG_20220729.pdf")
    if ref == "RV1":
        block = replace_property(block, "Value", "4.7k (TSR-065-472-R)")
        block = replace_property(block, "Datasheet", "https://akizukidenshi.com/catalog/g/g106062/")
    if ref == "U1":
        block = re.sub(r'\(lib_id "logger_v1_custom:NJM78L05UA"\)', '(lib_id "logger_v1_custom:NJM2845DL1-05")', block, count=1)
        block = replace_property(block, "Datasheet", "https://akizukidenshi.com/catalog/g/g111298/")
    if ref == "U8":
        block = replace_property(block, "Value", "CD74HC4053E")
        block = replace_property(block, "Datasheet", "https://akizukidenshi.com/catalog/g/g113266/")
    if ref == "Y1":
        block = replace_property(block, "Value", "HUSG-20.000-20")
        block = replace_property(block, "Datasheet", "https://akizukidenshi.com/catalog/g/g108673/")
    if ref == "BT1":
        block = replace_property(block, "Value", "CH004-2032LF")
        block = replace_property(block, "Datasheet", "https://akizukidenshi.com/catalog/g/g111255/")
    if ref.startswith("D") and ref not in {"D1", "D6", "D7", "D8", "D13", "D14"}:
        block = replace_property(block, "Value", "DF2S23P2CTC")
    if ref in {"F1", "F2"}:
        block = replace_property(block, "Value", "LVR200S (2A hold)")
        block = replace_property(block, "Footprint", "Fuse:Fuse_Littelfuse-LVR200")
    return block


def edit_sd_definition(block: str) -> str:
    block = block.replace("Connector:Micro_SD_Card_Det_Hirose_DM3AT", "logger_v1_custom:Micro_SD_Card_Molex_47219-2001", 1)
    block = block.replace("Micro_SD_Card_Det_Hirose_DM3AT", "Micro_SD_Card_Molex_47219-2001")
    block = replace_property(block, "Value", "47219-2001")
    block = replace_property(block, "Footprint", "logger_v1_custom:Molex_47219-2001")
    block = replace_property(block, "Datasheet", "https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/productspecificationpdf/472/47219/PS-47219-001-001.pdf")
    block = replace_property(block, "Description", "Molex 47219-2001 microSD hinged socket, 8 contacts plus shield, no card detect")
    pins = []
    for match in re.finditer(r'\(pin [a-z_]+ [a-z_]+', block):
        start = match.start()
        end = block_end(block, start)
        pin = block[start:end]
        number = re.search(r'\(number "([^"]+)"', pin)
        if number:
            pins.append((start, end, number.group(1)))
    for start, end, number in reversed(pins):
        if number in {"9", "10"}:
            block = block[:start] + block[end:]
        elif number == "11":
            pin = block[start:end].replace('(number "11"', '(number "9"', 1)
            block = block[:start] + pin + block[end:]
    return block


def edit_njm_definition(block: str, embedded: bool) -> str:
    old = "logger_v1_custom:NJM78L05UA" if embedded else "NJM78L05UA"
    new = "logger_v1_custom:NJM2845DL1-05" if embedded else "NJM2845DL1-05"
    block = block.replace(f'(symbol "{old}"', f'(symbol "{new}"', 1)
    block = block.replace("NJM78L05UA_", "NJM2845DL1-05_")
    block = replace_property(block, "Value", "NJM2845DL1-05")
    block = replace_property(block, "Footprint", "Package_TO_SOT_SMD:TO-252-3_TabPin2")
    block = replace_property(block, "Datasheet", "https://akizukidenshi.com/catalog/g/g111298/")
    block = replace_property(block, "Description", "NJM2845DL1-05 low-dropout 5 V regulator, TO-252-3; pin 1 IN, pin 2 GND/tab, pin 3 OUT")
    # The external legacy symbol had the 78L05 pin order.  NJM2845 uses 1-IN, 2-GND, 3-OUT.
    if not embedded:
        pin_blocks = []
        for match in re.finditer(r'\(pin (?:power_in|power_out) line', block):
            start = match.start()
            end = block_end(block, start)
            pin = block[start:end]
            name = re.search(r'\(name "([^"]+)"', pin).group(1)
            pin_blocks.append((start, end, name))
        for start, end, name in reversed(pin_blocks):
            pin = block[start:end]
            wanted = {"IN": "1", "GND": "2", "OUT": "3"}[name]
            pin = re.sub(r'\(number "[^"]+"', f'(number "{wanted}"', pin, count=1)
            block = block[:start] + pin + block[end:]
    return block


def main() -> None:
    shutil.copy2(SCH, SCH.with_suffix(".pre-footprints.kicad_sch"))
    text = SCH.read_text(encoding="utf-8")

    # Import the stock polarized-capacitor graphic into this self-contained schematic.
    if '(symbol "Device:C_Polarized_Small"' not in text:
        _, _, stock_cap = named_block(DEVICE_SYM.read_text(encoding="utf-8"), '(symbol "C_Polarized_Small"')
        stock_cap = stock_cap.replace('(symbol "C_Polarized_Small"', '(symbol "Device:C_Polarized_Small"', 1)
        lib_start = text.index("\t(lib_symbols")
        lib_end = block_end(text, lib_start)
        stock_cap = "\n".join("\t\t" + line.lstrip("\t") if i == 0 else "\t\t" + line for i, line in enumerate(stock_cap.splitlines()))
        text = text[:lib_end - 1] + "\n" + stock_cap + "\n\t" + text[lib_end - 1:]

    start, end, sd = named_block(text, '(symbol "Connector:Micro_SD_Card_Det_Hirose_DM3AT"')
    text = text[:start] + edit_sd_definition(sd) + text[end:]
    start, end, njm = named_block(text, '(symbol "logger_v1_custom:NJM78L05UA"')
    text = text[:start] + edit_njm_definition(njm, embedded=True) + text[end:]

    text = replace_top_level_instances(text, edit_instance)
    for uuid in (
        "d164cd26-fdb4-4054-bc4f-bea66d640ff8",  # obsolete DET_B-to-GND wire
        "07d1b833-9f76-44c1-b3d1-4c651c4430b3",  # obsolete SD_CD label at socket
        "0118089d-9c58-456e-b6f8-0e8bf2ef1827",  # obsolete DET_B GND symbol
    ):
        text = remove_top_level_uuid(text, uuid)
    SCH.write_text(text, encoding="utf-8", newline="\n")

    # Keep the project symbol library usable when J3/U1 are placed again later.
    custom = CUSTOM_SYM.read_text(encoding="utf-8")
    start, end, njm = named_block(custom, '(symbol "NJM78L05UA"')
    custom = custom[:start] + edit_njm_definition(njm, embedded=False) + custom[end:]
    _, _, sd_embedded = named_block(text, '(symbol "logger_v1_custom:Micro_SD_Card_Molex_47219-2001"')
    sd_external = sd_embedded.replace('(symbol "logger_v1_custom:Micro_SD_Card_Molex_47219-2001"', '(symbol "Micro_SD_Card_Molex_47219-2001"', 1)
    final_close = custom.rfind("\n)")
    custom = custom[:final_close] + "\n" + sd_external + custom[final_close:]
    CUSTOM_SYM.write_text(custom, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
