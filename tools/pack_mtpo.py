"""Pack Mike Tyson's Punch-Out!! (MMC2) -> Barba's Punch-Out!! (MMC3 / Mapper 176)."""
from __future__ import annotations

from pathlib import Path
import sys

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from mtpo_art import apply_mtpo_mod_art
from pack_f13 import Asm6502 as _BaseAsm6502
import roar_sample


class Asm6502(_BaseAsm6502):
    def jsr(self, target: str) -> None:
        self.abs_ref(0x20, target)

    def jmp(self, target: str) -> None:
        self.abs_ref(0x4C, target)

    def lda_abs_x(self, target: str) -> None:
        self.abs_ref(0xBD, target)

MTPO_HDR_SIZE = 16
MTPO_PRG_SIZE = 128 * 1024
MTPO_CHR_SIZE = 128 * 1024
MTPO_TOTAL_SIZE = MTPO_HDR_SIZE + MTPO_PRG_SIZE + MTPO_CHR_SIZE

PRG_OUT_SIZE = 256 * 1024  # 32 x 8KB banks
CHR_OUT_SIZE = 128 * 1024  # 128 x 1KB banks

# Fixed Bank 13 hooks
MTPO_ORIG_RESET = 0xA000
MTPO_ORIG_NMI = 0xA008
MTPO_ORIG_IRQ = 0xA000

# WRAM Bank 3 ($A001 = $A3) virtualization state ($7F80..$7FEF; $7FF0..$7FFF reserved!)
V_MMC3_SEL = 0x7F80
V_MODE = 0x7F81       # 0=static, 1=title, 2=link intro, 3=tale of tape, 4=fight
V_CHR0_FD = 0x7F82
V_CHR0_FE = 0x7F83
V_CHR1_FD = 0x7F84
V_CHR1_FE = 0x7F85
V_IRQ_STEP = 0x7F86
V_TMP_A = 0x7F87
V_WIN_FLAG = 0x7F88
V_TMP_X = 0x7F89
V_TMP_Y = 0x7F8A

V_RNG_SEED = 0x7FF0   # 8 bytes seeded by PortalTramp2
V_HOLD_CNT = 0x7FFF   # 60-frame Start+Select hold counter

# Bank 14 free space: $D858..$DFFF (1960 bytes of $00 in vanilla MTPO)
B14_CODE_BASE = 0xD860
# Bank 15 free space: $F869..$FFCF (1895 bytes of $00 in vanilla MTPO)
ROAR_DMC_ADDR = 0xF880  # 64-byte aligned -> $4012 = ($F880 - $C000) >> 6 = $E2
ROAR_DMC_RATE = 9
STANDALONE_BOOT_STUB = 0xFF60
STANDALONE_RESTORE_ADDR = 0xFF90


def _patch_slice(buf: bytearray, base: int, addr: int, new: bytes, expected: bytes, label: str = "") -> None:
    if len(new) != len(expected):
        raise ValueError(f"Patch length mismatch at ${addr:04X} ({label}): new={len(new)} != exp={len(expected)}")
    off = base + (addr - (0x8000 if addr < 0xA000 else (0xA000 if addr < 0xC000 else (0xC000 if addr < 0xE000 else 0xE000))))
    actual = bytes(buf[off : off + len(expected)])
    if actual != expected:
        raise ValueError(
            f"Patch mismatch at ${addr:04X} ({label}): got {actual.hex()}, expected {expected.hex()}"
        )
    buf[off : off + len(new)] = new


def _emit_chr0_helper(a: Asm6502) -> None:
    """Emit V_SET_CHR0 (A = 4KB bank) -> sets R0/R1, restores $8000=V_MMC3_SEL. Clobbers A."""
    a.label("v_set_chr0")
    a.emit(0x0A, 0x0A)                    # ASL A; ASL A
    a.emit(0x48)                          # PHA
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x80)  # LDA #$00; STA $8000
    a.emit(0x68, 0x8D, 0x01, 0x80)        # PLA; STA $8001
    a.emit(0x18, 0x69, 0x02, 0x48)        # CLC; ADC #$02; PHA
    a.emit(0xA9, 0x01, 0x8D, 0x00, 0x80)  # LDA #$01; STA $8000
    a.emit(0x68, 0x8D, 0x01, 0x80)        # PLA; STA $8001
    a.emit(0xAD, V_MMC3_SEL & 0xFF, V_MMC3_SEL >> 8)
    a.emit(0x8D, 0x00, 0x80)              # STA $8000
    a.emit(0x60)                          # RTS


def _emit_chr1_helper(a: Asm6502) -> None:
    """Emit V_SET_CHR1 (A = 4KB bank) -> sets R2..R5, restores $8000=V_MMC3_SEL. Clobbers A."""
    a.label("v_set_chr1")
    a.emit(0x0A, 0x0A)                    # ASL A; ASL A
    for r in (2, 3, 4, 5):
        a.emit(0x48)                      # PHA
        a.emit(0xA9, r, 0x8D, 0x00, 0x80) # LDA #r; STA $8000
        a.emit(0x68)                      # PLA
        a.emit(0x8D, 0x01, 0x80)          # STA $8001
        if r < 5:
            a.emit(0x18, 0x69, 0x01)      # CLC; ADC #$01
    a.emit(0xAD, V_MMC3_SEL & 0xFF, V_MMC3_SEL >> 8)
    a.emit(0x8D, 0x00, 0x80)              # STA $8000
    a.emit(0x60)                          # RTS


def _assemble_bank0_boot() -> bytes:
    """Assemble 8KB boot bank at $8000 (jumps immediately to fixed Bank 14 v_boot_cont)."""
    a = Asm6502(0x8000)
    a.emit(0x78, 0xD8)                    # SEI; CLD
    a.emit(0xA2, 0xFF, 0x9A)              # LDX #$FF; TXS
    a.emit(0x4C, B14_CODE_BASE & 0xFF, B14_CODE_BASE >> 8)  # JMP v_boot_cont
    code = a.finish()
    bank0 = bytearray(8192)
    bank0[: len(code)] = code
    return bytes(bank0)


def _assemble_bank14_runtime(
    restore_addr: int,
    reward_addr: int,
    roar_len_reg: int,
) -> tuple[bytes, dict[str, int]]:
    """Assemble all MMC3 virtualization, NMI, IRQ, roar, and return code at $D860."""
    a = Asm6502(B14_CODE_BASE)

    # ---- Entry 0 (fixed at B14_CODE_BASE = $D860): v_boot_cont ----
    a.label("v_boot_cont")
    a.emit(0xA9, 0xA3, 0x8D, 0x01, 0xA0)  # LDA #$A3; STA $A001 (WRAM bank 3 + FK23C unlock)
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0xA0)  # LDA #$00; STA $A000 (vertical mirroring)
    a.emit(0x8D, 0x00, 0xE0)              # STA $E000 (disable MMC3 IRQ)
    # Clear $7F80..$7FEF without touching $7FF0..$7FFF
    a.emit(0xA2, 0x6F)                    # LDX #$6F
    a.label("boot_clr")
    a.emit(0x9D, 0x80, 0x7F)              # STA $7F80,X
    a.emit(0xCA)                          # DEX
    a.branch(0x10, "boot_clr")            # BPL boot_clr
    # R7 = 29 (MTPO Bank 13 at $A000-$BFFF)
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80)
    a.emit(0xA9, 29, 0x8D, 0x01, 0x80)
    # R6 = 1 (MTPO Bank 0 at $8000-$9FFF)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0x8D, V_MMC3_SEL & 0xFF, V_MMC3_SEL >> 8)
    a.emit(0xA9, 0x01, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0x00)
    a.jsr("v_set_chr0")
    a.emit(0xA9, 0x00)
    a.jsr("v_set_chr1")
    a.emit(0x4C, MTPO_ORIG_RESET & 0xFF, MTPO_ORIG_RESET >> 8)

    _emit_chr0_helper(a)
    _emit_chr1_helper(a)

    # ---- v_post_wipe_init (called at $A28B after MTPO wipes $0000-$07FF) ----
    a.label("v_post_wipe_init")
    a.emit(0xAD, 0xF0, 0x7F, 0x4D, 0xF1, 0x7F, 0x09, 0x01, 0x85, 0x18)  # RNG seed $18
    a.emit(0xAD, 0xF2, 0x7F, 0x4D, 0xF3, 0x7F, 0x85, 0x19)              # RNG seed $19
    a.emit(0xAD, 0xF4, 0x7F, 0x4D, 0xF5, 0x7F, 0x85, 0x1E)              # frame seed $1E
    a.emit(0x58)                                                        # CLI (IRQs enabled in main thread)
    a.emit(0x4C, 0x02, 0xAF)                                            # JMP $AF02

    # ---- v_prg_switch (called from $AA4A; A = MTPO bank 0..12, preserves A/X/Y/I) ----
    a.label("v_prg_switch")
    a.emit(0x85, 0x0D)                    # STA $0D
    a.emit(0x08, 0x78)                    # PHP; SEI
    a.emit(0x48)                          # PHA
    a.emit(0xC9, 13)                      # CMP #13
    a.branch(0x90, "prg_sw_norm")         # BCC prg_sw_norm
    a.emit(0x18, 0x69, 16)                # CLC; ADC #16 (13..15 -> 29..31)
    a.branch(0xD0, "prg_sw_push")         # BNE (always taken, >=29)
    a.label("prg_sw_norm")
    a.emit(0x18, 0x69, 0x01)              # CLC; ADC #$01 (0..12 -> 1..13)
    a.label("prg_sw_push")
    a.emit(0x48)                          # PHA
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80)  # LDA #$06; STA $8000
    a.emit(0x68, 0x8D, 0x01, 0x80)        # PLA; STA $8001
    a.emit(0xAD, V_MMC3_SEL & 0xFF, V_MMC3_SEL >> 8)
    a.emit(0x8D, 0x00, 0x80)              # STA $8000
    a.emit(0x68)                          # PLA (original A)
    a.emit(0x28)                          # PLP
    a.emit(0x60)                          # RTS

    # ---- v_bf55 (replaces $BF55: A=chr1_fe, X=chr0, D000=0) ----
    a.label("v_bf55")
    a.emit(0x8D, V_CHR1_FE & 0xFF, V_CHR1_FE >> 8)
    a.emit(0x8E, V_CHR0_FD & 0xFF, V_CHR0_FD >> 8)
    a.emit(0x8E, V_CHR0_FE & 0xFF, V_CHR0_FE >> 8)
    a.emit(0x86, 0xA9)                    # STX $A9
    a.emit(0xA9, 0x00)
    a.emit(0x8D, V_CHR1_FD & 0xFF, V_CHR1_FD >> 8)
    # Detect V_MODE from (A=CHR1_FE, X=CHR0):
    #   Title2 ($B6D9): CHR1_FE=4, CHR0=4 -> mode 1
    #   Link Intro / Newspaper / Ending ($B674/$B8CF/$B96E): CHR1_FE=7 -> mode 2
    #   else -> mode 0
    a.emit(0xA9, 0x00)
    a.emit(0xAC, V_CHR1_FE & 0xFF, V_CHR1_FE >> 8)
    a.emit(0xC0, 0x04)
    a.branch(0xD0, "bf55_chk_intro")
    a.emit(0xE0, 0x04)
    a.branch(0xD0, "bf55_set_mode")
    a.emit(0xA9, 0x01)
    a.branch(0xD0, "bf55_set_mode")
    a.label("bf55_chk_intro")
    a.emit(0xC0, 0x07)
    a.branch(0xD0, "bf55_set_mode")
    a.emit(0xA9, 0x02)
    a.label("bf55_set_mode")
    a.emit(0x8D, V_MODE & 0xFF, V_MODE >> 8)
    a.emit(0x8A)                          # TXA (CHR0)
    a.jsr("v_set_chr0")
    a.emit(0xAD, V_CHR1_FE & 0xFF, V_CHR1_FE >> 8)
    # For Title (mode 1) start VBlank with Bank 0 (text at top); else Bank CHR1_FE
    a.emit(0xAE, V_MODE & 0xFF, V_MODE >> 8)
    a.emit(0xE0, 0x01)
    a.branch(0xD0, "bf55_chr1")
    a.emit(0xA9, 0x00)
    a.label("bf55_chr1")
    a.jsr("v_set_chr1")
    a.emit(0x60)

    # ---- v_b90f_chr0 (A = CHR0_FD in Belt screen) ----
    a.label("v_b90f_chr0")
    a.emit(0x8D, V_CHR0_FD & 0xFF, V_CHR0_FD >> 8)
    a.jsr("v_set_chr0")
    a.emit(0x60)

    # ---- v_tape_chr (replaces $BD05..$BD1A in Tale of the Tape) ----
    a.label("v_tape_chr")
    a.emit(0xA9, 0x03, 0x8D, V_MODE & 0xFF, V_MODE >> 8)  # V_MODE = 3 (Tape)
    a.emit(0xA9, 0x00, 0x8D, V_CHR1_FD & 0xFF, V_CHR1_FD >> 8)
    a.emit(0xAD, 0xEE, 0x06, 0x8D, V_CHR1_FE & 0xFF, V_CHR1_FE >> 8)
    a.emit(0xA9, 0x05, 0x8D, V_CHR0_FD & 0xFF, V_CHR0_FD >> 8)
    a.emit(0xAD, 0xEF, 0x06, 0x8D, V_CHR0_FE & 0xFF, V_CHR0_FE >> 8)
    a.emit(0x85, 0xA9)                    # STA $A9
    a.jsr("v_set_chr0")
    a.emit(0xA9, 0x00)                    # Bank 0 for text
    a.jsr("v_set_chr1")
    a.emit(0x60)

    # ---- v_fight_chr0 (called at $A5D7 in Fight NMI: A = $A9) ----
    a.label("v_fight_chr0")
    a.emit(0xA5, 0xA9)
    a.jsr("v_set_chr0")
    a.emit(0x60)

    # ---- v_fight_cli (called at $A64D in Fight NMI instead of JSR $8012) ----
    a.label("v_fight_cli")
    a.emit(0x20, 0x12, 0x80)              # JSR $8012
    a.emit(0x58)                          # CLI
    a.emit(0x60)

    # ---- v_arm_irq (hooked at $AA02: executes STA $2000, arms VBlank CHR + IRQ, CLI for Tape, RTS) ----
    a.label("v_arm_irq")
    a.emit(0x8D, 0x00, 0x20)              # STA $2000 (from original $AA02)
    a.jsr("v_setup_frame_irq")
    a.emit(0xAD, V_MODE & 0xFF, V_MODE >> 8, 0xC9, 0x03)
    a.branch(0xD0, "arm_irq_rts")
    # In Mode 3 (Tale of the Tape), hide portrait OAM sprites (54 <= Y < 192, X >= 16)
    # after VBlank PPU uploads so vanilla Mac/Doc/opponent OAM overlays never cover custom BG portraits.
    a.emit(0xA2, 0x00)
    a.label("m3_oam_lp")
    a.emit(0xBD, 0x00, 0x02)              # LDA $0200,X (Y)
    a.emit(0xC9, 54)
    a.branch(0x90, "m3_oam_nx")           # BCC
    a.emit(0xC9, 192)
    a.branch(0xB0, "m3_oam_nx")           # BCS
    a.emit(0xBD, 0x03, 0x02)              # LDA $0203,X (X)
    a.emit(0xC9, 16)
    a.branch(0x90, "m3_oam_nx")           # BCC
    a.emit(0xA9, 0xFF, 0x9D, 0x00, 0x02)  # STA $0200,X (hide)
    a.label("m3_oam_nx")
    a.emit(0xE8, 0xE8, 0xE8, 0xE8)        # INX x4
    a.branch(0xD0, "m3_oam_lp")
    a.emit(0x58)                          # CLI so early-scanline Tale of the Tape IRQ runs during $A6DF sound
    a.label("arm_irq_rts")
    a.emit(0x60)

    # ---- v_sound_nmi_end (hooked at $A036: arms IRQ after $1D>=3 NMI, CLI for early-scanline splits, then JMP $A6DF) ----
    a.label("v_sound_nmi_end")
    a.jsr("v_setup_frame_irq")
    a.emit(0x58)                          # CLI
    a.emit(0x4C, 0xDF, 0xA6)              # JMP $A6DF

    # ---- v_setup_frame_irq: sets VBlank CHR + arms scanline IRQ for current screen ----
    a.label("v_setup_frame_irq")
    a.emit(0x8D, 0x00, 0xE0)              # STA $E000 (disable IRQ while configuring)
    a.emit(0xA9, 0x00, 0x8D, V_IRQ_STEP & 0xFF, V_IRQ_STEP >> 8)
    # Only arm scanline IRQ if rendering is enabled ($11 & $18 == $18)
    a.emit(0xA5, 0x11, 0x29, 0x18, 0xC9, 0x18)
    a.branch(0xD0, "irq_off_done")
    # If $1D == 0 -> Fight mode (set V_MODE = 4 so sl=95 IRQ works even after $A66A sets $1D=1)
    a.emit(0xA5, 0x1D)
    a.branch(0xD0, "chk_vmode")
    a.emit(0xA9, 0x04, 0x8D, V_MODE & 0xFF, V_MODE >> 8)
    # Fight mode: R0/R1 = $A9, R2..R5 = 0, latch 94 (IRQ at sl=95)
    a.emit(0xA5, 0xA9)
    a.jsr("v_set_chr0")
    a.emit(0xA9, 0x00)
    a.jsr("v_set_chr1")
    a.emit(0xA9, 94)
    a.branch(0xD0, "arm_latch")
    a.label("irq_off_done")
    a.emit(0x60)

    a.label("chk_vmode")
    a.emit(0xAD, V_MODE & 0xFF, V_MODE >> 8)
    a.branch(0xF0, "irq_off_done")        # V_MODE == 0 -> no split
    a.emit(0xC9, 0x01)
    a.branch(0xD0, "chk_m2")
    # Mode 1 (Title): VBlank R0/R1=4, R2..R5=0, latch 46 (sl=47 -> Bank 4)
    a.emit(0xA9, 0x04)
    a.jsr("v_set_chr0")
    a.emit(0xA9, 0x00)
    a.jsr("v_set_chr1")
    a.emit(0xA9, 46)
    a.branch(0xD0, "arm_latch")

    a.label("chk_m2")
    a.emit(0xC9, 0x02)
    a.branch(0xD0, "chk_m3")
    # Mode 2 (Link Intro / Newspaper / Ending): VBlank R0/R1=V_CHR0_FE, R2..R5=7, latch 140 (sl=141 -> R0/R1=4 for "EVIL LINK")
    a.emit(0xAD, V_CHR0_FE & 0xFF, V_CHR0_FE >> 8)
    a.jsr("v_set_chr0")
    a.emit(0xA9, 0x07)
    a.jsr("v_set_chr1")
    a.emit(0xA9, 140)
    a.branch(0xD0, "arm_latch")

    a.label("chk_m3")
    a.emit(0xC9, 0x03)
    a.branch(0xD0, "irq_off_done")
    # Mode 3 (Tale of Tape): VBlank R0/R1=$06EF, R2..R5=0
    a.emit(0xAD, 0xEF, 0x06)
    a.jsr("v_set_chr0")
    a.emit(0xA9, 0x00)
    a.jsr("v_set_chr1")
    # Opponent portrait (rows 7..15 = y 56..127 in $2000) is on screen only if ($10 & $02)==0 and $20 < 127
    a.emit(0xA5, 0x10, 0x29, 0x02)
    a.branch(0xD0, "m3_no_irq")
    a.emit(0xA5, 0x20, 0xC9, 127)
    a.branch(0xB0, "m3_no_irq")
    a.emit(0xC9, 54)
    a.branch(0xB0, "m3_top_clip")
    a.emit(0xA9, 73, 0x8D, V_TMP_Y & 0xFF, V_TMP_Y >> 8)
    a.emit(0xA9, 53, 0x38, 0xE5, 0x20)    # 1 line early setup IRQ at sl = 54 - $20
    a.branch(0xB0, "arm_latch")
    a.label("m3_top_clip")
    a.emit(0xA9, 127, 0x38, 0xE5, 0x20)   # lines from sl=1..127-$20
    a.branch(0xF0, "m3_no_irq")
    a.emit(0x8D, V_TMP_Y & 0xFF, V_TMP_Y >> 8)
    a.emit(0xA9, 0x00)                    # setup IRQ at sl = 0
    a.branch(0xF0, "arm_latch")
    a.label("m3_no_irq")
    a.emit(0x60)

    a.label("arm_latch")
    a.emit(0x8D, 0x00, 0xC0)              # STA $C000
    a.emit(0x8D, 0x01, 0xC0)              # STA $C001 (reload)
    a.emit(0x8D, 0x01, 0xE0)              # STA $E001 (enable IRQ)
    a.emit(0x60)

    # ---- v_nmi_hook (NMI vector $FFFA): disables IRQ during VBlank, Start+Select 60f check ----
    a.label("v_nmi_hook")
    a.emit(0x48, 0x8A, 0x48, 0x98, 0x48)  # PHA; TXA; PHA; TYA; PHA
    a.emit(0x8D, 0x00, 0xE0)              # STA $E000 (ack/disable IRQ during VBlank)
    # Read controller 1 ($4016) for Start ($10) + Select ($20) = $30
    a.emit(0xA9, 0x01, 0x8D, 0x16, 0x40)
    a.emit(0xA9, 0x00, 0x8D, 0x16, 0x40)
    a.emit(0x8D, V_TMP_A & 0xFF, V_TMP_A >> 8)
    a.emit(0xA2, 0x08)
    a.label("nmi_pad_lp")
    a.emit(0xAD, 0x16, 0x40)
    a.emit(0x4A)                          # LSR A (bit 0 -> C)
    a.emit(0x2E, V_TMP_A & 0xFF, V_TMP_A >> 8)  # ROL V_TMP_A
    a.emit(0xCA)
    a.branch(0xD0, "nmi_pad_lp")
    # Bit order shifted MSB-first: A, B, Select, Start, Up, Down, Left, Right -> Select=$20, Start=$10!
    a.emit(0xAD, V_TMP_A & 0xFF, V_TMP_A >> 8)
    a.emit(0x29, 0x30, 0xC9, 0x30)
    a.branch(0xD0, "nmi_pad_rst")
    a.emit(0xEE, V_HOLD_CNT & 0xFF, V_HOLD_CNT >> 8)
    a.emit(0xAD, V_HOLD_CNT & 0xFF, V_HOLD_CNT >> 8)
    a.emit(0xC9, 60)
    a.branch(0x90, "nmi_continue")
    a.emit(0xA9, 0x00, 0x8D, V_WIN_FLAG & 0xFF, V_WIN_FLAG >> 8)
    a.jmp("v_exit_trampoline")

    a.label("nmi_pad_rst")
    a.emit(0xA9, 0x00, 0x8D, V_HOLD_CNT & 0xFF, V_HOLD_CNT >> 8)
    a.label("nmi_continue")
    a.emit(0x68, 0xA8, 0x68, 0xAA, 0x68)  # PLA; TAY; PLA; TAX; PLA
    a.emit(0x4C, MTPO_ORIG_NMI & 0xFF, MTPO_ORIG_NMI >> 8)

    # ---- v_irq_handler (IRQ vector $FFFE) ----
    a.label("v_irq_handler")
    a.emit(0x48, 0x8A, 0x48, 0x98, 0x48)  # PHA; TXA; PHA; TYA; PHA
    a.emit(0x8D, 0x00, 0xE0)              # STA $E000 (ack IRQ)
    a.emit(0xAD, V_MODE & 0xFF, V_MODE >> 8)
    a.emit(0xC9, 0x03)
    a.branch(0xD0, "irq_not_m3")
    a.jmp("irq_m3_entry")
    a.label("irq_not_m3")
    a.emit(0xC9, 0x04)
    a.branch(0xD0, "irq_not_fight")
    # Fight mode (sl=95): switch R2..R5 to $69 (Barba/Mario CHR1 bank)
    a.emit(0xA5, 0x69)
    a.jsr("v_set_chr1")
    a.jmp("irq_done")

    a.label("irq_not_fight")
    a.emit(0xAD, V_MODE & 0xFF, V_MODE >> 8)
    a.emit(0xC9, 0x01)
    a.branch(0xD0, "irq_chk_m2")
    # Mode 1 (Title): step 0 -> Bank 4 (sl=47, next 79), step 1 -> Bank 0 (sl=127, next 71), step 2 -> Bank 4 (sl=199, stop)
    a.emit(0xAD, V_IRQ_STEP & 0xFF, V_IRQ_STEP >> 8)
    a.branch(0xD0, "m1_s12")
    a.emit(0xA9, 0x04)
    a.jsr("v_set_chr1")
    a.emit(0xEE, V_IRQ_STEP & 0xFF, V_IRQ_STEP >> 8)
    a.emit(0xA9, 79)
    a.jmp("irq_rearm")
    a.label("m1_s12")
    a.emit(0xC9, 0x01)
    a.branch(0xD0, "m1_s2")
    a.emit(0xA9, 0x00)
    a.jsr("v_set_chr1")
    a.emit(0xEE, V_IRQ_STEP & 0xFF, V_IRQ_STEP >> 8)
    a.emit(0xA9, 71)
    a.jmp("irq_rearm")
    a.label("m1_s2")
    a.emit(0xA9, 0x04)
    a.jsr("v_set_chr1")
    a.jmp("irq_done")

    a.label("irq_chk_m2")
    a.emit(0xC9, 0x02)
    a.branch(0xF0, "m2_go")
    a.jmp("irq_done")
    a.label("m2_go")
    # Mode 2: step 0 (sl=141) -> R0/R1=Bank 4 ("EVIL LINK" logo), rearm 30 (sl=172); step 1 -> R2..R4=0, keep R5=31
    a.emit(0xAD, V_IRQ_STEP & 0xFF, V_IRQ_STEP >> 8)
    a.branch(0xD0, "m2_s1")
    a.emit(0xA9, 0x04)
    a.jsr("v_set_chr0")
    a.emit(0xEE, V_IRQ_STEP & 0xFF, V_IRQ_STEP >> 8)
    a.emit(0xA9, 30)
    a.jmp("irq_rearm")
    a.label("m2_s1")
    for r, b in ((2, 0), (3, 1), (4, 2)):
        a.emit(0xA9, r, 0x8D, 0x00, 0x80, 0xA9, b, 0x8D, 0x01, 0x80)
    a.emit(0xAD, V_MMC3_SEL & 0xFF, V_MMC3_SEL >> 8, 0x8D, 0x00, 0x80)
    a.jmp("irq_done")

    a.label("irq_m3_entry")
    # Mode 3 (Tale of the Tape): 3-scanline MMC3-resynced H-split to eliminate DPCM jitter
    a.emit(0xAD, V_IRQ_STEP & 0xFF, V_IRQ_STEP >> 8)
    a.branch(0xD0, "m3_run_slice")
    # Step 0 (1 line before portrait start): arm next sl ($C000=0), configure R3..R5 = $06EE
    a.emit(0xEE, V_IRQ_STEP & 0xFF, V_IRQ_STEP >> 8)
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0xC0, 0x8D, 0x01, 0xC0, 0x8D, 0x01, 0xE0)
    a.emit(0xAD, 0xEE, 0x06, 0x0A, 0x0A)        # A = $06EE * 4 (p0)
    a.emit(0x8D, V_TMP_X & 0xFF, V_TMP_X >> 8)
    for r in (3, 4, 5):
        a.emit(0x18, 0x69, 0x01, 0x48, 0xA9, r, 0x8D, 0x00, 0x80, 0x68, 0x8D, 0x01, 0x80)
    a.jmp("irq_done")

    a.label("m3_run_slice")
    # Single-pass H-split loop for all V_TMP_Y scanlines.
    # Base entry puts first STX $8001 at sl=54 dot=5; wait 43 cyc (129 dots) -> dot ~134 (col 16.75, 3 tiles before col 20).
    a.emit(0xA9, 0x06)                          # LDA #6 (2)
    a.label("tape_w1")
    a.emit(0x38, 0xE9, 0x01)
    a.branch(0xD0, "tape_w1")                   # 6*7-1 = 41 cyc -> 43 cyc
    a.emit(0xAC, V_TMP_Y & 0xFF, V_TMP_Y >> 8)  # Y = remaining scanlines (1..74)
    a.emit(0xAE, V_TMP_X & 0xFF, V_TMP_X >> 8)  # X = p0
    a.emit(0xA9, 0x02, 0x8D, 0x00, 0x80)        # preselect R2
    a.label("tape_h_lp")
    a.emit(0x8E, 0x01, 0x80)                    # STX $8001 (R2 = p0 at dot ~134) (4)
    a.emit(0xA9, 0x05)                          # LDA #5 (2)
    a.label("tape_w2")
    a.emit(0x38, 0xE9, 0x01)
    a.branch(0xD0, "tape_w2")                   # 5*7-1 = 34 cyc -> +6 = 42 cyc (126 dots -> dot ~260, HBlank)
    a.emit(0xA9, 0x00, 0x8D, 0x01, 0x80)        # R2 = 0 (6 cyc)
    a.emit(0x88)                                # DEY (2)
    a.branch(0xF0, "tape_slice_done")           # BEQ (2 not taken, 3 taken)
    # 113.75 cyc/line average (113 when Y&3==0, 114 otherwise) -> 341.25 dots/line
    a.emit(0x98, 0x29, 0x03)                    # TYA; AND #$03 (4)
    a.branch(0xF0, "tape_skip_nop")             # BEQ: 3 taken (113), 2 not taken (+NOP=114)
    a.emit(0xEA)                                # NOP (2)
    a.label("tape_skip_nop")
    a.emit(0xA9, 0x07)                          # LDA #7 (2)
    a.label("tape_w3")
    a.emit(0x38, 0xE9, 0x01)
    a.branch(0xD0, "tape_w3")                   # 7*7-1 = 48 cyc
    a.emit(0x24, 0x00)                          # BIT $00 (3 cyc) -> total 113|114 cyc/line
    a.branch(0xB0, "tape_h_lp")                 # BCS always taken (3)
    a.label("tape_slice_done")
    a.emit(0xA9, 0x00)
    a.jsr("v_set_chr1")
    a.emit(0xA9, 0x05)
    a.jsr("v_set_chr0")
    a.jmp("irq_done")

    a.label("irq_rearm")
    a.emit(0x8D, 0x00, 0xC0)              # STA $C000
    a.emit(0x8D, 0x01, 0xC0)              # STA $C001
    a.emit(0x8D, 0x01, 0xE0)              # STA $E001
    a.label("irq_done")
    a.emit(0xAD, V_MMC3_SEL & 0xFF, V_MMC3_SEL >> 8)
    a.emit(0x8D, 0x00, 0x80)              # restore $8000
    a.emit(0x68, 0xA8, 0x68, 0xAA, 0x68)  # PLA; TAY; PLA; TAX; PLA
    a.emit(0x40)                          # RTI

    # ---- Sampled Barba Roar hooks ----
    # v_roar_dpcm (Bank 8 $8054): Y = sample ID; if Y==$0A play Barba roar at rate 9 for 60 frames
    a.label("v_roar_dpcm")
    a.emit(0xC0, 0x0A)                    # CPY #$0A
    a.branch(0xF0, "do_barba_roar")
    # Vanilla Bank 8 $8054..$806F
    a.emit(0x98, 0x0A, 0xA8)              # TYA; ASL A; TAY
    a.emit(0xB9, 0x66, 0xF7, 0x8D, 0x12, 0x40)  # LDA $F766,Y; STA $4012
    a.emit(0xB9, 0x67, 0xF7, 0x8D, 0x13, 0x40)  # LDA $F767,Y; STA $4013
    a.emit(0xA2, 0x4F, 0xA5, 0xF7, 0xC9, 0x01)
    a.branch(0xF0, "dpcm_set_rate")
    a.emit(0xA2, 0x0F)
    a.label("dpcm_set_rate")
    a.emit(0x8E, 0x10, 0x40)              # STX $4010
    a.emit(0x60)

    a.label("do_barba_roar")
    a.emit(0xA9, (ROAR_DMC_ADDR - 0xC000) >> 6, 0x8D, 0x12, 0x40)  # $E2 -> $4012
    a.emit(0xA9, roar_len_reg, 0x8D, 0x13, 0x40)                   # len -> $4013
    a.emit(0xA9, ROAR_DMC_RATE, 0x8D, 0x10, 0x40)                  # rate 9 -> $4010
    a.emit(0xA9, 60, 0x8D, 0x1E, 0x07, 0x8D, 0x1F, 0x07)           # 60-frame duration
    a.emit(0x60)

    # Trigger helpers
    a.label("v_star_roar")
    a.emit(0xA9, 0xFF, 0x8D, 0x41, 0x03)  # STA $0341
    a.emit(0xA9, 0x0A, 0x85, 0xF3)        # LDA #$0A; STA $F3
    a.emit(0x60)

    a.label("v_round_roar")
    a.emit(0xA9, 0x0A, 0x85, 0xF3)        # LDA #$0A; STA $F3
    a.emit(0xA9, 0x01, 0xA4, 0x06)        # LDA #$01; LDY $06 (vanilla $A8FF)
    a.emit(0x60)

    a.label("v_kd_roar")
    a.emit(0xEE, 0xC0, 0x03)              # INC $03C0 (vanilla $A952)
    a.emit(0xA9, 0x0A, 0x85, 0xF3)        # LDA #$0A; STA $F3
    a.emit(0x60)

    # ---- v_win_hook (hooked at $AC6C when Champ Evil Link is beaten) ----
    a.label("v_win_hook")
    a.emit(0xA9, 0x01, 0x8D, V_WIN_FLAG & 0xFF, V_WIN_FLAG >> 8)

    # ---- v_exit_trampoline: silences PPU/APU/IRQ, writes reward_addr if won, runs $0300 exit ----
    a.label("v_exit_trampoline")
    a.emit(0x78)                          # SEI
    a.emit(0xA9, 0x00)
    a.emit(0x8D, 0x00, 0x20)              # PPUCTRL = 0
    a.emit(0x8D, 0x01, 0x20)              # PPUMASK = 0
    a.emit(0x8D, 0x00, 0xE0)              # disable MMC3 IRQ
    a.emit(0x8D, 0x15, 0x40)              # silence APU + DPCM
    a.emit(0xAD, V_WIN_FLAG & 0xFF, V_WIN_FLAG >> 8)
    a.branch(0xF0, "skip_reward")
    a.emit(0xA9, 0xA0, 0x8D, 0x01, 0xA0)  # WRAM bank 0
    a.emit(0xA9, 0x4D, 0x8D, reward_addr & 0xFF, reward_addr >> 8)  # set reward!
    a.label("skip_reward")
    # Ensure FK23C $5FF0-$5FF3 writes are unlocked before $0300 runs
    a.emit(0xA9, 0x80, 0x8D, 0x01, 0xA0)
    a.emit(0xA2, 0x00)
    a.label("copy_exit_lp")
    a.lda_abs_x("exit_ram_code")
    a.emit(0x9D, 0x00, 0x03)              # STA $0300,X
    a.emit(0xE8)
    a.emit(0xE0, 0x00)                    # placeholder length patched after finish
    len_patch_off = len(a.buf) - 1
    a.branch(0x90, "copy_exit_lp")
    a.emit(0x4C, 0x00, 0x03)              # JMP $0300

    # Relocatable $0300 trampoline returning to Barba (combined mode) or restore_addr
    exit_start = len(a.buf)
    a.label("exit_ram_code")
    a.emit(0xA9, 0x01, 0x8D, 0xF0, 0x5F)  # $5FF0 = $01
    a.emit(0xA9, 0x00, 0x8D, 0xF1, 0x5F, 0x8D, 0xF2, 0x5F)  # $5FF1 = 0, $5FF2 = 0
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x0C, 0x8D, 0x01, 0x80)  # R6 = $0C
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x0D, 0x8D, 0x01, 0x80)  # R7 = $0D
    a.emit(0xA9, 0xA0, 0x8D, 0x01, 0xA0)  # WRAM bank 0 ($A0)
    a.emit(0x4C, restore_addr & 0xFF, restore_addr >> 8)
    exit_len = len(a.buf) - exit_start

    a.buf[len_patch_off] = exit_len
    raw = a.finish()
    if B14_CODE_BASE + len(raw) > 0xE000:
        raise ValueError(f"Bank 14 runtime overflow: ${B14_CODE_BASE + len(raw):04X} > $E000")
    return raw, a.labels


def patch_mtpo(
    mtpo_bytes: bytes,
    restore_addr: int,
    *,
    reward_addr: int = 0x63BA,
    z2_bytes: bytes | None = None,
    standalone_stub: bool = False,
) -> tuple[bytes, bytes]:
    """Port and mod Mike Tyson's Punch-Out!! -> Barba's Punch-Out!! (256KB PRG, 128KB CHR)."""
    if len(mtpo_bytes) != MTPO_TOTAL_SIZE:
        raise ValueError(f"Unexpected MTPO ROM size: {len(mtpo_bytes)} != {MTPO_TOTAL_SIZE}")

    prg_in = bytearray(mtpo_bytes[MTPO_HDR_SIZE : MTPO_HDR_SIZE + MTPO_PRG_SIZE])
    chr_out = bytearray(mtpo_bytes[MTPO_HDR_SIZE + MTPO_PRG_SIZE : MTPO_TOTAL_SIZE])

    # Load Z2 fallback if available (unused if art is pure procedural, kept for signature contract)
    if z2_bytes is None:
        z2_default = Path(__file__).resolve().parent.parent / "roms" / "z2.nes"
        if z2_default.is_file():
            z2_bytes = z2_default.read_bytes()

    # 1. Apply Barba / Title / Evil Link / Z2 Opponent art & text mods
    apply_mtpo_mod_art(prg_in, chr_out, z2_bytes)

    # 2. Generate Barba sampled roar DMC into build/subgames/mtpo_roar/
    roar_dir = Path(__file__).resolve().parent.parent / "build" / "subgames" / "mtpo_roar"
    roar_wav = Path(__file__).resolve().parent.parent / "assets" / "roar.wav"
    roar_dmc, roar_meta = roar_sample.convert_soft(
        roar_wav, roar_dir, rate_index=ROAR_DMC_RATE, max_bytes=1537, amplitude=34
    )
    roar_len_reg = int(roar_meta["length_reg"])

    # 3. Assemble Bank 14 runtime
    b14_runtime, lbl = _assemble_bank14_runtime(restore_addr, reward_addr, roar_len_reg)

    # Place Bank 14 runtime at $D860..$DFFF (verify all $00)
    b14_base = 14 * 8192
    _patch_slice(prg_in, b14_base, B14_CODE_BASE, b14_runtime, b"\x00" * len(b14_runtime), "B14 runtime")

    # Place Barba roar DMC at Bank 15 $F880.. (verify all $00)
    b15_base = 15 * 8192
    _patch_slice(prg_in, b15_base, ROAR_DMC_ADDR, roar_dmc, b"\x00" * len(roar_dmc), "B15 roar DMC")

    # 4. Guarded patches in Bank 8, Bank 11, Bank 13, Bank 15
    def p8(addr: int, new: bytes, exp: bytes, name: str) -> None:
        _patch_slice(prg_in, 8 * 8192, addr, new, exp, name)

    def p11(addr: int, new: bytes, exp: bytes, name: str) -> None:
        _patch_slice(prg_in, 11 * 8192, addr, new, exp, name)

    def p13(addr: int, new: bytes, exp: bytes, name: str) -> None:
        _patch_slice(prg_in, 13 * 8192, addr, new, exp, name)

    def p15(addr: int, new: bytes, exp: bytes, name: str) -> None:
        _patch_slice(prg_in, 15 * 8192, addr, new, exp, name)

    def jsr(target_name: str) -> bytes:
        t = lbl[target_name]
        return bytes([0x20, t & 0xFF, t >> 8])

    def jmp(target_name: str) -> bytes:
        t = lbl[target_name]
        return bytes([0x4C, t & 0xFF, t >> 8])

    # Bank 8: DPCM roar playback hook ($8054..$806F = 28 bytes)
    p8(
        0x8054,
        jsr("v_roar_dpcm") + b"\xEA" * 25,
        bytes.fromhex("980aa8b966f78d1240b967f78d1340a24fa5f7c901f002a20f8e1040"),
        "B08 roar DPCM",
    )

    # Bank 11: Star Punch roar hooks
    p11(0x8171, jsr("v_star_roar") + b"\xEA\xEA", bytes.fromhex("a9ff8d4103"), "B11 star punch 1")
    p11(0x825B, jsr("v_star_roar") + b"\xEA\xEA", bytes.fromhex("a9ff8d4103"), "B11 star punch 2")

    # Bank 13: MMC2 -> MMC3 virtualization + boot/RNG/IRQ/roar/win hooks
    p13(0xA037, jmp("v_sound_nmi_end"), bytes.fromhex("4cdfa6"), "B13 sound NMI IRQ arm")
    p13(0xA28B, jsr("v_post_wipe_init"), bytes.fromhex("2002af"), "B13 RNG seed + CLI")
    p13(0xA5D7, jsr("v_fight_chr0"), bytes.fromhex("8d00c0"), "B13 fight CHR0")
    p13(0xA5E7, b"\xEA\xEA\xEA", bytes.fromhex("8d00e0"), "B13 nop fight $E000")
    p13(0xA64F, jsr("v_fight_cli"), bytes.fromhex("201280"), "B13 fight CLI")
    p13(0xA8FF, jsr("v_round_roar") + b"\xEA", bytes.fromhex("a901a406"), "B13 round roar")
    p13(0xA952, jsr("v_kd_roar"), bytes.fromhex("eec003"), "B13 knockdown/KO roar")
    p13(0xA9E6, b"\x8D\x00\xA0", bytes.fromhex("8d00f0"), "B13 MMC3 mirroring")
    p13(0xAA02, jmp("v_arm_irq") + b"\xEA", bytes.fromhex("8d002060"), "B13 VBlank end IRQ arm")
    p13(0xAA4A, jsr("v_prg_switch") + b"\xEA\xEA\x60", bytes.fromhex("8dffaf850d60"), "B13 PRG switch")
    p13(0xAC6C, jmp("v_win_hook"), bytes.fromhex("4caca2"), "B13 Champ win hook")
    p13(0xB679, b"\xEA\xEA\xEA", bytes.fromhex("8e00b0"), "B13 Title CHR0 nop")
    p13(0xB90F, jsr("v_b90f_chr0"), bytes.fromhex("8d00b0"), "B13 Belt CHR0")
    p13(
        0xBD03,
        jsr("v_tape_chr") + b"\xEA" * 21,
        bytes.fromhex("a9008d00d0adee068d00e0a9058d00b0adef068d00c085a9"),
        "B13 Tale of the Tape CHR",
    )
    p13(
        0xBF55,
        jsr("v_bf55") + b"\xEA" * 13,
        bytes.fromhex("8d00e0a9008d00d08e00b08e00c086a9"),
        "B13 BF55 CHR",
    )

    # Bank 15 vectors ($FFFA = v_nmi_hook, $FFFE = v_irq_handler)
    nmi_addr = lbl["v_nmi_hook"]
    irq_addr = lbl["v_irq_handler"]
    p15(0xFFFA, bytes([nmi_addr & 0xFF, nmi_addr >> 8]), bytes([MTPO_ORIG_NMI & 0xFF, MTPO_ORIG_NMI >> 8]), "NMI vec")
    p15(0xFFFE, bytes([irq_addr & 0xFF, irq_addr >> 8]), bytes([MTPO_ORIG_IRQ & 0xFF, MTPO_ORIG_IRQ >> 8]), "IRQ vec")

    if standalone_stub:
        a = Asm6502(STANDALONE_BOOT_STUB)
        a.emit(0x78, 0xD8)                                # SEI; CLD
        a.emit(0xA9, 0x80, 0x8D, 0x01, 0xA0)              # unlock $5FF0-$5FF3
        a.emit(0xA9, 0x01, 0x8D, 0xF0, 0x5F)              # $5FF0 = $01 (standalone MMC3 CHR-ROM)
        a.emit(0xA9, 0x00, 0x8D, 0xF1, 0x5F, 0x8D, 0xF2, 0x5F)
        a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x00, 0x8D, 0x01, 0x80)  # R6 = 0
        a.emit(0x4C, 0x00, 0x80)                          # JMP $8000
        stub = a.finish()
        assert STANDALONE_BOOT_STUB + len(stub) <= STANDALONE_RESTORE_ADDR
        p15(STANDALONE_BOOT_STUB, stub, b"\x00" * len(stub), "standalone stub")
        p15(
            STANDALONE_RESTORE_ADDR,
            bytes([0x4C, STANDALONE_RESTORE_ADDR & 0xFF, STANDALONE_RESTORE_ADDR >> 8]),
            b"\x00\x00\x00",
            "standalone restore",
        )
        p15(
            0xFFFC,
            bytes([STANDALONE_BOOT_STUB & 0xFF, STANDALONE_BOOT_STUB >> 8]),
            bytes([MTPO_ORIG_RESET & 0xFF, MTPO_ORIG_RESET >> 8]),
            "standalone RST vec",
        )

    # Assemble 256KB PRG:
    #   Bank 0      : boot bank ($8000)
    #   Banks 1..13 : MTPO PRG banks 0..12
    #   Banks 14..28: $FF padding
    #   Banks 29..31: MTPO fixed banks 13..15 ($A000-$FFFF)
    prg_out = bytearray(b"\xFF" * PRG_OUT_SIZE)
    prg_out[0:8192] = _assemble_bank0_boot()
    prg_out[8192 : 14 * 8192] = prg_in[0 : 13 * 8192]
    prg_out[29 * 8192 : 32 * 8192] = prg_in[13 * 8192 : 16 * 8192]

    return bytes(prg_out), bytes(chr_out)


def build_standalone(
    out_path: Path,
    mtpo_path: Path = Path("roms/mtpo.nes"),
    z2_path: Path = Path("roms/z2.nes"),
) -> Path:
    """Build standalone NES 2.0 Mapper 176 ROM at out_path."""
    mtpo_bytes = mtpo_path.read_bytes()
    z2_bytes = z2_path.read_bytes() if z2_path.is_file() else None
    prg_out, chr_out = patch_mtpo(
        mtpo_bytes,
        restore_addr=STANDALONE_RESTORE_ADDR,
        reward_addr=0x63BA,
        z2_bytes=z2_bytes,
        standalone_stub=True,
    )
    assert len(prg_out) == PRG_OUT_SIZE
    assert len(chr_out) == CHR_OUT_SIZE

    hdr = bytearray(16)
    hdr[0:4] = b"NES\x1a"
    hdr[4] = 16     # 16 * 16KB = 256KB PRG
    hdr[5] = 16     # 16 * 8KB = 128KB CHR-ROM
    hdr[6] = 0x02   # Vertical mirroring + battery
    hdr[7] = 0xB8   # NES 2.0 + Mapper 176
    hdr[10] = 0x90  # 32KB battery PRG-RAM

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(hdr) + prg_out + chr_out)
    return out_path


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    out = build_standalone(
        root / "build" / "subgames" / "mtpo.nes",
        root / "roms" / "mtpo.nes",
        root / "roms" / "z2.nes",
    )
    print(f"Built {out} ({out.stat().st_size} bytes)")
