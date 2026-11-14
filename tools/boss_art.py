"""Compile boss-derived playable Barba studies from the user's verified ROM.

Only the extraction/assembly recipe is committed. Original CHR pixels remain in
the local ROM and generated build previews. Frames are stored LEFT-facing, as
required by Zelda II's side-view renderer, and use the original palette indices.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from nes import CHR_OFFSET, decode_tile, load_source, write_png

ROOT = Path(__file__).resolve().parents[1]
PALETTE = [(20, 22, 28), (194, 43, 25), (255, 168, 57), (255, 243, 205)]
HEAD_PAIRS = {
    'closed': (0x14, 0x16, 0x18, 0x1A),
    'half': (0x1C, 0x22, 0x24, 0x26),
    'open': (0x28, 0x2A, 0x2C, 0x2E),
}


def source_pair(rom: bytes, tile: int, bank: int = 25) -> list[str]:
    """Even tile identifies an 8x16 pair in the selected 4 KiB CHR bank."""
    rows = []
    for half in (0, 1):
        start = CHR_OFFSET + bank*4096 + (tile+half)*16
        rows += [''.join(map(str, row)) for row in decode_tile(rom[start:start+16])]
    return rows


def source_head(rom: bytes, jaw: str = 'closed') -> list[str]:
    pairs = [source_pair(rom, tile) for tile in HEAD_PAIRS[jaw]]
    return [''.join(pair[y] for pair in pairs) for y in range(16)]


def resize_x(rows: list[str], width: int) -> list[str]:
    """Nearest-neighbor width adaptation; native vertical detail is preserved."""
    old = len(rows[0])
    return [''.join(row[min(old-1, (x*old+width//2)//width)] for x in range(width)) for row in rows]


def _blit(canvas: list[list[str]], rows: list[str], x: int, y: int) -> None:
    for iy, row in enumerate(rows):
        for ix, pixel in enumerate(row):
            if pixel != '0' and 0 <= y+iy < len(canvas) and 0 <= x+ix < len(canvas[0]):
                canvas[y+iy][x+ix] = pixel


def make_frames(rom: bytes, width: int = 24) -> dict[str, list[str]]:
    """Return named pixel-row frames in a 16x48 or 24x48 LEFT-facing canvas.

    Standing muzzle: visual row 11 (origin near x0). Crouched muzzle: row 27.
    Head is assembled from real boss tiles and resampled only horizontally.
    Neck strip is native A0/A2; bottom coils are masked native neck textures.
    The renderer must decide visual-height versus physical collision policy.
    """
    if width not in (16, 24):
        raise ValueError('Supported study widths: 16 and 24')
    neck = [''.join((source_pair(rom, 0xA0)[y], source_pair(rom, 0xA2)[y])) for y in range(16)]
    neck_width = 16 if width == 24 else 12
    neck = resize_x(neck, neck_width)

    def pose(jaw='closed', phase=0, crouch=False, hurt=False) -> list[str]:
        canvas = [['0']*width for _ in range(48)]
        head = resize_x(source_head(rom, jaw), width)
        head_y = 16 if crouch else 0
        if hurt:
            head_y += 2
        _blit(canvas, head, 0, head_y)
        # Alternating offsets provide a restrained source-like neck undulation.
        neck_x = width-neck_width
        for y in range(head_y+16, 42):
            sway = (0, -1, 0, 1)[((y-head_y)//8+phase)%4]
            row = neck[(y-head_y-16)%16]
            _blit(canvas, [row], neck_x+sway, y)
        # Curl the native segmented belly into a grounded coil. The elliptical
        # mask is new geometry; its color/segment texture comes from boss CHR.
        cx = (width-1)/2
        for y in range(32, 48):
            for x in range(width):
                outer = ((x-cx)/(width/2))**2 + ((y-40)/7.1)**2
                inner = ((x-cx)/(width/3.8))**2 + ((y-39)/2.5)**2
                if outer <= 1 and (inner >= 1 or x >= width-7):
                    sample = neck[(y+phase*2)%16][int(x*neck_width/width)]
                    canvas[y][x] = sample if sample != '0' else '1'
        return [''.join(row) for row in canvas]

    frames = {name: pose(jaw, phase, crouch, hurt) for name,jaw,phase,crouch,hurt in [
        ('idle','closed',0,False,False),
        ('walk0','closed',0,False,False),
        ('walk1','closed',1,False,False),
        ('walk2','closed',2,False,False),
        ('windup','half',0,False,False),
        ('attack','open',0,False,False),
        ('jump','closed',2,False,False),
        ('crouch','closed',0,True,False),
        ('crouch-attack','open',0,True,False),
        ('hurt','half',0,False,True),
        ('item','closed',0,False,False),
    ]}
    # Vertical poses turn the native head instead of inventing a different face.
    head = source_head(rom, 'open')
    up = [''.join(head[15-x][y] for x in range(16)) for y in range(32)]
    down = [row[::-1] for row in up[::-1]]
    for name, rows, y in [('up', up, 0), ('down', down, 16)]:
        canvas = [['0']*width for _ in range(48)]
        base = frames['idle']
        for at in (range(32,48) if name=='up' else range(0,16)):
            source_y = at if name=='up' else at+32
            canvas[at] = list(base[source_y])
        _blit(canvas, rows, (width-16)//2, y)
        frames[name] = [''.join(row) for row in canvas]
    frames['death'] = ['0'*width]*16 + frames['crouch'][16:]
    return frames


def make_study(root: Path = ROOT) -> Path:
    rom = load_source(root/'roms/z2.nes')
    images = []
    names = []
    for width in (16, 24):
        frames = make_frames(rom, width)
        for name in ('idle','walk1','windup','attack','crouch','crouch-attack','up','down'):
            images.append(frames[name]);names.append(f'{width}x48 {name}')
    pixels = []
    for batch in (images[:8], images[8:]):
        for y in range(48):
            row = []
            for picture in batch:
                row += [PALETTE[int(c)] for c in picture[y]] + [PALETTE[0]]*8
            row += [PALETTE[0]]*(256-len(row))
            pixels.append(row)
        pixels += [[PALETTE[0]]*256 for _ in range(8)]
    output = root/'build/barba-boss-study.png'
    write_png(output,pixels,4)
    (root/'build/barba-boss-study.json').write_text(json.dumps({
        'order':names,'source_bank_4k':25,'palette_nes':['0F','16','27','30'],
        'native_head_size':[32,16],'head_pairs':HEAD_PAIRS,'neck_pairs':[160,162],
        'muzzle_rows':{'standing':11,'crouched':27},
        'note':'Recipe-only source; pixels and previews are generated from the user ROM.'
    },indent=2)+'\n')
    return output


if __name__ == '__main__':
    print(make_study())
