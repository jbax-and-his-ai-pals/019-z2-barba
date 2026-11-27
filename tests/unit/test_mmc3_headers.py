"""ROM-free unit tests for subgame Mapper 4 (MMC3) header generation."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

import build_mmc3  # noqa: E402
from subgame_pack import make_rom_header  # noqa: E402


class TestMmc3Headers(unittest.TestCase):
    def test_ines1_mmc3_chr_rom(self) -> None:
        hdr = make_rom_header(256 * 1024, 32 * 1024, mapper='mmc3', vertical_mirroring=True)
        self.assertEqual(hdr[0:4], b'NES\x1a')
        self.assertEqual(hdr[4], 16)
        self.assertEqual(hdr[5], 4)
        self.assertEqual(hdr[6], 0x43)  # Mapper 4 low nibble + battery + vertical mirroring
        self.assertEqual(hdr[7], 0x00)  # Classic iNES 1.0
        self.assertEqual((hdr[6] >> 4) | (hdr[7] & 0xF0), 4)

    def test_nes2_mmc3_chr_ram(self) -> None:
        hdr = make_rom_header(256 * 1024, 0, mapper='mmc3', vertical_mirroring=False, chr_ram_kb=32)
        self.assertEqual(hdr[4], 16)
        self.assertEqual(hdr[5], 0)
        self.assertEqual(hdr[6], 0x42)  # Mapper 4 + battery
        self.assertEqual(hdr[7], 0x08)  # NES 2.0
        self.assertEqual(hdr[10], 0x70)  # 8 KB battery PRG-RAM
        self.assertEqual(hdr[11], 0x09)  # 32 KB CHR-RAM

    def test_mapper_176_header_matches_legacy(self) -> None:
        hdr = make_rom_header(256 * 1024, 8192, mapper='176', vertical_mirroring=False, chr_ram_kb=32)
        self.assertEqual(hdr[4], 16)
        self.assertEqual(hdr[5], 1)
        self.assertEqual(hdr[6], 0x02)
        self.assertEqual(hdr[7], 0xB8)
        self.assertEqual(hdr[10], 0x90)
        self.assertEqual(hdr[11], 0x09)

    def test_fk23c_only_games_rejected_by_mmc3_builder(self) -> None:
        with self.assertRaises(ValueError):
            build_mmc3.build_game_mmc3('wheel')


if __name__ == '__main__':
    unittest.main()
