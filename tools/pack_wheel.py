"""Assemble and patch Wheel of Barba (Round 2 upgrade of Wheel of Fortune, AxROM) for the Barba Mapper 176 portal."""
from __future__ import annotations

import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from pack_f13 import Asm6502
import roar_sample
import wheel_art
import wheel_puzzles


# Fixed entry points in guest WRAM bank ($7800-$7BFF)
WHEEL_WRAM_CODE_BASE = 0x7800
WHEEL_SET_BANK       = 0x7800
WHEEL_SET_BANK_X     = 0x7822
WHEEL_PPUCTRL_A      = 0x782A
WHEEL_PPUCTRL_X      = 0x7844
WHEEL_NMI_HOOK       = 0x7850
WHEEL_WIN_HOOK       = 0x78A0
WHEEL_SET_BANK_BODY  = 0x78B0
WHEEL_PPUSCROLL_NT0  = 0x7900
WHEEL_PPUSCROLL_NT1  = 0x790C
WHEEL_RETURN         = 0x7960
WHEEL_BOOT           = 0x7AE0
WHEEL_ROM_5FF1       = 0xFE14  # 16-byte common-ROM helper in all 4 banks: A=$5FF1 -> unlock, STA $5FF1, WRAM=$A3

# Bank 0 Wheel of Barba helpers ($FC48-$FE13) and relocated Bonus Prize bank in Block 0 MMC3 bank 2
WHEEL_ROAR_DMC_ADDR  = 0xE200  # 64-byte aligned DMC slot in Bank 0 & Bank 1 ($4012 = $88)
WHEEL_PLAY_ROAR      = 0xFC48
WHEEL_ROAR_SOLVE     = 0xFC69
WHEEL_BIG_SPIN_ROAR  = 0xFC6F
WHEEL_PRIZE_COPY     = 0xFC84
WHEEL_PRIZE_BANK     = 0x02    # Unused 8KB MMC3 bank 2 inside Block 0
WHEEL_BANK0_R6       = 0x1C    # Wheel Bank 0 $8000-$9FFF MMC3 bank index

# Guest WRAM state bytes (in guest WRAM bank)
WHEEL_NT_BIT         = 0x7FFA  # Precomputed effective PPUCTRL bit 0: (($7FFD & $10) >> 4) ^ $7FFB
WHEEL_NT_XOR         = 0x7FFB  # Per-screen nametable XOR (1 for $926B/$B774 under Vertical mirroring)
WHEEL_PPUCTRL        = 0x7FFC  # Shadow of $2000 write with bit 0 masked off
WHEEL_AX_SHADOW      = 0x7FFD  # Shadow of $8000 AxROM latch (bits 0-1: bank, bit 4: nametable)
WHEEL_WIN_FLAG       = 0x7FFE  # 0 = Start+Select exit, WHEEL_REWARD_MAGIC = bonus round win
WHEEL_DEBOUNCE       = 0x7FFF  # 60-frame ($3C) NMI debounce counter

# Barba WRAM bank 0 reward flag
WHEEL_REWARD_ADDR    = 0x648E
WHEEL_REWARD_MAGIC   = 0x57    # 'W'

# Wheel of Fortune (USA, Mapper 7 AxROM, 4x32KB PRG, CHR-RAM) addresses
WHEEL_ORIG_RESET     = 0xFF90
WHEEL_RESET_TARGET   = 0x8030
WHEEL_ORIG_NMIS      = (0x8B3A, 0xFDF2, 0xECF3, 0xFC48)
WHEEL_WIN_PATCH_ADDR = 0xC988  # Bonus Round win ("CONGRATULATIONS / YOU HAVE WON THE FOLLOWING")
WHEEL_PAD1_ZP        = 0x20    # P1 held buttons (Bit 5 = Select $20, Bit 4 = Start $10)
WHEEL_START_SELECT   = 0x30

STANDALONE_RESTORE_ADDR = 0x80F0

# All $8000 AxROM latch write sites per 32KB bank: (addr, expected_opcode)
AXROM_WRITE_SITES: dict[int, list[tuple[int, int]]] = {
    0: [
        (0x8099, 0x8D),
        (0x80A1, 0x8D),
        (0x80D0, 0x8D),
        (0x8101, 0x8E),  # STX $8000
        (0x8179, 0x8D),
        (0x8B45, 0x8D),
        (0xFF84, 0x8D),
        (0xFF8C, 0x8D),
        (0xFF93, 0x8D),
        (0xFFE2, 0x8D),
        (0xFFEA, 0x8D),
    ],
    1: [
        (0xFF84, 0x8D),
        (0xFF8C, 0x8D),
        (0xFF93, 0x8D),
        (0xFFE2, 0x8D),
        (0xFFEA, 0x8D),
    ],
    2: [
        (0xFF84, 0x8D),
        (0xFF8C, 0x8D),
        (0xFF93, 0x8D),
    ],
    3: [
        (0xFF84, 0x8D),
        (0xFF8C, 0x8D),
        (0xFF93, 0x8D),
    ],
}

# All $2000 PPUCTRL write sites per 32KB bank: (addr, expected_opcode)
PPUCTRL_WRITE_SITES: dict[int, list[tuple[int, int]]] = {
    0: [
        (0x802C, 0x8D), (0x8040, 0x8D), (0x8077, 0x8D), (0x811E, 0x8D),
        (0x81D6, 0x8D), (0x822A, 0x8D), (0x8254, 0x8D), (0x8274, 0x8E),  # STX $2000
        (0x8280, 0x8D), (0x8475, 0x8D), (0x84EC, 0x8D), (0x86B7, 0x8D),
        (0x8A65, 0x8D), (0x8B0E, 0x8D), (0x8B19, 0x8D), (0x8B98, 0x8D),
        (0x8BAD, 0x8D), (0x9277, 0x8D), (0x939C, 0x8D), (0x93A8, 0x8D),
        (0xA0E3, 0x8D), (0xA142, 0x8D), (0xA30C, 0x8D), (0xA44B, 0x8D),
        (0xA616, 0x8D), (0xB780, 0x8D), (0xB791, 0x8D), (0xB79D, 0x8D),
        (0xBB15, 0x8D), (0xC33F, 0x8D), (0xC34B, 0x8D), (0xC35A, 0x8D),
        (0xC55E, 0x8D), (0xC581, 0x8D), (0xC93F, 0x8D), (0xC97A, 0x8D),
        (0xF543, 0x8D),
    ],
    1: [
        (0x80DE, 0x8D),
        (0x8206, 0x8D),
    ],
    2: [],
    3: [
        (0x8099, 0x8D),
    ],
}


def make_wheel_wram_code(
    restore_addr: int,
    *,
    base_5ff0: int = 0x21,
    base_5ff1: int = 0x00,
    restore_r6: int = 0x0C,
    restore_r7: int = 0x0D,
    reward_addr: int = WHEEL_REWARD_ADDR,
    reward_magic: int = WHEEL_REWARD_MAGIC,
) -> bytes:
    """Assemble the 1024-byte ($7800-$7BFF) WRAM helper for Wheel of Fortune."""
    out = bytearray(b'\xFF' * 0x400)

    def place(addr: int, data: bytes, limit: int) -> None:
        off = addr - WHEEL_WRAM_CODE_BASE
        assert off + len(data) <= limit - WHEEL_WRAM_CODE_BASE, (
            f'Overflow at ${addr:04X}: {off + len(data)} > {limit - WHEEL_WRAM_CODE_BASE}'
        )
        out[off : off + len(data)] = data

    # 1. WHEEL_SET_BANK ($7800): virtualize AxROM $8000 write (A = bank[1:0] | nt[4])
    #    Fast-paths identical latch writes in 19 cycles so VBlank never overflows.
    a = Asm6502(WHEEL_SET_BANK)
    a.emit(0xCD, WHEEL_AX_SHADOW & 0xFF, WHEEL_AX_SHADOW >> 8)  # CMP $7FFD
    a.branch(0xF0, 'fast_done')                                 # BEQ fast_done
    a.emit(0x4C, WHEEL_SET_BANK_BODY & 0xFF, WHEEL_SET_BANK_BODY >> 8)  # JMP WHEEL_SET_BANK_BODY
    a.label('fast_done')
    a.emit(0x60)                                                # RTS
    place(WHEEL_SET_BANK, a.finish(), WHEEL_SET_BANK_X)

    # 1b. WHEEL_SET_BANK_BODY ($78B0): switches outer block only when bank bits 0-1 change,
    #     and updates precomputed WHEEL_NT_BIT ($7FFA) + $2000.
    a = Asm6502(WHEEL_SET_BANK_BODY)
    a.emit(0x48)                                                # PHA
    a.emit(0x4D, WHEEL_AX_SHADOW & 0xFF, WHEEL_AX_SHADOW >> 8)  # EOR $7FFD
    a.emit(0x29, 0x03)                                          # AND #$03
    a.branch(0xF0, 'nt_only')                                   # BEQ nt_only
    a.emit(0x68, 0x48)                                          # PLA; PHA
    a.emit(0x8D, WHEEL_AX_SHADOW & 0xFF, WHEEL_AX_SHADOW >> 8)  # STA $7FFD
    a.emit(0x29, 0x03)                                          # AND #$03
    a.emit(0x0A, 0x0A, 0x0A, 0x0A)                              # ASL A x4 (bank * $10)
    if base_5ff1:
        a.emit(0x18, 0x69, base_5ff1)                           # CLC; ADC #base_5ff1
    a.emit(0x20, WHEEL_ROM_5FF1 & 0xFF, WHEEL_ROM_5FF1 >> 8)    # JSR $FE14
    a.emit(0x68, 0x48)                                          # PLA; PHA
    a.abs_ref(0x4C, 'update_nt')                                # JMP update_nt
    a.label('nt_only')
    a.emit(0x68, 0x48)                                          # PLA; PHA
    a.emit(0x8D, WHEEL_AX_SHADOW & 0xFF, WHEEL_AX_SHADOW >> 8)  # STA $7FFD
    a.label('update_nt')
    a.emit(0x29, 0x10)                                          # AND #$10
    a.branch(0xF0, 'nt0')                                       # BEQ nt0
    a.emit(0xA9, 0x01)                                          # LDA #$01
    a.label('nt0')
    a.emit(0x4D, WHEEL_NT_XOR & 0xFF, WHEEL_NT_XOR >> 8)        # EOR $7FFB
    a.emit(0x8D, WHEEL_NT_BIT & 0xFF, WHEEL_NT_BIT >> 8)        # STA $7FFA
    a.emit(0x0D, WHEEL_PPUCTRL & 0xFF, WHEEL_PPUCTRL >> 8)      # ORA $7FFC
    a.emit(0x8D, 0x00, 0x20)                                    # STA $2000
    a.emit(0x68, 0x60)                                          # PLA; RTS
    place(WHEEL_SET_BANK_BODY, a.finish(), WHEEL_PPUSCROLL_NT0)

    # 1c. WHEEL_PPUSCROLL_NT0 ($7900) / WHEEL_PPUSCROLL_NT1 ($790C):
    #     Executes STA $2005 with A preserved and sets per-screen Vertical-mirroring NT XOR ($7FFB).
    a = Asm6502(WHEEL_PPUSCROLL_NT0)
    a.emit(0x8D, 0x05, 0x20)                                    # STA $2005
    a.emit(0x48, 0xA9, 0x00)                                    # PHA; LDA #$00
    a.emit(0x4C, (WHEEL_PPUSCROLL_NT1 + 6) & 0xFF, (WHEEL_PPUSCROLL_NT1 + 6) >> 8)
    place(WHEEL_PPUSCROLL_NT0, a.finish(), WHEEL_PPUSCROLL_NT1)

    a = Asm6502(WHEEL_PPUSCROLL_NT1)
    a.emit(0x8D, 0x05, 0x20)                                    # STA $2005 (offset +0..+2)
    a.emit(0x48, 0xA9, 0x01)                                    # PHA; LDA #$01 (offset +3..+5)
    # shared (+6):
    a.emit(0x8D, WHEEL_NT_XOR & 0xFF, WHEEL_NT_XOR >> 8)        # STA $7FFB
    a.emit(0xAD, WHEEL_AX_SHADOW & 0xFF, WHEEL_AX_SHADOW >> 8)  # LDA $7FFD
    a.emit(0x29, 0x10)                                          # AND #$10
    a.branch(0xF0, 'nt_done')                                   # BEQ nt_done
    a.emit(0xA9, 0x01)                                          # LDA #$01
    a.label('nt_done')
    a.emit(0x4D, WHEEL_NT_XOR & 0xFF, WHEEL_NT_XOR >> 8)        # EOR $7FFB
    a.emit(0x8D, WHEEL_NT_BIT & 0xFF, WHEEL_NT_BIT >> 8)        # STA $7FFA
    a.emit(0x0D, WHEEL_PPUCTRL & 0xFF, WHEEL_PPUCTRL >> 8)      # ORA $7FFC
    a.emit(0x8D, 0x00, 0x20)                                    # STA $2000
    a.emit(0x68, 0x60)                                          # PLA; RTS
    place(WHEEL_PPUSCROLL_NT1, a.finish(), WHEEL_RETURN)

    # 2. WHEEL_SET_BANK_X ($7822): virtualize STX $8000
    a = Asm6502(WHEEL_SET_BANK_X)
    a.emit(0x48, 0x8A)                                          # PHA; TXA
    a.emit(0x20, WHEEL_SET_BANK & 0xFF, WHEEL_SET_BANK >> 8)    # JSR WHEEL_SET_BANK
    a.emit(0x68, 0x60)                                          # PLA; RTS
    place(WHEEL_SET_BANK_X, a.finish(), WHEEL_PPUCTRL_A)

    # 3. WHEEL_PPUCTRL_A ($782A): shadow $2000 write (A) and inject precomputed WHEEL_NT_BIT
    a = Asm6502(WHEEL_PPUCTRL_A)
    a.emit(0x48)                                                # PHA
    a.emit(0x29, 0xFE)                                          # AND #$FE
    a.emit(0x8D, WHEEL_PPUCTRL & 0xFF, WHEEL_PPUCTRL >> 8)      # STA $7FFC
    a.emit(0x0D, WHEEL_NT_BIT & 0xFF, WHEEL_NT_BIT >> 8)        # ORA $7FFA
    a.emit(0x8D, 0x00, 0x20)                                    # STA $2000
    a.emit(0x68, 0x60)                                          # PLA; RTS
    place(WHEEL_PPUCTRL_A, a.finish(), WHEEL_PPUCTRL_X)

    # 4. WHEEL_PPUCTRL_X ($7844): shadow STX $2000
    a = Asm6502(WHEEL_PPUCTRL_X)
    a.emit(0x48, 0x8A)                                          # PHA; TXA
    a.emit(0x20, WHEEL_PPUCTRL_A & 0xFF, WHEEL_PPUCTRL_A >> 8)  # JSR WHEEL_PPUCTRL_A
    a.emit(0x68, 0x60)                                          # PLA; RTS
    place(WHEEL_PPUCTRL_X, a.finish(), WHEEL_NMI_HOOK)

    # 5. WHEEL_NMI_HOOK ($7850): 60-frame guard in $7FFF, Start+Select ($30 in $20),
    #    then dispatch to the active bank's original NMI handler preserving A, X, Y, SP.
    a = Asm6502(WHEEL_NMI_HOOK)
    a.emit(0x48)                                                # PHA
    a.emit(0xAD, WHEEL_DEBOUNCE & 0xFF, WHEEL_DEBOUNCE >> 8)    # LDA $7FFF
    a.emit(0xC9, 0x3C)                                          # CMP #$3C (60 frames)
    a.branch(0xB0, 'check_pad')                                 # BCS check_pad
    a.emit(0xEE, WHEEL_DEBOUNCE & 0xFF, WHEEL_DEBOUNCE >> 8)    # INC $7FFF
    a.branch(0xD0, 'normal_nmi')                                # BNE normal_nmi (always taken)
    a.label('check_pad')
    a.emit(0xA5, WHEEL_PAD1_ZP, 0x29, WHEEL_START_SELECT, 0xC9, WHEEL_START_SELECT)
    a.branch(0xF0, 'do_return')                                 # BEQ do_return
    a.label('normal_nmi')
    a.emit(0xAD, WHEEL_AX_SHADOW & 0xFF, WHEEL_AX_SHADOW >> 8)  # LDA $7FFD
    a.emit(0x29, 0x03)                                          # AND #$03
    a.branch(0xF0, 'nmi_b0')                                    # BEQ nmi_b0
    a.emit(0xC9, 0x01)
    a.branch(0xF0, 'nmi_b1')                                    # BEQ nmi_b1
    a.emit(0xC9, 0x02)
    a.branch(0xF0, 'nmi_b2')                                    # BEQ nmi_b2
    a.emit(0x68, 0x4C, WHEEL_ORIG_NMIS[3] & 0xFF, WHEEL_ORIG_NMIS[3] >> 8)
    a.label('nmi_b0')
    a.emit(0x68, 0x4C, WHEEL_ORIG_NMIS[0] & 0xFF, WHEEL_ORIG_NMIS[0] >> 8)
    a.label('nmi_b1')
    a.emit(0x68, 0x4C, WHEEL_ORIG_NMIS[1] & 0xFF, WHEEL_ORIG_NMIS[1] >> 8)
    a.label('nmi_b2')
    a.emit(0x68, 0x4C, WHEEL_ORIG_NMIS[2] & 0xFF, WHEEL_ORIG_NMIS[2] >> 8)
    a.label('do_return')
    a.emit(0x68)                                                # PLA
    a.emit(0xA9, 0x00, 0x8D, WHEEL_WIN_FLAG & 0xFF, WHEEL_WIN_FLAG >> 8)
    a.emit(0x4C, WHEEL_RETURN & 0xFF, WHEEL_RETURN >> 8)
    place(WHEEL_NMI_HOOK, a.finish(), WHEEL_WIN_HOOK)

    # 6. WHEEL_WIN_HOOK ($78A0): called from $C988 on Bonus Round win
    a = Asm6502(WHEEL_WIN_HOOK)
    a.emit(0xA9, reward_magic)
    a.emit(0x8D, WHEEL_WIN_FLAG & 0xFF, WHEEL_WIN_FLAG >> 8)
    a.emit(0x4C, WHEEL_RETURN & 0xFF, WHEEL_RETURN >> 8)
    place(WHEEL_WIN_HOOK, a.finish(), WHEEL_RETURN)

    # 7. WHEEL_RETURN ($7960): silence APU/PPU/IRQ, copy RAM trampoline to $0300, restore Barba/standalone
    a = Asm6502(WHEEL_RETURN)
    a.emit(0x78)                                                # SEI
    a.emit(0xA9, 0x00)
    a.emit(0x8D, 0x00, 0x20)                                    # STA $2000 (disable NMI)
    a.emit(0x8D, 0x01, 0x20)                                    # STA $2001 (disable rendering)
    a.emit(0x8D, 0x15, 0x40)                                    # STA $4015 (mute APU)
    a.emit(0x8D, 0x00, 0xE0)                                    # STA $E000 (disable MMC3 IRQ)
    a.emit(0xAE, WHEEL_WIN_FLAG & 0xFF, WHEEL_WIN_FLAG >> 8)    # LDX $7FFE (preserve win flag across $A001 switch)
    tramp = (
        bytes.fromhex(
            'a9 80 8d 01 a0 '                                   # LDA #$80; STA $A001 (unlock $5FFx)
            'a9 01 8d f0 5f '                                   # LDA #$01; STA $5FF0 (CHR-ROM mode)
            'a9 00 8d f1 5f 8d f2 5f '                          # LDA #$00; STA $5FF1; STA $5FF2
            'a9 a0 8d 01 a0 '                                   # LDA #$A0; STA $A001 (Barba WRAM bank 0)
            '8a f0 03 '                                         # TXA; BEQ +3
            '8d'
        )
        + reward_addr.to_bytes(2, 'little')                     # STA reward_addr
        + bytes([
            0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, restore_r6, 0x8D, 0x01, 0x80,
            0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, restore_r7, 0x8D, 0x01, 0x80,
            0x4C,
        ])
        + restore_addr.to_bytes(2, 'little')
    )
    a.emit(0xA0, len(tramp) - 1)                                # LDY #(len(tramp)-1)
    a.label('cp_tramp')
    a.abs_ref(0xB9, 'tramp_data')                               # LDA tramp_data,Y
    a.emit(0x99, 0x00, 0x03)                                    # STA $0300,Y
    a.emit(0x88)                                                # DEY
    a.branch(0x10, 'cp_tramp')                                  # BPL cp_tramp
    a.emit(0x4C, 0x00, 0x03)                                    # JMP $0300
    a.label('tramp_data')
    a.emit(*tramp)
    place(WHEEL_RETURN, a.finish(), WHEEL_BOOT)

    # 8. WHEEL_BOOT ($7AE0): init FK23C ($5FF0=$21 via $0320 once at boot), PPU/APU/MMC3 Vertical mirroring,
    #    map Wheel Bank 0 ($1C, $1D) and jump to Wheel Reset ($8030).
    ram_fk23c = bytes([
        0xA9, 0x80, 0x8D, 0x01, 0xA0,                           # LDA #$80; STA $A001 (unlock $5FFx)
        0xA9, base_5ff0, 0x8D, 0xF0, 0x5F,                      # LDA #base_5ff0; STA $5FF0 (CHR-RAM + 256KB MMC3)
        0xA9, base_5ff1, 0x8D, 0xF1, 0x5F,                      # LDA #base_5ff1; STA $5FF1
        0xA9, 0x00, 0x8D, 0xF2, 0x5F,                           # LDA #$00; STA $5FF2
        0xA9, 0xA3, 0x8D, 0x01, 0xA0,                           # LDA #$A3; STA $A001 (WRAM bank 3)
        0x60,                                                   # RTS
    ])
    a = Asm6502(WHEEL_BOOT)
    a.emit(0x78, 0xD8)                                          # SEI; CLD
    a.emit(0xA2, len(ram_fk23c) - 1)
    a.label('cp_ram5')
    a.abs_ref(0xBD, 'ram5_data')
    a.emit(0x9D, 0x20, 0x03, 0xCA)
    a.branch(0x10, 'cp_ram5')
    a.emit(0x20, 0x20, 0x03)                                    # JSR $0320
    a.emit(0xA9, 0x00)
    a.emit(0x8D, 0x00, 0x20)                                    # STA $2000
    a.emit(0x8D, 0x01, 0x20)                                    # STA $2001
    a.emit(0x8D, 0x15, 0x40)                                    # STA $4015
    a.emit(0x8D, 0x00, 0xE0)                                    # STA $E000 (ack/disable MMC3 IRQ)
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0xA0)                        # LDA #$00; STA $A000 (Vertical mirroring)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x1C, 0x8D, 0x01, 0x80)  # R6 = $1C
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x1D, 0x8D, 0x01, 0x80)  # R7 = $1D
    a.emit(0xA9, 0x00)
    a.emit(0x8D, WHEEL_NT_BIT & 0xFF, WHEEL_NT_BIT >> 8)
    a.emit(0x8D, WHEEL_NT_XOR & 0xFF, WHEEL_NT_XOR >> 8)
    a.emit(0x8D, WHEEL_PPUCTRL & 0xFF, WHEEL_PPUCTRL >> 8)
    a.emit(0x8D, WHEEL_AX_SHADOW & 0xFF, WHEEL_AX_SHADOW >> 8)
    a.emit(0x8D, WHEEL_WIN_FLAG & 0xFF, WHEEL_WIN_FLAG >> 8)
    a.emit(0x8D, WHEEL_DEBOUNCE & 0xFF, WHEEL_DEBOUNCE >> 8)
    a.emit(0x4C, WHEEL_RESET_TARGET & 0xFF, WHEEL_RESET_TARGET >> 8)  # JMP $8030
    a.label('ram5_data')
    a.emit(*ram_fk23c)
    place(WHEEL_BOOT, a.finish(), 0x7C00)

    return bytes(out)


def make_wheel_boot_bank0(
    restore_addr: int,
    *,
    wram_bank: int = 0xA3,
    base_5ff0: int = 0x21,
    base_5ff1: int = 0x00,
    restore_r6: int = 0x0C,
    restore_r7: int = 0x0D,
    standalone_stub: bool = False,
    reward_addr: int = WHEEL_REWARD_ADDR,
    reward_magic: int = WHEEL_REWARD_MAGIC,
) -> bytes:
    """Build 8KB loader bank 0 ($8000-$9FFF): copies $8100-$84FF -> $7800-$7BFF and jumps to WHEEL_BOOT."""
    bank0 = bytearray(b'\xFF' * 8192)
    a = Asm6502(0x8000)
    if standalone_stub:
        a.emit(0x78, 0xD8)                                      # SEI; CLD
    a.emit(0xA9, wram_bank, 0x8D, 0x01, 0xA0)                   # WRAM bank 3 enabled, $5FF0-$5FF3 UNLOCKED ($83)
    a.emit(0xA9, 0x00, 0x85, 0x00, 0x85, 0x02)                  # $00=0, $02=0
    a.emit(0xA9, 0x81, 0x85, 0x01)                              # $01=$81
    a.emit(0xA9, 0x78, 0x85, 0x03)                              # $03=$78
    a.emit(0xA2, 0x04, 0xA0, 0x00)                              # 4 pages ($8100-$84FF -> $7800-$7BFF)
    a.label('cp')
    a.emit(0xB1, 0x00, 0x91, 0x02, 0xC8)
    a.branch(0xD0, 'cp')
    a.emit(0xE6, 0x01, 0xE6, 0x03, 0xCA)
    a.branch(0xD0, 'cp')
    a.emit(0x4C, WHEEL_BOOT & 0xFF, WHEEL_BOOT >> 8)            # JMP WHEEL_BOOT ($7AE0)
    loader = a.finish()
    assert len(loader) <= 0xF0
    bank0[0 : len(loader)] = loader
    if standalone_stub:
        # $80F0: infinite loop target for standalone WHEEL_RETURN verification
        stub = bytes([0x4C, STANDALONE_RESTORE_ADDR & 0xFF, STANDALONE_RESTORE_ADDR >> 8])
        off = STANDALONE_RESTORE_ADDR - 0x8000
        bank0[off : off + len(stub)] = stub
    bank0[0x100 : 0x500] = make_wheel_wram_code(
        restore_addr,
        base_5ff0=base_5ff0,
        base_5ff1=base_5ff1,
        restore_r6=restore_r6,
        restore_r7=restore_r7,
        reward_addr=reward_addr,
        reward_magic=reward_magic,
    )
    return bytes(bank0)


def build_wheel_prize_bank(wheel_bytes: bytes) -> bytes:
    """Extract Bank 0 Bonus Prize pictures ($E162-$F57F) into an 8KB MMC3 bank ($8000-$9FFF)."""
    b0 = wheel_bytes[16 : 16 + 32768]
    bank = bytearray(b'\xFF' * 8192)
    start, end = 0xE162 - 0x8000, 0xF580 - 0x8000
    bank[start - 0x6000 : end - 0x6000] = b0[start:end]
    return bytes(bank)


def patch_wheel(
    wheel_bytes: bytes,
    *,
    base_5ff1: int = 0x00,
    z2_bytes: bytes | None = None,
) -> list[bytes]:
    """Verify and patch Wheel of Fortune -> Wheel of Barba (AxROM, 4x32KB PRG) -> [bank0..bank3]."""
    assert wheel_bytes[:4] == b'NES\x1a', 'Not an iNES ROM'
    assert wheel_bytes[4] == 8 and wheel_bytes[5] == 0, (
        f'Expected AxROM 128KB PRG + CHR-RAM (8x16KB, 0 CHR), got {wheel_bytes[4]}x16KB, {wheel_bytes[5]}'
    )
    mapper = (wheel_bytes[6] >> 4) | (wheel_bytes[7] & 0xF0)
    assert mapper == 7, f'Expected Mapper 7 (AxROM), got {mapper}'

    root_dir = Path(__file__).resolve().parent.parent
    if z2_bytes is None:
        z2_bytes = (root_dir / 'roms' / 'z2.nes').read_bytes()

    roar_out_dir = root_dir / 'build' / 'subgames' / 'wheel_roar'
    roar_out_dir.mkdir(parents=True, exist_ok=True)
    roar_dmc, roar_info = roar_sample.convert(root_dir / 'assets' / 'roar.wav', roar_out_dir)
    assert len(roar_dmc) <= (0xF532 - WHEEL_ROAR_DMC_ADDR), f'roar.dmc too large: {len(roar_dmc)}'
    dmc_addr_reg = (WHEEL_ROAR_DMC_ADDR - 0xC000) >> 6
    dmc_len_reg = (len(roar_dmc) - 1) >> 4
    dmc_rate_reg = roar_info['rate_index'] & 0x0F

    banks: list[bytes] = []
    for b in range(4):
        prg = bytearray(wheel_bytes[16 + b * 32768 : 16 + (b + 1) * 32768])
        assert len(prg) == 32768

        def patch(addr: int, new: bytes, expected: bytes, buf: bytearray = prg) -> None:
            off = addr - 0x8000
            assert bytes(buf[off : off + len(expected)]) == expected, (
                f'Unexpected Wheel bytes in bank {b} at ${addr:04X}: '
                f'{bytes(buf[off : off + len(expected)]).hex(" ")}'
            )
            buf[off : off + len(new)] = new

        # 1. NMI vector ($FFFA) -> WHEEL_NMI_HOOK ($7850)
        orig_nmi = WHEEL_ORIG_NMIS[b]
        patch(
            0xFFFA,
            bytes([WHEEL_NMI_HOOK & 0xFF, WHEEL_NMI_HOOK >> 8]),
            bytes([orig_nmi & 0xFF, orig_nmi >> 8]),
        )

        # 2. Virtualize all $8000 AxROM latch writes
        for addr, op in AXROM_WRITE_SITES[b]:
            target = WHEEL_SET_BANK_X if op == 0x8E else WHEEL_SET_BANK
            patch(
                addr,
                bytes([0x20, target & 0xFF, target >> 8]),
                bytes([op, 0x00, 0x80]),
            )

        # 3. Shadow all $2000 PPUCTRL writes to preserve virtualized nametable bit 0
        for addr, op in PPUCTRL_WRITE_SITES[b]:
            target = WHEEL_PPUCTRL_X if op == 0x8E else WHEEL_PPUCTRL_A
            patch(
                addr,
                bytes([0x20, target & 0xFF, target >> 8]),
                bytes([op, 0x00, 0x20]),
            )

        # 4. Common 16B $5FF1 switcher at $FE14 in all 4 banks
        rom_5ff1 = bytes([
            0x48,                                               # PHA
            0xA9, 0x80, 0x8D, 0x01, 0xA0,                       # LDA #$80; STA $A001 (unlock $5FFx)
            0x68, 0x8D, 0xF1, 0x5F,                             # PLA; STA $5FF1
            0xA9, 0xA3, 0x8D, 0x01, 0xA0,                       # LDA #$A3; STA $A001 (WRAM bank 3)
            0x60,                                               # RTS
        ])
        patch(WHEEL_ROM_5FF1, rom_5ff1, b'\xFF' * 16)

        # 5. Bonus Round win hook in Bank 0 ($C988) -> JMP WHEEL_WIN_HOOK ($78A0)
        if b == 0:
            patch(
                WHEEL_WIN_PATCH_ADDR,
                bytes([0x4C, WHEEL_WIN_HOOK & 0xFF, WHEEL_WIN_HOOK >> 8]),
                bytes.fromhex('a2 3e a0'),
            )
            # 5b. Per-screen Vertical-mirroring scroll fix: $B774/$926B use X=$F8 wrapping onto NT1/NT0.
            for addr in (0x926D, 0xB776):
                patch(
                    addr,
                    bytes([0x20, WHEEL_PPUSCROLL_NT1 & 0xFF, WHEEL_PPUSCROLL_NT1 >> 8]),
                    bytes([0x8D, 0x05, 0x20]),
                )
            for addr in (0x8DA3, 0xA4C1, 0xC335, 0xC4E5, 0xC9B4):
                patch(
                    addr,
                    bytes([0x20, WHEEL_PPUSCROLL_NT0 & 0xFF, WHEEL_PPUSCROLL_NT0 >> 8]),
                    bytes([0x8D, 0x05, 0x20]),
                )
            # 5b2. Compensate Sprite-0 -> $2000=$18 delay loops ($939F, $B794: LDX #$30 -> #$27)
            #      for the ~48 cycles added by two JSR WHEEL_PPUCTRL_A calls so the split lands
            #      in SL=137 HBlank instead of SL=138 visible pixels (flickering white line).
            for addr in (0x93A0, 0xB795):
                patch(addr, bytes([0x27]), bytes([0x30]))
            # 5c. Fast Bank0->Bank1($8CC8)->Bank0 VBlank CHR helper for $917C (saves ~130 cycles before SL=-1 dot 304)
            fast_b0 = Asm6502(0xFE24)
            fast_b0.emit(0xA9, 0x01, 0x8D, WHEEL_AX_SHADOW & 0xFF, WHEEL_AX_SHADOW >> 8)
            fast_b0.emit(0xA9, 0x80, 0x8D, 0x01, 0xA0)
            fast_b0.emit(0xA9, (base_5ff1 + 0x10) & 0xFF, 0x8D, 0xF1, 0x5F)
            fast_b0_bytes = fast_b0.finish()
            b1_resume_addr = 0xFE24 + len(fast_b0_bytes)
            patch(0xFE24, fast_b0_bytes, b'\xFF' * len(fast_b0_bytes))
            # Resume in Bank 0 after Bank 1 switches $5FF1 back to base_5ff1
            # Bank 1 runs: A9 A3 8D 01 A0 / 20 C8 8C / A9 00 8D FD 7F / A9 80 8D 01 A0 / A9 <base> 8D F1 5F (23 bytes)
            b0_resume_addr = b1_resume_addr + 23
            patch(b0_resume_addr, bytes([0xA9, 0xA3, 0x8D, 0x01, 0xA0, 0x60]), b'\xFF' * 6)
            patch(0x917C, bytes([0x20, 0x24, 0xFE]), bytes([0x20, 0xE0, 0xFF]))

            # 5d. Relocate Bonus Prize pictures ($E162-$F57F) to MMC3 Bank 2 ($8162-$957F)
            #     so Bank 0 $E200-$F531 holds roar.dmc in fixed $E000-$FFFF space.
            for p_off in range(0, 10, 2):
                hi_addr = 0xE124 + p_off + 1
                orig_hi = prg[hi_addr - 0x8000]
                assert 0xE1 <= orig_hi <= 0xF5
                prg[hi_addr - 0x8000] = orig_hi - 0x60

            # Embed roar.dmc at $E200 in Bank 0
            dmc_off = WHEEL_ROAR_DMC_ADDR - 0x8000
            prg[dmc_off : dmc_off + len(roar_dmc)] = roar_dmc

            # Assemble Bank 0 helpers at $FC48..$FCE0
            a_b0 = Asm6502(WHEEL_PLAY_ROAR)
            a_b0.emit(0x48)                                             # PHA
            a_b0.emit(0xA9, dmc_rate_reg, 0x8D, 0x10, 0x40)             # STA $4010
            a_b0.emit(0xA9, 0x40, 0x8D, 0x11, 0x40)                     # STA $4011 (DAC center)
            a_b0.emit(0xA9, dmc_addr_reg, 0x8D, 0x12, 0x40)             # STA $4012
            a_b0.emit(0xA9, dmc_len_reg, 0x8D, 0x13, 0x40)              # STA $4013
            a_b0.emit(0xA9, 0x0F, 0x8D, 0x15, 0x40)                     # STA $4015 (reset DMC)
            a_b0.emit(0xA9, 0x1F, 0x8D, 0x15, 0x40)                     # STA $4015 (start DMC)
            a_b0.emit(0x68, 0x60)                                       # PLA; RTS
            assert a_b0.base + len(a_b0.buf) == WHEEL_ROAR_SOLVE, f'Expected ${WHEEL_ROAR_SOLVE:04X}, got ${a_b0.base + len(a_b0.buf):04X}'
            a_b0.emit(0x20, 0x41, 0xF5)                                 # JSR $F541 (music/fanfare)
            a_b0.emit(0x4C, WHEEL_PLAY_ROAR & 0xFF, WHEEL_PLAY_ROAR >> 8)
            assert a_b0.base + len(a_b0.buf) == WHEEL_BIG_SPIN_ROAR, f'Expected ${WHEEL_BIG_SPIN_ROAR:04X}, got ${a_b0.base + len(a_b0.buf):04X}'
            a_b0.emit(0x20, 0xC9, 0xAA)                                 # JSR $AAC9 (build wedge HUD)
            a_b0.emit(0xAD, 0xFB, 0x04, 0xC9, 0xEA)                     # LDA $04FB; CMP #'F' (FREE SPIN)
            a_b0.branch(0xF0, 'spin_roar')
            a_b0.emit(0xA5, 0x6A, 0xC9, 0x1E)                           # LDA $6A; CMP #30 ($500+ wedge)
            a_b0.branch(0xB0, 'spin_roar')
            a_b0.emit(0x60)                                             # RTS
            a_b0.label('spin_roar')
            a_b0.emit(0x4C, WHEEL_PLAY_ROAR & 0xFF, WHEEL_PLAY_ROAR >> 8)
            assert a_b0.base + len(a_b0.buf) <= WHEEL_PRIZE_COPY, f'Overlap at ${a_b0.base + len(a_b0.buf):04X} > ${WHEEL_PRIZE_COPY:04X}'
            while a_b0.base + len(a_b0.buf) < WHEEL_PRIZE_COPY:
                a_b0.emit(0xEA)
            # WHEEL_PRIZE_COPY ($FC84): swap R6=2, copy 60 tiles from ($14),Y, restore R6=$1C
            a_b0.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, WHEEL_PRIZE_BANK, 0x8D, 0x01, 0x80)
            a_b0.emit(0xA5, 0xCA, 0x0A, 0xA8)                           # LDA $CA; ASL A; TAY
            a_b0.emit(0xB9, 0x24, 0xE1, 0x85, 0x14)                     # LDA $E124,Y; STA $14
            a_b0.emit(0xB9, 0x25, 0xE1, 0x85, 0x15)                     # LDA $E125,Y; STA $15
            a_b0.emit(0xA9, 0x3C, 0x85, 0x18)                           # LDA #$3C; STA $18
            a_b0.emit(0xA9, 0x11, 0x8D, 0x06, 0x20, 0xA9, 0x00, 0x8D, 0x06, 0x20)
            a_b0.emit(0xA0, 0x00)                                       # LDY #$00
            a_b0.label('p_tile')
            a_b0.emit(0xA2, 0x10)                                       # LDX #$10
            a_b0.label('p_byte')
            a_b0.emit(0xB1, 0x14, 0x8D, 0x07, 0x20, 0xC8)               # LDA ($14),Y; STA $2007; INY
            a_b0.branch(0xD0, 'p_same')
            a_b0.emit(0xE6, 0x15)                                       # INC $15
            a_b0.label('p_same')
            a_b0.emit(0xCA)                                             # DEX
            a_b0.branch(0xD0, 'p_byte')
            a_b0.emit(0xC6, 0x18)                                       # DEC $18
            a_b0.branch(0xD0, 'p_tile')
            a_b0.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, WHEEL_BANK0_R6, 0x8D, 0x01, 0x80)
            a_b0.emit(0x60)                                             # RTS
            b0_helpers = a_b0.finish()
            patch(WHEEL_PLAY_ROAR, b0_helpers, b'\xFF' * len(b0_helpers))
            patch(0xE130, bytes([0x4C, WHEEL_PRIZE_COPY & 0xFF, WHEEL_PRIZE_COPY >> 8]), bytes.fromhex('a5 ca 0a'))

            # 5e. Roar triggers on Puzzle Solve ($9750, $9A9D), Round/Match Win ($999B), and Big Spin ($A660)
            patch(0x9750, bytes([0x4C, WHEEL_ROAR_SOLVE & 0xFF, WHEEL_ROAR_SOLVE >> 8]), bytes.fromhex('4c 41 f5'))
            patch(0x9A9D, bytes([0x20, WHEEL_ROAR_SOLVE & 0xFF, WHEEL_ROAR_SOLVE >> 8]), bytes.fromhex('20 41 f5'))
            patch(0x999B, bytes([0x20, WHEEL_ROAR_SOLVE & 0xFF, WHEEL_ROAR_SOLVE >> 8]), bytes.fromhex('20 41 f5'))
            patch(0xA660, bytes([0x20, WHEEL_BIG_SPIN_ROAR & 0xFF, WHEEL_BIG_SPIN_ROAR >> 8]), bytes.fromhex('20 c9 aa'))

            # 5f. Apply Zelda II / Barba puzzles, categories, contestants, palettes, and UI text in Bank 0
            wheel_puzzles.apply_puzzle_patches_bank0(prg)
            wheel_art.apply_art_patches_bank0(prg)
        elif b == 1:
            # Matching Bank 1 half of fast $917C -> $8CC8 -> Bank 0 return trampoline
            b1_start = 0xFE24 + 15  # exact length of fast_b0_bytes (5+5+5)
            fast_b1 = bytes([
                0xA9, 0xA3, 0x8D, 0x01, 0xA0,                           # LDA #$A3; STA $A001
                0x20, 0xC8, 0x8C,                                       # JSR $8CC8
                0xA9, 0x00, 0x8D, WHEEL_AX_SHADOW & 0xFF, WHEEL_AX_SHADOW >> 8,
                0xA9, 0x80, 0x8D, 0x01, 0xA0,                           # LDA #$80; STA $A001
                0xA9, base_5ff1 & 0xFF, 0x8D, 0xF1, 0x5F,               # STA $5FF1 -> back to Bank 0
            ])
            assert len(fast_b1) == 23
            patch(b1_start, fast_b1, b'\xFF' * len(fast_b1))

            # Replace Vanna CHR frames ($8FB6 / $C1B1+) with Barba + Villainous Link and mirror roar.dmc
            wheel_art.apply_art_patches_bank1(prg, z2_bytes)
            dmc_off = WHEEL_ROAR_DMC_ADDR - 0x8000
            prg[dmc_off : dmc_off + len(roar_dmc)] = roar_dmc
        elif b == 2:
            wheel_puzzles.apply_puzzle_patches_bank2(prg)
            wheel_art.apply_art_patches_bank2(prg)

        banks.append(bytes(prg))

    return banks


def patch_wheel_for_combined(
    wheel_bytes: bytes,
    restore_addr: int,
    *,
    base_5ff0: int = 0x29,
    base_5ff1: int = 0x00,
    reward_addr: int = WHEEL_REWARD_ADDR,
    reward_magic: int = WHEEL_REWARD_MAGIC,
    z2_bytes: bytes | None = None,
) -> bytes:
    """Build 1024KB PRG (4 x 256KB outer blocks) for Wheel of Barba inside barba.nes."""
    banks = patch_wheel(wheel_bytes, base_5ff1=base_5ff1, z2_bytes=z2_bytes)
    prg1024 = bytearray(b'\xFF' * (1024 * 1024))
    prg1024[0 : 8192] = make_wheel_boot_bank0(
        restore_addr,
        base_5ff0=base_5ff0,
        base_5ff1=base_5ff1,
        restore_r6=0x0C,
        restore_r7=0x0D,
        reward_addr=reward_addr,
        reward_magic=reward_magic,
    )
    prg1024[WHEEL_PRIZE_BANK * 8192 : (WHEEL_PRIZE_BANK + 1) * 8192] = build_wheel_prize_bank(wheel_bytes)
    for b in range(4):
        base = b * (256 * 1024) + 28 * 8192
        prg1024[base : base + 32768] = banks[b]
    return bytes(prg1024)


def build_standalone(
    out_path: Path,
    wheel_path: Path = Path('roms/wheel.nes'),
    z2_path: Path | None = None,
) -> Path:
    """Wrap Wheel of Barba in a standalone 1024KB PRG + CHR-RAM NES 2.0 Mapper 176 ROM."""
    wheel_bytes = wheel_path.read_bytes()
    z2_bytes = z2_path.read_bytes() if z2_path is not None else None
    banks = patch_wheel(wheel_bytes, z2_bytes=z2_bytes)

    # Patch standalone reset vector ($FFFC) in Bank 0, Bank 1 (504..512KB power-on!), and Bank 3.
    cold_ram = bytes.fromhex(
        'a9 80 8d 01 a0 '        # $A001 = $80 (unlock $5FFx)
        'a9 21 8d f0 5f '        # $5FF0 = $21 (CHR-RAM + 256KB MMC3)
        'a9 00 8d f1 5f 8d f2 5f '  # $5FF1 = 0, $5FF2 = 0
        'a9 06 8d 00 80 a9 00 8d 01 80 '  # R6 = 0 (boot_bank0)
        '4c 00 80'               # JMP $8000
    )
    def make_cold_stub(addr: int) -> bytes:
        a_cold = Asm6502(addr)
        a_cold.emit(0x78, 0xD8, 0xA2, len(cold_ram) - 1)
        a_cold.label('cp')
        a_cold.abs_ref(0xBD, 'data')
        a_cold.emit(0x9D, 0x00, 0x03, 0xCA)
        a_cold.branch(0x10, 'cp')
        a_cold.emit(0x4C, 0x00, 0x03)
        a_cold.label('data')
        a_cold.emit(*cold_ram)
        return a_cold.finish()

    stub_len = len(make_cold_stub(0xFE00))
    rst_off = 0xFFFC - 0x8000
    for b_idx in (1, 3):
        bm = bytearray(banks[b_idx])
        idx = bm.find(b'\xFF' * stub_len, 0xFC00 - 0x8000, 0xFF80 - 0x8000)
        assert idx != -1, f'No {stub_len}B free in Bank {b_idx} $FC00-$FF7F'
        stub_addr = 0x8000 + idx
        bm[idx : idx + stub_len] = make_cold_stub(stub_addr)
        bm[rst_off : rst_off + 2] = bytes([stub_addr & 0xFF, stub_addr >> 8])
        banks[b_idx] = bytes(bm)

    b0_mut = bytearray(banks[0])
    assert b0_mut[rst_off : rst_off + 2] == bytes([WHEEL_ORIG_RESET & 0xFF, WHEEL_ORIG_RESET >> 8])
    b0_mut[rst_off : rst_off + 2] = bytes([0x00, 0x80])
    banks[0] = bytes(b0_mut)

    # Place each 32KB Wheel bank at the top 32KB (banks 28..31) of its own 256KB outer block.
    prg1024 = bytearray(b'\xFF' * (1024 * 1024))
    prg1024[0 : 8192] = make_wheel_boot_bank0(
        STANDALONE_RESTORE_ADDR,
        restore_r6=0x00,
        restore_r7=0x01,
        standalone_stub=True,
    )
    prg1024[WHEEL_PRIZE_BANK * 8192 : (WHEEL_PRIZE_BANK + 1) * 8192] = build_wheel_prize_bank(wheel_bytes)
    for b in range(4):
        base = b * (256 * 1024) + 28 * 8192
        prg1024[base : base + 32768] = banks[b]

    # NES 2.0 Mapper 176 (FK23C), 1024KB PRG, 32KB CHR-RAM (byte 11 = 0x09), 32KB PRG-RAM, Vertical mirroring
    hdr = bytearray(16)
    hdr[0:4] = b'NES\x1a'
    hdr[4] = 64     # 64 * 16KB = 1024KB PRG
    hdr[5] = 0      # 0 CHR-ROM (CHR-RAM)
    hdr[6] = 0x03   # Vertical mirroring + battery, mapper low = 0
    hdr[7] = 0xB8   # NES 2.0 + mapper mid = $B0 (176)
    hdr[10] = 0x90  # 32KB battery PRG-RAM
    hdr[11] = 0x09  # 32KB CHR-RAM

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(hdr) + bytes(prg1024))
    return out_path


if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    out = build_standalone(root / 'build/subgames/wheel.nes', root / 'roms/wheel.nes')
    rom = out.read_bytes()
    assert len(rom) == 16 + 1024 * 1024
    assert rom[0:4] == b'NES\x1a'
    assert rom[4] == 64 and rom[5] == 0
    assert rom[11] == 0x09
    assert ((rom[6] >> 4) | (rom[7] & 0xF0)) == 176
    # Verify patched NMI vector in Bank 0 and cold-boot reset vector in Bank 3
    b0_end = 16 + 256 * 1024
    assert rom[b0_end - 6 : b0_end - 4] == bytes([WHEEL_NMI_HOOK & 0xFF, WHEEL_NMI_HOOK >> 8])
    assert rom[b0_end - 4 : b0_end - 2] == bytes([0x00, 0x80])
    assert rom[-4:-2] != bytes([WHEEL_ORIG_RESET & 0xFF, WHEEL_ORIG_RESET >> 8])
    print(f'Built {out} ({len(rom)} bytes) - all assertions passed.')
