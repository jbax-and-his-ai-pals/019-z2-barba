"""Build-time Z2-derived CHR & metasprite compiler for Barba Man 2 (Mega Man 2).

All Zelda II pixels are extracted at build time from ``roms/z2.nes`` via
``boss_art`` and ``nes`` (no original game pixels are committed).
"""
from __future__ import annotations

from pathlib import Path

from boss_art import compile_lava_link, resize_x, source_head, source_pair
from nes import decode_tile, encode_tile, load_source, write_png


# Barba gameplay palette (Pal 0 when Mega Buster is equipped):
#   0 = transparent, 1 = $16 crimson red, 2 = $27 amber-orange, 3 = $30 cream-white
BARBA_PALETTE = [(20, 22, 28), (194, 43, 25), (255, 168, 57), (255, 243, 205)]

# Stage Select BG Palette 0:
#   0 = $0F black, 1 = $20 white, 2 = $11 medium blue, 3 = $2C cyan
STAGE_SELECT_PAL0 = [(12, 12, 16), (248, 248, 248), (24, 68, 180), (88, 208, 248)]

# Villainous Link Wily-cockpit palette (Pal 1):
#   0 = transparent, 1 = $0F black outline, 2 = $30 white/silver, 3 = $38 pale skin/gold
COCKPIT_PAL1 = [(20, 22, 28), (12, 12, 16), (248, 248, 248), (248, 216, 144)]

# Gameplay CHR slots in Bank 0 $9000 ($00..$8F) exclusively owned by Mega Man
# (verified collision-free against all fid > $21 metasprites and $87..$8B HUD bars).
PLAYER_TILE_POOL: list[int] = [
    t for t in range(0x83)
    if t not in {0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x6B, 0x74, 0x75, 0x76}
]

# Mega Buster fireball tiles (frame $22)
FIREBALL_TILE_HEAD = 0x69
FIREBALL_TILE_TAIL = 0x6A

# Bank 10 free layout IDs ($A4..$FF are $FF in vanilla Bank 10)
FIREBALL_LAYOUT_ID = 0xA4
FIRST_PLAYER_LAYOUT_ID = 0xA5

# Vanilla Mega Man 2 player frames ($00..$21) -> pose names
FRAME_POSE_MAP: dict[int, str] = {
    0x00: 'walk0',
    0x01: 'walk0',
    0x02: 'walk1',
    0x03: 'tiptoe',
    0x04: 'idle',
    0x05: 'blink',
    0x06: 'idle',
    0x07: 'jump',
    0x08: 'hurt',
    0x09: 'shoot_idle',
    0x0A: 'shoot_walk0',
    0x0B: 'shoot_walk1',
    0x0C: 'shoot_walk2',
    0x0D: 'throw_walk0',
    0x0E: 'throw_walk1',
    0x0F: 'throw_walk2',
    0x10: 'throw_idle',
    0x11: 'throw_blink',
    0x12: 'throw_idle',
    0x13: 'shoot_jump',
    0x14: 'shoot_jump',
    0x15: 'climb0',
    0x16: 'climb1',
    0x17: 'climb_top',
    0x18: 'flash',
    0x19: 'shoot_idle',
    0x1A: 'throw_jump',
    0x1B: 'beam',
    0x1C: 'land1',
    0x1D: 'land2',
    0x1E: 'hurt',
    0x1F: 'climb_shoot',
    0x20: 'shoot_walk1',
    0x21: 'climb_top_r',
}


def _shrink_y(rows: list[str], target_h: int) -> list[str]:
    old_h = len(rows)
    return [rows[min(old_h - 1, (y * old_h + target_h // 2) // target_h)] for y in range(target_h)]


def _blit(canvas: list[list[str]], rows: list[str], ox: int, oy: int) -> None:
    h, w = len(canvas), len(canvas[0])
    for iy, row in enumerate(rows):
        ny = oy + iy
        if 0 <= ny < h:
            for ix, ch in enumerate(row):
                nx = ox + ix
                if ch != '0' and 0 <= nx < w:
                    canvas[ny][nx] = ch


def _make_barba_32x40_poses(z2_bytes: bytes) -> dict[str, list[str]]:
    """Build 32x40 LEFT-facing full-body Barba poses (plus 8x40 beam) from Z2 boss tiles.

    Uses the full native 32x16 Barba head (no horizontal squishing) paired with
    24px of serpentine neck/body, back wing/fin, and claws/feet at rows 36..39.
    """
    heads = {
        jaw: source_head(z2_bytes, jaw)  # native 32x16
        for jaw in ('closed', 'half', 'open')
    }
    neck = [''.join((source_pair(z2_bytes, 0xA0)[y], source_pair(z2_bytes, 0xA2)[y])) for y in range(16)]

    # Claw/foot rows (4 rows x 16px) at bottom of dragon body (rows 36..39)
    claws = {
        'stand': [
            '0001110000111000',
            '0012210001221000',
            '0331100033110000',
            '0000000000000000',
        ],
        'walk0': [
            '0011100000011100',
            '0122100000012210',
            '3311000000331100',
            '0000000000000000',
        ],
        'walk1': [
            '0001110001100000',
            '0012210001210000',
            '0331100003300000',
            '0000000000000000',
        ],
        'walk2': [
            '0000111000111000',
            '0001221000122100',
            '0033110003311000',
            '0000000000000000',
        ],
        'jump': [
            '0011100011100000',
            '0122000122000000',
            '3310003310000000',
            '0000000000000000',
        ],
        'hurt': [
            '0111000000011100',
            '1220000000002210',
            '3100000000000133',
            '0000000000000000',
        ],
    }

    wing = [
        '001100',
        '012210',
        '123210',
        '122100',
        '011000',
        '010000',
    ]

    def compose(
        jaw: str = 'closed',
        *,
        head_x: int = 0,
        head_y: int = 0,
        neck_x: int = 12,
        sway_phase: int = 0,
        foot: str = 'stand',
        blink: bool = False,
        flame_muzzle: bool = False,
        dorsal_arm: bool = False,
    ) -> list[str]:
        canvas = [['0'] * 32 for _ in range(40)]
        # Serpentine neck from head_y+13 down to row 36
        for y in range(head_y + 13, 37):
            sway = (0, -1, 0, 1)[((y - head_y) // 5 + sway_phase) % 4]
            row = neck[(y - head_y - 13) % 16]
            _blit(canvas, [row], neck_x + sway, y)
        # Dragon wing/fin accent on back (right side)
        _blit(canvas, wing, min(26, neck_x + 12), max(12, head_y + 15))
        # Claws at rows 36..39
        _blit(canvas, claws[foot], max(8, neck_x - 1), 36)
        # Full native 32x16 head on top
        head_rows = [list(r) for r in heads[jaw]]
        if blink:
            for ry in range(3, 8):
                for rx in range(15, 23):
                    if head_rows[ry][rx] == '3':
                        head_rows[ry][rx] = '1'
        _blit(canvas, [''.join(r) for r in head_rows], head_x, head_y)
        if flame_muzzle:
            _blit(canvas, ['32', '21'], max(0, head_x), head_y + 8)
        if dorsal_arm:
            _blit(canvas, ['0122', '1233', '0110'], max(4, neck_x - 3), head_y + 20)
        return [''.join(r) for r in canvas]

    poses: dict[str, list[str]] = {
        'idle':        compose('closed', head_x=0, head_y=0, neck_x=12, sway_phase=0, foot='stand'),
        'blink':       compose('closed', head_x=0, head_y=0, neck_x=12, sway_phase=0, foot='stand', blink=True),
        'tiptoe':      compose('closed', head_x=0, head_y=0, neck_x=12, sway_phase=1, foot='stand'),
        'walk0':       compose('closed', head_x=0, head_y=0, neck_x=12, sway_phase=0, foot='walk0'),
        'walk1':       compose('closed', head_x=0, head_y=0, neck_x=12, sway_phase=1, foot='walk1'),
        'walk2':       compose('closed', head_x=0, head_y=0, neck_x=12, sway_phase=2, foot='walk2'),
        'jump':        compose('closed', head_x=0, head_y=0, neck_x=12, sway_phase=2, foot='jump'),
        'hurt':        compose('half',   head_x=0, head_y=0, neck_x=12, sway_phase=3, foot='hurt'),
        'shoot_idle':  compose('open',   head_x=0, head_y=0, neck_x=12, sway_phase=0, foot='stand', flame_muzzle=True),
        'shoot_walk0': compose('open',   head_x=0, head_y=0, neck_x=12, sway_phase=0, foot='walk0', flame_muzzle=True),
        'shoot_walk1': compose('open',   head_x=0, head_y=0, neck_x=12, sway_phase=1, foot='walk1', flame_muzzle=True),
        'shoot_walk2': compose('open',   head_x=0, head_y=0, neck_x=12, sway_phase=2, foot='walk2', flame_muzzle=True),
        'shoot_jump':  compose('open',   head_x=0, head_y=0, neck_x=12, sway_phase=2, foot='jump',  flame_muzzle=True),
        'throw_idle':  compose('half',   head_x=0, head_y=0, neck_x=12, sway_phase=0, foot='stand', dorsal_arm=True),
        'throw_blink': compose('half',   head_x=0, head_y=0, neck_x=12, sway_phase=0, foot='stand', blink=True, dorsal_arm=True),
        'throw_walk0': compose('half',   head_x=0, head_y=0, neck_x=12, sway_phase=0, foot='walk0', dorsal_arm=True),
        'throw_walk1': compose('half',   head_x=0, head_y=0, neck_x=12, sway_phase=1, foot='walk1', dorsal_arm=True),
        'throw_walk2': compose('half',   head_x=0, head_y=0, neck_x=12, sway_phase=2, foot='walk2', dorsal_arm=True),
        'throw_jump':  compose('half',   head_x=0, head_y=0, neck_x=12, sway_phase=2, foot='jump',  dorsal_arm=True),
    }

    # Climbing poses (compact vertical dragon silhouette gripping ladder)
    poses['climb0'] = compose('closed', head_x=0, head_y=0, neck_x=12, sway_phase=0, foot='walk0', dorsal_arm=True)
    poses['climb1'] = compose('closed', head_x=0, head_y=0, neck_x=12, sway_phase=2, foot='walk2', dorsal_arm=True)
    poses['climb_top'] = compose('closed', head_x=0, head_y=0, neck_x=12, sway_phase=1, foot='jump')
    poses['climb_top_r'] = [r[::-1] for r in poses['climb_top']]
    poses['climb_shoot'] = compose('open', head_x=0, head_y=0, neck_x=12, sway_phase=1, foot='walk1', flame_muzzle=True)

    # Hurt flash ($18): bright cream-white silhouette of idle
    poses['flash'] = [''.join('3' if c != '0' else '0' for c in row) for row in poses['idle']]

    # Teleport landing ($1C, $1D) and 8x40 flame beam ($1B)
    land1 = [['0'] * 32 for _ in range(40)]
    _blit(land1, ['00123210', '01233321', '12333332', '01233321', '00123210'], 12, 34)
    poses['land2'] = [''.join(r) for r in land1]
    _blit(land1, _shrink_y(heads['open'], 12), 0, 22)
    poses['land1'] = [''.join(r) for r in land1]

    beam_8x8 = [
        '00123210',
        '01233321',
        '01233321',
        '12333332',
        '12333332',
        '01233321',
        '01233321',
        '00123210',
    ]
    poses['beam'] = beam_8x8 * 5  # 40 rows x 8 cols
    return poses


def _split_32x40_nonempty(rows: list[str]) -> list[tuple[int, int, bytes]]:
    """Return list of (dy, dx, 16B_tile) for non-empty 8x8 tiles in a 32x40 canvas.

    Bottom row (ty=4) sits at dy=+4 so feet (y=36..39) touch Y+12, matching
    Mega Man's ground contact while extending 16px higher (dy=-28..+4).
    """
    blank_tile = b'\x00' * 16
    out: list[tuple[int, int, bytes]] = []
    for ty in range(5):
        dy = -28 + ty * 8
        for tx in range(4):
            dx = -16 + tx * 8
            trows = [rows[ty * 8 + y][tx * 8 : (tx + 1) * 8] for y in range(8)]
            tbytes = encode_tile(trows)
            if tbytes != blank_tile:
                out.append((dy, dx, tbytes))
    return out


def compile_barba_gameplay(
    z2_bytes: bytes,
) -> tuple[dict[int, bytes], dict[int, bytes], dict[int, bytes], dict[str, list[str]]]:
    """Compile Barba gameplay CHR tiles ($00..$82 pool), Bank 10 layouts ($A5+), and frames ($00..$21).

    Returns ``(chr_tiles, bank10_metasprites, custom_layouts, poses)``.
    """
    poses = _make_barba_32x40_poses(z2_bytes)
    blank_tile = b'\x00' * 16
    tile_to_id: dict[bytes, int] = {}
    chr_tiles: dict[int, bytes] = {}
    pool_idx = 0

    def alloc_tile(tile_bytes: bytes) -> int:
        nonlocal pool_idx
        if tile_bytes in tile_to_id:
            return tile_to_id[tile_bytes]
        if pool_idx >= len(PLAYER_TILE_POOL):
            raise RuntimeError(f'Barba gameplay CHR exceeded {len(PLAYER_TILE_POOL)} tiles')
        tid = PLAYER_TILE_POOL[pool_idx]
        pool_idx += 1
        tile_to_id[tile_bytes] = tid
        chr_tiles[tid] = tile_bytes
        return tid

    beam_tile = encode_tile(poses['beam'][:8])
    beam_tid = alloc_tile(beam_tile)

    layout_coords_to_id: dict[tuple[tuple[int, int], ...], int] = {}
    custom_layouts: dict[int, bytes] = {}
    next_layout_id = FIRST_PLAYER_LAYOUT_ID

    def alloc_layout(coords: tuple[tuple[int, int], ...]) -> int:
        nonlocal next_layout_id
        if coords in layout_coords_to_id:
            return layout_coords_to_id[coords]
        lid = next_layout_id
        assert lid <= 0xFF, 'Bank 10 layout IDs exhausted'
        next_layout_id += 1
        layout_coords_to_id[coords] = lid
        buf = bytearray([0x00, 0x00])
        for dy, dx in coords:
            buf.extend((dy & 0xFF, dx & 0xFF))
        custom_layouts[lid] = bytes(buf)
        return lid

    pose_metasprites: dict[str, bytes] = {}
    for pname, rows in poses.items():
        if pname == 'beam':
            coords = tuple((-28 + i * 8, -4) for i in range(5))
            lid = alloc_layout(coords)
            buf = bytearray([5, lid])
            for _ in range(5):
                buf.extend((beam_tid, 0))
            pose_metasprites[pname] = bytes(buf)
            continue

        if pname == 'climb_top_r':
            # Reuse climb_top's tiles with H-flip (attr=0x40) and mirrored dx = -8 - dx
            pieces = _split_32x40_nonempty(poses['climb_top'])
            coords = tuple((dy, (-8 - dx)) for dy, dx, _ in pieces)
            lid = alloc_layout(coords)
            buf = bytearray([len(pieces), lid])
            for _, _, tbytes in pieces:
                tid = alloc_tile(tbytes)
                buf.extend((tid, 0x40))
            pose_metasprites[pname] = bytes(buf)
            continue

        pieces = _split_32x40_nonempty(rows)
        coords = tuple((dy, dx) for dy, dx, _ in pieces)
        lid = alloc_layout(coords)
        attr = 1 if pname == 'flash' else 0
        buf = bytearray([len(pieces), lid])
        for _, _, tbytes in pieces:
            tid = alloc_tile(tbytes)
            buf.extend((tid, attr))
        pose_metasprites[pname] = bytes(buf)

    # Fill remaining unused player tiles with 0 so no stray Mega Man fragments remain
    while pool_idx < len(PLAYER_TILE_POOL):
        chr_tiles[PLAYER_TILE_POOL[pool_idx]] = blank_tile
        pool_idx += 1

    frame_data = {fid: pose_metasprites[pname] for fid, pname in FRAME_POSE_MAP.items()}
    return chr_tiles, frame_data, custom_layouts, poses


def compile_barba_fireball() -> tuple[dict[int, bytes], bytes, bytes]:
    """Build 16x8 directional Barba flame-crowned fireball (tiles $69-$6A, Frame $22, Layout $A3).

    Uses Pal 0 (attr=0 -> $0F, $16 red, $27 orange, $30 cream-white) and faces LEFT
    when unflipped (head at dx=-12, trailing flame at dx=-4); MM2 automatically flips
    both tiles and X offsets when facing RIGHT.
    """
    head_rows = [
        '00011100',
        '01222110',
        '12333210',
        '13333321',
        '13333321',
        '12333210',
        '01222110',
        '00011100',
    ]
    tail_rows = [
        '00100000',
        '01210100',
        '22112100',
        '32211110',
        '22121000',
        '12211100',
        '01100000',
        '00001000',
    ]
    tiles = {
        FIREBALL_TILE_HEAD: encode_tile(head_rows),
        FIREBALL_TILE_TAIL: encode_tile(tail_rows),
    }
    # Layout $A3: header (0,0) + 2 entries (dy, dx): (-12, -4) head, (-4, -4) tail
    layout_a3 = bytes([0x00, 0x00, 0xFC, 0xF4, 0xFC, 0xFC])  # dy=-4 ($FC), dx=-12 ($F4), dx=-4 ($FC)
    frame_22 = bytes([2, FIREBALL_LAYOUT_ID, FIREBALL_TILE_HEAD, 0x00, FIREBALL_TILE_TAIL, 0x00])
    return tiles, layout_a3, frame_22


def _extract_link_rows(z2_bytes: bytes) -> tuple[list[str], list[str], list[str], list[str]]:
    """Extract Villainous Link 16x16 heads (closed, open) and 16x16 tunic from Z2 via boss_art."""
    pairs = compile_lava_link(z2_bytes)

    def decode_16x16(pair_l: int, pair_r: int) -> list[str]:
        dl = decode_tile(pairs[pair_l][:16]) + decode_tile(pairs[pair_l][16:])
        dr = decode_tile(pairs[pair_r][:16]) + decode_tile(pairs[pair_r][16:])
        return [''.join(map(str, dl[y] + dr[y])) for y in range(16)]

    head_closed = decode_16x16(0x14, 0x16)
    head_open = decode_16x16(0x28, 0x2A)
    tunic = decode_16x16(0xA0, 0xA2)
    sword_beam = decode_16x16(0x52, 0x52)
    return head_closed, head_open, tunic, sword_beam


def _encode_grid_tiles(rows: list[str], cols: int, tile_rows: int) -> list[bytes]:
    out: list[bytes] = []
    for ty in range(tile_rows):
        for tx in range(cols):
            trows = [rows[ty * 8 + y][tx * 8 : (tx + 1) * 8] for y in range(8)]
            out.append(encode_tile(trows))
    return out


def compile_villain_link(z2_bytes: bytes) -> dict[str, object]:
    """Compile all Villainous Link portraits, UFO pilot, Wily Machine cockpit, and surrender sprites."""
    head_closed, head_open, tunic, _ = _extract_link_rows(z2_bytes)

    # ------------------------------------------------------------------
    # 1. Stage Select center 32x32 portrait (Bank 8 $8F00..$8FFF, tiles $70..$7F)
    #    Palette: 0=$0F black, 1=$20 white, 2=$11 medium blue, 3=$2C cyan
    # ------------------------------------------------------------------
    # Scale 16x16 head -> 22x22 and center inside a 32x32 framed portrait
    # Black outer frame -> cyan ring ('3') -> medium blue inner circle ('2') so black hair/outline ('0') pops!
    ss_canvas = [['0'] * 32 for _ in range(32)]
    for y in range(2, 30):
        for x in range(2, 30):
            dist2 = (x - 15.5) ** 2 + (y - 15.5) ** 2
            if dist2 <= 13.5 ** 2:
                ss_canvas[y][x] = '3'
            if dist2 <= 11.8 ** 2:
                ss_canvas[y][x] = '2'
    # Map Z2 Link indices (1=hair/outline, 2=skin, 3=cap/tunic) -> Stage Select palette (0=black, 1=white, 3=cyan)
    ss_map = {'0': '0', '1': '0', '2': '1', '3': '3'}
    head_22 = _shrink_y(resize_x(head_closed, 22), 22)
    for y in range(22):
        for x in range(22):
            if head_22[y][x] != '0':
                ss_canvas[3 + y][5 + x] = ss_map[head_22[y][x]]
    # Add fierce glowing eyes + small Triforce emblem at bottom-right
    ss_canvas[10][9] = '1'
    ss_canvas[10][12] = '1'
    # Tunic shoulders (rows 24..28)
    for y in range(24, 29):
        for x in range(8, 24):
            if (x - 15.5) ** 2 + (y - 15.5) ** 2 <= 11.0 ** 2:
                ss_canvas[y][x] = '3' if y % 2 == 0 else '1'
    ss_portrait_bytes = b''.join(_encode_grid_tiles([''.join(r) for r in ss_canvas], 4, 4))
    assert len(ss_portrait_bytes) == 16 * 16

    # ------------------------------------------------------------------
    # 2. Cockpit / UFO Pilot 24x16 (used in Bank 6 $9400..$947F AND Bank 5 $95A0..$968F)
    #    Palette (Pal 1): 0=transparent, 1=$0F black, 2=$30 white/silver, 3=$38 gold/skin
    # ------------------------------------------------------------------
    # Map Link indices (1=outline/hair, 2=skin, 3=cap/tunic) -> (1=black, 2=white, 3=skin/gold)
    pilot_map = {'0': '0', '1': '1', '2': '3', '3': '2'}

    def make_pilot_24x16(head16: list[str], *, hand_up: bool = False) -> list[bytes]:
        grid = [['0'] * 24 for _ in range(16)]
        # Blit 16x16 Link head (shifted slightly right so trailing pointed cap fills x=14..22)
        for y in range(16):
            for x in range(16):
                ch = head16[y][x]
                if ch != '0':
                    grid[y][2 + x] = pilot_map[ch]
        # Extended pointed Hylian cap tip sweeping right
        cap_tip = [
            (2, 16, '1'), (2, 17, '2'), (2, 18, '2'), (2, 19, '1'),
            (3, 17, '2'), (3, 18, '2'), (3, 19, '2'), (3, 20, '1'),
            (4, 18, '1'), (4, 19, '2'), (4, 20, '2'), (4, 21, '1'),
            (5, 19, '1'), (5, 20, '1'),
        ]
        for py, px, c in cap_tip:
            grid[py][px] = c
        # Collar & shoulders at bottom (rows 13..15)
        for x in range(4, 20):
            grid[14][x] = '2' if 6 <= x <= 17 else '1'
            grid[15][x] = '1' if x in (4, 19) else ('3' if 9 <= x <= 14 else '2')
        if hand_up:
            # Raised fist/controls on left side (x=1..4, y=11..15)
            for y in range(11, 15):
                grid[y][1] = '1'
                grid[y][2] = '3'
                grid[y][3] = '1'
        return _encode_grid_tiles([''.join(r) for r in grid], 3, 2)

    pilot_closed_tiles = make_pilot_24x16(head_closed, hand_up=False)
    pilot_open_tiles = make_pilot_24x16(head_open, hand_up=True)

    # ------------------------------------------------------------------
    # 3. Bank 6 $9500..$952F ($50..$52): UFO Dome Silhouette (24x8 half, mirrored!)
    # ------------------------------------------------------------------
    ufo_sil = [['0'] * 24 for _ in range(8)]
    # Pointed Hylian cap silhouette centered inside UFO dome (mirrored at x=23 -> x=24)
    for y in range(8):
        for x in range(10, 24):
            if y >= 2 and x >= 12 + (5 - min(5, y)):
                ufo_sil[y][x] = '2' if y < 6 else '3'
            if y == 6 and x >= 14:
                ufo_sil[y][x] = '1'
    ufo_sil_tiles = b''.join(_encode_grid_tiles([''.join(r) for r in ufo_sil], 3, 1))

    # ------------------------------------------------------------------
    # 4. Bank 6 $95C0..$968F ($5C..$68): Skull Castle 32x32 Bust (left half, H-mirrored!)
    #    Frame 6 uses:
    #      row 0: $5C, $5D (mirrored) -> head top / pointed cap
    #      row 1: $5E, $5F (mirrored) -> face / glowing eyes
    #      row 2: $60, $61 (mirrored) -> collar / Triforce
    #      row 3: $62, $63 (mirrored) -> tunic / belt
    #    Frame 8..10: $64..$68 (small emblem/cursor -> Triforce!)
    # ------------------------------------------------------------------
    bust_half = [['0'] * 16 for _ in range(32)]
    # Front-facing symmetric half-bust (x=0..15 is left half, x=15 is center!)
    bust_rows_left = [
        '0000000000000122',
        '0000000000012222',
        '0000000000122222',
        '0000000001222222',
        '0000000012222222',
        '0000000122211111',
        '0000001221113333',
        '0000001111333333',
        '0000001331331133',
        '0000001331312133',
        '0000001333333333',
        '0000000133333313',
        '0000000133333111',
        '0000000013333333',
        '0000000001133333',
        '0000000122211111',
        # rows 16..31: tunic + Triforce crest + belt (Pal 2: 1=dark, 2=light, 3=accent)
        '0000001222222222',
        '0000012222222322',
        '0000122222223332',
        '0000122222233333',
        '0001222222222222',
        '0001222222322322',
        '0001222223333333',
        '0001221222222222',
        '0000111111111111',
        '0000001333333333',
        '0000001222222222',
        '0000001222222222',
        '0000001222122222',
        '0000001221012222',
        '0000001110001111',
        '0000000000000000',
    ]
    bust_tiles = b''.join(_encode_grid_tiles(bust_rows_left, 2, 4))
    # $64..$68 (5 tiles: small Triforce / shield crest)
    triforce_8x8 = [
        '00000000',
        '00000001',
        '00000013',
        '00000133',
        '00001222',
        '00013133',
        '00133333',
        '00000000',
    ]
    triforce_half = encode_tile(triforce_8x8)
    small_emblem_tiles = triforce_half * 5

    # ------------------------------------------------------------------
    # 5. Wily Machine 2 Triforce Crest (Bank 5 $94B0..$94DF -> tiles $AB, $AC, $AD)
    # ------------------------------------------------------------------
    wm_crest = [
        encode_tile([
            '00000000',
            '00033000',
            '00322300',
            '03222230',
            '33333333',
            '00000000',
            '00000000',
            '00000000',
        ]),
        encode_tile([
            '00000000',
            '00000000',
            '00000000',
            '00000003',
            '00000032',
            '00000322',
            '00003222',
            '00033333',
        ]),
        encode_tile([
            '00000000',
            '00000000',
            '00000000',
            '30000000',
            '23000000',
            '22300000',
            '22230000',
            '33333000',
        ]),
    ]

    # ------------------------------------------------------------------
    # 6. Wily Stage 6 Surrender / Kneeling (Bank 8 $BA10..$BB6F -> Frame $D0..$D2)
    #    Frame $D0: startled jump ($A1..$A9 = 9 tiles)
    #    Frame $D1: kneeling 1 ($AA..$B0 = 7 tiles)
    #    Frame $D2: kneeling 2 ($B1..$B6 = 6 tiles)
    # ------------------------------------------------------------------
    # Frame $D0 sprite layout:
    #   (-12,-12)=$A1, (-4,-12)=$A2, (4,-12)=$A3
    #   (-12,-4)=$A4,  (-4,-4)=$A5,  (4,-4)=$A6
    #   (-12,+4)=$A7,  (-4,+4)=$A8,  (4,+4)=$A9
    #   Notice $A7 & $A9 use attr=3 (green boots), rest use attr=1 (Pal 1)!
    d0_grid = [['0'] * 24 for _ in range(24)]
    for y in range(16):
        for x in range(16):
            ch = head_open[y][x]
            if ch != '0':
                d0_grid[y][2 + x] = pilot_map[ch]
    # Arms thrown up + tunic + boots
    for x in range(6, 18):
        d0_grid[16][x] = '2' if 7 <= x <= 16 else '1'
        d0_grid[17][x] = '2' if 7 <= x <= 16 else '1'
        d0_grid[18][x] = '1'
    _blit(d0_grid, ['110', '331', '011'], 1, 10)
    _blit(d0_grid, ['011', '133', '110'], 19, 10)
    _blit(d0_grid, ['131', '331', '110'], 2, 19)
    _blit(d0_grid, ['131', '133', '011'], 17, 19)
    d0_tiles = b''.join(_encode_grid_tiles([''.join(r) for r in d0_grid], 3, 3))

    # Frame $D1 ($AA..$B0) and $D2 ($B1..$B6): 24x16 kneeling in defeat
    #   (-13,-4)=$AA, (-5,-4)=$AB, (3,-4)=$AC
    #   (-16,+4)=$AD, (-8,+4)=$AE, (0,+4)=$AF, (8,+4)=$B0
    def make_kneel(head16: list[str], bow_dy: int) -> list[bytes]:
        g = [['0'] * 32 for _ in range(16)]
        for y in range(16):
            for x in range(16):
                ch = head16[y][x]
                if ch != '0' and y + bow_dy < 16:
                    g[y + bow_dy][3 + x] = pilot_map[ch]
        # Kneeling tunic + hands on floor + green boot at right ($B0 at x=24..31, y=8..15)
        for x in range(2, 24):
            g[14][x] = '2' if 6 <= x <= 21 else '3'
            g[15][x] = '1'
        for x in range(24, 30):
            g[13][x] = '3'
            g[14][x] = '3'
            g[15][x] = '1'
        # Split top 24px ($AA..$AC at x=3..26) + bottom 32px ($AD..$B0 at x=0..31)
        top_rows = [''.join(r[3:27]) for r in g[:8]]
        bot_rows = [''.join(r[0:32]) for r in g[8:16]]
        return _encode_grid_tiles(top_rows, 3, 1) + _encode_grid_tiles(bot_rows, 4, 1)

    d1_tiles = make_kneel(head_closed, bow_dy=0)
    d2_tiles = make_kneel(head_open, bow_dy=1)

    return {
        'ss_portrait': ss_portrait_bytes,                       # Bank 8 $8F00 (16 tiles)
        'b6_ufo_pilot_closed': b''.join(pilot_closed_tiles),    # Bank 6 $9400 (6 tiles: $40..$45)
        'b6_ufo_pilot_open': b''.join(pilot_open_tiles[:2]),    # Bank 6 $9460 (2 tiles: $46..$47)
        'b6_ufo_sil': ufo_sil_tiles,                            # Bank 6 $9500 (3 tiles: $50..$52)
        'b6_bust': bust_tiles,                                  # Bank 6 $95C0 (8 tiles: $5C..$63)
        'b6_emblem': small_emblem_tiles,                        # Bank 6 $9640 (5 tiles: $64..$68)
        # Bank 5 $95A0..$968F cockpit tiles:
        #   $95A0..$95CF (3 tiles = $BA/$BB/$BC in $BE, $CA/$CB/$CC in $CE) = closed top 3
        #   $95E0..$960F (3 tiles = $BE/$BF/$C0 in $BE, $CE/$CF/$D0 in $CE) = closed bot 3
        #   $9630..$968F (6 tiles = $C3..$C8 in $BF, $D3..$D8 in $CF)      = open 6
        'b5_pilot_top': b''.join(pilot_closed_tiles[:3]),
        'b5_pilot_bot': b''.join(pilot_closed_tiles[3:6]),
        'b5_pilot_open': b''.join(pilot_open_tiles),
        'b5_triforce': b''.join(wm_crest),                      # Bank 5 $94B0 (3 tiles: $AB..$AD)
        'b8_surrender_d0': d0_tiles,                            # Bank 8 $BA10 (9 tiles: $A1..$A9)
        'b8_surrender_d1': b''.join(d1_tiles),                  # Bank 8 $BAA0 (7 tiles: $AA..$B0)
        'b8_surrender_d2': b''.join(d2_tiles[:6]),              # Bank 8 $BB10 (6 tiles: $B1..$B6)
    }


def compile_title_logo() -> bytes:
    """Compile 84 tiles ($2A..$7D in Bank 9 $B000) replacing 'MAN' with 'BARBA'."""
    # Clean 6x8 pixel-art glyphs with generous inner counters so B, A, R stay crisp
    glyphs = {
        'B': [
            '111110',
            '110011',
            '110011',
            '111110',
            '110011',
            '110011',
            '110011',
            '111110',
        ],
        'A': [
            '011110',
            '110011',
            '110011',
            '110011',
            '111111',
            '110011',
            '110011',
            '110011',
        ],
        'R': [
            '111110',
            '110011',
            '110011',
            '111110',
            '110110',
            '110011',
            '110011',
            '110011',
        ],
    }

    w, h = 192, 32
    face = [[False] * w for _ in range(h)]
    word = 'BARBA'
    # 5 letters x (24px wide + 6px gap) = 144px, slanted left-to-right to match 'MEGA'
    for idx, ch in enumerate(word):
        g = glyphs[ch]
        bx = 22 + idx * 30
        for gy in range(8):
            for gx in range(6):
                if g[gy][gx] == '1':
                    for sy in range(3):
                        y = 2 + gy * 3 + sy
                        slant = ((25 - y) * 18) // 25
                        for sx in range(4):
                            x = bx + gx * 4 + sx + slant
                            if 0 <= x < w and 0 <= y < h:
                                face[y][x] = True

    canvas = [['0'] * w for _ in range(h)]
    # 1. 3D drop shadow ('3' = dark green in Title BG Pal 1) shifted +3px right, +3px down
    for y in range(h):
        for x in range(w):
            if face[y][x]:
                for dy in range(2, 5):
                    for dx in range(2, 5):
                        if y + dy < h and x + dx < w:
                            canvas[y + dy][x + dx] = '3'
    # 2. 1px black separator ('0') around face so letters pop cleanly off the 3D shadow
    for y in range(h):
        for x in range(w):
            if face[y][x]:
                for dy, dx in ((1, 0), (0, 1), (1, 1)):
                    if y + dy < h and x + dx < w and not face[y + dy][x + dx]:
                        canvas[y + dy][x + dx] = '0'
    # 3. Crisp white/cyan horizontal-striped face ('2'=white, '1'=cyan in Title BG Pal 1)
    stripe_pat = (
        '2222222222'  # y=0..9: white top
        '1122112211'  # y=10..19: cyan/white stripes
        '222222222222'  # y=20..31: bright white base
    )
    for y in range(h):
        col_ch = stripe_pat[y]
        for x in range(w):
            if face[y][x]:
                canvas[y][x] = col_ch

    # Extract exact tiles $2A..$7D in nametable order:
    #   Row 8 (ty=0): cols 7..24 -> tx=3..20 (18 tiles: $2A..$3B)
    #   Row 9 (ty=1): cols 6..25 -> tx=2..21 (20 tiles: $3C..$4F)
    #   Row 10(ty=2): cols 5..26 -> tx=1..22 (22 tiles: $50..$65)
    #   Row 11(ty=3): cols 4..27 -> tx=0..23 (24 tiles: $66..$7D)
    row_spans = [(0, 3, 21), (1, 2, 22), (2, 1, 23), (3, 0, 24)]
    out = bytearray()
    for ty, tx_start, tx_end in row_spans:
        for tx in range(tx_start, tx_end):
            trows = [''.join(canvas[ty * 8 + y][tx * 8 : (tx + 1) * 8]) for y in range(8)]
            out.extend(encode_tile(trows))
    assert len(out) == 84 * 16
    return bytes(out)


def compile_title_barba(z2_bytes: bytes) -> dict[str, bytes]:
    """Compile 24x24 Barba standing on the Title Screen building (Bank 6 $9000)."""
    # Build a crisp 24x24 standing Barba (closed & roaring/open jaw for wind animation)
    heads_24 = {
        jaw: _shrink_y(resize_x(source_head(z2_bytes, jaw), 21), 13)
        for jaw in ('closed', 'open')
    }
    neck_raw = [''.join((source_pair(z2_bytes, 0xA0)[y], source_pair(z2_bytes, 0xA2)[y])) for y in range(16)]
    neck = resize_x(neck_raw, 12)
    claws = [
        '00011100111000',
        '00122100122100',
        '03311003311000',
    ]

    def make_24x24(jaw: str, ember: bool = False) -> list[bytes]:
        c = [['0'] * 24 for _ in range(24)]
        for y in range(11, 22):
            sway = (0, -1, 0, 1)[(y // 3) % 4]
            _blit(c, [neck[y % 16]], 10 + sway, y)
        _blit(c, ['0110', '1221', '1210', '0100'], 19, 11)
        _blit(c, claws, 8, 21)
        _blit(c, heads_24[jaw], 1, 0)
        if ember:
            _blit(c, ['32', '21'], 0, 7)
        return _encode_grid_tiles([''.join(r) for r in c], 3, 3)

    idle_tiles = make_24x24('closed', ember=False)  # 9 tiles: $00..$08
    open_tiles = make_24x24('open', ember=True)     # 9 tiles (top 6 = $09..$0E)
    blank_2 = b'\x00' * 32                          # $1F..$20 (hide Mega Man's face overlay)
    return {
        'b6_barba_idle': b''.join(idle_tiles),          # Bank 6 $9000 (9 tiles: $00..$08)
        'b6_barba_anim': b''.join(open_tiles[:6]),      # Bank 6 $9090 (6 tiles: $09..$0E)
        'b6_face_blank': blank_2,                       # Bank 6 $91F0 (2 tiles: $1F..$20)
    }


def write_preview_sheets(z2_path: Path, out_dir: Path) -> None:
    """Write preview PNGs of compiled Barba, Fireball, and Villainous Link art."""
    z2_bytes = load_source(z2_path)
    chr_tiles, _, _, poses = compile_barba_gameplay(z2_bytes)
    fb_tiles, _, _ = compile_barba_fireball()
    vlink = compile_villain_link(z2_bytes)

    # 1. Barba 32x40 poses grid
    names = [
        'idle', 'blink', 'walk0', 'walk1', 'walk2', 'jump',
        'shoot_idle', 'shoot_walk0', 'shoot_walk1', 'shoot_jump',
        'throw_idle', 'climb0', 'climb1', 'climb_shoot', 'hurt', 'land1',
    ]
    cols, cell_w, cell_h = 8, 36, 44
    rows_n = (len(names) + cols - 1) // cols
    img = [[BARBA_PALETTE[0]] * (cols * cell_w) for _ in range(rows_n * cell_h)]
    for i, nm in enumerate(names):
        ox, oy = (i % cols) * cell_w + 2, (i // cols) * cell_h + 2
        for y, row in enumerate(poses[nm]):
            for x, ch in enumerate(row):
                if ch != '0':
                    img[oy + y][ox + x] = BARBA_PALETTE[int(ch)]
    write_png(out_dir / 'preview_barba_poses.png', img, scale=2)

    # 2. Fireball 16x8
    fb_img = [[BARBA_PALETTE[0]] * 20 for _ in range(12)]
    for tx, tid in enumerate((FIREBALL_TILE_HEAD, FIREBALL_TILE_TAIL)):
        dec = decode_tile(fb_tiles[tid])
        for y in range(8):
            for x in range(8):
                fb_img[2 + y][2 + tx * 8 + x] = BARBA_PALETTE[dec[y][x]]
    write_png(out_dir / 'preview_fireball.png', fb_img, scale=4)

    # 3. Villainous Link Stage Select 32x32 + Pilot 24x16
    ss_img = [[STAGE_SELECT_PAL0[0]] * 36 for _ in range(36)]
    ss_raw = vlink['ss_portrait']
    assert isinstance(ss_raw, bytes)
    for idx in range(16):
        tx, ty = idx % 4, idx // 4
        dec = decode_tile(ss_raw[idx * 16 : (idx + 1) * 16])
        for y in range(8):
            for x in range(8):
                ss_img[2 + ty * 8 + y][2 + tx * 8 + x] = STAGE_SELECT_PAL0[dec[y][x]]
    write_png(out_dir / 'preview_vlink_stagesel.png', ss_img, scale=3)

    pilot_img = [[COCKPIT_PAL1[0]] * 28 for _ in range(40)]
    p_top = vlink['b5_pilot_top']
    p_bot = vlink['b5_pilot_bot']
    p_opn = vlink['b5_pilot_open']
    assert isinstance(p_top, bytes) and isinstance(p_bot, bytes) and isinstance(p_opn, bytes)
    for row_blk, raw_tiles in enumerate((p_top + p_bot, p_opn)):
        for idx in range(6):
            tx, ty = idx % 3, idx // 3
            dec = decode_tile(raw_tiles[idx * 16 : (idx + 1) * 16])
            for y in range(8):
                for x in range(8):
                    pilot_img[2 + row_blk * 18 + ty * 8 + y][2 + tx * 8 + x] = COCKPIT_PAL1[dec[y][x]]
    write_png(out_dir / 'preview_vlink_pilot.png', pilot_img, scale=3)


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    write_preview_sheets(root / 'roms' / 'z2.nes', root / 'build' / 'subgames' / 'mm2_inspect')
    print('Wrote MM2 art preview sheets.')
