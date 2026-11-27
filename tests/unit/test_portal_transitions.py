"""ROM-free unit tests for tools/portal_transitions.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

from asm6502 import Asm6502  # noqa: E402
from portal_transitions import (  # noqa: E402
    RA_LAST_WIN_GAME,
    WAVE_TABLE,
    build_return_helper,
    emit_clean_apu_mute,
    emit_wavy_transition,
)


class TestPortalTransitions(unittest.TestCase):
    def test_clean_apu_mute_bytes(self) -> None:
        a = Asm6502(0x8000)
        emit_clean_apu_mute(a)
        code = a.finish()
        self.assertEqual(
            code,
            bytes.fromhex('a9 00 8d 15 40 8d 11 40 8d 00 e0 a9 40 8d 17 40 a9 00'),
        )

    def test_return_helper_win_and_game_id(self) -> None:
        tramp = build_return_helper(
            0xE123,
            0x63B4,
            game_id=5,
            win_reg='y',
            check_magic=0x4D,
            lock_wram=True,
        )
        self.assertIn(RA_LAST_WIN_GAME.to_bytes(2, 'little'), tramp)
        self.assertIn(bytes([0xA9, 0x05, 0x8D]) + RA_LAST_WIN_GAME.to_bytes(2, 'little'), tramp)
        self.assertIn(bytes([0xC0, 0x4D]), tramp)
        self.assertIn(bytes([0x8C]) + (0x63B4).to_bytes(2, 'little'), tramp)
        self.assertTrue(tramp.endswith(bytes([0x4C, 0x23, 0xE1])))

    def test_wavy_transition_zp_and_abs_variants(self) -> None:
        a_zp = Asm6502(0xF4D7)
        emit_wavy_transition(
            a_zp,
            prefix='t_zp',
            frame_addr=0x00,
            cut_addr=0x01,
            band_addr=0x02,
            dir_addr=0x03,
            ppuctrl_addr=0xF7,
            ppumask_addr=0xF8,
            end_on_vblank=True,
        )
        zp_bytes = a_zp.finish()
        self.assertIn(bytes(WAVE_TABLE), zp_bytes)

        a_abs = Asm6502(0x8500)
        emit_wavy_transition(
            a_abs,
            prefix='t_abs',
            frame_addr=0x7FD1,
            cut_addr=0x7FD2,
            band_addr=0x7FD3,
            direction='out',
            ppuctrl_addr=0x0778,
            ppumask_addr=0x0779,
            scroll_x_addr=0x073F,
            scroll_nt_addr=0x0778,
            scroll_hud_bands=4,
            nt_tmp_addr=0x7FD4,
            base_tmp_addr=0x7FD5,
        )
        abs_bytes = a_abs.finish()
        self.assertIn(bytes(WAVE_TABLE), abs_bytes)
        self.assertGreater(len(abs_bytes), len(zp_bytes))
        # Verify JMP targets in emit_wavy_transition match exact label addresses (no dangling fixups)
        for lbl_name in ('t_abs_sc_ok', 't_abs_add_shear', 't_abs_next_frame', 't_abs_band', 't_abs_frame'):
            addr = a_abs.labels[lbl_name]
            self.assertIn(bytes([0x4C, addr & 0xFF, addr >> 8]), abs_bytes, f'Missing valid JMP to {lbl_name}')
        sc_addr = a_zp.labels['t_zp_sc_ok']
        self.assertIn(bytes([0x4C, sc_addr & 0xFF, sc_addr >> 8]), zp_bytes)

    def test_wavy_transition_inline_fallthrough(self) -> None:
        a = Asm6502(0x8200)
        emit_wavy_transition(
            a,
            prefix='t_in',
            frame_addr=0x75F8,
            cut_addr=0x75F9,
            band_addr=0x75FA,
            direction='out',
            ppuctrl_addr=0x0C,
            ppuctrl_mask=0x7C,
            ppumask_addr=0x0D,
            emit_rts=False,
        )
        nop_addr = 0x8200 + len(a.buf)
        a.emit(0xEA)
        code = a.finish()
        after = a.labels['t_in_after_wave']
        self.assertEqual(after, nop_addr)
        self.assertEqual(code[a.labels['t_in_ret'] - 0x8200], 0x4C)
        self.assertIn(bytes([0x4C, after & 0xFF, after >> 8]) + bytes(WAVE_TABLE), code)


if __name__ == '__main__':
    unittest.main()
