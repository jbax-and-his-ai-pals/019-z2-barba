"""Compile Barba assets into Family Feud (USA) CHR banks and PRG tile/attr blocks.

Recipe-only source: extracts Barba boss pixels from ``roms/z2.nes`` and
preserves protected stage/podium/UI tiles from ``roms/feud.nes`` at build time.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from boss_art import make_frames, resize_x, source_head
from nes import decode_tile, encode_tile, write_png


def _u8(prg: bytes | bytearray, addr: int) -> int:
    return prg[addr - 0x8000]


def _get_block(prg: bytes | bytearray, idx: int) -> tuple[int, int, list[int], int, int]:
    addr = _u8(prg, 0xDB12 + idx) | (_u8(prg, 0xDBDF + idx) << 8)
    aaddr = _u8(prg, 0xF218 + idx) | (_u8(prg, 0xF2E5 + idx) << 8)
    w, h = _u8(prg, addr), _u8(prg, addr + 1)
    tiles = [_u8(prg, addr + 2 + k) for k in range(w * h)]
    return w, h, tiles, addr, aaddr


def _decode_rle_screen(prg: bytes | bytearray, chr_rom: bytes | bytearray, screen_idx: int) -> list[int]:
    """Decode one compressed nametable+attribute screen from CHR banks 0E/0F ($A36D)."""
    base = 0xA410 + screen_idx * 4 - 0x8000
    b1, b2 = prg[base + 1], prg[base + 2]
    pos = (b2 >> 4) * 4096 + (((b2 & 0x0F) << 8) | b1)
    r11 = chr_rom[pos]
    pos += 1
    out: list[int] = []
    while len(out) < 1024:
        a = chr_rom[pos]
        pos += 1
        if a != r11:
            out.append(a)
        else:
            cnt = chr_rom[pos]
            pos += 1
            if cnt == 0:
                break
            val = chr_rom[pos]
            pos += 1
            out.extend([val] * cnt)
    return out


def _to_feud_indices(rows: list[str], flip_h: bool = False) -> list[str]:
    """Map Z2 Barba indices (0=trans,1=scales,2=belly,3=horns/eye) -> Feud (0,1=light,2=body,3=black)."""
    out = []
    for r in rows:
        rr = r[::-1] if flip_h else r
        out.append(''.join('2' if c == '1' else ('1' if c in ('2', '3') else '0') for c in rr))
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
        for x, ch in enumerate(r):
            if ch != '0' and 0 <= oy + y < h and 0 <= ox + x < w:
                canvas[oy + y][ox + x] = ch


def _build_portrait_4x6(frames24: dict[str, list[str]], kind: str, frame_idx: int, flip_h: bool) -> list[str]:
    """Build one 32x48 (4x6 tile) Barba portrait for Stage Close-Up & Fast Money."""
    pose_map = {
        'std':    ('idle', 'attack', 'idle', 'idle', 'walk1'),
        'tall':   ('walk0', 'attack', 'walk0', 'walk0', 'walk2'),
        'crouch': ('crouch', 'crouch-attack', 'crouch', 'crouch', 'crouch'),
        'up':     ('idle', 'up', 'idle', 'idle', 'idle'),
    }
    pose = pose_map[kind][frame_idx]
    width = 20 if kind == 'std' else 22
    raw = resize_x(frames24[pose], width)
    mapped = _to_feud_indices(raw[:-1], flip_h=flip_h)  # 47 rows -> y=1..47
    canvas = [['0'] * 32 for _ in range(48)]
    _stamp(canvas, mapped, (32 - width) // 2, 1)
    return [''.join(r) for r in _add_outline(canvas, skip_bottom=True)]


def _build_small_2x4(frames16: dict[str, list[str]], kind: str, frame_idx: int, flip_h: bool) -> list[str]:
    """Build one 16x32 (2x4 tile) Barba portrait for Stage Overview."""
    if kind == 'crouch':
        pose = 'crouch' if frame_idx == 0 else 'crouch-attack'
        slice_rows = frames16[pose][17:48]
    elif kind == 'up':
        pose = 'up' if frame_idx == 1 else 'idle'
        slice_rows = frames16[pose][0:31]
    else:
        pose = 'idle' if frame_idx == 0 else 'attack'
        slice_rows = frames16[pose][0:31]
    raw = resize_x(slice_rows, 14)
    mapped = _to_feud_indices(raw, flip_h=flip_h)
    canvas = [['0'] * 16 for _ in range(32)]
    _stamp(canvas, mapped, 1, 1)
    return [''.join(r) for r in _add_outline(canvas, skip_bottom=True)]


def _build_host_bust_4x6(z2: bytes, jaw: str, flip_h: bool) -> list[str]:
    """Build 32x48 (4x6 tile) Tuxedo Host Barba for Face-Off center podium."""
    raw = resize_x(source_head(z2, jaw), 22)
    head = _to_feud_indices(raw, flip_h=flip_h)
    canvas = [['0'] * 32 for _ in range(48)]
    for y in range(19, 48):
        pad = 2 if y == 19 else (1 if y == 20 else 0)
        for x in range(6 + pad, 26 - pad):
            canvas[y][x] = '3'
    for y in range(19, 34):
        half_v = max(1, (34 - y) // 4)
        for x in range(16 - half_v, 16 + half_v):
            canvas[y][x] = '1'
    for y in range(21, 24):
        for x in range(13, 19):
            canvas[y][x] = '1'
    canvas[22][15] = '3'
    canvas[22][16] = '3'
    for y in range(24, 34):
        canvas[y][15] = '3'
        canvas[y][16] = '3'
    canvas[29][21] = '1'
    canvas[30][22] = '1'
    for y in range(39, 46):
        for x in range(13, 19):
            canvas[y][x] = '1'
    for y in range(40, 44):
        for x in (11, 12, 19, 20):
            canvas[y][x] = '2'
    _stamp(canvas, head, 5, 2)
    return [''.join(r) for r in _add_outline(canvas, skip_bottom=True)]


def _build_host_walk_6x12(z2: bytes, jaw: str, stride: int, flip_h: bool, *, front: bool = False, back: bool = False) -> list[str]:
    """Build 48x96 (6x12 tile) Tuxedo Host Barba for Walking Host OAM."""
    raw = resize_x(source_head(z2, jaw), 22)
    head = _to_feud_indices(raw, flip_h=flip_h)
    canvas = [['0'] * 48 for _ in range(96)]

    if front or back:
        for y in range(28, 66):
            pad = 2 if y < 31 else (1 if y < 34 else 0)
            for x in range(15 + pad, 33 - pad):
                canvas[y][x] = '3'
        if front:
            for y in range(29, 45):
                half_v = max(1, (45 - y) // 4)
                for x in range(24 - half_v, 24 + half_v):
                    canvas[y][x] = '1'
            for y in range(31, 45):
                canvas[y][23] = '3'
                canvas[y][24] = '3'
            for y in range(42, 47):
                for x in range(30, 34):
                    canvas[y][x] = '2'
            for y in range(37, 42):
                for x in range(30, 34):
                    canvas[y][x] = '1' if y < 40 else '3'
        for lx in (17, 26):
            for y in range(66, 88):
                for dx in range(5):
                    canvas[y][lx + dx] = '3'
            for dx in range(6):
                canvas[88][lx + dx] = '1'
                canvas[89][lx + dx] = '1'
                canvas[90][lx + dx] = '3'
        if back:
            for y in range(12, 27):
                pad = 1 if y in (12, 13) else 0
                for x in range(18 + pad, 30 - pad):
                    canvas[y][x] = '2'
            for y in range(14, 26, 3):
                canvas[y][23] = '1'
                canvas[y][24] = '1'
            for y in range(9, 13):
                for x in (19, 20, 27, 28):
                    canvas[y][x] = '1'
            for y in range(26, 29):
                for x in range(20, 28):
                    canvas[y][x] = '1'
        else:
            _stamp(canvas, head, 13, 12)
        return [''.join(r) for r in _add_outline(canvas)]

    d = 1 if flip_h else -1
    cx = 24
    for y in range(28, 65):
        w_left = 6 if y < 31 else (8 if y < 56 else 7)
        w_right = 5 if y < 31 else (7 if y < 58 else 6)
        if not flip_h:
            w_left, w_right = w_right, w_left
        for x in range(cx - w_left, cx + w_right):
            canvas[y][x] = '3'
    sx = cx + (5 * d)
    for y in range(29, 54):
        canvas[y][sx] = '1'
        canvas[y][sx + d] = '1'
    canvas[29][sx - d] = '1'
    canvas[30][sx + 2 * d] = '1'
    canvas[40][cx + 2 * d] = '1'

    strides = [(-4, 4, 0, 0), (0, 6, 0, -3), (0, 0, 0, 0), (-6, 2, -3, 0)]
    b_off, f_off, b_y, f_y = strides[stride % 4]
    for leg_x, leg_dy in ((cx - 3 + b_off, b_y), (cx + 1 + f_off, f_y)):
        for y in range(65, 88 + leg_dy):
            for dx in range(4):
                canvas[y][leg_x + dx] = '3'
        sy = 88 + leg_dy
        for dx in range(-1, 6):
            xx = leg_x + (dx if d > 0 else 3 - dx)
            canvas[sy][xx] = '1'
            canvas[sy + 1][xx] = '1' if 1 <= dx <= 4 else '3'
            canvas[sy + 2][xx] = '3'

    hand_x = cx + 12 * d
    for y in range(44, 50):
        x_a, x_b = sorted((cx + 4 * d, hand_x - 2 * d))
        for x in range(x_a, x_b + 1):
            canvas[y][x] = '3'
    for y in range(44, 49):
        canvas[y][hand_x - 2 * d] = '1'
    for y in range(43, 48):
        for dx in (-1, 0, 1):
            canvas[y][hand_x + dx] = '2'
    for y in range(37, 42):
        for dx in (-1, 0, 1):
            canvas[y][hand_x + dx + d] = '1' if y < 40 else '3'
    canvas[42][hand_x + d] = '3'
    for y in range(25, 29):
        for x in range(cx - 2, cx + 4):
            canvas[y][x] = '2'
    _stamp(canvas, head, 15 if flip_h else 11, 11)
    return [''.join(r) for r in _add_outline(canvas)]


def _build_host_small_8x8(z2: bytes, jaw: str, stride: int, *, front: bool = False) -> list[str]:
    """Build 64x64 (8x8 tile) Tuxedo Host Barba for Stage Overview OAM."""
    raw = resize_x(source_head(z2, jaw), 18)
    head = _to_feud_indices(raw, flip_h=True)
    canvas = [['0'] * 64 for _ in range(64)]
    cx = 32
    if front:
        for y in range(28, 48):
            for x in range(cx - 6, cx + 6):
                canvas[y][x] = '3'
        for y in range(29, 38):
            canvas[y][cx - 1] = '1'
            canvas[y][cx] = '1'
        for lx in (cx - 5, cx + 2):
            for y in range(48, 59):
                for dx in range(3):
                    canvas[y][lx + dx] = '3'
            for dx in range(4):
                canvas[59][lx + dx] = '1'
        if stride % 2 == 1:
            for y in range(22, 30):
                for x in range(cx - 11, cx - 7):
                    canvas[y][x] = '2' if y < 25 else '3'
        _stamp(canvas, head, cx - 9, 13)
        return [''.join(r) for r in _add_outline(canvas)]

    for y in range(28, 48):
        for x in range(cx - 5, cx + 6):
            canvas[y][x] = '3'
    for y in range(29, 40):
        canvas[y][cx + 3] = '1'
    b_off, f_off = ((-3, 3), (0, 0))[stride % 2]
    for lx in (cx - 3 + b_off, cx + f_off):
        for y in range(48, 59):
            for dx in range(3):
                canvas[y][lx + dx] = '3'
        for dx in range(5):
            canvas[59][lx + dx] = '1'
    for y in range(32, 36):
        canvas[y][cx + 9] = '1' if y < 34 else '3'
    canvas[36][cx + 8] = '2'
    canvas[36][cx + 9] = '2'
    _stamp(canvas, head, cx - 7, 13)
    return [''.join(r) for r in _add_outline(canvas)]


def _decode_orig_block(prg: bytes | bytearray, chr_rom: bytes | bytearray, bank: int, idx: int) -> tuple[list[list[str]], list[list[int]]]:
    w, h, tiles, _, aaddr = _get_block(prg, idx)
    grid = [['0'] * (w * 8) for _ in range(h * 8)]
    attrs = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            t = tiles[r * w + c]
            attrs[r][c] = _u8(prg, aaddr + 2 + r * w + c) & 3
            if t != 0:
                dec = decode_tile(chr_rom[bank * 4096 + t * 16 : bank * 4096 + (t + 1) * 16])
                for y in range(8):
                    for x in range(8):
                        grid[r * 8 + y][c * 8 + x] = str(dec[y][x])
    return grid, attrs


def _build_faceoff_contestant(
    frames24: dict[str, list[str]],
    orig_grid: list[list[str]],
    orig_attr: list[list[int]],
    pal_id: int,
    jaw: str,
    phase: int,
    tall_h: int = 70,
) -> tuple[list[str], list[list[int]]]:
    """32x96 (4x12) Barba contestant composited behind preserved podium/buzzer/floor.

    Ends cleanly at y=79 (row 9) above the yellow stage floor (rows 10..11),
    where Pal 0 solid yellow floor fills cols 2..3 so both BG and OAM blend cleanly.
    """
    base = frames24['idle' if jaw == 'closed' else ('windup' if jaw == 'half' else 'attack')]
    head = resize_x(base[:16], 20)
    neck = resize_x(base[16:32], 18)
    canvas = [['0'] * 32 for _ in range(96)]
    top_y = 79 - tall_h
    for y in range(top_y + 14, 79):
        sway = (0, -1, 0, 1)[((y // 8) + phase) % 4]
        row = neck[y % 16]
        _stamp(canvas, _to_feud_indices([row]), 13 + sway, y)
    for y in range(46, 49):
        for x in range(7, 14):
            canvas[y][x] = '2'
    _stamp(canvas, _to_feud_indices(head), 10, top_y)
    outlined = _add_outline(canvas, skip_bottom=False)

    attrs = [[pal_id] * 4 for _ in range(12)]
    for y in range(96):
        r = y // 8
        for x in range(32):
            c = x // 8
            is_podium = (r >= 6 and c <= 1 and orig_grid[y][x] != '0')
            is_buzzer = (r == 5 and c == 0 and x < 10 and y >= 42 and orig_grid[y][x] != '0')
            if is_podium or is_buzzer:
                outlined[y][x] = orig_grid[y][x]
                if r >= 6 and c <= 1:
                    attrs[r][c] = 0
                elif r == 5 and c == 0:
                    attrs[r][c] = orig_attr[r][c]
            elif r >= 10 and c >= 2:
                # Solid yellow stage floor matching r24..r25 ($27 = index '2' in Pal 0)
                outlined[y][x] = '2'
                attrs[r][c] = 0
            elif r >= 10 and c <= 1:
                attrs[r][c] = 0
    return [''.join(r) for r in outlined], attrs


def _pack_bank(
    chr_buf: bytearray,
    bank: int,
    avail_tiles: list[int],
    grids: dict[int, list[str]],
    *,
    protected_pool_tiles: list[int] = (),
    row0_priority: bool = False,
) -> dict[int, list[int]]:
    """Encode and deduplicate 8x8 tiles for ``grids`` into ``chr_buf`` at ``bank``."""
    pool: dict[bytes, int] = {}
    # Seed pool with protected tiles (e.g. podium/floor) so matching blocks reuse them for free!
    for tid in protected_pool_tiles:
        off = bank * 4096 + tid * 16
        enc = bytes(chr_buf[off : off + 16])
        if any(enc) and enc not in pool:
            pool[enc] = tid

    avail_iter = iter(avail_tiles)
    packed: dict[int, list[int]] = {}

    def alloc_tile(enc: bytes) -> int:
        tid = pool.get(enc)
        if tid is not None:
            return tid
        try:
            tid = next(avail_iter)
        except StopIteration as exc:
            raise ValueError(f'CHR bank 0x{bank:02X} overflowed available tile budget ({len(avail_tiles)})') from exc
        pool[enc] = tid
        off = bank * 4096 + tid * 16
        chr_buf[off : off + 16] = enc
        return tid

    # Optionally allocate row 0 of every block first (keeps Stage Overview r16 inside R0 < 0x80)
    if row0_priority:
        for idx, rows in grids.items():
            w = len(rows[0]) // 8
            for c in range(w):
                sub = [rows[y][c * 8 : (c + 1) * 8] for y in range(8)]
                if any(ch != '0' for line in sub for ch in line):
                    alloc_tile(encode_tile(sub))

    for idx, rows in grids.items():
        h = len(rows) // 8
        w = len(rows[0]) // 8
        tids: list[int] = []
        for r in range(h):
            for c in range(w):
                sub = [rows[r * 8 + y][c * 8 : (c + 1) * 8] for y in range(8)]
                if all(ch == '0' for line in sub for ch in line):
                    tids.append(0)
                    continue
                tids.append(alloc_tile(encode_tile(sub)))
        packed[idx] = tids

    for unused in avail_iter:
        off = bank * 4096 + unused * 16
        chr_buf[off : off + 16] = b'\x00' * 16
    return packed


def _write_block_and_attr(
    prg_buf: bytearray,
    idx: int,
    tids: list[int],
    attrs: list[list[int]] | None = None,
) -> None:
    w, h, _, addr, aaddr = _get_block(prg_buf, idx)
    assert len(tids) == w * h, f'Block {idx} expected {w*h} tiles, got {len(tids)}'
    prg_buf[addr + 2 - 0x8000 : addr + 2 + w * h - 0x8000] = bytes(tids)
    if attrs is not None:
        flat = [attrs[r][c] & 3 for r in range(h) for c in range(w)]
        prg_buf[aaddr + 2 - 0x8000 : aaddr + 2 + w * h - 0x8000] = bytes(flat)


def _encode_rle_screen(data: list[int]) -> bytes:
    """Encode a 1024-byte nametable+attribute screen using Family Feud's RLE format."""
    assert len(data) == 1024
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    r11 = min(range(256), key=lambda b: counts[b])
    out = bytearray([r11])
    i = 0
    while i < 1024:
        val = data[i]
        run = 1
        while i + run < 1024 and data[i + run] == val and run < 255:
            run += 1
        if run >= 4 or val == r11:
            out.extend((r11, run, val))
            i += run
        else:
            out.append(val)
            i += 1
    out.extend((r11, 0x00))
    return bytes(out)


def _outline_logo(canvas: list[list[str]]) -> list[str]:
    """Convert '#' fill on '2' yellow background into '3' fill + '1' black outline."""
    h, w = len(canvas), len(canvas[0])
    out = [row[:] for row in canvas]
    for y in range(h):
        for x in range(w):
            if canvas[y][x] == '#':
                out[y][x] = '3'
            elif canvas[y][x] == '2':
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and canvas[ny][nx] == '#':
                        out[y][x] = '1'
                        break
    return [''.join(r) for r in out]


# 24px-tall Western slab-serif glyphs ('#' = fill; '1' black outline added around '#' on '2' yellow bg)
_TITLE_GLYPHS: dict[str, list[str]] = {
    'B': [
        '................',
        '############....',
        '############....',
        '#..###....###...',
        '...###.....###..',
        '...###.....###..',
        '...###.....###..',
        '...###.....###..',
        '...###....###...',
        '...#########....',
        '...#########....',
        '...###....###...',
        '...###.....###..',
        '...###.....###..',
        '...###.....###..',
        '...###.....###..',
        '...###.....###..',
        '...###.....###..',
        '...###....###...',
        '#..###...###....',
        '###########.....',
        '###########.....',
        '................',
        '................',
    ],
    'A': [
        '..................',
        '......######......',
        '.....########.....',
        '....####..####....',
        '....###....###....',
        '...###......###...',
        '...###......###...',
        '..###........###..',
        '..###........###..',
        '..##############..',
        '..##############..',
        '.###..........###.',
        '.###..........###.',
        '.###..........###.',
        '.###..........###.',
        '.###..........###.',
        '.###..........###.',
        '.###..........###.',
        '.###..........###.',
        '.###..........###.',
        '#####........#####',
        '#####........#####',
        '..................',
        '..................',
    ],
    'R': [
        '................',
        '############....',
        '############....',
        '#..###....###...',
        '...###.....###..',
        '...###.....###..',
        '...###.....###..',
        '...###.....###..',
        '...###....###...',
        '...#########....',
        '...#########....',
        '...###...###....',
        '...###....###...',
        '...###....###...',
        '...###.....###..',
        '...###.....###..',
        '...###.....###..',
        '...###.....###..',
        '...###.....###..',
        '#..###.....###..',
        '#######....####.',
        '#######....####.',
        '................',
        '................',
    ],
    "'": [
        '......',
        '.####.',
        '.####.',
        '.####.',
        '..###.',
        '.###..',
        '......',
        '......',
        '......',
        '......',
        '......',
        '......',
        '......',
        '......',
        '......',
        '......',
        '......',
        '......',
        '......',
        '......',
        '......',
        '......',
        '......',
        '......',
    ],
    'S': [
        '................',
        '...#########....',
        '..###########...',
        '.###.......###..',
        '.###.......###..',
        '.###........##..',
        '.###............',
        '..####..........',
        '...######.......',
        '.....######.....',
        '.......######...',
        '.........#####..',
        '...........###..',
        '...........###..',
        '...........###..',
        '.##........###..',
        '.###.......###..',
        '.###.......###..',
        '.###.......###..',
        '..###########...',
        '...#########....',
        '................',
        '................',
        '................',
    ],
    'E': [
        '................',
        '##############..',
        '##############..',
        '#..###......##..',
        '...###.......#..',
        '...###..........',
        '...###..........',
        '...###..........',
        '...###..........',
        '...###...#......',
        '...#######......',
        '...#######......',
        '...###...#......',
        '...###..........',
        '...###..........',
        '...###..........',
        '...###..........',
        '...###.......#..',
        '#..###......##..',
        '##############..',
        '##############..',
        '................',
        '................',
        '................',
    ],
    'F': [
        '................',
        '##############..',
        '##############..',
        '#..###......##..',
        '...###.......#..',
        '...###..........',
        '...###..........',
        '...###..........',
        '...###..........',
        '...###...#......',
        '...#######......',
        '...#######......',
        '...###...#......',
        '...###..........',
        '...###..........',
        '...###..........',
        '...###..........',
        '...###..........',
        '#..###..........',
        '#######.........',
        '#######.........',
        '................',
        '................',
        '................',
    ],
}


def apply_barba_title(prg_buf: bytearray, chr_buf: bytearray) -> int:
    """Replace the Screen 1 'FAMILY FEUD' title logo with 'BARBA'S BEEF'."""
    s1 = _decode_rle_screen(prg_buf, chr_buf, 1)
    s13 = _decode_rle_screen(prg_buf, chr_buf, 13)
    s14 = _decode_rle_screen(prg_buf, chr_buf, 14)

    letter_coords = (
        {(r, c) for r in range(9, 14) for c in range(8, 25)}
        | {(r, c) for r in range(14, 19) for c in range(9, 24)}
    )
    letter_coords.discard((9, 24))
    letter_coords.discard((18, 23))
    letter_tiles = {s1[r * 32 + c] for r, c in letter_coords} - {0x00, 0x38}
    outside_tiles = {s1[r * 32 + c] for r in range(30) for c in range(32) if (r, c) not in letter_coords}
    other_screens = set(s13[:960]) | set(s14[:960])
    avail_tiles = sorted((letter_tiles - outside_tiles - other_screens) | (set(range(256)) - set(s1[:960]) - other_screens))

    # Clear all old logo tiles (including the protruding F serifs in rows 9, 13, 14, 18)
    for r, c in letter_coords:
        if s1[r * 32 + c] not in outside_tiles:
            s1[r * 32 + c] = 0x38

    def render_word(text: str, width_px: int, gap_px: int) -> list[str]:
        total_w = sum(len(_TITLE_GLYPHS[ch][0]) for ch in text) + gap_px * (len(text) - 1)
        ox = (width_px - total_w) // 2
        canvas = [['2'] * width_px for _ in range(24)]
        for ch in text:
            g = _TITLE_GLYPHS[ch]
            for y, row in enumerate(g):
                for x, px in enumerate(row):
                    if px == '#' and 0 <= ox + x < width_px:
                        canvas[y][ox + x] = '#'
            ox += len(g[0]) + gap_px
        return _outline_logo(canvas)

    top_rows = render_word("BARBA'S", 16 * 8, 1)
    bot_rows = render_word('BEEF', 14 * 8, 3)

    tm_art = [
        '00000200000',
        '22022202020',
        '22022202020',
        '22022202220',
        '22022202220',
    ]
    bot_list = [list(r) for r in bot_rows]
    for y, trow in enumerate(tm_art):
        for x, px in enumerate(trow):
            bot_list[17 + y][14 * 8 - 14 + x] = px
    bot_rows = [''.join(r) for r in bot_list]

    solid_yellow = encode_tile(['2' * 8 for _ in range(8)])
    pool: dict[bytes, int] = {solid_yellow: 0x38}
    avail_iter = iter(avail_tiles)
    used_count = 0

    def stamp_rect(rows_24: list[str], r0: int, c0: int, w_tiles: int) -> None:
        nonlocal used_count
        for tr in range(3):
            for tc in range(w_tiles):
                sub = [rows_24[tr * 8 + y][tc * 8 : (tc + 1) * 8] for y in range(8)]
                enc = encode_tile(sub)
                tid = pool.get(enc)
                if tid is None:
                    tid = next(avail_iter)
                    pool[enc] = tid
                    off = 0x09000 + tid * 16
                    chr_buf[off : off + 16] = enc
                    used_count += 1
                s1[(r0 + tr) * 32 + (c0 + tc)] = tid

    stamp_rect(top_rows, 10, 8, 16)
    stamp_rect(bot_rows, 15, 9, 14)

    for unused in avail_iter:
        off = 0x09000 + unused * 16
        chr_buf[off : off + 16] = b'\x00' * 16

    rle = _encode_rle_screen(s1)
    max_len = 0x0E801 - 0x0E505
    assert len(rle) <= max_len, f'Screen 1 RLE overflowed ({len(rle)} > {max_len})'
    chr_buf[0x0E505 : 0x0E505 + len(rle)] = rle
    if len(rle) < max_len:
        chr_buf[0x0E505 + len(rle) : 0x0E801] = b'\x00' * (max_len - len(rle))
    return used_count


def _write_rle_screen_inplace(
    prg_buf: bytearray,
    chr_buf: bytearray,
    screen_idx: int,
    data: list[int],
    max_len: int,
) -> None:
    """Re-encode ``data`` (1024 bytes) into ``screen_idx``'s existing RLE slot."""
    base = 0xA410 + screen_idx * 4 - 0x8000
    b1, b2 = prg_buf[base + 1], prg_buf[base + 2]
    pos = (b2 >> 4) * 4096 + (((b2 & 0x0F) << 8) | b1)
    rle = _encode_rle_screen(data)
    assert len(rle) <= max_len, f'Screen {screen_idx} RLE overflowed ({len(rle)} > {max_len})'
    chr_buf[pos : pos + len(rle)] = rle
    if len(rle) < max_len:
        chr_buf[pos + len(rle) : pos + max_len] = b'\x00' * (max_len - len(rle))


def apply_title_build_number(prg_buf: bytearray, chr_buf: bytearray, build_number: int) -> None:
    """Write 5x7 digits '0'..'9' into empty Bank 0B tiles $B6..$BF and stamp B<N> on Screen 0 row 1 col 26."""
    s0 = _decode_rle_screen(prg_buf, chr_buf, 0)
    digit_rows = {
        '0': ['..####..','.##..##.','.##.###.','.######.','.##..##.','.##..##.','..####..','........'],
        '1': ['...##...','..###...','...##...','...##...','...##...','...##...','.######.','........'],
        '2': ['..####..','.##..##.','.....##.','..####..','.##.....','.##.....','.######.','........'],
        '3': ['..####..','.##..##.','.....##.','...###..','.....##.','.##..##.','..####..','........'],
        '4': ['....##..','...###..','..####..','.##.##..','.######.','....##..','....##..','........'],
        '5': ['.######.','.##.....','.#####..','.....##.','.....##.','.##..##.','..####..','........'],
        '6': ['..####..','.##.....','.#####..','.##..##.','.##..##.','.##..##.','..####..','........'],
        '7': ['.######.','.....##.','....##..','...##...','..##....','..##....','..##....','........'],
        '8': ['..####..','.##..##.','.##..##.','..####..','.##..##.','.##..##.','..####..','........'],
        '9': ['..####..','.##..##.','.##..##.','..#####.','.....##.','....##..','..###...','........'],
    }
    for d_idx in range(10):
        tid = 0xB6 + d_idx
        off = 0x0B000 + tid * 16
        assert chr_buf[off : off + 16] == b'\x00' * 16, f'Feud Bank 0B tile ${tid:02X} not empty'
        chr_buf[off : off + 16] = encode_tile([r.replace('#', '3').replace('.', '0') for r in digit_rows[str(d_idx)]])
    tag = [0x13 if ch == 'B' else 0xB6 + int(ch) for ch in f'B{build_number}']
    assert all(v == 0 for v in s0[1 * 32 + 26 : 1 * 32 + 26 + len(tag)])
    s0[1 * 32 + 26 : 1 * 32 + 26 + len(tag)] = tag
    rle = _encode_rle_screen(s0)
    # Relocate Screen 0 RLE to unused 0x0EE00 in CHR bank 0E and update Screen 0 pointer ($A411..$A412).
    reloc = 0x0EE00
    assert len(rle) <= 0x120 and chr_buf[reloc : reloc + len(rle)] == b'\x00' * len(rle)
    chr_buf[reloc : reloc + len(rle)] = rle
    ptr_off = 0xA410 - 0x8000
    prg_buf[ptr_off + 1] = reloc & 0xFF
    prg_buf[ptr_off + 2] = ((reloc >> 12) << 4) | ((reloc >> 8) & 0x0F)


def apply_barba_branding(prg_buf: bytearray, chr_buf: bytearray) -> None:
    """Replace remaining 'FAMILY FEUD' text/plaques and 'FF' podium emblems with 'BARBA'S BEEF' / 'BB'."""
    # 1. Bank 0B text screens: Screen 0 (credits), Screen 5 (1P/2P menu), Screen 11 (win account)
    s0 = _decode_rle_screen(prg_buf, chr_buf, 0)
    # Row 4 cols 9..22: "FAMILY  FEUD™" -> "BARBA'S BEEF™"
    barba_menu = [0x13, 0x02, 0x0A, 0x13, 0x02, 0x44, 0x0B, 0x00, 0x13, 0x04, 0x04, 0x0D, 0x07, 0x08]
    s0[4 * 32 + 9 : 4 * 32 + 23] = barba_menu
    _write_rle_screen_inplace(prg_buf, chr_buf, 0, s0, 0x0EB6A - 0x0EA67)

    s5 = _decode_rle_screen(prg_buf, chr_buf, 5)
    s5[7 * 32 + 9 : 7 * 32 + 23] = barba_menu
    _write_rle_screen_inplace(prg_buf, chr_buf, 5, s5, 0x0EBD6 - 0x0EB6A)

    s11 = _decode_rle_screen(prg_buf, chr_buf, 11)
    # Row 8: "Family FEUD. All" -> "Barba's BEEF. All" (shift 1 col left so space before "All" is preserved)
    # Copy 0B:44 apostrophe to unused tile 0xB5 in color 1 (matching s11 cream-yellow text; preserve $A1 white 'k')
    apos_src = decode_tile(chr_buf[0x0B000 + 0x44 * 16 : 0x0B000 + 0x45 * 16])
    chr_buf[0x0B000 + 0xB5 * 16 : 0x0B000 + 0xB6 * 16] = encode_tile(
        [''.join('1' if v else '0' for v in r) for r in apos_src]
    )
    s11[8 * 32 + 2 : 8 * 32 + 16] = [0x4A, 0x82, 0x8A, 0x98, 0x82, 0xB5, 0x89, 0x00, 0x4A, 0x4D, 0x4D, 0x4E, 0x90, 0x00]
    _write_rle_screen_inplace(prg_buf, chr_buf, 11, s11, 0x0F39C - 0x0F1C0)

    # 2. Screen 6 (Bank 01): Stage Overview center gold plaque ("FAMILY" / "FEUD" -> "BARBA'S" / "BEEF")
    s6 = _decode_rle_screen(prg_buf, chr_buf, 6)
    plaque_coords = [(r, c) for r in range(6, 10) for c in range(13, 19)]
    plaque_tiles = {s6[r * 32 + c] for r, c in plaque_coords}
    outside_s6 = {s6[r * 32 + c] for r in range(30) for c in range(32) if (r, c) not in plaque_coords}
    avail_01 = sorted((plaque_tiles - outside_s6) | (set(range(256)) - set(s6[:960])))

    # 5x11 serif-style mini glyphs ('3'=black on '2'=gold, 48x32 canvas)
    mini_glyphs: dict[str, list[str]] = {
        'B': [
            '####.',
            '#...#',
            '#...#',
            '#...#',
            '####.',
            '#...#',
            '#...#',
            '#...#',
            '#...#',
            '####.',
        ],
        'A': [
            '..#..',
            '.#.#.',
            '#...#',
            '#...#',
            '#####',
            '#...#',
            '#...#',
            '#...#',
            '#...#',
            '#...#',
        ],
        'R': [
            '####.',
            '#...#',
            '#...#',
            '#...#',
            '####.',
            '#..#.',
            '#...#',
            '#...#',
            '#...#',
            '#...#',
        ],
        "'": [
            '#.',
            '#.',
            '#.',
            '..',
            '..',
            '..',
            '..',
            '..',
            '..',
            '..',
        ],
        'S': [
            '.####',
            '#....',
            '#....',
            '.###.',
            '....#',
            '....#',
            '....#',
            '....#',
            '....#',
            '####.',
        ],
        'E': [
            '#####',
            '#....',
            '#....',
            '#....',
            '####.',
            '#....',
            '#....',
            '#....',
            '#....',
            '#####',
        ],
        'F': [
            '#####',
            '#....',
            '#....',
            '#....',
            '####.',
            '#....',
            '#....',
            '#....',
            '#....',
            '#....',
        ],
    }

    plaque_canvas = [['2'] * 48 for _ in range(32)]

    def draw_mini(text: str, oy: int, gap: int) -> None:
        tw = sum(len(mini_glyphs[ch][0]) for ch in text) + gap * (len(text) - 1)
        ox = (48 - tw) // 2
        for ch in text:
            g = mini_glyphs[ch]
            for y, row in enumerate(g):
                for x, px in enumerate(row):
                    if px == '#':
                        plaque_canvas[oy + y][ox + x] = '3'
            ox += len(g[0]) + gap

    draw_mini("BARBA'S", 4, 1)
    draw_mini('BEEF', 18, 2)

    pool_01: dict[bytes, int] = {}
    avail_01_iter = iter(avail_01)
    for tr in range(4):
        for tc in range(6):
            sub = [plaque_canvas[tr * 8 + y][tc * 8 : (tc + 1) * 8] for y in range(8)]
            enc = encode_tile(sub)
            tid = pool_01.get(enc)
            if tid is None:
                tid = next(avail_01_iter)
                pool_01[enc] = tid
                off = 0x01000 + tid * 16
                chr_buf[off : off + 16] = enc
            s6[(6 + tr) * 32 + (13 + tc)] = tid
    _write_rle_screen_inplace(prg_buf, chr_buf, 6, s6, 0x0E25F - 0x0E0DE)

    # 3. Podium "FF" -> "BB" emblems: Bank 00 (Screen 7 center podium) and Bank 09 (Screens 13 & 14)
    # Bank 00 tiles 19, 1A (row 21 cols 15..16) & 2A, 2B (row 22 cols 15..16)
    b00_patch = {
        0x19: [
            '22313000',
            '23100000',
            '23103110',
            '23103101',
            '23103110',
            '23103101',
            '23103101',
            '23103110',
        ],
        0x1A: [
            '00003132',
            '03110013',
            '03101013',
            '03110013',
            '03101013',
            '03101013',
            '03110013',
            '00330013',
        ],
        0x2A: [
            '22310330',
            '22231111',
            '22223333',
            '33333333',
            '11111111',
            '33333333',
            '30000000',
            '30000000',
        ],
        0x2B: [
            '00000132',
            '11111322',
            '33333222',
            '33333333',
            '11111111',
            '33333333',
            '00000003',
            '00000003',
        ],
    }
    for tid, rows in b00_patch.items():
        off = tid * 16
        chr_buf[off : off + 16] = encode_tile(rows)

    # Bank 09 tiles 2D, 2E (row 23 cols 24..25 in s13 / 7..8 in s14) & 36, 37 (row 24)
    b09_patch = {
        0x2D: [
            '31113333',
            '13330002',
            '32223002',
            '32332302',
            '02302302',
            '02223002',
            '02332302',
            '02302302',
        ],
        0x2E: [
            '33311322',
            '22300132',
            '33230313',
            '30230313',
            '22300313',
            '33230313',
            '30230313',
            '30230133',
        ],
        0x36: [
            '02302302',
            '02223000',
            '03330000',
            '11000000',
            '31111111',
            '33333333',
            '23333333',
            '22222222',
        ],
        0x37: [
            '22300133',
            '33301332',
            '00013332',
            '11133322',
            '33333222',
            '33222222',
            '32222222',
            '22222222',
        ],
    }
    for tid, rows in b09_patch.items():
        off = 0x09000 + tid * 16
        chr_buf[off : off + 16] = encode_tile(rows)


_STAGE_ROUND_GLYPHS: dict[str, list[str]] = {
    'C': [
        '.####',
        '#####',
        '##...',
        '##...',
        '##...',
        '##...',
        '#####',
        '.####',
    ],
    'D': [
        '####.',
        '#####',
        '##.##',
        '##.##',
        '##.##',
        '##.##',
        '#####',
        '####.',
    ],
    'E': [
        '#####',
        '#####',
        '##...',
        '####.',
        '####.',
        '##...',
        '#####',
        '#####',
    ],
    'F': [
        '#####',
        '#####',
        '##...',
        '####.',
        '####.',
        '##...',
        '##...',
        '##...',
    ],
    'H': [
        '##.##',
        '##.##',
        '##.##',
        '#####',
        '#####',
        '##.##',
        '##.##',
        '##.##',
    ],
    'I': [
        '##',
        '##',
        '##',
        '##',
        '##',
        '##',
        '##',
        '##',
    ],
    'N': [
        '##.##',
        '###.#',
        '#####',
        '#.###',
        '#..##',
        '#..##',
        '#..##',
        '#..##',
    ],
    'O': [
        '.###.',
        '#####',
        '##.##',
        '##.##',
        '##.##',
        '##.##',
        '#####',
        '.###.',
    ],
    'R': [
        '####.',
        '#####',
        '##.##',
        '####.',
        '###..',
        '##.#.',
        '##.##',
        '##.##',
    ],
    'S': [
        '.####',
        '#####',
        '##...',
        '####.',
        '.####',
        '...##',
        '#####',
        '####.',
    ],
    'T': [
        '#####',
        '#####',
        '.##..',
        '.##..',
        '.##..',
        '.##..',
        '.##..',
        '.##..',
    ],
    'U': [
        '##.##',
        '##.##',
        '##.##',
        '##.##',
        '##.##',
        '##.##',
        '#####',
        '.###.',
    ],
}


def _build_stage_round_banner(title: str) -> list[str]:
    """Render an 8x2 (64x16) Bank 0C sprite banner for Stage Overview rounds ('FIRST FEUD'..'FIFTH FEUD')."""
    canvas = [['0'] * 64 for _ in range(16)]
    word_gap = 3 if len(title) >= 11 else 4
    total_w = 0
    for idx, ch in enumerate(title):
        if ch == ' ':
            total_w += word_gap
        else:
            if idx > 0 and title[idx - 1] != ' ':
                total_w += 1
            total_w += len(_STAGE_ROUND_GLYPHS[ch][0])
    assert total_w <= 64, f'Stage banner {title!r} too wide: {total_w}px'
    ox = (64 - total_w) // 2
    for idx, ch in enumerate(title):
        if ch == ' ':
            ox += word_gap
            continue
        if idx > 0 and title[idx - 1] != ' ':
            ox += 1
        glyph = _STAGE_ROUND_GLYPHS[ch]
        for y, row in enumerate(glyph):
            for x, px in enumerate(row):
                if px == '#':
                    canvas[y][ox + x] = '3'
        ox += len(glyph[0])
    return [''.join(r) for r in canvas]


def _decode_local_grid(tiles: bytes, map_bytes: bytes, w: int, h: int) -> list[str]:
    """Reconstruct an (8*h) x (8*w) character grid from 1-based local tile indices."""
    grid = [['0'] * (w * 8) for _ in range(h * 8)]
    for r in range(h):
        for c in range(w):
            tid = map_bytes[r * w + c]
            if tid == 0:
                continue
            tile = decode_tile(tiles[(tid - 1) * 16 : tid * 16])
            for y in range(8):
                grid[r * 8 + y][c * 8 : (c + 1) * 8] = [str(p) for p in tile[y]]
    return [''.join(row) for row in grid]


def apply_barba_cast(
    prg_buf: bytearray,
    chr_buf: bytearray,
    z2_rom: bytes,
    *,
    z2_opponents: bool = False,
) -> dict[str, int]:
    """Replace Family Feud's stage, overview, Face-Off, Fast Money, and Host people with Barba (and optional Z2 opponent) assets."""
    frames24 = make_frames(z2_rom, 24)
    frames16 = make_frames(z2_rom, 16)

    z2_pool = None
    z2_pal_slots: list[int] = []
    if z2_opponents:
        import feud_cast
        cfg = feud_cast.load_cast_config()
        _, z2_pool = feud_cast.build_all_cast_pools(z2_rom, cfg)
        z2_pal_slots = list(feud_cast.get_runtime_cast_tables(cfg)['z2_pal_slots'])

    family_rosters = {
        0: [('std', True, 1), ('crouch', True, 3), ('up', True, 2), ('std', False, 0), ('tall', False, 1)],
        1: [('tall', True, 2), ('up', True, 1), ('crouch', False, 3), ('std', False, 0), ('up', False, 2)],
        2: [('crouch', True, 1), ('std', True, 0), ('tall', True, 3), ('up', False, 2), ('crouch', False, 1)],
    }

    stats: dict[str, int] = {}

    # 1. Stage Close-Up & Fast Money 4x6 portraits (Banks 05, 06, 07 -> blocks 0..74)
    for fam_id, bank in ((0, 0x05), (1, 0x06), (2, 0x07)):
        base_idx = fam_id * 25
        grids: dict[int, list[str]] = {}
        seat_pals: dict[int, int] = {}
        for seat, (kind, flp, pal_id) in enumerate(family_rosters[fam_id]):
            if z2_pool is not None and fam_id in (1, 2):
                z_idx = ((fam_id - 1) * 5 + seat) % len(z2_pool)
                seat_pals[seat] = z2_pal_slots[z_idx]
                v = z2_pool[z_idx].variants[seat % 3]
                st_frames = [_decode_local_grid(v.stage_tiles, v.stage_maps[f * 24 : (f + 1) * 24], 4, 6) for f in range(3)]
                for f_i in range(5):
                    idx = base_idx + seat * 5 + f_i
                    grids[idx] = st_frames[(0, 1, 2, 1, 0)[f_i]]
            else:
                seat_pals[seat] = pal_id
                for f_i in range(5):
                    idx = base_idx + seat * 5 + f_i
                    grids[idx] = _build_portrait_4x6(frames24, kind, f_i, flp)
        avail = list(range(0x04, 0x100))
        packed = _pack_bank(chr_buf, bank, avail, grids)
        stats[f'bank_{bank:02X}'] = len({t for ts in packed.values() for t in ts if t != 0})
        for idx, tids in packed.items():
            seat = (idx - base_idx) // 5
            _write_block_and_attr(prg_buf, idx, tids, [[seat_pals[seat]] * 4 for _ in range(6)])

    # 2. Main Stage Overview 2x4 small portraits (Bank 00 -> blocks 123..152)
    # Row 0 allocated first so r16 tiles stay in R0 (< 0x80) and avoid mid-scanline R1 switch lag!
    overview_grids: dict[int, list[str]] = {}
    for fam_id, base_idx in ((0, 123), (1, 133), (2, 143)):
        for seat, (kind, flp, _) in enumerate(family_rosters[fam_id]):
            if z2_pool is not None and fam_id in (1, 2):
                z_idx = ((fam_id - 1) * 5 + seat) % len(z2_pool)
                v = z2_pool[z_idx].variants[seat % 3]
                for f_i in range(2):
                    idx = base_idx + f_i * 5 + seat
                    overview_grids[idx] = _decode_local_grid(v.ov_tiles, v.ov_maps[f_i * 8 : (f_i + 1) * 8], 2, 4)
            else:
                for f_i in range(2):
                    idx = base_idx + f_i * 5 + seat
                    overview_grids[idx] = _build_small_2x4(frames16, kind, f_i, flp)
    avail_00 = [
        t for t in range(0x5B, 0x100)
        if t not in ({0x37, 0xC0, 0xC1, 0xCC} | set(range(0xD6, 0xFB)))
    ]
    packed_00 = _pack_bank(chr_buf, 0x00, avail_00, overview_grids, row0_priority=True)
    stats['bank_00'] = len({t for ts in packed_00.values() for t in ts if t != 0})
    for idx, tids in packed_00.items():
        _write_block_and_attr(prg_buf, idx, tids)

    # 3. Face-Off 4x12 Contestants + 4x6 Center Host (Banks 02, 03, 04 -> blocks 75..122)
    # Protect every Center Podium & Floor tile used in rows 20..27 of the Face-Off RLE screens!
    faceoff_cfg = [
        (0, 0x02, 75, 8),
        (1, 0x03, 91, 9),
        (2, 0x04, 107, 10),
    ]
    for fam_id, bank, base_idx, screen_idx in faceoff_cfg:
        nt = _decode_rle_screen(prg_buf, chr_buf, screen_idx)
        protected_r20_27 = {nt[r * 32 + c] for r in range(20, 28) for c in range(32) if nt[r * 32 + c] != 0}
        # Also protect 4x2 buzzer animation tiles (blocks base+14, base+15)
        for b_idx in (base_idx + 14, base_idx + 15):
            _, _, bt, _, _ = _get_block(prg_buf, b_idx)
            protected_r20_27.update(t for t in bt if t != 0)

        orig_grids = {
            seat: _decode_orig_block(prg_buf, chr_buf, bank, base_idx + seat)
            for seat in range(5)
        }
        grids_fo: dict[int, list[str]] = {}
        attrs_fo: dict[int, list[list[int]]] = {}
        for seat, (_, _, pal_id) in enumerate(family_rosters[fam_id]):
            og, oa = orig_grids[seat]
            if z2_pool is not None and fam_id in (1, 2):
                z_idx = ((fam_id - 1) * 5 + seat) % len(z2_pool)
                z_pal = z2_pal_slots[z_idx]
                v = z2_pool[z_idx].variants[seat % 3]
                fo_pair = []
                for f_i in range(2):
                    upper = _decode_local_grid(v.fo_tiles, v.fo_maps[f_i * 60 : (f_i + 1) * 60], 6, 10)
                    canvas = [list(row[4:36]) for row in upper] + [['0'] * 32 for _ in range(16)]
                    attrs = [[z_pal] * 4 for _ in range(12)]
                    for y in range(96):
                        r = y // 8
                        for x in range(32):
                            c = x // 8
                            is_podium = (r >= 6 and c <= 1 and og[y][x] != '0')
                            is_buzzer = (r == 5 and c == 0 and x < 10 and y >= 42 and og[y][x] != '0')
                            if is_podium or is_buzzer:
                                canvas[y][x] = og[y][x]
                                if r >= 6 and c <= 1:
                                    attrs[r][c] = 0
                                elif r == 5 and c == 0:
                                    attrs[r][c] = oa[r][c]
                            elif r >= 10 and c >= 2:
                                canvas[y][x] = '2'
                                attrs[r][c] = 0
                            elif r >= 10 and c <= 1:
                                attrs[r][c] = 0
                    fo_pair.append(([''.join(row) for row in canvas], attrs))
                g0, a0 = fo_pair[0]
                g1, a1 = fo_pair[1]
            else:
                tall_h = (70, 62, 72, 68, 70)[seat]
                g0, a0 = _build_faceoff_contestant(frames24, og, oa, pal_id, 'closed', seat % 4, tall_h=tall_h)
                g1, a1 = _build_faceoff_contestant(frames24, og, oa, pal_id, 'open', (seat + 1) % 4, tall_h=tall_h)
            grids_fo[base_idx + seat] = g0
            attrs_fo[base_idx + seat] = a0
            grids_fo[base_idx + 7 + seat] = g1
            attrs_fo[base_idx + 7 + seat] = a1

        grids_fo[base_idx + 5] = _build_host_bust_4x6(z2_rom, 'closed', flip_h=True)
        grids_fo[base_idx + 6] = _build_host_bust_4x6(z2_rom, 'closed', flip_h=True)
        grids_fo[base_idx + 12] = _build_host_bust_4x6(z2_rom, 'closed', flip_h=False)
        grids_fo[base_idx + 13] = _build_host_bust_4x6(z2_rom, 'open', flip_h=True)

        avail_fo = [t for t in range(0x01, 0xE1) if t not in protected_r20_27]
        packed_fo = _pack_bank(
            chr_buf, bank, avail_fo, grids_fo,
            protected_pool_tiles=sorted(protected_r20_27),
        )
        stats[f'bank_{bank:02X}'] = len({t for ts in packed_fo.values() for t in ts if t != 0})
        for idx, tids in packed_fo.items():
            if idx in attrs_fo:
                _write_block_and_attr(prg_buf, idx, tids, attrs_fo[idx])
            else:
                _write_block_and_attr(prg_buf, idx, tids)

    # 4. Walking Host OAM (Bank 0C -> 8x8 [159..165], 6x12 [166..175], 6x4 [204])
    host_grids: dict[int, list[str]] = {
        159: _build_host_small_8x8(z2_rom, 'closed', 0, front=True),
        160: _build_host_small_8x8(z2_rom, 'open', 1, front=True),
        161: _build_host_small_8x8(z2_rom, 'half', 1, front=True),
        162: _build_host_small_8x8(z2_rom, 'closed', 0),
        163: _build_host_small_8x8(z2_rom, 'closed', 1),
        164: _build_host_small_8x8(z2_rom, 'closed', 0),
        165: _build_host_small_8x8(z2_rom, 'closed', 1),
        166: _build_host_walk_6x12(z2_rom, 'closed', 0, True, front=True),
        167: _build_host_walk_6x12(z2_rom, 'open', 0, True, front=True),
        168: _build_host_walk_6x12(z2_rom, 'closed', 0, True),
        169: _build_host_walk_6x12(z2_rom, 'closed', 1, True),
        170: _build_host_walk_6x12(z2_rom, 'closed', 2, True),
        171: _build_host_walk_6x12(z2_rom, 'closed', 3, True),
        172: _build_host_walk_6x12(z2_rom, 'closed', 0, True),
        173: _build_host_walk_6x12(z2_rom, 'open', 2, True),
        174: _build_host_walk_6x12(z2_rom, 'closed', 0, True, back=True),
        175: _build_host_walk_6x12(z2_rom, 'closed', 1, True),
        204: ['0' * 48 for _ in range(32)],
    }
    for blk_idx, title in (
        (154, 'FIRST FEUD'),
        (155, 'SECOND FEUD'),
        (156, 'THIRD FEUD'),
        (157, 'FOURTH FEUD'),
        (158, 'FIFTH FEUD'),
    ):
        host_grids[blk_idx] = _build_stage_round_banner(title)
    avail_0c = list(range(0x01, 0x100))
    packed_0c = _pack_bank(chr_buf, 0x0C, avail_0c, host_grids)
    stats['bank_0C'] = len({t for ts in packed_0c.values() for t in ts if t != 0})
    for idx, tids in packed_0c.items():
        w, h, _, _, _ = _get_block(prg_buf, idx)
        _write_block_and_attr(prg_buf, idx, tids, [[0] * w for _ in range(h)])

    # 5. Unified 4-palette Barba set ($07, $08, $09, $0B)
    barba_pal16 = bytes([
        0x16, 0x2C, 0x27, 0x0F,
        0x16, 0x30, 0x26, 0x0F,
        0x16, 0x38, 0x12, 0x0F,
        0x16, 0x3A, 0x1A, 0x0F,
    ])
    for pal_addr in (0xA4F8, 0xA508, 0xA518, 0xA538):
        off = pal_addr - 0x8000
        prg_buf[off : off + 16] = barba_pal16

    # 6. Stage Close-Up portrait attribute table ($98B6-$9909)
    for fam_id in range(3):
        if z2_pool is not None and fam_id in (1, 2):
            pals = [z2_pal_slots[((fam_id - 1) * 5 + seat) % len(z2_pool)] for seat in range(5)]
        else:
            pals = [p for _, _, p in family_rosters[fam_id]]
        for side in range(2):
            order = list(reversed(pals)) if side == 0 else pals
            b0 = (order[0] << 2) | (order[0] << 6)
            b1 = order[0] | (order[0] << 4) | (order[1] << 2) | (order[1] << 6)
            b2 = order[1] | (order[1] << 4) | (order[2] << 2) | (order[2] << 6)
            b3 = order[2] | (order[2] << 4) | (order[3] << 2) | (order[3] << 6)
            b4 = order[3] | (order[3] << 4) | (order[4] << 2) | (order[4] << 6)
            b5 = order[4] | (order[4] << 4)
            row_top = [b0, b1, b2, b3, b4, b5, 0x00, 0x00]
            row_bot = [x & 0x0F for x in (b0, b1, b2, b3, b4, b5)]
            off = (0x98B6 + fam_id * 28 + side * 14) - 0x8000
            prg_buf[off : off + 14] = bytes(row_top + row_bot)

    # 7. Face-Off BG attribute table ($B9E6-$BA3F); $23DB=$40 host attr is handled via W_FACEOFF_ATTR at $BA4E.
    for seat in range(5):
        for fam_id in range(3):
            if z2_pool is not None and fam_id in (1, 2):
                p = z2_pal_slots[((fam_id - 1) * 5 + seat) % len(z2_pool)]
            else:
                p = family_rosters[fam_id][seat][2]
            dc = 0x10
            dd = (p << 4) | (p << 6)
            e4 = 0x11
            e5 = p * 0x55
            ec = 0x00
            ed = p * 0x05
            off = (0xB9E6 + seat * 18 + fam_id * 6) - 0x8000
            prg_buf[off : off + 6] = bytes([dc, dd, e4, e5, ec, ed])

    stats['bank_09_title'] = apply_barba_title(prg_buf, chr_buf)
    apply_barba_branding(prg_buf, chr_buf)

    # 8. Face-Off podium buzzer OAM blocks (89=off, 90=lit).
    # Barba is 6 sprites wide on scanlines $AF/$B7, leaving only 2 sprite slots;
    # emit 0 sprites on off-frame (BG shows dark circles) and only the 2x2 lit
    # cyan circles ($E2) on lit-frame, using $F838's 0x00 attrs (SPR pal 0).
    _write_block_and_attr(prg_buf, 89, [0x00] * 8)
    _write_block_and_attr(prg_buf, 90, [0x00, 0x00, 0xE2, 0xE2, 0x00, 0x00, 0xE2, 0xE2])
    prg_buf[0xF218 + 90 - 0x8000] = 0x38
    prg_buf[0xF2E5 + 90 - 0x8000] = 0xF8

    return stats


def patch_chr0b_blue_k(chr_buf: bytearray) -> None:
    """Write crisp blue lowercase 'k' at tile $B4 in CHR bank $0B (immune to $A1 apostrophe)."""
    dst_off = 0x0B * 4096 + 0xB4 * 16
    k_rows = [
        '03300000',
        '03300000',
        '03303300',
        '03333000',
        '03330000',
        '03303300',
        '03300330',
        '00000000',
    ]
    chr_buf[dst_off : dst_off + 16] = encode_tile(k_rows)


def compute_free_tiles(prg_orig: bytes, chr_orig: bytes) -> dict[str, object]:
    """Return guaranteed-free tile slots in CHR 00, 02, 03 plus Face-Off bottom-2 podium rows."""
    scr07 = set(_decode_rle_screen(prg_orig, chr_orig, 7)[:960])
    scr08 = set(_decode_rle_screen(prg_orig, chr_orig, 8)[:960])
    scr09 = set(_decode_rle_screen(prg_orig, chr_orig, 9)[:960])
    scr10 = set(_decode_rle_screen(prg_orig, chr_orig, 10)[:960])

    # Stage Overview (CHR 00): keep static Screen 07 + score/name glyphs ($00..$5A, $C0, $C1, $CC, $D6..$FA)
    ov_keep = scr07 | set(range(0x00, 0x5B)) | {0xC0, 0xC1, 0xCC} | set(range(0xD6, 0xFB))
    ov_free = [t for t in range(256) if t not in ov_keep]
    assert len(ov_free) >= 120, f'Expected >=120 overview free tiles, got {len(ov_free)}'

    # Face-Off Player (CHR 02): keep Host/Buzzer (80,81,87,88,89,90) + bottom 2 podium rows (75..79)
    fo_p1_keep: set[int] = {0x00}
    for b in (80, 81, 87, 88, 89, 90):
        _, _, ts, _, _ = _get_block(prg_orig, b)
        fo_p1_keep.update(ts)
    fo_p1_bot2: list[int] = []
    for b in range(75, 80):
        _, _, ts, _, _ = _get_block(prg_orig, b)
        fo_p1_keep.update(ts[40:])
        fo_p1_bot2.extend(ts[40:])
    fo_p1_free = [t for t in range(256) if t not in fo_p1_keep]
    assert len(fo_p1_free) >= 72, f'Expected >=72 Face-Off P1 free tiles, got {len(fo_p1_free)}'

    # Face-Off CPU (CHR 03): keep Host/Buzzer (96,97,103..106) + Screen 08/09/10 backdrop + bottom 2 rows (6x2)
    fo_cpu_keep: set[int] = {0x00} | scr08 | scr09 | scr10
    for b in (96, 97, 103, 104, 105, 106):
        _, _, ts, _, _ = _get_block(prg_orig, b)
        fo_cpu_keep.update(ts)
    fo_cpu_keep.add(0xEB)
    fo_cpu_free = [t for t in range(256) if t not in fo_cpu_keep]
    assert len(fo_cpu_free) >= 75, f'Expected >=75 Face-Off CPU free tiles, got {len(fo_cpu_free)}'
    lip_left_id, lip_mid_id, lip_right_id = fo_cpu_free[72:75]
    fo_cpu_lip_tiles = (
        encode_tile(['22311111', '22333333'] + ['2' * 8] * 6)
        + encode_tile(['11111111', '33333333'] + ['2' * 8] * 6)
        + encode_tile(['11111322', '33333322'] + ['2' * 8] * 6)
    )
    fo_cpu_bot2: list[int] = [
        lip_left_id, lip_mid_id, lip_mid_id, lip_mid_id, lip_mid_id, lip_right_id,
        0xEB, 0xEB, 0xEB, 0xEB, 0xEB, 0xEB,
    ]

    # Stage Close-Up (CHR 05 P1, CHR 06 CPU): keep screen nametables, blank block 153, & $B5..$BA
    scr0d = set(_decode_rle_screen(prg_orig, chr_orig, 0x0D)[:960])
    scr0e = set(_decode_rle_screen(prg_orig, chr_orig, 0x0E)[:960])
    st_ui_keep: set[int] = set(range(0xB5, 0xBB))
    for b in (153,):
        _, _, ts, _, _ = _get_block(prg_orig, b)
        st_ui_keep.update(ts)
    st_p1_free = [t for t in range(256) if t not in (scr0d | st_ui_keep)]
    st_cpu_free = [t for t in range(256) if t not in (scr0e | st_ui_keep)]
    assert len(st_p1_free) >= 180, f'Expected >=180 Stage P1 free tiles, got {len(st_p1_free)}'
    assert len(st_cpu_free) >= 170, f'Expected >=170 Stage CPU free tiles, got {len(st_cpu_free)}'

    return {
        'ov_free': bytes(ov_free[:120]),
        'st_p1_free': bytes(st_p1_free[:180]),
        'st_cpu_free': bytes(st_cpu_free[:170]),
        'fo_p1_free': bytes(fo_p1_free[:72]),
        'fo_cpu_free': bytes(fo_cpu_free[:72]),
        'fo_cpu_lip_ids': bytes((lip_left_id, lip_mid_id, lip_right_id)),
        'fo_cpu_lip_tiles': fo_cpu_lip_tiles,  # 3 * 16 = 48 bytes
        'fo_p1_bot2': bytes(fo_p1_bot2),   # 5 * 8 = 40 bytes
        'fo_cpu_bot2': bytes(fo_cpu_bot2), # 6 * 2 = 12 bytes
    }


def build_cast_rom_banks(z2_rom: bytes, feud_rom: bytes) -> dict[str, object]:
    """Compile all included cast characters x 3 height presets into 8KB PRG banks + metadata."""
    import feud_cast

    prg_buf = bytearray(feud_rom[16 : 16 + 32768])
    chr_buf = bytearray(feud_rom[16 + 32768 : 16 + 32768 + 131072])
    apply_barba_cast(prg_buf, chr_buf, z2_rom)
    free_info = compute_free_tiles(bytes(prg_buf), bytes(chr_buf))
    cfg = feud_cast.load_cast_config()
    barba_pool, z2_pool = feud_cast.build_all_cast_pools(z2_rom, cfg)
    rt = feud_cast.get_runtime_cast_tables(cfg)

    def _encode_variant_blob(v: feud_cast.CompiledVariant) -> bytearray:
        blob = bytearray([
            len(v.stage_tiles) // 16,
            len(v.ov_tiles) // 16,
            v.ov_row0_count,
            len(v.fo_tiles) // 16,
        ])
        blob.extend(v.stage_tiles)
        blob.extend(v.stage_maps)
        blob.extend(v.ov_tiles)
        blob.extend(v.ov_maps)
        blob.extend(v.fo_tiles)
        blob.extend(v.fo_maps)
        return blob

    def pack_pools(
        b_pool: list[feud_cast.CastCharacter],
        z_pool: list[feud_cast.CastCharacter],
        start_bank: int,
    ) -> tuple[list[bytes], list[tuple[int, int]], list[tuple[int, int]]]:
        items: list[tuple[int, str, int, bytearray]] = []
        b_meta: list[tuple[int, int]] = [(0, 0)] * (len(b_pool) * 3)
        z_meta: list[tuple[int, int]] = [(0, 0)] * (len(z_pool) * 3)
        for ch_idx, ch in enumerate(b_pool):
            for v_idx, v in enumerate(ch.variants):
                blob = _encode_variant_blob(v)
                items.append((len(blob), 'b', ch_idx * 3 + v_idx, blob))
        for ch_idx, ch in enumerate(z_pool):
            for v_idx, v in enumerate(ch.variants):
                blob = _encode_variant_blob(v)
                items.append((len(blob), 'z', ch_idx * 3 + v_idx, blob))

        # Pack all variant blobs across <= 25 8KB PRG banks (banks 5..29).
        # Start with deterministic FFD; if bin slack overflows 25 banks while total bytes fit,
        # search deterministic Best-Fit jittered orders for a <= 25 bank packing.
        import random

        def _try_pack(order: list[tuple[int, str, int, bytearray]], best_fit: bool) -> list[list[tuple[str, int, bytearray]]]:
            bins: list[list[tuple[str, int, bytearray]]] = [[]]
            rem = [8192]
            for sz, pool_tag, slot_idx, blob in order:
                if best_fit:
                    cand = [(rem[i] - sz, i) for i in range(len(bins)) if rem[i] >= sz]
                    target_bi = min(cand)[1] if cand else -1
                else:
                    target_bi = next((i for i in range(len(bins)) if rem[i] >= sz), -1)
                if target_bi < 0:
                    bins.append([])
                    rem.append(8192)
                    target_bi = len(bins) - 1
                bins[target_bi].append((pool_tag, slot_idx, blob))
                rem[target_bi] -= sz
            return bins

        base_order = sorted(items, key=lambda x: (-x[0], x[1], x[2]))
        chosen = _try_pack(base_order, best_fit=False)
        if len(chosen) > 25:
            best_bins = chosen
            for seed in range(256):
                rng = random.Random(seed)
                order = sorted(
                    items,
                    key=lambda x: (-(x[0] + (rng.randint(-200, 200) if seed else 0)), x[1], x[2]),
                )
                trial = _try_pack(order, best_fit=True)
                if len(trial) < len(best_bins):
                    best_bins = trial
                if len(best_bins) <= 25:
                    break
            chosen = best_bins

        banks: list[bytearray] = [bytearray() for _ in chosen]
        for bi, entries in enumerate(chosen):
            for pool_tag, slot_idx, blob in entries:
                addr = 0xA000 + len(banks[bi])
                banks[bi].extend(blob)
                if pool_tag == 'b':
                    b_meta[slot_idx] = (start_bank + bi, addr)
                else:
                    z_meta[slot_idx] = (start_bank + bi, addr)

        for b_buf in banks:
            b_buf.extend(b'\xFF' * (8192 - len(b_buf)))
        return [bytes(b) for b in banks], b_meta, z_meta

    all_banks, b_meta, z_meta = pack_pools(barba_pool, z2_pool, 5)
    assert 5 + len(all_banks) <= 30, f'Cast pools exceeded free PRG banks 5..29 ({5 + len(all_banks)})'

    return {
        **free_info,
        **rt,
        'cast_banks': all_banks,
        'barba_meta': b_meta,   # barba_count * 3 entries of (prg_bank, addr_in_A000)
        'z2_meta': z_meta,      # z2_count * 3 entries of (prg_bank, addr_in_A000)
        'barba_count': len(barba_pool),
        'z2_count': len(z2_pool),
    }


def render_previews(prg: bytes, chr_rom: bytes, out_dir: Path) -> list[Path]:
    """Render cast proof sheet and per-bank CHR sheets into ``out_dir`` for tile iteration."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    WALL = (152, 34, 32)
    PALS = {
        0: [WALL, (60, 210, 225), (255, 168, 57), (20, 22, 28)],
        1: [WALL, (255, 243, 205), (212, 68, 40), (20, 22, 28)],
        2: [WALL, (240, 232, 180), (48, 108, 210), (20, 22, 28)],
        3: [WALL, (210, 248, 200), (44, 168, 72), (20, 22, 28)],
        'host': [WALL, (248, 248, 248), (212, 68, 40), (20, 22, 28)],
    }

    canvas = [[WALL] * 440 for _ in range(320)]

    def draw_block(bank: int, idx: int, ox: int, oy: int, force_pal: int | str | None = None) -> None:
        grid, attrs = _decode_orig_block(prg, chr_rom, bank, idx)
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch != '0':
                    pk = force_pal if force_pal is not None else attrs[y // 8][x // 8]
                    canvas[oy + y][ox + x] = PALS[pk][int(ch)]

    for fam, bank in ((0, 0x05), (1, 0x06), (2, 0x07)):
        for seat in range(5):
            draw_block(bank, fam * 25 + seat * 5 + 2, 8 + seat * 36, 8 + fam * 54)
    for seat in range(5):
        draw_block(0x00, 123 + seat, 200 + seat * 20, 8, 1)
        draw_block(0x00, 138 + seat, 200 + seat * 20, 48, 2)
    draw_block(0x03, 91, 8, 180)
    draw_block(0x03, 96, 44, 180, 'host')
    draw_block(0x03, 98, 80, 180)
    for i, idx in enumerate((166, 168, 169, 170, 171, 174)):
        draw_block(0x0C, idx, 130 + i * 50, 180, 'host')

    proof_path = out_dir / 'all_cast_proof.png'
    write_png(proof_path, canvas, 2)
    written.append(proof_path)

    # Render patched 4KB CHR bank tile sheets (16x16 grid with 1px separators)
    sheet_pal = [(26, 28, 36), (255, 243, 205), (212, 68, 40), (10, 10, 14)]
    for bank in (0x00, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x0C):
        grid = [[(55, 58, 68)] * 144 for _ in range(144)]
        for tid in range(256):
            off = bank * 4096 + tid * 16
            dec = decode_tile(chr_rom[off : off + 16])
            for y in range(8):
                for x in range(8):
                    grid[(tid // 16) * 9 + y][(tid % 16) * 9 + x] = sheet_pal[dec[y][x]]
        p = out_dir / f'feud-barba-chr-{bank:02X}.png'
        write_png(p, grid, 3)
        written.append(p)

    return written


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, default=Path('build/feud-work/previews'))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    z2 = (root / 'roms/z2.nes').read_bytes()
    feud = (root / 'roms/feud.nes').read_bytes()
    prg_buf = bytearray(feud[16 : 16 + 32768])
    chr_buf = bytearray(feud[16 + 32768 : 16 + 32768 + 131072])
    stats = apply_barba_cast(prg_buf, chr_buf, z2)
    print('CHR tile usage per bank:', stats)
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    for p in render_previews(bytes(prg_buf), bytes(chr_buf), out_dir):
        print('Wrote', p)
