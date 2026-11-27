"""Build-time Z2/Barba sprite, animation, and palette theming for Wheel of Barba.

Extracts Barba (24x48) poses directly from roms/z2.nes at build time
(no original pixels or code committed).
"""

from __future__ import annotations

import assets
import boss_art
from pack_f13 import Asm6502


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
    # Title BG palette ($8801-$8810): swap magenta/pink for crimson & gold
    b0[0x8801 - 0x8000 : 0x8811 - 0x8000] = bytes.fromhex(
        '0f 16 27 30  0f 00 16 27  0f 06 16 30  0f 00 10 27'
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
