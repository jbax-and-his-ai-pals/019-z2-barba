# Mouth-anchored breath

`src/tall_player.inc` renders thirteen boss-derived 24x48 poses. Six original body
OAM slots hold the lower rows; three spare slots hold the head. The native
renderer retains item poses, invisibility and flying form. Extracted pixels
stay in local ignored outputs.

The body repeats the boss's narrow segmented neck without an added belly coil.
Vanilla reuses crouch frame 6 during ascent; the renderer selects a separate
full-body jump pose while airborne, leaving native animation and physics state
intact. Airborne low attacks also retain the whole body. Only grounded crouch
uses a compact 24px pose with eight pixels of segmented neck beneath the head.

Elevator contact (`$0754 != 0`, set by the native enemy pass) also selects the
compact crouch/crouch-attack art and crouched mouth origin. This is a visual fold:
`$80`, `$17`, movement and the elevator's Up/Down controller stay native. Riding
up or down therefore keeps the head inside the shaft; leaving restores the
ordinary pose. `tall_geometry` checks both poses and mouth placement; `state_pack`
checks the pose during real elevator travel in both directions.

## Shared geometry

`BarbaGeometry` publishes the 8x16 fireball origin in `$05F2/$05F3` and
validity/tuck flags in `$05F6`. Body drawing and new fireball shots use this
geometry. Screen X is actor screen X +28 facing right, or -4 facing left.
Fireball Y is actor Y -12 standing, +4 folded, or +12 crouched. World projectile X
adds the 16-bit scroll with carry. Clipped origins suppress new shots.

Four head corners use the area's native solid-tile predicate through a
single batched bank round-trip at fixed-bank `$FF4C`. Under stone the head shifts down sixteen pixels and the
middle neck row disappears. When grounded on lava (`LAVA_CONTACT != 0`) or in
swamp water (`$0752 != 0`), `GEOMETRY` bit 2 (`$04`) shifts the head and upper
neck down sixteen pixels into the native box and omits the bottom row. Crouch now draws a 24px body while retaining the native 16px physical lane.
Movement and enemy-contact collision retain their native sizes: the extra
head height is visual and needs human review.

All native melee origins are hidden after rendering, including up/down thrusts.
There is no attached plume. Item-holding and Wyrmling drawing remain native.
The Wyrmling art (tiles `$68`/`$6A`, wings up / wings down) is the front-facing
`wyrmling` pair in `assets/barba.json`; the native draw never flips it, so the design
stays facing-neutral. The healing-fairy pickup shares these tiles.
`BarbaBlocks` samples each live fireball's center using the original glove-gated
block handler, restoring player pose and velocity so remote fireballs avoid
sword recoil or bouncing Barba. After restoring held thrusts via `BarbaSetThrusts`,
it also runs `$E1DD` for active downstab (`$80 == $09`, temporarily offset +5px
to `$29 + $21` for the tile check and restored to `$29 + $1C` afterwards) and
rising upstab (`$80 == $08`, `$29 - $08`).

Block-animation exhaustion (2026-11-16): vanilla's five records at `$041A-$043C`
used to overwrite slot 0 when full. Breath could abandon a block midway through
its visual erase after its collision tile was already cleared, leaving an
unhittable fragment. Guarded, same-size rewrites in fixed bank 7 at `$E23A` and
`$E0FC` now reserve a record via `$E292` before changing collision. `$E29C`
returns failure on exhaustion; both brick breaking and crumbling floors defer
until a record is free. No ROM padding or RAM is allocated. `combat.lua` checks
pool exhaustion, preservation of all five records, their final four-tile erase,
a successful later breath retry, and both crumbling-floor allocation outcomes.

## Five-shot volley at every health level

Every attack emits five forward/downward fireballs: two pixels horizontally and
two downward per update. Five logical slots now keep an exact eight-update cadence in both stances.
The original two slots and three backed slots retain full projectile range. The volley continues after the attack animation
without locking movement. Holding B does not restart it; B release and an idle
attack state (`$0400 == 0` or standing post-slash recovery `$0400 == 4`) are required before rearming.

A full pool retries only until the 120-update burst deadline. Each projectile
has a 33-update maximum lifetime and is cleared before its Y coordinate wraps.
Menus, transitions, death and Wyrmling cancel queued shots. Health is never an
eligibility test. Breath is always fire class (`$05CA = 0`), so Fire-only enemies
take hits without a spell; flame class strictly dominates the native beam (`$D2`)
in bank 7 `$E6CB`. The old Fire slot is METEOR (see below).

State: `$05F1` deadline, `$05F7` spacing, `$05F8` latch, `$05FC/$05FD` projectile
lifetimes and `$05FE` pending-shot count. These locations have no original
references and are cleared by the native reset loop. `$05FF` guards the extra
pool. Three backed records at `$6400/$6410/$6420` and native-window scratch at
`$6440..$6456` use a gap outside collision buffers, room tables and save flags.
They reset on invalid scenes. The backed slots temporarily alias native slot 0
for movement, damage, shields and glove-gated blocks, then restore native state.
Collision wrappers skip inactive/distant shots to preserve frame headroom.

Extra fireballs use OAM `$3C/$44/$48`. The raised head moved to `$04/$4C/$C4` (avoiding `$F8`, which holds the native HUD magic partial-bar sprite),
avoiding the original enemy-projectile slots at `$28/$2C/$30`. During downstab
(`DRAW_FRAME == $51`), unused native sword/shield slots `$20/$24` draw a second
16x16 torso chunk (`$06/$08`) at `DRAW_TOP - $10` unless tucked or clipped by
the HUD/screen edges. Both torso chunks flip horizontally and vertically in place
during downstab: their two tile columns reverse and OAM attribute bits 6/7 toggle,
retaining palette. The turned head keeps its existing attributes.
Gem victory (2026-11-17) completes the torso only during the sampled
looking-up roar: `RoarTorsoHop` maps bank 6, `RoarGemTorso` lifts the three
existing rows 8px, then fills sword/shield slots `$20/$24` with the existing
`$06/$08` torso at the original feet height. Its top 8px overlap the identical
half-segment already in the look-up art: two complete chunks, no third partial
chunk, total height 56px. Facing controls column order and
flip attributes. Geometry tuck/submersion, HUD and right-edge clipping suppress
the extension; normal look-up attacks and other roars keep their existing art.
The helper restores bank 0 before returning. No new CHR, OAM slots or RAM.
`tall_geometry` checks both facing directions. Native shots and
their original OAM remain intact. Native enemy and shield entry hooks execute
through fixed-bank gateways and retain the original vulnerability routines.

The fatal-hit transition calls `BarbaDeathDisplay` in bank 3 through the
guarded driver at `$C9EE-$C9F7`. It lifts the compact death head by 16px
and fills that row's former space with the full `$06/$08` torso in OAM
`$20/$24`. The original lower torso stays at the feet, yielding one head
row and two full torso rows. The new row inherits native facing, palette
and per-column clipping. The helper restores bank 0 for the native palette
flash. `death_continue` checks the three rows in both directions.

2026-11-16 sprite follow-up: odd-frame priority rotation now swaps only Barba's
outer head sprites. The lower body stays in `$0214-$021F`; the renderer no longer
exchanges it with `$02C8-$02D3` inside the rotating native enemy records. This
removes dragon art from enemy-owned records and is the candidate fix for the
producer's intermittent red ghost during downstab/busy palace combat. The exact
reported ghost has not been reproduced; human confirmation remains open.
`tall_geometry` seeds six live enemies and verifies all six sprites of the native
record survive standing/downstab drawing on odd frames.

The title jaw tables now come from the compiled idle/windup/attack head rows.
The old open-jaw right column `$22` had become crouch art after tile allocation
changed; the correct shared horn column is `$04`. `title_roar` checks all three
complete jaws as well as the unchanged noise-channel roar.

## METEOR slam (spell slot 4)

Casting sets `$076F` bit 4, which lasts as vanilla Fire did (side-view init `$8CF4` clears it). `BarbaMeteorTick`
(after the HUD split, from `BarbaProjectiles`) starts a dive on mid-air `Down + B`
(`$F7` bit 2, `$F5` bit 6), cancels that attack's volley, and holds `$057D = 6`
until `$0479` clears. `MeteorLand` plays the stomp thud (`$ED |= $10`), a short
decor flash (`$074B = $84`) and emits two shots through the normal allocator with
`INFERNO_AIM = $C1/$C2`. Aim and `VOLLEY_SLOT` flags `$C0` (up + crouch, never
otherwise combined) mean a flat wave at `$29 + $12` with breath's 33-update life (63 held the 2-live-shot cap and throttled the next volley);
`BarbaStepSlotY` and the extra fast path skip Y movement for it. `METEOR_STATE`
is WRAM `$6474`, cleared on any non-gameplay frame.

Bank 0 had 3 free bytes, so METEOR reuses dead vanilla code: the Fire spell body
`$97F1-$9814` (`MeteorLand`), `Check_for_Fire_Spell` `$9847-$9877` (`BarbaMeteorTick`;
its only caller `$D50D` is the `BarbaUpdate` hook) and the raft-avatar tail
`$81C1-$81E4` after the `$81C0` RTS (`BarbaCancelBurst`/`BarbaArmBurst`). `build.py`
guards each full original range.

## HUD timing correction

The spell dispatcher runs before Zelda II's sprite-zero status/playfield split.
Repeated head probes there could make the scroll write arrive late. The spell
pointer now returns immediately, and all spawning runs through `BarbaProjectiles`
after that split. The renderer computes geometry once on ordinary frames; four
terrain corners share one bank round-trip instead of four.

In a 900-frame Palace 1 fixture, the old build's split reached line 42. The
new build stays at line 31 in idle, Fire idle, damaged-health Fire attacks and
full-health attacks with XP display updates. This addresses HUD scroll jitter;
the NES eight-sprites-per-line limit can still cause sprite flicker.

Existing movement, collisions, graphics, lifetime and sound use native handlers.
The volley borrows the boss's timed-fire idea while respecting the player's
native collision rules; it does not copy aimed enemy-projectile code.

## Validation

- `projectile_only.lua`: 16 real-loop health/Fire/facing/stance cases, exactly
  five shots each, muzzle alignment, direction, class and no attached melee.
- `burst.lua`: capacity, lifetime, deadline, held-input/rearm and cancellation.
- `extra_fire.lua`: native-window preservation, extra-slot damage/class, shield
  dispatch, movement/OAM and glove-gated blocks.
- `left_fire.lua`: left-facing shots near edges, across a world page, and with
  both original slots already occupied.
- `combat.lua`: glove-gated fireball brick breaking, restored player state,
  full animation pool / final erase / retry, and crumbling-floor allocation.
- `damage.lua`: real native Bot damage from ordinary and Fire-empowered shots
  in both directions.
- `shield_enemies.lua`: Orange Ironknuckle (`$18`) high/low shield blocking
  and crouching shallow-angle (`$29+$0A`, 0.5 px/frame) low-half hits.
- `gameplay.lua`, `tall_geometry.lua`, `routines.lua`: movement, jumps, ceilings,
  item/Fairy cleanup, disabled thrust collisions, lava and roar.
- `hud_timing.lua`: 900 Palace 1 frames with a stable line-31 split.
- `meteor.lua`: dive, fall cap, two flat fire-class floor waves at `$29+$12`,
  a floor Bot hit, and no dive without the spell.

Remaining: shield/boss balance, projectile walls, vertical-technique redesign,
crowded-room sprite review and complete human playtesting.
