import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fe_catalog


class TestFeCatalog(unittest.TestCase):
    def test_roundtrip_all_presets(self) -> None:
        for preset in ("vanilla", "barba", "barba_lite", "chaos"):
            vals = fe_catalog.preset_values(preset)
            fs = fe_catalog.encode_flagstring(vals, "SEED42")
            decoded, seed = fe_catalog.decode_flagstring(fs)
            self.assertEqual(seed, "SEED42")
            self.assertEqual(decoded, vals)

    def test_dependency_disables_dependents(self) -> None:
        vals = fe_catalog.preset_values("barba")
        vals["barba_protagonist"] = False
        resolved, notes = fe_catalog.resolve_flags(vals)
        self.assertFalse(resolved["ironknuckle_rebound"])
        self.assertFalse(resolved["glove_bricks"])
        self.assertFalse(resolved["spell_scales"])
        self.assertFalse(resolved["spell_wyrmling"])
        self.assertFalse(resolved["spell_inferno"])
        self.assertFalse(resolved["spell_meteor"])
        self.assertFalse(resolved["lava_wade"])
        self.assertFalse(resolved["title_and_ending"])
        self.assertFalse(resolved["palace_roar_shake"])
        self.assertFalse(resolved["rauru_sage_basement"])
        self.assertFalse(resolved["town_chaos"])
        self.assertFalse(resolved["error_ash_pile"])
        self.assertTrue(len(notes) >= 1)

    def test_coupled_flags_follow_barba_mode(self) -> None:
        vals = fe_catalog.preset_values("barba")
        vals["spell_scales"] = False
        vals["town_chaos"] = False
        resolved, _ = fe_catalog.resolve_flags(vals)
        self.assertTrue(resolved["spell_scales"])
        self.assertFalse(resolved["town_chaos"])
        self.assertFalse(resolved["error_ash_pile"])

    def test_web_catalog_matches_module(self) -> None:
        web_json = Path(__file__).resolve().parents[1] / "web" / "catalog.json"
        self.assertTrue(web_json.exists())
        data = json.loads(web_json.read_text())
        self.assertEqual(data["version"], 1)
        self.assertEqual(len(data["flags"]), len(fe_catalog.FLAGS))

    def test_prototype_build_cli_args_and_manifest_accuracy(self) -> None:
        vals = fe_catalog.preset_values("barba_lite")
        vals["sampled_roar"] = False
        vals["boss_meters"] = "vanilla"
        vals["game_over_portrait"] = False
        vals["game_over_laughs"] = False
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            with mock.patch("fe_catalog.subprocess.run") as run_mock:
                manifest = fe_catalog.run_prototype_build(vals, "SEED42", out_dir)
            run_mock.assert_called_once()
            cmd = run_mock.call_args.args[0]
            self.assertIn("--out", cmd)
            self.assertNotIn("--output", cmd)
            self.assertIn("--no-portals", cmd)
            self.assertNotIn("--no-waldo", cmd)
            self.assertIn("--native-audio", cmd)
            self.assertIn("--no-game-over-portrait", cmd)
            self.assertIn("--no-game-over-laughs", cmd)
            self.assertEqual(cmd[cmd.index("--boss-meter") + 1], "vanilla")

            self.assertEqual(manifest["applied_flags"]["crossover_portals"], False)
            self.assertEqual(manifest["applied_flags"]["sampled_roar"], False)
            self.assertEqual(manifest["applied_flags"]["boss_meters"], "vanilla")
            self.assertEqual(manifest["applied_flags"]["game_over_portrait"], False)
            self.assertEqual(manifest["applied_flags"]["game_over_laughs"], False)
            self.assertTrue(manifest["applied_flags"]["town_chaos"])
            self.assertEqual(manifest["unapplied_flags"], {"town_chaos": False, "error_ash_pile": False})

            written = json.loads((out_dir / "fe-manifest.json").read_text())
            self.assertEqual(written["unapplied_flags"], manifest["unapplied_flags"])

    def test_chaos_manifest_marks_planned_flags_unapplied(self) -> None:
        vals = fe_catalog.preset_values("chaos")
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            with mock.patch("fe_catalog.subprocess.run"):
                manifest = fe_catalog.run_prototype_build(vals, "CHAOS1", out_dir)
            self.assertNotIn("item_shuffle", manifest["applied_flags"])
            self.assertEqual(manifest["unapplied_flags"]["item_shuffle"], "full")
            self.assertEqual(manifest["unapplied_flags"]["xp_multiplier"], "2x")
            self.assertTrue(manifest["unapplied_flags"]["spell_shuffle"])


if __name__ == "__main__":
    unittest.main()
