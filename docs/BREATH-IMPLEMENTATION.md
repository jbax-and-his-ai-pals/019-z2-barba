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
fixed-bank gateway. Under stone the head shifts down sixteen pixels and the
middle neck row disappears. Crouch occupies only the bottom 16px lane.
Movement and enemy-contact collision retain their native sizes: the extra
head height is visual and needs human review.

Horizontal melee covers the two-part plume with a 16x10 box. Native vertical
shapes, technique unlocks and bounce remain; vertical flame art needs work.

## Bounded Fire upgrade

There is no automatic full-health beam. Fire retains the native first-shot
animation gate and Fire-only vulnerability, then schedules exactly one
follow-up eight updates later. Attack 1 and Attack 4 both support two slots.
A full pool drops the follow-up without retry. Holding an attack cannot
repeatedly arm bursts. Menus, scene changes, death, flying form, freezes and
disabling Fire cancel the queue. Delay/latch live at `$05F7/$05F8`, cleared by
the native reset loop with no original references found.

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

Remaining: vertical flames, shield/block interactions, scroll-boundary
fixtures, crowded-room flicker review and broader human playtesting.
