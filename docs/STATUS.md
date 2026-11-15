# Barba Edition status

Current playable alpha. Built locally from `roms/z2.nes` via `python tools/build.py`.

## Implemented features

- **Player (24x48 Barba)**: Boss-derived 24x48 side-view poses (`src/tall_player.inc`, `src/tall_layout.inc`), full-body jumps, compact 24px crouch, ceiling folding, partly submerged lava pose (`GEOMETRY` bit 2), 8x16 flying Wyrmling, and 16x16 overworld avatar. Terrain and enemy-contact hitboxes keep native dimensions. CHR allocation reserves `$4E`/`$50` (Ache/bat enemy frames) and `$5E`/`$62` (ending ash) so enemy sprites in caves/forests stay intact.
- **Attacks & techniques**:
  - Five-shot diagonal volley at all health levels (`src/breath.inc`, `src/extra_fire.inc`) with shared mouth placement, 8-update cadence, `LOAD_LIMIT = 7` governor, native Barba fireball SFX (`$ED |= $40`), and glove-gated brick breaking (`src/blocks.inc`). Standing post-slash recovery (`$0400 == 4`) with B released re-arms the volley so standing cancel-slashes fire without moving first.
  - Upward breath (airborne `Up+B` column) and rising head-butt (`Up` while ascending), both gated on Upward Thrust.
  - Downstab (`Down` while airborne with Downward Thrust) with 64px visual double-torso pose and 18x12 centered foot hitbox (`BarbaSetThrusts`).
  - Weak-enemy stomp (`$C2` 1..4) and touch item pickup (`src/stomp.inc`). No stomps during a boss fight's
    scroll lock (`$0728`): a stomp kill skipped the boss-death handler, so no key dropped (room softlock).
- **Lava & sea crossing**: Palace lava surface support with normal movement, jumping, and lava-launch boost (`$FA`). Water outside palaces keeps vanilla death; raft route uses dragon sea-crossing sprite.
- **Towns, shouts & combo banner**:
  - Outdoor villagers (`$10..$20`, including stationary outdoor villagers `$10..$12`) flee at catchable speed, take refuge in open/closed doors, and burn into temporary ash (`src/town.inc`). Native `$13..$18` house-openers hidden inside closed doors (`$AF = $80`, `Y = $A8`) stay hidden instead of popping out fleeing at `Y = $A8`, and `TownFlee` steps any `Y < $B0` villager down to street level (`$B0`). Single-area non-town and indoor NPCs (`$0A..$21` excluding `$0C`, across world 1/2 rooms except North Palace `$3C`, via `TownBurnable`) stay put and keep their native/service dialogue on approach, but also burn into temporary ash on fireball hits (`tests/town_nontown_burn.lua`).
  - Holding `Up` near a fleeing villager triggers fast direct panic dialogue (`src/town_dialogue.inc`).
  - Floating 7-OAM sprite shouts (`OH SHIT!`, `OH FUCK!`, `RUN!`, `OH NO!`, `OH GOD!`, `HELP!`, `SAVE ME!`, `NO!`, `BARBA!`) in `src/shouts.inc`.
  - Scorchable outdoor town props, buildings & street ground (`src/blocks.inc`) with animated lasting fires (16-slot FIFO ring, 8-frame tongue-swap animation, ~10s flame duration or oldest-eviction to char, cleared on room exit) and Unreal Tournament-style running combo banner (`MULTI KILL!` .. `GODLIKE!` at 12/24/40/60/85 pts) with live `X<pts>` counter in `src/combo.inc`.
  - Sleeping Zelda in North Palace can be scorched with `"OOPS..."` shout.
- **Overworld dragon fire**: Pressing `B` on the overworld breathes an animated 8x16 flame (`$60/$62` in CHR bank 30) with dragon fire SFX (`$ED |= $40`), splits the WRAM RLE map (`BarbaSplitBurnForest`) so only the single facing forest tile (`$06` -> `$04` Desert/Plains) is scorched without affecting neighboring trees across battles/scrolling, reveals Hidden Kasuto without needing the Hammer, and triggers magic/rumble reactions (`$EC = $04`) when aimed at towns or palaces (`A` keeps Hammer on boulders; `B` plays Flute on Spiders/open ground once owned) (`src/barba.asm`, `tests/overworld_fire.lua`).
- **Title, menus, bosses & ending**:
  - `BARBA I / THE ADVENTURE OF / BARBA` title screen with molten lava, animated roaring Barba, and scrolling story; Barba 1-Up dolls across all 13 even sprite banks; dragon spell names (`SCALES`, `JUMP`, `LIFE`, `WYRMLNG`, `FIRE`, `REFLECT`, `SPELL`, `INFERNO`) with native noise-channel Inferno roar, extended decor flash, and 4-wave 4-way firestorm barrage (`BarbaInfernoTick` in `src/breath.inc`, `tests/inferno.lua`); post-flash palette restore (`$16/$27/$30`).
  - Palace 6 boss converted to **Lava Link** (hand-drawn Link head/tunic in CHR 25, Sprite Palette 3, Spear/sword-beam breath, fireball damage).
  - **Dark Barba** ("Dark Link", 24x48 in `src/dark_barba.inc`) takes 1 HP fireball damage and yields the Triforce-hold pose.
  - **Boss fireball coverage** (2026-11-15): all six palace bosses die to fireballs alone, with no thrust
    techniques, then drop the key that unlocks the room: `tests/horsehead.lua`, `helmethead.lua`, `rebonack.lua`
    (both phases), `carock.lua`, `gooma.lua`, `lava_link_kill.lua` (shared driver `tests/boss_fight.lua`).
    Carock was immune in vanilla (bank 4 `$B1E9` skips the hit check for `$22`; Reflect only); `CarockHit`
    (bank 4 `$A7B0`) adds the projectile/sword check in his visible window and runs the native boss death on a
    kill (a raw kill drew him into OAM 0 and hung the sprite-0 wait). Dark Link: `tests/dark_link.lua`.
    Thunderbird keeps vanilla's rule (producer decision, 2026-11-15): immune until Inferno, then fireballs
    hurt it (probe, not a checked-in test).
    Verified by one-off probes (2026-11-15): downstab on mounted Rebonack (unhorses `$20` into `$0A`) and Reflect vs Carock (reflected beams damage and kill `$22`).
  - **Ending sequence**: 24x48 Barba beside woken Zelda, custom wake-up dialogue, curtain-fall behind-curtain fireball toast finale turning Zelda to ash, 20-entry credits, and New Game+ (`$07A0 = 1`).

## Performance & bank headroom

- `BarbaDisplay` fast path + `BarbaGeometry` terrain cache + `BarbaExtraUpdate` fast path + tightened `ExtraNearEnemy` + direct `BarbaExtraBlocks` + `BarbaLoadOk` 2-shot cap with `>= 2` enemies + odd-frame OAM priority rotation: Palace 1 `perf_volley.lua` achieves **0/900 lag frames** (idle avg 15,769 / peak 15,993 cycles; volley avg 18,890 / peak 24,992 cycles, 0 near-budget >27k frames). Palace 3 room `$0D` (2 Ironknuckles + breakable blocks) drops from 28,095 avg / 30,049+ peak (4 lag frames) to **25,338 avg / 28,155 peak (0 lag frames)**.
- `FarCall0` cold-hook ABI in fixed bank 7 (`src/farcall.inc`) keeps fixed-bank padding free without hot-path bank-switch overhead.

## Remaining / open items

- Full end-to-end human playthrough across all palaces, spell unlocks, item gates, and ending.
- Cross-check on a second accurate NES emulator / hardware-accurate MMC1 behavior.
- Audio listening pass on Inferno roar vs. music and transitions.
- Fixed 2026-11-14: Fat Woman/River Guard/Knight/indoor-NPC villagers drew combo digits and flame art
  (glyphs and fire tiles sat on bank-7 villager sprite pairs).
- Fixed 2026-11-15:
  - Town pause menu burnt icons: moved town fire char tiles off `$96/$B9` to unused bank-7 tiles `$35/$C2` (enforced by `tests/shout_follow.lua`).
  - Magic container/town item sprite (`$83`) overlap: moved shout glyph `H` from bank-7 `$83` to unused bank-6 pair `$7C`.
  - Spell-teaching Wise Man frame (`$62/$64`, bank 6) overlap: moved town `ASH_TILES` from `$64/$66` to unused bank-6 pairs `$7E/$80` and guarded `$62/$64` in `TOWN_SPRITE_PAIRS`.

Historical design notes and completed implementation plans are archived in [docs/archive/](archive/).
