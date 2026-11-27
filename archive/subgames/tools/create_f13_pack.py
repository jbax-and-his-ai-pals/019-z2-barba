"""Create a save-state pack for standalone Friday the 13th: Barba Edition (play/nes/f13.nes)."""
from __future__ import annotations

import argparse
from pathlib import Path

from subgame_pack import ROOT, create_pack, find_play_rom, prepare_profile, run_cli

ROM_PATH = ROOT / 'play/nes/f13.nes'
PACK_DIR = ROOT / 'build/f13-pack'
PROFILE_DIR = ROOT / 'build/mesen-scenarios/f13'
SCENARIOS = ROOT / 'tools/scenarios/f13_scenarios.lua'

SLOTS = [
    ('title', 'Title Screen (Friday the 13th)', 'Friday the 13th title screen. Press Start to begin.'),
    ('camp-map', 'Crystal Lake Camp Map', 'Barba selected on the Crystal Lake Camp Map (BARBA + portrait). Press Start to enter camp.'),
    ('exterior-path', 'Exterior Camp Path', '16x32 Barba on the camp path with HUD portrait and approaching zombie. Move, jump, crouch, and throw rocks.'),
    ('cabin-inside', 'Inside Cabin', 'Barba inside a Crystal Lake cabin. Explore or press Down at the door to exit.'),
]


def _paths(mmc3: bool = False) -> tuple[Path, Path, Path]:
    if mmc3:
        return (
            find_play_rom('f13-compat'),
            ROOT / 'build/f13-mmc3-pack',
            ROOT / 'build/mesen-scenarios/f13-mmc3',
        )
    return find_play_rom('f13'), PACK_DIR, PROFILE_DIR


def _build(mmc3: bool, rom_path: Path) -> None:
    if mmc3:
        import build_mmc3
        build_mmc3.build_game_mmc3('f13', rom_path.parent)
    else:
        import f13_build
        f13_build.build()


def create(force: bool = False, mmc3: bool = False) -> dict:
    rom_path, pack_dir, _ = _paths(mmc3)
    tag = 'f13-mmc3' if mmc3 else 'f13'
    return create_pack(
        tag, rom_path, lambda: _build(mmc3, rom_path), SLOTS, SCENARIOS,
        timeout=60, force=force, pack_dir=pack_dir,
    )


def prepare(force: bool = False, mmc3: bool = False) -> tuple[Path, dict]:
    rom_path, pack_dir, profile_dir = _paths(mmc3)
    tag = 'f13-mmc3' if mmc3 else 'f13'
    return prepare_profile(
        tag, rom_path, lambda: _build(mmc3, rom_path), SLOTS, SCENARIOS,
        timeout=60, force=force, pack_dir=pack_dir, profile_dir=profile_dir,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mmc3', action='store_true', help='Use play/compat/nes/f13-compat.nes instead of standalone.')
    parser.add_argument('--force', action='store_true', help='Regenerate all save states.')
    parser.add_argument('--prepare-only', action='store_true', help='Prepare profile without opening Mesen.')
    args = parser.parse_args()

    rom_path, pack_dir, profile_dir = _paths(args.mmc3)
    tag = 'f13-mmc3' if args.mmc3 else 'f13'
    run_cli(
        tag, rom_path, lambda: _build(args.mmc3, rom_path), SLOTS, SCENARIOS,
        timeout=60, force=args.force, prepare_only=args.prepare_only,
        pack_dir=pack_dir, profile_dir=profile_dir,
    )


if __name__ == '__main__':
    main()
