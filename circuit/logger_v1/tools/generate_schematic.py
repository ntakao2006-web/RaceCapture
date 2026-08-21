from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CUSTOM_LIB = ROOT / "logger_v1_custom.kicad_sym"
CUSTOM_FP = ROOT / "logger_v1_custom.pretty"
KICAD_SYMBOLS = Path(
    os.environ.get(
        "LOGGER_V1_KICAD_SYMBOLS",
        r"C:\Users\lintaroh\AppData\Local\Programs\KiCad\9.0\share\kicad\symbols",
    )
)


def effects(hidden: bool = False, italic: bool = False) -> str:
    extra = "\n        (hide yes)" if hidden else ""
    italic_s = "\n          (italic yes)" if italic else ""
    return f"""(effects
        (font
          (size 1.27 1.27){italic_s}
        ){extra}
      )"""


def property_s(name: str, value: str, x: float, y: float, hidden: bool = False) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'''    (property "{name}" "{escaped}"
      (at {x:g} {y:g} 0)
      {effects(hidden=hidden)}
    )'''


def pin_s(number: str, name: str, electrical: str, x: float, y: float, angle: int) -> str:
    return f'''      (pin {electrical} line
        (at {x:g} {y:g} {angle})
        (length 2.54)
        (name "{name}" {effects()})
        (number "{number}" {effects()})
      )'''


def module_symbol(
    name: str,
    reference: str,
    footprint: str,
    datasheet: str,
    description: str,
    pins: dict[str, list[tuple[str, str, str]]],
    width: float = 25.4,
) -> str:
    max_side = max(len(pins.get(side, [])) for side in ("left", "right", "top", "bottom"))
    height = max(12.7, (max_side + 1) * 2.54)
    hw, hh = width / 2, height / 2
    ref_y, val_y = hh + 2.54, -hh - 2.54
    lines = [
        f'  (symbol "{name}"',
        "    (pin_names (offset 1.016))",
        "    (exclude_from_sim no)",
        "    (in_bom yes)",
        "    (on_board yes)",
        property_s("Reference", reference, -hw, ref_y),
        property_s("Value", name, 0, val_y),
        property_s("Footprint", footprint, 0, 0, hidden=True),
        property_s("Datasheet", datasheet, 0, 0, hidden=True),
        property_s("Description", description, 0, 0, hidden=True),
        f'''    (symbol "{name}_0_1"
      (rectangle
        (start {-hw:g} {hh:g})
        (end {hw:g} {-hh:g})
        (stroke (width 0.254) (type default))
        (fill (type background))
      )
    )''',
        f'    (symbol "{name}_1_1"',
    ]

    def centered(count: int) -> list[float]:
        return [((count - 1) / 2 - i) * 2.54 for i in range(count)]

    for (num, pin_name, etype), y in zip(pins.get("left", []), centered(len(pins.get("left", [])))):
        lines.append(pin_s(num, pin_name, etype, -hw - 2.54, y, 0))
    for (num, pin_name, etype), y in zip(pins.get("right", []), centered(len(pins.get("right", [])))):
        lines.append(pin_s(num, pin_name, etype, hw + 2.54, y, 180))
    for (num, pin_name, etype), x in zip(pins.get("top", []), centered(len(pins.get("top", [])))):
        lines.append(pin_s(num, pin_name, etype, x, hh + 2.54, 270))
    for (num, pin_name, etype), x in zip(pins.get("bottom", []), centered(len(pins.get("bottom", [])))):
        lines.append(pin_s(num, pin_name, etype, x, -hh - 2.54, 90))
    lines += ["    )", "    (embedded_fonts no)", "  )"]
    return "\n".join(lines)


def write_symbol_library() -> None:
    symbols: list[str] = [
        module_symbol(
            "LDR6321",
            "U",
            "Package_SO:SSOP-16_4.4x5.2mm_P0.65mm",
            "https://akizukidenshi.com/goodsaffix/ldr6321.pdf",
            "USB PD/QC/AFC sink controller, maximum request configured for 12 V",
            {
                "left": [("2", "VCON0", "input"), ("3", "VCON1", "input"), ("4", "VCON2", "input"), ("5", "EN_D+", "output"), ("6", "QC_EN+", "output"), ("7", "DOWN_D+", "output"), ("8", "QC_EN-", "output")],
                "right": [("9", "ADC_D-", "input"), ("10", "UP_D-", "output"), ("11", "VBUSEN", "output"), ("12", "CC2", "bidirectional"), ("13", "CC1", "bidirectional"), ("14", "VREF", "input")],
                "top": [("16", "VDD", "power_in"), ("15", "PDLDO", "power_out")],
                "bottom": [("1", "VSS", "power_in")],
            },
            width=30.48,
        ),
        module_symbol(
            "NJM78L05UA",
            "U",
            "Package_TO_SOT_SMD:SOT-89-3",
            "https://akizukidenshi.com/goodsaffix/njm78lxx.pdf",
            "5 V 100 mA regulator for LDR6321",
            {
                "left": [("3", "IN", "power_in")],
                "right": [("1", "OUT", "power_out")],
                "top": [],
                "bottom": [("2", "GND", "power_in")],
            },
        ),
        module_symbol(
            "TCKE800NL",
            "U",
            "logger_v1_custom:TCKE800NL_WSON10B",
            "https://akizukidenshi.com/goodsaffix/TCKE800NL.pdf",
            "18 V 5 A latched eFuse, bare WSON10B device",
            {
                "left": [("2", "EN/UVLO", "input"), ("3", "VIN", "power_in"), ("4", "VIN", "power_in"), ("5", "VIN", "power_in")],
                "right": [("6", "VOUT", "passive"), ("7", "VOUT", "passive"), ("8", "VOUT", "passive"), ("9", "EFET", "output")],
                "top": [],
                "bottom": [("1", "dV/dT", "passive"), ("10", "ILIM", "passive"), ("11", "GND", "power_in")],
            },
            width=30.48,
        ),
        module_symbol(
            "OKL-T-6-W12N-C",
            "U",
            "logger_v1_custom:OKL_T_6_W12N_C",
            "https://akizukidenshi.com/goodsaffix/OKL_T6_W12.pdf",
            "6 A adjustable non-isolated buck converter, negative enable logic",
            {
                "left": [("2", "VIN", "power_in"), ("1", "ON/OFF", "input")],
                "right": [("4", "VOUT", "passive"), ("5", "SENSE", "input"), ("10", "PGOOD", "open_collector")],
                "top": [("8", "NC", "no_connect"), ("9", "SEQUENCE", "no_connect"), ("11", "NC", "no_connect"), ("12", "NC", "no_connect")],
                "bottom": [("3", "GND", "power_in"), ("7", "GND", "power_in"), ("6", "TRIM", "passive")],
            },
            width=30.48,
        ),
        module_symbol(
            "D36V50F5",
            "U",
            "logger_v1_custom:Pololu_D36V50F5",
            "https://www.pololu.com/product/4091",
            "Pololu 5 V 5.5 A step-down regulator module",
            {
                "left": [("1", "EN", "input"), ("2", "PG", "open_collector")],
                "right": [("11", "VOUT", "passive"), ("12", "VOUT", "passive")],
                "top": [("3", "VRP", "power_out"), ("4", "VRP", "power_out"), ("5", "VIN", "power_in"), ("6", "VIN", "power_in")],
                "bottom": [("7", "GND", "passive"), ("8", "GND", "passive"), ("9", "GND", "passive"), ("10", "GND", "passive")],
            },
            width=30.48,
        ),
        module_symbol(
            "AE-eFuse-TCKE800N-BO",
            "U",
            "logger_v1_custom:AE_eFuse_TCKE800N_BO",
            "https://akizukidenshi.com/goodsaffix/AE-eFuse-TCKE800N-BO_sch.pdf",
            "Akizuki TCKE800N electronic fuse breakout board",
            {
                "left": [("1", "dV/dT", "passive"), ("2", "EN/UVLO", "input"), ("3", "VIN", "power_in"), ("4", "VIN", "power_in")],
                "right": [("5", "VOUT", "passive"), ("6", "VOUT", "passive"), ("7", "VOUT", "passive"), ("8", "ILIM", "passive")],
                "top": [],
                "bottom": [],
            },
            width=30.48,
        ),
        module_symbol(
            "XC8114AA01PR-G",
            "U",
            "Package_TO_SOT_SMD:SOT-89-5",
            "https://product.torexsemi.com/system/files/series/xc8114.pdf",
            "3 A ideal-diode load switch with true reverse blocking",
            {
                "left": [("4", "VIN", "power_in"), ("3", "EN", "input")],
                "right": [("5", "VOUT", "passive")],
                "top": [],
                "bottom": [("1", "VSS", "power_in"), ("2", "EP", "power_in")],
            },
        ),
        module_symbol(
            "XC8107AC20MR-G",
            "U",
            "Package_TO_SOT_SMD:SOT-23-5",
            "https://akizukidenshi.com/goodsaffix/xc8107.pdf",
            "2 A USB VBUS source switch with current limit and reverse blocking",
            {
                "left": [("5", "VIN", "power_in"), ("4", "CE", "input")],
                "right": [("1", "VOUT", "power_out"), ("3", "~FLG", "open_collector")],
                "top": [],
                "bottom": [("2", "VSS", "power_in")],
            },
        ),
        module_symbol(
            "PEC3824C2A-AU",
            "D",
            "Package_TO_SOT_SMD:SOT-23",
            "https://akizukidenshi.com/goodsaffix/PEC3808C2A-AU_SERIES.pdf",
            "Dual bidirectional 24 V TVS for CAN bus",
            {
                "left": [("1", "LINE1", "passive"), ("2", "LINE2", "passive")],
                "right": [],
                "top": [],
                "bottom": [("3", "GND", "passive")],
            },
        ),
        module_symbol(
            "AE-LXDC55-3.3V",
            "U",
            "logger_v1_custom:AE_LXDC55_3V3",
            "https://akizukidenshi.com/goodsaffix/AE-LXDC55-3V3-rev1.pdf",
            "Akizuki 3.3 V 1.5 A step-down converter module",
            {
                "left": [("1", "IN", "power_in")],
                "right": [("3", "OUT", "power_out")],
                "top": [],
                "bottom": [("2", "GND", "power_in")],
            },
        ),
        module_symbol(
            "AE-BNO055-BO",
            "U",
            "logger_v1_custom:AE_BNO055_BO",
            "https://akizukidenshi.com/goodsaffix/AE-BNO055-BO_20220413.pdf",
            "Akizuki BNO055 9-axis sensor fusion module",
            {
                "left": [("3", "SDA/TX", "bidirectional"), ("4", "SCL/RX", "bidirectional"), ("5", "~RESET", "input"), ("6", "INT", "output")],
                "right": [("8", "VOUT_2V8", "power_out")],
                "top": [("1", "VIN", "power_in")],
                "bottom": [("2", "GND", "power_in"), ("7", "GND", "power_in")],
            },
        ),
        module_symbol(
            "Teseo-LIV3FL",
            "U",
            "logger_v1_custom:Teseo_LIV3FL_LCC18",
            "https://www.st.com/resource/en/datasheet/teseo-liv3fl.pdf",
            "ST 10 Hz multi-constellation GNSS module, LCC-18",
            {
                "left": [("2", "TX", "output"), ("3", "RX", "input"), ("4", "1PPS", "output"), ("5", "WAKE_UP", "input"), ("9", "~RESET", "input"), ("16", "SDA", "bidirectional"), ("17", "SCL", "bidirectional")],
                "right": [("11", "RF_IN", "input"), ("13", "ANT_OFF", "output"), ("14", "VCC_RF", "power_out"), ("15", "RESERVED", "no_connect"), ("18", "RESERVED", "no_connect")],
                "top": [("6", "VBATT", "power_in"), ("7", "VCC_IO", "power_in"), ("8", "VCC", "power_in")],
                "bottom": [("1", "GND", "power_in"), ("10", "GND_RF", "power_in"), ("12", "GND_RF", "power_in")],
            },
            width=30.48,
        ),
        module_symbol(
            "MCP2562FD-E-P",
            "U",
            "Package_DIP:DIP-8_W7.62mm",
            "https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/20005284A.pdf",
            "High-speed CAN FD transceiver with VIO, DIP-8",
            {
                "left": [("1", "TXD", "input"), ("4", "RXD", "output"), ("8", "STBY", "input")],
                "right": [("7", "CANH", "bidirectional"), ("6", "CANL", "bidirectional")],
                "top": [("3", "VDD", "power_in"), ("5", "VIO", "power_in")],
                "bottom": [("2", "VSS", "power_in")],
            },
        ),
    ]
    CUSTOM_LIB.write_text(
        "(kicad_symbol_lib\n  (version 20241209)\n  (generator \"kicad_symbol_editor\")\n  (generator_version \"9.0\")\n"
        + "\n".join(symbols)
        + "\n)\n",
        encoding="utf-8",
    )


def pad(number: str, x: float, y: float, size: float = 2.0, drill: float = 1.0, shape: str = "circle") -> str:
    return f'  (pad "{number}" thru_hole {shape} (at {x:g} {y:g}) (size {size:g} {size:g}) (drill {drill:g}) (layers "*.Cu" "*.Mask"))'


def fp_header(name: str, descr: str, ref_at: tuple[float, float], val_at: tuple[float, float], attr: str = "through_hole") -> str:
    return f'''(footprint "{name}"
  (version 20241229)
  (generator "pcbnew")
  (layer "F.Cu")
  (descr "{descr}")
  (property "Reference" "REF**" (at {ref_at[0]:g} {ref_at[1]:g} 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
  (property "Value" "{name}" (at {val_at[0]:g} {val_at[1]:g} 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
  (attr {attr})'''


def rect_lines(x1: float, y1: float, x2: float, y2: float, layer: str = "F.SilkS", width: float = 0.15) -> str:
    pts = [((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))]
    return "\n".join(
        f'  (fp_line (start {a[0]:g} {a[1]:g}) (end {b[0]:g} {b[1]:g}) (stroke (width {width:g}) (type solid)) (layer "{layer}"))'
        for a, b in pts
    )


def write_footprints() -> None:
    CUSTOM_FP.mkdir(exist_ok=True)

    # Toshiba WSON10B reference land pattern: 0.5 mm pitch, 0.85 x 0.28 mm
    # perimeter lands and the exposed GND thermal land shown on DS p.23.
    tcke = [fp_header("TCKE800NL_WSON10B", "Toshiba TCKE800NL WSON10B 3 x 3 mm", (0, -3.0), (0, 3.0), attr="smd")]
    tcke += [rect_lines(-1.5, -1.5, 1.5, 1.5, layer="F.Fab", width=0.1)]
    for n, y in zip(range(1, 6), (-1.0, -0.5, 0.0, 0.5, 1.0)):
        tcke.append(f'  (pad "{n}" smd roundrect (at -1.475 {y:g}) (size 0.85 0.28) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))')
    for n, y in zip(range(10, 5, -1), (-1.0, -0.5, 0.0, 0.5, 1.0)):
        tcke.append(f'  (pad "{n}" smd roundrect (at 1.475 {y:g}) (size 0.85 0.28) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))')
    tcke.append('  (pad "11" smd rect (at 0 0) (size 1.65 2.4) (layers "F.Cu" "F.Paste" "F.Mask"))')
    tcke.append('  (pad "11" smd rect (at 0 -1.55) (size 0.28 0.7) (layers "F.Cu" "F.Paste" "F.Mask"))')
    tcke.append('  (pad "11" smd rect (at 0 1.55) (size 0.28 0.7) (layers "F.Cu" "F.Paste" "F.Mask"))')
    tcke.append(")\n")
    (CUSTOM_FP / "TCKE800NL_WSON10B.kicad_mod").write_text("\n".join(tcke), encoding="utf-8")

    # OKL-T/6-W12 iLGA recommended footprint, redrawn from Murata Figure 3.
    # The large 2/3/4 power lands and all nine 1.14 mm square signal lands
    # follow the 12.40 mm through-board view dimensions.
    okl = [fp_header("OKL_T_6_W12N_C", "Murata OKL-T/6-W12N-C 12.2 x 12.2 mm iLGA", (0, -8.0), (0, 8.0), attr="smd")]
    okl += [rect_lines(-6.1, -6.1, 6.1, 6.1, layer="F.Fab", width=0.1)]
    okl.append('  (pad "2" smd rect (at -3.43 -5.15) (size 4.19 1.90) (layers "F.Cu" "F.Paste" "F.Mask"))')
    okl.append('  (pad "3" smd rect (at 1.14 -5.15) (size 4.19 1.90) (layers "F.Cu" "F.Paste" "F.Mask"))')
    okl.append('  (pad "4" smd rect (at 5.15 -3.43) (size 1.90 4.19) (layers "F.Cu" "F.Paste" "F.Mask"))')
    for n, x in [("8", -2.29), ("7", 0), ("12", 2.29)]:
        okl.append(f'  (pad "{n}" smd rect (at {x:g} 5.63) (size 1.14 1.14) (layers "F.Cu" "F.Paste" "F.Mask"))')
    for n, y in [("1", -1.145), ("10", 1.145), ("9", 3.435)]:
        okl.append(f'  (pad "{n}" smd rect (at -5.63 {y:g}) (size 1.14 1.14) (layers "F.Cu" "F.Paste" "F.Mask"))')
    for n, y in [("5", -1.145), ("11", 1.145), ("6", 3.435)]:
        okl.append(f'  (pad "{n}" smd rect (at 5.63 {y:g}) (size 1.14 1.14) (layers "F.Cu" "F.Paste" "F.Mask"))')
    okl.append(")\n")
    (CUSTOM_FP / "OKL_T_6_W12N_C.kicad_mod").write_text("\n".join(okl), encoding="utf-8")

    # Official top view, with pin 1 (EN) as the local origin.  The inner pin
    # row and the body extend toward negative Y; this is intentionally not a
    # mirrored bottom-view land pattern.
    d36 = [fp_header("Pololu_D36V50F5", "Pololu D36V50Fx official 25.4 mm module outline and 2.54 mm connector grid", (6.35, 3.5), (6.35, -27.0))]
    d36 += [rect_lines(-6.35, -24.13, 19.05, 1.27)]
    names = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
    i = 0
    for x in [0, 2.54, 5.08, 7.62, 10.16, 12.70]:
        for y in [0, -2.54]:
            d36.append(pad(names[i], x, y, size=2.0, drill=1.02, shape="rect" if names[i] == "1" else "circle"))
            i += 1
    for x, y in [(-4.15, -0.93), (16.95, -0.93), (16.95, -22.03)]:
        d36.append(f'  (pad "" np_thru_hole circle (at {x:g} {y:g}) (size 2.18 2.18) (drill 2.18) (layers "*.Cu" "*.Mask"))')
    d36.append('  (model "${KIPRJMOD}/3dmodels/d36v50fx.step" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))')
    d36.append(")\n")
    (CUSTOM_FP / "Pololu_D36V50F5.kicad_mod").write_text("\n".join(d36), encoding="utf-8")

    bno = [fp_header("AE_BNO055_BO", "Akizuki AE-BNO055-BO 18 x 11 mm DIP8 module", (3.81, -2.2), (3.81, 10.5)), rect_lines(-5.19, -1.69, 12.81, 9.31)]
    # Official top view: upper row 8..5 and lower row 1..4, both left-to-right.
    for n, x, y in [(8, 0, 0), (7, 2.54, 0), (6, 5.08, 0), (5, 7.62, 0), (1, 0, 7.62), (2, 2.54, 7.62), (3, 5.08, 7.62), (4, 7.62, 7.62)]:
        bno.append(pad(str(n), x, y, shape="rect" if n == 1 else "circle"))
    bno.append(")\n")
    (CUSTOM_FP / "AE_BNO055_BO.kicad_mod").write_text("\n".join(bno), encoding="utf-8")

    ef = [fp_header("AE_eFuse_TCKE800N_BO", "Akizuki AE-eFuse-TCKE800N-BO 18 x 10 mm DIP8 module", (7.62, -2.2), (7.62, 10.5)), rect_lines(-1.38, -1.19, 16.62, 8.81)]
    for n, x, y in [(1, 0, 0), (2, 0, 2.54), (3, 0, 5.08), (4, 0, 7.62), (8, 15.24, 0), (7, 15.24, 2.54), (6, 15.24, 5.08), (5, 15.24, 7.62)]:
        ef.append(pad(str(n), x, y, shape="rect" if n == 1 else "circle"))
    ef.append(")\n")
    (CUSTOM_FP / "AE_eFuse_TCKE800N_BO.kicad_mod").write_text("\n".join(ef), encoding="utf-8")

    lx = [fp_header("AE_LXDC55_3V3", "Akizuki AE-LXDC55 11 x 25 mm SIP3 module", (2.54, -3), (2.54, 27)), rect_lines(-2.96, -1.5, 8.04, 23.5)]
    for n, x in [(1, 0), (2, 2.54), (3, 5.08)]:
        lx.append(pad(str(n), x, 0, shape="rect" if n == 1 else "circle"))
    lx.append(")\n")
    (CUSTOM_FP / "AE_LXDC55_3V3.kicad_mod").write_text("\n".join(lx), encoding="utf-8")

    teseo = [fp_header("Teseo_LIV3FL_LCC18", "ST Teseo-LIV3FL LCC-18, 10.1 x 9.7 mm", (0, -6.5), (0, 6.5), attr="smd"), rect_lines(-5.05, -4.85, 5.05, 4.85)]
    # UM2980 recommended land pattern, top view: two rows of nine 0.9 x 1.6 mm pads at 1.1 mm pitch.
    # The top row is numbered 9..1 from left to right; the bottom row is 10..18.
    for n in range(1, 10):
        x = 4.4 - (n - 1) * 1.1
        shape = "roundrect" if n == 1 else "rect"
        rr = " (roundrect_rratio 0.2)" if n == 1 else ""
        teseo.append(f'  (pad "{n}" smd {shape} (at {x:g} -3.8) (size 0.9 1.6) (layers "F.Cu" "F.Paste" "F.Mask"){rr})')
    for n in range(10, 19):
        x = -4.4 + (n - 10) * 1.1
        teseo.append(f'  (pad "{n}" smd rect (at {x:g} 3.8) (size 0.9 1.6) (layers "F.Cu" "F.Paste" "F.Mask"))')
    teseo.append(")\n")
    (CUSTOM_FP / "Teseo_LIV3FL_LCC18.kicad_mod").write_text("\n".join(teseo), encoding="utf-8")

    # HRO 5077CR-16-SMC2-BK-TR, redrawn from the official Akizuki drawing.
    # Contact and shell geometry matches the 8.94 x 7.35 mm mechanical outline.
    usb = [fp_header("USB_C_5077CR-16-SMC2-BK-TR", "HRO 5077CR USB 2.0 Type-C receptacle", (0, -5.6), (0, 5.0), attr="smd")]
    usb += [rect_lines(-4.47, -3.675, 4.47, 3.675, layer="F.Fab", width=0.1)]
    usb += [rect_lines(-4.7, -4.7, 4.7, 3.9, layer="F.CrtYd", width=0.05)]
    usb += [
        '  (fp_line (start -4.7 -1.78) (end -4.7 0) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))',
        '  (fp_line (start 4.7 -1.78) (end 4.7 0) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))',
    ]
    contacts = [
        ("A1", -3.2, 0.6), ("A4", -2.4, 0.6), ("A5", -1.25, 0.3), ("A6", -0.25, 0.3),
        ("A7", 0.25, 0.3), ("A8", 1.25, 0.3), ("A9", 2.4, 0.6), ("A12", 3.2, 0.6),
        ("B1", 3.2, 0.6), ("B4", 2.4, 0.6), ("B5", 1.75, 0.3), ("B6", 0.75, 0.3),
        ("B7", -0.75, 0.3), ("B8", -1.75, 0.3), ("B9", -2.4, 0.6), ("B12", -3.2, 0.6),
    ]
    for number, x, w in contacts:
        usb.append(f'  (pad "{number}" smd roundrect (at {x:g} -3.745) (size {w:g} 1.3) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))')
    for x in (-2.89, 2.89):
        usb.append(f'  (pad "" np_thru_hole circle (at {x:g} -2.605) (size 0.65 0.65) (drill 0.65) (layers "*.Mask"))')
    for x in (-4.32, 4.32):
        usb.append(f'  (pad "S1" thru_hole oval (at {x:g} -3.105) (size 1 2.1) (drill oval 0.6 1.7) (layers "*.Cu" "*.Mask"))')
        usb.append(f'  (pad "S1" thru_hole oval (at {x:g} 1.075) (size 1 1.8) (drill oval 0.6 1.4) (layers "*.Cu" "*.Mask"))')
    usb.append(")\n")
    (CUSTOM_FP / "USB_C_5077CR-16-SMC2-BK-TR.kicad_mod").write_text("\n".join(usb), encoding="utf-8")

    # SS-12D00G3: 1P2T slide switch, 2.5 mm pin pitch.
    sw = [fp_header("SS-12D00G3", "1P2T through-hole slide switch, 8.5 x 3.7 mm", (2.5, -3.0), (2.5, 3.2)), rect_lines(-1.75, -1.85, 6.75, 1.85)]
    for n, x in [(1, 0), (2, 2.5), (3, 5.0)]:
        sw.append(pad(str(n), x, 0, size=1.4, drill=0.8, shape="rect" if n == 1 else "circle"))
    sw.append(")\n")
    (CUSTOM_FP / "SS-12D00G3.kicad_mod").write_text("\n".join(sw), encoding="utf-8")

    # Murata DLW21SN67x, 2.0 x 1.2 mm common-mode choke.
    cmc = [fp_header("DLW21SN670SQ2L", "Murata DLW21S 2.0 x 1.2 mm common-mode choke", (0, -2.1), (0, 2.1), attr="smd")]
    cmc += [rect_lines(-1.0, -0.6, 1.0, 0.6, layer="F.Fab", width=0.1)]
    for n, x, y in [(1, -0.75, -0.45), (2, 0.75, -0.45), (3, 0.75, 0.45), (4, -0.75, 0.45)]:
        cmc.append(f'  (pad "{n}" smd roundrect (at {x:g} {y:g}) (size 0.8 0.55) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))')
    cmc.append(")\n")
    (CUSTOM_FP / "DLW21SN670SQ2L.kicad_mod").write_text("\n".join(cmc), encoding="utf-8")

    # Murata PLT10HN450180P0B recommended PCB hole pattern (bottom view):
    # 12.7 x 4.2 mm centres, four 1.6 mm holes; winding pairs are 1-2 and 4-3.
    plt = [fp_header("PLT10HN450180P0", "Murata PLT10HN high-current common-mode choke", (6.35, -2.6), (6.35, 7.0)), rect_lines(-0.1, -1.2, 12.8, 5.4)]
    for n, x, y in [(1, 0, 0), (2, 12.7, 0), (3, 12.7, 4.2), (4, 0, 4.2)]:
        plt.append(pad(str(n), x, y, size=3.0, drill=1.6, shape="rect" if n == 1 else "circle"))
    plt.append(")\n")
    (CUSTOM_FP / "PLT10HN450180P0.kicad_mod").write_text("\n".join(plt), encoding="utf-8")

    # Toshiba DF2S23P2CTC input TVS (CST2C, 1.6 x 0.8 mm).
    tvs = [fp_header("DF2S23P2CTC_CST2C", "Toshiba DF2S23P2CTC CST2C TVS", (0, -1.8), (0, 1.8), attr="smd"), rect_lines(-0.8, -0.4, 0.8, 0.4, layer="F.Fab", width=0.1)]
    tvs.append('  (pad "1" smd roundrect (at -0.65 0) (size 0.8 0.9) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))')
    tvs.append('  (pad "2" smd roundrect (at 0.65 0) (size 0.8 0.9) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))')
    tvs.append(")\n")
    (CUSTOM_FP / "DF2S23P2CTC_CST2C.kicad_mod").write_text("\n".join(tvs), encoding="utf-8")

    fuse = [fp_header("Keystone_3557-15", "Keystone low-profile blade fuse holder 3557-15, official drawing", (6.735, -4.8), (6.735, 5.2)), rect_lines(-3.17, -3.365, 16.64, 3.365)]
    for n, x in [(1, 0), (2, 13.47)]:
        for y in [-1.70, 1.70]:
            fuse.append(pad(str(n), x, y, size=3.0, drill=1.6, shape="rect" if n == 1 and y < 0 else "circle"))
    fuse.append(")\n")
    (CUSTOM_FP / "Keystone_3557-15.kicad_mod").write_text("\n".join(fuse), encoding="utf-8")


def build_schematic() -> None:
    """Generate the compact, A1, procurement-constrained logger schematic."""
    write_symbol_library()
    write_footprints()
    os.environ["KICAD_SYMBOL_DIR"] = os.pathsep.join([str(KICAD_SYMBOLS), str(ROOT)])

    import kicad_sch_api as ksa

    sch = ksa.create_schematic("RaceCapture compatible logger v1")
    sch.set_paper_size("A1")
    sch.set_title_block(
        title="RaceCapture Compatible Data Logger / ESP32-S3",
        date="2026-08-14",
        rev="A / v1",
        company="",
        comments={
            1: "All specified purchasable parts: Akizuki Denshi, checked 2026-08-14",
            2: "USB-C J2 is a dedicated OTG host/source port; board power enters only at J1",
            3: "IC decoupling capacitors and functional RC, crystal and VBUS capacitors are shown",
        },
    )

    power_counter = 1
    std_power = {"+5V", "+3V3", "GND", "PWR_FLAG"}
    # Keep discrete passives compact.  R_Small_US is used explicitly for the
    # requested US resistor style; other passives use the matching KiCad
    # Small symbol where pin numbering is compatible.
    small_passive_symbols = {
        "Device:R": "Device:R_Small_US",
        "Device:C": "Device:C_Small",
        "Device:C_Polarized": "Device:C_Polarized_Small",
        "Device:D": "Device:D_Small",
        "Device:D_Zener": "Device:D_Zener_Small",
        "Device:Fuse": "Device:Fuse_Small",
        "Device:L": "Device:L_Small",
        "Device:L_Coupled": "Device:L_Coupled_Small",
    }

    def add(ref: str, lib: str, value: str, x: float, y: float, footprint: str = "", rotation: float = 0, **props):
        lib = small_passive_symbols.get(lib, lib)
        return sch.components.add(
            lib_id=lib,
            reference=ref,
            value=value,
            position=(x, y),
            footprint=footprint or None,
            rotation=rotation,
            **props,
        )

    def pos(ref: str, pin_num: str | int) -> tuple[float, float]:
        p = sch.get_component_pin_position(ref, str(pin_num))
        if p is None:
            raise RuntimeError(f"No pin {ref}.{pin_num}")
        return (p.x, p.y)

    def wire_path(*points: tuple[float, float]) -> None:
        for a, b in zip(points, points[1:]):
            if abs(a[0] - b[0]) > 0.01 and abs(a[1] - b[1]) > 0.01:
                raise RuntimeError(f"Non-orthogonal wire requested: {a} -> {b}")
            sch.add_wire(a, b)

    def wire_pins(ref1: str, pin1: str | int, ref2: str, pin2: str | int, via: list[tuple[float, float]] | None = None) -> None:
        p1, p2 = pos(ref1, pin1), pos(ref2, pin2)
        if via:
            wire_path(p1, *via, p2)
        elif abs(p1[0] - p2[0]) > 0.01 and abs(p1[1] - p2[1]) > 0.01:
            wire_path(p1, (p2[0], p1[1]), p2)
        else:
            wire_path(p1, p2)

    def junction(point: tuple[float, float]) -> None:
        if sch.junctions.get_at_position(point) is None:
            sch.junctions.add(point)

    LOCAL_LABEL_SIZE_MM = 1.27  # 50 mil

    def local_at(
        x: float,
        y: float,
        net_name: str,
        rotation: float = 0,
        justify_h: str = "left",
        size: float = LOCAL_LABEL_SIZE_MM,
    ) -> None:
        # Keep every local-net label at the requested 50 mil, including callers
        # that still pass a legacy visual-size hint.
        sch.labels.add(
            net_name,
            (x, y),
            rotation=rotation,
            size=LOCAL_LABEL_SIZE_MM,
            justify_h=justify_h,
        )

    def local_pin(ref: str, pin_num: str | int, net_name: str) -> None:
        sch.add_label(net_name, pin=(ref, str(pin_num)), size=LOCAL_LABEL_SIZE_MM)

    def stub(
        ref: str,
        pin_num: str | int,
        net_name: str,
        dx: float = 0,
        dy: float = 0,
        size: float = 1.15,
    ) -> None:
        p = pos(ref, pin_num)
        end = (p[0] + dx, p[1] + dy)
        wire_path(p, end)
        if dx < 0:
            local_at(end[0], end[1], net_name, justify_h="right", size=size)
        else:
            local_at(end[0], end[1], net_name, size=size)

    def rail_stub(
        ref: str,
        pin_num: str | int,
        rail: str,
        dx: float = 0,
        dy: float = 0,
        size: float = 1.15,
    ) -> None:
        """Move a rail marker or local label away from a crowded symbol pin."""
        p = pos(ref, pin_num)
        end = (p[0] + dx, p[1] + dy)
        wire_path(p, end)
        if rail in std_power:
            pwr_at(end, rail)
        elif dx < 0:
            local_at(end[0], end[1], rail, justify_h="right", size=size)
        else:
            local_at(end[0], end[1], rail, size=size)

    def place_fields(
        ref: str,
        reference_at: tuple[float, float],
        value_at: tuple[float, float],
    ) -> None:
        """Put Reference and Value on separate, explicitly positioned rows."""
        component = sch.components.get(ref)
        component.set_property_effects(
            "Reference", {"position": reference_at, "justify_h": "left", "rotation": 0}
        )
        component.set_property_effects(
            "Value", {"position": value_at, "justify_h": "left", "rotation": 0}
        )

    def local_pin_bus(
        ref: str,
        pin_nums: tuple[str | int, ...],
        net_name: str,
        dx: float,
        size: float = 0.8,
        label_y: float | None = None,
    ) -> None:
        """Join adjacent same-net pins at a short external bus and label once."""
        pins = [pos(ref, pin_num) for pin_num in pin_nums]
        bus_x = pins[0][0] + dx
        for pin in pins:
            wire_path(pin, (bus_x, pin[1]))
        if len(pins) > 1:
            wire_path((bus_x, min(pin[1] for pin in pins)), (bus_x, max(pin[1] for pin in pins)))
        y = label_y if label_y is not None else sum(pin[1] for pin in pins) / len(pins)
        local_at(
            bus_x,
            y,
            net_name,
            justify_h="right" if dx < 0 else "left",
            size=size,
        )

    def left_text(
        text_value: str,
        left: float,
        y: float,
        size: float = 1.27,
        bold: bool = False,
        italic: bool = False,
    ) -> None:
        """Place centre-anchored KiCad text by its intended visible left edge."""
        estimated_width = len(text_value) * size * 0.90
        sch.add_text(
            text_value,
            (left + estimated_width / 2, y),
            size=size,
            bold=bold,
            italic=italic,
        )

    def nc(ref: str, pin_num: str | int) -> None:
        sch.no_connects.add(pos(ref, pin_num))

    def pwr_at(point: tuple[float, float], rail: str, rotation: float = 0) -> None:
        nonlocal power_counter
        if rail not in std_power:
            raise ValueError(f"Only standard KiCad power symbols are allowed: {rail}")
        add(f"#PWR{power_counter:03d}", f"power:{rail}", rail, point[0], point[1], rotation=rotation)
        power_counter += 1

    def pwr_pin(ref: str, pin_num: str | int, rail: str) -> None:
        pwr_at(pos(ref, pin_num), rail)

    def rail_pin(ref: str, pin_num: str | int, rail: str) -> None:
        if rail in std_power:
            pwr_pin(ref, pin_num, rail)
        else:
            local_pin(ref, pin_num, rail)

    def passive_endpoint(
        ref: str,
        pin_num: str | int,
        net_name: str,
        centre: tuple[float, float],
        length: float = 3.81,
    ) -> None:
        """Give a compact passive an explicit, visible wire connection."""
        pin = pos(ref, pin_num)
        vx, vy = pin[0] - centre[0], pin[1] - centre[1]
        if abs(vx) >= abs(vy):
            direction = 1 if vx >= 0 else -1
            end = (pin[0] + direction * length, pin[1])
            justify = "left" if direction > 0 else "right"
        else:
            direction = 1 if vy >= 0 else -1
            end = (pin[0], pin[1] + direction * length)
            justify = "left"
        wire_path(pin, end)
        if net_name in std_power:
            pwr_at(end, net_name)
        else:
            local_at(end[0], end[1], net_name, justify_h=justify, size=0.78)

    def two_pin(
        ref: str,
        lib: str,
        value: str,
        x: float,
        y: float,
        footprint: str,
        net1: str,
        net2: str,
        rotation: float = 0,
    ):
        add(ref, lib, value, x, y, footprint, rotation)
        component_position = sch.components.get(ref).position
        centre = (component_position.x, component_position.y)
        passive_endpoint(ref, 1, net1, centre)
        passive_endpoint(ref, 2, net2, centre)

    def section(title: str, x: float, y: float, w: float, h: float, note: str = "") -> None:
        sch.add_rectangle((x, y), (x + w, y + h), stroke_width=0.20, stroke_type="dash", fill_type="none")
        # KiCad free text is centre-anchored. Estimate the rendered width so
        # the visible left edge, rather than its centre, starts inside the box.
        title_size = 2.0
        title_width = min(w - 16, len(title) * title_size * 0.90)
        sch.add_text(title, (x + 8 + title_width / 2, y + 4), size=title_size, bold=True)
        if note:
            note_size = 1.0
            note_width = min(w - 16, len(note) * note_size * 0.90)
            sch.add_text(note, (x + 8 + note_width / 2, y + 9), size=note_size, italic=True)

    # ==================================================================
    # LEFT: POWER
    # ==================================================================
    section("USB-C QC/PD POWER / 5 V DISTRIBUTION", 22, 22, 212, 440, "Dedicated power-only USB-C; separate from ESP32 USB host connector")
    left_text("12 V REQUEST: LDR6321 -> TCKE800NL -> OKL-T/6-W12N-C", 30, 40, size=1.05, bold=True)

    # J1 is a dedicated QC/PD power input.  Its D+/D- contacts belong to the
    # LDR6321 negotiation circuit and must never be joined to ESP32 USB data.
    add("J1", "Connector:USB_C_Receptacle_USB2.0_16P", "5077CR-16-SMC2-BK-TR", 39, 88, "logger_v1_custom:USB_C_5077CR-16-SMC2-BK-TR")
    rail_stub("J1", "A1", "GND", 0, 7.62)
    stub("J1", "A4", "QC_VBUS_RAW", 7.62, 0)
    for pin_num in ("A8", "B8"):
        nc("J1", pin_num)
    stub("J1", "S1", "QC_SHIELD", -7.62, 0)
    for pin_a, pin_b, net_name in (("A6", "B6", "QC_D+"), ("A7", "B7", "QC_D-")):
        pa, pb = pos("J1", pin_a), pos("J1", pin_b)
        bus_x = pa[0] + 7.62
        wire_path(pa, (bus_x, pa[1]), (bus_x, pb[1]), pb)
        local_at(bus_x, pa[1], net_name)
    stub("J1", "A5", "QC_CC1_CONN", 7.62, 0)
    stub("J1", "B5", "QC_CC2_CONN", 7.62, 0)
    place_fields("J1", (27, 61), (27, 64))

    # LDR6321 reference circuit.  VCON0=10k to GND requests the highest
    # available profile up to 12 V; VCON1/VCON2 are deliberately open.
    add("U1", "logger_v1_custom:LDR6321", "LDR6321", 91, 89, "Package_SO:SSOP-16_4.4x5.2mm_P0.65mm")
    place_fields("U1", (75, 67), (75, 70))
    pwr_pin("U1", 1, "GND")
    stub("U1", 11, "QC_VBUS_ENABLE", 5.08, 0)
    two_pin("R101", "Device:R", "10k", 62, 120, "Resistor_SMD:R_0603_1608Metric", "LDR_VCON0", "GND", rotation=90)
    stub("U1", 2, "LDR_VCON0", -5.08, 0)
    nc("U1", 3)
    nc("U1", 4)
    two_pin("R102", "Device:R", "100R", 61, 51, "Resistor_SMD:R_0603_1608Metric", "QC_CC1_CONN", "LDR_CC1", rotation=90)
    two_pin("R103", "Device:R", "100R", 78, 51, "Resistor_SMD:R_0603_1608Metric", "QC_CC2_CONN", "LDR_CC2", rotation=90)
    stub("U1", 13, "LDR_CC1", 5.08, 0)
    stub("U1", 12, "LDR_CC2", 5.08, 0)
    for ref, pin_num, value, net_name, x, y in (
        ("R106", 5, "13k", "QC_D+", 62, 132), ("R107", 7, "13k", "QC_D+", 78, 132), ("R108", 6, "2k", "QC_D+", 94, 132),
        ("R109", 9, "13k", "QC_D-", 110, 132), ("R110", 10, "13k", "QC_D-", 126, 132), ("R111", 8, "2k", "QC_D-", 142, 132),
    ):
        pin_net = f"{ref}_LDR"
        stub("U1", pin_num, pin_net, -5.08 if pin_num <= 8 else 5.08, 0)
        two_pin(ref, "Device:R", value, x, y, "Resistor_SMD:R_0603_1608Metric", pin_net, net_name, rotation=90)
    two_pin("R104", "Device:R", "499k", 112, 55, "Resistor_SMD:R_0603_1608Metric", "QC_VBUS_RAW", "LDR_VREF", rotation=90)
    two_pin("R105", "Device:R", "49.9k", 126, 55, "Resistor_SMD:R_0603_1608Metric", "LDR_VREF", "GND", rotation=90)
    add("C101", "Device:C", "0.1uF", 137, 55, "Capacitor_SMD:C_0603_1608Metric")
    local_pin("C101", 1, "LDR_VREF")
    pwr_pin("C101", 2, "GND")
    stub("U1", 14, "LDR_VREF", 5.08, 0)
    two_pin("C102", "Device:C", "1nF", 151, 55, "Capacitor_SMD:C_0603_1608Metric", "LDR_PDLDO", "GND", rotation=90)
    stub("U1", 15, "LDR_PDLDO", 5.08, 0)

    # The LDR6321 VDD absolute maximum is 6 V, so a cheap stocked 78L05
    # supplies it from raw VBUS both before and after the 12 V negotiation.
    add("U2", "logger_v1_custom:NJM78L05UA", "NJM78L05UA", 176, 52, "Package_TO_SOT_SMD:SOT-89-3")
    stub("U2", 3, "QC_VBUS_RAW", -5.08, 0)
    pwr_at(pos("U2", 3), "PWR_FLAG")
    pwr_pin("U2", 2, "GND")
    add("D100", "Device:D", "RB160M-30TR", 194, 52, "Diode_SMD:D_SOD-123", rotation=180)
    wire_pins("U2", 1, "D100", 2)
    local_pin("D100", 1, "LDR_5V")
    pwr_at(pos("D100", 1), "PWR_FLAG")
    stub("U1", 16, "LDR_5V", 0, -5.08)
    two_pin("C103", "Device:C", "0.33uF", 160, 67, "Capacitor_SMD:C_0603_1608Metric", "QC_VBUS_RAW", "GND", rotation=90)
    two_pin("C104", "Device:C", "2.2uF", 176, 67, "Capacitor_SMD:C_0603_1608Metric", "LDR_5V", "GND", rotation=90)
    two_pin("C105", "Device:C", "0.1uF", 192, 67, "Capacitor_SMD:C_0603_1608Metric", "LDR_5V", "GND", rotation=90)
    two_pin("R115", "Device:R", "10k", 208, 67, "Resistor_SMD:R_0603_1608Metric", "LDR_5V", "GND", rotation=90)

    # Bare TCKE800NL eFuse.  VBUSEN keeps the OKL input capacitor isolated
    # until negotiation completes; 20k sets the data-sheet 5 A class limit.
    left_text("12 V EFUSE / 5 V DC-DC", 30, 174, size=1.20, bold=True)
    add("U3", "logger_v1_custom:TCKE800NL", "TCKE800NL", 130, 198, "logger_v1_custom:TCKE800NL_WSON10B")
    stub("U3", 2, "QC_VBUS_ENABLE", -5.08, 0)
    for pin_num in (3, 4, 5):
        stub("U3", pin_num, "QC_VBUS_RAW", -5.08, 0)
    for pin_num in (6, 7, 8):
        stub("U3", pin_num, "QC_12V_PROTECTED", 5.08, 0)
    pwr_pin("U3", 11, "GND")
    nc("U3", 9)
    two_pin("C106", "Device:C", "1nF", 130, 225, "Capacitor_SMD:C_0603_1608Metric", "TCKE_DVDT", "GND", rotation=90)
    stub("U3", 1, "TCKE_DVDT", 0, 5.08)
    two_pin("R112", "Device:R", "20k", 151, 225, "Resistor_SMD:R_0603_1608Metric", "TCKE_ILIM", "GND", rotation=90)
    stub("U3", 10, "TCKE_ILIM", 0, 5.08)
    two_pin("C107", "Device:C", "1uF", 96, 207, "Capacitor_SMD:C_1206_3216Metric", "QC_VBUS_RAW", "GND", rotation=90)
    two_pin("C108", "Device:C", "1uF", 168, 207, "Capacitor_SMD:C_1206_3216Metric", "QC_12V_PROTECTED", "GND", rotation=90)

    # 12 V to 5 V converter.  Sense is tied at the output and 1.34k programs
    # 5.0 V.  The negative-logic ON/OFF pin is grounded for normal operation.
    add("U5", "logger_v1_custom:OKL-T-6-W12N-C", "OKL-T/6-W12N-C", 201, 198, "logger_v1_custom:OKL_T_6_W12N_C")
    stub("U5", 2, "QC_12V_PROTECTED", -5.08, 0)
    pwr_at(pos("U5", 2), "PWR_FLAG")
    pwr_pin("U5", 1, "GND")
    pwr_pin("U5", 3, "GND")
    pwr_pin("U5", 7, "GND")
    pwr_at(pos("U5", 7), "PWR_FLAG")
    rail_stub("U5", 4, "+5V", 5.08, 0)
    pwr_at(pos("U5", 4), "PWR_FLAG")
    rail_stub("U5", 5, "+5V", 5.08, 0)
    nc("U5", 8)
    nc("U5", 9)
    nc("U5", 10)
    nc("U5", 11)
    nc("U5", 12)
    two_pin("R113", "Device:R", "1.34k", 204, 227, "Resistor_SMD:R_0603_1608Metric", "OKL_TRIM", "GND", rotation=90)
    stub("U5", 6, "OKL_TRIM", 0, 5.08)
    two_pin("C109", "Device:C", "22uF", 178, 240, "Capacitor_SMD:C_1210_3225Metric", "QC_12V_PROTECTED", "GND", rotation=90)
    two_pin("C110", "Device:C", "10uF", 222, 240, "Capacitor_SMD:C_1206_3216Metric", "+5V", "GND", rotation=90)

    two_pin("R114", "Device:R", "1M", 44, 150, "Resistor_SMD:R_0603_1608Metric", "QC_SHIELD", "GND", rotation=90)
    two_pin("C111", "Device:C", "4.7nF", 65, 150, "Capacitor_SMD:C_1206_3216Metric", "QC_SHIELD", "GND", rotation=90)
    left_text("Requires a 12 V-capable QC/PD/AFC adapter. J1 is power-only.", 30, 258, size=0.9)

    left_text("5 V / 3.3 V RAILS", 30, 282, size=1.35, bold=True)
    add("U4", "Regulator_Linear:L7805", "LM2940T-3.3", 131, 308, "Package_TO_SOT_THT:TO-220-3_Vertical")
    place_fields("U4", (115.57, 290), (115.57, 293))
    pwr_pin("U4", 1, "+5V")
    pwr_pin("U4", 2, "GND")
    pwr_pin("U4", 3, "+3V3")
    # kicad-sch-api 0.5.6 swaps the rotated polarized-capacitor endpoints;
    # order these so exported physical pin 1 remains the positive terminal.
    two_pin("C2", "Device:C_Polarized", "10uF", 94, 308, "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm", "GND", "+5V", rotation=90)
    two_pin("C3", "Device:C_Polarized", "22uF", 170, 308, "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm", "GND", "+3V3", rotation=90)
    left_text("LM2940: place C2/C3 close to pins; provide TO-220 copper/heatsink area.", 30, 334, size=0.85)

    left_text("CAN AUX 2 A RESETTABLE PTC OUTPUTS", 30, 366, size=1.20, bold=True)
    two_pin("F2", "Device:Polyfuse_Small", "2A", 79, 392, "Fuse:Fuse_BelFuse_0ZRE0200FF_L24.9mm_W6.1mm", "+5V", "CAN1_AUX5V")
    two_pin("F3", "Device:Polyfuse_Small", "2A", 171, 392, "Fuse:Fuse_BelFuse_0ZRE0200FF_L24.9mm_W6.1mm", "+5V", "CAN2_AUX5V")
    left_text("F2/F3: LVR200S radial PPTC; allow thermal clearance.", 30, 418, size=0.85)

    # ==================================================================
    # CENTRE: MCU / DEBUG / USB-C
    # ==================================================================
    section("ESP32-S3 MCU / DEBUG", 246, 22, 302, 208, "[REF-MCU] N16R8: GPIO33...37 must not be assigned")
    add("U10", "RF_Module:ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1-N16R8", 385, 111, "RF_Module:ESP32-S3-WROOM-1")
    pwr_pin("U10", 2, "+3V3")
    pwr_pin("U10", 1, "GND")
    two_pin("C4", "Device:C", "10uF", 430, 176, "Capacitor_SMD:C_0805_2012Metric", "+3V3", "GND", rotation=90)
    two_pin("C5", "Device:C", "0.1uF", 447, 176, "Capacitor_SMD:C_0603_1608Metric", "+3V3", "GND", rotation=90)

    # Safe pin assignment: no GPIO33...37; GPIO45/46 strapping pins are NC.
    esp_nets = {
        3: "ESP_EN", 27: "ESP_BOOT", 39: "I2C_SDA", 38: "I2C_SCL",
        4: "CAN1_TX", 5: "CAN1_RX", 6: "CAN1_STBY",
        7: "SD_MISO", 12: "SD_MOSI", 17: "SD_CLK", 18: "CAN2_CS_N",
        19: "CAN2_MOSI", 20: "CAN2_SCK", 21: "CAN2_MISO", 22: "CAN2_INT_N",
        8: "USB_HOST_EN", 9: "SD_CS_N", 10: "GNSS_RXD", 11: "GNSS_TXD",
        13: "USB_D-_MCU", 14: "USB_D+_MCU", 23: "GNSS_PPS", 31: "USB_OC_N",
        32: "JTAG_TCK", 33: "JTAG_TDO", 34: "JTAG_TDI", 35: "JTAG_TMS",
        15: "GNSS_RESET_CTRL", 24: "SD_DET_N", 25: "CAN2_RESET_N", 37: "UART0_TX", 36: "UART0_RX",
    }
    for pin_num, net_name in esp_nets.items():
        # 5.08 mm keeps both endpoints on KiCad's 50 mil grid.
        dx = -5.08 if pos("U10", pin_num)[0] < 385 else 5.08
        stub("U10", pin_num, net_name, dx, 0)
    for pin_num in (16, 26, 28, 29, 30):
        nc("U10", pin_num)

    # Reset and boot networks, values only on passives and switches.
    two_pin("R10", "Device:R", "10k", 272, 74, "Resistor_SMD:R_0603_1608Metric", "+3V3", "ESP_EN", rotation=90)
    two_pin("C10", "Device:C", "1uF", 299, 74, "Capacitor_SMD:C_0603_1608Metric", "ESP_EN", "GND", rotation=90)
    two_pin("SW1", "Switch:SW_Push", "SW_Push", 275, 99, "Button_Switch_THT:SW_PUSH_6mm", "ESP_EN", "GND")
    two_pin("R11", "Device:R", "10k", 272, 132, "Resistor_SMD:R_0603_1608Metric", "+3V3", "ESP_BOOT", rotation=90)
    two_pin("SW2", "Switch:SW_Push", "SW_Push", 275, 157, "Button_Switch_THT:SW_PUSH_6mm", "ESP_BOOT", "GND")
    sch.add_text("RESET", (257, 99), size=1.0)
    sch.add_text("BOOT", (259, 157), size=1.0)

    # XH debugger connector requested by the user.
    add("J3", "Connector_Generic:Conn_01x10", "B10B-XH-A(LF)(SN)", 514, 78, "Connector_JST:JST_XH_B10B-XH-A_1x10_P2.50mm_Vertical")
    pwr_pin("J3", 1, "+3V3")
    pwr_pin("J3", 2, "GND")
    for pin_num, net_name in {3: "JTAG_TMS", 4: "JTAG_TCK", 5: "JTAG_TDO", 6: "JTAG_TDI", 7: "UART0_TX", 8: "UART0_RX", 9: "ESP_EN", 10: "ESP_BOOT"}.items():
        stub("J3", pin_num, net_name, -5.08, 0)
    sch.add_text("ESP32 DEBUG / JTAG + UART", (460, 57), size=1.15, bold=True)

    # Local I2C pull-ups; shared by GNSS and BNO055.
    two_pin("R30", "Device:R", "4.7k", 467, 153, "Resistor_SMD:R_0603_1608Metric", "+3V3", "I2C_SDA", rotation=90)
    two_pin("R31", "Device:R", "4.7k", 493, 153, "Resistor_SMD:R_0603_1608Metric", "+3V3", "I2C_SCL", rotation=90)

    # Visible net map in the margin, as requested.
    sch.add_text_box(
        "LOCAL NET CONNECTION MAP\n"
        "CAN1: GPIO4 TX / GPIO5 RX / GPIO6 STBY\n"
        "CAN2: GPIO10 CS / 11 MOSI / 12 SCK / 13 MISO / 14 INT / 48 RESET\n"
        "GNSS: GPIO17 RX / 18 TX / 21 PPS / GPIO1 SDA / GPIO2 SCL / GPIO3 RESET\n"
        "SD: GPIO7 MISO / 8 MOSI / 9 CLK / 16 CS / 47 DET\n"
        "USB HOST: GPIO19 D- / GPIO20 D+ / GPIO15 VBUS EN / GPIO38 OC\n"
        "DEBUG: GPIO39 TCK / 40 TDO / 41 TDI / 42 TMS / UART0",
        (253, 180), (286, 42), font_size=0.98, stroke_width=0.15,
    )

    section("USB 2.0 OTG HOST / USB-C SOURCE PORT", 246, 239, 302, 223, "[REF-USB] Fixed host role; board power comes only from J1")
    add("J2", "Connector:USB_C_Receptacle_USB2.0_16P", "5077CR-16-SMC2-BK-TR", 287, 319, "logger_v1_custom:USB_C_5077CR-16-SMC2-BK-TR")
    rail_stub("J2", "A1", "GND", 0, 7.62)
    for pin_num in ("A8", "B8"):
        nc("J2", pin_num)
    stub("J2", "S1", "USB_SHIELD", -10.16, 0, size=0.8)
    stub("J2", "A4", "USB_HOST_VBUS", 10.16, 0, size=0.8)
    # Join the duplicated Type-C data contacts close to the connector and
    # expose one readable local-net label per pair.
    for pin_a, pin_b, net_name in (
        ("A6", "B6", "USB_D+_CONN"),
        ("A7", "B7", "USB_D-_CONN"),
    ):
        pa, pb = pos("J2", pin_a), pos("J2", pin_b)
        bus_x = pa[0] + 10.16
        wire_path(pa, (bus_x, pa[1]), (bus_x, pb[1]), pb)
        local_at(bus_x, pa[1], net_name, size=0.8)
    stub("J2", "A5", "USB_CC1", 7.62, 0, size=0.8)
    stub("J2", "B5", "USB_CC2", 10.16, 0, size=0.8)
    place_fields("J2", (270.51, 295.91), (270.51, 298.45))

    # Low-capacitance rail clamps using only Akizuki-stocked parts.
    for i, (net_name, y) in enumerate([("USB_D-_CONN", 292), ("USB_D+_CONN", 310)], start=0):
        # Device:D_Small pin 1 is K and pin 2 is A.
        upper_ref, lower_ref = f"D{20+i*2}", f"D{21+i*2}"
        add(upper_ref, "Device:D_Small", "1SS355", 342, y, "Diode_SMD:D_SOD-323")
        add(lower_ref, "Device:D_Small", "1SS355", 368, y, "Diode_SMD:D_SOD-323")
        rail_stub(upper_ref, 1, "+3V3", -5.08, 0)
        wire_pins(upper_ref, 2, lower_ref, 1)
        signal_pin = pos(upper_ref, 2)
        local_at(signal_pin[0] + 2.54, signal_pin[1], net_name, size=0.8)
        rail_stub(lower_ref, 2, "GND", 5.08, 0)
    two_pin("R20", "Device:R", "33R", 402, 292, "Resistor_SMD:R_0603_1608Metric", "USB_D-_CONN", "USB_D-_MCU", rotation=90)
    two_pin("R21", "Device:R", "33R", 402, 310, "Resistor_SMD:R_0603_1608Metric", "USB_D+_CONN", "USB_D+_MCU", rotation=90)
    two_pin("R24", "Device:R", "1M", 325, 360, "Resistor_SMD:R_0603_1608Metric", "USB_SHIELD", "GND", rotation=90)
    two_pin("C20", "Device:C", "4.7nF", 356, 360, "Capacitor_SMD:C_1206_3216Metric", "USB_SHIELD", "GND", rotation=90)

    # Fixed Type-C source/host role: Rp is permanent, so no generic analog
    # switch or manual role selector is required.  The ESP32 controls only the
    # protected VBUS load switch, which is the minimum host-side power path.
    two_pin("R25", "Device:R", "56k", 426, 322, "Resistor_SMD:R_0603_1608Metric", "+5V", "USB_CC1", rotation=90)
    two_pin("R27", "Device:R", "56k", 450, 322, "Resistor_SMD:R_0603_1608Metric", "+5V", "USB_CC2", rotation=90)

    add("U8", "logger_v1_custom:XC8107AC20MR-G", "XC8107AC20MR-G", 490, 365, "Package_TO_SOT_SMD:SOT-23-5")
    rail_stub("U8", 5, "+5V", -7.62, 0)
    stub("U8", 4, "USB_HOST_EN", -10.16, 0, size=0.8)
    stub("U8", 1, "USB_HOST_VBUS", 10.16, 0, size=0.8)
    stub("U8", 3, "USB_OC_N", 10.16, 0, size=0.8)
    rail_stub("U8", 2, "GND", 0, 5.08)
    place_fields("U8", (475, 345), (475, 348))
    two_pin("R35", "Device:R", "100k", 450, 390, "Resistor_SMD:R_0603_1608Metric", "USB_HOST_EN", "GND", rotation=90)
    two_pin("C21", "Device:C", "1uF", 465, 390, "Capacitor_SMD:C_0805_2012Metric", "+5V", "GND", rotation=90)
    # kicad-sch-api 0.5.6 resolves the pins of a 90-degree rotated two-pin
    # symbol in reverse geometric order.  Supply the labels in that order so
    # the exported netlist still has pin 1 (+) on +5V and pin 2 on GND.
    two_pin("C22", "Device:C_Polarized", "120uF", 485, 405, "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", "GND", "+5V", rotation=90)
    two_pin("C23", "Device:C", "1uF", 505, 390, "Capacitor_SMD:C_0805_2012Metric", "USB_HOST_VBUS", "GND", rotation=90)
    two_pin("R36", "Device:R", "100k", 525, 390, "Resistor_SMD:R_0603_1608Metric", "+3V3", "USB_OC_N", rotation=90)

    sch.add_text_box(
        "DEDICATED USB OTG HOST PORT\nJ2 is a fixed Type-C source: CC1/CC2 use 56k Rp and never power the board.\nGPIO15 enables U8; GPIO38 reads its over-current output.\nBoard power always comes from the separate QC/PD connector J1.\nThis removes the 74HC4053 and manual role switch. Device mode is intentionally not provided on J2.\n1SS355 clamps are an Akizuki-only compromise, not IEC-rated USB TVS.",
        (253, 418), (286, 34), font_size=0.92, stroke_width=0.15,
    )

    # ==================================================================
    # RIGHT: PERIPHERALS
    # ==================================================================
    section("PERIPHERALS / CAN x2 / GNSS / SD", 560, 22, 260, 440, "Internal connections use wires; block boundaries use local labels")

    # CAN1, horizontal PHY -> CMC -> TVS/termination -> connector.
    left_text("CAN1 / ESP32 TWAI", 568, 42, size=1.5, bold=True)
    add("U20", "logger_v1_custom:MCP2562FD-E-P", "MCP2562FD-E/P", 610, 73, "Package_DIP:DIP-8_W7.62mm")
    for pin_num, net_name in ((1, "CAN1_TX"), (4, "CAN1_RX"), (8, "CAN1_STBY")):
        stub("U20", pin_num, net_name, -7.62, 0, size=0.75)
    pwr_pin("U20", 3, "+5V")
    pwr_pin("U20", 5, "+3V3")
    pwr_pin("U20", 2, "GND")
    two_pin("C11", "Device:C", "0.1uF", 640, 45, "Capacitor_SMD:C_0603_1608Metric", "+5V", "GND", rotation=90)
    two_pin("C12", "Device:C", "0.1uF", 657, 45, "Capacitor_SMD:C_0603_1608Metric", "+3V3", "GND", rotation=90)
    place_fields("U20", (620.27, 49.53), (620.27, 52.07))
    two_pin("R80", "Device:R", "10k", 575, 91, "Resistor_SMD:R_0603_1608Metric", "CAN1_STBY", "GND", rotation=90)
    add("L20", "Device:L_Coupled_Small", "67R@100MHz", 672, 73, "logger_v1_custom:DLW21SN670SQ2L")
    wire_pins("U20", 7, "L20", 1)
    wire_pins("U20", 6, "L20", 3)
    stub("L20", 2, "CAN1H", 7.62, 0, size=0.75)
    stub("L20", 4, "CAN1L", 7.62, 0, size=0.75)
    local_pin("U20", 7, "CAN1H_PHY")
    local_pin("L20", 1, "CAN1H_PHY")
    local_pin("U20", 6, "CAN1L_PHY")
    local_pin("L20", 3, "CAN1L_PHY")
    local_pin("L20", 2, "CAN1H")
    local_pin("L20", 4, "CAN1L")
    place_fields("L20", (660.40, 59.69), (660.40, 62.23))
    add("D50", "logger_v1_custom:PEC3824C2A-AU", "PEC3824C2A-AU", 720, 96, "Package_TO_SOT_SMD:SOT-23")
    stub("D50", 1, "CAN1H", -7.62, 0, size=0.75)
    stub("D50", 2, "CAN1L", -7.62, 0, size=0.75)
    rail_stub("D50", 3, "GND", 0, 5.08)
    place_fields("D50", (707.39, 84.00), (707.39, 86.54))
    two_pin("R81", "Device:R", "120R", 720, 62, "Resistor_SMD:R_0603_1608Metric", "CAN1H", "CAN1_TERM", rotation=90)
    two_pin("JP1", "Jumper:Jumper_2_Open", "Jumper_2_Open", 750, 62, "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "CAN1_TERM", "CAN1L")
    place_fields("R81", (711.20, 50.80), (711.20, 53.34))
    place_fields("JP1", (738.63, 50.80), (738.63, 53.34))
    add("J20", "Connector_Generic:Conn_01x04", "B4P-VH(LF)(SN)", 798, 72, "Connector_JST:JST_VH_B4P-VH_1x04_P3.96mm_Vertical")
    stub("J20", 1, "CAN1_AUX5V", -7.62, 0, size=0.70)
    rail_stub("J20", 2, "GND", -7.62, 0)
    stub("J20", 3, "CAN1H", -7.62, 0, size=0.70)
    stub("J20", 4, "CAN1L", -7.62, 0, size=0.70)
    place_fields("J20", (781.05, 55.88), (781.05, 58.42))

    # CAN2 MCP25625 with external crystal and internal TxCAN/RxCAN loop wires.
    left_text("CAN2 / MCP25625 SPI", 568, 133, size=1.5, bold=True)
    add("U21", "Interface_CAN_LIN:MCP25625x-x-SS", "MCP25625T-E/SS", 620, 192, "Package_SO:SSOP-28_5.3x10.2mm_P0.65mm")
    for pin_num, net_name in {14: "CAN2_SCK", 15: "CAN2_MOSI", 16: "CAN2_MISO", 17: "CAN2_CS_N", 13: "CAN2_INT_N", 18: "CAN2_RESET_N"}.items():
        stub("U21", pin_num, net_name, -7.62, 0, size=0.68)
    stub("U21", 5, "CAN2_STBY", -7.62, 0, size=0.68)
    for pin_num in (19, 1):
        pwr_pin("U21", pin_num, "+3V3")
    pwr_pin("U21", 27, "+5V")
    for pin_num in (10, 26):
        pwr_pin("U21", pin_num, "GND")
    two_pin("C13", "Device:C", "0.1uF", 580, 223, "Capacitor_SMD:C_0603_1608Metric", "+3V3", "GND", rotation=90)
    two_pin("C14", "Device:C", "0.1uF", 595, 238, "Capacitor_SMD:C_0603_1608Metric", "+3V3", "GND", rotation=90)
    two_pin("C15", "Device:C", "0.1uF", 610, 238, "Capacitor_SMD:C_0603_1608Metric", "+5V", "GND", rotation=90)
    place_fields("U21", (600.71, 142.24), (600.71, 144.78))
    # Required external controller/transceiver links.
    wire_pins("U21", 20, "U21", 24, via=[(704.85, pos("U21", 20)[1]), (704.85, pos("U21", 24)[1])])
    wire_pins("U21", 21, "U21", 28, via=[(709.93, pos("U21", 21)[1]), (709.93, pos("U21", 28)[1])])
    for pin_num in (2, 6, 7, 11, 12, 22, 23, 25):
        nc("U21", pin_num)
    two_pin("R82", "Device:R", "10k", 572, 176, "Resistor_SMD:R_0603_1608Metric", "+3V3", "CAN2_RESET_N", rotation=90)
    two_pin("R83", "Device:R", "10k", 572, 194, "Resistor_SMD:R_0603_1608Metric", "CAN2_STBY", "GND", rotation=90)
    add("Y1", "Device:Crystal_GND24", "16MHz", 691, 221, "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm")
    # Akizuki 102457, Epson FA238-16MHz (CL=10pF, 3.2 x 2.5 mm).
    local_pin("Y1", 1, "CAN2_OSC1")
    local_pin("Y1", 3, "CAN2_OSC2")
    pwr_pin("Y1", 2, "GND")
    pwr_pin("Y1", 4, "GND")
    stub("U21", 9, "CAN2_OSC1", 7.62, 0, size=0.70)
    stub("U21", 8, "CAN2_OSC2", 7.62, 0, size=0.70)
    two_pin("C60", "Device:C", "15pF", 727, 216, "Capacitor_SMD:C_0603_1608Metric", "CAN2_OSC1", "GND", rotation=90)
    two_pin("C61", "Device:C", "15pF", 727, 230, "Capacitor_SMD:C_0603_1608Metric", "CAN2_OSC2", "GND", rotation=90)
    add("L21", "Device:L_Coupled_Small", "67R@100MHz", 732, 174, "logger_v1_custom:DLW21SN670SQ2L")
    wire_pins("U21", 4, "L21", 1)
    wire_pins("U21", 3, "L21", 3)
    stub("L21", 2, "CAN2H", 7.62, 0, size=0.75)
    stub("L21", 4, "CAN2L", 7.62, 0, size=0.75)
    local_pin("U21", 4, "CAN2H_PHY")
    local_pin("L21", 1, "CAN2H_PHY")
    local_pin("U21", 3, "CAN2L_PHY")
    local_pin("L21", 3, "CAN2L_PHY")
    local_pin("L21", 2, "CAN2H")
    local_pin("L21", 4, "CAN2L")
    place_fields("L21", (720.09, 160.02), (720.09, 162.56))
    add("D51", "logger_v1_custom:PEC3824C2A-AU", "PEC3824C2A-AU", 767, 215, "Package_TO_SOT_SMD:SOT-23")
    stub("D51", 1, "CAN2H", -7.62, 0, size=0.75)
    stub("D51", 2, "CAN2L", -7.62, 0, size=0.75)
    rail_stub("D51", 3, "GND", 0, 5.08)
    place_fields("D51", (754.38, 203.20), (754.38, 205.74))
    two_pin("R84", "Device:R", "120R", 760, 159, "Resistor_SMD:R_0603_1608Metric", "CAN2H", "CAN2_TERM", rotation=90)
    two_pin("JP2", "Jumper:Jumper_2_Open", "Jumper_2_Open", 786, 159, "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "CAN2_TERM", "CAN2L")
    place_fields("R84", (751.84, 147.32), (751.84, 149.86))
    place_fields("JP2", (773.43, 147.32), (773.43, 149.86))
    add("J21", "Connector_Generic:Conn_01x04", "B4P-VH(LF)(SN)", 798, 192, "Connector_JST:JST_VH_B4P-VH_1x04_P3.96mm_Vertical")
    stub("J21", 1, "CAN2_AUX5V", -7.62, 0, size=0.70)
    rail_stub("J21", 2, "GND", -7.62, 0)
    stub("J21", 3, "CAN2H", -7.62, 0, size=0.70)
    stub("J21", 4, "CAN2L", -7.62, 0, size=0.70)
    place_fields("J21", (781.05, 175.26), (781.05, 177.80))

    # GNSS active-antenna bias tee.  The antenna-side choke and DC-block
    # capacitor are Akizuki-stocked RF parts (131838 / 117481); VCC_RF is the
    # module's switched, filtered antenna supply output.
    left_text("GNSS / ACTIVE ANTENNA", 568, 258, size=1.5, bold=True)
    add("U30", "logger_v1_custom:Teseo-LIV3FL", "Teseo-LIV3FL", 623, 303, "logger_v1_custom:Teseo_LIV3FL_LCC18")
    place_fields("U30", (609.60, 267.97), (609.60, 270.51))
    # Cross UART TX/RX: module TXD goes to the MCU's GNSS_RXD net and vice
    # versa.  Net names are from the ESP32 point of view.
    for pin_num, net_name in {2: "GNSS_RXD", 3: "GNSS_TXD", 4: "GNSS_PPS", 9: "GNSS_RESET_N", 16: "I2C_SDA", 17: "I2C_SCL"}.items():
        stub("U30", pin_num, net_name, -7.62, 0, size=0.68)
    for pin_num in (6, 7, 8):
        pwr_pin("U30", pin_num, "+3V3")
    for pin_num in (1, 10, 12):
        pwr_pin("U30", pin_num, "GND")
    two_pin("C16", "Device:C", "0.1uF", 658, 263, "Capacitor_SMD:C_0603_1608Metric", "+3V3", "GND", rotation=90)
    two_pin("C17", "Device:C", "0.1uF", 675, 263, "Capacitor_SMD:C_0603_1608Metric", "+3V3", "GND", rotation=90)
    two_pin("C18", "Device:C", "10uF", 692, 263, "Capacitor_SMD:C_0805_2012Metric", "+3V3", "GND", rotation=90)
    for pin_num in (5, 13, 15, 18):
        nc("U30", pin_num)
    add("R90", "Device:R", "10k", 572, 311, "Resistor_SMD:R_0603_1608Metric", rotation=90)
    rail_stub("R90", 1, "+3V3", 5.08, 0)
    stub("R90", 2, "GNSS_RESET_N", -7.62, 0, size=0.72)
    place_fields("R90", (562.61, 300.99), (562.61, 303.53))
    # UM2980 recommends host control of GNSS reset for firmware update and
    # recovery.  GPIO3 is a strapping input, so keep it LOW at ESP32 reset and
    # use an inverting open-drain 2N7002K instead of connecting it directly.
    two_pin("R32", "Device:R", "10k", 575, 280, "Resistor_SMD:R_0603_1608Metric", "GNSS_RESET_CTRL", "GND", rotation=90)
    add("Q30", "Transistor_FET:2N7002K", "2N7002K", 590, 294, "Package_TO_SOT_SMD:SOT-23")
    stub("Q30", 1, "GNSS_RESET_CTRL", -7.62, 0, size=0.70)
    pwr_pin("Q30", 2, "GND")
    stub("Q30", 3, "GNSS_RESET_N", 0, -7.62, size=0.70)
    place_fields("Q30", (579.12, 267.97), (579.12, 270.51))
    add("C70", "Device:C", "47pF", 701, 296, "Capacitor_SMD:C_0603_1608Metric")
    add("L30", "Device:L_Small", "47nH", 744, 276, "Inductor_SMD:L_0402_1005Metric")
    # Generic coaxial connector symbol only.  The user will select the exact
    # SMA connector and assign its footprint during PCB mechanical design.
    add("J30", "Connector:Conn_Coaxial", "SMA", 788, 296, "")
    wire_pins("U30", 11, "C70", 2)
    wire_pins("C70", 1, "J30", 1)
    wire_pins("U30", 14, "L30", 1, via=[(pos("U30", 14)[0] + 12.70, pos("U30", 14)[1]), (pos("U30", 14)[0] + 12.70, pos("L30", 1)[1])])
    wire_pins("L30", 2, "J30", 1, via=[(pos("J30", 1)[0] - 15.24, pos("L30", 2)[1]), (pos("J30", 1)[0] - 15.24, pos("J30", 1)[1])])
    local_pin("U30", 11, "GNSS_RF_IN")
    local_pin("C70", 2, "GNSS_RF_IN")
    local_pin("C70", 1, "GNSS_ANT")
    local_pin("L30", 2, "GNSS_ANT")
    local_pin("J30", 1, "GNSS_ANT")
    local_pin("U30", 14, "GNSS_ANT_BIAS")
    local_pin("L30", 1, "GNSS_ANT_BIAS")
    pwr_pin("J30", 2, "GND")
    place_fields("C70", (690.88, 284.48), (690.88, 287.02))
    place_fields("L30", (731.52, 265.43), (731.52, 267.97))
    left_text("External active antenna via SMA; assign J30 footprint later; 50 ohm RF trace", 670, 313, size=0.9, italic=True)

    # microSD SPI. CMD and all DAT lines have external pull-ups per Espressif.
    left_text("microSD / SPI MODE", 568, 337, size=1.5, bold=True)
    add("J31", "Connector:Micro_SD_Card_Det_Hirose_DM3AT", "DM3AT-SF-PEJM5", 610, 390, "Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5")
    place_fields("J31", (588.01, 347.98), (588.01, 350.52))
    pwr_pin("J31", 4, "+3V3")
    # Pin 9 is one side of the card-detect switch, not a supply pin.
    for pin_num in (6, 9, 11):
        pwr_pin("J31", pin_num, "GND")
    two_pin("C19", "Device:C", "0.1uF", 620, 440, "Capacitor_SMD:C_0603_1608Metric", "+3V3", "GND", rotation=90)
    two_pin("C24", "Device:C", "10uF", 640, 440, "Capacitor_SMD:C_0805_2012Metric", "+3V3", "GND", rotation=90)
    # Signal-side series resistors.
    two_pin("R91", "Device:R", "22R", 665, 354, "Resistor_SMD:R_0603_1608Metric", "SD_CLK", "SD_CLK_CARD", rotation=90)
    two_pin("R92", "Device:R", "22R", 665, 369, "Resistor_SMD:R_0603_1608Metric", "SD_MOSI", "SD_MOSI_CARD", rotation=90)
    two_pin("R93", "Device:R", "22R", 665, 384, "Resistor_SMD:R_0603_1608Metric", "SD_CS_N", "SD_CS_CARD_N", rotation=90)
    two_pin("R94", "Device:R", "22R", 665, 399, "Resistor_SMD:R_0603_1608Metric", "SD_MISO", "SD_MISO_CARD", rotation=90)
    for pin_num, net_name in (
        (2, "SD_CS_CARD_N"), (3, "SD_MOSI_CARD"), (5, "SD_CLK_CARD"),
        (7, "SD_MISO_CARD"), (1, "SD_DAT2"), (8, "SD_DAT1"), (10, "SD_DET_N"),
    ):
        local_pin("J31", pin_num, net_name)
    for i, (net_name, x) in enumerate([
        ("SD_DAT2", 704), ("SD_CS_CARD_N", 721), ("SD_MOSI_CARD", 738),
        ("SD_MISO_CARD", 755), ("SD_DAT1", 772), ("SD_DET_N", 789),
    ]):
        ref = f"R{95+i}"
        add(ref, "Device:R", "10k", x, 420, "Resistor_SMD:R_0603_1608Metric", rotation=180)
        component_position = sch.components.get(ref).position
        centre = (component_position.x, component_position.y)
        passive_endpoint(ref, 1, "+3V3", centre)
        passive_endpoint(ref, 2, net_name, centre)
        place_fields(ref, (x + 2.54, 418.73), (x + 2.54, 421.27))

    # ==================================================================
    # BOTTOM: REFERENCES / PROCUREMENT
    # ==================================================================
    sch.add_text_box(
        "DESIGN REFERENCES (page / figure)\n"
        "[REF-MCU] ESP32-S3-WROOM-1/-1U DS p.10-12, p.41 Fig.9-1\n"
        "https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf\n"
        "[REF-USB] ESP32-S3 HW Guide p.18-19 Fig.10; official USB-OTG schematic sheet 4\n"
        "https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/esp-hardware-design-guidelines-en-master-esp32s3.pdf\n"
        "https://dl.espressif.com/dl/schematics/SCH_ESP32-S3_USB_OTG.pdf\n"
        "[REF-CAN1] MCP2562FD DS p.6 Fig.1-2\n"
        "https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP2561-2FD-High-Speed-CAN-Flexible-Data-Rate-Transceiver-DS20005284.pdf\n"
        "[REF-CAN2] MCP25625 DS p.5 Fig.1-2, p.28-29 crystal circuit\n"
        "https://ww1.microchip.com/downloads/en/DeviceDoc/MCP25625-CAN-Controller-Data-Sheet-20005282C.pdf",
        (22, 474), (390, 89), font_size=0.83, stroke_width=0.15,
    )
    sch.add_text_box(
        "DESIGN REFERENCES / PROCUREMENT\n"
        "[REF-GNSS] Teseo-LIV3FL UM2980 p.3 Fig.2, p.9-10 active antenna, p.12 Fig.11\n"
        "https://www.st.com/resource/en/user_manual/um2980-hardware-specifications-for-teseoliv3fl-stmicroelectronics.pdf\n"
        "[REF-SD] Hirose DM3 catalog p.3 + Espressif SD pull-up requirements\n"
        "https://www.hirose.com/en/product/document?documentid=D49662_en&documenttype=Catalog&lang=en&series=DM3\n"
        "https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-reference/peripherals/sd_pullup_requirements.html\n"
        "[REF-PWR] LDR6321 Fig.4 / TCKE800NL app+land / OKL-T/6-W12 / LM2940 / XC8107\n"
        "https://akizukidenshi.com/goodsaffix/ldr6321.pdf  https://akizukidenshi.com/goodsaffix/TCKE800NL.pdf\n"
        "https://akizukidenshi.com/goodsaffix/OKL_T6_W12.pdf  https://akizukidenshi.com/goodsaffix/lm2940.pdf\n"
        "https://akizukidenshi.com/goodsaffix/xc8107.pdf",
        (420, 474), (400, 89), font_size=0.83, stroke_width=0.15,
    )
    left_text(
        "Akizuki availability checked 2026-08-14. Power: LDR6321 117569 / TCKE800NL 116580 / OKL-T/6-W12N-C 106187 / NJM78L05UA 104699 / USB-C 114356. CAN2 keeps MCP25625 because MCP2515-I/P also requires a separate transceiver.",
        26, 567, size=0.85, italic=True,
    )

    out = ROOT / "logger_v1.kicad_sch"
    sch.save(out, preserve_format=False)
    # kicad-sch-api 0.5.6 emits two old private Crystal_GND24 fields without
    # KiCad's required quoting. Repair only those serializer defects.
    serialized = out.read_text(encoding="utf-8")
    serialized = serialized.replace(
        '(property "private" "KLC_S3.3" The rectangle is not a symbol body but a graphical element',
        '(property private "KLC_S3.3" "The rectangle is not a symbol body but a graphical element"',
    ).replace(
        '(property "private" "KLC_S4.1" Some pins are on 50mil grid to make the symbol small',
        '(property private "KLC_S4.1" "Some pins are on 50mil grid to make the symbol small"',
    )
    out.write_text(serialized, encoding="utf-8")
    print(f"generated {out}")


if __name__ == "__main__":
    build_schematic()
