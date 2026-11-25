"""Assemble and patch Donkey Kong into Barba Kong (NES 2.0 Mapper 176 MMC3).

Round 2 upgrade:
- Hero: Lil' Barba (Wyrmling) climbing girders/ladders to save Princess Zelda.
- Villain: Big Bad Link (smug/sinister Z2-inspired Link) stomping and hurling hazards.
- Hazards & Pickups: Barba Fireballs, Z2 Bombs, Z2 Bits/Bubbles, Z2 Shields, Flame Fury.
- Audio: Sampled Barba roar (roar.dmc via tools/roar_sample.py) in fixed bank $C000-$FFFF.
- Architecture: 256 KB PRG + 32 KB CHR MMC3 banking (R0-R5 CHR animations, R6/R7 PRG).
"""
from __future__ import annotations

import json
from pathlib import Path

from nes import CHR_OFFSET as Z2_CHR_OFFSET, decode_tile, encode_tile, load_source
from pack_f13 import Asm6502
import roar_sample


# Fixed entry points in guest WRAM bank ($7800-$7BFF)
DK_WRAM_CODE_BASE = 0x7800
DK_NMI_HOOK       = 0x7840
DK_WIN_HOOK       = 0x7870
DK_SEED_RNG       = 0x7880
DK_RETURN         = 0x7960
DK_BOOT           = 0x7AE0

# Guest WRAM state bytes (in guest WRAM bank $A3)
# $7FF0-$7FF7 are reserved for Barba's subgame RNG seed.
DK_FB0_TIMER      = 0x7FE0  # Fireball item slot 0 lifetime (0 = inactive)
DK_FB0_X          = 0x7FE1
DK_FB0_Y          = 0x7FE2
DK_FB0_VX         = 0x7FE3
DK_FB0_VY         = 0x7FE4
DK_FB1_TIMER      = 0x7FE5  # Fireball item slot 1 lifetime (0 = inactive)
DK_FB1_X          = 0x7FE6
DK_FB1_Y          = 0x7FE7
DK_FB1_VX         = 0x7FE8
DK_FB1_VY         = 0x7FE9
DK_FB_COOLDOWN    = 0x7FEA  # Frames until next fireball shot
DK_SPRING_TIMER   = 0x7FEB  # Stage 2 (75m) Z2 Shield spawn timer (separate from bomb $36)
DK_ROAR_TIMER     = 0x7FF8  # Countdown frames for active roar.dmc playback
DK_ANIM_FRAME     = 0x7FF9  # Global NMI animation frame counter
DK_CHR_BANK_R0    = 0x7FFA  # Shadow of current MMC3 R0 bank (Lil' Barba)
DK_CHR_BANK_R1    = 0x7FFB  # Shadow of current MMC3 R1 bank (Zelda / Hazards)
DK_CHR_BANK_R4    = 0x7FFC  # Shadow of current MMC3 R4 bank (Big Bad Link)
DK_ROAR_COUNT     = 0x7FFD  # Number of sampled Barba roars triggered
DK_WIN_FLAG       = 0x7FFE  # 0 = Start+Select exit, DK_REWARD_MAGIC = 100m win exit
DK_DEBOUNCE       = 0x7FFF  # 60-frame ($3C) NMI debounce counter

# Barba WRAM bank 0 reward flag
DK_REWARD_ADDR    = 0x648F
DK_REWARD_MAGIC   = 0x44    # 'D'

# Donkey Kong (USA, NROM-128) addresses
DK_ORIG_NMI       = 0xC85F
DK_ORIG_RESET     = 0xC79E
DK_WIN_PATCH_ADDR = 0xC8B3  # 100m (Stage 3 / $53=4) rescue cutscene end ($044F==8, $43==0)
DK_PAD1_ZP        = 0x14    # Raw P1 held buttons (Bit 5 = Select $20, Bit 4 = Start $10)
DK_START_SELECT   = 0x30

STANDALONE_RESTORE_ADDR = 0x80F0

# Relocated DK routines ($F1B4-$F55A -> $8000-$83A6 in PRG Bank 1)
DK_RELOC_ORIG_START = 0xF1B4
DK_RELOC_ORIG_END   = 0xF55B
DK_RELOC_NEW_BASE   = 0x8000
DK_BANK1_CODE_BASE  = 0x83C0

# Sampled roar placement inside freed $F1B4-$FA47 window in fixed bank 31
ROAR_DMC_ADDR       = 0xF1C0
ROAR_DMC_CAPACITY   = 0xFA48 - ROAR_DMC_ADDR  # 2184 bytes (fits 2177-byte roar.dmc)


def _reloc_addr(orig_addr: int) -> int:
    return DK_RELOC_NEW_BASE + (orig_addr - DK_RELOC_ORIG_START)


# ---------------------------------------------------------------------------
# Art helpers & Barba Kong pixel recipes (build-time only; zero ROM pixels committed)
# ---------------------------------------------------------------------------

def _flip_h(rows: list[str]) -> list[str]:
    return [r[::-1] for r in rows]


def _flip_v(rows: list[str]) -> list[str]:
    return list(reversed(rows))


def _shift(rows: list[str], dx: int = 0, dy: int = 0) -> list[str]:
    h, w = len(rows), len(rows[0])
    out = []
    for y in range(h):
        sy = y - dy
        if 0 <= sy < h:
            line = [rows[sy][x - dx] if 0 <= x - dx < w else '0' for x in range(w)]
            out.append(''.join(line))
        else:
            out.append('0' * w)
    return out


def _overlay(base: list[str], fg: list[str]) -> list[str]:
    out = [list(r) for r in base]
    for y, r in enumerate(fg):
        for x, c in enumerate(r):
            if c != '0' and y < len(out) and x < len(out[0]):
                out[y][x] = c
    return [''.join(r) for r in out]


def _encode_16x16_dk_order(rows: list[str]) -> list[bytes]:
    """Encode a 16x16 sprite into 4 tiles in DK's $F096 column-major order:
    (top-left, bottom-left, top-right, bottom-right).
    """
    assert len(rows) == 16 and all(len(r) == 16 for r in rows)
    tl = encode_tile([r[0:8] for r in rows[0:8]])
    bl = encode_tile([r[0:8] for r in rows[8:16]])
    tr = encode_tile([r[8:16] for r in rows[0:8]])
    br = encode_tile([r[8:16] for r in rows[8:16]])
    return [tl, bl, tr, br]


def _encode_16x8_row_major(rows: list[str]) -> list[bytes]:
    assert len(rows) == 8 and all(len(r) == 16 for r in rows)
    return [
        encode_tile([r[0:8] for r in rows]),
        encode_tile([r[8:16] for r in rows]),
    ]


def _make_lil_barba_poses(barba_art: dict) -> dict[str, list[str]]:
    """Build all 16x16 Lil' Barba (Wyrmling) sprite poses from assets/barba.json."""
    small = barba_art['small']
    small_step = barba_art['small_step']
    front = barba_art['front']
    front_step = barba_art['front_step']
    back = barba_art['back']
    back_step = barba_art['back_step']

    walk3 = [
        '0000000000000000',
        '0000000003000000',
        '0000000031300000',
        '0000000122211100',
        '0000001223222211',
        '0000031222222221',
        '0000001221313130',
        '0000031222222210',
        '0000312211111100',
        '0000031233210000',
        '0000312222210000',
        '0003122233210000',
        '0131222222100000',
        '1222332233100000',
        '0111221122100000',
        '0000110001100000',
    ]
    claw_l = [
        '0000000000000000',
        '0000000000000000',
        '0000000000000000',
        '0030000000000000',
        '0013000000000000',
        '0012000000000000',
        '0001000000000000',
    ] + ['0' * 16] * 9
    claw_r = _flip_h(claw_l)
    wings_up = [
        '0000000000000000',
        '0000000000000000',
        '0000000000000000',
        '0000000000000000',
        '0000000000000000',
        '0300000000000000',
        '0130000000000000',
        '1223000000000000',
        '1221000000000000',
        '0110000000000000',
    ] + ['0' * 16] * 6
    wings_down = [
        '0000000000000000',
        '0000000000000000',
        '0000000000000000',
        '0000000000000000',
        '0000000000000000',
        '0000000000000000',
        '0000000000000000',
        '0300000000000000',
        '1230000000000000',
        '1223000000000000',
        '0110000000000000',
    ] + ['0' * 16] * 5
    roar = [
        '0000000003000000',
        '0000000031300000',
        '0000000122211100',
        '0000001223222211',
        '0000031222222221',
        '0000001221313130',
        '0000031222111110',
        '0000312211000000',
        '0000031233213130',
        '0000312222221110',
        '0000031233210000',
        '0000312222100000',
        '1303122332100000',
        '1211222222100000',
        '0133323321000000',
        '0001111110000000',
    ]
    skid = [
        '0000000000000000',
        '0000000003000000',
        '0000000031300000',
        '0000000122211100',
        '0000001223222211',
        '0000031222222221',
        '0000001221313130',
        '0000031222222210',
        '0000312211111100',
        '0003122332100000',
        '0031222222100000',
        '0012222332100000',
        '0122122222100000',
        '1321122332100000',
        '0110011221100000',
        '0000001111110000',
    ]
    return {
        'stand': small,
        'walk1': small_step,
        'walk2': _shift(small, 0, -1),
        'walk3': walk3,
        'climb0': back,
        'climb1': back_step,
        'climb_top0': _overlay(back, claw_l),
        'climb_top1': _overlay(back_step, claw_r),
        'fury_swing0': roar,
        'fury_swing1': _overlay(roar, wings_up),
        'jump0': _overlay(_shift(small_step, 0, -1), wings_up),
        'jump1': _overlay(_shift(small_step, 0, -1), wings_down),
        'skid': skid,
        'front': front,
        'front_step': front_step,
        'ko': _flip_v(front),
    }


def _make_big_bad_link_bg(pose: str, variant: int = 0) -> list[str]:
    """Build 48x32 (6 cols x 4 rows) Big Bad Link BG art for top-left boss perch."""
    g = [['0'] * 48 for _ in range(32)]

    def put(x0: int, y0: int, lines: list[str]) -> None:
        for dy, ln in enumerate(lines):
            for dx, ch in enumerate(ln):
                if ch != '.' and 0 <= y0 + dy < 32 and 0 <= x0 + dx < 48:
                    g[y0 + dy][x0 + dx] = ch

    # Pointed cap animates tip wiggle across CHR banks
    tip = '1111' if variant % 2 == 0 else '111.'
    put(12, 0, [
        f'..........111111{tip}.....',
        '.......111111111111111....',
        '.....1111111111111111111..',
        '....111111111111111111111.',
        '...1111111111111111111....',
        '...1111111111111111.......',
        '..333333333333333333......',
    ])
    eye_row = '.23322200322222300222332..' if variant != 2 else '.23322220322222320222332..'
    put(11, 6, [
        '...333333333333333333.....',
        '..33322222222222222333....',
        '223322332222222233223322..',
        eye_row,
        '..332222222222222222233...',
        '...3222222223322222223....',
        '...3322222222222222233....',
        '....32222000000022223.....',
        '....33222223332222233.....',
        '.....333222222222333......',
    ])
    put(11, 15, [
        '....1111111111111111......',
        '..11111113311111111111....',
        '.1111111113311111111111...',
        '.1111111111331111111111...',
        '.1111111111133111111111...',
        '..33333333333333333333....',
        '..33333333222233333333....',
        '..11111111111111111111....',
        '...111111111111111111.....',
        '...111111110011111111.....',
    ])
    if pose in ('stomp_l', 'stomp_r'):
        ly = 23 if pose == 'stomp_l' else 25
        ry = 23 if pose == 'stomp_r' else 25
        put(13, ly, ['333333', '333333', '3333333', '3333333', '3333333'][: 32 - ly])
        put(28, ry, ['333333', '333333', '3333333', '3333333', '3333333'][: 32 - ry])
    else:
        put(13, 25, ['333333', '333333', '3333333', '3333333', '3333333', '3333333', '3333333'])
        put(28, 25, ['333333', '333333', '3333333', '3333333', '3333333', '3333333', '3333333'])

    if pose == 'idle':
        put(6, 16, ['.....111111', '...11111111', '..2222111..', '..2222.....', '...33......'])
        put(33, 16, ['111111.....', '11111111...', '..1112222..', '.....2222..', '......33...'])
    elif pose == 'stomp_l':
        put(6, 8, ['22222..', '22222..', '2222...', '.1111..', '..1111.', '...1111', '....111', '....111', '....111'])
        put(33, 16, ['111111.....', '11111111...', '..1112222..', '.....2222..'])
    elif pose == 'stomp_r':
        put(6, 16, ['.....111111', '...11111111', '..2222111..', '..2222.....'])
        put(31, 8, ['......22222', '......22222', '.......2222', '......1111.', '.....1111..', '....1111...', '...1111....', '...111.....', '...111.....'])
    elif pose == 'throw_l':
        put(2, 15, ['...11111111', '22221111111', '22221111...', '222........'])
        put(33, 16, ['111111.....', '11111111...', '..1112222..'])
    elif pose == 'throw_r':
        put(6, 16, ['.....111111', '...11111111', '..2222111..'])
        put(33, 15, ['11111111...', '11111112222', '...11112222', '........222'])
    elif pose == 'grab':
        put(5, 13, ['222211111..', '22221111111', '222........'])
        put(33, 13, ['..111112222', '11111112222', '........222'])
    elif pose in ('fall_a', 'fall_b'):
        put(6, 9, ['2222...', '22222..', '.111111', '..11111', '...1111'])
        put(34, 9, ['...2222', '..22222', '111111.', '11111..', '1111...'])
        if pose == 'fall_b':
            g = g[::-1]
    return [''.join(r) for r in g]


def _make_big_bad_link_sprite_32x48() -> list[str]:
    """32x48 Big Bad Link sprite for $40..$57 (4 cols x 6 rows) during cutscenes."""
    bg = _make_big_bad_link_bg('stomp_l', 0)
    # Center 32x32 slice (cols 8..39) padded vertically to 32x48
    mid = [r[8:40] for r in bg]
    return ['0' * 32] * 8 + mid + ['0' * 32] * 8


def _make_zelda_poses(z2_bytes: bytes, variant: int = 0) -> tuple[list[str], list[str], list[str]]:
    """Build 16x24 Princess Zelda (top 16x8, stand 16x16, wave 16x16) from vanilla Z2 CHR 0E ($D8..$DF)."""
    assert z2_bytes[:4] == b'NES\x1a', 'Invalid z2.nes'
    bank_off = Z2_CHR_OFFSET + 14 * 4096
    tiles = {
        t: decode_tile(z2_bytes[bank_off + t * 16 : bank_off + (t + 1) * 16])
        for t in range(0xD8, 0xE0)
    }
    grid32: list[str] = []
    for l_tid, r_tid in ((0xD8, 0xDA), (0xD9, 0xDB), (0xDC, 0xDE), (0xDD, 0xDF)):
        for y in range(8):
            grid32.append(''.join(str(c) for c in (tiles[l_tid][y] + tiles[r_tid][y])))

    # Fit 16x32 side-profile Zelda into DK's 16x24 slot (keep head/bodice rows 1..18 + 6 skirt rows).
    keep_rows = list(range(1, 19)) + [19, 22, 25, 28, 30, 31]
    grid24 = [grid32[i] for i in keep_rows]

    # Map Z2 indices to Barba Kong SPR1 palette (0=trans, 1=pink $25, 2=peach $36, 3=gold $27).
    twinkle = '1' if variant % 2 == 0 else '2'
    remapped: list[str] = []
    for idx, row in enumerate(grid24):
        if idx < 18:
            # Head/hair/bodice: Z2 1 (hair/outline) -> 3 (gold), 2 (skin) -> 2 (peach), 3 (crown/sleeve) -> 1 (pink)
            cmap = {'0': '0', '1': '3', '2': '2', '3': '1'}
        else:
            # Skirt: Z2 1 (outline/shoes) -> 3 (gold), 2 (skirt body) -> 1 (pink)
            cmap = {'0': '0', '1': '3', '2': '1', '3': '1'}
        remapped.append(''.join(cmap[c] for c in row))

    # Subtle crown jewel twinkle across R1 shimmer banks
    remapped[1] = remapped[1][:3] + twinkle + remapped[1][4:]

    top = remapped[0:8]
    stand = remapped[8:24]

    # Wave pose: raise left/front arm to wave while keeping the exact Z2 side-profile body
    wave = list(stand)
    wave[2] = '0020' + wave[2][4:]
    wave[3] = '0311' + wave[3][4:]
    wave[4] = '0111' + wave[4][4:]
    wave[6] = '0000' + wave[6][4:]
    wave[7] = '00000' + wave[7][5:]
    wave[8] = '00000' + wave[8][5:]
    wave[9] = '00000' + wave[9][5:]

    # Mirror Princess Zelda horizontally so she faces right (away from Big Bad Link)
    return _flip_h(top), _flip_h(stand), _flip_h(wave)


def _make_hazard_sprites(z2_bytes: bytes, variant: int) -> dict[str, list[str]]:
    """Build Tumbling Z2 Bombs, Falling Z2 Bombs, Z2 Bits, Z2 Bubbles, Z2 Shields, Flame Fury."""
    # Extract Z2 bank-2 P-Bag / Magic Jar silhouette reference for build-time validation
    assert z2_bytes[:4] == b'NES\x1a', 'Invalid z2.nes'

    # Classic Zelda Blue Bombs ("B3 Star"): collared neck, fixed upper-left specular
    # highlight, orbiting star glint, and 4-bank R1 crackling fuse spark.
    v = variant % 4

    def _spark_patch(rows: list[str], coords: list[tuple[int, int, str]]) -> list[str]:
        grid = [list(r) for r in rows]
        for x, y, ch in coords:
            grid[y][x] = ch
        return ["".join(r) for r in grid]

    # Top-right spark (used on rolling frame 0)
    tr_sparks = [
        [(10, 0, '2'), (11, 0, '3'), (9, 1, '2'), (10, 1, '3'), (11, 1, '2'), (12, 1, '3'), (11, 2, '3')],
        [(10, 0, '3'), (11, 0, '2'), (9, 1, '3'), (10, 1, '2'), (11, 1, '3'), (12, 1, '2'), (11, 2, '2')],
        [(9, 0, '2'), (11, 0, '3'), (10, 1, '3'), (11, 1, '2'), (12, 1, '0'), (13, 1, '3'), (11, 2, '3')],
        [(10, 0, '3'), (12, 0, '2'), (9, 1, '2'), (10, 1, '3'), (11, 1, '2'), (12, 1, '0'), (11, 2, '2')],
    ][v]
    # Bottom-right spark (used on rolling frame 1)
    br_sparks = [
        [(15, 11, '3'), (12, 12, '2'), (13, 12, '3'), (14, 12, '2'), (15, 12, '3'), (13, 13, '2'), (14, 13, '3')],
        [(15, 11, '2'), (12, 12, '3'), (13, 12, '2'), (14, 12, '3'), (15, 12, '2'), (13, 13, '3'), (14, 13, '2')],
        [(14, 11, '3'), (12, 12, '3'), (13, 12, '2'), (14, 12, '0'), (15, 12, '3'), (13, 13, '3'), (15, 13, '2')],
        [(15, 11, '2'), (12, 12, '2'), (13, 12, '3'), (14, 12, '2'), (15, 12, '0'), (13, 13, '2'), (14, 13, '3')],
    ][v]
    # Bottom-left spark (used on rolling frame 2)
    bl_sparks = [
        [(4, 13, '3'), (3, 14, '2'), (4, 14, '3'), (5, 14, '2'), (6, 14, '3'), (4, 15, '3'), (5, 15, '2')],
        [(4, 13, '2'), (3, 14, '3'), (4, 14, '2'), (5, 14, '3'), (6, 14, '2'), (4, 15, '2'), (5, 15, '3')],
        [(3, 13, '3'), (2, 14, '3'), (4, 14, '3'), (5, 14, '2'), (6, 14, '0'), (4, 15, '2'), (5, 15, '3')],
        [(4, 13, '2'), (3, 14, '2'), (4, 14, '3'), (5, 14, '2'), (6, 14, '0'), (3, 15, '3'), (5, 15, '2')],
    ][v]
    # Top-left spark (used on rolling frame 3)
    tl_sparks = [
        [(3, 0, '2'), (4, 0, '3'), (2, 1, '2'), (3, 1, '3'), (4, 1, '2'), (5, 1, '3'), (3, 2, '3')],
        [(3, 0, '3'), (4, 0, '2'), (2, 1, '3'), (3, 1, '2'), (4, 1, '3'), (5, 1, '2'), (3, 2, '2')],
        [(2, 0, '2'), (4, 0, '3'), (2, 1, '0'), (3, 1, '3'), (4, 1, '2'), (5, 1, '3'), (3, 2, '3')],
        [(3, 0, '3'), (5, 0, '2'), (2, 1, '3'), (3, 1, '2'), (4, 1, '3'), (5, 1, '0'), (3, 2, '2')],
    ][v]

    rb0 = _spark_patch([
        '0000000000000000',
        '0000000000000000',
        '0000000022000000',
        '0000011122200000',
        '0001111112210000',
        '0011332111111100',
        '0013321112111100',
        '0113211123211110',
        '0112111112111110',
        '0111111111111110',
        '0111111111111110',
        '0011111111111100',
        '0011111111111100',
        '0001111111111000',
        '0000011111100000',
        '0000000000000000',
    ], tr_sparks)
    rb1 = _spark_patch([
        '0000000000000000',
        '0000011111100000',
        '0001111111111000',
        '0011332111111100',
        '0013321111111100',
        '0113211111111110',
        '0112111111111110',
        '0111111112111220',
        '0111111123211220',
        '0111111112111220',
        '0011111111112200',
        '0011111111112200',
        '0001111111100000',
        '0000011111000000',
        '0000000000000000',
        '0000000000000000',
    ], br_sparks)
    rb2 = _spark_patch([
        '0000000000000000',
        '0000011111100000',
        '0001111111111000',
        '0011332111111100',
        '0013321111111100',
        '0113211111111110',
        '0112111111111110',
        '0111111211111110',
        '0111112321111110',
        '0111111211111110',
        '0011111111111100',
        '0011222111111100',
        '0001122211111000',
        '0000002211100000',
        '0000000000000000',
        '0000000000000000',
    ], bl_sparks)
    rb3 = _spark_patch([
        '0000000000000000',
        '0000000000000000',
        '0000002200000000',
        '0000222111100000',
        '0001221111111000',
        '0011111111111100',
        '0011211111111100',
        '0112321111111110',
        '0111211111111110',
        '0111111111111110',
        '0111111111111110',
        '0011111111111100',
        '0011111111111100',
        '0001111111111000',
        '0000011111100000',
        '0000000000000000',
    ], tl_sparks)
    rolling_bombs = [rb0, rb1, rb2, rb3]

    # Falling Z2 Bombs ($90..$97): upright wobble frames with left/right whipping fuse
    fall_sparks_l = [
        ('0000003230000000', '0000000320000000'),
        ('0000002320000000', '0000000230000000'),
        ('0000032030000000', '0000000320000000'),
        ('0000003203000000', '0000000230000000'),
    ][v]
    fall_sparks_r = [
        ('0000000323000000', '0000000230000000'),
        ('0000000232000000', '0000000320000000'),
        ('0000000302300000', '0000000230000000'),
        ('0000003023000000', '0000000320000000'),
    ][v]
    bomb0 = [
        fall_sparks_l[0],
        fall_sparks_l[1],
        '0000002200000000',
        '0000022222000000',
        '0000112221100000',
        '0001133211110000',
        '0011332111111000',
        '0011321121111000',
        '0011111232111000',
        '0011111121111000',
        '0011111111111000',
        '0011111111111000',
        '0001111111110000',
        '0000111111100000',
        '0000011111000000',
        '0000000000000000',
    ]
    bomb1 = [
        fall_sparks_r[0],
        fall_sparks_r[1],
        '0000000022000000',
        '0000002222200000',
        '0000011222110000',
        '0000113321111000',
        '0001133211111100',
        '0001132111211100',
        '0001111112321100',
        '0001111111211100',
        '0001111111111100',
        '0001111111111100',
        '0000111111111000',
        '0000011111110000',
        '0000001111100000',
        '0000000000000000',
    ]

    # Z2 Bits (25m / 75m oil-drum spawns, 2 hopping squish frames)
    bit0 = [
        '0000000000000000',
        '0000000000000000',
        '0000011111100000',
        '0001133333311000',
        '0013333333333100',
        '0133223333223310',
        '0133203333023310',
        '1333223333223331',
        '1333333333333331',
        '1333113333113331',
        '1333333333333331',
        '1333333333333331',
        '0113333333333110',
        '0011111111111100',
        '0000000000000000',
        '0000000000000000',
    ]
    bit1 = [
        '0000000000000000',
        '0000000000000000',
        '0000000000000000',
        '0000000000000000',
        '0000111111110000',
        '0011333333331100',
        '0133322332233310',
        '1333320330233331',
        '1333322332233331',
        '1333333333333331',
        '1333111331113331',
        '1333333333333331',
        '1133333333333311',
        '0011111111111100',
        '0000000000000000',
        '0000000000000000',
    ]
    if variant % 2:
        bit0, bit1 = bit1, bit0

    # Z2 Bubbles (100m flying enemies, 2 wing-flap frames)
    bubble0 = [
        '0100010000100010',
        '1310131001310131',
        '1231321111231321',
        '0133222222223310',
        '0012222222222100',
        '0132200220022310',
        '1322200220022231',
        '1322222112222231',
        '0132222222222310',
        '0013212121213100',
        '0001212121211000',
        '0000111111110000',
        '0100013113100010',
        '0010001001000100',
        '0000000000000000',
        '0000000000000000',
    ]
    bubble1 = [
        '0000000000000000',
        '0000001111000000',
        '0000112222110000',
        '0001322222231000',
        '0013222222223100',
        '0132200220022310',
        '1322200220022231',
        '1322222112222231',
        '1232222222222321',
        '1313212121213131',
        '0101212121211010',
        '0000111111110000',
        '0000013113100000',
        '0000001001000000',
        '0000000000000000',
        '0000000000000000',
    ]
    if variant % 2:
        bubble0, bubble1 = bubble1, bubble0

    # Z2 Shields (75m bouncing/falling hazards)
    shield0 = [
        '0000111111110000',
        '0001222222221000',
        '0012233223322100',
        '0012311331132100',
        '0012312222132100',
        '0012222112222100',
        '0012221221222100',
        '0012221221222100',
        '0001222112221000',
        '0001222222221000',
        '0000122332210000',
        '0000122332210000',
        '0000012222100000',
        '0000001221000000',
        '0000000110000000',
        '0000000000000000',
    ]
    shield1 = [
        '0000001111000000',
        '0000012222100000',
        '0000122332210000',
        '0000123113210000',
        '0000123113210000',
        '0000122112210000',
        '0000122112210000',
        '0000122112210000',
        '0000012112100000',
        '0000012222100000',
        '0000001221000000',
        '0000001221000000',
        '0000000110000000',
        '0000000110000000',
        '0000000110000000',
        '0000000000000000',
    ]
    if variant % 2:
        shield0, shield1 = shield1, shield0

    # Flame Fury pickup / crest ($F6-$F7: 8x16 vertical) and Dragonfire Blast ($FA-$FB: 16x8 horizontal)
    fury_orb = [
        '00011000',
        '00131000',
        '01323100',
        '01232100',
        '13233210',
        '12333210',
        '12322310',
        '12233210',
        '12333210',
        '01222100',
        '00111000',
        '00010000',
        '00121000',
        '01232100',
        '00111000',
        '00000000',
    ]
    if variant % 2:
        fury_orb = _flip_h(fury_orb)

    blast_core = [
        '0000000000110000',
        '0000000111331000',
        '0000011333223100',
        '0001133222223310',
        '0113322222222331',
        '1332222222222231',
        '0113322222222331',
        '0001133222223310',
    ] if variant % 2 == 0 else [
        '0000000001110000',
        '0000001113331000',
        '0000113332223100',
        '0011332222223310',
        '1133222222222331',
        '0113322222222231',
        '0011332222222331',
        '0000113322223310',
    ]

    # Fireball title cursor ($A2, 8x8)
    cursor = [
        '00011000',
        '00123100',
        '01233210',
        '12333321',
        '12333321',
        '01233210',
        '00122100',
        '00011000',
    ] if variant % 2 == 0 else [
        '00100100',
        '00123100',
        '01233210',
        '12333321',
        '12333321',
        '01233210',
        '00123100',
        '00011000',
    ]

    # Z2 Heart / Triforce Heart ($C8-$CB, 16x16)
    heart = [
        '0011100000111000',
        '0133210001322100',
        '1332221012222210',
        '1322222122222210',
        '1222222222222210',
        '1222222222222210',
        '0122222222222100',
        '0122222222222100',
        '0012222222221000',
        '0001222222210000',
        '0000122222100000',
        '0000012221000000',
        '0000001210000000',
        '0000000100000000',
        '0000000000000000',
        '0000000000000000',
    ]

    return {
        'rolling_bombs': rolling_bombs,
        'bomb0': bomb0,
        'bomb1': bomb1,
        'bit0': bit0,
        'bit1': bit1,
        'bubble0': bubble0,
        'bubble1': bubble1,
        'shield0': shield0,
        'shield1': shield1,
        'fury_orb': fury_orb,
        'blast_core': blast_core,
        'cursor': cursor,
        'heart': heart,
    }


def _compile_r4_r5_big_bad_link(dk_bg_hi: bytes, variant: int) -> tuple[bytes, bytes, dict[str, list[int]]]:
    """Compile all 8 Big Bad Link 6x4 BG poses into 2 KB (R4=$80..$BF, R5=$C0..$FF).

    Preserves HUD tiles $D0-$D3 ('TOP-') and $FE-$FF ('1-') from dk_chr and
    deduplicates identical 8x8 tiles so all 8 poses fit cleanly.
    """
    poses = ('idle', 'grab', 'stomp_l', 'throw_l', 'throw_r', 'stomp_r', 'fall_a', 'fall_b')
    reserved = {0xD0, 0xD1, 0xD2, 0xD3, 0xFE, 0xFF}
    blank_tile = b'\x00' * 16
    tile_to_id: dict[bytes, int] = {blank_tile: 0x24}
    chr_2kb = bytearray(2048)
    for tid in reserved:
        off = (tid - 0x80) * 16
        chr_2kb[off : off + 16] = dk_bg_hi[off : off + 16]
    free_ids = iter(tid for tid in range(0x80, 0x100) if tid not in reserved)
    pose_grids: dict[str, list[int]] = {}

    for pose in poses:
        px = _make_big_bad_link_bg(pose, variant)
        # DK $F2D7 draws 4 rows vertically per column (6 columns x 4 rows = 24 tiles)
        grid: list[int] = []
        for col in range(6):
            for row in range(4):
                sub = [px[row * 8 + y][col * 8 : (col + 1) * 8] for y in range(8)]
                enc = encode_tile(sub)
                if enc not in tile_to_id:
                    tid = next(free_ids, None)
                    assert tid is not None, f'Big Bad Link tiles overflowed R4/R5 at pose={pose}'
                    tile_to_id[enc] = tid
                    off = (tid - 0x80) * 16
                    chr_2kb[off : off + 16] = enc
                grid.append(tile_to_id[enc])
        pose_grids[pose] = grid

    return bytes(chr_2kb[:1024]), bytes(chr_2kb[1024:2048]), pose_grids


def build_barba_kong_chr(dk_chr: bytes, z2_bytes: bytes) -> tuple[bytes, dict[str, list[int]]]:
    """Build 32 KB MMC3 CHR-ROM (32 x 1 KB banks) for Barba Kong."""
    assert len(dk_chr) == 8192
    assert z2_bytes[:4] == b'NES\x1a'

    root = Path(__file__).resolve().parent.parent
    barba_art = json.loads((root / 'assets/barba.json').read_text(encoding='utf-8'))
    poses = _make_lil_barba_poses(barba_art)

    # Extract Z2 bank-2 P-Bag ($72-$73), Magic Jar ($8C) for build-time item flavor
    z2_bank2_off = Z2_CHR_OFFSET + 2 * 4096
    z2_pbag_top = decode_tile(z2_bytes[z2_bank2_off + 0x72 * 16 : z2_bank2_off + 0x73 * 16])
    z2_pbag_bot = decode_tile(z2_bytes[z2_bank2_off + 0x73 * 16 : z2_bank2_off + 0x74 * 16])
    z2_jar = decode_tile(z2_bytes[z2_bank2_off + 0x8C * 16 : z2_bank2_off + 0x8D * 16])

    chr32 = bytearray(32 * 1024)

    def write_tile(bank1k: int, idx_in_bank: int, data: bytes) -> None:
        off = bank1k * 1024 + idx_in_bank * 16
        chr32[off : off + 16] = data

    def write_16x16_sprite(bank2k_start: int, base_tile: int, rows: list[str]) -> None:
        tiles = _encode_16x16_dk_order(rows)
        for i, t in enumerate(tiles):
            tid = base_tile + i
            write_tile(bank2k_start + (tid >> 6), tid & 0x3F, t)

    # ------------------------------------------------------------------
    # R0 banks (4 x 2 KB = 1 KB banks 0..7): Lil' Barba + Big Bad Link cutscene sprite
    # ------------------------------------------------------------------
    dk_spr_base = dk_chr[0:2048]
    link_spr_rows = _make_big_bad_link_sprite_32x48()
    link_spr_tiles: list[bytes] = []
    for col in range(4):
        for row in range(6):
            sub = [link_spr_rows[row * 8 + y][col * 8 : (col + 1) * 8] for y in range(8)]
            link_spr_tiles.append(encode_tile(sub))

    for var_idx, bank_start in enumerate((0, 2, 4, 6)):
        chr32[bank_start * 1024 : (bank_start + 2) * 1024] = dk_spr_base
        is_fury = var_idx >= 2
        shimmer = (var_idx & 1) == 1
        stand_pose = poses['fury_swing1' if is_fury else ('walk1' if shimmer else 'stand')]
        walk_a = poses['fury_swing0' if is_fury else 'walk1']
        walk_b = poses['fury_swing1' if is_fury else 'walk2']
        walk_c = poses['fury_swing0' if is_fury else 'walk3']
        jump_pose = poses['jump1' if shimmer else 'jump0']
        swing_pose = poses['fury_swing1' if shimmer else 'fury_swing0']

        sprite_slots = {
            0x00: stand_pose,
            0x04: walk_a,
            0x08: walk_b,
            0x0C: walk_c,
            0x10: poses['climb0'],
            0x14: poses['climb1'],
            0x18: poses['climb_top0'],
            0x1C: poses['climb_top1'],
            0x20: swing_pose,
            0x24: poses['climb_top0'] if shimmer else poses['climb_top1'],
            0x28: jump_pose,
            0x2C: poses['skid'],
            # Ladder-top climb-out and back-facing frames ($60..$6B)
            0x60: poses['climb_top0'],
            0x64: poses['climb_top1'],
            0x68: poses['climb0'],
            # Death spin frames ($6C..$7F)
            0x6C: poses['stand'],
            0x70: poses['front'],
            0x74: _flip_h(poses['stand']),
            0x78: poses['climb0'],
            0x7C: poses['ko'],
        }
        for tid, rows in sprite_slots.items():
            write_16x16_sprite(bank_start, tid, rows)
        # Cutscene / climbing Big Bad Link sprite ($40..$57)
        for i, tbytes in enumerate(link_spr_tiles):
            tid = 0x40 + i
            write_tile(bank_start + (tid >> 6), tid & 0x3F, tbytes)

    # ------------------------------------------------------------------
    # R1 banks (4 x 2 KB = 1 KB banks 8..15): Princess Zelda & Z2 Hazards
    # ------------------------------------------------------------------
    dk_spr_hi = dk_chr[2048:4096]
    for var_idx, bank_start in enumerate((8, 10, 12, 14)):
        chr32[bank_start * 1024 : (bank_start + 2) * 1024] = dk_spr_hi
        haz = _make_hazard_sprites(z2_bytes, var_idx)
        z_top, z_stand, z_wave = _make_zelda_poses(z2_bytes, var_idx)

        def write_hi_16x16(tid: int, rows: list[str]) -> None:
            for i, t in enumerate(_encode_16x16_dk_order(rows)):
                rel = (tid + i) - 0x80
                write_tile(bank_start + (rel >> 6), rel & 0x3F, t)

        # Rolling Z2 Bombs ($80..$8F)
        for idx_rb, rb_rows in enumerate(haz['rolling_bombs']):
            write_hi_16x16(0x80 + idx_rb * 4, rb_rows)
        # Falling Z2 Bombs ($90..$97)
        write_hi_16x16(0x90, haz['bomb0'])
        write_hi_16x16(0x94, haz['bomb1'])
        # Z2 Bits ($98..$9F)
        write_hi_16x16(0x98, haz['bit0'])
        write_hi_16x16(0x9C, haz['bit1'])
        # Title Fireball cursor ($A2)
        write_tile(bank_start, 0xA2 - 0x80, encode_tile(haz['cursor']))
        # Z2 Bubbles ($A8..$AF)
        write_hi_16x16(0xA8, haz['bubble0'])
        write_hi_16x16(0xAC, haz['bubble1'])
        # Z2 Shields ($C0..$C7)
        write_hi_16x16(0xC0, haz['shield0'])
        write_hi_16x16(0xC4, haz['shield1'])
        # Heart / Triforce Heart ($C8..$CB)
        write_hi_16x16(0xC8, haz['heart'])
        # Princess Zelda ($D5..$DE)
        top_t = _encode_16x8_row_major(z_top)
        write_tile(bank_start, 0xD5 - 0x80, top_t[0])
        write_tile(bank_start, 0xD6 - 0x80, top_t[1])
        write_hi_16x16(0xD7, z_wave)
        write_hi_16x16(0xDB, z_stand)
        # Flame / Breath Fury ($F6-$F7 orb, $FA-$FB dragonfire blast)
        write_tile(bank_start + 1, 0xF6 - 0xC0, encode_tile(haz['fury_orb'][:8]))
        write_tile(bank_start + 1, 0xF7 - 0xC0, encode_tile(haz['fury_orb'][8:16]))
        blast_t = _encode_16x8_row_major(haz['blast_core'])
        write_tile(bank_start + 1, 0xFA - 0xC0, blast_t[0])
        write_tile(bank_start + 1, 0xFB - 0xC0, blast_t[1])

    # ------------------------------------------------------------------
    # R2 bank (1 KB bank 16): BG $00-$3F (font, girders, ladders)
    # ------------------------------------------------------------------
    chr32[16 * 1024 : 17 * 1024] = dk_chr[4096 : 4096 + 1024]

    # ------------------------------------------------------------------
    # R3 banks (1 KB banks 17, 18): BG $40-$7F (Cauldron, Stacked Bombs, Title block, Z2 items)
    # ------------------------------------------------------------------
    cauldron_a = [
        '0000000000000000',
        '0001001100100000',
        '0012112211210000',
        '0001222222100000',
        '0111111111111100',
        '0013333333331000',
        '0011111111111000',
        '0012211112211000',
        '0012112211211000',
        '0011122221111000',
        '0011111111111000',
        '0001333333310000',
        '0001111111110000',
        '0011000000011000',
        '0110000000001100',
        '0000000000000000',
    ]
    cauldron_b = _overlay(_flip_h(cauldron_a[:4]) + cauldron_a[4:], ['0' * 16] * 16)
    stacked_bomb = [
        '0000003200000000',
        '0000000300000000',
        '0000011311000000',
        '0001112211100000',
        '0011223211110000',
        '0112221111111000',
        '0112211111111000',
        '0111111111111000',
        '0111111111111000',
        '0111111111111000',
        '0011111111110000',
        '0001111111100000',
        '0000111111000000',
        '0000000000000000',
        '0000000000000000',
        '0000000000000000',
    ]
    # Build Z2-derived Magic Jar (8x16) and Trophy/Key (16x16) from z2.nes tiles
    jar_top = [''.join(str(v) for v in row) for row in z2_jar]
    jar_bot = [
        '0112222110'[1:9],
        '0122322210'[1:9],
        '0122222210'[1:9],
        '0122222210'[1:9],
        '0112222110'[1:9],
        '0011111100'[1:9],
        '0000000000'[1:9],
        '0000000000'[1:9],
    ]
    pbag_8x16 = [
        ''.join(str(v) for v in row) for row in z2_pbag_top
    ] + [
        ''.join(str(v) for v in row) for row in z2_pbag_bot
    ]
    pbag_16x16 = ['0000' + row + '0000' for row in pbag_8x16]

    # Build 24x32 (3 cols x 4 rows = $50-$5B) stack of 4 Zelda Blue Bombs at top-left
    single_bomb_12x16 = [
        '000002300000',
        '000000200000',
        '000122221000',
        '001132111100',
        '011321111110',
        '011211121110',
        '111111232111',
        '111111121111',
        '111111111111',
        '011111111110',
        '011111111110',
        '001111111100',
        '000111111000',
        '000011110000',
        '000000000000',
        '000000000000',
    ]
    bomb_stack_a = [single_bomb_12x16[y] + single_bomb_12x16[y] for y in range(16)] * 2
    bomb_stack_b = [
        (single_bomb_12x16[y][::-1] if y < 2 else single_bomb_12x16[y])
        + (single_bomb_12x16[y][::-1] if y < 2 else single_bomb_12x16[y])
        for y in range(16)
    ] * 2

    for anim, bank1k in enumerate((17, 18)):
        chr32[bank1k * 1024 : (bank1k + 1) * 1024] = dk_chr[4096 + 1024 : 4096 + 2048]
        c_rows = cauldron_a if anim == 0 else cauldron_b
        # $4C-$4F: 2x2 Cauldron in column-major order ($4C TL, $4D BL, $4E TR, $4F BR)
        for i, t in enumerate(_encode_16x16_dk_order(c_rows)):
            write_tile(bank1k, 0x4C - 0x40 + i, t)
        # $50-$5B: 3 cols x 4 rows stacked Z2 Fire-Bombs (V=1 order: col0 50..53, col1 54..57, col2 58..5B)
        sb_grid = bomb_stack_a if anim == 0 else bomb_stack_b
        for col in range(3):
            for row in range(4):
                tid = 0x50 + col * 4 + row
                sub = [sb_grid[row * 8 + y][col * 8 : (col + 1) * 8] for y in range(8)]
                write_tile(bank1k, tid - 0x40, encode_tile(sub))
        # $6E-$6F: Z2 Magic Jar (8x16)
        write_tile(bank1k, 0x6E - 0x40, encode_tile(jar_top))
        write_tile(bank1k, 0x6F - 0x40, encode_tile(jar_bot))
        # $70-$73: Z2 P-Bag (centered 8x16 from $72-$73, $70 TL, $71 BL, $72 TR, $73 BR)
        for i, t in enumerate(_encode_16x16_dk_order(pbag_16x16)):
            write_tile(bank1k, 0x70 - 0x40 + i, t)

    # ------------------------------------------------------------------
    # R4/R5 banks (1 KB banks 20..27): Big Bad Link 4-bank animated poses
    # ------------------------------------------------------------------
    dk_bg_hi = dk_chr[4096 + 2048 : 4096 + 4096]
    pose_grids: dict[str, list[int]] = {}
    for var_idx in range(4):
        r4, r5, grids = _compile_r4_r5_big_bad_link(dk_bg_hi, var_idx)
        b = 20 + var_idx * 2
        chr32[b * 1024 : (b + 1) * 1024] = r4
        chr32[(b + 1) * 1024 : (b + 2) * 1024] = r5
        if var_idx == 0:
            pose_grids = grids

    return bytes(chr32), pose_grids


# ---------------------------------------------------------------------------
# PPU screen & palette packet builder (relocated to PRG Bank 1)
# ---------------------------------------------------------------------------

def _decode_ppu_packets(prg: bytes, addr: int) -> list[tuple[int, bool, bool, bytes]]:
    p = addr - 0xC000
    packets: list[tuple[int, bool, bool, bytes]] = []
    while prg[p] != 0:
        hi, lo, ctrl = prg[p], prg[p + 1], prg[p + 2]
        ppu = (hi << 8) | lo
        is_vert = bool(ctrl & 0x80)
        is_rle = bool(ctrl & 0x40)
        cnt = ctrl & 0x3F
        p += 3
        if is_rle:
            data = bytes([prg[p]]) * cnt
            p += 1
        else:
            data = bytes(prg[p : p + cnt])
            p += cnt
        packets.append((ppu, is_vert, is_rle, data))
    return packets


def _encode_ppu_packets(packets: list[tuple[int, bool, bool, bytes]]) -> bytes:
    out = bytearray()
    for ppu, is_vert, is_rle, data in packets:
        cnt = len(data)
        assert 1 <= cnt <= 63
        ctrl = cnt | (0x80 if is_vert else 0) | (0x40 if is_rle else 0)
        out.extend(((ppu >> 8) & 0xFF, ppu & 0xFF, ctrl))
        if is_rle:
            assert len(set(data)) == 1
            out.append(data[0])
        else:
            out.extend(data)
    out.append(0x00)
    return bytes(out)


def _encode_dk_text(s: str) -> bytes:
    out = bytearray()
    for ch in s:
        if '0' <= ch <= '9':
            out.append(ord(ch) - ord('0'))
        elif 'A' <= ch <= 'Z':
            out.append(ord(ch) - ord('A') + 0x0A)
        elif ch == ' ':
            out.append(0x24)
        elif ch == '.':
            out.append(0xD3)
        elif ch == '-':
            out.append(0x28)
        elif ch == '!':
            out.append(0x2E)
        else:
            out.append(0x24)
    return bytes(out)


def _make_barba_kong_title_packet() -> bytes:
    """Build custom 'BARBA KONG' title screen PPU packet."""
    # Palettes:
    # BG0: vanilla DK blue girders ($0F, $2C, $38, $12)
    # BG1: vanilla DK gold menu options ($0F, $27, $27, $27)
    # BG2: vanilla DK white footer ($0F, $30, $30, $30)
    # BG3: $0F, $00, $04, $2C
    # SPR0: Lil' Barba fireball cursor ($0F, $16, $27, $30)
    pal = bytes.fromhex(
        '0f 2c 38 12 '
        '0f 27 27 27 '
        '0f 30 30 30 '
        '0f 00 04 2c '
        '0f 16 27 30 '
        '0f 25 36 27 '
        '0f 16 30 37 '
        '0f 16 27 30'
    )
    packets: list[tuple[int, bool, bool, bytes]] = [
        (0x3F00, False, False, pal),
        (0x23E0, False, True, bytes([0x55]) * 16),
        (0x23F0, False, True, bytes([0xAA]) * 8),
    ]

    # Girder letterforms matching vanilla DK's KONG proportions (K, O, N, G)
    glyphs = {
        'B': ['###.', '#..#', '###.', '#..#', '###.'],
        'A': ['.##.', '#..#', '####', '#..#', '#..#'],
        'R': ['###.', '#..#', '###.', '#.#.', '#..#'],
        'K': ['#..#', '###.', '##..', '#.#.', '#..#'],
        'O': ['###', '#.#', '#.#', '#.#', '###'],
        'N': ['#..#', '##.#', '#.##', '#..#', '#..#'],
        'G': ['####', '#...', '#.##', '#..#', '####'],
    }

    def add_word(word: str, start_row: int, start_col: int) -> None:
        for r in range(5):
            row_tiles: list[int] = []
            for idx_ch, ch in enumerate(word):
                for cell in glyphs[ch][r]:
                    row_tiles.append(0x62 if cell == '#' else 0x24)
                if idx_ch + 1 < len(word):
                    row_tiles.append(0x24)
            ppu_addr = 0x2000 + (start_row + r) * 32 + start_col
            packets.append((ppu_addr, False, False, bytes(row_tiles)))

    add_word('BARBA', 4, 4)
    add_word('KONG', 10, 7)

    # Menu options matching DK's $C91E / $C95D / $C98A cursor Y positions
    for idx, label in enumerate((
        '1 PLAYER GAME A',
        '1 PLAYER GAME B',
        '2 PLAYER GAME A',
        '2 PLAYER GAME B',
    )):
        ppu_addr = 0x2209 + idx * 0x40
        packets.append((ppu_addr, False, False, _encode_dk_text(label)))

    # Vanilla Donkey Kong copyright footer
    packets.append((0x2305, False, False, bytes.fromhex('d301090801241712171d0e170d18240c1865151d0d64')))
    packets.append((0x234B, False, False, bytes.fromhex('160a0d0e24121724130a190a17')))

    return _encode_ppu_packets(packets)


def _upgrade_stage_ppu_packet(orig_prg: bytes, addr: int, stage: str) -> bytes:
    """Upgrade 25m / 75m / 100m PPU packet with Barba Kong / Big Bad Link / Zelda palettes."""
    packets = _decode_ppu_packets(orig_prg, addr)
    # Full 32-byte palette per stage so Big Bad Link (BG2), Lil' Barba (SPR0),
    # Princess Zelda (SPR1), Fireballs/Bits/Bubbles (SPR2), Flame Fury/Shields (SPR3)
    # always have exact colors regardless of entry order!
    palettes = {
        '25m': bytes.fromhex(
            '0f 15 2c 12 '  # BG0: pink girders, cyan ladders
            '0f 12 21 30 '  # BG1: stacked Zelda Blue Bombs (cobalt/sky-blue/white)
            '0f 2a 36 17 '  # BG2: Big Bad Link (green tunic, peach skin, brown hair/boots)
            '0f 30 36 06 '  # BG3: HUD text
            '0f 16 27 30 '  # SPR0: Lil' Barba
            '0f 25 36 27 '  # SPR1: Princess Zelda
            '0f 12 21 30 '  # SPR2: Zelda Blue Bombs / Z2 Bits
            '0f 16 27 30'   # SPR3: Flame Fury
        ),
        '75m': bytes.fromhex(
            '0f 15 27 02 '  # BG0: pink girders, gold ladders
            '0f 16 27 30 '  # BG1: Z2 Magic Jar / Trophy
            '0f 2a 36 17 '  # BG2: Big Bad Link
            '0f 30 2c 24 '  # BG3: HUD text
            '0f 16 27 30 '  # SPR0: Lil' Barba
            '0f 25 36 27 '  # SPR1: Princess Zelda
            '0f 16 30 37 '  # SPR2: Z2 Bits / Fireballs
            '0f 16 27 30'   # SPR3: Z2 Shields & Elevators
        ),
        '100m': bytes.fromhex(
            '0f 2c 27 02 '  # BG0: cyan girders, gold ladders & rivets
            '0f 16 27 30 '  # BG1: Z2 Magic Jar / Trophy / Cauldron
            '0f 2a 36 17 '  # BG2: Big Bad Link
            '0f 30 2c 24 '  # BG3: HUD text
            '0f 16 27 30 '  # SPR0: Lil' Barba
            '0f 25 36 27 '  # SPR1: Princess Zelda
            '0f 16 30 37 '  # SPR2: Z2 Bubbles & Fireballs
            '0f 16 27 30'   # SPR3: Flame Fury
        ),
    }
    # Replace initial $3F00 palette packet(s) with full 32-byte Barba Kong palette
    filtered = [p for p in packets if p[0] not in (0x3F00, 0x3F1D)]
    return _encode_ppu_packets([(0x3F00, False, False, palettes[stage])] + filtered)


# ---------------------------------------------------------------------------
# Relocated DK engine ($F1B4-$F55A -> $8000) & PRG Bank 1 Barba Kong code
# ---------------------------------------------------------------------------

def _relocate_f1b4_f55a(orig_prg: bytes) -> bytes:
    """Relocate DK routines $F1B4..$F55A to $8000..$83A6 in PRG Bank 1."""
    buf = bytearray(orig_prg[DK_RELOC_ORIG_START - 0xC000 : DK_RELOC_ORIG_END - 0xC000])
    # Exact internal JSR/JMP instructions within $F1B4..$F55A targeting $F1B4..$F55A
    internal_fixups = (
        0xF244, 0xF25C, 0xF266, 0xF27A, 0xF2EF, 0xF2F7, 0xF303, 0xF310,
        0xF35B, 0xF372, 0xF37D, 0xF388, 0xF399, 0xF3A4, 0xF3AF, 0xF3CF,
        0xF3D6, 0xF3DD, 0xF3E3, 0xF404, 0xF45B, 0xF465, 0xF46F, 0xF4CA,
        0xF4D2, 0xF4DA, 0xF4E1, 0xF51A, 0xF51E,
    )
    for addr in internal_fixups:
        off = addr - DK_RELOC_ORIG_START
        assert buf[off] in (0x20, 0x4C), f'Expected JSR/JMP at ${addr:04X}'
        tgt = buf[off + 1] | (buf[off + 2] << 8)
        assert DK_RELOC_ORIG_START <= tgt < DK_RELOC_ORIG_END
        new_tgt = _reloc_addr(tgt)
        buf[off + 1] = new_tgt & 0xFF
        buf[off + 2] = (new_tgt >> 8) & 0xFF
    return bytes(buf)


def _assemble_bank1(
    orig_prg: bytes,
    roar_info: dict,
    roar_dmc_len: int,
) -> tuple[bytes, dict[str, int]]:
    """Build 8 KB PRG Bank 1 ($8000-$9FFF): relocated DK core, MMC3 anim, roar, screens."""
    bank1 = bytearray(b'\xFF' * 8192)
    reloc_code = _relocate_f1b4_f55a(orig_prg)
    assert len(reloc_code) == DK_RELOC_ORIG_END - DK_RELOC_ORIG_START
    bank1[0 : len(reloc_code)] = reloc_code

    a = Asm6502(DK_BANK1_CODE_BASE)
    rate_idx = roar_info['rate_index'] & 0x0F
    dmc_reg = (ROAR_DMC_ADDR - 0xC000) >> 6
    len_reg = (roar_dmc_len - 1) >> 4
    roar_frames = min(255, roar_info['timer_frames'])

    # TriggerBarbaRoar: plays sampled roar.dmc from fixed bank $F1C0
    a.label('TriggerBarbaRoar')
    a.emit(0x48)                                                # PHA
    a.emit(0xA9, 0x0F, 0x8D, 0x15, 0x40)                        # stop prior DMC
    a.emit(0xA9, rate_idx, 0x8D, 0x10, 0x40)                    # $4010 = rate
    a.emit(0xA9, 0x40, 0x8D, 0x11, 0x40)                        # $4011 = $40 midpoint
    a.emit(0xA9, dmc_reg, 0x8D, 0x12, 0x40)                     # $4012 = addr reg
    a.emit(0xA9, len_reg, 0x8D, 0x13, 0x40)                     # $4013 = length reg
    a.emit(0xA9, 0x1F, 0x8D, 0x15, 0x40)                        # $4015 = enable DMC + channels
    a.emit(0xA9, roar_frames, 0x8D, DK_ROAR_TIMER & 0xFF, DK_ROAR_TIMER >> 8)
    a.emit(0xEE, DK_ROAR_COUNT & 0xFF, DK_ROAR_COUNT >> 8)      # INC DK_ROAR_COUNT
    a.emit(0x68, 0x60)                                          # PLA; RTS

    # BarbaKongTitleStart ($C98A): STA $0514; JMP TriggerBarbaRoar
    a.label('BarbaKongTitleStart')
    a.emit(0x8D, 0x14, 0x05)
    a.abs_ref(0x4C, 'TriggerBarbaRoar')

    # BarbaKongEnableApu ($C90C / $CA1D): keep DMC bit 4 live if DK_ROAR_TIMER != 0
    a.label('BarbaKongEnableApu')
    a.emit(0xAD, DK_ROAR_TIMER & 0xFF, DK_ROAR_TIMER >> 8)
    a.branch(0xF0, 'apu_no_dmc')
    a.emit(0xA9, 0x1F, 0x8D, 0x15, 0x40, 0x60)
    a.label('apu_no_dmc')
    a.emit(0xA9, 0x0F, 0x8D, 0x15, 0x40, 0x60)

    # BarbaKongPickupFury ($D88F): LDA $FC; STA $0519; clear fireball slots; JMP TriggerBarbaRoar
    a.label('BarbaKongPickupFury')
    a.emit(0xA5, 0xFC, 0x8D, 0x19, 0x05)
    a.emit(0xA9, 0x00)
    a.emit(0x8D, DK_FB0_TIMER & 0xFF, DK_FB0_TIMER >> 8)
    a.emit(0x8D, DK_FB1_TIMER & 0xFF, DK_FB1_TIMER >> 8)
    a.emit(0x8D, DK_FB_COOLDOWN & 0xFF, DK_FB_COOLDOWN >> 8)
    a.abs_ref(0x4C, 'TriggerBarbaRoar')

    # BarbaKongFireballUpdate ($D75B): shoot fireballs randomly in the hammer arc while $A0 != 0
    a.label('BarbaKongFireballUpdate')
    a.emit(0xAD, DK_FB_COOLDOWN & 0xFF, DK_FB_COOLDOWN >> 8)
    a.branch(0xF0, 'fb_try_spawn')
    a.emit(0xCE, DK_FB_COOLDOWN & 0xFF, DK_FB_COOLDOWN >> 8)
    a.abs_ref(0x4C, 'fb_update_slots')

    a.label('fb_try_spawn')
    a.emit(0xA2, 0x00)
    a.emit(0xAD, DK_FB0_TIMER & 0xFF, DK_FB0_TIMER >> 8)
    a.branch(0xF0, 'fb_spawn_slot')
    a.emit(0xA2, 0x05)
    a.emit(0xAD, DK_FB1_TIMER & 0xFF, DK_FB1_TIMER >> 8)
    a.branch(0xD0, 'fb_update_slots')

    a.label('fb_spawn_slot')
    a.emit(0xA9, 0x09, 0x8D, DK_FB_COOLDOWN & 0xFF, DK_FB_COOLDOWN >> 8)
    a.emit(0xA9, 0x1A, 0x9D, DK_FB0_TIMER & 0xFF, DK_FB0_TIMER >> 8)
    a.emit(0xA5, 0x18)                                       # LDA $18 (DK RNG)
    a.emit(0x4D, DK_ANIM_FRAME & 0xFF, DK_ANIM_FRAME >> 8)   # EOR DK_ANIM_FRAME
    a.emit(0x29, 0x0F, 0xA8)                                 # TAY (0..15 across 180-deg forward cone)
    a.abs_ref(0xB9, 'fb_dy_tbl')
    a.emit(0x18, 0x6D, 0x00, 0x02)                           # ADC BarbaY (head-to-feet body emit)
    a.emit(0x9D, DK_FB0_Y & 0xFF, DK_FB0_Y >> 8)
    a.emit(0xA5, 0x57, 0xC9, 0x01)
    a.branch(0xF0, 'fb_face_right')
    a.emit(0xAD, 0x03, 0x02, 0x18, 0x69, 0x04)               # center X = BarbaX + 4
    a.emit(0x38)
    a.abs_ref(0xF9, 'fb_dx_tbl')                             # SBC fb_dx_tbl,Y (project left)
    a.branch(0x90, 'fb_store_x')
    a.branch(0xB0, 'fb_store_x')
    a.label('fb_face_right')
    a.emit(0xAD, 0x03, 0x02, 0x18, 0x69, 0x04)               # center X = BarbaX + 4
    a.emit(0x18)
    a.abs_ref(0x79, 'fb_dx_tbl')                             # ADC fb_dx_tbl,Y (project right)
    a.label('fb_store_x')
    a.emit(0x9D, DK_FB0_X & 0xFF, DK_FB0_X >> 8)
    a.abs_ref(0xB9, 'fb_vy_tbl')
    a.emit(0x9D, DK_FB0_VY & 0xFF, DK_FB0_VY >> 8)
    a.abs_ref(0xB9, 'fb_vx_tbl')
    a.emit(0xA4, 0x57, 0xC0, 0x01)
    a.branch(0xF0, 'fb_store_vx')
    a.emit(0x49, 0xFF, 0x18, 0x69, 0x01)                     # negate vx when facing left (0 stays 0)
    a.label('fb_store_vx')
    a.emit(0x9D, DK_FB0_VX & 0xFF, DK_FB0_VX >> 8)

    a.label('fb_update_slots')
    a.emit(0xA2, 0xD0)                                       # OAM base $D0 when $A0 == 1
    a.emit(0xA5, 0xA0, 0xC9, 0x01)
    a.branch(0xF0, 'fb_oam_ok')
    a.emit(0xA2, 0xD8)                                       # OAM base $D8 when $A0 == 2
    a.label('fb_oam_ok')
    a.emit(0xA0, 0x00)
    a.abs_ref(0x20, 'fb_step_one')
    a.emit(0xE8, 0xE8, 0xE8, 0xE8)
    a.emit(0xA0, 0x05)
    a.abs_ref(0x4C, 'fb_step_one')

    a.label('fb_step_one')
    a.emit(0xB9, DK_FB0_TIMER & 0xFF, DK_FB0_TIMER >> 8)
    a.branch(0xD0, 'fb_active')
    a.emit(0xA9, 0xFF, 0x9D, 0x00, 0x02, 0x60)               # hide inactive OAM slot
    a.label('fb_active')
    a.emit(0x38, 0xE9, 0x01, 0x99, DK_FB0_TIMER & 0xFF, DK_FB0_TIMER >> 8)
    a.emit(0xB9, DK_FB0_X & 0xFF, DK_FB0_X >> 8)
    a.emit(0x18, 0x79, DK_FB0_VX & 0xFF, DK_FB0_VX >> 8)
    a.emit(0x99, DK_FB0_X & 0xFF, DK_FB0_X >> 8)
    a.emit(0xC9, 0x08)
    a.branch(0x90, 'fb_kill')
    a.emit(0xC9, 0xF8)
    a.branch(0xB0, 'fb_kill')
    a.emit(0xB9, DK_FB0_Y & 0xFF, DK_FB0_Y >> 8)
    a.emit(0x18, 0x79, DK_FB0_VY & 0xFF, DK_FB0_VY >> 8)
    a.emit(0x99, DK_FB0_Y & 0xFF, DK_FB0_Y >> 8)
    a.emit(0xC9, 0x18)
    a.branch(0x90, 'fb_kill')
    a.emit(0xC9, 0xE8)
    a.branch(0xB0, 'fb_kill')
    a.emit(0x9D, 0x00, 0x02)                                 # OAM Y
    a.emit(0xB9, DK_FB0_X & 0xFF, DK_FB0_X >> 8)
    a.emit(0x9D, 0x03, 0x02)                                 # OAM X
    a.emit(0xA9, 0xA2, 0x9D, 0x01, 0x02)                     # OAM Tile = $A2 (animated fireball)
    a.emit(0xA9, 0x03)                                       # SPR3 fiery palette
    a.emit(0xA4, 0x57, 0xC0, 0x01)
    a.branch(0xF0, 'fb_attr_ok')
    a.emit(0x09, 0x40)                                       # H-flip when facing left
    a.label('fb_attr_ok')
    a.emit(0x9D, 0x02, 0x02, 0x60)                           # OAM Attr; RTS

    a.label('fb_kill')
    a.emit(0xA9, 0x00, 0x99, DK_FB0_TIMER & 0xFF, DK_FB0_TIMER >> 8)
    a.emit(0xA9, 0xFF, 0x9D, 0x00, 0x02, 0x60)

    # 16-entry 180-deg forward cone (-90 deg straight up through 0 deg forward to +90 deg straight down)
    a.label('fb_vx_tbl')
    a.emit(0x00, 0x01, 0x01, 0x02, 0x03, 0x02, 0x03, 0x03, 0x03, 0x03, 0x02, 0x03, 0x02, 0x01, 0x01, 0x00)
    a.label('fb_vy_tbl')
    a.emit(0xFD, 0xFD, 0xFE, 0xFE, 0xFE, 0xFF, 0xFF, 0x00, 0x00, 0x01, 0x01, 0x02, 0x02, 0x02, 0x03, 0x03)
    a.label('fb_dx_tbl')
    a.emit(0x00, 0x02, 0x03, 0x04, 0x05, 0x05, 0x06, 0x06, 0x06, 0x06, 0x05, 0x05, 0x04, 0x03, 0x02, 0x00)
    a.label('fb_dy_tbl')
    a.emit(0xFE, 0xFF, 0x00, 0x01, 0x02, 0x03, 0x04, 0x04, 0x05, 0x06, 0x07, 0x08, 0x08, 0x09, 0x09, 0x0A)

    # BarbaKongFireballHit ($ECBF): test active fireballs against DK enemies/barrels
    a.label('BarbaKongFireballHit')
    a.emit(0xA5, 0xA0)
    a.branch(0xF0, 'fb_hit_none')
    a.emit(0xAD, DK_FB0_TIMER & 0xFF, DK_FB0_TIMER >> 8)
    a.branch(0xF0, 'fb_hit_check1')
    a.emit(0xAD, DK_FB0_X & 0xFF, DK_FB0_X >> 8, 0x85, 0x00)
    a.emit(0xAD, DK_FB0_Y & 0xFF, DK_FB0_Y >> 8, 0x85, 0x01)
    a.abs_ref(0x20, 'fb_hit_test')
    a.emit(0xA5, 0xBF)
    a.branch(0xF0, 'fb_hit_check1')
    a.emit(0xA9, 0x00, 0x8D, DK_FB0_TIMER & 0xFF, DK_FB0_TIMER >> 8, 0x60)

    a.label('fb_hit_check1')
    a.emit(0xAD, DK_FB1_TIMER & 0xFF, DK_FB1_TIMER >> 8)
    a.branch(0xF0, 'fb_hit_none')
    a.emit(0xAD, DK_FB1_X & 0xFF, DK_FB1_X >> 8, 0x85, 0x00)
    a.emit(0xAD, DK_FB1_Y & 0xFF, DK_FB1_Y >> 8, 0x85, 0x01)
    a.abs_ref(0x20, 'fb_hit_test')
    a.emit(0xA5, 0xBF)
    a.branch(0xF0, 'fb_hit_none')
    a.emit(0xA9, 0x00, 0x8D, DK_FB1_TIMER & 0xFF, DK_FB1_TIMER >> 8, 0x60)

    a.label('fb_hit_none')
    a.emit(0x4C, 0x87, 0xED)                                 # JMP $ED87 (no hit)

    # fb_hit_test: call vanilla $ED07; on Stage 2 ($53==3) also check bombs in slots 6..8 ($90..$B0)
    a.label('fb_hit_test')
    a.emit(0x20, 0x07, 0xED)                                 # JSR $ED07
    a.emit(0xA5, 0xBF)
    a.branch(0xD0, 'fb_test_done')
    a.emit(0xA5, 0x53, 0xC9, 0x03)
    a.branch(0xD0, 'fb_test_done')
    a.emit(0xA9, 0x06, 0x85, 0x5D)                           # LDA #$06; STA $5D
    a.label('fb_s2_loop')
    a.emit(0x20, 0xD5, 0xEF, 0x86, 0x04)                     # JSR $EFD5; STX $04
    a.emit(0x20, 0xEC, 0xEA)                                 # JSR $EAEC
    a.emit(0xA9, 0x3A, 0x20, 0x47, 0xC8)                     # LDA #$3A; JSR $C847
    a.emit(0x20, 0xEF, 0xEF)                                 # JSR $EFEF
    a.branch(0xD0, 'fb_s2_hit')
    a.emit(0xE6, 0x5D, 0xA5, 0x5D, 0xC9, 0x09)
    a.branch(0xD0, 'fb_s2_loop')
    a.label('fb_test_done')
    a.emit(0x60)
    a.label('fb_s2_hit')
    a.emit(0x20, 0xD1, 0xEA, 0x20, 0x94, 0xF0)               # JSR $EAD1; JSR $F094
    a.emit(0xA6, 0x5D, 0xA9, 0x00, 0x95, 0x5E)               # LDX $5D; LDA #0; STA $5E,X
    a.emit(0xA9, 0x01, 0x85, 0xBF, 0x60)                     # LDA #1; STA $BF; RTS

    # BarbaKongSpringSpawn ($EA34): Stage 2 Z2 Shield spawner using DK_SPRING_TIMER
    a.label('BarbaKongSpringSpawn')
    a.emit(0xAD, DK_SPRING_TIMER & 0xFF, DK_SPRING_TIMER >> 8)
    a.branch(0xD0, 'spring_spawn_done')
    a.emit(0xA5, 0x19, 0x29, 0x03, 0xAA)                     # LDA $19; AND #$03; TAX
    a.emit(0xBD, 0xFF, 0xC1, 0x18, 0x69, 0x10)               # LDA $C1FF,X; CLC; ADC #$10
    a.emit(0xAE, 0x45, 0x04, 0x9D, 0x46, 0x04)               # LDX $0445; STA $0446,X
    a.emit(0x85, 0x00, 0xA9, 0x30, 0x85, 0x01)               # STA $00; LDA #$30; STA $01
    a.emit(0xA9, 0xC4, 0x85, 0x02)                           # LDA #$C4; STA $02
    a.emit(0x20, 0xDB, 0xEA, 0x20, 0xF7, 0xEA)               # JSR $EADB; JSR $EAF7
    a.emit(0xBD, 0x57, 0xC4)                                 # LDA $C457,X
    a.emit(0x8D, DK_SPRING_TIMER & 0xFF, DK_SPRING_TIMER >> 8)
    a.label('spring_spawn_done')
    a.emit(0x60)

    # BarbaKongStage2Hook ($CF07): run vanilla collision ($EC29), tick spring timer, & run Link's bombs
    a.label('BarbaKongStage2Hook')
    a.emit(0x20, 0x29, 0xEC)                                 # JSR $EC29
    a.emit(0xAD, DK_SPRING_TIMER & 0xFF, DK_SPRING_TIMER >> 8)
    a.branch(0xF0, 's2_bombs_start')
    a.emit(0xCE, DK_SPRING_TIMER & 0xFF, DK_SPRING_TIMER >> 8)
    a.label('s2_bombs_start')
    a.emit(0xA9, 0x06, 0x85, 0x5D)                           # LDA #$06; STA $5D (OAM $90, $A0, $B0)
    a.label('s2_bomb_loop')
    a.emit(0x20, 0xD5, 0xEF)                                 # JSR $EFD5
    a.emit(0xBD, 0x00, 0x02, 0xC9, 0xFF)                     # LDA $0200,X; CMP #$FF
    a.branch(0xD0, 's2_bomb_active')
    a.emit(0xA5, 0x36)                                       # LDA $36
    a.branch(0xD0, 's2_bomb_next')
    a.emit(0xA9, 0x80, 0xA6, 0x5D, 0x95, 0x5E)               # LDA #$80; LDX $5D; STA $5E,X
    a.emit(0xA9, 0x10, 0x85, 0x37)                           # LDA #$10; STA $37
    a.emit(0x20, 0xF7, 0xEA, 0xBD, 0x43, 0xC4, 0x85, 0x36)   # JSR $EAF7; LDA $C443,X; STA $36
    a.abs_ref(0x4C, 's2_bomb_active')                        # Draw initial grab frame immediately
    a.label('s2_bomb_next')
    a.emit(0xE6, 0x5D, 0xA5, 0x5D, 0xC9, 0x09)               # INC $5D; LDA $5D; CMP #$09
    a.branch(0xD0, 's2_bomb_loop')
    # Check player collision against Stage 2 bombs ($90, $A0, $B0)
    a.emit(0xA9, 0x06, 0x85, 0x5D)
    a.label('s2_col_loop')
    a.emit(0x20, 0xD5, 0xEF, 0x20, 0xEC, 0xEA)               # JSR $EFD5; JSR $EAEC
    a.emit(0xA9, 0x3A, 0x20, 0x47, 0xC8, 0x20, 0xEF, 0xEF)   # LDA #$3A; JSR $C847; JSR $EFEF
    a.branch(0xD0, 's2_col_hit')
    a.emit(0xE6, 0x5D, 0xA5, 0x5D, 0xC9, 0x09)
    a.branch(0xD0, 's2_col_loop')
    a.emit(0x60)
    a.label('s2_col_hit')
    a.emit(0x20, 0x51, 0xEF, 0xA9, 0xFF, 0x85, 0x96, 0x60)   # JSR $EF51; LDA #$FF; STA $96; RTS

    a.label('s2_bomb_active')
    a.emit(0xA6, 0x5D, 0xB5, 0x5E)                           # LDX $5D; LDA $5E,X
    a.emit(0xC9, 0x80)
    a.branch(0xD0, 's2_not_80')
    a.emit(0x20, 0x9C, 0xDA)                                 # JSR $DA9C (grab)
    a.abs_ref(0x4C, 's2_bomb_next')
    a.label('s2_not_80')
    a.emit(0xC9, 0x81)
    a.branch(0xD0, 's2_not_81')
    a.emit(0x20, 0x00, 0xDB)                                 # JSR $DB00 (throw)
    a.abs_ref(0x4C, 's2_bomb_next')
    a.label('s2_not_81')
    a.emit(0xC9, 0x01)
    a.branch(0xD0, 's2_not_01')
    # Rolling ($01): top girder rolls right to X=$B8 then falls; bottom girder rolls left to X=$12 then despawns
    a.emit(0x20, 0xD5, 0xEF, 0x86, 0x04, 0x20, 0xEC, 0xEA)   # JSR $EFD5; STX $04; JSR $EAEC
    a.emit(0xA5, 0x01, 0xC9, 0x80)
    a.branch(0xB0, 's2_bot_girder')
    a.emit(0xE6, 0x00, 0xA5, 0x00, 0xC9, 0xB8)               # INC $00; LDA $00; CMP #$B8
    a.branch(0x90, 's2_draw_bomb')
    a.emit(0xA6, 0x5D, 0xA9, 0x08, 0x95, 0x5E)               # LDX $5D; LDA #$08; STA $5E,X
    a.abs_ref(0x4C, 's2_draw_bomb')
    a.label('s2_bot_girder')
    a.emit(0xC6, 0x00, 0xA5, 0x00, 0xC9, 0x12)               # DEC $00; LDA $00; CMP #$12
    a.branch(0xB0, 's2_draw_bomb')
    a.emit(0x20, 0xD1, 0xEA, 0xA6, 0x5D, 0xA9, 0x00, 0x95, 0x5E)  # JSR $EAD1; LDX $5D; LDA #0; STA $5E,X
    a.abs_ref(0x4C, 's2_bomb_next')

    a.label('s2_not_01')
    a.emit(0xC9, 0x08)
    a.branch(0xD0, 's2_bomb_next_tramp')
    # Falling ($08): fall down until Y=$CA, then roll left on bottom girder
    a.emit(0x20, 0xD5, 0xEF, 0x86, 0x04, 0x20, 0xEC, 0xEA)
    a.emit(0xE6, 0x01, 0xA5, 0x01, 0xC9, 0xCA)               # INC $01; LDA $01; CMP #$CA
    a.branch(0x90, 's2_draw_bomb')
    a.emit(0xA9, 0xCA, 0x85, 0x01)                           # LDA #$CA; STA $01
    a.emit(0xA6, 0x5D, 0xA9, 0x01, 0x95, 0x5E)               # LDX $5D; LDA #$01; STA $5E,X

    a.label('s2_draw_bomb')
    a.emit(0x20, 0xEE, 0xDB)                                 # JSR $DBEE (spin bomb)
    a.emit(0xA6, 0x5D, 0xB5, 0x72, 0x85, 0x02)               # LDX $5D; LDA $72,X; STA $02
    a.emit(0x20, 0xDB, 0xEA)                                 # JSR $EADB
    a.emit(0xA6, 0x04, 0xA9, 0x02, 0x20, 0x6C, 0xEE)         # LDX $04; LDA #2; JSR $EE6C
    a.label('s2_bomb_next_tramp')
    a.abs_ref(0x4C, 's2_bomb_next')

    # BarbaKongStageClear ($D086): LDA #$00; STA $FC; LDA #$01; STA $9A; JMP TriggerBarbaRoar
    a.label('BarbaKongStageClear')
    a.emit(0xA9, 0x00, 0x85, 0xFC, 0xA9, 0x01, 0x85, 0x9A)
    a.abs_ref(0x4C, 'TriggerBarbaRoar')

    # BarbaKongRescueRoar ($CE2F): LDA #$04; STA $FD; JMP TriggerBarbaRoar
    a.label('BarbaKongRescueRoar')
    a.emit(0xA9, 0x04, 0x85, 0xFD)
    a.abs_ref(0x4C, 'TriggerBarbaRoar')

    # BarbaKongNmiEnd ($C8E8): update MMC3 R0-R5 animations, tick roar timer, re-enable NMI, RTI
    a.label('BarbaKongNmiEnd')
    a.emit(0x8A, 0x48, 0x98, 0x48)                              # TXA; PHA; TYA; PHA (DK NMI only pushed A)
    a.emit(0xEE, DK_ANIM_FRAME & 0xFF, DK_ANIM_FRAME >> 8)      # INC DK_ANIM_FRAME
    a.emit(0xAD, DK_ANIM_FRAME & 0xFF, DK_ANIM_FRAME >> 8)
    a.emit(0x4A, 0x4A, 0x4A, 0x29, 0x03, 0xAA)                  # X = anim_2bit (0..3)

    # R0 ($0000-$07FF): Lil' Barba (0/2 normal, 4/6 Flame Fury when $A0 != 0)
    a.emit(0x8A, 0x29, 0x01, 0x0A)                              # A = (X & 1) * 2
    a.emit(0xA4, 0xA0)                                          # LDY $A0 (Flame Fury active?)
    a.branch(0xF0, 'r0_normal')
    a.emit(0x09, 0x04)                                          # ORA #$04
    a.label('r0_normal')
    a.emit(0xA0, 0x00, 0x8C, 0x00, 0x80)                        # R0 select
    a.emit(0x8D, 0x01, 0x80)                                    # R0 = A
    a.emit(0x8D, DK_CHR_BANK_R0 & 0xFF, DK_CHR_BANK_R0 >> 8)

    # R1 ($0800-$0FFF): Zelda & Hazards (8, 10, 12, 14)
    a.emit(0x8A, 0x0A, 0x18, 0x69, 0x08)                        # A = 8 + X * 2
    a.emit(0xA0, 0x01, 0x8C, 0x00, 0x80)                        # R1 select
    a.emit(0x8D, 0x01, 0x80)
    a.emit(0x8D, DK_CHR_BANK_R1 & 0xFF, DK_CHR_BANK_R1 >> 8)

    # R3 ($1400-$17FF): Lava Cauldron / Stacked Bombs (17 or 18)
    a.emit(0x8A, 0x29, 0x01, 0x18, 0x69, 0x11)                  # A = 17 + (X & 1)
    a.emit(0xA0, 0x03, 0x8C, 0x00, 0x80, 0x8D, 0x01, 0x80)

    # R4 & R5 ($1800-$1FFF): Big Bad Link (20/21, 22/23, 24/25, 26/27)
    a.emit(0x8A, 0x0A, 0x18, 0x69, 0x14)                        # A = 20 + X * 2
    a.emit(0xA0, 0x04, 0x8C, 0x00, 0x80, 0x8D, 0x01, 0x80)
    a.emit(0x8D, DK_CHR_BANK_R4 & 0xFF, DK_CHR_BANK_R4 >> 8)
    a.emit(0x18, 0x69, 0x01)                                    # A = R4 + 1
    a.emit(0xA0, 0x05, 0x8C, 0x00, 0x80, 0x8D, 0x01, 0x80)

    # Tick DK_ROAR_TIMER
    a.emit(0xAD, DK_ROAR_TIMER & 0xFF, DK_ROAR_TIMER >> 8)
    a.branch(0xF0, 'roar_done')
    a.emit(0xCE, DK_ROAR_TIMER & 0xFF, DK_ROAR_TIMER >> 8)
    a.label('roar_done')

    # Force all bomb OAM slots ($80..$97) to SPR2 (Zelda Blue) after VBlank PPU writes
    a.emit(0xA2, 0x30)                                          # LDX #$30
    a.label('bomb_pal_loop')
    a.emit(0xBD, 0x01, 0x02, 0xC9, 0x80)                        # LDA $0201,X; CMP #$80
    a.branch(0x90, 'bomb_pal_next')
    a.emit(0xC9, 0x98)                                          # CMP #$98
    a.branch(0xB0, 'bomb_pal_next')
    a.emit(0xBD, 0x02, 0x02, 0x29, 0xFC, 0x09, 0x02)            # LDA $0202,X; AND #$FC; ORA #$02
    a.emit(0x9D, 0x02, 0x02)                                    # STA $0202,X
    a.label('bomb_pal_next')
    a.emit(0xE8, 0xE8, 0xE8, 0xE8)                              # INX x4
    a.branch(0xD0, 'bomb_pal_loop')

    # Finish DK NMI ($C8E8..$C8F2)
    a.emit(0x68, 0xA8, 0x68, 0xAA)                              # PLA; TAY; PLA; TAX
    a.emit(0xA5, 0x10, 0x49, 0x80, 0x8D, 0x00, 0x20, 0x85, 0x10)
    a.emit(0x68, 0x40)                                          # PLA; RTI

    code = a.finish()
    code_off = DK_BANK1_CODE_BASE - 0x8000
    assert code_off + len(code) <= 0x800
    bank1[code_off : code_off + len(code)] = code
    syms = dict(a.labels)

    # Place upgraded PPU packets starting at $8800 in Bank 1
    pkt_cursor = 0x8800
    for name, pkt in (
        ('PKT_25M', _upgrade_stage_ppu_packet(orig_prg, 0xF55B, '25m')),
        ('PKT_75M', _upgrade_stage_ppu_packet(orig_prg, 0xF7CD, '75m')),
        ('PKT_100M', _upgrade_stage_ppu_packet(orig_prg, 0xF71C, '100m')),
        ('PKT_TITLE', _make_barba_kong_title_packet()),
        ('PKT_HUD', _encode_ppu_packets(_decode_ppu_packets(orig_prg, 0xFA1B))),
    ):
        syms[name] = pkt_cursor
        off = pkt_cursor - 0x8000
        assert off + len(pkt) <= 8192
        bank1[off : off + len(pkt)] = pkt
        pkt_cursor += len(pkt)

    return bytes(bank1), syms


# ---------------------------------------------------------------------------
# WRAM Helper ($7800-$7BFF) & Bank 0 ($8000-$9FFF)
# ---------------------------------------------------------------------------

def make_dk_wram_code(
    restore_addr: int,
    *,
    reward_addr: int = DK_REWARD_ADDR,
    reward_magic: int = DK_REWARD_MAGIC,
    rng_adv_addr: int = 0xF4ED,
    mmc3_mode: bool = False,
) -> bytes:
    """Assemble the 1024-byte ($7800-$7BFF) WRAM helper for Barba Kong."""
    out = bytearray(b'\xFF' * 0x400)

    def place(addr: int, data: bytes, limit: int) -> None:
        off = addr - DK_WRAM_CODE_BASE
        assert off + len(data) <= limit - DK_WRAM_CODE_BASE, (
            f'Overflow at ${addr:04X}: {off + len(data)} > {limit - DK_WRAM_CODE_BASE}'
        )
        out[off : off + len(data)] = data

    # 1. DK_NMI_HOOK ($7840): 60-frame guard in $7FFF, then Start+Select ($30 in $14) -> DK_RETURN
    a = Asm6502(DK_NMI_HOOK)
    a.emit(0x48)                                                # PHA
    a.emit(0xAD, DK_DEBOUNCE & 0xFF, DK_DEBOUNCE >> 8)          # LDA $7FFF
    a.emit(0xC9, 0x3C)                                          # CMP #$3C (60 frames)
    a.branch(0xB0, 'check_pad')                                 # BCS check_pad
    a.emit(0xEE, DK_DEBOUNCE & 0xFF, DK_DEBOUNCE >> 8)          # INC $7FFF
    a.branch(0xD0, 'normal_nmi')                                # BNE normal_nmi (always taken)
    a.label('check_pad')
    a.emit(0xA5, DK_PAD1_ZP, 0x29, DK_START_SELECT, 0xC9, DK_START_SELECT)  # LDA $14; AND #$30; CMP #$30
    a.branch(0xF0, 'do_return')                                 # BEQ do_return
    a.label('normal_nmi')
    a.emit(0x68, 0x4C, DK_ORIG_NMI & 0xFF, DK_ORIG_NMI >> 8)    # PLA; JMP $C85F
    a.label('do_return')
    a.emit(0x68)                                                # PLA
    a.emit(0xA9, 0x00, 0x8D, DK_WIN_FLAG & 0xFF, DK_WIN_FLAG >> 8)  # LDA #$00; STA $7FFE
    a.emit(0x4C, DK_RETURN & 0xFF, DK_RETURN >> 8)              # JMP DK_RETURN
    place(DK_NMI_HOOK, a.finish(), DK_WIN_HOOK)

    # 2. DK_WIN_HOOK ($7870): called from $C8B3 when 100m rescue cutscene finishes
    a = Asm6502(DK_WIN_HOOK)
    a.emit(0xA9, reward_magic)                                  # LDA #reward_magic
    a.emit(0x8D, DK_WIN_FLAG & 0xFF, DK_WIN_FLAG >> 8)          # STA $7FFE
    a.emit(0x4C, DK_RETURN & 0xFF, DK_RETURN >> 8)              # JMP DK_RETURN
    place(DK_WIN_HOOK, a.finish(), DK_SEED_RNG)

    # 2b. DK_SEED_RNG ($7880): seed 8-byte LFSR $18-$1F from Barba's $7FF0-$7FF7
    a = Asm6502(DK_SEED_RNG)
    a.emit(0xA2, 0x07)                                          # LDX #$07
    a.label('seed_loop')
    a.emit(0xBD, 0xF0, 0x7F)                                    # LDA $7FF0,X
    a.emit(0x95, 0x18)                                          # STA $18,X
    a.emit(0xCA)                                                # DEX
    a.branch(0x10, 'seed_loop')                                 # BPL seed_loop
    a.emit(0xA5, 0x18, 0x05, 0x19)                              # LDA $18; ORA $19
    a.branch(0xD0, 'seed_ok')                                   # BNE seed_ok
    a.emit(0xA9, 0xA5, 0x85, 0x18)                              # LDA #$A5; STA $18
    a.label('seed_ok')
    a.emit(0x4C, rng_adv_addr & 0xFF, rng_adv_addr >> 8)        # JMP rng_adv_addr
    place(DK_SEED_RNG, a.finish(), DK_RETURN)

    # 3. DK_RETURN ($7960): silence APU/PPU, copy RAM trampoline to $0300, restore Barba banks & reward
    a = Asm6502(DK_RETURN)
    a.emit(0x78)                                                # SEI
    a.emit(0xA9, 0x00)
    a.emit(0x8D, 0x00, 0x20)                                    # STA $2000 (disable NMI)
    a.emit(0x8D, 0x01, 0x20)                                    # STA $2001 (disable rendering)
    a.emit(0x8D, 0x15, 0x40)                                    # STA $4015 (mute APU + DMC)
    a.emit(0x8D, 0x00, 0xE0)                                    # STA $E000 (disable MMC3 IRQ)
    a.emit(0xAE, DK_WIN_FLAG & 0xFF, DK_WIN_FLAG >> 8)          # LDX $7FFE (preserve win flag across $A001 switch)
    tramp = (
        bytes.fromhex(
            'a9 80 8d 01 a0 '                                   # LDA #$80; STA $A001 (unlock $5FF0-$5FF3)
            'a9 01 8d f0 5f '                                   # LDA #$01; STA $5FF0
            'a9 00 8d f1 5f 8d f2 5f '                          # LDA #$00; STA $5FF1; STA $5FF2
            'a9 06 8d 00 80 a9 0c 8d 01 80 '                    # R6 = $0C
            'a9 07 8d 00 80 a9 0d 8d 01 80 '                    # R7 = $0D
            'a9 a0 8d 01 a0 '                                   # LDA #$A0; STA $A001 (Barba WRAM bank 0 + lock)
            '8a f0 03 '                                         # TXA; BEQ +3
            '8d'
        )
        + reward_addr.to_bytes(2, 'little')                     # STA reward_addr (in WRAM bank 0!)
        + b'\x4c'                                               # JMP restore_addr
        + restore_addr.to_bytes(2, 'little')
    )
    a.emit(0xA0, len(tramp) - 1)                                # LDY #(len(tramp)-1)
    a.label('cp_tramp')
    a.abs_ref(0xB9, 'tramp_data')                               # LDA tramp_data,Y
    a.emit(0x99, 0x00, 0x03)                                    # STA $0300,Y
    a.emit(0x88)                                                # DEY
    a.branch(0x10, 'cp_tramp')                                  # BPL cp_tramp
    a.emit(0x4C, 0x00, 0x03)                                    # JMP $0300
    a.label('tramp_data')
    a.emit(*tramp)
    place(DK_RETURN, a.finish(), DK_BOOT)

    # 4. DK_BOOT ($7AE0): init PPU/APU/MMC3 Horizontal mirroring, map PRG/CHR, JMP $C79E
    a = Asm6502(DK_BOOT)
    a.emit(0x78, 0xD8)                                          # SEI; CLD
    a.emit(0xA9, 0x00)
    a.emit(0x8D, 0x00, 0x20)                                    # STA $2000
    a.emit(0x8D, 0x01, 0x20)                                    # STA $2001
    a.emit(0x8D, 0x15, 0x40)                                    # STA $4015
    a.emit(0x8D, 0x00, 0xE0)                                    # STA $E000 (ack/disable MMC3 IRQ)
    a.emit(0xA9, 0x01, 0x8D, 0x00, 0xA0)                        # LDA #$01; STA $A000 (Horizontal mirroring)
    if mmc3_mode:
        # Map R6 = 1 ($8000-$9FFF Barba Kong expansion) and R7 = 2 ($A000-$BFFF)
        a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x01, 0x8D, 0x01, 0x80)
        a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x02, 0x8D, 0x01, 0x80)
        chr_init = ((0, 0), (1, 8), (2, 16), (3, 17), (4, 20), (5, 21))
    else:
        a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0xFE, 0x8D, 0x01, 0x80)
        a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0xFF, 0x8D, 0x01, 0x80)
        chr_init = ((0, 0), (1, 2), (2, 4), (3, 5), (4, 6), (5, 7))
    for reg, val in chr_init:
        a.emit(0xA9, reg, 0x8D, 0x00, 0x80, 0xA9, val, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0x00)
    for state_addr in (
        DK_ROAR_TIMER, DK_ANIM_FRAME, DK_ROAR_COUNT, DK_WIN_FLAG, DK_DEBOUNCE,
    ):
        a.emit(0x8D, state_addr & 0xFF, state_addr >> 8)
    if mmc3_mode:
        a.emit(0xA9, 0x00, 0x8D, DK_CHR_BANK_R0 & 0xFF, DK_CHR_BANK_R0 >> 8)
        a.emit(0xA9, 0x08, 0x8D, DK_CHR_BANK_R1 & 0xFF, DK_CHR_BANK_R1 >> 8)
        a.emit(0xA9, 0x14, 0x8D, DK_CHR_BANK_R4 & 0xFF, DK_CHR_BANK_R4 >> 8)
    a.emit(0x4C, DK_ORIG_RESET & 0xFF, DK_ORIG_RESET >> 8)      # JMP $C79E (DK Reset)
    place(DK_BOOT, a.finish(), 0x7C00)

    return bytes(out)


def make_dk_bank0(
    restore_addr: int,
    *,
    wram_bank: int = 0xA3,
    standalone_stub: bool = False,
    reward_addr: int = DK_REWARD_ADDR,
    rng_adv_addr: int = 0xF4ED,
    mmc3_mode: bool = False,
) -> bytes:
    """Build 8KB bank 0 ($8000-$9FFF): copies $8100-$84FF -> $7800-$7BFF and jumps to DK_BOOT."""
    bank0 = bytearray(b'\xFF' * 8192)
    a = Asm6502(0x8000)
    if standalone_stub:
        # Copy 31-byte MMC3-init stub to $0300 RAM before switching $5FF0/$8000 out from under us
        a.emit(0x78, 0xD8, 0xA2, 0x1E)                          # SEI; CLD; LDX #30
        a.label('cp_ram')
        a.abs_ref(0xBD, 'ram_boot')                             # LDA ram_boot,X
        a.emit(0x9D, 0x00, 0x03, 0xCA)                          # STA $0300,X; DEX
        a.branch(0x10, 'cp_ram')                                # BPL cp_ram
        a.emit(0x4C, 0x00, 0x03)                                # JMP $0300
        a.label('ram_boot')
        a.emit(0xA9, 0x80, 0x8D, 0x01, 0xA0)                    # LDA #$80; STA $A001
        a.emit(0xA9, 0x01, 0x8D, 0xF0, 0x5F)                    # LDA #$01; STA $5FF0
        a.emit(0xA9, 0x00, 0x8D, 0xF1, 0x5F, 0x8D, 0xF2, 0x5F)  # $5FF1=0, $5FF2=0
        a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x00, 0x8D, 0x01, 0x80)  # R6=0
        a.abs_ref(0x4C, 'after_mmc3')                           # JMP after_mmc3
        a.label('after_mmc3')
    a.emit(0xA9, wram_bank, 0x8D, 0x01, 0xA0)                   # WRAM bank + lock $5FF0-$5FF3
    a.emit(0xA9, 0x00, 0x85, 0x00, 0x85, 0x02)                  # $00=0, $02=0
    a.emit(0xA9, 0x81, 0x85, 0x01)                              # $01=$81
    a.emit(0xA9, 0x78, 0x85, 0x03)                              # $03=$78
    a.emit(0xA2, 0x04, 0xA0, 0x00)                              # 4 pages ($8100-$84FF -> $7800-$7BFF)
    a.label('cp')
    a.emit(0xB1, 0x00, 0x91, 0x02, 0xC8)
    a.branch(0xD0, 'cp')
    a.emit(0xE6, 0x01, 0xE6, 0x03, 0xCA)
    a.branch(0xD0, 'cp')
    a.emit(0x4C, DK_BOOT & 0xFF, DK_BOOT >> 8)                  # JMP DK_BOOT ($7AE0)
    loader = a.finish()
    assert len(loader) <= 0xF0
    bank0[0 : len(loader)] = loader
    if standalone_stub:
        # $80F0: infinite loop target for standalone DK_RETURN verification
        stub = bytes([0x4C, STANDALONE_RESTORE_ADDR & 0xFF, STANDALONE_RESTORE_ADDR >> 8])
        off = STANDALONE_RESTORE_ADDR - 0x8000
        bank0[off : off + len(stub)] = stub
    bank0[0x100 : 0x500] = make_dk_wram_code(
        restore_addr,
        reward_addr=reward_addr,
        rng_adv_addr=rng_adv_addr,
        mmc3_mode=mmc3_mode,
    )
    return bytes(bank0)


def _validate_dk_rom(dk_bytes: bytes) -> tuple[bytes, bytes]:
    assert dk_bytes[:4] == b'NES\x1a', 'Not an iNES ROM'
    assert dk_bytes[4] == 1 and dk_bytes[5] == 1, (
        f'Expected NROM-128 (1x16KB PRG, 1x8KB CHR), got {dk_bytes[4]}x16KB, {dk_bytes[5]}x8KB'
    )
    mapper = (dk_bytes[6] >> 4) | (dk_bytes[7] & 0xF0)
    assert mapper == 0, f'Expected Mapper 0 (NROM), got {mapper}'
    assert (dk_bytes[6] & 0x01) == 0, 'Expected Horizontal mirroring'
    prg = dk_bytes[16 : 16 + 16384]
    chr_data = dk_bytes[16 + 16384 : 16 + 16384 + 8192]
    assert len(prg) == 16384 and len(chr_data) == 8192
    return prg, chr_data


def patch_dk(dk_bytes: bytes) -> tuple[bytes, bytes]:
    """Legacy NROM-128 patcher kept for backward compatibility; returns (prg16k, chr8k)."""
    orig_prg, chr_data = _validate_dk_rom(dk_bytes)
    prg = bytearray(orig_prg)

    def patch(addr: int, new: bytes, expected: bytes) -> None:
        off = addr - 0xC000
        assert bytes(prg[off : off + len(expected)]) == expected, (
            f'Unexpected DK bytes at ${addr:04X}: {bytes(prg[off : off + len(expected)]).hex(" ")}'
        )
        prg[off : off + len(new)] = new

    patch(0xFFFA, bytes([DK_NMI_HOOK & 0xFF, DK_NMI_HOOK >> 8]), bytes([DK_ORIG_NMI & 0xFF, DK_ORIG_NMI >> 8]))
    patch(DK_WIN_PATCH_ADDR, bytes([0x4C, DK_WIN_HOOK & 0xFF, DK_WIN_HOOK >> 8]), bytes.fromhex('a9 00 8d'))
    patch(0xC7E1, bytes([0x20, DK_SEED_RNG & 0xFF, DK_SEED_RNG >> 8]), bytes.fromhex('20 ed f4'))
    return bytes(prg), chr_data


def _patch_dk_prg_mmc3(
    orig_prg: bytes,
    bank1_syms: dict[str, int],
    pose_grids: dict[str, list[int]],
    roar_dmc: bytes,
) -> bytes:
    """Patch DK's 16 KB fixed PRG ($C000-$FFFF) for Barba Kong MMC3 + roar.dmc."""
    prg = bytearray(orig_prg)
    touched: set[int] = set()

    def patch(addr: int, new: bytes, expected: bytes) -> None:
        assert len(new) == len(expected), f'Length mismatch at ${addr:04X}'
        off = addr - 0xC000
        actual = bytes(prg[off : off + len(expected)])
        assert actual == expected, (
            f'Unexpected DK bytes at ${addr:04X}: got {actual.hex(" ")}, expected {expected.hex(" ")}'
        )
        for i in range(off, off + len(new)):
            assert i not in touched, f'Overlapping PRG patch at ${0xC000 + i:04X}'
            touched.add(i)
        prg[off : off + len(new)] = new

    # 1. NMI vector ($FFFA) -> DK_NMI_HOOK ($7840)
    patch(0xFFFA, bytes([DK_NMI_HOOK & 0xFF, DK_NMI_HOOK >> 8]), bytes([DK_ORIG_NMI & 0xFF, DK_ORIG_NMI >> 8]))

    # 2. 100m rescue cutscene completion ($C8B3) -> JMP DK_WIN_HOOK ($7870)
    patch(DK_WIN_PATCH_ADDR, bytes([0x4C, DK_WIN_HOOK & 0xFF, DK_WIN_HOOK >> 8]), bytes.fromhex('a9 00 8d'))

    # 3. Boot RNG seed once after RAM clear ($C7C2: JSR $C7E7 -> JSR DK_SEED_RNG -> JMP $C7E7)
    #    and keep $C7E1 idle loop advancing the relocated LFSR ($F4ED -> _reloc_addr(0xF4ED))
    patch(0xC7C2, bytes([0x20, DK_SEED_RNG & 0xFF, DK_SEED_RNG >> 8]), bytes.fromhex('20 e7 c7'))
    rng_adv = _reloc_addr(0xF4ED)
    patch(0xC7E1, bytes([0x20, rng_adv & 0xFF, rng_adv >> 8]), bytes.fromhex('20 ed f4'))

    # 4. Redirect all external callers of relocated $F1B4..$F55A -> Bank 1 ($8000..$83A6)
    reloc_callers = (
        (0xC812, 0x4C, 0xF228),
        (0xC820, 0x4C, 0xF2D7),
        (0xC87B, 0x20, 0xF228),
        (0xC886, 0x20, 0xF50E),
        (0xC8CE, 0x20, 0xF4AC),
        (0xC8E2, 0x20, 0xF23C),
        (0xCA30, 0x20, 0xF4AC),
        (0xCAC9, 0x20, 0xF4AC),
        (0xCB8D, 0x20, 0xF4C2),
        (0xCBA8, 0x20, 0xF23C),
        (0xCBBA, 0x4C, 0xF1B4),
        (0xCBC7, 0x4C, 0xF4C2),
        (0xCC2E, 0x20, 0xF342),
        (0xCD0D, 0x20, 0xF4AC),
        (0xCF27, 0x20, 0xF4AC),
        (0xD021, 0x20, 0xF342),
        (0xD03E, 0x4C, 0xF435),
        (0xEBD0, 0x20, 0xF33E),
        (0xEBD7, 0x4C, 0xF23C),
    )
    for call_addr, op, orig_tgt in reloc_callers:
        new_tgt = _reloc_addr(orig_tgt)
        patch(
            call_addr,
            bytes([op, new_tgt & 0xFF, new_tgt >> 8]),
            bytes([op, orig_tgt & 0xFF, orig_tgt >> 8]),
        )

    # 5. Repoint $C4A7 PPU screen/palette table to Bank 1 upgraded Barba Kong packets
    new_c4a7 = b''.join(
        bank1_syms[k].to_bytes(2, 'little')
        for k in ('PKT_25M', 'PKT_TITLE', 'PKT_75M', 'PKT_100M', 'PKT_TITLE', 'PKT_HUD')
    )
    orig_c4a7 = bytes.fromhex('5b f5 d9 f8 cd f7 1c f7 d9 f8 1b fa')
    patch(0xC4A7, new_c4a7, orig_c4a7)

    # 6. Embed roar.dmc into freed $F1C0..$FA47 window (keeping $F1B4..$F1BF & $FA40+ clean)
    assert len(roar_dmc) <= ROAR_DMC_CAPACITY
    win_start = DK_RELOC_ORIG_START
    win_len = DK_RELOC_ORIG_END - win_start
    # Also free the 1261-byte PPU packet block $F55B..$FA47
    full_free_start = DK_RELOC_ORIG_START
    full_free_end = 0xFA48
    expected_orig = bytes(orig_prg[full_free_start - 0xC000 : full_free_end - 0xC000])
    new_window = bytearray(b'\xFF' * (full_free_end - full_free_start))
    dmc_rel = ROAR_DMC_ADDR - full_free_start
    new_window[dmc_rel : dmc_rel + len(roar_dmc)] = roar_dmc
    patch(full_free_start, bytes(new_window), expected_orig)

    # 7. Barba Kong NMI end hook ($C8E8), Roar triggers, & APU DMC preservation
    def jsr(sym: str) -> bytes:
        addr = bank1_syms[sym]
        return bytes([0x20, addr & 0xFF, addr >> 8])

    def jmp(sym: str) -> bytes:
        addr = bank1_syms[sym]
        return bytes([0x4C, addr & 0xFF, addr >> 8])

    patch(0xC8E8, jmp('BarbaKongNmiEnd') + bytes([0xEA] * 4), bytes.fromhex('a5 10 49 80 8d 00 20'))
    patch(0xC90C, jsr('BarbaKongEnableApu') + bytes([0xEA, 0xEA]), bytes.fromhex('a9 0f 8d 15 40'))
    patch(0xC98A, jsr('BarbaKongTitleStart'), bytes.fromhex('8d 14 05'))
    patch(0xCA1D, jsr('BarbaKongEnableApu') + bytes([0xEA, 0xEA]), bytes.fromhex('a9 0f 8d 15 40'))
    patch(0xCE2F, jsr('BarbaKongRescueRoar') + bytes([0xEA]), bytes.fromhex('a9 04 85 fd'))
    patch(0xD086, jsr('BarbaKongStageClear') + bytes([0xEA] * 5), bytes.fromhex('a9 00 85 fc a9 01 85 9a'))
    patch(0xD75C, jmp('BarbaKongFireballUpdate'), bytes.fromhex('a5 9f 4a'))
    patch(0xD88F, jsr('BarbaKongPickupFury') + bytes([0xEA, 0xEA]), bytes.fromhex('a5 fc 8d 19 05'))
    patch(0xCF07, jsr('BarbaKongStage2Hook'), bytes.fromhex('20 29 ec'))
    patch(0xEA34, jmp('BarbaKongSpringSpawn'), bytes.fromhex('a5 36 d0'))
    patch(0xEB24, bytes([0x04]), bytes([0x02]))
    patch(0xECBF, jmp('BarbaKongFireballHit') + bytes([0xEA]), bytes.fromhex('a5 a0 d0 03'))

    # Keep Lil' Barba facing forward during Flame Fury instead of cycling back-facing climb frames ($10-$1C)
    patch(0xC1A2, bytes([0x04, 0x08, 0x20, 0x04, 0x08, 0x20]), bytes.fromhex('0c 14 1c 10 18 20'))

    # 8. Update Flame Fury sprite-pal-2 flash ($C6A2-$C6A9): fury blue -> Zelda Blue Bombs ($12 $21 $30)
    patch(0xC6A2, bytes([0x13, 0x2C, 0x30, 0x12, 0x13, 0x12, 0x21, 0x30]), bytes.fromhex('13 2c 16 13 13 16 30 37'))
    # Keep left-side behind-BG bombs ($DFD5) and 25m barrel spawn ($EE57) on SPR2 ($22 / $02) instead of SPR3
    patch(0xDFD6, bytes([0x22]), bytes([0x23]))
    patch(0xEE58, bytes([0x02]), bytes([0x03]))

    # 9. Update Big Bad Link 6x4 BG tile tables ($C60C..$C6A1 and $C71C..$C74D)
    bg_pose_patches = (
        (0xC60C, 'stomp_l'),
        (0xC625, 'stomp_r'),
        (0xC63E, 'idle'),
        (0xC657, 'grab'),
        (0xC670, 'throw_l'),
        (0xC689, 'throw_r'),
        (0xC71C, 'fall_a'),
        (0xC735, 'fall_b'),
    )
    for tbl_addr, pose_name in bg_pose_patches:
        off = tbl_addr - 0xC000
        expected_blk = bytes(orig_prg[off : off + 25])
        assert expected_blk[0] == 0x46, f'Expected 4x6 block header $46 at ${tbl_addr:04X}'
        new_blk = bytes([0x46] + pose_grids[pose_name])
        assert len(new_blk) == 25
        patch(tbl_addr, new_blk, expected_blk)

    return bytes(prg)


def patch_dk_for_combined(
    dk_bytes: bytes,
    z2_bytes: bytes,
    restore_addr: int,
    *,
    reward_addr: int = 0x63B3,
) -> tuple[bytes, bytes]:
    """Build (prg_256k, chr_32k) for Barba Kong (Round 2) inside barba.nes Slot 7."""
    orig_prg, orig_chr = _validate_dk_rom(dk_bytes)

    root = Path(__file__).resolve().parent.parent
    roar_out = root / 'build/subgames/dk_roar'
    roar_dmc, roar_info = roar_sample.convert(root / 'assets/roar.wav', roar_out)

    chr32, pose_grids = build_barba_kong_chr(orig_chr, z2_bytes)
    bank1, bank1_syms = _assemble_bank1(orig_prg, roar_info, len(roar_dmc))
    fixed_prg16k = _patch_dk_prg_mmc3(orig_prg, bank1_syms, pose_grids, roar_dmc)

    bank0 = make_dk_bank0(
        restore_addr,
        wram_bank=0xA3,
        standalone_stub=False,
        reward_addr=reward_addr,
        rng_adv_addr=0xC7E7,
        mmc3_mode=True,
    )

    prg256 = bytearray(b'\xFF' * (256 * 1024))
    prg256[0 : 8192] = bank0
    prg256[8192 : 16384] = bank1
    prg256[30 * 8192 : 32 * 8192] = fixed_prg16k
    return bytes(prg256), chr32


def build_standalone(
    out_path: Path,
    dk_path: Path = Path('roms/dk.nes'),
    z2_path: Path = Path('roms/z2.nes'),
) -> Path:
    """Wrap Barba Kong in a standalone 256 KB PRG + 32 KB CHR NES 2.0 Mapper 176 ROM."""
    root = Path(__file__).resolve().parent.parent
    if not z2_path.is_absolute() and not z2_path.exists():
        z2_path = root / z2_path
    dk_bytes = dk_path.read_bytes()
    z2_bytes = load_source(z2_path)
    orig_prg, orig_chr = _validate_dk_rom(dk_bytes)

    roar_out = root / 'build/subgames/dk_roar'
    roar_dmc, roar_info = roar_sample.convert(root / 'assets/roar.wav', roar_out)

    chr32, pose_grids = build_barba_kong_chr(orig_chr, z2_bytes)
    bank1, bank1_syms = _assemble_bank1(orig_prg, roar_info, len(roar_dmc))
    fixed_prg16k = bytearray(_patch_dk_prg_mmc3(orig_prg, bank1_syms, pose_grids, roar_dmc))

    # Patch standalone reset vector ($FFFC) to $8000 (bank 0 loader)
    rst_off = 0xFFFC - 0xC000
    assert fixed_prg16k[rst_off : rst_off + 2] == bytes([DK_ORIG_RESET & 0xFF, DK_ORIG_RESET >> 8])
    fixed_prg16k[rst_off : rst_off + 2] = bytes([0x00, 0x80])

    bank0 = make_dk_bank0(
        STANDALONE_RESTORE_ADDR,
        standalone_stub=True,
        reward_addr=DK_REWARD_ADDR,
        rng_adv_addr=0xC7E7,
        mmc3_mode=True,
    )

    prg256 = bytearray(b'\xFF' * (256 * 1024))
    prg256[0 : 8192] = bank0
    prg256[8192 : 16384] = bank1
    # In standalone mode, DK_RETURN maps R6=$0C before JMP $80F0; fill $80F0..$9FFC in bank $0C with
    # 1-byte NOPs (plus JMP $80F0 at $9FFD) so dk_standalone.lua's endFrame cpu.pc=$7AE0 never lands mid-operand.
    stub_base = 0x0C * 8192 + (STANDALONE_RESTORE_ADDR - 0x8000)
    stub_end = 0x0C * 8192 + 0x1FFD
    prg256[stub_base : stub_end] = b'\xEA' * (stub_end - stub_base)
    prg256[stub_end : stub_end + 3] = bytes([0x4C, STANDALONE_RESTORE_ADDR & 0xFF, STANDALONE_RESTORE_ADDR >> 8])
    prg256[30 * 8192 : 32 * 8192] = bytes(fixed_prg16k)

    # NES 2.0 Mapper 176 (FK23C), 256KB PRG, 32KB CHR, 32KB PRG-RAM, Horizontal mirroring
    assert len(chr32) % 8192 == 0 and len(chr32) <= 128 * 1024
    hdr = bytearray(16)
    hdr[0:4] = b'NES\x1a'
    hdr[4] = 16                     # 16 * 16KB = 256KB PRG
    hdr[5] = len(chr32) // 8192     # 4 * 8KB = 32KB CHR
    hdr[6] = 0x02                   # Horizontal mirroring + battery, mapper low = 0
    hdr[7] = 0xB8                   # NES 2.0 + mapper mid = $B0 (176)
    hdr[10] = 0x90                  # 32KB battery PRG-RAM

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(hdr) + bytes(prg256) + chr32)
    return out_path


if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    out = build_standalone(root / 'build/subgames/dk.nes', root / 'roms/dk.nes', root / 'roms/z2.nes')
    rom = out.read_bytes()
    assert len(rom) == 16 + 256 * 1024 + 32 * 1024
    assert rom[0:4] == b'NES\x1a'
    assert rom[4] == 16 and rom[5] == 4
    assert ((rom[6] >> 4) | (rom[7] & 0xF0)) == 176
    assert rom[16 + 256 * 1024 - 6 : 16 + 256 * 1024 - 4] == bytes([DK_NMI_HOOK & 0xFF, DK_NMI_HOOK >> 8])
    assert rom[16 + 256 * 1024 - 4 : 16 + 256 * 1024 - 2] == bytes([0x00, 0x80])
    # Also sanity-check patch_dk_for_combined contract
    c_prg, c_chr = patch_dk_for_combined(
        (root / 'roms/dk.nes').read_bytes(),
        (root / 'roms/z2.nes').read_bytes(),
        0xE123,
    )
    assert len(c_prg) == 256 * 1024 and len(c_chr) == 32 * 1024
    print(f'Built {out} ({len(rom)} bytes) - Barba Kong MMC3 assertions passed.')
