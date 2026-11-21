"""Create a save-state pack inside Friday the 13th inside Zelda II (build/barba.nes)."""
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
PACK_DIR = ROOT / 'build/f13-z2-pack'
PROFILE_DIR = ROOT / 'build/mesen-scenarios/f13-z2'

SLOTS = [
    ('ruto-portal', 'Ruto Portal Door', 'Standing at the portal door in Ruto. Press Up then B to enter Friday the 13th.'),
    ('f13-title', 'F13 Title Screen (in Zelda II)', 'Inside Friday the 13th from Ruto door. Press Start to play, or Start+Select anytime to return to Ruto.'),
    ('f13-map', 'F13 Crystal Lake Camp Map', 'Barba selected on the Camp Map (BARBA + portrait). Press Start to enter camp, or Start+Select to return.'),
    ('f13-exterior', 'F13 Exterior Camp Path', '16x32 Barba on the camp path with HUD portrait and zombie. Start+Select returns to Ruto.'),
    ('f13-cabin', 'F13 Inside Cabin', 'Barba inside a Crystal Lake cabin. Press Down at the door to exit, or Start+Select to return.'),
    ('f13-win-return', 'F13 Day 3 Victory Return', 'Beating Day 3 triggers the automatic wavy transition back to Ruto in Zelda II.'),
]


def create(force: bool = False) -> dict:
    if not ROM_PATH.is_file():
        import build
        build.build(ROOT / 'roms/z2.nes', ROOT / 'build', ROOT / 'roms/roar.wav')

    digest = hashlib.sha256(ROM_PATH.read_bytes()).hexdigest()
    manifest_path = PACK_DIR / 'manifest.json'
    if manifest_path.exists() and not force:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('rom_sha256') == digest and all((PACK_DIR / f'{s[0]}.mss').exists() for s in SLOTS):
            return manifest

    PACK_DIR.mkdir(parents=True, exist_ok=True)
    scenario = ROOT / 'build/generate-f13-z2-states.lua'
    prefix = (
        f'PACK_DIR = {json.dumps(PACK_DIR.as_posix())}\n'
        f'TEST_DIR = {json.dumps((ROOT / "tests").as_posix())}\n'
    )
    scenario.write_text(prefix + (ROOT / 'tools/f13_z2_scenarios.lua').read_text(encoding='utf-8'), encoding='utf-8')
    if run(scenario, ROM_PATH, 120):
        raise SystemExit('F13-in-Zelda-II state generation failed; see build/generate-f13-z2-states-error.txt')

    states = []
    for slot, (sid, name, desc) in enumerate(SLOTS, 1):
        mss = PACK_DIR / f'{sid}.mss'
        if not mss.is_file() or not mss.read_bytes().startswith(b'MSS'):
            raise SystemExit(f'Missing or invalid state: {mss}')
        states.append({'slot': slot, 'id': sid, 'name': name, 'instructions': desc, 'file': mss.name})

    manifest = {'rom_sha256': digest, 'folder': str(PACK_DIR), 'rom': str(ROM_PATH), 'states': states}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
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

    script_window = config.setdefault('Debug', {}).setdefault('ScriptWindow', {})
    script_window['AllowIoOsAccess'] = False
    settings.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    return player, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true', help='Regenerate all save states.')
    parser.add_argument('--prepare-only', action='store_true', help='Prepare profile without opening Mesen.')
    args = parser.parse_args()

    player, manifest = prepare(force=args.force)
    for entry in manifest['states']:
        print(f"F{entry['slot']:<2} {entry['name']} - {entry['instructions']}")
    if args.prepare_only:
        print(f'Prepared profile: {PROFILE_DIR}')
        return
    subprocess.Popen([str(player), str(ROM_PATH)], cwd=PROFILE_DIR)


if __name__ == '__main__':
    main()
