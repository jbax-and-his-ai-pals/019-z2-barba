"""Assemble and patch Friday the 13th (NES, CNROM) for the Barba Mapper 176 portal."""
from __future__ import annotations


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

    def lda_lo(self, target: str) -> None:
        self.emit(0xA9, 0)
        self.fixups.append(('lo', len(self.buf) - 1, target))

    def lda_hi(self, target: str) -> None:
        self.emit(0xA9, 0)
        self.fixups.append(('hi', len(self.buf) - 1, target))

    def finish(self) -> bytes:
        for kind, pos, target in self.fixups:
            addr = self.labels[target]
            if kind == 'rel':
                rel = addr - (self.base + pos + 1)
                assert -128 <= rel <= 127, f'Branch out of range to {target}: {rel}'
                self.buf[pos] = rel & 0xFF
            elif kind == 'lo':
                self.buf[pos] = addr & 0xFF
            elif kind == 'hi':
                self.buf[pos] = (addr >> 8) & 0xFF
            else:
                self.buf[pos] = addr & 0xFF
                self.buf[pos + 1] = (addr >> 8) & 0xFF
        return bytes(self.buf)


# Fixed entry points in WRAM bank 3 ($7800-$7BFF)
F13_CHR_SWITCH   = 0x7800
F13_NMI_HOOK     = 0x7852
F13_WIPE_IN      = 0x786F
F13_SEED_RNG     = 0x795E
F13_RETURN       = 0x796C
F13_BOOT         = 0x7ADC
F13_RELOC_E5B4   = 0x7B17
F13_BARBA_DRAW   = 0x7B2A
F13_BARBA_BREATH = 0x7B3E
F13_BARBA_RESET  = 0x7B53
F13_ATK_GATE     = 0x7B60
F13_SAVE_OAM_PTR = 0x7B6B
F13_SFX_CALL     = 0x7B8C
F13_SET_R6       = 0x7B9E
F13_NMI_WRAP     = 0x7BB3
F13_WR_SEL       = 0x7BF4
F13_WIN_HOOK     = 0x7E80
F13_CANCEL_HOOK  = 0x7E88
F13_EXIT_TRAMP   = 0x7E98
F13_TITLE_ART    = 0x7ACC  # 13B Bank-1 $800C caller placed right before F13_BOOT

F13_MMC3_SEL     = 0x7BFB  # shadow of $8000 bank-select register
F13_CUR_R6       = 0x7BFC  # shadow of current R6 PRG bank
F13_WIN_FLAG     = 0x7FFA  # 0 = Start+Select exit, non-zero = win exit


def make_barba_trampolines() -> bytes:
    """Assemble WRAM bank-1 trampolines ($7B38-$7BFA) shared by standalone and Z2 F13."""
    out = bytearray(b'\xFF' * (0x7BFE - F13_BARBA_DRAW))

    def place_t(addr: int, data: bytes, limit: int) -> None:
        off = addr - F13_BARBA_DRAW
        assert off + len(data) <= limit - F13_BARBA_DRAW, f'Trampoline overflow at ${addr:04X}'
        out[off : off + len(data)] = data

    def bank_call(entry_addr: int, pre_call: tuple[int, ...] = (), save_x: bool = False) -> bytes:
        a = Asm6502(entry_addr)  # base unused; no branches
        for b in pre_call:
            a.emit(b)
        if save_x:
            a.emit(0x8A, 0x48)                                # TXA; PHA
        a.emit(0xA9, 0x01, 0x20, F13_SET_R6 & 0xFF, F13_SET_R6 >> 8)
        a.emit(0x20, entry_addr & 0xFF, entry_addr >> 8)
        if save_x:
            a.emit(0xA9, 0x04, 0x20, F13_SET_R6 & 0xFF, F13_SET_R6 >> 8)
            a.emit(0x68, 0xAA, 0x60)                          # PLA; TAX; RTS
        else:
            a.emit(0xA9, 0x04, 0x4C, F13_SET_R6 & 0xFF, F13_SET_R6 >> 8)
        return a.finish()

    # CallF13BarbaDraw (calls $8000; preserves X for $AEC8 JSR $AAE6)
    place_t(F13_BARBA_DRAW, bank_call(0x8000, save_x=True), F13_BARBA_BREATH)
    # CallF13BarbaBreath (calls $DBD8 first, then $8003; preserves X for $AEBF)
    place_t(F13_BARBA_BREATH, bank_call(0x8003, pre_call=(0x20, 0xD8, 0xDB), save_x=True), F13_BARBA_RESET)
    # CallF13BarbaReset (calls $8006)
    place_t(F13_BARBA_RESET, bank_call(0x8006), F13_ATK_GATE)
    # F13AttackGate (Barba -> A=0; Laura/Debbie -> $B271)
    a = Asm6502(F13_ATK_GATE)
    a.emit(0x20, 0x4B, 0xBB)                                  # JSR IsFemaleHuman
    a.emit(0xB0, 0x03)                                        # BCS human
    a.emit(0x4C, 0x80, 0xB2)                                  # JMP $B280 (return A=0)
    a.emit(0x4C, 0x71, 0xB2)                                  # JMP $B271 (vanilla check)
    place_t(F13_ATK_GATE, a.finish(), F13_SAVE_OAM_PTR)
    # Keep $05BF in [$30, $E0] and $056D >= $30 (protects Sprite 0 + HUD from $A84B)
    a = Asm6502(F13_SAVE_OAM_PTR)
    a.emit(0xAD, 0x6F, 0x05, 0xC9, 0x30, 0xB0, 0x02, 0xA9, 0x30)
    a.emit(0xC9, 0xE1, 0x90, 0x02, 0xA9, 0xE0, 0x8D, 0xBF, 0x05)
    a.emit(0xAD, 0x6D, 0x05, 0xC9, 0x30, 0xB0, 0x05, 0xA9, 0x30, 0x8D, 0x6D, 0x05)
    a.emit(0x60)
    place_t(F13_SAVE_OAM_PTR, a.finish(), F13_SFX_CALL)
    # Call $8F00+A in F13 bank 4 ($8000-$9FFF), then restore bank 1
    a = Asm6502(F13_SFX_CALL)
    a.emit(0x8D, (F13_SFX_CALL + 9) & 0xFF, (F13_SFX_CALL + 9) >> 8)  # STA low byte of JSR $8Fxx
    a.emit(0xA9, 0x04, 0x20, F13_SET_R6 & 0xFF, F13_SET_R6 >> 8)
    a.emit(0x20, 0x6C, 0x8F)                                  # offset +8..+10 (low byte at +9)
    a.emit(0xA9, 0x01, 0x4C, F13_SET_R6 & 0xFF, F13_SET_R6 >> 8)
    place_t(F13_SFX_CALL, a.finish(), F13_SET_R6)
    # SetR6: A = bank offset (1 or 4). Updates F13_MMC3_SEL, F13_CUR_R6, and MMC3 R6. Clobbers X.
    a = Asm6502(F13_SET_R6)
    a.emit(0x18, 0x6D, 0xFF, 0x7B)                            # CLC; ADC $7BFF (F13_PRG_BASE)
    a.emit(0xA2, 0x06)                                        # LDX #$06
    a.emit(0x8E, F13_MMC3_SEL & 0xFF, F13_MMC3_SEL >> 8)      # STX F13_MMC3_SEL
    a.emit(0x8E, 0x00, 0x80)                                  # STX $8000
    a.emit(0x8D, F13_CUR_R6 & 0xFF, F13_CUR_R6 >> 8)          # STA F13_CUR_R6
    a.emit(0x8D, 0x01, 0x80)                                  # STA $8001
    a.emit(0x60)                                              # RTS
    place_t(F13_SET_R6, a.finish(), F13_NMI_WRAP)
    # F13NmiWrap: safely switch R6 to F13 bank 4 for $80B7 NMI, then restore R6 and $8000 select
    a = Asm6502(F13_NMI_WRAP)
    a.emit(0x48)                                              # PHA
    a.emit(0xAD, F13_MMC3_SEL & 0xFF, F13_MMC3_SEL >> 8, 0x48)  # LDA F13_MMC3_SEL; PHA
    a.emit(0xAD, F13_CUR_R6 & 0xFF, F13_CUR_R6 >> 8, 0x48)    # LDA F13_CUR_R6; PHA
    a.emit(0xA9, 0x06)
    a.emit(0x8D, F13_MMC3_SEL & 0xFF, F13_MMC3_SEL >> 8, 0x8D, 0x00, 0x80)
    a.emit(0xA9, 0x04, 0x18, 0x6D, 0xFF, 0x7B)                # LDA #$04; CLC; ADC $7BFF
    a.emit(0x8D, F13_CUR_R6 & 0xFF, F13_CUR_R6 >> 8, 0x8D, 0x01, 0x80)
    a.lda_hi('nmi_ret'); a.emit(0x48)
    a.lda_lo('nmi_ret'); a.emit(0x48)
    a.emit(0x08)                                              # PHP
    a.emit(0x4C, 0xB7, 0x80)                                  # JMP $80B7 (RTIs to nmi_ret)
    a.label('nmi_ret')
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80)
    a.emit(0x68, 0x8D, F13_CUR_R6 & 0xFF, F13_CUR_R6 >> 8, 0x8D, 0x01, 0x80)
    a.emit(0x68, 0x8D, F13_MMC3_SEL & 0xFF, F13_MMC3_SEL >> 8, 0x8D, 0x00, 0x80)
    a.emit(0x68, 0x40)                                        # PLA; RTI
    place_t(F13_NMI_WRAP, a.finish(), F13_WR_SEL)
    # F13WrSel: STY F13_MMC3_SEL; STY $8000; RTS (preserves A, X, Y, P)
    a = Asm6502(F13_WR_SEL)
    a.emit(0x8C, F13_MMC3_SEL & 0xFF, F13_MMC3_SEL >> 8)
    a.emit(0x8C, 0x00, 0x80, 0x60)
    place_t(F13_WR_SEL, a.finish(), F13_MMC3_SEL)
    return bytes(out)


def make_reloc_e5b4() -> bytes:
    """Relocated 19-byte version of F13's $E5B4 wait loop (frees $E5B7-$E5C3 in fixed bank)."""
    a = Asm6502(F13_RELOC_E5B4)
    a.label('loop')
    a.emit(0x20, 0xEA, 0x81)                                  # JSR $81EA
    a.emit(0xAD, 0x74, 0x05, 0x29, 0x08)                      # LDA $0574; AND #$08
    a.branch(0xD0, 'exit_e5c4')                               # BNE exit_e5c4
    a.emit(0x88)                                              # DEY
    a.branch(0xD0, 'loop')                                    # BNE loop
    a.emit(0xA9, 0xFF, 0x60)                                  # LDA #$FF; RTS
    a.label('exit_e5c4')
    a.emit(0x4C, 0xC4, 0xE5)                                  # JMP $E5C4
    return a.finish()


def make_f13_wram_code(
    restore_addr: int,
    *,
    reward_addr: int = 0x63B1,
    reward_magic: int = 0x01,
) -> bytes:
    """Assemble the 1024-byte ($7800-$7BFF) WRAM bank 3 helper for Friday the 13th."""
    out = bytearray(b'\xFF' * 0x400)

    def place(addr: int, data: bytes, limit: int) -> None:
        off = addr - 0x7800
        assert off + len(data) <= limit - 0x7800, f'Overflow at ${addr:04X}: {off + len(data)} > {limit - 0x7800}'
        out[off : off + len(data)] = data

    # 1. F13ChrSwitch ($7800): Y = 8KB CHR bank (0..3). Preserves A, X, Y, P.
    a = Asm6502(F13_CHR_SWITCH)
    a.emit(0x08, 0x78, 0x48, 0x8A, 0x48, 0x98, 0x48)          # PHP; SEI; PHA; TXA; PHA; TYA; PHA
    a.emit(0x98, 0x0A, 0x0A, 0x0A, 0x09, 0x80, 0xAA)          # TYA; ASL*3; ORA #$80; TAX
    a.emit(0xC0, 0x02)                                        # CPY #$02
    a.branch(0xB0, 'norm_r0')
    a.emit(0xB9, 0x0B, 0x7C)                                  # LDA $7C0B,Y (BARBA_R0_0/1)
    a.branch(0xD0, 'set_r0')
    a.label('norm_r0')
    a.emit(0x8A)                                              # TXA
    a.label('set_r0')
    a.emit(0xA0, 0x00, 0x20, F13_WR_SEL & 0xFF, F13_WR_SEL >> 8, 0x8D, 0x01, 0x80)  # R0 = A
    a.emit(0xE8, 0xE8, 0xC8)                                  # INX; INX; INY (Y=1)
    a.emit(0x20, F13_WR_SEL & 0xFF, F13_WR_SEL >> 8)          # $8000 = 1 (R1)
    a.emit(0xE0, 0x92)                                        # CPX #$92 (indoors?)
    a.branch(0xD0, 'r1_norm')
    a.emit(0xAD, 0x07, 0x05, 0x38, 0xE9, 0x03, 0xC9, 0x02)  # Laura (3) or Debbie (4)?
    a.branch(0x90, 'r1_norm')
    a.emit(0xA9, 0xB2)                                        # A = $B2 (2KB idx 25 Barba indoor R1)
    a.branch(0xD0, 'r1_set')                                  # always taken
    a.label('r1_norm')
    a.emit(0x8A)                                              # TXA
    a.label('r1_set')
    a.emit(0x8D, 0x01, 0x80)                                  # R1 = A
    a.emit(0xE8, 0xE8, 0xC8)                                  # INX; INX; INY (Y=2)
    a.label('chr_loop')
    a.emit(0x20, F13_WR_SEL & 0xFF, F13_WR_SEL >> 8, 0x8E, 0x01, 0x80)              # STY $8000; STX $8001
    a.emit(0xE8, 0xC8, 0xC0, 0x06)                            # INX; INY; CPY #6
    a.branch(0x90, 'chr_loop')                                # BCC @chr_loop
    a.emit(0x68, 0xA8, 0x68, 0xAA, 0x68, 0x28, 0x60)          # PLA; TAY; PLA; TAX; PLA; PLP; RTS
    place(F13_CHR_SWITCH, a.finish(), F13_NMI_HOOK)

    # 2. F13NmiHook ($7840): 60-frame guard, then Select+Start -> F13Return
    a = Asm6502(F13_NMI_HOOK)
    a.emit(0x48, 0xAD, 0xFF, 0x7F, 0xC9, 0x3C)                # PHA; LDA $7FFF; CMP #$3C
    a.branch(0xB0, 'check_pad')
    a.emit(0xEE, 0xFF, 0x7F)                                  # INC $7FFF
    a.branch(0xD0, 'normal_nmi')
    a.label('check_pad')
    a.emit(0xA5, 0x2D, 0x29, 0x0C, 0xC9, 0x0C)                # LDA $2D; AND #$0C; CMP #$0C
    a.branch(0xF0, 'do_return')
    a.label('normal_nmi')
    a.emit(0x68, 0x4C, F13_NMI_WRAP & 0xFF, F13_NMI_WRAP >> 8)  # PLA; JMP F13NmiWrap
    a.label('do_return')
    a.emit(0x68, 0x4C, F13_CANCEL_HOOK & 0xFF, F13_CANCEL_HOOK >> 8)  # PLA; JMP F13_CANCEL_HOOK
    place(F13_NMI_HOOK, a.finish(), F13_WIPE_IN)

    # 3. F13WipeIn ($7860): 30-frame top-down wave reveal after $E486 flushes F13 palette/NT
    a = Asm6502(F13_WIPE_IN)
    a.emit(0xAD, 0xFE, 0x7F)                                  # LDA $7FFE
    a.branch(0xF0, 'w_start')                                 # BEQ w_start
    a.emit(0x4C, 0xBA, 0x82)                                  # JMP $82BA (subsequent calls)
    a.label('w_start')
    a.emit(0xEE, 0xFE, 0x7F)                                  # INC $7FFE
    a.emit(0x78)                                              # SEI
    a.emit(0xA5, 0x29, 0x29, 0x7F, 0x8D, 0x00, 0x20)          # $2000 = $29 & $7F (disable NMI)
    a.emit(0xA9, 29, 0x85, 0x08)                              # $08 = frame = 29
    a.label('w_frame')
    a.emit(0xA9, 30, 0x38, 0xE5, 0x08, 0x85, 0x09)            # $09 = reveal_band = 30 - frame
    a.emit(0x2C, 0x02, 0x20)
    a.label('w_vb')
    a.emit(0x2C, 0x02, 0x20)
    a.branch(0x10, 'w_vb')
    a.emit(0xA5, 0x29, 0x29, 0x7C, 0x8D, 0x00, 0x20)          # $2000 = $29 & $7C
    a.emit(0x2C, 0x02, 0x20, 0xA9, 0x00, 0x8D, 0x06, 0x20, 0x8D, 0x06, 0x20)
    a.emit(0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)                # $2005 = 0, 0
    a.emit(0xA9, 0x1E, 0x8D, 0x01, 0x20)                      # $2001 = $1E
    a.emit(0xA2, 21)
    a.label('w_pre_sl')
    a.emit(0xA0, 21)
    a.label('w_pre_in')
    a.emit(0x88)
    a.branch(0xD0, 'w_pre_in')
    a.emit(0xEA, 0xCA)
    a.branch(0xD0, 'w_pre_sl')
    a.emit(0xA9, 0x00, 0x85, 0x0A)                            # $0A = band = 0
    a.label('w_band')
    a.emit(0xA5, 0x0A, 0xC5, 0x09)
    a.branch(0x90, 'w_vis')
    a.emit(0xA9, 0x00, 0x8D, 0x01, 0x20)                      # $2001 = 0
    a.emit(0xA9, 0x3F, 0x8D, 0x06, 0x20, 0xA9, 0x0F, 0x8D, 0x06, 0x20)  # $2006 = $3F0F (black)
    a.abs_ref(0x4C, 'w_next')
    a.label('w_vis')
    a.emit(0xA5, 0x0A, 0x18, 0x65, 0x08, 0x29, 0x0F, 0xAA)    # X = (band + frame) & 15
    a.abs_ref(0xBD, 'w_wave')
    a.emit(0xA6, 0x08, 0xE0, 8)
    a.branch(0x90, 'w_half')
    a.emit(0xE0, 16)
    a.branch(0x90, 'w_sc_ok')
    a.emit(0xE0, 24)
    a.branch(0x90, 'w_2x')
    a.emit(0x0A)
    a.label('w_2x')
    a.emit(0x0A)
    a.abs_ref(0x4C, 'w_sc_ok')
    a.label('w_half')
    a.emit(0xC9, 0x80, 0x6A)
    a.label('w_sc_ok')
    a.emit(0x8D, 0x05, 0x20, 0xA9, 0x00, 0x8D, 0x05, 0x20)    # $2005 = shear, 0
    a.emit(0xA0, 158)
    a.label('w_wait')
    a.emit(0x88)
    a.branch(0xD0, 'w_wait')
    a.emit(0xE6, 0x0A, 0xA5, 0x0A, 0xC9, 30)
    a.branch(0xB0, 'w_next')
    a.abs_ref(0x4C, 'w_band')
    a.label('w_next')
    a.emit(0xC6, 0x08)
    a.branch(0x10, 'w_frame_jmp')
    a.abs_ref(0x4C, 'w_done')
    a.label('w_frame_jmp')
    a.abs_ref(0x4C, 'w_frame')
    a.label('w_done')
    a.emit(0x2C, 0x02, 0x20)
    a.label('w_vb2')
    a.emit(0x2C, 0x02, 0x20)
    a.branch(0x10, 'w_vb2')
    a.emit(0xA9, 0x00, 0x8D, 0x06, 0x20, 0x8D, 0x06, 0x20, 0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)
    a.emit(0x68, 0x85, 0x00, 0x68, 0x85, 0x01, 0x68)          # pop return addr -> $00/$01; discard $82A6's saved $2A
    a.emit(0xA9, 0x1E, 0x85, 0x2A)                            # $2A = $1E
    a.emit(0xA5, 0x29, 0x09, 0x80, 0x85, 0x29, 0x8D, 0x00, 0x20)  # enable NMI
    a.emit(0x58, 0xA5, 0x01, 0x48, 0xA5, 0x00, 0x48, 0x60)    # CLI; RTS to $E48C
    a.label('w_wave')
    a.emit(0x00, 0x02, 0x04, 0x05, 0x06, 0x05, 0x04, 0x02, 0x00, 0xFE, 0xFC, 0xFB, 0xFA, 0xFB, 0xFC, 0xFE)
    place(F13_WIPE_IN, a.finish(), F13_RETURN)

    # 4. F13Return ($7920): melt out + copy return trampoline to $0300 + jump to BarbaWaldoRestore6
    a = Asm6502(F13_RETURN)
    a.emit(0x78)                                              # SEI
    a.emit(0xA5, 0x29, 0x29, 0x7F, 0x85, 0x29, 0x8D, 0x00, 0x20)  # disable NMI
    a.emit(0xA9, 0x00, 0x8D, 0x15, 0x40, 0x8D, 0x11, 0x40, 0x8D, 0x00, 0xE0)    # $4015=0; $4011=0; $E000=0
    a.emit(0x48, 0xA9, 0x40, 0x8D, 0x17, 0x40, 0x68)          # $4017=$40; A=0
    a.emit(0x85, 0x08)                                        # $08 = frame = 0
    a.label('m_frame')
    a.emit(0xA9, 30, 0x38, 0xE5, 0x08, 0x85, 0x09)            # $09 = 30 - frame
    a.emit(0x2C, 0x02, 0x20)
    a.label('m_vb')
    a.emit(0x2C, 0x02, 0x20)
    a.branch(0x10, 'm_vb')
    a.emit(0xA5, 0x29, 0x29, 0x7C, 0x8D, 0x00, 0x20)          # $2000 = $29 & $7C
    a.emit(0x2C, 0x02, 0x20, 0xA9, 0x00, 0x8D, 0x06, 0x20, 0x8D, 0x06, 0x20)
    # Scroll = (0,0) if $38 != 0 else ($44, $46)
    a.emit(0xA5, 0x38)
    a.branch(0xF0, 'm_top_44')
    a.emit(0xA9, 0x00, 0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)
    a.emit(0xA0, 0x03, 0x20, F13_CHR_SWITCH & 0xFF, F13_CHR_SWITCH >> 8)
    a.branch(0xD0, 'm_top_done')
    a.label('m_top_44')
    a.emit(0xA5, 0x44, 0x8D, 0x05, 0x20, 0xA5, 0x46, 0x8D, 0x05, 0x20)
    a.label('m_top_done')
    a.emit(0xA5, 0x2A, 0x09, 0x18, 0x8D, 0x01, 0x20)          # $2001 = $2A | $18
    a.emit(0xA2, 21)
    a.label('m_pre_sl')
    a.emit(0xA0, 21)
    a.label('m_pre_in')
    a.emit(0x88)
    a.branch(0xD0, 'm_pre_in')
    a.emit(0xEA, 0xCA)
    a.branch(0xD0, 'm_pre_sl')
    a.emit(0xA9, 0x00, 0x85, 0x0A)                            # $0A = band = 0
    a.label('m_band')
    a.emit(0xA5, 0x0A, 0xC5, 0x09)
    a.branch(0x90, 'm_vis')
    a.emit(0xA9, 0x00, 0x8D, 0x01, 0x20)
    a.emit(0xA9, 0x3F, 0x8D, 0x06, 0x20, 0xA9, 0x0F, 0x8D, 0x06, 0x20)
    a.abs_ref(0x4C, 'm_next')
    a.label('m_vis')
    a.emit(0xA5, 0x38)
    a.branch(0xF0, 'm_use_44')
    a.emit(0xA5, 0x0A, 0xC9, 4)
    a.branch(0xD0, 'm_not_b4')
    a.emit(0xA4, 0x37, 0x20, F13_CHR_SWITCH & 0xFF, F13_CHR_SWITCH >> 8)
    a.label('m_not_b4')
    a.emit(0xA5, 0x0A, 0xC9, 4)
    a.branch(0x90, 'm_hud_base')
    a.emit(0xA5, 0x48, 0x85, 0x0C, 0xA5, 0x49)
    a.branch(0xD0, 'm_nt_set')
    a.emit(0xF0, 0x0C)
    a.label('m_hud_base')
    a.emit(0xA9, 0x00, 0x85, 0x0C)
    a.branch(0xF0, 'm_nt_set')
    a.label('m_use_44')
    a.emit(0xA5, 0x44, 0x85, 0x0C, 0xA5, 0x45)
    a.label('m_nt_set')
    a.emit(0x29, 0x01, 0x85, 0x0B)                            # $0B = NT bit 0
    a.emit(0xA5, 0x29, 0x29, 0x7C, 0x05, 0x0B, 0x85, 0x0B)
    a.emit(0xA5, 0x0A, 0x18, 0x65, 0x08, 0x29, 0x0F, 0xAA)
    a.emit(0xBD, (F13_WIPE_IN + 0xB8) & 0xFF, 0x78)           # placeholder: use local wave table
    # Wait: fix up wave table reference cleanly!
    a.buf[-2:] = []
    a.abs_ref(0xBD, 'm_wave')
    a.emit(0xA6, 0x08, 0xE0, 8)
    a.branch(0x90, 'm_half')
    a.emit(0xE0, 16)
    a.branch(0x90, 'm_sc_ok')
    a.emit(0xE0, 24)
    a.branch(0x90, 'm_2x')
    a.emit(0x0A)
    a.label('m_2x')
    a.emit(0x0A)
    a.abs_ref(0x4C, 'm_sc_ok')
    a.label('m_half')
    a.emit(0xC9, 0x80, 0x6A)
    a.label('m_sc_ok')
    a.emit(0xAA)
    a.branch(0x30, 'm_neg')
    a.emit(0x18, 0x65, 0x0C)
    a.branch(0x90, 'm_wr')
    a.emit(0xAA, 0xA5, 0x0B, 0x49, 0x01, 0x85, 0x0B, 0x8A)
    a.abs_ref(0x4C, 'm_wr')
    a.label('m_neg')
    a.emit(0x18, 0x65, 0x0C)
    a.branch(0xB0, 'm_wr')
    a.emit(0xAA, 0xA5, 0x0B, 0x49, 0x01, 0x85, 0x0B, 0x8A)
    a.label('m_wr')
    a.emit(0xA6, 0x0B, 0x8E, 0x00, 0x20, 0x8D, 0x05, 0x20, 0xA9, 0x00, 0x8D, 0x05, 0x20)
    a.emit(0xA0, 154)
    a.label('m_wait')
    a.emit(0x88)
    a.branch(0xD0, 'm_wait')
    a.emit(0xE6, 0x0A, 0xA5, 0x0A, 0xC9, 30)
    a.branch(0xB0, 'm_next')
    a.abs_ref(0x4C, 'm_band')
    a.label('m_next')
    a.emit(0xE6, 0x08, 0xA5, 0x08, 0xC9, 30)
    a.branch(0xB0, 'm_done')
    a.abs_ref(0x4C, 'm_frame')
    a.label('m_done')
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20)    # $2000=0; $2001=0
    a.emit(0xAC, F13_WIN_FLAG & 0xFF, F13_WIN_FLAG >> 8)      # LDY F13_WIN_FLAG
    a.emit(0xA9, 0x00, 0x8D, F13_WIN_FLAG & 0xFF, F13_WIN_FLAG >> 8)
    a.emit(0xA2, 56)                                          # copy 57B return trampoline from F13_EXIT_TRAMP ($7E98) to $0300
    a.label('m_cp')
    a.emit(0xBD, F13_EXIT_TRAMP & 0xFF, F13_EXIT_TRAMP >> 8)
    a.emit(0x9D, 0x00, 0x03, 0xCA)
    a.branch(0x10, 'm_cp')
    a.emit(0x4C, 0x00, 0x03)                                  # JMP $0300
    a.label('m_wave')
    a.emit(0x00, 0x02, 0x04, 0x05, 0x06, 0x05, 0x04, 0x02, 0x00, 0xFE, 0xFC, 0xFB, 0xFA, 0xFB, 0xFC, 0xFE)
    place(F13_RETURN, a.finish(), F13_TITLE_ART)

    # 4b. F13_TITLE_ART ($7ACC): switch R6->1, JSR $800C (F13TitleDraw), restore R6->4
    a = Asm6502(F13_TITLE_ART)
    a.emit(0xA9, 0x01, 0x20, F13_SET_R6 & 0xFF, F13_SET_R6 >> 8)
    a.emit(0x20, 0x0C, 0x80)
    a.emit(0xA9, 0x04, 0x4C, F13_SET_R6 & 0xFF, F13_SET_R6 >> 8)
    place(F13_TITLE_ART, a.finish(), F13_BOOT)

    # 5. F13Boot ($7AE0): map F13 PRG banks 28/29, CHR bank 0, Vertical mirroring, clear $7FFF, JMP $8000
    a = Asm6502(F13_BOOT)
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0xA0)                      # Vertical mirroring
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 28, 0x8D, 0x01, 0x80)    # R6 = 28 ($8000)
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 29, 0x8D, 0x01, 0x80)    # R7 = 29 ($A000)
    a.emit(0xA9, 24, 0x8D, 0xFF, 0x7B)                        # $7BFF = 24 (PRG base)
    a.emit(0xA9, 28, 0x8D, F13_CUR_R6 & 0xFF, F13_CUR_R6 >> 8)  # F13_CUR_R6 = 28
    a.emit(0xA9, 0x80, 0x8D, 0xFE, 0x7B)                      # $7BFE = $80 (CHR base)
    a.emit(0x20, F13_BARBA_RESET & 0xFF, F13_BARBA_RESET >> 8)
    a.emit(0xA0, 0x00, 0x20, F13_CHR_SWITCH & 0xFF, F13_CHR_SWITCH >> 8)  # CHR bank 0
    a.emit(0xA9, 0x00, 0x8D, 0xFF, 0x7F, 0x8D, 0xFE, 0x7F)    # Clear $7FFF and $7FFE
    a.emit(0x4C, 0x00, 0x80)                                  # JMP $8000 (F13 Reset)
    place(F13_BOOT, a.finish(), F13_RELOC_E5B4)

    # 5b. F13SeedRng ($7950): seed $31 from Barba's $7FF0 if non-zero, then TXS and JMP $8035
    a = Asm6502(F13_SEED_RNG)
    a.emit(0xAD, 0xF0, 0x7F)                                  # LDA $7FF0
    a.branch(0xF0, 'use_x')                                   # BEQ use_x
    a.emit(0xAA)                                              # TAX
    a.label('use_x')
    a.emit(0x86, 0x31)                                        # STX $31
    a.emit(0xA2, 0xFF, 0x9A)                                  # LDX #$FF; TXS
    a.emit(0x4C, 0x35, 0x80)                                  # JMP $8035
    place(F13_SEED_RNG, a.finish(), F13_RETURN)

    # 6. Relocated $E5B4 ($7B20) + Barba trampolines ($7B38-$7BFD)
    place(F13_RELOC_E5B4, make_reloc_e5b4(), F13_BARBA_DRAW)
    place(F13_BARBA_DRAW, make_barba_trampolines(), 0x7BFE)

    return bytes(out)


def make_f13_win_wram_block(
    restore_addr: int,
    *,
    reward_addr: int = 0x63B1,
    reward_magic: int = 0x01,
    build_number: int | None = None,
) -> bytes:
    """Assemble 128-byte $7E80-$7EFF block holding F13_WIN_HOOK ($7E80), F13_CANCEL_HOOK ($7E88), F13_EXIT_TRAMP ($7E98), and F13_TITLE_BUILD ($7ED4)."""
    out = bytearray(b'\xFF' * 0x80)
    a = Asm6502(F13_WIN_HOOK)
    a.emit(0xA9, reward_magic, 0x8D, F13_WIN_FLAG & 0xFF, F13_WIN_FLAG >> 8)
    a.emit(0x4C, F13_RETURN & 0xFF, F13_RETURN >> 8)
    win_bytes = a.finish()
    assert len(win_bytes) <= F13_CANCEL_HOOK - F13_WIN_HOOK
    out[0 : len(win_bytes)] = win_bytes

    ac = Asm6502(F13_CANCEL_HOOK)
    ac.emit(0xA9, 0x00, 0x8D, F13_WIN_FLAG & 0xFF, F13_WIN_FLAG >> 8)
    ac.emit(0x4C, F13_RETURN & 0xFF, F13_RETURN >> 8)
    cancel_bytes = ac.finish()
    assert len(cancel_bytes) <= F13_EXIT_TRAMP - F13_CANCEL_HOOK
    cancel_off = F13_CANCEL_HOOK - F13_WIN_HOOK
    out[cancel_off : cancel_off + len(cancel_bytes)] = cancel_bytes

    tramp = (
        bytes.fromhex(
            'a9 80 8d 01 a0 '                                   # unlock $5FF0-$5FF3
            'a9 01 8d f0 5f '                                   # $5FF0 = 1
            'a9 00 8d f1 5f 8d f2 5f '                          # $5FF1 = 0, $5FF2 = 0
            'a9 06 8d 00 80 a9 0c 8d 01 80 '                    # R6 = $0C
            'a9 07 8d 00 80 a9 0d 8d 01 80 '                    # R7 = $0D
            'a9 a0 8d 01 a0 '                                   # WRAM bank 0 + lock
            '98 f0 08 '                                         # TYA; BEQ +8
            '8d'
        )
        + reward_addr.to_bytes(2, 'little')
        + bytes.fromhex('a9 02 8d 04 68')                       # LDA #2; STA $6804 (RA_LAST_WIN_GAME)
        + b'\x4c'
        + restore_addr.to_bytes(2, 'little')
    )
    assert len(tramp) == 57
    off = F13_EXIT_TRAMP - F13_WIN_HOOK
    out[off : off + len(tramp)] = tramp

    tb_off = 0x7ED4 - F13_WIN_HOOK
    tb = Asm6502(0x7ED4)
    tb.emit(0x20, 0x9E, 0xE3)                                   # JSR $E39E
    if build_number is not None:
        tb.emit(0x2C, 0x02, 0x20)                               # BIT $2002
        tb.emit(0xA9, 0x20, 0x8D, 0x06, 0x20)                   # PPU $203A
        tb.emit(0xA9, 0x3A, 0x8D, 0x06, 0x20)
        for ch in f'B{build_number}':
            tid = 0x0B if ch == 'B' else int(ch)
            tb.emit(0xA9, tid, 0x8D, 0x07, 0x20)
    tb.emit(0x4C, F13_TITLE_ART & 0xFF, F13_TITLE_ART >> 8)     # JMP F13_TITLE_ART
    tb_bytes = tb.finish()
    assert tb_off + len(tb_bytes) <= len(out), f'F13_TITLE_BUILD overflow: {tb_off + len(tb_bytes)}'
    out[tb_off : tb_off + len(tb_bytes)] = tb_bytes
    return bytes(out)


def make_f13_bank0(
    restore_addr: int,
    *,
    reward_addr: int = 0x63B1,
    reward_magic: int = 0x01,
    build_number: int | None = None,
) -> bytes:
    """Build 8KB bank 0 for F13: copies $8100-$84FF -> $7800-$7BFF and $8500-$857F -> $7E80-$7EFF, then jumps to F13Boot."""
    bank0 = bytearray(b'\xFF' * 8192)
    a = Asm6502(0x8000)
    a.emit(0xA9, 0xA3, 0x8D, 0x01, 0xA0)                      # WRAM bank 3 + lock $5FF0-$5FF3
    a.emit(0xA9, 0x00, 0x85, 0x00, 0x85, 0x02)                # $00=0, $02=0
    a.emit(0xA9, 0x81, 0x85, 0x01)                            # $01=$81
    a.emit(0xA9, 0x78, 0x85, 0x03)                            # $03=$78
    a.emit(0xA2, 0x04, 0xA0, 0x00)                            # 4 pages
    a.label('cp')
    a.emit(0xB1, 0x00, 0x91, 0x02, 0xC8)
    a.branch(0xD0, 'cp')
    a.emit(0xE6, 0x01, 0xE6, 0x03, 0xCA)
    a.branch(0xD0, 'cp')
    a.emit(0xA2, 0x7F)
    a.label('cp_win')
    a.emit(0xBD, 0x00, 0x85, 0x9D, F13_WIN_HOOK & 0xFF, F13_WIN_HOOK >> 8, 0xCA)
    a.branch(0x10, 'cp_win')
    a.emit(0xA9, 0x00, 0x8D, F13_WIN_FLAG & 0xFF, F13_WIN_FLAG >> 8)
    a.emit(0x4C, F13_BOOT & 0xFF, F13_BOOT >> 8)              # JMP F13Boot ($7AE0)
    loader = a.finish()
    assert len(loader) <= 0x100
    bank0[0 : len(loader)] = loader
    bank0[0x100 : 0x500] = make_f13_wram_code(restore_addr, reward_addr=reward_addr, reward_magic=reward_magic)
    bank0[0x500 : 0x580] = make_f13_win_wram_block(
        restore_addr,
        reward_addr=reward_addr,
        reward_magic=reward_magic,
        build_number=build_number,
    )
    return bytes(bank0)


def patch_f13(f13: bytes) -> tuple[bytes, bytes, bytes]:
    """Verify and patch Friday the 13th PRG (MMC3 64KB) and return (prg_extra24k, prg32k, chr_bytes)."""
    assert f13[:4] == b'NES\x1a' and f13[4] == 4 and f13[5] in (4, 8)
    prg_extra = f13[16 + 8192 : 16 + 32768]
    prg = bytearray(f13[16 + 32768 : 16 + 65536])
    chr_len = f13[5] * 8192
    chr_data = f13[16 + 65536 : 16 + 65536 + chr_len]

    def patch(addr: int, new: bytes, expected: bytes) -> None:
        off = addr - 0x8000
        assert bytes(prg[off : off + len(expected)]) == expected, f'Unexpected F13 bytes at ${addr:04X}'
        prg[off : off + len(new)] = new

    # 1. Verify CHR bankswitch ($81A6) already jumps to F13ChrSwitch ($7800)
    patch(0x81A6, bytes([0x4C, F13_CHR_SWITCH & 0xFF, F13_CHR_SWITCH >> 8]),
          bytes([0x4C, F13_CHR_SWITCH & 0xFF, F13_CHR_SWITCH >> 8]))
    # 2. NMI vector ($FFFA) -> F13NmiHook ($7848)
    patch(0xFFFA, bytes([F13_NMI_HOOK & 0xFF, F13_NMI_HOOK >> 8]), bytes([F13_NMI_WRAP & 0xFF, F13_NMI_WRAP >> 8]))
    # 3. Title screen: keep $2A=0 at $8D22, wipe-in at $E489 (after $E486 flushes F13 palette/NT)
    patch(0x8D22, bytes.fromhex('68 ea ea'), bytes.fromhex('20 ba 82'))
    patch(0xE489, bytes([0x20, F13_WIPE_IN & 0xFF, F13_WIPE_IN >> 8]), bytes.fromhex('20 ba 82'))
    if bytes(prg[0x64F6 : 0x64F9]) == bytes.fromhex('20 00 79'):
        patch(0xE4F6, bytes([0x20, 0xD4, 0x7E]), bytes.fromhex('20 00 79'))
    # 4. Beat Day 3 ($8E4A) -> JMP F13_WIN_HOOK ($7E80)
    patch(0x8E4A, bytes([0x4C, F13_WIN_HOOK & 0xFF, F13_WIN_HOOK >> 8]), bytes.fromhex('4c f0 8c'))
    # 5. Boot RNG seed ($8030) -> JMP F13SeedRng ($7950)
    patch(0x8030, bytes([0x4C, F13_SEED_RNG & 0xFF, F13_SEED_RNG >> 8, 0xEA, 0xEA]),
          bytes.fromhex('86 31 a2 ff 9a'))

    return prg_extra, bytes(prg), chr_data
