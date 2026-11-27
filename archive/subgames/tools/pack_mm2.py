"""Assemble and patch Mega Man 2 (NES, MMC1, 256KB PRG, 32KB CHR-RAM) for Barba Man 2."""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import mm2_art
import nes
import roar_sample
from pack_f13 import Asm6502
from portal_transitions import (
    TransitionAsm,
    WAVE_TABLE,
    build_return_helper,
    emit_clean_apu_mute,
)
from subgame_pack import make_rom_header


_ROOT = _TOOLS_DIR.parent
_ROAR_WAV = _ROOT / 'assets' / 'roar.wav'
_ROAR_OUT_DIR = _ROOT / 'build' / 'subgames' / 'mm2_roar'
_Z2_SOURCE = _ROOT / 'roms' / 'z2.nes'


# Fixed entry points in Bank 15 free space ($F2E3-$F8FF, 1,565 bytes)
MM2_ROM_CODE_BASE = 0xF2E3
MM2_ROM_CODE_END  = 0xF900

MM2_PRG_SWITCH      = 0xF300
MM2_CHR0            = 0xF320
MM2_CHR1            = 0xF340
MM2_NMI_HOOK        = 0xF380
MM2_WIN_HOOK        = 0xF3C0
MM2_SEED_RNG        = 0xF3D0
MM2_RETURN          = 0xF3E0
MM2_BOOT            = 0xF450
MM2_PLAY_ROAR       = 0xF470
MM2_APU_4015        = 0xF498
MM2_ROAR_BOSS_INTRO = 0xF4B0
MM2_ROAR_SFX        = 0xF4B8
MM2_HITBOX_Y        = 0xF4C0
MM2_SPAWN_Y         = 0xF4C8
MM2_TRANS_CORE      = 0xF4D0  # 112B pocket $F4D0-$F53F
MM2_WAVE_DELAY      = 0xF8C1  # 63B pocket $F8C1-$F8FF
MM2_PRE_SL          = 0xF2E3  # 13B at start of Bank 15 free window ($F2E3-$F2FF)
MM2_VB_SYNC         = 0xF2F0  # 15B in $F2E3-$F2FF
MM2_WIPE_CHECK      = 0xFF87  # 89B Pocket B ($FF87-$FFDF)
MM2_ROAR_DMC_ADDR   = 0xF540  # 64-byte aligned ($F540 - $C000) >> 6 == $D5

# Standalone-only stubs in Bank 15 tail free space ($FF87-$FFDF, 89 bytes)
STANDALONE_BOOT_STUB    = 0xFF87
STANDALONE_RESTORE_ADDR = 0xFFD0

# Unused internal RAM bytes (zeroed at boot by Bank 14 $8015-$8027)
MM2_WIN_FLAG = 0x07FE  # 0 = Start+Select exit, MM2_REWARD_MAGIC = win exit
MM2_DEBOUNCE = 0x07FF  # 60-frame ($3C) NMI debounce counter

# Barba WRAM bank 0 reward flag
MM2_REWARD_ADDR  = 0x648F
MM2_REWARD_MAGIC = 0x32  # '2'

# Mega Man 2 (USA, MMC1) addresses
MM2_ORIG_NMI        = 0xCFF0
MM2_ORIG_RESET      = 0xFFE0
MM2_ORIG_RESET_BODY = 0xF2D1
MM2_ORIG_IRQ        = 0xFFE0
MM2_CTRL_ADDR       = 0xC05D
MM2_WIN_CLEAR_ADDR  = 0xC25A  # Robot Master stage clear after Weapon Get (JMP $8076)
MM2_WIN_END_ADDR    = 0xC273  # Wily defeated after ending/credits (JMP $F2D1)


def _assemble_bank15_code(
    restore_addr: int,
    *,
    reward_addr: int = MM2_REWARD_ADDR,
    reward_magic: int = MM2_REWARD_MAGIC,
    standalone_stub: bool = False,
    roar_rate_index: int = 9,
    roar_length_reg: int = 56,
    build_number: int | None = None,
    enable_transitions: bool = False,
    game_id: int | None = None,
) -> list[tuple[int, bytes, int]]:
    """Assemble all Bank 15 virtualization, hook, return, and boot routines."""
    segments: list[tuple[int, bytes, int]] = []

    # 1. MM2_PRG_SWITCH ($F300): virtualize 16KB MMC1 PRG bank A -> MMC3 R6=2*A, R7=2*A+1
    # Preserves X, Y, P.
    a = Asm6502(MM2_PRG_SWITCH)
    a.emit(0x08, 0x78)                                              # PHP; SEI
    a.emit(0x0A, 0x48)                                              # ASL A; PHA (2*bank)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80)                            # LDA #$06; STA $8000 (R6)
    a.emit(0x68, 0x8D, 0x01, 0x80)                                  # PLA; STA $8001
    a.emit(0x09, 0x01, 0x48)                                        # ORA #$01; PHA (2*bank+1)
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80)                            # LDA #$07; STA $8000 (R7)
    a.emit(0x68, 0x8D, 0x01, 0x80)                                  # PLA; STA $8001
    a.emit(0x28, 0x60)                                              # PLP; RTS
    segments.append((MM2_PRG_SWITCH, a.finish(), MM2_CHR0))

    # 2. MM2_CHR0 ($F320): virtualize 4KB MMC1 CHR0 (A mod 8) -> MMC3 R0, R1
    # Preserves X, Y, P.
    a = Asm6502(MM2_CHR0)
    a.emit(0x08, 0x78)                                              # PHP; SEI
    a.emit(0x29, 0x07, 0x0A, 0x0A, 0x48)                            # AND #$07; ASL A; ASL A; PHA
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x80)                            # R0
    a.emit(0x68, 0x8D, 0x01, 0x80)                                  # PLA; STA $8001
    a.emit(0x18, 0x69, 0x02, 0x48)                                  # CLC; ADC #$02; PHA
    a.emit(0xA9, 0x01, 0x8D, 0x00, 0x80)                            # R1
    a.emit(0x68, 0x8D, 0x01, 0x80)                                  # PLA; STA $8001
    a.emit(0x28, 0x60)                                              # PLP; RTS
    segments.append((MM2_CHR0, a.finish(), MM2_CHR1))

    # 3. MM2_CHR1 ($F340): virtualize 4KB MMC1 CHR1 (A mod 8) -> MMC3 R2, R3, R4, R5
    # Preserves X, Y, P.
    a = Asm6502(MM2_CHR1)
    a.emit(0x08, 0x78)                                              # PHP; SEI
    a.emit(0x29, 0x07, 0x0A, 0x0A)                                  # AND #$07; ASL A; ASL A
    for reg in (2, 3, 4, 5):
        a.emit(0x48)                                                # PHA
        a.emit(0xA9, reg, 0x8D, 0x00, 0x80)                         # LDA #reg; STA $8000
        a.emit(0x68, 0x8D, 0x01, 0x80)                              # PLA; STA $8001
        if reg < 5:
            a.emit(0x18, 0x69, 0x01)                                # CLC; ADC #$01
    a.emit(0x28, 0x60)                                              # PLP; RTS
    segments.append((MM2_CHR1, a.finish(), MM2_NMI_HOOK))

    # 4. MM2_NMI_HOOK ($F380): 60-frame guard in $07FF, then direct $4016 Start+Select poll -> MM2_RETURN
    a = Asm6502(MM2_NMI_HOOK)
    a.emit(0x48)                                                    # PHA
    a.emit(0xAD, MM2_DEBOUNCE & 0xFF, MM2_DEBOUNCE >> 8)            # LDA $07FF
    if enable_transitions:
        a.emit(0x29, 0x7F)                                          # bits 0..6 = debounce, bit 7 = wipe_done
    a.emit(0xC9, 0x3C)                                              # CMP #$3C (60 frames)
    a.branch(0xB0, 'check_pad')                                     # BCS check_pad
    a.emit(0xEE, MM2_DEBOUNCE & 0xFF, MM2_DEBOUNCE >> 8)            # INC $07FF
    a.branch(0xD0, 'normal_nmi')                                    # BNE normal_nmi (always taken after INC $07FF)
    a.label('check_pad')
    a.emit(0xA9, 0x01, 0x8D, 0x16, 0x40, 0xA9, 0x00, 0x8D, 0x16, 0x40)  # strobe $4016
    a.emit(0xAD, 0x16, 0x40, 0xAD, 0x16, 0x40)                      # skip A, B
    a.emit(0xAD, 0x16, 0x40, 0x29, 0x01)                            # Select
    a.branch(0xF0, 'normal_nmi')
    a.emit(0xAD, 0x16, 0x40, 0x29, 0x01)                            # Start
    a.branch(0xD0, 'do_return')
    a.label('normal_nmi')
    if enable_transitions:
        a.emit(0x4C, MM2_WIPE_CHECK & 0xFF, MM2_WIPE_CHECK >> 8)
    else:
        a.emit(0x68, 0x4C, MM2_ORIG_NMI & 0xFF, MM2_ORIG_NMI >> 8)  # PLA; JMP $CFF0
    a.label('do_return')
    a.emit(0x68)                                                    # PLA
    a.emit(0xA9, 0x00, 0x8D, MM2_WIN_FLAG & 0xFF, MM2_WIN_FLAG >> 8)
    a.emit(0x4C, MM2_RETURN & 0xFF, MM2_RETURN >> 8)                # JMP MM2_RETURN
    segments.append((MM2_NMI_HOOK, a.finish(), MM2_WIN_HOOK))

    # 5. MM2_WIN_HOOK ($F3C0): stage clear / ending completion
    a = Asm6502(MM2_WIN_HOOK)
    a.emit(0xA9, reward_magic)                                      # LDA #reward_magic
    a.emit(0x8D, MM2_WIN_FLAG & 0xFF, MM2_WIN_FLAG >> 8)            # STA $07FE
    a.emit(0x4C, MM2_RETURN & 0xFF, MM2_RETURN >> 8)                # JMP MM2_RETURN
    segments.append((MM2_WIN_HOOK, a.finish(), MM2_SEED_RNG))

    # 5b. MM2_SEED_RNG ($F3D0): seed $4A from Barba's $7FF0 if non-zero, then LDA #$0E; JMP $C05D
    a = Asm6502(MM2_SEED_RNG)
    a.emit(0xAD, 0xF0, 0x7F)                                        # LDA $7FF0
    a.branch(0xF0, 'skip_seed')                                     # BEQ skip_seed
    a.emit(0x85, 0x4A)                                              # STA $4A
    a.label('skip_seed')
    a.emit(0xA9, 0x0E)                                              # LDA #$0E
    a.emit(0x4C, MM2_CTRL_ADDR & 0xFF, MM2_CTRL_ADDR >> 8)          # JMP $C05D
    segments.append((MM2_SEED_RNG, a.finish(), MM2_RETURN))

    # 6. MM2_RETURN ($F3E0): silence APU/PPU, copy RAM trampoline to $0300, restore Barba banks & reward
    a = Asm6502(MM2_RETURN)
    a.emit(0x78)                                                    # SEI
    if enable_transitions:
        ta = TransitionAsm(MM2_RETURN)
        ta.buf = a.buf
        ta.lda_imm(0x00)
        ta.sta(0x2000)
        ta.sta(0x4015)
        ta.sta(0x4011)
        ta.sta(0xE000)
        ta.sta(0x00)
        ta.sta(0x03)
        ta.lda_imm(0x40)
        ta.sta(0x4017)
        ta.jsr_abs(MM2_TRANS_CORE)                                  # $03=0, $00=0 -> melt-out
    a.emit(0xA9, 0x00)
    a.emit(0x8D, 0x00, 0x20)                                        # STA $2000 (disable NMI)
    a.emit(0x8D, 0x01, 0x20)                                        # STA $2001 (disable rendering)
    if not enable_transitions:
        a.emit(0x8D, 0x15, 0x40)                                    # STA $4015 (mute APU)
        a.emit(0x8D, 0x00, 0xE0)                                    # STA $E000 (disable MMC3 IRQ)
    a.emit(0xAE, MM2_WIN_FLAG & 0xFF, MM2_WIN_FLAG >> 8)            # LDX $07FE
    r6_val = 0x00 if standalone_stub else 0x0C
    r7_val = 0x01 if standalone_stub else 0x0D
    if enable_transitions:
        tramp = build_return_helper(
            restore_addr,
            reward_addr,
            game_id=game_id,
            win_reg='x',
            restore_r6=r6_val,
            restore_r7=r7_val,
        )
    else:
        tramp = (
            bytes.fromhex(
                'a9 80 8d 01 a0 '                                   # LDA #$80; STA $A001 (unlock $5FFx)
                'a9 01 8d f0 5f '                                   # LDA #$01; STA $5FF0
                'a9 00 8d f1 5f 8d f2 5f '                          # LDA #$00; STA $5FF1; STA $5FF2
                'a9 a0 8d 01 a0 '                                   # LDA #$A0; STA $A001 (WRAM bank 0)
                '8a f0 03 '                                         # TXA; BEQ +3
                '8d'
            )
            + reward_addr.to_bytes(2, 'little')                     # STA reward_addr
            + bytes([
                0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, r6_val, 0x8D, 0x01, 0x80,  # R6
                0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, r7_val, 0x8D, 0x01, 0x80,  # R7
                0x4C,                                               # JMP restore_addr
            ])
            + restore_addr.to_bytes(2, 'little')
        )
    a.emit(0xA0, len(tramp) - 1)                                    # LDY #(len(tramp)-1)
    a.label('cp_tramp')
    a.abs_ref(0xB9, 'tramp_data')                                   # LDA tramp_data,Y
    a.emit(0x99, 0x00, 0x03)                                        # STA $0300,Y
    a.emit(0x88)                                                    # DEY
    a.branch(0x10, 'cp_tramp')                                      # BPL cp_tramp
    a.emit(0x4C, 0x00, 0x03)                                        # JMP $0300
    a.label('tramp_data')
    a.emit(*tramp)
    segments.append((MM2_RETURN, a.finish(), MM2_BOOT))

    # 7. MM2_BOOT ($F450): init PPU/APU/MMC3 IRQ/mirroring, clear debounce & win flag, JMP $F2D1
    a = Asm6502(MM2_BOOT)
    a.emit(0x78, 0xD8)                                              # SEI; CLD
    a.emit(0xA9, 0x00)
    a.emit(0x8D, 0x00, 0x20)                                        # STA $2000
    a.emit(0x8D, 0x01, 0x20)                                        # STA $2001
    a.emit(0x8D, 0x15, 0x40)                                        # STA $4015
    a.emit(0x8D, 0x00, 0xE0)                                        # STA $E000 (disable MMC3 IRQ)
    a.emit(0x8D, 0x00, 0xA0)                                        # STA $A000 (Vertical mirroring)
    a.emit(0x8D, MM2_DEBOUNCE & 0xFF, MM2_DEBOUNCE >> 8)            # Clear $07FF debounce
    a.emit(0x8D, MM2_WIN_FLAG & 0xFF, MM2_WIN_FLAG >> 8)            # Clear $07FE win flag
    a.emit(0x4C, MM2_ORIG_RESET_BODY & 0xFF, MM2_ORIG_RESET_BODY >> 8)  # JMP $F2D1
    segments.append((MM2_BOOT, a.finish(), MM2_PLAY_ROAR))

    # 8. MM2_PLAY_ROAR ($F470): trigger sampled Barba DMC roar cleanly (preserves A, X, Y)
    assert (MM2_ROAR_DMC_ADDR & 0x3F) == 0
    roar_dpcm_reg = (MM2_ROAR_DMC_ADDR - 0xC000) >> 6
    a = Asm6502(MM2_PLAY_ROAR)
    a.emit(0x48)                                                    # PHA
    a.emit(0xA9, roar_rate_index, 0x8D, 0x10, 0x40)                 # LDA #rate; STA $4010
    a.emit(0xA9, 0x40, 0x8D, 0x11, 0x40)                            # LDA #$40; STA $4011
    a.emit(0xA9, roar_dpcm_reg, 0x8D, 0x12, 0x40)                   # LDA #addr; STA $4012
    a.emit(0xA9, roar_length_reg, 0x8D, 0x13, 0x40)                 # LDA #len; STA $4013
    a.emit(0xA9, 0x0F, 0x8D, 0x15, 0x40)                            # LDA #$0F; STA $4015
    a.emit(0xA9, 0x1F, 0x8D, 0x15, 0x40)                            # LDA #$1F; STA $4015 (start DMC)
    a.emit(0x68, 0x60)                                              # PLA; RTS
    segments.append((MM2_PLAY_ROAR, a.finish(), MM2_APU_4015))

    # 9. MM2_APU_4015 ($F498): Bank 12 $4015 write wrapper keeping bit 4 set while DMC active
    a = Asm6502(MM2_APU_4015)
    a.emit(0x48)                                                    # PHA
    a.emit(0xAD, 0x15, 0x40)                                        # LDA $4015
    a.emit(0x29, 0x10)                                              # AND #$10
    a.branch(0xF0, 'dmc_done')                                      # BEQ dmc_done
    a.emit(0x68, 0x09, 0x10, 0x8D, 0x15, 0x40, 0x60)                # PLA; ORA #$10; STA $4015; RTS
    a.label('dmc_done')
    a.emit(0x68, 0x8D, 0x15, 0x40, 0x60)                            # PLA; STA $4015; RTS
    segments.append((MM2_APU_4015, a.finish(), MM2_ROAR_BOSS_INTRO))

    # 10. MM2_ROAR_BOSS_INTRO ($F4B0): Bank 13 $81BA wrapper (clear OAM buffers + roar)
    a = Asm6502(MM2_ROAR_BOSS_INTRO)
    a.emit(0x20, 0x65, 0x84)                                        # JSR $8465
    a.emit(0x4C, MM2_PLAY_ROAR & 0xFF, MM2_PLAY_ROAR >> 8)          # JMP MM2_PLAY_ROAR
    segments.append((MM2_ROAR_BOSS_INTRO, a.finish(), MM2_ROAR_SFX))

    # 11. MM2_ROAR_SFX ($F4B8): Bank 13 SFX enqueue + roar wrapper
    a = Asm6502(MM2_ROAR_SFX)
    a.emit(0x20, 0x51, 0xC0)                                        # JSR $C051
    a.emit(0x4C, MM2_PLAY_ROAR & 0xFF, MM2_PLAY_ROAR >> 8)          # JMP MM2_PLAY_ROAR
    segments.append((MM2_ROAR_SFX, a.finish(), MM2_HITBOX_Y))

    # 12. MM2_HITBOX_Y ($F4C0): shift enemy-player hitbox Y center up 4px for taller Barba
    a = Asm6502(MM2_HITBOX_Y)
    a.emit(0xAD, 0xA0, 0x04)                                        # LDA $04A0
    a.emit(0x38, 0xE9, 0x04)                                        # SEC; SBC #$04
    a.emit(0x60)                                                    # RTS
    segments.append((MM2_HITBOX_Y, a.finish(), MM2_SPAWN_Y))

    # 13. MM2_SPAWN_Y ($F4C8): shift weapon spawn Y up 6px to Barba's open jaws
    a = Asm6502(MM2_SPAWN_Y)
    a.emit(0xAD, 0xA0, 0x04)                                        # LDA $04A0
    a.emit(0x38, 0xE9, 0x06)                                        # SEC; SBC #$06
    a.emit(0x60)                                                    # RTS
    segments.append((MM2_SPAWN_Y, a.finish(), MM2_TRANS_CORE if enable_transitions else MM2_ROAR_DMC_ADDR))

    if enable_transitions:
        # 15a. MM2_TRANS_CORE ($F4D0-$F53F, <= 112B): ZP ($00=frame,$01=cut,$02=band,$03=dir) frame loop
        at = TransitionAsm(MM2_TRANS_CORE)
        at.label('tr_frame')
        at.lda_imm(30)
        at.emit(0x38)                                               # SEC
        at.sbc(0x00)
        at.sta(0x01)
        at.bit_abs(0x2002)
        at.label('tr_vb')
        at.bit_abs(0x2002)
        at.branch(0x10, 'tr_vb')
        at.lda(0xF7)
        at.and_imm(0x7C)
        at.sta(0x2000)
        at.bit_abs(0x2002)
        at.lda_imm(0x00)
        at.sta(0x2006)
        at.sta(0x2006)
        at.sta(0x2005)
        at.sta(0x2005)
        at.lda(0xF8)
        at.ora_imm(0x18)
        at.sta(0x2001)
        at.jsr_abs(MM2_PRE_SL)
        at.lda_imm(0x00)
        at.sta(0x02)
        at.label('tr_band')
        at.lda(0x02)
        at.cmp_m(0x01)
        at.branch(0x90, 'tr_vis')
        at.lda_imm(0x00)
        at.sta(0x2001)
        at.lda_imm(0x3F)
        at.sta(0x2006)
        at.lda_imm(0x0F)
        at.sta(0x2006)
        at.branch(0xD0, 'tr_next')                                  # always taken ($0F != 0)
        at.label('tr_vis')
        at.jsr_abs(MM2_WAVE_DELAY)
        at.inc(0x02)
        at.lda(0x02)
        at.cmp_imm(30)
        at.branch(0x90, 'tr_band')
        at.label('tr_next')
        at.lda(0x03)
        at.branch(0xD0, 'tr_rev')
        at.inc(0x00)
        at.lda(0x00)
        at.cmp_imm(30)
        at.branch(0x90, 'tr_frame')
        at.emit(0x60)
        at.label('tr_rev')
        at.dec(0x00)
        at.branch(0x10, 'tr_frame')
        at.emit(0x60)
        segments.append((MM2_TRANS_CORE, at.finish(), MM2_ROAR_DMC_ADDR))

        # 15b. MM2_WAVE_DELAY ($F8C1-$F8FF, <= 63B): wave lookup/scale, $2005, 8-sl wait, wave table
        awd = TransitionAsm(MM2_WAVE_DELAY)
        awd.lda(0x02)
        awd.emit(0x18)                                              # CLC
        awd.adc(0x00)
        awd.and_imm(0x0F)
        awd.emit(0xAA)                                              # TAX
        awd.abs_ref(0xBD, 'wave_tbl')
        awd.ldx(0x00)
        awd.cpx_imm(8)
        awd.branch(0x90, 'half')
        awd.cpx_imm(16)
        awd.branch(0x90, 'sc_ok')
        awd.cpx_imm(24)
        awd.branch(0x90, 'x2')
        awd.emit(0x0A)
        awd.label('x2')
        awd.emit(0x0A, 0xB8)                                        # ASL A; CLV
        awd.branch(0x50, 'sc_ok')                                   # BVC sc_ok (unconditional!)
        awd.label('half')
        awd.cmp_imm(0x80)
        awd.emit(0x6A)                                              # ROR A
        awd.label('sc_ok')
        awd.sta(0x2005)
        awd.lda_imm(0x00)
        awd.sta(0x2005)
        awd.ldy_imm(156)
        awd.label('wd_wait')
        awd.emit(0x88)
        awd.branch(0xD0, 'wd_wait')
        awd.emit(0x60)
        awd.label('wave_tbl')
        awd.emit(*WAVE_TABLE)
        segments.append((MM2_WAVE_DELAY, awd.finish(), 0xF900))

        # 15c. $F2E3-$F2FF (29B): MM2_PRE_SL (13B) + MM2_VB_SYNC (15B), and Pocket B $FF87-$FFDF (89B): MM2_WIPE_CHECK
        ap = TransitionAsm(MM2_PRE_SL)
        ap.ldx_imm(21)
        ap.label('pre_sl')
        ap.ldy_imm(21)
        ap.label('pre_in')
        ap.emit(0x88)
        ap.branch(0xD0, 'pre_in')
        ap.emit(0xEA, 0xCA)
        ap.branch(0xD0, 'pre_sl')
        ap.emit(0x60)
        segments.append((MM2_PRE_SL, ap.finish(), MM2_VB_SYNC))

        av = TransitionAsm(MM2_VB_SYNC)
        av.bit_abs(0x2002)
        av.label('vb2')
        av.bit_abs(0x2002)
        av.branch(0x10, 'vb2')
        av.sta(0x2006)
        av.sta(0x2006)
        av.emit(0x60)
        segments.append((MM2_VB_SYNC, av.finish(), MM2_PRG_SWITCH))

        awc = TransitionAsm(MM2_WIPE_CHECK)
        awc.bit_abs(MM2_DEBOUNCE)
        awc.branch(0x30, 'wchk_orig')
        awc.lda(0xF8)
        awc.and_imm(0x08)
        awc.branch(0xF0, 'wchk_orig')
        awc.lda(MM2_DEBOUNCE)
        awc.and_imm(0x7F)
        awc.cmp_imm(0x04)
        awc.branch(0x90, 'wchk_orig')
        awc.emit(0x8A, 0x48, 0x98, 0x48)                            # TXA; PHA; TYA; PHA
        awc.ldx_imm(0x00)
        awc.label('zp_sv')
        awc.emit(0xB5, 0x00, 0x48, 0xE8, 0xE0, 0x04)                # LDA $00,X; PHA; INX; CPX #4
        awc.branch(0xD0, 'zp_sv')
        awc.lda(MM2_DEBOUNCE)
        awc.ora_imm(0x80)
        awc.sta(MM2_DEBOUNCE)
        awc.lda(0xF7)
        awc.and_imm(0x7F)
        awc.sta(0x2000)
        awc.lda_imm(0x01)
        awc.sta(0x03)
        awc.lda_imm(29)
        awc.sta(0x00)
        awc.jsr_abs(MM2_TRANS_CORE)
        awc.lda_imm(0x00)
        awc.jsr_abs(MM2_VB_SYNC)
        awc.sta(0x2005)
        awc.sta(0x2005)
        awc.ldx_imm(0x03)
        awc.label('zp_rs')
        awc.emit(0x68, 0x95, 0x00, 0xCA)                            # PLA; STA $00,X; DEX
        awc.branch(0x10, 'zp_rs')
        awc.emit(0x68, 0xA8, 0x68, 0xAA)                            # PLA; TAY; PLA; TAX
        awc.label('wchk_orig')
        awc.emit(0x68)                                              # PLA
        awc.jmp_abs(MM2_ORIG_NMI)
        segments.append((MM2_WIPE_CHECK, awc.finish(), 0xFFE0))

    return segments


def patch_mm2(
    mm2_bytes: bytes,
    restore_addr: int = STANDALONE_RESTORE_ADDR,
    *,
    reward_addr: int = MM2_REWARD_ADDR,
    reward_magic: int = MM2_REWARD_MAGIC,
    standalone_stub: bool = False,
    z2_bytes: bytes | None = None,
    build_number: int | None = None,
    enable_transitions: bool = False,
    game_id: int | None = None,
) -> bytes:
    """Verify and patch Mega Man 2 (MMC1, 256KB PRG, 32KB CHR-RAM) into Barba Man 2."""
    assert mm2_bytes[:4] == b'NES\x1a', 'Not an iNES ROM'
    assert mm2_bytes[4] == 16 and mm2_bytes[5] == 0, (
        f'Expected 16x16KB PRG and 0x8KB CHR, got {mm2_bytes[4]}x16KB, {mm2_bytes[5]}x8KB'
    )
    mapper = (mm2_bytes[6] >> 4) | (mm2_bytes[7] & 0xF0)
    assert mapper == 1, f'Expected Mapper 1 (MMC1), got {mapper}'

    if z2_bytes is None:
        z2_bytes = nes.load_source(_Z2_SOURCE)
    roar_dmc, roar_info = roar_sample.convert_soft(_ROAR_WAV, _ROAR_OUT_DIR)

    prg = bytearray(mm2_bytes[16 : 16 + 256 * 1024])
    assert len(prg) == 256 * 1024
    written_ranges: list[tuple[int, int]] = []

    def _claim_range(off: int, length: int) -> None:
        end = off + length
        for prev_start, prev_end in written_ranges:
            assert end <= prev_start or off >= prev_end, (
                f'Overlapping ROM write at 0x{off:06X}..0x{end:06X} '
                f'(overlaps 0x{prev_start:06X}..0x{prev_end:06X})'
            )
        written_ranges.append((off, end))

    def patch_bank(
        bank: int,
        addr: int,
        new: bytes,
        expected: bytes | None = None,
        *,
        expected_sha256: str | None = None,
    ) -> None:
        base = 0xC000 if bank == 15 else 0x8000
        off = bank * 0x4000 + (addr - base)
        _claim_range(off, len(new))
        orig = bytes(prg[off : off + len(new)])
        if expected is not None:
            assert len(expected) == len(new), f'Length mismatch at bank {bank} ${addr:04X}'
            assert orig == expected, (
                f'Unexpected MM2 bytes at bank {bank} ${addr:04X}: {orig.hex(" ")}'
            )
        elif expected_sha256 is not None:
            actual_sha = hashlib.sha256(orig).hexdigest()[:len(expected_sha256)]
            assert actual_sha == expected_sha256, (
                f'Unexpected MM2 SHA at bank {bank} ${addr:04X}: {actual_sha} != {expected_sha256}'
            )
        else:
            raise ValueError('Either expected or expected_sha256 must be provided')
        prg[off : off + len(new)] = new

    # 1. Place Bank 15 virtualization, hook, return, boot, and roar code in $F2E3-$F53F
    for addr, data, limit in _assemble_bank15_code(
        restore_addr,
        reward_addr=reward_addr,
        reward_magic=reward_magic,
        standalone_stub=standalone_stub,
        roar_rate_index=roar_info['rate_index'],
        roar_length_reg=roar_info['length_reg'],
        build_number=build_number,
        enable_transitions=enable_transitions,
        game_id=game_id,
    ):
        assert addr + len(data) <= limit, (
            f'Overflow at ${addr:04X}: {addr + len(data):04X} > {limit:04X}'
        )
        patch_bank(15, addr, data, b'\xFF' * len(data))

    # 2. Virtualize Fixed Bank 15 MMC1 PRG writes ($C006, $C024, $D097)
    mmc1_prg_seq = bytes.fromhex('8d f0 ff 4a 8d f0 ff 4a 8d f0 ff 4a 8d f0 ff 4a 8d f0 ff')
    for patch_addr, ret_addr in ((0xC006, 0xC019), (0xC024, 0xC037), (0xD097, 0xD0AA)):
        repl = bytes([
            0x20, MM2_PRG_SWITCH & 0xFF, MM2_PRG_SWITCH >> 8,
            0x4C, ret_addr & 0xFF, ret_addr >> 8,
        ]) + b'\xEA' * (len(mmc1_prg_seq) - 6)
        patch_bank(15, patch_addr, repl, mmc1_prg_seq)

    # 3. Virtualize Fixed Bank 15 MMC1 Control/mirroring write ($C05D..$C070)
    mmc1_ctrl_seq = bytes.fromhex('8d ff 9f 4a 8d ff 9f 4a 8d ff 9f 4a 8d ff 9f 4a 8d ff 9f 60')
    ctrl_repl = bytes.fromhex('29 01 8d 00 a0 60') + b'\xEA' * (len(mmc1_ctrl_seq) - 6)
    patch_bank(15, MM2_CTRL_ADDR, ctrl_repl, mmc1_ctrl_seq)

    # 4. Virtualize Bank 14 CHR0/CHR1 writes ($802F, $8044)
    mmc1_chr0_seq = bytes.fromhex('8d ff bf 4a 8d ff bf 4a 8d ff bf 4a 8d ff bf 4a 8d ff bf')
    chr0_repl = bytes([
        0x20, MM2_CHR0 & 0xFF, MM2_CHR0 >> 8,
        0x4C, 0x42, 0x80,
    ]) + b'\xEA' * (len(mmc1_chr0_seq) - 6)
    patch_bank(14, 0x802F, chr0_repl, mmc1_chr0_seq)

    mmc1_chr1_seq = bytes.fromhex('8d ff df 4a 8d ff df 4a 8d ff df 4a 8d ff df 4a 8d ff df')
    chr1_repl = bytes([
        0x20, MM2_CHR1 & 0xFF, MM2_CHR1 >> 8,
        0x4C, 0x57, 0x80,
    ]) + b'\xEA' * (len(mmc1_chr1_seq) - 6)
    patch_bank(14, 0x8044, chr1_repl, mmc1_chr1_seq)

    # 5. NOP out INC $FFE1 at $FFE1 so odd-$E000-$FFFF write cannot enable MMC3 IRQs
    patch_bank(15, 0xFFE1, b'\xEA\xEA\xEA', bytes.fromhex('ee e1 ff'))

    # 6. Hook stage clear ($C25A) and ending completion ($C273) -> JMP MM2_WIN_HOOK
    win_jmp = bytes([0x4C, MM2_WIN_HOOK & 0xFF, MM2_WIN_HOOK >> 8])
    patch_bank(15, MM2_WIN_CLEAR_ADDR, win_jmp, bytes.fromhex('4c 76 80'))
    patch_bank(15, MM2_WIN_END_ADDR, win_jmp, bytes.fromhex('4c d1 f2'))

    # 7. Hook NMI vector ($FFFA) -> MM2_NMI_HOOK
    patch_bank(
        15,
        0xFFFA,
        bytes([MM2_NMI_HOOK & 0xFF, MM2_NMI_HOOK >> 8]),
        bytes([MM2_ORIG_NMI & 0xFF, MM2_ORIG_NMI >> 8]),
    )

    # 8. Boot RNG seed (Bank 14 $8028: LDA #$0E; JSR $C05D -> JSR MM2_SEED_RNG)
    patch_bank(
        14,
        0x8028,
        bytes([0x20, MM2_SEED_RNG & 0xFF, MM2_SEED_RNG >> 8, 0xEA, 0xEA]),
        bytes.fromhex('a9 0e 20 5d c0'),
    )

    # 9. Sampled Barba roar DMC data at $F540..$F8C0 + Bank 12 $4015 wrapper + Bank 13 triggers
    assert MM2_ROAR_DMC_ADDR + len(roar_dmc) <= MM2_ROM_CODE_END
    patch_bank(15, MM2_ROAR_DMC_ADDR, roar_dmc, b'\xFF' * len(roar_dmc))

    jsr_apu4015 = bytes([0x20, MM2_APU_4015 & 0xFF, MM2_APU_4015 >> 8])
    for addr in (0x8231, 0x84CE, 0x8505):
        patch_bank(12, addr, jsr_apu4015, bytes.fromhex('8d 15 40'))

    patch_bank(
        13,
        0x81B8,
        bytes([0x20, MM2_ROAR_BOSS_INTRO & 0xFF, MM2_ROAR_BOSS_INTRO >> 8]),
        bytes.fromhex('20 65 84'),
    )
    jsr_roar_sfx = bytes([0x20, MM2_ROAR_SFX & 0xFF, MM2_ROAR_SFX >> 8])
    for addr in (0x96DC, 0x98BC, 0x9B69, 0xBB0C):
        patch_bank(13, addr, jsr_roar_sfx, bytes.fromhex('20 51 c0'))

    # 10. Barba gameplay CHR tiles ($00..$8F in Bank 0 $9000) & Fireball CHR ($69-$6A)
    barba_tiles, frame_data, custom_layouts, _ = mm2_art.compile_barba_gameplay(z2_bytes)
    fb_tiles, layout_a4, frame_22 = mm2_art.compile_barba_fireball()
    b0_9000_sha = hashlib.sha256(prg[0x1000:0x1900]).hexdigest()[:16]
    assert b0_9000_sha == 'bcf4e4dbc2439eff', f'Unexpected Bank 0 $9000 SHA: {b0_9000_sha}'
    for tid, tile_bytes in {**barba_tiles, **fb_tiles}.items():
        assert 0 <= tid < 0x90 and len(tile_bytes) == 16
        off = 0x1000 + tid * 16
        _claim_range(off, 16)
        prg[off : off + 16] = tile_bytes

    # 11. Bank 10 Barba metasprites (Frames $00..$21), custom layouts ($A5+), Fireball Frame $22 & Layout $A4
    b10_cursor = 0xBB36
    b10_end = 0xBFE0
    all_layouts = {mm2_art.FIREBALL_LAYOUT_ID: layout_a4, **custom_layouts}
    for lid in sorted(all_layouts):
        lbytes = all_layouts[lid]
        assert b10_cursor + len(lbytes) <= b10_end, f'Bank 10 layout overflow at ${b10_cursor:04X}'
        laddr = b10_cursor
        patch_bank(10, laddr, lbytes, b'\xFF' * len(lbytes))
        b10_cursor += len(lbytes)
        patch_bank(10, 0x8400 + lid, bytes([laddr & 0xFF]), b'\xFF')
        patch_bank(10, 0x8500 + lid, bytes([laddr >> 8]), b'\xFF')

    all_frames = {**frame_data, 0x22: frame_22}
    blob_to_addr: dict[bytes, int] = {}
    new_lo = bytearray(0x23)
    new_hi = bytearray(0x23)
    for fid in range(0x23):
        blob = all_frames[fid]
        if blob not in blob_to_addr:
            assert b10_cursor + len(blob) <= b10_end, f'Bank 10 overflow at ${b10_cursor:04X}'
            patch_bank(10, b10_cursor, blob, b'\xFF' * len(blob))
            blob_to_addr[blob] = b10_cursor
            b10_cursor += len(blob)
        faddr = blob_to_addr[blob]
        new_lo[fid] = faddr & 0xFF
        new_hi[fid] = faddr >> 8

    expected_lo = bytes.fromhex('0000162a3c52687e96aec4daee0216283a50667c92aabacad6eafe141e343e566a828e')
    expected_hi = bytes.fromhex('8787878787878787878787878788888888888888888888888888888989898989898989')
    patch_bank(10, 0x8000, bytes(new_lo), expected_lo)
    patch_bank(10, 0x8200, bytes(new_hi), expected_hi)

    # 12. Barba flame palette (Pal 0: $16 crimson, $27 amber-orange, $30 cream-white)
    barba_pal = bytes.fromhex('16 27 30')
    vanilla_pal = bytes.fromhex('0f 2c 11')
    patch_bank(15, 0xD303, barba_pal, vanilla_pal)
    for bank in range(8):
        patch_bank(bank, 0xBE13, barba_pal, vanilla_pal)
    for bank in range(6):
        patch_bank(bank, 0xBF13, barba_pal, vanilla_pal)

    # 13. Villainous Link replacing Dr. Wily (Stage Select, Reveal/Castle, Boss, Surrender)
    vlink = mm2_art.compile_villain_link(z2_bytes)
    patch_bank(11, 0xB02E, bytes.fromhex('05 16 09 0c'), bytes.fromhex('04 1b 20 20'))  # 'EVIL'
    patch_bank(11, 0xB04F, bytes.fromhex('0c 09 0e 0b'), bytes.fromhex('17 09 0c 19'))  # 'LINK'

    vlink_chr_patches = [
        (8, 0x8F00, vlink['ss_portrait'],         '2e21def9dd188c13'),
        (6, 0x9400, vlink['b6_ufo_pilot_closed'], '896309a2e8ff1744'),
        (6, 0x9460, vlink['b6_ufo_pilot_open'],   'dafba30f7bab08c9'),
        (6, 0x9500, vlink['b6_ufo_sil'],          '2f08d71cbb6572b7'),
        (6, 0x95C0, vlink['b6_bust'],             'b9f3c2bddfa6e87a'),
        (6, 0x9640, vlink['b6_emblem'],           '8d882ea2ab341bc1'),
        (5, 0x95A0, vlink['b5_pilot_top'],        '0b34bdff514d3890'),
        (5, 0x95E0, vlink['b5_pilot_bot'],        '5215a404ec929c7a'),
        (5, 0x9630, vlink['b5_pilot_open'],       'b892e1b31f9fdbfc'),
        (5, 0x94B0, vlink['b5_triforce'],         '28b25dae4bb0c69a'),
        (8, 0xBA10, vlink['b8_surrender_d0'],     '4cf8854c43ed7cce'),
        (8, 0xBAA0, vlink['b8_surrender_d1'],     'a6138154b949969a'),
        (8, 0xBB10, vlink['b8_surrender_d2'],     '778f6ea35a66376e'),
    ]
    for bank, addr, blob, sha in vlink_chr_patches:
        assert isinstance(blob, bytes)
        patch_bank(bank, addr, blob, expected_sha256=sha)

    # 14. Collision, hitbox, and fireball spawn adjustments for wider/taller 32x40 Barba
    # Bank 14 tile collision: 22px physical width (X +/- 11 walls, X +/- 10 floor/ceil),
    # 32px physical height (Y - 20 ceiling, Y + 12 floor) so Barba clears 32px corridors.
    patch_bank(14, 0x8969, b'\x69\x0B', b'\x69\x08')
    patch_bank(14, 0x89D5, b'\xE9\x0B', b'\xE9\x08')
    patch_bank(14, 0x8CED, bytes.fromhex('0a f6 00 ff'), bytes.fromhex('07 f9 00 ff'))
    patch_bank(14, 0x8A7E, bytes.fromhex('ec fc 0b ff ff 00'), bytes.fromhex('f4 fc 0b ff ff 00'))
    patch_bank(14, 0x8B54, b'\xE9\x14', b'\xE9\x0C')
    patch_bank(14, 0x8BDB, b'\xE9\x14', b'\xE9\x0C')

    # Bank 15 enemy-player hitbox: widen X (+3) & Y (+4), shift Y center up 4px
    b15_off = 15 * 0x4000
    orig_hx = bytes(prg[b15_off + 0x14E4 : b15_off + 0x1584])
    orig_hy = bytes(prg[b15_off + 0x1584 : b15_off + 0x1624])
    patch_bank(15, 0xD4E4, bytes(min(0xFF, b + 3) for b in orig_hx), expected_sha256='657082a48ab39704')
    patch_bank(15, 0xD584, bytes(min(0xFF, b + 4) for b in orig_hy), expected_sha256='18d7a775cd9f2d3f')
    patch_bank(15, 0xE57E, bytes([0x20, MM2_HITBOX_Y & 0xFF, MM2_HITBOX_Y >> 8]), bytes.fromhex('ad a0 04'))

    # Bank 15 Mega Buster fireball spawn: +4px forward (snout tip) & -6px Y (open jaws)
    patch_bank(15, 0xD473, b'\x14', b'\x10')
    patch_bank(15, 0xD41C, bytes([0x20, MM2_SPAWN_Y & 0xFF, MM2_SPAWN_Y >> 8]), bytes.fromhex('ad a0 04'))

    # 15. Title Screen: 'MEGA BARBA II' logo (Bank 9 $B2A0) + Rooftop Barba (Bank 6 $9000) + Palettes
    patch_bank(9, 0xB2A0, mm2_art.compile_title_logo(), expected_sha256='defa368519923d69')
    tbarba = mm2_art.compile_title_barba(z2_bytes)
    patch_bank(6, 0x9000, tbarba['b6_barba_idle'], expected_sha256='ed08eb1ddabc2456')
    patch_bank(6, 0x9090, tbarba['b6_barba_anim'], expected_sha256='bd494d871234bb4f')
    patch_bank(6, 0x91F0, tbarba['b6_face_blank'], expected_sha256='8efc9cd8fcb4cea9')
    title_barba_pal = bytes.fromhex('16 27 30 0f 16 27 30 0f')
    title_orig_pal = bytes.fromhex('0f 2c 11 0f 0f 30 38 0f')
    for addr in (0xAA60, 0xAA80, 0xAAA0):
        patch_bank(13, addr, title_barba_pal, title_orig_pal)
    # Frame 1 rooftop metasprite ($AB6A): swap rows 1..2 ($09..$0E) for small_step while keeping row 0 blank ($00..$02)
    patch_bank(
        13,
        0xAB6A,
        bytes.fromhex(
            '0b 00 00 01 c8 00 01 01 d0 00 02 01 d8 '
            '08 09 00 c8 08 0a 00 d0 08 0b 00 d8 '
            '08 1f 01 c8 08 20 01 d0 '
            '10 0c 00 c8 10 0d 00 d0 10 0e 00 d8'
        ),
        bytes.fromhex(
            '0b 00 09 01 c8 00 0a 01 d0 00 0b 01 d8 '
            '08 03 00 c8 08 04 00 d0 08 05 00 d8 '
            '08 1f 01 c8 08 20 01 d0 '
            '10 06 00 c8 10 07 00 d0 10 08 00 d8'
        ),
    )
    # Slow title rooftop idle toggle from 5 frames (12 Hz) to 12 frames (5 Hz) for overworld bob
    patch_bank(13, 0xA5FA, bytes.fromhex('a9 0c 8d 90 06'), bytes.fromhex('a9 05 8d 90 06'))

    if build_number is not None:
        # Stamp B<N> into Bank 13 rooftop nametable row 1 cols 26..30 ($B6CB; sky $00).
        # Bank 9 $A000..$AFFF holds title BG CHR: '0'=A0,'1'=A7,'2'=A2,'5'=A8,'8'=A1,'9'=A5,'B'=C2.
        # Add missing digits '3','4','6','7' in empty Bank 9 slots $BD..$C0 ($ABD0..$AC00).
        extra_digits = {
            '3': (0xBD, bytes.fromhex('007cc6063c06c67c') + bytes(8)),
            '4': (0xBE, bytes.fromhex('000c1c3c6cfe0c0c') + bytes(8)),
            '6': (0xBF, bytes.fromhex('007cc0fcc6c6c67c') + bytes(8)),
            '7': (0xC0, bytes.fromhex('00fe060c18303030') + bytes(8)),
        }
        for _d, (tid, tbytes) in extra_digits.items():
            patch_bank(9, 0xA000 + tid * 16, tbytes, b'\x00' * 16)
        mm2_digits = {'0': 0xA0, '1': 0xA7, '2': 0xA2, '5': 0xA8, '8': 0xA1, '9': 0xA5}
        for d, (tid, _) in extra_digits.items():
            mm2_digits[d] = tid
        tag_tiles = bytes(0xC2 if ch == 'B' else mm2_digits[ch] for ch in f'B{build_number}')
        patch_bank(13, 0xB6CB, tag_tiles, b'\x00' * len(tag_tiles))

    return bytes(prg)


def build_standalone(
    out_path: Path,
    mm2_path: Path = Path('roms/mm2.nes'),
    *,
    mapper: str = '176',
    build_number: int | None = None,
) -> Path:
    """Wrap patched Mega Man 2 in a standalone 256KB PRG + 32KB CHR-RAM ROM (Mapper 176 or NES 2.0 MMC3)."""
    from build_history import HISTORY_FILE, next_subgame_build_number, record_subgame_build
    import hashlib
    record_this = build_number is None
    if build_number is None:
        build_number = next_subgame_build_number(HISTORY_FILE, 'mm2')
    mm2_bytes = mm2_path.read_bytes()
    prg = bytearray(patch_mm2(mm2_bytes, restore_addr=STANDALONE_RESTORE_ADDR, standalone_stub=True, build_number=build_number))

    def patch_b15(addr: int, new: bytes, expected: bytes) -> None:
        off = 15 * 0x4000 + (addr - 0xC000)
        assert bytes(prg[off : off + len(expected)]) == expected, (
            f'Unexpected bytes at ${addr:04X}'
        )
        prg[off : off + len(new)] = new

    # Standalone boot stub at $FF87
    a = Asm6502(STANDALONE_BOOT_STUB)
    a.emit(0x78, 0xD8)                                              # SEI; CLD
    a.emit(0xA9, 0x80, 0x8D, 0x01, 0xA0)                            # LDA #$80; STA $A001 (enable WRAM / unlock $5FFx)
    if mapper == '176':
        a.emit(0xA9, 0x21, 0x8D, 0xF0, 0x5F)                        # LDA #$21; STA $5FF0 (32KB CHR-RAM via R0..R5)
        a.emit(0xA9, 0x00, 0x8D, 0xF1, 0x5F, 0x8D, 0xF2, 0x5F)      # LDA #$00; STA $5FF1; STA $5FF2
    a.emit(0x4C, MM2_BOOT & 0xFF, MM2_BOOT >> 8)                    # JMP MM2_BOOT
    boot_stub = a.finish()
    assert STANDALONE_BOOT_STUB + len(boot_stub) <= STANDALONE_RESTORE_ADDR
    patch_b15(STANDALONE_BOOT_STUB, boot_stub, b'\xFF' * len(boot_stub))

    # Standalone restore target ($FFD0): JMP $FFD0
    patch_b15(
        STANDALONE_RESTORE_ADDR,
        bytes([0x4C, STANDALONE_RESTORE_ADDR & 0xFF, STANDALONE_RESTORE_ADDR >> 8]),
        b'\xFF\xFF\xFF',
    )

    # Standalone reset vector ($FFFC) -> STANDALONE_BOOT_STUB
    patch_b15(
        0xFFFC,
        bytes([STANDALONE_BOOT_STUB & 0xFF, STANDALONE_BOOT_STUB >> 8]),
        bytes([MM2_ORIG_RESET & 0xFF, MM2_ORIG_RESET >> 8]),
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
        record_subgame_build(HISTORY_FILE, 'mm2', build_number, mapper, out_path, hashlib.sha256(rom_bytes).hexdigest())
    return out_path


if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=None)
    parser.add_argument('--mapper', choices=('176', 'mmc3'), default='176')
    args = parser.parse_args()
    default_out = root / ('play/compat/nes/mm2-compat.nes' if args.mapper == 'mmc3' else 'build/subgames/mm2.nes')
    out = build_standalone(args.out or default_out, root / 'roms/mm2.nes', mapper=args.mapper)
    if args.mapper == 'mmc3' and args.out is None:
        from bps import write_bps
        write_bps(
            root / 'roms/mm2.nes',
            out,
            out_bps_path=root / 'play/compat/bps/mm2-compat.bps',
            metadata='mm2-compat | Barba Edition (MMC3)',
        )
    rom = out.read_bytes()
    expected_mapper = 4 if args.mapper == 'mmc3' else 176
    expected_chr_banks = 0 if args.mapper == 'mmc3' else 1
    assert len(rom) == 16 + 256 * 1024 + expected_chr_banks * 8192
    assert rom[0:4] == b'NES\x1a'
    assert rom[4] == 16 and rom[5] == expected_chr_banks
    assert rom[11] == 0x09
    assert ((rom[6] >> 4) | (rom[7] & 0xF0)) == expected_mapper
    assert rom[16 + 256 * 1024 - 6 : 16 + 256 * 1024 - 4] == bytes([MM2_NMI_HOOK & 0xFF, MM2_NMI_HOOK >> 8])
    assert rom[16 + 256 * 1024 - 4 : 16 + 256 * 1024 - 2] == bytes([STANDALONE_BOOT_STUB & 0xFF, STANDALONE_BOOT_STUB >> 8])
    print(f'Built {out} ({len(rom)} bytes, mapper={expected_mapper}) - all assertions passed.')
