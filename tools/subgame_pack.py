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


def create_pack(
    game: str,
    rom_path: Path,
    build_fn: Callable[[], None],
    slots: list[tuple[str, str, str]],
    scenarios_lua: Path,
    timeout: int = 120,
    force: bool = False,
) -> dict:
    if not rom_path.is_file():
        build_fn()

    pack_dir = ROOT / f'build/{game}-pack'
    digest = hashlib.sha256(rom_path.read_bytes()).hexdigest()
    manifest_path = pack_dir / 'manifest.json'
    if manifest_path.exists() and not force:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('rom_sha256') == digest and all((pack_dir / f'{s[0]}.mss').exists() for s in slots):
            return manifest

    pack_dir.mkdir(parents=True, exist_ok=True)
    scenario = ROOT / f'build/generate-{game}-states.lua'
    prefix = f'PACK_DIR = {json.dumps(pack_dir.as_posix())}\n'
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


def prepare_profile(
    game: str,
    rom_path: Path,
    build_fn: Callable[[], None],
    slots: list[tuple[str, str, str]],
    scenarios_lua: Path,
    timeout: int = 120,
    force: bool = False,
) -> tuple[Path, dict]:
    manifest = create_pack(game, rom_path, build_fn, slots, scenarios_lua, timeout=timeout, force=force)
    source_exe = ROOT / '.tools/mesen/Mesen.exe'
    if not source_exe.is_file():
        raise SystemExit('Mesen is missing. Run tools/bootstrap.ps1 -WithEmulator first.')

    profile_dir = ROOT / f'build/mesen-scenarios/{game}'
    profile_dir.mkdir(parents=True, exist_ok=True)
    player = profile_dir / 'Mesen.exe'
    if not player.exists():
        shutil.copyfile(source_exe, player)

    slots_dir = profile_dir / 'slots'
    slots_dir.mkdir(exist_ok=True)
    (profile_dir / 'saves').mkdir(exist_ok=True)
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
        'SaveDataFolder': str(profile_dir / 'saves'),
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
) -> None:
    player, manifest = prepare_profile(
        game, rom_path, build_fn, slots, scenarios_lua, timeout=timeout, force=force
    )
    for entry in manifest['states']:
        print(f"F{entry['slot']:<2} {entry['name']} - {entry['instructions']}")
    if prepare_only:
        print(f"Prepared profile: {ROOT / f'build/mesen-scenarios/{game}'}")
        return
    subprocess.Popen([str(player), str(rom_path)], cwd=player.parent)
