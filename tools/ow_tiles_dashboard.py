"""Extract overworld environment tile animations for the local dev dashboard.

Builds `web/local_ow_tiles_data.js` (never published to GitHub Pages) with:
  - All animated overworld environment tile types from the ROM:
      * Water ($6E) — Settled (R0 CHR bankswitch + OAM sun-glint crest)
      * Swamp ($6F) — Settled (R0 CHR bankswitch + OAM marsh bubble)
      * Desert ($6C) — Settled (OAM sand sparkle)
      * Mountain / Lava ($64-$67) — Settled ambience (OAM rising ember)
      * Graveyard ($70/$71) — Settled ambience (OAM cross wisp)
      * Forest ($68-$6B) — Iterating (CHR 31 R1 $A4-$AF + candidate possibilities)
      * Grass ($6D) — Iterating (CHR 31 R1 $9E-$A3 + candidate possibilities)
  - Live 8x8 2bpp pixel grids extracted from `build/barba.nes` (or synthesized
    deterministically from `roms/z2.nes` when `build/barba.nes` is absent).
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path
from typing import Any

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from nes import CHR_OFFSET, decode_tile, encode_tile, load_source  # noqa: E402

ROOT = _TOOLS_DIR.parent

# Standard 64-color NES 2C02 RGB palette (matches tools/duck_dashboard.py).
NES_PALETTE: list[list[int]] = [
    [84, 84, 84], [0, 30, 116], [8, 16, 144], [48, 0, 136],
    [68, 0, 100], [92, 0, 48], [84, 4, 0], [60, 24, 0],
    [32, 42, 0], [8, 58, 0], [0, 64, 0], [0, 60, 0],
    [0, 50, 60], [0, 0, 0], [0, 0, 0], [0, 0, 0],
    [152, 150, 152], [8, 76, 196], [48, 50, 236], [92, 30, 228],
    [136, 20, 176], [160, 20, 100], [152, 34, 32], [120, 60, 0],
    [84, 90, 0], [40, 114, 0], [8, 124, 0], [0, 118, 40],
    [0, 102, 120], [0, 0, 0], [0, 0, 0], [0, 0, 0],
    [236, 238, 236], [76, 154, 236], [120, 124, 236], [176, 98, 236],
    [228, 84, 236], [236, 88, 180], [236, 106, 100], [212, 136, 32],
    [160, 170, 0], [116, 196, 0], [76, 208, 32], [56, 204, 108],
    [56, 180, 204], [60, 60, 60], [0, 0, 0], [0, 0, 0],
    [236, 238, 236], [168, 204, 236], [188, 188, 236], [212, 178, 236],
    [236, 174, 236], [236, 174, 212], [236, 180, 176], [228, 196, 144],
    [204, 210, 120], [180, 222, 120], [168, 226, 144], [152, 226, 180],
    [160, 214, 228], [160, 162, 160], [0, 0, 0], [0, 0, 0],
]

# Authentic Zelda II Overworld BG & Sprite palettes (index 0..3).
OVERWORLD_PALETTES: dict[str, dict[str, Any]] = {
    "west_foliage": {"label": "West Hyrule Foliage (BG0)", "colors": [0x36, 0x0F, 0x2A, 0x1A]},
    "east_foliage": {"label": "East Hyrule Foliage (BG0)", "colors": [0x36, 0x0F, 0x29, 0x19]},
    "water_desert": {"label": "Water & Desert (BG3)", "colors": [0x36, 0x30, 0x27, 0x12]},
    "mountain_grave": {"label": "Mountain & Graveyard (BG1)", "colors": [0x36, 0x0F, 0x30, 0x17]},
    "saria_swamp": {"label": "Swamp / Foul Water (BG0)", "colors": [0x36, 0x0F, 0x2A, 0x1A]},
    "spr0": {"label": "Overworld Sprite Pal 0 (Glint/Ember/Bubble)", "colors": [0x36, 0x16, 0x27, 0x30]},
    "spr2": {"label": "Overworld Sprite Pal 2 (Water Crest)", "colors": [0x36, 0x30, 0x21, 0x0F]},
}


def _ror8(byte: int, shift: int) -> int:
    s = shift % 8
    return ((byte >> s) | (byte << (8 - s))) & 0xFF


def _shift_tile_rows(tile_bytes: bytes, row_shifts: dict[int, int], *, wrap: bool) -> bytes:
    buf = bytearray(tile_bytes)
    for row, shift in row_shifts.items():
        for plane in (0, 8):
            val = buf[plane + row]
            if wrap:
                buf[plane + row] = _ror8(val, shift)
            else:
                buf[plane + row] = ((val >> shift) if shift > 0 else (val << -shift)) & 0xFF
    return bytes(buf)


def _tile_to_flat(tile_bytes: bytes) -> list[int]:
    grid = decode_tile(tile_bytes)
    return [px for row in grid for px in row]


def _flat_to_rows(flat: list[int]) -> list[list[int]]:
    return [flat[r * 8:(r + 1) * 8] for r in range(8)]


def _rows_to_flat(rows: list[list[int]]) -> list[int]:
    return [px for row in rows for px in row]


def _parse_chr_offsets_from_ines(rom: bytes) -> tuple[int, int]:
    """Return (prg_size, chr_offset) from an iNES / NES 2.0 header."""
    if len(rom) < 16 or rom[:4] != b"NES\x1a":
        raise ValueError("Not a valid iNES/NES 2.0 ROM")
    prg_lsb = rom[4]
    prg_msb = rom[9] & 0x0F
    prg_banks = prg_lsb | (prg_msb << 8)
    prg_size = prg_banks * 16384
    return prg_size, 16 + prg_size


def _load_overworld_chr_data() -> dict[str, Any]:
    """Load base CHR 30/31, extended R0 banks 230/232/234/236, and R1 variants."""
    barba_path = ROOT / "build" / "barba.nes"
    z2_path = ROOT / "roms" / "z2.nes"

    if barba_path.exists():
        rom = barba_path.read_bytes()
        _, chr_off = _parse_chr_offsets_from_ines(rom)
        ow_r0 = rom[chr_off + 31 * 4096:chr_off + 31 * 4096 + 2048]
        ow_r1 = rom[chr_off + 31 * 4096 + 2048:chr_off + 32 * 4096]
        # Extended CHR starts at 256 KB into CHR (bank 128 * 1KB = 131072).
        ext_banks: dict[int, bytes] = {124: ow_r0}
        for b in (230, 232, 234, 236):
            off = chr_off + b * 1024
            ext_banks[b] = rom[off:off + 2048]
        source_label = "build/barba.nes"
        return {
            "source": source_label,
            "ow_r0": ow_r0,
            "ow_r1": ow_r1,
            "ext_r0": ext_banks,
        }

    if not z2_path.exists():
        raise FileNotFoundError("Neither build/barba.nes nor roms/z2.nes found")

    src = load_source(z2_path)
    # In vanilla z2.nes, overworld tiles live in CHR bank 16+17.
    ow_r0 = src[CHR_OFFSET + 16 * 4096:CHR_OFFSET + 16 * 4096 + 2048]
    ow_r1 = bytearray(src[CHR_OFFSET + 17 * 4096:CHR_OFFSET + 17 * 4096 + 2048])

    # Synthesize the exact build.py extended water/swamp R0 banks.
    ext_banks = {124: ow_r0}
    for slot, (top_shift, bot_shift) in enumerate(((1, -1), (2, -2), (-1, 1), (-2, 2))):
        variant = bytearray(ow_r0)
        for tid in (0x6E, 0x6F):
            t_off = tid * 16
            for row in range(8):
                shift = top_shift if row < 4 else bot_shift
                variant[t_off + row] = _ror8(variant[t_off + row], shift)
                variant[t_off + 8 + row] = _ror8(variant[t_off + 8 + row], shift)
        ext_banks[230 + slot * 2] = bytes(variant)

    # Synthesize the exact build.py CHR 31 R1 grass & forest variants ($9E..$AF).
    grass_variants = (
        {0: 1, 1: 1},
        {0: -1, 1: -1},
        {5: 1, 6: 1},
        {5: -1, 6: -1},
        {0: 1, 1: 1, 2: 1, 5: 1, 6: 1},
        {0: 1, 1: 1, 5: -1, 6: -1},
    )
    for idx, rs in enumerate(grass_variants):
        tid = 0x9E + idx
        t_src = ow_r0[0x6D * 16:0x6E * 16]
        ow_r1[(tid - 0x80) * 16:(tid - 0x7F) * 16] = _shift_tile_rows(t_src, rs, wrap=True)

    forest_tl_variants = (
        {0: 1, 1: 1},
        {1: -1, 2: -1},
        {4: -1, 6: -1},
        {4: 1, 6: 1},
        {0: 1, 1: 1, 4: 1},
        {2: -1, 3: -1, 6: -1},
    )
    for idx, rs in enumerate(forest_tl_variants):
        tid = 0xA4 + idx
        t_src = ow_r0[0x68 * 16:0x69 * 16]
        ow_r1[(tid - 0x80) * 16:(tid - 0x7F) * 16] = _shift_tile_rows(t_src, rs, wrap=False)

    return {
        "source": "roms/z2.nes (recipe)",
        "ow_r0": ow_r0,
        "ow_r1": bytes(ow_r1),
        "ext_r0": ext_banks,
    }


def _parse_foliage_sequences(path: Path) -> list[list[int]]:
    """Parse FolSeqTiles 10x4 table from src/ow_foliage.inc."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"FolSeqTiles:\s*\n((?:\s*\.byte\s+[^\n]+\n)+)", text)
    if not m:
        return []
    seqs: list[list[int]] = []
    for line in m.group(1).splitlines():
        vals = [int(x, 16) for x in re.findall(r"\$([0-9A-Fa-f]{2})", line.split(";")[0])]
        if vals:
            seqs.append(vals)
    return seqs


def _encode_8x16_chars(rows: list[str]) -> list[int]:
    """Encode top 8x8 of a build.py _chr_8x16 particle glyph into 64 palette indices."""
    cmap = {".": 0, "o": 1, "+": 2, "#": 3}
    out: list[int] = []
    for r in range(8):
        for ch in rows[r]:
            out.append(cmap[ch])
    return out


def _build_grass_possibilities(base_flat: list[int], rom_variants: dict[str, list[int]]) -> list[dict[str, Any]]:
    """Build current ROM + candidate iteration possibilities for Grass ($6D)."""
    base_rows = _flat_to_rows(base_flat)

    def _shift_rows_no_wrap(row_shifts: dict[int, int]) -> list[int]:
        rows = [list(r) for r in base_rows]
        for r_idx, sh in row_shifts.items():
            src = base_rows[r_idx]
            dst = [2] * 8  # fill vacated edge with grass base color 2 ($2A)
            for x in range(8):
                nx = x + sh
                if 0 <= nx < 8:
                    dst[nx] = src[x]
            rows[r_idx] = dst
        return _rows_to_flat(rows)

    def _recolor_pixels(edits: dict[tuple[int, int], int]) -> list[int]:
        rows = [list(r) for r in base_rows]
        for (r_idx, x_idx), val in edits.items():
            rows[r_idx][x_idx] = val
        return _rows_to_flat(rows)

    # Possibility 1: Non-wrapping tuft lean (keeps edge blades from wrapping across tile seams)
    nowrap_r = _shift_rows_no_wrap({0: 1, 1: 1})
    nowrap_l = _shift_rows_no_wrap({0: -1, 1: -1})
    nowrap_low_r = _shift_rows_no_wrap({5: 1, 6: 1})

    # Possibility 2: Directional wind gust (coherent wave across meadow)
    gust_1 = _shift_rows_no_wrap({0: 1, 1: 1, 2: 1})
    gust_2 = _shift_rows_no_wrap({0: 1, 1: 1, 2: 1, 5: 1, 6: 1})

    # Possibility 3: Blade shade shimmer / wildflower glint (zero silhouette jitter)
    shimmer_a = _recolor_pixels({(0, 0): 2, (1, 0): 3, (2, 2): 1, (5, 3): 2})
    shimmer_b = _recolor_pixels({(0, 4): 2, (1, 4): 2, (2, 6): 2, (6, 1): 1})
    shimmer_c = _recolor_pixels({(2, 2): 0, (5, 5): 0})  # tiny tan/sun fleck

    # Possibility 4: Minimal 2-frame upper tip nod
    tip_nod = _recolor_pixels({(0, 0): 2, (0, 1): 3, (0, 4): 2, (0, 5): 3})

    return [
        {
            "id": "grass_rom_current",
            "name": "Current ROM (Nametable Swap $9E-$A3)",
            "status": "current",
            "mechanism": "CHR 31 R1 nametable tile-swap (6 async slots, 12-43f/step, wrap=True)",
            "pros": "Already wired in ow_foliage.inc; async meadow breeze",
            "notes": "Uses _ror8 wrap=True, which can wrap edge blades across tile seams.",
            "mode": "async_meadow",
            "frames_per_step": 18,
            "tiles": {
                "base": base_flat,
                **rom_variants,
            },
            "sequences": [
                ["$9E", "$9F", "$9E", "base"],
                ["$A0", "$A1", "base"],
                ["$A2", "$9E", "$A3", "base"],
                ["$9F", "base"],
            ],
        },
        {
            "id": "grass_nowrap_lean",
            "name": "Option A: Non-Wrap Tuft Lean",
            "status": "candidate",
            "mechanism": "CHR 31 R1 nametable swap with wrap=False (fills vacated edge with base green)",
            "pros": "Eliminates 8px tile-boundary wrap artifacts while keeping breeze feel",
            "notes": "Drop-in replacement in tools/build.py (wrap=False + edge fill).",
            "mode": "async_meadow",
            "frames_per_step": 18,
            "tiles": {
                "base": base_flat,
                "lean_r": nowrap_r,
                "lean_l": nowrap_l,
                "low_r": nowrap_low_r,
            },
            "sequences": [
                ["lean_r", "base", "lean_l", "base"],
                ["low_r", "base"],
                ["lean_r", "low_r", "base"],
            ],
        },
        {
            "id": "grass_wind_gust",
            "name": "Option B: Directional Wind Gust Sweep",
            "status": "candidate",
            "mechanism": "Coherent left-to-right phase wave across meadow columns",
            "pros": "Reads clearly as wind sweeping across Hyrule fields",
            "notes": "Can run via R0 bankswitch or column-phased nametable swap.",
            "mode": "wave_meadow",
            "frames_per_step": 10,
            "tiles": {
                "base": base_flat,
                "gust_1": gust_1,
                "gust_2": gust_2,
            },
            "sequences": [
                ["base", "gust_1", "gust_2", "gust_1", "base", "base", "base", "base"],
            ],
        },
        {
            "id": "grass_shade_shimmer",
            "name": "Option C: Blade Shade Shimmer / Sun Fleck",
            "status": "candidate",
            "mechanism": "Subtle pixel shade pulse without shifting blade geometry",
            "pros": "Zero horizontal jitter or seam breaks; calm ambient life",
            "notes": "Very gentle; good if row-shifting feels too busy.",
            "mode": "async_meadow",
            "frames_per_step": 22,
            "tiles": {
                "base": base_flat,
                "shim_a": shimmer_a,
                "shim_b": shimmer_b,
                "shim_c": shimmer_c,
            },
            "sequences": [
                ["shim_a", "base"],
                ["shim_b", "base"],
                ["shim_c", "base"],
            ],
        },
        {
            "id": "grass_tip_nod",
            "name": "Option D: Minimal Upper-Tip Nod",
            "status": "candidate",
            "mechanism": "Only row 0 tips bend 1px right, keeping lower tufts anchored",
            "pros": "Subtle, clean, never noisy even on large green plains",
            "notes": "Least visually distracting nametable-swap option.",
            "mode": "async_meadow",
            "frames_per_step": 20,
            "tiles": {
                "base": base_flat,
                "tip_nod": tip_nod,
            },
            "sequences": [
                ["tip_nod", "base"],
            ],
        },
        {
            "id": "grass_pollen_oam",
            "name": "Option E: Grass Pollen / Firefly Mote (OAM)",
            "status": "candidate",
            "mechanism": "Sparse OAM particle via ow_sparkle.inc (no BG tile changes at all)",
            "pros": "100% consistent with Desert/Swamp/Mountain/Graveyard particle system",
            "notes": "Zero nametable writes; shares the 3 OAM slots in ow_sparkle.inc.",
            "mode": "oam_meadow",
            "frames_per_step": 8,
            "tiles": {
                "base": base_flat,
            },
            "oam_frames": [
                [0, 0, 0, 0, 0, 0, 0, 0,
                 0, 3, 0, 0, 0, 0, 0, 0] + [0] * 48,
                [0, 0, 0, 0, 0, 0, 0, 0,
                 0, 2, 3, 0, 0, 0, 0, 0] + [0] * 48,
            ],
            "sequences": [["base"]],
        },
    ]


def _build_forest_possibilities(
    tl_flat: list[int],
    bl_flat: list[int],
    tr_flat: list[int],
    br_flat: list[int],
    rom_tl: dict[str, list[int]],
    rom_tr: dict[str, list[int]],
) -> list[dict[str, Any]]:
    """Build current ROM + candidate iteration possibilities for Forest ($68-$6B)."""
    tl_rows = _flat_to_rows(tl_flat)
    tr_rows = _flat_to_rows(tr_flat)

    def _shift_rows_zero(src_rows: list[list[int]], row_shifts: dict[int, int]) -> list[int]:
        rows = [list(r) for r in src_rows]
        for r_idx, sh in row_shifts.items():
            src = src_rows[r_idx]
            dst = [0] * 8
            for x in range(8):
                nx = x + sh
                if 0 <= nx < 8:
                    dst[nx] = src[x]
            rows[r_idx] = dst
        return _rows_to_flat(rows)

    def _recolor_rows(src_rows: list[list[int]], edits: dict[tuple[int, int], int]) -> list[int]:
        rows = [list(r) for r in src_rows]
        for (r_idx, x_idx), val in edits.items():
            rows[r_idx][x_idx] = val
        return _rows_to_flat(rows)

    # Option A: Interior-only leaf rustle (preserves outer trunk/crown silhouette)
    tl_int_a = _recolor_rows(tl_rows, {(3, 4): 2, (4, 3): 2, (5, 4): 2})
    tl_int_b = _recolor_rows(tl_rows, {(2, 3): 2, (4, 5): 2, (6, 4): 2})
    tr_int_a = _recolor_rows(tr_rows, {(2, 4): 2, (3, 5): 2, (5, 3): 2})
    tr_int_b = _recolor_rows(tr_rows, {(1, 5): 2, (4, 4): 2, (6, 4): 2})

    # Option B: Top-crown 1px gentle breeze (top 2 rows only)
    tl_top = _shift_rows_zero(tl_rows, {0: 1, 1: 1})
    tr_top = _shift_rows_zero(tr_rows, {0: 1, 1: 1})

    # Option C: Dappled sunlight (bright green highlight spots shifting across crown)
    tl_sun_1 = _recolor_rows(tl_rows, {(1, 2): 2, (1, 3): 2, (2, 2): 2})
    tl_sun_2 = _recolor_rows(tl_rows, {(4, 4): 2, (5, 4): 2, (5, 5): 2})
    tr_sun_1 = _recolor_rows(tr_rows, {(1, 5): 2, (2, 5): 2, (2, 6): 2})
    tr_sun_2 = _recolor_rows(tr_rows, {(4, 3): 2, (4, 4): 2, (5, 3): 2})

    return [
        {
            "id": "forest_rom_current",
            "name": "Current ROM (Nametable Swap $A4-$AF)",
            "status": "current",
            "mechanism": "CHR 31 R1 nametable swap ($68->$A4..$A9, $6A->$AA..$AF, 6 async slots, 10-32f)",
            "pros": "Already wired in ow_foliage.inc; independent per-tree timing",
            "notes": "Only animates top-left ($68) and top-right ($6A); bottom ($69/$6B) stay static.",
            "mode": "async_forest",
            "frames_per_step": 16,
            "base": {"tl": tl_flat, "bl": bl_flat, "tr": tr_flat, "br": br_flat},
            "tl_variants": rom_tl,
            "tr_variants": rom_tr,
            "tl_sequences": [["$A4", "$A5", "base"], ["$A6", "$A7", "$A4", "base"], ["$A8", "$A9", "base"]],
            "tr_sequences": [["$AA", "$AB", "base"], ["$AC", "$AD", "$AA", "base"], ["$AE", "$AF", "base"]],
        },
        {
            "id": "forest_interior_rustle",
            "name": "Option A: Interior Leaf Rustle (Silhouette Locked)",
            "status": "candidate",
            "mechanism": "Swaps only interior canopy pixels (2<->3) while outer outline never moves",
            "pros": "Tree silhouettes stay crisp and rock-solid; zero edge clipping",
            "notes": "Easy to tune in CHR 31 R1 ($A4-$AF) without touching ow_foliage.inc.",
            "mode": "async_forest",
            "frames_per_step": 18,
            "base": {"tl": tl_flat, "bl": bl_flat, "tr": tr_flat, "br": br_flat},
            "tl_variants": {"tl_a": tl_int_a, "tl_b": tl_int_b},
            "tr_variants": {"tr_a": tr_int_a, "tr_b": tr_int_b},
            "tl_sequences": [["tl_a", "tl_b", "base"], ["tl_b", "base"]],
            "tr_sequences": [["tr_a", "tr_b", "base"], ["tr_b", "base"]],
        },
        {
            "id": "forest_crown_breeze",
            "name": "Option B: Gentle Top-Crown Breeze",
            "status": "candidate",
            "mechanism": "Shifts only top 2 rows of crown 1px right, keeping trunk & sides still",
            "pros": "Clear wind motion without breaking tree-to-tree alignment",
            "notes": "Simpler 2-frame cadence; less noisy in dense forests.",
            "mode": "async_forest",
            "frames_per_step": 22,
            "base": {"tl": tl_flat, "bl": bl_flat, "tr": tr_flat, "br": br_flat},
            "tl_variants": {"tl_top": tl_top},
            "tr_variants": {"tr_top": tr_top},
            "tl_sequences": [["tl_top", "base"]],
            "tr_sequences": [["tr_top", "base"]],
        },
        {
            "id": "forest_dappled_sun",
            "name": "Option C: Dappled Sunlight Shimmer",
            "status": "candidate",
            "mechanism": "Highlights shift between upper and mid canopy as clouds pass",
            "pros": "Very atmospheric; pairs naturally with overworld clouds/breeze",
            "notes": "Zero pixel shifting; pure 2-bit shade cycling on select leaves.",
            "mode": "async_forest",
            "frames_per_step": 20,
            "base": {"tl": tl_flat, "bl": bl_flat, "tr": tr_flat, "br": br_flat},
            "tl_variants": {"sun1": tl_sun_1, "sun2": tl_sun_2},
            "tr_variants": {"sun1": tr_sun_1, "sun2": tr_sun_2},
            "tl_sequences": [["sun1", "sun2", "base"]],
            "tr_sequences": [["sun1", "sun2", "base"]],
        },
        {
            "id": "forest_falling_leaf",
            "name": "Option D: Falling Leaf / Canopy Mote (OAM)",
            "status": "candidate",
            "mechanism": "Sparse OAM leaf sprite drifting down from canopy (ow_sparkle.inc)",
            "pros": "Leaves BG tiles 100% static; matches Desert/Swamp/Mountain particle feel",
            "notes": "Needs 2 CHR sprite tiles and 1 entry in OwTerrainKind.",
            "mode": "oam_forest",
            "frames_per_step": 8,
            "base": {"tl": tl_flat, "bl": bl_flat, "tr": tr_flat, "br": br_flat},
            "tl_variants": {},
            "tr_variants": {},
            "oam_frames": [
                [0, 0, 2, 0, 0, 0, 0, 0,
                 0, 2, 3, 2, 0, 0, 0, 0] + [0] * 48,
                [0, 0, 0, 0, 0, 0, 0, 0,
                 0, 0, 2, 3, 0, 0, 0, 0] + [0] * 48,
            ],
            "tl_sequences": [["base"]],
            "tr_sequences": [["base"]],
        },
    ]


def collect_ow_tiles_data() -> dict[str, Any]:
    """Collect all animated overworld tile types, sprites, and iteration candidates."""
    chr_data = _load_overworld_chr_data()
    ow_r0 = chr_data["ow_r0"]
    ow_r1 = chr_data["ow_r1"]
    ext_r0 = chr_data["ext_r0"]

    def r0_tile(tid: int, bank: int = 124) -> list[int]:
        buf = ext_r0[bank]
        return _tile_to_flat(buf[tid * 16:(tid + 1) * 16])

    def r1_tile(tid: int) -> list[int]:
        off = (tid - 0x80) * 16
        return _tile_to_flat(ow_r1[off:off + 16])

    water_banks = [124, 230, 232, 230, 124, 234, 236, 234]
    water_frames = [r0_tile(0x6E, b) for b in water_banks]
    swamp_frames = [r0_tile(0x6F, b) for b in water_banks]

    desert_base = r0_tile(0x6C)
    grass_base = r0_tile(0x6D)
    forest_tl = r0_tile(0x68)
    forest_bl = r0_tile(0x69)
    forest_tr = r0_tile(0x6A)
    forest_br = r0_tile(0x6B)
    mtn_tiles = [r0_tile(t) for t in (0x64, 0x65, 0x66, 0x67)]
    grave_tiles = [r0_tile(0x70), r0_tile(0x71), [0] * 64, [0] * 64]

    # OAM particle sprites from tools/build.py ($D0-$E3)
    particles = {
        "desert_glint": {
            "pal": "spr0",
            "duration": 28,
            "frames": [
                _encode_8x16_chars([
                    "........", ".#......", "........", "........",
                    "........", "........", "........", "........",
                ]),
                _encode_8x16_chars([
                    ".#......", "###.....", ".#......", "........",
                    "........", "........", "........", "........",
                ]),
            ],
        },
        "water_crest": {
            "pal": "spr2",
            "duration": 24,
            "frames": [
                _encode_8x16_chars([
                    "........", ".o......", ".#......", "........",
                    "........", "........", "........", "........",
                ]),
                _encode_8x16_chars([
                    "........", "ooo.....", ".##.....", "........",
                    "........", "........", "........", "........",
                ]),
            ],
        },
        "swamp_bubble": {
            "pal": "spr0",
            "duration": 44,
            "frames": [
                _encode_8x16_chars([
                    "........", ".+......", "........", "........",
                    "........", "........", "........", "........",
                ]),
                _encode_8x16_chars([
                    ".#+.....", ".++.....", "........", "........",
                    "........", "........", "........", "........",
                ]),
                _encode_8x16_chars([
                    ".#......", "###.....", ".#......", "........",
                    "........", "........", "........", "........",
                ]),
            ],
        },
        "mtn_ember": {
            "pal": "spr0",
            "duration": 40,
            "frames": [
                _encode_8x16_chars([
                    "........", ".#......", "........", "........",
                    "........", "........", "........", "........",
                ]),
                _encode_8x16_chars([
                    "........", ".+......", "........", "........",
                    "........", "........", "........", "........",
                ]),
                _encode_8x16_chars([
                    "........", ".o......", "........", "........",
                    "........", "........", "........", "........",
                ]),
            ],
        },
        "grave_wisp": {
            "pal": "spr0",
            "duration": 48,
            "frames": [
                _encode_8x16_chars([
                    "........", ".+......", "........", "........",
                    "........", "........", "........", "........",
                ]),
                _encode_8x16_chars([
                    "..#.....", ".+......", "........", "........",
                    "........", "........", "........", "........",
                ]),
            ],
        },
    }

    grass_rom_variants = {f"${tid:02X}": r1_tile(tid) for tid in range(0x9E, 0xA4)}
    forest_tl_rom_variants = {f"${tid:02X}": r1_tile(tid) for tid in range(0xA4, 0xAA)}
    forest_tr_rom_variants = {f"${tid:02X}": r1_tile(tid) for tid in range(0xAA, 0xB0)}

    fol_seqs = _parse_foliage_sequences(ROOT / "src" / "ow_foliage.inc")

    environments = [
        {
            "id": "water",
            "name": "Water",
            "tile_ids": "$6E (Terrain $0C/$0D)",
            "status": "settled",
            "pal": "water_desert",
            "mechanism": "R0 CHR Bankswitch (124, 230, 232, 230, 124, 234, 236, 234) + OAM Sun-Glint ($D5/$D7)",
            "timing": "16 frames/step (R0 ripple) · 24f OAM glint",
            "notes": "8-step counter-phase +/-2px ripple; settled.",
            "kind": "water",
            "frames": water_frames,
            "bank_labels": [str(b) for b in water_banks],
            "particle": "water_crest",
        },
        {
            "id": "swamp",
            "name": "Swamp / Foul Water",
            "tile_ids": "$6F (Terrain $07 & Saria $0A)",
            "status": "settled",
            "pal": "saria_swamp",
            "mechanism": "R0 CHR Bankswitch (same 8-step ripple) + OAM Marsh Bubble ($D9/$DB/$D3)",
            "timing": "16 frames/step (R0 ripple) · 44f rising bubble",
            "notes": "Bubbles rise 1px every 8 frames and pop; settled.",
            "kind": "swamp",
            "frames": swamp_frames,
            "bank_labels": [str(b) for b in water_banks],
            "particle": "swamp_bubble",
        },
        {
            "id": "desert",
            "name": "Desert",
            "tile_ids": "$6C (Terrain $04)",
            "status": "settled",
            "pal": "water_desert",
            "mechanism": "OAM Sand Sparkle ($D1 1px white / $D3 3x3 twinkle) across 8 metatile offsets",
            "timing": "28 frames/sparkle · 3 shared OAM slots",
            "notes": "Sparse, slow, per-tile glint anchored to scroll ($FD/$FC); settled.",
            "kind": "desert",
            "frames": [desert_base],
            "particle": "desert_glint",
        },
        {
            "id": "mountain",
            "name": "Mountain / Rock / Lava",
            "tile_ids": "$64-$67 (Terrain $0A/$0B/$0E)",
            "status": "settled",
            "pal": "mountain_grave",
            "mechanism": "OAM Rising Ember ($D1/$DD/$DF) rising 1px every 4 frames",
            "timing": "40 frames/ember · 3 shared OAM slots",
            "notes": "Shared ambience particle system in ow_sparkle.inc.",
            "kind": "mountain",
            "frames": mtn_tiles,
            "particle": "mtn_ember",
        },
        {
            "id": "graveyard",
            "name": "Graveyard",
            "tile_ids": "$70/$71 (Terrain $08)",
            "status": "settled",
            "pal": "mountain_grave",
            "mechanism": "OAM Cross Wisp ($E1/$E3) rising + swaying every 16 frames",
            "timing": "48 frames/wisp · -112..-81f cooldown",
            "notes": "Shared ambience particle system in ow_sparkle.inc.",
            "kind": "graveyard",
            "frames": grave_tiles,
            "particle": "grave_wisp",
        },
        {
            "id": "forest",
            "name": "Forest",
            "tile_ids": "$68 TL, $69 BL, $6A TR, $6B BR (Terrain $06)",
            "status": "iterating",
            "pal": "west_foliage",
            "mechanism": "CHR 31 R1 Nametable Swap ($A4-$AF) across 6 async slots (6..11)",
            "timing": "10..32 frames/step · 3 TL + 3 TR patterns",
            "notes": "Not settled yet — compare current ROM vs candidate options below.",
            "kind": "forest",
            "frames": [forest_tl, forest_bl, forest_tr, forest_br],
            "variants_tl": forest_tl_rom_variants,
            "variants_tr": forest_tr_rom_variants,
            "fol_sequences": fol_seqs[4:10] if len(fol_seqs) >= 10 else [],
        },
        {
            "id": "grass",
            "name": "Grass",
            "tile_ids": "$6D (Terrain $05)",
            "status": "iterating",
            "pal": "west_foliage",
            "mechanism": "CHR 31 R1 Nametable Swap ($9E-$A3) across 6 async slots (0..5)",
            "timing": "12..43 frames/step · 4 patterns",
            "notes": "Not settled yet — compare current ROM vs candidate options below.",
            "kind": "grass",
            "frames": [grass_base],
            "variants": grass_rom_variants,
            "fol_sequences": fol_seqs[0:4] if len(fol_seqs) >= 4 else [],
        },
    ]

    return {
        "version": 1,
        "source": chr_data["source"],
        "nes_palette": NES_PALETTE,
        "palettes": OVERWORLD_PALETTES,
        "particles": particles,
        "environments": environments,
        "grass_possibilities": _build_grass_possibilities(grass_base, grass_rom_variants),
        "forest_possibilities": _build_forest_possibilities(
            forest_tl, forest_bl, forest_tr, forest_br,
            forest_tl_rom_variants, forest_tr_rom_variants,
        ),
    }


def write_ow_tiles_data_js(out_dir: Path | None = None) -> Path:
    """Write `web/local_ow_tiles_data.js` for the local-only dashboard."""
    target_dir = (ROOT / "web") if out_dir is None else out_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / "local_ow_tiles_data.js"
    payload = collect_ow_tiles_data()
    out_path.write_text(f"window.OW_TILES_DATA = {json.dumps(payload)};\n", encoding="utf-8")
    return out_path


if __name__ == "__main__":
    out = write_ow_tiles_data_js()
    print(f"Wrote {out}")
