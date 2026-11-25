"""Assemble and patch Duck Hunt -> Villager Hunt (MMC3, Mapper 176) for Barba Edition."""
from __future__ import annotations

from pathlib import Path

from duck_art import SPRITE_PAL_BYTES, build_duck_chr_and_tables
from duck_code import (
    FIXED_PAD_BASE,
    ROAR_DMC_ADDR,
    assemble_bank1,
    assemble_fixed_pad,
)
from pack_f13 import Asm6502
import roar_sample


# Fixed entry points in guest WRAM bank ($7800-$7BFF)
DUCK_WRAM_CODE_BASE = 0x7800
DUCK_NMI_HOOK       = 0x7840
DUCK_WIN_HOOK       = 0x7870
DUCK_SEED_RNG       = 0x7880
DUCK_RETURN         = 0x7960
DUCK_BOOT           = 0x7AE0

# Guest WRAM state bytes (in guest WRAM bank)
DUCK_WIN_FLAG       = 0x7FFE  # 0 = Start+Select exit, DUCK_REWARD_MAGIC = round clear exit
DUCK_DEBOUNCE       = 0x7FFF  # 60-frame ($3C) NMI debounce counter

# Barba WRAM bank 0 reward flag (standalone default; combined uses $63B5)
DUCK_REWARD_ADDR    = 0x648F
DUCK_REWARD_MAGIC   = 0x48    # 'H'

# Duck Hunt (USA, NROM-128) addresses
DUCK_ORIG_NMI       = 0xC086
DUCK_ORIG_RESET     = 0xC000
DUCK_WIN_PATCH_ADDR = 0xD39B  # Round clear completion (both normal & 10/10 Perfect paths)
DUCK_PAD1_ZP        = 0x16    # Debounced P1 held buttons (Bit 5 = Select $20, Bit 4 = Start $10)
DUCK_START_SELECT   = 0x30

STANDALONE_RESTORE_ADDR = 0x80F0

ROOT = Path(__file__).resolve().parent.parent


def make_duck_wram_code(
    restore_addr: int,
    *,
    reward_addr: int = DUCK_REWARD_ADDR,
    reward_magic: int = DUCK_REWARD_MAGIC,
    standalone_stub: bool = False,
) -> bytes:
    """Assemble the 1024-byte ($7800-$7BFF) WRAM helper for Villager Hunt."""
    out = bytearray(b'\xFF' * 0x400)

    def place(addr: int, data: bytes, limit: int) -> None:
        off = addr - DUCK_WRAM_CODE_BASE
        assert off + len(data) <= limit - DUCK_WRAM_CODE_BASE, (
            f'Overflow at ${addr:04X}: {off + len(data)} > {limit - DUCK_WRAM_CODE_BASE}'
        )
        out[off : off + len(data)] = data

    # 1. DUCK_NMI_HOOK ($7840): 60-frame guard in $7FFF, then Start+Select ($30 in $16) -> DUCK_RETURN
    a = Asm6502(DUCK_NMI_HOOK)
    a.emit(0x48)                                                # PHA
    a.emit(0xAD, DUCK_DEBOUNCE & 0xFF, DUCK_DEBOUNCE >> 8)      # LDA $7FFF
    a.emit(0xC9, 0x3C)                                          # CMP #$3C (60 frames)
    a.branch(0xB0, 'check_pad')                                 # BCS check_pad
    a.emit(0xEE, DUCK_DEBOUNCE & 0xFF, DUCK_DEBOUNCE >> 8)      # INC $7FFF
    a.branch(0xD0, 'normal_nmi')                                # BNE normal_nmi (always taken)
    a.label('check_pad')
    a.emit(0xA5, DUCK_PAD1_ZP, 0x29, DUCK_START_SELECT, 0xC9, DUCK_START_SELECT)
    a.branch(0xF0, 'do_return')                                 # BEQ do_return
    a.label('normal_nmi')
    a.emit(0x68, 0x4C, DUCK_ORIG_NMI & 0xFF, DUCK_ORIG_NMI >> 8)
    a.label('do_return')
    a.emit(0x68)                                                # PLA
    a.emit(0xA9, 0x00, 0x8D, DUCK_WIN_FLAG & 0xFF, DUCK_WIN_FLAG >> 8)
    a.emit(0x4C, DUCK_RETURN & 0xFF, DUCK_RETURN >> 8)
    place(DUCK_NMI_HOOK, a.finish(), DUCK_WIN_HOOK)

    # 2. DUCK_WIN_HOOK ($7870): called from $D39B when a round is cleared
    a = Asm6502(DUCK_WIN_HOOK)
    a.emit(0xA9, reward_magic)
    a.emit(0x8D, DUCK_WIN_FLAG & 0xFF, DUCK_WIN_FLAG >> 8)
    a.emit(0x4C, DUCK_RETURN & 0xFF, DUCK_RETURN >> 8)
    place(DUCK_WIN_HOOK, a.finish(), DUCK_SEED_RNG)

    # 2b. DUCK_SEED_RNG ($7880): seed 4-byte LFSR $05EC-$05EF from Barba's $7FF0-$7FF3, then JMP $C22B
    a = Asm6502(DUCK_SEED_RNG)
    a.emit(0xA2, 0x03)
    a.label('seed_loop')
    a.emit(0xBD, 0xF0, 0x7F)
    a.emit(0x9D, 0xEC, 0x05)
    a.emit(0xCA)
    a.branch(0x10, 'seed_loop')
    a.emit(0xAD, 0xEC, 0x05, 0x0D, 0xED, 0x05)
    a.branch(0xD0, 'seed_ok')
    a.emit(0xA9, 0x5F, 0x8D, 0xEC, 0x05)
    a.label('seed_ok')
    a.emit(0x4C, 0x2B, 0xC2)
    place(DUCK_SEED_RNG, a.finish(), DUCK_RETURN)

    # 3. DUCK_RETURN ($7960): silence APU/PPU/IRQ, copy RAM trampoline to $0300, restore Barba banks & reward
    a = Asm6502(DUCK_RETURN)
    a.emit(0x78)                                                # SEI
    a.emit(0xA9, 0x00)
    a.emit(0x8D, 0x00, 0x20)                                    # STA $2000 (disable NMI)
    a.emit(0x8D, 0x01, 0x20)                                    # STA $2001 (disable rendering)
    a.emit(0x8D, 0x15, 0x40)                                    # STA $4015 (mute APU/DMC)
    a.emit(0x8D, 0x00, 0xE0)                                    # STA $E000 (disable MMC3 IRQ)
    a.emit(0xAE, DUCK_WIN_FLAG & 0xFF, DUCK_WIN_FLAG >> 8)      # LDX $7FFE
    tramp = (
        bytes.fromhex(
            'a9 80 8d 01 a0 '                                   # LDA #$80; STA $A001 (unlock $5FF0-$5FF3)
            'a9 01 8d f0 5f '                                   # LDA #$01; STA $5FF0 (Barba Lower 2MB)
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
    a.emit(0xA0, len(tramp) - 1)
    a.label('cp_tramp')
    a.abs_ref(0xB9, 'tramp_data')
    a.emit(0x99, 0x00, 0x03)
    a.emit(0x88)
    a.branch(0x10, 'cp_tramp')
    a.emit(0x4C, 0x00, 0x03)
    a.label('tramp_data')
    a.emit(*tramp)
    place(DUCK_RETURN, a.finish(), DUCK_BOOT)

    # 4. DUCK_BOOT ($7AE0): init PPU/APU/MMC3 Vertical mirroring, map PRG banks (R6=2, R7=1) & CHR, JMP $C000
    a = Asm6502(DUCK_BOOT)
    a.emit(0x78, 0xD8)                                          # SEI; CLD
    a.emit(0xA9, 0x00)
    a.emit(0x8D, 0x00, 0x20)                                    # STA $2000
    a.emit(0x8D, 0x01, 0x20)                                    # STA $2001
    a.emit(0x8D, 0x15, 0x40)                                    # STA $4015
    a.emit(0x8D, 0x00, 0xE0)                                    # STA $E000
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0xA0)                        # Vertical mirroring
    # Map R6 = 2 ($8000-$9FFF) and R7 = 1 ($A000-$BFFF); $C000-$FFFF fixed to -2,-1 (banks 30, 31)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x02, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x01, 0x8D, 0x01, 0x80)
    # Initial CHR banks: Title sprites (R0=12), Barba (R1=14), Title BG (R2..R5=4..7)
    for reg, val in ((0, 12), (1, 14), (2, 4), (3, 5), (4, 6), (5, 7)):
        a.emit(0xA9, reg, 0x8D, 0x00, 0x80, 0xA9, val, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0x00)
    a.emit(0x8D, DUCK_DEBOUNCE & 0xFF, DUCK_DEBOUNCE >> 8)
    a.emit(0x8D, DUCK_WIN_FLAG & 0xFF, DUCK_WIN_FLAG >> 8)
    a.emit(0x4C, DUCK_ORIG_RESET & 0xFF, DUCK_ORIG_RESET >> 8)  # JMP $C000
    place(DUCK_BOOT, a.finish(), 0x7C00)

    return bytes(out)


def make_duck_bank0(
    restore_addr: int,
    *,
    wram_bank: int = 0xA3,
    standalone_stub: bool = False,
    reward_addr: int = DUCK_REWARD_ADDR,
) -> bytes:
    """Build 8KB bank 0 ($8000-$9FFF): copies $8100-$84FF -> $7800-$7BFF and jumps to DUCK_BOOT."""
    bank0 = bytearray(b'\xFF' * 8192)
    a = Asm6502(0x8000)
    if standalone_stub:
        a.emit(0x78, 0xD8, 0xA2, 0x1E)
        a.label('cp_ram')
        a.abs_ref(0xBD, 'ram_boot')
        a.emit(0x9D, 0x00, 0x03, 0xCA)
        a.branch(0x10, 'cp_ram')
        a.emit(0x4C, 0x00, 0x03)
        a.label('ram_boot')
        a.emit(0xA9, 0x80, 0x8D, 0x01, 0xA0)
        a.emit(0xA9, 0x01, 0x8D, 0xF0, 0x5F)                    # Standalone 256KB mode ONLY
        a.emit(0xA9, 0x00, 0x8D, 0xF1, 0x5F, 0x8D, 0xF2, 0x5F)
        a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x00, 0x8D, 0x01, 0x80)
        a.abs_ref(0x4C, 'after_mmc3')
        a.label('after_mmc3')
    a.emit(0xA9, wram_bank, 0x8D, 0x01, 0xA0)                   # WRAM bank + lock $5FF0-$5FF3
    a.emit(0xA9, 0x00, 0x85, 0x00, 0x85, 0x02)
    a.emit(0xA9, 0x81, 0x85, 0x01)
    a.emit(0xA9, 0x78, 0x85, 0x03)
    a.emit(0xA2, 0x04, 0xA0, 0x00)
    a.label('cp')
    a.emit(0xB1, 0x00, 0x91, 0x02, 0xC8)
    a.branch(0xD0, 'cp')
    a.emit(0xE6, 0x01, 0xE6, 0x03, 0xCA)
    a.branch(0xD0, 'cp')
    a.emit(0x4C, DUCK_BOOT & 0xFF, DUCK_BOOT >> 8)
    loader = a.finish()
    assert len(loader) <= 0xF0
    bank0[0 : len(loader)] = loader
    if standalone_stub:
        stub = bytes([0x4C, STANDALONE_RESTORE_ADDR & 0xFF, STANDALONE_RESTORE_ADDR >> 8])
        off = STANDALONE_RESTORE_ADDR - 0x8000
        bank0[off : off + len(stub)] = stub
    bank0[0x100 : 0x500] = make_duck_wram_code(
        restore_addr,
        reward_addr=reward_addr,
        standalone_stub=standalone_stub,
    )
    return bytes(bank0)


def _validate_duck_rom(duck_bytes: bytes) -> None:
    assert duck_bytes[:4] == b'NES\x1a', 'Not an iNES ROM'
    assert duck_bytes[4] == 1 and duck_bytes[5] == 1, (
        f'Expected NROM-128 (1x16KB PRG, 1x8KB CHR), got {duck_bytes[4]}x16KB, {duck_bytes[5]}x8KB'
    )
    mapper = (duck_bytes[6] >> 4) | (duck_bytes[7] & 0xF0)
    assert mapper == 0, f'Expected Mapper 0 (NROM), got {mapper}'
    assert (duck_bytes[6] & 0x01) == 1, 'Expected Vertical mirroring'


def _build_villager_hunt_banks(
    duck_bytes: bytes,
    z2_bytes: bytes,
    restore_addr: int,
    *,
    reward_addr: int,
    standalone_stub: bool,
    roar_wav: Path | None = None,
) -> tuple[bytes, bytes]:
    """Build full (prg_256k, chr_32k) for Villager Hunt."""
    _validate_duck_rom(duck_bytes)
    wav_path = roar_wav or (ROOT / 'assets' / 'roar.wav')
    roar_out = ROOT / 'build' / 'subgames' / 'duck_roar'
    roar_dmc, roar_info = roar_sample.convert(wav_path, roar_out)
    assert len(roar_dmc) <= 0xE000 - ROAR_DMC_ADDR, (
        f'roar.dmc ({len(roar_dmc)} B) exceeds ${ROAR_DMC_ADDR:04X}-$DFFF'
    )

    art = build_duck_chr_and_tables(duck_bytes, z2_bytes)
    fixed_pad, fixed_syms = assemble_fixed_pad()
    bank1, b1_syms = assemble_bank1(art, roar_info)

    prg16 = bytearray(duck_bytes[16 : 16 + 16384])

    def patch(addr: int, new: bytes, expected: bytes) -> None:
        off = addr - 0xC000
        actual = bytes(prg16[off : off + len(expected)])
        assert actual == expected, (
            f'Unexpected Duck Hunt bytes at ${addr:04X}: {actual.hex(" ")} != {expected.hex(" ")}'
        )
        prg16[off : off + len(new)] = new

    # Place fixed-bank audio guards at $EF5A
    patch(FIXED_PAD_BASE, fixed_pad, b'\xFF' * len(fixed_pad))

    # Portal / reset / NMI / win / RNG hooks
    patch(
        0xFFFA,
        bytes([DUCK_NMI_HOOK & 0xFF, DUCK_NMI_HOOK >> 8]),
        bytes([DUCK_ORIG_NMI & 0xFF, DUCK_ORIG_NMI >> 8]),
    )
    patch(
        0xFFFC,
        bytes([0x00, 0x80]),
        bytes([DUCK_ORIG_RESET & 0xFF, DUCK_ORIG_RESET >> 8]),
    )
    if not standalone_stub:
        patch(
            DUCK_WIN_PATCH_ADDR,
            bytes([0x4C, DUCK_WIN_HOOK & 0xFF, DUCK_WIN_HOOK >> 8]),
            bytes.fromhex('a2 02 a4'),
        )
    patch(
        0xC02F,
        bytes([0x20, DUCK_SEED_RNG & 0xFF, DUCK_SEED_RNG >> 8]),
        bytes.fromhex('20 2b c2'),
    )

    # Controller, crosshair, fireball burst, Z2 villagers, Barba/Link, roar hooks
    def jsr_to(sym: str) -> bytes:
        addr = b1_syms[sym]
        return bytes([0x20, addr & 0xFF, addr >> 8])

    def jmp_to(sym: str) -> bytes:
        addr = b1_syms[sym]
        return bytes([0x4C, addr & 0xFF, addr >> 8])

    patch(0xC071, jsr_to('vh_after_pad_poll'), bytes.fromhex('20 84 c2'))
    patch(0xC079, jsr_to('vh_frame_tick'), bytes.fromhex('20 1e c6'))
    patch(0xC16E, jmp_to('vh_title_input') + b'\xEA' * 5, bytes.fromhex('a5 16 29 30 c9 10 d0 13'))
    patch(0xC5C4, jsr_to('vh_setup_title_screen') + b'\xEA' * 4, bytes.fromhex('a2 04 a0 e4 20 17 c6'))
    patch(0xC839, jsr_to('vh_setup_game_ab_chr'), bytes.fromhex('20 d9 c5'))
    patch(0xC83C, jsr_to('vh_load_forest_bg') + b'\xEA' * 4, bytes.fromhex('a2 42 a0 e0 20 17 c6'))
    patch(0xD54B, jsr_to('vh_setup_game_c_chr'), bytes.fromhex('20 d9 c5'))
    patch(0xCA16, jmp_to('vh_on_villager_spawn'), bytes.fromhex('e6 31 60'))
    patch(0xD6D2, jmp_to('vh_on_clay_spawn'), bytes.fromhex('e6 31 60'))
    patch(0xD01B, jmp_to('vh_draw_sprite') + b'\xEA', bytes.fromhex('a5 36 85 b4'))
    patch(0xD17E, jmp_to('vh_shot_branch') + b'\xEA' * 7, bytes.fromhex('a9 04 85 23 20 3b c2 20 e1 c5'))

    # Sampled Barba roar triggers + native audio guards
    patch(0xCD52, jsr_to('vh_on_intro_roar') + b'\xEA', bytes.fromhex('a9 04 85 9e'))
    patch(0xCD66, b'\xEA\xEA\xEA', bytes.fromhex('20 28 d5'))
    patch(0xD579, jsr_to('vh_on_clay_intro_roar'), bytes.fromhex('20 6c f5'))
    patch(0xD30F, jsr_to('vh_on_round_clear_roar'), bytes.fromhex('20 1d d5'))
    patch(0xD353, jsr_to('vh_on_perfect_roar'), bytes.fromhex('20 38 d5'))
    guard_dmc = fixed_syms['vh_dmc_guard']
    patch(0xF591, bytes([0x4C, guard_dmc & 0xFF, guard_dmc >> 8, 0xEA, 0xEA]), bytes.fromhex('a5 f2 4a b0 0c'))
    guard_4011 = fixed_syms['vh_4011_guard']
    patch(0xF68F, bytes([0x20, guard_4011 & 0xFF, guard_4011 >> 8]), bytes.fromhex('8d 11 40'))

    # Zapper white box fallback tile ($18 in shared R0 bank)
    patch(0xC6AF, bytes.fromhex('a9 18'), bytes.fromhex('a9 56'))

    # Shift target & Barba/Link OAM ranges to $20..$DF so Fireball ($0200) & Crosshair ($0210) render on top
    patch(0xE5F1, bytes.fromhex('20 5F'), bytes.fromhex('00 3F'))
    patch(0xC927, bytes.fromhex('a9 60 85 36 a9 8f 85 37'), bytes.fromhex('a9 40 85 36 a9 7f 85 37'))
    patch(0xE8E0, bytes.fromhex('20 5F'), bytes.fromhex('00 4F'))
    patch(0xE774, bytes.fromhex('90 ff'), bytes.fromhex('00 bf'))
    patch(0xD812, bytes.fromhex('a9 90 85 36 a9 ff 85 37'), bytes.fromhex('a9 50 85 36 a9 9f 85 37'))

    # Game C shatter particles -> fiery ember tiles ($10/$11, Pal 1)
    ember_shatter = bytes([
        0x10, 0x41, 0x10, 0x41, 0x10, 0xC1, 0x10, 0x81,
        0x10, 0x01, 0x10, 0x01, 0x10, 0x01, 0x10, 0x01,
        0x11, 0x41, 0x11, 0x41, 0x11, 0x41, 0x11, 0x41,
        0x11, 0x01, 0x11, 0x01, 0x11, 0x01, 0x11, 0x01,
    ])
    patch(
        0xEA30,
        ember_shatter,
        bytes.fromhex('ed 40 ed 40 ed c0 ed 80 ed 00 ed 00 ed 00 ed 00 ee 40 ee 40 ee 40 ee 40 ee 00 ee 00 ee 00 ee 00'),
    )

    # Title BG Palette ($E543): keep vanilla Duck Hunt palette intact:
    #   Pal 0: black ($0F), cyan ($2C), orange ($27), black ($0F) -> BARBA'S, HUNT, divider bar
    #   Pal 1: white text/cursor ($30) -> cursor & controls
    #   Pal 2: green text ($2A) -> TOP SCORE = 12000
    #   Pal 3: orange text ($27) -> GAME A / B / C

    # Game A/B Forest Encounter BG Palettes ($E55B, $E5CA):
    #   Pal 0: black ($0F), trunks ($17, $07, $08)
    #   Pal 1: black ($0F), canopy/bushes/ground ($29, $19, $09)
    #   Pal 2: black ($0F), black ($0F), HUD green ($29), dirt ($18)
    #   Pal 3: black ($0F), black ($0F), white ($30), red ($16)
    forest_bg_pals = bytes.fromhex('0f 17 07 08 0f 29 19 09 0f 0f 29 18 0f 0f 30 16')
    orig_ab_bg_pals = bytes.fromhex('21 07 29 0a 21 30 29 0a 21 0f 29 18 21 0f 30 16')
    patch(0xE55B, forest_bg_pals, orig_ab_bg_pals)
    patch(0xE5CA, forest_bg_pals, orig_ab_bg_pals)

    # Gameplay Sprite Palettes ($E56B, $E58F, $E5B7, $E724)
    game_ab_pals = bytearray(SPRITE_PAL_BYTES)
    for i in (0, 4, 8, 12):
        game_ab_pals[i] = 0x0F
    patch(
        0xE56B,
        bytes(game_ab_pals),
        bytes.fromhex('21 30 0a 0f 21 30 26 0f 21 30 17 0f 21 07 17 0f'),
    )
    game_c_pals = bytearray(SPRITE_PAL_BYTES)
    for i in (0, 4, 8, 12):
        game_c_pals[i] = 0x2C
    patch(
        0xE58F,
        bytes(game_c_pals),
        bytes.fromhex('2c 30 0f 0f 2c 30 16 07 2c 30 17 0f 2c 07 17 0f'),
    )
    patch(
        0xE5B7,
        bytes(game_ab_pals),
        bytes.fromhex('21 30 0a 0f 21 30 26 0f 21 30 17 0f 21 07 17 0f'),
    )
    patch(
        0xE724,
        bytes(game_ab_pals),
        bytes.fromhex('21 30 0a 0f 21 30 26 0f 21 30 14 02 21 30 26 02'),
    )

    # Assemble 256KB PRG (32 x 8KB banks)
    prg256 = bytearray(b'\xFF' * (256 * 1024))
    prg256[0 : 8192] = make_duck_bank0(
        restore_addr,
        reward_addr=reward_addr,
        standalone_stub=standalone_stub,
    )
    prg256[1 * 8192 : 2 * 8192] = bank1
    if standalone_stub:
        # Warm-reset safety in Bank 2 ($8000): if emu.reset() leaves R6=2, switch R6=0 and jump to $8000.
        reset_tramp = bytes.fromhex('a9 06 8d 00 80 a9 00 8d 01 80 4c 00 80')
        prg256[2 * 8192 : 2 * 8192 + len(reset_tramp)] = reset_tramp
        # DUCK_RETURN maps R6=$0C before JMP $80F0; fill $80F0..$9FFC in bank $0C with 1-byte NOPs
        # so duck_standalone.lua's endFrame cpu.pc=$7AE0 never catches a multi-byte instruction mid-fetch.
        stub_base = 0x0C * 8192 + (STANDALONE_RESTORE_ADDR - 0x8000)
        stub_end = 0x0C * 8192 + 0x1FFD
        prg256[stub_base : stub_end] = b'\xEA' * (stub_end - stub_base)
        prg256[stub_end : stub_end + 3] = bytes([0x4C, STANDALONE_RESTORE_ADDR & 0xFF, STANDALONE_RESTORE_ADDR >> 8])

    # Bank 29: copy of Bank 30 ($C000-$D6FF) + roar.dmc at $D700
    bank29 = bytearray(prg16[0:8192])
    dmc_off = ROAR_DMC_ADDR - 0xC000
    bank29[dmc_off : 8192] = b'\xFF' * (8192 - dmc_off)
    bank29[dmc_off : dmc_off + len(roar_dmc)] = roar_dmc
    prg256[29 * 8192 : 30 * 8192] = bytes(bank29)

    # Banks 30..31: patched Duck Hunt $C000-$FFFF
    prg256[30 * 8192 : 32 * 8192] = bytes(prg16)

    return bytes(prg256), art['chr']


def patch_duck(duck_bytes: bytes) -> tuple[bytes, bytes]:
    """Legacy NROM signature kept for backwards callers; returns (prg16k, chr8k)."""
    _validate_duck_rom(duck_bytes)
    prg = bytearray(duck_bytes[16 : 16 + 16384])
    chr_data = duck_bytes[16 + 16384 : 16 + 16384 + 8192]

    def patch(addr: int, new: bytes, expected: bytes) -> None:
        off = addr - 0xC000
        assert bytes(prg[off : off + len(expected)]) == expected
        prg[off : off + len(new)] = new

    patch(0xFFFA, bytes([DUCK_NMI_HOOK & 0xFF, DUCK_NMI_HOOK >> 8]), bytes([DUCK_ORIG_NMI & 0xFF, DUCK_ORIG_NMI >> 8]))
    patch(DUCK_WIN_PATCH_ADDR, bytes([0x4C, DUCK_WIN_HOOK & 0xFF, DUCK_WIN_HOOK >> 8]), bytes.fromhex('a2 02 a4'))
    patch(0xC02F, bytes([0x20, DUCK_SEED_RNG & 0xFF, DUCK_SEED_RNG >> 8]), bytes.fromhex('20 2b c2'))
    return bytes(prg), chr_data


def patch_duck_for_combined(
    duck_bytes: bytes,
    z2_bytes: bytes,
    restore_addr: int,
    *,
    reward_addr: int = 0x63B5,
) -> tuple[bytes, bytes]:
    """Build Villager Hunt (prg_256k, chr_up_to_128k) for Slot 12 of combined barba.nes."""
    prg256, chr_data = _build_villager_hunt_banks(
        duck_bytes,
        z2_bytes,
        restore_addr,
        reward_addr=reward_addr,
        standalone_stub=False,
    )
    assert len(prg256) == 256 * 1024
    assert len(chr_data) <= 128 * 1024 and len(chr_data) % 8192 == 0
    return prg256, chr_data


def build_standalone(
    out_path: Path,
    duck_path: Path = ROOT / 'roms/duck.nes',
    z2_path: Path = ROOT / 'roms/z2.nes',
) -> Path:
    """Wrap Villager Hunt in a standalone 256KB PRG + 32KB CHR NES 2.0 Mapper 176 ROM."""
    duck_bytes = duck_path.read_bytes()
    z2_bytes = z2_path.read_bytes()
    prg256, chr_data = _build_villager_hunt_banks(
        duck_bytes,
        z2_bytes,
        STANDALONE_RESTORE_ADDR,
        reward_addr=DUCK_REWARD_ADDR,
        standalone_stub=True,
    )

    # NES 2.0 Mapper 176 (FK23C), 256KB PRG, 32KB CHR, 32KB battery PRG-RAM, Vertical mirroring
    hdr = bytearray(16)
    hdr[0:4] = b'NES\x1a'
    hdr[4] = 16                          # 16 * 16KB = 256KB PRG
    hdr[5] = len(chr_data) // 8192       # 4 * 8KB = 32KB CHR
    hdr[6] = 0x03                        # Vertical mirroring + battery, mapper low = 0
    hdr[7] = 0xB8                        # NES 2.0 + mapper mid = $B0 (176)
    hdr[10] = 0x90                       # 32KB battery PRG-RAM

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(hdr) + prg256 + chr_data)
    return out_path


if __name__ == '__main__':
    out = build_standalone(ROOT / 'build/subgames/duck.nes')
    rom = out.read_bytes()
    chr_len = rom[5] * 8192
    assert len(rom) == 16 + 256 * 1024 + chr_len
    assert rom[0:4] == b'NES\x1a'
    assert rom[4] == 16 and rom[5] in (4, 8, 16)
    assert ((rom[6] >> 4) | (rom[7] & 0xF0)) == 176
    assert rom[16 + 256 * 1024 - 6 : 16 + 256 * 1024 - 4] == bytes([DUCK_NMI_HOOK & 0xFF, DUCK_NMI_HOOK >> 8])
    assert rom[16 + 256 * 1024 - 4 : 16 + 256 * 1024 - 2] == bytes([0x00, 0x80])
    print(f'Built {out} ({len(rom)} bytes, CHR={chr_len} bytes) - all assertions passed.')
