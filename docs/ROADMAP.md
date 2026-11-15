# Barba Edition roadmap

## Direction from the first human playtest

Movement and basic animation are a useful foundation. Scales and Wyrmling are
working well. The next pass should prioritize fidelity to the actual Barba boss,
especially the sprite and attack, rather than adding more cosmetic substitutions.
A taller playable dragon is explicitly acceptable if it works with the rooms.
Spell names are flexible: retain distinctive dragon names where useful, but
familiar Zelda II names are preferable when behavior remains essentially vanilla.

## 1. Stabilize progression and test checkpoints

**Fixed:** upgraded F2-F7 checkpoints retained the starting character's cached
next-level XP target after their stats were raised. At 50 XP, the game could
open the level-up menu without an affordable choice, trapping its selection loop.
The generator now derives the correct target from the ROM's XP tables and clears
current XP whenever it grants test levels. This changes checkpoint preparation,
not the ROM's experience system.

Regression: a 50-XP gain must not open the menu; 2,000 XP must offer an attack
upgrade from level 4 to 5, subtract XP once, close the menu and resume play.
Regenerate and reinstall all seven checkpoint slots after generator changes.
Further normal-play XP, cancellation, repeated upgrades and max-level rewards
remain part of the progression audit.

## 2. Establish a more authentic playable Barba

**Playable prototype implemented:** 24x48 frames now adapt the actual boss's
head and neck from the supplied ROM. The following remain review criteria:

- Preserve the recognizable snout, horns, eye, open jaw, long neck and segmented
  underside; adapt these features directly rather than extending the current
  simplified snake artwork indefinitely.
- Compare the current 16x32 footprint with taller 16x48 and 24x48 studies.
  These are prototype envelopes, not a promise that every pose needs all pixels.
- Build idle, slither/coil, turn, jump, crouch and open-mouth attack poses first.
- Distinguish visual height, terrain collision and enemy hurtbox explicitly.
  A visually tall prototype can keep the current movement box temporarily;
  that mismatch needs review before treating it as the final gameplay design.
- If the physical body grows, test low doors, elevators, ceilings, crouch
  clearance, NPC interactions and enemy contact before committing to it.
- Check native sprite limits with enemies and breath visible. Greater height
  costs additional sprite rows; greater width adds scanline pressure.

Exit criterion: choose an authentic silhouette and muzzle position that stay
readable and navigable in the castle, combat corridor, lava and boss checkpoints.

## 3. Rebuild the attack around Barba's mouth

**Playable prototype implemented:** the automatic full-health beam is gone.
Boss-derived jaws, attached plume and bounded Fire burst share one mouth
calculation ([details](BREATH-IMPLEMENTATION.md)). Vertical flames and broader
combat interactions still need work.

Study the original boss's firing animation, spacing and projectile paths in F6.
Prototype a short attached plume and a compact fireball burst against that
reference before settling the combat feel.

Recommended direction:

- One consistent breath windup, mouth flare and recovery at every health level.
- Reliable short-range breath as the basic attack, with its damage aligned to
  the visible fire in standing, crouched and airborne poses.
- Fire/Blaze empowers range or adds a Barba-like projectile burst, preserving
  the spell's progression and enemy-vulnerability role.
- Remove the distracting distinction between a reskinned sword beam and breath.
  Prefer dropping the automatic full-health beam, or integrating a full-health
  bonus into the same breath animation if playtesting favors that behavior.
  The automatic full-health beam has now been removed.
- Preserve attack commitment and directional defense. Avoid unlimited rapid
  fire or repeatedly damaging an enemy on every animation frame by accident.
- Give up/down attacks dedicated fire art, retaining unlocks, down-thrust bounce
  and block-breaking rules until tested replacements exist.

Validate muzzle alignment, left/right symmetry, high/low lanes, enemy shields,
walls, screen edges, bosses, projectile limits and sprite crowding.

## 4. Consolidate spells and dragon presentation

- Keep the successful Scales and Wyrmling concepts.
- Prefer Jump, Life, Fire and Reflect where those names explain unchanged
  abilities more clearly. Keep Inferno if its roar/visuals earn the distinction.
  Renaming is secondary to behavior and readability; no immediate rename is required.
- Polish partially submerged lava poses, sea-crossing animation, damage,
  death, item holds and remaining menu/ending graphics.
- Listen to the roar against music and transitions, then add selected milestone
  triggers without making every action equally loud.

## 5. Resolve encounters and finish the conversion

Implement a distinct Ice Barba boss appearance after the player palette and
sprite direction settle. Review Dark Link's shared graphics deliberately.
Then audit spells and item gates, towns, all palaces, hazards, save/continue and
ending behavior. Complete a full playthrough and a second-emulator check.

## Current playable milestone (November 14)

Implemented: 24x48 boss-derived player, three slither frames, jaw windup/open
attack, shared mouth calculation, 16x10 attached flame damage, ceiling folding,
16px crouch and a bounded two-shot Fire burst eight updates apart. Existing
movement and enemy-contact boxes remain unchanged. This visual/physical height
distinction needs human review, especially when enemies pass near the head.

Next: human review of F1/F2 movement and attacks, F3 Fire and vertical techniques,
F4/F5 lava and F6 player/boss readability. Then refine the neck/coil and vertical
flames, give Palace 6 a distinct Ice Barba, and audit elevators, towns, item
holds, enemy shields, blocks and sprite crowding. Full progression and another
emulator remain required before calling this a finished conversion.

## Latest battle feedback

Implemented the requested full-life bonus: two downward-diagonal fireballs from
the mouth replace the straight sword beam. Fire upgrades their vulnerability
class; below full life the spell retains its horizontal burst. Native two-slot
limits and attack commitment remain. Tune the angle and burst spacing from
human feedback before adding more projectile slots.

HUD text shifting was reproduced in the Palace 1 timing fixture. Batched head
checks and deferred spawning now keep all measured splits on line 31. Continue
watching crowded rooms; ordinary NES sprite-limit flicker remains separate.

## Current direction: five-shot breath and reactive towns

The latest user decision supersedes the health-dependent beam/plume proposals:
Barba attacks only with a five-shot diagonal volley at any health. Native melee
and thrust collisions are removed; Fire changes projectile vulnerability, and
fireballs preserve the glove gate for breakable bricks.

Town prototype: native generated outdoor wanderers alone can panic or burn.
They flee away from Barba, enter a real doorway when encountered, and stay
inside until room reset. Up opens a fearful plea. Indoor/scripted NPCs retain
normal behavior and cannot be burned. Casualties are not persistent. Next town
work is broader street/door/quest interaction review and more dialogue variety;
there is no town reputation system or permanent population loss yet.

## Current playtest fixes

Crouch now includes a short segmented body. Five logical projectile slots
replace the two-slot cadence bottleneck, preserving range while firing every
eight updates. Left-facing occupied-slot and page-crossing checks pass.
Wanderers flee at one pixel per update, panic at a smaller radius, and despawn
immediately at existing doors without touching background tiles. Close Up
conversations respect transitions. F8 uses the real Rauru street; player house
entry and return are tested. Older checkpoints must be regenerated.

## Producer direction (2026-11-14, latest)

- **Lava Link stays the producer's original vision:** Barba's boss moves (rise, fire, sink) in Link's body. Sword beams
  fire at every health level. No weakening phases: bosses don't get weaker as they're damaged. Difficulty and challenge
  are not goals for this fight.
- **Experiment:** shield mechanics for Lava Link. **Do:** Link's hurt sound when Lava Link takes damage (Link only).
- **Later:** battle flicker, and polish (lava pose, roar triggers, leftover Link art in menus/ending).
- **Now:** fix the stale town/shout/dialogue tests, and build save-state **checkpoint sets of key spots** so a whole-game
  playtest is quick.
- Town fire is final: scorch marks and casualties never persist after leaving a town.
