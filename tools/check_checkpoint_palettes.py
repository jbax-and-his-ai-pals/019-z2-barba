"""Compare town checkpoint background palettes with vanilla through the same fixture."""
import json
import create_test_pack as pack
from emulator_test import run


def compare() -> dict:
    palettes = {}
    for name, rom in [('barba', 'build/barba.nes'), ('vanilla', 'roms/z2.nes')]:
        folder = pack.ROOT / 'build' / ('checkpoint-palettes-' + name)
        folder.mkdir(parents=True, exist_ok=True)
        script = folder / 'generate.lua'
        script.write_text('PACK_DIR=' + json.dumps(folder.as_posix()) + chr(10)
                          + pack.scene_prefix('world')
                          + (pack.ROOT / 'tools/state_scenarios.lua').read_text())
        if run(script, pack.ROOT / rom, 60):
            raise ValueError('Palette fixture failed: ' + name)
        palettes[name] = {}
        for line in (folder / 'capture-log.txt').read_text().splitlines():
            if line.startswith('PALETTE '):
                _, key, values = line.split(' ', 2)
                palettes[name][key] = values
    for key in ['darunia', 'old-kasuto']:
        actual = palettes['barba'][key]
        expected = palettes['vanilla'][key]
        if actual != expected:
            raise ValueError(f'{key}: Barba {actual} != vanilla {expected}')
        print(f'PASS {key}: Barba = vanilla: {actual}')
    return palettes


if __name__ == '__main__':
    compare()
