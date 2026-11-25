"""Build-time Z2-derived CHR compiler for Super Barba Bros. (32 KB MMC3 CHR).

All Zelda II pixels are extracted at build time from ``roms/z2.nes`` (no
original game pixels are committed). Combines SMB1 base CHR with multi-bank
MMC3 CHR banks for:
  - R0=0  (2KB): Wyrmling (Small Barba) + shared fireballs, Bit/Bot, items, crystal flag
  - R0=2  (2KB): Super Barba (16x32 dragon) + shared $64..$7F
  - R0=12 (2KB): Inferno Barba (flame-crowned 16x32) + shared $64..$7F
  - R0=14 (2KB): Roaring Barba (open-jaw roar/fire) + shared $64..$7F
  - R0=24 (2KB): Roaring Wyrmling (open-jaw small) + shared $64..$7F
  - R1=16 (2KB): World Enemies (Stalfos, Ironknuckle, Geldarm, Wizzrobe, Bubble, Tome, Triforce Star)
  - R1=18 (2KB): Castle Boss & Captives (Villainous Link, Sword Beam, Bomb, Caged Zelda/Fairy/Toad)
  - R2=4/8 (1KB): BG HUD + Bricks + Palace Crystal Flagpole ($2F/$3D) shimmer pair
  - R3=5/10/11 (1KB): BG Scenery + Castle Triforce/Crystal Axe ($7B-$7E) shimmer pair
  - R4=6, R5=7 (2KB): BG Castle/Pipes/Title Screen RLE ($1EC0-$1FFF preserved)
"""
from __future__ import annotations

import json
from pathlib import Path

from assets import encounter_connector_rows, encounter_trail_rows
from boss_art import make_frames, resize_x, source_head, source_pair
from nes import CHR_OFFSET, decode_tile, encode_tile, write_png


# MMC3 CHR bank indices (1 KB units inside the 32 KB CHR buffer)
CHR_R0_WYRMLING      = 0
CHR_R0_BARBA         = 2
CHR_R2_WORLD_A       = 4
CHR_R3_WORLD         = 5
CHR_R4_BG            = 6
CHR_R5_BG            = 7
CHR_R2_WORLD_B       = 8
CHR_R3_WORLD_B       = 9
CHR_R3_CASTLE_A      = 10
CHR_R3_CASTLE_B      = 11
CHR_R0_INFERNO       = 12
CHR_R0_ROAR          = 14
CHR_R1_ENEMIES       = 16
CHR_R1_CASTLE        = 18
CHR_R0_WYRMLING_ROAR = 24

SMB_CHR_SIZE = 32 * 1024


def _flip_h(rows: list[str]) -> list[str]:
    return [r[::-1] for r in rows]


def _flip_v(rows: list[str]) -> list[str]:
    return list(reversed(rows))


def _z2_pair(z2: bytes, bank4k: int, tid: int) -> list[str]:
    return source_pair(z2, tid & 0xFE, bank4k)


def _z2_grid(z2: bytes, bank4k: int, grid: list[list[int | None]], *, flip_h: bool = False) -> list[str]:
    out: list[str] = []
    for row in grid:
        cols = [
            (['0' * 8] * 16) if tid is None else _z2_pair(z2, bank4k, tid)
            for tid in row
        ]
        for y in range(16):
            line = ''.join(c[y] for c in cols)
            out.append(line[::-1] if flip_h else line)
    return out


def _shrink_y(rows: list[str], target_h: int) -> list[str]:
    old_h = len(rows)
    return [rows[min(old_h - 1, (y * old_h + target_h // 2) // target_h)] for y in range(target_h)]


def _split_tiles(rows: list[str], cols: int, tile_rows: int) -> list[list[str]]:
    out: list[list[str]] = []
    for ty in range(tile_rows):
        for tx in range(cols):
            out.append([rows[ty * 8 + y][tx * 8 : (tx + 1) * 8] for y in range(8)])
    return out


def _stamp(canvas: list[list[str]], rows: list[str], ox: int, oy: int) -> None:
    h, w = len(canvas), len(canvas[0])
    for y, row in enumerate(rows):
        ny = oy + y
        if 0 <= ny < h:
            for x, ch in enumerate(row):
                nx = ox + x
                if ch != '0' and 0 <= nx < w:
                    canvas[ny][nx] = ch


def _put_tile(buf: bytearray, bank1k: int, tid_in_bank: int, rows: list[str]) -> None:
    assert 0 <= tid_in_bank < 64
    off = bank1k * 1024 + tid_in_bank * 16
    buf[off : off + 16] = encode_tile(rows)


def _put_sprite_tile(buf: bytearray, bank2k: int, tid: int, rows: list[str]) -> None:
    """Write one 8x8 tile at sprite tile index $00..$7F inside a 2 KB sprite bank."""
    assert 0 <= tid < 128, f'Sprite tile ${tid:02X} out of 2KB bank range'
    off = bank2k * 1024 + tid * 16
    buf[off : off + 16] = encode_tile(rows)


def _put_grid(buf: bytearray, bank2k: int, tids: list[int], rows: list[str], cols: int, tile_rows: int) -> None:
    tiles = _split_tiles(rows, cols, tile_rows)
    assert len(tiles) == len(tids)
    for tid, t in zip(tids, tiles):
        _put_sprite_tile(buf, bank2k, tid, t)


def _remap_rows(rows: list[str], mapping: dict[str, str]) -> list[str]:
    return [''.join(mapping.get(c, c) for c in r) for r in rows]


def _make_wyrmling_poses(z2: bytes, *, roaring: bool = False) -> dict[str, list[str]]:
    """Build 16x16 RIGHT-facing Small Barba poses from Zelda 2's overworld Barba sprite."""
    art_path = Path(__file__).resolve().parents[1] / 'assets' / 'barba.json'
    art = json.loads(art_path.read_text())
    small = list(art['small'])
    small_step = list(art['small_step'])
    front = list(art['front'])
    front_step = list(art['front_step'])

    def open_jaw(rows: list[str]) -> list[str]:
        out = [list(r) for r in rows]
        # Open the snout/jaw on the right side (rows 4..7, cols 11..15) for roar frames
        for y, row_patch in ((4, '22230'), (5, '20000'), (6, '10030'), (7, '11110')):
            for dx, ch in enumerate(row_patch):
                if 11 + dx < 16:
                    out[y][11 + dx] = ch
        return [''.join(r) for r in out]

    s0 = open_jaw(small) if roaring else small
    s1 = open_jaw(small_step) if roaring else small_step
    return {
        'stand': s0,
        'walk1': s0,
        'walk2': s1,
        'walk3': s0,
        'jump': s1,
        'skid': s1,
        'swim1': s0,
        'swim2': s1,
        'climb1': front,
        'climb2': front_step,
        'death': open_jaw(small),
    }


def _make_barba_poses(z2: bytes, *, inferno: bool = False, roaring: bool = False) -> dict[str, list[str]]:
    """Build 24px-wide Full Body Barba poses + 16x16 bend, horizontal torso, tail tip, and crouch."""
    f24 = make_frames(z2, 24)

    def adapt_32(pose_name: str, *, flame_crest: bool = False, leg_shift: int = 0) -> list[str]:
        src = _flip_h(f24[pose_name])  # 24x48 RIGHT-facing (neck in cols 0..15, snout in cols 16..23)
        head = src[0:14]
        neck = _shrink_y(src[14:46], 16)
        feet = src[46:48]
        rows = head + neck + feet
        canvas = [list(r) for r in rows]
        if flame_crest:
            for y, x, c in ((0, 4, '3'), (0, 6, '2'), (1, 3, '2'), (1, 5, '3'), (2, 2, '3')):
                if canvas[y][x] == '0':
                    canvas[y][x] = c
        if leg_shift != 0:
            for y in range(28, 32):
                r = ''.join(canvas[y][:16])
                if leg_shift > 0:
                    shifted = ('0' * leg_shift + r)[:16]
                else:
                    s = -leg_shift
                    shifted = (r[s:] + '0' * s)[:16]
                canvas[y][:16] = list(shifted)
        return [''.join(r) for r in canvas]

    head_pose = 'attack' if roaring else ('windup' if inferno else 'idle')
    walk_head = 'attack' if roaring else ('windup' if inferno else 'walk0')
    poses = {
        'stand': adapt_32(head_pose, flame_crest=inferno),
        'walk1': adapt_32(walk_head, flame_crest=inferno, leg_shift=-1),
        'walk2': adapt_32('attack' if roaring else 'walk1', flame_crest=inferno, leg_shift=0),
        'walk3': adapt_32('attack' if roaring else 'walk2', flame_crest=inferno, leg_shift=1),
        'skid':  adapt_32('hurt' if roaring else 'windup', flame_crest=inferno),
        'jump':  adapt_32('attack' if roaring else 'jump', flame_crest=inferno, leg_shift=-1),
        'swim1': adapt_32(walk_head, flame_crest=inferno),
        'swim2': adapt_32('attack' if roaring else 'walk2', flame_crest=inferno),
        'climb1': adapt_32('up', flame_crest=inferno),
        'climb2': adapt_32('attack' if roaring else 'up', flame_crest=inferno, leg_shift=1),
        'fire':  adapt_32('attack', flame_crest=True),
    }

    # Build authentic Z2 16x16 bend, horizontal torso chunk, and tapered tail tip from the upright neck
    idle_left = f24['idle']  # 24x48 LEFT-facing; neck is cols 8..23, rows 16..31
    neck_16 = [r[8:24] for r in idle_left[16:32]]
    pair_06 = encode_tile([r[0:8] for r in neck_16[0:8]]) + encode_tile([r[0:8] for r in neck_16[8:16]])
    pair_08 = encode_tile([r[8:16] for r in neck_16[0:8]]) + encode_tile([r[8:16] for r in neck_16[8:16]])
    gfx = {0x06: pair_06, 0x08: pair_08}
    bend_r = _flip_h(encounter_connector_rows(gfx))      # 16x16 RIGHT-facing elbow bend
    trail_r = _flip_h(encounter_trail_rows(gfx))         # 32x16 RIGHT-facing (tail_tip + horiz_torso)
    poses['bend'] = bend_r
    poses['torso'] = [r[16:32] for r in trail_r]
    poses['tail'] = [r[0:16] for r in trail_r]
    poses['crouch_bend'] = bend_r[0:8]                   # 16x8 corridor bend for crouching
    return poses


def _write_barba_bank(
    buf: bytearray,
    bank2k: int,
    z2: bytes,
    shared_tiles: dict[int, list[str]],
    *,
    inferno: bool = False,
    roaring: bool = False,
) -> None:
    """Populate a 2 KB R0 sprite bank for 24px-wide Full Body Super / Inferno / Roaring Barba."""
    poses = _make_barba_poses(z2, inferno=inferno, roaring=roaring)

    def head_24x16(pose_rows: list[str]) -> list[str]:
        return pose_rows[0:16]

    def neck_16x16(pose_rows: list[str]) -> list[str]:
        return [r[0:16] for r in pose_rows[16:32]]

    # Heads (3x2 = 6 tiles each)
    _put_grid(buf, bank2k, list(range(0x00, 0x06)), head_24x16(poses['stand']), 3, 2)   # $00..$05: normal head
    _put_grid(buf, bank2k, list(range(0x06, 0x0C)), head_24x16(poses['fire']), 3, 2)    # $06..$0B: fire/attack head
    _put_grid(buf, bank2k, list(range(0x0C, 0x12)), head_24x16(poses['climb1']), 3, 2)  # $0C..$11: climb head
    _put_grid(buf, bank2k, list(range(0x12, 0x18)), head_24x16(poses['skid']), 3, 2)    # $12..$17: skid/windup head

    # Upright Necks (2x2 = 4 tiles each, cols 0..15)
    _put_grid(buf, bank2k, list(range(0x18, 0x1C)), neck_16x16(poses['walk1']), 2, 2)   # $18..$1B: walk1 neck
    _put_grid(buf, bank2k, list(range(0x1C, 0x20)), neck_16x16(poses['stand']), 2, 2)   # $1C..$1F: stand/walk2 neck
    _put_grid(buf, bank2k, list(range(0x20, 0x24)), neck_16x16(poses['walk3']), 2, 2)   # $20..$23: walk3 neck
    _put_grid(buf, bank2k, list(range(0x24, 0x28)), neck_16x16(poses['jump']), 2, 2)    # $24..$27: jump neck
    _put_grid(buf, bank2k, list(range(0x28, 0x2C)), neck_16x16(poses['climb1']), 2, 2)  # $28..$2B: climb1 neck
    _put_grid(buf, bank2k, list(range(0x2C, 0x30)), neck_16x16(poses['climb2']), 2, 2)  # $2C..$2F: climb2 neck

    # Bend ($30..$33), Horizontal Torso Chunk ($34..$37), Tail Tip ($38..$3B), Crouch Bend ($3C..$3D)
    _put_grid(buf, bank2k, list(range(0x30, 0x34)), poses['bend'], 2, 2)
    _put_grid(buf, bank2k, list(range(0x34, 0x38)), poses['torso'], 2, 2)
    _put_grid(buf, bank2k, list(range(0x38, 0x3C)), poses['tail'], 2, 2)
    _put_grid(buf, bank2k, [0x3C, 0x3D], poses['crouch_bend'], 2, 1)

    # Grow intermediates ($4A..$4E)
    grow_tiles = _split_tiles(neck_16x16(poses['stand']), 2, 2)
    _put_sprite_tile(buf, bank2k, 0x4C, grow_tiles[0])
    _put_sprite_tile(buf, bank2k, 0x4D, grow_tiles[1])
    _put_sprite_tile(buf, bank2k, 0x4E, grow_tiles[3])
    _put_grid(buf, bank2k, [0x4A, 0x4B], [r[0:16] for r in poses['stand'][24:32]], 2, 1)

    for tid, rows in shared_tiles.items():
        _put_sprite_tile(buf, bank2k, tid, rows)


def _write_wyrmling_bank(
    buf: bytearray,
    bank2k: int,
    z2: bytes,
    shared_tiles: dict[int, list[str]],
    *,
    roaring: bool = False,
) -> None:
    """Populate a 2 KB R0 sprite bank for Small Barba (Zelda 2 overworld graphic)."""
    poses = _make_wyrmling_poses(z2, roaring=roaring)
    # Stand ($32..$35)
    _put_grid(buf, bank2k, [0x32, 0x33, 0x34, 0x35], poses['stand'], 2, 2)
    # Walk1 ($36..$39)
    _put_grid(buf, bank2k, [0x36, 0x37, 0x38, 0x39], poses['walk1'], 2, 2)
    # Walk2 ($3A, $46, $3B, $3C -> full 16x16 step frame without sharing $37)
    w2 = _split_tiles(poses['walk2'], 2, 2)
    _put_sprite_tile(buf, bank2k, 0x3A, w2[0])
    _put_sprite_tile(buf, bank2k, 0x46, w2[1])
    _put_sprite_tile(buf, bank2k, 0x3B, w2[2])
    _put_sprite_tile(buf, bank2k, 0x3C, w2[3])
    # Walk3 ($3D..$40)
    _put_grid(buf, bank2k, [0x3D, 0x3E, 0x3F, 0x40], poses['walk3'], 2, 2)
    # Skid ($41..$43, shares $32)
    sk = _split_tiles(poses['skid'], 2, 2)
    _put_sprite_tile(buf, bank2k, 0x41, sk[1])
    _put_sprite_tile(buf, bank2k, 0x42, sk[2])
    _put_sprite_tile(buf, bank2k, 0x43, sk[3])
    # Jump ($44, $45)
    jp = _split_tiles(poses['jump'], 2, 2)
    _put_sprite_tile(buf, bank2k, 0x44, jp[2])
    _put_sprite_tile(buf, bank2k, 0x45, jp[3])
    # Swim ($47, $48, $49)
    sw1 = _split_tiles(poses['swim1'], 2, 2)
    sw2 = _split_tiles(poses['swim2'], 2, 2)
    _put_sprite_tile(buf, bank2k, 0x47, sw1[3])
    _put_sprite_tile(buf, bank2k, 0x48, sw2[2])
    _put_sprite_tile(buf, bank2k, 0x49, sw2[3])
    # Climb ($50..$53) & Death ($54..$57) & Grow ($4F)
    _put_grid(buf, bank2k, [0x50, 0x51], poses['climb1'][8:16], 2, 1)
    _put_grid(buf, bank2k, [0x52, 0x53], poses['climb2'][8:16], 2, 1)
    _put_grid(buf, bank2k, [0x54, 0x55, 0x56, 0x57], poses['death'], 2, 2)
    _put_sprite_tile(buf, bank2k, 0x4F, _split_tiles(poses['walk2'], 2, 2)[2])

    for tid, rows in shared_tiles.items():
        _put_sprite_tile(buf, bank2k, tid, rows)


def _shared_r0_tiles(z2: bytes) -> dict[int, list[str]]:
    """Build tiles $64..$7F shared across all R0 sprite banks."""
    tiles: dict[int, list[str]] = {}

    # $64, $65: Flame-crowned Barba fireballs (8x8)
    tiles[0x64] = [
        '00300030',
        '01230120',
        '12331230',
        '12333221',
        '12333321',
        '01233210',
        '00122100',
        '00011000',
    ]
    tiles[0x65] = [
        '03003000',
        '01203210',
        '02313321',
        '12233321',
        '12333321',
        '01233210',
        '00122100',
        '00011000',
    ]
    # $66, $67, $68: Fireball flame burst explosion (for 2x2 mirrored burst)
    tiles[0x66] = [
        '00000010',
        '00000120',
        '00011230',
        '00122331',
        '01233332',
        '01233322',
        '00123210',
        '00012100',
    ]
    tiles[0x67] = [
        '00001000',
        '00102100',
        '01212200',
        '00223210',
        '11333210',
        '01232100',
        '00121000',
        '00010000',
    ]
    tiles[0x68] = [
        '01000010',
        '00100100',
        '00000000',
        '10000001',
        '00000000',
        '00100100',
        '01000010',
        '00000000',
    ]

    # $70..$73, $6D..$6F: Z2 Bot/Bit Slime (replacing Goomba!)
    # Z2 bank 0x14: 0xB2 is left half (8x16) of Bot Slime; H-flip forms symmetric 16x16 slime!
    bot_left = _z2_pair(z2, 0x14, 0xB2)
    bot_raw = [r + r[::-1] for r in bot_left]
    bot_tiles = _split_tiles(bot_raw, 2, 2)
    # In SMB1 Goomba uses FC FC 70 71 72 73 (top row=70,71; bot row=72,73)
    tiles[0x70] = bot_tiles[0]
    tiles[0x71] = bot_tiles[1]
    tiles[0x72] = bot_tiles[2]
    tiles[0x73] = bot_tiles[3]
    # Squashed Bot ($6D..$6F -> bottom 8px flattened slime)
    squash_l = ['0' * 8] * 3 + bot_tiles[0][3:5] + bot_tiles[2][5:8]
    squash_r = ['0' * 8] * 3 + bot_tiles[1][3:5] + bot_tiles[3][5:8]
    tiles[0x6D] = squash_l
    tiles[0x6E] = squash_r
    tiles[0x6F] = ['0' * 8] * 8

    # $76..$79: Power-up Mushroom / 1-Up -> Z2 Red/Magic Jar (16x16, symmetric via flip)
    # $76,$77 left half (top, bottom); $78,$79 unused or right half -> Z2 Magic Jar (bank 0x00, 0x8A/0x8B)
    jar_rows = _z2_pair(z2, 0x00, 0x8A)  # 8x16 jar! Stretch/center to 16x16
    jar_16 = resize_x(jar_rows, 14)
    jar_canvas = [['0'] * 16 for _ in range(16)]
    _stamp(jar_canvas, jar_16, 1, 0)
    jar_tiles = _split_tiles([''.join(r) for r in jar_canvas], 2, 2)
    tiles[0x76] = jar_tiles[0]
    tiles[0x77] = jar_tiles[1]
    tiles[0x78] = jar_tiles[2]
    tiles[0x79] = jar_tiles[3]

    # $7E, $7F: Flagpole Flag -> Palace Crystal / Triforce Banner (16x16)
    banner_l = [
        '11111111',
        '12222231',
        '12233221',
        '12333321',
        '12322321',
        '12233221',
        '12222221',
        '11111111',
    ]
    banner_r = [
        '11111110',
        '12222210',
        '12332210',
        '13333100',
        '12322100',
        '12221000',
        '11110000',
        '00000000',
    ]
    tiles[0x7E] = banner_l
    tiles[0x7F] = banner_r
    return tiles


def _make_z2_fireball_item(z2: bytes) -> list[str]:
    """Build 16x16 RIGHT-flying Z2 fireball item from bank 0 tile $84 (Barba's flame shot)."""
    fb8 = _flip_h(_z2_pair(z2, 0x00, 0x84)[5:13])
    return [''.join(c * 2 for c in r) for r in fb8 for _ in range(2)]


def _build_enemies_bank(buf: bytearray, bank2k: int, z2: bytes, smb_chr0: bytes) -> None:
    """Populate R1=16 (tiles $80..$FF) with Z2 Stalfos, Ironknuckle, Geldarm, Wizzrobe, Bubble."""
    # Copy SMB1 base $80..$FF first so score popups ($F0..$F5), $FC blank, $FF Sprite 0 stay intact
    buf[bank2k * 1024 : bank2k * 1024 + 2048] = smb_chr0[2048:4096]

    def put(tid: int, rows: list[str]) -> None:
        assert 0x80 <= tid <= 0xFF
        off = bank2k * 1024 + (tid - 0x80) * 16
        buf[off : off + 16] = encode_tile(rows)

    def put_grid(tids: list[int], rows: list[str], cols: int, tile_rows: int) -> None:
        for tid, t in zip(tids, _split_tiles(rows, cols, tile_rows)):
            put(tid, t)

    # 1. Stalfos (replaces Green Koopa $A0..$AB, 16x24 facing LEFT)
    # Z2 bank 0x14: F0, F2 (top), F4, F6 (walk1 bottom), F8, FA (walk2 bottom) - raw Z2 faces RIGHT, so flip_h=True
    st_w1 = _shrink_y(_z2_grid(z2, 0x14, [[0xF0, 0xF2], [0xF4, 0xF6]], flip_h=True), 24)
    st_w2 = _shrink_y(_z2_grid(z2, 0x14, [[0xF0, 0xF2], [0xF8, 0xFA]], flip_h=True), 24)
    put_grid([0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5], st_w1, 2, 3)
    put_grid([0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xAB], st_w2, 2, 3)
    # Stalfos shell/skull pile ($AC, $AD, $AE, $AF)
    skull_16 = st_w1[0:16]
    put_grid([0xAC, 0xAD, 0xAE, 0xAF], skull_16, 2, 2)

    # 2. Ironknuckle (Red/Blue/Throwing Ironknuckle at $B0..$BB + shield $BC/$BD -> wait Wizzrobe is $B8..$BD!)
    # Use $B0..$B7 + $C0..$CB (Bowser slots unused outside castles!) for Ironknuckle!
    ik_w1 = _shrink_y(_z2_grid(z2, 0x15, [[0x41, 0x43], [0x49, 0x4B]]), 24)
    ik_w2 = _shrink_y(_z2_grid(z2, 0x15, [[0x4D, 0x43], [0x51, 0x4B]]), 24)
    put_grid([0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5], ik_w1, 2, 3)
    put_grid([0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xCB], ik_w2, 2, 3)
    # Ironknuckle crouched shield/helmet ($CC, $CD, $CE, $CF)
    put_grid([0xCC, 0xCD, 0xCE, 0xCF], ik_w1[0:16], 2, 2)

    # 3. Geldarm (replaces Piranha Plant $E5, $E6, $EB, $EC, $ED, $EE, 16x24)
    # Z2 bank 0x08: 0x62 (8x16 head with antennae), 0x64 (8x16 body)
    g_head_8 = _z2_pair(z2, 0x08, 0x62)
    g_body_8 = _z2_pair(z2, 0x08, 0x64)
    # Widen to 12px centered in 16px, or mirrored left+right to 16px!
    g_head_16 = resize_x(g_head_8, 14)
    g_body_16 = resize_x(g_body_8, 14)
    geld_a = [['0'] * 16 for _ in range(24)]
    _stamp(geld_a, g_head_16, 1, 0)
    _stamp(geld_a, g_body_16[0:8], 1, 16)
    geld_b = [['0'] * 16 for _ in range(24)]
    _stamp(geld_b, g_head_16, 1, 2)
    _stamp(geld_b, g_body_16[4:12], 1, 18)
    g_tiles_a = _split_tiles([''.join(r) for r in geld_a], 2, 3)
    g_tiles_b = _split_tiles([''.join(r) for r in geld_b], 2, 3)
    # SMB1 Piranha uses: closed (E5 E5 E6 E6 EB EB) / open (EC EC ED ED EE EE)
    # Place Geldarm in unused World tiles ($90-$93, $9E-$9F and $BC-$BF, $E5-$E6)
    # so $80..$87 (bouncing coin, brick chunk, bouncing block) remain vanilla SMB1!
    put_grid([0x90, 0x91, 0x92, 0x93, 0x9E, 0x9F], [''.join(r) for r in geld_a], 2, 3)
    put_grid([0xBC, 0xBD, 0xBE, 0xBF, 0xE5, 0xE6], [''.join(r) for r in geld_b], 2, 3)

    # 4. Wizzrobe (replaces Lakitu $B8..$BD, 16x24 facing LEFT)
    # Z2 bank 0x14: D0, D2 (top), D4, D6 (bottom) -> 16x32, shrink to 16x24; D8, DA for cast frame
    wiz_1 = _shrink_y(_z2_grid(z2, 0x14, [[0xD0, 0xD2], [0xD4, 0xD6]]), 24)
    wiz_2 = _shrink_y(_z2_grid(z2, 0x14, [[0xD8, 0xDA], [0xD4, 0xD6]]), 24)
    put_grid([0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5], wiz_1, 2, 3)
    put_grid([0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xBB], wiz_2, 2, 3)

    # 5. Bubble (replaces Spiny & Spiny Egg $8E..$9D, 16x16 flaming skull)
    # Z2 bank 0x09: 0x3C (skull) composited inside bank 0x14: 0xDC (flaming aura)!
    bub_aura = _z2_pair(z2, 0x14, 0xDC)
    bub_skull = _z2_pair(z2, 0x09, 0x3C)
    bub_base = [list(r + r[::-1]) for r in bub_aura]
    _stamp(bub_base, bub_skull, 4, 0)
    bub_16 = [''.join(r) for r in bub_base]
    bub_16_flicker = [r[::-1] if y < 6 else r for y, r in enumerate(bub_16)]
    put_grid([0x96, 0x97, 0x98, 0x99], bub_16, 2, 2)
    put_grid([0x9A, 0x9B, 0x9C, 0x9D], bub_16_flicker, 2, 2)
    # Spiny egg / Podoboo ($8E..$91 and $D0, $D7) -> flaming Bubble
    put_grid([0x8E, 0x8F, 0x94, 0x95], bub_16, 2, 2)
    put(0xD0, _split_tiles(bub_16, 2, 2)[0])
    put(0xD7, _split_tiles(bub_16, 2, 2)[2])

    # 6. Fire Flower ($EB..$EE) -> Z2 Barba/Flame fireball (bank 0 tile $84, 2x to 16x16)
    put_grid([0xEB, 0xEC, 0xED, 0xEE], _make_z2_fireball_item(z2), 2, 2)

    # 7. Starman ($8D, $E4) -> Golden Triforce
    tri_top = [
        '00000001',
        '00000012',
        '00000122',
        '00001232',
        '00012332',
        '00123322',
        '01233222',
        '12222222',
    ]
    tri_bot = [
        '00000001',
        '00000012',
        '00000122',
        '00001232',
        '00012332',
        '00123322',
        '01233222',
        '11111111',
    ]
    # SMB1 Starman mirrors $8D (top) and $E4 (bottom) left+right via H-flip!
    put(0x8D, tri_top)
    put(0xE4, tri_bot)

    # 8. Keep $84/$85 vanilla in World bank R1=16 (brick chunk & bouncing block).
    # Z2 Bomb ($84/$85) is placed in Castle bank R1=18 for Villainous Link.


def _build_castle_bank(buf: bytearray, bank2k: int, z2: bytes, smb_chr0: bytes) -> None:
    """Populate R1=18 (tiles $80..$FF) with Villainous Link, Sword Beam, Bomb, Zelda/Fairy/Toad."""
    buf[bank2k * 1024 : bank2k * 1024 + 2048] = smb_chr0[2048:4096]

    def put(tid: int, rows: list[str]) -> None:
        assert 0x80 <= tid <= 0xFF
        off = bank2k * 1024 + (tid - 0x80) * 16
        buf[off : off + 16] = encode_tile(rows)

    def put_grid(tids: list[int], rows: list[str], cols: int, tile_rows: int) -> None:
        for tid, t in zip(tids, _split_tiles(rows, cols, tile_rows)):
            put(tid, t)

    # 1. Villainous Link (24x24 / 32x24 across two halves, facing LEFT toward Barba!)
    # Z2 Link: bank 0x02 / 0x03:
    #   Stand: [[0x00, 0x02], [0x04, 0x06]] (16x32, shrink_y to 16x24)
    #   Walk:  [[0x00, 0x02], [0x0C, 0x0E]]
    #   Slash: [[0x20, 0x22], [0x24, 0x26]] or [[0x08, 0x0A], [0x0C, 0x0E]]
    # Remember in Z2 bank 0x02, even tiles (00,02,04,06) are in bank 2, odd in bank 3.
    # Let's extract Link from bank 0x02 (even pairs):
    link_stand = _flip_h(_shrink_y(_z2_grid(z2, 0x02, [[0x00, 0x02], [0x04, 0x06]]), 24))
    link_walk  = _flip_h(_shrink_y(_z2_grid(z2, 0x02, [[0x00, 0x02], [0x0C, 0x0E]]), 24))
    # Add villainous dark cape / raised sword in the 16x24 front & back halves!
    # Wait: in SMB1, Bowser front half ($036A=1) is at X, back half ($036A=2) is at X+16 (when facing left).
    # Put Link's front sword + shield + head/torso at $BF..$C4 (front 16x24) and trailing cape/sword-hilt/leg at $C5..$CA (back 16x24),
    # PLUS attack pose ($CB..$D0) when $0363 < 0 (swinging sword / shooting beam)!
    # Better yet: draw full 16x24 Villainous Link in front half ($BF..$C4 walk1, $B0..$B5 walk2, $B6..$BB attack)
    # and a sweeping 16x24 dark cape + floating villain aura / raised sword blade in back/front!
    # Wait: let's build two 16x24 halves (32x24 total):
    #   - Front half: extended Sword Blade (8px wide on left!) + Link front half (8px)
    #   - Back half: Link back half (8px) + flowing dark cape (8px on right!)
    def build_vlink_32x24(body16: list[str], *, sword_up: bool = False) -> tuple[list[str], list[str]]:
        canvas = [['0'] * 32 for _ in range(24)]
        _stamp(canvas, body16, 8, 0)
        # Extended villainous blade attached to Link's front hand (x=0..9)
        if sword_up:
            sword = [
                '000003000',
                '000033000',
                '000331000',
                '003310000',
                '033100000',
                '331000000',
                '012200000',
                '002222000',
            ]
            _stamp(canvas, sword, 1, 4)
        else:
            # Horizontal thrusting blade extending straight from Link's grip
            blade = [
                '0000002000',
                '3333332210',
                '0333332210',
                '0000002000',
            ]
            _stamp(canvas, blade, 0, 12)
        # Flowing dark cape behind Link (x=22..29)
        cape = [
            '11000000',
            '13100000',
            '13310000',
            '11331000',
            '01333100',
            '01133100',
            '00133310',
            '00113310',
            '00013310',
            '00011310',
            '00001110',
            '00000100',
        ]
        _stamp(canvas, cape, 22, 8)
        front = [''.join(r[0:16]) for r in canvas]
        back  = [''.join(r[16:32]) for r in canvas]
        return front, back

    vf1, vb1 = build_vlink_32x24(link_stand, sword_up=False)
    vf2, vb2 = build_vlink_32x24(link_walk, sword_up=False)
    vfa, vba = build_vlink_32x24(link_walk, sword_up=True)
    # Front idle/walk1 ($BF..$C4), Front walk2 ($B0..$B5), Front attack ($B6..$BB)
    put_grid([0xBF, 0xC0, 0xC1, 0xC2, 0xC3, 0xC4], vf1, 2, 3)
    put_grid([0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5], vf2, 2, 3)
    put_grid([0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xBB], vfa, 2, 3)
    # Back idle/walk1 ($C5..$CA), Back walk2 ($90..$95), Back attack ($96..$9B)
    put_grid([0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA], vb1, 2, 3)
    put_grid([0x90, 0x91, 0x92, 0x93, 0x94, 0x95], vb2, 2, 3)
    put_grid([0x96, 0x97, 0x98, 0x99, 0x9A, 0x9B], vba, 2, 3)

    # 2. Link's Horizontal Sword Beam (replaces Bowser Flame $80..$83)
    beam_16 = _z2_pair(z2, 0x02, 0x32)  # 8x16 with beam in rows 10..13
    beam_rows = beam_16[8:16]           # 8x8 horizontal beam
    beam_tail = ['00000000', '00000000', '01122333', '02233333', '01122333', '00000000', '00000000', '00000000']
    beam_tip  = ['00000000', '00010000', '12332100', '33333320', '12332100', '00010000', '00000000', '00000000']
    put(0x80, beam_tip)
    put(0x81, beam_tail)
    put(0x82, _flip_v(beam_tip))
    put(0x83, _flip_v(beam_tail))

    # 3. Lit Bomb (replaces Hammer $84, $85)
    put(0x84, [
        '00002320',
        '00001200',
        '00111100',
        '01221110',
        '12321111',
        '12211111',
        '01111110',
        '00111100',
    ])
    put(0x85, [
        '00032030',
        '00001300',
        '00111100',
        '01221110',
        '12321111',
        '12211111',
        '01111110',
        '00111100',
    ])

    # 4. Caged Zelda ($DA..$DF), Caged Fairy ($CC..$CF + $DC..$DD), Caged Toad (keeps $CD..$CF or overlaid cage!)
    # Z2 Princess Zelda (bank 0x03: 70, 72, 74, 76 -> 16x32 -> shrink_y to 16x24 + iron cage bars)
    zelda_24 = _shrink_y(_z2_grid(z2, 0x03, [[0x70, 0x72], [0x74, 0x76]]), 24)
    # Overlay thin iron cage frame (border + top bar + 2 thin bars)
    def add_cage(rows24: list[str]) -> list[str]:
        c = [list(r) for r in rows24]
        for x in range(16):
            c[0][x] = '1'
            c[23][x] = '1'
        for y in range(24):
            c[y][0] = '1'
            c[y][15] = '1'
            if y in (1, 2, 3, 20, 21, 22):
                c[y][5] = '1'
                c[y][10] = '1'
        return [''.join(r) for r in c]

    put_grid([0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD], add_cage(zelda_24), 2, 3)

    # Caged Fairy (bank 0x00: 0x68, 0x6A -> 8x16 each, centered in 16x24 cage!)
    fairy_a = _z2_pair(z2, 0x00, 0x68)
    fairy_b = _z2_pair(z2, 0x00, 0x6A)
    def fairy_in_cage(f8: list[str]) -> list[str]:
        c = [['0'] * 16 for _ in range(24)]
        _stamp(c, resize_x(f8, 12), 2, 4)
        return add_cage([''.join(r) for r in c])

    put_grid([0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5], fairy_in_cage(fairy_a), 2, 3)
    put_grid([0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xAB], fairy_in_cage(fairy_b), 2, 3)

    # Caged Toad ($CC..$CF + $AE..$AF: wrap SMB1's Toad $CD,$CE,$CF in cage!)
    toad_top = list(''.join(str(v) for v in r) for r in decode_tile(smb_chr0[2048 + (0xCD - 0x80) * 16 : 2048 + (0xCE - 0x80) * 16]))
    toad_mid = list(''.join(str(v) for v in r) for r in decode_tile(smb_chr0[2048 + (0xCE - 0x80) * 16 : 2048 + (0xCF - 0x80) * 16]))
    toad_bot = list(''.join(str(v) for v in r) for r in decode_tile(smb_chr0[2048 + (0xCF - 0x80) * 16 : 2048 + (0xD0 - 0x80) * 16]))
    toad_24 = [r + r[::-1] for r in (toad_top + toad_mid + toad_bot)]
    put_grid([0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5], add_cage(toad_24), 2, 3)

    # Also keep $D0/$D7 Bubble (Podoboo in castle!)
    bub_half = _z2_pair(z2, 0x14, 0xDC)
    bub_16 = [r + r[::-1] for r in bub_half]
    put(0xD0, _split_tiles(bub_16, 2, 2)[0])
    put(0xD7, _split_tiles(bub_16, 2, 2)[2])

    # 5. Fire item ($EB..$EE) -> Z2 Barba/Flame fireball (same slots as world bank)
    put_grid([0xEB, 0xEC, 0xED, 0xEE], _make_z2_fireball_item(z2), 2, 2)


def _build_bg_banks(buf: bytearray, smb_chr1: bytes) -> None:
    """Populate 1KB BG banks 4..11 (R2/R3/R4/R5 + Palace Crystal & Triforce variants)."""
    # Base 4KB ($1000-$1FFF) in banks 4, 5, 6, 7
    buf[CHR_R2_WORLD_A * 1024 : (CHR_R5_BG + 1) * 1024] = smb_chr1[:4096]

    # Palace Crystal Flagpole top ($2F) and Crystal pillar ($3D) in R2=4 and R2=8
    crystal_a = [
        '00033000',
        '00322300',
        '03233230',
        '32333323',
        '32322323',
        '03233230',
        '00322300',
        '00033000',
    ]
    crystal_b = [
        '00022000',
        '00233200',
        '02311320',
        '23133132',
        '23111132',
        '02311320',
        '00233200',
        '00022000',
    ]
    pillar = [
        '00023000',
        '00032000',
        '00023000',
        '00032000',
        '00023000',
        '00032000',
        '00023000',
        '00032000',
    ]
    _put_tile(buf, CHR_R2_WORLD_A, 0x2F, crystal_a)
    _put_tile(buf, CHR_R2_WORLD_A, 0x3D, pillar)
    buf[CHR_R2_WORLD_B * 1024 : CHR_R2_WORLD_B * 1024 + 1024] = buf[CHR_R2_WORLD_A * 1024 : CHR_R2_WORLD_A * 1024 + 1024]
    _put_tile(buf, CHR_R2_WORLD_B, 0x2F, crystal_b)

    # Copy R3=5 -> R3=9, 10, 11
    r3_base = buf[CHR_R3_WORLD * 1024 : CHR_R3_WORLD * 1024 + 1024]
    for b in (CHR_R3_WORLD_B, CHR_R3_CASTLE_A, CHR_R3_CASTLE_B):
        buf[b * 1024 : b * 1024 + 1024] = r3_base

    # Castle Axe ($7B, $7C, $7D, $7E -> tiles $3B..$3E in R3) -> Golden Triforce!
    # SMB1 metatile $8CA0: top-left=$7B, bot-left=$7D, top-right=$7C, bot-right=$7E
    tri_16_a = [
        '0000000330000000',
        '0000003223000000',
        '0000032332300000',
        '0000323223230000',
        '0003232222323000',
        '0032322222232300',
        '0323222222223230',
        '3233333333333323',
        '0003300000033000',
        '0032230000322300',
        '0323323003233230',
        '3232232332322323',
        '3222222332222223',
        '3222222332222223',
        '3333333333333333',
        '0000000000000000',
    ]
    tri_16_b = [
        '0000000220000000',
        '0000002332000000',
        '0000023113200000',
        '0000231331320000',
        '0002313333132000',
        '0023133333313200',
        '0231333333331320',
        '2322222222222232',
        '0002200000022000',
        '0023320000233200',
        '0231132002311320',
        '2313313223133132',
        '2333333223333332',
        '2333333223333332',
        '2222222222222222',
        '0000000000000000',
    ]
    ta = _split_tiles(tri_16_a, 2, 2)
    tb = _split_tiles(tri_16_b, 2, 2)
    for b, tset in ((CHR_R3_WORLD, ta), (CHR_R3_CASTLE_A, ta), (CHR_R3_CASTLE_B, tb)):
        _put_tile(buf, b, 0x7B - 0x40, tset[0])
        _put_tile(buf, b, 0x7C - 0x40, tset[1])
        _put_tile(buf, b, 0x7D - 0x40, tset[2])
        _put_tile(buf, b, 0x7E - 0x40, tset[3])


def build_smb_barba_chr(smb_bytes: bytes, z2_bytes: bytes) -> bytes:
    """Compile the full 32 KB multi-bank MMC3 CHR ROM for Super Barba Bros."""
    smb_chr = smb_bytes[16 + 32768 : 16 + 32768 + 8192]
    smb_chr0 = smb_chr[:4096]
    smb_chr1 = smb_chr[4096:]

    buf = bytearray(b'\x00' * SMB_CHR_SIZE)
    shared_r0 = _shared_r0_tiles(z2_bytes)

    # Seed R0 sprite banks with SMB1 base $00..$7F first so any untouched fallback tile stays valid
    for r0_bank in (CHR_R0_WYRMLING, CHR_R0_BARBA, CHR_R0_INFERNO, CHR_R0_ROAR, CHR_R0_WYRMLING_ROAR):
        buf[r0_bank * 1024 : r0_bank * 1024 + 2048] = smb_chr0[:2048]

    _write_wyrmling_bank(buf, CHR_R0_WYRMLING, z2_bytes, shared_r0, roaring=False)
    _write_wyrmling_bank(buf, CHR_R0_WYRMLING_ROAR, z2_bytes, shared_r0, roaring=True)
    _write_barba_bank(buf, CHR_R0_BARBA, z2_bytes, shared_r0, inferno=False, roaring=False)
    _write_barba_bank(buf, CHR_R0_INFERNO, z2_bytes, shared_r0, inferno=True, roaring=False)
    _write_barba_bank(buf, CHR_R0_ROAR, z2_bytes, shared_r0, inferno=True, roaring=True)

    _build_enemies_bank(buf, CHR_R1_ENEMIES, z2_bytes, smb_chr0)
    _build_castle_bank(buf, CHR_R1_CASTLE, z2_bytes, smb_chr0)
    _build_bg_banks(buf, smb_chr1)

    return bytes(buf)


def render_chr_preview(chr_bytes: bytes, out_path: Path) -> Path:
    """Render key 2KB sprite & 1KB BG banks into a single contact sheet PNG for visual audit."""
    colors = [(20, 22, 28), (194, 43, 25), (255, 168, 57), (255, 243, 205)]
    banks = [
        CHR_R0_WYRMLING,
        CHR_R0_BARBA,
        CHR_R0_INFERNO,
        CHR_R0_ROAR,
        CHR_R1_ENEMIES,
        CHR_R1_CASTLE,
    ]
    # Each 2KB bank = 128 tiles (8 rows x 16 cols)
    row_h = 8 * 9 + 4
    w = 16 * 9
    h = len(banks) * row_h
    pixels = [[(45, 48, 58)] * w for _ in range(h)]
    for b_idx, bank2k in enumerate(banks):
        y_base = b_idx * row_h
        for tid in range(128):
            off = bank2k * 1024 + tid * 16
            tile = decode_tile(chr_bytes[off : off + 16])
            tx, ty = tid % 16, tid // 16
            for y, row in enumerate(tile):
                for x, v in enumerate(row):
                    pixels[y_base + ty * 9 + y][tx * 9 + x] = colors[v]
    write_png(out_path, pixels, 3)
    return out_path


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    smb = (root / 'roms/smb.nes').read_bytes()
    z2 = (root / 'roms/z2.nes').read_bytes()
    chr_data = build_smb_barba_chr(smb, z2)
    out = render_chr_preview(chr_data, root / 'build/subgames/smb_art_preview.png')
    print(f'Rendered {out} ({len(chr_data)} bytes)')
