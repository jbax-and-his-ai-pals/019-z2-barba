"""Stamp build numbers on play/ artifacts and package flat .bps release zips."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parent.parent
_BUILD_SUFFIX_RE = re.compile(r'-b(\d+)$')


def _strip_build_suffix(stem: str) -> str:
    return _BUILD_SUFFIX_RE.sub('', stem)


def _extract_build_num(stem: str) -> int:
    match = _BUILD_SUFFIX_RE.search(stem)
    return int(match.group(1)) if match else -1


def _normalize_subgame_base(base: str) -> str:
    if base.endswith('-barba'):
        return base[:-len('-barba')]
    if base.endswith('-mmc3'):
        return base[:-len('-mmc3')] + '-compat'
    return base


def _stamp_dir(
    directory: Path,
    suffix: str,
    default_build: int,
    subgame_builds: dict[str, int] | None = None,
    *,
    only_bases: set[str] | None = None,
    normalize_legacy: bool = False,
) -> None:
    if not directory.is_dir():
        return
    by_base: dict[str, list[Path]] = {}
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() == suffix:
            base = _strip_build_suffix(path.stem)
            if normalize_legacy:
                base = _normalize_subgame_base(base)
            if only_bases is not None and base not in only_bases:
                continue
            by_base.setdefault(base, []).append(path)
    for base, paths in by_base.items():
        game_key = base.split('-', 1)[0]
        build_number = (
            subgame_builds[game_key]
            if subgame_builds and game_key in subgame_builds
            else default_build
        )
        # Prefer canonical un-numbered, then legacy un-numbered, then highest numeric build.
        unnumbered_canonical = [p for p in paths if p.stem == base]
        unnumbered_legacy = [p for p in paths if _extract_build_num(p.stem) == -1]
        if unnumbered_canonical:
            source = unnumbered_canonical[-1]
        elif unnumbered_legacy:
            source = unnumbered_legacy[-1]
        else:
            source = max(paths, key=lambda p: (_extract_build_num(p.stem), p.stem.startswith(f'{base}-b')))
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
    """Ensure all .nes and .bps files in play/, play/nes/, play/bps/, and play/compat/{nes,bps}/ carry -b<N>."""
    play_dir = root / 'play'
    for ext in ('.nes', '.bps'):
        _stamp_dir(play_dir, ext, build_number, only_bases={'barba'})
    _stamp_dir(play_dir / 'nes', '.nes', build_number, subgame_builds, normalize_legacy=True)
    _stamp_dir(play_dir / 'bps', '.bps', build_number, subgame_builds, normalize_legacy=True)
    _stamp_dir(play_dir / 'compat' / 'nes', '.nes', build_number, subgame_builds, normalize_legacy=True)
    _stamp_dir(play_dir / 'compat' / 'bps', '.bps', build_number, subgame_builds, normalize_legacy=True)


def collect_bps_files(root: Path = ROOT) -> list[Path]:
    """Return sorted .bps paths from play/barba*.bps, play/bps/*.bps, and play/compat/bps/*.bps (latest per base)."""
    files: list[Path] = []
    play_dir = root / 'play'
    if play_dir.is_dir():
        barba_bps = [
            p for p in play_dir.iterdir()
            if p.is_file() and p.suffix.lower() == '.bps' and _strip_build_suffix(p.stem) == 'barba'
        ]
        if barba_bps:
            unnumbered = [p for p in barba_bps if p.stem == 'barba']
            files.append(unnumbered[-1] if unnumbered else max(barba_bps, key=lambda p: _extract_build_num(p.stem)))
    by_base: dict[str, list[Path]] = {}
    for bps_dir in (play_dir / 'bps', play_dir / 'compat' / 'bps'):
        if bps_dir.is_dir():
            for path in sorted(p for p in bps_dir.iterdir() if p.is_file() and p.suffix.lower() == '.bps'):
                by_base.setdefault(_strip_build_suffix(path.stem), []).append(path)
    for k in sorted(by_base):
        paths = by_base[k]
        unnumbered = [p for p in paths if p.stem == k]
        files.append(unnumbered[-1] if unnumbered else max(paths, key=lambda p: _extract_build_num(p.stem)))
    return files


def build_flat_zip(out_path: Path, bps_files: list[Path]) -> Path:
    """Write a flat zip containing only the basename of each .bps file."""
    if not bps_files:
        raise FileNotFoundError('No .bps files found under play/, play/bps/, or play/compat/bps/')
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
        from build_history import HISTORY_FILE, get_all_subgame_build_numbers
        subgame_builds = get_all_subgame_build_numbers(HISTORY_FILE) if HISTORY_FILE.is_file() else None
        stamp_play_artifacts(ROOT, args.build_number, subgame_builds)

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
