# Mouth-anchored breath

Implements roadmap milestone 3's first half: one breath at every health level,
with Fire as the upgrade. Original game code remains in the user's local ROM;
`src/breath.inc` contains only new routines.

## What changed in the ROM

| Location | Change |
| --- | --- |
| Bank 7 `$D50D` → `BarbaUpdate` | Calls `BarbaProjectiles` (enters native `$9878`) instead of `$9847` |
| Bank 0 `$8E50` (ROM `$0E60`) | Fire spell pointer `F1 97` → `BarbaFireSpell` (guarded) |
| `BarbaUpdate` | Also calls `BarbaMuzzleScreen`, mirroring the mouth to `$05F2/$05F3` |

### No automatic full-health beam

Native `$9847` spawns the sword beam at full health when Fire is inactive, then
falls into the shared projectile update at `$9878`. `$9878` reloads X and has no
state dependency on the skipped range, so entering it directly keeps every live
projectile's motion, lifetime, wall/enemy handling, graphics and the two-slot
ceiling while never creating a beam. Melee breath is identical at any health.

### Fire leaves the mouth

`BarbaFireSpell` wraps native `$97F1`. That routine still decides timing, free
slots and the attack-level slot count. A newly allocated slot is exactly `1`
(`INC` from 0). Only such a slot is moved; existing flames are untouched.

The mouth is computed **at spawn time** from the same state the native spawner
reads: world X `$4D/$3B`, Y `$29`, facing `$9F`, duck/shield `$17`. An earlier
draft had the renderer publish the mouth, but the spell loop runs before the
player display, so that position would be a frame late after a stance change.

```text
MuzzleOffsetX[$9F]: right +$20, left -$08   ; top-left of the 8x16 fire sprite
MuzzleOffsetY[$17]: ducked +$10, standing +$00
```

These match the attached breath sprite (OAM `$0220`) on the current 16x32 body,
measured in Mesen. Native Fire used X+`$0D` for both facings (mid-body) and Y
+4/+`$0D`. Tile `$84` and the breath flame share a vertical center (row ~8), so
the projectile travels in the visible breath lane. `$05CA` stays zero, keeping
it a Fire flame: `$84` graphics and Fire-only enemy vulnerability are unchanged.

**When the sprite changes, retune these four bytes** together with the attached
plume position so the visible fire, melee box and Fire origin still agree.

## Verification (`tests/breath_height.lua`)

16 controller-driven cases: Fire on/off × full/damaged health × left/right ×
standing/crouched, plus jump, crouch and castle-exit movement. 37 checks pass:

- Without Fire, no projectile slot ever activates, at full or damaged health.
- A Bot overlapping the visible breath sprite takes damage in every stance.
- With Fire, a native Fire-class projectile spawns within 8 px (Y) / 12 px (X)
  of the mirrored mouth, in all eight stance/facing/health combinations.

The existing gameplay, combat, palace, routines and boot scenarios still pass,
and the F1-F7 test pack regenerates and validates for the new build.

## Original Barba reference (for the flare/burst follow-up)

The Palace 6 boss uses its `$0499` state and `$0504,X` timer to rise, hold and
shoot, then descend. Its firing path is bank 4 `$B180..$B1BC`: it opens a short
timer window, fires on alternate frames, asks `$9BE5` for a projectile slot/aim,
selects enemy projectile type 4, multiplies both velocity components by four
and offsets the projectile from the head. It is a timed volley, not a beam.

## Not done yet

- A windup/muzzle-flare frame borrowed from the boss's jaw, and plume art tied
  to the chosen (taller) sprite. Depends on milestone 2's sprite.
- A boss-like multi-shot Fire burst. It would need its own bounded scheduling;
  the native two-slot allocation is deliberately unchanged.
- Up/down breath art; vertical attacks still use the original damage shapes.
- Scroll crossing a 256-pixel page and screen-edge spawns are covered by the
  16-bit math but not yet by a dedicated scenario.
