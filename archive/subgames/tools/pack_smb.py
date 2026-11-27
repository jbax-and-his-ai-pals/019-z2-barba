"""Assemble and patch Super Mario Bros. (NES, NROM-256) for the Barba Mapper 176 portal."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from portal_transitions import build_return_helper, emit_clean_apu_mute, emit_wavy_transition
import smb_art
import smb_barba
from subgame_pack import make_rom_header

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / 'roms' / 'smb.nes'
DEFAULT_Z2_SOURCE = ROOT / 'roms' / 'z2.nes'
DEFAULT_OUT = ROOT / 'build' / 'subgames' / 'smb.nes'

# Fixed entry points in guest WRAM ($7800-$7BFF)
SMB_NMI_HOOK   = 0x7800
SMB_WIN_HOOK   = 0x7850
SMB_SEED_RNG   = 0x7858
SMB_RETURN     = 0x7880
SMB_WIPE_THUNK = 0x78A8
SMB_BOOT       = 0x7900
SMB_CALL_BANK1 = smb_barba.SMB_CALL_BANK1
SMB_B0_WIPE_IN = 0x8500
SMB_B0_MELT_OUT = 0x8680

# Transition scratch in guest WRAM ($7FD0-$7FD5)
SMB_WIPE_DONE = 0x7FD0
SMB_TR_FRAME  = 0x7FD1
SMB_TR_CUT    = 0x7FD2
SMB_TR_BAND   = 0x7FD3
SMB_TR_NT_TMP = 0x7FD4
SMB_TR_BASE   = 0x7FD5

# Barba WRAM bank 0 win flag ($648F, unused per docs/MEMORY-MAP.md)
SMB_WIN_FLAG  = 0x648F
SMB_WIN_MAGIC = 0x4D

# SMB1 (USA) constants verified from roms/smb.nes
SMB_RESET_ADDR   = 0x8000
SMB_NMI_ADDR     = 0x8082
SMB_IRQ_ADDR     = 0xFFF0
SMB_CTRL1_ADDR   = 0x06FC  # SavedJoypad1Bits (debounced Start/Select in $074A)
SMB_START_SELECT = 0x30    # Select ($20) | Start ($10)
SMB_W8_END_ADDR  = 0x8487  # World 8-4 victory wait (LDA $06FC)
SMB_CASTLE_ADDR  = 0x8466  # Any castle clear after Toad/Princess text (LDY $075F)

DEFAULT_WRAM_BANK    = 0xA3
DEFAULT_RESTORE_ADDR = 0xE000


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


def make_smb_wram_code(
    restore_addr: int,
    wram_bank: int = DEFAULT_WRAM_BANK,
    *,
    reward_addr: int = SMB_WIN_FLAG,
    reward_magic: int = SMB_WIN_MAGIC,
    r1_bank: int = 2,
    include_bank1: bool = False,
    lock_exit: bool = False,
    enable_transitions: bool = False,
) -> bytes:
    """Assemble the 1024-byte ($7800-$7BFF) WRAM helper for Super Mario Bros."""
    out = bytearray(b'\xFF' * 0x400)

    def place(addr: int, data: bytes, limit: int) -> None:
        off = addr - 0x7800
        assert off + len(data) <= limit - 0x7800, f'Overflow at ${addr:04X}: {off + len(data)} > {limit - 0x7800}'
        out[off : off + len(data)] = data

    # 1. SMB_NMI_HOOK ($7800): 60-frame ($3C) debounce in $7FFF, then Start+Select -> SMB_RETURN
    a = Asm6502(SMB_NMI_HOOK)
    a.emit(0x48, 0xAD, 0xFF, 0x7F, 0xC9, 0x3C)                # PHA; LDA $7FFF; CMP #$3C
    a.branch(0xB0, 'check_pad')                               # BCS check_pad
    a.emit(0xEE, 0xFF, 0x7F)                                  # INC $7FFF
    a.branch(0xD0, 'normal_nmi')                              # BNE normal_nmi
    a.label('check_pad')
    a.emit(0x8A, 0x48)                                        # TXA; PHA
    a.emit(0xA9, 0x01, 0x8D, 0x16, 0x40)                      # LDA #$01; STA $4016
    a.emit(0x4A, 0x8D, 0x16, 0x40)                            # LSR A; STA $4016
    a.emit(0xA2, 0x08)                                        # LDX #$08
    a.label('pad_loop')
    a.emit(0x48, 0xAD, 0x16, 0x40, 0x29, 0x03, 0xC9, 0x01)    # PHA; LDA $4016; AND #$03; CMP #$01
    a.emit(0x68, 0x2A, 0xCA)                                  # PLA; ROL A; DEX
    a.branch(0xD0, 'pad_loop')                                # BNE pad_loop
    a.emit(0x29, SMB_START_SELECT, 0xC9, SMB_START_SELECT)    # AND #$30; CMP #$30
    a.branch(0xF0, 'do_return')                               # BEQ do_return
    a.emit(0x68, 0xAA)                                        # PLA; TAX
    a.label('normal_nmi')
    if enable_transitions:
        a.emit(0x4C, SMB_WIPE_THUNK & 0xFF, SMB_WIPE_THUNK >> 8)
    else:
        if include_bank1:
            a.emit(0xAD, smb_barba.W_CUR_R6 & 0xFF, smb_barba.W_CUR_R6 >> 8)
            a.emit(0x8D, smb_barba.W_NMI_SAVED_R6 & 0xFF, smb_barba.W_NMI_SAVED_R6 >> 8)
            a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 28, 0x8D, 0x01, 0x80)
        a.emit(0x68, 0x4C, SMB_NMI_ADDR & 0xFF, SMB_NMI_ADDR >> 8)  # PLA; JMP $8082
    a.label('do_return')
    a.emit(0x68, 0xAA, 0x68)                                  # PLA; TAX; PLA
    a.emit(0x4C, SMB_RETURN & 0xFF, SMB_RETURN >> 8)          # JMP SMB_RETURN
    place(SMB_NMI_HOOK, a.finish(), SMB_WIN_HOOK)

    # 2. SMB_WIN_HOOK ($7850): record win magic in $7FFE (guest WRAM), then jump to SMB_RETURN
    # (Never switch $A001 while executing from $78xx WRAM!)
    a = Asm6502(SMB_WIN_HOOK)
    a.emit(0xA9, reward_magic, 0x8D, 0xFE, 0x7F)              # LDA #reward_magic; STA $7FFE
    a.emit(0x4C, SMB_RETURN & 0xFF, SMB_RETURN >> 8)          # JMP SMB_RETURN
    place(SMB_WIN_HOOK, a.finish(), SMB_SEED_RNG)

    # 2b. SMB_SEED_RNG ($7858): seed PseudoRandomBitReg ($07A7-$07AD) from Barba's $7FF0-$7FF6
    a = Asm6502(SMB_SEED_RNG)
    a.emit(0xA2, 0x06)                                        # LDX #$06
    a.label('seed_loop')
    a.emit(0xBD, 0xF0, 0x7F)                                  # LDA $7FF0,X
    a.emit(0x9D, 0xA7, 0x07)                                  # STA $07A7,X
    a.emit(0xCA)                                              # DEX
    a.branch(0x10, 'seed_loop')                               # BPL seed_loop
    a.emit(0xAD, 0xA7, 0x07)                                  # LDA $07A7
    a.branch(0xD0, 'seed_ok')                                 # BNE seed_ok
    a.emit(0xA9, 0xA5, 0x8D, 0xA7, 0x07)                      # LDA #$A5; STA $07A7
    a.label('seed_ok')
    a.emit(0x60)                                              # RTS
    place(SMB_SEED_RNG, a.finish(), SMB_RETURN)

    # 3. SMB_RETURN ($7880): silence PPU/APU/IRQ, copy return trampoline to $0300, restore Barba banks
    a = Asm6502(SMB_RETURN)
    a.emit(0x78)                                              # SEI
    if enable_transitions:
        a.emit(0xAD, 0x78, 0x07, 0x29, 0x7F, 0x8D, 0x00, 0x20)
        emit_clean_apu_mute(a)
        a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x00, 0x8D, 0x01, 0x80)
        a.emit(0x4C, SMB_B0_MELT_OUT & 0xFF, SMB_B0_MELT_OUT >> 8)
        place(SMB_RETURN, a.finish(), SMB_WIPE_THUNK)

        at = Asm6502(SMB_WIPE_THUNK)
        if include_bank1:
            at.emit(0xAD, smb_barba.W_CUR_R6 & 0xFF, smb_barba.W_CUR_R6 >> 8)
            at.emit(0x8D, smb_barba.W_NMI_SAVED_R6 & 0xFF, smb_barba.W_NMI_SAVED_R6 >> 8)
        at.emit(0xAD, SMB_WIPE_DONE & 0xFF, SMB_WIPE_DONE >> 8)
        at.branch(0xD0, 'map28')
        at.emit(0xAD, 0x79, 0x07, 0x29, 0x08)
        at.branch(0xF0, 'map28')
        at.emit(0xAD, 0xFF, 0x7F, 0xC9, 0x04)
        at.branch(0x90, 'map28')
        at.emit(0x8A, 0x48, 0x98, 0x48)
        at.emit(0xEE, SMB_WIPE_DONE & 0xFF, SMB_WIPE_DONE >> 8)
        at.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x00, 0x8D, 0x01, 0x80)
        at.emit(0x20, SMB_B0_WIPE_IN & 0xFF, SMB_B0_WIPE_IN >> 8)
        at.emit(0x68, 0xA8, 0x68, 0xAA)
        at.label('map28')
        at.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 28, 0x8D, 0x01, 0x80)
        at.emit(0x68, 0x4C, SMB_NMI_ADDR & 0xFF, SMB_NMI_ADDR >> 8)
        place(SMB_WIPE_THUNK, at.finish(), SMB_BOOT)
    else:
        a.emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20)  # $2000=0; $2001=0
        a.emit(0x8D, 0x15, 0x40, 0x8D, 0x00, 0xE0)              # $4015=0; $E000=0 (disable MMC3 IRQ)
        a.emit(0xAC, 0xFE, 0x7F)                                # LDY $7FFE (0 or SMB_WIN_MAGIC)
        a.emit(0xA9, 0x00, 0x8D, 0xFE, 0x7F)                    # clear $7FFE
        a.emit(0xA2, 47)                                        # copy 48B trampoline to $0300
        a.label('cp')
        a.abs_ref(0xBD, 'tramp')
        a.emit(0x9D, 0x00, 0x03, 0xCA)
        a.branch(0x10, 'cp')
        a.emit(0x4C, 0x00, 0x03)                                # JMP $0300
        a.label('tramp')
        tramp = (
            bytes.fromhex(
                'a9 80 8d 01 a0 '                               # unlock $5FF0-$5FF3 (WRAM bank 0 until lock writes $A0)
                'a9 01 8d f0 5f '
                'a9 00 8d f1 5f 8d f2 5f '
                'a9 06 8d 00 80 a9 0c 8d 01 80 '
                'a9 07 8d 00 80 a9 0d 8d 01 80 '
            )
            + (bytes.fromhex('a9 a0 8d 01 a0') if lock_exit else b'')
            + bytes([0xC0, reward_magic, 0xD0, 0x03, 0x8C])      # if Y==reward_magic: STY reward_addr (WRAM bank 0)
            + reward_addr.to_bytes(2, 'little')
            + b'\x4c'
            + restore_addr.to_bytes(2, 'little')
        )
        a.buf[a.buf.index(0xA2) + 1] = len(tramp) - 1           # patch exact trampoline copy length
        a.emit(*tramp)
        place(SMB_RETURN, a.finish(), SMB_BOOT)

    # 4. SMB_BOOT ($7900): Vertical mirroring, map 32KB PRG + CHR, init WRAM, JMP $8000
    a = Asm6502(SMB_BOOT)
    a.emit(0x78)                                              # SEI
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0xA0, 0x8D, 0x00, 0xE0)    # $A000=0 (Vertical), $E000=0 (IRQ off)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 28, 0x8D, 0x01, 0x80)    # R6 = 28 ($8000-$9FFF)
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 29, 0x8D, 0x01, 0x80)    # R7 = 29 ($A000-$BFFF)
    for reg, bank in ((0, 0), (1, r1_bank), (2, 4), (3, 5), (4, 6), (5, 7)):
        a.emit(0xA9, reg, 0x8D, 0x00, 0x80, 0xA9, bank, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0x00, 0x8D, 0xFF, 0x7F, 0x8D, 0xFE, 0x7F)    # clear $7FFF debounce & $7FFE win flag
    if enable_transitions:
        a.emit(0x8D, SMB_WIPE_DONE & 0xFF, SMB_WIPE_DONE >> 8)
    if include_bank1:
        a.emit(0xA2, 0x0F)
        a.label('clr_barba')
        a.emit(0x9D, 0x00, 0x7C, 0xCA)                        # clear $7C00-$7C0F
        a.branch(0x10, 'clr_barba')
        a.emit(0xA9, 28, 0x8D, smb_barba.W_CUR_R6 & 0xFF, smb_barba.W_CUR_R6 >> 8)
        a.emit(0xA9, 0x06, 0x8D, smb_barba.W_MMC3_SEL & 0xFF, smb_barba.W_MMC3_SEL >> 8)
    a.emit(0x4C, SMB_RESET_ADDR & 0xFF, SMB_RESET_ADDR >> 8)  # JMP $8000 (SMB Reset)
    if include_bank1:
        place(SMB_BOOT, a.finish(), SMB_CALL_BANK1)
        place(SMB_CALL_BANK1, smb_barba.assemble_call_bank1(), smb_barba.SMB_NMI_EXIT)
        nmi_exit = Asm6502(smb_barba.SMB_NMI_EXIT)
        nmi_exit.emit(0x8D, 0x00, 0x20)                       # STA $2000 (enable PPU NMI)
        nmi_exit.emit(0x48)                                   # PHA
        nmi_exit.emit(0xA9, 0x06, 0x8D, 0x00, 0x80)
        nmi_exit.emit(0xAD, smb_barba.W_NMI_SAVED_R6 & 0xFF, smb_barba.W_NMI_SAVED_R6 >> 8)
        nmi_exit.emit(0x8D, 0x01, 0x80)                       # restore interrupted R6 (1 or 28)
        nmi_exit.emit(0xAD, smb_barba.W_MMC3_SEL & 0xFF, smb_barba.W_MMC3_SEL >> 8)
        nmi_exit.emit(0x8D, 0x00, 0x80)                       # restore interrupted $8000 select
        nmi_exit.emit(0x68, 0x40)                             # PLA; RTI
        place(smb_barba.SMB_NMI_EXIT, nmi_exit.finish(), 0x7C00)
    else:
        place(SMB_BOOT, a.finish(), 0x7C00)

    return bytes(out)


def make_smb_bank0(
    restore_addr: int,
    wram_bank: int = DEFAULT_WRAM_BANK,
    *,
    reward_addr: int = SMB_WIN_FLAG,
    reward_magic: int = SMB_WIN_MAGIC,
    r1_bank: int = 2,
    include_bank1: bool = False,
    lock_exit: bool = False,
    enable_transitions: bool = False,
    game_id: int | None = None,
) -> bytes:
    """Build 8KB bank 0 for SMB: $8000 copies $8100-$84FF -> $7800-$7BFF and jumps to SMB_BOOT."""
    bank0 = bytearray(b'\xFF' * 8192)
    a = Asm6502(0x8000)
    a.emit(0x78)                                              # SEI
    a.emit(0xA9, wram_bank, 0x8D, 0x01, 0xA0)                 # enable guest WRAM bank + lock $5FF0-$5FF3
    a.emit(0xA9, 0x00, 0x85, 0x00, 0x85, 0x02)                # $00=0, $02=0
    a.emit(0xA9, 0x81, 0x85, 0x01)                            # $01=$81
    a.emit(0xA9, 0x78, 0x85, 0x03)                            # $03=$78
    a.emit(0xA2, 0x04, 0xA0, 0x00)                            # 4 pages ($8100-$84FF -> $7800-$7BFF)
    a.label('cp')
    a.emit(0xB1, 0x00, 0x91, 0x02, 0xC8)
    a.branch(0xD0, 'cp')
    a.emit(0xE6, 0x01, 0xE6, 0x03, 0xCA)
    a.branch(0xD0, 'cp')
    a.emit(0x4C, SMB_BOOT & 0xFF, SMB_BOOT >> 8)              # JMP SMB_BOOT ($7900)
    loader = a.finish()
    assert len(loader) <= 0x100
    bank0[0 : len(loader)] = loader
    bank0[0x100 : 0x500] = make_smb_wram_code(
        restore_addr,
        wram_bank=wram_bank,
        reward_addr=reward_addr,
        reward_magic=reward_magic,
        r1_bank=r1_bank,
        include_bank1=include_bank1,
        lock_exit=lock_exit,
        enable_transitions=enable_transitions,
    )
    if enable_transitions:
        aw = Asm6502(SMB_B0_WIPE_IN)
        emit_wavy_transition(
            aw,
            prefix='smbw',
            frame_addr=SMB_TR_FRAME,
            cut_addr=SMB_TR_CUT,
            band_addr=SMB_TR_BAND,
            direction='in',
            ppuctrl_addr=0x0778,
            ppuctrl_mask=0x7C,
            ppumask_addr=0x0779,
            scroll_x_addr=0x073F,
            scroll_nt_addr=0x0778,
            scroll_hud_bands=4,
            nt_tmp_addr=SMB_TR_NT_TMP,
            base_tmp_addr=SMB_TR_BASE,
            end_on_vblank=True,
        )
        wipe_bytes = aw.finish()
        assert SMB_B0_WIPE_IN + len(wipe_bytes) <= SMB_B0_MELT_OUT
        bank0[SMB_B0_WIPE_IN - 0x8000 : SMB_B0_WIPE_IN - 0x8000 + len(wipe_bytes)] = wipe_bytes

        am = Asm6502(SMB_B0_MELT_OUT)
        emit_wavy_transition(
            am,
            prefix='smbm',
            frame_addr=SMB_TR_FRAME,
            cut_addr=SMB_TR_CUT,
            band_addr=SMB_TR_BAND,
            direction='out',
            ppuctrl_addr=0x0778,
            ppuctrl_mask=0x7C,
            ppumask_addr=0x0779,
            scroll_x_addr=0x073F,
            scroll_nt_addr=0x0778,
            scroll_hud_bands=4,
            nt_tmp_addr=SMB_TR_NT_TMP,
            base_tmp_addr=SMB_TR_BASE,
            emit_rts=False,
        )
        am.emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20)
        am.emit(0xAC, 0xFE, 0x7F, 0xA9, 0x00, 0x8D, 0xFE, 0x7F)
        tramp = build_return_helper(
            restore_addr,
            reward_addr,
            game_id=game_id,
            win_reg='y',
            check_magic=reward_magic,
            lock_wram=lock_exit,
        )
        am.emit(0xA2, len(tramp) - 1)
        am.label('cp_tramp')
        am.abs_ref(0xBD, 'tramp_data')
        am.emit(0x9D, 0x00, 0x03, 0xCA)
        am.branch(0x10, 'cp_tramp')
        am.emit(0x4C, 0x00, 0x03)
        am.label('tramp_data')
        am.emit(*tramp)
        melt_bytes = am.finish()
        assert SMB_B0_MELT_OUT - 0x8000 + len(melt_bytes) <= 8192
        bank0[SMB_B0_MELT_OUT - 0x8000 : SMB_B0_MELT_OUT - 0x8000 + len(melt_bytes)] = melt_bytes
    return bytes(bank0)


def patch_smb(smb_bytes: bytes, *, castle_clear: bool = False) -> tuple[bytes, bytes, dict]:
    """Verify and patch SMB (NROM-256) PRG/CHR and return (prg32k, chr8k, metadata)."""
    assert smb_bytes[:4] == b'NES\x1a', 'Invalid iNES header'
    assert smb_bytes[4] == 2, f'Expected 2x16KB PRG, got {smb_bytes[4]}'
    assert smb_bytes[5] == 1, f'Expected 1x8KB CHR, got {smb_bytes[5]}'
    assert (smb_bytes[6] & 0x01) == 1, 'Expected Vertical mirroring'

    prg = bytearray(smb_bytes[16 : 16 + 32768])
    chr_data = smb_bytes[16 + 32768 : 16 + 32768 + 8192]

    def patch(addr: int, new: bytes, expected: bytes) -> None:
        off = addr - 0x8000
        actual = bytes(prg[off : off + len(expected)])
        assert actual == expected, f'Unexpected SMB bytes at ${addr:04X}: {actual.hex(" ")}'
        prg[off : off + len(new)] = new

    # 1. Redirect NMI vector ($FFFA) -> SMB_NMI_HOOK ($7800)
    patch(
        0xFFFA,
        bytes([SMB_NMI_HOOK & 0xFF, SMB_NMI_HOOK >> 8]),
        bytes([SMB_NMI_ADDR & 0xFF, SMB_NMI_ADDR >> 8]),
    )

    # 2. Win hook: World 8-4 ending ($8487) or any castle clear ($8466)
    win_addrs = [SMB_W8_END_ADDR]
    patch(
        SMB_W8_END_ADDR,
        bytes([0x4C, SMB_WIN_HOOK & 0xFF, SMB_WIN_HOOK >> 8]),
        bytes.fromhex('ad fc 06'),
    )
    if castle_clear:
        win_addrs.insert(0, SMB_CASTLE_ADDR)
        patch(
            SMB_CASTLE_ADDR,
            bytes([0x4C, SMB_WIN_HOOK & 0xFF, SMB_WIN_HOOK >> 8]),
            bytes.fromhex('ac 5f 07'),
        )

    # 3. Boot RNG seed ($8039: STA $07A7 -> JSR SMB_SEED_RNG)
    patch(
        0x8039,
        bytes([0x20, SMB_SEED_RNG & 0xFF, SMB_SEED_RNG >> 8]),
        bytes.fromhex('8d a7 07'),
    )

    metadata = {
        'prg_size': len(prg),
        'chr_size': len(chr_data),
        'boot_addr': 0x8000,
        'vectors': {
            'nmi': SMB_NMI_ADDR,
            'reset': SMB_RESET_ADDR,
            'irq': SMB_IRQ_ADDR,
        },
        'ctrl_addr': SMB_CTRL1_ADDR,
        'ctrl_mask': SMB_START_SELECT,
        'win_addrs': win_addrs,
        'win_flag_addr': SMB_WIN_FLAG,
        'win_flag_magic': SMB_WIN_MAGIC,
    }
    return bytes(prg), chr_data, metadata


def patch_smb_barba(
    smb_bytes: bytes,
    z2_bytes: bytes,
    *,
    castle_clear: bool = False,
    build_number: int | None = None,
) -> tuple[bytes, bytes, bytes, dict]:
    """Patch SMB into Super Barba Bros. (bank1 8KB, prg32 32KB, chr32 32KB, metadata)."""
    orig_prg32 = smb_bytes[16 : 16 + 32768]
    bank1_8k = smb_barba.build_bank1(orig_prg32)
    prg32_base, _, metadata = patch_smb(smb_bytes, castle_clear=castle_clear)
    prg32 = bytearray(prg32_base)
    barba_meta = smb_barba.apply_barba_patches(prg32, ROOT)
    chr32 = bytearray(smb_art.build_smb_barba_chr(smb_bytes, z2_bytes))
    if build_number is not None:
        # SMB title PPU stream starts at CHR $1EC0; append $203A B<N> at the 0x00 terminator.
        pos = 0x1EC0
        while pos < 0x2000 and chr32[pos] != 0x00:
            ctrl = chr32[pos + 2]
            pos += 4 if (ctrl & 0x40) else (3 + (ctrl & 0x3F))
        tag = bytes([0x0B] + [int(c) for c in str(build_number)])
        pkt = bytes([0x20, 0x3A, len(tag)]) + tag + b'\x00'
        assert pos + len(pkt) <= 0x2000, f'SMB title B<N> overflow at ${pos:04X}'
        assert chr32[pos : pos + len(pkt)] == b'\x00' + b'\xFF' * (len(pkt) - 1)
        chr32[pos : pos + len(pkt)] = pkt
    assert len(bank1_8k) == 8192
    assert len(prg32) == 32768
    assert len(chr32) <= 128 * 1024
    metadata['chr_size'] = len(chr32)
    metadata['bank1_size'] = len(bank1_8k)
    metadata['barba'] = barba_meta
    return bank1_8k, bytes(prg32), bytes(chr32), metadata


def patch_smb_for_combined(
    smb_bytes: bytes,
    z2_bytes: bytes,
    restore_addr: int,
    *,
    reward_addr: int = 0x63B4,
    reward_magic: int = SMB_WIN_MAGIC,
    castle_clear: bool = False,
    enable_transitions: bool = False,
    game_id: int | None = None,
) -> tuple[bytes, bytes]:
    """Build combined-ROM Slot 6 payload: (prg_256k, chr_up_to_128k) with offset 0 as boot bank."""
    bank1_8k, prg32_patched, chr32, _ = patch_smb_barba(
        smb_bytes, z2_bytes, castle_clear=castle_clear
    )
    bank0 = make_smb_bank0(
        restore_addr,
        wram_bank=DEFAULT_WRAM_BANK,
        reward_addr=reward_addr,
        reward_magic=reward_magic,
        r1_bank=smb_art.CHR_R1_ENEMIES,
        include_bank1=True,
        lock_exit=True,
        enable_transitions=enable_transitions,
        game_id=game_id,
    )
    prg256 = bytearray(b'\xFF' * (256 * 1024))
    prg256[0 : 8192] = bank0
    prg256[8192 : 2 * 8192] = bank1_8k
    prg256[28 * 8192 : 32 * 8192] = prg32_patched
    return bytes(prg256), chr32


def build_standalone(
    out_path: Path = DEFAULT_OUT,
    source_path: Path = DEFAULT_SOURCE,
    z2_path: Path = DEFAULT_Z2_SOURCE,
    *,
    restore_addr: int = DEFAULT_RESTORE_ADDR,
    wram_bank: int = DEFAULT_WRAM_BANK,
    castle_clear: bool = False,
    mapper: str = '176',
    build_number: int | None = None,
) -> dict:
    """Build standalone Super Barba Bros. ROM (Mapper 176 or MMC3) at out_path."""
    from build_history import HISTORY_FILE, next_subgame_build_number, record_subgame_build
    import hashlib
    record_this = build_number is None
    if build_number is None:
        build_number = next_subgame_build_number(HISTORY_FILE, 'smb')
    bank1_8k, prg32k, chr32k, metadata = patch_smb_barba(
        source_path.read_bytes(), z2_path.read_bytes(), castle_clear=castle_clear,
        build_number=build_number,
    )
    bank0 = make_smb_bank0(
        restore_addr,
        wram_bank=0x80 if mapper == 'mmc3' else wram_bank,
        r1_bank=smb_art.CHR_R1_ENEMIES,
        include_bank1=True,
        lock_exit=False,
    )

    # 256KB PRG (32 x 8KB banks): bank 0 = loader+WRAM, bank 1 = relocated SMB routines + Z2 code,
    # banks 28..31 = SMB 32KB PRG (with roar.dmc & MMC3 hooks)
    prg256 = bytearray(b'\xFF' * (256 * 1024))
    prg256[0 : 8192] = bank0
    prg256[8192 : 2 * 8192] = bank1_8k
    prg256[28 * 8192 : 32 * 8192] = prg32k

    assert len(chr32k) % 8192 == 0
    hdr = make_rom_header(len(prg256), len(chr32k), mapper=mapper, vertical_mirroring=True)

    rom_bytes = bytes(hdr) + bytes(prg256) + chr32k
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(rom_bytes)
    if record_this:
        record_subgame_build(HISTORY_FILE, 'smb', build_number, mapper, out_path, hashlib.sha256(rom_bytes).hexdigest())
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--z2', type=Path, default=DEFAULT_Z2_SOURCE)
    parser.add_argument('--out', type=Path, default=None)
    parser.add_argument('--mapper', choices=('176', 'mmc3'), default='176')
    parser.add_argument('--castle-clear', action='store_true', help='Also trigger win hook on World 1-4..7-4 clear')
    args = parser.parse_args()
    out_path = args.out or (ROOT / 'play/compat/nes/smb-compat.nes' if args.mapper == 'mmc3' else DEFAULT_OUT)
    meta = build_standalone(out_path, args.source, args.z2, castle_clear=args.castle_clear, mapper=args.mapper)
    if args.mapper == 'mmc3' and args.out is None:
        from bps import write_bps
        write_bps(
            args.source,
            out_path,
            out_bps_path=ROOT / 'play/compat/bps/smb-compat.bps',
            metadata='smb-compat | Barba Edition (MMC3)',
        )
    print(f'Built {out_path} ({out_path.stat().st_size:,} bytes, mapper={args.mapper}): {meta}')


if __name__ == '__main__':
    main()
