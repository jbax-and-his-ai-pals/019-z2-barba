"""Generate authentic, animated NES pixel-art previews and WAV audio from real game assets.

All sprites, portraits, clouds, fireballs, flames, tiles, and DPCM audio are
extracted directly from roms/z2.nes, roms/waldo.nes, assets/, boss_art.py,
game_over_art.py, game_over_audio.py, and assets.py into web/previews/ (gitignored).
"""
from __future__ import annotations

import json
import shutil
import struct
import wave
import zlib
from pathlib import Path

import assets
import boss_art
import game_over_art
import game_over_audio
from nes import CHR_OFFSET, decode_tile, load_source, prg_offset

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "web" / "previews"

RGBA = tuple[int, int, int, int]
TRANSPARENT: RGBA = (0, 0, 0, 0)

# NES-authentic palettes (index 0 = transparent)
PAL_BARBA: list[RGBA] = [TRANSPARENT, (194, 43, 25, 255), (255, 168, 57, 255), (255, 243, 205, 255)]
PAL_SCALES: list[RGBA] = [TRANSPARENT, (24, 60, 156, 255), (92, 180, 255, 255), (236, 248, 255, 255)]
PAL_GOLD: list[RGBA] = [TRANSPARENT, (140, 82, 12, 255), (245, 184, 65, 255), (255, 248, 220, 255)]
PAL_EMERALD: list[RGBA] = [TRANSPARENT, (18, 92, 52, 255), (61, 220, 151, 255), (225, 255, 240, 255)]
PAL_LINK: list[RGBA] = [TRANSPARENT, (16, 140, 36, 255), (248, 184, 120, 255), (168, 32, 16, 255)]
PAL_KNIGHT: list[RGBA] = [TRANSPARENT, (36, 48, 88, 255), (168, 184, 216, 255), (255, 112, 67, 255)]
PAL_FIRE: list[RGBA] = [TRANSPARENT, (210, 48, 24, 255), (255, 152, 36, 255), (255, 246, 168, 255)]
PAL_ITEM: list[RGBA] = [TRANSPARENT, (184, 48, 24, 255), (245, 184, 65, 255), (255, 248, 220, 255)]
PAL_VILLAGER: list[RGBA] = [TRANSPARENT, (48, 96, 184, 255), (248, 184, 120, 255), (248, 248, 248, 255)]
PAL_BLUE_WATER: list[RGBA] = [TRANSPARENT, (12, 28, 120, 255), (32, 88, 236, 255), (140, 220, 255, 255)]
PAL_FOUL: list[RGBA] = [TRANSPARENT, (15, 15, 15, 255), (61, 184, 72, 255), (220, 238, 168, 255)]
PAL_GAME_OVER: list[RGBA] = [TRANSPARENT, (15, 15, 15, 255), (168, 24, 24, 255), (228, 56, 44, 255)]
PAL_CRYSTAL: list[RGBA] = [TRANSPARENT, (24, 64, 140, 255), (91, 192, 235, 255), (232, 250, 255, 255)]
PAL_CLOUD: list[RGBA] = [TRANSPARENT, (188, 224, 255, 255), (228, 244, 255, 255), (255, 255, 255, 255)]


def write_rgba_png(path: Path, pixels: list[list[RGBA]]) -> None:
    height = len(pixels)
    width = len(pixels[0])
    raw = b"".join(b"\0" + b"".join(bytes(px) for px in row) for row in pixels)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def new_canvas(w: int, h: int, fill: RGBA = TRANSPARENT) -> list[list[RGBA]]:
    return [[fill for _ in range(w)] for _ in range(h)]


def blit_rows(canvas: list[list[RGBA]], rows: list[str], pal: list[RGBA], x: int, y: int, flip_x: bool = False) -> None:
    h, w = len(canvas), len(canvas[0])
    for iy, row in enumerate(rows):
        src = row[::-1] if flip_x else row
        for ix, ch in enumerate(src):
            idx = int(ch)
            if idx != 0 and 0 <= y + iy < h and 0 <= x + ix < w:
                canvas[y + iy][x + ix] = pal[idx]


def rect(canvas: list[list[RGBA]], x: int, y: int, w: int, h: int, color: RGBA) -> None:
    ch, cw = len(canvas), len(canvas[0])
    for iy in range(y, y + h):
        if 0 <= iy < ch:
            for ix in range(x, x + w):
                if 0 <= ix < cw:
                    canvas[iy][ix] = color


def paint_z2_grass_bg(c: list[list[RGBA]], ground_y: int) -> None:
    """Paint a Vanilla Z2 early Bit/Bot grass encounter background (sky + distant bush + grass + earth)."""
    w, h = len(c[0]), len(c)
    rect(c, 0, 0, w, ground_y, (92, 148, 252, 255))  # NES sky blue
    # Distant grass hillocks
    for hx in range(0, w, 24):
        rect(c, hx + 2, ground_y - 5, 16, 5, (0, 148, 0, 255))
        rect(c, hx + 5, ground_y - 8, 10, 3, (0, 168, 0, 255))
    # Foreground grass edge + earth
    rect(c, 0, ground_y, w, 4, (0, 168, 0, 255))
    rect(c, 0, ground_y + 2, w, 2, (128, 208, 16, 255))
    rect(c, 0, ground_y + 4, w, h - (ground_y + 4), (168, 80, 0, 255))
    for dx in range(4, w, 12):
        rect(c, dx, ground_y + 6, 4, 2, (112, 48, 0, 255))


def strip(frames: list[list[list[RGBA]]]) -> list[list[RGBA]]:
    h = len(frames[0])
    return [sum((f[y] for f in frames), []) for y in range(h)]


def tile_8x8(rom: bytes, bank: int, tile: int) -> list[str]:
    start = CHR_OFFSET + bank * 4096 + tile * 16
    return ["".join(map(str, row)) for row in decode_tile(rom[start : start + 16])]


def tile_pair(rom: bytes, bank: int, tile: int) -> list[str]:
    return boss_art.source_pair(rom, tile, bank=bank)


def bytes_to_8x8(data: bytes) -> list[str]:
    return ["".join(map(str, row)) for row in decode_tile(data)]


def bytes_to_8x16(data: bytes) -> list[str]:
    return bytes_to_8x8(data[:16]) + bytes_to_8x8(data[16:32])


def draw_full_barba(
    c: list[list[RGBA]],
    barba_frames: dict[str, list[str]],
    graphics: dict[int, bytes],
    pose: str,
    pal: list[RGBA],
    x: int,
    y: int,
    tail_flick: bool = False,
) -> None:
    """Draw 24x48 Barba facing right WITH the curved junction, horizontal torso, and flicking tail."""
    # Delayed-Y trail behind Barba's left (back) side:
    # near torso (x-8), outer torso (x-16), near tip (x-24), far tip (x-32).
    torso_near = bytes_to_8x16(graphics[assets.ENCOUNTER_TRAIL_PAIRS[0]])
    torso_far = bytes_to_8x16(graphics[assets.ENCOUNTER_TRAIL_PAIRS[1]])
    tip_near = bytes_to_8x16(graphics[assets.ENCOUNTER_TRAIL_PAIRS[2]])
    tip_far = bytes_to_8x16(graphics[assets.ENCOUNTER_TRAIL_PAIRS[3]])
    tip_y = y + (31 if tail_flick else 33)
    blit_rows(c, tip_far, pal, x - 32, tip_y, flip_x=True)
    blit_rows(c, tip_near, pal, x - 24, tip_y, flip_x=True)
    blit_rows(c, torso_far, pal, x - 16, y + 32, flip_x=True)
    blit_rows(c, torso_near, pal, x - 8, y + 32, flip_x=True)

    # Clip the bottom 16px of the upright 24x48 frame so the curved junction
    # pieces (TRAIL_BEND_BACK at x, TRAIL_BEND_CENTER at x+8) replace the standing feet.
    clipped = [
        ("0" * 24) if iy >= 32 else row
        for iy, row in enumerate(barba_frames[pose])
    ]
    blit_rows(c, clipped, pal, x, y, flip_x=True)
    bend_center = bytes_to_8x16(graphics[assets.ENCOUNTER_CONNECTOR_PAIRS[0]])
    bend_back = bytes_to_8x16(graphics[assets.ENCOUNTER_CONNECTOR_PAIRS[1]])
    blit_rows(c, bend_back, pal, x, y + 32, flip_x=True)
    blit_rows(c, bend_center, pal, x + 8, y + 32, flip_x=True)


def build_link_frames(rom: bytes) -> list[list[list[RGBA]]]:
    """Right-facing Link standing/walking cleanly on a Z2 grass encounter background."""
    top_l = tile_pair(rom, 0, 0x00)
    top_r = tile_pair(rom, 0, 0x02)
    # Use standing/idle legs ($08/$0A) and gentle step ($04/$06) facing right (mirrored from left-facing CHR)
    leg_l = tile_pair(rom, 0, 0x08)
    leg_r = tile_pair(rom, 0, 0x0A)
    step_l = tile_pair(rom, 0, 0x04)
    step_r = tile_pair(rom, 0, 0x06)
    frames = []
    for i in range(4):
        c = new_canvas(64, 56)
        paint_z2_grass_bg(c, 46)
        dy = 1 if i == 1 else 0
        # Facing right: flip_x=True swaps left/right columns
        blit_rows(c, top_r, PAL_LINK, 24, 14 + dy, flip_x=True)
        blit_rows(c, top_l, PAL_LINK, 32, 14 + dy, flip_x=True)
        if i in (0, 2):
            blit_rows(c, leg_r, PAL_LINK, 24, 30, flip_x=True)
            blit_rows(c, leg_l, PAL_LINK, 32, 30, flip_x=True)
        else:
            blit_rows(c, step_r, PAL_LINK, 24, 30, flip_x=True)
            blit_rows(c, step_l, PAL_LINK, 32, 30, flip_x=True)
        frames.append(c)
    return frames


def build_barba_frames(barba_frames: dict[str, list[str]], graphics: dict[int, bytes]) -> list[list[list[RGBA]]]:
    """Full Barba with tail on a Z2 grass encounter background."""
    seq = [("idle", False), ("walk0", True), ("walk1", False), ("walk2", True)]
    frames = []
    for pose, flick in seq:
        c = new_canvas(64, 56)
        paint_z2_grass_bg(c, 46)
        draw_full_barba(c, barba_frames, graphics, pose, PAL_BARBA, 36, 0, tail_flick=flick)
        frames.append(c)
    return frames


def build_sword_frames(rom: bytes) -> list[list[list[RGBA]]]:
    """Stationary Link performing his sword slash on a Z2 grass encounter background."""
    top_l = tile_pair(rom, 0, 0x00)
    top_r = tile_pair(rom, 0, 0x02)
    slash_head = tile_pair(rom, 0, 0x26)
    sword = tile_pair(rom, 0, 0x40)
    leg_l = tile_pair(rom, 0, 0x08)
    leg_r = tile_pair(rom, 0, 0x0A)
    frames = []
    for i in range(4):
        c = new_canvas(76, 56)
        paint_z2_grass_bg(c, 46)
        if i in (1, 2):
            blit_rows(c, top_r, PAL_LINK, 22, 15, flip_x=True)
            blit_rows(c, slash_head, PAL_LINK, 30, 15, flip_x=True)
            blit_rows(c, sword, PAL_LINK, 38, 19, flip_x=True)
        else:
            blit_rows(c, top_r, PAL_LINK, 22, 14, flip_x=True)
            blit_rows(c, top_l, PAL_LINK, 30, 14, flip_x=True)
        blit_rows(c, leg_r, PAL_LINK, 22, 30, flip_x=True)
        blit_rows(c, leg_l, PAL_LINK, 30, 30, flip_x=True)
        frames.append(c)
    return frames


def build_volley_frames(rom: bytes, barba_frames: dict[str, list[str]], graphics: dict[int, bytes]) -> list[list[list[RGBA]]]:
    """Stationary Barba in open-jaw attack pose with ONLY the fireballs streaming out."""
    fb0 = tile_pair(rom, 0, 0x84)
    fb1 = tile_pair(rom, 0, 0x86)
    frames = []
    for i in range(4):
        c = new_canvas(76, 56)
        paint_z2_grass_bg(c, 46)
        draw_full_barba(c, barba_frames, graphics, "attack", PAL_BARBA, 20, 0, tail_flick=False)
        # Fireballs advance diagonally from snout across the 4 frames
        for s in range(i + 1):
            fx = 44 + (i - s) * 8
            fy = 12 + (i - s) * 4
            if fx < 70:
                blit_rows(c, fb0 if (s + i) % 2 == 0 else fb1, PAL_FIRE, fx, fy)
        frames.append(c)
    return frames


def build_palette_shuffle_frames(barba_frames: dict[str, list[str]], graphics: dict[int, bytes]) -> list[list[list[RGBA]]]:
    pals = [PAL_BARBA, PAL_SCALES, PAL_EMERALD, PAL_GOLD]
    cycle = [
        ("walk0", True), ("walk1", False), ("walk2", True), ("idle", False),
        ("walk0", True), ("walk1", False), ("walk2", True), ("idle", False),
        ("attack", True), ("attack", False), ("idle", False), ("idle", True),
    ]
    frames = []
    for pal in pals:
        for pose, flick in cycle:
            c = new_canvas(64, 56)
            paint_z2_grass_bg(c, 46)
            draw_full_barba(c, barba_frames, graphics, pose, pal, 36, 0, tail_flick=flick)
            frames.append(c)
    return frames


def build_rebound_frames(rom: bytes) -> list[list[list[RGBA]]]:
    ik_head = tile_pair(rom, 3, 0x90)
    ik_shield = tile_pair(rom, 3, 0x92)
    ik_body = tile_pair(rom, 3, 0x94)
    fb0 = tile_pair(rom, 0, 0x84)
    fb1 = tile_pair(rom, 0, 0x86)
    arc = [(8, 14), (24, 18), (34, 10), (16, 4)]
    frames = []
    for i in range(4):
        c = new_canvas(64, 48)
        rect(c, 0, 0, 64, 40, (20, 24, 36, 255))
        rect(c, 0, 40, 64, 8, (64, 72, 104, 255))
        blit_rows(c, ik_head, PAL_KNIGHT, 42, 8)
        blit_rows(c, ik_shield, PAL_KNIGHT, 34, 14)
        blit_rows(c, ik_body, PAL_KNIGHT, 42, 24)
        fx, fy = arc[i]
        blit_rows(c, fb0 if i % 2 == 0 else fb1, PAL_FIRE, fx, fy)
        frames.append(c)
    return frames


def build_spells_frames(rom: bytes, barba_frames: dict[str, list[str]], graphics: dict[int, bytes]) -> list[list[list[RGBA]]]:
    barba_json = json.loads((ROOT / "assets" / "barba.json").read_text(encoding="utf-8"))
    small_a = barba_json["small"]
    small_b = barba_json["small_step"]
    fb0 = tile_pair(rom, 0, 0x84)
    fb1 = tile_pair(rom, 0, 0x86)
    frames = []
    for i in range(4):
        c = new_canvas(64, 56)
        paint_z2_grass_bg(c, 46)
        if i == 0:
            draw_full_barba(c, barba_frames, graphics, "idle", PAL_SCALES, 26, 0)
        elif i == 1:
            blit_rows(c, small_a, PAL_BARBA, 24, 18, flip_x=True)
        elif i == 2:
            draw_full_barba(c, barba_frames, graphics, "attack", PAL_BARBA, 20, 0)
            blit_rows(c, fb0, PAL_FIRE, 46, 12)
        else:
            blit_rows(c, small_b, PAL_FIRE, 24, 8, flip_x=True)
            for k in range(3):
                blit_rows(c, fb0 if k % 2 == 0 else fb1, PAL_FIRE, 10 + k * 16, 20 + (k % 2) * 8)
        frames.append(c)
    return frames


def build_scenery_frames(rom: bytes) -> list[list[list[RGBA]]]:
    """Real Z2 Bank 5 encounter clouds ($B3-$B8) drifting over Z2 grass encounter sky."""
    c_top = [tile_8x8(rom, 5, 0xB3), tile_8x8(rom, 5, 0xB5), tile_8x8(rom, 5, 0xB7)]
    c_bot = [tile_8x8(rom, 5, 0xB4), tile_8x8(rom, 5, 0xB6), tile_8x8(rom, 5, 0xB8)]
    frames = []
    for i in range(4):
        c = new_canvas(72, 48)
        paint_z2_grass_bg(c, 38)
        cx = (8 + i * 8) % 48
        for col in range(3):
            blit_rows(c, c_top[col], PAL_CLOUD, cx + col * 8, 6)
            blit_rows(c, c_bot[col], PAL_CLOUD, cx + col * 8, 14)
        frames.append(c)
    return frames


def build_saria_frames(rom: bytes, foul: bool) -> list[list[list[RGBA]]]:
    """Vanilla Saria Blue River vs Barba Saria Foul Water."""
    tile = tile_8x8(rom, 17, 0x6E)
    pal = PAL_FOUL if foul else PAL_BLUE_WATER
    frames = []
    for i in range(4):
        c = new_canvas(56, 36)
        shift = (i * 2) if foul else (i % 2)
        for ty in (6, 14, 22):
            for tx in range(0, 56, 8):
                blit_rows(c, tile, pal, (tx + shift) % 56, ty)
        frames.append(c)
    return frames


def build_palace_roar_frames(rom: bytes) -> list[list[list[RGBA]]]:
    crystal = tile_pair(rom, 0, 0x72)
    frames = []
    for i in range(4):
        c = new_canvas(64, 40)
        rect(c, 0, 0, 64, 40, (16, 20, 32, 255))
        sx = (0, 2, -2, 1)[i]
        blit_rows(c, crystal, PAL_CRYSTAL, 28 + sx, 6)
        rect(c, 4 + sx, 28, 56, 8, (56, 72, 112, 255))
        glow = (255, 196, 84, 255) if i % 2 else (120, 160, 220, 255)
        rect(c, 10 + sx + (2 - i) * 4, 29, 8, 4, glow)
        rect(c, 46 + sx - (2 - i) * 4, 29, 8, 4, glow)
        frames.append(c)
    return frames


def build_boss_meter_frames(rom: bytes) -> list[list[list[RGBA]]]:
    pip = tile_8x8(rom, 7, 0xC6)
    frames = []
    for i in range(4):
        c = new_canvas(64, 24)
        pips = 8 - i * 2
        for p in range(8):
            pal = PAL_FIRE if p < pips else [TRANSPARENT, (40, 44, 56, 255), (52, 58, 72, 255), (68, 74, 92, 255)]
            blit_rows(c, pip, pal, 4 + p * 7, 8)
        frames.append(c)
    return frames


def build_title_cliff_frames(rom: bytes) -> list[list[list[RGBA]]]:
    head_closed = boss_art.resize_x(boss_art.source_head(rom, "closed"), 24)
    head_open = boss_art.resize_x(boss_art.source_head(rom, "open"), 24)
    lava_a = tile_8x8(rom, assets.TITLE_CHR_BANK, 0x68)
    lava_b = tile_8x8(rom, assets.TITLE_CHR_BANK, 0x69)
    frames = []
    for i in range(4):
        c = new_canvas(64, 40)
        rect(c, 36, 18, 24, 14, (44, 34, 42, 255))
        blit_rows(c, head_open if i in (1, 2) else head_closed, PAL_BARBA, 16, 4)
        for lx in range(0, 64, 8):
            tile = lava_a if ((lx // 8 + i) % 2 == 0) else lava_b
            blit_rows(c, tile, PAL_FIRE, lx, 32)
        frames.append(c)
    return frames


def build_game_over_ganon_frames(rom: bytes) -> list[list[list[RGBA]]]:
    """Vanilla Ganon Game Over silhouette decoded directly from roms/z2.nes."""
    mask = game_over_art._ganon_mask(rom)
    # Ganon's portrait spans roughly x=80..176, y=112..224 -> downsample 2x to 48x56
    c_base = new_canvas(48, 56, (15, 15, 15, 255))
    for y in range(56):
        for x in range(48):
            sy, sx = 112 + y * 2, 80 + x * 2
            if sy < 240 and sx < 256 and mask[sy][sx]:
                c_base[y][x] = (216, 40, 28, 255)
    frames = []
    for i in range(4):
        dy = 1 if i % 2 else 0
        c = new_canvas(48, 56, (15, 15, 15, 255))
        for y in range(56 - dy):
            c[y + dy] = c_base[y][:]
        frames.append(c)
    return frames


def build_game_over_link_frames(rom: bytes) -> list[list[list[RGBA]]]:
    """Barba Link Game Over portrait compiled by game_over_art.compile_game_over_link(rom)."""
    tiles, macro = game_over_art.compile_game_over_link(rom)
    full = new_canvas(80, 96, (15, 15, 15, 255))
    idx = 0
    while idx < len(macro) and macro[idx] != 0xFF:
        addr = macro[idx] * 256 + macro[idx + 1]
        flags = macro[idx + 2]
        idx += 3
        count = flags & 63
        for k in range(count):
            tid = macro[idx] if (flags & 64) else macro[idx + k]
            if tid in tiles:
                px = ((addr & 31) - 11) * 8
                py = ((addr - 0x2000) // 32 - 8) * 8
                if 0 <= px < 80 and 0 <= py < 96:
                    blit_rows(full, bytes_to_8x8(tiles[tid]), PAL_GAME_OVER, px, py)
            addr += 32 if (flags & 128) else 1
        idx += 1 if (flags & 64) else count

    small = new_canvas(48, 56, (15, 15, 15, 255))
    for y in range(48):
        for x in range(40):
            small[y + 4][x + 4] = full[y * 2][x * 2]

    frames = []
    for i in range(4):
        dy = 1 if i % 2 else 0
        c = new_canvas(48, 56, (15, 15, 15, 255))
        for y in range(56 - dy):
            c[y + dy] = small[y][:]
        frames.append(c)
    return frames


def build_roar_audio_frames() -> list[list[list[RGBA]]]:
    bars = [
        [3, 6, 12, 8, 14, 7, 4],
        [6, 12, 16, 14, 10, 12, 6],
        [4, 9, 14, 16, 12, 8, 5],
        [2, 5, 8, 10, 7, 4, 2],
    ]
    frames = []
    for i in range(4):
        c = new_canvas(56, 28)
        for b, h in enumerate(bars[i]):
            rect(c, 6 + b * 7, 14 - h // 2, 4, h, (255, 107, 53, 255) if b % 2 == 0 else (245, 184, 65, 255))
        frames.append(c)
    return frames


def build_town_chaos_frames(rom: bytes) -> list[list[list[RGBA]]]:
    villager = tile_pair(rom, 7, 0xC0)
    fire_vals = list(assets.compile_town_fire(ROOT).values())
    fire_l = bytes_to_8x8(fire_vals[0])
    fire_r = bytes_to_8x8(fire_vals[1 % len(fire_vals)])
    frames = []
    for i in range(4):
        c = new_canvas(64, 40)
        vx = 14 + i * 7
        blit_rows(c, villager, PAL_VILLAGER, vx, 16)
        blit_rows(c, fire_l if i % 2 == 0 else fire_r, PAL_FIRE, vx - 10, 22)
        col = (245, 184, 65, 255) if i % 2 == 0 else (255, 107, 53, 255)
        rect(c, 34, 4, 24, 6, col)
        frames.append(c)
    return frames


def build_portal_frames() -> list[list[list[RGBA]]]:
    barba_json = json.loads((ROOT / "assets" / "barba.json").read_text(encoding="utf-8"))
    small = barba_json["small"]
    frames = []
    for i in range(4):
        c = new_canvas(56, 40)
        for y in range(6, 34, 2):
            wx = 20 + ((y + i * 3) % 4) - 1
            col = (91, 192, 235, 255) if (y + i) % 4 == 0 else (186, 104, 248, 255)
            rect(c, wx, y, 16, 2, col)
        blit_rows(c, small, PAL_BARBA, 20, 12, flip_x=True)
        frames.append(c)
    return frames


def build_item_shuffle_frames(rom: bytes) -> list[list[list[RGBA]]]:
    items = [
        tile_pair(rom, 0, 0x72),
        tile_pair(rom, 0, 0x78),
        tile_pair(rom, 0, 0x7C),
        tile_pair(rom, 0, 0x68),
    ]
    frames = []
    for item in items:
        c = new_canvas(32, 32)
        blit_rows(c, item, PAL_ITEM, 12, 8)
        frames.append(c)
    return frames


def _write_pcm_wav(path: Path, samples: list[float], sample_rate: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 1-pole DC blocker + peak normalization to 0.85 so DAC midpoint offsets never click or clip.
    filtered: list[float] = []
    prev_x = 0.0
    prev_y = 0.0
    for x in samples:
        y = x - prev_x + 0.996 * prev_y
        prev_x = x
        prev_y = y
        filtered.append(y)
    peak = max((abs(v) for v in filtered), default=1.0) or 1.0
    scale = 27850.0 / peak
    pcm_bytes = bytearray()
    for s in filtered:
        val = max(-32767, min(32767, round(s * scale)))
        pcm_bytes += struct.pack("<h", val)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(pcm_bytes))


def _render_laugh_sequence(samples: list[bytes], dmc_rate_hz: float, out_hz: int = 44100) -> list[float]:
    """Render 5 NES Game Over laugh DPCM clips at native 23-frame spacing and continuous DAC level."""
    total = round((4 * 23 / 60.099 + 0.35) * out_hz)
    values = [0.0] * total
    level = 64
    for number, sample in enumerate(samples):
        pcm = game_over_audio.decode(sample, level)
        level = pcm[-1]
        start = round(number * 23 / 60.099 * out_hz)
        dur_samples = round(len(pcm) * out_hz / dmc_rate_hz)
        for i in range(dur_samples):
            if start + i >= total:
                break
            src_idx = min(len(pcm) - 1, int(i * dmc_rate_hz / out_hz))
            values[start + i] = (pcm[src_idx] - 64) / 64.0
        # Hold the resting DAC level until the next laugh rather than snapping to 0.
        next_start = round((number + 1) * 23 / 60.099 * out_hz) if number < len(samples) - 1 else total
        tail_val = (level - 64) / 64.0
        for i in range(start + dur_samples, min(total, next_start)):
            values[i] = tail_val
    return values


def export_audio_previews(rom: bytes) -> None:
    """Export real WAV audio previews: Sampled Roar + authentic 5-tick Ganon and Barba Link laugh sequences."""
    from roar_sample import CPU_HZ, PERIODS

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    roar_src = ROOT / "assets" / "roar.wav"
    if roar_src.exists():
        shutil.copy2(roar_src, OUT_DIR / "roar_sampled.wav")

    native_clips: list[bytes] = []
    for entry in game_over_audio.LAUGH_ENTRIES:
        table = prg_offset(6, 0x917B + entry * 2)
        start = prg_offset(7, 0xC000 + rom[table] * 64)
        native_clips.append(rom[start : start + rom[table + 1] * 16 + 1])

    dmc_rate_15 = CPU_HZ / PERIODS[15]
    ganon_pcm = _render_laugh_sequence(native_clips, dmc_rate_15)
    _write_pcm_wav(OUT_DIR / "ganon_laugh_seq.wav", ganon_pcm, 44100)

    raised_clips = [data for _, data, _ in game_over_audio.compile_laughs(rom)]
    link_pcm = _render_laugh_sequence(raised_clips, dmc_rate_15)
    _write_pcm_wav(OUT_DIR / "link_laugh_seq.wav", link_pcm, 44100)
    write_audio_data_js()


def write_audio_data_js(out_dir: Path = OUT_DIR) -> Path:
    """Bundle preview WAVs as base64 JS data so Web Audio works on file:// without CORS errors."""
    import base64

    payload: dict[str, str] = {}
    for name in ("roar_sampled.wav", "ganon_laugh_seq.wav", "link_laugh_seq.wav"):
        wav_path = out_dir / name
        if wav_path.is_file():
            payload[f"previews/{name}"] = base64.b64encode(wav_path.read_bytes()).decode("ascii")
    out_path = out_dir / "audio_data.js"
    out_path.write_text(f"window.BARBA_AUDIO_DATA = {json.dumps(payload)};\n", encoding="utf-8")
    return out_path


def generate_all(source_path: Path = ROOT / "roms" / "z2.nes") -> list[Path]:
    rom = load_source(source_path)
    barba_frames = boss_art.make_frames(rom)
    _, graphics, _, _ = assets.compile_assets(ROOT, source_path)
    specs = {
        "link_idle.png": build_link_frames(rom),
        "sword_slash.png": build_sword_frames(rom),
        "barba_hero.png": build_barba_frames(barba_frames, graphics),
        "barba_palettes.png": build_palette_shuffle_frames(barba_frames, graphics),
        "firebreath_volley.png": build_volley_frames(rom, barba_frames, graphics),
        "ironknuckle_rebound.png": build_rebound_frames(rom),
        "barba_spells.png": build_spells_frames(rom, barba_frames, graphics),
        "scenery_anim.png": build_scenery_frames(rom),
        "vanilla_saria_river.png": build_saria_frames(rom, False),
        "saria_water.png": build_saria_frames(rom, True),
        "palace_roar.png": build_palace_roar_frames(rom),
        "boss_meter.png": build_boss_meter_frames(rom),
        "title_cliff.png": build_title_cliff_frames(rom),
        "game_over_ganon.png": build_game_over_ganon_frames(rom),
        "game_over_link.png": build_game_over_link_frames(rom),
        "roar_audio.png": build_roar_audio_frames(),
        "town_chaos.png": build_town_chaos_frames(rom),
        "crossover_portals.png": build_portal_frames(),
        "item_shuffle.png": build_item_shuffle_frames(rom),
    }
    written = []
    for name, frames in specs.items():
        out = OUT_DIR / name
        write_rgba_png(out, strip(frames))
        written.append(out)
    export_audio_previews(rom)
    return written


def generate_waldo_tagger(
    waldo_rom_path: Path = ROOT / "roms" / "waldo.nes",
    crowd_json_path: Path = ROOT / "assets" / "waldo_crowd.json",
) -> int:
    """Extract Waldo non-Waldo crowd descriptors + sprite atlas for the web tile tagger."""
    if not waldo_rom_path.exists() or not crowd_json_path.exists():
        return 0
    rom = waldo_rom_path.read_bytes()
    prg_total = rom[4] * 16384
    chr_base = 16 + prg_total
    crowd_cfg = json.loads(crowd_json_path.read_text(encoding="utf-8"))
    flee_set = {tuple(x) for x in crowd_cfg.get("flee", [])}
    hide_set = {tuple(x) for x in crowd_cfg.get("hide", [])}

    level_names = {
        4: "Level 1 — Train Station (Bank 4)",
        5: "Level 2 — Beach (Bank 5)",
        6: "Level 3 — Carnival (Bank 6)",
        7: "Level 4 — Castle (Bank 7)",
        8: "Level 5 — Subway (Bank 8)",
    }
    level_chr = {
        4: [17, 18, 19],
        5: [20, 21, 22],
        6: [23, 24, 25],
        7: [26, 27, 28],
        8: [29, 30, 31],
    }
    waldo_pals: list[list[RGBA]] = [
        [TRANSPARENT, (24, 36, 92, 255), (248, 184, 120, 255), (255, 255, 255, 255)],
        [TRANSPARENT, (168, 32, 24, 255), (248, 160, 64, 255), (255, 243, 205, 255)],
        [TRANSPARENT, (24, 112, 48, 255), (104, 212, 120, 255), (232, 255, 224, 255)],
        [TRANSPARENT, (64, 48, 120, 255), (168, 144, 240, 255), (244, 236, 255, 255)],
    ]

    entries: list[dict] = []
    sprites: list[list[list[RGBA]]] = []
    for prg_bank in (4, 5, 6, 7, 8):
        bank_off = 16 + prg_bank * 0x2000
        for band_idx in range(3):
            b4k = level_chr[prg_bank][band_idx]
            desc_ptr = int.from_bytes(rom[bank_off + 8 + band_idx * 2 : bank_off + 10 + band_idx * 2], "little")
            desc_off = bank_off + (desc_ptr - 0xA000)
            n_waldo = rom[desc_off]
            n_non_waldo = rom[desc_off + 1]
            for k in range(n_non_waldo):
                nw_off = desc_off + 2 + (n_waldo + k) * 6
                ew, eh = rom[nw_off], rom[nw_off + 1]
                tlist_ptr = int.from_bytes(rom[nw_off + 2 : nw_off + 4], "little")
                tlist_off = bank_off + (tlist_ptr - 0xA000)
                pal = waldo_pals[rom[nw_off + 5] & 0x03]
                pw, ph = max(8, ew * 8), max(8, eh * 8)
                canvas = new_canvas(pw, ph)
                for ty in range(eh):
                    for tx in range(ew):
                        tid = rom[tlist_off + ty * ew + tx]
                        toff = chr_base + b4k * 4096 + tid * 16
                        rows = ["".join(map(str, r)) for r in decode_tile(rom[toff : toff + 16])]
                        blit_rows(canvas, rows, pal, tx * 8, ty * 8)
                key = (prg_bank, band_idx, k)
                if ew == 1 and eh == 1:
                    st = "scrap"
                elif key in hide_set:
                    st = "hide"
                elif key in flee_set:
                    st = "flee"
                else:
                    st = "static"
                entries.append({
                    "bank": prg_bank,
                    "band": band_idx,
                    "idx": k,
                    "w": ew,
                    "h": eh,
                    "pw": pw,
                    "ph": ph,
                    "state": st,
                })
                sprites.append(canvas)

    cols = 20
    pad = 2
    row_heights: list[int] = []
    col_widths = [max((e["pw"] for i, e in enumerate(entries) if i % cols == c), default=8) for c in range(cols)]
    for r in range((len(entries) + cols - 1) // cols):
        row_entries = entries[r * cols : (r + 1) * cols]
        row_heights.append(max(e["ph"] for e in row_entries))
    atlas_w = sum(col_widths) + cols * pad
    atlas_h = sum(row_heights) + len(row_heights) * pad
    atlas = new_canvas(atlas_w, atlas_h)
    col_x = []
    cx = 0
    for cw in col_widths:
        col_x.append(cx)
        cx += cw + pad
    row_y = []
    ry = 0
    for rh in row_heights:
        row_y.append(ry)
        ry += rh + pad
    for i, (e, spr) in enumerate(zip(entries, sprites)):
        r, c = divmod(i, cols)
        ax, ay = col_x[c], row_y[r]
        e["ax"] = ax
        e["ay"] = ay
        for y, row in enumerate(spr):
            for x, px in enumerate(row):
                atlas[ay + y][ax + x] = px

    write_rgba_png(OUT_DIR / "waldo_atlas.png", atlas)
    payload = {
        "levels": [{"bank": b, "name": level_names[b]} for b in (4, 5, 6, 7, 8)],
        "atlas_w": atlas_w,
        "atlas_h": atlas_h,
        "descriptors": entries,
    }
    (ROOT / "web" / "waldo_tagger.js").write_text(f"window.WALDO_TAGGER_DATA = {json.dumps(payload)};\n")
    return len(entries)


NES_PALETTE_64: list[list[int]] = [
    [84, 84, 84],    [0, 30, 116],    [8, 16, 144],    [48, 0, 136],
    [68, 0, 100],    [92, 0, 48],     [84, 4, 0],      [60, 24, 0],
    [32, 42, 0],     [8, 58, 0],      [0, 64, 0],      [0, 60, 0],
    [0, 50, 60],     [0, 0, 0],       [0, 0, 0],       [0, 0, 0],
    [152, 150, 152], [8, 76, 196],    [48, 50, 236],   [92, 30, 228],
    [136, 20, 176],  [160, 20, 100],  [152, 34, 32],   [120, 60, 0],
    [84, 90, 0],     [40, 114, 0],    [8, 124, 0],     [0, 118, 40],
    [0, 102, 120],   [0, 0, 0],       [0, 0, 0],       [0, 0, 0],
    [236, 238, 236], [76, 154, 236],  [120, 124, 236], [176, 98, 236],
    [228, 84, 236],  [236, 88, 180],  [236, 106, 100], [212, 136, 32],
    [160, 170, 0],   [116, 196, 0],   [76, 208, 32],   [56, 204, 108],
    [56, 180, 204],  [60, 60, 60],    [0, 0, 0],       [0, 0, 0],
    [236, 238, 236], [168, 204, 236], [188, 188, 236], [212, 178, 236],
    [236, 174, 236], [236, 174, 212], [236, 180, 176], [228, 196, 144],
    [204, 210, 120], [180, 222, 120], [168, 226, 144], [152, 226, 180],
    [160, 214, 228], [160, 162, 160], [0, 0, 0],       [0, 0, 0],
]


def generate_feud_cast_dashboard(
    z2_path: Path = ROOT / "roms" / "z2.nes",
    feud_path: Path = ROOT / "roms" / "feud.nes",
) -> int:
    """Export raw 32x48 sprite grids, NES palette, and Stage Close-Up podium backdrop for the web cast dashboard."""
    if not z2_path.exists():
        return 0
    import feud_art
    import feud_cast

    z2 = load_source(z2_path)
    sprites = feud_cast.export_dashboard_sprites(z2)
    defaults = feud_cast.build_default_config()
    config = feud_cast.load_cast_config()

    has_stage_bg = False
    if feud_path.exists():
        feud = feud_path.read_bytes()
        prg = feud[16 : 16 + 32768]
        chr_rom = feud[16 + 32768 : 16 + 32768 + 131072]
        s0e = feud_art._decode_rle_screen(prg, chr_rom, 0x0E)
        # Render rows 15..27 (256x104 px) of Screen 0x0E using CHR Bank 0x06 and BG Pal 0 (16, 2C, 27, 0F)
        pal0 = [
            tuple(NES_PALETTE_64[0x16]) + (255,),
            tuple(NES_PALETTE_64[0x2C]) + (255,),
            tuple(NES_PALETTE_64[0x27]) + (255,),
            tuple(NES_PALETTE_64[0x0F]) + (255,),
        ]
        bg = new_canvas(256, 104, pal0[0])
        for row in range(15, 28):
            for col in range(32):
                # Clear the 5 contestant standing columns on rows 16..21 to solid wall ($16)
                if 16 <= row <= 21 and 6 <= col <= 25:
                    continue
                tid = s0e[row * 32 + col]
                if tid == 0:
                    continue
                off = 0x09 * 4096 + tid * 16
                dec = decode_tile(chr_rom[off : off + 16])
                py0 = (row - 15) * 8
                px0 = col * 8
                for y in range(8):
                    for x in range(8):
                        v = dec[y][x]
                        if v:
                            bg[py0 + y][px0 + x] = pal0[v]
        write_rgba_png(OUT_DIR / "feud_stage_bg.png", bg)
        has_stage_bg = True

    payload = {
        "nes_palette": NES_PALETTE_64,
        "has_stage_bg": has_stage_bg,
        "defaults": defaults,
        "config": config,
        "sprites": sprites,
    }
    (ROOT / "web" / "feud_cast_data.js").write_text(
        f"window.FEUD_CAST_DATA = {json.dumps(payload)};\n",
        encoding="utf-8",
    )
    return len(sprites)


if __name__ == "__main__":
    from duck_dashboard import generate_duck_tiles_dashboard

    files = generate_all()
    waldo_count = generate_waldo_tagger()
    feud_count = generate_feud_cast_dashboard()
    duck_count = generate_duck_tiles_dashboard()
    print(
        f"Generated {len(files)} real-asset preview strips, WAVs, "
        f"{waldo_count} Waldo descriptors, {feud_count} Feud cast sprites, "
        f"and {duck_count} Duck Hunt sprites in {OUT_DIR}"
    )
