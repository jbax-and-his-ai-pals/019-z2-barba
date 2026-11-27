"""Assemble and patch The Legend of Zelda (NES, MMC1, 128KB PRG, CHR-RAM) for the Barba Mapper 176 portal."""
from __future__ import annotations

import argparse
from pathlib import Path

from pack_f13 import Asm6502
import roar_sample
from subgame_pack import make_rom_header
from zelda_art import build_barba_player_tiles


ROOT = Path(__file__).resolve().parent.parent

# Fixed WRAM Bank 3 ($A3) addresses ($7EE8-$7FFF; $6C90-$7EE7 holds Zelda 1's WRAM engine)
ZELDA_WRAM_CODE_BASE = 0x7EE8
ZELDA_RETURN         = 0x7EE8
ZELDA_WIN_HOOK       = 0x7F06
ZELDA_NMI_ROAR       = 0x7F10
ZELDA_EXIT_ROM       = 0x8200  # Boot Bank 0 exit trampoline copier ($0300)

ZELDA_CUR_R6         = 0x7FE8  # Current 8KB MMC3 bank at $8000-$9FFF
ZELDA_CUR_R7         = 0x7FE9  # Current 8KB MMC3 bank at $A000-$BFFF
ZELDA_ROAR_DONE      = 0x7FEA  # 0..2: fires game-start Barba roar once Mode $05 begins
ZELDA_ROAR_PEND      = 0x7FEB  # Non-zero: trigger Barba sampled roar on next NMI
ZELDA_ROAR_TMR       = 0x7FEC  # Remaining roar frames while DMC plays from $C000
ZELDA_WIN_FLAG       = 0x7FEE  # 0 = Start+Select exit, ZELDA_REWARD_MAGIC = Level 9 Zelda win
ZELDA_DEBOUNCE       = 0x7FFF  # 60-frame ($3C) NMI debounce counter

# Barba WRAM bank 0 reward flag (Portal Slot 14 / arcade_zelda)
ZELDA_REWARD_ADDR    = 0x63B9
ZELDA_REWARD_MAGIC   = 0x5A    # 'Z'

# Roar DMC placement inside 256KB PRG (8KB bank 18 -> $C000-$DFFF when $8000 bit 6 = 1)
ZELDA_ROAR_BANK_R6   = 18

# Vanilla Zelda 1 (USA PRG0, MMC1) fixed addresses
ZELDA_ORIG_RESET     = 0xFF50
ZELDA_RESET_BODY     = 0xE440
ZELDA_ORIG_NMI       = 0xE484
ZELDA_MMC1_CTRL      = 0xFF98
ZELDA_MMC1_PRG       = 0xFFAC

# Fixed-bank hooks in $FF50-$FFEA
ZELDA_NMI_HOOK          = 0xFF58
STANDALONE_BOOT_STUB    = 0xFF60
STANDALONE_RESTORE_ADDR = 0xFFE4


def _load_roar_dmc(roar_wav: Path | None = None) -> tuple[bytes, dict]:
    """Encode assets/roar.wav into NES DMC bytes, writing temp files to build/subgames/zelda_roar/."""
    wav_path = roar_wav or (ROOT / 'assets' / 'roar.wav')
    out_dir = ROOT / 'build' / 'subgames' / 'zelda_roar'
    dmc, info = roar_sample.convert(wav_path, out_dir)
    assert len(dmc) <= 8192, f'Zelda roar DMC exceeds 8KB bank ({len(dmc)} bytes)'
    return dmc, info


def _assemble_wram_code(
    *,
    reward_magic: int = ZELDA_REWARD_MAGIC,
    roar_rate_index: int = 9,
    roar_length_reg: int = 0x88,
    roar_timer_frames: int = 97,
) -> bytes:
    """Assemble WRAM Bank 3 resident routines at $7EE8-$7FE7 (256 bytes)."""
    out = bytearray(b'\xFF' * 0x100)

    def place(addr: int, data: bytes, limit: int) -> None:
        off = addr - ZELDA_WRAM_CODE_BASE
        assert off + len(data) <= limit - ZELDA_WRAM_CODE_BASE, (
            f'WRAM overflow at ${addr:04X}: ${addr + len(data):04X} > ${limit:04X}'
        )
        out[off : off + len(data)] = data

    # 1. ZELDA_RETURN ($7EE8): silence PPU/APU/IRQ, map Boot Bank 0 (R6=0), jump to ZELDA_EXIT_ROM ($8200)
    a = Asm6502(ZELDA_RETURN)
    a.emit(0x78)                                                # SEI
    a.emit(0xA9, 0x00)
    a.emit(0x8D, 0x00, 0x20)                                    # STA $2000 (disable NMI)
    a.emit(0x8D, 0x01, 0x20)                                    # STA $2001 (disable rendering)
    a.emit(0x8D, 0x15, 0x40)                                    # STA $4015 (mute APU/DMC)
    a.emit(0x8D, 0x00, 0xE0)                                    # STA $E000 (disable MMC3 IRQ)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80)                        # LDA #$06; STA $8000 (PRG mode 0, R6)
    a.emit(0xA9, 0x00, 0x8D, 0x01, 0x80)                        # LDA #$00; STA $8001 (Boot Bank 0)
    a.emit(0x4C, ZELDA_EXIT_ROM & 0xFF, ZELDA_EXIT_ROM >> 8)    # JMP $8200
    place(ZELDA_RETURN, a.finish(), ZELDA_WIN_HOOK)

    # 2. ZELDA_WIN_HOOK ($7F06): Princess Zelda rescue ending complete -> return with reward
    a = Asm6502(ZELDA_WIN_HOOK)
    a.emit(0xA9, reward_magic)
    a.emit(0x8D, ZELDA_WIN_FLAG & 0xFF, ZELDA_WIN_FLAG >> 8)
    a.emit(0x4C, ZELDA_RETURN & 0xFF, ZELDA_RETURN >> 8)
    place(ZELDA_WIN_HOOK, a.finish(), ZELDA_NMI_ROAR)

    # 3. ZELDA_NMI_ROAR ($7F10): debounce, Start+Select, sampled roar state machine, dispatch NMI
    a = Asm6502(ZELDA_NMI_ROAR)
    a.emit(0xAD, ZELDA_DEBOUNCE & 0xFF, ZELDA_DEBOUNCE >> 8)
    a.emit(0xC9, 0x3C)
    a.branch(0xB0, 'chk_pad')
    a.emit(0xEE, ZELDA_DEBOUNCE & 0xFF, ZELDA_DEBOUNCE >> 8)
    a.branch(0xD0, 'after_pad')

    a.label('chk_pad')
    a.emit(0xA9, 0x01, 0x8D, 0x16, 0x40, 0xA9, 0x00, 0x8D, 0x16, 0x40)  # strobe $4016
    a.emit(0xAD, 0x16, 0x40, 0xAD, 0x16, 0x40)                          # skip A, B
    a.emit(0xAD, 0x16, 0x40, 0x29, 0x01)                                # Select
    a.branch(0xF0, 'after_pad')
    a.emit(0xAD, 0x16, 0x40, 0x29, 0x01)                                # Start
    a.branch(0xF0, 'after_pad')
    a.emit(0x68, 0x68, 0x68)                                            # pop Y, X, A
    a.emit(0xA9, 0x00, 0x8D, ZELDA_WIN_FLAG & 0xFF, ZELDA_WIN_FLAG >> 8)
    a.emit(0x4C, ZELDA_RETURN & 0xFF, ZELDA_RETURN >> 8)

    a.label('after_pad')
    a.emit(0xAD, ZELDA_ROAR_TMR & 0xFF, ZELDA_ROAR_TMR >> 8)
    a.branch(0xF0, 'chk_start_roar')
    a.emit(0xCE, ZELDA_ROAR_TMR & 0xFF, ZELDA_ROAR_TMR >> 8)
    a.branch(0xF0, 'roar_done')
    a.emit(0xAD, 0x15, 0x40, 0x29, 0x10)
    a.branch(0xD0, 'roar_hold')

    a.label('roar_done')
    a.emit(0xA9, 0x00, 0x8D, ZELDA_ROAR_TMR & 0xFF, ZELDA_ROAR_TMR >> 8)
    a.emit(0xA9, 0x0F, 0x8D, 0x15, 0x40)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80)
    a.emit(0xAD, ZELDA_CUR_R6 & 0xFF, ZELDA_CUR_R6 >> 8, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80)
    a.emit(0xAD, ZELDA_CUR_R7 & 0xFF, ZELDA_CUR_R7 >> 8, 0x8D, 0x01, 0x80)
    a.branch(0xD0, 'normal_nmi')                                        # CUR_R7 is always odd (>= 1)

    a.label('chk_start_roar')
    a.emit(0xA5, 0x12, 0xC9, 0x05)                                      # Game Mode $05 (Overworld active)?
    a.branch(0xD0, 'chk_pend')
    a.emit(0xAD, ZELDA_ROAR_DONE & 0xFF, ZELDA_ROAR_DONE >> 8, 0xC9, 0x02)
    a.branch(0xB0, 'chk_pend')
    a.emit(0xEE, ZELDA_ROAR_DONE & 0xFF, ZELDA_ROAR_DONE >> 8)
    a.emit(0xAD, ZELDA_ROAR_DONE & 0xFF, ZELDA_ROAR_DONE >> 8, 0xC9, 0x02)
    a.branch(0xD0, 'chk_pend')
    a.emit(0xA9, 0x01, 0x8D, ZELDA_ROAR_PEND & 0xFF, ZELDA_ROAR_PEND >> 8)

    a.label('chk_pend')
    a.emit(0xAD, ZELDA_ROAR_PEND & 0xFF, ZELDA_ROAR_PEND >> 8)
    a.branch(0xF0, 'normal_nmi')
    a.emit(0xA9, 0x00, 0x8D, ZELDA_ROAR_PEND & 0xFF, ZELDA_ROAR_PEND >> 8)
    a.emit(0xA9, roar_timer_frames & 0xFF, 0x8D, ZELDA_ROAR_TMR & 0xFF, ZELDA_ROAR_TMR >> 8)
    a.emit(0xA9, 0x0F, 0x8D, 0x15, 0x40)
    a.emit(0xA9, 0x46, 0x8D, 0x00, 0x80)                                # PRG mode 1 ($C000-$DFFF = R6)
    a.emit(0xA9, ZELDA_ROAR_BANK_R6, 0x8D, 0x01, 0x80)
    a.emit(0xA9, roar_rate_index & 0x0F, 0x8D, 0x10, 0x40)
    a.emit(0xA9, 0x40, 0x8D, 0x11, 0x40)
    a.emit(0xA9, 0x00, 0x8D, 0x12, 0x40)
    a.emit(0xA9, roar_length_reg & 0xFF, 0x8D, 0x13, 0x40)
    a.emit(0xA9, 0x1F, 0x8D, 0x15, 0x40)

    a.label('roar_hold')
    a.emit(0x68, 0xA8, 0x68, 0xAA, 0x68, 0x40)                          # PLA; TAY; PLA; TAX; PLA; RTI

    a.label('normal_nmi')
    a.emit(0x68, 0xA8, 0x68, 0xAA, 0x68)                                # PLA; TAY; PLA; TAX; PLA
    a.emit(0x4C, ZELDA_ORIG_NMI & 0xFF, ZELDA_ORIG_NMI >> 8)
    place(ZELDA_NMI_ROAR, a.finish(), ZELDA_WRAM_CODE_BASE + 0x100)

    return bytes(out)


def _make_boot_bank0(
    wram_code: bytes,
    restore_addr: int,
    *,
    reward_addr: int = ZELDA_REWARD_ADDR,
) -> bytes:
    """Assemble 8KB Boot Bank 0 ($8000-$9FFF): initializes WRAM $A3 ($6000-$77FF), installs $7EE8-$7FE7, boots Z1, and hosts $8200 exit copier."""
    assert len(wram_code) == 0x100
    bank0 = bytearray(b'\xFF' * 8192)

    a = Asm6502(0x8000)
    a.emit(0x78, 0xD8, 0xA2, 0xFF, 0x9A)                                # SEI; CLD; LDX #$FF; TXS
    a.emit(0xA9, 0xA3, 0x8D, 0x01, 0xA0)                                # WRAM bank 3 + lock $5FF0-$5FF3
    a.emit(0xA9, 0x00)
    a.emit(0x8D, 0x00, 0x20)                                            # STA $2000
    a.emit(0x8D, 0x01, 0x20)                                            # STA $2001
    a.emit(0x8D, 0x15, 0x40)                                            # STA $4015
    a.emit(0x8D, 0x00, 0xE0)                                            # STA $E000
    a.emit(0xA9, 0x01, 0x8D, 0x00, 0xA0)                                # Horizontal mirroring

    # Clear portal/roar state in $7FE8-$7FEE and $7FFF (preserving $7FF0-$7FF7 RNG seed!)
    a.emit(0xA9, 0x00)
    for addr in (
        ZELDA_ROAR_DONE,
        ZELDA_ROAR_PEND,
        ZELDA_ROAR_TMR,
        ZELDA_WIN_FLAG,
        ZELDA_DEBOUNCE,
    ):
        a.emit(0x8D, addr & 0xFF, addr >> 8)

    # Clear WRAM $6000-$77FF so stale bytes from other subgames never affect Zelda 1
    a.emit(0xA9, 0x00, 0x85, 0x00)
    a.emit(0xA9, 0x60, 0x85, 0x01)
    a.emit(0xA0, 0x00)
    a.label('clr_loop')
    a.emit(0xA9, 0x00, 0x91, 0x00)
    a.emit(0xC8)
    a.branch(0xD0, 'clr_loop')
    a.emit(0xE6, 0x01, 0xA5, 0x01, 0xC9, 0x78)
    a.branch(0xD0, 'clr_loop')

    # Mark all 3 save slot headers empty ($FF)
    a.emit(0xA9, 0xFF, 0x8D, 0x2A, 0x65, 0x8D, 0x2B, 0x65, 0x8D, 0x2C, 0x65)

    # Copy $8100-$81FF -> $7EE8-$7FE7 (256 bytes, stops before $7FE8)
    a.emit(0xA2, 0x00)
    a.label('cp_wram')
    a.emit(0xBD, 0x00, 0x81)
    a.emit(0x9D, ZELDA_WRAM_CODE_BASE & 0xFF, ZELDA_WRAM_CODE_BASE >> 8)
    a.emit(0xE8)
    a.branch(0xD0, 'cp_wram')

    # Jump to Z1 Reset body ($E440, fixed bank), which calls $FFAC to map Z1 Bank 5
    a.emit(0xA9, 12, 0x8D, ZELDA_CUR_R6 & 0xFF, ZELDA_CUR_R6 >> 8)
    a.emit(0xA9, 13, 0x8D, ZELDA_CUR_R7 & 0xFF, ZELDA_CUR_R7 >> 8)
    a.emit(0x4C, ZELDA_RESET_BODY & 0xFF, ZELDA_RESET_BODY >> 8)

    loader = a.finish()
    assert len(loader) <= 0x100, f'Boot loader exceeded 256B ({len(loader)} bytes)'
    bank0[0 : len(loader)] = loader
    bank0[0x100 : 0x100 + len(wram_code)] = wram_code

    # Exit trampoline copier at ZELDA_EXIT_ROM ($8200)
    ae = Asm6502(ZELDA_EXIT_ROM)
    ae.emit(0xAE, ZELDA_WIN_FLAG & 0xFF, ZELDA_WIN_FLAG >> 8)   # LDX $7FEE
    tramp = (
        bytes.fromhex(
            'a9 80 8d 01 a0 '                                   # LDA #$80; STA $A001 (unlock $5FFx)
            'a9 01 8d f0 5f '                                   # LDA #$01; STA $5FF0 (Barba 256K + CHR-ROM)
            'a9 00 8d f1 5f 8d f2 5f '                          # LDA #$00; STA $5FF1; STA $5FF2
            'a9 a0 8d 01 a0 '                                   # LDA #$A0; STA $A001 (WRAM bank 0)
            '8a f0 03 '                                         # TXA; BEQ +3
            '8d'
        )
        + reward_addr.to_bytes(2, 'little')
        + bytes([
            0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x0C, 0x8D, 0x01, 0x80,  # R6 = $0C
            0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x0D, 0x8D, 0x01, 0x80,  # R7 = $0D
            0x4C,
        ])
        + restore_addr.to_bytes(2, 'little')
    )
    ae.emit(0xA0, len(tramp) - 1)
    ae.label('cp_tramp')
    ae.abs_ref(0xB9, 'tramp_data')
    ae.emit(0x99, 0x00, 0x03)
    ae.emit(0x88)
    ae.branch(0x10, 'cp_tramp')
    ae.emit(0x4C, 0x00, 0x03)
    ae.label('tramp_data')
    ae.emit(*tramp)
    exit_code = ae.finish()
    bank0[0x200 : 0x200 + len(exit_code)] = exit_code

    return bytes(bank0)


def patch_zelda(
    zelda_bytes: bytes,
    restore_addr: int,
    *,
    reward_addr: int = ZELDA_REWARD_ADDR,
    reward_magic: int = ZELDA_REWARD_MAGIC,
    z2_bytes: bytes | None = None,
    build_number: int | None = None,
) -> bytes:
    """Verify and patch The Legend of Zelda (MMC1, 128KB PRG) into a 256KB Mapper 176 PRG block."""
    assert zelda_bytes[:4] == b'NES\x1a', 'Not an iNES ROM'
    assert zelda_bytes[4] == 8 and zelda_bytes[5] == 0, (
        f'Expected 8x16KB PRG and 0 CHR-ROM, got {zelda_bytes[4]}x16KB, {zelda_bytes[5]}'
    )
    mapper = (zelda_bytes[6] >> 4) | (zelda_bytes[7] & 0xF0)
    assert mapper == 1, f'Expected Mapper 1 (MMC1), got {mapper}'

    if z2_bytes is None:
        z2_bytes = (ROOT / 'roms' / 'z2.nes').read_bytes()

    roar_dmc, roar_info = _load_roar_dmc()
    art = build_barba_player_tiles(z2_bytes)

    src_prg = bytearray(zelda_bytes[16 : 16 + 128 * 1024])
    assert len(src_prg) == 128 * 1024

    if build_number is not None:
        # Title screen row 1 ($2020 len $20) starts at PRG 0x1A88E; cols 26..30 ($203A) are sky ($24).
        title_b_off = 0x1A88E + 26
        tag = bytes([0x0B] + [int(c) for c in str(build_number)])
        assert src_prg[title_b_off : title_b_off + len(tag)] == b'\x24' * len(tag)
        src_prg[title_b_off : title_b_off + len(tag)] = tag

    def patch_bank(bank: int, addr: int, new: bytes, expected: bytes) -> None:
        base = 0xC000 if bank == 7 else 0x8000
        off = bank * 0x4000 + (addr - base)
        actual = bytes(src_prg[off : off + len(expected)])
        assert actual == expected, (
            f'Unexpected Zelda bytes at bank {bank} ${addr:04X}: {actual.hex(" ")}'
        )
        src_prg[off : off + len(new)] = new

    # 1. Virtualize MMC1 Control & PRG bankswitch in Banks 0..6 ($BF98/$BFAC) and Bank 7 ($FF98/$FFAC)
    for b in range(7):
        patch_bank(
            b, 0xBF98,
            bytes([0x4C, ZELDA_MMC1_CTRL & 0xFF, ZELDA_MMC1_CTRL >> 8]) + b'\xEA' * 17,
            bytes.fromhex('8d 00 80 4a 8d 00 80 4a 8d 00 80 4a 8d 00 80 4a 8d 00 80 60'),
        )
        patch_bank(
            b, 0xBFAC,
            bytes([0x4C, ZELDA_MMC1_PRG & 0xFF, ZELDA_MMC1_PRG >> 8]) + b'\xEA' * 17,
            bytes.fromhex('8d 00 e0 4a 8d 00 e0 4a 8d 00 e0 4a 8d 00 e0 4a 8d 00 e0 60'),
        )

    # Bank 7 $FF50 soft-reset target (used by Bank 5 $8625)
    a_rst = Asm6502(ZELDA_ORIG_RESET)
    a_rst.emit(0xA9, 0x01, 0x8D, 0x00, 0xA0)
    a_rst.emit(0x4C, ZELDA_RESET_BODY & 0xFF, ZELDA_RESET_BODY >> 8)
    rst_stub = a_rst.finish()
    assert len(rst_stub) == 8
    patch_bank(7, ZELDA_ORIG_RESET, rst_stub, bytes.fromhex('78 d8 a9 00 8d 00 20 a2'))

    # Bank 7 $FF58 NMI entry trampoline -> $7F70
    a_nmi = Asm6502(ZELDA_NMI_HOOK)
    a_nmi.emit(0x48, 0x8A, 0x48, 0x98, 0x48)
    a_nmi.emit(0x4C, ZELDA_NMI_ROAR & 0xFF, ZELDA_NMI_ROAR >> 8)
    nmi_stub = a_nmi.finish()
    assert len(nmi_stub) == 8
    patch_bank(7, ZELDA_NMI_HOOK, nmi_stub, bytes.fromhex('ff 9a ad 02 20 29 80 f0'))
    # Reclaim dead MMC1 reset stub at $FF60-$FF97 (56 bytes)
    patch_bank(
        7, 0xFF60,
        b'\xFF' * 56,
        bytes.fromhex(
            'f9 ad 02 20 29 80 f0 f9 09 ff 8d 00 80 8d 00 a0 8d 00 c0 8d 00 e0 '
            'a9 0f 20 98 ff a9 00 8d 00 a0 4a 8d 00 a0 4a 8d 00 a0 4a 8d 00 a0 '
            '4a 8d 00 a0 a9 07 20 ac ff 4c 40 e4'
        ),
    )

    # Bank 7 $FF98 MMC1 Control -> $A000 mirroring
    a_ctrl = Asm6502(ZELDA_MMC1_CTRL)
    a_ctrl.emit(0x29, 0x01, 0x8D, 0x00, 0xA0, 0x60)
    ctrl_code = a_ctrl.finish()
    assert len(ctrl_code) <= 20
    patch_bank(
        7, ZELDA_MMC1_CTRL,
        ctrl_code.ljust(20, b'\xFF'),
        bytes.fromhex('8d 00 80 4a 8d 00 80 4a 8d 00 80 4a 8d 00 80 4a 8d 00 80 60'),
    )

    # Bank 7 $FFAC MMC1 PRG bank A (0..7) -> R6=(A+1)*2, R7=R6+1 (preserves X, Y, P)
    a_prg = Asm6502(ZELDA_MMC1_PRG)
    a_prg.emit(0x08, 0x78)                                      # PHP; SEI
    a_prg.emit(0x29, 0x07, 0x18, 0x69, 0x01, 0x0A)              # AND #$07; CLC; ADC #$01; ASL A
    a_prg.emit(0x8D, ZELDA_CUR_R6 & 0xFF, ZELDA_CUR_R6 >> 8)    # STA ZELDA_CUR_R6
    a_prg.emit(0x48)                                            # PHA
    a_prg.emit(0xA9, 0x06, 0x8D, 0x00, 0x80)                    # LDA #$06; STA $8000
    a_prg.emit(0x68, 0x8D, 0x01, 0x80)                          # PLA; STA $8001
    a_prg.emit(0x09, 0x01)                                      # ORA #$01
    a_prg.emit(0x8D, ZELDA_CUR_R7 & 0xFF, ZELDA_CUR_R7 >> 8)    # STA ZELDA_CUR_R7
    a_prg.emit(0x48)                                            # PHA
    a_prg.emit(0xA9, 0x07, 0x8D, 0x00, 0x80)                    # LDA #$07; STA $8000
    a_prg.emit(0x68, 0x8D, 0x01, 0x80)                          # PLA; STA $8001
    a_prg.emit(0x28, 0x60)                                      # PLP; RTS
    prg_code = a_prg.finish()
    assert len(prg_code) <= 38
    patch_bank(
        7, ZELDA_MMC1_PRG,
        prg_code,
        bytes.fromhex('8d 00 e0 4a 8d 00 e0 4a 8d 00 e0 4a 8d 00 e0 4a 8d 00 e0 60')
        + b'\xFF' * (len(prg_code) - 20),
    )

    # Bank 7 NMI vector ($FFFA) -> ZELDA_NMI_HOOK
    patch_bank(
        7, 0xFFFA,
        bytes([ZELDA_NMI_HOOK & 0xFF, ZELDA_NMI_HOOK >> 8]),
        bytes([ZELDA_ORIG_NMI & 0xFF, ZELDA_ORIG_NMI >> 8]),
    )

    # 2. Protect WRAM $7800-$7FFF from vanilla Z1 save signature/clear checks
    # Bank 7 $E911: NOP out LDA #$A5; STA $7FFF
    patch_bank(7, 0xE911, b'\xEA' * 5, bytes.fromhex('a9 a5 8d ff 7f'))
    # Bank 5 $B4AC: check only $6001 == #$5A (skip $7FFF == #$A5 check)
    patch_bank(
        5, 0xB4AC,
        bytes.fromhex('ad 01 60 c9 5a f0 33') + b'\xEA' * 7,
        bytes.fromhex('ad 01 60 c9 5a d0 07 ad ff 7f c9 a5 f0 2c'),
    )
    # Bank 5 $B4E0: clear up to $7800 instead of $8000
    patch_bank(5, 0xB4E0, bytes.fromhex('c9 78'), bytes.fromhex('c9 80'))

    # Bank 1 $8D30: stop WRAM engine copy ($6C90..$7EE7) at $7EE8 so $7EE8-$7FFF stay untouched
    patch_bank(1, 0x8D30, bytes.fromhex('c9 7e d0 de a5 02 c9 e8'), bytes.fromhex('c9 7f d0 de a5 02 c9 00'))

    # 3. RNG seeding ($B50A in Bank 5 -> $B8A0 in Bank 5 free space)
    seed_addr = 0xB8A0
    a_seed = Asm6502(seed_addr)
    a_seed.emit(0xA9, 0x01, 0x8D, 0x36, 0x06, 0x8D, 0x37, 0x06)  # displaced $0636/$0637 init
    a_seed.emit(0xA2, 0x07, 0xA9, 0x00, 0x85, 0x00)
    a_seed.label('seed_loop')
    a_seed.emit(0xBD, 0xF0, 0x7F, 0x95, 0x18, 0x05, 0x00, 0x85, 0x00)
    a_seed.emit(0xCA)
    a_seed.branch(0x10, 'seed_loop')
    a_seed.emit(0xA5, 0x00)
    a_seed.branch(0xD0, 'seed_ok')
    a_seed.emit(0xA9, 0x40, 0x85, 0x18)
    a_seed.label('seed_ok')
    a_seed.emit(0x60)
    seed_code = a_seed.finish()
    patch_bank(5, seed_addr, seed_code, b'\xFF' * len(seed_code))
    patch_bank(
        5, 0xB50A,
        bytes([0x20, seed_addr & 0xFF, seed_addr >> 8]) + b'\xEA' * 5 + b'\x60',
        bytes.fromhex('a9 01 8d 36 06 8d 37 06 60'),
    )

    # 4. Barba sprites, firebreath/fireball graphics, and Villainous Dark Link (CHR-RAM payloads)
    patch_bank(2, 0x807F, art['barba_00_1b'], src_prg[2 * 0x4000 + 0x007F : 2 * 0x4000 + 0x007F + 0x1C0])
    patch_bank(2, 0x827F, art['fire_vert'],   src_prg[2 * 0x4000 + 0x027F : 2 * 0x4000 + 0x027F + 0x20])
    patch_bank(2, 0x869F, art['spark_62_65'], src_prg[2 * 0x4000 + 0x069F : 2 * 0x4000 + 0x069F + 0x40])
    patch_bank(1, 0x8E34, art['hold_78'],     src_prg[1 * 0x4000 + 0x0E34 : 1 * 0x4000 + 0x0E34 + 0x20])
    patch_bank(1, 0x8ED4, art['fire_horiz'],  src_prg[1 * 0x4000 + 0x0ED4 : 1 * 0x4000 + 0x0ED4 + 0x20])
    patch_bank(3, 0xA7DB, art['villain_c0_e7'], src_prg[3 * 0x4000 + 0x27DB : 3 * 0x4000 + 0x27DB + 0x280])

    # 5. Palettes: Barba Sprite Pal 0 ($16,$27,$30), Ring tunic upgrades, Villainous Dark Link ($06,$16,$36)
    for lvl_pal_addr in (0x9314, 0x9410, 0x950C, 0x9608, 0x9704, 0x9800, 0x98FC, 0x99F8, 0x9AF4, 0x9BF0):
        exp = bytes.fromhex('29 37 17') if lvl_pal_addr == 0x9608 else bytes.fromhex('29 27 17')
        patch_bank(6, lvl_pal_addr, bytes.fromhex('16 27 30'), exp)
    patch_bank(6, 0x9CEC, bytes.fromhex('16 27 30'), bytes.fromhex('29 27 07'))
    patch_bank(1, 0xAB95, bytes.fromhex('16 22 27'), bytes.fromhex('29 32 16'))
    patch_bank(6, 0xA206, bytes.fromhex('06 16 36'), bytes.fromhex('16 2c 3c'))
    patch_bank(1, 0xA1C8, bytes.fromhex('06 16 36'), bytes.fromhex('16 2c 3c'))
    patch_bank(4, 0xAF67, bytes.fromhex('06 16 36'), bytes.fromhex('16 2c 3c'))

    # 6. Bank 4 free space ($B46F+): Firebreath/fireball bush ignition + Boss/Triforce roar hooks
    b4_pc = 0xB46F
    a4 = Asm6502(b4_pc)

    # B4_BUSH_CHECK: check Candle flames ($10,$11), Fireball ($0E), and Melee Firebreath ($0D)
    a4.label('bush_check')
    a4.emit(0xA0, 0x10)
    a4.emit(0xB9, 0xAC, 0x00, 0xC9, 0x22)
    a4.branch(0xF0, 'chk_candle_tmr')
    a4.emit(0xC8)
    a4.emit(0xB9, 0xAC, 0x00, 0xC9, 0x22)
    a4.branch(0xD0, 'chk_fireball')
    a4.label('chk_candle_tmr')
    a4.emit(0x84, 0x00)                                                 # STY $00 (expected by $8F3F/$8EE0)
    a4.emit(0xB9, 0x28, 0x00, 0xC9, 0x02)
    a4.branch(0xB0, 'chk_fireball')
    a4.emit(0x20, 0x3F, 0x8F)
    a4.branch(0xD0, 'burn_hit')

    a4.label('chk_fireball')
    a4.emit(0xA0, 0x0E)
    a4.emit(0xB9, 0xAC, 0x00)
    a4.emit(0xC9, 0x10)
    a4.branch(0xF0, 'test_fb')
    a4.emit(0xC9, 0x80)
    a4.branch(0xD0, 'chk_melee')
    a4.label('test_fb')
    a4.emit(0x84, 0x00)                                                 # STY $00
    a4.emit(0x20, 0x3F, 0x8F)
    a4.branch(0xD0, 'burn_hit')

    a4.label('chk_melee')
    a4.emit(0xA0, 0x0D)
    a4.emit(0xB9, 0xAC, 0x00, 0x29, 0x0F)
    a4.branch(0xF0, 'bush_miss')
    a4.emit(0x84, 0x00)                                                 # STY $00
    a4.emit(0x20, 0x3F, 0x8F)
    a4.branch(0xF0, 'bush_miss')

    a4.label('burn_hit')
    a4.emit(0x4C, 0x32, 0x8F)
    a4.label('bush_miss')
    a4.emit(0x60)

    # Boss & Level 9 Triforce roar helpers
    a4.label('roar_hc_x')
    a4.emit(0xA9, 0x5D, 0x9D, 0x4F, 0x03)
    a4.emit(0xA9, 0x01, 0x8D, ZELDA_ROAR_PEND & 0xFF, ZELDA_ROAR_PEND >> 8, 0x60)

    a4.label('roar_hc_y')
    a4.emit(0xA9, 0x5D, 0x99, 0x50, 0x03)
    a4.emit(0xA9, 0x01, 0x8D, ZELDA_ROAR_PEND & 0xFF, ZELDA_ROAR_PEND >> 8, 0x60)

    a4.label('roar_ganon')
    a4.emit(0xA9, 0x02, 0x8D, 0x00, 0x06)
    a4.emit(0xA9, 0x01, 0x8D, ZELDA_ROAR_PEND & 0xFF, ZELDA_ROAR_PEND >> 8, 0x60)

    a4.label('roar_tri_pwr')
    a4.emit(0xA9, 0x20, 0x8D, 0x00, 0x06)
    a4.emit(0xA9, 0x01, 0x8D, ZELDA_ROAR_PEND & 0xFF, ZELDA_ROAR_PEND >> 8, 0x60)

    b4_code = a4.finish()
    assert b4_pc + len(b4_code) <= 0xBF50
    patch_bank(4, b4_pc, b4_code, b'\xFF' * len(b4_code))

    # Hook Bank 4 bush check ($8F13)
    bush_addr = a4.labels['bush_check']
    patch_bank(4, 0x8F13, bytes([0x4C, bush_addr & 0xFF, bush_addr >> 8]), bytes.fromhex('a0 10 b9'))

    # Hook Bank 4 boss Heart Container spawns & Level 9 Ganon / Triforce
    hc_x = a4.labels['roar_hc_x']
    hc_y = a4.labels['roar_hc_y']
    ganon_r = a4.labels['roar_ganon']
    tri_pwr_r = a4.labels['roar_tri_pwr']
    for addr in (0x8D87, 0xA27D, 0xA9E5):
        patch_bank(4, addr, bytes([0x20, hc_x & 0xFF, hc_x >> 8, 0xEA, 0xEA]), bytes.fromhex('a9 5d 9d 4f 03'))
    for addr in (0x94F9, 0xAA67):
        patch_bank(4, addr, bytes([0x20, hc_y & 0xFF, hc_y >> 8, 0xEA, 0xEA]), bytes.fromhex('a9 5d 99 50 03'))
    patch_bank(4, 0xAD75, bytes([0x20, ganon_r & 0xFF, ganon_r >> 8, 0xEA, 0xEA]), bytes.fromhex('a9 02 8d 00 06'))
    patch_bank(4, 0xACD4, bytes([0x20, tri_pwr_r & 0xFF, tri_pwr_r >> 8, 0xEA, 0xEA]), bytes.fromhex('a9 20 8d 00 06'))

    # 7. Triforce shard pickup roar in Bank 1 ($A1A0 -> free space $B7B0, after seed_code at $B751)
    b1_roar_addr = 0xB7B0
    b1_roar = bytes([0xA9, 0x20, 0x8D, 0x00, 0x06, 0xA9, 0x01, 0x8D, ZELDA_ROAR_PEND & 0xFF, ZELDA_ROAR_PEND >> 8, 0x60])
    patch_bank(1, b1_roar_addr, b1_roar, b'\xFF' * len(b1_roar))
    patch_bank(1, 0xA1A0, bytes([0x20, b1_roar_addr & 0xFF, b1_roar_addr >> 8, 0xEA, 0xEA]), bytes.fromhex('a9 20 8d 00 06'))

    # 8. Ending Triforce overhead roar ($AA50) & Princess Zelda Win Hook ($ABA7) in Bank 2
    b2_roar_addr = 0xAF90
    b2_roar = bytes([0xA9, 0x10, 0x8D, 0x00, 0x06, 0xA9, 0x01, 0x8D, ZELDA_ROAR_PEND & 0xFF, ZELDA_ROAR_PEND >> 8, 0x60])
    patch_bank(2, b2_roar_addr, b2_roar, b'\xFF' * len(b2_roar))
    patch_bank(2, 0xAA50, bytes([0x20, b2_roar_addr & 0xFF, b2_roar_addr >> 8, 0xEA, 0xEA]), bytes.fromhex('a9 10 8d 00 06'))
    patch_bank(
        2, 0xABA8,
        bytes([0x4C, ZELDA_WIN_HOOK & 0xFF, ZELDA_WIN_HOOK >> 8, 0xEA]),
        bytes.fromhex('a9 0d 85 12'),
    )

    # 9. Assemble 256KB PRG layout
    wram_code = _assemble_wram_code(
        reward_magic=reward_magic,
        roar_rate_index=roar_info['rate_index'],
        roar_length_reg=(len(roar_dmc) - 1) // 16,
        roar_timer_frames=roar_info['timer_frames'],
    )
    boot_bank0 = _make_boot_bank0(wram_code, restore_addr, reward_addr=reward_addr)

    prg256 = bytearray(b'\xFF' * (256 * 1024))
    prg256[0 : 8192] = boot_bank0
    # Z1 Banks 0..6 (16KB each) -> 8KB banks 2..15
    for b in range(7):
        off_dst = (b + 1) * 16384
        prg256[off_dst : off_dst + 16384] = src_prg[b * 16384 : (b + 1) * 16384]
    # Z1 Bank 7 -> 8KB banks 16..17 (for MMC1 A=7) AND fixed 240..256KB (banks 30..31)
    b7_bytes = bytes(src_prg[7 * 16384 : 8 * 16384])
    prg256[128 * 1024 : 144 * 1024] = b7_bytes
    prg256[240 * 1024 : 256 * 1024] = b7_bytes
    # Roar DMC sample -> 8KB bank 18 (144..152KB)
    roar_off = ZELDA_ROAR_BANK_R6 * 8192
    prg256[roar_off : roar_off + len(roar_dmc)] = roar_dmc

    return bytes(prg256)


def build_standalone(
    out_path: Path,
    zelda_path: Path = ROOT / 'roms' / 'zelda.nes',
    z2_path: Path = ROOT / 'roms' / 'z2.nes',
    *,
    mapper: str = '176',
    build_number: int | None = None,
) -> Path:
    """Wrap patched Legend of Zelda in a standalone 256KB PRG + 32KB CHR-RAM ROM (Mapper 176 or NES 2.0 MMC3)."""
    from build_history import HISTORY_FILE, next_subgame_build_number, record_subgame_build
    import hashlib
    record_this = build_number is None
    if build_number is None:
        build_number = next_subgame_build_number(HISTORY_FILE, 'zelda')
    zelda_bytes = zelda_path.read_bytes()
    z2_bytes = z2_path.read_bytes()
    prg = bytearray(
        patch_zelda(
            zelda_bytes,
            STANDALONE_RESTORE_ADDR,
            reward_addr=ZELDA_REWARD_ADDR,
            z2_bytes=z2_bytes,
            build_number=build_number,
        )
    )

    def patch_fixed(addr: int, new: bytes, expected: bytes) -> None:
        for base_off in (128 * 1024, 240 * 1024):
            off = base_off + (addr - 0xC000)
            actual = bytes(prg[off : off + len(expected)])
            assert actual == expected, f'Unexpected fixed bytes at ${addr:04X}: {actual.hex(" ")}'
            prg[off : off + len(new)] = new

    # Standalone cold-boot stub at $FF60: wait 2 VBlanks, init mapper, R6=0, JMP $8000
    a = Asm6502(STANDALONE_BOOT_STUB)
    a.emit(0x78, 0xD8, 0xA2, 0xFF, 0x9A)                    # SEI; CLD; LDX #$FF; TXS
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20)  # PPU off
    a.label('v1')
    a.emit(0x2C, 0x02, 0x20)
    a.branch(0x10, 'v1')
    a.label('v2')
    a.emit(0x2C, 0x02, 0x20)
    a.branch(0x10, 'v2')
    a.emit(0xA9, 0x80, 0x8D, 0x01, 0xA0)                    # enable WRAM / unlock $5FF0-$5FF3
    if mapper == '176':
        a.emit(0xA9, 0x21, 0x8D, 0xF0, 0x5F)                # $5FF0 = $21 (256KB MMC3 + 32KB CHR-RAM)
        a.emit(0xA9, 0x00, 0x8D, 0xF1, 0x5F, 0x8D, 0xF2, 0x5F)  # $5FF1 = 0, $5FF2 = 0
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x00, 0x8D, 0x01, 0x80)  # R6 = 0
    a.emit(0x4C, 0x00, 0x80)                                # JMP $8000
    boot_stub = a.finish()
    assert STANDALONE_BOOT_STUB + len(boot_stub) <= ZELDA_MMC1_CTRL
    patch_fixed(STANDALONE_BOOT_STUB, boot_stub, b'\xFF' * len(boot_stub))

    # Standalone restore target ($FFE4): JMP $FFE4
    patch_fixed(
        STANDALONE_RESTORE_ADDR,
        bytes([0x4C, STANDALONE_RESTORE_ADDR & 0xFF, STANDALONE_RESTORE_ADDR >> 8]),
        b'\xFF\xFF\xFF',
    )

    # Standalone reset vector ($FFFC) -> STANDALONE_BOOT_STUB
    patch_fixed(
        0xFFFC,
        bytes([STANDALONE_BOOT_STUB & 0xFF, STANDALONE_BOOT_STUB >> 8]),
        bytes([ZELDA_ORIG_RESET & 0xFF, ZELDA_ORIG_RESET >> 8]),
    )

    if mapper == 'mmc3':
        hdr = make_rom_header(len(prg), 0, mapper='mmc3', vertical_mirroring=False, chr_ram_kb=32)
        chr_tail = b''
    else:
        hdr = make_rom_header(len(prg), 8192, mapper='176', vertical_mirroring=False, chr_ram_kb=32)
        chr_tail = b'\x00' * 8192

    rom_bytes = bytes(hdr) + bytes(prg) + chr_tail
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(rom_bytes)
    if record_this:
        record_subgame_build(HISTORY_FILE, 'zelda', build_number, mapper, out_path, hashlib.sha256(rom_bytes).hexdigest())
    return out_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=None)
    parser.add_argument('--mapper', choices=('176', 'mmc3'), default='176')
    args = parser.parse_args()
    default_out = ROOT / ('play/nes/zelda-mmc3.nes' if args.mapper == 'mmc3' else 'build/subgames/zelda.nes')
    out = build_standalone(args.out or default_out, mapper=args.mapper)
    if args.mapper == 'mmc3' and args.out is None:
        from bps import write_bps
        write_bps(
            ROOT / 'roms/zelda.nes',
            out,
            out_bps_path=ROOT / 'play/bps/zelda-mmc3.bps',
            metadata='zelda-mmc3 | Barba Edition (MMC3)',
        )
    rom = out.read_bytes()
    expected_mapper = 4 if args.mapper == 'mmc3' else 176
    expected_chr_banks = 0 if args.mapper == 'mmc3' else 1
    assert len(rom) == 16 + 256 * 1024 + expected_chr_banks * 8192
    assert rom[0:4] == b'NES\x1a'
    assert rom[4] == 16 and rom[5] == expected_chr_banks and rom[11] == 0x09
    assert ((rom[6] >> 4) | (rom[7] & 0xF0)) == expected_mapper
    assert rom[16 + 256 * 1024 - 6 : 16 + 256 * 1024 - 4] == bytes([ZELDA_NMI_HOOK & 0xFF, ZELDA_NMI_HOOK >> 8])
    assert rom[16 + 256 * 1024 - 4 : 16 + 256 * 1024 - 2] == bytes([STANDALONE_BOOT_STUB & 0xFF, STANDALONE_BOOT_STUB >> 8])
    print(f'Built {out} ({len(rom):,} bytes, mapper={expected_mapper}) - all assertions passed.')
