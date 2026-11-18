"""Prepare a separate portable Mesen profile for human playtesting."""
import ctypes
import json
import os
import shutil
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def monitor_scale(location: dict) -> float:
    if os.name != 'nt':
        return 1.0
    user32 = ctypes.windll.user32
    user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    user32.MonitorFromPoint.restype = wintypes.HMONITOR
    get_scale = ctypes.windll.shcore.GetScaleFactorForMonitor
    get_scale.argtypes = [wintypes.HMONITOR, ctypes.POINTER(ctypes.c_int)]

    # Mesen stores the window position in physical pixels and its size in DIPs.
    previous = user32.SetThreadDpiAwarenessContext(-4)  # Per-monitor aware V2
    try:
        point = wintypes.POINT(location.get('X', 0), location.get('Y', 0))
        monitor = user32.MonitorFromPoint(point, 1)  # Primary monitor if offscreen
        percent = ctypes.c_int()
        if get_scale(monitor, ctypes.byref(percent)) == 0 and percent.value:
            return percent.value / 100
        return 1.0
    finally:
        if previous:
            user32.SetThreadDpiAwarenessContext(previous)


def apply_play_defaults(config: dict) -> None:
    nes = config.setdefault('Nes', {})
    nes['AutoConfigureInput'] = False
    port = nes.setdefault('Port1', {})
    port['Type'] = 'NesController'
    keyboard = port.setdefault('Mapping1', {})
    if not keyboard.get('A'):
        keyboard.update({'A': 67, 'B': 69, 'Start': 6,
                         'Up': 24, 'Down': 26, 'Left': 23, 'Right': 25})
        port.setdefault('Mapping2', {
            'A': 0x100E, 'B': 0x100D, 'Start': 0x1005, 'Select': 0x1006,
            'Up': 0x1001, 'Down': 0x1002, 'Left': 0x1003, 'Right': 0x1004,
        })
    keyboard['Select'] = 18  # Space in Mesen's KeyDefinitions.h

    window = config.setdefault('MainWindow', {})
    scale = monitor_scale(window.get('WindowLocation', {}))
    menu_height = 0 if config.get('Preferences', {}).get('AutoHideMenu') else 25
    window['WindowSize'] = {'Width': round(256 * 4 / scale),
                            'Height': round(240 * 4 / scale) + menu_height}
    window['WindowIsMaximized'] = False


def prepare() -> None:
    source = ROOT / '.tools/mesen/Mesen.exe'
    player = ROOT / '.tools/mesen-play/Mesen.exe'
    if not source.exists():
        raise SystemExit('Mesen is missing. Run tools/bootstrap.ps1 -WithEmulator first.')
    player.parent.mkdir(parents=True, exist_ok=True)
    if not player.exists():
        shutil.copyfile(source, player)

    settings = player.with_name('settings.json')
    if settings.exists():
        original = settings.read_text(encoding='utf-8-sig')
    else:
        original = json.dumps({
            'Debug': {'ScriptWindow': {'AllowIoOsAccess': False}},
            'Preferences': {'OverrideSaveDataFolder': True,
                            'SaveDataFolder': str(ROOT / 'build/play-saves')},
        })
    config = json.loads(original)
    apply_play_defaults(config)
    if config != json.loads(original):
        settings.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    print(player)


if __name__ == '__main__':
    prepare()
