"""Prepare a separate portable Mesen profile for human playtesting."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / '.tools/mesen/Mesen.exe'
player = ROOT / '.tools/mesen-play/Mesen.exe'
if not source.exists():
    raise SystemExit('Mesen is missing. Run tools/bootstrap.ps1 -WithEmulator first.')
player.parent.mkdir(parents=True, exist_ok=True)
if not player.exists():
    shutil.copyfile(source, player)

settings = player.parent / 'settings.json'
if not settings.exists():
    # Mesen's shared key codes, not Windows VK codes (KeyDefinitions.h).
    keyboard = {'A': 67, 'B': 69, 'Start': 6, 'Select': 116,
                'Up': 24, 'Down': 26, 'Left': 23, 'Right': 25}
    gamepad = {'A': 0x1000+14, 'B': 0x1000+13, 'Start': 0x1000+5,
               'Select': 0x1000+6, 'Up': 0x1000+1, 'Down': 0x1000+2,
               'Left': 0x1000+3, 'Right': 0x1000+4}
    settings.write_text(json.dumps({
        'Nes': {'AutoConfigureInput': False,
                'Port1': {'Type': 'NesController', 'Mapping1': keyboard, 'Mapping2': gamepad}},
        'Debug': {'ScriptWindow': {'AllowIoOsAccess': False}},
        'Preferences': {'OverrideSaveDataFolder': True,
                        'SaveDataFolder': str(ROOT/'build/play-saves')}
    }, indent=2)+'\n')
print(player)
