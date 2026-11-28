"""Unit tests for fe_catalog and standardized public/local dashboard builds."""
from __future__ import annotations

import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_dashboard  # noqa: E402
import capture_subgame_previews  # noqa: E402
import fe_catalog  # noqa: E402
import title_dashboard  # noqa: E402
import z2_strings_dashboard  # noqa: E402


class TestFeCatalog(unittest.TestCase):
    def test_unique_ids_and_two_char_codes(self) -> None:
        ids = [f["id"] for f in fe_catalog.FLAGS]
        codes = [f["code"] for f in fe_catalog.FLAGS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(codes), len(set(codes)))
        for code in codes:
            self.assertEqual(len(code), 2, f"Expected 2-char code, got {code!r}")

    def test_upstab_downstab_and_new_barba_features_present(self) -> None:
        expected = {
            "upstab_breath",
            "downstab_stomp",
            "overworld_barba_trail",
            "hud_and_death_polish",
            "cave_firelight",
            "burned_signs",
            "ngplus_mountain_melt",
            "enemy_polish",
            "arcade_spells_and_gear",
            "title_screen",
            "ending_sequence",
            "overworld_scenery",
            "scanline_scenery",
        }
        self.assertTrue(expected.issubset(fe_catalog.FLAG_BY_ID.keys()))
        for fid in ("title_screen", "ending_sequence", "overworld_scenery", "scanline_scenery"):
            p = fe_catalog.FLAG_BY_ID[fid]["preview"]
            self.assertIn("off", p)
            self.assertIn("on", p)

    def test_flagstring_round_trip_and_coupling(self) -> None:
        for preset in ("vanilla", "barba", "barba_lite", "chaos"):
            vals = fe_catalog.preset_values(preset)
            fs = fe_catalog.encode_flagstring(vals, "TESTSEED")
            decoded, seed = fe_catalog.decode_flagstring(fs)
            self.assertEqual(seed, "TESTSEED")
            self.assertEqual(decoded, vals)

        # Turning off crossover_portals should auto-disable arcade_spells_and_gear
        vals = fe_catalog.preset_values("barba")
        vals["crossover_portals"] = False
        resolved, notes = fe_catalog.resolve_flags(vals)
        self.assertFalse(resolved["arcade_spells_and_gear"])
        self.assertTrue(any("arcade_spells_and_gear" in n for n in notes))


class TestDashboardBuilder(unittest.TestCase):
    def test_public_and_local_flavors_from_shared_template(self) -> None:
        template = build_dashboard.TEMPLATE_PATH.read_text(encoding="utf-8")
        public_html = build_dashboard.render_flavor(template, "public")
        local_html = build_dashboard.render_flavor(template, "local")

        self.assertIn('window.BARBA_DASHBOARD_FLAVOR = "public";', public_html)
        self.assertIn('window.BARBA_DASHBOARD_FLAVOR = "local";', local_html)

        # Public flavor is presentation-only: no internal dev tabs/scripts/CLI box and uses public data files
        for marker in (
            'id="view-waldo"',
            'id="view-feud"',
            'id="view-duck"',
            'id="view-z2strings"',
            "waldo_tagger.js",
            "feud_cast_ui.js",
            "duck_tiles_ui.js",
            "z2_strings_ui.js",
            "local_state.js",
            "local_catalog.js",
            "local_subgames_data.js",
            "local_title_review_data.js",
            "local_z2_strings_data.js",
            'id="cli-cmd"',
            'id="seed-input"',
            'id="flagstring"',
            'id="presets"',
            'aria-label="Seed and Flagstring"',
            "Live Build Preview",
        ):
            self.assertNotIn(marker, public_html, f"Public HTML should not contain {marker}")

        for marker in ('src="catalog.js"', 'src="title_review_data.js"', 'src="subgames_data.js"', '>Overview<', 'id="view-overview"', '>Summary<', 'Barba Edition', '>Zelda 2<', '>All Title Screens<'):
            self.assertIn(marker, public_html)

        # Local flavor has all internal dev tools, state bar, and local data files
        for marker in (
            'id="view-waldo"',
            'id="view-feud"',
            'id="view-duck"',
            'id="view-z2strings"',
            "waldo_tagger.js",
            "feud_cast_ui.js",
            "duck_tiles_ui.js",
            "z2_strings_ui.js",
            "local_state.js",
            "local_catalog.js",
            "local_subgames_data.js",
            "local_title_review_data.js",
            "local_z2_strings_data.js",
            'id="cli-cmd"',
            'id="seed-input"',
            'id="flagstring"',
            'id="presets"',
            'aria-label="Seed and Flagstring"',
            'id="local-build-bar"',
            '>Summary<',
        ):
            self.assertIn(marker, local_html, f"Local HTML missing {marker}")

        # Neither flavor should have unreplaced placeholders
        self.assertNotIn("{{", public_html)
        self.assertNotIn("{{", local_html)

        # Done Title Screens strip should not appear in either flavor
        for marker in ("Done Title Screens", "titles-done-strip"):
            self.assertNotIn(marker, public_html)
            self.assertNotIn(marker, local_html)

        # Non-visual options must be grouped in their own section below animated cards
        self.assertIn("Non-Visual Options, Audio & Tunables", public_html)
        self.assertIn("Non-Visual Options, Audio & Tunables", local_html)

        # ROM Patcher removed; Title Screens kept; public subgame tabs in public, all subgame tabs in local
        for html in (public_html, local_html):
            self.assertNotIn('data-tab="patcher"', html)
            self.assertNotIn('id="view-patcher"', html)
            self.assertNotIn("bps.js", html)
            self.assertIn('data-tab="titles"', html)
            self.assertIn('id="view-titles"', html)
            self.assertIn("subgames_ui.js", html)

        for g in build_dashboard.subgame_tabs_for_flavor("public"):
            gid = g["id"]
            self.assertIn(f'data-tab="sub-{gid}"', public_html)
            self.assertIn(f'id="view-sub-{gid}"', public_html)
        for g in build_dashboard.subgame_tabs_for_flavor("local"):
            gid = g["id"]
            self.assertIn(f'data-tab="sub-{gid}"', local_html)
            self.assertIn(f'id="view-sub-{gid}"', local_html)

    def test_whole_game_and_title_visibility_filtering(self) -> None:
        template = build_dashboard.TEMPLATE_PATH.read_text(encoding="utf-8")
        synthetic_games = [
            {
                "id": "pubgame",
                "tab_label": "Public Game",
                "name": "Public Game",
                "original": "Orig",
                "summary": "Public summary",
                "scenes": [
                    ("s1", "S1", "Desc", 256, 224, 24, 12, "V", "M"),
                    ("s2", "S2", "Hidden", 256, 224, 24, 12, "V", "M", {"visibility": "local"}),
                ],
            },
            {
                "id": "secretgame",
                "tab_label": "Secret Game",
                "name": "Secret Game",
                "original": "Orig 2",
                "summary": "Secret summary",
                "visibility": "local",
                "scenes": [
                    ("s1", "S1", "Desc", 256, 224, 24, 12, "V", "M"),
                ],
            },
        ]
        pub_html = build_dashboard.render_flavor(template, "public", subgames=synthetic_games)
        loc_html = build_dashboard.render_flavor(template, "local", subgames=synthetic_games)

        self.assertIn('data-tab="sub-pubgame"', pub_html)
        self.assertNotIn('data-tab="sub-secretgame"', pub_html)
        self.assertNotIn('id="view-sub-secretgame"', pub_html)

        self.assertIn('data-tab="sub-secretgame"', loc_html)
        self.assertIn("is-local-only", loc_html)
        self.assertIn('<span class="tab-local-pill">Local</span>', loc_html)

        pub_sub = capture_subgame_previews.build_subgames_payload(include_local=False, games=synthetic_games)
        loc_sub = capture_subgame_previews.build_subgames_payload(include_local=True, games=synthetic_games)
        self.assertEqual([g["id"] for g in pub_sub["games"]], ["pubgame"])
        self.assertEqual([s["id"] for s in pub_sub["games"][0]["scenes"]], ["s1"])
        self.assertEqual([g["id"] for g in loc_sub["games"]], ["pubgame", "secretgame"])
        self.assertEqual(loc_sub["games"][0]["scenes"][1]["visibility"], "local")
        self.assertEqual(loc_sub["games"][1]["visibility"], "local")

        synthetic_titles = {
            "version": 2,
            "games": [
                {
                    "id": "g1",
                    "name": "G1",
                    "original": "O1",
                    "build_number": 1,
                    "status_label": "Build #1",
                    "summary": "S",
                    "screens": [
                        {"id": "pub", "title": "Pub", "vanilla": {}, "ours": {}},
                        {"id": "sec", "title": "Sec", "vanilla": {}, "ours": {}, "visibility": "local"},
                    ],
                },
                {
                    "id": "g2",
                    "name": "G2",
                    "original": "O2",
                    "build_number": 2,
                    "status_label": "Build #2",
                    "summary": "S2",
                    "visibility": "local",
                    "screens": [{"id": "s", "title": "S", "vanilla": {}, "ours": {}}],
                },
            ],
        }
        pub_tit = title_dashboard.title_catalog_payload(include_local=False, catalog_override=synthetic_titles)
        loc_tit = title_dashboard.title_catalog_payload(include_local=True, catalog_override=synthetic_titles)
        self.assertEqual([g["id"] for g in pub_tit["games"]], ["g1"])
        self.assertEqual([s["id"] for s in pub_tit["games"][0]["screens"]], ["pub"])
        self.assertEqual([g["id"] for g in loc_tit["games"]], ["g1", "g2"])

    def test_local_tabs_ordered_by_published_local_and_archived(self) -> None:
        import re

        template = build_dashboard.TEMPLATE_PATH.read_text(encoding="utf-8")
        synthetic_games = [
            {
                "id": "archgame",
                "tab_label": "Archived Game",
                "name": "Archived Game",
                "original": "Orig A",
                "summary": "Archived summary",
                "visibility": "local",
                "archived": True,
                "scenes": [("s1", "S1", "Desc", 256, 224, 24, 12, "V", "M")],
            },
            {
                "id": "pubgame",
                "tab_label": "Public Game",
                "name": "Public Game",
                "original": "Orig P",
                "summary": "Public summary",
                "scenes": [("s1", "S1", "Desc", 256, 224, 24, 12, "V", "M")],
            },
            {
                "id": "locgame",
                "tab_label": "Local Game",
                "name": "Local Game",
                "original": "Orig L",
                "summary": "Local summary",
                "visibility": "local",
                "scenes": [("s1", "S1", "Desc", 256, 224, 24, 12, "V", "M")],
            },
        ]
        loc_html = build_dashboard.render_flavor(template, "local", subgames=synthetic_games)
        nav_match = re.search(r'<nav class="tab-bar"[^>]*>(.*?)</nav>', loc_html, re.DOTALL)
        self.assertIsNotNone(nav_match)
        tab_ids = re.findall(r'data-tab="([^"]+)"', nav_match.group(1))
        self.assertEqual(
            tab_ids,
            [
                "overview",
                "fe",
                "sub-pubgame",
                "sub-locgame",
                "z2strings",
                "owtiles",
                "waldo",
                "feud",
                "duck",
                "sub-archgame",
                "titles",
            ],
        )

    def test_stage_pages_bundle_excludes_local_only_files_and_previews(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage_dir = Path(tmp) / "_site"
            build_dashboard.stage_pages_bundle(stage_dir)

            self.assertTrue((stage_dir / "index.html").is_file())
            self.assertTrue((stage_dir / "subgames_data.js").is_file())
            self.assertTrue((stage_dir / "catalog.js").is_file())
            self.assertTrue((stage_dir / "title_review_data.js").is_file())
            self.assertTrue((stage_dir / "previews" / "subgames" / "waldo_title_modded.png").is_file())

            # Local-only HTML/JS and dev tools must never be staged
            for forbidden in (
                "local.html",
                "local_state.js",
                "local_catalog.js",
                "local_subgames_data.js",
                "local_title_review_data.js",
                "local_z2_strings_data.js",
                "waldo_tagger.js",
                "feud_cast_ui.js",
                "duck_tiles_ui.js",
                "z2_strings_ui.js",
            ):
                self.assertFalse((stage_dir / forbidden).exists(), f"Staged Pages bundle should omit {forbidden}")


class TestSubgamesData(unittest.TestCase):
    def test_subgames_data_and_png_sheets(self) -> None:
        data_path = ROOT / "web" / "subgames_data.js"
        self.assertTrue(data_path.is_file(), f"Missing {data_path}")
        raw = data_path.read_text(encoding="utf-8").strip()
        prefix = "window.BARBA_SUBGAMES_DATA = "
        self.assertTrue(raw.startswith(prefix))
        self.assertTrue(raw.endswith(";"))
        payload = json.loads(raw[len(prefix) : -1])

        expected_ids = [g["id"] for g in build_dashboard.subgame_tabs_for_flavor("public")]
        self.assertEqual([g["id"] for g in payload["games"]], expected_ids)

        full_payload = capture_subgame_previews.build_subgames_payload(include_local=True)

        for game in full_payload["games"]:
            scenes = game["scenes"]
            self.assertGreaterEqual(len(scenes), 3, f"{game['id']} should have >= 3 scenes")
            for scene in scenes:
                w, h, n_frames = scene["w"], scene["h"], scene["frames"]
                cols = min(n_frames, 8)
                rows = math.ceil(n_frames / cols)
                for side_key in ("vanilla", "modded"):
                    img_rel = scene[side_key]["img"]
                    img_path = ROOT / "web" / img_rel
                    self.assertTrue(img_path.is_file(), f"Missing preview PNG: {img_path}")
                    hdr = img_path.read_bytes()[:24]
                    self.assertEqual(hdr[:8], b"\x89PNG\r\n\x1a\n")
                    png_w, png_h = struct.unpack(">II", hdr[16:24])
                    self.assertEqual(png_w, cols * w, f"{img_rel} width mismatch")
                    self.assertEqual(png_h, rows * h, f"{img_rel} height mismatch")


class TestTitleReviewData(unittest.TestCase):
    EXPECTED_IDS = ["z2", "waldo", "feud", "dk", "duck", "wheel"]

    def test_title_review_data_and_256x240_pngs(self) -> None:
        prefix = "window.TITLE_REVIEW_DATA = "
        for filename in ("title_review_data.js", "local_title_review_data.js"):
            data_path = ROOT / "web" / filename
            self.assertTrue(data_path.is_file(), f"Missing {data_path}")
            raw = data_path.read_text(encoding="utf-8").strip()
            self.assertTrue(raw.startswith(prefix), f"{filename} missing expected JS prefix")
            self.assertTrue(raw.endswith(";"), f"{filename} missing trailing semicolon")
            payload = json.loads(raw[len(prefix) : -1])

            games = payload["games"]
            if filename == "title_review_data.js":
                self.assertEqual([g["id"] for g in games], self.EXPECTED_IDS)

            for game in games:
                bnum = game["build_number"]
                self.assertIsInstance(bnum, int)
                self.assertGreater(bnum, 0, f"{game['id']} build_number must be > 0")
                self.assertEqual(game["status_label"], f"Build #{bnum}")
                screens = game["screens"]
                self.assertGreaterEqual(len(screens), 1, f"{game['id']} should have >= 1 screen")
                for screen in screens:
                    for side_key in ("vanilla", "ours"):
                        img_rel = screen[side_key]["img"]
                        img_path = ROOT / "web" / img_rel
                        self.assertTrue(img_path.is_file(), f"Missing title PNG: {img_path}")
                        hdr = img_path.read_bytes()[:24]
                        self.assertEqual(hdr[:8], b"\x89PNG\r\n\x1a\n", f"Invalid PNG header: {img_rel}")
                        png_w, png_h = struct.unpack(">II", hdr[16:24])
                        self.assertEqual((png_w, png_h), (256, 240), f"{img_rel} dimensions mismatch")


class TestZ2StringsDashboard(unittest.TestCase):
    def test_z2_strings_extracted_and_valid(self) -> None:
        import re

        payload = z2_strings_dashboard.build_z2_strings_payload(ROOT)
        strings = payload["strings"]
        self.assertGreaterEqual(len(strings), 70)
        ids = [s["id"] for s in strings]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate string IDs")

        expected_areas = {
            "Title & Game Over",
            "Rauru",
            "Saria",
            "Mido",
            "Darunia",
            "Ruto",
            "Towns (General)",
            "Rauru Arcade & Portals",
            "Pause / Spell & Gear Menu",
            "Ending & Credits",
        }
        self.assertTrue(expected_areas.issubset(set(payload["areas"])))

        for s in strings:
            c = s["constraints"]
            lines = s["text"].split("\n")
            self.assertLessEqual(len(lines), c["max_lines"], f"{s['id']} too many lines")
            for idx, line in enumerate(lines, 1):
                self.assertLessEqual(
                    len(line), c["max_line_len"], f"{s['id']} L{idx} too long: {line!r}"
                )
                if c["exact_line_len"]:
                    self.assertEqual(
                        len(line), c["max_line_len"], f"{s['id']} L{idx} not exact: {line!r}"
                    )
            self.assertRegex(s["text"], c["allowed_regex"], f"{s['id']} invalid charset")


class TestTitleBuildResolution(unittest.TestCase):
    def test_lookup_subgame_build_by_sha256_prefers_matching_hash(self) -> None:
        import hashlib
        import sqlite3
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rom_path = tmp_path / "zelda.nes"
            rom_bytes = b"NES\x1a" + b"zelda-b69"
            rom_path.write_bytes(rom_bytes)
            digest = hashlib.sha256(rom_bytes).hexdigest()

            db_path = tmp_path / "history.sqlite3"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE subgame_builds (
                    game TEXT NOT NULL,
                    build_number INTEGER NOT NULL,
                    completed_utc TEXT NOT NULL,
                    mapper TEXT NOT NULL,
                    output_path TEXT NOT NULL,
                    output_sha256 TEXT NOT NULL,
                    git_commit TEXT,
                    git_dirty INTEGER,
                    PRIMARY KEY (game, build_number)
                )
                """
            )
            conn.execute(
                "INSERT INTO subgame_builds VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("zelda", 69, "2026-11-27T00:00:00+00:00", "176", "build/subgames/zelda.nes", digest, None, None),
            )
            conn.execute(
                "INSERT INTO subgame_builds VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("zelda", 80, "2026-11-27T01:00:00+00:00", "176", "/tmp/other/zelda.nes", "0" * 64, None, None),
            )
            conn.commit()
            conn.close()

            self.assertEqual(title_dashboard._lookup_subgame_build_by_sha256(db_path, "zelda", rom_path), 69)

    def test_build_catalog_prefer_existing_preserves_captured_build_numbers(self) -> None:
        import tempfile
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_js = tmp_path / "title_review_data.js"
            local_js = tmp_path / "local_title_review_data.js"
            local_js.write_text(
                "window.TITLE_REVIEW_DATA = "
                + json.dumps({"version": 2, "games": [{"id": "zelda", "build_number": 69}]})
                + ";\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(title_dashboard, "DATA_JS", data_js),
                mock.patch.object(title_dashboard, "LOCAL_DATA_JS", local_js),
                mock.patch.object(
                    title_dashboard,
                    "resolve_rom_and_build",
                    side_effect=lambda gid, tag: (Path(f"{gid}.nes"), 999),
                ),
            ):
                cat = title_dashboard.build_catalog(allow_fallback=True, prefer_existing=True)
                by_id = {g["id"]: g for g in cat["games"]}
                self.assertEqual(by_id["zelda"]["build_number"], 69)
                self.assertEqual(by_id["smb"]["build_number"], 999)

    def test_release_downloads_pending_and_published(self) -> None:
        template = build_dashboard.TEMPLATE_PATH.read_text(encoding="utf-8")
        sample_manifest = {
            "repo": "jbax-and-his-ai-pals/019-z2-barba",
            "tag": "v2.0.0",
            "build_number": 825,
            "published": False,
            "collections": [
                {
                    "id": "all",
                    "title": "Complete BPS Collection",
                    "description": "All patches",
                    "filename": "barba-bps-v2.0.0-b825.zip",
                    "size_bytes": 123456,
                    "file_count": 2,
                }
            ],
            "patches": [
                {
                    "id": "barba",
                    "game": "barba",
                    "tier": "main",
                    "title": "Zelda II: Barba Edition (Combined)",
                    "filename": "barba-b825.bps",
                    "size_bytes": 654321,
                    "mapper": "NES 2.0 Mapper 176 (FK23C)",
                    "base_rom": "Zelda II: The Adventure of Link (USA PRG0)",
                },
                {
                    "id": "dk-compat",
                    "game": "dk",
                    "tier": "compat",
                    "title": "Donkey Barba (MMC3 Compat)",
                    "filename": "dk-compat-b27.bps",
                    "size_bytes": 294273,
                    "mapper": "Mapper 4 (MMC3)",
                    "base_rom": "Donkey Kong (USA / Rev A)",
                },
            ],
        }
        pending_html = build_dashboard.render_flavor(template, "public", release_manifest=sample_manifest)
        self.assertIn("Pending Upload", pending_html)
        self.assertIn("barba-bps-v2.0.0-b825.zip", pending_html)
        self.assertIn("barba-b825.bps", pending_html)
        self.assertIn("dk-compat-b27.bps", pending_html)
        self.assertNotIn("releases/download/v2.0.0/", pending_html)

        published_manifest = dict(sample_manifest, published=True)
        live_html = build_dashboard.render_flavor(template, "public", release_manifest=published_manifest)
        self.assertIn("https://github.com/jbax-and-his-ai-pals/019-z2-barba/releases/download/v2.0.0/barba-bps-v2.0.0-b825.zip", live_html)
        self.assertIn("https://github.com/jbax-and-his-ai-pals/019-z2-barba/releases/download/v2.0.0/barba-b825.bps", live_html)
        self.assertIn("https://github.com/jbax-and-his-ai-pals/019-z2-barba/releases/download/v2.0.0/dk-compat-b27.bps", live_html)
        self.assertNotIn("Pending Upload", live_html)


class TestOverworldTilesLab(unittest.TestCase):
    def test_public_omits_ow_tiles_lab_and_local_includes_it(self) -> None:
        template = build_dashboard.TEMPLATE_PATH.read_text(encoding="utf-8")
        pub_html = build_dashboard.render_flavor(template, "public")
        loc_html = build_dashboard.render_flavor(template, "local")

        self.assertNotIn('data-tab="owtiles"', pub_html)
        self.assertNotIn('id="view-owtiles"', pub_html)
        self.assertNotIn("local_ow_tiles_data.js", pub_html)
        self.assertNotIn("ow_tiles_ui.js", pub_html)

        self.assertIn('data-tab="owtiles"', loc_html)
        self.assertIn('id="view-owtiles"', loc_html)
        self.assertIn("local_ow_tiles_data.js", loc_html)
        self.assertIn("ow_tiles_ui.js", loc_html)

    def test_collect_ow_tiles_data_covers_all_environment_types(self) -> None:
        import ow_tiles_dashboard

        payload = ow_tiles_dashboard.collect_ow_tiles_data()
        env_by_id = {e["id"]: e for e in payload["environments"]}
        for required in ("water", "swamp", "desert", "mountain", "graveyard", "forest", "grass"):
            self.assertIn(required, env_by_id)
        for settled in ("water", "swamp", "desert", "mountain", "graveyard"):
            self.assertEqual(env_by_id[settled]["status"], "settled")
        for iterating in ("forest", "grass"):
            self.assertEqual(env_by_id[iterating]["status"], "iterating")
        self.assertGreaterEqual(len(payload["grass_possibilities"]), 4)
        self.assertGreaterEqual(len(payload["forest_possibilities"]), 4)
        for tile_flat in payload["environments"][0]["frames"]:
            self.assertEqual(len(tile_flat), 64)


if __name__ == "__main__":
    unittest.main()
