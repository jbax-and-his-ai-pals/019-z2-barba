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

    # Extract exact B (x=148..164) and R (x=166..182) from BROS., and A (x=68..84) from MARIO!
    # Sample y=72..111 (40px tall)
    def extract_glyph(x0: int, x1: int) -> list[list[str]]:
        g: list[list[str]] = []
        for y in range(72, 112):
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

    # Clear MARIO area cleanly (x=48..134, y=70..113)
    _fill_rect(out, 48, 70, 134, 114, sign_bg)

    # Place B A R B A across x=49..133 matching BROS. exact pitch & baseline
    glyphs = [g_B, g_A, g_R, g_B, g_A]
    cur_x = 49
    for g in glyphs:
        gw = len(g[0])
        for dy, row in enumerate(g):
            for dx, ch in enumerate(row):
                if ch == 'P':
                    out[72 + dy][cur_x + dx] = peach
                elif ch == 'S':
                    out[72 + dy][cur_x + dx] = shadow
        cur_x += gw + 1
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

    # Chiseled ZELDA-style 9x12 glyphs (bold slab serifs, beveled corners)
    z_glyphs = {
        'B': [
            '111111100',
            '011000110',
            '011000110',
            '011000110',
            '011111100',
            '011000110',
            '011000110',
            '011000110',
            '011000110',
            '111111110',
        ],
        'A': [
            '001111100',
            '011000110',
            '011000110',
            '110000011',
            '110000011',
            '111111111',
            '110000011',
            '110000011',
            '110000011',
            '111000111',
        ],
        'R': [
            '111111100',
            '011000110',
            '011000110',
            '011000110',
            '011111100',
            '011011000',
            '011001100',
            '011000110',
            '011000110',
            '111000111',
        ],
    }
    # Scale 2.8x -> 24px wide x 28px tall (matches ZELDA height y=64..91)
    scale_x, scale_y = 3, 2.8
    word = 'BARBA'
    start_x, start_y = 56, 64
    face = [[False] * 256 for _ in range(240)]
    for idx, ch in enumerate(word):
        g = z_glyphs[ch]
        bx = start_x + idx * 29
        for gy, row in enumerate(g):
            for gx, bit in enumerate(row):
                if bit == '1':
                    y0 = int(start_y + gy * scale_y)
                    y1 = int(start_y + (gy + 1) * scale_y)
                    for py in range(y0, y1):
                        for px_off in range(scale_x):
                            px_x = bx + gx * scale_x + px_off
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
    # Clear FORTUNE (x=128..224, y=63..89), keeping PRESENTS above (y<=62) and ® at x>=225
    _fill_rect(out, 128, 63, 224, 90, (0, 0, 0))
    # Clear BARBA EDITION subtitle below if we're unifying to WHEEL OF BARBA
    _fill_rect(out, 60, 92, 200, 104, (0, 0, 0))

    pink = (254, 110, 204)
    white = (255, 255, 255)
    # Tall condensed 5x9 glyphs scaled 2x wide x 2.5x tall (~10x22px, matching WHEEL)
    glyphs = {
        'B': ['11110', '10001', '10001', '11110', '10001', '10001', '10001', '11110'],
        'A': ['01110', '10001', '10001', '11111', '10001', '10001', '10001', '10001'],
        'R': ['11110', '10001', '10001', '11110', '10100', '10010', '10001', '10001'],
    }
    face = [[False] * 256 for _ in range(240)]
    for idx, ch in enumerate('BARBA'):
        g = glyphs[ch]
        bx = 132 + idx * 17
        for gy, row in enumerate(g):
            for gx, bit in enumerate(row):
                if bit == '1':
                    for sy in range(3):
                        py = 63 + gy * 3 + sy
                        for sx in range(3):
                            px_x = bx + gx * 3 + sx
                            if px_x < 222 and py < 88:
                                face[py][px_x] = True
    # 1px white outline around face, then pink fill
    for y in range(61, 90):
        for x in range(130, 224):
            if face[y][x]:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if not face[y + dy][x + dx]:
                            out[y + dy][x + dx] = white
    for y in range(61, 90):
        for x in range(130, 224):
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

    # Erase FORTUNE pixels along the bottom arc (radius 34..60 around center (128, 108), y >= 110)
    # Preserve blue/purple stars (where b > r + 20) and preserve the inner orange/grey wheel ring (r < 34)
    cx, cy = 128.0, 108.0
    for y in range(110, 174):
        for x in range(56, 200):
            dist = math.hypot(x - cx, y - cy)
            if 34.5 <= dist <= 61.0:
                r, g, b = out[y][x]
                if b > r + 20:  # keep purple/blue perimeter stars
                    continue
                out[y][x] = (0, 0, 0)

    # Polar-map 'BARBA' onto the bottom arc: theta from 142 deg (left) to 38 deg (right)
    # In screen coords (y down): sin(theta) > 0 is bottom!
    glyphs = {
        'B': ['11110', '10001', '10001', '11110', '10001', '10001', '10001', '11110'],
        'A': ['01110', '10001', '10001', '11111', '10001', '10001', '10001', '10001'],
        'R': ['11110', '10001', '10001', '11110', '10100', '10010', '10001', '10001'],
    }
    face = [[False] * 256 for _ in range(240)]
    word = 'BARBA'
    # Each letter spans ~18 deg with 3 deg gap -> total ~102 deg centered at 90 deg (bottom)
    for y in range(115, 174):
        for x in range(56, 200):
            dx, dy = x - cx, y - cy
            dist = math.hypot(dx, dy)
            if 36.0 <= dist <= 58.0:
                ang = math.degrees(math.atan2(dy, dx))  # 90 is straight down, 180 is left, 0 is right
                # Map ang from [142 .. 38] -> u in [0 .. 5]
                u = (142.0 - ang) / 21.0
                idx = int(math.floor(u))
                if 0 <= idx < 5:
                    lu = u - idx
                    if 0.08 <= lu <= 0.90:
                        gx = int((lu - 0.08) / 0.82 * 5)
                        gy = int((dist - 36.0) / 22.0 * 8)
                        if 0 <= gx < 5 and 0 <= gy < 8:
                            if glyphs[word[idx]][gy][gx] == '1':
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

    # Also update bottom marquee 'PRESENTS - WHEEL • of • BARBA'
    _fill_rect(out, 100, 212, 230, 234, (0, 0, 0))
    _draw_block_text(out, 'WHEEL OF BARBA', 102, 217, orange, scale=1)
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
    sky_grey = fixed_base[124][218]
    barba_pal = {'1': NES_RGB[0x16], '2': NES_RGB[0x27], '3': NES_RGB[0x30]}

    # Candidate A: Full-Body Barba (32x40 with junction and tail) on rooftop
    cand_a = _copy_px(fixed_base)
    _fill_rect(cand_a, 198, 118, 224, 144, sky_grey)
    _, _, _, poses = mm2_art.compile_barba_gameplay(z2_bytes)
    _draw_grid(cand_a, poses['idle'], 194, 108, barba_pal, scale=1)

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


def generate_all() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
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
    _draw_f13_brush_text(f13_a, 'CAMP BARBA', 60, 128, barba_stripes, NES_RGB[0x06], scale=2)
    write_png(OUT_DIR / 'f13_cand_a.png', f13_a)

    # Alternate striping rhythm (gold/crimson alternating bands)
    alt_stripes = [
        NES_RGB[0x27], NES_RGB[0x27], NES_RGB[0x16], NES_RGB[0x16],
        NES_RGB[0x30], NES_RGB[0x27], NES_RGB[0x16], NES_RGB[0x16],
        NES_RGB[0x27], NES_RGB[0x16],
    ]
    f13_b = _copy_px(f13_base)
    _draw_grid(f13_b, barba_frames['idle'], 6, 70, barba_pal, scale=2)
    _draw_f13_brush_text(f13_b, 'CAMP BARBA', 60, 128, alt_stripes, NES_RGB[0x06], scale=2)
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
    # Match MIKE TYSON bold centered positioning (above LINK IS WAITING at y=176)
    _fill_rect(mtpo_a, 88, 138, 168, 174, (0, 0, 0))
    _draw_block_text(mtpo_a, 'EVIL', 106, 138, NES_RGB[0x27], scale=2)
    _draw_block_text(mtpo_a, 'LINK', 106, 156, NES_RGB[0x27], scale=2)
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
    for y in range(180, 240):
        for x in range(72, 120):
            r, g, b = zelda_b[y][x]
            # Keep vanilla bright white foam/highlights untouched!
            if r > 220 and g > 220 and b > 220:
                continue
            # Recolor mint/cyan water body into flowing Palace VI crimson/amber lava
            if g > 140 and b > 140:
                zelda_b[y][x] = NES_RGB[0x27] if ((y // 4 + x // 8) % 3 == 0) else NES_RGB[0x16]
    write_png(OUT_DIR / 'zelda_cand_b.png', zelda_b)

    catalog = {
        'done_games': [
            {'id': 'dk', 'name': 'Barba Kong', 'note': 'Title screen & arcade cabinet done.'},
            {'id': 'duck', 'name': "Barba's Hunt", 'note': 'Title screen & forest sprites done.'},
            {'id': 'feud', 'name': "Barba's Beef", 'note': 'Title, cast & ordinal rounds done.'},
            {'id': 'waldo', 'name': "Where's Barba?", 'note': 'Title screen & crowd tagger done.'},
        ],
        'jason_mask_lab': [
            {
                'id': 'jmask_lab',
                'name': 'Jason Mask Lab (Friday the 13th Intro)',
                'status': 'prototype',
                'status_label': 'Dedicated Mask R&D',
                'summary': 'Fitting a round human hockey mask onto Barba’s elongated 32x16 dragon head & snout.',
                'context_note': '4 mask geometry studies at 4x scale (white mask + crimson chevrons on Barba’s head).',
                'current': [
                    {'id': 'f13_cur_mask', 'label': 'Vanilla Intro Mask (Frame 120)', 'img': 'previews/titles/f13_current_mask.png', 'caption': 'Vanilla blue Jason hockey mask'},
                ],
                'candidates': jmask_cands,
            },
        ],
        'games': [
            {
                'id': 'f13',
                'name': 'Friday the 13th: Camp Barba',
                'status': 'prototype',
                'status_label': 'CAMP BARBA + Left Barba',
                'summary': 'Folded Candidate B’s left-side Barba (now in vanilla Barba colors) with CAMP BARBA in the jagged F13 brush font striped with Barba’s torso/head palette. Jason mask moved to its own Jason Mask Lab tab.',
                'context_note': 'F13 uses 4KB CHR bank 7 for the blood-red logo ($C0..$FE) and sprite palettes for Barba.',
                'current': [
                    {'id': 'f13_cur_title', 'label': 'Current Title (Frame 420)', 'img': 'previews/titles/f13_current_title.png', 'caption': 'Vanilla FRIDAY THE 13TH logo'},
                ],
                'candidates': [
                    {
                        'id': 'f13_cand_a',
                        'label': 'Candidate A: Attack Barba + Striped CAMP BARBA',
                        'img': 'previews/titles/f13_cand_a.png',
                        'caption': 'Left-side Barba in vanilla colors + CAMP BARBA in F13 brush font with Barba torso/head striping.',
                    },
                    {
                        'id': 'f13_cand_b',
                        'label': 'Candidate B: Idle Barba + Gold-Band CAMP BARBA',
                        'img': 'previews/titles/f13_cand_b.png',
                        'caption': 'Idle Barba pose + alternate gold/crimson Barba palette striping on CAMP BARBA.',
                    },
                ],
            },
            {
                'id': 'smb',
                'name': 'Super Barba Bros.',
                'status': 'fixed_needs_title',
                'status_label': 'Ready for SUPER BARBA BROS. Sign',
                'summary': 'BARBA now matches the exact condensed beveled font & style of BROS. Demo mode keeps tiny Wyrmling (it grows on mushroom/jar pickup). Note: the "10" + tile above Barba in the roar shot is SMB’s "1000" floating score popup on the first grow-toggle frame.',
                'context_note': 'B, R, and A glyphs sampled directly from BROS. / MARIO on the wooden title sign.',
                'current': [
                    {'id': 'smb_cur_title', 'label': 'Current Title (Demo Wyrmling)', 'img': 'previews/titles/smb_current_title.png', 'caption': 'Still says SUPER MARIO BROS.'},
                    {'id': 'smb_fix_roar', 'label': 'Mushroom Roar Frame (1000 popup)', 'img': 'previews/titles/smb_fixed_roar.png', 'caption': 'Roaring on first grow frame ("10" is the 1000 score popup)'},
                    {'id': 'smb_fix_big', 'label': 'Full-Body Super Barba', 'img': 'previews/titles/smb_fixed_big.png', 'caption': 'Crisp 24x32 + trail Super Barba'},
                ],
                'candidates': [
                    {
                        'id': 'smb_cand_a',
                        'label': 'Candidate A: SUPER BARBA BROS. Sign',
                        'img': 'previews/titles/smb_cand_a.png',
                        'caption': 'BARBA matched pixel-for-pixel to BROS. font, bevels, and 3D drop shadow; keeps tiny Barba in demo mode.',
                    },
                ],
            },
            {
                'id': 'mtpo',
                'name': "Barba's Punch-Out!!",
                'status': 'needs_rework',
                'status_label': 'Needs Rework (Z2 Game Over Link)',
                'summary': 'Rebuilt Link portrait from Zelda 2’s Game Over Link silhouette + EVIL LINK matching MIKE TYSON positioning.',
                'context_note': 'Uses game_over_art.compile_game_over_link() 80x96 silhouette inside the Title2 portrait frame.',
                'current': [
                    {'id': 'mtpo_cur_t2', 'label': 'Current Title2 (Evil Link)', 'img': 'previews/titles/mtpo_current_title2.png', 'caption': 'Rough Link portrait & blocky font'},
                    {'id': 'mtpo_zoom', 'label': 'Context: Current Link Portrait (2x)', 'img': 'previews/titles/mtpo_link_zoom.png', 'caption': 'Flat green silhouette needs Z2 Game Over detail'},
                ],
                'candidates': [
                    {
                        'id': 'mtpo_cand_a',
                        'label': 'Candidate A: Z2 Game Over Link Silhouette + EVIL LINK',
                        'img': 'previews/titles/mtpo_cand_a.png',
                        'caption': 'Looming Z2 Game Over Link silhouette + EVIL LINK centered in MIKE TYSON position.',
                    },
                ],
            },
            {
                'id': 'mm2',
                'name': 'Mega Barba 2 (Barba Man 2)',
                'status': 'discussion',
                'status_label': 'Fixed Clipped A + 2 Rooftop Directions',
                'summary': 'Fixed the missing top-right corner of the trailing A in MEGA BARBA II (tools/mm2_art.py). Two rooftop character directions below for iteration: full-body Barba with junction/tail vs Mega Man with Barba snout sticking out of the helmet.',
                'context_note': 'Logo fix is already applied in tools/mm2_art.py; zoom below previews the unclipped A.',
                'current': [
                    {'id': 'mm2_cur', 'label': 'Current ROM Title (Clipped A)', 'img': 'previews/titles/mm2_current_title.png', 'caption': 'Pre-fix capture (trailing A top-right clipped)'},
                    {'id': 'mm2_zoom', 'label': 'Fixed Logo Zoom (Unclipped A)', 'img': 'previews/titles/mm2_logo_zoom.png', 'caption': 'Fixed in mm2_art.py: trailing A + shadow fully inside nametable span'},
                ],
                'candidates': [
                    {
                        'id': 'mm2_cand_a',
                        'label': 'Candidate A: Full-Body Barba (Junction + Tail)',
                        'img': 'previews/titles/mm2_cand_a.png',
                        'caption': '32x40 full-body Barba with neck junction and tail on the skyscraper rooftop.',
                    },
                    {
                        'id': 'mm2_cand_b',
                        'label': 'Candidate B: Mega Man Helmet + Barba Snout',
                        'img': 'previews/titles/mm2_cand_b.png',
                        'caption': 'Mega Man armor & blue helmet with Barba’s dragon snout poking out.',
                    },
                ],
            },
            {
                'id': 'wheel',
                'name': 'Wheel of Barba',
                'status': 'align',
                'status_label': 'Aligned: WHEEL OF BARBA',
                'summary': 'Replaces FORTUNE with BARBA on both Screen 1 and the Screen 2 bottom wheel arc, preserving the exact fonts, colors, and curved wheel geometry.',
                'context_note': 'Screen 1 keeps pink/white-outlined WHEEL • of • BARBA; Screen 2 curves BARBA along the bottom arc in grey/orange.',
                'current': [
                    {'id': 'wheel_cur_s1', 'label': 'Current Screen 1 (Splash)', 'img': 'previews/titles/wheel_current_s1.png', 'caption': 'WHEEL of FORTUNE / BARBA EDITION'},
                    {'id': 'wheel_cur_s2', 'label': 'Current Screen 2 (Big Wheel)', 'img': 'previews/titles/wheel_current_s2.png', 'caption': 'Still says FAMILY EDITION + WHEEL OF FORTUNE'},
                ],
                'candidates': [
                    {
                        'id': 'wheel_cand_s1',
                        'label': 'Candidate Screen 1: WHEEL • of • BARBA',
                        'img': 'previews/titles/wheel_cand_s1.png',
                        'caption': 'Replaces FORTUNE with BARBA in the exact pink/white-outline font.',
                    },
                    {
                        'id': 'wheel_cand_s2',
                        'label': 'Candidate Screen 2: Curved Bottom-Arc BARBA',
                        'img': 'previews/titles/wheel_cand_s2.png',
                        'caption': 'Replaces bottom-arc FORTUNE with curved BARBA in grey + orange outline + shadow.',
                    },
                ],
            },
            {
                'id': 'zelda',
                'name': 'The Legend of Barba (Zelda 1)',
                'status': 'not_started',
                'status_label': 'ZELDA-Matched Font + White-Foam Lava',
                'summary': 'BARBA now matches ZELDA’s chiseled serif font, warm brown fill, and 3D black shadow. Candidate B preserves the vanilla waterfall’s bright white foam highlights inside the flowing lava.',
                'context_note': 'Zelda 1 uses CHR-RAM; title tiles and waterfall palette patch cleanly in pack_zelda.py.',
                'current': [
                    {'id': 'zelda_cur', 'label': 'Current Title (Vanilla Z1)', 'img': 'previews/titles/zelda_current_title.png', 'caption': 'Unmodified THE LEGEND OF ZELDA'},
                ],
                'candidates': [
                    {
                        'id': 'zelda_cand_a',
                        'label': 'Candidate A: THE LEGEND OF BARBA (ZELDA Font)',
                        'img': 'previews/titles/zelda_cand_a.png',
                        'caption': 'Chiseled brown+black BARBA matching ZELDA’s look & feel.',
                    },
                    {
                        'id': 'zelda_cand_b',
                        'label': 'Candidate B: Lava Falls (With White Foam)',
                        'img': 'previews/titles/zelda_cand_b.png',
                        'caption': 'Flowing Palace VI crimson/amber lava keeping the vanilla waterfall’s white foam.',
                    },
                ],
            },
        ],
    }

    DATA_JS.write_text('window.TITLE_REVIEW_DATA = ' + json.dumps(catalog, indent=2) + ';\n', encoding='utf-8')
    print(f'Generated title review assets in {OUT_DIR} and {DATA_JS}')
    return catalog


if __name__ == '__main__':
    generate_all()
