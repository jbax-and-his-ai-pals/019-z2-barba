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
`BarbaBlocks` samples each live fireball's center using the original glove-gated
block handler, restoring player pose and velocity so remote fireballs avoid
sword recoil or bouncing Barba. After restoring held thrusts via `BarbaSetThrusts`,
it also runs `$E1DD` for active downstab (`$80 == $09`, temporarily offset +5px
to `$29 + $21` for the tile check and restored to `$29 + $1C` afterwards) and
rising upstab (`$80 == $08`, `$29 - $08`).

## Five-shot volley at every health level

Every attack emits five forward/downward fireballs: two pixels horizontally and
two downward per update. Five logical slots now keep an exact eight-update cadence in both stances.
The original two slots and three backed slots retain full projectile range. The volley continues after the attack animation
without locking movement. Holding B does not restart it; B release and an idle
attack state (`$0400 == 0` or standing post-slash recovery `$0400 == 4`) are required before rearming.

A full pool retries only until the 120-update burst deadline. Each projectile
has a 33-update maximum lifetime and is cleared before its Y coordinate wraps.
Menus, transitions, death and Wyrmling cancel queued shots. Health is never an
eligibility test. Fire changes vulnerability class, allowing Fire-only enemy
hits; ordinary breath retains the native beam class and progression rules.

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
the HUD/screen edges. Native shots and
their original OAM remain intact. Native enemy and shield entry hooks execute
through fixed-bank gateways and retain the original vulnerability routines.

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
- `combat.lua`: glove-gated fireball brick breaking and restored player state.
- `damage.lua`: real native Bot damage from ordinary and Fire-empowered shots
  in both directions.
- `shield_enemies.lua`: Orange Ironknuckle (`$18`) high/low shield blocking
  and crouching shallow-angle (`$29+$0A`, 0.5 px/frame) low-half hits.
- `gameplay.lua`, `tall_geometry.lua`, `routines.lua`: movement, jumps, ceilings,
  item/Fairy cleanup, disabled thrust collisions, lava and roar.
- `hud_timing.lua`: 900 Palace 1 frames with a stable line-31 split.

Remaining: shield/boss balance, projectile walls, vertical-technique redesign,
crowded-room sprite review and complete human playtesting.
