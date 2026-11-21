"""Local-only review sheet for encounter-trail art candidates.

Writes build/trail-candidates.html (gitignored). The sheet embeds pixels
extracted from the local verified ROM, so never publish or commit it.

Parts are generated separately so each can be picked on its own:
  corner  16x16, replaces the bottom row's center+back columns (x 8-23)
  torso   16x16, the upright torso chunk turned so the spines face up
  tip      8x16, the pointed end; one sprite, so the budget stays 5 pairs
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from boss_art import make_frames  # noqa: E402
from nes import load_source  # noqa: E402
import assets  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BEND_POSES = ('idle', 'walk0', 'walk1', 'walk2', 'windup', 'attack', 'jump')


def torso_chunk(frames) -> list[str]:
    return [row[8:24] for row in frames['idle'][16:32]]


def turn_ccw(rows: list[str]) -> list[str]:
    n = len(rows)
    return [''.join(row[x] for row in rows) for x in range(n - 1, -1, -1)]


def grid(rows):
    return [list(r) for r in rows]


def rows_of(g):
    return [''.join(r) for r in g]


# ---------------------------------------------------------------- corners
def rotsprite(src: list[str], deg: float, out: int, dx: float, dy: float, k: int = 8) -> list[str]:
    """RotSprite-style: upscale k, rotate (nearest), majority-downsample."""
    n = len(src)
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    cx = cy = n / 2
    res = []
    for oy in range(out):
        line = ''
        for ox in range(out):
            votes = [0, 0, 0, 0]
            for sy in range(k):
                for sx in range(k):
                    px = ox + (sx + .5) / k - out / 2 - dx
                    py = oy + (sy + .5) / k - out / 2 - dy
                    # inverse rotate (screen y down; positive deg = CCW on screen)
                    ux = ca * px - sa * py + cx
                    uy = sa * px + ca * py + cy
                    ix, iy = int(math.floor(ux)), int(math.floor(uy))
                    v = int(src[iy][ix]) if 0 <= ix < n and 0 <= iy < n else 0
                    votes[v] += 1
            # transparent only if it is the clear majority
            opaque = votes[1:]
            best = 1 + max(range(3), key=lambda i: opaque[i])
            line += str(best) if votes[0] < k * k * 0.5 else '0'
        res.append(line)
    return res


def outline(rows: list[str]) -> list[str]:
    """Give every opaque edge pixel the dark outline colour 1."""
    g = grid(rows)
    h, w = len(g), len(g[0])
    out = [r[:] for r in g]
    for y in range(h):
        for x in range(w):
            if g[y][x] == '0':
                continue
            for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                if 0 <= nx < w and 0 <= ny < h and g[ny][nx] == '0':
                    out[y][x] = '1'
                    break
    return rows_of(out)


def polar_bend(src: list[str], px: float, py: float, rmax: float, spines: str) -> list[str]:
    """Sweep the upright chunk around a pivot near the top-right corner.

    0 deg reads the chunk's top row (body arriving from above), 90 deg the
    right edge (leaving horizontally). Torso column u maps to radius, so the
    belly rides the outer arc and the spines the inner one.
    """
    n = len(src)
    res = []
    for y in range(16):
        line = ''
        for x in range(16):
            dx, dy = px - (x + .5), (y + .5) - py
            r = math.hypot(dx, dy)
            th = math.atan2(dy, dx)  # 0 = pointing left of the pivot, pi/2 = down
            if th < -0.05 or th > math.pi / 2 + .05:
                line += '0'
                continue
            u = rmax - r  # 0 = belly (outer), n-1 = spine side (inner)
            ui = int(math.floor(u * n / rmax))
            t = th / (math.pi / 2)
            vi = int(t * (n - 1) + .5)
            if not (0 <= ui < n):
                line += '0'
                continue
            v = src[vi][ui]
            if ui >= n - 3 and v == '3':
                v = {'keep': '3', 'thin': '3' if (vi % 3 == 0) else '1', 'drop': '1'}[spines]
            line += v
        res.append(line)
    return res


def corner_candidates(torso: list[str]) -> dict[str, list[str]]:
    c = {}
    c['Rot45 centered'] = outline(rotsprite(torso, 45, 16, 0, 0))
    c['Rot45 hugged'] = outline(rotsprite(torso, 45, 16, -2.5, 0.5))
    c['Rot45 nearest'] = outline(rotsprite(torso, 45, 16, -1, 0.5, k=1))
    c['Elbow tight'] = outline(polar_bend(torso, 16.0, 0.0, 16.0, 'thin'))
    c['Elbow round'] = outline(polar_bend(torso, 17.5, -1.0, 17.0, 'thin'))
    c['Elbow bare spine'] = outline(polar_bend(torso, 16.5, -0.5, 16.5, 'drop'))
    return c


# ---------------------------------------------------------------- tails
def tip_from_profile(profile, turned: list[str], spine_every: int = 0, flat: bool = False) -> list[str]:
    """Taper cut from the torso's own texture.

    The turned torso repeats its scale pattern every three columns, so the
    tip keeps tiling columns 10-12 at their original rows. The top edge
    drops toward the point, so the dark upper scales go first and the
    orange belly carries through to the tip.
    """
    g = [['0'] * len(profile) for _ in range(16)]
    for x, (top, bot) in enumerate(profile):
        for y in range(top, bot + 1):
            if y in (top, bot):
                g[y][x] = '1'
            elif flat:
                g[y][x] = '3' if y >= bot - 2 else '2'
            else:
                src = turned[min(max(y, 2), 12)][10 + x % 3]
                g[y][x] = src if src != '0' else '2'
        if spine_every and x % spine_every == 0 and top >= 1 and x < len(profile) - 1:
            g[top - 1][x] = '3'
    return rows_of(g)


# (top, bottom) per column; the left column overlaps the torso's end
# (rows 2-11) by +/-2 so the delayed Y never opens a gap.
TIP_PROFILES = {
    'Needle':    ((1, 13), (3, 13), (4, 13), (6, 13), (7, 13), (9, 13), (10, 13), (12, 13)),
    'Long spike': ((1, 13), (2, 13), (4, 13), (5, 13), (7, 13), (8, 13), (10, 13), (11, 12)),
    'Droop':     ((1, 13), (3, 13), (5, 14), (7, 14), (9, 15), (10, 15), (12, 15), (13, 15)),
    'Stub':      ((1, 13), (3, 13), (5, 13), (7, 13), (9, 12), (10, 11), (0, -1), (0, -1)),
    'Flick up':  ((1, 13), (3, 12), (4, 11), (5, 10), (5, 9), (5, 8), (4, 6), (3, 4)),
}


def tip_candidates(turned: list[str]) -> dict[str, list[str]]:
    t = {}
    for name, prof in TIP_PROFILES.items():
        t[name] = tip_from_profile(prof, turned)
    t['Needle spined'] = tip_from_profile(TIP_PROFILES['Needle'], turned, spine_every=2)
    t['Droop spined'] = tip_from_profile(TIP_PROFILES['Droop'], turned, spine_every=2)
    t['Needle flat (old shading)'] = tip_from_profile(TIP_PROFILES['Needle'], turned, flat=True)
    for name, prof in WIDE_TIPS.items():
        t[name] = tip_from_profile(prof, turned)
    t['Flick up 16 spined'] = tip_from_profile(WIDE_TIPS['Flick up 16'], turned, spine_every=3)
    return t


# 16px tips: two sprites. The belly sweeps up into a hook at the end.
WIDE_TIPS = {
    'Flick up 16': ((1, 13), (2, 13), (3, 13), (3, 12), (4, 12), (4, 11), (5, 11), (5, 10),
                    (5, 10), (5, 9), (5, 9), (5, 8), (4, 7), (4, 6), (3, 5), (2, 3)),
    'Flick up 16 slim': ((1, 13), (3, 13), (4, 12), (5, 12), (6, 11), (6, 10), (6, 10), (6, 9),
                         (6, 9), (6, 8), (5, 8), (5, 7), (4, 6), (3, 5), (2, 4), (1, 2)),
    'Flick up 16 late': ((1, 13), (2, 13), (3, 13), (4, 13), (5, 13), (5, 12), (6, 12), (6, 11),
                         (7, 11), (7, 10), (7, 9), (6, 8), (5, 7), (4, 6), (3, 4), (2, 3)),
}


def torso_candidates(torso: list[str], current_trail: list[str]) -> dict[str, list[str]]:
    turned = turn_ccw(torso)
    t = {'Turned (exact)': turned}
    # Same chunk with the outline pulled to the very ends so seams overlap.
    g = grid(turned)
    for y in range(16):
        row = ''.join(g[y])
        if row.strip('0'):
            left = len(row) - len(row.lstrip('0'))
            if left > 0 and y in range(2, 13):
                g[y][left - 1] = '1'
    t['Turned, closed seam'] = rows_of(g)
    t['Turned, flipped grain'] = [r[::-1] for r in turned]
    return t


def main() -> None:
    frames = make_frames(load_source(ROOT / 'roms/z2.nes'), 24)
    torso = torso_chunk(frames)
    turned = turn_ccw(torso)
    # The trail now in the build, from the same recipes assets.py uses.
    pairs = assets.sprite_pairs(torso)
    graphics = {0x06: pairs[0], 0x08: pairs[1]}
    current = assets.encounter_trail_rows(graphics)
    corners = {'In build': assets.encounter_connector_rows(graphics)}
    data = {
        'poses': {n: frames[n][:32] for n in BEND_POSES},
        'corners': {**corners, **corner_candidates(torso)},
        'torsos': torso_candidates(torso, current),
        'tips': tip_candidates(turned),
        'current_trail': current,
    }
    html = (Path(__file__).with_name('trail_candidates.html')).read_text(encoding='utf-8')
    out = ROOT / 'build/trail-candidates.html'
    out.write_text(html.replace('/*DATA*/null', json.dumps(data)), encoding='utf-8')
    for kind in ('corners', 'torsos', 'tips'):
        for name, rows in data[kind].items():
            print(f'[{kind}] {name}')
            for r in rows:
                print('   ', r.replace('0', '.'))
    print('wrote', out)


if __name__ == '__main__':
    main()
