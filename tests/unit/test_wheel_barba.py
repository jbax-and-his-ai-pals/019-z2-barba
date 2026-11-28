"""ROM-free unit tests for Wheel of Barba (Round 2) packaging and combined-ROM contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import pack_wheel
import wheel_art
import wheel_puzzles
import wheel_title_audio


class WheelBarbaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.wheel_bytes = (ROOT / 'roms' / 'wheel.nes').read_bytes()
        cls.z2_bytes = (ROOT / 'roms' / 'z2.nes').read_bytes()

    def test_puzzles_and_categories_valid(self) -> None:
        self.assertEqual(len(wheel_puzzles.WHEEL_BARBA_CATEGORIES), 12)
        self.assertEqual(len(wheel_puzzles.WHEEL_BARBA_PUZZLES), 97)
        for cat_id, lines in wheel_puzzles.WHEEL_BARBA_PUZZLES:
            self.assertIn(cat_id, {0, 1, 2, 4, 7, 8})
            self.assertTrue(1 <= len(lines) <= 4)
            letters = sum(1 for ch in ''.join(lines) if ch.isalpha())
            self.assertGreaterEqual(letters, 4, f'Puzzle too short: {lines!r}')
            for line in lines:
                self.assertTrue(1 <= len(line) <= 12, line)
                enc = wheel_puzzles._encode_puzzle(cat_id, lines)
                self.assertEqual(enc[-1], cat_id)
        self.assertEqual(len(wheel_puzzles.WHEEL_BARBA_CONTESTANTS), 20)
        for name in wheel_puzzles.WHEEL_BARBA_CONTESTANTS:
            self.assertEqual(len(name), 10)

    def test_puzzles_no_self_defining_category_words(self) -> None:
        forbidden_by_cat = {
            0: {'PLACE', 'PLACES'},
            1: {'BOSS', 'BOSSES'},
            2: {'ITEM', 'ITEMS'},
            4: {'PHRASE', 'PHRASES'},
            7: {'ENEMY', 'ENEMIES'},
            8: {'SPELL', 'SPELLS'},
        }
        for cat_id, lines in wheel_puzzles.WHEEL_BARBA_PUZZLES:
            words = set(' '.join(lines).replace('-', ' ').split())
            overlap = words & forbidden_by_cat[cat_id]
            self.assertEqual(
                overlap,
                set(),
                f'Puzzle {lines!r} contains self-defining word(s) {overlap} for category {cat_id}',
            )

    def test_art_extraction(self) -> None:
        poses = wheel_art.extract_barba_frames(self.z2_bytes)
        self.assertEqual(set(poses.keys()), set(wheel_art.BARBA_POSE_ORDER))
        for name, data in poses.items():
            self.assertEqual(len(data), 192, name)
            self.assertTrue(any(data), name)
        self.assertNotEqual(poses['idle'], poses['attack'])
        self.assertNotEqual(poses['idle'], poses['up'])
        self.assertNotEqual(poses['idle'], poses['walk1'])

    def test_patch_wheel_for_combined_contract(self) -> None:
        prg = pack_wheel.patch_wheel_for_combined(
            self.wheel_bytes,
            0xC000,
            base_5ff0=0x29,
            base_5ff1=0x00,
            reward_addr=0x63B8,
        )
        self.assertEqual(len(prg), 1024 * 1024)

        # Boot bank0 must write $5FF0 = $29 (base_5ff0) and NEVER $01/$21.
        boot = prg[:8192]
        self.assertIn(bytes.fromhex('a9 29 8d f0 5f'), boot)
        self.assertNotIn(bytes.fromhex('a9 21 8d f0 5f'), boot)

        # No $5FF0 = $01 or $21 writes anywhere in the 1024KB PRG outside the $0300 exit trampoline
        # inside boot_bank0 ($8100-$84FF -> $7800-$7BFF WRAM helper).
        tramp_pat = bytes.fromhex('a9 01 8d f0 5f')
        hits = []
        idx = prg.find(tramp_pat)
        while idx != -1:
            hits.append(idx)
            idx = prg.find(tramp_pat, idx + 1)
        self.assertEqual(len(hits), 1, f'Unexpected $5FF0=$01 writes at offsets {hits}')
        self.assertLess(hits[0], 0x2000)

        self.assertEqual(prg.find(bytes.fromhex('a9 21 8d f0 5f')), -1)

        # Relocated Bonus Prize bank sits at MMC3 bank 2 ($4000-$5FFF)
        prize_bank = prg[2 * 8192 : 3 * 8192]
        self.assertNotEqual(prize_bank, b'\xFF' * 8192)

        # Bank 3 $CD48 ("FORTUNE" -> "BARBA") title audio patch
        wav_path = ROOT / 'assets' / 'wheel_barba_title.wav'
        if wav_path.exists():
            expected = wheel_title_audio.build_barba_title_packed(wav_path)
            b3_off = 3 * (256 * 1024) + 28 * 8192 + (wheel_title_audio.CLIP2_ADDR - 0x8000)
            self.assertEqual(prg[b3_off : b3_off + len(expected)], expected)

    def test_title_audio_7bit_roundtrip(self) -> None:
        samples = [(i * 17) & 0x7F for i in range(wheel_title_audio.CLIP2_SAMPLES)]
        packed = wheel_title_audio.encode_7bit(samples)
        self.assertEqual(len(packed), wheel_title_audio.CLIP2_PACKED_LEN)
        self.assertEqual(wheel_title_audio.decode_7bit(packed), samples)


if __name__ == '__main__':
    unittest.main()
