"""Build Barba Edition from a verified local ROM, preserving all unpatched bytes."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from assets import (ASH_TILES, SHOUT_GLYPH_BANK, SHOUT_PAIR_SHA256,
                    TITLE_CHR_BANK, TITLE_TILE_SHA256,
                    TOWN_FIRE_BANK, TOWN_FIRE_TILE_SHA256,
                    compile_assets, compile_file_select_doll,
                    compile_shout_glyphs, compile_title_logo, compile_town_fire)
from bps import apply, encode
from boss_art import compile_lava_link
from nes import CHR_OFFSET, SOURCE_SHA256, load_source, prg_offset

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
    for filename, bank, address in [('code', 0, 0xAA40), ('lava', 7, 0xD39A), ('terrain', 7, 0xFF4C), ('town', 3, 0xB803), ('gateway', 7, 0xFEAA)]:
        data = (output/f'barba-{filename}.bin').read_bytes()
        overlay.prg(bank, address, data, b'\xFF'*len(data), f'New {filename} routines')
    def hook(bank: int, address: int, label: str, opcode: int, expected: str, pad: int = 0):
        dest = labels[label]
        data = bytes([opcode, dest & 255, dest >> 8]) + b'\xEA'*pad
        overlay.prg(bank, address, data, bytes.fromhex(expected), label+' hook')
    hook(0, 0x877C, 'BarbaOverworld', 0x20, 'a2 0e a0 00', 1)
    hook(7, 0xD52D, 'BarbaDisplay', 0x20, '20 f0 eb')
    hook(7, 0xE0A4, 'LavaSurface', 0x4C, 'a9 01 85')
    hook(7, 0xD4FE, 'BarbaPreEnemy', 0x20, '20 25 99')
    hook(7, 0xD535, 'BarbaBlocks', 0x20, '20 dd e1')
    hook(7, 0xD50D, 'BarbaUpdate', 0x20, '20 47 98')
    hook(7, 0xE48B, 'EnemyFireGateway', 0x4C, 'b5 b6 c9 01', 1)
    hook(7, 0xE617, 'ShieldFireGateway', 0x4C, 'a5 c8 0a')
    overlay.prg(7, 0xE6E2, bytes.fromhex('4c f3 e6 ea'), bytes.fromhex('29 20 f0 0d'),
                'Allow fireballs against sword-only enemies')
    hook(3, 0xB5F8, 'TownDialog', 0x4C, '0a a8 ad 07 07', 2)
    hook(3, 0xB74D, 'TownLetterDelay', 0x20, 'a9 05 8d 66 05', 2)
    hook(3, 0xB65E, 'TownLineDelay', 0x20, '8c 66 05')
    for address in (0x94B3, 0x94B5, 0x94B7, 0x94B9, 0x94BB, 0x94BD):
        dest = labels['TownUpdate']
        overlay.prg(3, address, dest.to_bytes(2, 'little'), bytes.fromhex('d4 97'),
                    f'Static outdoor villager update {address:04X}')
    for address in (0x94BF, 0x94C1, 0x94C3, 0x94C5, 0x94C7, 0x94C9, 0x94CB, 0x94CD):
        dest = labels['TownUpdate']
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
    # File Select save-slot dolls: CHR bank 0 tile $D0/$D1.
    doll = compile_file_select_doll(ROOT)
    doll_offset = CHR_OFFSET + 0xD0 * 16
    overlay.put(doll_offset, doll, source[doll_offset:doll_offset+32], 'CHR 00: File Select Barba doll')
    # Villager shout words: town CHR bank 7 only (odd 8x16 sprite tiles).
    glyphs = compile_shout_glyphs(ROOT, source)
    if set(glyphs) != set(SHOUT_PAIR_SHA256):
        raise ValueError('Shout glyph pairs differ from the audited allocation')
    for pair, data in sorted(glyphs.items()):
        offset = CHR_OFFSET + SHOUT_GLYPH_BANK*4096 + pair*16
        original = source[offset:offset+32]
        if hashlib.sha256(original).hexdigest()[:16] != SHOUT_PAIR_SHA256[pair]:
            raise ValueError(f'Shout glyph pair {pair:02X} is not the audited original')
        overlay.put(offset, data, original, f'CHR {SHOUT_GLYPH_BANK:02X}: shout glyph pair {pair:02X}')
    # Town scorch marks: flame and char 2x2 BG art in town CHR bank 7 (ScorchTiles in src/blocks.inc).
    for tile, data in sorted(compile_town_fire(ROOT).items()):
        offset = CHR_OFFSET + TOWN_FIRE_BANK*4096 + tile*16
        original = source[offset:offset+16]
        if hashlib.sha256(original).hexdigest()[:16] != TOWN_FIRE_TILE_SHA256[tile]:
            raise ValueError(f'Town fire tile {tile:02X} is not the audited original')
        overlay.put(offset, data, original, f'CHR {TOWN_FIRE_BANK:02X}: town fire tile {tile:02X}')
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

    # Existing menu stores 14-byte rows. Preserve border, cost digits and spacing.
    for i, name in enumerate(['SCALES','JUMP','LIFE','WYRMLNG','FIRE','REFLECT','SPELL','INFERNO']):
        offset = prg_offset(0, 0x9C2A + i*14)
        data = bytes(0xDA+ord(c)-ord('A') for c in name.ljust(7) if c != ' ')
        data += b'\xCF'*(7-len(data))
        overlay.put(offset, data, source[offset:offset+7], f'Spell menu: {name}')

    # Palace 6 "Lava Link" boss: Link art in CHR bank 25, Spear (05) sword beams, Link palette.
    for tile_id, pair_bytes in compile_lava_link(source).items():
        offset = CHR_OFFSET + 25*4096 + tile_id*16
        overlay.put(offset, pair_bytes, source[offset:offset+32], f'Lava Link CHR bank 25 pair {tile_id:02X}')
    overlay.prg(4, 0xB19B, b'\x05', b'\x04', 'Lava Link sword-beam breath (05)')
    overlay.prg(4, 0xAABB, b'\x01', b'\x00', 'Lava Link sword-beam palette (1)')
    overlay.prg(4, 0xB11F, bytes.fromhex('20 65 a7'), bytes.fromhex('20 0d b2'), 'Lava Link palette hook')
    overlay.prg(
        4, 0xA765,
        # Ends in JMP LavaLinkHurt ($A795), which then continues to the original $B20D.
        bytes.fromhex('ad 99 04 d0 21 ad 28 07 f0 1c ad 25 07 d0 17 ad 01 03 d0 12 a0 00 b9 8e a7 99 02 03 c8 c0 07 d0 f5 a9 06 8d 01 03 4c 95 a7'),
        b'\xff' * 41,
        'Lava Link palette helper',
    )
    overlay.prg(4, 0xA78E, bytes.fromhex('3f 15 03 18 36 2a ff'), b'\xff' * 7, 'Lava Link palette packet')
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
    # Lava Link shield experiment (producer, 2026-11-14). The boss hit check at $B1F3 (JSR $DE40, shared
    # with other bank-4 enemies) now calls LavaLinkShield ($A7A9). Code $21 (Lava Link) is vulnerable only
    # in the hold phase ($0499 = 2) while its timer is $30-$5F: the half/open-mouth heads around the beam
    # window ($40-$4F). Otherwise the closed head holds the shield up: HP is lifted to $FF around $DE40, so a
    # hit can never kill, then HP is restored, the hit flash ($040E = $30) is cleared, the enemy-hit SFX bit
    # dropped and the shield clank ($EC = 2, as bank 7 $E654) plays. Other enemies JMP $DE40 unchanged.
    overlay.prg(4, 0xB1F3, bytes.fromhex('20 a9 a7'), bytes.fromhex('20 40 de'), 'Lava Link shield hook')
    overlay.prg(
        4, 0xA7A9,
        bytes.fromhex(
            'b5 a1 c9 21 d0 37'          # LDA $A1,X / CMP #$21 / BNE open
            'ad 99 04 c9 02 d0 0a'       # LDA $0499 / CMP #$02 / BNE shielded
            'bd 04 05 38 e9 30 c9 30 90 26'  # LDA $0504,X / SEC / SBC #$30 / CMP #$30 / BCC open
            'b5 c2 48 a9 ff 95 c2'       # shielded: save HP, HP = $FF
            '20 40 de a6 10 68 95 c2'    # JSR $DE40 / LDX $10 / restore HP
            'bd 0e 04 c9 30 d0 0f'       # fresh hit? ($040E,X == $30)
            'a9 00 9d 0e 04'             # no flash
            'a5 ed 29 ef 85 ed'          # drop enemy-hit SFX
            'a9 02 85 ec'                # shield clank
            '60'                         # RTS
            '4c 40 de'                   # open: JMP $DE40
        ),
        b'\xff' * 64,
        'Lava Link shield',
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
    patch = encode(source, target, 'Zelda II - Barba Edition | development alpha',
                   [(CHR_OFFSET+30*4096+len(ow), CHR_OFFSET+16*4096+len(ow), 8192-len(ow))])
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
