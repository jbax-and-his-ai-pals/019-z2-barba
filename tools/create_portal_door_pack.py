"""Generate on-the-fly Mesen save states at every active portal door in build/portal-manifest.json."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from emulator_test import run
from prepare_player import apply_play_defaults

ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / 'build/barba.nes'
MANIFEST_PATH = ROOT / 'build/portal-manifest.json'
PACK_DIR = ROOT / 'build/portal-doors-pack'
PROFILE_DIR = ROOT / 'build/mesen-scenarios/portal-doors'


def _lua_slots(slots: list[dict]) -> str:
    entries = []
    for s in slots:
        d = s['door']
        x_mid = (d['x_lo'] + d['x_hi']) // 2
        entries.append(
            f"  {{ slot = {s['slot']}, id = {json.dumps(s['id'])}, "
            f"town = {d['town_id']}, room = {d['room']}, page = {d['page']}, x = {x_mid} }}"
        )
    return 'PORTAL_SLOTS = {\n' + ',\n'.join(entries) + '\n}\n'


def create(force: bool = False) -> dict:
    if not ROM_PATH.is_file() or not MANIFEST_PATH.is_file():
        raise SystemExit('Missing build/barba.nes or build/portal-manifest.json. Run python tools/build.py first.')

    portal_manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    slots = portal_manifest['slots']
    digest = hashlib.sha256(ROM_PATH.read_bytes()).hexdigest()
    pack_manifest_path = PACK_DIR / 'manifest.json'

    if pack_manifest_path.exists() and not force:
        existing = json.loads(pack_manifest_path.read_text(encoding='utf-8'))
        if existing.get('rom_sha256') == digest and all(
            (PACK_DIR / f"portal-{s['id']}.mss").exists() for s in slots
        ):
            return existing

    PACK_DIR.mkdir(parents=True, exist_ok=True)
    scenario = ROOT / 'build/generate-portal-door-states.lua'
    prefix = (
        f'PACK_DIR = {json.dumps(PACK_DIR.as_posix())}\n'
        f'TEST_DIR = {json.dumps((ROOT / "tests").as_posix())}\n'
        + _lua_slots(slots)
    )
    scenario.write_text(
        prefix + (ROOT / 'tools/portal_door_scenarios.lua').read_text(encoding='utf-8'),
        encoding='utf-8',
    )
    if run(scenario, ROM_PATH, 120):
        raise SystemExit('Portal door state generation failed; see build/generate-portal-door-states-error.txt')

    states = []
    for fkey, s in enumerate(slots, 1):
        mss = PACK_DIR / f"portal-{s['id']}.mss"
        if not mss.is_file() or not mss.read_bytes().startswith(b'MSS'):
            raise SystemExit(f'Missing or invalid state: {mss}')
        d = s['door']
        states.append({
            'slot': fkey,
            'id': f"portal-{s['id']}",
            'name': f"{d['town_name']} -> {s['name']}",
            'instructions': f"Standing at {d['town_name']} portal door (room ${d['room']:02X}, page {d['page']}). Press Up to enter {s['name']}.",
            'file': mss.name,
        })

    manifest = {'rom_sha256': digest, 'folder': str(PACK_DIR), 'rom': str(ROM_PATH), 'states': states}
    pack_manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def prepare(force: bool = False) -> tuple[Path, dict]:
    manifest = create(force=force)
    source_exe = ROOT / '.tools/mesen/Mesen.exe'
    if not source_exe.is_file():
        raise SystemExit('Mesen is missing. Run tools/bootstrap.ps1 -WithEmulator first.')

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    player = PROFILE_DIR / 'Mesen.exe'
    if not player.exists():
        shutil.copyfile(source_exe, player)

    slots_dir = PROFILE_DIR / 'slots'
    slots_dir.mkdir(exist_ok=True)
    (PROFILE_DIR / 'saves').mkdir(exist_ok=True)
    for slot in range(len(manifest['states']) + 1, 11):
        (slots_dir / f'{ROM_PATH.stem}_{slot}.mss').unlink(missing_ok=True)

    for entry in manifest['states']:
        shutil.copyfile(PACK_DIR / entry['file'], slots_dir / f"{ROM_PATH.stem}_{entry['slot']}.mss")

    settings = PROFILE_DIR / 'settings.json'
    config = json.loads(settings.read_text(encoding='utf-8-sig')) if settings.exists() else {}
    apply_play_defaults(config)
    preferences = config.setdefault('Preferences', {})
    preferences.update({
        'SingleInstance': False,
        'AutoLoadPatches': False,
        'OverrideSaveDataFolder': True,
        'SaveDataFolder': str(PROFILE_DIR / 'saves'),
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
    config.setdefault('Debug', {}).setdefault('ScriptWindow', {})['AllowIoOsAccess'] = False
    settings.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    return player, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    player, manifest = prepare(force=args.force)
    for s in manifest['states']:
        print(f"F{s['slot']}: {s['name']} -> {s['instructions']}")
    if not args.prepare_only:
        subprocess.Popen([str(player), str(ROM_PATH)], cwd=str(PROFILE_DIR))


if __name__ == '__main__':
    main()
