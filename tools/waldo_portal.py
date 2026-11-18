"""Play the experimental Rauru-to-Waldo round trip in portable Mesen."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import zlib
from pathlib import Path

from prepare_player import apply_play_defaults


ROOT = Path(__file__).resolve().parents[1]
WALDO = ROOT / 'roms/waldo.nes'
BARBA = ROOT / 'build/barba.nes'


def prepare_mesen(session: Path) -> Path:
    source = ROOT / '.tools/mesen'
    if not (source / 'Mesen.exe').is_file():
        raise SystemExit('Portable Mesen is missing. See docs/BUILD.md.')
    emulator = session / 'Mesen.exe'
    for path in source.iterdir():
        if path.is_file() and path.name != 'settings.json':
            shutil.copy2(path, session / path.name)
    config = {
        'Debug': {'ScriptWindow': {'AllowIoOsAccess': True, 'AutoStartScriptOnLoad': True}},
        'Preferences': {
            'SingleInstance': False, 'AutomaticallyCheckForUpdates': False,
            'OverrideSaveDataFolder': True, 'SaveDataFolder': str(session / 'saves'),
        },
    }
    (session / 'saves').mkdir()
    apply_play_defaults(config)
    (session / 'settings.json').write_text(json.dumps(config), encoding='utf-8')
    return emulator


def play_stage(command: list[str], session: Path) -> int:
    process = subprocess.Popen(command, cwd=session)
    try:
        while not any((session / name).is_file() for name in ('next', 'error')):
            try:
                return process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                continue
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()


def run_stage(emulator: Path, stage: str, headless: bool) -> str:
    session = emulator.parent
    marker = session / 'next'
    error = session / 'error'
    marker.unlink(missing_ok=True)
    error.unlink(missing_ok=True)
    script = session / f'{stage}.lua'
    variables = {
        'PORTAL_DIR': session.as_posix(), 'TEST_DIR': (ROOT / 'tests').as_posix(),
        'STAGE': stage, 'HEADLESS': headless,
    }
    script.write_text(
        ''.join(f'{key} = {json.dumps(value, ensure_ascii=False)}\n' for key, value in variables.items())
        + (ROOT / 'tools/waldo_portal.lua').read_text(encoding='utf-8'),
        encoding='utf-8',
    )
    rom = WALDO if stage == 'waldo' else BARBA
    mode = ['--testRunner', '--timeout=30'] if headless else ['--doNotSaveSettings']
    command = [str(emulator), *mode, str(script), str(rom)]
    if headless:
        exit_code = subprocess.run(command, cwd=session, timeout=40, check=False).returncode
    else:
        exit_code = play_stage(command, session)
    if error.is_file():
        raise SystemExit(error.read_text(encoding='utf-8'))
    if exit_code or (headless and not marker.is_file()):
        raise SystemExit(f'{stage} failed (Mesen exit {exit_code}).')
    return marker.read_text(encoding='ascii') if marker.is_file() else 'closed'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true', help='Verify the round trip headlessly.')
    args = parser.parse_args()
    if not BARBA.is_file():
        raise SystemExit('Run python tools/build.py to build Barba first.')
    if not WALDO.is_file():
        raise SystemExit('Place the US Where’s Waldo? dump at roms/waldo.nes.')
    waldo = WALDO.read_bytes()
    if waldo[:7] != b'NES\x1a\x08\x10\x40' or zlib.crc32(waldo[16:]) != 0xC3463A3D:
        raise SystemExit('Unexpected Where’s Waldo? ROM. Use the verified US dump.')

    report = BARBA.parent / 'waldo-portal.txt'
    screenshot = BARBA.parent / 'waldo-portal.png'
    if args.smoke:
        report.unlink(missing_ok=True)
        screenshot.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='waldo-portal-', dir=BARBA.parent) as directory:
        emulator = prepare_mesen(Path(directory))
        if run_stage(emulator, 'setup', True) != 'ready':
            raise SystemExit('Could not prepare the Rauru doorstep.')
        if not args.smoke:
            print('Press Up at the Rauru door. The Moon ending or Start + Select returns to Rauru.', flush=True)
        stage = 'enter'
        while stage in ('enter', 'waldo', 'return'):
            stage = run_stage(emulator, stage, args.smoke)
        if args.smoke:
            if stage != 'done':
                raise SystemExit('The portal did not complete the round trip.')
            arrival = (emulator.parent / 'arrival').read_text(encoding='ascii')
            proof = '\n'.join((
                'PASS Native Rauru doorway handed off to Waldo',
                'PASS Waldo returned control to Barba',
                f'PASS Exact Rauru return {arrival}',
                'PASS Held Up did not reopen the portal',
                'RESULT PASS',
            ))
            shutil.copy2(emulator.parent / 'waldo.png', screenshot)
            report.write_text(proof + '\n', encoding='ascii')
            print(proof)


if __name__ == '__main__':
    main()
