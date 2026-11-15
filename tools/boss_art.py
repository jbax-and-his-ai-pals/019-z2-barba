"""Compile boss-derived playable Barba studies from the user's verified ROM.

Only the extraction/assembly recipe is committed. Original CHR pixels remain in
the local ROM and generated build previews. Frames are stored LEFT-facing, as
required by Zelda II's side-view renderer, and use the original palette indices.
"""
from __future__ import annotations

import json
from pathlib import Path

from nes import CHR_OFFSET, decode_tile, encode_tile, load_source, write_png

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


UP_SHEAR = 0.5  # 2:1 pixel-art slope; snout rises (width-1)/2 px


def shear_up(rows: list[str], slope: float = UP_SHEAR) -> list[str]:
    """Tilt a LEFT-facing head snout-up by shifting each column vertically.

    Columns stay intact, so the jaw, eye and horns keep their native pixels;
    outlines become clean 2:1 diagonals instead of rotation noise.
    """
    width = len(rows[0])
    lift = round((width-1)*slope)
    out = [['0']*width for _ in range(len(rows)+lift)]
    for x in range(width):
        dy = lift - round((width-1-x)*slope)
        for y, row in enumerate(rows):
            out[y+dy][x] = row[x]
    return [''.join(row) for row in out]


def looking_up(rom: bytes, width: int, neck: list[str], neck_width: int) -> list[str]:
    """Open-jaw head tilted up-and-forward; snout tip at canvas top-left.

    Upward shots spawn 12 px above the standing muzzle (canvas row 11), i.e.
    right at this snout tip. The neck starts lower, the feet stay at row 47.
    """
    head = shear_up(resize_x(source_head(rom, 'open'), width))
    canvas = [['0']*width for _ in range(48)]
    top = len(head) - 4
    for y in range(top, 48):
        sway = (0, -1, 0, 1)[((y-top)//8) % 4]
        _blit(canvas, [neck[(y-top) % 16]], width-neck_width+sway, y)
    _blit(canvas, head, 0, 0)
    return [''.join(row) for row in canvas]


def make_frames(rom: bytes, width: int = 24) -> dict[str, list[str]]:
    """Return named pixel-row frames in a 16x48 or 24x48 LEFT-facing canvas.

    Standing muzzle: visual row 11 (origin near x0). Crouched muzzle: row 35.
    Head is assembled from real boss tiles and resampled only horizontally.
    The narrow continuous body uses the native A0/A2 neck strip throughout.
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
        head_y = 24 if crouch else 0
        # Alternating offsets provide a restrained source-like neck undulation.
        neck_x = width-neck_width
        for y in range(head_y+14, 48):
            sway = (0, -1, 0, 1)[((y-head_y)//8+phase)%4]
            row = neck[max(0, y-head_y-16)%16]
            _blit(canvas, [row], neck_x+sway, y)
        # Keep the encounter's narrow segmented silhouette all the way to the
        # feet. No added coil or wider belly, including during the jump pose.
        # Draw the native jaw over the neck so its open-mouth silhouette stays
        # intact. Crouching leaves eight pixels of native neck below the jaw,
        # retaining the narrow serpentine body rather than a detached head.
        _blit(canvas, head, 0, head_y)
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
        ('hurt','half',1,False,True),
        ('item','closed',0,False,False),
    ]}
    # Down turns the native head instead of inventing a different face.
    head = source_head(rom, 'open')
    turned = [''.join(head[15-x][y] for x in range(16)) for y in range(32)]
    down = [row[::-1] for row in turned[::-1]]
    for name, rows, y in [('down', down, 16)]:
        canvas = [['0']*width for _ in range(48)]
        base = frames['idle']
        for at in (range(32,48) if name=='up' else range(0,16)):
            source_y = at if name=='up' else at+16
            canvas[at] = list(base[source_y])
        _blit(canvas, rows, (width-16)//2, y)
        frames[name] = [''.join(row) for row in canvas]
    frames['up'] = looking_up(rom, width, neck, neck_width)
    frames['death'] = ['0'*width]*16 + frames['crouch'][16:]
    # Compact 32px fallback for the original renderer's item/Dark Link paths.
    frames['tuck'] = ['0'*width]*16 + frames['idle'][:16] + frames['idle'][32:]
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
        'muzzle_rows':{'standing':11,'crouched':35,'tucked':27},
        'note':'Recipe-only source; pixels and previews are generated from the user ROM.'
    },indent=2)+'\n')
    return output


def compile_lava_link(rom: bytes) -> dict[int, bytes]:
    """Build Palace 6 'Lava Link' CHR bank 25 pairs from original Link bank 2 pixels."""
    # Original hand-drawn 16x16 Link heads, facing left (producer-approved 2026-11-14).
    # The game draws only the left 16x16 of each head state (first two pairs); the
    # right pairs feed the top neck piece, so they carry the neck strip.
    # Indices: 1 = $18 olive outline/hair, 2 = $36 skin, 3 = $2A green cap/tunic.
    head_top = [
        '......33333.....',
        '....333333333...',
        '...33333333333..',
        '..1333333333333.',
        '..1111111113333.',
        '..1222221122.333',
        '.12212221122..33',
        '.122222212.....3',
        '1222222212......',
    ]
    head_bottom = {
        # closed: calm profile with a chin line
        0: ['.122222221......', '..12222122......', '..1222222.......', '...11111........'],
        # half: small open mouth
        2: ['.122222221......', '..11222122......', '..1222222.......', '...11111........'],
        # open: round shout, not a dropped jaw
        4: ['.122222221......', '..11222122......', '..11222222......', '...11111........'],
    }
    # The collar sweeps back to the right edge, where the top neck piece starts 14 px over.
    collar = ['...3333333331...', '..3333333333331.', '.33333333333333.']

    def make_head(mouth_open: int) -> list[str]:
        return [row.replace('.', '0') for row in head_top + head_bottom[mouth_open] + collar]

    # Clean green tunic + brown belt column (16x16) using Link's tunic palette (1=brown, 2=gold/skin, 3=green).
    # Derived from Link's tunic color indices in bank 2 pairs 0x00/0x02.
    neck_rows = []
    for y in range(16):
        if y == 15:
            row = '00' + '1' * 12 + '00'
        elif y in (13, 14):
            row = '0013332222333100'
        else:
            row = '0013331333333100' if y % 4 == 0 else '0013333333333100'
        neck_rows.append(row)

    def pairs_from_rows(rows: list[str]) -> list[bytes]:
        return [
            encode_tile([r[x:x+8] for r in rows[:8]]) + encode_tile([r[x:x+8] for r in rows[8:16]])
            for x in range(0, len(rows[0]), 8)
        ]

    pairs: dict[int, bytes] = {}
    for state, mouth_open in (('closed', 0), ('half', 2), ('open', 4)):
        tile_ids = HEAD_PAIRS[state]
        compiled = pairs_from_rows([h + n for h, n in zip(make_head(mouth_open), neck_rows)])
        for tile_id, pair_bytes in zip(tile_ids, compiled):
            pairs[tile_id] = pair_bytes

    neck_compiled = pairs_from_rows(neck_rows)
    pairs[0xA0] = neck_compiled[0]
    pairs[0xA2] = neck_compiled[1]

    # Copy Link's horizontal sword beam (bank 2 pair 0x32) to bank 25 pair 0x52.
    sword_off = CHR_OFFSET + 2 * 4096 + 0x32 * 16
    pairs[0x52] = rom[sword_off:sword_off + 32]
    return pairs


if __name__ == '__main__':
    print(make_study())
