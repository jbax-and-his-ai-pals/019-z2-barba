# Barba Edition status

Current playable alpha. Built locally from `roms/z2.nes` via `python tools/build.py`.

## Implemented features

- **Player (24x48 Barba)**: Boss-derived 24x48 side-view poses (`src/tall_player.inc`, `src/tall_layout.inc`), full-body jumps, compact 24px crouch, ceiling folding, partly submerged lava pose (`GEOMETRY` bit 2), 8x16 flying Wyrmling, and 16x16 overworld avatar. Terrain and enemy-contact hitboxes keep native dimensions.
- **Attacks & techniques**:
  - Five-shot diagonal volley at all health levels (`src/breath.inc`, `src/extra_fire.inc`) with shared mouth placement, 8-update cadence, `LOAD_LIMIT = 7` governor, native Barba fireball SFX (`$ED |= $40`), and glove-gated brick breaking (`src/blocks.inc`).
  - Upward breath (airborne `Up+B` column) and rising head-butt (`Up` while ascending), both gated on Upward Thrust.
  - Downstab (`Down` while airborne with Downward Thrust) with 64px visual double-torso pose and 18x12 centered foot hitbox (`BarbaSetThrusts`).
  - Weak-enemy stomp (`$C2` 1..4) and touch item pickup (`src/stomp.inc`).
- **Lava & sea crossing**: Palace lava surface support with normal movement, jumping, and lava-launch boost (`$FA`). Water outside palaces keeps vanilla death; raft route uses dragon sea-crossing sprite.
- **Towns, shouts & combo banner**:
  - Outdoor villagers (`$10..$20`, including stationary outdoor villagers `$10..$12`) flee at catchable speed, take refuge in open/closed doors, and burn into temporary ash (`src/town.inc`). Indoor and story-critical NPCs (`$0D..$0F`) remain protected.
  - Holding `Up` near a fleeing villager triggers fast direct panic dialogue (`src/town_dialogue.inc`).
  - Floating 7-OAM sprite shouts (`OH SHIT!`, `OH FUCK!`, `RUN!`, `OH NO!`, `OH GOD!`, `HELP!`, `SAVE ME!`, `NO!`, `BARBA!`) in `src/shouts.inc`.
  - Scorchable outdoor town props & buildings (`src/blocks.inc`) and Unreal Tournament-style running combo banner (`DOUBLE KILL!` .. `GODLIKE!`) in `src/combo.inc`.
  - Sleeping Zelda in North Palace can be scorched with `"OOPS..."` shout.
- **Title, menus, bosses & ending**:
  - `BARBA I / THE ADVENTURE OF / BARBA` title screen with molten lava, animated roaring Barba, and scrolling story; Barba 1-Up dolls across all 13 even sprite banks; dragon spell names (`SCALES`, `JUMP`, `LIFE`, `WYRMLNG`, `FIRE`, `REFLECT`, `SPELL`, `INFERNO`) with native noise-channel Inferno roar; post-flash palette restore (`$16/$27/$30`).
  - Palace 6 boss converted to **Lava Link** (hand-drawn Link head/tunic in CHR 25, Sprite Palette 3, Spear/sword-beam breath, fireball damage).
  - **Dark Barba** ("Dark Link", 24x48 in `src/dark_barba.inc`) takes 1 HP fireball damage and yields the Triforce-hold pose.
  - **Ending sequence**: 24x48 Barba beside woken Zelda, custom wake-up dialogue, curtain-fall behind-curtain fireball toast finale turning Zelda to ash, 20-entry credits, and New Game+ (`$07A0 = 1`).

## Performance & bank headroom

- `BarbaDisplay` fast path + `BarbaGeometry` terrain cache + `BarbaExtraUpdate` fast path + tightened `ExtraNearEnemy` + odd-frame OAM priority rotation: Palace 1 `perf_volley.lua` achieves **0/900 lag frames** (idle avg 15,638 / peak 15,867 cycles; volley avg 19,820 / peak 28,411 cycles).
- `FarCall0` cold-hook ABI in fixed bank 7 (`src/farcall.inc`) keeps fixed-bank padding free without hot-path bank-switch overhead.

## Remaining / open items

- Full end-to-end human playthrough across all palaces, spell unlocks, item gates, and ending.
- Cross-check on a second accurate NES emulator / hardware-accurate MMC1 behavior.
- Audio listening pass on Inferno roar vs. music and transitions.

Historical design notes and completed implementation plans are archived in [docs/archive/](archive/).
