"""PRG Bank 1 + fixed-bank MMC3/roar/boss patches for Super Barba Bros."""
from __future__ import annotations

from pathlib import Path

import roar_sample
from smb_art import (
    CHR_R0_BARBA,
    CHR_R0_INFERNO,
    CHR_R0_ROAR,
    CHR_R0_WYRMLING,
    CHR_R0_WYRMLING_ROAR,
    CHR_R1_CASTLE,
    CHR_R1_ENEMIES,
    CHR_R2_WORLD_A,
    CHR_R2_WORLD_B,
    CHR_R3_CASTLE_A,
    CHR_R3_CASTLE_B,
    CHR_R3_WORLD,
)


class Asm6502:
    """Minimal 6502 assembler with labels and relative/absolute fixups."""

    def __init__(self, base: int) -> None:
        self.base = base
        self.buf = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[str, int, str]] = []

    def emit(self, *bs: int) -> None:
        self.buf.extend(bs)

    def label(self, name: str) -> None:
        self.labels[name] = self.base + len(self.buf)

    def branch(self, op: int, target: str) -> None:
        self.emit(op, 0)
        self.fixups.append(('rel', len(self.buf) - 1, target))

    def abs_ref(self, op: int, target: str) -> None:
        self.emit(op, 0, 0)
        self.fixups.append(('abs', len(self.buf) - 2, target))

    def finish(self) -> bytes:
        for kind, pos, target in self.fixups:
            addr = self.labels[target]
            if kind == 'rel':
                rel = addr - (self.base + pos + 1)
                assert -128 <= rel <= 127, f'Branch out of range to {target}: {rel}'
                self.buf[pos] = rel & 0xFF
            else:
                self.buf[pos] = addr & 0xFF
                self.buf[pos + 1] = (addr >> 8) & 0xFF
        return bytes(self.buf)


# WRAM Bank 3 runtime state ($7C00-$7C1F)
W_ROAR_TIMER = 0x7C00
W_CUR_R6     = 0x7C01
W_FIRE_TIMER = 0x7C02
W_BOSS_FLASH = 0x7C03
W_MMC3_SEL   = 0x7C04
W_SHAKE_TIMER = 0x7C05
W_B1_IDX     = 0x7C08
W_SAVE_A     = 0x7C09
W_SAVE_X     = 0x7C0A
W_B1_PTR_LO  = 0x7C0B
W_B1_PTR_HI  = 0x7C0C
W_NMI_SAVED_R6 = 0x7C0D
W_VL_ROW     = 0x7C0E
W_EXTRA_ACTIVE = 0x7C10
W_EXTRA_X      = 0x7C11
W_EXTRA_Y      = 0x7C12
W_EXTRA_DIR    = 0x7C13
W_EXTRA_ATTR   = 0x7C14
W_EXTRA_HEAD   = 0x7C15
W_EXTRA_CROUCH = 0x7C16
W_EXTRA_OFFS   = 0x7C17
W_OAM_SCAN     = 0x7C18
W_EX_Y0        = 0x7C19
W_EX_Y1        = 0x7C1A
W_EX_FLIP      = 0x7C1B

# Fixed WRAM trampolines ($7A00-$7AFF in guest WRAM bank 3)
SMB_CALL_BANK1 = 0x7A00
SMB_NMI_EXIT   = 0x7A80

# Fixed-bank DMC & stub placement ($E6BE-$F129 inside Bank 31)
STUB_BASE    = 0xE6BE  # 14 stubs * 8B = 112B ($E6BE-$E72D)
DMC_ADDR     = 0xE740
DMC_LIMIT    = 0xEFC4
FIXED_HELPER = 0xEFC4  # $EFC4-$F129 (358B)

# Relocated SMB1 graphics block ($E6BE-$F129 -> $8100-$8B6B in Bank 1)
RELOC_SRC_START = 0xE6BE
RELOC_SRC_END   = 0xF12A
RELOC_DST_START = 0x8100
RELOC_DELTA     = RELOC_DST_START - RELOC_SRC_START

# Exact data-only subranges inside $E6BE-$F129 (excluded from instruction decoding)
_DATA_RANGES = (
    (0xE6BE, 0xE6D2),
    (0xE73E, 0xE87D),
    (0xEBCD, 0xEBD1),
    (0xED06, 0xED09),
    (0xEE07, 0xEEE9),
    (0xEF9E, 0xEFA4),
    (0xF09C, 0xF0B0),
)

_OP_LEN = {
    0x00: 1, 0x01: 2, 0x05: 2, 0x06: 2, 0x08: 1, 0x09: 2, 0x0A: 1, 0x0D: 3, 0x0E: 3,
    0x10: 2, 0x11: 2, 0x15: 2, 0x16: 2, 0x18: 1, 0x19: 3, 0x1D: 3, 0x1E: 3,
    0x20: 3, 0x21: 2, 0x24: 2, 0x25: 2, 0x26: 2, 0x28: 1, 0x29: 2, 0x2A: 1, 0x2C: 3, 0x2D: 3, 0x2E: 3,
    0x30: 2, 0x31: 2, 0x35: 2, 0x36: 2, 0x38: 1, 0x39: 3, 0x3D: 3, 0x3E: 3,
    0x40: 1, 0x41: 2, 0x45: 2, 0x46: 2, 0x48: 1, 0x49: 2, 0x4A: 1, 0x4C: 3, 0x4D: 3, 0x4E: 3,
    0x50: 2, 0x51: 2, 0x55: 2, 0x56: 2, 0x58: 1, 0x59: 3, 0x5D: 3, 0x5E: 3,
    0x60: 1, 0x61: 2, 0x65: 2, 0x66: 2, 0x68: 1, 0x69: 2, 0x6A: 1, 0x6C: 3, 0x6D: 3, 0x6E: 3,
    0x70: 2, 0x71: 2, 0x75: 0x02, 0x76: 2, 0x78: 1, 0x79: 3, 0x7D: 3, 0x7E: 3,
    0x81: 2, 0x84: 2, 0x85: 2, 0x86: 2, 0x88: 1, 0x8A: 1, 0x8C: 3, 0x8D: 3, 0x8E: 3,
    0x90: 2, 0x91: 2, 0x94: 2, 0x95: 2, 0x96: 2, 0x98: 1, 0x99: 3, 0x9A: 1, 0x9D: 3,
    0xA0: 2, 0xA1: 2, 0xA2: 2, 0xA4: 2, 0xA5: 2, 0xA6: 2, 0xA8: 1, 0xA9: 2, 0xAA: 1, 0xAC: 3, 0xAD: 3, 0xAE: 3,
    0xB0: 2, 0xB1: 2, 0xB4: 2, 0xB5: 2, 0xB6: 2, 0xB8: 1, 0xB9: 3, 0xBA: 1, 0xBC: 3, 0xBD: 3, 0xBE: 3,
    0xC0: 2, 0xC1: 2, 0xC4: 2, 0xC5: 2, 0xC6: 2, 0xC8: 1, 0xC9: 2, 0xCA: 1, 0xCC: 3, 0xCD: 3, 0xCE: 3,
    0xD0: 2, 0xD1: 2, 0xD5: 2, 0xD6: 2, 0xD8: 1, 0xD9: 3, 0xDD: 3, 0xDE: 3,
    0xE0: 2, 0xE1: 2, 0xE4: 2, 0xE5: 2, 0xE6: 2, 0xE8: 1, 0xE9: 2, 0xEA: 1, 0xEC: 3, 0xED: 3, 0xEE: 3,
    0xF0: 2, 0xF1: 2, 0xF5: 2, 0xF6: 2, 0xF8: 1, 0xF9: 3, 0xFD: 3, 0xFE: 3,
}


def _in_data(addr: int) -> bool:
    return any(lo <= addr < hi for lo, hi in _DATA_RANGES)


def _relocate_gfx_block(orig_prg: bytes) -> bytearray:
    """Relocate SMB1 $E6BE-$F129 to $8100-$8B6B, updating all internal 16-bit references."""
    block = bytearray(orig_prg[RELOC_SRC_START - 0x8000 : RELOC_SRC_END - 0x8000])
    pc = RELOC_SRC_START
    while pc < RELOC_SRC_END:
        if _in_data(pc):
            pc += 1
            continue
        off = pc - RELOC_SRC_START
        op = block[off]
        ln = _OP_LEN[op]
        if ln == 3:
            tgt = block[off + 1] | (block[off + 2] << 8)
            if RELOC_SRC_START <= tgt < RELOC_SRC_END:
                new_tgt = (tgt + RELOC_DELTA) & 0xFFFF
                block[off + 1] = new_tgt & 0xFF
                block[off + 2] = new_tgt >> 8
        pc += ln
    return block


def build_bank1(orig_prg: bytes) -> bytes:
    """Assemble PRG Bank 1 ($8000-$9FFF): relocated & Z2-upgraded graphics, boss & cast handlers."""
    bank1 = bytearray(b'\xFF' * 8192)
    reloc = _relocate_gfx_block(orig_prg)

    def r_off(orig_addr: int) -> int:
        return orig_addr - RELOC_SRC_START

    def r_addr(orig_addr: int) -> int:
        return orig_addr + RELOC_DELTA

    # 1. Patch relocated EnemyGfx data tables for Z2 Cast:
    #    - Stalfos (idx 00, 04, 09, 0E, 10): $A0..$AB
    reloc[r_off(0xE74A) : r_off(0xE756)] = bytes([
        0xFC, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4,  # Stalfos walk1 ($0C)
        0xFC, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA,  # Stalfos walk2 ($12) -> bottom uses A4/A5, A8/A9/AA/AB!
    ])
    # Better: use full 6-tile Stalfos walk1 ($A0..$A5) and walk2 ($A6..$AB):
    reloc[r_off(0xE74A) : r_off(0xE756)] = bytes([
        0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5,
        0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xAB,
    ])
    #    - Paratroopa (idx 09, 0E, 10 -> $E756): Stalfos + wings
    reloc[r_off(0xE756) : r_off(0xE762)] = bytes([
        0x69, 0xA1, 0x6A, 0xA3, 0xA4, 0xA5,
        0x6B, 0xA7, 0x6C, 0xA9, 0xAA, 0xAB,
    ])
    #    - Geldarm (idx 0D Piranha Plant -> $E7FE): $90..$93,$9E..$9F / $BC..$BF,$E5..$E6
    reloc[r_off(0xE7FE) : r_off(0xE80A)] = bytes([
        0x90, 0x91, 0x92, 0x93, 0x9E, 0x9F,
        0xBC, 0xBD, 0xBE, 0xBF, 0xE5, 0xE6,
    ])
    #    - Wizzrobe (idx 11 Lakitu -> $E7CE): $B0..$B5 (hover) / $B6..$BB (cast)
    reloc[r_off(0xE7CE) : r_off(0xE7DA)] = bytes([
        0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5,
        0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xBB,
    ])
    #    - Skip $EAD7 right-column mirror on Geldarm ($EF == $0D) and Bubble ($EF == $12)
    assert reloc[r_off(0xEABA) : r_off(0xEACA)] == bytes.fromhex('c9 0d f0 19 c9 0c f0 15 c9 12 d0 04 e0 05 d0 48')
    reloc[r_off(0xEABA) : r_off(0xEABE)] = bytes([0xEA, 0xEA, 0xEA, 0xEA])
    reloc[r_off(0xEAC2) : r_off(0xEACA)] = bytes([0xC9, 0x12, 0xF0, 0x4C, 0xEA, 0xEA, 0xEA, 0xEA])
    #    - Skip $EB14 Lakitu cloud bottom-row mirror for Wizzrobe ($EF == $11)
    assert reloc[r_off(0xEB12) : r_off(0xEB16)] == bytes.fromhex('a5 ef c9 11')
    reloc[r_off(0xEB15)] = 0xFF
    #    - Spiny Egg ($E76E/$E774 = off $30/$36) -> upright 16x16 flaming Bubble skull ($96..$9D)
    reloc[r_off(0xE76E) : r_off(0xE77A)] = bytes([
        0xFC, 0xFC, 0x96, 0x97, 0x98, 0x99,
        0xFC, 0xFC, 0x9A, 0x9B, 0x9C, 0x9D,
    ])

    # 2. Patch relocated PlayerGfxTbl for Wyrmling & Super/Inferno Barba:
    #    - Big stand ($EE09 = $C8 -> $18) and grow intermediates ($EED7..$EEE6)
    assert reloc[r_off(0xEE09)] == 0xC8
    reloc[r_off(0xEE09)] = 0x18
    assert reloc[r_off(0xEED7) : r_off(0xEEE7)] == bytes.fromhex(
        'fc fc 00 01 4c 4d 4e 4e '
        '00 01 4c 4d 4a 4a 4b 4b'
    )
    reloc[r_off(0xEED7) : r_off(0xEEE7)] = bytes([
        0xFC, 0xFC, 0x18, 0x19, 0x4C, 0x4D, 0x4A, 0x4B,
        0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F,
    ])
    #    - Big crouch (pose 10 at $EE67): FC FC FC FC 50 51 52 53 (preserves $5B castle girder)
    assert reloc[r_off(0xEE67) : r_off(0xEE6F)] == bytes.fromhex('fc fc 08 09 58 59 5a 5a')
    reloc[r_off(0xEE67) : r_off(0xEE6F)] = bytes([0xFC, 0xFC, 0xFC, 0xFC, 0x50, 0x51, 0x52, 0x53])
    #    - Big fire throw (pose 11 at $EE6F): 38 39 3A 3B 3C 3D 3E 3F
    assert reloc[r_off(0xEE6F) : r_off(0xEE77)] == bytes.fromhex('08 09 28 29 2a 2b 0e 0f')
    reloc[r_off(0xEE6F) : r_off(0xEE77)] = bytes([0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F])
    #    - Small climb1/2 ($EEB7..$EEC6) & die ($EEC7..$EECE): use $50..$57 inside R0
    assert reloc[r_off(0xEEB7) : r_off(0xEECF)] == bytes.fromhex(
        'fc fc fc fc 32 33 90 91 '
        'fc fc fc fc 3a 37 92 93 '
        'fc fc fc fc 9e 9e 9f 9f'
    )
    reloc[r_off(0xEEB7) : r_off(0xEECF)] = bytes([
        0xFC, 0xFC, 0xFC, 0xFC, 0x32, 0x33, 0x50, 0x51,
        0xFC, 0xFC, 0xFC, 0xFC, 0x3A, 0x37, 0x52, 0x53,
        0xFC, 0xFC, 0xFC, 0xFC, 0x54, 0x55, 0x56, 0x57,
    ])
    #    - Small stand ($EECF..$EED6): use crisp stand pose $32 $33 $34 $35 (not $3A $37 $4F $4F)
    assert reloc[r_off(0xEECF) : r_off(0xEED7)] == bytes.fromhex('fc fc fc fc 3a 37 4f 4f')
    reloc[r_off(0xEECF) : r_off(0xEED7)] = bytes([0xFC, 0xFC, 0xFC, 0xFC, 0x32, 0x33, 0x34, 0x35])
    #    - Small walk2 ($EE87..$EE8E): use $46 for top-right so 16x16 overworld step frame bobs cleanly
    assert reloc[r_off(0xEE87) : r_off(0xEE8F)] == bytes.fromhex('fc fc fc fc 3a 37 3b 3c')
    reloc[r_off(0xEE8C)] = 0x46
    #    - Skip $EFB5 bottom-left H-flip in DrawTitleMario so lives remaining screen keeps unflipped Small Barba
    assert reloc[r_off(0xEFB5) : r_off(0xEFBE)] == bytes.fromhex('ad 26 02 09 40 8d 22 02 60')
    reloc[r_off(0xEFB5)] = 0x60  # RTS
    #    - Skip $F0E9 mirror-flip pass (crouch, climb, death now have dedicated unmirrored left/right tiles)
    reloc[r_off(0xF0E9)] = 0x60  # RTS

    # 3. Assemble custom Bank 1 routines at $8C00+
    CUSTOM_BASE = 0x8C00
    a = Asm6502(CUSTOM_BASE)

    # 3a. Red/Blue/Throwing Ironknuckle & Stalfos shell hooks inside EnemyGfxHandler
    # Hooked from $E92A (LDA $E840,Y; TAX) -> JSR EnemyTileOverride
    a.label('EnemyTileOverride')
    # Input: $EF = enemy gfx index, $EC = frame/state; Output: X = tile-table offset, $EC, $04
    a.emit(0xA4, 0xEF)                            # LDY $EF
    a.emit(0xC0, 0x01)                            # CPY #$01 (Red Koopa -> Red Ironknuckle)
    a.branch(0xF0, 'ironknuckle')
    a.emit(0xC0, 0x03)                            # CPY #$03 (Red Koopa 2 -> Red Ironknuckle)
    a.branch(0xF0, 'ironknuckle')
    a.emit(0xC0, 0x0F)                            # CPY #$0F (Red Paratroopa -> Red Ironknuckle)
    a.branch(0xF0, 'ironknuckle')
    a.emit(0xC0, 0x02)                            # CPY #$02 (Buzzy Beetle -> Dark Ironknuckle)
    a.branch(0xF0, 'ironknuckle')
    a.emit(0xC0, 0x05)                            # CPY #$05 (Hammer Bro -> Throwing Ironknuckle)
    a.branch(0xF0, 'ironknuckle')
    a.emit(0xB9, (0xE840 + RELOC_DELTA) & 0xFF, (0xE840 + RELOC_DELTA) >> 8)
    a.emit(0xAA, 0x60)                            # TAX; RTS
    a.label('ironknuckle')
    # Check if shelled ($EC == 4 -> $AC/$CC) or walking
    a.emit(0xA6, 0xEC, 0xE0, 0x04)                # LDX $EC; CPX #$04
    a.branch(0xF0, 'ik_shell')
    a.emit(0xA2, 0xA8)                            # X = $A8 (Ironknuckle walk1/walk2 in $E7E6)
    a.emit(0x60)
    a.label('ik_shell')
    a.emit(0xA2, 0x00)                            # X = $00 (Ironknuckle helmet/shield shell in $E73E)
    a.emit(0x60)

    # 3b. Patch shell X=$72 -> Stalfos skull shell ($06) vs Ironknuckle ($00) vs Bloober/other
    a.label('ShellTileOverride')
    # Replaces $E9AC: LDX #$72; INC $02 -> JSR ShellTileOverride
    a.emit(0xA5, 0xEF)                            # LDA $EF
    a.emit(0xC9, 0x01); a.branch(0xF0, 'sh_ik')
    a.emit(0xC9, 0x02); a.branch(0xF0, 'sh_ik')
    a.emit(0xC9, 0x03); a.branch(0xF0, 'sh_ik')
    a.emit(0xC9, 0x05); a.branch(0xF0, 'sh_ik')
    a.emit(0xA2, 0x06)                            # Stalfos skull shell ($06)
    a.emit(0xE6, 0x02, 0x60)                      # INC $02; RTS
    a.label('sh_ik')
    a.emit(0xA2, 0x00)                            # Ironknuckle shell ($00)
    a.emit(0xE6, 0x02, 0x60)                      # INC $02; RTS

    # 3c. Villainous Link Renderer (replaces Bowser $036A == 1/2 at $E930)
    # Preserves original flow: sets X (offset into $E73E? Or sets $0200 OAM directly via $EA4B?)
    # Even simpler: put Villainous Link's 6 tile layouts into $E73E? No, $EA4B uses $EBAA -> $E73E + X (8-bit X).
    # Instead, Villainous Link writes $0200-$0217 via $F282 directly (10 lines of ASM!) and jumps to $EA56!
    a.label('DrawVillainousLink')
    # $036A is 1 (front half) or 2 (back half). $08 = enemy slot. $EB = OAM offset.
    # Boss flash: if W_BOSS_FLASH != 0 and ($09 & 2) != 0, use pal 2 ($02), else pal 1 ($01).
    a.emit(0xA9, 0x01)
    a.emit(0xAE, W_BOSS_FLASH & 0xFF, W_BOSS_FLASH >> 8)
    a.branch(0xF0, 'vl_pal_ok')
    a.emit(0xA5, 0x09, 0x29, 0x02)
    a.branch(0xF0, 'vl_pal_ok')
    a.emit(0xA9, 0x02)
    a.label('vl_pal_ok')
    a.emit(0x85, 0x04)                            # $04 = sprite palette (1 or 2)
    # Choose pose index 0 (idle), 6 (walk2), 12 (attack)
    a.emit(0xA2, 0x00)                            # pose = 0 (idle)
    a.emit(0xAD, 0x63, 0x03)                      # LDA $0363
    a.branch(0x10, 'vl_chk_walk')                 # BPL chk_walk
    a.emit(0xA2, 12)                              # pose = 12 (attack: sword raised!)
    a.branch(0xD0, 'vl_pose_ok')
    a.label('vl_chk_walk')
    a.emit(0xA5, 0x09, 0x29, 0x08)
    a.branch(0xF0, 'vl_pose_ok')
    a.emit(0xA2, 6)                               # pose = 6 (walk2)
    a.label('vl_pose_ok')
    a.emit(0xAD, 0x6A, 0x03, 0xC9, 0x01)          # LDA $036A; CMP #$01
    a.branch(0xF0, 'vl_front')
    # Back half ($036A == 2): +18 into table
    a.emit(0x8A, 0x18, 0x69, 18, 0xAA)
    a.label('vl_front')
    # If $ED & $20 (flipped/defeated falling), set $0109 = 1
    a.emit(0xA5, 0xED, 0x29, 0x20)
    a.branch(0xF0, 'vl_draw')
    a.emit(0x8E, 0x09, 0x01)
    a.label('vl_draw')
    # Force $03 = 1 (unflipped) because Villainous Link's front (sword) & back (cape) are pre-oriented left
    a.emit(0xA9, 0x01, 0x85, 0x03)
    # Draw 3 rows of 2 tiles using $F282 ($00=left, $01=right, $02=Y, $03=dir, $04=attr, $05=X)
    a.emit(0xA4, 0xEB)                            # LDY $EB (OAM offset)
    a.emit(0xA9, 0x03, 0x8D, W_VL_ROW & 0xFF, W_VL_ROW >> 8)  # loop 3 rows using W_VL_ROW ($7C0E)
    a.label('vl_row')
    a.abs_ref(0xBD, 'VLinkTiles')
    a.emit(0x85, 0x00)
    a.abs_ref(0xBD, 'VLinkTilesPlus1')
    a.emit(0x85, 0x01)
    a.emit(0x8E, W_SAVE_X & 0xFF, W_SAVE_X >> 8)
    a.emit(0x20, 0x82, 0xF2)                      # JSR $F282 (draws 2 tiles, advances Y+=8, $02+=8)
    a.emit(0xAE, W_SAVE_X & 0xFF, W_SAVE_X >> 8)
    a.emit(0xE8, 0xE8)                            # INX; INX
    a.emit(0xCE, W_VL_ROW & 0xFF, W_VL_ROW >> 8)
    a.branch(0xD0, 'vl_row')
    # Jump back into EnemyGfxHandler at $EA56 (handles $0109 V-flip + offscreen clipping!)
    a.emit(0x4C, (0xEA56 + RELOC_DELTA) & 0xFF, (0xEA56 + RELOC_DELTA) >> 8)

    a.label('VLinkTiles')
    # 0..17: Front half (idle, walk2, attack)
    a.emit(0xBF, 0xC0, 0xC1, 0xC2, 0xC3, 0xC4)
    a.emit(0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5)
    a.emit(0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xBB)
    # 18..35: Back half (idle, walk2, attack)
    a.emit(0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA)
    a.emit(0x90, 0x91, 0x92, 0x93, 0x94, 0x95)
    a.emit(0x96, 0x97, 0x98, 0x99, 0x9A, 0x9B)
    a.labels['VLinkTilesPlus1'] = a.labels['VLinkTiles'] + 1

    # 3d. Captive Sprite Selector ($35 Toad/Fairy/Zelda) hooked at $EA0E
    # Replaces $EA0E..$EA21 inside EnemyGfxHandler
    a.label('CaptiveOverride')
    a.emit(0xC9, 0x15)                            # CMP #$15 (retainer?)
    a.branch(0xD0, 'cap_norm')
    a.emit(0xAD, 0x5F, 0x07)                      # LDA $075F (WorldNumber)
    a.emit(0xC9, 0x07)
    a.branch(0xB0, 'cap_zelda')                   # World 8 -> Caged Zelda!
    a.emit(0x29, 0x01)
    a.branch(0xD0, 'cap_toad')                    # Odd/even worlds: 1,3,5,7 (0,2,4,6) -> Fairy; 2,4,6 -> Toad
    # Caged Fairy (flapping wings every 8 frames): $00..$05 in $E7D4? Use $5A / $60? Put at $18/$1E?
    # Better: put Caged Zelda ($D8..$DD), Fairy1 ($A0..$A5), Fairy2 ($A6..$AB), Toad ($E0..$E5) at $E7DA/$E7E0/$E7CE!
    # Wait: let's check free 6-byte slots in $E73E..$E83F when in Castle ($074E==3):
    # Actually we can draw Captive right here using $E7DA/$E7E0 (and put Fairy2 at $E798, Toad at $E7A0)!
    a.emit(0xA2, 0x9C)                            # Fairy frame 1 ($E7DA)
    a.emit(0xA5, 0x09, 0x29, 0x08)
    a.branch(0xF0, 'cap_set')
    a.emit(0xA2, 0x5A)                            # Fairy frame 2 ($E798)
    a.branch(0xD0, 'cap_set')
    a.label('cap_toad')
    a.emit(0xA2, 0x60)                            # Caged Toad ($E79E)
    a.branch(0xD0, 'cap_set')
    a.label('cap_zelda')
    a.emit(0xA2, 0xA2)                            # Caged Zelda ($E7E0)
    a.label('cap_set')
    a.emit(0xA9, 0x00, 0x85, 0xEC)                # $EC = 0 (never H-flip right half!)
    a.emit(0xA9, 0x03, 0x85, 0x04)                # $04 = attr $03 (Castle Spr Pal 3)
    a.emit(0x4C, (0xEA37 + RELOC_DELTA) & 0xFF, (0xEA37 + RELOC_DELTA) >> 8)
    a.label('cap_norm')
    a.emit(0xA0, 0x00)
    a.emit(0x4C, (0xEA22 + RELOC_DELTA) & 0xFF, (0xEA22 + RELOC_DELTA) >> 8)

    # 3e. DrawSwordBeam (replaces BowserFlame $E4DC-$E540 for both Sword Beams & thrown Bombs)
    # ($2A,X & $7F) < 2 -> 2-tile Sword Beam ($80/$81 or $82/$83)
    # ($2A,X & $7F) >= 2 -> Z2 Lit Bomb ($84/$85)
    a.label('DrawSwordBeam')
    a.emit(0xBC, 0xF3, 0x06)                      # LDY $06F3,X (OAM offset)
    a.emit(0xB5, 0x2A, 0x29, 0x7F, 0xC9, 0x02)    # LDA $2A,X; AND #$7F; CMP #$02
    a.branch(0xB0, 'sb_bomb')
    a.emit(0xAD, 0xBE, 0x03)                      # LDA $03BE (Y)
    a.emit(0x99, 0x00, 0x02, 0x99, 0x04, 0x02)    # STA $0200,Y; STA $0204,Y
    a.emit(0xAD, 0xB3, 0x03)                      # LDA $03B3 (X)
    a.emit(0x99, 0x03, 0x02)                      # STA $0203,Y
    a.emit(0x18, 0x69, 0x08, 0x99, 0x07, 0x02)    # CLC; ADC #8; STA $0207,Y
    a.emit(0xA5, 0x09, 0x29, 0x04)                # LDA $09; AND #$04
    a.branch(0xF0, 'sb_t0')
    a.emit(0xA9, 0x82)
    a.branch(0xD0, 'sb_tile_ok')
    a.label('sb_t0')
    a.emit(0xA9, 0x80)
    a.label('sb_tile_ok')
    a.emit(0x99, 0x01, 0x02)                      # STA $0201,Y
    a.emit(0x18, 0x69, 0x01, 0x99, 0x05, 0x02)    # ADC #1; STA $0205,Y
    a.emit(0xA9, 0x02)                            # attr = $02
    a.emit(0x99, 0x02, 0x02, 0x99, 0x06, 0x02)
    a.branch(0x10, 'sb_clip')                     # always taken (A=$02)
    a.label('sb_bomb')
    a.emit(0xAD, 0xBE, 0x03, 0x99, 0x00, 0x02)    # Y -> $0200,Y
    a.emit(0xA9, 0xF8, 0x99, 0x04, 0x02)          # hide 2nd sprite
    a.emit(0xAD, 0xB3, 0x03, 0x99, 0x03, 0x02)    # X -> $0203,Y
    a.emit(0xA5, 0x09, 0x29, 0x04)
    a.branch(0xF0, 'sb_bm0')
    a.emit(0xA9, 0x85)
    a.branch(0xD0, 'sb_bm_ok')
    a.label('sb_bm0')
    a.emit(0xA9, 0x84)
    a.label('sb_bm_ok')
    a.emit(0x99, 0x01, 0x02)
    a.emit(0xA9, 0x02, 0x99, 0x02, 0x02)
    a.label('sb_clip')
    # Offscreen clip check ($03D6 & $FC) identical to $E52E-$E540
    a.emit(0xA6, 0x08)                            # LDX $08 (Enemy_Offset)
    a.emit(0xAD, 0xD6, 0x03, 0x29, 0xFC)
    a.branch(0xF0, 'sb_done')
    a.emit(0xA9, 0x00, 0x95, 0x2A)                # STA $2A,X
    a.emit(0xA9, 0xF8, 0x20, 0xC1, 0xE5)          # JSR $E5C1 (hide offscreen sprites)
    a.label('sb_done')
    a.emit(0x60)

    # 3f. DrawCrystalFlag (Flagpole Crystal/Triforce banner, replaces $E54B)
    a.label('DrawCrystalFlag')
    a.emit(0xBC, 0xE5, 0x06)                      # LDY $06E5,X
    a.emit(0xAD, 0xAE, 0x03)                      # LDA $03AE (X)
    a.emit(0x99, 0x03, 0x02)                      # STA $0203,Y
    a.emit(0x18, 0x69, 0x08)
    a.emit(0x99, 0x07, 0x02, 0x99, 0x0B, 0x02)
    a.emit(0x18, 0x69, 0x0C, 0x85, 0x05)
    a.emit(0xB5, 0xCF, 0x20, 0xC1, 0xE5)          # LDA $CF,X; JSR $E5C1 (sets Y for 0,4)
    a.emit(0x69, 0x08, 0x99, 0x08, 0x02)
    a.emit(0xAD, 0x0D, 0x01, 0x85, 0x02)
    a.emit(0xA9, 0x01)
    a.emit(0xA5, 0x09, 0x29, 0x08)                # pulse Crystal Flag between Pal 1 and Pal 2!
    a.branch(0xF0, 'cf_pal_ok')
    a.emit(0xA9, 0x02)
    a.label('cf_pal_ok')
    a.emit(0x85, 0x03, 0x85, 0x04)
    a.emit(0x99, 0x02, 0x02, 0x99, 0x06, 0x02, 0x99, 0x0A, 0x02)
    a.emit(0xA9, 0x7E, 0x99, 0x01, 0x02, 0x99, 0x09, 0x02)
    a.emit(0xA9, 0x7F, 0x99, 0x05, 0x02)
    # Handle flagpole score digit ($E58D-$E5B2 inlined with Bank-1 JSR r_addr($EBB2))
    a.emit(0xAD, 0x0F, 0x07)                      # LDA $070F
    a.branch(0xF0, 'cf_clip')
    a.emit(0x98, 0x18, 0x69, 0x0C, 0xA8)          # TYA; CLC; ADC #$0C; TAY
    a.emit(0xAD, 0x0F, 0x01, 0x0A, 0xAA)          # LDA $010F; ASL A; TAX
    a.emit(0xBD, 0x41, 0xE5, 0x85, 0x00)          # LDA $E541,X; STA $00
    a.emit(0xBD, 0x42, 0xE5)                      # LDA $E542,X
    a.emit(0x20, r_addr(0xEBB2) & 0xFF, r_addr(0xEBB2) >> 8)
    a.label('cf_clip')
    a.emit(0xA6, 0x08, 0xBC, 0xE5, 0x06)          # LDX $08; LDY $06E5,X
    a.emit(0xAD, 0xD1, 0x03, 0x29, 0x0E)          # LDA $03D1; AND #$0E
    a.branch(0xF0, 'cf_done')
    a.emit(0x4C, 0xB3, 0xE5)                      # JMP $E5B3 (hide offscreen sprites)
    a.label('cf_done')
    a.emit(0x60)

    # 3g. DrawBombHammer (replaces $EDE1: uses $84/$85 flickering fuse spark in castles!)
    a.label('DrawBombHammer')
    a.emit(0xA4, 0xB5, 0x88)                      # LDY $B5; DEY
    a.branch(0xD0, 'dbh_done')
    a.emit(0xAD, 0xD3, 0x03, 0x29, 0x08)          # LDA $03D3; AND #$08
    a.branch(0xD0, 'dbh_done')
    a.emit(0xBC, 0xEE, 0x06)                      # LDY $06EE,X
    a.emit(0xAD, 0xB0, 0x03, 0x99, 0x03, 0x02)    # X
    a.emit(0xAD, 0xBB, 0x03, 0x99, 0x00, 0x02)    # Y
    a.emit(0xA9, 0x84)
    a.emit(0xA5, 0x09, 0x29, 0x04)
    a.branch(0xF0, 'dbh_t')
    a.emit(0xA9, 0x85)
    a.label('dbh_t')
    a.emit(0x99, 0x01, 0x02)
    a.emit(0xA9, 0x02, 0x99, 0x02, 0x02)          # Pal 2 (glowing red/gold bomb!)
    a.label('dbh_done')
    a.emit(0x60)

    # 3h. FullBarbaCheck / FullBarbaGfxHandler (hooked at $EEFE: LDY $0704; BEQ $EF34)
    # Handles Big/Inferno Barba ($0754 == 0) with 24px head, bend, horizontal torso, tail tip, and crouch.
    a.label('FullBarbaCheck')
    a.emit(0xAD, 0x54, 0x07)                      # LDA $0754 (0=Big/Inferno, 1=Small)
    a.branch(0xF0, 'fb_start')
    a.emit(0xAC, 0x04, 0x07)                      # LDY $0704
    a.emit(0x4C, (0xEF01 + RELOC_DELTA) & 0xFF, (0xEF01 + RELOC_DELTA) >> 8)

    a.label('fb_start')
    a.emit(0x20, r_addr(0xEFEC) & 0xFF, r_addr(0xEFEC) >> 8)  # JSR $EFEC -> A = pose offset
    # Tick & check FireballThrowingTimer ($0711), same as $EF50..$EF65
    a.emit(0xAE, 0x11, 0x07)                      # LDX $0711
    a.branch(0xF0, 'fb_no_fire')
    a.emit(0x48)                                  # PHA
    a.emit(0xA0, 0x00, 0xAD, 0x81, 0x07, 0xCD, 0x11, 0x07, 0x8C, 0x11, 0x07)
    a.branch(0xB0, 'fb_fire_tick_done')
    a.emit(0x8D, 0x11, 0x07)
    a.label('fb_fire_tick_done')
    a.emit(0x68, 0xA9, 0x58)                      # PLA; LDA #$58 (fire throw pose)
    a.label('fb_no_fire')

    # Map pose offset A -> W_EXTRA_CROUCH (0/1), W_EXTRA_HEAD (0/6/12), X = neck base ($18..$2C)
    a.emit(0xA2, 0x00, 0x8E, W_EXTRA_CROUCH & 0xFF, W_EXTRA_CROUCH >> 8)
    a.emit(0x8E, W_EXTRA_HEAD & 0xFF, W_EXTRA_HEAD >> 8)
    a.emit(0xC9, 0x50)                            # Crouch?
    a.branch(0xD0, 'fb_chk_fire')
    a.emit(0xEE, W_EXTRA_CROUCH & 0xFF, W_EXTRA_CROUCH >> 8)
    a.emit(0xA2, 0x1C)
    a.branch(0xD0, 'fb_pose_ok')

    a.label('fb_chk_fire')
    a.emit(0xC9, 0x58)                            # Fire throw?
    a.branch(0xD0, 'fb_chk_climb1')
    a.emit(0xA2, 0x06, 0x8E, W_EXTRA_HEAD & 0xFF, W_EXTRA_HEAD >> 8)
    a.emit(0xA2, 0x1C)
    a.branch(0xD0, 'fb_pose_ok')

    a.label('fb_chk_climb1')
    a.emit(0xC9, 0x40)
    a.branch(0xD0, 'fb_chk_climb2')
    a.emit(0xA2, 0x0C, 0x8E, W_EXTRA_HEAD & 0xFF, W_EXTRA_HEAD >> 8)
    a.emit(0xA2, 0x28)
    a.branch(0xD0, 'fb_pose_ok')

    a.label('fb_chk_climb2')
    a.emit(0xC9, 0x48)
    a.branch(0xD0, 'fb_chk_jump')
    a.emit(0xA2, 0x0C, 0x8E, W_EXTRA_HEAD & 0xFF, W_EXTRA_HEAD >> 8)
    a.emit(0xA2, 0x2C)
    a.branch(0xD0, 'fb_pose_ok')

    a.label('fb_chk_jump')
    a.emit(0xC9, 0x20)
    a.branch(0xD0, 'fb_chk_w1')
    a.emit(0xA2, 0x24)
    a.branch(0xD0, 'fb_pose_ok')

    a.label('fb_chk_w1')
    a.emit(0xC9, 0x00)
    a.branch(0xF0, 'fb_neck_w1')
    a.emit(0xC9, 0x28)
    a.branch(0xD0, 'fb_chk_w3')
    a.label('fb_neck_w1')
    a.emit(0xA2, 0x18)
    a.branch(0xD0, 'fb_pose_ok')

    a.label('fb_chk_w3')
    a.emit(0xC9, 0x10)
    a.branch(0xF0, 'fb_neck_w3')
    a.emit(0xC9, 0x30)
    a.branch(0xF0, 'fb_neck_w3')
    a.emit(0xC9, 0x38)
    a.branch(0xF0, 'fb_neck_w3')
    a.emit(0xA2, 0x1C)                            # Stand / Walk2 default neck
    a.branch(0xD0, 'fb_pose_ok')
    a.label('fb_neck_w3')
    a.emit(0xA2, 0x20)

    a.label('fb_pose_ok')
    # X = neck base ($18..$2C). Save state to W_EXTRA_*
    a.emit(0x8E, W_SAVE_X & 0xFF, W_SAVE_X >> 8)
    a.emit(0xAD, 0xAD, 0x03, 0x8D, 0x55, 0x07, 0x8D, W_EXTRA_X & 0xFF, W_EXTRA_X >> 8)
    a.emit(0xAD, 0xB8, 0x03, 0x8D, W_EXTRA_Y & 0xFF, W_EXTRA_Y >> 8)
    a.emit(0xA5, 0x33, 0x8D, W_EXTRA_DIR & 0xFF, W_EXTRA_DIR >> 8)
    # Compute attr = $03C4 (with Starman palette cycle if $0704 != 0, and $40 H-flip if facing left)
    a.emit(0xAD, 0xC4, 0x03)
    a.emit(0xAC, 0x04, 0x07)                      # LDY $0704 (StarInvincibleTimer)
    a.branch(0xF0, 'fb_no_star')
    a.emit(0x29, 0xFC, 0x85, 0x00)
    a.emit(0xA5, 0x09, 0x4A, 0x4A, 0x29, 0x03, 0x05, 0x00)
    a.label('fb_no_star')
    a.emit(0xA4, 0x33, 0xC0, 0x01)                # CPY #1 (facing right?)
    a.branch(0xF0, 'fb_attr_ok')
    a.emit(0x09, 0x40)                            # H-flip for facing left
    a.label('fb_attr_ok')
    a.emit(0x8D, W_EXTRA_ATTR & 0xFF, W_EXTRA_ATTR >> 8)
    a.emit(0xAD, 0xD0, 0x03, 0x4A, 0x4A, 0x4A, 0x4A, 0x8D, W_EXTRA_OFFS & 0xFF, W_EXTRA_OFFS >> 8)
    a.emit(0xA9, 0x01, 0x8D, W_EXTRA_ACTIVE & 0xFF, W_EXTRA_ACTIVE >> 8)

    # Draw 8 core sprites at $0200 + $06E4
    # Shift front column backward 14px (X-14 right, X+14 left) so neck belly aligns directly on top of bend!
    # $00 = X, $01 = X+8, $02 = Y, $03 = attr, $04 = offs_mask, $05 = head_base, $06 = neck_base
    a.emit(0xAD, W_EXTRA_DIR & 0xFF, W_EXTRA_DIR >> 8, 0xC9, 0x01)
    a.branch(0xD0, 'fb_x_left')
    a.emit(0xAD, W_EXTRA_X & 0xFF, W_EXTRA_X >> 8)
    a.emit(0x38, 0xE9, 14, 0x85, 0x00)
    a.branch(0xB0, 'fb_x_r_ok')
    a.emit(0xA9, 0x00, 0x85, 0x00)
    a.label('fb_x_r_ok')
    a.emit(0x18, 0x69, 0x08, 0x85, 0x01)
    a.abs_ref(0x4C, 'fb_x_ok')
    a.label('fb_x_left')
    a.emit(0xAD, W_EXTRA_X & 0xFF, W_EXTRA_X >> 8, 0x18, 0x69, 14, 0x85, 0x00)
    a.emit(0x18, 0x69, 0x08, 0x85, 0x01)
    a.label('fb_x_ok')
    a.emit(0xAD, W_EXTRA_Y & 0xFF, W_EXTRA_Y >> 8, 0x85, 0x02)
    a.emit(0xAD, W_EXTRA_ATTR & 0xFF, W_EXTRA_ATTR >> 8, 0x85, 0x03)
    a.emit(0xAD, W_EXTRA_OFFS & 0xFF, W_EXTRA_OFFS >> 8, 0x85, 0x04)
    a.emit(0xAD, W_EXTRA_HEAD & 0xFF, W_EXTRA_HEAD >> 8, 0x85, 0x05)
    a.emit(0xAD, W_SAVE_X & 0xFF, W_SAVE_X >> 8, 0x85, 0x06)
    a.emit(0xAC, 0xE4, 0x06)                      # LDY $06E4

    a.emit(0xAD, W_EXTRA_CROUCH & 0xFF, W_EXTRA_CROUCH >> 8)
    a.branch(0xD0, 'fb_core_crouch')

    # Upright: shift up 2 tiles (Y-16) so neck sits cleanly on top of bend (rows Y-16, Y-8, Y+0, Y+8)
    a.emit(0xA5, 0x02, 0x38, 0xE9, 0x10, 0x85, 0x02)
    a.emit(0xA5, 0x05, 0xA2, 0x01); a.abs_ref(0x20, 'fb_emit_row')
    a.emit(0xA5, 0x05, 0x18, 0x69, 0x03, 0xA2, 0x01); a.abs_ref(0x20, 'fb_emit_row')
    a.emit(0xA5, 0x06, 0xA2, 0x01); a.abs_ref(0x20, 'fb_emit_row')
    a.emit(0xA5, 0x06, 0x18, 0x69, 0x02, 0xA2, 0x01); a.abs_ref(0x20, 'fb_emit_row')
    a.emit(0x60)

    # Crouch 4 rows: hidden, (head+0,head+1), (head+3,head+4), ($3C,$3D)
    a.label('fb_core_crouch')
    a.emit(0xA9, 0xF8, 0x99, 0x00, 0x02, 0x99, 0x04, 0x02)
    a.emit(0xA5, 0x02, 0x18, 0x69, 0x08, 0x85, 0x02)
    a.emit(0x46, 0x04)                            # LSR $04 (consume row 0 offscreen bit)
    a.emit(0x98, 0x18, 0x69, 0x08, 0xA8)          # Y += 8
    a.emit(0xA5, 0x05, 0xA2, 0x01); a.abs_ref(0x20, 'fb_emit_row')
    a.emit(0xA5, 0x05, 0x18, 0x69, 0x03, 0xA2, 0x01); a.abs_ref(0x20, 'fb_emit_row')
    a.emit(0xA9, 0x3C, 0xA2, 0x01); a.abs_ref(0x20, 'fb_emit_row')
    a.emit(0x60)

    # Helper fb_emit_row: A = left_tile, A+X = right_tile (swapped if $03 & $40 != 0)
    a.label('fb_emit_row')
    a.emit(0x85, 0x07)                            # $07 = left_tile
    a.emit(0x8A, 0x18, 0x65, 0x07, 0xAA)          # X = right_tile
    a.emit(0x24, 0x03)                            # BIT $03 (bit 6 = V flag = H-flip)
    a.branch(0x50, 'fb_er_noflip')                # BVC
    a.emit(0xA5, 0x07, 0x86, 0x07, 0xAA)          # swap $07 <-> X
    a.label('fb_er_noflip')
    a.emit(0xA5, 0x02)                            # A = Y
    a.emit(0x46, 0x04)                            # LSR $04 (offscreen bit -> C)
    a.branch(0xB0, 'fb_er_yoff')
    a.emit(0xC9, 0xF0)                            # hide wrapped Y >= $F0 (from Y < 16)
    a.branch(0x90, 'fb_er_yon')
    a.label('fb_er_yoff')
    a.emit(0xA9, 0xF8)
    a.label('fb_er_yon')
    a.emit(0x99, 0x00, 0x02, 0x99, 0x04, 0x02)    # Y0, Y1
    a.emit(0xA5, 0x07, 0x99, 0x01, 0x02)          # tile0
    a.emit(0x8A, 0x99, 0x05, 0x02)                # tile1
    a.emit(0xA5, 0x03, 0x99, 0x02, 0x02, 0x99, 0x06, 0x02)  # attr0, attr1
    a.emit(0xA5, 0x00, 0x99, 0x03, 0x02)          # X0
    a.emit(0xA5, 0x01, 0x99, 0x07, 0x02)          # X1
    a.emit(0xA5, 0x02, 0x18, 0x69, 0x08, 0x85, 0x02)  # $02 += 8
    a.emit(0x98, 0x18, 0x69, 0x08, 0xA8)          # Y += 8
    a.emit(0x60)

    # 3i. DrawBarbaExtraSprites (Bank 1 stub 14, called at end of NMI frame)
    a.label('DrawBarbaExtraSprites')
    a.emit(0xAD, W_EXTRA_ACTIVE & 0xFF, W_EXTRA_ACTIVE >> 8)
    a.branch(0xD0, 'ex_active')
    a.abs_ref(0x4C, 'OamCycle')
    a.label('ex_active')
    a.emit(0xA9, 0x00, 0x8D, W_EXTRA_ACTIVE & 0xFF, W_EXTRA_ACTIVE >> 8)
    a.emit(0xA9, 0x28, 0x8D, W_OAM_SCAN & 0xFF, W_OAM_SCAN >> 8)  # scan from $0228..$02FC

    # Compute row Ys for snout: if crouch, rows 1,2 (Y+8, Y+16); else upright (Y-16, Y-8)
    a.emit(0xAD, W_EXTRA_OFFS & 0xFF, W_EXTRA_OFFS >> 8, 0x85, 0x04)
    a.emit(0xAD, W_EXTRA_Y & 0xFF, W_EXTRA_Y >> 8)
    a.emit(0xAE, W_EXTRA_CROUCH & 0xFF, W_EXTRA_CROUCH >> 8)
    a.branch(0xF0, 'ex_snout_up')
    a.emit(0x18, 0x69, 0x08)
    a.emit(0x46, 0x04)
    a.branch(0x10, 'ex_snout_y')                  # always taken (LSR clears N)
    a.label('ex_snout_up')
    a.emit(0x38, 0xE9, 0x10)
    a.label('ex_snout_y')
    a.emit(0x85, 0x02)                            # $02 = snout top Y
    a.emit(0xA9, 0xF8, 0x8D, W_EX_Y0 & 0xFF, W_EX_Y0 >> 8, 0x8D, W_EX_Y1 & 0xFF, W_EX_Y1 >> 8)
    a.emit(0x46, 0x04)                            # bit 0 -> C
    a.branch(0xB0, 'ex_sn_y1')
    a.emit(0xA5, 0x02, 0xC9, 0xF0)
    a.branch(0xB0, 'ex_sn_y1')
    a.emit(0x8D, W_EX_Y0 & 0xFF, W_EX_Y0 >> 8)
    a.label('ex_sn_y1')
    a.emit(0x46, 0x04)                            # bit 1 -> C
    a.branch(0xB0, 'ex_sn_x')
    a.emit(0xA5, 0x02, 0x18, 0x69, 0x08, 0xC9, 0xF0)
    a.branch(0xB0, 'ex_sn_x')
    a.emit(0x8D, W_EX_Y1 & 0xFF, W_EX_Y1 >> 8)

    # Snout X: +2 if facing right, +6 if facing left (matches 14px backward head shift)
    a.label('ex_sn_x')
    a.emit(0xAD, W_EXTRA_X & 0xFF, W_EXTRA_X >> 8)
    a.emit(0xAE, W_EXTRA_DIR & 0xFF, W_EXTRA_DIR >> 8)
    a.emit(0xE0, 0x01)
    a.branch(0xD0, 'ex_sn_left')
    a.emit(0x18, 0x69, 0x02)
    a.branch(0xB0, 'ex_trail')                    # >= 256 -> skip snout
    a.branch(0x90, 'ex_sn_emit')                  # always taken (carry clear)
    a.label('ex_sn_left')
    a.emit(0x18, 0x69, 0x06)
    a.branch(0xB0, 'ex_trail')
    a.label('ex_sn_emit')
    a.emit(0x85, 0x05)                            # $05 = snout X
    a.emit(0xAD, W_EXTRA_HEAD & 0xFF, W_EXTRA_HEAD >> 8, 0x18, 0x69, 0x02)
    a.emit(0xAC, W_EX_Y0 & 0xFF, W_EX_Y0 >> 8)
    a.abs_ref(0x20, 'ex_put_spr')
    a.emit(0xAD, W_EXTRA_HEAD & 0xFF, W_EXTRA_HEAD >> 8, 0x18, 0x69, 0x05)
    a.emit(0xAC, W_EX_Y1 & 0xFF, W_EX_Y1 >> 8)
    a.abs_ref(0x20, 'ex_put_spr')

    # Trail (Bend + Horizontal Torso + Tail Tip) at rows 2 & 3 (Y+16, Y+24)
    a.label('ex_trail')
    a.emit(0xAD, W_EXTRA_OFFS & 0xFF, W_EXTRA_OFFS >> 8)
    a.emit(0x4A, 0x4A, 0x85, 0x04)                # $04 bit 0 = row 2 offscreen, bit 1 = row 3 offscreen
    a.emit(0xA9, 0xF8, 0x8D, W_EX_Y0 & 0xFF, W_EX_Y0 >> 8, 0x8D, W_EX_Y1 & 0xFF, W_EX_Y1 >> 8)
    a.emit(0x46, 0x04)
    a.branch(0xB0, 'ex_tr_y3')
    a.emit(0xAD, W_EXTRA_Y & 0xFF, W_EXTRA_Y >> 8, 0x18, 0x69, 0x10, 0x8D, W_EX_Y0 & 0xFF, W_EX_Y0 >> 8)
    a.label('ex_tr_y3')
    a.emit(0x46, 0x04)
    a.branch(0xB0, 'ex_tr_loop_init')
    a.emit(0xAD, W_EXTRA_Y & 0xFF, W_EXTRA_Y >> 8, 0x18, 0x69, 0x18, 0x8D, W_EX_Y1 & 0xFF, W_EX_Y1 >> 8)

    a.label('ex_tr_loop_init')
    a.emit(0xA2, 0x00)                            # X = 0..5 (6 columns)
    a.label('ex_tr_loop')
    a.emit(0xAD, W_EXTRA_DIR & 0xFF, W_EXTRA_DIR >> 8, 0xC9, 0x01)
    a.branch(0xD0, 'ex_tr_left')
    # Facing right: signed negative dx
    a.abs_ref(0xBD, 'TrailDxR')
    a.emit(0x18, 0x6D, W_EXTRA_X & 0xFF, W_EXTRA_X >> 8)
    a.branch(0x90, 'ex_tr_next')                  # underflow (< 0) -> skip
    a.branch(0xB0, 'ex_tr_xok')
    a.label('ex_tr_left')
    # Facing left: positive dx
    a.abs_ref(0xBD, 'TrailDxL')
    a.emit(0x18, 0x6D, W_EXTRA_X & 0xFF, W_EXTRA_X >> 8)
    a.branch(0xB0, 'ex_tr_next')                  # overflow (>= 256) -> skip
    a.label('ex_tr_xok')
    a.emit(0x85, 0x05)                            # $05 = col X
    a.emit(0x8E, W_SAVE_X & 0xFF, W_SAVE_X >> 8)
    a.abs_ref(0xBD, 'TrailTileTop')
    a.emit(0xAC, W_EX_Y0 & 0xFF, W_EX_Y0 >> 8)
    a.abs_ref(0x20, 'ex_put_spr')
    a.emit(0xAE, W_SAVE_X & 0xFF, W_SAVE_X >> 8)
    a.abs_ref(0xBD, 'TrailTileBot')
    a.emit(0xAC, W_EX_Y1 & 0xFF, W_EX_Y1 >> 8)
    a.abs_ref(0x20, 'ex_put_spr')
    a.emit(0xAE, W_SAVE_X & 0xFF, W_SAVE_X >> 8)
    a.label('ex_tr_next')
    a.emit(0xE8, 0xE0, 0x06)
    a.branch(0xD0, 'ex_tr_loop')

    # OamCycle: 4-phase OAM rotation ($0204..$02FB, preserving Sprite 0 at $0200..$0203)
    # Runs only during active gameplay ($0770==1, $0772==3) so >8 sprites/scanline flicker fairly.
    a.label('OamCycle')
    a.emit(0xAD, 0x70, 0x07, 0xC9, 0x01)
    a.branch(0xD0, 'oc_early_done')
    a.emit(0xAD, 0x72, 0x07, 0xC9, 0x03)
    a.branch(0xD0, 'oc_early_done')
    a.emit(0xA5, 0x09, 0x29, 0x03)                # FrameCounter & 3
    a.branch(0xD0, 'oc_chk_p1')
    a.label('oc_early_done')
    a.emit(0x60)
    a.label('oc_chk_p1')
    a.emit(0xC9, 0x01)
    a.branch(0xD0, 'oc_p2')
    # phase 1: swap OAM[1..31] ($04) <-> OAM[32..62] ($80), count=31
    a.emit(0xA2, 0x04, 0xA0, 0x80, 0xA9, 31)
    a.abs_ref(0x4C, 'oc_swap_loop')
    a.label('oc_p2')
    a.emit(0xC9, 0x02)
    a.branch(0xD0, 'oc_p3')
    # phase 2: swap [1..15]<->[16..30] and [32..46]<->[48..62]
    a.emit(0xA2, 0x04, 0xA0, 0x44, 0xA9, 15)
    a.abs_ref(0x20, 'oc_swap_loop')
    a.emit(0xA2, 0x80, 0xA0, 0xC0, 0xA9, 15)
    a.abs_ref(0x4C, 'oc_swap_loop')
    # phase 3: swap OAM[1..15] ($04) <-> OAM[48..62] ($C0), count=15
    a.label('oc_p3')
    a.emit(0xA2, 0x04, 0xA0, 0xC0, 0xA9, 15)

    # oc_swap_loop: X = off1, Y = off2, A = count
    a.label('oc_swap_loop')
    a.emit(0x85, 0x00)                            # $00 = count
    a.label('oc_sl_next')
    a.emit(0xBD, 0x00, 0x02, 0xC9, 0xF8)          # skip if both sprites are empty ($F8)
    a.branch(0xD0, 'oc_do_swap')
    a.emit(0xB9, 0x00, 0x02, 0xC9, 0xF8)
    a.branch(0xF0, 'oc_skip_swap')
    a.label('oc_do_swap')
    for k in range(4):
        a.emit(0xBD, k, 0x02, 0x48)               # LDA $0200+k,X; PHA
        a.emit(0xB9, k, 0x02, 0x9D, k, 0x02)      # LDA $0200+k,Y; STA $0200+k,X
        a.emit(0x68, 0x99, k, 0x02)               # PLA; STA $0200+k,Y
    a.label('oc_skip_swap')
    a.emit(0xE8, 0xE8, 0xE8, 0xE8)
    a.emit(0xC8, 0xC8, 0xC8, 0xC8)
    a.emit(0xC6, 0x00)
    a.branch(0xD0, 'oc_sl_next')
    a.label('oc_done')
    a.emit(0x60)

    # ex_put_spr: A = tile, Y = Y_pos ($F8 skips), $05 = X_pos, W_EXTRA_ATTR = attr
    a.label('ex_put_spr')
    a.emit(0xC0, 0xF8)
    a.branch(0xF0, 'ex_put_done')
    a.emit(0x48)                                  # PHA (save tile)
    a.emit(0xAE, W_OAM_SCAN & 0xFF, W_OAM_SCAN >> 8)
    a.label('ex_scan')
    a.emit(0xBD, 0x00, 0x02, 0xC9, 0xF8)
    a.branch(0xF0, 'ex_found')
    a.emit(0xE8, 0xE8, 0xE8, 0xE8)
    a.branch(0xD0, 'ex_scan')
    a.emit(0x68, 0x60)                            # OAM full -> PLA; RTS
    a.label('ex_found')
    a.emit(0x98, 0x9D, 0x00, 0x02)                # Y -> $0200,X
    a.emit(0x68, 0x9D, 0x01, 0x02)                # tile -> $0201,X
    a.emit(0xAD, W_EXTRA_ATTR & 0xFF, W_EXTRA_ATTR >> 8, 0x9D, 0x02, 0x02)
    a.emit(0xA5, 0x05, 0x9D, 0x03, 0x02)          # X -> $0203,X
    a.emit(0xE8, 0xE8, 0xE8, 0xE8)
    a.branch(0xD0, 'ex_save_scan')
    a.emit(0xA2, 0xFC)                            # clamp scan at $FC if wrapped
    a.label('ex_save_scan')
    a.emit(0x8E, W_OAM_SCAN & 0xFF, W_OAM_SCAN >> 8)
    a.label('ex_put_done')
    a.emit(0x60)

    # 3j. WidenBarbaBox (Bank 1 stub 15, called from $B157): widen & raise player sprite-vs-sprite hitbox ($04AC..$04AF)
    a.label('WidenBarbaBox')
    a.emit(0x20, 0x9C, 0xE2)                      # JSR BoundingBoxCore ($04AC=left, $04AD=top, $04AE=right)
    a.emit(0xAD, 0x54, 0x07)                      # LDA $0754 (0=Big/Inferno, 1=Small)
    a.branch(0xD0, 'wb_done')
    a.emit(0xAD, 0xAC, 0x04, 0xCD, 0xAE, 0x04)    # CMP $04AE (skip if offscreen/invalid left >= right)
    a.branch(0xB0, 'wb_done')
    a.emit(0xAD, 0x14, 0x07)                      # upright ($0714 == 0)? raise top ($04AD) by 16px
    a.branch(0xD0, 'wb_chk_dir')
    a.emit(0xAD, 0xAD, 0x04, 0x38, 0xE9, 16)
    a.branch(0xB0, 'wb_top_ok')
    a.emit(0xA9, 0x00)
    a.label('wb_top_ok')
    a.emit(0x8D, 0xAD, 0x04)
    a.label('wb_chk_dir')
    a.emit(0xA5, 0x33, 0x4A)                      # LSR $33 (C=1 if facing right)
    a.branch(0x90, 'wb_left')
    a.emit(0xAD, 0xAC, 0x04, 0x38, 0xE9, 18)
    a.branch(0xB0, 'wb_r_l_ok')
    a.emit(0xA9, 0x00)
    a.label('wb_r_l_ok')
    a.emit(0x8D, 0xAC, 0x04)
    a.emit(0xAD, 0xAE, 0x04, 0x18, 0x69, 8)
    a.branch(0x90, 'wb_r_r_ok')
    a.emit(0xA9, 0xFF)
    a.label('wb_r_r_ok')
    a.emit(0x8D, 0xAE, 0x04, 0x60)
    a.label('wb_left')
    a.emit(0xAD, 0xAC, 0x04, 0x38, 0xE9, 8)
    a.branch(0xB0, 'wb_l_l_ok')
    a.emit(0xA9, 0x00)
    a.label('wb_l_l_ok')
    a.emit(0x8D, 0xAC, 0x04)
    a.emit(0xAD, 0xAE, 0x04, 0x18, 0x69, 18)
    a.branch(0x90, 'wb_l_r_ok')
    a.emit(0xA9, 0xFF)
    a.label('wb_l_r_ok')
    a.emit(0x8D, 0xAE, 0x04)
    a.label('wb_done')
    a.emit(0x60)

    a.label('TrailDxR')
    a.emit((-14) & 0xFF, (-6) & 0xFF, (-30) & 0xFF, (-22) & 0xFF, (-46) & 0xFF, (-38) & 0xFF)
    a.label('TrailDxL')
    a.emit(22, 14, 38, 30, 54, 46)
    a.label('TrailTileTop')
    a.emit(0x30, 0x31, 0x34, 0x35, 0x38, 0x39)
    a.label('TrailTileBot')
    a.emit(0x32, 0x33, 0x36, 0x37, 0x3A, 0x3B)

    # 3g. PowerupFireOrStar: Z2 fireball item ($EB..$EE, no H-flip, pal 0/2 flicker) vs Starman (H-flip + pal 0..3)
    a.label('PowerupFireOrStar')
    a.emit(0xC9, 0x01)                            # CMP #$01 (Fireball item)
    a.branch(0xF0, 'pfs_fire')
    a.emit(0xA5, 0x09, 0x4A, 0x29, 0x03)          # LDA $09; LSR A; AND #$03
    a.emit(0x0D, 0xCA, 0x03)                      # ORA $03CA
    a.emit(0x99, 0x02, 0x02, 0x99, 0x06, 0x02)    # STA $0202,Y; STA $0206,Y
    a.emit(0x99, 0x0A, 0x02, 0x99, 0x0E, 0x02)    # STA $020A,Y; STA $020E,Y
    a.emit(0x09, 0x40)                            # ORA #$40 (H-flip right column)
    a.emit(0x99, 0x06, 0x02, 0x99, 0x0E, 0x02)    # STA $0206,Y; STA $020E,Y
    a.emit(0x4C, r_addr(0xEB64) & 0xFF, r_addr(0xEB64) >> 8)
    a.label('pfs_fire')
    a.emit(0xA5, 0x09, 0x29, 0x04, 0x4A)          # LDA $09; AND #$04; LSR A (0 or 2)
    a.emit(0x0D, 0xCA, 0x03)                      # ORA $03CA
    a.emit(0x99, 0x02, 0x02, 0x99, 0x06, 0x02)    # STA $0202,Y; STA $0206,Y
    a.emit(0x99, 0x0A, 0x02, 0x99, 0x0E, 0x02)    # STA $020A,Y; STA $020E,Y
    a.emit(0x4C, r_addr(0xEB64) & 0xFF, r_addr(0xEB64) >> 8)

    custom_bytes = a.finish()

    # 4. Patch the relocated $E73E data slots for Ironknuckle & Captives & Shells:
    #    - $E73E (offset $00, 6B): Ironknuckle shell ($CC CD CC CD CE CF)
    reloc[r_off(0xE73E) : r_off(0xE744)] = bytes([0xCC, 0xCD, 0xCC, 0xCD, 0xCE, 0xCF])
    #    - $E744 (offset $06, 6B): Stalfos skull shell ($AC AD AC AD AE AF)
    reloc[r_off(0xE744) : r_off(0xE74A)] = bytes([0xAC, 0xAD, 0xAC, 0xAD, 0xAE, 0xAF])
    #    - $E7E6 (offset $A8, 12B): Ironknuckle walk1/walk2 ($C0..$CB)
    reloc[r_off(0xE7E6) : r_off(0xE7F2)] = bytes([
        0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5,
        0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xCB,
    ])
    #    - $E798 (offset $5A, 6B): Caged Fairy frame 2 ($A6..$AB)
    #    - $E79E (offset $60, 6B): Caged Toad ($E0..$E5)
    #    - $E7DA (offset $9C, 6B): Caged Fairy frame 1 ($A0..$A5)
    #    - $E7E0 (offset $A2, 6B): Caged Zelda ($D8..$DD)
    reloc[r_off(0xE798) : r_off(0xE7A4)] = bytes([
        0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xAB,
        0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5,
    ])
    reloc[r_off(0xE7DA) : r_off(0xE7E6)] = bytes([
        0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5,
        0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD,
    ])

    # 5. Wire hooks inside relocated EnemyGfxHandler:
    #    - $E92A (LDA $E840,Y; TAX) -> JSR EnemyTileOverride
    assert reloc[r_off(0xE92A) : r_off(0xE92E)] == bytes([
        0xB9, (0xE840 + RELOC_DELTA) & 0xFF, (0xE840 + RELOC_DELTA) >> 8, 0xAA
    ])
    reloc[r_off(0xE92A) : r_off(0xE92E)] = bytes([
        0x20, a.labels['EnemyTileOverride'] & 0xFF, a.labels['EnemyTileOverride'] >> 8, 0xEA
    ])
    #    - $E930 (Bowser check: LDA $036A; BEQ $E965) -> if non-zero, JMP DrawVillainousLink!
    assert reloc[r_off(0xE930) : r_off(0xE935)] == bytes.fromhex('ad 6a 03 f0 30')
    #      Keep BEQ $E965, replace $E935..$E937 with JMP DrawVillainousLink!
    reloc[r_off(0xE935) : r_off(0xE938)] = bytes([
        0x4C, a.labels['DrawVillainousLink'] & 0xFF, a.labels['DrawVillainousLink'] >> 8
    ])
    #    - $E9AC (LDX #$72; INC $02 -> shell tile) -> JSR ShellTileOverride; NOP
    assert reloc[r_off(0xE9AC) : r_off(0xE9B0)] == bytes.fromhex('a2 72 e6 02')
    reloc[r_off(0xE9AC) : r_off(0xE9B0)] = bytes([
        0x20, a.labels['ShellTileOverride'] & 0xFF, a.labels['ShellTileOverride'] >> 8, 0xEA
    ])
    #    - $EA0E (CMP #$15 -> Toad/Princess) -> JMP CaptiveOverride
    assert reloc[r_off(0xEA0E) : r_off(0xEA12)] == bytes.fromhex('c9 15 d0 10')
    reloc[r_off(0xEA0E) : r_off(0xEA12)] = bytes([
        0x4C, a.labels['CaptiveOverride'] & 0xFF, a.labels['CaptiveOverride'] >> 8, 0xEA
    ])

    #    - $E6C2..$E6C5: Fire item tiles ($EB..$EE, 16x16 Z2 fireball) & $E710 -> JMP PowerupFireOrStar
    assert reloc[r_off(0xE6C2) : r_off(0xE6C6)] == bytes([0xD6, 0xD6, 0xD9, 0xD9])
    reloc[r_off(0xE6C2) : r_off(0xE6C6)] = bytes([0xEB, 0xEC, 0xED, 0xEE])
    assert reloc[r_off(0xE710) : r_off(0xE713)] == bytes.fromhex('85 00 a5')
    reloc[r_off(0xE710) : r_off(0xE713)] = bytes([
        0x4C, a.labels['PowerupFireOrStar'] & 0xFF, a.labels['PowerupFireOrStar'] >> 8
    ])
    #    - $EEFE (LDY $0704 inside PlayerGfxHandler) -> JMP FullBarbaCheck
    assert reloc[r_off(0xEEFE) : r_off(0xEF01)] == bytes.fromhex('ac 04 07')
    reloc[r_off(0xEEFE) : r_off(0xEF01)] = bytes([
        0x4C, a.labels['FullBarbaCheck'] & 0xFF, a.labels['FullBarbaCheck'] >> 8
    ])

    # 6. Assemble 15-entry pointer table at $8000 (30 bytes)
    ptr_table = [
        r_addr(0xE87D),                  # 0: EnemyGfxHandler
        r_addr(0xEC53),                  # 1: DrawLargePlatform
        r_addr(0xECDE),                  # 2: DrawFireball
        r_addr(0xECED),                  # 3: FireballTileAnim
        r_addr(0xED09),                  # 4: DrawExplosion
        r_addr(0xED17),                  # 5: DrawExplosion2
        r_addr(0xED66),                  # 6: DrawVine
        a.labels['DrawBombHammer'],      # 7: DrawHammer -> Bomb
        r_addr(0xEEE9),                  # 8: PlayerGfxHandler
        r_addr(0xEFA4),                  # 9: DrawTitleMario
        r_addr(0xE6D2),                  # 10: PowerupGfxHandler
        a.labels['DrawSwordBeam'],       # 11: DrawBowserFlame -> SwordBeam
        a.labels['DrawCrystalFlag'],     # 12: DrawFlagpoleFlag -> CrystalFlag
        r_addr(0xEBD1),                  # 13: DrawSmallPlatform
        a.labels['DrawBarbaExtraSprites'],  # 14: Full Body Barba snout/bend/torso/tail
        a.labels['WidenBarbaBox'],          # 15: Full Body Barba sprite-vs-sprite hitbox
    ]
    tbl_bytes = b''.join(p.to_bytes(2, 'little') for p in ptr_table)
    bank1[0 : len(tbl_bytes)] = tbl_bytes

    reloc_off = RELOC_DST_START - 0x8000
    bank1[reloc_off : reloc_off + len(reloc)] = reloc
    cust_off = CUSTOM_BASE - 0x8000
    assert cust_off + len(custom_bytes) <= 8192
    bank1[cust_off : cust_off + len(custom_bytes)] = custom_bytes
    return bytes(bank1)


def assemble_call_bank1() -> bytes:
    """Assemble SMB_CALL_BANK1 ($7A00 in WRAM) for fast NMI-safe R6=1 dispatch preserving A, X, Y, flags."""
    a = Asm6502(SMB_CALL_BANK1)
    a.emit(0x8D, W_B1_IDX & 0xFF, W_B1_IDX >> 8)    # STA W_B1_IDX
    a.emit(0x8E, W_SAVE_X & 0xFF, W_SAVE_X >> 8)    # STX W_SAVE_X
    a.emit(0xA9, 0x01, 0x8D, W_CUR_R6 & 0xFF, W_CUR_R6 >> 8)
    a.emit(0xA9, 0x06, 0x8D, W_MMC3_SEL & 0xFF, W_MMC3_SEL >> 8)
    a.emit(0x8D, 0x00, 0x80)                        # R6
    a.emit(0xA9, 0x01, 0x8D, 0x01, 0x80)            # = Bank 1
    a.emit(0xAE, W_B1_IDX & 0xFF, W_B1_IDX >> 8)    # LDX W_B1_IDX
    a.emit(0xBD, 0x00, 0x80)                        # LDA $8000,X
    a.emit(0x8D, W_B1_PTR_LO & 0xFF, W_B1_PTR_LO >> 8)
    a.emit(0xBD, 0x01, 0x80)                        # LDA $8001,X
    a.emit(0x8D, W_B1_PTR_HI & 0xFF, W_B1_PTR_HI >> 8)
    a.emit(0xAE, W_SAVE_X & 0xFF, W_SAVE_X >> 8)    # restore X
    a.emit(0xAD, W_SAVE_A & 0xFF, W_SAVE_A >> 8)    # restore A
    a.abs_ref(0x20, 'call_ind')
    a.emit(0x08, 0x48)                              # PHP; PHA
    a.emit(0xA9, 28,   0x8D, W_CUR_R6 & 0xFF, W_CUR_R6 >> 8)
    a.emit(0xA9, 0x06, 0x8D, W_MMC3_SEL & 0xFF, W_MMC3_SEL >> 8)
    a.emit(0x8D, 0x00, 0x80)                        # R6
    a.emit(0xA9, 28,   0x8D, 0x01, 0x80)            # = Bank 28
    a.emit(0x68, 0x28, 0x60)                        # PLA; PLP; RTS
    a.label('call_ind')
    a.emit(0x6C, W_B1_PTR_LO & 0xFF, W_B1_PTR_LO >> 8)  # JMP (W_B1_PTR)
    out = a.finish()
    assert len(out) <= 0x200, f'SMB_CALL_BANK1 too large: {len(out)}'
    return out


def apply_barba_patches(prg: bytearray, root: Path) -> dict:
    """Install roar.dmc, Bank 1 dispatch stubs, palettes, text, and gameplay hooks into SMB 32KB PRG."""
    def patch(addr: int, new: bytes, expected: bytes) -> None:
        off = addr - 0x8000
        actual = bytes(prg[off : off + len(expected)])
        assert actual == expected, f'Unexpected SMB bytes at ${addr:04X}: {actual.hex(" ")}'
        prg[off : off + len(new)] = new

    # 1. Generate roar.dmc -> build/subgames/smb_roar/ and place at $E740-$EFC0
    roar_out = root / 'build' / 'subgames' / 'smb_roar'
    roar_dmc, roar_info = roar_sample.convert(root / 'assets' / 'roar.wav', roar_out)
    assert DMC_ADDR + len(roar_dmc) <= DMC_LIMIT, (
        f'roar.dmc overflow: ${DMC_ADDR + len(roar_dmc):04X} > ${DMC_LIMIT:04X}'
    )
    prg[DMC_ADDR - 0x8000 : DMC_ADDR - 0x8000 + len(roar_dmc)] = roar_dmc
    dmc_start_reg = (DMC_ADDR - 0xC000) >> 6
    dmc_len_reg = (len(roar_dmc) - 1) >> 4
    dmc_rate_reg = roar_info['rate_index']
    dmc_frames = min(250, roar_info['timer_frames'])

    # 2. Assemble 16 Bank-1 stubs at $E6BE ($E6BE..$E73D) + fixed helpers at $EFC4..$F129
    stubs = bytearray()
    stub_addrs = []
    for idx in range(16):
        stub_addrs.append(STUB_BASE + len(stubs))
        stubs.extend(bytes([
            0x8D, W_SAVE_A & 0xFF, W_SAVE_A >> 8,   # STA W_SAVE_A
            0xA9, idx * 2,                          # LDA #idx*2
            0x4C, SMB_CALL_BANK1 & 0xFF, SMB_CALL_BANK1 >> 8,
        ]))
    assert STUB_BASE + len(stubs) <= DMC_ADDR
    prg[STUB_BASE - 0x8000 : STUB_BASE - 0x8000 + len(stubs)] = stubs

    a = Asm6502(FIXED_HELPER)

    # TriggerRoar: starts one-shot DMC roar without touching X, Y (clobbers A)
    a.label('TriggerRoar')
    a.emit(0xA9, 0x0F,          0x8D, 0x15, 0x40)
    a.emit(0xA9, dmc_frames,    0x8D, W_ROAR_TIMER & 0xFF, W_ROAR_TIMER >> 8)
    a.emit(0xA9, dmc_rate_reg,  0x8D, 0x10, 0x40)
    a.emit(0xA9, 0x40,          0x8D, 0x11, 0x40)
    a.emit(0xA9, dmc_start_reg, 0x8D, 0x12, 0x40)
    a.emit(0xA9, dmc_len_reg,   0x8D, 0x13, 0x40)
    a.emit(0xA9, 0x1F,          0x8D, 0x15, 0x40)
    a.emit(0x60)

    # OnPowerupRoar ($D849: JSR $D948): preserve A, Y -> TriggerRoar -> shake on Fireball ($39==1) -> JMP $D948
    a.label('OnPowerupRoar')
    a.emit(0x48)
    a.abs_ref(0x20, 'TriggerRoar')
    a.emit(0xA5, 0x39, 0xC9, 0x01)                # LDA $39 (PowerUpType); CMP #1 (Fireball)
    a.branch(0xD0, 'opr_no_shake')
    a.emit(0xA9, 44, 0x8D, W_SHAKE_TIMER & 0xFF, W_SHAKE_TIMER >> 8)
    a.label('opr_no_shake')
    a.emit(0x68, 0x4C, 0x48, 0xD9)

    # OnFireballAlreadyRoar ($D825: CMP #$01; BNE $D84C): roar + shake if already Fire ($0756==2) & picking up Fireball ($39==1)
    a.label('OnFireballAlreadyRoar')
    a.emit(0xC9, 0x01)
    a.branch(0xD0, 'ofar_chk_fire')
    a.emit(0x4C, 0x29, 0xD8)                      # JMP $D829 (become Fire)
    a.label('ofar_chk_fire')
    a.emit(0xA5, 0x39, 0xC9, 0x01)                # PowerUpType == 1 (Fireball)?
    a.branch(0xD0, 'ofar_done')
    a.abs_ref(0x20, 'TriggerRoar')
    a.emit(0xA9, 44, 0x8D, W_SHAKE_TIMER & 0xFF, W_SHAKE_TIMER >> 8)
    a.label('ofar_done')
    a.emit(0x4C, 0x4C, 0xD8)                      # JMP $D84C (score)

    # OnAxeRoar ($DE0E: LDA #$00; STA $0772): TriggerRoar -> LDA #$00; STA $0772; RTS
    a.label('OnAxeRoar')
    a.abs_ref(0x20, 'TriggerRoar')
    a.emit(0xA9, 0x00, 0x8D, 0x72, 0x07, 0x60)

    # OnBossHitRoar ($D75C: DEC $0483): flash boss + TriggerRoar + DEC $0483 (preserves Z for BNE $D7C3!)
    a.label('OnBossHitRoar')
    a.emit(0xA9, 10, 0x8D, W_BOSS_FLASH & 0xFF, W_BOSS_FLASH >> 8)
    a.abs_ref(0x20, 'TriggerRoar')
    a.emit(0xCE, 0x83, 0x04, 0x60)

    # OnFireballShoot ($B64F: LDA #$20; STA $FF): set fire-jaw timer + LDA #$20; STA $FF; RTS (preserves X, Y)
    a.label('OnFireballShoot')
    a.emit(0xA9, 12, 0x8D, W_FIRE_TIMER & 0xFF, W_FIRE_TIMER >> 8)
    a.emit(0xA9, 0x20, 0x85, 0xFF, 0x60)

    # NmiChrAndRoarTick ($80E4: JSR $F2D0): tick timers, update R0/R1/R2/R3, JMP $F2D0
    a.label('NmiChrAndRoarTick')
    a.emit(0xA9, 0x00, 0x8D, W_EXTRA_ACTIVE & 0xFF, W_EXTRA_ACTIVE >> 8)
    a.emit(0xAD, W_ROAR_TIMER & 0xFF, W_ROAR_TIMER >> 8)
    a.branch(0xF0, 'chk_fire_tmr')
    a.emit(0xCE, W_ROAR_TIMER & 0xFF, W_ROAR_TIMER >> 8)
    a.label('chk_fire_tmr')
    a.emit(0xAD, W_FIRE_TIMER & 0xFF, W_FIRE_TIMER >> 8)
    a.branch(0xF0, 'chk_flash_tmr')
    a.emit(0xCE, W_FIRE_TIMER & 0xFF, W_FIRE_TIMER >> 8)
    a.label('chk_flash_tmr')
    a.emit(0xAD, W_BOSS_FLASH & 0xFF, W_BOSS_FLASH >> 8)
    a.branch(0xF0, 'chk_shake_tmr')
    a.emit(0xCE, W_BOSS_FLASH & 0xFF, W_BOSS_FLASH >> 8)
    a.label('chk_shake_tmr')
    a.emit(0xAD, W_SHAKE_TIMER & 0xFF, W_SHAKE_TIMER >> 8)
    a.branch(0xF0, 'sel_r0')
    a.emit(0xCE, W_SHAKE_TIMER & 0xFF, W_SHAKE_TIMER >> 8)

    # Select R0: force Small overworld Barba on title ($0770==0) & lives screen ($0770==1,$0772<3)
    a.label('sel_r0')
    a.emit(0xAD, 0x70, 0x07)                      # LDA $0770 (OperMode)
    a.branch(0xF0, 'r0_small')
    a.emit(0xC9, 0x01)
    a.branch(0xD0, 'r0_chk_size')
    a.emit(0xAD, 0x72, 0x07, 0xC9, 0x03)          # LDA $0772 (OperMode_Task); CMP #3
    a.branch(0x90, 'r0_small')
    a.label('r0_chk_size')
    a.emit(0xAD, 0x54, 0x07)                      # LDA $0754 (0=Big/Inferno, 1=Small)
    a.branch(0xF0, 'r0_big')
    a.label('r0_small')
    a.emit(0xA2, CHR_R0_WYRMLING)
    a.emit(0xAD, W_ROAR_TIMER & 0xFF, W_ROAR_TIMER >> 8)
    a.branch(0xF0, 'set_r0')
    a.emit(0xA2, CHR_R0_WYRMLING_ROAR)
    a.branch(0xD0, 'set_r0')
    a.label('r0_big')
    a.emit(0xAD, 0x56, 0x07, 0xC9, 0x02)          # LDA $0756 (2=Fire/Inferno); CMP #2
    a.branch(0xF0, 'r0_fire')
    a.emit(0xA2, CHR_R0_BARBA)
    a.branch(0xD0, 'r0_chk_roar')
    a.label('r0_fire')
    a.emit(0xA2, CHR_R0_INFERNO)
    a.emit(0xAD, W_FIRE_TIMER & 0xFF, W_FIRE_TIMER >> 8)
    a.branch(0xD0, 'r0_use_roar')
    a.label('r0_chk_roar')
    a.emit(0xAD, W_ROAR_TIMER & 0xFF, W_ROAR_TIMER >> 8)
    a.branch(0xF0, 'set_r0')
    a.label('r0_use_roar')
    a.emit(0xA2, CHR_R0_ROAR)
    a.label('set_r0')
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80)

    # Select R1: Castle ($074E == 3 -> 18) vs World (16)
    a.emit(0xA2, CHR_R1_ENEMIES)
    a.emit(0xAD, 0x4E, 0x07, 0xC9, 0x03)
    a.branch(0xD0, 'set_r1')
    a.emit(0xA2, CHR_R1_CASTLE)
    a.label('set_r1')
    a.emit(0xA9, 0x01, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80)

    # Select R2: Crystal Flagpole shimmer (4 / 8)
    a.emit(0xA2, CHR_R2_WORLD_A)
    a.emit(0xA5, 0x09, 0x29, 0x10)
    a.branch(0xF0, 'set_r2')
    a.emit(0xA2, CHR_R2_WORLD_B)
    a.label('set_r2')
    a.emit(0xA9, 0x02, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80)

    # Select R3: Castle Triforce shimmer (10 / 11) vs World (5)
    a.emit(0xA2, CHR_R3_WORLD)
    a.emit(0xAD, 0x4E, 0x07, 0xC9, 0x03)
    a.branch(0xD0, 'set_r3')
    a.emit(0xA2, CHR_R3_CASTLE_A)
    a.emit(0xA5, 0x09, 0x29, 0x08)
    a.branch(0xF0, 'set_r3')
    a.emit(0xA2, CHR_R3_CASTLE_B)
    a.label('set_r3')
    a.emit(0xA9, 0x03, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80)
    a.emit(0xAD, W_MMC3_SEL & 0xFF, W_MMC3_SEL >> 8, 0x8D, 0x00, 0x80)
    a.emit(0x4C, 0xD0, 0xF2)                      # JMP $F2D0 (SoundEngine)

    # SfxWrite4015A (input A = channel mask): preserve DMC bit 4 while W_ROAR_TIMER > 0 (preserves X, Y)
    a.label('SfxWrite4015A')
    a.emit(0x48)                                  # PHA
    a.emit(0xAD, W_ROAR_TIMER & 0xFF, W_ROAR_TIMER >> 8)
    a.branch(0xF0, 'wr4015_no')
    a.emit(0x68, 0x09, 0x10)                      # PLA; ORA #$10
    a.emit(0x8D, 0x15, 0x40, 0x60)
    a.label('wr4015_no')
    a.emit(0x68, 0x8D, 0x15, 0x40, 0x60)          # PLA; STA $4015; RTS

    # SfxWrite4011 ($F37D: STY $4011): skip $4011 pop writes while W_ROAR_TIMER > 0
    a.label('SfxWrite4011')
    a.emit(0xAE, W_ROAR_TIMER & 0xFF, W_ROAR_TIMER >> 8)
    a.branch(0xD0, 'skip4011')
    a.emit(0x8C, 0x11, 0x40)
    a.label('skip4011')
    a.emit(0x60)

    # NmiEndExtra ($817E): preserve A ($2000 value), draw extra Barba sprites & cycle OAM, JMP SMB_NMI_EXIT
    a.label('NmiEndExtra')
    a.emit(0x48)                                  # PHA (save PPUCTRL value for STA $2000 in SMB_NMI_EXIT!)
    a.emit(0x20, stub_addrs[14] & 0xFF, stub_addrs[14] >> 8)
    a.emit(0x68)                                  # PLA
    a.emit(0x4C, SMB_NMI_EXIT & 0xFF, SMB_NMI_EXIT >> 8)

    # ShakeScrollY ($8163: LDA $0740; STA $2005): vertical playfield shake below HUD during W_SHAKE_TIMER
    a.label('ShakeScrollY')
    a.emit(0xAD, W_SHAKE_TIMER & 0xFF, W_SHAKE_TIMER >> 8)
    a.branch(0xF0, 'ssy_normal')
    a.emit(0x29, 0x02)
    a.branch(0xF0, 'ssy_normal')
    a.emit(0xAD, 0x40, 0x07, 0x18, 0x69, 0x04)    # +4px vertical shake
    a.emit(0x8D, 0x05, 0x20, 0x60)
    a.label('ssy_normal')
    a.emit(0xAD, 0x40, 0x07, 0x8D, 0x05, 0x20, 0x60)

    helper_bytes = a.finish()
    assert FIXED_HELPER + len(helper_bytes) <= 0xF12A, (
        f'Fixed helpers overflowed $F12A: ${FIXED_HELPER + len(helper_bytes):04X}'
    )
    prg[FIXED_HELPER - 0x8000 : FIXED_HELPER - 0x8000 + len(helper_bytes)] = helper_bytes

    # 3. Redirect all 13 graphics entry callers/vectors -> Bank-1 dispatch stubs
    call_sites = [
        (0xB905, 0x20, 0xE87D, 0),
        (0xBA82, 0x4C, 0xE87D, 0),
        (0xC8DD, 0x4C, 0xE87D, 0),
        (0xC8EB, 0x20, 0xE87D, 0),
        (0xBE99, 0x20, 0xEC53, 1),
        (0xB6EB, 0x4C, 0xECDE, 2),
        (0xCE08, 0x20, 0xECED, 3),
        (0xB6F6, 0x4C, 0xED09, 4),
        (0xD2B9, 0x20, 0xED17, 5),
        (0xC95C, 0x20, 0xED66, 6),
        (0xB680, 0x20, 0xEDE1, 7),
        (0x839D, 0x4C, 0xEEE9, 8),
        (0xAF16, 0x20, 0xEEE9, 8),
        (0x86C2, 0x20, 0xEFA4, 9),
        (0xBCE1, 0x20, 0xE6D2, 10),
        (0xBB34, 0x20, 0xE4DC, 11),
        (0xB8B2, 0x20, 0xE54B, 12),
        (0xBEBE, 0x20, 0xEBD1, 13),
    ]
    for site, op, orig_tgt, stub_idx in call_sites:
        s_addr = stub_addrs[stub_idx]
        patch(
            site,
            bytes([op, s_addr & 0xFF, s_addr >> 8]),
            bytes([op, orig_tgt & 0xFF, orig_tgt >> 8]),
        )

    # 4. Wire Roar, Fireball jaw, NMI CHR, and SoundEngine DMC protection hooks
    patch(
        0x80E4,
        bytes([0x20, a.labels['NmiChrAndRoarTick'] & 0xFF, a.labels['NmiChrAndRoarTick'] >> 8]),
        bytes.fromhex('20 d0 f2'),
    )
    patch(
        0x8162,
        bytes([0x20, a.labels['ShakeScrollY'] & 0xFF, a.labels['ShakeScrollY'] >> 8, 0xEA, 0xEA, 0xEA]),
        bytes.fromhex('ad 40 07 8d 05 20'),
    )
    patch(
        0x817E,
        bytes([0x4C, a.labels['NmiEndExtra'] & 0xFF, a.labels['NmiEndExtra'] >> 8, 0xEA]),
        bytes.fromhex('8d 00 20 40'),
    )
    patch(
        0xB157,
        bytes([0x20, stub_addrs[15] & 0xFF, stub_addrs[15] >> 8]),
        bytes.fromhex('20 9c e2'),
    )
    # Raise upright Big Barba head-bump Y-offset ($E3CC[0]=04->00, $E3CC[7]=02->00) for taller head
    patch(0xE3CC, bytes([0x00]), bytes([0x04]))
    patch(0xE3D3, bytes([0x00]), bytes([0x02]))
    sfx_w = a.labels['SfxWrite4015A']
    sfx_lo, sfx_hi = sfx_w & 0xFF, sfx_w >> 8
    patch(0xF2DE, bytes([0xA9, 0x0F, 0x20, sfx_lo, sfx_hi]), bytes.fromhex('a9 0f 8d 15 40'))
    patch(0xF308, bytes([0xA9, 0x0F, 0x20, sfx_lo, sfx_hi]), bytes.fromhex('a9 0f 8d 15 40'))
    patch(
        0xF4AB,
        bytes([0xA9, 0x0E, 0x20, sfx_lo, sfx_hi, 0xA9, 0x0F, 0x20, sfx_lo, sfx_hi]),
        bytes.fromhex('a2 0e 8e 15 40 a2 0f 8e 15 40'),
    )
    patch(
        0xF571,
        bytes([0xA9, 0x0D, 0x20, sfx_lo, sfx_hi, 0xA9, 0x0F, 0x20, sfx_lo, sfx_hi]),
        bytes.fromhex('a2 0d 8e 15 40 a2 0f 8e 15 40'),
    )
    patch(
        0xF730,
        bytes([0xA9, 0x0B, 0x20, sfx_lo, sfx_hi, 0xA9, 0x0F, 0x20, sfx_lo, sfx_hi]),
        bytes.fromhex('a9 0b 8d 15 40 a9 0f 8d 15 40'),
    )
    patch(
        0xF37D,
        bytes([0x20, a.labels['SfxWrite4011'] & 0xFF, a.labels['SfxWrite4011'] >> 8]),
        bytes.fromhex('8c 11 40'),
    )
    patch(
        0xD825,
        bytes([0x4C, a.labels['OnFireballAlreadyRoar'] & 0xFF, a.labels['OnFireballAlreadyRoar'] >> 8, 0xEA]),
        bytes.fromhex('c9 01 d0 23'),
    )
    patch(
        0xD849,
        bytes([0x20, a.labels['OnPowerupRoar'] & 0xFF, a.labels['OnPowerupRoar'] >> 8]),
        bytes.fromhex('20 48 d9'),
    )
    patch(
        0xDE0E,
        bytes([0x20, a.labels['OnAxeRoar'] & 0xFF, a.labels['OnAxeRoar'] >> 8, 0xEA, 0xEA]),
        bytes.fromhex('a9 00 8d 72 07'),
    )
    patch(
        0xD75C,
        bytes([0x20, a.labels['OnBossHitRoar'] & 0xFF, a.labels['OnBossHitRoar'] >> 8]),
        bytes.fromhex('ce 83 04'),
    )
    patch(
        0xB64F,
        bytes([0x20, a.labels['OnFireballShoot'] & 0xFF, a.labels['OnFireballShoot'] >> 8, 0xEA]),
        bytes.fromhex('a9 20 85 ff'),
    )

    # 5. Villainous Link throws Bombs (Hammers) in ALL worlds, not just World 6+ ($D11A: CMP #$05; BCC $D127)
    patch(0xD11A, bytes([0xEA, 0xEA, 0xEA, 0xEA]), bytes.fromhex('c9 05 90 09'))
    #    Use Z2 Lit Bomb ($84/$85) for thrown Hammers/Bombs ($E682..$E685) and single 8x8 sprite ($E694)
    patch(0xE682, bytes([0x84, 0x85, 0x84, 0x85]), bytes([0x60, 0x61, 0x62, 0x63]))
    patch(0xE694, bytes([0xA9, 0xF8, 0x99, 0x04, 0x02, 0xEA]), bytes.fromhex('18 69 08 99 04 02'))

    # 6. Barba palettes:
    #    - $85D7: Wyrmling/Barba ($16,$27,$30), Berba ($1A,$27,$30), Inferno ($26,$37,$30)
    patch(
        0x85D7,
        bytes([0x22, 0x16, 0x27, 0x30, 0x22, 0x1A, 0x27, 0x30, 0x22, 0x26, 0x37, 0x30]),
        bytes.fromhex('22 16 27 18 22 30 27 19 22 37 27 16'),
    )
    #    - Area sprite pal 0 ($16,$27,$18 -> $16,$27,$30) + Overworld Pal 3 Z2 Bot ($0F,$12,$30) + Castle pals
    for addr in (0x8CB8, 0x8CDC, 0x8D00):
        patch(addr, bytes([0x16, 0x27, 0x30]), bytes.fromhex('16 27 18'))
    patch(0x8CE8, bytes([0x0F, 0x12, 0x30]), bytes.fromhex('0f 36 17'))
    # Castle sprite pals 0..3 ($8D24..$8D33):
    #   Pal 0: Barba ($16,$27,$30)
    #   Pal 1: Villainous Link ($0F,$36,$16 -> dark hair/outline, skin, evil crimson tunic!)
    #   Pal 2: Sword Beam / Bomb / Bubble ($16,$30,$27)
    #   Pal 3: Caged Zelda / Fairy / Toad ($16,$36,$30)
    patch(
        0x8D24,
        bytes([
            0x16, 0x27, 0x30, 0x0F,
            0x0F, 0x36, 0x16, 0x0F,
            0x16, 0x30, 0x27, 0x0F,
            0x16, 0x36, 0x30, 0x00,
        ]),
        bytes.fromhex('16 27 18 0f 1c 36 17 0f 16 30 27 0f 00 30 10 00'),
    )
    # Also override BowserPalette ($8D4F..$8D52) so Villainous Link uses dark/crimson palette instead of green
    patch(
        0x8D4F,
        bytes([0x0F, 0x0F, 0x36, 0x16]),
        bytes.fromhex('0f 1a 30 27'),
    )

    # 7. Rename MARIO -> BARBA, LUIGI -> BERBA, CASTLE -> PALACE
    for addr in (0x8755, 0x879B, 0x87AE, 0x8D61):
        patch(addr, bytes([0x0B, 0x0A, 0x1B, 0x0B, 0x0A]), bytes([0x16, 0x0A, 0x1B, 0x12, 0x18]))
    for addr in (0x87ED, 0x8D75):
        patch(addr, bytes([0x0B, 0x0E, 0x1B, 0x0B, 0x0A]), bytes([0x15, 0x1E, 0x12, 0x10, 0x12]))
    patch(0x8DA0, bytes([0x19, 0x0A, 0x15, 0x0A, 0x0C, 0x0E]), bytes([0x0C, 0x0A, 0x1C, 0x1D, 0x15, 0x0E]))

    return {
        'roar_info': roar_info,
        'dmc_addr': DMC_ADDR,
        'dmc_bytes': len(roar_dmc),
        'labels': a.labels,
    }
