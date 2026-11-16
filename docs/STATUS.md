# Barba Edition status

Current playable alpha. Built locally from `roms/z2.nes` via `python tools/build.py`.

2026-11-15 audit findings resolved: all 9 findings and maintenance items from
[the 2026-11-15 audit](AUDIT-2026-11-15.md) plus the 2026-11-16 town trigger/respawn
follow-up are fixed and verified (ROM SHA-256
`92bfdbacfc66e1ce56902fba20a69b70716b5ae082b35c354fd2b253d855b5dc`), with all 17
unit tests, town/progression checks, and regenerated test-pack checkpoints passing.

2026-11-16: Wyrmling redrawn as a front-facing baby dragon (two flap frames, original
art in `assets/barba.json`). burst, tall_geometry, ending and boot pass; producer
approved the look.

2026-11-16: Overworld dragon redrawn as a mini Barba (croc snout, crest, back spikes,
banded belly, slim coil) in all directions; up/down now have real walk frames
(`front_step`/`back_step`: jaws chomp, neck sways). overworld_side, overworld_fire,
forest_burn_limit, encounter_hazard, gameplay and boot pass; awaiting producer playtest.

## Implemented features

- **Player (24x48 Barba)**: Boss-derived 24x48 side-view poses (`src/tall_player.inc`, `src/tall_layout.inc`), full-body jumps, compact 24px crouch, ceiling folding, partly submerged lava and swamp-water pose (`GEOMETRY` bit 2 via `LAVA_CONTACT` or `$0752`, `tests/swamp_submerge.lua`), 8x16 flying Wyrmling, and 16x16 overworld avatar. Terrain and enemy-contact hitboxes keep native dimensions. CHR allocation reserves `$4E`/`$50` (Ache/bat enemy frames) and `$5E`/`$62` (ending ash) so enemy sprites in caves/forests stay intact, plus `$60` (the XP "3" score digit, also the first digit of "30"; the down pose had overwritten it, 2026-11-15). The budget is full, so `tools/assets.py` reuses any allocated pair within 1 pixel (attack head = idle head, crouch-attack tail = crouch tail), freeing `$5C`. Tall head OAM moved from `$F8` to `$C4` (and town combo OAM `$C4` to `$64`) so Barba no longer clobbers the native HUD magic partial-bar sprite at `$02F8` (verified in `tests/hud_timing.lua`).
- **Attacks & techniques**:
  - Five-shot diagonal volley at all health levels (`src/breath.inc`, `src/extra_fire.inc`) with shared mouth placement, 8-update cadence, `LOAD_LIMIT = 7` governor, native Barba fireball SFX (`$ED |= $40`), and glove-gated brick breaking (`src/blocks.inc`, all palace groups `$0707 >= 3`). Standing post-slash recovery (`$0400 == 4`) with B released re-arms the volley so standing cancel-slashes fire without moving first.
  - Geldarm (West Hyrule sand worm, `$20`) hurtbox (`$E90E`, type 5) widened to `12x64` px (`$FE, $0C, $00, $40`) so standing, crouching, and extra-slot fireballs hit its body as well as its head. HP 8 -> 4 (bank 1 `$9441`; attack 1-2 = 2 hits, 3+ = 1 hit). A lethal hit from any source — including jump stomp in `BarbaStomp` (`src/stomp.inc`) — no longer explodes it at full height: `src/geldarm.inc` (bank-1 pad `$9EB9`, hooks `$9BB5`/`$9C3D`) keeps it alive at HP 0, flashing and immune, sinking into the sand 2 px/frame (~1/2 s), then runs the native death `$E880` at the sand line (`tests/geldarm.lua`).
  - Hidden Red Jars (`enemy $05`, Bank 4 Type A `$B83E`, Bank 4 Type B `$AF61`, Great Palace Bank 5 `$A521`) are hooked via `HiddenJarHit` (`$A7BF` in bank 4, `HiddenJarHit` in bank 5) so ordinary breath (native and extra slots) as well as melee reveals them.
  - Upward breath (airborne `Up+B` column) and rising head-butt (`Up` while ascending), both gated on Upward Thrust; rising head-butt breaks glove-gated overhead bricks via `BarbaBlocks` (`tests/stab_blocks.lua`).
  - Downstab (`Down` while airborne with Downward Thrust) with 64px visual double-torso pose, 18x12 centered foot hitbox (`BarbaSetThrusts`), and glove-gated floor brick breaking via `BarbaBlocks` (`tests/stab_blocks.lua`).
  - Easy-enemy jump stomp (`$C2` 1..16, full-body foot reach `$29 + $22 - $2A,x < $1E`, excluding shielded palace
    enemies `$18..$1A`, `$1F`, `$23`, verified by `tests/stomp.lua`) and touch item pickup (`src/stomp.inc`). No stomps during a boss fight's
    scroll lock (`$0728`): a stomp kill skipped the boss-death handler, so no key dropped (room softlock).
- **Lava & sea crossing**: Palace (`$0707 >= 3`) and outside-palace encounter (`$0707 == 0`) water/lava surface support with normal movement, crouching, jumping, submerged pose (`GEOMETRY` bit 2), and lava-launch boost (`$FA`) (`LavaSurfaceBody` in `src/farcall.inc`, `tests/encounter_hazard.lua`). Town water (`$0707 = 1, 2`) keeps vanilla death; raft route uses dragon sea-crossing sprite.
- **Towns, shouts & combo banner**:
  - Outdoor wandering villagers (`$10..$12`, `$19..$20`) flee at catchable speed, take refuge in open/closed doors, and burn into temporary ash (`src/town.inc`). House-opening villagers (`$13..$18`, including `$17` healer and `$18` magic-house openers) are excluded from `TownEligible` and `TownBurnable` so they stay invulnerable, keep their native `$97D4` door-emerge and `$54` door-opening behavior, talk on `B` (or `Up`) (`TownNativeTalk` at `$9A2C`, tested by `tests/spell_door.lua`), and trigger `$99E6` heal/magic restoration on entering (`$0736 == #$16`, `tests/heal_door.lua`). Single-area non-town and indoor NPCs (`$0A..$20` excluding `$0C`, `$13..$18`, and invisible triggers `$21..$22` such as Saria's Mirror and Nabooru's Water of Life Fountain, across world 1/2 rooms except North Palace `$3C`, via `TownBurnable`) stay put and keep their native/service dialogue on approach, burn into temporary ash on fireball hits, and clear their room-table spawn bit via `jsr $DD3D` in `TownHide` so re-entering repopulates them (`tests/town_nontown_burn.lua`).
  - Burned signs (2026-11-16): scorching a sign board makes it read one of six rotating burned lines until the room reloads (`src/sign.inc`, docs/TOWNS.md "Burned signs", `tests/sign_burn.lua`). Not yet playtested by the producer.
  - Holding `Up` near a fleeing villager triggers fast direct panic dialogue (`src/town_dialogue.inc`, `TownLine` asserted `<= 11` chars so lines stay inside the 14-tile dialogue box border).
  - Floating 7-OAM sprite shouts (`OH SHIT!`, `OH FUCK!`, `RUN!`, `OH NO!`, `OH GOD!`, `HELP!`, `SAVE ME!`, `NO!`, `BARBA!`) in `src/shouts.inc`.
  - Scorchable outdoor town props, buildings & street ground (`src/blocks.inc`) with animated lasting fires (16-slot FIFO ring, tracking `SCORCH_PAGE` against `$4B` so matching screen coordinates on different pages do not alias, 8-frame tongue-swap animation, ~10s flame duration or oldest-eviction to char, cleared on room exit) and Unreal Tournament-style running combo banner (`MULTI KILL!` .. `GODLIKE!` at 12/24/40/60/85 pts) with live `X<pts>` counter in `src/combo.inc`.
  - Sleeping Zelda in North Palace can be scorched with `"OOPS..."` shout.
- **Overworld dragon fire**: Pressing `B` on the overworld breathes an animated 8x16 flame (`$60/$62` in CHR bank 30) with dragon fire SFX (`$ED |= $40`), splits the WRAM RLE map (`BarbaSplitBurnForest`) so only the single facing forest tile (`$06` -> `$04` Desert/Plains) is scorched without affecting neighboring trees across battles/scrolling (while cancelling the PPU plains redraw via `BurnAbort` if `BurnMapEndGuard` refuses a split at the `$7FF0` map-capacity limit), reveals Hidden Kasuto without needing the Hammer, and triggers magic/rumble reactions (`$EC = $04`) when aimed at towns or palaces (`A` keeps Hammer on boulders; `B` plays Flute on Spiders/open ground once owned) (`src/barba.asm`, `tests/overworld_fire.lua`, `tests/forest_burn_limit.lua`).
- **Title, menus, bosses & ending**:
  - `BARBA I / THE ADVENTURE OF / BARBA` title screen with molten lava, animated roaring Barba, and scrolling story; Barba 1-Up dolls across all 13 even sprite banks; dragon spell names (`SCALES`, `JUMP`, `LIFE`, `WYRMLNG`, `METEOR`, `REFLECT`, `SPELL`, `INFERNO`) with native noise-channel Inferno roar, extended decor flash, and 4-wave 4-way firestorm barrage (`BarbaInfernoTick` in `src/breath.inc`, `tests/inferno.lua`); post-flash palette restore (`$16/$27/$30`).
  - **METEOR** (2026-11-15) replaces the Fire spell (slot 4, `$076F` bit 4, lasts like vanilla Fire): mid-air
    `Down + B` dives at 6 px/frame (`$057D = 6`); landing thuds, flashes and sends one flat, fire-class
    floor shockwave each way gated through `BarbaLoadOk` (`METEOR_WAVE` = `$C0` flags, 33 updates like breath). Breath is now always fire class
    (`$05CA = 0`), so Fire-only enemies no longer need a spell; range stays 33 updates. Code lives in reclaimed
    dead vanilla bank-0 code (`$97F1`, `$9847`, `$81C1`; original bytes guarded). `tests/meteor.lua`.
  - Palace 6 boss converted to **Lava Link** (hand-drawn Link head/tunic in CHR 25, Sprite Palette 3, Spear/sword-beam breath, fireball damage).
  - **Dark Barba** ("Dark Link", 24x48 in `src/dark_barba.inc`, sharing `src/tall_layout.inc` directly and enforcing `$0753 = 2` shadow palette on entry) takes 1 HP fireball damage and yields the Triforce-hold pose (`tests/dark_link.lua`).
  - **Boss fireball coverage** (2026-11-15): all six palace bosses die to fireballs alone, with no thrust
    techniques, then drop the key that unlocks the room: `tests/horsehead.lua`, `helmethead.lua`, `rebonack.lua`
    (both phases), `carock.lua`, `gooma.lua`, `lava_link_kill.lua` (shared driver `tests/boss_fight.lua`).
    Carock was immune in vanilla (bank 4 `$B1E9` skips the hit check for `$22`; Reflect only); `CarockHit`
    (bank 4 `$A7B0`) adds the projectile/sword check in his visible window and runs the native boss death on a
    kill (a raw kill drew him into OAM 0 and hung the sprite-0 wait). Dark Link: `tests/dark_link.lua`.
    Thunderbird keeps vanilla's rule (producer decision, 2026-11-15): immune until Inferno, then fireballs
    hurt it; `ThunderHit` (`$922A` hook in `src/barba.asm`) preserves Thunderbird's boss-death state (`$6E3F = $FF`) even when a second Inferno deals lethal native Thunder damage so the Key drops cleanly.
    Verified by one-off probes (2026-11-15): downstab on mounted Rebonack (unhorses `$20` into `$0A`) and Reflect vs Carock (reflected beams damage and kill `$22`).
  - **Ending sequence**: 24x48 Barba beside woken Zelda, custom wake-up dialogue, curtain-fall behind-curtain fireball toast finale turning Zelda to ash, 20-entry credits, and New Game+ (`$07A0 = 1`).

- **Boss checkpoint set** (2026-11-15): `play/Test Barba - Bosses.cmd` maps F1-F8 to the left edge of every boss room (Horsehead through Dark Link) with route-appropriate loadouts; all 8 reload-validated (`docs/TEST-PACK.md`).

## Performance & bank headroom

- `BarbaDisplay` fast path + `BarbaGeometry` terrain cache + `BarbaExtraUpdate` fast path + tightened `ExtraNearEnemy` + direct `BarbaExtraBlocks` + `BarbaLoadOk` 2-shot cap with `>= 2` enemies + odd-frame OAM priority rotation: Palace 1 `perf_volley.lua` achieves **0/900 lag frames** (idle avg 15,862 / peak 16,086 cycles; volley avg 19,373 / peak 25,533 cycles, 0 near-budget >27k frames). `perf_meteor.lua` passes with **0/900 lag** (`17,353` avg / `19,142` peak, `slams=10 wavesPlaced=2`), and the six-Bot METEOR + volley stress probe (`build/audit_perf_meteor_six.lua`) now achieves **0/900 lag** (`maxLiveShots = 1`, peak `28,983` cycles, down from `160/900` lag). Palace 3 room `$0D` (2 Ironknuckles + breakable blocks) previously measured **25,338 avg / 28,155 peak (0 lag frames)**, down from 28,095 avg / 30,049+ peak (4 lag frames).
- `FarCall0` cold-hook ABI in fixed bank 7 (`src/farcall.inc`) keeps fixed-bank padding free without hot-path bank-switch overhead.

## Final end-to-end review (2026-11-16)

These checks found no progression blocker and no bank or WRAM fault:

- the full suite, including `tests/death_continue.lua`
- a static cross-bank scan of the source and hooks
- a WRAM write-watch
- a death and game over → continue probe
- a check of the flute gates (Palace 6 call spot and River Devil)

Two cosmetic P3 limits are logged in [AUDIT-2026-11-15.md](AUDIT-2026-11-15.md#final-end-to-end-review-2026-11-16-rom-92bfdbac-unchanged): leftover fire for under 1 s after a respawn, and the scorch ring keyed only on room number.

## Remaining / open items

- Full end-to-end human playthrough across all palaces, spell unlocks, item gates, and ending.
- METEOR (2026-11-15, awaiting producer playtest): magic cost still uses vanilla Fire's table (`$8D9B`);
  slams are unlimited while the spell lasts. Retune after the feel check.
- Trailing torso (shelved 2026-11-15): the producer liked a lagged 16x16 segment behind the lower body (OAM `$20/$24`,
  Y from an 8-entry ring of past actor Y) "with minor adjustments", but reverted it for cost: +190 cycles/frame,
  volley over-8 frames 34 -> 224 of 900, Rebonack bot fight lag 28 -> 60. Patch (renderer compaction that frees
  ~250 bank-0 bytes, trail, test updates): `docs/archive/trailing-torso-prototype.patch`.
- Cross-check on a second accurate NES emulator / hardware-accurate MMC1 behavior.
- Audio listening pass on Inferno roar vs. music and transitions.
- Fireball range (producer decision pending, 2026-11-15): an uncommitted change raised volley lifetime from 33 to 63
  updates (64 px -> 124 px). Reverted before commit because the fireball-only Rebonack fight (`tests/rebonack.lua`)
  never finished: long-lived misses hold the 2-live-shot cap, so fire rate collapses. Longer range needs a fire-rate
  or cap rethink first. `VOLLEY_LIFE` in `src/breath.inc` is the knob.
- Fixed 2026-11-14: Fat Woman/River Guard/Knight/indoor-NPC villagers drew combo digits and flame art
  (glyphs and fire tiles sat on bank-7 villager sprite pairs).
- Fixed 2026-11-15:
  - Town pause menu burnt icons: moved town fire char tiles off `$96/$B9` to unused bank-7 tiles `$35/$C2` (enforced by `tests/shout_follow.lua`).
  - Town double-door visual bug: hooked native door entry (`$98AB`) to `TownDoorCoords` / `TownDoorEmerged` (`src/town.inc`) so calm/non-panicked villagers derive the door's exact column and page from `$DC/$DD` instead of `$4E,x + L9780,y` (which drew a duplicate closed door one column left of the real doorway), while house-openers emerging from inside (`L97F5`, `$AF=$81`) recover their doorway from `($4E,x - L9740,y)` and `$3C,x` because `LEA32` runs while `$4E,x` is offset (`tests/spell_door.lua`).
  - Magic container/town item sprite (`$83`) overlap: moved shout glyph `H` from bank-7 `$83` to unused bank-6 pair `$7C`.
  - Spell-teaching Wise Man frame (`$62/$64`, bank 6) overlap: moved town `ASH_TILES` from `$64/$66` to unused bank-6 pairs `$7E/$80` and guarded `$62/$64` in `TOWN_SPRITE_PAIRS`.
  - Overworld forest-burn overflow: each burned tree grows the WRAM RLE map (`$7C00..`, ends near `$7F20`) by up to
    2 bytes, so roughly 110-220 burns in one region would have shifted map bytes past `$7FFF` into MMC1 registers
    (crash/corruption; West Hyrule has 359 forest tiles). `BurnMapEndGuard` (bank 0 pad `$BFE0`) refuses splits once
    the map end reaches `$7FF0`; `BurnAbort` cancels the queued plains redraw so the tree stays visually and logically (`tests/forest_burn_limit.lua`).
  - Spell-house door softlock: excluded `$13..$18` house-openers from `TownEligible` and `TownBurnable` and hooked `$9A2C` (`TownNativeTalk`) + `TownUpdate` to talk on `B` (or `Up`) (`tests/spell_door.lua`).
  - Audit fixes (`AUDIT-2026-11-15.md`): `ThunderHit` prevents lethal Inferno softlock on exposed Thunderbird; `BarbaLoadOk` gates `BarbaFireSpell` and `MeteorEmit` (0/900 lag under 6-Bot METEOR stress); `DarkBarbaTiles` includes `src/tall_layout.inc` directly with `$0753 = 2` shadow palette; `HiddenJarHit` allows breath to reveal hidden red jars across banks 4/5; `BarbaTownBurn` compares `SCORCH_PAGE`; `BarbaStomp` routes Geldarm stomp kills through its sinking death (`tests/geldarm.lua`); Bosses F7 (`$35`) / Core F10 (`$35`) / Bosses F8 / `assets.py` metadata / test exit-status propagation (`dark_link`, `ending`, `link_boss`, `title_roar`, `perf_volley`, `perf_meteor`) fixed.
- Fixed 2026-11-16: Phantom closed door in open street (producer screenshot). Hidden house-openers (`$13..$18`, `$AF = $80`) decided to emerge from `$C9`/`$CD`, which belong to whichever actor drew last, so one could emerge while its doorway was pages away; its door macro then wrote into nametable (page & 1) over the visible street. `TownOpenerGate` (`src/town.inc`, placed in BANK3_SIGN) now also requires Barba to be within 96 px of the opener (16-bit) before native `$97D4` runs. Repro pre-fix: emerged at 223 px; post-fix 95 px (`tests/opener_far.lua`). Not yet playtested by the producer.

Historical design notes and completed implementation plans are archived in [docs/archive/](archive/).
