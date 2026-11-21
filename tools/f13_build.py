"""Build script for Friday the 13th: Barba Edition (roms/f13.nes -> build/f13_barba.nes)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nes import encode_tile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROM = ROOT / "roms/f13.nes"
Z2_ROM = ROOT / "roms/z2.nes"
SOURCE_SHA256 = "3e2bfc0097f5913b72dc4c77512e9596231359484423e3a5c26bea06c67b48e4"
OUT_ROM = ROOT / "build/f13_barba.nes"
PLAY_ROM = ROOT / "play/f13-barba.nes"

HEADER_SIZE = 16
PRG_SIZE = 0x8000
CHR_OFFSET = HEADER_SIZE + PRG_SIZE


class GuardedRom:
    """Applies guarded byte patches to a copy of the source ROM."""

    def __init__(self, source: bytes) -> None:
        self.data = bytearray(source)
        self.touched: set[int] = set()

    def put(self, offset: int, expected: bytes, replacement: bytes, label: str = "") -> None:
        if len(expected) != len(replacement):
            raise ValueError(f"{label}: length mismatch {len(expected)} != {len(replacement)}")
        actual = bytes(self.data[offset : offset + len(expected)])
        if actual != expected:
            raise ValueError(
                f"{label} @ 0x{offset:05X}: expected {expected.hex(' ')}, got {actual.hex(' ')}"
            )
        for i in range(offset, offset + len(replacement)):
            if i in self.touched:
                raise ValueError(f"{label}: overlapping write at 0x{i:05X}")
            self.touched.add(i)
        self.data[offset : offset + len(replacement)] = replacement

    def put_chr_tile(self, bank4k: int, tile_id: int, rows: list[str], label: str = "") -> None:
        off = CHR_OFFSET + bank4k * 4096 + tile_id * 16
        encoded = encode_tile(rows)
        # CHR tiles are replaced unconditionally after verifying bounds
        for i in range(off, off + 16):
            if i in self.touched:
                raise ValueError(f"{label}: overlapping CHR write at 0x{i:05X}")
            self.touched.add(i)
        self.data[off : off + 16] = encoded


def flip_h(rows: list[str]) -> list[str]:
    return [row[::-1] for row in rows]


def split_grid(rows: list[str], cols: int, tile_rows: int) -> list[list[str]]:
    """Split a (8*tile_rows) x (8*cols) grid into row-major 8x8 tiles."""
    tiles = []
    for ty in range(tile_rows):
        for tx in range(cols):
            tiles.append([rows[ty * 8 + y][tx * 8 : (tx + 1) * 8] for y in range(8)])
    return tiles


def shift_rows(rows: list[str], dy: int = 0, dx: int = 0) -> list[str]:
    h, w = len(rows), len(rows[0])
    out = []
    for y in range(h):
        sy = y - dy
        if 0 <= sy < h:
            row = []
            for x in range(w):
                sx = x - dx
                row.append(rows[sy][sx] if 0 <= sx < w else "0")
            out.append("".join(row))
        else:
            out.append("0" * w)
    return out


def build() -> Path:
    raw = SOURCE_ROM.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise SystemExit(f"Source ROM SHA-256 mismatch: {digest}")

    rom = GuardedRom(raw)

    # 1. Counselor names at $8AEB (PRG 0x0AEB, 6 bytes each, 0xFF = space):
    #    0=GEORGE->BARBA, 1=MARK->BERBA, 2=PAUL->BORBA, 3=LAURA (kept), 4=DEBBIE (kept), 5=CRISSY->BURBA
    rom.put(
        HEADER_SIZE + 0x0AEB,
        bytes([
            0x10, 0x0E, 0x18, 0x1B, 0x10, 0x0E,  # GEORGE
            0x16, 0x0A, 0x1B, 0x14, 0xFF, 0xFF,  # MARK
            0x19, 0x0A, 0x1E, 0x15, 0xFF, 0xFF,  # PAUL
        ]),
        bytes([
            0x0B, 0x0A, 0x1B, 0x0B, 0x0A, 0xFF,  # BARBA
            0x0B, 0x0E, 0x1B, 0x0B, 0x0A, 0xFF,  # BERBA
            0x0B, 0x18, 0x1B, 0x0B, 0x0A, 0xFF,  # BORBA
        ]),
        "counselor_012_names",
    )
    rom.put(
        HEADER_SIZE + 0x0B09,
        bytes([0x0C, 0x1B, 0x12, 0x1C, 0x1C, 0x22]),  # CRISSY
        bytes([0x0B, 0x1E, 0x1B, 0x0B, 0x0A, 0xFF]),  # BURBA
        "counselor_5_name",
    )

    # 1b. Rename "JASON" -> "LINK " at $8CAC (PRG 0x0CAC)
    rom.put(
        HEADER_SIZE + 0x0CAC,
        bytes([0x13, 0x0A, 0x1C, 0x18, 0x17]),
        bytes([0x15, 0x12, 0x17, 0x14, 0xFF]),
        "jason_to_link_name",
    )

    # 2. Counselor sprite palettes (CHR table 0x0DD5D = 6x8B, and 0x0E218 for counselor 0):
    #    Keep 3 (Laura) and 4 (Debbie) untouched; give 0,1,2,5 distinct Barba palettes!
    barba_red  = bytes([0x0F, 0x16, 0x27, 0x37, 0x0F, 0x16, 0x27, 0x37])
    barba_pyro = bytes([0x0F, 0x26, 0x28, 0x37, 0x0F, 0x26, 0x28, 0x37])
    barba_wyrm = bytes([0x0F, 0x1A, 0x27, 0x37, 0x0F, 0x1A, 0x27, 0x37])
    barba_sky  = bytes([0x0F, 0x11, 0x21, 0x37, 0x0F, 0x11, 0x21, 0x37])

    orig_012 = bytes([
        0x0F, 0x26, 0x36, 0x0F, 0x0F, 0x14, 0x36, 0x0F,  # George
        0x0F, 0x27, 0x36, 0x0F, 0x0F, 0x20, 0x36, 0x0F,  # Mark
        0x0F, 0x07, 0x17, 0x0F, 0x0F, 0x21, 0x17, 0x0F,  # Paul
    ])
    rom.put(0x0DD5D, orig_012, barba_red + barba_pyro + barba_wyrm, "counselor_012_pal_table")
    rom.put(
        0x0DD5D + 5 * 8,
        bytes([0x0F, 0x27, 0x35, 0x0F, 0x0F, 0x23, 0x35, 0x0F]),  # Crissy
        barba_sky,
        "counselor_5_pal_table",
    )
    rom.put(
        0x0E218,
        bytes([0x0F, 0x26, 0x36, 0x0F, 0x0F, 0x14, 0x36, 0x0F]),
        barba_red,
        "counselor_0_ext_pal",
    )

    # 2b. Helper IsFemaleHuman at $BB4B (PRG 0x3B4B, 15B in 16B zero-pad):
    #     Returns C=1 if $0507 in {3, 4} (Laura/Debbie), C=0 if Barba {0, 1, 2, 5}.
    rom.put(
        HEADER_SIZE + 0x3B4B,
        bytes(15),
        bytes([
            0xAD, 0x07, 0x05,  # LDA $0507
            0xC9, 0x03,        # CMP #$03 (Laura)
            0xF0, 0x06,        # BEQ @yes
            0xC9, 0x04,        # CMP #$04 (Debbie)
            0xF0, 0x02,        # BEQ @yes
            0x18, 0x60,        # CLC; RTS
            0x38, 0x60,        # SEC; RTS
        ]),
        "is_female_human_helper",
    )
    # Use Barba exterior tiles ($45-$64) for 0,1,2,5 and keep female tiles for 3,4 (Laura/Debbie)
    rom.put(
        HEADER_SIZE + 0x3AF5,
        bytes([0xAD, 0x07, 0x05, 0xC9, 0x03, 0xB0, 0x0D]),
        bytes([0x20, 0x4B, 0xBB, 0xEA, 0xEA, 0xB0, 0x0D]),
        "exterior_sprite_barba_check",
    )
    # Give all 4 Barbas (0,1,2,5) the high jump (LDY #$0C) and keep Laura/Debbie (3,4) low (LDY #$00)
    rom.put(
        HEADER_SIZE + 0x34FE,
        bytes([0xAD, 0x07, 0x05, 0xC9, 0x01, 0xF0, 0x06, 0xC9, 0x05, 0xF0, 0x02, 0xA0, 0x00]),
        bytes([0xA0, 0x00, 0x20, 0x4B, 0xBB, 0xB0, 0x02, 0xA0, 0x0C, 0xEA, 0xEA, 0xEA, 0xEA]),
        "jump_height_barba_check",
    )
    # HUD portrait base tiles at $8B42 (PRG 0x0B42): 0,1,2,5 -> $60 (Barba), 3 -> $6C (Laura), 4 -> $F8 (Debbie)
    rom.put(
        HEADER_SIZE + 0x0B42,
        bytes([0x60, 0x64, 0x68, 0x6C, 0xF8, 0xFC]),
        bytes([0x60, 0x60, 0x60, 0x6C, 0xF8, 0x60]),
        "hud_portrait_barba_0125",
    )

    # 2c. Buff all 4 Barbas (0,1,2,5) in counselor stat tables; keep Laura (3) & Debbie (4) slow/weak!
    rom.put(
        HEADER_SIZE + 0x3045,
        bytes([0x04, 0x05, 0x04, 0x04, 0x04, 0x04]),
        bytes([0x06, 0x06, 0x06, 0x03, 0x03, 0x06]),
        "barba_stat_b045",
    )
    rom.put(
        HEADER_SIZE + 0x3268,
        bytes([0x04, 0x05, 0x04, 0x05, 0x04, 0x05]),
        bytes([0x06, 0x06, 0x06, 0x03, 0x03, 0x06]),
        "barba_stat_b268",
    )
    rom.put(
        HEADER_SIZE + 0x3E94,
        bytes([0x03, 0x04, 0x03, 0x04, 0x03, 0x04]),
        bytes([0x05, 0x05, 0x05, 0x02, 0x02, 0x05]),
        "barba_stat_be94",
    )
    rom.put(
        HEADER_SIZE + 0x4C7E,
        bytes([0x02, 0x03, 0x04, 0x05, 0x04, 0x03]),
        bytes([0x06, 0x06, 0x06, 0x02, 0x02, 0x06]),
        "barba_stat_cc7e",
    )
    # Straight horizontal fire breath for weapon 0 (Rock -> Fireball) at $C28E (PRG 0x428E, 3B; frees $C291-$C29E)
    rom.put(
        HEADER_SIZE + 0x428E,
        bytes([0x08, 0x34, 0x04]),
        bytes([0x80, 0x00, 0x00]),
        "fire_breath_straight_arc",
    )
    rom.put(
        HEADER_SIZE + 0x54D6,
        bytes([0x01, 0x04, 0x02, 0x05, 0x03, 0x01]),
        bytes([0x06, 0x0A, 0x08, 0x0C, 0x0A, 0x08]),
        "weapon_damage_boost",
    )

    # 2d. Liquidy splat SFX when Laura (3) or Debbie (4) falls into a pit ($B2B5 -> $C291)
    #     Channel header at $8911 (7B of 11B FF-pad): Noise @ $A34A, Pulse2 @ $BC0C
    rom.put(
        HEADER_SIZE + 0x0911,
        bytes([0xFF] * 7),
        bytes([0x07, 0x4A, 0xA3, 0x05, 0x0C, 0xBC, 0xFF]),
        "splat_sfx_header",
    )
    rom.put(
        HEADER_SIZE + 0x234A,
        bytes(10),
        bytes([0xF0, 0x04, 0x82, 0x0F, 0x0D, 0x0E, 0x0C, 0x0F, 0x0E, 0xFF]),
        "splat_sfx_noise",
    )
    rom.put(
        HEADER_SIZE + 0x3C0C,
        bytes(8),
        bytes([0xF0, 0x04, 0x82, 0x28, 0x34, 0x42, 0x50, 0xFF]),
        "splat_sfx_pulse2",
    )
    # Point SFX $0F ($FAFF in $FAE1 pointer table) to $8911
    rom.put(
        HEADER_SIZE + 0x7AFF,
        bytes([0x36, 0xFF]),
        bytes([0x11, 0x89]),
        "splat_sfx_0F_ptr",
    )
    # PitFallSplat at $C291 (14B in freed rock-arc space): INC $056C; if Laura/Debbie play SFX $0F
    rom.put(
        HEADER_SIZE + 0x4291,
        bytes([0x24, 0x04, 0x14, 0x04, 0x18, 0x04, 0x28, 0x08, 0x38, 0x08, 0x48, 0x80, 0x68, 0x00]),
        bytes([
            0xEE, 0x6C, 0x05,  # INC $056C
            0x20, 0x4B, 0xBB,  # JSR $BB4B (IsFemaleHuman)
            0x90, 0x05,        # BCC @done
            0xA9, 0x0F,        # LDA #$0F (liquidy splat!)
            0x4C, 0x75, 0xF6,  # JMP $F675 (queue SFX)
            0x60,              # RTS
        ]),
        "pit_fall_splat_hook",
    )
    rom.put(
        HEADER_SIZE + 0x32B5,
        bytes([0xEE, 0x6C, 0x05]),
        bytes([0x20, 0x91, 0xC2]),
        "pit_fall_b2b5_hook",
    )

    # 3. Stock Barba graphics from assets/barba.json
    barba_art = json.loads((ROOT / "assets/barba.json").read_text(encoding="utf-8"))
    # body is 16x32 facing left; flip horizontally to face right (attr & $40 == 0)
    body_r = flip_h(barba_art["body"])
    front_16 = barba_art["front"]

    # Exterior player sprite: 16x32 = 2x4 tiles (head 16x8, body 16x24)
    # Note: F13 draws head at Y and body at Y+7..Y+23 (1px overlap at row 7/8)
    head_stand = split_grid(body_r[0:8], 2, 1)
    body_idle = split_grid(body_r[8:32], 2, 3)
    body_walk1 = split_grid(shift_rows(body_r[8:32], dy=1), 2, 3)
    body_walk2 = split_grid(shift_rows(body_r[8:32], dy=-1), 2, 3)
    head_jump = split_grid(shift_rows(body_r[0:8], dy=-1), 2, 1)
    body_jump = split_grid(shift_rows(body_r[8:32], dy=-1), 2, 3)
    # Crouch: 16x16 body (bottom coil + torso)
    body_crouch = split_grid(body_r[16:32], 2, 2)

    ext_tiles: list[tuple[int, list[str]]] = [
        # Head (stand/walk/crouch)
        (0x45, head_stand[0]), (0x46, head_stand[1]),
        # Walk 1 body
        (0x47, body_walk1[0]), (0x48, body_walk1[1]),
        (0x49, body_walk1[2]), (0x4A, body_walk1[3]),
        (0x4B, body_walk1[4]), (0x4C, body_walk1[5]),
        # Idle body
        (0x4D, body_idle[0]), (0x4E, body_idle[1]),
        (0x4F, body_idle[2]), (0x50, body_idle[3]),
        (0x51, body_idle[4]), (0x52, body_idle[5]),
        # Walk 2 body
        (0x53, body_walk2[0]), (0x54, body_walk2[1]),
        (0x55, body_walk2[2]), (0x56, body_walk2[3]),
        (0x57, body_walk2[4]), (0x58, body_walk2[5]),
        # Jump head + body
        (0x59, head_jump[0]), (0x5A, head_jump[1]),
        (0x5B, body_jump[0]), (0x5C, body_jump[1]),
        (0x5D, body_jump[2]), (0x5E, body_jump[3]),
        (0x5F, body_jump[4]), (0x60, body_jump[5]),
        # Crouch body
        (0x61, body_crouch[0]), (0x62, body_crouch[1]),
        (0x63, body_crouch[2]), (0x64, body_crouch[3]),
        # Fireball replacing Rock ($15)
        (0x15, [
            "00022200",
            "00233320",
            "02311332",
            "23111132",
            "23111132",
            "02311332",
            "00233320",
            "00022200",
        ]),
        # Thin layer of noodles ($71, unused tile in Bank 0)
        (0x71, [
            "00000000",
            "00000000",
            "00000000",
            "00000000",
            "00000000",
            "22322322",
            "33233233",
            "22322322",
        ]),
    ]

    # 3b. Link as Jason (exterior tiles extracted from roms/z2.nes CHR0)
    z2_raw = Z2_ROM.read_bytes()
    z2_chr0 = z2_raw[0x20010 : 0x20010 + 4096]

    def z2_tile(tid: int) -> list[str]:
        off = tid * 16
        rows = []
        for y in range(8):
            p0, p1 = z2_chr0[off + y], z2_chr0[off + y + 8]
            rows.append("".join(str(((p0 >> x) & 1) | (((p1 >> x) & 1) << 1)) for x in range(7, -1, -1)))
        return rows

    link_ext_tiles: list[tuple[int, list[str]]] = [
        # Stand Link (head/cap/torso/legs) -> Jason exterior slots
        (0xCA, z2_tile(0x00)), (0xCB, z2_tile(0x02)),
        (0xCC, z2_tile(0x08)), (0xCD, z2_tile(0x0A)),
        (0xEA, z2_tile(0x01)), (0xEB, z2_tile(0x03)),
        (0xEC, z2_tile(0x09)), (0xED, z2_tile(0x0B)),
        (0xEE, z2_tile(0x04)), (0xEF, z2_tile(0x06)),
        (0xF0, z2_tile(0x0C)), (0xF1, z2_tile(0x0E)),
    ]
    ext_tiles.extend(link_ext_tiles)

    for bank4k in (0, 2):
        for tid, tile in ext_tiles:
            rom.put_chr_tile(bank4k, tid, tile, f"ext_bank{bank4k}_{tid:02X}")

    # 3c. Cabin-fight Link replacing Jason's hockey mask (CHR Bank 4 $04-$05, $14-$15, $24-$25, $34-$35)
    cabin_link_head = [
        "0000001111000000",
        "0000012222100000",
        "0000122222210000",
        "0001222222221000",
        "0012222222222100",
        "0011111111111100",
        "0013313333133100",
        "0013113333113100",
        "0013333333333100",
        "0001333113331000",
        "0000133333310000",
        "0000012222100000",
        "0000122222210000",
        "0001222112221000",
        "0001222222221000",
        "0001222222221000",
        "0012222222222100",
        "0012222222222100",
        "0012222222222100",
        "0012222222222100",
        "0001222222221000",
        "0001222222221000",
        "0001222222221000",
        "0001222222221000",
        "0000122222210000",
        "0000122222210000",
        "0000122222210000",
        "0000122222210000",
        "0000000000000000",
        "0000000000000000",
        "0000000000000000",
        "0000000000000000",
    ]
    cabin_tiles = split_grid(cabin_link_head, 2, 4)
    for row_idx, base_tid in enumerate((0x04, 0x14, 0x24, 0x34)):
        rom.put_chr_tile(4, base_tid, cabin_tiles[row_idx * 2], f"cabin_link_{base_tid:02X}")
        rom.put_chr_tile(4, base_tid + 1, cabin_tiles[row_idx * 2 + 1], f"cabin_link_{base_tid+1:02X}")

    # HUD portrait ($60-$63 in CHR bank 6) and Map portrait ($00,$01,$10,$11 in CHR bank 6)
    portrait_tiles = split_grid(front_16, 2, 2)
    for idx, tid in enumerate((0x60, 0x61, 0x62, 0x63)):
        rom.put_chr_tile(6, tid, portrait_tiles[idx], f"hud_portrait_{tid:02X}")
    for idx, tid in enumerate((0x00, 0x01, 0x10, 0x11)):
        rom.put_chr_tile(6, tid, portrait_tiles[idx], f"map_portrait_{tid:02X}")

    OUT_ROM.parent.mkdir(parents=True, exist_ok=True)
    OUT_ROM.write_bytes(rom.data)
    PLAY_ROM.parent.mkdir(parents=True, exist_ok=True)
    PLAY_ROM.write_bytes(rom.data)
    print(f"Built {OUT_ROM} and {PLAY_ROM} ({len(rom.data)} bytes)")
    return OUT_ROM


if __name__ == "__main__":
    build()
