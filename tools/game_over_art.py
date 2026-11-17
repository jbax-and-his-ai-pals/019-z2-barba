"""Recipe-only game-over Link silhouette, extracted from the user's source ROM."""
from nes import CHR_OFFSET, decode_tile, encode_tile, prg_offset

GAME_OVER_CHR_BANK = 17
GAME_OVER_MAP_START = 0x801F
GAME_OVER_MAP_END = 0x80C9


def _ganon_mask(source: bytes) -> list[list[bool]]:
    """Read the native portrait macro, without storing original art in source."""
    mask = [[False]*256 for _ in range(240)]
    cursor = prg_offset(0, GAME_OVER_MAP_START)
    while source[cursor] != 0xFF:
        address = source[cursor]*256 + source[cursor+1]
        flags = source[cursor+2]
        cursor += 3
        for i in range(flags & 63):
            tile = source[cursor if flags & 64 else cursor+i]
            if 0x2000 <= address < 0x23C0:
                x, y = (address & 31)*8, ((address-0x2000)//32)*8
                offset = CHR_OFFSET + GAME_OVER_CHR_BANK*4096 + tile*16
                for dy, row in enumerate(decode_tile(source[offset:offset+16])):
                    for dx, value in enumerate(row):
                        if y+dy < 240:
                            mask[y+dy][x+dx] = value != 0
            address += 32 if flags & 128 else 1
        cursor += 1 if flags & 64 else flags & 63
    return mask


def _polygon(rows: list[list[str]], points: list[tuple[int, int]], color: str = '3') -> None:
    """Rasterize authored cap, face and collar shapes at NES pixel resolution."""
    for y, row in enumerate(rows):
        for x in range(len(row)):
            inside = False
            for (ax, ay), (bx, by) in zip(points, points[1:]+points[:1]):
                if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
                    inside = not inside
            if inside:
                row[x] = color


def compile_game_over_link(source: bytes, expression: str = 'thin_split', *,
                           cap: str = 'soft', neck_mark: str = 'none',
                           ear_join: str = 'notch') -> tuple[dict[int, bytes], bytes]:
    """Reshape Ganon into a narrow, front-facing black Link bust.

    Only Ganon's dedicated $00-$39 tiles are available. Deduplicate the portrait
    tiles so overworld terrain, font and menu graphics in this bank stay intact.
    Replace the whole Ganon nametable macro (including his broad shoulders).
    Both native game-over palettes map index 3 to NES black ($0F).
    """
    native = _ganon_mask(source)
    rows = [['0']*80 for _ in range(96)]
    # Keep the original looming shoulders/arms, compressed to 44% width.
    # The boar's horns, snout and eyes are replaced completely above the neck.
    for y in range(30, 96):
        for x in range(80):
            sx = 128 + round((x-40)/0.44)
            if 0 <= sx < 256 and native[y+144][sx]:
                rows[y][x] = '3'
    # Neck, human jaw and pointed ears, then a single long folded cap.
    _polygon(rows, [(32,24),(48,24),(49,36),(31,36)])
    _polygon(rows, [(26,14),(54,14),(53,29),(47,35),(33,35),(27,29)])
    _polygon(rows, [(26,20),(17,15),(21,26),(28,28)])
    if ear_join not in ('original', 'notch', 'lower_ear', 'blend', 'round'):
        raise ValueError(f'Unknown game-over ear join: {ear_join}')
    right_ear = ([(54,20),(61,17),(59,25),(52,28)] if ear_join == 'lower_ear'
                 else [(54,20),(63,15),(59,26),(52,28)])
    _polygon(rows, right_ear)
    caps = {
        'original': [(25,17),(28,8),(37,2),(48,1),(57,5),(62,11),
                     (67,15),(57,16),(49,11),(49,16)],
        'soft': [(25,17),(28,8),(37,2),(48,1),(57,5),(61,10),
                 (64,13),(64,15),(59,16),(55,15),(51,13),(50,15),(49,16)],
        'tucked': [(25,17),(28,8),(37,2),(48,1),(56,5),(59,9),
                   (61,13),(61,15),(58,16),(55,16),(52,15),(50,14),(49,17)],
    }
    if cap not in caps:
        raise ValueError(f'Unknown game-over cap: {cap}')
    _polygon(rows, caps[cap])
    if ear_join == 'notch':
        for x in (61, 62, 63):
            rows[15][x] = '0'
    elif ear_join == 'blend':
        # Ease the internal fold into the ear without its sharp red corner.
        rows[15][54] = '3'
        for y, end in ((16,61),(17,59),(18,57),(19,55)):
            for x in range(54, end+1):
                rows[y][x] = '3'
    elif ear_join == 'round':
        for x, y in ((63,13),(63,14),(62,15),(63,15),(62,16)):
            rows[y][x] = '0'
    # The approved portrait uses the mouthless, single-pixel split collar.
    expressions = {
        'collar': [(34,36),(40,40),(46,36),(40,44)],
        'grin': [(32,28),(36,30),(40,31),(44,30),(48,28),
                 (46,32),(42,33),(38,33),(34,32)],
        'smirk': [(34,30),(39,31),(44,30),(48,27),(47,31),(43,33),(38,33)],
        'deep_collar': [(31,42),(40,47),(49,42),(46,49),(40,54),(34,49)],
        'split_collar': [(29,41),(38,45),(37,51),(32,47)],
        'tunic_collar': [(36,42),(40,45),(44,42),(43,49),(42,49),
                         (42,57),(38,57),(38,49),(37,49)],
        'thin_shallow': [], 'thin_v': [], 'thin_split': [],
    }
    if expression not in expressions:
        raise ValueError(f'Unknown game-over expression: {expression}')
    # Smile candidates sit on the face; collar candidates start well below the
    # jaw (row 35), with a solid black chin/neck separating clothing from eyes.
    _polygon(rows, [(30,22),(37,24),(37,26),(31,25)], '0')
    _polygon(rows, [(50,22),(43,24),(43,26),(49,25)], '0')
    _polygon(rows, expressions[expression], '0')
    # Single-pixel clothing seams, with no filled red area beneath the chin.
    thin_marks = {
        'thin_shallow': [(x,38+(6-abs(x-40))//3) for x in range(34,47)],
        'thin_v': [(x,38+6-abs(x-40)) for x in range(34,47)],
        'thin_split': [(x,39+(x-32)//2) for x in range(32,38)] +
                      [(80-x,39+(x-32)//2) for x in range(32,38)],
    }
    for x, y in thin_marks.get(expression, []):
        rows[y][x] = '0'
    if expression == 'thin_split':
        # Close the seven-pixel seam left by the narrowed native right shoulder.
        for y in range(32, 39):
            rows[y][52] = '3'
    if expression == 'split_collar':
        _polygon(rows, [(51,41),(42,45),(43,51),(48,47)], '0')
    elif expression == 'tunic_collar':
        # Black laces break up the vertical opening, making it read as a tunic.
        for y in (50, 54):
            rows[y][38:42] = ['3']*4
    if neck_mark not in ('original', 'none', 'accent'):
        raise ValueError(f'Unknown game-over neck mark: {neck_mark}')
    if neck_mark == 'none':
        rows[31][28] = '3'
    elif neck_mark == 'accent':
        # Extend the isolated native dot into a short, one-pixel diagonal seam.
        for x, y in ((28,31),(29,32),(30,33)):
            rows[y][x] = '0'
    rows = [''.join(row) for row in rows]
    tiles: dict[int, bytes] = {}
    lookup: dict[bytes, int] = {}
    macro = bytearray()
    for ty in range(12):
        address = 0x2000 + (18+ty)*32 + 11
        macro.extend((address >> 8, address & 255, 10))
        for tx in range(10):
            data = encode_tile([row[tx*8:tx*8+8] for row in rows[ty*8:ty*8+8]])
            if data not in lookup:
                tile = len(tiles)
                if tile > 0x39:
                    raise ValueError('Game-over Link exceeds dedicated Ganon CHR tiles')
                lookup[data] = tile
                tiles[tile] = data
            macro.append(lookup[data])
    macro.append(0xFF)
    size = GAME_OVER_MAP_END - GAME_OVER_MAP_START
    if len(macro) > size:
        raise ValueError('Game-over Link exceeds native nametable macro')
    return tiles, bytes(macro).ljust(size, b'\xFF')
