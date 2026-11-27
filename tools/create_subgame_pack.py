"""Create and launch save-state packs for standalone subgames in play/nes/."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from bps import write_bps
from subgame_pack import ROOT, find_play_rom, run_cli


def _build_subgame(game: str, mmc3: bool = False) -> None:
    if mmc3:
        subprocess.run([sys.executable, str(ROOT / 'tools/build_mmc3.py'), '--game', game], check=True)
        return
    subprocess.run([sys.executable, str(ROOT / f'tools/pack_{game}.py')], check=True)
    src = ROOT / f'build/subgames/{game}.nes'
    dst = ROOT / f'play/nes/{game}.nes'
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    write_bps(
        ROOT / 'roms' / f'{game}.nes',
        dst,
        out_bps_path=ROOT / f'play/bps/{game}.bps',
        metadata=f'{game} | Barba Edition',
    )


GAMES: dict[str, dict] = {
    'dk': {
        'rom': ROOT / 'play/nes/dk.nes',
        'scenarios': ROOT / 'tools/scenarios/dk_scenarios.lua',
        'timeout': 90,
        'slots': [
            ('title', 'Title Screen (Barba Kong)', 'Barba Kong title screen with fireball cursor. Press Start to begin.'),
            ('stage_25m', '25m Stage (Girders)', "Lil' Barba at the start of 25m with Big Bad Link tossing barrels and Princess Zelda at the top."),
            ('fury_25m', '25m Flame Fury', "Lil' Barba in 25m with Flame Fury (hammer) active! Smash barrels and fireballs."),
            ('stage_50m', '50m Stage (Conveyors)', "Lil' Barba on 50m (conveyor/pie stage) with Big Bad Link and fireballs."),
            ('stage_75m', '75m Stage (Elevators)', "Lil' Barba on 75m (elevators & springs stage)."),
            ('stage_100m', '100m Stage (Rivets)', "Lil' Barba on 100m (rivets stage) with Big Bad Link and Z2 Bubbles."),
        ],
    },
    'duck': {
        'rom': ROOT / 'play/nes/duck.nes',
        'scenarios': ROOT / 'tools/scenarios/duck_scenarios.lua',
        'timeout': 120,
        'slots': [
            ('title', 'Title Screen (Villager Hunt)', 'Villager Hunt title screen. Press A to start Game A, Game B, or Game C.'),
            ('barba_intro', 'Barba Intro & Jump', 'Full-body Barba walking across the grass and leaping in with the Z2 downstab graphic.'),
            ('game_a', 'Forest (Game A, 1 Villager)', 'Round 1 Forest with a Zelda II villager flying across the sky. Aim with D-pad and press A for fireball burst!'),
            ('plains', 'Plains (Round 2 Grass)', 'Round 2 Overworld Grass with a Zelda II villager flying across the sky.'),
            ('desert', 'Desert (Round 3 Desert)', 'Round 3 Desert with a Zelda II villager flying across the sky.'),
            ('barba_catch', 'Barba Catch Celebration', 'Barba popping up from the grass holding the caught villager.'),
            ('link_laugh', 'Villainous Link Laugh', 'Villainous Link popping up laughing after a miss!'),
            ('game_b', 'Game B (2 Villagers)', 'Game B with two Zelda II villagers flying at once.'),
            ('game_c', 'Game C (Octoroks & Moas)', 'Game C with Zelda II Octoroks, Moas, and Palace Plates flying.'),
            ('perfect_round', '10/10 Perfect Round Clear', 'End of a 10/10 round right before the PERFECT!! fanfare, roar, and screen shake.'),
        ],
    },
    'wheel': {
        'rom': ROOT / 'play/nes/wheel.nes',
        'scenarios': ROOT / 'tools/scenarios/wheel_scenarios.lua',
        'timeout': 180,
        'slots': [
            ('title', 'Title Screen (Wheel of Barba)', 'Wheel of Barba title screen. Press Start to begin.'),
            ('menu', 'Game Setup Menu', 'Menu board showing WHEEL OF BARBA EDITION.'),
            ('board', 'Main Board (Barba & Dark Link)', 'Main puzzle board with Barba, Dark Link contestant, and Zelda II puzzle.'),
            ('barba_walk', 'Barba Unveiling Letter', 'Barba walking across the stage to unveil a letter on the board.'),
        ],
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', required=True, choices=sorted(GAMES.keys()))
    parser.add_argument('--mmc3', action='store_true', help='Use play/compat/nes/<game>-compat.nes instead of standalone.')
    parser.add_argument('--force', action='store_true', help='Regenerate all save states.')
    parser.add_argument('--prepare-only', action='store_true', help='Prepare profile without opening Mesen.')
    args = parser.parse_args()

    cfg = GAMES[args.game]
    game_id = f'{args.game}-mmc3' if args.mmc3 else args.game
    rom_path = find_play_rom(f'{args.game}-compat' if args.mmc3 else args.game)
    run_cli(
        game=game_id,
        rom_path=rom_path,
        build_fn=lambda: _build_subgame(args.game, mmc3=args.mmc3),
        slots=cfg['slots'],
        scenarios_lua=cfg['scenarios'],
        timeout=cfg['timeout'],
        force=args.force,
        prepare_only=args.prepare_only,
    )


if __name__ == '__main__':
    main()
