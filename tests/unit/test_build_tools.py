"""Validate patch integrity and build safety without requiring a Nintendo ROM."""
import json
import random
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tools'))
from bps import apply, encode, write_bps
from build import Overlay
from build_history import (
    HISTORICAL_BASELINE,
    SUBGAME_BASELINES,
    get_subgame_build_number,
    next_subgame_build_number,
    record_build,
    record_subgame_build,
)
from assets import TALL_POSES, validate_layout
import build as builder
from nes import decode_tile, encode_tile, load_source, prg_offset


class BuildHistoryTests(unittest.TestCase):
    def test_rebuilds_share_sequence_and_failed_reports_do_not_consume_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history = root / 'history.sqlite3'
            metadata = {'output_dir': 'build', 'bps_sha256': 'patch', 'audio': 'sampled',
                        'waldo_portal': True, 'git_commit': None, 'git_dirty': None,
                        'release': None}
            report = {'output_sha256': 'same-rom'}
            record_build(history, root, report.copy(), metadata)
            with self.assertRaises(FileNotFoundError):
                record_build(history, root / 'missing', report.copy(), metadata)
            alternate = root / 'alternate'
            alternate.mkdir()
            record_build(history, alternate, report.copy(),
                         {**metadata, 'output_dir': 'alternate', 'release': 'example'})

            first = HISTORICAL_BASELINE + 1
            with closing(sqlite3.connect(history)) as connection:
                rows = connection.execute(
                    'SELECT build_number, output_sha256, release FROM builds ORDER BY build_number'
                ).fetchall()
            self.assertEqual(rows, [(first, 'same-rom', None), (first + 1, 'same-rom', 'example')])
            self.assertEqual(json.loads((alternate / 'build-report.json').read_text())['build_number'],
                             first + 1)

    def test_subgame_builds_track_independently_from_z2(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history = root / 'history.sqlite3'
            self.assertEqual(get_subgame_build_number(history, 'dk'), SUBGAME_BASELINES['dk'])
            next_dk = next_subgame_build_number(history, 'dk')
            self.assertEqual(next_dk, SUBGAME_BASELINES['dk'] + 1)
            record_subgame_build(history, 'dk', next_dk, '176', root / 'dk.nes', 'dk-sha')
            self.assertEqual(get_subgame_build_number(history, 'dk'), next_dk)
            self.assertEqual(get_subgame_build_number(history, 'duck'), SUBGAME_BASELINES['duck'])


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

    def test_write_bps_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = root / 'source.nes'
            tgt = root / 'sub' / 'target.nes'
            tgt.parent.mkdir()
            src.write_bytes(b'NES\x1a' + bytes(range(128)))
            tgt.write_bytes(b'NES\x1a' + bytes(reversed(range(128))))
            bps_path = write_bps(src, tgt, metadata='unit test')
            self.assertEqual(bps_path, tgt.with_suffix('.bps'))
            self.assertEqual(apply(src.read_bytes(), bps_path.read_bytes()), tgt.read_bytes())

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

    def test_distributable_tall_layout_without_rom(self):
        root = Path(__file__).resolve().parents[2]
        layout = validate_layout(root)
        self.assertEqual(len(layout), len(TALL_POSES)*9)
        # The recipe must reject an accidental weapon-slot overwrite even in
        # public CI, which deliberately has no original game pixels available.
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            (fixture/'src').mkdir()
            text = (root/'src/tall_layout.inc').read_text()
            (fixture/'src/tall_layout.inc').write_text(text.replace('$00', '$32', 1))
            with self.assertRaisesRegex(ValueError, 'reserved'):
                validate_layout(fixture)

    def test_build_generates_layout_before_assembly_and_forwards_rom(self):
        with tempfile.TemporaryDirectory() as directory:
            location = Path(directory)
            source = location/'custom-source.nes'
            with patch.object(builder, 'load_source', return_value=b'original'), \
                 patch.object(builder, 'compile_assets', side_effect=ValueError('asset sentinel')) as assets, \
                 patch.object(builder, 'assemble') as assembler:
                with self.assertRaisesRegex(ValueError, 'asset sentinel'):
                    builder.build(source, location/'output')
                assets.assert_called_once_with(builder.ROOT, source)
                assembler.assert_not_called()

    def test_shout_glyph_layout_matches_audited_pairs(self):
        import re
        from assets import SHOUT_PAIR_SHA256, TOWN_SPRITE_PAIRS
        root = Path(__file__).resolve().parents[2]
        text = (root/'src/shout_layout.inc').read_text()
        tiles = [int(v, 16) for v in re.findall(r'^ShoutTile_\w+\s*=\s*\$([0-9A-F]{2})', text, re.MULTILINE)]
        # Odd bytes read town BG bank 7 ($1000); even bytes read town sprite bank 6 ($0000).
        keys = sorted((7 if tile % 2 else 6, tile & 0xFE) for tile in tiles)
        self.assertEqual(keys, sorted(SHOUT_PAIR_SHA256))
        # Never the native font/dialog range or sprite 0's $C4/$C5 pair.
        self.assertTrue(all((tile & 0xFE) < 0xC4 for tile in tiles))
        # 8x16 bytes draw a whole pair: never a pair a town villager sprite uses.
        for bank, pair in keys:
            self.assertNotIn(pair, TOWN_SPRITE_PAIRS[bank], f'glyph overwrites villager pair {bank}:{pair:02X}')


if __name__=='__main__':unittest.main()
