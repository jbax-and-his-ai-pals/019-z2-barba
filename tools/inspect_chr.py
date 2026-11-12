"""Render local ROM graphics for research. Outputs stay in the ignored build folder."""
import argparse
from pathlib import Path
from nes import CHR_OFFSET, decode_tile, load_source, write_png

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--rom", type=Path, default=Path("roms/z2.nes"))
args = parser.parse_args()
rom = load_source(args.rom)
colors = [(22, 24, 30), (242, 107, 44), (255, 204, 97), (255, 244, 217)]
for bank in range(32):
    pixels = [[(55, 58, 68)] * 144 for _ in range(144)]
    for tile in range(256):
        offset = CHR_OFFSET + bank * 4096 + tile * 16
        for y, row in enumerate(decode_tile(rom[offset:offset+16])):
            for x, value in enumerate(row):
                pixels[(tile // 16)*9+y][(tile % 16)*9+x] = colors[value]
    write_png(Path(f"build/chr/bank-{bank:02X}.png"), pixels, 4)
print("Rendered 32 CHR banks to build/chr/")
