"""Render ASCII 32..126 (plus the degree sign in slot 127) of a monospace TTF into a grayscale atlas (PGM) for the burn-in HUD (overlay_rec.c).

The UNO Q has no Pillow/FreeType, so this runs on the PC with the font copied from the UNO Q
(/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf, DejaVu fonts license).
The cell metrics go into a PGM comment line that overlay_rec.c reads:
    # atlas cell_w cell_h first count cols

usage: python make_font_atlas.py <font.ttf> <pixel_size> <out.pgm>
"""
import sys

from PIL import Image, ImageDraw, ImageFont

FIRST, COUNT, COLS = 32, 96, 16
# Slot 127 (DEL) holds the degree sign: hud_layout.h / hud_layout.py turn "°" (and "℃" -> "°C") in hud.ini into byte 127.
# 96 cells still fit the same 16x6 grid, so the atlas size and every ASCII glyph stay as before.
EXTRA = {127: '°'}


def main():
    font_path, size, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    font = ImageFont.truetype(font_path, size)
    ascent, descent = font.getmetrics()
    cell_w = round(font.getlength('0'))
    cell_h = ascent + descent
    rows = (COUNT + COLS - 1) // COLS
    atlas = Image.new('L', (cell_w * COLS, cell_h * rows), 0)
    draw = ImageDraw.Draw(atlas)
    for i in range(COUNT):
        x, y = (i % COLS) * cell_w, (i // COLS) * cell_h
        draw.text((x, y), EXTRA.get(FIRST + i, chr(FIRST + i)), font=font, fill=255)
    with open(out, 'wb') as f:
        f.write(f'P5\n# atlas {cell_w} {cell_h} {FIRST} {COUNT} {COLS}\n{atlas.width} {atlas.height}\n255\n'.encode())
        f.write(atlas.tobytes())
    print(f'{out}: {atlas.width}x{atlas.height}, cell {cell_w}x{cell_h}')


if __name__ == '__main__':
    main()
