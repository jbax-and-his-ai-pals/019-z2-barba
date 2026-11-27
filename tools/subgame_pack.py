"""Shared helper for creating and launching standalone subgame save-state packs."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from emulator_test import run
from prepare_player import apply_play_defaults

ROOT = Path(__file__).resolve().parents[1]


def find_play_rom(stem: str) -> Path:
    """Return the latest build-numbered play/nes/<stem>-b<N>.nes if present, else play/nes/<stem>.nes."""
    nes_dir = ROOT / 'play' / 'nes'
    if nes_dir.is_dir():
        matches = []
        for path in nes_dir.glob(f'{stem}-b*.nes'):
            suffix = path.stem[len(stem) + 2:]
            if suffix.isdigit():
                matches.append((int(suffix), path))
        if matches:
            matches.sort(key=lambda item: item[0])
            return matches[-1][1]
    return nes_dir / f'{stem}.nes'


def create_pack(
    game: str,
    rom_path: Path,
    build_fn: Callable[[], None],
    slots: list[tuple[str, str, str]],
    scenarios_lua: Path,
    timeout: int = 120,
    force: bool = False,
    pack_dir: Path | None = None,
    include_test_dir: bool = False,
    extra_prefix: str = '',
) -> dict:
    if not rom_path.is_file():
        build_fn()

    pack_dir = pack_dir or (ROOT / f'build/{game}-pack')
    digest = hashlib.sha256(rom_path.read_bytes()).hexdigest()
    manifest_path = pack_dir / 'manifest.json'
    if manifest_path.exists() and not force:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('rom_sha256') == digest and all((pack_dir / f'{s[0]}.mss').exists() for s in slots):
            return manifest

    pack_dir.mkdir(parents=True, exist_ok=True)
    scenario = ROOT / f'build/generate-{game}-states.lua'
    prefix = f'PACK_DIR = {json.dumps(pack_dir.as_posix())}\n'
    if include_test_dir:
        prefix += f'TEST_DIR = {json.dumps((ROOT / "tests").as_posix())}\n'
    if extra_prefix:
        prefix += extra_prefix
    scenario.write_text(prefix + scenarios_lua.read_text(encoding='utf-8'), encoding='utf-8')
    if run(scenario, rom_path, timeout):
        raise SystemExit(f'{game} state generation failed; see build/generate-{game}-states-error.txt')

    states = []
    for slot, (sid, name, desc) in enumerate(slots, 1):
        mss = pack_dir / f'{sid}.mss'
        if not mss.is_file() or not mss.read_bytes().startswith(b'MSS'):
            raise SystemExit(f'Missing or invalid state: {mss}')
        states.append({'slot': slot, 'id': sid, 'name': name, 'instructions': desc, 'file': mss.name})

    manifest = {'rom_sha256': digest, 'folder': str(pack_dir), 'rom': str(rom_path), 'states': states}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def install_pack_profile(
    profile_dir: Path,
    rom_path: Path,
    manifest: dict,
    *,
    saves_dir: Path | None = None,
    trim_unused_slots: bool = True,
) -> Path:
    source_exe = ROOT / '.tools/mesen/Mesen.exe'
    if not source_exe.is_file():
        raise SystemExit('Mesen is missing. Run tools/bootstrap.ps1 -WithEmulator first.')

    profile_dir.mkdir(parents=True, exist_ok=True)
    player = profile_dir / 'Mesen.exe'
    if not player.exists():
        shutil.copyfile(source_exe, player)

    slots_dir = profile_dir / 'slots'
    slots_dir.mkdir(exist_ok=True)
    resolved_saves = saves_dir or (profile_dir / 'saves')
    resolved_saves.mkdir(parents=True, exist_ok=True)
    if trim_unused_slots:
        for slot in range(len(manifest['states']) + 1, 11):
            (slots_dir / f'{rom_path.stem}_{slot}.mss').unlink(missing_ok=True)

    pack_dir = Path(manifest['folder'])
    for entry in manifest['states']:
        shutil.copyfile(pack_dir / entry['file'], slots_dir / f"{rom_path.stem}_{entry['slot']}.mss")

    settings = profile_dir / 'settings.json'
    config = json.loads(settings.read_text(encoding='utf-8-sig')) if settings.exists() else {}
    apply_play_defaults(config)
    preferences = config.setdefault('Preferences', {})
    preferences.update({
        'SingleInstance': False,
        'AutoLoadPatches': False,
        'OverrideSaveDataFolder': True,
        'SaveDataFolder': str(resolved_saves),
        'OverrideSaveStateFolder': True,
        'SaveStateFolder': str(slots_dir),
    })

    reserved = set(range(90, 100))
    shortcuts = preferences.setdefault('ShortcutKeys', [])
    for entry in shortcuts:
        for key_field in ('KeyCombination', 'KeyCombination2'):
            combo = entry.get(key_field)
            if combo and combo.get('Key1') in reserved and not combo.get('Key2') and not combo.get('Key3'):
                combo['Key1'] = 0
    names = {f'LoadStateSlot{slot}' for slot in range(1, 11)}
    shortcuts[:] = [s for s in shortcuts if s.get('Shortcut') not in names]
    for entry in manifest['states']:
        shortcuts.append({
            'Shortcut': f"LoadStateSlot{entry['slot']}",
            'KeyCombination': {'Key1': 89 + entry['slot'], 'Key2': 0, 'Key3': 0},
        })

    script_window = config.setdefault('Debug', {}).setdefault('ScriptWindow', {})
    script_window['AllowIoOsAccess'] = False
    settings.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    return player


def prepare_profile(
    game: str,
    rom_path: Path,
    build_fn: Callable[[], None],
    slots: list[tuple[str, str, str]],
    scenarios_lua: Path,
    timeout: int = 120,
    force: bool = False,
    pack_dir: Path | None = None,
    profile_dir: Path | None = None,
    include_test_dir: bool = False,
    extra_prefix: str = '',
) -> tuple[Path, dict]:
    manifest = create_pack(
        game, rom_path, build_fn, slots, scenarios_lua,
        timeout=timeout, force=force, pack_dir=pack_dir,
        include_test_dir=include_test_dir, extra_prefix=extra_prefix,
    )
    resolved_profile = profile_dir or (ROOT / f'build/mesen-scenarios/{game}')
    player = install_pack_profile(resolved_profile, rom_path, manifest)
    return player, manifest


def run_cli(
    game: str,
    rom_path: Path,
    build_fn: Callable[[], None],
    slots: list[tuple[str, str, str]],
    scenarios_lua: Path,
    timeout: int = 120,
    force: bool = False,
    prepare_only: bool = False,
    pack_dir: Path | None = None,
    profile_dir: Path | None = None,
    include_test_dir: bool = False,
    extra_prefix: str = '',
) -> None:
    player, manifest = prepare_profile(
        game, rom_path, build_fn, slots, scenarios_lua,
        timeout=timeout, force=force, pack_dir=pack_dir,
        profile_dir=profile_dir, include_test_dir=include_test_dir,
        extra_prefix=extra_prefix,
    )
    for entry in manifest['states']:
        print(f"F{entry['slot']:<2} {entry['name']} - {entry['instructions']}")
    if prepare_only:
        print(f'Prepared profile: {player.parent}')
        return
    subprocess.Popen([str(player), str(rom_path)], cwd=player.parent)


def _nes2_ram_shift(size_kb: int) -> int:
    """Return NES 2.0 4-bit shift count N such that (64 << N) == size_kb * 1024."""
    if size_kb <= 0:
        return 0
    size_bytes = size_kb * 1024
    if size_bytes < 128 or (size_bytes & (size_bytes - 1)) != 0:
        raise ValueError(f'NES 2.0 RAM size must be a power of 2 >= 1 KB, got {size_kb} KB')
    shift = (size_bytes // 64).bit_length() - 1
    assert (64 << shift) == size_bytes
    return shift


def make_rom_header(
    prg_bytes_len: int,
    chr_bytes_len: int,
    *,
    mapper: str = '176',
    vertical_mirroring: bool = False,
    battery: bool = True,
    wram_kb: int | None = None,
    chr_ram_kb: int = 0,
) -> bytearray:
    """Build a 16-byte iNES or NES 2.0 ROM header for Mapper 176 (FK23C) or Mapper 4 (MMC3)."""
    if mapper not in ('176', 'mmc3'):
        raise ValueError(f'Unsupported mapper {mapper!r}; expected "176" or "mmc3"')
    if prg_bytes_len % 16384 != 0 or prg_bytes_len == 0:
        raise ValueError(f'PRG size must be a non-zero multiple of 16 KB, got {prg_bytes_len}')
    if chr_bytes_len % 8192 != 0:
        raise ValueError(f'CHR size must be a multiple of 8 KB, got {chr_bytes_len}')

    hdr = bytearray(16)
    hdr[0:4] = b'NES\x1a'
    hdr[4] = prg_bytes_len // 16384
    hdr[5] = chr_bytes_len // 8192
    flags6 = (0x01 if vertical_mirroring else 0x00) | (0x02 if battery else 0x00)

    if mapper == '176':
        hdr[6] = flags6
        hdr[7] = 0xB8  # NES 2.0 + Mapper 176 (high nibble $B0)
        w_kb = 32 if wram_kb is None else wram_kb
        shift = _nes2_ram_shift(w_kb)
        hdr[10] = (shift << 4) if battery else shift
        if chr_ram_kb > 0:
            hdr[11] = _nes2_ram_shift(chr_ram_kb)
        return hdr

    # Standard MMC3 (Mapper 4)
    hdr[6] = 0x40 | flags6
    w_kb = 8 if wram_kb is None else wram_kb
    if chr_ram_kb > 0:
        # NES 2.0 Mapper 4 when >8 KB CHR-RAM is required (e.g. 32 KB CHR-RAM for mm2/zelda)
        hdr[7] = 0x08
        shift = _nes2_ram_shift(w_kb)
        hdr[10] = (shift << 4) if battery else shift
        hdr[11] = _nes2_ram_shift(chr_ram_kb)
    else:
        # Classic iNES 1.0 Mapper 4 for maximum flash-cart & emulator compatibility
        hdr[7] = 0x00
    return hdr
