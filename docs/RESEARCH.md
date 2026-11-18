# Research notes

## Local input

- Size: 262,160 bytes, including a 16-byte iNES header.
- Header: `4e45531a081012000000000000000000`.
- Mapper 1 (MMC1); 128 KiB PRG; 128 KiB CHR; battery-backed save flag.
- SHA-256: `ad8c0fbcf092bf84b48e69fd3964eea4ed91bfe62abc352943d537979782680c`.
- Headerless CRC32: `BA322865`.

## Disassembly evaluation

[FiendsOfTheElements/z2disassembly](https://github.com/FiendsOfTheElements/z2disassembly)
at `c4c3a4c7d4156b41f54f726dc40644d45812ad29` was assembled with ca65/ld65.
The resulting 128 KiB PRG differs from this input at 853 bytes. Differences
include omitted bank-end mapper/reset routines and several changed references.
Its build script also concatenates only fourteen 8 KiB CHR chunks, while this
input declares sixteen. Therefore, it is a research reference, not a replacement
for the user's ROM or a demonstrated matching rebuild.

Implementation uses checked overlays against the original input. New code
assembles into documented free space. Every replacement checks original bytes;
the source hash, changed ranges, and output hash are recorded by the build.

The upstream disassembly is deliberately kept only in the ignored local tools
folder. This public repository contains the new routines and asset compiler,
not a repackaged copy of the original game's full disassembled program.

## Relevant findings

- Bank 0 has an annotated free region at CPU `$AA40` through `$BF6F`.
- Fixed bank 7 has small annotated free regions at `$D39A` and `$FEAA`.
- Player side-view display: bank 7 `$EBF0`; six 8x16 sprite slots are available.
- Attack origin: RAM `$047E/$0480`; melee bounding box: bank 7 `$E9A2`.
- Collision bits: RAM `$A7`, bits `ABLR`; below is bit 2.
- Hazard entry: bank 7 `$E0A4`; both lava and water reach it.
- Side-view area group: RAM `$0707`; palace groups start at 3.
- Player animation graphics repeat across numerous 4 KiB CHR banks.
- NES sprite evaluation selects at most eight sprites per scanline. A wide
  player plus breath can crowd out enemies. Keep sprite width modest.
  [NESdev: sprite evaluation](https://www.nesdev.org/wiki/PPU_sprite_evaluation).
- The FDS roar cannot be transplanted as FDS register writes into an MMC1 NES
  cartridge: its wavetable channel belongs to the FDS hardware.
  [NESdev: FDS audio](https://www.nesdev.org/wiki/FDS_audio).
- DPCM is an alternative, but its sample addressing and bank stability require
  planning. Native synthesis is the initial approach.
  [NESdev: DMC](https://www.nesdev.org/wiki/APU_DMC).

## Gotchas & lessons learned (extracted from archived plans)

- **Sprite Palette 1 (`$3F15`) is shared**: boss health bars, Barba's partial LIFE
  bar, and Barba's fireballs all use Sprite Palette 1. Recoloring a boss (such as
  Lava Link) must use Sprite Palette 3 (`$3F1D`) instead, or player fireballs and
  HUD bars lose their red/orange/white colors.
- **Lava Link boss geometry & shield**:
  - The boss head is 16x16 (`14/16`, `1C/22`, `28/2A`), not 32x16; only the left
    16 px ever render.
  - The neck loop at bank 4 `$B294` must draw at least 1 piece even below Y `$D0`
    so `$049A` (head/beam X) stays current while the boss emerges.
  - A closed-head shield that blocks fire outside the beam window was tried and
    reverted — it made the boss too hard to hit. Don't re-add it.
- **Temporary collision origins must be restored**: `BarbaBlocks` (`src/blocks.inc`)
  temporarily overwrites `$0480/$047E` to test each live fireball against blocks.
  It must restore the held thrust origin (`BarbaSetThrusts`) afterward, otherwise a
  live fireball erases the rising head-butt / downstab hitbox before the next enemy
  update.
- **Visual height vs. physical hitbox**: Barba's 24x48 tall head is visual while
  the physical body stays native height. Vertical hitboxes (like the rising
  head-butt) must be anchored to the native head top, not the 48 px art top, or
  attacks hit things Barba didn't touch.
- **NMI CPU budget & battle slowdown (~29,780 cycles/frame)**:
  - The main cause of battle lag wasn't per-enemy collision math alone — it was
    repeated MMC1 bank switches in fixed-bank gateways even when no extra shots
    were alive, plus idle slot-0 save/restore copies. Keep `EXTRA_LIVE` fast paths
    in the fixed bank and early-exit idle paths.
  - Alternate-frame collision thinning gave no measurable benefit and was reverted.
  - Queued volley throttling (`BarbaLoadOk`) and integer-velocity fast paths keep
    lag at 0 frames without thinning collisions.
- **8-sprites-per-line PPU limit & OAM rotation**:
  - Wide sprites + breath + enemies easily exceed 8 sprites/scanline. Rotating OAM
    priority on odd frames (`$12 & 1`) between Barba's outer head / lower body and
    enemy slots prevents permanent sprite dropout (converting it to 30 Hz flicker).
  - A lagged 16x16 trailing torso segment was prototyped (`docs/archive/trailing-torso-prototype.patch`)
    and shelved due to +190 cycles/frame and extra OAM scanline pressure.
- **Town shouts & nametable writes**: writing dynamic text into the playfield
  nametable near moving villagers requires background tile restoration, attribute
  handling, and heavy VBlank traffic. Anchoring 8x16 sprite glyphs to the speaker
  avoids all nametable/scrolling math.
