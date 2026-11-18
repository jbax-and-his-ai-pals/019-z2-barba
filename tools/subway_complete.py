"""Launch Where's Barba at the Subway Complete save state in an isolated Mesen profile."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from prepare_player import apply_play_defaults

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / 'build/Subway Complete.mss'
ROM_PATH = ROOT / 'play/wheres-barba.nes'
PROFILE_DIR = ROOT / 'build/mesen-scenarios/subway-complete'


def prepare() -> tuple[Path, Path]:
    if not STATE_PATH.is_file():
        raise SystemExit(f'Save state missing: {STATE_PATH}')
    if not ROM_PATH.is_file():
        import build_waldo
        build_waldo.build()
    if not ROM_PATH.is_file():
        raise SystemExit(f'ROM missing: {ROM_PATH}')

    source_exe = ROOT / '.tools/mesen/Mesen.exe'
    if not source_exe.is_file():
        raise SystemExit('Mesen is missing. Run tools/bootstrap.ps1 -WithEmulator first.')

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    player = PROFILE_DIR / 'Mesen.exe'
    if not player.exists():
        shutil.copyfile(source_exe, player)

    slots = PROFILE_DIR / 'slots'
    slots.mkdir(exist_ok=True)
    shutil.copyfile(STATE_PATH, slots / f'{ROM_PATH.stem}_1.mss')
    (PROFILE_DIR / 'saves').mkdir(exist_ok=True)

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
        'SaveStateFolder': str(slots),
    })

    shortcuts = preferences.setdefault('ShortcutKeys', [])
    for entry in shortcuts:
        for key_field in ('KeyCombination', 'KeyCombination2'):
            combo = entry.get(key_field)
            if combo and combo.get('Key1') == 90 and not combo.get('Key2') and not combo.get('Key3'):
                combo['Key1'] = 0
    shortcuts[:] = [s for s in shortcuts if s.get('Shortcut') != 'LoadStateSlot1']
    shortcuts.append({'Shortcut': 'LoadStateSlot1', 'KeyCombination': {'Key1': 90, 'Key2': 0, 'Key3': 0}})

    script_window = config.setdefault('Debug', {}).setdefault('ScriptWindow', {})
    script_window['AllowIoOsAccess'] = True
    script_window['AutoStartScriptOnLoad'] = True
    settings.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')

    script = PROFILE_DIR / 'load_subway_complete.lua'
    script.write_text(
        f'local STATE_PATH = {json.dumps(STATE_PATH.as_posix())}\n'
        'local loaded = false\n'
        'local cb\n'
        'cb = emu.addEventCallback(function()\n'
        '    if loaded then return end\n'
        '    loaded = true\n'
        '    local f = assert(io.open(STATE_PATH, "rb"))\n'
        '    local data = f:read("*a")\n'
        '    f:close()\n'
        '    emu.loadSavestate(data)\n'
        '    emu.removeEventCallback(cb, emu.eventType.endFrame)\n'
        'end, emu.eventType.endFrame)\n',
        encoding='utf-8',
    )
    return player, script


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true', help='Prepare profile without opening Mesen.')
    args = parser.parse_args()

    player, script = prepare()
    if args.prepare_only:
        print(f'Prepared Subway Complete profile: {PROFILE_DIR}')
        return

    subprocess.Popen([str(player), str(script), str(ROM_PATH)], cwd=PROFILE_DIR)
    print('Opened Where\'s Barba at Subway Complete. Press F1 anytime to reload.')


if __name__ == '__main__':
    main()
