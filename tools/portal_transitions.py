"""Shared 6502 portal transition, APU mute, and return-trampoline builders."""
from __future__ import annotations

from typing import Callable

from asm6502 import Asm6502


RA_LAST_WIN_GAME = 0x6804

WAVE_TABLE: tuple[int, ...] = (
    0x00, 0x02, 0x04, 0x05, 0x06, 0x05, 0x04, 0x02,
    0x00, 0xFE, 0xFC, 0xFB, 0xFA, 0xFB, 0xFC, 0xFE,
)


class TransitionAsm(Asm6502):
    """Asm6502 extended with mnemonic helpers that auto-select ZP vs abs."""

    def _mem(self, zp_op: int, abs_op: int, addr: int) -> None:
        if 0 <= addr < 0x100:
            self.emit(zp_op, addr)
        else:
            self.emit(abs_op, addr & 0xFF, (addr >> 8) & 0xFF)

    def lda_imm(self, val: int) -> None:
        self.emit(0xA9, val & 0xFF)

    def ldx_imm(self, val: int) -> None:
        self.emit(0xA2, val & 0xFF)

    def ldy_imm(self, val: int) -> None:
        self.emit(0xA0, val & 0xFF)

    def lda(self, addr: int) -> None:
        self._mem(0xA5, 0xAD, addr)

    def ldx(self, addr: int) -> None:
        self._mem(0xA6, 0xAE, addr)

    def ldy(self, addr: int) -> None:
        self._mem(0xA4, 0xAC, addr)

    def sta(self, addr: int) -> None:
        self._mem(0x85, 0x8D, addr)

    def stx(self, addr: int) -> None:
        self._mem(0x86, 0x8E, addr)

    def sty(self, addr: int) -> None:
        self._mem(0x84, 0x8C, addr)

    def inc(self, addr: int) -> None:
        self._mem(0xE6, 0xEE, addr)

    def dec(self, addr: int) -> None:
        self._mem(0xC6, 0xCE, addr)

    def adc(self, addr: int) -> None:
        self._mem(0x65, 0x6D, addr)

    def sbc(self, addr: int) -> None:
        self._mem(0xE5, 0xED, addr)

    def cmp_m(self, addr: int) -> None:
        self._mem(0xC5, 0xCD, addr)

    def ora(self, addr: int) -> None:
        self._mem(0x05, 0x0D, addr)

    def eor_imm(self, val: int) -> None:
        self.emit(0x49, val & 0xFF)

    def and_imm(self, val: int) -> None:
        self.emit(0x29, val & 0xFF)

    def ora_imm(self, val: int) -> None:
        self.emit(0x09, val & 0xFF)

    def cmp_imm(self, val: int) -> None:
        self.emit(0xC9, val & 0xFF)

    def cpx_imm(self, val: int) -> None:
        self.emit(0xE0, val & 0xFF)

    def cpy_imm(self, val: int) -> None:
        self.emit(0xC0, val & 0xFF)

    def bit_abs(self, addr: int) -> None:
        self.emit(0x2C, addr & 0xFF, (addr >> 8) & 0xFF)

    def jsr_abs(self, addr: int) -> None:
        self.emit(0x20, addr & 0xFF, (addr >> 8) & 0xFF)

    def jmp_abs(self, addr: int) -> None:
        self.emit(0x4C, addr & 0xFF, (addr >> 8) & 0xFF)


def emit_clean_apu_mute(a: Asm6502, *, leave_a_zero: bool = True) -> None:
    """Mute all NES APU channels, DAC level, MMC3 IRQ, and frame counter IRQ."""
    t = TransitionAsm(0)
    t.buf = a.buf  # emit directly into caller buffer
    t.lda_imm(0x00)
    t.sta(0x4015)
    t.sta(0x4011)
    t.sta(0xE000)
    t.lda_imm(0x40)
    t.sta(0x4017)
    if leave_a_zero:
        t.lda_imm(0x00)


def build_return_helper(
    restore_addr: int,
    reward_addr: int,
    *,
    game_id: int | None = None,
    win_reg: str = 'x',
    check_magic: int | None = None,
    restore_r6: int = 0x0C,
    restore_r7: int = 0x0D,
    lock_wram: bool = True,
) -> bytes:
    """Assemble the relocatable $0300 return helper returning to Z2 Bank 6."""
    assert win_reg in ('x', 'y')
    a = TransitionAsm(0x0300)
    # Unlock FK23C $5FF0-$5FF3 (WRAM bank 0 until locked)
    a.lda_imm(0x80)
    a.sta(0xA001)
    a.lda_imm(0x01)
    a.sta(0x5FF0)
    a.lda_imm(0x00)
    a.sta(0x5FF1)
    a.sta(0x5FF2)
    # Restore Zelda II PRG windows R6=$0C, R7=$0D
    a.lda_imm(0x06)
    a.sta(0x8000)
    a.lda_imm(restore_r6)
    a.sta(0x8001)
    a.lda_imm(0x07)
    a.sta(0x8000)
    a.lda_imm(restore_r7)
    a.sta(0x8001)
    if lock_wram:
        a.lda_imm(0xA0)
        a.sta(0xA001)

    if check_magic is None:
        a.emit(0x8A if win_reg == 'x' else 0x98)  # TXA / TYA
        a.branch(0xF0, 'skip_win')                # BEQ skip_win
        a.sta(reward_addr)
    else:
        if win_reg == 'x':
            a.cpx_imm(check_magic)
        else:
            a.cpy_imm(check_magic)
        a.branch(0xD0, 'skip_win')                # BNE skip_win
        if win_reg == 'x':
            a.stx(reward_addr)
        else:
            a.sty(reward_addr)

    if game_id is not None:
        a.lda_imm(game_id)
        a.sta(RA_LAST_WIN_GAME)

    a.label('skip_win')
    a.jmp_abs(restore_addr)
    return a.finish()


def emit_wavy_transition(
    a: Asm6502,
    *,
    prefix: str,
    frame_addr: int,
    cut_addr: int,
    band_addr: int,
    dir_addr: int | None = None,
    direction: str = 'out',
    ppuctrl_addr: int | None = None,
    ppuctrl_mask: int = 0x7C,
    ppuctrl_or_addr: int | None = None,
    ppumask_addr: int | None = None,
    ppumask_const: int = 0x1E,
    scroll_x_addr: int | None = None,
    scroll_y_addr: int | None = None,
    scroll_nt_addr: int | None = None,
    scroll_hud_bands: int = 0,
    nt_tmp_addr: int | None = None,
    base_tmp_addr: int | None = None,
    vblank_hook: Callable[[Asm6502], None] | None = None,
    band_hook: Callable[[Asm6502, int], None] | None = None,
    wave_label: str | None = None,
    end_on_vblank: bool = False,
    emit_rts: bool = True,
) -> None:
    """Emit a 30-frame wavy horizontal wipe-in or melt-out routine (ending with RTS or fall-through)."""
    assert direction in ('in', 'out')
    if scroll_x_addr is not None:
        assert scroll_nt_addr is not None
        assert nt_tmp_addr is not None and base_tmp_addr is not None

    t = TransitionAsm(a.base)
    t.buf = a.buf
    t.labels = a.labels
    t.fixups = a.fixups

    def L(name: str) -> str:
        return f'{prefix}_{name}'

    w_lbl = wave_label or L('wave')

    if dir_addr is not None:
        # Entered with A = 0 for melt-out (0..29) or A != 0 for wipe-in (29..0)
        t.sta(dir_addr)
        t.branch(0xD0, L('init_in'))
        t.lda_imm(0x00)
        t.sta(frame_addr)
        t.branch(0xF0, L('frame'))
        t.label(L('init_in'))
        t.lda_imm(29)
        t.sta(frame_addr)
    elif direction == 'out':
        t.lda_imm(0x00)
        t.sta(frame_addr)
    else:
        t.lda_imm(29)
        t.sta(frame_addr)

    t.label(L('frame'))
    t.lda_imm(30)
    t.emit(0x38)  # SEC
    t.sbc(frame_addr)
    t.sta(cut_addr)

    t.bit_abs(0x2002)
    t.label(L('vb'))
    t.bit_abs(0x2002)
    t.branch(0x10, L('vb'))

    if ppuctrl_addr is not None:
        t.lda(ppuctrl_addr)
        t.and_imm(ppuctrl_mask)
        if ppuctrl_or_addr is not None:
            t.ora(ppuctrl_or_addr)
    else:
        t.lda_imm(0x00)
    t.sta(0x2000)

    t.bit_abs(0x2002)
    t.lda_imm(0x00)
    t.sta(0x2006)
    t.sta(0x2006)
    t.sta(0x2005)
    if scroll_y_addr is not None and scroll_hud_bands == 0:
        t.lda(scroll_y_addr)
    t.sta(0x2005)

    if ppumask_addr is not None:
        t.lda(ppumask_addr)
        t.ora_imm(0x18)
    else:
        t.lda_imm(ppumask_const)
    t.sta(0x2001)

    if vblank_hook is not None:
        vblank_hook(a)

    # Pre-scanline delay (~21 scanlines)
    t.ldx_imm(21)
    t.label(L('pre_sl'))
    t.ldy_imm(21)
    t.label(L('pre_in'))
    t.emit(0x88)  # DEY
    t.branch(0xD0, L('pre_in'))
    t.emit(0xEA, 0xCA)  # NOP; DEX
    t.branch(0xD0, L('pre_sl'))

    t.lda_imm(0x00)
    t.sta(band_addr)
    t.label(L('band'))
    t.lda(band_addr)
    t.cmp_m(cut_addr)
    t.branch(0x90, L('vis'))
    t.lda_imm(0x00)
    t.sta(0x2001)
    t.lda_imm(0x3F)
    t.sta(0x2006)
    t.lda_imm(0x0F)
    t.sta(0x2006)
    t.abs_ref(0x4C, L('next_frame'))

    t.label(L('vis'))
    if band_hook is not None:
        band_hook(a, band_addr)

    t.lda(band_addr)
    t.emit(0x18)  # CLC
    t.adc(frame_addr)
    t.and_imm(0x0F)
    t.emit(0xAA)  # TAX
    t.abs_ref(0xBD, w_lbl)  # LDA wave,X

    t.ldx(frame_addr)
    t.cpx_imm(8)
    t.branch(0x90, L('half'))
    t.cpx_imm(16)
    t.branch(0x90, L('sc_ok'))
    t.cpx_imm(24)
    t.branch(0x90, L('x2'))
    t.emit(0x0A)  # ASL A
    t.label(L('x2'))
    t.emit(0x0A)  # ASL A
    t.abs_ref(0x4C, L('sc_ok'))
    t.label(L('half'))
    t.cmp_imm(0x80)
    t.emit(0x6A)  # ROR A
    t.label(L('sc_ok'))

    if scroll_x_addr is None:
        t.sta(0x2005)
        t.lda_imm(0x00)
        t.sta(0x2005)
    else:
        assert scroll_nt_addr is not None and nt_tmp_addr is not None and base_tmp_addr is not None
        t.emit(0xAA)  # TAX (signed shear)
        if ppuctrl_addr is not None:
            t.lda(ppuctrl_addr)
            t.and_imm(ppuctrl_mask & 0xFE)
        else:
            t.lda_imm(0x00)
        t.sta(nt_tmp_addr)
        if scroll_hud_bands > 0:
            t.lda(band_addr)
            t.cmp_imm(scroll_hud_bands)
            t.branch(0x90, L('hud_band'))
        t.lda(scroll_nt_addr)
        t.and_imm(0x01)
        t.ora(nt_tmp_addr)
        t.sta(nt_tmp_addr)
        t.lda(scroll_x_addr)
        if scroll_hud_bands > 0:
            t.abs_ref(0x4C, L('add_shear'))
            t.label(L('hud_band'))
            t.lda_imm(0x00)
        t.label(L('add_shear'))
        t.sta(base_tmp_addr)
        t.emit(0x8A)  # TXA
        t.branch(0x30, L('neg'))
        t.emit(0x18)  # CLC
        t.adc(base_tmp_addr)
        t.branch(0x90, L('wr'))
        t.emit(0xAA)
        t.lda(nt_tmp_addr)
        t.eor_imm(0x01)
        t.sta(nt_tmp_addr)
        t.emit(0x8A)
        t.abs_ref(0x4C, L('wr'))
        t.label(L('neg'))
        t.emit(0x18)  # CLC
        t.adc(base_tmp_addr)
        t.branch(0xB0, L('wr'))
        t.emit(0xAA)
        t.lda(nt_tmp_addr)
        t.eor_imm(0x01)
        t.sta(nt_tmp_addr)
        t.emit(0x8A)
        t.label(L('wr'))
        t.ldx(nt_tmp_addr)
        t.stx(0x2000)
        t.sta(0x2005)
        t.lda_imm(0x00)
        t.sta(0x2005)

    # Wait ~8 scanlines per band
    is_zp = (frame_addr < 0x100 and band_addr < 0x100)
    wait_iters = 156 if (is_zp and scroll_x_addr is None) else 152
    t.ldy_imm(wait_iters)
    t.label(L('wait'))
    t.emit(0x88)  # DEY
    t.branch(0xD0, L('wait'))

    t.inc(band_addr)
    t.lda(band_addr)
    t.cmp_imm(30)
    t.branch(0xB0, L('next_frame'))
    t.abs_ref(0x4C, L('band'))

    t.label(L('next_frame'))
    if dir_addr is not None:
        t.lda(dir_addr)
        t.branch(0xD0, L('rev_next'))
        t.inc(frame_addr)
        t.lda(frame_addr)
        t.cmp_imm(30)
        t.branch(0xB0, L('done'))
        t.abs_ref(0x4C, L('frame'))
        t.label(L('rev_next'))
        t.dec(frame_addr)
        t.branch(0x30, L('done'))
        t.abs_ref(0x4C, L('frame'))
    elif direction == 'out':
        t.inc(frame_addr)
        t.lda(frame_addr)
        t.cmp_imm(30)
        t.branch(0xB0, L('done'))
        t.abs_ref(0x4C, L('frame'))
    else:
        t.dec(frame_addr)
        t.branch(0x30, L('done'))
        t.abs_ref(0x4C, L('frame'))

    t.label(L('done'))
    if end_on_vblank or dir_addr is not None:
        if dir_addr is not None and not end_on_vblank:
            t.lda(dir_addr)
            t.branch(0xF0, L('ret'))
        t.bit_abs(0x2002)
        t.label(L('vb2'))
        t.bit_abs(0x2002)
        t.branch(0x10, L('vb2'))
        t.lda_imm(0x00)
        t.sta(0x2006)
        t.sta(0x2006)
        t.sta(0x2005)
        t.sta(0x2005)
    t.label(L('ret'))
    if emit_rts:
        t.emit(0x60)  # RTS
        if wave_label is None:
            t.label(w_lbl)
            t.emit(*WAVE_TABLE)
    elif wave_label is None:
        t.abs_ref(0x4C, L('after_wave'))
        t.label(w_lbl)
        t.emit(*WAVE_TABLE)
        t.label(L('after_wave'))
