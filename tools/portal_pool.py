"""Subgame portal pool, Barba's Arcade booth layout, and Mapper 176 slot manifest."""
from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CandidateDoor:
    """An audited Zelda II doorway (inside Barba's Arcade, Rauru room $1C) for subgames."""

    id: str
    town_id: int        # $056B
    town_name: str
    room: int           # $0561
    page: int           # $3B
    x_lo: int           # $4D min
    x_hi: int           # $4D max
    note: str


# 11 arcade booths inside Barba's Arcade (Rauru interior room $1C, pages 0..3),
# plus room for expansion on page 3.
CANDIDATE_DOORS: list[CandidateDoor] = [
    CandidateDoor(
        id='arcade_waldo',
        town_id=0x00,
        town_name="Barba's Arcade",
        room=0x1C,
        page=0x00,
        x_lo=0x48,
        x_hi=0x60,
        note="Barba's Arcade page 0 booth 0 (Where's Barba?)",
    ),
    CandidateDoor(
        id='arcade_f13',
        town_id=0x00,
        town_name="Barba's Arcade",
        room=0x1C,
        page=0x00,
        x_lo=0x88,
        x_hi=0xA0,
        note="Barba's Arcade page 0 booth 1 (Friday the 13th)",
    ),
    CandidateDoor(
        id='arcade_feud',
        town_id=0x00,
        town_name="Barba's Arcade",
        room=0x1C,
        page=0x00,
        x_lo=0xC8,
        x_hi=0xE0,
        note="Barba's Arcade page 0 booth 2 (Barba's Beef / Family Feud)",
    ),
    CandidateDoor(
        id='arcade_dk',
        town_id=0x00,
        town_name="Barba's Arcade",
        room=0x1C,
        page=0x01,
        x_lo=0x18,
        x_hi=0x30,
        note="Barba's Arcade page 1 booth 3 (Barba Kong)",
    ),
    CandidateDoor(
        id='arcade_smb',
        town_id=0x00,
        town_name="Barba's Arcade",
        room=0x1C,
        page=0x01,
        x_lo=0x68,
        x_hi=0x80,
        note="Barba's Arcade page 1 booth 4 (Super Barba Bros.)",
    ),
    CandidateDoor(
        id='arcade_duck',
        town_id=0x00,
        town_name="Barba's Arcade",
        room=0x1C,
        page=0x01,
        x_lo=0xB8,
        x_hi=0xD0,
        note="Barba's Arcade page 1 booth 5 (Villager Hunt)",
    ),
    CandidateDoor(
        id='arcade_mm2',
        town_id=0x00,
        town_name="Barba's Arcade",
        room=0x1C,
        page=0x02,
        x_lo=0x68,
        x_hi=0x80,
        note="Barba's Arcade page 2 booth 7 (Barba Man 2)",
    ),
    CandidateDoor(
        id='arcade_wheel',
        town_id=0x00,
        town_name="Barba's Arcade",
        room=0x1C,
        page=0x02,
        x_lo=0xB8,
        x_hi=0xD0,
        note="Barba's Arcade page 2 booth 8 (Wheel of Barba)",
    ),
    CandidateDoor(
        id='arcade_zelda',
        town_id=0x00,
        town_name="Barba's Arcade",
        room=0x1C,
        page=0x03,
        x_lo=0x18,
        x_hi=0x30,
        note="Barba's Arcade page 3 booth 9 (Legend of Barba)",
    ),
    CandidateDoor(
        id='arcade_mtpo',
        town_id=0x00,
        town_name="Barba's Arcade",
        room=0x1C,
        page=0x03,
        x_lo=0x68,
        x_hi=0x80,
        note="Barba's Arcade page 3 booth 10 (Barba's Punch-Out!!)",
    ),
]
CANDIDATE_DOORS_BY_ID: dict[str, CandidateDoor] = {d.id: d for d in CANDIDATE_DOORS}


@dataclass(frozen=True)
class SubgameSpec:
    """Metadata and Mapper 176 boot parameters for a pool subgame."""

    id: str
    name: str
    mapper_class: str       # 'mmc3', 'cnrom', 'unrom', 'mmc1', 'nrom', 'axrom', 'mmc2'
    wram_bank: int          # $A001 value ($A2 = bank 2, $A3 = bank 3, ...)
    reg_5ff0: int           # FK23C outer mode
    reg_5ff1: int           # FK23C PRG outer bank
    reg_5ff2: int           # FK23C CHR outer bank
    r6_bank: int            # MMC3 R6 ($8000-$9FFF) initial bank
    boot_addr: int          # Guest entry address after outer-bank switch
    default_door_id: str
    reward_addr: int = 0x63B0
    name_label: str = 'ArcadeName00'
    status: str = 'greenlit'  # 'candidate' | 'round1' | 'greenlit'


SUBGAME_POOL: list[SubgameSpec] = [
    SubgameSpec(
        id='waldo',
        name="Where's Barba? (Where's Waldo?)",
        mapper_class='mmc3',
        wram_bank=0xA2,
        reg_5ff0=0x01,
        reg_5ff1=0x10,
        reg_5ff2=0x20,
        r6_bank=0x00,
        boot_addr=0xE000,
        default_door_id='arcade_waldo',
        reward_addr=0x648B,
        name_label='ArcadeName00',
        status='greenlit',
    ),
    SubgameSpec(
        id='f13',
        name='Friday the 13th: Barba Edition',
        mapper_class='cnrom',
        wram_bank=0xA3,
        reg_5ff0=0x01,
        reg_5ff1=0x20,
        reg_5ff2=0x30,
        r6_bank=0x00,
        boot_addr=0x8000,
        default_door_id='arcade_f13',
        reward_addr=0x63B1,
        name_label='ArcadeName01',
        status='greenlit',
    ),
    SubgameSpec(
        id='feud',
        name="Barba's Beef (Family Feud)",
        mapper_class='mmc1',
        wram_bank=0xA3,
        reg_5ff0=0x01,
        reg_5ff1=0x40,
        reg_5ff2=0x80,
        r6_bank=0x04,
        boot_addr=0x8300,
        default_door_id='arcade_feud',
        reward_addr=0x63B2,
        name_label='ArcadeName02',
        status='greenlit',
    ),
    SubgameSpec(
        id='dk',
        name='Barba Kong (Donkey Kong)',
        mapper_class='nrom',
        wram_bank=0xA3,
        reg_5ff0=0x01,
        reg_5ff1=0x70,
        reg_5ff2=0x40,
        r6_bank=0x00,
        boot_addr=0x8000,
        default_door_id='arcade_dk',
        reward_addr=0x63B3,
        name_label='ArcadeName03',
        status='round1',
    ),
    SubgameSpec(
        id='smb',
        name='Super Barba Bros.',
        mapper_class='nrom',
        wram_bank=0xA3,
        reg_5ff0=0x01,
        reg_5ff1=0x60,
        reg_5ff2=0x50,
        r6_bank=0x00,
        boot_addr=0x8000,
        default_door_id='arcade_smb',
        reward_addr=0x63B4,
        name_label='ArcadeName04',
        status='round1',
    ),
    SubgameSpec(
        id='duck',
        name='Villager Hunt (Duck Hunt)',
        mapper_class='nrom',
        wram_bank=0xA3,
        reg_5ff0=0x09,
        reg_5ff1=0x40,
        reg_5ff2=0x60,
        r6_bank=0x00,
        boot_addr=0x8000,
        default_door_id='arcade_duck',
        reward_addr=0x63B5,
        name_label='ArcadeName05',
        status='round1',
    ),
    SubgameSpec(
        id='mm2',
        name='Barba Man 2 (Mega Man 2)',
        mapper_class='mmc1',
        wram_bank=0xA3,
        reg_5ff0=0x21,
        reg_5ff1=0x30,
        reg_5ff2=0x00,
        r6_bank=0x1C,
        boot_addr=0xF450,
        default_door_id='arcade_mm2',
        reward_addr=0x63B7,
        name_label='ArcadeName07',
        status='round1',
    ),
    SubgameSpec(
        id='wheel',
        name='Wheel of Barba (Wheel of Fortune)',
        mapper_class='axrom',
        wram_bank=0xA3,
        reg_5ff0=0x29,
        reg_5ff1=0x00,
        reg_5ff2=0x00,
        r6_bank=0x00,
        boot_addr=0x8000,
        default_door_id='arcade_wheel',
        reward_addr=0x63B8,
        name_label='ArcadeName08',
        status='round1',
    ),
    SubgameSpec(
        id='zelda',
        name='The Legend of Barba (Zelda 1)',
        mapper_class='mmc1',
        wram_bank=0xA3,
        reg_5ff0=0x29,
        reg_5ff1=0x60,
        reg_5ff2=0x00,
        r6_bank=0x00,
        boot_addr=0x8000,
        default_door_id='arcade_zelda',
        reward_addr=0x63B9,
        name_label='ArcadeName09',
        status='candidate',
    ),
    SubgameSpec(
        id='mtpo',
        name="Barba's Punch-Out!!",
        mapper_class='mmc2',
        wram_bank=0xA3,
        reg_5ff0=0x09,
        reg_5ff1=0x70,
        reg_5ff2=0x90,
        r6_bank=0x00,
        boot_addr=0x8000,
        default_door_id='arcade_mtpo',
        reward_addr=0x63BA,
        name_label='ArcadeName10',
        status='candidate',
    ),
]
SUBGAME_POOL_BY_ID: dict[str, SubgameSpec] = {s.id: s for s in SUBGAME_POOL}


@dataclass(frozen=True)
class PortalAssignment:
    """Resolved portal slot pairing a SubgameSpec with a CandidateDoor."""

    slot: int
    subgame: SubgameSpec
    door: CandidateDoor

    def to_manifest_dict(self) -> dict:
        return {
            'slot': self.slot,
            'id': self.subgame.id,
            'name': self.subgame.name,
            'mapper_class': self.subgame.mapper_class,
            'status': self.subgame.status,
            'reward_addr': self.subgame.reward_addr,
            'door': asdict(self.door),
            'boot': {
                'wram_bank': self.subgame.wram_bank,
                'reg_5ff0': self.subgame.reg_5ff0,
                'reg_5ff1': self.subgame.reg_5ff1,
                'reg_5ff2': self.subgame.reg_5ff2,
                'r6_bank': self.subgame.r6_bank,
                'boot_addr': self.subgame.boot_addr,
            },
        }


MAX_PORTAL_SLOTS = 16
TOOLS_DIR = Path(__file__).resolve().parent


def build_portal_assignments(
    selected_ids: list[str] | None = None,
    *,
    seed: int | None = None,
    include_f13: bool = True,
    roms_dir: Path | None = None,
) -> list[PortalAssignment]:
    """Build ordered portal slot assignments."""
    if selected_ids is None:
        ids = ['waldo']
        if include_f13:
            ids.append('f13')
        if roms_dir is not None:
            for sid in ('feud', 'dk', 'smb', 'duck', 'mm2', 'wheel', 'zelda', 'mtpo'):
                if (roms_dir / f'{sid}.nes').is_file() and (TOOLS_DIR / f'pack_{sid}.py').is_file():
                    ids.append(sid)
    else:
        ids = list(selected_ids)

    if len(ids) > MAX_PORTAL_SLOTS:
        raise ValueError(f'At most {MAX_PORTAL_SLOTS} portal slots are supported (got {len(ids)})')

    specs = [SUBGAME_POOL_BY_ID[sid] for sid in ids]

    if seed is None:
        doors = [CANDIDATE_DOORS_BY_ID[s.default_door_id] for s in specs]
    else:
        if len(specs) > len(CANDIDATE_DOORS):
            raise ValueError('Not enough CANDIDATE_DOORS for requested subgame count')
        rng = random.Random(seed)
        doors = rng.sample(CANDIDATE_DOORS, len(specs))

    return [
        PortalAssignment(slot=idx, subgame=spec, door=door)
        for idx, (spec, door) in enumerate(zip(specs, doors))
    ]


def patch_portal_tables(
    rom: bytearray,
    labels: dict[str, int],
    assignments: list[PortalAssignment],
    prg_offset_fn,
) -> None:
    """Patch Barba's PortalTbl* arrays in-place from resolved PortalAssignments."""
    if not assignments:
        return
    if len(assignments) > MAX_PORTAL_SLOTS:
        raise ValueError(f'Portal table supports at most {MAX_PORTAL_SLOTS} slots (got {len(assignments)})')

    def put_b2(name: str, data: bytes) -> None:
        off = prg_offset_fn(2, labels[name])
        rom[off : off + len(data)] = data

    n = len(assignments)
    put_b2('PortalCount', bytes([n]))
    put_b2('PortalTblTown', bytes(a.door.town_id for a in assignments))
    put_b2('PortalTblRoom', bytes(a.door.room for a in assignments))
    put_b2('PortalTblPage', bytes(a.door.page for a in assignments))
    put_b2('PortalTblXlo', bytes(a.door.x_lo for a in assignments))
    put_b2('PortalTblXhi', bytes(a.door.x_hi for a in assignments))

    put_b2('PortalTblWram', bytes(a.subgame.wram_bank for a in assignments))
    put_b2('PortalTbl5FF0', bytes(a.subgame.reg_5ff0 for a in assignments))
    put_b2('PortalTbl5FF1', bytes(a.subgame.reg_5ff1 for a in assignments))
    put_b2('PortalTbl5FF2', bytes(a.subgame.reg_5ff2 for a in assignments))
    put_b2('PortalTblR6', bytes(a.subgame.r6_bank for a in assignments))
    put_b2('PortalTblBootLo', bytes(a.subgame.boot_addr & 0xFF for a in assignments))
    put_b2('PortalTblBootHi', bytes((a.subgame.boot_addr >> 8) & 0xFF for a in assignments))
    if 'PortalTblNameLo' in labels and 'PortalTblNameHi' in labels:
        name_addrs = [labels[a.subgame.name_label] for a in assignments]
        put_b2('PortalTblNameLo', bytes(addr & 0xFF for addr in name_addrs))
        put_b2('PortalTblNameHi', bytes((addr >> 8) & 0xFF for addr in name_addrs))
    if 'PortalTblSignLo' in labels and 'PortalTblSignHi' in labels:
        sign_addrs = [labels[a.subgame.name_label.replace('Name', 'Sign')] for a in assignments]
        put_b2('PortalTblSignLo', bytes(addr & 0xFF for addr in sign_addrs))
        put_b2('PortalTblSignHi', bytes((addr >> 8) & 0xFF for addr in sign_addrs))


def write_portal_manifest(path: Path, assignments: list[PortalAssignment], *, seed: int | None = None) -> Path:
    """Write build/portal-manifest.json for test-pack generators and tooling."""
    payload = {
        'seed': seed,
        'slots': [a.to_manifest_dict() for a in assignments],
    }
    path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    return path
