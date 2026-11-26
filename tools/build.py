"""Build Barba Edition from a verified local ROM, preserving all unpatched bytes."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import shutil
import sqlite3
import subprocess
from pathlib import Path
from assets import (ASH_TILES, CASTLE_FIRE_BANK, CASTLE_FIRE_TILE_SHA256,
                    CASTLE_SHOUT_BANK, CASTLE_SHOUT_PAIR_SHA256,
                    SHOUT_PAIR_SHA256, TOWN_SPRITE_PAIRS,
                    TITLE_CHR_BANK, TITLE_FOREST_EDGE_TILES, TITLE_LAVA_TILES, TITLE_TILE_SHA256,
                    TOWN_FIRE_BANK, TOWN_FIRE_TILE_SHA256,
                    TEXT_GLYPH_BANK, TEXT_GLYPH_SHA256, TEXT_GLYPHS,
                    BREATH_ICON_BANKS, BREATH_ICON_SHA256, BREATH_ICON_TILE,
                    compile_assets, compile_breath_icon, compile_castle_fire, compile_ending_fire,
                    compile_castle_shout_glyphs, compile_file_select_doll, compile_overworld_wyrmling,
                    compile_shout_glyphs, compile_souls_bar_chr, compile_text_glyphs, compile_title_logo,
                    compile_title_shore, compile_town_fire, validate_layout)
from bps import apply, encode
from boss_art import compile_lava_link
from build_history import HISTORY_FILE, git_source, record_build
from game_over_art import (GAME_OVER_CHR_BANK, GAME_OVER_MAP_START,
                           compile_game_over_link)
from nes import CHR_OFFSET, SOURCE_SHA256, decode_tile, encode_tile, load_source, prg_offset
import roar_sample
import game_over_audio

ROOT = Path(__file__).resolve().parents[1]


class Overlay:
    def __init__(self, source: bytes):
        self.source = source
        self.target = bytearray(source)
        self.ranges: list[dict] = []
        self._group: str = 'barba_core'

    @contextlib.contextmanager
    def group(self, name: str):
        prev = self._group
        self._group = name
        try:
            yield
        finally:
            self._group = prev

    def put(self, offset: int, data: bytes, expected: bytes, name: str, *, group: str | None = None) -> None:
        if len(data) != len(expected) or not 0 <= offset <= len(self.source)-len(data):
            raise ValueError(f'Invalid patch length/location: {name}')
        if self.source[offset:offset+len(data)] != expected:
            raise ValueError(f'Original bytes differ at {offset:05X}: {name}')
        for previous in self.ranges:
            if offset < previous['offset']+previous['length'] and previous['offset'] < offset+len(data):
                raise ValueError(f'Overlapping patches: {name} and {previous["name"]}')
        self.target[offset:offset+len(data)] = data
        self.ranges.append({'name': name, 'offset': offset, 'length': len(data),
                            'sha256': hashlib.sha256(data).hexdigest(),
                            'group': group or self._group})

    def prg(self, bank: int, address: int, data: bytes, expected: bytes, name: str, *, group: str | None = None) -> None:
        self.put(prg_offset(bank, address), data, expected, name, group=group)


def assemble(output: Path, sampled_roar: bool = False, waldo_portal: bool = False,
             souls_boss_meter: bool = False) -> dict[str, int]:
    def find(name: str) -> str:
        local = ROOT / f'.tools/cc65/bin/{name}.exe'
        result = str(local) if local.exists() else shutil.which(name)
        if not result:
            raise ValueError(f'{name} is missing. Install cc65; see docs/BUILD.md.')
        return result
    defines = ['-D', 'SAMPLED_ROAR=1'] if sampled_roar else []
    if waldo_portal:
        defines += ['-D', 'WALDO_PORTAL=1']
    if souls_boss_meter:
        defines += ['-D', 'SOULS_BOSS_METER=1']
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


def build(source_path: Path, output: Path, title_roar_wav: Path | None = ROOT/'assets/roar.wav',
          waldo_portal: bool = True, boss_meter: str = 'souls', *,
          game_over_portrait: bool = True, game_over_laughs: bool = True,
          release: str | None = None) -> dict:
    source = load_source(source_path)
    if output.resolve() == source_path.parent.resolve():
        raise ValueError('Output must not be the source ROM directory')
    git_commit, git_dirty = git_source(ROOT)
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
    ending_pal = source[prg_offset(1, 0x800E):prg_offset(1, 0x80EE)].replace(
        bytes.fromhex('18 36 2a'), bytes.fromhex('16 27 30'))
    (output/'ending_pal.bin').write_bytes(ending_pal)
    labels = assemble(output, bool(title_roar_wav), waldo_portal, boss_meter == 'souls')
    overlay = Overlay(source)
    # FarCall0 identifies the ACTUAL mapped bank without touching the native
    # mapper path (and without mistaking the area-bank variable for a shadow).
    fingerprints = bytes.fromhex('f0 7d 60 2e 91 2f 00 c9')
    for bank, expected in enumerate(fingerprints):
        offset = prg_offset(bank, 0x8506 if bank < 7 else 0xC506)
        if source[offset] != expected:
            raise ValueError(f'FarCall0 bank fingerprint changed: {bank}')
    segment_groups = {
        'lava': 'platform', 'terrain': 'platform', 'lag-ret': 'platform', 'gateway': 'platform',
        'bank6': 'platform', 'bank6-pad': 'platform',
        'town': 'town_chaos', 'bank2-smoke': 'town_chaos', 'bank3-sign': 'town_chaos',
        'bank3-pad': 'town_chaos', 'bank3-dlg': 'town_chaos',
        'bank6-cloud': 'scanline_scenery', 'bank6-haze': 'scanline_scenery',
        'bank4-spk': 'scanline_scenery', 'bank4-spk2': 'scanline_scenery',
        'bank4-spk3': 'scanline_scenery', 'bank4-spk4': 'scanline_scenery',
    }
    for filename, bank, address in [('code', 0, 0xAA40), ('bank0-ow', 0, 0xA89E), ('bank0-tail', 0, 0xBFE0),('lava', 7, 0xD39A), ('terrain', 7, 0xFF4C), ('lag-ret', 7, 0xE013), ('town', 3, 0xB803), ('gateway', 7, 0xFEAA), ('bank6', 6, 0xAC09), ('bank6-cloud', 6, 0x8900), ('bank6-pad', 6, 0x8DB0), ('bank6-haze', 6, 0x9DA8), ('bank5', 5, 0xBDE0), ('bank5-splat', 5, 0xBBD5), ('bank1', 1, 0x9EB9), ('bank2-cave', 2, 0x87D3), ('bank2-smoke', 2, 0xA933), ('bank3-sign', 3, 0x9D0A), ('bank3-pad', 3, 0x9134), ('bank3-dlg', 3, 0x8BB1), ('bank4-spk', 4, 0x9EE0), ('bank4-spk2', 4, 0xA539), ('bank4-spk3', 4, 0xA80F), ('bank4-spk4', 4, 0xA7E5), ('bank4-ow', 4, 0x8817), ('bank4-ow2', 4, 0xA3FB), ('bank5-ow', 5, 0xBB15), ('bank2-ow', 2, 0x9FA1), ('bank2-ow2', 2, 0xBF33), ('bank2-ow3', 2, 0x93C9)]:
        data = (output/f'barba-{filename}.bin').read_bytes()
        expected = b'\xFF'*len(data)
        if filename == 'code' and len(data) > 0x1530:
            expected = b'\xFF'*0x1530 + bytes.fromhex('78d8a2008e00')[:len(data)-0x1530]
        elif filename == 'lag-ret':
            expected = bytes.fromhex('85 03 48 20 c5 ff 68 60')[:len(data)]
        overlay.prg(bank, address, data, expected, f'New {filename} routines',
                    group=segment_groups.get(filename, 'barba_core'))
    gear_bin = (output/'barba-bank1-gear.bin').read_bytes()
    if gear_bin:
        overlay.prg(1, 0x87C6, gear_bin, b'\xFF'*len(gear_bin), 'Cosmetic gear menu (Bank 1)')
    pad2_bin = (output/'barba-bank1-pad2.bin').read_bytes()
    if pad2_bin:
        overlay.prg(1, 0x84E7, pad2_bin, b'\xFF'*len(pad2_bin), 'Arcade DoubleXp2 (Bank 1)')
    tail1_bin = (output/'barba-bank1-tail.bin').read_bytes()
    if tail1_bin:
        overlay.prg(1, 0xBFE0, tail1_bin, b'\xFF'*len(tail1_bin), 'Arcade SideViewInit2 (Bank 1)')
    gear2_bin = (output/'barba-bank1-gear2.bin').read_bytes()
    if gear2_bin:
        overlay.prg(1, 0x93BB, gear2_bin, b'\xFF'*len(gear2_bin), 'Cosmetic gear menu init (Bank 1)')
    souls_bin = (output/'barba-bank1-souls.bin').read_bytes()
    if souls_bin:
        overlay.prg(1, 0xA933, souls_bin, b'\xFF'*len(souls_bin), 'Dark Souls bottom boss bar & gear UI (Bank 1)', group='boss_meters')
    scene_oam = (output/'barba-bank6-oam.bin').read_bytes()
    overlay.prg(6, 0x878C, scene_oam, b'\xFF'*len(scene_oam), 'Room sprite priority and boss meters', group='boss_meters')
    palace_roar = (output/'barba-palace-roar.bin').read_bytes()
    overlay.prg(4, 0x8EC3, palace_roar, b'\xFF'*len(palace_roar), 'Palace roar choreography and boss meters')
    bank4_gear = (output/'barba-bank4-gear.bin').read_bytes()
    if bank4_gear:
        overlay.prg(4, 0x83DC, bank4_gear, b'\xFF'*len(bank4_gear), 'Cosmetic gear OAM renderer (Bank 4)')
    palace_shake = (output/'barba-palace-shake.bin').read_bytes()
    overlay.prg(6, 0x87CC, palace_shake, b'\xFF'*len(palace_shake), 'Lava Link entrance camera shake')
    lair_hud_shake = (output/'barba-lair-hud-shake.bin').read_bytes()
    overlay.prg(6, 0xBFE0, lair_hud_shake, b'\xFF'*len(lair_hud_shake), 'Lava Link entrance HUD shake')
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
    def hook(bank: int, address: int, label: str, opcode: int, expected: str, pad: int = 0, *, group: str | None = None):
        dest = labels[label]
        data = bytes([opcode, dest & 255, dest >> 8]) + b'\xEA'*pad
        overlay.prg(bank, address, data, bytes.fromhex(expected), label+' hook', group=group)
    hook(0, 0x877C, 'BarbaOverworld', 0x20, 'a2 0e a0 00', 1)
    hook(4, 0x9B47, 'RoarGemEnd', 0x4C, 'ac fb 07')
    hook(4, 0xB122, 'LavaLinkIntro', 0x20, '20 de b1')
    hook(0, 0x8518, 'BarbaOverworldA', 0x4C, 'ad 89 07')
    hook(0, 0x922A, 'ThunderHit', 0x20, '20 26 e7')
    splat5 = labels['GiantBotSplat5']
    overlay.prg(5, 0xA180, bytes([0x20, splat5 & 255, splat5 >> 8, 0xB0, 0x45, 0xA0, 0x05, 0xEA]),
                bytes.fromhex('b5 c2 c9 30 b0 44 a0 05'), 'GiantBotSplat5 hook (preserving $A188)')
    hook(7, 0xD52D, 'BarbaDisplay', 0x20, '20 f0 eb')
    hook(0, 0x91A1, 'BarbaDisplay', 0x4C, '4c f0 eb')
    hook(0, 0x92DE, 'BarbaDisplay', 0x4C, '4c f0 eb')
    death_draw = labels['BarbaDisplay'].to_bytes(2, 'little')
    overlay.prg(7, 0xC9EE, bytes.fromhex('20 c5 ff a9 0a 85 80 20') + death_draw,
                bytes.fromhex('20 c5 ff a9 0a 85 80 20 f0 eb'), 'Fatal-hit transition renderer')
    lives_text = labels['BarbaLivesText'].to_bytes(2, 'little')
    overlay.prg(7, 0xC3BE, bytes.fromhex('a9 01 20 cc ff 20') + lives_text + bytes.fromhex('4c dd c3'),
                bytes.fromhex('a0 13 b9 58 69 99 02 03 88 10 f7'),
                'Lives-remaining screen tightly wrapped text around Barba midsection')
    lives_draw = labels['BarbaLivesDisplay'].to_bytes(2, 'little')
    overlay.prg(7, 0xC405, bytes.fromhex('a9 03 20 cc ff 4c') + lives_draw + b'\xea\xea\xea',
                bytes.fromhex('85 c8 85 13 85 11 85 90 4c 02 ec'),
                'Lives-remaining screen full Barba renderer')
    overlay.prg(0, 0x8FC9, b'\xa9\x09', b'\xa9\x0a', 'Fall-in-hole downstab pose ($09)')
    overlay.prg(0, 0x8FD3, b'\xa9\x3c', b'\xa9\x30', 'Fall shadow OAM starts after the full player pose')
    hook(0, 0x8FE3, 'BarbaFallDraw', 0x20, '20 02 ec')
    hook(0, 0x8FEE, 'BarbaFallDraw', 0x20, '20 02 ec')
    hook(7, 0xE0A4, 'LavaSurface', 0x4C, 'a9 01 85')
    hook(7, 0xD4F3, 'LavaLinkPlayerUpdate', 0x20, '20 3a 90')
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
    overlay.prg(7, 0xD458, b'\x20' + labels['FarCall0'].to_bytes(2, 'little')
                + labels['ArcadeDoubleXp0'].to_bytes(2, 'little') + b'\xea',
                bytes.fromhex('ad 76 07 18 65 00'), 'DOUBLE spell 2x XP hook')
    overlay.prg(7, 0xE899, b'\x20' + labels['FarCall0'].to_bytes(2, 'little')
                + labels['ArcadeLuckyDrop0'].to_bytes(2, 'little') + b'\xea',
                bytes.fromhex('fe de 05 bd de 05'), 'LUCKY spell forced drop hook')
    overlay.prg(7, 0xE731, b'\x20' + labels['FarCall0'].to_bytes(2, 'little')
                + labels['ArcadeHeavyDmg0'].to_bytes(2, 'little') + b'\xea',
                bytes.fromhex('38 f9 6c e6 95 c2'), 'HEAVY spell 2x damage hook')
    hook(7, 0xE48B, 'EnemyFireGateway', 0x4C, 'b5 b6 c9 01', 1)
    hook(7, 0xE617, 'ShieldFireGateway', 0x4C, 'a5 c8 0a')
    hook(7, 0xE646, 'ShieldReboundImpact', 0x20, '20 e8 e6')
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
                bytes.fromhex('a9 06 20 cc ff 20 00'), 'Lag-frame NMI bank preservation', group='platform')
    # MMC3 (Mapper 4) port: preserve $C000-$FFFF fixed (PRG mode 0), map $8000/$A000
    # in 8KB pairs, map CHR in 1KB/2KB units (BG at $0000 via R0/R1, Sprites at $1000
    # via R2-R5 so MMC3 A12 clocks on every scanline), and keep $8000 bank-select
    # NMI-safe via $64D5 shadow + LagNmiBank6 save/restore.
    overlay.put(5, b'\x20', b'\x10', 'Expand CHR-ROM to 256 KB (32 x 8KB banks)', group='platform')
    overlay.put(6, b'\x42', b'\x12', 'iNES mapper 4 (MMC3)', group='platform')
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
    # Overworld RLE map rows ($6000/$6001) live in WRAM ($7C00-$7FFF); skip
    # the redundant SwapToSavedPRG / SwapToPRG0 pair per RLE run in LE001.
    overlay.prg(7, 0xE001, bytes.fromhex('b1 0e 29 0f 85 02 b1 0e 4a 4a 4a 4a 38 65 03 85 03 60'),
                bytes.fromhex('20 c9 ff b1 0e 29 0f 85 02 b1 0e 4a 4a 4a 4a 38 65 03'),
                'Skip redundant PRG bank swaps in overworld RLE decode ($E001)', group='platform')
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
    # Both former clear entries now clear all 64 Y bytes. Starting Y at $80
    # lets the two stores cover opposite halves and wrap to Y=0 after 32
    # iterations. This keeps X, A=$F8 and flags as on the old return.
    overlay.prg(7, 0xD24C, bytes.fromhex('a0 80 a9 f8 99 80 01 99 00 02 c8 c8 c8 c8 d0 f4 60 ea'),
                bytes.fromhex('a0 00 f0 02 a0 04 a9 f8 99 00 02 c8 c8 c8 c8 d0 f7 60'),
                'Two-way unrolled native OAM Y clear')
    overlay.prg(7, 0xC212, bytes.fromhex('20 4c d2'), bytes.fromhex('20 50 d2'),
                'Pause pane calls the relocated OAM clear entry')
    overlay.prg(5, 0xA7A8, bytes.fromhex('20 4c d2'), bytes.fromhex('20 50 d2'),
                'Title calls the relocated OAM clear entry')
    title_hook5 = labels['TitleEndHook5']
    overlay.prg(5, 0xA693, b'\x20' + title_hook5.to_bytes(2, 'little'),
                bytes.fromhex('ad 02 20'), 'Title NMI end -> OAM shadow + IRQ setup')
    # Title lava shimmer: the vanilla $FF pad at $A5E8 holds a stub that runs
    # TitleLavaChr6 (bank 6) in VBlank, then the native sound call $C032.
    lava_stub = (bytes.fromhex('20 ee a5 4c 32 c0 a9') + bytes([(labels['TitleLavaChr6'] - 1) >> 8])
                 + bytes.fromhex('48 a9') + bytes([(labels['TitleLavaChr6'] - 1) & 0xFF])
                 + bytes.fromhex('48 4c') + labels['SwapToBank6'].to_bytes(2, 'little'))
    overlay.prg(5, 0xA5E8, lava_stub, b'\xff' * len(lava_stub), 'Title lava shimmer stub (bank 5 pad)')
    overlay.prg(5, 0xA682, bytes.fromhex('20 e8 a5'), bytes.fromhex('20 32 c0'),
                'Title NMI: lava shimmer CHR swap before the sound driver')
    # NMI prologue: clean without LateSplit trampoline.
    overlay.prg(7, 0xC091, bytes.fromhex('a0 00 a5 fe 29 e0 ac 26 07 d0 07 a5 fe 09 18 0d 68 07 ea ea ea ea ea'),
                bytes.fromhex('ad 27 07 f0 00 a0 00 a5 fe 29 e0 ac 26 07 d0 07 a5 fe 09 18 0d 68 07'),
                'NMI prologue compaction (no LateSplit)')
    # Replace $0725 macro clear + sound call ($C108-$C131) with Bank 6 NmiVblankSetup6,
    # freeing $C110-$C131 for IrqHandler2. Setup returns through SwapToPRG0
    # with A = 1 (the odd PRG bank number), so BNE always skips the handler.
    # Skip the mask helper on normal splits so the next MMC3 reload reaches
    # $C001 before the A12 edge at dot 260, even during a DMC fetch.
    swap_b6 = labels['SwapToBank6']
    nmi_setup6 = labels['NmiVblankSetup6']
    copy_oam6 = labels['CopySceneOam6']
    nmi_rng6 = labels['NmiRng6']
    overlay.prg(7, 0xC108,
                b'\x20' + swap_b6.to_bytes(2, 'little')
                + b'\x20' + nmi_setup6.to_bytes(2, 'little')
                + bytes.fromhex('d0 22')
                + bytes.fromhex('8d 05 20 bd e4 64 c5 fe d0 74 e8 ec d7 64 b0 0f 8e d6 64 bd d8 64 8d 00 c0 8d 01 c0 8d 01 e0 4c 99 ff'),
                bytes.fromhex(
                    'ae 25 07 f0 0f c8 e0 01 f0 07 c8 a9 00 e0 02 d0 13 ce 25 07 be 5d c0 a9 00 9d 01 03 a9 ff 9d 02 03 ad 25 07 8d 25 07 20 c1 c1'),
                'NMI VBlank Bank 6 setup + CLI + IrqHandler2 ($C110)')
    # The three early-outs that branch to the NMI tail, which moves $C1A8 -> $C19D (or $C19F with Souls bar).
    if boss_meter == 'souls':
        overlay.prg(7, 0xC156, bytes([0x48]), bytes([0x51]), 'NMI tail branch (dialogue)')
        overlay.prg(7, 0xC163, bytes([0x3b]), bytes([0x44]), 'NMI tail branch (talking)')
        overlay.prg(7, 0xC168, bytes([0x36]), bytes([0x3F]), 'NMI tail branch (routine)')
        if waldo_portal or not title_roar_wav:
            souls_irq_addr = 0xFC90
            souls_irq_split = bytes.fromhex(
                '98 48 '                         # TYA / PHA (preserve Y across IRQ)
                'a9 0b 38 e9 01 d0 fb '          # wait ~80 cycles to HBlank of scanline 213
                '2c 02 20 '                      # bit $2002
                'ae 5d 63 d0 18 '                # ldx SOULS_BG_VALID / bne +24
                'a9 00 8d 01 20 '                # frame 1 only: blank to read $3F00
                'a9 3f 8d 06 20 a9 00 8d 06 20 ' # PPUADDR = $3F00
                'ad 07 20 8d 5b 63 ee 5d 63 '    # read $3F00 -> SOULS_SAVED_BG, SOULS_BG_VALID = 1
                'a0 3f a2 0f a9 00 '             # Y=$3F, X=$0F, A=$00
                '8d 01 20 '                      # $2001 = $00 at start of HBlank (dot ~270)
                '8c 06 20 8d 06 20 '             # PPUADDR = $3F00 (8 cyc)
                '8e 07 20 '                      # [$3F00] = $0F black (12 cyc)
                'a2 04 8e 06 20 8d 06 20 '       # PPUADDR = $0400 (22 cyc, still in HBlank!)
                'a9 01 8d 5c 63 '                # SOULS_BG_DIRTY = 1
                'a9 01 8d 00 80 a9 9c 8d 01 80 ' # R1 = 156 (Souls CHR) while rendering is off
                'ad d5 64 8d 00 80 '             # restore MMC3 $8000 shadow
                'a9 18 38 e9 01 d0 fb '          # wait ~170 cycles to HBlank of scanline 215 (dot ~290)
                '68 a8 '                         # PLA / TAY
                'a9 0e 4c 99 c1'                 # $2001 = $0E (BG on, sprites off) -> $C199
            )
            souls_irq_off = prg_offset(7, souls_irq_addr)
            overlay.prg(7, souls_irq_addr, souls_irq_split, source[souls_irq_off:souls_irq_off+len(souls_irq_split)],
                        'Dark Souls bottom boss bar IRQ split ($FC90)', group='boss_meters')
        else:
            # Sampled no-portal builds pack the roar and 4 compact laughs into $F400-$FD70,
            # so place the Souls split across the free displaced-laugh pockets ($F3E0, $FCF1, $FD71).
            souls_irq_addr = 0xF3E0
            souls_irq_parts = [
                (0xF3E0, bytes.fromhex(
                    'a9 00 8d 01 20 '                # blank scanline 214 immediately in HBlank of 213
                    'a9 01 8d 00 80 a9 9c 8d 01 80 ' # R1 = 156 (Souls CHR) while rendering is off
                    'ad d5 64 8d 00 80 '             # restore MMC3 $8000 shadow
                    '2c 02 20 a9 04 8d 06 20 '       # PPUADDR high byte = $04
                    '4c f1 fc'                       # JMP $FCF1
                ), 'Dark Souls bottom boss bar IRQ split part 1 ($F3E0)'),
                (0xFCF1, bytes.fromhex(
                    'a9 00 8d 06 20 '                # PPUADDR low byte = $00 ($0400)
                    'a9 08 38 e9 01 d0 fb '          # wait ~62 cycles to HBlank of scanline 214
                    '4c 71 fd'                       # JMP $FD71
                ), 'Dark Souls bottom boss bar IRQ split part 2 ($FCF1)'),
                (0xFD71, bytes.fromhex(
                    'a9 0e 4c 99 c1'                 # $2001 = $0E (BG on, sprites off) -> $C199
                ), 'Dark Souls bottom boss bar IRQ split part 3 ($FD71)'),
            ]
            for part_addr, part_bytes, part_name in souls_irq_parts:
                part_off = prg_offset(7, part_addr)
                overlay.prg(7, part_addr, part_bytes, source[part_off:part_off+len(part_bytes)], part_name, group='boss_meters')
        nmi_tail_bytes = (
            bytes.fromhex('20 4c d2 20 ca c2')
            + b'\x20' + swap_b6.to_bytes(2, 'little')
            + b'\x4c' + nmi_rng6.to_bytes(2, 'little')
            + bytes.fromhex('48 a9 7f 4a d0 fd 68 4a b0 1b 2a 8d 01 20 4c 1a c1')
            + b'\x20' + swap_b6.to_bytes(2, 'little')
            + b'\x20' + copy_oam6.to_bytes(2, 'little')
            + bytes.fromhex('20 c5 ff')
            + bytes.fromhex('a5 ff 09 80 85 ff 8d 00 20 68 40')
            + b'\x4c' + souls_irq_addr.to_bytes(2, 'little')
        )
        nmi_rti = 0xC182 + len(nmi_tail_bytes) - 4
    else:
        overlay.prg(7, 0xC156, bytes([0x46]), bytes([0x51]), 'NMI tail branch (dialogue)')
        overlay.prg(7, 0xC163, bytes([0x39]), bytes([0x44]), 'NMI tail branch (talking)')
        overlay.prg(7, 0xC168, bytes([0x34]), bytes([0x3F]), 'NMI tail branch (routine)')
        nmi_tail_bytes = (
            bytes.fromhex('20 4c d2 20 ca c2')
            + b'\x20' + swap_b6.to_bytes(2, 'little')
            + b'\x4c' + nmi_rng6.to_bytes(2, 'little')
            + bytes.fromhex('ea ea 48 a9 7f 4a d0 fd 68 8d 01 20 4c 1a c1')
            + b'\x20' + swap_b6.to_bytes(2, 'little')
            + b'\x20' + copy_oam6.to_bytes(2, 'little')
            + bytes.fromhex('20 c5 ff ea ea ea ea ea a5 ff 09 80 85 ff 8d 00 20 68 40')
        )
        nmi_rti = 0xC182 + len(nmi_tail_bytes) - 1
    assert nmi_tail_bytes[nmi_rti - 0xC182] == 0x40
    nmi_work_end = 0xC182 + nmi_tail_bytes.index(b'\x20' + copy_oam6.to_bytes(2, 'little'))
    labels['NmiWorkEnd'] = nmi_work_end
    labels['NmiRti'] = nmi_rti
    with (output / 'barba.lbl').open('a', encoding='utf-8') as lbl_file:
        lbl_file.write(f'al {nmi_work_end:06X} .NmiWorkEnd\n')
        lbl_file.write(f'al {nmi_rti:06X} .NmiRti\n')
    # RNG moved to Bank 6 (NmiRng6); $C18E-$C19C holds MaskWrite (HBlank-aligned $2001 write when != $FE).
    overlay.prg(7, 0xC182,
        nmi_tail_bytes,
        bytes.fromhex('ee 12 00 a2 00 a0 09 ad 1a 05 29 02 85 00 ad 1b 05 29 02 45 00 18 f0 01 38 7e 1a 05'
                      'e8 88 d0 f9 20 50 d2 20 ca c2 ad 02 20 a5 ff 09 80 85 ff 8d 00 20 68 40'),
        'NMI RNG -> Bank 6, MaskWrite ($C18E), and OAM shadow copy tail')
    # Replace Sprite-0 busy-wait ($D4AB-$D4CD) with IrqHandler ($D4AE-$D4CD).
    overlay.prg(7, 0xD47A, bytes.fromhex('f0 52'), bytes.fromhex('f0 2f'), 'Retarget $D47A BEQ to $D4CE')
    overlay.prg(7, 0xD485, bytes.fromhex('f0 47'), bytes.fromhex('f0 24'), 'Retarget $D485 BEQ to $D4CE')
    overlay.prg(7, 0xD4AB, bytes.fromhex(
        '4c ce d4'
        '48 8a 48 8d 00 e0 ae d6 64 a5 ff 29 fc 1d e0 64 85 ff 8d 00 20 2c 02 20 bd dc 64 4c 10 c1 ea ea'),
        bytes.fromhex(
            'ad 4c 07 c9 02 b0 1c 2c 02 20 50 fb a5 ff 0d 46 07 85 ff a6 fd a0 10 88 d0 fd 8d 00 20 8e 05 20 8c 05 20'),
        'Replace Sprite-0 wait with MMC3 IrqHandler ($D4AE)')
    # Eliminate the remaining side-view Sprite-0 busy-waits in banks 0 and 3 (menus/towns/castle);
    # the scanline-31 IRQ already performs the HUD split cleanly.
    overlay.prg(0, 0x9D54, bytes.fromhex('4c 75 9d'), bytes.fromhex('a0 50 88'), 'Skip Level-Up/Pause Sprite-0 wait ($9D54)')
    overlay.prg(0, 0x9DB0, bytes.fromhex('4c cc 9d'), bytes.fromhex('2c 02 20'), 'Skip Pause Sprite-0 wait ($9DB0)')
    overlay.prg(0, 0xA7B1, bytes.fromhex('4c cd a7'), bytes.fromhex('2c 02 20'), 'Skip Castle Sprite-0 wait ($A7B1)')
    overlay.prg(3, 0xB089, bytes.fromhex('4c ab b0'), bytes.fromhex('a0 f0 ea'), 'Skip Town Sprite-0 delay and wait ($B089)')
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
    # $F24F is the sole caller and always clips two columns. Its preceding
    # stores already use $0200,Y/$0204,Y, with a two-sprite OAM row in page 2.
    # Test those exact mask bits directly. Y already equals $09 and $0A
    # still gets the old loop's final value before X is restored from $08.
    overlay.prg(7, 0xF1D7, bytes.fromhex(
        'a9 02 85 0a'
        ' a5 c9 29 08 f0 05 a9 f8 99 00 02'
        ' a5 c9 29 04 f0 05 a9 f8 99 04 02'
        ' a6 08 60'),
        bytes.fromhex('a9 08 85 0a a5 0a 25 c9 f0 05 a9 f8 99 00 02 c8 c8 c8 c8 46 0a ca d0 ec a6 08 a4 09 60'),
        'Unroll the native two-column OAM clip')
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
    hook(3, 0xB5F8, 'TownDialog', 0x4C, '0a a8 ad 07 07', 2, group='town_chaos')
    if waldo_portal:
        hook(3, 0xB480, 'WaldoDialogCheck', 0x4C, 'a9 00 85 05 8d 8c 04', 4, group='crossover_portals')
        hat_hop = (output / 'barba-waldo-hat-1.bin').read_bytes()
        overlay.prg(6, 0x8F66, hat_hop, b'\xff' * len(hat_hop), 'Bank 6 Waldo hat CHR far-call hop', group='crossover_portals')
        arcade_addr = labels['BarbaArcadeArea']
        overlay.prg(3, 0x855B, arcade_addr.to_bytes(2, 'little'), b'\xc2\x9c',
                    "Barba's Arcade room $1C area pointer", group='crossover_portals')
        overlay.prg(3, 0x85D9, (0x73E0).to_bytes(2, 'little'), b'\x7b\x70',
                    "Barba's Arcade room $1C enemy pointer", group='crossover_portals')
        overlay.prg(3, 0x881C, b'\x70', b'\x71',
                    "Rauru $01 page 1 enters Barba's Arcade page 0", group='crossover_portals')
        overlay.prg(3, 0x878B, b'\x05', b'\x00',
                    "Barba's Arcade page 0 left exit returns to Rauru $01", group='crossover_portals')
        overlay.prg(3, 0x878E, b'\x05', b'\x09',
                    "Barba's Arcade page 3 right exit returns to Rauru $01", group='crossover_portals')
    hook(3, 0xB0D2, 'DlgDrawRows', 0x4C, 'ad 25 05', group='town_chaos')
    hook(3, 0xB183, 'DlgEraseRow', 0x4C, 'ce 25 05', group='town_chaos')
    hook(3, 0xB350, 'DlgSaveAttr', 0x4C, 'ad 2c 07', group='town_chaos')
    overlay.prg(3, 0xB706, b'\x68', b'\x88', 'Dialog text base X offset (4 tiles wider)')
    overlay.prg(3, 0xB725, b'\xa0', b'\xe0', 'Dialog text base Y offset (2 tiles higher)')
    overlay.prg(3, 0xB615, b'\x0a', b'\x2a', 'Standardized dialogue initial delay (10f)')
    overlay.prg(3, 0xB74E, b'\x02', b'\x05', 'Standardized dialogue letter delay (2f)')
    overlay.prg(3, 0xB657, b'\x05', b'\x0b', 'Standardized dialogue newline delay (5f)')
    overlay.prg(3, 0xB65D, b'\x18', b'\x2d', 'Standardized dialogue pause delay (24f)')
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
    hook(3, 0x9950, 'TownDoorRender', 0x4C, 'a5 c9 29 0c c9 0c d0 02 a2 0c', 7)
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
    # In-place town dialogue replacements with a blank tile at each border.
    town_glyphs = {chr(ord('A') + i): 0xDA + i for i in range(26)}
    town_glyphs.update({' ': 0xF4, '.': 0xCF, '!': 0x36, '\n': 0xFD})
    for address, name, original, dialogue in (
        (0xA99E, 'Mido downstab', 'WHEN YOU\nJUMP PRESS\nDOWNWARD\nTO STAB.',
         'JUMP. HOLD\nDOWN FOR A\nWYRM DIVE.'),
        (0xADBF, 'Darunia upstab', 'WHEN YOU\nJUMP PRESS\nUP TO STAB.',
         'JUMP. HOLD\nUP TO RAM\nHEADFIRST.'),
        (0xA656, 'Saria mirror lady', 'OH! YOU\nFOUND MY\nMIRROR!\nFOLLOW ME.',
         'OH MY GOD!\nMY MIRROR!\nFOLLOW ME.'),
        (0xA7FE, 'Saria bridge guard', 'ONLY TOWN\nFOLK MAY\nCROSS THIS\nRIVER!',
         'FOUL WATER!\nLOCALS\nONLY.'),
        (0xA9C4, 'Bagu note', 'BAGU IS MY\nNAME. SHOW\nMY NOTE TO\nRIVER MAN.',
         'BAGU IS MY\nNAME. SHOW\nMY NOTE TO\nTHE GUARD.'),
        (0xA9F7, 'Bagu location', 'LET ME BE!\nMASTER IS\nIN WOODS\nN OF RIVER',
         'LET ME BE!\nMASTER IS\nIN WOODS\nN OF SARIA'),
    ):
        expected = bytes(town_glyphs[ch] for ch in original) + b'\xff'
        replacement = bytes(town_glyphs[ch] for ch in dialogue) + b'\xff'
        lines = dialogue.splitlines()
        if (len(replacement) > len(expected) or len(lines) > len(original.splitlines())
                or any(len(line) > 14 for line in lines)):
            raise ValueError(f'{name} exceeds its dialogue space')
        overlay.prg(3, address, replacement.ljust(len(expected), b'\xff'), expected, name + ' dialogue')
    overlay.prg(3, 0xAFF8, labels['SariaSignText'].to_bytes(2, 'little'), b'\x1d\xa7',
                'Saria sign dialogue pointer')
    # These runs are the connected water tiles through Saria, rows $58-$60.
    # West Hyrule renders terrain $0A with green palette 0 (via OwTerrainPal0)
    # and reports unwalkable water, keeping the town crossing required.
    for address, runs in (
        (0x92D4, '7c'), (0x92E0, '7c'), (0x92E3, 'fc 0c'), (0x92EE, 'fc bc'),
        (0x92F9, '3c'), (0x92FB, 'fc'), (0x9305, 'bc'), (0x930E, 'ac'),
        (0x9317, 'ac'), (0x9320, '9c'), (0x932B, '8c'),
    ):
        expected = bytes.fromhex(runs)
        overlay.prg(1, address, bytes((run & 0xF0) | 0x0A for run in expected), expected,
                    'West Hyrule map: Saria foul water river')
    hook(1, 0x83FE, 'WestFoulWaterTerrain1', 0x4C, 'b0 08 c8 4c eb 83', 3)
    for address in (0x8AA8, 0x8AB1, 0x8ABA, 0x8AC3, 0x8BB3, 0x8BBC, 0x8BC6, 0x8BCF):
        hook(0, address, 'OwTerrainPal0', 0x20, 'bd e3 87')
    # Town liquid uses a palette-1 alias of $92. Keep the native streaming
    # renderer and collision path in agreement, including the initial draw.
    town_palette1 = prg_offset(3, 0x86A2)
    palette1_tiles = source[town_palette1:town_palette1+0xFC]
    overlay.prg(3, 0x9300, palette1_tiles + bytes.fromhex('98 99 98 99'), b'\xff' * 256,
                'Town palette-1 metatile table with foul water at $7F')
    overlay.prg(3, 0x8502, b'\x00\x93', b'\xa2\x86', 'Town palette-1 metatile table pointer')
    for address in (0x832A, 0x8363, 0x8520):
        overlay.prg(3, address, b'\x7f', b'\x92', 'Town foul water metatile')
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
    # AXE Arcade spell: reuse Daira's diagonal spinning axe ($FA in CHR bank 2) at
    # $7E in non-town side-view banks ($7E is ash in towns) and $FE in town bank 6.
    daira_axe = source[CHR_OFFSET + 2 * 4096 + 0xFA * 16:CHR_OFFSET + 2 * 4096 + 0xFA * 16 + 32]
    for bank, tile in [(b, 0x7E) for b in (0, 2, 4, 8, 10, 12, 16, 18, 20, 22, 24)] + [(6, 0xFE)]:
        axe_off = CHR_OFFSET + bank * 4096 + tile * 16
        overlay.put(axe_off, daira_axe, source[axe_off:axe_off + 32],
                    f'CHR {bank:02X}: Daira spinning axe at ${tile:02X}')
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
    # Dark cave fireball glow halo in CHR 00 ($86/$87, replacing unused Link sword beam).
    cave_glow_top = encode_tile([
        '00000000',
        '01000010',
        '00101000',
        '01022010',
        '10233201',
        '02333320',
        '12333321',
        '23333332',
    ])
    cave_glow_bot = encode_tile([
        '23333332',
        '12333321',
        '02333320',
        '10233201',
        '01022010',
        '00101001',
        '01000000',
        '00000000',
    ])
    glow_off = CHR_OFFSET + 0x86 * 16
    overlay.put(glow_off, cave_glow_top + cave_glow_bot, source[glow_off:glow_off + 32],
                'CHR 00: dark cave fireball rounded glow halo ($86/$87)')
    # Ending ash tiles ($5E/$62 in CHR 0E only; $62 is Geldarm's head in overworld banks).
    for dst_tile, src_tile in ((0x5E, ASH_TILES[0]), (0x62, ASH_TILES[1])):
        ash_off = CHR_OFFSET + 14*4096 + dst_tile*16
        overlay.put(ash_off, graphics[src_tile], source[ash_off:ash_off+32], f'CHR 0E: ending ash tile {dst_tile:02X}')
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
        bytes.fromhex('23 f0 08 00 00 00 00 00 00 00 44') +
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
    # Palette 3 shares two lava colors with palette 2. The title's black
    # sprite-zero target moves to palette 1, where index 2 is opaque black.
    overlay.prg(
        5, 0xAF48,
        bytes.fromhex('0f0616270f270a160f3016060f2b0f000f1627300f0f1627'),
        bytes.fromhex('0f0112210f0f0a120f3012020f2b0f000f1626300f0f1921'),
        'Title screen lava and Barba palette',
    )
    # $AD6B/$AD73/$AD7B: the story's three-row attribute table ($AD64, read at $ADA9).
    for address in (0xAB0A, 0xAB12, 0xAD6B, 0xAD73, 0xAD7B, 0xAF83, 0xAFA9, *range(0xB031, 0xB04A, 4)):
        overlay.prg(5, address, b'\x44', b'\xcc', 'Title opaque right border uses cliff palette')
    title_border = 0x67  # a former LINK-logo tile unused by BARBA
    title_r0_off = CHR_OFFSET + TITLE_CHR_BANK * 4096
    border_offset = title_r0_off + title_border * 16
    original = source[border_offset:border_offset + 16]
    if hashlib.sha256(original).hexdigest()[:16] != TITLE_TILE_SHA256[title_border]:
        raise ValueError('Title opaque border tile is not the audited logo tile')
    overlay.put(border_offset, encode_tile(['22222222'] * 8), original, 'CHR 01: opaque title border')
    # $AAC7/$AAE4 end the two blank story rows ($AAAB/$AAC8, story pointers 13 and 14).
    for address in (0xAAC7, 0xAAE4, 0xAC30, 0xAF64, 0xAF68, 0xAF78, 0xAF9E, 0xAFC5):
        overlay.prg(5, address, bytes([title_border]), b'\xfd', 'Title opaque right border tile')
    title_water = source[title_r0_off + 0x6A0:title_r0_off + 0x6B0]
    for tile in range(0x6B, 0x71):
        offset = title_r0_off + tile * 16
        original = source[offset:offset + 16]
        overlay.put(offset, compile_title_shore(tile, original, title_water), original,
                    f'CHR 01: title forest tile {tile:02X}')
    # Top lava-line row ($2A00..$2A1B): use dedicated wave tiles $5A-$5D (variants of $68/$69)
    # so only row 5 (scanline 144) gets a subtle 1px undulating wave, and extend the lava
    # across cols 26-27 (under the trimmed cliff columns X=214/222) while keeping the cliff
    # below ($2A5A-$2A5B) and the remaining right cliff column (X=224+).
    overlay.prg(5, 0xB04D, b'\x5a\x5b' * 6 + b'\x5c\x5d' * 4 + b'\x5a\x5b' * 3 + b'\x5c\x5d',
                b'\x68' * 12 + b'\x69' * 8 + b'\x68' * 6 + b'\x71\x7a',
                'Title lava top-row wave tiles')
    overlay.prg(5, 0xB08A, b'\x6a\x68', b'\x77\x76', 'Title lava row 17 cols 26-27 under trimmed cliff')
    overlay.prg(5, 0xB21A, b'\x7a', b'\x76', 'Title lava attribute for rows 16-17 cols 26-27')
    for tid, base_tid in ((0x5A, 0x68), (0x5B, 0x68), (0x5C, 0x69), (0x5D, 0x69)):
        offset = title_r0_off + tid * 16
        original = source[offset:offset + 16]
        if hashlib.sha256(original).hexdigest()[:16] != TITLE_TILE_SHA256[tid]:
            raise ValueError(f'Title wave tile {tid:02X} is not the audited logo tile')
        base_bytes = bytearray(source[title_r0_off + base_tid * 16:title_r0_off + base_tid * 16 + 16])
        mask = 0xFC if (tid & 1) == 0 else 0x7F
        base_bytes[5] &= mask
        base_bytes[13] &= mask
        overlay.put(offset, bytes(base_bytes), original, f'CHR 01: title wave tile {tid:02X}')

    # Restore the three original head columns. Inset the cliff's outer edge
    # by one tile so all five cliff and three head sprites fit on the same line.
    overlay.prg(5, 0xA7DD, bytes.fromhex('7f0002747f02027c'), bytes.fromhex('6ff802786ffa0280'), 'Title Barba head left/mid')
    overlay.prg(5, 0xA7FD, bytes.fromhex('7f0402848f06027c'), bytes.fromhex('7ffc02787ffe0280'), 'Title Barba head right/neck')
    # Use the two hidden cliff bevel entries for the outer torso and near tip.
    # Both now start below the cliff's upper rows and the title split.
    overlay.prg(5, 0xA7E5, bytes.fromhex('9f3e0294'), bytes.fromhex('6fee01d0'), 'Title Barba outer torso')
    overlay.prg(5, 0xA805, bytes.fromhex('9f44029c'), bytes.fromhex('7ff001d0'), 'Title Barba near tip')
    # Trim the two inner cliff columns at Y=$6F/$7F (X=214, X=222) so scanlines 128-143
    # have 6 static sprites (3 Barba head + 3 cliff) and 2 free slots for lava particles.
    overlay.prg(5, 0xA7E9, b'\xf8', b'\x6f', 'Hide title cliff col X=214 (Y=$6F)')
    overlay.prg(5, 0xA7ED, b'\xf8', b'\x6f', 'Hide title cliff col X=222 (Y=$6F)')
    overlay.prg(5, 0xA809, b'\xf8', b'\x7f', 'Hide title cliff col X=214 (Y=$7F)')
    overlay.prg(5, 0xA80D, b'\xf8', b'\x7f', 'Hide title cliff col X=222 (Y=$7F)')
    overlay.prg(5, 0xA819, bytes.fromhex('8f0802849f14028c9f34027c9f360284'), bytes.fromhex('8fea02788fec02809fea02789fec0280'), 'Title Barba neck, elbow and near torso')
    # The vanilla sword glint (OAM $F8, Y $78 X $95) now floats in the sky beside Barba's head and
    # reads as a star. Draw it behind the background like the other stars so the story text covers
    # it. The glint cycler keeps bit 5 (AND #$23); the other glints start at attr $00-$03 and stay in front.
    overlay.prg(5, 0xA8BB, b'\x22', b'\x02', 'Title sky glint behind background')
    overlay.prg(5, 0xA927, b'\x23', b'\x03', 'Title glint cycler keeps priority bit')
    # Title/story scroll split. After the sprite-0 hit (line 128), the native code wrote $2006
    # mid-line on scanline 143 (dots 184-227; the upper end comes from up to two rate-9 DMC roar
    # fetches) and read $2007 twice to step fine Y. Vanilla hid the moving seam under the lower
    # outer-bevel sprite at x 208, which the head now displaces ($A805), so tile column 26
    # flickered between sky and lava. Preload t with $2006/$2005/$2005 and make the final $2006
    # write in HBlank (dots ~265-308 of 143, inside 254-317): line 143 stays sky and line 144 starts
    # on the same row/fine Y 5 the $2007 reads reached. $28 is always 0 and $27 cycles
    # $2A/$20/$22/$28 (fine Y 2, $ADC5), so the Y write is ($27 & 3) << 6 | 5. The X write also
    # sets fine X immediately, which is harmless because the title's fine X is always 0.
    # The absolute STA $00FF adds one cycle to center the window (1,708 cycles hit-to-write).
    title_split = bytes.fromhex(
        'a0 00 88 d0 fd '                 # 1,281-cycle wait (native)
        'a5 ff 29 fc 05 36 8d ff 00 '     # $FF nametable bits for the NMI tail (native)
        'a5 27 8d 06 20 '                 # t: nametable and coarse Y bits 3-4
        '4a 6a 6a 29 c0 09 05 8d 05 20 '  # t: coarse Y 0/16, fine Y 5
        + ('20 de a5 ' if title_roar_wav else '8c 05 20 ') +
        ('a0 4a 88 d0 fd ' if title_roar_wav else 'a0 4d 88 d0 fd ') +
        '8c 06 20')                       # v = t during HBlank
    native_split = bytes.fromhex(
        'a0 00 88 d0 fd a0 4a 88 d0 fd a5 ff 29 fc 05 36 85 ff 8d 00 20'
        'a5 27 a4 28 8d 06 20 8c 06 20 ad 07 20 ad 07 20 ad 02 20')
    for address, label in ((0xA742, 'title'), (0xAB78, 'story')):
        overlay.prg(5, address, title_split, native_split, f'Title {label} scroll split in HBlank')
    # Title screen: occasionally open Barba's mouth subtly. The fireball SFX ($ED |= $40) that used to fire
    # here took over pulse 1 and cut into the title music (producer, 2026-11-14). Instead, every 4th full jaw
    # opening (~17 s) starts the short noise-channel roar (same envelope as Inferno's), which leaves both
    # pulse melodies and the triangle alone. The hook now enters TitleRoarUpdate ($A5AE), which runs the roar
    # envelope each frame and then jumps to the jaw animation at $A54F.
    roar_update = 0xA5AE
    sampled_title_code = None
    alternate_laugh_data = None
    if game_over_laughs and (waldo_portal or not title_roar_wav):
        # The combined ROM has two copies of the fixed bank. Keep the roar in
        # pages 30/31 and put all five laughs in the alternate pages 14/15.
        laugh_overlay = Overlay(source) if title_roar_wav else overlay
        laughs = game_over_audio.compile_laughs(source)
        for number, (entry, (address, raised, expected)) in enumerate(zip(game_over_audio.LAUGH_ENTRIES, laughs), 1):
            laugh_overlay.prg(7, address, raised, expected, f'Game Over octave-up laugh {number}', group='game_over_laughs')
            table_address = 0x917B + entry*2
            offset = prg_offset(6, table_address)
            overlay.prg(6, table_address, bytes([(address-0xC000)//64, (len(raised)-1)//16]),
                        source[offset:offset+2], f'Game Over shortened laugh {number} pointer/length', group='game_over_laughs')
        if title_roar_wav:
            start = prg_offset(7, roar_sample.SAMPLE_ADDRESS)
            alternate_laugh_data = bytes(laugh_overlay.target[start:start+roar_sample.SAMPLE_CAPACITY])
            roar_info['game_over_banked_laugh'] = {
                'waveforms': [{'address': a, 'bytes': len(d)} for a, d, _ in laughs],
                'rate': 15, 'spacing_frames': 23, 'initial_delay_frames': 36}
    if title_roar_wav:
        with overlay.group('sampled_roar'):
            sampled_title_code, roar_update, roar_jaw = roar_sample.title_code(sample, roar_info)
            for filename, bank, address in [('sampled-roar', 6, 0x8C00),
                                             ('item-roar', 6, 0x8A00),
                                             ('laugh-delay', 6, 0x8F70)]:
                data = (output/f'barba-{filename}.bin').read_bytes()
                overlay.prg(bank, address, data, b'\xff'*len(data), f'Sampled roar {filename} helpers')
        # The sampled driver consumes the shaft cue. Retire the native sweep
        # and its continuation while retaining the shifts for the other effects.
        overlay.prg(6, 0x940F, b'\xea\xea\x4a\xea\xea', bytes.fromhex('b0 d4 4a b0 e5'),
                    'Skip native shaft sweep in sampled builds')
        overlay.prg(6, 0x93E5, (output/'barba-fall-roar.bin').read_bytes(), bytes.fromhex(
            '8c fe 07 20 b5 90 a9 79 8d f7 07 a2 9f a0 c5 a9 58 20 64 90 '
            'ad f7 07 c9 01 d0 05 a9 22 20 67 90 4c 12 95'), 'Palace shaft roar audio dispatch')
        if waldo_portal:
            data = (output/'barba-laugh-bank.bin').read_bytes()
            overlay.prg(6, 0x8F28, data, b'\xff'*len(data), 'Enable each banked laugh only once')
            hook(6, 0x9296, 'RoarNativeEnable', 0x4C, 'a9 1f 8d 15 40 60', 3)
        # Only the bank-0 copy of the reset entry is dead. The mapper
        # routines beginning at $BF9D are also called by gameplay.
        item_hold = (output/'barba-item-hold.bin').read_bytes()
        expected_stub = bytes.fromhex(
            '78d8a2008e0020e8ad022010fbcaf0f89a8e00808e00a08e00c08e00e0'
            'a90f209dbf20b1bfa90720ccbf4c00c0'
        )
        overlay.prg(0, 0xBF76, item_hold, expected_stub[6:6+len(item_hold)], 'Item celebration pickup and input helpers')
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
        if not waldo_portal and game_over_laughs:
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
                            f'Compact octave-up Ganon laugh waveform {number}', group='game_over_laughs')
            for number, entry in enumerate(game_over_audio.LAUGH_ENTRIES):
                laugh_address, _, _ = laughs[game_over_audio.SHARED_LAUGH_INDICES[number]]
                table_address = 0x917B + entry*2
                offset = prg_offset(6, table_address)
                overlay.prg(6, table_address,
                            bytes([(laugh_address-0xC000)//64, (game_over_audio.SHARED_LAUGH_LENGTHS[number]-1)//16]),
                            source[offset:offset+2], f'Game Over compact laugh pointer/length {entry}', group='game_over_laughs')
            roar_info['game_over_shared_laugh'] = {
                'waveforms': [{'address': a, 'bytes': len(d)} for a, d, _ in laughs],
                'rates': list(game_over_audio.SHARED_LAUGH_RATES), 'spacing_frames': 23,
                'initial_delay_frames': 36}
        if game_over_laughs:
            overlay.prg(6, 0x925A, b'\x20' + labels['RoarNativeRate'].to_bytes(2, 'little') + b'\xea\xea',
                        bytes.fromhex('a9 0f 8d 10 40'), 'Configure native DMC playback for the Game Over laugh', group='game_over_laughs')
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
        if waldo_portal:
            title_enable = b'\x20' + labels['RoarRestoreBank'].to_bytes(2, 'little') + title_enable
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
    tall_layout = validate_layout(ROOT)
    title_heads = [tall_layout[pose*9:pose*9+3] for pose in (3, 4, 5)]
    title_jaws = bytes(head[col] for col in range(3) for head in title_heads)
    title_animation = bytearray(bytes.fromhex(
            'ad 1c 02 c9 7f d0 38 a5 12 c9 40 90 1e c9 60 b0 1a '
            'c9 48 90 12 f0 06 c9 58 b0 0c 90 06 '
            '20 9e a5 ea ea ea '
            'a2 02 d0 06 a2 01 d0 02 a2 00 '
            'bd 95 a5 8d 1d 02 bd 98 a5 8d 21 02 bd 9b a5 8d 3d 02 '
            'a2 6b a5 12 4c 05 87 '
        ) + title_jaws)
    if sampled_title_code is not None:
        title_animation[7:11] = b'\x20' + roar_jaw.to_bytes(2, 'little') + b'\xea'
    overlay.prg(
        5, 0xA54F,
        bytes(title_animation),
        b'\xff' * len(title_animation),
        'Title Barba mouth animation',
    )
    # Title Barba body/tail roar wiggle and 2nd-roar shake (Bank 5 $FF pads).
    # Keeps $A588 (ldx #$6B / lda $12) at its audited address and jumps here from $A58C.
    roar_target = 'e0 bf'
    for addr, hex_bytes, desc in [
        (0x8705, 'ad 1c 02 c9 7f d0 08 a9 9f 8d 44 02 20 e0 84 a2 6b a5 12 4c d3 a8',
         'Title Barba body anim entry + tail reset + exit'),
        (0x84E0, 'a9 06 8d 41 02 a9 08 8d 59 02 ad f0 05 4c f4 84',
         'Title Barba body anim neck reset + roar load'),
        (0x84F4, f'f0 03 4c {roar_target} 8d fa 64 60',
         'Title Barba body anim roar/shake dispatch'),
        (0xBFE0, 'ad fa 05 c9 02 d0 07 a5 12 29 02 8d fa 64 a5 12 29 08 d0 01 60 4c 91 88',
         'Title Barba 2nd-roar shake + roar wiggle gate'),
        (0x8891, 'ce 44 02 a2 10 8e 41 02 e8 e8 8e 59 02 60',
         'Title Barba tail wag + neck swap'),
    ]:
        data = bytes.fromhex(hex_bytes)
        overlay.prg(5, addr, data, b'\xff' * len(data), desc)
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
        assert sampled_title_code[0x40:] == b'\xea' * 10
        # $A5DE TitleShakeX5 (7 B): write LAIR_SHAKE_X ($64FA) to $2005 via X (preserves A=$FC and Y=0)
        title_roar = sampled_title_code[:0x40] + bytes.fromhex('ae fa 64 8e 05 20 60 ea ea ea')
        overlay.prg(5, 0xA66D, bytes.fromhex('20 de a5'), bytes.fromhex('8c 05 20'),
                    'Title NMI top X scroll shake')
    overlay.prg(5, 0xA59E, title_roar, b'\xff' * len(title_roar), 'Title Barba roar')
    if game_over_portrait:
        with overlay.group('game_over_portrait'):
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
    def encode_story_line(line: str, border: int = 0xFD) -> bytes:
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
        out.append(border)
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
    new_story = b''.join(encode_story_line(line, title_border) for line in story_lines)
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
    # Two 8x16 overworld sand sparkle frames at tile pairs $D0 (1px white) and $D2 (3x3 white '+' twinkle).
    if world[0xD0*16:0xD4*16] != b'\x00'*64:
        raise ValueError('Overworld sand sparkle sprite slots $D0-$D3 are not empty')
    world[0xD0*16:0xD2*16] = _chr_8x16([
        '........', '.#......', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
    ])
    world[0xD2*16:0xD4*16] = _chr_8x16([
        '.#......', '###.....', '.#......', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
    ])
    # Additional overworld ambience particles ($D4-$DF):
    # $D4/$D6: Water sun-glint crest (Palette 2: o=white $30, #=black $0F shadow).
    # $D8/$DA: Swamp marsh bubble (Palette 0: +=gold $27, #=white $30).
    # $DC/$DE: Mountain/rock/lava rising ember (Palette 0: +=gold $27, o=red $16).
    if world[0xD4*16:0xE0*16] != b'\x00'*192:
        raise ValueError('Overworld ambience sprite slots $D4-$DF are not empty')
    world[0xD4*16:0xD6*16] = _chr_8x16([
        '........', '.o......', '.#......', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
    ])
    world[0xD6*16:0xD8*16] = _chr_8x16([
        '........', 'ooo.....', '.##.....', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
    ])
    world[0xD8*16:0xDA*16] = _chr_8x16([
        '........', '.+......', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
    ])
    world[0xDA*16:0xDC*16] = _chr_8x16([
        '.#+.....', '.++.....', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
    ])
    world[0xDC*16:0xDE*16] = _chr_8x16([
        '........', '.+......', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
    ])
    world[0xDE*16:0xE0*16] = _chr_8x16([
        '........', '.o......', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
    ])
    # $E0/$E2: Graveyard cross wisp (Palette 0: +=gold $27, #=white $30).
    if world[0xE0*16:0xE4*16] != b'\x00'*64:
        raise ValueError('Overworld graveyard wisp sprite slots $E0-$E3 are not empty')
    world[0xE0*16:0xE2*16] = _chr_8x16([
        '........', '.+......', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
    ])
    world[0xE2*16:0xE4*16] = _chr_8x16([
        '..#.....', '.+......', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
        '........', '........', '........', '........',
    ])
    # Replace unused CHR 30 $68-$6B copy and overworld R1 Fairy ($80-$87) with Wyrmling.
    world[0x68*16:0x6A*16] = graphics[0x68]
    world[0x6A*16:0x6C*16] = graphics[0x6A]
    ow_fairy_off = 4096 + 0x80 * 16
    if hashlib.sha256(world[ow_fairy_off:ow_fairy_off + 128]).hexdigest()[:16] != '80f9fc3bde2ab466':
        raise ValueError('Overworld R1 Fairy slots $80-$87 do not match expected vanilla bytes')
    world[ow_fairy_off:ow_fairy_off + 128] = compile_overworld_wyrmling(ROOT)
    offset = CHR_OFFSET+30*4096
    pre_foliage = 4096 + 0x9E * 16
    post_foliage = 4096 + 0xB0 * 16
    if world[pre_foliage:post_foliage] != b'\x00' * (post_foliage - pre_foliage):
        raise ValueError('Overworld R1 foliage slots $9E-$AF are not empty')
    overlay.put(offset, world[:pre_foliage], b'\xFF' * pre_foliage,
                'Dedicated overworld graphics (CHR 30 + CHR 31 up to $9D)')
    overlay.put(offset + post_foliage, world[post_foliage:], b'\xFF' * (8192 - post_foliage),
                'Dedicated overworld graphics (CHR 31 $B0-$FF)')

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

    # Reclaimed SpellMenu_Pane__SpellText ($9C1A..$9D31, 280 bytes) -> 18-spell / 2-col menu stubs.
    for fname, addr, limit, desc in [
        ('barba-bank0-spell.bin', 0x9C1A, 0x0118, 'Bank 0 18-spell & 2-col menu stubs'),
        ('barba-bank0-spell2.bin', 0xA347, 0x0018, 'Bank 0 2-col menu init/attr stubs'),
        ('barba-bank0-spell3.bin', 0x8DC9, 0x0013, 'Bank 0 2-col menu input stub'),
    ]:
        stub = (output / fname).read_bytes()
        assert len(stub) <= limit, f'{fname} too large: {len(stub)}'
        off = prg_offset(0, addr)
        overlay.put(off, stub, source[off:off + len(stub)], desc)
    spells_bank1 = (output / 'barba-bank1-spells.bin').read_bytes()
    overlay.prg(1, 0xB234, spells_bank1, b'\xFF' * len(spells_bank1), 'Bank 1 18-spell & 2-col menu routines')
    hook(0, 0x8CF4, 'ArcadeSideViewInit0', 0x20, '8d 6f 07')
    hook(0, 0x8DC6, 'ArcadeSpellHook0', 0x4C, '0d 24 05')
    for ptr_addr, label_name, orig_hex in [
        (0x9D7D, 'LevelUpInit0', '47 a3'),
        (0x9DE6, 'SpellMenuInit0', '47 a3'),
        (0x9DEA, 'SpellMenuAttrSave0', '6b a2'),
        (0x9DEC, 'SpellMenuDraw0', 'fe a2'),
        (0x9DEE, 'SpellMenuInput0', 'dd a1'),
        (0x9DF0, 'SpellMenuAttrSave0', '6b a2'),
        (0x9DF2, 'SpellMenuRestore0', 'd7 a3'),
        (0x9DF4, 'SpellMenuDone0', '38 a3'),
    ]:
        dest = labels[label_name]
        overlay.prg(0, ptr_addr, bytes([dest & 255, dest >> 8]), bytes.fromhex(orig_hex), f'Pause pane {label_name}')

    # Palace 6 "Lava Link" boss: Link art in R5 CHR bank 154 ($C0-$D1), Spear (05) sword beams, Link palette.
    # Use Sprite Palette 3 ($3F1D) so Sprite Palette 1 ($3F15, shared by health bars and fireballs) stays red/orange.
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
    # and drop the enemy-hit SFX bit if the driver hasn't consumed it yet; then JMP to Lava Link's intro gate.
    overlay.prg(
        4, 0xA795,
        bytes.fromhex('bd 0e 04 c9 30 d0 0a a9 01 85 e9 a5 ed 29 ef 85 ed 4c')
        + labels['LavaLinkGate'].to_bytes(2, 'little'),
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
    # The DMA shadow now draws the boss meters. Keep the native routines'
    # enemy-slot restore and bypass their writes to the rotating sprite page.
    overlay.prg(4, 0x9C45, bytes.fromhex('4c 7a 9c'), bytes.fromhex('85 00 a0'), 'Palace boss meter moves to shadow OAM')
    overlay.prg(5, 0xA4E9, bytes.fromhex('4c 1e a5'), bytes.fromhex('85 00 a0'), 'Great Palace boss meter moves to shadow OAM')
    # 48 HP takes three fireballs at Attack 7 (18 each). Six HP per pip is set in boss_meter.inc.
    overlay.prg(4, 0xA943, b'\x30', b'\x10', 'Carock HP (16 -> 48)')
    # Reflected bolts use Attack 8 damage (24) against Carock, with native damage for other targets.
    overlay.prg(4, 0xA804, bytes.fromhex('b5 a1 c9 22 d0 02 a0 08 4c 26 e7'), b'\xff' * 11,
                'Carock Reflect damage helper')  # LDA $A1,X / CMP #$22 / BNE native / LDY #8 / JMP $E726
    overlay.prg(4, 0xAD6B, bytes.fromhex('20 04 a8'), bytes.fromhex('20 26 e7'), 'Carock reflected bolt damage')
    # Gooma's renderer shares $0240/$0244 with Barba's projectiles. Move the
    # ball and links to four unused entries in the boss room for both poses.
    # The bank-6 shadow copy gives them early OAM priority on crowded lines.
    gooma_oam = {0x40: 0xA0, 0x44: 0xA4, 0x90: 0xA8, 0x94: 0xAC}
    for addresses, opcode, old_offset in [
        ((0xB637, 0xB6FD), 0x8D, 0x40),
        ((0xB63A, 0xB700), 0x8D, 0x44),
        ((0xB643, 0xB6C5), 0x8D, 0x43),
        ((0xB649, 0xB6CB), 0x8D, 0x47),
        ((0xB6D7,), 0x6D, 0x43),
        ((0xB6DE,), 0x8D, 0x93),
        ((0xB6E4,), 0x8D, 0x97),
        ((0xB6E9,), 0x8D, 0x91),
        ((0xB6EC,), 0x8D, 0x95),
        ((0xB6EF,), 0xAD, 0x42),
        ((0xB6F2,), 0x8D, 0x92),
        ((0xB6F5,), 0x8D, 0x96),
        ((0xB703,), 0x8D, 0x90),
        ((0xB706,), 0x8D, 0x94),
        ((0xB70E,), 0x8D, 0x42),
        ((0xB711,), 0x8D, 0x46),
        ((0xB71A,), 0x8C, 0x41),
        ((0xB71D,), 0x8D, 0x45),
        ((0xB722,), 0x8D, 0x41),
        ((0xB725,), 0x8C, 0x45),
    ]:
        new_offset = gooma_oam[old_offset & 0xFC] + (old_offset & 3)
        for address in addresses:
            overlay.prg(4, address, bytes([opcode, new_offset, 2]),
                        bytes([opcode, old_offset, 2]), f'Gooma weapon OAM at ${address:04X}')
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
            'c0 36 60 60 c0 34 60 68 f8 f5 60 70'
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
    # Reload North Palace's palette table ($7919..$79F8) before entering $8B50
    # so beating Dark Barba in Great Palace renders North Palace with its own
    # lavender/brown/white/pink palette instead of Great Palace's black palette.
    overlay.prg(
        7, 0xC376,
        bytes.fromhex('20 c5 ff') + b'\x4c' + labels['EndingPalFix0'].to_bytes(2, 'little'),
        bytes.fromhex('20 88 c3 4c 50 8b'),
        'Ending reload North Palace palette before $8B50',
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

    # East Hyrule ($076E = $04 -> CHR bank 5) clouds drift left-to-right;
    # horizontally mirror $B3-$B8 (swapping left $B3/$B4 <-> right $B7/$B8)
    # before building the water-ripple R1 variants so all East encounters match.
    def _hflip_tile(tile: bytes) -> bytes:
        return bytes(int(f'{b:08b}'[::-1], 2) for b in tile)
    east_cloud_off = CHR_OFFSET + 5 * 4096 + 0xB3 * 16
    east_cloud_orig = source[east_cloud_off:east_cloud_off + 6 * 16]
    east_cloud_new = b''.join([
        _hflip_tile(east_cloud_orig[4 * 16:5 * 16]),  # B3 <- hflip(B7)
        _hflip_tile(east_cloud_orig[5 * 16:6 * 16]),  # B4 <- hflip(B8)
        _hflip_tile(east_cloud_orig[2 * 16:3 * 16]),  # B5 <- hflip(B5)
        _hflip_tile(east_cloud_orig[3 * 16:4 * 16]),  # B6 <- hflip(B6)
        _hflip_tile(east_cloud_orig[0 * 16:1 * 16]),  # B7 <- hflip(B3)
        _hflip_tile(east_cloud_orig[1 * 16:2 * 16]),  # B8 <- hflip(B4)
    ])
    overlay.put(east_cloud_off, east_cloud_new, east_cloud_orig,
                'CHR 05: East Hyrule horizontally mirrored cloud tiles B3-B8')

    # Append 128 KB extra CHR-ROM (1 KB banks 128..255) containing 3 horizontally rippled
    # R1 ($0800-$0FFF) variants for each of the 13 side-view CHR pairs (0..24). Only lava
    # surface tiles $98/$99 are shifted per-scanline so bricks/walls stay stationary.
    ext_chr = bytearray(131072)
    def _ror8(val: int, n: int) -> int:
        n &= 7
        return ((val >> n) | (val << (8 - n))) & 0xFF
    def _encode_2bpp(rows: tuple[str, ...]) -> bytes:
        p0, p1 = bytearray(8), bytearray(8)
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                v = '.#*O'.index(ch)
                bit = 7 - c
                p0[r] |= (v & 1) << bit
                p1[r] |= ((v >> 1) & 1) << bit
        return bytes(p0) + bytes(p1)
    def _ripple_r1(base_r1: bytes, v: int) -> bytearray:
        variant = bytearray(base_r1)
        for t_idx in (0x18, 0x19):
            t_off = t_idx * 16
            for row in range(8):
                phase = (v + (row >> 1) + (2 if t_idx == 0x19 else 0)) & 3
                shift = (0, 1, 2, 1)[phase]
                variant[t_off + row] = _ror8(variant[t_off + row], shift)
                variant[t_off + 8 + row] = _ror8(variant[t_off + 8 + row], shift)
        return variant
    for pair_idx in range(1, 13):
        base_off = CHR_OFFSET + (pair_idx * 2 + 1) * 4096 + 2048
        base_r1 = overlay.target[base_off:base_off + 2048]
        for v in (1, 2, 3):
            ext_off = (pair_idx * 3 + (v - 1)) * 2048
            ext_chr[ext_off:ext_off + 2048] = _ripple_r1(base_r1, v)

    # R1 banks 146, 148, 150, 152 (2 KB each): all three Saria street rooms
    # use 4 KB town CHR bank 7 R1 and bubble with town BG palette 1
    # ($22 sky, $37 pale highlight [#], $2A green [*], $0F dark murky base [O]).
    saria6_base = overlay.target[CHR_OFFSET + 7 * 4096 + 2048:CHR_OFFSET + 7 * 4096 + 4096]
    foul_surface_frames = (
        (
            '........',
            '........',
            '..*O..O.',
            'OO#*OOOO',
            'OOOOO*#O',
            'O*#OOOOO',
            'OOOO*OOO',
            'OO*#OOOO',
        ),
        (
            '........',
            '...#....',
            '.O*#O*O.',
            'OOOO*#OO',
            'O*#OOOOO',
            'OOOO*#OO',
            'OO*OOOO*',
            'OOOO*#OO',
        ),
        (
            '........',
            '.....*..',
            'O*O*#*OO',
            'O*#OOOOO',
            'OOOO*#OO',
            'OO*#OOOO',
            'O*OOO*#O',
            'OOOO*OOO',
        ),
        (
            '........',
            '........',
            'O*OO*O*O',
            'OOOOO*#O',
            'OO*#OOOO',
            'O*OOOO*O',
            'OOO*#OOO',
            'O*#OOOOO',
        ),
    )
    foul_body_frames = (
        (
            'OO*#OOOO',
            'OOOOO*#O',
            'O*OOOOOO',
            'OOO*#OOO',
            'OOOOOO*O',
            'O*#OOOOO',
            'OOOO*#OO',
            'OO*OOOOO',
        ),
        (
            'O*OOOO*O',
            'OOO*#OOO',
            'O*#OOOOO',
            'OOOOO*#O',
            'OO*OOOOO',
            'OOOO*#OO',
            'O*#OOOOO',
            'OOOO*OOO',
        ),
        (
            'OOOO*#OO',
            'O*#OOOOO',
            'OOOOO*#O',
            'OO*OOOOO',
            'O*#OOOOO',
            'OOOOOO*O',
            'OOO*#OOO',
            'O*OOOO*O',
        ),
        (
            'OOO*#OOO',
            'OO*OOOOO',
            'O*#OOOOO',
            'OOOO*#OO',
            'OOOOO*#O',
            'OO*OOOOO',
            'O*OOOO*O',
            'OO*#OOOO',
        ),
    )
    for v, bank_1kb in enumerate((146, 148, 150, 152)):
        variant = bytearray(saria6_base)
        variant[0x18 * 16:0x19 * 16] = _encode_2bpp(foul_surface_frames[v])
        variant[0x19 * 16:0x1A * 16] = _encode_2bpp(foul_body_frames[v])
        ext_off = (bank_1kb - 128) * 1024
        ext_chr[ext_off:ext_off + 2048] = variant

    # R5 bank 174 ($1C00-$1FFF, tiles $C0-$DF): Palace 6 Lava Link + crystal sprites
    # kept on A12=1 so they never trigger extra MMC3 scanline IRQ clocks (bank 154 holds title_r5).
    lava_link_pairs = compile_lava_link(source)
    crystal_off = CHR_OFFSET + 25 * 4096 + 0x3C * 16
    lava_link_pairs[0x3C] = source[crystal_off:crystal_off + 32]
    lava_link_off = (174 - 128) * 1024
    for slot, src_pair in enumerate((0x14, 0x16, 0x18, 0x1A, 0x1C, 0x22, 0x24, 0x26, 0x28, 0x2A, 0x2C, 0x2E, 0xA0, 0xA2, 0x52, 0x3C)):
        pair_off = lava_link_off + slot * 32
        ext_chr[pair_off:pair_off + 32] = lava_link_pairs[src_pair]

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

    # R0 banks 246..253 are the four nonzero wind phases for East Hyrule's
    # tall grass ($4E in 4 KB bank 5 / 1 KB bank 20), leading right first.
    east_r0_off = CHR_OFFSET + 5 * 4096
    east_r0 = overlay.target[east_r0_off:east_r0_off + 2048]
    for phase, shift in enumerate((1, 2, -1, -2)):
        variant = bytearray(east_r0)
        middle_shift = 1 if shift > 0 else -1
        for plane in (0, 8):
            for row, bend in enumerate((shift, shift, middle_shift, middle_shift, middle_shift)):
                offset = 0x4E * 16 + plane + row
                pixels = variant[offset]
                shifted = pixels >> bend if bend > 0 else pixels << -bend
                if shifted.bit_count() != pixels.bit_count() or shifted > 0xFF:
                    raise ValueError('East grass wind phase clips the tip tile')
                variant[offset] = shifted
        ext_off = (246 - 128) * 1024 + phase * 2048
        ext_chr[ext_off:ext_off + 2048] = variant

    # R0 banks 170, 172 (2 KB each): town bush ($45: tiles $4C/$4E top,
    # $4D/$4F bottom) wind-sway variants from 4 KB CHR bank 7 (1 KB bank 28).
    # Gentle ±1 px lean on the upper 10 rows (y=192..201), keeping the lower
    # belly and tapering base (y=202..207) rooted.
    town_r0_off = CHR_OFFSET + 7 * 4096
    town_r0 = overlay.target[town_r0_off:town_r0_off + 2048]
    for bank_id, shift in ((170, -1), (172, 1)):
        variant = bytearray(town_r0)
        def _shift_bush_row(left_tile: int, right_tile: int, row: int, s: int) -> None:
            for plane in (0, 8):
                lo = left_tile * 16 + plane + row
                hi = right_tile * 16 + plane + row
                wide = (variant[lo] << 8) | variant[hi]
                shifted = (wide >> s) if s > 0 else ((wide << -s) & 0xFFFF)
                variant[lo] = (shifted >> 8) & 0xFF
                variant[hi] = shifted & 0xFF
        for r in range(8):
            _shift_bush_row(0x4C, 0x4E, r, shift)
        for r in range(2):
            _shift_bush_row(0x4D, 0x4F, r, shift)
        ext_off = (bank_id - 128) * 1024
        ext_chr[ext_off:ext_off + 2048] = variant

    # R3 banks 214..227 are shimmer variants of the candle flame ($52/$53):
    # 214..220 from 1 KB bank 9 (identical to 41, 49, 57, 73, 81, 97) and
    # 221..227 from 1 KB bank 89 ($076E = $16).
    flame_variants = (
        (
            ('...##...', '...#*#..', '..##*#..', '..#**#..', '.##**##.', '.#***##.', '.##**##.', '.#****#.'),
            ('#*****##', '#**OO**#', '#**OO**#', '#*OOOO*#', '##*OO*##', '.##**##.', '..####..', '........'),
        ),
        (
            ('....*...', '....#...', '........', '..##....', '..#*#...', '.##*##..', '.#***#..', '.##**##.'),
            ('##**#*##', '##*O**##', '#**OO**#', '#**OO**#', '##*OO*##', '.##**##.', '..####..', '........'),
        ),
        (
            ('.....#..', '........', '...#....', '..#*#...', '..#**#..', '.##**#..', '.#***##.', '.##***#.'),
            ('#****###', '##*OO*##', '#**OO**#', '#*OOO**#', '##*OO*##', '.##**##.', '..####..', '........'),
        ),
        (
            ('........', '....#...', '...##...', '..##.#..', '.##*#...', '.##**#..', '.#***##.', '##***###'),
            ('#******#', '#**OO**#', '#*OOOO*#', '#*OOOO*#', '##*OO*##', '.##**##.', '..####..', '........'),
        ),
        (
            ('..#.....', '..#..#..', '.##..#..', '.#*###..', '.##**#..', '.#***##.', '.##**##.', '.#****#.'),
            ('##****##', '#**OO*##', '#**OO**#', '#**OO**#', '##****##', '.##**##.', '..####..', '........'),
        ),
        (
            ('....#...', '...#*...', '...##...', '..#**#..', '.##**#..', '.#***##.', '.#****#.', '##**O*##'),
            ('#**OO**#', '#*OOOO*#', '#*OOOO*#', '#**OO**#', '##*OO*##', '.##**##.', '..####..', '........'),
        ),
        (
            ('......#.', '....#...', '..#.##..', '.##*#...', '.###*#..', '.##**#..', '.##**##.', '.###*##.'),
            ('##**#*##', '##****##', '#**OO**#', '#**OO**#', '##*OO*##', '.##**##.', '..####..', '........'),
        ),
    )
    encoded_flames = [
        (_encode_2bpp(top_rows), _encode_2bpp(bot_rows))
        for top_rows, bot_rows in flame_variants
    ]
    for base_r3, ext_start in ((9, 214), (89, 221)):
        base_off = CHR_OFFSET + base_r3 * 1024
        base_r3_bytes = overlay.target[base_off:base_off + 1024]
        for idx, (top_bytes, bot_bytes) in enumerate(encoded_flames):
            variant = bytearray(base_r3_bytes)
            variant[0x12 * 16:0x13 * 16] = top_bytes
            variant[0x13 * 16:0x14 * 16] = bot_bytes
            ext_off = (ext_start + idx - 128) * 1024
            ext_chr[ext_off:ext_off + 1024] = variant

    # R5 bank 228: palace entrance parallax cloud 8x16 sprite pairs ($C0/$C1, $C2/$C3, $C4/$C5)
    # derived from vanilla BG cloud tiles $B3-$B8 in CHR bank 9, remapping color 1 <-> 3
    # (p1 ^= p0) so sprite palette 3 renders white highlights and sky-blue/gray shading.
    cloud_bank_off = (228 - 128) * 1024
    cloud_src_off = CHR_OFFSET + 9 * 4096 + 0xB3 * 16
    cloud_tiles = bytearray()
    for t_idx in range(6):
        tile = bytearray(source[cloud_src_off + t_idx * 16:cloud_src_off + (t_idx + 1) * 16])
        for row in range(8):
            tile[8 + row] ^= tile[row]
        cloud_tiles.extend(tile)
    ext_chr[cloud_bank_off:cloud_bank_off + 6 * 16] = cloud_tiles

    # R4 bank 229: town outdoor parallax cloud 8x16 sprite pairs ($88/$89, $8A/$8B, $8C/$8D)
    # overlaid onto a copy of town sprite bank 6 R4 ($80-$BF) so AshTileRight ($80),
    # fireballs / GODLIKE! flames ($84), combo glyphs ($9C-$AE), and Little Kid sprites
    # ($B0, $BA-$BE) stay intact while all townfolk in R5 ($C0-$FF) stay vanilla.
    # ($89 ^ $04 == $8D, so East Hyrule H-flip swaps left/right puffs cleanly.)
    town_cloud_bank_off = (229 - 128) * 1024
    town_r4_off = CHR_OFFSET + 6 * 4096 + 0x800
    ext_chr[town_cloud_bank_off:town_cloud_bank_off + 1024] = overlay.target[town_r4_off:town_r4_off + 1024]
    ext_chr[town_cloud_bank_off + 0x08 * 16:town_cloud_bank_off + 0x0E * 16] = cloud_tiles
    # Smoke puff 8x16 sprite pairs ($8E/$8F, $90/$91, $92/$93) in R4 bank 229.
    smoke_puffs = (
        (
            ('........', '........', '........', '........', '...OO...', '..OOOO..', '..#OO#..', '...##...'),
            ('..####..', '.######.', '..####..', '........', '........', '........', '........', '........'),
        ),
        (
            ('........', '...OO...', '..OOOO..', '.OOOO#..', '..#OO#..', '..###...', '...##...', '........'),
            ('..###...', '.###OO..', '..####..', '...##...', '........', '........', '........', '........'),
        ),
        (
            ('...O....', '..OO#...', '...##...', '..#.....', '...#....', '........', '........', '........'),
            ('........', '..##....', '...#....', '........', '........', '........', '........', '........'),
        ),
    )
    for idx, (top_rows, bot_rows) in enumerate(smoke_puffs):
        pair_off = town_cloud_bank_off + (0x0E + idx * 2) * 16
        ext_chr[pair_off:pair_off + 16] = _encode_2bpp(top_rows)
        ext_chr[pair_off + 16:pair_off + 32] = _encode_2bpp(bot_rows)

    # R0 banks 230, 232, 234, 236 (2 KB each): overworld water/lava ($6E) and swamp ($6F).
    # Grass ($6D) and forest ($68/$6A) animate asynchronously per-tile via CHR 31 R1 ($9E..$AF).
    ow_r0_off = CHR_OFFSET + 31 * 4096
    ow_r0 = overlay.target[ow_r0_off:ow_r0_off + 2048]
    for slot, (top_shift, bot_shift) in enumerate((
        (1, -1), (2, -2), (-1, 1), (-2, 2)
    )):
        variant = bytearray(ow_r0)
        # Water/lava ($6E) and swamp ($6F): 8-step counter-phase ripple (+/-2 px).
        for tile_id in (0x6E, 0x6F):
            t_off = tile_id * 16
            for row in range(8):
                shift = top_shift if row < 4 else bot_shift
                variant[t_off + row] = _ror8(variant[t_off + row], shift)
                variant[t_off + 8 + row] = _ror8(variant[t_off + 8 + row], shift)
        ext_off = (230 + slot * 2 - 128) * 1024
        ext_chr[ext_off:ext_off + 2048] = variant

    # CHR 31 R1 ($0800-$0FFF, tiles $9E..$AF): independent grass ($6D) and forest
    # ($68 TL / $6A TR) sway/rustle variants written into the dedicated overworld R1 bank.
    ow_r1_off = ow_r0_off + 2048
    def _shift_ow_tile(src_tile: int, row_shifts: dict[int, int], *, wrap: bool) -> bytes:
        buf = bytearray(overlay.target[ow_r0_off + src_tile * 16:ow_r0_off + (src_tile + 1) * 16])
        for row, shift in row_shifts.items():
            for plane in (0, 8):
                val = buf[plane + row]
                if wrap:
                    buf[plane + row] = _ror8(val, shift)
                else:
                    buf[plane + row] = ((val >> shift) if shift > 0 else (val << -shift)) & 0xFF
        return bytes(buf)

    grass_variants = (
        {0: 1, 1: 1},                  # $9E: top tuft leans right
        {0: -1, 1: -1},                # $9F: top tuft leans left
        {5: 1, 6: 1},                  # $A0: lower tuft rustles right
        {5: -1, 6: -1},                # $A1: lower tuft rustles left
        {0: 1, 1: 1, 2: 1, 5: 1, 6: 1},  # $A2: full breeze right
        {0: 1, 1: 1, 5: -1, 6: -1},    # $A3: cross breeze
    )
    for idx, rs in enumerate(grass_variants):
        tid = 0x9E + idx
        overlay.put(ow_r1_off + (tid - 0x80) * 16, _shift_ow_tile(0x6D, rs, wrap=True),
                    b'\xFF' * 16, f'Overworld grass R1 variant ${tid:02X}')

    forest_tl_variants = (
        {0: 1, 1: 1},          # $A4: upper crown shifts right
        {1: -1, 2: -1},        # $A5: upper canopy shifts left
        {4: -1, 6: -1},        # $A6: mid/lower leaves shift left
        {4: 1, 6: 1},          # $A7: mid/lower leaves shift right
        {0: 1, 1: 1, 4: 1},    # $A8: upper-mid breeze right
        {2: -1, 3: -1, 6: -1}, # $A9: canopy breeze left
    )
    for idx, rs in enumerate(forest_tl_variants):
        tid = 0xA4 + idx
        overlay.put(ow_r1_off + (tid - 0x80) * 16, _shift_ow_tile(0x68, rs, wrap=False),
                    b'\xFF' * 16, f'Overworld forest-TL R1 variant ${tid:02X}')

    def _forest_tr_tile(overrides: dict[int, str], shift_rows: dict[int, int]) -> bytes:
        base = bytearray(overlay.target[ow_r0_off + 0x6A * 16:ow_r0_off + 0x6B * 16])
        for row, shift in shift_rows.items():
            for plane in (0, 8):
                val = base[plane + row]
                base[plane + row] = ((val >> shift) if shift > 0 else (val << -shift)) & 0xFF
        for row, pat in overrides.items():
            enc = _encode_2bpp((pat,) + ('........',) * 7)
            base[row] = enc[0]
            base[8 + row] = enc[8]
        return bytes(base)

    forest_tr_variants = (
        ({1: 'O..*OOO*', 2: 'OO.*OOO*'}, {}),       # $AA: upper canopy rustle
        ({3: 'OO..OOO.'}, {4: 1}),                 # $AB: mid-crown leaf shift
        ({}, {4: 1, 5: -1}),                       # $AC: counter-sway middle leaves
        ({6: 'OO.OO*O*', 7: 'O..OOO.*'}, {}),      # $AD: lower canopy rustle
        ({1: 'O..*OOO*', 3: 'OO..OOO.'}, {4: 1}),  # $AE: upper+mid breeze
        ({2: 'OO.*OOO*', 7: 'O..OOO.*'}, {5: -1}), # $AF: cross-canopy twitch
    )
    for idx, (overrides, rs) in enumerate(forest_tr_variants):
        tid = 0xAA + idx
        overlay.put(ow_r1_off + (tid - 0x80) * 16, _forest_tr_tile(overrides, rs),
                    b'\xFF' * 16, f'Overworld forest-TR R1 variant ${tid:02X}')

    # R0 banks 238, 240, 242, 244 (2 KB each): ripple the open lava and carry
    # the same texture through the original water masks in the forest edge.
    # Also build the 1px undulating surface wave on row 5 of tiles $5A-$5D.
    title_r0 = overlay.target[title_r0_off:title_r0_off + 2048]
    wave_masks = (0xFC7F, 0xFE3F, 0xFF1F, 0xFE3F)
    for v in range(4):
        variant = bytearray(title_r0)
        for t_idx, t_phase in zip(TITLE_LAVA_TILES, (0, 2, 1)):
            t_off = t_idx * 16
            for row in range(8):
                phase = (v + (row >> 1) + t_phase) & 3
                shift = (0, 1, 2, 1)[phase]
                variant[t_off + row] = _ror8(variant[t_off + row], shift)
                variant[t_off + 8 + row] = _ror8(variant[t_off + 8 + row], shift)
        m_hi = (wave_masks[v] >> 8) & 0xFF
        m_lo = wave_masks[v] & 0xFF
        for left_tid, right_tid, base_tid in ((0x5A, 0x5B, 0x68), (0x5C, 0x5D, 0x69)):
            base_slice = variant[base_tid * 16:base_tid * 16 + 16]
            for tid, m in ((left_tid, m_hi), (right_tid, m_lo)):
                t_off = tid * 16
                variant[t_off:t_off + 16] = base_slice
                variant[t_off + 5] &= m
                variant[t_off + 13] &= m
        for tile in TITLE_FOREST_EDGE_TILES:
            offset = tile * 16
            forest = source[title_r0_off + offset:title_r0_off + offset + 16]
            variant[offset:offset + 16] = compile_title_shore(tile, forest, variant[0x6A0:0x6B0])
        ext_off = (238 + v * 2 - 128) * 1024
        ext_chr[ext_off:ext_off + 2048] = variant

    # R5 bank 154 (1 KB): title sprite bank 3 with tiny lava-bubble and ember pairs ($C0-$C6).
    title_r5 = bytearray(overlay.target[CHR_OFFSET + 3 * 1024:CHR_OFFSET + 4 * 1024])
    title_bubble_tiles = {
        0xC0: [
            '00000000',
            '00000000',
            '00000000',
            '00032000',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
        ],
        0xC2: [
            '00000000',
            '00030000',
            '00202000',
            '00020000',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
        ],
        0xC4: [
            '00000000',
            '00203000',
            '00000000',
            '00020000',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
        ],
        0xC6: [
            '00000000',
            '00000000',
            '00000000',
            '00020000',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
        ],
    }
    for pair_id, rows in title_bubble_tiles.items():
        p_off = (pair_id - 0xC0) * 16
        title_r5[p_off:p_off + 16] = encode_tile(rows)
        title_r5[p_off + 16:p_off + 32] = b'\x00' * 16
    ext_chr[(154 - 128) * 1024:(155 - 128) * 1024] = title_r5

    # R2 bank 155 (side-view): Waldo-hat variants of Barba's head tiles.
    def _overlay_hat_8x16(r2: bytearray, pairs: tuple[int, ...], x0: int, y0: int,
                          hat_rows: tuple[str, ...]) -> None:
        width = len(pairs) * 8
        canvas = [[0] * width for _ in range(16)]
        for col, pair_idx in enumerate(pairs):
            base = pair_idx * 16
            top = decode_tile(r2[base:base + 16])
            bot = decode_tile(r2[base + 16:base + 32])
            for y in range(8):
                canvas[y][col * 8:(col + 1) * 8] = top[y]
                canvas[y + 8][col * 8:(col + 1) * 8] = bot[y]
        for dy, hrow in enumerate(hat_rows):
            yy = y0 + dy
            if 0 <= yy < 16:
                for dx, ch in enumerate(hrow):
                    xx = x0 + dx
                    if ch != '.' and 0 <= xx < width:
                        canvas[yy][xx] = int(ch)
        for col, pair_idx in enumerate(pairs):
            base = pair_idx * 16
            top_rows = [''.join(str(canvas[y][col * 8 + x]) for x in range(8)) for y in range(8)]
            bot_rows = [''.join(str(canvas[y + 8][col * 8 + x]) for x in range(8)) for y in range(8)]
            r2[base:base + 16] = encode_tile(top_rows)
            r2[base + 16:base + 32] = encode_tile(bot_rows)

    sv_hat = (
        '..11111111',
        '.111111111',
        '3333333333',
        '3333333333',
    )
    sv_glasses = (
        '111111..',
        '13333111',
        '131331..',
        '133331..',
        '111111..',
    )
    sv_r2 = bytearray(overlay.target[CHR_OFFSET:CHR_OFFSET + 1024])
    _overlay_hat_8x16(sv_r2, (0x02, 0x04), 3, 0, sv_hat)
    _overlay_hat_8x16(sv_r2, (0x20,), 3, 0, tuple(r[:5] for r in sv_hat))
    _overlay_hat_8x16(sv_r2, (0x3A, 0x3C), 4, 5, sv_hat)
    _overlay_hat_8x16(sv_r2, (0x02, 0x04), 3, 4, sv_glasses)
    _overlay_hat_8x16(sv_r2, (0x20,), 3, 4, tuple(r[:5] for r in sv_glasses))
    _overlay_hat_8x16(sv_r2, (0x3A, 0x3C), 4, 9, sv_glasses)
    sv_hat_front_rows = (
        '00011133',
        '03311133',
        '33333113',
        '33333313',
        '11113331',
        '11111111',
        '11111111',
        '00000000',
        '00000000',
        '00000000',
        '00000000',
        '00000000',
        '00000000',
        '00000000',
        '00000000',
        '00000000',
    )
    sv_r2[0x1C * 16:0x1E * 16] = encode_tile(sv_hat_front_rows[:8]) + encode_tile(sv_hat_front_rows[8:])
    ext_chr[(155 - 128) * 1024:(156 - 128) * 1024] = sv_r2

    # R2 bank 181 (side-view): Friday the 13th Hockey Mask over Barba's snout/face.
    # Color 3 = white mask plate, 1 = dark eye/air holes & outline, 2 = red chevrons.
    sv_hockey_mask = (
        '..1111111..',
        '.133233231.',
        '.131131131.',
        '1333333331.',
        '1323131321.',
        '1333333331.',
        '.131313131.',
        '..1111111..',
    )
    sv_r2_mask = bytearray(overlay.target[CHR_OFFSET:CHR_OFFSET + 1024])
    _overlay_hat_8x16(sv_r2_mask, (0x02, 0x04), 0, 4, sv_hockey_mask)
    _overlay_hat_8x16(sv_r2_mask, (0x1C,), 0, 4, tuple(r[:8] for r in sv_hockey_mask))
    _overlay_hat_8x16(sv_r2_mask, (0x20,), 0, 4, tuple(r[:8] for r in sv_hockey_mask))
    _overlay_hat_8x16(sv_r2_mask, (0x3A, 0x3C), 1, 9, sv_hockey_mask)
    ext_chr[(181 - 128) * 1024:(182 - 128) * 1024] = sv_r2_mask
    if boss_meter == 'souls':
        ext_chr[(156 - 128) * 1024:(158 - 128) * 1024] = compile_souls_bar_chr()
        # R5 banks 175-180: odd-bank ($076E+1) sprite pairs ($08..$2E -> $C1..$E7,
        # Rebonack/Thunderbird $3E..$4E -> $ED..$FD, Gooma $9E..$A2 -> $E9..$ED)
        # so MMC3 scanline IRQs never see A12=0 sprite fetches during boss fights.
        for r5_bank, gfx_id in ((175, 0x08), (176, 0x0A), (177, 0x14), (178, 0x16), (179, 0x12), (180, 0x0C)):
            r5_buf = bytearray(1024)
            src_spr = CHR_OFFSET + (gfx_id + 1) * 4096
            for pair in range(0x08, 0x30, 2):
                dst_off = (pair + 0xB9 - 0xC1) * 16
                r5_buf[dst_off:dst_off + 32] = source[src_spr + pair * 16:src_spr + pair * 16 + 32]
            if gfx_id in (0x0C, 0x12):
                for pair in range(0x3E, 0x50, 2):
                    dst_off = (pair + 0xAF - 0xC1) * 16
                    r5_buf[dst_off:dst_off + 32] = source[src_spr + pair * 16:src_spr + pair * 16 + 32]
            if gfx_id == 0x12:
                # Dismounted Rebonack ($50..$5E) -> unused slots $DB..$E9 in bank 179.
                for pair in range(0x50, 0x60, 2):
                    dst_off = (pair + 0x8B - 0xC1) * 16
                    r5_buf[dst_off:dst_off + 32] = source[src_spr + pair * 16:src_spr + pair * 16 + 32]
            if gfx_id in (0x0A, 0x14):
                src_even = CHR_OFFSET + gfx_id * 4096
                src_tile = 0xCE if gfx_id == 0x0A else 0xDC
                dst_off = (0xEE - 0xC0) * 16
                r5_buf[dst_off:dst_off + 32] = source[src_even + src_tile * 16:src_even + src_tile * 16 + 32]
            if gfx_id == 0x16:
                for pair in (0x9E, 0xA0, 0xA2):
                    dst_off = (pair + 0x4B - 0xC1) * 16
                    r5_buf[dst_off:dst_off + 32] = source[src_spr + pair * 16:src_spr + pair * 16 + 32]
            ext_chr[(r5_bank - 128) * 1024:(r5_bank - 127) * 1024] = r5_buf
    if waldo_portal:
        sv_hat_tall_rows = (
            '33100000',
            '33113000',
            '13113300',
            '13133110',
            '31100110',
            '11301111',
            '00001111',
            '00000110',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
            '00000000',
        )
        sv_hat_tall = encode_tile(sv_hat_tall_rows[:8]) + encode_tile(sv_hat_tall_rows[8:])
        for bank in (0, 2, 4, 6, 8, 10, 12, 16, 18, 20, 22, 24):
            hat_off = CHR_OFFSET + bank * 4096 + 0x5E * 16
            overlay.put(hat_off, sv_hat_tall, source[hat_off:hat_off + 32],
                        f'CHR {bank:02X}: tall Waldo hat + puffball at $5E')

        # Cross-game cosmetic trophy OAM tiles: $78/$7A/$7C in non-town side-view banks,
        # $F8/$FA/$FC in town bank 6 (keeping town $78/$7A/$7C shout glyphs untouched).
        trophy_tiles = (
            (0x78, 0xF8, (
                '..1111..',
                '.133331.',
                '.123321.',
                '11222211',
                '12222221',
                '12233221',
                '.111111.',
                '00000000',
            )),
            (0x7A, 0xFA, (
                '..111...',
                '.12321..',
                '..121...',
                '..121...',
                '.12221..',
                '.12221..',
                '..121...',
                '...1....',
            )),
            (0x7C, 0xFC, (
                '00000000',
                '.111111.',
                '11233211',
                '11222211',
                '11233211',
                '.111111.',
                '00000000',
                '00000000',
            )),
        )
        blank8 = ('00000000',) * 8
        for sv_pair, town_pair, rows8 in trophy_tiles:
            norm_rows = tuple(r.replace('.', '0') for r in rows8)
            tile_bytes = encode_tile(norm_rows) + encode_tile(blank8)
            for bank, pair_id in [(b, sv_pair) for b in (0, 2, 4, 8, 10, 12, 16, 18, 20, 22, 24)] + [(6, town_pair)]:
                t_off = CHR_OFFSET + bank * 4096 + pair_id * 16
                overlay.put(t_off, tile_bytes, source[t_off:t_off + 32],
                            f'CHR {bank:02X}: cosmetic trophy tile at ${pair_id:02X}')

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
    nmi_tail = 0xC19F if boss_meter == 'souls' else 0xC19D
    stray = [x for x in nmi_branches(target, nmi_tail + 1, 0xC1B5)
             if not (boss_meter == 'souls' and x == (0xC196, 0xC1B3))]
    if [a for a, _ in nmi_branches(source, 0xC1A8, 0xC1A8)] != [0xC155, 0xC162, 0xC167] \
            or stray \
            or [t for _, t in nmi_branches(target, nmi_tail, nmi_tail)] != [nmi_tail] * 3:
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
    chr_base = CHR_OFFSET
    if waldo_portal:
        import build_waldo
        import f13_build
        import pack_waldo
        import portal_pool
        waldo_bytes = build_waldo.build().read_bytes()
        f13_bytes = f13_build.build().read_bytes() if f13_build.SOURCE_ROM.is_file() else None
        assignments = portal_pool.build_portal_assignments(
            include_f13=(f13_bytes is not None),
            roms_dir=ROOT / 'roms',
        )
        target_buf = bytearray(target)
        portal_pool.patch_portal_tables(target_buf, labels, assignments, prg_offset)
        portal_pool.write_portal_manifest(output / 'portal-manifest.json', assignments)
        target = pack_waldo.pack_combined(bytes(target_buf), labels['BarbaWaldoRestore6'], waldo_bytes,
                                          alternate_laugh_data, f13=f13_bytes,
                                          extra_ids=[a.subgame.id for a in assignments],
                                          roms_dir=ROOT / 'roms')
        prg_16k = ((target[9] & 0x0F) << 8) | target[4]
        chr_base = CHR_OFFSET + prg_16k * 16384 - 128 * 1024
    patch = encode(source, target, 'Zelda II - Barba Edition | development alpha',
                   [(chr_base+30*4096+len(ow), CHR_OFFSET+16*4096+len(ow), 0x60*16-len(ow)),
                    (chr_base+30*4096+0x64*16, CHR_OFFSET+16*4096+0x64*16, (0x68-0x64)*16),
                    (chr_base+30*4096+0x6C*16, CHR_OFFSET+16*4096+0x6C*16, (0xD0-0x6C)*16),
                    (chr_base+30*4096+0xE4*16, CHR_OFFSET+16*4096+0xE4*16, (0x180-0xE4)*16),
                    (chr_base+30*4096+0x188*16, CHR_OFFSET+16*4096+0x188*16, (0x19E-0x188)*16),
                    (chr_base+30*4096+0x1B0*16, CHR_OFFSET+16*4096+0x1B0*16, 8192-0x1B0*16)])
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
    changed_bytes = sum(a != b for a, b in zip(source, target)) + max(0, len(target) - len(source))
    patch_groups: dict[str, dict[str, int]] = {}
    for entry in overlay.ranges:
        grp = entry.get('group', 'barba_core')
        bucket = patch_groups.setdefault(grp, {'count': 0, 'bytes': 0})
        bucket['count'] += 1
        bucket['bytes'] += entry['length']
    report = {'stage': 'development alpha', 'source_sha256': SOURCE_SHA256,
              'output_sha256': hashlib.sha256(target).hexdigest(),
              'size': len(target), 'changed_bytes': changed_bytes,
              'labels': labels, 'patch_groups': patch_groups,
              'patches': sorted(overlay.ranges, key=lambda r: r['offset'])}
    if roar_info:
        report['title_roar_prototype'] = roar_info
    output_dir = output.resolve()
    if output_dir.is_relative_to(ROOT):
        output_dir = output_dir.relative_to(ROOT)
    record_build(HISTORY_FILE, output, report, {
        'output_dir': output_dir.as_posix(),
        'bps_sha256': hashlib.sha256(patch).hexdigest(),
        'audio': 'sampled' if title_roar_wav else 'native',
        'waldo_portal': waldo_portal,
        'boss_meter': boss_meter,
        'game_over_portrait': game_over_portrait,
        'game_over_laughs': game_over_laughs,
        'git_commit': git_commit,
        'git_dirty': git_dirty,
        'release': release,
    })
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, default=ROOT/'roms/z2.nes')
    parser.add_argument('--out', type=Path, default=ROOT/'build')
    parser.add_argument('--title-roar-wav', type=Path, default=ROOT/'assets/roar.wav',
                        help='Local PCM roar WAV (default: assets/roar.wav)')
    parser.add_argument('--native-audio', action='store_true',
                        help='Build the legacy noise roar and five distinct Game Over laughs')
    parser.add_argument('--no-portals', dest='waldo_portal', action='store_false',
                        help='Build without crossover subgame portals (smaller shareable patch)')
    parser.add_argument('--no-waldo', dest='waldo_portal', action='store_false',
                        help=argparse.SUPPRESS)
    parser.add_argument('--boss-meter', choices=('vanilla', 'souls'), default='souls',
                        help='Boss health meter style: vanilla (8 left pips) or souls (bottom bar, default)')
    parser.add_argument('--no-game-over-portrait', dest='game_over_portrait', action='store_false',
                        help='Keep vanilla Ganon Game Over silhouette and subtitle')
    parser.add_argument('--no-game-over-laughs', dest='game_over_laughs', action='store_false',
                        help='Keep vanilla Game Over DPCM laugh cues')
    parser.add_argument('--release', metavar='VERSION',
                        help='Associate a release version with this build in the local history')
    args = parser.parse_args()
    try:
        report = build(args.rom, args.out, None if args.native_audio else args.title_roar_wav,
                       waldo_portal=args.waldo_portal, boss_meter=args.boss_meter,
                       game_over_portrait=args.game_over_portrait,
                       game_over_laughs=args.game_over_laughs,
                       release=args.release)
    except (ValueError, OSError, sqlite3.Error, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Build failed: {error}\n')
    print(f"Build #{report['build_number']}: {args.out/'barba.nes'} "
          f"({report['changed_bytes']:,} changed bytes)")
    print(f"BPS patch verified; SHA-256 {report['output_sha256']}")
