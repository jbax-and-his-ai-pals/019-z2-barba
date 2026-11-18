"""Build the Barba-as-Waldo ROM hack (`build/waldo_barba.nes`) from `roms/waldo.nes`."""
from __future__ import annotations

import json
import math
import zlib
from pathlib import Path

from boss_art import source_head, source_pair
from nes import CHR_OFFSET, HEADER_SIZE, decode_tile, encode_tile, load_source

ROOT = Path(__file__).resolve().parents[1]
WALDO_PATH = ROOT / 'roms/waldo.nes'
Z2_PATH = ROOT / 'roms/z2.nes'
OUT_PATH = ROOT / 'build/waldo_barba.nes'
PLAY_PATH = ROOT / 'play/wheres-barba.nes'
BARBA_JSON = ROOT / 'assets/barba.json'

WALDO_CRC32 = 0xC3463A3D
WALDO_CHR_OFFSET = HEADER_SIZE + 0x20000


def put(buf: bytearray, offset: int, new: bytes, expected: bytes | None = None) -> None:
    if expected is not None and bytes(buf[offset:offset + len(expected)]) != expected:
        raise ValueError(f'Unexpected bytes at 0x{offset:06X}')
    buf[offset:offset + len(new)] = new


def put_chr_tile(buf: bytearray, bank_4k: int, tile_idx: int, rows: list[str]) -> None:
    off = WALDO_CHR_OFFSET + bank_4k * 4096 + tile_idx * 16
    buf[off:off + 16] = encode_tile(rows)


def remap_rows(rows: list[str], mapping: dict[str, str]) -> list[str]:
    return [''.join(mapping[c] for c in r) for r in rows]


def put_grid(buf: bytearray, bank_4k: int, base_tile: int, rows: list[str], cols: int, tile_rows: int) -> None:
    """Write a (cols*8) x (tile_rows*8) pixel grid into consecutive CHR tiles row-major."""
    for tr in range(tile_rows):
        for tc in range(cols):
            sub = [rows[tr * 8 + y][tc * 8:(tc + 1) * 8] for y in range(8)]
            put_chr_tile(buf, bank_4k, base_tile + tr * cols + tc, sub)


def build() -> None:
    if not WALDO_PATH.is_file():
        raise SystemExit('Missing roms/waldo.nes')
    waldo = WALDO_PATH.read_bytes()
    if waldo[:7] != b'NES\x1a\x08\x10\x40' or (zlib.crc32(waldo[16:]) & 0xFFFFFFFF) != WALDO_CRC32:
        raise SystemExit('Unexpected roms/waldo.nes')

    barba = json.loads(BARBA_JSON.read_text(encoding='utf-8'))
    z2 = load_source(Z2_PATH)  # verified source ROM for boss-derived art

    out = bytearray(waldo)

    # 1. Skill Select 16x16 cursor (Bank 2, tiles $C4-$C7).
    # Skill Select Sprite Pal 0 = [20(bg), 0E(black), 16(red), 38(pale yellow)]
    # barba.json["front"]: 0=trans, 1=red, 2=gold, 3=black/ivory
    front = remap_rows(barba['front'], {'0': '0', '1': '2', '2': '3', '3': '1'})
    put_grid(out, bank_4k=2, base_tile=0xC4, rows=front, cols=2, tile_rows=2)

    # 2. Overworld Map 16x32 walking Barba (Bank 2, 12 slots at $00, $08, ..., $58).
    # Patch Map Sprite Pal 0 & Pal 1 to [0E, 16(red), 27(gold), 38(ivory)]
    put(out, HEADER_SIZE + 0x1E801, bytes([0x16, 0x27, 0x38]), expected=bytes([0x16, 0x20, 0x38]))
    put(out, HEADER_SIZE + 0x1E805, bytes([0x16, 0x27, 0x38]), expected=bytes([0x16, 0x22, 0x20]))

    # barba.json["body"] is 16x32 facing right; flip horizontally so CHR faces left (attr=$40 flips right).
    body_left = [r[::-1] for r in barba['body']]
    # Shift alternate walk frames by 1px vertically for a subtle slither/bob.
    body_bob = body_left[1:] + ['0' * 16]
    for slot in range(12):
        pose = body_bob if (slot % 2 == 1) else body_left
        put_grid(out, bank_4k=2, base_tile=slot * 8, rows=pose, cols=2, tile_rows=4)

    # 3. Title Screen Stamp Portrait (Bank 13).
    # Patch Title BG Pal 3 color 3 ($26 peach -> $16 red) so Barba has white(0), blue(1), black(2), red(3).
    put(out, HEADER_SIZE + 0x1E88F, bytes([0x16]), expected=bytes([0x26]))
    stamp_tiles = [
        [0x06, 0x07, 0x08, 0x09, 0x0A, None],
        [0x0F, 0x10, 0x11, 0x12, 0x13, None],
        [0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F],
        [0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B],
        [0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C],
        [0x4C, 0x4D, 0x4E, 0x4F, 0x50, 0x51],
    ]
    # Decode 48x48 grid (rows 3..8, cols 21..26 of nametable)
    grid = [[0] * 48 for _ in range(48)]
    for tr, row in enumerate(stamp_tiles):
        for tc, tid in enumerate(row):
            if tid is None:
                continue
            off = WALDO_CHR_OFFSET + 13 * 4096 + tid * 16
            d = decode_tile(bytes(out[off:off + 16]))
            for y in range(8):
                for x in range(8):
                    grid[tr * 8 + y][tc * 8 + x] = d[y][x]

    # Clear interior of rotated stamp box to 1 (blue) while preserving border (0/2) and postmark (x < 17)
    for y in range(6, 44):
        x_min = 17 + int((y - 6) * 0.22)
        x_max = 35 + int((y - 6) * 0.22)
        for x in range(x_min, min(46, x_max)):
            if y >= 11 - int((x - 17) * 0.22) and y <= 43 - int((x - 17) * 0.22):
                grid[y][x] = 1

    # Blit Barba's open-jaw head (32x16) + 12px neck inside the stamp
    head = source_head(z2, 'open')
    neck = [''.join((source_pair(z2, 0xA0)[y], source_pair(z2, 0xA2)[y])) for y in range(16)]
    # Map Z2 colors (1=red, 2=gold, 3=ivory) -> stamp colors (2=black, 3=red, 0=white)
    cmap = {'1': '2', '2': '3', '3': '0'}
    ox, oy = 17, 18
    for y in range(12):
        for x in range(16):
            p = neck[y][x]
            if p != '0' and 0 <= oy + 14 + y < 48 and 0 <= ox + 12 + x < 48:
                grid[oy + 14 + y][ox + 12 + x] = int(cmap[p])
    for y in range(16):
        for x in range(32):
            p = head[y][x]
            if p != '0' and 0 <= oy + y < 48 and 0 <= ox + x < 48:
                grid[oy + y][ox + x] = int(cmap[p])

    for tr, row in enumerate(stamp_tiles):
        for tc, tid in enumerate(row):
            if tid is None:
                continue
            sub = [''.join(str(grid[tr * 8 + y][tc * 8 + x]) for x in range(8)) for y in range(8)]
            put_chr_tile(out, 13, tid, sub)

    # 4. "One Ticket to the Moon" Peeking Head (Bank 15).
    # Palette on Ticket screen top: 0=white, 1=red, 2=black, 3=pale yellow.
    # Nametable rows 6..11, cols 12..19 (8x6 tiles = 64x48 px):
    ticket_tiles = [
        [0x24, 0x25, 0x26, 0x27, 0x28, 0x29, None, None],
        [0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, None],
        [0x3C, 0x3D, 0x3E, 0x3F, 0x40, 0x41, 0x42, 0x43],
        [0x4E, 0x4F, 0x50, 0x51, 0x52, 0x53, 0x54, 0x55],
        [0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69],
        [0x77, 0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E],
    ]
    tgrid = [[0] * 64 for _ in range(48)]
    for tr, row in enumerate(ticket_tiles):
        for tc, tid in enumerate(row):
            if tid is None:
                continue
            off = WALDO_CHR_OFFSET + 15 * 4096 + tid * 16
            d = decode_tile(bytes(out[off:off + 16]))
            for y in range(8):
                for x in range(8):
                    # Preserve dithered horizon in r09..r11 outer cols (tc==0 or tc==7) where sky/dots are
                    if tr >= 3 and (tc == 0 or tc == 7) and d[y][x] in (0, 3):
                        tgrid[tr * 8 + y][tc * 8 + x] = d[y][x]
                    if tr == 5 and y >= 6:
                        tgrid[tr * 8 + y][tc * 8 + x] = d[y][x]

    # Scale source_head(z2, 'open') 2x -> 64x32 at y=2, plus 2x neck below it (y=30..45)
    tcmap = {'1': 1, '2': 3, '3': 0}
    for y in range(12):
        for x in range(16):
            p = neck[y][x]
            if p != '0':
                val = tcmap[p]
                for sy in range(2):
                    for sx in range(2):
                        yy, xx = 28 + y * 2 + sy, 24 + x * 2 + sx
                        if yy < 46 and xx < 64:
                            tgrid[yy][xx] = val
    for y in range(16):
        for x in range(32):
            p = head[y][x]
            if p == '0':
                n_nz = sum(
                    1 for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
                    if 0 <= y + dy < 16 and 0 <= x + dx < 32 and head[y + dy][x + dx] != '0'
                )
                val = 2 if n_nz >= 3 else None
            else:
                val = tcmap[p]
            if val is not None:
                for sy in range(2):
                    for sx in range(2):
                        yy, xx = 2 + y * 2 + sy, x * 2 + sx
                        if yy < 46:
                            tgrid[yy][xx] = val

    for tr, row in enumerate(ticket_tiles):
        for tc, tid in enumerate(row):
            if tid is None:
                continue
            sub = [''.join(str(tgrid[tr * 8 + y][tc * 8 + x]) for x in range(8)) for y in range(8)]
            put_chr_tile(out, 15, tid, sub)

    # 5. Train Station hidden Waldo (Bank 19, tiles $95, $96 / $97, $98, 16x16).
    small = remap_rows(barba['small'], {'0': '0', '1': '1', '2': '2', '3': '3'})
    for tr, row_ids in enumerate(([0x95, 0x96], [0x97, 0x98])):
        for tc, tid in enumerate(row_ids):
            sub = [small[tr * 8 + y][tc * 8:(tc + 1) * 8] for y in range(8)]
            put_chr_tile(out, 19, tid, sub)

    # 6. Title Screen "WALDO?" -> "BARBA?" (Bank 14, r16..r25, c6..c28).
    # Note: 0x00 (blank) and 0x1E (left postcard border) are skipped when writing back.
    title_b14_nt = [
        [0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F,0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18,0x19],
        [0x1E,0x1F,0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x29,0x2A,0x2B,0x00,0x00,0x2C,0x2D,0x2E,0x2F,0x30,0x31,0x32],
        [0x36,0x37,0x38,0x39,0x3A,0x3B,0x3C,0x3D,0x3E,0x3F,0x40,0x41,0x1E,0x42,0x43,0x44,0x45,0x46,0x47,0x48,0x49,0x4A,0x4B],
        [0x4F,0x50,0x51,0x52,0x53,0x54,0x55,0x56,0x00,0x00,0x57,0x58,0x59,0x5A,0x5B,0x5C,0x5D,0x5E,0x5F,0x60,0x61,0x62,0x63],
        [0x67,0x00,0x68,0x69,0x6A,0x6B,0x00,0x00,0x6C,0x6D,0x6E,0x6F,0x70,0x71,0x72,0x73,0x74,0x75,0x76,0x77,0x00,0x78,0x79],
        [0x7D,0x00,0x7E,0x7F,0x00,0x80,0x81,0x82,0x83,0x84,0x85,0x86,0x87,0x88,0x89,0x8A,0x8B,0x8C,0x8D,0x8E,0x8F,0x90,0x91],
        [0x94,0x00,0x00,0x95,0x96,0x97,0x98,0x99,0x9A,0x9B,0x9C,0x9D,0x9E,0x9F,0xA0,0xA1,0xA2,0xA3,0xA4,0xA5,0xA6,0xA7,0x00],
        [0xA8,0xA9,0x00,0xAA,0xAB,0xAC,0xAD,0xAE,0xAF,0xB0,0xB1,0xB2,0xB3,0xB4,0xB5,0xB6,0xB7,0xB8,0xB9,0x00,0x00,0x00,0x00],
        [0xBA,0xBB,0x00,0xBC,0xBD,0xBE,0xBF,0xC0,0xC1,0xC2,0xC3,0xC4,0xC5,0xC6,0xC7,0xC8,0xC9,0x00,0x00,0x00,0x00,0x00,0x00],
        [0xCA,0xCB,0x00,0x00,0xCC,0xCD,0xCE,0xCF,0xD0,0xD1,0xD2,0xD3,0xD4,0xD5,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    ]
    W14, H14 = 23 * 8, 10 * 8
    g14 = [[0] * W14 for _ in range(H14)]
    for tr, row in enumerate(title_b14_nt):
        for tc, tid in enumerate(row):
            if tid == 0:
                continue
            off = WALDO_CHR_OFFSET + 14 * 4096 + tid * 16
            d = decode_tile(bytes(out[off:off + 16]))
            for y in range(8):
                for x in range(8):
                    g14[tr * 8 + y][tc * 8 + x] = d[y][x]

    # Define bold 5x7 glyphs for B, A, R matching the postcard style
    glyphs = {
        'B': [
            '11110',
            '10001',
            '10001',
            '11110',
            '10001',
            '10001',
            '11110',
        ],
        'A': [
            '00100',
            '01110',
            '01010',
            '10001',
            '11111',
            '10001',
            '10001',
        ],
        'R': [
            '11110',
            '10001',
            '10001',
            '11110',
            '10100',
            '10010',
            '10001',
        ],
    }
    # Render "BARBA" into a high-res rotated mask over the WALDO strip
    # Postcard tilt: -20.5 deg; origin at top-left of first 'B'
    ang = math.radians(-20.5)
    ca, sa = math.cos(ang), math.sin(ang)
    x0, y0 = 31.0, 47.0

    def in_word(u: float, v: float) -> bool:
        if v < 0 or v >= 28.0 or u < 0:
            return False
        idx = int(u // 24.0)
        if idx < 0 or idx >= 5:
            return False
        lu = u - idx * 24.0
        if lu >= 19.0:
            return False
        ch = 'BARBA'[idx]
        gx = min(4, int(lu / 3.8))
        gy = min(6, int(v / 4.0))
        return glyphs[ch][gy][gx] == '1'

    def to_uv(px: float, py: float) -> tuple[float, float]:
        dx, dy = px - x0, py - y0
        return (dx * ca + dy * sa, -dx * sa + dy * ca)

    # Clear WALDO strip (inside red-palette region, strictly above the bottom postcard border and left of '?')
    for y in range(H14):
        for x in range(W14):
            if x >= 161 or (x >= 158 and y < 14) or y >= 99.0 - 0.37 * x:
                continue
            u, v = to_uv(x, y)
            if -12.0 <= u <= 148.0 and -4.0 <= v <= 48.0:
                g14[y][x] = 0

    # Draw shadow (2), outline (3), and red fill (1)
    for y in range(H14):
        for x in range(W14):
            if x >= 159 or y >= 95.0 - 0.37 * x:
                continue
            u, v = to_uv(x, y)
            if not (-4.0 <= u <= 122.0 and -3.0 <= v <= 32.0):
                continue
            if in_word(u, v):
                g14[y][x] = 1
            elif any(in_word(*to_uv(x + dx, y + dy))
                     for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))):
                g14[y][x] = 3
            elif any(in_word(*to_uv(x + dx, y + dy))
                     for dx, dy in ((2, -2), (3, -2), (2, -3), (3, -3))):
                g14[y][x] = 2

    for tr, row in enumerate(title_b14_nt):
        for tc, tid in enumerate(row):
            if tid in (0, 0x1E):
                continue
            sub = [''.join(str(g14[tr * 8 + y][tc * 8 + x]) for x in range(8)) for y in range(8)]
            put_chr_tile(out, 14, tid, sub)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_bytes(out)
    PLAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAY_PATH.write_bytes(out)
    print(f'Wrote {OUT_PATH} and {PLAY_PATH} ({len(out)} bytes)')


if __name__ == '__main__':
    build()
