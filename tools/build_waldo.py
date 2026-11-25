"""Build the Barba-as-Waldo ROM hack (`build/waldo_barba.nes`) from `roms/waldo.nes`."""
from __future__ import annotations

import json
import math
import zlib
from pathlib import Path

import roar_sample
from assets import compile_assets, encounter_connector_rows, encounter_trail_rows
from boss_art import resize_x, shear_up, source_head, source_pair
from nes import CHR_OFFSET, HEADER_SIZE, decode_tile, encode_tile, load_source

ROOT = Path(__file__).resolve().parents[1]
WALDO_PATH = ROOT / 'roms/waldo.nes'
Z2_PATH = ROOT / 'roms/z2.nes'
OUT_PATH = ROOT / 'build/waldo_barba.nes'
PLAY_PATH = ROOT / 'play/standalone/waldo-barba.nes'
BARBA_JSON = ROOT / 'assets/barba.json'
CROWD_JSON = ROOT / 'assets/waldo_crowd.json'
ASH_JSON = ROOT / 'assets/ash.json'

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


SHOUT_CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ!?' ."
SHOUT_FONT_5X6 = {
    'A': ['01110', '10001', '11111', '10001', '10001', '10001'],
    'B': ['11110', '10001', '11110', '10001', '10001', '11110'],
    'C': ['01111', '10000', '10000', '10000', '10000', '01111'],
    'D': ['11110', '10001', '10001', '10001', '10001', '11110'],
    'E': ['11111', '10000', '11110', '10000', '10000', '11111'],
    'F': ['11111', '10000', '11110', '10000', '10000', '10000'],
    'G': ['01111', '10000', '10111', '10001', '10001', '01110'],
    'H': ['10001', '10001', '11111', '10001', '10001', '10001'],
    'I': ['11111', '00100', '00100', '00100', '00100', '11111'],
    'J': ['00111', '00010', '00010', '00010', '10010', '01100'],
    'K': ['10001', '10010', '11100', '10010', '10001', '10001'],
    'L': ['10000', '10000', '10000', '10000', '10000', '11111'],
    'M': ['10001', '11011', '10101', '10001', '10001', '10001'],
    'N': ['10001', '11001', '10101', '10011', '10001', '10001'],
    'O': ['01110', '10001', '10001', '10001', '10001', '01110'],
    'P': ['11110', '10001', '11110', '10000', '10000', '10000'],
    'Q': ['01110', '10001', '10001', '10101', '10010', '01101'],
    'R': ['11110', '10001', '11110', '10100', '10010', '10001'],
    'S': ['01111', '10000', '01110', '00001', '00001', '11110'],
    'T': ['11111', '00100', '00100', '00100', '00100', '00100'],
    'U': ['10001', '10001', '10001', '10001', '10001', '01110'],
    'V': ['10001', '10001', '10001', '10001', '01010', '00100'],
    'W': ['10001', '10001', '10001', '10101', '11011', '10001'],
    'X': ['10001', '01010', '00100', '00100', '01010', '10001'],
    'Y': ['10001', '01010', '00100', '00100', '00100', '00100'],
    'Z': ['11111', '00010', '00100', '01000', '10000', '11111'],
    '!': ['00100', '00100', '00100', '00100', '00000', '00100'],
    '?': ['01110', '10001', '00010', '00100', '00000', '00100'],
    "'": ['00100', '00100', '00000', '00000', '00000', '00000'],
    ' ': ['00000', '00000', '00000', '00000', '00000', '00000'],
    '.': ['00000', '00000', '00000', '00000', '00000', '00100'],
}
SHOUT_MESSAGES = [
    'BARBA!', 'RUN!', 'HELP!', 'AAAH!', 'NOOO!', 'DRAGON!',
    'YIKES!', 'FLEE!', 'OH NO!', 'SCARY!', 'RUUUN!', 'MOMMY!',
]


def write_shout_font(buf: bytearray) -> None:
    """Write 1px black-outlined (color 1) white (color 3) 8x8 font into 1KB bank 127 ($7F)."""
    # 1KB bank 127 = 4KB bank 31 + $C00 (tiles $C0..$FF in 4KB bank 31)
    for idx, ch in enumerate(SHOUT_CHARSET):
        glyph = SHOUT_FONT_5X6[ch]
        grid = [['0'] * 8 for _ in range(8)]
        for y in range(6):
            for x in range(5):
                if glyph[y][x] == '1':
                    grid[y + 1][x + 1] = '3'
        for y in range(8):
            for x in range(8):
                if grid[y][x] == '0' and any(
                    0 <= y + dy < 8 and 0 <= x + dx < 8 and grid[y + dy][x + dx] == '3'
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0)
                ):
                    grid[y][x] = '1'
        put_chr_tile(buf, bank_4k=31, tile_idx=0xC0 + idx, rows=[''.join(r) for r in grid])


def make_crowd_flee_code(base: int = 0xCD00) -> tuple[bytes, dict[str, int]]:
    """Assemble individualized 360-degree radial crowd-fleeing routines in Bank 16 ($CD00)."""
    # WRAM Bank 2 layout (leaving $7FFF free for pack_waldo's Start+Select guard):
    #   During $EEEB (level load):
    #     $6680-$673F : COLL_BITS_STG (192B; keeps $6800-$687F attributes & $7100-$713F right NT safe!)
    #     $7200-$77FF : BG_TILES (64x24 clean background + Barba + static props)
    #     $7800-$7EFF : staging for PERSON_X..PERSON_TIMER (7 pages)
    #   After $EC75 (CrowdStart) & during gameplay:
    #     $6000-$60FF : PERSON_X (256B, $FF = fled offscreen)
    #     $6100-$61FF : PERSON_Y (256B)
    #     $6200-$62FF : PERSON_WH (256B, (h<<4)|w)
    #     $6300-$63FF : PERSON_BAND (256B, 0..2)
    #     $6400-$64FF : PERSON_TLO (256B)
    #     $6500-$65FF : PERSON_THI (256B)
    #     $6600-$66FF : PERSON_TIMER (256B)
    #     $6700-$67FF : PERSON_DIR (256B: bit7=init, bit6=side(0=L,1=R), bit5=has_prev, bits2..0=last_dir)
    #     $6800-$68BF : CROWD_BITS (192B: 64x24 live crowd occupancy bitmap)
    #     $6900-$6EFF : FLOW_LR (1536B: 64x24 BFS flow field; lo=L exit dir, hi=R exit dir)
    #     $6F00-$6FFF : VISITED (192B during BFS) -> PERSON_AGE (256B during gameplay)
    #     $7000-$70FF : QX/QY (128B+128B during BFS) -> PERSON_STUCK (256B during gameplay)
    #     $7200-$77FF : BG_TILES (64x24 clean background + Barba + static props)
    #     $7800-$7DFF : LIVE_TILES (64x24 current nametable)
    #     $7E00-$7EBF : COLL_BITS (192B: 64x24 solid base scenery + w>=5 static props)
    #   State & PPU Queue ($7F00-$7F9F, leaving $7FFF untouched):
    #     $7F00       : CROWD_ACTIVE
    #     $7F01       : PERSON_COUNT (0..255)
    #     $7F02       : PPU_Q_COUNT (0..32)
    #     $7F03       : PERSON_CUR
    #     $7F04       : CROWD_BANK (level R7 bank 4..8)
    #     $7F05       : STEP_BUDGET
    #     $7F06       : CUR_WAS_VIS (0/1)
    #     $7F07       : CUR_IGNORE_COLL (0/1)
    #     $7F08       : CUR_W
    #     $7F09       : CUR_H
    #     $7F0A       : CUR_X
    #     $7F0B       : CUR_Y
    #     $7F0C       : CUR_NX
    #     $7F0D       : CUR_NY
    #     $7F0E       : CUR_IDX
    #     $7F0F       : CUR_TILE_IDX
    #     $7F10-$7F12 : BAND_MIN_Y[0..2]
    #     $7F13-$7F15 : BAND_MAX_Y[0..2]
    #     $7F16       : ABS_DX
    #     $7F17       : ABS_DY
    #     $7F18-$7F27 : TMP_TILES (up to 16 bytes)
    #     $7F28       : SCROLL_TX
    #     $7F29       : IDEAL_DIR (0..7)
    #     $7F2A       : CAND_IDX (0..7)
    #     $7F2B       : TRY_DIR (0..7)
    #     $7F2C       : VIS_END (SCROLL_TX + 32)
    #     $7F2D       : REV_DIR ($FF or 0..7)
    #     $7F2E       : BFS_PASS (0/1) / CHOSEN_CI
    #     $7F2F       : CUR_BAND / Q_HEAD
    #     $7F30-$7F4F : PPU_Q_HI (32B)
    #     $7F50-$7F6F : PPU_Q_LO (32B)
    #     $7F70-$7F8F : PPU_Q_TILE (32B)
    #     $7F90-$7F95 : SHOUT_ACTIVE..SHOUT_PAL_SET
    #     $7F96       : Q_TAIL
    #     $7F97       : BFS_CX
    #     $7F98       : BFS_CY
    #     $7F99       : BFS_D
    buf = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str, str]] = []

    def emit(*b: int) -> None:
        buf.extend(b)

    def label(name: str) -> None:
        labels[name] = base + len(buf)

    def rel(op: int, target: str) -> None:
        emit(op, 0)
        fixups.append((len(buf) - 1, 'rel', target))

    def abs16(op: int, target: str) -> None:
        emit(op, 0, 0)
        fixups.append((len(buf) - 2, 'abs', target))

    # CrowdNmiFlush ($CD00): jumped to from $E304 after OAM DMA when $05 == $20.
    label('CrowdNmiFlush')
    emit(0xAD, 0x00, 0x7F)              # LDA CROWD_ACTIVE
    rel(0xD0, 'nmi_is_active')
    abs16(0x4C, 'nmi_done')
    label('nmi_is_active')
    # Map R2 ($1000-$13FF, tiles $00-$3F) -> 1KB bank 196 ($C4) for Barba & fireballs,
    # and R3 ($1400-$17FF, tiles $40-$7F) -> 1KB bank 127 ($7F) for shout font.
    emit(0xA9, 0x42, 0x8D, 0x00, 0x80, 0xA9, 0xC4, 0x8D, 0x01, 0x80)
    emit(0xA9, 0x43, 0x8D, 0x00, 0x80, 0xA9, 0x7F, 0x8D, 0x01, 0x80)
    emit(0xAD, 0x04, 0x02, 0xC9, 0x43)  # if $0204 == #$43 (R3), keep $0203 = #$7F
    rel(0xD0, 'nmi_r2_chk')
    emit(0xA9, 0x7F, 0x8D, 0x03, 0x02)
    label('nmi_r2_chk')
    emit(0xAD, 0x04, 0x02, 0xC9, 0x42)  # if $0204 == #$42 (R2), keep $0203 = #$C4
    rel(0xD0, 'nmi_r3_ok')
    emit(0xA9, 0xC4, 0x8D, 0x03, 0x02)
    label('nmi_r3_ok')
    # Set Sprite Pal 2 ($3F19..$3F1B = $16 red, $27 gold, $38 ivory) for Barba & fireballs,
    # and Sprite Pal 3 ($3F1D..$3F1F = $0E black, $16 red, $30 white) for shouts, once when PPU_Q is empty.
    emit(0xAD, 0x02, 0x7F)              # LDA PPU_Q_COUNT
    rel(0xD0, 'nmi_q_start')
    emit(0xAD, 0x95, 0x7F)              # SHOUT_PAL_SET
    rel(0xD0, 'nmi_done')
    emit(0xA9, 0x01, 0x8D, 0x95, 0x7F)
    emit(0x2C, 0x02, 0x20)
    emit(0xA9, 0x3F, 0x8D, 0x06, 0x20, 0xA9, 0x19, 0x8D, 0x06, 0x20)
    emit(0xA9, 0x16, 0x8D, 0x07, 0x20)  # $3F19 = $16 (red)
    emit(0xA9, 0x27, 0x8D, 0x07, 0x20)  # $3F1A = $27 (gold)
    emit(0xA9, 0x38, 0x8D, 0x07, 0x20)  # $3F1B = $38 (ivory)
    emit(0xA9, 0x0E, 0x8D, 0x07, 0x20)  # $3F1C (unused mirror)
    emit(0xA9, 0x0E, 0x8D, 0x07, 0x20)  # $3F1D = $0E (black)
    emit(0xA9, 0x16, 0x8D, 0x07, 0x20)  # $3F1E = $16 (red)
    emit(0xA9, 0x30, 0x8D, 0x07, 0x20)  # $3F1F = $30 (white)
    rel(0xD0, 'nmi_done')               # BNE nmi_done (A = $30 != 0)
    label('nmi_q_start')
    emit(0x2C, 0x02, 0x20)              # BIT $2002
    emit(0xA2, 0x00)                    # LDX #0
    label('nmi_q_loop')
    emit(0xBD, 0x30, 0x7F, 0x8D, 0x06, 0x20)  # LDA PPU_Q_HI,X; STA $2006
    emit(0xBD, 0x50, 0x7F, 0x8D, 0x06, 0x20)  # LDA PPU_Q_LO,X; STA $2006
    emit(0xBD, 0x70, 0x7F, 0x8D, 0x07, 0x20)  # LDA PPU_Q_TILE,X; STA $2007
    emit(0xE8)                                # INX
    emit(0xEC, 0x02, 0x7F)                    # CPX PPU_Q_COUNT
    rel(0xD0, 'nmi_q_loop')
    emit(0xA9, 0x00, 0x8D, 0x02, 0x7F)        # LDA #0; STA PPU_Q_COUNT
    label('nmi_done')
    emit(0x4C, 0x74, 0xE3)              # JMP $E374

    # CrowdInit: called from $EE28 (replaces LDA $F3D1,X; X = level 0..4).
    label('CrowdInit')
    emit(0xA9, 0x00)
    emit(0x8D, 0x00, 0x7F)              # STA CROWD_ACTIVE
    emit(0x8D, 0x01, 0x7F)              # STA PERSON_COUNT
    emit(0x8D, 0x02, 0x7F)              # STA PPU_Q_COUNT
    emit(0x8D, 0x03, 0x7F)              # STA PERSON_CUR
    emit(0x8D, 0x90, 0x7F)              # STA SHOUT_ACTIVE
    emit(0x8D, 0x93, 0x7F)              # STA SHOUT_STR_IDX
    emit(0x8D, 0x94, 0x7F)              # STA SHOUT_SCAN
    emit(0x8D, 0x95, 0x7F)              # STA SHOUT_PAL_SET
    # Clear COLL_BITS_STG ($6680-$673F, 192B)
    emit(0xA0, 0xBF)
    label('ci_clr_coll')
    emit(0x99, 0x80, 0x66, 0x88)
    rel(0xD0, 'ci_clr_coll')
    emit(0x99, 0x80, 0x66)              # Y = 0
    emit(0xA9, 0x0F, 0x8D, 0x91, 0x7F)  # SHOUT_TIMER = 15 (first yell soon after start)
    emit(0xBD, 0xDB, 0xF3, 0x8D, 0x04, 0x7F)  # LDA $F3DB,X; STA CROWD_BANK
    emit(0xBD, 0xD1, 0xF3)              # LDA $F3D1,X
    emit(0x60)

    # CrowdExit: called from $EBFC on search-level exit (replaces JSR $E4EC).
    # Clears CROWD_ACTIVE, hides Barba/Fireball OAM slots, and restores R2/R3
    # so Barba's overworld pose_b tiles ($40..$47) do not render as shout font glyphs.
    label('CrowdExit')
    emit(0xA9, 0x00)
    emit(0x8D, 0x00, 0x7F)              # STA CROWD_ACTIVE
    emit(0x8D, 0x02, 0x7F)              # STA PPU_Q_COUNT
    emit(0x8D, 0x90, 0x7F)              # STA SHOUT_ACTIVE
    emit(0xA9, 0xFE, 0xA2, 0x00)
    label('ce_hide_fb')
    emit(0x9D, 0x10, 0x07, 0xE8, 0xE8, 0xE8, 0xE8, 0xE0, 0x18)  # slots 4..9 (6 fireballs)
    rel(0xD0, 'ce_hide_fb')
    emit(0xA2, 0x00)
    label('ce_hide_bb')
    emit(0x9D, 0x60, 0x07, 0xE8, 0xE8, 0xE8, 0xE8, 0xE0, 0x40)  # slots 24..39 (16 Barba)
    rel(0xD0, 'ce_hide_bb')
    emit(0xA9, 0x42, 0x8D, 0x00, 0x80)  # R2 = 1KB bank 8
    emit(0xA9, 0x08, 0x8D, 0x01, 0x80)
    emit(0xA9, 0x43, 0x8D, 0x00, 0x80)  # R3 = 1KB bank 9
    emit(0xA9, 0x09, 0x8D, 0x01, 0x80)
    emit(0xAD, 0x04, 0x02, 0xC9, 0x43)  # if $0204 == #$43 (R3), restore $0203 = #$09
    rel(0xD0, 'ce_r3_ok')
    emit(0xA9, 0x09, 0x8D, 0x03, 0x02)
    label('ce_r3_ok')
    emit(0x4C, 0xEC, 0xE4)              # JMP $E4EC

    # CrowdSaveBg: called from $EF65 (replaces LDA #$C0; STA $22).
    # Copies ($50 - $4F) * 64 bytes from $6000 to BG_TILES ($7200) + $4F*64,
    # and records base-scenery collision bits (non-zero tiles) into COLL_BITS_STG ($6680 + $4F*8).
    label('CrowdSaveBg')
    emit(0xA6, 0x4D)                    # LDX $4D (band 0..2)
    emit(0x8E, 0x2F, 0x7F)              # STX CUR_BAND ($7F2F)
    emit(0xA5, 0x4F, 0x9D, 0x10, 0x7F)  # STA BAND_MIN_Y,X
    emit(0x85, 0x1A)                    # STA $1A (cur_ty)
    emit(0xA5, 0x50, 0x9D, 0x13, 0x7F)  # STA BAND_MAX_Y,X
    emit(0xA9, 0x00, 0x85, 0x26, 0xA9, 0x60, 0x85, 0x27)
    emit(0xA5, 0x4F, 0x4A, 0x4A, 0x18, 0x69, 0x72, 0x85, 0x2B)
    emit(0xA5, 0x4F, 0x29, 0x03, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x85, 0x2A)
    emit(0xA5, 0x50, 0x38, 0xE5, 0x4F, 0xAA)
    label('cp_band_row')
    emit(0xA0, 0x3F)
    label('cp_band_col')
    emit(0xB1, 0x26, 0x91, 0x2A, 0x88)
    rel(0x10, 'cp_band_col')
    # Build 8 collision bytes for row $1A at $6680 + $1A*8
    emit(0x8A, 0x48)                    # TXA; PHA (preserve row counter)
    emit(0xA5, 0x1A, 0x0A, 0x0A, 0x0A, 0xAA)  # LDX cur_ty*8
    emit(0xA9, 0x00, 0x85, 0x1D)        # byte_idx = 0..7
    label('cp_coll_byte')
    emit(0xA9, 0x00, 0x85, 0x1C)        # bit_acc = 0
    emit(0xA5, 0x1D, 0x0A, 0x0A, 0x0A, 0x18, 0x69, 0x07, 0xA8)  # Y = byte_idx*8 + 7
    emit(0xA9, 0x08, 0x85, 0x1E)        # 8 bits
    label('cp_coll_bit')
    emit(0xB1, 0x26)                    # LDA ($26),Y
    rel(0xF0, 'cp_coll_zero')
    emit(0x38)                          # SEC
    rel(0xB0, 'cp_coll_rol')
    label('cp_coll_zero')
    emit(0x18)                          # CLC
    label('cp_coll_rol')
    emit(0x26, 0x1C)                    # ROL $1C
    emit(0x88)                          # DEY
    emit(0xC6, 0x1E)                    # DEC $1E
    rel(0xD0, 'cp_coll_bit')
    emit(0xA5, 0x1C)
    emit(0x9D, 0x80, 0x66)              # STA COLL_BITS_STG,X ($6680..$673F)
    emit(0xE8)                          # INX
    emit(0xE6, 0x1D, 0xA5, 0x1D, 0xC9, 0x08)
    rel(0xD0, 'cp_coll_byte')
    emit(0xE6, 0x1A)                    # INC cur_ty
    emit(0x68, 0xAA)                    # PLA; TAX (restore row counter)
    emit(0xA5, 0x26, 0x18, 0x69, 0x40, 0x85, 0x26)
    rel(0x90, 'cp_src_ok')
    emit(0xE6, 0x27)
    label('cp_src_ok')
    emit(0xA5, 0x2A, 0x18, 0x69, 0x40, 0x85, 0x2A)
    rel(0x90, 'cp_dst_ok')
    emit(0xE6, 0x2B)
    label('cp_dst_ok')
    emit(0xCA)
    rel(0xD0, 'cp_band_row')
    emit(0xA9, 0xC0, 0x85, 0x22, 0x60)

    # CrowdStampCheck: called from $F1AC (replaces JSR $E4BF).
    # Record tagged fleeing people/pets (descriptor byte 5 bit 6 = $40) into staging ($7800-$7EFF) up to 255.
    # For Barba (bit 7), skip BG stamping entirely because Barba is rendered as a 32x32 moving OAM sprite.
    # For static props (bit 6 = 0), stamp into BG_TILES ($7200) so fleeing people never erase them.
    label('CrowdStampCheck')
    emit(0xA0, 0x05, 0xB1, 0x4B)        # LDY #5; LDA ($4B),Y
    rel(0x30, 'barba_skip_stamp')       # BMI -> Barba -> skip BG stamp
    emit(0x29, 0x40)                    # AND #$40 (tagged fleeing person?)
    rel(0xF0, 'stamp_to_bg')            # BEQ -> static prop -> stamp into BG_TILES
    emit(0xAD, 0x01, 0x7F, 0xC9, 0xFF)  # PERSON_COUNT < 255?
    rel(0xB0, 'stamp_to_bg')
    emit(0xA0, 0x00, 0xB1, 0x4B)        # w
    rel(0xF0, 'stamp_to_bg')
    emit(0x85, 0x1C)
    emit(0xC8, 0xB1, 0x4B)              # h
    rel(0xF0, 'stamp_to_bg')
    emit(0x0A, 0x0A, 0x0A, 0x0A, 0x05, 0x1C)  # (h<<4)|w
    emit(0xAE, 0x01, 0x7F)              # LDX PERSON_COUNT
    emit(0x9D, 0x00, 0x7A)              # STA $7A00,X (staging WH)
    emit(0xA5, 0x24, 0x9D, 0x00, 0x78)  # STA $7800,X (staging X)
    emit(0xA5, 0x22, 0x9D, 0x00, 0x79)  # STA $7900,X (staging Y)
    emit(0xAD, 0x2F, 0x7F, 0x9D, 0x00, 0x7B)  # STA $7B00,X (staging BAND)
    emit(0xA0, 0x02, 0xB1, 0x4B, 0x9D, 0x00, 0x7C)  # STA $7C00,X (staging TLO)
    emit(0xC8, 0xB1, 0x4B, 0x9D, 0x00, 0x7D)        # STA $7D00,X (staging THI)
    emit(0x8A, 0x29, 0x03, 0x18, 0x69, 0x01)        # initial timer = 1 + (X & 3)
    emit(0x9D, 0x00, 0x7E)              # STA $7E00,X (staging TIMER)
    emit(0xEE, 0x01, 0x7F)              # INC PERSON_COUNT
    emit(0x4C, 0xBF, 0xE4)              # JMP $E4BF
    label('barba_skip_stamp')
    emit(0x60)                          # RTS (Barba is OAM sprite, not BG)

    # Stamp Barba or static prop into BG_TILES ($7200 + $22*64 + $24),
    # and set all non-zero tiles in COLL_BITS_STG ($6680-$673F) so people route cleanly around static props.
    label('stamp_to_bg')
    emit(0xA5, 0x22, 0x85, 0x1E)        # $1E = cur_ty
    emit(0x4A, 0x4A, 0x18, 0x69, 0x72, 0x85, 0x2B)
    emit(0xA5, 0x22, 0x29, 0x03, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A)
    emit(0x18, 0x65, 0x24, 0x85, 0x2A)
    rel(0x90, 'stamp_ptr_ok')
    emit(0xE6, 0x2B)
    label('stamp_ptr_ok')
    emit(0xA0, 0x02, 0xB1, 0x4B, 0x85, 0x26, 0xC8, 0xB1, 0x4B, 0x85, 0x27)
    emit(0xA0, 0x01, 0xB1, 0x4B, 0x85, 0x1C)
    label('stamp_row')
    emit(0xA0, 0x00, 0xB1, 0x4B, 0x85, 0x1D, 0xA0, 0x00)
    label('stamp_col')
    emit(0xB1, 0x26, 0x91, 0x2A)
    rel(0xF0, 'stamp_no_coll')          # tile == $00 -> not solid
    emit(0xA5, 0x1E, 0xC9, 0x18)        # ty < 24?
    rel(0xB0, 'stamp_no_coll')
    emit(0x98, 0x18, 0x65, 0x24)        # A = tx = $24 + Y
    emit(0xC9, 0x40)                    # tx < 64?
    rel(0xB0, 'stamp_no_coll')
    emit(0x85, 0x1F)                    # $1F = tx
    emit(0x4A, 0x4A, 0x4A, 0x85, 0x1A)  # tx >> 3
    emit(0xA5, 0x1E, 0x0A, 0x0A, 0x0A, 0x05, 0x1A, 0xAA)  # X = (ty << 3) | (tx >> 3)
    emit(0x98, 0x48)                    # save Y
    emit(0xA5, 0x1F, 0x29, 0x07, 0xA8)  # Y = tx & 7
    emit(0xBD, 0x80, 0x66)
    abs16(0x19, 'BIT_MASK')             # ORA BIT_MASK,Y
    emit(0x9D, 0x80, 0x66)
    emit(0x68, 0xA8)                    # restore Y
    label('stamp_no_coll')
    emit(0xC8, 0xC4, 0x1D)
    rel(0xD0, 'stamp_col')
    emit(0xA5, 0x26, 0x18, 0x65, 0x1D, 0x85, 0x26)
    rel(0x90, 'stamp_src_ok')
    emit(0xE6, 0x27)
    label('stamp_src_ok')
    emit(0xA5, 0x2A, 0x18, 0x69, 0x40, 0x85, 0x2A)
    rel(0x90, 'stamp_dst_ok')
    emit(0xE6, 0x2B)
    label('stamp_dst_ok')
    emit(0xE6, 0x1E)                    # INC cur_ty
    emit(0xC6, 0x1C)
    rel(0xD0, 'stamp_row')
    emit(0x4C, 0xBF, 0xE4)

    # CrowdStart: called from $EC75 (replaces JSR $E557, after $F358 has uploaded to PPU).
    # 1. Save $7E00-$7EFF (staging PERSON_TIMER) -> $6800-$68FF (attributes already uploaded).
    # 2. Copy COLL_BITS_STG ($6680-$673F, 192B) -> COLL_BITS ($7E00-$7EBF).
    # 3. Copy 6 staging pages $7800-$7DFF -> $6000-$65FF, and $6800-$68FF -> $6600-$66FF.
    # 4. Clear PERSON_DIR ($6700-$67FF).
    # 5. Interleave $6A00 (left) + $6E00 (right) -> LIVE_TILES ($7800-$7DFF).
    # 6. Clear CROWD_BITS ($6800-$68BF) & populate with initial person rects.
    # 7. Run two BFS passes to build FLOW_LR ($6900-$6EFF).
    # 8. Clear PERSON_AGE ($6F00-$6FFF) & PERSON_STUCK ($7000-$70FF).
    # CrowdPrep: called from $EC1D (replaces JSR $F358 while PPU rendering is OFF).
    # First uploads nametable/attributes/palettes via $F358, then prepares crowd arrays and BFS flow fields
    # BEFORE fade-in so people start fleeing immediately on frame 1 with zero perceived freeze!
    # Leaves CROWD_ACTIVE = 0 until CrowdActivate ($EC75).
    label('CrowdPrep')
    emit(0x20, 0x58, 0xF3)              # JSR $F358 (upload NT/attr/pal while screen is OFF)
    emit(0xA2, 0x00)
    label('cs_sv_tmr')
    emit(0xBD, 0x00, 0x7E, 0x9D, 0x00, 0x68, 0xE8)
    rel(0xD0, 'cs_sv_tmr')

    emit(0xA2, 0xBF)
    label('cs_cp_coll')
    emit(0xBD, 0x80, 0x66, 0x9D, 0x00, 0x7E, 0xCA)
    rel(0xD0, 'cs_cp_coll')
    emit(0xBD, 0x80, 0x66, 0x9D, 0x00, 0x7E)

    emit(0xA9, 0x00, 0x85, 0x26, 0x85, 0x2A)
    emit(0xA9, 0x78, 0x85, 0x27)        # src = $7800
    emit(0xA9, 0x60, 0x85, 0x2B)        # dst = $6000
    emit(0xA2, 0x06)                    # 6 pages ($6000-$65FF)
    label('cs_st_page')
    emit(0xA0, 0x00)
    label('cs_st_byte')
    emit(0xB1, 0x26, 0x91, 0x2A, 0xC8)
    rel(0xD0, 'cs_st_byte')
    emit(0xE6, 0x27, 0xE6, 0x2B, 0xCA)
    rel(0xD0, 'cs_st_page')

    emit(0xA2, 0x00)
    label('cs_rs_tmr')
    emit(0xBD, 0x00, 0x68, 0x9D, 0x00, 0x66, 0xE8)
    rel(0xD0, 'cs_rs_tmr')

    # Initialize PERSON_DIR ($6700..$67FF): 0 = uninitialized
    emit(0xA2, 0x00, 0xA9, 0x00)
    label('cs_init_dir')
    emit(0x9D, 0x00, 0x67, 0xE8)
    rel(0xD0, 'cs_init_dir')

    # Interleave 24 rows from $6A00 (left row 4) & $6E00 (right row 4) -> $7800 (LIVE_TILES)
    emit(0xA9, 0x00, 0x85, 0x26, 0xA9, 0x6A, 0x85, 0x27)  # left = $6A00
    emit(0xA9, 0x00, 0x85, 0x1A, 0xA9, 0x6E, 0x85, 0x1B)  # right = $6E00
    emit(0xA9, 0x00, 0x85, 0x2A, 0xA9, 0x78, 0x85, 0x2B)  # live = $7800
    emit(0xA2, 0x18)                                      # 24 rows
    label('cs_lv_row')
    emit(0xA0, 0x1F)
    label('cs_lv_l')
    emit(0xB1, 0x26, 0x91, 0x2A, 0x88)
    rel(0x10, 'cs_lv_l')
    emit(0xA5, 0x2A, 0x18, 0x69, 0x20, 0x85, 0x2A)
    rel(0x90, 'cs_lv_r_ptr')
    emit(0xE6, 0x2B)
    label('cs_lv_r_ptr')
    emit(0xA0, 0x1F)
    label('cs_lv_r')
    emit(0xB1, 0x1A, 0x91, 0x2A, 0x88)
    rel(0x10, 'cs_lv_r')
    emit(0xA5, 0x26, 0x18, 0x69, 0x20, 0x85, 0x26)
    rel(0x90, 'cs_adv_r')
    emit(0xE6, 0x27)
    label('cs_adv_r')
    emit(0xA5, 0x1A, 0x18, 0x69, 0x20, 0x85, 0x1A)
    rel(0x90, 'cs_adv_lv')
    emit(0xE6, 0x1B)
    label('cs_adv_lv')
    emit(0xA5, 0x2A, 0x18, 0x69, 0x20, 0x85, 0x2A)
    rel(0x90, 'cs_lv_next')
    emit(0xE6, 0x2B)
    label('cs_lv_next')
    emit(0xCA)
    rel(0xD0, 'cs_lv_row')

    # Clear CROWD_BITS ($6800-$68BF, 192B) & mark all initial person rects
    emit(0xA2, 0xBF, 0xA9, 0x00)
    label('cs_clr_crowd')
    emit(0x9D, 0x00, 0x68, 0xCA)
    rel(0xD0, 'cs_clr_crowd')
    emit(0x9D, 0x00, 0x68)              # X=0
    emit(0xAC, 0x01, 0x7F)              # LDY PERSON_COUNT
    rel(0xF0, 'cs_crowd_done')
    emit(0xA2, 0x00)
    label('cs_mark_p')
    emit(0x8E, 0x0E, 0x7F)
    emit(0xBD, 0x00, 0x60, 0x8D, 0x0C, 0x7F)  # CUR_NX = PERSON_X[X]
    emit(0xBD, 0x00, 0x61, 0x8D, 0x0D, 0x7F)  # CUR_NY = PERSON_Y[X]
    emit(0xBD, 0x00, 0x62, 0x48, 0x29, 0x0F, 0x8D, 0x08, 0x7F)
    emit(0x68, 0x4A, 0x4A, 0x4A, 0x4A, 0x8D, 0x09, 0x7F)
    abs16(0x20, 'SetCrowdNewRect')
    emit(0xAE, 0x0E, 0x7F, 0xE8, 0xEC, 0x01, 0x7F)
    rel(0xD0, 'cs_mark_p')
    label('cs_crowd_done')

    # Populate FLOW_LR ($6900-$6EFF, 1536B) directly from COLL_BITS ($7E00-$7EBF, 192B):
    # $EE if blocked (COLL_BITS bit=1), $FF if passable & unvisited.
    emit(0xA9, 0x00, 0x85, 0x2A, 0xA9, 0x69, 0x85, 0x2B)  # ptr = $6900
    emit(0xA2, 0x00)                                      # X = 0..191
    label('cs_fl_byte')
    emit(0xBD, 0x00, 0x7E, 0x85, 0x1A)                    # $1A = COLL_BITS[X]
    emit(0xA0, 0x00)                                      # Y = 0..7
    label('cs_fl_bit')
    emit(0xA9, 0xFF)                                      # passable & unvisited
    emit(0x46, 0x1A)                                      # LSR $1A -> bit -> C
    rel(0x90, 'cs_fl_pass')
    emit(0xA9, 0xEE)                                      # blocked
    label('cs_fl_pass')
    emit(0x91, 0x2A)
    emit(0xC8, 0xC0, 0x08)
    rel(0xD0, 'cs_fl_bit')
    emit(0xA5, 0x2A, 0x18, 0x69, 0x08, 0x85, 0x2A)
    rel(0x90, 'cs_fl_ptr_ok')
    emit(0xE6, 0x2B)
    label('cs_fl_ptr_ok')
    emit(0xE8, 0xE0, 0xC0)
    rel(0xD0, 'cs_fl_byte')

    # Mark Barba's rect ($718B=X, $718C=Y, $718D=W, $718E=H) as $EE in FLOW_LR
    emit(0xAD, 0x8D, 0x71)                                # BARBA_W
    rel(0xF0, 'cs_barba_done')
    emit(0xAD, 0x8E, 0x71)                                # BARBA_H
    rel(0xF0, 'cs_barba_done')
    emit(0xA9, 0x00, 0x85, 0x1E)                          # dy = 0
    label('cs_bb_row')
    emit(0xAD, 0x8C, 0x71, 0x18, 0x65, 0x1E)              # ty = BARBA_Y + dy
    emit(0xC9, 0x18)
    rel(0xB0, 'cs_bb_next_row')
    emit(0x85, 0x1D)
    emit(0xA9, 0x00, 0x85, 0x1F)                          # dx = 0
    label('cs_bb_col')
    emit(0xAD, 0x8B, 0x71, 0x18, 0x65, 0x1F)              # tx = BARBA_X + dx
    emit(0xC9, 0x40)
    rel(0xB0, 'cs_bb_next_col')
    emit(0x85, 0x1C)
    emit(0xA5, 0x1D, 0x4A, 0x4A, 0x18, 0x69, 0x69, 0x85, 0x27)
    emit(0xA5, 0x1D, 0x29, 0x03, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x18, 0x65, 0x1C)
    emit(0x85, 0x26)
    rel(0x90, 'cs_bb_ptr_ok')
    emit(0xE6, 0x27)
    label('cs_bb_ptr_ok')
    emit(0xA0, 0x00, 0xA9, 0xEE, 0x91, 0x26)
    label('cs_bb_next_col')
    emit(0xE6, 0x1F, 0xA5, 0x1F, 0xCD, 0x8D, 0x71)
    rel(0xD0, 'cs_bb_col')
    label('cs_bb_next_row')
    emit(0xE6, 0x1E, 0xA5, 0x1E, 0xCD, 0x8E, 0x71)
    rel(0xD0, 'cs_bb_row')
    label('cs_barba_done')

    # Run BFS Pass 0 (Left exit x=0) and Pass 1 (Right exit x=63)
    emit(0xA9, 0x00, 0x8D, 0x2E, 0x7F)
    abs16(0x20, 'BuildFlowBfs')
    emit(0xA9, 0x01, 0x8D, 0x2E, 0x7F)
    abs16(0x20, 'BuildFlowBfs')

    # Zero PERSON_AGE ($6F00-$6FFF) and PERSON_STUCK ($7000-$70FF)
    emit(0xA2, 0x00, 0xA9, 0x00)
    label('cs_clr_age')
    emit(0x9D, 0x00, 0x6F)
    emit(0x9D, 0x00, 0x70)
    emit(0xE8)
    rel(0xD0, 'cs_clr_age')
    emit(0x60)                                            # RTS (leave CROWD_ACTIVE = 0 until CrowdActivate)

    # CrowdActivate: called from $EC75 after fade-in completes.
    label('CrowdActivate')
    abs16(0x20, 'BarbaInit')
    emit(0xA9, 0x01, 0x8D, 0x00, 0x7F)                    # CROWD_ACTIVE = 1
    emit(0xA9, 0x08, 0x4C, 0x57, 0xE5)                    # JMP $E557

    # Helper: BuildFlowBfs(BFS_PASS $7F2E: 0=Left exit x=0 dir=6, 1=Right exit x=63 dir=2)
    # Uses $FF=unvisited/$EE=blocked directly in FLOW_LR ($6900-$6EFF), per-band Y clamp,
    # and 256-entry ring buffer QX ($6F00-$6FFF) / QY ($7000-$70FF).
    label('BuildFlowBfs')
    emit(0xA9, 0x00)
    emit(0x8D, 0x2F, 0x7F)              # Q_HEAD = 0
    emit(0x8D, 0x96, 0x7F)              # Q_TAIL = 0

    # Seed x=0 (if pass 0) or x=63 (if pass 1) across y=0..23
    emit(0xA9, 0x00, 0x85, 0x1D)        # ty = 0
    label('bfs_seed_loop')
    emit(0xA9, 0x00)
    emit(0xAE, 0x2E, 0x7F)
    rel(0xF0, 'bfs_seed_x_ok')
    emit(0xA9, 0x3F)                    # x = 63
    label('bfs_seed_x_ok')
    emit(0x85, 0x1C)
    emit(0xA9, 0x06)                    # exit dir = 6 (West)
    emit(0xAE, 0x2E, 0x7F)
    rel(0xF0, 'bfs_seed_dir_ok')
    emit(0xA9, 0x02)                    # exit dir = 2 (East)
    label('bfs_seed_dir_ok')
    abs16(0x20, 'BfsVisitAndPush')
    emit(0xE6, 0x1D, 0xA5, 0x1D, 0xC9, 0x18)
    rel(0xD0, 'bfs_seed_loop')

    # Main BFS loop
    label('bfs_pop_loop')
    emit(0xAE, 0x2F, 0x7F, 0xEC, 0x96, 0x7F)  # Q_HEAD == Q_TAIL?
    rel(0xD0, 'bfs_have_item')
    emit(0x60)                                # done!
    label('bfs_have_item')
    emit(0xBD, 0x00, 0x6F, 0x8D, 0x97, 0x7F)  # BFS_CX = QX[X]
    emit(0xBD, 0x00, 0x70, 0x8D, 0x98, 0x7F)  # BFS_CY = QY[X]
    emit(0xE8, 0x8E, 0x2F, 0x7F)              # Q_HEAD = (Q_HEAD + 1) & $FF

    # Determine band Y bounds [CUR_BAND_MIN, CUR_BAND_MAX) for BFS_CY so flow never crosses CHR bands
    emit(0xAD, 0x98, 0x7F)
    emit(0xCD, 0x13, 0x7F)                    # < BAND_MAX_Y[0]?
    rel(0x90, 'bfs_b0')
    emit(0xCD, 0x14, 0x7F)                    # < BAND_MAX_Y[1]?
    rel(0x90, 'bfs_b1')
    emit(0xA2, 0x02)
    rel(0xD0, 'bfs_b_ok')
    label('bfs_b0')
    emit(0xA2, 0x00)
    rel(0xF0, 'bfs_b_ok')
    label('bfs_b1')
    emit(0xA2, 0x01)
    label('bfs_b_ok')
    emit(0xBD, 0x10, 0x7F, 0x8D, 0x9A, 0x7F)  # CUR_BAND_MIN = BAND_MIN_Y[X]
    emit(0xBD, 0x13, 0x7F, 0x8D, 0x9B, 0x7F)  # CUR_BAND_MAX = BAND_MAX_Y[X]

    emit(0xA9, 0x00, 0x8D, 0x99, 0x7F)        # BFS_D = 0..7
    label('bfs_nbr_loop')
    emit(0xAE, 0x99, 0x7F)
    abs16(0xBC, 'BFS_DIRS')                   # Y = dir (0..7)
    emit(0xAD, 0x97, 0x7F, 0x18)
    abs16(0x79, 'DIR_DX')
    emit(0xC9, 0x40)                          # unsigned < 64?
    rel(0xB0, 'bfs_nbr_next')
    emit(0x85, 0x1C)                          # $1C = nx
    emit(0xAD, 0x98, 0x7F, 0x18)
    abs16(0x79, 'DIR_DY')
    emit(0xCD, 0x9B, 0x7F)                    # >= CUR_BAND_MAX? (catches $FF wrap too)
    rel(0xB0, 'bfs_nbr_next')
    emit(0xCD, 0x9A, 0x7F)                    # < CUR_BAND_MIN?
    rel(0x90, 'bfs_nbr_next')
    emit(0x85, 0x1D)                          # $1D = ny
    emit(0x98, 0x49, 0x04)                    # A = dir ^ 4
    abs16(0x20, 'BfsVisitAndPush')
    label('bfs_nbr_next')
    emit(0xEE, 0x99, 0x7F, 0xAD, 0x99, 0x7F, 0xC9, 0x08)
    rel(0xD0, 'bfs_nbr_loop')
    abs16(0x4C, 'bfs_pop_loop')

    # Helper: BfsVisitAndPush(A=dir 0..7, $1C=tx, $1D=ty)
    label('BfsVisitAndPush')
    emit(0x85, 0x1A)                                # $1A = dir (0..7)
    # Compute FLOW_LR pointer in $26/$27 ($6900 + ty*64 + tx)
    emit(0xA5, 0x1D, 0x4A, 0x4A, 0x18, 0x69, 0x69, 0x85, 0x27)
    emit(0xA5, 0x1D, 0x29, 0x03, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x18, 0x65, 0x1C)
    emit(0x85, 0x26)
    rel(0x90, 'bvp_ptr_ok')
    emit(0xE6, 0x27)
    label('bvp_ptr_ok')
    emit(0xA0, 0x00, 0xB1, 0x26)                    # A = FLOW_LR[ty, tx]
    emit(0xAE, 0x2E, 0x7F)                          # BFS_PASS == 0?
    rel(0xD0, 'bvp_pass1')
    emit(0xC9, 0xFF)                                # Pass 0: unvisited passable == $FF
    rel(0xD0, 'bvp_done')
    emit(0xA5, 0x1A, 0x09, 0xF0, 0x91, 0x26)        # write $F0 | dir
    rel(0xD0, 'bvp_push')
    label('bvp_pass1')
    emit(0xC9, 0xF0)                                # Pass 1: unvisited passable >= $F0
    rel(0x90, 'bvp_done')
    emit(0x29, 0x0F, 0x85, 0x1B)                    # keep low nibble
    emit(0xA5, 0x1A, 0x0A, 0x0A, 0x0A, 0x0A, 0x05, 0x1B, 0x91, 0x26)  # (dir << 4) | low
    label('bvp_push')
    emit(0xAE, 0x96, 0x7F)                          # old Q_TAIL
    emit(0xE8)                                      # next_tail = (Q_TAIL + 1) & $FF
    emit(0xEC, 0x2F, 0x7F)                          # == Q_HEAD?
    rel(0xF0, 'bvp_done')
    emit(0x8E, 0x96, 0x7F)                          # Q_TAIL = next_tail
    emit(0xCA)                                      # X = old Q_TAIL
    emit(0xA5, 0x1C, 0x9D, 0x00, 0x6F)              # QX[X] = tx
    emit(0xA5, 0x1D, 0x9D, 0x00, 0x70)              # QY[X] = ty
    label('bvp_done')
    emit(0x60)

    # Helper: PushPpuTile(A=tile, $1C=tx 0..63, $1D=ty 0..23).
    label('PushPpuTile')
    emit(0x48)                          # PHA (tile)
    emit(0xAC, 0x02, 0x7F)              # LDY PPU_Q_COUNT
    emit(0xC0, 0x20)                    # CPY #32
    rel(0x90, 'pq_ok')
    emit(0x68, 0x60)                    # full -> drop
    label('pq_ok')
    emit(0x68, 0x99, 0x70, 0x7F)        # PLA; STA PPU_Q_TILE,Y
    emit(0xA5, 0x1D, 0x18, 0x69, 0x04)  # ppu_y = ty + 4
    emit(0x48)                          # PHA (ppu_y)
    emit(0x4A, 0x4A, 0x4A)              # ppu_y >> 3
    emit(0xA6, 0x1C, 0xE0, 0x20)        # CPX #32
    rel(0x90, 'pq_left_nt')
    emit(0x18, 0x69, 0x24)              # right NT ($24+)
    rel(0xD0, 'pq_hi_done')
    label('pq_left_nt')
    emit(0x18, 0x69, 0x20)              # left NT ($20+)
    label('pq_hi_done')
    emit(0x99, 0x30, 0x7F)              # STA PPU_Q_HI,Y
    emit(0x68, 0x29, 0x07, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A)  # (ppu_y & 7) << 5
    emit(0x85, 0x1A)                    # temp
    emit(0xA5, 0x1C, 0x29, 0x1F, 0x05, 0x1A)  # | (tx & 31)
    emit(0x99, 0x50, 0x7F)              # STA PPU_Q_LO,Y
    emit(0xEE, 0x02, 0x7F)              # INC PPU_Q_COUNT
    emit(0x60)

    # Helper: IsBarbaTile($1C=tx, $1D=ty) -> Carry clear (Barba is OAM sprite, never blocks BG tiles).
    label('IsBarbaTile')
    emit(0x18, 0x60)

    # Helpers for CROWD_BITS ($6800-$68BF): ClearCrowdOldRect, SetCrowdOldRect, SetCrowdNewRect, CheckCrowdBit
    label('CheckCrowdBit')
    emit(0xA5, 0x1C, 0x4A, 0x4A, 0x4A, 0x85, 0x1A)
    emit(0xA5, 0x1D, 0x0A, 0x0A, 0x0A, 0x05, 0x1A, 0xAA)
    emit(0xA5, 0x1C, 0x29, 0x07, 0xA8)
    emit(0xBD, 0x00, 0x68)
    abs16(0x39, 'BIT_MASK')
    emit(0x60)

    label('ClearCrowdOldRect')
    emit(0xA9, 0x00, 0x85, 0x1E)
    label('ccr_row')
    emit(0xAD, 0x0B, 0x7F, 0x18, 0x65, 0x1E, 0x85, 0x1D)
    emit(0xA9, 0x00, 0x85, 0x1F)
    label('ccr_col')
    emit(0xAD, 0x0A, 0x7F, 0x18, 0x65, 0x1F, 0x85, 0x1C)
    emit(0x4A, 0x4A, 0x4A, 0x85, 0x1A)
    emit(0xA5, 0x1D, 0x0A, 0x0A, 0x0A, 0x05, 0x1A, 0xAA)
    emit(0xA5, 0x1C, 0x29, 0x07, 0xA8)
    abs16(0xB9, 'BIT_MASK')
    emit(0x49, 0xFF, 0x3D, 0x00, 0x68, 0x9D, 0x00, 0x68)
    emit(0xE6, 0x1F, 0xA5, 0x1F, 0xCD, 0x08, 0x7F)
    rel(0xD0, 'ccr_col')
    emit(0xE6, 0x1E, 0xA5, 0x1E, 0xCD, 0x09, 0x7F)
    rel(0xD0, 'ccr_row')
    emit(0x60)

    label('SetCrowdOldRect')
    emit(0xAD, 0x0A, 0x7F, 0x8D, 0x0C, 0x7F)
    emit(0xAD, 0x0B, 0x7F, 0x8D, 0x0D, 0x7F)
    label('SetCrowdNewRect')
    emit(0xA9, 0x00, 0x85, 0x1E)
    label('scr_row')
    emit(0xAD, 0x0D, 0x7F, 0x18, 0x65, 0x1E, 0x85, 0x1D)
    emit(0xA9, 0x00, 0x85, 0x1F)
    label('scr_col')
    emit(0xAD, 0x0C, 0x7F, 0x18, 0x65, 0x1F, 0x85, 0x1C)
    emit(0x4A, 0x4A, 0x4A, 0x85, 0x1A)
    emit(0xA5, 0x1D, 0x0A, 0x0A, 0x0A, 0x05, 0x1A, 0xAA)
    emit(0xA5, 0x1C, 0x29, 0x07, 0xA8)
    emit(0xBD, 0x00, 0x68)
    abs16(0x19, 'BIT_MASK')
    emit(0x9D, 0x00, 0x68)
    emit(0xE6, 0x1F, 0xA5, 0x1F, 0xCD, 0x08, 0x7F)
    rel(0xD0, 'scr_col')
    emit(0xE6, 0x1E, 0xA5, 0x1E, 0xCD, 0x09, 0x7F)
    rel(0xD0, 'scr_row')
    emit(0x60)

    # Helper: EraseOldRect(CUR_X, CUR_Y, CUR_W, CUR_H) -> restores from BG_TILES & queues PPU_Q.
    label('EraseOldRect')
    emit(0xA9, 0x00, 0x85, 0x1E)
    label('er_row')
    emit(0xAD, 0x0B, 0x7F, 0x18, 0x65, 0x1E, 0x85, 0x1D)
    emit(0xA9, 0x00, 0x85, 0x1F)
    label('er_col')
    emit(0xAD, 0x0A, 0x7F, 0x18, 0x65, 0x1F, 0x85, 0x1C)
    abs16(0x20, 'IsBarbaTile')
    rel(0xB0, 'er_skip')
    emit(0xA5, 0x1D, 0x4A, 0x4A, 0xAA, 0x18, 0x69, 0x72, 0x85, 0x27)
    emit(0x8A, 0x18, 0x69, 0x78, 0x85, 0x2B)
    emit(0xA5, 0x1D, 0x29, 0x03, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x18, 0x65, 0x1C)
    emit(0x85, 0x26, 0x85, 0x2A)
    rel(0x90, 'er_ptr_ok')
    emit(0xE6, 0x27, 0xE6, 0x2B)
    label('er_ptr_ok')
    emit(0xA0, 0x00, 0xB1, 0x26, 0xD1, 0x2A)
    rel(0xF0, 'er_skip')
    emit(0x91, 0x2A)
    abs16(0x20, 'PushPpuTile')
    label('er_skip')
    emit(0xE6, 0x1F, 0xA5, 0x1F, 0xCD, 0x08, 0x7F)
    rel(0xD0, 'er_col')
    emit(0xE6, 0x1E, 0xA5, 0x1E, 0xCD, 0x09, 0x7F)
    rel(0xD0, 'er_row')
    emit(0x60)

    # CrowdStep: called from $ED0D (replaces LDA $12; ORA $13).
    label('CrowdStep')
    emit(0xAD, 0x00, 0x7F)              # CROWD_ACTIVE
    rel(0xD0, 'cs_active')
    abs16(0x4C, 'cs_ret')
    label('cs_active')
    abs16(0x20, 'BarbaStep')
    emit(0xAD, 0x01, 0x7F)              # PERSON_COUNT
    rel(0xD0, 'cs_has_people')
    abs16(0x4C, 'cs_ret')
    label('cs_has_people')
    emit(0xAD, 0x02, 0x7F)              # PPU_Q_COUNT (wait until 0)
    rel(0xF0, 'cs_q_free')
    abs16(0x4C, 'cs_ret')
    label('cs_q_free')
    emit(0xA9, 0x60, 0x8D, 0x05, 0x7F)  # STEP_BUDGET = 96
    emit(0xAE, 0x03, 0x7F)              # LDX PERSON_CUR
    label('cs_loop')
    emit(0xBD, 0x00, 0x60)              # LDA PERSON_X,X
    emit(0xC9, 0xFF)
    rel(0xD0, 'cs_alive')
    abs16(0x4C, 'cs_next')
    label('cs_alive')
    emit(0xDE, 0x00, 0x66)              # DEC PERSON_TIMER,X
    rel(0xF0, 'cs_timer_hit')
    abs16(0x4C, 'cs_next')
    label('cs_timer_hit')
    emit(0x8E, 0x0E, 0x7F)              # STX CUR_IDX
    emit(0x8D, 0x0A, 0x7F)              # STA CUR_X
    emit(0xBD, 0x00, 0x61, 0x8D, 0x0B, 0x7F)  # CUR_Y
    emit(0xBD, 0x00, 0x62, 0x48, 0x29, 0x0F, 0x8D, 0x08, 0x7F)  # CUR_W
    emit(0x68, 0x4A, 0x4A, 0x4A, 0x4A, 0x8D, 0x09, 0x7F)        # CUR_H
    # Check PPU_Q_COUNT + 2*w*h <= 32
    emit(0xAD, 0x08, 0x7F, 0xA8, 0xA9, 0x00)
    label('mul_wh')
    emit(0x18, 0x6D, 0x09, 0x7F, 0x88)
    rel(0xD0, 'mul_wh')
    emit(0x0A, 0x18, 0x6D, 0x02, 0x7F, 0xC9, 0x21)  # 2*w*h + PPU_Q_COUNT <= 32
    rel(0x90, 'cs_budget_ok')
    emit(0xAE, 0x0E, 0x7F, 0xA9, 0x01, 0x9D, 0x00, 0x66)
    emit(0x8E, 0x03, 0x7F)
    abs16(0x4C, 'cs_ret')
    label('cs_budget_ok')
    # Compute ABS_DX and ABS_DY from Barba ($718B, $718C)
    emit(0xAD, 0x0A, 0x7F, 0xCD, 0x8B, 0x71)
    rel(0x90, 'dx_neg')
    emit(0x38, 0xED, 0x8B, 0x71, 0x8D, 0x16, 0x7F)
    rel(0xB0, 'dx_done')
    label('dx_neg')
    emit(0xAD, 0x8B, 0x71, 0x38, 0xED, 0x0A, 0x7F, 0x8D, 0x16, 0x7F)
    label('dx_done')
    emit(0xAD, 0x0B, 0x7F, 0xCD, 0x8C, 0x71)
    rel(0x90, 'dy_neg')
    emit(0x38, 0xED, 0x8C, 0x71, 0x8D, 0x17, 0x7F)
    rel(0xB0, 'dy_done')
    label('dy_neg')
    emit(0xAD, 0x8C, 0x71, 0x38, 0xED, 0x0B, 0x7F, 0x8D, 0x17, 0x7F)
    label('dy_done')
    # Compute SCROLL_TX ($7F28) from $00 & $04 (horizontal scroll X!), VIS_END ($7F2C) = SCROLL_TX + 32
    emit(0xA5, 0x00, 0x4A, 0xA5, 0x04, 0x6A, 0x4A, 0x4A)
    emit(0x8D, 0x28, 0x7F, 0x18, 0x69, 0x20, 0x8D, 0x2C, 0x7F)

    # Compute CUR_WAS_VIS ($7F06): 1 iff CUR_X + CUR_W > SCROLL_TX and CUR_X < VIS_END
    emit(0xA9, 0x00, 0x8D, 0x06, 0x7F)
    emit(0xAD, 0x0A, 0x7F, 0x18, 0x6D, 0x08, 0x7F)  # CUR_X + CUR_W
    emit(0xCD, 0x28, 0x7F)                          # <= SCROLL_TX?
    rel(0x90, 'vis_done')
    rel(0xF0, 'vis_done')
    emit(0xAD, 0x0A, 0x7F, 0xCD, 0x2C, 0x7F)        # CUR_X >= VIS_END?
    rel(0xB0, 'vis_done')
    emit(0xA9, 0x01, 0x8D, 0x06, 0x7F)
    label('vis_done')

    # Reload timer = 3 + min(6, (ABS_DX + ABS_DY) >> 3) + (CUR_IDX & 1) + (8 if offscreen)
    emit(0xAD, 0x16, 0x7F, 0x18, 0x6D, 0x17, 0x7F, 0x4A, 0x4A, 0x4A)
    emit(0xC9, 0x06)
    rel(0x90, 'tmr_clamp_ok')
    emit(0xA9, 0x06)
    label('tmr_clamp_ok')
    emit(0x18, 0x69, 0x03)
    emit(0xAC, 0x06, 0x7F)                          # CUR_WAS_VIS == 0 -> +8 so visible crowd gets priority
    rel(0xD0, 'tmr_vis_ok')
    emit(0x18, 0x69, 0x08)
    label('tmr_vis_ok')
    emit(0x85, 0x1A, 0xAE, 0x0E, 0x7F, 0x8A, 0x29, 0x01, 0x18, 0x65, 0x1A)
    emit(0x9D, 0x00, 0x66)

    # Read w*h tiles from PRG CROWD_BANK into TMP_TILES ($7F18+)
    emit(0xAE, 0x0E, 0x7F)
    emit(0xBD, 0x00, 0x64, 0x85, 0x26)              # TLO
    emit(0xBD, 0x00, 0x65, 0x85, 0x27)              # THI
    emit(0xA9, 0x47, 0x8D, 0x00, 0x80, 0xAD, 0x04, 0x7F, 0x8D, 0x01, 0x80)
    emit(0xA0, 0x00)
    label('rd_tiles')
    emit(0xB1, 0x26, 0x99, 0x18, 0x7F, 0xC8, 0xC0, 0x10)
    rel(0xD0, 'rd_tiles')
    emit(0xA9, 0x47, 0x8D, 0x00, 0x80, 0xAD, 0x03, 0x02, 0x8D, 0x01, 0x80)

    # Initialize PERSON_DIR[CUR_IDX] once: bit7=1, bit6=side(0=L,1=R)
    emit(0xAE, 0x0E, 0x7F, 0xBD, 0x00, 0x67)
    rel(0x30, 'dir_inited')
    emit(0xA9, 0x80)
    emit(0xAD, 0x0A, 0x7F, 0xCD, 0x8B, 0x71)        # CUR_X >= Barba_X?
    rel(0x90, 'dir_init_save')
    emit(0x09, 0x40)                                # side = 1 (Right)
    label('dir_init_save')
    emit(0x9D, 0x00, 0x67)
    label('dir_inited')

    # If offscreen (CUR_WAS_VIS == 0), force side away from viewport so offscreen people never enter screen
    emit(0xAD, 0x06, 0x7F)
    rel(0xD0, 'side_ready')
    emit(0xAD, 0x0A, 0x7F, 0xCD, 0x2C, 0x7F)        # CUR_X >= VIS_END?
    rel(0xB0, 'force_side_r')
    emit(0xBD, 0x00, 0x67, 0x29, 0xBF, 0x9D, 0x00, 0x67)
    rel(0x30, 'side_ready')                         # BMI (bit 7 = 1)
    label('force_side_r')
    emit(0xBD, 0x00, 0x67, 0x09, 0x40, 0x9D, 0x00, 0x67)
    label('side_ready')

    # Increment PERSON_AGE[CUR_IDX] (cap at 255)
    emit(0xBD, 0x00, 0x6F, 0xC9, 0xFF)
    rel(0xF0, 'age_ok')
    emit(0xFE, 0x00, 0x6F)
    label('age_ok')

    # CUR_IGNORE_COLL = 1 if PERSON_STUCK >= 6 or PERSON_AGE >= 48
    emit(0xA9, 0x00, 0x8D, 0x07, 0x7F)
    emit(0xBD, 0x00, 0x70, 0xC9, 0x06)
    rel(0xB0, 'set_ignore_coll')
    emit(0xBD, 0x00, 0x6F, 0xC9, 0x30)
    rel(0x90, 'ignore_coll_done')
    label('set_ignore_coll')
    emit(0xA9, 0x01, 0x8D, 0x07, 0x7F)
    label('ignore_coll_done')

    # Load CUR_BAND_MIN ($7F9A) / CUR_BAND_MAX ($7F9B) from PERSON_BAND[CUR_IDX] (preserving X=CUR_IDX)
    emit(0xAE, 0x0E, 0x7F)
    emit(0xBD, 0x00, 0x63, 0xA8)
    emit(0xB9, 0x10, 0x7F, 0x8D, 0x9A, 0x7F)
    emit(0xB9, 0x13, 0x7F, 0x8D, 0x9B, 0x7F)

    # Compute IDEAL_DIR ($7F29)
    emit(0xAD, 0x07, 0x7F)                          # CUR_IGNORE_COLL?
    rel(0xF0, 'use_flow_dir')
    emit(0xBD, 0x00, 0x67, 0x29, 0x40)              # side == 0 -> West (6), side == 1 -> East (2)
    rel(0xD0, 'ghost_east')
    emit(0xA9, 0x06)
    rel(0xD0, 'save_ideal')
    label('ghost_east')
    emit(0xA9, 0x02)
    rel(0xD0, 'save_ideal')

    label('use_flow_dir')
    # Read FLOW_LR at feet (CUR_X, CUR_Y + CUR_H - 1)
    emit(0xAD, 0x0B, 0x7F, 0x18, 0x6D, 0x09, 0x7F, 0x38, 0xE9, 0x01)
    emit(0x85, 0x1D)
    emit(0x4A, 0x4A, 0x18, 0x69, 0x69, 0x85, 0x27)
    emit(0xA5, 0x1D, 0x29, 0x03, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A)
    emit(0x18, 0x6D, 0x0A, 0x7F, 0x85, 0x26)
    rel(0x90, 'fl_ptr_ok')
    emit(0xE6, 0x27)
    label('fl_ptr_ok')
    emit(0xA0, 0x00, 0xB1, 0x26, 0x85, 0x1A)        # $1A = FLOW_LR byte
    emit(0xBD, 0x00, 0x67, 0x29, 0x40)              # side == 0 or 1?
    rel(0xD0, 'flow_pick_r')
    # side == 0: try low nibble (< 8), fallback high nibble (< 8), fallback 6
    emit(0xA5, 0x1A, 0x29, 0x0F, 0xC9, 0x08)
    rel(0x90, 'save_ideal')
    emit(0xA5, 0x1A, 0x4A, 0x4A, 0x4A, 0x4A, 0xC9, 0x08)
    rel(0x90, 'save_ideal')
    emit(0xA9, 0x06)
    rel(0xD0, 'save_ideal')
    label('flow_pick_r')
    # side == 1: try high nibble (< 8), fallback low nibble (< 8), fallback 2
    emit(0xA5, 0x1A, 0x4A, 0x4A, 0x4A, 0x4A, 0xC9, 0x08)
    rel(0x90, 'save_ideal')
    emit(0xA5, 0x1A, 0x29, 0x0F, 0xC9, 0x08)
    rel(0x90, 'save_ideal')
    emit(0xA9, 0x02)
    label('save_ideal')
    emit(0x8D, 0x29, 0x7F)

    # Compute REV_DIR ($7F2D)
    emit(0xBD, 0x00, 0x67, 0x29, 0x20)              # has_prev?
    rel(0xD0, 'has_rev')
    emit(0xA9, 0xFF)
    rel(0xD0, 'save_rev')
    label('has_rev')
    emit(0xBD, 0x00, 0x67, 0x29, 0x07, 0x49, 0x04)
    label('save_rev')
    emit(0x8D, 0x2D, 0x7F)

    # Clear own rect from CROWD_BITS before checking candidate moves
    abs16(0x20, 'ClearCrowdOldRect')

    # Pass 1: try OFFSETS[0..7] avoiding REV_DIR
    emit(0xA9, 0x00, 0x8D, 0x2A, 0x7F)              # CAND_IDX = 0
    label('cand_loop')
    emit(0xAC, 0x2A, 0x7F)
    abs16(0xB9, 'DIR_OFFSETS')
    emit(0x18, 0x6D, 0x29, 0x7F, 0x29, 0x07)        # TRY_DIR = (IDEAL_DIR + offset) & 7
    emit(0xCD, 0x2D, 0x7F)                          # == REV_DIR?
    rel(0xF0, 'cand_next')
    emit(0x8D, 0x2B, 0x7F)
    abs16(0x20, 'TryMoveDir')
    rel(0x90, 'cs_do_move_idx')
    label('cand_next')
    emit(0xEE, 0x2A, 0x7F, 0xAD, 0x2A, 0x7F, 0xC9, 0x08)
    rel(0xD0, 'cand_loop')

    # Pass 2: if REV_DIR != $FF, allow immediate reverse as last resort
    emit(0xAD, 0x2D, 0x7F, 0xC9, 0xFF)
    rel(0xF0, 'all_blocked')
    emit(0x8D, 0x2B, 0x7F)
    emit(0xA9, 0x04, 0x8D, 0x2A, 0x7F)              # treat reverse as CAND_IDX >= 2
    abs16(0x20, 'TryMoveDir')
    rel(0x90, 'cs_do_move_idx')

    # All directions blocked: re-set CROWD_BITS, increment stuck (flip side at 12 if onscreen)
    label('all_blocked')
    abs16(0x20, 'SetCrowdOldRect')
    emit(0xAE, 0x0E, 0x7F)
    emit(0xBD, 0x00, 0x70, 0xC9, 0x0F)
    rel(0xF0, 'blk_chk_flip')
    emit(0xFE, 0x00, 0x70)
    label('blk_chk_flip')
    emit(0xBD, 0x00, 0x70, 0xC9, 0x0C)
    rel(0x90, 'blk_ret')
    emit(0xAD, 0x06, 0x7F)                          # CUR_WAS_VIS != 0?
    rel(0xF0, 'blk_ret')
    emit(0xA9, 0x06, 0x9D, 0x00, 0x70)              # stuck = 6
    emit(0xBD, 0x00, 0x67, 0x49, 0x40, 0x9D, 0x00, 0x67)  # flip side
    label('blk_ret')
    abs16(0x4C, 'cs_next')

    # Move succeeded! A = offscreen flag (0=onscreen, 1=offscreen)
    label('cs_do_move_idx')
    emit(0x09, 0x00)
    rel(0xF0, 'onscreen')

    label('go_offscreen')
    abs16(0x20, 'EraseOldRect')
    emit(0xAE, 0x0E, 0x7F, 0xA9, 0xFF, 0x9D, 0x00, 0x60)
    abs16(0x4C, 'cs_next')

    label('onscreen')
    # Erase old rect, set new CROWD_BITS, draw new rect (never overwriting BG_TILES != 0!)
    abs16(0x20, 'EraseOldRect')
    abs16(0x20, 'SetCrowdNewRect')
    emit(0xA9, 0x00, 0x8D, 0x0F, 0x7F)
    emit(0xA9, 0x00, 0x85, 0x1E)
    label('dr_row')
    emit(0xAD, 0x0D, 0x7F, 0x18, 0x65, 0x1E, 0x85, 0x1D)
    emit(0xA9, 0x00, 0x85, 0x1F)
    label('dr_col')
    emit(0xAD, 0x0C, 0x7F, 0x18, 0x65, 0x1F, 0x85, 0x1C)
    abs16(0x20, 'IsBarbaTile')
    rel(0xB0, 'dr_skip')
    emit(0xA5, 0x1D, 0x4A, 0x4A, 0xAA, 0x18, 0x69, 0x72, 0x85, 0x27)
    emit(0x8A, 0x18, 0x69, 0x78, 0x85, 0x2B)
    emit(0xA5, 0x1D, 0x29, 0x03, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x18, 0x65, 0x1C)
    emit(0x85, 0x26, 0x85, 0x2A)
    rel(0x90, 'dr_ptr_ok')
    emit(0xE6, 0x27, 0xE6, 0x2B)
    label('dr_ptr_ok')
    # Never overwrite any background scenery or static prop (BG_TILES != 0)
    emit(0xA0, 0x00, 0xB1, 0x26)
    rel(0xD0, 'dr_skip')
    emit(0xAC, 0x0F, 0x7F, 0xB9, 0x18, 0x7F)
    rel(0xF0, 'dr_skip')                            # skip empty $00 corner tiles!
    emit(0xA0, 0x00, 0xD1, 0x2A)
    rel(0xF0, 'dr_skip')
    emit(0x91, 0x2A)
    abs16(0x20, 'PushPpuTile')
    label('dr_skip')
    emit(0xEE, 0x0F, 0x7F)
    emit(0xE6, 0x1F, 0xA5, 0x1F, 0xCD, 0x08, 0x7F)
    rel(0xD0, 'dr_col')
    emit(0xE6, 0x1E, 0xA5, 0x1E, 0xCD, 0x09, 0x7F)
    rel(0xD0, 'dr_row')

    # Update PERSON_X/Y/DIR/STUCK[CUR_IDX]
    emit(0xAE, 0x0E, 0x7F)
    emit(0xAD, 0x0C, 0x7F, 0x9D, 0x00, 0x60)
    emit(0xAD, 0x0D, 0x7F, 0x9D, 0x00, 0x61)
    emit(0xBD, 0x00, 0x67, 0x29, 0xC0, 0x09, 0x20)  # keep bit7, bit6; set bit5 (has_prev)
    emit(0x0D, 0x2B, 0x7F, 0x9D, 0x00, 0x67)        # | TRY_DIR

    emit(0xAD, 0x07, 0x7F)                          # CUR_IGNORE_COLL == 0?
    rel(0xD0, 'upd_stuck_ghost')
    emit(0xAD, 0x2A, 0x7F)                          # CAND_IDX == 0?
    rel(0xD0, 'upd_chk_ci2')
    emit(0xBD, 0x00, 0x70)
    rel(0xF0, 'cs_next')
    emit(0xDE, 0x00, 0x70)
    rel(0x10, 'cs_next')
    label('upd_chk_ci2')
    emit(0xC9, 0x02)
    rel(0x90, 'cs_next')
    emit(0xBD, 0x00, 0x70, 0xC9, 0x0F)
    rel(0xF0, 'cs_next')
    emit(0xFE, 0x00, 0x70)
    rel(0xD0, 'cs_next')

    label('upd_stuck_ghost')
    emit(0xAD, 0x2A, 0x7F)
    rel(0xD0, 'upd_ghost_ci2')
    emit(0xA9, 0x06, 0x9D, 0x00, 0x70)              # latch stuck = 6
    rel(0xD0, 'cs_next')
    label('upd_ghost_ci2')
    emit(0xC9, 0x02)
    rel(0x90, 'cs_next')
    emit(0xBD, 0x00, 0x70, 0xC9, 0x0F)
    rel(0xF0, 'upd_ghost_flip')
    emit(0xFE, 0x00, 0x70)
    label('upd_ghost_flip')
    emit(0xBD, 0x00, 0x70, 0xC9, 0x0C)
    rel(0x90, 'cs_next')
    emit(0xAD, 0x06, 0x7F)                          # CUR_WAS_VIS != 0?
    rel(0xF0, 'cs_next')
    emit(0xA9, 0x06, 0x9D, 0x00, 0x70)
    emit(0xBD, 0x00, 0x67, 0x49, 0x40, 0x9D, 0x00, 0x67)  # flip side

    label('cs_next')
    emit(0xE8, 0xEC, 0x01, 0x7F)
    rel(0x90, 'cs_x_ok')
    emit(0xA2, 0x00)
    label('cs_x_ok')
    emit(0xCE, 0x05, 0x7F)
    rel(0xF0, 'cs_save_cur')
    abs16(0x4C, 'cs_loop')
    label('cs_save_cur')
    emit(0x8E, 0x03, 0x7F)
    label('cs_ret')
    emit(0xAD, 0x00, 0x7F)              # only run ShoutTick when CROWD_ACTIVE == 1
    rel(0xF0, 'cs_exit')
    abs16(0x20, 'ShoutTick')
    label('cs_exit')
    emit(0xA5, 0x12, 0x05, 0x13, 0x60)

    # Direction tables (0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW)
    label('DIR_DX')
    emit(0x00, 0x01, 0x01, 0x01, 0x00, 0xFF, 0xFF, 0xFF)
    label('DIR_DY')
    emit(0xFF, 0xFF, 0x00, 0x01, 0x01, 0x01, 0x00, 0xFF)
    label('BFS_DIRS')
    emit(0, 2, 4, 6, 1, 3, 5, 7)
    label('DIR_OFFSETS')
    emit(0, 1, 7, 2, 6, 3, 5, 4)

    label('BIT_MASK')
    emit(0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80)

    # Helper: CheckCollBit($1C=tx, $1D=ty) -> Z=0 if base scenery bit is set in COLL_BITS ($7E00-$7EBF).
    label('CheckCollBit')
    emit(0xA5, 0x1C, 0x4A, 0x4A, 0x4A, 0x85, 0x1A)  # tx >> 3
    emit(0xA5, 0x1D, 0x0A, 0x0A, 0x0A, 0x05, 0x1A)  # (ty << 3) | (tx >> 3)
    emit(0xAA)
    emit(0xA5, 0x1C, 0x29, 0x07, 0xA8)              # Y = tx & 7
    emit(0xBD, 0x00, 0x7E)                          # LDA COLL_BITS,X
    abs16(0x39, 'BIT_MASK')                         # AND BIT_MASK,Y
    emit(0x60)

    # Helper: TryMoveDir(TRY_DIR) -> checks per-band Y bounds [CUR_BAND_MIN, CUR_BAND_MAX),
    # Barba, CROWD_BITS, and full w x h COLL_BITS.
    # Returns C=1 if blocked; C=0 if ok (A=1 offscreen, A=0 onscreen), with CUR_NX/CUR_NY set.
    label('TryMoveDir')
    emit(0xAC, 0x2B, 0x7F)                          # LDY TRY_DIR
    emit(0xAD, 0x0B, 0x7F, 0x18)                    # LDA CUR_Y; CLC
    abs16(0x79, 'DIR_DY')                           # ADC DIR_DY,Y
    emit(0x8D, 0x0D, 0x7F)                          # STA CUR_NY
    rel(0x30, 'tm_reject_near')
    emit(0xCD, 0x9A, 0x7F)                          # >= CUR_BAND_MIN?
    rel(0x90, 'tm_reject_near')
    emit(0x18, 0x6D, 0x09, 0x7F)                    # CUR_NY + CUR_H
    emit(0x85, 0x1A)
    emit(0xAD, 0x9B, 0x7F)                          # CUR_BAND_MAX
    emit(0xC5, 0x1A)                                # >= CUR_NY + CUR_H?
    rel(0xB0, 'tm_y_ok')
    label('tm_reject_near')
    emit(0x38, 0x60)                                # SEC; RTS

    label('tm_y_ok')
    emit(0xAC, 0x2B, 0x7F)                          # LDY TRY_DIR
    emit(0xAD, 0x0A, 0x7F, 0x18)                    # LDA CUR_X; CLC
    abs16(0x79, 'DIR_DX')                           # ADC DIR_DX,Y
    emit(0x8D, 0x0C, 0x7F)                          # STA CUR_NX
    rel(0x30, 'tm_offscreen')
    emit(0x18, 0x6D, 0x08, 0x7F, 0xC9, 0x41)
    rel(0x90, 'tm_chk_vis_enter')
    label('tm_offscreen')
    emit(0xA9, 0x01, 0x18, 0x60)                    # LDA #1; CLC; RTS

    # If CUR_WAS_VIS == 0, forbid stepping into visible viewport [SCROLL_TX, VIS_END)
    label('tm_chk_vis_enter')
    emit(0xAD, 0x06, 0x7F)
    rel(0xD0, 'tm_onscreen')
    emit(0xAD, 0x0C, 0x7F, 0x18, 0x6D, 0x08, 0x7F)  # CUR_NX + CUR_W
    emit(0xCD, 0x28, 0x7F)                          # <= SCROLL_TX?
    rel(0x90, 'tm_onscreen')
    rel(0xF0, 'tm_onscreen')
    emit(0xAD, 0x0C, 0x7F, 0xCD, 0x2C, 0x7F)        # >= VIS_END?
    rel(0xB0, 'tm_onscreen')
    emit(0x38, 0x60)                                # SEC; RTS (blocked!)

    label('tm_onscreen')
    emit(0xA9, 0x00, 0x85, 0x1E)                    # dy = 0..CUR_H-1
    label('tm_row')
    emit(0xAD, 0x0D, 0x7F, 0x18, 0x65, 0x1E, 0x85, 0x1D)
    emit(0xA9, 0x00, 0x85, 0x1F)                    # dx = 0..CUR_W-1
    label('tm_col')
    emit(0xAD, 0x0C, 0x7F, 0x18, 0x65, 0x1F, 0x85, 0x1C)
    abs16(0x20, 'IsBarbaTile')
    rel(0xB0, 'tm_reject')
    abs16(0x20, 'CheckCrowdBit')
    rel(0xD0, 'tm_reject')
    # Check full w x h COLL_BITS unless CUR_IGNORE_COLL != 0
    emit(0xAD, 0x07, 0x7F)
    rel(0xD0, 'tm_skip')
    abs16(0x20, 'CheckCollBit')
    rel(0xD0, 'tm_reject')
    label('tm_skip')
    emit(0xE6, 0x1F, 0xA5, 0x1F, 0xCD, 0x08, 0x7F)
    rel(0xD0, 'tm_col')
    emit(0xE6, 0x1E, 0xA5, 0x1E, 0xCD, 0x09, 0x7F)
    rel(0xD0, 'tm_row')

    # If CUR_WAS_VIS != 0, despawn if CUR_NX is now completely outside [SCROLL_TX, VIS_END)
    emit(0xAD, 0x06, 0x7F)
    rel(0xF0, 'tm_stay_onscreen')
    emit(0xAD, 0x0C, 0x7F, 0x18, 0x6D, 0x08, 0x7F)  # CUR_NX + CUR_W
    emit(0xCD, 0x28, 0x7F)
    rel(0x90, 'tm_offscreen_end')
    rel(0xF0, 'tm_offscreen_end')
    emit(0xAD, 0x0C, 0x7F, 0xCD, 0x2C, 0x7F)
    rel(0xB0, 'tm_offscreen_end')
    label('tm_stay_onscreen')
    emit(0xA9, 0x00, 0x18, 0x60)                    # LDA #0; CLC; RTS
    label('tm_offscreen_end')
    emit(0xA9, 0x01, 0x18, 0x60)                    # LDA #1; CLC; RTS
    label('tm_reject')
    emit(0x38, 0x60)                                # SEC; RTS

    # HideShout: sets OAM slots 16..23 ($0740..$075F) Y = #$FE
    label('HideShout')
    emit(0xA9, 0xFE, 0xA2, 0x00)
    label('hs_loop')
    emit(0x9D, 0x40, 0x07, 0xE8, 0xE8, 0xE8, 0xE8, 0xE0, 0x20)
    rel(0xD0, 'hs_loop')
    emit(0x60)

    # ShoutTick: one person yells at a time above their head as they flee.
    # Uses $7F90=SHOUT_ACTIVE, $7F91=SHOUT_TIMER, $7F92=SHOUT_PERSON, $7F93=SHOUT_STR_IDX, $7F94=SHOUT_SCAN
    label('ShoutTick')
    # Compute scroll_tile_x = ($04 >> 3) | (($00 & 1) << 5) -> store in $1A
    emit(0xA5, 0x04, 0x4A, 0x4A, 0x4A, 0x85, 0x1A)
    emit(0xA5, 0x00, 0x29, 0x01, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x05, 0x1A, 0x85, 0x1A)
    emit(0xAD, 0x90, 0x7F)              # SHOUT_ACTIVE
    rel(0xF0, 'st_not_active')
    abs16(0x4C, 'st_active')
    label('st_not_active')
    emit(0xCE, 0x91, 0x7F)              # DEC SHOUT_TIMER
    rel(0xF0, 'st_pick')
    emit(0x60)
    label('st_pick')
    emit(0xAD, 0x01, 0x7F)              # PERSON_COUNT
    rel(0xF0, 'st_no_pick')
    emit(0x85, 0x1B)                    # budget = PERSON_COUNT
    emit(0xA9, 0xFF, 0x85, 0x1E)        # $1E = best_dist ($FF = none)
    emit(0xAE, 0x94, 0x7F)              # LDX SHOUT_SCAN
    label('st_find')
    emit(0xBD, 0x00, 0x60)              # PERSON_X,X
    emit(0xC9, 0xFF)
    rel(0xF0, 'st_find_next')
    emit(0x38, 0xE5, 0x1A)              # px - scroll_tile_x
    emit(0xC9, 0x17)                    # 0 <= rel <= 22 (onscreen with room for 7-char shout)
    rel(0xB0, 'st_find_next')
    # Compute Manhattan distance to Barba ($718B, $718C) -> $1C
    emit(0xBD, 0x00, 0x60, 0xCD, 0x8B, 0x71)
    rel(0x90, 'st_dx_neg')
    emit(0x38, 0xED, 0x8B, 0x71)
    rel(0xB0, 'st_dx_ok')
    label('st_dx_neg')
    emit(0xAD, 0x8B, 0x71, 0x38, 0xFD, 0x00, 0x60)  # SBC PERSON_X,X
    label('st_dx_ok')
    emit(0x85, 0x1C)
    emit(0xBD, 0x00, 0x61, 0xCD, 0x8C, 0x71)
    rel(0x90, 'st_dy_neg')
    emit(0x38, 0xED, 0x8C, 0x71)
    rel(0xB0, 'st_dy_ok')
    label('st_dy_neg')
    emit(0xAD, 0x8C, 0x71, 0x38, 0xFD, 0x00, 0x61)  # SBC PERSON_Y,X
    label('st_dy_ok')
    emit(0x18, 0x65, 0x1C)              # A = |dx| + |dy|
    emit(0xC5, 0x1E)                    # CMP best_dist
    rel(0xB0, 'st_find_next')           # >= best_dist -> skip
    emit(0x85, 0x1E)                    # best_dist = A
    emit(0x8E, 0x1F, 0x00)              # $001F = best_idx (ZP $1F)
    label('st_find_next')
    emit(0xE8, 0xEC, 0x01, 0x7F)
    rel(0x90, 'st_fn_ok')
    emit(0xA2, 0x00)
    label('st_fn_ok')
    emit(0xC6, 0x1B)
    rel(0xD0, 'st_find')
    emit(0xA5, 0x1E, 0xC9, 0xFF)        # found anyone onscreen?
    rel(0xF0, 'st_no_pick')
    emit(0xA6, 0x1F, 0x8E, 0x92, 0x7F)  # SHOUT_PERSON = best_idx
    emit(0xE8, 0xEC, 0x01, 0x7F)
    rel(0x90, 'st_sc_ok')
    emit(0xA2, 0x00)
    label('st_sc_ok')
    emit(0x8E, 0x94, 0x7F)              # advance SHOUT_SCAN
    emit(0xA9, 0x01, 0x8D, 0x90, 0x7F)  # SHOUT_ACTIVE = 1
    emit(0xA9, 0x2D, 0x8D, 0x91, 0x7F)  # SHOUT_TIMER = 45 (~0.75s)
    rel(0xD0, 'st_draw')
    label('st_no_pick')
    emit(0xA9, 0x0A, 0x8D, 0x91, 0x7F)
    emit(0x60)

    label('st_active')
    emit(0xCE, 0x91, 0x7F)              # DEC SHOUT_TIMER
    rel(0xD0, 'st_draw')
    label('st_end_shout')
    emit(0xA9, 0x00, 0x8D, 0x90, 0x7F)  # SHOUT_ACTIVE = 0
    emit(0xA9, 0x0A, 0x8D, 0x91, 0x7F)  # pause 10 frames
    emit(0xEE, 0x93, 0x7F, 0xAD, 0x93, 0x7F, 0xC9, len(SHOUT_MESSAGES))
    rel(0x90, 'st_idx_ok')
    emit(0xA9, 0x00, 0x8D, 0x93, 0x7F)
    label('st_idx_ok')
    abs16(0x4C, 'HideShout')

    label('st_draw')
    emit(0xAE, 0x92, 0x7F)              # LDX SHOUT_PERSON
    emit(0xBD, 0x00, 0x60)              # PERSON_X,X
    emit(0xC9, 0xFF)
    rel(0xF0, 'st_end_shout')
    emit(0x38, 0xE5, 0x1A)              # rel_tile_x
    emit(0xC9, 0x1A)                    # > 25 -> offscreen
    rel(0xB0, 'st_end_shout')
    emit(0x0A, 0x0A, 0x0A, 0x85, 0x1C)  # $1C = screen_x = rel_tile_x * 8
    emit(0xBD, 0x00, 0x61)              # PERSON_Y,X
    emit(0x0A, 0x0A, 0x0A, 0x18, 0x69, 0x16)  # py*8 + 22 (above head)
    emit(0xC9, 0x20)                    # clamp >= 32 (below HUD timer)
    rel(0xB0, 'st_y_ok')
    emit(0xA9, 0x20)
    label('st_y_ok')
    emit(0x85, 0x1D)                    # $1D = screen_y
    # Load string pointer from ShoutPtrs[SHOUT_STR_IDX] into $26/$27
    emit(0xAE, 0x93, 0x7F)
    abs16(0xBD, 'ShoutPtrsLo')
    emit(0x85, 0x26)
    abs16(0xBD, 'ShoutPtrsHi')
    emit(0x85, 0x27)
    emit(0xA0, 0x00, 0xB1, 0x26, 0x85, 0x1E)  # $1E = len
    emit(0xA2, 0x00)                    # OAM offset = 0 ($0740,X)
    emit(0xA0, 0x01)                    # string byte index = 1..len
    label('st_spr_loop')
    emit(0xA5, 0x1D, 0x9D, 0x40, 0x07)  # Y
    emit(0xB1, 0x26, 0x9D, 0x41, 0x07)  # Tile ($40 + idx)
    emit(0xA9, 0x03, 0x9D, 0x42, 0x07)  # Attr (Pal 3)
    emit(0xA5, 0x1C, 0x9D, 0x43, 0x07)  # X
    emit(0x18, 0x69, 0x08, 0x85, 0x1C)  # screen_x += 8
    emit(0xE8, 0xE8, 0xE8, 0xE8)
    emit(0xC8, 0xC6, 0x1E)
    rel(0xD0, 'st_spr_loop')
    # Hide remaining OAM slots up to $20 (8 slots)
    emit(0xA9, 0xFE)
    label('st_hide_rem')
    emit(0xE0, 0x20)
    rel(0xB0, 'st_done')
    emit(0x9D, 0x40, 0x07, 0xE8, 0xE8, 0xE8, 0xE8)
    rel(0xD0, 'st_hide_rem')
    label('st_done')
    emit(0x60)

    # Shout string tables
    msg_addrs = []
    for msg in SHOUT_MESSAGES:
        msg_addrs.append(base + len(buf))
        emit(len(msg))
        for ch in msg:
            emit(0x40 + SHOUT_CHARSET.index(ch))
    label('ShoutPtrsLo')
    for a in msg_addrs:
        emit(a & 0xFF)
    label('ShoutPtrsHi')
    for a in msg_addrs:
        emit((a >> 8) & 0xFF)

    # =========================================================================
    # Autonomous 2x Barba Roaming, Z2-style Fireballs, and Crowd Burn-to-Ash
    # =========================================================================
    # WRAM $7FA0-$7FD3:
    #   $7FA0: BARBA_STATE (0=roam, 1=pause+shoot)
    #   $7FA1: BARBA_TIMER
    #   $7FA2/$7FA3: BARBA_X_LO/HI (0..456)
    #   $7FA4: BARBA_Y (12..144)
    #   $7FA5/$7FA6: BARBA_TGT_X_LO/HI
    #   $7FA7: BARBA_TGT_Y
    #   $7FA8: BARBA_FACING (0=left, 1=right)
    #   $7FA9: BARBA_VISITED (8-bit sector mask)
    #   $7FAA: BARBA_RNG
    #   $7FAB: BARBA_ANIM
    #   $7FAC: BARBA_ROAR_TIMER
    #   $7FB0-$7FB5: FB_STATE[0..5] (0=off, 1=fly, 2..13=fizzle)
    #   $7FB6-$7FBB: FB_X_LO[0..5]
    #   $7FBC-$7FC1: FB_X_HI[0..5]
    #   $7FC2-$7FC7: FB_Y[0..5]
    #   $7FC8-$7FCD: FB_VX[0..5]
    #   $7FCE-$7FD3: FB_VY[0..5]

    label('StepRng')
    emit(0xAD, 0xAA, 0x7F)              # LDA BARBA_RNG
    emit(0x0A)                          # ASL A
    rel(0x90, 'rng_no_eor')
    emit(0x49, 0x1D)                    # EOR #$1D
    label('rng_no_eor')
    emit(0x8D, 0xAA, 0x7F)              # STA BARBA_RNG
    emit(0x60)

    label('BarbaInit')
    emit(0xA5, 0x12, 0x4D, 0x8B, 0x71, 0x4D, 0x04, 0x7F)  # $12 ^ $718B ^ CROWD_BANK
    rel(0xD0, 'bi_rng_ok')
    emit(0xA9, 0xA5)
    label('bi_rng_ok')
    emit(0x8D, 0xAA, 0x7F)              # BARBA_RNG
    # BARBA_X = $718B * 8, clamped to [16..456]
    emit(0xAD, 0x8B, 0x71, 0x0A, 0x0A, 0x0A, 0x8D, 0xA2, 0x7F)
    emit(0xAD, 0x8B, 0x71, 0x4A, 0x4A, 0x4A, 0x4A, 0x4A, 0x8D, 0xA3, 0x7F)
    rel(0xD0, 'bi_chk_xmax')
    emit(0xAD, 0xA2, 0x7F, 0xC9, 0x10)
    rel(0xB0, 'bi_x_ok')
    emit(0xA9, 0x10, 0x8D, 0xA2, 0x7F)
    rel(0xD0, 'bi_x_ok')
    label('bi_chk_xmax')
    emit(0xAD, 0xA2, 0x7F, 0xC9, 0xC8)
    rel(0x90, 'bi_x_ok')
    emit(0xA9, 0xC8, 0x8D, 0xA2, 0x7F)
    label('bi_x_ok')
    # BARBA_Y = $718C * 8, clamped to [12..144]
    emit(0xAD, 0x8C, 0x71, 0x0A, 0x0A, 0x0A)
    emit(0xC9, 0x0C)
    rel(0xB0, 'bi_chk_ymax')
    emit(0xA9, 0x0C)
    label('bi_chk_ymax')
    emit(0xC9, 0x90)
    rel(0x90, 'bi_y_ok')
    emit(0xA9, 0x90)
    label('bi_y_ok')
    emit(0x8D, 0xA4, 0x7F)
    emit(0xA9, 0x04, 0x8D, 0x8D, 0x71, 0x8D, 0x8E, 0x71)  # BARBA_W = 4, BARBA_H = 4
    emit(0xA9, 0x00)
    emit(0x8D, 0xA0, 0x7F, 0x8D, 0xA1, 0x7F, 0x8D, 0xA8, 0x7F)
    emit(0x8D, 0xA9, 0x7F, 0x8D, 0xAB, 0x7F, 0x8D, 0xAC, 0x7F)
    emit(0xA2, 0x05)
    label('bi_clr_fb')
    emit(0x9D, 0xB0, 0x7F, 0xCA)
    rel(0x10, 'bi_clr_fb')
    abs16(0x4C, 'PickBarbaTarget')

    label('SecXLo')
    emit(16, 128, 240, 96)              # 16, 128, 240, 352&255
    label('SecXHi')
    emit(0, 0, 0, 1)
    label('SecYMin')
    emit(12, 84)

    label('PickBarbaTarget')
    abs16(0x20, 'StepRng')
    emit(0xAD, 0xA9, 0x7F, 0xC9, 0xFF)
    rel(0xD0, 'pbt_not_full')
    emit(0xA9, 0x00, 0x8D, 0xA9, 0x7F)
    label('pbt_not_full')
    emit(0xAD, 0xAA, 0x7F, 0x29, 0x07, 0xAA)  # X = rng & 7
    emit(0xA9, 0x08, 0x85, 0x1A)
    label('pbt_find')
    emit(0xAD, 0xA9, 0x7F)
    abs16(0x3D, 'BIT_MASK')             # AND BIT_MASK,X
    rel(0xF0, 'pbt_found')
    emit(0xE8, 0x8A, 0x29, 0x07, 0xAA)
    emit(0xC6, 0x1A)
    rel(0xD0, 'pbt_find')
    label('pbt_found')
    emit(0xAD, 0xA9, 0x7F)
    abs16(0x1D, 'BIT_MASK')             # ORA BIT_MASK,X
    emit(0x8D, 0xA9, 0x7F)
    emit(0x8A, 0x48)                    # save sector X
    emit(0x29, 0x03)                    # col = sector & 3
    emit(0xAE, 0x00, 0x06)              # LDX $0600 (0 = Easy, 1-screen)
    rel(0xD0, 'pbt_col_ok')
    emit(0x29, 0x01)                    # 1-screen: clamp col to 0..1
    label('pbt_col_ok')
    emit(0xA8)
    abs16(0xB9, 'SecXLo')
    emit(0x8D, 0xA5, 0x7F)
    abs16(0xB9, 'SecXHi')
    emit(0x8D, 0xA6, 0x7F)
    abs16(0x20, 'StepRng')
    emit(0x29, 0x3F, 0x18, 0x6D, 0xA5, 0x7F, 0x8D, 0xA5, 0x7F)
    rel(0x90, 'pbt_x1_ok')
    emit(0xEE, 0xA6, 0x7F)
    label('pbt_x1_ok')
    abs16(0x20, 'StepRng')
    emit(0x29, 0x1F, 0x18, 0x6D, 0xA5, 0x7F, 0x8D, 0xA5, 0x7F)
    rel(0x90, 'pbt_x2_ok')
    emit(0xEE, 0xA6, 0x7F)
    label('pbt_x2_ok')
    emit(0x68, 0x4A, 0x4A, 0xA8)        # row = sector >> 2
    abs16(0xB9, 'SecYMin')
    emit(0x8D, 0xA7, 0x7F)
    abs16(0x20, 'StepRng')
    emit(0x29, 0x3F, 0x18, 0x6D, 0xA7, 0x7F, 0x8D, 0xA7, 0x7F)
    emit(0x60)

    # Fireball burst velocities (3 shots): facing=0 (left) or 1 (right)
    label('FbVxTbl')
    emit(0xFE, 0xFE, 0xFD, 0x02, 0x02, 0x03)  # -2,-2,-3 (left), +2,+2,+3 (right)
    label('FbVyTbl')
    emit(0x01, 0x02, 0x01)                    # +1, +2, +1

    label('SpawnFireball')
    # A = shot index (0..2)
    emit(0xA8)                          # Y = shot idx
    emit(0xA2, 0x00)
    label('sf_find')
    emit(0xBD, 0xB0, 0x7F)              # FB_STATE,X
    rel(0xF0, 'sf_free')
    emit(0xE8, 0xE0, 0x06)
    rel(0xD0, 'sf_find')
    emit(0x60)                          # all 6 full
    label('sf_free')
    emit(0xA9, 0x01, 0x9D, 0xB0, 0x7F)  # FB_STATE = 1
    emit(0xAD, 0xA4, 0x7F, 0x18, 0x69, 0x06, 0x9D, 0xC2, 0x7F)  # FB_Y = BARBA_Y + 6
    emit(0xAD, 0xA2, 0x7F, 0x9D, 0xB6, 0x7F)
    emit(0xAD, 0xA3, 0x7F, 0x9D, 0xBC, 0x7F)
    emit(0xAD, 0xA8, 0x7F)              # BARBA_FACING
    rel(0xF0, 'sf_left')
    # facing right: mouth at BARBA_X + 24
    emit(0xBD, 0xB6, 0x7F, 0x18, 0x69, 0x18, 0x9D, 0xB6, 0x7F)
    rel(0x90, 'sf_rx_ok')
    emit(0xFE, 0xBC, 0x7F)
    label('sf_rx_ok')
    emit(0x98, 0x18, 0x69, 0x03, 0xA8)  # Y += 3 for right vx
    rel(0xD0, 'sf_set_v')
    label('sf_left')
    label('sf_set_v')
    emit(0x98, 0x48)
    abs16(0xB9, 'FbVxTbl')
    emit(0x9D, 0xC8, 0x7F)
    emit(0x68)
    emit(0xC9, 0x03)
    rel(0x90, 'sf_vy_ok')
    emit(0x38, 0xE9, 0x03)
    label('sf_vy_ok')
    emit(0xA8)
    abs16(0xB9, 'FbVyTbl')
    emit(0x9D, 0xCE, 0x7F)
    emit(0x60)

    label('BarbaStep')
    emit(0xEE, 0xAB, 0x7F)              # INC BARBA_ANIM
    emit(0xAD, 0xAC, 0x7F)              # BARBA_ROAR_TIMER
    rel(0xF0, 'bs_no_roar_dec')
    emit(0xCE, 0xAC, 0x7F)
    label('bs_no_roar_dec')
    emit(0xAD, 0xA0, 0x7F)              # BARBA_STATE
    rel(0xF0, 'bs_roam')
    abs16(0x4C, 'bs_shoot')

    label('bs_roam')
    # Move X toward TGT_X (1 px/frame)
    emit(0xAD, 0xA3, 0x7F, 0xCD, 0xA6, 0x7F)
    rel(0x90, 'bs_x_inc')
    rel(0xD0, 'bs_x_dec')
    emit(0xAD, 0xA2, 0x7F, 0xCD, 0xA5, 0x7F)
    rel(0x90, 'bs_x_inc')
    rel(0xF0, 'bs_y_move')
    label('bs_x_dec')
    emit(0xA9, 0x00, 0x8D, 0xA8, 0x7F)  # facing left
    emit(0xAD, 0xA2, 0x7F)
    rel(0xD0, 'bs_xd_lo')
    emit(0xCE, 0xA3, 0x7F)
    label('bs_xd_lo')
    emit(0xCE, 0xA2, 0x7F)
    rel(0x10, 'bs_y_move')
    rel(0x30, 'bs_y_move')
    label('bs_x_inc')
    emit(0xA9, 0x01, 0x8D, 0xA8, 0x7F)  # facing right
    emit(0xEE, 0xA2, 0x7F)
    rel(0xD0, 'bs_y_move')
    emit(0xEE, 0xA3, 0x7F)

    label('bs_y_move')
    emit(0xAD, 0xA4, 0x7F, 0xCD, 0xA7, 0x7F)
    rel(0xF0, 'bs_chk_arrive')
    rel(0x90, 'bs_y_inc')
    emit(0xCE, 0xA4, 0x7F)
    rel(0x10, 'bs_chk_arrive')
    rel(0x30, 'bs_chk_arrive')
    label('bs_y_inc')
    emit(0xEE, 0xA4, 0x7F)

    label('bs_chk_arrive')
    emit(0xAD, 0xA3, 0x7F, 0xCD, 0xA6, 0x7F)
    rel(0xD0, 'bs_after_move')
    emit(0xAD, 0xA2, 0x7F, 0x38, 0xED, 0xA5, 0x7F)
    rel(0xB0, 'bs_adx_ok')
    emit(0x49, 0xFF, 0x18, 0x69, 0x01)
    label('bs_adx_ok')
    emit(0xC9, 0x03)
    rel(0xB0, 'bs_after_move')
    emit(0xAD, 0xA4, 0x7F, 0x38, 0xED, 0xA7, 0x7F)
    rel(0xB0, 'bs_ady_ok')
    emit(0x49, 0xFF, 0x18, 0x69, 0x01)
    label('bs_ady_ok')
    emit(0xC9, 0x03)
    rel(0xB0, 'bs_after_move')
    emit(0xA9, 0x01, 0x8D, 0xA0, 0x7F)  # BARBA_STATE = 1
    emit(0xA9, 0x30, 0x8D, 0xA1, 0x7F)  # BARBA_TIMER = 48
    rel(0xD0, 'bs_after_move')

    label('bs_shoot')
    emit(0xCE, 0xA1, 0x7F)              # DEC BARBA_TIMER
    emit(0xAD, 0xA1, 0x7F)
    emit(0xC9, 0x28)                    # 40 -> open mouth
    rel(0xD0, 'bs_s1')
    emit(0xA9, 0x20, 0x8D, 0xAC, 0x7F)  # ROAR_TIMER = 32
    label('bs_s1')
    emit(0xC9, 0x24)                    # 36 -> shot 0
    rel(0xD0, 'bs_s2')
    emit(0xA9, 0x00)
    abs16(0x20, 'SpawnFireball')
    rel(0x10, 'bs_after_move')
    rel(0x30, 'bs_after_move')
    label('bs_s2')
    emit(0xC9, 0x1A)                    # 26 -> shot 1
    rel(0xD0, 'bs_s3')
    emit(0xA9, 0x01)
    abs16(0x20, 'SpawnFireball')
    rel(0x10, 'bs_after_move')
    rel(0x30, 'bs_after_move')
    label('bs_s3')
    emit(0xC9, 0x10)                    # 16 -> shot 2
    rel(0xD0, 'bs_s_end')
    emit(0xA9, 0x02)
    abs16(0x20, 'SpawnFireball')
    rel(0x10, 'bs_after_move')
    rel(0x30, 'bs_after_move')
    label('bs_s_end')
    emit(0xAD, 0xA1, 0x7F)
    rel(0xD0, 'bs_after_move')
    emit(0x8D, 0xA0, 0x7F)              # BARBA_STATE = 0
    abs16(0x20, 'PickBarbaTarget')

    label('bs_after_move')
    # Update $718B (tile X) and $718C (tile Y) for click hit-test & crowd flee
    emit(0xAD, 0xA2, 0x7F, 0x4A, 0x4A, 0x4A, 0x85, 0x1A)
    emit(0xAD, 0xA3, 0x7F, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x05, 0x1A)
    emit(0xC9, 0x3D)
    rel(0x90, 'bs_tx_ok')
    emit(0xA9, 0x3C)
    label('bs_tx_ok')
    emit(0x8D, 0x8B, 0x71)
    emit(0xAD, 0xA4, 0x7F, 0x4A, 0x4A, 0x4A)
    emit(0xC9, 0x15)
    rel(0x90, 'bs_ty_ok')
    emit(0xA9, 0x14)
    label('bs_ty_ok')
    emit(0x8D, 0x8C, 0x71)

    # Update 6 Fireballs
    emit(0xA2, 0x00)
    label('fb_loop')
    emit(0xBD, 0xB0, 0x7F)              # FB_STATE,X
    rel(0xD0, 'fb_active')
    abs16(0x4C, 'fb_next')
    label('fb_active')
    emit(0xC9, 0x01)
    rel(0xF0, 'fb_fly')
    # Fizzling (2..13)
    emit(0xFE, 0xB0, 0x7F)
    emit(0xBD, 0xB0, 0x7F, 0xC9, 0x0E)
    rel(0x90, 'fb_next_j')
    emit(0xA9, 0x00, 0x9D, 0xB0, 0x7F)
    label('fb_next_j')
    abs16(0x4C, 'fb_next')

    label('fb_fly')
    # X += signed FB_VX,X
    emit(0xBD, 0xC8, 0x7F)
    rel(0x30, 'fb_vx_neg')
    emit(0x18, 0x7D, 0xB6, 0x7F, 0x9D, 0xB6, 0x7F)
    rel(0x90, 'fb_vy_step')
    emit(0xFE, 0xBC, 0x7F)
    rel(0x10, 'fb_vy_step')
    rel(0x30, 'fb_vy_step')
    label('fb_vx_neg')
    emit(0x18, 0x7D, 0xB6, 0x7F, 0x9D, 0xB6, 0x7F)
    rel(0xB0, 'fb_vy_step')
    emit(0xDE, 0xBC, 0x7F)
    label('fb_vy_step')
    emit(0xBD, 0xC2, 0x7F, 0x18, 0x7D, 0xCE, 0x7F, 0x9D, 0xC2, 0x7F)
    # Bounds check: X >= 504 ($01F8) or Y >= 188
    emit(0xBD, 0xBC, 0x7F)
    rel(0x30, 'fb_kill')
    emit(0xC9, 0x02)
    rel(0xB0, 'fb_kill')
    emit(0xC9, 0x01)
    rel(0xD0, 'fb_y_chk')
    emit(0xBD, 0xB6, 0x7F, 0xC9, 0xF8)
    rel(0xB0, 'fb_kill')
    label('fb_y_chk')
    emit(0xBD, 0xC2, 0x7F, 0xC9, 0xBC)
    rel(0x90, 'fb_tile_chk')
    label('fb_kill')
    emit(0xA9, 0x00, 0x9D, 0xB0, 0x7F)
    abs16(0x4C, 'fb_next')

    label('fb_tile_chk')
    # tx = (FB_X + 4) >> 3 -> $1C, ty = (FB_Y + 4) >> 3 -> $1D
    emit(0xBD, 0xB6, 0x7F, 0x18, 0x69, 0x04, 0x85, 0x1A)
    emit(0xBD, 0xBC, 0x7F, 0x69, 0x00, 0x85, 0x1B)
    emit(0xA5, 0x1A, 0x4A, 0x4A, 0x4A, 0x85, 0x1C)
    emit(0xA5, 0x1B, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x05, 0x1C)
    emit(0xC9, 0x40)
    rel(0xB0, 'fb_kill')
    emit(0x85, 0x1C)
    emit(0xBD, 0xC2, 0x7F, 0x18, 0x69, 0x04, 0x4A, 0x4A, 0x4A)
    emit(0xC9, 0x18)
    rel(0xB0, 'fb_fizzle')
    emit(0x85, 0x1D)
    # Check CROWD_BITS($1C, $1D)
    emit(0x8E, 0x1B, 0x00)              # save fb index X in ZP $1B
    abs16(0x20, 'CheckCrowdBit')
    rel(0xF0, 'fb_chk_coll')
    emit(0xAD, 0x02, 0x7F)              # PPU_Q_COUNT == 0?
    rel(0xD0, 'fb_restore_x')
    abs16(0x20, 'BurnPersonAt')
    emit(0xA6, 0x1B)
    rel(0x10, 'fb_fizzle')
    rel(0x30, 'fb_fizzle')
    label('fb_chk_coll')
    emit(0xA6, 0x1B)
    emit(0xA5, 0x1D, 0xC9, 0x16)        # ground row ty >= 22 -> fizzle
    rel(0xB0, 'fb_fizzle')
    rel(0x90, 'fb_next')
    label('fb_fizzle')
    emit(0xA9, 0x02, 0x9D, 0xB0, 0x7F)
    rel(0xD0, 'fb_next')
    label('fb_restore_x')
    emit(0xA6, 0x1B)
    label('fb_next')
    emit(0xE8, 0xE0, 0x06)
    rel(0xF0, 'fb_done')
    abs16(0x4C, 'fb_loop')
    label('fb_done')
    abs16(0x20, 'DrawBarbaOam')
    abs16(0x4C, 'DrawFireballOam')

    # BurnPersonAt($1C=tx, $1D=ty): find fleeing person covering (tx, ty), erase them, stamp static ash!
    label('BurnPersonAt')
    emit(0xAC, 0x01, 0x7F)              # PERSON_COUNT
    rel(0xD0, 'bpa_start')
    emit(0x60)
    label('bpa_start')
    emit(0xA2, 0x00)
    rel(0x10, 'bpa_scan')               # always branches (X=0 >= 0)
    label('bpa_next')
    emit(0xE8, 0xEC, 0x01, 0x7F)
    rel(0xD0, 'bpa_scan')
    emit(0x60)
    label('bpa_scan')
    emit(0xBD, 0x00, 0x60, 0xC9, 0xFF)
    rel(0xF0, 'bpa_next')
    emit(0xA5, 0x1C, 0xDD, 0x00, 0x60)  # tx < px?
    rel(0x90, 'bpa_next')
    emit(0xBD, 0x00, 0x62, 0x29, 0x0F, 0x18, 0x7D, 0x00, 0x60)  # px + w
    emit(0xC5, 0x1C)
    rel(0x90, 'bpa_next')
    rel(0xF0, 'bpa_next')
    emit(0xA5, 0x1D, 0xDD, 0x00, 0x61)  # ty < py?
    rel(0x90, 'bpa_next')
    emit(0xBD, 0x00, 0x62, 0x4A, 0x4A, 0x4A, 0x4A, 0x18, 0x7D, 0x00, 0x61)  # py + h
    emit(0xC5, 0x1D)
    rel(0x90, 'bpa_next')
    rel(0xF0, 'bpa_next')
    # Found person X!
    emit(0x8E, 0x0E, 0x7F)              # CUR_IDX
    emit(0xBD, 0x00, 0x60, 0x8D, 0x0A, 0x7F)  # CUR_X
    emit(0xBD, 0x00, 0x61, 0x8D, 0x0B, 0x7F)  # CUR_Y
    emit(0xBD, 0x00, 0x62, 0x48, 0x29, 0x0F, 0x8D, 0x08, 0x7F)  # CUR_W
    emit(0x68, 0x4A, 0x4A, 0x4A, 0x4A, 0x8D, 0x09, 0x7F)        # CUR_H
    abs16(0x20, 'EraseOldRect')
    abs16(0x20, 'ClearCrowdOldRect')
    # Stamp 2x1 (or 1x1) static ash pile at (CUR_X, CUR_Y + CUR_H - 1)
    emit(0xAE, 0x0E, 0x7F)
    emit(0xA9, 0xFC)                    # default ash tile $FC
    emit(0xAD, 0x04, 0x7F, 0xC9, 0x07)  # CROWD_BANK == 7?
    rel(0xD0, 'bpa_ash_ok')
    emit(0xBD, 0x00, 0x63, 0xC9, 0x02)  # PERSON_BAND == 2?
    rel(0xD0, 'bpa_ash_ok')
    emit(0xA9, 0x3E)                    # Bank 7 band 2 ash tile $3E
    label('bpa_ash_ok')
    emit(0x85, 0x1E)                    # $1E = ash0
    emit(0xAD, 0x0B, 0x7F, 0x18, 0x6D, 0x09, 0x7F, 0x38, 0xE9, 0x01)
    emit(0xC9, 0x18)
    rel(0xB0, 'bpa_kill_p')
    emit(0x85, 0x1D)                    # $1D = ty_bot
    emit(0xAD, 0x0A, 0x7F, 0x85, 0x1C)  # $1C = px
    emit(0xA5, 0x1E)
    abs16(0x20, 'StampAshTile')
    emit(0xAD, 0x08, 0x7F, 0xC9, 0x02)  # w >= 2?
    rel(0x90, 'bpa_kill_p')
    emit(0xE6, 0x1C, 0xA5, 0x1C, 0xC9, 0x40)
    rel(0xB0, 'bpa_kill_p')
    emit(0xA5, 0x1E, 0x18, 0x69, 0x01)  # ash1 = ash0 + 1
    abs16(0x20, 'StampAshTile')
    label('bpa_kill_p')
    emit(0xAE, 0x0E, 0x7F, 0xA9, 0xFF, 0x9D, 0x00, 0x60)  # PERSON_X = $FF
    label('bpa_ret')
    emit(0x60)

    # StampAshTile(A=tile, $1C=tx, $1D=ty): writes BG_TILES, LIVE_TILES, and PushPpuTile
    label('StampAshTile')
    emit(0x48)                          # save tile
    emit(0xA5, 0x1D, 0x4A, 0x4A, 0xAA, 0x18, 0x69, 0x72, 0x85, 0x27)
    emit(0x8A, 0x18, 0x69, 0x78, 0x85, 0x2B)
    emit(0xA5, 0x1D, 0x29, 0x03, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x18, 0x65, 0x1C)
    emit(0x85, 0x26, 0x85, 0x2A)
    rel(0x90, 'sat_ptr_ok')
    emit(0xE6, 0x27, 0xE6, 0x2B)
    label('sat_ptr_ok')
    emit(0x68, 0xA0, 0x00, 0x91, 0x26, 0x91, 0x2A)
    abs16(0x4C, 'PushPpuTile')

    # DrawBarbaOam: writes 16 OAM sprites at $0760..$079F (slots 24..39)
    label('DrawBarbaOam')
    # scroll_px ($1A/$1B) = (($00 & 1) << 8) + $04
    emit(0xA5, 0x04, 0x85, 0x1A, 0xA5, 0x00, 0x29, 0x01, 0x85, 0x1B)
    # base_tile ($1E): $20 if ROAR_TIMER != 0, else (BARBA_ANIM & 8) ? $10 : $00
    emit(0xAD, 0xAC, 0x7F)
    rel(0xF0, 'dbo_walk')
    emit(0xA9, 0x20)
    rel(0xD0, 'dbo_base_ok')
    label('dbo_walk')
    emit(0xAD, 0xAB, 0x7F, 0x29, 0x08, 0x0A)  # 0 or $10
    label('dbo_base_ok')
    emit(0x85, 0x1E)
    emit(0xA2, 0x00)                    # OAM byte offset (0..60 step 4)
    emit(0xA9, 0x00, 0x85, 0x1F)        # row = 0..3
    label('dbo_row')
    emit(0xA5, 0x1F, 0x0A, 0x0A, 0x0A, 0x18, 0x6D, 0xA4, 0x7F, 0x18, 0x69, 0x1F)
    emit(0x85, 0x1D)                    # screen_y = 31 + BARBA_Y + row*8
    emit(0xA9, 0x00, 0x85, 0x1C)        # col = 0..3
    label('dbo_col')
    emit(0xA5, 0x1C, 0x0A, 0x0A, 0x0A, 0x18, 0x6D, 0xA2, 0x7F, 0x85, 0x26)
    emit(0xAD, 0xA3, 0x7F, 0x69, 0x00, 0x85, 0x27)
    emit(0xA5, 0x26, 0x38, 0xE5, 0x1A, 0x85, 0x26)  # sx_lo
    emit(0xA5, 0x27, 0xE5, 0x1B)                    # sx_hi
    rel(0xD0, 'dbo_hide')
    emit(0xA5, 0x1D, 0x9D, 0x60, 0x07)  # Y
    emit(0xAD, 0xA8, 0x7F)              # facing
    rel(0xF0, 'dbo_left')
    emit(0xA9, 0x03, 0x38, 0xE5, 0x1C)  # 3 - col
    rel(0x10, 'dbo_tile')
    label('dbo_left')
    emit(0xA5, 0x1C)
    label('dbo_tile')
    emit(0x85, 0x27)
    emit(0xA5, 0x1F, 0x0A, 0x0A, 0x18, 0x65, 0x27, 0x18, 0x65, 0x1E)
    emit(0x9D, 0x61, 0x07)              # Tile
    emit(0xA9, 0x02)
    emit(0xAC, 0xA8, 0x7F)
    rel(0xF0, 'dbo_attr')
    emit(0x09, 0x40)                    # H-flip
    label('dbo_attr')
    emit(0x9D, 0x62, 0x07)              # Attr
    emit(0xA5, 0x26, 0x9D, 0x63, 0x07)  # X
    rel(0x10, 'dbo_next')
    rel(0x30, 'dbo_next')
    label('dbo_hide')
    emit(0xA9, 0xFE, 0x9D, 0x60, 0x07)
    label('dbo_next')
    emit(0xE8, 0xE8, 0xE8, 0xE8)
    emit(0xE6, 0x1C, 0xA5, 0x1C, 0xC9, 0x04)
    rel(0xD0, 'dbo_col')
    emit(0xE6, 0x1F, 0xA5, 0x1F, 0xC9, 0x04)
    rel(0xF0, 'dbo_done')
    abs16(0x4C, 'dbo_row')
    label('dbo_done')
    emit(0x60)

    # DrawFireballOam: writes 6 OAM sprites at $0710..$0727 (slots 4..9)
    label('DrawFireballOam')
    emit(0xA0, 0x00)                    # i = 0..5
    emit(0xA2, 0x00)                    # OAM byte offset 0..20 step 4
    label('dfo_loop')
    emit(0xB9, 0xB0, 0x7F)              # FB_STATE,Y
    rel(0xF0, 'dfo_hide')
    emit(0xB9, 0xB6, 0x7F, 0x38, 0xE5, 0x1A, 0x85, 0x26)  # sx_lo
    emit(0xB9, 0xBC, 0x7F, 0xE5, 0x1B)                    # sx_hi
    rel(0xD0, 'dfo_hide')
    emit(0xB9, 0xC2, 0x7F, 0x18, 0x69, 0x1F, 0x9D, 0x10, 0x07)  # Y = 31 + FB_Y
    emit(0xB9, 0xB0, 0x7F, 0xC9, 0x02)
    rel(0x90, 'dfo_fly_tile')
    emit(0xC9, 0x08)
    emit(0xA9, 0x34)
    rel(0x90, 'dfo_tile_ok')
    emit(0xA9, 0x35)
    rel(0xD0, 'dfo_tile_ok')
    label('dfo_fly_tile')
    emit(0xAD, 0xAB, 0x7F, 0x4A, 0x29, 0x03, 0x18, 0x69, 0x30)  # $30..$33
    label('dfo_tile_ok')
    emit(0x9D, 0x11, 0x07)              # Tile
    emit(0xA9, 0x02, 0x9D, 0x12, 0x07)  # Attr (Pal 2)
    emit(0xA5, 0x26, 0x9D, 0x13, 0x07)  # X
    rel(0x10, 'dfo_next')
    rel(0x30, 'dfo_next')
    label('dfo_hide')
    emit(0xA9, 0xFE, 0x9D, 0x10, 0x07)
    label('dfo_next')
    emit(0xE8, 0xE8, 0xE8, 0xE8)
    emit(0xC8, 0xC0, 0x06)
    rel(0xD0, 'dfo_loop')
    emit(0x60)

    for pos, kind, target in fixups:
        addr = labels[target]
        if kind == 'rel':
            delta = addr - (base + pos + 1)
            assert -128 <= delta <= 127, f'Branch {target} out of range: {delta}'
            buf[pos] = delta & 0xFF
        else:
            buf[pos] = addr & 0xFF
            buf[pos + 1] = (addr >> 8) & 0xFF
    return bytes(buf), labels


def put_grid(buf: bytearray, bank_4k: int, base_tile: int, rows: list[str], cols: int, tile_rows: int) -> None:
    """Write a (cols*8) x (tile_rows*8) pixel grid into consecutive CHR tiles row-major."""
    for tr in range(tile_rows):
        for tc in range(cols):
            sub = [rows[tr * 8 + y][tc * 8:(tc + 1) * 8] for y in range(8)]
            put_chr_tile(buf, bank_4k, base_tile + tr * cols + tc, sub)


def _patch_ticket_lava(out: bytearray, waldo: bytes) -> None:
    """Replace 'Moon' on the Ticket screen ($070E4, rows 15..18) with 'Lava' and center 'to the Lava'."""
    nt_off = HEADER_SIZE + 0x070E4
    expected_rows = {
        15: bytes.fromhex('CE CF D0 D1 D2 D3 87 D4 D5 D6 87 D7 D8 87 87 87 87 87'),
        16: bytes.fromhex('E1 E2 E3 E4 E5 E6 E7 E8 E9 EA EB EC ED EE E8 EF F0 F1'),
        17: bytes.fromhex('06 07 08 09 0A 0B 0C 0D 0E 0F 10 11 12 13 14 15 16 17'),
        18: bytes.fromhex('1D 1E 1F 20 21 22 23 24 25 26 27 26 28 29 2A 2B 2C 2D'),
    }

    # Decode original 'to the ' (rows 15..18, cols 7..15, pixels x=59..123 -> ox=3..67)
    orig_grid = [[2] * 72 for _ in range(32)]
    for r in range(15, 19):
        bank = 15 if r < 17 else 16
        for c in range(7, 16):
            tid = waldo[nt_off + r * 32 + c]
            off = WALDO_CHR_OFFSET + bank * 4096 + tid * 16
            d = decode_tile(waldo[off:off + 16])
            for y in range(8):
                for x in range(8):
                    orig_grid[(r - 15) * 8 + y][(c - 7) * 8 + x] = d[y][x]

    # Shift 'to the ' +3 px (x=62..126) so 'to the Lava' (x=62..191) aligns with 'One Ticket' (x=62..192)
    canvas = [[2] * 144 for _ in range(32)]
    for y in range(32):
        for ox in range(3, 68):
            canvas[y][ox + 3] = orig_grid[y][ox]

    # Capital L (20x26 at x=129, y=6..31) matching M/T engraved white+black serif style
    glyph_L = [
        '11111111111122222222',
        '1..........122222222',
        '1111.111.11122222222',
        '2211.111.12222222222',
        '2211.111.12222222222',
        '2211.111.12222222222',
        '2211.111.12222222222',
        '2211.111.12222222222',
        '2211.111.12222222222',
        '2211.111.12222222222',
        '2211.111.12222222222',
        '2211.111.12222222222',
        '2211.111.12222222222',
        '2211.111.12222222222',
        '2211.111.12222222222',
        '2211.111.12222222222',
        '2211.111.12222222111',
        '2211.111.12222221..1',
        '2211.111.12222211..1',
        '2211.111.1111111...1',
        '2211.111...........1',
        '2211.11111111111...1',
        '211.11111.111.111..1',
        '1.................11',
        '11111111111111111112',
        '11111111111111111122',
    ]
    # Lowercase a (13x16) and v (14x16) matching yellow+black serif style at y=11..26
    glyph_a = [
        '2211111112222',
        '2133333331222',
        '1333113333122',
        '1333122133312',
        '2111222133312',
        '2221111133312',
        '2213333333312',
        '2133311133312',
        '1333122133312',
        '1333122133312',
        '1333122133312',
        '1333122133312',
        '1333121133312',
        '2133311333311',
        '2213333113331',
        '2221111221111',
    ]
    glyph_v = [
        '11111122111111',
        '13333122133331',
        '21333122133112',
        '21333122133122',
        '22133312133122',
        '22133312133122',
        '22133312133122',
        '22213331331222',
        '22213331331222',
        '22213331331222',
        '22221333312222',
        '22221333312222',
        '22222133312222',
        '22222133122222',
        '22222133122222',
        '22222211122222',
    ]
    cmap = {'.': 0, '1': 1, '2': 2, '3': 3}

    def blit_glyph(rows: list[str], gx: int, gy: int) -> None:
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                val = cmap[ch]
                if val != 2:
                    canvas[gy + dy][gx - 56 + dx] = val

    blit_glyph(glyph_L, 129, 6)
    blit_glyph(glyph_a, 150, 11)
    blit_glyph(glyph_v, 164, 11)
    blit_glyph(glyph_a, 179, 11)

    # Decorative underline under 'ava' (y=28 yellow, y=29 black, x=150..190)
    canvas[29][150 - 56] = 1
    for px in range(151, 191):
        canvas[28][px - 56] = 3
        canvas[29][px - 56] = 1

    cyan_tile = tuple((2,) * 8 for _ in range(8))
    bank_specs = (
        (15, (15, 16), 0x87, list(range(0xCE, 0xD9)) + list(range(0xE1, 0xF2))),
        (16, (17, 18), 0x05, list(range(0x06, 0x18)) + list(range(0x1D, 0x2E))),
    )
    for bank, rows_pair, cyan_tid, pool in bank_specs:
        assigned: dict[tuple[tuple[int, ...], ...], int] = {}
        pool_idx = 0
        for r in rows_pair:
            tr = r - 15
            row_tids: list[int] = []
            for tc in range(18):
                sub = tuple(tuple(canvas[tr * 8 + y][tc * 8 + x] for x in range(8)) for y in range(8))
                if sub == cyan_tile:
                    row_tids.append(cyan_tid)
                else:
                    tid = assigned.get(sub)
                    if tid is None:
                        assert pool_idx < len(pool), f'Ticket Lava Bank {bank} tile pool exhausted'
                        tid = pool[pool_idx]
                        pool_idx += 1
                        assigned[sub] = tid
                        put_chr_tile(out, bank, tid, [''.join(str(v) for v in row) for row in sub])
                    row_tids.append(tid)
            put(out, nt_off + r * 32 + 7, bytes(row_tids), expected=expected_rows[r])


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
    # Move the Bank 14 Cave objects at $8A75 (4 sprites, flashlight), $8A76 (4 sprites, hourglass),
    # and $8A78 (4 sprites, light/circle) out of Barba's 36-sprite (0..35) OAM range to slots
    # 36 ($24), 40 ($28), and 44 ($2C), leaving slots 48..63 for the Cave timer.
    put(out, HEADER_SIZE + 0x1CA75, bytes([0x24, 0x28]), expected=bytes([0x1C, 0x10]))
    put(out, HEADER_SIZE + 0x1CA78, bytes([0x2C]), expected=bytes([0x14]))

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

    # Preserve last horizontal facing (WRAM $7FD4: 0=left, 1=right) when walking up/down in Bank 14 (Cave).
    # Hooks $84FE (ASL A; TAY; LDA $8BA2,Y) -> JMP $8C82 in the freed descriptor space ($8C82..$8D51).
    b14_code = bytearray()
    b14_labels: dict[str, int] = {}
    b14_fixups: list[tuple[int, str]] = []
    def b14_emit(*bs: int) -> None:
        b14_code.extend(bs)
    def b14_label(name: str) -> None:
        b14_labels[name] = len(b14_code)
    def b14_rel(op: int, target: str) -> None:
        b14_code.append(op)
        b14_fixups.append((len(b14_code), target))
        b14_code.append(0)
    b14_emit(0xC9, 0x08)                    # CMP #$08 (0..7 = left)
    b14_rel(0xB0, 'not_left')
    b14_emit(0xA0, 0x00, 0x8C, 0xD4, 0x7F)  # LDY #$00; STY $7FD4
    b14_rel(0xF0, 'map_pose')               # always branches (Y=0)
    b14_label('not_left')
    b14_emit(0xC9, 0x10)                    # CMP #$10 (8..15 = right, 16..23 = up/down)
    b14_rel(0xB0, 'vertical')
    b14_emit(0xA0, 0x01, 0x8C, 0xD4, 0x7F)  # LDY #$01; STY $7FD4
    b14_rel(0xD0, 'map_pose')               # always branches (Y=1)
    b14_label('vertical')
    b14_emit(0x48, 0xAD, 0xD4, 0x7F, 0x29, 0x01, 0xA8, 0x68)  # PHA; LDA $7FD4; AND #1; TAY; PLA
    b14_label('map_pose')
    b14_emit(0x29, 0x01)                    # AND #$01 (pose A/B)
    b14_emit(0xC0, 0x00)                    # CPY #$00
    b14_rel(0xF0, 'do_lookup')
    b14_emit(0x09, 0x08)                    # ORA #$08 (right: indices 8/9)
    b14_label('do_lookup')
    b14_emit(0x0A, 0xA8, 0xB9, 0xA2, 0x8B)  # ASL A; TAY; LDA $8BA2,Y
    b14_emit(0x4C, 0x03, 0x85)              # JMP $8503
    for pos, target in b14_fixups:
        b14_code[pos] = (b14_labels[target] - (pos + 1)) & 0xFF
    assert len(b14_code) <= 0x8D52 - 0x8C82
    put(out, HEADER_SIZE + 0x1CC82, bytes(b14_code),
        expected=waldo[HEADER_SIZE + 0x1CC82:HEADER_SIZE + 0x1CC82 + len(b14_code)])
    put(out, HEADER_SIZE + 0x1C4FE, bytes([0x4C, 0x82, 0x8C]), expected=bytes([0x0A, 0xA8, 0xB9]))

    # 3. Title Screen Stamp Portrait (Bank 13 BG + Bank 198 behind-BG sprite overlay).
    # Keep Title BG Pal 3 as [20(white), 12(blue), 0E(black), 16(red)] and patch Title Sprite Pal 0
    # ($1E890: 20 16 0E 38 -> 20 16 27 38) so Barba uses his full Z2 3-tone palette:
    # 1=$16 (red-orange), 2=$27 (light orange/gold), 3=$38 (ivory/white), with BG 2=$0E (black) outline.
    put(out, HEADER_SIZE + 0x1E88F, bytes([0x16]), expected=bytes([0x26]))
    put(out, HEADER_SIZE + 0x1E892, bytes([0x27]), expected=bytes([0x0E]))
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

    # Cut out Barba's silhouette to BG 0 (transparent so behind-BG sprite shows through) and add a 1px black (2) outline
    head = source_head(z2, 'open')
    neck = neck_raw
    stamp_head = resize_x(head, 24)
    stamp_neck = resize_x(neck, 12)
    ox, oy = 17, 15
    barba_mask = [[False] * 48 for _ in range(48)]
    for y in range(16):
        for x in range(12):
            yy, xx = oy + 14 + y, ox + 10 + x
            if stamp_neck[y][x] != '0' and 0 <= yy < 48 and 0 <= xx < 48 and in_stamp_box(xx, yy):
                barba_mask[yy][xx] = True
    for y in range(16):
        for x in range(24):
            yy, xx = oy + y, ox + x
            if stamp_head[y][x] != '0' and 0 <= yy < 48 and 0 <= xx < 48 and in_stamp_box(xx, yy):
                barba_mask[yy][xx] = True

    for y in range(48):
        for x in range(48):
            if barba_mask[y][x]:
                if grid[y][x] == 1:
                    grid[y][x] = 0
            elif grid[y][x] == 1 and any(
                0 <= y + dy < 48 and 0 <= x + dx < 48 and barba_mask[y + dy][x + dx]
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
            ):
                grid[y][x] = 2

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

    _patch_ticket_lava(out, waldo)

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
    crowd_cfg = json.loads(CROWD_JSON.read_text(encoding='utf-8'))
    ash_rows = json.loads(ASH_JSON.read_text(encoding='utf-8'))['rows']
    flee_set = {tuple(x) for x in crowd_cfg.get('flee', [])}
    hide_set = {tuple(x) for x in crowd_cfg.get('hide', [])}
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
            n_non_waldo = out[desc_off + 1]
            for k in range(n_non_waldo):
                nw_off = desc_off + 2 + (n_waldo + k) * 6
                ew, eh = out[nw_off], out[nw_off + 1]
                key = (prg_bank, band_idx, k)
                if (ew == 1 and eh == 1) or key in hide_set:
                    out[nw_off + 4] = 0
                    out[nw_off + 5] &= 0xBF
                elif key in flee_set:
                    out[nw_off + 5] |= 0x40
                    cap = 2 if ew * eh <= 6 else 1
                    if out[nw_off + 4] > cap:
                        out[nw_off + 4] = cap
                else:
                    out[nw_off + 5] &= 0xBF
                    if out[nw_off + 4] > 1:
                        out[nw_off + 4] = 1
            # Write Barba's 16x8 ash mound (assets/ash.json) into the 2 freed BG CHR tiles (tiles[0], tiles[1])
            for tc in range(2):
                sub = [ash_rows[y][tc * 8:(tc + 1) * 8] for y in range(8)]
                put_chr_tile(out, b4k, tiles[tc], sub)
    write_shout_font(out)

    # 6. Title Screen: "WHERE'S WALDO?" -> "THERE'S BARBA" (or "WHERE'S BARBA?" if TITLE_MODE == 'wheres_barba').
    TITLE_MODE = 'theres_barba'  # set to 'wheres_barba' to revert to "WHERE'S BARBA?"

    def _patch_title_wheres_barba() -> None:
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

        glyphs = {
            'B': ['11110', '10001', '10001', '11110', '10001', '10001', '11110'],
            'A': ['00100', '01110', '01010', '10001', '11111', '10001', '10001'],
            'R': ['11110', '10001', '10001', '11110', '10100', '10010', '10001'],
        }
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

        for y in range(H14):
            for x in range(W14):
                if x >= 161 or (x >= 160 and y < 14) or y >= 99.0 - 0.37 * x:
                    continue
                u, v = to_uv(x, y)
                if -12.0 <= u <= 148.0 and -4.0 <= v <= 48.0:
                    g14[y][x] = 0

        for y in range(H14):
            for x in range(W14):
                if x >= 159 or y >= 95.0 - 0.37 * x:
                    continue
                u, v = to_uv(x, y)
                if not (-4.0 <= u <= 132.0 and -3.0 <= v <= 32.0):
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
        # Clear tiny gray legacy shadow artifact below first 'B' of BARBA (r26 c11 = $D8, unique)
        put_chr_tile(out, 14, 0xD8, ['0' * 8] * 8)

    def _patch_title_theres_barba() -> None:
        # 1) Patch Bank 14 nametable cells for "BARBA" (plus clear shared tile $36 at r18 c6 and $7C at r15 c10).
        nt14_patches = [
            (1, 0,  0x1E, 0x00),  # r17 c6: clear 1px speck top-left of 'T'
            (1, 15, 0x00, 0xED),
            (2, 0,  0x36, 0x00),  # r18 c6: was shared $36 (only 1px shadow of 'W')
            (2, 12, 0x1E, 0xEE),
            (3, 9,  0x00, 0xEF),
            (4, 7,  0x00, 0xF0),
            (5, 4,  0x00, 0xF1),
            (10, 4, 0x36, 0x00),  # r26 c10: clear 1px speck bottom-left of first 'B'
        ]
        for tr, tc, old_tid, new_tid in nt14_patches:
            put(out, HEADER_SIZE + 0x0651B + tr * 32 + tc, bytes([new_tid]), expected=bytes([old_tid]))

        # r15 (Bank 13) patches: replace shared $7C at r15 c10 with free tile $F3; clear r15 c26..27 ($F0/$F1 top of '?')
        nt_base = HEADER_SIZE + 0x06315
        put(out, nt_base + 15 * 32 + 10, bytes([0xF3]), expected=bytes([0x7C]))
        blank_8 = ['0' * 8 for _ in range(8)]
        for tid in (0xF0, 0xF1, 0xF3):
            put_chr_tile(out, 13, tid, blank_8)
        # In $E2 (r15 c11, x=88..95), clear W's 4th leg (x<6) while preserving H's top-left corner (x>=6, y=125..127)
        e2_off = WALDO_CHR_OFFSET + 13 * 4096 + 0xE2 * 16
        e2_d = decode_tile(bytes(out[e2_off:e2_off + 16]))
        for y in range(8):
            for x in range(6):
                e2_d[y][x] = 0
        put_chr_tile(out, 13, 0xE2, [''.join(str(v) for v in r) for r in e2_d])

        title_b14_nt = [
            [0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F,0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18,0x19],
            [0x1E,0x1F,0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x29,0x2A,0x2B,0x00,0xED,0x2C,0x2D,0x2E,0x2F,0x30,0x31,0x32],
            [0x00,0x37,0x38,0x39,0x3A,0x3B,0x3C,0x3D,0x3E,0x3F,0x40,0x41,0xEE,0x42,0x43,0x44,0x45,0x46,0x47,0x48,0x49,0x4A,0x4B],
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

        # 2) Clear 'W' in Bank 14 (r16..r20, c7..c11 -> tc=1..5).
        # Keep c12 (0x09,0x24,0x3C,0x55) which is 'H' left leg, and keep c11 r16..r17 (0x08,0x23) x>=93 which is 'H' left edge/shadow!
        w_clear_tids = {
            0x06, 0x07,
            0x1F, 0x20, 0x21, 0x22,
            0x37, 0x38, 0x39, 0x3A, 0x3B,
            0x50, 0x51, 0x52, 0x53, 0x54,
            0x68, 0x69, 0x6A, 0x6B,
        }
        for tr in range(5):
            for tc in range(1, 6):
                if title_b14_nt[tr][tc] in w_clear_tids:
                    for y in range(8):
                        for x in range(8):
                            g14[tr * 8 + y][tc * 8 + x] = 0
        # Clear 'W' 4th leg in c11 (tc=5, x=88..95) while preserving 'H' left-leg edge/shadow at x>=93 (r16..r17)
        for gy in range(16):
            for x in range(5):
                g14[gy][5 * 8 + x] = 0

        # Set attr5[2] (r20..r21 c08..c11) top-left (c08..c09) from pal 1 (red) to pal 2 (blue) so full-height 'T' stays blue
        put(out, HEADER_SIZE + 0x06315 + 960 + 5 * 8 + 2, bytes([0xAA]), expected=bytes([0xA9]))

        # 3) Draw blue 'T' (matching "HERE'S": rigid -20.5 deg tilt, full 31px height, 1=blue, 2=black, 3=grey)
        # Pixels at py >= 160 (r20, shared with red BARBA) go into OAM sprite tiles $0A/$0B (Pal 1) instead of BG.
        ang_t = math.radians(-20.5)
        ca_t, sa_t = math.cos(ang_t), math.sin(ang_t)
        tx0, ty0 = 68.5, 136.0

        def in_t(px: float, py: float) -> bool:
            dx, dy = px - tx0, py - ty0
            u = dx * ca_t + dy * sa_t
            v = -dx * sa_t + dy * ca_t
            if 0.0 <= u <= 21.0 and 0.0 <= v < 6.5:
                return True
            if 6.5 <= u <= 13.5 and 0.0 <= v <= 31.0:
                return True
            if 5.2 <= u <= 7.0 and 5.5 <= v <= 7.6:
                return True
            return False

        b13_t_tiles = {(15, 10): 0xF3, (15, 11): 0xE2}
        t_tip_grid = [[0] * 16 for _ in range(8)]
        for py in range(120, 168):
            for px in range(65, 108):
                if px >= 109 and py >= 128:
                    continue  # stay left of 'H'
                if in_t(px, py):
                    col_val = 1
                elif any(in_t(px + dx, py + dy)
                         for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))):
                    col_val = 2
                elif any(in_t(px + dx, py + dy)
                         for dx, dy in ((1, -2), (2, -1), (2, -2), (3, -1), (3, -2), (1, -3), (2, -3), (3, -3),
                                        (1, -4), (2, -4), (3, -4))):
                    col_val = 3
                else:
                    continue
                if py >= 160:
                    if 78 <= px < 94:
                        t_tip_grid[py - 160][px - 78] = col_val
                    continue
                tr_full, tc_full = py // 8, px // 8
                if tr_full == 15:
                    tid = b13_t_tiles.get((tr_full, tc_full))
                    if tid is not None:
                        off = WALDO_CHR_OFFSET + 13 * 4096 + tid * 16
                        d = decode_tile(bytes(out[off:off + 16]))
                        d[py % 8][px % 8] = col_val
                        put_chr_tile(out, 13, tid, [''.join(str(v) for v in r) for r in d])
                elif 16 <= tr_full <= 19 and 6 <= tc_full <= 13:
                    g14[(tr_full - 16) * 8 + (py % 8)][(tc_full - 6) * 8 + (px % 8)] = col_val

        # 3b) Turn the apostrophe (Bank 13 r11..r13 c23..c24: $92,$93,$A9,$AA,$C1,$C2) into an arrow pointing at Barba
        # Preserve 'S' pixels on the right edge of $93 (ax >= 13) and $AA (ax >= 14).
        arrow_nt = [[0x92, 0x93], [0xA9, 0xAA], [0xC1, 0xC2]]
        ag = [[0] * 16 for _ in range(24)]
        for tr, row_t in enumerate(arrow_nt):
            for tc, tid in enumerate(row_t):
                off = WALDO_CHR_OFFSET + 13 * 4096 + tid * 16
                d = decode_tile(bytes(out[off:off + 16]))
                for y in range(8):
                    for x in range(8):
                        ax = tc * 8 + x
                        if (tid == 0x93 and x >= 5) or (tid == 0xAA and x >= 6):
                            ag[tr * 8 + y][ax] = d[y][x]

        def in_arrow(ax: float, ay: float) -> bool:
            # Steep upward arrow from (5.0, 21.0) pointing at Barba portrait centroid via tip (9.0, 2.0)
            ux, uy = 0.206, -0.979
            dx, dy = ax - 5.0, ay - 21.0
            along = dx * ux + dy * uy
            perp = abs(-dx * uy + dy * ux)
            if 0.0 <= along <= 14.0 and perp <= 1.6:
                return True
            if 12.5 <= along <= 19.4 and perp <= (19.4 - along) * 0.65:
                return True
            return False

        for ay in range(24):
            for ax in range(16):
                if ag[ay][ax] != 0:
                    continue  # preserve 'S' on right edge of $93/$AA
                if in_arrow(ax, ay):
                    ag[ay][ax] = 1
                elif any(in_arrow(ax + dx, ay + dy)
                         for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))):
                    ag[ay][ax] = 2
                elif any(in_arrow(ax + dx, ay + dy)
                         for dx, dy in ((1, -2), (2, -1), (2, -2), (1, -3), (2, -3))):
                    ag[ay][ax] = 3

        for tr, row_t in enumerate(arrow_nt):
            for tc, tid in enumerate(row_t):
                sub = [''.join(str(ag[tr * 8 + y][tc * 8 + x]) for x in range(8)) for y in range(8)]
                put_chr_tile(out, 13, tid, sub)

        # 4) Clear WALDO? strip (including '?') and render centered "BARBA"
        glyphs = {
            'B': ['11110', '10001', '10001', '11110', '10001', '10001', '11110'],
            'A': ['00100', '01110', '01010', '10001', '11111', '10001', '10001'],
            'R': ['11110', '10001', '10001', '11110', '10100', '10010', '10001'],
        }
        ang = math.radians(-20.5)
        ca, sa = math.cos(ang), math.sin(ang)
        x0, y0 = 35.0, 48.0

        def in_bowl(lu: float, v: float, v0: float, v1: float, w: float, r_out: float) -> bool:
            if lu < 0 or lu >= w or v < v0 or v >= v1:
                return False
            if lu > w - r_out:
                if v < v0 + r_out and (lu - (w - r_out)) ** 2 + (v - (v0 + r_out)) ** 2 > r_out ** 2:
                    return False
                if v > v1 - r_out and (lu - (w - r_out)) ** 2 + (v - (v1 - r_out)) ** 2 > r_out ** 2:
                    return False
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
            if lu < 0 or lu >= 19.0 or v < 0 or v >= 28.0:
                return False
            if lu < 4.0:
                return True
            return in_bowl(lu, v, 0.0, 15.2, 18.2, 3.5) or in_bowl(lu, v, 12.2, 28.0, 19.0, 3.5)

        def in_a(lu: float, v: float) -> bool:
            """19x28 'A' with smooth rounded arch top instead of blocky 5x7 stair-steps."""
            if lu < 0 or lu >= 19.0 or v < 0 or v >= 28.0:
                return False
            # Outer arch: rounded top (radius ~5.5 centered at (9.5, 5.5)) + smooth flared legs
            if v < 5.5:
                if (lu - 9.5) ** 2 + (v - 5.5) ** 2 > 5.5 ** 2:
                    return False
            else:
                half_w = 5.5 + (v - 5.5) * (4.0 / 22.5)
                if abs(lu - 9.5) > half_w:
                    return False
            # Crossbar
            if 15.0 <= v <= 19.2:
                return True
            # Inner cutout (rounded arch top, flared inner legs)
            if v >= 4.5:
                in_hw = 2.0 + (v - 4.5) * (3.2 / 23.5)
                if v < 7.0:
                    if (lu - 9.5) ** 2 + (v - 7.0) ** 2 < 2.2 ** 2:
                        return False
                elif abs(lu - 9.5) < in_hw:
                    return False
            return True

        def in_word(u: float, v: float) -> bool:
            if v < 0 or v >= 28.0 or u < 0:
                return False
            # '!' after "BARBA" at u = 122..128 (dot v < 26.8 so bottom border stays in r19 above r20 border)
            if 122.0 <= u < 128.0:
                return (0.0 <= v < 18.0) or (22.0 <= v < 26.8)
            idx = int(u // 24.0)
            if idx < 0 or idx >= 5:
                return False
            lu = u - idx * 24.0
            if lu >= 19.0:
                return False
            ch = 'BARBA'[idx]
            if ch == 'B':
                return in_b(lu, v)
            if ch == 'A':
                return in_a(lu, v)
            gx = min(4, int(lu / 3.8))
            gy = min(6, int(v / 4.0))
            return glyphs[ch][gy][gx] == '1'

        def to_uv(px: float, py: float) -> tuple[float, float]:
            dx, dy = px - x0, py - y0
            return (dx * ca + dy * sa, -dx * sa + dy * ca)

        # Clear WALDO? strip (keep v >= -4.0 so "HERE'S" bottoms & shadows stay intact; clear 0x7E speck at x < 32)
        for y in range(H14):
            for x in range(W14):
                if x < 16 or x >= 184 or y >= 99.0 - 0.37 * x:
                    continue
                u, v = to_uv(x, y)
                if (-30.0 <= u <= 155.0 and -4.0 <= v <= 48.0) or (x < 32 and -30.0 <= u <= 0.0 and -16.0 <= v <= 48.0):
                    g14[y][x] = 0

        for y in range(H14):
            for x in range(W14):
                if x >= 179 or y >= 95.0 - 0.37 * x:
                    continue
                u, v = to_uv(x, y)
                if not (-4.0 <= u <= 132.0 and -3.0 <= v <= 32.0):
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
        # Clear tiny gray legacy shadow artifact below first 'B' of BARBA (r26 c11 = $D8, unique)
        put_chr_tile(out, 14, 0xD8, ['0' * 8] * 8)
        return t_tip_grid

    t_tip_grid = None
    if TITLE_MODE == 'wheres_barba':
        _patch_title_wheres_barba()
    else:
        t_tip_grid = _patch_title_theres_barba()

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

    # 9. Moon Ending Barba sprite (1KB CHR Bank 65 = 4KB Bank 16 $40..$67, 44x48 px, 12 sprites in 8x16 mode).
    # Map R4 ($1800-$1BFF, tiles $80-$BF) -> Bank 65 at $A042 via $BF9F, and draw 12 sprites at $A1B6 via $BFBE.
    # 4 sprites/scanline at every height (4 Rocket + 4 Barba = 8, zero flicker and zero Rocket/Barba drops).
    # All 12 sprites use Sprite Pal 2 [0E(trans), 20(white), 16(red), 38(pale yellow)].
    mcmap = {'0': '0', '1': '2', '2': '3', '3': '1'}
    mhead = [r[::-1] for r in head_24]
    mhead_up = [r[::-1] for r in shear_up(resize_x(source_head(z2, 'open'), 24))]
    mneck = [r[::-1] for r in resize_x(neck_raw, 12)]
    melbow = [r[::-1] for r in resize_x(elbow_16, 12)]
    mtail = [r[::-1] for r in resize_x(trail_32, 22)]

    def make_moon_canvas(head_rows: list[str], hx: int, hy: int, clip_head_y: int = 48) -> list[str]:
        canvas = [['0'] * 44 for _ in range(48)]

        def mblit(rows: list[str], ox: int, oy: int, max_y: int = 48) -> None:
            for iy, row in enumerate(rows):
                if oy + iy >= max_y:
                    continue
                for ix, px in enumerate(row):
                    if px != '0' and 0 <= oy + iy < 48 and 0 <= ox + ix < 44:
                        canvas[oy + iy][ox + ix] = mcmap[px]

        mblit(mtail, 0, 32)
        mblit(melbow, 20, 32)
        mblit(mneck, 20, 16)
        mblit(mneck[:4], 20, 30)
        mblit(head_rows, hx, hy, clip_head_y)

        # Waldo space helmet bubble around Barba's head (center (28.5, 10.5), rx=14.5, ry=10.0).
        for y in range(21):
            for x in range(14, 44):
                if canvas[y][x] != '0':
                    continue
                dx = (x - 28.5) / 14.5
                dy = (y - 10.5) / 10.0
                r2 = dx * dx + dy * dy
                if 0.80 <= r2 <= 1.08:
                    canvas[y][x] = '1'
                elif dx < -0.20 and dy < -0.20 and 0.48 <= r2 <= 0.64:
                    canvas[y][x] = '1'
                elif 0.35 <= dx <= 0.55 and -0.60 <= dy <= -0.35 and 0.45 <= r2 <= 0.65:
                    canvas[y][x] = '1'
        # Helmet neck collar at y=19..20 across neck (x=19..32)
        for x in range(19, 33):
            canvas[19][x] = '1'
            if x % 2 == 1:
                canvas[20][x] = '2'
        return [''.join(r) for r in canvas]

    mrows = make_moon_canvas(mhead, 18, 3)
    mrows_roar = make_moon_canvas(mhead_up, 16, -1, clip_head_y=19)
    # 12 8x16 sprite pairs in Bank 65 (4KB Bank 16, tiles $40..$57 normal, $58..$67 roar head+helmet):
    # 0..3: Head+Helmet at (x=12,20,28,36, y=0..15)
    # 4..7: Neck+Bottom-of-Helmet+Collar at (x=12,20,28,36, y=16..31)
    # 8..11: Tail+Torso+Elbow at (x=0,8,16,24, y=32..47)
    moon_sprites = [
        (12, 0), (20, 0), (28, 0), (36, 0),
        (12, 16), (20, 16), (28, 16), (36, 16),
        (0, 32), (8, 32), (16, 32), (24, 32),
    ]
    for idx, (sx, sy) in enumerate(moon_sprites):
        for sub_y in (0, 8):
            tile_rows = [mrows[sy + sub_y + y][sx:sx + 8] for y in range(8)]
            put_chr_tile(out, 16, 0x40 + idx * 2 + (sub_y // 8), tile_rows)
    for idx, (sx, sy) in enumerate(moon_sprites[:8]):
        for sub_y in (0, 8):
            tile_rows = [mrows_roar[sy + sub_y + y][sx:sx + 8] for y in range(8)]
            put_chr_tile(out, 16, 0x58 + idx * 2 + (sub_y // 8), tile_rows)

    # Move Rocket col 3, rows 1..5 (10 tiles, 9 unique) into Moon BG (4K Bank 8, R1=$21 -> PPU $80..$FF)
    # using tile IDs unused outside the Rocket area, with Rocket aligned at X=$E8 (-24, so cols 3..7 are at X=0..39).
    # That reduces Rocket to 4 sprites/scanline across rows 0..5 (hiding empty row 0 col 7 + col 3 rows 1..5),
    # giving 4 sprites/scanline for Barba at all heights with zero flicker and zero Moon BG corruption.
    rocket_bg_cmap = {0: 0, 1: 3, 2: 1, 3: 0}
    moon_free_ppu_tiles = [0x81, 0x82, 0x83, 0x84, 0xA1, 0xA2, 0xA3, 0xA4, 0xFF]
    col3_raw = []
    for r in range(1, 6):
        i = r * 8 + 3
        t = 0x80 + i * 2 if i < 32 else 0xC0 + (i - 32) * 2
        for h in (0, 1):
            off = WALDO_CHR_OFFSET + 16 * 4096 + (t + h) * 16
            d = decode_tile(bytes(waldo[off:off + 16]))
            col3_raw.append([''.join(str(rocket_bg_cmap[p]) for p in row) for row in d])
    # Share (r=1, h=1) [idx 1] with (r=2, h=1) [idx 3] (3 px diff) so 9 free PPU tiles suffice.
    slot_for_idx = [0, 1, 2, 1, 3, 4, 5, 6, 7, 8]
    col3_tiles = [moon_free_ppu_tiles[slot] for slot in slot_for_idx]

    put(out, HEADER_SIZE + 0x000CD, bytes([0x60]), expected=bytes([0x5C]))  # Rocket Y = $60
    put(out, HEADER_SIZE + 0x00145, bytes([0xE7]), expected=bytes([0xF4]))  # Rocket X = $E8
    put(out, HEADER_SIZE + 0x00158, bytes.fromhex('20 10 ae ea'), expected=bytes.fromhex('a9 2c 85 26'))

    # Store col3_tiles (10 bytes) + hide OAM offsets (6 bytes) at $AF00
    hide_oam = bytes([
        0x1C,                                # Rocket row 0 col 7 (empty)
        0x2C, 0x4C, 0x6C, 0x8C, 0xAC,        # Rocket col 3 rows 1..5
    ])
    put(out, HEADER_SIZE + 0x00F00, bytes(col3_tiles) + hide_oam, expected=bytes(16))
    # $AE10: VBlank-sync write of Rocket col 3 (c=0, r=14..23) + attrs $23D8/$23E0/$23E8 + hide 6 Rocket OAM slots
    rocket_bg_code = bytes.fromhex(
        'a5 00 29 7f 8d 00 20 2c 02 20 2c 02 20 10 fb '
        'a5 00 09 04 8d 00 20 '
        'a9 21 8d 06 20 a9 c0 8d 06 20 '
        'a2 00 bd 00 af 8d 07 20 e8 e0 0a d0 f5 '
        'a5 00 29 fb 8d 00 20 '
        'a9 23 8d 06 20 a9 d8 8d 06 20 a9 10 8d 07 20 '
        'a9 23 8d 06 20 a9 e0 8d 06 20 a9 11 8d 07 20 '
        'a9 23 8d 06 20 a9 e8 8d 06 20 a9 11 8d 07 20 '
        'a9 00 8d 06 20 8d 06 20 8d 05 20 8d 05 20 '
        'a5 00 8d 00 20 '
        'a0 00 a9 f4 be 0a af 9d 00 07 c8 c0 06 d0 f5 '
        'a9 2c 85 26 60'
    )
    assert len(rocket_bg_code) <= 0xF0, f'rocket_bg_code too large: {len(rocket_bg_code)}'
    put(out, HEADER_SIZE + 0x00E10, rocket_bg_code, expected=bytes(len(rocket_bg_code)))

    # Patch Bank 0 $A042 -> JSR $BF9F to map R1 = $C0 (CHR 4K Bank 48) & R4 = Bank 65,
    # $A1A8 -> JSR $C970 (Moon pause + head-up roar + post-roar pause),
    # and $A1B6 -> JMP $BFBE for 12-sprite OAM.
    put(out, HEADER_SIZE + 0x00042, bytes.fromhex('20 9f bf ea ea'), expected=bytes.fromhex('a9 47 8d 04 02'))
    put(out, HEADER_SIZE + 0x001A1, bytes.fromhex('20 70 c9 ea ea ea ea ea'),
        expected=bytes.fromhex('a9 01 85 02 a5 02 d0 fc'))
    put(
        out, HEADER_SIZE + 0x001B6,
        bytes.fromhex('4c be bf') + bytes([0xEA] * 30) + bytes([0x60]),
        expected=waldo[HEADER_SIZE + 0x001B6:HEADER_SIZE + 0x001D8],
    )
    moon_bank0_code = bytes.fromhex(
        # $BF9F: map R1 = $C0 (4K Bank 48), R4 = Bank 65, restore R7 = 0 ($A042)
        'a9 41 8d 00 80 a9 c0 8d 01 80 85 3e '
        'a9 44 8d 00 80 a9 41 8d 01 80 a9 47 8d 04 02 8d 00 80 60'
    )
    moon_oam_code = bytes.fromhex(
        # $BFBE (48 bytes): draw 12 Barba sprites from Bank 16 tables ($DFC0=off, $DFCC=dx, $DFD8=dy)
        'a0 00 a9 81 85 08 '           # LDY #0; LDA #$81; STA $08
        'be c0 df '                    # LDX $DFC0,Y
        'a5 27 18 79 d8 df 9d 00 07 '  # LDA $27; CLC; ADC $DFD8,Y; STA $0700,X
        'a5 08 9d 01 07 18 69 02 85 08 '  # LDA $08; STA $0701,X; CLC; ADC #2; STA $08
        'a9 02 9d 02 07 '              # LDA #2; STA $0702,X
        'a5 26 18 79 cc df 9d 03 07 '  # LDA $26; CLC; ADC $DFCC,Y; STA $0703,X
        'c8 c0 0c d0 d7 60'            # INY; CPY #12; BNE loop (-41 = $D7); RTS
    )
    swap_moon_oam = bytes.fromhex(
        # $BFEE (17 bytes): set OAM #56..#63 tiles to A, A+2, ..., A+14
        'a2 00 9d e1 07 18 69 02 e8 e8 e8 e8 e0 20 d0 f2 60'
    )
    put(out, HEADER_SIZE + 0x01F9F, moon_bank0_code + moon_oam_code + swap_moon_oam,
        expected=bytes(len(moon_bank0_code + moon_oam_code + swap_moon_oam)))

    # 10. Subway level (PRG Bank 2, 4KB CHR Bank 2 tiles $B8..$C3 = OAM sprite tiles $78..$83):
    #     - Item 0 ($78..$7B, Pal 1): Barba (replacing Waldo)
    #     - Item 1 ($7C..$7F, Pal 2): Link (replacing Odlaw/bad guy; extracted from z2.nes CHR bank 2)
    #     - Item 2 ($80..$83, Pal 1): Barba Flame (replacing Glasses; OAM attr $02 -> $01)
    def frame_subway_14(rows14: list[str], cmap: dict[str, str]) -> list[str]:
        framed = ['0' * 16]
        for r in rows14:
            framed.append('0' + ''.join(cmap[c] for c in r) + '0')
        framed.append('0' * 16)
        return framed

    # 10a. Barba ($78..$7B -> Bank 2 $B8..$BB, Pal 1 = [0E black, 20 white, 16 red, 38 ivory])
    sub_barba_14 = [list(r) for r in resize_xy(barba['small'], 14, 14)]
    sub_barba_14[11][0], sub_barba_14[11][1], sub_barba_14[11][2] = '0', '3', '1'
    sub_barba_14[12][0], sub_barba_14[12][1], sub_barba_14[12][2] = '1', '2', '3'
    sub_barba_grid = frame_subway_14([''.join(r) for r in sub_barba_14], {'0': '1', '1': '0', '2': '2', '3': '3'})
    put_grid(out, bank_4k=2, base_tile=0xB8, rows=sub_barba_grid, cols=2, tile_rows=2)

    # 10b. Link ($7C..$7F -> Bank 2 $BC..$BF, Pal 2 = [0E black, 20 white, 2A green, 37 skin])
    def z2_spr_tile(bank_4k: int, tid: int) -> list[str]:
        off = CHR_OFFSET + bank_4k * 4096 + tid * 16
        return [''.join(str(c) for c in row) for row in decode_tile(z2[off:off + 16])]

    link_l = z2_spr_tile(2, 0x00) + z2_spr_tile(2, 0x01)
    link_r = z2_spr_tile(2, 0x02) + z2_spr_tile(2, 0x03)
    link_top16 = [a + b for a, b in zip(link_l, link_r)]
    sub_link_14 = resize_xy(link_top16[1:16], 14, 14)
    sub_link_grid = frame_subway_14(sub_link_14, {'0': '1', '1': '0', '2': '3', '3': '2'})
    put_grid(out, bank_4k=2, base_tile=0xBC, rows=sub_link_grid, cols=2, tile_rows=2)
    put(out, HEADER_SIZE + 0x1E82A, bytes([0x2A, 0x37]), expected=bytes([0x22, 0x38]))

    # 10c. Barba Flame ($80..$83 -> Bank 2 $C0..$C3, Pal 1 = [0E black, 20 white, 16 red, 38 ivory])
    sub_flame_14 = [
        '11111101111111',
        '11111020101111',
        '11110222020111',
        '11102232220111',
        '11022333201111',
        '11023333220111',
        '10223113320111',
        '10233111322011',
        '10231111332011',
        '10233113322011',
        '11023333220111',
        '11022333220111',
        '11100222001111',
        '11111000111111',
    ]
    sub_flame_grid = frame_subway_14(sub_flame_14, {'0': '0', '1': '1', '2': '2', '3': '3'})
    put_grid(out, bank_4k=2, base_tile=0xC0, rows=sub_flame_grid, cols=2, tile_rows=2)
    put(out, HEADER_SIZE + 0x04410, bytes([0x01]), expected=bytes([0x02]))

    # 7. Expand PRG from 128KB (8x16KB) to 256KB (16x16KB) and add Barba's sampled roar in Bank 16 ($C000).
    # Waldo uses MMC3 PRG Mode 1 ($8000 bit 6=1: $8000=Bank 30, $A000=R7, $C000=R6, $E000=Bank 31)
    # and never reads or switches R6 ($C000-$DFFF), making Bank 16 ideal for DPCM samples + hooks.
    roar_wav = ROOT / 'assets/roar.wav'
    if roar_wav.is_file():
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        sample, roar_info = roar_sample.convert(roar_wav, OUT_PATH.parent)
        assert len(sample) <= 0x0900, f'Sample too large for $C000-$C8FF: {len(sample)}'
        roar_rate = roar_info['rate_index']
        roar_len = (len(sample) - 1) // 16

        hdr = bytearray(out[:HEADER_SIZE])
        hdr[4] = 0x10  # 16 x 16KB PRG = 256KB
        hdr[5] = 0x20  # 32 x 8KB CHR = 256KB (4KB Bank 48 holds Moon BG copy of Bank 8)
        prg_128 = bytes(out[HEADER_SIZE:HEADER_SIZE + 0x20000])
        chr_128 = bytes(out[HEADER_SIZE + 0x20000:])
        chr_256 = bytearray(chr_128) + bytes(0x20000)
        chr_256[48 * 4096:49 * 4096] = chr_128[8 * 4096:9 * 4096]
        for idx, slot in enumerate(slot_for_idx):
            if idx == 3:
                continue
            t_off = 48 * 4096 + (moon_free_ppu_tiles[slot] - 0x80) * 16
            chr_256[t_off:t_off + 16] = encode_tile(col3_raw[idx])

        # 1KB CHR Bank 128 ($80, 4KB Bank 32): 32x32 Barba (Pose A $00..$0F, Pose B $10..$1F, Roar $20..$2F),
        # 4 Fireball frames ($30..$33), and 2 Fizzle frames ($34..$35) for search levels (R2).
        # Palette 2 = [trans, 1=red ($16), 2=gold ($27), 3=ivory ($38)].
        head_20_closed = resize_xy(source_head(z2, 'closed'), 20, 14)
        head_20_open = resize_xy(source_head(z2, 'open'), 20, 14)
        neck_10 = resize_x(neck_raw, 10)
        elbow_10 = resize_xy(elbow_16, 10, 10)
        trail_14 = resize_xy(trail_32, 14, 10)

        def make_search_barba(head_rows: list[str], phase: int) -> list[str]:
            canvas = [['0'] * 32 for _ in range(32)]
            hy = 1 if phase == 1 else 0
            tb = -1 if phase == 1 else 0
            for iy, row in enumerate(elbow_10):
                for ix, px in enumerate(row):
                    if px != '0':
                        canvas[22 + iy][8 + ix] = px
            for iy, row in enumerate(trail_14):
                for ix, px in enumerate(row):
                    if px != '0':
                        yy = 22 + iy + (tb if ix >= 7 else 0)
                        if 0 <= yy < 32 and 18 + ix < 32:
                            canvas[yy][18 + ix] = px
            for y in range(hy + 12, 24):
                sway = (0, -1, 0, 1)[((y - hy) // 3 + phase) % 4] if y < 21 else 0
                row = neck_10[(y - hy - 12) % 16]
                nx = 8 + sway
                for ix, px in enumerate(row):
                    if px != '0' and 0 <= nx + ix < 32:
                        canvas[y][nx + ix] = px
            for iy, row in enumerate(head_rows):
                for ix, px in enumerate(row):
                    if px != '0' and 0 <= hy + iy < 32 and 0 <= ix - 1 < 32:
                        canvas[hy + iy][ix - 1] = px
            return [''.join(r) for r in canvas]

        def put_1k_tile(bank_1k: int, tid: int, rows: list[str]) -> None:
            off = bank_1k * 1024 + tid * 16
            chr_256[off:off + 16] = encode_tile(rows)

        for base_tid, frame_rows in (
            (0x00, make_search_barba(head_20_closed, 0)),
            (0x10, make_search_barba(head_20_closed, 1)),
            (0x20, make_search_barba(head_20_open, 0)),
        ):
            for tr in range(4):
                for tc in range(4):
                    sub = [frame_rows[tr * 8 + y][tc * 8:(tc + 1) * 8] for y in range(8)]
                    put_1k_tile(196, base_tid + tr * 4 + tc, sub)

        fireball_frames = [
            [
                '00111100',
                '01222110',
                '12332210',
                '12333211',
                '12232210',
                '01222110',
                '00111100',
                '00000000',
            ],
            [
                '00110100',
                '01221100',
                '12322210',
                '12333210',
                '12332211',
                '01222110',
                '00111000',
                '00000000',
            ],
            [
                '00111000',
                '01222100',
                '12233210',
                '12333210',
                '12232210',
                '01122110',
                '00111100',
                '00000000',
            ],
            [
                '00011100',
                '01122210',
                '12233210',
                '12332210',
                '01232210',
                '01221100',
                '00111000',
                '00000000',
            ],
        ]
        fizzle_frames = [
            [
                '01000010',
                '00211200',
                '01233210',
                '10322301',
                '01233210',
                '00211200',
                '01000010',
                '00000000',
            ],
            [
                '10000001',
                '00100100',
                '00022000',
                '01200210',
                '00022000',
                '00100100',
                '10000001',
                '00000000',
            ],
        ]
        for idx, frows in enumerate(fireball_frames):
            put_1k_tile(196, 0x30 + idx, frows)
        for idx, zrows in enumerate(fizzle_frames):
            put_1k_tile(196, 0x34 + idx, zrows)

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
        title_start_roar = bytes.fromhex('4c 60 df')  # JMP $DF60 (TitleStartRoarSeq)
        # $DF60: Title Screen Start roar + horizontal screen shake (~1.57s) + brief stabilization (0.3s) before fade-out
        # Shakes X ($04 + T tip OAM X) only so $03 (Y) stays 0 and Sprite-0 CHR split at y=128 never glitches.
        title_start_roar_seq = bytes([
            0x20, 0x00, 0xC9,                   # JSR $C900 (play sampled roar)
            0xA9, 0x00, 0x85, 0x02,             # LDA #$00; STA $02 (reset frame counter)
            # roar_loop (44 bytes):
            0xA5, 0x02,                         # LDA $02
            0xC5, 0x02, 0xF0, 0xFC,             # wait_nmi: CMP $02; BEQ wait_nmi
            0xA5, 0x02, 0x29, 0x03, 0xAA,       # LDA $02; AND #$03; TAX
            0xBD, 0xE1, 0xC9, 0x85, 0x04,       # LDA $C9E1,X; STA $04 (BG scroll X)
            0x38, 0xA9, 0x4E, 0xFD, 0xE1, 0xC9, # SEC; LDA #$4E; SBC $C9E1,X
            0x8D, 0x2F, 0x07,                   # STA $072F (T tip left X)
            0x38, 0xA9, 0x56, 0xFD, 0xE1, 0xC9, # SEC; LDA #$56; SBC $C9E1,X
            0x8D, 0x33, 0x07,                   # STA $0733 (T tip right X)
            0xA9, 0x40, 0x85, 0x05,             # LDA #$40; STA $05 (OAM DMA)
            0xA5, 0x02, 0xC9, 0x5E, 0x90, 0xD4, # LDA $02; CMP #94; BCC roar_loop (-44)
            # restore scroll X & T tip OAM X
            0xA9, 0x00, 0x85, 0x04,             # LDA #$00; STA $04
            0xA9, 0x4E, 0x8D, 0x2F, 0x07,
            0xA9, 0x56, 0x8D, 0x33, 0x07,
            0xA9, 0x40, 0x85, 0x05,             # LDA #$40; STA $05 (OAM DMA)
            0xA9, 0x00, 0x85, 0x02,             # LDA #$00; STA $02
            # stab_loop: brief ~0.3s (18 frames) stabilization before difficulty screen
            0xA5, 0x02, 0xC9, 0x12, 0x90, 0xFA, # LDA $02; CMP #18; BCC stab_loop
            0x4C, 0xED, 0xE5,                   # JMP $E5ED
        ])
        assert len(title_start_roar_seq) <= 0x60, f'title_start_roar_seq too large: {len(title_start_roar_seq)}'
        # $C970 (113 bytes): Moon ending sequence: draw final pos, pause 1s, head-up roar + dim music + screen shake (~1.67s), restore + 1.5s
        moon_roar_seq = bytes.fromhex(
            '20 be bf '                         # JSR $BFBE (draw 13 sprites at final ($26, $27))
            'a9 20 85 05 '                      # trigger OAM DMA
            'a9 00 85 02 a5 02 c9 3c 90 fa '    # wait 60 frames (1s)
            'a9 99 20 ee bf a9 20 85 05 '       # swap OAM #56..#63 -> $99..$A7 (roar head) + OAM DMA
            '20 00 c9 '                         # JSR $C900 (play sampled roar)
            'a5 04 85 08 a5 03 85 09 '          # save base scroll ($04->$08, $03->$09)
            'a0 64 '                            # LDY #100 (~1.67s matching ROAR_LENGTH=136)
            # roar_loop: wait 1 NMI, dim BG music, shake scroll ($04/$03)
            'a5 02 c5 02 f0 fc '                # wait for $02 to increment
            'a9 32 8d 00 40 8d 04 40 '          # dim Pulse 1 & 2 to constant vol 2
            'a9 00 8d 08 40 8d 0c 40 '          # mute Triangle & Noise so roar dominates
            'a5 02 29 03 aa '                   # X = $02 & 3
            'a5 08 18 7d e1 c9 85 04 '          # $04 = base_x + shake_x[X]
            'a5 09 18 7d e5 c9 85 03 '          # $03 = base_y + shake_y[X]
            '88 d0 d2 '                         # DEY; BNE roar_loop (-46)
            'a5 08 85 04 a5 09 85 03 '          # restore base scroll
            'a9 81 20 ee bf a9 20 85 05 '       # restore OAM #56..#63 -> $81..$8F + OAM DMA
            'a9 00 85 02 a5 02 c9 5a 90 fa '    # wait 90 frames (1.5s)
            '60'                                # RTS
        )
        shake_xy = bytes([0, 3, 1, 2, 0, 2, 3, 1])  # $C9E1: shake_x[4], $C9E5: shake_y[4]
        # $DFC0 (36 bytes): 12-sprite Moon OAM tables (#56..#63, #11, #19, #27, #35)
        moon_oam_tables_12 = bytes([
            0xE0, 0xE4, 0xE8, 0xEC, 0xF0, 0xF4, 0xF8, 0xFC, 0x2C, 0x4C, 0x6C, 0x8C,
            12, 20, 28, 36, 12, 20, 28, 36, 0, 8, 16, 24,
            0xE6, 0xE6, 0xE6, 0xE6, 0xF6, 0xF6, 0xF6, 0xF6, 0x06, 0x06, 0x06, 0x06,
        ])

        assert len(moon_roar_seq) == 113
        assert 0x970 + len(moon_roar_seq) + len(shake_xy) <= 0x9FC
        prg_256[0x20900:0x20900 + len(play_roar)] = play_roar
        prg_256[0x20930:0x20930 + len(nmi_dmc_check)] = nmi_dmc_check
        prg_256[0x20950:0x20950 + len(found_barba_roar)] = found_barba_roar
        prg_256[0x2096A:0x2096A + len(title_start_roar)] = title_start_roar
        prg_256[0x20970:0x20970 + len(moon_roar_seq)] = moon_roar_seq
        prg_256[0x209E1:0x209E1 + len(shake_xy)] = shake_xy
        prg_256[0x21F60:0x21F60 + len(title_start_roar_seq)] = title_start_roar_seq
        prg_256[0x21FC0:0x21FC0 + len(moon_oam_tables_12)] = moon_oam_tables_12

        # Bank 31 ($E000-$FFFF at 0x3E000): RESET sets R6=16 (in $FFE0-$FFF9 tail padding), plus NMI/level/ending hooks
        put(prg_256, 0x3E03B, bytes.fromhex('20 e0 ff ea ea ea ea ea ea ea'),
            expected=bytes.fromhex('a9 47 8d 00 80 a9 52 8d 01 80'))
        put(prg_256, 0x3FFE0, bytes.fromhex('a9 46 8d 00 80 a9 10 8d 01 80 a9 47 8d 00 80 a9 52 8d 01 80 60'),
            expected=bytes(21))
        put(prg_256, 0x3FA13, bytes.fromhex('20 30 c9'), expected=bytes.fromhex('ad f6 03'))
        put(prg_256, 0x3EBC8, bytes.fromhex('20 50 c9 ea ea ea'), expected=bytes.fromhex('90 04 a0 6c a9 ea'))
        # 1KB CHR Bank 198 ($C6): Title Screen Stamp Barba sprite tiles ($00..$05 = 24x16 head, $06..$09 = 12x16 neck)
        for tr in range(2):
            for tc in range(3):
                sub = [stamp_head[tr * 8 + y][tc * 8:(tc + 1) * 8] for y in range(8)]
                put_1k_tile(198, tr * 3 + tc, sub)
        neck_pad = [row + '0000' for row in stamp_neck]
        for tr in range(2):
            for tc in range(2):
                sub = [neck_pad[tr * 8 + y][tc * 8:(tc + 1) * 8] for y in range(8)]
                put_1k_tile(198, 6 + tr * 2 + tc, sub)
        if t_tip_grid is not None:
            for tc in range(2):
                sub = [''.join(str(t_tip_grid[y][tc * 8 + x]) for x in range(8)) for y in range(8)]
                put_1k_tile(198, 10 + tc, sub)

        # $CC60 (clear of $C9FC..$CC5F used by pack_waldo.py): TitleStampInit
        title_stamp_init = bytes([
            0x2C, 0x02, 0x20,                   # BIT $2002
            0xA9, 0x3F, 0x8D, 0x06, 0x20,       # LDA #$3F; STA $2006
            0xA9, 0x11, 0x8D, 0x06, 0x20,       # LDA #$11; STA $2006
            0xA9, 0x16, 0x8D, 0x07, 0x20,       # LDA #$16; STA $2007 (Pal 0: red-orange)
            0xA9, 0x27, 0x8D, 0x07, 0x20,       # LDA #$27; STA $2007 (Pal 0: light orange)
            0xA9, 0x38, 0x8D, 0x07, 0x20,       # LDA #$38; STA $2007 (Pal 0: ivory/white)
            0xA9, 0x20, 0x8D, 0x07, 0x20,       # LDA #$20; STA $2007 ($3F14)
            0xA9, 0x12, 0x8D, 0x07, 0x20,       # LDA #$12; STA $2007 (Pal 1: blue)
            0xA9, 0x0E, 0x8D, 0x07, 0x20,       # LDA #$0E; STA $2007 (Pal 1: black)
            0xA9, 0x00, 0x8D, 0x07, 0x20,       # LDA #$00; STA $2007 (Pal 1: grey)
            0xA9, 0x42, 0x8D, 0x00, 0x80,       # LDA #$42; STA $8000 (keep PRG mode 1 bit 6!)
            0xA9, 0xC6, 0x8D, 0x01, 0x80,       # LDA #$C6; STA $8001
            0xA2, 0x2F,                         # LDX #$2F (48 bytes - 1)
            0xBD, 0xB2, 0xCC,                   # LDA $CCB2,X (title_stamp_oam)
            0x9D, 0x04, 0x07,                   # STA $0704,X
            0xCA, 0x10, 0xF7,                   # DEX; BPL -9
            0xA9, 0x40, 0x85, 0x05,             # LDA #$40; STA $05 (OAM DMA $0700)
            0xA5, 0x05, 0xD0, 0xFC,             # wait for NMI OAM DMA
            0xA2, 0x03, 0xA9, 0xA3, 0x60,       # LDX #$03; LDA #$A3; RTS
        ])
        # $CCB2 (48 bytes): OAM[1..10] stamp + OAM[11..12] 'T' bottom tip (y=160, Pal 1, front of BG)
        title_stamp_oam = bytes([
            0x26, 0x00, 0x20, 0xB9,  0x26, 0x01, 0x20, 0xC1,  0x26, 0x02, 0x20, 0xC9,
            0x2E, 0x03, 0x20, 0xB9,  0x2E, 0x04, 0x20, 0xC1,  0x2E, 0x05, 0x20, 0xC9,
            0x34, 0x06, 0x20, 0xC3,  0x34, 0x07, 0x20, 0xCB,
            0x3C, 0x08, 0x20, 0xC3,  0x3C, 0x09, 0x20, 0xCB,
            0x9F, 0x0A, 0x01, 0x4E,  0x9F, 0x0B, 0x01, 0x56,
        ])
        assert len(title_stamp_init) == 0x52
        prg_256[0x20C60:0x20C60 + len(title_stamp_init)] = title_stamp_init
        prg_256[0x20CB2:0x20CB2 + len(title_stamp_oam)] = title_stamp_oam
        # Bank 3 ($A021): init Title Screen Barba stamp sprite overlay & palette before fade-in
        put(prg_256, 0x06021, bytes.fromhex('20 60 cc ea'), expected=bytes.fromhex('a2 03 a9 a3'))
        # Bank 3 ($A03C): Title Screen Start roar
        put(prg_256, 0x0603C, bytes.fromhex('20 6a c9'), expected=bytes.fromhex('20 ed e5'))

        # Bank 16 ($CD00 at 0x20D00): Search-level crowd fleeing from Barba
        crowd_code, crowd_labels = make_crowd_flee_code(0xCD00)
        assert len(crowd_code) <= 0x1260, f'crowd_code too large: {len(crowd_code)}'
        prg_256[0x20D00:0x20D00 + len(crowd_code)] = crowd_code

        def jsr(name: str) -> bytes:
            a = crowd_labels[name]
            return bytes([0x20, a & 0xFF, a >> 8])

        def jmp(name: str) -> bytes:
            a = crowd_labels[name]
            return bytes([0x4C, a & 0xFF, a >> 8])

        put(prg_256, 0x3E304, jmp('CrowdNmiFlush'), expected=bytes.fromhex('4c 74 e3'))
        put(prg_256, 0x3EBFE, jsr('CrowdExit'), expected=bytes.fromhex('20 ec e4'))
        put(prg_256, 0x3EC1D, jsr('CrowdPrep'), expected=bytes.fromhex('20 58 f3'))
        put(prg_256, 0x3EC75, jsr('CrowdActivate'), expected=bytes.fromhex('20 57 e5'))
        put(prg_256, 0x3ED0D, jsr('CrowdStep') + b'\xea', expected=bytes.fromhex('a5 12 05 13'))
        put(prg_256, 0x3EE28, jsr('CrowdInit'), expected=bytes.fromhex('bd d1 f3'))
        put(prg_256, 0x3EF65, jsr('CrowdSaveBg') + b'\xea', expected=bytes.fromhex('a9 c0 85 22'))
        put(prg_256, 0x3F1AC, jsr('CrowdStampCheck'), expected=bytes.fromhex('20 bf e4'))

        out = hdr + prg_256 + chr_256

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_bytes(out)
    PLAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAY_PATH.write_bytes(out)
    print(f'Wrote {OUT_PATH} and {PLAY_PATH} ({len(out)} bytes)')
    return OUT_PATH


if __name__ == '__main__':
    build()
