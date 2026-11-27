"""Unit tests for tools/pack_duck.py, tools/duck_art.py, and tools/duck_code.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

import duck_code  # noqa: E402
import pack_duck  # noqa: E402

DUCK_ROM = ROOT / 'roms' / 'duck.nes'
Z2_ROM = ROOT / 'roms' / 'z2.nes'


class PackDuckTests(unittest.TestCase):
    def test_combined_bank0_never_writes_5ff0_during_boot(self) -> None:
        bank0 = pack_duck.make_duck_bank0(0x9092, wram_bank=0xA3, standalone_stub=False, reward_addr=0x63B5)
        self.assertEqual(len(bank0), 8192)
        loader = bank0[:0x100]
        # Must not write $5FF0 = $01 during boot
        self.assertNotIn(bytes.fromhex('a9 01 8d f0 5f'), loader)
        # Must lock WRAM bank 3 ($A3) -> $A001
        self.assertIn(bytes.fromhex('a9 a3 8d 01 a0'), loader)

        wram = bank0[0x100:0x500]
        boot_slice = wram[pack_duck.DUCK_BOOT - pack_duck.DUCK_WRAM_CODE_BASE :]
        self.assertNotIn(bytes.fromhex('8d f0 5f'), boot_slice)

        ret_slice = wram[
            pack_duck.DUCK_RETURN - pack_duck.DUCK_WRAM_CODE_BASE :
            pack_duck.DUCK_BOOT - pack_duck.DUCK_WRAM_CODE_BASE
        ]
        expected_tramp = (
            bytes.fromhex(
                'a9 80 8d 01 a0 '
                'a9 01 8d f0 5f '
                'a9 00 8d f1 5f 8d f2 5f '
                'a9 06 8d 00 80 a9 0c 8d 01 80 '
                'a9 07 8d 00 80 a9 0d 8d 01 80 '
                'a9 a0 8d 01 a0 '
                '8a f0 03 8d b5 63 '
                '4c 92 90'
            )
        )
        self.assertIn(expected_tramp, ret_slice)

    def test_standalone_bank0_writes_5ff0_01(self) -> None:
        bank0 = pack_duck.make_duck_bank0(
            pack_duck.STANDALONE_RESTORE_ADDR,
            wram_bank=0xA3,
            standalone_stub=True,
            reward_addr=pack_duck.DUCK_REWARD_ADDR,
        )
        self.assertIn(bytes.fromhex('a9 01 8d f0 5f'), bank0[:0x100])

    def test_fixed_pad_and_title_stream_assemble(self) -> None:
        fixed_pad, syms = duck_code.assemble_fixed_pad()
        self.assertIn('vh_dmc_guard', syms)
        self.assertIn('vh_4011_guard', syms)
        self.assertLessEqual(len(fixed_pad), 0x3A6)
        stream = duck_code.build_title_ppu_stream()
        self.assertEqual(stream[-1], 0x00)

    def test_title_stream_build_number_uses_black_palette(self) -> None:
        tag_write = bytes([0x20, 0x3A, 0x03, 0x0B, 0x02, 0x04])
        attr_write = bytes([0x23, 0xC6, 0x02, 0x0C, 0x0F])

        stream_with = duck_code.build_title_ppu_stream(24)
        self.assertIn(tag_write, stream_with)
        self.assertIn(attr_write, stream_with)

        stream_without = duck_code.build_title_ppu_stream(None)
        self.assertNotIn(tag_write, stream_without)
        self.assertNotIn(attr_write, stream_without)

    @unittest.skipUnless(DUCK_ROM.is_file() and Z2_ROM.is_file(), 'ROMs required for combined pack test')
    def test_patch_duck_for_combined_contract(self) -> None:
        prg_256k, chr_data = pack_duck.patch_duck_for_combined(
            DUCK_ROM.read_bytes(),
            Z2_ROM.read_bytes(),
            0x9123,
            reward_addr=0x63B5,
        )
        self.assertEqual(len(prg_256k), 256 * 1024)
        self.assertLessEqual(len(chr_data), 128 * 1024)
        self.assertEqual(len(chr_data) % 8192, 0)
        # Offset 0 is 8KB boot bank ($8000) and does not write $5FF0=$01 during boot
        self.assertNotIn(bytes.fromhex('a9 01 8d f0 5f'), prg_256k[:0x100])
        # Reset vector points to $8000, NMI vector points to $7840
        self.assertEqual(prg_256k[-6:-4], bytes([pack_duck.DUCK_NMI_HOOK & 0xFF, pack_duck.DUCK_NMI_HOOK >> 8]))
        self.assertEqual(prg_256k[-4:-2], bytes([0x00, 0x80]))
        # Combined ROM patches $D39B -> JMP DUCK_WIN_HOOK ($7870)
        win_off = 30 * 8192 + (pack_duck.DUCK_WIN_PATCH_ADDR - 0xC000)
        self.assertEqual(
            prg_256k[win_off : win_off + 3],
            bytes([0x4C, pack_duck.DUCK_WIN_HOOK & 0xFF, pack_duck.DUCK_WIN_HOOK >> 8]),
        )

    @unittest.skipUnless(DUCK_ROM.is_file() and Z2_ROM.is_file(), 'ROMs required for standalone pack test')
    def test_standalone_leaves_round_clear_unpatched(self) -> None:
        prg_256k, _ = pack_duck._build_villager_hunt_banks(
            DUCK_ROM.read_bytes(),
            Z2_ROM.read_bytes(),
            pack_duck.STANDALONE_RESTORE_ADDR,
            reward_addr=pack_duck.DUCK_REWARD_ADDR,
            standalone_stub=True,
        )
        win_off = 30 * 8192 + (pack_duck.DUCK_WIN_PATCH_ADDR - 0xC000)
        self.assertEqual(prg_256k[win_off : win_off + 3], bytes.fromhex('a2 02 a4'))

    @unittest.skipUnless(DUCK_ROM.is_file() and Z2_ROM.is_file(), 'ROMs required for Barba art test')
    def test_barba_full_body_and_downstab_art(self) -> None:
        import duck_art
        art = duck_art.build_duck_chr_and_tables(DUCK_ROM.read_bytes(), Z2_ROM.read_bytes())
        # 8 poses: walk0, walk1, windup, attack, downstab, crouch, catch_windup, catch_attack
        self.assertEqual(len(art['barba_maps']), 8)
        self.assertLessEqual(art['tile_counts']['barba'], 0x70)
        # walk0 has horizontal tail tiles at negative dx (-32..-8) and 3 vertical 16px rows (dy=0..40)
        walk0 = art['barba_maps'][0]
        self.assertLessEqual(len(walk0), 24)
        self.assertTrue(any(dx >= 0xE0 for _, dx, _ in walk0))  # signed -32..-8
        self.assertTrue(any(dy == 40 for _, _, dy in walk0))
        # catch poses (6, 7) are 24x48 (3 vertical 16px rows, dy in 0..40, no tail)
        for idx in (6, 7):
            catch_pose = art['barba_maps'][idx]
            self.assertLessEqual(len(catch_pose), 18)
            self.assertTrue(all(dx < 24 and dy <= 40 for _, dx, dy in catch_pose))
            self.assertTrue(any(dy == 40 for _, _, dy in catch_pose))
        # downstab has vertical tip at dy=-48 (0xD0), 3 vertical torso chunks (0xE0, 0xF0, 0), and turned head down to dy=40
        downstab = art['barba_maps'][4]
        self.assertLessEqual(len(downstab), 28)
        self.assertTrue(any(dy == 0xD0 for _, _, dy in downstab))
        self.assertTrue(any(dy == 0xE0 for _, _, dy in downstab))
        self.assertTrue(any(dy == 0xF0 for _, _, dy in downstab))
        self.assertTrue(any(dy == 0 for _, _, dy in downstab))
        self.assertTrue(any(dy == 40 for _, _, dy in downstab))

    @unittest.skipUnless(DUCK_ROM.is_file() and Z2_ROM.is_file(), 'ROMs required for CHR score popup test')
    def test_r1_banks_preserve_score_popup_tiles(self) -> None:
        duck_bytes = DUCK_ROM.read_bytes()
        orig_f0_ff = duck_bytes[16 + 16384 + 0xF0 * 16 : 16 + 16384 + 0x100 * 16]
        _, chr_data = pack_duck.patch_duck_for_combined(
            duck_bytes,
            Z2_ROM.read_bytes(),
            0x9123,
            reward_addr=0x63B5,
        )
        for bank_kb in (14, 16):
            base = bank_kb * 1024 + 0x70 * 16
            self.assertEqual(chr_data[base : base + 0x100], orig_f0_ff)

    @unittest.skipUnless(DUCK_ROM.is_file() and Z2_ROM.is_file(), 'ROMs required for Z2 XP bag test')
    def test_barba_catch_trophy_is_z2_pbag(self) -> None:
        from boss_art import source_pair
        from nes import encode_tile

        z2_bytes = Z2_ROM.read_bytes()
        expected_rows = source_pair(z2_bytes, 0x72, 2)
        expected = encode_tile(expected_rows[0:8]) + encode_tile(expected_rows[8:16])

        _, chr_data = pack_duck.patch_duck_for_combined(
            DUCK_ROM.read_bytes(),
            z2_bytes,
            0x9123,
            reward_addr=0x63B5,
        )
        base = 14 * 1024 + 0x6E * 16
        self.assertEqual(chr_data[base : base + 32], expected)

    @unittest.skipUnless(DUCK_ROM.is_file() and Z2_ROM.is_file(), 'ROMs required for Round 2+ sky palette test')
    def test_round2_sprite_palette_table_keeps_black_sky(self) -> None:
        prg_256k, _ = pack_duck._build_villager_hunt_banks(
            DUCK_ROM.read_bytes(),
            Z2_ROM.read_bytes(),
            pack_duck.STANDALONE_RESTORE_ADDR,
            reward_addr=pack_duck.DUCK_REWARD_ADDR,
            standalone_stub=True,
        )
        # $E724..$E73B holds 3 pairs of 8-byte sprite palettes; Round 2+ ($C1 != 1)
        # unlocks $E766[4..7] which index the 3rd pair ($E734..$E73B).
        # Color 0 of every entry mirrors to $3F00 (sky), so all 6 must be $0F (black).
        off = 30 * 8192 + (0xE724 - 0xC000)
        table = prg_256k[off : off + 24]
        for pal_idx in range(6):
            self.assertEqual(table[pal_idx * 4], 0x0F, f'palette {pal_idx} color 0 was ${table[pal_idx * 4]:02X}')
