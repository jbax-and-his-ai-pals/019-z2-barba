"""6502 code and PPU stream assembly for Villager Hunt (Duck Hunt MMC3 upgrade)."""
from __future__ import annotations

from pack_f13 import Asm6502


# Unused internal RAM ($0620-$063F, cleared at boot by $C000)
VH_CURSOR_X     = 0x0620
VH_CURSOR_Y     = 0x0621
VH_PREV_PAD1    = 0x0622
VH_SHOT_MODE    = 0x0623
VH_FIRE_TIMER   = 0x0624
VH_FIRE_X       = 0x0625
VH_FIRE_Y       = 0x0626
VH_TARGET_KIND0 = 0x0627
VH_TARGET_KIND1 = 0x0628
VH_ROAR_TIMER   = 0x0629
VH_MMC3_MODE    = 0x062A  # $00 normal, $40 while roar DMC plays in $C000-$DFFF (bank 29)
VH_CUR_R0       = 0x062B
VH_CUR_R1       = 0x062C
VH_CUR_BG       = 0x062D
VH_TMP0         = 0x062E
VH_TMP1         = 0x062F
VH_TMP2         = 0x0630
VH_TMP3         = 0x0631
VH_TMP4         = 0x0632
VH_TMP5         = 0x0633
VH_CLAY_SEQ     = 0x0634
VH_SHAKE_TIMER  = 0x0635
VH_SCENE_IDX    = 0x0636  # 0=Forest, 1=Overworld Grass, 2=Desert (cycles per Game A/B round)

# Unused Zero Page ($96-$97, $CC-$CE — never referenced by Duck Hunt game or sound code)
ZP_PTR0 = 0xCC  # $CC/$CD
ZP_PTR1 = 0x96  # $96/$97
ZP_SCR  = 0xCE

# Bank 1 entry base ($A000-$BFFF via R7 = 1)
BANK1_BASE = 0xA000

# Fixed Bank 31 pad ($EF5A-$F2FF)
FIXED_PAD_BASE = 0xEF5A

# Roar DMC location in Bank 29 ($D700-$DF81)
ROAR_DMC_ADDR     = 0xD700
ROAR_DMC_ADDR_REG = (ROAR_DMC_ADDR - 0xC000) // 64  # $5C


class DuckAsm(Asm6502):
    """Asm6502 extended with offset absolute/word fixups."""

    def abs_ref_off(self, op: int, target: str, offset: int = 0) -> None:
        self.emit(op, 0, 0)
        self.fixups.append(('abs_off', len(self.buf) - 2, (target, offset)))

    def word_ref(self, target: str) -> None:
        self.emit(0, 0)
        self.fixups.append(('abs', len(self.buf) - 2, target))

    def finish(self) -> bytes:
        for kind, pos, target in self.fixups:
            if kind == 'abs_off':
                tname, off = target
                addr = self.labels[tname] + off
                self.buf[pos] = addr & 0xFF
                self.buf[pos + 1] = (addr >> 8) & 0xFF
            elif kind == 'rel':
                addr = self.labels[target]
                rel = addr - (self.base + pos + 1)
                assert -128 <= rel <= 127, f'Branch out of range to {target}: {rel}'
                self.buf[pos] = rel & 0xFF
            elif kind == 'lo':
                addr = self.labels[target]
                self.buf[pos] = addr & 0xFF
            elif kind == 'hi':
                addr = self.labels[target]
                self.buf[pos] = (addr >> 8) & 0xFF
            else:
                addr = self.labels[target]
                self.buf[pos] = addr & 0xFF
                self.buf[pos + 1] = (addr >> 8) & 0xFF
        return bytes(self.buf)


def _encode_title_str(s: str) -> list[int]:
    out: list[int] = []
    for ch in s:
        if '0' <= ch <= '9':
            out.append(ord(ch) - ord('0'))
        elif 'A' <= ch <= 'Z':
            out.append(10 + ord(ch) - ord('A'))
        elif ch == ' ':
            out.append(0x24)
        elif ch == '=':
            out.append(0x27)
        else:
            out.append(0x24)
    return out


def build_title_ppu_stream() -> bytes:
    """Build PPU nametable stream ($2000) for "BARBA'S HUNT" title screen."""
    buf = bytearray()

    def write_row(ppu_addr: int, tiles: list[int]) -> None:
        buf.append((ppu_addr >> 8) & 0xFF)
        buf.append(ppu_addr & 0xFF)
        buf.append(len(tiles))
        buf.extend(tiles)

    def repeat_row(ppu_addr: int, count: int, tile: int, vert: bool = False) -> None:
        buf.append((ppu_addr >> 8) & 0xFF)
        buf.append(ppu_addr & 0xFF)
        buf.append((0x80 if vert else 0x00) | 0x40 | count)
        buf.append(tile)

    # Rounded 5-row Duck Hunt logo tiles for "BARBA'S" at rows 3..7, cols 4..27 (24 cols)
    # Uses vanilla $B7 (solid), $F0-$F3 (outer curves), plus custom $C0-$CD in title_bg.
    _ = 0x24
    B = [
        [0xB7, 0xB7, 0xF0],
        [0xB7, 0xC2, 0xC3],
        [0xB7, 0xB7, 0xC4],
        [0xB7, 0xC2, 0xC5],
        [0xB7, 0xB7, 0xF1],
    ]
    A = [
        [0xF2, 0xB7, 0xF0],
        [0xB7, 0xC1, 0xB7],
        [0xB7, 0xB7, 0xB7],
        [0xB7, 0xC0, 0xB7],
        [0xB7, 0xC0, 0xB7],
    ]
    R = [
        [0xB7, 0xB7, 0xF0],
        [0xB7, 0xC2, 0xC3],
        [0xB7, 0xB7, 0xC4],
        [0xB7, 0xC0, 0xC5],
        [0xB7, 0xC0, 0xB7],
    ]
    APOS = [
        [0xC6, 0xC7],
        [0xC8, 0xC9],
        [_, _],
        [_, _],
        [_, _],
    ]
    S = [
        [0xF2, 0xB7, 0xF0],
        [0xB7, 0xCA, 0xCB],
        [0xF3, 0xB7, 0xF0],
        [0xCC, 0xCD, 0xB7],
        [0xF3, 0xB7, 0xF1],
    ]
    barbas_parts = [B, [_], A, [_], R, [_], B, [_], A, APOS, S]
    for r in range(5):
        row_tiles: list[int] = []
        for part in barbas_parts:
            if part == [_]:
                row_tiles.append(_)
            else:
                row_tiles.extend(part[r])
        write_row(0x2000 + (3 + r) * 32 + 4, row_tiles)

    # Vanilla orange divider bar on row 9, cols 4..27 (24 cols)
    repeat_row(0x2124, 24, 0xFB)

    # Vanilla "HUNT" at rows 10..14, cols 9..27 (19 cols, right-aligned with divider bar)
    hunt_rows = [
        [0xB7, 0xB7, _,    0xB7, _, 0xB7, 0xB7, _,    0xB7, _, 0xB7, 0xB7, _,    0xB7, _, 0xB7, 0xB7, 0xB7, 0xB7],
        [0xB7, 0xB7, 0xFA, 0xB7, _, 0xB7, 0xB7, _,    0xB7, _, 0xB7, 0xB7, 0xF0, 0xB7, _, _,    0xB7, 0xB7, _   ],
        [0xB7, 0xB7, 0xB7, 0xB7, _, 0xB7, 0xB7, 0xF4, 0xB7, _, 0xB7, 0xB7, 0xB7, 0xB7, _, _,    0xB7, 0xB7, _   ],
        [0xB7, 0xB7, _,    0xB7, _, 0xB7, 0xB7, 0xB7, 0xB7, _, 0xB7, 0xB7, 0xF9, 0xB7, _, _,    0xB7, 0xB7, _   ],
        [0xB7, 0xB7, _,    0xB7, _, 0xF3, 0xB7, 0xB7, 0xF1, _, 0xB7, 0xB7, _,    0xB7, _, _,    0xB7, 0xB7, _   ],
    ]
    for r, row_tiles in enumerate(hunt_rows):
        write_row(0x2000 + (10 + r) * 32 + 9, row_tiles)

    # Menu options at exact Duck Hunt cursor rows ($2228, $2268, $22A8)
    write_row(0x2228, _encode_title_str('GAME A   1 MONSTER'))
    write_row(0x2268, _encode_title_str('GAME B   2 MONSTERS'))
    write_row(0x22A8, _encode_title_str('GAME C   OCTOROKS MOAS'))
    write_row(0x2307, _encode_title_str('TOP SCORE ='))
    write_row(0x2345, _encode_title_str('DPAD AIM   A B FIREBALL'))

    # Attribute colors (matching vanilla Duck Hunt):
    # $23C0..$23DF (rows 0-15): BARBA'S, divider bar, HUNT -> Pal 0 ($00: cyan + orange bar)
    # $23E0..$23E1, $23E8..$23E9: cursor col 6 -> Pal 1 ($55: white)
    # $23E2..$23E7, $23EA..$23EF: GAME A/B/C -> Pal 3 ($FF: orange)
    # $23F0..$23F7: TOP SCORE = 12000 (top half) Pal 2 green + DPAD AIM... (bottom half) Pal 1 white ($5A)
    # $23F8..$23FF: bottom border -> Pal 0 ($00)
    repeat_row(0x23C0, 32, 0x00)
    repeat_row(0x23E0, 2, 0x55)
    repeat_row(0x23E2, 6, 0xFF)
    repeat_row(0x23E8, 2, 0x55)
    repeat_row(0x23EA, 6, 0xFF)
    repeat_row(0x23F0, 8, 0x5A)
    repeat_row(0x23F8, 8, 0x00)
    buf.append(0x00)
    return bytes(buf)


def _build_encounter_ppu_stream(
    sky_fn,
    ground_r20: list[int],
    ground_r21: list[int],
    attrs: list[int],
    *,
    horizon_r18: list[int] | None = None,
    horizon_r19: list[int] | None = None,
) -> bytes:
    """Build PPU nametable stream ($2000) for a Game A/B Z2 encounter scene."""
    buf = bytearray()

    def write_row(ppu_addr: int, tiles: list[int]) -> None:
        buf.append((ppu_addr >> 8) & 0xFF)
        buf.append(ppu_addr & 0xFF)
        buf.append(len(tiles))
        buf.extend(tiles)

    def repeat_row(ppu_addr: int, count: int, tile: int, vert: bool = False) -> None:
        buf.append((ppu_addr >> 8) & 0xFF)
        buf.append(ppu_addr & 0xFF)
        buf.append((0x80 if vert else 0x00) | 0x40 | count)
        buf.append(tile)

    # Clear sky ($2000..$22FF = rows 0..23) to $24 (blank space)
    for r in range(24):
        repeat_row(0x2000 + r * 32, 32, 0x24)

    # Horizon/bushes (rows 18..19) for OAM $20 behind-bush masking
    if horizon_r18 is None:
        repeat_row(0x2240, 32, 0x6E)
    else:
        write_row(0x2240, horizon_r18)
    if horizon_r19 is None:
        repeat_row(0x2260, 32, 0x6F)
    else:
        write_row(0x2260, horizon_r19)

    sky_fn(write_row)

    # Ground (rows 20..21)
    write_row(0x2280, ground_r20)
    write_row(0x22A0, ground_r21)

    # Dirt & HUD (rows 22..29) matching Duck Hunt $E042 layout
    dirt_r22 = [0x50, 0x51, 0x50, 0x52] * 8
    write_row(0x22C0, dirt_r22)
    dirt_r23 = [
        0x52, 0x50, 0x53, 0x50, 0x50, 0x51, 0x50, 0x50,
        0x52, 0x50, 0x53, 0x50, 0x50, 0x53, 0x50, 0x50,
        0x51, 0x50, 0x50, 0x52, 0x50, 0x53, 0x50, 0x50,
        0x50, 0x51, 0x50, 0x50, 0x52, 0x50, 0x53, 0x50,
    ]
    write_row(0x22E0, dirt_r23)
    write_row(0x2300, [
        0x52, 0x50, 0x54, 0x1B, 0x27, 0x50, 0x50, 0x50,
        0x50, 0x50, 0x54, 0x52, 0x50, 0x54, 0x52, 0x54,
        0x52, 0x50, 0x50, 0x50, 0x50, 0x54, 0x52, 0x50,
        0x50, 0x50, 0x50, 0x50, 0x50, 0x50, 0x54, 0x52,
    ])
    write_row(0x2320, [
        0x50, 0x50, 0xE2, 0xE3, 0xE3, 0xE3, 0xE4, 0xE2,
        0xE3, 0xE3, 0xE3, 0xE3, 0xE3, 0xE3, 0xE3, 0xE3,
        0xE3, 0xE3, 0xE3, 0xE3, 0xE3, 0xE3, 0xE4, 0xE2,
        0xE3, 0xE3, 0xE3, 0xE3, 0xE3, 0xE3, 0xE4, 0x50,
    ])
    write_row(0x2340, [
        0x50, 0x50, 0xE5, 0xD9, 0xD9, 0xD9, 0xE7, 0xE5,
        0x11, 0x12, 0x1D, 0xB7, 0xD6, 0xD6, 0xD6, 0xD6,
        0xD6, 0xD6, 0xD6, 0xD6, 0xD6, 0xD6, 0xE7, 0xE5,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xE7, 0x50,
    ])
    write_row(0x2360, [
        0x50, 0x50, 0xE5, 0xDA, 0xDB, 0xDC, 0xE7, 0xE5,
        0xB7, 0xB7, 0xB7, 0xB7, 0xB7, 0xB7, 0xB7, 0xB7,
        0xB7, 0xB7, 0xB7, 0xB7, 0xB7, 0xB7, 0xE7, 0xE5,
        0xB7, 0x1C, 0x0C, 0x18, 0x1B, 0x0E, 0xE7, 0x50,
    ])
    write_row(0x2380, [
        0x50, 0x50, 0xE8, 0xE9, 0xE9, 0xE9, 0xEA, 0xE8,
        0xE9, 0xE9, 0xE9, 0xE9, 0xE9, 0xE9, 0xE9, 0xE9,
        0xE9, 0xE9, 0xE9, 0xE9, 0xE9, 0xE9, 0xEA, 0xE8,
        0xE9, 0xE9, 0xE9, 0xE9, 0xE9, 0xE9, 0xEA, 0x50,
    ])
    repeat_row(0x23A0, 32, 0x50)

    # Split into two 32-byte writes (count=64 would set bit 6 RLE in $C617!)
    write_row(0x23C0, attrs[:32])
    write_row(0x23E0, attrs[32:])
    buf.append(0x00)
    return bytes(buf)


def build_forest_ppu_stream() -> bytes:
    """Build PPU nametable stream ($2000) for Zelda II Forest Encounter (Game A/B)."""
    def sky(write_row):
        # Canopy (rows 0..5): Z2 forest leaves ($68/$6A top, $69/$6B solid, $6C/$6D hanging)
        write_row(0x2000, [0x68, 0x6A] * 16)
        write_row(0x2020, [0x69, 0x6B] * 16)
        write_row(0x2040, [0x68, 0x6A] * 16)
        write_row(0x2060, [0x69, 0x6B] * 5 + [0x6C, 0x6D] * 6 + [0x69, 0x6B] * 5)
        # Side canopy overhangs on rows 4..5 (leaving cols 10..21 open for ROUND/FLY AWAY box)
        write_row(0x2080, [0x68, 0x6A] * 3)
        write_row(0x20A0, [0x6C, 0x6D] * 3)
        write_row(0x209A, [0x68, 0x6A] * 3)
        write_row(0x20BA, [0x6C, 0x6D] * 3)
        # Two tree trunks (cols 6..7 and cols 24..25, rows 4..17)
        for r in range(4, 18):
            tl, tr = (0x60, 0x62) if (r & 1) == 0 else (0x61, 0x63)
            write_row(0x2000 + r * 32 + 6, [tl, tr])
            write_row(0x2000 + r * 32 + 24, [tl, tr])

    attrs = [
        0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55,  # rows 0..3: canopy
        0x55, 0x11, 0x00, 0xF0, 0xF0, 0xF0, 0x44, 0x55,  # rows 4..7: overhangs, trunks, popup
        0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x00, 0x00,  # rows 8..11: trunks, popup
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # rows 12..15: trunks
        0x50, 0x50, 0x50, 0x50, 0x50, 0x50, 0x50, 0x50,  # rows 16..19: trunks top, bushes bottom
        0xA5, 0xA5, 0xA5, 0xA5, 0xA5, 0xA5, 0xA5, 0xA5,  # rows 20..23: ground top, dirt bottom
        0xAA, 0xAA, 0xAA, 0xFA, 0xFA, 0xBA, 0xFA, 0xBA,  # rows 24..27: HUD
        0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A,  # rows 28..29: HUD bottom
    ]
    return _build_encounter_ppu_stream(sky, [0x64, 0x66] * 16, [0x65, 0x67] * 16, attrs)


def build_grass_ppu_stream() -> bytes:
    """Build PPU nametable stream ($2000) for Zelda II Overworld Grass Encounter."""
    def sky(write_row):
        # Z2 clouds ($60/$61/$62 top, $63/$6A/$6B bottom): short cloud left, long cloud right
        write_row(0x2000 + 3 * 32 + 4, [0x60, 0x62])
        write_row(0x2000 + 4 * 32 + 4, [0x63, 0x6B])
        write_row(0x2000 + 2 * 32 + 23, [0x60, 0x61, 0x62])
        write_row(0x2000 + 3 * 32 + 23, [0x63, 0x6A, 0x6B])
        # Tall grass sprigs ($68 top, $69 bottom) on rows 16..17 above the bushes
        write_row(0x2000 + 16 * 32 + 1, [0x68] * 8)
        write_row(0x2000 + 17 * 32 + 1, [0x69] * 8)
        write_row(0x2000 + 16 * 32 + 24, [0x68, 0x68])
        write_row(0x2000 + 17 * 32 + 24, [0x69, 0x69])
        write_row(0x2000 + 16 * 32 + 30, [0x68, 0x68])
        write_row(0x2000 + 17 * 32 + 30, [0x69, 0x69])

    attrs = [
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # rows 0..3: sky & clouds (Pal 0)
        0x00, 0x00, 0x00, 0xF0, 0xF0, 0xF0, 0x00, 0x00,  # rows 4..7: sky & popup
        0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x00, 0x00,  # rows 8..11: sky & popup
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # rows 12..15: sky
        0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55,  # rows 16..19: sprigs & bushes (Pal 1)
        0xA5, 0xA5, 0xA5, 0xA5, 0xA5, 0xA5, 0xA5, 0xA5,  # rows 20..23: grass top (Pal 1), dirt bottom (Pal 2)
        0xAA, 0xAA, 0xAA, 0xFA, 0xFA, 0xBA, 0xFA, 0xBA,  # rows 24..27: HUD
        0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A,  # rows 28..29: HUD bottom
    ]
    return _build_encounter_ppu_stream(sky, [0x64, 0x66] * 16, [0x65, 0x67] * 16, attrs)


def build_desert_ppu_stream() -> bytes:
    """Build PPU nametable stream ($2000) for Zelda II Desert Encounter."""
    def sky(write_row):
        # Z2 clouds ($60/$61/$62 top, $63/$6A/$6B bottom): long cloud left, short cloud right
        write_row(0x2000 + 2 * 32 + 3, [0x60, 0x61, 0x62])
        write_row(0x2000 + 3 * 32 + 3, [0x63, 0x6A, 0x6B])
        write_row(0x2000 + 4 * 32 + 25, [0x60, 0x62])
        write_row(0x2000 + 5 * 32 + 25, [0x63, 0x6B])
        # Armed cactus at cols 4..5 (rows 16..19)
        write_row(0x2000 + 16 * 32 + 4, [0x68])
        write_row(0x2000 + 17 * 32 + 4, [0x69, 0x6C])
        write_row(0x2000 + 18 * 32 + 4, [0x69, 0x6D])
        write_row(0x2000 + 19 * 32 + 4, [0x69])
        # Tall cactus at col 26 (rows 17..19)
        for r, tid in ((17, 0x68), (18, 0x69), (19, 0x69)):
            write_row(0x2000 + r * 32 + 26, [tid])

    attrs = [
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # rows 0..3: open desert sky & clouds (Pal 0)
        0x00, 0x00, 0x00, 0xF0, 0xF0, 0xF0, 0x00, 0x00,  # rows 4..7: sky & popup
        0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x00, 0x00,  # rows 8..11: sky & popup
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # rows 12..15: sky
        0x00, 0x11, 0x00, 0x00, 0x00, 0x00, 0x44, 0x00,  # rows 16..19: cacti (Pal 1) & sand bumps (Pal 0)
        0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0,  # rows 20..23: sand top (Pal 0), dirt bottom (Pal 2)
        0xAA, 0xAA, 0xAA, 0xFA, 0xFA, 0xBA, 0xFA, 0xBA,  # rows 24..27: HUD
        0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A,  # rows 28..29: HUD bottom
    ]
    horizon_r19 = [0x24, 0x6F] * 16
    horizon_r19[5] = 0x24   # keep Pal 1 cactus block free of Pal 0 sand bumps
    horizon_r19[27] = 0x24
    return _build_encounter_ppu_stream(
        sky,
        [0x64, 0x66] * 16,
        [0x65, 0x67] * 16,
        attrs,
        horizon_r18=[0x24] * 32,
        horizon_r19=horizon_r19,
    )


def assemble_fixed_pad() -> tuple[bytes, dict[str, int]]:
    """Assemble tiny fixed-bank ($EF5A) DMC/4011 audio guards."""
    a = DuckAsm(FIXED_PAD_BASE)

    # vh_dmc_guard: replaces $F591 (A5 F2 4A B0 0C -> JMP vh_dmc_guard)
    a.label('vh_dmc_guard')
    a.emit(0xAD, VH_ROAR_TIMER & 0xFF, VH_ROAR_TIMER >> 8)   # LDA VH_ROAR_TIMER
    a.branch(0xF0, 'dmc_ok')                                 # BEQ dmc_ok
    a.emit(0x60)                                             # RTS (skip native bark/quack while Barba roars)
    a.label('dmc_ok')
    a.emit(0xA5, 0xF2, 0x4A)                                 # LDA $F2; LSR A
    a.emit(0x4C, 0x94, 0xF5)                                 # JMP $F594

    # vh_4011_guard: replaces $F68F (8D 11 40 -> JSR vh_4011_guard)
    a.label('vh_4011_guard')
    a.emit(0x48)                                             # PHA
    a.emit(0xAD, VH_ROAR_TIMER & 0xFF, VH_ROAR_TIMER >> 8)   # LDA VH_ROAR_TIMER
    a.branch(0xD0, 'skip_4011')                              # BNE skip_4011
    a.emit(0x68, 0x8D, 0x11, 0x40, 0x60)                     # PLA; STA $4011; RTS
    a.label('skip_4011')
    a.emit(0x68, 0x60)                                       # PLA; RTS

    code = a.finish()
    assert len(code) <= 0x3A6, f'Fixed pad overflow: {len(code)}'
    return code, dict(a.labels)


def assemble_bank1(art: dict, roar_info: dict, *, is_pal: bool = False) -> tuple[bytes, dict[str, int]]:
    """Assemble Bank 1 ($A000-$BFFF, mapped via R7 = 1) code and sprite tables."""
    a = DuckAsm(BANK1_BASE)

    roar_rate = int(roar_info['rate_index']) & 0x0F
    roar_len_reg = (int(roar_info['bytes']) - 1) // 16
    roar_timer_frames = min(250, int(roar_info['timer_frames']))

    # ------------------------------------------------------------------
    # 1. MMC3 CHR & Roar DMC Helpers
    # ------------------------------------------------------------------
    a.label('vh_set_r0')
    a.emit(0xCD, VH_CUR_R0 & 0xFF, VH_CUR_R0 >> 8)
    a.branch(0xF0, 'r0_done')
    a.emit(0x8D, VH_CUR_R0 & 0xFF, VH_CUR_R0 >> 8)
    a.emit(0x48)
    a.emit(0xAD, VH_MMC3_MODE & 0xFF, VH_MMC3_MODE >> 8)
    a.emit(0x8D, 0x00, 0x80)                                 # R0 | mode
    a.emit(0x68, 0x8D, 0x01, 0x80)
    a.label('r0_done')
    a.emit(0x60)

    a.label('vh_set_r1')
    a.emit(0xCD, VH_CUR_R1 & 0xFF, VH_CUR_R1 >> 8)
    a.branch(0xF0, 'r1_done')
    a.emit(0x8D, VH_CUR_R1 & 0xFF, VH_CUR_R1 >> 8)
    a.emit(0x48)
    a.emit(0xA9, 0x01, 0x0D, VH_MMC3_MODE & 0xFF, VH_MMC3_MODE >> 8)
    a.emit(0x8D, 0x00, 0x80)                                 # R1 | mode
    a.emit(0x68, 0x8D, 0x01, 0x80)
    a.label('r1_done')
    a.emit(0x60)

    # A = 0 (game BG) or 4 (title BG)
    a.label('vh_set_bg')
    a.emit(0xCD, VH_CUR_BG & 0xFF, VH_CUR_BG >> 8)
    a.branch(0xF0, 'bg_done')
    a.emit(0x8D, VH_CUR_BG & 0xFF, VH_CUR_BG >> 8)
    a.emit(0xAA)                                             # X = base (0 or 4)
    for reg in (2, 3, 4, 5):
        a.emit(0xA9, reg, 0x0D, VH_MMC3_MODE & 0xFF, VH_MMC3_MODE >> 8)
        a.emit(0x8D, 0x00, 0x80)
        a.emit(0x8E, 0x01, 0x80)
        if reg < 5:
            a.emit(0xE8)
    a.label('bg_done')
    a.emit(0x60)

    a.label('vh_play_roar')
    a.emit(0x48, 0x8A, 0x48)                                 # PHA; TXA; PHA
    a.emit(0xA9, 0x0F, 0x8D, 0x15, 0x40)                     # stop prior DMC
    a.emit(0xA9, 0x40, 0x8D, VH_MMC3_MODE & 0xFF, VH_MMC3_MODE >> 8)
    a.emit(0xA9, 0x46, 0x8D, 0x00, 0x80)                     # R6 at $C000-$DFFF
    a.emit(0xA9, 29, 0x8D, 0x01, 0x80)                       # Bank 29 (roar.dmc at $D700)
    a.emit(0xA9, roar_rate, 0x8D, 0x10, 0x40)
    a.emit(0xA9, 0x40, 0x8D, 0x11, 0x40)
    a.emit(0xA9, ROAR_DMC_ADDR_REG, 0x8D, 0x12, 0x40)
    a.emit(0xA9, roar_len_reg, 0x8D, 0x13, 0x40)
    a.emit(0xA9, 0x1F, 0x8D, 0x15, 0x40)
    a.emit(0xA9, roar_timer_frames, 0x8D, VH_ROAR_TIMER & 0xFF, VH_ROAR_TIMER >> 8)
    a.emit(0x68, 0xAA, 0x68, 0x60)                           # PLA; TAX; PLA; RTS

    a.label('vh_stop_roar')
    a.emit(0xA9, 0x00)
    a.emit(0x8D, VH_ROAR_TIMER & 0xFF, VH_ROAR_TIMER >> 8)
    a.emit(0x8D, VH_SHAKE_TIMER & 0xFF, VH_SHAKE_TIMER >> 8)
    a.emit(0x85, 0x0B)                                       # clear Y scroll shake
    a.emit(0x8D, VH_MMC3_MODE & 0xFF, VH_MMC3_MODE >> 8)
    a.emit(0xA9, 0x0F, 0x8D, 0x15, 0x40)
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80)                     # Normal PRG mode ($8000=R6)
    a.emit(0xA9, 0x02, 0x8D, 0x01, 0x80)                     # R6 = Bank 2
    a.emit(0x60)

    # ------------------------------------------------------------------
    # 2. Setup / Spawn / Roar Trigger Hooks
    # ------------------------------------------------------------------
    a.label('vh_init_cursor')
    a.emit(0xA9, 120, 0x8D, VH_CURSOR_X & 0xFF, VH_CURSOR_X >> 8)
    a.emit(0xA9, 96, 0x8D, VH_CURSOR_Y & 0xFF, VH_CURSOR_Y >> 8)
    a.emit(0xA9, 0x00)
    a.emit(0x8D, VH_FIRE_TIMER & 0xFF, VH_FIRE_TIMER >> 8)
    a.emit(0x8D, VH_SHOT_MODE & 0xFF, VH_SHOT_MODE >> 8)
    a.emit(0x60)

    # Replaces $C5C4 (LDX #$04; LDY #$E4; JSR $C617)
    a.label('vh_setup_title_screen')
    a.emit(0xA9, 0xFF)
    a.emit(0x8D, VH_CUR_R0 & 0xFF, VH_CUR_R0 >> 8)
    a.emit(0x8D, VH_CUR_R1 & 0xFF, VH_CUR_R1 >> 8)
    a.emit(0x8D, VH_CUR_BG & 0xFF, VH_CUR_BG >> 8)
    a.emit(0x8D, VH_SCENE_IDX & 0xFF, VH_SCENE_IDX >> 8)
    a.abs_ref(0x20, 'vh_init_cursor')
    a.emit(0xA9, 4); a.abs_ref(0x20, 'vh_set_bg')
    a.emit(0xA9, 12); a.abs_ref(0x20, 'vh_set_r0')
    a.emit(0xA9, 14); a.abs_ref(0x20, 'vh_set_r1')
    a.lda_lo('title_ppu_stream'); a.emit(0xAA)               # LDX #<title_ppu_stream
    a.lda_hi('title_ppu_stream'); a.emit(0xA8)               # LDY #>title_ppu_stream
    a.emit(0x4C, 0x17, 0xC6)                                 # JMP $C617

    # Replaces $C839 (JSR $C5D9): reset encounter scene to 0xFF (Round 1 -> 0 = Forest in vh_on_round_start)
    a.label('vh_setup_game_ab_chr')
    a.abs_ref(0x20, 'vh_init_cursor')
    a.emit(0xA9, 0xFF, 0x8D, VH_SCENE_IDX & 0xFF, VH_SCENE_IDX >> 8)
    a.emit(0xA9, 18); a.abs_ref(0x20, 'vh_set_bg')
    a.emit(0xA9, 8); a.abs_ref(0x20, 'vh_set_r0')
    a.emit(0xA9, 14); a.abs_ref(0x20, 'vh_set_r1')
    a.emit(0x4C, 0xD9, 0xC5)                                 # JMP $C5D9

    # Replaces $C83C (LDX #$42; LDY #$E0; JSR $C617): Round 1 Forest BG
    a.label('vh_load_forest_bg')
    a.lda_lo('forest_ppu_stream'); a.emit(0xAA)              # LDX #<forest_ppu_stream
    a.lda_hi('forest_ppu_stream'); a.emit(0xA8)              # LDY #>forest_ppu_stream
    a.emit(0x4C, 0x17, 0xC6)                                 # JMP $C617

    # Replaces $C854 (JSR $D4D9; JSR $D2A4): runs once at start of every Game A/B round
    a.label('vh_on_round_start')
    a.emit(0xEE, VH_SCENE_IDX & 0xFF, VH_SCENE_IDX >> 8)     # INC VH_SCENE_IDX (0xFF -> 0 on Round 1)
    a.emit(0xAD, VH_SCENE_IDX & 0xFF, VH_SCENE_IDX >> 8)
    a.branch(0xF0, 'vh_rs_done')                             # Round 1 already loaded Forest at $C839/$C83C
    a.emit(0xC9, 0x03)
    a.branch(0x90, 'vh_rs_load')
    a.emit(0xA9, 0x00, 0x8D, VH_SCENE_IDX & 0xFF, VH_SCENE_IDX >> 8)
    a.label('vh_rs_load')
    a.emit(0x20, 0xE1, 0xC5)                                 # JSR $C5E1 (PPU off)
    a.emit(0xAE, VH_SCENE_IDX & 0xFF, VH_SCENE_IDX >> 8)
    a.abs_ref(0xBD, 'tbl_scene_bg_bank')
    a.abs_ref(0x20, 'vh_set_bg')
    a.emit(0xAD, VH_SCENE_IDX & 0xFF, VH_SCENE_IDX >> 8)
    a.emit(0x0A, 0xA8)                                       # ASL A; TAY = scene * 2
    a.abs_ref(0xB9, 'tbl_scene_ppu_ptrs')
    a.emit(0xAA)
    a.abs_ref_off(0xB9, 'tbl_scene_ppu_ptrs', 1)
    a.emit(0xA8)
    a.emit(0x20, 0x17, 0xC6)                                 # JSR $C617 (write nametable + attrs)
    a.emit(0xA9, 0x02, 0x85, 0x23)                           # LDA #$02; STA $23 (load scene palette)
    a.emit(0x20, 0xC1, 0xC3)                                 # JSR $C3C1
    a.emit(0x20, 0xEE, 0xC5)                                 # JSR $C5EE (PPU on)
    a.label('vh_rs_done')
    a.emit(0x20, 0xD9, 0xD4)                                 # JSR $D4D9
    a.emit(0x4C, 0xA4, 0xD2)                                 # JMP $D2A4

    # Replaces $C251 (LDA $E532,Y; LDX $E533,Y) to serve scene-specific Game A/B palettes
    a.label('vh_get_pal_ptr')
    a.emit(0xAD, VH_SCENE_IDX & 0xFF, VH_SCENE_IDX >> 8)
    a.emit(0xC9, 0x03)
    a.branch(0xB0, 'vh_pal_orig')                            # $FF on title/game_c -> orig
    a.emit(0x0A, 0xAA)                                       # TAX = scene * 2
    a.emit(0xC0, 0x02)
    a.branch(0xF0, 'vh_pal_full')
    a.emit(0xC0, 0x0A)
    a.branch(0xF0, 'vh_pal_bg')
    a.emit(0xC0, 0x0C)
    a.branch(0xF0, 'vh_pal_restore')
    a.label('vh_pal_orig')
    a.emit(0xB9, 0x32, 0xE5, 0xBE, 0x33, 0xE5, 0x60)         # LDA $E532,Y; LDX $E533,Y; RTS
    a.label('vh_pal_full')
    a.emit(0x8A, 0xA8)                                       # TXA; TAY = scene * 2
    a.abs_ref(0xB9, 'tbl_scene_pal_full')
    a.abs_ref_off(0xBE, 'tbl_scene_pal_full', 1)
    a.emit(0x60)
    a.label('vh_pal_bg')
    a.emit(0x8A, 0xA8)                                       # TXA; TAY = scene * 2
    a.abs_ref(0xB9, 'tbl_scene_pal_bg')
    a.abs_ref_off(0xBE, 'tbl_scene_pal_bg', 1)
    a.emit(0x60)
    a.label('vh_pal_restore')
    a.emit(0x8A, 0xA8)                                       # TXA; TAY = scene * 2
    a.abs_ref(0xB9, 'tbl_scene_pal_restore')
    a.abs_ref_off(0xBE, 'tbl_scene_pal_restore', 1)
    a.emit(0x60)

    # Replaces $CF49 (LDA $E724,X; STA $0403,Y) so backdrop color 0 matches active scene sky
    a.label('vh_copy_e724_pal')
    a.emit(0x8A, 0x29, 0x03)                                 # TXA; AND #$03
    a.branch(0xD0, 'vh_e724_orig')
    a.emit(0xAD, VH_SCENE_IDX & 0xFF, VH_SCENE_IDX >> 8)
    a.emit(0xC9, 0x03)
    a.branch(0xB0, 'vh_e724_orig')
    a.emit(0x8E, VH_TMP0 & 0xFF, VH_TMP0 >> 8)
    a.emit(0xAA)                                             # TAX = scene index
    a.abs_ref(0xBD, 'tbl_scene_sky')
    a.emit(0xAE, VH_TMP0 & 0xFF, VH_TMP0 >> 8)
    a.branch(0x10, 'vh_e724_store')
    a.label('vh_e724_orig')
    a.emit(0xBD, 0x24, 0xE7)                                 # LDA $E724,X
    a.label('vh_e724_store')
    a.emit(0x99, 0x03, 0x04, 0x60)                           # STA $0403,Y; RTS

    # Replaces $D54B (JSR $C5D9)
    a.label('vh_setup_game_c_chr')
    a.abs_ref(0x20, 'vh_init_cursor')
    a.emit(0xA9, 0xFF, 0x8D, VH_SCENE_IDX & 0xFF, VH_SCENE_IDX >> 8)
    a.emit(0xA9, 0); a.abs_ref(0x20, 'vh_set_bg')
    a.emit(0xA9, 10); a.abs_ref(0x20, 'vh_set_r0')
    a.emit(0xA9, 14); a.abs_ref(0x20, 'vh_set_r1')
    a.emit(0x4C, 0xD9, 0xC5)                                 # JMP $C5D9

    # Replaces $CA16 (INC $31; RTS) when Duck 1/2 spawns (up to 64 flying enemies across N R0 banks)
    num_villagers = len(art['villager_pals'])
    a.label('vh_on_villager_spawn')
    a.emit(0xA6, 0xA1)                                       # LDX $A1 (0=Target1, 1=Target2)
    a.branch(0xD0, 'spawn_slot1')
    a.label('spawn0_rng')
    a.emit(0x20, 0x88, 0xC5)                                 # JSR $C588 (RNG)
    a.emit(0x29, 0x3F)                                       # AND #$3F (0..63)
    a.emit(0xC9, num_villagers)                              # CMP #N
    a.branch(0xB0, 'spawn0_rng')                             # BCS retry
    a.emit(0x8D, VH_TARGET_KIND0 & 0xFF, VH_TARGET_KIND0 >> 8)
    a.emit(0xAA)                                             # TAX
    a.abs_ref(0xBD, 'tbl_villager_r0_bank')
    a.abs_ref(0x20, 'vh_set_r0')
    a.branch(0x10, 'spawn_done')
    a.label('spawn_slot1')
    # Target 2 must share Target 1's R0 bank and differ from Target 1
    a.emit(0xAE, VH_TARGET_KIND0 & 0xFF, VH_TARGET_KIND0 >> 8)
    a.abs_ref(0xBD, 'tbl_villager_bank_idx')
    a.emit(0xA8)                                             # TAY (bank_idx)
    a.abs_ref(0xB9, 'tbl_bank_count')
    a.emit(0x8D, VH_TMP0 & 0xFF, VH_TMP0 >> 8)               # TMP0 = count
    a.abs_ref(0xB9, 'tbl_bank_start')
    a.emit(0x8D, VH_TMP1 & 0xFF, VH_TMP1 >> 8)               # TMP1 = start
    a.label('spawn1_rng')
    a.emit(0x20, 0x88, 0xC5)                                 # JSR $C588 (RNG)
    a.emit(0x29, 0x07)                                       # AND #$07
    a.emit(0xCD, VH_TMP0 & 0xFF, VH_TMP0 >> 8)               # CMP count
    a.branch(0xB0, 'spawn1_rng')                             # BCS retry
    a.emit(0x18, 0x6D, VH_TMP1 & 0xFF, VH_TMP1 >> 8)         # CLC; ADC start
    a.emit(0xCD, VH_TARGET_KIND0 & 0xFF, VH_TARGET_KIND0 >> 8)
    a.branch(0xD0, 'store_slot1')
    a.emit(0x18, 0x69, 0x01)                                 # CLC; ADC #1
    a.emit(0x8D, VH_TMP2 & 0xFF, VH_TMP2 >> 8)
    a.emit(0xAD, VH_TMP1 & 0xFF, VH_TMP1 >> 8)
    a.emit(0x18, 0x6D, VH_TMP0 & 0xFF, VH_TMP0 >> 8)         # A = start + count
    a.emit(0xCD, VH_TMP2 & 0xFF, VH_TMP2 >> 8)
    a.branch(0xD0, 'use_tmp2')
    a.emit(0xAD, VH_TMP1 & 0xFF, VH_TMP1 >> 8)               # wrap to start
    a.branch(0x10, 'store_slot1')
    a.label('use_tmp2')
    a.emit(0xAD, VH_TMP2 & 0xFF, VH_TMP2 >> 8)
    a.label('store_slot1')
    a.emit(0x8D, VH_TARGET_KIND1 & 0xFF, VH_TARGET_KIND1 >> 8)
    a.emit(0xAA)                                             # TAX
    a.abs_ref(0xBD, 'tbl_villager_r0_bank')
    a.abs_ref(0x20, 'vh_set_r0')
    a.label('spawn_done')
    a.emit(0xE6, 0x31, 0x60)                                 # INC $31; RTS

    # Replaces $D6D2 (INC $31; RTS) when Clay 1/2 spawns (2 clay targets: 0=Octorok, 1=Moa)
    a.label('vh_on_clay_spawn')
    a.emit(0xA9, 10); a.abs_ref(0x20, 'vh_set_r0')
    a.emit(0xEE, VH_CLAY_SEQ & 0xFF, VH_CLAY_SEQ >> 8)
    a.emit(0xAD, VH_CLAY_SEQ & 0xFF, VH_CLAY_SEQ >> 8)
    a.emit(0x29, 0x01)                                       # AND #$01
    a.emit(0xA6, 0xA1)
    a.branch(0xD0, 'clay_slot1')
    a.emit(0x8D, VH_TARGET_KIND0 & 0xFF, VH_TARGET_KIND0 >> 8)
    a.emit(0xA9, 0x20, 0x85, 0x36, 0xA9, 0x5F, 0x85, 0x37)   # OAM $0220-$025F
    a.emit(0xE6, 0x31, 0x60)
    a.label('clay_slot1')
    a.emit(0x8D, VH_TARGET_KIND1 & 0xFF, VH_TARGET_KIND1 >> 8)
    a.emit(0xA9, 0x60, 0x85, 0x36, 0xA9, 0x8F, 0x85, 0x37)   # OAM $0260-$028F
    a.emit(0xE6, 0x31, 0x60)

    # Roar trigger hooks
    a.label('vh_on_intro_roar')
    a.abs_ref(0x20, 'vh_play_roar')
    a.emit(0xA9, 60, 0x8D, VH_SHAKE_TIMER & 0xFF, VH_SHAKE_TIMER >> 8)  # screen shake during jump
    a.emit(0xA9, 0x04, 0x85, 0x9E, 0x60)                     # LDA #$04; STA $9E; RTS

    a.label('vh_on_clay_intro_roar')
    a.emit(0x20, 0x6C, 0xF5)                                 # JSR $F56C
    a.abs_ref(0x4C, 'vh_play_roar')

    a.label('vh_on_round_clear_roar')
    a.emit(0x20, 0x1D, 0xD5)                                 # JSR $D51D (round clear jingle)
    a.abs_ref(0x4C, 'vh_play_roar')

    a.label('vh_on_perfect_roar')
    a.emit(0x20, 0x38, 0xD5)                                 # JSR $D538 (perfect jingle)
    a.abs_ref(0x4C, 'vh_play_roar')

    # ------------------------------------------------------------------
    # 3. Title Input Hook ($C16E) + Controller Poll Hook ($C071) + Frame Tick ($C079)
    # ------------------------------------------------------------------
    # Replaces $C16E (LDA $16; AND #$30; CMP #$10; BNE $C189 -> 8 bytes -> JMP vh_title_input)
    a.label('vh_title_input')
    a.emit(0xA5, 0x16, 0x29, 0x30, 0xC9, 0x10)
    a.branch(0xF0, 'title_start')
    # Also check raw $0440 newly pressed A ($80) -> start game; Up/Down ($0C) -> cycle $05FE
    a.emit(0xAD, 0x40, 0x04)
    a.emit(0x4D, VH_PREV_PAD1 & 0xFF, VH_PREV_PAD1 >> 8)     # changed bits
    a.emit(0x2D, 0x40, 0x04)                                 # newly pressed bits
    a.emit(0x48)
    a.emit(0x29, 0x80)                                       # A button?
    a.branch(0xF0, 'title_chk_ud')
    a.emit(0x68)
    a.label('title_start')
    a.emit(0x4C, 0x76, 0xC1)                                 # Start game!
    a.label('title_chk_ud')
    a.emit(0x68, 0x29, 0x0C)                                 # Up or Down?
    a.branch(0xF0, 'title_no_start')
    a.emit(0xA9, 0x00, 0x8D, 0xFD, 0x05)                     # allow immediate cycle
    a.emit(0xA9, 0x20)                                       # fake Select ($20) into $C189!
    a.emit(0x4C, 0x89, 0xC1)
    a.label('title_no_start')
    a.emit(0xA5, 0x16, 0x29, 0x30)
    a.emit(0x4C, 0x89, 0xC1)

    # Replaces $C071 (JSR $C284)
    a.label('vh_after_pad_poll')
    a.emit(0x20, 0x84, 0xC2)                                 # JSR $C284 (polls $4016 -> $0440 & $16)
    a.emit(0xA5, 0x24)
    a.branch(0xF0, 'poll_chk_pause')
    a.emit(0x60)
    a.label('poll_chk_pause')
    a.emit(0xAD, 0xFC, 0x05)                                 # paused?
    a.branch(0xF0, 'poll_chk_state')
    a.emit(0x60)
    a.label('poll_chk_state')
    a.emit(0xA5, 0x25)
    a.emit(0xC9, 0x03)
    a.branch(0xF0, 'poll_active')
    a.emit(0xC9, 0x0B)
    a.branch(0xF0, 'poll_active')
    a.emit(0x60)
    a.label('poll_active')
    # Safety guard: ensure Bank 30 is active ($C000-$DFFF) before active targets run ($D700-$DFFF)
    a.emit(0xA5, 0xB9)                                       # targets active?
    a.branch(0xF0, 'poll_roar_ok')
    a.emit(0xAD, VH_ROAR_TIMER & 0xFF, VH_ROAR_TIMER >> 8)
    a.branch(0xF0, 'poll_roar_ok')
    a.abs_ref(0x20, 'vh_stop_roar')
    a.label('poll_roar_ok')
    # D-Pad movement (3 px/frame)
    a.emit(0xAD, 0x40, 0x04)
    a.emit(0x4A)                                             # bit 0 = Right
    a.branch(0x90, 'no_right')
    a.emit(0x48)
    a.emit(0xAD, VH_CURSOR_X & 0xFF, VH_CURSOR_X >> 8)
    a.emit(0x18, 0x69, 0x03, 0xC9, 240)
    a.branch(0x90, 'st_right')
    a.emit(0xA9, 240)
    a.label('st_right')
    a.emit(0x8D, VH_CURSOR_X & 0xFF, VH_CURSOR_X >> 8)
    a.emit(0x68)
    a.label('no_right')
    a.emit(0x4A)                                             # bit 1 = Left
    a.branch(0x90, 'no_left')
    a.emit(0x48)
    a.emit(0xAD, VH_CURSOR_X & 0xFF, VH_CURSOR_X >> 8)
    a.emit(0x38, 0xE9, 0x03, 0xC9, 8)
    a.branch(0xB0, 'st_left')
    a.emit(0xA9, 8)
    a.label('st_left')
    a.emit(0x8D, VH_CURSOR_X & 0xFF, VH_CURSOR_X >> 8)
    a.emit(0x68)
    a.label('no_left')
    a.emit(0x4A)                                             # bit 2 = Down
    a.branch(0x90, 'no_down')
    a.emit(0x48)
    a.emit(0xAD, VH_CURSOR_Y & 0xFF, VH_CURSOR_Y >> 8)
    a.emit(0x18, 0x69, 0x03, 0xC9, 176)
    a.branch(0x90, 'st_down')
    a.emit(0xA9, 176)
    a.label('st_down')
    a.emit(0x8D, VH_CURSOR_Y & 0xFF, VH_CURSOR_Y >> 8)
    a.emit(0x68)
    a.label('no_down')
    a.emit(0x4A)                                             # bit 3 = Up
    a.branch(0x90, 'no_up')
    a.emit(0xAD, VH_CURSOR_Y & 0xFF, VH_CURSOR_Y >> 8)
    a.emit(0x38, 0xE9, 0x03, 0xC9, 8)
    a.branch(0xB0, 'st_up')
    a.emit(0xA9, 8)
    a.label('st_up')
    a.emit(0x8D, VH_CURSOR_Y & 0xFF, VH_CURSOR_Y >> 8)
    a.label('no_up')
    # Edge-triggered A/B ($C0) shot
    a.emit(0xAD, 0x40, 0x04, 0x29, 0xC0)
    a.branch(0xF0, 'poll_done')
    a.emit(0xAD, VH_PREV_PAD1 & 0xFF, VH_PREV_PAD1 >> 8, 0x29, 0xC0)
    a.branch(0xD0, 'poll_done')
    a.emit(0xA5, 0xB9)                                       # targets active?
    a.branch(0xF0, 'poll_done')
    a.emit(0xA5, 0xBA)                                       # ammo > 0?
    a.branch(0xF0, 'poll_done')
    a.emit(0xA9, 0x01)
    a.emit(0x8D, VH_SHOT_MODE & 0xFF, VH_SHOT_MODE >> 8)
    a.emit(0x85, 0xB5)                                       # trigger shot!
    a.emit(0xA9, 14, 0x8D, VH_FIRE_TIMER & 0xFF, VH_FIRE_TIMER >> 8)
    a.emit(0xAD, VH_CURSOR_X & 0xFF, VH_CURSOR_X >> 8, 0x8D, VH_FIRE_X & 0xFF, VH_FIRE_X >> 8)
    a.emit(0xAD, VH_CURSOR_Y & 0xFF, VH_CURSOR_Y >> 8, 0x8D, VH_FIRE_Y & 0xFF, VH_FIRE_Y >> 8)
    a.label('poll_done')
    a.emit(0x60)

    # Replaces $C079 (JSR $C61E)
    a.label('vh_frame_tick')
    # Save raw P1 for next frame's edge detection
    a.emit(0xAD, 0x40, 0x04, 0x8D, VH_PREV_PAD1 & 0xFF, VH_PREV_PAD1 >> 8)
    # Roar DMC timer tick
    a.emit(0xAD, VH_ROAR_TIMER & 0xFF, VH_ROAR_TIMER >> 8)
    a.branch(0xF0, 'ft_no_roar')
    a.emit(0xCE, VH_ROAR_TIMER & 0xFF, VH_ROAR_TIMER >> 8)
    a.branch(0xD0, 'ft_no_roar')
    a.abs_ref(0x20, 'vh_stop_roar')
    a.label('ft_no_roar')
    # Screen shake timer tick (writes Y scroll $0B during Barba's downstab jump)
    a.emit(0xAD, VH_SHAKE_TIMER & 0xFF, VH_SHAKE_TIMER >> 8)
    a.branch(0xF0, 'ft_no_shake')
    a.emit(0xCE, VH_SHAKE_TIMER & 0xFF, VH_SHAKE_TIMER >> 8)
    a.branch(0xF0, 'ft_shake_end')
    a.emit(0xAD, VH_SHAKE_TIMER & 0xFF, VH_SHAKE_TIMER >> 8)
    a.emit(0x29, 0x03, 0xAA)
    a.abs_ref(0xBD, 'tbl_shake_y')
    a.emit(0x85, 0x0B)
    a.branch(0x10, 'ft_no_shake')
    a.label('ft_shake_end')
    a.emit(0xA9, 0x00, 0x85, 0x0B)
    a.label('ft_no_shake')
    # Draw Fireball Burst ($0200-$020F) and Crosshair ($0210-$021F) ON TOP of targets in active gameplay
    a.emit(0xA5, 0x24)
    a.branch(0xD0, 'ft_hide_overlay')
    a.emit(0xA5, 0x25)
    a.emit(0xC9, 0x03)
    a.branch(0xF0, 'ft_draw_crosshair')
    a.emit(0xC9, 0x0B)
    a.branch(0xF0, 'ft_draw_crosshair')
    a.label('ft_hide_overlay')
    a.emit(0xA9, 0xF4, 0xA2, 0x00)
    a.label('hide_ov_loop')
    a.emit(0x9D, 0x00, 0x02)
    a.emit(0xE8, 0xE8, 0xE8, 0xE8, 0xE0, 0x20)
    a.branch(0xD0, 'hide_ov_loop')
    a.emit(0x4C, 0x1E, 0xC6)                                 # JMP $C61E

    a.label('ft_draw_crosshair')
    # Crosshair ($0210-$021F): 4 sprites at (CX-8, CY-8), (CX, CY-8), (CX-8, CY), (CX, CY) tiles $00..$03, Pal 1
    a.emit(0xAD, VH_CURSOR_Y & 0xFF, VH_CURSOR_Y >> 8, 0x38, 0xE9, 0x08)
    a.emit(0x8D, 0x10, 0x02, 0x8D, 0x14, 0x02)               # Y top
    a.emit(0x18, 0x69, 0x08)
    a.emit(0x8D, 0x18, 0x02, 0x8D, 0x1C, 0x02)               # Y bot
    a.emit(0xAD, VH_CURSOR_X & 0xFF, VH_CURSOR_X >> 8, 0x38, 0xE9, 0x08)
    a.emit(0x8D, 0x13, 0x02, 0x8D, 0x1B, 0x02)               # X left
    a.emit(0x18, 0x69, 0x08)
    a.emit(0x8D, 0x17, 0x02, 0x8D, 0x1F, 0x02)               # X right
    a.emit(0xA9, 0x00, 0x8D, 0x11, 0x02)
    a.emit(0xA9, 0x01, 0x8D, 0x15, 0x02)
    a.emit(0xA9, 0x02, 0x8D, 0x19, 0x02)
    a.emit(0xA9, 0x03, 0x8D, 0x1D, 0x02)
    a.emit(0xA9, 0x01)                                       # Pal 1
    a.emit(0x8D, 0x12, 0x02, 0x8D, 0x16, 0x02)
    a.emit(0x8D, 0x1A, 0x02, 0x8D, 0x1E, 0x02)

    # Fireball Burst ($0200-$020F) — highest OAM priority!
    a.emit(0xAD, VH_FIRE_TIMER & 0xFF, VH_FIRE_TIMER >> 8)
    a.branch(0xF0, 'ft_hide_fire')
    a.emit(0xCE, VH_FIRE_TIMER & 0xFF, VH_FIRE_TIMER >> 8)
    a.emit(0xA2, 0x04)                                       # Frame 0 ($04..$07)
    a.emit(0xC9, 10)
    a.branch(0xB0, 'fb_frame_ok')
    a.emit(0xA2, 0x08)                                       # Frame 1 ($08..$0B)
    a.emit(0xC9, 5)
    a.branch(0xB0, 'fb_frame_ok')
    a.emit(0xA2, 0x0C)                                       # Frame 2 ($0C..$0F)
    a.label('fb_frame_ok')
    a.emit(0x8E, 0x01, 0x02, 0xE8)
    a.emit(0x8E, 0x05, 0x02, 0xE8)
    a.emit(0x8E, 0x09, 0x02, 0xE8)
    a.emit(0x8E, 0x0D, 0x02)
    a.emit(0xAD, VH_FIRE_Y & 0xFF, VH_FIRE_Y >> 8, 0x38, 0xE9, 0x08)
    a.emit(0x8D, 0x00, 0x02, 0x8D, 0x04, 0x02)
    a.emit(0x18, 0x69, 0x08)
    a.emit(0x8D, 0x08, 0x02, 0x8D, 0x0C, 0x02)
    a.emit(0xAD, VH_FIRE_X & 0xFF, VH_FIRE_X >> 8, 0x38, 0xE9, 0x08)
    a.emit(0x8D, 0x03, 0x02, 0x8D, 0x0B, 0x02)
    a.emit(0x18, 0x69, 0x08)
    a.emit(0x8D, 0x07, 0x02, 0x8D, 0x0F, 0x02)
    a.emit(0xA9, 0x01)                                       # Pal 1
    a.emit(0x8D, 0x02, 0x02, 0x8D, 0x06, 0x02)
    a.emit(0x8D, 0x0A, 0x02, 0x8D, 0x0E, 0x02)
    a.emit(0x4C, 0x1E, 0xC6)
    a.label('ft_hide_fire')
    a.emit(0xA9, 0xF4)
    a.emit(0x8D, 0x00, 0x02, 0x8D, 0x04, 0x02, 0x8D, 0x08, 0x02, 0x8D, 0x0C, 0x02)
    a.emit(0x4C, 0x1E, 0xC6)

    # ------------------------------------------------------------------
    # 4. Shot Resolution Hook ($D17E)
    # ------------------------------------------------------------------
    a.label('vh_shot_branch')
    a.emit(0xAD, VH_SHOT_MODE & 0xFF, VH_SHOT_MODE >> 8)
    a.branch(0xD0, 'ctrl_shot')
    # Zapper fallback
    a.emit(0xA9, 0x04, 0x85, 0x23)
    a.emit(0x20, 0x3B, 0xC2, 0x20, 0xE1, 0xC5)
    a.emit(0x4C, 0x88, 0xD1)

    a.label('ctrl_shot')
    a.emit(0xA9, 0x00, 0x8D, VH_SHOT_MODE & 0xFF, VH_SHOT_MODE >> 8)
    a.emit(0xA2, 18)                                         # hit_ry = 18 (villagers)
    a.emit(0xA5, 0x1F, 0xC9, 0x02)
    a.branch(0xD0, 'ry_ok')
    a.emit(0xA2, 14)                                         # hit_ry = 14 (clay targets)
    a.label('ry_ok')
    a.emit(0x8E, VH_TMP0 & 0xFF, VH_TMP0 >> 8)               # VH_TMP0 = hit_ry
    # Check Target 1 ($0300 != 0 and $0301 == 3)
    a.emit(0xAD, 0x00, 0x03)
    a.branch(0xF0, 'chk_t2')
    a.emit(0xAD, 0x01, 0x03, 0xC9, 0x03)
    a.branch(0xD0, 'chk_t2')
    a.emit(0xAD, 0x03, 0x03)                                 # Target 1 X
    a.emit(0x38, 0xED, VH_CURSOR_X & 0xFF, VH_CURSOR_X >> 8)
    a.branch(0xB0, 't1_dx_pos')
    a.emit(0x49, 0xFF, 0x18, 0x69, 0x01)
    a.label('t1_dx_pos')
    a.emit(0xC9, 15)                                         # |dx| <= 14
    a.branch(0xB0, 'chk_t2')
    a.emit(0xAD, 0x02, 0x03)                                 # Target 1 Y
    a.emit(0x38, 0xED, VH_CURSOR_Y & 0xFF, VH_CURSOR_Y >> 8)
    a.branch(0xB0, 't1_dy_pos')
    a.emit(0x49, 0xFF, 0x18, 0x69, 0x01)
    a.label('t1_dy_pos')
    a.emit(0xCD, VH_TMP0 & 0xFF, VH_TMP0 >> 8)
    a.branch(0xB0, 'chk_t2')
    # Target 1 HIT!
    a.emit(0xA9, 0x04, 0x8D, 0x01, 0x03)
    a.emit(0xE6, 0xAA, 0xE6, 0xBD, 0x60)

    a.label('chk_t2')
    a.emit(0xAD, 0x50, 0x03)
    a.branch(0xF0, 'ctrl_miss')
    a.emit(0xAD, 0x51, 0x03, 0xC9, 0x03)
    a.branch(0xD0, 'ctrl_miss')
    a.emit(0xAD, 0x53, 0x03)                                 # Target 2 X
    a.emit(0x38, 0xED, VH_CURSOR_X & 0xFF, VH_CURSOR_X >> 8)
    a.branch(0xB0, 't2_dx_pos')
    a.emit(0x49, 0xFF, 0x18, 0x69, 0x01)
    a.label('t2_dx_pos')
    a.emit(0xC9, 15)
    a.branch(0xB0, 'ctrl_miss')
    a.emit(0xAD, 0x52, 0x03)                                 # Target 2 Y
    a.emit(0x38, 0xED, VH_CURSOR_Y & 0xFF, VH_CURSOR_Y >> 8)
    a.branch(0xB0, 't2_dy_pos')
    a.emit(0x49, 0xFF, 0x18, 0x69, 0x01)
    a.label('t2_dy_pos')
    a.emit(0xCD, VH_TMP0 & 0xFF, VH_TMP0 >> 8)
    a.branch(0xB0, 'ctrl_miss')
    # Target 2 HIT!
    a.emit(0xA9, 0x04, 0x8D, 0x51, 0x03)
    a.emit(0xE6, 0xAA, 0xE6, 0xBD)
    a.label('ctrl_miss')
    a.emit(0x60)

    # ------------------------------------------------------------------
    # 5. Metasprite Renderer ($D01B -> JMP vh_draw_sprite)
    # ------------------------------------------------------------------
    a.label('vh_draw_sprite')
    a.emit(0xA5, 0x36, 0x85, 0xB4)                           # $B4 = OAM write cursor
    a.emit(0xA5, 0xA1)                                       # 0=Target1, 1=Target2, 2=Dog
    a.emit(0xC9, 0x02)
    a.branch(0xD0, 'draw_target')
    a.abs_ref(0x4C, 'draw_dog_slot')

    a.label('draw_target')
    a.emit(0xA5, 0x1F, 0xC9, 0x02)
    a.branch(0xD0, 'draw_villager')
    a.abs_ref(0x4C, 'draw_clay')

    # --- Draw 16x32 Z2 Enemy ---
    a.label('draw_villager')
    a.emit(0xA6, 0xA1)
    a.emit(0xBD, VH_TARGET_KIND0 & 0xFF, VH_TARGET_KIND0 >> 8)
    a.emit(0x8D, VH_TMP0 & 0xFF, VH_TMP0 >> 8)               # TMP0 = kind
    a.emit(0xAA)                                             # TAX
    a.abs_ref(0xBD, 'tbl_villager_r0_bank')
    a.abs_ref(0x20, 'vh_set_r0')
    a.emit(0xAE, VH_TMP0 & 0xFF, VH_TMP0 >> 8)
    a.abs_ref(0xBD, 'tbl_villager_pals')
    a.emit(0x8D, VH_TMP1 & 0xFF, VH_TMP1 >> 8)               # TMP1 = base palette
    # Shocked ($31 == 4) -> flash Pal 1 on odd frames + 1px shake; Falling ($31 == 5) -> V-flip ($80)
    a.emit(0xA5, 0x31, 0xC9, 0x04)
    a.branch(0xD0, 'v_not_shock')
    a.emit(0xA5, 0x2F, 0x29, 0x02)
    a.branch(0xF0, 'v_shock_pal_ok')
    a.emit(0xA9, 0x01, 0x8D, VH_TMP1 & 0xFF, VH_TMP1 >> 8)
    a.label('v_shock_pal_ok')
    a.emit(0xA9, 0x00, 0x8D, VH_TMP2 & 0xFF, VH_TMP2 >> 8)   # frame = 0
    a.branch(0x10, 'v_attr_build')
    a.label('v_not_shock')
    a.emit(0xA5, 0x2F, 0x29, 0x04, 0x4A, 0x4A)
    a.emit(0x8D, VH_TMP2 & 0xFF, VH_TMP2 >> 8)               # walk frame (0 or 1)
    a.label('v_attr_build')
    a.emit(0xAD, VH_TMP1 & 0xFF, VH_TMP1 >> 8)
    a.emit(0xA6, 0x38)                                       # behind grass?
    a.branch(0xF0, 'v_no_bg')
    a.emit(0x09, 0x20)
    a.label('v_no_bg')
    a.emit(0xA6, 0x34)                                       # $34==0 -> face right (H-flip $40)
    a.branch(0xD0, 'v_no_hflip')
    a.emit(0x09, 0x40)
    a.label('v_no_hflip')
    a.emit(0xA6, 0x31, 0xE0, 0x05)
    a.branch(0xD0, 'v_no_vflip')
    a.emit(0x09, 0x80)                                       # V-flip when falling
    a.label('v_no_vflip')
    a.emit(0x8D, VH_TMP3 & 0xFF, VH_TMP3 >> 8)               # TMP3 = final OAM attr

    # Map index = kind * 2 + walk_frame (0..11)
    a.emit(0xAD, VH_TMP0 & 0xFF, VH_TMP0 >> 8, 0x0A)
    a.emit(0x0D, VH_TMP2 & 0xFF, VH_TMP2 >> 8, 0x0A, 0xAA)
    a.abs_ref(0xBD, 'tbl_villager_ptrs')
    a.emit(0x85, ZP_PTR0)
    a.abs_ref_off(0xBD, 'tbl_villager_ptrs', 1)
    a.emit(0x85, ZP_PTR0 + 1)

    # Top-left Y = $32 - 16 (clamped >= 8; if $31==3 & walk_frame==1 subtract 1px panic hop)
    a.emit(0xA5, 0x32, 0x38, 0xE9, 16)
    a.emit(0xC9, 0xF0)
    a.branch(0x90, 'v_y_ok')
    a.emit(0xA9, 0x08)
    a.label('v_y_ok')
    a.emit(0x8D, VH_TMP4 & 0xFF, VH_TMP4 >> 8)               # base Y
    a.emit(0xA5, 0x33, 0x38, 0xE9, 8)
    a.emit(0x8D, VH_TMP5 & 0xFF, VH_TMP5 >> 8)               # base X

    # Draw 2x4 grid (row 0..3, col 0..1)
    # Note: if H-flipped ($34==0), swap col 0 and col 1 X offsets!
    a.emit(0xA0, 0x00)                                       # Y = map index (0..7)
    a.label('v_row_loop')
    a.emit(0xB1, ZP_PTR0)
    a.emit(0xC9, 0xFF)
    a.branch(0xF0, 'v_skip_tile')
    a.emit(0xA6, 0xB4, 0xE4, 0x37)
    a.branch(0xB0, 'v_done_oam')
    # Y coord = base_Y + (row * 8); if V-flipped ($31==5), (3-row)*8
    a.emit(0x48)                                             # push tile
    a.emit(0x98, 0x4A, 0x0A, 0x0A, 0x0A)                     # (Y >> 1) * 8
    a.emit(0xA6, 0x31, 0xE0, 0x05)
    a.branch(0xD0, 'v_y_normal')
    a.emit(0x49, 0x18)                                       # 24 - row*8
    a.label('v_y_normal')
    a.emit(0x18, 0x6D, VH_TMP4 & 0xFF, VH_TMP4 >> 8)
    a.emit(0xA6, 0xB4, 0x9D, 0x00, 0x02)                     # OAM Y
    a.emit(0x68, 0x9D, 0x01, 0x02)                           # OAM tile
    a.emit(0xAD, VH_TMP3 & 0xFF, VH_TMP3 >> 8, 0x9D, 0x02, 0x02)  # OAM attr
    # X coord: col = Y & 1; if H-flipped ($34==0), col ^= 1 (keep Y intact!)
    a.emit(0x98, 0x29, 0x01)
    a.emit(0xA6, 0x34)                                       # LDX $34
    a.branch(0xD0, 'v_x_noflip')
    a.emit(0x49, 0x01)
    a.label('v_x_noflip')
    a.emit(0x0A, 0x0A, 0x0A, 0x18, 0x6D, VH_TMP5 & 0xFF, VH_TMP5 >> 8)
    a.emit(0xA6, 0xB4, 0x9D, 0x03, 0x02)                     # LDX $B4; STA $0203,X
    a.emit(0x8A, 0x18, 0x69, 0x04, 0x85, 0xB4)
    a.label('v_skip_tile')
    a.emit(0xC8, 0xC0, 0x08)
    a.branch(0xD0, 'v_row_loop')
    a.label('v_done_oam')
    a.abs_ref(0x4C, 'vh_clear_oam')

    # --- Draw 16x16 Game C Flying Target (Octorok / Moa) ---
    a.label('draw_clay')
    a.emit(0xA9, 10); a.abs_ref(0x20, 'vh_set_r0')
    a.emit(0xA6, 0xA1)
    a.emit(0xBD, VH_TARGET_KIND0 & 0xFF, VH_TARGET_KIND0 >> 8)  # 0..2
    a.emit(0x8D, VH_TMP0 & 0xFF, VH_TMP0 >> 8)
    a.emit(0xAA)
    a.abs_ref(0xBD, 'tbl_clay_pals')
    a.emit(0xA6, 0x38)
    a.branch(0xF0, 'c_no_bg')
    a.emit(0x09, 0x20)
    a.label('c_no_bg')
    a.emit(0x8D, VH_TMP3 & 0xFF, VH_TMP3 >> 8)               # attr
    # Scale tier from $35 ($18..$21): 0..2 -> full anim (0/1), 3..6 -> med (2), 7..9 -> sml (3)
    a.emit(0xA5, 0x35, 0x38, 0xE9, 0x18)
    a.emit(0xC9, 0x03)
    a.branch(0xB0, 'c_not_near')
    a.emit(0xA5, 0x2F, 0x29, 0x04, 0x4A, 0x4A)               # anim frame 0 or 1
    a.branch(0x10, 'c_scale_ok')
    a.label('c_not_near')
    a.emit(0xC9, 0x07)
    a.branch(0xB0, 'c_far')
    a.emit(0xA9, 0x02)                                       # med
    a.branch(0x10, 'c_scale_ok')
    a.label('c_far')
    a.emit(0xA9, 0x03)                                       # sml
    a.label('c_scale_ok')
    a.emit(0x8D, VH_TMP2 & 0xFF, VH_TMP2 >> 8)
    # map index = kind * 4 + tier (0..11)
    a.emit(0xAD, VH_TMP0 & 0xFF, VH_TMP0 >> 8, 0x0A, 0x0A)
    a.emit(0x0D, VH_TMP2 & 0xFF, VH_TMP2 >> 8, 0x0A, 0xAA)
    a.abs_ref(0xBD, 'tbl_clay_ptrs')
    a.emit(0x85, ZP_PTR0)
    a.abs_ref_off(0xBD, 'tbl_clay_ptrs', 1)
    a.emit(0x85, ZP_PTR0 + 1)
    a.emit(0xA5, 0x32, 0x38, 0xE9, 0x08, 0x8D, VH_TMP4 & 0xFF, VH_TMP4 >> 8)
    a.emit(0xA5, 0x33, 0x38, 0xE9, 0x08, 0x8D, VH_TMP5 & 0xFF, VH_TMP5 >> 8)
    a.emit(0xA0, 0x00)
    a.label('c_loop')
    a.emit(0xB1, ZP_PTR0)
    a.emit(0xC9, 0xFF)
    a.branch(0xF0, 'c_skip')
    a.emit(0xA6, 0xB4, 0xE4, 0x37)
    a.branch(0xB0, 'c_done')
    a.emit(0x9D, 0x01, 0x02)                                 # tile
    a.emit(0xAD, VH_TMP3 & 0xFF, VH_TMP3 >> 8, 0x9D, 0x02, 0x02)
    a.emit(0x98, 0x4A, 0x0A, 0x0A, 0x0A, 0x18, 0x6D, VH_TMP4 & 0xFF, VH_TMP4 >> 8)
    a.emit(0x9D, 0x00, 0x02)                                 # Y
    a.emit(0x98, 0x29, 0x01, 0x0A, 0x0A, 0x0A, 0x18, 0x6D, VH_TMP5 & 0xFF, VH_TMP5 >> 8)
    a.emit(0x9D, 0x03, 0x02)                                 # X
    a.emit(0xA5, 0xB4, 0x18, 0x69, 0x04, 0x85, 0xB4)
    a.label('c_skip')
    a.emit(0xC8, 0xC0, 0x04)
    a.branch(0xD0, 'c_loop')
    a.label('c_done')
    a.abs_ref(0x4C, 'vh_clear_oam')

    # --- Draw Dog Slot ($A1 == 2): Barba ($0C..$15) or Villainous Link ($16..$17) ---
    a.label('draw_dog_slot')
    a.emit(0xA5, 0x35)
    a.emit(0xC9, 0x16)
    a.branch(0x90, 'draw_barba')
    a.emit(0xC9, 0x18)
    a.branch(0xB0, 'draw_barba')

    # --- Villainous Link (laugh/mock $16..$17) ---
    a.emit(0xA9, 16); a.abs_ref(0x20, 'vh_set_r1')
    a.emit(0xA5, 0x35, 0x38, 0xE9, 0x16, 0x0A, 0xAA)         # 0 or 2
    a.abs_ref(0xBD, 'tbl_link_ptrs')
    a.emit(0x85, ZP_PTR0)
    a.abs_ref_off(0xBD, 'tbl_link_ptrs', 1)
    a.emit(0x85, ZP_PTR0 + 1)
    a.emit(0xA9, 0x03)                                       # Pal 3
    a.emit(0xA6, 0x38)
    a.branch(0xF0, 'l_no_bg')
    a.emit(0x09, 0x20)
    a.label('l_no_bg')
    a.emit(0x8D, VH_TMP3 & 0xFF, VH_TMP3 >> 8)
    a.emit(0xA5, 0x32, 0x38, 0xE9, 12, 0x8D, VH_TMP4 & 0xFF, VH_TMP4 >> 8)
    a.emit(0xA5, 0x33, 0x38, 0xE9, 0x08, 0x8D, VH_TMP5 & 0xFF, VH_TMP5 >> 8)
    a.emit(0xA0, 0x00)
    a.label('l_loop')
    a.emit(0xB1, ZP_PTR0)
    a.emit(0xC9, 0xFF)
    a.branch(0xF0, 'l_skip')
    a.emit(0xA6, 0xB4, 0xE4, 0x37)
    a.branch(0xB0, 'l_done')
    a.emit(0x9D, 0x01, 0x02)
    a.emit(0xAD, VH_TMP3 & 0xFF, VH_TMP3 >> 8, 0x9D, 0x02, 0x02)
    a.emit(0x98, 0x4A, 0x0A, 0x0A, 0x0A, 0x18, 0x6D, VH_TMP4 & 0xFF, VH_TMP4 >> 8)
    a.emit(0x9D, 0x00, 0x02)
    a.emit(0x98, 0x29, 0x01, 0x0A, 0x0A, 0x0A, 0x18, 0x6D, VH_TMP5 & 0xFF, VH_TMP5 >> 8)
    a.emit(0x9D, 0x03, 0x02)
    a.emit(0xA5, 0xB4, 0x18, 0x69, 0x04, 0x85, 0xB4)
    a.label('l_skip')
    a.emit(0xC8, 0xC0, 0x08)
    a.branch(0xD0, 'l_loop')
    a.label('l_done')
    a.abs_ref(0x4C, 'vh_clear_oam')

    # --- Barba (full-body 56x48 + Z2 downstab, Pal 1) ---
    a.label('draw_barba')
    a.emit(0xA9, 14); a.abs_ref(0x20, 'vh_set_r1')
    # Map $35 ($0C..$15) -> Barba pose:
    #   0=walk0, 1=walk1, 2=windup, 3=attack/roar, 4=downstab, 5=crouch, 6=catch_windup, 7=catch_attack
    a.emit(0xA5, 0x35)
    a.emit(0xC9, 0x0C)
    a.branch(0xF0, 'b_w0')
    a.emit(0xC9, 0x0D)
    a.branch(0xF0, 'b_w1')
    a.emit(0xC9, 0x0E)
    a.branch(0xF0, 'b_w0')
    a.emit(0xC9, 0x0F)
    a.branch(0xF0, 'b_crouch')
    a.emit(0xC9, 0x10)
    a.branch(0xF0, 'b_windup')
    a.emit(0xC9, 0x11)
    a.branch(0xF0, 'b_attack')
    a.emit(0xC9, 0x12)
    a.branch(0xF0, 'b_downstab')
    a.emit(0xC9, 0x13)
    a.branch(0xF0, 'b_downstab')
    # $14 or $15 (catch celebration): alternate 24x48 catch_attack / catch_windup (3 vertical 16px rows)
    a.emit(0xA5, 0x2F, 0x29, 0x08)
    a.branch(0xF0, 'b_catch_attack')
    a.emit(0xA9, 0x06); a.branch(0x10, 'b_pose_ok')
    a.label('b_catch_attack')
    a.emit(0xA9, 0x07); a.branch(0x10, 'b_pose_ok')
    a.label('b_windup')
    a.emit(0xA9, 0x02); a.branch(0x10, 'b_pose_ok')
    a.label('b_w0')
    a.emit(0xA9, 0x00); a.branch(0x10, 'b_pose_ok')
    a.label('b_w1')
    a.emit(0xA9, 0x01); a.branch(0x10, 'b_pose_ok')
    a.label('b_attack')
    a.emit(0xA9, 0x03); a.branch(0x10, 'b_pose_ok')
    a.label('b_downstab')
    a.emit(0xA9, 0x04); a.branch(0x10, 'b_pose_ok')
    a.label('b_crouch')
    a.emit(0xA9, 0x05)
    a.label('b_pose_ok')
    a.emit(0x0A, 0xAA)
    a.abs_ref(0xBD, 'tbl_barba_ptrs')
    a.emit(0x85, ZP_PTR0)
    a.abs_ref_off(0xBD, 'tbl_barba_ptrs', 1)
    a.emit(0x85, ZP_PTR0 + 1)
    a.emit(0xA9, 0x01)                                       # Pal 1
    a.emit(0xA6, 0x38)
    a.branch(0xF0, 'b_no_bg')
    a.emit(0x09, 0x20)
    a.label('b_no_bg')
    a.emit(0x8D, VH_TMP3 & 0xFF, VH_TMP3 >> 8)
    a.emit(0xA5, 0x32, 0x38, 0xE9, 24, 0x8D, VH_TMP4 & 0xFF, VH_TMP4 >> 8)
    a.emit(0xA5, 0x33, 0x38, 0xE9, 12, 0x8D, VH_TMP5 & 0xFF, VH_TMP5 >> 8)

    # Metasprite list: (tile_id, signed dx, signed dy), terminated by $FF
    a.emit(0xA0, 0x00)
    a.label('b_loop')
    a.emit(0xB1, ZP_PTR0)
    a.emit(0xC9, 0xFF)
    a.branch(0xF0, 'b_done')
    a.emit(0xA6, 0xB4)
    a.branch(0xF0, 'b_done')                                 # wrapped past $FC
    a.emit(0xE4, 0x37)
    a.branch(0xB0, 'b_done')
    a.emit(0x8D, VH_TMP0 & 0xFF, VH_TMP0 >> 8)               # tile_id
    a.emit(0xC8)                                             # -> dx
    a.emit(0xB1, ZP_PTR0)
    a.branch(0x30, 'b_dx_neg')
    a.emit(0x18, 0x6D, VH_TMP5 & 0xFF, VH_TMP5 >> 8)
    a.branch(0xB0, 'b_skip_y1')                              # >= 256
    a.branch(0x90, 'b_x_ok')
    a.label('b_dx_neg')
    a.emit(0x18, 0x6D, VH_TMP5 & 0xFF, VH_TMP5 >> 8)
    a.branch(0x90, 'b_skip_y1')                              # < 0
    a.label('b_x_ok')
    a.emit(0x8D, VH_TMP1 & 0xFF, VH_TMP1 >> 8)               # screen X
    a.emit(0xC8)                                             # -> dy
    a.emit(0xB1, ZP_PTR0)
    a.emit(0x18, 0x6D, VH_TMP4 & 0xFF, VH_TMP4 >> 8)
    a.emit(0xC9, 0xEF)
    a.branch(0xB0, 'b_skip_next')                            # offscreen Y
    a.emit(0xA6, 0xB4)
    a.emit(0x9D, 0x00, 0x02)                                 # Y (A still holds OAM Y)
    a.emit(0xC9, 0x8F)                                       # >= 143 (scanline 144+, bush top)?
    a.emit(0xA9, 0x01)                                       # Pal 1, in front of BG (preserves C)
    a.branch(0x90, 'b_attr_ok')                              # above bushes -> always in front of trees
    a.emit(0xAD, VH_TMP3 & 0xFF, VH_TMP3 >> 8)
    a.label('b_attr_ok')
    a.emit(0x9D, 0x02, 0x02)                                 # attr
    a.emit(0xAD, VH_TMP0 & 0xFF, VH_TMP0 >> 8, 0x9D, 0x01, 0x02)  # tile
    a.emit(0xAD, VH_TMP1 & 0xFF, VH_TMP1 >> 8, 0x9D, 0x03, 0x02)  # X
    a.emit(0x8A, 0x18, 0x69, 0x04, 0x85, 0xB4)
    a.emit(0xC8)
    a.branch(0xD0, 'b_loop')
    a.label('b_skip_y1')
    a.emit(0xC8)
    a.label('b_skip_next')
    a.emit(0xC8)
    a.branch(0xD0, 'b_loop')
    a.label('b_done')
    # Catch celebration ($14 = 1 hit, $15 = 2 hits): draw Z2 XP bag ($EE/$EF) in Barba's mouth (keeps Pal 1)
    a.emit(0xA5, 0x35)
    a.emit(0xC9, 0x14)
    a.branch(0x90, 'vh_clear_oam')
    a.emit(0xAD, VH_TMP5 & 0xFF, VH_TMP5 >> 8, 0x18, 0x69, 20)
    a.emit(0x8D, VH_TMP1 & 0xFF, VH_TMP1 >> 8)
    a.abs_ref(0x20, 'vh_draw_dead_pair')
    a.emit(0xA5, 0x35, 0xC9, 0x15)
    a.branch(0xD0, 'vh_clear_oam')
    a.emit(0xAD, VH_TMP1 & 0xFF, VH_TMP1 >> 8, 0x18, 0x69, 9)
    a.emit(0x8D, VH_TMP1 & 0xFF, VH_TMP1 >> 8)
    a.abs_ref(0x20, 'vh_draw_dead_pair')
    a.label('vh_clear_oam')
    a.emit(0xA6, 0xB4)
    a.branch(0xF0, 'vh_clr_done')
    a.emit(0xA9, 0xF4)
    a.label('vh_clr_loop')
    a.emit(0xE4, 0x37)                                       # CPX $37
    a.branch(0xB0, 'vh_clr_done')                            # BCS done (safe when $B4 >= $37)
    a.emit(0x9D, 0x00, 0x02, 0xE8)
    a.branch(0xD0, 'vh_clr_loop')
    a.label('vh_clr_done')
    a.emit(0x60)

    # Emit 8x16 Z2 XP bag ($EE top, $EF bottom) at (VH_TMP1, VH_TMP4 + 4 / +12)
    a.label('vh_draw_dead_pair')
    a.emit(0xAD, VH_TMP4 & 0xFF, VH_TMP4 >> 8, 0x18, 0x69, 4)
    a.emit(0xA0, 0xEE)
    a.abs_ref(0x20, 'vh_emit_bag_tile')
    a.emit(0xAD, VH_TMP4 & 0xFF, VH_TMP4 >> 8, 0x18, 0x69, 12)
    a.emit(0xA0, 0xEF)
    a.label('vh_emit_bag_tile')
    a.emit(0xC9, 0xEF)
    a.branch(0xB0, 'dead_rts')
    a.emit(0xA6, 0xB4)
    a.branch(0xF0, 'dead_rts')
    a.emit(0xE4, 0x37)
    a.branch(0xB0, 'dead_rts')
    a.emit(0x9D, 0x00, 0x02)                                 # Y (A still holds OAM Y)
    a.emit(0xC9, 0x8F)                                       # >= 143 (scanline 144+, bush top)?
    a.emit(0xA9, 0x01)                                       # Pal 1, in front of BG (preserves C)
    a.branch(0x90, 'dead_attr_ok')                           # above bushes -> always in front of trees
    a.emit(0xAD, VH_TMP3 & 0xFF, VH_TMP3 >> 8)
    a.label('dead_attr_ok')
    a.emit(0x9D, 0x02, 0x02)                                 # attr
    a.emit(0x98, 0x9D, 0x01, 0x02)                           # tile
    a.emit(0xAD, VH_TMP1 & 0xFF, VH_TMP1 >> 8, 0x9D, 0x03, 0x02)  # X
    a.emit(0x8A, 0x18, 0x69, 0x04, 0x85, 0xB4)
    a.label('dead_rts')
    a.emit(0x60)

    # ------------------------------------------------------------------
    # 6. Tables & Title Stream
    # ------------------------------------------------------------------
    a.label('tbl_col_x')
    a.emit(0, 8, 16)

    a.label('tbl_shake_y')
    a.emit(0, 3, 1, 4)

    a.label('tbl_villager_pals')
    a.emit(*art['villager_pals'])

    a.label('tbl_villager_r0_bank')
    a.emit(*art['villager_r0_banks'])

    a.label('tbl_villager_bank_idx')
    a.emit(*art['villager_bank_idx'])

    a.label('tbl_bank_start')
    a.emit(*art['bank_starts'])

    a.label('tbl_bank_count')
    a.emit(*art['bank_counts'])

    a.label('tbl_clay_pals')
    a.emit(*art['clay_pals'])

    a.label('tbl_villager_ptrs')
    for i in range(len(art['villager_maps'])):
        a.word_ref(f'vmap_{i}')
    for i, m in enumerate(art['villager_maps']):
        a.label(f'vmap_{i}')
        a.emit(*m)

    a.label('tbl_clay_ptrs')
    for i in range(len(art['clay_maps'])):
        a.word_ref(f'cmap_{i}')
    for i, m in enumerate(art['clay_maps']):
        a.label(f'cmap_{i}')
        a.emit(*m)

    a.label('tbl_link_ptrs')
    for i in range(len(art['link_maps'])):
        a.word_ref(f'lmap_{i}')
    for i, m in enumerate(art['link_maps']):
        a.label(f'lmap_{i}')
        a.emit(*m)

    a.label('tbl_barba_ptrs')
    for i in range(len(art['barba_maps'])):
        a.word_ref(f'bmap_{i}')
    for i, entries in enumerate(art['barba_maps']):
        a.label(f'bmap_{i}')
        for tid, dx, dy in entries:
            a.emit(tid, dx, dy)
        a.emit(0xFF)

    a.label('title_ppu_stream')
    a.emit(*build_title_ppu_stream())

    a.label('forest_ppu_stream')
    a.emit(*build_forest_ppu_stream())

    a.label('grass_ppu_stream')
    a.emit(*build_grass_ppu_stream())

    a.label('desert_ppu_stream')
    a.emit(*build_desert_ppu_stream())

    # Encounter scene tables (0=Forest, 1=Overworld Grass, 2=Desert)
    a.label('tbl_scene_bg_bank')
    a.emit(18, 32, 36)

    a.label('tbl_scene_sky')
    a.emit(0x0F, 0x21, 0x22)

    a.label('tbl_scene_ppu_ptrs')
    a.word_ref('forest_ppu_stream')
    a.word_ref('grass_ppu_stream')
    a.word_ref('desert_ppu_stream')

    a.label('tbl_scene_pal_full')
    a.word_ref('pal_full_forest')
    a.word_ref('pal_full_grass')
    a.word_ref('pal_full_desert')

    a.label('tbl_scene_pal_bg')
    a.word_ref('pal_bg_forest')
    a.word_ref('pal_bg_grass')
    a.word_ref('pal_bg_desert')

    a.label('tbl_scene_pal_restore')
    a.word_ref('pal_res_forest')
    a.word_ref('pal_res_grass')
    a.word_ref('pal_res_desert')

    from duck_art import SPRITE_PAL_BYTES
    scene_pals = [
        ('forest', 0x0F, bytes.fromhex('0f 17 07 08 0f 29 19 09 0f 0f 29 18 0f 0f 30 16')),
        ('grass',  0x21, bytes.fromhex('21 30 10 00 21 29 19 09 21 0f 29 18 21 0f 30 16')),
        ('desert', 0x22, bytes.fromhex('22 30 36 27 22 29 17 09 22 0f 29 18 22 0f 30 16')),
    ]
    for sname, sky, bg_pal in scene_pals:
        spr_pal = bytearray(SPRITE_PAL_BYTES)
        for i in (0, 4, 8, 12):
            spr_pal[i] = sky
        a.label(f'pal_full_{sname}')
        a.emit(0x3F, 0x00, 0x20, *bg_pal, *spr_pal, 0x00)
        a.label(f'pal_bg_{sname}')
        a.emit(0x3F, 0x00, 0x10, *bg_pal, 0x00)
        a.label(f'pal_res_{sname}')
        a.emit(0x3F, 0x10, 0x10, *spr_pal, 0x3F, 0x00, 0x10, *bg_pal, 0x00)

    code = a.finish()
    assert len(code) <= 8192, f'Bank 1 overflow: {len(code)} > 8192'
    bank1 = bytearray(b'\xFF' * 8192)
    bank1[0 : len(code)] = code
    return bytes(bank1), dict(a.labels)
