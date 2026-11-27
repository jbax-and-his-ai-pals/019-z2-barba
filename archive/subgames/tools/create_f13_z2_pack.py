"""Create a save-state pack inside Friday the 13th inside Zelda II (build/barba.nes)."""
from __future__ import annotations

import argparse
from pathlib import Path

from subgame_pack import ROOT, create_pack, prepare_profile, run_cli

ROM_PATH = ROOT / 'build/barba.nes'
PACK_DIR = ROOT / 'build/f13-z2-pack'
PROFILE_DIR = ROOT / 'build/mesen-scenarios/f13-z2'
SCENARIOS = ROOT / 'tools/scenarios/f13_z2_scenarios.lua'

SLOTS = [
    ('ruto-portal', 'Ruto Portal Door', 'Standing at the portal door in Ruto. Press Up then B to enter Friday the 13th.'),
    ('f13-title', 'F13 Title Screen (in Zelda II)', 'Inside Friday the 13th from Ruto door. Press Start to play, or Start+Select anytime to return to Ruto.'),
    ('f13-map', 'F13 Crystal Lake Camp Map', 'Barba selected on the Camp Map (BARBA + portrait). Press Start to enter camp, or Start+Select to return.'),
    ('f13-exterior', 'F13 Exterior Camp Path', '16x32 Barba on the camp path with HUD portrait and zombie. Start+Select returns to Ruto.'),
    ('f13-cabin', 'F13 Inside Cabin', 'Barba inside a Crystal Lake cabin. Press Down at the door to exit, or Start+Select to return.'),
    ('f13-win-return', 'F13 Day 3 Victory Return', 'Beating Day 3 triggers the automatic wavy transition back to Ruto in Zelda II.'),
]


def _build_z2() -> None:
    import build
    build.build(ROOT / 'roms/z2.nes', ROOT / 'build', ROOT / 'assets/roar.wav')


def create(force: bool = False) -> dict:
    return create_pack(
        'f13-z2', ROM_PATH, _build_z2, SLOTS, SCENARIOS,
        timeout=120, force=force, pack_dir=PACK_DIR, include_test_dir=True,
    )


def prepare(force: bool = False) -> tuple[Path, dict]:
    return prepare_profile(
        'f13-z2', ROM_PATH, _build_z2, SLOTS, SCENARIOS,
        timeout=120, force=force, pack_dir=PACK_DIR, profile_dir=PROFILE_DIR,
        include_test_dir=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true', help='Regenerate all save states.')
    parser.add_argument('--prepare-only', action='store_true', help='Prepare profile without opening Mesen.')
    args = parser.parse_args()
    run_cli(
        'f13-z2', ROM_PATH, _build_z2, SLOTS, SCENARIOS,
        timeout=120, force=args.force, prepare_only=args.prepare_only,
        pack_dir=PACK_DIR, profile_dir=PROFILE_DIR, include_test_dir=True,
    )


if __name__ == '__main__':
    main()
