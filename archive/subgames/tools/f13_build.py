"""Build script for Friday the 13th: Barba Edition (roms/f13.nes -> build/f13_barba.nes)."""
from __future__ import annotations

import hashlib
from pathlib import Path

from boss_art import make_frames, resize_x, source_head
from bps import write_bps
from f13_barba_code import (
    F13_HUD_HOOK,
    F13_PAL_HOOK,
    build_barba_bank1,
    build_barba_chr_variants,
    build_title_chr,
)
from f13_coven import build_coven_banks, build_coven_chr
from nes import decode_tile, encode_tile
from pack_f13 import (
    Asm6502,
    F13_ATK_GATE,
    F13_BARBA_BREATH,
    F13_BARBA_DRAW,
    F13_BARBA_RESET,
    F13_BOOT,
    F13_CHR_SWITCH,
    F13_CUR_R6,
    F13_MMC3_SEL,
    F13_NMI_WRAP,
    F13_RELOC_E5B4,
    F13_SAVE_OAM_PTR,
    F13_SET_R6,
    make_barba_trampolines,
    make_reloc_e5b4,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROM = ROOT / "roms/f13.nes"
Z2_ROM = ROOT / "roms/z2.nes"
SOURCE_SHA256 = "3e2bfc0097f5913b72dc4c77512e9596231359484423e3a5c26bea06c67b48e4"
OUT_ROM = ROOT / "build/f13_barba.nes"
PLAY_ROM = ROOT / "play/nes/f13.nes"

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


def build(count_build: bool = True, build_number: int | None = None, write_play: bool = True) -> Path:
    from build_history import HISTORY_FILE, get_subgame_build_number, next_subgame_build_number, record_subgame_build
    if build_number is None:
        build_number = next_subgame_build_number(HISTORY_FILE, "f13") if count_build else get_subgame_build_number(HISTORY_FILE, "f13")
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

    # Note: 0x0B08C..0x0B133 is F13's 168-byte ($A8) $E764 entry-12 CHR RLE + cabin/forest table
    # (0x0B113..0x0B133 holds non-zero cabin/forest data); shifting it breaks cabin/forest entry.

    # 2. Counselor sprite palettes (CHR table 0x0DD5D = 6x8B, and 0x0E218 for counselor 0):
    #    Keep 3 (Laura) and 4 (Debbie) untouched; give 0,1,2,5 distinct Barba palettes!
    #    Keep Sprite Palette 3 color 3 = $0F (black) so Sprite 0 (OAM[0], tile=$FF, attr=$23)
    #    stays invisible behind the BG instead of showing a white moon/dash artifact at top-left.
    barba_red  = bytes([0x0F, 0x16, 0x27, 0x30, 0x0F, 0x16, 0x27, 0x0F])
    barba_pyro = bytes([0x0F, 0x26, 0x28, 0x30, 0x0F, 0x26, 0x28, 0x0F])
    barba_wyrm = bytes([0x0F, 0x1A, 0x27, 0x30, 0x0F, 0x1A, 0x27, 0x0F])
    barba_sky  = bytes([0x0F, 0x11, 0x21, 0x30, 0x0F, 0x11, 0x21, 0x0F])

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
    # Exterior Sprite Palette 1: exact Z2 Palace 1 Wosu palette ($0F black, $16 red, $27 orange/tan, $30 white)
    rom.put(
        0x006ED,
        bytes([0x0F, 0x27, 0x1C, 0x0F]),
        bytes([0x0F, 0x16, 0x27, 0x30]),
        "ext_wosu_spr_pal1",
    )
    rom.put(
        0x0E214,
        bytes([0x0F, 0x27, 0x1C, 0x0F, 0x0F, 0x26, 0x36, 0x0F]),
        bytes([0x0F, 0x16, 0x27, 0x30]) + barba_red[:4],
        "wosu_and_counselor_0_ext_pal",
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
    # Use full 24x48 Barba + trail for 0,1,2,5 and keep female tiles for 3,4 (Laura/Debbie)
    rom.put(
        HEADER_SIZE + 0x3AF5,
        bytes([0xAD, 0x07, 0x05, 0xC9, 0x03, 0xB0, 0x0D, 0xA5, 0x00, 0x18]),
        bytes([
            0x20, 0x4B, 0xBB, 0xEA, 0xEA, 0xB0, 0x0D,
            0x4C, F13_BARBA_DRAW & 0xFF, F13_BARBA_DRAW >> 8,
        ]),
        "exterior_sprite_barba_check",
    )
    # Skip vanilla counselor body/legs ($AAE6, tiles $4D..$52) when 24x48 Barba was drawn
    rom.put(
        HEADER_SIZE + 0x4291,
        bytes.fromhex("24 04 14 04 18 04 28 08 38 08 48 80"),
        bytes([
            0xAD, 0x0A, 0x7C,  # LDA BARBA_SKIP_BODY ($7C0A)
            0xF0, 0x04,        # BEQ +4
            0xCE, 0x0A, 0x7C,  # DEC BARBA_SKIP_BODY
            0x60,              # RTS
            0x4C, 0xE6, 0xAA,  # JMP $AAE6
        ]),
        "skip_barba_vanilla_body_gate",
    )
    rom.put(
        HEADER_SIZE + 0x2EC9,
        bytes([0x20, 0xE6, 0xAA]),
        bytes([0x20, 0x91, 0xC2]),
        "exterior_barba_skip_vanilla_body",
    )
    rom.put(
        HEADER_SIZE + 0x3D11,
        bytes([0x20, 0xE6, 0xAA]),
        bytes([0x20, 0x91, 0xC2]),
        "hurt_barba_skip_vanilla_body",
    )
    rom.put(
        HEADER_SIZE + 0x3E00,
        bytes([0x20, 0xE6, 0xAA, 0x20, 0xD0, 0xBA]),
        bytes([0x20, 0xD0, 0xBA, 0x20, 0x91, 0xC2]),
        "water_barba_skip_vanilla_body",
    )
    # Run Z2 5-shot fireball volley & update every exterior frame ($AEBC: JSR $DBD8 -> JSR F13_BARBA_BREATH)
    rom.put(
        HEADER_SIZE + 0x2EBC,
        bytes([0x20, 0xD8, 0xDB]),
        bytes([0x20, F13_BARBA_BREATH & 0xFF, F13_BARBA_BREATH >> 8]),
        "exterior_barba_breath_hook",
    )
    # Disable regular F13 attack completely for Barba (0,1,2,5); keep for Laura/Debbie (3,4)
    rom.put(
        HEADER_SIZE + 0x326E,
        bytes([0x20, 0xF4, 0xB2]),
        bytes([0x4C, F13_ATK_GATE & 0xFF, F13_ATK_GATE >> 8]),
        "disable_regular_f13_attack_for_barba",
    )
    # Protect Sprite 0 from $05BF == 0 when OAM is full ($AEDC: LDY $056F; STY $05BF)
    rom.put(
        HEADER_SIZE + 0x2EDC,
        bytes([0xAC, 0x6F, 0x05, 0x8C, 0xBF, 0x05]),
        bytes([0x20, F13_SAVE_OAM_PTR & 0xFF, F13_SAVE_OAM_PTR >> 8, 0xEA, 0xEA, 0xEA]),
        "protect_sprite0_oam_ptr",
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

    # 3. Canonical Z2 boss-derived 24x48 Barba graphics + trail (base_tiles go into banks 0 & 2,
    #    and build_barba_chr_variants clones $00-$7F into extra R0 banks for Attack/Crouch/Hurt).
    z2_raw = Z2_ROM.read_bytes()
    front_16 = flip_h(resize_x(source_head(z2_raw, "closed"), 16))

    ext_tiles: list[tuple[int, list[str]]] = [
        # Fireball replacing Rock ($15) - canonical flame-crowned Z2 fireball
        (0x15, [
            "00300030",
            "01230120",
            "12331230",
            "12333221",
            "12333321",
            "01233210",
            "00122100",
            "00011000",
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

    # 3b. Link as Jason + Wosu as overworld zombie (extracted from roms/z2.nes CHR banks 0 & 3)
    def z2_tile(tid: int, bank4k: int = 0) -> list[str]:
        off = 0x20010 + bank4k * 4096 + tid * 16
        rows = []
        for y in range(8):
            p0, p1 = z2_raw[off + y], z2_raw[off + y + 8]
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

    # Wosu (Z2 Palace 1 CHR bank 9, 8x16 pairs facing left -> H-flipped to face right in F13)
    def wosu_frame(top_l: int, top_r: int, bot_l: int, bot_r: int) -> list[list[str]]:
        # Z2 8x16 pairs: top=(top_l/top_l+1, top_r/top_r+1), bottom=(bot_l/bot_l+1, bot_r/bot_r+1)
        return [
            flip_h(z2_tile(top_r, 9)), flip_h(z2_tile(top_l, 9)),
            flip_h(z2_tile(top_r + 1, 9)), flip_h(z2_tile(top_l + 1, 9)),
            flip_h(z2_tile(bot_r, 9)), flip_h(z2_tile(bot_l, 9)),
            flip_h(z2_tile(bot_r + 1, 9)), flip_h(z2_tile(bot_l + 1, 9)),
        ]

    wosu_a = wosu_frame(0x30, 0x32, 0x44, 0x46)
    wosu_b = wosu_frame(0x30, 0x32, 0x48, 0x4A)
    wosu_tiles = (
        [(0x84 + i, tile) for i, tile in enumerate(wosu_a)]       # Zombie frame 1 ($84-$8B)
        + [(0x8C + i, tile) for i, tile in enumerate(wosu_b)]     # Zombie frame 2 ($8C-$93)
        + [(0x94 + i, tile) for i, tile in enumerate(wosu_b[4:])] # Zombie frame 3 bottom ($94-$97)
    )
    ext_tiles.extend(wosu_tiles)

    for bank4k in (0, 2):
        for tid, tile in ext_tiles:
            # Tile $71 in 4KB bank 2 (CHR bank 1) holds E728[16] data; only free in bank 0
            if tid == 0x71 and bank4k == 2:
                continue
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

    # HUD portrait ($60-$63 in CHR bank 6) & Map Slot 0 ($00-$03) keep OG Barba;
    # slots $04-$07, $08-$0B, $64-$67, $68-$6B, $FC-$FF hold 5 distinct (1,2,3) dragon portraits,
    # and $14-$17 holds a Pal-2-remapped crimson roaring dragon (3=Laura, 4=Debbie kept untouched).
    portrait_tiles = split_grid(front_16, 2, 2)
    for idx, tid in enumerate((0x60, 0x61, 0x62, 0x63)):
        rom.put_chr_tile(6, tid, portrait_tiles[idx], f"hud_portrait_{tid:02X}")
    for idx, tid in enumerate((0x00, 0x01, 0x02, 0x03)):
        rom.put_chr_tile(6, tid, portrait_tiles[idx], f"map_portrait_og_{tid:02X}")

    roar_fire_16 = [
        "0033000330000000",
        "0322103210000000",
        "0012212110000000",
        "0131222211100000",
        "0131122222211000",
        "0012113312222100",
        "0012223312222210",
        "0122221122222130",
        "0122222221111323",
        "0122222110030232",
        "0122211100002323",
        "0122110000003230",
        "0122110030302300",
        "0122211122211000",
        "1223222222110000",
        "1223322211100000",
    ]
    wyrm_prof_16 = [
        "3300000330000000",
        "0321003210000000",
        "0012112210000000",
        "0012222211100000",
        "0011222222211000",
        "0012111331222100",
        "0012212332222210",
        "0122222112222210",
        "0122222222211000",
        "0122222111111000",
        "0122111303030000",
        "0122110000000000",
        "0122113322220000",
        "0122211222211000",
        "0123222111110000",
        "1233222111100000",
    ]
    front_mug_16 = [
        "3300000000000033",
        "3210000000000123",
        "0121001111001210",
        "0122112222112210",
        "0012222332222100",
        "0011221221221100",
        "0122133113312210",
        "0122131111312210",
        "0122222222222210",
        "0012221221222100",
        "0011222222221100",
        "0001222222221000",
        "0013122332213100",
        "0013311111133100",
        "0012222222222100",
        "0122332222332210",
    ]
    crown_mug_16 = [
        "3300000330000033",
        "3210000220000123",
        "0121001221001210",
        "0122112222112210",
        "0012222332222100",
        "0011221221221100",
        "0122133113312210",
        "0122131111312210",
        "0122222222222210",
        "0012221221222100",
        "0011222222221100",
        "0001222222221000",
        "0013122332213100",
        "0013311111133100",
        "0012222222222100",
        "0122332222332210",
    ]
    left_crest_16 = [row[::-1] for row in wyrm_prof_16]
    pal2_roar_16 = [
        "0022000220000000",
        "0233102310000000",
        "0013113110000000",
        "0121113111100000",
        "0121111133111000",
        "0011112211133100",
        "0011112211133310",
        "0111111111133130",
        "0111111111111323",
        "0111111110020232",
        "0111111100003232",
        "0111110000002320",
        "0111110020203200",
        "0111111133311000",
        "1112333333110000",
        "1112233311100000",
    ]
    for base_tid, grid, name in (
        (0x04, roar_fire_16, "roar_fire"),
        (0x08, wyrm_prof_16, "wyrm_prof"),
        (0x64, front_mug_16, "front_mug"),
        (0x68, crown_mug_16, "crown_mug"),
        (0xFC, left_crest_16, "left_crest"),
        (0x14, pal2_roar_16, "pal2_roar"),
    ):
        tiles = split_grid(grid, 2, 2)
        for idx in range(4):
            rom.put_chr_tile(6, base_tid + idx, tiles[idx], f"map_portrait_{name}_{base_tid+idx:02X}")

    # Move Child icon ($18-$1B in CHR6) from Map Pal 1 -> Map Pal 2 (0F,16,35,27) by remapping 1->3
    # so Sprite Pal 1 is 100% free for OG Barba (0F,16,27,30) with identical Child pixels.
    for idx in range(4):
        tid = 0x18 + idx
        off = CHR_OFFSET + 6 * 4096 + tid * 16
        decoded = decode_tile(bytes(rom.data[off : off + 16]))
        remapped = ["".join("3" if px == 1 else str(px) for px in row) for row in decoded]
        rom.put_chr_tile(6, tid, remapped, f"child_icon_pal2_{tid:02X}")
    rom.put(HEADER_SIZE + 0x4A46, bytes([0x01]), bytes([0x02]), "child_icon_oam_pal2")

    # Redirect Map Screen portrait descriptors for Barba slots 0, 1, 2, 5 to WRAM $7CA0..$7CAC
    rom.put(HEADER_SIZE + 0x46C6, bytes.fromhex("2b ca"), bytes([0xA0, 0x7C]), "map_desc_ptr_slot0")
    rom.put(HEADER_SIZE + 0x46CC, bytes.fromhex("2f ca"), bytes([0xA4, 0x7C]), "map_desc_ptr_slot1")
    rom.put(HEADER_SIZE + 0x46D2, bytes.fromhex("33 ca"), bytes([0xA8, 0x7C]), "map_desc_ptr_slot2")
    rom.put(HEADER_SIZE + 0x46E4, bytes.fromhex("3f ca"), bytes([0xAC, 0x7C]), "map_desc_ptr_slot5")

    # Hook palette loader ($84B7) and HUD portrait lookup ($8B2F) for seeded Barba colors/faces
    rom.put(
        HEADER_SIZE + 0x04B7,
        bytes.fromhex("a9 01 85 2c 60"),
        bytes([0x4C, F13_PAL_HOOK & 0xFF, F13_PAL_HOOK >> 8, 0xEA, 0xEA]),
        "seeded_palette_hook",
    )
    rom.put(
        HEADER_SIZE + 0x0B2F,
        bytes.fromhex("b9 42 8b"),
        bytes([0x20, F13_HUD_HOOK & 0xFF, F13_HUD_HOOK >> 8]),
        "seeded_hud_portrait_hook",
    )

    # 4. MMC3 conversion (Mapper 4, 64KB PRG = banks 0..7, 32KB CHR)
    #    - $81A6 CNROM CHR switch -> JMP $7800 (WRAM Mmc3ChrSwitch)
    rom.put(
        HEADER_SIZE + 0x01A6,
        bytes.fromhex("b9 ad 81"),
        bytes([0x4C, F13_CHR_SWITCH & 0xFF, F13_CHR_SWITCH >> 8]),
        "mmc3_chr_switch_hook",
    )
    #    - Relocate $E5B4..$E5C3 wait loop to WRAM $7B10, freeing 13B at $E5B7 for Mmc3Boot
    rom.put(
        HEADER_SIZE + 0x65B4,
        bytes.fromhex("20 ea 81 ad 74 05 29 08 d0 06 88 d0 f3 a9 ff 60"),
        bytes([0x4C, F13_RELOC_E5B4 & 0xFF, F13_RELOC_E5B4 >> 8])
        + bytes.fromhex("a9 06 8d 00 80 a9 00 8d 01 80 4c 00 80"),
        "mmc3_boot_stub_e5b4",
    )
    rom.put(
        HEADER_SIZE + 0x7FFA,
        bytes.fromhex("b7 80"),
        bytes([F13_NMI_WRAP & 0xFF, F13_NMI_WRAP >> 8]),
        "mmc3_nmi_vector",
    )
    rom.put(
        HEADER_SIZE + 0x7FFC,
        bytes.fromhex("00 80"),
        bytes.fromhex("b7 e5"),
        "mmc3_reset_vector",
    )

    # Title screen hook at $E4F6 (always draws Attack Barba + CAMP BARBA; optionally stamps B<N> at $203A)
    rom.put(
        HEADER_SIZE + 0x64F6,
        bytes.fromhex("20 9e e3"),
        bytes([0x20, 0x00, 0x79]),
        "title_build_number_hook",
    )

    # Assemble 1KB WRAM helper ($7800-$7BFF) for standalone MMC3
    wram = bytearray(b"\xFF" * 0x400)
    a = Asm6502(F13_CHR_SWITCH)
    a.emit(0x08, 0x78, 0x48, 0x8A, 0x48, 0x98, 0x48)          # PHP; SEI; PHA; TXA; PHA; TYA; PHA
    a.emit(0x98, 0x0A, 0x0A, 0x0A, 0xAA)                      # TYA; ASL*3; TAX (0..3 -> 0,8,16,24)
    a.emit(0xC0, 0x02)                                        # CPY #$02
    a.branch(0xB0, "norm_r0")
    a.emit(0xB9, 0x0B, 0x7C)                                  # LDA $7C0B,Y (BARBA_R0_0/1)
    a.branch(0xD0, "set_r0")
    a.label("norm_r0")
    a.emit(0x8A)                                              # TXA
    a.label("set_r0")
    a.emit(0xA0, 0x00, 0x8C, F13_MMC3_SEL & 0xFF, F13_MMC3_SEL >> 8)
    a.emit(0x8C, 0x00, 0x80, 0x8D, 0x01, 0x80)                # R0 = A
    a.emit(0xE8, 0xE8, 0x8A, 0x48)                            # X += 2; TXA; PHA (save normal R1)
    a.emit(0xE0, 18)                                          # CPX #18 (Y == 2 indoors?)
    a.branch(0xD0, "r1_norm")
    a.emit(0xAD, 0x07, 0x05, 0xC9, 0x03)                      # Laura?
    a.branch(0xF0, "r1_norm")
    a.emit(0xC9, 0x04)                                        # Debbie?
    a.branch(0xF0, "r1_norm")
    a.emit(0xA2, 50)                                          # LDX #50 (2KB idx 25: Barba indoor R1)
    a.label("r1_norm")
    a.emit(0xA9, 0x01, 0x8D, F13_MMC3_SEL & 0xFF, F13_MMC3_SEL >> 8)
    a.emit(0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80)                # R1 = X
    a.emit(0x68, 0xAA)                                        # PLA; TAX (restore normal R1)
    a.emit(0xE8, 0xE8, 0xA0, 0x02)
    a.label("chr_loop")
    a.emit(0x8C, F13_MMC3_SEL & 0xFF, F13_MMC3_SEL >> 8)
    a.emit(0x8C, 0x00, 0x80, 0x8E, 0x01, 0x80)
    a.emit(0xE8, 0xC8, 0xC0, 0x06)
    a.branch(0x90, "chr_loop")
    a.emit(0x68, 0xA8, 0x68, 0xAA, 0x68, 0x28, 0x60)          # PLA; TAY; PLA; TAX; PLA; PLP; RTS
    chr_sw = a.finish()
    wram[0 : len(chr_sw)] = chr_sw

    tb_addr = 0x7900
    tb = Asm6502(tb_addr)
    tb.emit(0x20, 0x9E, 0xE3)                                  # JSR $E39E (draw title RLE screen)
    if build_number is not None:
        tb.emit(0x2C, 0x02, 0x20)                              # BIT $2002
        tb.emit(0xA9, 0x20, 0x8D, 0x06, 0x20)                  # $2006 = $20
        tb.emit(0xA9, 0x3A, 0x8D, 0x06, 0x20)                  # $2006 = $3A (row 1 col 26)
        for ch in f"B{build_number}":
            tid = 0x0B if ch == "B" else int(ch)
            tb.emit(0xA9, tid, 0x8D, 0x07, 0x20)
    tb.emit(0xA9, 0x01, 0x20, F13_SET_R6 & 0xFF, F13_SET_R6 >> 8)
    tb.emit(0x20, 0x0C, 0x80)                                  # JSR F13TitleDraw ($800C in bank 1)
    tb.emit(0xA9, 0x04, 0x4C, F13_SET_R6 & 0xFF, F13_SET_R6 >> 8)
    tb_bytes = tb.finish()
    assert tb_addr + len(tb_bytes) <= F13_BOOT
    wram[tb_addr - 0x7800 : tb_addr - 0x7800 + len(tb_bytes)] = tb_bytes

    a = Asm6502(F13_BOOT)
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0xA0)                      # Vertical mirroring
    a.emit(0x8D, 0x00, 0xE0)                                  # Disable MMC3 IRQ
    a.emit(0x8D, F13_MMC3_SEL & 0xFF, F13_MMC3_SEL >> 8)      # F13_MMC3_SEL = 0
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 4, 0x8D, 0x01, 0x80)  # R6 = 4 ($8000)
    a.emit(0x8D, F13_CUR_R6 & 0xFF, F13_CUR_R6 >> 8)          # F13_CUR_R6 = 4
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 5, 0x8D, 0x01, 0x80)  # R7 = 5 ($A000)
    a.emit(0xA9, 0x00, 0x8D, 0xFF, 0x7B, 0x8D, 0xFE, 0x7B)    # PRG_BASE=0, CHR_BASE=0
    a.emit(0x20, F13_BARBA_RESET & 0xFF, F13_BARBA_RESET >> 8)
    a.emit(0xA0, 0x00, 0x20, F13_CHR_SWITCH & 0xFF, F13_CHR_SWITCH >> 8)
    a.emit(0x4C, 0x00, 0x80)                                  # JMP $8000 (F13 Reset)
    boot_wram = a.finish()
    wram[F13_BOOT - 0x7800 : F13_BOOT - 0x7800 + len(boot_wram)] = boot_wram

    reloc = make_reloc_e5b4()
    wram[F13_RELOC_E5B4 - 0x7800 : F13_RELOC_E5B4 - 0x7800 + len(reloc)] = reloc
    tramp = make_barba_trampolines()
    wram[F13_BARBA_DRAW - 0x7800 : F13_BARBA_DRAW - 0x7800 + len(tramp)] = tramp

    bank0 = bytearray(b"\xFF" * 8192)
    a = Asm6502(0x8000)
    a.emit(0xA9, 0x80, 0x8D, 0x01, 0xA0)                      # Enable WRAM
    a.emit(0xA9, 0x00, 0x85, 0x00, 0x85, 0x02)
    a.emit(0xA9, 0x81, 0x85, 0x01, 0xA9, 0x78, 0x85, 0x03)
    a.emit(0xA2, 0x04, 0xA0, 0x00)
    a.label("cp")
    a.emit(0xB1, 0x00, 0x91, 0x02, 0xC8)
    a.branch(0xD0, "cp")
    a.emit(0xE6, 0x01, 0xE6, 0x03, 0xCA)
    a.branch(0xD0, "cp")
    a.emit(0x4C, F13_BOOT & 0xFF, F13_BOOT >> 8)
    loader = a.finish()
    bank0[0 : len(loader)] = loader
    bank0[0x100 : 0x500] = wram

    chr64, base_tiles = build_barba_chr_variants(z2_raw, bytes(rom.data[CHR_OFFSET:]))
    # Write base_tiles into 4KB CHR banks 0 and 2 of chr64
    chr64_buf = bytearray(chr64)
    for bank4k in (0, 2):
        for tid, rows in base_tiles.items():
            off = bank4k * 4096 + tid * 16
            chr64_buf[off : off + 16] = encode_tile(rows)
    build_coven_chr(chr64_buf, bytes(rom.data[CHR_OFFSET:]), z2_raw)
    title_layout = build_title_chr(chr64_buf, bytes(rom.data[CHR_OFFSET:]), z2_raw)

    extra_24k = bytearray(b"\xFF" * (3 * 8192))
    extra_24k[0:8192] = build_barba_bank1(title_layout)
    bank2, bank3 = build_coven_banks()
    extra_24k[8192:16384] = bank2
    extra_24k[16384:24576] = bank3
    hdr = bytearray(16)
    hdr[0:4] = b"NES\x1a"
    hdr[4] = 4     # 4 * 16KB = 64KB PRG (MMC3 banks 0..7)
    hdr[5] = 8     # 8 * 8KB = 64KB CHR
    hdr[6] = 0x41  # Mapper 4 (MMC3), Vertical mirroring
    out_bytes = bytes(hdr) + bytes(bank0) + bytes(extra_24k) + bytes(rom.data[HEADER_SIZE:CHR_OFFSET]) + bytes(chr64_buf)

    OUT_ROM.parent.mkdir(parents=True, exist_ok=True)
    OUT_ROM.write_bytes(out_bytes)
    if write_play:
        PLAY_ROM.parent.mkdir(parents=True, exist_ok=True)
        PLAY_ROM.write_bytes(out_bytes)
    if count_build:
        record_subgame_build(
            HISTORY_FILE,
            "f13",
            build_number,
            "mmc3",
            PLAY_ROM if write_play else OUT_ROM,
            hashlib.sha256(out_bytes).hexdigest(),
        )
    if write_play:
        write_bps(
            SOURCE_ROM,
            PLAY_ROM,
            out_bps_path=ROOT / "play/bps/f13.bps",
            metadata="Friday the 13th | Barba Edition",
        )
        print(f"Built {OUT_ROM} and {PLAY_ROM} ({len(out_bytes)} bytes, MMC3)")
    else:
        print(f"Built {OUT_ROM} ({len(out_bytes)} bytes, MMC3)")
    return OUT_ROM


if __name__ == "__main__":
    build()
