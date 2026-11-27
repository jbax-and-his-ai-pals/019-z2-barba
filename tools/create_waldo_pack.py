"""Create a 10-slot Where's Barba? save-state pack and isolated Mesen profile."""
from __future__ import annotations

import argparse
from pathlib import Path

from subgame_pack import ROOT, create_pack, find_play_rom, prepare_profile, run_cli

ROM_PATH = ROOT / 'play/nes/waldo-barba.nes'
PACK_DIR = ROOT / 'build/waldo-pack'
PROFILE_DIR = ROOT / 'build/mesen-scenarios/wheres-barba'
SCENARIOS = ROOT / 'tools/scenarios/waldo_scenarios.lua'

SLOTS = [
    ('title', "Title Screen (WHERE'S BARBA?)", 'Postcard title screen with Barba stamp portrait.'),
    ('skill-select', 'Skill Select (Wyrmling Cursor)', '16x16 animated Wyrmling cursor on the Skill Select screen.'),
    ('moon-ticket', 'One Ticket to the Lava', 'Peeking Barba head above the Lava ticket.'),
    ('overworld-map', 'Overworld Map (Walking Barba)', '48x48 full-body Barba walking across the Overworld Map to Train Station.'),
    ('train-station', 'Level 1: Train Station', 'Search the Train Station for hidden 16x16 Barba.'),
    ('before-subway', 'Before Level 5: The Subway', 'Walking to the Subway on the Overworld Map right before the level starts. Collect Barba and the Flame while dodging Link!'),
    ('castle', 'Level 6: The Castle', 'Search the Castle courtyard for hidden 16x16 Barba right before Launch Pad.'),
    ('slots-two-barbas', 'Slots: 2 Barbas Locked', 'Reels 2 and 3 are locked on Barba. Time A on Reel 1 for the 3-Barba Moon launch!'),
    ('slots-jackpot', 'Slots: 3-Barba Jackpot', 'All three Barbas matched! Watch the rocket launch to the Moon.'),
    ('moon-ending', 'Moon Ending', 'Barba on the Moon ending sequence.'),
]


def _paths(mmc3: bool = False) -> tuple[Path, Path, Path]:
    if mmc3:
        return (
            find_play_rom('waldo-mmc3'),
            ROOT / 'build/waldo-mmc3-pack',
            ROOT / 'build/mesen-scenarios/wheres-barba-mmc3',
        )
    return find_play_rom('waldo-barba'), PACK_DIR, PROFILE_DIR


def _build(mmc3: bool, rom_path: Path) -> None:
    if mmc3:
        import build_mmc3
        build_mmc3.build_game_mmc3('waldo', rom_path.parent)
    else:
        import build_waldo
        build_waldo.build()


def create(force: bool = False, mmc3: bool = False) -> dict:
    rom_path, pack_dir, _ = _paths(mmc3)
    tag = 'waldo-mmc3' if mmc3 else 'waldo'
    return create_pack(
        tag, rom_path, lambda: _build(mmc3, rom_path), SLOTS, SCENARIOS,
        timeout=90, force=force, pack_dir=pack_dir,
    )


def prepare(force: bool = False, mmc3: bool = False) -> tuple[Path, dict]:
    rom_path, pack_dir, profile_dir = _paths(mmc3)
    tag = 'waldo-mmc3' if mmc3 else 'waldo'
    return prepare_profile(
        tag, rom_path, lambda: _build(mmc3, rom_path), SLOTS, SCENARIOS,
        timeout=90, force=force, pack_dir=pack_dir, profile_dir=profile_dir,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mmc3', action='store_true', help='Use play/nes/waldo-mmc3.nes instead of standalone.')
    parser.add_argument('--force', action='store_true', help='Regenerate all 10 save states.')
    parser.add_argument('--prepare-only', action='store_true', help='Prepare profile without opening Mesen.')
    args = parser.parse_args()

    rom_path, pack_dir, profile_dir = _paths(args.mmc3)
    tag = 'waldo-mmc3' if args.mmc3 else 'waldo'
    run_cli(
        tag, rom_path, lambda: _build(args.mmc3, rom_path), SLOTS, SCENARIOS,
        timeout=90, force=args.force, prepare_only=args.prepare_only,
        pack_dir=pack_dir, profile_dir=profile_dir,
    )


if __name__ == '__main__':
    main()
