"""Build script for Friday the 13th: Barba Edition (roms/f13.nes -> build/f13_barba.nes)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nes import encode_tile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROM = ROOT / "roms/f13.nes"
SOURCE_SHA256 = "3e2bfc0097f5913b72dc4c77512e9596231359484423e3a5c26bea06c67b48e4"
OUT_ROM = ROOT / "build/f13_barba.nes"

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

    # 1. Rename counselor 0 ("GEORGE" -> "BARBA ") at $8AEB (PRG 0x0AEB)
    rom.put(
        HEADER_SIZE + 0x0AEB,
        bytes([0x10, 0x0E, 0x18, 0x1B, 0x10, 0x0E]),
        bytes([0x0B, 0x0A, 0x1B, 0x0B, 0x0A, 0xFF]),
        "counselor_0_name",
    )

    # 2. Counselor 0 sprite palettes (head/portrait pal 2 + body pal 3):
    #    0F = transparent, 16 = red scales, 27 = gold belly, 37 = ivory horns/eyes
    barba_pal = bytes([0x0F, 0x16, 0x27, 0x37, 0x0F, 0x16, 0x27, 0x37])
    orig_pal = bytes([0x0F, 0x26, 0x36, 0x0F, 0x0F, 0x14, 0x36, 0x0F])
    rom.put(0x0DD5D, orig_pal, barba_pal, "counselor_0_pal_table")
    rom.put(0x0E218, orig_pal, barba_pal, "counselor_0_ext_pal")

    # 2b. Make Barba (counselor 0) top-tier in all counselor stat tables + buff weapon damage
    rom.put(HEADER_SIZE + 0x3045, bytes([0x04]), bytes([0x05]), "barba_stat_b045")
    rom.put(HEADER_SIZE + 0x3268, bytes([0x04]), bytes([0x05]), "barba_stat_b268")
    rom.put(HEADER_SIZE + 0x3E94, bytes([0x03]), bytes([0x04]), "barba_stat_be94")
    rom.put(HEADER_SIZE + 0x4C7E, bytes([0x02]), bytes([0x05]), "barba_stat_cc7e")
    rom.put(
        HEADER_SIZE + 0x54D6,
        bytes([0x01, 0x04, 0x02, 0x05, 0x03, 0x01]),
        bytes([0x04, 0x08, 0x06, 0x0A, 0x08, 0x06]),
        "weapon_damage_boost",
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
    ]

    for bank4k in (0, 2):
        for tid, tile in ext_tiles:
            rom.put_chr_tile(bank4k, tid, tile, f"ext_bank{bank4k}_{tid:02X}")

    # HUD portrait ($60-$63 in CHR bank 6) and Map portrait ($00,$01,$10,$11 in CHR bank 6)
    portrait_tiles = split_grid(front_16, 2, 2)
    for idx, tid in enumerate((0x60, 0x61, 0x62, 0x63)):
        rom.put_chr_tile(6, tid, portrait_tiles[idx], f"hud_portrait_{tid:02X}")
    for idx, tid in enumerate((0x00, 0x01, 0x10, 0x11)):
        rom.put_chr_tile(6, tid, portrait_tiles[idx], f"map_portrait_{tid:02X}")

    OUT_ROM.parent.mkdir(parents=True, exist_ok=True)
    OUT_ROM.write_bytes(rom.data)
    print(f"Built {OUT_ROM} ({len(rom.data)} bytes)")
    return OUT_ROM


if __name__ == "__main__":
    build()
