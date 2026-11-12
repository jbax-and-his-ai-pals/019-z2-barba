"""Build Barba Edition from a verified local ROM, preserving all unpatched bytes."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from assets import compile_assets
from bps import apply, encode
from nes import CHR_OFFSET, SOURCE_SHA256, load_source, prg_offset

ROOT = Path(__file__).resolve().parents[1]


class Overlay:
    def __init__(self, source: bytes):
        self.source = source
        self.target = bytearray(source)
        self.ranges: list[dict] = []

    def put(self, offset: int, data: bytes, expected: bytes, name: str) -> None:
        if len(data) != len(expected) or not 0 <= offset <= len(self.source)-len(data):
            raise ValueError(f'Invalid patch length/location: {name}')
        if self.source[offset:offset+len(data)] != expected:
            raise ValueError(f'Original bytes differ at {offset:05X}: {name}')
        for previous in self.ranges:
            if offset < previous['offset']+previous['length'] and previous['offset'] < offset+len(data):
                raise ValueError(f'Overlapping patches: {name} and {previous["name"]}')
        self.target[offset:offset+len(data)] = data
        self.ranges.append({'name': name, 'offset': offset, 'length': len(data),
                            'sha256': hashlib.sha256(data).hexdigest()})

    def prg(self, bank: int, address: int, data: bytes, expected: bytes, name: str) -> None:
        self.put(prg_offset(bank, address), data, expected, name)


def assemble(output: Path) -> dict[str, int]:
    def find(name: str) -> str:
        local = ROOT / f'.tools/cc65/bin/{name}.exe'
        result = str(local) if local.exists() else shutil.which(name)
        if not result:
            raise ValueError(f'{name} is missing. Install cc65; see docs/BUILD.md.')
        return result
    subprocess.run([find('ca65'), str(ROOT/'src/barba.asm'), '-g', '-o', 'barba.o'], cwd=output, check=True)
    subprocess.run([find('ld65'), '-C', str(ROOT/'src/barba.cfg'), 'barba.o',
                    '-Ln', 'barba.lbl', '-m', 'barba.map', '--dbgfile', 'barba.dbg'], cwd=output, check=True)
    labels = {}
    for line in (output/'barba.lbl').read_text().splitlines():
        _, address, label = line.split()
        if not label.startswith('.@'):
            labels[label.lstrip('.')] = int(address, 16)
    return labels


def build(source_path: Path, output: Path) -> dict:
    source = load_source(source_path)
    if output.resolve() == source_path.parent.resolve():
        raise ValueError('Output must not be the source ROM directory')
    output.mkdir(parents=True, exist_ok=True)
    labels = assemble(output)
    overlay = Overlay(source)
    for filename, bank, address in [('code', 0, 0xAA40), ('lava', 7, 0xD39A), ('gateway', 7, 0xFEAA)]:
        data = (output/f'barba-{filename}.bin').read_bytes()
        overlay.prg(bank, address, data, b'\xFF'*len(data), f'New {filename} routines')
    def hook(bank: int, address: int, label: str, opcode: int, expected: str, pad: int = 0):
        dest = labels[label]
        data = bytes([opcode, dest & 255, dest >> 8]) + b'\xEA'*pad
        overlay.prg(bank, address, data, bytes.fromhex(expected), label+' hook')
    hook(0, 0x877C, 'BarbaOverworld', 0x20, 'a2 0e a0 00', 1)
    hook(7, 0xD52D, 'BarbaDisplay', 0x20, '20 f0 eb')
    hook(7, 0xE9A2, 'HitboxGateway', 0x4C, 'a0 00 ad')
    hook(7, 0xE0A4, 'LavaSurface', 0x4C, 'a9 01 85')
    hook(7, 0xD50D, 'BarbaUpdate', 0x20, '20 47 98')
    dest = labels['BarbaInferno']
    overlay.prg(0, 0x8E56, bytes([dest & 255, dest >> 8]), bytes.fromhex('e6 91'), 'Inferno spell pointer')

    # Keep the raft route and item checks. Return after the new two-sprite avatar.
    overlay.prg(0, 0x81C0, b'\x60', b'\xA9', 'Sea crossing avatar')
    overlay.prg(0, 0x814F, b'\x1E', b'\x10', 'Dedicated overworld CHR pair')
    overlay.prg(0, 0x960B, bytes.fromhex('a9 40 85 ed'), bytes.fromhex('a9 20 85 ed'), 'Flame attack sound')
    overlay.prg(0, 0x9819, bytes.fromhex('30 d0'), bytes.fromhex('20 e0'), 'Faster ranged flame')

    mapping, graphics, ow, _ = compile_assets(ROOT)
    offset = prg_offset(7, 0xEB25)
    overlay.put(offset, mapping, source[offset:offset+len(mapping)], 'Dragon animation metasprites')
    for bank in range(0, 26, 2):
        for tile, pair in graphics.items():
            offset = CHR_OFFSET + bank*4096 + tile*16
            overlay.put(offset, pair, source[offset:offset+32], f'CHR {bank:02X}: dragon tile {tile:02X}')
    # Last two CHR banks are filler in the guarded input; dedicate them to overworld.
    world = bytearray(source[CHR_OFFSET+16*4096:CHR_OFFSET+18*4096])
    world[:len(ow)] = ow
    offset = CHR_OFFSET+30*4096
    overlay.put(offset, world, b'\xFF'*8192, 'Dedicated overworld graphics')

    old_palette, new_palette = bytes.fromhex('18 36 2a'), bytes.fromhex('16 27 30')
    palette_offsets = [i for i in range(16, CHR_OFFSET-2) if source[i:i+3] == old_palette]
    for offset in palette_offsets:
        overlay.put(offset, new_palette, old_palette, f'Dragon palette at {offset:05X}')

    # Existing menu stores 14-byte rows. Preserve border, cost digits and spacing.
    for i, name in enumerate(['SCALES','SPRING','RENEW','WYRMLNG','BLAZE','MIRROR','ANCIENT','INFERNO']):
        offset = prg_offset(0, 0x9C2A + i*14)
        data = bytes(0xDA+ord(c)-ord('A') for c in name.ljust(7) if c != ' ')
        data += b'\xCF'*(7-len(data))
        overlay.put(offset, data, source[offset:offset+7], f'Spell menu: {name}')

    target = bytes(overlay.target)
    if target[:16] != source[:16] or len(target) != len(source):
        raise ValueError('Mapper/header/size invariant failed')
    patch = encode(source, target, 'Zelda II - Barba Edition | development alpha',
                   [(CHR_OFFSET+30*4096+len(ow), CHR_OFFSET+16*4096+len(ow), 8192-len(ow))])
    if apply(source, patch) != target:
        raise ValueError('BPS patch round-trip failed')
    # Independent post-application source check protects the original file.
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Source ROM changed during build')
    (output/'barba.nes').write_bytes(target)
    (output/'barba.bps').write_bytes(patch)
    report = {'stage': 'development alpha', 'source_sha256': SOURCE_SHA256,
              'output_sha256': hashlib.sha256(target).hexdigest(),
              'size': len(target), 'changed_bytes': sum(a != b for a, b in zip(source, target)),
              'labels': labels, 'patches': sorted(overlay.ranges, key=lambda r: r['offset'])}
    (output/'build-report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, default=ROOT/'roms/z2.nes')
    parser.add_argument('--out', type=Path, default=ROOT/'build')
    args = parser.parse_args()
    try:
        report = build(args.rom, args.out)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Build failed: {error}\n')
    print(f"Built {args.out/'barba.nes'} ({report['changed_bytes']:,} changed bytes)")
    print(f"BPS patch verified; SHA-256 {report['output_sha256']}")
