"""Barba, Villainous Link, Title, and Zelda II opponent mod assets for MTPO."""
from __future__ import annotations

from nes import decode_tile, encode_tile

# MTPO custom text encoding (used in PRG Bank 9 & Bank 12)
MTPO_CHAR = {
    ' ': 0xFF,
    "'": 0x26,
    '-': 0x27,
    '!': 0x28,
    '.': 0x2A,
    ':': 0x2B,
    ',': 0x2C,
    '#': 0x2D,
    '?': 0x30,
}
for _i in range(10):
    MTPO_CHAR[str(_i)] = 0x01 + _i
for _i in range(26):
    MTPO_CHAR[chr(ord('A') + _i)] = 0x0B + _i


def encode_mtpo_text(s: str) -> bytes:
    return bytes(MTPO_CHAR[ch] for ch in s)


# ---------------------------------------------------------------------------
# 2bpp pixel-art helpers
# Palette conventions for BG3 (Barba):
#   0 = transparent / mat background
#   1 = crimson red ($16)
#   2 = black outline / shadow ($0F)
#   3 = gold / ivory / flame highlight ($38)
# ---------------------------------------------------------------------------

_CHAR_MAP = {'.': '0', 'r': '1', 'R': '1', 'k': '2', 'K': '2', 'g': '3', 'G': '3',
             '0': '0', '1': '1', '2': '2', '3': '3'}


def _tile_from_ascii(rows: list[str]) -> bytes:
    assert len(rows) == 8
    conv = []
    for r in rows:
        assert len(r) == 8, f"Row length {len(r)} != 8: {r!r}"
        conv.append(''.join(_CHAR_MAP[c] for c in r))
    return encode_tile(conv)


def _draw_canvas_into_chr(
    chr_rom: bytearray,
    bank_4k: int,
    tile_grid: list[list[int | None]],
    canvas: list[str],
) -> None:
    """Slice an (8*H) x (8*W) ASCII pixel canvas into specified 4KB CHR bank tiles."""
    h_tiles = len(tile_grid)
    w_tiles = len(tile_grid[0])
    assert len(canvas) == h_tiles * 8
    for row in canvas:
        assert len(row) == w_tiles * 8
    for ty in range(h_tiles):
        for tx in range(w_tiles):
            tid = tile_grid[ty][tx]
            if tid is None:
                continue
            sub = [canvas[ty * 8 + py][tx * 8 : tx * 8 + 8] for py in range(8)]
            off = bank_4k * 4096 + tid * 16
            chr_rom[off : off + 16] = _tile_from_ascii(sub)


# 3 cols x 8 rows = 24x64 back-view Barba (Idle: tiles $01..$07, $08..$0F, $10..$17)
# Note: Col 0 starts with blank tile $FF above $01..$07 (so row 0 of Col 0 is blank,
# while Col 1 ($08) & Col 2 ($10) start 1 row higher — let's check LO_00:
#   Col 0: [FF, 01, 02, 03, 04, 05, 06, 07] -> rows 1..7
#   Col 1: [08, 09, 0A, 0B, 0C, 0D, 0E, 0F] -> rows 0..7
#   Col 2: [10, 11, 12, 13, 14, 15, 16, 17] -> rows 0..7
# Wait: both Col 1 and Col 2 have 8 tiles and Col 0 has FF + 7 tiles = 8 rows!
_BARBA_IDLE_GRID = [
    [None, 0x08, 0x10],
    [0x01, 0x09, 0x11],
    [0x02, 0x0A, 0x12],
    [0x03, 0x0B, 0x13],
    [0x04, 0x0C, 0x14],
    [0x05, 0x0D, 0x15],
    [0x06, 0x0E, 0x16],
    [0x07, 0x0F, 0x17],
]

# 24x64 back-view Barba canvas:
#   Top (rows 0-23): curved gold/ivory horns, crimson dragon skull, dorsal head-spikes, fierce gold eye glint
#   Mid (rows 24-47): flared crimson/black ribbed dragon wings, gold spinal plates, raised clawed fists
#   Low (rows 48-63): muscular dragon legs, clawed feet, sweeping crimson/gold tail
_BARBA_IDLE_CANVAS = [
    # y=0..7 (Col 0 ignored -> '.')
    "........" "..kggk.." "........",
    "........" ".kgrrgk." "..kggk..",
    "........" ".kgRRgk." ".kgRRgk.",
    "........" "kRRggRRk" "kggRRgk.",
    "........" "kRRggRRk" "kRRRggk.",
    "........" "kRRRRRRk" "kRRRRk..",
    "........" "kRggRRRk" "kRRRgk..",
    "........" "kRggRRRk" "kRRggk..",
    # y=8..15
    ".....kgg" "kkRRRRkk" "ggk.....",
    "....kgRR" "kRRggRRk" "RRgk....",
    "...kgrRR" "kRRggRRk" "RRrgk...",
    "...kRRRk" "RRRRRRRR" "kRRRk...",
    "..kRRRRk" "RkkggkkR" "kRRRRk..",
    "..kRRgRk" "RRkggkRR" "kRgRRk..",
    "..kRggRk" "RRRRRRRR" "kRggRk..",
    "...kRRRk" "kRRRRRRk" "kRRRk...",
    # y=16..23 (shoulders + raised dragon fists + neck spines)
    ".kkRRRRk" ".kRRggRk" "kRRRRkk.",
    "kggRRRRk" ".kRRggRk" "kRRRRggk",
    "kgRRRRRk" "kRRRggRk" "kRRRRRgk",
    "kRRkkkRk" "kRRRRRRk" "kRkkkRRk",
    "kRRk.kRk" "kRRggRRk" "kRk.kRRk",
    ".kk..kRk" "kRRggRRk" "kRk..kk.",
    "....kRRk" "kRRRRRRk" "kRRk....",
    "...kRRRR" "kRRggRRk" "RRRRk...",
    # y=24..31 (ribbed dragon wings + dorsal gold spine)
    "..kRRRRR" "kRRggRRk" "RRRRRk..",
    ".kRRkkRR" "kRRRRRRk" "RRkkRRk.",
    "kRRk.kRR" "kRRggRRk" "RRk.kRRk",
    "kRk..kRR" "kRRggRRk" "RRk..kRk",
    "kRk.kRRR" "kRRRRRRk" "RRRk.kRk",
    "kRk.kRRk" "kRRggRRk" "kRRk.kRk",
    ".k..kRRk" "kRRggRRk" "kRRk..k.",
    "....kRRk" "kRRRRRRk" "kRRk....",
    # y=32..39 (wings fold + waist/scales)
    "...kRRRk" "kRRggRRk" "kRRRk...",
    "..kRRggk" "kRRRRRRk" "kggRRk..",
    "..kRRkkk" "kRRggRRk" "kkkRRk..",
    "...kk..k" "kRRggRRk" "k..kk...",
    "......kR" "kRRRRRRk" "Rk......",
    ".....kRR" "kRRggRRk" "RRk.....",
    ".....kRR" "RRRRRRRR" "RRk.....",
    "....kRRR" "kRRggRRk" "RRRk....",
    # y=40..47 (hips + tail start)
    "....kRRk" "kRRRRRRk" "kRRk....",
    "....kRRk" "kRRggRRk" "kRRk....",
    "...kRRRk" "kRRRRRRk" "kRRRk...",
    "...kRRRk" "kRRggRRk" "kRRRk...",
    "...kRRRk" "kRRRRRRk" "kRRRk...",
    "...kRRk." ".kRggRk." ".kRRk...",
    "..kRRRk." ".kRRRRk." ".kRRRk..",
    "..kRRk.." ".kRggRk." "..kRRk..",
    # y=48..55 (legs + sweeping tail left)
    "..kRRk.." ".kRRRRk." "..kRRk..",
    ".kRRRk.." "..kRRk.." "..kRRRk.",
    ".kRRk..." "..kRRk.." "...kRRk.",
    ".kRRk..." ".kRRk..." "...kRRk.",
    ".kggk..." ".kRRk..." "...kggk.",
    "kggk...." "kRRgk..." "....kggk",
    "kkk....." "kRggk..." ".....kkk",
    "........" "kRRgk..." "........",
    # y=56..63 (clawed feet + tail tip)
    "........" "kRRRk..." "........",
    ".......k" "RRRRk..." "........",
    "......kR" "RRggk..." "........",
    ".....kRR" "ggkk...." "........",
    "....kRRg" "kk......" "........",
    "....kggk" "........" "........",
    ".....kkk" "........" "........",
    "........" "........" "........",
]

# Crouched lower half for LO_01 ($18..$1B, $1C..$1F, $20..$22)
_BARBA_BOB_LOW_GRID = [
    [0x18, 0x1C, 0x20],
    [0x19, 0x1D, 0x21],
    [0x1A, 0x1E, 0x22],
    [0x1B, 0x1F, None],
]
_BARBA_BOB_LOW_CANVAS = _BARBA_IDLE_CANVAS[36:] + [
    "........" "........" "........" for _ in range(4)
]

# Duck/guard head+wings ($23..$25, $26..$29)
_BARBA_DUCK_GRID = [
    [0x23, None, 0x26],
    [0x24, None, 0x27],
    [0x25, None, 0x28],
    [None, None, 0x29],
]


def _dragonize_mac_tile(tile: bytes, flame_boost: bool = False) -> bytes:
    """Recolor a Mac silhouette tile into Barba crimson scales, black outline, and gold claws/ridge."""
    dec = decode_tile(tile)
    rows_out = []
    for y in range(8):
        r = []
        for x in range(8):
            px = dec[y][x]
            if px == 3:
                # Gold dorsal/scale accents on crimson dragon hide
                if flame_boost and ((x + y) % 2 == 0):
                    r.append('3')
                elif (x + y) % 4 == 0:
                    r.append('3')
                else:
                    r.append('1')
            elif px == 1:
                # Gloves/trunks -> crimson with glowing gold claw/flame edge near outline/bg
                is_edge = False
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if nx < 0 or nx >= 8 or ny < 0 or ny >= 8 or dec[ny][nx] in (0, 2):
                        is_edge = True
                        break
                if (flame_boost and (y % 2 == 0)) or is_edge:
                    r.append('3')
                else:
                    r.append('1')
            else:
                r.append(str(px))
        rows_out.append(''.join(r))
    return encode_tile(rows_out)


def _patch_barba_chr(chr_rom: bytearray) -> None:
    """Draw Barba into CHR Bank 1 (Mac-only tiles) & Bank 2 (100% Mac), preserving Mario/TKO/UI."""
    # 1. Idle / Guard Barba in Bank 1 ($01..$17)
    _draw_canvas_into_chr(chr_rom, 1, _BARBA_IDLE_GRID, _BARBA_IDLE_CANVAS)

    # 2. Bob lower body ($18..$22) — shift 4px lower squat look
    bob_canvas = [
        "..kRRkkk" "kRRggRRk" "kkkRRk..",
        "...kk..k" "kRRggRRk" "k..kk...",
        ".....kRR" "kRRRRRRk" "RRk.....",
        "....kRRR" "kRRggRRk" "RRRk....",
        "...kRRRk" "kRRRRRRk" "kRRRk...",
        "...kRRRk" "kRRggRRk" "kRRRk...",
        "..kRRRk." "kRRRRRRk" ".kRRRk..",
        "..kRRk.." ".kRggRk." "..kRRk..",
        ".kRRRk.." ".kRRRRk." "..kRRRk.",
        ".kRRk..." "..kRRk.." "...kRRk.",
        ".kggk..." ".kRRk..." "...kggk.",
        "kggk...." "kRRgk..." "....kggk",
        "kkk....." "kRggk..." ".....kkk",
        ".......k" "RRRRk..." "........",
        "......kR" "RRggk..." "........",
        ".....kRR" "ggkk...." "........",
        "....kRRg" "kk......" "........",
        "....kggk" "........" "........",
        ".....kkk" "........" "........",
        "........" "........" "........",
    ] + ["........" * 3 for _ in range(12)]
    _draw_canvas_into_chr(chr_rom, 1, _BARBA_BOB_LOW_GRID, bob_canvas)

    # 3. Duck top ($23..$29)
    duck_rows = [
        "........" "........" "........",
        "........" "........" "........",
        ".....kgg" "........" "ggk.....",
        "....kgRR" "........" "RRgk....",
        "...kRRRR" "........" "RRRRk...",
        "..kRRgRk" "........" "kRgRRk..",
        "..kRggRk" "........" "kRggRk..",
        "...kRRRk" "........" "kRRRk...",
        ".kkRRRRk" "........" "kRRRRkk.",
        "kggRRRRk" "........" "kRRRRggk",
        "kgRRRRRk" "........" "kRRRRRgk",
        "kRRkkkRk" "........" "kRkkkRRk",
        "kRRk.kRk" "........" "kRk.kRRk",
        ".kk..kRk" "........" "kRk..kk.",
        "....kRRk" "........" "kRRk....",
        "...kRRRR" "........" "RRRRk...",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
        "........" "........" "........",
    ]
    _draw_canvas_into_chr(chr_rom, 1, _BARBA_DUCK_GRID, duck_rows)

    # 4. Bank 1 Mac punch/dodge/hurt tiles ($2A..$6B, NEVER touching $6C+ Mario or $A6+ TKO/1..10!)
    # Also Bank 1 $8A..$A5 (uppercut/dodge)
    b1_barba_slots = list(range(0x2A, 0x6C)) + list(range(0x8A, 0xA6))
    for tid in b1_barba_slots:
        if tid in (0x5C, 0x5D):  # shared small dots in HI UI
            continue
        off = 1 * 4096 + tid * 16
        tile = chr_rom[off : off + 16]
        if any(tile):
            flame = (0x48 <= tid <= 0x6B) or (0x8A <= tid <= 0xA5)
            chr_rom[off : off + 16] = _dragonize_mac_tile(tile, flame_boost=flame)

    # 5. CHR Bank 2 is 100% Little Mac (left/right hooks, dodge, hurt, Star Punch)
    for tid in range(0x01, 0xFD):
        off = 2 * 4096 + tid * 16
        tile = chr_rom[off : off + 16]
        if any(tile):
            flame = (0x6F <= tid <= 0x7D) or (0xC0 <= tid <= 0xC4)
            chr_rom[off : off + 16] = _dragonize_mac_tile(tile, flame_boost=flame)


# ---------------------------------------------------------------------------
# Villainous Link Portrait (CHR Bank 7) & Fight Sprites (CHR Bank 8)
# ---------------------------------------------------------------------------

# Minimal crisp 8x8 uppercase block font for "EVIL LINK " in Bank 7 ($F3..$FC)
# Bank 7 palette for bottom banner: 0=bg, 1=brown/gold, 2=black, 3=white
_LINK_BANNER_GLYPHS = {
    'E': [
        "22222222",
        "23333332",
        "23322222",
        "23333322",
        "23322222",
        "23333332",
        "22222222",
        "00000000",
    ],
    'V': [
        "22222222",
        "23322332",
        "23322332",
        "23322332",
        "22333322",
        "22233222",
        "22222222",
        "00000000",
    ],
    'I': [
        "22222222",
        "23333332",
        "22233222",
        "22233222",
        "22233222",
        "23333332",
        "22222222",
        "00000000",
    ],
    'L': [
        "22222222",
        "23322222",
        "23322222",
        "23322222",
        "23322222",
        "23333332",
        "22222222",
        "00000000",
    ],
    ' ': [
        "22222222",
        "22222222",
        "22222222",
        "22222222",
        "22222222",
        "22222222",
        "22222222",
        "00000000",
    ],
    'N': [
        "22222222",
        "23322332",
        "23332332",
        "23233332",
        "23223332",
        "23322332",
        "22222222",
        "00000000",
    ],
    'K': [
        "22222222",
        "23322332",
        "23323322",
        "23333222",
        "23323322",
        "23322332",
        "22222222",
        "00000000",
    ],
    'B': [
        "22222222",
        "23333322",
        "23322332",
        "23333322",
        "23322332",
        "23333322",
        "22222222",
        "00000000",
    ],
    'A': [
        "22222222",
        "22333322",
        "23322332",
        "23333332",
        "23322332",
        "23322332",
        "22222222",
        "00000000",
    ],
    'R': [
        "22222222",
        "23333322",
        "23322332",
        "23333322",
        "23323322",
        "23322332",
        "22222222",
        "00000000",
    ],
}


def _game_over_sil_mask(z2_bytes: bytes) -> list[list[bool]]:
    """Decode Z2 Game Over Link 80x96 silhouette boolean mask from roms/z2.nes."""
    from game_over_art import compile_game_over_link

    tiles, macro = compile_game_over_link(z2_bytes)
    sil = [[False] * 80 for _ in range(96)]
    idx = 0
    for ty in range(12):
        idx += 3  # addr_hi, addr_lo, len
        for tx in range(10):
            tid = macro[idx]
            idx += 1
            dec = decode_tile(tiles[tid])
            for py in range(8):
                for px in range(8):
                    if dec[py][px] != 0:
                        sil[ty * 8 + py][tx * 8 + px] = True
    return sil


def _build_evil_link_oam_canvas(z2_bytes: bytes | None) -> list[str]:
    """Build 32x40 Evil Link OAM canvas from the Z2 Game Over Link silhouette."""
    if z2_bytes is None:
        return [
            "00000000" "00001111" "11111000" "00000000",
            "00000000" "00113333" "33333110" "00000000",
            "00000000" "01333333" "33333331" "00000000",
            "00000000" "13333333" "33333333" "10000000",
            "00000000" "13331111" "11111133" "10000000",
            "00000000" "13112222" "22222113" "10000000",
            "00000000" "11222222" "22222221" "10000000",
            "00000000" "12222222" "22222222" "10000000",
        ] + ["0" * 32 for _ in range(32)]

    sil = _game_over_sil_mask(z2_bytes)

    # Downsample 64x80 (x=8..71, y=0..79) -> 32x40 (2x2 block -> 1px)
    # Color mapping in Intro SP0: 0=transparent, 1=black ($0F), 2=skin ($27), 3=Hylian green ($1A)
    mask32 = [[False] * 32 for _ in range(40)]
    for y in range(40):
        sy = y * 2
        for x in range(32):
            sx = 8 + x * 2
            hits = sum(
                1
                for dy in (0, 1)
                for dx in (0, 1)
                if sil[sy + dy][sx + dx]
            )
            mask32[y][x] = hits >= 2

    canvas: list[str] = []
    for y in range(40):
        row = []
        for x in range(32):
            if not mask32[y][x]:
                row.append("0")
                continue
            # Keep a crisp 1px black silhouette outline on all edges
            is_edge = (
                x == 0
                or x == 31
                or y == 0
                or y == 39
                or not mask32[y - 1][x]
                or not mask32[y + 1][x]
                or not mask32[y][x - 1]
                or not mask32[y][x + 1]
            )
            if is_edge:
                row.append("1")
                continue
            # Interior coloring following the Z2 Game Over Link bust geometry:
            #   y=1..7  : folded Hylian cap (green '3')
            #   y=8..17 : face & pointed ears (skin '2', fierce black brows/eyes '1')
            #   y=18..39: looming shoulders & split-collar tunic (green '3' + black '1' V-split & shadow)
            if y <= 7:
                row.append("3")
            elif y <= 17:
                # Fierce dark brows & eyes inside the Z2 Link head shape
                if y == 11 and x in (11, 12, 13, 18, 19, 20):
                    row.append("1")
                elif y == 12 and x in (12, 19):
                    row.append("1")
                elif y == 15 and 13 <= x <= 18:
                    row.append("1")  # grim scowl
                else:
                    row.append("2")
            else:
                # Split collar V-opening at y=19..23, x=13..18
                dist = abs(x - 15.5)
                if 19 <= y <= 23 and dist <= (23 - y) * 0.6:
                    row.append("1")
                elif y >= 32 and (x < 4 or x > 27):
                    row.append("1")  # looming dark shoulder edge
                else:
                    row.append("3")
        canvas.append("".join(row))
    return canvas


def _encode_b9_rle_grid(grid: list[list[int]]) -> bytes:
    """Encode a 10x10 tile grid into MTPO Bank 9 RLE packet format ($02-$3F inc / $4x lit / $Ex rep / $90 / $00)."""
    out = bytearray()
    for r_idx, row in enumerate(grid):
        i = 0
        n = len(row)
        while i < n:
            # 1. Identical repeat run (>= 2) -> $E0|cnt, val
            j = i + 1
            while j < n and row[j] == row[i] and (j - i) < 15:
                j += 1
            if j - i >= 2:
                out.append(0xE0 | (j - i))
                out.append(row[i])
                i = j
                continue
            # 2. Incrementing run (row[k] == row[i] + (k - i), len >= 2) -> cnt, start_val
            k = i + 1
            while k < n and row[k] == row[k - 1] + 1 and (k - i) < 15:
                k += 1
            if k - i >= 2:
                out.append(k - i)
                out.append(row[i])
                i = k
                continue
            # 3. Literal run ($40|cnt, bytes...) stopping before repeat (>=2) or inc run (>=2)
            start = i
            i += 1
            while i < n and (i - start) < 15:
                if i + 1 < n and (row[i] == row[i + 1] or row[i] + 1 == row[i + 1]):
                    break
                i += 1
            out.append(0x40 | (i - start))
            out.extend(row[start:i])
        out.append(0x90 if r_idx < len(grid) - 1 else 0x00)
    return bytes(out)


def _patch_evil_link_chr(
    chr_rom: bytearray,
    z2_bytes: bytes | None = None,
    prg: bytearray | None = None,
) -> None:
    """Mod Bank 7 Intro wallpaper (' BARBA ') + Z2 Game Over Link BG portrait + Bank 4 chunky LINK."""
    # 1. Bank 7 wallpaper $F3..$F9 (" BARBA ") — keep $FB untouched so portrait bg stripe stays clean!
    for idx, ch in enumerate(" BARBA "):
        off = 7 * 4096 + (0xF3 + idx) * 16
        chr_rom[off : off + 16] = encode_tile(_LINK_BANNER_GLYPHS[ch])

    # 2. Clear "MIKE"/"TYSON" BG shadow tiles in the black text box ($06,$07,$3A..$3C,$4B..$4D,$68,$69,$6E,$91,$96 -> $00)
    for tid in [0x06, 0x07, 0x3A, 0x3B, 0x3C, 0x4B, 0x4C, 0x4D, 0x68, 0x69, 0x6E, 0x91, 0x96]:
        off = 7 * 4096 + tid * 16
        chr_rom[off : off + 16] = b"\x00" * 16

    # Draw chunky white-outlined green "LINK" into Bank 4 tiles $01..$17 (OAM sprites at y=143..166 on Intro!)
    # Canvas is 64x24 (tile (0,0) unused in OAM -> letter pixels confined to x=9..55, y=2..17).
    link_9x12 = {
        'L': [
            "111000000", "111000000", "111000000", "111000000",
            "111000000", "111000000", "111000000", "111000000",
            "111000000", "111111111", "111111111", "111111111",
        ],
        'I': [
            "111111111", "111111111", "000111000", "000111000",
            "000111000", "000111000", "000111000", "000111000",
            "000111000", "000111000", "111111111", "111111111",
        ],
        'N': [
            "111000111", "111100111", "111100111", "111110111",
            "111011111", "111011111", "111001111", "111001111",
            "111000111", "111000111", "111000111", "111000111",
        ],
        'K': [
            "111000111", "111001110", "111011100", "111111000",
            "111110000", "111111000", "111011100", "111001110",
            "111000111", "111000111", "111000111", "111000111",
        ],
    }
    oam_face = [[False] * 64 for _ in range(24)]
    for li, ch in enumerate("LINK"):
        bx = 10 + li * 12
        for gy, row in enumerate(link_9x12[ch]):
            for gx, bit in enumerate(row):
                if bit == '1':
                    oam_face[4 + gy][bx + gx] = True
    oam_c = [['0'] * 64 for _ in range(24)]
    for py in range(24):
        for px in range(64):
            if oam_face[py][px]:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if 0 <= py + dy < 24 and 0 <= px + dx < 64 and not oam_face[py + dy][px + dx]:
                            oam_c[py + dy][px + dx] = '1'
    for py in range(24):
        for px in range(64):
            if oam_face[py][px]:
                oam_c[py][px] = '2'
    oam_grid = [
        [None, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07],
        [0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F],
        [0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17],
    ]
    _draw_canvas_into_chr(chr_rom, 4, oam_grid, [''.join(r) for r in oam_c])

    # 3. Clear Tyson's Intro OAM portrait & shoulder/glove tiles ($6F..$8F, $93, $95) in Bank 8 so the
    #    Bank 7 BG Z2 Game Over Link silhouette is not overlapped by Intro OAM sprites.
    for tid in list(range(0x6F, 0x90)) + [0x93, 0x95]:
        off = 8 * 4096 + tid * 16
        chr_rom[off : off + 16] = b"\x00" * 16

    # 3b. Render full 80x80 (10x10 tiles) Z2 Game Over Link BG silhouette into unused Bank 7 slots
    #     and patch Bank 9 Title2 portrait RLE ($813A..$818A, 81 bytes).
    if prg is not None and z2_bytes is not None:
        sil = _game_over_sil_mask(z2_bytes)
        bg_c = [['2'] * 80 for _ in range(80)]
        for py in range(73, 79):
            for px in range(1, 79):
                bg_c[py][px] = '3'  # brown shelf
        for py in range(1, 79):
            sy = py + 2
            for px in range(1, 79):
                if sy < 96 and sil[sy][px]:
                    bg_c[py][px] = '0'  # black Z2 Game Over Link silhouette
        for i in range(80):
            bg_c[0][i] = '1'
            bg_c[79][i] = '1'
            bg_c[i][0] = '1'
            bg_c[i][79] = '1'

        # Existing unchanged Bank 7 frame/solid tiles we can deduplicate against for free
        reuse_ids = (0x01, 0x02, 0x08, 0x09, 0x19, 0x3D, 0x3E, 0x3F, 0xFB)
        known_tiles: dict[bytes, int] = {}
        for rt in reuse_ids:
            t_bytes = bytes(chr_rom[7 * 4096 + rt * 16 : 7 * 4096 + (rt + 1) * 16])
            known_tiles[t_bytes] = rt

        # Contiguous Title2-only Bank 7 slots ($97..$F2 = 92 contiguous tiles) so sequential runs
        # compress cleanly to 2-byte incrementing runs [cnt, start_tid] inside the 81/97-byte RLE buffers.
        free_pool = list(range(0x97, 0xF3))
        portrait_grid = [[0] * 10 for _ in range(10)]
        for ty in range(10):
            for tx in range(10):
                t_rows = [''.join(bg_c[ty * 8 + py][tx * 8 : (tx + 1) * 8]) for py in range(8)]
                enc = encode_tile(t_rows)
                if enc in known_tiles:
                    portrait_grid[ty][tx] = known_tiles[enc]
                else:
                    if not free_pool:
                        raise RuntimeError("MTPO Bank 7 Title2 portrait tile pool exhausted")
                    ntid = free_pool.pop(0)
                    off = 7 * 4096 + ntid * 16
                    chr_rom[off : off + 16] = enc
                    portrait_grid[ty][tx] = ntid

        rle = _encode_b9_rle_grid(portrait_grid)
        # Patch BOTH Bank 9 $843A (Intro Challenge screen = 97B) and $813A (81B portrait copy)
        for cpu_addr, buf_len in ((0x843A, 97), (0x813A, 81)):
            b9_off = 9 * 8192 + (cpu_addr - 0x8000)
            if len(rle) > buf_len:
                raise RuntimeError(f"MTPO B9 ${cpu_addr:04X} portrait RLE overflow: {len(rle)} > {buf_len}")
            expected_end = prg[b9_off + buf_len - 1]
            if prg[b9_off : b9_off + 4] != bytes.fromhex("41 3d e8 3e") or expected_end != 0x00:
                raise ValueError(f"Unexpected MTPO B9 ${cpu_addr:04X} portrait RLE header/terminator")
            prg[b9_off : b9_off + buf_len] = rle + b"\x00" * (buf_len - len(rle))

    # 4. Bank 8 fight face tiles ($52..$5B = Tyson's two huge head rows)
    # In Evil Link's SP palette: 0=transparent, 1=black, 2=crimson/skin, 3=green/white
    # Give Tyson's Bank 8 head tiles ($52..$5B) Hylian cap brim, pointed bangs, and glowing crimson scowl!
    evil_face_tiles = {
        0x52: [
            "00000011", "00001133", "00113333", "01333331",
            "13333112", "13311222", "11122111", "01221221",
        ],
        0x53: [
            "11111111", "33333333", "33333333", "11333333",
            "22211333", "22222111", "11122222", "12212222",
        ],
        0x54: [
            "11110000", "33331100", "33333110", "33333310",
            "33113331", "11221331", "22211111", "22122210",
        ],
        0x55: [
            "01221122", "01222122", "00122222", "00122222",
            "00012221", "00012222", "00001222", "00000111",
        ],
        0x56: [
            "22221111", "22222222", "22222222", "22211112",
            "11122221", "22222222", "22221111", "11110000",
        ],
        0x57: [
            "22112210", "22122210", "22222100", "22222100",
            "12221000", "22221000", "22210000", "11100000",
        ],
        # Second face expression ($58..$5B)
        0x58: [
            "00000111", "00011333", "00133333", "01333113",
            "13311222", "11122111", "01221221", "01222222",
        ],
        0x59: [
            "11111110", "33333311", "33333331", "33113331",
            "22221111", "11122222", "12212222", "22222222",
        ],
        0x5A: [
            "01222222", "00122222", "00121111", "00012222",
            "00012222", "00001222", "00000111", "00000000",
        ],
        0x5B: [
            "22222220", "22222210", "11112210", "22221100",
            "22221000", "22210000", "11100000", "00000000",
        ],
    }
    for tid, rows in evil_face_tiles.items():
        off = 8 * 4096 + tid * 16
        chr_rom[off : off + 16] = encode_tile(rows)


def _patch_title_chr(chr_rom: bytearray) -> None:
    """Replace Bank 4 'MIKE TYSON'S' tiles ($00..$1F) cleanly just in case referenced."""
    # Clear Bank 4 $00..$1F Tyson block tiles so no stale "MIKE TYSON'S" glyphs appear
    for tid in range(0x00, 0x20):
        off = 4 * 4096 + tid * 16
        chr_rom[off : off + 16] = b"\x00" * 16


def _draw_barba_bust(
    canvas: list[list[str]],
    cx: int,
    top_y: int,
    scale: float,
    c_bg: str,
    c_body: str,
    c_accent: str,
    c_outline: str = "0",
) -> None:
    """Stamp a fierce horned Barba dragon bust onto a 2bpp ASCII canvas."""
    h = len(canvas)
    w = len(canvas[0])

    def put(px: int, py: int, col: str) -> None:
        if 0 <= px < w and 0 <= py < h:
            canvas[py][px] = col

    def ell(rx: float, ry: float, ox: float, oy: float, col: str) -> None:
        for y in range(int(top_y + (oy - ry) * scale) - 1, int(top_y + (oy + ry) * scale) + 2):
            for x in range(int(cx + (ox - rx) * scale) - 1, int(cx + (ox + rx) * scale) + 2):
                dx = (x - (cx + ox * scale)) / (rx * scale)
                dy = (y - (top_y + oy * scale)) / (ry * scale)
                if dx * dx + dy * dy <= 1.0:
                    put(x, y, col)

    # Shoulders / torso
    ell(14, 12, 0, 26, c_outline)
    ell(12, 10, 0, 26, c_body)
    # Gold/white belly plates
    ell(6, 8, 0, 27, c_accent)
    # Neck
    ell(7, 7, 0, 17, c_outline)
    ell(5.5, 6, 0, 17, c_body)
    # Curved dragon horns (left & right)
    for sign in (-1, 1):
        for t in range(10):
            hx = cx + int(sign * (4 + t * 0.7) * scale)
            hy = top_y + int((5 - t * 0.55) * scale)
            put(hx, hy - 1, c_outline)
            put(hx, hy + 1, c_outline)
            put(hx - sign, hy, c_outline)
            put(hx, hy, c_accent)
    # Dragon head & snout
    ell(9, 7.5, 0, 9, c_outline)
    ell(7.5, 6, 0, 9, c_body)
    ell(6, 4.5, 0, 12, c_outline)
    ell(4.5, 3.2, 0, 12, c_body)
    # Fierce eyes & snout ridge
    for sign in (-1, 1):
        ex = cx + int(sign * 3.5 * scale)
        ey = top_y + int(7.5 * scale)
        put(ex, ey, c_accent)
        put(ex - sign, ey - 1, c_outline)
    # Fangs on snout
    for sign in (-1, 1):
        fx = cx + int(sign * 2.5 * scale)
        fy = top_y + int(14 * scale)
        put(fx, fy, c_accent)
    # Raised clawed fists
    for sign in (-1, 1):
        ell(4, 4, sign * 11, 20, c_outline)
        ell(2.8, 2.8, sign * 11, 20, c_body)
        put(cx + int(sign * 11 * scale), top_y + int(17 * scale), c_accent)


def _patch_tape_barbas_chr(
    chr_rom: bytearray,
    prg: bytearray | None = None,
    z2_bytes: bytes | None = None,
) -> None:
    """Replace Doc & Mac's Tale of the Tape portrait with segmented Barba (head + vertical torso)."""
    # Patch Tale of the Tape BG0/BG1 color 3 at Bank 12 $973B ($07->$16) and $973F ($36->$16)
    # so both BG0 and BG1 have crimson ($16) for Barba's scales.
    if prg is not None:
        pal_off = 12 * 8192 + (0x9738 - 0x8000)
        if prg[pal_off + 3] == 0x07:
            prg[pal_off + 3] = 0x16
        if prg[pal_off + 7] == 0x36:
            prg[pal_off + 7] = 0x16

        # Patch Bank 12 $8486..$84D3 (78 bytes): clean 8x10 green box with dedicated Barba tiles
        # ($4C..$53 = 4x2 head, $54..$62 = 3x5 vertical torso, $4A/$4B = BG0/BG1 green, $74/$75 = bottom).
        macro_off = 12 * 8192 + (0x8486 - 0x8000)
        new_macro = bytes([
            0x41, 0x35, 0xE3, 0x4A, 0xE5, 0x4B, 0x41, 0x63, 0x90,                   # r16 (9)
            0x41, 0x35, 0xE2, 0x4A, 0x04, 0x4C, 0xE2, 0x4B, 0x41, 0x63, 0x90,       # r17 (11)
            0x41, 0x35, 0xE2, 0x4A, 0x04, 0x50, 0xE2, 0x4B, 0x41, 0x63, 0x90,       # r18 (11)
            0x42, 0x35, 0x4A, 0x03, 0x54, 0xE4, 0x4B, 0x41, 0x63, 0x90,             # r19 (10)
            0x42, 0x35, 0x4A, 0x03, 0x57, 0xE4, 0x4B, 0x41, 0x63, 0x90,             # r20 (10)
            0x42, 0x35, 0x4A, 0x03, 0x5A, 0xE4, 0x4B, 0x41, 0x63, 0x90,             # r21 (10)
            0x42, 0x35, 0x4A, 0x03, 0x5D, 0xE4, 0x4B, 0x41, 0x63, 0x90,             # r22 (10)
            0xE2, 0x74, 0xE8, 0x75, 0x00, 0x00, 0x00,                               # r23 (7) -> total 78
        ])
        assert len(new_macro) == 78
        prg[macro_off : macro_off + 78] = new_macro

    # Solid green tiles ($4A for BG0 color 2, $4B for BG1 color 1)
    chr_rom[0 * 4096 + 0x4A * 16 : 0 * 4096 + 0x4A * 16 + 16] = encode_tile(["22222222"] * 8)
    chr_rom[0 * 4096 + 0x4B * 16 : 0 * 4096 + 0x4B * 16 + 16] = encode_tile(["11111111"] * 8)
    # Left/right/bottom 1px white box borders
    chr_rom[0 * 4096 + 0x35 * 16 : 0 * 4096 + 0x35 * 16 + 16] = encode_tile(["12222222"] * 8)
    chr_rom[0 * 4096 + 0x63 * 16 : 0 * 4096 + 0x63 * 16 + 16] = encode_tile(["11111112"] * 8)
    chr_rom[0 * 4096 + 0x74 * 16 : 0 * 4096 + 0x74 * 16 + 16] = encode_tile(["22222222"] * 7 + ["11111111"])
    chr_rom[0 * 4096 + 0x75 * 16 : 0 * 4096 + 0x75 * 16 + 16] = encode_tile(["11111111"] * 7 + ["22222222"])

    # Build Barba head (32x16) + segmented vertical torso (16x40) from boss_art.py
    # Canvas covers tx=2..6 (40px wide, x=0..39) x ty=1..6 (48px tall, y=0..47) -> r17..r22, cols 4..8
    # Note: r17..r18 (ty=1..2) has tx=3..6 (4x2 = $4C..$53); r19..r22 (ty=3..6) has tx=2..4 (3x4 = $54..$5F).
    # We'll render on the full 80x64 box canvas and slice out $4C..$62!
    grid = [
        [None, None, None, None, None, None, None, None, None, None],
        [None, None, None, 0x4C, 0x4D, 0x4E, 0x4F, None, None, None],
        [None, None, None, 0x50, 0x51, 0x52, 0x53, None, None, None],
        [None, None, 0x54, 0x55, 0x56, None, None, None, None, None],
        [None, None, 0x57, 0x58, 0x59, None, None, None, None, None],
        [None, None, 0x5A, 0x5B, 0x5C, None, None, None, None, None],
        [None, None, 0x5D, 0x5E, 0x5F, None, None, None, None, None],
        [None, None, None, None, None, None, None, None, None, None],
    ]

    # Store intermediate pixel values ('b'=bg, 'w'=white, 'k'=black, 'r'=crimson) on 80x64 canvas
    raw = [["b"] * 80 for _ in range(64)]
    if z2_bytes is not None:
        from boss_art import source_head, source_pair

        head = [row[::-1] for row in source_head(z2_bytes, "closed")]  # 32x16 right-facing
        neck = [
            "".join((source_pair(z2_bytes, 0xA0)[y], source_pair(z2_bytes, 0xA2)[y]))[::-1]
            for y in range(16)
        ]

        # Place segmented vertical torso first (x=21..36, y=22..55) so head overlaps neck cleanly
        for y in range(22, 56):
            sway = (0, -1, 0, 1)[((y - 22) // 8) % 4]
            nrow = neck[(y - 22) % 16]
            for ix, ch in enumerate(nrow):
                if ch != "0":
                    raw[y][22 + sway + ix] = {"1": "r", "2": "r", "3": "w"}[ch]

        # Place native 32x16 Barba head at x=24..55, y=8..23 (inside tx=3..6, ty=1..2)
        for iy, hrow in enumerate(head):
            for ix, ch in enumerate(hrow):
                if ch != "0":
                    raw[8 + iy][24 + ix] = {"1": "r", "2": "r", "3": "w"}[ch]

        # Add 1px black ('k') outline around Barba against the green background
        outlined = [list(r) for r in raw]
        for y in range(1, 63):
            for x in range(1, 79):
                if raw[y][x] == "b":
                    if any(raw[y + dy][x + dx] != "b" for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                        outlined[y][x] = "k"
        raw = outlined

    # Map ('b','w','k','r') to BG0 (cols 2..5, rows 16..19; cols 2..3, rows 20..23) or BG1
    for ty in range(8):
        for tx in range(10):
            tid = grid[ty][tx]
            if tid is None:
                continue
            col = 2 + tx
            row = 16 + ty
            is_bg1 = (col >= 6) or (col >= 4 and row >= 20)
            cmap = (
                {"b": "1", "w": "2", "k": "0", "r": "3"}
                if is_bg1
                else {"b": "2", "w": "1", "k": "0", "r": "3"}
            )
            sub = [
                "".join(cmap[raw[ty * 8 + py][tx * 8 + px]] for px in range(8))
                for py in range(8)
            ]
            off = 0 * 4096 + tid * 16
            chr_rom[off : off + 16] = encode_tile(sub)

    # Clear Doc & Mac's Tale of the Tape OAM overlay tiles in CHR Bank 5 so the Barba
    # in Bank 0 BG is not covered by Doc & Mac's sprites.
    for tid in list(range(0x03, 0x10)) + list(range(0xDA, 0xE5)) + [0xE9, 0xED, 0xEE, 0xEF, 0xF9]:
        off = 5 * 4096 + tid * 16
        chr_rom[off : off + 16] = b"\x00" * 16


def _patch_tape_opponents_chr(chr_rom: bytearray) -> None:
    """Draw Stalfos (Glass Joe slot) and Wizzrobe (Great Tiger slot) into Bank 6."""
    # Bank 6 BG3 palette: 0=black, 1=white ($30), 2=blue ring bg ($12), 3=pink/accent ($35)
    # Clean Glass Joe's ring ropes ($03,$04), corner post ($05..$07), pink body ($15..$1B), and $FC
    solid_blue = encode_tile(["22222222"] * 8)
    left_border = encode_tile(["12222222"] * 8)
    right_border = encode_tile(["22222221"] * 8)
    bottom_border = encode_tile(["22222222"] * 7 + ["11111111"])
    for tid in (0x01, 0x03):
        chr_rom[6 * 4096 + tid * 16 : 6 * 4096 + tid * 16 + 16] = left_border
    for tid in (0x02, 0x07):
        chr_rom[6 * 4096 + tid * 16 : 6 * 4096 + tid * 16 + 16] = right_border
    for tid in (0x04, 0x05, 0x06, 0x15, 0x16, 0x17, 0x18, 0xFC):
        chr_rom[6 * 4096 + tid * 16 : 6 * 4096 + tid * 16 + 16] = solid_blue
    for tid in (0x09, 0x19, 0x1A, 0x1B):
        chr_rom[6 * 4096 + tid * 16 : 6 * 4096 + tid * 16 + 16] = bottom_border
    chr_rom[6 * 4096 + 0x08 * 16 : 6 * 4096 + 0x08 * 16 + 16] = encode_tile(["12222222"] * 7 + ["11111111"])
    chr_rom[6 * 4096 + 0x0A * 16 : 6 * 4096 + 0x0A * 16 + 16] = encode_tile(["22222221"] * 7 + ["11111111"])

    # 1. Stalfos (tiles $0B..$14, 3x4 grid = 24x32, cols 4..6 rows 10..13)
    stalfos_grid = [
        [0x0B, 0x0C, None],
        [0x0D, 0x0E, None],
        [0x0F, 0x10, 0x11],
        [0x12, 0x13, 0x14],
    ]
    stalfos_canvas = [
        "22220000" "00000000" "22222222",
        "22001111" "11111100" "22222222",
        "20111111" "11111110" "22222222",
        "01111111" "11111111" "02222222",
        "01113111" "11131111" "02222222",
        "01111111" "11111111" "02222222",
        "01100011" "11000111" "02222222",
        "01000001" "10000011" "02222222",
        # y=8..15 (eye sockets + cheekbones + nasal)
        "01000001" "10000011" "02222222",
        "01003001" "10030011" "02222222",
        "01100011" "11000111" "02222222",
        "20111110" "01111110" "22222222",
        "20111100" "00111110" "22222222",
        "22011110" "01111102" "22222222",
        "22011111" "11111102" "22222222",
        "22010101" "01010102" "22222222",
        # y=16..23 (grinning jaw + bony neck)
        "22010101" "01010102" "22222222",
        "22011111" "11111102" "22222222",
        "22201111" "11111022" "22222222",
        "22220000" "00000222" "22222222",
        "22222011" "11102222" "22222222",
        "22222013" "31102222" "22222222",
        "22200011" "11100022" "22222222",
        "20011111" "11111100" "22222222",
        # y=24..31 (clavicle + ribcage)
        "01111100" "00111110" "22222222",
        "01100011" "11000110" "22222222",
        "01001111" "11110010" "22222222",
        "01011100" "00111010" "22222222",
        "01011011" "11011010" "22222222",
        "01000011" "11000010" "22222222",
        "01111110" "01111110" "22222222",
        "01110000" "00001110" "22222222",
    ]
    _draw_canvas_into_chr(chr_rom, 6, stalfos_grid, stalfos_canvas)

    # 2. Wizzrobe (Great Tiger slot: Bank 6 $AD..$CD, 7x6 grid = 56x48, cols 21..27 rows 8..13)
    wizz_grid = [
        [0xAD, 0xAE, 0xAF, None, None, None, None],
        [0xB0, 0xB1, 0xB2, 0xB3, None, None, None],
        [0xB4, 0xB5, 0xB6, 0xB7, 0xB8, None, 0xCA],
        [0xB9, 0xBA, 0xBB, 0xBC, None, None, 0xBD],
        [0xBE, 0xBF, 0xC0, 0xC1, 0xC2, 0xC3, 0xC4],
        [0xC5, 0xC6, 0xC7, None, None, 0xC9, 0xC8],
    ]
    # Also clear $CB, $CC, $CD (bottom robe hem) to blue/robe
    wizz_canvas = [["2"] * 56 for _ in range(48)]

    def wput(x: int, y: int, c: str) -> None:
        if 0 <= x < 56 and 0 <= y < 48:
            wizz_canvas[y][x] = c

    # Pointed wizard hood (triangle y=0..18, centered at x=16)
    for y in range(19):
        half = 1 + (y * 13) // 18
        for x in range(16 - half, 16 + half + 1):
            if x == 16 - half or x == 16 + half or y == 0:
                wput(x, y, "0")
            elif x <= 16 - half + 2 or y >= 16:
                wput(x, y, "1")  # white hood highlight / brim
            else:
                wput(x, y, "3")  # magenta arcane hood

    # Deep black shadowed face inside hood (y=15..26, x=8..24) + glowing white eyes
    for y in range(15, 27):
        for x in range(8, 25):
            if abs(x - 16) <= 8 - (y - 15) // 4:
                wput(x, y, "0")
    for ex in (12, 13, 19, 20):
        wput(ex, 20, "1")
        wput(ex, 21, "3")

    # Flowing arcane robes (y=27..47, x=4..28)
    for y in range(27, 48):
        half = 10 + (y - 27) // 4
        for x in range(16 - half, 16 + half + 1):
            if x == 16 - half or x == 16 + half:
                wput(x, y, "0")
            elif abs(x - 16) <= 2:
                wput(x, y, "1")  # white arcane sash
            elif (x + y) % 5 == 0:
                wput(x, y, "1")
            else:
                wput(x, y, "3")

    # Floating arcane staff & glowing magic orb on right (x=36..52, y=16..47)
    for y in range(22, 48):
        wput(44, y, "0")
        wput(45, y, "1")
        wput(46, y, "0")
    # Glowing orb (cx=45, cy=18, r=5)
    for y in range(13, 24):
        for x in range(40, 51):
            d2 = (x - 45) ** 2 + (y - 18) ** 2
            if d2 <= 25:
                wput(x, y, "0" if d2 >= 18 else ("1" if d2 <= 6 else "3"))

    _draw_canvas_into_chr(chr_rom, 6, wizz_grid, ["".join(r) for r in wizz_canvas])
    # Clean bottom hem $CB, $CC, $CD
    for tid in (0xCB, 0xCC, 0xCD):
        off = 6 * 4096 + tid * 16
        chr_rom[off : off + 16] = encode_tile(["03311330"] * 8)


# ---------------------------------------------------------------------------
# Palettes (PRG Banks 0..5) and Text (PRG Bank 9 & Bank 12)
# ---------------------------------------------------------------------------

# Opponent sprite palettes (16 bytes per round = SP0..SP3, 4 bytes each, index 0 = mat)
# Format: [(c1, c2, c3) for SP0, SP1, SP2, SP3]
_Z2_OPP_SPRITE_PALETTES: dict[int, list[tuple[int, int, int]]] = {
    # 00 Stalfos (Glass Joe): bone white, gold trim, black outlines
    0: [(0x30, 0x27, 0x0F), (0x30, 0x16, 0x0F), (0x27, 0x30, 0x0F), (0x30, 0x17, 0x0F)],
    # 01 Horsehead (Von Kaiser): crimson armor, steel gray, black
    1: [(0x16, 0x10, 0x0F), (0x27, 0x16, 0x0F), (0x16, 0x30, 0x0F), (0x16, 0x26, 0x0F)],
    # 02 Helmethead (Piston Honda 1): bronze/gold helmet, crimson plume, black
    2: [(0x27, 0x30, 0x0F), (0x27, 0x16, 0x0F), (0x16, 0x30, 0x0F), (0x17, 0x27, 0x0F)],
    # 03 Carock (Don Flamenco 1): arcane purple robe, gold, white
    3: [(0x14, 0x30, 0x0F), (0x14, 0x27, 0x0F), (0x24, 0x30, 0x0F), (0x16, 0x27, 0x0F)],
    # 04 Iron Knuckle (King Hippo): royal cobalt armor, gold/red shield, black
    4: [(0x12, 0x30, 0x0F), (0x12, 0x27, 0x0F), (0x27, 0x16, 0x0F), (0x16, 0x30, 0x0F)],
    # 05 Wizzrobe (Great Tiger): dark violet cloak, cyan flash, gold
    5: [(0x14, 0x21, 0x0F), (0x24, 0x21, 0x0F), (0x14, 0x30, 0x0F), (0x27, 0x24, 0x0F)],
    # 06 Gooma (Bald Bull 1): iron gray, crimson trim, gold chain
    6: [(0x10, 0x30, 0x0F), (0x10, 0x16, 0x0F), (0x27, 0x30, 0x0F), (0x16, 0x27, 0x0F)],
    # 07 Helmethead II (Piston Honda 2)
    7: [(0x27, 0x30, 0x0F), (0x27, 0x16, 0x0F), (0x16, 0x30, 0x0F), (0x17, 0x27, 0x0F)],
    # 08 Dark Lizalfos (Soda Popinski): emerald scales, crimson crest, black
    8: [(0x19, 0x30, 0x06), (0x19, 0x16, 0x06), (0x16, 0x27, 0x06), (0x2A, 0x16, 0x06)],
    # 09 Gooma II (Bald Bull 2)
    9: [(0x10, 0x30, 0x0F), (0x10, 0x16, 0x0F), (0x27, 0x30, 0x0F), (0x16, 0x27, 0x0F)],
    # 10 Carock II (Don Flamenco 2)
    10: [(0x14, 0x30, 0x0F), (0x14, 0x27, 0x0F), (0x24, 0x30, 0x0F), (0x16, 0x27, 0x0F)],
    # 11 Rebonack (Mr. Sandman): obsidian armor, gold lance/gloves, crimson
    11: [(0x2D, 0x30, 0x0F), (0x27, 0x16, 0x0F), (0x2D, 0x27, 0x0F), (0x16, 0x27, 0x0F)],
    # 12 Thunderbird (Super Macho Man): storm blue, crimson, gold
    12: [(0x11, 0x30, 0x0F), (0x11, 0x16, 0x0F), (0x11, 0x27, 0x0F), (0x27, 0x16, 0x0F)],
    # 13 Evil Link (Mike Tyson): dark obsidian outline, pale skin, Hylian green, crimson eyes/gloves!
    13: [(0x0F, 0x36, 0x1A), (0x0F, 0x16, 0x29), (0x0F, 0x27, 0x16), (0x0F, 0x16, 0x30)],
}


def _patch_palettes(prg: bytearray) -> None:
    """Patch all 14 opponents' BG3 (Barba crimson/black/gold) and SP0..SP3 (Z2/Evil Link)."""
    # Intro portrait SP0 palette (Bank 12 $9971..$9973): [07, 17, 8F] -> [8F, 27, 1A]
    # Maps Link OAM colors: 1=black ($0F), 2=skin ($27), 3=Hylian green ($1A) for cap & tunic!
    intro_sp0_off = 12 * 8192 + (0x9971 - 0x8000)
    if bytes(prg[intro_sp0_off : intro_sp0_off + 3]) != bytes((0x07, 0x17, 0x8F)):
        raise ValueError(f"Unexpected Intro SP0 palette bytes at B12 $9971: {prg[intro_sp0_off:intro_sp0_off+3].hex()}")
    prg[intro_sp0_off : intro_sp0_off + 3] = bytes((0x8F, 0x27, 0x1A))

    # Intro "LINK" OAM SP1 palette (Bank 12 $9975): $3A (pale green) -> $30 (crisp white outline, fill stays $1A green)
    if prg[intro_sp0_off + 4] != 0x3A:
        raise ValueError(f"Unexpected Intro SP1 palette byte at B12 $9975: {prg[intro_sp0_off + 4]:02x}")
    prg[intro_sp0_off + 4] = 0x30

    b13 = 13 * 8192
    for opp in range(14):
        b_idx = prg[b13 + 0x0D1 + opp * 2]
        slot_off = prg[b13 + 0x0D1 + opp * 2 + 1]
        hdr_off = b_idx * 8192 + slot_off
        p_pal = prg[hdr_off + 6] | (prg[hdr_off + 7] << 8)
        r_off = b_idx * 8192 + (p_pal - 0x8000)
        sp_pal = _Z2_OPP_SPRITE_PALETTES[opp]
        mat = prg[r_off]
        # BG3 = Barba: [mat, crimson $16, black $8F ($0F), gold/ivory $38]
        prg[r_off + 12] = mat
        prg[r_off + 13] = 0x16
        prg[r_off + 14] = 0x8F
        prg[r_off + 15] = 0x38
        # SP0..SP3 = Z2 boss / Evil Link colors
        for si, (c1, c2, c3) in enumerate(sp_pal):
            s_off = r_off + 16 + si * 4
            prg[s_off] = mat
            prg[s_off + 1] = c1
            prg[s_off + 2] = c2
            prg[s_off + 3] = c3


def _patch_text_exact(prg: bytearray, bank: int, cpu_addr: int, old: str, new: str) -> None:
    assert len(old) == len(new), f"Length mismatch: {old!r} vs {new!r}"
    off = bank * 8192 + (cpu_addr - 0x8000)
    expected = encode_mtpo_text(old)
    actual = bytes(prg[off : off + len(expected)])
    if actual != expected:
        raise ValueError(
            f"Unexpected text at B{bank:02d} ${cpu_addr:04X}: got {actual.hex()}, expected {expected.hex()} ({old!r})"
        )
    prg[off : off + len(expected)] = encode_mtpo_text(new)


def _patch_texts(prg: bytearray) -> None:
    """Apply exact-length Z2 / Barba / Evil Link text replacements in Banks 9 & 12."""
    # Bank 9 opponent cards & intro dialogue
    b9_patches = [
        (0x809C, "MIKE TYSON,", "EVIL LINK, "),
        (0x81B6, "MIKE IS WAITING", "LINK IS WAITING"),
        (0x838F, "PISTON", "HELMET"),
        (0x8398, "HONDA", "HEAD "),
        (0x83A1, "TOKYO:", "PALACE"),
        (0x83AA, "JAPAN", "THREE"),
        (0x849D, "MIKE TYSON", "EVIL LINK "),
        (0x84AB, "CATSKILL:", "HYRULE:  "),
        (0x84B7, "N", "D"),
        (0x84B9, "Y", "K"),
        (0x8587, "SODA", "DARK"),
        (0x858E, "POPINSKI", "LIZALFOS"),
        (0x859A, "MOSCOW:", "DEATH: "),
        (0x868B, "SUPER", "GREAT"),
        (0x8693, "MACHO MAN", "THUNDERBD"),
        (0x869F, "HOLLYWOOD:", "GREAT:    "),
        (0x877A, "MR", "RE"),
        (0x877D, "SANDMAN", "BONACK "),
        (0x8788, "PHILADEL!", "ISLAND:  "),
        (0x8794, "PHIA:PA", "PALACE "),
        (0x8862, "BALD BULL", "GOOMA    "),
        (0x886F, "ISTANBUL:", "OCEAN:   "),
        (0x887B, "TURKEY", "PALACE"),
        (0x8941, "GREAT", "WIZZ "),
        (0x8949, "TIGER", "ROBE "),
        (0x8952, "BOMBAY:", "MAZE:  "),
        (0x895C, "INDIA", "PAL 4"),
        (0x8A34, "VON KAISER", "HORSEHEAD "),
        (0x8A42, "BERLIN:", "PARAPA:"),
        (0x8A4C, "GERMANY", "PALACE "),
        (0x8B22, "KING HIPPO", "IRON KNUCK"),
        (0x8B2F, "HIPPO", "MIDOR"),
        (0x8B37, "ISLAND:", "SWAMP: "),
        (0x8B41, "SOUTH", "PALAC"),
        (0x8B49, "PACIFIC", "E TWO  "),
        (0x8C00, "DON", "CAR"),
        (0x8C06, "FLAMENCO", "OCK     "),
        (0x8C12, "MADRID:", "MAZE:  "),
        (0x8C1C, "SPAIN", "PAL 4"),
        (0x8CD3, "GLASS JOE", "STALFOS  "),
        (0x8CE0, "PARIS:", "PARAPA"),
        (0x8CE9, "FRANCE", "CRYPT "),
    ]
    for addr, old, new in b9_patches:
        _patch_text_exact(prg, 9, addr, old, new)

    # Bank 12 Title, Profile, Credits, and Ring Announcer
    b12_patches = [
        (0x8874, "MIKE TYSON'S", "  BARBA'S   "),
        (0x83FF, "LITTLE MAC", "BARBA     "),
        (0x89B1, "GLASS JOE", "STALFOS  "),
        (0x89BC, "VON KAISER", "HORSEHEAD "),
        (0x89C9, "KING HIPPO", "IRON KNUCK"),
        (0x89D5, "PISTON HONDA", "HELMETHEAD  "),
        (0x89E4, "GREAT TIGER", "WIZZROBE   "),
        (0x89F1, "BALD BULL", "GOOMA    "),
        (0x8A00, "SANDMAN", "REBONAK"),
        (0x8A09, "DON FLAMENCO", "CAROCK      "),
        (0x8A1E, "SUPER", "GREAT"),
        (0x8A26, "POPINSKI", "LIZALFOS"),
        (0x8A30, "MACHO MAN", "THUNDRBRD"),
        (0x8A54, "MIKE TYSON", "EVIL LINK "),
        (0x8D92, "KID DYNAMITE:", "DARK KNIGHT: "),
        (0x8DA3, "MIKE TYSON", "EVIL LINK "),
        (0x90F9, "LITTLE MAC.", "LORD BARBA."),
    ]
    for addr, old, new in b12_patches:
        _patch_text_exact(prg, 12, addr, old, new)

    # Bank 12 $8511..$853A (42-byte Tale of the Tape Barba stats macro):
    #   FROM BRONX / N.Y. / AGE: 17  / WEIGHT:107
    # ->FROM THE   / LAVA / AGE: ??  / WEIGHT:99999
    tape_stats_off = 12 * 8192 + (0x8511 - 0x8000)
    expected_tape_stats = (
        bytes([0x4A]) + encode_mtpo_text("FROM BRONX")
        + bytes([0x90, 0xF6, 0x44, 0x18, 0x25, 0x23, 0x25])  # N.Y.
        + bytes([0x90, 0x48, 0x0B, 0x11, 0x0F, 0x2C, 0xFF, 0x02, 0x08, 0xFF])  # AGE: 17 
        + bytes([0x90, 0xF7, 0x90, 0x4A, 0x21, 0x0F, 0x13, 0x11, 0x12, 0x1E, 0x2C, 0x02, 0x01, 0x08])  # WEIGHT:107
    )
    new_tape_stats = (
        bytes([0x48]) + encode_mtpo_text("FROM THE")
        + bytes([0x90, 0xF6, 0x44]) + encode_mtpo_text("LAVA")
        + bytes([0x90, 0x48, 0x0B, 0x11, 0x0F, 0x2C, 0xFF, 0x30, 0x30, 0xFF])  # AGE: ?? 
        + bytes([0x90, 0xF7, 0x90, 0x4C, 0x21, 0x0F, 0x13, 0x11, 0x12, 0x1E, 0x2C]) + encode_mtpo_text("99999")
    )
    assert len(expected_tape_stats) == len(new_tape_stats) == 42
    actual_tape = bytes(prg[tape_stats_off : tape_stats_off + 42])
    if actual_tape != expected_tape_stats:
        raise ValueError(f"Unexpected Tale of the Tape stats at B12 $8516: {actual_tape.hex()}")
    prg[tape_stats_off : tape_stats_off + 42] = new_tape_stats


def apply_mtpo_mod_art(prg: bytearray, chr_rom: bytearray, z2_bytes: bytes | None = None) -> None:
    """Apply Barba, Title, Evil Link, and Zelda II opponent mods to MTPO PRG & CHR."""
    _patch_title_chr(chr_rom)
    _patch_barba_chr(chr_rom)
    _patch_evil_link_chr(chr_rom, z2_bytes, prg=prg)
    _patch_tape_barbas_chr(chr_rom, prg, z2_bytes)
    _patch_tape_opponents_chr(chr_rom)
    _patch_palettes(prg)
    _patch_texts(prg)
