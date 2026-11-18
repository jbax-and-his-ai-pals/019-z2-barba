"""Build a single NES 2.0 Mapper 176 ROM containing Barba + Where's Waldo?."""
from __future__ import annotations

import zlib
from pathlib import Path

from build import ROOT, build


def make_waldo_nmi_hook() -> bytes:
    """Assemble Waldo's $F603 NMI return hook (Start+Select or 360-frame Moon ending)."""
    # Offsets from $F603:
    # 00: 48          PHA
    # 01: AD FF 7F    LDA $7FFF
    # 04: C9 3C       CMP #$3C
    # 06: B0 05       BCS +5 -> 0D (@check_pad)
    # 08: EE FF 7F    INC $7FFF
    # 0B: D0 08       BNE +8 -> 15 (@check_moon)
    # 0D (@check_pad):
    # 0D: A5 06       LDA $06
    # 0F: 29 0C       AND #$0C
    # 11: C9 0C       CMP #$0C
    # 13: F0 31       BEQ +49 -> 46 (@do_return)
    # 15 (@check_moon):
    # 15: A5 00       LDA $00
    # 17: C9 A8       CMP #$A8
    # 19: D0 1E       BNE +30 -> 39 (@clear_moon)
    # 1B: A5 34       LDA $34
    # 1D: C9 1F       CMP #$1F
    # 1F: D0 18       BNE +24 -> 39 (@clear_moon)
    # 21: A5 56       LDA $56
    # 23: C9 80       CMP #$80
    # 25: D0 12       BNE +18 -> 39 (@clear_moon)
    # 27: EE FD 7F    INC $7FFD
    # 2A: D0 03       BNE +3 -> 2F
    # 2C: EE FE 7F    INC $7FFE
    # 2F: AD FE 7F    LDA $7FFE
    # 32: C9 01       CMP #$01
    # 34: 90 0D       BCC +13 -> 43 (@normal_nmi)
    # 36: AD FD 7F    LDA $7FFD
    # 39: C9 68       CMP #$68
    # 3B: B0 09       BCS +9 -> 46 (@do_return)
    # 3D: 90 04       BCC +4 -> 43 (@normal_nmi)
    #Wait! @clear_moon would overlap 0x39 if @check_moon ended at 0x3F! Let's recount carefully:
    # 0x15: A5 00 C9 A8 (4) -> 0x19: D0 xx (2) -> 0x1B
    # 0x1B: A5 34 C9 1F (4) -> 0x1F: D0 xx (2) -> 0x21
    # 0x21: A5 56 C9 80 (4) -> 0x25: D0 xx (2) -> 0x27
    # 0x27: EE FD 7F (3) -> 0x2A
    # 0x2A: D0 03 (2) -> 0x2C
    # 0x2C: EE FE 7F (3) -> 0x2F
    # 0x2F: AD FE 7F C9 01 (5) -> 0x34
    # 0x34: 90 xx (2) -> 0x36
    # 0x36: AD FD 7F C9 68 (5) -> 0x3B
    # 0x3B: B0 xx (2) -> 0x3D
    # 0x3D: 90 xx (2) -> 0x3F (@clear_moon)
    # 0x3F (@clear_moon): A9 00 8D FD 7F 8D FE 7F (8) -> 0x47 (@normal_nmi)
    # 0x47 (@normal_nmi): 68 4C 37 E2 (4) -> 0x4B (@do_return)
    # 0x4B (@do_return): 4C A4 F9 (3) -> 0x4E (78 bytes <= 81!)
    # Recount branch displacements:
    # 0x13: F0 xx -> target 0x4B, next=0x15 -> 0x4B - 0x15 = 0x36
    # 0x19: D0 xx -> target 0x3F, next=0x1B -> 0x3F - 0x1B = 0x24
    # 0x1F: D0 xx -> target 0x3F, next=0x21 -> 0x3F - 0x21 = 0x1E
    # 0x25: D0 xx -> target 0x3F, next=0x27 -> 0x3F - 0x27 = 0x18
    # 0x34: 90 xx -> target 0x47, next=0x36 -> 0x47 - 0x36 = 0x11
    # 0x3B: B0 xx -> target 0x4B, next=0x3D -> 0x4B - 0x3D = 0x0E
    # 0x3D: 90 xx -> target 0x47, next=0x3F -> 0x47 - 0x3F = 0x08
    return bytes.fromhex(
        '48 ad ff 7f c9 3c b0 05 ee ff 7f d0 08 '
        'a5 06 29 0c c9 0c f0 36 '
        'a5 00 c9 a8 d0 24 '
        'a5 34 c9 1f d0 1e '
        'a5 56 c9 80 d0 18 '
        'ee fd 7f d0 03 ee fe 7f '
        'ad fe 7f c9 01 90 11 '
        'ad fd 7f c9 68 b0 0e 90 08 '
        'a9 00 8d fd 7f 8d fe 7f '
        '68 4c 37 e2 '
        '4c a4 f9'
    )


def pack() -> Path:
    waldo_path = ROOT / 'roms/waldo.nes'
    waldo = waldo_path.read_bytes()
    if waldo[:7] != b'NES\x1a\x08\x10\x40' or zlib.crc32(waldo[16:]) != 0xC3463A3D:
        raise SystemExit('Unexpected Where’s Waldo? ROM at roms/waldo.nes.')

    work_dir = ROOT / 'build/waldo-work'
    report = build(ROOT / 'roms/z2.nes', work_dir, ROOT / 'roms/roar.wav', waldo_portal=True)
    barba = (work_dir / 'barba.nes').read_bytes()
    restore_addr = report['labels']['BarbaWaldoRestore6']

    b_prg = bytearray(barba[16 : 16 + 128 * 1024])
    b_chr = barba[16 + 128 * 1024 :]

    # Patch Barba's $FF81 WRAM enable from $80 -> $A0 (WRAM bank 0 + lock $5FF0-$5FF3)
    off_ff81 = 7 * 16384 + 0x3F81
    assert b_prg[off_ff81 : off_ff81 + 5] == bytes.fromhex('a9 80 8d 01 a0')
    b_prg[off_ff81 + 1] = 0xA0

    w_prg = bytearray(waldo[16 : 16 + 128 * 1024])
    w_chr = waldo[16 + 128 * 1024 :]

    # Patch Waldo's $E031 WRAM enable from $80 -> $A2 (WRAM bank 2 + lock $5FF0-$5FF3)
    assert w_prg[0x1E031:0x1E036] == bytes.fromhex('a9 80 8d 01 a0')
    w_prg[0x1E032] = 0xA2

    # Patch Waldo's NMI hook at $F603-$F653 (free 0x00 region) + vector $FFFA
    hook = make_waldo_nmi_hook()
    assert len(hook) <= 81
    assert all(x == 0 for x in w_prg[0x1F603 : 0x1F603 + len(hook)])
    w_prg[0x1F603 : 0x1F603 + len(hook)] = hook
    assert w_prg[0x1FFFA:0x1FFFC] == bytes.fromhex('37 e2')
    w_prg[0x1FFFA:0x1FFFC] = bytes.fromhex('03 f6')

    # Patch Waldo's $F9A4 return stage: blank PPU/APU/IRQ, map bank 16 @ $8000, JMP $8000
    stage = bytes.fromhex(
        '78 a9 00 8d 00 20 8d 01 20 8d 15 40 8d 00 e0 '
        'a9 06 8d 00 80 a9 10 8d 01 80 4c 00 80'
    )
    assert len(stage) <= 51
    assert all(x == 0 for x in w_prg[0x1F9A4 : 0x1F9A4 + len(stage)])
    w_prg[0x1F9A4 : 0x1F9A4 + len(stage)] = stage

    # Build 512KB PRG:
    #   0..128KB   : Barba
    #   240..256KB : Barba fixed bank ($C000-$FFFF)
    #   256..384KB : Waldo
    #   384..392KB : Bank 16 (Waldo->Barba RAM trampoline)
    #   496..512KB : Waldo fixed bank ($C000-$FFFF) + cold-boot stub to Barba
    prg512 = bytearray(b'\xFF' * (512 * 1024))
    prg512[0 : 128 * 1024] = b_prg
    prg512[240 * 1024 : 256 * 1024] = b_prg[112 * 1024 : 128 * 1024]
    prg512[256 * 1024 : 384 * 1024] = w_prg
    prg512[496 * 1024 : 512 * 1024] = w_prg[112 * 1024 : 128 * 1024]

    tramp = (
        bytes.fromhex(
            'a9 80 8d 01 a0 '
            'a9 01 8d f0 5f '
            'a9 00 8d f1 5f 8d f2 5f '
            'a9 06 8d 00 80 a9 0c 8d 01 80 '
            'a9 07 8d 00 80 a9 0d 8d 01 80 '
            '4c'
        )
        + restore_addr.to_bytes(2, 'little')
    )
    bank16_loader = bytes([0xA2, len(tramp) - 1]) + bytes.fromhex('bd 10 80 9d 00 03 ca 10 f7 4c 00 03')
    prg512[384 * 1024 : 384 * 1024 + len(bank16_loader)] = bank16_loader
    prg512[384 * 1024 + 0x10 : 384 * 1024 + 0x10 + len(tramp)] = tramp

    # Cold-boot stub in 504..512KB (power-on starts in 512KB mode):
    # Place 16-byte loader at $F9C1 (remaining 22B in $F9A4..$F9D6) and 16-byte RAM stub
    # in the next >=16B zero run in $E000-$FFFF.
    off_504 = 504 * 1024
    boot_ram = bytes.fromhex('a9 01 8d f0 5f a9 00 8d f1 5f 8d f2 5f 6c fc ff')
    ram_src = None
    run = 0
    for i in range(0x2000):
        if prg512[off_504 + i] == 0:
            run += 1
            if run == len(boot_ram):
                ram_src = 0xE000 + i - run + 1
                prg512[off_504 + i - run + 1 : off_504 + i + 1] = boot_ram
                break
        else:
            run = 0
    assert ram_src is not None
    boot = bytes.fromhex('78 d8 a2 0f bd') + ram_src.to_bytes(2, 'little') + bytes.fromhex('9d 00 03 ca 10 f7 4c 00 03')
    assert all(x == 0 for x in prg512[off_504 + 0x19C1 : off_504 + 0x19C1 + len(boot)])
    prg512[off_504 + 0x19C1 : off_504 + 0x19C1 + len(boot)] = boot
    prg512[off_504 + 0x1FFC : off_504 + 0x1FFE] = bytes.fromhex('c1 f9')

    # 512KB CHR: 0..256KB Barba, 256..384KB Waldo, 384..512KB free
    chr512 = bytearray(b'\xFF' * (512 * 1024))
    chr512[0 : 256 * 1024] = b_chr
    chr512[256 * 1024 : 384 * 1024] = w_chr

    # NES 2.0 Mapper 176 (FK23C), 512KB PRG, 512KB CHR, 32KB battery WRAM
    hdr = bytearray(16)
    hdr[0:4] = b'NES\x1a'
    hdr[4] = 32
    hdr[5] = 64
    hdr[6] = 0x02
    hdr[7] = 0xB8
    hdr[10] = 0x90

    play_dir = ROOT / 'play'
    play_dir.mkdir(exist_ok=True)
    out_path = play_dir / 'barba-waldo.nes'
    out_path.write_bytes(bytes(hdr) + bytes(prg512) + bytes(chr512))
    return out_path


if __name__ == '__main__':
    out = pack()
    print(f'Built {out} ({out.stat().st_size:,} bytes)')
