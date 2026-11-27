"""Create a save-state pack for standalone Family Feud: Barba Edition (play/nes/feud.nes)."""
from __future__ import annotations

import argparse
from pathlib import Path

from subgame_pack import ROOT, create_pack, find_play_rom, prepare_profile, run_cli

ROM_PATH = ROOT / 'play/nes/feud.nes'
PACK_DIR = ROOT / 'build/feud-pack'
PROFILE_DIR = ROOT / 'build/mesen-scenarios/feud'
SCENARIOS = ROOT / 'tools/scenarios/feud_scenarios.lua'

SLOTS = [
    ('title', "Title Screen (Barba's Beef)", 'Family Feud: Barba Edition title screen. Press Start to begin.'),
    ('overview', 'Stage Overview (Barba vs Z2)', 'All 10 animated Barba & Zelda II contestants on stage (random cast, heights, palettes, and Zelda family names).'),
    ('faceoff', 'Face-Off (1-on-1)', 'Head-to-head Face-Off podium with randomized Barba vs Zelda II challenger.'),
    ('stage_barba', 'Barba Family Stage', 'Main Round on the Barba family podium. Watch contestants randomly roar or head-wiggle while idle.'),
    ('stage_z2', 'Zelda II Opposing Stage', 'Opposing Zelda II family on stage with randomized characters and Zelda family name.'),
    ('pre_fast_money', 'Before Fast Money', 'Barba family celebrating on stage right before Fast Money begins.'),
    ('fast_money', 'Fast Money Round', 'Fast Money active with Zelda II survey questions on the clock.'),
    ('after_fast_money', 'After Fast Money ($5,000)', 'Post-Fast Money winnings screen showing $5,000 banked toward the $20,000 grand prize.'),
    ('limit_20k', '$20,000 Limit Victory', 'Grand prize limit screen after reaching $20,000 total winnings.'),
    ('lose_msg', 'Zelda Lose Message', 'End-of-game Zelda II excuse screen (Due to <reason>, the <NAME> family...).'),
]


def _paths(mmc3: bool = False) -> tuple[Path, Path, Path]:
    if mmc3:
        return (
            find_play_rom('feud-compat'),
            ROOT / 'build/feud-mmc3-pack',
            ROOT / 'build/mesen-scenarios/feud-mmc3',
        )
    return find_play_rom('feud'), PACK_DIR, PROFILE_DIR


def _build(mmc3: bool, rom_path: Path) -> None:
    if mmc3:
        import build_mmc3
        build_mmc3.build_game_mmc3('feud', rom_path.parent)
    else:
        import pack_feud
        rom_path.parent.mkdir(parents=True, exist_ok=True)
        pack_feud.build_standalone(
            rom_path,
            ROOT / 'roms/feud.nes',
            ROOT / 'roms/z2.nes',
            ROOT / 'assets/barba.json',
        )


def create(force: bool = False, mmc3: bool = False) -> dict:
    rom_path, pack_dir, _ = _paths(mmc3)
    tag = 'feud-mmc3' if mmc3 else 'feud'
    return create_pack(
        tag, rom_path, lambda: _build(mmc3, rom_path), SLOTS, SCENARIOS,
        timeout=120, force=force, pack_dir=pack_dir,
    )


def prepare(force: bool = False, mmc3: bool = False) -> tuple[Path, dict]:
    rom_path, pack_dir, profile_dir = _paths(mmc3)
    tag = 'feud-mmc3' if mmc3 else 'feud'
    return prepare_profile(
        tag, rom_path, lambda: _build(mmc3, rom_path), SLOTS, SCENARIOS,
        timeout=120, force=force, pack_dir=pack_dir, profile_dir=profile_dir,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mmc3', action='store_true', help='Use play/compat/nes/feud-compat.nes instead of standalone.')
    parser.add_argument('--force', action='store_true', help='Regenerate all save states.')
    parser.add_argument('--prepare-only', action='store_true', help='Prepare profile without opening Mesen.')
    args = parser.parse_args()

    rom_path, pack_dir, profile_dir = _paths(args.mmc3)
    tag = 'feud-mmc3' if args.mmc3 else 'feud'
    run_cli(
        tag, rom_path, lambda: _build(args.mmc3, rom_path), SLOTS, SCENARIOS,
        timeout=120, force=args.force, prepare_only=args.prepare_only,
        pack_dir=pack_dir, profile_dir=profile_dir,
    )


if __name__ == '__main__':
    main()
