"""Assemble and patch Family Feud (USA, MMC1) for the Barba Mapper 176 portal."""
from __future__ import annotations

import json
from pathlib import Path

from pack_f13 import Asm6502


# Fixed entry points in guest WRAM bank ($7800-$7BFF)
FEUD_WRAM_CODE_BASE = 0x7800
FEUD_MMC1_CHR0      = 0x7800
FEUD_MMC1_CHR1      = 0x7820
FEUD_MMC1_CTRL      = 0x7860
FEUD_NMI_HOOK       = 0x7880
FEUD_RETURN         = 0x7900
FEUD_WIN_HOOK       = 0x7980
FEUD_BOOT           = 0x7A00

# Guest WRAM state bytes (in guest WRAM bank)
FEUD_PAD_TMP        = 0x7FFD
FEUD_WIN_FLAG       = 0x7FFE  # 0 = Start+Select exit, FEUD_REWARD_MAGIC = win
FEUD_DEBOUNCE       = 0x7FFF  # 60-frame ($3C) NMI debounce counter

# Barba WRAM bank 0 reward flag
FEUD_REWARD_ADDR    = 0x648F
FEUD_REWARD_MAGIC   = 0x46    # 'F'

# Family Feud (USA, Mapper 1 MMC1, 32KB PRG, 128KB CHR-ROM) addresses
FEUD_ORIG_NMI       = 0xCA5E
FEUD_NMI_RTI        = 0xCABE  # PLA; TAY; PLA; TAX; PLA; RTI (always reached, post-VBlank/split)
FEUD_ORIG_RESET     = 0xD136
FEUD_CHR0_ROUTINE   = 0x9954
FEUD_CHR1_ROUTINE   = 0x9968
FEUD_CTRL_ROUTINE   = 0x997C
FEUD_PRG_ROUTINE    = 0x9990
FEUD_WIN_PATCH_ADDR = 0xA964  # Fast Money $5,000 Grand Prize win (LDA #$8A; STA $05F9)

STANDALONE_BOOT_STAGE1 = 0xFFC5  # 13 bytes of 0xFF padding
STANDALONE_BOOT_STAGE2 = 0xFFE2  # 20 bytes of 0x00 padding
STANDALONE_COPY_ADDR   = 0x8300  # PRG bank 4 ($8300, after wram_code at $8000-$82FF)

# 5-bit text tables matching $ACBD, $ACDD, $ACFD
_T0 = '@ABCDEFGHIJKLMNOPQRSTUVWXYZ  |||'
_T1 = '@abcdefghijklmnopqrstuvwxyz     '
_T2 = "@0123456789/'()+*[]-&           "

# 20 Zelda II-themed Main Round puzzles: (prefix_idx, question, [(answer, pts), ...])
# prefix_idx ($AFFD): 0=none, 1="Name the ", 2="Name something ", 3="Name a ", 4="Name an ", 5="Tell me ", 6="How many "
ZELDA2_MAIN_PUZZLES: list[tuple[int, str, list[tuple[str, int]]]] = [
    (3, 'PALACE BOSS', [('HORSE[+]HEAD', 18), ('HELMET[+]HEAD', 16), ('REBONACK', 14), ('CAROCK', 13), ('GOOMA', 12), ('BARBA', 11), ('THUNDER[+]BIRD', 8), ('DARK[+]LINK/SHADOW[+]LINK', 8)]),
    (3, 'KEY ITEM', [('CANDLE/TORCH', 18), ('GLOVE/POWER+GLOVE', 16), ('RAFT', 14), ('BOOTS/WATER+BOOTS', 13), ('FLUTE/WHISTLE', 12), ('CROSS', 11), ('HAMMER', 8), ('MAGIC+KEY', 8)]),
    (3, 'SPELL IN ZELDA II', [('SHIELD', 18), ('JUMP', 16), ('LIFE', 14), ('FAIRY', 13), ('FIRE', 12), ('REFLECT', 11), ('SPELL', 8), ('THUNDER', 8)]),
    (3, 'LINK ATTACK TYPE', [('SWORD/SLASH/THRUST', 28), ('DOWN[+]STAB/DOWNWARD+THRUST', 24), ('UP[+]STAB/UPWARD+THRUST', 18), ('BEAM/SWORD+BEAM', 12), ('FIRE[BALLs]', 10), ('THUNDER', 8)]),
    (3, 'PALACE IN HYRULE', [('PARAPA[+PALACE]', 22), ('MIDORO[+PALACE]', 18), ('ISLAND[+PALACE]', 16), ('MAZE[+PALACE]', 14), ('OCEAN[+PALACE]', 12), ('THREE[-]EYE[+ROCK]', 10), ('GREAT[+PALACE]', 8)]),
    (3, 'TOWN IN HYRULE', [('RAURU', 18), ('RUTO', 16), ('SARIA', 15), ('MIDO', 14), ('NABOORU', 12), ('DARUNIA', 10), ('NEW+KASUTO', 8), ('OLD+KASUTO', 7)]),
    (4, 'ATTACK LEVEL XP', [('200', 22), ('500', 18), ('1000', 16), ('2000', 14), ('3000', 12), ('5000', 10), ('8000', 8)]),
    (3, 'MAGIC LEVEL XP', [('100', 22), ('300', 18), ('700', 16), ('1200', 14), ('2200', 12), ('3500', 10), ('6000', 8)]),
    (3, 'LIFE LEVEL XP', [('50', 22), ('150', 18), ('400', 16), ('800', 14), ('1500', 12), ('2500', 10), ('4000', 8)]),
    (3, 'PARAPA PALACE ENEMY', [('STALFOS', 28), ('IRON[+]KNUCKLEs', 24), ('BOTs', 18), ('BITs', 14), ('BUBBLEs', 10), ('RAs', 6)]),
    (3, 'MIDORO OR ISLAND ENEMY', [('IRON[+]KNUCKLEs', 26), ('STALFOS', 22), ('GORIYAs', 18), ('DOOM[+]KNOCKERs', 14), ('MAUs', 12), ('BUBBLEs', 8)]),
    (3, 'MAZE OR OCEAN ENEMY', [('WIZZROBEs', 28), ('MAGOs', 22), ('IRON[+]KNUCKLEs', 18), ('STALFOS', 14), ('BUBBLEs', 10), ('MOAs', 8)]),
    (3, 'GREAT PALACE ENEMY', [('FOKKAs', 30), ('FOKKERUs', 24), ('BUBBLEs', 18), ('BOTs', 12), ('THUNDER[+]BIRD', 10), ('DARK[+]LINK', 6)]),
    (3, 'DEATH MTN ENEMY', [('DARIA[s]', 30), ('TEKTITEs', 24), ('OCTO[ROK]s', 18), ('GORIYAs', 16), ('BUBBLEs', 12)]),
    (4, 'OVERWORLD HAZARD', [('SWAMP', 30), ('DESERT', 24), ('FOREST/WOODS', 18), ('GRAVEYARD', 16), ('LA(V/B)A', 12)]),
    (2, 'FOUND IN A TOWN', [('HEALER/[TOWN+]LADY/VILLAGERs/PEOPLE', 28), ('ERROR', 24), ('SAGE/WISE+MAN', 18), ('BAGU', 12), ('KNIGHT', 10), ('CHIMNEY', 8)]),
    (3, 'WAY TO CROSS WATER', [('RAFT', 40), ('BOOTS/WATER+BOOTS', 34), ('FAIRY[+SPELL]', 16), ('BRIDGE', 10)]),
    (3, 'DROP FROM AN ENEMY', [('P[-]BAG', 38), ('RED[+MAGIC]+JAR', 26), ('BLUE[+MAGIC]+JAR', 20), ('KEY', 16)]),
    (3, 'WAY TO HEAL LINK', [('FAIRY', 30), ('LIFE[+SPELL]', 26), ('TOWN+LADY/HEALER', 20), ('LEVEL+UP', 14), ('RED[+MAGIC]+JAR', 10)]),
    (2, 'THAT GUARDS THE TRIFORCE', [('THUNDER[+]BIRD', 45), ('DARK[+]LINK/SHADOW[+]LINK', 35), ('OLD+MAN/SAGE', 20)]),
]

# 17 Zelda II-themed Fast Money puzzles
ZELDA2_FM_PUZZLES: list[tuple[int, str, list[tuple[str, int]]]] = [
    (3, 'BARBA EDITION SPELL', [('SCALES', 35), ('METEOR', 30), ('INFERNO', 25), ('WYRML[I]NG', 10)]),
    (3, 'P-BAG XP VALUE', [('200', 40), ('100', 25), ('50', 20), ('500', 15)]),
    (4, 'IRONKNUCKLE COLOR', [('ORANGE', 45), ('RED', 35), ('BLUE', 20)]),
    (3, 'TOWN QUEST ITEM', [('TROPHY', 35), ('MIRROR', 25), ('MEDICINE/WATER+OF+LIFE', 25), ('KID/CHILD', 15)]),
    (2, 'SHOWN ON THE HUD', [('LIFE', 35), ('MAGIC', 25), ('ATTACK', 20), ('XP/EXP/EXPERIENCE', 20)]),
    (4, 'OVERWORLD ENEMY', [('MOBLINs', 35), ('OCTO[ROK]s', 25), ('TEKTITEs', 25), ('LEEVERs', 15)]),
    (3, 'HYRULE REGION', [('WEST+HYRULE', 35), ('EAST+HYRULE', 30), ('DEATH+M(TN/OUNTAIN)', 20), ('MAZE+ISLAND', 15)]),
    (3, 'WAY TO GET A 1-UP', [('1[-]UP[+DOLL]/DOLL', 65), ('9000+XP/9000+EXPERIENCE', 35)]),
    (3, 'COLOR OF MAGIC JAR', [('RED', 55), ('BLUE', 45)]),
    (3, 'DANGEROUS LIQUID', [('LA(V/B)A', 65), ('WATER', 20), ('SWAMP', 15)]),
    (3, 'GIFT FROM A FAIRY', [('LIFE/HEALTH/HEALING', 65), ('MAGIC', 35)]),
    (2, 'ON BARBA TITLE SCREEN', [('BARBA', 50), ('LA(V/B)A', 30), ('CLIFF', 20)]),
    (2, 'ON GAME OVER SCREEN', [('GAN[N]ON', 40), ('RETURN+OF+GAN[N]ON/LINK+KEEPS+LA(V/B)A', 25), ('LAUGH', 20), ('LINK', 15)]),
    (4, 'ENEMY PROJECTILE', [('ROCK', 30), ('FIRE[BALLs]', 25), ('AXE/MACE', 25), ('SPEAR/CLUB', 20)]),
    (3, 'GIFT FROM A WISE MAN', [('SPELL/MAGIC', 45), ('UP[+]STAB', 25), ('DOWN[+]STAB', 20), ('CLUE/HINT', 10)]),
    (3, 'PLACE IN WEST HYRULE', [('PARAPA[+PALACE]', 30), ('RAURU', 25), ('DEATH+M(TN/OUNTAIN)', 25), ('MIDORO[+SWAMP]', 20)]),
    (3, 'PLACE IN EAST HYRULE', [('NABOORU', 30), ('DARUNIA', 25), ('MAZE+ISLAND', 25), ('GREAT[+PALACE]', 20)]),
]


def encode_5bit(text: str) -> bytes:
    """Encode an ASCII string into Family Feud's 5-bit LSB-first packed format."""
    codes: list[int] = []
    for ch in text + '@':
        if ch in _T0[:29]:
            codes.append(_T0.index(ch))
        elif ch in _T1[:29]:
            codes.append(0x1D)
            codes.append(_T1.index(ch))
        elif ch in _T2[:29]:
            codes.append(0x1E)
            codes.append(_T2.index(ch))
        else:
            codes.append(_T0.index(' '))
    bits = 0
    nbits = 0
    out = bytearray()
    for c in codes:
        bits |= (c & 0x1F) << nbits
        nbits += 5
        while nbits >= 8:
            out.append(bits & 0xFF)
            bits >>= 8
            nbits -= 8
    if nbits > 0:
        out.append(bits & 0xFF)
    return bytes(out)


def encode_puzzle(prefix_idx: int, question: str, answers: list[tuple[str, int]]) -> bytes:
    """Encode one question + answers record."""
    buf = bytearray()
    buf.extend(encode_5bit(question))
    hdr = ((prefix_idx & 0x07) << 4) | (len(answers) & 0x0F)
    buf.append(hdr)
    for ans_text, pts in answers:
        buf.append(pts & 0xFF)
        buf.extend(encode_5bit(ans_text))
    return bytes(buf)


def _pad_to(a: Asm6502, target_pc: int) -> None:
    cur = a.base + len(a.buf)
    if cur < target_pc:
        a.emit(*([0xFF] * (target_pc - cur)))
    elif cur > target_pc:
        raise ValueError(f'Code overflowed ${target_pc:04X} (at ${cur:04X})')


def _assemble_standalone_wram(
    wram_syms: dict[str, int],
    *,
    nmi_exit_addr: int | None = None,
) -> bytes:
    """Assemble standalone $7800-$7AFF trampolines using dynamic cast WRAM engine."""
    from feud_engine import W_CHR_MODE
    w = wram_syms
    a = Asm6502(FEUD_WRAM_CODE_BASE)

    # FEUD_MMC1_CHR0 ($7800): A = 4KB CHR bank at PPU $0000
    # Ultra-fast inline A==0 HBlank split (R0 -> R1 -> $5FF0) -> finish in $7900
    a.branch(0xF0, 'c0_fast0')
    a.emit(0x4C, FEUD_RETURN & 0xFF, FEUD_RETURN >> 8)
    a.label('c0_fast0')
    a.emit(0x8D, 0x00, 0x80, 0x8D, 0x01, 0x80)                    # R0 = 0 (A is 0)
    a.emit(0xA9, 0x01, 0x8D, 0x00, 0x80, 0x0A, 0x8D, 0x01, 0x80)  # R1 = 2
    a.emit(0xA9, 0x21, 0x8D, 0xF0, 0x5F)                          # $5FF0 = $21 (CHR-RAM)
    a.emit(0x8D, W_CHR_MODE & 0xFF, W_CHR_MODE >> 8)
    a.abs_ref(0x4C, 'fc_00_post')

    # FEUD_MMC1_CHR1 ($7820): A = 4KB CHR bank at PPU $1000
    # Fast inline paths for A==$0C in RAM mode and any bank in ROM or RAM mode
    _pad_to(a, FEUD_MMC1_CHR1)
    a.emit(0x8D, 0x71, 0x60)  # STA W_CUR_CHR1 ($6071)
    a.emit(0xC9, 0x0C); a.branch(0xD0, 'c1_other')
    a.emit(0xAD, W_CHR_MODE & 0xFF, W_CHR_MODE >> 8)
    a.emit(0xC9, 0x21); a.branch(0xD0, 'c1_other')
    for reg, val in ((2, 0x18), (3, 0x19), (4, 0x1A), (5, 0x1B)):
        a.emit(0xA9, reg, 0x8D, 0x00, 0x80, 0xA9, val, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0x00, 0x60)  # LDA #$00; RTS
    a.label('c1_other')
    a.abs_ref(0x4C, 'c1_dispatch')

    # FEUD_MMC1_CTRL ($7860): A = MMC1 control bits 0..1 -> $A000 mirroring
    _pad_to(a, FEUD_MMC1_CTRL)
    a.emit(0x29, 0x03, 0x49, 0x02, 0x8D, 0x00, 0xA0, 0xA9, 0x00, 0x60)

    # FEUD_NMI_HOOK ($7880): idle animation tick then normal NMI exit (or portal NMI wrapper)
    _pad_to(a, FEUD_NMI_HOOK)
    a.emit(0x20, w['W_NMI_IDLE_TICK'] & 0xFF, w['W_NMI_IDLE_TICK'] >> 8)
    if nmi_exit_addr is None:
        a.emit(0x68, 0xA8, 0x68, 0xAA, 0x68, 0x40)  # PLA; TAY; PLA; TAX; PLA; RTI
    else:
        a.emit(0x4C, nmi_exit_addr & 0xFF, nmi_exit_addr >> 8, 0xEA, 0xEA, 0xEA)

    # Slack $7889-$78FF: fast ROM CHR0 ($08) and CHR1 helpers (no W_SYNC_CHR overhead)
    a.label('c1_dispatch')
    a.emit(0x8E, 0xFF, 0x7F)
    a.emit(0xAD, W_CHR_MODE & 0xFF, W_CHR_MODE >> 8)
    a.emit(0xC9, 0x21); a.branch(0xF0, 'c1_ram_fast')
    a.emit(0xAD, 0x71, 0x60, 0x29, 0x1F)
    a.branch(0x10, 'c1_set_r2_r5')
    a.label('c1_ram_fast')
    a.emit(0xAD, 0x71, 0x60, 0x29, 0x0F, 0xAA)
    a.emit(0xBD, w['TBL_CHR_TO_RAM'] & 0xFF, w['TBL_CHR_TO_RAM'] >> 8)
    a.label('c1_set_r2_r5')
    a.emit(0x0A, 0x0A, 0xAA)
    for reg in (2, 3, 4, 5):
        a.emit(0xA9, reg, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80)
        if reg < 5:
            a.emit(0xE8)
    a.emit(0xAE, 0xFF, 0x7F, 0xA9, 0x00, 0x60)
    a.label('fc_08')
    a.emit(0x8E, 0xFF, 0x7F)
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x80, 0xA9, 0x20, 0x8D, 0x01, 0x80)  # R0 = 32
    a.emit(0xA9, 0x01, 0x8D, 0x00, 0x80, 0xA9, 0x22, 0x8D, 0x01, 0x80)  # R1 = 34
    a.emit(0xA9, 0x01, 0x8D, 0xF0, 0x5F)
    a.emit(0x8D, W_CHR_MODE & 0xFF, W_CHR_MODE >> 8)
    a.emit(0xAD, 0x71, 0x60, 0x29, 0x1F)
    a.abs_ref(0x4C, 'c1_set_r2_r5')

    # $7900 (unused FEUD_RETURN in standalone): non-zero fast CHR0 paths
    _pad_to(a, FEUD_RETURN)
    a.emit(0x8D, 0x70, 0x60)        # STA W_CUR_CHR0
    a.emit(0xC9, 0x03); a.branch(0xF0, 'fc_03')
    a.emit(0xC9, 0x05, 0xD0, 0x03); a.abs_ref(0x4C, 'fc_05')
    a.emit(0xC9, 0x06, 0xD0, 0x03); a.abs_ref(0x4C, 'fc_06')
    a.emit(0xC9, 0x08, 0xD0, 0x03); a.abs_ref(0x4C, 'fc_08')
    a.emit(0xC9, 0x09); a.branch(0xF0, 'fc_09')
    a.emit(0xC9, 0x07, 0xD0, 0x03); a.abs_ref(0x4C, 'fc_07')
    a.emit(0xC9, 0x0B, 0xD0, 0x03); a.abs_ref(0x4C, 'fc_0B')
    a.label('fc_c1_sync')
    a.emit(0x20, w['W_SYNC_CHR'] & 0xFF, w['W_SYNC_CHR'] >> 8)
    a.emit(0xA9, 0x00, 0x60)
    a.label('fc_03')                # Face-Off / FM sl=95 split: R0 -> $5FF0 -> R1 inside HBlank
    a.emit(0x8E, 0xFF, 0x7F)
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x80)  # select R0 before HBlank
    a.emit(0xA2, 0x0C)                    # R0 = 12 (CHR 03)
    a.emit(0xAD, 0xD3, 0x04, 0xC9, 0x02)  # mode == 2 (Face-Off)?
    a.branch(0xF0, 'fc_03_ram')
    a.emit(0xA9, 0x01)                    # FM / ROM mode
    a.branch(0xD0, 'fc_03_go')
    a.label('fc_03_ram')
    a.emit(0xA9, 0x21, 0xEA)              # RAM mode (+NOP to match cycle count)
    a.label('fc_03_go')
    a.emit(0x8E, 0x01, 0x80)              # R0 = 12
    a.emit(0x8D, 0xF0, 0x5F)              # $5FF0 = $21 or $01 (12 dots after R0!)
    a.emit(0xA2, 0x01, 0x8E, 0x00, 0x80, 0xA2, 0x0E, 0x8E, 0x01, 0x80)  # R1 = 14
    a.emit(0x8D, W_CHR_MODE & 0xFF, W_CHR_MODE >> 8)
    a.abs_ref(0x4C, 'fc_ret_fast')
    a.label('fc_09')                # Stage ($04/$0D/$0E) switches directly to RAM slot 7 (R0=28, R1=30)
    a.emit(0xAD, 0x45, 0x03, 0xC9, 0x0D)
    a.branch(0xF0, 'fc_09_ram')
    a.emit(0xC9, 0x0E); a.branch(0xF0, 'fc_09_ram')
    a.emit(0xC9, 0x04); a.branch(0xF0, 'fc_09_ram')
    a.emit(0x8E, 0xFF, 0x7F)
    a.emit(0xA2, 0x24)
    a.abs_ref(0x4C, 'fc_rom_r0')
    a.label('fc_09_ram')
    a.emit(0x8E, 0xFF, 0x7F, 0x8C, 0xFC, 0x7F)  # STX $7FFF; STY $7FFC
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x80)        # select R0
    a.emit(0xA9, 0x1C, 0xA2, 0x1E, 0xA0, 0x01)  # R0=28, R1=30, Y=1
    a.emit(0x8D, 0x01, 0x80)                    # R0 = 28
    a.emit(0x8C, 0x00, 0x80)                    # select R1 (+12 dots)
    a.emit(0x8E, 0x01, 0x80)                    # R1 = 30 (+24 dots)
    a.emit(0xAC, 0xFC, 0x7F)
    a.abs_ref(0x4C, 'fc_ret_fast')
    a.label('fc_05')
    a.emit(0x8E, 0xFF, 0x7F)
    a.emit(0xA2, 0x10)              # slot 4 * 4 = 16 (CHR 05)
    a.abs_ref(0x4C, 'fc_ram_no_c1')
    a.label('fc_06')
    a.emit(0x8E, 0xFF, 0x7F)
    a.emit(0xA2, 0x14)              # slot 5 * 4 = 20 (CHR 06)
    a.label('fc_ram_no_c1')
    a.emit(0x8C, 0xFC, 0x7F)              # STY $7FFC
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x80)  # select R0 before HBlank
    a.emit(0x8A, 0xA0, 0x21, 0xA2, 0x01)  # A=slot*4, Y=$21, X=$01
    a.emit(0x8D, 0x01, 0x80)              # R0 = slot*4
    a.emit(0x8E, 0x00, 0x80)              # select R1 (+12 dots)
    a.emit(0x09, 0x02, 0x8D, 0x01, 0x80)  # R1 = slot*4 + 2 (+24 dots)
    a.emit(0x8C, 0xF0, 0x5F)              # $5FF0 = $21 (+36 dots)
    a.emit(0x8C, W_CHR_MODE & 0xFF, W_CHR_MODE >> 8)
    a.emit(0xAC, 0xFC, 0x7F)
    a.label('fc_ret_fast')
    a.emit(0xAE, 0xFF, 0x7F, 0xA9, 0x00, 0x60)

    # FEUD_BOOT ($7A00): cold init -> copy static CHR0..7 to CHR-RAM -> Reset
    _pad_to(a, FEUD_BOOT)
    a.emit(0x78, 0xD8, 0xA2, 0xFF, 0x9A)        # SEI; CLD; LDX #$FF; TXS
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20)  # PPU off
    a.emit(0xA9, 0x83, 0x8D, 0x01, 0xA0)        # STA $A001 (WRAM bank 3 + unlock $5FF0-$5FF3)
    a.emit(0x2C, 0x02, 0x20)                    # BIT $2002
    a.label('st_v1')
    a.emit(0x2C, 0x02, 0x20)
    a.branch(0x10, 'st_v1')
    a.label('st_v2')
    a.emit(0x2C, 0x02, 0x20)
    a.branch(0x10, 'st_v2')
    a.emit(0xA9, 0x00)
    a.emit(0x8D, 0x70, 0x60, 0x8D, 0x71, 0x60, 0x8D, 0x2A, 0x60)  # clear CHR0/1 + magic
    a.emit(0x20, w['W_CALL_B4'] & 0xFF, w['W_CALL_B4'] >> 8)      # A=0: copy CHR 0..7 -> CHR-RAM
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x00, 0x8D, 0x01, 0x80)  # R6=0
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x01, 0x8D, 0x01, 0x80)  # R7=1
    a.emit(0x20, w['W_SYNC_CHR'] & 0xFF, w['W_SYNC_CHR'] >> 8)
    a.emit(0x4C, FEUD_ORIG_RESET & 0xFF, FEUD_ORIG_RESET >> 8)

    # Overflow helpers in remaining $7Axx slack after FEUD_BOOT
    a.label('fc_ram_fast')
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80, 0xE8, 0xE8)
    a.emit(0xA9, 0x01, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80)
    a.emit(0xA9, 0x21, 0x8D, 0xF0, 0x5F)
    a.emit(0x8D, W_CHR_MODE & 0xFF, W_CHR_MODE >> 8)
    a.label('fc_done_sync')
    a.emit(0xAE, 0xFF, 0x7F)        # restore X
    a.emit(0x20, w['W_SYNC_CHR'] & 0xFF, w['W_SYNC_CHR'] >> 8)
    a.emit(0xA9, 0x00, 0x60)
    a.label('fc_07')
    a.emit(0x8E, 0xFF, 0x7F)
    a.emit(0xA2, 0x1C)              # ROM CHR 07 * 4 = 28 ($1C)
    a.label('fc_rom_r0')
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80, 0xE8, 0xE8)
    a.emit(0xA9, 0x01, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80)
    a.emit(0xA9, 0x01, 0x8D, 0xF0, 0x5F)
    a.emit(0x8D, W_CHR_MODE & 0xFF, W_CHR_MODE >> 8)
    a.abs_ref(0x4C, 'fc_done_sync')
    a.label('fc_0B')                # Fast Money sl=99 split: align into HBlank, RAM slot 1
    a.emit(0x8E, 0xFF, 0x7F)
    a.emit(0xEA, 0xEA)              # +4 cyc into HBlank
    a.emit(0xA2, 0x04)              # slot 1 * 4 = 4
    a.emit(0xAD, 0xD3, 0x04, 0xC9, 0x03)
    a.emit(0xD0, 0x03); a.abs_ref(0x4C, 'fc_ram_fast')
    a.emit(0xA2, 0x2C)              # ROM CHR 0B * 4 = 44 ($2C)
    a.abs_ref(0x4C, 'fc_rom_r0')
    a.label('fc_00_post')
    a.emit(0xA9, 0x00, 0x8D, 0x70, 0x60)
    a.emit(0x20, w['W_SYNC_CHR'] & 0xFF, w['W_SYNC_CHR'] >> 8)
    a.emit(0xA9, 0x00, 0x60)
    _pad_to(a, FEUD_WRAM_CODE_BASE + 0x0300)
    return a.finish()


def assemble_feud_wram_code(
    restore_addr: int,
    *,
    restore_r6: int = 0x00,
    restore_r7: int = 0x01,
    standalone_stub: bool = False,
    wram_syms: dict[str, int] | None = None,
    nmi_exit_addr: int | None = None,
) -> bytes:
    """Assemble the WRAM trampoline and hooks at $7800-$7AFF."""
    if standalone_stub:
        assert wram_syms is not None, 'wram_syms required for standalone_stub=True'
        return _assemble_standalone_wram(wram_syms, nmi_exit_addr=nmi_exit_addr)
    a = Asm6502(FEUD_WRAM_CODE_BASE)

    # ---- FEUD_MMC1_CHR0 ($7800): A = 4KB CHR bank at PPU $0000 ----
    # Preserves X and Y. MMC3 R0/R1 take 1KB bank numbers (bit 0 ignored).
    a.label('FEUD_MMC1_CHR0')
    a.emit(0x0A, 0x0A)              # ASL A; ASL A (bank * 4)
    a.emit(0x48)                    # PHA
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x80)  # LDA #$00; STA $8000
    a.emit(0x68)                    # PLA
    a.emit(0x8D, 0x01, 0x80)        # STA $8001
    a.emit(0x18, 0x69, 0x02)        # CLC; ADC #$02
    a.emit(0x48)                    # PHA
    a.emit(0xA9, 0x01, 0x8D, 0x00, 0x80)  # LDA #$01; STA $8000
    a.emit(0x68)                    # PLA
    a.emit(0x8D, 0x01, 0x80)        # STA $8001
    a.emit(0xA9, 0x00)              # LDA #$00 (vanilla $9954 leaves A=0..1)
    a.emit(0x60)                    # RTS

    # ---- FEUD_MMC1_CHR1 ($7820): A = 4KB CHR bank at PPU $1000 ----
    # Preserves X and Y.
    _pad_to(a, FEUD_MMC1_CHR1)
    a.label('FEUD_MMC1_CHR1')
    a.emit(0x0A, 0x0A)              # ASL A; ASL A (bank * 4)
    for reg in (2, 3, 4, 5):
        if reg > 2:
            a.emit(0x18, 0x69, 0x01)  # CLC; ADC #$01
        a.emit(0x48)                # PHA
        a.emit(0xA9, reg, 0x8D, 0x00, 0x80)  # LDA #reg; STA $8000
        a.emit(0x68)                # PLA
        a.emit(0x8D, 0x01, 0x80)    # STA $8001
    a.emit(0xA9, 0x00)              # LDA #$00 (vanilla $9968 leaves A=0; $D174 clears RAM with A!)
    a.emit(0x60)                    # RTS

    # ---- FEUD_MMC1_CTRL ($7860): A = MMC1 control byte ----
    _pad_to(a, FEUD_MMC1_CTRL)
    a.label('FEUD_MMC1_CTRL')
    a.emit(0x29, 0x01)              # AND #$01 (0=Vertical, 1=Horizontal)
    a.emit(0x8D, 0x00, 0xA0)        # STA $A000
    a.emit(0xA9, 0x00)              # LDA #$00
    a.emit(0x60)                    # RTS

    # ---- FEUD_NMI_HOOK ($7880) ----
    _pad_to(a, FEUD_NMI_HOOK)
    a.label('FEUD_NMI_HOOK')

    # Debounce counter
    a.emit(0xAD, FEUD_DEBOUNCE & 0xFF, FEUD_DEBOUNCE >> 8)
    a.branch(0xF0, 'check_pad')     # BEQ check_pad
    a.emit(0xCE, FEUD_DEBOUNCE & 0xFF, FEUD_DEBOUNCE >> 8)
    a.emit(0x68, 0xA8, 0x68, 0xAA, 0x68, 0x40)  # PLA; TAY; PLA; TAX; PLA; RTI

    a.label('check_pad')
    # Read joypad 1 ($4016)
    a.emit(0xA9, 0x01, 0x8D, 0x16, 0x40)  # LDA #$01; STA $4016
    a.emit(0xA9, 0x00, 0x8D, 0x16, 0x40)  # LDA #$00; STA $4016
    a.emit(0x8D, FEUD_PAD_TMP & 0xFF, FEUD_PAD_TMP >> 8)
    a.emit(0xA2, 0x08)                    # LDX #$08
    a.label('pad_loop')
    a.emit(0xAD, 0x16, 0x40)              # LDA $4016
    a.emit(0x4A)                          # LSR A
    a.emit(0x2E, FEUD_PAD_TMP & 0xFF, FEUD_PAD_TMP >> 8)  # ROL FEUD_PAD_TMP
    a.emit(0xCA)                          # DEX
    a.branch(0xD0, 'pad_loop')            # BNE pad_loop

    a.emit(0xAD, FEUD_PAD_TMP & 0xFF, FEUD_PAD_TMP >> 8)
    a.emit(0x29, 0x30)                    # AND #$30 (Start+Select)
    a.emit(0xC9, 0x30)                    # CMP #$30
    a.branch(0xD0, 'nmi_resume')          # BNE nmi_resume
    a.emit(0xA9, 0x00, 0x8D, FEUD_WIN_FLAG & 0xFF, FEUD_WIN_FLAG >> 8)
    a.emit(0x4C, FEUD_RETURN & 0xFF, FEUD_RETURN >> 8)

    a.label('nmi_resume')
    a.emit(0x68, 0xA8, 0x68, 0xAA, 0x68, 0x40)  # PLA; TAY; PLA; TAX; PLA; RTI

    # ---- FEUD_RETURN ($7900) ----
    _pad_to(a, FEUD_RETURN)
    a.label('FEUD_RETURN')
    a.emit(0x78)                          # SEI
    a.emit(0xAE, FEUD_WIN_FLAG & 0xFF, FEUD_WIN_FLAG >> 8)  # LDX FEUD_WIN_FLAG
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20, 0x8D, 0x15, 0x40)

    # Switch to Barba outer banks ($5FF0=0, $5FF1=0, $5FF2=0) and WRAM bank 0 ($A0)
    a.emit(0xA9, 0x00, 0x8D, 0xF0, 0x5F, 0x8D, 0xF1, 0x5F, 0x8D, 0xF2, 0x5F)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, restore_r6, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, restore_r7, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0xA0, 0x8D, 0x01, 0xA0)
    a.emit(0xE0, FEUD_REWARD_MAGIC)       # CPX #FEUD_REWARD_MAGIC
    a.branch(0xD0, 'ret_no_win')
    a.emit(0x8E, FEUD_REWARD_ADDR & 0xFF, FEUD_REWARD_ADDR >> 8)
    a.label('ret_no_win')
    if standalone_stub:
        a.label('ret_halt')
        a.emit(0x4C, a.labels['ret_halt'] & 0xFF, a.labels['ret_halt'] >> 8)
    else:
        a.emit(0x4C, restore_addr & 0xFF, restore_addr >> 8)

    # ---- FEUD_WIN_HOOK ($7980) ----
    _pad_to(a, FEUD_WIN_HOOK)
    a.label('FEUD_WIN_HOOK')
    a.emit(0xA9, FEUD_REWARD_MAGIC, 0x8D, FEUD_WIN_FLAG & 0xFF, FEUD_WIN_FLAG >> 8)
    a.emit(0x4C, FEUD_RETURN & 0xFF, FEUD_RETURN >> 8)

    # ---- FEUD_BOOT ($7A00) ----
    _pad_to(a, FEUD_BOOT)
    a.label('FEUD_BOOT')
    a.emit(0x78)                          # SEI
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20)
    a.emit(0xA9, 0x3C, 0x8D, FEUD_DEBOUNCE & 0xFF, FEUD_DEBOUNCE >> 8)
    a.emit(0xA9, 0x00, 0x8D, FEUD_WIN_FLAG & 0xFF, FEUD_WIN_FLAG >> 8)

    # Map 32KB PRG: R6=0, R7=1 (C000-FFFF fixed to 2, 3)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x00, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x01, 0x8D, 0x01, 0x80)
    a.emit(0x4C, FEUD_ORIG_RESET & 0xFF, FEUD_ORIG_RESET >> 8)

    return a.finish()


def patch_feud_prg_and_chr(
    prg: bytes,
    chr_rom: bytes,
    z2_rom: bytes | None = None,
    barba_json: Path | None = None,
    *,
    standalone: bool = False,
    wram_syms: dict[str, int] | None = None,
    celeb_syms: dict[str, int] | None = None,
    win_hook_addr: int | None = None,
) -> tuple[bytes, bytes]:
    """Patch Family Feud 32KB PRG and 128KB CHR-ROM for Mapper 176 portal, Zelda II puzzles, and Barba/Z2 sprites."""
    assert len(prg) == 32768
    assert len(chr_rom) == 131072
    buf = bytearray(prg)
    cbuf = bytearray(chr_rom)

    def patch_jmp(addr: int, target: int) -> None:
        off = addr - 0x8000
        buf[off] = 0x4C
        buf[off + 1] = target & 0xFF
        buf[off + 2] = target >> 8

    # 1. Replace MMC1 serial routines with WRAM trampolines
    patch_jmp(FEUD_CHR0_ROUTINE, FEUD_MMC1_CHR0)
    patch_jmp(FEUD_CHR1_ROUTINE, FEUD_MMC1_CHR1)
    patch_jmp(FEUD_CTRL_ROUTINE, FEUD_MMC1_CTRL)
    buf[FEUD_PRG_ROUTINE - 0x8000] = 0x60  # RTS

    # 2. NOP out MMC1 reset (INC $9FFF/$BFFF/$DFFF/$FFFF at $D15B-$D166)
    mmc1_rst_off = 0xD15B - 0x8000
    assert bytes(buf[mmc1_rst_off : mmc1_rst_off + 12]) == bytes.fromhex('EEFF9FEEFFBFEEFFDFEEFFFF')
    buf[mmc1_rst_off : mmc1_rst_off + 12] = b'\xEA' * 12

    # 3. Hook NMI exit (post-VBlank/split) and Endgame Win
    nmi_rti_off = FEUD_NMI_RTI - 0x8000
    assert bytes(buf[nmi_rti_off : nmi_rti_off + 6]) == bytes.fromhex('68A868AA6840')
    patch_jmp(FEUD_NMI_RTI, FEUD_NMI_HOOK)
    buf[nmi_rti_off + 3 : nmi_rti_off + 6] = b'\xEA\xEA\xEA'
    if win_hook_addr is not None:
        patch_jmp(FEUD_WIN_PATCH_ADDR, win_hook_addr)
    elif not standalone:
        patch_jmp(FEUD_WIN_PATCH_ADDR, FEUD_WIN_HOOK)

    # 4. Encode Zelda II Main Round + Fast Money puzzles into Bank 16 ($10000 in CHR)
    q_bank = bytearray()
    main_lens = [0]
    for p_idx, q_str, ans in ZELDA2_MAIN_PUZZLES:
        rec = encode_puzzle(p_idx, q_str, ans)
        assert len(rec) < 256
        main_lens.append(len(rec))
        q_bank.extend(rec)
    fm_start = len(q_bank)
    fm_lens = []
    for p_idx, q_str, ans in ZELDA2_FM_PUZZLES:
        rec = encode_puzzle(p_idx, q_str, ans)
        assert len(rec) < 256
        fm_lens.append(len(rec))
        q_bank.extend(rec)
    assert len(q_bank) <= 4096, f'Zelda II puzzles exceeded 4KB bank 16 ({len(q_bank)} bytes)'
    cbuf[16 * 4096 : 16 * 4096 + len(q_bank)] = q_bank

    # Patch $B132 (Main lengths) and $B312 (FM lengths) and $ADE5 (FM start offset)
    buf[0xB132 - 0x8000 : 0xB132 - 0x8000 + len(main_lens)] = bytes(main_lens)
    buf[0xB312 - 0x8000 : 0xB312 - 0x8000 + len(fm_lens)] = bytes(fm_lens)
    buf[0xADE6 - 0x8000] = fm_start & 0xFF
    buf[0xADEB - 0x8000] = fm_start >> 8

    # Force pool size to len(ZELDA2_MAIN_PUZZLES) for Main Round ($AE99) and len(ZELDA2_FM_PUZZLES) for Fast Money ($AEC0), and $C68F high byte = 0
    main_count = len(ZELDA2_MAIN_PUZZLES)
    fm_count = len(ZELDA2_FM_PUZZLES)
    buf[0xC68F - 0x8000] = 0x00  # AND #$00
    a_wrap = Asm6502(0xAE99)
    a_wrap.emit(0xA9, 0x00, 0x8D, 0x18, 0x03)  # LDA #$00; STA $0318
    a_wrap.emit(0xAD, 0x17, 0x03)              # LDA $0317
    a_wrap.label('m_mod')
    a_wrap.emit(0xC9, main_count)              # CMP #main_count
    a_wrap.branch(0x90, 'm_ok')                # BCC m_ok
    a_wrap.emit(0xE9, main_count)              # SBC #main_count
    a_wrap.emit(0x4C, (0xAE99 + 8) & 0xFF, (0xAE99 + 8) >> 8)
    a_wrap.label('m_ok')
    a_wrap.emit(0x8D, 0x17, 0x03)              # STA $0317
    a_wrap.emit(0x4C, 0xA5, 0xAD)              # JMP $ADA5
    w_bytes = a_wrap.finish()
    assert len(w_bytes) <= 36
    buf[0xAE99 - 0x8000 : 0xAE99 - 0x8000 + len(w_bytes)] = w_bytes

    a_fm = Asm6502(0xAEC0)
    a_fm.emit(0xA9, 0x00, 0x8D, 0x1C, 0x03)    # LDA #$00; STA $031C
    a_fm.emit(0xAD, 0x1B, 0x03)                # LDA $031B
    a_fm.label('fm_mod')
    a_fm.emit(0xC9, fm_count)                  # CMP #fm_count
    a_fm.branch(0x90, 'fm_ok')                 # BCC fm_ok
    a_fm.emit(0xE9, fm_count)                  # SBC #fm_count
    a_fm.emit(0x4C, (0xAEC0 + 8) & 0xFF, (0xAEC0 + 8) >> 8)
    a_fm.label('fm_ok')
    a_fm.emit(0x8D, 0x1B, 0x03)                # STA $031B
    a_fm.emit(0x4C, 0xE5, 0xAD)                # JMP $ADE5
    fm_bytes = a_fm.finish()
    assert len(fm_bytes) <= 35
    buf[0xAEC0 - 0x8000 : 0xAEC0 - 0x8000 + len(fm_bytes)] = fm_bytes

    # 5. Replace Family Feud stage, overview, Face-Off, Fast Money, and Host people with Barba assets.
    _ = barba_json
    if z2_rom is not None:
        from feud_art import apply_barba_cast, patch_chr0b_blue_k
        apply_barba_cast(buf, cbuf, z2_rom)
        if standalone:
            assert wram_syms is not None, 'wram_syms required for standalone=True'
            import feud_hooks
            # Restore vanilla podium/UI tiles in CHR 05/06 overwritten by static apply_barba_cast
            # so dynamic Stage Close-Up keeps crisp podium top rails and blank $B5..$BA.
            podium_keep = set(range(0x04, 0x5D))
            for b_chr in (0x05, 0x06):
                for t in podium_keep:
                    off = b_chr * 4096 + t * 16
                    cbuf[off : off + 16] = chr_rom[off : off + 16]
            cbuf[0x06 * 4096 + 0xB5 * 16 : 0x06 * 4096 + 0xBB * 16] = b'\x00' * (6 * 16)
            patch_chr0b_blue_k(cbuf)
            feud_hooks.apply_feud_prg_hooks(buf, wram_syms, celeb_syms)

    assert len(buf) == 32768
    assert len(cbuf) == 131072
    return bytes(buf), bytes(cbuf)


def build_standalone(out_path: Path, src_rom: Path, z2_rom_path: Path | None = None, barba_json: Path | None = None) -> Path:
    """Build a standalone Mapper 176 test ROM for Family Feud: Barba Edition."""
    raw = src_rom.read_bytes()
    assert raw[:4] == b'NES\x1a'
    z2_bytes = z2_rom_path.read_bytes() if z2_rom_path and z2_rom_path.exists() else None
    dyn = None
    roar_dmc = None
    roar_soft_dmc = None
    if z2_bytes is not None:
        import feud_hooks
        dyn = feud_hooks.build_dynamic_assets(z2_bytes, raw)
        roar_wav = Path(__file__).resolve().parent.parent / 'assets' / 'roar.wav'
        if roar_wav.is_file():
            import roar_sample
            roar_dmc, _ = roar_sample.convert(roar_wav, out_path.parent)
            assert len(roar_dmc) <= 0xE544 - 0xDCC0, f'roar.dmc too large for $DCC0-$E543: {len(roar_dmc)}'
            roar_soft_dmc, _ = roar_sample.convert_soft(roar_wav, out_path.parent)
            assert len(roar_soft_dmc) <= 0xECC6 - 0xE940, f'roar_soft.dmc too large for $E940-$ECC5: {len(roar_soft_dmc)}'
    prg, chr_rom = patch_feud_prg_and_chr(
        raw[16 : 16 + 32768],
        raw[16 + 32768 : 16 + 32768 + 131072],
        z2_bytes,
        barba_json,
        standalone=dyn is not None,
        wram_syms=dyn['wram_syms'] if dyn is not None else None,
        celeb_syms=dyn['celeb_syms'] if (dyn is not None and roar_dmc is not None) else None,
    )

    wram_code = assemble_feud_wram_code(
        0x0000,
        standalone_stub=True,
        wram_syms=dyn['wram_syms'] if dyn is not None else None,
    )
    assert len(wram_code) <= 0x300

    # Stage 1 ($FFC5, 13 bytes of 0xFF padding): unlock $5FFx, enter MMC3 256K mode, jump to Stage 2
    a_s1 = Asm6502(STANDALONE_BOOT_STAGE1)
    a_s1.emit(0xA9, 0x80, 0x8D, 0x01, 0xA0)  # LDA #$80; STA $A001
    a_s1.emit(0xA9, 0x01, 0x8D, 0xF0, 0x5F)  # LDA #$01; STA $5FF0
    a_s1.emit(0x4C, STANDALONE_BOOT_STAGE2 & 0xFF, STANDALONE_BOOT_STAGE2 >> 8)
    stage1 = a_s1.finish()
    assert len(stage1) == 13

    # Stage 2 ($FFE2, 20 bytes of 0x00 padding): map PRG bank 4 to $8000, jump to copy stub
    a_s2 = Asm6502(STANDALONE_BOOT_STAGE2)
    a_s2.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x04, 0x8D, 0x01, 0x80)
    a_s2.emit(0x4C, STANDALONE_COPY_ADDR & 0xFF, STANDALONE_COPY_ADDR >> 8)
    stage2 = a_s2.finish()
    assert len(stage2) == 13

    # Copy stub ($8300 in PRG bank 4): copy wram_code to $7800-$7AFF and jump to FEUD_BOOT
    a_cp = Asm6502(STANDALONE_COPY_ADDR)
    a_cp.emit(0x78)                          # SEI
    a_cp.emit(0xA9, 0xA3, 0x8D, 0x01, 0xA0)  # WRAM bank 3
    a_cp.emit(0xA2, 0x00)                    # LDX #$00
    a_cp.label('cp_loop')
    for page in range(3):
        a_cp.emit(0xBD, 0x00, 0x80 + page)
        a_cp.emit(0x9D, 0x00, (FEUD_WRAM_CODE_BASE >> 8) + page)
    if dyn is not None:
        for page in range(5):
            a_cp.emit(0xBD, 0x00, 0x84 + page)
            a_cp.emit(0x9D, 0x00, 0x7B + page)
        a_cp.emit(0xBD, 0x00, 0x9F)
        a_cp.emit(0x9D, 0x00, 0x74)
        if roar_dmc is not None:
            for page in range(4):
                a_cp.emit(0xBD, 0x00, 0x9B + page)
                a_cp.emit(0x9D, 0x00, 0x70 + page)
    a_cp.emit(0xE8)                          # INX
    a_cp.branch(0xD0, 'cp_loop')             # BNE cp_loop
    a_cp.emit(0xA9, 0x00, 0x8D, 0xF1, 0x5F, 0x8D, 0xF2, 0x5F)
    a_cp.emit(0x4C, FEUD_BOOT & 0xFF, FEUD_BOOT >> 8)
    copy_stub = a_cp.finish()
    assert len(copy_stub) <= 0x100

    prg512 = bytearray(b'\xFF' * (512 * 1024))
    prg512[0 : 16384] = prg[0:16384]
    prg512[32768 : 32768 + len(wram_code)] = wram_code
    prg512[32768 + 0x300 : 32768 + 0x300 + len(copy_stub)] = copy_stub
    if dyn is not None:
        wram_extra = dyn['wram_extra']
        pal_wram = dyn['pal_wram']
        celeb_wram = dyn['celeb_wram']
        bank4_code = dyn['bank4_code']
        cast_banks = dyn['cast_banks']
        assert len(wram_extra) <= 0x0500
        assert len(pal_wram) <= 0x0100
        assert len(celeb_wram) <= 0x0400
        assert len(bank4_code) <= (0x1200 if roar_dmc is not None else 0x1700)
        assert 1 <= len(cast_banks) <= 25
        prg512[32768 + 0x400 : 32768 + 0x400 + len(wram_extra)] = wram_extra
        prg512[32768 + 0x900 : 32768 + 0x900 + len(bank4_code)] = bank4_code
        prg512[32768 + 0x1F00 : 32768 + 0x1F00 + len(pal_wram)] = pal_wram
        if roar_dmc is not None:
            prg512[32768 + 0x1B00 : 32768 + 0x1B00 + len(celeb_wram)] = celeb_wram
        for i, bank in enumerate(cast_banks):
            assert len(bank) == 8192
            off = (5 + i) * 8192
            assert off + 8192 <= 240 * 1024
            prg512[off : off + 8192] = bank
    for top_base in (240 * 1024, 256 * 1024 + 240 * 1024):
        prg512[top_base : top_base + 16384] = prg[16384:32768]
        s1_off = top_base + (STANDALONE_BOOT_STAGE1 - 0xC000)
        assert prg512[s1_off : s1_off + len(stage1)] == b'\xFF' * len(stage1)
        prg512[s1_off : s1_off + len(stage1)] = stage1
        s2_off = top_base + (STANDALONE_BOOT_STAGE2 - 0xC000)
        assert prg512[s2_off : s2_off + len(stage2)] == b'\x00' * len(stage2)
        prg512[s2_off : s2_off + len(stage2)] = stage2
    if roar_dmc is not None:
        # Upper 256KB ($5FF1=$10): keep $C000-$DCAB & $E544-$FFFF intact; place roar.dmc at $DCC0
        # (over replaced DYN blocks 0..79) and roar_soft.dmc at $E940 (over replaced DYN blocks 107..152).
        prg512[256 * 1024 : 256 * 1024 + 16384] = prg[0:16384]
        up_top = 256 * 1024 + 240 * 1024
        prg512[up_top + 0x1CC0 : up_top + 0x1CC0 + len(roar_dmc)] = roar_dmc
        if roar_soft_dmc is not None:
            prg512[up_top + 0x2940 : up_top + 0x2940 + len(roar_soft_dmc)] = roar_soft_dmc
    prg512[0x7FFFC:0x7FFFE] = bytes([STANDALONE_BOOT_STAGE1 & 0xFF, STANDALONE_BOOT_STAGE1 >> 8])

    chr256 = bytearray(b'\x00' * (256 * 1024))
    chr256[0 : 131072] = chr_rom

    hdr = bytearray(16)
    hdr[0:4] = b'NES\x1a'
    hdr[4] = 32     # 32 * 16KB = 512KB PRG
    hdr[5] = 32     # 32 * 8KB = 256KB CHR
    hdr[6] = 0x03   # Vertical mirroring + battery
    hdr[7] = 0xB8   # NES 2.0 + mapper 176
    hdr[10] = 0x90  # 32KB battery PRG-RAM
    if dyn is not None:
        hdr[11] = 0x09  # 32KB unbattery CHR-RAM (64 << 9)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(hdr) + bytes(prg512) + bytes(chr256))
    return out_path


FEUD_PORTAL_NMI      = 0x7500
FEUD_PORTAL_WIN      = 0x7560
FEUD_PORTAL_RETURN   = 0x7570
FEUD_PORTAL_PAD_TMP  = 0x75FD
FEUD_PORTAL_DEB      = 0x75FE
FEUD_PORTAL_WIN_FLAG = 0x75FF


def _assemble_feud_portal_wram(
    restore_addr: int,
    *,
    reward_addr: int = FEUD_REWARD_ADDR,
    reward_magic: int = FEUD_REWARD_MAGIC,
    restore_r6: int = 0x0C,
    restore_r7: int = 0x0D,
) -> bytes:
    """Assemble the $7500-$75FF portal NMI/win/return helper for Barba's Beef."""
    out = bytearray(b'\xFF' * 0x100)

    def place(addr: int, data: bytes, limit: int) -> None:
        off = addr - FEUD_PORTAL_NMI
        assert off + len(data) <= limit - FEUD_PORTAL_NMI, f'Feud portal WRAM overflow at ${addr:04X}'
        out[off : off + len(data)] = data

    # 1. FEUD_PORTAL_NMI ($7500): 60-frame debounce, then Start+Select -> FEUD_PORTAL_RETURN
    a = Asm6502(FEUD_PORTAL_NMI)
    a.emit(0xAD, FEUD_PORTAL_DEB & 0xFF, FEUD_PORTAL_DEB >> 8)
    a.emit(0xC9, 0x3C)
    a.branch(0xB0, 'chk_pad')
    a.emit(0xEE, FEUD_PORTAL_DEB & 0xFF, FEUD_PORTAL_DEB >> 8)
    a.branch(0xD0, 'resume')
    a.label('chk_pad')
    a.emit(0xA9, 0x01, 0x8D, 0x16, 0x40, 0xA9, 0x00, 0x8D, 0x16, 0x40)
    a.emit(0x8D, FEUD_PORTAL_PAD_TMP & 0xFF, FEUD_PORTAL_PAD_TMP >> 8)
    a.emit(0xA2, 0x08)
    a.label('pad_loop')
    a.emit(0xAD, 0x16, 0x40, 0x4A)
    a.emit(0x2E, FEUD_PORTAL_PAD_TMP & 0xFF, FEUD_PORTAL_PAD_TMP >> 8)
    a.emit(0xCA)
    a.branch(0xD0, 'pad_loop')
    a.emit(0xAD, FEUD_PORTAL_PAD_TMP & 0xFF, FEUD_PORTAL_PAD_TMP >> 8)
    a.emit(0x29, 0x30, 0xC9, 0x30)
    a.branch(0xD0, 'resume')
    a.emit(0x68, 0x68, 0x68)  # pop Y, X, A pushed by Feud NMI
    a.emit(0xA9, 0x00, 0x8D, FEUD_PORTAL_WIN_FLAG & 0xFF, FEUD_PORTAL_WIN_FLAG >> 8)
    a.emit(0x4C, FEUD_PORTAL_RETURN & 0xFF, FEUD_PORTAL_RETURN >> 8)
    a.label('resume')
    a.emit(0x68, 0xA8, 0x68, 0xAA, 0x68, 0x40)  # PLA; TAY; PLA; TAX; PLA; RTI
    place(FEUD_PORTAL_NMI, a.finish(), FEUD_PORTAL_WIN)

    # 2. FEUD_PORTAL_WIN ($7560)
    a = Asm6502(FEUD_PORTAL_WIN)
    a.emit(0xA9, reward_magic, 0x8D, FEUD_PORTAL_WIN_FLAG & 0xFF, FEUD_PORTAL_WIN_FLAG >> 8)
    a.emit(0x4C, FEUD_PORTAL_RETURN & 0xFF, FEUD_PORTAL_RETURN >> 8)
    place(FEUD_PORTAL_WIN, a.finish(), FEUD_PORTAL_RETURN)

    # 3. FEUD_PORTAL_RETURN ($7570)
    a = Asm6502(FEUD_PORTAL_RETURN)
    a.emit(0x78, 0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20, 0x8D, 0x15, 0x40, 0x8D, 0x00, 0xE0)
    a.emit(0xAE, FEUD_PORTAL_WIN_FLAG & 0xFF, FEUD_PORTAL_WIN_FLAG >> 8)
    tramp = (
        bytes.fromhex('a9 80 8d 01 a0 8a f0 03 8d')
        + reward_addr.to_bytes(2, 'little')
        + bytes.fromhex('a9 01 8d f0 5f a9 00 8d f1 5f 8d f2 5f')
        + bytes([0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, restore_r6, 0x8D, 0x01, 0x80])
        + bytes([0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, restore_r7, 0x8D, 0x01, 0x80])
        + bytes.fromhex('a9 a0 8d 01 a0 4c')
        + restore_addr.to_bytes(2, 'little')
    )
    a.emit(0xA0, len(tramp) - 1)
    a.label('cp')
    a.abs_ref(0xB9, 'tramp_data')
    a.emit(0x99, 0x00, 0x03, 0x88)
    a.branch(0x10, 'cp')
    a.emit(0x4C, 0x00, 0x03)
    a.label('tramp_data')
    a.emit(*tramp)
    place(FEUD_PORTAL_RETURN, a.finish(), FEUD_PORTAL_NMI + 0x100)
    return bytes(out)


def patch_feud_for_combined(
    feud_bytes: bytes,
    z2_bytes: bytes,
    restore_addr: int,
    *,
    base_5ff1: int = 0xC0,
    roar_5ff1: int = 0xD0,
    base_5ff2: int = 0x80,
    reward_addr: int = 0x63B2,
    reward_magic: int = FEUD_REWARD_MAGIC,
    barba_json: Path | None = None,
) -> tuple[bytes, bytes, bytes]:
    """Build (prg_256k, roar_prg_256k, chr_128k) for Family Feud: Barba Edition inside barba.nes."""
    assert feud_bytes[:4] == b'NES\x1a'
    import feud_hooks
    import roar_sample

    dyn = feud_hooks.build_dynamic_assets(
        z2_bytes,
        feud_bytes,
        base_5ff1=base_5ff1,
        roar_5ff1=roar_5ff1,
    )
    root = Path(__file__).resolve().parent.parent
    roar_wav = root / 'assets' / 'roar.wav'
    roar_out = root / 'build' / 'subgames'
    roar_out.mkdir(parents=True, exist_ok=True)
    roar_dmc, _ = roar_sample.convert(roar_wav, roar_out)
    assert len(roar_dmc) <= 0xE544 - 0xDCC0
    roar_soft_dmc, _ = roar_sample.convert_soft(roar_wav, roar_out)
    assert len(roar_soft_dmc) <= 0xECC6 - 0xE940

    prg, chr_rom = patch_feud_prg_and_chr(
        feud_bytes[16 : 16 + 32768],
        feud_bytes[16 + 32768 : 16 + 32768 + 131072],
        z2_bytes,
        barba_json,
        standalone=True,
        wram_syms=dyn['wram_syms'],
        celeb_syms=dyn['celeb_syms'],
        win_hook_addr=FEUD_PORTAL_WIN,
    )

    wram_code = assemble_feud_wram_code(
        restore_addr,
        standalone_stub=True,
        wram_syms=dyn['wram_syms'],
        nmi_exit_addr=FEUD_PORTAL_NMI,
    )
    assert len(wram_code) <= 0x300
    portal_wram = _assemble_feud_portal_wram(
        restore_addr,
        reward_addr=reward_addr,
        reward_magic=reward_magic,
    )

    # Copy stub ($8300 in PRG bank 4): copy wram_code, wram_extra, pal_wram, celeb_wram, and Bank 3 portal_wram
    a_cp = Asm6502(STANDALONE_COPY_ADDR)
    a_cp.emit(0x78)                          # SEI
    a_cp.emit(0xA9, 0x83, 0x8D, 0x01, 0xA0)  # WRAM bank 3 + unlock $5FF0-$5FF3
    a_cp.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x03, 0x8D, 0x01, 0x80)  # R7 = 3 ($A000-$BFFF)
    a_cp.emit(0xA2, 0x00)                    # LDX #$00
    a_cp.label('cp_loop')
    for page in range(3):
        a_cp.emit(0xBD, 0x00, 0x80 + page)
        a_cp.emit(0x9D, 0x00, (FEUD_WRAM_CODE_BASE >> 8) + page)
    for page in range(5):
        a_cp.emit(0xBD, 0x00, 0x84 + page)
        a_cp.emit(0x9D, 0x00, 0x7B + page)
    a_cp.emit(0xBD, 0x00, 0x9F)
    a_cp.emit(0x9D, 0x00, 0x74)
    for page in range(4):
        a_cp.emit(0xBD, 0x00, 0x9B + page)
        a_cp.emit(0x9D, 0x00, 0x70 + page)
    a_cp.emit(0xBD, 0x00, 0xA0)
    a_cp.emit(0x9D, 0x00, 0x75)
    a_cp.emit(0xE8)
    a_cp.branch(0xD0, 'cp_loop')
    a_cp.emit(0xA9, 0x00)
    a_cp.emit(0x8D, FEUD_PORTAL_DEB & 0xFF, FEUD_PORTAL_DEB >> 8)
    a_cp.emit(0x8D, FEUD_PORTAL_WIN_FLAG & 0xFF, FEUD_PORTAL_WIN_FLAG >> 8)
    a_cp.emit(0xA9, base_5ff1, 0x8D, 0xF1, 0x5F)
    a_cp.emit(0xA9, base_5ff2, 0x8D, 0xF2, 0x5F)
    a_cp.emit(0x4C, FEUD_BOOT & 0xFF, FEUD_BOOT >> 8)
    copy_stub = a_cp.finish()
    assert len(copy_stub) <= 0x100

    prg256 = bytearray(b'\xFF' * (256 * 1024))
    prg256[0 : 16384] = prg[0:16384]
    prg256[3 * 8192 : 3 * 8192 + 0x100] = portal_wram
    prg256[32768 : 32768 + len(wram_code)] = wram_code
    prg256[32768 + 0x300 : 32768 + 0x300 + len(copy_stub)] = copy_stub
    prg256[32768 + 0x400 : 32768 + 0x400 + len(dyn['wram_extra'])] = dyn['wram_extra']
    prg256[32768 + 0x900 : 32768 + 0x900 + len(dyn['bank4_code'])] = dyn['bank4_code']
    prg256[32768 + 0x1F00 : 32768 + 0x1F00 + len(dyn['pal_wram'])] = dyn['pal_wram']
    prg256[32768 + 0x1B00 : 32768 + 0x1B00 + len(dyn['celeb_wram'])] = dyn['celeb_wram']
    for i, bank in enumerate(dyn['cast_banks']):
        off = (5 + i) * 8192
        assert off + 8192 <= 240 * 1024
        prg256[off : off + 8192] = bank
    prg256[240 * 1024 : 256 * 1024] = prg[16384:32768]

    roar256 = bytearray(b'\xFF' * (256 * 1024))
    roar256[0 : 16384] = prg[0:16384]
    roar256[240 * 1024 : 256 * 1024] = prg[16384:32768]
    roar256[240 * 1024 + 0x1CC0 : 240 * 1024 + 0x1CC0 + len(roar_dmc)] = roar_dmc
    roar256[240 * 1024 + 0x2940 : 240 * 1024 + 0x2940 + len(roar_soft_dmc)] = roar_soft_dmc

    return bytes(prg256), bytes(roar256), chr_rom


if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    out = build_standalone(
        root / 'build/subgames/feud.nes',
        root / 'roms/feud.nes',
        root / 'roms/z2.nes',
        root / 'assets/barba.json',
    )
    play_out = root / 'play/standalone/feud-barba.nes'
    play_out.parent.mkdir(parents=True, exist_ok=True)
    play_out.write_bytes(out.read_bytes())
    print(f'Built {out} ({out.stat().st_size} bytes) and {play_out}')
