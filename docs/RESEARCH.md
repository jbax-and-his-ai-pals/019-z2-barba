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
