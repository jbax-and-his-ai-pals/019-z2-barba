"""Assemble and patch Family Feud (USA, MMC1) for the Barba Mapper 176 portal."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from asm6502 import Asm6502
from portal_transitions import build_return_helper, emit_clean_apu_mute, emit_wavy_transition
from subgame_pack import make_rom_header


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

# 35 Zelda II-themed Main Round puzzles: (prefix_idx, question, [(answer, pts), ...])
# prefix_idx ($AFFD): 0=none, 1="Name the ", 2="Name something ", 3="Name a ", 4="Name an ", 5="Tell me ", 6="How many "
ZELDA2_MAIN_PUZZLES: list[tuple[int, str, list[tuple[str, int]]]] = [
    (3, 'PALACE BOSS', [('HORSE[+]HEAD', 29), ('HELMET[+]HEAD', 20), ('REBONACK', 14), ('CAROCK', 11), ('GOOMA', 9), ('BARBA', 7), ('THUNDER[+]BIRD', 6), ('DARK[+]LINK/SHADOW[+]LINK', 4)]),
    (3, 'KEY ITEM', [('CANDLE/TORCH', 26), ('GLOVE/POWER+GLOVE', 19), ('RAFT', 16), ('BOOTS/WATER+BOOTS', 13), ('FLUTE/WHISTLE', 9), ('CROSS', 7), ('HAMMER', 6), ('MAGIC+KEY', 4)]),
    (3, 'SPELL IN ZELDA II', [('SHIELD', 24), ('JUMP', 21), ('LIFE', 17), ('FAIRY', 13), ('FIRE', 10), ('REFLECT', 7), ('SPELL', 5), ('THUNDER', 3)]),
    (3, 'LINK ATTACK TYPE', [('SWORD/SLASH/THRUST', 37), ('DOWN[+]STAB/DOWNWARD+THRUST', 26), ('UP[+]STAB/UPWARD+THRUST', 16), ('BEAM/SWORD+BEAM', 11), ('FIRE[BALLs]', 6), ('THUNDER', 4)]),
    (3, 'PALACE IN HYRULE', [('PARAPA[+PALACE]', 30), ('MIDORO[+PALACE]', 19), ('ISLAND[+PALACE]', 17), ('MAZE[+PALACE]', 13), ('OCEAN[+PALACE]', 9), ('THREE[-]EYE[+ROCK]', 8), ('GREAT[+PALACE]', 4)]),
    (3, 'TOWN IN HYRULE', [('RAURU', 27), ('RUTO', 18), ('SARIA', 16), ('MIDO', 13), ('NABOORU', 11), ('DARUNIA', 7), ('NEW+KASUTO', 5), ('OLD+KASUTO', 3)]),
    (4, 'ATTACK LEVEL XP', [('200', 32), ('500', 21), ('1000', 16), ('2000', 12), ('3000', 9), ('5000', 6), ('8000', 4)]),
    (3, 'MAGIC LEVEL XP', [('100', 28), ('300', 23), ('700', 17), ('1200', 13), ('2200', 10), ('3500', 6), ('6000', 3)]),
    (3, 'LIFE LEVEL XP', [('50', 33), ('150', 21), ('400', 15), ('800', 11), ('1500', 9), ('2500', 7), ('4000', 4)]),
    (3, 'PARAPA PALACE ENEMY', [('STALFOS', 36), ('IRON[+]KNUCKLEs', 27), ('BOTs', 17), ('BITs', 10), ('BUBBLEs', 6), ('RAs', 4)]),
    (3, 'MIDORO OR ISLAND ENEMY', [('IRON[+]KNUCKLEs', 32), ('STALFOS', 23), ('GORIYAs', 19), ('DOOM[+]KNOCKERs', 13), ('MAUs', 8), ('BUBBLEs', 5)]),
    (3, 'MAZE OR OCEAN ENEMY', [('WIZZROBEs', 38), ('MAGOs', 22), ('IRON[+]KNUCKLEs', 16), ('STALFOS', 12), ('BUBBLEs', 7), ('MOAs', 5)]),
    (3, 'GREAT PALACE ENEMY', [('FOKKAs', 40), ('FOKKERUs', 23), ('BUBBLEs', 14), ('BOTs', 11), ('THUNDER[+]BIRD', 8), ('DARK[+]LINK/SHADOW[+]LINK', 4)]),
    (3, 'DEATH MTN ENEMY', [('DARIA[s]', 41), ('TEKTITEs', 24), ('OCTO[ROK]s', 17), ('GORIYAs', 12), ('BUBBLEs', 6)]),
    (4, 'OVERWORLD TILE THAT SPAWNS ENCOUNTERS', [('GRASS/PLAINS', 31), ('SWAMP', 24), ('DESERT', 17), ('FOREST/WOODS', 13), ('GRAVEYARD', 9), ('LA(V/B)A', 6)]),
    (2, 'FOUND IN A TOWN', [('HEALER/[TOWN+]LADY/[OLD+]WOMAN/VILLAGERs/PEOPLE', 34), ('ERROR', 27), ('SAGE/WISE+MAN/OLD+MAN', 17), ('BAGU', 11), ('KNIGHT', 7), ('CHIMNEY', 4)]),
    (3, 'WAY TO CROSS WATER', [('RAFT', 43), ('BOOTS/WATER+BOOTS', 36), ('FAIRY[+SPELL]', 14), ('BRIDGE', 7)]),
    (3, 'DROP FROM AN ENEMY', [('P[-]BAG/POINT+BAG/XP+BAG/EXP+BAG', 46), ('RED[+MAGIC]+JAR/RED+POTION', 27), ('BLUE[+MAGIC]+JAR/BLUE+POTION/[MAGIC+]JAR/POTION', 19), ('KEY', 8)]),
    (3, 'WAY TO HEAL LINK', [('FAIRY', 39), ('LIFE[+SPELL]', 31), ('TOWN+LADY/HEALER', 19), ('LEVEL+UP', 11)]),
    (2, 'THAT GUARDS THE TRIFORCE', [('THUNDER[+]BIRD', 51), ('DARK[+]LINK/SHADOW[+]LINK', 36), ('OLD+MAN/SAGE/IMPA', 13)]),
    (3, 'PLACE YOU FIND A HEART CONTAINER', [('CAVE', 34), ('WATER/OCEAN/RIVER', 26), ('DESERT', 19), ('SWAMP/BUSH', 13), ('TOWN/KASUTO', 8)]),
    (3, 'PLACE YOU FIND A MAGIC CONTAINER', [('DEATH+M(T/TN/OUNTAIN)', 33), ('CAVE', 27), ('RAURU/NORTH+CASTLE', 18), ('MAZE+ISLAND', 13), ('OLD+KASUTO/FOREST', 9)]),
    (3, 'STAT YOU CAN LEVEL UP', [('ATTACK', 43), ('MAGIC', 31), ('LIFE', 26)]),
    (3, 'CHARACTER IN ZELDA II', [('LINK', 36), ('ZELDA', 22), ('BARBA', 16), ('ERROR', 11), ('GAN[N]ON', 7), ('BAGU', 5), ('IMPA', 3)]),
    (2, 'ON THE ZELDA II OVERWORLD', [('ROAD/PATH', 29), ('BRIDGE', 23), ('CAVE', 18), ('TOWN', 14), ('PALACE', 9), ('RIVER/WATER', 7)]),
    (3, 'TRIFORCE', [('COURAGE', 47), ('POWER', 29), ('WISDOM', 24)]),
    (3, 'VANILLA WEST HYRULE SPELL', [('SHIELD', 36), ('JUMP', 27), ('LIFE', 23), ('FAIRY', 14)]),
    (3, 'VANILLA EAST HYRULE SPELL', [('FIRE', 37), ('REFLECT', 28), ('SPELL', 19), ('THUNDER', 16)]),
    (3, 'FLYING CREATURE', [('FAIRY', 34), ('FOKKA', 24), ('THUNDER[+]BIRD', 19), ('FOKKERU', 11), ('ACHE', 6), ('MOA/BUBBLE', 6)]),
    (3, 'REASON TO VISIT A TOWN', [('HEAL/LIFE', 37), ('LEARN+SPELL/GET+SPELL', 29), ('MAGIC', 16), ('TALK/CLUE', 11), ('QUEST/ITEM', 7)]),
    (3, 'WAY TO GET EXTRA XP', [('P[-]BAG/POINT+BAG', 44), ('KILL+ENEMIES', 29), ('PALACE+CRYSTAL/CRYSTAL', 18), ('BOSS', 9)]),
    (4, 'ENEMY WITH A SHIELD OR ARMOR', [('IRON[+]KNUCKLE', 50), ('STALFOS', 23), ('REBONACK', 13), ('FOKKA', 8), ('DOOM[+]KNOCKER', 6)]),
    (2, 'YOU USE THE HAMMER ON', [('ROCK/BOULDER', 53), ('TREE[s]/FOREST/WOODS', 33), ('SPECTACLE+ROCK', 14)]),
    (3, 'DESERT OR SWAMP ENEMY', [('GELDARM', 38), ('LEEVER', 25), ('MOBLIN', 18), ('OCTO[ROK]', 12), ('BOT', 7)]),
    (3, 'HIGH[-]COST MAGIC SPELL', [('THUNDER', 48), ('FAIRY', 24), ('SPELL', 17), ('LIFE', 11)]),
]

# 27 Zelda II-themed Fast Money puzzles
ZELDA2_FM_PUZZLES: list[tuple[int, str, list[tuple[str, int]]]] = [
    (3, 'BARBA EDITION SPELL', [('SCALES', 38), ('METEOR', 29), ('INFERNO', 24), ('WYRML[I]NG', 9)]),
    (3, 'P-BAG XP VALUE', [('200', 43), ('100', 27), ('50', 19), ('500', 11)]),
    (4, 'IRONKNUCKLE COLOR', [('ORANGE', 49), ('RED', 34), ('BLUE', 17)]),
    (3, 'TOWN QUEST ITEM', [('TROPHY', 37), ('MIRROR', 28), ('MEDICINE/WATER+OF+LIFE', 22), ('KID/CHILD', 13)]),
    (2, 'SHOWN ON THE HUD', [('LIFE', 34), ('MAGIC', 27), ('ATTACK', 18), ('XP/EXP/EXPERIENCE', 14), ('NEXT/LEVEL', 7)]),
    (4, 'OVERWORLD ENEMY', [('MOBLINs', 39), ('OCTO[ROK]s', 28), ('TEKTITEs', 21), ('LEEVERs', 12)]),
    (3, 'HYRULE REGION', [('WEST+HYRULE', 40), ('EAST+HYRULE', 31), ('DEATH+M(T/TN/OUNTAIN)', 18), ('MAZE+ISLAND', 11)]),
    (3, 'WAY TO GET A 1-UP', [('1[-]UP[+DOLL]/DOLL', 67), ('9000+XP/9000+EXPERIENCE', 33)]),
    (3, 'COLOR OF MAGIC JAR', [('RED', 57), ('BLUE', 43)]),
    (3, 'DANGEROUS LIQUID', [('LA(V/B)A', 69), ('WATER', 19), ('SWAMP', 12)]),
    (3, 'GIFT FROM A FAIRY', [('LIFE/HEALTH/HEALING', 64), ('MAGIC', 36)]),
    (2, 'ON BARBA TITLE SCREEN', [('BARBA/DRAGON', 50), ('LA(V/B)A', 26), ('CLIFF', 13), ('SWORD', 7), ('STAR[s]', 4)]),
    (2, 'ON GAME OVER SCREEN', [('GAN[N]ON', 40), ('GAME+OVER', 24), ('RETURN+OF+GAN[N]ON/LINK+KEEPS+LA(V/B)A', 17), ('LAUGH', 12), ('LINK', 7)]),
    (4, 'ENEMY PROJECTILE', [('ROCK', 29), ('FIRE[BALLs]', 26), ('AXE/MACE', 19), ('SPEAR/CLUB', 13), ('BOOMERANG', 9), ('BEAM/LIGHTNING', 4)]),
    (3, 'GIFT FROM A WISE MAN', [('SPELL/MAGIC', 47), ('UP[+]STAB/UPWARD+THRUST', 26), ('DOWN[+]STAB/DOWNWARD+THRUST', 19), ('CLUE/HINT', 8)]),
    (3, 'PLACE IN WEST HYRULE', [('PARAPA[+PALACE]', 34), ('RAURU', 29), ('DEATH+M(T/TN/OUNTAIN)', 21), ('MIDORO[+SWAMP]', 16)]),
    (3, 'PLACE IN EAST HYRULE', [('NABOORU', 33), ('DARUNIA', 27), ('MAZE+ISLAND', 24), ('GREAT[+PALACE]', 16)]),
    (0, 'MAX LEVELS FOR A STAT', [('8/EIGHT', 79), ('9/NINE', 21)]),
    (2, 'BARBA BURNS', [('SIGN[s]', 36), ('VILLAGER[s]/PEOPLE', 28), ('FOREST/TREES', 17), ('TOWN[s]', 12), ('ENEMIES', 7)]),
    (4, 'IMPORTANT NPC', [('ERROR', 35), ('BAGU', 27), ('IMPA', 19), ('ZELDA', 13), ('WISE+MAN/OLD+MAN', 6)]),
    (3, 'DIRECTION YOU CAN STAB', [('FORWARD/STRAIGHT', 44), ('DOWN', 37), ('UP', 19)]),
    (2, 'IN PALACE 6', [('BARBA', 42), ('LA(V/B)A', 26), ('WIZZROBE', 14), ('MAGO', 11), ('CRYSTAL', 7)]),
    (3, 'BOSS THAT SHOOTS PROJECTILES', [('BARBA', 40), ('CAROCK', 29), ('THUNDER[+]BIRD', 19), ('HELMET[+]HEAD', 12)]),
    (3, 'COLOR OF AN ENEMY IN ZELDA II', [('RED', 39), ('BLUE', 32), ('ORANGE', 18), ('GREEN', 11)]),
    (2, 'THAT REFILLS AT A PALACE CRYSTAL', [('LIFE', 47), ('MAGIC', 36), ('XP/LEVEL', 17)]),
    (3, 'CREATURE THAT JUMPS AROUND', [('TEKTITE', 46), ('BOT', 27), ('BIT', 14), ('IRON[+]KNUCKLE', 8), ('DARK[+]LINK/SHADOW[+]LINK', 5)]),
    (4, 'INSTANT[-]DEATH HAZARD', [('PIT/FALLING', 54), ('LA(V/B)A', 33), ('WATER', 13)]),
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
    mmc3_pure_chr: bool = False,
) -> bytes:
    """Assemble the WRAM trampoline and hooks at $7800-$7AFF."""
    if standalone_stub and not mmc3_pure_chr:
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
    if not mmc3_pure_chr:
        a.emit(0xA9, 0x00, 0x8D, 0xF0, 0x5F, 0x8D, 0xF1, 0x5F, 0x8D, 0xF2, 0x5F)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, restore_r6, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, restore_r7, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0x80 if mmc3_pure_chr else 0xA0, 0x8D, 0x01, 0xA0)
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

    if mmc3_pure_chr:
        # $7A30..$7AFF: Zelda II CPU family name picker & default P1 name "BARBA"
        mmc3_pick_z2_name = 0x7A30
        mmc3_def_p1_name = 0x7A58
        _pad_to(a, mmc3_pick_z2_name)
        a.emit(0x24, 0x0C); a.branch(0x10, '_mpzn_now')
        a.emit(0x20, 0xF9, 0xCA)
        a.label('_mpzn_now')
        a.emit(0x20, 0xBB, 0x9B)                  # JSR Feud RNG ($01FA)
        a.emit(0xAD, 0xFA, 0x01, 0x29, 0x0F, 0xAA)
        a.abs_ref(0xBC, 'TBL_MMC3_NOFF')          # LDY TBL_MMC3_NOFF,X
        a.emit(0xA2, 0x00)
        a.label('_mpzn_cp')
        a.abs_ref(0xB9, 'TBL_MMC3_NAMES')         # LDA TBL_MMC3_NAMES,Y
        a.emit(0x9D, 0x08, 0x03)                  # STA $0308,X
        a.branch(0x30, '_mpzn_done')              # BMI done (last char has bit 7 set)
        a.emit(0xE8, 0xC8); a.branch(0xD0, '_mpzn_cp')
        a.label('_mpzn_done')
        a.emit(0x60)

        _pad_to(a, mmc3_def_p1_name)
        a.emit(0xA5, 0x0B); a.branch(0xD0, '_mdpn_done')
        a.emit(0xA2, 0x07)
        a.label('_mdpn_chk')
        a.emit(0xB5, 0x48, 0x29, 0x7F, 0xC9, 0x41); a.branch(0xD0, '_mdpn_done')
        a.emit(0xCA); a.branch(0x10, '_mdpn_chk')
        a.emit(0xA2, 0x04)
        a.label('_mdpn_cp')
        a.abs_ref(0xBD, 'TBL_MMC3_BARBA'); a.emit(0x9D, 0x00, 0x03, 0xCA)
        a.branch(0x10, '_mdpn_cp')
        a.label('_mdpn_done')
        a.emit(0x4C, 0xD5, 0x96)
        a.label('TBL_MMC3_BARBA'); a.emit(0x42, 0x41, 0x52, 0x42, 0xC1)

        z2_names = (
            'ZELDA', 'LINK', 'GANON', 'RAURU', 'SARIA', 'ERROR', 'BAGU', 'MIDO',
            'DARUNIA', 'IMPA', 'KASUTO', 'NABOORU', 'RUTO', 'FOKKA', 'CAROCK', 'GOOMA',
        )
        offs: list[int] = []
        blob: list[int] = []
        for nm in z2_names:
            offs.append(len(blob))
            bs = [ord(ch) for ch in nm]
            bs[-1] |= 0x80
            blob.extend(bs)
        a.label('TBL_MMC3_NOFF'); a.emit(*offs)
        a.label('TBL_MMC3_NAMES'); a.emit(*blob)
        out = a.finish()
        assert len(out) <= 0x0300, f'MMC3 WRAM overflow: {len(out)} > 0x0300'
        return out

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
    z2_opponents: bool = False,
    patch_win_hook: bool = True,
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
    elif patch_win_hook and not standalone:
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
        apply_barba_cast(buf, cbuf, z2_rom, z2_opponents=z2_opponents)
        if z2_opponents and not standalone:
            import feud_hooks
            feud_hooks._patch_round_title(buf)
            # Force P1 = Family 0 (Barba) and CPU = Family 1 or 2 (Zelda II opponents)
            roll_both = bytes([0xA9, 0x00, 0x8D, 0x15, 0x03, 0x20, 0xBB, 0x9B, 0xAD, 0xFA, 0x01, 0x29, 0x01, 0x18, 0x69, 0x01, 0x8D, 0x16, 0x03, 0x60])
            buf[0xC9DE - 0x8000 : 0xC9DE - 0x8000 + len(roll_both)] = roll_both
            roll_p1 = bytes([0xA9, 0x00, 0x8D, 0x15, 0x03, 0x60])
            buf[0xCA0C - 0x8000 : 0xCA0C - 0x8000 + len(roll_p1)] = roll_p1
            roll_cpu = bytes([0x20, 0xBB, 0x9B, 0xAD, 0xFA, 0x01, 0x29, 0x01, 0x18, 0x69, 0x01, 0x8D, 0x16, 0x03, 0x60])
            buf[0xCA22 - 0x8000 : 0xCA22 - 0x8000 + len(roll_cpu)] = roll_cpu
            # Zelda II CPU family name ($7A30) + default P1 name "BARBA" ($7A58)
            buf[0x9653 - 0x8000 : 0x9659 - 0x8000] = bytes([0x20, 0x30, 0x7A, 0x4C, 0xBE, 0x97])
            buf[0x96B3 - 0x8000 : 0x96B6 - 0x8000] = bytes([0x20, 0x58, 0x7A])
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


def _build_standalone_mmc3(
    out_path: Path,
    raw: bytes,
    z2_bytes: bytes | None,
    barba_json: Path | None,
    build_number: int | None = None,
) -> Path:
    """Build a classic iNES 1.0 Mapper 4 (MMC3, 256KB PRG + 256KB CHR-ROM + DPCM roars) Feud ROM."""
    import feud_hooks
    import feud_mmc3
    import feud_wram
    import roar_sample
    from feud_art import patch_chr0b_blue_k

    assert z2_bytes is not None, 'roms/z2.nes is required for MMC3 Barba build'

    roar_wav = Path(__file__).resolve().parent.parent / 'assets' / 'roar.wav'
    roar_dmc = None
    roar_soft_dmc = None
    if roar_wav.is_file():
        roar_dir = Path(__file__).resolve().parent.parent / 'build' / 'subgames'
        roar_dir.mkdir(parents=True, exist_ok=True)
        roar_dmc, _ = roar_sample.convert(roar_wav, roar_dir)
        assert len(roar_dmc) <= 0xE544 - 0xDCC0, f'roar.dmc too large for $DCC0-$E543: {len(roar_dmc)}'
        roar_soft_dmc, _ = roar_sample.convert_soft(roar_wav, roar_dir)
        assert len(roar_soft_dmc) <= 0xECC6 - 0xE940, f'roar_soft.dmc too large for $E940-$ECC5: {len(roar_soft_dmc)}'

    wram_extra, wram_syms = feud_wram.assemble_wram_extra(mmc3_pure_chr=True)
    pal_wram, pal_syms = feud_wram.assemble_pal_wram()
    all_wram_syms = {**wram_syms, **pal_syms}
    celeb_wram = None
    celeb_syms = None
    if roar_dmc is not None:
        celeb_wram, celeb_syms = feud_wram.assemble_celeb_wram(mmc3_pure_chr=True)

    prg, chr_rom = patch_feud_prg_and_chr(
        raw[16 : 16 + 32768],
        raw[16 + 32768 : 16 + 32768 + 131072],
        z2_bytes,
        barba_json,
        standalone=False,
        win_hook_addr=None,
        z2_opponents=False,
        patch_win_hook=False,
    )
    prg_buf = bytearray(prg)
    chr_buf = bytearray(chr_rom)
    patch_chr0b_blue_k(chr_buf)
    feud_hooks.apply_feud_prg_hooks(prg_buf, all_wram_syms, celeb_syms, mmc3_4x12_fo=False)

    cast_assets = feud_mmc3.build_mmc3_cast_assets(bytes(prg_buf), bytes(chr_buf), raw, z2_bytes)
    prg_patched_buf = bytearray(cast_assets['prg_patched'])  # type: ignore[arg-type]
    chr256_buf = bytearray(cast_assets['chr256'])            # type: ignore[arg-type]
    if build_number is not None:
        from feud_art import apply_title_build_number
        apply_title_build_number(prg_patched_buf, chr256_buf, build_number)
    prg_patched = bytes(prg_patched_buf)
    chr256 = bytes(chr256_buf)
    bank5: bytes = cast_assets['bank5']              # type: ignore[assignment]
    bank6: bytes = cast_assets['bank6']              # type: ignore[assignment]

    bank4_code = feud_mmc3.assemble_mmc3_bank4(cast_assets)
    wram_code = feud_mmc3.assemble_mmc3_wram_code(all_wram_syms)
    assert len(wram_code) <= 0x300
    assert len(wram_extra) <= 0x500
    assert len(pal_wram) <= 0x100
    assert len(bank4_code) <= 0x1200

    # Stage 1 ($FFC5, <=13 bytes of 0xFF padding): SEI; CLD; enable MMC3 WRAM; disable IRQ; jump to Stage 2
    a_s1 = Asm6502(STANDALONE_BOOT_STAGE1)
    a_s1.emit(0x78, 0xD8, 0xA9, 0x80, 0x8D, 0x01, 0xA0, 0x8D, 0x00, 0xE0)
    a_s1.emit(0x4C, STANDALONE_BOOT_STAGE2 & 0xFF, STANDALONE_BOOT_STAGE2 >> 8)
    stage1 = a_s1.finish()
    assert len(stage1) <= 13

    # Stage 2 ($FFE2, <=20 bytes of 0x00 padding): map PRG bank 4 to $8000, jump to copy stub
    a_s2 = Asm6502(STANDALONE_BOOT_STAGE2)
    a_s2.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x04, 0x8D, 0x01, 0x80)
    a_s2.emit(0x4C, STANDALONE_COPY_ADDR & 0xFF, STANDALONE_COPY_ADDR >> 8)
    stage2 = a_s2.finish()
    assert len(stage2) <= 20

    # Copy stub ($8300 in PRG bank 4): copy wram_code, wram_extra, pal_wram, celeb_wram -> WRAM -> FEUD_BOOT
    a_cp = Asm6502(STANDALONE_COPY_ADDR)
    a_cp.emit(0x78)                          # SEI
    a_cp.emit(0xA9, 0x80, 0x8D, 0x01, 0xA0)  # Enable MMC3 WRAM
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
    if celeb_wram is not None:
        for page in range(4):
            a_cp.emit(0xBD, 0x00, 0x9B + page)
            a_cp.emit(0x9D, 0x00, 0x70 + page)
    a_cp.emit(0xE8)                          # INX
    a_cp.branch(0xD0, 'cp_loop')             # BNE cp_loop
    a_cp.emit(0x4C, FEUD_BOOT & 0xFF, FEUD_BOOT >> 8)
    copy_stub = a_cp.finish()
    assert len(copy_stub) <= 0x100

    prg256 = bytearray(b'\xFF' * (256 * 1024))
    prg256[0 : 16384] = prg_patched[0:16384]
    prg256[32768 : 32768 + len(wram_code)] = wram_code
    prg256[32768 + 0x300 : 32768 + 0x300 + len(copy_stub)] = copy_stub
    prg256[32768 + 0x400 : 32768 + 0x400 + len(wram_extra)] = wram_extra
    prg256[32768 + 0x900 : 32768 + 0x900 + len(bank4_code)] = bank4_code
    if celeb_wram is not None:
        assert len(celeb_wram) <= 0x400
        prg256[32768 + 0x1B00 : 32768 + 0x1B00 + len(celeb_wram)] = celeb_wram
    prg256[32768 + 0x1F00 : 32768 + 0x1F00 + len(pal_wram)] = pal_wram
    prg256[5 * 8192 : 6 * 8192] = bank5
    prg256[6 * 8192 : 7 * 8192] = bank6

    top_base = 240 * 1024
    prg256[top_base : top_base + 16384] = prg_patched[16384:32768]
    if roar_dmc is not None:
        prg256[top_base + 0x1CC0 : top_base + 0x1CC0 + len(roar_dmc)] = roar_dmc
    if roar_soft_dmc is not None:
        prg256[top_base + 0x2940 : top_base + 0x2940 + len(roar_soft_dmc)] = roar_soft_dmc

    s1_off = top_base + (STANDALONE_BOOT_STAGE1 - 0xC000)
    assert prg256[s1_off : s1_off + len(stage1)] == b'\xFF' * len(stage1)
    prg256[s1_off : s1_off + len(stage1)] = stage1
    s2_off = top_base + (STANDALONE_BOOT_STAGE2 - 0xC000)
    assert prg256[s2_off : s2_off + len(stage2)] == b'\x00' * len(stage2)
    prg256[s2_off : s2_off + len(stage2)] = stage2
    prg256[0x3FFFC:0x3FFFE] = bytes([STANDALONE_BOOT_STAGE1 & 0xFF, STANDALONE_BOOT_STAGE1 >> 8])

    hdr = make_rom_header(len(prg256), len(chr256), mapper='mmc3', vertical_mirroring=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(hdr) + bytes(prg256) + chr256)
    return out_path


def build_standalone(
    out_path: Path,
    src_rom: Path,
    z2_rom_path: Path | None = None,
    barba_json: Path | None = None,
    *,
    mapper: str = '176',
    build_number: int | None = None,
) -> Path:
    """Build a standalone Family Feud: Barba Edition ROM (Mapper 176 or pure CHR-ROM MMC3)."""
    from build_history import HISTORY_FILE, next_subgame_build_number, record_subgame_build
    import hashlib
    record_this = build_number is None
    if build_number is None:
        build_number = next_subgame_build_number(HISTORY_FILE, 'feud')
    raw = src_rom.read_bytes()
    assert raw[:4] == b'NES\x1a'
    z2_bytes = z2_rom_path.read_bytes() if z2_rom_path and z2_rom_path.exists() else None
    if mapper == 'mmc3':
        res = _build_standalone_mmc3(out_path, raw, z2_bytes, barba_json, build_number=build_number)
        if record_this:
            record_subgame_build(HISTORY_FILE, 'feud', build_number, mapper, res, hashlib.sha256(res.read_bytes()).hexdigest())
        return res
    dyn = None
    roar_dmc = None
    roar_soft_dmc = None
    if z2_bytes is not None:
        import feud_hooks
        dyn = feud_hooks.build_dynamic_assets(z2_bytes, raw)
        roar_wav = Path(__file__).resolve().parent.parent / 'assets' / 'roar.wav'
        if roar_wav.is_file():
            import roar_sample
            roar_dir = Path(__file__).resolve().parent.parent / 'build' / 'subgames'
            roar_dir.mkdir(parents=True, exist_ok=True)
            roar_dmc, _ = roar_sample.convert(roar_wav, roar_dir)
            assert len(roar_dmc) <= 0xE544 - 0xDCC0, f'roar.dmc too large for $DCC0-$E543: {len(roar_dmc)}'
            roar_soft_dmc, _ = roar_sample.convert_soft(roar_wav, roar_dir)
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
    prg_buf = bytearray(prg)
    chr_buf = bytearray(chr_rom)
    if build_number is not None:
        from feud_art import apply_title_build_number
        apply_title_build_number(prg_buf, chr_buf, build_number)
    prg = bytes(prg_buf)
    chr_rom = bytes(chr_buf)

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

    out_bytes = bytes(hdr) + bytes(prg512) + bytes(chr256)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(out_bytes)
    if record_this:
        record_subgame_build(HISTORY_FILE, 'feud', build_number, mapper, out_path, hashlib.sha256(out_bytes).hexdigest())
    return out_path


FEUD_PORTAL_NMI      = 0x7500
FEUD_PORTAL_WIN      = 0x7580
FEUD_PORTAL_RETURN   = 0x7590
FEUD_PORTAL_WIPE     = 0x75FC
FEUD_PORTAL_PAD_TMP  = 0x75FD
FEUD_PORTAL_DEB      = 0x75FE
FEUD_PORTAL_WIN_FLAG = 0x75FF
FEUD_B3_WIPE_IN      = 0x8100
FEUD_B3_MELT_OUT     = 0x8200


def _assemble_feud_portal_bank3(
    restore_addr: int,
    *,
    reward_addr: int = FEUD_REWARD_ADDR,
    restore_r6: int = 0x0C,
    restore_r7: int = 0x0D,
    game_id: int | None = None,
) -> bytes:
    """Assemble Bank 3 ($8100-$84FF) wipe-in and melt-out routines for Feud combined mode."""
    out = bytearray(b'\xFF' * 0x400)

    def place(addr: int, data: bytes, limit: int) -> None:
        off = addr - FEUD_B3_WIPE_IN
        assert off + len(data) <= limit - FEUD_B3_WIPE_IN, (
            f'Feud Bank 3 overflow at ${addr:04X}: ${addr + len(data):04X} > ${limit:04X}'
        )
        out[off : off + len(data)] = data

    # 1. FEUD_B3_WIPE_IN ($8100): 30-frame top-down wavy reveal ending at VBlank start
    aw = Asm6502(FEUD_B3_WIPE_IN)
    emit_wavy_transition(
        aw,
        prefix='fw',
        frame_addr=0x75F8,
        cut_addr=0x75F9,
        band_addr=0x75FA,
        direction='in',
        ppuctrl_addr=0x0C,
        ppuctrl_mask=0x7C,
        ppumask_addr=0x0D,
        end_on_vblank=True,
    )
    place(FEUD_B3_WIPE_IN, aw.finish(), FEUD_B3_MELT_OUT)

    # 2. FEUD_B3_MELT_OUT ($8200): 30-frame bottom-up melt, blank PPU, run $0300 return helper
    am = Asm6502(FEUD_B3_MELT_OUT)
    emit_wavy_transition(
        am,
        prefix='fm',
        frame_addr=0x75F8,
        cut_addr=0x75F9,
        band_addr=0x75FA,
        direction='out',
        ppuctrl_addr=0x0C,
        ppuctrl_mask=0x7C,
        ppumask_addr=0x0D,
        emit_rts=False,
    )
    am.emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20)  # $2000=0, $2001=0
    am.emit(0xAE, FEUD_PORTAL_WIN_FLAG & 0xFF, FEUD_PORTAL_WIN_FLAG >> 8)
    tramp = build_return_helper(
        restore_addr,
        reward_addr,
        game_id=game_id,
        win_reg='x',
        restore_r6=restore_r6,
        restore_r7=restore_r7,
    )
    am.emit(0xA0, len(tramp) - 1)
    am.label('cp')
    am.abs_ref(0xB9, 'tramp_data')
    am.emit(0x99, 0x00, 0x03, 0x88)
    am.branch(0x10, 'cp')
    am.emit(0x4C, 0x00, 0x03)
    am.label('tramp_data')
    am.emit(*tramp)
    place(FEUD_B3_MELT_OUT, am.finish(), FEUD_B3_WIPE_IN + 0x400)
    return bytes(out)


def _assemble_feud_portal_wram(
    restore_addr: int,
    *,
    base_5ff1: int = 0x40,
    reward_addr: int = FEUD_REWARD_ADDR,
    reward_magic: int = FEUD_REWARD_MAGIC,
    restore_r6: int = 0x0C,
    restore_r7: int = 0x0D,
) -> bytes:
    """Assemble the $7500-$75FF portal NMI/win/return helper for Barba's Beef."""
    del restore_addr, reward_addr, restore_r6, restore_r7
    out = bytearray(b'\xFF' * 0x100)

    def place(addr: int, data: bytes, limit: int) -> None:
        off = addr - FEUD_PORTAL_NMI
        assert off + len(data) <= limit - FEUD_PORTAL_NMI, f'Feud portal WRAM overflow at ${addr:04X}'
        out[off : off + len(data)] = data

    # 1. FEUD_PORTAL_NMI ($7500): 60-frame debounce, Start+Select -> FEUD_PORTAL_RETURN, and first-frame wipe-in
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
    a.emit(0xAD, FEUD_PORTAL_WIPE & 0xFF, FEUD_PORTAL_WIPE >> 8)
    a.branch(0xD0, 'nmi_rti')
    a.emit(0xA5, 0x0D, 0x29, 0x08)
    a.branch(0xF0, 'nmi_rti')
    a.emit(0xAD, FEUD_PORTAL_DEB & 0xFF, FEUD_PORTAL_DEB >> 8, 0xC9, 0x04)
    a.branch(0x90, 'nmi_rti')
    a.emit(0xEE, FEUD_PORTAL_WIPE & 0xFF, FEUD_PORTAL_WIPE >> 8)
    a.emit(0xA5, 0x0C, 0x29, 0x7F, 0x8D, 0x00, 0x20)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x03, 0x8D, 0x01, 0x80)
    a.emit(0x20, FEUD_B3_WIPE_IN & 0xFF, FEUD_B3_WIPE_IN >> 8)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x00, 0x8D, 0x01, 0x80)
    a.emit(0xA5, 0x0C, 0x8D, 0x00, 0x20)
    a.label('nmi_rti')
    a.emit(0x68, 0xA8, 0x68, 0xAA, 0x68, 0x40)  # PLA; TAY; PLA; TAX; PLA; RTI
    place(FEUD_PORTAL_NMI, a.finish(), FEUD_PORTAL_WIN)

    # 2. FEUD_PORTAL_WIN ($7570)
    a = Asm6502(FEUD_PORTAL_WIN)
    a.emit(0xA9, reward_magic, 0x8D, FEUD_PORTAL_WIN_FLAG & 0xFF, FEUD_PORTAL_WIN_FLAG >> 8)
    a.emit(0x4C, FEUD_PORTAL_RETURN & 0xFF, FEUD_PORTAL_RETURN >> 8)
    place(FEUD_PORTAL_WIN, a.finish(), FEUD_PORTAL_RETURN)

    # 3. FEUD_PORTAL_RETURN ($7580): mute APU, restore base $5FF1 via $0340, map R6=3 -> FEUD_B3_MELT_OUT
    a = Asm6502(FEUD_PORTAL_RETURN)
    a.emit(0x78)
    a.emit(0xA5, 0x0C, 0x29, 0x7F, 0x8D, 0x00, 0x20)
    emit_clean_apu_mute(a)
    fix_stub = bytes([
        0xA9, 0x80, 0x8D, 0x01, 0xA0,        # unlock $5FFx
        0xA9, base_5ff1, 0x8D, 0xF1, 0x5F,   # restore base_5ff1 (in case roar_5ff1 active)
        0xA9, 0x83, 0x8D, 0x01, 0xA0,        # keep WRAM bank 3 + $5FFx unlocked
        0x60,                                # RTS
    ])
    a.emit(0xA2, len(fix_stub) - 1)
    a.label('cp_fix')
    a.abs_ref(0xBD, 'fix_data')
    a.emit(0x9D, 0x40, 0x03, 0xCA)
    a.branch(0x10, 'cp_fix')
    a.emit(0x20, 0x40, 0x03)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x03, 0x8D, 0x01, 0x80)
    a.emit(0x4C, FEUD_B3_MELT_OUT & 0xFF, FEUD_B3_MELT_OUT >> 8)
    a.label('fix_data')
    a.emit(*fix_stub)
    place(FEUD_PORTAL_RETURN, a.finish(), FEUD_PORTAL_WIPE)
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
    enable_transitions: bool = False,
    game_id: int | None = None,
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
        base_5ff1=base_5ff1,
        reward_addr=reward_addr,
        reward_magic=reward_magic,
    )
    del enable_transitions  # Always active in combined build; kept for uniform signature
    portal_bank3 = _assemble_feud_portal_bank3(
        restore_addr,
        reward_addr=reward_addr,
        game_id=game_id,
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
    a_cp.emit(0x8D, FEUD_PORTAL_WIPE & 0xFF, FEUD_PORTAL_WIPE >> 8)
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
    prg256[3 * 8192 + 0x100 : 3 * 8192 + 0x100 + len(portal_bank3)] = portal_bank3
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=None)
    parser.add_argument('--mapper', choices=('176', 'mmc3'), default='176')
    args = parser.parse_args()
    default_out = root / ('play/compat/nes/feud-compat.nes' if args.mapper == 'mmc3' else 'build/subgames/feud.nes')
    out = build_standalone(
        args.out or default_out,
        root / 'roms/feud.nes',
        root / 'roms/z2.nes',
        root / 'assets/barba.json',
        mapper=args.mapper,
    )
    if args.mapper == '176' and args.out is None:
        from bps import write_bps
        play_out = root / 'play/nes/feud.nes'
        play_out.parent.mkdir(parents=True, exist_ok=True)
        play_out.write_bytes(out.read_bytes())
        write_bps(
            root / 'roms/feud.nes',
            play_out,
            out_bps_path=root / 'play/bps/feud.bps',
            metadata='feud | Barba Edition',
        )
        print(f'Built {out} ({out.stat().st_size} bytes) and {play_out}')
    else:
        if args.mapper == 'mmc3' and args.out is None:
            from bps import write_bps
            write_bps(
                root / 'roms/feud.nes',
                out,
                out_bps_path=root / 'play/compat/bps/feud-compat.bps',
                metadata='feud-compat | Barba Edition (MMC3)',
            )
        print(f'Built {out} ({out.stat().st_size} bytes, mapper={args.mapper})')
