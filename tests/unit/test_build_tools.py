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


class StampPlayArtifactsTests(unittest.TestCase):
    def test_stamp_prefers_newly_built_barba_over_stale_numbered(self) -> None:
        from package_bps import collect_bps_files, stamp_play_artifacts
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            play = root / 'play'
            nes_dir = play / 'nes'
            bps_dir = play / 'bps'
            compat_nes_dir = play / 'compat' / 'nes'
            compat_bps_dir = play / 'compat' / 'bps'
            nes_dir.mkdir(parents=True)
            bps_dir.mkdir(parents=True)
            compat_nes_dir.mkdir(parents=True)
            compat_bps_dir.mkdir(parents=True)
            (play / 'barba-b811.nes').write_bytes(b'old-811-nes')
            (play / 'barba.nes').write_bytes(b'new-812-nes')
            (play / 'barba-b811.bps').write_bytes(b'old-811-bps')
            (play / 'barba.bps').write_bytes(b'new-812-bps')
            (play / 'other.nes').write_bytes(b'keep-other')
            (nes_dir / 'dk-b790.nes').write_bytes(b'old-dk')
            (nes_dir / 'dk.nes').write_bytes(b'new-dk')
            (bps_dir / 'dk-b790.bps').write_bytes(b'old-dk-bps')
            (bps_dir / 'dk.bps').write_bytes(b'new-dk-bps')
            (compat_nes_dir / 'dk-compat-b790.nes').write_bytes(b'old-dk-compat')
            (compat_nes_dir / 'dk-compat.nes').write_bytes(b'new-dk-compat')
            (compat_bps_dir / 'dk-compat-b790.bps').write_bytes(b'old-dk-compat-bps')
            (compat_bps_dir / 'dk-compat.bps').write_bytes(b'new-dk-compat-bps')

            stamp_play_artifacts(root, 812, {'dk': 791})

            self.assertFalse((play / 'barba-b811.nes').exists())
            self.assertFalse((play / 'barba.nes').exists())
            self.assertEqual((play / 'barba-b812.nes').read_bytes(), b'new-812-nes')
            self.assertEqual((play / 'barba-b812.bps').read_bytes(), b'new-812-bps')
            self.assertEqual((play / 'other.nes').read_bytes(), b'keep-other')
            self.assertFalse((nes_dir / 'dk-b790.nes').exists())
            self.assertEqual((nes_dir / 'dk-b791.nes').read_bytes(), b'new-dk')
            self.assertEqual((bps_dir / 'dk-b791.bps').read_bytes(), b'new-dk-bps')
            self.assertFalse((compat_nes_dir / 'dk-compat-b790.nes').exists())
            self.assertEqual((compat_nes_dir / 'dk-compat-b791.nes').read_bytes(), b'new-dk-compat')
            self.assertEqual((compat_bps_dir / 'dk-compat-b791.bps').read_bytes(), b'new-dk-compat-bps')
            collected = [p.name for p in collect_bps_files(root)]
            self.assertEqual(collected, ['barba-b812.bps', 'dk-b791.bps', 'dk-compat-b791.bps'])

    def test_stamp_migrates_legacy_barba_and_mmc3_names(self) -> None:
        from package_bps import collect_bps_files, stamp_play_artifacts
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            play = root / 'play'
            nes_dir = play / 'nes'
            bps_dir = play / 'bps'
            compat_nes_dir = play / 'compat' / 'nes'
            compat_bps_dir = play / 'compat' / 'bps'
            nes_dir.mkdir(parents=True)
            bps_dir.mkdir(parents=True)
            compat_nes_dir.mkdir(parents=True)
            compat_bps_dir.mkdir(parents=True)
            (play / 'barba-b812.nes').write_bytes(b'core-nes')
            (play / 'barba-b812.bps').write_bytes(b'core-bps')
            (nes_dir / 'dk-barba-b20.nes').write_bytes(b'legacy-dk')
            (nes_dir / 'dk.nes').write_bytes(b'fresh-dk')
            (bps_dir / 'dk-barba-b20.bps').write_bytes(b'legacy-dk-bps')
            (compat_nes_dir / 'dk-mmc3-b20.nes').write_bytes(b'legacy-mmc3')
            (compat_bps_dir / 'dk-mmc3-b20.bps').write_bytes(b'legacy-mmc3-bps')

            stamp_play_artifacts(root, 813, {'dk': 21})

            self.assertEqual((play / 'barba-b813.nes').read_bytes(), b'core-nes')
            self.assertEqual((play / 'barba-b813.bps').read_bytes(), b'core-bps')
            self.assertFalse((nes_dir / 'dk-barba-b20.nes').exists())
            self.assertFalse((bps_dir / 'dk-barba-b20.bps').exists())
            self.assertFalse((compat_nes_dir / 'dk-mmc3-b20.nes').exists())
            self.assertFalse((compat_bps_dir / 'dk-mmc3-b20.bps').exists())
            self.assertEqual((nes_dir / 'dk-b21.nes').read_bytes(), b'fresh-dk')
            self.assertEqual((bps_dir / 'dk-b21.bps').read_bytes(), b'legacy-dk-bps')
            self.assertEqual((compat_nes_dir / 'dk-compat-b21.nes').read_bytes(), b'legacy-mmc3')
            self.assertEqual((compat_bps_dir / 'dk-compat-b21.bps').read_bytes(), b'legacy-mmc3-bps')
            collected = [p.name for p in collect_bps_files(root)]
            self.assertEqual(collected, ['barba-b813.bps', 'dk-b21.bps', 'dk-compat-b21.bps'])

    def test_stamp_numeric_ordering_past_100(self) -> None:
        from package_bps import collect_bps_files, stamp_play_artifacts
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            play = root / 'play'
            play.mkdir(parents=True)
            (play / 'barba-b99.nes').write_bytes(b'b99')
            (play / 'barba-b100.nes').write_bytes(b'b100')
            (play / 'barba-b99.bps').write_bytes(b'b99-bps')
            (play / 'barba-b100.bps').write_bytes(b'b100-bps')

            self.assertEqual([p.name for p in collect_bps_files(root)], ['barba-b100.bps'])
            stamp_play_artifacts(root, 101)
            self.assertFalse((play / 'barba-b99.nes').exists())
            self.assertFalse((play / 'barba-b100.nes').exists())
            self.assertEqual((play / 'barba-b101.nes').read_bytes(), b'b100')

    def test_stage_release_assets_creates_individual_bps_and_collection_zips(self) -> None:
        import zipfile
        from package_bps import stage_release_assets
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            play = root / 'play'
            (play / 'bps').mkdir(parents=True)
            (play / 'compat' / 'bps').mkdir(parents=True)
            (play / 'barba-b825.bps').write_bytes(b'barba')
            (play / 'bps' / 'dk-b27.bps').write_bytes(b'dk')
            (play / 'compat' / 'bps' / 'dk-compat-b27.bps').write_bytes(b'dkc')

            out_dir, manifest = stage_release_assets(
                root,
                version='v2.0.0',
                build_number=825,
                published=False,
            )
            self.assertEqual(manifest['tag'], 'v2.0.0')
            self.assertFalse(manifest['published'])
            self.assertEqual([c['filename'] for c in manifest['collections']], [
                'barba-bps-v2.0.0-b825.zip',
                'barba-subgames-bps-v2.0.0-b825.zip',
                'barba-compat-bps-v2.0.0-b825.zip',
            ])
            self.assertEqual([p['filename'] for p in manifest['patches']], [
                'barba-b825.bps',
                'dk-b27.bps',
                'dk-compat-b27.bps',
            ])
            for name in ('barba-b825.bps', 'dk-b27.bps', 'dk-compat-b27.bps'):
                self.assertTrue((out_dir / name).is_file())
            with zipfile.ZipFile(out_dir / 'barba-bps-v2.0.0-b825.zip') as zf:
                self.assertEqual(sorted(zf.namelist()), ['barba-b825.bps', 'dk-b27.bps', 'dk-compat-b27.bps'])
            with zipfile.ZipFile(out_dir / 'barba-subgames-bps-v2.0.0-b825.zip') as zf:
                self.assertEqual(zf.namelist(), ['dk-b27.bps'])
            with zipfile.ZipFile(out_dir / 'barba-compat-bps-v2.0.0-b825.zip') as zf:
                self.assertEqual(zf.namelist(), ['dk-compat-b27.bps'])


class PlayCmdLaunchersTests(unittest.TestCase):
    def test_all_play_cmd_launchers_valid_and_in_sync(self) -> None:
        from generate_play_cmds import validate_cmds
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(validate_cmds(root), [])

    def test_no_compat_files_outside_play_compat(self) -> None:
        root = Path(__file__).resolve().parents[2]
        play = root / 'play'
        compat_dir = play / 'compat'
        stray = [
            p.relative_to(root).as_posix()
            for p in play.rglob('*-compat*')
            if compat_dir not in p.parents
        ]
        self.assertEqual(stray, [])


if __name__=='__main__':unittest.main()
