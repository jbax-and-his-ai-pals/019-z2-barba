"""Stamp build numbers on play/ artifacts and package flat .bps release zips."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parent.parent
_BUILD_SUFFIX_RE = re.compile(r'-b\d+$')


def _strip_build_suffix(stem: str) -> str:
    return _BUILD_SUFFIX_RE.sub('', stem)


def _stamp_dir(
    directory: Path,
    suffix: str,
    default_build: int,
    subgame_builds: dict[str, int] | None = None,
) -> None:
    if not directory.is_dir():
        return
    by_base: dict[str, list[Path]] = {}
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() == suffix:
            by_base.setdefault(_strip_build_suffix(path.stem), []).append(path)
    for base, paths in by_base.items():
        game_key = base.split('-', 1)[0]
        build_number = (
            subgame_builds[game_key]
            if subgame_builds and game_key in subgame_builds
            else default_build
        )
        # Prefer an un-numbered (newly built) file if both un-numbered and old-numbered exist.
        unnumbered = [p for p in paths if p.stem == base]
        source = unnumbered[-1] if unnumbered else paths[-1]
        target = directory / f'{base}-b{build_number}{suffix}'
        if source != target:
            if target.exists():
                target.unlink()
            source.rename(target)
        for stale in paths:
            if stale != source and stale != target and stale.exists():
                stale.unlink()


def stamp_play_artifacts(
    root: Path,
    build_number: int,
    subgame_builds: dict[str, int] | None = None,
) -> None:
    """Ensure all .nes and .bps files in play/, play/nes/, and play/bps/ carry -b<N>."""
    play_dir = root / 'play'
    for ext in ('.nes', '.bps'):
        if play_dir.is_dir():
            for path in sorted(play_dir.iterdir()):
                if path.is_file() and path.suffix.lower() == ext and _strip_build_suffix(path.stem) == 'barba':
                    target = play_dir / f'barba-b{build_number}{ext}'
                    if path != target:
                        if target.exists():
                            target.unlink()
                        path.rename(target)
    _stamp_dir(play_dir / 'nes', '.nes', build_number, subgame_builds)
    _stamp_dir(play_dir / 'bps', '.bps', build_number, subgame_builds)


def collect_bps_files(root: Path = ROOT) -> list[Path]:
    """Return sorted .bps paths from play/barba*.bps and play/bps/*.bps (latest per base)."""
    files: list[Path] = []
    play_dir = root / 'play'
    if play_dir.is_dir():
        barba_bps = sorted(
            p for p in play_dir.iterdir()
            if p.is_file() and p.suffix.lower() == '.bps' and _strip_build_suffix(p.stem) == 'barba'
        )
        if barba_bps:
            files.append(barba_bps[-1])
    bps_dir = play_dir / 'bps'
    if bps_dir.is_dir():
        by_base: dict[str, Path] = {}
        for path in sorted(p for p in bps_dir.iterdir() if p.is_file() and p.suffix.lower() == '.bps'):
            by_base[_strip_build_suffix(path.stem)] = path
        files.extend(by_base[k] for k in sorted(by_base))
    return files


def build_flat_zip(out_path: Path, bps_files: list[Path]) -> Path:
    """Write a flat zip containing only the basename of each .bps file."""
    if not bps_files:
        raise FileNotFoundError('No .bps files found under play/ or play/bps/')
    seen: dict[str, Path] = {}
    for path in bps_files:
        if path.name in seen:
            raise ValueError(f'Duplicate .bps filename {path.name}: {seen[path.name]} and {path}')
        seen[path.name] = path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path in bps_files:
            zf.write(path, arcname=path.name)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description='Create a flat zip of all .bps patches for release.')
    parser.add_argument('--out', type=Path, help='Output zip path (default: dist/barba-bps[-bN].zip)')
    parser.add_argument('--build-number', type=int, help='Stamp -b<N> on play/ artifacts and zip filename')
    parser.add_argument('--version', help='Optional release version tag, e.g. v1.1.0')
    args = parser.parse_args()

    if args.build_number is not None:
        stamp_play_artifacts(ROOT, args.build_number)

    out_path = args.out
    if out_path is None:
        parts = ['barba-bps']
        if args.version:
            parts.append(args.version)
        if args.build_number is not None:
            parts.append(f'b{args.build_number}')
        out_path = ROOT / 'dist' / f"{'-'.join(parts)}.zip"

    bps_files = collect_bps_files()
    build_flat_zip(out_path, bps_files)
    print(f'Wrote {out_path.relative_to(ROOT)} ({len(bps_files)} .bps files, flat):')
    for path in bps_files:
        print(f'  {path.name} ({path.stat().st_size:,} bytes)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
