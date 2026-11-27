"""Unit tests for tools/pack_mm2.py and tools/mm2_art.py (Barba Man 2)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

import mm2_art  # noqa: E402
import nes  # noqa: E402
import pack_mm2  # noqa: E402

MM2_ROM = ROOT / 'roms' / 'mm2.nes'
Z2_ROM = ROOT / 'roms' / 'z2.nes'


class PackMm2Tests(unittest.TestCase):
    def test_bank15_code_segments_fit_bounds(self) -> None:
        segs = pack_mm2._assemble_bank15_code(
            0xE000,
            reward_addr=0x63B7,
            standalone_stub=False,
        )
        addrs = {addr: (data, limit) for addr, data, limit in segs}
        for required in (
            pack_mm2.MM2_PRG_SWITCH,
            pack_mm2.MM2_CHR0,
            pack_mm2.MM2_CHR1,
            pack_mm2.MM2_NMI_HOOK,
            pack_mm2.MM2_WIN_HOOK,
            pack_mm2.MM2_SEED_RNG,
            pack_mm2.MM2_RETURN,
            pack_mm2.MM2_BOOT,
            pack_mm2.MM2_PLAY_ROAR,
            pack_mm2.MM2_APU_4015,
            pack_mm2.MM2_ROAR_BOSS_INTRO,
            pack_mm2.MM2_ROAR_SFX,
            pack_mm2.MM2_HITBOX_Y,
            pack_mm2.MM2_SPAWN_Y,
        ):
            self.assertIn(required, addrs)
            data, limit = addrs[required]
            self.assertLessEqual(required + len(data), limit)
        # Combined-ROM return trampoline must restore WRAM bank 0 ($A0) and write reward $63B7
        ret_data, _ = addrs[pack_mm2.MM2_RETURN]
        self.assertIn(bytes.fromhex('a9 a0 8d 01 a0'), ret_data)
        self.assertIn(bytes.fromhex('8d b7 63'), ret_data)

    def test_fireball_art_layout_and_tiles(self) -> None:
        tiles, layout_a4, frame_22 = mm2_art.compile_barba_fireball()
        self.assertEqual(set(tiles.keys()), {mm2_art.FIREBALL_TILE_HEAD, mm2_art.FIREBALL_TILE_TAIL})
        for tile in tiles.values():
            self.assertEqual(len(tile), 16)
        self.assertEqual(len(layout_a4), 6)
        self.assertEqual(len(frame_22), 6)
        self.assertEqual(frame_22[0], 2)
        self.assertEqual(frame_22[1], mm2_art.FIREBALL_LAYOUT_ID)

    def test_title_barba_uses_left_facing_overworld_sprite(self) -> None:
        tbarba = mm2_art.compile_title_barba()
        idle = tbarba['b6_barba_idle']
        anim = tbarba['b6_barba_anim']
        blank = tbarba['b6_face_blank']
        self.assertEqual(len(idle), 9 * 16)
        self.assertEqual(len(anim), 6 * 16)
        self.assertEqual(len(blank), 2 * 16)
        self.assertEqual(idle[:3 * 16], b'\x00' * (3 * 16))
        self.assertEqual(blank, b'\x00' * 32)

        art = json.loads((ROOT / 'assets' / 'barba.json').read_text(encoding='utf-8'))

        def decode_24x16(blob: bytes) -> list[str]:
            grid = [['0'] * 24 for _ in range(16)]
            for idx in range(6):
                tx, ty = idx % 3, idx // 3
                rows = nes.decode_tile(blob[idx * 16 : (idx + 1) * 16])
                for y in range(8):
                    for x in range(8):
                        grid[ty * 8 + y][tx * 8 + x] = str(rows[y][x])
            return [''.join(r) for r in grid]

        expected_small_left = ['0000' + r[::-1] + '0000' for r in art['small']]
        expected_step_left = ['0000' + r[::-1] + '0000' for r in art['small_step']]
        self.assertEqual(decode_24x16(idle[3 * 16 :]), expected_small_left)
        self.assertEqual(decode_24x16(anim), expected_step_left)

    def test_combined_rom_patch_contract(self) -> None:
        if not (MM2_ROM.is_file() and Z2_ROM.is_file()):
            return
        prg = pack_mm2.patch_mm2(
            MM2_ROM.read_bytes(),
            restore_addr=0xE000,
            reward_addr=0x63B7,
        )
        self.assertEqual(len(prg), 256 * 1024)
        roar_dmc = ROOT / 'build' / 'subgames' / 'mm2_roar' / 'roar-soft.dmc'
        self.assertTrue(roar_dmc.is_file())
        dmc_bytes = roar_dmc.read_bytes()
        off_dmc = 15 * 0x4000 + (pack_mm2.MM2_ROAR_DMC_ADDR - 0xC000)
        self.assertEqual(prg[off_dmc : off_dmc + len(dmc_bytes)], dmc_bytes)
        # Stage Select text uses EVIL LINK instead of Dr. WILY
        b11 = prg[11 * 0x4000 : 12 * 0x4000]
        self.assertEqual(b11[0x302E:0x3032], bytes.fromhex('05 16 09 0c'))
        self.assertEqual(b11[0x304F:0x3053], bytes.fromhex('0c 09 0e 0b'))
        # Mega Buster Pal 0 uses Barba crimson/amber/cream ($16/$27/$30)
        b15 = prg[15 * 0x4000 : 16 * 0x4000]
        self.assertEqual(b15[0x1303:0x1306], bytes.fromhex('16 27 30'))
        # Collision patches for wider/taller Barba (22px wide, 32px tall)
        b14 = prg[14 * 0x4000 : 15 * 0x4000]
        self.assertEqual(b14[0x0969:0x096B], b'\x69\x0B')
        self.assertEqual(b14[0x09D5:0x09D7], b'\xE9\x0B')
        self.assertEqual(b14[0x0B54:0x0B56], b'\xE9\x14')
        self.assertEqual(b14[0x0BDB:0x0BDD], b'\xE9\x14')
        # Title screen Barba palette and Frame 1 / animation speed in Bank 13
        b13 = prg[13 * 0x4000 : 14 * 0x4000]
        self.assertEqual(b13[0x2AA0:0x2AA8], bytes.fromhex('16 27 30 0f 16 27 30 0f'))
        self.assertEqual(
            b13[0x2B6A : 0x2B6A + 45],
            bytes.fromhex(
                '0b 00 00 01 c8 00 01 01 d0 00 02 01 d8 '
                '08 09 00 c8 08 0a 00 d0 08 0b 00 d8 '
                '08 1f 01 c8 08 20 01 d0 '
                '10 0c 00 c8 10 0d 00 d0 10 0e 00 d8'
            ),
        )
        self.assertEqual(b13[0x25FA:0x25FF], bytes.fromhex('a9 0c 8d 90 06'))


if __name__ == '__main__':
    unittest.main()
