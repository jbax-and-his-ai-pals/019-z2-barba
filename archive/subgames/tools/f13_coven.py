"""Forest Coven & King's Quest-style endings (Debbie cliff & Laura noodles) for Friday the 13th."""
from __future__ import annotations

from boss_art import make_frames
from nes import encode_tile
from pack_f13 import Asm6502, F13_WIN_HOOK

F13_CHR_BASE = 0x7BFE
F13_PRG_BASE = 0x7BFF

# WRAM allocations for the cutscene (free region $7C60-$7DFF)
COVEN_ENDING_FLAG = 0x7C60  # 0=none, 1=Debbie cliff, 2=Laura noodles (RA-friendly)
CUT_TMP0          = 0x7C61
CUT_TMP1          = 0x7C62
CUT_TMP2          = 0x7C63
CUT_TMP3          = 0x7C64
CUT_PAD_CUR       = 0x7C65
CUT_PAD_PREV      = 0x7C66
CUT_PAD_NEW       = 0x7C67
CUT_FRAME         = 0x7C68
CUT_SHAKE         = 0x7C69
CUT_MOUTH_STATE   = 0x7C6A
CUT_MOUTH_MASK    = 0x7C6B  # bitmask of speaking Barbas: bit0..3
CUT_SPEAKER       = 0x7C6C
CUT_TXT_ROW       = 0x7C6D
CUT_TXT_COL       = 0x7C6E
CUT_TXT_IDX       = 0x7C6F
CUT_SCRIPT_IDX    = 0x7C70
CUT_PX            = 0x7C71
CUT_PY            = 0x7C72
CUT_PVY           = 0x7C73
CUT_TIMER         = 0x7C74
CUT_OAM_COUNT     = 0x7CFF
CUT_OAM_SNAP      = 0x7D00  # up to 16 sprites * 4B = 64B ($7D00-$7D3F)

# Tile IDs in Cutscene BG CHR bank (4KB at $1000-$1FFF, copied from F13 CHR1 + free slots $30..$9B)
T_DIGITS   = 0x30  # 0..9 ($30..$39)
T_ALPHA    = 0x3A  # A..Z ($3A..$53)
T_BANG     = 0x54  # !
T_APOS     = 0x55  # '
T_DOT      = 0x56  # .
T_COMMA    = 0x57  # ,
T_DASH     = 0x58  # -
T_COLON    = 0x59  # :
T_QUEST    = 0x5A  # ?
T_SPACE    = 0x5B  # ' '
T_ARROW    = 0x5C  # blink prompt

T_BOX_TL   = 0x60
T_BOX_T    = 0x61
T_BOX_TR   = 0x62
T_BOX_L    = 0x63
T_BOX_R    = 0x64
T_BOX_BL   = 0x65
T_BOX_B    = 0x66
T_BOX_BR   = 0x67

T_CLIFF_TOP  = 0x68
T_CLIFF_WALL = 0x69
T_PIT_BLACK  = 0x6A
T_NOODLE_0   = 0x70
T_NOODLE_1   = 0x71

# Barba BG tiles: 20 tiles each (6 head closed + 6 head open + 8 body)
T_BARBA_L_HC = 0x74  # $74..$79
T_BARBA_L_HO = 0x7A  # $7A..$7F
T_BARBA_L_BD = 0x80  # $80..$87
T_BARBA_R_HC = 0x88  # $88..$8D
T_BARBA_R_HO = 0x8E  # $8E..$93
T_BARBA_R_BD = 0x94  # $94..$9B
T_TRUNK      = 0x9C  # forest tree trunk bark

# Sprite tiles in Cutscene Sprite 2KB bank 24 ($0000-$07FF, copied from 2KB bank 0 + $72..$77)
T_SPARKLE_0  = 0x72
T_SPARKLE_1  = 0x73
T_TENDRIL_0  = 0x74
T_TENDRIL_1  = 0x75
T_TENDRIL_2  = 0x76
T_TENDRIL_3  = 0x77

# Speaker IDs
SPK_BARBA  = 0
SPK_BERBA  = 1
SPK_BORBA  = 2
SPK_BURBA  = 3
SPK_ALL    = 4
SPK_DEBBIE = 5
SPK_LAURA  = 6


def _flip_h(rows: list[str]) -> list[str]:
    return [r[::-1] for r in rows]


def _split_grid(rows: list[str], cols: int, tile_rows: int) -> list[list[str]]:
    tiles = []
    for ty in range(tile_rows):
        for tx in range(cols):
            tiles.append([rows[ty * 8 + y][tx * 8 : (tx + 1) * 8] for y in range(8)])
    return tiles


def encode_text(s: str) -> list[int]:
    """Encode uppercase ASCII string into Cutscene BG tile IDs."""
    out = []
    for ch in s:
        if "0" <= ch <= "9":
            out.append(T_DIGITS + ord(ch) - ord("0"))
        elif "A" <= ch <= "Z":
            out.append(T_ALPHA + ord(ch) - ord("A"))
        elif ch == "!":
            out.append(T_BANG)
        elif ch == "'":
            out.append(T_APOS)
        elif ch == ".":
            out.append(T_DOT)
        elif ch == ",":
            out.append(T_COMMA)
        elif ch == "-":
            out.append(T_DASH)
        elif ch == ":":
            out.append(T_COLON)
        elif ch == "?":
            out.append(T_QUEST)
        elif ch == " ":
            out.append(T_SPACE)
        else:
            raise ValueError(f"Unsupported char in coven text: {ch!r}")
    return out


def build_coven_chr(chr64_buf: bytearray, f13_chr: bytes, z2_raw: bytes) -> None:
    """Populate 2KB CHR indices 22, 23 (BG) and 24 (Sprites) in chr64_buf."""
    # 1. Cutscene BG (4KB at 2KB indices 22..23 = offset 44KB..48KB)
    bg_off = 22 * 2048
    chr64_buf[bg_off : bg_off + 4096] = f13_chr[1 * 4096 : 2 * 4096]

    def put_bg(tid: int, raw16: bytes) -> None:
        chr64_buf[bg_off + tid * 16 : bg_off + (tid + 1) * 16] = raw16

    def put_bg_rows(tid: int, rows: list[str]) -> None:
        put_bg(tid, encode_tile(rows))

    # Copy font from F13 CHR bank 7
    chr7 = f13_chr[7 * 4096 : 8 * 4096]
    for i in range(10):
        put_bg(T_DIGITS + i, chr7[i * 16 : (i + 1) * 16])
    for i in range(26):
        put_bg(T_ALPHA + i, chr7[(0x0A + i) * 16 : (0x0B + i) * 16])
    put_bg(T_BANG, chr7[0x25 * 16 : 0x26 * 16])
    put_bg(T_APOS, chr7[0x26 * 16 : 0x27 * 16])
    put_bg(T_DOT, chr7[0x27 * 16 : 0x28 * 16])
    put_bg(T_COMMA, chr7[0x29 * 16 : 0x2A * 16])

    # Custom punctuation & space & arrow (color 3 = white)
    put_bg_rows(T_DASH, [
        "00000000", "00000000", "00000000", "03333330",
        "03333330", "00000000", "00000000", "00000000",
    ])
    put_bg_rows(T_COLON, [
        "00000000", "00033000", "00033000", "00000000",
        "00033000", "00033000", "00000000", "00000000",
    ])
    put_bg_rows(T_QUEST, [
        "00333300", "03300330", "00000330", "00033300",
        "00033000", "00000000", "00033000", "00000000",
    ])
    put_bg_rows(T_SPACE, ["00000000"] * 8)
    put_bg_rows(T_ARROW, [
        "00000000", "02222220", "00222200", "00022000",
        "00000000", "00000000", "00000000", "00000000",
    ])

    # Box border tiles (color 2 = gold, color 1 = red)
    put_bg_rows(T_BOX_TL, [
        "00000000", "02222222", "02111111", "02100000",
        "02100000", "02100000", "02100000", "02100000",
    ])
    put_bg_rows(T_BOX_T, [
        "00000000", "22222222", "11111111", "00000000",
        "00000000", "00000000", "00000000", "00000000",
    ])
    put_bg_rows(T_BOX_TR, [
        "00000000", "22222220", "11111120", "00000120",
        "00000120", "00000120", "00000120", "00000120",
    ])
    put_bg_rows(T_BOX_L, [
        "02100000", "02100000", "02100000", "02100000",
        "02100000", "02100000", "02100000", "02100000",
    ])
    put_bg_rows(T_BOX_R, [
        "00000120", "00000120", "00000120", "00000120",
        "00000120", "00000120", "00000120", "00000120",
    ])
    put_bg_rows(T_BOX_BL, [
        "02100000", "02100000", "02100000", "02100000",
        "02100000", "02111111", "02222222", "00000000",
    ])
    put_bg_rows(T_BOX_B, [
        "00000000", "00000000", "00000000", "00000000",
        "00000000", "11111111", "22222222", "00000000",
    ])
    put_bg_rows(T_BOX_BR, [
        "00000120", "00000120", "00000120", "00000120",
        "00000120", "11111120", "22222220", "00000000",
    ])

    # Cliff & Pit tiles (for Debbie's ending)
    put_bg_rows(T_CLIFF_TOP, [
        "22222100", "33221100", "33321000", "23311000",
        "22110000", "12110000", "11100000", "11100000",
    ])
    put_bg_rows(T_CLIFF_WALL, [
        "12100000", "11100000", "21100000", "11000000",
        "12100000", "11000000", "21100000", "11000000",
    ])
    put_bg_rows(T_PIT_BLACK, ["00000000"] * 8)

    # Noodle puddle BG tiles (for Laura's ending)
    put_bg_rows(T_NOODLE_0, [
        "00000000", "00000000", "00223200", "02322320",
        "23223322", "32232233", "23322322", "32233232",
    ])
    put_bg_rows(T_NOODLE_1, [
        "00000000", "02232200", "23223220", "32232322",
        "23322232", "32233223", "22322332", "33233223",
    ])
    put_bg_rows(T_TRUNK, [
        "03313310", "03133330", "03331330", "01333310",
        "03331330", "03133330", "03333130", "03313330",
    ])

    # 24x48 Barba BG tiles (left-facing & right-facing)
    frames = make_frames(z2_raw, 24)
    hc_l = _split_grid(frames["idle"][0:16], 3, 2)
    ho_l = _split_grid(frames["attack"][0:16], 3, 2)
    bd_l = _split_grid([r[8:24] for r in frames["walk0"][16:48]], 2, 4)

    hc_r = _split_grid(_flip_h(frames["idle"][0:16]), 3, 2)
    ho_r = _split_grid(_flip_h(frames["attack"][0:16]), 3, 2)
    bd_r = _split_grid(_flip_h([r[8:24] for r in frames["walk0"][16:48]]), 2, 4)

    for i, t in enumerate(hc_l):
        put_bg_rows(T_BARBA_L_HC + i, t)
    for i, t in enumerate(ho_l):
        put_bg_rows(T_BARBA_L_HO + i, t)
    for i, t in enumerate(bd_l):
        put_bg_rows(T_BARBA_L_BD + i, t)
    for i, t in enumerate(hc_r):
        put_bg_rows(T_BARBA_R_HC + i, t)
    for i, t in enumerate(ho_r):
        put_bg_rows(T_BARBA_R_HO + i, t)
    for i, t in enumerate(bd_r):
        put_bg_rows(T_BARBA_R_BD + i, t)

    # 2. Cutscene Sprite 2KB bank 24 (offset 48KB..50KB)
    spr_off = 24 * 2048
    chr64_buf[spr_off : spr_off + 2048] = chr64_buf[0:2048]

    def put_spr(tid: int, rows: list[str]) -> None:
        chr64_buf[spr_off + tid * 16 : spr_off + (tid + 1) * 16] = encode_tile(rows)

    put_spr(T_SPARKLE_0, [
        "00030000", "00030000", "00232000", "33333330",
        "00232000", "00030000", "00030000", "00000000",
    ])
    put_spr(T_SPARKLE_1, [
        "02000200", "00303000", "00030000", "02333200",
        "00030000", "00303000", "02000200", "00000000",
    ])
    put_spr(T_TENDRIL_0, [
        "00023000", "00232000", "00232200", "00023200",
        "00232000", "02322000", "02320000", "00232000",
    ])
    put_spr(T_TENDRIL_1, [
        "00232000", "02320000", "02322000", "00232000",
        "00023200", "00232000", "02320000", "00232000",
    ])
    put_spr(T_TENDRIL_2, [
        "00232000", "00023200", "00232000", "02320000",
        "02322000", "00232000", "00023200", "00232000",
    ])
    put_spr(T_TENDRIL_3, [
        "02332200", "23223200", "23202320", "02322320",
        "00233200", "02322320", "23200232", "02333200",
    ])


# =============================================================================
# Scripts (stored in Bank 3 $A000-$BFFF)
# Format per script: list of (speaker_id, [line1, line2, line3])
# Max 26 chars per line (box interior is cols 3..28 = 26 chars, rows 2..4 = 3 lines;
# speaker header goes on row 2, text lines on rows 3..5? Let's use:
#   Box border: rows 1..6, cols 1..30 (interior rows 2..5, cols 2..29 = 28 chars)
#   Row 2: SPEAKER:
#   Row 3: line 1 (max 26 chars)
#   Row 4: line 2 (max 26 chars)
#   Row 5: line 3 (max 26 chars) + blinking arrow at col 29
# =============================================================================
SPEAKER_LABELS = {
    SPK_BARBA:  "BARBA:",
    SPK_BERBA:  "BERBA:",
    SPK_BORBA:  "BORBA:",
    SPK_BURBA:  "BURBA:",
    SPK_ALL:    "ALL:",
    SPK_DEBBIE: "DEBBIE:",
    SPK_LAURA:  "LAURA:",
}

DEBBIE_SCRIPTS = [
    [
        (SPK_BARBA,  ["WELCOME TO THE CLEARING,", "DEBBIE. WE WERE EXPECTING", "SOMEONE... LESS ROBUST."]),
        (SPK_BERBA,  ["NO FIRE BREATH. NO SCALES.", "JUST A VERY CONFUSED", "CAMP COUNSELOR."]),
        (SPK_DEBBIE, ["UH... HI? ARE YOU GUYS", "WITH CAMP CRYSTAL LAKE", "MAINTENANCE?"]),
        (SPK_BORBA,  ["IN A MANNER OF SPEAKING.", "WE MAINTAIN THE CLIFF.", "MOSTLY BY USING IT."]),
        (SPK_ALL,    ["THE COVEN HAS VOTED.", "GRAVITY TAKES THE", "MINUTES."]),
    ],
    [
        (SPK_BURBA,  ["HOLD IT RIGHT THERE.", "YOU STEPPED ON THE", "SACRED MOSS."]),
        (SPK_DEBBIE, ["I LITERALLY JUST WALKED", "IN HERE FIVE SECONDS", "AGO!"]),
        (SPK_BARBA,  ["IGNORANCE OF THE MOSS", "IS NO EXCUSE FOR", "STANDING ON THE MOSS."]),
        (SPK_BERBA,  ["BESIDES, THAT PIT OVER", "THERE LOOKS TERRIBLY", "LONELY."]),
        (SPK_ALL,    ["UP YOU GO, COUNSELOR.", "MIND THE FIRST STEP."]),
    ],
    [
        (SPK_BORBA,  ["FOUR DRAGONS. ONE", "COUNSELOR. ZERO", "ESCAPE ROUTES."]),
        (SPK_DEBBIE, ["WAIT, WHY DO ALL FOUR", "OF YOU LOOK LIKE THE", "EXACT SAME GUY?"]),
        (SPK_BURBA,  ["WE ARE DISTINCT", "INDIVIDUALS WITH RICH", "INNER LIVES."]),
        (SPK_BARBA,  ["AND WE ALL AGREE ON", "ONE THING: CLIFF TIME."]),
        (SPK_ALL,    ["FLY, LITTLE HUMAN.", "WELL, FALL MOSTLY."]),
    ],
    [
        (SPK_BERBA,  ["THE MOON IS HIGH. THE", "WOODS ARE DARK. THE", "SCRIPT IS QUESTIONABLE."]),
        (SPK_BARBA,  ["IS THIS A SEANCE OR", "A PERFORMANCE REVIEW?"]),
        (SPK_BORBA,  ["BOTH. DEBBIE, YOUR", "SURVIVAL RATING JUST", "DROPPED."]),
        (SPK_DEBBIE, ["IS THERE AN HR", "DEPARTMENT AT THIS", "CAMP?!"]),
        (SPK_ALL,    ["YES. IT IS AT THE", "BOTTOM OF THIS PIT."]),
    ],
]

LAURA_SCRIPTS = [
    [
        (SPK_BARBA,  ["AH, LAURA. YOU WALKED", "INTO THE DEEP WOODS", "WITHOUT A SNACK."]),
        (SPK_BERBA,  ["FORTUNATELY, THE FOREST", "PROVIDES. SPECIFICALLY,", "CARBOHYDRATES."]),
        (SPK_LAURA,  ["WHY IS THE DIRT", "SMELLING LIKE GARLIC", "AND BUTTER?"]),
        (SPK_BORBA,  ["DO NOT QUESTION THE", "PASTA CIRCLE, LAURA."]),
        (SPK_ALL,    ["ARISE, NOODLES!", "CLAIM YOUR COUNSELOR!"]),
    ],
    [
        (SPK_BURBA,  ["WE TRIED FIRE. WE TRIED", "CLIFFS. TONIGHT WE TRY", "CULINARY SORCERY."]),
        (SPK_LAURA,  ["ARE THOSE... SPAGHETTI", "TENDRILS UNDER MY", "BOOTS?!"]),
        (SPK_BARBA,  ["AL DENTE. HAND-PULLED", "BY ANCIENT DRAGON", "TRADITION."]),
        (SPK_BERBA,  ["OR LEFTOVER FROM", "TUESDAY. EITHER WAY,", "HOLD STILL."]),
        (SPK_ALL,    ["SLURP HER INTO THE", "ABYSS!"]),
    ],
    [
        (SPK_BORBA,  ["LAURA! YOU HAVE", "DISTURBED THE COVEN'S", "DINNER RESERVATION."]),
        (SPK_LAURA,  ["I JUST WANTED TO FIND", "A CABIN AND NOT DIE!"]),
        (SPK_BURBA,  ["GOOD NEWS: THIS IS", "TECHNICALY NOT JASON."]),
        (SPK_BARBA,  ["BAD NEWS: YOU ARE", "THE MAIN COURSE."]),
        (SPK_ALL,    ["NOODLES, ASSEMBLE!", "BON APPETIT!"]),
    ],
    [
        (SPK_BERBA,  ["WAIT. WHO SUMMONED", "THE NOODLES THIS TIME?"]),
        (SPK_BORBA,  ["I THOUGHT BARBA DID.", "I BROUGHT THE PARMESAN."]),
        (SPK_LAURA,  ["COULD WE MAYBE TALK", "THIS OVER BEFORE I GET", "DRAGGED UNDER?!"]),
        (SPK_BARBA,  ["SORRY. ONCE THE WATER", "BOILS, IT'S OUT OF", "OUR HANDS."]),
        (SPK_ALL,    ["DOWN INTO THE", "PASTA DIMENSION!"]),
    ],
]


def build_coven_banks() -> tuple[bytes, bytes]:
    """Assemble Bank 2 (8KB, $8000-$9FFF) and Bank 3 (8KB, $A000-$BFFF)."""
    # First build Bank 3 data ($A000-$BFFF): script tables & encoded strings
    b3 = Asm6502(0xA000)

    # Pointer tables at $A000 and $A008 (4 scripts each, 2B pointers)
    for i in range(4):
        b3.abs_ref(0x00, f"deb_script_{i}")  # placeholder 2B? Asm6502 abs_ref emits 1 opcode + 2B!
    # Clean 2-byte word helper instead:
    b3 = Asm6502(0xA000)

    def emit_word(lbl: str) -> None:
        b3.emit(0x00, 0x00)
        b3.fixups.append(("abs", len(b3.buf) - 2, lbl))

    for i in range(4):
        emit_word(f"deb_script_{i}")
    for i in range(4):
        emit_word(f"lau_script_{i}")

    for spk_id in range(7):
        b3.label(f"spk_lbl_{spk_id}")
        enc = encode_text(SPEAKER_LABELS[spk_id])
        b3.emit(*enc, 0xFF)

    def emit_scripts(prefix: str, scripts: list[list[tuple[int, list[str]]]]) -> None:
        for s_idx, boxes in enumerate(scripts):
            b3.label(f"{prefix}_script_{s_idx}")
            for b_idx, (spk, lines) in enumerate(boxes):
                b3.emit(spk, len(lines))
                for l_idx in range(len(lines)):
                    emit_word(f"{prefix}_{s_idx}_{b_idx}_{l_idx}")
            b3.emit(0xFF)
        for s_idx, boxes in enumerate(scripts):
            for b_idx, (_, lines) in enumerate(boxes):
                for l_idx, line in enumerate(lines):
                    b3.label(f"{prefix}_{s_idx}_{b_idx}_{l_idx}")
                    b3.emit(*encode_text(line), 0xFF)

    emit_scripts("deb", DEBBIE_SCRIPTS)
    emit_scripts("lau", LAURA_SCRIPTS)

    bank3_raw = b3.finish()
    assert len(bank3_raw) <= 8192, f"Bank 3 overflow: {len(bank3_raw)}"
    bank3 = bytearray(b"\xFF" * 8192)
    bank3[0 : len(bank3_raw)] = bank3_raw

    # Now build Bank 2 ($8000-$9FFF): Cutscene Engine
    a = Asm6502(0x8000)
    a.abs_ref(0x4C, "CovenMain")

    # Helper: WaitVBlank (polls $2002 bit 7)
    a.label("WaitVBlank")
    a.emit(0x2C, 0x02, 0x20)
    a.label("wv_loop")
    a.emit(0x2C, 0x02, 0x20)
    a.branch(0x10, "wv_loop")
    a.emit(0x60)

    # Helper: WaitFrames (X = frame count; updates OAM DMA, scroll+shake, pad, frame counter)
    a.label("WaitFrames")
    a.emit(0x8A, 0x48)  # TXA; PHA
    a.label("wf_loop")
    a.abs_ref(0x20, "PresentFrame")
    a.emit(0x68, 0xAA, 0xCA, 0xF0, 0x06)  # PLA; TAX; DEX; BEQ done
    a.emit(0x8A, 0x48)
    a.abs_ref(0x4C, "wf_loop")
    a.emit(0x60)

    # Helper: PresentFrame (wait vblank, OAM DMA, scroll with shake, read pad, inc frame)
    a.label("PresentFrame")
    a.abs_ref(0x20, "WaitVBlank")
    a.emit(0xA9, 0x00, 0x8D, 0x03, 0x20)
    a.emit(0xA9, 0x02, 0x8D, 0x14, 0x40)  # OAM DMA $0200
    a.emit(0xA9, 0x00, 0x8D, 0x06, 0x20, 0x8D, 0x06, 0x20)
    a.emit(0xAD, CUT_SHAKE & 0xFF, CUT_SHAKE >> 8)
    a.branch(0xF0, "pf_noshake")
    a.emit(0xCE, CUT_SHAKE & 0xFF, CUT_SHAKE >> 8)
    a.emit(0x29, 0x01)
    a.branch(0xF0, "pf_sh_pos")
    a.emit(0xA9, 0x00, 0xF0, 0x02)
    a.label("pf_sh_pos")
    a.emit(0xA9, 0x03)
    a.emit(0x8D, 0x05, 0x20)  # X scroll = +-3
    a.emit(0x8D, 0x05, 0x20)  # Y scroll = +-3
    a.abs_ref(0x4C, "pf_sc_done")
    a.label("pf_noshake")
    a.emit(0xA9, 0x00, 0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)
    a.label("pf_sc_done")
    a.emit(0xEE, CUT_FRAME & 0xFF, CUT_FRAME >> 8)
    a.abs_ref(0x20, "ReadPad")
    a.emit(0x60)

    # Helper: ReadPad -> CUT_PAD_CUR, CUT_PAD_NEW (standard NES bit order: A=80, B=40, Sel=20, Start=10)
    a.label("ReadPad")
    a.emit(0xAD, CUT_PAD_CUR & 0xFF, CUT_PAD_CUR >> 8)
    a.emit(0x8D, CUT_PAD_PREV & 0xFF, CUT_PAD_PREV >> 8)
    a.emit(0xA9, 0x01, 0x8D, 0x16, 0x40)
    a.emit(0xA9, 0x00, 0x8D, 0x16, 0x40)
    a.emit(0xA2, 0x08)
    a.label("rp_loop")
    a.emit(0xAD, 0x16, 0x40, 0x4A, 0x26, 0x00)
    a.emit(0xCA)
    a.branch(0xD0, "rp_loop")
    a.emit(0xA5, 0x00, 0x8D, CUT_PAD_CUR & 0xFF, CUT_PAD_CUR >> 8)
    a.emit(0x4D, CUT_PAD_PREV & 0xFF, CUT_PAD_PREV >> 8)
    a.emit(0x2D, CUT_PAD_CUR & 0xFF, CUT_PAD_CUR >> 8)
    a.emit(0x8D, CUT_PAD_NEW & 0xFF, CUT_PAD_NEW >> 8)
    a.emit(0x60)

    # Helper: SetChrBank (Y = MMC3 reg 0..5, A = bank)
    a.label("SetChrBank")
    a.emit(0x18, 0x6D, F13_CHR_BASE & 0xFF, F13_CHR_BASE >> 8)
    a.emit(0x8C, 0x00, 0x80, 0x8D, 0x01, 0x80, 0x60)

    # Helper: ClearOam ($0200-$02FF = $FE)
    a.label("ClearOam")
    a.emit(0xA9, 0xFE, 0xA2, 0x00)
    a.label("co_lp")
    a.emit(0x9D, 0x00, 0x02, 0xE8)
    a.branch(0xD0, "co_lp")
    a.emit(0x60)

    # Helper: DrawPlayerOam (draws snapped sprites at CUT_PX, CUT_PY into $0200..)
    a.label("DrawPlayerOam")
    a.emit(0xAD, CUT_OAM_COUNT & 0xFF, CUT_OAM_COUNT >> 8)
    a.branch(0xF0, "dpo_done")
    a.emit(0x8D, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.emit(0xA2, 0x00)
    a.label("dpo_lp")
    a.emit(0xBD, CUT_OAM_SNAP & 0xFF, CUT_OAM_SNAP >> 8)
    a.emit(0x18, 0x6D, CUT_PY & 0xFF, CUT_PY >> 8)
    a.branch(0xB0, "dpo_hide")  # carry set = wrapped past 255 -> hide!
    a.emit(0xC9, 0xEF)
    a.branch(0x90, "dpo_y_ok")
    a.label("dpo_hide")
    a.emit(0xA9, 0xFE)
    a.label("dpo_y_ok")
    a.emit(0x9D, 0x00, 0x02)
    a.emit(0xBD, (CUT_OAM_SNAP + 1) & 0xFF, (CUT_OAM_SNAP + 1) >> 8, 0x9D, 0x01, 0x02)
    a.emit(0xBD, (CUT_OAM_SNAP + 2) & 0xFF, (CUT_OAM_SNAP + 2) >> 8, 0x9D, 0x02, 0x02)
    a.emit(0xBD, (CUT_OAM_SNAP + 3) & 0xFF, (CUT_OAM_SNAP + 3) >> 8)
    a.emit(0x18, 0x6D, CUT_PX & 0xFF, CUT_PX >> 8)
    a.emit(0x9D, 0x03, 0x02)
    a.emit(0xE8, 0xE8, 0xE8, 0xE8)
    a.emit(0xEC, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.branch(0x90, "dpo_lp")
    a.label("dpo_done")
    a.emit(0x60)

    # Helper: PlayBlip (A = timer_lo, X = volume/duty)
    a.label("PlayBlip")
    a.emit(0x8E, 0x00, 0x4000 >> 8)  # $4000
    a.emit(0x8D, 0x02, 0x40)         # $4002
    a.emit(0xA9, 0x18, 0x8D, 0x03, 0x40)
    a.emit(0x60)

    # Helper: PpuAddrFromRowCol (A = row 0..29, X = col 0..31) -> sets $2006
    a.label("SetNtAddr")
    a.emit(0x2C, 0x02, 0x20)  # reset PPU latch
    a.emit(0x85, 0x00, 0xA9, 0x00, 0x85, 0x01)
    a.emit(0x06, 0x00, 0x26, 0x01)  # *2
    a.emit(0x06, 0x00, 0x26, 0x01)  # *4
    a.emit(0x06, 0x00, 0x26, 0x01)  # *8
    a.emit(0x06, 0x00, 0x26, 0x01)  # *16
    a.emit(0x06, 0x00, 0x26, 0x01)  # *32
    a.emit(0x8A, 0x05, 0x00, 0x85, 0x00)
    a.emit(0xA5, 0x01, 0x09, 0x20, 0x8D, 0x06, 0x20)
    a.emit(0xA5, 0x00, 0x8D, 0x06, 0x20, 0x60)

    # Helper: StampBarba (CUT_TMP0=col, CUT_TMP1=row, CUT_TMP2=dir(0=R,1=L), CUT_TMP3=pal(0/1), A=open(0/1))
    # Draws 3x6 Barba into NT0 during VBlank (or while blanked)
    a.label("StampBarba")
    a.emit(0x48)  # save open flag
    # Compute head base tile -> $04
    a.emit(0xAD, CUT_TMP2 & 0xFF, CUT_TMP2 >> 8)
    a.branch(0xD0, "sb_left")
    a.emit(0x68, 0xD0, 0x04)  # right-facing
    a.emit(0xA9, T_BARBA_R_HC, 0xD0, 0x02)
    a.emit(0xA9, T_BARBA_R_HO)
    a.emit(0x85, 0x04, 0xA9, T_BARBA_R_BD, 0x85, 0x05)
    a.abs_ref(0x4C, "sb_draw")
    a.label("sb_left")
    a.emit(0x68, 0xD0, 0x04)
    a.emit(0xA9, T_BARBA_L_HC, 0xD0, 0x02)
    a.emit(0xA9, T_BARBA_L_HO)
    a.emit(0x85, 0x04, 0xA9, T_BARBA_L_BD, 0x85, 0x05)

    a.label("sb_draw")
    # 2 head rows (3 cols each)
    a.emit(0xA0, 0x00, 0x84, 0x06)  # row_i = 0
    a.label("sb_hrow")
    a.emit(0xAD, CUT_TMP1 & 0xFF, CUT_TMP1 >> 8, 0x18, 0x65, 0x06)
    a.emit(0xAE, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA5, 0x04, 0x8D, 0x07, 0x20, 0xE6, 0x04)
    a.emit(0xA5, 0x04, 0x8D, 0x07, 0x20, 0xE6, 0x04)
    a.emit(0xA5, 0x04, 0x8D, 0x07, 0x20, 0xE6, 0x04)
    a.emit(0xE6, 0x06, 0xA5, 0x06, 0xC9, 0x02)
    a.branch(0x90, "sb_hrow")
    # 4 body rows (2 cols each, centered at col + 0..1 or +1..2 depending on dir)
    a.label("sb_brow")
    a.emit(0xAD, CUT_TMP1 & 0xFF, CUT_TMP1 >> 8, 0x18, 0x65, 0x06)
    a.emit(0x48)  # save row
    a.emit(0xAE, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.emit(0xAD, CUT_TMP2 & 0xFF, CUT_TMP2 >> 8)
    a.branch(0xF0, "sb_bcol_ok")
    a.emit(0xE8)  # left-facing: body at col+1..col+2
    a.label("sb_bcol_ok")
    a.emit(0x68)  # restore row into A
    a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA5, 0x05, 0x8D, 0x07, 0x20, 0xE6, 0x05)
    a.emit(0xA5, 0x05, 0x8D, 0x07, 0x20, 0xE6, 0x05)
    a.emit(0xE6, 0x06, 0xA5, 0x06, 0xC9, 0x06)
    a.branch(0x90, "sb_brow")
    a.emit(0x60)

    # Helper: StampBarbaHeadOnly (updates just the 2x3 head tiles during VBlank for mouth animation!)
    # Input: X = Barba index 0..3, A = open(0/1)
    a.label("StampBarbaHead")
    a.emit(0x48)
    a.abs_ref(0xBD, "BarbaColTbl")
    a.emit(0x8D, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.emit(0xA9, 16, 0x8D, CUT_TMP1 & 0xFF, CUT_TMP1 >> 8)
    a.abs_ref(0xBD, "BarbaDirTbl")
    a.emit(0x8D, CUT_TMP2 & 0xFF, CUT_TMP2 >> 8)
    a.branch(0xD0, "sbh_l")
    a.emit(0x68, 0xD0, 0x04)
    a.emit(0xA9, T_BARBA_R_HC, 0xD0, 0x02)
    a.emit(0xA9, T_BARBA_R_HO)
    a.emit(0x85, 0x04)
    a.abs_ref(0x4C, "sbh_go")
    a.label("sbh_l")
    a.emit(0x68, 0xD0, 0x04)
    a.emit(0xA9, T_BARBA_L_HC, 0xD0, 0x02)
    a.emit(0xA9, T_BARBA_L_HO)
    a.emit(0x85, 0x04)
    a.label("sbh_go")
    a.emit(0xA9, 16, 0xAE, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA5, 0x04, 0x8D, 0x07, 0x20, 0xE6, 0x04)
    a.emit(0xA5, 0x04, 0x8D, 0x07, 0x20, 0xE6, 0x04)
    a.emit(0xA5, 0x04, 0x8D, 0x07, 0x20, 0xE6, 0x04)
    a.emit(0xA9, 17, 0xAE, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA5, 0x04, 0x8D, 0x07, 0x20, 0xE6, 0x04)
    a.emit(0xA5, 0x04, 0x8D, 0x07, 0x20, 0xE6, 0x04)
    a.emit(0xA5, 0x04, 0x8D, 0x07, 0x20, 0xE6, 0x04)
    a.emit(0x60)

    # Helper: ClearBoxInterior (clears rows 2..5, cols 2..29 to T_SPACE while rendering is on!)
    a.label("ClearBoxInterior")
    a.emit(0xA9, 2, 0x8D, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.label("cbi_row")
    a.abs_ref(0x20, "WaitVBlank")
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0xA2, 2)
    a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA9, T_SPACE, 0xA2, 28)
    a.label("cbi_col")
    a.emit(0x8D, 0x07, 0x20, 0xCA)
    a.branch(0xD0, "cbi_col")
    a.emit(0xA9, 0x00, 0x8D, 0x06, 0x20, 0x8D, 0x06, 0x20, 0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)
    a.emit(0xEE, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0xC9, 6)
    a.branch(0x90, "cbi_row")
    a.emit(0x60)

    # =========================================================================
    # CovenMain ($8000 entry)
    # =========================================================================
    a.label("CovenMain")
    a.emit(0x78)  # SEI

    # 1. Snapshot Debbie/Laura OAM sprites (Y in [$98,$DC], X in [$68,$98])
    a.emit(0xA9, 0x00, 0x8D, CUT_OAM_COUNT & 0xFF, CUT_OAM_COUNT >> 8)
    a.emit(0xA2, 0x00, 0xA0, 0x00)  # X=src oam, Y=dst snap
    a.label("snap_lp")
    a.emit(0xBD, 0x00, 0x02)
    a.emit(0xC9, 0x98)
    a.branch(0x90, "snap_next")
    a.emit(0xC9, 0xDC)
    a.branch(0xB0, "snap_next")
    a.emit(0xBD, 0x03, 0x02)
    a.emit(0xC9, 0x68)
    a.branch(0x90, "snap_next")
    a.emit(0xC9, 0x98)
    a.branch(0xB0, "snap_next")
    # Match! Store dy = Y - $A0, tile, attr, dx = X - $78
    a.emit(0xBD, 0x00, 0x02, 0x38, 0xE9, 0xA0, 0x99, CUT_OAM_SNAP & 0xFF, CUT_OAM_SNAP >> 8)
    a.emit(0xBD, 0x01, 0x02, 0x99, (CUT_OAM_SNAP + 1) & 0xFF, (CUT_OAM_SNAP + 1) >> 8)
    a.emit(0xBD, 0x02, 0x02, 0x99, (CUT_OAM_SNAP + 2) & 0xFF, (CUT_OAM_SNAP + 2) >> 8)
    a.emit(0xBD, 0x03, 0x02, 0x38, 0xE9, 0x78, 0x99, (CUT_OAM_SNAP + 3) & 0xFF, (CUT_OAM_SNAP + 3) >> 8)
    a.emit(0xC8, 0xC8, 0xC8, 0xC8)
    a.emit(0x8C, CUT_OAM_COUNT & 0xFF, CUT_OAM_COUNT >> 8)
    a.emit(0xC0, 64)
    a.branch(0xB0, "snap_done")
    a.label("snap_next")
    a.emit(0xE8, 0xE8, 0xE8, 0xE8)
    a.branch(0xD0, "snap_lp")
    a.label("snap_done")

    # 2. Pick RNG script index (0..3) from frame/timer entropy
    a.emit(0xA5, 0x02, 0x4D, 0x12, 0x05, 0x45, 0x44, 0x29, 0x03)
    a.emit(0x8D, CUT_SCRIPT_IDX & 0xFF, CUT_SCRIPT_IDX >> 8)

    # 3. Blank PPU, silence APU, disable IRQ, switch CHR
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20, 0x8D, 0x00, 0xE0)
    a.emit(0x8D, 0x15, 0x40, 0xA9, 0x0F, 0x8D, 0x15, 0x40)
    a.emit(0xA9, 0x00, 0x8D, CUT_FRAME & 0xFF, CUT_FRAME >> 8, 0x8D, CUT_SHAKE & 0xFF, CUT_SHAKE >> 8)

    # Set MMC3 CHR banks: R0=48, R1=2, R2=44, R3=45, R4=46, R5=47
    a.emit(0xA0, 0, 0xA9, 48); a.abs_ref(0x20, "SetChrBank")
    a.emit(0xA0, 1, 0xA9, 2);  a.abs_ref(0x20, "SetChrBank")
    a.emit(0xA0, 2, 0xA9, 44); a.abs_ref(0x20, "SetChrBank")
    a.emit(0xA0, 3, 0xA9, 45); a.abs_ref(0x20, "SetChrBank")
    a.emit(0xA0, 4, 0xA9, 46); a.abs_ref(0x20, "SetChrBank")
    a.emit(0xA0, 5, 0xA9, 47); a.abs_ref(0x20, "SetChrBank")

    # 4. Clear NT0 ($2000-$23FF) to T_SPACE, attr = $AA (pal 2 = forest green)
    a.emit(0x2C, 0x02, 0x20)
    a.emit(0xA9, 0x20, 0x8D, 0x06, 0x20, 0xA9, 0x00, 0x8D, 0x06, 0x20)
    a.emit(0xA9, T_SPACE, 0xA2, 30, 0xA0, 32)
    a.label("clr_nt_lp")
    a.emit(0x8D, 0x07, 0x20, 0x88)
    a.branch(0xD0, "clr_nt_lp")
    a.emit(0xA0, 32, 0xCA)
    a.branch(0xD0, "clr_nt_lp")
    # Attributes ($23C0-$23FF): attr row 0 = $00 (box), attr row 1 = $A0 (top=box pal0, bot=canopy pal2), rest = $AA (pal 2)
    a.emit(0xA9, 0x00, 0xA2, 8)
    a.label("attr_top0")
    a.emit(0x8D, 0x07, 0x20, 0xCA)
    a.branch(0xD0, "attr_top0")
    a.emit(0xA9, 0xA0, 0xA2, 8)
    a.label("attr_top1")
    a.emit(0x8D, 0x07, 0x20, 0xCA)
    a.branch(0xD0, "attr_top1")
    a.emit(0xA9, 0xAA, 0xA2, 48)
    a.label("attr_bot")
    a.emit(0x8D, 0x07, 0x20, 0xCA)
    a.branch(0xD0, "attr_bot")

    # 5. Draw Dialogue Box Border (rows 1..6, cols 1..30)
    a.emit(0xA9, 1, 0xA2, 1); a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA9, T_BOX_TL, 0x8D, 0x07, 0x20)
    a.emit(0xA9, T_BOX_T, 0xA2, 28)
    a.label("bt_lp")
    a.emit(0x8D, 0x07, 0x20, 0xCA)
    a.branch(0xD0, "bt_lp")
    a.emit(0xA9, T_BOX_TR, 0x8D, 0x07, 0x20)

    a.emit(0xA9, 2, 0x8D, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.label("bm_lp")
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0xA2, 1); a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA9, T_BOX_L, 0x8D, 0x07, 0x20)
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0xA2, 30); a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA9, T_BOX_R, 0x8D, 0x07, 0x20)
    a.emit(0xEE, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0xC9, 6)
    a.branch(0x90, "bm_lp")

    a.emit(0xA9, 6, 0xA2, 1); a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA9, T_BOX_BL, 0x8D, 0x07, 0x20)
    a.emit(0xA9, T_BOX_B, 0xA2, 28)
    a.label("bb_lp")
    a.emit(0x8D, 0x07, 0x20, 0xCA)
    a.branch(0xD0, "bb_lp")
    a.emit(0xA9, T_BOX_BR, 0x8D, 0x07, 0x20)

    # 6. Draw Forest Clearing (canopy rows 7..10 = tile $10/$11, trunks rows 11..21 = $C4/$C5, dirt rows 22..29 = $E0/$E1)
    a.emit(0xA9, 7, 0x8D, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.label("canopy_r")
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0xA2, 0); a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA2, 32, 0xA9, 0x10)
    a.label("canopy_c")
    a.emit(0x8D, 0x07, 0x20, 0x49, 0x01, 0xCA)
    a.branch(0xD0, "canopy_c")
    a.emit(0xEE, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0xC9, 11)
    a.branch(0x90, "canopy_r")

    # Tree trunks at cols 0, 5, 11, 15, 25, 29 on rows 11..21
    a.emit(0xA9, 11, 0x8D, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.label("tr_row")
    a.emit(0xA0, 0)
    a.label("tr_col")
    a.abs_ref(0xB9, "TreeCols")
    a.emit(0xC9, 0xFF)
    a.branch(0xF0, "tr_next_r")
    a.emit(0xAA, 0x98, 0x48)  # X=col, push Y
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)  # A=row
    a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA9, T_TRUNK, 0x8D, 0x07, 0x20)
    a.emit(0x68, 0xA8, 0xC8)
    a.abs_ref(0x4C, "tr_col")
    a.label("tr_next_r")
    a.emit(0xEE, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0xC9, 22)
    a.branch(0x90, "tr_row")

    # Ground rows 22..29: grass/dirt ($E0/$E1) — if Debbie ($7C60 == 1), cols 24..31 are Cliff/Pit!
    a.emit(0xA9, 22, 0x8D, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.label("gnd_row")
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0xA2, 0); a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA2, 0)  # col 0..31
    a.label("gnd_col")
    a.emit(0xAD, COVEN_ENDING_FLAG & 0xFF, COVEN_ENDING_FLAG >> 8, 0xC9, 0x01)
    a.branch(0xD0, "gnd_dirt")
    a.emit(0xE0, 24)
    a.branch(0x90, "gnd_dirt")
    a.emit(0xE0, 24)
    a.branch(0xD0, "gnd_pit")
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0xC9, 22)
    a.branch(0xD0, "gnd_cwall")
    a.emit(0xA9, T_CLIFF_TOP)
    a.abs_ref(0x4C, "gnd_wr")
    a.label("gnd_cwall")
    a.emit(0xA9, T_CLIFF_WALL)
    a.abs_ref(0x4C, "gnd_wr")
    a.label("gnd_pit")
    a.emit(0xA9, T_PIT_BLACK)
    a.abs_ref(0x4C, "gnd_wr")
    a.label("gnd_dirt")
    a.emit(0xA9, 0xE0)
    a.label("gnd_wr")
    a.emit(0x8D, 0x07, 0x20, 0xE8, 0xE0, 32)
    a.branch(0x90, "gnd_col")
    a.emit(0xEE, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0xC9, 30)
    a.branch(0x90, "gnd_row")

    # Set attributes for Barba positions (rows 16..21 -> attr rows 4..5, cols 2..4, 7..9 = pal 0/1; 17..19, 21..23 = pal 0/1)
    # Attr row 4 ($23E0..$23E7) and row 5 ($23E8..$23EF):
    #   byte 0 (cols 0..3): pal 0 ($00)  byte 1 (cols 4..7): pal 1 ($55)
    #   byte 2 (cols 8..11): pal 1 ($55) byte 4 (cols 16..19): pal 0 ($00)
    #   byte 5 (cols 20..23): pal 1 ($55)
    a.emit(0xA2, 0)
    a.label("b_attr_lp")
    a.emit(0xA9, 0x23, 0x8D, 0x06, 0x20)
    a.emit(0x8A, 0x18, 0x69, 0xE0, 0x8D, 0x06, 0x20)
    a.abs_ref(0xBD, "CovenAttrRow")
    a.emit(0x8D, 0x07, 0x20)
    a.emit(0xA9, 0x23, 0x8D, 0x06, 0x20)
    a.emit(0x8A, 0x18, 0x69, 0xE8, 0x8D, 0x06, 0x20)
    a.abs_ref(0xBD, "CovenAttrRow")
    a.emit(0x8D, 0x07, 0x20)
    a.emit(0xE8, 0xE0, 8)
    a.branch(0x90, "b_attr_lp")

    # 7. Load Palettes ($3F00-$3F1F)
    a.emit(0xA9, 0x3F, 0x8D, 0x06, 0x20, 0xA9, 0x00, 0x8D, 0x06, 0x20)
    a.emit(0xA2, 0)
    a.label("pal_lp")
    a.abs_ref(0xBD, "CovenPalette")
    a.emit(0x8D, 0x07, 0x20, 0xE8, 0xE0, 32)
    a.branch(0x90, "pal_lp")

    # 8. Place Debbie/Laura at (X=112, Y=154) and turn rendering on!
    a.abs_ref(0x20, "ClearOam")
    a.emit(0xA9, 112, 0x8D, CUT_PX & 0xFF, CUT_PX >> 8)
    a.emit(0xA9, 154, 0x8D, CUT_PY & 0xFF, CUT_PY >> 8)
    a.abs_ref(0x20, "DrawPlayerOam")
    a.abs_ref(0x20, "WaitVBlank")
    a.emit(0xA9, 0x10, 0x8D, 0x00, 0x20)  # BG=$1000, Sprites=$0000, NT0
    a.emit(0xA9, 0x00, 0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)
    a.emit(0xA9, 0x1E, 0x8D, 0x01, 0x20)

    a.emit(0xA2, 25); a.abs_ref(0x20, "WaitFrames")

    # =========================================================================
    # Phase 1: Coven Arrival (spawn 4 Barbas one by one, bake into BG!)
    # =========================================================================
    a.emit(0xA9, 0, 0x8D, CUT_TIMER & 0xFF, CUT_TIMER >> 8)  # Barba idx 0..3
    a.label("arrive_lp")
    # Play materialize chime
    a.emit(0xA9, 0x90, 0xA2, 0x88); a.abs_ref(0x20, "PlayBlip")
    a.emit(0xA2, 6); a.abs_ref(0x20, "WaitFrames")
    a.abs_ref(0x20, "WaitVBlank")
    a.emit(0xAE, CUT_TIMER & 0xFF, CUT_TIMER >> 8)
    a.abs_ref(0xBD, "BarbaColTbl"); a.emit(0x8D, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.emit(0xA9, 16, 0x8D, CUT_TMP1 & 0xFF, CUT_TMP1 >> 8)
    a.abs_ref(0xBD, "BarbaDirTbl"); a.emit(0x8D, CUT_TMP2 & 0xFF, CUT_TMP2 >> 8)
    a.emit(0xA9, 0x00)
    a.abs_ref(0x20, "StampBarba")
    a.emit(0xA9, 0x00, 0x8D, 0x06, 0x20, 0x8D, 0x06, 0x20, 0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)
    a.emit(0xA2, 16); a.abs_ref(0x20, "WaitFrames")
    a.emit(0xEE, CUT_TIMER & 0xFF, CUT_TIMER >> 8)
    a.emit(0xAD, CUT_TIMER & 0xFF, CUT_TIMER >> 8, 0xC9, 4)
    a.branch(0x90, "arrive_lp")

    a.emit(0xA2, 20); a.abs_ref(0x20, "WaitFrames")

    # =========================================================================
    # Phase 2: King's Quest-Style Dialogue (Bank 3 $A000-$BFFF)
    # =========================================================================
    # Compute script pointer into ZP ($10, $11)
    a.emit(0xAD, COVEN_ENDING_FLAG & 0xFF, COVEN_ENDING_FLAG >> 8, 0xC9, 0x01)
    a.branch(0xD0, "use_lau_tbl")
    a.emit(0xA9, 0x00, 0xF0, 0x02)
    a.label("use_lau_tbl")
    a.emit(0xA9, 0x08)
    a.emit(0x18, 0x6D, CUT_SCRIPT_IDX & 0xFF, CUT_SCRIPT_IDX >> 8)
    a.emit(0x18, 0x6D, CUT_SCRIPT_IDX & 0xFF, CUT_SCRIPT_IDX >> 8)
    a.emit(0xAA)
    a.emit(0xBD, 0x00, 0xA0, 0x85, 0x10)
    a.emit(0xBD, 0x01, 0xA0, 0x85, 0x11)

    a.label("dlg_box_loop")
    a.emit(0xA0, 0x00, 0xB1, 0x10)  # speaker_id or $FF
    a.emit(0xC9, 0xFF)
    a.branch(0xD0, "dlg_have_box")
    a.abs_ref(0x4C, "Phase3Climax")

    a.label("dlg_have_box")
    a.emit(0x8D, CUT_SPEAKER & 0xFF, CUT_SPEAKER >> 8)
    a.emit(0xC8, 0xB1, 0x10, 0x85, 0x12)  # num_lines in $12
    # Advance ($10,$11) by 2 to point to line pointers
    a.emit(0xA5, 0x10, 0x18, 0x69, 0x02, 0x85, 0x10)
    a.branch(0x90, "dlg_p_ok")
    a.emit(0xE6, 0x11)
    a.label("dlg_p_ok")

    # Set mouth mask based on speaker
    a.emit(0xAE, CUT_SPEAKER & 0xFF, CUT_SPEAKER >> 8)
    a.abs_ref(0xBD, "SpeakerMaskTbl")
    a.emit(0x8D, CUT_MOUTH_MASK & 0xFF, CUT_MOUTH_MASK >> 8)

    a.abs_ref(0x20, "ClearBoxInterior")

    # Print speaker label at row 2, col 3
    a.abs_ref(0x20, "WaitVBlank")
    a.emit(0xA9, 2, 0xA2, 3); a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xAE, CUT_SPEAKER & 0xFF, CUT_SPEAKER >> 8)
    a.abs_ref(0xBD, "SpeakerPtrLo"); a.emit(0x85, 0x14)
    a.abs_ref(0xBD, "SpeakerPtrHi"); a.emit(0x85, 0x15)
    a.emit(0xA0, 0x00)
    a.label("spk_lbl_lp")
    a.emit(0xB1, 0x14, 0xC9, 0xFF)
    a.branch(0xF0, "spk_lbl_done")
    a.emit(0x8D, 0x07, 0x20, 0xC8)
    a.abs_ref(0x4C, "spk_lbl_lp")
    a.label("spk_lbl_done")
    a.emit(0xA9, 0x00, 0x8D, 0x06, 0x20, 0x8D, 0x06, 0x20, 0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)

    # If ALL: speaks, trigger 4-frame shake!
    a.emit(0xAD, CUT_SPEAKER & 0xFF, CUT_SPEAKER >> 8, 0xC9, SPK_ALL)
    a.branch(0xD0, "dlg_no_sh")
    a.emit(0xA9, 6, 0x8D, CUT_SHAKE & 0xFF, CUT_SHAKE >> 8)
    a.label("dlg_no_sh")

    # Typewriter each line (0..$12-1)
    a.emit(0xA9, 0, 0x85, 0x13)  # line_idx = 0
    a.label("line_lp")
    a.emit(0xA5, 0x13, 0x0A, 0xA8)
    a.emit(0xB1, 0x10, 0x85, 0x14, 0xC8, 0xB1, 0x10, 0x85, 0x15)  # ($14,$15) = line str
    a.emit(0xA5, 0x13, 0x18, 0x69, 3, 0x8D, CUT_TXT_ROW & 0xFF, CUT_TXT_ROW >> 8)
    a.emit(0xA9, 3, 0x8D, CUT_TXT_COL & 0xFF, CUT_TXT_COL >> 8)
    a.emit(0xA9, 0, 0x8D, CUT_TXT_IDX & 0xFF, CUT_TXT_IDX >> 8)

    a.label("char_lp")
    a.emit(0xAC, CUT_TXT_IDX & 0xFF, CUT_TXT_IDX >> 8)
    a.emit(0xB1, 0x14, 0xC9, 0xFF)
    a.branch(0xF0, "line_done")
    a.emit(0x48)  # save char
    a.abs_ref(0x20, "PresentFrame")
    a.emit(0xAD, CUT_TXT_ROW & 0xFF, CUT_TXT_ROW >> 8)
    a.emit(0xAE, CUT_TXT_COL & 0xFF, CUT_TXT_COL >> 8)
    a.abs_ref(0x20, "SetNtAddr")
    a.emit(0x68, 0x8D, 0x07, 0x20)
    a.emit(0xA9, 0x00, 0x8D, 0x06, 0x20, 0x8D, 0x06, 0x20, 0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)

    # Voice blip every 2 chars + mouth toggle every 4 chars
    a.emit(0xAD, CUT_TXT_IDX & 0xFF, CUT_TXT_IDX >> 8, 0x29, 0x01)
    a.branch(0xD0, "no_blip")
    a.emit(0xAE, CUT_SPEAKER & 0xFF, CUT_SPEAKER >> 8)
    a.abs_ref(0xBD, "SpeakerPitchTbl")
    a.emit(0xA2, 0x84)
    a.abs_ref(0x20, "PlayBlip")
    a.label("no_blip")

    # Mouth anim on bit 2 of CUT_FRAME
    a.emit(0xAD, CUT_FRAME & 0xFF, CUT_FRAME >> 8, 0x29, 0x04)
    a.emit(0xCD, CUT_MOUTH_STATE & 0xFF, CUT_MOUTH_STATE >> 8)
    a.branch(0xF0, "no_mouth_chg")
    a.emit(0x8D, CUT_MOUTH_STATE & 0xFF, CUT_MOUTH_STATE >> 8)
    a.abs_ref(0x20, "UpdateMouths")
    a.label("no_mouth_chg")

    a.emit(0xEE, CUT_TXT_COL & 0xFF, CUT_TXT_COL >> 8)
    a.emit(0xEE, CUT_TXT_IDX & 0xFF, CUT_TXT_IDX >> 8)
    # 1 extra frame wait unless A/B held
    a.emit(0xAD, CUT_PAD_CUR & 0xFF, CUT_PAD_CUR >> 8, 0x29, 0xC0)
    a.branch(0xD0, "char_lp")
    a.abs_ref(0x20, "PresentFrame")
    a.abs_ref(0x4C, "char_lp")

    a.label("line_done")
    a.emit(0xE6, 0x13, 0xA5, 0x13, 0xC5, 0x12)
    a.branch(0xB0, "box_typed")
    a.abs_ref(0x4C, "line_lp")

    a.label("box_typed")
    # Close all mouths
    a.abs_ref(0x20, "WaitVBlank")
    a.emit(0xA9, 0x00, 0x8D, CUT_MOUTH_STATE & 0xFF, CUT_MOUTH_STATE >> 8)
    a.abs_ref(0x20, "UpdateMouths")

    # Wait for fresh A or B press with blinking arrow at row 5, col 29
    a.label("wait_btn_lp")
    a.abs_ref(0x20, "PresentFrame")
    a.emit(0xA9, 5, 0xA2, 29); a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xAD, CUT_FRAME & 0xFF, CUT_FRAME >> 8, 0x29, 0x10)
    a.branch(0xF0, "arr_off")
    a.emit(0xA9, T_ARROW, 0xD0, 0x02)
    a.label("arr_off")
    a.emit(0xA9, T_SPACE)
    a.emit(0x8D, 0x07, 0x20)
    a.emit(0xA9, 0x00, 0x8D, 0x06, 0x20, 0x8D, 0x06, 0x20, 0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)
    a.emit(0xAD, CUT_PAD_NEW & 0xFF, CUT_PAD_NEW >> 8, 0x29, 0xC0)
    a.branch(0xF0, "wait_btn_lp")

    # Advance ($10,$11) by 2 * num_lines to next box
    a.emit(0xA5, 0x12, 0x0A, 0x18, 0x65, 0x10, 0x85, 0x10)
    a.branch(0x90, "nxt_b_ok")
    a.emit(0xE6, 0x11)
    a.label("nxt_b_ok")
    a.abs_ref(0x4C, "dlg_box_loop")

    # Helper: UpdateMouths (updates up to 2 Barbas per call to stay well inside VBlank)
    a.label("UpdateMouths")
    a.emit(0xAD, CUT_MOUTH_MASK & 0xFF, CUT_MOUTH_MASK >> 8)
    a.emit(0xC9, 0x0F)
    a.branch(0xD0, "um_start")
    # ALL: alternate (0,1) vs (2,3) based on CUT_FRAME bit 3
    a.emit(0xAD, CUT_FRAME & 0xFF, CUT_FRAME >> 8, 0x29, 0x08)
    a.branch(0xD0, "um_all_23")
    a.emit(0xA9, 0x03, 0xD0, 0x02)
    a.label("um_all_23")
    a.emit(0xA9, 0x0C)
    a.label("um_start")
    a.emit(0x85, 0x07)  # effective mask in $07
    a.emit(0xA2, 0x00)
    a.label("um_lp")
    a.abs_ref(0xBD, "BitTbl")
    a.emit(0x25, 0x07)
    a.branch(0xF0, "um_nxt")
    a.emit(0x8A, 0x48)
    a.emit(0xAD, CUT_MOUTH_STATE & 0xFF, CUT_MOUTH_STATE >> 8)
    a.abs_ref(0x20, "StampBarbaHead")
    a.emit(0x68, 0xAA)
    a.label("um_nxt")
    a.emit(0xE8, 0xE0, 4)
    a.branch(0x90, "um_lp")
    a.emit(0xA9, 0x00, 0x8D, 0x06, 0x20, 0x8D, 0x06, 0x20, 0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)
    a.emit(0x60)

    # =========================================================================
    # Phase 3: Climax (Debbie Cliff vs Laura Noodles)
    # =========================================================================
    a.label("Phase3Climax")
    a.abs_ref(0x20, "ClearBoxInterior")
    a.emit(0xAD, COVEN_ENDING_FLAG & 0xFF, COVEN_ENDING_FLAG >> 8, 0xC9, 0x01)
    a.branch(0xF0, "ClimaxDebbie")
    a.abs_ref(0x4C, "ClimaxLaura")

    # --- Debbie: Magic levitation + float over cliff + pit drop ---
    a.label("ClimaxDebbie")
    a.emit(0xA9, 0, 0x8D, CUT_TIMER & 0xFF, CUT_TIMER >> 8)
    a.label("deb_lift_lp")
    a.abs_ref(0x20, "ClearOam")
    a.abs_ref(0x20, "DrawPlayerOam")
    # Draw 4 orbiting magic sparkles around (CUT_PX+4, CUT_PY+16)
    a.abs_ref(0x20, "DrawSparkleRing")
    a.emit(0xCE, CUT_PY & 0xFF, CUT_PY >> 8)  # rise 1px/frame
    a.emit(0xAD, CUT_TIMER & 0xFF, CUT_TIMER >> 8, 0x29, 0x03)
    a.branch(0xD0, "deb_no_s1")
    a.emit(0xA9, 0x60, 0x38, 0xED, CUT_TIMER & 0xFF, CUT_TIMER >> 8, 0xA2, 0x86)
    a.abs_ref(0x20, "PlayBlip")
    a.label("deb_no_s1")
    a.abs_ref(0x20, "PresentFrame")
    a.emit(0xEE, CUT_TIMER & 0xFF, CUT_TIMER >> 8)
    a.emit(0xAD, CUT_TIMER & 0xFF, CUT_TIMER >> 8, 0xC9, 44)
    a.branch(0x90, "deb_lift_lp")

    # Float right over the pit (X: 112 -> 212 = 50 frames at +2px/frame)
    a.emit(0xA9, 0, 0x8D, CUT_TIMER & 0xFF, CUT_TIMER >> 8)
    a.label("deb_flt_lp")
    a.abs_ref(0x20, "ClearOam")
    a.abs_ref(0x20, "DrawPlayerOam")
    a.abs_ref(0x20, "DrawSparkleRing")
    a.emit(0xEE, CUT_PX & 0xFF, CUT_PX >> 8, 0xEE, CUT_PX & 0xFF, CUT_PX >> 8)
    a.abs_ref(0x20, "PresentFrame")
    a.emit(0xEE, CUT_TIMER & 0xFF, CUT_TIMER >> 8)
    a.emit(0xAD, CUT_TIMER & 0xFF, CUT_TIMER >> 8, 0xC9, 50)
    a.branch(0x90, "deb_flt_lp")

    # Drop into the pit!
    a.emit(0xA9, 1, 0x8D, CUT_PVY & 0xFF, CUT_PVY >> 8)
    a.emit(0xA9, 0, 0x8D, CUT_TIMER & 0xFF, CUT_TIMER >> 8)
    a.label("deb_drop_lp")
    a.abs_ref(0x20, "ClearOam")
    a.abs_ref(0x20, "DrawPlayerOam")
    a.emit(0xAD, CUT_PY & 0xFF, CUT_PY >> 8, 0x18, 0x6D, CUT_PVY & 0xFF, CUT_PVY >> 8)
    a.emit(0x8D, CUT_PY & 0xFF, CUT_PY >> 8)
    a.emit(0xAD, CUT_TIMER & 0xFF, CUT_TIMER >> 8, 0x29, 0x03)
    a.branch(0xD0, "deb_no_acc")
    a.emit(0xEE, CUT_PVY & 0xFF, CUT_PVY >> 8)
    a.label("deb_no_acc")
    # Descending whistle pitch
    a.emit(0xAD, CUT_TIMER & 0xFF, CUT_TIMER >> 8, 0x0A, 0x0A, 0x18, 0x69, 0x40, 0xA2, 0x88)
    a.abs_ref(0x20, "PlayBlip")
    a.abs_ref(0x20, "PresentFrame")
    a.emit(0xEE, CUT_TIMER & 0xFF, CUT_TIMER >> 8)
    a.emit(0xAD, CUT_PY & 0xFF, CUT_PY >> 8, 0xC9, 232)
    a.branch(0x90, "deb_drop_lp")

    # Thud + shake!
    a.abs_ref(0x20, "ClearOam")
    a.emit(0xA9, 14, 0x8D, CUT_SHAKE & 0xFF, CUT_SHAKE >> 8)
    a.emit(0xA9, 0xFF, 0xA2, 0x8F); a.abs_ref(0x20, "PlayBlip")
    a.emit(0xA2, 35); a.abs_ref(0x20, "WaitFrames")
    a.abs_ref(0x4C, "Phase4Ending")

    # Helper: DrawSparkleRing (4 OAM sprites after player OAM)
    a.label("DrawSparkleRing")
    a.emit(0xAD, CUT_OAM_COUNT & 0xFF, CUT_OAM_COUNT >> 8, 0xAA)
    a.emit(0xA9, 0, 0x8D, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.label("dsr_lp2")
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0x0A, 0x0A)
    a.emit(0x18, 0x6D, CUT_FRAME & 0xFF, CUT_FRAME >> 8, 0x29, 0x0F, 0xA8)
    a.abs_ref(0xB9, "SparkleDy"); a.emit(0x18, 0x6D, CUT_PY & 0xFF, CUT_PY >> 8, 0x9D, 0x00, 0x02)
    a.emit(0xAD, CUT_FRAME & 0xFF, CUT_FRAME >> 8, 0x29, 0x04)
    a.branch(0xF0, "dsr_sp1")
    a.emit(0xA9, T_SPARKLE_0, 0xD0, 0x02)
    a.label("dsr_sp1")
    a.emit(0xA9, T_SPARKLE_1)
    a.emit(0x9D, 0x01, 0x02)
    a.emit(0xA9, 0x00, 0x9D, 0x02, 0x02)  # pal 0 (bright white/red sparkles)
    a.abs_ref(0xB9, "SparkleDx"); a.emit(0x18, 0x6D, CUT_PX & 0xFF, CUT_PX >> 8, 0x9D, 0x03, 0x02)
    a.emit(0xE8, 0xE8, 0xE8, 0xE8)
    a.emit(0xEE, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0xC9, 4)
    a.branch(0x90, "dsr_lp2")
    a.emit(0x60)

    # --- Laura: Noodles erupt from ground, shoot up & grab her, yank her down ---
    a.label("ClimaxLaura")
    # Stamp BG noodle puddle at row 22, cols 12..18
    a.abs_ref(0x20, "WaitVBlank")
    a.emit(0xA9, 22, 0xA2, 12); a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA2, 7, 0xA9, T_NOODLE_0)
    a.label("np_lp")
    a.emit(0x8D, 0x07, 0x20, 0x49, 0x01, 0xCA)
    a.branch(0xD0, "np_lp")
    a.emit(0xA9, 0x00, 0x8D, 0x06, 0x20, 0x8D, 0x06, 0x20, 0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)
    a.emit(0xA9, 6, 0x8D, CUT_SHAKE & 0xFF, CUT_SHAKE >> 8)
    a.emit(0xA9, 0xD0, 0xA2, 0x8A); a.abs_ref(0x20, "PlayBlip")
    a.emit(0xA2, 16); a.abs_ref(0x20, "WaitFrames")

    # Rise 3 noodle tendrils up around Laura (height 0 -> 32px in 24 frames)
    a.emit(0xA9, 0, 0x8D, CUT_TIMER & 0xFF, CUT_TIMER >> 8)
    a.label("noodle_rise_lp")
    a.abs_ref(0x20, "ClearOam")
    a.abs_ref(0x20, "DrawPlayerOam")
    a.abs_ref(0x20, "DrawNoodleTendrils")
    a.emit(0xAD, CUT_TIMER & 0xFF, CUT_TIMER >> 8, 0x29, 0x03)
    a.branch(0xD0, "nr_ns")
    a.emit(0xA9, 0xC0, 0xA2, 0x86); a.abs_ref(0x20, "PlayBlip")
    a.label("nr_ns")
    a.abs_ref(0x20, "PresentFrame")
    a.emit(0xEE, CUT_TIMER & 0xFF, CUT_TIMER >> 8)
    a.emit(0xAD, CUT_TIMER & 0xFF, CUT_TIMER >> 8, 0xC9, 28)
    a.branch(0x90, "noodle_rise_lp")

    # Yank Laura + noodles straight down off screen!
    a.emit(0xA9, 12, 0x8D, CUT_SHAKE & 0xFF, CUT_SHAKE >> 8)
    a.label("noodle_yank_lp")
    a.abs_ref(0x20, "ClearOam")
    a.abs_ref(0x20, "DrawPlayerOam")
    a.abs_ref(0x20, "DrawNoodleTendrils")
    a.emit(0xEE, CUT_PY & 0xFF, CUT_PY >> 8, 0xEE, CUT_PY & 0xFF, CUT_PY >> 8)
    a.emit(0xAD, CUT_FRAME & 0xFF, CUT_FRAME >> 8, 0x29, 0x03)
    a.branch(0xD0, "ny_ns")
    a.emit(0xA9, 0xE0, 0xA2, 0x8C); a.abs_ref(0x20, "PlayBlip")
    a.label("ny_ns")
    a.abs_ref(0x20, "PresentFrame")
    a.emit(0xAD, CUT_PY & 0xFF, CUT_PY >> 8, 0xC9, 224)
    a.branch(0x90, "noodle_yank_lp")

    a.abs_ref(0x20, "ClearOam")
    a.emit(0xA2, 30); a.abs_ref(0x20, "WaitFrames")
    a.abs_ref(0x4C, "Phase4Ending")

    # Helper: DrawNoodleTendrils (6 OAM sprites: 3 columns x 2 rows anchored around Laura)
    a.label("DrawNoodleTendrils")
    a.emit(0xAD, CUT_OAM_COUNT & 0xFF, CUT_OAM_COUNT >> 8, 0xAA)
    a.emit(0xA9, 0, 0x8D, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.label("dnt_lp")
    a.emit(0xAC, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.abs_ref(0xB9, "TendrilDy")
    a.emit(0x18, 0x6D, CUT_PY & 0xFF, CUT_PY >> 8)
    a.branch(0xB0, "dnt_hide")
    a.emit(0xC9, 0xEF)
    a.branch(0x90, "dnt_y_ok")
    a.label("dnt_hide")
    a.emit(0xA9, 0xFE)
    a.label("dnt_y_ok")
    a.emit(0x9D, 0x00, 0x02)
    a.abs_ref(0xB9, "TendrilTile")
    a.emit(0x9D, 0x01, 0x02)
    a.emit(0xA9, 0x00, 0x9D, 0x02, 0x02)  # pal 0 (bright gold/yellow pasta)
    a.abs_ref(0xB9, "TendrilDx")
    a.emit(0x18, 0x6D, CUT_PX & 0xFF, CUT_PX >> 8)
    # Wiggle +-1px on frame bit 2
    a.emit(0x48, 0xAD, CUT_FRAME & 0xFF, CUT_FRAME >> 8, 0x29, 0x04)
    a.branch(0xF0, "dnt_w0")
    a.emit(0x68, 0x18, 0x69, 0x01, 0xD0, 0x02)
    a.label("dnt_w0")
    a.emit(0x68)
    a.emit(0x9D, 0x03, 0x02)
    a.emit(0xE8, 0xE8, 0xE8, 0xE8)
    a.emit(0xEE, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8)
    a.emit(0xAD, CUT_TMP0 & 0xFF, CUT_TMP0 >> 8, 0xC9, 6)
    a.branch(0x90, "dnt_lp")
    a.emit(0x60)

    # =========================================================================
    # Phase 4: King's Quest Card ("WELL THAT WAS WEIRD.") + Exit
    # =========================================================================
    a.label("Phase4Ending")
    a.emit(0xA9, 0x00, 0x8D, 0x01, 0x20, 0x8D, 0x15, 0x40)
    a.abs_ref(0x20, "ClearOam")
    # Clear NT0 + Attr0 to 0
    a.emit(0xA9, 0x20, 0x8D, 0x06, 0x20, 0xA9, 0x00, 0x8D, 0x06, 0x20)
    a.emit(0xA9, T_SPACE, 0xA2, 30, 0xA0, 32)
    a.label("e_clr")
    a.emit(0x8D, 0x07, 0x20, 0x88)
    a.branch(0xD0, "e_clr")
    a.emit(0xA0, 32, 0xCA)
    a.branch(0xD0, "e_clr")
    a.emit(0xA9, 0x00, 0xA2, 64)
    a.label("e_attr")
    a.emit(0x8D, 0x07, 0x20, 0xCA)
    a.branch(0xD0, "e_attr")

    # Write "WELL THAT WAS WEIRD." at row 13, col 6
    a.emit(0xA9, 13, 0xA2, 6); a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA2, 0)
    a.label("ew_lp")
    a.abs_ref(0xBD, "EndCardMsg")
    a.emit(0xC9, 0xFF)
    a.branch(0xF0, "ew_done")
    a.emit(0x8D, 0x07, 0x20, 0xE8)
    a.abs_ref(0x4C, "ew_lp")
    a.label("ew_done")

    a.abs_ref(0x20, "WaitVBlank")
    a.emit(0xA9, 0x10, 0x8D, 0x00, 0x20)  # BG=$1000, Sprites=$0000, NT0
    a.emit(0xA9, 0x00, 0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)
    a.emit(0xA9, 0x1E, 0x8D, 0x01, 0x20)
    a.emit(0xA2, 45); a.abs_ref(0x20, "WaitFrames")

    # Write "PRESS START" at row 16, col 10
    a.abs_ref(0x20, "WaitVBlank")
    a.emit(0xA9, 16, 0xA2, 10); a.abs_ref(0x20, "SetNtAddr")
    a.emit(0xA2, 0)
    a.label("ps_lp")
    a.abs_ref(0xBD, "PressStartMsg")
    a.emit(0xC9, 0xFF)
    a.branch(0xF0, "ps_done")
    a.emit(0x8D, 0x07, 0x20, 0xE8)
    a.abs_ref(0x4C, "ps_lp")
    a.label("ps_done")
    a.emit(0xA9, 0x00, 0x8D, 0x06, 0x20, 0x8D, 0x06, 0x20, 0x8D, 0x05, 0x20, 0x8D, 0x05, 0x20)

    a.label("wait_end_btn")
    a.abs_ref(0x20, "PresentFrame")
    a.emit(0xAD, CUT_PAD_NEW & 0xFF, CUT_PAD_NEW >> 8, 0x29, 0x90)  # A ($80) or Start ($10)
    a.branch(0xF0, "wait_end_btn")

    # Exit: standalone -> reset ($FFFC); combined Z2 -> F13_WIN_HOOK ($7E80)
    a.emit(0xAD, F13_PRG_BASE & 0xFF, F13_PRG_BASE >> 8)
    a.branch(0xD0, "ret_to_z2")
    a.emit(0x6C, 0xFC, 0xFF)  # JMP ($FFFC)
    a.label("ret_to_z2")
    a.emit(0x4C, F13_WIN_HOOK & 0xFF, F13_WIN_HOOK >> 8)

    # =========================================================================
    # Data Tables in Bank 2
    # =========================================================================
    a.label("TreeCols"); a.emit(13, 15, 25, 29, 0xFF)
    a.label("BarbaColTbl"); a.emit(1, 5, 17, 21)
    a.label("BarbaDirTbl"); a.emit(0, 0, 1, 1)  # 0=right-facing, 1=left-facing
    a.label("CovenAttrRow"); a.emit(0x00, 0x55, 0x55, 0xAA, 0x00, 0x55, 0xAA, 0xAA)
    a.label("CovenPalette")
    a.emit(
        0x0F, 0x16, 0x27, 0x30,  # BG0: Red Barba / Gold / White
        0x0F, 0x1A, 0x27, 0x30,  # BG1: Green Barba / Gold / White
        0x0F, 0x0B, 0x1B, 0x08,  # BG2: Forest greens
        0x0F, 0x0B, 0x1B, 0x18,  # BG3: Forest dirt
        0x0F, 0x27, 0x28, 0x30,  # SPR0: gold/yellow/white (sparkles & noodles!)
        0x0F, 0x27, 0x1C, 0x0F,  # SPR1 (Debbie/Laura/Noodles)
        0x0F, 0x17, 0x35, 0x0F,  # SPR2 (Laura skin/dress)
        0x0F, 0x2C, 0x35, 0x0F,  # SPR3 (Debbie skin/dress)
    )
    a.label("BitTbl"); a.emit(0x01, 0x02, 0x04, 0x08)
    a.label("SpeakerMaskTbl"); a.emit(0x01, 0x02, 0x04, 0x08, 0x0F, 0x00, 0x00)
    a.label("SpeakerPitchTbl"); a.emit(0xE0, 0xB8, 0x98, 0x78, 0xF8, 0x58, 0x50)
    a.label("SpeakerPtrLo")
    for i in range(7):
        a.emit(b3.labels[f"spk_lbl_{i}"] & 0xFF)
    a.label("SpeakerPtrHi")
    for i in range(7):
        a.emit(b3.labels[f"spk_lbl_{i}"] >> 8)

    a.label("SparkleDy"); a.emit(
        0, 3, 8, 13, 16, 13, 8, 3, 0, 253, 248, 243, 240, 243, 248, 253
    )
    a.label("SparkleDx"); a.emit(
        8, 13, 16, 13, 8, 3, 0, 253, 248, 253, 0, 3, 8, 13, 16, 13
    )
    a.label("TendrilDy"); a.emit(16, 24, 12, 20, 16, 24)
    a.label("TendrilDx"); a.emit(252, 252, 4, 4, 12, 12)
    a.label("TendrilTile"); a.emit(T_TENDRIL_0, T_TENDRIL_1, T_TENDRIL_3, T_TENDRIL_2, T_TENDRIL_0, T_TENDRIL_1)

    a.label("EndCardMsg"); a.emit(*encode_text("WELL THAT WAS WEIRD."), 0xFF)
    a.label("PressStartMsg"); a.emit(*encode_text("PRESS START"), 0xFF)

    bank2_raw = a.finish()
    assert len(bank2_raw) <= 8192, f"Bank 2 overflow: {len(bank2_raw)}"
    bank2 = bytearray(b"\xFF" * 8192)
    bank2[0 : len(bank2_raw)] = bank2_raw

    return bytes(bank2), bytes(bank3)
