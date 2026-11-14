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

- Wanderers panic within 64 pixels, or 112 during an attack, on the same floor.
  They choose a direction away from Barba and flee using native movement.
- They use a real closed doorway encountered along that path, complete its
  native animation, close it and remain inside. This does not find the nearest
  house across the whole street. Without a door they run offscreen.
- A live player fireball can ignite an eligible wanderer. A brief flame effect
  reuses its own OAM slots before removing the actor. No extra sprites or quest
  flags are allocated. Ordinary room resets/generation can repopulate the town;
  casualties are not permanent.
- Press Up near an eligible wanderer for “PLEASE / NO FIRE.” B remains attack.
  The native conversation engine handles text, cancellation and movement lock.
  The guarded dialogue hook preserves original selection for every other NPC.

The prototype borrows each generated actor's `$AF` state. The native generator
clears it on spawn. Conversations already in progress finish normally.

## Validation and limits

`tests/town_safety.lua` checks 1,041 eligibility combinations plus five dialogue
fallback cases, including indoor rooms, scripted origins, important types,
non-town worlds and inactive actors. `tests/town.lua` uses the native Rauru room
loader and generator, then controlled positions to verify fleeing, a real
player-fireball burn, scripted-walker survival, fear dialogue closure and a
completed native door-entry sequence. F8 is a fresh native street checkpoint.

More towns, door layouts, simultaneous conversations, quest interactions and
healing services still need human playtesting. There is no reputation system,
persistent population loss or alternate quest progression.
