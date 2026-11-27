"""Build-time Z2 art extraction and MMC3 CHR-ROM compiler for Monster Hunt (Duck Hunt)."""
from __future__ import annotations

from pathlib import Path

from assets import encounter_connector_rows, encounter_trail_rows, sprite_pairs
from boss_art import make_frames, resize_x, source_pair
from nes import encode_tile, write_png


# Shared 4 Sprite Palettes (color 0 = transparent / sky)
#   Pal 0: white ($30), red ($16), black ($0F)   -> Score popups, Ache, Acheman, Fokka, Octorok, Palace Plate
#   Pal 1: red ($16), orange ($27), white ($30)  -> Barba, Fireball Burst, Crosshair, Shock flash
#   Pal 2: black ($0F), blue ($12), skin ($36)   -> Moa, Fokkeru, Mago
#   Pal 3: black ($0F), green ($2A), skin ($36)  -> Villainous Link
SPRITE_PAL_BYTES = bytes([
    0x21, 0x30, 0x16, 0x0F,  # Pal 0
    0x21, 0x16, 0x27, 0x30,  # Pal 1
    0x21, 0x0F, 0x12, 0x36,  # Pal 2
    0x21, 0x0F, 0x2A, 0x36,  # Pal 3
])

CROSSHAIR_TILES = (
    (
        '00000000',
        '03333000',
        '03220000',
        '03200000',
        '03000003',
        '00000030',
        '00000000',
        '00000003',
    ),
    (
        '00000000',
        '00033330',
        '00002230',
        '00000230',
        '30000030',
        '03000000',
        '00000000',
        '30000000',
    ),
    (
        '00000003',
        '00000000',
        '00000030',
        '03000003',
        '03200000',
        '03220000',
        '03333000',
        '00000000',
    ),
    (
        '30000000',
        '00000000',
        '03000000',
        '30000030',
        '00000230',
        '00002230',
        '00033330',
        '00000000',
    ),
)

# 3 frames of 16x16 Barba Fireball Burst (tiles $04..$0F, Pal 1: 1=red, 2=orange, 3=white)
FIREBALL_FRAMES = (
    # Frame 0: tight bright core
    (
        '0000000000000000',
        '0000000000000000',
        '0000001111000000',
        '0000012222100000',
        '0000123333210000',
        '0001233333321000',
        '0011233333321100',
        '0012333333332100',
        '0012333333332100',
        '0011233333321100',
        '0001233333321000',
        '0000123333210000',
        '0000012222100000',
        '0000001111000000',
        '0000000000000000',
        '0000000000000000',
    ),
    # Frame 1: expanding flame ring
    (
        '0000001111000000',
        '0001122332211000',
        '0012233333322100',
        '0123332222333210',
        '0123321001233210',
        '1233210330123321',
        '1232103333012321',
        '1232103333012321',
        '1232103333012321',
        '1233210330123321',
        '0123321001233210',
        '0123332222333210',
        '0012233333322100',
        '0001122332211000',
        '0000001111000000',
        '0000000000000000',
    ),
    # Frame 2: dissipating embers
    (
        '0100012002100010',
        '1200230000320021',
        '0010010000100100',
        '0231000110001320',
        '0120001221000210',
        '2000012002100002',
        '1001000000001001',
        '0012000220002100',
        '0012000220002100',
        '1001000000001001',
        '2000012002100002',
        '0120001221000210',
        '0231000110001320',
        '0010010000100100',
        '1200230000320021',
        '0100012002100010',
    ),
)

# 2 shatter/scorch ember tiles ($10..$11) + 2 ash mound tiles ($12..$13)
EMBER_TILES = (
    (
        '00120000',
        '01232000',
        '00231010',
        '00010121',
        '01000010',
        '12100000',
        '01001200',
        '00000100',
    ),
    (
        '00002100',
        '01023210',
        '12101200',
        '01000000',
        '00120010',
        '00231121',
        '00010010',
        '00000000',
    ),
    (
        '00000000',
        '00000000',
        '00000110',
        '00011221',
        '00122322',
        '01232212',
        '11221121',
        '11111111',
    ),
    (
        '00000000',
        '00000000',
        '01100000',
        '12211000',
        '22322100',
        '21223210',
        '12112211',
        '11111111',
    ),
)

# HUD icons (8x8 BG tiles, color 0=black box, 1=blue, 2=white (unhit), 3=red (hit))
HUD_OCTOROK_UNHIT = (
    '11111111',
    '11222211',
    '12222221',
    '22122122',
    '22222222',
    '12122121',
    '21122112',
    '11111111',
)
HUD_OCTOROK_HIT = (
    '11111111',
    '11333311',
    '13333331',
    '33133133',
    '33333333',
    '13133131',
    '31133113',
    '11111111',
)
HUD_ENEMY_UNHIT = (
    '11111111',
    '12111121',
    '22211222',
    '22222222',
    '21211212',
    '11222211',
    '11122111',
    '11111111',
)
HUD_ENEMY_HIT = (
    '11111111',
    '13111131',
    '33311333',
    '33333333',
    '31311313',
    '11333311',
    '11133111',
    '11111111',
)
HUD_FIREBALL_ICON = (
    '00001000',
    '00122100',
    '01233210',
    '12333221',
    '12333221',
    '01232110',
    '00111000',
    '00000000',
)


def _pair(z2: bytes, bank: int, tid: int) -> list[str]:
    if tid == 0xF5:
        return ['0' * 8] * 16
    return source_pair(z2, tid & 0xFE, bank)


def _z2_16x32(z2: bytes, eb: int, ob: int, tl: int, tr: int, bl: int, br: int) -> list[str]:
    def getp(t: int) -> list[str]:
        return _pair(z2, ob if (t & 1) else eb, t)
    a, b, c, d = getp(tl), getp(tr), getp(bl), getp(br)
    return [a[y] + b[y] for y in range(16)] + [c[y] + d[y] for y in range(16)]


def _z2_16x16(z2: bytes, eb: int, ob: int, l: int, r: int) -> list[str]:
    a = _pair(z2, ob if (l & 1) else eb, l)
    b = _pair(z2, ob if (r & 1) else eb, r)
    return [a[y] + b[y] for y in range(16)]


def _z2_16x16_mir(z2: bytes, bank: int, tid: int) -> list[str]:
    """Build a symmetric 16x16 sprite by horizontally mirroring an 8x16 tile pair."""
    a = _pair(z2, bank, tid)
    return [a[y] + a[y][::-1] for y in range(16)]


def _pad32(rows16: list[str], y_off: int = 8) -> list[str]:
    """Center/place a 16x16 sprite inside a 16x32 canvas."""
    return ['0' * 16] * y_off + rows16 + ['0' * 16] * (16 - y_off)


def _bob_up2(rows32: list[str]) -> list[str]:
    """Shift a 16x32 sprite up by 2 pixels for flight/hover animation."""
    return rows32[2:] + ['0' * 16] * 2


def _composite_16x32(top16: list[str], top_y: int, bot16: list[str], bot_y: int) -> list[str]:
    """Composite two 16x16 halves onto a 16x32 canvas with configurable Y offsets."""
    canvas = [['0'] * 16 for _ in range(32)]
    for oy, part in ((top_y, top16), (bot_y, bot16)):
        for y, row in enumerate(part):
            if 0 <= oy + y < 32:
                for x, c in enumerate(row):
                    if c != '0':
                        canvas[oy + y][x] = c
    return [''.join(r) for r in canvas]


def _remap(rows: list[str], mapping: dict[str, str], *, flip_h: bool = False) -> list[str]:
    out = []
    for row in rows:
        rr = row[::-1] if flip_h else row
        out.append(''.join(mapping[c] for c in rr))
    return out


def _shrink_y(rows: list[str], h: int) -> list[str]:
    """Nearest-neighbor vertical resample to h rows."""
    old_h = len(rows)
    return [rows[min(old_h - 1, (y * old_h + h // 2) // h)] for y in range(h)]


def _shrink_rows(rows: list[str], w: int, h: int) -> list[str]:
    """Nearest-neighbor shrink/pad to 16x16 centered."""
    resized = resize_x(rows, w)
    shrunk_y = _shrink_y(resized, h)
    ox = (16 - w) // 2
    oy = (16 - h) // 2
    canvas = [['0'] * 16 for _ in range(16)]
    for y, r in enumerate(shrunk_y):
        for x, c in enumerate(r):
            canvas[oy + y][ox + x] = c
    return [''.join(r) for r in canvas]


def _make_shared_r0_head() -> list[bytes]:
    """Build tiles $00..$1F (32 tiles) shared across all R0 banks."""
    tiles: list[bytes] = [b'\x00' * 16] * 32
    # $00..$03: Crosshair
    for i, t in enumerate(CROSSHAIR_TILES):
        tiles[i] = encode_tile(list(t))
    # $04..$0F: 3 frames of 2x2 Fireball Burst
    for fi, grid in enumerate(FIREBALL_FRAMES):
        for ty in range(2):
            for tx in range(2):
                sub = [grid[ty * 8 + y][tx * 8 : (tx + 1) * 8] for y in range(8)]
                tiles[4 + fi * 4 + ty * 2 + tx] = encode_tile(sub)
    # $10..$13: Embers & Ash
    for i, t in enumerate(EMBER_TILES):
        tiles[0x10 + i] = encode_tile(list(t))
    # $18: Solid white Zapper flash box (color 1 = $30 in Pal 0)
    tiles[0x18] = encode_tile(['1' * 8] * 8)
    return tiles


def _pack_grids_into_bank(
    grids: list[list[str]],
    base_tile: int,
    max_tile_excl: int,
) -> tuple[list[bytes], list[list[int]]]:
    """Deduplicate 8x8 tiles from WxH pixel grids starting at base_tile.

    Returns (encoded_tiles, per_grid_flat_tile_ids) where 0xFF means blank/skip.
    """
    pool: dict[bytes, int] = {}
    tiles_out: list[bytes] = []
    maps: list[list[int]] = []
    for grid in grids:
        ht = len(grid) // 8
        wt = len(grid[0]) // 8
        m: list[int] = []
        for ty in range(ht):
            for tx in range(wt):
                sub = [grid[ty * 8 + y][tx * 8 : (tx + 1) * 8] for y in range(8)]
                if all(c == '0' for r in sub for c in r):
                    m.append(0xFF)
                    continue
                enc = encode_tile(sub)
                tid = pool.get(enc)
                if tid is None:
                    tid = base_tile + len(tiles_out)
                    assert tid < max_tile_excl, f'CHR tile overflow: ${tid:02X} >= ${max_tile_excl:02X}'
                    pool[enc] = tid
                    tiles_out.append(enc)
                m.append(tid)
        maps.append(m)
    return tiles_out, maps


def _build_barba_full_and_down(z2: bytes) -> tuple[dict[str, list[tuple[int, int, list[str]]]], dict[str, list[str]]]:
    """Build right-facing full-body Barba poses (head+torso+bend+2-tile tail) and Z2 downstab.

    Returns (pose_pieces, preview_grids) where each pose_pieces[name] is a list of
    (dx, dy, grid_rows) tuples relative to the 24x48 body origin (dx=0..23, dy=0..47).
    """
    raw = make_frames(z2, 24)
    # Extract the 16x16 upright torso from idle[16:32] cols 8..24 (matches Z2's $06/$08)
    torso_left = [row[8:24] for row in raw['idle'][16:32]]
    t_pairs = sprite_pairs(torso_left)
    fake_gfx = {0x06: t_pairs[0], 0x08: t_pairs[1]}
    bend_left = encounter_connector_rows(fake_gfx)   # 16x16
    trail_left = encounter_trail_rows(fake_gfx)      # 32x16
    tip_rows = [row[16:32] for row in trail_left]
    vertical_tip = [''.join(col) for col in zip(*tip_rows)][::-1]
    tip_8x16 = resize_x(vertical_tip, 8)

    # Flip horizontally so Barba faces RIGHT (matching Duck Hunt $34=0);
    # downstab torso chunks keep torso_left's horizontal orientation (mirrored vs head_down_right).
    bend_right = [r[::-1] for r in bend_left]
    trail_right = [r[::-1] for r in trail_left]
    torso_down_right = torso_left[::-1]
    tip_right = [r[::-1] for r in tip_8x16]
    head_down_right = [r[::-1] for r in raw['down'][16:48]]

    poses: dict[str, list[tuple[int, int, list[str]]]] = {}
    previews: dict[str, list[str]] = {}

    def compose_preview(pieces: list[tuple[int, int, list[str]]]) -> list[str]:
        # Canvas: x in [-32..23] (56px), y in [-48..47] (96px)
        canvas = [['0'] * 56 for _ in range(96)]
        for dx, dy, grid in pieces:
            ox, oy = dx + 32, dy + 48
            for y, row in enumerate(grid):
                for x, ch in enumerate(row):
                    if ch != '0' and 0 <= oy + y < 96 and 0 <= ox + x < 56:
                        canvas[oy + y][ox + x] = ch
        return [''.join(r) for r in canvas]

    for name in ('walk0', 'walk1', 'windup', 'attack'):
        upper = [r[::-1] for r in raw[name][0:32]]
        pieces = [
            (0, 0, upper),
            (0, 32, bend_right),
            (-32, 32, trail_right),
        ]
        poses[name] = pieces
        previews[name] = compose_preview(pieces)

    # Crouch / sniffing: head dips down 16px directly onto the bend + horizontal tail
    crouch_head = [r[::-1] for r in raw['idle'][0:16]]
    crouch_pieces = [
        (0, 16, crouch_head),
        (0, 32, bend_right),
        (-32, 32, trail_right),
    ]
    poses['crouch'] = crouch_pieces
    previews['crouch'] = compose_preview(crouch_pieces)

    # Downstab: exact Z2 Barba downstab (vertical tip + 3 torso chunks + turned open-jaw head)
    down_pieces = [
        (4, -48, tip_right),
        (0, -32, torso_down_right),
        (0, -16, torso_down_right),
        (0, 0, torso_down_right),
        (0, 16, head_down_right),
    ]
    poses['downstab'] = down_pieces
    previews['downstab'] = compose_preview(down_pieces)

    # Catch celebration (emerging from bushes after a hit): 3 vertical 16px rows (24x48: head + 2 torso chunks, no bend/tail)
    for name in ('windup', 'attack'):
        upper = [r[::-1] for r in raw[name][0:32]]
        extra_torso = [r[::-1] for r in raw[name][16:32]]
        cname = f'catch_{name}'
        poses[cname] = [
            (0, 0, upper),
            (0, 32, extra_torso),
        ]
        previews[cname] = compose_preview(poses[cname])

    return poses, previews


def _pack_barba_poses(
    poses: dict[str, list[tuple[int, int, list[str]]]],
    order: tuple[str, ...],
    base_tile: int,
    max_tile_excl: int,
) -> tuple[list[bytes], list[list[tuple[int, int, int]]]]:
    """Deduplicate 8x8 tiles from Barba pose pieces into (tile_id, dx, dy) metasprite lists."""
    pool: dict[bytes, int] = {}
    tiles_out: list[bytes] = []
    maps: list[list[tuple[int, int, int]]] = []
    for name in order:
        entries: list[tuple[int, int, int]] = []
        for dx, dy, grid in poses[name]:
            ht = len(grid) // 8
            wt = len(grid[0]) // 8
            for ty in range(ht):
                for tx in range(wt):
                    sub = [grid[ty * 8 + y][tx * 8 : (tx + 1) * 8] for y in range(8)]
                    if all(c == '0' for r in sub for c in r):
                        continue
                    enc = encode_tile(sub)
                    tid = pool.get(enc)
                    if tid is None:
                        tid = base_tile + len(tiles_out)
                        assert tid < max_tile_excl, f'Barba CHR tile overflow: ${tid:02X} >= ${max_tile_excl:02X}'
                        pool[enc] = tid
                        tiles_out.append(enc)
                    entries.append((tid, (dx + tx * 8) & 0xFF, (dy + ty * 8) & 0xFF))
        maps.append(entries)
    return tiles_out, maps


def _build_villainous_link(z2: bytes) -> list[list[str]]:
    """Build 2 side-profile 16x32 frames of vanilla Z2 Link (Pal 3: 1=black, 2=green, 3=skin)."""
    # Vanilla Z2 Link standing ($00/$02/$04/$06) and walking ($08/$0A/$0C/$0E) in CHR bank 2
    # Map Z2 Link colors (1=outline, 2=skin, 3=green) -> Pal 3 (1=black, 2=green, 3=skin)
    m = {'0': '0', '1': '1', '2': '3', '3': '2'}
    f0 = _remap(_z2_16x32(z2, 2, 3, 0x00, 0x02, 0x04, 0x06), m, flip_h=True)
    f1 = _remap(_z2_16x32(z2, 2, 3, 0x08, 0x0A, 0x0C, 0x0E), m, flip_h=True)
    return [f0, f1]


def build_duck_chr_and_tables(duck_bytes: bytes, z2_bytes: bytes) -> dict:
    """Compile the 32KB MMC3 CHR-ROM and metasprite tilemap tables for Villager Hunt."""
    orig_chr = duck_bytes[16 + 16384 : 16 + 16384 + 8192]
    assert len(orig_chr) == 8192
    orig_spr = bytearray(orig_chr[0:4096])
    orig_bg = bytearray(orig_chr[4096:8192])

    # 1. Gameplay BG (1KB banks 0..3): patch HUD icons $D3(hit clay), $D4(unhit clay), $D5(hit enemy), $D6(unhit enemy), $D9(fireball)
    # Leave $D7 (blue pass-threshold line) untouched!
    game_bg = bytearray(orig_bg)
    game_bg[0xD3 * 16 : 0xD4 * 16] = encode_tile(list(HUD_OCTOROK_HIT))
    game_bg[0xD4 * 16 : 0xD5 * 16] = encode_tile(list(HUD_OCTOROK_UNHIT))
    game_bg[0xD5 * 16 : 0xD6 * 16] = encode_tile(list(HUD_ENEMY_HIT))
    game_bg[0xD6 * 16 : 0xD7 * 16] = encode_tile(list(HUD_ENEMY_UNHIT))
    game_bg[0xD9 * 16 : 0xDA * 16] = encode_tile(list(HUD_FIREBALL_ICON))

    # 1b. Game A/B Forest Encounter BG (1KB banks 18..21): Z2 Bank 3 forest scenery + remapped HUD
    forest_bg = bytearray(game_bg)
    z2_chr_base = 16 + 128 * 1024 + 3 * 4096
    forest_tile_map = (
        (0x60, 0x44), (0x61, 0x45), (0x62, 0x46), (0x63, 0x47),  # Tree trunk
        (0x64, 0x48), (0x65, 0x49), (0x66, 0x4A), (0x67, 0x4B),  # Forest ground
        (0x68, 0x50), (0x69, 0x51), (0x6A, 0x52), (0x6B, 0x53),  # Canopy leaves
        (0x6C, 0x54), (0x6D, 0x55),                              # Hanging canopy leaves
        (0x6E, 0x78), (0x6F, 0x79),                              # Forest bushes
    )
    for dst_tid, src_tid in forest_tile_map:
        src_off = z2_chr_base + src_tid * 16
        forest_bg[dst_tid * 16 : (dst_tid + 1) * 16] = z2_bytes[src_off : src_off + 16]
    # On black ($0F) backdrop, remap color 0 -> color 2 ($29 green) in SHOT ($DA-$DC),
    # pass-threshold ($D7), and fireball icon ($D9) so they remain crisp on black.
    from nes import decode_tile as _decode_tile
    for hud_tid in (0xD7, 0xD9, 0xDA, 0xDB, 0xDC):
        rows = _decode_tile(bytes(forest_bg[hud_tid * 16 : (hud_tid + 1) * 16]))
        remapped = [''.join('2' if c == 0 else str(c) for c in r) for r in rows]
        forest_bg[hud_tid * 16 : (hud_tid + 1) * 16] = encode_tile(remapped)
    # Thematic HUD backdrop tile ($50): solid color 3 (Pal 2 dark green $09)
    forest_bg[0x50 * 16 : 0x51 * 16] = encode_tile(['33333333'] * 8)

    # 1c. Game A/B Overworld Grass Encounter BG (1KB banks 32..35)
    grass_bg = bytearray(game_bg)
    grass_tile_map = (
        (0x60, 0xB3), (0x61, 0xB5), (0x62, 0xB7),                # Cloud top (L, M, R)
        (0x63, 0xB4), (0x6A, 0xB6), (0x6B, 0xB8),                # Cloud bottom (L, M, R)
        (0x64, 0x36), (0x65, 0x36), (0x66, 0x37), (0x67, 0x37),  # Overworld grass ground ($36/$37)
        (0x68, 0x4E), (0x69, 0x4F),                              # Tall grass sprigs ($4E top, $4F bottom)
        (0x6E, 0x4C), (0x6F, 0x4D),                              # Grass-area bushes ($4C top, $4D bottom)
    )
    for dst_tid, src_tid in grass_tile_map:
        src_off = z2_chr_base + src_tid * 16
        grass_bg[dst_tid * 16 : (dst_tid + 1) * 16] = z2_bytes[src_off : src_off + 16]
    # Thematic HUD backdrop tile ($50): solid color 3 (Pal 2 mid green $19)
    grass_bg[0x50 * 16 : 0x51 * 16] = encode_tile(['33333333'] * 8)

    # 1d. Game A/B Desert Encounter BG (1KB banks 36..39)
    desert_bg = bytearray(game_bg)
    desert_tile_map = (
        (0x60, 0xB3), (0x61, 0xB5), (0x62, 0xB7),                # Cloud top (L, M, R)
        (0x63, 0xB4), (0x6A, 0xB6), (0x6B, 0xB8),                # Cloud bottom (L, M, R)
        (0x64, 0x36), (0x65, 0x36), (0x66, 0x37), (0x67, 0x37),  # Desert sand ground ($36/$37)
        (0x68, 0x3C), (0x69, 0x3D), (0x6C, 0x3E), (0x6D, 0x3F),  # Cacti ($3C top, $3D stem, $3E/$3F arm)
        (0x6F, 0x35),                                            # Desert surface sand bump ($35)
    )
    for dst_tid, src_tid in desert_tile_map:
        src_off = z2_chr_base + src_tid * 16
        desert_bg[dst_tid * 16 : (dst_tid + 1) * 16] = z2_bytes[src_off : src_off + 16]
    # Thematic HUD backdrop tile ($50): solid color 3 (Pal 2 sand $36)
    desert_bg[0x50 * 16 : 0x51 * 16] = encode_tile(['33333333'] * 8)

    # 2. Title BG (1KB banks 4..7): copy gameplay BG + custom rounded "BARBA'S" logo tiles ($C0..$CD)
    title_bg = bytearray(game_bg)
    title_logo_tiles: dict[int, list[str]] = {
        0xC0: [  # 10px left stem, 4px gap, 10px right stem (A legs, B/R vertical)
            '11000011',
            '11000011',
            '11000011',
            '11000011',
            '11000011',
            '11000011',
            '11000011',
            '11000011',
        ],
        0xC1: [  # A inner arch hole
            '11111111',
            '11111111',
            '11100111',
            '11000011',
            '11000011',
            '11000011',
            '11000011',
            '11000011',
        ],
        0xC2: [  # B/R rounded inner hole
            '11100111',
            '11000011',
            '11000011',
            '11000011',
            '11000011',
            '11000011',
            '11000011',
            '11100111',
        ],
        0xC3: [  # B/R upper waist curve
            '11111111',
            '11111111',
            '11111111',
            '11111111',
            '11111111',
            '11111110',
            '11111100',
            '11111000',
        ],
        0xC4: [  # B/R waist notch
            '11110000',
            '11100000',
            '11000000',
            '11000000',
            '11000000',
            '11000000',
            '11100000',
            '11110000',
        ],
        0xC5: [  # B/R lower waist curve
            '11111000',
            '11111100',
            '11111110',
            '11111111',
            '11111111',
            '11111111',
            '11111111',
            '11111111',
        ],
        0xC6: [  # Apostrophe top-left
            '00000111',
            '00000111',
            '00000111',
            '00000111',
            '00000111',
            '00000111',
            '00000111',
            '00000111',
        ],
        0xC7: [  # Apostrophe top-right
            '11100000',
            '11100000',
            '11100000',
            '11100000',
            '11100000',
            '11100000',
            '11100000',
            '11100000',
        ],
        0xC8: [  # Apostrophe bottom-left
            '00000111',
            '00000111',
            '00001111',
            '00001110',
            '00011100',
            '00011000',
            '00000000',
            '00000000',
        ],
        0xC9: [  # Apostrophe bottom-right
            '11100000',
            '11000000',
            '10000000',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
        ],
        0xCA: [  # S row 1 col 1 (10px left stem)
            '11000000',
            '11000000',
            '11000000',
            '11000000',
            '11000000',
            '11000000',
            '11000000',
            '11000000',
        ],
        0xCB: [  # S row 1 col 2 (upper-right tip)
            '11111111',
            '11111111',
            '11111111',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
        ],
        0xCC: [  # S row 3 col 0 (lower-left tip)
            '00000000',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
            '11111111',
            '11111111',
            '11111111',
        ],
        0xCD: [  # S row 3 col 1 (10px right stem)
            '00000011',
            '00000011',
            '00000011',
            '00000011',
            '00000011',
            '00000011',
            '00000011',
            '00000011',
        ],
    }
    for tid, grid in title_logo_tiles.items():
        title_bg[tid * 16 : (tid + 1) * 16] = encode_tile(grid)

    # 3. 5 Themed 2KB R0 Enemy Banks (each: Shared $00..$1F + up to 96 enemy tiles $20..$7F)
    shared_r0 = _make_shared_r0_head()
    # Z2 enemy color mappings -> our 4 Sprite Palettes:
    #   Pal 0: 1=white ($30), 2=red ($16), 3=black ($0F)
    #   Pal 1: 1=red ($16), 2=orange ($27), 3=white ($30)
    #   Pal 2: 1=black ($0F), 2=blue ($12), 3=skin ($36)
    #   Pal 3: 1=black ($0F), 2=green ($2A), 3=skin ($36)
    m_pal0  = {'0': '0', '1': '3', '2': '2', '3': '1'}
    m_ident = {'0': '0', '1': '1', '2': '2', '3': '3'}

    def make_r0_bank(specs: list[tuple[str, int, list[str], list[str]]]) -> tuple[bytearray, list[int], list[list[int]], int]:
        grids: list[list[str]] = []
        pals: list[int] = []
        for _, pal_idx, f0, f1 in specs:
            grids.extend((f0, f1))
            pals.append(pal_idx)
        tiles, maps = _pack_grids_into_bank(grids, 0x20, 0x80)
        bank = bytearray(b'\x00' * 2048)
        for i, t in enumerate(shared_r0):
            bank[i * 16 : (i + 1) * 16] = t
        for i, t in enumerate(tiles):
            bank[(0x20 + i) * 16 : (0x21 + i) * 16] = t
        return bank, pals, maps, len(tiles)

    # --- R0 Bank 0 (1KB banks 8..9, R0=8): Shared / Overworld ---
    ache_f0 = _remap(_pad32(_z2_16x16_mir(z2_bytes, 8, 0x4E), 8), m_pal0)
    ache_f1 = _remap(_pad32(_z2_16x16_mir(z2_bytes, 8, 0x50), 9), m_pal0)
    acheman_f0 = _remap(_z2_16x32(z2_bytes, 8, 8, 0x7C, 0x7E, 0x80, 0x82), m_pal0)
    acheman_f1 = _bob_up2(acheman_f0)
    moa_raw = _z2_16x16(z2_bytes, 8, 8, 0xB6, 0xB8)
    moa_f0 = _remap(_pad32(moa_raw, 8), m_ident)
    moa_f1 = _remap(_pad32(moa_raw[::-1], 8), m_ident)
    bot_f0 = _remap(_pad32(_z2_16x16_mir(z2_bytes, 8, 0xB2), 8), m_ident)
    bot_f1 = _remap(_pad32(_z2_16x16_mir(z2_bytes, 8, 0xB4), 8), m_ident)
    bagobago_f0 = _remap(_pad32(_z2_16x16(z2_bytes, 8, 8, 0xC0, 0xC2), 8), m_pal0)
    bagobago_f1 = _remap(_pad32(_z2_16x16(z2_bytes, 8, 8, 0xC0, 0xC4), 8), m_pal0)
    myu_f0 = _remap(_pad32(_z2_16x16_mir(z2_bytes, 8, 0x24), 8), m_ident)
    myu_f1 = _remap(_pad32(_z2_16x16_mir(z2_bytes, 8, 0xB0), 8), m_ident)
    deeler_f0 = _remap(_pad32(_z2_16x16(z2_bytes, 8, 8, 0xC6, 0xC8), 8), m_pal0)
    deeler_f1 = _remap(_pad32(_z2_16x16(z2_bytes, 8, 8, 0xCA, 0xCC), 8), m_pal0)
    # Actual Z2 Fairy: Bank 8 $68 (f0), $6A (f1) (8x16 centered in 16x32)
    f0_8 = _pair(z2_bytes, 8, 0x68)
    f1_8 = _pair(z2_bytes, 8, 0x6A)
    fairy_f0 = _remap(_pad32(['0' * 4 + r + '0' * 4 for r in f0_8], 8), m_pal0)
    fairy_f1 = _bob_up2(_remap(_pad32(['0' * 4 + r + '0' * 4 for r in f1_8], 8), m_pal0))

    bank_shared_specs = [
        ('ache',     0, ache_f0,     ache_f1),
        ('acheman',  0, acheman_f0,  acheman_f1),
        ('moa',      2, moa_f0,      moa_f1),
        ('bot',      2, bot_f0,      bot_f1),
        ('bagobago', 0, bagobago_f0, bagobago_f1),
        ('myu',      2, myu_f0,      myu_f1),
        ('deeler',   0, deeler_f0,   deeler_f1),
        ('fairy',    1, fairy_f0,    fairy_f1),
    ]
    r0_villagers, v0_pals, v0_maps, v0_cnt = make_r0_bank(bank_shared_specs)

    # --- R0 Bank 1 (1KB banks 22..23, R0=22): West Hyrule & Death Mountain (Z2 Bank 2/3) ---
    moby_f0 = _remap(_pad32(_z2_16x16(z2_bytes, 2, 3, 0xD0, 0xD2), 8), m_pal0)
    moby_f1 = _remap(_pad32(_z2_16x16(z2_bytes, 2, 3, 0xD0, 0xD4), 8), m_pal0)
    lowder_f0 = _remap(_pad32(_z2_16x16(z2_bytes, 2, 3, 0xDE, 0xE0), 8), m_pal0)
    lowder_f1 = _remap(_pad32(_z2_16x16(z2_bytes, 2, 3, 0xE2, 0xE0), 8), m_pal0)
    megmat_f0 = _remap(_pad32(_z2_16x16(z2_bytes, 2, 3, 0xD6, 0xD8), 8), m_pal0)
    megmat_f1 = _remap(_pad32(_z2_16x16(z2_bytes, 2, 3, 0xDA, 0xDC), 8), m_pal0)
    moblin_f0 = _remap(_z2_16x32(z2_bytes, 2, 3, 0x0F, 0x11, 0x17, 0x19), m_pal0)
    moblin_f1 = _remap(_z2_16x32(z2_bytes, 2, 3, 0x0F, 0x11, 0x13, 0x15), m_pal0)
    daira_f0 = _remap(_z2_16x32(z2_bytes, 2, 3, 0xE6, 0xE8, 0xEA, 0xEC), m_pal0)
    daira_f1 = _remap(_z2_16x32(z2_bytes, 2, 3, 0xEE, 0xF0, 0xF2, 0xF4), m_pal0)
    goriya_f0 = _remap(_z2_16x32(z2_bytes, 2, 3, 0x01, 0x03, 0xEA, 0xEC), m_pal0)
    goriya_f1 = _remap(_z2_16x32(z2_bytes, 2, 3, 0x05, 0x07, 0xF2, 0xF4), m_pal0)
    geld_head = _pair(z2_bytes, 2, 0x62)
    geld_body = _pair(z2_bytes, 2, 0x64)
    geldarm_f0 = _remap(['0' * 4 + r + '0' * 4 for r in geld_head + geld_body], m_pal0)
    geldarm_f1 = geldarm_f0

    bank_west_specs = [
        ('moby',    0, moby_f0,    moby_f1),
        ('lowder',  0, lowder_f0,  lowder_f1),
        ('megmat',  0, megmat_f0,  megmat_f1),
        ('moblin',  0, moblin_f0,  moblin_f1),
        ('daira',   0, daira_f0,   daira_f1),
        ('goriya',  0, goriya_f0,  goriya_f1),
        ('geldarm', 0, geldarm_f0, geldarm_f1),
    ]
    r0_villagers2, v1_pals, v1_maps, v1_cnt = make_r0_bank(bank_west_specs)

    # --- R0 Bank 2 (1KB banks 24..25, R0=24): East Hyrule & Maze Island (Z2 Bank 4/5) ---
    tektite_f0 = _remap(_z2_16x32(z2_bytes, 4, 5, 0xD0, 0xD2, 0xD4, 0xD6), m_pal0)
    tektite_f1 = _remap(_z2_16x32(z2_bytes, 4, 5, 0xD8, 0xDA, 0xD4, 0xD6), m_pal0)
    aru_24_f0 = (
        ['0' * 8 + _z2_16x16(z2_bytes, 4, 5, 0xFC, 0xFE)[y] for y in range(16)]
        + [_pair(z2_bytes, 4, 0xEE)[y] + _z2_16x16(z2_bytes, 4, 5, 0xF0, 0xF4)[y] for y in range(16)]
    )
    aru_24_f1 = (
        ['0' * 8 + _z2_16x16(z2_bytes, 4, 5, 0xF5, 0xF2)[y] for y in range(16)]
        + [_pair(z2_bytes, 4, 0xFA)[y] + _z2_16x16(z2_bytes, 4, 5, 0xF6, 0xF8)[y] for y in range(16)]
    )
    aru_f0 = _remap(resize_x(aru_24_f0, 16), m_pal0)
    aru_f1 = _remap(resize_x(aru_24_f1, 16), m_pal0)
    zora_f0 = _remap(_z2_16x32(z2_bytes, 4, 5, 0xE6, 0xE8, 0xEA, 0xEC), m_pal0)
    zora_f1 = _bob_up2(zora_f0)
    giro_f0 = _remap(_pad32(_z2_16x16(z2_bytes, 4, 5, 0x01, 0x03), 8), m_pal0)
    giro_f1 = _remap(_pad32(_z2_16x16(z2_bytes, 4, 5, 0x05, 0x03), 8), m_pal0)
    leever_f0 = _remap(_pad32(_z2_16x16_mir(z2_bytes, 5, 0x07), 8), m_pal0)
    leever_f1 = _remap(_pad32(_z2_16x16_mir(z2_bytes, 5, 0x09), 8), m_pal0)
    boon_f0 = _remap(_pad32(_z2_16x16(z2_bytes, 4, 5, 0x0B, 0x0D), 8), m_pal0)
    boon_f1 = _remap(_pad32(_z2_16x16(z2_bytes, 4, 5, 0x0B, 0x0F), 8), m_pal0)
    liz_f0 = _remap(_z2_16x32(z2_bytes, 4, 5, 0x11, 0x13, 0x15, 0x17), m_pal0)
    liz_f1 = _remap(_z2_16x32(z2_bytes, 4, 5, 0x11, 0x13, 0x19, 0x1B), m_pal0)

    bank_east_specs = [
        ('tektite',    0, tektite_f0, tektite_f1),
        ('aru_lowder', 0, aru_f0,     aru_f1),
        ('zora',       0, zora_f0,    zora_f1),
        ('girobokku',  0, giro_f0,    giro_f1),
        ('leever',     0, leever_f0,  leever_f1),
        ('boon',       0, boon_f0,    boon_f1),
        ('lizalfos',   0, liz_f0,     liz_f1),
    ]
    r0_villagers3, v2_pals, v2_maps, v2_cnt = make_r0_bank(bank_east_specs)

    # --- R0 Bank 3 (1KB banks 26..27, R0=26): Palaces 1-6 ---
    stalfos_f0 = _remap(_z2_16x32(z2_bytes, 8, 9, 0xF0, 0xF2, 0xF4, 0xF6), m_pal0)
    stalfos_f1 = _remap(_z2_16x32(z2_bytes, 8, 9, 0xF0, 0xF2, 0xF8, 0xFA), m_pal0)
    ironknuckle_f0 = _remap(_z2_16x32(z2_bytes, 8, 9, 0x41, 0x43, 0x49, 0x4B), m_ident)
    ironknuckle_f1 = _remap(_z2_16x32(z2_bytes, 8, 9, 0x41, 0x43, 0x45, 0x47), m_ident)
    wizzrobe_f0 = _remap(_z2_16x32(z2_bytes, 20, 21, 0xD0, 0xD2, 0xD4, 0xD6), m_ident)
    wizzrobe_f1 = _bob_up2(wizzrobe_f0)
    mago_f0 = _remap(_z2_16x32(z2_bytes, 22, 22, 0xD0, 0xD2, 0xD4, 0xD6), m_ident)
    mago_f1 = _bob_up2(mago_f0)
    guma_f0 = _remap(_z2_16x32(z2_bytes, 8, 9, 0xE0, 0xE2, 0xE4, 0xE6), m_pal0)
    guma_f1 = _remap(_z2_16x32(z2_bytes, 8, 9, 0xE0, 0xE2, 0xE8, 0xEA), m_pal0)
    mau_f0 = _remap(_pad32(_z2_16x16(z2_bytes, 18, 19, 0x39, 0x3B), 8), m_pal0)
    mau_f1 = _bob_up2(mau_f0)

    bank_palace_specs = [
        ('stalfos',     0, stalfos_f0,     stalfos_f1),
        ('ironknuckle', 2, ironknuckle_f0, ironknuckle_f1),
        ('wizzrobe',    2, wizzrobe_f0,    wizzrobe_f1),
        ('mago',        2, mago_f0,        mago_f1),
        ('guma',        0, guma_f0,        guma_f1),
        ('mau',         0, mau_f0,         mau_f1),
    ]
    r0_villagers4, v3_pals, v3_maps, v3_cnt = make_r0_bank(bank_palace_specs)

    # --- R0 Bank 4 (1KB banks 28..29, R0=28): Great Palace ---
    fokka_f0 = _remap(_z2_16x32(z2_bytes, 12, 13, 0x41, 0x43, 0x49, 0x4B), m_pal0)
    fokka_f1 = fokka_f0
    fokkeru_f0 = _remap(_z2_16x32(z2_bytes, 12, 13, 0xE0, 0xE2, 0xE4, 0xE6), m_pal0)
    fokkeru_f1 = _remap(_z2_16x32(z2_bytes, 12, 13, 0xE8, 0xEA, 0xEC, 0xEE), m_pal0)
    ra_f0 = _remap(_pad32(_z2_16x16(z2_bytes, 12, 13, 0x35, 0x37), 8), m_pal0)
    ra_f1 = ra_f0
    firerope_f0 = _remap(_pad32(_z2_16x16(z2_bytes, 12, 13, 0x0B, 0x0D), 8), m_pal0)
    firerope_f1 = firerope_f0
    gb0 = _pair(z2_bytes, 12, 0xF0)
    gb2 = _pair(z2_bytes, 12, 0xF2)
    gb4 = _pair(z2_bytes, 12, 0xF4)
    gb6 = _pair(z2_bytes, 12, 0xF6)
    gb8 = _pair(z2_bytes, 12, 0xF8)
    gba = _pair(z2_bytes, 12, 0xFA)
    gbot_48 = [
        gb0[y] + gb2[y] + gb4[y] + gb4[y][::-1] + gb2[y][::-1] + gb0[y][::-1] for y in range(16)
    ] + [
        gb6[y] + gb8[y] + gba[y] + gba[y][::-1] + gb8[y][::-1] + gb6[y][::-1] for y in range(16)
    ]
    giant_bot_f0 = _remap(resize_x(gbot_48, 16), m_ident)
    giant_bot_f1 = giant_bot_f0

    bank_gp_specs = [
        ('fokka',     0, fokka_f0,     fokka_f1),
        ('fokkeru',   0, fokkeru_f0,   fokkeru_f1),
        ('ra',        0, ra_f0,        ra_f1),
        ('firerope',  0, firerope_f0,  firerope_f1),
        ('giant_bot', 2, giant_bot_f0, giant_bot_f1),
    ]
    r0_villagers5, v4_pals, v4_maps, v4_cnt = make_r0_bank(bank_gp_specs)

    # --- R0 Bank 5 (1KB banks 30..31, R0=30): Bosses ---
    hh_48 = (
        _z2_16x32(z2_bytes, 8, 9, 0x1B, 0x1D, 0x1F, 0x21)
        + _z2_16x16(z2_bytes, 8, 9, 0x13, 0x15)
    )
    horsehead_f0 = _remap(_shrink_y(hh_48, 32), m_pal0)
    horsehead_f1 = horsehead_f0

    def _helm_48(leg_l: int, leg_r: int) -> list[str]:
        body = _z2_16x32(z2_bytes, 9, 9, 0x0F, 0x11, leg_l, leg_r)
        canvas = [list('0' * 16) for _ in range(16)] + [list(r) for r in body]
        head = _pair(z2_bytes, 9, 0x09)
        for y in range(16):
            for x in range(8):
                if head[y][x] != '0':
                    canvas[4 + y][4 + x] = head[y][x]
        return _shrink_y(_remap([''.join(r) for r in canvas], m_ident), 32)
    helmethead_f0 = _helm_48(0x13, 0x15)
    helmethead_f1 = _helm_48(0x17, 0x19)

    reb_tl = _z2_16x16(z2_bytes, 19, 19, 0x09, 0x0B)
    reb_tr = _z2_16x16(z2_bytes, 19, 19, 0x4D, 0x43)
    reb_bl = _z2_16x16(z2_bytes, 19, 19, 0x0D, 0x0F)
    reb_br = _z2_16x16(z2_bytes, 19, 19, 0x11, 0x13)
    def _reb_16(bob: int) -> list[str]:
        canvas = [list(reb_bl[y - 16] + reb_br[y - 16]) if y >= 16 else list('0' * 32) for y in range(32)]
        for y in range(16):
            dy = y + bob
            if dy < 16:
                for x in range(16):
                    if reb_tl[y][x] != '0':
                        canvas[dy][x] = reb_tl[y][x]
            for x in range(16):
                if reb_tr[y][x] != '0':
                    canvas[dy][16 + x] = reb_tr[y][x]
        return _remap(resize_x([''.join(r) for r in canvas], 16), m_ident)
    rebonack_f0 = _reb_16(0)
    rebonack_f1 = _reb_16(1)

    car_32_f0 = (
        [_z2_16x16(z2_bytes, 21, 21, 0x09, 0x0B)[y] + _z2_16x16(z2_bytes, 21, 21, 0x11, 0x13)[y] for y in range(16)]
        + [_z2_16x16(z2_bytes, 21, 21, 0x0D, 0x0F)[y] + _z2_16x16(z2_bytes, 21, 21, 0x15, 0x17)[y] for y in range(16)]
    )
    car_32_f1 = (
        [_z2_16x16(z2_bytes, 21, 21, 0x1F, 0x21)[y] + _z2_16x16(z2_bytes, 21, 21, 0x23, 0x25)[y] for y in range(16)]
        + [_z2_16x16(z2_bytes, 21, 21, 0x27, 0x29)[y] + _z2_16x16(z2_bytes, 21, 21, 0x2B, 0x2D)[y] for y in range(16)]
    )
    carock_f0 = _remap(resize_x(car_32_f0, 16), m_ident)
    carock_f1 = _remap(resize_x(car_32_f1, 16), m_ident)

    goo_48 = (
        [''.join(_pair(z2_bytes, 23, t)[y] for t in (0x09, 0x0B, 0x0D)) for y in range(16)]
        + [''.join(_pair(z2_bytes, 23, t)[y] for t in (0x0F, 0x11, 0x13)) for y in range(16)]
        + [''.join(_pair(z2_bytes, 23, t)[y] for t in (0x15, 0x17, 0x19)) for y in range(16)]
    )
    gooma_f0 = _remap(_shrink_y(resize_x(goo_48, 16), 32), m_pal0)
    gooma_f1 = gooma_f0

    def _tb_16(rows_tids: tuple[tuple[int, int], ...]) -> list[str]:
        half: list[str] = []
        for a, b in rows_tids:
            half.extend(_z2_16x16(z2_bytes, 13, 13, a, b))
        return _remap(_shrink_y(resize_x([r + r[::-1] for r in half], 16), 32), m_pal0)
    thunderbird_f0 = _tb_16(((0x11, 0x13), (0x17, 0x29), (0x1D, 0x1F), (0x21, 0x23)))
    thunderbird_f1 = _tb_16(((0x11, 0x13), (0x17, 0x2B), (0x1D, 0x1F), (0x25, 0x27)))

    bank_boss_specs = [
        ('horsehead',   0, horsehead_f0,   horsehead_f1),
        ('helmethead',  2, helmethead_f0,  helmethead_f1),
        ('rebonack',    2, rebonack_f0,    rebonack_f1),
        ('carock',      2, carock_f0,      carock_f1),
        ('gooma',       0, gooma_f0,       gooma_f1),
        ('thunderbird', 0, thunderbird_f0, thunderbird_f1),
    ]
    r0_villagers6, v5_pals, v5_maps, v5_cnt = make_r0_bank(bank_boss_specs)

    # 4. R0 Bank 1 (1KB banks 10..11): Shared $00..$1F + Game C Octoroks / Moas / Palace Plates ($20..$7F)
    m_octo = {'0': '0', '1': '2', '2': '3', '3': '1'}
    octo_f0 = _remap(_z2_16x16(z2_bytes, 8, 8, 0xBA, 0xBC), m_octo)
    octo_f1 = _shrink_rows(octo_f0, 14, 15)  # bobbing legs frame
    octo_med = _shrink_rows(octo_f0, 12, 12)
    octo_sml = _shrink_rows(octo_f0, 8, 8)

    moa_f0 = _remap(_z2_16x16(z2_bytes, 8, 8, 0xB6, 0xB8), m_ident)
    moa_f1 = [moa_f0[y] for y in range(1, 16)] + ['0' * 16]
    moa_med = _shrink_rows(moa_f0, 12, 12)
    moa_sml = _shrink_rows(moa_f0, 8, 8)

    clay_grids = [
        octo_f0, octo_f1, octo_med, octo_sml,
        moa_f0, moa_f1, moa_med, moa_sml,
    ]
    c_tiles, c_maps = _pack_grids_into_bank(clay_grids, 0x20, 0x80)
    r0_clay = bytearray(b'\x00' * 2048)
    for i, t in enumerate(shared_r0):
        r0_clay[i * 16 : (i + 1) * 16] = t
    for i, t in enumerate(c_tiles):
        r0_clay[(0x20 + i) * 16 : (0x21 + i) * 16] = t

    # 5. R0 Bank 2 (1KB banks 12..13): Title sprites (Shared $00..$1F + original $20..$7F)
    r0_title = bytearray(orig_spr[0:2048])
    for i, t in enumerate(shared_r0):
        r0_title[i * 16 : (i + 1) * 16] = t

    # 6. R1 Bank 0 (1KB banks 14..15): Barba ($80..$EF) + Score popups & Title sprites ($F0..$FF)
    barba_poses, barba_previews = _build_barba_full_and_down(z2_bytes)
    barba_order = ('walk0', 'walk1', 'windup', 'attack', 'downstab', 'crouch', 'catch_windup', 'catch_attack')
    b_tiles, b_maps = _pack_barba_poses(barba_poses, barba_order, 0x80, 0xEE)
    r1_barba = bytearray(b'\x00' * 2048)
    for i, t in enumerate(b_tiles):
        r1_barba[i * 16 : (i + 1) * 16] = t
    # Extract exact 8x16 XP bag (P-Bag) from Z2 CHR bank 2 ($72/$73) — Z2 Pal 1 ($16/$27/$30) matches Duck Hunt Pal 1
    pbag_rows = source_pair(z2_bytes, 0x72, 2)
    r1_barba[0x6E * 16 : 0x6F * 16] = encode_tile(pbag_rows[0:8])
    r1_barba[0x6F * 16 : 0x70 * 16] = encode_tile(pbag_rows[8:16])
    r1_barba[0x70 * 16 : 0x80 * 16] = orig_spr[0xF0 * 16 : 0x100 * 16]

    # 7. R1 Bank 1 (1KB banks 16..17): Villainous Link ($80..$EF) + Score popups ($F0..$FF)
    link_grids = _build_villainous_link(z2_bytes)
    l_tiles, l_maps = _pack_grids_into_bank(link_grids, 0x80, 0xF0)
    r1_link = bytearray(b'\x00' * 2048)
    for i, t in enumerate(l_tiles):
        r1_link[i * 16 : (i + 1) * 16] = t
    r1_link[0x70 * 16 : 0x80 * 16] = orig_spr[0xF0 * 16 : 0x100 * 16]

    # 8. Assemble 64KB CHR-ROM (64 x 1KB banks, well under 128KB limit)
    chr32 = bytearray(b'\x00' * (64 * 1024))
    chr32[0 * 1024 : 4 * 1024] = game_bg
    chr32[4 * 1024 : 8 * 1024] = title_bg
    chr32[8 * 1024 : 10 * 1024] = r0_villagers
    chr32[10 * 1024 : 12 * 1024] = r0_clay
    chr32[12 * 1024 : 14 * 1024] = r0_title
    chr32[14 * 1024 : 16 * 1024] = r1_barba
    chr32[16 * 1024 : 18 * 1024] = r1_link
    chr32[18 * 1024 : 22 * 1024] = forest_bg
    chr32[22 * 1024 : 24 * 1024] = r0_villagers2
    chr32[24 * 1024 : 26 * 1024] = r0_villagers3
    chr32[26 * 1024 : 28 * 1024] = r0_villagers4
    chr32[28 * 1024 : 30 * 1024] = r0_villagers5
    chr32[30 * 1024 : 32 * 1024] = r0_villagers6
    chr32[32 * 1024 : 36 * 1024] = grass_bg
    chr32[36 * 1024 : 40 * 1024] = desert_bg

    bank_defs = [
        (8,  'r0_villagers',  'Shared / Overworld', bank_shared_specs),
        (22, 'r0_villagers2', 'West Hyrule',        bank_west_specs),
        (24, 'r0_villagers3', 'East Hyrule',        bank_east_specs),
        (26, 'r0_villagers4', 'Palaces 1-6',        bank_palace_specs),
        (28, 'r0_villagers5', 'Great Palace',       bank_gp_specs),
        (30, 'r0_villagers6', 'Bosses',             bank_boss_specs),
    ]
    villager_r0_banks: list[int] = []
    villager_bank_idx: list[int] = []
    bank_starts: list[int] = []
    bank_counts: list[int] = []
    offset = 0
    for bi, (r0_id, _, _, specs) in enumerate(bank_defs):
        bank_starts.append(offset)
        bank_counts.append(len(specs))
        villager_r0_banks.extend([r0_id] * len(specs))
        villager_bank_idx.extend([bi] * len(specs))
        offset += len(specs)

    return {
        'chr': bytes(chr32),
        'villager_pals': v0_pals + v1_pals + v2_pals + v3_pals + v4_pals + v5_pals,
        'villager_maps': v0_maps + v1_maps + v2_maps + v3_maps + v4_maps + v5_maps,
        'villager_r0_banks': villager_r0_banks,
        'villager_bank_idx': villager_bank_idx,
        'bank_starts': bank_starts,
        'bank_counts': bank_counts,
        'clay_pals': [0, 2],          # Octorok=Pal0, Moa=Pal2
        'clay_maps': c_maps,          # 8 entries (2 targets x 4 scales/frames), each 4 tile IDs (2x2)
        'barba_maps': b_maps,         # 8 entries, each list of (tid, dx, dy)
        'link_maps': l_maps,          # 2 entries (laugh0, laugh1), each 8 tile IDs (2x4)
        'tile_counts': {
            'villagers': v0_cnt,
            'villagers2': v1_cnt,
            'villagers3': v2_cnt,
            'villagers4': v3_cnt,
            'villagers5': v4_cnt,
            'villagers6': v5_cnt,
            'clay': len(c_tiles),
            'barba': len(b_tiles),
            'link': len(l_tiles),
        },
        'preview_grids': {
            'villagers': bank_shared_specs,
            'villagers2': bank_west_specs,
            'villagers3': bank_east_specs,
            'villagers4': bank_palace_specs,
            'villagers5': bank_gp_specs,
            'villagers6': bank_boss_specs,
            'villager_banks': bank_defs,
            'clay': [('octorok', 0, octo_f0, octo_f1), ('moa', 2, moa_f0, moa_f1)],
            'barba': [(n, 1, barba_previews[n]) for n in barba_order],
            'link': [('link0', 3, link_grids[0]), ('link1', 3, link_grids[1])],
        },
    }


def write_preview(art: dict, out_path: Path) -> Path:
    """Render an RGB preview sheet of all Villager Hunt sprites to out_path."""
    pals = [
        [(20, 22, 28), (248, 248, 248), (216, 40, 0), (16, 16, 16)],    # Pal 0
        [(20, 22, 28), (216, 40, 0), (252, 152, 56), (248, 248, 248)],  # Pal 1
        [(20, 22, 28), (16, 16, 16), (32, 88, 204), (252, 212, 168)],   # Pal 2
        [(20, 22, 28), (16, 16, 16), (0, 168, 68), (252, 212, 168)],    # Pal 3
    ]
    rows_px = [[pals[0][0]] * 500 for _ in range(120)]

    def blit(grid: list[str], pal_i: int, ox: int, oy: int) -> None:
        pal = pals[pal_i]
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch != '0':
                    rows_px[oy + y][ox + x] = pal[int(ch)]

    x = 4
    for _, pi, f0, f1 in art['preview_grids']['villagers']:
        blit(f0, pi, x, 4)
        blit(f1, pi, x + 18, 4)
        x += 40
    for _, pi, f0, f1 in art['preview_grids']['clay']:
        blit(f0, pi, x, 4)
        x += 20
    # Crosshair & Fireball on row 2
    ch16 = [
        CROSSHAIR_TILES[0][y] + CROSSHAIR_TILES[1][y] for y in range(8)
    ] + [
        CROSSHAIR_TILES[2][y] + CROSSHAIR_TILES[3][y] for y in range(8)
    ]
    blit(ch16, 1, 4, 48)
    for fi, fb in enumerate(FIREBALL_FRAMES):
        blit(list(fb), 1, 28 + fi * 20, 48)
    bx = 100
    for _, pi, grid in art['preview_grids']['barba']:
        blit(grid, pi, bx, 48)
        bx += 60
    for _, pi, grid in art['preview_grids']['link']:
        blit(grid, pi, bx, 48)
        bx += 20

    write_png(out_path, rows_px, 3)
    return out_path
