"""Stamp build numbers on play/ artifacts and package flat .bps release zips."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import zipfile
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
_BUILD_SUFFIX_RE = re.compile(r'-b(\d+)$')
DEFAULT_REPO = 'jbax-and-his-ai-pals/019-z2-barba'
MANIFEST_PATH = ROOT / 'tools' / 'release_manifest.json'

PATCH_METADATA: dict[str, dict[str, str]] = {
    'barba': {
        'title': 'Zelda II: Barba Edition (Combined)',
        'base_rom': 'Zelda II: The Adventure of Link (USA PRG0)',
        'mapper': 'NES 2.0 Mapper 176 (FK23C)',
    },
    'waldo': {
        'title': "Where's Barba?",
        'base_rom': "Where's Waldo? (USA)",
        'mapper': 'NES 2.0 Mapper 176',
        'compat_mapper': 'Mapper 4 (MMC3)',
    },
    'feud': {
        'title': "Barba's Feud",
        'base_rom': 'Family Feud (USA)',
        'mapper': 'NES 2.0 Mapper 176',
        'compat_mapper': 'Mapper 4 (MMC3)',
    },
    'dk': {
        'title': 'Donkey Barba',
        'base_rom': 'Donkey Kong (USA / Rev A)',
        'mapper': 'NES 2.0 Mapper 176',
        'compat_mapper': 'Mapper 4 (MMC3)',
    },
    'duck': {
        'title': "Barba's Hunt",
        'base_rom': 'Duck Hunt (World)',
        'mapper': 'NES 2.0 Mapper 176',
        'compat_mapper': 'Mapper 4 (MMC3)',
    },
    'wheel': {
        'title': "Barba's Wheel",
        'base_rom': 'Wheel of Fortune (USA)',
        'mapper': 'NES 2.0 Mapper 176',
        'compat_mapper': 'NES 2.0 Mapper 176',
    },
}


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


def _collect_dir_bps(bps_dir: Path) -> list[Path]:
    if not bps_dir.is_dir():
        return []
    by_base: dict[str, list[Path]] = {}
    for path in sorted(p for p in bps_dir.iterdir() if p.is_file() and p.suffix.lower() == '.bps'):
        by_base.setdefault(_strip_build_suffix(path.stem), []).append(path)
    out: list[Path] = []
    for k in sorted(by_base):
        paths = by_base[k]
        unnumbered = [p for p in paths if p.stem == k]
        out.append(unnumbered[-1] if unnumbered else max(paths, key=lambda p: _extract_build_num(p.stem)))
    return out


def collect_bps_groups(root: Path = ROOT) -> dict[str, list[Path]]:
    """Return .bps paths grouped into main, subgames, compat, and all."""
    play_dir = root / 'play'
    main_list: list[Path] = []
    if play_dir.is_dir():
        barba_bps = [
            p for p in play_dir.iterdir()
            if p.is_file() and p.suffix.lower() == '.bps' and _strip_build_suffix(p.stem) == 'barba'
        ]
        if barba_bps:
            unnumbered = [p for p in barba_bps if p.stem == 'barba']
            main_list.append(unnumbered[-1] if unnumbered else max(barba_bps, key=lambda p: _extract_build_num(p.stem)))
    subgames_list = _collect_dir_bps(play_dir / 'bps')
    compat_list = _collect_dir_bps(play_dir / 'compat' / 'bps')
    return {
        'main': main_list,
        'subgames': subgames_list,
        'compat': compat_list,
        'all': [*main_list, *subgames_list, *compat_list],
    }


def collect_bps_files(root: Path = ROOT) -> list[Path]:
    """Return sorted .bps paths from play/barba*.bps, play/bps/*.bps, and play/compat/bps/*.bps (latest per base)."""
    groups = collect_bps_groups(root)
    return [*groups['main'], *sorted([*groups['subgames'], *groups['compat']], key=lambda p: _strip_build_suffix(p.stem))]


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


def _zip_name(prefix: str, version: str | None, build_number: int | None) -> str:
    parts = [prefix]
    if version:
        parts.append(version)
    if build_number is not None:
        parts.append(f'b{build_number}')
    return f"{'-'.join(parts)}.zip"


def _patch_entry(path: Path, tier: str) -> dict[str, Any]:
    base = _strip_build_suffix(path.stem)
    game_key = base[:-len('-compat')] if base.endswith('-compat') else base
    meta = PATCH_METADATA.get(game_key, {})
    is_compat = tier == 'compat' or base.endswith('-compat')
    title = meta.get('title', game_key.upper())
    if is_compat:
        title = f'{title} (MMC3 Compat)'
    mapper = meta.get('compat_mapper' if is_compat else 'mapper', 'Mapper 4 (MMC3)' if is_compat else 'NES 2.0 Mapper 176')
    return {
        'id': base,
        'game': game_key,
        'tier': tier,
        'title': title,
        'filename': path.name,
        'size_bytes': path.stat().st_size,
        'mapper': mapper,
        'base_rom': meta.get('base_rom', ''),
    }


def stage_release_assets(
    root: Path = ROOT,
    release_dir: Path | None = None,
    *,
    version: str | None = None,
    build_number: int | None = None,
    tag: str | None = None,
    repo: str = DEFAULT_REPO,
    published: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """Copy individual .bps patches and build collection .zip archives in a release staging directory."""
    groups = collect_bps_groups(root)
    all_bps = groups['all']
    if not all_bps:
        raise FileNotFoundError('No .bps files found under play/, play/bps/, or play/compat/bps/')

    resolved_tag = tag or version or (f'b{build_number}' if build_number is not None else 'dev')
    target_dir = release_dir or (root / 'dist' / f'release-{resolved_tag}')
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy individual .bps files flat into target_dir
    for path in all_bps:
        shutil.copy2(path, target_dir / path.name)

    # Build collection zips
    collection_specs = [
        ('all', 'Complete BPS Collection', 'Zelda II: Barba Edition + all standalone subgames (Flagship + MMC3 Compat).', 'barba-bps', groups['all']),
        ('subgames', 'Standalone Subgames (Flagship)', 'All 5 standalone Barba subgame .bps patches (Mapper 176).', 'barba-subgames-bps', groups['subgames']),
        ('compat', 'Standalone Subgames (MMC3 Compat)', 'Universal Mapper 4 / MMC3 compatibility .bps patches for standalone subgames.', 'barba-compat-bps', groups['compat']),
    ]
    collections: list[dict[str, Any]] = []
    for cid, title, desc, prefix, files in collection_specs:
        if not files:
            continue
        zip_filename = _zip_name(prefix, version, build_number)
        zip_path = target_dir / zip_filename
        build_flat_zip(zip_path, files)
        collections.append({
            'id': cid,
            'title': title,
            'description': desc,
            'filename': zip_filename,
            'size_bytes': zip_path.stat().st_size,
            'file_count': len(files),
            'files': [p.name for p in files],
        })

    patches: list[dict[str, Any]] = []
    for tier in ('main', 'subgames', 'compat'):
        for path in groups[tier]:
            patches.append(_patch_entry(path, tier))

    manifest = {
        'repo': repo,
        'tag': resolved_tag,
        'version': version,
        'build_number': build_number,
        'published': published,
        'collections': collections,
        'patches': patches,
    }
    return target_dir, manifest


def write_release_manifest(manifest: dict[str, Any], path: Path = MANIFEST_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description='Create flat .bps zip(s) and stage GitHub release assets.')
    parser.add_argument('--out', type=Path, help='Output zip path (default: dist/barba-bps[-bN].zip)')
    parser.add_argument('--build-number', type=int, help='Stamp -b<N> on play/ artifacts and zip filename')
    parser.add_argument('--version', help='Optional release version tag, e.g. v2.0.0')
    parser.add_argument('--tag', help='GitHub release tag for manifest links (defaults to --version or b<N>)')
    parser.add_argument('--stage-release', action='store_true', help='Stage individual .bps files and collection .zips into dist/release-<tag>/')
    parser.add_argument('--release-dir', type=Path, help='Custom output directory for --stage-release')
    parser.add_argument('--write-manifest', action='store_true', help='Write tools/release_manifest.json for the dashboard')
    parser.add_argument('--publish', action='store_true', help='Mark tools/release_manifest.json as published=true')
    args = parser.parse_args()

    if args.publish and not args.stage_release and not args.write_manifest:
        if not MANIFEST_PATH.is_file():
            raise FileNotFoundError(f'No manifest found at {MANIFEST_PATH}; run with --stage-release --write-manifest first')
        manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        manifest['published'] = True
        if args.tag:
            manifest['tag'] = args.tag
        write_release_manifest(manifest, MANIFEST_PATH)
        print(f'Marked {MANIFEST_PATH.relative_to(ROOT)} as published=true (tag={manifest.get("tag")})')
        return 0

    if args.build_number is not None:
        from build_history import HISTORY_FILE, get_all_subgame_build_numbers
        subgame_builds = get_all_subgame_build_numbers(HISTORY_FILE) if HISTORY_FILE.is_file() else None
        stamp_play_artifacts(ROOT, args.build_number, subgame_builds)

    if args.stage_release or args.write_manifest:
        release_dir, manifest = stage_release_assets(
            ROOT,
            args.release_dir,
            version=args.version,
            build_number=args.build_number,
            tag=args.tag,
            published=args.publish,
        )
        print(f'Staged release assets in {release_dir.relative_to(ROOT) if release_dir.is_relative_to(ROOT) else release_dir}:')
        for col in manifest['collections']:
            print(f"  [zip] {col['filename']} ({col['file_count']} files, {col['size_bytes']:,} bytes)")
        for patch in manifest['patches']:
            print(f"  [bps] {patch['filename']} ({patch['size_bytes']:,} bytes)")
        if args.write_manifest:
            mpath = write_release_manifest(manifest, MANIFEST_PATH)
            print(f'Wrote {mpath.relative_to(ROOT)} (published={manifest["published"]}, tag={manifest["tag"]})')
        return 0

    out_path = args.out
    if out_path is None:
        out_path = ROOT / 'dist' / _zip_name('barba-bps', args.version, args.build_number)

    bps_files = collect_bps_files()
    build_flat_zip(out_path, bps_files)
    print(f'Wrote {out_path.relative_to(ROOT)} ({len(bps_files)} .bps files, flat):')
    for path in bps_files:
        print(f'  {path.name} ({path.stat().st_size:,} bytes)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
