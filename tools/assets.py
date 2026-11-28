"""Compile editable pixel rows into native NES tiles and player metasprites."""
from __future__ import annotations
import json
import math
import re
from pathlib import Path
from nes import CHR_OFFSET, decode_tile, encode_tile, load_source, write_png
from boss_art import make_frames, resize_x

COLORS = [(20, 22, 28), (194, 43, 25), (255, 168, 57), (255, 243, 205)]
TALL_POSES = ('walk0', 'walk1', 'walk2', 'idle', 'windup', 'attack',
              'crouch', 'crouch-attack', 'up', 'down', 'hurt', 'death', 'jump')
ASH_TILES = (0x7E, 0x80)
# Player-bank pairs the tall renderer must never allocate: Myu crawl frame (0x24,
# mirrored by the bank-7 sprite table at $EE7B), candle (0x52), corridor bend
# (0x32, 0x54, formerly the hidden horizontal slash sprites),
# Ache/bat enemy (0x4E, 0x50), ending ash (0x5E, 0x62, patched in build.py),
# and the XP "3" score digit (0x60, drawn by the bank-7 score table at $DD4C).
PLAYER_RESERVED_PAIRS = frozenset({0x24, 0x32, 0x4E, 0x50, 0x52, 0x54, 0x5E, 0x60, 0x62})
# Sparse pose columns can share the idle seam with small pixel differences.
# Keep the original allocator order so tiles referenced directly stay stable.
ENCOUNTER_TRAIL_PAIRS = (0x14, 0x3E, 0x44, 0x30)
ENCOUNTER_CONNECTOR_PAIRS = (0x34, 0x36)
CROUCH_BEND_PAIRS = (0x32, 0x54)
ENCOUNTER_SEAM_PAIR = 0x0A
FALL_TIP_PAIR = ENCOUNTER_SEAM_PAIR
# The far tip column borrows the crouch-attack neck pair, which differs from
# the crouch/death neck $22 by 16 pixels in a brief pose.
ENCOUNTER_TIP_ALIAS = (0x30, 0x22, 16)
# Flick-up tip, 16px wide: (top, bottom) rows per column. The near column
# overlaps the turned torso's end (rows 2-11) so the delayed Y never opens a gap.
ENCOUNTER_TIP_PROFILE = ((1, 13), (2, 13), (3, 13), (3, 12), (4, 12), (4, 11), (5, 11), (5, 10),
                         (5, 10), (5, 9), (5, 9), (5, 8), (4, 7), (4, 6), (3, 5), (2, 3))
ENCOUNTER_TIP_SPINE_EVERY = 3
# Elbow corner: the upright torso swept a quarter turn around a pivot just
# outside the top-right corner (x, y, outer radius). Spines thin on the inner arc.
ENCOUNTER_ELBOW = (17.5, -1.0, 17.0)


# Two poses of the ending projectile, facing right. Index 0 is transparent.
# The warm palette progresses from red (1) to orange (2) to white (3).
ENDING_FIRE_FRAMES = (
    (
        "0000000001100000",
        "0000000011221000",
        "0011000112232100",
        "0001111122333210",
        "0111222223333321",
        "1111122223333321",
        "0001122222333210",
        "0011101112222100",
        "0000000011111000",
    ),
    (
        "0000000001110000",
        "0000000011221000",
        "0000011112232100",
        "1100111122333210",
        "0111122223333321",
        "0012222223333321",
        "0111112222333210",
        "1100011112222100",
        "0000000011111000",
    ),
)


def compile_ending_fire() -> bytes:
    """Pack tail A/B then head A/B, matching the ending renderer."""
    first, second = (
        sprite_pairs(['0' * 16] * 2 + list(frame) + ['0' * 16] * 5)
        for frame in ENDING_FIRE_FRAMES
    )
    return b''.join((first[0], second[0], first[1], second[1]))


SOULS_FONT = {
    'A': ('00000000', '00000000', '00111000', '01101100', '11000110', '11111110', '11000110', '11000110'),
    'B': ('00000000', '00000000', '11111100', '11000110', '11111100', '11000110', '11000110', '11111100'),
    'C': ('00000000', '00000000', '01111100', '11000110', '11000000', '11000000', '11000110', '01111100'),
    'D': ('00000000', '00000000', '11111000', '11001100', '11000110', '11000110', '11001100', '11111000'),
    'E': ('00000000', '00000000', '11111110', '11000000', '11111100', '11000000', '11000000', '11111110'),
    'G': ('00000000', '00000000', '01111100', '11000000', '11001110', '11000110', '11000110', '01111110'),
    'H': ('00000000', '00000000', '11000110', '11000110', '11111110', '11000110', '11000110', '11000110'),
    'I': ('00000000', '00000000', '01111100', '00111000', '00111000', '00111000', '00111000', '01111100'),
    'K': ('00000000', '00000000', '11000110', '11001100', '11110000', '11011000', '11001100', '11000110'),
    'L': ('00000000', '00000000', '11000000', '11000000', '11000000', '11000000', '11000000', '11111110'),
    'M': ('00000000', '00000000', '11000110', '11101110', '11111110', '11010110', '11000110', '11000110'),
    'N': ('00000000', '00000000', '11000110', '11100110', '11110110', '11011110', '11001110', '11000110'),
    'O': ('00000000', '00000000', '01111100', '11000110', '11000110', '11000110', '11000110', '01111100'),
    'R': ('00000000', '00000000', '11111100', '11000110', '11111100', '11011000', '11001100', '11000110'),
    'S': ('00000000', '00000000', '01111100', '11000000', '01111100', '00000110', '11000110', '01111100'),
    'T': ('00000000', '00000000', '11111110', '00111000', '00111000', '00111000', '00111000', '00111000'),
    'U': ('00000000', '00000000', '11000110', '11000110', '11000110', '11000110', '11000110', '01111100'),
}

SOULS_FONT_EXTRA = {
    ',': ('00000000', '00000000', '00000000', '00000000', '00000000', '00110000', '00110000', '01100000'),
    'F': ('00000000', '00000000', '11111110', '11000000', '11111100', '11000000', '11000000', '11000000'),
    'P': ('00000000', '00000000', '11111100', '11000110', '11111100', '11000000', '11000000', '11000000'),
    'Q': ('00000000', '00000000', '01111100', '11000110', '11000110', '11010110', '11001100', '01110110'),
    'W': ('00000000', '00000000', '11000110', '11000110', '11010110', '11111110', '11101110', '11000110'),
    'X': ('00000000', '00000000', '11000110', '01101100', '00111000', '00111000', '01101100', '11000110'),
    'Y': ('00000000', '00000000', '11000110', '01101100', '00111000', '00111000', '00111000', '00111000'),
    'Z': ('00000000', '00000000', '11111110', '00001100', '00011000', '00110000', '01100000', '11111110'),
}


def compile_souls_bar_chr() -> bytes:
    """Build 2 KB CHR bank (banks 156-157) for the Dark Souls-style bottom boss bar."""
    chr_data = bytearray(2048)
    # $00: blank tile (all 0)
    # $01..$11: boss name uppercase letters in palette color 1 (white)
    for idx, ch in enumerate(sorted(SOULS_FONT), start=1):
        chr_data[idx * 16:(idx + 1) * 16] = encode_tile(SOULS_FONT[ch])
    # $23..$2A: extended boss title glyphs (comma + F, P, Q, W, X, Y, Z)
    for idx, ch in enumerate(sorted(SOULS_FONT_EXTRA), start=0x23):
        chr_data[idx * 16:(idx + 1) * 16] = encode_tile(SOULS_FONT_EXTRA[ch])
    # $12: left endcap, $13: right endcap (ornate diamond tip + vertical frame)
    left_cap = (
        '00000200',
        '00002122',
        '00021200',
        '00212000',
        '00212000',
        '00021200',
        '00002122',
        '00000200',
    )
    right_cap = tuple(row[::-1] for row in left_cap)
    chr_data[0x12 * 16:0x13 * 16] = encode_tile(left_cap)
    chr_data[0x13 * 16:0x14 * 16] = encode_tile(right_cap)
    # $14..$22: 15 inner bar tiles covering all (red_2px, white_2px) pairs in 0..4
    tile_idx = 0x14
    for r in range(5):
        for w in range(5 - r):
            e = 4 - r - w
            body = ('3' * (r * 2)) + ('1' * (w * 2)) + ('0' * (e * 2))
            rows = (
                '00000000',
                '22222222',
                body,
                body,
                body,
                body,
                '22222222',
                '00000000',
            )
            chr_data[tile_idx * 16:(tile_idx + 1) * 16] = encode_tile(rows)
            tile_idx += 1
    return bytes(chr_data)


def _pair_pixel_diff(a: bytes, b: bytes) -> int:
    """Count differing pixels between two 32-byte 8x16 sprite pairs."""
    return sum(bin((a[t+y] ^ b[t+y]) | (a[t+y+8] ^ b[t+y+8])).count('1')
               for t in (0, 16) for y in range(8))


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
SHOUT_SPRITE_BANK = 6        # even sprite tiles read the town sprite table ($0000)
SHOUT_FONT_0 = 0xD0          # native font: '0'..'9' are consecutive tiles
SHOUT_FONT_A = 0xDA          # native font: 'A'..'Z' are consecutive tiles
# Truncated SHA-256 of each original 32-byte pair replaced, keyed (CHR bank, pair).
# An 8x16 tile byte T draws BOTH tiles T&$FE and T|1, so a pair is free only if
# neither tile is town BG (bank-3 metatile tables + 126-room nametable census),
# no town sprite byte selects it (bank-3 townfolk table: $01-$27 odd in bank 7,
# $C0-$CE/$62/$64/$74/$76 even in bank 6; items; emulator census of all town
# rooms), and no menu/HUD pane draws it. Bank 7 $00-$27 are villager sprites.
SHOUT_PAIR_SHA256 = {
    (7, 0x7E): '8f729ebb615dc165',
    (7, 0x80): '893a0325cdc7cf39', (7, 0x84): 'af85fa03d8808ac1',
    (7, 0x86): '3e0dffed3d26d014', (7, 0x88): '55dc69973efa250d', (7, 0x8A): '431ab247f511fe1d',
    (7, 0x8C): 'c644321081be6393', (7, 0x92): 'cab870c820270963', (7, 0x94): '13ea6b95d58a4960',
    (7, 0x9C): '8d5f82fc987a6193', (7, 0x9E): 'f9523c2896786a4b',
    (7, 0xA0): '56c8c7c281e4177f', (7, 0xA2): '904a335528773b88', (7, 0xA8): '8a67b0ac638f1721',
    (7, 0xAA): '28d9e3968e5dce9e',
    (7, 0xBA): '77125f6e91a0dc9e', (7, 0xBC): '14f9bfc9ad98c854', (7, 0xBE): '5155a7a4143a9e04',
    # Combo counter X/1-9, BA, and H: unused Link-only / palace pairs of town sprite bank 6.
    (6, 0x66): 'beda0a359f94a46e', (6, 0xB2): 'd9a52e50afa1aff0', (6, 0xB4): '9e9f47dbebac4537',
    (6, 0x78): '3054cb3b20613bbd', (6, 0x7A): 'd5aa306916f80c94', (6, 0x7C): 'dd16785f9de0c5fe',
    (6, 0x94): 'a19816f6150159eb', (6, 0x96): 'c4a1e8d2f73af810', (6, 0x98): 'ad60a4ced100a384',
    (6, 0xAA): '75da72438cdf4244', (6, 0xAC): 'e0526bda20a145b0', (6, 0xAE): 'be16549eb5b081fb',
    (6, 0xB6): '203f10a2f9e335b4',
}
# Town sprite pairs that must stay vanilla (checked after every build).
TOWN_SPRITE_PAIRS = {
    7: tuple(range(0x00, 0x28, 2)) + (0x2E, 0x30, 0x64, 0x66, 0x74, 0x76, 0x7A, 0xC4, 0xF4, 0xFE),
    6: (0x60, 0x62, 0x64, 0x6C, 0x6E, 0x70, 0x74, 0x76, 0x9C, 0x9E, 0xA0, 0xA2, 0xA4, 0xA6,
        0xC0, 0xC2, 0xC4, 0xC6, 0xC8, 0xCA, 0xCC, 0xCE),
}


def _render_shout_pair(char: str, spec: dict, source: bytes) -> bytes:
    """Render one 8x16 shout glyph pair from authored art or the ROM font."""
    letter, outline = str(spec['letter_index']), str(spec['outline_index'])
    if char in spec['authored']:
        rows = [row.replace('.', '0') for row in spec['authored'][char]]
    elif len(char) == 1 and 'A' <= char <= 'Z':
        offset = CHR_OFFSET + SHOUT_FONT_BANK*4096 + (SHOUT_FONT_A+ord(char)-ord('A'))*16
        rows = [''.join(str(v) for v in row) for row in decode_tile(source[offset:offset+16])]
    elif len(char) == 1 and '0' <= char <= '9':
        offset = CHR_OFFSET + SHOUT_FONT_BANK*4096 + (SHOUT_FONT_0+ord(char)-ord('0'))*16
        rows = [''.join(str(v) for v in row) for row in decode_tile(source[offset:offset+16])]
    else:
        raise ValueError(f'No shout glyph source for {char!r}')
    if len(rows) != 8 or any(len(row) != 8 or set(row)-set('012') for row in rows):
        raise ValueError(f'Shout glyph {char!r} must be 8x8 using 0..2')
    authored = char in spec['authored']
    if not authored and any(row[0] == '1' for row in rows):
        drop = 4 if char in ('N', 'K') else 3
        rows = ['0' + row[:drop] + row[drop+1:7] + '0' for row in rows]
    canvas = [['0']*8 for _ in range(8)] + [list(row) for row in rows]
    body = {(y, x) for y in range(16) for x in range(8) if canvas[y][x] == '1'}
    out = [['0']*8 for _ in range(16)]
    for y in range(16):
        for x in range(8):
            if (y, x) in body:
                out[y][x] = letter
            elif (authored and canvas[y][x] == '2') or any((y+dy, x+dx) in body
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                out[y][x] = outline
    return sprite_pairs([''.join(row) for row in out])[0]


def compile_shout_glyphs(root: Path, source: bytes) -> dict[tuple[int, int], bytes]:
    """Build 8x16 shout-word glyph pairs from the user's own ROM font.

    Returns {(CHR bank, even pair index): 32 bytes}. Odd tile bytes select
    town BG bank 7 ($1000); even bytes select town sprite bank 6 ($0000).
    Letters are recolored from the BG font at build time, so no ROM pixels
    are committed. Each glyph sits in the lower tile; the upper tile is blank
    apart from the outline row above the letter.
    """
    spec = json.loads((root / 'assets/shout_glyphs.json').read_text())
    include = (root / 'src/shout_layout.inc').read_text()
    tiles = {m.group(1): int(m.group(2), 16) for m in
             re.finditer(r'^ShoutTile_(\w+)\s*=\s*\$([0-9A-F]{2})\s*$', include, re.MULTILINE)}
    names = {'Bang': '!'}
    result: dict[tuple[int, int], bytes] = {}
    for name, tile in tiles.items():
        char = names.get(name, name)
        key = (SHOUT_GLYPH_BANK if tile % 2 else SHOUT_SPRITE_BANK, tile & 0xFE)
        if key in result:
            raise ValueError(f'Shout glyph {char} reuses an allocated pair')
        result[key] = _render_shout_pair(char, spec, source)
    return result


CASTLE_SHOUT_BANK = 3        # North Palace BG/odd-sprite pattern table (4K CHR bank)
CASTLE_SHOUT_TILES = {
    'O': 0x5F, 'P': 0x61, 'S': 0x63, '...': 0x65,
}
# All 4 pairs are 32 zero bytes in original CHR bank 3.
CASTLE_SHOUT_PAIR_SHA256 = {tile & 0xFE: '66687aadf862bd77' for tile in CASTLE_SHOUT_TILES.values()}


def compile_castle_shout_glyphs(root: Path, source: bytes) -> dict[int, bytes]:
    """Build 8x16 shout-word glyph pairs for Barba in North Palace (CHR bank 3)."""
    spec = json.loads((root / 'assets/shout_glyphs.json').read_text())
    return {tile & 0xFE: _render_shout_pair(char, spec, source)
            for char, tile in CASTLE_SHOUT_TILES.items()}


TITLE_CHR_BANK = 1  # title screen BG pattern table ($1000 when $76E == 0)
TITLE_LAVA_TILES = (0x68, 0x69, 0x6A)
TITLE_FOREST_EDGE_TILES = (0x6D, 0x6E, 0x6F, 0x70)


def compile_title_shore(tile: int, forest: bytes, lava: bytes) -> bytes:
    """Composite lava through the original forest's index-3 water mask."""
    # This corner tile's only foliage is a detached two-pixel fleck.
    if tile == 0x70:
        forest = b'\xff' * 16
    # Palette 1 has black (0), gold (1), green (2), red (3). Map open-lava
    # dark red (1), red (2), and gold (3) to black (0), red (3), and gold (1).
    lava_colors = (0, 0, 3, 1)
    return encode_tile([
        ''.join(str(lava_colors[liquid] if tree == 3 else tree & 2)
                for tree, liquid in zip(forest_row, lava_row))
        for forest_row, lava_row in zip(decode_tile(forest), decode_tile(lava))
    ])


# Truncated SHA-256 of each original 16-byte tile in bank 1 used exclusively by
# the "LINK" title logo (never shared with "ZELDA II", "THE ADVENTURE OF",
# "TM", story scroll, or borders).
TITLE_TILE_SHA256 = {
    0x08: '371d8e9cb6316f58', 0x09: '649f2a5ed69da97f', 0x0A: '9147ab7e42b250c0',
    0x0B: '5a76765c34612834', 0x0C: '1c9a6a270eba5569', 0x0D: 'f165b2d2b496f400',
    0x0F: '374708fff7719dd5', 0x10: 'cbba06729da534a0', 0x11: '0170b5093715d9cd',
    0x12: 'f1a32dd9bb342605', 0x13: '6c7e98a360cd532e', 0x14: '55c9dc053ef77941',
    0x15: '8b49c028ac739f64', 0x16: '4b2d82926df1f59a', 0x17: 'e2b9a8d07bfb190f',
    0x1A: 'c855540fd4119033', 0x3E: 'c188f501b4bc9a90', 0x3F: '87669a249efd631f',
    0x40: 'd96ae899ea88facf', 0x41: '4a5d0546e52ffa90', 0x42: '6b75fb316aa357ee',
    0x43: '26991008efdd2d01', 0x44: '465acaaf337dbda6', 0x45: 'd0906abed0c87110',
    0x46: 'b1c5cf63ba57631b', 0x47: '17d014410caf8ff3', 0x48: '83ef6c626299ec5f',
    0x49: '17d014410caf8ff3', 0x4A: 'd60973e30109d200', 0x4B: 'd3b51386a6cdb886',
    0x4C: '6982dfc1ca77282c', 0x4D: 'd68abbfd56da3c2c', 0x4E: '9922d2ab646c67c5',
    0x4F: 'd8b85654ced2070a', 0x50: '9d51b3afcd4cf2df', 0x51: 'd96ae899ea88facf',
    0x52: 'e355c8e54e1c8dcb', 0x53: 'fdd06dd77479f928', 0x54: '38d18df06d4558c9',
    0x55: '542636ae4cd933db', 0x56: '322bad65b84d2b0e', 0x57: '827ad5631666685d',
    0x58: 'd96ae899ea88facf', 0x59: '2b0dc49f17947974', 0x5A: '2e0b9451211d638e',
    0x5B: '0c0e107614ca4e36', 0x5C: 'ac4c7e69ac53603c', 0x5D: 'd94cb0fab02f37d5',
    0x5E: '87c4471416b07ebe', 0x5F: '3fae0548ede339dd', 0x60: 'c967a2d4e2771a7c',
    0x61: '4fa5ae7205e2b4c2', 0x62: 'c816db8e032adad3', 0x63: 'b213fd6c9dcd3e46',
    0x64: '845e4b27693c9b88', 0x65: 'aa4240846448d732', 0x66: '02a41544a51738a6',
    0x67: 'c1c6f8ea72091c8c',
}


TOWN_FIRE_BANK = 7           # town BG pattern table (both west and east towns map CHR 6/7)
# Truncated SHA-256 of each original 16-byte tile replaced in bank 7. None of these
# tiles is in any bank-3 town tile table or 126-room nametable census, none is
# half of a town sprite pair (bank 7 $00-$27 are villager 8x16 sprites), and none
# is drawn by the native pause/spell menu. Flame and char share their lower half
# ($A7/$C2), so six tiles cover both stages. $34 is the vanilla dialogue '?' and must
# stay vanilla; $35 (blank in vanilla) is the dialogue apostrophe (TEXT_GLYPHS).
TOWN_FIRE_TILE_SHA256 = {
    0xA4: '9cdf7aff56268b1c', 0xAC: 'a80338b3fc699cff',
    0xC0: '1cecb0d1030f7c54', 0xC1: 'ebe7bc86960b8544',
    0xA7: '899cbd256813b89a', 0xC2: 'e43c2b7f9db2ff96',
}

# Dialogue glyphs added to the town BG bank. The native text engine draws a byte
# below $40 as tile = byte (with blank $F4 above), so these must sit in $00-$3F or
# $C0-$FC. Pixel values: 1 = font highlight, 2 = font shade (as in the ROM font).
TEXT_GLYPH_BANK = 7
TEXT_GLYPHS = {
    0x33: ["00000000", "00000000", "00000000", "00000000",
           "00000000", "00112000", "00112000", "01120000"],   # comma (vanilla Z2 2bpp)
    0x35: ["00012000", "00012000", "00020000", "00000000",
           "00000000", "00000000", "00000000", "00000000"],   # apostrophe
}
TEXT_GLYPH_SHA256 = {
    0x33: '374708fff7719dd5',   # blank in vanilla bank 7
    0x35: '374708fff7719dd5',   # blank in vanilla bank 7
}


# Level-up pane / File Select attack icon: BG tile $C9 (vanilla sword) in every
# odd side-view BG bank $01-$19, redrawn as an original fireball. The level-up
# pane draws it once per attack level (bank 0 $9E23); File Select draws it
# beside each save's levels (bank 5 $BC4E). The status bar never uses it.
# Pixel values: 1 = white core, 2 = font shade, 3 = red (heart colour).
BREATH_ICON_TILE = 0xC9
BREATH_ICON_BANKS = tuple(range(1, 26, 2))
BREATH_ICON_SHA256 = '1dd9fbe8bb7dd961'   # vanilla sword, identical in all 13 banks
BREATH_ICON = ["00300030",   # flame-crowned fireball (picked 2026-11-16)
               "03303330",
               "03313130",
               "33111133",
               "31111113",
               "31111113",
               "03111130",
               "00333300"]


def compile_breath_icon() -> bytes:
    """Encode the level-up BREATH fireball icon (original pixels)."""
    return encode_tile(BREATH_ICON)


def compile_text_glyphs() -> dict[int, bytes]:
    """Encode authored dialogue glyphs (original pixels) for TEXT_GLYPH_BANK."""
    if set(TEXT_GLYPHS) != set(TEXT_GLYPH_SHA256) or set(TEXT_GLYPHS) & set(TOWN_FIRE_TILE_SHA256):
        raise ValueError('Text glyph tiles differ from the audited allocation')
    return {tile: encode_tile(rows) for tile, rows in TEXT_GLYPHS.items()}


def _encode_scorch_art(spec: dict, tile_map: dict[str, dict[str, int]]) -> tuple[dict[int, bytes], list[int]]:
    """Encode 16x16 flame and char art into 8 BG tiles using tile_map."""
    digits = {'.': '0', 'o': '1', '+': '2', '#': '3'}
    order = []
    tiles: dict[int, bytes] = {}
    for stage in ('flame', 'char'):
        rows = spec[stage]
        if len(rows) != 16 or any(len(row) != 16 or set(row) - set(digits) for row in rows):
            raise ValueError(f'Town fire {stage} must be 16 rows of 16 of . o + #')
        rows = [''.join(digits[c] for c in row) for row in rows]
        ids = tile_map[stage]
        for corner, (y, x) in (('tl', (0, 0)), ('bl', (8, 0)), ('tr', (0, 8)), ('br', (8, 8))):
            tile = ids[corner]
            data = encode_tile([row[x:x+8] for row in rows[y:y+8]])
            if tiles.get(tile, data) != data:
                raise ValueError(f'Scorch tile {tile:02X} is shared by quadrants with different art')
            tiles[tile] = data
            order.append(tile)
    return tiles, order


def compile_town_fire(root: Path) -> dict[int, bytes]:
    """Compile the authored 16x16 flame and char art into eight town BG tiles."""
    spec = json.loads((root / 'assets/town_fire.json').read_text())
    tile_map = {stage: {k: int(v, 16) for k, v in spec['tiles'][stage].items()}
                for stage in ('flame', 'char')}
    tiles, order = _encode_scorch_art(spec, tile_map)
    if set(tiles) != set(TOWN_FIRE_TILE_SHA256):
        raise ValueError('Town fire tiles differ from the audited allocation')
    text = (root / 'src/blocks.inc').read_text()
    table = re.search(r'^ScorchTiles:\s*\n((?:[ \t]*\.byte[^\n]*\n){2})', text, re.MULTILINE)
    found = [int(v, 16) for v in re.findall(r'\$([0-9A-Fa-f]{2})', table.group(1))] if table else []
    if found != order:
        raise ValueError('ScorchTiles in src/blocks.inc does not match assets/town_fire.json')
    return tiles


CASTLE_FIRE_BANK = 3         # North Palace BG pattern table (4K CHR bank)
CASTLE_FIRE_TILES = {
    'flame': {'tl': 0x56, 'bl': 0x57, 'tr': 0x58, 'br': 0x59},
    'char':  {'tl': 0x5A, 'bl': 0x5B, 'tr': 0x5C, 'br': 0x5D},
}
# All 8 tiles are 16 zero bytes in original CHR bank 3.
CASTLE_FIRE_TILE_SHA256 = {tile: '374708fff7719dd5' for stage in CASTLE_FIRE_TILES.values() for tile in stage.values()}


def compile_castle_fire(root: Path) -> dict[int, bytes]:
    """Compile the authored 16x16 flame and char art into eight North Palace BG tiles."""
    spec = json.loads((root / 'assets/town_fire.json').read_text())
    tiles, order = _encode_scorch_art(spec, CASTLE_FIRE_TILES)
    if set(tiles) != set(CASTLE_FIRE_TILE_SHA256):
        raise ValueError('Castle fire tiles differ from the audited allocation')
    text = (root / 'src/blocks.inc').read_text()
    table = re.search(r'^ScorchTiles:\s*\n(?:[ \t]*\.byte[^\n]*\n){2}((?:[ \t]*\.byte[^\n]*\n){2})', text, re.MULTILINE)
    found = [int(v, 16) for v in re.findall(r'\$([0-9A-Fa-f]{2})', table.group(1))] if table else []
    if found != order:
        raise ValueError('Castle ScorchTiles in src/blocks.inc does not match CASTLE_FIRE_TILES')
    return tiles


def compile_title_logo(root: Path) -> tuple[dict[int, bytes], list[list[int]]]:
    """Compile authored BARBA title-screen tiles into LINK's title CHR slots."""
    spec = json.loads((root / 'assets/title_logo.json').read_text())
    palette = {'.': '0', '#': '1', '@': '2', '*': '3'}
    blank = b'\x00' * 16
    solid = b'\xff' * 8 + b'\x00' * 8
    pool = [t for t in sorted(TITLE_TILE_SHA256) if not (0x0F <= t <= 0x17)]
    by_bytes: dict[bytes, int] = {blank: 0xF4, solid: 0xFD}
    tiles: dict[int, bytes] = {}
    letter_grids: dict[str, list[list[int]]] = {}
    for ch, rows in spec['letters'].items():
        if len(rows) != 32 or any(len(r) != 32 or set(r) - set(palette) for r in rows):
            raise ValueError(f'Title letter {ch!r} must be 32x32 using .#@')
        grid: list[list[int]] = []
        for tr in range(4):
            row_ids: list[int] = []
            for tc in range(4):
                sub = [''.join(palette[rows[tr*8 + y][tc*8 + x]] for x in range(8)) for y in range(8)]
                raw = encode_tile(sub)
                if raw not in by_bytes:
                    if not pool:
                        raise ValueError('BARBA title logo exceeded 49 available tile slots')
                    tid = pool.pop(0)
                    by_bytes[raw] = tid
                    tiles[tid] = raw
                row_ids.append(by_bytes[raw])
            grid.append(row_ids)
        letter_grids[ch] = grid
    rows_out: list[list[int]] = []
    for r in range(4):
        row = []
        for ch in spec['word']:
            row.extend(letter_grids[ch][r])
        if r == 0:
            row.append(0xF4)  # blank space (no TM symbol)
        rows_out.append(row)
    sub = spec['subtitle']
    if len(sub) != 8 or any(len(r) != 72 or set(r) - {'.', '*'} for r in sub):
        raise ValueError('Title subtitle must be 8x72 using .*')
    for idx in range(9):
        tiles[0x0F + idx] = encode_tile(
            [''.join(palette[sub[y][idx*8 + x]] for x in range(8)) for y in range(8)]
        )
    return tiles, rows_out


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
        if any(tile != 0xF5 and (tile % 2 or tile >= 0x64 or tile in PLAYER_RESERVED_PAIRS
                                 or tile in ENCOUNTER_TRAIL_PAIRS or tile in ENCOUNTER_CONNECTOR_PAIRS)
               for tile in tiles):
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


def _encounter_torso(graphics: dict[int, bytes]) -> list[str]:
    def pair_rows(pair: bytes) -> list[str]:
        return [''.join(map(str, row)) for offset in (0, 16) for row in decode_tile(pair[offset:offset+16])]

    left, right = (pair_rows(graphics[tile]) for tile in (0x06, 0x08))
    return [a + b for a, b in zip(left, right)]


def _outline(rows: list[str]) -> list[str]:
    """Give every opaque pixel that touches transparency the outline colour."""
    h, w = len(rows), len(rows[0])
    out = [list(row) for row in rows]
    for y in range(h):
        for x in range(w):
            if rows[y][x] != '0' and any(
                    0 <= nx < w and 0 <= ny < h and rows[ny][nx] == '0'
                    for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1))):
                out[y][x] = '1'
    return [''.join(row) for row in out]


def encounter_trail_rows(graphics: dict[int, bytes]) -> list[str]:
    """32x16: the turned torso (two pairs) followed by the 16px tip (two pairs)."""
    torso = _encounter_torso(graphics)
    # The left-facing original has spines on its right edge. CCW brings that
    # edge to the top. The renderer mirrors horizontally for the other facing.
    turned = [''.join(row[x] for row in torso) for x in range(15, -1, -1)]
    # Close the outline on the corner side so the delayed Y never shows a gap.
    closed = [list(row) for row in turned]
    for y in range(2, 13):
        lead = len(turned[y]) - len(turned[y].lstrip('0'))
        if lead:
            closed[y][lead - 1] = '1'
    # The tip tiles columns 10-12 of the turned torso, which repeat its scale
    # pattern, so the dark upper scales drop away first and the belly
    # carries through to the hooked point.
    tip = [['0'] * len(ENCOUNTER_TIP_PROFILE) for _ in range(16)]
    for x, (top, bottom) in enumerate(ENCOUNTER_TIP_PROFILE):
        for y in range(top, bottom + 1):
            if y in (top, bottom):
                tip[y][x] = '1'
            else:
                pixel = turned[min(max(y, 2), 12)][10 + x % 3]
                tip[y][x] = pixel if pixel != '0' else '2'
        if x % ENCOUNTER_TIP_SPINE_EVERY == 0 and top >= 1 and x < len(ENCOUNTER_TIP_PROFILE) - 1:
            tip[top - 1][x] = '3'
    return [''.join(a) + ''.join(b) for a, b in zip(closed, tip)]


def encounter_connector_rows(graphics: dict[int, bytes]) -> list[str]:
    """16x16 elbow: the upright torso swept from vertical (top edge) to
    horizontal (right edge). Belly rides the outer arc, spines the inner."""
    torso = _encounter_torso(graphics)
    pivot_x, pivot_y, radius = ENCOUNTER_ELBOW
    n = len(torso)
    rows = []
    for y in range(16):
        line = ''
        for x in range(16):
            dx, dy = pivot_x - (x + .5), (y + .5) - pivot_y
            angle = math.atan2(dy, dx)
            u = int(math.floor((radius - math.hypot(dx, dy)) * n / radius))
            if not (-0.05 <= angle <= math.pi / 2 + .05 and 0 <= u < n):
                line += '0'
                continue
            v = int(angle / (math.pi / 2) * (n - 1) + .5)
            pixel = torso[v][u]
            if u >= n - 3 and pixel == '3' and v % 3:
                pixel = '1'
            line += pixel
        rows.append(line)
    return _outline(rows)


def compile_file_select_doll(root: Path) -> bytes:
    """Build the 8x16 File Select Barba head/bust sprite pair."""
    doll = [
        '30000003',
        '13000031',
        '01222210',
        '12222221',
        '12322321',
        '12222221',
        '12222221',
        '12122121',
        '01222210',
        '00111100',
        '00122100',
        '01233210',
        '01222210',
        '12233221',
        '12222221',
        '11111111',
    ]
    return sprite_pairs(doll)[0]


def compile_assets(root: Path, source_path: Path | None = None) -> tuple[bytes, dict[int, bytes], bytes, list[list[str]]]:
    art = json.loads((root / 'assets/barba.json').read_text())
    small = art['small']
    for name in ('body', 'small', 'small_step', 'front', 'front_step', 'back', 'back_step'):
        for row in art.get(name, []):
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
                      'crouch-attack', 'crouch', 'crouch-attack', 'tuck',
                      'tuck', 'tuck', 'tuck', 'tuck', 'down', 'death',
                      'tuck', 'tuck', 'tuck')
    fallback = [named[name][16:] for name in fallback_names]

    slots = iter(i for i in range(0, 0x64, 2) if i not in PLAYER_RESERVED_PAIRS)
    pairs: dict[bytes, int] = {bytes(32): 0xF5}
    graphics: dict[int, bytes] = {}
    def allocate(rows):
        result = bytearray()
        for pair in sprite_pairs(rows):
            if pair not in pairs:
                # Reuse an allocated pair that differs by at most one pixel: the
                # player budget is exactly full, and this keeps $60 free.
                near = next((known for known in pairs
                             if _pair_pixel_diff(pair, known) <= 1), None)
                if near is not None:
                    pairs[pair] = pairs[near]
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
    # Downstab mirrors the two neck columns in place; BarbaDisplay toggles
    # both flip attributes without changing the turned head or position.
    down_index = TALL_POSES.index('down')
    tall_mapping[down_index][1:3] = tall_mapping[down_index][1:3][::-1]
    mapping = b''.join(allocate(rows) for rows in fallback)
    remap = bytearray(range(256))
    seam_aliases = {slot: (ENCOUNTER_SEAM_PAIR, 14) for slot in ENCOUNTER_TRAIL_PAIRS[:3]}
    seam_aliases.update({0x34: (ENCOUNTER_SEAM_PAIR, 17), 0x36: (0x2A, 20)})
    tip_slot, tip_replacement, tip_limit = ENCOUNTER_TIP_ALIAS
    seam_aliases[tip_slot] = (tip_replacement, tip_limit)
    for slot, (replacement, limit) in seam_aliases.items():
        if _pair_pixel_diff(graphics[slot], graphics[replacement]) > limit:
            raise ValueError(f'Encounter trail would replace a distinct body column at ${slot:02X}')
        remap[slot] = replacement
    tall_mapping = [row.translate(bytes(remap)) for row in tall_mapping]
    mapping = mapping.translate(bytes(remap))
    graphics.update(zip(ENCOUNTER_TRAIL_PAIRS, sprite_pairs(encounter_trail_rows(graphics))))
    graphics.update(zip(ENCOUNTER_CONNECTOR_PAIRS, sprite_pairs(encounter_connector_rows(graphics))))
    # The old seam is four isolated pixels. Its slots can disappear in the
    # upright poses, freeing a pair for the tapered, upward-pointing pit tail.
    if _pair_pixel_diff(graphics[FALL_TIP_PAIR], bytes(32)) != 4:
        raise ValueError('Falling tail would replace a distinct seam')
    hide_seam = bytes(range(FALL_TIP_PAIR)) + bytes([0xF5]) + bytes(range(FALL_TIP_PAIR + 1, 256))
    tall_mapping = [row.translate(hide_seam) for row in tall_mapping]
    mapping = mapping.translate(hide_seam)
    tip_pairs = [graphics[slot] for slot in ENCOUNTER_TRAIL_PAIRS[2:]]
    near, far = (decode_tile(pair[:16]) + decode_tile(pair[16:]) for pair in tip_pairs)
    tip_rows = [''.join(str(pixel) for pixel in left + right) for left, right in zip(near, far)]
    # Turn the flick so its end points toward the top, then fit the narrow
    # tip into one 8x16 sprite. Its base meets the center of the third chunk.
    vertical_tip = [''.join(column) for column in zip(*tip_rows)][::-1]
    graphics[FALL_TIP_PAIR] = sprite_pairs(resize_x(vertical_tip, 8))[0]
    for slot, elbow in zip(CROUCH_BEND_PAIRS, ENCOUNTER_CONNECTOR_PAIRS):
        graphics[slot] = graphics[elbow][:16] + bytes(16)
    # This file contains indexes only, never extracted CHR pixels. Keeping it
    # checked in lets ca65 validate the renderer without redistributing a ROM.
    include = '; Generated by tools/assets.py from the local verified ROM.\n'
    include += '; Nine 8x16 pairs per pose: three rows, left to right.\n'
    include += 'BarbaTallTiles:\n'
    for name, tiles in zip(TALL_POSES, tall_mapping):
        include += '    .byte ' + ', '.join(f'${v:02X}' for v in tiles) + f' ; {name}\n'
    include += '\n.ifndef DARK_BARBA_LAYOUT\n'
    include += '; Full head above the eight visible rows of the corridor bend.\n'
    for label, pose in (('BarbaCorridorCrouch', 'idle'), ('BarbaCorridorAttack', 'attack')):
        head = tall_mapping[TALL_POSES.index(pose)][:3]
        tiles = [0xF5]*3 + list(head) + [0xF5, *CROUCH_BEND_PAIRS]
        include += f'{label}:\n    .byte ' + ', '.join(f'${v:02X}' for v in tiles) + '\n'
    include += '.endif\n'
    include += '\n; Encounter trail tile indexes rebased for shadow OAM.\n'
    trail_indexes = ('TRAIL_TORSO_LEFT', 'TRAIL_TORSO_RIGHT', 'TRAIL_TIP', 'TRAIL_TIP_FAR',
                     'TRAIL_BEND_CENTER', 'TRAIL_BEND_BACK')
    for name, slot in zip(trail_indexes, ENCOUNTER_TRAIL_PAIRS + ENCOUNTER_CONNECTOR_PAIRS):
        include += f'{name} = ${slot | 1:02X}\n'
    include += f'TRAIL_CORRIDOR_BEND = ${CROUCH_BEND_PAIRS[0] | 1:02X}\n'
    include += f'FALL_TAIL_TILE = ${FALL_TIP_PAIR | 1:02X}\n'
    include_path = root / 'src/tall_layout.inc'
    if not include_path.exists() or include_path.read_text() != include:
        include_path.write_text(include, encoding='ascii')

    # Fairy's 8x16 slot becomes a front-facing Wyrmling, preserving flight logic.
    # The native draw never flips it, so the design is facing-neutral; frames
    # $68/$6A alternate every 4 frames (wings up / wings down).
    wyrmling = art['wyrmling']
    if len(wyrmling) != 2 or any(len(f) != 16 or any(len(r) != 8 or set(r) - set('0123') for r in f)
                                 for f in wyrmling):
        raise ValueError('wyrmling needs two 8x16 frames of 0-3 pixels')
    graphics[0x68] = sprite_pairs(wyrmling[0])[0]
    graphics[0x6A] = sprite_pairs(wyrmling[1])[0]
    ash_graphics, ash_rows = compile_ash(root)
    if graphics.keys() & ash_graphics.keys():
        raise ValueError('Ash sprites overlap another graphics allocation')
    graphics.update(ash_graphics)

    ow = bytearray()
    # Each view may have an explicit walk frame (`<view>_step`); without one the whole sprite bobs.
    small_step = art.get('small_step')
    for rows, step_rows in ((small, small_step), ([r[::-1] for r in small], small_step and [r[::-1] for r in small_step]),
                            (art['front'], art.get('front_step')), (art['back'], art.get('back_step'))):
        for step in (0, 1):
            animated = rows if step == 0 else (step_rows or ['0'*16] + rows[:-1])
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
        'body_pairs': len(set(mapping).union(*tall_mapping) - {0xF5}),
        'available_body_pairs': 0x64//2 - len(PLAYER_RESERVED_PAIRS) - len(seam_aliases),
        'encounter_trail_pairs': list(ENCOUNTER_TRAIL_PAIRS),
        'encounter_connector_pairs': list(ENCOUNTER_CONNECTOR_PAIRS),
        'crouch_bend_pairs': list(CROUCH_BEND_PAIRS), 'wyrmling_pairs': [0x68, 0x6A],
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


def compile_overworld_wyrmling(root: Path) -> bytes:
    """Build 2 frames of centered 16x16 overworld Wyrmling sprite pairs ($80-$87)."""
    wyrmling = json.loads((root / 'assets/barba.json').read_text())['wyrmling']
    if len(wyrmling) != 2 or any(len(f) != 16 or any(len(r) != 8 or set(r) - set('0123') for r in f)
                                 for f in wyrmling):
        raise ValueError('wyrmling needs two 8x16 frames of 0-3 pixels')
    out = bytearray()
    for frame in wyrmling:
        left_pair, right_pair = sprite_pairs(['0000' + row + '0000' for row in frame])
        out.extend(left_pair)
        out.extend(right_pair)
    return bytes(out)
