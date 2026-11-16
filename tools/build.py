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
                    compile_assets, compile_castle_fire,
                    compile_castle_shout_glyphs, compile_file_select_doll,
                    compile_shout_glyphs, compile_title_logo, compile_town_fire)
from bps import apply, encode
from boss_art import compile_lava_link
from nes import CHR_OFFSET, SOURCE_SHA256, encode_tile, load_source, prg_offset

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


def assemble(output: Path) -> dict[str, int]:
    def find(name: str) -> str:
        local = ROOT / f'.tools/cc65/bin/{name}.exe'
        result = str(local) if local.exists() else shutil.which(name)
        if not result:
            raise ValueError(f'{name} is missing. Install cc65; see docs/BUILD.md.')
        return result
    subprocess.run([find('ca65'), str(ROOT/'src/barba.asm'), '-I', str(ROOT/'src'), '-g', '-o', 'barba.o'], cwd=output, check=True)
    subprocess.run([find('ld65'), '-C', str(ROOT/'src/barba.cfg'), 'barba.o',
                    '-Ln', 'barba.lbl', '-m', 'barba.map', '--dbgfile', 'barba.dbg'], cwd=output, check=True)
    labels = {}
    for line in (output/'barba.lbl').read_text().splitlines():
        _, address, label = line.split()
        if not label.startswith('.@'):
            labels[label.lstrip('.')] = int(address, 16)
    return labels


def build(source_path: Path, output: Path) -> dict:
    source = load_source(source_path)
    if output.resolve() == source_path.parent.resolve():
        raise ValueError('Output must not be the source ROM directory')
    output.mkdir(parents=True, exist_ok=True)
    # Asset compilation emits the tile-index include consumed by ca65. Complete
    # it before assembling so the ROM and renderer always share one layout.
    mapping, graphics, ow, _ = compile_assets(ROOT, source_path)
    labels = assemble(output)
    overlay = Overlay(source)
    # FarCall0 identifies the ACTUAL mapped bank without touching the native
    # mapper path (and without mistaking the area-bank variable for a shadow).
    fingerprints = bytes.fromhex('f0 7d 60 2e 91 2f 00 c9')
    for bank, expected in enumerate(fingerprints):
        offset = prg_offset(bank, 0x8506 if bank < 7 else 0xC506)
        if source[offset] != expected:
            raise ValueError(f'FarCall0 bank fingerprint changed: {bank}')
    for filename, bank, address in [('code', 0, 0xAA40), ('bank0-ow', 0, 0xA89E), ('bank0-tail', 0, 0xBFE0),('lava', 7, 0xD39A), ('terrain', 7, 0xFF4C), ('town', 3, 0xB803), ('gateway', 7, 0xFEAA), ('bank6', 6, 0xBA00), ('bank5', 5, 0xBDE0), ('bank1', 1, 0x9EB9)]:
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
    hook(0, 0x84F2, 'BarbaOverworldA', 0x4C, 'a5 f5 29 80 f0 1a', 3)
    hook(7, 0xD52D, 'BarbaDisplay', 0x20, '20 f0 eb')
    hook(7, 0xE0A4, 'LavaSurface', 0x4C, 'a9 01 85')
    hook(7, 0xD4FE, 'BarbaPreEnemy', 0x20, '20 25 99')
    hook(7, 0xD535, 'BarbaBlocks', 0x20, '20 dd e1')
    hook(7, 0xD50D, 'BarbaUpdate', 0x20, '20 47 98')
    hook(7, 0xE48B, 'EnemyFireGateway', 0x4C, 'b5 b6 c9 01', 1)
    hook(7, 0xE617, 'ShieldFireGateway', 0x4C, 'a5 c8 0a')
    hook(5, 0x9A7F, 'DarkBarbaDraw', 0x20, '20 02 ec')
    hook(5, 0x9BB1, 'DarkBarbaTriforcePose', 0x4C, 'a9 0b 85 80 e6 af 4c 11 ef', 6)
    lag_dest = labels['LagNmiBank6']
    overlay.prg(7, 0xC065, bytes.fromhex('ad 06 85 48') + bytes([0x4C, lag_dest & 255, lag_dest >> 8]),
                bytes.fromhex('a9 06 20 cc ff 20 00'), 'Lag-frame NMI bank preservation')
    overlay.prg(7, 0xE6E2, bytes.fromhex('4c f3 e6 ea'), bytes.fromhex('29 20 f0 0d'),
                'Allow fireballs against sword-only enemies')
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
    dest = labels['TownUpdate']
    overlay.prg(3, 0x949F, dest.to_bytes(2, 'little'), bytes.fromhex('78 98'),
                'Indoor NPC update 949F')
    overlay.prg(3, 0x94AB, dest.to_bytes(2, 'little'), bytes.fromhex('a9 97'),
                'Wise Man NPC update 94AB')
    overlay.prg(3, 0x94CF, dest.to_bytes(2, 'little'), bytes.fromhex('bd 9a'),
                'Special NPC update 94CF')
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
    overlay.prg(5, 0xA8CF, bytes.fromhex('4c ae a5 ea'), bytes.fromhex('a2 6b a5 12'), 'Title Barba animate hook')
    overlay.prg(
        5, 0xA54F,
        bytes.fromhex(
            'ad 1c 02 c9 7f d0 38 a5 12 c9 40 90 1e c9 60 b0 1a '
            'c9 48 90 12 f0 06 c9 58 b0 0c 90 06 '
            '20 9e a5 ea ea ea '   # jsr TitleRoarStart (was the fireball SFX)
            'a2 02 d0 06 a2 01 d0 02 a2 00 '
            'bd 95 a5 8d 1d 02 bd 98 a5 8d 21 02 bd 9b a5 8d 3d 02 '
            'a2 6b a5 12 4c d3 a8 '
            '00 1a 1e 02 1c 20 04 04 22'
        ),
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
    overlay.prg(5, 0xA59E, title_roar, b'\xff' * len(title_roar), 'Title Barba roar')
    # Game Over screen: replace "RETURN OF GANON" ($8010, 15 bytes) with "LINK KEEPS LAVA".
    overlay.prg(
        0, 0x8010,
        bytes(0xF4 if ch == ' ' else 0xDA + ord(ch) - ord('A') for ch in 'LINK KEEPS LAVA'),
        bytes.fromhex('ebdeedeeebe7f4e8dff4e0dae7e8e7'),
        'Game Over Barba subtitle',
    )
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
    # In his visible window ($AF $E0-$EF, $AEB2) the $E4D9 call goes to CarockHit ($A7B0, bank-4 pad):
    # JSR $DE63 runs the native projectile check ($E48B, Barba's fireball gateway), the sword check, then
    # the same $E4D9. A kill there leaves the generic death state ($B6 = 2), which would draw Carock into
    # OAM 0 (the HUD sprite-0 split) and hang the NMI; so on a kill call $B1F6, the native boss-death
    # bookkeeping that $B1E9 runs after a Reflect kill. Teleport/fade phases stay untouchable; Reflect path unchanged.
    overlay.prg(
        4, 0xA7B0,
        # JSR $DE63 / LDX $10 / LDA $B6,X / CMP #1 / BEQ +3 / JSR $B1F6 / RTS
        bytes.fromhex('20 63 de a6 10 b5 b6 c9 01 f0 03 20 f6 b1 60'),
        b'\xff' * 15,
        'CarockHit helper',
    )
    overlay.prg(4, 0xAEB4, bytes.fromhex('20 b0 a7'), bytes.fromhex('20 d9 e4'), 'Carock fireball hit check')

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
    # Ending toast finale ($8CEB..$8D4D + @ash at $8F6F -> $8B4A):
    # When the curtain reaches $22A0 (covering Barba's head), Barba fires a behind-curtain fireball
    # (attr $20) that drops below the curtain into view right before hitting Zelda and turning her to ash.
    overlay.prg(
        5, 0x8F6F,
        bytes.fromhex(
            'a9 f8 8d 30 02 8d 34 02 8d 40 02 '
            'a9 5e 8d 39 02 a9 62 8d 3d 02 '
            'a9 22 8d 3a 02 8d 3e 02 '
            '4c f7 93'
        ),
        source[prg_offset(5, 0x8F6F):prg_offset(5, 0x8F6F + 32)],
        'Ending Zelda-to-ash helper',
    )
    overlay.prg(
        5, 0x93F7,
        bytes.fromhex('a9 c8 8d 38 02 8d 3c 02 60'),
        b'\xff' * 9,
        'Ending Zelda-to-ash Y=$C8 tail',
    )
    ending_toast = bytes.fromhex(
        # $8CEB:
        'ad f8 05 d0 27 '                  # lda $05F8; bne @not_idle (+$27)
        'ad 61 07 c9 06 d0 1f '            # lda $0761; cmp #6; bne @done (+$1F)
        'a5 27 c9 22 d0 19 '               # lda $27; cmp #$22; bne @done (+$19)
        'a5 28 c9 a0 90 13 '               # lda $28; cmp #$A0; bcc @done (+$13)
        'ee f8 05 '                        # inc $05F8 (start fire)
        'a9 aa 8d f9 05 '                  # lda #$AA; sta $05F9 (Y)
        'a9 72 8d fa 05 '                  # lda #$72; sta $05FA (X)
        'a5 ed 09 40 85 ed '               # lda $ED; ora #$40; sta $ED (SFX)
        '60 '                              # @done: rts
        # @not_idle ($8D17):
        'c9 01 d0 2a '                     # cmp #1; bne @ash (+$2A -> jmp $8F6F)
        'ee f9 05 '                        # inc $05F9 (Y += 1)
        'a5 12 29 01 f0 03 ee fa 05 '      # odd frame: X += 1
        'ad f9 05 c9 bc b0 14 '            # cmp #$BC; bcs @hit (+$14)
        '8d 40 02 a9 32 8d 41 02 '         # OAM $0240: Y, tile $32
        'a9 20 8d 42 02 ad fa 05 8d 43 02 ' # attr $20 (behind BG/curtain), X
        '60 '                              # rts
        # @hit:
        'ee f8 05 '                        # inc $05F8 ($05F8 = 2)
        # @ash:
        '4c 6f 8f'                         # jmp $8F6F
    )
    assert len(ending_toast) <= 0x8D4E - 0x8CEB, f'ending_toast too big: {len(ending_toast)}'
    assert ending_toast[5 + 0x27 + 4 + 0x2a:] == bytes.fromhex('4c 6f 8f')
    overlay.prg(
        5, 0x8CEB,
        ending_toast,
        source[prg_offset(5, 0x8CEB):prg_offset(5, 0x8CEB + len(ending_toast))],
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

    target = bytes(overlay.target)
    for bank, expected in enumerate(fingerprints):
        offset = prg_offset(bank, 0x8506 if bank < 7 else 0xC506)
        if target[offset] != expected:
            raise ValueError(f'Patch overwrote FarCall0 bank fingerprint: {bank}')
    # The FF byte at FF4B is the high operand of a live JMP, not filler.
    # Keep its whole instruction untouched beside the new terrain allocation.
    anchor = prg_offset(7, 0xFF49)
    if source[anchor:anchor+3] != bytes.fromhex('4c c5 ff') or target[anchor:anchor+3] != source[anchor:anchor+3]:
        raise ValueError('Terrain allocation overlaps the native room-loader return')
    if target[:16] != source[:16] or len(target) != len(source):
        raise ValueError('Mapper/header/size invariant failed')
    # 8x16 byte T draws tiles T&$FE and T|1: town villager pairs must stay vanilla.
    for bank, pairs in TOWN_SPRITE_PAIRS.items():
        for pair in pairs:
            offset = CHR_OFFSET + bank*4096 + pair*16
            if target[offset:offset+32] != source[offset:offset+32]:
                raise ValueError(f'Patch overwrote town sprite pair CHR {bank:02X}:{pair:02X}')
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
    (output/'build-report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, default=ROOT/'roms/z2.nes')
    parser.add_argument('--out', type=Path, default=ROOT/'build')
    args = parser.parse_args()
    try:
        report = build(args.rom, args.out)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Build failed: {error}\n')
    print(f"Built {args.out/'barba.nes'} ({report['changed_bytes']:,} changed bytes)")
    print(f"BPS patch verified; SHA-256 {report['output_sha256']}")
