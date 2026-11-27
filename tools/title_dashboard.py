"""Generate Title Screen Review screenshots, candidates, and data for the Barba Enterprise dashboard."""
from __future__ import annotations

import json
import shutil
import struct
import sys
import zlib
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import boss_art
from nes import load_source, write_png

ROOT = _TOOLS_DIR.parent
OUT_DIR = ROOT / 'web' / 'previews' / 'titles'
DATA_JS = ROOT / 'web' / 'title_review_data.js'
SCRATCH = Path(r'C:\Users\baxte\.gemini\antigravity\brain\c9f9e555-9e4a-49ea-8cd1-43c40c0f4f3a\scratch')

# Authentic NES palette RGBs used in our subgames
NES_RGB = {
    0x0F: (0, 0, 0),
    0x00: (84, 84, 84),
    0x10: (152, 150, 152),
    0x20: (236, 238, 236),
    0x30: (236, 238, 236),
    0x06: (100, 12, 0),
    0x16: (180, 27, 0),
    0x26: (236, 76, 36),
    0x27: (228, 148, 24),
    0x37: (248, 196, 120),
    0x38: (244, 216, 144),
    0x17: (148, 60, 0),
    0x36: (244, 180, 156),
    0x0C: (0, 60, 88),
    0x1C: (0, 112, 168),
    0x2C: (88, 208, 248),
    0x01: (0, 20, 136),
    0x11: (24, 68, 180),
    0x21: (60, 148, 252),
    0x09: (20, 80, 0),
    0x1A: (40, 160, 20),
    0x29: (120, 212, 56),
}


def _read_png(path: Path) -> list[list[tuple[int, int, int]]]:
    """Dependency-free PNG reader for 8-bit RGB/RGBA/indexed NES screenshots."""
    data = path.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    pos = 8
    w = h = color_type = 0
    plte: list[tuple[int, int, int]] = []
    idat = bytearray()
    while pos < len(data):
        ln = struct.unpack('>I', data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + ln]
        pos += 12 + ln
        if kind == b'IHDR':
            w, h, bit_depth, color_type = struct.unpack('>IIBB', payload[:10])
            assert bit_depth == 8, f'Unsupported bit depth {bit_depth}'
        elif kind == b'PLTE':
            plte = [(payload[i], payload[i + 1], payload[i + 2]) for i in range(0, len(payload), 3)]
        elif kind == b'IDAT':
            idat.extend(payload)
        elif kind == b'IEND':
            break
    bpp = {2: 3, 6: 4, 3: 1}[color_type]
    raw = zlib.decompress(bytes(idat))
    stride = w * bpp
    recon = bytearray(h * stride)
    for y in range(h):
        ftype = raw[y * (stride + 1)]
        row_in = raw[y * (stride + 1) + 1 : (y + 1) * (stride + 1)]
        row_out = y * stride
        for x in range(stride):
            a = recon[row_out + x - bpp] if x >= bpp else 0
            b = recon[row_out - stride + x] if y > 0 else 0
            c = recon[row_out - stride + x - bpp] if (y > 0 and x >= bpp) else 0
            v = row_in[x]
            if ftype == 1:
                v = (v + a) & 0xFF
            elif ftype == 2:
                v = (v + b) & 0xFF
            elif ftype == 3:
                v = (v + ((a + b) >> 1)) & 0xFF
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                v = (v + pr) & 0xFF
            recon[row_out + x] = v
    pixels: list[list[tuple[int, int, int]]] = []
    for y in range(h):
        row_px: list[tuple[int, int, int]] = []
        off = y * stride
        for x in range(w):
            if color_type == 3:
                row_px.append(plte[recon[off + x]])
            else:
                row_px.append((recon[off + x * bpp], recon[off + x * bpp + 1], recon[off + x * bpp + 2]))
        pixels.append(row_px)
    return pixels


def _copy_px(px: list[list[tuple[int, int, int]]]) -> list[list[tuple[int, int, int]]]:
    return [list(r) for r in px]


def _fill_rect(px: list[list[tuple[int, int, int]]], x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
    h, w = len(px), len(px[0])
    for y in range(max(0, y0), min(h, y1)):
        for x in range(max(0, x0), min(w, x1)):
            px[y][x] = color


def _crop_px(px: list[list[tuple[int, int, int]]], x0: int, y0: int, x1: int, y1: int) -> list[list[tuple[int, int, int]]]:
    return [r[x0:x1] for r in px[y0:y1]]


def _draw_grid(px: list[list[tuple[int, int, int]]], rows: list[str], x0: int, y0: int, pal: dict[str, tuple[int, int, int]], scale: int = 1) -> None:
    h, w = len(px), len(px[0])
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in pal:
                c = pal[ch]
                for sy in range(scale):
                    for sx in range(scale):
                        nx, ny = x0 + x * scale + sx, y0 + y * scale + sy
                        if 0 <= nx < w and 0 <= ny < h:
                            px[ny][nx] = c


import math
import game_over_art
import mm2_art


def _draw_f13_brush_text(
    px: list[list[tuple[int, int, int]]],
    text: str,
    x0: int,
    y0: int,
    stripe_colors: list[tuple[int, int, int]],
    shadow: tuple[int, int, int],
    scale: int = 2,
) -> None:
    """Draw jagged, forward-slanted Friday the 13th brush lettering with Barba-palette striping."""
    # 7x11 horror brush glyphs (ragged edges, slanted top/bottom serifs)
    glyphs = {
        'C': [
            '..11111',
            '.110001',
            '1100000',
            '1100000',
            '1100000',
            '1100000',
            '1100000',
            '1100000',
            '.110001',
            '..11110',
            '.......',
        ],
        'A': [
            '...111.',
            '..11011',
            '.110011',
            '.110011',
            '1100011',
            '1111111',
            '1100011',
            '1100011',
            '1100011',
            '1000011',
            '.......',
        ],
        'M': [
            '1100011',
            '1110111',
            '1111111',
            '1101011',
            '1101011',
            '1100011',
            '1100011',
            '1100011',
            '1100011',
            '1100011',
            '.......',
        ],
        'P': [
            '111111.',
            '1100011',
            '1100011',
            '1100011',
            '111111.',
            '1100000',
            '1100000',
            '1100000',
            '1100000',
            '1100000',
            '.......',
        ],
        'B': [
            '111111.',
            '1100011',
            '1100011',
            '1100110',
            '111110.',
            '1100011',
            '1100011',
            '1100011',
            '1100011',
            '111111.',
            '.......',
        ],
        'R': [
            '111111.',
            '1100011',
            '1100011',
            '1100011',
            '111110.',
            '1101100',
            '1100110',
            '1100011',
            '1100011',
            '1100011',
            '.......',
        ],
        ' ': ['.......'] * 11,
    }
    h, w = len(px), len(px[0])
    cx = x0
    for ch in text.upper():
        g = glyphs.get(ch, glyphs[' '])
        for gy, row in enumerate(g):
            slant = (10 - gy) // 3  # forward italic slant matching FRIDAY THE 13TH
            fg = stripe_colors[gy % len(stripe_colors)]
            for gx, bit in enumerate(row):
                if bit == '1':
                    # Jagged brush shadow
                    for sy in range(scale):
                        for sx in range(scale):
                            nx = cx + (gx + slant) * scale + sx + scale
                            ny = y0 + gy * scale + sy + scale
                            if 0 <= nx < w and 0 <= ny < h:
                                px[ny][nx] = shadow
                    for sy in range(scale):
                        for sx in range(scale):
                            nx = cx + (gx + slant) * scale + sx
                            ny = y0 + gy * scale + sy
                            if 0 <= nx < w and 0 <= ny < h:
                                px[ny][nx] = fg
        cx += (8 if ch != ' ' else 5) * scale


def _jason_mask_studies(z2_bytes: bytes) -> list[tuple[str, str, list[str]]]:
    """Return 4 distinct Jason hockey-mask-on-dragon-head studies (32x16 grids)."""
    closed = [list(r) for r in boss_art.source_head(z2_bytes, 'closed')]
    roaring = [list(r) for r in boss_art.source_head(z2_bytes, 'open')]

    def apply(base: list[list[str]], overlay: list[str], ox: int = 0, oy: int = 0) -> list[str]:
        g = [list(r) for r in base]
        for y, row in enumerate(overlay):
            for x, ch in enumerate(row):
                if ch != '.' and 0 <= oy + y < 16 and 0 <= ox + x < 32:
                    g[oy + y][ox + x] = ch
        return [''.join(r) for r in g]

    # Study 1: Snout-wrap contoured mask (white shell follows snout & brow, red chevrons)
    s1 = apply(closed, [
        '.....MMMMMM.....',
        '...MMMRRRRMMM...',
        '..MM00MMMM00MM..',
        '.MMM00MMMM00MMM.',
        '.MMMMMMMRMMMMMM.',
        '..MM.MM.MM.MM...',
        '...MMMMMMMMMM...',
        '....MM.MM.MM....',
    ], ox=2, oy=3)

    # Study 2: Upper-visor half-mask (classic round Jason mask on brow/eyes, snout & fangs exposed)
    s2 = apply(closed, [
        '.....MMMMMM.....',
        '....MMMRRMMM....',
        '...MM00MM00MM...',
        '...MM00MM00MM...',
        '...MMMMMMMMMM...',
        '....MMMRRMMM....',
        '.....MMMMMM.....',
    ], ox=8, oy=2)

    # Study 3: Hinged roaring mask (upper mask over open-jaw roaring Barba)
    s3 = apply(roaring, [
        '.....MMMMMM.....',
        '....MMMRRMMM....',
        '...MM00MM00MM...',
        '...MMMMMMMMMM...',
        '....MMMRRMMM....',
        '.....MM..MM.....',
    ], ox=7, oy=1)

    # Study 4: Full-face stylized plate with horns poking above
    s4 = apply(closed, [
        '....MMMMMMMM....',
        '...MMMRRRRMMM...',
        '..MMM00MM00MMM..',
        '..MMM00MM00MMM..',
        '..MMMMMMMMMMMM..',
        '...MMMRRRRMMM...',
        '...MM.MMMM.MM...',
        '....MM.MM.MM....',
        '.....MMMMMM.....',
    ], ox=4, oy=4)

    # Map 'M'->'3'(white), 'R'->'1'(crimson), '0'->'0'(black)
    def remap(rows: list[str]) -> list[str]:
        t = str.maketrans({'M': '3', 'R': '1'})
        return [r.translate(t) for r in rows]

    return [
        ('jmask_1', 'Study 1: Snout-Wrap Contoured Mask', remap(s1)),
        ('jmask_2', 'Study 2: Upper Visor (Exposed Snout & Jaw)', remap(s2)),
        ('jmask_3', 'Study 3: Roaring Open-Jaw + Hinged Mask', remap(s3)),
        ('jmask_4', 'Study 4: Full-Face Plate + Exposed Horns', remap(s4)),
    ]


def _draw_smb_barba_sign(smb_base: list[list[tuple[int, int, int]]]) -> list[list[tuple[int, int, int]]]:
    """Replace MARIO with BARBA in the exact condensed beveled font & style of BROS."""
    out = _copy_px(smb_base)
    sign_bg = smb_base[72][48]
    peach = smb_base[76][154]  # exact BROS. peach color
    shadow = (0, 0, 0)

    # Sample y=72..115 (44px tall, including full 4px bottom drop shadow)
    def extract_glyph(x0: int, x1: int) -> list[list[str]]:
        g: list[list[str]] = []
        for y in range(72, 116):
            row: list[str] = []
            for x in range(x0, x1):
                c = smb_base[y][x]
                if c[0] > 200 and c[1] > 150:
                    row.append('P')
                elif c[0] < 30 and c[1] < 30 and c[2] < 30:
                    row.append('S')
                else:
                    row.append('.')
            g.append(row)
        return g

    g_B = extract_glyph(137, 153)
    g_R = extract_glyph(153, 169)
    g_A = extract_glyph(73, 89)

    # Clear MARIO area cleanly including full bottom shadow (x=48..135, y=70..116)
    _fill_rect(out, 48, 70, 136, 116, sign_bg)

    # Place B A R B A across x=49..134 matching BROS. exact pitch & baseline
    glyphs = [g_B, g_A, g_R, g_B, g_A]
    cur_x = 49
    for g in glyphs:
        for dy, row in enumerate(g):
            for dx, ch in enumerate(row):
                if ch == 'P':
                    out[72 + dy][cur_x + dx] = peach
                elif ch == 'S':
                    out[72 + dy][cur_x + dx] = shadow
        cur_x += 17
    return out


def _draw_go_link_pixels(z2_bytes: bytes) -> list[list[str]]:
    """Decode Z2 Game Over Link silhouette (80x96) into '0'/'3' char grid."""
    tiles, macro = game_over_art.compile_game_over_link(z2_bytes)
    from nes import decode_tile
    grid = [['0'] * 80 for _ in range(96)]
    pos = 0
    ty = 0
    while pos < len(macro) and macro[pos] != 0xFF and ty < 12:
        count = macro[pos + 2]
        pos += 3
        for tx in range(count):
            tid = macro[pos + tx]
            trows = decode_tile(tiles[tid])
            for dy in range(8):
                for dx in range(8):
                    grid[ty * 8 + dy][tx * 8 + dx] = str(trows[dy][dx])
        pos += count
        ty += 1
    return grid


def _draw_zelda_barba(zelda_base: list[list[tuple[int, int, int]]]) -> list[list[tuple[int, int, int]]]:
    """Draw BARBA in the exact chiseled ZELDA title font (brown fill + black 3D drop shadow)."""
    out = _copy_px(zelda_base)
    brown = (148, 60, 0)
    # Detect actual ZELDA brown & gold from the image
    for y in range(64, 92):
        for x in range(56, 200):
            r, g, b = zelda_base[y][x]
            if 110 < r < 180 and 30 < g < 90 and b < 30:
                brown = (r, g, b)
                break

    # Clear ZELDA brown/black pixels inside the crest (x=54..201, y=62..95) by restoring Triforce gold / pink sky
    # Sample Triforce gold around (128, 58) and sky pink at (60, 60)
    sky_pink = zelda_base[50][60]
    gold = zelda_base[58][128]
    # Reconstruct clean Triforce inverted triangle behind ZELDA (apex at (128, 126), top y=54, x=91..165)
    for y in range(64, 95):
        # Triforce width at y: linearly interpolates from (91..165) at y=54 to (128..128) at y=126
        t = (y - 54) / (126 - 54)
        half_w = 37 * (1.0 - t)
        for x in range(54, 202):
            c = zelda_base[y][x]
            # Preserve green vines (g > r and g > b)
            if c[1] > c[0] + 15 and c[1] > c[2] + 15:
                continue
            if abs(x - 128) <= half_w:
                out[y][x] = gold
            else:
                out[y][x] = sky_pink

    # Angled/chiseled ZELDA-style 12x10 glyphs (sweeping diagonals, angled serifs, wide legs)
    z_glyphs = {
        'B': [
            '111111111000',
            '011100011100',
            '011100001110',
            '011100011100',
            '011111110000',
            '011100011100',
            '011100001110',
            '011100001110',
            '011100011100',
            '111111111000',
        ],
        'A': [
            '000011110000',
            '000111111000',
            '001110011100',
            '011100001110',
            '011100001110',
            '111111111111',
            '111000000111',
            '111000000111',
            '111000000111',
            '111100001111',
        ],
        'R': [
            '111111111000',
            '011100011100',
            '011100001110',
            '011100011100',
            '011111110000',
            '011101110000',
            '011100111000',
            '011100011100',
            '011100001110',
            '111100001111',
        ],
    }
    # Scale -> ~26px wide x 28px tall (matches ZELDA height y=64..91)
    scale_x, scale_y = 2.4, 2.8
    word = 'BARBA'
    start_x, start_y = 54, 64
    face = [[False] * 256 for _ in range(240)]
    for idx, ch in enumerate(word):
        g = z_glyphs[ch]
        bx = start_x + idx * 30
        for gy, row in enumerate(g):
            for gx, bit in enumerate(row):
                if bit == '1':
                    y0 = int(start_y + gy * scale_y)
                    y1 = int(start_y + (gy + 1) * scale_y)
                    x0 = int(bx + gx * scale_x)
                    x1 = int(bx + (gx + 1) * scale_x)
                    for py in range(y0, y1):
                        for px_x in range(x0, x1):
                            if 0 <= px_x < 256 and 0 <= py < 240:
                                face[py][px_x] = True

    # 3px black drop shadow below+right, then warm brown fill
    for y in range(60, 100):
        for x in range(50, 208):
            if face[y][x]:
                for dy in range(1, 4):
                    for dx in range(1, 3):
                        if y + dy < 240 and x + dx < 256:
                            out[y + dy][x + dx] = (0, 0, 0)
    for y in range(60, 100):
        for x in range(50, 208):
            if face[y][x]:
                out[y][x] = brown
    return out


def _draw_wheel_s1_barba(wheel_s1: list[list[tuple[int, int, int]]]) -> list[list[tuple[int, int, int]]]:
    """Replace FORTUNE with BARBA on Wheel Screen 1 preserving pink+white-outline font."""
    out = _copy_px(wheel_s1)
    # Clear FORTUNE (x=134..225, y=77..95), keeping PRES above (y<=69) and ® at x>=225
    _fill_rect(out, 134, 77, 225, 95, (0, 0, 0))
    # Clear BARBA EDITION subtitle below if we're unifying to WHEEL OF BARBA
    _fill_rect(out, 60, 95, 200, 108, (0, 0, 0))

    pink = (254, 110, 204)
    white = (255, 255, 255)
    # 11x14 pink face (3px vertical stems, 2px horizontal bars) + 1px white outline = 16px tall (matches WHEEL)
    glyphs = {
        'B': [
            '11111111110',
            '11111111111',
            '11100000111',
            '11100000111',
            '11100000111',
            '11100000111',
            '11111111110',
            '11111111110',
            '11100000111',
            '11100000111',
            '11100000111',
            '11100000111',
            '11111111111',
            '11111111110',
        ],
        'A': [
            '00111111100',
            '01111111110',
            '11100000111',
            '11100000111',
            '11100000111',
            '11100000111',
            '11111111111',
            '11111111111',
            '11100000111',
            '11100000111',
            '11100000111',
            '11100000111',
            '11100000111',
            '11100000111',
        ],
        'R': [
            '11111111110',
            '11111111111',
            '11100000111',
            '11100000111',
            '11100000111',
            '11100000111',
            '11111111110',
            '11111111100',
            '11100111000',
            '11100011100',
            '11100001110',
            '11100000111',
            '11100000111',
            '11100000111',
        ],
    }
    face = [[False] * 256 for _ in range(240)]
    for idx, ch in enumerate('BARBA'):
        g = glyphs[ch]
        bx = 138 + idx * 17
        for gy, row in enumerate(g):
            py = 79 + gy
            for gx, bit in enumerate(row):
                if bit == '1':
                    px_x = bx + gx
                    if px_x < 224 and py < 93:
                        face[py][px_x] = True
    # 1px white outline around face, then pink fill
    for y in range(77, 95):
        for x in range(135, 225):
            if face[y][x]:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if not face[y + dy][x + dx]:
                            out[y + dy][x + dx] = white
    for y in range(77, 95):
        for x in range(135, 225):
            if face[y][x]:
                out[y][x] = pink
    return out


def _draw_wheel_s2_barba(wheel_s2: list[list[tuple[int, int, int]]]) -> list[list[tuple[int, int, int]]]:
    """Replace FORTUNE on the bottom arc of the big wheel with curved BARBA in same font/colors."""
    out = _copy_px(wheel_s2)
    # Sample exact grey, orange outline, and dark shadow from WHEEL top arc
    orange = (228, 148, 24)
    grey = (160, 160, 160)
    shadow = (84, 84, 84)
    for y in range(25, 55):
        for x in range(110, 146):
            r, g, b = wheel_s2[y][x]
            if r > 200 and 100 < g < 180 and b < 60:
                orange = (r, g, b)
            elif 120 < r < 200 and abs(r - g) < 15 and abs(g - b) < 15:
                grey = (r, g, b)

    # Erase FORTUNE pixels along the bottom arc (radius 34..62 around center (128, 108), y >= 110)
    # Preserve blue/purple stars (where b > r + 20) and preserve the inner orange/grey wheel ring (r < 34)
    cx, cy = 128.0, 108.0
    for y in range(110, 174):
        for x in range(56, 200):
            dist = math.hypot(x - cx, y - cy)
            if 34.5 <= dist <= 62.0:
                r, g, b = out[y][x]
                if b > r + 20:  # keep purple/blue perimeter stars
                    continue
                out[y][x] = (0, 0, 0)

    # Straight-edged rotated rectangular 8x8 glyphs matching WHEEL's wedge-block geometry on top arc
    glyphs = {
        'B': [
            '11111111',
            '11111111',
            '11100111',
            '11111110',
            '11111110',
            '11100111',
            '11111111',
            '11111111',
        ],
        'A': [
            '11111111',
            '11111111',
            '11100111',
            '11111111',
            '11111111',
            '11100111',
            '11100111',
            '11100111',
        ],
        'R': [
            '11111111',
            '11111111',
            '11100111',
            '11111111',
            '11111110',
            '11101111',
            '11100111',
            '11100111',
        ],
    }
    face = [[False] * 256 for _ in range(240)]
    word = 'BARBA'
    # Each letter is a straight-edged rotated rectangle centered at radius 47 along the bottom arc
    angles = [140.0, 115.0, 90.0, 65.0, 40.0]
    box_w, box_h = 17.0, 22.0
    rad_c = 47.0
    for ch, deg in zip(word, angles):
        th = math.radians(deg)
        lx = cx + rad_c * math.cos(th)
        ly = cy + rad_c * math.sin(th)
        # Local axes: right = (sin, -cos), up = (-cos, -sin)
        rx, ry = math.sin(th), -math.cos(th)
        ux, uy = -math.cos(th), -math.sin(th)
        g = glyphs[ch]
        for y in range(114, 176):
            for x in range(52, 204):
                dx, dy = x - lx, y - ly
                u = dx * rx + dy * ry
                v = dx * ux + dy * uy
                if -box_w / 2 <= u <= box_w / 2 and -box_h / 2 <= v <= box_h / 2:
                    gx = int((u + box_w / 2) / box_w * 8)
                    gy = int((box_h / 2 - v) / box_h * 8)
                    if 0 <= gx < 8 and 0 <= gy < 8 and g[gy][gx] == '1':
                        face[y][x] = True

    # Drop shadow (+2, +2), orange 1px outline, grey fill
    for y in range(115, 174):
        for x in range(56, 200):
            if face[y][x]:
                if y + 2 < 240 and x + 2 < 256 and not face[y + 2][x + 2]:
                    out[y + 2][x + 2] = shadow
    for y in range(115, 174):
        for x in range(56, 200):
            if face[y][x]:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if not face[y + dy][x + dx]:
                            out[y + dy][x + dx] = orange
    for y in range(115, 174):
        for x in range(56, 200):
            if face[y][x]:
                out[y][x] = grey

    # Keep vanilla scrolling 'PRESENTS - WHEEL • o' intact, complete 'f • BARBA' in the exact 14px orange+white font
    _fill_rect(out, 187, 215, 256, 233, (0, 0, 0))
    mq_glyphs = {
        'f': [
            '00111', '01111', '01100', '11111', '11111', '01100',
            '01100', '01100', '01100', '01100', '01100', '01100',
            '01100', '01100',
        ],
        'B': [
            '111111110', '111111111', '110000011', '110000011', '110000011', '110000011',
            '111111110', '111111110', '110000011', '110000011', '110000011', '110000011',
            '111111111', '111111110',
        ],
        'A': [
            '001111100', '011111110', '110000011', '110000011', '110000011', '110000011',
            '111111111', '111111111', '110000011', '110000011', '110000011', '110000011',
            '110000011', '110000011',
        ],
        'R': [
            '111111110', '111111111', '110000011', '110000011', '110000011', '110000011',
            '111111110', '111111100', '110011000', '110001100', '110000110', '110000011',
            '110000011', '110000011',
        ],
    }
    mq_face = [[False] * 256 for _ in range(240)]
    for gy, row in enumerate(mq_glyphs['f']):
        for gx, bit in enumerate(row):
            if bit == '1':
                mq_face[217 + gy][187 + gx] = True
    # Small diamond dot '•' at x=194..196, y=222..225
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, 2), (2, 1)):
        mq_face[222 + dy][194 + dx] = True
    for idx, ch in enumerate('BARBA'):
        g = mq_glyphs[ch]
        bx = 200 + idx * 11
        for gy, row in enumerate(g):
            for gx, bit in enumerate(row):
                if bit == '1' and bx + gx < 255:
                    mq_face[217 + gy][bx + gx] = True
    white = (255, 255, 255)
    for y in range(216, 232):
        for x in range(187, 255):
            if mq_face[y][x]:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if 0 <= x + dx < 256 and not mq_face[y + dy][x + dx]:
                            out[y + dy][x + dx] = white
    for y in range(216, 232):
        for x in range(187, 255):
            if mq_face[y][x]:
                out[y][x] = orange
    return out


def _draw_mm2_rooftop_candidates(
    mm2_base: list[list[tuple[int, int, int]]],
    z2_bytes: bytes,
) -> tuple[list[list[tuple[int, int, int]]], list[list[tuple[int, int, int]]], list[list[tuple[int, int, int]]]]:
    """Build fixed-A MM2 title, Candidate A (Full-Body Barba + junction/tail), Candidate B (Mega Man + Barba snout)."""
    from nes import decode_tile
    # Render fixed compile_title_logo() onto mm2_base so the clipped trailing A is fixed!
    fixed_base = _copy_px(mm2_base)
    logo_bytes = mm2_art.compile_title_logo()
    # Title BG Pal 1 from mm2_current_title.png: 0=black, 1=cyan(60,188,252), 2=white(255,255,255), 3=dark green(0,80,0)
    logo_pal = {
        0: (0, 0, 0),
        1: fixed_base[80][32] if fixed_base[80][32][2] > 150 else (60, 188, 252),
        2: (255, 255, 255),
        3: (0, 88, 0),
    }
    row_spans = [(8, 7, 25), (9, 6, 26), (10, 5, 27), (11, 4, 28)]
    off = 0
    for ty, col_s, col_e in row_spans:
        for tx in range(col_s, col_e):
            trows = decode_tile(logo_bytes[off : off + 16])
            off += 16
            for dy in range(8):
                for dx in range(8):
                    fixed_base[ty * 8 + dy][tx * 8 + dx] = logo_pal[trows[dy][dx]]

    # Rooftop wall background around x=196..224, y=118..146 (light grey building parapet)
    sky_grey = fixed_base[124][230]
    barba_pal = {'1': NES_RGB[0x16], '2': NES_RGB[0x27], '3': NES_RGB[0x30]}

    # Candidate A: Full-Body 3x3-metatile (48x48) Barba: head + vertical torso + junction + horizontal torso + tail
    cand_a = _copy_px(fixed_base)
    _fill_rect(cand_a, 198, 118, 224, 144, sky_grey)
    import assets
    from nes import encode_tile
    frames24 = boss_art.make_frames(z2_bytes, width=24)
    walk0_r0 = frames24['walk0'][16:32]
    gfx = {
        0x06: encode_tile([r[8:16] for r in walk0_r0[:8]]) + encode_tile([r[8:16] for r in walk0_r0[8:16]]),
        0x08: encode_tile([r[16:24] for r in walk0_r0[:8]]) + encode_tile([r[16:24] for r in walk0_r0[8:16]]),
    }
    elbow_16 = assets.encounter_connector_rows(gfx)
    trail_32 = assets.encounter_trail_rows(gfx)
    # Assemble 48x48 (3x3 metatile) Barba: head+vertical torso (24x32) at (0,0),
    # junction (16x16) at (8,32), horizontal torso+tail (32x16) at (24,32)
    full_barba = [['0'] * 56 for _ in range(48)]
    for y in range(32):
        for x in range(24):
            full_barba[y][x] = frames24['idle'][y][x]
    for y in range(16):
        for x in range(16):
            if elbow_16[y][x] != '0':
                full_barba[32 + y][8 + x] = elbow_16[y][x]
        for x in range(32):
            if trail_32[y][x] != '0':
                full_barba[32 + y][24 + x] = trail_32[y][x]
    _draw_grid(cand_a, [''.join(r) for r in full_barba], 188, 100, barba_pal, scale=1)

    # Candidate B: Mega Man blue body & helmet with Barba dragon head + snout sticking out!
    cand_b = _copy_px(fixed_base)
    _fill_rect(cand_b, 198, 118, 224, 144, sky_grey)
    mm_body = [
        '......BBBBBB......',
        '....BBBBBBBBBB....',
        '...BBBCCCCCCBBB...',
        '...BBCCCCCCCCBB...',
        '...BBCCCCCCCCBB...',
        '....BBBBBBBBBB....',
        '.....BBBBBBBB.....',
        '....BBCCCCCCBB....',
        '...BBBCCCCCCBBB...',
        '..BBBBBBBBBBBBBB..',
        '..BB..BBBBBB..BB..',
        '......BBBBBB......',
        '.....BBB..BBB.....',
        '....BBBB..BBBB....',
        '...BBBBB..BBBBB...',
    ]
    mm_pal = {'B': NES_RGB[0x11], 'C': NES_RGB[0x2C]}
    _draw_grid(cand_b, mm_body, 202, 129, mm_pal, scale=1)
    # Barba snout/face sticking out left of the Mega Man helmet
    snout = [
        '..3311..',
        '.221122.',
        '2233111.',
        '.112211.',
        '..1111..',
    ]
    _draw_grid(cand_b, snout, 197, 133, barba_pal, scale=1)

    return fixed_base, cand_a, cand_b


def _draw_block_text(px: list[list[tuple[int, int, int]]], text: str, x0: int, y0: int, fg: tuple[int, int, int], shadow: tuple[int, int, int] | None = None, scale: int = 1) -> None:
    font5x7 = {
        'A': ['01110', '10001', '10001', '11111', '10001', '10001', '10001'],
        'B': ['11110', '10001', '10001', '11110', '10001', '10001', '11110'],
        'C': ['01110', '10001', '10000', '10000', '10000', '10001', '01110'],
        'D': ['11110', '10001', '10001', '10001', '10001', '10001', '11110'],
        'E': ['11111', '10000', '10000', '11110', '10000', '10000', '11111'],
        'F': ['11111', '10000', '10000', '11110', '10000', '10000', '10000'],
        'G': ['01110', '10001', '10000', '10111', '10001', '10001', '01110'],
        'H': ['10001', '10001', '10001', '11111', '10001', '10001', '10001'],
        'I': ['11111', '00100', '00100', '00100', '00100', '00100', '11111'],
        'K': ['10001', '10010', '10100', '11000', '10100', '10010', '10001'],
        'L': ['10000', '10000', '10000', '10000', '10000', '10000', '11111'],
        'M': ['10001', '11011', '10101', '10001', '10001', '10001', '10001'],
        'N': ['10001', '11001', '10101', '10011', '10001', '10001', '10001'],
        'O': ['01110', '10001', '10001', '10001', '10001', '10001', '01110'],
        'P': ['11110', '10001', '10001', '11110', '10000', '10000', '10000'],
        'R': ['11110', '10001', '10001', '11110', '10100', '10010', '10001'],
        'S': ['01111', '10000', '10000', '01110', '00001', '00001', '11110'],
        'T': ['11111', '00100', '00100', '00100', '00100', '00100', '00100'],
        'U': ['10001', '10001', '10001', '10001', '10001', '10001', '01110'],
        'V': ['10001', '10001', '10001', '10001', '10001', '01010', '00100'],
        'W': ['10001', '10001', '10001', '10001', '10101', '11011', '10001'],
        'Y': ['10001', '10001', '01010', '00100', '00100', '00100', '00100'],
        'Z': ['11111', '00001', '00010', '00100', '01000', '10000', '11111'],
        ' ': ['00000'] * 7,
    }
    h, w = len(px), len(px[0])
    cx = x0
    for ch in text.upper():
        g = font5x7.get(ch, font5x7[' '])
        for gy, row in enumerate(g):
            for gx, bit in enumerate(row):
                if bit == '1':
                    if shadow:
                        for sy in range(scale):
                            for sx in range(scale):
                                nx, ny = cx + gx * scale + sx + scale, y0 + gy * scale + sy + scale
                                if 0 <= nx < w and 0 <= ny < h:
                                    px[ny][nx] = shadow
                    for sy in range(scale):
                        for sx in range(scale):
                            nx, ny = cx + gx * scale + sx, y0 + gy * scale + sy
                            if 0 <= nx < w and 0 <= ny < h:
                                px[ny][nx] = fg
        cx += 6 * scale


def _copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        shutil.copy2(src, dst)


_VANILLA_SPECS: list[tuple[str, str, list[str], str]] = [
    (
        'f13',
        'f13.nes',
        ['f13_vanilla_title.png'],
        """
local f = 0
emu.addEventCallback(function()
    f = f + 1
    if f == 420 then
        local pf = assert(io.open(OUTPUT_DIR .. '/f13_vanilla_title.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    ),
    (
        'smb',
        'smb.nes',
        ['smb_vanilla_title.png'],
        """
local f = 0
emu.addEventCallback(function()
    f = f + 1
    if f == 45 then
        local pf = assert(io.open(OUTPUT_DIR .. '/smb_vanilla_title.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    ),
    (
        'mtpo',
        'mtpo.nes',
        ['mtpo_vanilla_title2.png'],
        """
local f = 0
local inp = {}
emu.addEventCallback(function() emu.setInput(inp, 0) end, emu.eventType.inputPolled)
emu.addEventCallback(function()
    f = f + 1
    inp = {}
    if f >= 180 and f < 185 then inp.start = true end
    if f >= 240 and f < 245 then inp.start = true end
    if f == 300 then
        local pf = assert(io.open(OUTPUT_DIR .. '/mtpo_vanilla_title2.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    ),
    (
        'mm2',
        'mm2.nes',
        ['mm2_vanilla_title.png'],
        """
local f = 0
local inp = {}
emu.addEventCallback(function() emu.setInput(inp, 0) end, emu.eventType.inputPolled)
emu.addEventCallback(function()
    f = f + 1
    inp = {}
    if f >= 180 and f < 185 then inp.start = true end
    if f == 300 then
        local pf = assert(io.open(OUTPUT_DIR .. '/mm2_vanilla_title.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    ),
    (
        'wheel',
        'wheel.nes',
        ['wheel_vanilla_s1.png', 'wheel_vanilla_s2.png'],
        """
local f = 0
emu.addEventCallback(function()
    f = f + 1
    if f == 180 then
        local pf = assert(io.open(OUTPUT_DIR .. '/wheel_vanilla_s1.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
    elseif f == 1000 then
        local pf = assert(io.open(OUTPUT_DIR .. '/wheel_vanilla_s2.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    ),
    (
        'zelda',
        'zelda.nes',
        ['zelda_vanilla_title.png'],
        """
local f = 0
emu.addEventCallback(function()
    f = f + 1
    if f == 120 then
        local pf = assert(io.open(OUTPUT_DIR .. '/zelda_vanilla_title.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    ),
]


def capture_vanilla(force: bool = False) -> None:
    """Capture genuine vanilla title screenshots directly from roms/*.nes via Mesen."""
    import emulator_test

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    build_dir = ROOT / 'build'
    build_dir.mkdir(exist_ok=True)
    for key, rom_name, out_files, lua in _VANILLA_SPECS:
        if not force and all((OUT_DIR / f).exists() for f in out_files):
            continue
        rom_path = ROOT / 'roms' / rom_name
        if not rom_path.exists():
            raise FileNotFoundError(f'Missing vanilla ROM: {rom_path}')
        lua_path = build_dir / f'capture_vanilla_{key}.lua'
        lua_path.write_text(lua, encoding='utf-8')
        rc = emulator_test.run(lua_path, rom_path, timeout=30)
        if rc != 0:
            raise RuntimeError(f'Vanilla title capture failed for {rom_name} (exit {rc})')
        for fname in out_files:
            shutil.copy2(build_dir / fname, OUT_DIR / fname)


def generate_all(recapture_vanilla: bool = False) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    capture_vanilla(force=recapture_vanilla)
    z2_bytes = load_source(ROOT / 'roms' / 'z2.nes')
    barba_frames = boss_art.make_frames(z2_bytes, width=24)
    barba_pal = {'1': NES_RGB[0x16], '2': NES_RGB[0x27], '3': NES_RGB[0x30]}
    # Striping lifted straight from Barba's vanilla torso/head palette (cream, gold, crimson)
    barba_stripes = [
        NES_RGB[0x30],
        NES_RGB[0x27],
        NES_RGB[0x16],
        NES_RGB[0x16],
        NES_RGB[0x27],
        NES_RGB[0x30],
        NES_RGB[0x27],
        NES_RGB[0x16],
        NES_RGB[0x16],
        NES_RGB[0x06],
    ]

    # 1. Copy captured baseline screenshots
    _copy_if_exists(SCRATCH / 'title_f13.png', OUT_DIR / 'f13_current_mask.png')
    _copy_if_exists(SCRATCH / 'title_f13_420.png', OUT_DIR / 'f13_current_title.png')
    _copy_if_exists(SCRATCH / 'title_smb.png', OUT_DIR / 'smb_current_title.png')
    _copy_if_exists(ROOT / 'build' / 'smb_barba_03_super_roar.png', OUT_DIR / 'smb_fixed_roar.png')
    _copy_if_exists(ROOT / 'build' / 'smb_barba_04_super_barba.png', OUT_DIR / 'smb_fixed_big.png')
    _copy_if_exists(SCRATCH / 'title_mtpo_420.png', OUT_DIR / 'mtpo_current_title2.png')
    _copy_if_exists(ROOT / 'build' / 'mm2_title.png', OUT_DIR / 'mm2_current_title.png')
    _copy_if_exists(SCRATCH / 'title_wheel.png', OUT_DIR / 'wheel_current_s1.png')
    _copy_if_exists(ROOT / 'build' / 'wheel_t_1000.png', OUT_DIR / 'wheel_current_s2.png')
    _copy_if_exists(SCRATCH / 'title_zelda.png', OUT_DIR / 'zelda_current_title.png')

    # 2. Friday the 13th: CAMP BARBA + Left Barba (vanilla Barba colors)
    f13_base = _read_png(OUT_DIR / 'f13_current_title.png')
    f13_a = _copy_px(f13_base)
    _draw_grid(f13_a, barba_frames['attack'], 6, 70, barba_pal, scale=2)
    _draw_f13_brush_text(f13_a, 'CAMP BARBA', 60, 134, barba_stripes, NES_RGB[0x06], scale=2)
    write_png(OUT_DIR / 'f13_cand_a.png', f13_a)

    # Alternate striping rhythm (gold/crimson alternating bands)
    alt_stripes = [
        NES_RGB[0x27], NES_RGB[0x27], NES_RGB[0x16], NES_RGB[0x16],
        NES_RGB[0x30], NES_RGB[0x27], NES_RGB[0x16], NES_RGB[0x16],
        NES_RGB[0x27], NES_RGB[0x16],
    ]
    f13_b = _copy_px(f13_base)
    _draw_grid(f13_b, barba_frames['idle'], 6, 70, barba_pal, scale=2)
    _draw_f13_brush_text(f13_b, 'CAMP BARBA', 60, 134, alt_stripes, NES_RGB[0x06], scale=2)
    write_png(OUT_DIR / 'f13_cand_b.png', f13_b)

    # 2b. Dedicated Jason Mask Lab (4 dragon-head mask studies at 4x on 160x96)
    jmask_cands = []
    for jid, jlabel, jgrid in _jason_mask_studies(z2_bytes):
        canvas = [[NES_RGB[0x0F]] * 160 for _ in range(96)]
        _draw_grid(canvas, jgrid, 16, 16, barba_pal, scale=4)
        fname = f'{jid}.png'
        write_png(OUT_DIR / fname, canvas)
        jmask_cands.append({
            'id': jid,
            'label': jlabel,
            'img': f'previews/titles/{fname}',
            'caption': '32x16 Barba dragon head at 4x scale.',
        })

    # 3. Super Barba Bros. (BARBA matched to BROS. font + tiny Barba kept in demo mode)
    smb_base = _read_png(OUT_DIR / 'smb_current_title.png')
    smb_a = _draw_smb_barba_sign(smb_base)
    write_png(OUT_DIR / 'smb_cand_a.png', smb_a)

    # 4. Barba's Punch-Out!! (Z2 Game Over Link silhouette + EVIL LINK matching MIKE TYSON)
    mtpo_base = _read_png(OUT_DIR / 'mtpo_current_title2.png')
    mtpo_zoom = _crop_px(mtpo_base, 84, 44, 172, 136)
    write_png(OUT_DIR / 'mtpo_link_zoom.png', mtpo_zoom, scale=2)

    mtpo_a = _copy_px(mtpo_base)
    _fill_rect(mtpo_a, 89, 49, 166, 120, (136, 136, 252))
    _fill_rect(mtpo_a, 89, 120, 166, 126, (120, 40, 0))
    go_grid = _draw_go_link_pixels(z2_bytes)
    # Center 80x96 silhouette inside 77x77 portrait box (crop 2px sides, start at y=49..126)
    go_cropped = [r[2:78] for r in go_grid[2:78]]
    go_pal = {'3': (0, 0, 0), '1': NES_RGB[0x16], '2': NES_RGB[0x27]}
    _draw_grid(mtpo_a, go_cropped, 89, 49, go_pal, scale=1)
    # Match MIKE TYSON bold green + 1px white outline font & positioning (above LINK IS WAITING at y=176)
    _fill_rect(mtpo_a, 80, 134, 176, 172, (0, 0, 0))
    mtpo_glyphs = {
        'E': [
            '1111111',
            '1111111',
            '1110000',
            '1111110',
            '1111110',
            '1110000',
            '1111111',
            '1111111',
        ],
        'V': [
            '11100111',
            '11100111',
            '11100111',
            '11100111',
            '01111110',
            '01111110',
            '00111100',
            '00011000',
        ],
        'I': [
            '111',
            '111',
            '111',
            '111',
            '111',
            '111',
            '111',
            '111',
        ],
        'L': [
            '1110000',
            '1110000',
            '1110000',
            '1110000',
            '1110000',
            '1110000',
            '1111111',
            '1111111',
        ],
        'N': [
            '11100111',
            '11110111',
            '11111111',
            '11111111',
            '11101111',
            '11100111',
            '11100111',
            '11100111',
        ],
        'K': [
            '11100111',
            '11101110',
            '11111100',
            '11111000',
            '11111100',
            '11101110',
            '11100111',
            '11100111',
        ],
    }
    mtpo_face = [[False] * 256 for _ in range(240)]
    for word, wy in (('LINK', 145),):
        total_w = sum(len(mtpo_glyphs[c][0]) * 2 for c in word) + (len(word) - 1) * 2
        cx = 128 - total_w // 2
        for ch in word:
            g = mtpo_glyphs[ch]
            for gy, row in enumerate(g):
                for gx, bit in enumerate(row):
                    if bit == '1':
                        for sy in range(2):
                            for sx in range(2):
                                py = wy + gy * 2 + sy
                                px_x = cx + gx * 2 + sx
                                if 0 <= px_x < 256 and 0 <= py < 240:
                                    mtpo_face[py][px_x] = True
            cx += len(g[0]) * 2 + 2
    mtpo_green = (0, 148, 0)
    mtpo_white = (236, 238, 236)
    for y in range(134, 172):
        for x in range(76, 180):
            if mtpo_face[y][x]:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if not mtpo_face[y + dy][x + dx]:
                            mtpo_a[y + dy][x + dx] = mtpo_white
    for y in range(134, 172):
        for x in range(76, 180):
            if mtpo_face[y][x]:
                mtpo_a[y][x] = mtpo_green
    write_png(OUT_DIR / 'mtpo_cand_a.png', mtpo_a)

    # 5. Mega Barba 2 (Fixed trailing A + Full-Body vs Helmet-Snout candidates)
    mm2_base = _read_png(OUT_DIR / 'mm2_current_title.png')
    mm2_fixed, mm2_cand_a, mm2_cand_b = _draw_mm2_rooftop_candidates(mm2_base, z2_bytes)
    write_png(OUT_DIR / 'mm2_logo_zoom.png', _crop_px(mm2_fixed, 32, 24, 244, 184))
    write_png(OUT_DIR / 'mm2_cand_a.png', mm2_cand_a)
    write_png(OUT_DIR / 'mm2_cand_b.png', mm2_cand_b)

    # 6. Wheel of Barba (Preserve font/theme/arc, replace FORTUNE with BARBA)
    wheel_s1 = _read_png(OUT_DIR / 'wheel_current_s1.png')
    wheel_s2 = _read_png(OUT_DIR / 'wheel_current_s2.png')
    write_png(OUT_DIR / 'wheel_cand_s1.png', _draw_wheel_s1_barba(wheel_s1))
    write_png(OUT_DIR / 'wheel_cand_s2.png', _draw_wheel_s2_barba(wheel_s2))

    # 7. Zelda 1 (BARBA matching ZELDA font + Lava waterfall keeping white foam)
    zelda_base = _read_png(OUT_DIR / 'zelda_current_title.png')
    zelda_a = _draw_zelda_barba(zelda_base)
    write_png(OUT_DIR / 'zelda_cand_a.png', zelda_a)

    zelda_b = _copy_px(zelda_a)
    import assets
    from nes import CHR_OFFSET, decode_tile
    lava_tiles = [
        decode_tile(z2_bytes[CHR_OFFSET + assets.TITLE_CHR_BANK * 4096 + tid * 16 : CHR_OFFSET + assets.TITLE_CHR_BANK * 4096 + (tid + 1) * 16])
        for tid in assets.TITLE_LAVA_TILES[:2]
    ]
    z2_lava_pal = {
        0: (0, 0, 0),
        1: (234, 158, 34),   # $27 amber
        2: (181, 49, 32),    # $16 crimson
        3: (108, 6, 0),      # $06 dark red
    }
    for y in range(180, 240):
        for x in range(80, 112):
            r, g, b = zelda_base[y][x]
            # Keep only the top 2 rows of each white foam crest; thin out lower foam into lava
            if r > 220 and g > 220 and b > 220:
                is_top_crest = any(
                    y - dy >= 180 and not (zelda_base[y - dy][x][0] > 220 and zelda_base[y - dy][x][1] > 220 and zelda_base[y - dy][x][2] > 220)
                    for dy in (1, 2)
                )
                if is_top_crest:
                    continue
                tile = lava_tiles[((x // 8) + (y // 8)) % 2]
                zelda_b[y][x] = z2_lava_pal[tile[y % 8][x % 8]]
                continue
            # Recolor mint/cyan water body using actual Z2 title lava tiles (8x8)
            if g > 140 and b > 140:
                tile = lava_tiles[((x // 8) + (y // 8)) % 2]
                zelda_b[y][x] = z2_lava_pal[tile[y % 8][x % 8]]
    write_png(OUT_DIR / 'zelda_cand_b.png', zelda_b)

    catalog = {
        'done_games': [
            {'id': 'dk', 'name': 'Barba Kong', 'note': 'Title screen & arcade cabinet done.'},
            {'id': 'duck', 'name': "Barba's Hunt", 'note': 'Title screen & forest sprites done.'},
            {'id': 'feud', 'name': "Barba's Beef", 'note': 'Title, cast & ordinal rounds done.'},
            {'id': 'waldo', 'name': "Where's Barba?", 'note': 'Title screen & crowd tagger done.'},
        ],
        'games': [
            {
                'id': 'f13',
                'name': 'Friday the 13th: Camp Barba',
                'status_label': 'CAMP BARBA + Attack Barba',
                'summary': 'Left-side Attack Barba in vanilla colors with CAMP BARBA in the jagged F13 brush font striped with Barba’s torso/head palette.',
                'screens': [
                    {
                        'title': 'Title Screen',
                        'vanilla': {'label': 'Vanilla', 'img': 'previews/titles/f13_vanilla_title.png', 'caption': 'Vanilla FRIDAY THE 13TH logo'},
                        'ours': {'label': 'Our Version', 'img': 'previews/titles/f13_cand_a.png', 'caption': 'Attack Barba + Striped CAMP BARBA'},
                    },
                ],
            },
            {
                'id': 'smb',
                'name': 'Super Barba Bros.',
                'status_label': 'SUPER BARBA BROS. Sign',
                'summary': 'BARBA matched pixel-for-pixel to BROS. font, bevels, and 3D drop shadow; keeps tiny Wyrmling in demo mode.',
                'screens': [
                    {
                        'title': 'Title Screen',
                        'vanilla': {'label': 'Vanilla', 'img': 'previews/titles/smb_vanilla_title.png', 'caption': 'SUPER MARIO BROS. sign'},
                        'ours': {'label': 'Our Version', 'img': 'previews/titles/smb_cand_a.png', 'caption': 'SUPER BARBA BROS. sign'},
                    },
                ],
            },
            {
                'id': 'mtpo',
                'name': "Barba's Punch-Out!!",
                'status_label': 'Z2 Game Over Link + EVIL LINK',
                'summary': 'Looming Zelda 2 Game Over Link silhouette inside the Title2 portrait frame with EVIL LINK in MIKE TYSON positioning.',
                'screens': [
                    {
                        'title': 'Title2 Screen',
                        'vanilla': {'label': 'Vanilla', 'img': 'previews/titles/mtpo_vanilla_title2.png', 'caption': "Vanilla MIKE TYSON'S PUNCH-OUT!! Title2"},
                        'ours': {'label': 'Our Version', 'img': 'previews/titles/mtpo_cand_a.png', 'caption': 'Z2 Game Over Link Silhouette + EVIL LINK'},
                    },
                ],
            },
            {
                'id': 'mm2',
                'name': 'Mega Barba 2 (Barba Man 2)',
                'status_label': 'MEGA BARBA II + Rooftop Barba',
                'summary': 'Unclipped trailing A in MEGA BARBA II with full-body Barba standing on the skyscraper rooftop.',
                'screens': [
                    {
                        'title': 'Title Screen',
                        'vanilla': {'label': 'Vanilla', 'img': 'previews/titles/mm2_vanilla_title.png', 'caption': 'Vanilla MEGA MAN II title screen'},
                        'ours': {'label': 'Our Version', 'img': 'previews/titles/mm2_cand_a.png', 'caption': 'Unclipped MEGA BARBA II + Full-Body Rooftop Barba'},
                    },
                ],
            },
            {
                'id': 'wheel',
                'name': 'Wheel of Barba',
                'status_label': 'WHEEL OF BARBA',
                'summary': 'Replaces FORTUNE with BARBA on both Screen 1 and the Screen 2 bottom wheel arc, preserving the exact fonts, colors, and curved wheel geometry.',
                'screens': [
                    {
                        'title': 'Screen 1 (Splash)',
                        'vanilla': {'label': 'Vanilla', 'img': 'previews/titles/wheel_vanilla_s1.png', 'caption': 'Vanilla WHEEL of FORTUNE FAMILY EDITION'},
                        'ours': {'label': 'Our Version', 'img': 'previews/titles/wheel_cand_s1.png', 'caption': 'WHEEL • of • BARBA'},
                    },
                    {
                        'title': 'Screen 2 (Big Wheel)',
                        'vanilla': {'label': 'Vanilla', 'img': 'previews/titles/wheel_vanilla_s2.png', 'caption': 'Vanilla WHEEL OF FORTUNE'},
                        'ours': {'label': 'Our Version', 'img': 'previews/titles/wheel_cand_s2.png', 'caption': 'Curved Bottom-Arc BARBA'},
                    },
                ],
            },
            {
                'id': 'zelda',
                'name': 'The Legend of Barba (Zelda 1)',
                'status_label': 'THE LEGEND OF BARBA + Lava Falls',
                'summary': 'Chiseled brown+black BARBA matching ZELDA’s font plus flowing Palace VI crimson/amber lava falls keeping the vanilla white foam crests.',
                'screens': [
                    {
                        'title': 'Title Screen',
                        'vanilla': {'label': 'Vanilla', 'img': 'previews/titles/zelda_vanilla_title.png', 'caption': 'THE LEGEND OF ZELDA'},
                        'ours': {'label': 'Our Version', 'img': 'previews/titles/zelda_cand_b.png', 'caption': 'THE LEGEND OF BARBA + Lava Falls (with white foam)'},
                    },
                ],
            },
        ],
    }

    DATA_JS.write_text('window.TITLE_REVIEW_DATA = ' + json.dumps(catalog, indent=2) + ';\n', encoding='utf-8')
    print(f'Generated title review assets in {OUT_DIR} and {DATA_JS}')
    return catalog


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-vanilla', action='store_true', help='Re-capture all vanilla title PNGs from roms/*.nes')
    args = parser.parse_args()
    generate_all(recapture_vanilla=args.capture_vanilla)
