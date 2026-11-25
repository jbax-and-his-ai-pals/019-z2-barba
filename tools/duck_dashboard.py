"""Export compiled CHR banks, metasprites, BG diffs, and Z2 source banks for the Barba's Hunt web dashboard."""
from __future__ import annotations

import json
from pathlib import Path

from duck_art import (
    CROSSHAIR_TILES,
    FIREBALL_FRAMES,
    HUD_ENEMY_HIT,
    HUD_ENEMY_UNHIT,
    HUD_FIREBALL_ICON,
    HUD_OCTOROK_HIT,
    HUD_OCTOROK_UNHIT,
    SPRITE_PAL_BYTES,
    _bob_up2,
    _composite_16x32,
    _pad32,
    _pair,
    _remap,
    _z2_16x16,
    _z2_16x16_mir,
    _z2_16x32,
    build_duck_chr_and_tables,
)
from nes import CHR_OFFSET, decode_tile, load_source


ROOT = Path(__file__).resolve().parent.parent

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


def _encode_chr_bank(raw: bytes) -> list[str]:
    """Convert raw 16-byte-per-tile CHR bytes into 64-char '0'..'3' strings."""
    count = len(raw) // 16
    out: list[str] = []
    for i in range(count):
        dec = decode_tile(raw[i * 16 : (i + 1) * 16])
        out.append(''.join(str(v) for row in dec for v in row))
    return out


def _flatten_grid(rows: list[str]) -> str:
    return ''.join(rows)


def _z2_24x32(z2: bytes, eb: int, ob: int, t0: int, t1: int, t2: int, b0: int, b1: int, b2: int) -> list[str]:
    def getp(t: int) -> list[str]:
        return _pair(z2, ob if (t & 1) else eb, t)
    top = [getp(t0), getp(t1), getp(t2)]
    bot = [getp(b0), getp(b1), getp(b2)]
    return [top[0][y] + top[1][y] + top[2][y] for y in range(16)] + [
        bot[0][y] + bot[1][y] + bot[2][y] for y in range(16)
    ]


def _z2_mir_pair(z2: bytes, bank: int, tid: int) -> list[str]:
    return _z2_16x16_mir(z2, bank, tid)


def _z2_tids_expand(tids: list[int]) -> list[int]:
    out: list[int] = []
    for t in tids:
        if t == 0xF5:
            continue
        t0 = t & 0xFE
        out.extend((t0, t0 + 1))
    return out


def _build_all_z2_enemies(z2: bytes) -> list[dict]:
    """Extract all Zelda II enemies and bosses with verified 1:1 CHR/tile and Duck Hunt mappings."""
    m_pal0 = {'0': '0', '1': '3', '2': '2', '3': '1'}
    m_ident = {'0': '0', '1': '1', '2': '2', '3': '3'}
    m_octo = {'0': '0', '1': '2', '2': '3', '3': '1'}

    out: list[dict] = []

    def add(
        slug: str,
        name: str,
        category: str,
        pal: int,
        chr_bank: str,
        w: int,
        h: int,
        source: str,
        mapping_status: str,
        dh_mapping: str,
        f0: list[str],
        f1: list[str],
        src_tids: list[int],
    ) -> None:
        out.append({
            'id': f'z2_{slug}',
            'name': name,
            'category': category,
            'pal': pal,
            'chr_bank': chr_bank,
            'w': w,
            'h': h,
            'source': source,
            'mapping_status': mapping_status,
            'dh_mapping': dh_mapping,
            'z2_true_name': name,
            'frames': [_flatten_grid(f0), _flatten_grid(f1)],
            'frame_labels': ['Frame 0', 'Frame 1'],
            'highlight_tids': _z2_tids_expand(src_tids),
        })

    # --- Shared / Multi-Area (Z2 Bank 8 / 9) ---
    add('ache', 'Ache', 'z2_shared', 0, 'z2_bank_8', 16, 32,
        'Z2 Bank 8: mirrored $4E (f0), $50 (f1)', 'match', 'Ported -> DH #0 (Ache)',
        _remap(_pad32(_z2_mir_pair(z2, 8, 0x4E), 8), m_pal0),
        _remap(_pad32(_z2_mir_pair(z2, 8, 0x50), 9), m_pal0),
        [0x4E, 0x50])
    acheman0 = _remap(_z2_16x32(z2, 8, 8, 0x7C, 0x7E, 0x80, 0x82), m_pal0)
    add('acheman', 'Acheman', 'z2_shared', 0, 'z2_bank_8', 16, 32,
        'Z2 Bank 8: $7C/$7E/$80/$82', 'match', 'Ported -> DH #1 (Acheman)',
        acheman0, _bob_up2(acheman0), [0x7C, 0x7E, 0x80, 0x82])
    moa16 = _remap(_z2_16x16(z2, 8, 8, 0xB6, 0xB8), m_ident)
    add('moa', 'Moa', 'z2_shared', 2, 'z2_bank_8', 16, 32,
        'Z2 Bank 8: $B6/$B8 + vflip', 'match', 'Ported -> DH #2 (Moa) & Clay #1',
        _pad32(moa16, 8), _pad32(moa16[::-1], 8), [0xB6, 0xB8])
    bot0 = _remap(_pad32(_z2_mir_pair(z2, 8, 0xB2), 8), m_ident)
    bot1 = _remap(_pad32(_z2_mir_pair(z2, 8, 0xB4), 8), m_ident)
    add('bot', 'Bot', 'z2_shared', 2, 'z2_bank_8', 16, 32,
        'Z2 Bank 8: mirrored $B2 (f0), $B4 (f1)', 'match', 'Ported -> DH #7 (Bot)',
        bot0, bot1, [0xB2, 0xB4])
    add('bit', 'Bit', 'z2_shared', 1, 'z2_bank_8', 16, 32,
        'Z2 Bank 8: mirrored $B2 (f0), $B4 (f1) (Red/Orange)', 'z2_only', 'Shares Bot sprite in Z2 (Pal 1)',
        _remap(_pad32(_z2_mir_pair(z2, 8, 0xB2), 8), m_pal0),
        _remap(_pad32(_z2_mir_pair(z2, 8, 0xB4), 8), m_pal0),
        [0xB2, 0xB4])
    add('bagobago', 'Bago-Bago', 'z2_shared', 0, 'z2_bank_8', 16, 32,
        'Z2 Bank 8: $C0/$C2 (f0), $C0/$C4 (f1)', 'match', 'Ported -> DH #8 (Bago-Bago)',
        _remap(_pad32(_z2_16x16(z2, 8, 8, 0xC0, 0xC2), 8), m_pal0),
        _remap(_pad32(_z2_16x16(z2, 8, 8, 0xC0, 0xC4), 8), m_pal0),
        [0xC0, 0xC2, 0xC4])
    add('myu', 'Myu', 'z2_shared', 2, 'z2_bank_8', 16, 32,
        'Z2 Bank 8: mirrored $24 (f0), $B0 (f1)', 'match', 'Ported -> DH #9 (Myu)',
        _remap(_pad32(_z2_mir_pair(z2, 8, 0x24), 8), m_ident),
        _remap(_pad32(_z2_mir_pair(z2, 8, 0xB0), 8), m_ident),
        [0x24, 0xB0])
    octo0 = _remap(_pad32(_z2_16x16(z2, 8, 8, 0xBA, 0xBC), 8), m_octo)
    add('octorok', 'Octorok', 'z2_shared', 0, 'z2_bank_8', 16, 32,
        'Z2 Bank 8: $BA/$BC', 'match', 'Ported -> Clay #0 (Octorok)',
        octo0, _bob_up2(octo0), [0xBA, 0xBC])
    add('deeler', 'Deeler', 'z2_shared', 0, 'z2_bank_8', 16, 32,
        'Z2 Bank 8: $C6/$C8 (f0), $CA/$CC (f1)', 'z2_only', 'Not yet ported to DH',
        _remap(_pad32(_z2_16x16(z2, 8, 8, 0xC6, 0xC8), 8), m_pal0),
        _remap(_pad32(_z2_16x16(z2, 8, 8, 0xCA, 0xCC), 8), m_pal0),
        [0xC6, 0xC8, 0xCA, 0xCC])
    fairy0_8 = _pair(z2, 8, 0x68)
    fairy1_8 = _pair(z2, 8, 0x6A)
    fairy0 = _remap(_pad32(['0' * 4 + r + '0' * 4 for r in fairy0_8], 8), m_pal0)
    fairy1 = _remap(_pad32(['0' * 4 + r + '0' * 4 for r in fairy1_8], 8), m_pal0)
    add('fairy', 'Fairy (Actual Z2)', 'z2_shared', 1, 'z2_bank_8', 16, 32,
        'Z2 Bank 8: $68 (f0), $6A (f1) (8x16)', 'mismatch', 'Mis-mapped: DH #15 ("Fairy") has $86/$88 instead',
        fairy0, _bob_up2(fairy1), [0x68, 0x6A])

    # --- West Hyrule & Death Mountain (Z2 Bank 2 / 3) ---
    add('moby', 'Moby', 'z2_west', 0, 'z2_bank_2', 16, 32,
        'Z2 Bank 2: $D0/$D2 (f0), $D0/$D4 (f1)', 'match', 'Ported -> DH #8 (Moby)',
        _remap(_pad32(_z2_16x16(z2, 2, 3, 0xD0, 0xD2), 8), m_pal0),
        _remap(_pad32(_z2_16x16(z2, 2, 3, 0xD0, 0xD4), 8), m_pal0),
        [0xD0, 0xD2, 0xD4])
    add('lowder', 'Lowder', 'z2_west', 0, 'z2_bank_2', 16, 32,
        'Z2 Bank 2: $DE/$E0 (f0), $E2/$E0 (f1)', 'match', 'Ported -> DH #9 (Lowder)',
        _remap(_pad32(_z2_16x16(z2, 2, 3, 0xDE, 0xE0), 8), m_pal0),
        _remap(_pad32(_z2_16x16(z2, 2, 3, 0xE2, 0xE0), 8), m_pal0),
        [0xDE, 0xE0, 0xE2])
    add('megmat', 'Megmat', 'z2_west', 0, 'z2_bank_2', 16, 32,
        'Z2 Bank 2: $D6/$D8 (f0), $DA/$DC (f1)', 'match', 'Ported -> DH #10 (Megmat)',
        _remap(_pad32(_z2_16x16(z2, 2, 3, 0xD6, 0xD8), 8), m_pal0),
        _remap(_pad32(_z2_16x16(z2, 2, 3, 0xDA, 0xDC), 8), m_pal0),
        [0xD6, 0xD8, 0xDA, 0xDC])
    add('moblin', 'Moblin', 'z2_west', 0, 'z2_bank_3', 16, 32,
        'Z2 Bank 2/3: $0F/$11/$17/$19 (f0), $0F/$11/$13/$15 (f1)', 'match', 'Ported -> DH #11 (Moblin)',
        _remap(_z2_16x32(z2, 2, 3, 0x0F, 0x11, 0x17, 0x19), m_pal0),
        _remap(_z2_16x32(z2, 2, 3, 0x0F, 0x11, 0x13, 0x15), m_pal0),
        [0x0F, 0x11, 0x13, 0x15, 0x17, 0x19])
    add('daira', 'Daira', 'z2_west', 0, 'z2_bank_2', 16, 32,
        'Z2 Bank 2: $E6/$E8/$EA/$EC (f0), $EE/$F0/$F2/$F4 (f1)', 'match', 'Ported -> DH #12 (Daira)',
        _remap(_z2_16x32(z2, 2, 3, 0xE6, 0xE8, 0xEA, 0xEC), m_pal0),
        _remap(_z2_16x32(z2, 2, 3, 0xEE, 0xF0, 0xF2, 0xF4), m_pal0),
        [0xE6, 0xE8, 0xEA, 0xEC, 0xEE, 0xF0, 0xF2, 0xF4])
    add('goriya', 'Goriya', 'z2_west', 0, 'z2_bank_3', 16, 32,
        'Z2 Bank 2/3: $01/$03/$EA/$EC (f0), $05/$07/$F2/$F4 (f1)', 'match', 'Ported -> DH #13 (Goriya)',
        _remap(_z2_16x32(z2, 2, 3, 0x01, 0x03, 0xEA, 0xEC), m_pal0),
        _remap(_z2_16x32(z2, 2, 3, 0x05, 0x07, 0xF2, 0xF4), m_pal0),
        [0x01, 0x03, 0x05, 0x07, 0xEA, 0xEC, 0xF2, 0xF4])
    geld0 = _remap(['0' * 4 + r + '0' * 4 for r in _pair(z2, 2, 0x62) + _pair(z2, 2, 0x64)], m_pal0)
    add('geldarm', 'Geldarm', 'z2_west', 0, 'z2_bank_2', 16, 32,
        'Z2 Bank 2: $62 (head) + $64 (body)', 'match', 'Ported -> DH #14 (Geldarm)',
        geld0, geld0, [0x62, 0x64])

    # --- East Hyrule & Maze Island (Z2 Bank 4 / 5) ---
    add('tektite', 'Tektite', 'z2_east', 0, 'z2_bank_4', 16, 32,
        'Z2 Bank 4: $D0/$D2/$D4/$D6 (f0), $D8/$DA/$D4/$D6 (f1)', 'match', 'Ported -> DH #15 (Tektite)',
        _remap(_z2_16x32(z2, 4, 5, 0xD0, 0xD2, 0xD4, 0xD6), m_pal0),
        _remap(_z2_16x32(z2, 4, 5, 0xD8, 0xDA, 0xD4, 0xD6), m_pal0),
        [0xD0, 0xD2, 0xD4, 0xD6, 0xD8, 0xDA])
    add('aru_lowder', 'Aru Lowder', 'z2_east', 0, 'z2_bank_4', 24, 32,
        'Z2 Bank 4: $FC/$FE + $EE/$F0/$F4 (f0), $F2 + $FA/$F6/$F8 (f1)', 'match', 'Ported -> DH #16 (Aru Lowder)',
        _remap(['0' * 8 + _z2_16x16(z2, 4, 5, 0xFC, 0xFE)[y] for y in range(16)]
               + [_pair(z2, 4, 0xEE)[y] + _z2_16x16(z2, 4, 5, 0xF0, 0xF4)[y] for y in range(16)], m_pal0),
        _remap(['0' * 8 + _z2_16x16(z2, 4, 5, 0xF5, 0xF2)[y] for y in range(16)]
               + [_pair(z2, 4, 0xFA)[y] + _z2_16x16(z2, 4, 5, 0xF6, 0xF8)[y] for y in range(16)], m_pal0),
        [0xEE, 0xF0, 0xF2, 0xF4, 0xF6, 0xF8, 0xFA, 0xFC, 0xFE])
    zora0 = _remap(_z2_16x32(z2, 4, 5, 0xE6, 0xE8, 0xEA, 0xEC), m_pal0)
    add('zora', 'Zora', 'z2_east', 0, 'z2_bank_4', 16, 32,
        'Z2 Bank 4: $E6/$E8/$EA/$EC', 'match', 'Ported -> DH #17 (Zora)',
        zora0, _bob_up2(zora0), [0xE6, 0xE8, 0xEA, 0xEC])
    add('girobokku', 'Girobokku', 'z2_east', 0, 'z2_bank_5', 16, 32,
        'Z2 Bank 5: $01/$03 (f0), $05/$03 (f1)', 'match', 'Ported -> DH #18 (Girobokku)',
        _remap(_pad32(_z2_16x16(z2, 4, 5, 0x01, 0x03), 8), m_pal0),
        _remap(_pad32(_z2_16x16(z2, 4, 5, 0x05, 0x03), 8), m_pal0),
        [0x01, 0x03, 0x05])
    add('leever', 'Leever', 'z2_east', 0, 'z2_bank_5', 16, 32,
        'Z2 Bank 5: mirrored $07 (f0), $09 (f1)', 'match', 'Ported -> DH #19 (Leever)',
        _remap(_pad32(_z2_mir_pair(z2, 5, 0x07), 8), m_pal0),
        _remap(_pad32(_z2_mir_pair(z2, 5, 0x09), 8), m_pal0),
        [0x07, 0x09])
    add('boon', 'Boon', 'z2_east', 0, 'z2_bank_5', 16, 32,
        'Z2 Bank 5: $0B/$0D (f0), $0B/$0F (f1)', 'match', 'Ported -> DH #20 (Boon)',
        _remap(_pad32(_z2_16x16(z2, 4, 5, 0x0B, 0x0D), 8), m_pal0),
        _remap(_pad32(_z2_16x16(z2, 4, 5, 0x0B, 0x0F), 8), m_pal0),
        [0x0B, 0x0D, 0x0F])
    add('lizalfos', 'Lizalfos', 'z2_east', 0, 'z2_bank_5', 16, 32,
        'Z2 Bank 5: $11/$13/$15/$17 (f0), $11/$13/$19/$1B (f1)', 'match', 'Ported -> DH #21 (Lizalfos)',
        _remap(_z2_16x32(z2, 4, 5, 0x11, 0x13, 0x15, 0x17), m_pal0),
        _remap(_z2_16x32(z2, 4, 5, 0x11, 0x13, 0x19, 0x1B), m_pal0),
        [0x11, 0x13, 0x15, 0x17, 0x19, 0x1B])

    # --- Palaces 1-6 (Z2 Bank 8/9, 18/19, 20/21, 22/23, 24/25) ---
    stalfos0 = _remap(_z2_16x32(z2, 8, 9, 0xF0, 0xF2, 0xF4, 0xF6), m_pal0)
    stalfos1 = _remap(_z2_16x32(z2, 8, 9, 0xF0, 0xF2, 0xF8, 0xFA), m_pal0)
    add('stalfos', 'Stalfos', 'z2_palace', 0, 'z2_bank_8', 16, 32,
        'Z2 Bank 8: $F0/$F2/$F4/$F6 (f0), $F0/$F2/$F8/$FA (f1)', 'match',
        'Ported -> DH #22 (Stalfos)',
        stalfos0, stalfos1, [0xF0, 0xF2, 0xF4, 0xF6, 0xF8, 0xFA])
    ik0 = _remap(_z2_16x32(z2, 8, 9, 0x41, 0x43, 0x49, 0x4B), m_ident)
    ik1 = _remap(_z2_16x32(z2, 8, 9, 0x41, 0x43, 0x45, 0x47), m_ident)
    add('ironknuckle', 'Ironknuckle', 'z2_palace', 2, 'z2_bank_9', 16, 32,
        'Z2 Bank 9: $41/$43/$49/$4B (f0), $41/$43/$45/$47 (f1)', 'match',
        'Ported -> DH #23 (Ironknuckle)',
        ik0, ik1, [0x41, 0x43, 0x45, 0x47, 0x49, 0x4B])
    wiz0 = _remap(_z2_16x32(z2, 20, 21, 0xD0, 0xD2, 0xD4, 0xD6), m_ident)
    add('wizzrobe', 'Wizzrobe', 'z2_palace', 2, 'z2_bank_20', 16, 32,
        'Z2 Bank 20: $D0/$D2/$D4/$D6', 'match',
        'Ported -> DH #24 (Wizzrobe)',
        wiz0, _bob_up2(wiz0), [0xD0, 0xD2, 0xD4, 0xD6])
    mago0 = _remap(_z2_16x32(z2, 22, 23, 0xD0, 0xD2, 0xD4, 0xD6), m_ident)
    add('mago', 'Mago', 'z2_palace', 2, 'z2_bank_22', 16, 32,
        'Z2 Bank 22: $D0/$D2/$D4/$D6', 'match', 'Ported -> DH #25 (Mago)',
        mago0, _bob_up2(mago0), [0xD0, 0xD2, 0xD4, 0xD6])
    guma0 = _remap(_z2_16x32(z2, 8, 9, 0xE0, 0xE2, 0xE4, 0xE6), m_pal0)
    guma1 = _remap(_z2_16x32(z2, 8, 9, 0xE0, 0xE2, 0xE8, 0xEA), m_pal0)
    add('guma', 'Guma', 'z2_palace', 0, 'z2_bank_8', 16, 32,
        'Z2 Bank 8: $E0/$E2/$E4/$E6 (f0), $E0/$E2/$E8/$EA (f1)', 'match', 'Ported -> DH #26 (Guma)',
        guma0, guma1, [0xE0, 0xE2, 0xE4, 0xE6, 0xE8, 0xEA])
    mau0 = _remap(_pad32(_z2_16x16(z2, 18, 19, 0x39, 0x3B), 8), m_pal0)
    add('mau', 'Mau (Wolf Head)', 'z2_palace', 0, 'z2_bank_19', 16, 32,
        'Z2 Bank 19: $39/$3B', 'match', 'Ported -> DH #27 (Mau)',
        mau0, _bob_up2(mau0), [0x39, 0x3B])

    # --- Great Palace (Z2 Bank 12 / 13) ---
    fokka0 = _remap(_z2_16x32(z2, 12, 13, 0x41, 0x43, 0x49, 0x4B), m_pal0)
    add('fokka', 'Fokka', 'z2_great_palace', 0, 'z2_bank_13', 16, 32,
        'Z2 Bank 13: $41/$43/$49/$4B', 'match',
        'Ported -> DH #28 (Fokka)',
        fokka0, fokka0, [0x41, 0x43, 0x49, 0x4B])
    fokkeru0 = _remap(_z2_16x32(z2, 12, 13, 0xE0, 0xE2, 0xE4, 0xE6), m_pal0)
    fokkeru1 = _remap(_z2_16x32(z2, 12, 13, 0xE8, 0xEA, 0xEC, 0xEE), m_pal0)
    add('fokkeru', 'Fokkeru', 'z2_great_palace', 0, 'z2_bank_12', 16, 32,
        'Z2 Bank 12: $E0/$E2/$E4/$E6 (f0), $E8/$EA/$EC/$EE (f1)', 'match',
        'Ported -> DH #29 (Fokkeru)',
        fokkeru0, fokkeru1, [0xE0, 0xE2, 0xE4, 0xE6, 0xE8, 0xEA, 0xEC, 0xEE])
    ra0 = _remap(_pad32(_z2_16x16(z2, 12, 13, 0x35, 0x37), 8), m_pal0)
    add('ra', 'Ra', 'z2_great_palace', 0, 'z2_bank_13', 16, 32,
        'Z2 Bank 13: $35/$37', 'match',
        'Ported -> DH #30 (Ra)',
        ra0, ra0, [0x35, 0x37])
    fr0 = _remap(_pad32(_z2_16x16(z2, 12, 13, 0x0B, 0x0D), 8), m_pal0)
    add('firerope', 'Fire Rope', 'z2_great_palace', 0, 'z2_bank_13', 16, 32,
        'Z2 Bank 13: $0B/$0D', 'match',
        'Ported -> DH #31 (Firerope)',
        fr0, fr0, [0x0B, 0x0D])
    gb0, gb2, gb4 = _pair(z2, 12, 0xF0), _pair(z2, 12, 0xF2), _pair(z2, 12, 0xF4)
    gb6, gb8, gba = _pair(z2, 12, 0xF6), _pair(z2, 12, 0xF8), _pair(z2, 12, 0xFA)
    gbot_48 = _remap([
        gb0[y] + gb2[y] + gb4[y] + gb4[y][::-1] + gb2[y][::-1] + gb0[y][::-1] for y in range(16)
    ] + [
        gb6[y] + gb8[y] + gba[y] + gba[y][::-1] + gb8[y][::-1] + gb6[y][::-1] for y in range(16)
    ], m_ident)
    add('giant_bot', 'Giant Bot', 'z2_great_palace', 2, 'z2_bank_12', 48, 32,
        'Z2 Bank 12: $F0/$F2/$F4/$F6/$F8/$FA (48x32 mirrored)', 'match', 'Ported -> DH #32 (Giant Bot)',
        gbot_48, gbot_48, [0xF0, 0xF2, 0xF4, 0xF6, 0xF8, 0xFA])

    # --- Bosses ---
    hh0 = _remap(_z2_16x32(z2, 8, 9, 0x1B, 0x1D, 0x1F, 0x21) + _z2_16x16(z2, 8, 9, 0x13, 0x15), m_pal0)
    add('horsehead', 'Horsehead (Palace 1)', 'z2_boss', 0, 'z2_bank_9', 16, 48,
        'Z2 Bank 9: $1B/$1D/$1F/$21/$13/$15', 'match', 'Ported -> DH #33 (Horsehead)',
        hh0, hh0, [0x1B, 0x1D, 0x1F, 0x21, 0x13, 0x15])
    helm_body = _z2_16x32(z2, 8, 9, 0x41, 0x43, 0x45, 0x47)
    def _helm_frame(tid: int, hy: int) -> list[str]:
        canvas = [list('0' * 16) for _ in range(16)] + [list(r) for r in helm_body]
        head = _pair(z2, 9, tid)
        for y in range(16):
            for x in range(8):
                if head[y][x] != '0':
                    canvas[hy + y][4 + x] = head[y][x]
        return _remap([''.join(r) for r in canvas], m_ident)
    helm0, helm1 = _helm_frame(0x09, 6), _helm_frame(0x0B, 4)
    add('helmethead', 'Helmethead (Palace 2)', 'z2_boss', 2, 'z2_bank_9', 16, 48,
        'Z2 Bank 9: $09/$0B (helmet) + $41/$43/$45/$47 (body)', 'z2_only', 'Not yet ported to DH',
        helm0, helm1, [0x09, 0x0B, 0x41, 0x43, 0x45, 0x47])
    reb0 = _remap(
        [_z2_16x16(z2, 19, 19, 0x09, 0x0B)[y] + _z2_16x16(z2, 19, 19, 0x4D, 0x43)[y] for y in range(16)]
        + [_z2_16x16(z2, 19, 19, 0x0D, 0x0F)[y] + _z2_16x16(z2, 19, 19, 0x11, 0x13)[y] for y in range(16)],
        m_ident,
    )
    reb1 = _remap(
        [_z2_16x16(z2, 19, 19, 0x09, 0x0B)[y] + _z2_16x16(z2, 19, 19, 0x4D, 0x43)[y] for y in range(16)]
        + [_z2_16x16(z2, 19, 19, 0x0D, 0x0F)[y] + _z2_16x16(z2, 19, 19, 0x1F, 0x21)[y] for y in range(16)],
        m_ident,
    )
    add('rebonack', 'Rebonack (Palace 3)', 'z2_boss', 2, 'z2_bank_19', 32, 32,
        'Z2 Bank 19: $09/$0B/$4D/$43 + $0D/$0F/$11/$13 (f0), $1F/$21 (f1) (32x32)', 'z2_only', 'Not yet ported to DH',
        reb0, reb1, [0x09, 0x0B, 0x0D, 0x0F, 0x11, 0x13, 0x1F, 0x21, 0x43, 0x4D])
    car0 = _remap(
        [_z2_16x16(z2, 21, 21, 0x09, 0x0B)[y] + _z2_16x16(z2, 21, 21, 0x11, 0x13)[y] for y in range(16)]
        + [_z2_16x16(z2, 21, 21, 0x0D, 0x0F)[y] + _z2_16x16(z2, 21, 21, 0x15, 0x17)[y] for y in range(16)],
        m_ident,
    )
    car1 = _remap(
        [_z2_16x16(z2, 21, 21, 0x1F, 0x21)[y] + _z2_16x16(z2, 21, 21, 0x23, 0x25)[y] for y in range(16)]
        + [_z2_16x16(z2, 21, 21, 0x27, 0x29)[y] + _z2_16x16(z2, 21, 21, 0x2B, 0x2D)[y] for y in range(16)],
        m_ident,
    )
    add('carock', 'Carock (Palace 4)', 'z2_boss', 2, 'z2_bank_21', 32, 32,
        'Z2 Bank 21: $09..$17 (f0), $1F..$2D (f1) (32x32)', 'z2_only', 'Not yet ported to DH',
        car0, car1, [0x09, 0x0B, 0x0D, 0x0F, 0x11, 0x13, 0x15, 0x17, 0x1F, 0x21, 0x23, 0x25, 0x27, 0x29, 0x2B, 0x2D])
    goo0 = _remap(
        [''.join(_pair(z2, 23, t)[y] for t in (0x09, 0x0B, 0x0D)) for y in range(16)]
        + [''.join(_pair(z2, 23, t)[y] for t in (0x0F, 0x11, 0x13)) for y in range(16)]
        + [''.join(_pair(z2, 23, t)[y] for t in (0x15, 0x17, 0x19)) for y in range(16)],
        m_pal0,
    )
    add('gooma', 'Gooma (Palace 5)', 'z2_boss', 0, 'z2_bank_23', 24, 48,
        'Z2 Bank 23: $09/$0B/$0D/$0F/$11/$13/$15/$17/$19', 'match', 'Ported -> DH #35 (Gooma)',
        goo0, goo0, [0x09, 0x0B, 0x0D, 0x0F, 0x11, 0x13, 0x15, 0x17, 0x19])
    def _tb_frame(rows_tids: tuple[tuple[int, int], ...]) -> list[str]:
        half: list[str] = []
        for a, b in rows_tids:
            half.extend(_z2_16x16(z2, 13, 13, a, b))
        return _remap([r + r[::-1] for r in half], m_pal0)
    tb0 = _tb_frame(((0x11, 0x13), (0x17, 0x29), (0x1D, 0x1F), (0x21, 0x23)))
    tb1 = _tb_frame(((0x11, 0x13), (0x17, 0x2B), (0x1D, 0x1F), (0x25, 0x27)))
    add('thunderbird', 'Thunderbird (Great Palace)', 'z2_boss', 0, 'z2_bank_13', 32, 64,
        'Z2 Bank 13: $11/$13/$17/$29/$1D/$1F/$21/$23 (mirrored 32x64)', 'z2_only', 'Not yet ported to DH',
        tb0, tb1, [0x11, 0x13, 0x17, 0x29, 0x1D, 0x1F, 0x21, 0x23, 0x2B, 0x25, 0x27])
    m_dark = {'0': '0', '1': '1', '2': '1', '3': '1'}
    dlink0 = _remap(_z2_16x32(z2, 2, 3, 0x00, 0x02, 0x04, 0x06), m_dark)
    dlink1 = _remap(_z2_16x32(z2, 2, 3, 0x08, 0x0A, 0x0C, 0x0E), m_dark)
    add('dark_link', 'Dark Link (Great Palace)', 'z2_boss', 2, 'z2_bank_2', 16, 32,
        'Z2 Bank 2: $00/$02/$04/$06 & $08/$0A/$0C/$0E (silhouette)', 'z2_only', 'Villainous Link uses Link tiles (Pal 3)',
        dlink0, dlink1, [0x00, 0x02, 0x04, 0x06, 0x08, 0x0A, 0x0C, 0x0E])

    return out


def generate_duck_tiles_dashboard(
    duck_path: Path = ROOT / 'roms' / 'duck.nes',
    z2_path: Path = ROOT / 'roms' / 'z2.nes',
    out_js: Path = ROOT / 'web' / 'duck_tiles_data.js',
) -> int:
    """Build web/duck_tiles_data.js with all compiled Duck Hunt CHR banks, sprites, BG diffs, and Z2 sources."""
    if not duck_path.exists() or not z2_path.exists():
        return 0

    duck_bytes = duck_path.read_bytes()
    z2_bytes = load_source(z2_path)
    art = build_duck_chr_and_tables(duck_bytes, z2_bytes)

    orig_chr = duck_bytes[16 + 16384 : 16 + 16384 + 8192]
    orig_spr = orig_chr[0:4096]
    orig_bg = orig_chr[4096:8192]
    chr32 = art['chr']

    chr_banks = [
        {
            'id': 'r0_villagers',
            'label': 'R0 Bank 0 (R0=8) — Shared / Overworld ($00–$7F)',
            'group': 'compiled',
            'base_tid': 0x00,
            'default_pal': 'spr0',
            'tiles': _encode_chr_bank(chr32[8 * 1024 : 10 * 1024]),
        },
        {
            'id': 'r0_villagers2',
            'label': 'R0 Bank 1 (R0=22) — West Hyrule ($00–$7F)',
            'group': 'compiled',
            'base_tid': 0x00,
            'default_pal': 'spr0',
            'tiles': _encode_chr_bank(chr32[22 * 1024 : 24 * 1024]),
        },
        {
            'id': 'r0_villagers3',
            'label': 'R0 Bank 2 (R0=24) — East Hyrule ($00–$7F)',
            'group': 'compiled',
            'base_tid': 0x00,
            'default_pal': 'spr0',
            'tiles': _encode_chr_bank(chr32[24 * 1024 : 26 * 1024]),
        },
        {
            'id': 'r0_villagers4',
            'label': 'R0 Bank 3 (R0=26) — Palaces 1–6 ($00–$7F)',
            'group': 'compiled',
            'base_tid': 0x00,
            'default_pal': 'spr0',
            'tiles': _encode_chr_bank(chr32[26 * 1024 : 28 * 1024]),
        },
        {
            'id': 'r0_villagers5',
            'label': 'R0 Bank 4 (R0=28) — Great Palace & Bosses ($00–$7F)',
            'group': 'compiled',
            'base_tid': 0x00,
            'default_pal': 'spr0',
            'tiles': _encode_chr_bank(chr32[28 * 1024 : 30 * 1024]),
        },
        {
            'id': 'r0_clay',
            'label': 'R0 Bank 1 — Clay Targets ($00–$7F)',
            'group': 'compiled',
            'base_tid': 0x00,
            'default_pal': 'spr0',
            'tiles': _encode_chr_bank(chr32[10 * 1024 : 12 * 1024]),
        },
        {
            'id': 'r0_title',
            'label': 'R0 Bank 2 — Title Sprites ($00–$7F)',
            'group': 'compiled',
            'base_tid': 0x00,
            'default_pal': 'spr1',
            'tiles': _encode_chr_bank(chr32[12 * 1024 : 14 * 1024]),
        },
        {
            'id': 'r1_barba',
            'label': 'R1 Bank 0 — Barba + Score ($80–$FF)',
            'group': 'compiled',
            'base_tid': 0x80,
            'default_pal': 'spr1',
            'tiles': _encode_chr_bank(chr32[14 * 1024 : 16 * 1024]),
        },
        {
            'id': 'r1_link',
            'label': 'R1 Bank 1 — Villainous Link ($80–$FF)',
            'group': 'compiled',
            'base_tid': 0x80,
            'default_pal': 'spr3',
            'tiles': _encode_chr_bank(chr32[16 * 1024 : 18 * 1024]),
        },
        {
            'id': 'game_bg',
            'label': 'Gameplay BG ($00–$FF)',
            'group': 'compiled',
            'base_tid': 0x00,
            'default_pal': 'bg_sky',
            'tiles': _encode_chr_bank(chr32[0 * 1024 : 4 * 1024]),
        },
        {
            'id': 'forest_bg',
            'label': 'Forest Encounter BG ($00–$FF)',
            'group': 'compiled',
            'base_tid': 0x00,
            'default_pal': 'bg_forest',
            'tiles': _encode_chr_bank(chr32[18 * 1024 : 22 * 1024]),
        },
        {
            'id': 'orig_spr',
            'label': 'Vanilla Duck Hunt — Sprites ($00–$FF)',
            'group': 'vanilla',
            'base_tid': 0x00,
            'default_pal': 'spr0',
            'tiles': _encode_chr_bank(orig_spr),
        },
        {
            'id': 'orig_bg',
            'label': 'Vanilla Duck Hunt — BG ($00–$FF)',
            'group': 'vanilla',
            'base_tid': 0x00,
            'default_pal': 'bg_sky',
            'tiles': _encode_chr_bank(orig_bg),
        },
    ]

    z2_source_banks = [
        (2, 'Z2 Bank 2 — West Hyrule Even (Link, Moby, Lowder, Megmat, Goriya)'),
        (3, 'Z2 Bank 3 — West Hyrule Odd / Forest BG (Moblin, Daira, Geldarm)'),
        (4, 'Z2 Bank 4 — East Hyrule Even (Tektite, Aru Lowder, Zora)'),
        (5, 'Z2 Bank 5 — East Hyrule Odd (Girobokku, Leever, Boon, Lizalfos)'),
        (8, 'Z2 Bank 8 — Palace 1 / Shared Even (Ache, Moa, Bot, Stalfos)'),
        (9, 'Z2 Bank 9 — Palace 1 Odd (Ironknuckle, Horsehead)'),
        (10, 'Z2 Bank 10 — Palace 2 Even'),
        (11, 'Z2 Bank 11 — Palace 2 Odd (Helmethead)'),
        (12, 'Z2 Bank 12 — Great Palace Even (Fokkeru, Giant Bot)'),
        (13, 'Z2 Bank 13 — Great Palace Odd (Fokka, Ra, Fire Rope, Thunderbird)'),
        (18, 'Z2 Bank 18 — Palace 3 Even'),
        (19, 'Z2 Bank 19 — Palace 3 Odd (Mau, Rebonack)'),
        (20, 'Z2 Bank 20 — Palace 4 Even (Wizzrobe)'),
        (21, 'Z2 Bank 21 — Palace 4 Odd (Carock)'),
        (22, 'Z2 Bank 22 — Palace 5 Even (Mago)'),
        (23, 'Z2 Bank 23 — Palace 5 Odd (Gooma)'),
        (24, 'Z2 Bank 24 — Palace 6 Even (Guma)'),
        (25, 'Z2 Bank 25 — Palace 6 Odd (Guma, Barba)'),
    ]
    for bank_idx, label in z2_source_banks:
        off = CHR_OFFSET + bank_idx * 4096
        chr_banks.append({
            'id': f'z2_bank_{bank_idx}',
            'label': label,
            'group': 'z2',
            'base_tid': 0x00,
            'default_pal': 'spr0',
            'tiles': _encode_chr_bank(z2_bytes[off : off + 4096]),
        })

    # Sprite palettes + helpful BG palettes for inspection
    palettes = {
        'spr0': {'label': 'Spr Pal 0 (White/Red/Blk)', 'colors': list(SPRITE_PAL_BYTES[0:4])},
        'spr1': {'label': 'Spr Pal 1 (Red/Org/Wht)', 'colors': list(SPRITE_PAL_BYTES[4:8])},
        'spr2': {'label': 'Spr Pal 2 (Blk/Blu/Skin)', 'colors': list(SPRITE_PAL_BYTES[8:12])},
        'spr3': {'label': 'Spr Pal 3 (Blk/Grn/Skin)', 'colors': list(SPRITE_PAL_BYTES[12:16])},
        'bg_sky': {'label': 'BG Sky/Grass (Duck Hunt)', 'colors': [0x21, 0x2A, 0x1A, 0x0F]},
        'bg_forest': {'label': 'BG Forest (Black/Green)', 'colors': [0x0F, 0x1A, 0x29, 0x30]},
        'bg_hud': {'label': 'BG HUD (Black/Blue/Wht/Red)', 'colors': [0x0F, 0x11, 0x30, 0x16]},
        'gray': {'label': 'Grayscale (0..3)', 'colors': [0x0F, 0x00, 0x10, 0x30]},
    }

    z2_sources_by_slug = {
        'ache': 'Z2 Bank 8: mirrored $4E (f0), $50 (f1)',
        'acheman': 'Z2 Bank 8: $7C/$7E/$80/$82',
        'moa': 'Z2 Bank 8: $B6/$B8 + vflip',
        'bot': 'Z2 Bank 8: mirrored $B2 (f0), $B4 (f1)',
        'bagobago': 'Z2 Bank 8: $C0/$C2 (f0), $C0/$C4 (f1)',
        'myu': 'Z2 Bank 8: mirrored $24 (f0), $B0 (f1)',
        'deeler': 'Z2 Bank 8: $C6/$C8 (f0), $CA/$CC (f1)',
        'fairy': 'Z2 Bank 8: $68 (f0), $6A (f1)',
        'moby': 'Z2 Bank 2: $D0/$D2 (f0), $D0/$D4 (f1)',
        'lowder': 'Z2 Bank 2: $DE/$E0 (f0), $E2/$E0 (f1)',
        'megmat': 'Z2 Bank 2: $D6/$D8 (f0), $DA/$DC (f1)',
        'moblin': 'Z2 Bank 2/3: $0F/$11/$17/$19 (f0), $0F/$11/$13/$15 (f1)',
        'daira': 'Z2 Bank 2: $E6/$E8/$EA/$EC (f0), $EE/$F0/$F2/$F4 (f1)',
        'goriya': 'Z2 Bank 2/3: $01/$03/$EA/$EC (f0), $05/$07/$F2/$F4 (f1)',
        'geldarm': 'Z2 Bank 2: $62 (head) + $64 (body) centered',
        'tektite': 'Z2 Bank 4: $D0/$D2/$D4/$D6 (f0), $D8/$DA/$D4/$D6 (f1)',
        'aru_lowder': 'Z2 Bank 4: $FC/$FE + $EE/$F0/$F4 (f0), $F2 + $FA/$F6/$F8 (f1) (24x32 -> 16x32)',
        'zora': 'Z2 Bank 4: $E6/$E8/$EA/$EC',
        'girobokku': 'Z2 Bank 5: $01/$03 (f0), $05/$03 (f1)',
        'leever': 'Z2 Bank 5: mirrored $07 (f0), $09 (f1)',
        'boon': 'Z2 Bank 5: $0B/$0D (f0), $0B/$0F (f1)',
        'lizalfos': 'Z2 Bank 5: $11/$13/$15/$17 (f0), $11/$13/$19/$1B (f1)',
        'stalfos': 'Z2 Bank 8: $F0/$F2/$F4/$F6 (f0), $F0/$F2/$F8/$FA (f1)',
        'ironknuckle': 'Z2 Bank 9: $41/$43/$49/$4B (f0), $41/$43/$45/$47 (f1)',
        'wizzrobe': 'Z2 Bank 20/21: $D0/$D2/$D4/$D6',
        'mago': 'Z2 Bank 22: $D0/$D2/$D4/$D6',
        'guma': 'Z2 Bank 8: $E0/$E2/$E4/$E6 (f0), $E0/$E2/$E8/$EA (f1)',
        'mau': 'Z2 Bank 19: $39/$3B',
        'fokka': 'Z2 Bank 13: $41/$43/$49/$4B',
        'fokkeru': 'Z2 Bank 12: $E0/$E2/$E4/$E6 (f0), $E8/$EA/$EC/$EE (f1)',
        'ra': 'Z2 Bank 13: $35/$37',
        'firerope': 'Z2 Bank 13: $0B/$0D',
        'horsehead': 'Z2 Bank 9: $1B/$1D/$1F/$21/$13/$15 (16x48 -> 16x32)',
        'gooma': 'Z2 Bank 23: $09/$0B/$0D/$0F/$11/$13/$15/$17/$19 (24x48 -> 16x32)',
    }
    clay_sources = {
        'octorok': 'Z2 Bank 8: $BA/$BC, m_octo',
        'moa': 'Z2 Bank 8: $B6/$B8, m_ident',
    }

    sprites: list[dict] = []

    # 1. Ported Duck Hunt Flying Enemies (36 enemies across 5 themed R0 banks)
    global_idx = 0
    for r0_id, bank_key, bank_label, specs in art['preview_grids']['villager_banks']:
        for name, pal_idx, f0, f1 in specs:
            pretty = name.replace('_', ' ').title()
            sprites.append({
                'id': f'villager_{name}',
                'name': f'DH #{global_idx}: {pretty}',
                'category': 'villager',
                'sub_group': bank_label,
                'tab': 'dh_enemies',
                'pal': pal_idx,
                'chr_bank': bank_key,
                'w': 16,
                'h': 32,
                'source': f'{z2_sources_by_slug.get(name, "")} (R0={r0_id})',
                'mapping_status': 'match',
                'dh_mapping': f'DH #{global_idx} ({bank_label}) -> Z2 {pretty} (1:1 Match)',
                'z2_true_name': pretty,
                'frames': [_flatten_grid(f0), _flatten_grid(f1)],
                'frame_labels': ['Frame 0', 'Frame 1'],
                'tile_maps': [art['villager_maps'][global_idx * 2], art['villager_maps'][global_idx * 2 + 1]],
            })
            global_idx += 1

    # 2. Clay / Game C Targets
    for idx, (name, pal_idx, f0, f1) in enumerate(art['preview_grids']['clay']):
        sprites.append({
            'id': f'clay_{name}',
            'name': f'Clay #{idx}: {name.capitalize()}',
            'category': 'clay',
            'tab': 'dh_enemies',
            'pal': pal_idx,
            'chr_bank': 'r0_clay',
            'w': 16,
            'h': 16,
            'source': clay_sources.get(name, ''),
            'mapping_status': 'match',
            'dh_mapping': f'Clay #{idx} -> Z2 {name.capitalize()} (1:1 Match)',
            'z2_true_name': name.capitalize(),
            'frames': [_flatten_grid(f0), _flatten_grid(f1)],
            'frame_labels': ['Frame 0', 'Frame 1'],
            'tile_maps': [art['clay_maps'][idx * 4], art['clay_maps'][idx * 4 + 1]],
        })

    # 3. Barba Poses
    for idx, (name, pal_idx, grid) in enumerate(art['preview_grids']['barba']):
        sprites.append({
            'id': f'barba_{name}',
            'name': f'Barba: {name}',
            'category': 'barba',
            'tab': 'barba',
            'pal': pal_idx,
            'chr_bank': 'r1_barba',
            'w': 56,
            'h': 96,
            'source': 'Z2 Barba 24x48 + connector/trail (origin x=32, y=48)',
            'frames': [_flatten_grid(grid)],
            'frame_labels': [name],
            'metasprite': [[tid, dx, dy] for tid, dx, dy in art['barba_maps'][idx]],
        })

    # 4. Villainous Link
    link_grids = [g for _, _, g in art['preview_grids']['link']]
    sprites.append({
        'id': 'villainous_link',
        'name': 'Villainous Link',
        'category': 'link',
        'tab': 'barba',
        'pal': 3,
        'chr_bank': 'r1_link',
        'w': 16,
        'h': 32,
        'source': 'Z2 Bank 2/3: $00/$02/$04/$06 & $08/$0A/$0C/$0E, flip_h, Pal 3',
        'frames': [_flatten_grid(link_grids[0]), _flatten_grid(link_grids[1])],
        'frame_labels': ['Stand', 'Walk'],
        'tile_maps': [art['link_maps'][0], art['link_maps'][1]],
    })

    # 5. Shared R0 (Crosshair & Fireball)
    ch16 = [CROSSHAIR_TILES[0][y] + CROSSHAIR_TILES[1][y] for y in range(8)] + [
        CROSSHAIR_TILES[2][y] + CROSSHAIR_TILES[3][y] for y in range(8)
    ]
    sprites.append({
        'id': 'shared_crosshair',
        'name': 'Crosshair',
        'category': 'shared',
        'tab': 'barba',
        'pal': 1,
        'chr_bank': 'r0_villagers',
        'w': 16,
        'h': 16,
        'source': 'Custom 16x16 Crosshair ($00–$03)',
        'frames': [_flatten_grid(ch16)],
        'frame_labels': ['Crosshair'],
        'tile_maps': [[0x00, 0x01, 0x02, 0x03]],
    })
    sprites.append({
        'id': 'shared_fireball',
        'name': 'Fireball Burst',
        'category': 'shared',
        'tab': 'barba',
        'pal': 1,
        'chr_bank': 'r0_villagers',
        'w': 16,
        'h': 16,
        'source': 'Custom 16x16 3-frame burst ($04–$0F)',
        'frames': [_flatten_grid(list(fb)) for fb in FIREBALL_FRAMES],
        'frame_labels': ['Core', 'Ring', 'Embers'],
        'tile_maps': [[0x04, 0x05, 0x06, 0x07], [0x08, 0x09, 0x0A, 0x0B], [0x0C, 0x0D, 0x0E, 0x0F]],
    })

    # 6. All Zelda II Enemies & Bosses (1:1 Z2 Reference + DH Port Status)
    dh_by_slug: dict[str, int] = {}
    gi = 0
    for _, _, _, specs in art['preview_grids']['villager_banks']:
        for sname, _, _, _ in specs:
            dh_by_slug[sname] = gi
            gi += 1
    z2_all = _build_all_z2_enemies(z2_bytes)
    for entry in z2_all:
        slug = entry['id'].removeprefix('z2_')
        entry['tab'] = 'z2_ref'
        if slug in dh_by_slug:
            entry['mapping_status'] = 'match'
            entry['dh_mapping'] = f'Ported -> DH #{dh_by_slug[slug]} ({entry["name"]})'
        elif slug == 'octorok':
            entry['mapping_status'] = 'match'
            entry['dh_mapping'] = 'Ported -> Clay #0 (Octorok)'
        elif slug == 'dark_link':
            entry['mapping_status'] = 'z2_only'
            entry['dh_mapping'] = 'Villainous Link uses Link tiles (Pal 3)'
        else:
            entry['mapping_status'] = 'z2_only'
            entry['dh_mapping'] = 'Z2 Reference Only (Not in DH pool)'
    sprites.extend(z2_all)

    # BG tile diffs (vanilla vs game_bg / forest_bg)
    bg_patches: list[dict] = []
    game_bg_tiles = _encode_chr_bank(chr32[0 * 1024 : 4 * 1024])
    forest_bg_tiles = _encode_chr_bank(chr32[18 * 1024 : 22 * 1024])
    orig_bg_tiles = _encode_chr_bank(orig_bg)
    z2_b3_tiles = _encode_chr_bank(z2_bytes[CHR_OFFSET + 3 * 4096 : CHR_OFFSET + 4 * 4096])

    hud_notes = {
        0xD3: ('HUD Octorok Hit', 'game_bg'),
        0xD4: ('HUD Octorok Unhit', 'game_bg'),
        0xD5: ('HUD Enemy Hit', 'game_bg'),
        0xD6: ('HUD Enemy Unhit', 'game_bg'),
        0xD7: ('HUD Pass Line (forest remap 0->2)', 'forest_bg'),
        0xD9: ('HUD Fireball Icon', 'game_bg'),
        0xDA: ('HUD SHOT "S" (forest remap 0->2)', 'forest_bg'),
        0xDB: ('HUD SHOT "HO" (forest remap 0->2)', 'forest_bg'),
        0xDC: ('HUD SHOT "T" (forest remap 0->2)', 'forest_bg'),
    }
    for tid, (note, bank_name) in hud_notes.items():
        bg_patches.append({
            'tid': tid,
            'bank': bank_name,
            'note': note,
            'orig': orig_bg_tiles[tid],
            'patched': forest_bg_tiles[tid] if bank_name == 'forest_bg' else game_bg_tiles[tid],
            'z2_src': None,
        })

    forest_tile_map = (
        (0x60, 0x44, 'Tree Trunk TL'), (0x61, 0x45, 'Tree Trunk BL'),
        (0x62, 0x46, 'Tree Trunk TR'), (0x63, 0x47, 'Tree Trunk BR'),
        (0x64, 0x48, 'Forest Ground TL'), (0x65, 0x49, 'Forest Ground BL'),
        (0x66, 0x4A, 'Forest Ground TR'), (0x67, 0x4B, 'Forest Ground BR'),
        (0x68, 0x50, 'Canopy Leaves TL'), (0x69, 0x51, 'Canopy Leaves BL'),
        (0x6A, 0x52, 'Canopy Leaves TR'), (0x6B, 0x53, 'Canopy Leaves BR'),
        (0x6C, 0x54, 'Hanging Leaves L'), (0x6D, 0x55, 'Hanging Leaves R'),
        (0x6E, 0x78, 'Forest Bush L'), (0x6F, 0x79, 'Forest Bush R'),
    )
    for dst_tid, src_tid, note in forest_tile_map:
        bg_patches.append({
            'tid': dst_tid,
            'bank': 'forest_bg',
            'note': f'{note} (Z2 B3 ${src_tid:02X})',
            'orig': orig_bg_tiles[dst_tid],
            'patched': forest_bg_tiles[dst_tid],
            'z2_src': z2_b3_tiles[src_tid],
        })

    payload = {
        'nes_palette': NES_PALETTE_64,
        'palettes': palettes,
        'tile_counts': art['tile_counts'],
        'categories': [
            ('villager', 'DH: Flying Enemies (Ported)'),
            ('clay', 'DH: Clay Targets (Ported)'),
            ('z2_shared', 'Z2: Shared / Overworld'),
            ('z2_west', 'Z2: West Hyrule'),
            ('z2_east', 'Z2: East Hyrule'),
            ('z2_palace', 'Z2: Palaces 1–6'),
            ('z2_great_palace', 'Z2: Great Palace'),
            ('z2_boss', 'Z2: Bosses'),
            ('barba', 'Barba Poses'),
            ('link', 'Villainous Link'),
            ('shared', 'Shared R0'),
        ],
        'sprites': sprites,
        'bg_patches': bg_patches,
        'chr_banks': chr_banks,
    }
    out_js.write_text(f'window.DUCK_TILES_DATA = {json.dumps(payload)};\n', encoding='utf-8')
    return len(sprites)
