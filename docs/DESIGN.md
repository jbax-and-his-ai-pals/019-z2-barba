# Refined project brief

## Decisions confirmed November 12, 2026

- Compact serpentine Barba, based on the boss's silhouette; no added wings required.
- Keep the original item, spell, palace, and overworld progression.
- A convincing NES-native roar is sufficient; exact FDS restoration is optional.
- Standard MMC1 output. No expansion-audio mapper or emulator-specific features.

## Playable form

Fit the collision body inside Link's original movement footprint. Curled tail,
horns, gold underside, and an elongated snout establish Barba's identity.
Coil/slither on the ground; lift the coil during jumps. Crouch lowers the head
to the low attack lane. Defensive scales preserve the shield's directional role.
Retain damage flashing, ducking, recoil, item holds, and death animation coverage.

Use a readable 16x16 overworld avatar, with two animation frames per direction.
Water crossings remain tied to the raft unlock and its existing route; the
crossing depicts hovering/skimming rather than unrestricted flight.

## Combat

- B produces a short, timed flame burst. Keep attack commitment and recovery.
- Standing and crouched flames remain distinct attack lanes.
- Down- and up-thrust become vertical fire attacks. Preserve their unlocks,
  block-breaking requirements, and down-thrust bounce behavior.
- A visible flame must agree with its damage region. Decorative pixels may
  taper, but invisible long-range damage is unacceptable.
- The basic flame retains the sword's enemy interaction rules to preserve
  progression. The Fire spell upgrades to the dedicated ranged fire interaction.
- Full-health beams become embers/fireballs. Speed and size upgrades need
  separate wall, shield, and boss checks before changing balance.

## Lava

Palace lava should support the dragon at its surface with a partly submerged
visual pose. He can move and jump out. Simply disabling death is insufficient:
it can strand the player below the room's floor or trigger bottom-screen death.
Water, bottomless pits, collapsing floors, and enemy contact remain separate cases.
No redesigned palace routes are assumed in the first implementation.

## Spells

| Original | Dragon theme | Initial behavior |
| --- | --- | --- |
| Shield | Scales | Existing damage reduction and defensive presentation |
| Jump | Spring | Coil-assisted high jump; no unrestricted flight |
| Life | Renew | Regeneration |
| Fairy | Wyrmling | Small flying serpentine form |
| Fire | Blaze | Empowered ranged fire |
| Reflect | Mirror | Reflective scales |
| Spell | Ancient | Existing world/quest interactions |
| Thunder | Inferno | Screen attack with signature roar |

Any true glide is a later movement change requiring a gate/ceiling audit.
Short menu labels must fit the existing menu; longer names can appear in docs.

## Audio and bosses

Start with a short native pulse/noise roar. Reserve its strongest cue for
Inferno and major milestones rather than every ordinary attack or spell.
Audio must coexist with music and avoid leaving an APU channel stuck.

Prefer a distinct Ice Barba for Palace 6: separate colors and readable eyes,
with the established boss behavior retained initially. Dark Link's shared player
graphics also need a deliberate appearance check after player replacement.

## Implementation sequence and exit criteria

1. Reproducible, hash-guarded build; original ROM unchanged; local patch round trip.
2. Complete visual conversion in overworld and side view; inspect actual emulator frames.
3. Flame visuals and collision alignment; standing/crouched/vertical/wall/boss checks.
4. Palace lava surface movement; test exit, jump, water death, and bottomless pits.
5. Spell, roar, raft, and Palace 6 treatment; check unlocks and audio cleanup.
6. Full playthrough and compatibility pass before calling the hack a release.

Use build-time assertions, focused emulated scenarios, and human playtesting.
Passing a boot check does not imply that a full playthrough has been validated.
