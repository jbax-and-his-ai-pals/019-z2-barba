"""ROM-free unit tests for tools/feud_art.py."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import feud_art
import feud_cast
import feud_engine
import feud_wram
from nes import encode_tile

ROOT = Path(__file__).resolve().parents[2]
Z2_ROM = ROOT / 'roms' / 'z2.nes'


class FeudArtTests(unittest.TestCase):
    def test_index_mapping_and_outline(self):
        mapped = feud_art._to_feud_indices(['0123'], flip_h=True)
        self.assertEqual(mapped, ['1120'])
        outlined = feud_art._add_outline([list('0000'), list('0210'), list('0000')])
        self.assertEqual([''.join(r) for r in outlined], ['0330', '3213', '0330'])

    def test_pack_bank_dedup_protected_and_row0_priority(self):
        chr_buf = bytearray(16 * 4096)
        # Seed protected tile 0xE1 in bank 2
        prot_rows = ['2' * 8 for _ in range(8)]
        chr_buf[2 * 4096 + 0xE1 * 16 : 2 * 4096 + 0xE2 * 16] = encode_tile(prot_rows)

        # Two blocks: row 0 is identical, row 1 reuses protected tile 0xE1
        block_a = ['1' * 8 for _ in range(8)] + ['2' * 8 for _ in range(8)]
        block_b = ['1' * 8 for _ in range(8)] + ['0' * 8 for _ in range(8)]
        packed = feud_art._pack_bank(
            chr_buf,
            2,
            [0x10, 0x85],
            {0: block_a, 1: block_b},
            protected_pool_tiles=[0xE1],
            row0_priority=True,
        )
        self.assertEqual(packed[0], [0x10, 0xE1])
        self.assertEqual(packed[1], [0x10, 0x00])
        # Protected tile stays intact and unused 0x85 stays zeroed
        self.assertEqual(chr_buf[2 * 4096 + 0xE1 * 16 : 2 * 4096 + 0xE2 * 16], encode_tile(prot_rows))
        self.assertEqual(chr_buf[2 * 4096 + 0x85 * 16 : 2 * 4096 + 0x86 * 16], b'\x00' * 16)

    def test_pack_bank_overflow_raises(self):
        chr_buf = bytearray(4096)
        block = ['1' * 8 for _ in range(8)] + ['2' * 8 for _ in range(8)]
        with self.assertRaises(ValueError):
            feud_art._pack_bank(chr_buf, 0, [0x04], {0: block})

    def test_zelda_family_names_and_lose_reasons(self):
        names = feud_engine.ZELDA_FAMILY_NAMES
        self.assertGreaterEqual(len(names), 16)
        self.assertLessEqual(len(names), 32)
        self.assertEqual(len(names), len(set(names)))
        self.assertIn('BARBA', names)
        for name in names:
            self.assertTrue(1 <= len(name) <= 7, f'Name too long: {name}')
            self.assertTrue(all('A' <= c <= 'Z' for c in name), name)

        reasons = feud_engine.LOSE_REASONS
        self.assertEqual(len(reasons), 7)
        expected_substrings = [
            'lava', 'Return of Ganon', 'missing Triforce',
            'Attack 9', 'not knowing Bagu', 'missing eco-key', 'softlocking',
        ]
        for sub, msg in zip(expected_substrings, reasons):
            self.assertIn(sub, msg)
            encoded = feud_engine._encode_chr0b_blue(msg)
            self.assertEqual(len(encoded), len(msg))
        self.assertEqual(feud_engine.CHR0B_BLUE_MAP['k'], 0xB4)

    def test_wram_and_bank4_assembly_fit(self):
        wram_bytes, wram_syms = feud_wram.assemble_wram_extra()
        self.assertLessEqual(len(wram_bytes), 0x0500)
        for sym in (
            'W_CALL_B4', 'W_SYNC_CHR', 'W_PICK_Z2_NAME', 'W_DEFAULT_P1_NAME',
            'W_WRITE_STAGE_ATTR', 'W_WRITE_OV_ATTR', 'W_FACEOFF_ATTR',
            'W_ZELDA_LOSE', 'W_ROLL_BOTH', 'W_ROLL_P1', 'W_ROLL_CPU',
            'W_NMI_IDLE_TICK', 'nit_ov_tick',
        ):
            self.assertIn(sym, wram_syms, f'Missing WRAM symbol {sym}')
        # W_NMI_IDLE_TICK must include Name Select ($0345 == $04) alongside $0D/$0E
        nit_off = wram_syms['W_NMI_IDLE_TICK'] - feud_engine.WRAM_EXTRA_ORG
        nit_end = wram_syms['nit_rst'] - feud_engine.WRAM_EXTRA_ORG
        self.assertIn(bytes.fromhex('C904'), wram_bytes[nit_off:nit_end])

        synth_cast = {
            'ov_free': bytes(range(120)),
            'st_p1_free': bytes(range(180)),
            'st_cpu_free': bytes(range(170)),
            'fo_p1_free': bytes(range(72)),
            'fo_cpu_free': bytes(range(72)),
            'fo_cpu_lip_ids': bytes([0x80, 0x81, 0x82]),
            'fo_cpu_lip_tiles': bytes(48),
            'fo_p1_bot2': bytes([0x01] * 40),
            'fo_cpu_bot2': bytes([0xEB] * 12),
            'barba_meta': [(16, 0x8000 + i * 0x100) for i in range(14 * 3)],
            'z2_meta': [(18, 0x8000 + i * 0x100) for i in range(16 * 3)],
        }
        bank4 = feud_engine._assemble_bank4(synth_cast)
        self.assertLessEqual(len(bank4), 0x1700)

        celeb_bytes, celeb_syms = feud_wram.assemble_celeb_wram()
        self.assertLessEqual(len(celeb_bytes), 0x0400)
        for sym in (
            'W_APPLY_SCROLL', 'W_CELEB_INIT', 'W_CELEB_SET_TIMER',
            'W_CELEB_HEAD_TILT_TICK', 'W_CELEB_ROAR_PHASE', 'W_CELEB_SPLIT',
            'W_AMB_ROAR_TICK', 'W_AMB_ROAR_STOP', 'W_AMB_ROAR_MAYBE',
        ):
            self.assertIn(sym, celeb_syms, f'Missing celeb WRAM symbol {sym}')
        # Upper 256 KB PRG bank switch in 256 KB MMC3 mode ($5FF0=$01/$21) requires $5FF1=$10, not $01.
        self.assertNotIn(bytes.fromhex('A9018DF15F'), celeb_bytes)
        self.assertEqual(celeb_bytes.count(bytes.fromhex('A9108DF15F')), 2)

    def test_overview_split_hblank_timing(self):
        import pack_feud
        _, wram_syms = feud_wram.assemble_wram_extra()
        _, pal_syms = feud_wram.assemble_pal_wram()
        wram_code = pack_feud.assemble_feud_wram_code(
            0x0000,
            standalone_stub=True,
            wram_syms={**wram_syms, **pal_syms},
        )
        # c0_fast0 must set R0=0 and R1=2 before switching $5FF0=$21 so R1 never lags past sl=127 HBlank.
        r0_seq = bytes.fromhex('8D00808D0180')
        r1_seq = bytes.fromhex('A9018D00800A8D0180')
        ram_seq = bytes.fromhex('A9218DF05F')
        self.assertIn(r0_seq + r1_seq + ram_seq, wram_code[:0x20])

        feud_rom = ROOT / 'roms' / 'feud.nes'
        if feud_rom.is_file() and Z2_ROM.is_file():
            raw = feud_rom.read_bytes()
            prg_out, _ = pack_feud.patch_feud_prg_and_chr(
                raw[16 : 16 + 32768],
                raw[16 + 32768 : 16 + 32768 + 131072],
                Z2_ROM.read_bytes(),
                standalone=True,
                wram_syms={**wram_syms, **pal_syms},
            )
            for addr in (0x8153, 0x8194):
                off = addr - 0x8000
                self.assertEqual(prg_out[off : off + 5], bytes.fromhex('A2B5CAD0FD'))

    @unittest.skipUnless(Z2_ROM.exists(), 'roms/z2.nes not present')
    def test_cast_pools_tile_budgets(self):
        z2 = Z2_ROM.read_bytes()
        barba_pool, z2_pool = feud_cast.build_all_cast_pools(z2, feud_cast.build_default_config())
        self.assertEqual(len(barba_pool), 13)
        self.assertEqual(len(z2_pool), 33)
        self.assertTrue(all(c.char_id.startswith('barba_') and 'link' not in c.char_id for c in barba_pool))
        self.assertTrue({'z2_link', 'z2_lavalink'} <= {c.char_id for c in z2_pool})
        for pool, max_st, fo_map_len in ((barba_pool, 36, 140), (z2_pool, 34, 120)):
            for char in pool:
                self.assertEqual(len(char.variants), 3)
                for h_idx, var in enumerate(char.variants):
                    self.assertLessEqual(
                        len(var.stage_tiles), max_st * 16,
                        f'{char.char_id} h={h_idx} stage tiles exceeded {max_st}',
                    )
                    self.assertEqual(len(var.stage_maps), 72)
                    self.assertLessEqual(var.ov_row0_count, 4)
                    self.assertEqual(len(var.ov_maps), 16)
                    self.assertEqual(len(var.fo_maps), fo_map_len)

    @unittest.skipUnless(Z2_ROM.exists(), 'roms/z2.nes not present')
    def test_cast_config_filtering_and_export(self):
        z2 = Z2_ROM.read_bytes()
        cfg = feud_cast.load_cast_config()
        self.assertEqual(len(cfg['characters']), 46)
        excluded = {c['id'] for c in cfg['characters'] if not c['included']}
        self.assertEqual(excluded, {'z2_moblin', 'z2_rebonack'})
        dl = next(c for c in cfg['characters'] if c['id'] == 'z2_darklink')
        self.assertEqual(dl['mapping'], '333')
        self.assertFalse(dl['outline'])

        barba_cur, z2_cur = feud_cast.build_all_cast_pools(z2, cfg)
        self.assertEqual(len(barba_cur), 13)
        self.assertEqual(len(z2_cur), 31)

        # Exclude all but 5 from each pool and customize a Z2 character mapping/slot
        cfg_sub = feud_cast.build_default_config()
        b_kept = 0
        z_kept = 0
        for ch in cfg_sub['characters']:
            if ch['pool'] == 'barba':
                ch['included'] = b_kept < 5
                if ch['included']:
                    b_kept += 1
            else:
                ch['included'] = z_kept < 5
                if ch['included']:
                    ch['pal_slot'] = 2
                    ch['mapping'] = '123'
                    ch['outline'] = False
                    z_kept += 1
        barba_pool, z2_pool = feud_cast.build_all_cast_pools(z2, cfg_sub)
        self.assertEqual(len(barba_pool), 5)
        self.assertEqual(len(z2_pool), 5)
        rt = feud_cast.get_runtime_cast_tables(cfg_sub)
        self.assertEqual(rt['z2_pal_slots'], [2, 2, 2, 2, 2])
        self.assertEqual(len(rt['barba_pal_pairs']), 12)
        self.assertEqual(len(rt['z2_pal_pairs']), 12)

        dash = feud_cast.export_dashboard_sprites(z2)
        self.assertEqual(len(dash), 46)
        self.assertEqual(len(dash[0]['raw_frames'][0]), 32 * 48)
        self.assertEqual(len(dash[0]['raw_frames_top'][0]), 32 * 48)
        waldo_dash = next(d for d in dash if d['id'] == 'barba_waldo')
        # Top hat row (y=1) is shifted right onto Barba's head (starts at x=15, outline at x=14)
        row1 = waldo_dash['raw_frames'][0][32:64]
        self.assertEqual(row1.index('2'), 17)
        z2_dash = [d for d in dash if d['pool'] == 'z2']
        self.assertEqual(len(z2_dash[0]['raw_frames_top'][0]), 32 * 48)
        self.assertEqual(len(z2_dash[0]['y_keeps_top']), 3)

    @unittest.skipUnless(Z2_ROM.exists(), 'roms/z2.nes not present')
    def test_darklink_always_black_and_waldo_hat(self):
        from nes import decode_tile
        z2 = Z2_ROM.read_bytes()
        cfg = feud_cast.load_cast_config()
        barba_pool, z2_pool = feud_cast.build_all_cast_pools(z2, cfg)
        dl_char = next(c for c in z2_pool if c.char_id == 'z2_darklink')
        for var in dl_char.variants:
            for tile_bytes in (var.stage_tiles, var.ov_tiles):
                for off in range(0, len(tile_bytes), 16):
                    dec = decode_tile(tile_bytes[off : off + 16])
                    self.assertTrue(all(px in (0, 3) for r in dec for px in r))
            # Check Dark Link's character rows (0..7) in Face-Off (rows 8..9 hold the Pal 0 riser box)
            char_tids = {t for t in (var.fo_maps[0:48] + var.fo_maps[60:108]) if t != 0}
            for tid in char_tids:
                off = (tid - 1) * 16
                dec = decode_tile(var.fo_tiles[off : off + 16])
                self.assertTrue(all(px in (0, 3) for r in dec for px in r))
        self.assertTrue(any(c.char_id == 'barba_waldo' for c in barba_pool))

    @unittest.skipUnless(Z2_ROM.exists(), 'roms/z2.nes not present')
    def test_top_half_sprite_type_budgets(self):
        z2 = Z2_ROM.read_bytes()
        cfg = feud_cast.build_default_config()
        for ch in cfg['characters']:
            self.assertEqual(ch['sprite_type'], 'full')
            ch['sprite_type'] = 'top_half'
        barba_pool, z2_pool = feud_cast.build_all_cast_pools(z2, cfg)
        self.assertEqual(len(barba_pool), 13)
        self.assertEqual(len(z2_pool), 33)
        for pool, max_st, fo_map_len in ((barba_pool, 36, 140), (z2_pool, 34, 120)):
            for char in pool:
                for var in char.variants:
                    self.assertLessEqual(len(var.stage_tiles), max_st * 16)
                    self.assertEqual(len(var.stage_maps), 72)
                    self.assertLessEqual(var.ov_row0_count, 4)
                    self.assertEqual(len(var.ov_maps), 16)
                    self.assertEqual(len(var.fo_maps), fo_map_len)

    def test_feud_puzzles_and_town_synonyms(self):
        import pack_feud

        def expand_variants(raw: str) -> list[str]:
            # Mirror $FE56 normalization followed by $FA00 paren/slash expansion
            norm = ['(']
            for i, ch in enumerate(raw):
                if 'a' <= ch <= 'z':
                    norm.append('(/' + ch.upper() + ')')
                elif ch == '*':
                    nxt = raw[i + 1] if i + 1 < len(raw) else ''
                    norm.append('(/*)' if nxt == ' ' else '(/* )')
                elif ch == '+':
                    norm.append('(/ )')
                elif ch == '[':
                    norm.append('(/')
                elif ch in (']', ')'):
                    norm.append(')')
                else:
                    norm.append(ch)
            norm.append(')')
            s = ''.join(norm)

            def _expand(expr: str) -> list[str]:
                if '(' not in expr:
                    return [expr]
                l = expr.index('(')
                depth = 0
                r = -1
                parts: list[str] = []
                cur: list[str] = []
                for idx in range(l + 1, len(expr)):
                    c = expr[idx]
                    if c == '(':
                        depth += 1
                        cur.append(c)
                    elif c == ')':
                        if depth == 0:
                            parts.append(''.join(cur))
                            r = idx
                            break
                        depth -= 1
                        cur.append(c)
                    elif c == '/' and depth == 0:
                        parts.append(''.join(cur))
                        cur = []
                    else:
                        cur.append(c)
                assert r != -1, f'Unbalanced parens in {expr!r}'
                prefix = expr[:l]
                suffix_opts = _expand(expr[r + 1:])
                out: list[str] = []
                for p in parts:
                    for po in _expand(p):
                        for so in suffix_opts:
                            out.append(prefix + po + so)
                return out

            seen: list[str] = []
            for v in _expand(s):
                if v not in seen:
                    seen.append(v)
            return seen

        total_bytes = 0
        seen_vecs: set[tuple[int, ...]] = set()
        for pool in (pack_feud.ZELDA2_MAIN_PUZZLES, pack_feud.ZELDA2_FM_PUZZLES):
            for p_idx, q_str, answers in pool:
                rec = pack_feud.encode_puzzle(p_idx, q_str, answers)
                self.assertLess(len(rec), 256, q_str)
                total_bytes += len(rec)
                pts = [p for _ans, p in answers]
                self.assertEqual(sum(pts), 100, q_str)
                self.assertTrue(all(pts[i] >= pts[i + 1] for i in range(len(pts) - 1)), q_str)
                self.assertGreaterEqual(pts[-1], 2, q_str)
                self.assertFalse(all(p % 5 == 0 for p in pts), q_str)
                seen_vecs.add(tuple(pts))
                for ans_text, _pts in answers:
                    variants = expand_variants(ans_text)
                    self.assertLessEqual(len(variants), 20, f'{q_str}: {ans_text} -> {len(variants)} variants')
                    buf_len = sum(len(v) + 1 for v in variants)
                    self.assertLess(buf_len, 256, f'{q_str}: {ans_text} buffer {buf_len}')
        self.assertEqual(len(seen_vecs), len(pack_feud.ZELDA2_MAIN_PUZZLES) + len(pack_feud.ZELDA2_FM_PUZZLES))
        self.assertLessEqual(total_bytes, 4096)

        town_q = next(a for _p, q, a in pack_feud.ZELDA2_MAIN_PUZZLES if q == 'FOUND IN A TOWN')
        villager_ans, pts = town_q[0]
        self.assertEqual(pts, 34)
        town_variants = expand_variants(villager_ans)
        for accepted in ('HEALER', 'LADY', 'TOWN LADY', 'VILLAGER', 'VILLAGERS', 'PEOPLE'):
            self.assertIn(accepted, town_variants)

        triforce_q = next(a for _p, q, a in pack_feud.ZELDA2_MAIN_PUZZLES if q == 'THAT GUARDS THE TRIFORCE')
        old_man_ans, old_man_pts = triforce_q[2]
        self.assertEqual(old_man_pts, 13)
        triforce_variants = expand_variants(old_man_ans)
        for accepted in ('OLD MAN', 'SAGE', 'IMPA'):
            self.assertIn(accepted, triforce_variants)

        enc_q = next(a for _p, q, a in pack_feud.ZELDA2_MAIN_PUZZLES if q == 'OVERWORLD TILE THAT SPAWNS ENCOUNTERS')
        self.assertEqual(sum(pts for _ans, pts in enc_q), 100)
        enc_variants = [v for ans, _pts in enc_q for v in expand_variants(ans)]
        for accepted in ('GRASS', 'SWAMP', 'DESERT', 'FOREST', 'GRAVEYARD', 'LAVA'):
            self.assertIn(accepted, enc_variants)


if __name__ == '__main__':
    unittest.main()
