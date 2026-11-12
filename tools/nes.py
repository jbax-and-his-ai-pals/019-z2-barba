"""Small, dependency-free iNES/2bpp helpers used by the build and asset tools."""
from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path

SOURCE_SHA256 = "ad8c0fbcf092bf84b48e69fd3964eea4ed91bfe62abc352943d537979782680c"
HEADER_SIZE = 16
PRG_SIZE = 0x20000
CHR_OFFSET = HEADER_SIZE + PRG_SIZE


def load_source(path: Path) -> bytes:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError("Unsupported source ROM. See docs/BUILD.md for the required SHA-256.")
    return data


def prg_offset(bank: int, address: int) -> int:
    base = 0xC000 if bank == 7 else 0x8000
    if not 0 <= bank <= 7 or not base <= address < base + 0x4000:
        raise ValueError(f"Invalid PRG location: bank {bank}, address {address:04X}")
    return HEADER_SIZE + bank * 0x4000 + address - base


def decode_tile(data: bytes) -> list[list[int]]:
    if len(data) != 16:
        raise ValueError("An NES tile is 16 bytes")
    return [[((data[y] >> (7-x)) & 1) | (((data[y+8] >> (7-x)) & 1) << 1)
             for x in range(8)] for y in range(8)]


def encode_tile(rows: list[str]) -> bytes:
    if len(rows) != 8 or any(len(row) != 8 or set(row) - set("0123") for row in rows):
        raise ValueError("Tiles require eight rows of eight palette indices (0..3)")
    return bytes(sum(((int(rows[y][x]) >> plane) & 1) << (7-x) for x in range(8))
                 for plane in range(2) for y in range(8))


def write_png(path: Path, pixels: list[list[tuple[int, int, int]]], scale: int = 1) -> None:
    width, height = len(pixels[0]) * scale, len(pixels) * scale
    raw = b"".join((b"\0" + b"".join(bytes(pixel) * scale for pixel in row)) * scale
                   for row in pixels)
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
