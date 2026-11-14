"""Compile editable pixel rows into native NES tiles and player metasprites."""
from __future__ import annotations
import json
import re
from pathlib import Path
from nes import CHR_OFFSET, decode_tile, encode_tile, load_source, write_png
from boss_art import make_frames

COLORS = [(20, 22, 28), (194, 43, 25), (255, 168, 57), (255, 243, 205)]
TALL_POSES = ('walk0', 'walk1', 'walk2', 'idle', 'windup', 'attack',
              'crouch', 'crouch-attack', 'up', 'down', 'hurt', 'death', 'jump')
ASH_TILES = (0x64, 0x66)


def compile_ash(root: Path) -> tuple[dict[int, bytes], list[str]]:
    """Compile authored ash independently of the private source ROM.

    The caller chooses the native charcoal/ember sprite palette. Place both 8x16 sprites at
    NPC Y+24: the eight visible rows then sit at the original NPC's feet.
    """
    rows = json.loads((root / 'assets/ash.json').read_text())['rows']
    if len(rows) != 8 or any(len(row) != 16 or set(row)-set('0123') for row in rows):
        raise ValueError('Ash art requires eight 16-pixel rows using indexes 0..3')
    # Keep fixed IDs in a ROM-free include so the town renderer can assemble
    # without copying or extracting any game pixels.
    include = (root / 'src/ash_layout.inc').read_text()
    for name, tile in zip(('AshTileLeft', 'AshTileRight'), ASH_TILES):
        if not re.search(rf'^{name}\s*=\s*\${tile:02X}\s*$', include, re.MULTILINE):
            raise ValueError(f'Ash layout {name} does not match allocated tile ${tile:02X}')
    return dict(zip(ASH_TILES, sprite_pairs(rows+['0'*16]*8))), rows


SHOUT_FONT_BANK = 7          # town BG pattern table (4K CHR bank)
SHOUT_GLYPH_BANK = 7         # odd sprite tiles read the same $1000 table
SHOUT_FONT_A = 0xDA          # native font: 'A'..'Z' are consecutive tiles
# Truncated SHA-256 of each original 32-byte pair replaced in bank 7. These
# decorative pairs appeared in no town room ($00..$3E) nametable census.
SHOUT_PAIR_SHA256 = {
    0x80: '893a0325cdc7cf39', 0x82: '42de53a38d178b20', 0x84: 'af85fa03d8808ac1',
    0x86: '3e0dffed3d26d014', 0x88: '55dc69973efa250d', 0x8A: '431ab247f511fe1d',
    0x8C: 'c644321081be6393', 0x92: 'cab870c820270963', 0x94: '13ea6b95d58a4960',
    0x9C: '8d5f82fc987a6193', 0x9E: 'f9523c2896786a4b', 0xA0: '56c8c7c281e4177f',
}


def compile_shout_glyphs(root: Path, source: bytes) -> dict[int, bytes]:
    """Build 8x16 shout-word glyph pairs from the user's own ROM font.

    Returns {even pair index: 32 bytes} for town CHR bank 7 only. Letters
    are recolored from the BG font at build time, so no ROM pixels are
    committed. Each glyph sits in the lower tile; the upper tile is blank
    apart from the outline row above the letter.
    """
    spec = json.loads((root / 'assets/shout_glyphs.json').read_text())
    letter, outline = str(spec['letter_index']), str(spec['outline_index'])
    include = (root / 'src/shout_layout.inc').read_text()
    tiles = {m.group(1): int(m.group(2), 16) for m in
             re.finditer(r'^ShoutTile_(\w+)\s*=\s*\$([0-9A-F]{2})\s*$', include, re.MULTILINE)}
    names = {'Bang': '!'}
    result: dict[int, bytes] = {}
    for name, tile in tiles.items():
        char = names.get(name, name)
        if not tile % 2:
            raise ValueError(f'Shout glyph {char} must be an odd ($1000 table) 8x16 tile')
        if char in spec['authored']:
            rows = [row.replace('.', '0') for row in spec['authored'][char]]
        elif len(char) == 1 and 'A' <= char <= 'Z':
            offset = CHR_OFFSET + SHOUT_FONT_BANK*4096 + (SHOUT_FONT_A+ord(char)-ord('A'))*16
            rows = [''.join(str(v) for v in row) for row in decode_tile(source[offset:offset+16])]
        else:
            raise ValueError(f'No shout glyph source for {char!r}')
        if len(rows) != 8 or any(len(row) != 8 or set(row)-set('012') for row in rows):
            raise ValueError(f'Shout glyph {char!r} must be 8x8 using 0..2')
        canvas = [['0']*8 for _ in range(8)] + [list(row) for row in rows]
        body = {(y, x) for y in range(16) for x in range(8) if canvas[y][x] == '1'}
        out = [['0']*8 for _ in range(16)]
        for y in range(16):
            for x in range(8):
                if (y, x) in body:
                    out[y][x] = letter
                elif canvas[y][x] == '2' or any((y+dy, x+dx) in body
                        for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                    out[y][x] = outline
        if tile & 0xFE in result:
            raise ValueError(f'Shout glyph {char} reuses an allocated pair')
        result[tile & 0xFE] = sprite_pairs([''.join(row) for row in out])[0]
    return result


def validate_layout(root: Path) -> bytes:
    """Validate the distributable index recipe without loading original CHR."""
    text = (root / 'src/tall_layout.inc').read_text()
    rows = re.findall(r'^\s*\.byte\s+([^;\n]+);\s*(\S+)\s*$', text, re.MULTILINE)
    if [name for _, name in rows] != list(TALL_POSES):
        raise ValueError('Tall layout must contain the ordered player poses')
    layout = bytearray()
    for values, name in rows:
        tokens = [token.strip() for token in values.split(',')]
        if len(tokens) != 9 or any(not re.fullmatch(r'\$[0-9A-F]{2}', token) for token in tokens):
            raise ValueError(f'Tall layout {name} requires nine byte indexes')
        tiles = [int(token[1:], 16) for token in tokens]
        if any(tile != 0xF5 and (tile % 2 or tile >= 0x64 or tile in {0x32,0x50,0x54}) for tile in tiles):
            raise ValueError(f'Tall layout {name} uses a reserved or invalid body pair')
        if name in ('crouch', 'crouch-attack') and tiles[:3] != [0xF5]*3:
            raise ValueError(f'Tall layout {name} exceeds the compact crouch lane')
        layout.extend(tiles)
    return bytes(layout)


def sprite_pairs(rows: list[str]) -> list[bytes]:
    width = len(rows[0])
    if len(rows) % 16 or width % 8 or any(len(r) != width for r in rows):
        raise ValueError('Metasprites require 8-pixel columns and 16-pixel rows')
    return [b''.join(encode_tile([rows[y+dy][x:x+8] for dy in range(8)])
                     for y in (top, top+8))
            for top in range(0, len(rows), 16) for x in range(0, width, 8)]


def compile_assets(root: Path, source_path: Path | None = None) -> tuple[bytes, dict[int, bytes], bytes, list[list[str]]]:
    art = json.loads((root / 'assets/barba.json').read_text())
    small = art['small']
    for name in ('body', 'small', 'front', 'back'):
        for row in art[name]:
            if len(row) != 16 or set(row) - set('0123'):
                raise ValueError(f'Invalid pixel row in {name}: {row!r}')
    # Original pixels come exclusively from the user's verified local ROM.
    # ROM-free CI can assemble the checked-in layout indexes, but must not call
    # this extraction function: substituting fake art would mask build errors.
    source_path = source_path if source_path is not None else root / 'roms/z2.nes'
    if not source_path.exists():
        raise FileNotFoundError('Boss-derived assets require local roms/z2.nes; '
                                'ROM-free CI should validate src/tall_layout.inc instead')
    named = make_frames(load_source(source_path), 24)
    for name in ('crouch', 'crouch-attack'):
        if any(set(row)-{'0'} for row in named[name][:24]):
            raise ValueError(f'{name} must leave the first 24 canvas rows transparent')
    frames = [named[name] for name in TALL_POSES]
    # Indexed by the vanilla six-sprite record, preserving all nineteen states.
    # Standing fallback packs the native head and narrow body into 32px. Duck
    # poses retain their compact head/neck; both reuse existing tall-frame pairs.
    fallback_names = ('tuck', 'tuck', 'tuck', 'crouch', 'tuck', 'tuck',
                      'crouch-attack', 'crouch', 'crouch-attack', 'up',
                      'tuck', 'tuck', 'tuck', 'tuck', 'down', 'death',
                      'tuck', 'tuck', 'tuck')
    fallback = [named[name][16:] for name in fallback_names]

    # Reserve weapon tiles used by existing renderer immediates and the new tip.
    reserved = {0x32, 0x50, 0x54}
    slots = iter(i for i in range(0, 0x64, 2) if i not in reserved)
    pairs: dict[bytes, int] = {bytes(32): 0xF5}
    graphics: dict[int, bytes] = {}
    def allocate(rows):
        result = bytearray()
        for pair in sprite_pairs(rows):
            if pair not in pairs:
                try:
                    tile = next(slots)
                except StopIteration as exc:
                    raise ValueError('Player graphics exceed the reserved tile budget') from exc
                pairs[pair] = tile
                graphics[tile] = pair
            result.append(pairs[pair])
        return result

    tall_mapping = [allocate(rows) for rows in frames]
    mapping = b''.join(allocate(rows) for rows in fallback)
    # This file contains indexes only, never extracted CHR pixels. Keeping it
    # checked in lets ca65 validate the renderer without redistributing a ROM.
    include = '; Generated by tools/assets.py from the local verified ROM.\n'
    include += '; Nine 8x16 pairs per pose: three rows, left to right.\n'
    include += 'BarbaTallTiles:\n'
    for name, tiles in zip(TALL_POSES, tall_mapping):
        include += '    .byte ' + ', '.join(f'${v:02X}' for v in tiles) + f' ; {name}\n'
    include_path = root / 'src/tall_layout.inc'
    if not include_path.exists() or include_path.read_text() != include:
        include_path.write_text(include, encoding='ascii')

    flame = ['00000000']*3 + [
        '10000000','12100000','12211010','12322121','12333222',
        '12333222','12322121','12211010','12100000','10000000'] + ['00000000']*3
    tip = ['00000000']*3 + [
        '00000000','00000000','01000000','12101000','22212110',
        '22212110','12101000','01000000','00000000','00000000'] + ['00000000']*3
    for tile, rows in ((0x32, flame), (0x54, flame), (0x50, tip)):
        graphics[tile] = sprite_pairs([row[::-1] for row in rows])[0]
    # Fairy's existing 8x16 slot becomes a tiny dragon, preserving flight logic.
    hatchling = [row[::2] for row in small]
    graphics[0x68] = sprite_pairs(hatchling)[0]
    graphics[0x6A] = sprite_pairs(hatchling[1:]+['00000000'])[0]
    ash_graphics, ash_rows = compile_ash(root)
    if graphics.keys() & ash_graphics.keys():
        raise ValueError('Ash sprites overlap another graphics allocation')
    graphics.update(ash_graphics)

    ow = bytearray()
    for rows in (small, [r[::-1] for r in small], art['front'], art['back']):
        for step in (0, 1):
            animated = rows if step == 0 else ['0'*16] + rows[:-1]
            ow.extend(b''.join(sprite_pairs(animated)))

    # Local-only preview contains the extracted boss face and native texture.
    preview_rows = []
    for top in range(0, len(frames), 5):
        for y in range(48):
            row = []
            for frame in frames[top:top+5]:
                row += [COLORS[int(v)] for v in frame[y]] + [(40, 44, 52)]*4
            preview_rows.append(row + [COLORS[0]] * (140-len(row)))
        preview_rows += [[COLORS[0]]*140 for _ in range(4)]
    write_png(root / 'build/barba-sprites.png', preview_rows, 4)
    ash_colors = [(20,22,28), (55,55,55), (112,112,112), (182,182,182)]
    write_png(root / 'build/ash-sprite.png',
              [[ash_colors[int(pixel)] for pixel in row] for row in ash_rows], 12)
    (root / 'build/barba-assets.json').write_text(json.dumps({
        'poses': list(TALL_POSES), 'size': [24, 48],
        'body_pairs': len(pairs)-1, 'available_body_pairs': 47,
        'weapon_pairs': [0x32, 0x50, 0x54], 'wyrmling_pairs': [0x68, 0x6A],
        'ash_pairs': list(ASH_TILES), 'ash_visible_size': [16,8],
        'ash_sprite_npc_y_offset': 24,
        'mapping': [list(row) for row in tall_mapping],
        'fallback_mapping_bytes': len(mapping),
        'muzzle_left_canvas': {'standing': [0,11], 'crouched': [0,35],
                               'tucked': [0,27]},
        'muzzle_left_actor': {'standing': [0,-5], 'crouched': [0,19],
                              'tucked': [0,11]},
        'note': 'Actor-relative y assumes canvas starts actorY-16; right-facing x mirrors at 23.'
    }, indent=2)+'\n')
    return bytes(mapping), graphics, bytes(ow), frames
