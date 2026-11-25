"""PRG-ROM hooks and dynamic cast asset packaging for Family Feud: Barba Edition."""
from __future__ import annotations

import feud_art
import feud_engine
import feud_wram


def _patch_bytes(
    prg_buf: bytearray,
    cpu_addr: int,
    expected_prefix: bytes,
    replacement: bytes,
) -> None:
    off = cpu_addr - 0x8000
    n_chk = len(expected_prefix)
    actual = bytes(prg_buf[off : off + n_chk])
    assert actual == expected_prefix, (
        f'PRG mismatch at ${cpu_addr:04X}: got {actual.hex()}, '
        f'expected {expected_prefix.hex()}'
    )
    assert len(replacement) <= max(n_chk, 3), (
        f'Replacement too long at ${cpu_addr:04X}'
    )
    prg_buf[off : off + len(replacement)] = replacement


def _jsr(addr: int) -> bytes:
    return bytes((0x20, addr & 0xFF, addr >> 8))


def _jmp(addr: int) -> bytes:
    return bytes((0x4C, addr & 0xFF, addr >> 8))


def _patch_round_title(prg_buf: bytearray) -> None:
    """Replace 'ROUND N' (+ 'DOUBLE POINTS') with 'FIRST FEUD'..'TENTH FEUD' at $8542 / $95F7."""
    # 1. Dead vanilla CPU family-name table ($95F7..$963D, 71 bytes) -> 11-byte offsets + 55-byte packed ordinals
    offs: list[int] = [0]
    blob = bytearray()
    for word in feud_engine.ROUND_ORDINALS:
        blob.extend(feud_engine._encode_chr0a_title(word)[:-1])
        offs.append(len(blob))
    tbl_data = bytes(offs) + bytes(blob)
    assert len(tbl_data) <= 71, f'Round ordinal table overflow: {len(tbl_data)} > 71'
    tbl_off = 0x95F7 - 0x8000
    assert bytes(prg_buf[tbl_off : tbl_off + 13]) == bytes.fromhex('0A11171C212830363C414B454E')
    prg_buf[tbl_off : tbl_off + 71] = tbl_data.ljust(71, b'\xEA')

    # 2. Replace $8542..$85C3 (130 bytes) with ordinal + "FEUD" (+ "DOUBLE POINTS" on round >= 3)
    w_feud = feud_engine._encode_chr0a_title('FEUD')
    w_double = feud_engine._encode_chr0a_title('DOUBLE')
    w_points = feud_engine._encode_chr0a_title('POINTS')
    off_feud = 0
    off_double = len(w_feud)
    off_points = off_double + len(w_double)

    a = feud_engine.FeudAsm(0x8542)
    a.emit(0xAD, 0x43, 0x05); a.branch(0xF0, 'drt_not_fm')  # skip in Fast Money
    a.emit(0x60)
    a.label('drt_not_fm')
    a.emit(0xAD, 0x10, 0x03); a.branch(0xD0, 'drt_has_rnd')  # guard round == 0
    a.emit(0x60)
    a.label('drt_has_rnd')
    a.emit(0xC9, 0x0B); a.branch(0xB0, 'drt_ge11')
    a.emit(0x38, 0xE9, 0x01, 0xAA)  # X = round - 1 (0..9)
    a.emit(0xA9, 0x20, 0x8D, 0x06, 0x20, 0xA9, 0x62, 0x8D, 0x06, 0x20)  # PPU $2062 (row 3, col 2)
    a.emit(0xBD, 0xF8, 0x95, 0x85, 0x10)  # end offset -> $10
    a.emit(0xBC, 0xF7, 0x95)              # start offset -> Y
    a.label('drt_ord_loop')
    a.emit(0xB9, 0x02, 0x96, 0x8D, 0x07, 0x20, 0xC8, 0xC4, 0x10)
    a.branch(0xD0, 'drt_ord_loop')
    a.emit(0xA0, 0x82, 0xA2, off_feud); a.abs_ref(0x20, 'drt_puts')  # row 4, col 2: "FEUD"
    a.branch(0x10, 'drt_chk_double')  # always taken (X > 0)

    a.label('drt_ge11')
    a.emit(0xA0, 0x62, 0xA2, off_feud); a.abs_ref(0x20, 'drt_puts')  # row 3, col 2: "FEUD"

    a.label('drt_chk_double')
    a.emit(0xAD, 0x10, 0x03, 0xC9, 0x03); a.branch(0x90, 'drt_done')
    a.emit(0xA0, 0xC2, 0xA2, off_double); a.abs_ref(0x20, 'drt_puts')  # row 6, col 2: "DOUBLE"
    a.emit(0xA0, 0xE2, 0xA2, off_points); a.abs_ref(0x20, 'drt_puts')  # row 7, col 2: "POINTS"
    a.label('drt_done')
    a.emit(0x60)

    a.label('drt_puts')
    a.emit(0xA9, 0x20, 0x8D, 0x06, 0x20, 0x8C, 0x06, 0x20)
    a.label('drt_puts_lp')
    a.abs_ref(0xBD, 'tbl_words'); a.branch(0xF0, 'drt_puts_rts')
    a.emit(0x8D, 0x07, 0x20, 0xE8); a.branch(0xD0, 'drt_puts_lp')
    a.label('drt_puts_rts')
    a.emit(0x60)

    a.label('tbl_words')
    a.emit(*(w_feud + w_double + w_points))

    code = a.finish()
    assert len(code) <= 130, f'Round title routine overflow: {len(code)} > 130'
    fn_off = 0x8542 - 0x8000
    assert bytes(prg_buf[fn_off : fn_off + 5]) == bytes.fromhex('AD4305D06B')
    prg_buf[fn_off : fn_off + 130] = code.ljust(130, b'\xEA')



def apply_feud_prg_hooks(
    prg_buf: bytearray,
    w: dict[str, int],
    c: dict[str, int] | None = None,
) -> None:
    """Install all dynamic-cast, palette, idle-anim, name, and lose hooks."""
    rng_prefix = bytes.fromhex('20BB9BADFA012903')
    oam_prefix = bytes.fromhex('BDCFD19530E8E010D0F6')

    _patch_bytes(
        prg_buf, 0x9653,
        bytes.fromhex('20BB9BADFA01'),
        _jsr(w['W_PICK_Z2_NAME']) + _jmp(0x97BE),
    )
    _patch_bytes(prg_buf, 0x96B3, bytes.fromhex('20D596'), _jsr(w['W_DEFAULT_P1_NAME']))
    _patch_bytes(prg_buf, 0x9914, bytes.fromhex('A60BBC1503'), _jmp(w['W_WRITE_STAGE_ATTR']))
    _patch_bytes(prg_buf, 0x84B2, bytes.fromhex('AE1503BC9D84'), _jmp(w['W_WRITE_OV_ATTR']))
    _patch_round_title(prg_buf)
    _patch_bytes(prg_buf, 0x9942, bytes.fromhex('A000B10E992D03'), _jmp(w['W_PAL_FIX_992E']))
    _patch_bytes(prg_buf, 0xA35C, bytes.fromhex('20A9A3'), _jsr(w['W_PAL_FIX_A307_WRAP']))
    _patch_bytes(prg_buf, 0x8108, oam_prefix, _jsr(w['W_LOAD_OAM_PAL']) + bytes([0xEA] * 7))
    _patch_bytes(prg_buf, 0x9AF2, bytes.fromhex('A20FBDCFD1'), _jmp(w['W_LOAD_OAM_PAL']))
    _patch_bytes(prg_buf, 0xB515, bytes.fromhex('208684'), _jsr(w['W_LOAD_FACEOFF']))
    _patch_bytes(prg_buf, 0xB972, bytes.fromhex('A9059DC705'), bytes.fromhex('A9039DC705'))
    _patch_bytes(prg_buf, 0xB98F, bytes.fromhex('A9129DE505'), bytes.fromhex('A9159DE505'))
    _patch_bytes(prg_buf, 0xBA4E, bytes.fromhex('20D8BBEAEAA9DC'), _jmp(w['W_FACEOFF_ATTR']))
    _patch_bytes(prg_buf, 0xC931, bytes.fromhex('20BB9BADFA012907'), _jmp(w['W_ZELDA_LOSE']))
    _patch_bytes(prg_buf, 0xC9DE, rng_prefix, _jmp(w['W_ROLL_BOTH']))
    _patch_bytes(prg_buf, 0xCA0C, rng_prefix, _jmp(w['W_ROLL_P1']))
    _patch_bytes(prg_buf, 0xCA22, rng_prefix, _jmp(w['W_ROLL_CPU']))
    _patch_bytes(
        prg_buf, 0xD9B7,
        bytes.fromhex('B912DB8519B9DFDB'),
        _jsr(w['W_LOAD_BLK_AND_ATTR']) + _jmp(0xD9CB),
    )
    _patch_bytes(
        prg_buf, 0xDA9A,
        bytes.fromhex(
            'B912DB8545B9DFDB8546'
            'A000B1458540C8B14585418542C9079004E9068542'
        ),
        _jsr(w['W_LOAD_BG_BLK']) + bytes.fromhex(
            'A000B1458540C8B1458541'
            'C906F0069006E906B002A9038542EAEAEA'
        ),
    )
    _patch_bytes(
        prg_buf, 0x8153,
        bytes.fromhex('A2B9CAD0FD'),
        bytes.fromhex('A2B5CAD0FD'),
    )
    _patch_bytes(
        prg_buf, 0x8194,
        bytes.fromhex('A2B9CAD0FD'),
        bytes.fromhex('A2B5CAD0FD'),
    )
    _patch_bytes(
        prg_buf, 0x8715,
        bytes.fromhex('A2C2CAD0FD'),
        bytes.fromhex('A2BFCAD0FD'),
    )
    _patch_bytes(
        prg_buf, 0x9029,
        bytes.fromhex('A2C4CAD0FD'),
        bytes.fromhex('A2C0CAD0FD'),
    )
    _patch_bytes(
        prg_buf, 0x906A,
        bytes.fromhex('A291CAD0FD'),
        bytes.fromhex('A28BCAD0FD'),
    )
    _patch_bytes(
        prg_buf, 0x9080,
        bytes.fromhex('A005A230'),
        bytes.fromhex('A005A218'),
    )
    _patch_bytes(
        prg_buf, 0x908D,
        bytes.fromhex('A003A21DCAD0FD'),
        bytes.fromhex('A003A21BCAD0FD'),
    )
    _patch_bytes(prg_buf, 0xCA6F, bytes.fromhex('20CDCF'), _jsr(w['W_VBLANK_EXTRA']))
    _patch_bytes(
        prg_buf, 0xD027,
        bytes.fromhex('A93F8D0620A9108D0620'),
        _jmp(feud_engine.W_FAST_PAL),
    )
    if c is not None:
        _patch_bytes(
            prg_buf, 0xCA8D,
            bytes.fromhex('A9008D05208D0520'),
            _jsr(c['W_APPLY_SCROLL']) + bytes([0xEA] * 5),
        )
        _patch_bytes(prg_buf, 0xA24D, bytes.fromhex('208698'), _jsr(c['W_CELEB_INIT']))
        _patch_bytes(
            prg_buf, 0xA250,
            bytes.fromhex('A90520F799'),
            _jsr(c['W_CELEB_SET_TIMER']) + bytes([0xEA, 0xEA]),
        )
        _patch_bytes(prg_buf, 0xA26A, bytes.fromhex('205B90'), _jsr(c['W_CELEB_HEAD_TILT_TICK']))
        _patch_bytes(
            prg_buf, 0xA277,
            bytes.fromhex('AD9303290F'),
            _jsr(c['W_CELEB_ROAR_PHASE']) + bytes([0xEA, 0xEA]),
        )


def build_dynamic_assets(
    z2_rom: bytes,
    feud_rom: bytes,
    *,
    base_5ff1: int = 0x00,
    roar_5ff1: int = 0x10,
) -> dict:
    """Compile extra WRAM code, Bank 4 engine, and 18 cast ROM banks."""
    wram_extra, wram_syms = feud_wram.assemble_wram_extra()
    pal_wram, pal_syms = feud_wram.assemble_pal_wram()
    celeb_wram, celeb_syms = feud_wram.assemble_celeb_wram(base_5ff1=base_5ff1, roar_5ff1=roar_5ff1)
    cast_pkg = feud_art.build_cast_rom_banks(z2_rom, feud_rom)
    bank4_code = feud_engine._assemble_bank4(cast_pkg)
    return {
        'wram_extra': wram_extra,
        'wram_syms': {**wram_syms, **pal_syms},
        'pal_wram': pal_wram,
        'celeb_wram': celeb_wram,
        'celeb_syms': celeb_syms,
        'cast_banks': cast_pkg['cast_banks'],
        'bank4_code': bank4_code,
    }
