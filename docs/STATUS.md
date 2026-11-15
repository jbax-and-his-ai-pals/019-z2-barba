# Development alpha status

This is an initial playable implementation, not a completed total conversion.

## Town rampage combo banner (2026-11-14)

- `src/combo.inc` (PRG bank 6 `$BA00`, called from `BarbaShouts` via `SwapToBank6` in `LAVA` and `jmp $FFC5`) implements an Unreal Tournament-style running combo banner in towns (`DOUBLE KILL!`, `MULTI KILL!`, `MEGA KILL!`, `ULTRA KILL!`, `MONSTER KILL!`, `GODLIKE!`).
- Weighted scoring: igniting an eligible villager (`src/town.inc`) adds `+3` to `COMBO_ADD`; scorching a fresh building metatile (`src/blocks.inc`) adds `+1`. Tiers unlock every 3 points starting at 6 (`DOUBLE KILL!` .. `GODLIKE!` at 21+), with a 180-frame (~3.0s) decay timer, 45-frame low-timer blink warning, and clean hiding on pause/dialogue/scene change.
- Higher tiers escalate in width (8 → 9 → 10 px letter spacing), palette (pale `$02` → fire `$01` → `$01`/`$02` strobe), slam-in/shake (`±1`/`±2 px`), tier-up SFX (`$ED |= $10`), and two flanking animated flame sprites (`$84`) on `GODLIKE!`.
- `tests/town_combo.lua`, `tests/shouts.lua`, `tests/shout_follow.lua`, `tests/town.lua`, `tests/town_fire.lua`, `tests/castle_zelda_burn.lua`, and `tests/farcall.lua` all PASS.

## Dark Barba 24x48 height & Triforce-hold pose (2026-11-14)

- `src/dark_barba.inc` (`BANK5` `$BDE0`, hooked from bank 5 `$9A7F`) draws Dark Barba ("Dark Link") at full 24x48 Barba height (`$026C/$0270/$0274` top row at `$2A - $10`, `$0250..$0264` torso and base) using `DarkBarbaTiles`, matching Barba's height while preserving `LEC02` sword hitboxes and slash OAM (`$0268`).
- `DarkBarbaTriforcePose` (hooked at bank 5 `$9BB1`) sets `$80 = $08` (48px looking-up Barba) instead of `$0B` (the crouched death slot) and raises the Triforce sprites (`$0208,y`/`$020C,y` via `$91`) by 16px above Barba's head while keeping the old man on the floor.
- `tests/dark_link.lua` and `tests/ending.lua` both PASS.

## Downstab second torso chunk (2026-11-14)

- `src/tall_player.inc` (`BarbaDisplay`, `@done_draw`) now draws a second 16x16 torso chunk (`$06/$08`) at `DRAW_TOP - $10` during downstab (`DRAW_FRAME == $51`) using the unused native sword/shield OAM slots (`$0220/$0224`), giving Barba two torso chunks above the turned-down head (64px visual height).
- Clipped against the HUD (`Y < $20`), screen bottom/wrap (`Y >= $F0`), horizontal screen edges, and ceiling/lava tuck (`GEOMETRY & $06`); collision, hurtbox, and `BarbaSetThrusts` foot hitbox (`$0480`) are unchanged.
- Freed 44 unused table bytes in `src/tall_player.inc` (`HeadProbeX`, `HeadProbeY`, `TallOam`, `TallMirror`, `TallColumn`, `TallRow`) so `BANK0` fits cleanly.
- `tests/routines.lua`, `tests/tall_geometry.lua`, `tests/upstab.lua`, `tests/gameplay.lua`, `tests/projectile_only.lua`, and `tests/perf_volley.lua` all PASS.

## Lava Link palette fix (2026-11-14)

- Moved Palace 6 "Lava Link" (`bank4` `$A9F6`: `$4E` -> `$CE`), sword beams (`$AABB`: `01` -> `03`), and the boss palette packet (`$A78E`: `$3F15` -> `$3F1D`) from Sprite Palette 1 to **Sprite Palette 3**.
- Keeps Sprite Palette 1 (`16 27 30`) intact for the boss health bar, Barba's partial LIFE bar, and Barba's fireballs instead of turning them olive/green during the fight. `tests/link_boss.lua` PASS (including fireball damage and Link hurt SFX).

## Stationary outdoor villagers flee & burn (2026-11-14)

- `src/town.inc` (`TownEligible`, `TownUpdate`) and `tools/build.py` (bank 3 `$94AD`, `$94AF`, `$94B1` routine pointers) now include stationary outdoor villagers `$10..$12` (e.g., Saria's old man with a cane and Ruto's stationary hint-givers) in panic fleeing, shouting, doorway refuge, and fireball burning/ash, while keeping story-critical NPCs (`$0D..$0F`, including Wise Man `$0F`), invisible triggers (`$0C`, `$21`, `$22`), and all indoor actors protected.
- Fixed `BarbaExtraReset` in `src/extra_fire.inc` (`lda #$00` inside the clear loop) so entering a town or room no longer leaves `$10` in `$6410/$6419`, which previously drew a stray fireball over OAM `$00` (Sprite 0) and risked hanging `$B082` waiting for Sprite 0 hit.
- `tests/town_safety.lua`, `tests/town.lua`, `tests/shouts.lua`, `tests/shout_follow.lua`, `tests/dialogue_speed.lua`, `tests/doors.lua`, and `tests/town_fire.lua` all PASS.

## Ending sequence & 1-Up Barba doll (2026-11-14)

- `tools/build.py` converts the ending sequence in PRG bank 5: replaces the half-Barba/half-Link chimera (`$8D8D`, `$8C0D`, `$8C38`, `$8DD5` -> `$8B31`) with full 24x48 Barba (`$0210..$022F`) standing beside woken Zelda (`$0230..$023F`), skips `$3F10` palette clobbering in `L8CE3` so Barba never turns into a red silhouette during the awakening flash, keeps Barba and Zelda in place (`$8F6E`), and adds the curtain-fall toast finale (`$8CEB..$8D4B`, `$8F6F..$8F8C`): when the curtain reaches `$22A0`, Barba fires a behind-curtain fireball (`$32`, attr `$20`) that drops below the curtain into view right before hitting Zelda and turning her into a pile of ash (`$5E/$62` in CHR bank 2). Adds a shaded `?` glyph in CHR bank 15 tile `$0F`, updates Zelda's wake-up dialogue (`$BDA1`, 4x15 at `$2184`: `BARBA? / HOLY SHIT! / THE FUCK ARE / YOU DOING HERE?`), and expands the credits (`$9259..$93FF`, `$9176`, `$9197`) to 20 entries including `BARBA EDITION / JERBTRUNDLES` and `LAVA RECLAIMED. / PUSH START TO REPLAY`.
- `tools/build.py` replaces the side-view 1-Up Link doll (`$A8/$A9`) across all 13 even CHR banks (`0, 2, ..., 24`) with Barba's 8x16 doll (`compile_file_select_doll`).
- `tests/ending.lua` PASS (24x48 Barba OAM, woken Zelda OAM, zero Link tiles `$E0-$E6`, Barba stays in place, curtain fireball `$32` attr `$20` drops below curtain, Zelda turns to ash `$5E/$62`, 20-entry credits, New Game+ `$07A0 == 1`).

## Dark Link fireball damage (2026-11-14)

- `src/extra_fire.inc` (`DarkLinkFireCheck` / `DarkLinkHitBox`) and `src/barba.asm` (`BarbaUpdate`) now check all five fireball slots (native `$8D/$8E` and backed `EXTRA_BASE` records) against Dark Link (`$0707=5`, `$A1=$23`, `$63=3`) and apply the exact 1-HP sword-strike response from bank 5 `$9A8D` (`DEC $C2`, `$0509=$38`, `$050D=$18`/`$FF`, `$DC91` knockback, `$057E=$FD`, `$E9=1`).
- `tests/dark_link.lua` PASS (8 hits, `maxDelta=1`, hurt state, death state, victory phase `$63>=4`).

The current player uses boss-derived 24x48 poses, a shared mouth position and a
five-shot diagonal volley at all health levels. Terrain and enemy-contact collision retain the
native body: the raised head is visual, not a newly enlarged hurtbox. Solid
ceilings fold the head into the original 32px height; crouch draws a 24px compact body over the native 16px physical lane.
The body now keeps the boss's narrow neck silhouette without the added belly
coil. Full-body jump rendering is checked during ascent and descent; grounded
crouching retains a short neck beneath the head.

## North Palace sleeping princess burn & shout

- `src/blocks.inc` (`BarbaBlocks`/`BarbaBlockSlot`/`BarbaTownBurn`) now scorches
  sleeping Zelda (`$4E`/`$4F`) in North Palace (`$0707=0, $0706=0, $0561=0`)
  into 2x2 flame and char in CHR bank 3 (`$56..$5D`, hash-guarded zero tiles).
- `src/shouts.inc` (`CastleZeldaShout`) triggers `"OOPS..."` (`SHOUT_WORD = 10`,
  `SHOUT_SLOT = $FF`, OAM `$28..$38`, CHR bank 3 odd tiles `$5F..$65`) above
  Barba when Zelda is ignited. `tests/castle_zelda_burn.lua` PASS.

## Playthrough checkpoint sets (2026-11-14)

Core keeps its existing F1-F10 fixtures. Four selectable local sets add ten palace
entrance/pre-boss states, seven endgame approaches, ten town/world states and seven
movement fixtures (44 states with Core; duplicates and elevator starts fixed in `836b8c4`). See [TEST-PACK.md](TEST-PACK.md) for the explicit standard-route
assumptions, levels, spells, items, techniques, zero spare keys, crystals and quest
flags. Native container meter limits and next-level XP targets are recomputed;
no persistent cheats or game-code changes. Test profiles now live under build/,
not the read-only shared .tools/ junction.

All 29 retained emulator scenarios pass sequentially; 16 ROM-free unit tests pass.
The 43-state pack reload checks include visible frames and 120-frame survival;
new states also assert progression, native meter capacity and controller response.
All five launcher selections pass PrepareOnly. Claude reviewed every screenshot (Codex
could not open images): right rooms, Barba visible, elevators under Barba, no duplicates. Ending/crystal-placement and mid-pit/long-shaft snapshots are omitted,
not faked; boss/shaft approaches are supplied instead. Full details and remaining
acceptance limits: build/CHECKPOINTS-REPORT.md. No gates advanced.

## Looking-up head (2026-11-14, `feat/look-up-head`)

Tall frame 8 is the boss open-jaw head sheared 2:1 snout-up (build-time recipe in `tools/boss_art.py`,
no ROM pixels committed), replacing the broken 90-degree rotation. Drawn while rising with Up held, during
an airborne Up+B windup, and for an upward-latched volley; forward air/ground attacks keep frames 4/5.
`tests/look_up.lua` PASS; body pairs 43/47; upward perf 27,837 peak, 0/900 lag.

## Upward breath and rising head-butt (2026-11-14)

Implemented the approved [upstab plan](UPSTAB-FIRE-PLAN.md). With Upward Thrust learned,
airborne Up+B starts a latched five-shot upward column (-3 Y, slight forward drift).
Grounded Up+B stays forward/vanilla; no tech means normal breath. Hold Up while rising
for centered native-head melee; descent disables it. Glove-gated ceiling bricks and
folded-head spawning are covered. Existing open-jaw art only; LOAD_LIMIT remains 7.

Build, 10 unit tests, 797 upstab assertions, all 23 non-stale suite scenarios, and
10 regenerated checkpoint reloads pass. Four known stale scenario reports are exactly
identical to base 262501a. Standard volley peak +39 cycles (30,119 -> 30,158), existing
1/900 lag unchanged; lava +22 (21,677 -> 21,699), 0 lag. Six-active-Bot upward probe:
27,839 peak versus base forward 27,888, 0/900 lag, 25 upward shots.
Elevator test is a CPU grounded/elevator-actor fixture, not a real elevator ride.
No new checkpoint; F3 is the playtest. Local report: build/UPSTAB-REPORT.md. No gates advanced.

## Fixed-bank headroom branch (2026-11-14)

`FarCall0` is a cold-hook ABI with exact caller-bank restoration; the lava body
moves to bank0. Fixed padding free increases from 11 to 16 bytes; no new
unproven region is used. See BUILD.md for 5-byte hook recipe/cycles and
FIXED-BANK-AUDIT.md for every owned fixed-bank byte. Hot enemy/terrain paths
are unchanged. Baseline/final idle avg/peak: 15,370/15,378 cycles; volley:
19,931/30,119, with lag unchanged at 0/300 idle and 1/900 volley.

At this branch's starting commit (`9793c6c`), full-suite acceptance was not
green: `town_safety`, `shouts`, `shout_queue`, and `dialogue_speed` had
subtitle-era and earlier dialogue expectations. The test-only reconciliation
now checks eight frame-dependent panic messages, expanded outdoor eligibility,
scripted-actor fast typing, floating OAM words, no HUD subtitle writes, and
the 120-update shout cooldown. The obsolete subtitle-only `shout_queue`
scenario is retired; `shout_follow` covers its replacement. No game source,
assets or build logic changed. Detailed per-assertion results are local in
`build/STALE-TESTS-REPORT.md`. All 27 retained suite scenarios pass, run
sequentially; all 10 ROM-free unit tests pass; test-pack generation and reload
validation pass for all 10 checkpoints. No game bug was demonstrated by the
20 baseline assertion failures.
`routines` had a stale pose-9 no-thrust assertion despite the already-existing
downstab; it now checks the precise foot hitbox and passes on both builds.
Full logs and baseline comparisons are local under build/. No gates advanced.

Human spot check: F4/F5 lava checkpoints, walk/jump on lava and exit normally;
then F9 into the boss fight. Expect no gameplay or visual changes.

## Verified locally

Validation performed with portable Mesen 2.1.1 and the exact source hash in
BUILD.md. Hardware sprite limits remain enabled.

| Check | Result and limits |
| --- | --- |
| Build integrity | Source hash enforced; all replacements guarded; overlapping writes rejected; original header/mapper/size preserved; source unchanged after build |
| Patch integrity | BPS output reconstructs the generated ROM exactly; wrong source and corrupted patch checksums rejected |
| ROM-free tool tests | Eight unit tests cover binary patch round trips, relocated source references, guards, overlaps, bank offsets and NES 2bpp encoding |
| New-game integration | Controller-driven name entry, castle gameplay, standing/crouched attack poses, jump, castle exit and overworld dragon renderer |
| Projectile-only attack | 16 real-game health/Fire/facing/stance cases each emit exactly five mouth-aligned diagonal fireballs with no melee/plume |
| Actual palace room | Test enters original Palace 6 room `$33` through the normal room loader, walks into lava, settles in the partly submerged lava pose (`GEOMETRY` bit 2, 16px lower with bottom row omitted and sprites kept in front of background), crouches in lava with full head/horns visible, jumps out (with lava-launch `$FA` boost to prevent pit softlocks) and returns alive; 99 hazard contacts during the scenario |
| Block progression | Six CPU cases verify native glove-gated brick breaking at either projectile, no player-body block damage and restored player pose/speed |
| Shielded enemies | `shield_enemies.lua` verifies Orange Ironknuckle (`$18`) high shield blocks standing shots and yields to crouching shots (shallow 0.5 px/frame drift from `$29+$0A`), while low shield blocks crouching shots and yields to standing shots |
| Hazard routine | All six world groups checked: palace groups gain support; other groups retain original water-death state |
| Roar routine | Inferno consumes the original Thunder state, starts the envelope, and reaches a zero-volume override after 48 updates |
| Human test pack | Eight native Mesen states generated for the exact build; every state reloads with a visible frame and survives 120 further frames; sea crossing completes on East Hyrule |
| Tall geometry and renderer | Four-corner native solid probes, lower head row, world-page crossing, edge rejection, ceiling folding, crouch and extra OAM cleanup pass controlled CPU checks |
| HUD split timing | 900 measured Palace 1 frames keep the split on line 31; previous build reached line 42. No upper-HUD scroll/address writes; native sprite-limit flicker remains possible |
| Bounded volley | Five logical slots keep exact eight-update spacing, preserve range, continue beyond attack animation, require release before rearming, and sustain Zelda II's native Barba/Flame fireball sound (`$ED |= $40` in `BarbaBreathSfx`) every frame while any volley fireball is live at all spell levels |
| Weak-enemy stomp & item pickup | `BarbaPreEnemy` (`$D4FE` -> `stomp.inc`) lets descending Barba stomp-kill weak enemies (`$C2,x` 1..4, excluding Dark Barba `$A1 = $23`) via native `$E880` with an upward bounce (`$057D = $FC`) and no contact damage, and lets Barba pick up keys, jars, P-bags, and 1-Ups (`$A1 = $01`, `$AF & $7F` in `$08..$0D, $10, $11`) by touching them via native `$E771` without requiring a crouched fireball |
| Post-flash palette | Strided WRAM flash-restore table (`$A9FA`/`$AA00`/`$AA06` -> `$69D2`/`$69D8`/`$69DE`) and side-view init (`$90DA`) patched to `$16/$27/$30` so `$074B` flash sequences (spells, item pickups, crystal flashes) restore Barba's red/orange/white palette instead of vanilla green/beige (`$18/$36/$2A`) |
| Downstab | `BarbaSetThrusts` (`src/tall_player.inc`) preserves `$0480`/`$047E` when `$80 == $09` (Downstab) while keeping horizontal melee disabled (`$F8`); hitbox widened to 18x12 px (`$E9B5`, `$E9A1`) centered under Barba (`$29+$1C`, `$CC+$0B`) |
| Town safety | All outdoor `$13..$20` villagers (static, generated, scripted, and house-openers) are eligible to panic and burn, and respawn when leaving and re-entering the room/town; indoor rooms and `$0B..$12` wise men/healers remain excluded |
| Town gameplay | Native Rauru generator, away-from-Barba fleeing (`$0E`/`$F2`, signed page check + continuous re-check; 72 px normal / 96 px attack awareness radius), real fireball burn/ash/expiry, scorchable outdoor town props & buildings (`BarbaTownBurn` in `src/blocks.inc`: a 2x2 flame turns to char in the nametable only, buildings and collision stay intact; `tests/town_fire.lua`), reachable held-Up dialogue, open black entryway (`$91`) shelter, and closed doorway (`$8B`) open/enter/close PPU animation without collision RAM edits |
| Left-facing and player doors | Busy-original-slot and world-page tests emit five shots; real doorway entry/return works with a nearby villager; F8 starts at Rauru entrance (`$00`) |
| Floating shout words | Floating sprite words above fleeing villagers (`OH SHIT!`, `OH FUCK!`, `RUN!`, `OH NO!`, `OH GOD!`, `HELP!`, `SAVE ME!`, `NO!`, `BARBA!`) rotate every ~2 s (`SHOUT_COOLDOWN = $78`) in 7 OAM slots (`$DC-$F4`) with 6 px compacted glyph bodies (`1..6`) for full 1 px black left/right borders, 8 px space skipping (`$FF`), edge clipping, and doorway/burn/dialogue/menu hiding; top-HUD subtitle text removed |
| Panic dialogue speed | Holding Up catches a fleeing villager; protected-NPC delays and caller registers retain original behavior |
| Checkpoint XP regression | Upgraded states now recompute the next-level target; 50 XP stays in gameplay, 2,000 XP permits one attack upgrade and returns to gameplay afterward |
| Battle performance | `BarbaDisplay` fast path (`$F27D` + unrolled 9-sprite draw) + `BarbaGeometry` `TerrainBatch` cache (`$6458-$645F`) cut display cost; `BarbaExtraUpdate` direct fast path + tightened `ExtraNearEnemy` (`-32 <= dx < +48`, `-32 <= dy < +64`) cut `extraAvg`/`extraMax` from 594/1,433 to 287/544 cycles; odd-frame OAM priority swap (`$0204 <-> $02F8`, `$0214..$021F <-> $02C8..$02D3` outside towns) balances 8-sprite drops across Barba's head/body and enemies (`perf_volley.lua`: idle avg 15,638 / peak 15,867, volley avg 19,820 / peak 28,411 cycles, `nearBudget(>27000)=8`, **0/900 lag frames**, `maxSpritesOnLine=11`, `framesOver8=64`) |
| Title, File Select, Game Over & NPCs | `BARBA I / THE ADVENTURE OF / BARBA` replaces `ZELDA II` and `LINK` (`$AFC6` + redraw tables `$AB65`/`$AEEA`); title water replaced with molten lava + 24x48 Barba (`$A7DD..$A828`, `$AF48`) that periodically opens its jaw (`windup`/`attack` head tiles via `$A8CF` -> `$A54F`) and triggers the fireball SFX (`$ED |= $40`); scrolling title story (`$A932`); File Select save-slot dolls (`CHR 00` `$D0/$D1`) show 8x16 Barba heads/busts; Game Over subtitle reads `LINK KEEPS LAVA` (`$8010`); Wise Men (`$0F`), Healing Ladies (`$17`), and Magic Women (`$18`) react to Barba while keeping their spell/heal logic; spell menu reads `SCALES`, `JUMP`, `LIFE`, `WYRMLNG`, `FIRE`, `REFLECT`, `SPELL`, `INFERNO` |
| Palace 6 Lava Link boss | `tests/link_boss.lua` verifies Palace 6 boss (`$21`) switches Sprite Palette 1 to Link (`18 36 2A` via `$A765` PPU packet), renders hand-drawn 16x16 Link heads and the button-down tunic neck in `CHR 25` (`14..2E`, `A0/A2`, sword beam `52` from `CHR 2` `32`), centers the head over the body (`$B286` `02 FE`), neck stops at the lava (5 pieces, `$B294`), plays Link's hurt sound once per hit (`$A795`), breathes 2 Spear/sword beams per attack (`$05` at `$B19B`, `$B18C` mask `$37`) instead of 6 flames (`$04`), and takes damage from Barba's fireballs |

Combat and palace scenarios intentionally create controlled fixtures (enemy
positions or room entry and extra health). They exercise the original game
loop, collision and damage code but do not establish that normal progression
through every palace is complete. The routine harness is an isolated CPU check.

Screenshots and detailed reports are generated in the ignored `build/` folder.
Audio register/envelope validation is not a listening-quality review.

## Remaining work before a finished conversion

The ordered next steps and latest human feedback are in [ROADMAP.md](ROADMAP.md).

- Upward breath and rising head-butt have producer signoff (2026-11-14). Glove-gated
  fireball block breaking is implemented.
- Palace 6's boss is now **Lava Link** (`tests/link_boss.lua` PASS); full defeat-to-crystal playthrough remains to be tested by hand.
- Audit sprite states and CHR sharing in every town, palace, menu, ending and
  the Dark Link encounter; the current replacement covers 13 side-view sprite banks.
- Replace residual Link references and item/menu art where appropriate (title screen logo now reads `BARBA`).
- Partially submerged lava pose is implemented (`tall_player.inc`: `GEOMETRY` bit 2 shifts standing sprites 16px down and omits the bottom row while keeping all sprites in front of background bricks); audit all lava rooms,
  bottomless pits, water hazards, elevators, low tunnels and collapsing floors.
- Listen to and tune the roar with music, pause/unpause and scene transitions.
  Additional milestone triggers are not implemented yet.
- Test all spell unlocks, NPC/quest interactions, Reflect, bosses, blocks,
  projectile walls, save/load/continue and a complete playthrough.
- Cross-check another accurate emulator and original-style MMC1 hardware behavior.

No public ROM or finished release is provided in the repository. Build locally
from the required source ROM; the ROM and generated patches stay ignored.


## Checkpoint repair follow-up

feat/checkpoint-sets: distinct GP $2C / P1 $03 low tunnels replace the duplicate
GP $36 fixtures; both elevator states start on native object $13 and ride down/up
in reload tests. World Darunia/Old Kasuto background palettes match vanilla
($13/$02 sky). Movement adds the P6 $28 -> $2D drop-shaft edge, accurately labeled
nonlethal; the requested lethal bottomless pit remains unverified, not fabricated.
No game code, ROM recipe, asset, merge, push or producer gate was changed.
Details and numeric proof: docs/TEST-PACK.md and local build/CHECKPOINTS-REPORT.md.
