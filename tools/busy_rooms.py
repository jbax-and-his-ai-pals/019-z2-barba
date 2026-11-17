"""Busy-room lag / status-bar probe over generated test-pack checkpoints.

python tools/busy_rooms.py                       # default busy set, 500 frames each
python tools/busy_rooms.py --sets palaces,movement,world --frames 800
python tools/busy_rooms.py --states movement/p2-floor,palaces/p5-before-boss

Needs a test pack for the current build (python tools/create_test_pack.py --set <name>);
an older pack can be used with --pack <sha12> (RAM layout permitting). Writes
build/busy-rooms.txt; RESULT PASS when no side-view frame starts with a shifted
status bar.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from emulator_test import run

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ['movement/p2-floor', 'palaces/p5-before-boss', 'world/old-kasuto',
           'world/new-kasuto', 'world/rauru', 'palaces/p1-before-boss']

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sets', help='comma-separated checkpoint sets (all their states)')
    parser.add_argument('--states', help='comma-separated set/state ids')
    parser.add_argument('--frames', type=int, default=500)
    parser.add_argument('--pack', help='test-pack folder name (default: current build hash)')
    parser.add_argument('--rom', type=Path, default=ROOT/'build/barba.nes')
    args = parser.parse_args()
    pack = ROOT/'build/test-pack'/(args.pack or hashlib.sha256(args.rom.read_bytes()).hexdigest()[:12])
    if args.states:
        states = args.states.split(',')
    elif args.sets:
        states = [f'{s}/{p.stem}' for s in args.sets.split(',') for p in sorted((pack/s).glob('*.mss'))]
    else:
        states = DEFAULT
    missing = [s for s in states if not (pack/(s+'.mss')).exists()]
    if missing:
        raise SystemExit(f'Missing checkpoints in {pack}: {missing}. Run tools/create_test_pack.py for those sets.')
    prefix = (f'BUSY_PACK = {json.dumps(pack.as_posix())}\nBUSY_FRAMES = {args.frames}\n'
              f'BUSY_STATES = {{{",".join(json.dumps(s) for s in states)}}}\n')
    scenario = ROOT/'build/busy_rooms_gen.lua'
    scenario.write_text(prefix + (ROOT/'tests/busy_rooms.lua').read_text())
    code = run(scenario, args.rom, timeout=60 + len(states)*args.frames//25)
    print((ROOT/'build/busy-rooms.txt').read_text())
    return code

if __name__ == '__main__':
    raise SystemExit(main())
