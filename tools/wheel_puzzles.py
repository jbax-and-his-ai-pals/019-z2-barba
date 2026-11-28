"""Zelda II & Barba Universe puzzles, categories, contestants, and text for Wheel of Barba."""

from __future__ import annotations

# 12 category 8-byte NUL-terminated slots at Bank 0 $911C-$917B.
# Category 3 prints slot 3 + slot 10; Category 9 prints slot 9 + slot 11.
WHEEL_BARBA_CATEGORIES: list[str] = [
    'PLACE',     # 0
    'BOSS',      # 1
    'ITEM',      # 2
    'PLACE',     # 3 (unused compound slot)
    'PHRASE',    # 4
    'ITEM',      # 5 (unused)
    'PLACE',     # 6 (unused)
    'ENEMY',     # 7
    'SPELL',     # 8
    'ENEMY',     # 9 (unused compound slot)
    'PLACE',     # 10 (unused suffix for cat 3)
    'ENEMY',     # 11 (unused suffix for cat 9)
]

# 97 curated Zelda II puzzles (all lines <= 12 chars, all puzzles >= 4 letters).
# Active Category IDs: 0=PLACE, 1=BOSS, 2=ITEM, 4=PHRASE, 7=ENEMY, 8=SPELL
WHEEL_BARBA_PUZZLES: list[tuple[int, list[str]]] = [
    # 0: PLACE (20)
    (0, ['PARAPA', 'PALACE']),
    (0, ['MIDORO', 'PALACE']),
    (0, ['ISLAND', 'PALACE']),
    (0, ['MAZE ISLAND', 'PALACE']),
    (0, ['OCEAN PALACE']),
    (0, ['THREE-EYE', 'ROCK PALACE']),
    (0, ['THE GREAT', 'PALACE']),
    (0, ['DEATH', 'MOUNTAIN']),
    (0, ['TOWN OF', 'RAURU']),
    (0, ['TOWN OF', 'RUTO']),
    (0, ['TOWN OF', 'SARIA']),
    (0, ['TOWN OF', 'MIDO']),
    (0, ['TOWN OF', 'NABOORU']),
    (0, ['TOWN OF', 'DARUNIA']),
    (0, ['NEW KASUTO']),
    (0, ['OLD KASUTO']),
    (0, ['BAGUS CABIN']),
    (0, ['MORUGE SWAMP']),
    (0, ['SPECTACLE', 'ROCK']),
    (0, ['KINGS TOMB']),
    # 1: BOSS (8)
    (1, ['HORSEHEAD']),
    (1, ['HELMETHEAD']),
    (1, ['REBONACK']),
    (1, ['CAROCK']),
    (1, ['GOOMA']),
    (1, ['BARBA']),
    (1, ['THUNDERBIRD']),
    (1, ['DARK LINK']),
    # 7: ENEMY (40)
    (7, ['ORANGE', 'IRONKNUCKLE']),
    (7, ['RED', 'IRONKNUCKLE']),
    (7, ['BLUE', 'IRONKNUCKLE']),
    (7, ['ORANGE', 'MOBLIN']),
    (7, ['RED MOBLIN']),
    (7, ['BLUE MOBLIN']),
    (7, ['ORANGE', 'GORIYA']),
    (7, ['RED GORIYA']),
    (7, ['BLUE GORIYA']),
    (7, ['ORANGE DAIRA']),
    (7, ['RED DAIRA']),
    (7, ['ORANGE GERU']),
    (7, ['RED GERU']),
    (7, ['BLUE GERU']),
    (7, ['RED OCTOROK']),
    (7, ['BLUE OCTOROK']),
    (7, ['RED STALFOS']),
    (7, ['BLUE STALFOS']),
    (7, ['RED DEELER']),
    (7, ['BLUE DEELER']),
    (7, ['RED MOA']),
    (7, ['BLUE MOA']),
    (7, ['ORANGE', 'WIZZROBE']),
    (7, ['RED FOKKA']),
    (7, ['BLUE FOKKA']),
    (7, ['FOKKERU']),
    (7, ['BAGO-BAGO']),
    (7, ['FIRE', 'BAGO-BAGO']),
    (7, ['GELDARM']),
    (7, ['TEKTITE']),
    (7, ['LEEVER']),
    (7, ['LOWDER']),
    (7, ['ACHE']),
    (7, ['ACHEMAN']),
    (7, ['BUBBLE']),
    (7, ['MOBY']),
    (7, ['PARUTAMU']),
    (7, ['ANERU']),
    (7, ['MAGO']),
    (7, ['KOBOLD']),
    # 2: ITEM (12)
    (2, ['HANDY GLOVE']),
    (2, ['MAGIC CANDLE']),
    (2, ['CROSSING', 'RAFT']),
    (2, ['WATER BOOTS']),
    (2, ['MYSTIC FLUTE']),
    (2, ['MAGIC HAMMER']),
    (2, ['MAGIC KEY']),
    (2, ['CROSS']),
    (2, ['HEART', 'CONTAINER']),
    (2, ['MAGIC', 'CONTAINER']),
    (2, ['LINK DOLL']),
    (2, ['RED POTION']),
    # 8: SPELL (7)
    (8, ['SHIELD']),
    (8, ['JUMP']),
    (8, ['LIFE']),
    (8, ['FAIRY']),
    (8, ['FIRE']),
    (8, ['REFLECT']),
    (8, ['THUNDER']),
    # 4: PHRASE (10)
    (4, ['I AM ERROR']),
    (4, ['RETURN OF', 'GANON']),
    (4, ['THE', 'ADVENTURE', 'OF LINK']),
    (4, ['BAGU IS MY', 'NAME']),
    (4, ['EASTMOST', 'PENNINSULA']),
    (4, ['THANKS A', 'MILLION']),
    (4, ['DOWNWARD', 'THRUST']),
    (4, ['UPWARD', 'THRUST']),
    (4, ['TRIFORCE OF', 'COURAGE']),
    (4, ['AWAKEN', 'PRINCESS', 'ZELDA']),
]

assert len(WHEEL_BARBA_PUZZLES) == 97

WHEEL_BARBA_CONTESTANTS: list[str] = [
    'DARK LINK ',
    'BARBA     ',
    'ZELDA     ',
    'LINK      ',
    'ERROR     ',
    'BAGU      ',
    'RAURU     ',
    'THNDRBIRD ',
    'CAROCK    ',
    'GOOMA     ',
    'REBONACK  ',
    'HORSEHEAD ',
    'HELMETHD  ',
    'WIZZROBE  ',
    'LIZALFOS  ',
    'IRONKNKL  ',
    'DARUNIA   ',
    'SARIA     ',
    'NABOORU   ',
    'KASUTO    ',
]


def _encode_cat_tile(text: str) -> bytes:
    """Encode a <=7-char uppercase string as an 8-byte Bank 0 category slot."""
    assert 1 <= len(text) <= 7 and text.isalpha() and text.isupper(), f'Bad category {text!r}'
    bs = bytes(0xE5 + ord(c) - ord('A') for c in text)
    return bs + b'\x00' * (8 - len(bs))


def _encode_msg_tile(text: str, *, space: int = 0xD4, digit_base: int = 0xD5) -> bytes:
    """Encode Wheel Bank 0 tile string ('A'-'Z'->$E5..$FE, space->$D4 or $00, '0'-'9'->digit_base)."""
    out = bytearray()
    for ch in text:
        if ch == ' ':
            out.append(space)
        elif 'A' <= ch <= 'Z':
            out.append(0xE5 + ord(ch) - ord('A'))
        elif '0' <= ch <= '9':
            out.append(digit_base + ord(ch) - ord('0'))
        elif ch == '?':
            out.append(0xDA)
        elif ch == '!':
            out.append(0xDF)
        elif ch == '\'':
            out.append(0x00)
        else:
            raise ValueError(f'Unsupported message char: {ch!r}')
    return bytes(out)


def _encode_puzzle(cat_id: int, lines: list[str]) -> bytes:
    """Encode one puzzle in Bank 2 native format (bit 7 on last char of each line + cat_id)."""
    assert 0 <= cat_id < 10
    assert 1 <= len(lines) <= 4
    out = bytearray()
    for line in lines:
        assert 1 <= len(line) <= 12, f'Line too long ({len(line)}): {line!r}'
        for idx, ch in enumerate(line):
            assert ('A' <= ch <= 'Z') or ch in (" ", "-", "'"), f'Bad puzzle char {ch!r}'
            b = ord(ch)
            if idx == len(line) - 1:
                b |= 0x80
            out.append(b)
    out.append(cat_id)
    return bytes(out)


def apply_puzzle_patches_bank0(b0: bytearray) -> None:
    """Patch Bank 0 categories, contestant names, title board, and UI text for Wheel of Barba."""
    def patch(addr: int, new: bytes, expected: bytes | None = None) -> None:
        off = addr - 0x8000
        if expected is not None:
            assert bytes(b0[off : off + len(expected)]) == expected, (
                f'Unexpected Bank 0 bytes at ${addr:04X}: {bytes(b0[off : off + len(expected)]).hex(" ")}'
            )
        b0[off : off + len(new)] = new

    # 1. Categories at $911C-$917B (12 x 8 bytes) and OAM cursor start offsets ($9C47-$9C50)
    cat_blob = b''.join(_encode_cat_tile(c) for c in WHEEL_BARBA_CATEGORIES)
    assert len(cat_blob) == 96
    patch(0x911C, cat_blob)
    # $9C47[cat] = 4 + 4 * total_printed_chars (reserves OAM slots 1..N for the category banner)
    oam_offsets = []
    for cid in range(10):
        nchars = len(WHEEL_BARBA_CATEGORIES[cid])
        if cid == 3:
            nchars += len(WHEEL_BARBA_CATEGORIES[10])
        elif cid == 9:
            nchars += len(WHEEL_BARBA_CATEGORIES[11])
        oam_offsets.append(4 + 4 * nchars)
    patch(0x9C47, bytes(oam_offsets), bytes.fromhex('181c18381c1c181c183c'))

    # 2. Contestant preset names at $B45E-$B525 (20 x 10 bytes)
    names_blob = b''.join(n.encode('ascii') for n in WHEEL_BARBA_CONTESTANTS)
    assert len(names_blob) == 200
    patch(0xB45E, names_blob)

    # 2b. Bias CPU name picker ($B3EC-$B405): on first attempt ($0412,X == $C5), pick
    #     idx 0 ('DARK LINK ') for CPU1 ($14==$0A) and idx 1 ('BARBA     ') for CPU2 ($14==$14).
    #     Falls back to random ($0B & $0F) if that slot collided with a human player's name.
    #     Original $B3EC..$B405 is 26 bytes:
    #       a5 0b 29 0f 85 19 a5 0c 29 03 18 65 19 a5 0c 2a 2a 29 01 18 65 19 c5 18 f0 df
    picker = bytes.fromhex(
        'bd 12 04 '     # LDA $0412,X
        'c9 c5 '        # CMP #$C5 (still untouched?)
        'd0 0a '        # BNE fallback
        'a9 00 '        # LDA #$00 (DARK LINK)
        'e0 0a '        # CPX #$0A
        'f0 0a '        # BEQ store
        'a9 01 '        # LDA #$01 (BARBA)
        'd0 06 '        # BNE store
        # fallback:
        'a5 0b '        # LDA $0B
        '29 0f '        # AND #$0F
        'c5 18 '        # CMP $18
        'f0 f8 '        # BEQ fallback (re-check/wait - wait $0B doesn't change inside loop without $8726!)
    )
    # Wait: if fallback loops back to $B3E7 (which calls JSR $8726 advancing $0B!), it must branch to $B3E7 (-29?):
    # Offset of $B3E7 from $B406 is 0xB3E7 - 0xB406 = -31 = 0xE1!
    picker = bytes.fromhex(
        'bd 12 04 '     # $B3EC: LDA $0412,X
        'c9 c5 '        # $B3EF: CMP #$C5
        'd0 0a '        # $B3F1: BNE fallback ($B3FD)
        'a9 00 '        # $B3F3: LDA #$00 (DARK LINK)
        'e0 0a '        # $B3F5: CPX #$0A
        'f0 0a '        # $B3F7: BEQ $B403 -> Wait: $B3F7+2+10 = $B403!
        'a9 01 '        # $B3F9: LDA #$01 (BARBA)
        'd0 06 '        # $B3FB: BNE $B403 -> $B3FB+2+6 = $B403!
        # fallback ($B3FD):
        'a5 0b '        # $B3FD: LDA $0B
        '29 0f '        # $B3FF: AND #$0F
        'c5 18 '        # $B401: CMP $18
        'f0 e2 '        # $B403: BEQ $B3E7 ($B403+2 - 30 = $B3E7) -> Wait: skip CMP if direct!
    )
    # Wait: if $B3F7 branches to $B405 (the next byte after $B404, wait $B406 is STA $18!):
    # Let's place CMP $18 at $B401 (2B), BEQ $B3E7 at $B403 (2B) -> total 25 bytes ($B3EC..$B404), pad 1 NOP at $B405!
    # Wait: if BEQ is at $B403, then $B3F7 must jump to $B406 (past BEQ!), skipping CMP $18?
    # No, CMP $18 at $B401 checks $18 != A (fine if $18 was initialized or wait: skip CMP $18 on first try?):
    # Layout exact 26 bytes ($B3EC..$B405):
    #   $B3EC: bd 12 04 (3) LDA $0412,X
    #   $B3EF: c9 c5    (2) CMP #$C5
    #   $B3F1: d0 0a    (2) BNE $B3FD
    #   $B3F3: a9 00    (2) LDA #$00
    #   $B3F5: e0 0a    (2) CPX #$0A
    #   $B3F7: f0 0c    (2) BEQ $B405 (after fallback? Wait $B3F7+2+12 = $B405!)
    #   $B3F9: a9 01    (2) LDA #$01
    #   $B3FB: d0 08    (2) BNE $B405 ($B3FB+2+8 = $B405!)
    #   $B3FD: a5 0b    (2) LDA $0B
    #   $B3FF: 29 0f    (2) AND #$0F
    #   $B401: c5 18    (2) CMP $18
    #   $B403: f0 e2    (2) BEQ $B3E7 ($B405 - 30 = $B3E7)
    #   $B405: ea       (1) NOP -> falls into $B406: STA $18!
    picker = bytes.fromhex(
        'bd 12 04 c9 c5 d0 0a '
        'a9 00 e0 0a f0 0c '
        'a9 01 d0 08 '
        'a5 0b 29 0f c5 18 f0 e2 '
        'ea'
    )
    assert len(picker) == 26
    patch(0xB3EC, picker)

    # 3. Title/Menu board puzzle ($85BC-$85FB, 64 bytes: 4 x 16)
    title_board = (
        b'    WHEEL       '
        b'      OF        '
        b'     BARBA      '
        b'    EDITION     '
    )
    assert len(title_board) == 64
    patch(0x85BC, title_board, b'   WHEEL            OF            FORTUNE         FAMILY        ')

    # 4. Title marquee ($8335-$8400) & splash credits ($8C81-$8D41):
    #    Replace "FAMILY EDITION" and TV/Merv Griffin credits with Zelda II & Barba flavor.
    patch(0x8335, b'BARBA,EDITION,', b'FAMILY,EDITION')
    patch(0x8375, b'HYRULE,PALACE,STUDIOS,,,', b'MERV,GRIFFIN,ENTERPRISES')
    patch(0x8399, b'PALACE,VI,DRAGON,', b'COLUMBIA,PICTURES')
    patch(0x83AB, b'BARBA,EDITION,,,,,', b'ENTERTAINMENT;,INC')
    patch(0x83CB, b'ZELDA,II,,', b'I:J:E:,INC')
    patch(0x83E1, b'BARBA,VS,DARK,LINK,,,,,', b'CALIFON,PRODUCTIONS,INC')

    patch(0x8C81, b',' * 13 + b'\xac', b'FAMILY,EDITIO\xce')
    patch(0x8CBF, b',HYRULE,PALACE,STUDIOS,,\xac', b'MERV,GRIFFIN,ENTERPRISES\xbb')
    patch(0x8CE4, b'PALACE,VI,DRAGO\xce', b'COLUMBIA,PICTURE\xd3')
    patch(0x8CF7, b',,BARBA,EDITION,,,\xac', b'ENTERTAINMENT;,INC\xba')
    patch(0x8D15, b',ZELDA,II,\xac', b'I:J:E:,INC\xba')
    patch(0x8D29, b'BARBA,VS,DARK,LINK,,,,,\xac', b'CALIFON,PRODUCTIONS,INC\xba')

    # 5. "GET READY TO PLAY / WHEEL OF FORTUNE" ($BEBC-$BEDF) -> "... /  WHEEL OF BARBA "
    patch(0xBED0, _encode_msg_tile(' WHEEL OF BARBA ', space=0xD4), _encode_msg_tile('WHEEL OF FORTUNE', space=0xD4))

    # 6. Bonus Win text: "3 FABULOUS PRIZE 3" ($CA6F-$CA86) -> "3 BARBA TREASURE 3"
    patch(0xCA71, _encode_msg_tile('BARBA TREASURE', space=0x00), _encode_msg_tile('FABULOUS PRIZE', space=0x00))

    # 6b. Bonus Prize names ($C641-$C6AC, 6 x 18 bytes)
    prize_names = [
        ' PALACE 6 CRYSTAL ',
        'EAST HYRULE CRUISE',
        ' HYRULE ITEM HOARD',
        '  APRIL IN RAURU  ',
        'THIS COOL BOULDER ',
        'PIECE OF PALACE 4 ',
    ]
    orig_prizes = (
        ' EMERALD NECKLACE '
        ' CARIBBEAN CRUISE '
        '   BEACH  HOUSE   '
        '  APRIL IN PARIS  '
        'CONCORDE TO LONDON'
        '      BENTLEY     '
    )
    new_prize_blob = b''.join(_encode_msg_tile(n, space=0x00, digit_base=0xDB) for n in prize_names)
    assert len(new_prize_blob) == 108
    patch(0xC641, new_prize_blob, _encode_msg_tile(orig_prizes, space=0x00))

    # 7. Title marquee ("WHEEL" at $8EC4 and $8F70): replace "FORTUNE" ($8F75) -> " BARBA "
    #    Wait: $8F6A..$8F7E had: <F4><F7><ED><F4><F2><ED><B6><FA><F3><FB><E9><F0><B6><F7><F3><F0><FA><E9>
    #    Let's replace only exact matches in marquee safely:
    #    Look at $8F70..$8F7E: ... $F7 $F4 $ED $F2 $B6 $FA $F3 $FB $E9 $F0 $B6 $F7 $F3 $F0 $FA $E9
    #    That's "SPIN VOWEL SOLVE" ($F7$F4$ED$F2 "SPIN", $FA$F3$FB$E9$F0 "VOWEL", $F7$F3$F0$FA$E9 "SOLVE")!
    #    And $8EC4 is $EC $FB $E9 $E9 $F0 ("WHEEL") -> $8ECC..$8ED4 is "PRESENTS", $8EDD..$8EE2 is "TO" ($F8$F3), $8F45..$8F4A is "RARE"
    #    Leave SPIN VOWEL SOLVE intact; check $8EB8 marquee only if needed!

    # 8. Fix "<NAME>'S TURN" possessive placement ($984A-$9866) when a name contains a space
    #    (e.g. "DARK LINK "): copy all 10 chars (LDA #$0A) and track the last non-space char
    #    in $19 (then INC $19) instead of stopping at the first space.
    patch(0x984A, bytes.fromhex('a9 0a'), bytes.fromhex('a9 09'))
    patch(
        0x984E,
        bytes.fromhex(
            'bd 12 04 '     # LDA $0412,X
            'c9 c5 '        # CMP #$C5 (space in name buffer)
            'd0 04 '        # BNE not_space
            'a9 d4 '        # LDA #$D4 (display space)
            'd0 02 '        # BNE store (always taken)
            '84 19 '        # STY $19 (last non-space index)
            '99 07 05 '     # STA $0507,Y
            'e8 '           # INX
            'c8 '           # INY
            'c6 18 '        # DEC $18
            'd0 ea '        # BNE loop ($984E)
            'e6 19 '        # INC $19 (one past last non-space)
            '60'            # RTS
        ),
        bytes.fromhex('bd 12 04 c9 c5 d0 08 a5 19 d0 02 84 19 a9 d4 99 07 05 e8 c8 c6 18 d0 e8 60'),
    )


def apply_puzzle_patches_bank2(b2: bytearray) -> None:
    """Replace Bank 2 puzzle pool and selector limit with the 64 Zelda II & Barba puzzles."""
    def patch(addr: int, new: bytes, expected: bytes | None = None) -> None:
        off = addr - 0x8000
        if expected is not None:
            assert bytes(b2[off : off + len(expected)]) == expected, (
                f'Unexpected Bank 2 bytes at ${addr:04X}: {bytes(b2[off : off + len(expected)]).hex(" ")}'
            )
        b2[off : off + len(new)] = new

    # 1. Encode all puzzles at $8FDF.. and fill ALL 1090 pointer slots at $875A..$8FDE
    #    so no original Wheel of Fortune puzzle can ever be referenced.
    pool = bytearray()
    ptrs = bytearray()
    for cat_id, lines in WHEEL_BARBA_PUZZLES:
        off = len(pool)
        ptrs.append((off >> 8) & 0xFF)   # big-endian offset relative to $8FDF (see $80F5..$8101)
        ptrs.append(off & 0xFF)
        pool.extend(_encode_puzzle(cat_id, lines))

    # Original table spans $875A..$8FDF (2181 bytes), original pool spans $8FDF..$DAE0
    assert len(ptrs) == 2 * len(WHEEL_BARBA_PUZZLES)
    assert len(pool) <= 0x4B00, f'Puzzle pool too large: {len(pool)}'
    tiled_ptrs = (bytes(ptrs) * ((0x8FDF - 0x875A) // len(ptrs) + 1))[: 0x8FDF - 0x875A]
    patch(0x875A, tiled_ptrs)
    padded_pool = bytes(pool) + b'\x00' * (0xDAE0 - 0x8FDF - len(pool))
    patch(0x8FDF, padded_pool)

    # 2. Patch Bank 2 puzzle selector ($8018-$80BF) to cover 128 tiled slots (16 bytes $0770-$077F)
    #    spanning all 97 unique puzzles.
    # Original $8018-$802A (19 bytes):
    #   a5 0b e5 0c 29 7f 85 18 a5 0b 29 80 4a 4a 4a 4a 65 18 aa
    # New (19 bytes): pick X uniformly in 0..15 -> 128 tiled puzzle slots.
    fast_pick = bytes.fromhex(
        'a5 0b e5 0c 29 0f '                    # LDA $0B; SBC $0C; AND #$0F
        'ea ea ea ea ea ea ea ea ea ea ea ea '  # NOP x12
        'aa'                                    # TAX
    )
    assert len(fast_pick) == 19
    patch(
        0x8018,
        fast_pick,
        bytes.fromhex('a50be50c297f8518a50b29804a4a4a4a6518aa'),
    )
    # Original $8061-$807D (29 bytes):
    #   ad f8 07 c9 c0 d0 16  a2 88 bd 6f 07 c9 ff d0 0d  ca d0 f6 a9 00 9d 70 07 e8 e0 89 d0 f8
    # New (29 bytes): check $0770..$077F == $FF; if all $FF, clear $0770..$077F = $00.
    sel_check = bytes.fromhex(
        'a2 0f '        # $8061: LDX #$0F
        'bd 70 07 '     # $8063: LDA $0770,X
        'c9 ff '        # $8066: CMP #$FF
        'd0 14 '        # $8068: BNE $807E
        'ca '           # $806A: DEX
        '10 f6 '        # $806B: BPL $8063
        'a2 0f '        # $806D: LDX #$0F
        'a9 00 '        # $806F: LDA #$00
        '9d 70 07 '     # $8071: STA $0770,X
        'ca '           # $8074: DEX
        '10 fa '        # $8075: BPL $8071
        'ea ea ea ea ea ea ea'  # $8077-$807D: NOP padding to $807E
    )
    assert len(sel_check) == 29
    patch(
        0x8061,
        sel_check,
        bytes.fromhex('adf807c9c0d016a288bd6f07c9ffd00dcad0f6a9009d7007e8e089d0f8'),
    )

    # Original $8098-$80BF (40 bytes):
    #   a5 0b 29 7f 85 18 a5 0c 29 09 18 65 18 aa   (14B: random X 0..136)
    #   bd 70 07 c9 ff d0 09 e8 e0 89 d0 f4 a2 00 f0 f0 (16B: scan X 0..136)
    #   85 14 e0 88 d0 04 c9 c0 d0 ed              (10B: $07F8 == $C0 special case)
    sel_pick = bytes.fromhex(
        'a5 0b 29 0f aa '           # $8098: LDA $0B; AND #$0F; TAX (random byte 0..15)
        'ea ea ea ea ea ea ea ea ea '  # $809D-$80A5: NOP x9
        'bd 70 07 '                 # $80A6: LDA $0770,X
        'c9 ff '                    # $80A9: CMP #$FF
        'd0 09 '                    # $80AB: BNE $80B6
        'e8 '                       # $80AD: INX
        'e0 10 '                    # $80AE: CPX #$10
        'd0 f4 '                    # $80B0: BNE $80A6
        'a2 00 '                    # $80B2: LDX #$00
        'f0 f0 '                    # $80B4: BEQ $80A6
        '85 14 '                    # $80B6: STA $14
        'ea ea ea ea ea ea ea ea'   # $80B8-$80BF: NOP out $88/$C0 check -> falls into $80C0
    )
    assert len(sel_pick) == 40
    patch(
        0x8098,
        sel_pick,
        bytes.fromhex(
            'a50b297f8518a50c2909186518aa'
            'bd7007c9ffd009e8e089d0f4a200f0f0'
            '8514e088d004c9c0d0ed'
        ),
    )
