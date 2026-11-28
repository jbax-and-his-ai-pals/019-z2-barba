"""Build-time Z2/Barba sprite, animation, and palette theming for Wheel of Barba.

Extracts Barba (24x48) poses directly from roms/z2.nes at build time
(no original pixels or code committed).
"""

from __future__ import annotations

import math

from nes import CHR_OFFSET, decode_tile
import assets
import boss_art
from asm6502 import Asm6502


def _encode_tile_2bpp(grid_8x8: list[list[int]]) -> bytes:
    """Encode an 8x8 pixel grid (values 0..3) into a 16-byte NES 2bpp tile."""
    p0 = bytearray(8)
    p1 = bytearray(8)
    for y in range(8):
        b0 = 0
        b1 = 0
        row = grid_8x8[y]
        for x in range(8):
            c = row[x] & 3
            bit = 7 - x
            if c & 1:
                b0 |= 1 << bit
            if c & 2:
                b1 |= 1 << bit
        p0[y] = b0
        p1[y] = b1
    return bytes(p0) + bytes(p1)


def _barba_grid_to_chr(grid: list[str]) -> bytes:
    """Convert top 32x24 of boss_art LEFT-facing grid into 12 RIGHT-facing NES 2bpp tiles (3x4).

    Wheel's metasprite renderer (2:DD84) draws unflipped sprites facing RIGHT
    ($03 bit 7 = 0) and flips them horizontally ($03 bit 7 = 1, EOR #$40) when
    facing LEFT. Mirroring boss_art's left-facing grid here makes Barba face
    the puzzle board on the left stage and face his walking direction.
    The bottom 16px (junction bend, horizontal torso, tail) are static tiles.
    """
    assert len(grid) == 48 and len(grid[0]) == 24
    mirrored = [row[::-1] for row in grid[:32]]
    out = bytearray()
    for ty in range(4):
        for tx in range(3):
            sub = [[int(mirrored[ty * 8 + y][tx * 8 + x]) for x in range(8)] for y in range(8)]
            out.extend(_encode_tile_2bpp(sub))
    assert len(out) == 12 * 16
    return bytes(out)


def _rows_to_chr_tiles(rows: list[str], tx_start: int, tx_count: int) -> bytes:
    """Encode a 16px-tall slice of right-facing rows into tx_count*2 NES 2bpp tiles."""
    out = bytearray()
    for ty in range(2):
        for tx in range(tx_start, tx_start + tx_count):
            sub = [[int(rows[ty * 8 + y][tx * 8 + x]) for x in range(8)] for y in range(8)]
            out.extend(_encode_tile_2bpp(sub))
    return bytes(out)


def extract_barba_body_tiles(z2_bytes: bytes) -> bytes:
    """Return 192-byte (12-tile) right-facing tail (4), horizontal torso (4), and junction bend (4)."""
    def pair_to_32b(tile: int) -> bytes:
        rows = boss_art.source_pair(z2_bytes, tile)
        top = [[int(c) for c in r] for r in rows[:8]]
        bot = [[int(c) for c in r] for r in rows[8:16]]
        return _encode_tile_2bpp(top) + _encode_tile_2bpp(bot)

    graphics = {0x06: pair_to_32b(0xA0), 0x08: pair_to_32b(0xA2)}
    trail_right = [r[::-1] for r in assets.encounter_trail_rows(graphics)]
    elbow_right = [r[::-1] for r in assets.encounter_connector_rows(graphics)]
    tail_chr = _rows_to_chr_tiles(trail_right, 0, 2)      # 4 tiles (leftmost 16x16)
    torso_chr = _rows_to_chr_tiles(trail_right, 2, 2)     # 4 tiles (middle 16x16)
    elbow_chr = _rows_to_chr_tiles(elbow_right, 0, 2)     # 4 tiles (junction bend 16x16)
    out = tail_chr + torso_chr + elbow_chr
    assert len(out) == 12 * 16
    return out


BARBA_POSE_ORDER = ('idle', 'walk1', 'walk2', 'windup', 'attack', 'up')

# Map Wheel's 34 Vanna animation frames ($AB & $7F = 0..33) to BARBA_POSE_ORDER indices:
#   0: idle, 1..2: talk/gesture, 3..5: turn/cheer, 6..13: walk cycle, 14..33: reach up to unveil
_FRAME_TO_POSE_NAME = [
    'idle',                                                     # 0: standing
    'idle', 'windup',                                           # 1..2: talking/gesturing
    'idle', 'windup', 'attack',                                 # 3..5: turning / cheering
    'idle', 'walk1', 'walk2', 'walk1',                          # 6..9: walk cycle (first half)
    'idle', 'walk1', 'walk2', 'walk1',                          # 10..13: walk cycle (second half)
    'windup', 'up', 'up', 'windup',                             # 14..17: unveil row 3
    'windup', 'up', 'up', 'up', 'up', 'windup',                 # 18..23: unveil row 0
    'windup', 'up', 'up', 'up', 'windup',                       # 24..28: unveil row 1
    'windup', 'up', 'up', 'up', 'windup',                       # 29..33: unveil row 2
]
assert len(_FRAME_TO_POSE_NAME) == 34


def extract_barba_frames(z2_bytes: bytes) -> dict[str, bytes]:
    """Return named 288-byte (18-tile) right-facing Barba CHR poses for Bank 1."""
    bf = boss_art.make_frames(z2_bytes, width=24)
    return {name: _barba_grid_to_chr(bf[name]) for name in BARBA_POSE_ORDER}


def apply_art_patches_bank0(b0: bytearray) -> None:
    """Theme Bank 0 palettes for Barba and Palace VI stage floor."""
    # Title BG palette ($8801-$8810): keep BG0 (0F 16 25 20) at vanilla pink for the Screen 2 marquee,
    # swap BG1-BG2 for crimson & gold, and keep BG3 (0F 00 15 10) at vanilla magenta/grey for the Big Wheel.
    b0[0x8801 - 0x8000 : 0x8811 - 0x8000] = bytes.fromhex(
        '0f 16 25 20  0f 00 16 27  0f 06 16 30  0f 00 15 10'
    )
    # Main Board / Menu BG palette ($8811-$8820):
    #   BG0: gold/brown stage arch (0F 17 28 07)
    #   BG1: Palace VI crimson stage floor (0F 06 16 30)
    #   BG2: emerald puzzle board (0F 09 1A 29)
    #   BG3: crisp silver HUD (0F 00 10 30)
    b0[0x8811 - 0x8000 : 0x8821 - 0x8000] = bytes.fromhex(
        '0f 17 28 07  0f 06 16 30  0f 09 1a 29  0f 00 10 30'
    )
    # Main Board / Menu SPR palette ($8861-$8870):
    #   SPR0: Barba (0F 16 27 30 - crimson red, gold scales, white horns/teeth)
    #   SPR1: Floor shadow (0F 00 10 0F)
    #   SPR2: Gold accents (0F 20 38 0F)
    #   SPR3: Category badge & cursor (0F 00 28 20)
    b0[0x8861 - 0x8000 : 0x8871 - 0x8000] = bytes.fromhex(
        '0f 16 27 30  0f 00 10 0f  0f 20 38 0f  0f 00 28 20'
    )


def apply_art_patches_bank1(b1: bytearray, z2_bytes: bytes) -> None:
    """Replace Bank 1 Vanna CHR animation frames with Barba poses and speed up walking."""
    poses = extract_barba_frames(z2_bytes)

    # Point Bank 1 $8FB6 table (34 entries) to safe dummy address $C1B1 (unused by fast_upload)
    dummy_addr = 0xC1B1
    tbl_off = 0x8FB6 - 0x8000
    for i in range(34):
        b1[tbl_off + i * 2] = dummy_addr & 0xFF
        b1[tbl_off + i * 2 + 1] = dummy_addr >> 8

    # Keep Barba facing the board in Bank 1 idle state 1 (1:900A..1:9017):
    # Original 1:9010..1:9011 is 40 80 (64 frames with bit 7 flipped), which turns
    # Barba left while standing at the far left ($04=$12) and clips him off-screen.
    assert b1[0x9010 - 0x8000 : 0x9012 - 0x8000] == bytes([0x40, 0x80])
    b1[0x9011 - 0x8000] = 0x00

    # Slow Barba walking in Bank 1 (1:90D8..1:90EA): 2 px/frame
    # Original 1:90DE..1:90EA: A9 04 85 9A C6 04 B0 04 E6 04 E6 04 60
    fast_walk_addr = 0xC1B1
    assert b1[0x90DE - 0x8000 : 0x90E1 - 0x8000] == bytes.fromhex('a9 04 85')
    b1[0x90DE - 0x8000 : 0x90E1 - 0x8000] = bytes([0x4C, fast_walk_addr & 0xFF, fast_walk_addr >> 8])

    a_walk = Asm6502(fast_walk_addr)
    a_walk.emit(0xA9, 0x04, 0x85, 0x9A)        # LDA #$04; STA $9A (pause Bank 0 timer while walking)
    a_walk.emit(0xA5, 0x04, 0xC5, 0xB3)        # LDA $04; CMP $B3
    a_walk.branch(0x90, 'walk_right')          # BCC walk_right ($04 < $B3)
    a_walk.emit(0x38, 0xE9, 0x02)              # SEC; SBC #$02
    a_walk.branch(0x90, 'clamp_target')        # BCC clamp_target
    a_walk.emit(0xC5, 0xB3)                    # CMP $B3
    a_walk.branch(0xB0, 'store_x')             # BCS store_x
    a_walk.label('clamp_target')
    a_walk.emit(0xA5, 0xB3)                    # LDA $B3
    a_walk.abs_ref(0x4C, 'store_x')            # JMP store_x
    a_walk.label('walk_right')
    a_walk.emit(0x18, 0x69, 0x02)              # CLC; ADC #$02
    a_walk.branch(0xB0, 'clamp_target')        # BCS clamp_target
    a_walk.emit(0xC5, 0xB3)                    # CMP $B3
    a_walk.branch(0xB0, 'clamp_target')        # BCS clamp_target
    a_walk.label('store_x')
    a_walk.emit(0x85, 0x04, 0x60)              # STA $04; RTS
    walk_bytes = a_walk.finish()
    b1[fast_walk_addr - 0x8000 : fast_walk_addr - 0x8000 + len(walk_bytes)] = walk_bytes

    # Fast unrolled VBlank CHR-RAM uploader replacing $0680 ($8C8F[0] and direct JMP $0680 callers)
    # Supports all 6 Barba upright poses (192B each = Q0:64B, Q1:64B, Q2:64B, Q3:0B).
    assert b1[0x8C8F - 0x8000] == 0x80 and b1[0x8C97 - 0x8000] == 0x06, (
        f'Unexpected $8C8F[0]: ${b1[0x8C97 - 0x8000]:02X}{b1[0x8C8F - 0x8000]:02X}'
    )
    fast_addr = 0xC200
    b1[0x8C8F - 0x8000] = fast_addr & 0xFF
    b1[0x8C97 - 0x8000] = fast_addr >> 8
    for jmp_addr in (0x8C2E, 0x8E80, 0x8EA4):
        off = jmp_addr - 0x8000
        assert b1[off : off + 3] == bytes([0x4C, 0x80, 0x06]), (
            f'Unexpected JMP $0680 at 1:${jmp_addr:04X}: {b1[off : off + 3].hex(" ")}'
        )
        b1[off + 1] = fast_addr & 0xFF
        b1[off + 2] = fast_addr >> 8

    a = Asm6502(fast_addr)
    a.emit(0xA5, 0xA8, 0x8D, 0x06, 0x20)          # LDA $A8; STA $2006
    a.emit(0xA5, 0xA9, 0x8D, 0x06, 0x20)          # LDA $A9; STA $2006 (N set iff $C0)
    a.branch(0x30, 'q0_or_q2')                    # BMI q0_or_q2
    a.emit(0xA5, 0xA8, 0x29, 0x01)                # LDA $A8; AND #$01
    a.branch(0xD0, 'q1')                          # BNE q1
    a.emit(0x60)                                  # q3: RTS

    pose_idx = {name: i * 2 for i, name in enumerate(BARBA_POSE_ORDER)}

    def emit_dispatch_iny(q_label: str, ptr_label: str, *, set_mid_addr: bool = False) -> None:
        a.label(q_label)
        if set_mid_addr:
            a.emit(0xA5, 0xA8, 0x8D, 0x06, 0x20)  # LDA $A8; STA $2006 ($17 or $19)
            a.emit(0xA9, 0x00, 0x8D, 0x06, 0x20)  # LDA #$00; STA $2006 ($1700 or $1900)
        a.emit(0xA5, 0xAB, 0x29, 0x7F)            # LDA $AB; AND #$7F
        a.emit(0xC9, 0x22)                        # CMP #34
        a.branch(0x90, f'{q_label}_ok')           # BCC ok
        a.emit(0xA9, 0x00)                        # LDA #$00
        a.label(f'{q_label}_ok')
        a.emit(0xA8)                              # TAY
        a.abs_ref(0xB9, 'frame_pose_tbl')         # LDA frame_pose_tbl,Y (already *2)
        a.emit(0xA8)                              # TAY
        a.abs_ref(0xB9, ptr_label)                # LDA ptr_label,Y
        a.emit(0x85, 0x10)                        # STA $10
        a.emit(0xC8)                              # INY
        a.abs_ref(0xB9, ptr_label)                # LDA ptr_label,Y
        a.emit(0x85, 0x11)                        # STA $11
        a.emit(0x6C, 0x10, 0x00)                  # JMP ($0010)

    emit_dispatch_iny('q1', 'q1_ptrs')
    a.label('q0_or_q2')
    a.emit(0xA5, 0xA8, 0x29, 0x01)                # LDA $A8; AND #$01
    a.branch(0xF0, 'q0')                          # BEQ q0
    emit_dispatch_iny('q2', 'q2_ptrs', set_mid_addr=True)
    emit_dispatch_iny('q0', 'q0_ptrs')

    a.label('frame_pose_tbl')
    a.emit(*[pose_idx[name] for name in _FRAME_TO_POSE_NAME])

    for q in range(3):
        a.label(f'q{q}_ptrs')
        for name in BARBA_POSE_ORDER:
            a.fixups.append(('abs', len(a.buf), f'{name}_{q}'))
            a.emit(0, 0)

    for name in BARBA_POSE_ORDER:
        chr_192 = poses[name]
        # q0: bytes 0..64 ($16C0/$18C0), q1: bytes 128..192 ($1740/$1940), q2: bytes 64..128 ($1700/$1900)
        for q, (start, end) in enumerate(((0, 64), (128, 192), (64, 128))):
            a.label(f'{name}_{q}')
            prev = None
            for byte in chr_192[start:end]:
                if byte != prev:
                    a.emit(0xA9, byte)            # LDA #byte
                    prev = byte
                a.emit(0x8D, 0x07, 0x20)          # STA $2007
            a.emit(0x60)                          # RTS

    body_chr = extract_barba_body_tiles(z2_bytes)
    a.label('static_body')
    prev = None
    for byte in body_chr:
        if byte != prev:
            a.emit(0xA9, byte)
            prev = byte
        a.emit(0x8D, 0x07, 0x20)
    a.emit(0x60)

    # Screen-init helper (replaces Bank 1 $82CA..$82DC, called with rendering OFF):
    # Uploads idle Barba (12 upright tiles) + static full body (12 tiles) to BOTH $16C0 and $18C0.
    a.label('screen_init_helper')
    a.emit(0xA9, 0x00, 0x85, 0xAB, 0x85, 0x03)    # LDA #$00; STA $AB; STA $03
    a.emit(0x20, 0x6F, 0x8F)                      # JSR $8F6F (init $0690)
    a.emit(0xA9, 0x16, 0x8D, 0x06, 0x20, 0xA9, 0xA0)  # LDA #$16; STA $2006; LDA #$A0
    a.emit(0x20, 0xEA, 0x81)                      # JSR $81EA (preserve $16A0..$16BF shadow tiles)
    for ppu_hi in (0x16, 0x18):
        a.emit(0xA9, ppu_hi, 0x8D, 0x06, 0x20, 0xA9, 0xC0, 0x8D, 0x06, 0x20)
        a.abs_ref(0x20, 'idle_0')
        a.abs_ref(0x20, 'idle_2')
        a.abs_ref(0x20, 'idle_1')
        a.abs_ref(0x20, 'static_body')
    a.emit(0x60)

    fast_bytes = a.finish()
    assert fast_addr + len(fast_bytes) <= 0xE200, (
        f'fast_upload overflowed into roar.dmc: ${fast_addr + len(fast_bytes):04X} > $E200'
    )
    b1[fast_addr - 0x8000 : fast_addr - 0x8000 + len(fast_bytes)] = fast_bytes

    helper_addr = fast_addr + a.labels['screen_init_helper'] - fast_addr
    assert b1[0x82CA - 0x8000 : 0x82DD - 0x8000] == bytes.fromhex('a90385ab8503206f8fa9168d0620a9a04cea81')
    b1[0x82CA - 0x8000 : 0x82CD - 0x8000] = bytes([0x4C, helper_addr & 0xFF, helper_addr >> 8])

    patch_s1_logo_bank1(b1)


def _decode_tile_2bpp(tile_bytes: bytes) -> list[list[int]]:
    out = [[0] * 8 for _ in range(8)]
    for y in range(8):
        p0, p1 = tile_bytes[y], tile_bytes[y + 8]
        for x in range(8):
            out[y][7 - x] = ((p0 >> x) & 1) | (((p1 >> x) & 1) << 1)
    return out


def patch_s1_logo_bank1(b1: bytearray) -> None:
    """Replace 'FORTUNE' (cols 13..23) in Bank 1 $95F1 with 'BARBA' (shared by Screen 1 & S2 ticker)."""
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
    w, h = 88, 16
    face = [[False] * w for _ in range(h)]
    for idx, ch in enumerate('BARBA'):
        g = glyphs[ch]
        bx = 2 + idx * 17
        for gy, row in enumerate(g):
            for gx, bit in enumerate(row):
                if bit == '1' and 0 <= bx + gx < w:
                    face[1 + gy][bx + gx] = True

    grid = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if face[y][x]:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and not face[ny][nx]:
                            grid[ny][nx] = 3
    for y in range(h):
        for x in range(w):
            if face[y][x]:
                grid[y][x] = 2

    # B1 $95F1.. is 24 columns x 2 tile rows (column-major: col*32 + row*16)
    base_off = 0x95F1 - 0x8000
    for c_rel in range(11):
        for tr in range(2):
            tile_grid = [grid[tr * 8 + py][c_rel * 8 : (c_rel + 1) * 8] for py in range(8)]
            off = base_off + (13 + c_rel) * 32 + tr * 16
            b1[off : off + 16] = _encode_tile_2bpp(tile_grid)


def patch_s2_wheel_barba(b1: bytearray, b2: bytearray) -> None:
    """Replace 'FORTUNE' on the Screen 2 Big Wheel bottom arc (B1 $B291 + B2 $81C5) with curved 'BARBA'."""
    chr_off = 0xB291 - 0x8000
    nt_off = 0x81C5 - 0x8000
    nt = list(b2[nt_off : nt_off + 304])  # 19 rows x 16 cols

    # Decode entire 128x152 wheel pixel buffer (top left screen (64, 24) -> center (64, 84))
    w, h = 128, 152
    buf = [[0] * w for _ in range(h)]
    tile_cache: dict[int, list[list[int]]] = {}
    for ry in range(19):
        for rx in range(16):
            tid = nt[ry * 16 + rx]
            if tid == 0:
                continue
            if tid not in tile_cache:
                t_off = chr_off + (tid - 1) * 16
                tile_cache[tid] = _decode_tile_2bpp(bytes(b1[t_off : t_off + 16]))
            t = tile_cache[tid]
            for py in range(8):
                for px in range(8):
                    buf[ry * 8 + py][rx * 8 + px] = t[py][px]

    # Erase FORTUNE along bottom arc outside the inner orange/grey oval around 'of'
    cx, cy = 64.0, 84.0
    for ly in range(80, h):
        for lx in range(w):
            dist = math.hypot(lx - cx, ly - cy)
            in_inner_ellipse = ((lx - cx) / 37.2) ** 2 + ((ly - cy) / 35.5) ** 2 <= 1.0
            if not in_inner_ellipse and dist <= 62.5:
                buf[ly][lx] = 0

    glyphs = {
        'B': [
            '11111111', '11111111', '11100111', '11111110',
            '11111110', '11100111', '11111111', '11111111',
        ],
        'A': [
            '11111111', '11111111', '11100111', '11111111',
            '11111111', '11100111', '11100111', '11100111',
        ],
        'R': [
            '11111111', '11111111', '11100111', '11111111',
            '11111110', '11101111', '11100111', '11100111',
        ],
    }
    face = [[False] * w for _ in range(h)]
    angles = [140.0, 115.0, 90.0, 65.0, 40.0]
    box_w, box_h, rad_c = 17.0, 22.0, 47.0
    for ch, deg in zip('BARBA', angles):
        th = math.radians(deg)
        lcx = cx + rad_c * math.cos(th)
        lcy = cy + rad_c * math.sin(th)
        rx_v, ry_v = math.sin(th), -math.cos(th)
        ux_v, uy_v = -math.cos(th), -math.sin(th)
        g = glyphs[ch]
        for ly in range(90, h):
            for lx in range(w):
                dx, dy = lx - lcx, ly - lcy
                u = dx * rx_v + dy * ry_v
                v = dx * ux_v + dy * uy_v
                if -box_w / 2 <= u <= box_w / 2 and -box_h / 2 <= v <= box_h / 2:
                    gx = int((u + box_w / 2) / box_w * 8)
                    gy = int((box_h / 2 - v) / box_h * 8)
                    if 0 <= gx < 8 and 0 <= gy < 8 and g[gy][gx] == '1':
                        face[ly][lx] = True

    # Drop shadow (+2, +2) color 1 ($00), light-grey 1px outline color 3 ($10), magenta fill color 2 ($15)
    for ly in range(90, h):
        for lx in range(w):
            if face[ly][lx] and ly + 2 < h and lx + 2 < w and not face[ly + 2][lx + 2]:
                buf[ly + 2][lx + 2] = 1
    for ly in range(90, h):
        for lx in range(w):
            if face[ly][lx]:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = ly + dy, lx + dx
                        if 0 <= ny < h and 0 <= nx < w and not face[ny][nx]:
                            buf[ny][nx] = 3
    for ly in range(90, h):
        for lx in range(w):
            if face[ly][lx]:
                buf[ly][lx] = 2

    # Pack bottom half (ry=10..18) preserving top-half tiles verbatim and reusing bottom-exclusive slots
    top_tiles = set(nt[: 10 * 16])
    top_tile_by_bytes: dict[bytes, int] = {}
    for tid in sorted(top_tiles):
        if tid != 0:
            t_off = chr_off + (tid - 1) * 16
            top_tile_by_bytes[bytes(b1[t_off : t_off + 16])] = tid

    excl_pool = sorted(t for t in set(nt[10 * 16 :]) if t != 0 and t not in top_tiles)
    alloc_by_bytes: dict[bytes, int] = {}
    for ry in range(10, 19):
        for rx in range(16):
            grid8 = [buf[ry * 8 + py][rx * 8 : (rx + 1) * 8] for py in range(8)]
            if all(px == 0 for r in grid8 for px in r):
                b2[nt_off + ry * 16 + rx] = 0
                continue
            enc = _encode_tile_2bpp(grid8)
            if enc in top_tile_by_bytes:
                tid = top_tile_by_bytes[enc]
            elif enc in alloc_by_bytes:
                tid = alloc_by_bytes[enc]
            else:
                if not excl_pool:
                    raise RuntimeError('Wheel S2 bottom-exclusive tile pool exhausted')
                tid = excl_pool.pop(0)
                t_off = chr_off + (tid - 1) * 16
                b1[t_off : t_off + 16] = enc
                alloc_by_bytes[enc] = tid
            b2[nt_off + ry * 16 + rx] = tid


def apply_art_patches_bank2(b2: bytearray) -> None:
    """Replace Bank 2 Vanna metasprites ($DE10+) with full-body Barba (head/neck + bend + torso + tail)."""
    barba_list_addr = 0xED16
    empty_list_addr = 0xED60
    tuple_addr      = 0xED62
    clip_addr       = 0xED68

    # Full-body Barba in 2:DD88 format (24 tiles, max 6 sprites/scanline):
    #   byte 0: anchor X offset = 16 (at $04=18, tail tip starts at X=2, head at X=34..57)
    #   $C0..$CB (12 tiles): 3x4 animated head+neck at dx=32..48, dy=48,40,32,24
    #   $CC..$CF (4 tiles): 2x2 tail tip at dx=0,8, dy=16,8
    #   $D0..$D3 (4 tiles): 2x2 horizontal torso at dx=16,24, dy=16,8
    #   $D4..$D7 (4 tiles): 2x2 junction bend at dx=32,40, dy=16,8
    barba_list = bytearray([16])
    for ty in range(4):
        dy = 48 - ty * 8
        for tx in range(3):
            tile = 0xC0 + ty * 3 + tx
            dx = 32 + tx * 8
            barba_list.extend((tile, dx, dy))
    for part_idx, base_dx in enumerate((0, 16, 32)):
        for ty in range(2):
            dy = 16 - ty * 8
            for tx in range(2):
                tile = 0xCC + part_idx * 4 + ty * 2 + tx
                dx = base_dx + tx * 8
                barba_list.extend((tile, dx, dy))
    barba_list.append(0x00)
    assert len(barba_list) == 1 + 24 * 3 + 1  # 74 bytes ($ED16..$ED5F)

    b2[barba_list_addr - 0x8000 : barba_list_addr - 0x8000 + len(barba_list)] = barba_list
    b2[empty_list_addr - 0x8000 : empty_list_addr - 0x8000 + 2] = b'\x00\x00'

    # 6-byte tuple (pal0=barba, pal1=empty, pal2=empty)
    tup = (
        barba_list_addr.to_bytes(2, 'little')
        + empty_list_addr.to_bytes(2, 'little')
        + empty_list_addr.to_bytes(2, 'little')
    )
    b2[tuple_addr - 0x8000 : tuple_addr - 0x8000 + 6] = tup

    # Left-facing X-underflow clip in 2:DD84 (2:DDF5 was STA $0203,X after SBC ($16),Y):
    # If borrow (C=0 -> X_oam < 0), hide sprite at Y=$F8 and skip to 2:DE01; else store X and resume at 2:DDF8.
    assert b2[0xDDF5 - 0x8000 : 0xDE01 - 0x8000] == bytes.fromhex('9d 03 02 c8 a5 18 38 f1 16 9d 00 02')
    b2[0xDDF5 - 0x8000 : 0xDDF8 - 0x8000] = bytes([0x4C, clip_addr & 0xFF, clip_addr >> 8])
    a_clip = Asm6502(clip_addr)
    a_clip.branch(0xB0, 'ok')       # BCS ok
    a_clip.emit(0xA9, 0xF8, 0x9D, 0x00, 0x02, 0xC8)  # LDA #$F8; STA $0200,X; INY
    a_clip.emit(0x4C, 0x01, 0xDE)   # JMP $DE01
    a_clip.label('ok')
    a_clip.emit(0x9D, 0x03, 0x02)   # STA $0203,X
    a_clip.emit(0x4C, 0xF8, 0xDD)   # JMP $DDF8
    clip_bytes = a_clip.finish()
    b2[clip_addr - 0x8000 : clip_addr - 0x8000 + len(clip_bytes)] = clip_bytes

    # Point all 34 entries of 2:DE10..2:DE53 to our Barba tuple
    for i in range(34):
        off = 0xDE10 - 0x8000 + i * 2
        b2[off : off + 2] = tuple_addr.to_bytes(2, 'little')


# ---------------------------------------------------------------------------
# Bonus Round ("BARBA TREASURE") 6-Prize Artworks (80x48 = 10x6 tiles each)
# ---------------------------------------------------------------------------

WHEEL_PRIZE_SPECS: list[dict[str, object]] = [
    {
        'name': 'PALACE 6 CRYSTAL',
        'bg_pal': (0x11, 0x21, 0x30),
        'spr_pal': (0x27, 0x38, 0x30),
    },
    {
        'name': 'EAST HYRULE CRUISE',
        'bg_pal': (0x11, 0x27, 0x30),
        'spr_pal': (0x11, 0x27, 0x30),
    },
    {
        'name': 'HYRULE ITEM HOARD',
        'bg_pal': (0x16, 0x27, 0x30),
        'spr_pal': (0x16, 0x27, 0x30),
    },
    {
        'name': 'APRIL IN RAURU',
        'bg_pal': (0x20, 0x19, 0x12),
        'spr_pal': (0x20, 0x19, 0x12),
    },
    {
        'name': 'THIS COOL BOULDER',
        'bg_pal': (0x07, 0x17, 0x27),
        'spr_pal': (0x07, 0x17, 0x27),
    },
    {
        'name': 'PIECE OF PALACE 4',
        'bg_pal': (0x02, 0x12, 0x30),
        'spr_pal': (0x02, 0x12, 0x30),
    },
]


def _new_canvas(w: int = 80, h: int = 48) -> list[list[int]]:
    return [[0] * w for _ in range(h)]


def _pset(g: list[list[int]], x: int, y: int, c: int) -> None:
    if 0 <= y < len(g) and 0 <= x < len(g[0]):
        g[y][x] = c


def _fill_rect(g: list[list[int]], x0: int, y0: int, w: int, h: int, c: int) -> None:
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            _pset(g, x, y, c)


def _draw_sparkle(g: list[list[int]], cx: int, cy: int, r: int = 3, c: int = 3) -> None:
    _pset(g, cx, cy, c)
    for d in range(1, r + 1):
        _pset(g, cx - d, cy, c)
        _pset(g, cx + d, cy, c)
        _pset(g, cx, cy - d, c)
        _pset(g, cx, cy + d, c)


def _blit_z2_tile(
    g: list[list[int]],
    z2_bytes: bytes,
    bank4k: int,
    tile_idx: int,
    dx: int,
    dy: int,
    *,
    transparent_zero: bool = True,
) -> None:
    off = CHR_OFFSET + bank4k * 4096 + tile_idx * 16
    tile = decode_tile(z2_bytes[off : off + 16])
    for py in range(8):
        for px in range(8):
            c = tile[py][px]
            if transparent_zero and c == 0:
                continue
            _pset(g, dx + px, dy + py, c)


def _grid_to_60_tiles(g: list[list[int]]) -> bytes:
    assert len(g) == 48 and len(g[0]) == 80
    out = bytearray()
    for ty in range(6):
        for tx in range(10):
            sub = [[g[ty * 8 + y][tx * 8 + x] for x in range(8)] for y in range(8)]
            out.extend(_encode_tile_2bpp(sub))
    assert len(out) == 60 * 16
    return bytes(out)


def _draw_crystal_prize() -> list[list[int]]:
    g = _new_canvas()
    # Palace VI stepped pedestal
    _fill_rect(g, 20, 44, 40, 3, 1)
    _fill_rect(g, 24, 41, 32, 3, 2)
    _fill_rect(g, 28, 39, 24, 2, 3)
    _fill_rect(g, 25, 41, 30, 1, 3)
    # Faceted crystal (y=5..36, center x=40)
    for y in range(5, 37):
        if y < 14:
            half = 1 + (y - 5) * 12 // 9
        elif y <= 27:
            half = 13
        else:
            half = max(1, 13 - (y - 27) * 12 // 9)
        for x in range(40 - half, 40 + half + 1):
            if x in (40 - half, 40 + half) or y in (5, 36):
                c = 1
            elif x < 37 and y < 23:
                c = 3
            elif x > 43 or y > 28:
                c = 1
            elif abs(x - 40) <= 3 and 12 <= y <= 25:
                c = 3
            else:
                c = 2
            _pset(g, x, y, c)
    # Inner facet lines
    for y in range(9, 32):
        _pset(g, 34, y, 3 if y < 22 else 2)
        _pset(g, 45, y, 1)
    # Radiating sparkles
    _draw_sparkle(g, 15, 11, 3, 3)
    _draw_sparkle(g, 64, 13, 3, 3)
    _draw_sparkle(g, 18, 28, 2, 2)
    _draw_sparkle(g, 61, 29, 2, 3)
    return g


def _draw_cruise_prize() -> list[list[int]]:
    g = _new_canvas()
    # Sun (top right)
    for y in range(3, 16):
        for x in range(56, 70):
            d2 = (x - 63) ** 2 + (y - 9) ** 2
            if d2 <= 25:
                _pset(g, x, y, 2 if d2 > 9 else 3)
    # Clouds
    for cx, cy in ((16, 8), (34, 6)):
        _fill_rect(g, cx - 6, cy, 13, 4, 3)
        _fill_rect(g, cx - 3, cy - 2, 7, 2, 3)
    # Raft mast & billowing sail
    _fill_rect(g, 38, 9, 2, 18, 2)
    for y in range(10, 25):
        w = (y - 9) * 11 // 15
        _fill_rect(g, 40, y, max(1, w), 1, 3)
        _pset(g, 40 + max(1, w) - 1, y, 2)
    # Pennant at mast top
    _fill_rect(g, 34, 9, 4, 2, 2)
    # Wooden log raft deck (x=23..56, y=26..31)
    _fill_rect(g, 24, 26, 31, 5, 2)
    for lx in range(25, 55, 5):
        _fill_rect(g, lx, 26, 1, 5, 1)
    _fill_rect(g, 24, 28, 31, 1, 3)
    # Tiny dragon passenger at prow
    _fill_rect(g, 29, 21, 5, 5, 2)
    _pset(g, 30, 22, 3)
    _pset(g, 28, 22, 2)
    # Layered NES ocean waves (y=31..47)
    for y in range(31, 48):
        for x in range(80):
            wave_y = 32 + ((x + (y // 5) * 4) % 12 < 6) * 1
            if y < 32:
                continue
            if (y - 32) % 5 == 0 and ((x + y) % 8 < 5):
                _pset(g, x, y, 3)
            elif (y - 32) % 5 == 1 and ((x + y) % 8 < 3):
                _pset(g, x, y, 3)
            else:
                _pset(g, x, y, 1)
    return g


def _draw_rauru_town_house(g: list[list[int]]) -> None:
    """Draw peaked-roof Rauru Town house on the left side of the April in Rauru card."""
    for i in range(9):
        _fill_rect(g, 6 + (8 - i), 15 + i, 2 + i * 2, 1, 1 if i % 2 == 0 else 3)
    _fill_rect(g, 6, 24, 19, 22, 3)
    _fill_rect(g, 6, 24, 19, 2, 1)
    _fill_rect(g, 9, 28, 4, 4, 0)
    _fill_rect(g, 18, 28, 4, 4, 0)
    _fill_rect(g, 13, 35, 5, 11, 0)
    _fill_rect(g, 5, 45, 21, 2, 1)


def _draw_april_rauru_prize(wheel_bytes: bytes) -> list[list[int]]:
    """Start from vanilla April in Paris (Slot 3) and swap Eiffel Tower + 'Paris' -> Rauru Town House + 'Rauru'."""
    g = _april_paris_base(wheel_bytes)
    _draw_rauru_town_house(g)
    return g


def _draw_item_hoard_prize(z2_bytes: bytes) -> list[list[int]]:
    g = _new_canvas()
    # Two display shelves
    for sy in (21, 43):
        _fill_rect(g, 4, sy, 72, 2, 2)
        _fill_rect(g, 6, sy + 2, 68, 2, 1)
    # Top shelf (y=5): P-Bag, Magic Candle, Magic Hammer, Water Boots
    top_items = [
        (12, (0x72, 0x73)),
        (28, (0x8C, 0x8D)),
        (44, (0x98, 0x99)),
        (60, (0x92, 0x93)),
    ]
    # Bottom shelf (y=27): Mystic Flute, Cross, Magic Key
    bot_items = [
        (12, (0x94, 0x95)),
        (28, (0x96, 0x97)),
        (44, (0x9A, 0x9B)),
    ]
    for dx, (t_top, t_bot) in top_items:
        _blit_z2_tile(g, z2_bytes, 4, t_top, dx, 5)
        _blit_z2_tile(g, z2_bytes, 4, t_bot, dx, 13)
    for dx, (t_top, t_bot) in bot_items:
        _blit_z2_tile(g, z2_bytes, 4, t_top, dx, 27)
        _blit_z2_tile(g, z2_bytes, 4, t_bot, dx, 35)
    # 8th item: Elixir / Water of Life bottle ($8A)
    _blit_z2_tile(g, z2_bytes, 4, 0x8A, 60, 32)
    return g


def _draw_boulder_prize(z2_bytes: bytes) -> list[list[int]]:
    g = _new_canvas()
    # Showcase pedestal
    _fill_rect(g, 18, 43, 44, 4, 1)
    _fill_rect(g, 22, 40, 36, 3, 2)
    _fill_rect(g, 23, 40, 34, 1, 3)
    # Z2 Overworld 16x16 boulder metatile (CHR bank 17: top-left=$56, bot-left=$57, top-right=$58, bot-right=$59)
    # at crisp 2x (32x32). Palette map: 2=outside/bg -> 0, 1=highlight -> 3, 3=body -> 2, 0=shadow -> 1.
    ow_boulder_map = {2: 0, 1: 3, 3: 2, 0: 1}
    for ti, qx, qy in ((0x56, 0, 0), (0x57, 0, 8), (0x58, 8, 0), (0x59, 8, 8)):
        off_ow = CHR_OFFSET + 17 * 4096 + ti * 16
        tile_ow = decode_tile(z2_bytes[off_ow : off_ow + 16])
        for py in range(8):
            for px in range(8):
                c = ow_boulder_map[tile_ow[py][px]]
                if c:
                    _fill_rect(g, 24 + (qx + px) * 2, 8 + (qy + py) * 2, 2, 2, c)
    _draw_sparkle(g, 15, 13, 3, 3)
    _draw_sparkle(g, 63, 16, 2, 3)
    return g


def _draw_palace4_prize(z2_bytes: bytes) -> list[list[int]]:
    g = _new_canvas()
    # Showcase base
    _fill_rect(g, 16, 43, 48, 4, 1)
    _fill_rect(g, 20, 40, 40, 3, 2)
    _fill_rect(g, 21, 40, 38, 1, 3)
    # Tile Palace 4 brick & pillar tiles from Z2 CHR bank 11
    for ty in range(1, 5):
        for tx in range(2, 8):
            t_id = 0x5E if tx in (3, 6) else 0x5C
            _blit_z2_tile(g, z2_bytes, 11, t_id, tx * 8, ty * 8, transparent_zero=False)
    # Carve a jagged broken-off ruin silhouette
    for y in range(8, 40):
        left_cut = 20 + max(0, (24 - y) // 2) + ((y * 3) % 4 if y < 24 else 0)
        right_cut = 59 - max(0, (32 - y) // 2) - ((y * 5) % 5 if y < 30 else 0)
        for x in range(16, 64):
            if x < left_cut or x > right_cut or (y < 14 and x > 44):
                _pset(g, x, y, 0)
            elif x in (left_cut, right_cut):
                _pset(g, x, y, 3 if x == left_cut else 1)
    # Fallen rubble pebbles on base
    _fill_rect(g, 22, 38, 4, 2, 2)
    _fill_rect(g, 53, 37, 5, 3, 2)
    _pset(g, 54, 37, 3)
    return g


def build_wheel_prize_assets(z2_bytes: bytes, wheel_bytes: bytes) -> dict[str, object]:
    """Build 6x60-tile Bonus Prize graphics, tilemaps, and palettes for Wheel of Barba."""
    grids = [
        _draw_crystal_prize(),
        _draw_cruise_prize(),
        _draw_item_hoard_prize(z2_bytes),
        _draw_april_rauru_prize(wheel_bytes),
        _draw_boulder_prize(z2_bytes),
        _draw_palace4_prize(z2_bytes),
    ]
    chr_chunks = [_grid_to_60_tiles(g) for g in grids]
    identity_tm = bytes(range(60))
    return {
        'specs': WHEEL_PRIZE_SPECS,
        'chr_chunks': chr_chunks,
        'tilemap': identity_tm,
    }


def apply_prize_art_patches_bank0(b0: bytearray) -> None:
    """Patch Bank 0 Bonus Prize palettes, 10x6 tilemaps, OAM overlay, and Bank 2 CHR pointers."""
    # 1. BG2 palettes ($C1E1-$C1F2, 6 x 3 bytes) and SPR0 palettes ($C1CF-$C1E0, 6 x 3 bytes)
    bg_blob = bytes(c for spec in WHEEL_PRIZE_SPECS for c in spec['bg_pal'])  # type: ignore[union-attr]
    spr_blob = bytes(c for spec in WHEEL_PRIZE_SPECS for c in spec['spr_pal'])  # type: ignore[union-attr]
    assert len(bg_blob) == 18 and len(spr_blob) == 18
    b0[0xC1E1 - 0x8000 : 0xC1F3 - 0x8000] = bg_blob
    b0[0xC1CF - 0x8000 : 0xC1E1 - 0x8000] = spr_blob

    # 2. 10x6 identity tilemaps ($C77A-$C8E1, 6 x 60 bytes)
    tm = bytes(range(60))
    for i in range(6):
        off = 0xC77A - 0x8000 + i * 60
        b0[off : off + 60] = tm

    # 3. Disable Slot 0's vanilla Emerald Necklace OAM overlay ($CAF5 -> $CB4A empty list)
    assert b0[0xCAF5 - 0x8000 : 0xCAF7 - 0x8000] == bytes([0x13, 0xCB])
    b0[0xCAF5 - 0x8000 : 0xCAF7 - 0x8000] = bytes([0x4A, 0xCB])

    # 4. Relocated MMC3 Bank 2 CHR pointers ($E124-$E12F, 6 x 2 bytes at $8162 + i * $3C0)
    ptrs = bytearray()
    for i in range(6):
        addr = 0x8162 + i * 0x3C0
        ptrs.extend((addr & 0xFF, addr >> 8))
    b0[0xE124 - 0x8000 : 0xE130 - 0x8000] = ptrs


# ---------------------------------------------------------------------------
# Candidate Preview Generator for Dashboard Iteration (April in Rauru & Boulder)
# ---------------------------------------------------------------------------

def _draw_paris_matched_rauru(g: list[list[int]]) -> None:
    """Draw 'Rauru' at x=28..76, y=24..44 matching vanilla 'Paris' height & serif style."""
    # Clear 'Paris' ('P' x=31..48 y=23..45 including right loop at 47..48, 'aris' x=46..77 y=31..45)
    # while preserving 'April' (y<=22) and 'in' (x>=51).
    _fill_rect(g, 28, 23, 22, 23, 2)
    _fill_rect(g, 46, 31, 32, 15, 2)

    def draw_glyph(ox: int, oy: int, rows: list[str]) -> None:
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch == '#':
                    _pset(g, ox + dx + 1, oy + dy + 1, 0)
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch == '#':
                    _pset(g, ox + dx, oy + dy, 1)

    # 21px-tall calligraphic 'R' matching vanilla 22px 'P'
    glyph_R = [
        '##########....',
        '.###.....###..',
        '.##........##.',
        '.##........##.',
        '.##........##.',
        '.##........##.',
        '.##.......##..',
        '.##......##...',
        '.#########....',
        '.##....###....',
        '.##.....##....',
        '.##......##...',
        '.##......##...',
        '.##.......##..',
        '.##.......##..',
        '.##........##.',
        '.##........##.',
        '.##........##.',
        '.##........##.',
        '.##........##.',
        '####.......###',
    ]
    # 13px-tall lowercase glyphs matching vanilla 'aris'
    glyph_a = [
        '..#####.',
        '.##...##',
        '......##',
        '......##',
        '..######',
        '.##...##',
        '##....##',
        '##....##',
        '##....##',
        '##...###',
        '.####.##',
        '........',
        '........',
    ]
    glyph_u = [
        '###..###',
        '.##...##',
        '.##...##',
        '.##...##',
        '.##...##',
        '.##...##',
        '.##...##',
        '.##...##',
        '.##...##',
        '.##..###',
        '..###.##',
        '........',
        '........',
    ]
    glyph_r = [
        '###.###',
        '.###.##',
        '.##..##',
        '.##....',
        '.##....',
        '.##....',
        '.##....',
        '.##....',
        '.##....',
        '.##....',
        '####...',
        '.......',
        '.......',
    ]
    draw_glyph(28, 24, glyph_R)
    draw_glyph(43, 32, glyph_a)
    draw_glyph(52, 32, glyph_u)
    draw_glyph(61, 32, glyph_r)
    draw_glyph(68, 32, glyph_u)


def _april_paris_base(wheel_bytes: bytes) -> list[list[int]]:
    b0 = wheel_bytes[16 : 16 + 32768]
    tm = b0[0xC82E - 0x8000 : 0xC82E - 0x8000 + 60]
    chr_off = 0xE162 - 0x8000
    g = _new_canvas()
    for ty in range(6):
        for tx in range(10):
            t_idx = tm[ty * 10 + tx]
            tile = decode_tile(b0[chr_off + t_idx * 16 : chr_off + (t_idx + 1) * 16])
            for py in range(8):
                for px in range(8):
                    g[ty * 8 + py][tx * 8 + px] = tile[py][px]
    _fill_rect(g, 2, 1, 28, 46, 2)
    _draw_paris_matched_rauru(g)
    return g
