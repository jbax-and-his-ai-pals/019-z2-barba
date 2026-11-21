"""Build the Barba-as-Waldo ROM hack (`build/waldo_barba.nes`) from `roms/waldo.nes`."""
from __future__ import annotations

import json
import math
import zlib
from pathlib import Path

import roar_sample
from assets import compile_assets, encounter_connector_rows, encounter_trail_rows
from boss_art import resize_x, source_head, source_pair
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


def resize_xy(rows: list[str], width: int, height: int) -> list[str]:
    """Nearest-neighbor 2D resize."""
    old_h = len(rows)
    y_scaled = [rows[min(old_h - 1, (y * old_h + height // 2) // height)] for y in range(height)]
    return resize_x(y_scaled, width)


def put_grid(buf: bytearray, bank_4k: int, base_tile: int, rows: list[str], cols: int, tile_rows: int) -> None:
    """Write a (cols*8) x (tile_rows*8) pixel grid into consecutive CHR tiles row-major."""
    for tr in range(tile_rows):
        for tc in range(cols):
            sub = [rows[tr * 8 + y][tc * 8:(tc + 1) * 8] for y in range(8)]
            put_chr_tile(buf, bank_4k, base_tile + tr * cols + tc, sub)


def build() -> Path:
    if not WALDO_PATH.is_file():
        raise SystemExit('Missing roms/waldo.nes')
    waldo = WALDO_PATH.read_bytes()
    if waldo[:7] != b'NES\x1a\x08\x10\x40' or (zlib.crc32(waldo[16:]) & 0xFFFFFFFF) != WALDO_CRC32:
        raise SystemExit('Unexpected roms/waldo.nes')

    barba = json.loads(BARBA_JSON.read_text(encoding='utf-8'))
    z2 = load_source(Z2_PATH)  # verified source ROM for boss-derived art
    _, z2_graphics, _, _ = compile_assets(ROOT, Z2_PATH)
    elbow_16 = encounter_connector_rows(z2_graphics)  # 16x16 vertical-to-horizontal curve
    trail_32 = encounter_trail_rows(z2_graphics)      # 32x16 horizontal torso + tapered tail tip

    out = bytearray(waldo)

    # 1. Skill Select 16x16 cursor (Bank 2, tiles $C4-$C7 frame 0, $C8-$CB frame 1).
    # Skill Select Sprite Pal 0 = [20(bg), 0E(black), 16(red), 38(pale yellow)]
    # barba.json["wyrmling"] is 2x 8x16 frames using 0=trans, 1=black, 2=red, 3=pale yellow.
    for frame_idx, base_tile in enumerate((0xC4, 0xC8)):
        wyr_16 = ['0000' + r + '0000' for r in barba['wyrmling'][frame_idx]]
        put_grid(out, bank_4k=2, base_tile=base_tile, rows=wyr_16, cols=2, tile_rows=2)

    # Animate Skill Select cursor in Bank 3 ($ABB5 loop -> $BFDC SkillTick, $AC15 -> $BFEF SkillSetTile)
    put(out, HEADER_SIZE + 0x06BC1, bytes.fromhex('20 dc bf'), expected=bytes.fromhex('ee f3 03'))
    put(out, HEADER_SIZE + 0x06C15, bytes.fromhex('20 ef bf ea'), expected=bytes.fromhex('a9 84 85 22'))
    skill_anim_code = bytes.fromhex(
        'ee f3 03 ad f3 03 29 0f d0 08 68 68 ae 02 06 4c 01 ac 60 '  # $BFDC SkillTick
        'ad f3 03 29 10 4a 4a 18 69 84 85 22 60'                      # $BFEF SkillSetTile
    )
    put(out, HEADER_SIZE + 0x07FDC, skill_anim_code, expected=bytes(len(skill_anim_code)))

    # 2. Overworld Map 16x32 walking Barba (Bank 2, 12 slots at $00, $08, ..., $58).
    # Patch Map Sprite Pal 0 & Pal 1 to [0E, 16(red), 27(gold), 38(ivory)]
    put(out, HEADER_SIZE + 0x1E801, bytes([0x16, 0x27, 0x38]), expected=bytes([0x16, 0x20, 0x38]))
    put(out, HEADER_SIZE + 0x1E805, bytes([0x16, 0x27, 0x38]), expected=bytes([0x16, 0x22, 0x20]))

    # Build 48x48 LEFT-facing Barba from Z2 boss chunks (24x16 head + undulating neck + elbow + horizontal trail/tail).
    head_16 = resize_x(source_head(z2, 'closed'), 16)
    head_24 = resize_x(source_head(z2, 'closed'), 24)
    neck_raw = [''.join((source_pair(z2, 0xA0)[y], source_pair(z2, 0xA2)[y])) for y in range(16)]
    neck_12 = resize_x(neck_raw, 12)
    map_trail_24 = resize_x(trail_32, 24)

    def make_map_barba(phase: int) -> list[str]:
        canvas = [['0'] * 48 for _ in range(48)]
        head_y = 1 if (phase % 2 == 1) else 0
        tail_bob = -1 if (phase % 2 == 1) else 0
        for iy, row in enumerate(elbow_16):
            for ix, px in enumerate(row):
                if px != '0':
                    canvas[32 + iy][8 + ix] = px
        for iy, row in enumerate(map_trail_24):
            for ix, px in enumerate(row):
                if px != '0':
                    yy = 32 + iy + (tail_bob if ix >= 12 else 0)
                    if 0 <= yy < 48:
                        canvas[yy][24 + ix] = px
        for y in range(head_y + 14, 34):
            sway = (0, -1, 0, 1)[((y - head_y) // 4 + phase) % 4] if y < 30 else 0
            row = neck_raw[(y - head_y - 16) % 16]
            nx = 8 + sway
            for ix, px in enumerate(row):
                if px != '0' and 0 <= nx + ix < 48:
                    canvas[y][nx + ix] = px
        for iy, row in enumerate(head_24):
            for ix, px in enumerate(row):
                if px != '0' and 0 <= head_y + iy < 48:
                    canvas[head_y + iy][ix] = px
        return [''.join(r) for r in canvas]

    pose_a = make_map_barba(0)
    pose_b = make_map_barba(2)
    put_grid(out, bank_4k=2, base_tile=0x00, rows=pose_a, cols=6, tile_rows=6)
    put_grid(out, bank_4k=2, base_tile=0x24, rows=pose_b, cols=6, tile_rows=6)
    for tid in range(0x48, 0x60):
        put_chr_tile(out, 2, tid, ['0' * 8] * 8)

    # Extend Overworld Map sprite size from 2x4 to 6x6 (48x48, 36 sprites) in Bank 14.
    put(out, HEADER_SIZE + 0x1CA6B, bytes([0x06, 0x06]), expected=bytes([0x02, 0x04]))
    put(out, HEADER_SIZE + 0x1C49A, bytes([0xA2, 0x24]), expected=bytes([0xA2, 0x08]))
    put(out, HEADER_SIZE + 0x1C4AB, bytes([0xA2, 0x24]), expected=bytes([0xA2, 0x08]))

    # Replace the 24 overworld sprite descriptors ($8BA2..$8D51) with 4 shared 44-byte descriptors (6x6 tiles).
    desc_addrs = (0x8BD2, 0x8BFE, 0x8C2A, 0x8C56)
    left_a_tiles = list(range(0x00, 0x24))
    left_b_tiles = list(range(0x24, 0x48))
    right_a_tiles = [r * 6 + (5 - c) for r in range(6) for c in range(6)]
    right_b_tiles = [0x24 + r * 6 + (5 - c) for r in range(6) for c in range(6)]
    descs = bytes([
        0x06, 0x06, 0xBF, 0x00, 0x00, 0x00, 0x00, 0x00, *left_a_tiles,
        0x06, 0x06, 0xBF, 0x00, 0x00, 0x00, 0x00, 0x00, *left_b_tiles,
        0x06, 0x06, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00, *right_a_tiles,
        0x06, 0x06, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00, *right_b_tiles,
    ])
    ptrs = bytearray()
    for i in range(24):
        is_right = (8 <= i <= 15) or i in (18, 19, 22, 23)
        is_b = (i % 2 == 1)
        addr = desc_addrs[(2 if is_right else 0) + (1 if is_b else 0)]
        ptrs += bytes([addr & 0xFF, addr >> 8])
    put(out, HEADER_SIZE + 0x1CBA2, bytes(ptrs), expected=waldo[HEADER_SIZE + 0x1CBA2:HEADER_SIZE + 0x1CBD2])
    put(out, HEADER_SIZE + 0x1CBD2, descs, expected=waldo[HEADER_SIZE + 0x1CBD2:HEADER_SIZE + 0x1CBD2 + len(descs)])

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

    # Clear interior of rotated stamp box to 1 (blue) while preserving border (0/2) and postmark (x < 16)
    def in_stamp_box(x: int, y: int) -> bool:
        if y < 6 or y > 45:
            return False
        if x > 34 + int((y - 6) * 0.22):
            return False
        if y < 12 - int((x - 15) * 0.23) or y > 45 - int((x - 17) * 0.18):
            return False
        if x >= 16:
            return True
        # Clear Waldo's red hat / white face pixels inside the upper-left of the box without erasing the postmark
        return x >= 11 and y <= 17 and grid[y][x] in (0, 3)

    for y in range(48):
        for x in range(48):
            if in_stamp_box(x, y):
                grid[y][x] = 1

    # Blit Barba's open-jaw head (20x14) + curved neck + elbow + horizontal tail clipped inside the stamp
    head = source_head(z2, 'open')
    neck = neck_raw
    stamp_head = resize_xy(head, 20, 14)
    stamp_neck = resize_x(neck, 10)
    stamp_elbow = resize_xy(elbow_16, 10, 10)
    stamp_trail = resize_xy(trail_32, 14, 10)
    # Map Z2 colors (1=red, 2=gold, 3=ivory) -> stamp colors (2=black, 3=red, 0=white)
    cmap = {'1': '2', '2': '3', '3': '0'}
    ox, oy = 15, 13
    for y in range(10):
        for x in range(10):
            p = stamp_elbow[y][x]
            yy, xx = oy + 19 + y, ox + 7 + x
            if p != '0' and 0 <= yy < 48 and 0 <= xx < 48 and in_stamp_box(xx, yy):
                grid[yy][xx] = int(cmap[p])
    for y in range(10):
        for x in range(14):
            p = stamp_trail[y][x]
            yy, xx = oy + 19 + y, ox + 17 + x
            if p != '0' and 0 <= yy < 48 and 0 <= xx < 48 and in_stamp_box(xx, yy):
                grid[yy][xx] = int(cmap[p])
    for y in range(10):
        for x in range(10):
            p = stamp_neck[y][x]
            yy, xx = oy + 12 + y, ox + 7 + x
            if p != '0' and 0 <= yy < 48 and 0 <= xx < 48 and in_stamp_box(xx, yy):
                grid[yy][xx] = int(cmap[p])
    for y in range(14):
        for x in range(20):
            p = stamp_head[y][x]
            yy, xx = oy + y, ox + x
            if p != '0' and 0 <= yy < 48 and 0 <= xx < 48 and in_stamp_box(xx, yy):
                grid[yy][xx] = int(cmap[p])

    for tr, row in enumerate(stamp_tiles):
        for tc, tid in enumerate(row):
            if tid is None:
                continue
            sub = [''.join(str(grid[tr * 8 + y][tc * 8 + x]) for x in range(8)) for y in range(8)]
            put_chr_tile(out, 13, tid, sub)

    # 4. "One Ticket to the Moon" Peeking Head (Bank 15).
    # Palette on Ticket screen top: 0=white, 1=red, 2=black, 3=pale yellow.
    # Nametable rows 6..11, cols 12..19 (8x6 tiles = 64x48 px):
    # Patch blank sky tiles at (r6, c18..19) and (r7, c19) to empty CHR tiles $F6..$F8
    # so the right horn and back crest are not clipped, and clear Waldo's pom-pom ($1C/$1D).
    put(out, HEADER_SIZE + 0x071B6, bytes([0xF6, 0xF7]), expected=bytes([0x00, 0x00]))
    put(out, HEADER_SIZE + 0x071D7, bytes([0xF8]), expected=bytes([0x00]))
    for tid in (0x1C, 0x1D):
        put_chr_tile(out, 15, tid, ['0' * 8] * 8)

    ticket_tiles = [
        [0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0xF6, 0xF7],
        [0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0xF8],
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

    # Scale source_head(z2, 'open') 2x -> 64x32 at y=2, plus 2x neck below it (y=28..45)
    tcmap = {'1': 1, '2': 3, '3': 0}
    tbody = [[False] * 64 for _ in range(48)]
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
                            tbody[yy][xx] = True
    for y in range(16):
        for x in range(32):
            p = head[y][x]
            if p != '0':
                val = tcmap[p]
                for sy in range(2):
                    for sx in range(2):
                        yy, xx = 2 + y * 2 + sy, x * 2 + sx
                        if yy < 46:
                            tgrid[yy][xx] = val
                            tbody[yy][xx] = True
    # Taper 2x-scaled horn tips into curved points reaching yy=1 (outline at yy=0)
    for yy, xx in ((1, 42), (1, 43), (1, 54), (1, 55), (2, 55)):
        tbody[yy][xx] = True
        tgrid[yy][xx] = 0
    for yy, xx in ((2, 40), (2, 52)):
        tbody[yy][xx] = False

    # Add 1px black (2) outline around Barba so white highlights/teeth/horns stand out against the white sky
    for yy in range(46):
        for xx in range(64):
            if not tbody[yy][xx]:
                if any(
                    0 <= yy + dy < 46 and 0 <= xx + dx < 64 and tbody[yy + dy][xx + dx]
                    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
                ):
                    tgrid[yy][xx] = 2

    for tr, row in enumerate(ticket_tiles):
        for tc, tid in enumerate(row):
            if tid is None:
                continue
            sub = [''.join(str(tgrid[tr * 8 + y][tc * 8 + x]) for x in range(8)) for y in range(8)]
            put_chr_tile(out, 15, tid, sub)

    # 5. Hidden Barba across all 5 search levels (PRG banks 4-8, 3 scanline bands each).
    # Each level randomly picks one band (0..2) and one of n_waldo descriptors in that band's table
    # ($A008/$A00A/$A00C). Patch every Waldo descriptor in every band to 2x2 Barba (16x16) using
    # 4 tiles unused by that band's nametable and non-Waldo descriptors.
    small = remap_rows(barba['small'], {'0': '0', '1': '1', '2': '2', '3': '3'})
    level_bands = [
        # (prg_bank, tile_list_cpu_addr, [(chr_4k_bank, (t0, t1, t2, t3)), ...])
        (4, 0xBF80, [(17, (0xFC, 0xFD, 0xFE, 0xFF)), (18, (0xFC, 0xFD, 0xFE, 0xFF)), (19, (0xFC, 0xFD, 0xFE, 0xFF))]),
        (5, 0xBFF0, [(20, (0xFC, 0xFD, 0xFE, 0xFF)), (21, (0xFC, 0xFD, 0xFE, 0xFF)), (22, (0xFC, 0xFD, 0xFE, 0xFF))]),
        (6, 0xBF80, [(23, (0xFC, 0xFD, 0xFE, 0xFF)), (24, (0xFC, 0xFD, 0xFE, 0xFF)), (25, (0xFC, 0xFD, 0xFE, 0xFF))]),
        (7, 0xBF80, [(26, (0xFC, 0xFD, 0xFE, 0xFF)), (27, (0xFC, 0xFD, 0xFE, 0xFF)), (28, (0x3E, 0x3F, 0x40, 0x41))]),
        (8, 0xBF80, [(29, (0xFC, 0xFD, 0xFE, 0xFF)), (30, (0xFC, 0xFD, 0xFE, 0xFF)), (31, (0xFC, 0xFD, 0xFE, 0xFF))]),
    ]
    for prg_bank, base_cpu, bands in level_bands:
        bank_off = HEADER_SIZE + prg_bank * 0x2000
        written_lists: dict[tuple[int, int, int, int], int] = {}
        next_cpu = base_cpu
        for band_idx, (b4k, tiles) in enumerate(bands):
            if tiles not in written_lists:
                put(out, bank_off + (next_cpu - 0xA000), bytes(tiles), expected=bytes(4))
                written_lists[tiles] = next_cpu
                next_cpu += 4
            list_cpu = written_lists[tiles]
            desc_ptr = int.from_bytes(out[bank_off + 8 + band_idx * 2 : bank_off + 10 + band_idx * 2], 'little')
            desc_off = bank_off + (desc_ptr - 0xA000)
            n_waldo = out[desc_off]
            for k in range(n_waldo):
                entry_off = desc_off + 2 + k * 6
                assert out[entry_off + 5] == 0x80, f'Bank {prg_bank} band {band_idx} desc[{k}] missing $80 flag'
                put(out, entry_off, bytes([0x02, 0x02, list_cpu & 0xFF, list_cpu >> 8]))
            for tr, row_ids in enumerate((tiles[:2], tiles[2:])):
                for tc, tid in enumerate(row_ids):
                    sub = [small[tr * 8 + y][tc * 8:(tc + 1) * 8] for y in range(8)]
                    put_chr_tile(out, b4k, tid, sub)

    # 6. Title Screen "WALDO?" -> "BARBA?" (Bank 14, r16..r25, c6..c28).
    # Patch the 5 blank/reused nametable cells overlapped by "BARBA" to empty CHR tiles $ED..$F1
    # so the letters do not get white notches when $00/$1E are skipped on writeback.
    nt14_patches = [
        (1, 15, 0x00, 0xED),
        (2, 12, 0x1E, 0xEE),
        (3, 9,  0x00, 0xEF),
        (4, 7,  0x00, 0xF0),
        (5, 4,  0x00, 0xF1),
    ]
    for tr, tc, old_tid, new_tid in nt14_patches:
        put(out, HEADER_SIZE + 0x0651B + tr * 32 + tc, bytes([new_tid]), expected=bytes([old_tid]))

    # Note: 0x00 (blank) and 0x1E (left postcard border) are skipped when writing back.
    title_b14_nt = [
        [0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F,0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18,0x19],
        [0x1E,0x1F,0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x29,0x2A,0x2B,0x00,0xED,0x2C,0x2D,0x2E,0x2F,0x30,0x31,0x32],
        [0x36,0x37,0x38,0x39,0x3A,0x3B,0x3C,0x3D,0x3E,0x3F,0x40,0x41,0xEE,0x42,0x43,0x44,0x45,0x46,0x47,0x48,0x49,0x4A,0x4B],
        [0x4F,0x50,0x51,0x52,0x53,0x54,0x55,0x56,0x00,0xEF,0x57,0x58,0x59,0x5A,0x5B,0x5C,0x5D,0x5E,0x5F,0x60,0x61,0x62,0x63],
        [0x67,0x00,0x68,0x69,0x6A,0x6B,0x00,0xF0,0x6C,0x6D,0x6E,0x6F,0x70,0x71,0x72,0x73,0x74,0x75,0x76,0x77,0x00,0x78,0x79],
        [0x7D,0x00,0x7E,0x7F,0xF1,0x80,0x81,0x82,0x83,0x84,0x85,0x86,0x87,0x88,0x89,0x8A,0x8B,0x8C,0x8D,0x8E,0x8F,0x90,0x91],
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
    x0, y0 = 32.0, 49.0

    def in_bowl(lu: float, v: float, v0: float, v1: float, w: float, r_out: float) -> bool:
        if lu < 0 or lu >= w or v < v0 or v >= v1:
            return False
        if lu > w - r_out:
            if v < v0 + r_out and (lu - (w - r_out)) ** 2 + (v - (v0 + r_out)) ** 2 > r_out ** 2:
                return False
            if v > v1 - r_out and (lu - (w - r_out)) ** 2 + (v - (v1 - r_out)) ** 2 > r_out ** 2:
                return False
        # Hollow interior with 1.5px rounded right corners
        h_r = w - 4.0
        hv0, hv1 = v0 + 3.8, v1 - 3.8
        if 4.0 <= lu < h_r and hv0 <= v < hv1:
            ri = 1.5
            if lu > h_r - ri:
                if v < hv0 + ri and (lu - (h_r - ri)) ** 2 + (v - (hv0 + ri)) ** 2 > ri ** 2:
                    return True
                if v > hv1 - ri and (lu - (h_r - ri)) ** 2 + (v - (hv1 - ri)) ** 2 > ri ** 2:
                    return True
            return False
        return True

    def in_b(lu: float, v: float) -> bool:
        """19x28 'B' with smooth circular-arc corners on both bowls."""
        if lu < 0 or lu >= 19.0 or v < 0 or v >= 28.0:
            return False
        if lu < 4.0:
            return True
        return in_bowl(lu, v, 0.0, 15.2, 18.2, 3.5) or in_bowl(lu, v, 12.2, 28.0, 19.0, 3.5)

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
        if ch == 'B':
            return in_b(lu, v)
        gx = min(4, int(lu / 3.8))
        gy = min(6, int(v / 4.0))
        return glyphs[ch][gy][gx] == '1'

    def to_uv(px: float, py: float) -> tuple[float, float]:
        dx, dy = px - x0, py - y0
        return (dx * ca + dy * sa, -dx * sa + dy * ca)

    # Clear WALDO strip (inside red-palette region, strictly above the bottom postcard border and left of '?')
    for y in range(H14):
        for x in range(W14):
            if x >= 161 or (x >= 160 and y < 14) or y >= 99.0 - 0.37 * x:
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

    # 8. Slot Machine Barba portrait (CHR Bank 3, tiles $00..$1F, 4x8 = 32x64 px).
    # BG Pal 1 = [20(white), 0E(black), 38(pale yellow), 16(red)].
    slot_w, slot_h = 32, 64
    sgrid = [['0'] * slot_w for _ in range(slot_h)]
    body_mask = [[False] * slot_w for _ in range(slot_h)]
    head_24_19 = resize_xy(source_head(z2, 'open'), 24, 19)
    scmap = {'1': '3', '2': '2', '3': '0'}

    def sblit(rows_src: list[str], x0: int, y0: int) -> None:
        for iy, row in enumerate(rows_src):
            for ix, px in enumerate(row):
                xx, yy = x0 + ix, y0 + iy
                if px != '0' and 1 <= xx < 31 and 1 <= yy < 63:
                    sgrid[yy][xx] = scmap[px]
                    body_mask[yy][xx] = True

    # Draw coiled elbow (curving left) + horizontal torso + tapered tail tip, then curving neck (y=21..44)
    slot_elbow = [r[::-1] for r in resize_xy(elbow_16, 12, 14)]
    slot_trail = [r[::-1] for r in resize_xy(trail_32, 16, 14)]
    sblit(slot_elbow, 17, 43)
    sblit(slot_trail, 2, 43)
    neck_12_slot = resize_x(neck, 12)
    for y in range(21, 45):
        t = y - 21
        cx = 13 + min(4, (t * 5) // 22)
        sblit([neck_12_slot[t % 16]], cx, y)
    # Draw head at x=2..25, y=5..23
    sblit(head_24_19, 2, 5)
    # Add 1px black outline around Barba (on white background)
    for y in range(1, slot_h - 1):
        for x in range(1, slot_w - 1):
            if not body_mask[y][x]:
                if any(body_mask[y + dy][x + dx] for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                    sgrid[y][x] = '1'
    # 1px black frame around the 32x64 reel cell
    for x in range(slot_w):
        sgrid[0][x] = '1'
        sgrid[slot_h - 1][x] = '1'
    for y in range(slot_h):
        sgrid[y][0] = '1'
        sgrid[y][slot_w - 1] = '1'
    put_grid(out, bank_4k=3, base_tile=0x00, rows=[''.join(r) for r in sgrid], cols=4, tile_rows=8)

    # 9. Moon Ending Barba sprite (1KB CHR Bank 65 = 4KB Bank 16 $40..$53, 44x48 px, 10 sprites in 8x16 mode).
    # Map R4 ($1800-$1BFF, tiles $80-$BF) -> Bank 65 at $A042 via $BF9F, and draw 10 sprites at $A1B6 via $BFB2.
    # All 10 sprites use Sprite Pal 2 [0E(trans), 20(white), 16(red), 38(pale yellow)].
    mcmap = {'0': '0', '1': '2', '2': '3', '3': '1'}
    mcanvas = [['0'] * 44 for _ in range(48)]
    mhead = [r[::-1] for r in head_24]
    mneck = [r[::-1] for r in neck_raw]
    melbow = [r[::-1] for r in elbow_16]
    mtail = [r[::-1] for r in resize_x(trail_32, 16)]

    def mblit(rows: list[str], ox: int, oy: int) -> None:
        for iy, row in enumerate(rows):
            for ix, px in enumerate(row):
                if px != '0' and 0 <= oy + iy < 48 and 0 <= ox + ix < 44:
                    mcanvas[oy + iy][ox + ix] = mcmap[px]

    mblit(mtail, 0, 32)
    mblit(melbow, 16, 32)
    mblit(mneck, 16, 16)
    mblit(mneck[:4], 16, 30)
    mblit(mhead, 16, 3)

    # Waldo space helmet bubble around Barba's head (center (27.5, 10.5), rx=15.0, ry=10.0).
    for y in range(21):
        for x in range(12, 44):
            if mcanvas[y][x] != '0':
                continue
            dx = (x - 27.5) / 15.0
            dy = (y - 10.5) / 10.0
            r2 = dx * dx + dy * dy
            if 0.80 <= r2 <= 1.08:
                mcanvas[y][x] = '1'
            elif dx < -0.20 and dy < -0.20 and 0.48 <= r2 <= 0.64:
                mcanvas[y][x] = '1'
            elif 0.35 <= dx <= 0.55 and -0.60 <= dy <= -0.35 and 0.45 <= r2 <= 0.65:
                mcanvas[y][x] = '1'
    # Helmet neck collar at y=19..20 across neck (x=17..30)
    for x in range(17, 31):
        mcanvas[19][x] = '1'
        if x % 2 == 1:
            mcanvas[20][x] = '2'

    mrows = [''.join(r) for r in mcanvas]
    # 10 8x16 sprite pairs in Bank 65 (4KB Bank 16, tiles $40..$53):
    # 0..3: Head+Helmet at (x=12,20,28,36, y=0..15)
    # 4..5: Neck+Collar at (x=16,24, y=16..31)
    # 6..9: Tail+Torso+Elbow at (x=0,8,16,24, y=32..47)
    moon_sprites = [
        (12, 0), (20, 0), (28, 0), (36, 0),
        (16, 16), (24, 16),
        (0, 32), (8, 32), (16, 32), (24, 32),
    ]
    for idx, (sx, sy) in enumerate(moon_sprites):
        for sub_y in (0, 8):
            tile_rows = [mrows[sy + sub_y + y][sx:sx + 8] for y in range(8)]
            put_chr_tile(out, 16, 0x40 + idx * 2 + (sub_y // 8), tile_rows)

    # Move Rocket interior cols 3..4, rows 1..5 (20 tiles) into Moon BG (4K Bank 10: $AC..$BF)
    # with Rocket aligned at X=$F0 (-16, so cols 2..7 are at X=0..47) and Y=$60 (96).
    # That reduces Rocket to 4 sprites/scanline across rows 1..5, giving 4 sprites/scanline for Barba at all heights.
    rocket_bg_cmap = {0: 0, 1: 3, 2: 1, 3: 0}
    bg_next = 0xAC
    col3_tiles = []
    col4_tiles = []
    for r in range(1, 6):
        for c, dst in ((3, col3_tiles), (4, col4_tiles)):
            i = r * 8 + c
            t = 0x80 + i * 2 if i < 32 else 0xC0 + (i - 32) * 2
            for h in (0, 1):
                off = WALDO_CHR_OFFSET + 16 * 4096 + (t + h) * 16
                d = decode_tile(bytes(waldo[off:off + 16]))
                put_chr_tile(out, 10, bg_next, [''.join(str(rocket_bg_cmap[p]) for p in row) for row in d])
                dst.append(bg_next)
                bg_next += 1
    assert bg_next <= 0xC1
    put(out, HEADER_SIZE + 0x000CD, bytes([0x60]), expected=bytes([0x5C]))  # Rocket Y = $60
    put(out, HEADER_SIZE + 0x00145, bytes([0xEF]), expected=bytes([0xF4]))  # Rocket X = $F0
    put(out, HEADER_SIZE + 0x00158, bytes.fromhex('20 10 ae ea'), expected=bytes.fromhex('a9 2c 85 26'))

    # Store col3_tiles (10 bytes) + col4_tiles (10 bytes) + hide OAM offsets (10 bytes) at $AF00
    hide_oam = bytes([
        0x2C, 0x30, 0x4C, 0x50, 0x6C, 0x70, 0x8C, 0x90, 0xAC, 0xB0,  # Rocket cols 3..4 rows 1..5
    ])
    put(out, HEADER_SIZE + 0x00F00, bytes(col3_tiles) + bytes(col4_tiles) + hide_oam, expected=bytes(30))
    # $AE10: VBlank-sync write of Rocket cols 3..4 (c=1..2, r=14..23) + clear $228B..$229E + attrs $23D8/$23E0/$23E8
    rocket_bg_code = bytes.fromhex(
        'a5 00 29 7f 8d 00 20 2c 02 20 2c 02 20 10 fb '
        'a5 00 09 04 8d 00 20 '
        'a9 21 8d 06 20 a9 c1 8d 06 20 '
        'a2 00 bd 00 af 8d 07 20 e8 e0 0a d0 f5 '
        'a9 21 8d 06 20 a9 c2 8d 06 20 '
        'a2 00 bd 0a af 8d 07 20 e8 e0 0a d0 f5 '
        'a5 00 29 fb 8d 00 20 '
        'a9 23 8d 06 20 a9 d8 8d 06 20 a9 50 8d 07 20 '
        'a9 23 8d 06 20 a9 e0 8d 06 20 a9 55 8d 07 20 '
        'a9 23 8d 06 20 a9 e8 8d 06 20 a9 55 8d 07 20 '
        'a9 00 8d 06 20 8d 06 20 8d 05 20 8d 05 20 '
        'a5 00 8d 00 20 '
        'a0 00 a9 f4 be 14 af 9d 00 07 c8 c0 0a d0 f5 '
        'a9 2c 85 26 60'
    )
    assert len(rocket_bg_code) <= 0xF0, f'rocket_bg_code too large: {len(rocket_bg_code)}'
    put(out, HEADER_SIZE + 0x00E10, rocket_bg_code, expected=bytes(len(rocket_bg_code)))

    # Patch Bank 0 $A042 -> JSR $BF9F to map R4 = Bank 65, and $A1B6 -> JMP $BFB2 for 10-sprite OAM.
    put(out, HEADER_SIZE + 0x00042, bytes.fromhex('20 9f bf ea ea'), expected=bytes.fromhex('a9 47 8d 04 02'))
    moon_oam_tables = bytes([
        0xE0, 0xE4, 0xE8, 0xEC, 0xF0, 0xF4, 0xF8, 0xFC, 0xAC, 0xB0,  # OAM offsets (#56..#63, #43..#44)
        12, 20, 28, 36, 16, 24, 0, 8, 16, 24,                        # dx
        0xE6, 0xE6, 0xE6, 0xE6, 0xF6, 0xF6, 0x06, 0x06, 0x06, 0x06,  # dy (-26, -10, +6)
    ])
    put(
        out, HEADER_SIZE + 0x001B6,
        bytes.fromhex('4c b2 bf') + moon_oam_tables + bytes([0x60]),
        expected=waldo[HEADER_SIZE + 0x001B6:HEADER_SIZE + 0x001D8],
    )
    moon_bank0_code = bytes.fromhex(
        # $BF9F: map R4 = Bank 65, restore R7 = 0 ($A042)
        'a9 44 8d 00 80 a9 41 8d 01 80 a9 47 8d 04 02 8d 00 80 60'
    )
    moon_oam_code = bytes.fromhex(
        'a0 00 a9 81 85 08 '           # LDY #0; LDA #$81; STA $08
        'be b9 a1 '                    # LDX $A1B9,Y
        'a5 27 18 79 cd a1 9d 00 07 '  # LDA $27; CLC; ADC $A1CD,Y; STA $0700,X
        'a5 08 9d 01 07 18 69 02 85 08 '  # LDA $08; STA $0701,X; CLC; ADC #2; STA $08
        'a9 02 9d 02 07 '              # LDA #2; STA $0702,X
        'a5 26 18 79 c3 a1 9d 03 07 '  # LDA $26; CLC; ADC $A1C3,Y; STA $0703,X
        'c8 c0 0a d0 d7 60'            # INY; CPY #10; BNE loop (-41 = $D7); RTS
    )
    put(out, HEADER_SIZE + 0x01F9F, moon_bank0_code + moon_oam_code, expected=bytes(len(moon_bank0_code + moon_oam_code)))

    # 7. Expand PRG from 128KB (8x16KB) to 256KB (16x16KB) and add Barba's sampled roar in Bank 16 ($C000).
    # Waldo uses MMC3 PRG Mode 1 ($8000 bit 6=1: $8000=Bank 30, $A000=R7, $C000=R6, $E000=Bank 31)
    # and never reads or switches R6 ($C000-$DFFF), making Bank 16 ideal for DPCM samples + hooks.
    roar_wav = ROOT / 'roms/roar.wav'
    if roar_wav.is_file():
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        sample, roar_info = roar_sample.convert(roar_wav, OUT_PATH.parent)
        assert len(sample) <= 0x0900, f'Sample too large for $C000-$C8FF: {len(sample)}'
        roar_rate = roar_info['rate_index']
        roar_len = (len(sample) - 1) // 16

        hdr = bytearray(out[:HEADER_SIZE])
        hdr[4] = 0x10  # 16 x 16KB PRG = 256KB
        prg_128 = bytes(out[HEADER_SIZE:HEADER_SIZE + 0x20000])
        chr_128 = bytes(out[HEADER_SIZE + 0x20000:])

        prg_256 = bytearray(b'\xff' * 0x40000)
        prg_256[0x00000:0x1C000] = prg_128[0x00000:0x1C000]  # Banks 0..13
        prg_256[0x3C000:0x40000] = prg_128[0x1C000:0x20000]  # Banks 14..15 -> 30..31

        # Bank 16 ($C000-$DFFF at 0x20000): DPCM sample + roar helpers
        prg_256[0x20000:0x20000 + len(sample)] = sample
        play_roar = bytes([
            0xAD, 0xF6, 0x03, 0x0D, 0xF7, 0x03, 0x29, 0x0F, 0x8D, 0x15, 0x40,
            0xA9, 0x40, 0x8D, 0x11, 0x40,
            0xA9, roar_rate, 0x8D, 0x10, 0x40,
            0xA9, 0x00, 0x8D, 0x12, 0x40,
            0xA9, roar_len, 0x8D, 0x13, 0x40,
            0xAD, 0xF7, 0x03, 0x09, 0x10, 0x8D, 0xF7, 0x03,
            0x0D, 0xF6, 0x03, 0x8D, 0x15, 0x40, 0x60,
        ])
        nmi_dmc_check = bytes.fromhex(
            'ad f7 03 29 10 f0 0f ad 15 40 29 10 d0 08 ad f7 03 29 ef 8d f7 03 ad f6 03 60'
        )
        found_barba_roar = bytes.fromhex(
            'b0 0a 48 98 48 20 00 c9 68 a8 68 60 a0 6c a9 ea 60'
        )
        moon_ending_roar = bytes.fromhex('20 00 c9 4c 0b e2')
        title_start_roar = bytes.fromhex('20 00 c9 4c ed e5')

        prg_256[0x20900:0x20900 + len(play_roar)] = play_roar
        prg_256[0x20930:0x20930 + len(nmi_dmc_check)] = nmi_dmc_check
        prg_256[0x20950:0x20950 + len(found_barba_roar)] = found_barba_roar
        prg_256[0x20964:0x20964 + len(moon_ending_roar)] = moon_ending_roar
        prg_256[0x2096A:0x2096A + len(title_start_roar)] = title_start_roar

        # Bank 31 ($E000-$FFFF at 0x3E000): RESET sets R6=16 (in $FFE0-$FFF9 tail padding), plus NMI/level/ending hooks
        put(prg_256, 0x3E03B, bytes.fromhex('20 e0 ff ea ea ea ea ea ea ea'),
            expected=bytes.fromhex('a9 47 8d 00 80 a9 52 8d 01 80'))
        put(prg_256, 0x3FFE0, bytes.fromhex('a9 46 8d 00 80 a9 10 8d 01 80 a9 47 8d 00 80 a9 52 8d 01 80 60'),
            expected=bytes(21))
        put(prg_256, 0x3FA13, bytes.fromhex('20 30 c9'), expected=bytes.fromhex('ad f6 03'))
        put(prg_256, 0x3EBC8, bytes.fromhex('20 50 c9 ea ea ea'), expected=bytes.fromhex('90 04 a0 6c a9 ea'))
        put(prg_256, 0x3E1B4, bytes.fromhex('20 64 c9'), expected=bytes.fromhex('20 0b e2'))
        # Bank 3 ($A03C): Title Screen Start roar
        put(prg_256, 0x0603C, bytes.fromhex('20 6a c9'), expected=bytes.fromhex('20 ed e5'))

        out = hdr + prg_256 + chr_128

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_bytes(out)
    PLAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAY_PATH.write_bytes(out)
    print(f'Wrote {OUT_PATH} and {PLAY_PATH} ({len(out)} bytes)')
    return OUT_PATH


if __name__ == '__main__':
    build()
