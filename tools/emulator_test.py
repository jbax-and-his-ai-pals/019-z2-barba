"""Run a checked-in Lua scenario with portable Mesen 2; no GUI or global settings."""
from __future__ import annotations
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(scenario: Path, rom: Path, timeout: int = 30) -> int:
    emulator = ROOT / '.tools/mesen/Mesen.exe'
    if not emulator.exists():
        raise SystemExit('Portable Mesen is missing. See docs/BUILD.md.')
    settings = emulator.parent / 'settings.json'
    output = ROOT / 'build'
    output.mkdir(exist_ok=True)
    saves = Path(tempfile.mkdtemp(prefix='test-saves-', dir=output))
    settings.write_text(json.dumps({
        'Debug': {'ScriptWindow': {'AllowIoOsAccess': True}},
        'Nes': {'AutoConfigureInput': False, 'Port1': {'Type': 'NesController'}},
        'Preferences': {'OverrideSaveDataFolder': True, 'SaveDataFolder': str(saves)}
    }))
    runner = output / (scenario.stem + '-run.lua')
    prefix = 'OUTPUT_DIR = ' + json.dumps(output.as_posix()) + '\n'
    prefix += 'TEST_DIR = ' + json.dumps((ROOT/'tests').as_posix()) + '\n'
    error_path = output/(scenario.stem+'-error.txt')
    error_path.write_text('')
    prefix += 'ERROR_PATH = ' + json.dumps(error_path.as_posix()) + '\n'
    labels_file = rom.resolve().parent/'build-report.json'
    labels = json.loads(labels_file.read_text())['labels'] if labels_file.exists() else {}
    prefix += 'LABELS = {' + ','.join(f'{name}={value}' for name, value in labels.items()) + '}\n'
    guard = '''
local function failScenario(message)
    local file=assert(io.open(ERROR_PATH,'w'))
    file:write(tostring(message));file:close()
    local stop=emu.exit or emu.stop;stop(2)
end
local function guarded(fn)
    return function(...)
        local ok,result=xpcall(fn,debug.traceback,...)
        if not ok then failScenario(result) else return result end
    end
end
local addEvent=emu.addEventCallback
emu.addEventCallback=function(fn,...) return addEvent(guarded(fn),...) end
local addMemory=emu.addMemoryCallback
emu.addMemoryCallback=function(fn,...) return addMemory(guarded(fn),...) end
local function runScenario()
'''
    runner.write_text(prefix + guard + scenario.read_text() + '\nend\nguarded(runScenario)()\n')
    result = subprocess.run([str(emulator), '--testRunner', str(runner), str(rom.resolve()),
                             f'--timeout={timeout}'], capture_output=True, timeout=timeout+10)
    (output / (scenario.stem + '-mesen.log')).write_bytes(result.stdout + result.stderr)
    print(f'{scenario.name}: Mesen exit {result.returncode}')
    if error_path.read_text():
        print(error_path.read_text())
        return result.returncode or 2
    return result.returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scenario', type=Path)
    parser.add_argument('--rom', type=Path, default=ROOT / 'build/barba.nes')
    args = parser.parse_args()
    raise SystemExit(run(args.scenario, args.rom))
