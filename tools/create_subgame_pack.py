"""Create and launch save-state packs for standalone subgames in play/standalone/."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from subgame_pack import ROOT, run_cli


def _build_subgame(game: str) -> None:
    subprocess.run([sys.executable, str(ROOT / f'tools/pack_{game}.py')], check=True)
    src = ROOT / f'build/subgames/{game}.nes'
    dst = ROOT / f'play/standalone/{game}-barba.nes'
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


GAMES: dict[str, dict] = {
    'dk': {
        'rom': ROOT / 'play/standalone/dk-barba.nes',
        'scenarios': ROOT / 'tools/dk_scenarios.lua',
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
        'rom': ROOT / 'play/standalone/duck-barba.nes',
        'scenarios': ROOT / 'tools/duck_scenarios.lua',
        'timeout': 120,
        'slots': [
            ('title', 'Title Screen (Villager Hunt)', 'Villager Hunt title screen. Press A to start Game A, Game B, or Game C.'),
            ('barba_intro', 'Barba Intro Walk', 'Full-body Barba walking across the grass during the opening sequence.'),
            ('barba_jump', 'Barba Downstab Jump', 'Barba leaping into the grass with the full-length Z2 downstab graphic and screen shake.'),
            ('game_a', 'Game A (1 Villager)', 'Zelda II villager flying across the sky. Aim with D-pad and press A for fireball burst!'),
            ('barba_catch', 'Barba Catch Celebration', 'Barba popping up from the grass holding the caught villager.'),
            ('link_laugh', 'Villainous Link Laugh', 'Villainous Link popping up laughing after a miss!'),
            ('game_b', 'Game B (2 Villagers)', 'Game B with two Zelda II villagers flying at once.'),
            ('game_c', 'Game C (Octoroks & Moas)', 'Game C with Zelda II Octoroks, Moas, and Palace Plates flying.'),
        ],
    },
    'mm2': {
        'rom': ROOT / 'play/standalone/mm2-barba.nes',
        'scenarios': ROOT / 'tools/mm2_scenarios.lua',
        'timeout': 120,
        'slots': [
            ('title', 'Title Screen (Barba Man 2)', 'Barba Man 2 title screen. Press Start to begin.'),
            ('stage_select', 'Stage Select (Evil Link)', 'Stage Select screen with the Villainous Link center portrait.'),
            ('boss_intro', 'Boss Intro (Barba Roar)', "Robot Master intro screen with Barba's sampled roar."),
            ('gameplay', 'Stage Gameplay (Fireball Buster)', 'Inside Bubble Man stage as Barba with fireball Mega Buster.'),
            ('wily_reveal', 'Wily Castle Reveal', 'Wily Castle intro cutscene with Villainous Link pilot.'),
        ],
    },
    'mtpo': {
        'rom': ROOT / 'play/standalone/mtpo-barba.nes',
        'scenarios': ROOT / 'tools/mtpo_scenarios.lua',
        'timeout': 120,
        'slots': [
            ('intro', "Intro (Barba's Punch-Out!!)", "Barba's Punch-Out!! intro screen."),
            ('title', 'Title Screen', 'Title screen. Press Start to enter the ring.'),
            ('tape', 'Tale of the Tape', 'Pre-fight Tale of the Tape matchup screen.'),
            ('fight', 'Round 1 Fight (Barba)', 'Active Round 1 fight with crimson Barba in the ring!'),
        ],
    },
    'smb': {
        'rom': ROOT / 'play/standalone/smb-barba.nes',
        'scenarios': ROOT / 'tools/smb_scenarios.lua',
        'timeout': 180,
        'slots': [
            ('title', 'Title Screen (Super Barba Bros.)', 'Super Barba Bros. title screen. Press Start to begin.'),
            ('w1_wyrmling', 'World 1-1 (Wyrmling vs Bot)', 'Small Wyrmling Barba facing a Zelda II Bot slime in World 1-1.'),
            ('super_barba', 'Super Barba (Full Body)', 'Full-body Super Barba in World 1-1 after Mushroom power-up.'),
            ('inferno_barba', 'Inferno Barba (Fireball)', 'Inferno Barba in World 1-1 ready to breathe flame-crowned fireballs (press B).'),
            ('z2_enemies', 'Z2 Enemy Showcase', 'Stalfos, Red Ironknuckle, Wizzrobe, Geldarm, and Bubble all onscreen together!'),
            ('castle_boss', 'Castle 1-4 (Villainous Link)', 'On the Castle 1-4 bridge fighting Villainous Link (throwing sword beams & bombs).'),
            ('caged_fairy', 'Castle 1-4 Caged Fairy', 'Caged Fairy rescue after grabbing the Triforce Axe.'),
        ],
    },
    'wheel': {
        'rom': ROOT / 'play/standalone/wheel-barba.nes',
        'scenarios': ROOT / 'tools/wheel_scenarios.lua',
        'timeout': 180,
        'slots': [
            ('title', 'Title Screen (Wheel of Barba)', 'Wheel of Barba title screen. Press Start to begin.'),
            ('menu', 'Game Setup Menu', 'Menu board showing WHEEL OF BARBA EDITION.'),
            ('board', 'Main Board (Barba & Dark Link)', 'Main puzzle board with Barba, Dark Link contestant, and Zelda II puzzle.'),
            ('barba_walk', 'Barba Unveiling Letter', 'Barba walking across the stage to unveil a letter on the board.'),
        ],
    },
    'zelda': {
        'rom': ROOT / 'play/standalone/zelda-barba.nes',
        'scenarios': ROOT / 'tools/zelda_scenarios.lua',
        'timeout': 120,
        'slots': [
            ('title', 'Title Screen (Zelda 1: Barba)', 'The Legend of Zelda: Barba Edition title screen.'),
            ('file_select', 'File Select', 'File Select screen. Choose a save slot or Register Your Name.'),
            ('overworld_start', 'Hyrule Overworld Start', 'Barba starting in Hyrule Overworld (Screen $77).'),
            ('burn_bush', 'Burnable Bush Secret (Screen $78)', 'Barba standing above the secret bush on Screen $78 with Sword. Press A to breathe fire and reveal the stairs!'),
        ],
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', required=True, choices=sorted(GAMES.keys()))
    parser.add_argument('--force', action='store_true', help='Regenerate all save states.')
    parser.add_argument('--prepare-only', action='store_true', help='Prepare profile without opening Mesen.')
    args = parser.parse_args()

    cfg = GAMES[args.game]
    run_cli(
        game=args.game,
        rom_path=cfg['rom'],
        build_fn=lambda: _build_subgame(args.game),
        slots=cfg['slots'],
        scenarios_lua=cfg['scenarios'],
        timeout=cfg['timeout'],
        force=args.force,
        prepare_only=args.prepare_only,
    )


if __name__ == '__main__':
    main()
