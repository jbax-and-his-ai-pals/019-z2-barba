# Zelda II — Barba Edition

A work-in-progress NES ROM hack that makes Barba the playable protagonist in
*Zelda II: The Adventure of Link*.

The design uses a compact serpentine dragon, preserves the original progression,
and targets an ordinary MMC1 cartridge with NES-native audio.

## Development alpha

The local build currently includes:

- Coiled side-view Barba with animation remapping, an 8x16 flying wyrmling,
  and a dedicated 16x16 overworld avatar with directional animation.
- A two-part horizontal flame plume and a 22x10 melee region, including crouched
  attacks. Enemy damage and Fire-spell vulnerability rules retain their original roles.
- Faster ranged shots and a fiery attack sound.
- Palace lava surface support with normal movement and jumping. Water outside
  palaces retains its original death behavior.
- Dragon spell menu names and a short native noise-channel roar on Inferno.
- Dragon sea crossings on the existing raft route and unlock.

**Not a finished conversion.** Vertical attacks still need dedicated flame art;
Palace 6's boss has not yet received the Ice Barba treatment. Title/story text,
some menu graphics, lava pose polish, and full-game compatibility testing remain.
See [validation and remaining work](docs/STATUS.md) for exact coverage.

## Development

The source ROM belongs at `roms/z2.nes`. It is never modified in place.
ROMs, extracted game assets, emulator saves, and downloaded tools are excluded
from this repository. Build outputs and patches are generated locally.

```powershell
.\tools\bootstrap.ps1 -WithEmulator
python tools/build.py
```

Open `build/barba.nes` in a standard NES emulator. `build/barba.bps` is the
source-specific patch; the build validates a complete patch round trip.
The generated ROM is an alpha for testing, not a completed-game release.

On Windows, double-click **Play Barba.cmd**, or run `./tools/launch.ps1`.
It rebuilds the alpha and opens it in Mesen automatically. Keyboard controls:
arrows move, **X** jumps, **Z** attacks, **Enter** is Start, and **Left Shift** is
Select. The launcher uses a separate play profile and persistent saves in
`build/play-saves/`; automated test settings and temporary saves stay separate.

For instant testing checkpoints, double-click **Test Barba.cmd**. **F1-F7** jump
to the castle, combat, all-spells sandbox, lava ledge, lava surface, Barba boss,
and sea crossing. See [the test pack guide](docs/TEST-PACK.md). Test progress uses
a separate Mesen profile and never overwrites your normal play save.

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
