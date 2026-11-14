# Mouth-anchored breath

`src/tall_player.inc` renders thirteen boss-derived 24x48 poses. Six original body
OAM slots hold the lower rows; three spare slots hold the head. The native
renderer retains item poses, invisibility and flying form. Extracted pixels
stay in local ignored outputs.

The body repeats the boss's narrow segmented neck without an added belly coil.
Vanilla reuses crouch frame 6 during ascent; the renderer selects a separate
full-body jump pose while airborne, leaving native animation and physics state
intact. Airborne low attacks also retain the whole body. Only grounded crouch
uses the head-only low pose.

## Shared geometry

`BarbaGeometry` publishes the attached 8x16 plume origin in `$05F2/$05F3` and
validity/tuck flags in `$05F6`. Body drawing, melee and new Fire shots use this
geometry. Screen X is actor screen X +28 facing right, or -4 facing left.
Plume Y is actor Y -12 standing, +4 folded, or +20 crouched. World projectile X
adds the 16-bit scroll with carry. Clipped origins suppress new shots.

Four head corners use the area's native solid-tile predicate through a
single batched bank round-trip at fixed-bank `$FF4C`. Under stone the head shifts down sixteen pixels and the
middle neck row disappears. Crouch occupies only the bottom 16px lane.
Movement and enemy-contact collision retain their native sizes: the extra
head height is visual and needs human review.

Horizontal melee covers the two-part plume with a 16x10 box. Native vertical
shapes, technique unlocks and bounce remain; vertical flame art needs work.

## Bounded full-life volley and Fire upgrade

Full life replaces the straight beam with two forward/downward fireballs.
Each travels two pixels horizontally and two downward per update, mirrored
with facing. Without Fire, these retain beam-class damage and the native
timeout, so they cannot bypass Fire-only enemies. With Fire active, the same
volley gains the spell's vulnerability class. Below full life, Fire supplies
the horizontal burst. Both modes retain the native attack-animation gate and
schedule exactly one follow-up eight updates later. Attack 1 and Attack 4 support two slots.
A full pool drops the follow-up without retry. Holding an attack cannot
repeatedly arm bursts. Menus, scene changes, death, flying form, freezes and
disabling Fire below full life cancel the queue. Taking damage cancels a pending
full-life follow-up. Delay/latch live at `$05F7/$05F8`, cleared by
the native reset loop with no original references found. Two slot flags at
`$05FC/$05FD` select diagonal movement; `$05FE` records the burst mode. Projectiles
are cleared at the bottom of the screen before their Y coordinate can wrap.

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
two-slot pool; it does not copy aimed enemy-projectile code.

## Validation

- `breath_height.lua`: 16 real-loop health/Fire/facing/stance cases, damage at
  the visible plume, mouth spawns, jump, crouch and castle exit.
- `combat.lua`: native Bot damage near the flame tip in four stances.
- `burst.lua`: controlled CPU harness checks timing, capacity, held attacks,
  dropped retries and cancellation. Projectile movement is parked deliberately
  so slot lifetime cannot obscure scheduling errors.
- `tall_geometry.lua`: controlled geometry and renderer-clearance checks.
- `hud_timing.lua`: actual PPU scroll/address writes, split scanline, mapper
  traffic and NMI duration in four Palace 1 phases; CSV stays in local build output.

Remaining: vertical flames, shield/block interactions, scroll-boundary
fixtures, crowded-room flicker review and broader human playtesting.
