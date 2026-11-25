"""Zelda II: Barba Enterprise — Feature catalog, flagstring codec, and prototype builder.

Models Barba Edition features, Vanilla Zelda II baselines, and planned
Free Enterprise-style randomizer options as a composable flag graph.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

CATEGORIES: list[dict[str, str]] = [
    {"id": "barba_core", "title": "Barba Mode (Coupled Core)", "icon": "dragon"},
    {"id": "barba_options", "title": "Barba-Only Options & Tunables", "icon": "flame"},
    {"id": "world_presentation", "title": "World, Presentation & Crossover (Decoupled)", "icon": "map"},
    {"id": "randomizer", "title": "Randomizer & Pacing", "icon": "dice"},
]

# Status values:
# - "toggleable": wired to tools/build.py today (can actually be toggled in a build)
# - "built": implemented in Barba Edition (bundled into Barba Mode; coupled flags follow barba_protagonist)
# - "planned": unbuilt Free Enterprise option (shown in UI for design/flagstring prototyping)
FLAGS: list[dict[str, Any]] = [
    # Barba Mode (Coupled Core)
    {
        "id": "barba_protagonist",
        "code": "Bb",
        "category": "barba_core",
        "label": "Barba Mode: Link (Sword Slash) -> Barba (Firebreath Volley & Dragon Kit)",
        "type": "bool",
        "status": "built",
        "vanilla": False,
        "barba": True,
        "requires": [],
        "description": "Hard switch between Vanilla Link and Full Barba (24x48 dragon with diagonal firebreath volleys, dragon spells, and Barba-specific mechanics).",
        "preview": {"off": "previews/cap_vanilla_grass_attack.png", "off_w": 256, "off_h": 176, "off_label": "Link (Sword Slash)", "on": "previews/cap_barba_grass_attack.png", "on_w": 256, "on_h": 176, "on_label": "Barba (Firebreath Volley)", "frames": 84, "fps": 20},
    },
    {
        "id": "spell_scales",
        "code": "S1",
        "category": "barba_core",
        "label": "Shield -> SCALES",
        "type": "bool",
        "status": "built",
        "coupled": True,
        "vanilla": False,
        "barba": True,
        "requires": ["barba_protagonist"],
        "description": "Replaces Shield with SCALES: navy outline + sky-blue body, cast roar/decor flash, and shielded-hit clang.",
        "preview": {"off": "previews/cap_vanilla_spell_scales.png", "off_w": 256, "off_h": 176, "off_label": "Vanilla Shield", "on": "previews/cap_barba_spell_scales.png", "on_w": 256, "on_h": 176, "on_label": "SCALES", "frames": 48, "fps": 20},
    },
    {
        "id": "spell_wyrmling",
        "code": "S2",
        "category": "barba_core",
        "label": "Fairy -> WYRMLING",
        "type": "bool",
        "status": "built",
        "coupled": True,
        "vanilla": False,
        "barba": True,
        "requires": ["barba_protagonist"],
        "description": "Replaces Fairy with an 8x16 flying Wyrmling form.",
        "preview": {"off": "previews/cap_vanilla_spell_wyrmling.png", "off_w": 256, "off_h": 176, "off_label": "Vanilla Fairy", "on": "previews/cap_barba_spell_wyrmling.png", "on_w": 256, "on_h": 176, "on_label": "WYRMLING", "frames": 48, "fps": 20},
    },
    {
        "id": "spell_inferno",
        "code": "S3",
        "category": "barba_core",
        "label": "Fire -> INFERNO",
        "type": "bool",
        "status": "built",
        "coupled": True,
        "vanilla": False,
        "barba": True,
        "requires": ["barba_protagonist"],
        "description": "Replaces Fire with dragon Inferno breath enhancement.",
        "preview": {"off": "previews/cap_vanilla_spell_inferno.png", "off_w": 256, "off_h": 176, "off_label": "Vanilla Fire", "on": "previews/cap_barba_spell_inferno.png", "on_w": 256, "on_h": 176, "on_label": "INFERNO", "frames": 48, "fps": 20},
    },
    {
        "id": "spell_meteor",
        "code": "S4",
        "category": "barba_core",
        "label": "Thunder -> METEOR",
        "type": "bool",
        "status": "built",
        "coupled": True,
        "vanilla": False,
        "barba": True,
        "requires": ["barba_protagonist"],
        "description": "Replaces Thunder with screen-clearing METEOR fireballs.",
        "preview": {"off": "previews/cap_vanilla_spell_meteor.png", "off_w": 256, "off_h": 176, "off_label": "Vanilla Thunder", "on": "previews/cap_barba_spell_meteor.png", "on_w": 256, "on_h": 176, "on_label": "METEOR", "frames": 48, "fps": 20},
    },
    {
        "id": "ironknuckle_rebound",
        "code": "Ir",
        "category": "barba_core",
        "label": "Ironknuckle Shield Rebound",
        "type": "bool",
        "status": "built",
        "coupled": True,
        "vanilla": False,
        "barba": True,
        "requires": ["barba_protagonist"],
        "description": "Palace Ironknuckles bank downward firebreath off their shields toward other enemies.",
        "preview": {"off": "previews/cap_vanilla_ironknuckle_rebound.png", "off_w": 256, "off_h": 176, "off_label": "Vanilla Ironknuckle", "on": "previews/cap_barba_ironknuckle_rebound.png", "on_w": 256, "on_h": 176, "on_label": "Shield Rebound", "frames": 64, "fps": 20},
    },
    {
        "id": "glove_bricks",
        "code": "Gb",
        "category": "barba_core",
        "label": "Breath Breaks Glove Bricks",
        "type": "bool",
        "status": "built",
        "coupled": True,
        "vanilla": False,
        "barba": True,
        "requires": ["barba_protagonist"],
        "description": "Firebreath shatters glove-gated palace blocks once the Handy Glove is acquired.",
    },
    {
        "id": "lava_wade",
        "code": "Lw",
        "category": "barba_core",
        "label": "Submerged Lava & Swamp Pose",
        "type": "bool",
        "status": "built",
        "coupled": True,
        "vanilla": False,
        "barba": True,
        "requires": ["barba_protagonist"],
        "description": "Draws Barba partially submerged when wading in lava or foul water.",
    },
    {
        "id": "palace_roar_shake",
        "code": "Wp",
        "category": "barba_core",
        "label": "Palace Crystal & Lava Link Roar Shake",
        "type": "bool",
        "status": "built",
        "coupled": True,
        "vanilla": False,
        "barba": True,
        "requires": ["barba_protagonist"],
        "description": "Crystal floor pulse, Palace 6 drop roar, and Lava Link entrance camera/HUD shake.",
        "preview": {"off": "previews/cap_vanilla_palace_roar.png", "off_w": 256, "off_h": 176, "off_label": "Vanilla Crystal", "on": "previews/cap_barba_palace_roar.png", "on_w": 256, "on_h": 176, "on_label": "Crystal Pulse & Shake", "frames": 48, "fps": 20},
    },
    {
        "id": "rauru_sage_basement",
        "code": "Wr",
        "category": "barba_core",
        "label": "Rauru Sage Basement Sequence",
        "type": "bool",
        "status": "built",
        "coupled": True,
        "vanilla": False,
        "barba": True,
        "requires": ["barba_protagonist"],
        "description": "Adds the post-SCALES 'WAIT.' callout and 5-box dialogue with Rauru's sage.",
    },
    {
        "id": "title_and_ending",
        "code": "Wt",
        "category": "barba_core",
        "label": "Title & Ending: Link -> Barba Cliff & Dark Barba",
        "type": "bool",
        "status": "built",
        "coupled": True,
        "vanilla": False,
        "barba": True,
        "requires": ["barba_protagonist"],
        "description": "Title screen dragon silhouette, lava shimmer, 2nd-roar shake, and Dark Barba Triforce ending.",
        "preview": {"off": "previews/cap_vanilla_title.png", "off_w": 256, "off_h": 128, "off_label": "Vanilla Title", "on": "previews/cap_barba_title.png", "on_w": 256, "on_h": 128, "on_label": "Barba Title Cliff", "frames": 16, "fps": 15},
    },
    # Barba-Only Options & Tunables
    {
        "id": "volley_count",
        "code": "Vc",
        "category": "barba_options",
        "label": "Volley Shot Count",
        "type": "int",
        "min": 1,
        "max": 5,
        "status": "planned",
        "vanilla": 1,
        "barba": 5,
        "requires": ["barba_protagonist"],
        "description": "Maximum simultaneous fireballs in a volley (Barba Edition uses 5 with BarbaLoadOk governor).",
    },
    {
        "id": "town_chaos",
        "code": "Tc",
        "category": "barba_options",
        "label": "Towns: Peaceful -> Chaos (Flee, Burn, Shouts & Combos)",
        "type": "bool",
        "status": "built",
        "vanilla": False,
        "barba": True,
        "requires": ["barba_protagonist"],
        "description": "Barba-only town panic: villagers flee and burn with multi-row shouts and MULTI KILL / GODLIKE combo counters.",
        "preview": {"off": "previews/cap_vanilla_town_chaos.png", "off_w": 256, "off_h": 176, "off_label": "Peaceful Towns (Vanilla)", "on": "previews/cap_barba_town_chaos.png", "on_w": 256, "on_h": 176, "on_label": "Town Chaos (Flee & Burn)", "frames": 64, "fps": 20},
    },
    {
        "id": "error_ash_pile",
        "code": "We",
        "category": "barba_options",
        "label": "Error of Ruto Ash Pile",
        "type": "bool",
        "status": "built",
        "vanilla": False,
        "barba": True,
        "requires": ["town_chaos"],
        "description": "Burning Error leaves an interactive ash pile ('I AM ASH PILE.').",
    },
    # World, Presentation & Crossover (Decoupled)
    {
        "id": "scanline_scenery",
        "code": "Ws",
        "category": "world_presentation",
        "label": "Overworld & Encounter Scenery (IRQ Clouds & Shimmer)",
        "type": "bool",
        "status": "built",
        "vanilla": False,
        "barba": True,
        "requires": [],
        "description": "Parallax clouds, swaying grass/sprigs, shimmering water/lava/flames, and rock-steady HUD split.",
        "preview": {"off": "previews/cap_vanilla_grass_walk.png", "off_w": 256, "off_h": 176, "off_label": "Vanilla Static Scenery", "on": "previews/cap_barba_grass_walk.png", "on_w": 256, "on_h": 176, "on_label": "IRQ Clouds & Sway", "frames": 48, "fps": 30},
    },
    {
        "id": "saria_foul_water",
        "code": "Wf",
        "category": "world_presentation",
        "label": "Saria River & Village Water: Blue Water -> Foul Water",
        "type": "bool",
        "status": "built",
        "vanilla": False,
        "barba": True,
        "requires": ["scanline_scenery"],
        "description": "Replaces vanilla Saria's blue river and village water with animated green foul water and bridge guard warning.",
        "preview": {"off": "previews/cap_vanilla_saria_town.png", "off_w": 256, "off_h": 176, "off_label": "Vanilla Blue Water", "on": "previews/cap_barba_saria_town.png", "on_w": 256, "on_h": 176, "on_label": "Saria Foul Water", "frames": 104, "fps": 20},
    },
    {
        "id": "boss_meters",
        "code": "Wm",
        "category": "world_presentation",
        "label": "Boss Health Meter Style (Left 8-Pip / Dark Souls Bottom)",
        "type": "enum",
        "options": ["vanilla", "souls"],
        "status": "toggleable",
        "vanilla": "vanilla",
        "barba": "souls",
        "requires": [],
        "description": "vanilla: Improved 8-pip left OAM meter (Gooma weapon priority, Lava Link A12 fix). souls: Full-width Dark Souls bottom bar with boss name above and white hit-flash drain.",
        "preview": {"off": "previews/cap_vanilla_boss_meter.png", "off_w": 256, "off_h": 176, "off_label": "Vanilla (8-Pip Left)", "on": "previews/cap_barba_boss_meter.png", "on_w": 256, "on_h": 176, "on_label": "Dark Souls Bottom Bar", "frames": 48, "fps": 20},
    },
    {
        "id": "crossover_portals",
        "code": "Tp",
        "category": "world_presentation",
        "label": "Crossover Portals (Where's Barba? / F13)",
        "type": "bool",
        "status": "toggleable",
        "vanilla": False,
        "barba": True,
        "requires": [],
        "description": "Enables the 4-slot town portal table in Rauru and Ruto.",
        "preview": {"off": "previews/cap_vanilla_crossover_portals.png", "off_w": 256, "off_h": 176, "off_label": "Vanilla Town Door", "on": "previews/cap_barba_crossover_portals.png", "on_w": 256, "on_h": 176, "on_label": "Wavy Crossover Portal", "frames": 48, "fps": 20},
    },
    {
        "id": "sampled_roar",
        "code": "Ar",
        "category": "world_presentation",
        "label": "Dragon Roar Audio: Native Noise -> Sampled DMC",
        "type": "bool",
        "status": "toggleable",
        "vanilla": False,
        "barba": True,
        "requires": [],
        "description": "Plays digitized dragon roar samples on title, item pickups, crystals, and boss intros.",
        "preview": {"on": "previews/roar_audio.png", "on_w": 56, "on_h": 28, "on_label": "DMC Roar Sample", "frames": 4, "fps": 6},
        "audio": {"off_synth": "noise_roar", "off_label": "Play Native Noise Roar", "on_wav": "previews/roar_sampled.wav", "on_label": "Play Sampled Roar", "pitch_control": True},
    },
    {
        "id": "game_over_portrait",
        "code": "Ap",
        "category": "world_presentation",
        "label": "Game Over Portrait: Vanilla Ganon -> Barba Link",
        "type": "bool",
        "status": "toggleable",
        "vanilla": False,
        "barba": True,
        "requires": [],
        "description": "Replaces Ganon's Game Over silhouette with the custom front-facing Link bust.",
        "preview": {"off": "previews/cap_vanilla_game_over.png", "off_w": 256, "off_h": 176, "off_label": "Vanilla Ganon", "on": "previews/cap_barba_game_over.png", "on_w": 256, "on_h": 176, "on_label": "Barba Link", "frames": 64, "fps": 15},
    },
    {
        "id": "game_over_laughs",
        "code": "Ag",
        "category": "world_presentation",
        "label": "Game Over Laughs: Ganon -> 5 Reworked Laughs",
        "type": "bool",
        "status": "toggleable",
        "vanilla": False,
        "barba": True,
        "requires": [],
        "description": "Replaces Ganon's 5-tick DPCM laugh sequence with five octave-up reworked Game Over laugh cues.",
        "audio": {"off_wav": "previews/ganon_laugh_seq.wav", "off_label": "Play Ganon 5-Laughs", "on_wav": "previews/link_laugh_seq.wav", "on_label": "Play Link 5-Laughs", "pitch_control": True},
    },
    # Randomizer & Pacing (Unbuilt / Planned FE Layer)
    {
        "id": "item_shuffle",
        "code": "Ri",
        "category": "randomizer",
        "label": "Key Item Shuffle",
        "type": "enum",
        "options": ["vanilla", "palaces", "full"],
        "status": "planned",
        "vanilla": "vanilla",
        "barba": "vanilla",
        "requires": [],
        "description": "Shuffle palace key items (Candle, Glove, Raft, Boots, Flute, Cross, Hammer, Magic Key) across pedestals.",
        "preview": {"on": "previews/item_shuffle.png", "on_w": 32, "on_h": 32, "on_label": "Shuffled Pedestals", "frames": 4},
    },
    {
        "id": "spell_shuffle",
        "code": "Rs",
        "category": "randomizer",
        "label": "Town Spell Shuffle",
        "type": "bool",
        "status": "planned",
        "vanilla": False,
        "barba": False,
        "requires": [],
        "description": "Randomize which wise man teaches each spell across Hyrule's towns.",
    },
    {
        "id": "boss_shuffle",
        "code": "Rb",
        "category": "randomizer",
        "label": "Palace Boss Shuffle",
        "type": "bool",
        "status": "planned",
        "vanilla": False,
        "barba": False,
        "requires": [],
        "description": "Shuffle palace guardians (Horsehead, Helmethead, Rebonack, Carock, Gooma, Lava Link).",
    },
    {
        "id": "portal_shuffle",
        "code": "Rp",
        "category": "randomizer",
        "label": "Portal Destination Shuffle",
        "type": "bool",
        "status": "planned",
        "vanilla": False,
        "barba": False,
        "requires": ["crossover_portals"],
        "description": "Randomize which town doors host the 4-slot crossover portal table.",
    },
    {
        "id": "xp_multiplier",
        "code": "Rx",
        "category": "randomizer",
        "label": "XP Gain Multiplier",
        "type": "enum",
        "options": ["1x", "2x", "4x"],
        "status": "planned",
        "vanilla": "1x",
        "barba": "1x",
        "requires": [],
        "description": "Scale enemy XP drops for faster Free Enterprise-style pacing.",
    },
    {
        "id": "open_great_palace",
        "code": "Ro",
        "category": "randomizer",
        "label": "Open Great Palace (Crystals Required)",
        "type": "int",
        "min": 0,
        "max": 6,
        "status": "planned",
        "vanilla": 6,
        "barba": 6,
        "requires": [],
        "description": "Number of palace crystals required to break the Great Palace barrier.",
    },
    {
        "id": "palette_shuffle",
        "code": "Rc",
        "category": "randomizer",
        "label": "Seeded Palette Shuffle",
        "type": "bool",
        "status": "planned",
        "vanilla": False,
        "barba": False,
        "requires": [],
        "description": "Deterministically remix overworld, palace, and Barba scale palettes from the seed.",
        "preview": {"off": "previews/barba_hero.png", "off_w": 64, "off_h": 56, "off_label": "Classic Scales", "on": "previews/barba_palettes.png", "on_w": 64, "on_h": 56, "on_label": "Seeded Palettes", "frames": 4},
    },
]

FLAG_BY_ID: dict[str, dict[str, Any]] = {f["id"]: f for f in FLAGS}
FLAG_BY_CODE: dict[str, dict[str, Any]] = {f["code"]: f for f in FLAGS}


def preset_values(name: str) -> dict[str, Any]:
    if name == "vanilla":
        return {f["id"]: f["vanilla"] for f in FLAGS}
    if name == "barba":
        return {f["id"]: f["barba"] for f in FLAGS}
    if name == "barba_lite":
        vals = {f["id"]: f["barba"] for f in FLAGS}
        vals["town_chaos"] = False
        vals["error_ash_pile"] = False
        vals["crossover_portals"] = False
        return vals
    if name == "chaos":
        vals = {f["id"]: f["barba"] for f in FLAGS}
        vals["item_shuffle"] = "full"
        vals["spell_shuffle"] = True
        vals["boss_shuffle"] = True
        vals["portal_shuffle"] = True
        vals["xp_multiplier"] = "2x"
        vals["open_great_palace"] = 4
        vals["palette_shuffle"] = True
        return vals
    raise ValueError(f"Unknown preset: {name}")


def resolve_flags(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Fill defaults, clamp ranges, and enforce `requires` dependencies."""
    resolved = preset_values("barba")
    for f in FLAGS:
        fid = f["id"]
        if fid in raw:
            val = raw[fid]
            if f["type"] == "bool":
                resolved[fid] = bool(val)
            elif f["type"] == "int":
                resolved[fid] = max(f["min"], min(f["max"], int(val)))
            elif f["type"] == "enum":
                resolved[fid] = val if val in f["options"] else f["barba"]
    notes: list[str] = []
    # Coupled flags follow barba_protagonist as a hard switch.
    barba_on = bool(resolved["barba_protagonist"])
    for f in FLAGS:
        if f.get("coupled"):
            resolved[f["id"]] = barba_on
    # Fixed-point pass to disable flags whose requirements are off.
    changed = True
    while changed:
        changed = False
        for f in FLAGS:
            fid = f["id"]
            if f["type"] == "bool" and resolved[fid]:
                missing = [req for req in f["requires"] if not resolved.get(req)]
                if missing:
                    resolved[fid] = False
                    changed = True
                    notes.append(f"Disabled {fid} (requires {', '.join(missing)})")
    return resolved, notes


def encode_flagstring(values: dict[str, Any], seed: int | str) -> str:
    """Encode flag values and seed into a compact FF4FE-style flagstring."""
    parts: list[str] = []
    for f in FLAGS:
        val = values[f["id"]]
        if f["type"] == "bool":
            if val:
                parts.append(f["code"])
        elif f["type"] == "int":
            parts.append(f"{f['code']}{val}")
        elif f["type"] == "enum":
            idx = f["options"].index(val)
            parts.append(f"{f['code']}{idx}")
    return f"BFE1|{' '.join(parts)}#{seed}"


def decode_flagstring(flagstring: str) -> tuple[dict[str, Any], str]:
    """Decode a BFE1 flagstring back into (values, seed)."""
    text = flagstring.strip()
    if "#" in text:
        body, seed = text.rsplit("#", 1)
    else:
        body, seed = text, "0"
    if not body.startswith("BFE1|"):
        raise ValueError("Flagstring must start with 'BFE1|'")
    tokens = [t for t in body[5:].split() if t]
    values = preset_values("vanilla")
    for tok in tokens:
        code = tok[:2]
        if code not in FLAG_BY_CODE:
            raise ValueError(f"Unknown flag code: {code}")
        f = FLAG_BY_CODE[code]
        rest = tok[2:]
        if f["type"] == "bool":
            values[f["id"]] = True
        elif f["type"] == "int":
            values[f["id"]] = int(rest)
        elif f["type"] == "enum":
            values[f["id"]] = f["options"][int(rest)]
    resolved, _ = resolve_flags(values)
    return resolved, seed


def catalog_payload() -> dict[str, Any]:
    return {
        "version": 1,
        "categories": CATEGORIES,
        "flags": FLAGS,
        "presets": {
            name: {
                "values": preset_values(name),
                "flagstring": encode_flagstring(preset_values(name), "BARBA2026"),
            }
            for name in ("vanilla", "barba", "barba_lite", "chaos")
        },
    }


WIRED_FLAG_IDS: tuple[str, ...] = (
    "boss_meters",
    "crossover_portals",
    "sampled_roar",
    "game_over_portrait",
    "game_over_laughs",
)


def _partition_manifest_flags(values: dict[str, Any], is_vanilla: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (applied_flags, unapplied_flags) reflecting what build.py actually produces."""
    if is_vanilla:
        return {}, {}
    applied: dict[str, Any] = {}
    unapplied: dict[str, Any] = {}
    for f in FLAGS:
        fid = f["id"]
        if fid in WIRED_FLAG_IDS:
            applied[fid] = values[fid]
        elif f["status"] == "built":
            applied[fid] = f["barba"]
            if values[fid] != f["barba"]:
                unapplied[fid] = values[fid]
        elif values[fid] != f["barba"]:
            unapplied[fid] = values[fid]
    return applied, unapplied


def run_prototype_build(values: dict[str, Any], seed: str, out_dir: Path) -> dict[str, Any]:
    """Run tools/build.py with the currently-wired toggles and emit a manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    flagstring = encode_flagstring(values, seed)
    is_vanilla = all(values[f["id"]] == f["vanilla"] for f in FLAGS)
    cmd: list[str] | None = None
    if not is_vanilla:
        cmd = [sys.executable, str(ROOT / "tools" / "build.py"), "--out", str(out_dir)]
        if not values.get("sampled_roar", True):
            cmd.append("--native-audio")
        if not values.get("crossover_portals", True):
            cmd.append("--no-portals")
        if not values.get("game_over_portrait", True):
            cmd.append("--no-game-over-portrait")
        if not values.get("game_over_laughs", True):
            cmd.append("--no-game-over-laughs")
        boss_meter = values.get("boss_meters", "vanilla")
        if boss_meter in ("vanilla", "souls"):
            cmd.extend(["--boss-meter", boss_meter])
        subprocess.run(cmd, cwd=ROOT, check=True)
    applied_flags, unapplied_flags = _partition_manifest_flags(values, is_vanilla)
    manifest = {
        "flagstring": flagstring,
        "seed": seed,
        "mode": "vanilla" if is_vanilla else "barba_prototype",
        "command": cmd,
        "wired_flags": list(WIRED_FLAG_IDS),
        "resolved_flags": values,
        "applied_flags": applied_flags,
        "unapplied_flags": unapplied_flags,
        "seed_digest": hashlib.sha256(f"{flagstring}".encode()).hexdigest()[:16],
        "rng_preview": random.Random(seed).randint(100000, 999999),
    }
    (out_dir / "fe-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Barba Enterprise flag catalog & prototype builder")
    parser.add_argument("--dump-json", action="store_true", help="Print catalog JSON to stdout")
    parser.add_argument("--write-web-catalog", action="store_true", help="Write web/catalog.json")
    parser.add_argument("--preset", choices=["vanilla", "barba", "barba_lite", "chaos"])
    parser.add_argument("--flags", help="BFE1 flagstring to decode/validate")
    parser.add_argument("--seed", default="BARBA2026", help="Seed string")
    parser.add_argument("--build", action="store_true", help="Run prototype build into build/fe/")
    args = parser.parse_args()

    if args.dump_json:
        print(json.dumps(catalog_payload(), indent=2))
        return
    if args.write_web_catalog:
        web_dir = ROOT / "web"
        web_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(catalog_payload(), indent=2)
        out_json = web_dir / "catalog.json"
        out_js = web_dir / "catalog.js"
        out_json.write_text(payload + "\n")
        out_js.write_text(f"window.BARBA_FE_CATALOG = {payload};\n")
        print(f"Wrote {out_json} and {out_js}")
        return

    if args.flags:
        values, seed = decode_flagstring(args.flags)
        if args.seed != "BARBA2026":
            seed = args.seed
    elif args.preset:
        values = preset_values(args.preset)
        seed = args.seed
    else:
        values = preset_values("barba")
        seed = args.seed

    values, notes = resolve_flags(values)
    for note in notes:
        print(f"[note] {note}", file=sys.stderr)
    print(f"Flagstring: {encode_flagstring(values, seed)}")
    if args.build:
        manifest = run_prototype_build(values, seed, ROOT / "build" / "fe")
        print(f"Built prototype manifest: {ROOT / 'build' / 'fe' / 'fe-manifest.json'} ({manifest['mode']})")


if __name__ == "__main__":
    main()
