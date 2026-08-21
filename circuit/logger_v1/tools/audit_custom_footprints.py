"""Audit project-local footprints used by logger_v1.

Checks schematic pin-number coverage, exact critical geometry, and confirms that
the Molex 47219-2001 pads still match KiCad 9's official implementation.
"""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SCH = ROOT / "logger_v1.kicad_sch"
CUSTOM_SYM = ROOT / "logger_v1_custom.kicad_sym"
NETLIST = ROOT / "logger_v1.net"
FP_DIR = ROOT / "logger_v1_custom.pretty"
KICAD_FP = Path.home() / "AppData/Local/Programs/KiCad/9.0/share/kicad/footprints"


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


def blocks(text: str, pattern: str) -> list[str]:
    result = []
    for match in re.finditer(pattern, text):
        start = match.start()
        result.append(text[start:block_end(text, start)])
    return result


def property_value(block: str, name: str) -> str:
    match = re.search(rf'\(property "{re.escape(name)}" "([^"]*)"', block)
    return match.group(1) if match else ""


def pad_numbers(text: str) -> set[str]:
    return {re.match(r'\(pad "([^"]*)"', block).group(1) for block in blocks(text, r'\(pad "')}


def normalized_pads(text: str) -> list[str]:
    result = []
    for block in blocks(text, r'\(pad "'):
        block = re.sub(r'\(uuid "[^"]+"\)', "", block)
        result.append(re.sub(r"\s+", "", block))
    return sorted(result)


def assert_contains(text: str, fragment: str, label: str) -> None:
    if fragment not in re.sub(r"\s+", " ", text):
        raise AssertionError(f"{label}: expected {fragment}")


def main() -> None:
    sch = SCH.read_text(encoding="utf-8")
    starts = [m.start() + 1 for m in re.finditer(r'\n\t\(symbol\n\t\t\(lib_id ', sch)]
    used = []
    for start in starts:
        block = sch[start:block_end(sch, start)]
        fp = property_value(block, "Footprint")
        if not fp.startswith("logger_v1_custom:"):
            continue
        ref = property_value(block, "Reference")
        symbol_pins = set(re.findall(r'\(pin "([^"]+)"', block))
        fp_name = fp.split(":", 1)[1]
        fp_path = FP_DIR / f"{fp_name}.kicad_mod"
        if not fp_path.exists():
            raise AssertionError(f"{ref}: missing {fp_path.name}")
        pads = pad_numbers(fp_path.read_text(encoding="utf-8"))
        missing = symbol_pins - pads
        if missing:
            raise AssertionError(f"{ref}/{fp_name}: symbol pins missing pads: {sorted(missing)}")
        used.append((ref, fp_name, ",".join(sorted(symbol_pins))))

    battery = (FP_DIR / "BatteryHolder_CH004-2032LF.kicad_mod").read_text(encoding="utf-8")
    assert_contains(battery, '(pad "1" smd roundrect (at 13.32 0) (size 3.3 4.1)', "CH004 positive pad")
    assert_contains(battery, '(pad "2" smd roundrect (at -15.93 0) (size 3.3 4.1)', "CH004 negative pad")

    sma = (FP_DIR / "SMA_S-037-TGG_Horizontal.kicad_mod").read_text(encoding="utf-8")
    for xy in ("0 0", "-2.54 -2.54", "2.54 -2.54", "-2.54 2.54", "2.54 2.54"):
        assert_contains(sma, f"(at {xy}) (size 2.5 2.5) (drill 1.5)", f"S-037-TGG hole {xy}")
    for start, end in (
        ("-3.6 -1.3", "-3.6 1.3"),
        ("-1.3 -3.6", "1.3 -3.6"),
        ("-1.3 3.6", "1.3 3.6"),
        ("3.6 -1.3", "3.6 1.3"),
    ):
        assert_contains(
            sma,
            f'(fp_line (start {start}) (end {end}) (stroke (width 0.15)',
            f"S-037-TGG foot-only silk {start} to {end}",
        )
    assert_contains(sma, '(fp_rect (start -3.5 -3.5) (end 11.5 3.5)', "S-037-TGG 15x7 mm fab outline")
    assert_contains(
        sma,
        '(model "${KIPRJMOD}/3dmodels/S-037-TGG_mechanical_proxy_WE60311002114501.step"',
        "S-037-TGG mechanical proxy model",
    )
    if sma.count('(layer "F.SilkS")') != 5:  # reference plus four short foot marks
        raise AssertionError("S-037-TGG silkscreen contains graphics beyond the four foot marks")

    led = (FP_DIR / "LED_D3.0mm_JLCPCB.kicad_mod").read_text(encoding="utf-8")
    assert_contains(led, '(pad "1" thru_hole rect (at 0 0) (size 1.8 1.8) (drill 0.9)', "3 mm LED cathode pad")
    assert_contains(led, '(pad "2" thru_hole circle (at 2.54 0) (size 1.8 1.8) (drill 0.9)', "3 mm LED anode pad")
    assert_contains(led, '(model "${KICAD9_3DMODEL_DIR}/LED_THT.3dshapes/LED_D3.0mm.step"', "3 mm LED model")
    if led.count('(layer "F.SilkS")') != 5:  # reference plus four clearance-safe marks
        raise AssertionError("3 mm LED silkscreen contains unexpected graphics")
    led_assignments = {ref for ref, name, _ in used if name == "LED_D3.0mm_JLCPCB"}
    expected_leds = {f"D{number}" for number in range(4, 12)}
    if led_assignments != expected_leds:
        raise AssertionError(f"3 mm LED assignments differ: {sorted(led_assignments)}")

    official = KICAD_FP / "Connector_Card.pretty/microSD_HC_Molex_47219-2001.kicad_mod"
    local = FP_DIR / "Molex_47219-2001.kicad_mod"
    if normalized_pads(official.read_text(encoding="utf-8")) != normalized_pads(local.read_text(encoding="utf-8")):
        raise AssertionError("Molex 47219-2001 pad geometry differs from KiCad 9 official footprint")

    custom_sym = CUSTOM_SYM.read_text(encoding="utf-8")
    sd_start = custom_sym.index('(symbol "Micro_SD_Card_Molex_47219-2001"')
    sd_symbol = custom_sym[sd_start:block_end(custom_sym, sd_start)]
    expected_sd_pins = {
        "1": "DAT2", "2": "DAT3/CD", "3": "CMD", "4": "VDD", "5": "CLK",
        "6": "VSS", "7": "DAT0", "8": "DAT1", "9": "SHIELD",
    }
    actual_sd_pins = {}
    for pin in blocks(sd_symbol, r'\(pin (?:input|output|bidirectional|tri_state|passive|power_in|power_out|open_collector|open_emitter|no_connect) '):
        name = re.search(r'\(name "([^"]+)"', pin)
        number = re.search(r'\(number "([^"]+)"', pin)
        if name and number:
            actual_sd_pins[number.group(1)] = name.group(1)
    if actual_sd_pins != expected_sd_pins:
        raise AssertionError(f"Molex microSD symbol pin map differs: {actual_sd_pins}")
    netlist = NETLIST.read_text(encoding="utf-8")
    if not re.search(r'\(net \(code "[^"]+"\) \(name "GND"\)[\s\S]*?\(node \(ref "J3"\) \(pin "9"\)', netlist):
        raise AssertionError("J3 shield pin 9 is not connected to GND in exported netlist")

    rm065 = KICAD_FP / "Potentiometer_THT.pretty/Potentiometer_Runtron_RM-065_Vertical.kicad_mod"
    rm065_text = rm065.read_text(encoding="utf-8")
    for pad, xy in (("1", "0 0"), ("2", "2.5 5"), ("3", "5 0")):
        assert_contains(rm065_text, f'(pad "{pad}" thru_hole', f"RM-065 pad {pad}")
        if not re.search(rf'\(pad "{pad}" thru_hole[\s\S]*?\(at {re.escape(xy)}\)', rm065_text):
            raise AssertionError(f"RM-065 pad {pad}: expected location {xy}")

    print(f"PASS: {len(used)} custom-footprint assignments ({len({name for _, name, _ in used})} unique footprints) checked")
    for ref, name, pins in used:
        print(f"  {ref:4} {name:38} pins {pins}")
    print("PASS: CH004-2032LF recommended pad geometry and polarity")
    print("PASS: S-037-TGG five-hole geometry")
    print("PASS: D4-D11 use the 3 mm, 2-pin, pin-1-cathode JLCPCB-safe LED footprint")
    print("PASS: Molex 47219-2001 pads exactly match KiCad 9 official footprint")
    print("PASS: Molex microSD symbol pin map 1-8 plus shield pin 9; shield is on GND")
    print("PASS: KiCad RM-065 pad pattern matches TSR-065 recommended PCB layout")


if __name__ == "__main__":
    main()
