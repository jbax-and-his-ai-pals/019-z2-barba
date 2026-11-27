"""Unit tests for the Legend of Zelda: Barba Edition subgame packer."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

import pack_zelda  # noqa: E402
import zelda_art  # noqa: E402


class PackZeldaTests(unittest.TestCase):
    @unittest.skipUnless((ROOT / 'roms' / 'z2.nes').exists(), 'roms/z2.nes not present')
    def test_zelda_art_tile_sizes(self) -> None:
        art = zelda_art.build_barba_player_tiles((ROOT / 'roms' / 'z2.nes').read_bytes())
        self.assertEqual(len(art['barba_00_1b']), 0x1C0)
        self.assertEqual(len(art['fire_vert']), 0x20)
        self.assertEqual(len(art['fire_horiz']), 0x20)
        self.assertEqual(len(art['spark_62_65']), 0x40)
        self.assertEqual(len(art['hold_78']), 0x20)
        self.assertEqual(len(art['villain_c0_e7']), 0x280)

    def test_wram_code_and_boot_bank_isolation(self) -> None:
        wram = pack_zelda._assemble_wram_code(
            reward_magic=pack_zelda.ZELDA_REWARD_MAGIC,
            roar_rate_index=9,
            roar_length_reg=0x88,
            roar_timer_frames=97,
        )
        self.assertEqual(len(wram), 0x100)
        bank0 = pack_zelda._make_boot_bank0(wram, restore_addr=0xC345, reward_addr=0x63B9)
        self.assertEqual(len(bank0), 8192)
        # Boot sequence must start with SEI; CLD; LDX #$FF; TXS and WRAM bank $A3
        self.assertEqual(bank0[0:5], bytes([0x78, 0xD8, 0xA2, 0xFF, 0x9A]))
        self.assertIn(bytes([0xA9, 0xA3, 0x8D, 0x01, 0xA0]), bank0[:0x100])
        # Combined mode must NEVER write $5FF0 outside the $8200 ($0300 exit trampoline) block
        writes_5ff0 = bytes([0x8D, 0xF0, 0x5F])
        self.assertNotIn(writes_5ff0, bank0[:0x200])
        self.assertNotIn(writes_5ff0, bank0[0x300:])
        self.assertIn(bytes([0xA9, 0x01, 0x8D, 0xF0, 0x5F]), bank0[0x200:0x300])

    @unittest.skipUnless((ROOT / 'roms' / 'zelda.nes').exists(), 'roms/zelda.nes not present')
    def test_patch_zelda_combined_contract(self) -> None:
        zelda_bytes = (ROOT / 'roms' / 'zelda.nes').read_bytes()
        prg = pack_zelda.patch_zelda(zelda_bytes, 0xD123, reward_addr=0x63B9)
        self.assertEqual(len(prg), 256 * 1024)
        # Fixed bank at 240..256 KB mirrors 128..144 KB and keeps reset -> $FF50 ($FFFC untouched for portal boot_addr=$8000)
        self.assertEqual(prg[128 * 1024 : 144 * 1024], prg[240 * 1024 : 256 * 1024])
        reset_vec = int.from_bytes(prg[256 * 1024 - 4 : 256 * 1024 - 2], 'little')
        self.assertEqual(reset_vec, pack_zelda.ZELDA_ORIG_RESET)
        # No $5FF0 writes outside the $8200-$82FF exit trampoline payload in boot bank 0
        writes_5ff0 = bytes([0x8D, 0xF0, 0x5F])
        self.assertNotIn(writes_5ff0, prg[:0x200])
        self.assertNotIn(writes_5ff0, prg[0x300:])
        # Roar DMC sample lives at 8KB bank 18 (144..152 KB)
        roar_slice = prg[pack_zelda.ZELDA_ROAR_BANK_R6 * 8192 : pack_zelda.ZELDA_ROAR_BANK_R6 * 8192 + 256]
        self.assertTrue(any(b != 0xFF for b in roar_slice))

    @unittest.skipUnless(
        (ROOT / 'roms' / 'zelda.nes').exists() and (ROOT / 'roms' / 'z2.nes').exists(),
        'roms/zelda.nes or roms/z2.nes not present',
    )
    def test_build_standalone_header_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = pack_zelda.build_standalone(Path(tmp) / 'zelda.nes')
            rom = out.read_bytes()
            self.assertEqual(len(rom), 16 + 256 * 1024 + 8192)
            self.assertEqual(rom[0:4], b'NES\x1a')
            self.assertEqual(rom[4], 16)
            self.assertEqual(rom[5], 1)
            self.assertEqual(rom[10], 0x90)
            self.assertEqual(rom[11], 0x09)
            self.assertEqual((rom[6] >> 4) | (rom[7] & 0xF0), 176)


if __name__ == '__main__':
    unittest.main()
