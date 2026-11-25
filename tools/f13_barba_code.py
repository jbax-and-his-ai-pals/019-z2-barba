"""24x48 Barba body + Z2 5-shot fireball volley generator for Friday the 13th (MMC3)."""
from __future__ import annotations

from pathlib import Path

from assets import encounter_connector_rows, encounter_trail_rows
from boss_art import make_frames, source_pair
from nes import encode_tile
from f13_coven import COVEN_ENDING_FLAG
from pack_f13 import Asm6502, F13_SET_R6, F13_SFX_CALL

# WRAM Bank 3 addresses ($7C00-$7CFF)
BREATH_STATE     = 0x7C00
BREATH_REMAINING = 0x7C01
BREATH_DELAY     = 0x7C02
BARBA_JAW_TIMER  = 0x7C03
TRAIL_IDX        = 0x7C04
FIRE_LOOP_I      = 0x7C05
HIT_ENEMY_Y      = 0x7C06
HIT_MAX_HP       = 0x7C07
BARBA_CROUCH     = 0x7C08
BARBA_R0         = 0x7C09  # legacy/unused (replaced by BARBA_R0_0/1)
BARBA_SKIP_BODY  = 0x7C0A
BARBA_R0_0       = 0x7C0B  # R0 override for Y=0 (0 = normal)
BARBA_R0_1       = 0x7C0C  # R0 override for Y=1 (0 = normal)

FIRE_LIFE        = 0x7C10  # 5 bytes ($7C10-$7C14)
FIRE_X           = 0x7C18  # 5 bytes ($7C18-$7C1C)
FIRE_Y           = 0x7C20  # 5 bytes ($7C20-$7C24)
FIRE_DX          = 0x7C28  # 5 bytes ($7C28-$7C2C)
FIRE_DY          = 0x7C30  # 5 bytes ($7C30-$7C34)
TRAIL_Y_RING     = 0x7C40  # 16 bytes ($7C40-$7C4F)

# Seeded Barba roster WRAM layout ($7CA0-$7CEF) + runtime hooks ($7D40-$7DDE)
F13_MAP_DESC     = 0x7CA0  # 4 x 4B sprite descriptors for slots 0, 1, 2, 5 ($7CA0-$7CAF)
F13_HUD_TILES    = 0x7CB0  # 6B HUD base tile IDs ($7CB0-$7CB5)
F13_STAND_SEEDED = 0x7CB6  # 0 = standalone not yet title-seeded, 1 = seeded
F13_MAP_PAL0     = 0x7CB8  # 4B Map Screen Sprite Pal 0 ($7CB8-$7CBB)
F13_MAP_PAL3     = 0x7CBC  # 4B Map Screen Sprite Pal 3 ($7CBC-$7CBF)
F13_EXT_PALS     = 0x7CC0  # 6 x 4B Exterior counselor sprite palettes ($7CC0-$7CD7)
F13_SEED_LO      = 0x7CE0
F13_SEED_HI      = 0x7CE1
F13_TMP_PERM     = 0x7CE2
F13_TMP_H0       = 0x7CE3
F13_TMP_H1       = 0x7CE4
F13_TMP_H2       = 0x7CE5
F13_TMP_P0_IDX   = 0x7CE6
F13_TMP_P3_IDX   = 0x7CE7
F13_TMP_C_MODE   = 0x7CE8
F13_TMP_K        = 0x7CE9

F13_PAL_HOOK     = 0x7D40  # WRAM hook called from $84B7 (JMP $7D40)
F13_HUD_HOOK     = 0x7E40  # WRAM hook called from $8B2F (JSR $7E40)

F13_CHR_BASE     = 0x7BFE  # $00 standalone, $80 Z2
F13_PRG_BASE     = 0x7BFF  # 0 standalone, 24 Z2
F13_CUR_CHR      = 0x7FFD  # last CHR bank (0..3)

# Tile IDs inside $45-$64 for Barba's 24x48 poses & trail
T_HEAD_BASE   = 0x45  # 6 tiles: 3 cols x 2 rows ($45..$4A)
T_BODY_BASE   = 0x4B  # 12 tiles: 3 sway variants x 2 halves x 2 cols ($4B..$56)
T_TRAIL_ELBOW = 0x57  # 4 tiles: 2 cols x 2 rows ($57..$5A)
T_TRAIL_TORSO = 0x5B  # 4 tiles: 2 cols x 2 rows ($5B..$5E)
T_TRAIL_TIP   = 0x5F  # 4 tiles: 2 cols x 2 rows ($5F..$62)
T_CROUCH_HEAD = 0x45  # 6 tiles ($45..$4A)
T_CROUCH_OPEN = 0x4B  # 6 tiles ($4B..$50)
T_CROUCH_BEND = 0x51  # 2 tiles ($51..$52): 16x8 rounded elbow
T_FIREBALL    = 0x15  # Z2 flame-crowned fireball tile


def _split_grid(rows: list[str], cols: int, tile_rows: int) -> list[list[str]]:
    tiles = []
    for ty in range(tile_rows):
        for tx in range(cols):
            tiles.append([rows[ty * 8 + y][tx * 8 : (tx + 1) * 8] for y in range(8)])
    return tiles


def build_barba_chr_variants(z2_raw: bytes, f13_chr: bytes) -> tuple[bytes, dict[int, list[str]]]:
    """Build 64KB f13_chr with 24x48 Barba + trail tiles across R0 pose variants.

    Returns (chr64k, base_tiles_dict) where base_tiles_dict maps tile_id -> 8x8 rows
    for base banks 0 and 1 ($45..$62).
    """
    frames = make_frames(z2_raw, 24)

    # Extract 8x16 pairs 0x06 and 0x08 from walk0 to feed encounter_connector_rows / encounter_trail_rows
    # walk0 is 24x48 LEFT-facing; columns 1..2 (x=8..23) hold the 16px-wide neck/torso!
    def encode_pair_from_rows(rows16: list[str]) -> bytes:
        return encode_tile(rows16[0:8]) + encode_tile(rows16[8:16])

    walk0_r0 = frames["walk0"][16:32]
    g06 = encode_pair_from_rows([r[8:16] for r in walk0_r0])
    g08 = encode_pair_from_rows([r[16:24] for r in walk0_r0])
    graphics = {0x06: g06, 0x08: g08}

    elbow_16x16 = encounter_connector_rows(graphics)
    trail_32x16 = encounter_trail_rows(graphics)
    torso_16x16 = [r[0:16] for r in trail_32x16]
    tip_16x16   = [r[16:32] for r in trail_32x16]

    # Head tiles (24x16 -> 6 tiles)
    head_closed = _split_grid(frames["idle"][0:16], 3, 2)
    head_open   = _split_grid(frames["attack"][0:16], 3, 2)
    head_hurt   = _split_grid(frames["windup"][0:16], 3, 2)

    # Body tiles:
    # walk0 rows 16..31 (sway 0, +1) + rows 32..47 (sway 0, -1) -> 8 tiles
    # walk1 rows 16..31 (sway +1, 0) + rows 32..47 (sway -1, 0) -> 8 tiles
    # Notice: walk0[16:24] (half0, sway=0) == walk1[24:32] (half1, sway=0) has different half!
    # So we store 3 sways x 2 halves x 2 cols = 12 tiles:
    #   half0 (y%16 in 0..7): walk0[16:24] (sway 0), walk1[16:24] (sway +1), walk1[32:40] (sway -1)
    #   half1 (y%16 in 8..15): walk0[24:32] (sway +1), walk0[40:48] (sway -1), walk1[24:32] (sway 0)
    b_h0_s0 = _split_grid([r[8:24] for r in frames["walk0"][16:24]], 2, 1)
    b_h0_sp = _split_grid([r[8:24] for r in frames["walk1"][16:24]], 2, 1)
    b_h0_sm = _split_grid([r[8:24] for r in frames["walk1"][32:40]], 2, 1)
    b_h1_s0 = _split_grid([r[8:24] for r in frames["walk1"][24:32]], 2, 1)
    b_h1_sp = _split_grid([r[8:24] for r in frames["walk0"][24:32]], 2, 1)
    b_h1_sm = _split_grid([r[8:24] for r in frames["walk0"][40:48]], 2, 1)
    body_12 = b_h0_s0 + b_h0_sp + b_h0_sm + b_h1_s0 + b_h1_sp + b_h1_sm

    # Crouch elbow: top 8 rows of elbow_16x16 (16x8 -> 2 tiles)
    crouch_bend = _split_grid(elbow_16x16[0:8], 2, 1)

    trail_tiles = (
        _split_grid(elbow_16x16, 2, 2)
        + _split_grid(torso_16x16, 2, 2)
        + _split_grid(tip_16x16, 2, 2)
    )

    def make_variant(head_tiles: list[list[str]], is_crouch: bool = False) -> dict[int, list[str]]:
        d: dict[int, list[str]] = {}
        if is_crouch:
            for i, t in enumerate(head_closed):
                d[T_CROUCH_HEAD + i] = t
            for i, t in enumerate(head_open):
                d[T_CROUCH_OPEN + i] = t
            for i, t in enumerate(crouch_bend):
                d[T_CROUCH_BEND + i] = t
        else:
            for i, t in enumerate(head_tiles):
                d[T_HEAD_BASE + i] = t
            for i, t in enumerate(body_12):
                d[T_BODY_BASE + i] = t
        for i, t in enumerate(trail_tiles):
            d[T_TRAIL_ELBOW + i] = t
        return d

    base_tiles = make_variant(head_closed, is_crouch=False)
    atk_tiles  = make_variant(head_open,   is_crouch=False)
    crch_tiles = make_variant(head_closed, is_crouch=True)
    hurt_tiles = make_variant(head_hurt,   is_crouch=False)

    # Expand 32KB f13_chr -> 64KB (8 x 8KB banks)
    chr64 = bytearray(b"\xFF" * (64 * 1024))
    chr64[0 : 32 * 1024] = f13_chr[: 32 * 1024]

    def write_2k_variant(dst_2k_idx: int, src_4k_bank: int, tile_map: dict[int, list[str]]) -> None:
        src_off = src_4k_bank * 4096
        dst_off = dst_2k_idx * 2048
        chr64[dst_off : dst_off + 2048] = chr64[src_off : src_off + 2048]
        for tid, rows in tile_map.items():
            chr64[dst_off + tid * 16 : dst_off + (tid + 1) * 16] = encode_tile(rows)

    # Note: Base banks 0 (4KB bank 0) and 1 (4KB bank 2) get base_tiles via f13_build.py's put_chr_tile.
    # Extra 2KB banks 16..21 (R0 = 32, 34, 36, 38, 40, 42) hold Attack, Crouch, Hurt for Y=0 and Y=1:
    #   R0 = 32 (2KB idx 16): Y=0 Attack
    #   R0 = 34 (2KB idx 17): Y=1 Attack
    #   R0 = 36 (2KB idx 18): Y=0 Crouch
    #   R0 = 38 (2KB idx 19): Y=1 Crouch
    #   R0 = 40 (2KB idx 20): Y=0 Hurt
    #   R0 = 42 (2KB idx 21): Y=1 Hurt
    write_2k_variant(16, 0, atk_tiles)
    write_2k_variant(17, 2, atk_tiles)
    write_2k_variant(18, 0, crch_tiles)
    write_2k_variant(19, 2, crch_tiles)
    write_2k_variant(20, 0, hurt_tiles)
    write_2k_variant(21, 2, hurt_tiles)

    return bytes(chr64), base_tiles


def build_barba_bank1() -> bytes:
    """Assemble 8KB PRG bank 1 ($8000-$9FFF) with 24x48 Barba renderer + Z2 fireball volley."""
    a = Asm6502(0x8000)

    # Fixed jump table at $8000, $8003, $8006, $8009
    a.abs_ref(0x4C, "F13BarbaDraw")
    a.abs_ref(0x4C, "F13BarbaBreath")
    a.abs_ref(0x4C, "F13BarbaReset")
    a.abs_ref(0x4C, "F13SeedSetup")

    # =========================================================================
    # F13BarbaReset: clear WRAM $7C00-$7C7F, install WRAM hooks, seed roster
    # =========================================================================
    a.label("F13BarbaReset")
    a.emit(0xA9, 0x00, 0xA2, 0x7F)
    a.label("rst_lp")
    a.emit(0x9D, 0x00, 0x7C, 0xCA)
    a.branch(0x10, "rst_lp")
    a.emit(0x8D, F13_STAND_SEEDED & 0xFF, F13_STAND_SEEDED >> 8)
    a.emit(0x8D, 0xB7, 0x7C)  # clear standalone title-wait tick counter ($7CB7)
    # Copy F13_PAL_HOOK ($7D40) and F13_HUD_HOOK ($7DC0) into WRAM
    a.emit(0xA2, 0x00)
    a.label("cp_pal_hook")
    a.abs_ref(0xBD, "WramPalHook")
    a.emit(0x9D, F13_PAL_HOOK & 0xFF, F13_PAL_HOOK >> 8, 0xE8)
    a.emit(0xE0, 0x00)  # patched after assembling WramPalHook
    pal_len_patch_idx = len(a.buf) - 1
    a.branch(0x90, "cp_pal_hook")
    a.emit(0xA2, 0x03)
    a.label("cp_hud_hook")
    a.abs_ref(0xBD, "WramHudHook")
    a.emit(0x9D, F13_HUD_HOOK & 0xFF, F13_HUD_HOOK >> 8, 0xCA)
    a.branch(0x10, "cp_hud_hook")
    a.abs_ref(0x4C, "F13SeedSetup")

    # =========================================================================
    # F13BarbaDraw: Draw full 24x48 Barba + trail into OAM ($0200 + $056F)
    # Falls back to $BB09 (vanilla draw) if $0308 >= 6 or $7FFD >= 2.
    # =========================================================================
    a.label("F13BarbaDraw")
    a.emit(0xAD, 0x08, 0x03, 0xC9, 0x06)         # LDA $0308; CMP #$06
    a.branch(0x90, "draw_ok1")
    a.label("draw_fallback")
    a.emit(0xA9, 0x00, 0x8D, BARBA_SKIP_BODY & 0xFF, BARBA_SKIP_BODY >> 8)
    a.emit(0x8D, BARBA_R0_0 & 0xFF, BARBA_R0_0 >> 8)
    a.emit(0x8D, BARBA_R0_1 & 0xFF, BARBA_R0_1 >> 8)
    a.emit(0x4C, 0x09, 0xBB)                     # JMP $BB09
    a.label("draw_ok1")
    a.emit(0xA5, 0x38, 0xC9, 0x01)               # $38 == 1 (exterior)?
    a.branch(0xD0, "draw_fallback")
    a.emit(0xA5, 0x37, 0xC9, 0x02)               # $37 < 2?
    a.branch(0xB0, "draw_fallback")
    a.emit(0xA9, 0x01, 0x8D, BARBA_SKIP_BODY & 0xFF, BARBA_SKIP_BODY >> 8)
    a.emit(0xAD, 0x68, 0x03, 0x0D, 0x78, 0x03)   # LDA $0368; ORA $0378
    a.branch(0xF0, "draw_onscreen")
    a.emit(0x60)                                 # offscreen -> RTS
    a.label("draw_onscreen")

    # Determine crouch vs hurt vs stand/walk/jump
    a.emit(0xA9, 0x00, 0x8D, BARBA_CROUCH & 0xFF, BARBA_CROUCH >> 8)
    a.emit(0xAD, 0x20, 0x04, 0xC9, 0x07)         # $0420 == 7 (hurt)?
    a.branch(0xD0, "chk_crouch")
    # Hurt pose: R0 = 40 (Y=0) / 42 (Y=1)
    a.emit(0xA9, 40)
    a.abs_ref(0x20, "SetR0")
    a.emit(0xA0, 0x04)                           # body frame 4 = hurt (walk1)
    a.abs_ref(0x4C, "draw_upright")

    a.label("chk_crouch")
    a.emit(0xAD, 0x20, 0x04, 0xC9, 0x03)         # $0420 == 3 (crouch)?
    a.branch(0xF0, "is_crouch")
    a.emit(0xAD, 0x08, 0x03, 0xC9, 0x02)         # $0308 == 2 (crouch)?
    a.branch(0xF0, "is_crouch")
    a.emit(0xAD, 0x20, 0x04)                     # grounded ($0420 == 0) & Down ($2D & $20)?
    a.branch(0xD0, "not_crouch")
    a.emit(0xA5, 0x2D, 0x29, 0x20)
    a.branch(0xF0, "not_crouch")
    a.label("is_crouch")
    a.emit(0xA9, 0x01, 0x8D, BARBA_CROUCH & 0xFF, BARBA_CROUCH >> 8)
    a.emit(0xA9, 36)
    a.abs_ref(0x20, "SetR0")
    a.abs_ref(0x4C, "draw_crouch")

    a.label("not_crouch")
    # Stand / Walk / Jump / Attack
    a.emit(0xAD, BARBA_JAW_TIMER & 0xFF, BARBA_JAW_TIMER >> 8)
    a.branch(0xF0, "jaw_closed")
    a.emit(0xA9, 32)
    a.abs_ref(0x20, "SetR0")
    a.abs_ref(0x4C, "pick_walk_frame")
    a.label("jaw_closed")
    a.emit(0xA9, 0x00)
    a.abs_ref(0x20, "SetR0")

    a.label("pick_walk_frame")
    a.emit(0xAD, 0x20, 0x04)                     # airborne ($0420 == 1 or 2)?
    a.branch(0xF0, "chk_walk_spd")
    a.emit(0xA0, 0x03)                           # frame 3 = jump (walk2)
    a.abs_ref(0x4C, "draw_upright")
    a.label("chk_walk_spd")
    a.emit(0xAD, 0x58, 0x04)                     # $0458 == 0 -> idle
    a.branch(0xD0, "is_walking")
    a.emit(0xA0, 0x00)                           # frame 0 = idle
    a.abs_ref(0x4C, "draw_upright")
    a.label("is_walking")
    a.emit(0xA5, 0x31, 0x4A, 0x4A, 0x29, 0x03)   # ($31 >> 2) & 3 -> 0,1,2,3
    a.emit(0xA8)                                 # Y = 0..3 (walk0, walk1, walk2, walk1)
    a.emit(0xC0, 0x03)
    a.branch(0xD0, "draw_upright")
    a.emit(0xA0, 0x01)

    # -------------------------------------------------------------------------
    # draw_upright: Y = body frame (0=walk0, 1=walk1, 2=walk2, 3=jump, 4=hurt)
    # $00 = attr ($00 facing left, $40 facing right)
    # $01 = center X ($0360)
    # $02 = feet Y ($0370)
    # $03 = body frame Y
    # -------------------------------------------------------------------------
    a.label("draw_upright")
    a.emit(0x84, 0x03)
    a.abs_ref(0x20, "SetupPlayerPos")            # sets $00=attr, $01=X, $02=feetY

    # Head: 3 cols x 2 rows at Y = feetY - 48, feetY - 40
    a.emit(0xA5, 0x02, 0x38, 0xE9, 48, 0x85, 0x04)  # $04 = top Y
    a.emit(0xA9, T_HEAD_BASE, 0x85, 0x05)           # $05 = tile
    a.abs_ref(0x20, "Draw3x2Head")

    # Body: 2 cols x 2 rows (top 16px of neck) at Y = feetY - 32, -24.
    # Bottom 16px (feetY - 16, -8) is replaced by the 16x16 elbow in DrawTrail!
    a.emit(0xA4, 0x03, 0xA2, 0x00)
    a.label("body_row_lp")
    a.emit(0x8A, 0x0A, 0x0A, 0x0A, 0x18, 0x65, 0x02, 0x38, 0xE9, 32, 0x85, 0x04)  # $04 = feetY - 32 + row*8
    a.emit(0xA5, 0x03, 0x0A, 0x0A, 0x85, 0x06)      # $06 = frame*4
    a.emit(0x8A, 0x18, 0x65, 0x06, 0xA8)            # Y = frame*4 + row
    a.abs_ref(0xB9, "BodyRowLeftTile")
    a.emit(0x85, 0x05)                              # $05 = left tile (in left-facing art)
    a.abs_ref(0xB9, "BodyRowRightTile")
    a.emit(0x85, 0x06)                              # $06 = right tile (in left-facing art)
    a.emit(0x8A, 0x48)                              # save row X
    a.abs_ref(0x20, "Draw2ColBodyRow")
    a.emit(0x68, 0xAA, 0xE8, 0xE0, 0x02)
    a.branch(0x90, "body_row_lp")

    # Draw elbow (at feetY-16, -8 directly under neck) + torso (off=12) + tip (off=28)
    a.emit(0xA5, 0x02, 0x38, 0xE9, 16)
    a.abs_ref(0x4C, "DrawTrail")

    # -------------------------------------------------------------------------
    # draw_crouch: 24x24 crouched head + 16x8 elbow + torso/tip trail
    # -------------------------------------------------------------------------
    a.label("draw_crouch")
    a.abs_ref(0x20, "SetupPlayerPos")            # $00=attr, $01=X, $02=feetY
    a.emit(0xA5, 0x02, 0x38, 0xE9, 24, 0x85, 0x04)  # head top = feetY - 24
    a.emit(0xA9, T_CROUCH_HEAD)
    a.emit(0xAC, BARBA_JAW_TIMER & 0xFF, BARBA_JAW_TIMER >> 8)
    a.branch(0xF0, "crch_closed")
    a.emit(0xA9, T_CROUCH_OPEN)
    a.label("crch_closed")
    a.emit(0x85, 0x05)
    a.abs_ref(0x20, "Draw3x2Head")

    # 16x8 elbow at feetY - 8
    a.emit(0xA5, 0x02, 0x38, 0xE9, 8, 0x85, 0x04)
    a.emit(0xA9, T_CROUCH_BEND, 0x85, 0x05)
    a.emit(0xA9, T_CROUCH_BEND + 1, 0x85, 0x06)
    a.abs_ref(0x20, "Draw2ColBodyRow")

    # Trail (torso + tip only; crouch bend already sits at feetY - 8)
    a.emit(0xA5, 0x02, 0x38, 0xE9, 16)
    a.abs_ref(0x4C, "DrawTrail")

    # =========================================================================
    # Helpers for F13BarbaDraw
    # =========================================================================
    a.label("SetR0")
    a.emit(0xC9, 0x00)                            # normal pose (0) clears both overrides
    a.branch(0xD0, "sr_nonzero")
    a.emit(0x8D, BARBA_R0_0 & 0xFF, BARBA_R0_0 >> 8)
    a.emit(0x8D, BARBA_R0_1 & 0xFF, BARBA_R0_1 >> 8)
    a.emit(0x60)
    a.label("sr_nonzero")
    a.emit(0x48)
    a.emit(0x0D, F13_CHR_BASE & 0xFF, F13_CHR_BASE >> 8)
    a.emit(0x8D, BARBA_R0_0 & 0xFF, BARBA_R0_0 >> 8)
    a.emit(0x68, 0x18, 0x69, 0x02)
    a.emit(0x0D, F13_CHR_BASE & 0xFF, F13_CHR_BASE >> 8)
    a.emit(0x8D, BARBA_R0_1 & 0xFF, BARBA_R0_1 >> 8)
    a.emit(0x60)

    a.label("SetupPlayerPos")
    a.emit(0xA9, 0x02, 0x85, 0x00)               # Palette 2 (0F, 16, 27, 30)
    a.emit(0xAD, 0x50, 0x03, 0x29, 0x04)
    a.branch(0xD0, "pos_left")
    a.emit(0xA9, 0x42, 0x85, 0x00)               # H-flip + Palette 2
    a.label("pos_left")
    a.emit(0xAD, 0x60, 0x03, 0x85, 0x01)         # $01 = X
    a.emit(0xAD, 0x70, 0x03, 0x85, 0x02)         # $02 = feetY
    a.emit(0x60)

    # Draw3x2Head: $00=attr, $01=X, $04=topY, $05=baseTile
    a.label("Draw3x2Head")
    a.emit(0xA0, 0x00)                           # row 0..1
    a.label("h_row")
    a.emit(0xA2, 0x00)                           # col 0..2
    a.label("h_col")
    a.emit(0xA5, 0x00, 0x29, 0x40)
    a.branch(0xD0, "h_flip")
    # Left-facing: col 0,1,2 -> X - 12 + col*8
    a.emit(0x8A, 0x0A, 0x0A, 0x0A, 0x18, 0x65, 0x01, 0x38, 0xE9, 12)
    a.branch(0xB0, "h_x_ok")                     # if no borrow, wait: X could be < 12 near left edge!
    a.abs_ref(0x4C, "h_skip")                    # off left edge -> skip
    a.label("h_flip")
    # Right-facing: art col 0,1,2 -> X + 4 - col*8
    a.emit(0x8A, 0x0A, 0x0A, 0x0A, 0x85, 0x07)
    a.emit(0xA5, 0x01, 0x18, 0x69, 0x04)
    a.branch(0xB0, "h_skip")                     # wrapped >= 256 -> skip
    a.emit(0x38, 0xE5, 0x07)
    a.branch(0x90, "h_skip")                     # wrapped < 0 -> skip
    a.label("h_x_ok")
    a.emit(0x85, 0x08)                           # $08 = sprite X
    a.emit(0xA5, 0x04, 0xC9, 0xEF)
    a.branch(0xB0, "h_skip")
    a.emit(0x85, 0x09)                           # $09 = sprite Y
    a.emit(0xA5, 0x05, 0x85, 0x0A)               # $0A = tile
    a.emit(0x8A, 0x48)                           # save col X
    a.abs_ref(0x20, "EmitOamSprite")
    a.emit(0x68, 0xAA)                           # restore col X
    a.label("h_skip")
    a.emit(0xE6, 0x05)                           # next tile
    a.emit(0xE8, 0xE0, 0x03)
    a.branch(0x90, "h_col")
    a.emit(0xA5, 0x04, 0x18, 0x69, 0x08, 0x85, 0x04)
    a.emit(0xC8, 0xC0, 0x02)
    a.branch(0x90, "h_row")
    a.emit(0x60)

    # Draw2ColBodyRow: $00=attr, $01=X, $04=Y, $05=leftArtTile, $06=rightArtTile
    # Left-facing: leftArtTile at X-4, rightArtTile at X+4
    # Right-facing: leftArtTile at X-4, rightArtTile at X-12
    a.label("Draw2ColBodyRow")
    a.emit(0xA5, 0x04, 0xC9, 0xEF)
    a.branch(0x90, "b2_y_ok")
    a.emit(0x60)
    a.label("b2_y_ok")
    a.emit(0x85, 0x09)                           # $09 = Y
    a.emit(0xA5, 0x00, 0x29, 0x40)
    a.branch(0xD0, "b2_right")
    # Left-facing: X-4 and X+4
    a.emit(0xA5, 0x01, 0x38, 0xE9, 0x04)
    a.branch(0x90, "b2_l2")
    a.emit(0x85, 0x08, 0xA5, 0x05, 0x85, 0x0A)
    a.abs_ref(0x20, "EmitOamSprite")
    a.label("b2_l2")
    a.emit(0xA5, 0x01, 0x18, 0x69, 0x04)
    a.branch(0xB0, "b2_done")
    a.emit(0x85, 0x08, 0xA5, 0x06, 0x85, 0x0A)
    a.abs_ref(0x4C, "EmitOamSprite")
    a.label("b2_right")
    # Right-facing: leftArtTile at X-4, rightArtTile at X-12
    a.emit(0xA5, 0x01, 0x38, 0xE9, 0x04)
    a.branch(0x90, "b2_r2")
    a.emit(0x85, 0x08, 0xA5, 0x05, 0x85, 0x0A)
    a.abs_ref(0x20, "EmitOamSprite")
    a.label("b2_r2")
    a.emit(0xA5, 0x01, 0x38, 0xE9, 12)
    a.branch(0x90, "b2_done")
    a.emit(0x85, 0x08, 0xA5, 0x06, 0x85, 0x0A)
    a.abs_ref(0x4C, "EmitOamSprite")
    a.label("b2_done")
    a.emit(0x60)

    # EmitOamSprite: $09=Y, $0A=tile, $00=attr, $08=X
    a.label("EmitOamSprite")
    a.emit(0xAE, 0x6F, 0x05)                     # LDX $056F
    a.branch(0xF0, "oam_full")
    a.emit(0xE0, 0xFC)                           # never wrap $056F to 0 (protects Sprite 0 / $05BF)
    a.branch(0x90, "oam_ok")
    a.label("oam_full")
    a.emit(0x60)                                 # OAM full
    a.label("oam_ok")
    a.emit(0xA5, 0x09, 0x9D, 0x00, 0x02)         # Y
    a.emit(0xA5, 0x0A, 0x9D, 0x01, 0x02)         # tile
    a.emit(0xA5, 0x00, 0x9D, 0x02, 0x02)         # attr
    a.emit(0xA5, 0x08, 0x9D, 0x03, 0x02)         # X
    a.emit(0xE8, 0xE8, 0xE8, 0xE8)
    a.emit(0x8E, 0x6F, 0x05)
    a.emit(0x60)

    # =========================================================================
    # DrawTrail: A = base Y (feetY - 16), $00=attr, $01=X
    # Draws elbow (16x16), torso (16x16), tip (16x16) with delayed Y wiggle!
    # =========================================================================
    a.label("DrawTrail")
    a.emit(0x85, 0x04)                           # $04 = elbow Y
    # Push $04 into 16-entry ring buffer and read delayed Y for torso (4 frames) & tip (8 frames)
    a.emit(0xAE, TRAIL_IDX & 0xFF, TRAIL_IDX >> 8)
    a.emit(0x9D, TRAIL_Y_RING & 0xFF, TRAIL_Y_RING >> 8)
    a.emit(0x8A, 0x38, 0xE9, 0x04, 0x29, 0x0F, 0xA8)
    a.emit(0xB9, TRAIL_Y_RING & 0xFF, TRAIL_Y_RING >> 8)
    a.branch(0xD0, "tr_ty_ok")
    a.emit(0xA5, 0x04)
    a.label("tr_ty_ok")
    a.emit(0x85, 0x0B)                           # $0B = torso Y
    a.emit(0x8A, 0x38, 0xE9, 0x08, 0x29, 0x0F, 0xA8)
    a.emit(0xB9, TRAIL_Y_RING & 0xFF, TRAIL_Y_RING >> 8)
    a.branch(0xD0, "tr_py_ok")
    a.emit(0xA5, 0x04)
    a.label("tr_py_ok")
    a.emit(0x85, 0x0C)                           # $0C = tip Y
    a.emit(0xE8, 0x8A, 0x29, 0x0F, 0x8D, TRAIL_IDX & 0xFF, TRAIL_IDX >> 8)

    # Draw elbow (16x16) directly below neck when upright (BARBA_CROUCH == 0):
    #   Row 0 at $04 (feetY - 16), Row 1 at $04 + 8 (feetY - 8)
    a.emit(0xAD, BARBA_CROUCH & 0xFF, BARBA_CROUCH >> 8)
    a.branch(0xD0, "tr_skip_elbow")
    a.emit(0xA5, 0x04, 0x85, 0x0D)               # save $04
    a.emit(0xA9, T_TRAIL_ELBOW, 0x85, 0x05)
    a.emit(0xA9, T_TRAIL_ELBOW + 1, 0x85, 0x06)
    a.abs_ref(0x20, "Draw2ColBodyRow")
    a.emit(0xA5, 0x0D, 0x18, 0x69, 0x08, 0x85, 0x04)
    a.emit(0xA9, T_TRAIL_ELBOW + 2, 0x85, 0x05)
    a.emit(0xA9, T_TRAIL_ELBOW + 3, 0x85, 0x06)
    a.abs_ref(0x20, "Draw2ColBodyRow")
    a.label("tr_skip_elbow")

    # Draw torso (16x16) at X+12 (left) / X-28 (right) and tip (16x16) at X+28 (left) / X-44 (right)
    a.emit(0xA9, T_TRAIL_TORSO, 0x85, 0x05)
    a.emit(0xA5, 0x0B, 0x85, 0x06)
    a.emit(0xA9, 12)
    a.abs_ref(0x20, "DrawTrail16x16")

    a.emit(0xA9, T_TRAIL_TIP, 0x85, 0x05)
    a.emit(0xA5, 0x0C, 0x85, 0x06)
    a.emit(0xA9, 28)
    a.abs_ref(0x4C, "DrawTrail16x16")

    # DrawTrail16x16: A = unsigned offset from X (12, 28, 44), $05 = baseTile, $06 = segY
    # Facing left: col0 at X + off, col1 at X + off + 8
    # Facing right: col0 at X - off - 8, col1 at X - off - 16
    a.label("DrawTrail16x16")
    a.emit(0x85, 0x07)
    a.emit(0xA5, 0x00, 0x29, 0x40)
    a.branch(0xD0, "t16_right")
    a.emit(0xA5, 0x01, 0x18, 0x65, 0x07)
    a.branch(0xB0, "t16_done")
    a.emit(0x85, 0x0D)                           # col0 X
    a.emit(0x18, 0x69, 0x08)
    a.branch(0x90, "t16_c1_ok")
    a.emit(0xA9, 0xFF)                           # mark skip
    a.label("t16_c1_ok")
    a.emit(0x85, 0x0E)                           # col1 X
    a.abs_ref(0x4C, "t16_draw")
    a.label("t16_right")
    a.emit(0xA5, 0x01, 0x38, 0xE5, 0x07, 0x38, 0xE9, 0x08)
    a.branch(0x90, "t16_done")
    a.emit(0x85, 0x0D)                           # col0 X (near)
    a.emit(0x38, 0xE9, 0x08)
    a.branch(0xB0, "t16_c1_ok2")
    a.emit(0xA9, 0xFF)
    a.label("t16_c1_ok2")
    a.emit(0x85, 0x0E)                           # col1 X (far)
    a.label("t16_draw")
    # Row 0 (segY), Row 1 (segY + 8)
    a.emit(0xA0, 0x00)
    a.label("t16_row")
    a.emit(0xA5, 0x06, 0xC9, 0xEF)
    a.branch(0xB0, "t16_next_row")
    a.emit(0x85, 0x09)
    a.emit(0xA5, 0x0D, 0x85, 0x08, 0xA5, 0x05, 0x85, 0x0A)
    a.abs_ref(0x20, "EmitOamSprite")
    a.emit(0xE6, 0x05)
    a.emit(0xA5, 0x0E, 0xC9, 0xF8)
    a.branch(0xB0, "t16_skip_c1")
    a.emit(0x85, 0x08, 0xA5, 0x05, 0x85, 0x0A)
    a.abs_ref(0x20, "EmitOamSprite")
    a.label("t16_skip_c1")
    a.emit(0xE6, 0x05)
    a.abs_ref(0x4C, "t16_row_adv")
    a.label("t16_next_row")
    a.emit(0xE6, 0x05, 0xE6, 0x05)
    a.label("t16_row_adv")
    a.emit(0xA5, 0x06, 0x18, 0x69, 0x08, 0x85, 0x06)
    a.emit(0xC8, 0xC0, 0x02)
    a.branch(0x90, "t16_row")
    a.label("t16_done")
    a.emit(0x60)

    # Body tile lookup tables (5 poses x 4 rows = 20 bytes)
    # Base tiles:
    #   +0..+1: h0_s0   +2..+3: h0_sp   +4..+5: h0_sm
    #   +6..+7: h1_s0   +8..+9: h1_sp   +10..+11: h1_sm
    a.label("BodyRowLeftTile")
    a.emit(
        T_BODY_BASE + 0, T_BODY_BASE + 8, T_BODY_BASE + 0, T_BODY_BASE + 10,   # 0: walk0
        T_BODY_BASE + 2, T_BODY_BASE + 6, T_BODY_BASE + 4, T_BODY_BASE + 6,    # 1: walk1
        T_BODY_BASE + 0, T_BODY_BASE + 10, T_BODY_BASE + 0, T_BODY_BASE + 8,   # 2: walk2
        T_BODY_BASE + 0, T_BODY_BASE + 10, T_BODY_BASE + 0, T_BODY_BASE + 8,   # 3: jump
        T_BODY_BASE + 2, T_BODY_BASE + 6, T_BODY_BASE + 4, T_BODY_BASE + 6,    # 4: hurt
    )
    a.label("BodyRowRightTile")
    a.emit(
        T_BODY_BASE + 1, T_BODY_BASE + 9, T_BODY_BASE + 1, T_BODY_BASE + 11,
        T_BODY_BASE + 3, T_BODY_BASE + 7, T_BODY_BASE + 5, T_BODY_BASE + 7,
        T_BODY_BASE + 1, T_BODY_BASE + 11, T_BODY_BASE + 1, T_BODY_BASE + 9,
        T_BODY_BASE + 1, T_BODY_BASE + 11, T_BODY_BASE + 1, T_BODY_BASE + 9,
        T_BODY_BASE + 3, T_BODY_BASE + 7, T_BODY_BASE + 5, T_BODY_BASE + 7,
    )

    # =========================================================================
    # F13BarbaBreath: Z2 5-shot diagonal fireball volley + collision + OAM
    # =========================================================================
    a.label("F13BarbaBreath")
    a.emit(0x20, 0x4B, 0xBB)                     # JSR IsFemaleHuman
    a.branch(0x90, "br_is_barba")
    a.abs_ref(0x4C, "CheckForestCoven")          # Laura/Debbie -> check Forest Coven trigger
    a.label("br_is_barba")
    a.emit(0xA5, 0x38, 0xC9, 0x01)
    a.branch(0xF0, "br_ext_chk37")
    a.emit(0x60)
    a.label("br_ext_chk37")
    a.emit(0xA5, 0x37, 0xC9, 0x02)
    a.branch(0x90, "br_ext")
    a.emit(0x60)                                 # not exterior -> skip
    a.label("br_ext")

    # Decrement jaw timer if active
    a.emit(0xAD, BARBA_JAW_TIMER & 0xFF, BARBA_JAW_TIMER >> 8)
    a.branch(0xF0, "br_chk_state")
    a.emit(0xCE, BARBA_JAW_TIMER & 0xFF, BARBA_JAW_TIMER >> 8)

    # Check player alive ($0420 != 7, 8, $0F)
    a.label("br_chk_state")
    a.emit(0xAD, 0x20, 0x04)
    a.emit(0xC9, 0x07)
    a.branch(0xF0, "br_dead")
    a.emit(0xC9, 0x08)
    a.branch(0xF0, "br_dead")
    a.emit(0xC9, 0x0F)
    a.branch(0xF0, "br_dead")

    a.emit(0xAD, BREATH_STATE & 0xFF, BREATH_STATE >> 8)
    a.emit(0xC9, 0x02)
    a.branch(0xD0, "br_not_wait")
    # Wait for B release ($2D & $02 == 0)
    a.emit(0xA5, 0x2D, 0x29, 0x02)
    a.branch(0xD0, "br_update_only")
    a.emit(0xA9, 0x00, 0x8D, BREATH_STATE & 0xFF, BREATH_STATE >> 8)

    a.label("br_not_wait")
    a.emit(0xAD, BREATH_STATE & 0xFF, BREATH_STATE >> 8)
    a.branch(0xD0, "br_firing")
    # Ready: check newly pressed B ($0574 & $02)
    a.emit(0xAD, 0x74, 0x05, 0x29, 0x02)
    a.branch(0xF0, "br_update_only")
    a.emit(0xA9, 0x01, 0x8D, BREATH_STATE & 0xFF, BREATH_STATE >> 8)
    a.emit(0xA9, 0x05, 0x8D, BREATH_REMAINING & 0xFF, BREATH_REMAINING >> 8)
    a.emit(0xA9, 0x00, 0x8D, BREATH_DELAY & 0xFF, BREATH_DELAY >> 8)

    a.label("br_firing")
    a.emit(0xAD, BREATH_DELAY & 0xFF, BREATH_DELAY >> 8)
    a.branch(0xF0, "br_emit_try")
    a.emit(0xCE, BREATH_DELAY & 0xFF, BREATH_DELAY >> 8)
    a.abs_ref(0x4C, "br_update_only")

    a.label("br_emit_try")
    a.abs_ref(0x20, "EmitOneFireball")
    a.branch(0x90, "br_update_only")             # pool full -> retry next frame
    a.emit(0xA9, 0x08, 0x8D, BARBA_JAW_TIMER & 0xFF, BARBA_JAW_TIMER >> 8)
    a.emit(0xA9, 0x6C, 0x20, F13_SFX_CALL & 0xFF, F13_SFX_CALL >> 8)  # JSR $8F6C (fire SFX) via WRAM
    a.emit(0xCE, BREATH_REMAINING & 0xFF, BREATH_REMAINING >> 8)
    a.branch(0xF0, "br_volley_done")
    a.emit(0xA9, 0x08, 0x8D, BREATH_DELAY & 0xFF, BREATH_DELAY >> 8)
    a.abs_ref(0x4C, "br_update_only")
    a.label("br_volley_done")
    a.emit(0xA9, 0x02, 0x8D, BREATH_STATE & 0xFF, BREATH_STATE >> 8)
    a.abs_ref(0x4C, "br_update_only")

    a.label("br_dead")
    a.emit(0xA9, 0x00, 0x8D, BREATH_STATE & 0xFF, BREATH_STATE >> 8)

    # Update all 5 fireball slots
    a.label("br_update_only")
    a.emit(0xA2, 0x00)
    a.label("fire_lp")
    a.emit(0xBD, FIRE_LIFE & 0xFF, FIRE_LIFE >> 8)
    a.branch(0xD0, "fire_active")
    a.abs_ref(0x4C, "fire_next")
    a.label("fire_active")
    a.emit(0x8E, FIRE_LOOP_I & 0xFF, FIRE_LOOP_I >> 8)

    # Apply camera scroll $65 (signed magnitude)
    a.emit(0xA5, 0x65)
    a.branch(0x30, "scr_neg")
    a.emit(0x18, 0x7D, FIRE_X & 0xFF, FIRE_X >> 8)
    a.branch(0xB0, "fire_kill")
    a.abs_ref(0x4C, "scr_done")
    a.label("scr_neg")
    a.emit(0x29, 0x7F, 0x85, 0x00)
    a.emit(0xBD, FIRE_X & 0xFF, FIRE_X >> 8, 0x38, 0xE5, 0x00)
    a.branch(0x90, "fire_kill")
    a.label("scr_done")
    a.emit(0x9D, FIRE_X & 0xFF, FIRE_X >> 8)

    # Move X += DX
    a.emit(0xBD, FIRE_DX & 0xFF, FIRE_DX >> 8)
    a.branch(0x30, "dx_neg")
    a.emit(0x18, 0x7D, FIRE_X & 0xFF, FIRE_X >> 8)
    a.branch(0xB0, "fire_kill")
    a.abs_ref(0x4C, "dx_done")
    a.label("dx_neg")
    a.emit(0x18, 0x7D, FIRE_X & 0xFF, FIRE_X >> 8)
    a.branch(0x90, "fire_kill")
    a.label("dx_done")
    a.emit(0x9D, FIRE_X & 0xFF, FIRE_X >> 8)

    # Move Y += DY (+2)
    a.emit(0xBD, FIRE_Y & 0xFF, FIRE_Y >> 8)
    a.emit(0x18, 0x7D, FIRE_DY & 0xFF, FIRE_DY >> 8)
    a.emit(0xC9, 0xEB)
    a.branch(0xB0, "fire_kill")
    a.emit(0x9D, FIRE_Y & 0xFF, FIRE_Y >> 8)

    # Decrement life
    a.emit(0xDE, FIRE_LIFE & 0xFF, FIRE_LIFE >> 8)
    a.branch(0xF0, "fire_kill")

    # Check enemy collision (Y = 2..5) using native F13 hitbox routines
    a.abs_ref(0x20, "CheckFireballHit")
    a.branch(0xB0, "fire_kill")

    # Draw fireball OAM sprite
    a.emit(0xAE, FIRE_LOOP_I & 0xFF, FIRE_LOOP_I >> 8)
    a.emit(0xBD, FIRE_Y & 0xFF, FIRE_Y >> 8, 0x38, 0xE9, 0x04, 0x85, 0x09)
    a.emit(0xBD, FIRE_X & 0xFF, FIRE_X >> 8, 0x38, 0xE9, 0x04, 0x85, 0x08)
    a.emit(0xA9, T_FIREBALL, 0x85, 0x0A)
    a.emit(0xA5, 0x31, 0x29, 0x02, 0xF0, 0x02, 0xA9, 0x40)  # alternate H-flip every 2 frames
    a.emit(0x85, 0x00)
    a.abs_ref(0x20, "EmitOamSprite")
    a.abs_ref(0x4C, "fire_next_reload")

    a.label("fire_kill")
    a.emit(0xAE, FIRE_LOOP_I & 0xFF, FIRE_LOOP_I >> 8)
    a.emit(0xA9, 0x00, 0x9D, FIRE_LIFE & 0xFF, FIRE_LIFE >> 8)

    a.label("fire_next_reload")
    a.emit(0xAE, FIRE_LOOP_I & 0xFF, FIRE_LOOP_I >> 8)
    a.label("fire_next")
    a.emit(0xE8, 0xE0, 0x05)
    a.branch(0xB0, "fire_done")
    a.abs_ref(0x4C, "fire_lp")
    a.label("fire_done")
    a.emit(0x60)

    # EmitOneFireball: finds free slot 0..4, spawns at Barba's mouth, returns C=1 if spawned
    a.label("EmitOneFireball")
    a.emit(0xAD, 0x68, 0x03, 0x0D, 0x78, 0x03)   # offscreen player?
    a.branch(0xF0, "ef_onscreen")
    a.emit(0x18, 0x60)
    a.label("ef_onscreen")
    a.emit(0xA2, 0x00)
    a.label("ef_find")
    a.emit(0xBD, FIRE_LIFE & 0xFF, FIRE_LIFE >> 8)
    a.branch(0xF0, "ef_found")
    a.emit(0xE8, 0xE0, 0x05)
    a.branch(0x90, "ef_find")
    a.emit(0x18, 0x60)                           # full
    a.label("ef_found")
    a.emit(0xAD, 0x50, 0x03, 0x29, 0x04)         # bit 2: 0=right, 4=left
    a.branch(0xD0, "ef_left")
    # Facing right: X = playerX + 12, DX = +2
    a.emit(0xAD, 0x60, 0x03, 0x18, 0x69, 12)
    a.branch(0x90, "ef_x_ok")
    a.emit(0x18, 0x60)
    a.label("ef_left")
    # Facing left: X = playerX - 12, DX = -2 ($FE)
    a.emit(0xAD, 0x60, 0x03, 0x38, 0xE9, 12)
    a.branch(0xB0, "ef_x_ok2")
    a.emit(0x18, 0x60)
    a.label("ef_x_ok")
    a.emit(0x9D, FIRE_X & 0xFF, FIRE_X >> 8)
    a.emit(0xA9, 0x02, 0x9D, FIRE_DX & 0xFF, FIRE_DX >> 8)
    a.branch(0xD0, "ef_set_y")
    a.label("ef_x_ok2")
    a.emit(0x9D, FIRE_X & 0xFF, FIRE_X >> 8)
    a.emit(0xA9, 0xFE, 0x9D, FIRE_DX & 0xFF, FIRE_DX >> 8)
    a.label("ef_set_y")
    a.emit(0xA9, 38)                             # standing mouth = feetY - 38
    a.emit(0xAC, BARBA_CROUCH & 0xFF, BARBA_CROUCH >> 8)
    a.branch(0xF0, "ef_stand_y")
    a.emit(0xA9, 14)                             # crouched mouth = feetY - 14
    a.label("ef_stand_y")
    a.emit(0x85, 0x00)
    a.emit(0xAD, 0x70, 0x03, 0x38, 0xE5, 0x00)
    a.emit(0x9D, FIRE_Y & 0xFF, FIRE_Y >> 8)
    a.emit(0xA9, 0x02, 0x9D, FIRE_DY & 0xFF, FIRE_DY >> 8)
    a.emit(0xA9, 33, 0x9D, FIRE_LIFE & 0xFF, FIRE_LIFE >> 8)  # Z2 VOLLEY_LIFE = 33
    a.emit(0x38, 0x60)                           # SEC; RTS

    # CheckFireballHit: X = fireball slot (0..4). Returns C=1 if hit enemy, C=0 otherwise.
    a.label("CheckFireballHit")
    a.emit(0xBD, FIRE_X & 0xFF, FIRE_X >> 8, 0x85, 0x07)         # $07 = FIRE_X[i]
    a.emit(0xBD, FIRE_Y & 0xFF, FIRE_Y >> 8, 0x85, 0x09)         # $09 = FIRE_Y[i]
    a.emit(0xA9, 0x00, 0x85, 0x0F)                               # $0F = 0 (Rock/Fireball hitbox)
    a.emit(0x20, 0x64, 0xDE)                                     # JSR $DE64 (projectile hitbox)
    a.emit(0xA0, 0x02)                                           # enemy slot Y = 2..5
    a.label("hit_lp")
    a.emit(0xB9, 0x20, 0x04)
    a.branch(0xF0, "hit_next")
    a.emit(0xA9, 0x08, 0x39, 0x70, 0x04)
    a.branch(0xD0, "hit_next")
    a.emit(0xB9, 0x68, 0x03, 0x19, 0x78, 0x03)
    a.branch(0xD0, "hit_next")
    a.emit(0xB9, 0x60, 0x03, 0x85, 0x00)
    a.emit(0xB9, 0x70, 0x03, 0x85, 0x02)
    a.emit(0xB9, 0x78, 0x04, 0x20, 0x9F, 0xDE)                   # JSR $DE9F (enemy hitbox)
    a.emit(0x20, 0xEA, 0xDD)                                     # JSR $DDEA (AABB overlap)
    a.branch(0xD0, "hit_found")
    a.label("hit_next")
    a.emit(0xC8, 0xC0, 0x06)
    a.branch(0x90, "hit_lp")
    a.emit(0x18, 0x60)                                           # CLC (no hit)

    a.label("hit_found")
    a.emit(0xB9, 0x78, 0x04, 0x20, 0x3B, 0xDF)                   # JSR $DF3B (enemy max HP; 0=invuln)
    a.branch(0xF0, "hit_next")
    a.emit(0x8D, HIT_MAX_HP & 0xFF, HIT_MAX_HP >> 8)
    a.emit(0x8C, HIT_ENEMY_Y & 0xFF, HIT_ENEMY_Y >> 8)
    a.emit(0xA9, 0x70, 0x20, F13_SFX_CALL & 0xFF, F13_SFX_CALL >> 8)  # JSR $8F70 (hit SFX) via WRAM
    a.emit(0xAC, HIT_ENEMY_Y & 0xFF, HIT_ENEMY_Y >> 8)
    a.emit(0xA9, 0x0C, 0x99, 0x88, 0x04)                         # $0488,Y = $0C (hurt flash)
    a.emit(0xEE, 0xB1, 0x05)                                     # INC $05B1 (drop counter)
    a.emit(0xA9, 0x04, 0x18, 0x79, 0x80, 0x04, 0x99, 0x80, 0x04) # +4 damage to $0480,Y
    a.emit(0xCD, HIT_MAX_HP & 0xFF, HIT_MAX_HP >> 8)             # >= max HP?
    a.branch(0x90, "hit_ret")
    a.emit(0xA9, 0x08, 0x19, 0x70, 0x04, 0x99, 0x70, 0x04)       # mark dying
    a.emit(0xA9, 0x1C, 0x99, 0x88, 0x04)
    a.emit(0xA9, 0x10, 0x99, 0x20, 0x04)
    a.label("hit_ret")
    a.emit(0x38, 0x60)                                           # SEC (hit!)

    # =========================================================================
    # CheckForestCoven: trigger Debbie cliff / Laura noodles ending in Forest
    # =========================================================================
    a.label("CheckForestCoven")
    a.emit(0xAD, COVEN_ENDING_FLAG & 0xFF, COVEN_ENDING_FLAG >> 8)
    a.branch(0xD0, "cfc_rts")
    a.emit(0xA5, 0x38, 0xC9, 0x01)
    a.branch(0xD0, "cfc_rts")
    a.emit(0xA5, 0xC5, 0xC9, 0x08)               # Forest BG pal ($C5=$08, $C9=$0B)
    a.branch(0xD0, "cfc_rts")
    a.emit(0xA5, 0xC9, 0xC9, 0x0B)
    a.branch(0xD0, "cfc_rts")
    a.emit(0xA5, 0x45, 0xC9, 0x01)               # $45 == 1
    a.branch(0xD0, "cfc_rts")
    a.emit(0xA5, 0x44, 0xC9, 0x10)               # $44 in [$10, $4F]
    a.branch(0x90, "cfc_rts")
    a.emit(0xC9, 0x50)
    a.branch(0xB0, "cfc_rts")
    a.emit(0xAD, 0x20, 0x04)                     # grounded ($0420 == 0)
    a.branch(0xD0, "cfc_rts")
    a.emit(0xA2, 0x02)                           # 2 = Laura
    a.emit(0xAD, 0x07, 0x05, 0xC9, 0x04)
    a.branch(0xD0, "cfc_set")
    a.emit(0xCA)                                 # 1 = Debbie
    a.label("cfc_set")
    a.emit(0x8E, COVEN_ENDING_FLAG & 0xFF, COVEN_ENDING_FLAG >> 8)
    a.emit(0xA2, 30)
    a.label("cfc_cp")
    a.abs_ref(0xBD, "CovenTramp")
    a.emit(0x9D, 0x80, 0x7C, 0xCA)
    a.branch(0x10, "cfc_cp")
    a.emit(0x4C, 0x80, 0x7C)
    a.label("cfc_rts")
    a.emit(0x60)

    a.label("CovenTramp")
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x02, 0x18, 0x6D, F13_PRG_BASE & 0xFF, F13_PRG_BASE >> 8, 0x8D, 0x01, 0x80)
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x03, 0x18, 0x6D, F13_PRG_BASE & 0xFF, F13_PRG_BASE >> 8, 0x8D, 0x01, 0x80)
    a.emit(0x4C, 0x00, 0x80)

    # =========================================================================
    # WRAM Hooks (copied to F13_PAL_HOOK $7D40 and F13_HUD_HOOK $7DC0 at reset)
    # =========================================================================
    wh = Asm6502(F13_PAL_HOOK)
    wh.emit(0x8A, 0x48, 0x98, 0x48)                          # TXA; PHA; TYA; PHA
    wh.emit(0xA5, 0x03)                                      # LDA $03
    wh.branch(0xF0, "wh_z_ok")
    wh.abs_ref(0x4C, "wh_done")
    wh.label("wh_z_ok")
    wh.emit(0xA5, 0x02, 0xC9, 0xD0)                          # Map 16B sprite palette load ($02=$D0, $04=$10)?
    wh.branch(0xD0, "wh_chk_ext")
    wh.emit(0xA5, 0x04, 0xC9, 0x10)
    wh.branch(0xF0, "wh_chk_map_sig")
    wh.abs_ref(0x4C, "wh_done")
    wh.label("wh_chk_map_sig")
    # Map screen uniquely has Pal 2 = 0F,16,35,27 ($DA=$35, $DB=$27)
    wh.emit(0xA5, 0xDA, 0xC9, 0x35)
    wh.branch(0xD0, "wh_chk_ext_sig")
    wh.emit(0xA5, 0xDB, 0xC9, 0x27)
    wh.branch(0xF0, "wh_chk_seed")
    wh.label("wh_chk_ext_sig")
    # Exterior gameplay has Wosu Pal 1 = 0F,16,27,30 ($D5=$16, $D6=$27) and $DB != $27
    wh.emit(0xA5, 0xD5, 0xC9, 0x16)
    wh.branch(0xD0, "wh_done_mid")
    wh.emit(0xA5, 0xD6, 0xC9, 0x27)
    wh.branch(0xD0, "wh_done_mid")
    wh.abs_ref(0x4C, "wh_ext_go")
    wh.label("wh_done_mid")
    wh.abs_ref(0x4C, "wh_done")
    wh.label("wh_chk_seed")
    wh.emit(0xAD, F13_CHR_BASE & 0xFF, F13_CHR_BASE >> 8)
    wh.branch(0xD0, "wh_map_apply")
    wh.emit(0xAD, F13_STAND_SEEDED & 0xFF, F13_STAND_SEEDED >> 8)
    wh.branch(0xD0, "wh_map_apply")
    # Standalone first map load: mix $31 + $7CB7 (title-wait ticks) if $7CB7 != 0
    wh.emit(0xAD, 0xB7, 0x7C)
    wh.branch(0xF0, "wh_map_apply")
    wh.emit(0xEE, F13_STAND_SEEDED & 0xFF, F13_STAND_SEEDED >> 8)
    wh.emit(0x8D, 0xF0, 0x7F, 0xA5, 0x31, 0x49, 0x5A, 0x8D, 0xF1, 0x7F)
    wh.emit(0x0D, 0xB7, 0x7C, 0x8D, 0xF2, 0x7F, 0xA5, 0x31, 0x49, 0xA5, 0x8D, 0xF3, 0x7F)
    wh.emit(0xA9, 0x01, 0x20, F13_SET_R6 & 0xFF, F13_SET_R6 >> 8)
    wh.emit(0x20, 0x09, 0x80)                                # JSR F13SeedSetup ($8009 in bank 1)
    wh.emit(0xA9, 0x04, 0x20, F13_SET_R6 & 0xFF, F13_SET_R6 >> 8)
    wh.label("wh_map_apply")
    wh.emit(0xA2, 0x03)
    wh.label("wh_mp_lp")
    wh.emit(0xBD, F13_MAP_PAL0 & 0xFF, F13_MAP_PAL0 >> 8, 0x95, 0xD0)
    wh.abs_ref(0xBD, "wh_og_pal")
    wh.emit(0x95, 0xD4)
    wh.emit(0xBD, F13_MAP_PAL3 & 0xFF, F13_MAP_PAL3 >> 8, 0x95, 0xDC)
    wh.emit(0xCA)
    wh.branch(0x10, "wh_mp_lp")
    wh.branch(0x30, "wh_done")                               # unconditional (X=$FF)
    wh.label("wh_chk_ext")
    wh.emit(0xC9, 0xD8)                                      # Exterior 8B counselor palette load ($02=$D8, $04=$08)?
    wh.branch(0xD0, "wh_done")
    wh.emit(0xA5, 0x04, 0xC9, 0x08)
    wh.branch(0xF0, "wh_ext_go")
    # Count title-screen palette flashes ($02=$D8, $04=$04) in $7CB7 for standalone entropy
    wh.emit(0xEE, 0xB7, 0x7C)
    wh.branch(0xD0, "wh_done")
    wh.branch(0xF0, "wh_done")
    wh.label("wh_ext_go")
    wh.emit(0xAE, 0x07, 0x05, 0xE0, 0x06)                    # $0507 < 6?
    wh.branch(0xB0, "wh_done")
    wh.emit(0xE0, 0x03)                                      # skip Laura (3)
    wh.branch(0xF0, "wh_done")
    wh.emit(0xE0, 0x04)                                      # skip Debbie (4)
    wh.branch(0xF0, "wh_done")
    wh.emit(0x8A, 0x0A, 0x0A, 0xAA, 0xA0, 0x00)              # X = slot * 4, Y = 0
    wh.label("wh_ext_lp")
    wh.emit(0xBD, F13_EXT_PALS & 0xFF, F13_EXT_PALS >> 8)
    wh.emit(0x99, 0xD8, 0x00, 0x99, 0xDC, 0x00)
    wh.emit(0xE8, 0xC8, 0xC0, 0x04)
    wh.branch(0xD0, "wh_ext_lp")
    wh.emit(0xA9, 0x0F, 0x85, 0xDF)                          # Sprite 0 color 3 stays $0F
    wh.label("wh_done")
    wh.emit(0x68, 0xA8, 0x68, 0xAA)                          # PLA; TAY; PLA; TAX
    wh.emit(0xA9, 0x01, 0x85, 0x2C, 0x60)                    # LDA #$01; STA $2C; RTS
    wh.label("wh_og_pal")
    wh.emit(0x0F, 0x16, 0x27, 0x30)
    wram_pal_bytes = wh.finish()
    assert len(wram_pal_bytes) <= (F13_HUD_HOOK - F13_PAL_HOOK), f"WramPalHook too large: {len(wram_pal_bytes)}"

    a.label("WramPalHook")
    a.emit(*wram_pal_bytes)
    a.label("WramHudHook")
    a.emit(0xB9, F13_HUD_TILES & 0xFF, F13_HUD_TILES >> 8, 0x60)  # LDA F13_HUD_TILES,Y; RTS

    # =========================================================================
    # F13SeedSetup ($8009): populate seeded Barba roster in WRAM $7CA0-$7CD7
    # =========================================================================
    a.label("F13SeedSetup")
    # 1. Always lock Slot 0 (BARBA) to OG Barba + set Laura/Debbie HUD tiles
    a.emit(0xA9, 0x00, 0x8D, F13_MAP_DESC + 0 & 0xFF, F13_MAP_DESC + 0 >> 8)
    a.emit(0xA9, 0x2F, 0x8D, F13_MAP_DESC + 1 & 0xFF, F13_MAP_DESC + 1 >> 8)
    a.emit(0xA9, 0x22, 0x8D, F13_MAP_DESC + 2 & 0xFF, F13_MAP_DESC + 2 >> 8)
    a.emit(0xA9, 0x01, 0x8D, F13_MAP_DESC + 3 & 0xFF, F13_MAP_DESC + 3 >> 8)
    a.emit(0xA9, 0x60, 0x8D, F13_HUD_TILES + 0 & 0xFF, F13_HUD_TILES + 0 >> 8)
    a.emit(0xA9, 0x6C, 0x8D, F13_HUD_TILES + 3 & 0xFF, F13_HUD_TILES + 3 >> 8)
    a.emit(0xA9, 0xF8, 0x8D, F13_HUD_TILES + 4 & 0xFF, F13_HUD_TILES + 4 >> 8)
    a.emit(0xA2, 0x03)
    a.label("ss_og_ext")
    a.abs_ref(0xBD, "OgPalData")
    a.emit(0x9D, F13_EXT_PALS & 0xFF, F13_EXT_PALS >> 8, 0xCA)
    a.branch(0x10, "ss_og_ext")

    # 2. Check if seeded (Z2 $7BFE != 0 OR standalone title-seeded $7CB6 != 0)
    a.emit(0xAD, F13_CHR_BASE & 0xFF, F13_CHR_BASE >> 8)
    a.branch(0xD0, "ss_do_rng")
    a.emit(0xAD, F13_STAND_SEEDED & 0xFF, F13_STAND_SEEDED >> 8)
    a.branch(0xD0, "ss_do_rng")
    # Default showcase preset for cold unseeded boot
    a.emit(0xA9, 0x00)
    a.emit(0x8D, F13_TMP_P0_IDX & 0xFF, F13_TMP_P0_IDX >> 8)   # Emerald
    a.emit(0x8D, F13_TMP_P3_IDX & 0xFF, F13_TMP_P3_IDX >> 8)   # Frost
    a.emit(0x8D, F13_TMP_PERM & 0xFF, F13_TMP_PERM >> 8)       # perm 0: C, G, X
    a.emit(0x8D, F13_TMP_C_MODE & 0xFF, F13_TMP_C_MODE >> 8)   # Pal 2 Crimson Roar
    a.emit(0xA9, 0x01, 0x8D, F13_TMP_H0 & 0xFF, F13_TMP_H0 >> 8)  # Wyrm profile
    a.emit(0xA9, 0x03, 0x8D, F13_TMP_H1 & 0xFF, F13_TMP_H1 >> 8)  # Crowned Frost mugshot
    a.emit(0xA9, 0x02, 0x8D, F13_TMP_H2 & 0xFF, F13_TMP_H2 >> 8)
    a.abs_ref(0x4C, "ss_build")

    a.label("ss_do_rng")
    a.emit(0xAD, 0xF0, 0x7F, 0x4D, 0xF2, 0x7F, 0x4D, 0xF4, 0x7F, 0x4D, 0xF6, 0x7F)
    a.emit(0x8D, F13_SEED_LO & 0xFF, F13_SEED_LO >> 8)
    a.emit(0xAD, 0xF1, 0x7F, 0x4D, 0xF3, 0x7F, 0x4D, 0xF5, 0x7F, 0x4D, 0xF7, 0x7F)
    a.emit(0x8D, F13_SEED_HI & 0xFF, F13_SEED_HI >> 8)
    a.emit(0x0D, F13_SEED_LO & 0xFF, F13_SEED_LO >> 8)
    a.branch(0xD0, "ss_mix")
    a.emit(0xA9, 0xA5, 0x8D, F13_SEED_LO & 0xFF, F13_SEED_LO >> 8)
    a.emit(0xA9, 0x5A, 0x8D, F13_SEED_HI & 0xFF, F13_SEED_HI >> 8)
    a.label("ss_mix")
    a.emit(0xA2, 0x04)
    a.label("ss_warm")
    a.abs_ref(0x20, "SeedNextRng")
    a.emit(0xCA)
    a.branch(0xD0, "ss_warm")

    a.abs_ref(0x20, "SeedNextRng")
    a.emit(0x29, 0x03, 0x8D, F13_TMP_P0_IDX & 0xFF, F13_TMP_P0_IDX >> 8)
    a.abs_ref(0x20, "SeedNextRng")
    a.emit(0x29, 0x07, 0x8D, F13_TMP_P3_IDX & 0xFF, F13_TMP_P3_IDX >> 8)
    a.abs_ref(0x20, "SeedNextRng")
    a.emit(0x29, 0x07, 0xC9, 0x06)
    a.branch(0x90, "ss_perm_ok")
    a.emit(0xE9, 0x06)                                       # C=1 from CMP >= 6 -> A -= 6
    a.label("ss_perm_ok")
    a.emit(0x8D, F13_TMP_PERM & 0xFF, F13_TMP_PERM >> 8)
    a.abs_ref(0x20, "SeedNextRng")
    a.emit(0x29, 0x01, 0x8D, F13_TMP_C_MODE & 0xFF, F13_TMP_C_MODE >> 8)

    # Distinct heads H0, H1, H2 in 0..4
    a.abs_ref(0x20, "SeedNextRng")
    a.emit(0x29, 0x07, 0xC9, 0x05)
    a.branch(0x90, "ss_h0_ok")
    a.emit(0xE9, 0x05)
    a.label("ss_h0_ok")
    a.emit(0x8D, F13_TMP_H0 & 0xFF, F13_TMP_H0 >> 8)

    a.abs_ref(0x20, "SeedNextRng")
    a.emit(0x29, 0x03, 0x18, 0x69, 0x01)
    a.emit(0x6D, F13_TMP_H0 & 0xFF, F13_TMP_H0 >> 8, 0xC9, 0x05)
    a.branch(0x90, "ss_h1_ok")
    a.emit(0xE9, 0x05)
    a.label("ss_h1_ok")
    a.emit(0x8D, F13_TMP_H1 & 0xFF, F13_TMP_H1 >> 8)

    a.abs_ref(0x20, "SeedNextRng")
    a.emit(0x29, 0x01, 0x18, 0x69, 0x01)
    a.emit(0x6D, F13_TMP_H1 & 0xFF, F13_TMP_H1 >> 8, 0xC9, 0x05)
    a.branch(0x90, "ss_h2_mod")
    a.emit(0xE9, 0x05)
    a.label("ss_h2_mod")
    a.emit(0xCD, F13_TMP_H0 & 0xFF, F13_TMP_H0 >> 8)
    a.branch(0xD0, "ss_h2_ok")
    a.emit(0x18, 0x69, 0x01, 0xC9, 0x05)
    a.branch(0x90, "ss_h2_ok")
    a.emit(0xE9, 0x05)
    a.label("ss_h2_ok")
    a.emit(0x8D, F13_TMP_H2 & 0xFF, F13_TMP_H2 >> 8)

    # 3. Copy chosen Pal 0 and Pal 3 into WRAM map palette slots
    a.label("ss_build")
    a.emit(0xAD, F13_TMP_P0_IDX & 0xFF, F13_TMP_P0_IDX >> 8, 0x0A, 0x0A, 0xAA)
    a.emit(0xA0, 0x00)
    a.label("ss_cp_p0")
    a.abs_ref(0xBD, "Pal0Table")
    a.emit(0x99, F13_MAP_PAL0 & 0xFF, F13_MAP_PAL0 >> 8, 0xE8, 0xC8, 0xC0, 0x04)
    a.branch(0xD0, "ss_cp_p0")

    a.emit(0xAD, F13_TMP_P3_IDX & 0xFF, F13_TMP_P3_IDX >> 8, 0x0A, 0x0A, 0xAA)
    a.emit(0xA0, 0x00)
    a.label("ss_cp_p3")
    a.abs_ref(0xBD, "Pal3Table")
    a.emit(0x99, F13_MAP_PAL3 & 0xFF, F13_MAP_PAL3 >> 8, 0xE8, 0xC8, 0xC0, 0x04)
    a.branch(0xD0, "ss_cp_p3")

    # 4. Populate slots 1, 2, 5 (k = 0, 1, 2)
    a.emit(0xA9, 0x00, 0x8D, F13_TMP_K & 0xFF, F13_TMP_K >> 8)
    a.label("ss_slot_lp")
    a.emit(0xAD, F13_TMP_PERM & 0xFF, F13_TMP_PERM >> 8, 0x0A, 0x18)
    a.emit(0x6D, F13_TMP_PERM & 0xFF, F13_TMP_PERM >> 8)     # A = perm * 3
    a.emit(0x18, 0x6D, F13_TMP_K & 0xFF, F13_TMP_K >> 8, 0xA8)
    a.abs_ref(0xB9, "PermTable")                             # A = channel (0=G, 1=X, 2=C)
    a.branch(0xD0, "ss_not_g")
    # Channel 0 (G): Pal 0 Green Wyrm
    a.emit(0xAE, F13_TMP_H0 & 0xFF, F13_TMP_H0 >> 8)
    a.abs_ref(0xBD, "HeadPool")
    a.emit(0x48)                                             # push tile (both map & hud)
    a.emit(0xA9, 0x00, 0x48)                                 # push map attr = 0
    a.emit(0xA0, 0x00)
    a.label("ss_g_ext")
    a.emit(0xB9, F13_MAP_PAL0 & 0xFF, F13_MAP_PAL0 >> 8)
    a.emit(0x99, 0xF0, 0x7C, 0xC8, 0xC0, 0x04)               # staging $7CF0..$7CF3
    a.branch(0xD0, "ss_g_ext")
    a.abs_ref(0x4C, "ss_write_slot")

    a.label("ss_not_g")
    a.emit(0xC9, 0x01)
    a.branch(0xD0, "ss_is_c")
    # Channel 1 (X): Pal 3 Showcase
    a.emit(0xAE, F13_TMP_H1 & 0xFF, F13_TMP_H1 >> 8)
    a.abs_ref(0xBD, "HeadPool")
    a.emit(0x48, 0xA9, 0x03, 0x48)                           # push tile, push attr = 3
    a.emit(0xA0, 0x00)
    a.label("ss_x_ext")
    a.emit(0xB9, F13_MAP_PAL3 & 0xFF, F13_MAP_PAL3 >> 8)
    a.emit(0x99, 0xF0, 0x7C, 0xC8, 0xC0, 0x04)
    a.branch(0xD0, "ss_x_ext")
    a.abs_ref(0x4C, "ss_write_slot")

    a.label("ss_is_c")
    a.emit(0xAD, F13_TMP_C_MODE & 0xFF, F13_TMP_C_MODE >> 8)
    a.branch(0xD0, "ss_c_blaze")
    # Channel 2 mode 0: Pal 2 Crimson Roar (map tile $14, attr $02, hud tile $04)
    a.emit(0xA9, 0x04, 0x48)                                 # push hud tile $04
    a.emit(0xA9, 0x14, 0x48)                                 # push map tile $14
    a.emit(0xA9, 0x02, 0x48)                                 # push map attr $02
    a.emit(0xA2, 0x03)
    a.label("ss_c0_ext")
    a.abs_ref(0xBD, "CrimExtPal")
    a.emit(0x9D, 0xF0, 0x7C, 0xCA)
    a.branch(0x10, "ss_c0_ext")
    a.abs_ref(0x4C, "ss_write_split")

    a.label("ss_c_blaze")
    # Channel 2 mode 1: Pal 1 Blaze (distinct head H2, attr $01, gold/crimson ext)
    a.emit(0xAE, F13_TMP_H2 & 0xFF, F13_TMP_H2 >> 8)
    a.abs_ref(0xBD, "HeadPool")
    a.emit(0x48, 0xA9, 0x01, 0x48)                           # push tile, push attr = 1
    a.emit(0xA2, 0x03)
    a.label("ss_c1_ext")
    a.abs_ref(0xBD, "BlazeExtPal")
    a.emit(0x9D, 0xF0, 0x7C, 0xCA)
    a.branch(0x10, "ss_c1_ext")

    a.label("ss_write_slot")
    # Stack has: [hud=map_tile] [attr] -> duplicate tile for split path
    a.emit(0x68, 0xAA, 0x68, 0x48, 0x48, 0x8A, 0x48)         # stack: [hud] [map] [attr]

    a.label("ss_write_split")
    # Stack top -> bottom: attr, map_tile, hud_tile
    a.emit(0xAE, F13_TMP_K & 0xFF, F13_TMP_K >> 8)
    a.abs_ref(0xBC, "DescOffTable")                          # Y = desc offset (4, 8, 12)
    a.emit(0x68, 0x99, (F13_MAP_DESC + 3) & 0xFF, (F13_MAP_DESC + 3) >> 8)  # attr
    a.emit(0x68, 0x99, (F13_MAP_DESC + 0) & 0xFF, (F13_MAP_DESC + 0) >> 8)  # map_tile
    a.emit(0xA9, 0x2F, 0x99, (F13_MAP_DESC + 1) & 0xFF, (F13_MAP_DESC + 1) >> 8)
    a.emit(0xA9, 0x22, 0x99, (F13_MAP_DESC + 2) & 0xFF, (F13_MAP_DESC + 2) >> 8)
    a.abs_ref(0xBC, "SlotIdxTable")                          # Y = slot (1, 2, 5)
    a.emit(0x68, 0x99, F13_HUD_TILES & 0xFF, F13_HUD_TILES >> 8)
    a.emit(0x98, 0x0A, 0x0A, 0xA8)                           # Y = slot * 4
    a.emit(0xA2, 0x00)
    a.label("ss_wr_ext")
    a.emit(0xBD, 0xF0, 0x7C, 0x99, F13_EXT_PALS & 0xFF, F13_EXT_PALS >> 8)
    a.emit(0xC8, 0xE8, 0xE0, 0x04)
    a.branch(0xD0, "ss_wr_ext")

    a.emit(0xEE, F13_TMP_K & 0xFF, F13_TMP_K >> 8)
    a.emit(0xAD, F13_TMP_K & 0xFF, F13_TMP_K >> 8, 0xC9, 0x03)
    a.branch(0xB0, "ss_done")
    a.abs_ref(0x4C, "ss_slot_lp")
    a.label("ss_done")
    a.emit(0x60)

    a.label("SeedNextRng")
    a.emit(0xAD, F13_SEED_LO & 0xFF, F13_SEED_LO >> 8, 0x0A)
    a.emit(0x2E, F13_SEED_HI & 0xFF, F13_SEED_HI >> 8)
    a.branch(0x90, "snr_nox")
    a.emit(0x49, 0x2D)
    a.label("snr_nox")
    a.emit(0x8D, F13_SEED_LO & 0xFF, F13_SEED_LO >> 8)
    a.emit(0x4D, F13_SEED_HI & 0xFF, F13_SEED_HI >> 8, 0x60)

    a.label("OgPalData")
    a.emit(0x0F, 0x16, 0x27, 0x30)
    a.label("CrimExtPal")
    a.emit(0x0F, 0x06, 0x16, 0x27)
    a.label("BlazeExtPal")
    a.emit(0x0F, 0x16, 0x28, 0x30)
    a.label("Pal0Table")
    a.emit(
        0x0F, 0x0A, 0x2A, 0x37,  # 0: Emerald Wyrm
        0x0F, 0x0B, 0x2B, 0x37,  # 1: Jade Sea-Wyrm
        0x0F, 0x09, 0x29, 0x37,  # 2: Toxic Moss Wyrm
        0x0F, 0x1A, 0x28, 0x37,  # 3: Gilded Forest Wyrm
    )
    a.label("Pal3Table")
    a.emit(
        0x0F, 0x11, 0x21, 0x30,  # 0: Frost / Sky
        0x0F, 0x03, 0x14, 0x30,  # 1: Amethyst Void
        0x0F, 0x00, 0x10, 0x30,  # 2: Obsidian Steel
        0x0F, 0x06, 0x16, 0x37,  # 3: Blood Ruby
        0x0F, 0x07, 0x27, 0x38,  # 4: Solar Gold
        0x0F, 0x0C, 0x2C, 0x30,  # 5: Glacier Cyan
        0x0F, 0x06, 0x26, 0x37,  # 6: Magma Coral
        0x0F, 0x04, 0x24, 0x30,  # 7: Royal Plum
    )
    a.label("HeadPool")
    a.emit(0x04, 0x08, 0x64, 0x68, 0xFC)
    a.label("PermTable")
    a.emit(
        2, 0, 1,
        0, 1, 2,
        1, 2, 0,
        2, 1, 0,
        1, 0, 2,
        0, 2, 1,
    )
    a.label("SlotIdxTable")
    a.emit(1, 2, 5)
    a.label("DescOffTable")
    a.emit(4, 8, 12)

    a.buf[pal_len_patch_idx] = len(wram_pal_bytes)
    code = a.finish()
    assert len(code) <= 8192, f"Bank 1 overflow: {len(code)}"
    bank1 = bytearray(b"\xFF" * 8192)
    bank1[: len(code)] = code
    return bytes(bank1)
