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

Next implementation milestone: a sprite/height study using the actual boss's
tiles, colors and proportions extracted locally from the supplied ROM.

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
  This is a design proposal; the current ROM's beam rule is unchanged.
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

## Suggested next work

With the checkpoint XP bug corrected, start milestone 2: a boss-derived Barba
sprite study with two height options. Use its chosen mouth position for the
milestone 3 breath prototype. Keep the current alpha and checkpoint recipe as
the comparison baseline; do not quietly replace the combat model during art study.
