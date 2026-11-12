"""Compile editable pixel rows into native NES tiles and player metasprites."""
from __future__ import annotations
import json
from pathlib import Path
from nes import encode_tile, write_png

COLORS = [(20, 22, 28), (194, 43, 25), (255, 168, 57), (255, 243, 205)]


def sprite_pairs(rows: list[str]) -> list[bytes]:
    width = len(rows[0])
    if len(rows) % 16 or width % 8 or any(len(r) != width for r in rows):
        raise ValueError('Metasprites require 8-pixel columns and 16-pixel rows')
    return [b''.join(encode_tile([rows[y+dy][x:x+8] for dy in range(8)])
                     for y in (top, top+8))
            for top in range(0, len(rows), 16) for x in range(0, width, 8)]


def compile_assets(root: Path) -> tuple[bytes, dict[int, bytes], bytes, list[list[str]]]:
    art = json.loads((root / 'assets/barba.json').read_text())
    body, small = art['body'], art['small']
    for name in ('body', 'small', 'front', 'back'):
        for row in art[name]:
            if len(row) != 16 or set(row) - set('0123'):
                raise ValueError(f'Invalid pixel row in {name}: {row!r}')
    # Indexed by the original six-sprite record number, not by animation ID.
    frames = []
    for record in range(19):
        rows = list(body)
        if record in (0, 1, 2):
            delta = (0, 1, -1)[record]
            for y in range(20, 31):
                row = rows[y]
                rows[y] = (('0'+row[:-1]) if delta > 0 else (row[1:]+'0')) if delta else row
        if record in (3, 7, 8, 9, 10, 11, 12):
            rows = ['0'*16]*16 + list(small)
        if record in (6, 8):
            # Mouth opening in the standing/crouched attack lane.
            for y in (8, 9):
                at = y + (16 if record == 8 else 0)
                rows[at] = rows[at][:10] + '000000'
        if record == 13:  # Hit reaction: coil tightens.
            rows = ['0'*16]*4 + rows[:-4]
        if record == 15:  # Death: collapsed coil, retain full state coverage.
            rows = ['0'*16]*16 + [r[::-1] for r in small]
        # The game's side-view renderer flips stored LEFT-facing art for right.
        frames.append(['0'*8+r[::-1] for r in rows])

    # Reserve weapon tiles used by existing renderer immediates and the new tip.
    reserved = {0x32, 0x50, 0x54}
    slots = iter(i for i in range(0, 0x64, 2) if i not in reserved)
    pairs: dict[bytes, int] = {bytes(32): 0xF5}
    graphics: dict[int, bytes] = {}
    mapping = bytearray()
    for rows in frames:
        for pair in sprite_pairs(rows):
            if pair not in pairs:
                try:
                    tile = next(slots)
                except StopIteration as exc:
                    raise ValueError('Player graphics exceed the reserved tile budget') from exc
                pairs[pair] = tile
                graphics[tile] = pair
            mapping.append(pairs[pair])

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

    ow = bytearray()
    for rows in (small, [r[::-1] for r in small], art['front'], art['back']):
        for step in (0, 1):
            animated = rows if step == 0 else ['0'*16] + rows[:-1]
            ow.extend(b''.join(sprite_pairs(animated)))

    # Preview only original pixel art; no source ROM data in this artifact.
    preview_rows = []
    for top in range(0, len(frames), 5):
        for y in range(32):
            row = []
            for frame in frames[top:top+5]:
                row += [COLORS[int(v)] for v in frame[y]] + [(40, 44, 52)]*4
            preview_rows.append(row + [COLORS[0]] * (140-len(row)))
        preview_rows += [[COLORS[0]]*140 for _ in range(4)]
    write_png(root / 'build/barba-sprites.png', preview_rows, 4)
    return bytes(mapping), graphics, bytes(ow), frames
