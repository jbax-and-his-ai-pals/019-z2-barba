# Zelda II — Barba Edition

A work-in-progress NES ROM hack that makes Barba the playable protagonist in
*Zelda II: The Adventure of Link*.

The design uses a compact serpentine dragon, preserves the original progression,
and targets an ordinary MMC1 cartridge with NES-native audio.

## Development alpha

The local build currently includes:

- Thin, boss-derived 24x48 side-view Barba with full-body jumps, a compact crouched neck, jaw animation and ceiling folding,
  an 8x16 flying wyrmling,
  and a dedicated 16x16 overworld avatar with directional animation.
- Evenly spaced five-shot downward-diagonal volleys at every health level, with
  glove-gated brick breaking, upward breath / rising head-butt (Upward Thrust),
  downstab (Downward Thrust), and weak-enemy stomp. Fire empowers projectile damage
  against Fire-only enemies.
- Outdoor villagers flee at a catchable speed, vanish at existing doors, or burn into temporary ash piles
  when hit, with floating panic shouts, scorchable town props, and a rampage combo banner.
  Indoor and story-critical NPCs are protected. Hold Up near a wanderer for faster direct dialogue.
- Palace lava surface support with partly submerged lava pose and normal movement/jumping. Water outside
  palaces retains its original death behavior.
- Custom title screen (`BARBA I`), 1-Up dolls, dragon spell names with Inferno roar,
  Palace 6 "Lava Link" boss, Dark Barba encounter, and custom ending sequence.

The tall head is visual: terrain and enemy contact retain the native collision
body. Crouching fits the original low lane; stone ceilings fold the head down.

**Playable alpha.** Full-game playthrough and second-emulator cross-checking remain.
See [status and verification](docs/STATUS.md) for details.

## Development

The source ROM belongs at `roms/z2.nes`. It is never modified in place.
ROMs, extracted game assets, emulator saves, and downloaded tools are excluded
from this repository. Build outputs and patches are generated locally.

```powershell
.\tools\bootstrap.ps1 -WithEmulator
python tools/build.py
```

Open `play/barba.nes` (also written to `build/barba.nes`) in a standard NES emulator. `play/barba.bps` is the
source-specific patch; the build validates a complete patch round trip.
The generated ROM is an alpha for testing, not a completed-game release.

On Windows, double-click **play/Play Barba.cmd**, or run `./tools/launch.ps1`.
It rebuilds the alpha and opens it in Mesen at 4× windowed scale. The arrows move,
**X** jumps, **Z** attacks, **Enter** is Start, and **Space** is Select.
The launcher uses a separate play profile and persistent saves in
`build/play-saves/`; automated test settings and temporary saves stay separate.

For instant testing checkpoints, double-click **play/Test Barba.cmd**. **F1-F9** jump
to the castle, combat, all-spells sandbox, lava ledge, lava surface, Barba boss,
sea crossing, and a Rauru town street. See [the test pack guide](docs/TEST-PACK.md). Test progress uses
a separate Mesen profile and never overwrites your normal play save.

See [status](docs/STATUS.md), [build instructions](docs/BUILD.md),
[town reactions](docs/TOWNS.md), [research notes](docs/RESEARCH.md), and
[archived design docs](docs/archive/).

This is an unofficial fan project. Zelda II and its original characters,
graphics, music, and game data belong to their respective owners.

## Credits

Research references include Trax's Zelda II disassembly and the
[FiendsOfTheElements buildable version](https://github.com/FiendsOfTheElements/z2disassembly),
the [NESdev documentation](https://www.nesdev.org/wiki/Nesdev_Wiki),
[cc65](https://cc65.github.io/), and [Mesen](https://github.com/SourMesen/Mesen2).
Original game code and graphics are obtained only from the user's local ROM.
