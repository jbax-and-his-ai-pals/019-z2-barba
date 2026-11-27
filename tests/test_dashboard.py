"""Unit tests for fe_catalog and standardized public/local dashboard builds."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_dashboard  # noqa: E402
import fe_catalog  # noqa: E402


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
        }
        self.assertTrue(expected.issubset(fe_catalog.FLAG_BY_ID.keys()))

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

        # Public flavor is presentation-only: no internal dev tabs/scripts/CLI box
        for marker in ('id="view-waldo"', 'id="view-feud"', 'id="view-duck"', "waldo_tagger.js", "feud_cast_ui.js", "duck_tiles_ui.js", "local_state.js", 'id="cli-cmd"'):
            self.assertNotIn(marker, public_html, f"Public HTML should not contain {marker}")

        # Local flavor has all internal dev tools and state bar
        for marker in ('id="view-waldo"', 'id="view-feud"', 'id="view-duck"', "waldo_tagger.js", "feud_cast_ui.js", "duck_tiles_ui.js", "local_state.js", 'id="cli-cmd"', 'id="local-build-bar"'):
            self.assertIn(marker, local_html, f"Local HTML missing {marker}")

        # Neither flavor should have unreplaced placeholders
        self.assertNotIn("{{", public_html)
        self.assertNotIn("{{", local_html)

        # Non-visual options must be grouped in their own section below animated cards
        self.assertIn("Non-Visual Options, Audio & Tunables", public_html)
        self.assertIn("Non-Visual Options, Audio & Tunables", local_html)


if __name__ == "__main__":
    unittest.main()
