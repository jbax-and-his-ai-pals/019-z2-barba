"""WRAM ($7B00-$7DFF) trampolines, CHR-RAM bank sync, palette fixups, and idle animations."""
from __future__ import annotations

from feud_engine import (
    CELEB_WRAM_ORG,
    FeudAsm,
    W_AMB_ROAR_ON,
    W_AMB_TMR_HI,
    W_AMB_TMR_LO,
    W_BLK_A_HI,
    W_BLK_A_LO,
    W_BLK_DYN,
    W_BLK_T_HI,
    W_BLK_T_LO,
    W_CELEB_ACTIVE,
    W_CELEB_DELAY,
    W_CELEB_HOLD,
    W_CELEB_POSE,
    W_CELEB_RNG,
    W_CELEB_STEP,
    W_CHR_MODE,
    W_CPU_FO_ATTR,
    W_CPU_OV_ATTR,
    W_CPU_PAL_CLR,
    W_CPU_ST_ATTR,
    W_CUR_CHR0,
    W_CUR_CHR1,
    W_FO_COLORS,
    W_IDLE_HOLD,
    W_IDLE_POSE,
    W_IDLE_REP,
    W_IDLE_SEAT,
    W_IDLE_TIMER,
    W_IDLE_VIEW,
    W_JMP_HI,
    W_JMP_LO,
    W_LAST_ST_SEAT,
    W_OV_HOLD,
    W_P1_OV_ATTR,
    W_P1_PAL_CLR,
    W_P1_ST_ATTR,
    W_ROAR_GAP,
    W_ROAR_LAST_R,
    W_ROAR_LEFT,
    W_ROAR_MIN,
    W_ROAR_SEAT_Q,
    W_SAVE_0C,
    W_SAVE_0D,
    W_SHAKE_IDX,
    W_SHAKE_X,
    W_ST_CUR,
    W_ST_HOLD,
    W_ST_REP,
    W_ST_TGT,
    W_TMP0,
    W_TMP1,
    W_TMP3,
    WRAM_EXTRA_ORG,
)


def _assemble_wram_part1(a: FeudAsm) -> None:
    """Emit W_CALL_B4, W_SYNC_CHR, block routers, and attribute writers."""
    # Tables (16 bytes CHR->RAM slot map + PPU X coords for Stage Close-Up & Overview)
    a.label('TBL_CHR_TO_RAM')
    # Logical Feud CHR -> CHR-RAM slot 0..7 (00->0, 0B->1, 02->2, 03->3, 05->4, 06->5, 0C->6, 09->7)
    a.emit(0, 0, 2, 3, 0, 4, 5, 0, 0, 7, 0, 1, 6, 0, 0, 0)

    a.label('TBL_ST_P1_X');  a.emit(22, 18, 10, 14, 6)
    a.label('TBL_ST_CPU_X'); a.emit(6, 10, 18, 14, 22)
    a.label('TBL_OV_X');     a.emit(10, 8, 6, 4, 2, 20, 22, 24, 26, 28)
    a.label('TBL_OV_IDLE');  a.emit(143, 144, 145, 146, 147, 152, 151, 150, 149, 148)
    a.label('TBL_OV_ROAR');  a.emit(128, 129, 130, 131, 132, 138, 139, 140, 141, 142)

    # ---- W_CALL_B4(A = entry offset in Bank 4 $8900) ----
    a.label('W_CALL_B4')
    a.op16(0x8D, W_JMP_LO)
    a.abs_ref(0x20, '_w_amb_stop')
    a.label('_cb4_no_amb')
    a.emit(0xA9, 0x89); a.op16(0x8D, W_JMP_HI)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x04, 0x8D, 0x01, 0x80)
    a.abs_ref(0x20, '_w_ind_jmp')
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x00, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x01, 0x8D, 0x01, 0x80)
    a.abs_ref(0x20, 'W_SYNC_CHR')
    a.emit(0x60)
    a.label('_w_ind_jmp')
    a.emit(0x6C); a.u16(W_JMP_LO)

    # ---- W_SYNC_CHR: programs $5FF0 + MMC3 R0/R1 fast (<60c) then R2..R5 ----
    a.label('W_SYNC_CHR')
    a.emit(0x08, 0x78, 0x48, 0x8A, 0x48, 0x98, 0x48)  # PHP; SEI; PHA; TXA; PHA; TYA; PHA
    # Decide RAM vs ROM from W_CUR_CHR0
    a.op16(0xAD, W_CUR_CHR0)
    a.branch(0xD0, 'sc_not00')
    a.emit(0xAD, 0x45, 0x03, 0xC9, 0x11)  # skip RAM if unused Scr 17
    a.branch(0xF0, 'sc_use_rom')
    a.branch(0xD0, 'sc_use_ram')
    a.label('sc_not00')
    a.emit(0xC9, 0x05); a.branch(0xF0, 'sc_use_ram')
    a.emit(0xC9, 0x06); a.branch(0xF0, 'sc_use_ram')
    a.emit(0xC9, 0x0B); a.branch(0xD0, 'sc_chk_fo')
    a.emit(0xAD, 0xD3, 0x04, 0xC9, 0x03)  # $0B uses RAM only in Fast Money ($04D3==3)
    a.branch(0xF0, 'sc_use_ram')
    a.branch(0xD0, 'sc_use_rom')
    a.label('sc_chk_fo')
    a.emit(0xC9, 0x02); a.branch(0xF0, 'sc_is_fo')
    a.emit(0xC9, 0x03); a.branch(0xD0, 'sc_use_rom')
    a.label('sc_is_fo')
    a.emit(0xAD, 0xD3, 0x04, 0xC9, 0x02)  # $02/$03 use RAM only in Face-Off ($04D3==2)
    a.branch(0xF0, 'sc_use_ram')

    a.label('sc_use_rom')
    a.emit(0xA9, 0x01, 0x48)
    a.op16(0xAD, W_CUR_CHR0); a.emit(0x29, 0x1F)
    a.branch(0x10, '_sc_do_r0')  # always positive (0..31)

    a.label('sc_use_ram')
    a.emit(0xA9, 0x21, 0x48)
    a.op16(0xAD, W_CUR_CHR0); a.emit(0x29, 0x0F, 0xAA); a.abs_ref(0xBD, 'TBL_CHR_TO_RAM')

    a.label('_sc_do_r0')
    a.emit(0x0A, 0x0A, 0xAA)
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80, 0xE8, 0xE8)
    a.emit(0xA9, 0x01, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80)
    a.emit(0x68, 0x8D, 0xF0, 0x5F)
    a.op16(0x8D, W_CHR_MODE)
    a.emit(0xC9, 0x21)
    a.branch(0xF0, '_sc_set_ram')
    a.op16(0xAD, W_CUR_CHR1); a.emit(0x29, 0x1F)
    a.branch(0x10, '_sc_set_chr1_exit')  # always positive (0..31)
    a.label('_sc_set_ram')
    a.op16(0xAD, W_CUR_CHR1); a.emit(0x29, 0x0F, 0xAA); a.abs_ref(0xBD, 'TBL_CHR_TO_RAM')

    a.label('_sc_set_chr1_exit')
    a.emit(0x0A, 0x0A, 0xAA, 0xA0, 0x02)
    a.label('_sc_r25_lp')
    a.emit(0x8C, 0x00, 0x80, 0x8E, 0x01, 0x80, 0xE8, 0xC8, 0xC0, 0x06)
    a.branch(0xD0, '_sc_r25_lp')
    a.label('sc_exit')
    a.emit(0x68, 0xA8, 0x68, 0xAA, 0x68, 0x28, 0x60)

    # ---- Ambient soft-roar helpers (shared across W_CALL_B4, W_LOAD_BLK_AND_ATTR, W_NMI_IDLE_TICK) ----
    a.label('_w_stop_amb_if_on')
    a.emit(0xC0, 153); a.branch(0xB0, '_saio_ret')  # blocks >= 153 are intact in upper 256KB PRG
    a.label('_w_amb_stop')
    a.op16(0xAD, W_AMB_ROAR_ON); a.branch(0xF0, '_saio_ret')
    a.op16(0xAD, CELEB_WRAM_ORG); a.emit(0xC9, 0x4C); a.branch(0xD0, '_saio_ret')
    a.op16(0x4C, CELEB_WRAM_ORG + 3)
    a.label('_saio_ret')
    a.emit(0x60)

    a.label('_w_amb_maybe')
    a.op16(0xAD, W_AMB_ROAR_ON); a.branch(0xD0, '_wam_zero')
    a.op16(0xAD, CELEB_WRAM_ORG); a.emit(0xC9, 0x4C); a.branch(0xD0, '_wam_zero')
    a.op16(0x4C, CELEB_WRAM_ORG + 6)
    a.label('_wam_zero')
    a.emit(0xA9, 0x00, 0x60)

    a.label('_w_amb_tick9')
    a.op16(0xAD, CELEB_WRAM_ORG); a.emit(0xC9, 0x4C); a.branch(0xD0, '_saio_ret')
    a.op16(0x4C, CELEB_WRAM_ORG + 9)

    a.label('W_LOAD_BLK_AND_ATTR')
    a.op16(0xB9, W_BLK_DYN)
    a.branch(0xD0, 'lba_dyn')
    a.abs_ref(0x20, '_w_stop_amb_if_on')
    a.emit(0xB9, 0x12, 0xDB, 0x85, 0x19, 0xB9, 0xDF, 0xDB, 0x85, 0x1A)
    a.emit(0xB9, 0x18, 0xF2, 0x85, 0x1B, 0xB9, 0xE5, 0xF2, 0x85, 0x1C, 0x60)
    a.label('lba_dyn')
    a.op16(0xB9, W_BLK_T_LO); a.emit(0x85, 0x19)
    a.op16(0xB9, W_BLK_T_HI); a.emit(0x85, 0x1A)
    a.op16(0xB9, W_BLK_A_LO); a.emit(0x85, 0x1B)
    a.op16(0xB9, W_BLK_A_HI); a.emit(0x85, 0x1C, 0x60)

    a.label('W_LOAD_BG_BLK')
    a.op16(0xB9, W_BLK_DYN)
    a.branch(0xD0, 'lbb_dyn')
    a.abs_ref(0x20, '_w_stop_amb_if_on')
    a.emit(0xB9, 0x12, 0xDB, 0x85, 0x45, 0xB9, 0xDF, 0xDB, 0x85, 0x46, 0x60)
    a.label('lbb_dyn')
    a.op16(0xB9, W_BLK_T_LO); a.emit(0x85, 0x45)
    a.op16(0xB9, W_BLK_T_HI); a.emit(0x85, 0x46, 0x60)

    # ---- Stage Close-Up & Overview & Face-Off Attribute Writers ----
    a.label('W_WRITE_STAGE_ATTR')
    a.emit(0xA2, 0x00, 0xA4, 0x0B)
    a.branch(0xF0, '_wsa_go')
    a.emit(0xA2, 0x10)
    a.label('_wsa_go')
    a.emit(0xA0, 0x0E)
    a.label('_wsa_lp')
    a.op16(0xBD, W_P1_ST_ATTR); a.emit(0x8D, 0x07, 0x20, 0xE8, 0x88)
    a.branch(0xD0, '_wsa_lp'); a.emit(0x60)

    a.label('W_WRITE_OV_ATTR')
    a.emit(0xA9, 0xE0, 0xA2, 0x00)
    a.abs_ref(0x20, '_woa_3')
    a.emit(0xA9, 0xE5, 0xA2, 0x03)
    a.label('_woa_3')
    a.emit(0xA0, 0x23, 0x8C, 0x06, 0x20, 0x8D, 0x06, 0x20, 0xA0, 0x03)
    a.label('_woa_lp')
    a.op16(0xBD, W_P1_OV_ATTR)  # W_CPU_OV_ATTR == +3, W_CPU_FO_ATTR == +6
    a.emit(0x8D, 0x07, 0x20, 0xE8, 0x88)
    a.branch(0xD0, '_woa_lp')
    a.emit(0x60)

    a.label('W_FACEOFF_ATTR')
    a.emit(0xA9, 0x23, 0x8D, 0x06, 0x20, 0xA9, 0xDB, 0x8D, 0x06, 0x20)
    a.emit(0xA9, 0x40, 0x8D, 0x07, 0x20)  # preserve Host top-left Pal 1!
    a.emit(0xA2, 0x06, 0xA9, 0xDC)
    a.label('wfa_lp')
    a.emit(0x48); a.abs_ref(0x20, '_woa_3'); a.emit(0x68)
    a.emit(0x18, 0x69, 0x08, 0xC9, 0xF4); a.branch(0xD0, 'wfa_lp')
    a.emit(0x60)


PAL_WRAM_ORG = 0x7400  # 256 B ($7400-$74FF) palette fixups & VBlank extra


def assemble_pal_wram() -> tuple[bytes, dict[str, int]]:
    """Build palette fixup & VBlank extra routines at $7400-$74FF (copied from Bank 4 $9F00)."""
    a = FeudAsm(PAL_WRAM_ORG)
    # Fixed $7400 entry for W_LOAD_FACEOFF in wram_extra
    a.emit(0x4C); a.ref16('W_OAM_PAL_FIX')

    # Apply 12 contestant colors from W_P1_PAL_CLR (X=0) or W_CPU_PAL_CLR (X=6) into $032D+4..15
    a.label('_w_apply_pal_to_032D')
    a.emit(0xA0, 0x00)
    a.label('wap_lp')
    a.emit(0xA9, 0x16, 0x99, 0x31, 0x03)
    a.op16(0xBD, W_P1_PAL_CLR);     a.emit(0x99, 0x32, 0x03)
    a.op16(0xBD, W_P1_PAL_CLR + 1); a.emit(0x99, 0x33, 0x03)
    a.emit(0xA9, 0x0F, 0x99, 0x34, 0x03)
    a.emit(0xE8, 0xE8, 0xC8, 0xC8, 0xC8, 0xC8, 0xC0, 0x0C)
    a.branch(0xD0, 'wap_lp')
    a.emit(0x60)

    a.label('W_PAL_FIX_992E')
    a.emit(0xA0, 0x00)
    a.label('wp9_orig')
    a.emit(0xB1, 0x0E, 0x99, 0x2D, 0x03, 0xA9, 0x0F, 0x99, 0x1D, 0x03, 0xC8, 0xC0, 0x10)
    a.branch(0xD0, 'wp9_orig')
    a.label('wp9_sel')
    a.emit(0xA2, 0x00, 0xA5, 0x0B)
    a.branch(0xF0, 'wp9_apply')
    a.emit(0xA2, 0x06)
    a.label('wp9_apply')
    a.abs_ref(0x4C, '_w_apply_pal_to_032D')

    a.label('W_PAL_FIX_A307_WRAP')
    a.emit(0x20, 0xA9, 0xA3)
    a.label('W_PAL_FIX_A307')
    a.emit(0xAD, 0x45, 0x03)
    a.emit(0xC9, 0x06); a.branch(0xF0, 'wpa_st')
    a.emit(0xC9, 0x07); a.branch(0xF0, 'wpa_ov')
    a.emit(0xC9, 0x0D); a.branch(0xF0, 'wpa_st')
    a.emit(0xC9, 0x0E); a.branch(0xF0, 'wpa_st')
    a.emit(0xC9, 0x08); a.branch(0xF0, 'wpa_fo')
    a.emit(0xC9, 0x09); a.branch(0xF0, 'wpa_fo')
    a.emit(0xC9, 0x0A); a.branch(0xF0, 'wpa_fo')
    a.emit(0x60)

    a.label('wpa_st')
    a.abs_ref(0x20, 'wp9_sel')
    a.abs_ref(0x4C, '_w_sync_031d')
    a.label('wpa_ov')
    a.emit(0xA2, 0x00)
    a.abs_ref(0x20, '_w_apply_pal_to_032D')
    a.abs_ref(0x4C, '_w_sync_031d')

    a.label('wpa_fo')
    a.emit(0xA2, 0x0B)
    a.label('wpa_fo_lp')
    a.abs_ref(0xBD, 'TBL_FO_PAL_DEF'); a.emit(0x9D, 0x31, 0x03, 0xCA)
    a.branch(0x10, 'wpa_fo_lp')
    a.op16(0xAD, W_FO_COLORS + 2); a.emit(0x8D, 0x36, 0x03)
    a.op16(0xAD, W_FO_COLORS + 3); a.emit(0x8D, 0x37, 0x03)
    a.abs_ref(0x4C, '_w_sync_031d')
    a.label('TBL_FO_PAL_DEF')
    a.emit(0x16, 0x30, 0x26, 0x0F, 0x16, 0x00, 0x00, 0x0F, 0x16, 0x37, 0x17, 0x0F)

    a.label('_w_sync_031d')
    a.emit(0xAD, 0x41, 0x03)
    a.branch(0xD0, 'ws_done')
    a.emit(0xA2, 0x0F)
    a.label('ws_cp')
    a.emit(0xBD, 0x2D, 0x03, 0x9D, 0x1D, 0x03, 0xCA)
    a.branch(0x10, 'ws_cp')
    a.label('ws_done')
    a.emit(0x60)

    a.label('W_OAM_PAL_FIX')
    a.emit(0xAD, 0xD3, 0x04, 0xC9, 0x02)
    a.branch(0xD0, 'wof_done')
    a.emit(0xA9, 0x16, 0x85, 0x34)
    a.op16(0xAD, W_FO_COLORS);     a.emit(0x85, 0x35)
    a.op16(0xAD, W_FO_COLORS + 1); a.emit(0x85, 0x36)
    a.emit(0xA9, 0x0F, 0x85, 0x37)
    a.label('wof_done')
    a.emit(0x18, 0x60)

    a.label('W_LOAD_OAM_PAL')
    a.emit(0xA2, 0x0F)
    a.label('wlop_cp')
    a.emit(0xBD, 0xCF, 0xD1, 0x95, 0x30, 0xCA); a.branch(0x10, 'wlop_cp')
    a.abs_ref(0x4C, 'W_OAM_PAL_FIX')

    a.label('W_VBLANK_EXTRA')
    a.emit(0x20, 0xCD, 0xCF)
    a.emit(0xAD, 0xD3, 0x04, 0xC9, 0x01)
    a.branch(0xD0, 'vbe_done')
    a.emit(0xAD, 0xBD, 0x05)
    a.branch(0xF0, 'vbe_done')
    a.emit(0x20, 0x85, 0xDA)
    a.label('vbe_done')
    a.emit(0x60)

    raw = a.finish()
    assert len(raw) <= 0x0100, f'Pal WRAM overflow: {len(raw)} > 256'
    return raw, dict(a.labels)


def _assemble_wram_part2(a: FeudAsm) -> None:
    """Emit Bank 4 entry wrappers and idle roar/wiggle."""
    # ---- Bank 4 Entry Wrappers ----
    a.label('_w_call_b4_ppu_off')
    a.emit(0x48)
    a.emit(0xA5, 0x0D); a.op16(0x8D, W_SAVE_0D)
    a.emit(0xA5, 0x0C); a.op16(0x8D, W_SAVE_0C)
    a.branch(0x10, '_cbpo_off')
    a.emit(0x20, 0xC0, 0x99)
    a.label('_cbpo_off')
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20)
    a.emit(0x68); a.abs_ref(0x20, 'W_CALL_B4')
    a.op16(0xAD, W_SAVE_0D); a.emit(0x85, 0x0D)
    a.op16(0x2C, W_SAVE_0C); a.branch(0x10, '_cbpo_done')
    a.emit(0x20, 0xEF, 0xCA)
    a.label('_cbpo_done')
    a.emit(0x60)

    a.label('W_ROLL_BOTH')
    a.emit(0xA9, 3); a.abs_ref(0x4C, '_w_call_b4_ppu_off')

    a.label('W_ROLL_P1')
    a.emit(0xA9, 6); a.abs_ref(0x4C, '_w_call_b4_ppu_off')

    a.label('W_ROLL_CPU')
    a.emit(0xA9, 9); a.abs_ref(0x4C, '_w_call_b4_ppu_off')

    a.label('W_LOAD_FACEOFF')
    a.emit(0x20, 0x86, 0x84)
    a.emit(0xA9, 12); a.abs_ref(0x20, '_w_call_b4_ppu_off')
    a.op16(0x4C, PAL_WRAM_ORG)

    a.label('W_PICK_Z2_NAME')
    a.emit(0x24, 0x0C); a.branch(0x10, '_pzn_now')
    a.emit(0x20, 0xF9, 0xCA)
    a.label('_pzn_now')
    a.emit(0xA9, 15); a.abs_ref(0x4C, 'W_CALL_B4')

    a.label('W_DEFAULT_P1_NAME')
    a.emit(0xA5, 0x0B)
    a.branch(0xD0, 'dpn_done')
    a.emit(0xA2, 0x07)
    a.label('dpn_chk')
    a.emit(0xB5, 0x48, 0x29, 0x7F, 0xC9, 0x41)
    a.branch(0xD0, 'dpn_done')
    a.emit(0xCA); a.branch(0x10, 'dpn_chk')
    a.emit(0xA2, 0x04)
    a.label('dpn_cp')
    a.abs_ref(0xBD, 'TBL_DEF_BARBA'); a.emit(0x9D, 0x00, 0x03, 0xCA)
    a.branch(0x10, 'dpn_cp')
    a.label('dpn_done')
    a.emit(0x4C, 0xD5, 0x96)
    a.label('TBL_DEF_BARBA'); a.emit(0x42, 0x41, 0x52, 0x42, 0xC1)

    a.label('W_ZELDA_LOSE')
    a.emit(0xA2, 0x00, 0x8E, 0xA1, 0x05, 0x8E, 0x44, 0x03, 0x86, 0x1F)
    a.emit(0xA9, 0x0F, 0x20, 0x07, 0xA3)
    a.emit(0xA9, 18); a.abs_ref(0x20, 'W_CALL_B4')
    a.emit(0x4C, 0x7B, 0xC9)

    # ---- Idle Roar & Wiggle Ticker (called once/frame from FEUD_NMI_HOOK) ----
    a.label('W_NMI_IDLE_TICK')
    a.op16(0xAD, CELEB_WRAM_ORG); a.emit(0xC9, 0x4C); a.branch(0xD0, 'nit_no_amb_t')
    a.op16(0x20, CELEB_WRAM_ORG)  # tick/poll active soft roar (checks W_AMB_ROAR_ON)
    a.label('nit_no_amb_t')
    a.op16(0xAD, W_CELEB_ACTIVE); a.branch(0xD0, 'nit_rst_hop')
    a.emit(0xA5, 0x0D, 0x29, 0x18, 0xC9, 0x18); a.branch(0xD0, 'nit_rst_hop')
    a.emit(0xAD, 0xE3, 0x05, 0xC9, 0xFF); a.branch(0xD0, 'nit_rst_hop')
    a.emit(0xAD, 0xE4, 0x05, 0xC9, 0xFF); a.branch(0xD0, 'nit_rst_hop')
    a.emit(0xAD, 0xE2, 0x04); a.branch(0xD0, 'nit_rst_hop')  # skip Pre-FM / Fast Money
    a.emit(0xAD, 0x41, 0x03); a.branch(0xD0, 'nit_rst_hop')  # wait until fade-in completes
    a.emit(0xAD, 0x3D, 0x03); a.branch(0xD0, 'nit_can_wait')  # avoid $D027 + $DA85 VBlank overflow
    a.emit(0xAD, 0xD6, 0x04); a.branch(0xD0, 'nit_can_wait')  # avoid $CB71 board reveal + $DA85 overflow
    a.emit(0xA5, 0x21); a.branch(0xD0, 'nit_can_wait')        # wait while text update pending
    a.emit(0xA5, 0x47); a.branch(0xD0, 'nit_can_wait')        # wait if block row write in flight

    # View check: $04D3==0 & ($0345==$04/$0D/$0E) -> Stage/NameSelect; $04D3==1 & $0345==$06 -> Overview
    a.emit(0xAD, 0xD3, 0x04); a.branch(0xD0, 'nit_chk_ov')
    a.emit(0xAD, 0x45, 0x03)
    a.emit(0xC9, 0x0D); a.branch(0xF0, 'nit_st_ok')
    a.emit(0xC9, 0x0E); a.branch(0xF0, 'nit_st_ok')
    a.emit(0xC9, 0x04); a.branch(0xD0, 'nit_rst')
    a.label('nit_st_ok')
    a.emit(0xA5, 0x0B); a.branch(0xD0, 'nit_st_dec_init')
    a.abs_ref(0x20, '_w_amb_tick9')  # tick ambient roar timer at true 60 Hz
    a.label('nit_st_dec_init')
    a.emit(0xA2, 0x04)
    a.label('nit_st_dec')
    a.op16(0xBD, W_ST_HOLD); a.emit(0xC9, 0x02); a.branch(0x90, 'nit_st_dnx')
    a.op16(0xDE, W_ST_HOLD)
    a.label('nit_st_dnx')
    a.emit(0xCA); a.branch(0x10, 'nit_st_dec')
    a.emit(0xAD, 0xBD, 0x05); a.branch(0xF0, 'nit_can_queue')
    a.label('nit_can_wait')
    a.emit(0x60)
    a.label('nit_rst_hop')
    a.abs_ref(0x4C, 'nit_rst')

    a.label('nit_chk_ov')
    a.emit(0xC9, 0x01); a.branch(0xD0, 'nit_rst')
    a.emit(0xAD, 0x45, 0x03, 0xC9, 0x06); a.branch(0xD0, 'nit_rst')
    a.abs_ref(0x4C, 'nit_ov_tick')

    a.label('nit_rst')
    a.abs_ref(0x20, '_w_amb_stop')
    a.label('nit_rst_clr')
    a.emit(0xA9, 0xFF); a.op16(0x8D, W_LAST_ST_SEAT)
    a.emit(0xA9, 0x04); a.op16(0x8D, W_IDLE_TIMER)
    a.emit(0xA9, 0x00); a.op16(0x8D, W_IDLE_POSE)
    a.emit(0xA2, 0x09, 0xA9, 0x00)
    a.label('nit_clr_ov')
    a.op16(0x9D, W_OV_HOLD); a.emit(0xCA); a.branch(0x10, 'nit_clr_ov')
    a.emit(0xA2, 0x04)
    a.label('nit_clr_st')
    a.op16(0x9D, W_ST_HOLD); a.op16(0x9D, W_ST_CUR); a.emit(0xCA); a.branch(0x10, 'nit_clr_st')
    a.emit(0x60)

    # Stage Close-Up / Name Select: multi-seat wiggle + mouth open/close toggles + periodic soft roar
    a.label('nit_can_queue')
    a.emit(0xA2, 0x04)
    a.label('nit_step_lp')
    a.op16(0xBD, W_ST_HOLD); a.emit(0xC9, 0x01); a.branch(0xF0, 'nit_do_step')
    a.emit(0xCA); a.branch(0x10, 'nit_step_lp')
    a.branch(0x30, 'nit_chk_roar')  # always branches

    a.label('nit_do_step')
    a.op16(0xBD, W_ST_REP); a.branch(0xF0, 'nit_step_fin')
    a.op16(0xDE, W_ST_REP)
    a.op16(0xBD, W_ST_CUR); a.branch(0xD0, 'nit_to_idle')
    a.op16(0xBD, W_ST_TGT)
    a.branch(0xD0, 'nit_st_set')  # always non-zero (1 or 2)
    a.label('nit_to_idle')
    a.emit(0xA9, 0x00)
    a.label('nit_st_set')
    a.op16(0x9D, W_ST_CUR)
    a.emit(0x48, 0xA9, 0x08); a.op16(0x9D, W_ST_HOLD); a.emit(0x68)
    a.abs_ref(0x4C, '_nit_st_blk_ppu_pose')

    a.label('nit_step_fin')
    a.emit(0xA9, 0x00); a.op16(0x9D, W_ST_HOLD)
    a.op16(0xBD, W_ST_CUR); a.branch(0xF0, 'nit_fin_rts')
    a.emit(0xA9, 0x00); a.op16(0x9D, W_ST_CUR)
    a.abs_ref(0x4C, '_nit_st_blk_ppu_pose')
    a.label('nit_fin_rts')
    a.emit(0x60)

    a.label('nit_chk_roar')
    a.emit(0xA5, 0x0B); a.branch(0xD0, 'nit_wait_start')  # only Barba P1 roars
    a.abs_ref(0x20, '_w_amb_maybe')
    a.branch(0xF0, 'nit_wait_start')
    a.abs_ref(0x20, '_nit_pick_st_seat')
    a.emit(0xA9, 0x01); a.op16(0x9D, W_ST_CUR); a.op16(0x9D, W_ST_TGT)
    a.emit(0xA9, 0x00); a.op16(0x9D, W_ST_REP)
    a.emit(0xA9, 10);   a.op16(0x9D, W_ST_HOLD)
    a.emit(0xA9, 0x01); a.abs_ref(0x4C, '_nit_st_blk_ppu_pose')

    a.label('nit_wait_start')
    a.op16(0xCE, W_IDLE_TIMER)
    a.branch(0xF0, 'nit_trigger')
    a.emit(0x60)

    a.label('nit_trigger')
    a.abs_ref(0x20, '_nit_pick_st_seat')
    a.op16(0xBD, W_ST_HOLD); a.branch(0xF0, 'nit_trig_ok')
    a.emit(0xA9, 0x02); a.op16(0x8D, W_IDLE_TIMER)
    a.emit(0x60)
    a.label('nit_trig_ok')
    a.op16(0x8E, W_LAST_ST_SEAT)
    a.emit(0xAD, 0xFB, 0x01, 0x4D, 0xFC, 0x01, 0x29, 0x03)  # 0 => brief mouth open (25%), 1..3 => wiggle (75%)
    a.branch(0xD0, 'nit_trig_wig')
    a.emit(0xA9, 0x00); a.op16(0x9D, W_ST_REP)
    a.emit(0xA9, 0x06); a.op16(0x9D, W_ST_HOLD)
    a.emit(0xA9, 0x01); a.branch(0xD0, 'nit_trig_go')
    a.label('nit_trig_wig')
    a.emit(0xAD, 0xFA, 0x01, 0x29, 0x02, 0x18, 0x69, 0x03)  # 3 or 5 wiggle toggles
    a.op16(0x9D, W_ST_REP)
    a.emit(0xA9, 0x08); a.op16(0x9D, W_ST_HOLD)
    a.emit(0xA9, 0x02)
    a.label('nit_trig_go')
    a.op16(0x9D, W_ST_TGT); a.op16(0x9D, W_ST_CUR)
    a.emit(0x48)
    a.emit(0xAD, 0xFA, 0x01, 0x4D, 0xFB, 0x01, 0x29, 0x07, 0x18, 0x69, 0x06)  # 6..13f stagger
    a.op16(0x8D, W_IDLE_TIMER)
    a.emit(0x68); a.abs_ref(0x4C, '_nit_st_blk_ppu_pose')

    a.label('_nit_pick_st_seat')
    a.emit(0xAD, 0xFA, 0x01, 0x4D, 0xFB, 0x01, 0x29, 0x07, 0xC9, 0x05)
    a.branch(0x90, 'npss_ok')
    a.emit(0xE9, 0x05)
    a.label('npss_ok')
    a.op16(0xCD, W_LAST_ST_SEAT); a.branch(0xD0, 'npss_chk')
    a.emit(0x18, 0x69, 0x01, 0xC9, 0x05); a.branch(0x90, 'npss_chk')
    a.emit(0xA9, 0x00)
    a.label('npss_chk')
    a.emit(0xAA); a.op16(0xBD, W_ST_HOLD); a.branch(0xF0, 'npss_ret')
    a.emit(0xE8, 0xE0, 0x05); a.branch(0x90, 'npss_ret')
    a.emit(0xA2, 0x00)
    a.label('npss_ret')
    a.emit(0x60)

    # Overview: staggered multi-seat cheers balanced across both teams + periodic Barba soft roar
    a.label('nit_ov_tick')
    a.abs_ref(0x20, '_w_amb_tick9')
    a.emit(0xA2, 0x09)
    a.label('nit_ov_dec')
    a.op16(0xBD, W_OV_HOLD); a.emit(0xC9, 0x02); a.branch(0x90, 'nit_ov_dec_nx')
    a.op16(0xDE, W_OV_HOLD)
    a.label('nit_ov_dec_nx')
    a.emit(0xCA); a.branch(0x10, 'nit_ov_dec')

    a.emit(0xAD, 0xBD, 0x05, 0xC9, 0x03); a.branch(0x90, 'nit_ov_qok')
    a.emit(0x60)
    a.label('nit_ov_qok')

    a.emit(0xA2, 0x09)
    a.label('nit_ov_rest_lp')
    a.op16(0xBD, W_OV_HOLD); a.emit(0xC9, 0x01); a.branch(0xF0, 'nit_ov_do_rest')
    a.emit(0xCA); a.branch(0x10, 'nit_ov_rest_lp')
    a.branch(0x30, 'nit_ov_chk_roar')  # always branches

    a.label('nit_ov_do_rest')
    a.op16(0xAD, W_IDLE_TIMER); a.emit(0xC9, 0x02); a.branch(0x90, 'nit_ov_rest_go')
    a.op16(0xCE, W_IDLE_TIMER)
    a.label('nit_ov_rest_go')
    a.emit(0xA9, 0x00); a.op16(0x9D, W_OV_HOLD)
    a.abs_ref(0xBD, 'TBL_OV_IDLE')
    a.label('_nit_ov_enq')
    a.emit(0x48); a.abs_ref(0xBD, 'TBL_OV_X'); a.emit(0xAA, 0x68)
    a.abs_ref(0x4C, '_nit_enqueue')

    a.label('nit_ov_chk_roar')
    a.abs_ref(0x20, '_w_amb_maybe')
    a.branch(0xF0, 'nit_ov_chk_trig')
    a.emit(0xAD, 0xFA, 0x01, 0x29, 0x03, 0xAA)  # random Barba seat 0..3
    a.emit(0xA9, 10); a.op16(0x9D, W_OV_HOLD)
    a.abs_ref(0xBD, 'TBL_OV_ROAR')
    a.abs_ref(0x4C, '_nit_ov_enq')

    a.label('nit_ov_chk_trig')
    a.op16(0xCE, W_IDLE_TIMER)
    a.branch(0xD0, 'nit_ov_done')
    a.emit(0xAD, 0xFA, 0x01, 0x4D, 0xFB, 0x01, 0x29, 0x07, 0xC9, 0x05)
    a.branch(0x90, 'nit_ov_s5')
    a.emit(0xE9, 0x05)
    a.label('nit_ov_s5')
    a.emit(0xAA)
    a.op16(0xAD, W_IDLE_POSE); a.emit(0x4A, 0x8A); a.branch(0x90, 'nit_ov_sok')
    a.emit(0x69, 0x04)  # Carry is set from LSR A, so +4+1 = +5
    a.label('nit_ov_sok')
    a.emit(0xAA); a.op16(0xBD, W_OV_HOLD); a.branch(0xF0, 'nit_ov_go')
    a.emit(0x8A, 0x49, 0x01, 0xAA); a.op16(0xBD, W_OV_HOLD); a.branch(0xF0, 'nit_ov_go')
    a.emit(0xA9, 0x01); a.op16(0x8D, W_IDLE_TIMER)
    a.label('nit_ov_done')
    a.emit(0x60)

    a.label('nit_ov_go')
    a.op16(0xEE, W_IDLE_POSE)
    a.emit(0xAD, 0xFB, 0x01, 0x4D, 0xFA, 0x01, 0x29, 0x03, 0x18, 0x69, 6)   # 6..9f brief mouth open
    a.op16(0x9D, W_OV_HOLD)
    a.emit(0xAD, 0xFB, 0x01, 0x4D, 0xFA, 0x01, 0x29, 0x07, 0x18, 0x69, 10)  # 10..17f stagger
    a.op16(0x8D, W_IDLE_TIMER)
    a.abs_ref(0xBD, 'TBL_OV_ROAR')
    a.abs_ref(0x4C, '_nit_ov_enq')

    # _nit_st_blk_ppu_pose: X = seat 0..4, A = pose (0=idle, 1=roar, 2=wiggle -> blk off 0, 1, 4)
    a.label('_nit_st_blk_ppu_pose')
    a.op16(0x8E, W_TMP1)
    a.emit(0xC9, 0x02); a.branch(0xD0, '_nsbp_go')
    a.emit(0xA9, 0x04)  # pose 2 (wiggle) lives at block offset +4 in TBL_ST_POSE_MAP
    a.label('_nsbp_go')
    a.op16(0x8D, W_TMP0)
    a.emit(0x8A, 0x0A, 0x0A, 0x18); a.op16(0x6D, W_TMP1)  # seat * 5
    a.emit(0x18); a.op16(0x6D, W_TMP0)                    # + pose_off
    a.emit(0xA4, 0x0B); a.branch(0xF0, 'nsbp_p1')
    a.emit(0x18, 0x69, 25, 0x48)
    a.abs_ref(0xBD, 'TBL_ST_CPU_X'); a.emit(0xAA, 0x68)
    a.abs_ref(0x4C, '_nit_enqueue')
    a.label('nsbp_p1')
    a.emit(0x48); a.abs_ref(0xBD, 'TBL_ST_P1_X'); a.emit(0xAA, 0x68)

    # _nit_enqueue: A = blk_id, X = ppu_lo ($2200 + X)
    a.label('_nit_enqueue')
    a.emit(0xAC, 0xBE, 0x05)
    a.emit(0x99, 0xAE, 0x05)
    a.emit(0x8A, 0x99, 0xAF, 0x05)
    a.emit(0xA9, 0x22, 0x99, 0xB0, 0x05)
    a.emit(0x98, 0x18, 0x69, 0x03, 0xC9, 0x0F, 0xD0, 0x02, 0xA9, 0x00)
    a.emit(0x8D, 0xBE, 0x05, 0xEE, 0xBD, 0x05, 0x60)


def assemble_wram_extra() -> tuple[bytes, dict[str, int]]:
    """Build WRAM routines at $7B00-$7EFF and return (code_bytes, entry_addrs)."""
    a = FeudAsm(WRAM_EXTRA_ORG)
    _assemble_wram_part1(a)
    _assemble_wram_part2(a)
    raw = a.finish()
    assert len(raw) <= 0x04FC, f'WRAM extra overflow: {len(raw)} > 1276'
    return raw, dict(a.labels)


def assemble_celeb_wram(
    base_5ff1: int = 0x00,
    roar_5ff1: int = 0x10,
) -> tuple[bytes, dict[str, int]]:
    """Build Barba round-win head-tilt, randomized roar burst, and shake routines at $7000-$73FF."""
    FEUD_MMC1_CTRL = 0x7860
    a = FeudAsm(CELEB_WRAM_ORG)

    # Fixed jump entries at $7000, $7003, $7006, $7009 for ambient soft roar coordination
    a.emit(0x4C); a.ref16('W_AMB_ROAR_TICK')
    a.emit(0x4C); a.ref16('W_AMB_ROAR_STOP')
    a.emit(0x4C); a.ref16('W_AMB_ROAR_MAYBE')
    a.emit(0x4C); a.ref16('W_AMB_TMR_STEP')

    # Tables
    a.label('C_ST_P1_X')
    a.emit(22, 18, 10, 14, 6)
    a.label('C_LR_SEAT')
    a.emit(4, 2, 3, 1, 0)
    a.label('C_ROAR_RATES')
    a.emit(7, 8, 9, 10, 11, 8, 9, 10)
    a.label('C_ROAR_MIN_LEN')  # min $4013 lengths (~0.48s) for rates 7..11
    a.emit(32, 36, 42, 48, 54)
    a.label('C_SHAKE_X')  # 16-frame 30Hz horizontal shake (0..6 px even steps, 6px peak-to-peak)
    a.emit(0, 0, 6, 6, 2, 2, 4, 4, 0, 0, 6, 6, 2, 2, 4, 4)

    # ---- W_APPLY_SCROLL: called from NMI ($CA8D) ----
    a.label('W_APPLY_SCROLL')
    a.op16(0xAD, W_SHAKE_X)
    a.emit(0x8D, 0x05, 0x20, 0xA9, 0x00, 0x8D, 0x05, 0x20, 0x60)

    # ---- _c_rng: 16-bit Galois LFSR on W_CELEB_RNG, mixed with $01FA ----
    a.label('_c_rng')
    a.op16(0xAD, W_CELEB_RNG)
    a.op16(0x4E, W_CELEB_RNG + 1)
    a.emit(0x6A)  # ROR A
    a.branch(0x90, 'cr_no_xor')
    a.emit(0xA8)
    a.op16(0xAD, W_CELEB_RNG + 1)
    a.emit(0x49, 0xB4)
    a.op16(0x8D, W_CELEB_RNG + 1)
    a.emit(0x98)
    a.label('cr_no_xor')
    a.op16(0x8D, W_CELEB_RNG)
    a.emit(0x4D, 0xFA, 0x01)
    a.emit(0x60)

    # ---- _c_enq_p1_seat: A = seat (0..4), Y = pose_off (0, 1, or 4) ----
    a.label('_c_enq_p1_seat')
    a.op16(0x8C, W_TMP0)
    a.op16(0x8D, W_TMP1)
    a.emit(0xAA)  # X = seat
    a.emit(0x0A, 0x0A, 0x18); a.op16(0x6D, W_TMP1)  # A = seat * 5
    a.emit(0x18); a.op16(0x6D, W_TMP0)              # A = seat * 5 + pose_off
    a.emit(0xAC, 0xBE, 0x05)
    a.emit(0x99, 0xAE, 0x05)
    a.abs_ref(0xBD, 'C_ST_P1_X')
    a.emit(0x99, 0xAF, 0x05)
    a.emit(0xA9, 0x22, 0x99, 0xB0, 0x05)
    a.emit(0x98, 0x18, 0x69, 0x03, 0xC9, 0x0F, 0xD0, 0x02, 0xA9, 0x00)
    a.emit(0x8D, 0xBE, 0x05, 0xEE, 0xBD, 0x05, 0x60)

    # ---- _c_step_shake / _c_shift_host_oam ----
    a.label('_c_step_shake')
    a.op16(0xAE, W_SHAKE_IDX)
    a.abs_ref(0xBD, 'C_SHAKE_X')
    a.op16(0x8D, W_SHAKE_X)
    a.emit(0xE8, 0x8A, 0x29, 0x0F)
    a.op16(0x8D, W_SHAKE_IDX)
    a.emit(0x60)

    a.label('_c_shift_host_oam')
    a.emit(0xA2, 0x04)
    a.label('cso_lp')
    a.emit(0xBD, 0x00, 0x02, 0xC9, 0xEF); a.branch(0xB0, 'cso_nx')
    a.emit(0xBD, 0x03, 0x02, 0x38); a.op16(0xED, W_SHAKE_X)
    a.emit(0x9D, 0x03, 0x02)
    a.label('cso_nx')
    a.emit(0xE8, 0xE8, 0xE8, 0xE8, 0xE0, 0xF0); a.branch(0x90, 'cso_lp')
    a.emit(0x60)

    # ---- _c_fire_roar: pick random pitch & duration, launch DPCM at $C000 ----
    a.label('_c_fire_roar')
    a.op16(0xCE, W_ROAR_LEFT)
    a.abs_ref(0x20, '_c_rng')
    a.emit(0x29, 0x07, 0xAA)
    a.abs_ref(0xBD, 'C_ROAR_RATES')
    a.op16(0xCD, W_ROAR_LAST_R); a.branch(0xD0, 'cfr_rok')
    a.emit(0xE8, 0x8A, 0x29, 0x07, 0xAA)
    a.abs_ref(0xBD, 'C_ROAR_RATES')
    a.label('cfr_rok')
    a.op16(0x8D, W_ROAR_LAST_R)
    a.op16(0x8D, W_TMP0)
    a.emit(0x38, 0xE9, 0x07, 0xAA)
    a.abs_ref(0xBD, 'C_ROAR_MIN_LEN')
    a.op16(0x8D, W_TMP1)
    a.abs_ref(0x20, '_c_rng')
    a.emit(0x29, 0x1F, 0x18); a.op16(0x6D, W_TMP1)  # len = min_len + (0..31)
    a.emit(0xA8)  # Y = len
    a.emit(0xA9, 0x0F, 0x8D, 0x15, 0x40)
    a.op16(0xAD, W_TMP0); a.emit(0x8D, 0x10, 0x40)
    a.emit(0xA9, 0x73, 0x8D, 0x12, 0x40)  # roar.dmc at $DCC0 in upper 256KB PRG
    a.emit(0x8C, 0x13, 0x40)
    a.emit(0xA9, 0x1F, 0x8D, 0x15, 0x40)
    a.emit(0xA9, 18); a.op16(0x8D, W_ROAR_MIN)
    a.emit(0x60)

    # ---- W_CELEB_SPLIT: Stage Close-Up split tuned for active DMC DMA ----
    # Matches $905B ($D2D6 + $D93E + Sprite-0 wait + fc_05 + CHR1=$0C + fc_09)
    # with HBlank margin for DMC DMA cycle steals.
    a.label('W_CELEB_SPLIT')
    a.emit(0x20, 0xD6, 0xD2, 0x20, 0x3E, 0xD9, 0x20, 0xD0, 0x9B)
    a.emit(0xA2, 0x15)
    a.label('cs_w1'); a.emit(0xCA); a.branch(0xD0, 'cs_w1')
    a.emit(0xA2, 0x90)
    a.label('cs_w2'); a.emit(0xCA); a.branch(0xD0, 'cs_w2')
    a.emit(0xA9, 0x05, 0x20, 0x00, 0x78)  # CHR0 = $05 (FEUD_MMC1_CHR0)
    a.emit(0xA9, 0x0C, 0x20, 0x20, 0x78)  # CHR1 = $0C (FEUD_MMC1_CHR1)
    a.emit(0xA0, 0x05, 0xA2, 0x22)
    a.label('cs_w3'); a.emit(0xCA); a.branch(0xD0, 'cs_w3')
    a.emit(0x88); a.branch(0xD0, 'cs_w3')
    a.emit(0xA9, 0x09, 0x4C, 0x00, 0x78)  # CHR0 = $09 (FEUD_MMC1_CHR0)

    # ---- W_CELEB_INIT: hooked at $A24D (JSR $9886) ----
    a.label('W_CELEB_INIT')
    a.abs_ref(0x20, 'W_AMB_ROAR_STOP')
    a.emit(0xA5, 0x0B); a.branch(0xD0, 'ci_no')
    a.emit(0xAE, 0xC3, 0x05); a.branch(0x30, 'ci_clr')
    a.emit(0x20, 0xAE, 0xD2)  # free $05E3,X BG script slot cleanly
    a.label('ci_clr')
    a.emit(0xA9, 0xFF, 0x8D, 0xC3, 0x05)
    a.emit(0xA9, 0x01); a.op16(0x8D, W_CELEB_ACTIVE)
    a.emit(0xA9, 0x00)
    a.op16(0x8D, W_SHAKE_X)
    a.op16(0x8D, W_CELEB_STEP)
    a.op16(0x8D, W_CELEB_HOLD)
    a.op16(0x8D, W_CELEB_DELAY)
    a.emit(0xA9, 0x04); a.op16(0x8D, W_CELEB_POSE)  # start with head tilt (pose 2 = blk+4)
    a.emit(0xAD, 0xFA, 0x01, 0x45, 0x2D); a.op16(0x8D, W_CELEB_RNG)
    a.emit(0xAD, 0xFB, 0x01, 0x09, 0x01); a.op16(0x8D, W_CELEB_RNG + 1)
    a.emit(0x60)
    a.label('ci_no')
    a.emit(0x20, 0x86, 0x98)  # Z2 team: run vanilla $9886 cheering script
    a.emit(0xA9, 0x00); a.op16(0x8D, W_CELEB_ACTIVE); a.op16(0x8D, W_SHAKE_X)
    a.emit(0x60)

    # ---- W_CELEB_SET_TIMER: hooked at $A250 (LDA #$05; JSR $99F7) ----
    a.label('W_CELEB_SET_TIMER')
    a.op16(0xAD, W_CELEB_ACTIVE); a.branch(0xF0, 'cst_van')
    a.emit(0xA9, 0x03, 0x4C, 0xF7, 0x99)
    a.label('cst_van')
    a.emit(0xA9, 0x05, 0x4C, 0xF7, 0x99)

    # ---- W_CELEB_HEAD_TILT_TICK: hooked at $A26A (JSR $905B) ----
    a.label('W_CELEB_HEAD_TILT_TICK')
    a.emit(0x20, 0x5B, 0x90)
    a.op16(0xAD, W_CELEB_ACTIVE); a.emit(0xC9, 0x01); a.branch(0xD0, 'ht_done')
    a.emit(0xAD, 0x5E, 0x03); a.branch(0xD0, 'ht_done')  # wait for BARBA banner finish
    a.emit(0xA5, 0x50, 0xC9, 0xFF); a.branch(0xD0, 'ht_done')
    a.op16(0xAD, W_CELEB_HOLD); a.branch(0xF0, 'ht_chk_blk')
    a.op16(0xCE, W_CELEB_HOLD)
    a.emit(0x60)
    a.label('ht_chk_blk')
    a.emit(0xA5, 0x47, 0x0D, 0xBD, 0x05); a.branch(0xD0, 'ht_done')
    a.op16(0xAE, W_CELEB_STEP)
    a.abs_ref(0xBD, 'C_LR_SEAT')
    a.op16(0xAC, W_CELEB_POSE)
    a.abs_ref(0x20, '_c_enq_p1_seat')
    a.op16(0xEE, W_CELEB_STEP)
    a.op16(0xAD, W_CELEB_STEP); a.emit(0xC9, 0x05); a.branch(0x90, 'ht_done')
    a.emit(0xA9, 0x00); a.op16(0x8D, W_CELEB_STEP)
    a.op16(0xAD, W_CELEB_POSE); a.emit(0x49, 0x04); a.op16(0x8D, W_CELEB_POSE)
    a.emit(0xA9, 0x07); a.op16(0x8D, W_CELEB_HOLD)
    a.label('ht_done')
    a.emit(0x60)

    # ---- W_CELEB_ROAR_PHASE: hooked at $A277 (LDA $0393; AND #$0F) ----
    a.label('W_CELEB_ROAR_PHASE')
    a.op16(0xAD, W_CELEB_ACTIVE); a.emit(0xC9, 0x01); a.branch(0xF0, 'crp_wait_flush')
    a.emit(0xAD, 0x93, 0x03, 0x29, 0x0F, 0x60)

    a.label('crp_wait_flush')
    a.emit(0xA5, 0x47, 0x0D, 0xBD, 0x05); a.branch(0xF0, 'crp_flushed')
    a.emit(0x20, 0xF9, 0xCA, 0x20, 0x5B, 0x90)
    a.abs_ref(0x4C, 'crp_wait_flush')

    a.label('crp_flushed')
    a.emit(0xA9, 0x00, 0x8D, 0xF9, 0x05, 0x8D, 0xFA, 0x05, 0x8D, 0x03, 0x06)
    a.emit(0xA9, 0x0F, 0x8D, 0x15, 0x40)
    a.emit(0xA9, 0x40, 0x8D, 0x11, 0x40)  # settle DMC DAC midpoint once
    a.emit(0xA9, 0x02); a.op16(0x8D, W_CELEB_ACTIVE)
    a.emit(0xA9, 0x03, 0x20, FEUD_MMC1_CTRL & 0xFF, FEUD_MMC1_CTRL >> 8)  # Horiz mirroring (MMC1 val 3 -> $A000=1)
    a.emit(0xA9, roar_5ff1, 0x8D, 0xF1, 0x5F)  # upper 256KB PRG (roar.dmc at $DCC0)

    # Pick random roar count in 3..5
    a.abs_ref(0x20, '_c_rng')
    a.emit(0x29, 0x03, 0xC9, 0x03); a.branch(0xD0, 'crp_cnt_ok')
    a.emit(0xA9, 0x01)
    a.label('crp_cnt_ok')
    a.emit(0x18, 0x69, 0x03); a.op16(0x8D, W_ROAR_LEFT)

    a.emit(0xA9, 0xFF); a.op16(0x8D, W_ROAR_LAST_R)
    a.emit(0xA9, 0x00)
    a.op16(0x8D, W_SHAKE_IDX)
    a.op16(0x8D, W_ROAR_GAP)
    a.op16(0x8D, W_ROAR_MIN)
    a.op16(0x8D, W_ROAR_SEAT_Q)
    a.op16(0x8D, W_CELEB_STEP)

    # Start Roar #1 + Shake immediately
    a.abs_ref(0x20, '_c_fire_roar')
    a.abs_ref(0x20, '_c_step_shake')

    a.label('crp_roar_loop')
    a.emit(0x20, 0xF9, 0xCA); a.abs_ref(0x20, 'W_CELEB_SPLIT')

    # Queue remaining seats 0..4 to pose 1 (roar)
    a.op16(0xAD, W_ROAR_SEAT_Q); a.emit(0xC9, 0x05); a.branch(0xB0, 'crp_chk_state')
    a.emit(0xA5, 0x47, 0x0D, 0xBD, 0x05); a.branch(0xD0, 'crp_chk_state')
    a.op16(0xAE, W_ROAR_SEAT_Q)
    a.abs_ref(0xBD, 'C_LR_SEAT')
    a.emit(0xA0, 0x01); a.abs_ref(0x20, '_c_enq_p1_seat')
    a.op16(0xEE, W_ROAR_SEAT_Q)

    a.label('crp_chk_state')
    a.op16(0xAD, W_ROAR_GAP); a.branch(0xF0, 'crp_playing')
    a.op16(0xCE, W_ROAR_GAP); a.branch(0xD0, 'crp_adv_shake')
    a.op16(0xAD, W_ROAR_LEFT); a.branch(0xF0, 'crp_roars_done')
    a.abs_ref(0x20, '_c_fire_roar')
    a.emit(0xA5, 0x47, 0x0D, 0xBD, 0x05); a.branch(0xD0, 'crp_adv_shake')
    a.op16(0xAE, W_CELEB_STEP)
    a.abs_ref(0xBD, 'C_LR_SEAT')
    a.emit(0xA0, 0x01); a.abs_ref(0x20, '_c_enq_p1_seat')
    a.abs_ref(0x4C, 'crp_adv_shake')

    a.label('crp_playing')
    a.op16(0xAD, W_ROAR_MIN); a.branch(0xF0, 'crp_poll_dmc')
    a.op16(0xCE, W_ROAR_MIN)
    a.abs_ref(0x4C, 'crp_adv_shake')

    a.label('crp_poll_dmc')
    a.emit(0xAD, 0x15, 0x40, 0x29, 0x10); a.branch(0xD0, 'crp_adv_shake')
    a.op16(0xAD, W_ROAR_LEFT); a.branch(0xF0, 'crp_roars_done')
    a.abs_ref(0x20, '_c_rng')
    a.emit(0x29, 0x03, 0x18, 0x69, 0x04); a.op16(0x8D, W_ROAR_GAP)  # 4..7f breath gap
    a.emit(0xA5, 0x47, 0x0D, 0xBD, 0x05); a.branch(0xD0, 'crp_adv_shake')
    a.op16(0xEE, W_CELEB_STEP)
    a.op16(0xAD, W_CELEB_STEP); a.emit(0xC9, 0x05); a.branch(0x90, 'crp_dip_ok')
    a.emit(0xA9, 0x00); a.op16(0x8D, W_CELEB_STEP)
    a.label('crp_dip_ok')
    a.emit(0xAA); a.abs_ref(0xBD, 'C_LR_SEAT')
    a.emit(0xA0, 0x00); a.abs_ref(0x20, '_c_enq_p1_seat')

    a.label('crp_adv_shake')
    a.abs_ref(0x20, '_c_step_shake')
    a.abs_ref(0x20, '_c_shift_host_oam')
    a.abs_ref(0x4C, 'crp_roar_loop')

    # ---- Last roar ended: stop shake & DMC, restore banks, pause < 1s ----
    a.label('crp_roars_done')
    a.emit(0xA9, 0x00); a.op16(0x8D, W_SHAKE_X)
    a.emit(0xA9, 0x0F, 0x8D, 0x15, 0x40)
    a.emit(0xA9, base_5ff1, 0x8D, 0xF1, 0x5F)  # restore Feud base 256KB PRG
    a.emit(0xA9, 0x02, 0x20, FEUD_MMC1_CTRL & 0xFF, FEUD_MMC1_CTRL >> 8)  # restore Vertical mirroring (MMC1 val 2 -> $A000=0)

    a.emit(0xA9, 0x00); a.op16(0x8D, W_ROAR_SEAT_Q)
    a.emit(0xA9, 28); a.op16(0x8D, W_ROAR_GAP)  # ~0.47s pause + ~0.25s fade = ~0.72s (< 1s)
    a.label('crp_pause_loop')
    a.emit(0x20, 0xF9, 0xCA, 0x20, 0x5B, 0x90)
    a.op16(0xAD, W_ROAR_SEAT_Q); a.emit(0xC9, 0x05); a.branch(0xB0, 'crp_pause_tick')
    a.emit(0xA5, 0x47, 0x0D, 0xBD, 0x05); a.branch(0xD0, 'crp_pause_tick')
    a.op16(0xAE, W_ROAR_SEAT_Q)
    a.abs_ref(0xBD, 'C_LR_SEAT')
    a.emit(0xA0, 0x00); a.abs_ref(0x20, '_c_enq_p1_seat')
    a.op16(0xEE, W_ROAR_SEAT_Q)
    a.label('crp_pause_tick')
    a.op16(0xCE, W_ROAR_GAP); a.branch(0xD0, 'crp_pause_loop')

    a.emit(0xA9, 0x00); a.op16(0x8D, W_CELEB_ACTIVE)
    a.emit(0xA2, 0x04)
    a.label('crp_clr_st')
    a.op16(0x9D, W_ST_HOLD); a.op16(0x9D, W_ST_CUR); a.emit(0xCA); a.branch(0x10, 'crp_clr_st')
    a.emit(0xAD, 0x93, 0x03, 0x29, 0x0F, 0x60)

    # ---- Periodic Ambient Soft Roar ($E940, rate 9, len 56, DAC amp 24) ----
    a.label('W_AMB_ROAR_TICK')
    a.op16(0xAD, W_AMB_ROAR_ON); a.branch(0xF0, 'art_done')
    a.emit(0xC9, 0x01); a.branch(0xF0, 'art_poll')
    a.op16(0xCE, W_AMB_ROAR_ON)
    a.emit(0x60)
    a.label('art_poll')
    a.emit(0xAD, 0x15, 0x40, 0x29, 0x10); a.branch(0xD0, 'art_done')
    a.label('W_AMB_ROAR_STOP')
    a.op16(0xAD, W_AMB_ROAR_ON); a.branch(0xF0, 'art_done')
    a.emit(0xA9, 0x0F, 0x8D, 0x15, 0x40)
    a.emit(0xA9, base_5ff1, 0x8D, 0xF1, 0x5F); a.op16(0x8D, W_AMB_ROAR_ON)
    a.label('art_done')
    a.emit(0x60)

    a.label('W_AMB_TMR_STEP')
    a.op16(0xAD, W_AMB_ROAR_ON); a.branch(0xD0, 'ats_done')
    a.op16(0xAD, W_AMB_TMR_LO); a.branch(0xD0, 'ats_dec_lo')
    a.op16(0xAD, W_AMB_TMR_HI); a.branch(0xF0, 'ats_done')
    a.op16(0xCE, W_AMB_TMR_HI)
    a.label('ats_dec_lo')
    a.op16(0xCE, W_AMB_TMR_LO)
    a.label('ats_done')
    a.emit(0x60)

    a.label('W_AMB_ROAR_MAYBE')
    a.op16(0xAD, W_AMB_TMR_LO); a.op16(0x0D, W_AMB_TMR_HI); a.branch(0xF0, 'arm_fire')
    a.emit(0xA9, 0x00, 0x60)
    a.label('arm_fire')
    a.emit(0xAD, 0xFA, 0x01, 0x45, 0x1F, 0x29, 0x7F, 0x18, 0x69, 14)  # 270..397 frames (4.5..6.6s)
    a.op16(0x8D, W_AMB_TMR_LO)
    a.emit(0xA9, 0x01); a.op16(0x8D, W_AMB_TMR_HI)
    a.emit(0xA9, roar_5ff1, 0x8D, 0xF1, 0x5F)     # upper 256KB PRG (roar_soft.dmc at $E940)
    a.emit(0xA9, 0x0F, 0x8D, 0x15, 0x40)
    a.emit(0xA9, 0x40, 0x8D, 0x11, 0x40)     # settle DMC DAC midpoint before ambient roar
    a.emit(0xA9, 0x09, 0x8D, 0x10, 0x40)     # rate 9 (11,186 Hz, matches Z2 Barba roar)
    a.emit(0xA9, 0xA5, 0x8D, 0x12, 0x40)     # ($E940 - $C000) / 64 = $A5
    a.emit(0xA9, 56,   0x8D, 0x13, 0x40)     # (897 - 1) / 16 = 56
    a.emit(0xA9, 0x1F, 0x8D, 0x15, 0x40)
    a.emit(0xA9, 36); a.op16(0x8D, W_AMB_ROAR_ON)
    a.emit(0xA9, 0x01, 0x60)

    raw = a.finish()
    assert len(raw) <= 0x0400, f'Celeb WRAM overflow: {len(raw)} > 1024'
    return raw, dict(a.labels)
