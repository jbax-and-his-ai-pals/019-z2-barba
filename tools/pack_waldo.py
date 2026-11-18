"""Build a single NES 2.0 Mapper 176 ROM containing Barba + Where's Waldo?."""
from __future__ import annotations

import zlib
from pathlib import Path

import build_waldo
from build import ROOT, build


def make_waldo_nmi_hook() -> bytes:
    """Assemble Waldo's $F603 NMI return hook (Start+Select after 60 frames)."""
    # Offsets from $F603:
    # 00: 48          PHA
    # 01: AD FF 7F    LDA $7FFF
    # 04: C9 3C       CMP #$3C
    # 06: B0 05       BCS +5 -> 0D (@check_pad)
    # 08: EE FF 7F    INC $7FFF
    # 0B: D0 08       BNE +8 -> 15 (@normal_nmi)
    # 0D (@check_pad):
    # 0D: A5 06       LDA $06
    # 0F: 29 0C       AND #$0C
    # 11: C9 0C       CMP #$0C
    # 13: F0 04       BEQ +4 -> 19 (@do_return)
    # 15 (@normal_nmi):
    # 15: 68          PLA
    # 16: 4C 37 E2    JMP $E237
    # 19 (@do_return):
    # 19: 4C A4 F9    JMP $F9A4
    return bytes.fromhex(
        '48 ad ff 7f c9 3c b0 05 ee ff 7f d0 08 '
        'a5 06 29 0c c9 0c f0 04 '
        '68 4c 37 e2 '
        '4c a4 f9'
    )


def make_waldo_melt_out() -> bytes:
    """Assemble Waldo's 30-frame bottom-up wavy melt-out at $CB10 (Bank 16)."""
    # Uses ZP $08=frame, $09=wipe, $0A=band, $0B=nt; reads wave table at $CB00.
    base = 0xCB10
    buf = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str, str]] = []

    def emit(*b: int) -> None:
        buf.extend(b)

    def label(name: str) -> None:
        labels[name] = base + len(buf)

    def branch(op: int, target: str) -> None:
        emit(op, 0)
        fixups.append(('rel', len(buf) - 1, target))

    def jmp(target: str) -> None:
        emit(0x4C, 0, 0)
        fixups.append(('abs', len(buf) - 2, target))

    emit(0x78, 0xA9, 0x00, 0x8D, 0x15, 0x40, 0x8D, 0x00, 0xE0, 0x85, 0x08)  # SEI; $4015=0; $E000=0; $08=0
    label('frame_loop')
    emit(0xA9, 30, 0x38, 0xE5, 0x08, 0x85, 0x09)                            # $09 = 30 - frame
    emit(0x2C, 0x02, 0x20)                                                  # BIT $2002
    label('vb_wait')
    emit(0x2C, 0x02, 0x20)
    branch(0x10, 'vb_wait')                                                 # BPL @vb_wait
    emit(0xA5, 0x00, 0x29, 0x7C, 0x8D, 0x00, 0x20)                          # $2000 = $00 & $7C
    emit(0x2C, 0x02, 0x20, 0xA9, 0x00, 0x8D, 0x06, 0x20, 0x8D, 0x06, 0x20)  # BIT $2002; $2006 = 0
    emit(0xA5, 0x03, 0x8D, 0x05, 0x20, 0xA5, 0x04, 0x8D, 0x05, 0x20)        # $2005 = $03, $04
    emit(0xA5, 0x01, 0x09, 0x18, 0x8D, 0x01, 0x20)                          # $2001 = $01 | $18
    emit(0xA2, 21)                                                          # LDX #21
    label('pre_sl')
    emit(0xA0, 21)                                                          # LDY #21
    label('pre_in')
    emit(0x88)                                                              # DEY
    branch(0xD0, 'pre_in')
    emit(0xEA, 0xCA)                                                        # NOP; DEX
    branch(0xD0, 'pre_sl')
    emit(0xA9, 0x00, 0x85, 0x0A)                                            # band = 0
    label('band_loop')
    emit(0xA5, 0x0A, 0xC5, 0x09)                                            # CMP $09
    branch(0x90, 'band_vis')                                                # BCC @band_vis
    emit(0xA9, 0x00, 0x8D, 0x01, 0x20)                                      # $2001 = 0
    emit(0xA9, 0x3F, 0x8D, 0x06, 0x20, 0xA9, 0x00, 0x8D, 0x06, 0x20)        # $2006 = $3F00
    jmp('next_frame')
    label('band_vis')
    emit(0xA5, 0x0A, 0x18, 0x65, 0x08, 0x29, 0x0F, 0xAA, 0xBD, 0x00, 0xCB)  # LDA $CB00,X
    emit(0xA6, 0x08, 0xE0, 8)
    branch(0x90, 'scale_half')
    emit(0xE0, 16)
    branch(0x90, 'scale_done')
    emit(0xE0, 24)
    branch(0x90, 'scale_2x')
    emit(0x0A)                                                              # ASL A
    label('scale_2x')
    emit(0x0A)                                                              # ASL A
    jmp('scale_done')
    label('scale_half')
    emit(0xC9, 0x80, 0x6A)                                                  # CMP #$80; ROR A
    label('scale_done')
    emit(0xAA, 0xA5, 0x00, 0x29, 0x7F, 0x85, 0x0B, 0x8A)                    # TAX; $0B = $00 & $7F; TXA
    branch(0x30, 'neg_shear')                                               # BMI @neg_shear
    emit(0x18, 0x65, 0x03)                                                  # CLC; ADC $03
    branch(0x90, 'write_scroll')                                            # BCC @write_scroll
    emit(0xAA, 0xA5, 0x0B, 0x49, 0x01, 0x85, 0x0B, 0x8A)                    # flip NT bit 0
    jmp('write_scroll')
    label('neg_shear')
    emit(0x18, 0x65, 0x03)                                                  # CLC; ADC $03
    branch(0xB0, 'write_scroll')                                            # BCS @write_scroll
    emit(0xAA, 0xA5, 0x0B, 0x49, 0x01, 0x85, 0x0B, 0x8A)                    # flip NT bit 0
    label('write_scroll')
    emit(0xA6, 0x0B, 0x8E, 0x00, 0x20, 0x8D, 0x05, 0x20, 0xA9, 0x00, 0x8D, 0x05, 0x20)
    emit(0xA0, 158)                                                         # LDY #158
    label('band_wait')
    emit(0x88)                                                              # DEY
    branch(0xD0, 'band_wait')
    emit(0xE6, 0x0A, 0xA5, 0x0A, 0xC9, 30)                                  # INC band; CMP #30
    branch(0xB0, 'next_frame')                                              # BCS @next_frame
    jmp('band_loop')
    label('next_frame')
    emit(0xE6, 0x08, 0xA5, 0x08, 0xC9, 30)                                  # INC frame; CMP #30
    branch(0xB0, 'done')                                                    # BCS @done
    jmp('frame_loop')
    label('done')
    emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20, 0x60)              # $2000=0; $2001=0; RTS

    for kind, pos, target in fixups:
        addr = labels[target]
        if kind == 'rel':
            rel = addr - (base + pos + 1)
            assert -128 <= rel <= 127, f'Branch out of range to {target}: {rel}'
            buf[pos] = rel & 0xFF
        else:
            buf[pos] = addr & 0xFF
            buf[pos + 1] = (addr >> 8) & 0xFF
    return bytes(buf)


def pack() -> Path:
    waldo_path = build_waldo.build()
    waldo = waldo_path.read_bytes()
    assert waldo[:4] == b'NES\x1a' and waldo[4] in (8, 16) and waldo[5] == 0x10
    w_prg_size = waldo[4] * 16384

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

    w_prg = bytearray(waldo[16 : 16 + w_prg_size])
    w_chr = waldo[16 + w_prg_size :]
    e000_off = w_prg_size - 0x2000

    # Patch Waldo's $E031 WRAM enable from $80 -> $A2 (WRAM bank 2 + lock $5FF0-$5FF3)
    assert w_prg[e000_off + 0x0031 : e000_off + 0x0036] == bytes.fromhex('a9 80 8d 01 a0')
    w_prg[e000_off + 0x0032] = 0xA2

    # Skip Waldo's first (copyright/splash) screen ($E0E9: JSR $A045 -> NOP NOP NOP)
    assert w_prg[e000_off + 0x00E9 : e000_off + 0x00EC] == bytes.fromhex('20 45 a0')
    w_prg[e000_off + 0x00E9 : e000_off + 0x00EC] = bytes.fromhex('ea ea ea')

    # Replace Title Screen's JSR $E79C at $A025 (Bank 3) with JSR $C9FC (Bank 16, already mapped at $C000)
    assert w_prg[0x06025:0x06028] == bytes.fromhex('20 9c e7')
    w_prg[0x06025:0x06028] = bytes.fromhex('20 fc c9')

    # Patch Waldo's NMI hook at $F603-$F653 (free 0x00 region) + vector $FFFA
    hook = make_waldo_nmi_hook()
    assert len(hook) <= 81
    assert all(x == 0 for x in w_prg[e000_off + 0x1603 : e000_off + 0x1603 + len(hook)])
    w_prg[e000_off + 0x1603 : e000_off + 0x1603 + len(hook)] = hook
    assert w_prg[e000_off + 0x1FFA : e000_off + 0x1FFC] == bytes.fromhex('37 e2')
    w_prg[e000_off + 0x1FFA : e000_off + 0x1FFC] = bytes.fromhex('03 f6')

    # Hook end of Moon Ending ($A1B3 in Bank 0: JMP $E4EC -> JMP $F9A4) so it waves out to Barba
    assert w_prg[0x01B3:0x01B6] == bytes.fromhex('4c ec e4')
    w_prg[0x01B3:0x01B6] = bytes.fromhex('4c a4 f9')

    # Patch Waldo's $F9A4 return stage: JSR $CB10 (WaldoMeltOut), map bank 16 @ $8000, JMP $8C00
    stage = bytes.fromhex(
        '20 10 cb '
        'a9 06 8d 00 80 a9 10 8d 01 80 4c 00 8c'
    )
    assert len(stage) <= 29
    assert all(x == 0 for x in w_prg[e000_off + 0x19A4 : e000_off + 0x19A4 + len(stage)])
    w_prg[e000_off + 0x19A4 : e000_off + 0x19A4 + len(stage)] = stage

    # Build 512KB PRG:
    #   0..128KB   : Barba
    #   240..256KB : Barba fixed bank ($C000-$FFFF)
    #   256..512KB : Where's Barba? (banks 0..13, bank 16 DPCM+roar+wipe+tramp, banks 30..31 fixed)
    prg512 = bytearray(b'\xFF' * (512 * 1024))
    prg512[0 : 128 * 1024] = b_prg
    prg512[240 * 1024 : 256 * 1024] = b_prg[112 * 1024 : 128 * 1024]
    if w_prg_size == 128 * 1024:
        prg512[256 * 1024 : 384 * 1024] = w_prg
        prg512[496 * 1024 : 512 * 1024] = w_prg[112 * 1024 : 128 * 1024]
    else:
        prg512[256 * 1024 : 512 * 1024] = w_prg

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
    # Bank 16 $8C00/$8C10 (offset 0x0C00/0x0C10, after $C000-$C96F DPCM/roar and $CA00-$CB0F TitleWipeIn)
    bank16_loader = bytes([0xA2, len(tramp) - 1]) + bytes.fromhex('bd 10 8c 9d 00 03 ca 10 f7 4c 00 03')
    assert all(x == 0xFF for x in prg512[384 * 1024 + 0x0C00 : 384 * 1024 + 0x0C10 + len(tramp)])
    prg512[384 * 1024 + 0x0C00 : 384 * 1024 + 0x0C00 + len(bank16_loader)] = bank16_loader
    prg512[384 * 1024 + 0x0C10 : 384 * 1024 + 0x0C10 + len(tramp)] = tramp

    # TitleWipeIn in Bank 16 at $CA00 (offset 0x0A00) + wave table at $CB00 (offset 0x0B00)
    title_wipe = bytes.fromhex(
        'a0 11 b1 1a 99 32 00 88 10 f8 a9 20 85 05 a5 05 d0 fc '                 # $CA00: setup_nt ($1A/$1B already set)
        '78 a9 08 8d 00 20 a9 1d 85 08 '                                        # $CA12: SEI; frame = 29
        'a9 1e 38 e5 08 85 09 '                                                 # $CA1C (@frame_loop): reveal_band = 30 - frame
        '2c 02 20 2c 02 20 10 fb '                                              # $CA23: wait VBlank
        'a9 40 8d 00 80 a5 38 8d 01 80 '                                        # $CA2B: R0 = $38
        'a9 41 8d 00 80 a5 3e 8d 01 80 '                                        # $CA35: R1 = $3E
        'a9 08 8d 00 20 2c 02 20 a9 00 8d 06 20 8d 06 20 8d 05 20 8d 05 20 a9 1e 8d 01 20 '  # $CA3F: reset v/scroll; render on
        'a2 15 a0 15 88 d0 fd ea ca d0 f7 '                                     # $CA5A: wait 21 scanlines
        'a9 00 85 0a '                                                          # $CA65: band = 0
        'a5 0a c9 10 d0 14 '                                                    # $CA69 (@band_loop): if band == 16
        'a9 40 8d 00 80 a5 39 8d 01 80 '                                        # $CA6F: R0 = $39
        'a9 41 8d 00 80 a5 3f 8d 01 80 '                                        # $CA79: R1 = $3F
        'a5 0a c5 09 90 12 '                                                    # $CA83: if band >= reveal_band
        'a9 00 8d 01 20 a9 3f 8d 06 20 a9 01 8d 06 20 '                         # $CA89: $2001=0; $2006=$3F01 (black)
        '4c c8 ca '                                                             # $CA98: JMP $CAC8 (@next_frame)
        '18 65 08 29 0f aa bd 00 cb '                                           # $CA9B: LDA $CB00,X (wave)
        'a6 08 e0 08 90 06 0a e0 10 90 01 0a '                                  # $CAA4: scale wave by frame
        '8d 05 20 a9 00 8d 05 20 '                                              # $CAB0: $2005 = shear, $2005 = 0
        'a0 a0 88 d0 fd '                                                       # $CAB8: wait 8 scanlines
        'e6 0a a5 0a c9 1e b0 03 4c 69 ca '                                     # $CABD: band++; if < 30 JMP $CA69
        'c6 08 10 03 4c d2 ca 4c 1c ca '                                        # $CAC8 (@next_frame): frame--; if >= 0 JMP $CA1C
        '2c 02 20 2c 02 20 10 fb '                                              # $CAD2 (@done): wait VBlank
        'a9 00 8d 06 20 8d 06 20 8d 05 20 8d 05 20 '                            # $CADA: reset $2006/$2005
        'a9 1e 85 01 a9 ff 85 30 a9 88 85 00 8d 00 20 58 60'                    # $CAE8: enable NMI/IRQ; CLI; RTS
    )
    wave_tbl = bytes.fromhex('00 02 04 05 06 05 04 02 00 fe fc fb fa fb fc fe')
    assert all(x == 0xFF for x in prg512[384 * 1024 + 0x09FC : 384 * 1024 + 0x0A00])
    prg512[384 * 1024 + 0x09FC : 384 * 1024 + 0x0A00] = bytes.fromhex('86 1a 85 1b')
    prg512[384 * 1024 + 0x0A00 : 384 * 1024 + 0x0A00 + len(title_wipe)] = title_wipe
    prg512[384 * 1024 + 0x0B00 : 384 * 1024 + 0x0B00 + len(wave_tbl)] = wave_tbl
    melt_out = make_waldo_melt_out()
    assert len(melt_out) <= 0x0C00 - 0x0B10
    assert all(x == 0xFF for x in prg512[384 * 1024 + 0x0B10 : 384 * 1024 + 0x0B10 + len(melt_out)])
    prg512[384 * 1024 + 0x0B10 : 384 * 1024 + 0x0B10 + len(melt_out)] = melt_out

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
