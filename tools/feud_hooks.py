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
