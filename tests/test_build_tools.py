"""Validate patch integrity and build safety without requiring a Nintendo ROM."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from bps import apply, encode
from build import Overlay
from nes import decode_tile, encode_tile, load_source, prg_offset


class PatchTests(unittest.TestCase):
    def test_round_trip_sizes_and_binary_changes(self):
        rng=random.Random(42)
        for size in [0,1,127,128,4096]:
            source=rng.randbytes(size)
            for target in (source, source+b'new', source[:size//2], bytes(size), source[::-1]):
                self.assertEqual(apply(source,encode(source,target,'test')),target)

    def test_corrupt_patch_and_wrong_source_rejected(self):
        patch=encode(b'original',b'modified')
        with self.assertRaises(ValueError): apply(b'wrong',patch)
        corrupt=bytearray(patch);corrupt[8]^=1
        with self.assertRaises(ValueError): apply(b'original',corrupt)

    def test_relocated_assets_use_source_references(self):
        source=bytes(range(256))*4
        target=source[700:900]+b'new art'+source[100:400]
        patch=encode(source,target,source_copies=[(0,700,200),(207,100,300)])
        self.assertEqual(apply(source,patch),target)
        self.assertLess(len(patch),64)
        with self.assertRaises(ValueError):encode(source,target,source_copies=[(0,0,200)])

    def test_guard_and_overlap_fail_before_mutation(self):
        overlay=Overlay(b'abcdefgh')
        with self.assertRaises(ValueError): overlay.put(0,b'XY',b'zz','wrong bytes')
        self.assertEqual(overlay.target,b'abcdefgh')
        overlay.put(1,b'XY',b'bc','first')
        with self.assertRaises(ValueError): overlay.put(2,b'ZZ',b'cd','overlap')
        self.assertEqual(overlay.target,b'aXYdefgh')

    def test_banked_addresses(self):
        self.assertEqual(prg_offset(0,0x8000),16)
        self.assertEqual(prg_offset(7,0xFFFA),0x2000A)
        with self.assertRaises(ValueError):prg_offset(7,0x8000)

    def test_2bpp_planar_round_trip(self):
        rows=['01230123','32103210']*4
        self.assertEqual(decode_tile(encode_tile(rows)),[[int(c) for c in row] for row in rows])
        with self.assertRaises(ValueError):encode_tile(['00000004']*8)


if __name__=='__main__':unittest.main()
