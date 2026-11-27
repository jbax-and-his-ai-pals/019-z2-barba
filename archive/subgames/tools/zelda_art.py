"""Compile Barba, fireball, and Villainous Link CHR-RAM sprites for The Legend of Barba (Zelda 1)."""
from __future__ import annotations

from pathlib import Path

from boss_art import source_head
from nes import decode_tile, encode_tile, write_png

# Barba NES sprite palette 0: $0F (transparent), $16 (crimson), $27 (amber-gold), $30 (cream-white)
BARBA_PALETTE = [(20, 22, 28), (196, 40, 28), (248, 160, 48), (252, 244, 212)]
# Villainous Dark/Crimson Link palette: $0F (transparent), $06 (dark maroon), $16 (crimson), $36 (pale/silver)
VILLAIN_PALETTE = [(20, 22, 28), (104, 16, 28), (216, 40, 32), (244, 212, 200)]


def _rows_to_pair(rows16x8: list[str]) -> bytes:
    """Encode an 8x16 sprite (16 rows of 8 chars '0'..'3') as 32 CHR bytes (top tile + bottom tile)."""
    assert len(rows16x8) == 16 and all(len(r) == 8 for r in rows16x8)
    return encode_tile(rows16x8[:8]) + encode_tile(rows16x8[8:])


def _split_16x16(grid16x16: list[str]) -> bytes:
    """Encode a 16x16 metasprite (16 rows of 16 chars) as two 8x16 pairs (64 bytes)."""
    assert len(grid16x16) == 16 and all(len(r) == 16 for r in grid16x16)
    left = [r[:8] for r in grid16x16]
    right = [r[8:] for r in grid16x16]
    return _rows_to_pair(left) + _rows_to_pair(right)


def _hflip(rows: list[str]) -> list[str]:
    return [r[::-1] for r in rows]


def _extract_barba_side_head(z2_bytes: bytes, jaw: str = 'closed') -> list[str]:
    """Extract and adapt Barba's real boss head from z2.nes into a 12x10 RIGHT-facing head."""
    # source_head returns 16 rows x 32 cols facing LEFT. Flip horizontally to face RIGHT.
    src = [row[::-1] for row in source_head(z2_bytes, jaw)]
    # Resample 32x16 -> 12x10 keeping eye, horns, and jaw silhouette crisp.
    out = []
    for y in range(10):
        sy = min(15, (y * 16 + 5) // 10)
        row = ''.join(src[sy][min(31, (x * 32 + 6) // 12)] for x in range(12))
        out.append(row)
    return out


def _compose_side_barba(head12x10: list[str], step: int, jaw_open: bool) -> list[str]:
    """Build a 16x16 RIGHT-facing Barba sprite combining the z2.nes head with dragon body & claws."""
    canvas = [['0'] * 16 for _ in range(16)]
    # Blit 12x10 head at top-right (x=4..15, y=0..9)
    for y in range(10):
        for x in range(12):
            if head12x10[y][x] != '0':
                canvas[y][4 + x] = head12x10[y][x]
    # Add dorsal horn crest & bright eye accent on the head
    canvas[1][6] = '3'
    canvas[2][7] = '2'
    canvas[3][10] = '3'  # fierce white eye
    canvas[3][11] = '1'
    if not jaw_open:
        # Cleanly close snout/jaw so walk vs firebreath contrast is unmistakable
        for x in range(10, 16):
            canvas[6][x] = '2' if x >= 12 else '1'
            canvas[7][x] = '1' if x <= 14 else '0'
        canvas[8][10] = '1'
        canvas[8][11] = '1'
        for x in range(12, 16):
            canvas[8][x] = '0'
    else:
        canvas[6][13] = '2'
        canvas[6][14] = '3'
        canvas[7][12] = '1'
        canvas[8][13] = '2'
        canvas[8][14] = '3'
    # Serpentine winged dragon torso, curved tail, and stepping claws
    body_rows = [
        (5,  '001112..........'),
        (6,  '011221..........'),
        (7,  '121121..........'),
        (8,  '11122211........'),
        (9,  '012112211.......'),
        (10, '0011222111......'),
        (11, '0112221121......'),
        (12, '1211121111......'),
        (13, '11001121011.....'),
    ]
    for y, pat in body_rows:
        for x, ch in enumerate(pat):
            if ch in '123' and canvas[y][x] == '0':
                canvas[y][x] = ch
    # Stepping legs/claws (row 13..15)
    if step == 0:
        legs = [
            (13, '1000111001100000'),
            (14, '0000121000120000'),
            (15, '0000303000033000'),
        ]
    elif step == 1:
        legs = [
            (13, '0100110011100000'),
            (14, '0001210001210000'),
            (15, '0003030003030000'),
        ]
    else:  # attack lunge
        legs = [
            (13, '1001110001110000'),
            (14, '0012100000121000'),
            (15, '0030300000033000'),
        ]
    for y, pat in legs:
        canvas[y] = list(pat)
    return [''.join(r) for r in canvas]


# Hand-crafted 16x16 top-down Barba DOWN, UP, and TRIFORCE-HOLD sprites
# Palette: 1=Crimson scales, 2=Amber/gold snout/horns/belly, 3=Cream-white fangs/eyes/horn-tips
BARBA_DOWN_WALK = [
    '..3..........3..',
    '..23..1111..32..',
    '..122112211221..',
    '..111121121111..',
    '.11131111113111.',
    '.11121111112111.',
    '..112222222211..',
    '..122322223221..',
    '.11111222211111.',
    '1211122332211121',
    '111.12222221.111',
    '3.1.11222211.1.3',
    '....11122111....',
    '....111..111....',
    '...121....121...',
    '...3.3....3.3...',
]

BARBA_DOWN_ATTACK = [
    '..3..........3..',
    '..23..1111..32..',
    '..122112211221..',
    '..111121121111..',
    '.11131111113111.',
    '.11121111112111.',
    '..112222222211..',
    '..123000000321..',
    '.11120233202111.',
    '1211203333021121',
    '111.12233221.111',
    '3.1.11222211.1.3',
    '....11122111....',
    '...121....121...',
    '...3.3....3.3...',
    '................',
]

BARBA_UP_WALK = [
    '....3......3....',
    '...2111111112...',
    '..112212212211..',
    '..111112211111..',
    '.11111233211111.',
    '.12111122111121.',
    '..111122221111..',
    '.11112233221111.',
    '121.11122111.121',
    '11..11222211..11',
    '3...11122111...3',
    '....11122111....',
    '....12111121....',
    '...111.22.111...',
    '...3.3.12.3.3...',
    '........3.......',
]

BARBA_UP_ATTACK = [
    '...3........3...',
    '..211112211112..',
    '..112213312211..',
    '.11111222211111.',
    '.12111233211121.',
    '111.11122111.111',
    '3...11222211...3',
    '....11233211....',
    '...1112222111...',
    '..121112211121..',
    '..3.11122111.3..',
    '....11122111....',
    '....121..121....',
    '...111.22.111...',
    '...3.3.12.3.3...',
    '........3.......',
]

# Left 8x16 of symmetrical Barba holding Triforce overhead (tile $78; right half is H-flipped)
BARBA_HOLD_LEFT = [
    '....3...',
    '....23..',
    '...12211',
    '...11112',
    '..111311',
    '..111211',
    '.1211222',
    '.3111232',
    '..111122',
    '...11222',
    '...11122',
    '....1112',
    '....1111',
    '...121..',
    '...3.3..',
    '........',
]

# Flame-crowned Fireball (8x16, vertical pointing UP at tile $20; horizontal pointing RIGHT at tile $82)
FIREBALL_VERT = [
    '........',
    '...33...',
    '..2332..',
    '.123321.',
    '.123321.',
    '.122221.',
    '..1221..',
    '.112211.',
    '.122221.',
    '..1211..',
    '..1221..',
    '...12...',
    '..1.11..',
    '...1.1..',
    '....1...',
    '........',
]

FIREBALL_HORIZ = [
    '........',
    '........',
    '........',
    '........',
    '..1...1.',
    '.1.11221',
    '11222332',
    '.1223333',
    '11222332',
    '.1.11221',
    '..1...1.',
    '........',
    '........',
    '........',
    '........',
    '........',
]

# Fiery ember burst (8x16 at $62 and $64)
EMBER_SPARK_A = [
    '..1..1..',
    '.2.3..2.',
    '..3223..',
    '1.2332.1',
    '..2332..',
    '.3.22.3.',
    '1..1..1.',
    '........',
    '..1..1..',
    '.2.3..2.',
    '..3223..',
    '1.2332.1',
    '..2332..',
    '.3.22.3.',
    '1..1..1.',
    '........',
]

EMBER_SPARK_B = [
    '.1....1.',
    '..2..2..',
    '.2.33.2.',
    '..3223..',
    '.2.33.2.',
    '..2..2..',
    '.1....1.',
    '........',
    '.1....1.',
    '..2..2..',
    '.2.33.2.',
    '..3223..',
    '.2.33.2.',
    '..2..2..',
    '.1....1.',
    '........',
]

# 32x32 Villainous Dark/Crimson Link boss (replaces Ganon in Level 9, tiles $C0..$E7)
# Palette: 1=Dark maroon cloak/hair, 2=Crimson tunic/cape/eyes, 3=Pale skin / silver sword!
# Left 16x32 half (symmetric frames $D0..$E7; right half is H-flipped by Ganon renderer)
VILLAIN_HALF_IDLE = [
    '.........1111111',
    '........11222222',
    '........11222222',
    '.......112222222',
    '......1111111111',
    '......1133331111',
    '.....11332233111',
    '.....11333333111',
    '......1133333111',
    '.......111111111',
    '......1122222222',
    '.....12222112222',
    '....122211331122',
    '...1222112222112',
    '..12221122332211',
    '..12211222332221',
    '..12112222222221',
    '..11.12222222222',
    '.11..12221111222',
    '.1...12211331122',
    '.....12112222112',
    '.....11122222211',
    '......1122222222',
    '......1122222222',
    '......1111111111',
    '.......111221111',
    '.......1122211..',
    '.......111111...',
    '......1122211...',
    '......111111....',
    '.....111111.....',
    '.....11111......',
]

# Attacking / Casting 32x32 half (arms raised, glowing dark aura)
VILLAIN_HALF_CAST = [
    '..3......1111111',
    '..33....11222222',
    '..233...11222222',
    '..223..112222222',
    '...2211111111111',
    '...1221133331111',
    '..12211332233111',
    '..12111333333111',
    '..121.1133333111',
    '..11...111111111',
    '......1122222222',
    '.....12222112222',
    '....122211331122',
    '...1222112222112',
    '..12221122332211',
    '..12211222332221',
    '..12112222222221',
    '..11.12222222222',
    '.11..12221111222',
    '.1...12211331122',
    '.....12112222112',
    '.....11122222211',
    '......1122222222',
    '......1122222222',
    '......1111111111',
    '.......111221111',
    '......1122211...',
    '......111111....',
    '.....1122211....',
    '.....111111.....',
    '....111111......',
    '....11111.......',
]

# Full 32x32 Villainous Link Sword-and-Shield pose (frame 0: $C0..$CE)
# Left 16 cols = Shield arm; Right 16 cols = Raised Dark Sword!
VILLAIN_FULL_SWORD_32X32 = [
    '.........11111.............3....',
    '........11222211...........33...',
    '........11222222111........33...',
    '.......11222222222211......33...',
    '......11222222222222211....33...',
    '......111111111111111111...33...',
    '.....1133331111113333111...33...',
    '.....1133223311332233111...33...',
    '.....1133333311333333111...33...',
    '......113333333333333111...23...',
    '.......1111111111111111....23...',
    '......112222222222222211..2222..',
    '..11112222211111122222211..22...',
    '.1333122211333333112222121.33...',
    '13223122112222222211222112331...',
    '1323312112233333322112211221....',
    '132231112223333332221121121.....',
    '133331.12222222222221.1111......',
    '.13331.12221111112221...........',
    '..1111.12211333311221...........',
    '.......12112222221121...........',
    '.......11122222222111...........',
    '........112222222211............',
    '........112222222211............',
    '........111111111111............',
    '........111221122111............',
    '........11222..22211............',
    '........11111..11111............',
    '.......112221..122211...........',
    '.......111111..111111...........',
    '......111111....111111..........',
    '......11111......11111..........',
]


def _encode_quadrant_16x16(rows16x16: list[str]) -> bytes:
    return _split_16x16([r.replace('.', '0') for r in rows16x16])


def build_barba_player_tiles(z2_bytes: bytes) -> dict[str, bytes]:
    """Build replacement CHR tile blocks for Barba, fireball breath, and Villainous Link."""
    head_closed = _extract_barba_side_head(z2_bytes, 'closed')
    head_open = _extract_barba_side_head(z2_bytes, 'open')

    right_w0 = _compose_side_barba(head_closed, 0, False)
    right_w1 = _compose_side_barba(head_closed, 1, False)
    right_atk = _compose_side_barba(head_open, 2, True)

    down_w = [r.replace('.', '0') for r in BARBA_DOWN_WALK]
    down_a = [r.replace('.', '0') for r in BARBA_DOWN_ATTACK]
    up_w = [r.replace('.', '0') for r in BARBA_UP_WALK]
    up_a = [r.replace('.', '0') for r in BARBA_UP_ATTACK]

    # Tiles $00..$1B (14 pairs = 448 bytes at Bank 2 $807F)
    barba_00_1b = b''.join([
        _split_16x16(right_w0),  # $00, $02: Right walk 0
        _split_16x16(right_w1),  # $04, $06: Right walk 1
        _split_16x16(down_w),    # $08, $0A: Down walk
        _split_16x16(up_w),      # $0C, $0E: Up walk
        _split_16x16(right_atk), # $10, $12: Right attack
        _split_16x16(down_a),    # $14, $16: Down attack
        _split_16x16(up_a),      # $18, $1A: Up attack
    ])

    fire_vert = _rows_to_pair([r.replace('.', '0') for r in FIREBALL_VERT])      # $20 (32B)
    fire_horiz = _rows_to_pair([r.replace('.', '0') for r in FIREBALL_HORIZ])   # $82 (32B)
    spark_62_65 = (
        _rows_to_pair([r.replace('.', '0') for r in EMBER_SPARK_B])
        + _rows_to_pair([r.replace('.', '0') for r in EMBER_SPARK_A])
    )
    hold_78 = _rows_to_pair([r.replace('.', '0') for r in BARBA_HOLD_LEFT])      # $78 (32B)

    # Villainous Link 32x32 ($C0..$E7 = 20 pairs = 1280 bytes in Bank 3 $A7DB)
    # Frame 0 ($C0..$CF): full asymmetric 32x32; note Ganon renderer H-flips right quadrants ($C4..$CF)
    v_full = [r.replace('.', '0') for r in VILLAIN_FULL_SWORD_32X32]
    c0 = _encode_quadrant_16x16([r[:16] for r in v_full[:16]])
    c4 = _encode_quadrant_16x16(_hflip([r[16:] for r in v_full[:16]]))
    c8 = _encode_quadrant_16x16([r[:16] for r in v_full[16:]])
    cc = _encode_quadrant_16x16(_hflip([r[16:] for r in v_full[16:]]))

    v_idle = [r.replace('.', '0') for r in VILLAIN_HALF_IDLE]
    d0 = _encode_quadrant_16x16(v_idle[:16])
    d4 = _encode_quadrant_16x16(v_idle[16:])

    v_cast = [r.replace('.', '0') for r in VILLAIN_HALF_CAST]
    d8 = _encode_quadrant_16x16(v_cast[:16])
    dc = _encode_quadrant_16x16(v_cast[16:])

    # $E0..$E7: lunge/flash half-frame (shifted slightly inward)
    v_lunge = [r[1:] + '0' for r in v_cast]
    e0 = _encode_quadrant_16x16(v_lunge[:16])
    e4 = _encode_quadrant_16x16(v_lunge[16:])

    villain_c0_e7 = c0 + c4 + c8 + cc + d0 + d4 + d8 + dc + e0 + e4
    assert len(barba_00_1b) == 0x1C0
    assert len(villain_c0_e7) == 0x280

    return {
        'barba_00_1b': barba_00_1b,
        'fire_vert': fire_vert,
        'fire_horiz': fire_horiz,
        'spark_62_65': spark_62_65,
        'hold_78': hold_78,
        'villain_c0_e7': villain_c0_e7,
        '_preview_grids': (
            [right_w0, right_w1, down_w, up_w, right_atk, down_a, up_a],
            v_full,
        ),
    }


def patch_zelda_title_tiles(src_prg: bytearray) -> None:
    """Replace 'ZELDA' BG1 title logo tiles (PRG Bank 1 $96B4, $70 & $7C..$C0) with chiseled 'BARBA'."""
    tile_base = 0x56B4  # PRG Bank 1 $96B4 -> $70..$F1
    rows_map: list[tuple[int, range, list[int]]] = [
        (8, range(7, 23), list(range(0x7C, 0x8C))),
        (9, range(7, 24), list(range(0x8C, 0x9D))),
        (10, range(7, 25), list(range(0x9D, 0xAF))),
        (11, range(6, 25), [0x70] + list(range(0xAF, 0xC1))),
    ]
    # Canvas covering cols 6..24 (x=48..199, w=152) x rows 8..11 (y=64..95, h=32)
    # BG1 color map: '0'=pink sky ($36), '1'=brown ($17), '2'=Triforce gold ($27), '3'=black ($0F)
    canvas = [['0'] * 152 for _ in range(32)]
    for py in range(32):
        y = 64 + py
        # Triforce edges joining r07 (y=63: 93..162) cleanly to r12 (y=96: 111..142)
        t = (y - 63) / 33.0
        left_g = int(round(93 + t * (111 - 93)))
        right_g = int(round(162 + t * (142 - 162)))
        left_in = left_g + 4
        right_in = right_g - 4
        for x in range(left_g, right_g + 1):
            if 48 <= x < 200:
                if x in (left_in, left_in + 1, right_in) or x == right_g + 1:
                    canvas[py][x - 48] = '3'
                elif x <= right_g:
                    canvas[py][x - 48] = '2'

    z_glyphs = {
        'B': [
            '111111111000', '011100011100', '011100001110', '011100011100', '011111110000',
            '011100011100', '011100001110', '011100001110', '011100011100', '111111111000',
        ],
        'A': [
            '000011110000', '000111111000', '001110011100', '011100001110', '011100001110',
            '111111111111', '111000000111', '111000000111', '111000000111', '111100001111',
        ],
        'R': [
            '111111111000', '011100011100', '011100001110', '011100011100', '011111110000',
            '011101110000', '011100111000', '011100011100', '011100001110', '111100001111',
        ],
    }
    scale_x, scale_y = 2.2, 2.8
    start_x, start_y, pitch = 56, 64, 26
    face = [[False] * 152 for _ in range(32)]
    for idx, ch in enumerate('BARBA'):
        g = z_glyphs[ch]
        bx = start_x + idx * pitch
        for gy, row in enumerate(g):
            for gx, bit in enumerate(row):
                if bit == '1':
                    y0 = int(start_y + gy * scale_y)
                    y1 = int(start_y + (gy + 1) * scale_y)
                    x0 = int(bx + gx * scale_x)
                    x1 = int(bx + (gx + 1) * scale_x)
                    for py_abs in range(y0, y1):
                        for px_abs in range(x0, x1):
                            face[py_abs - 64][px_abs - 48] = True

    for py in range(32):
        for px in range(152):
            if face[py][px]:
                for dy in range(1, 4):
                    for dx in range(1, 3):
                        if py + dy < 32 and px + dx < 152:
                            canvas[py + dy][px + dx] = '3'
    for py in range(32):
        for px in range(152):
            if face[py][px]:
                canvas[py][px] = '1'

    for tile_row, cols, tids in rows_map:
        py_base = (tile_row - 8) * 8
        for col, tid in zip(cols, tids):
            px_base = (col - 6) * 8
            tile_rows = [''.join(canvas[py_base + py][px_base : px_base + 8]) for py in range(8)]
            off = tile_base + (tid - 0x70) * 16
            src_prg[off : off + 16] = encode_tile(tile_rows)


def write_preview(z2_bytes: bytes, out_path: Path) -> Path:
    """Render a labelled PNG preview of Barba, fireballs, and Villainous Link."""
    art = build_barba_player_tiles(z2_bytes)
    frames, v_full = art['_preview_grids']
    # Row 0: 7 Barba 16x16 frames + Triforce hold + Fireballs; Row 1..2: 32x32 Villainous Link
    w = 160
    h = 64
    img = [[BARBA_PALETTE[0]] * w for _ in range(h)]

    def blit(grid: list[str], ox: int, oy: int, pal: list[tuple[int, int, int]]) -> None:
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch != '0':
                    img[oy + y][ox + x] = pal[int(ch)]

    for i, g in enumerate(frames):
        blit(g, 4 + i * 20, 4, BARBA_PALETTE)
    hold16 = [r + r[::-1] for r in [s.replace('.', '0') for s in BARBA_HOLD_LEFT]]
    blit(hold16, 4 + 7 * 20, 4, BARBA_PALETTE)

    blit([r.replace('.', '0') for r in FIREBALL_VERT], 4, 28, BARBA_PALETTE)
    blit([r.replace('.', '0') for r in FIREBALL_HORIZ], 16, 28, BARBA_PALETTE)
    blit(v_full, 40, 26, VILLAIN_PALETTE)

    write_png(out_path, img, scale=4)
    return out_path


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    z2 = (root / 'roms' / 'z2.nes').read_bytes()
    out = write_preview(z2, root / 'build' / 'subgames' / 'zelda-art-preview.png')
    print(f'Wrote {out}')
