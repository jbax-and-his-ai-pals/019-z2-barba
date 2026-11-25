"""Create a save-state pack for standalone Family Feud: Barba Edition (play/standalone/feud-barba.nes)."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from emulator_test import run
from prepare_player import apply_play_defaults

ROM_PATH = ROOT / 'play/standalone/feud-barba.nes'
PACK_DIR = ROOT / 'build/feud-pack'
PROFILE_DIR = ROOT / 'build/mesen-scenarios/feud'

SLOTS = [
    ('title', 'Title Screen (Barba\'s Beef)', 'Family Feud: Barba Edition title screen. Press Start to begin.'),
    ('overview', 'Stage Overview (Barba vs Z2)', 'All 10 animated Barba & Zelda II contestants on stage (random cast, heights, palettes, and Zelda family names).'),
    ('faceoff', 'Face-Off (1-on-1)', 'Head-to-head Face-Off podium with randomized Barba vs Zelda II challenger.'),
    ('stage_barba', 'Barba Family Stage', 'Main Round on the Barba family podium. Watch contestants randomly roar or head-wiggle while idle.'),
    ('stage_z2', 'Zelda II Opposing Stage', 'Opposing Zelda II family on stage with randomized characters and Zelda family name.'),
    ('pre_fast_money', 'Before Fast Money', 'Barba family celebrating on stage right before Fast Money begins.'),
    ('fast_money', 'Fast Money Round', 'Fast Money active with Zelda II survey questions on the clock.'),
    ('after_fast_money', 'After Fast Money ($5,000)', 'Post-Fast Money winnings screen showing $5,000 banked toward the $20,000 grand prize.'),
    ('limit_20k', '$20,000 Limit Victory', 'Grand prize limit screen after reaching $20,000 total winnings.'),
    ('lose_msg', 'Zelda Lose Message', 'End-of-game Zelda II excuse screen (Due to <reason>, the <NAME> family...).'),
]


def create(force: bool = False) -> dict:
    if not ROM_PATH.is_file():
        import pack_feud
        ROM_PATH.parent.mkdir(parents=True, exist_ok=True)
        pack_feud.build_standalone(
            ROM_PATH,
            ROOT / 'roms/feud.nes',
            ROOT / 'roms/z2.nes',
            ROOT / 'assets/barba.json',
        )

    digest = hashlib.sha256(ROM_PATH.read_bytes()).hexdigest()
    manifest_path = PACK_DIR / 'manifest.json'
    if manifest_path.exists() and not force:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('rom_sha256') == digest and all((PACK_DIR / f'{s[0]}.mss').exists() for s in SLOTS):
            return manifest

    PACK_DIR.mkdir(parents=True, exist_ok=True)
    scenario = ROOT / 'build/generate-feud-states.lua'
    prefix = f'PACK_DIR = {json.dumps(PACK_DIR.as_posix())}\n'
    scenario.write_text(prefix + (ROOT / 'tools/feud_scenarios.lua').read_text(encoding='utf-8'), encoding='utf-8')
    if run(scenario, ROM_PATH, 120):
        raise SystemExit('Family Feud state generation failed; see build/generate-feud-states-error.txt')

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
