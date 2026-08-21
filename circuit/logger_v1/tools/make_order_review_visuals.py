#!/usr/bin/env python3
"""Build readable PNGs used by the logger_v1 board-review report."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
VIS = ROOT / "tmp" / "order_review_visuals"
AUDIT = ROOT / "tmp" / "order_review_data.json"


def font(size, bold=False):
    choices = [
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf"),
    ]
    for path in choices:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def labeled_crop(source, box, output, title):
    image = Image.open(source).convert("RGB").crop(box)
    canvas = Image.new("RGB", (image.width, image.height + 76), "white")
    canvas.paste(image, (0, 76))
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 17), title, font=font(34, True), fill="#111827")
    canvas.save(output, quality=95)


def board_transform(panel, x, y):
    left, top, right, bottom = panel
    return (
        left + (x + 0.635) / 70.635 * (right - left),
        top + y / 100.0 * (bottom - top),
    )


def draw_board(draw, panel, title):
    left, top, right, bottom = panel
    draw.rounded_rectangle(panel, radius=26, fill="#f8fafc", outline="#334155", width=4)
    draw.text((left, top - 52), title, font=font(34, True), fill="#0f172a")


def make_spacing_map(data):
    canvas = Image.new("RGB", (1900, 1500), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((70, 38), "Same-net spacing heuristic: all 60 locations classified", font=font(48, True), fill="#0f172a")
    draw.text((70, 103), "57 local bend corners; 3 same-net pad junctions; no isolated narrow copper slots", font=font(29), fill="#475569")
    front = (220, 220, 820, 1330)
    back = (1080, 220, 1680, 1330)
    draw_board(draw, front, "F.Cu (not mirrored)")
    draw_board(draw, back, "B.Cu (not mirrored)")
    counts = {"F.Cu": 0, "B.Cu": 0}
    for item in data["spacing_violations"]:
        panel = front if item["layer"] == "F.Cu" else back
        counts[item["layer"]] += 1
        x, y = board_transform(panel, *item["marker"])
        color = "#dc2626" if item["gap_mm"] < 0.10 else "#f59e0b" if item["gap_mm"] < 0.20 else "#2563eb"
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=color, outline="white", width=2)
    draw.text((310, 1370), f"{counts['F.Cu']} markers", font=font(28, True), fill="#334155")
    draw.text((1170, 1370), f"{counts['B.Cu']} markers", font=font(28, True), fill="#334155")
    draw.ellipse((690, 1413, 712, 1435), fill="#dc2626")
    draw.text((720, 1405), "<0.10 mm", font=font(25), fill="#334155")
    draw.ellipse((920, 1413, 942, 1435), fill="#f59e0b")
    draw.text((950, 1405), "0.10-0.20", font=font(25), fill="#334155")
    draw.ellipse((1190, 1413, 1212, 1435), fill="#2563eb")
    draw.text((1220, 1405), "0.20-0.25", font=font(25), fill="#334155")
    canvas.save(VIS / "same_net_spacing_map.png", quality=95)


def make_copper_changes():
    canvas = Image.new("RGB", (1350, 1750), "white")
    draw = ImageDraw.Draw(canvas)
    panel = (260, 285, 1090, 1540)
    draw.text((60, 42), "Copper changes after the previous Gerber export", font=font(46, True), fill="#0f172a")
    draw.text((60, 108), "+3V3 and /OTG_OC reroutes; eight GND stitching vias; one duplicate via removed", font=font(27), fill="#475569")
    draw_board(draw, panel, "Current board coordinates")

    added = [
        ((24.257, 55.753), (24.257, 57.531), "+3V3"),
        ((25.397, 51.054), (25.397, 54.613), "+3V3"),
        ((25.397, 54.613), (24.257, 55.753), "+3V3"),
        ((10.922, 31.242), (9.144, 31.242), "/OTG_OC"),
        ((11.811, 32.131), (10.922, 31.242), "/OTG_OC"),
        ((11.811, 35.133595), (11.811, 32.131), "/OTG_OC"),
    ]
    removed = [
        ((24.257, 52.194), (24.257, 57.531)),
        ((25.397, 51.054), (24.257, 52.194)),
        ((11.557, 31.242), (9.144, 31.242)),
        ((11.811, 31.496), (11.557, 31.242)),
        ((11.811, 35.133595), (11.811, 31.496)),
    ]
    vias = [(10, 65), (10, 70), (10, 75), (15, 70), (15, 75), (22.86, 64.516), (22.987, 60.96), (46.99, 78.74)]
    for start, end in removed:
        draw.line((*board_transform(panel, *start), *board_transform(panel, *end)), fill="#94a3b8", width=5)
    for start, end, _ in added:
        draw.line((*board_transform(panel, *start), *board_transform(panel, *end)), fill="#dc2626", width=9)
    for vx, vy in vias:
        x, y = board_transform(panel, vx, vy)
        draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill="#16a34a", outline="white", width=3)
    rx, ry = board_transform(panel, 54, 49)
    draw.ellipse((rx - 12, ry - 12, rx + 12, ry + 12), outline="#64748b", width=4)
    draw.line((rx - 10, ry - 10, rx + 10, ry + 10), fill="#64748b", width=4)
    draw.line((rx - 10, ry + 10, rx + 10, ry - 10), fill="#64748b", width=4)
    draw.text((300, 1600), "red: added/rerouted track", font=font(27, True), fill="#dc2626")
    draw.text((690, 1600), "gray: prior geometry", font=font(27, True), fill="#64748b")
    draw.text((300, 1644), "green: added GND via", font=font(27, True), fill="#16a34a")
    draw.text((690, 1644), "cross: duplicate via removed", font=font(27, True), fill="#64748b")
    canvas.save(VIS / "copper_changes.png", quality=95)


def main():
    VIS.mkdir(parents=True, exist_ok=True)
    front = VIS / "front_layers.png"
    top = VIS / "board_top.png"
    labeled_crop(front, (180, 240, 930, 1120), VIS / "usb_u10_detail.png", "USB-C J2/J6 and U10 detail")
    labeled_crop(front, (120, 1900, 1980, 2390), VIS / "led_silk_detail.png", "LED row: footprint polarity and functional labels")
    labeled_crop(top, (0, 930, 1160, 1568), VIS / "sma_mechanical_detail.png", "S-037-TGG edge placement")
    data = json.loads(AUDIT.read_text(encoding="utf-8"))
    make_spacing_map(data)
    make_copper_changes()


if __name__ == "__main__":
    main()
