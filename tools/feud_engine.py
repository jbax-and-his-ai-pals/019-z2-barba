"""Dynamic cast, palette, Zelda names/lose messages, and idle animations for Family Feud: Barba Edition."""
from __future__ import annotations

from feud_art import build_cast_rom_banks, patch_chr0b_blue_k
from pack_f13 import Asm6502

WRAM_EXTRA_ORG = 0x7B00
BANK4_EXTRA_OFF = 0x0400
BANK4_CODE_ORG = 0x8900
BANK4_CODE_OFF = 0x0900

# WRAM State Layout ($6000-$6EFF - unused by Family Feud)
W_P1_CHAR       = 0x6000  # 5 bytes: Barba pool char_id (0..13)
W_P1_HEIGHT     = 0x6005  # 5 bytes: height preset (0..2)
W_P1_PAL_IDX    = 0x600A  # 5 bytes: BG pal slot (1..3)
W_CPU_CHAR      = 0x600F  # 5 bytes: Z2 pool char_id (0..15)
W_CPU_HEIGHT    = 0x6014  # 5 bytes: height preset (0..2)
W_CPU_PAL_IDX   = 0x6019  # 5 bytes: BG pal slot (1..3)
W_P1_PAL_CLR    = 0x601E  # 6 bytes: [c1_p1, c2_p1, c1_p2, c2_p2, c1_p3, c2_p3]
W_CPU_PAL_CLR   = 0x6024  # 6 bytes: [c1_p1, c2_p1, c1_p2, c2_p2, c1_p3, c2_p3]
W_ROLLED_MAGIC  = 0x602A  # 0x5A when rolled
W_SIDE_ARG      = 0x602B
W_SEAT_IDX      = 0x602C
W_VAR_BANK      = 0x602D
W_VAR_LO        = 0x602E
W_VAR_HI        = 0x602F
W_P1_ST_ATTR    = 0x6030  # 14 bytes Stage Close-Up $23E1..$23EE
W_CPU_ST_ATTR   = 0x6040  # 14 bytes Stage Close-Up $23E1..$23EE
W_P1_OV_ATTR    = 0x6050  # 3 bytes Overview $23E0..$23E2
W_CPU_OV_ATTR   = 0x6053  # 3 bytes Overview $23E5..$23E7
W_CPU_FO_ATTR   = 0x6056  # 9 bytes Face-Off $23DC..$23DE, $23E4..$23E6, $23EC..$23EE (== W_P1_OV_ATTR + 6)
W_FO_COLORS     = 0x6080  # 4 bytes: [p1_c1, p1_c2, cpu_c1, cpu_c2]
W_IDLE_TIMER    = 0x6060
W_IDLE_SEAT     = 0x6061  # $FF if idle, else 0..4 (stage) or 0..9 (ov)
W_IDLE_POSE     = 0x6062  # 1=roar, 2=wiggle
W_IDLE_HOLD     = 0x6063
W_IDLE_VIEW     = 0x6064  # 0=stage, 1=overview
W_OV_FREE_IDX   = 0x6065
W_LAST_LOSE_IDX = 0x6066  # 0..6
W_ST_FREE_IDX   = 0x6067
W_TILE_BASE     = 0x6068
W_BLK_PTR_LO    = 0x6069
W_BLK_PTR_HI    = 0x606A
W_COPY_CNT      = 0x606B
W_ST_CNT        = 0x606C
W_OV_CNT        = 0x606D
W_FO_CNT        = 0x606E
W_IDLE_REP      = 0x606F
W_CUR_CHR0      = 0x6070
W_CUR_CHR1      = 0x6071
W_TMP0          = 0x6072
W_TMP1          = 0x6073
W_TMP2          = 0x6074
W_TMP3          = 0x6075
W_JMP_LO        = 0x6076
W_JMP_HI        = 0x6077
W_SAVE_0E       = 0x6078
W_SAVE_0F       = 0x6079
W_SAVE_11       = 0x607A
W_SAVE_12       = 0x607B
W_SAVE_0C       = 0x607C
W_SAVE_0D       = 0x607D
W_CHR_MODE      = 0x607E  # $01 = CHR-ROM, $21 = CHR-RAM ($5FF0 shadow)
W_OV_HOLD       = 0x6084  # 10 bytes ($6084..$608D): Overview per-seat roar timer (0=idle, 1=restore, 2..31=roar)
W_LAST_ST_SEAT  = 0x608E  # 1 byte: last animated Stage Close-Up seat (0..4, or $FF)
W_CELEB_ACTIVE  = 0x608F  # 1 byte: 0=normal, 1=head-tilt celeb, 2=roar+shake
W_SHAKE_X       = 0x6090  # 1 byte: signed horizontal scroll shake (-3..+3)
W_CELEB_STEP    = 0x6091  # 1 byte: head-tilt wave index (0..4)
W_CELEB_HOLD    = 0x6092  # 1 byte: head-tilt phase pause timer
W_CELEB_POSE    = 0x6093  # 1 byte: current wave target pose (0=idle, 2=wiggle)
W_CELEB_DELAY   = 0x6094  # 1 byte: stagger frame divider
W_ROAR_LEFT     = 0x6095  # 1 byte: remaining roars in burst
W_ROAR_GAP      = 0x6096  # 1 byte: inter-roar / post-roar wait frames
W_ROAR_LAST_R   = 0x6097  # 1 byte: previous DMC rate index
W_ROAR_MIN      = 0x6098  # 1 byte: minimum frames before polling $4015
W_SHAKE_IDX     = 0x6099  # 1 byte: shake table cursor
W_CELEB_RNG     = 0x609A  # 2 bytes ($609A-$609B): 16-bit xorshift PRNG
W_ROAR_SEAT_Q   = 0x609C  # 1 byte: queued roar-snap seat cursor (0..5)
W_ST_HOLD       = 0x60A0  # 5 bytes ($60A0-$60A4): Stage Close-Up per-seat frame hold timer
W_ST_CUR        = 0x60A5  # 5 bytes ($60A5-$60A9): Stage Close-Up per-seat current pose (0/1/2)
W_ST_TGT        = 0x60AA  # 5 bytes ($60AA-$60AE): Stage Close-Up per-seat target pose (1=mouth, 2=wiggle)
W_ST_REP        = 0x60AF  # 5 bytes ($60AF-$60B3): Stage Close-Up per-seat remaining toggles
W_AMB_TMR_LO    = 0x60B4  # 1 byte: ambient soft roar countdown lo
W_AMB_TMR_HI    = 0x60B5  # 1 byte: ambient soft roar countdown hi
W_AMB_ROAR_ON   = 0x60B6  # 1 byte: 0=off, 1=poll $4015, 2..255=min hold before polling
CELEB_WRAM_ORG  = 0x7000  # 1 KB ($7000-$73FF) round-win celebration engine

# Dynamic Block & Attribute Pointer Tables ($6100-$65FF)
W_BLK_DYN       = 0x6100
W_BLK_T_LO      = 0x6200
W_BLK_T_HI      = 0x6300
W_BLK_A_LO      = 0x6400
W_BLK_A_HI      = 0x6500

# Dynamic Block Payloads ($6600-$6EFF)
W_STAGE_BLKS    = 0x6600  # 10 seats * 3 poses * 26 bytes ($6600..$690B)
W_OV_BLKS       = 0x6A00  # 10 seats * 2 poses * 10 bytes ($6A00..$6AC7)
W_FO_OAM_ATTR   = 0x6B00  # 86 bytes: [7, 12, 1*84] ($6B00..$6B55)
W_FO_BLKS       = 0x6C00  # 2 active P1 7x12 blocks * 86 bytes ($6C00..$6CAB)
W_FO_CPU_BLKS   = 0x6D00  # 2 active CPU 6x12 blocks * 74 bytes ($6D00..$6D93)
W_CHRRAM_BUF    = 0x6E00  # 256 bytes staging buffer
W_FAST_PAL      = 0x6F00  # 256 bytes unrolled $D027 palette copy routine

# 3 palette slots x 4 subtle variations per slot (aligned: Slot 1=Red/Orange, Slot 2=Blue/Slate, Slot 3=Green/Gold)
BARBA_PALETTE_PAIRS = [
    # Slot 1: Crimson / Ember / Bronze Barbas
    (0x37, 0x26), (0x36, 0x27), (0x37, 0x17), (0x36, 0x06),
    # Slot 2: Cobalt / Slate / Royal Barbas
    (0x30, 0x12), (0x37, 0x00), (0x31, 0x02), (0x36, 0x13),
    # Slot 3: Emerald / Forest / Gold Barbas
    (0x37, 0x1A), (0x36, 0x2A), (0x38, 0x29), (0x37, 0x28),
]

Z2_PALETTE_PAIRS = [
    # Slot 1: Z2 Red / Orange / Gold (Moblin, Daira, Fokka, Bagu, Guard, Healer, Townswoman)
    (0x37, 0x26), (0x36, 0x27), (0x30, 0x26), (0x36, 0x17),
    # Slot 2: Z2 Blue / Bone / Indigo (Ironknuckle, Stalfos, Bot, Mago, Error, Old Woman)
    (0x30, 0x12), (0x30, 0x21), (0x30, 0x00), (0x37, 0x13),
    # Slot 3: Z2 Green / Peach / Gold (Link, Young Lad, Little Kid)
    (0x36, 0x2A), (0x36, 0x1A), (0x37, 0x2A), (0x36, 0x28),
]

# Canonical Z2 palette slot (1..3) matching each of the 16 characters in _build_z2_pool
Z2_CHAR_PAL_SLOTS = [
    3,  # z2_link
    2,  # z2_error
    1,  # z2_bagu
    1,  # z2_healer
    2,  # z2_oldwoman
    1,  # z2_guard
    2,  # z2_bot
    3,  # z2_lad
    3,  # z2_kid
    1,  # z2_fatwoman
    1,  # z2_moblin
    1,  # z2_daira
    2,  # z2_ironknuckle
    2,  # z2_stalfos
    2,  # z2_mago
    1,  # z2_fokka
]

# 8 alternating Barba seat palette patterns [seat0..seat4]; zero adjacent repeats in both Close-Up and Overview
BARBA_ALT_PATS = [
    2, 1, 3, 2, 1,
    3, 1, 2, 3, 1,
    1, 2, 3, 1, 2,
    3, 2, 1, 3, 2,
    1, 3, 2, 1, 3,
    2, 3, 1, 2, 3,
    3, 1, 3, 2, 1,
    2, 1, 2, 3, 1,
]

ZELDA_FAMILY_NAMES = [
    'HYRULE', 'BARBA', 'ZELDA', 'GANON', 'BAGU', 'ERROR', 'RAURU', 'RUTO',
    'SARIA', 'DARUNIA', 'NABOORU', 'IMPA', 'KASUTO', 'MIDO', 'FOKKA',
    'DAIRA', 'MOBLIN', 'STALFOS', 'CAROCK', 'GOOMA', 'GELDARM',
    'MAGO', 'GORON', 'OCTOROK', 'TINGLE',
]

CHR0B_BLUE_MAP: dict[str, int] = {
    ' ': 0x00,
    'G': 0x01, 'A': 0x02, 'M': 0x03, 'E': 0x04, 'T': 0x05, 'K': 0x06,
    'P': 0x09, 'R': 0x0A, 'S': 0x0B, 'N': 0x0C, 'F': 0x0D, 'I': 0x0E,
    'L': 0x0F, 'Y': 0x10, 'U': 0x11, 'D': 0x12, 'B': 0x13,
    'a': 0x14, 's': 0x15, 'e': 0x16, 'd': 0x17, 'o': 0x18, 'n': 0x19,
    't': 0x1A, 'h': 0x1B, 'l': 0x1C, 'v': 0x1D, 'i': 0x1E, 'p': 0x1F,
    'r': 0x20, 'g': 0x21, 'm': 0x22, 'u': 0x23, 'c': 0x24, 'b': 0x25,
    'y': 0x26, 'C': 0x27, '.': 0x28, '1': 0x2B, '9': 0x2C, ',': 0x2F,
    'f': 0x30, 'w': 0x31, '-': 0x35, 'k': 0xB4,
}

LOSE_REASONS = [
    'Due to lava,',
    'Due to Return of Ganon,',
    'Due to missing Triforce,',
    'Due to Attack 9,',
    'Due to not knowing Bagu,',
    'Due to missing eco-key,',
    'Due to softlocking,',
]


class FeudAsm(Asm6502):
    """Asm6502 extended with 16-bit literal/table references and long conditional branches."""

    def u16(self, val: int) -> None:
        self.emit(val & 0xFF, (val >> 8) & 0xFF)

    def op16(self, op: int, addr: int) -> None:
        self.emit(op, addr & 0xFF, (addr >> 8) & 0xFF)

    def ref_lo(self, target: str) -> None:
        self.emit(0)
        self.fixups.append(('lo', len(self.buf) - 1, target))

    def ref_hi(self, target: str) -> None:
        self.emit(0)
        self.fixups.append(('hi', len(self.buf) - 1, target))

    def ref16(self, target: str) -> None:
        self.emit(0, 0)
        self.fixups.append(('abs', len(self.buf) - 2, target))


def _encode_chr0b_blue(text: str) -> bytes:
    return bytes(CHR0B_BLUE_MAP[ch] for ch in text)


def _encode_chr0a_title(text: str) -> bytes:
    """Encode uppercase ASCII/digits/spaces into Face-Off CHR bank 0A tiles ($8F66 map)."""
    out = bytearray()
    for ch in text:
        if ch == ' ':
            out.append(0x01)
        elif '0' <= ch <= '9':
            out.append(0x43 + (ord(ch) - 0x30))
        elif 'A' <= ch <= 'Z':
            out.append(0x29 + (ord(ch) - 0x41))
        else:
            raise ValueError(f'Unsupported Face-Off title char: {ch!r}')
    out.append(0x00)
    return bytes(out)


ROUND_ORDINALS = (
    'FIRST', 'SECOND', 'THIRD', 'FOURTH', 'FIFTH',
    'SIXTH', 'SEVENTH', 'EIGHTH', 'NINTH', 'TENTH',
)


def _encode_names_blob() -> tuple[list[int], bytes]:
    offs: list[int] = []
    blob = bytearray()
    for name in ZELDA_FAMILY_NAMES:
        offs.append(len(blob))
        bs = [ord(c) for c in name]
        bs[-1] |= 0x80
        blob.extend(bs)
    return offs, bytes(blob)


def _assemble_bank4(cast: dict[str, object]) -> bytes:
    """Assemble the permanent PRG Bank 4 code & lookup tables ($8700-$9FFF)."""
    ov_free: bytes = cast['ov_free']       # type: ignore[assignment]
    st_p1_free: bytes = cast['st_p1_free'] # type: ignore[assignment]
    st_cpu_free: bytes = cast['st_cpu_free'] # type: ignore[assignment]
    fo_p1_free: bytes = cast['fo_p1_free'] # type: ignore[assignment]
    fo_cpu_free: bytes = cast['fo_cpu_free'] # type: ignore[assignment]
    fo_cpu_lip_ids: bytes = cast['fo_cpu_lip_ids'] # type: ignore[assignment]
    fo_cpu_lip_tiles: bytes = cast['fo_cpu_lip_tiles'] # type: ignore[assignment]
    fo_p1_bot2: bytes = cast['fo_p1_bot2'] # type: ignore[assignment]
    fo_cpu_bot2: bytes = cast['fo_cpu_bot2'] # type: ignore[assignment]
    barba_meta: list[tuple[int, int]] = cast['barba_meta'] # type: ignore[assignment]
    z2_meta: list[tuple[int, int]] = cast['z2_meta']       # type: ignore[assignment]
    barba_count = int(cast.get('barba_count', len(barba_meta) // 3))  # type: ignore[arg-type]
    z2_count = int(cast.get('z2_count', len(z2_meta) // 3))           # type: ignore[arg-type]
    barba_pal_pairs: list[tuple[int, int]] = cast.get('barba_pal_pairs', BARBA_PALETTE_PAIRS)  # type: ignore[assignment]
    z2_pal_pairs: list[tuple[int, int]] = cast.get('z2_pal_pairs', Z2_PALETTE_PAIRS)           # type: ignore[assignment]
    z2_pal_slots: list[int] = cast.get('z2_pal_slots', Z2_CHAR_PAL_SLOTS)                      # type: ignore[assignment]
    assert 5 <= barba_count <= 16, f'barba_count must be 5..16, got {barba_count}'
    assert 5 <= z2_count <= 64, f'z2_count must be 5..64, got {z2_count}'
    name_offs, name_blob = _encode_names_blob()

    a = FeudAsm(BANK4_CODE_ORG)

    # Dispatch jump table at $8700 (entries 0, 3, 6, 9, 12, 15, 18)
    for tgt in (
        'B4_BOOT_COPY_CHRRAM',
        'B4_ROLL_BOTH',
        'B4_ROLL_P1',
        'B4_ROLL_CPU',
        'B4_LOAD_FACEOFF',
        'B4_PICK_Z2_NAME',
        'B4_ZELDA_LOSE',
    ):
        a.emit(0x4C); a.ref16(tgt)

    # ---- Static Data Tables ----
    a.label('TBL_BARBA_BANK'); a.emit(*(bk for bk, _ in barba_meta))
    a.label('TBL_BARBA_LO');   a.emit(*(ad & 0xFF for _, ad in barba_meta))
    a.label('TBL_BARBA_HI');   a.emit(*(ad >> 8 for _, ad in barba_meta))
    a.label('TBL_Z2_BANK');    a.emit(*(bk for bk, _ in z2_meta))
    a.label('TBL_Z2_LO');      a.emit(*(ad & 0xFF for _, ad in z2_meta))
    a.label('TBL_Z2_HI');      a.emit(*(ad >> 8 for _, ad in z2_meta))

    a.label('TBL_OV_FREE');     a.emit(*ov_free)
    a.label('TBL_ST_P1_FREE');  a.emit(*st_p1_free)
    a.label('TBL_ST_CPU_FREE'); a.emit(*st_cpu_free)
    a.label('TBL_FO_P1_FREE');  a.emit(*fo_p1_free)
    a.label('TBL_FO_CPU_FREE'); a.emit(*fo_cpu_free)
    a.label('TBL_FO_CPU_LIP_IDS'); a.emit(*fo_cpu_lip_ids)
    a.label('TBL_FO_CPU_LIP_TILES'); a.emit(*fo_cpu_lip_tiles)
    a.label('TBL_FO_P1_BOT2');  a.emit(*fo_p1_bot2)
    a.label('TBL_FO_CPU_BOT2'); a.emit(*fo_cpu_bot2)

    a.label('TBL_BARBA_C1'); a.emit(*(c1 for c1, _ in barba_pal_pairs))
    a.label('TBL_BARBA_C2'); a.emit(*(c2 for _, c2 in barba_pal_pairs))
    a.label('TBL_Z2_C1');    a.emit(*(c1 for c1, _ in z2_pal_pairs))
    a.label('TBL_Z2_C2');    a.emit(*(c2 for _, c2 in z2_pal_pairs))
    a.label('TBL_Z2_CHAR_PAL');    a.emit(*z2_pal_slots)
    a.label('TBL_BARBA_ALT_PATS'); a.emit(*BARBA_ALT_PATS)

    a.label('TBL_NAME_OFF'); a.emit(*name_offs)
    a.label('TBL_NAMES');    a.emit(*name_blob)

    for idx, msg in enumerate(LOSE_REASONS):
        a.label(f'LOSE_STR_{idx}'); a.emit(*_encode_chr0b_blue(msg))
    a.label('TBL_LOSE_LEN'); a.emit(*(len(m) for m in LOSE_REASONS))
    a.label('TBL_LOSE_PAD'); a.emit(*((28 - len(m)) // 2 for m in LOSE_REASONS))
    a.label('TBL_LOSE_LO')
    for idx in range(len(LOSE_REASONS)): a.ref_lo(f'LOSE_STR_{idx}')
    a.label('TBL_LOSE_HI')
    for idx in range(len(LOSE_REASONS)): a.ref_hi(f'LOSE_STR_{idx}')
    a.label('TBL_BLUE_THE');    a.emit(*_encode_chr0b_blue('the '))
    a.label('TBL_BLUE_FAMILY'); a.emit(*_encode_chr0b_blue(' family'))

    a.label('TBL_INIT_ROM_BANKS'); a.emit(0x00, 0x0B, 0x02, 0x03, 0x05, 0x06, 0x0C, 0x09)
    a.label('TBL_ST_POSE_MAP');    a.emit(0, 1, 0, 0, 2)
    # Stage Close-Up block seat bases (0,5,10,15,20 for P1; +25 for CPU)
    # Seat display order left-to-right on P1 (X=6,10,14,18,22): seats [4,2,3,1,0]
    # Seat display order left-to-right on CPU (X=6,10,14,18,22): seats [0,1,3,2,4]
    a.label('TBL_P1_LR_SEAT');  a.emit(4, 2, 3, 1, 0)
    a.label('TBL_CPU_LR_SEAT'); a.emit(0, 1, 3, 2, 4)

    # ---- Helpers ----
    a.label('B4_SAVE_ZP')
    a.emit(0xA5, 0x0E); a.op16(0x8D, W_SAVE_0E)
    a.emit(0xA5, 0x0F); a.op16(0x8D, W_SAVE_0F)
    a.emit(0xA5, 0x11); a.op16(0x8D, W_SAVE_11)
    a.emit(0xA5, 0x12); a.op16(0x8D, W_SAVE_12)
    a.emit(0x60)

    a.label('B4_RESTORE_ZP')
    a.op16(0xAD, W_SAVE_0E); a.emit(0x85, 0x0E)
    a.op16(0xAD, W_SAVE_0F); a.emit(0x85, 0x0F)
    a.op16(0xAD, W_SAVE_11); a.emit(0x85, 0x11)
    a.op16(0xAD, W_SAVE_12); a.emit(0x85, 0x12)
    a.emit(0x60)

    # B4_MAP_CHR0_P0: A=4KB bank, X=$01 (ROM) or $21 (RAM) -> R0/R1 + $5FF0
    a.label('B4_MAP_CHR0_P0')
    a.emit(0x8E, 0xF0, 0x5F)
    a.emit(0x0A, 0x0A, 0xAA)
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80)
    a.emit(0xE8, 0xE8)
    a.emit(0xA9, 0x01, 0x8D, 0x00, 0x80, 0x8E, 0x01, 0x80)
    a.emit(0x60)

    # B4_SET_PPU_TILE: A = tile ID -> PPUADDR = $0000 + A*16
    a.label('B4_SET_PPU_TILE')
    a.emit(0x48, 0x4A, 0x4A, 0x4A, 0x4A, 0x8D, 0x06, 0x20)
    a.emit(0x68, 0x0A, 0x0A, 0x0A, 0x0A, 0x8D, 0x06, 0x20)
    a.emit(0x60)

    # B4_LOAD_VAR_PTR: given W_SIDE_ARG (0=Barba,1=Z2), W_TMP0=char, W_TMP1=height(0..2)
    # idx = char*3 + height; sets R7 = bank and $0E/$0F = addr; reads 4-byte header into W_ST_CNT..W_FO_CNT
    a.label('B4_LOAD_VAR_PTR')
    a.op16(0xAD, W_TMP0)
    a.emit(0x0A, 0x18)
    a.op16(0x6D, W_TMP0)  # char*3
    a.emit(0x18)
    a.op16(0x6D, W_TMP1)  # + height
    a.emit(0xAA)
    a.op16(0xAD, W_SIDE_ARG)
    a.branch(0xD0, 'lvp_z2')
    a.abs_ref(0xBD, 'TBL_BARBA_BANK'); a.op16(0x8D, W_VAR_BANK)
    a.abs_ref(0xBD, 'TBL_BARBA_LO');   a.emit(0x85, 0x0E)
    a.abs_ref(0xBD, 'TBL_BARBA_HI');   a.emit(0x85, 0x0F)
    a.abs_ref(0x4C, 'lvp_map')
    a.label('lvp_z2')
    a.abs_ref(0xBD, 'TBL_Z2_BANK'); a.op16(0x8D, W_VAR_BANK)
    a.abs_ref(0xBD, 'TBL_Z2_LO');   a.emit(0x85, 0x0E)
    a.abs_ref(0xBD, 'TBL_Z2_HI');   a.emit(0x85, 0x0F)
    a.label('lvp_map')
    a.emit(0xA9, 0x07, 0x8D, 0x00, 0x80)
    a.op16(0xAD, W_VAR_BANK)
    a.emit(0x8D, 0x01, 0x80)
    a.emit(0xA0, 0x00, 0xB1, 0x0E); a.op16(0x8D, W_ST_CNT)
    a.emit(0xC8, 0xB1, 0x0E);       a.op16(0x8D, W_OV_CNT)
    a.emit(0xC8, 0xC8, 0xB1, 0x0E); a.op16(0x8D, W_FO_CNT)
    a.emit(0xA9, 0x04)
    a.abs_ref(0x4C, 'B4_ADV_0E')

    a.label('B4_ADV_0E')
    a.emit(0x18, 0x65, 0x0E, 0x85, 0x0E)
    a.branch(0x90, 'adv0_ok')
    a.emit(0xE6, 0x0F)
    a.label('adv0_ok')
    a.emit(0x60)

    a.label('B4_ADV_0E_X16')
    a.emit(0x48, 0x0A, 0x0A, 0x0A, 0x0A, 0x18, 0x65, 0x0E, 0x85, 0x0E)
    a.branch(0x90, 'advx_hi')
    a.emit(0xE6, 0x0F)
    a.label('advx_hi')
    a.emit(0x68, 0x4A, 0x4A, 0x4A, 0x4A, 0x18, 0x65, 0x0F, 0x85, 0x0F)
    a.emit(0x60)

    # Stream W_COPY_CNT tiles from ($0E/$0F) to $2007 (auto-advances $0E/$0F)
    a.label('B4_STREAM_TILES')
    a.op16(0xAD, W_COPY_CNT)
    a.branch(0xF0, 'bst_done')
    a.label('bst_tile')
    a.emit(0xA0, 0x00)
    a.label('bst_byte')
    a.emit(0xB1, 0x0E, 0x8D, 0x07, 0x20, 0xC8, 0xC0, 0x10)
    a.branch(0xD0, 'bst_byte')
    a.emit(0xA9, 0x10); a.abs_ref(0x20, 'B4_ADV_0E')
    a.op16(0xCE, W_COPY_CNT)
    a.branch(0xD0, 'bst_tile')
    a.label('bst_done')
    a.emit(0x60)

    # Stream W_COPY_CNT tiles to individual free tile IDs using free table at ($11/$12)
    # W_TMP2 = start index into ($11/$12)
    a.label('B4_STREAM_FREE_TILES')
    a.op16(0xAD, W_COPY_CNT)
    a.branch(0xF0, 'bsft_done')
    a.label('bsft_tile')
    a.op16(0xAC, W_TMP2)
    a.emit(0xB1, 0x11)
    a.abs_ref(0x20, 'B4_SET_PPU_TILE')
    a.op16(0xEE, W_TMP2)
    a.emit(0xA0, 0x00)
    a.label('bsft_byte')
    a.emit(0xB1, 0x0E, 0x8D, 0x07, 0x20, 0xC8, 0xC0, 0x10)
    a.branch(0xD0, 'bsft_byte')
    a.emit(0xA9, 0x10); a.abs_ref(0x20, 'B4_ADV_0E')
    a.op16(0xCE, W_COPY_CNT)
    a.branch(0xD0, 'bsft_tile')
    a.label('bsft_done')
    a.emit(0x60)

    # ---- B4_BOOT_COPY_CHRRAM ----
    a.label('B4_BOOT_COPY_CHRRAM')
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20, 0x2C, 0x02, 0x20)
    a.emit(0xAA)
    a.label('boot_clr')
    for pg in range(0x60, 0x6E):
        a.emit(0x9D, 0x00, pg)
    a.emit(0xE8)
    a.branch(0xD0, 'boot_clr')
    a.emit(0xA9, 0xFF); a.op16(0x8D, W_IDLE_SEAT)
    a.emit(0xA9, 0x48); a.op16(0x8D, W_IDLE_TIMER)
    a.emit(0xA9, 120);  a.op16(0x8D, W_AMB_TMR_LO)
    a.emit(0xA9, 0x40, 0x8D, 0x11, 0x40)  # settle DMC DAC midpoint once at boot
    a.emit(0xA9, 0x07); a.op16(0x8D, W_FO_OAM_ATTR)
    a.emit(0xA9, 0x0C); a.op16(0x8D, W_FO_OAM_ATTR + 1)
    a.emit(0xA2, 83, 0xA9, 0x01)
    a.label('boot_fo_a')
    a.op16(0x9D, W_FO_OAM_ATTR + 2)
    a.emit(0xCA); a.branch(0x10, 'boot_fo_a')
    a.emit(0xA2, 0x00)
    a.label('boot_fast_pal')
    a.abs_ref(0xBD, 'TBL_FAST_PAL'); a.op16(0x9D, W_FAST_PAL)
    a.emit(0xE8); a.branch(0xD0, 'boot_fast_pal')

    a.emit(0xA9, 0x00); a.op16(0x8D, W_TMP0)  # slot = 0..7
    a.label('boot_slot_loop')
    a.emit(0xA9, 0x00); a.op16(0x8D, W_TMP1)  # page = 0..15
    a.label('boot_page_loop')
    a.op16(0xAE, W_TMP0)
    a.abs_ref(0xBD, 'TBL_INIT_ROM_BANKS')
    a.emit(0xA2, 0x01); a.abs_ref(0x20, 'B4_MAP_CHR0_P0')
    a.op16(0xAD, W_TMP1)
    a.emit(0x8D, 0x06, 0x20, 0xA9, 0x00, 0x8D, 0x06, 0x20)
    a.emit(0xAD, 0x07, 0x20)  # dummy read
    a.emit(0xA2, 0x00)
    a.label('boot_rd')
    a.emit(0xAD, 0x07, 0x20); a.op16(0x9D, W_CHRRAM_BUF)
    a.emit(0xE8); a.branch(0xD0, 'boot_rd')
    a.op16(0xAD, W_TMP0)
    a.emit(0xA2, 0x21); a.abs_ref(0x20, 'B4_MAP_CHR0_P0')
    a.op16(0xAD, W_TMP1)
    a.emit(0x8D, 0x06, 0x20, 0xA9, 0x00, 0x8D, 0x06, 0x20)
    a.emit(0xA2, 0x00)
    a.label('boot_wr')
    a.op16(0xBD, W_CHRRAM_BUF); a.emit(0x8D, 0x07, 0x20)
    a.emit(0xE8); a.branch(0xD0, 'boot_wr')
    a.op16(0xEE, W_TMP1)
    a.op16(0xAD, W_TMP1)
    a.emit(0xC9, 0x10)
    a.branch(0xF0, 'boot_next_slot')
    a.abs_ref(0x4C, 'boot_page_loop')
    a.label('boot_next_slot')
    a.op16(0xEE, W_TMP0)
    a.op16(0xAD, W_TMP0)
    a.emit(0xC9, 0x08)
    a.branch(0xF0, 'boot_done')
    a.abs_ref(0x4C, 'boot_slot_loop')
    a.label('boot_done')
    a.emit(0x60)

    # ---- Helper: B4_RNG (Bank 4 safe clone of $9BBB) ----
    a.label('B4_RNG')
    a.emit(0xAD, 0xFC, 0x01, 0x29, 0x80, 0x4A, 0x4D, 0xFC, 0x01)
    a.emit(0x2A, 0x2A, 0x2E, 0xFA, 0x01, 0x2E, 0xFB, 0x01, 0x2E, 0xFC, 0x01, 0x60)

    # ---- Helper: B4_RAND_MOD_A (picks 0..A-1 in A using B4_RNG) ----
    # Uses $11 as limit, mixes $01FA with $1E+$1F to guarantee decorrelation
    a.label('B4_RAND_MOD')
    a.emit(0x85, 0x11)
    a.label('rmod_retry')
    a.abs_ref(0x20, 'B4_RNG')
    a.emit(0xAD, 0xFA, 0x01, 0x45, 0x1F, 0x29, 0x3F, 0xC5, 0x11)
    a.branch(0xB0, 'rmod_retry')
    a.emit(0x60)

    # ---- B4_ROLL_BOTH / B4_ROLL_P1 / B4_ROLL_CPU ----
    a.label('B4_ROLL_BOTH')
    a.emit(0xA9, 0x00, 0x8D, 0x15, 0x03, 0xA9, 0x01, 0x8D, 0x16, 0x03)
    a.emit(0xA9, 0xA0, 0x8D, 0x00, 0x03, 0x8D, 0x08, 0x03)
    a.abs_ref(0x20, 'B4_SAVE_ZP')
    a.emit(0xA9, 0x00); a.abs_ref(0x20, 'B4_ROLL_SIDE')
    a.emit(0xA9, 0x01); a.abs_ref(0x20, 'B4_ROLL_SIDE')
    a.emit(0xA9, 0x5A); a.op16(0x8D, W_ROLLED_MAGIC)
    a.abs_ref(0x4C, 'B4_RESTORE_ZP')

    a.label('B4_ROLL_P1')
    a.emit(0xA9, 0x00, 0x8D, 0x15, 0x03)
    a.abs_ref(0x20, 'B4_SAVE_ZP')
    a.emit(0xA9, 0x00); a.abs_ref(0x20, 'B4_ROLL_SIDE')
    a.abs_ref(0x4C, 'B4_RESTORE_ZP')

    a.label('B4_ROLL_CPU')
    a.emit(0xA9, 0x01, 0x8D, 0x16, 0x03)
    a.abs_ref(0x20, 'B4_SAVE_ZP')
    a.emit(0xA9, 0x01); a.abs_ref(0x20, 'B4_ROLL_SIDE')
    a.abs_ref(0x4C, 'B4_RESTORE_ZP')

    # ---- B4_ROLL_SIDE (A = 0 P1 / 1 CPU) ----
    a.label('B4_ROLL_SIDE')
    a.op16(0x8D, W_SIDE_ARG)

    # 1. Pick 5 unique characters + 5 random heights + 5 random pal slots (1..3)
    a.emit(0xA9, 0x00); a.op16(0x8D, W_SEAT_IDX)
    a.label('rs_pick_loop')
    a.label('rs_pick_char')
    a.emit(0xA9, barba_count)
    a.op16(0xAC, W_SIDE_ARG)
    a.branch(0xF0, 'rs_lim_ok')
    a.emit(0xA9, z2_count)
    a.label('rs_lim_ok')
    a.abs_ref(0x20, 'B4_RAND_MOD')
    # Check uniqueness against earlier seats 0..W_SEAT_IDX-1
    a.op16(0xAC, W_SEAT_IDX)
    a.branch(0xF0, 'rs_char_ok')
    a.emit(0x85, 0x12)  # candidate
    a.op16(0xAD, W_SIDE_ARG)
    a.branch(0xD0, 'rs_chk_z2')
    a.label('rs_chk_p1')
    a.emit(0x88)
    a.op16(0xB9, W_P1_CHAR)
    a.emit(0xC5, 0x12)
    a.branch(0xF0, 'rs_pick_char')
    a.emit(0x98); a.branch(0xD0, 'rs_chk_p1')
    a.emit(0xA5, 0x12); a.abs_ref(0x4C, 'rs_char_ok')
    a.label('rs_chk_z2')
    a.emit(0x88)
    a.op16(0xB9, W_CPU_CHAR)
    a.emit(0xC5, 0x12)
    a.branch(0xF0, 'rs_pick_char')
    a.emit(0x98); a.branch(0xD0, 'rs_chk_z2')
    a.emit(0xA5, 0x12)
    a.label('rs_char_ok')
    a.op16(0xAE, W_SEAT_IDX)
    a.op16(0xAC, W_SIDE_ARG)
    a.branch(0xD0, 'rs_st_z2c')
    a.op16(0x9D, W_P1_CHAR); a.abs_ref(0x4C, 'rs_pick_h')
    a.label('rs_st_z2c')
    a.op16(0x9D, W_CPU_CHAR)

    a.label('rs_pick_h')
    a.emit(0xA9, 0x03); a.abs_ref(0x20, 'B4_RAND_MOD')
    a.op16(0xAE, W_SEAT_IDX)
    a.op16(0xAC, W_SIDE_ARG)
    a.branch(0xD0, 'rs_st_z2h')
    a.op16(0x9D, W_P1_HEIGHT); a.abs_ref(0x4C, 'rs_pick_p')
    a.label('rs_st_z2h')
    a.op16(0x9D, W_CPU_HEIGHT)

    a.label('rs_pick_p')
    a.op16(0xAC, W_SIDE_ARG)
    a.branch(0xF0, 'rs_next_pick')  # P1 palette pattern assigned cleanly after loop
    a.op16(0xAE, W_SEAT_IDX)
    a.op16(0xBC, W_CPU_CHAR)
    a.abs_ref(0xB9, 'TBL_Z2_CHAR_PAL')
    a.op16(0x9D, W_CPU_PAL_IDX)
    a.label('rs_next_pick')
    a.op16(0xEE, W_SEAT_IDX)
    a.op16(0xAD, W_SEAT_IDX)
    a.emit(0xC9, 0x05)
    a.branch(0xF0, 'rs_picks_done')
    a.abs_ref(0x4C, 'rs_pick_loop')
    a.label('rs_picks_done')

    # For Barba (side==0), pick 1 of 8 alternating seat patterns (zero adjacent duplicates)
    a.op16(0xAD, W_SIDE_ARG)
    a.branch(0xD0, 'rp_roll_colors')
    a.emit(0xA9, 0x08); a.abs_ref(0x20, 'B4_RAND_MOD')
    a.op16(0x8D, W_TMP0)
    a.emit(0x0A, 0x0A, 0x18); a.op16(0x6D, W_TMP0); a.emit(0xA8)  # Y = pat * 5
    a.emit(0xA2, 0x00)
    a.label('rp_alt_cp')
    a.abs_ref(0xB9, 'TBL_BARBA_ALT_PATS'); a.op16(0x9D, W_P1_PAL_IDX)
    a.emit(0xC8, 0xE8, 0xE0, 0x05); a.branch(0xD0, 'rp_alt_cp')

    # 2. Pick 1 of 4 curated variations for each of the 3 palette slots (0..2)
    a.label('rp_roll_colors')
    a.emit(0xA9, 0x00); a.op16(0x8D, W_TMP3)
    a.label('rp_slot_lp')
    a.emit(0xA9, 0x04); a.abs_ref(0x20, 'B4_RAND_MOD')
    a.op16(0x8D, W_TMP0)
    a.op16(0xAD, W_TMP3); a.emit(0x0A, 0x0A, 0x18); a.op16(0x6D, W_TMP0); a.emit(0xA8)  # Y = slot*4 + var
    a.op16(0xAD, W_TMP3); a.emit(0x0A, 0xAA)  # X = slot*2
    a.op16(0xAD, W_SIDE_ARG)
    a.branch(0xD0, 'rp_z2_tbl')
    a.abs_ref(0xB9, 'TBL_BARBA_C1'); a.op16(0x9D, W_P1_PAL_CLR)
    a.abs_ref(0xB9, 'TBL_BARBA_C2'); a.op16(0x9D, W_P1_PAL_CLR + 1)
    a.abs_ref(0x4C, 'rp_next')
    a.label('rp_z2_tbl')
    a.abs_ref(0xB9, 'TBL_Z2_C1'); a.op16(0x9D, W_CPU_PAL_CLR)
    a.abs_ref(0xB9, 'TBL_Z2_C2'); a.op16(0x9D, W_CPU_PAL_CLR + 1)
    a.label('rp_next')
    a.op16(0xEE, W_TMP3); a.op16(0xAD, W_TMP3); a.emit(0xC9, 0x03)
    a.branch(0xD0, 'rp_slot_lp')

    # 3. Compute Stage Close-Up 14 attr bytes + Overview 3 attr bytes for this side
    a.abs_ref(0x20, 'B4_BUILD_ATTRS')

    # 4. Upload Stage Close-Up & Overview tiles & build WRAM blocks for seats 0..4
    a.emit(0xA9, 0x00); a.op16(0x8D, W_SEAT_IDX); a.op16(0x8D, W_ST_FREE_IDX)
    a.op16(0xAD, W_SIDE_ARG)
    a.emit(0xF0, 0x04, 0xA9, 0x3C, 0xD0, 0x02, 0xA9, 0x00)  # ov_free offset = 0 (P1) or 60 (CPU)
    a.op16(0x8D, W_OV_FREE_IDX)

    a.label('rs_upload_seat')
    a.op16(0xAE, W_SEAT_IDX)
    a.op16(0xAD, W_SIDE_ARG)
    a.branch(0xD0, 'ru_z2')
    a.op16(0xBD, W_P1_CHAR);   a.op16(0x8D, W_TMP0)
    a.op16(0xBD, W_P1_HEIGHT); a.op16(0x8D, W_TMP1)
    a.abs_ref(0x4C, 'ru_load')
    a.label('ru_z2')
    a.op16(0xBD, W_CPU_CHAR);   a.op16(0x8D, W_TMP0)
    a.op16(0xBD, W_CPU_HEIGHT); a.op16(0x8D, W_TMP1)
    a.label('ru_load')
    a.abs_ref(0x20, 'B4_LOAD_VAR_PTR')

    # --- 4a. Upload Stage Close-Up tiles into CHR-RAM 4 (P1) or CHR-RAM 5 (CPU) via free tables ---
    a.op16(0xAD, W_ST_FREE_IDX); a.op16(0x8D, W_TILE_BASE); a.op16(0x8D, W_TMP2)
    a.op16(0xAD, W_SIDE_ARG)
    a.branch(0xD0, 'ru_st_cpu_tbl')
    a.lda_lo('TBL_ST_P1_FREE'); a.emit(0x85, 0x11)
    a.lda_hi('TBL_ST_P1_FREE'); a.emit(0x85, 0x12)
    a.abs_ref(0x4C, 'ru_st_go')
    a.label('ru_st_cpu_tbl')
    a.lda_lo('TBL_ST_CPU_FREE'); a.emit(0x85, 0x11)
    a.lda_hi('TBL_ST_CPU_FREE'); a.emit(0x85, 0x12)
    a.label('ru_st_go')
    a.emit(0xA9, 0x04); a.emit(0x18); a.op16(0x6D, W_SIDE_ARG)  # RAM bank 4 or 5
    a.emit(0xA2, 0x21); a.abs_ref(0x20, 'B4_MAP_CHR0_P0')
    a.op16(0xAD, W_ST_CNT); a.op16(0x8D, W_COPY_CNT)
    a.abs_ref(0x20, 'B4_STREAM_FREE_TILES')
    a.op16(0xAD, W_TMP2); a.op16(0x8D, W_ST_FREE_IDX)

    # --- 4b. Build 3 Stage Close-Up 4x6 blocks (frames 0,1,2) in W_STAGE_BLKS ---
    # ($0E/$0F) now points at stage_maps (3 * 24 bytes)!
    # dst ptr ($11/$12) = W_STAGE_BLKS + (side*5 + seat)*78
    a.emit(0xA9); a.emit(W_STAGE_BLKS & 0xFF); a.emit(0x85, 0x11)
    a.emit(0xA9); a.emit(W_STAGE_BLKS >> 8);   a.emit(0x85, 0x12)
    a.op16(0xAD, W_SIDE_ARG)
    a.branch(0xF0, 'sb_add_seat')
    # + 5 * 78 = +390 ($0186)
    a.emit(0x18, 0xA5, 0x11, 0x69, 0x86, 0x85, 0x11, 0xA5, 0x12, 0x69, 0x01, 0x85, 0x12)
    a.label('sb_add_seat')
    a.op16(0xAE, W_SEAT_IDX)
    a.label('sb_s_lp')
    a.branch(0xF0, 'sb_ptr_ok')
    a.emit(0x18, 0xA5, 0x11, 0x69, 0x4E, 0x85, 0x11)
    a.branch(0x90, 'sb_s_nc')
    a.emit(0xE6, 0x12)
    a.label('sb_s_nc')
    a.emit(0xCA); a.abs_ref(0x4C, 'sb_s_lp')
    a.label('sb_ptr_ok')
    # Save base ptr of frame 0 into W_BLK_PTR_LO/HI (frames 1,2 are at +26, +52)
    a.emit(0xA5, 0x11); a.op16(0x8D, W_BLK_PTR_LO)
    a.emit(0xA5, 0x12); a.op16(0x8D, W_BLK_PTR_HI)
    a.emit(0xA9, 0x00); a.op16(0x8D, W_COPY_CNT)  # frame = 0..2
    a.label('sb_frm_lp')
    a.emit(0xA0, 0x00, 0xA9, 0x04, 0x91, 0x11, 0xC8, 0xA9, 0x06, 0x91, 0x11)
    a.emit(0xA0, 0x00)
    a.label('sb_tile_lp')
    a.emit(0xB1, 0x0E)
    a.branch(0xF0, 'sb_tile_z')
    a.emit(0x38, 0xE9, 0x01, 0x18); a.op16(0x6D, W_TILE_BASE)
    a.emit(0xAA)
    a.op16(0xAD, W_SIDE_ARG)
    a.branch(0xD0, 'sb_tile_cpu')
    a.abs_ref(0xBD, 'TBL_ST_P1_FREE')
    a.abs_ref(0x4C, 'sb_tile_z')
    a.label('sb_tile_cpu')
    a.abs_ref(0xBD, 'TBL_ST_CPU_FREE')
    a.label('sb_tile_z')
    a.emit(0xC8, 0xC8, 0x91, 0x11, 0x88, 0xC0, 0x18)
    a.branch(0xD0, 'sb_tile_lp')
    a.emit(0xA9, 0x18); a.abs_ref(0x20, 'B4_ADV_0E')
    a.emit(0x18, 0xA5, 0x11, 0x69, 0x1A, 0x85, 0x11)
    a.branch(0x90, 'sb_no_c')
    a.emit(0xE6, 0x12)
    a.label('sb_no_c')
    a.op16(0xEE, W_COPY_CNT); a.op16(0xAD, W_COPY_CNT)
    a.emit(0xC9, 0x03)
    a.branch(0xD0, 'sb_frm_lp')

    # Register blocks blk_base + 0..4 -> [f0, f1, f0, f1, f2]
    a.op16(0xAD, W_SEAT_IDX); a.emit(0x0A, 0x0A, 0x18); a.op16(0x6D, W_SEAT_IDX)
    a.op16(0xAC, W_SIDE_ARG)
    a.branch(0xF0, 'sb_reg_init')
    a.emit(0x18, 0x69, 0x19)
    a.label('sb_reg_init')
    a.emit(0xAA, 0xA0, 0x00)
    a.label('sb_reg_lp')
    a.abs_ref(0xB9, 'TBL_ST_POSE_MAP')
    a.emit(0x48)
    a.op16(0xAD, W_BLK_PTR_LO); a.op16(0x9D, W_BLK_T_LO)
    a.op16(0xAD, W_BLK_PTR_HI); a.op16(0x9D, W_BLK_T_HI)
    a.emit(0x68)
    a.branch(0xF0, 'sb_reg_done_ptr')
    a.label('sb_add26_lp')
    a.emit(0x48, 0x18)
    a.op16(0xBD, W_BLK_T_LO); a.emit(0x69, 0x1A); a.op16(0x9D, W_BLK_T_LO)
    a.branch(0x90, 'sb_a26_nc')
    a.op16(0xFE, W_BLK_T_HI)
    a.label('sb_a26_nc')
    a.emit(0x68, 0x38, 0xE9, 0x01)
    a.branch(0xD0, 'sb_add26_lp')
    a.label('sb_reg_done_ptr')
    a.emit(0xBD, 0x18, 0xF2); a.op16(0x9D, W_BLK_A_LO)
    a.emit(0xBD, 0xE5, 0xF2); a.op16(0x9D, W_BLK_A_HI)
    a.emit(0xA9, 0x01); a.op16(0x9D, W_BLK_DYN)
    a.emit(0xE8, 0xC8, 0xC0, 0x05)
    a.branch(0xD0, 'sb_reg_lp')

    # --- 4c. Upload Overview tiles to CHR-RAM 0 using ov_free[W_OV_FREE_IDX..] ---
    a.op16(0xAD, W_OV_FREE_IDX); a.op16(0x8D, W_TILE_BASE); a.op16(0x8D, W_TMP2)
    a.lda_lo('TBL_OV_FREE'); a.emit(0x85, 0x11)
    a.lda_hi('TBL_OV_FREE'); a.emit(0x85, 0x12)
    a.emit(0xA9, 0x00, 0xA2, 0x21); a.abs_ref(0x20, 'B4_MAP_CHR0_P0')
    a.op16(0xAD, W_OV_CNT); a.op16(0x8D, W_COPY_CNT)
    a.abs_ref(0x20, 'B4_STREAM_FREE_TILES')
    a.op16(0xAD, W_TMP2); a.op16(0x8D, W_OV_FREE_IDX)

    # --- 4d. Build 2 Overview 2x4 blocks (idle, roar) in W_OV_BLKS + (side*5 + seat)*20 ---
    a.emit(0xA9, W_OV_BLKS & 0xFF, 0x85, 0x11, 0xA9, W_OV_BLKS >> 8, 0x85, 0x12)
    a.op16(0xAD, W_SIDE_ARG)
    a.branch(0xF0, 'ob_add_seat')
    a.emit(0x18, 0xA5, 0x11, 0x69, 0x64, 0x85, 0x11)
    a.branch(0x90, 'ob_add_seat')
    a.emit(0xE6, 0x12)
    a.label('ob_add_seat')
    a.op16(0xAE, W_SEAT_IDX)
    a.label('ob_s_lp')
    a.branch(0xF0, 'ob_ptr_ok')
    a.emit(0x18, 0xA5, 0x11, 0x69, 0x14, 0x85, 0x11)
    a.branch(0x90, 'ob_s_nc')
    a.emit(0xE6, 0x12)
    a.label('ob_s_nc')
    a.emit(0xCA); a.abs_ref(0x4C, 'ob_s_lp')
    a.label('ob_ptr_ok')
    a.emit(0xA5, 0x11); a.op16(0x8D, W_BLK_PTR_LO)
    a.emit(0xA5, 0x12); a.op16(0x8D, W_BLK_PTR_HI)
    a.emit(0xA9, 0x00); a.op16(0x8D, W_COPY_CNT)
    a.label('ob_frm_lp')
    a.emit(0xA0, 0x00, 0xA9, 0x02, 0x91, 0x11, 0xC8, 0xA9, 0x04, 0x91, 0x11)
    a.emit(0xA0, 0x00)
    a.label('ob_tile_lp')
    a.emit(0xB1, 0x0E)
    a.branch(0xF0, 'ob_tile_z')
    a.emit(0x38, 0xE9, 0x01, 0x18); a.op16(0x6D, W_TILE_BASE)
    a.emit(0xAA); a.abs_ref(0xBD, 'TBL_OV_FREE')
    a.label('ob_tile_z')
    a.emit(0xC8, 0xC8, 0x91, 0x11, 0x88, 0xC0, 0x08)
    a.branch(0xD0, 'ob_tile_lp')
    a.emit(0xA9, 0x08); a.abs_ref(0x20, 'B4_ADV_0E')
    a.emit(0x18, 0xA5, 0x11, 0x69, 0x0A, 0x85, 0x11)
    a.branch(0x90, 'ob_no_c')
    a.emit(0xE6, 0x12)
    a.label('ob_no_c')
    a.op16(0xEE, W_COPY_CNT); a.op16(0xAD, W_COPY_CNT)
    a.emit(0xC9, 0x02)
    a.branch(0xD0, 'ob_frm_lp')

    a.op16(0xAD, W_SIDE_ARG)
    a.branch(0xD0, 'ob_reg_cpu')
    a.emit(0x18); a.op16(0xAD, W_SEAT_IDX); a.emit(0x69, 143, 0xAA); a.abs_ref(0x20, 'B4_REG_OV_IDLE')
    a.emit(0x18); a.op16(0xAD, W_SEAT_IDX); a.emit(0x69, 123, 0xAA); a.abs_ref(0x20, 'B4_REG_OV_IDLE')
    a.emit(0x18); a.op16(0xAD, W_SEAT_IDX); a.emit(0x69, 128, 0xAA); a.abs_ref(0x20, 'B4_REG_OV_ROAR')
    a.abs_ref(0x4C, 'rs_next_seat')
    a.label('ob_reg_cpu')
    a.emit(0xA9, 152, 0x38); a.op16(0xED, W_SEAT_IDX); a.emit(0xAA); a.abs_ref(0x20, 'B4_REG_OV_IDLE')
    a.emit(0x18); a.op16(0xAD, W_SEAT_IDX); a.emit(0x69, 133, 0xAA); a.abs_ref(0x20, 'B4_REG_OV_IDLE')
    a.emit(0x18); a.op16(0xAD, W_SEAT_IDX); a.emit(0x69, 138, 0xAA); a.abs_ref(0x20, 'B4_REG_OV_ROAR')

    a.label('rs_next_seat')
    a.op16(0xEE, W_SEAT_IDX); a.op16(0xAD, W_SEAT_IDX)
    a.emit(0xC9, 0x05)
    a.branch(0xF0, 'rs_all_done')
    a.abs_ref(0x4C, 'rs_upload_seat')
    a.label('rs_all_done')
    a.emit(0x60)

    a.label('B4_REG_OV_IDLE')
    a.op16(0xAD, W_BLK_PTR_LO); a.op16(0x9D, W_BLK_T_LO)
    a.op16(0xAD, W_BLK_PTR_HI); a.op16(0x9D, W_BLK_T_HI)
    a.emit(0xBD, 0x18, 0xF2);   a.op16(0x9D, W_BLK_A_LO)
    a.emit(0xBD, 0xE5, 0xF2);   a.op16(0x9D, W_BLK_A_HI)
    a.emit(0xA9, 0x01);         a.op16(0x9D, W_BLK_DYN)
    a.emit(0x60)

    a.label('B4_REG_OV_ROAR')
    a.emit(0x18); a.op16(0xAD, W_BLK_PTR_LO); a.emit(0x69, 0x0A); a.op16(0x9D, W_BLK_T_LO)
    a.op16(0xAD, W_BLK_PTR_HI); a.emit(0x69, 0x00); a.op16(0x9D, W_BLK_T_HI)
    a.emit(0xBD, 0x18, 0xF2);   a.op16(0x9D, W_BLK_A_LO)
    a.emit(0xBD, 0xE5, 0xF2);   a.op16(0x9D, W_BLK_A_HI)
    a.emit(0xA9, 0x01);         a.op16(0x9D, W_BLK_DYN)
    a.emit(0x60)

    # ---- B4_BUILD_ATTRS ----
    a.label('B4_BUILD_ATTRS')
    a.op16(0xAD, W_SIDE_ARG)
    a.branch(0xD0, 'ba_cpu')
    a.emit(0xA2, 0x00)
    a.label('ba_p1_cp')
    a.abs_ref(0xBC, 'TBL_P1_LR_SEAT')
    a.op16(0xB9, W_P1_PAL_IDX); a.op16(0x9D, W_CHRRAM_BUF)
    a.emit(0xE8, 0xE0, 0x05); a.branch(0xD0, 'ba_p1_cp')
    a.emit(0xA0, 0x00); a.abs_ref(0x20, 'ba_emit_stage')
    # Overview P1 ($23E0..$23E2): cols 2..11 -> seats [none/4], [3/2], [1/0]
    a.op16(0xAD, W_P1_PAL_IDX + 4); a.emit(0x0A, 0x0A, 0x85, 0x11, 0x0A, 0x0A, 0x0A, 0x0A, 0x05, 0x11)
    a.op16(0x8D, W_P1_OV_ATTR)
    a.op16(0xAD, W_P1_PAL_IDX + 2); a.emit(0x0A, 0x0A, 0x85, 0x11, 0x0A, 0x0A, 0x0A, 0x0A, 0x05, 0x11)
    a.op16(0x0D, W_P1_PAL_IDX + 3); a.emit(0x48); a.op16(0xAD, W_P1_PAL_IDX + 3); a.emit(0x0A, 0x0A, 0x0A, 0x0A, 0x85, 0x11, 0x68, 0x05, 0x11)
    a.op16(0x8D, W_P1_OV_ATTR + 1)
    a.op16(0xAD, W_P1_PAL_IDX + 0); a.emit(0x0A, 0x0A, 0x85, 0x11, 0x0A, 0x0A, 0x0A, 0x0A, 0x05, 0x11)
    a.op16(0x0D, W_P1_PAL_IDX + 1); a.emit(0x48); a.op16(0xAD, W_P1_PAL_IDX + 1); a.emit(0x0A, 0x0A, 0x0A, 0x0A, 0x85, 0x11, 0x68, 0x05, 0x11)
    a.op16(0x8D, W_P1_OV_ATTR + 2)
    a.emit(0x60)

    a.label('ba_cpu')
    a.emit(0xA2, 0x00)
    a.label('ba_cpu_cp')
    a.abs_ref(0xBC, 'TBL_CPU_LR_SEAT')
    a.op16(0xB9, W_CPU_PAL_IDX); a.op16(0x9D, W_CHRRAM_BUF)
    a.emit(0xE8, 0xE0, 0x05); a.branch(0xD0, 'ba_cpu_cp')
    a.emit(0xA0, 0x10); a.abs_ref(0x20, 'ba_emit_stage')
    # Overview CPU ($23E5..$23E7): cols 20..29 -> seats [0/1], [2/3], [4/none]
    a.op16(0xAD, W_CPU_PAL_IDX + 1); a.emit(0x0A, 0x0A, 0x85, 0x11, 0x0A, 0x0A, 0x0A, 0x0A, 0x05, 0x11)
    a.op16(0x0D, W_CPU_PAL_IDX + 0); a.emit(0x48); a.op16(0xAD, W_CPU_PAL_IDX + 0); a.emit(0x0A, 0x0A, 0x0A, 0x0A, 0x85, 0x11, 0x68, 0x05, 0x11)
    a.op16(0x8D, W_CPU_OV_ATTR)
    a.op16(0xAD, W_CPU_PAL_IDX + 3); a.emit(0x0A, 0x0A, 0x85, 0x11, 0x0A, 0x0A, 0x0A, 0x0A, 0x05, 0x11)
    a.op16(0x0D, W_CPU_PAL_IDX + 2); a.emit(0x48); a.op16(0xAD, W_CPU_PAL_IDX + 2); a.emit(0x0A, 0x0A, 0x0A, 0x0A, 0x85, 0x11, 0x68, 0x05, 0x11)
    a.op16(0x8D, W_CPU_OV_ATTR + 1)
    a.op16(0xAD, W_CPU_PAL_IDX + 4); a.emit(0x0A, 0x0A, 0x85, 0x11, 0x0A, 0x0A, 0x0A, 0x0A, 0x05, 0x11)
    a.op16(0x0D, W_CPU_PAL_IDX + 4); a.emit(0x48); a.op16(0xAD, W_CPU_PAL_IDX + 4); a.emit(0x0A, 0x0A, 0x0A, 0x0A, 0x85, 0x11, 0x68, 0x05, 0x11)
    a.op16(0x8D, W_CPU_OV_ATTR + 2)
    a.emit(0x60)

    a.label('ba_emit_stage')
    a.op16(0xAD, W_CHRRAM_BUF); a.emit(0x0A, 0x0A, 0x85, 0x11, 0x0A, 0x0A, 0x0A, 0x0A, 0x05, 0x11)
    a.op16(0x99, W_P1_ST_ATTR); a.emit(0x29, 0x0F); a.op16(0x99, W_P1_ST_ATTR + 8)
    a.emit(0xC8, 0xA2, 0x00)
    a.label('bes_lp')
    a.op16(0xBD, W_CHRRAM_BUF + 1); a.emit(0x0A, 0x0A, 0x85, 0x11, 0x0A, 0x0A, 0x0A, 0x0A, 0x05, 0x11)
    a.op16(0x1D, W_CHRRAM_BUF); a.emit(0x48); a.op16(0xBD, W_CHRRAM_BUF); a.emit(0x0A, 0x0A, 0x0A, 0x0A, 0x85, 0x11, 0x68, 0x05, 0x11)
    a.op16(0x99, W_P1_ST_ATTR); a.emit(0x29, 0x0F); a.op16(0x99, W_P1_ST_ATTR + 8)
    a.emit(0xC8, 0xE8, 0xE0, 0x04); a.branch(0xD0, 'bes_lp')
    a.op16(0xAD, W_CHRRAM_BUF + 4); a.emit(0x0A, 0x0A, 0x0A, 0x0A); a.op16(0x0D, W_CHRRAM_BUF + 4)
    a.op16(0x99, W_P1_ST_ATTR); a.emit(0x29, 0x0F); a.op16(0x99, W_P1_ST_ATTR + 8)
    a.emit(0xC8, 0xA9, 0x00); a.op16(0x99, W_P1_ST_ATTR); a.emit(0xC8); a.op16(0x99, W_P1_ST_ATTR)
    a.emit(0x60)

    # ---- B4_LOAD_FACEOFF ----
    a.label('B4_LOAD_FACEOFF')
    a.abs_ref(0x20, 'B4_SAVE_ZP')
    a.emit(0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20, 0x2C, 0x02, 0x20)
    a.emit(0xAD, 0xDC, 0x04); a.op16(0x8D, W_SEAT_IDX)
    a.emit(0xA9, 0x00); a.op16(0x8D, W_SIDE_ARG)
    a.label('lfo_side_lp')
    a.op16(0xAE, W_SEAT_IDX); a.op16(0xAD, W_SIDE_ARG)
    a.branch(0xD0, 'lfo_z2')
    a.op16(0xBD, W_P1_CHAR);    a.op16(0x8D, W_TMP0)
    a.op16(0xBD, W_P1_HEIGHT);  a.op16(0x8D, W_TMP1)
    a.op16(0xBD, W_P1_PAL_IDX); a.emit(0x38, 0xE9, 0x01, 0x0A, 0xA8)
    a.op16(0xB9, W_P1_PAL_CLR);     a.op16(0x8D, W_FO_COLORS)
    a.op16(0xB9, W_P1_PAL_CLR + 1); a.op16(0x8D, W_FO_COLORS + 1)
    a.abs_ref(0x4C, 'lfo_load')
    a.label('lfo_z2')
    a.op16(0xBD, W_CPU_CHAR);    a.op16(0x8D, W_TMP0)
    a.op16(0xBD, W_CPU_HEIGHT);  a.op16(0x8D, W_TMP1)
    a.op16(0xBD, W_CPU_PAL_IDX); a.emit(0x38, 0xE9, 0x01, 0x0A, 0xA8)
    a.op16(0xB9, W_CPU_PAL_CLR);     a.op16(0x8D, W_FO_COLORS + 2)
    a.op16(0xB9, W_CPU_PAL_CLR + 1); a.op16(0x8D, W_FO_COLORS + 3)
    a.label('lfo_load')
    a.abs_ref(0x20, 'B4_LOAD_VAR_PTR')
    a.op16(0xAD, W_ST_CNT); a.abs_ref(0x20, 'B4_ADV_0E_X16')
    a.emit(0xA9, 72);       a.abs_ref(0x20, 'B4_ADV_0E')
    a.op16(0xAD, W_OV_CNT); a.abs_ref(0x20, 'B4_ADV_0E_X16')
    a.emit(0xA9, 16);       a.abs_ref(0x20, 'B4_ADV_0E')

    a.emit(0xA9, 0x02, 0x18); a.op16(0x6D, W_SIDE_ARG)
    a.emit(0xA2, 0x21); a.abs_ref(0x20, 'B4_MAP_CHR0_P0')
    a.op16(0xAD, W_SIDE_ARG)
    a.branch(0xD0, 'lfo_fcpu')
    a.lda_lo('TBL_FO_P1_FREE'); a.emit(0x85, 0x11)
    a.lda_hi('TBL_FO_P1_FREE'); a.emit(0x85, 0x12)
    a.abs_ref(0x4C, 'lfo_stream')
    a.label('lfo_fcpu')
    a.lda_lo('TBL_FO_CPU_FREE'); a.emit(0x85, 0x11)
    a.lda_hi('TBL_FO_CPU_FREE'); a.emit(0x85, 0x12)
    a.label('lfo_stream')
    a.emit(0xA9, 0x00); a.op16(0x8D, W_TMP2)
    a.op16(0xAD, W_FO_CNT); a.op16(0x8D, W_COPY_CNT)
    a.abs_ref(0x20, 'B4_STREAM_FREE_TILES')
    a.op16(0xAD, W_SIDE_ARG); a.branch(0xF0, 'lfo_no_lip')
    a.emit(0xA2, 0x00, 0xA0, 0x00)
    a.label('lfo_lip_tile')
    a.abs_ref(0xBD, 'TBL_FO_CPU_LIP_IDS')
    a.abs_ref(0x20, 'B4_SET_PPU_TILE')
    a.emit(0xA9, 16); a.op16(0x8D, W_TMP3)
    a.label('lfo_lip_byte')
    a.abs_ref(0xB9, 'TBL_FO_CPU_LIP_TILES'); a.emit(0x8D, 0x07, 0x20, 0xC8)
    a.op16(0xCE, W_TMP3); a.branch(0xD0, 'lfo_lip_byte')
    a.emit(0xE8, 0xE0, 0x03); a.branch(0xD0, 'lfo_lip_tile')
    a.label('lfo_no_lip')

    a.emit(0xA9, 0x00); a.op16(0x8D, W_COPY_CNT)
    a.label('lfo_blk_frm')
    a.op16(0xAD, W_SIDE_ARG); a.branch(0xD0, 'lfo_cpu_frm')
    # --- P1: 7x12 block (70 upper tiles + 14 bottom blank) into W_FO_BLKS + 0/86 ---
    a.emit(0xA2, 0x00)
    a.op16(0xAD, W_COPY_CNT); a.branch(0xF0, 'lfo_p1_off')
    a.emit(0xA2, 86)
    a.label('lfo_p1_off')
    a.emit(0xA9, 0x07); a.op16(0x9D, W_FO_BLKS); a.emit(0xE8)
    a.emit(0xA9, 0x0C); a.op16(0x9D, W_FO_BLKS); a.emit(0xE8)
    a.emit(0xA0, 0x00)
    a.label('lfo_map70')
    a.emit(0xB1, 0x0E)
    a.branch(0xF0, 'lfo_mz70')
    a.emit(0x84, 0x10, 0x38, 0xE9, 0x01, 0xA8, 0xB1, 0x11, 0xA4, 0x10)
    a.label('lfo_mz70')
    a.op16(0x9D, W_FO_BLKS); a.emit(0xE8, 0xC8, 0xC0, 70)
    a.branch(0xD0, 'lfo_map70')
    a.emit(0xA9, 0x00); a.emit(0xA0, 14)
    a.label('lfo_bot14')
    a.op16(0x9D, W_FO_BLKS); a.emit(0xE8, 0x88)
    a.branch(0xD0, 'lfo_bot14')
    a.emit(0xA9, 70); a.abs_ref(0x20, 'B4_ADV_0E')
    a.abs_ref(0x4C, 'lfo_next_frm')

    # --- CPU: 6x12 block (60 upper tiles + 12 bottom floor/lip) into W_FO_CPU_BLKS + 0/74 ---
    a.label('lfo_cpu_frm')
    a.emit(0xA2, 0x00)
    a.op16(0xAD, W_COPY_CNT); a.branch(0xF0, 'lfo_cpu_off')
    a.emit(0xA2, 74)
    a.label('lfo_cpu_off')
    a.emit(0xA9, 0x06); a.op16(0x9D, W_FO_CPU_BLKS); a.emit(0xE8)
    a.emit(0xA9, 0x0C); a.op16(0x9D, W_FO_CPU_BLKS); a.emit(0xE8)
    a.emit(0xA0, 0x00)
    a.label('lfo_map60')
    a.emit(0xB1, 0x0E)
    a.branch(0xF0, 'lfo_mz60')
    a.emit(0x84, 0x10, 0x38, 0xE9, 0x01, 0xA8, 0xB1, 0x11, 0xA4, 0x10)
    a.label('lfo_mz60')
    a.op16(0x9D, W_FO_CPU_BLKS); a.emit(0xE8, 0xC8, 0xC0, 60)
    a.branch(0xD0, 'lfo_map60')
    a.emit(0xA0, 0x00)
    a.label('lfo_bot12')
    a.abs_ref(0xB9, 'TBL_FO_CPU_BOT2')
    a.op16(0x9D, W_FO_CPU_BLKS); a.emit(0xE8, 0xC8, 0xC0, 12)
    a.branch(0xD0, 'lfo_bot12')
    a.emit(0xA9, 60); a.abs_ref(0x20, 'B4_ADV_0E')

    a.label('lfo_next_frm')
    a.op16(0xEE, W_COPY_CNT); a.op16(0xAD, W_COPY_CNT); a.emit(0xC9, 0x02)
    a.branch(0xF0, 'lfo_frm_done')
    a.abs_ref(0x4C, 'lfo_blk_frm')
    a.label('lfo_frm_done')
    # Face-Off animation scripts ($94/$96/$98/$9A/$9C) swap seats 2 and 3 ([0,1,3,2,4]).
    a.op16(0xAC, W_SEAT_IDX); a.abs_ref(0xB9, 'TBL_CPU_LR_SEAT'); a.op16(0x8D, W_TMP0)

    # Clear old DYN for 75..79, 82..86, 91..95, 98..102 once (only on side=0)
    a.op16(0xAD, W_SIDE_ARG); a.branch(0xD0, 'lfo_reg_cpu')
    a.emit(0xA2, 0x04, 0xA9, 0x00)
    a.label('lfo_clr_dyn')
    a.op16(0x9D, W_BLK_DYN + 75); a.op16(0x9D, W_BLK_DYN + 82)
    a.op16(0x9D, W_BLK_DYN + 91); a.op16(0x9D, W_BLK_DYN + 98)
    a.emit(0xCA); a.branch(0x10, 'lfo_clr_dyn')

    a.emit(0xA9, 75, 0x18); a.op16(0x6D, W_TMP0); a.emit(0xAA)
    a.emit(0xA9, W_FO_BLKS & 0xFF);        a.op16(0x9D, W_BLK_T_LO)
    a.emit(0xA9, W_FO_BLKS >> 8);          a.op16(0x9D, W_BLK_T_HI)
    a.emit(0xA9, W_FO_OAM_ATTR & 0xFF);    a.op16(0x9D, W_BLK_A_LO)
    a.emit(0xA9, W_FO_OAM_ATTR >> 8);      a.op16(0x9D, W_BLK_A_HI)
    a.emit(0xA9, 0x01);                    a.op16(0x9D, W_BLK_DYN)
    a.emit(0xA9, 82, 0x18); a.op16(0x6D, W_TMP0); a.emit(0xAA)
    a.emit(0xA9, (W_FO_BLKS + 86) & 0xFF); a.op16(0x9D, W_BLK_T_LO)
    a.emit(0xA9, (W_FO_BLKS + 86) >> 8);   a.op16(0x9D, W_BLK_T_HI)
    a.emit(0xA9, W_FO_OAM_ATTR & 0xFF);    a.op16(0x9D, W_BLK_A_LO)
    a.emit(0xA9, W_FO_OAM_ATTR >> 8);      a.op16(0x9D, W_BLK_A_HI)
    a.emit(0xA9, 0x01);                    a.op16(0x9D, W_BLK_DYN)
    a.abs_ref(0x4C, 'lfo_next_side')
    a.label('lfo_reg_cpu')
    a.emit(0xA9, 91, 0x18); a.op16(0x6D, W_TMP0); a.emit(0xAA)
    a.emit(0xA9, W_FO_CPU_BLKS & 0xFF);        a.op16(0x9D, W_BLK_T_LO)
    a.emit(0xA9, W_FO_CPU_BLKS >> 8);          a.op16(0x9D, W_BLK_T_HI)
    a.emit(0xBD, 0x18, 0xF2);                  a.op16(0x9D, W_BLK_A_LO)
    a.emit(0xBD, 0xE5, 0xF2);                  a.op16(0x9D, W_BLK_A_HI)
    a.emit(0xA9, 0x01);                        a.op16(0x9D, W_BLK_DYN)
    a.emit(0xA9, 98, 0x18); a.op16(0x6D, W_TMP0); a.emit(0xAA)
    a.emit(0xA9, (W_FO_CPU_BLKS + 74) & 0xFF); a.op16(0x9D, W_BLK_T_LO)
    a.emit(0xA9, (W_FO_CPU_BLKS + 74) >> 8);   a.op16(0x9D, W_BLK_T_HI)
    a.emit(0xBD, 0x18, 0xF2);                  a.op16(0x9D, W_BLK_A_LO)
    a.emit(0xBD, 0xE5, 0xF2);                  a.op16(0x9D, W_BLK_A_HI)
    a.emit(0xA9, 0x01);                        a.op16(0x9D, W_BLK_DYN)

    a.label('lfo_next_side')
    a.op16(0xEE, W_SIDE_ARG); a.op16(0xAD, W_SIDE_ARG); a.emit(0xC9, 0x02)
    a.branch(0xF0, 'lfo_done')
    a.abs_ref(0x4C, 'lfo_side_lp')
    a.label('lfo_done')
    for i, val in enumerate((0x10, 0xA0, 0xA0, 0x11, 0xAA, 0xAA, 0x00, 0x0A, 0x0A)):
        a.emit(0xA9, val); a.op16(0x8D, W_CPU_FO_ATTR + i)
    a.abs_ref(0x4C, 'B4_RESTORE_ZP')

    # ---- B4_PICK_Z2_NAME ----
    a.label('B4_PICK_Z2_NAME')
    a.label('pzn_rng')
    a.abs_ref(0x20, 'B4_RNG')
    a.emit(0xAD, 0xFA, 0x01, 0x45, 0x1F, 0x29, 0x1F, 0xC9, len(ZELDA_FAMILY_NAMES))
    a.branch(0xB0, 'pzn_rng')
    a.emit(0xAA)
    a.abs_ref(0xBC, 'TBL_NAME_OFF')
    a.emit(0xA2, 0x00)
    a.label('pzn_cp')
    a.abs_ref(0xB9, 'TBL_NAMES')
    a.emit(0x9D, 0x08, 0x03)
    a.branch(0x30, 'pzn_done')
    a.emit(0xE8, 0xC8); a.abs_ref(0x4C, 'pzn_cp')
    a.label('pzn_done')
    a.emit(0x60)

    # ---- B4_ZELDA_LOSE ----
    a.label('B4_ZELDA_LOSE')
    a.abs_ref(0x20, 'B4_SAVE_ZP')
    a.label('zl_rng')
    a.abs_ref(0x20, 'B4_RNG')
    a.emit(0xAD, 0xFA, 0x01, 0x45, 0x1F, 0x29, 0x07, 0xC9, 0x07)
    a.branch(0xB0, 'zl_rng')
    a.op16(0x8D, W_LAST_LOSE_IDX)
    a.emit(0x48)
    a.emit(0xA9, 0x21, 0x8D, 0x06, 0x20, 0xA9, 0x02, 0x8D, 0x06, 0x20)
    a.emit(0xA9, 0x00, 0xA2, 28)
    a.label('zl_clr8')
    a.emit(0x8D, 0x07, 0x20, 0xCA); a.branch(0xD0, 'zl_clr8')
    a.emit(0xA9, 0x21, 0x8D, 0x06, 0x20, 0xA9, 0x82, 0x8D, 0x06, 0x20)
    a.emit(0xA9, 0x00, 0xA2, 28)
    a.label('zl_clr12')
    a.emit(0x8D, 0x07, 0x20, 0xCA); a.branch(0xD0, 'zl_clr12')

    a.emit(0x68, 0xAA)
    a.abs_ref(0xBD, 'TBL_LOSE_LO'); a.emit(0x85, 0x0E)
    a.abs_ref(0xBD, 'TBL_LOSE_HI'); a.emit(0x85, 0x0F)
    a.abs_ref(0xBD, 'TBL_LOSE_LEN'); a.op16(0x8D, W_TMP0)
    a.abs_ref(0xBD, 'TBL_LOSE_PAD')
    a.emit(0x18, 0x69, 0x02, 0x48)
    a.emit(0xA9, 0x21, 0x8D, 0x06, 0x20, 0x68, 0x8D, 0x06, 0x20)
    a.emit(0xA0, 0x00)
    a.label('zl_wr_r')
    a.emit(0xB1, 0x0E, 0x8D, 0x07, 0x20, 0xC8)
    a.emit(0x98); a.op16(0xCD, W_TMP0); a.branch(0xD0, 'zl_wr_r')

    a.emit(0xA2, 0x00)
    a.label('zl_nlen')
    a.emit(0xBD, 0x08, 0x03, 0x08, 0xE8, 0x28)
    a.branch(0x10, 'zl_nlen')
    a.op16(0x8E, W_TMP0)
    a.emit(0xA9, 17, 0x38); a.op16(0xED, W_TMP0); a.emit(0x4A)
    a.emit(0x18, 0x69, 0x82, 0x48)
    a.emit(0xA9, 0x21, 0x8D, 0x06, 0x20, 0x68, 0x8D, 0x06, 0x20)
    a.emit(0xA2, 0x00)
    a.label('zl_the')
    a.abs_ref(0xBD, 'TBL_BLUE_THE'); a.emit(0x8D, 0x07, 0x20, 0xE8, 0xE0, 0x04)
    a.branch(0xD0, 'zl_the')
    a.emit(0xA2, 0x00)
    a.label('zl_name')
    a.emit(0xBD, 0x08, 0x03, 0x08, 0x29, 0x7F, 0x18, 0x69, 0x08, 0x8D, 0x07, 0x20, 0xE8, 0x28)
    a.branch(0x10, 'zl_name')
    a.emit(0xA2, 0x00)
    a.label('zl_fam')
    a.abs_ref(0xBD, 'TBL_BLUE_FAMILY'); a.emit(0x8D, 0x07, 0x20, 0xE8, 0xE0, 0x07)
    a.branch(0xD0, 'zl_fam')
    a.abs_ref(0x4C, 'B4_RESTORE_ZP')

    # Unrolled replacement for $D027 (writes $3F10..$3F1F from $30..$3F and $3F00..$3F0F from $031D..$032C).
    # Saves ~230 cycles (>2 scanlines) per palette update so board/Face-Off NMI bursts never spill past VBlank.
    a.label('TBL_FAST_PAL')
    fast_pal_start = len(a.buf)
    a.emit(0xA9, 0x3F, 0x8D, 0x06, 0x20, 0xA9, 0x10, 0x8D, 0x06, 0x20)
    for i in range(16):
        a.emit(0xA5, 0x30 + i, 0x8D, 0x07, 0x20)
    a.emit(0xA9, 0x3F, 0x8D, 0x06, 0x20, 0xA9, 0x00, 0x8D, 0x06, 0x20, 0x85, 0x1F)
    for i in range(16):
        addr = 0x031D + i
        a.emit(0xAD, addr & 0xFF, addr >> 8, 0x8D, 0x07, 0x20)
    a.emit(0xA2, 0x10, 0x60)
    pad_len = 256 - (len(a.buf) - fast_pal_start)
    assert pad_len >= 0, f'TBL_FAST_PAL overflow: {256 - pad_len} > 256'
    a.emit(*([0x00] * pad_len))

    out = a.finish()
    assert len(out) <= 0x1700, f'Bank 4 engine overflowed: {len(out)} > 5888'
    return out

