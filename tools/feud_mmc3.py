"""Standard iNES 1.0 Mapper 4 (MMC3) multi-lineup cast, WRAM, and DPCM roar support for Family Feud."""
from __future__ import annotations

from pathlib import Path

import feud_art
import feud_cast
import feud_engine
import feud_wram
from asm6502 import Asm6502

# Extra MMC3 WRAM state ($60B8..$60CF, unused in pure CHR-ROM mode)
W_MMC3_P1_L   = 0x60B8  # 0..2 active Barba lineup index
W_MMC3_CPU_L  = 0x60B9  # 0..5 active Z2 lineup index
W_CHR_MAP     = 0x60C0  # 16 bytes: logical 4KB CHR bank 0..15 -> physical MMC3 4KB bank 0..63

# WRAM block storage ($6600..$6C73 = 1,652 B)
MMC3_P1_ST_BASE    = 0x6600  # 390 B ($6600..$6785)
MMC3_CPU_ST_BASE   = 0x6786  # 390 B ($6786..$690B)
MMC3_P1_OV_BASE    = 0x6910  # 100 B ($6910..$6973)
MMC3_CPU_OV_BASE   = 0x6974  # 100 B ($6974..$69D7)
MMC3_HOST_BUZ_BASE = 0x6A00  # 124 B ($6A00..$6A7B): blocks 112,113,119,120,121,122
MMC3_ST_ATTR_TPLS  = 0x6A80  # 78 B ($6A80..$6ACD): 3 x 26B [4,6,pal*24] for pal 1..3
MMC3_FO_OAM_ATTR   = 0x6ACE  # 86 B ($6ACE..$6B23): [7,12,1*84]
MMC3_P1_FO_BASE    = 0x6B30  # 172 B ($6B30..$6BDB): active seat only (2 x 7x12)
MMC3_CPU_FO_BASE   = 0x6BE0  # 148 B ($6BE0..$6C73): active seat only (2 x 6x12)

# 256 KB CHR-ROM bank layout (64 x 4 KB banks; 0x00..0x1F base, 0x20..0x3C extra)
B_ST_BANKS = (0x05, 0x20, 0x21)
B_FO_BANKS = (0x02, 0x22, 0x23)
Z_ST_BANKS = (0x06, 0x07, 0x24, 0x25, 0x26, 0x27)
Z_FO_BANKS = (0x03, 0x04, 0x28, 0x29, 0x2A, 0x2B)
# 3 Barba x 6 Z2 = 18 Overview banks: (0,0) -> 0x00, others -> 0x2C..0x3C
OV_BANKS = tuple(
    tuple(0x00 if (bi == 0 and zi == 0) else (0x2B + bi * 6 + zi) for zi in range(6))
    for bi in range(3)
)

# Zero-repeat alternating palette rows from BARBA_ALT_PATS (no cyan palette 0 on Barbas)
BARBA_LINEUP_PALS = (
    (2, 1, 3, 2, 1),
    (3, 1, 2, 3, 1),
    (1, 2, 3, 1, 2),
)


def _encode_block(w: int, h: int, tids: list[int]) -> bytes:
    assert len(tids) == w * h
    return bytes((w, h)) + bytes(tids)


def _stage_attr_bytes(pals: tuple[int, ...] | list[int]) -> bytes:
    """Compute the 14-byte Stage Close-Up attribute block for seats [0..4] (P1/CPU order)."""
    # Note: Stage Close-Up writes the same 14-byte table reversed for P1 vs CPU.
    # Let caller pass pals in display order [left..right].
    p = list(pals)
    b0 = (p[0] << 2) | (p[0] << 6)
    b1 = p[0] | (p[0] << 4) | (p[1] << 2) | (p[1] << 6)
    b2 = p[1] | (p[1] << 4) | (p[2] << 2) | (p[2] << 6)
    b3 = p[2] | (p[2] << 4) | (p[3] << 2) | (p[3] << 6)
    b4 = p[3] | (p[3] << 4) | (p[4] << 2) | (p[4] << 6)
    b5 = p[4] | (p[4] << 4)
    row_top = [b0, b1, b2, b3, b4, b5, 0x00, 0x00]
    row_bot = [x & 0x0F for x in (b0, b1, b2, b3, b4, b5)]
    return bytes(row_top + row_bot)


def _ov_attr_bytes(pals: tuple[int, ...] | list[int], *, is_cpu: bool) -> bytes:
    """Compute the 3-byte Stage Overview attribute bytes ($23E0..$23E2 P1 or $23E5..$23E7 CPU)."""
    p = list(pals)
    if not is_cpu:
        # P1 ($23E0..$23E2): cols 2..11 -> seats [none/4], [3/2], [1/0]
        a0 = (p[4] << 2) | (p[4] << 6)
        a1 = p[2] | (p[2] << 4) | (p[3] << 2) | (p[3] << 6)
        a2 = p[0] | (p[0] << 4) | (p[1] << 2) | (p[1] << 6)
        return bytes((a0, a1, a2))
    # CPU ($23E5..$23E7): cols 20..29 -> seats [0/1], [2/3], [4/none]
    a0 = p[1] | (p[1] << 4) | (p[0] << 2) | (p[0] << 6)
    a1 = p[3] | (p[3] << 4) | (p[2] << 2) | (p[2] << 6)
    a2 = p[4] | (p[4] << 4) | (p[4] << 2) | (p[4] << 6)
    return bytes((a0, a1, a2))


def build_mmc3_cast_assets(
    prg_patched: bytes,
    chr_base128: bytes,
    feud_orig_rom: bytes,
    z2_rom: bytes,
) -> dict[str, object]:
    """Compile 256 KB CHR-ROM (3 Barba x 6 Z2 lineups) + Bank 5/6 lineup tables for MMC3."""
    prg_orig = feud_orig_rom[16 : 16 + 32768]
    chr_orig = feud_orig_rom[16 + 32768 : 16 + 32768 + 131072]

    cfg = feud_cast.load_cast_config()
    barba_pool, z2_pool = feud_cast.build_all_cast_pools(z2_rom, cfg)
    rt = feud_cast.get_runtime_cast_tables(cfg)
    z2_pal_slots = list(rt['z2_pal_slots'])

    # 3 Barba lineups (15 seats covering all 13 Barbas) & 6 Z2 lineups (30 seats covering 30 Z2 chars)
    b_lineups = [
        [(i * 5 + s) % len(barba_pool) for s in range(5)]
        for i in range(3)
    ]
    z_lineups = [
        [(i * 5 + s) % len(z2_pool) for s in range(5)]
        for i in range(6)
    ]

    chr256 = bytearray(b'\x00' * (256 * 1024))
    chr256[0 : 131072] = chr_base128
    # Note: chr_base128 already has BARBA'S BEEF title, branding (incl. 00 "BB"), blue 'k' in 0B,
    # FIRST..FIFTH FEUD banners + walking host in 0C, and Z2 puzzles in 10.
    # Restore vanilla protected tiles in 00, 02, 03, 04, 05, 06, 07 before multi-lineup packing.
    for b in (0x00, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07):
        chr256[b * 4096 : (b + 1) * 4096] = chr_orig[b * 4096 : (b + 1) * 4096]
    # Re-apply Bank 00 "BB" podium emblem so all cloned Overview banks inherit it
    feud_art.apply_barba_branding(bytearray(prg_patched), chr256)

    scr0d = set(feud_art._decode_rle_screen(prg_orig, chr_orig, 0x0D)[:960])
    scr0e = set(feud_art._decode_rle_screen(prg_orig, chr_orig, 0x0E)[:960])
    st_ui = set(range(0xB5, 0xBB)) | set(feud_art._get_block(prg_orig, 153)[2])
    avail_st_p1 = [t for t in range(4, 256) if t not in (scr0d | st_ui)]
    avail_st_cpu = [t for t in range(4, 256) if t not in (scr0e | st_ui)]

    scr07 = set(feud_art._decode_rle_screen(prg_orig, chr_orig, 7)[:960])
    ov_keep = scr07 | set(range(0x00, 0x5B)) | {0xC0, 0xC1, 0xCC} | set(range(0xD6, 0xFB))
    ov_free = [t for t in range(256) if t not in ov_keep]

    def pack_stage(bank: int, tmpl: int, avail: list[int], seats: list[int], pool: list[feud_cast.CastCharacter]) -> bytes:
        chr256[bank * 4096 : (bank + 1) * 4096] = chr_orig[tmpl * 4096 : (tmpl + 1) * 4096]
        if tmpl == 0x06:
            chr256[bank * 4096 + 0xB5 * 16 : bank * 4096 + 0xBB * 16] = b'\x00' * (6 * 16)
        grids: dict[int, list[str]] = {}
        for s, ci in enumerate(seats):
            v = pool[ci].variants[s % 3]
            for f_i in range(3):
                grids[s * 3 + f_i] = feud_art._decode_local_grid(v.stage_tiles, v.stage_maps[f_i * 24 : (f_i + 1) * 24], 4, 6)
        pk = feud_art._pack_bank(chr256, bank, avail, grids)
        out = bytearray()
        for s in range(5):
            for f_i in range(3):
                out.extend(_encode_block(4, 6, pk[s * 3 + f_i]))
        assert len(out) == 390
        return bytes(out)

    def pack_fo_bank(
        bank: int,
        tmpl: int,
        base_idx: int,
        screen_idx: int,
        seats: list[int],
        pool: list[feud_cast.CastCharacter],
        is_z2: bool,
    ) -> tuple[bytes, dict[int, list[int]]]:
        chr256[bank * 4096 : (bank + 1) * 4096] = chr_orig[tmpl * 4096 : (tmpl + 1) * 4096]
        nt = feud_art._decode_rle_screen(prg_orig, chr_orig, screen_idx)
        prot = {nt[r * 32 + c] for r in range(20, 28) for c in range(32) if nt[r * 32 + c] != 0}
        for b_idx in (base_idx + 14, base_idx + 15):
            _, _, bt, _, _ = feud_art._get_block(prg_orig, b_idx)
            prot.update(t for t in bt if t != 0)
        avail = [t for t in range(0x01, 0xE1) if t not in prot]
        orig = {seat: feud_art._decode_orig_block(prg_orig, chr_orig, tmpl, base_idx + seat) for seat in range(5)}

        # Pack Host busts FIRST so they get identical deterministic tile IDs across all banks sharing tmpl!
        grids_fo: dict[int, list[str]] = {
            base_idx + 5: feud_art._build_host_bust_4x6(z2_rom, 'closed', flip_h=True),
            base_idx + 6: feud_art._build_host_bust_4x6(z2_rom, 'closed', flip_h=True),
            base_idx + 12: feud_art._build_host_bust_4x6(z2_rom, 'closed', flip_h=False),
            base_idx + 13: feud_art._build_host_bust_4x6(z2_rom, 'open', flip_h=True),
        }
        lip_row0 = list('22311111' + '11111111' * 4 + '11111322')
        lip_row1 = list('22333333' + '33333333' * 4 + '33333322')
        for seat, ci in enumerate(seats):
            v = pool[ci].variants[seat % 3]
            w_src = 6 if is_z2 else 7
            for f_i in range(2):
                upper = feud_art._decode_local_grid(v.fo_tiles, v.fo_maps[f_i * w_src * 10 : (f_i + 1) * w_src * 10], w_src, 10)
                if is_z2:
                    canvas = [list(row) for row in upper] + [lip_row0[:], lip_row1[:]] + [['2'] * 48 for _ in range(14)]
                else:
                    canvas = [list(row) for row in upper] + [['0'] * 56 for _ in range(16)]
                grids_fo[seat * 2 + f_i] = [''.join(row) for row in canvas]

        pk = feud_art._pack_bank(chr256, bank, avail, grids_fo, protected_pool_tiles=sorted(prot))
        out = bytearray()
        blk_w = 6 if is_z2 else 7
        for seat in range(5):
            for f_i in range(2):
                out.extend(_encode_block(blk_w, 12, pk[seat * 2 + f_i]))
        assert len(out) == (740 if is_z2 else 860)
        host_blocks = {
            base_idx + 5: pk[base_idx + 5],
            base_idx + 6: pk[base_idx + 6],
            base_idx + 12: pk[base_idx + 12],
            base_idx + 13: pk[base_idx + 13],
        }
        return bytes(out), host_blocks

    # Pack Overview banks (3 x 6 = 18 banks)
    # Since Overview blocks 123..152 depend on BOTH Barba & Z2 tile IDs, keep tile IDs decoupled per pair:
    # We pack Overview blocks for (bi, zi) and store the 100B P1 OV blocks + 100B CPU OV blocks?
    # Wait: P1 OV tiles sit in ov_free[0..59] and CPU OV tiles sit in ov_free[60..119], OR better:
    # Each Barba lineup bi uses the SAME tile slots in ov_free[0..59] across ALL 6 Z2 lineups zi!
    # Wait: how? Pack Barba bi into ov_free[0..59] ONCE -> get fixed P1 OV block IDs AND fixed tiles!
    # Wait: Z2 zi uses <= 60 tiles too? Let's verify! Each character is <= 13 tiles, 5 chars <= 65 tiles!
    # Let's check: 5 Barbas max OV tiles vs 5 Z2 max OV tiles -> if Barba uses <= 62 and Z2 uses <= 62,
    # ov_free has 125 tiles! Let's pack Barba into ov_free[:63] (with row0_priority!) and Z2 into ov_free[63:]!
    ov_p1_avail = ov_free[:63]
    ov_cpu_avail = ov_free[63:]
    assert len(ov_cpu_avail) >= 62

    # Pack Barba OV tiles into ov_p1_avail ONCE per bi (independent of zi!)
    b_ov_chr_patches: list[tuple[list[tuple[int, bytes]], bytes]] = []
    for bi, b_seats in enumerate(b_lineups):
        tmp_chr = bytearray(chr256[: 4096])
        b_grids = {}
        for s, ci in enumerate(b_seats):
            v = barba_pool[ci].variants[s % 3]
            for f_i in range(2):
                b_grids[s * 2 + f_i] = feud_art._decode_local_grid(v.ov_tiles, v.ov_maps[f_i * 8 : (f_i + 1) * 8], 2, 4)
        pk = feud_art._pack_bank(tmp_chr, 0, ov_p1_avail, b_grids, row0_priority=True)
        patches = [(t, bytes(tmp_chr[t * 16 : (t + 1) * 16])) for t in ov_p1_avail]
        ov_bytes = bytearray()
        for s in range(5):
            for f_i in range(2):
                ov_bytes.extend(_encode_block(2, 4, pk[s * 2 + f_i]))
        b_ov_chr_patches.append((patches, bytes(ov_bytes)))

    # Pack Z2 OV tiles into ov_cpu_avail ONCE per zi (independent of bi!)
    z_ov_chr_patches: list[tuple[list[tuple[int, bytes]], bytes]] = []
    for zi, z_seats in enumerate(z_lineups):
        tmp_chr = bytearray(chr256[: 4096])
        z_grids = {}
        for s, ci in enumerate(z_seats):
            v = z2_pool[ci].variants[s % 3]
            for f_i in range(2):
                z_grids[s * 2 + f_i] = feud_art._decode_local_grid(v.ov_tiles, v.ov_maps[f_i * 8 : (f_i + 1) * 8], 2, 4)
        pk = feud_art._pack_bank(tmp_chr, 0, ov_cpu_avail, z_grids, row0_priority=True)
        patches = [(t, bytes(tmp_chr[t * 16 : (t + 1) * 16])) for t in ov_cpu_avail]
        ov_bytes = bytearray()
        for s in range(5):
            for f_i in range(2):
                ov_bytes.extend(_encode_block(2, 4, pk[s * 2 + f_i]))
        z_ov_chr_patches.append((patches, bytes(ov_bytes)))

    # Stamp all 18 (bi, zi) Overview banks cleanly!
    base_00_template = bytes(chr256[0 : 4096])
    for bi in range(3):
        for zi in range(6):
            bank = OV_BANKS[bi][zi]
            off_b = bank * 4096
            chr256[off_b : off_b + 4096] = base_00_template
            for t, data in b_ov_chr_patches[bi][0]:
                chr256[off_b + t * 16 : off_b + (t + 1) * 16] = data
            for t, data in z_ov_chr_patches[zi][0]:
                chr256[off_b + t * 16 : off_b + (t + 1) * 16] = data

    # Build PRG Bank 5 (Barba 0..2 lineups * 1024B + Host/Buzzer 112..122 at $AC00)
    prg_buf = bytearray(prg_patched)
    bank5 = bytearray(b'\xFF' * 8192)
    b_host_ref: dict[int, list[int]] | None = None
    for bi, b_seats in enumerate(b_lineups):
        st_b = pack_stage(B_ST_BANKS[bi], 0x05, avail_st_p1, b_seats, barba_pool)
        ov_b = b_ov_chr_patches[bi][1]
        fo_b, host_b = pack_fo_bank(B_FO_BANKS[bi], 0x02, 75, 8, b_seats, barba_pool, False)
        if b_host_ref is None:
            b_host_ref = host_b
            for blk_id, tids in host_b.items():
                feud_art._write_block_and_attr(prg_buf, blk_id, tids)
        else:
            assert host_b == b_host_ref, f'Barba Host bust tile mismatch on lineup {bi}'
        pals = BARBA_LINEUP_PALS[bi]
        # Stage Close-Up P1 display order is reversed ([4, 2, 3, 1, 0])
        st_attr = _stage_attr_bytes([pals[s] for s in (4, 2, 3, 1, 0)])
        ov_attr = _ov_attr_bytes(pals, is_cpu=False)
        rec = st_b + ov_b + fo_b + st_attr + ov_attr + bytes(pals)
        assert len(rec) == 1372
        bank5[bi * 1372 : bi * 1372 + len(rec)] = rec

    # Intact Host/Buzzer blocks 112, 113, 119, 120, 121, 122 (in CHR 04 template!) -> Bank 5 $AC00
    z_host_ref_even: dict[int, list[int]] | None = None
    z_host_ref_odd: dict[int, list[int]] | None = None
    bank6 = bytearray(b'\xFF' * 8192)
    for zi, z_seats in enumerate(z_lineups):
        st_b = pack_stage(Z_ST_BANKS[zi], 0x06, avail_st_cpu, z_seats, z2_pool)
        ov_b = z_ov_chr_patches[zi][1]
        fo_b, host_b = pack_fo_bank(Z_FO_BANKS[zi], 0x03, 91, 9, z_seats, z2_pool, True)
        if zi == 0:
            for blk_id, tids in host_b.items():
                feud_art._write_block_and_attr(prg_buf, blk_id, tids)
            z_host_ref_even = host_b
        else:
            assert host_b == z_host_ref_even, f'Z2 FO host mismatch on lineup {zi}'
        pals = [z2_pal_slots[ci] for ci in z_seats]
        # Stage Close-Up CPU display order is [0, 1, 3, 2, 4]
        st_attr = _stage_attr_bytes([pals[s] for s in (0, 1, 3, 2, 4)])
        ov_attr = _ov_attr_bytes(pals, is_cpu=True)
        rec = st_b + ov_b + fo_b + st_attr + ov_attr + bytes(pals)
        assert len(rec) == 1252
        bank6[zi * 1252 : zi * 1252 + len(rec)] = rec

    # Copy intact blocks 112, 113, 119, 120, 121, 122 (124 B total) into Bank 5 $BF00..$BF7B
    host_buz_blob = bytearray()
    for blk_id in (112, 113, 119, 120, 121, 122):
        w, h, tids, _, _ = feud_art._get_block(prg_buf, blk_id)
        host_buz_blob.extend(_encode_block(w, h, tids))
    assert len(host_buz_blob) == 124
    bank5[0x1F00 : 0x1F00 + 124] = host_buz_blob

    # Fix Overview init ($8049) resetting $05BD=0 without resetting $05BE/$05BF (NMI queue desync)
    assert bytes(prg_buf[0x0049:0x004E]) == bytes((0x8E, 0xBD, 0x05, 0xA0, 0x00))
    prg_buf[0x0049:0x004E] = bytes((0x20, 0xC0, 0x78, 0xEA, 0xEA))

    return {
        'prg_patched': bytes(prg_buf),
        'chr256': bytes(chr256),
        'bank5': bytes(bank5),
        'bank6': bytes(bank6),
        'rt': rt,
        'prg_orig': prg_orig,
    }


def assemble_mmc3_wram_code(wram_syms: dict[str, int]) -> bytes:
    """Assemble standalone MMC3 $7800-$7AFF trampolines (no $5FF0, no Start+Select halt)."""
    from feud_engine import W_CUR_CHR0, W_CUR_CHR1
    from pack_feud import (
        FEUD_BOOT,
        FEUD_MMC1_CHR1,
        FEUD_MMC1_CTRL,
        FEUD_NMI_HOOK,
        FEUD_ORIG_RESET,
        FEUD_WRAM_CODE_BASE,
    )

    w = wram_syms
    a = Asm6502(FEUD_WRAM_CODE_BASE)

    # FEUD_MMC1_CHR0 ($7800): A = logical 4KB CHR bank -> R0/R1 via W_CHR_MAP (preserves X & Y)
    a.emit(0x8D, W_CUR_CHR0 & 0xFF, W_CUR_CHR0 >> 8)
    a.emit(0x8E, 0xFD, 0x7F)              # STX $7FFD
    a.emit(0xC9, 0x10); a.branch(0xB0, 'c0_raw')
    a.emit(0xAA)                          # TAX
    a.emit(0xBD, W_CHR_MAP & 0xFF, W_CHR_MAP >> 8)
    a.label('c0_raw')
    a.emit(0x0A, 0x0A)                    # ASL A; ASL A
    a.abs_ref(0x4C, 'c0_r01')

    # FEUD_MMC1_CHR1 ($7820): A = logical 4KB CHR bank -> R2..R5 via W_CHR_MAP (preserves X & Y)
    while a.base + len(a.buf) < FEUD_MMC1_CHR1:
        a.emit(0xFF)
    assert a.base + len(a.buf) == FEUD_MMC1_CHR1
    a.emit(0x8D, W_CUR_CHR1 & 0xFF, W_CUR_CHR1 >> 8)
    a.emit(0x8E, 0xFD, 0x7F)
    a.emit(0xC9, 0x10); a.branch(0xB0, 'c1_raw')
    a.emit(0xAA)
    a.emit(0xBD, W_CHR_MAP & 0xFF, W_CHR_MAP >> 8)
    a.label('c1_raw')
    a.emit(0x0A, 0x0A, 0xAA)              # ASL A; ASL A; TAX
    for reg in (2, 3, 4, 5):
        a.emit(0xA9, reg, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80)
        if reg < 5:
            a.emit(0xE8)
    a.emit(0xAE, 0xFD, 0x7F, 0xA9, 0x00, 0x60)

    # FEUD_MMC1_CTRL ($7860): A = MMC1 control -> $A000 bit 0 (0=Vertical, 1=Horizontal)
    while a.base + len(a.buf) < FEUD_MMC1_CTRL:
        a.emit(0xFF)
    assert a.base + len(a.buf) == FEUD_MMC1_CTRL
    a.emit(0x29, 0x01, 0x8D, 0x00, 0xA0, 0xA9, 0x00, 0x60)

    # FEUD_NMI_HOOK ($7880): idle animation & ambient roar tick, then normal RTI
    while a.base + len(a.buf) < FEUD_NMI_HOOK:
        a.emit(0xFF)
    assert a.base + len(a.buf) == FEUD_NMI_HOOK
    a.emit(0x20, w['W_NMI_IDLE_TICK'] & 0xFF, w['W_NMI_IDLE_TICK'] >> 8)
    a.emit(0x68, 0xA8, 0x68, 0xAA, 0x68, 0x40)  # PLA; TAY; PLA; TAX; PLA; RTI

    # Slack $7889..$79FF: c0_r01 helper + FEUD_MMC3_CLR_Q ($78C0)
    a.label('c0_r01')
    a.emit(0xA2, 0x00, 0x8E, 0x00, 0x80, 0x8D, 0x01, 0x80)  # R0 = A
    a.emit(0xE8, 0x8E, 0x00, 0x80, 0x09, 0x02, 0x8D, 0x01, 0x80)  # R1 = A | 2
    a.emit(0xAE, 0xFD, 0x7F, 0xA9, 0x00, 0x60)

    while a.base + len(a.buf) < 0x78C0:
        a.emit(0xFF)
    assert a.base + len(a.buf) == 0x78C0
    a.emit(0x8E, 0xBD, 0x05, 0x8E, 0xBE, 0x05, 0x8E, 0xBF, 0x05, 0xA0, 0x00, 0x60)

    # FEUD_BOOT ($7A00): cold init for MMC3 real hardware -> Bank 4 init -> Reset
    while a.base + len(a.buf) < FEUD_BOOT:
        a.emit(0xFF)
    assert a.base + len(a.buf) == FEUD_BOOT
    a.emit(0x78, 0xD8, 0xA2, 0xFF, 0x9A)                    # SEI; CLD; LDX #$FF; TXS
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20)  # PPU off
    a.emit(0x8D, 0x00, 0xE0)                                # disable MMC3 IRQ
    a.emit(0xA9, 0x80, 0x8D, 0x01, 0xA0)                    # enable WRAM
    a.emit(0x2C, 0x02, 0x20)
    a.label('m3_v1'); a.emit(0x2C, 0x02, 0x20); a.branch(0x10, 'm3_v1')
    a.label('m3_v2'); a.emit(0x2C, 0x02, 0x20); a.branch(0x10, 'm3_v2')
    a.emit(0xA9, 0x00)
    a.emit(0x20, w['W_CALL_B4'] & 0xFF, w['W_CALL_B4'] >> 8)  # A=0: B4_BOOT_INIT
    a.emit(0xA9, 0x06, 0x8D, 0x00, 0x80, 0xA9, 0x00, 0x8D, 0x01, 0x80)  # R6=0
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x01, 0x8D, 0x01, 0x80)  # R7=1
    a.emit(0x20, w['W_SYNC_CHR'] & 0xFF, w['W_SYNC_CHR'] >> 8)
    a.emit(0x4C, FEUD_ORIG_RESET & 0xFF, FEUD_ORIG_RESET >> 8)

    while a.base + len(a.buf) < FEUD_WRAM_CODE_BASE + 0x0300:
        a.emit(0xFF)
    out = a.finish()
    assert len(out) == 0x0300, f'MMC3 WRAM code size mismatch: {len(out)}'
    return out


def assemble_mmc3_bank4(cast_assets: dict[str, object]) -> bytes:
    """Assemble PRG Bank 4 ($8900-$9FFF) for MMC3 multi-lineup cast, palettes, names, and lose."""
    from feud_engine import (
        BANK4_CODE_ORG,
        CHR0B_BLUE_MAP,
        FeudAsm,
        LOSE_REASONS,
        W_AMB_TMR_LO,
        W_BLK_A_HI,
        W_BLK_A_LO,
        W_BLK_DYN,
        W_BLK_PTR_HI,
        W_BLK_PTR_LO,
        W_BLK_T_HI,
        W_BLK_T_LO,
        W_COPY_CNT,
        W_CPU_FO_ATTR,
        W_CPU_OV_ATTR,
        W_CPU_PAL_CLR,
        W_CPU_PAL_IDX,
        W_CPU_ST_ATTR,
        W_FO_COLORS,
        W_IDLE_SEAT,
        W_IDLE_TIMER,
        W_LAST_LOSE_IDX,
        W_P1_OV_ATTR,
        W_P1_PAL_CLR,
        W_P1_PAL_IDX,
        W_P1_ST_ATTR,
        W_ROLLED_MAGIC,
        W_SAVE_0E,
        W_SAVE_0F,
        W_SAVE_11,
        W_SAVE_12,
        W_SEAT_IDX,
        W_SIDE_ARG,
        W_TMP0,
        W_TMP1,
        W_TMP3,
        ZELDA_FAMILY_NAMES,
        _encode_chr0b_blue,
        _encode_names_blob,
    )

    rt: dict = cast_assets['rt']  # type: ignore[assignment]
    prg_orig: bytes = cast_assets['prg_orig']  # type: ignore[assignment]
    barba_pal_pairs = rt['barba_pal_pairs']
    z2_pal_pairs = rt['z2_pal_pairs']
    name_offs, name_blob = _encode_names_blob()

    a = FeudAsm(BANK4_CODE_ORG)

    # Dispatch jump table at $8900 (entries 0, 3, 6, 9, 12, 15, 18)
    for tgt in (
        'B4_BOOT_INIT',
        'B4_ROLL_BOTH',
        'B4_ROLL_P1',
        'B4_ROLL_CPU',
        'B4_LOAD_FACEOFF',
        'B4_PICK_Z2_NAME',
        'B4_ZELDA_LOSE',
    ):
        a.emit(0x4C); a.ref16(tgt)

    # ---- Static Tables ----
    a.label('TBL_B_ST_BANK'); a.emit(*B_ST_BANKS)
    a.label('TBL_B_FO_BANK'); a.emit(*B_FO_BANKS)
    a.label('TBL_Z_ST_BANK'); a.emit(*Z_ST_BANKS)
    a.label('TBL_Z_FO_BANK'); a.emit(*Z_FO_BANKS)
    a.label('TBL_OV_BANK')
    for row in OV_BANKS:
        a.emit(*row)

    a.label('TBL_BARBA_C1'); a.emit(*(c1 for c1, _ in barba_pal_pairs))
    a.label('TBL_BARBA_C2'); a.emit(*(c2 for _, c2 in barba_pal_pairs))
    a.label('TBL_Z2_C1');    a.emit(*(c1 for c1, _ in z2_pal_pairs))
    a.label('TBL_Z2_C2');    a.emit(*(c2 for _, c2 in z2_pal_pairs))

    a.label('TBL_NAME_OFF'); a.emit(*name_offs)
    a.label('TBL_NAMES');    a.emit(*name_blob)

    for idx, msg in enumerate(LOSE_REASONS):
        a.label(f'LOSE_STR_{idx}'); a.emit(*_encode_chr0b_blue(msg))
    a.label('TBL_LOSE_LEN'); a.emit(*(len(m) for m in LOSE_REASONS))
    a.label('TBL_LOSE_PAD'); a.emit(*((28 - len(m)) // 2 for m in LOSE_REASONS))
    a.label('TBL_LOSE_LO')
    for idx in range(len(LOSE_REASONS)): a.ref_lo(f'LOSE_STR_{idx}')
    a.label('TBL_LOSE_HI')
    for idx in range(len(LOSE_REASONS)): a.ref_hi(f'LOSE_STR_{idx}')
    a.label('TBL_BLUE_THE');    a.emit(*_encode_chr0b_blue('the '))
    a.label('TBL_BLUE_FAMILY'); a.emit(*_encode_chr0b_blue(' family'))

    a.label('TBL_ST_POSE_MAP'); a.emit(0, 1, 0, 0, 2)
    a.label('TBL_CPU_LR_SEAT'); a.emit(0, 1, 3, 2, 4)
    a.label('TBL_B_LINEUP_LO'); a.emit(*((0xA000 + bi * 1372) & 0xFF for bi in range(3)))
    a.label('TBL_B_LINEUP_HI'); a.emit(*((0xA000 + bi * 1372) >> 8 for bi in range(3)))
    a.label('TBL_Z_LINEUP_LO'); a.emit(*((0xA000 + zi * 1252) & 0xFF for zi in range(6)))
    a.label('TBL_Z_LINEUP_HI'); a.emit(*((0xA000 + zi * 1252) >> 8 for zi in range(6)))
    a.label('TBL_ST_ATTR_TPLS')
    for pal in (1, 2, 3):
        a.emit(4, 6, *([pal] * 24))
    a.label('TBL_FO_OAM_TPL')
    a.emit(7, 12, *([1] * 84))
    a.label('TBL_HOST_BUZ_IDS')
    a.emit(112, 113, 119, 120, 121, 122)
    a.label('TBL_HOST_BUZ_OFFS')
    a.emit(0, 26, 52, 78, 104, 114)  # byte offsets inside $6A00

    # ---- Helpers ----
    a.label('B4_SAVE_ZP')
    a.emit(0xA5, 0x0E); a.op16(0x8D, W_SAVE_0E)
    a.emit(0xA5, 0x0F); a.op16(0x8D, W_SAVE_0F)
    a.emit(0xA5, 0x11); a.op16(0x8D, W_SAVE_11)
    a.emit(0xA5, 0x12); a.op16(0x8D, W_SAVE_12)
    a.emit(0x60)

    a.label('B4_RESTORE_ZP')
    a.op16(0xAD, W_SAVE_0E); a.emit(0x85, 0x0E)
    a.op16(0xAD, W_SAVE_0F); a.emit(0x85, 0x0F)
    a.op16(0xAD, W_SAVE_11); a.emit(0x85, 0x11)
    a.op16(0xAD, W_SAVE_12); a.emit(0x85, 0x12)
    a.emit(0x60)

    a.label('B4_RNG')
    a.emit(0xAD, 0xFC, 0x01, 0x29, 0x80, 0x4A, 0x4D, 0xFC, 0x01)
    a.emit(0x2A, 0x2A, 0x2E, 0xFA, 0x01, 0x2E, 0xFB, 0x01, 0x2E, 0xFC, 0x01, 0x60)

    a.label('B4_RAND_MOD')
    a.emit(0x85, 0x11)
    a.label('rmod_retry')
    a.abs_ref(0x20, 'B4_RNG')
    a.emit(0xAD, 0xFA, 0x01, 0x45, 0x1F, 0x29, 0x1F, 0xC5, 0x11)
    a.branch(0xB0, 'rmod_retry')
    a.emit(0x60)

    # Copy A bytes (0 = 256) from ($0E) to ($11) and advance both pointers by A
    a.label('B4_COPY_N')
    a.emit(0x85, 0x10, 0xA0, 0x00)
    a.label('bcn_lp')
    a.emit(0xB1, 0x0E, 0x91, 0x11, 0xC8, 0xC4, 0x10)
    a.branch(0xD0, 'bcn_lp')
    a.emit(0xA5, 0x10); a.branch(0xD0, 'bcn_adv')
    a.emit(0xE6, 0x0F, 0xE6, 0x12, 0x60)
    a.label('bcn_adv')
    a.emit(0x18, 0x65, 0x0E, 0x85, 0x0E); a.branch(0x90, 'bcn_nc1'); a.emit(0xE6, 0x0F)
    a.label('bcn_nc1')
    a.emit(0xA5, 0x10, 0x18, 0x65, 0x11, 0x85, 0x11); a.branch(0x90, 'bcn_nc2'); a.emit(0xE6, 0x12)
    a.label('bcn_nc2')
    a.emit(0x60)

    # ---- B4_BOOT_INIT ----
    a.label('B4_BOOT_INIT')
    a.abs_ref(0x20, 'B4_SAVE_ZP')
    a.emit(0xA9, 0x00, 0xAA)
    a.label('bi_clr')
    for pg in range(0x60, 0x6D):
        a.emit(0x9D, 0x00, pg)
    a.emit(0xE8); a.branch(0xD0, 'bi_clr')
    a.emit(0xA9, 0xFF); a.op16(0x8D, W_IDLE_SEAT)
    a.emit(0xA9, 0x48); a.op16(0x8D, W_IDLE_TIMER)
    a.emit(0xA9, 120);  a.op16(0x8D, W_AMB_TMR_LO)
    a.emit(0xA9, 0x40, 0x8D, 0x11, 0x40)

    # Copy TBL_FAST_PAL -> $6F00 (256 B)
    a.emit(0xA2, 0x00)
    a.label('bi_fp')
    a.abs_ref(0xBD, 'TBL_FAST_PAL'); a.emit(0x9D, 0x00, 0x6F, 0xE8); a.branch(0xD0, 'bi_fp')

    # Copy Stage attr templates (78 B) + FO OAM attr template (86 B) -> $6A80..$6B23
    a.emit(0xA2, 163)
    a.label('bi_tpl')
    a.abs_ref(0xBD, 'TBL_ST_ATTR_TPLS'); a.op16(0x9D, MMC3_ST_ATTR_TPLS)
    a.emit(0xCA); a.branch(0x10, 'bi_tpl')

    # Copy intact Host/Buzzer blocks 112,113,119..122 (124 B) from Bank 5 $BF00 -> $6A00
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x05, 0x8D, 0x01, 0x80)
    a.emit(0xA2, 123)
    a.label('bi_hb')
    a.emit(0xBD, 0x00, 0xBF); a.op16(0x9D, MMC3_HOST_BUZ_BASE)
    a.emit(0xCA); a.branch(0x10, 'bi_hb')
    a.emit(0xA2, 0x05)
    a.label('bi_hb_reg')
    a.abs_ref(0xBC, 'TBL_HOST_BUZ_IDS')
    a.abs_ref(0xBD, 'TBL_HOST_BUZ_OFFS')
    a.emit(0x8A, 0x99, W_BLK_T_LO & 0xFF, W_BLK_T_LO >> 8)
    a.emit(0xA9, MMC3_HOST_BUZ_BASE >> 8, 0x99, W_BLK_T_HI & 0xFF, W_BLK_T_HI >> 8)
    a.emit(0xB9, 0x18, 0xF2, 0x99, W_BLK_A_LO & 0xFF, W_BLK_A_LO >> 8)
    a.emit(0xB9, 0xE5, 0xF2, 0x99, W_BLK_A_HI & 0xFF, W_BLK_A_HI >> 8)
    a.emit(0xA9, 0x01, 0x99, W_BLK_DYN & 0xFF, W_BLK_DYN >> 8)
    a.emit(0xCA); a.branch(0x10, 'bi_hb_reg')

    # Init W_CHR_MAP[0..15] = 0..15
    a.emit(0xA2, 0x0F)
    a.label('bi_cm')
    a.emit(0x8A); a.op16(0x9D, W_CHR_MAP); a.emit(0xCA); a.branch(0x10, 'bi_cm')
    a.abs_ref(0x4C, 'B4_RESTORE_ZP')

    # ---- B4_ROLL_BOTH / B4_ROLL_P1 / B4_ROLL_CPU ----
    a.label('B4_ROLL_BOTH')
    a.emit(0xA9, 0x00, 0x8D, 0x15, 0x03, 0xA9, 0x01, 0x8D, 0x16, 0x03)
    a.emit(0xA9, 0xA0, 0x8D, 0x00, 0x03, 0x8D, 0x08, 0x03)
    a.abs_ref(0x20, 'B4_SAVE_ZP')
    a.emit(0xA9, 0x00); a.abs_ref(0x20, 'B4_ROLL_SIDE')
    a.emit(0xA9, 0x01); a.abs_ref(0x20, 'B4_ROLL_SIDE')
    a.emit(0xA9, 0x5A); a.op16(0x8D, W_ROLLED_MAGIC)
    a.abs_ref(0x4C, 'B4_RESTORE_ZP')

    a.label('B4_ROLL_P1')
    a.emit(0xA9, 0x00, 0x8D, 0x15, 0x03)
    a.abs_ref(0x20, 'B4_SAVE_ZP')
    a.emit(0xA9, 0x00); a.abs_ref(0x20, 'B4_ROLL_SIDE')
    a.abs_ref(0x4C, 'B4_RESTORE_ZP')

    a.label('B4_ROLL_CPU')
    a.emit(0xA9, 0x01, 0x8D, 0x16, 0x03)
    a.abs_ref(0x20, 'B4_SAVE_ZP')
    a.emit(0xA9, 0x01); a.abs_ref(0x20, 'B4_ROLL_SIDE')
    a.abs_ref(0x4C, 'B4_RESTORE_ZP')

    # ---- B4_ROLL_SIDE (A = 0 P1 / 1 CPU) ----
    a.label('B4_ROLL_SIDE')
    a.op16(0x8D, W_SIDE_ARG)
    a.branch(0xD0, 'rs_pick_cpu')
    a.emit(0xA9, 0x03); a.abs_ref(0x20, 'B4_RAND_MOD')
    a.op16(0x8D, W_MMC3_P1_L); a.emit(0xAA)
    a.abs_ref(0xBD, 'TBL_B_LINEUP_LO'); a.emit(0x85, 0x0E)
    a.abs_ref(0xBD, 'TBL_B_LINEUP_HI'); a.emit(0x85, 0x0F)
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x05, 0x8D, 0x01, 0x80)  # R7 = 5
    a.emit(0xA9, MMC3_P1_ST_BASE & 0xFF, 0x85, 0x11, 0xA9, MMC3_P1_ST_BASE >> 8, 0x85, 0x12)
    a.abs_ref(0x4C, 'rs_copy_payload')

    a.label('rs_pick_cpu')
    a.emit(0xA9, 0x06); a.abs_ref(0x20, 'B4_RAND_MOD')
    a.op16(0x8D, W_MMC3_CPU_L); a.emit(0xAA)
    a.abs_ref(0xBD, 'TBL_Z_LINEUP_LO'); a.emit(0x85, 0x0E)
    a.abs_ref(0xBD, 'TBL_Z_LINEUP_HI'); a.emit(0x85, 0x0F)
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x06, 0x8D, 0x01, 0x80)  # R7 = 6
    a.emit(0xA9, MMC3_CPU_ST_BASE & 0xFF, 0x85, 0x11, 0xA9, MMC3_CPU_ST_BASE >> 8, 0x85, 0x12)

    a.label('rs_copy_payload')
    # Copy 390 B Stage (256 + 134)
    a.emit(0xA9, 0x00); a.abs_ref(0x20, 'B4_COPY_N')
    a.emit(0xA9, 134);  a.abs_ref(0x20, 'B4_COPY_N')
    # Copy 100 B Overview -> P1/CPU OV base
    a.op16(0xAD, W_SIDE_ARG); a.branch(0xD0, 'rcp_ov_cpu')
    a.emit(0xA9, MMC3_P1_OV_BASE & 0xFF, 0x85, 0x11, 0xA9, MMC3_P1_OV_BASE >> 8, 0x85, 0x12)
    a.abs_ref(0x4C, 'rcp_ov_go')
    a.label('rcp_ov_cpu')
    a.emit(0xA9, MMC3_CPU_OV_BASE & 0xFF, 0x85, 0x11, 0xA9, MMC3_CPU_OV_BASE >> 8, 0x85, 0x12)
    a.label('rcp_ov_go')
    a.emit(0xA9, 100); a.abs_ref(0x20, 'B4_COPY_N')
    # Skip Face-Off section in ROM (860 B = $035C for P1, 740 B = $02E4 for CPU)
    a.op16(0xAD, W_SIDE_ARG); a.branch(0xD0, 'rcp_skip_cpu')
    a.emit(0x18, 0xA5, 0x0E, 0x69, 0x5C, 0x85, 0x0E, 0xA5, 0x0F, 0x69, 0x03, 0x85, 0x0F)
    a.abs_ref(0x4C, 'rcp_meta')
    a.label('rcp_skip_cpu')
    a.emit(0x18, 0xA5, 0x0E, 0x69, 0xE4, 0x85, 0x0E, 0xA5, 0x0F, 0x69, 0x02, 0x85, 0x0F)
    a.label('rcp_meta')
    # Copy 14B st_attr, 3B ov_attr, 5B pal_idx
    a.op16(0xAD, W_SIDE_ARG); a.branch(0xD0, 'rcp_m_cpu')
    a.emit(0xA9, W_P1_ST_ATTR & 0xFF, 0x85, 0x11, 0xA9, W_P1_ST_ATTR >> 8, 0x85, 0x12)
    a.emit(0xA9, 14); a.abs_ref(0x20, 'B4_COPY_N')
    a.emit(0xA9, W_P1_OV_ATTR & 0xFF, 0x85, 0x11, 0xA9, W_P1_OV_ATTR >> 8, 0x85, 0x12)
    a.emit(0xA9, 3);  a.abs_ref(0x20, 'B4_COPY_N')
    a.emit(0xA9, W_P1_PAL_IDX & 0xFF, 0x85, 0x11, 0xA9, W_P1_PAL_IDX >> 8, 0x85, 0x12)
    a.emit(0xA9, 5);  a.abs_ref(0x20, 'B4_COPY_N')
    a.abs_ref(0x4C, 'rs_roll_colors')
    a.label('rcp_m_cpu')
    a.emit(0xA9, W_CPU_ST_ATTR & 0xFF, 0x85, 0x11, 0xA9, W_CPU_ST_ATTR >> 8, 0x85, 0x12)
    a.emit(0xA9, 14); a.abs_ref(0x20, 'B4_COPY_N')
    a.emit(0xA9, W_CPU_OV_ATTR & 0xFF, 0x85, 0x11, 0xA9, W_CPU_OV_ATTR >> 8, 0x85, 0x12)
    a.emit(0xA9, 3);  a.abs_ref(0x20, 'B4_COPY_N')
    a.emit(0xA9, W_CPU_PAL_IDX & 0xFF, 0x85, 0x11, 0xA9, W_CPU_PAL_IDX >> 8, 0x85, 0x12)
    a.emit(0xA9, 5);  a.abs_ref(0x20, 'B4_COPY_N')

    # Roll 3 palette slot color variations
    a.label('rs_roll_colors')
    a.emit(0xA9, 0x00); a.op16(0x8D, W_TMP3)
    a.label('rrc_lp')
    a.emit(0xA9, 0x04); a.abs_ref(0x20, 'B4_RAND_MOD')
    a.op16(0x8D, W_TMP0)
    a.op16(0xAD, W_TMP3); a.emit(0x0A, 0x0A, 0x18); a.op16(0x6D, W_TMP0); a.emit(0xA8)
    a.op16(0xAD, W_TMP3); a.emit(0x0A, 0xAA)
    a.op16(0xAD, W_SIDE_ARG); a.branch(0xD0, 'rrc_z2')
    a.abs_ref(0xB9, 'TBL_BARBA_C1'); a.op16(0x9D, W_P1_PAL_CLR)
    a.abs_ref(0xB9, 'TBL_BARBA_C2'); a.op16(0x9D, W_P1_PAL_CLR + 1)
    a.abs_ref(0x4C, 'rrc_nx')
    a.label('rrc_z2')
    a.abs_ref(0xB9, 'TBL_Z2_C1'); a.op16(0x9D, W_CPU_PAL_CLR)
    a.abs_ref(0xB9, 'TBL_Z2_C2'); a.op16(0x9D, W_CPU_PAL_CLR + 1)
    a.label('rrc_nx')
    a.op16(0xEE, W_TMP3); a.op16(0xAD, W_TMP3); a.emit(0xC9, 0x03)
    a.branch(0xD0, 'rrc_lp')

    # Register W_BLK_DYN / pointers for Stage, Overview, and Face-Off (seats 0..4)
    a.emit(0xA9, 0x00); a.op16(0x8D, W_SEAT_IDX)
    a.op16(0xAD, W_SIDE_ARG); a.branch(0xD0, 'reg_cpu_init')
    a.emit(0xA9, MMC3_P1_ST_BASE & 0xFF); a.op16(0x8D, W_BLK_PTR_LO)
    a.emit(0xA9, MMC3_P1_ST_BASE >> 8);   a.op16(0x8D, W_BLK_PTR_HI)
    a.abs_ref(0x4C, 'reg_seat_lp')
    a.label('reg_cpu_init')
    a.emit(0xA9, MMC3_CPU_ST_BASE & 0xFF); a.op16(0x8D, W_BLK_PTR_LO)
    a.emit(0xA9, MMC3_CPU_ST_BASE >> 8);   a.op16(0x8D, W_BLK_PTR_HI)

    a.label('reg_seat_lp')
    # Stage: Compute attr block ptr ($6E80 + (pal-1)*26) in $0E/$0F
    a.op16(0xAE, W_SEAT_IDX)
    a.op16(0xAD, W_SIDE_ARG); a.branch(0xD0, 'rs_attr_cpu')
    a.op16(0xBD, W_P1_PAL_IDX); a.abs_ref(0x4C, 'rs_attr_go')
    a.label('rs_attr_cpu')
    a.op16(0xBD, W_CPU_PAL_IDX)
    a.label('rs_attr_go')
    a.emit(0x38, 0xE9, 0x01, 0xAA, 0xA9, MMC3_ST_ATTR_TPLS & 0xFF, 0x85, 0x0E)
    a.emit(0xA9, MMC3_ST_ATTR_TPLS >> 8, 0x85, 0x0F)
    a.label('rs_attr_mul')
    a.emit(0xE0, 0x00); a.branch(0xF0, 'rs_attr_ok')
    a.emit(0x18, 0xA5, 0x0E, 0x69, 26, 0x85, 0x0E); a.branch(0x90, 'rs_am_nc'); a.emit(0xE6, 0x0F)
    a.label('rs_am_nc')
    a.emit(0xCA); a.abs_ref(0x4C, 'rs_attr_mul')
    a.label('rs_attr_ok')

    # Stage blk base = seat*5 + (0 if P1 else 25)
    a.op16(0xAD, W_SEAT_IDX); a.emit(0x0A, 0x0A, 0x18); a.op16(0x6D, W_SEAT_IDX)
    a.op16(0xAC, W_SIDE_ARG); a.branch(0xF0, 'rs_st_reg_init')
    a.emit(0x18, 0x69, 25)
    a.label('rs_st_reg_init')
    a.emit(0xAA, 0xA0, 0x00)
    a.label('rs_st_reg_lp')
    a.abs_ref(0xB9, 'TBL_ST_POSE_MAP'); a.emit(0x48)
    a.op16(0xAD, W_BLK_PTR_LO); a.op16(0x9D, W_BLK_T_LO)
    a.op16(0xAD, W_BLK_PTR_HI); a.op16(0x9D, W_BLK_T_HI)
    a.emit(0x68); a.branch(0xF0, 'rs_st_ptr_ok')
    a.label('rs_st_a26')
    a.emit(0x48, 0x18); a.op16(0xBD, W_BLK_T_LO); a.emit(0x69, 26); a.op16(0x9D, W_BLK_T_LO)
    a.branch(0x90, 'rs_st_nc'); a.op16(0xFE, W_BLK_T_HI)
    a.label('rs_st_nc')
    a.emit(0x68, 0x38, 0xE9, 0x01); a.branch(0xD0, 'rs_st_a26')
    a.label('rs_st_ptr_ok')
    a.emit(0xA5, 0x0E); a.op16(0x9D, W_BLK_A_LO)
    a.emit(0xA5, 0x0F); a.op16(0x9D, W_BLK_A_HI)
    a.emit(0xA9, 0x01); a.op16(0x9D, W_BLK_DYN)
    # Mirror CPU seat to blocks 50..74 as well when side==1
    a.op16(0xAD, W_SIDE_ARG); a.branch(0xF0, 'rs_st_nx')
    a.op16(0xBD, W_BLK_T_LO); a.op16(0x9D, W_BLK_T_LO + 25)
    a.op16(0xBD, W_BLK_T_HI); a.op16(0x9D, W_BLK_T_HI + 25)
    a.emit(0xA5, 0x0E); a.op16(0x9D, W_BLK_A_LO + 25)
    a.emit(0xA5, 0x0F); a.op16(0x9D, W_BLK_A_HI + 25)
    a.emit(0xA9, 0x01); a.op16(0x9D, W_BLK_DYN + 25)
    a.label('rs_st_nx')
    a.emit(0xE8, 0xC8, 0xC0, 0x05); a.branch(0xD0, 'rs_st_reg_lp')
    # Advance W_BLK_PTR by 78 for next seat
    a.emit(0x18); a.op16(0xAD, W_BLK_PTR_LO); a.emit(0x69, 78); a.op16(0x8D, W_BLK_PTR_LO)
    a.branch(0x90, 'rs_st_ptr_adv_ok'); a.op16(0xEE, W_BLK_PTR_HI)
    a.label('rs_st_ptr_adv_ok')

    # Overview pointers for this seat
    # ptr = OV_BASE + seat * 20
    a.op16(0xAD, W_SEAT_IDX); a.emit(0x0A, 0x0A, 0x85, 0x10)  # seat*4
    a.emit(0x0A, 0x0A, 0x18, 0x65, 0x10, 0x85, 0x10)           # seat*20 (< 100)
    a.op16(0xAD, W_SIDE_ARG); a.branch(0xD0, 'reg_ov_cpu')
    a.emit(0xA5, 0x10, 0x18, 0x69, MMC3_P1_OV_BASE & 0xFF, 0x85, 0x0E)
    a.emit(0xA9, MMC3_P1_OV_BASE >> 8, 0x69, 0x00, 0x85, 0x0F)
    a.emit(0x18); a.op16(0xAD, W_SEAT_IDX); a.emit(0x69, 143, 0xAA); a.abs_ref(0x20, 'B4_REG_OV_IDLE')
    a.emit(0x18); a.op16(0xAD, W_SEAT_IDX); a.emit(0x69, 123, 0xAA); a.abs_ref(0x20, 'B4_REG_OV_IDLE')
    a.emit(0x18); a.op16(0xAD, W_SEAT_IDX); a.emit(0x69, 128, 0xAA); a.abs_ref(0x20, 'B4_REG_OV_ROAR')
    a.abs_ref(0x4C, 'reg_next_seat')
    a.label('reg_ov_cpu')
    a.emit(0xA5, 0x10, 0x18, 0x69, MMC3_CPU_OV_BASE & 0xFF, 0x85, 0x0E)
    a.emit(0xA9, MMC3_CPU_OV_BASE >> 8, 0x69, 0x00, 0x85, 0x0F)
    a.emit(0xA9, 152, 0x38); a.op16(0xED, W_SEAT_IDX); a.emit(0xAA); a.abs_ref(0x20, 'B4_REG_OV_IDLE')
    a.emit(0x18); a.op16(0xAD, W_SEAT_IDX); a.emit(0x69, 133, 0xAA); a.abs_ref(0x20, 'B4_REG_OV_IDLE')
    a.emit(0x18); a.op16(0xAD, W_SEAT_IDX); a.emit(0x69, 138, 0xAA); a.abs_ref(0x20, 'B4_REG_OV_ROAR')

    a.label('reg_next_seat')
    a.op16(0xEE, W_SEAT_IDX); a.op16(0xAD, W_SEAT_IDX); a.emit(0xC9, 0x05)
    a.branch(0xF0, 'reg_all_done')
    a.abs_ref(0x4C, 'reg_seat_lp')

    a.label('reg_all_done')
    # Update W_CHR_MAP[0, 2, 3, 4, 5, 6, 7]
    a.op16(0xAE, W_MMC3_P1_L)
    a.abs_ref(0xBD, 'TBL_B_FO_BANK'); a.op16(0x8D, W_CHR_MAP + 2)
    a.abs_ref(0xBD, 'TBL_B_ST_BANK'); a.op16(0x8D, W_CHR_MAP + 5)
    a.op16(0xAE, W_MMC3_CPU_L)
    a.abs_ref(0xBD, 'TBL_Z_FO_BANK'); a.op16(0x8D, W_CHR_MAP + 3); a.op16(0x8D, W_CHR_MAP + 4)
    a.abs_ref(0xBD, 'TBL_Z_ST_BANK'); a.op16(0x8D, W_CHR_MAP + 6); a.op16(0x8D, W_CHR_MAP + 7)
    a.op16(0xAD, W_MMC3_P1_L); a.emit(0x0A, 0x85, 0x10, 0x0A, 0x18, 0x65, 0x10)  # p1_l * 6
    a.emit(0x18); a.op16(0x6D, W_MMC3_CPU_L); a.emit(0xAA)
    a.abs_ref(0xBD, 'TBL_OV_BANK'); a.op16(0x8D, W_CHR_MAP + 0)
    a.emit(0x60)

    a.label('B4_REG_OV_IDLE')
    a.emit(0xA5, 0x0E);         a.op16(0x9D, W_BLK_T_LO)
    a.emit(0xA5, 0x0F);         a.op16(0x9D, W_BLK_T_HI)
    a.emit(0xBD, 0x18, 0xF2);   a.op16(0x9D, W_BLK_A_LO)
    a.emit(0xBD, 0xE5, 0xF2);   a.op16(0x9D, W_BLK_A_HI)
    a.emit(0xA9, 0x01);         a.op16(0x9D, W_BLK_DYN)
    a.emit(0x60)

    a.label('B4_REG_OV_ROAR')
    a.emit(0x18, 0xA5, 0x0E, 0x69, 10); a.op16(0x9D, W_BLK_T_LO)
    a.emit(0xA5, 0x0F, 0x69, 0x00);     a.op16(0x9D, W_BLK_T_HI)
    a.emit(0xBD, 0x18, 0xF2);           a.op16(0x9D, W_BLK_A_LO)
    a.emit(0xBD, 0xE5, 0xF2);           a.op16(0x9D, W_BLK_A_HI)
    a.emit(0xA9, 0x01);                 a.op16(0x9D, W_BLK_DYN)
    a.emit(0x60)

    a.label('B4_REG_FO_CPU_PAIR')
    # Registers block X (in 91..102) and X+16 (in 107..118) to ($0E/$0F)
    a.emit(0xA5, 0x0E);       a.op16(0x9D, W_BLK_T_LO); a.op16(0x9D, W_BLK_T_LO + 16)
    a.emit(0xA5, 0x0F);       a.op16(0x9D, W_BLK_T_HI); a.op16(0x9D, W_BLK_T_HI + 16)
    a.emit(0xBD, 0x18, 0xF2); a.op16(0x9D, W_BLK_A_LO); a.op16(0x9D, W_BLK_A_LO + 16)
    a.emit(0xBD, 0xE5, 0xF2); a.op16(0x9D, W_BLK_A_HI); a.op16(0x9D, W_BLK_A_HI + 16)
    a.emit(0xA9, 0x01);       a.op16(0x9D, W_BLK_DYN);  a.op16(0x9D, W_BLK_DYN + 16)
    a.emit(0x60)

    # ---- B4_LOAD_FACEOFF ----
    a.label('B4_LOAD_FACEOFF')
    a.abs_ref(0x20, 'B4_SAVE_ZP')
    a.emit(0xAE, 0xDC, 0x04)  # active seat 0..4
    a.abs_ref(0xBD, 'TBL_CPU_LR_SEAT'); a.op16(0x8D, W_TMP0)

    # Clear old DYN for 75..79, 82..86, 91..95, 98..102, 107..111, 114..118
    a.emit(0xA2, 0x04, 0xA9, 0x00)
    a.label('lfo_clr_dyn')
    for base in (75, 82, 91, 98, 107, 114):
        a.op16(0x9D, W_BLK_DYN + base)
    a.emit(0xCA); a.branch(0x10, 'lfo_clr_dyn')

    # Copy active seat P1 7x12 (172 B) from Bank 5 -> MMC3_P1_FO_BASE
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x05, 0x8D, 0x01, 0x80)
    a.op16(0xAE, W_MMC3_P1_L)
    a.abs_ref(0xBD, 'TBL_B_LINEUP_LO'); a.emit(0x18, 0x69, 0xEA, 0x85, 0x0E)
    a.abs_ref(0xBD, 'TBL_B_LINEUP_HI'); a.emit(0x69, 0x01, 0x85, 0x0F)
    a.emit(0xAE, 0xDC, 0x04)
    a.label('lfo_p1_mul')
    a.branch(0xF0, 'lfo_p1_cp')
    a.emit(0x18, 0xA5, 0x0E, 0x69, 172, 0x85, 0x0E); a.branch(0x90, 'lfo_p1_nc'); a.emit(0xE6, 0x0F)
    a.label('lfo_p1_nc')
    a.emit(0xCA); a.abs_ref(0x4C, 'lfo_p1_mul')
    a.label('lfo_p1_cp')
    a.emit(0xA9, MMC3_P1_FO_BASE & 0xFF, 0x85, 0x11, 0xA9, MMC3_P1_FO_BASE >> 8, 0x85, 0x12)
    a.emit(0xA9, 172); a.abs_ref(0x20, 'B4_COPY_N')

    # Copy active seat CPU 6x12 (148 B) from Bank 6 -> MMC3_CPU_FO_BASE
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80, 0xA9, 0x06, 0x8D, 0x01, 0x80)
    a.op16(0xAE, W_MMC3_CPU_L)
    a.abs_ref(0xBD, 'TBL_Z_LINEUP_LO'); a.emit(0x18, 0x69, 0xEA, 0x85, 0x0E)
    a.abs_ref(0xBD, 'TBL_Z_LINEUP_HI'); a.emit(0x69, 0x01, 0x85, 0x0F)
    a.emit(0xAE, 0xDC, 0x04)
    a.label('lfo_cpu_mul')
    a.branch(0xF0, 'lfo_cpu_cp')
    a.emit(0x18, 0xA5, 0x0E, 0x69, 148, 0x85, 0x0E); a.branch(0x90, 'lfo_cpu_nc'); a.emit(0xE6, 0x0F)
    a.label('lfo_cpu_nc')
    a.emit(0xCA); a.abs_ref(0x4C, 'lfo_cpu_mul')
    a.label('lfo_cpu_cp')
    a.emit(0xA9, MMC3_CPU_FO_BASE & 0xFF, 0x85, 0x11, 0xA9, MMC3_CPU_FO_BASE >> 8, 0x85, 0x12)
    a.emit(0xA9, 148); a.abs_ref(0x20, 'B4_COPY_N')

    # Register P1 blocks 75+lr_seat & 82+lr_seat
    a.emit(0xA9, 75, 0x18); a.op16(0x6D, W_TMP0); a.emit(0xAA)
    a.emit(0xA9, MMC3_P1_FO_BASE & 0xFF); a.op16(0x9D, W_BLK_T_LO)
    a.emit(0xA9, MMC3_P1_FO_BASE >> 8);   a.op16(0x9D, W_BLK_T_HI)
    a.emit(0xA9, MMC3_FO_OAM_ATTR & 0xFF); a.op16(0x9D, W_BLK_A_LO)
    a.emit(0xA9, MMC3_FO_OAM_ATTR >> 8);   a.op16(0x9D, W_BLK_A_HI)
    a.emit(0xA9, 0x01);                    a.op16(0x9D, W_BLK_DYN)
    a.emit(0xA9, 82, 0x18); a.op16(0x6D, W_TMP0); a.emit(0xAA)
    a.emit(0xA9, (MMC3_P1_FO_BASE + 86) & 0xFF); a.op16(0x9D, W_BLK_T_LO)
    a.emit(0xA9, (MMC3_P1_FO_BASE + 86) >> 8);   a.op16(0x9D, W_BLK_T_HI)
    a.emit(0xA9, MMC3_FO_OAM_ATTR & 0xFF); a.op16(0x9D, W_BLK_A_LO)
    a.emit(0xA9, MMC3_FO_OAM_ATTR >> 8);   a.op16(0x9D, W_BLK_A_HI)
    a.emit(0xA9, 0x01);                    a.op16(0x9D, W_BLK_DYN)

    # Register CPU blocks 91+lr_seat, 107+lr_seat, 98+lr_seat, 114+lr_seat
    a.emit(0xA9, MMC3_CPU_FO_BASE & 0xFF, 0x85, 0x0E, 0xA9, MMC3_CPU_FO_BASE >> 8, 0x85, 0x0F)
    a.emit(0xA9, 91, 0x18); a.op16(0x6D, W_TMP0); a.emit(0xAA); a.abs_ref(0x20, 'B4_REG_FO_CPU_PAIR')
    a.emit(0xA9, (MMC3_CPU_FO_BASE + 74) & 0xFF, 0x85, 0x0E, 0xA9, (MMC3_CPU_FO_BASE + 74) >> 8, 0x85, 0x0F)
    a.emit(0xA9, 98, 0x18); a.op16(0x6D, W_TMP0); a.emit(0xAA); a.abs_ref(0x20, 'B4_REG_FO_CPU_PAIR')

    # Colors & 9-byte W_CPU_FO_ATTR ($23DC..$23DE, $23E4..$23E6, $23EC..$23EE; CPU at col 21..26)
    a.emit(0xAE, 0xDC, 0x04)
    a.op16(0xBD, W_P1_PAL_IDX); a.emit(0x38, 0xE9, 0x01, 0x0A, 0xA8)
    a.op16(0xB9, W_P1_PAL_CLR);     a.op16(0x8D, W_FO_COLORS)
    a.op16(0xB9, W_P1_PAL_CLR + 1); a.op16(0x8D, W_FO_COLORS + 1)
    a.op16(0xBD, W_CPU_PAL_IDX); a.op16(0x8D, W_TMP0)
    a.emit(0x38, 0xE9, 0x01, 0x0A, 0xA8)
    a.op16(0xB9, W_CPU_PAL_CLR);     a.op16(0x8D, W_FO_COLORS + 2)
    a.op16(0xB9, W_CPU_PAL_CLR + 1); a.op16(0x8D, W_FO_COLORS + 3)

    a.emit(0xA9, 0x10); a.op16(0x8D, W_CPU_FO_ATTR + 0)
    a.emit(0xA9, 0x11); a.op16(0x8D, W_CPU_FO_ATTR + 3)
    a.emit(0xA9, 0x00); a.op16(0x8D, W_CPU_FO_ATTR + 6)
    a.op16(0xAD, W_TMP0); a.emit(0x0A, 0x0A, 0x85, 0x10)                # p << 2
    a.emit(0x0A, 0x0A, 0x85, 0x11)                                      # p << 4
    a.emit(0x0A, 0x0A, 0x05, 0x11)                                      # (p<<4)|(p<<6)
    a.op16(0x8D, W_CPU_FO_ATTR + 1); a.op16(0x8D, W_CPU_FO_ATTR + 2)
    a.op16(0xAD, W_TMP0); a.emit(0x0A, 0x0A, 0x18); a.op16(0x6D, W_TMP0)  # p * 5
    a.op16(0x8D, W_CPU_FO_ATTR + 7); a.op16(0x8D, W_CPU_FO_ATTR + 8)
    a.emit(0x0A, 0x0A, 0x0A, 0x0A, 0x18); a.op16(0x6D, W_CPU_FO_ATTR + 7) # p * 0x55
    a.op16(0x8D, W_CPU_FO_ATTR + 4); a.op16(0x8D, W_CPU_FO_ATTR + 5)
    a.abs_ref(0x4C, 'B4_RESTORE_ZP')

    # ---- B4_PICK_Z2_NAME ----
    a.label('B4_PICK_Z2_NAME')
    a.label('pzn_rng')
    a.abs_ref(0x20, 'B4_RNG')
    a.emit(0xAD, 0xFA, 0x01, 0x45, 0x1F, 0x29, 0x1F, 0xC9, len(ZELDA_FAMILY_NAMES))
    a.branch(0xB0, 'pzn_rng')
    a.emit(0xAA)
    a.abs_ref(0xBC, 'TBL_NAME_OFF')
    a.emit(0xA2, 0x00)
    a.label('pzn_cp')
    a.abs_ref(0xB9, 'TBL_NAMES')
    a.emit(0x9D, 0x08, 0x03)
    a.branch(0x30, 'pzn_done')
    a.emit(0xE8, 0xC8); a.abs_ref(0x4C, 'pzn_cp')
    a.label('pzn_done')
    a.emit(0x60)

    # ---- B4_ZELDA_LOSE ----
    a.label('B4_ZELDA_LOSE')
    a.abs_ref(0x20, 'B4_SAVE_ZP')
    a.label('zl_rng')
    a.abs_ref(0x20, 'B4_RNG')
    a.emit(0xAD, 0xFA, 0x01, 0x45, 0x1F, 0x29, 0x07, 0xC9, 0x07)
    a.branch(0xB0, 'zl_rng')
    a.op16(0x8D, W_LAST_LOSE_IDX)
    a.emit(0x48)
    a.emit(0xA9, 0x21, 0x8D, 0x06, 0x20, 0xA9, 0x02, 0x8D, 0x06, 0x20)
    a.emit(0xA9, 0x00, 0xA2, 28)
    a.label('zl_clr8'); a.emit(0x8D, 0x07, 0x20, 0xCA); a.branch(0xD0, 'zl_clr8')
    a.emit(0xA9, 0x21, 0x8D, 0x06, 0x20, 0xA9, 0x82, 0x8D, 0x06, 0x20)
    a.emit(0xA9, 0x00, 0xA2, 28)
    a.label('zl_clr12'); a.emit(0x8D, 0x07, 0x20, 0xCA); a.branch(0xD0, 'zl_clr12')
    a.emit(0x68, 0xAA)
    a.abs_ref(0xBD, 'TBL_LOSE_LO'); a.emit(0x85, 0x0E)
    a.abs_ref(0xBD, 'TBL_LOSE_HI'); a.emit(0x85, 0x0F)
    a.abs_ref(0xBD, 'TBL_LOSE_LEN'); a.op16(0x8D, W_TMP0)
    a.abs_ref(0xBD, 'TBL_LOSE_PAD')
    a.emit(0x18, 0x69, 0x02, 0x48)
    a.emit(0xA9, 0x21, 0x8D, 0x06, 0x20, 0x68, 0x8D, 0x06, 0x20)
    a.emit(0xA0, 0x00)
    a.label('zl_wr_r')
    a.emit(0xB1, 0x0E, 0x8D, 0x07, 0x20, 0xC8)
    a.emit(0x98); a.op16(0xCD, W_TMP0); a.branch(0xD0, 'zl_wr_r')
    a.emit(0xA2, 0x00)
    a.label('zl_nlen')
    a.emit(0xBD, 0x08, 0x03, 0x08, 0xE8, 0x28); a.branch(0x10, 'zl_nlen')
    a.op16(0x8E, W_TMP0)
    a.emit(0xA9, 17, 0x38); a.op16(0xED, W_TMP0); a.emit(0x4A)
    a.emit(0x18, 0x69, 0x82, 0x48)
    a.emit(0xA9, 0x21, 0x8D, 0x06, 0x20, 0x68, 0x8D, 0x06, 0x20)
    a.emit(0xA2, 0x00)
    a.label('zl_the')
    a.abs_ref(0xBD, 'TBL_BLUE_THE'); a.emit(0x8D, 0x07, 0x20, 0xE8, 0xE0, 0x04); a.branch(0xD0, 'zl_the')
    a.emit(0xA2, 0x00)
    a.label('zl_name')
    a.emit(0xBD, 0x08, 0x03, 0x08, 0x29, 0x7F, 0x18, 0x69, 0x08, 0x8D, 0x07, 0x20, 0xE8, 0x28)
    a.branch(0x10, 'zl_name')
    a.emit(0xA2, 0x00)
    a.label('zl_fam')
    a.abs_ref(0xBD, 'TBL_BLUE_FAMILY'); a.emit(0x8D, 0x07, 0x20, 0xE8, 0xE0, 0x07); a.branch(0xD0, 'zl_fam')
    a.abs_ref(0x4C, 'B4_RESTORE_ZP')

    # Unrolled $D027 palette copy -> copied to $6F00
    a.label('TBL_FAST_PAL')
    fast_pal_start = len(a.buf)
    a.emit(0xA9, 0x3F, 0x8D, 0x06, 0x20, 0xA9, 0x10, 0x8D, 0x06, 0x20)
    for i in range(16):
        a.emit(0xA5, 0x30 + i, 0x8D, 0x07, 0x20)
    a.emit(0xA9, 0x3F, 0x8D, 0x06, 0x20, 0xA9, 0x00, 0x8D, 0x06, 0x20, 0x85, 0x1F)
    for i in range(16):
        addr = 0x031D + i
        a.emit(0xAD, addr & 0xFF, addr >> 8, 0x8D, 0x07, 0x20)
    a.emit(0xA2, 0x10, 0x60)
    pad_len = 256 - (len(a.buf) - fast_pal_start)
    assert pad_len >= 0
    a.emit(*([0x00] * pad_len))

    out = a.finish()
    assert len(out) <= 0x1200, f'MMC3 Bank 4 code overflowed: {len(out)} > 4608'
    return out
