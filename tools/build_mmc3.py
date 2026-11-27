"""Build standalone Mapper 4 (MMC3) subgame ROMs into play/nes/<game>-mmc3.nes."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from bps import write_bps
from build_history import HISTORY_FILE, next_subgame_build_number, record_subgame_build
import hashlib

ROOT = _TOOLS_DIR.parent
DEFAULT_OUT_DIR = ROOT / 'play' / 'nes'

# Subgames that run on standard Mapper 4 (MMC3) without FK23C ($5FF0/$5FF1) extensions.
# Excluded (FK23C / Mapper 176 required):
#   - wheel: AxROM 32 KB bankswitching swaps $E000-$FFFF via FK23C $5FF1 outer bank
MMC3_GAMES: tuple[str, ...] = (
    'dk',
    'duck',
    'f13',
    'feud',
    'mm2',
    'mtpo',
    'smb',
    'waldo',
    'zelda',
)

FK23C_ONLY_GAMES: dict[str, str] = {
    'wheel': 'AxROM $E000-$FFFF 32 KB bankswitching via $5FF1',
}


def build_game_mmc3(game: str, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    """Build one subgame as a Mapper 4 (MMC3) ROM at <out_dir>/<game>-mmc3.nes."""
    if game not in MMC3_GAMES:
        reason = FK23C_ONLY_GAMES.get(game, 'unknown game')
        raise ValueError(f'{game!r} cannot be built as standard MMC3 ({reason})')

    out_dir.mkdir(parents=True, exist_ok=True)
    build_number = next_subgame_build_number(HISTORY_FILE, game)
    out_path = out_dir / f'{game}-mmc3.nes'

    if game == 'dk':
        import pack_dk
        pack_dk.build_standalone(out_path, ROOT / 'roms/dk.nes', ROOT / 'roms/z2.nes', mapper='mmc3', build_number=build_number)
    elif game == 'duck':
        import pack_duck
        pack_duck.build_standalone(out_path, ROOT / 'roms/duck.nes', ROOT / 'roms/z2.nes', mapper='mmc3', build_number=build_number)
    elif game == 'f13':
        import f13_build
        built = f13_build.build(count_build=False, build_number=build_number)
        shutil.copyfile(built, out_path)
    elif game == 'feud':
        import pack_feud
        pack_feud.build_standalone(
            out_path,
            ROOT / 'roms/feud.nes',
            ROOT / 'roms/z2.nes',
            ROOT / 'assets/barba.json',
            mapper='mmc3',
            build_number=build_number,
        )
    elif game == 'mm2':
        import pack_mm2
        pack_mm2.build_standalone(out_path, ROOT / 'roms/mm2.nes', mapper='mmc3', build_number=build_number)
    elif game == 'mtpo':
        import pack_mtpo
        pack_mtpo.build_standalone(out_path, ROOT / 'roms/mtpo.nes', ROOT / 'roms/z2.nes', mapper='mmc3', build_number=build_number)
    elif game == 'smb':
        import pack_smb
        pack_smb.build_standalone(out_path, ROOT / 'roms/smb.nes', ROOT / 'roms/z2.nes', mapper='mmc3', build_number=build_number)
    elif game == 'waldo':
        import build_waldo
        built = build_waldo.build(count_build=False, build_number=build_number)
        shutil.copyfile(built, out_path)
    elif game == 'zelda':
        import pack_zelda
        pack_zelda.build_standalone(out_path, ROOT / 'roms/zelda.nes', ROOT / 'roms/z2.nes', mapper='mmc3', build_number=build_number)

    rom = out_path.read_bytes()
    mapper_num = (rom[6] >> 4) | (rom[7] & 0xF0)
    if mapper_num != 4:
        raise AssertionError(f'{out_path}: expected Mapper 4 (MMC3), got Mapper {mapper_num}')
    record_subgame_build(HISTORY_FILE, game, build_number, 'mmc3', out_path, hashlib.sha256(rom).hexdigest())
    bps_path = (
        ROOT / 'play' / 'bps' / f'{game}-mmc3.bps'
        if out_dir.resolve() == DEFAULT_OUT_DIR.resolve()
        else None
    )
    write_bps(
        ROOT / 'roms' / f'{game}.nes',
        out_path,
        out_bps_path=bps_path,
        metadata=f'{game}-mmc3 | Barba Edition (MMC3)',
    )
    return out_path


def build_all_mmc3(
    games: list[str] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> list[Path]:
    """Build all requested (or all supported) MMC3 subgame ROMs into out_dir."""
    targets = list(MMC3_GAMES) if not games else games
    return [build_game_mmc3(game, out_dir) for game in targets]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--game',
        action='append',
        choices=MMC3_GAMES,
        help='Subgame to build (repeatable; defaults to all MMC3-compatible subgames)',
    )
    parser.add_argument('--out-dir', type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    built = build_all_mmc3(args.game, args.out_dir)
    for path in built:
        hdr = path.read_bytes()[:16]
        mapper_num = (hdr[6] >> 4) | (hdr[7] & 0xF0)
        prg_kb = hdr[4] * 16
        chr_kb = hdr[5] * 8
        nes2 = (hdr[7] & 0x0C) == 0x08
        chr_ram_kb = (64 << (hdr[11] & 0x0F)) // 1024 if nes2 and (hdr[11] & 0x0F) else 0
        chr_desc = f'{chr_kb}KB CHR-ROM' if chr_kb else f'{chr_ram_kb}KB CHR-RAM (NES 2.0)'
        print(f'  {path.relative_to(ROOT)}  Mapper {mapper_num}  {prg_kb}KB PRG  {chr_desc}')

    if not args.game:
        for game, reason in FK23C_ONLY_GAMES.items():
            print(f'  [skipped] {game}: Mapper 176 only ({reason})')


if __name__ == '__main__':
    main()
