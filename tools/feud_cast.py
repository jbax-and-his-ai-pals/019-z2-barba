"""Compile Barba-side and Zelda II-side character pools for Family Feud.

All Zelda II pixels are extracted at build time from ``roms/z2.nes`` (no
original pixels are committed). Each character is compiled at 3 height
variants into:
- 4x6 Stage Close-Up & Fast Money (3 frames: idle, roar, wiggle; <= 48 tiles)
- 2x4 Stage Overview (2 frames: idle, roar; <= 12 tiles, <= 3 row-0 tiles)
- 7x12 (Barba) / 6x12 (Z2 on riser box) Face-Off (2 frames: closed, open; y=0..79 above floor)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from assets import encounter_connector_rows, encounter_trail_rows, sprite_pairs
from boss_art import compile_lava_link, make_frames, resize_x, source_head, source_pair
from nes import encode_tile

ROOT = Path(__file__).resolve().parents[1]
CAST_CONFIG_PATH = ROOT / 'assets' / 'feud_cast.json'

DEFAULT_BARBA_PALETTES: dict[str, list[list[int]]] = {
    '1': [[0x37, 0x26], [0x36, 0x27], [0x37, 0x17], [0x36, 0x06]],
    '2': [[0x30, 0x12], [0x37, 0x00], [0x31, 0x02], [0x36, 0x13]],
    '3': [[0x37, 0x1A], [0x36, 0x2A], [0x38, 0x29], [0x37, 0x28]],
}

DEFAULT_Z2_PALETTES: dict[str, list[list[int]]] = {
    '1': [[0x37, 0x26], [0x36, 0x27], [0x30, 0x26], [0x36, 0x17]],
    '2': [[0x30, 0x12], [0x30, 0x21], [0x30, 0x00], [0x37, 0x13]],
    '3': [[0x36, 0x2A], [0x36, 0x1A], [0x37, 0x2A], [0x36, 0x28]],
}

# (char_id, label, default_pal_slot, default_mapping_123)
DEFAULT_BARBA_META: list[tuple[str, str, int]] = [
    ('barba_std',      'Barba',        1),
    ('barba_tall',     'Tall Barba',   1),
    ('barba_crouch',   'Crouch Barba', 1),
    ('barba_up',       'Sky Barba',    1),
    ('barba_dark',     'Dark Barba',   2),
    ('barba_tux',      'Tux Barba',    1),
    ('barba_waldo',    'Waldo Barba',  1),
    ('barba_jason',    'F13 Barba',    2),
    ('barba_moon',     'Moon Barba',   2),
    ('barba_wyrmling', 'Wyrmling',     3),
    ('barba_shades',   'Cool Barba',   2),
    ('barba_king',     'King Barba',   3),
    ('barba_berba',    'Spiked Berba', 3),
]

DEFAULT_Z2_META: list[tuple[str, str, int, str]] = [
    ('z2_link',        'Link',        3, '312'),
    ('z2_lavalink',    'Lava Link',   3, '312'),
    ('z2_error',       'Error',       2, '312'),
    ('z2_bagu',        'Sage',        1, '211'),
    ('z2_healer',      'Town Healer', 1, '321'),
    ('z2_oldwoman',    'Old Woman',   2, '321'),
    ('z2_guard',       'Town Guard',  1, '312'),
    ('z2_bot',         'Bot Slime',   2, '321'),
    ('z2_lad',         'Young Lad',   3, '312'),
    ('z2_kid',         'Little Kid',  3, '312'),
    ('z2_fatwoman',    'Townswoman',  1, '321'),
    ('z2_moblin',      'Moblin',      1, '213'),
    ('z2_daira',       'Daira',       1, '321'),
    ('z2_ironknuckle', 'Ironknuckle', 2, '211'),
    ('z2_stalfos',     'Stalfos',     2, '321'),
    ('z2_mago',        'Mago',        2, '312'),
    ('z2_fokka',       'Fokka',       1, '213'),
    ('z2_horsehead',   'Horsehead',   1, '211'),
    ('z2_helmethead',  'Helmethead',  1, '211'),
    ('z2_rebonack',    'Rebonack',    2, '213'),
    ('z2_carock',      'Carock',      2, '321'),
    ('z2_gooma',       'Gooma',       1, '321'),
    ('z2_thunderbird', 'Thunderbird', 1, '213'),
    ('z2_darklink',    'Dark Link',   3, '333'),
    ('z2_bowllady',    'Bowl Lady',   1, '321'),
    ('z2_wiseman',     'Wise Man',    2, '312'),
    ('z2_zelda',       'Zelda',       1, '321'),
    ('z2_fairy',       'Fairy',       1, '321'),
    ('z2_lizalfos',    'Wosu',        1, '321'),
    ('z2_fokkeru',     'Impa',        1, '321'),
    ('z2_acheman',     'Acheman',     1, '321'),
    ('z2_octorok',     'Octorok',     1, '321'),
    ('z2_ache',        'Ache',        2, '321'),
]


VALID_SPRITE_TYPES = ('full', 'top_half')


def build_default_config() -> dict:
    """Return default assets/feud_cast.json structure with all cast sprites included."""
    chars: list[dict] = []
    for cid, label, slot in DEFAULT_BARBA_META:
        chars.append({
            'id': cid,
            'pool': 'barba',
            'label': label,
            'included': True,
            'pal_slot': slot,
            'sprite_type': 'full',
        })
    for cid, label, slot, mapping in DEFAULT_Z2_META:
        chars.append({
            'id': cid,
            'pool': 'z2',
            'label': label,
            'included': True,
            'pal_slot': slot,
            'mapping': mapping,
            'outline': cid != 'z2_darklink',
            'sprite_type': 'full',
        })
    return {
        'version': 1,
        'barba_palettes': {k: [pair[:] for pair in v] for k, v in DEFAULT_BARBA_PALETTES.items()},
        'z2_palettes': {k: [pair[:] for pair in v] for k, v in DEFAULT_Z2_PALETTES.items()},
        'characters': chars,
    }


def load_cast_config(config_path: Path | None = None) -> dict:
    """Load assets/feud_cast.json, falling back cleanly to defaults."""
    path = config_path or CAST_CONFIG_PATH
    cfg = build_default_config()
    if not path.is_file():
        return cfg
    raw = json.loads(path.read_text(encoding='utf-8'))
    for pal_key in ('barba_palettes', 'z2_palettes'):
        if isinstance(raw.get(pal_key), dict):
            for slot in ('1', '2', '3'):
                pairs = raw[pal_key].get(slot)
                if isinstance(pairs, list) and len(pairs) == 4:
                    cfg[pal_key][slot] = [[int(p[0]) & 0x3F, int(p[1]) & 0x3F] for p in pairs]
    by_id = {c['id']: c for c in raw.get('characters', []) if isinstance(c, dict) and 'id' in c}
    for ch in cfg['characters']:
        ov = by_id.get(ch['id'])
        if not ov:
            continue
        if 'included' in ov:
            ch['included'] = bool(ov['included'])
        if 'pal_slot' in ov and int(ov['pal_slot']) in (1, 2, 3):
            ch['pal_slot'] = int(ov['pal_slot'])
        st = ov.get('sprite_type')
        if st in VALID_SPRITE_TYPES:
            ch['sprite_type'] = st
        if ch['pool'] == 'z2':
            m = str(ov.get('mapping', ch['mapping']))
            if len(m) == 3 and all(c in '0123' for c in m):
                ch['mapping'] = m
            if 'outline' in ov:
                ch['outline'] = bool(ov['outline'])
    return cfg


def get_runtime_cast_tables(config: dict | None = None) -> dict:
    """Return flat palette pair tables and included Z2 slot list for ROM assembly."""
    cfg = config or load_cast_config()
    barba_pairs: list[tuple[int, int]] = []
    z2_pairs: list[tuple[int, int]] = []
    for slot in ('1', '2', '3'):
        barba_pairs.extend((int(a), int(b)) for a, b in cfg['barba_palettes'][slot])
        z2_pairs.extend((int(a), int(b)) for a, b in cfg['z2_palettes'][slot])
    z2_slots = [
        int(ch['pal_slot'])
        for ch in cfg['characters']
        if ch['pool'] == 'z2' and ch.get('included', True)
    ]
    return {
        'barba_pal_pairs': barba_pairs,
        'z2_pal_pairs': z2_pairs,
        'z2_pal_slots': z2_slots,
    }


@dataclass(frozen=True)
class CompiledVariant:
    """One compiled height variant of a character across all 3 views."""

    stage_tiles: bytes       # N_s * 16 bytes (N_s <= 48)
    stage_maps: bytes        # 3 * 24 bytes (frames 0,1,2; 0=blank, 1..N_s=local tile)
    ov_tiles: bytes          # N_o * 16 bytes (N_o <= 12, row-0 tiles first)
    ov_row0_count: int       # number of tiles in ov_tiles used by row 0 (<= 3)
    ov_maps: bytes           # 2 * 8 bytes (frames 0,1; 0=blank, 1..N_o=local tile)
    fo_tiles: bytes          # N_f * 16 bytes (N_f <= 72)
    fo_maps: bytes           # 2 * 70 bytes (barba 7x10) or 2 * 60 bytes (z2 6x10) upper rows 0..9


@dataclass(frozen=True)
class CastCharacter:
    """A playable/opposing character with 3 height presets."""

    char_id: str
    label: str
    pool: str                # 'barba' | 'z2'
    variants: tuple[CompiledVariant, CompiledVariant, CompiledVariant]


def _to_feud(rows: list[str], *, flip_h: bool = False, mapping: dict[str, str] | None = None) -> list[str]:
    m = mapping or {'0': '0', '1': '2', '2': '1', '3': '1'}
    out: list[str] = []
    for r in rows:
        rr = r[::-1] if flip_h else r
        out.append(''.join(m[c] for c in rr))
    return out


def _add_outline(grid: list[list[str]], *, skip_bottom: bool = False) -> list[list[str]]:
    h, w = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    for y in range(h):
        if skip_bottom and y == h - 1:
            continue
        for x in range(w):
            if grid[y][x] == '0':
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and grid[ny][nx] != '0':
                        out[y][x] = '3'
                        break
    return out


def _stamp(canvas: list[list[str]], rows: list[str], ox: int, oy: int) -> None:
    h, w = len(canvas), len(canvas[0])
    for y, r in enumerate(rows):
        ny = oy + y
        if 0 <= ny < h:
            for x, ch in enumerate(r):
                nx = ox + x
                if ch != '0' and 0 <= nx < w:
                    canvas[ny][nx] = ch


def _shift_rows(rows: list[str], dx: int = 0, dy: int = 0) -> list[str]:
    h, w = len(rows), len(rows[0])
    out = [['0'] * w for _ in range(h)]
    for y in range(h):
        ny = y + dy
        if 0 <= ny < h:
            for x in range(w):
                nx = x + dx
                if 0 <= nx < w and rows[y][x] != '0':
                    out[ny][nx] = rows[y][x]
    return [''.join(r) for r in out]


def _stretch_y(rows: list[str], target_h: int) -> list[str]:
    old_h = len(rows)
    return [rows[min(old_h - 1, (y * old_h + target_h // 2) // target_h)] for y in range(target_h)]


def _z2_pair(z2: bytes, even_bank: int, odd_bank: int, tid: int) -> list[str]:
    if tid in (0xF5, None):
        return ['0' * 8 for _ in range(16)]
    bank = odd_bank if (tid & 1) else even_bank
    return source_pair(z2, tid & 0xFE, bank)


def _z2_sprite(z2: bytes, even_bank: int, odd_bank: int, grid_tids: list[list[int]], *, flip_h: bool = False) -> list[str]:
    out: list[str] = []
    for row in grid_tids:
        cols = [_z2_pair(z2, even_bank, odd_bank, t) for t in row]
        for y in range(16):
            line = ''.join(col[y] for col in cols)
            out.append(line[::-1] if flip_h else line)
    return out


def _crop_top_half(rows: list[str], *, trim_x: bool = False) -> list[str]:
    """Return the top half of non-empty sprite rows for waist-up podium framing."""
    top = 0
    while top < len(rows) and all(c == '0' for c in rows[top]):
        top += 1
    bot = len(rows)
    while bot > top and all(c == '0' for c in rows[bot - 1]):
        bot -= 1
    trimmed = rows[top:bot] or rows
    half = trimmed[:max(1, round(len(trimmed) * 0.5))]
    if not trim_x:
        return half
    left = min((x for r in half for x, c in enumerate(r) if c != '0'), default=0)
    right = max((x for r in half for x, c in enumerate(r) if c != '0'), default=len(half[0]) - 1) + 1
    return [r[left:right] for r in half]


def _trimmed_bbox(rows: list[str]) -> tuple[int, int, int, int]:
    """Return (x0, x1, y0, y1) bounding box of non-transparent pixels."""
    ys = [y for y, r in enumerate(rows) if any(c != '0' for c in r)]
    xs = [x for r in rows for x, c in enumerate(r) if c != '0']
    if not ys or not xs:
        return 0, len(rows[0]), 0, len(rows)
    return min(xs), max(xs) + 1, min(ys), max(ys) + 1


def _proportional_target_size(
    sw: int,
    sh: int,
    max_w: int,
    max_h: int,
    target_scale: float,
    *,
    min_h: int = 16,
    max_stretch: float = 1.15,
) -> tuple[int, int, float]:
    """Compute proportional (tw, th, eff_scale) capped by bounds and aspect ratio."""
    s = min(target_scale, max_w / sw, max_h / sh)
    tw = max(8, round(sw * s))
    th = max(min_h, round(sh * s))
    if (th / sh) > max_stretch * (tw / sw):
        tw = min(max_w, round(sw * (th / sh) / max_stretch))
    return tw, th, th / sh


def _scale_z2_by_factor(
    rows: list[str],
    scale: float,
    max_w: int,
    max_h: int,
    mapping: dict[str, str],
    *,
    min_h: int = 12,
    max_stretch: float = 1.15,
) -> list[str]:
    """Trim empty borders and scale proportionally by ``scale`` within bounds."""
    x0, x1, y0, y1 = _trimmed_bbox(rows)
    sw, sh = x1 - x0, y1 - y0
    tw = min(max_w, max(8, round(sw * scale)))
    th = min(max_h, max(min_h, round(sh * scale)))
    if (th / sh) > max_stretch * (tw / sw):
        tw = min(max_w, round(sw * (th / sh) / max_stretch))
    sub = [r[x0:x1] for r in rows[y0:y1]]
    scaled = _stretch_y(resize_x(sub, tw), th)
    return [''.join(mapping[c] for c in r) for r in scaled]


def _draw_faceoff_box(canvas: list[list[str]]) -> None:
    """Draw the 44x16 Family Feud stage riser box on y=64..79 (Pal 0 colors 1..3)."""
    x0, x1, y_top = 2, 45, 64
    for x in range(x0 + 1, x1):
        canvas[y_top][x] = '3'
    for y in (y_top + 1, y_top + 2):
        canvas[y][x0] = '3'
        canvas[y][x1] = '3'
        for x in range(x0 + 1, x1):
            canvas[y][x] = '1'
    for x in range(x0, x1 + 1):
        canvas[y_top + 3][x] = '3'
    for y in range(y_top + 4, y_top + 15):
        canvas[y][x0 + 1] = '3'
        canvas[y][x0 + 2] = '1'
        canvas[y][x0 + 3] = '3'
        canvas[y][x1 - 1] = '3'
        canvas[y][x1 - 2] = '1'
        canvas[y][x1 - 3] = '3'
        for x in range(x0 + 4, x1 - 3):
            canvas[y][x] = '2'
    for x in range(x0 + 6, x1 - 5):
        canvas[y_top + 7][x] = '3'
        canvas[y_top + 8][x] = '1'
        canvas[y_top + 9][x] = '1'
        canvas[y_top + 10][x] = '3'
    for y in (y_top + 8, y_top + 9):
        canvas[y][x0 + 6] = '3'
        canvas[y][x1 - 6] = '3'
    for x in range(x0 + 1, x1):
        canvas[y_top + 15][x] = '3'


def _trim_and_scale_z2(
    rows: list[str],
    target_w: int,
    target_h: int,
    mapping: dict[str, str],
) -> list[str]:
    # Trim empty top/bottom rows so characters sit flush on bottom edge
    top = 0
    while top < len(rows) and all(c == '0' for c in rows[top]):
        top += 1
    bot = len(rows)
    while bot > top and all(c == '0' for c in rows[bot - 1]):
        bot -= 1
    trimmed = rows[top:bot] or rows
    scaled = _stretch_y(resize_x(trimmed, target_w), target_h)
    return [''.join(mapping[c] for c in r) for r in scaled]


def _pack_frames_local(frames: list[list[str]], max_tiles: int, *, row0_first: bool = False) -> tuple[bytes, int, bytes]:
    """Pack WxH tile grids into local 1-based deduplicated tiles + tilemaps."""
    h_tiles = len(frames[0]) // 8
    w_tiles = len(frames[0][0]) // 8
    pool: dict[bytes, int] = {}
    tiles_out: list[bytes] = []

    def get_tid(sub: list[str]) -> int:
        if all(ch == '0' for line in sub for ch in line):
            return 0
        enc = encode_tile(sub)
        tid = pool.get(enc)
        if tid is None:
            tid = len(tiles_out) + 1
            if tid > max_tiles:
                raise ValueError(f'Character exceeded {max_tiles} tile budget ({tid})')
            pool[enc] = tid
            tiles_out.append(enc)
        return tid

    row0_count = 0
    if row0_first:
        for grid in frames:
            for c in range(w_tiles):
                sub = [grid[y][c * 8 : (c + 1) * 8] for y in range(8)]
                get_tid(sub)
        row0_count = len(tiles_out)

    maps_out = bytearray()
    for grid in frames:
        for r in range(h_tiles):
            for c in range(w_tiles):
                sub = [grid[r * 8 + y][c * 8 : (c + 1) * 8] for y in range(8)]
                maps_out.append(get_tid(sub))

    return b''.join(tiles_out), row0_count, bytes(maps_out)


def _draw_accessory(canvas: list[list[str]], kind: str, ox: int, oy: int, roar: bool = False) -> None:
    """Stamp Barba-side accessories (hat, mask, helmet, crown, shades, tux)."""
    cw = len(canvas[0])
    ch = len(canvas)
    if kind == 'waldo':
        # Zelda 2 approved floppy striped Waldo hat + puffball (front + back at +7) + glasses
        sv_hat_front = (
            '00011133',
            '03311133',
            '33333113',
            '33333313',
            '11113331',
            '11111111',
            '11111111',
        )
        sv_hat_tall = (
            '33100000',
            '33113000',
            '13113300',
            '13133110',
            '31100110',
            '11301111',
            '00001111',
            '00000110',
        )
        m_waldo = {'1': '2', '3': '1'}
        hat_grid = [['0'] * 15 for _ in range(8)]
        for hy, row in enumerate(sv_hat_tall):
            for hx, hch in enumerate(row):
                if hch in m_waldo:
                    hat_grid[hy][7 + hx] = m_waldo[hch]
        for hy, row in enumerate(sv_hat_front):
            for hx, hch in enumerate(row):
                if hch in m_waldo:
                    hat_grid[hy][hx] = m_waldo[hch]
        hat = [''.join(r) for r in hat_grid]
        hat_ox = ox + (11 if cw >= 56 else 8)
        hat_oy = max(1 if ch <= 48 else 0, oy - (5 if ch > 48 else 4))
        _stamp(canvas, hat, hat_ox, hat_oy)
        # Glasses rim over eye area
        gx0 = ox + (8 if cw >= 56 else 6)
        gx1 = ox + (15 if cw >= 56 else 12)
        for gx in range(gx0, gx1):
            if 0 <= oy + 4 < ch and 0 <= gx < cw:
                canvas[oy + 4][gx] = '1'
    elif kind == 'jason':
        # White hockey mask over front face
        mask = [
            '01111110',
            '11311311',
            '11121111',
            '11111111',
            '01311310',
            '00111100',
        ]
        _stamp(canvas, mask, ox + 1, oy + 3)
    elif kind == 'moon':
        # Bubble helmet dome around head
        hx, hy = ox + (12 if cw >= 56 else 10), oy + 7
        for y in range(max(0, hy - 9), min(ch, hy + 10)):
            for x in range(max(0, hx - 12), min(cw, hx + 13)):
                d2 = ((x - hx) / 11.5) ** 2 + ((y - hy) / 8.8) ** 2
                if 0.78 <= d2 <= 1.0:
                    canvas[y][x] = '1'
    elif kind == 'shades':
        # Cool dark shades + white shine
        gx0 = ox + (7 if cw >= 56 else 5)
        gx1 = ox + (18 if cw >= 56 else 15)
        for gx in range(gx0, gx1):
            if 0 <= oy + 6 < ch and 0 <= gx < cw:
                canvas[oy + 6][gx] = '3'
                if oy + 7 < ch:
                    canvas[oy + 7][gx] = '3'
        for shine_dx in (1, 6):
            if 0 <= oy + 6 < ch and 0 <= gx0 + shine_dx < cw:
                canvas[oy + 6][gx0 + shine_dx] = '1'
    elif kind == 'crown':
        crown = [
            '1001001001',
            '1211211211',
            '1121111211',
        ]
        crown_ox = ox + (11 if cw >= 56 else 9)
        _stamp(canvas, crown, crown_ox, max(0, oy - 1))
    elif kind == 'tux':
        # Sharp black tux & white V-shirt + accent bowtie & pocket square covering neck & dorsal spines
        ty = oy + 15
        x0 = 9 if cw >= 56 else (ox + 7 if ox <= 8 else ox + 2)
        x1 = 23 if cw >= 56 else min(cw - 1, ox + 20)
        cx = (x0 + x1) // 2
        tux_end = ch - 14 if ch >= 80 else ch
        for y in range(ty, tux_end):
            for x in range(x0, x1):
                canvas[y][x] = '3'
            if y - ty < 12:
                hw = max(1, (12 - (y - ty)) // 3)
                for x in range(cx - hw, cx + hw):
                    canvas[y][x] = '1'
        if ty + 1 < ch:
            for x in range(cx - 2, cx + 2):
                canvas[ty + 1][x] = '2'
        if ty + 8 < ch:
            canvas[ty + 8][min(x1 - 2, cx + 3)] = '2'
            canvas[ty + 8][min(x1 - 1, cx + 4)] = '2'
    elif kind == 'dark':
        # Fierce glowing eye + alternating dorsal spikes attached to back edge
        if 0 <= oy + 5 < ch and 0 <= ox + 7 < cw:
            canvas[oy + 5][ox + 7] = '1'
        spine_end = ch - 16 if ch >= 80 else ch
        for y in range(oy + 14, spine_end, 4):
            sx = 22
            while sx > 12 and canvas[y][sx - 1] == '0':
                sx -= 1
            canvas[y][sx] = '1'
            if y + 1 < spine_end:
                canvas[y + 1][sx] = '1'
    elif kind == 'berba':
        # Extra double-horn crest + chest spikes attached to the neck edge
        dx = 15 if cw >= 56 else 13
        if 0 <= oy + 2 < ch and ox + dx + 4 < cw:
            canvas[oy + 2][ox + dx] = '1'
            canvas[oy + 1][ox + dx + 1] = '1'
            canvas[oy + 2][ox + dx + 3] = '1'
            canvas[oy + 1][ox + dx + 4] = '1'
        spike_end = ch - 15 if ch >= 80 else ch
        for y in range(oy + 16, spike_end, 5):
            sx = 0
            while sx < cw and canvas[y][sx] == '0':
                sx += 1
            if 0 < sx < cw:
                canvas[y][sx - 1] = '1'


def _apply_barba_detail(canvas: list[list[str]], detail: str, ox: int, oy: int) -> None:
    """Apply subtle scale, belly-ridge, and dorsal-crest variations across Barba variants."""
    cw = len(canvas[0])
    ch = len(canvas)
    top_y = next((y for y in range(ch) if any(c != '0' for c in canvas[y])), oy)
    if detail == 'ribbed':
        # Subtle belly-plate seam lines on tall/spiked variants
        for y in range(max(0, top_y + 17), ch - 1, 5):
            for x in range(ox + 2, min(cw, ox + 12)):
                if canvas[y][x] == '1':
                    canvas[y][x] = '2'
                    break
    elif detail == 'spined':
        # Subtle pale dorsal scale tips along the back edge
        for y in range(max(0, top_y + 15), ch - 1, 5):
            for x in range(min(cw - 1, ox + 22), ox + 5, -1):
                if canvas[y][x] == '2':
                    canvas[y][x] = '1'
                    break
    elif detail == 'horned':
        # Extra subtle brow highlight + neck-scale notch
        if 0 <= top_y + 2 < ch and 0 <= ox + 11 < cw:
            canvas[top_y + 2][ox + 11] = '1'
        for y in range(max(0, top_y + 19), ch - 1, 6):
            for x in range(ox + 3, min(cw, ox + 12)):
                if canvas[y][x] == '1':
                    canvas[y][x] = '2'
                    break
    elif detail == 'sleek':
        # Subtle bright crest dot + clean mid-neck scale accent
        if 0 <= top_y + 1 < ch and 0 <= ox + 12 < cw:
            canvas[top_y + 1][ox + 12] = '1'


def _mapping_dict(m: str | dict[str, str]) -> dict[str, str]:
    if isinstance(m, dict):
        return m
    return {'0': '0', '1': m[0], '2': m[1], '3': m[2]}


def _barba_stage_grids(
    frames24: dict[str, list[str]],
    spec: tuple,
    dy_st: int,
    sprite_type: str = 'full',
) -> list[list[str]]:
    cid = spec[0]
    _, _, p_idle, p_roar, p_wig, acc, detail, w_px, base_h = spec
    if sprite_type == 'top_half':
        w_top = min(24, round(w_px * 1.2))
        raw_top_grids: list[list[list[str]]] = []
        for f_i, pose_name in enumerate((p_idle, p_roar, p_wig)):
            src = frames24[pose_name]
            raw = _stretch_y(resize_x(src[:-1], w_px), base_h)
            mapped = _to_feud(raw, flip_h=False)
            c0 = [['0'] * 32 for _ in range(48)]
            ox0, oy0 = (32 - w_px) // 2, 48 - base_h
            _stamp(c0, mapped, ox0, oy0)
            if detail:
                _apply_barba_detail(c0, detail, ox0, oy0)
            if acc:
                _draw_accessory(c0, acc, ox0, oy0, roar=(f_i == 1))
            cropped = _crop_top_half([''.join(r) for r in c0], trim_x=True)
            scaled = _stretch_y(resize_x(cropped, w_top), base_h)
            c_top = [['0'] * 32 for _ in range(48)]
            oy = 48 - base_h + dy_st
            ox = (32 - w_top) // 2
            if f_i == 2:
                _stamp(c_top, scaled, ox + 1, min(47, oy + 1))
            else:
                _stamp(c_top, scaled, ox, oy)
            raw_top_grids.append(_add_outline(c_top, skip_bottom=True))

        for yk1, yk2 in ((24, 16), (16, 16), (16, 8), (8, 8)):
            st_grids: list[list[str]] = []
            for f_i, grid in enumerate(raw_top_grids):
                cur = [row[:] for row in grid]
                if f_i in (1, 2) and st_grids:
                    yk = yk1 if f_i == 1 else yk2
                    for y in range(yk, 48):
                        cur[y] = list(st_grids[0][y])
                st_grids.append([''.join(r) for r in cur])
            try:
                _pack_frames_local(st_grids, 36)
                return st_grids
            except ValueError:
                continue
        return st_grids

    raw_grids: list[list[list[str]]] = []
    for f_i, pose_name in enumerate((p_idle, p_roar, p_wig)):
        src = frames24[pose_name]
        raw = _stretch_y(resize_x(src[:-1], w_px), base_h)
        mapped = _to_feud(raw, flip_h=False)
        canvas = [['0'] * 32 for _ in range(48)]
        oy = 48 - base_h + dy_st
        ox = (32 - w_px) // 2 + (1 if cid == 'barba_up' else 0)
        if f_i == 2:
            _stamp(canvas, mapped, ox + 1, min(47, oy + 1))
            if detail:
                _apply_barba_detail(canvas, detail, ox + 1, min(47, oy + 1))
            if acc:
                _draw_accessory(canvas, acc, ox + 1, min(47, oy + 1), roar=False)
        else:
            _stamp(canvas, mapped, ox, oy)
            if detail:
                _apply_barba_detail(canvas, detail, ox, oy)
            if acc:
                _draw_accessory(canvas, acc, ox, oy, roar=(f_i == 1))
        raw_grids.append(_add_outline(canvas, skip_bottom=True))

    # Keep as much of the roar/wiggle pose intact as fits within the 36-tile seat budget
    # so tilted ('up') and crouched ('crouch') Barbas never lose half their head.
    candidates = (
        (48, 48), (48, 32), (48, 24), (48, 16),
        (40, 24), (40, 16), (32, 24), (32, 16), (24, 16),
    )
    st_grids: list[list[str]] = []
    for yk1, yk2 in candidates:
        st_grids = []
        for f_i, grid in enumerate(raw_grids):
            cur = [row[:] for row in grid]
            if f_i in (1, 2) and st_grids:
                yk = yk1 if f_i == 1 else yk2
                for y in range(yk, 48):
                    cur[y] = list(st_grids[0][y])
            st_grids.append([''.join(r) for r in cur])
        try:
            _pack_frames_local(st_grids, 36)
            return st_grids
        except ValueError:
            continue
    return st_grids


def _make_lava_link_frames(z2: bytes) -> dict[str, list[str]]:
    """Build 26x48 closed/open Lava Link frames (1=hair/outline, 2=skin, 3=green cap/tunic)."""
    from nes import decode_tile

    lava_pairs = compile_lava_link(z2)

    def decode_pair(pbytes: bytes) -> list[str]:
        t0 = decode_tile(pbytes[:16])
        t1 = decode_tile(pbytes[16:32])
        return [''.join(str(x) for x in r) for r in (t0 + t1)]

    lava_neck = [a + b for a, b in zip(decode_pair(lava_pairs[0xA0]), decode_pair(lava_pairs[0xA2]))]
    lava_neck16 = resize_x(lava_neck, 16)
    lava_frames: dict[str, list[str]] = {}
    for jaw, pair_ids in (('closed', (0x14, 0x16)), ('open', (0x28, 0x2A))):
        head16 = [a + b for a, b in zip(decode_pair(lava_pairs[pair_ids[0]]), decode_pair(lava_pairs[pair_ids[1]]))]
        head20 = resize_x(head16, 20)
        c = [['0'] * 26 for _ in range(48)]
        for y in range(14, 48):
            sway = (0, -1, 0, 1)[(y // 8) % 4]
            _stamp(c, [lava_neck16[(y - 16) % 16]], 8 + sway, y)
        _stamp(c, head20, 6, 0)
        lava_frames[jaw] = [''.join(r) for r in c]
    return lava_frames


def _prepare_barba_assets(z2: bytes) -> tuple[dict, dict, list, list, list, list[tuple]]:
    frames24 = make_frames(z2, 24)
    frames16 = make_frames(z2, 16)

    native_neck = [''.join((source_pair(z2, 0xA0)[y], source_pair(z2, 0xA2)[y])) for y in range(16)]
    neck_pairs = sprite_pairs(native_neck)
    torso_gfx = {0x06: neck_pairs[0], 0x08: neck_pairs[1]}
    barba_bend = encounter_connector_rows(torso_gfx)
    barba_trail = encounter_trail_rows(torso_gfx)

    specs = [
        ('barba_std',      'Barba',        'idle',   'attack',        'walk1',  None,     None,     20, 47),
        ('barba_tall',     'Tall Barba',   'walk0',  'attack',        'walk2',  None,     'ribbed', 22, 47),
        ('barba_crouch',   'Crouch Barba', 'crouch', 'crouch-attack', 'crouch', None,     'horned', 22, 47),
        ('barba_up',       'Sky Barba',    'idle',   'up',            'idle',   None,     'spined', 20, 47),
        ('barba_dark',     'Dark Barba',   'idle',   'attack',        'walk1',  'dark',   'ribbed', 20, 47),
        ('barba_tux',      'Tux Barba',    'idle',   'attack',        'walk1',  'tux',    None,     20, 47),
        ('barba_waldo',    'Waldo Barba',  'idle',   'attack',        'walk1',  'waldo',  None,     20, 43),
        ('barba_jason',    'F13 Barba',    'idle',   'attack',        'walk1',  'jason',  'sleek',  20, 47),
        ('barba_moon',     'Moon Barba',   'idle',   'attack',        'walk1',  'moon',   None,     20, 45),
        ('barba_wyrmling', 'Wyrmling',     'idle',   'attack',        'walk1',  None,     'spined', 18, 34),
        ('barba_shades',   'Cool Barba',   'idle',   'attack',        'walk1',  'shades', 'sleek',  20, 47),
        ('barba_king',     'King Barba',   'idle',   'attack',        'walk1',  'crown',  'horned', 20, 45),
        ('barba_berba',    'Spiked Berba', 'idle',   'attack',        'walk1',  'berba',  'ribbed', 20, 46),
    ]
    return frames24, frames16, native_neck, barba_bend, barba_trail, specs


def _build_barba_pool(
    z2: bytes,
    included_ids: set[str] | None = None,
    char_overrides: dict[str, dict] | None = None,
) -> list[CastCharacter]:
    frames24, frames16, native_neck, barba_bend, barba_trail, specs = _prepare_barba_assets(z2)

    pool: list[CastCharacter] = []
    for c_idx, spec in enumerate(specs):
        cid, label, p_idle, p_roar, p_wig, acc, detail, w_px, base_h = spec
        if included_ids is not None and cid not in included_ids:
            continue
        ov = (char_overrides or {}).get(cid)
        sprite_type = ov.get('sprite_type', 'full') if ov else 'full'
        if sprite_type not in VALID_SPRITE_TYPES:
            sprite_type = 'full'
        variants: list[CompiledVariant] = []
        for h_idx, (dy_st, dy_ov, dy_fo) in enumerate(((0, 0, 0), (3, 2, 5), (6, 4, 10))):
            # 1. Stage Close-Up 4x6 (32x48)
            st_grids = _barba_stage_grids(frames24, spec, dy_st, sprite_type=sprite_type)
            st_tiles, _, st_maps = _pack_frames_local(st_grids, 36)

            # 2. Stage Overview 2x4 (16x32) - preserve full head on roar within 13 tiles
            ov_raw: list[list[list[str]]] = []
            for f_i, pose_name in enumerate((p_idle, p_roar)):
                if pose_name in ('crouch', 'crouch-attack'):
                    src16 = frames16[pose_name][17:48]
                else:
                    src16 = frames16[pose_name][0:31]
                if sprite_type == 'top_half':
                    src16 = _crop_top_half(src16)
                oh = min(28, max(18, round(28 * base_h / 47)))
                w16 = 14 if sprite_type == 'top_half' else 13
                raw16 = _stretch_y(resize_x(src16, w16), oh)
                mapped16 = _to_feud(raw16, flip_h=False)
                c16 = [['0'] * 16 for _ in range(32)]
                oy16 = 32 - oh + dy_ov
                _stamp(c16, mapped16, 1, oy16)
                ov_raw.append(_add_outline(c16, skip_bottom=True))
            ov_tiles = b''
            ov_r0 = 0
            ov_maps = b''
            for ov_yk in (32, 24, 16):
                ov_grids = [
                    [''.join(r) for r in ov_raw[0]],
                    [''.join(ov_raw[1][y] if y < ov_yk else ov_raw[0][y]) for y in range(32)],
                ]
                try:
                    ov_tiles, ov_r0, ov_maps = _pack_frames_local(ov_grids, 13, row0_first=True)
                    if ov_r0 <= 4:
                        break
                except ValueError:
                    continue
            assert ov_tiles and ov_r0 <= 4, f'{cid} h={h_idx} used {ov_r0} row-0 overview tiles (>4)'

            # 3. Face-Off 7x10 full-body Z2 Barba (56x80, y=0..79 above floor; bend+tail on y=63..78)
            fo_grids: list[list[str]] = []
            for f_i, pose_name in enumerate((p_idle, p_roar)):
                src = frames24[pose_name]
                tall_h = round(70 * base_h / 47) - dy_fo
                if pose_name in ('crouch', 'crouch-attack'):
                    tall_h -= 12
                    head = src[24:40]
                    neck = native_neck
                    neck_off = 14
                elif pose_name == 'up':
                    head = src[:28]
                    neck = native_neck
                    neck_off = 24
                else:
                    head = src[:16]
                    neck = native_neck
                    neck_off = 14
                tall_h = max(40, min(72, tall_h))
                top_y = 79 - tall_h
                c_fo = [['0'] * 56 for _ in range(80)]
                for y in range(top_y + neck_off, 65):
                    sway = (0, -1, 0, 1)[((y // 8) + f_i + c_idx) % 4]
                    _stamp(c_fo, _to_feud([neck[y % 16]]), 8 + sway, y)
                _stamp(c_fo, _to_feud(barba_bend), 8, 63)
                _stamp(c_fo, _to_feud(barba_trail), 24, 63)
                _stamp(c_fo, _to_feud(head), 0, top_y)
                if detail:
                    _apply_barba_detail(c_fo, detail, 0, top_y)
                if acc:
                    _draw_accessory(c_fo, acc, 0, top_y, roar=(f_i == 1))
                outlined_fo = _add_outline(c_fo, skip_bottom=False)
                fo_grids.append([''.join(r) for r in outlined_fo])
            fo_tiles, _, fo_maps = _pack_frames_local(fo_grids, 72)

            variants.append(CompiledVariant(st_tiles, st_maps, ov_tiles, ov_r0, ov_maps, fo_tiles, fo_maps))
        pool.append(CastCharacter(cid, label, 'barba', (variants[0], variants[1], variants[2])))
    return pool


def _restore_sage_staff(idle_rows: list[str], spell_rows: list[str]) -> list[str]:
    """Keep the sage's upper staff shaft/orb visible in the spell-cast frame."""
    out = [list(r) for r in spell_rows]
    for y in range(min(16, len(out), len(idle_rows))):
        for x in range(min(4, len(out[y]), len(idle_rows[y]))):
            if idle_rows[y][x] != '0' and out[y][x] == '0':
                out[y][x] = idle_rows[y][x]
    return [''.join(r) for r in out]


def _mirror_half(left_rows: list[str]) -> list[str]:
    return [r + r[::-1] for r in left_rows]


def _overlay_rows(base: list[str], top: list[str], ox: int, oy: int) -> list[str]:
    out = [list(r) for r in base]
    for y, row in enumerate(top):
        ny = oy + y
        if 0 <= ny < len(out):
            for x, ch in enumerate(row):
                nx = ox + x
                if ch != '0' and 0 <= nx < len(out[0]):
                    out[ny][nx] = ch
    return [''.join(r) for r in out]


_Z2_JUMP_ROAR = frozenset({
    'z2_link', 'z2_guard', 'z2_kid', 'z2_bot', 'z2_rebonack',
    'z2_darklink', 'z2_fairy', 'z2_lizalfos', 'z2_fokkeru', 'z2_ache',
})

_Z2_YKEEP_BY_CID: dict[str, tuple[int, int]] = {
    'z2_healer':      (48, 16),
    'z2_bowllady':    (48, 16),
    'z2_guard':       (48, 16),
    'z2_zelda':       (24, 16),
    'z2_fairy':       (48, 48),
    'z2_ache':        (48, 48),
    'z2_fokka':       (32, 16),
    'z2_moblin':      (48, 0),
    'z2_horsehead':   (24, 16),
    'z2_rebonack':    (48, 16),
    'z2_thunderbird': (24, 16),
    'z2_lizalfos':    (24, 16),
    'z2_fokkeru':     (24, 16),
}


def _z2_y_keep(cid: str, f_i: int, oy: int) -> int:
    if f_i in (1, 2) and cid in _Z2_YKEEP_BY_CID:
        return _Z2_YKEEP_BY_CID[cid][f_i - 1]
    return min(40, max(16, ((max(0, oy) + 15) // 8) * 8))


def _z2_specs(z2: bytes) -> list[tuple]:
    M_STD   = '312'
    M_DRESS = '321'
    M_ROBE  = '211'
    M_ENEMY = '213'

    def spr(eb, ob, tids):
        return _z2_sprite(z2, eb, ob, tids)

    sage_idle = spr(0x06, 0x07, [[0xD0, 0xD2], [0xD4, 0xD6]])
    sage_spell = _restore_sage_staff(sage_idle, spr(0x06, 0x07, [[0x62, 0x64], [0xCC, 0xCE]]))
    healer_idle = spr(0x06, 0x07, [[0xD8, 0xDA], [0xE0, 0xE2]])
    healer_walk = spr(0x06, 0x07, [[0xD8, 0xDA], [0xE4, 0xE6]])
    guard_idle = spr(0x06, 0x07, [[0x01, 0x03], [0x05, 0x07]])
    moblin_idle = spr(0x09, 0x09, [[0x0F, 0x11], [0x17, 0x19]])
    moblin_walk = spr(0x09, 0x09, [[0x0F, 0x11], [0x13, 0x15]])
    daira_idle = spr(0x08, 0x08, [[0xE0, 0xE2], [0xE4, 0xE6]])
    daira_roar = spr(0x08, 0x08, [[0xE0, 0xE2], [0xEA, 0xEC]])
    fokka_idle = spr(0x0C, 0x0C, [[0xE0, 0xE2], [0xE4, 0xE6]])
    fokka_roar = spr(0x0C, 0x0C, [[0xE8, 0xEA], [0xEC, 0xEE]])

    ik_pad = ['0' * 16] * 11 + spr(0x09, 0x09, [[0x41, 0x43], [0x45, 0x47]])
    helmet_idle = _overlay_rows(ik_pad, spr(0x09, 0x09, [[0x09]]), 4, 2)
    helmet_roar = _overlay_rows(ik_pad, spr(0x09, 0x09, [[0x0B]]), 4, 0)

    rebo_idle = spr(0x13, 0x13, [[0x09, 0x0B, 0x0D], [0x0F, 0x11, 0x13]])
    tbird_idle = _mirror_half(spr(0x0D, 0x0D, [[0x11, 0x13], [0x17, 0x29], [0x1D, 0x1F], [0x21, 0x23]]))
    tbird_roar = _mirror_half(spr(0x0D, 0x0D, [[0x11, 0x13], [0x17, 0x2B], [0x25, 0x27], [0x21, 0x23]]))
    lava_frames = _make_lava_link_frames(z2)

    return [
        ('z2_link',        'Link',        spr(0x02, 0x03, [[0x00, 0x02], [0x04, 0x06]]),
                                          spr(0x02, 0x03, [[0x00, 0x02], [0x0C, 0x0E]]),
                                          spr(0x02, 0x03, [[0x00, 0x02], [0x0C, 0x0E]]), M_STD,   18, 42),
        ('z2_lavalink',    'Lava Link',   lava_frames['closed'],
                                          lava_frames['open'],
                                          lava_frames['closed'],                         M_STD,   20, 47),
        ('z2_error',       'Error',       spr(0x06, 0x07, [[0xE8, 0xEA], [0xF0, 0xF2]]),
                                          spr(0x06, 0x07, [[0xE8, 0xEA], [0xEC, 0xEE]]),
                                          spr(0x06, 0x07, [[0xE8, 0xEA], [0xEC, 0xEE]]), M_STD,   20, 42),
        ('z2_bagu',        'Sage',        sage_idle, sage_spell, sage_spell,            M_ROBE,  18, 42),
        ('z2_healer',      'Town Healer', healer_idle, healer_walk, healer_idle,         M_DRESS, 20, 42),
        ('z2_oldwoman',    'Old Woman',   spr(0x06, 0x07, [[0xF4, 0xF6], [0xF8, 0xFA]]),
                                          spr(0x06, 0x07, [[0xF4, 0xF6], [0xFC, 0xFE]]),
                                          spr(0x06, 0x07, [[0xF4, 0xF6], [0xFC, 0xFE]]), M_DRESS, 20, 40),
        ('z2_guard',       'Town Guard',  guard_idle, guard_idle, guard_idle,            M_STD,   20, 43),
        ('z2_bot',         'Bot Slime',   spr(0x14, 0x15, [[0xB6, 0xB8]]),
                                          spr(0x14, 0x15, [[0xB6, 0xB8]]),
                                          spr(0x14, 0x15, [[0xB6, 0xB8]]),               M_DRESS, 20, 26),
        ('z2_lad',         'Young Lad',   spr(0x06, 0x07, [[0xC0, 0xC2], [0xC4, 0xC6]]),
                                          spr(0x06, 0x07, [[0xC0, 0xC2], [0xC8, 0xCA]]),
                                          spr(0x06, 0x07, [[0xC0, 0xC2], [0xC8, 0xCA]]), M_STD,   18, 40),
        ('z2_kid',         'Little Kid',  spr(0x06, 0x07, [[0xF5, 0xF5], [0xB0, 0xBA]]),
                                          spr(0x06, 0x07, [[0xF5, 0xF5], [0xBC, 0xBE]]),
                                          spr(0x06, 0x07, [[0xF5, 0xF5], [0xBC, 0xBE]]), M_STD,   18, 28),
        ('z2_fatwoman',    'Townswoman',  spr(0x06, 0x07, [[0x11, 0x13], [0x15, 0x17]]),
                                          spr(0x06, 0x07, [[0x19, 0x1B], [0x1D, 0x1F]]),
                                          spr(0x06, 0x07, [[0x19, 0x1B], [0x1D, 0x1F]]), M_DRESS, 20, 42),
        ('z2_moblin',      'Moblin',      moblin_idle, moblin_walk, moblin_idle,         M_ENEMY, 18, 43),
        ('z2_daira',       'Daira',       daira_idle,  daira_roar,  daira_idle,          M_DRESS, 20, 44),
        ('z2_ironknuckle', 'Ironknuckle', spr(0x15, 0x15, [[0x41, 0x43], [0x49, 0x4B]]),
                                          spr(0x15, 0x15, [[0x4D, 0x43], [0x51, 0x4B]]),
                                          spr(0x15, 0x15, [[0x4D, 0x43], [0x51, 0x4B]]), M_ROBE,  20, 44),
        ('z2_stalfos',     'Stalfos',     spr(0x14, 0x14, [[0xF0, 0xF2], [0xF4, 0xF6]]),
                                          spr(0x14, 0x14, [[0xF0, 0xF2], [0xF8, 0xFA]]),
                                          spr(0x14, 0x14, [[0xF0, 0xF2], [0xF8, 0xFA]]), M_DRESS, 20, 44),
        ('z2_mago',        'Mago',        spr(0x14, 0x14, [[0xD0, 0xD2], [0xD4, 0xD6]]),
                                          spr(0x14, 0x14, [[0xD8, 0xDA], [0xD4, 0xD6]]),
                                          spr(0x14, 0x14, [[0xD8, 0xDA], [0xD4, 0xD6]]), M_STD,   20, 42),
        ('z2_fokka',       'Fokka',       fokka_idle,  fokka_roar,  fokka_idle,          M_ENEMY, 16, 45),
        ('z2_horsehead',   'Horsehead',   spr(0x09, 0x09, [[0x1B, 0x1D], [0x1F, 0x21]]),
                                          spr(0x09, 0x09, [[0x1B, 0x1D], [0x1F, 0x23]]),
                                          spr(0x09, 0x09, [[0x1B, 0x1D], [0x1F, 0x21]]), M_ROBE,  20, 44),
        ('z2_helmethead',  'Helmethead',  helmet_idle, helmet_roar, helmet_idle,         M_ROBE,  20, 46),
        ('z2_rebonack',    'Rebonack',    rebo_idle,   rebo_idle,   rebo_idle,           M_ENEMY, 28, 37),
        ('z2_carock',      'Carock',      spr(0x15, 0x15, [[0x09, 0x0B, 0x11, 0x13], [0x0D, 0x0F, 0x15, 0x17]]),
                                          spr(0x15, 0x15, [[0x1F, 0x21, 0x23, 0x25], [0x27, 0x29, 0x2B, 0x2D]]),
                                          spr(0x15, 0x15, [[0x09, 0x0B, 0x11, 0x13], [0x0D, 0x0F, 0x15, 0x17]]), M_DRESS, 24, 44),
        ('z2_gooma',       'Gooma',       spr(0x17, 0x17, [[0x09, 0x0B, 0x0D], [0x0F, 0x11, 0x13], [0x15, 0x17, 0x19]]),
                                          spr(0x17, 0x17, [[0x29, 0x2B, 0x2D], [0x1B, 0x1D, 0x1F], [0x21, 0x23, 0xA3]]),
                                          spr(0x17, 0x17, [[0x09, 0x0B, 0x0D], [0x0F, 0x11, 0x13], [0x15, 0x17, 0x19]]), M_DRESS, 24, 47),
        ('z2_thunderbird', 'Thunderbird', tbird_idle,  tbird_roar,  tbird_idle,          M_ENEMY, 26, 46),
        ('z2_darklink',    'Dark Link',   spr(0x02, 0x03, [[0x00, 0x02], [0x04, 0x06]]),
                                          spr(0x02, 0x03, [[0x00, 0x02], [0x0C, 0x0E]]),
                                          spr(0x02, 0x03, [[0x00, 0x02], [0x04, 0x06]]), '333',   18, 42),
        ('z2_bowllady',    'Bowl Lady',   spr(0x06, 0x07, [[0xDC, 0xDE], [0xE0, 0xE2]]),
                                          spr(0x06, 0x07, [[0xDC, 0xDE], [0xE4, 0xE6]]),
                                          spr(0x06, 0x07, [[0xDC, 0xDE], [0xE0, 0xE2]]), M_DRESS, 20, 42),
        ('z2_wiseman',     'Wise Man',    spr(0x06, 0x07, [[0xD0, 0xD2], [0xD4, 0xD6]]),
                                          spr(0x06, 0x07, [[0x74, 0x76], [0xD4, 0xD6]]),
                                          spr(0x06, 0x07, [[0xD0, 0xD2], [0xD4, 0xD6]]), M_STD,   18, 43),
        ('z2_zelda',       'Zelda',       spr(0x03, 0x03, [[0x70, 0x72], [0x74, 0x76]]),
                                          spr(0x03, 0x03, [[0x70, 0x72], [0x74, 0x76]]),
                                          spr(0x03, 0x03, [[0x70, 0x72], [0x74, 0x76]]), M_DRESS, 18, 43),
        ('z2_fairy',       'Fairy',       spr(0x06, 0x06, [[0x68]]),
                                          spr(0x06, 0x06, [[0x6A]]),
                                          spr(0x06, 0x06, [[0x68]]),                     M_DRESS, 14, 24),
        ('z2_lizalfos',    'Wosu',        spr(0x09, 0x09, [[0x31, 0x33], [0x45, 0x47]]),
                                          spr(0x09, 0x09, [[0x31, 0x33], [0x49, 0x4B]]),
                                          spr(0x09, 0x09, [[0x31, 0x33], [0x45, 0x47]]), M_DRESS, 20, 38),
        ('z2_fokkeru',     'Impa',        spr(0x0D, 0x0D, [[0x71, 0x73]]),
                                          spr(0x0D, 0x0D, [[0x75, 0x77]]),
                                          spr(0x0D, 0x0D, [[0x71, 0x73]]),               M_DRESS, 20, 42),
        ('z2_acheman',     'Acheman',     spr(0x08, 0x08, [[0xD0, 0xD2], [0xD4, 0xD6]]),
                                          spr(0x08, 0x08, [[0xD8, 0xDA], [0xD4, 0xD6]]),
                                          spr(0x08, 0x08, [[0xD0, 0xD2], [0xD4, 0xD6]]), M_DRESS, 18, 42),
        ('z2_octorok',     'Octorok',     spr(0x08, 0x08, [[0xBA, 0xBC]]),
                                          spr(0x08, 0x08, [[0xBA, 0xBC]]),
                                          spr(0x08, 0x08, [[0xBA, 0xBC]]),               M_DRESS, 20, 26),
        ('z2_ache',        'Ache',        spr(0x11, 0x11, [[0x80, 0x82]]),
                                          spr(0x11, 0x11, [[0x84, 0x86]]),
                                          spr(0x11, 0x11, [[0x80, 0x82]]),               M_DRESS, 18, 28),
    ]


def _band_top_8(grid: list[list[str]], max_top: int) -> int:
    """Return 8px-aligned top row index of non-transparent pixels in ``grid``."""
    top_y = next((y for y, row in enumerate(grid) if any(ch != '0' for ch in row)), 0)
    return min(max_top, (top_y // 8) * 8)


def _grid_diff_count(a: list[list[str]], b: list[list[str]], y0: int, y1: int) -> int:
    return sum(
        1
        for y in range(max(0, y0), min(len(a), y1))
        for x in range(len(a[0]))
        if a[y][x] != b[y][x]
    )


def _z2_raw_stage_canvases(
    spec: tuple,
    dy_st: int,
    sprite_type: str = 'full',
) -> tuple[list[list[list[str]]], list[int]]:
    """Return 3 unmapped 32x48 raw Z2 canvases (idle, roar, wiggle) and per-frame y_keep."""
    cid, _, s_idle, s_roar, _, _, _, _ = spec
    raw_ident = {'0': '0', '1': '1', '2': '2', '3': '3'}
    idle_src = _crop_top_half(s_idle) if sprite_type == 'top_half' else s_idle
    x0, x1, y0, y1 = _trimmed_bbox(idle_src)
    sw0, sh0 = x1 - x0, y1 - y0
    st_scale = 1.65 if sprite_type == 'top_half' else (1.5 if sh0 <= 18 else 1.3)
    _, _, eff_scale = _proportional_target_size(sw0, sh0, 28, 45, st_scale, min_h=18, max_stretch=1.15)

    def _render_stage(src: list[str], dy_jump: int) -> tuple[list[list[str]], int]:
        src_rows = _crop_top_half(src) if sprite_type == 'top_half' else src
        scaled = _scale_z2_by_factor(src_rows, eff_scale, 30, 46, raw_ident, min_h=16, max_stretch=1.15)
        canvas = [['0'] * 32 for _ in range(48)]
        oy = max(1, 48 - len(scaled) + dy_st + dy_jump) if dy_jump < 0 else (48 - len(scaled) + dy_st)
        ox = (32 - len(scaled[0])) // 2
        _stamp(canvas, scaled, ox, oy)
        return canvas, oy

    c0, oy0 = _render_stage(s_idle, 0)
    band_top = _band_top_8(c0, 32)
    band_end = min(48, band_top + 16)

    # Only small/hovering JUMP_ROAR sprites (sh0 <= 18) jump the full body vertically;
    # taller 32px+ sprites keep dy=0 so tightening f1 to <=24px never slices their waist.
    dy_init = -2 if (cid in _Z2_JUMP_ROAR and sh0 <= 18) else 0
    c1, _ = _render_stage(s_roar, dy_init)
    if _grid_diff_count(c0, c1, band_top, band_end) < 24:
        # Subtle 1px forward nod on the upper band so grounded chars keep feet planted and tile count stays lean.
        for y in range(band_top, band_end):
            c1[y] = c1[y][1:] + ['0']

    # Subtle 1px horizontal head-tilt on the upper 16px/24px band (never shifts rows off 8px tile alignment)
    c2 = [row[:] for row in c0]
    for y in range(band_top, band_end):
        c2[y] = ['0'] + c0[y][:-1]

    y_keeps = [
        _z2_y_keep(cid, 0, oy0),
        _z2_y_keep(cid, 1, max(1, oy0 - 2)),
        band_end,
    ]
    return [c0, c1, c2], y_keeps


def _compile_z2_stage_with_budget(
    raw_canvases: list[list[list[str]]],
    y_keeps: list[int],
    mapping: dict[str, str],
    use_outline: bool,
    max_tiles: int = 27,
) -> tuple[bytes, bytes, list[int]]:
    """Compile 3 Z2 stage canvases, tightening the animated head band to stay within max_tiles."""
    mapped_all = [[[mapping[ch] for ch in row] for row in raw_c] for raw_c in raw_canvases]
    outlined_all = [
        _add_outline(mc, skip_bottom=True) if use_outline else mc
        for mc in mapped_all
    ]
    band_top = _band_top_8(outlined_all[0], 32)
    full_h = 48 - band_top
    candidates = [
        (full_h, 16),
        (24, 24),
        (24, 16),
        (16, 16),
        (16, 8),
        (8, 8),
    ]
    last_err: ValueError | None = None
    for budget in (max_tiles, 34) if max_tiles < 34 else (max_tiles,):
        for h1, h2 in candidates:
            hs = [full_h, h1, h2]
            st_grids: list[list[str]] = []
            for f_i, base_grid in enumerate(outlined_all):
                cur = [row[:] for row in base_grid]
                y_end = min(48, band_top + hs[f_i])
                if f_i in (1, 2) and st_grids:
                    for y in range(0, band_top):
                        cur[y] = list(st_grids[0][y])
                    for y in range(y_end, 48):
                        cur[y] = list(st_grids[0][y])
                st_grids.append([''.join(r) for r in cur])
            try:
                st_tiles, _, st_maps = _pack_frames_local(st_grids, budget)
                return st_tiles, st_maps, [y_keeps[0], min(48, band_top + h1), min(48, band_top + h2)]
            except ValueError as exc:
                last_err = exc
    raise last_err or ValueError(f'Character exceeded {max_tiles} tile budget')


def _build_z2_pool(z2: bytes, char_overrides: dict[str, dict] | None = None) -> list[CastCharacter]:
    specs = _z2_specs(z2)
    pool: list[CastCharacter] = []
    for cid, label, s_idle, s_roar, s_wig, default_map, w_px, base_h in specs:
        ov = (char_overrides or {}).get(cid)
        if ov is not None and not ov.get('included', True):
            continue
        mapping = _mapping_dict(ov.get('mapping', default_map) if ov else default_map)
        use_outline = bool(ov.get('outline', True)) if ov else True
        sprite_type = ov.get('sprite_type', 'full') if ov else 'full'
        if sprite_type not in VALID_SPRITE_TYPES:
            sprite_type = 'full'
        variants: list[CompiledVariant] = []
        for h_idx, (dy_st, dy_ov) in enumerate(((0, 0), (2, 1), (4, 2))):
            # 1. Stage Close-Up 4x6 (32x48)
            raw_canvases, y_keeps = _z2_raw_stage_canvases(
                (cid, label, s_idle, s_roar, s_wig, default_map, w_px, base_h),
                dy_st,
                sprite_type=sprite_type,
            )
            st_tiles, st_maps, _ = _compile_z2_stage_with_budget(
                raw_canvases, y_keeps, mapping, use_outline, max_tiles=27,
            )

            # 2. Stage Overview 2x4 (16x32)
            ov_idle_src = _crop_top_half(s_idle) if sprite_type == 'top_half' else s_idle
            ox0, ox1, oy0, oy1 = _trimmed_bbox(ov_idle_src)
            osw0, osh0 = ox1 - ox0, oy1 - oy0
            ov_scale = 1.15 if sprite_type == 'top_half' else (1.2 if osh0 <= 18 else 0.9)
            _, _, ov_eff = _proportional_target_size(osw0, osh0, 14, 28, ov_scale, min_h=16, max_stretch=1.35)

            def _render_ov(pose_rows: list[str], dy_jump: int) -> tuple[list[list[str]], int]:
                ov_src = _crop_top_half(pose_rows) if sprite_type == 'top_half' else pose_rows
                scaled16 = _scale_z2_by_factor(ov_src, ov_eff, 14, 28, mapping, min_h=14, max_stretch=1.35)
                c16 = [['0'] * 16 for _ in range(32)]
                min_oy = 1 if use_outline else 0
                oy16 = max(min_oy, 32 - len(scaled16) + dy_ov + dy_jump) if dy_jump < 0 else (32 - len(scaled16) + dy_ov)
                _stamp(c16, scaled16, (16 - len(scaled16[0])) // 2, oy16)
                outlined16 = _add_outline(c16, skip_bottom=True) if use_outline else c16
                return outlined16, oy16

            ov0, oy16_0 = _render_ov(s_idle, 0)
            ov_band = _band_top_8(ov0, 16)
            ov_end = min(32, ov_band + 16)
            ov_tiles = b''
            ov_r0 = 0
            ov_maps = b''
            if cid in _Z2_JUMP_ROAR:
                # Only allow full-sprite jump when all rows below ov_band fit cleanly without mid-body slicing.
                ov1_jump, _ = _render_ov(s_roar, -2)
                ov_grids = [[''.join(r) for r in ov0], [''.join(r) for r in ov1_jump]]
                try:
                    t_try, r0_try, m_try = _pack_frames_local(ov_grids, 13, row0_first=True)
                    if r0_try <= 4:
                        ov_tiles, ov_r0, ov_maps = t_try, r0_try, m_try
                except ValueError:
                    pass
            if not ov_tiles:
                ov1, _ = _render_ov(s_roar, 0)
                if _grid_diff_count(ov0, ov1, ov_band, ov_end) < 12:
                    for y in range(ov_band, ov_end):
                        ov1[y] = ov1[y][1:] + ['0']
                for h_ov in (16, 8):
                    y_end = min(32, ov_band + h_ov)
                    ov_frame1 = [ov1[y] if ov_band <= y < y_end else ov0[y] for y in range(32)]
                    if _grid_diff_count(ov0, ov_frame1, ov_band, y_end) < 8:
                        ov_frame1 = [
                            (ov0[y][1:] + ['0']) if ov_band <= y < y_end else ov0[y]
                            for y in range(32)
                        ]
                    ov_grids = [
                        [''.join(r) for r in ov0],
                        [''.join(r) for r in ov_frame1],
                    ]
                    try:
                        ov_tiles, ov_r0, ov_maps = _pack_frames_local(ov_grids, 13, row0_first=True)
                        if ov_r0 <= 4:
                            break
                    except ValueError:
                        continue
            assert ov_tiles and ov_r0 <= 4, f'{cid} h={h_idx} used {ov_r0} row-0 overview tiles (>4)'

            # 3. Face-Off 6x10 upper body (48x80: character y=0..63 on 44x16 box at y=64..79)
            fx0, fx1, fy0, fy1 = _trimmed_bbox(s_idle)
            fsw0, fsh0 = fx1 - fx0, fy1 - fy0
            fo_target = (1.6 if fsh0 <= 18 else (1.35 if fsh0 <= 36 else 1.0)) * (1.0 - 0.06 * h_idx)
            _, _, fo_eff = _proportional_target_size(fsw0, fsh0, 38, 56, fo_target, min_h=20, max_stretch=1.15)
            fo_grids: list[list[str]] = []
            for f_i, src in enumerate((s_idle, s_roar)):
                scaled_fo = _scale_z2_by_factor(src, fo_eff, 40, 60, mapping, min_h=18, max_stretch=1.15)
                c_fo = [['0'] * 48 for _ in range(80)]
                dy_jump = -2 if (f_i == 1 and cid in _Z2_JUMP_ROAR) else 0
                oy_fo = 64 - len(scaled_fo) + dy_jump
                ox_fo = (48 - len(scaled_fo[0])) // 2
                _stamp(c_fo, scaled_fo, ox_fo, oy_fo)
                outlined_fo = _add_outline(c_fo, skip_bottom=(dy_jump == 0)) if use_outline else c_fo
                _draw_faceoff_box(outlined_fo)
                fo_grids.append([''.join(r) for r in outlined_fo])
            fo_tiles, _, fo_maps = _pack_frames_local(fo_grids, 72)

            variants.append(CompiledVariant(st_tiles, st_maps, ov_tiles, ov_r0, ov_maps, fo_tiles, fo_maps))
        pool.append(CastCharacter(cid, label, 'z2', (variants[0], variants[1], variants[2])))
    return pool


def export_dashboard_sprites(z2: bytes) -> list[dict]:
    """Export raw 32x48 frames (full & top_half, idle/roar/wiggle) for the web dashboard."""
    out: list[dict] = []
    frames24, _, _, _, _, b_specs = _prepare_barba_assets(z2)
    for spec in b_specs:
        cid, label = spec[0], spec[1]
        grids = _barba_stage_grids(frames24, spec, 0, sprite_type='full')
        grids_top = _barba_stage_grids(frames24, spec, 0, sprite_type='top_half')
        out.append({
            'id': cid,
            'pool': 'barba',
            'label': label,
            'y_keep': 48,
            'raw_frames': [''.join(g) for g in grids],
            'raw_frames_top': [''.join(g) for g in grids_top],
        })
    for spec in _z2_specs(z2):
        cid, label = spec[0], spec[1]
        default_map = _mapping_dict(spec[5])
        canvases, y_keeps = _z2_raw_stage_canvases(spec, 0, sprite_type='full')
        canvases_top, y_keeps_top = _z2_raw_stage_canvases(spec, 0, sprite_type='top_half')
        _, _, eff_yks = _compile_z2_stage_with_budget(canvases, y_keeps, default_map, True, max_tiles=34)
        _, _, eff_yks_top = _compile_z2_stage_with_budget(canvases_top, y_keeps_top, default_map, True, max_tiles=34)
        out.append({
            'id': cid,
            'pool': 'z2',
            'label': label,
            'y_keeps': eff_yks,
            'y_keeps_top': eff_yks_top,
            'raw_frames': [''.join(''.join(row) for row in c) for c in canvases],
            'raw_frames_top': [''.join(''.join(row) for row in c) for c in canvases_top],
        })
    return out


def build_all_cast_pools(
    z2: bytes,
    config: dict | None = None,
) -> tuple[list[CastCharacter], list[CastCharacter]]:
    """Build and validate the included Barba-side and Zelda II-side character pools."""
    cfg = config if config is not None else load_cast_config()
    by_id = {c['id']: c for c in cfg.get('characters', [])}
    barba_included = {
        c['id'] for c in cfg.get('characters', [])
        if c.get('pool') == 'barba' and c.get('included', True)
    }
    if not any(c.get('pool') == 'barba' for c in cfg.get('characters', [])):
        barba_included = None  # type: ignore[assignment]
    barba_pool = _build_barba_pool(z2, barba_included, by_id)
    z2_pool = _build_z2_pool(z2, by_id)
    assert len(barba_pool) >= 5, f'Need at least 5 included Barba characters, got {len(barba_pool)}'
    assert len(z2_pool) >= 5, f'Need at least 5 included Z2 characters, got {len(z2_pool)}'
    return barba_pool, z2_pool
