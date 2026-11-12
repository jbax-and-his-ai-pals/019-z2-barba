# Zelda II — Barba Edition

A work-in-progress NES ROM hack that makes Barba the playable protagonist in
*Zelda II: The Adventure of Link*.

The design uses a compact serpentine dragon, preserves the original progression,
and targets an ordinary MMC1 cartridge with NES-native audio.

## Development

The source ROM belongs at `roms/z2.nes`. It is never modified in place.
ROMs, extracted game assets, emulator saves, and downloaded tools are excluded
from this repository. Build outputs and patches are generated locally.

See [the refined design](docs/DESIGN.md), [build instructions](docs/BUILD.md),
and [research notes](docs/RESEARCH.md).

This is an unofficial fan project. Zelda II and its original characters,
graphics, music, and game data belong to their respective owners.

## Credits

Research references include Trax's Zelda II disassembly and the
[FiendsOfTheElements buildable version](https://github.com/FiendsOfTheElements/z2disassembly),
the [NESdev documentation](https://www.nesdev.org/wiki/Nesdev_Wiki),
[cc65](https://cc65.github.io/), and [Mesen](https://github.com/SourMesen/Mesen2).
Original game code and graphics are obtained only from the user's local ROM.
