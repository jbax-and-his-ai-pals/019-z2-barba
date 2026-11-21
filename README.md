# Zelda II — Barba Edition

Play as Barba, the dragon from Palace 6, in *Zelda II: The Adventure of Link*.
Hyrule's map, palace order, item gates, and much of the original soundtrack
remain familiar. Fire breath, dragon techniques, and new village reactions
change how you play.

## Current development build

- **Dragon movement and combat.** The 24×48 Barba crouches, folds his head
  under low ceilings, stomps weak enemies, and fires five-shot diagonal volleys.
  In the air, Up+B breathes upward and Up triggers the rising head-butt
  after learning Upward Thrust. Down triggers the downstab after learning
  Downward Thrust. Fireballs break glove-gated blocks and reveal hidden red jars.
  The Fairy spell becomes the flying Wyrmling form.
- **Exploration.** Barba can wade and jump in palace and encounter liquids.
  Town hazards remain lethal, including the quicksand under Saria's bridges.
  On the overworld, breath can burn individual forest tiles and reveal Hidden
  Kasuto. Clouds drift, grass sways, and water and lava ripple.
- **Town reactions.** Villagers may flee, hide, or turn to ash. Fire can scorch
  buildings, ground, and signs. Floating panic shouts and a rampage counter
  track the commotion. Hold Up near a wanderer for direct dialogue.
- **Spells and bosses.** SCALES shields Barba. With METEOR active, Down+B
  dives from midair and sends out floor shockwaves. INFERNO sends out four
  waves of fire. All six palace
  bosses can be beaten with breath. Link takes Barba's place in Palace 6,
  and Dark Barba waits in the Great Palace.
- **Presentation.** The development build adds a sampled roar, raised-head
  item and victory celebrations, a revised Game Over screen and laugh
  sequence, a reworked title, and a custom ending.

Some dialogue contains strong profanity.

## Patching and compatibility

Apply the BPS for your version to a clean, headered USA PRG0 Zelda II ROM
(Mapper 1 / MMC1). The source SHA-256 is
`ad8c0fbcf092bf84b48e69fd3964eea4ed91bfe62abc352943d537979782680c`.

The **v1.05 tag** identifies the earlier MMC1 release. The **current development
build** produces a different format: NES 2.0 Mapper 176 (FK23C), with a
playable *Where's Barba?* crossover hidden in Rauru. Use Mesen 2.1.1 for the
combined build. See [current verification and open issues](docs/STATUS.md).

## Build and playtest

Place the source ROMs in `roms/z2.nes` and `roms/waldo.nes`, and the local
roar sample in `roms/roar.wav`. The source files are read locally. The
[build guide](docs/BUILD.md) lists input checksums, audio options, and outputs.

```powershell
.\tools\bootstrap.ps1 -WithEmulator
python tools/build.py
```

The build writes `barba.nes` and `barba.bps` to both `build/` and `play/`.
On Windows, **play/Play Barba.cmd** rebuilds and opens the ROM in Mesen.
Arrows move, **X** jumps, **Z** attacks, **Enter** starts or pauses, and
**Space** selects or casts. Normal play saves use `build/play-saves/`.
Run `./tools/launch.ps1 -NoRebuild` to open an existing playable artifact.

**play/Test Barba.cmd** gives you Core checkpoints on **F1–F10**, from the
starting castle through the Great Palace approach. The other launchers
cover bosses, towns, scenery, item and gem celebrations, and Game Over.
Each set has an isolated Mesen profile. See the [checkpoint guide](docs/TEST-PACK.md)
for the key map and the crossover shortcuts.

## Project notes and credits

See [combat and geometry](docs/BREATH-IMPLEMENTATION.md),
[town behavior](docs/TOWNS.md), [research notes](docs/RESEARCH.md), and the
[archived changelog](docs/archive/CHANGELOG.md).

AI assisted with the 6502 assembly, Python build and asset tools, emulator
tests, and new visual assets under human direction and playtesting. Most
character and scenery art is built from tiles extracted from the local
Zelda II ROM. The repository tracks the build recipes and authored assets.

Research and tooling credits include Trax's Zelda II disassembly, the
[FiendsOfTheElements buildable fork](https://github.com/FiendsOfTheElements/z2disassembly),
[NESdev](https://www.nesdev.org/wiki/Nesdev_Wiki), [cc65](https://cc65.github.io/),
and [Mesen](https://github.com/SourMesen/Mesen2).

This is an unofficial fan project. The original games and their characters,
graphics, music, and game data belong to their respective owners.
