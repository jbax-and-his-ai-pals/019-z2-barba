# Reactive town prototype

Only native randomly generated outdoor wanderers can flee or burn. Eligibility
requires all of these: live slot value 1, generator-origin marker `$BC,x=$FF`,
type `$19..$1C`, town world 1 or 2, and an explicit outdoor street. Street rooms
`$00..$13` except `$06` were checked against the source headers and generator
entries; all other rooms are excluded. Scripted walkers of the same type have
a different origin and retain their normal behavior.

Four bank-3 first-stage pointers at `$94BF..$94C5` redirect those walking types
to `src/town.inc`. Every action rechecks provenance; other NPC pointers remain
untouched. The code occupies verified filler starting at bank 3 `$B803`.

## Behavior

- Wanderers panic within 48 pixels, or 80 during an attack, on the same floor.
  They choose a direction away from Barba and flee at one pixel per update,
  allowing two-pixel-per-update fireballs to catch them.
- They disappear immediately at a real closed doorway encountered along that
  path, hiding all four sprites without any door animation or background edits. This does not find the nearest
  house across the whole street. Without a door they run offscreen.
- A live player fireball can ignite an eligible wanderer. A brief flame effect
  leaves a charcoal-and-ember pile for about two seconds before removal.
  Both effects reuse its original OAM slots. No extra sprites or quest
  flags are allocated. Ordinary room resets/generation can repopulate the town;
  casualties are not permanent.
- Hold Up while approaching an eligible wanderer for one of four panicked messages, including
  “OH SHIT. / IT IS BARBA. / RUN.” and “FUCK THAT. / I AM OUT / OF HERE.”
  Different wandering types get different lines. B remains attack. Talking
  requires being within 48 pixels on the same floor, grounded and in normal
  play; it cannot interrupt an existing conversation or doorway transition.
  The button is latched until release, preventing repeated reopening. Panic
  dialogue uses a two-update initial delay and one-update letters/line breaks;
  important/indoor dialogue keeps its original timing.
  The native conversation engine handles text, cancellation and movement lock.
  The guarded dialogue hook preserves original selection for every other NPC.

Passive panic shouts also appear automatically in the unused top HUD row.
All twenty padded glyphs are queued at once: no typewriter wait, conversation,
input lock or pause. They last about 100 updates with a 180-update global
cooldown. Busy queues defer the request instead of overwriting native commands.
The row stays fixed while scrolling and restores native blank tiles on expiry.

`src/shouts.inc` uses `$05EA` as a reset guard and `$6460..$6466` for timer,
cooldown, pending message, scene identity and the Up latch, outside the backed
projectile records. Each 23-byte packet appends to the native queue only when
its total stays within 32 bytes and `$0725=0`; menus/dialogue defer it.

Ash uses generated-actor states `$A0..$BF`, two authored sprite pairs at
`$64/$66`, and the town's charcoal/ember NPC palette. It draws only at the
original actor's feet. Ash cannot talk, flee, be damaged again, or alter a
background tile. It expires after roughly two seconds; room reset still clears
actors normally. The art recipe is `assets/ash.json`.

The prototype borrows each generated actor's `$AF` state. The native generator
clears it on spawn. Conversations already in progress finish normally.

## Validation and limits

`tests/town_safety.lua` checks 1,041 eligibility combinations plus eight dialogue
fallback cases, including indoor rooms, scripted origins, important types,
non-town worlds and inactive actors. `tests/town.lua` uses the native Rauru room
loader and generator, then controlled positions to verify fleeing, a real
player-fireball burn/ash/expiry, scripted-walker survival, held-Up dialogue and closure and a
doorway despawn with unchanged collision tiles. `tests/doors.lua` enters an
actual open door with a nearby wanderer and exits back to the correct street.
F8 now loads actual Rauru street room `$01`. The earlier room `$00` was a
lookalike entrance copy without the normal interior routes. Regenerate/load
the new F8 state; old states can contain fake doors from the retired animation.

More towns, door layouts, simultaneous conversations, quest interactions and
healing services still need human playtesting. There is no reputation system,
persistent population loss or alternate quest progression.

`tests/shouts.lua` measures actual PPU visibility within six frames, player
movement without dialogue locks, automatic cleanup and queue budget.
`tests/shout_queue.lua` checks busy queues, prefix preservation, erasure,
scene/dialogue deferral and adjacent-buffer safety. `tests/dialogue_speed.lua`
checks fast panic typing and unchanged protected-NPC delays/register behavior.
