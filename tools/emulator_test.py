"""Run a checked-in Lua scenario with portable Mesen 2; no GUI or global settings."""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(scenario: Path, rom: Path, timeout: int = 30) -> int:
    emulator = ROOT / '.tools/mesen/Mesen.exe'
    if not emulator.exists():
        raise SystemExit('Portable Mesen is missing. See docs/BUILD.md.')
    settings = emulator.parent / 'settings.json'
    settings.write_text(json.dumps({'Debug': {'ScriptWindow': {'AllowIoOsAccess': True}}}))
    output = ROOT / 'build'
    output.mkdir(exist_ok=True)
    runner = output / (scenario.stem + '-run.lua')
    runner.write_text('OUTPUT_DIR = ' + json.dumps(output.as_posix()) + '\n' + scenario.read_text())
    result = subprocess.run([str(emulator), '--testRunner', str(runner), str(rom.resolve()),
                             f'--timeout={timeout}'], capture_output=True, timeout=timeout+10)
    (output / (scenario.stem + '-mesen.log')).write_bytes(result.stdout + result.stderr)
    print(f'{scenario.name}: Mesen exit {result.returncode}')
    return result.returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scenario', type=Path)
    parser.add_argument('--rom', type=Path, default=ROOT / 'build/barba.nes')
    args = parser.parse_args()
    raise SystemExit(run(args.scenario, args.rom))
