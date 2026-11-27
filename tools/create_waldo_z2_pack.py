"""Create a 10-slot save-state pack inside Waldo inside Zelda II (build/barba.nes)."""
from __future__ import annotations

import argparse
from pathlib import Path

from subgame_pack import ROOT, create_pack, prepare_profile, run_cli

ROM_PATH = ROOT / 'build/barba.nes'
PACK_DIR = ROOT / 'build/waldo-z2-pack'
PROFILE_DIR = ROOT / 'build/mesen-scenarios/waldo-z2'
SCENARIOS = ROOT / 'tools/scenarios/waldo_z2_scenarios.lua'

SLOTS = [
    ('title', "Title Screen (WHERE'S BARBA?)", 'Inside Waldo from Rauru door. Press Start to advance, or Start+Select anytime to return to Zelda II.'),
    ('moon-ticket', 'One Ticket to the Lava', 'Peeking Barba head above the Lava ticket.'),
    ('overworld-map', 'Overworld Map (Walking Barba)', '16x48 Barba walking across the Overworld Map to Train Station.'),
    ('train-station', 'Level 1: Train Station', 'Search the Train Station for hidden 16x16 Barba.'),
    ('before-subway', 'Before Level 5: The Subway', 'Walking to the Subway on the Overworld Map right before the level starts. Collect Barba and the Flame while dodging Link!'),
    ('castle', 'Level 6: The Castle', 'Search the Castle courtyard for hidden 16x16 Barba right before Launch Pad.'),
    ('slots-two-barbas', 'Slots: 2 Barbas Locked', 'Reels 2 and 3 are locked on Barba. Time A on Reel 1 for the 3-Barba Moon launch!'),
    ('slots-jackpot', 'Slots: 3-Barba Jackpot', 'All three Barbas matched! Watch the rocket launch to the Moon.'),
    ('moon-ending', 'Moon Ending (Rocket Landing)', 'Barba on the Moon; watch the full Moon landing, then the wavy transition back to Rauru in Zelda II.'),
    ('moon-return', 'Moon Ending (About to Return)', '~1 second before the automatic wavy transition back to Rauru in Zelda II.'),
]


def _build_z2() -> None:
    import build
    build.build(ROOT / 'roms/z2.nes', ROOT / 'build', ROOT / 'assets/roar.wav')


def create(force: bool = False) -> dict:
    return create_pack(
        'waldo-z2', ROM_PATH, _build_z2, SLOTS, SCENARIOS,
        timeout=120, force=force, pack_dir=PACK_DIR, include_test_dir=True,
    )


def prepare(force: bool = False) -> tuple[Path, dict]:
    return prepare_profile(
        'waldo-z2', ROM_PATH, _build_z2, SLOTS, SCENARIOS,
        timeout=120, force=force, pack_dir=PACK_DIR, profile_dir=PROFILE_DIR,
        include_test_dir=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true', help='Regenerate all 10 save states.')
    parser.add_argument('--prepare-only', action='store_true', help='Prepare profile without opening Mesen.')
    args = parser.parse_args()
    run_cli(
        'waldo-z2', ROM_PATH, _build_z2, SLOTS, SCENARIOS,
        timeout=120, force=args.force, prepare_only=args.prepare_only,
        pack_dir=PACK_DIR, profile_dir=PROFILE_DIR, include_test_dir=True,
    )


if __name__ == '__main__':
    main()
