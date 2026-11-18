"""Build Barba Edition from a verified local ROM, preserving all unpatched bytes."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from assets import (ASH_TILES, CASTLE_FIRE_BANK, CASTLE_FIRE_TILE_SHA256,
                    CASTLE_SHOUT_BANK, CASTLE_SHOUT_PAIR_SHA256,
                    SHOUT_PAIR_SHA256, TOWN_SPRITE_PAIRS,
                    TITLE_CHR_BANK, TITLE_TILE_SHA256,
                    TOWN_FIRE_BANK, TOWN_FIRE_TILE_SHA256,
                    TEXT_GLYPH_BANK, TEXT_GLYPH_SHA256, TEXT_GLYPHS,
                    BREATH_ICON_BANKS, BREATH_ICON_SHA256, BREATH_ICON_TILE,
                    compile_assets, compile_breath_icon, compile_castle_fire, compile_ending_fire,
                    compile_castle_shout_glyphs, compile_file_select_doll,
                    compile_shout_glyphs, compile_text_glyphs, compile_title_logo,
                    compile_town_fire, validate_layout)
from bps import apply, encode
from boss_art import compile_lava_link
from game_over_art import (GAME_OVER_CHR_BANK, GAME_OVER_MAP_START,
                           compile_game_over_link)
from nes import CHR_OFFSET, SOURCE_SHA256, encode_tile, load_source, prg_offset
import roar_sample
import game_over_audio

ROOT = Path(__file__).resolve().parents[1]


class Overlay:
    def __init__(self, source: bytes):
        self.source = source
        self.target = bytearray(source)
        self.ranges: list[dict] = []

    def put(self, offset: int, data: bytes, expected: bytes, name: str) -> None:
        if len(data) != len(expected) or not 0 <= offset <= len(self.source)-len(data):
            raise ValueError(f'Invalid patch length/location: {name}')
        if self.source[offset:offset+len(data)] != expected:
            raise ValueError(f'Original bytes differ at {offset:05X}: {name}')
        for previous in self.ranges:
            if offset < previous['offset']+previous['length'] and previous['offset'] < offset+len(data):
                raise ValueError(f'Overlapping patches: {name} and {previous["name"]}')
        self.target[offset:offset+len(data)] = data
        self.ranges.append({'name': name, 'offset': offset, 'length': len(data),
                            'sha256': hashlib.sha256(data).hexdigest()})

    def prg(self, bank: int, address: int, data: bytes, expected: bytes, name: str) -> None:
        self.put(prg_offset(bank, address), data, expected, name)


def assemble(output: Path, sampled_roar: bool = False, waldo_portal: bool = False) -> dict[str, int]:
    def find(name: str) -> str:
        local = ROOT / f'.tools/cc65/bin/{name}.exe'
        result = str(local) if local.exists() else shutil.which(name)
        if not result:
            raise ValueError(f'{name} is missing. Install cc65; see docs/BUILD.md.')
        return result
    defines = ['-D', 'SAMPLED_ROAR=1'] if sampled_roar else []
    if waldo_portal:
        defines += ['-D', 'WALDO_PORTAL=1']
    subprocess.run([find('ca65'), str(ROOT/'src/barba.asm'), '-I', str(ROOT/'src'), '-I', str(output.resolve()),
                    *defines, '-g', '-o', 'barba.o'], cwd=output, check=True)
    subprocess.run([find('ld65'), '-C', str(ROOT/'src/barba.cfg'), 'barba.o',
                    '-Ln', 'barba.lbl', '-m', 'barba.map', '--dbgfile', 'barba.dbg'], cwd=output, check=True)
    labels = {}
    for line in (output/'barba.lbl').read_text().splitlines():
        _, address, label = line.split()
        if not label.startswith('.@'):
            labels[label.lstrip('.')] = int(address, 16)
    return labels


def build(source_path: Path, output: Path, title_roar_wav: Path | None = ROOT/'roms/roar.wav',
          waldo_portal: bool = False) -> dict:
    source = load_source(source_path)
    if output.resolve() == source_path.parent.resolve():
        raise ValueError('Output must not be the source ROM directory')
    output.mkdir(parents=True, exist_ok=True)
    roar_info = None
    if title_roar_wav:
        sample, roar_info = roar_sample.convert(title_roar_wav, output)
        (output/'sample-roar-params.inc').write_text(
            f'ROAR_RATE = {roar_info["rate_index"]}\nROAR_LENGTH = {(len(sample)-1)//16}\n'
            f'HURT_LENGTH = {roar_info["hurt_length"]}\n')
    # Asset compilation emits the tile-index include consumed by ca65. Complete
    # it before assembling so the ROM and renderer always share one layout.
    mapping, graphics, ow, _ = compile_assets(ROOT, source_path)
    labels = assemble(output, bool(title_roar_wav), waldo_portal)
    overlay = Overlay(source)
    # FarCall0 identifies the ACTUAL mapped bank without touching the native
    # mapper path (and without mistaking the area-bank variable for a shadow).
    fingerprints = bytes.fromhex('f0 7d 60 2e 91 2f 00 c9')
    for bank, expected in enumerate(fingerprints):
        offset = prg_offset(bank, 0x8506 if bank < 7 else 0xC506)
        if source[offset] != expected:
            raise ValueError(f'FarCall0 bank fingerprint changed: {bank}')
    for filename, bank, address in [('code', 0, 0xAA40), ('bank0-ow', 0, 0xA89E), ('bank0-tail', 0, 0xBFE0),('lava', 7, 0xD39A), ('terrain', 7, 0xFF4C), ('town', 3, 0xB803), ('gateway', 7, 0xFEAA), ('bank6', 6, 0xAC09), ('bank5', 5, 0xBDE0), ('bank1', 1, 0x9EB9), ('bank3-sign', 3, 0x9D0A)]:
        data = (output/f'barba-{filename}.bin').read_bytes()
        overlay.prg(bank, address, data, b'\xFF'*len(data), f'New {filename} routines')
    # Dead vanilla bank-0 code reused for METEOR. Guard the full original ranges:
    # the Fire spell body ($97F1-$9814; pointer $8E50 -> BarbaSpellDeferred) and
    # Check_for_Fire_Spell ($9847-$9877; sole caller $D50D -> BarbaUpdate hook).
    for filename, address, expected in [
            ('fire-spell', 0x97F1, 'a2 01 ad 77 07 c9 04 b0 02 a2 00 ac 00 04 88 cc 95 04 d0 0e ad 0a 05 c9 05 d0 07 b5 8d f0 0b ca 10 f9 18 60'),
            ('fire-check', 0x9847, 'ad 6f 07 29 10 d0 2a ad 84 07 0a 0a 0a 0a 0a 38 e9 01 cd 74 07 d0 1a 20 fa 97 90 15 a5 29 ac 95 04 79 17 98 95 36 a9 d2 8d ca 05 a5 ef 09 08 85 ef'),
            # Raft-avatar tail after the 'Sea crossing avatar' RTS at $81C0 (only self-referenced).
            ('raft-tail', 0x81C1, '45 8d 01 02 a9 47 8d 05 02 ac a9 07 b9 ae 81 8d 02 02 8d 06 02 c0 01 d0 0a a9 47 8d 01 02 a9 45 8d 05 02 60')]:
        data = (output/f'barba-{filename}.bin').read_bytes()
        original = bytes.fromhex(expected)
        overlay.prg(0, address, data + original[len(data):], original, f'METEOR in dead vanilla {filename}')
    def hook(bank: int, address: int, label: str, opcode: int, expected: str, pad: int = 0):
        dest = labels[label]
        data = bytes([opcode, dest & 255, dest >> 8]) + b'\xEA'*pad
        overlay.prg(bank, address, data, bytes.fromhex(expected), label+' hook')
    hook(0, 0x877C, 'BarbaOverworld', 0x20, 'a2 0e a0 00', 1)
    hook(0, 0x8518, 'BarbaOverworldA', 0x4C, 'ad 89 07')
    hook(0, 0x922A, 'ThunderHit', 0x20, '20 26 e7')
    hook(7, 0xD52D, 'BarbaDisplay', 0x20, '20 f0 eb')
    death_draw = labels['BarbaDeathDisplay'].to_bytes(2, 'little')
    overlay.prg(7, 0xC9EE, bytes.fromhex('a9 03 20 cc ff 20') + death_draw + b'\xea\xea',
                bytes.fromhex('20 c5 ff a9 0a 85 80 20 f0 eb'), 'Fatal-hit transition renderer')
    overlay.prg(0, 0x8FC9, b'\xa9\x09', b'\xa9\x0a', 'Fall-in-hole downstab pose ($09)')
    hook(0, 0x8FE3, 'BarbaFallDraw', 0x20, '20 02 ec')
    hook(0, 0x8FEE, 'BarbaFallDraw', 0x20, '20 02 ec')
    hook(7, 0xE0A4, 'LavaSurface', 0x4C, 'a9 01 85')
    hook(7, 0xD4FE, 'BarbaPreEnemy', 0x20, '20 25 99')
    hook(7, 0xD535, 'BarbaBlocks', 0x20, '20 dd e1')
    # Five native block-animation records can fill during breath/thrust chains.
    # Vanilla reuses record 0 while its last 2x2 erase is still pending, leaving
    # a drawn fragment over an already-empty collision tile. Allocate BEFORE
    # changing collision; on exhaustion leave the block hittable for a retry.
    # E292 returns Y=$02 and N clear on success ($0F is $60..$63); N set on
    # failure (DEX reached $FF). Both callers must honor that failure.
    overlay.prg(7, 0xE29C, bytes.fromhex('60 ea'), bytes.fromhex('a2 00'),
                'Full block animation pool returns failure instead of overwriting slot 0')
    overlay.prg(7, 0xE23A, bytes.fromhex('20 92 e2 30 f3 a9 42 91 0e a9 01 9d 1a 04'),
                bytes.fromhex('a9 42 a4 02 91 0e 20 92 e2 a9 01 9d 1a 04'),
                'Breath and thrust blocks reserve animation before clearing collision')
    overlay.prg(7, 0xE0FC, bytes.fromhex('20 92 e2 30 2a a9 8f 91 0e a9 81 9d 1a 04'),
                bytes.fromhex('a9 8f a4 02 91 0e 20 92 e2 a9 81 9d 1a 04'),
                'Crumbling floors honor full block animation pool')
    hook(7, 0xD50D, 'BarbaUpdate', 0x20, '20 47 98')
    # The native player-contact gate sets carry when slot parity matches frame
    # parity. An XOR tests the same condition without saving flags on the stack.
    # Its callee at $E469 sets up its own registers and carry. The space after
    # the gate holds a tail call that skips $D56D for empty projectile slots.
    # Active slots, including negative disappearing blades, still run $D56D.
    overlay.prg(7, 0xE3B9, bytes.fromhex(
        '8a 45 12 4a 90 f9 b0 08'    # TXA / EOR $12 / LSR / BCC $E3B8 / BCS $E3C9
        ' b5 87 f0 03 4c 6d d5 60'  # LDA $87,X / BEQ RTS / JMP $D56D / RTS
        ), bytes.fromhex('a5 12 4a 8a 29 01 d0 06 08 68 49 01 48 28 b0 ef'),
        'Enemy projectile contact parity and empty-slot check')
    overlay.prg(7, 0xD5D1, bytes.fromhex('20 c1 e3'), bytes.fromhex('20 6d d5'),
                'Check projectile type before calculating the offscreen mask')
    # Empty enemy slots ($B6,X == 0) never read the offscreen-column mask ($C9/$CD);
    # branch directly to $D603 before $F27D, and direct-jump active/dying/score
    # states ($B6,X == 1,2,3) after $F27D (which preserves X). Frees $D5F6-$D5F8.
    overlay.prg(7, 0xD5DA, bytes.fromhex(
        'b5 b6 f0 25'              # LDA $B6,X / BEQ $D603
        ' a0 01 e8 20 7d f2 ca'    # LDY #$01 / INX / JSR $F27D / DEX
        ' b5 b6 c9 02 90 05 f0 06' # LDA $B6,X / CMP #$02 / BCC $D5F0 / BEQ $D5F3
        ' 4c 6c dd'                # JMP $DD6C ($B6,X == 3)
        ' 4c ca d6'                # JMP $D6CA ($B6,X == 1)
        ' 4c ae dc'                # JMP $DCAE ($B6,X == 2)
        ' ea ea ea'                # 3 spare bytes ($D5F6-$D5F8)
    ), bytes.fromhex(
        'a0 01 e8 20 7d f2 a6 10 b5 b6 0a a8 b9 f1 d5 85 0e b9 f2 d5 4c d6 d6'
        ' 03 d6 ca d6 ae dc 6c dd'
    ), 'Skip offscreen mask for empty enemy slots and direct-dispatch active enemies')
    hook(7, 0xE48B, 'EnemyFireGateway', 0x4C, 'b5 b6 c9 01', 1)
    hook(7, 0xE617, 'ShieldFireGateway', 0x4C, 'a5 c8 0a')
    hook(5, 0x9A7F, 'DarkBarbaDraw', 0x20, '20 02 ec')
    overlay.prg(5, 0x9887, b'\xa9\x03', b'\xa9\x06', 'Dark Barba full-height pre-fight landing pose')
    overlay.prg(5, 0x99D0, b'\xa9\x0c', b'\xa9\x06', 'Dark Barba full-height ascending jump pose')
    overlay.prg(7, 0xDD18, b'\x20' + labels['FarCall0'].to_bytes(2, 'little')
                + labels['BarbaBossShadow'].to_bytes(2, 'little') + b'\xea',
                bytes.fromhex('8e 53 07 20 02 ec'), 'Boss-defeat 48px Barba shadow')
    hook(5, 0x9BB1, 'DarkBarbaTriforcePose', 0x4C, 'a9 0b 85 80 e6 af 4c 11 ef', 6)
    if title_roar_wav:
        hook(5, 0x9BAC, 'DarkBarbaVictory', 0x4C, 'ac 12 05')
    lag_dest = 0xFFEA
    overlay.prg(7, 0xC065, bytes.fromhex('ad 06 85 48') + bytes([0x4C, lag_dest & 255, lag_dest >> 8]),
                bytes.fromhex('a9 06 20 cc ff 20 00'), 'Lag-frame NMI bank preservation')
    # MMC3 (Mapper 4) port: preserve $C000-$FFFF fixed (PRG mode 0), map $8000/$A000
    # in 8KB pairs, map CHR in 1KB/2KB units (BG at $0000 via R0/R1, Sprites at $1000
    # via R2-R5 so MMC3 A12 clocks on every scanline), and keep $8000 bank-select
    # NMI-safe via $64D5 shadow + LagNmiBank6 save/restore.
    overlay.put(5, b'\x20', b'\x10', 'Expand CHR-ROM to 256 KB (32 x 8KB banks)')
    overlay.put(6, b'\x42', b'\x12', 'iNES mapper 4 (MMC3)')
    lag_in_bank6 = labels['LagNmiInBank6']
    overlay.prg(7, 0xFF81, bytes.fromhex(
        'a9 80 8d 01 a0 8d 00 e0 a9 0f 20 9d ff 20 b1 ff a9 07 20 cc ff 4c 00 c0'
        '68 aa 68 40'
        '8d 00 a0 a9 00 60'
        'ca 30 0a e0 01 d0 02 09 07 e9 01 10 09 60'
        '29 fe 0a 0a 09 03 a2 05 8e d5 64 8e 00 80 8d 01 80 4c a3 ff'
    ), bytes.fromhex(
        '8e 00 80 8e 00 a0 8e 00 c0 8e 00 e0 a9 0f 20 9d ff 20 b1 ff a9 07 20 cc ff 4c 00 c0'
        '8d 00 80 4a 8d 00 80 4a 8d 00 80 4a 8d 00 80 4a 8d 00 80 60'
        '8d 00 a0 4a 8d 00 a0 4a 8d 00 a0 4a 8d 00 a0 4a 8d 00 a0 60'
    ), 'MMC3 reset, IRQ exit, mirroring (ConfigureMMC1), and swapped CHR (SwapCHR)')
    overlay.prg(7, 0xFFCC, bytes.fromhex(
        '0a 48 a9 06 8d d5 64 8d 00 80 68 8d 01 80 09 01 48 a9 07 8d d5 64 8d 00 80 68 8d 01 80 60'
        '68 a8 ad d5 64 48 98 48 a9 06 20 cc ff 4c') + lag_in_bank6.to_bytes(2, 'little'),
        bytes.fromhex(
        '8d 00 e0 4a 8d 00 e0 4a 8d 00 e0 4a 8d 00 e0 4a 8d 00 e0 60'
        '4c 45 47 45 4e 44 20 4f 46 20 5a 45 4c 44 41 32'
        '98 f2 dd db 33 04 01 0f 01 00'
    ), 'MMC3 PRG swap (SwapPRG) and LagNmiBank6 trampoline')
    overlay.prg(7, 0xFFFE, bytes.fromhex('ae d4'), bytes.fromhex('f0 ff'), 'MMC3 scanline IRQ vector ($D4AE)')
    # Retarget the 5 live bank-0/bank-5 calls to the bank-local $BF9D/$BFB1 MMC1
    # copies so they invoke the fixed-bank MMC3 routines at $FF9D/$FFB1 instead.
    for bank, addr, label in (
        (0, 0x814D, 'Bank 0 init ConfigureMMC1 -> $FF9D'),
        (0, 0x8152, 'Bank 0 init SwapCHR -> $FFB1'),
        (0, 0xA86D, 'Bank 0 OW SwapCHR -> $FFB1'),
        (5, 0xA716, 'Bank 5 title ConfigureMMC1 -> $FF9D'),
        (5, 0xA72A, 'Bank 5 title SwapCHR -> $FFB1'),
    ):
        overlay.prg(bank, addr, b'\xff', b'\xbf', label)
    # BG at $0000 (bit 4 = 0), 8x16 sprites at $1000 via $6500 shadow OAM; free OAM slot 0.
    overlay.prg(5, 0xA6D2, b'\xa0', b'\xb0', 'Reset PPU_CTRL BG=$0000')
    overlay.prg(7, 0xC0BE, b'\x65', b'\x02', 'NMI OAM DMA from $6500 shadow')
    overlay.prg(5, 0xA63D, b'\x65', b'\x02', 'Title NMI OAM DMA from $6500 shadow')
    overlay.prg(7, 0xD251, b'\x00', b'\x04', 'Free OAM slot 0 (clear all 64 sprites)')
    title_hook5 = labels['TitleEndHook5']
    overlay.prg(5, 0xA693, b'\x20' + title_hook5.to_bytes(2, 'little'),
                bytes.fromhex('ad 02 20'), 'Title NMI end -> OAM shadow + IRQ setup')
    # NMI prologue: clean without LateSplit trampoline.
    overlay.prg(7, 0xC091, bytes.fromhex('a0 00 a5 fe 29 e0 ac 26 07 d0 07 a5 fe 09 18 0d 68 07 ea ea ea ea ea'),
                bytes.fromhex('ad 27 07 f0 00 a0 00 a5 fe 29 e0 ac 26 07 d0 07 a5 fe 09 18 0d 68 07'),
                'NMI prologue compaction (no LateSplit)')
    # Replace $0725 macro clear + sound call ($C108-$C131) with Bank 6 NmiVblankSetup6,
    # freeing $C111-$C131 (33 bytes) for IrqHandler2.
    swap_b6 = labels['SwapToBank6']
    nmi_setup6 = labels['NmiVblankSetup6']
    copy_oam6 = labels['CopyOamShadow6']
    overlay.prg(7, 0xC108,
                b'\x20' + swap_b6.to_bytes(2, 'little')
                + b'\x20' + nmi_setup6.to_bytes(2, 'little')
                + bytes.fromhex('4c 32 c1')
                + bytes.fromhex('8d 05 20 bd e4 64 8d 01 20 e8 ec d7 64 b0 0f 8e d6 64 bd d8 64 8d 00 c0 8d 01 c0 8d 01 e0 4c 99 ff'),
                bytes.fromhex(
                    'ae 25 07 f0 0f c8 e0 01 f0 07 c8 a9 00 e0 02 d0 13 ce 25 07 be 5d c0 a9 00 9d 01 03 a9 ff 9d 02 03 ad 25 07 8d 25 07 20 c1 c1'),
                'NMI VBlank Bank 6 setup + CLI + IrqHandler2 ($C112)')
    # The three early-outs that branch to the NMI tail, which moves $C1A8 -> $C19D.
    overlay.prg(7, 0xC156, bytes([0x46]), bytes([0x51]), 'NMI tail branch (dialogue)')
    overlay.prg(7, 0xC163, bytes([0x39]), bytes([0x44]), 'NMI tail branch (talking)')
    overlay.prg(7, 0xC168, bytes([0x34]), bytes([0x3F]), 'NMI tail branch (routine)')
    # RNG compaction + OAM shadow copy tail ($C19D). RTI stays at $C1B5.
    overlay.prg(7, 0xC182, bytes.fromhex(
        'e6 12 a2 00 a0 09 ad 1a 05 4d 1b 05 4a 4a 7e 1a 05 e8 88 d0 f9 20 50 d2 20 ca c2')
        + b'\x20' + swap_b6.to_bytes(2, 'little')
        + b'\x20' + copy_oam6.to_bytes(2, 'little')
        + bytes.fromhex('20 c5 ff ea ea ea ea ea a5 ff 09 80 85 ff 8d 00 20 68 40'),
        bytes.fromhex('ee 12 00 a2 00 a0 09 ad 1a 05 29 02 85 00 ad 1b 05 29 02 45 00 18 f0 01 38 7e 1a 05'
                      'e8 88 d0 f9 20 50 d2 20 ca c2 ad 02 20 a5 ff 09 80 85 ff 8d 00 20 68 40'),
        'NMI RNG compaction + OAM shadow copy tail')
    # Replace Sprite-0 busy-wait ($D4AB-$D4CD) with IrqHandler ($D4AE-$D4CD).
    overlay.prg(7, 0xD47A, bytes.fromhex('f0 52'), bytes.fromhex('f0 2f'), 'Retarget $D47A BEQ to $D4CE')
    overlay.prg(7, 0xD485, bytes.fromhex('f0 47'), bytes.fromhex('f0 24'), 'Retarget $D485 BEQ to $D4CE')
    overlay.prg(7, 0xD4AB, bytes.fromhex(
        '4c ce d4'
        '48 8a 48 8d 00 e0 ae d6 64 a5 ff 29 fc 1d e0 64 85 ff 8d 00 20 2c 02 20 bd dc 64 4c 11 c1 ea ea'),
        bytes.fromhex(
            'ad 4c 07 c9 02 b0 1c 2c 02 20 50 fb a5 ff 0d 46 07 85 ff a6 fd a0 10 88 d0 fd 8d 00 20 8e 05 20 8c 05 20'),
        'Replace Sprite-0 wait with MMC3 IrqHandler ($D4AE)')
    # Eliminate the remaining side-view Sprite-0 busy-waits in banks 0 and 3 (menus/towns/castle);
    # the scanline-31 IRQ already performs the HUD split cleanly.
    overlay.prg(0, 0x9D54, bytes.fromhex('4c 75 9d'), bytes.fromhex('a0 50 88'), 'Skip Level-Up/Pause Sprite-0 wait ($9D54)')
    overlay.prg(0, 0x9DB0, bytes.fromhex('4c cc 9d'), bytes.fromhex('2c 02 20'), 'Skip Pause Sprite-0 wait ($9DB0)')
    overlay.prg(0, 0xA7B1, bytes.fromhex('4c cd a7'), bytes.fromhex('2c 02 20'), 'Skip Castle Sprite-0 wait ($A7B1)')
    overlay.prg(3, 0xB08F, bytes.fromhex('4c ab b0'), bytes.fromhex('2c 02 20'), 'Skip Town Sprite-0 wait ($B08F)')
    # Offscreen-column mask ($F27D, called for every drawn object): the native
    # 4-pass loop costs ~300 cycles/call (a third of the enemy pass in busy rooms).
    # Same $C8,y/$CC,y/A/Y/flags from one 16-bit subtraction (~60 cycles): with
    # d = objX - scroll, page 0 marks the right-hand columns past 256, page $FF
    # the complement, any other page all four. $01/$0E/$0F are no longer written
    # (watched: 311k calls over all checkpoints, never read before rewritten).
    # BIT $F27C (table byte $40) sets V on page $FF. $F2D2 (RTS) stays as spare.
    overlay.prg(7, 0xF27D, bytes.fromhex(
        '84 00 b5 4d 38 ed 2c 07 a8 b5 3b ed 2a 07 b8 f0 0b c9 ff f0 04 a9 0f d0 15'
        '2c 7c f2 c0 e8 a9 00 90 08 98 4a 4a 4a a8 b9 b2 f2 50 02 49 0f'
        'a4 00 99 c8 00 b5 29 18 69 10 b5 19 69 00 c9 01 f0 08 a9 f0 19 c8 00 99 c8 00'
        'b5 4d 38 ed 2c 07 99 cc 00 60 01 03 07'),
        bytes.fromhex(
        '84 00 a9 00 99 c8 00 a0 03 b5 4d 18 79 74 f2 85 0e b5 3b 69 00 85 0f a5 0e cd 2c 07'
        'a5 0f ed 2a 07 f0 0f 84 01 b9 70 f2 a4 00 19 c8 00 99 c8 00 a4 01 88 10 d4 a4 00 b5 29'
        '18 69 10 b5 19 69 00 c9 01 f0 08 a9 f0 19 c8 00 99 c8 00 b5 4d 38 ed 2c 07 99 cc 00'),
        'Fast offscreen-column mask ($F27D)')
    overlay.prg(7, 0xE6E2, bytes.fromhex('4c f3 e6 ea'), bytes.fromhex('29 20 f0 0d'),
                'Allow fireballs against sword-only enemies')
    # East Hyrule rock-tossing Lizalfos ($1D) skip the normal shot check.
    # Run it during the exposed throw cycle (AI phase 3), then resume
    # display and the AI dispatch only if the enemy is still alive.
    overlay.prg(2, 0x9F85, bytes.fromhex(
        'b5 af 29 03 c9 03 d0 09'  # LDA $AF,X / AND #3 / CMP #3 / BNE draw
        '20 8b e4 b5 b6 c9 01 d0 0a'  # JSR $E48B / LDA $B6,X / CMP #1 / BNE done
        '20 11 ef b5 af 29 03 4c 83 97 60'  # draw: displaced code, JMP $9783; done: RTS
    ), b'\xff' * 28, 'Rock-tossing Lizalfos fireball check')
    overlay.prg(2, 0x977C, bytes.fromhex('4c 85 9f ea ea ea ea'),
                bytes.fromhex('20 11 ef b5 af 29 03'), 'Rock-tossing Lizalfos fireball hook')
    hook(3, 0xB5F8, 'TownDialog', 0x4C, '0a a8 ad 07 07', 2)
    hook(3, 0xB74D, 'TownLetterDelay', 0x20, 'a9 05 8d 66 05', 2)
    hook(3, 0xB65E, 'TownLineDelay', 0x20, '8c 66 05')
    emerged = labels['TownDoorEmerged']
    coords = labels['TownDoorCoords']
    overlay.prg(
        3,
        0x98AB,
        bytes([0xB5, 0xAF, 0xC9, 0x81, 0xD0, 0x03,
               0x4C, emerged & 255, emerged >> 8,
               0x4C, coords & 255, coords >> 8]) + b'\xEA' * 4,
        bytes.fromhex('b4 60 b5 4e 18 79 80 97 9d 99 05 b5 3c 9d 9f 05'),
        'Town door coordinates hook',
    )
    hook(3, 0x9A2C, 'TownNativeTalk', 0x20, 'ad f5 00 29 40', 2)
    # Burned signs (src/sign.inc): sign readers $21/$22 update pointers ($9ABD) -> SignUpdate.
    # SignUpdate only adds the burn mark and tail-calls $9ABD, so $21 quest triggers
    # (Mirror/Fountain) keep their native behaviour.
    dest = labels['SignUpdate']
    for address, kind in ((0x94CF, '$21'), (0x94D1, '$22')):
        overlay.prg(3, address, dest.to_bytes(2, 'little'), bytes.fromhex('bd 9a'), f'Sign reader {kind} update {address:04X}')
    # Message-box padding (max 10 chars/line): end two 11-char vanilla lines one byte
    # early by turning the final period into the terminator. The following $FF is left unread.
    for address, line in ((0xA423, 'A STRANGER'), (0xA612, 'THE CASTLE')):
        overlay.prg(3, address, b'\xff', b'\xcf', f'Vanilla dialogue width trim: {line}')
    # The Mido and Darunia knights teach Barba's aerial techniques in place.
    town_glyphs = {chr(ord('A') + i): 0xDA + i for i in range(26)}
    town_glyphs.update({' ': 0xF4, '.': 0xCF, '\n': 0xFD})
    for address, name, original, lesson in (
        (0xA99E, 'Mido downstab', 'WHEN YOU\nJUMP PRESS\nDOWNWARD\nTO STAB.',
         'JUMP. HOLD\nDOWN FOR A\nWYRM DIVE.'),
        (0xADBF, 'Darunia upstab', 'WHEN YOU\nJUMP PRESS\nUP TO STAB.',
         'JUMP. HOLD\nUP TO RAM\nHEADFIRST.'),
    ):
        expected = bytes(town_glyphs[ch] for ch in original) + b'\xff'
        replacement = bytes(town_glyphs[ch] for ch in lesson) + b'\xff'
        lines = lesson.splitlines()
        if len(replacement) > len(expected) or len(lines) > 3 or any(len(line) > 10 for line in lines):
            raise ValueError(f'{name} lesson exceeds its dialogue space')
        overlay.prg(3, address, replacement.ljust(len(expected), b'\xff'), expected, name + ' lesson')
    # East message 36 is five mid-height dots (tile $32), which is now shout glyph D's
    # upper half. Draw them with the period glyph instead.
    overlay.prg(3, 0xAE19, b'\xcf' * 5, b'\x32' * 5, 'Vanilla dialogue ellipsis uses periods')
    dest = labels['TownUpdate']
    overlay.prg(3, 0x949F, dest.to_bytes(2, 'little'), bytes.fromhex('78 98'),
                'Indoor NPC update 949F')
    overlay.prg(3, 0x94AB, dest.to_bytes(2, 'little'), bytes.fromhex('a9 97'),
                'Wise Man NPC update 94AB')
    for address in (0x94A1, 0x94A7, 0x94A9, 0x94AD, 0x94AF, 0x94B1):
        overlay.prg(3, address, dest.to_bytes(2, 'little'), bytes.fromhex('93 97'),
                    f'Stationary villager/NPC update {address:04X}')
    for address in (0x94B3, 0x94B5, 0x94B7, 0x94B9, 0x94BB, 0x94BD):
        overlay.prg(3, address, dest.to_bytes(2, 'little'), bytes.fromhex('d4 97'),
                    f'Static outdoor villager update {address:04X}')
    for address in (0x94BF, 0x94C1, 0x94C3, 0x94C5, 0x94C7, 0x94C9, 0x94CB, 0x94CD):
        overlay.prg(3, address, dest.to_bytes(2, 'little'), bytes.fromhex('78 98'),
                    f'Wandering villager update {address:04X}')
    dest = labels['BarbaInferno']
    overlay.prg(0, 0x8E56, bytes([dest & 255, dest >> 8]), bytes.fromhex('e6 91'), 'Inferno spell pointer')
    dest = labels['BarbaSpellDeferred']
    overlay.prg(0, 0x8E50, bytes([dest & 255, dest >> 8]), bytes.fromhex('f1 97'), 'Defer Fire spawning until after HUD split')

    # Keep the raft route and item checks. Return after the new two-sprite avatar.
    overlay.prg(0, 0x81C0, b'\x60', b'\xA9', 'Sea crossing avatar')
    overlay.prg(0, 0x814F, b'\x1E', b'\x10', 'Dedicated overworld CHR pair')
    # Vanilla Link's art sits left in its 16px box, so the game draws him at X=$84.
    # Barba's overworld art is centered: draw at $80 so he sits on the tile.
    overlay.prg(0, 0x8727, b'\x80', b'\x84', 'Center overworld dragon on tile')
    overlay.prg(0, 0x960B, bytes.fromhex('a9 40 85 ed'), bytes.fromhex('a9 20 85 ed'), 'Flame attack sound')
    overlay.prg(0, 0x9819, bytes.fromhex('30 d0'), bytes.fromhex('20 e0'), 'Faster ranged flame')

    offset = prg_offset(7, 0xEB25)
    overlay.put(offset, mapping, source[offset:offset+len(mapping)], 'Dragon animation metasprites')
    for bank in range(0, 26, 2):
        for tile, pair in graphics.items():
            # Ash is town-only (sprite bank 6). Tiles $64/$66 are shared sprites in
            # the other banks (palaces, caves), so leave those untouched.
            if tile in ASH_TILES and bank != 6:
                continue
            offset = CHR_OFFSET + bank*4096 + tile*16
            overlay.put(offset, pair, source[offset:offset+32], f'CHR {bank:02X}: dragon tile {tile:02X}')
    # Ending sprite bank: reuse the four Link pairs displaced by Barba and Zelda.
    ending_fire_graphics = compile_ending_fire()
    fire_off = CHR_OFFSET + 14 * 4096 + 0xE0 * 16
    original = source[fire_off:fire_off+len(ending_fire_graphics)]
    if hashlib.sha256(original).hexdigest() != 'bd229b13118d533415235815b40458d5e292cd88ac776be66674586dbc28eaa0':
        raise ValueError('Ending fireball CHR allocation changed')
    overlay.put(fire_off, ending_fire_graphics, original, 'CHR 0E: ending fireball frames')
    # Ending '?' glyph in CHR bank 15 tile $0F (matching the shaded font of !/$07 and A/$DA).
    question_tile = encode_tile([
        '01111120',
        '11200112',
        '00001122',
        '00011220',
        '00022000',
        '00000000',
        '00012000',
        '00022000',
    ])
    q_off = CHR_OFFSET + 15 * 4096 + 0x0F * 16
    overlay.put(q_off, question_tile, b'\x00' * 16, 'CHR 0F: ending question mark tile 0F')
    # Ending ash tiles ($5E/$62, replacing unused Link-only tiles across matching even CHR banks).
    for bank in (0, 2, 4, 8, 10, 12, 14, 18, 20, 24):
        for dst_tile, src_tile in ((0x5E, ASH_TILES[0]), (0x62, ASH_TILES[1])):
            ash_off = CHR_OFFSET + bank*4096 + dst_tile*16
            overlay.put(ash_off, graphics[src_tile], source[ash_off:ash_off+32], f'CHR {bank:02X}: ending ash tile {dst_tile:02X}')
    # File Select & 1-Up dolls: CHR bank 0 $D0/$D1 and all 13 even side-view banks $A8/$A9.
    doll = compile_file_select_doll(ROOT)
    doll_offset = CHR_OFFSET + 0xD0 * 16
    overlay.put(doll_offset, doll, source[doll_offset:doll_offset+32], 'CHR 00: File Select Barba doll')
    for bank in range(0, 26, 2):
        oneup_offset = CHR_OFFSET + bank*4096 + 0xA8*16
        overlay.put(oneup_offset, doll, source[oneup_offset:oneup_offset+32], f'CHR {bank:02X}: 1-Up Barba doll')
    # Villager shout words & combo counter: town CHR bank 7 (odd 8x16 bytes) or
    # town sprite bank 6 (even bytes), towns only.
    glyphs = compile_shout_glyphs(ROOT, source)
    if set(glyphs) != set(SHOUT_PAIR_SHA256):
        raise ValueError('Shout glyph pairs differ from the audited allocation')
    for (bank, pair), data in sorted(glyphs.items()):
        offset = CHR_OFFSET + bank*4096 + pair*16
        original = source[offset:offset+32]
        if hashlib.sha256(original).hexdigest()[:16] != SHOUT_PAIR_SHA256[(bank, pair)]:
            raise ValueError(f'Shout glyph pair {bank:02X}:{pair:02X} is not the audited original')
        overlay.put(offset, data, original, f'CHR {bank:02X}: shout glyph pair {pair:02X}')
    # Town scorch marks: flame and char 2x2 BG art in town CHR bank 7 (ScorchTiles in src/blocks.inc).
    for tile, data in sorted(compile_town_fire(ROOT).items()):
        offset = CHR_OFFSET + TOWN_FIRE_BANK*4096 + tile*16
        original = source[offset:offset+16]
        if hashlib.sha256(original).hexdigest()[:16] != TOWN_FIRE_TILE_SHA256[tile]:
            raise ValueError(f'Town fire tile {tile:02X} is not the audited original')
        overlay.put(offset, data, original, f'CHR {TOWN_FIRE_BANK:02X}: town fire tile {tile:02X}')
    # Dialogue glyphs (apostrophe) in the town BG bank; see TEXT_GLYPHS in tools/assets.py.
    for tile, data in sorted(compile_text_glyphs().items()):
        offset = CHR_OFFSET + TEXT_GLYPH_BANK*4096 + tile*16
        original = source[offset:offset+16]
        if hashlib.sha256(original).hexdigest()[:16] != TEXT_GLYPH_SHA256[tile]:
            raise ValueError(f'Text glyph tile {tile:02X} is not the audited original')
        overlay.put(offset, data, original, f'CHR {TEXT_GLYPH_BANK:02X}: dialogue glyph {tile:02X}')
    # Level-up pane: ATTACK -> BREATH (same six tiles) and the sword icon -> fireball.
    overlay.prg(0, 0x9BE9, bytes.fromhex('db eb de da ed e1'), bytes.fromhex('da ed ed da dc e4'),
                'Level-up pane label BREATH')
    breath_icon = compile_breath_icon()
    for bank in BREATH_ICON_BANKS:
        offset = CHR_OFFSET + bank*4096 + BREATH_ICON_TILE*16
        original = source[offset:offset+16]
        if hashlib.sha256(original).hexdigest()[:16] != BREATH_ICON_SHA256:
            raise ValueError(f'Breath icon tile {bank:02X}:{BREATH_ICON_TILE:02X} is not the vanilla sword')
        overlay.put(offset, breath_icon, original, f'CHR {bank:02X}: level-up breath icon {BREATH_ICON_TILE:02X}')
    # North Palace sleeping-princess scorch marks & Barba shout glyphs in CHR bank 3.
    for tile, data in sorted(compile_castle_fire(ROOT).items()):
        offset = CHR_OFFSET + CASTLE_FIRE_BANK*4096 + tile*16
        original = source[offset:offset+16]
        if hashlib.sha256(original).hexdigest()[:16] != CASTLE_FIRE_TILE_SHA256[tile]:
            raise ValueError(f'Castle fire tile {tile:02X} is not the audited original')
        overlay.put(offset, data, original, f'CHR {CASTLE_FIRE_BANK:02X}: castle fire tile {tile:02X}')
    for pair, data in sorted(compile_castle_shout_glyphs(ROOT, source).items()):
        offset = CHR_OFFSET + CASTLE_SHOUT_BANK*4096 + pair*16
        original = source[offset:offset+32]
        if hashlib.sha256(original).hexdigest()[:16] != CASTLE_SHOUT_PAIR_SHA256[pair]:
            raise ValueError(f'Castle shout pair {pair:02X} is not the audited original')
        overlay.put(offset, data, original, f'CHR {CASTLE_SHOUT_BANK:02X}: castle shout pair {pair:02X}')
    # Title screen: replace LINK's bank-1 tiles and nametable rows with BARBA.
    title_tiles, title_rows = compile_title_logo(ROOT)
    for tid, data in sorted(title_tiles.items()):
        offset = CHR_OFFSET + TITLE_CHR_BANK*4096 + tid*16
        original = source[offset:offset+16]
        if hashlib.sha256(original).hexdigest()[:16] != TITLE_TILE_SHA256[tid]:
            raise ValueError(f'Title tile {tid:02X} is not the audited original')
        overlay.put(offset, data, original, f'CHR {TITLE_CHR_BANK:02X}: title logo tile {tid:02X}')
    title_macro = (
        bytes([0x22, 0xC6, len(title_rows[0]), *title_rows[0]]) +
        bytes([0x22, 0xE6, len(title_rows[1]), *title_rows[1]]) +
        bytes([0x23, 0x06, len(title_rows[2]), *title_rows[2]]) +
        bytes.fromhex('23 f0 08 00 00 00 00 00 00 00 cc') +
        bytes([0x23, 0x26, len(title_rows[3]), *title_rows[3]])
    )
    expected_title_macro = bytes.fromhex(
        '22ca0e3e4042f44b4d5153585a5f61081822df01fd'
        '22ea0d3f4143f44c4e5254595b60620922ff01fd'
        '2309174446484a1afd4f5556fd5c63650a0cf4f4f4f4f4f4f4fd'
        '23f00800000000000000cc'
        '2329174547494967475047575d5e64660b0df4f4f4f4f4f4f4fd'
    )
    overlay.prg(5, 0xAFC6, title_macro, expected_title_macro, 'Title screen BARBA logo macro')
    row0_addr = 0xAFC6
    row1_addr = row0_addr + 3 + len(title_rows[0])
    row2_addr = row1_addr + 3 + len(title_rows[1])
    row3_addr = row2_addr + 3 + len(title_rows[2]) + 11
    overlay.prg(
        5, 0xAB65,
        b''.join(addr.to_bytes(2, 'little') for addr in (row0_addr, row1_addr, row2_addr, row3_addr)),
        bytes.fromhex('c6afdbafefaf14b0'),
        'Title screen BARBA logo redraw pointers',
    )
    overlay.prg(
        5, 0xAEEA,
        bytes([
            3 + len(title_rows[0]),
            3 + len(title_rows[1]),
            3 + len(title_rows[2]) + 11,
            3 + len(title_rows[3]),
        ]),
        bytes.fromhex('1514251a'),
        'Title screen BARBA logo redraw lengths',
    )
    # Title screen: replace blue water with molten lava and embers, and use Barba's gold palette.
    overlay.prg(
        5, 0xAF48,
        bytes.fromhex('0f0616270f0f0a190f3016060f2b0f000f1627300f0f1627'),
        bytes.fromhex('0f0112210f0f0a120f3012020f2b0f000f1626300f0f1921'),
        'Title screen lava and Barba palette',
    )
    # Title screen: replace the sword-in-stone OAM entries with 24x48 Barba overlooking the lava.
    overlay.prg(5, 0xA7DD, bytes.fromhex('7f0002747f02027c'), bytes.fromhex('6ff802786ffa0280'), 'Title Barba head left/mid')
    overlay.prg(5, 0xA7FD, bytes.fromhex('7f0402848f06027c'), bytes.fromhex('7ffc02787ffe0280'), 'Title Barba head right/neck')
    overlay.prg(5, 0xA819, bytes.fromhex('8f0802849f0a02749f0c027c9f0e0284'), bytes.fromhex('8fea02788fec02809fea02789fec0280'), 'Title Barba neck/body')
    # Title screen: occasionally open Barba's mouth subtly. The fireball SFX ($ED |= $40) that used to fire
    # here took over pulse 1 and cut into the title music (producer, 2026-11-14). Instead, every 4th full jaw
    # opening (~17 s) starts the short noise-channel roar (same envelope as Inferno's), which leaves both
    # pulse melodies and the triangle alone. The hook now enters TitleRoarUpdate ($A5AE), which runs the roar
    # envelope each frame and then jumps to the jaw animation at $A54F.
    roar_update = 0xA5AE
    sampled_title_code = None
    if title_roar_wav:
        sampled_title_code, roar_update, roar_jaw = roar_sample.title_code(sample, roar_info)
        for filename, bank, address in [('sampled-roar', 6, 0x8C00), ('sample-gem', 4, 0xA7E5),
                                         ('item-roar', 6, 0x8A00),
                                         ('laugh-delay', 6, 0x8F70)]:
            data = (output/f'barba-{filename}.bin').read_bytes()
            overlay.prg(bank, address, data, b'\xff'*len(data), f'Sampled roar {filename} helpers')
        # Only the bank-0 copy of the reset entry is dead. The mapper
        # routines beginning at $BF9D are also called by gameplay.
        item_hold = (output/'barba-item-hold.bin').read_bytes()
        expected_stub = bytes.fromhex(
            '78d8a2008e0020e8ad022010fbcaf0f89a8e00808e00a08e00c08e00e0'
            'a90f209dbf20b1bfa90720ccbf4c00c0'
        )
        overlay.prg(0, 0xBF70, item_hold, expected_stub[:len(item_hold)], 'Item celebration pickup and input helpers')
        overlay.prg(7, 0xE547, b'\x20' + labels['FarCall0'].to_bytes(2, 'little')
                    + labels['ItemHoldPickup'].to_bytes(2, 'little') + b'\x60\xea\xea',
                    bytes.fromhex('b5 af 29 7f 8d 9d 04 60'), 'Start the key item hold at pickup')
        for address, target, original in [(0x9341, 'ItemHoldPose', 'ad 9c 04'),
                                          (0x8DC3, 'ItemHoldSpell', 'ad 4c 07')]:
            hook(0, address, target, 0x4C, original)
        # Block Start during the hold. Otherwise use the native rising-edge
        # test, written as (current XOR previous) AND current AND Start.
        overlay.prg(0, 0x9D96, bytes.fromhex('ad d4 64 d0 31 a5 f7 4d 44 07 25 f7 29 10 f0 26 ea'),
                    bytes.fromhex('ad 44 07 29 10 85 00 a5 f7 29 10 f0 29 c5 00 f0 25'),
                    'Block the side-view pause pane during item celebrations')
        overlay.prg(6, 0x9010, b'\x20' + labels['RoarAudio'].to_bytes(2, 'little'),
                    bytes.fromhex('20 0b 92'), 'Sampled gameplay DMC coordinator')
        overlay.prg(6, 0x9B24, b'\x20' + labels['RoarItemFanfareEnd'].to_bytes(2, 'little'),
                    bytes.fromhex('ad 07 07'), 'Key item roar after native pickup fanfare')
        overlay.prg(6, 0x9B73, b'\x20' + labels['RoarItemFanfareStart'].to_bytes(2, 'little'),
                    bytes.fromhex('8d fb 07'), 'Retire interrupted item fanfares on a track change')
        for address, target, original in [(0x9031, 'RoarPulse1', '8e 00 40'), (0x9038, 'RoarPulse2', '8e 04 40')]:
            overlay.prg(6, address, b'\x20' + labels[target].to_bytes(2, 'little'),
                        bytes.fromhex(original), f'Gameplay music ducking {target}')
        overlay.prg(4, 0x9B47, b'\x4c' + labels['RoarGemEnd'].to_bytes(2, 'little'),
                    bytes.fromhex('ac fb 07'), 'Palace victory roar before refill, control unlock and XP')
        overlay.prg(7, 0xE314, b'\x20' + labels['FarCall0'].to_bytes(2, 'little')
                    + labels['BarbaHurtRoar'].to_bytes(2, 'little') + b'\xea',
                    bytes.fromhex('a9 01 85 e9 85 00'), 'Barba short hurt roar; native recoil setup preserved')
        # Native early pad polling precedes the HUD split: no bank bridge or
        # repeated reads can fit its raster budget. During a roar, return raw
        # buttons captured safely by the later audio hook (one frame latency).
        # Otherwise replay the overwritten prologue and continue vanilla.
        pad_capture = bytes.fromhex(
            'ad ee 05 10 07 ad 15 40 29 10 d0 08 a2 01 8e 16 40 4c 6c d3 '
            'ad d2 64 85 f5 ad d3 64 85 f6 60')
        pad_offset = prg_offset(7, 0xF3C1)
        overlay.prg(7, 0xF3C1, pad_capture, source[pad_offset:pad_offset+len(pad_capture)],
                    'Sample experiment: early cached pad read in displaced laugh data')
        overlay.prg(7, 0xD367, bytes.fromhex('4c c1 f3 ea ea'),
                    bytes.fromhex('a2 01 8e 16 40'), 'DMC-safe controller cache hook before HUD split')
        offset = prg_offset(7, roar_sample.SAMPLE_ADDRESS)
        expected = source[offset:offset+roar_sample.SAMPLE_CAPACITY]
        if hashlib.sha256(expected).hexdigest() != roar_sample.ORIGINAL_SHA256:
            raise ValueError('Original laugh sample allocation differs')
        overlay.prg(7, roar_sample.SAMPLE_ADDRESS, sample, expected[:len(sample)],
                    'Famicom roar in reclaimed native laugh sample data')
        laughs = game_over_audio.compact_laughs(source, len(sample))
        for number, (address, data, original) in enumerate(laughs, 1):
            shared = max(0, game_over_audio.SAMPLE_ADDRESS + len(sample) - address)
            if shared and data[:shared] != sample[-shared:]:
                raise ValueError('Compact laugh does not match the approved roar tail')
            end = len(data)
            if number < len(laughs) and address+end-1 == laughs[number][0]:
                if data[-1:] != laughs[number][1][:1]:
                    raise ValueError('Compact laughs disagree on their shared silent byte')
                end -= 1  # The next guarded write owns the shared byte.
            overlay.prg(7, address+shared, data[shared:end], original[shared:end],
                        f'Compact octave-up Ganon laugh waveform {number}')
        for number, entry in enumerate(game_over_audio.LAUGH_ENTRIES):
            laugh_address, laugh, _ = laughs[game_over_audio.SHARED_LAUGH_INDICES[number]]
            table_address = 0x917B + entry*2
            original = source[prg_offset(6, table_address):prg_offset(6, table_address)+2]
            overlay.prg(6, table_address,
                        bytes([(laugh_address-0xC000)//64, (game_over_audio.SHARED_LAUGH_LENGTHS[number]-1)//16]), original,
                        f'Game Over compact laugh pointer/length {entry}')
        overlay.prg(6, 0x925A, b'\x20' + labels['RoarNativeRate'].to_bytes(2, 'little') + b'\xea\xea',
                    bytes.fromhex('a9 0f 8d 10 40'), 'Game Over native descending contour; other sample rates preserved')
        roar_info['game_over_shared_laugh'] = {
            'waveforms': [{'address': a, 'bytes': len(d)} for a, d, _ in laughs],
            'rates': list(game_over_audio.SHARED_LAUGH_RATES), 'spacing_frames': 23,
            'initial_delay_frames': 36}
        # Title-only music driver normally disables DMC every frame. Preserve
        # it while the one-shot timer is live, without retriggering a completed
        # sample. Leaving title mode clears the timer and disables DMC even if
        # Start interrupts a roar. Use the end of bank-6 UNUSED_0 before $9000.
        overlay.prg(6, 0x8005, bytes.fromhex('20 d0 8f ea ea'),
                    bytes.fromhex('a9 0f 8d 15 40'), 'PROTOTYPE: title DMC enable hook')
        # Ease the DAC from reset's zero to its sample midpoint before the first
        # jaw opening. A direct $4011=$40 at the first roar produces a pop.
        title_bias = bytes.fromhex(
            'ad 36 07 c9 03 f0 09 a9 00 8d ee 05 8d ef 05 60 '
            'ad fa 05 d0 10 ad ee 05 c9 40 b0 09 18 69 02 8d ee 05 8d 11 40 60')
        overlay.prg(6, 0x8F40, title_bias, b'\xff'*len(title_bias),
                    'Sampled title: gentle initial DAC bias instead of first-roar pop')
        title_enable = bytes.fromhex('20 40 8f') + bytes.fromhex(
            'ad 36 07 c9 03 f0 05 a9 00 8d f0 05 '
            'ad f0 05 f0 09 ad 15 40 29 10 09 0f d0 02 a9 0f 8d 15 40 60')
        overlay.prg(6, 0x8FD0, title_enable, b'\xff'*len(title_enable),
                    'PROTOTYPE: preserve title DMC playback')
        # The title pulse volume writers share X=control/volume. Halve only
        # the volume nibble while roaring; preserve duty/envelope bits and all
        # caller registers/flags. Normal envelopes continue running underneath.
        duck_table = bytes((v & 0xf0) | ((v & 15)//2) for v in range(256))
        overlay.prg(6, 0x8E00, duck_table, b'\xff'*256,
                    'PROTOTYPE: title music half-volume table')
        for original, helper, register in [(0x810F, 0x8F00, 0x4000), (0x8116, 0x8F14, 0x4004)]:
            store = helper + 14
            code = (bytes.fromhex('08 48 ad f0 05 f0 06 bd 00 8e 4c')
                    + store.to_bytes(2, 'little') + b'\x8a\x8d'
                    + register.to_bytes(2, 'little') + bytes.fromhex('68 28 60'))
            overlay.prg(6, helper, code, b'\xff'*len(code),
                        f'PROTOTYPE: title pulse {register:04X} duck helper')
            overlay.prg(6, original, b'\x20' + helper.to_bytes(2, 'little'),
                        b'\x8e' + register.to_bytes(2, 'little'),
                        f'PROTOTYPE: title pulse {register:04X} volume hook')
    overlay.prg(5, 0xA8CF, b'\x4c' + roar_update.to_bytes(2, 'little') + b'\xea',
                bytes.fromhex('a2 6b a5 12'), 'Title Barba animate hook')
    # Keep the title's three jaw columns synchronized with the compiled player
    # art. A stale $22 right-column byte selected crouch art on the open frame.
    tall_layout = validate_layout(ROOT)
    title_heads = [tall_layout[pose*9:pose*9+3] for pose in (3, 4, 5)]
    title_jaws = bytes(head[col] for col in range(3) for head in title_heads)
    title_animation = bytearray(bytes.fromhex(
            'ad 1c 02 c9 7f d0 38 a5 12 c9 40 90 1e c9 60 b0 1a '
            'c9 48 90 12 f0 06 c9 58 b0 0c 90 06 '
            '20 9e a5 ea ea ea '
            'a2 02 d0 06 a2 01 d0 02 a2 00 '
            'bd 95 a5 8d 1d 02 bd 98 a5 8d 21 02 bd 9b a5 8d 3d 02 '
            'a2 6b a5 12 4c d3 a8 '
        ) + title_jaws)
    if sampled_title_code is not None:
        title_animation[7:11] = b'\x20' + roar_jaw.to_bytes(2, 'little') + b'\xea'
    overlay.prg(
        5, 0xA54F,
        bytes(title_animation),
        b'\xff' * 79,
        'Title Barba mouth animation',
    )
    # Title roar. $05FA (DRAW_FRAME) is renderer scratch, written before it is read in gameplay, so the title
    # can use it as a jaw-opening counter. $05F0 is ROAR_TIMER (no original references).
    title_roar = bytes.fromhex(
        # TitleRoarStart $A59E: inc counter; every 4th opening set ROAR_TIMER = $30
        'ee fa 05 ad fa 05 29 03 d0 05 a9 30 8d f0 05 60 '
        # TitleRoarUpdate $A5AE: same envelope as BarbaUpdate's @roar, then jmp $A54F
        'ad f0 05 f0 1a ce f0 05 ad f0 05 4a 4a aa '
        'bd d0 a5 8d 0c 40 bd dc a5 8d 0e 40 a9 08 8d 0f 40 '
        '4c 4f a5 '
        # $A5D0 RoarVolume, $A5DC RoarPitch (copies of the bank-0 tables in src/barba.asm)
        '30 32 34 35 36 38 39 3a 3c 3d 3f 3b '
        '0f 0f 0e 0f 0d 0f 0e 0c 0f 0d 0b 0e'
    )
    assert len(title_roar) == 0xA5E8 - 0xA59E
    if sampled_title_code is not None:
        title_roar = sampled_title_code
    overlay.prg(5, 0xA59E, title_roar, b'\xff' * len(title_roar), 'Title Barba roar')
    # Sampled audio packs its compact laugh above; legacy audio owns five samples.
    if not title_roar_wav:
        laughs = game_over_audio.compile_laughs(source)
        for number, (entry, (address, raised, expected)) in enumerate(zip(game_over_audio.LAUGH_ENTRIES, laughs), 1):
            overlay.prg(7, address, raised, expected, f'Game Over octave-up laugh {number}')
            table_address = 0x917B + entry*2
            original = source[prg_offset(6, table_address):prg_offset(6, table_address)+2]
            overlay.prg(6, table_address, bytes([(address-0xC000)//64, (len(raised)-1)//16]),
                        original, f'Game Over shortened laugh {number} pointer/length')
    # Game Over screen: replace "RETURN OF GANON" ($8010, 15 bytes) with "LINK KEEPS LAVA".
    overlay.prg(
        0, 0x8010,
        bytes(0xF4 if ch == ' ' else 0xDA + ord(ch) - ord('A') for ch in 'LINK KEEPS LAVA'),
        bytes.fromhex('ebdeedeeebe7f4e8dff4e0dae7e8e7'),
        'Game Over Barba subtitle',
    )
    game_over_tiles, game_over_map = compile_game_over_link(source)
    map_offset = prg_offset(0, GAME_OVER_MAP_START)
    overlay.prg(0, GAME_OVER_MAP_START, game_over_map,
                source[map_offset:map_offset+len(game_over_map)],
                'Game Over black Link nametable')
    for tile, data in game_over_tiles.items():
        offset = CHR_OFFSET + GAME_OVER_CHR_BANK*4096 + tile*16
        overlay.put(offset, data, source[offset:offset+16],
                    f'Game Over black Link tile {tile:02X}')
    story_lines = [
        'AFTER BARBA WOKE UP FROM A  ',
        'LONG NAP, HE FOUND LINK     ',
        'SQUATTING IN PALACE 6.      ',
        'FURIOUS, BARBA LEFT HIS     ',
        'LAVA BATH TO SPEAK WITH     ',
        'THE TOWNSFOLK OF HYRULE.    ',
        'UNFORTUNATELY, HE STILL     ',
        'BREATHES FIVE FIREBALLS     ',
        'EVERY TIME HE SAYS HELLO.   ',
        'NOW BARBA MUST ROAST HIS    ',
        'WAY BACK TO PALACE 6 AND    ',
        'EVICT THAT GREEN SQUATTER...',
        '     @2026 JERBTRUNDLES     ',
    ]
    story_char = {'.': 0xCF, ',': 0x9C, ' ': 0xF4, '@': 0x0E}
    def encode_story_line(line: str) -> bytes:
        if len(line) != 28:
            raise ValueError(f'Title story line must be 28 chars: {line!r}')
        out = bytearray()
        for ch in line:
            if 'A' <= ch <= 'Z':
                out.append(0xDA + ord(ch) - ord('A'))
            elif '0' <= ch <= '9':
                out.append(0xD0 + ord(ch) - ord('0'))
            elif ch in story_char:
                out.append(story_char[ch])
            else:
                raise ValueError(f'Unsupported title story char {ch!r}')
        out.append(0xFD)
        return bytes(out)
    expected_story = b''.join(encode_story_line(line) for line in [
        'AFTER GANON WAS DESTROYED,  ',
        'IMPA TOLD LINK A SLEEPING   ',
        'SPELL WAS CAST ON PRINCESS  ',
        'ZELDA. SHE WILL WAKE ONLY   ',
        'WITH THE POWER OF NO.3      ',
        'TRIFORCE SEALED IN A PALACE ',
        'IN HYRULE. TO BREAK THE     ',
        'SEAL,CRYSTALS MUST BE       ',
        'PLACED IN STATUES IN 6      ',
        'WELL GUARDED PALACES.       ',
        'LINK SET OUT ON HIS MOST    ',
        'ADVENTURESOME QUEST YET...  ',
        '       @1987 NINTENDO       ',
    ])
    new_story = b''.join(encode_story_line(line) for line in story_lines)
    overlay.prg(5, 0xA932, new_story, expected_story, 'Title screen Barba story scroll')
    # Last two CHR banks are filler in the guarded input; dedicate them to overworld.
    world = bytearray(source[CHR_OFFSET+16*4096:CHR_OFFSET+18*4096])
    world[:len(ow)] = ow
    # Two 8x16 overworld flame frames at tile pairs $60 and $62 (empty in vanilla bank 16).
    if world[0x60*16:0x64*16] != b'\x00'*64:
        raise ValueError('Overworld flame sprite slots $60-$63 are not empty')
    def _chr_8x16(rows):
        out = bytearray(32)
        for y in range(16):
            p0 = p1 = 0
            for x, ch in enumerate(rows[y]):
                v = {'.': 0, 'o': 1, '+': 2, '#': 3}[ch]
                bit = 7 - x
                p0 |= (v & 1) << bit
                p1 |= ((v >> 1) & 1) << bit
            base = (y // 8) * 16 + (y % 8)
            out[base] = p0
            out[base + 8] = p1
        return bytes(out)
    world[0x60*16:0x62*16] = _chr_8x16([
        '....o...', '...oo...', '...o+o..', '..oo+o..',
        '..o++oo.', '.oo+o+o.', '.o++o+o.', 'oo+o++oo',
        'o+oooo+o', 'o++oo++o', '+o++++o+', '#+o++o+#',
        '##+##+##', '.######.', '..####..', '........',
    ])
    world[0x62*16:0x64*16] = _chr_8x16([
        '..o.....', '..oo..o.', '..o+o.oo', '.oo+o.o.',
        '.o++oo+o', 'oo+o++o.', 'o+oo+oo.', 'o++o++oo',
        '+oooooo+', 'o+oooo+o', '+o++++o+', '#+o++o+#',
        '##+##+##', '.######.', '..####..', '........',
    ])
    offset = CHR_OFFSET+30*4096
    overlay.put(offset, world, b'\xFF'*8192, 'Dedicated overworld graphics')

    old_palette, new_palette = bytes.fromhex('18 36 2a'), bytes.fromhex('16 27 30')
    palette_offsets = [i for i in range(16, CHR_OFFSET-2) if source[i:i+3] == old_palette]
    for offset in palette_offsets:
        overlay.put(offset, new_palette, old_palette, f'Dragon palette at {offset:05X}')
    # Strided WRAM flash-restore palette table ($69CE/$69D4/$69DA + 4) and side-view init ($90D9).
    overlay.prg(0, 0x90DA, b'\x30', b'\x2A', 'Dragon palette restore ($69DE) on side-view init')
    # SCALES (Shield): vanilla turns colour 3 red ($16), which Barba already is. Keep the white belly (byte still sets the $070F flag);
    # src/scales.inc turns the outline navy and the body sky blue.
    # instead; the same byte is the $070F active flag (src/scales.inc adds the cast/hit feedback).
    overlay.prg(0, 0x8E8E, b'\x30', b'\x16', 'SCALES white belly colour ($69DE/$070F)')
    overlay.prg(0, 0xA9FA, b'\x16', b'\x18', 'Dragon flash-restore palette color 1 ($69D2)')
    overlay.prg(0, 0xAA00, b'\x27', b'\x36', 'Dragon flash-restore palette color 2 ($69D8)')
    overlay.prg(0, 0xAA06, b'\x30', b'\x2A', 'Dragon flash-restore palette color 3 ($69DE)')
    # Generous Downstab hitbox ($E9A2): 18 px wide ($0E->$12) x 12 px tall ($03->$0C).
    overlay.prg(7, 0xE9A1, b'\x0C', b'\x03', 'Downstab hitbox height (12 px)')
    overlay.prg(7, 0xE9B5, b'\x12', b'\x0E', 'Sword/Downstab hitbox width (18 px)')
    # Geldarm (sand worm) hurtbox ($E90E, type 5): widen 8->12 px (dx=-2) and extend height 8->64 px
    # so Barba's standing and crouching fireballs hit its body as well as its head.
    overlay.prg(7, 0xE90E, b'\xFE\x0C\x00\x40', b'\x00\x08\x00\x08', 'Geldarm (sand worm) hurtbox (12x64 px)')
    # Geldarm dies by sinking into the sand (producer, 2026-11-15; src/geldarm.inc, bank-1 pad $9EB9):
    # entry ($9BB5 LDA $AF,X / BNE) -> GeldarmUpdate, and its JSR $DE40 hit/draw call -> GeldarmHits.
    hook(1, 0x9BB5, 'GeldarmUpdate', 0x4C, 'b5 af d0 35', 1)
    hook(1, 0x9C3D, 'GeldarmHits', 0x20, '20 40 de')
    # Fewer hits: West Hyrule HP table ($9421 + enemy $20, copied to $6D41) 8 -> 4.
    overlay.prg(1, 0x9441, b'\x04', b'\x08', 'Geldarm HP 8 -> 4')

    # Existing menu stores 14-byte rows. Preserve border, cost digits and spacing.
    for i, name in enumerate(['SCALES','JUMP','LIFE','WYRMLNG','METEOR','REFLECT','SPELL','INFERNO']):
        offset = prg_offset(0, 0x9C2A + i*14)
        data = bytes(0xDA+ord(c)-ord('A') for c in name.ljust(7) if c != ' ')
        data += b'\xCF'*(7-len(data))
        overlay.put(offset, data, source[offset:offset+7], f'Spell menu: {name}')

    # Palace 6 "Lava Link" boss: Link art in CHR bank 25, Spear (05) sword beams, Link palette.
    # Use Sprite Palette 3 ($3F1D) so Sprite Palette 1 ($3F15, shared by health bars and fireballs) stays red/orange.
    for tile_id, pair_bytes in compile_lava_link(source).items():
        offset = CHR_OFFSET + 25*4096 + tile_id*16
        overlay.put(offset, pair_bytes, source[offset:offset+32], f'Lava Link CHR bank 25 pair {tile_id:02X}')
    overlay.prg(4, 0xA9F6, b'\xce', b'\x4e', 'Lava Link enemy palette (3)')
    overlay.prg(4, 0xB19B, b'\x05', b'\x04', 'Lava Link sword-beam breath (05)')
    overlay.prg(4, 0xAABB, b'\x03', b'\x00', 'Lava Link sword-beam palette (3)')
    overlay.prg(4, 0xB11F, bytes.fromhex('20 65 a7'), bytes.fromhex('20 0d b2'), 'Lava Link palette hook')
    overlay.prg(
        4, 0xA765,
        # Ends in JMP LavaLinkHurt ($A795), which then continues to the original $B20D.
        bytes.fromhex('ad 99 04 d0 21 ad 28 07 f0 1c ad 25 07 d0 17 ad 01 03 d0 12 a0 00 b9 8e a7 99 02 03 c8 c0 07 d0 f5 a9 06 8d 01 03 4c 95 a7'),
        b'\xff' * 41,
        'Lava Link palette helper',
    )
    overlay.prg(4, 0xA78E, bytes.fromhex('3f 1d 03 18 36 2a ff'), b'\xff' * 7, 'Lava Link palette packet')
    # Lava Link plays Link's hurt sound when hit (producer, 2026-11-14; boss only, Barba keeps hers).
    # Every hit sets the enemy hit timer $040E,X = $30 (bank 7 $E726) and the enemy-hit SFX ($ED |= $10);
    # Display decrements the timer later in this same update, so exactly one boss update per hit sees $30.
    # LavaLinkHurt ($A795, X = boss slot): on $30, start Link's hurt SFX ($E9 = 1, as bank 7 $E314 does)
    # and drop the enemy-hit SFX bit if the driver hasn't consumed it yet; then JMP $B20D as before.
    overlay.prg(
        4, 0xA795,
        bytes.fromhex('bd 0e 04 c9 30 d0 0a a9 01 85 e9 a5 ed 29 ef 85 ed 4c 0d b2'),
        b'\xff' * 20,
        'Lava Link hurt sound',
    )
    # Neck stops at the lava surface (producer, 2026-11-14): fewer sprites, and it reads as rising out of the
    # lava. Vanilla counted pieces down to Y=$E8 and skipped the whole neck below it (which also skips the
    # $049A head/beam X update). Now: count down to $D0, and below it draw a single piece instead of none, so
    # $049A stays current while the boss emerges. Fully risen: 7 pieces -> 5 (14 -> 10 neck sprites).
    # $D0 - Y max is $50 (Y >= $80), so the dropped AND #$07 cap is never needed.
    overlay.prg(
        4, 0xB294,
        bytes.fromhex('a9 d0 38 e5 00 b0 02 a9 00 4a 4a 4a 4a'),
        bytes.fromhex('a9 e8 38 e5 00 90 69 4a 4a 4a 4a 29 07'),
        'Lava Link neck stops at lava',
    )
    overlay.prg(4, 0xB286, b'\x02\xfe', b'\x10\xf0', 'Lava Link head centered over body')
    # Cut Lava Link sword beams per attack from 6 (every 2 frames in $4F..$40) to 2 ($48 and $40, 8 frames apart).
    overlay.prg(4, 0xB18C, b'\x29\x37', b'\x29\x30', 'Lava Link beam cadence mask ($37 -> $48/$40)')
    overlay.prg(4, 0xB190, b'\xea' * 5, bytes.fromhex('a5 12 4a 90 29'), 'Lava Link beam cadence no parity skip')

    # Carock takes fireball damage (producer, 2026-11-14). Vanilla's shared boss helper ($B1E9) skips the
    # projectile/sword checks for enemy $22, so beams and fireballs pass through and only Reflect hurts him.
    # In his visible window ($AF $E0-$EF, $AEB2) the $E4D9 call goes to CarockHit ($A7D0, bank-4 pad):
    # JSR $DE63 runs the native projectile check ($E48B, Barba's fireball gateway), the sword check, then
    # the same $E4D9. A kill there leaves the generic death state ($B6 = 2), which would draw Carock into
    # OAM 0 (the HUD sprite-0 split) and hang the NMI; so on a kill call $B1F6, the native boss-death
    # bookkeeping used for boss kills. Fireballs still need the visible window.
    # $AEB2 is shared with the Palace 3/4/6 Wizzrobe ($1D, routine $AE4F), so the $B1F6 call is gated on
    # $A1 = $22. Ungated (2026-11-14..16), a Wizzrobe kill ran $B1F6: it revived the Wizzrobe ($B6 = 1, HP
    # wrapped) and wrote $FF to $6E1D+$1D, so every later Wizzrobe death in that palace dropped a boss key.
    # Wizzrobes keep the breath/sword checks from $DE63 (vanilla only had $E4D9) and die normally.
    overlay.prg(
        4, 0xA7D0,
        # JSR $DE63 / LDX $10 / LDA $B6,X / CMP #1 / BEQ rts / LDA $A1,X / CMP #$22 / BNE rts / JSR $B1F6 / RTS
        bytes.fromhex('20 63 de a6 10 b5 b6 c9 01 f0 09 b5 a1 c9 22 d0 03 20 f6 b1 60'),
        b'\xff' * 21,
        'CarockHit helper',
    )
    overlay.prg(4, 0xAEB4, bytes.fromhex('20 d0 a7'), bytes.fromhex('20 d9 e4'), 'Carock fireball hit check')
    # 48 HP takes three fireballs at Attack 7 (18 each). Six HP per pip fills the eight-pip bar.
    overlay.prg(4, 0xA943, b'\x30', b'\x10', 'Carock HP (16 -> 48)')
    overlay.prg(4, 0xAE82, b'\x06', b'\x02', 'Carock HUD HP per pip (2 -> 6)')
    # Reflected bolts use Attack 8 damage (24) against Carock, with native damage for other targets.
    overlay.prg(4, 0xA804, bytes.fromhex('b5 a1 c9 22 d0 02 a0 08 4c 26 e7'), b'\xff' * 11,
                'Carock Reflect damage helper')  # LDA $A1,X / CMP #$22 / BNE native / LDY #8 / JMP $E726
    overlay.prg(4, 0xAD6B, bytes.fromhex('20 04 a8'), bytes.fromhex('20 26 e7'), 'Carock reflected bolt damage')
    # Hidden Red Jars ($05): allow breath as well as melee to reveal them.
    hook(5, 0xA525, 'HiddenJarHit', 0x20, '20 77 e6')
    overlay.prg(
        4, 0xA7BF,
        bytes.fromhex('a9 ff 95 c2 20 77 e6 b5 a8 29 20 d0 03 4c 8b e4 60'),
        b'\xff' * 17,
        'HiddenJarHit bank 4 helper',
    )
    overlay.prg(4, 0xB842, bytes.fromhex('20 bf a7'), bytes.fromhex('20 77 e6'), 'Hidden Red Jar Type A fireball hit check')
    overlay.prg(4, 0xAF65, bytes.fromhex('20 bf a7'), bytes.fromhex('20 77 e6'), 'Hidden Red Jar Type B fireball hit check')

    # Ending sequence (PRG bank 5): replace Link & half-Link chimera with full 24x48 Barba + Zelda,
    # update Zelda's wake-up dialogue, and add Barba Edition credits.
    overlay.prg(
        5, 0x8C0D,
        bytes.fromhex('b0 d8 22 80 b0 da 22 88 c0 dc 22 80 c0 de 22 88'),
        bytes.fromhex('b0 e0 00 78 b0 e0 40 80 c0 e2 00 78 c0 e2 40 80'),
        'Ending Zelda OAM sprites',
    )
    overlay.prg(
        5, 0x8D8D,
        bytes.fromhex(
            'a0 04 60 60 a0 02 60 68 a0 00 60 70 '
            'b0 08 60 60 b0 06 60 68 '
            'c0 0e 60 60 c0 0c 60 68 c0 0a 60 70'
        ),
        bytes.fromhex(
            'b0 02 60 70 b0 e4 20 78 b0 d8 22 80 b0 da 22 88 '
            'c0 06 60 70 c0 e6 20 78 c0 dc 22 80 c0 de 22 88'
        ),
        'Ending 24x48 Barba OAM sprites',
    )
    overlay.prg(
        5, 0x8C38,
        bytes.fromhex('4c d6 93') + b'\xea' * 9,
        bytes.fromhex('a0 0f b9 0d 8c 99 10 02 88 10 f7 60'),
        'Ending draw 24x48 Barba hook',
    )
    overlay.prg(
        5, 0x93D6,
        bytes.fromhex(
            'a0 1f b9 8d 8d 99 10 02 88 10 f7 '
            'ad 61 07 c9 06 b0 0d '
            'a9 40 a0 1c '
            '99 12 02 88 88 88 88 10 f7 '
            '60'
        ),
        b'\xff' * 32,
        'Ending draw 24x48 Barba (visible before curtain, behind curtain on drop)',
    )
    overlay.prg(
        5, 0x8DD5,
        bytes.fromhex('4c 31 8b') + b'\xea' * 9,
        bytes.fromhex('a0 1f b9 8d 8d 99 10 02 88 10 f7 60'),
        'Ending draw Barba and Zelda hook',
    )
    overlay.prg(
        5, 0x8B31,
        bytes.fromhex('20 38 8c a0 0f b9 0d 8c 99 30 02 88 10 f7 4c eb 8c'),
        b'\xff' * 17,
        'Ending draw Barba and Zelda helper',
    )
    # Clear ending toast state ($05F8 = 0) when ending starts at $8C32 (instead of JSR $8C38 directly).
    overlay.prg(5, 0x8C32, bytes.fromhex('20 42 8b'), bytes.fromhex('20 38 8c'), 'Ending init toast state hook')
    overlay.prg(
        5, 0x8B42,
        bytes.fromhex('a9 00 8d f8 05 4c 38 8c'),
        b'\xff' * 8,
        'Ending init toast state helper',
    )
    # L8CE3: keep the $074B awakening flash timer without clobbering Sprite Palette 0 ($3F10),
    # which turned Barba into a red silhouette when the split Triforce passed over him.
    # ($8CE2 is RTS, so D0 FA returns cleanly.)
    overlay.prg(
        5, 0x8CE3,
        bytes.fromhex('ce 4b 07 d0 fa 4c 44 8c'),
        source[prg_offset(5, 0x8CE3):prg_offset(5, 0x8CEB)],
        'Ending awakening flash without red Barba silhouette',
    )
    # L8F6B: keep Barba and Zelda in place (do not step closer together) and run toast update.
    overlay.prg(
        5, 0x8F6E,
        bytes.fromhex('60'),
        bytes.fromhex('a9'),
        'Ending keep Barba distance from Zelda',
    )
    # Ending toast finale ($8CEB..$8D4D + ash at $8F6F and $93F7):
    # When the curtain reaches $22A0 (covering Barba's head), Barba fires a behind-curtain fireball
    # (attr $20) that drops below the curtain into view right before hitting Zelda and turning her to ash.
    # Ash inherits the lower Zelda sprites' $22 attributes from the draw helper.
    ending_ash = bytes.fromhex(
        'a9 f8 8d 30 02 8d 34 02 8d 40 02 8d 44 02 '
        'a9 5e 8d 39 02 a9 62 8d 3d 02 '
        '4c f7 93'
    )
    overlay.prg(
        5, 0x8F6F,
        ending_ash + b'\xea' * 5,
        source[prg_offset(5, 0x8F6F):prg_offset(5, 0x8F8F)],
        'Ending Zelda-to-ash helper',
    )
    overlay.prg(
        5, 0x93F7,
        bytes.fromhex('a9 c8 8d 38 02 8d 3c 02 60'),
        b'\xff' * 9,
        'Ending Zelda-to-ash Y=$C8 tail',
    )
    ending_toast = (output/'barba-ending-fire.bin').read_bytes()
    original = source[prg_offset(5, 0x8CEB):prg_offset(5, 0x8D4E)]
    if hashlib.sha256(original).hexdigest() != 'b4717dc1b5c51ec741afd9288f02627d2f438a158397e07caec2dcb9dd8e27d6':
        raise ValueError('Ending fireball PRG allocation changed')
    overlay.prg(
        5, 0x8CEB,
        ending_toast,
        original[:len(ending_toast)],
        'Ending curtain fireball toast logic',
    )
    def encode_ending_text(text: str) -> bytes:
        table = {' ': 0x00, '!': 0x07, '?': 0x0F, '.': 0xCF}
        out = bytearray()
        for ch in text:
            if 'A' <= ch <= 'Z':
                out.append(0xDA + ord(ch) - ord('A'))
            elif ch in table:
                out.append(table[ch])
            else:
                raise ValueError(f'Unsupported ending char {ch!r}')
        out.append(0xFF)
        return bytes(out)
    ending_text = encode_ending_text(
        'BARBA?         '
        'HOLY SHIT!     '
        'THE FUCK ARE   '
        'YOU DOING HERE?'
    )
    overlay.prg(
        5, 0xBDA1,
        ending_text,
        b'\xff' * len(ending_text),
        'Ending Zelda wake-up dialogue',
    )
    overlay.prg(5, 0x8E10, bytes.fromhex('a1 bd'), bytes.fromhex('e1 8d'), 'Ending text pointer (read)')
    overlay.prg(5, 0x8E60, bytes.fromhex('a1 bd'), bytes.fromhex('e1 8d'), 'Ending text pointer (draw)')
    overlay.prg(5, 0x8E31, b'\x84', b'\xcb', 'Ending text start position ($2184)')
    overlay.prg(5, 0x8E37, b'\x0f', b'\x0a', 'Ending text line width 15 (cmp)')
    overlay.prg(5, 0x8E3C, b'\x0f', b'\x0a', 'Ending text line width 15 (sbc)')
    def encode_credit_pkt(rows: list[tuple[int, int, str]]) -> bytes:
        pkt = bytearray()
        for hi, lo, text in rows:
            pkt.extend([hi, lo, len(text)])
            for ch in text:
                if 'A' <= ch <= 'Z':
                    pkt.append(0xDA + ord(ch) - ord('A'))
                elif ch == ' ':
                    pkt.append(0xF4)
                elif ch == '.':
                    pkt.append(0xCF)
                else:
                    raise ValueError(f'Unsupported credit char {ch!r}')
        pkt.append(0xFF)
        return bytes(pkt)
    credit_entries = [
        [(0x22, 0x47, 'EXECUTIVE PRODUCER')],
        [(0x22, 0x8B, 'H.YAMAUCHI')],
        [(0x22, 0x47, 'PRODUCER          ')],
        [(0x22, 0x8B, 'MIYAHON   ')],
        [(0x22, 0x47, 'DIRECTOR')],
        [(0x22, 0x8B, 'SUGIYAN'), (0x22, 0xCB, 'YAMAHEN')],
        [(0x22, 0x47, 'DESIGNER')],
        [(0x22, 0x8B, 'ISSHIN '), (0x22, 0xCB, '       ')],
        [(0x22, 0x47, 'SOUND COMPOSER')],
        [(0x22, 0x8B, 'TSUKASAN')],
        [(0x22, 0x47, 'PROGRAMER     ')],
        [(0x22, 0x8B, 'MORIKAZU '), (0x22, 0xCB, 'MARUMARU')],
        '__PROG__',
        [(0x22, 0x8B, 'SHIGECHAN'), (0x22, 0xCB, 'NISHIYAN')],
        '__PROG__',
        [(0x22, 0x8B, 'NAKAZOO  '), (0x22, 0xCB, '        ')],
        [(0x22, 0x47, 'BARBA EDITION ')],
        [(0x22, 0x8B, 'JERBTRUNDLES')],
        [(0x22, 0x47, 'LAVA RECLAIMED.  ')],
        [(0x22, 0x8B, 'PUSH START  '), (0x22, 0xCB, 'TO REPLAY')],
    ]
    credit_blob = bytearray()
    credit_ptrs = []
    prog_ptr = None
    data_base = 0x9259 + len(credit_entries) * 2
    for entry in credit_entries:
        if entry == '__PROG__':
            credit_ptrs.append(prog_ptr)
            continue
        addr = data_base + len(credit_blob)
        if entry == [(0x22, 0x47, 'PROGRAMER     ')]:
            prog_ptr = addr
        credit_ptrs.append(addr)
        credit_blob.extend(encode_credit_pkt(entry))
    credit_table = b''.join(p.to_bytes(2, 'little') for p in credit_ptrs) + bytes(credit_blob)
    if len(credit_table) > 0x9400 - 0x9259:
        raise ValueError(f'Ending credits overflow bank 5: {len(credit_table)} bytes')
    expected_credits = source[prg_offset(5, 0x9259):prg_offset(5, 0x9259 + len(credit_table))]
    if source[prg_offset(5, 0x93AE):prg_offset(5, 0x9400)] != b'\xff' * (0x9400 - 0x93AE):
        raise ValueError('Bank 5 ending credits unused area changed')
    overlay.prg(5, 0x9259, credit_table, expected_credits, 'Ending credits with Barba Edition')
    overlay.prg(5, 0x9176, b'\x14', b'\x12', 'Ending credits entry count (20)')
    overlay.prg(5, 0x9197, b'\x12', b'\x10', 'Ending credits clear STAFF header index')

    # Append 128 KB extra CHR-ROM (1 KB banks 128..255) containing 3 horizontally rippled
    # R1 ($0800-$0FFF) variants for each of the 13 side-view CHR pairs (0..24). Only lava
    # surface tiles $98/$99 are shifted per-scanline so bricks/walls stay stationary.
    ext_chr = bytearray(131072)
    def _ror8(val: int, n: int) -> int:
        n &= 7
        return ((val >> n) | (val << (8 - n))) & 0xFF
    for pair_idx in range(13):
        base_off = CHR_OFFSET + (pair_idx * 2 + 1) * 4096 + 2048
        base_r1 = overlay.target[base_off:base_off + 2048]
        for v in (1, 2, 3):
            variant = bytearray(base_r1)
            for t_idx in (0x18, 0x19):
                t_off = t_idx * 16
                for row in range(8):
                    phase = (v + (row >> 1) + (2 if t_idx == 0x19 else 0)) & 3
                    shift = (0, 1, 2, 1)[phase]
                    variant[t_off + row] = _ror8(variant[t_off + row], shift)
                    variant[t_off + 8 + row] = _ror8(variant[t_off + 8 + row], shift)
            ext_off = (pair_idx * 3 + (v - 1)) * 2048
            ext_chr[ext_off:ext_off + 2048] = variant

    # R0 banks 206..213 are the four nonzero wind phases used by
    # UpdateGrassChr6. West Hyrule's sprig tip ($4E) fits within one tile.
    # Taper the bend toward the bottom two rows so it meets the fixed base.
    west_r0_off = CHR_OFFSET + 3 * 4096
    west_r0 = overlay.target[west_r0_off:west_r0_off + 2048]
    for phase, shift in enumerate((1, 2, -1, -2)):
        variant = bytearray(west_r0)
        middle_shift = 1 if shift > 0 else -1
        for plane in (0, 8):
            for row, bend in enumerate((shift, shift, middle_shift, middle_shift), start=2):
                offset = 0x4E * 16 + plane + row
                pixels = variant[offset]
                shifted = pixels >> bend if bend > 0 else pixels << -bend
                if shifted.bit_count() != pixels.bit_count() or shifted > 0xFF:
                    raise ValueError('Sprig wind phase clips the tip tile')
                variant[offset] = shifted
        ext_off = (206 - 128) * 1024 + phase * 2048
        ext_chr[ext_off:ext_off + 2048] = variant
    target = bytes(overlay.target) + bytes(ext_chr)
    for bank, expected in enumerate(fingerprints):
        offset = prg_offset(bank, 0x8506 if bank < 7 else 0xC506)
        if target[offset] != expected:
            raise ValueError(f'Patch overwrote FarCall0 bank fingerprint: {bank}')
    # LateSplit: the source NMI body has exactly three branches into the old tail
    # $C1A8, all retargeted to $C19D; the output must have none left inside $C19E-$C1B5.
    def nmi_branches(rom: bytes, lo: int, hi: int) -> list[tuple[int, int]]:
        found = []
        for a in range(0xC07B, 0xC19D):
            op = rom[prg_offset(7, a)]
            if op in (0x10, 0x30, 0x50, 0x70, 0x90, 0xB0, 0xD0, 0xF0):
                t = a + 2 + ((rom[prg_offset(7, a + 1)] ^ 0x80) - 0x80)
                if lo <= t <= hi:
                    found.append((a, t))
        return found
    if [a for a, _ in nmi_branches(source, 0xC1A8, 0xC1A8)] != [0xC155, 0xC162, 0xC167] \
            or nmi_branches(target, 0xC19E, 0xC1B5) \
            or [t for _, t in nmi_branches(target, 0xC19D, 0xC19D)] != [0xC19D] * 3:
        raise ValueError('NMI tail branch retargeting incomplete (LateSplit)')
    # The FF byte at FF4B is the high operand of a live JMP, not filler.
    # Keep its whole instruction untouched beside the new terrain allocation.
    anchor = prg_offset(7, 0xFF49)
    if source[anchor:anchor+3] != bytes.fromhex('4c c5 ff') or target[anchor:anchor+3] != source[anchor:anchor+3]:
        raise ValueError('Terrain allocation overlaps the native room-loader return')
    if (target[:5] != source[:5] or target[5] != 0x20 or target[6] != 0x42 or target[7:16] != source[7:16]
            or len(target) != len(source) + 131072):
        raise ValueError('Mapper/header/size invariant failed')
    # 8x16 byte T draws tiles T&$FE and T|1: town villager pairs must stay vanilla.
    for bank, pairs in TOWN_SPRITE_PAIRS.items():
        for pair in pairs:
            offset = CHR_OFFSET + bank*4096 + pair*16
            if target[offset:offset+32] != source[offset:offset+32]:
                raise ValueError(f'Patch overwrote town sprite pair CHR {bank:02X}:{pair:02X}')
    # Dialogue glyphs: the box border, font and punctuation the town message box draws
    # must stay vanilla in the town BG bank (only TEXT_GLYPHS are added), and every
    # vanilla message byte must resolve to one of them. 2026-11-16: the town fire art
    # had overwritten '?' ($34) and a shout glyph the mid-dot ($32).
    font = set(range(0xD0, 0xF5)) | {0xCA, 0xCB, 0xCC, 0xCF, 0x34, 0x36}
    for tile in font:
        offset = CHR_OFFSET + TEXT_GLYPH_BANK*4096 + tile*16
        if target[offset:offset+16] != source[offset:offset+16]:
            raise ValueError(f'Patch overwrote dialogue glyph CHR {TEXT_GLYPH_BANK:02X}:{tile:02X}')
    text = target[prg_offset(3, 0xA380):prg_offset(3, 0xAFBE)]
    bad = sorted({b for b in text if b < 0xFD and b not in font | set(TEXT_GLYPHS)})
    if bad:
        raise ValueError('Vanilla dialogue uses glyph bytes outside the guarded font: '
                         + ' '.join(f'{b:02X}' for b in bad))
    patch = encode(source, target, 'Zelda II - Barba Edition | development alpha',
                   [(CHR_OFFSET+30*4096+len(ow), CHR_OFFSET+16*4096+len(ow), 0x60*16-len(ow)),
                    (CHR_OFFSET+30*4096+0x64*16, CHR_OFFSET+16*4096+0x64*16, 8192-0x64*16)])
    if apply(source, patch) != target:
        raise ValueError('BPS patch round-trip failed')
    # Independent post-application source check protects the original file.
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Source ROM changed during build')
    (output/'barba.nes').write_bytes(target)
    (output/'barba.bps').write_bytes(patch)
    if output.resolve() == (ROOT/'build').resolve():
        play_dir = ROOT/'play'
        play_dir.mkdir(exist_ok=True)
        (play_dir/'barba.nes').write_bytes(target)
        (play_dir/'barba.bps').write_bytes(patch)
    report = {'stage': 'development alpha', 'source_sha256': SOURCE_SHA256,
              'output_sha256': hashlib.sha256(target).hexdigest(),
              'size': len(target), 'changed_bytes': sum(a != b for a, b in zip(source, target)),
              'labels': labels, 'patches': sorted(overlay.ranges, key=lambda r: r['offset'])}
    if roar_info:
        report['title_roar_prototype'] = roar_info
    (output/'build-report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, default=ROOT/'roms/z2.nes')
    parser.add_argument('--out', type=Path, default=ROOT/'build')
    parser.add_argument('--title-roar-wav', type=Path, default=ROOT/'roms/roar.wav',
                        help='Local PCM roar WAV (default: roms/roar.wav)')
    parser.add_argument('--native-audio', action='store_true',
                        help='Build the legacy noise roar and five distinct Game Over laughs')
    args = parser.parse_args()
    try:
        report = build(args.rom, args.out, None if args.native_audio else args.title_roar_wav)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Build failed: {error}\n')
    print(f"Built {args.out/'barba.nes'} ({report['changed_bytes']:,} changed bytes)")
    print(f"BPS patch verified; SHA-256 {report['output_sha256']}")
