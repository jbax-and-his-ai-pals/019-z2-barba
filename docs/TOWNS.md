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

### Shout word above the villager

The villager who shouts also carries a short word drawn as 8x16 sprites
2 px above its head: type `$19` "SHIT!", `$1A` "RUN!", `$1B` "FUCK!",
`$1C` "NO!". `TownRequestShout` records the actor slot (`$6465`), word
(`$6467`) and a 100-update timer (`$6468`). `BarbaShouts` runs at `$D50D`,
after the native actor loop, and each frame recomputes the word's position
from that actor's `$4E/$3C` minus scroll `$072C/$072A` and `$2A`, so the
word follows the villager as it flees and as the screen scrolls. The native
sprites are placed from the pre-move position, so the word can lead the body
by at most 1 px during a frame of movement. Each glyph is clipped on its own
at either screen edge, with no wraparound. That includes a villager up to
16 px past the left edge. The whole word hides once the villager is further
offscreen, or when the word would reach the HUD.

The word is cancelled for good when the slot stops being that living
generated wanderer: doorway or offscreen despawn (`$B6`), burning or ash
(`$AF`), or a new actor in the slot (`$BC`). It is also cancelled on timer
expiry, on room or world change, and on any dialogue, menu or transition
(`$074C`, `$DE`, `$0726`, mode not `$0B`). Talking skips the native OAM
clear, so the cancel path hides the five entries itself. A burn-triggered
shout therefore shows only the subtitle. Up-to-talk is unchanged.

- **OAM:** five entries, `$E0..$F0`. Natively these are the enemy-projectile
  windows `$E0/$E8/$F0` from the `$D59B` rotation. A census loaded all 63
  town rooms (`$00..$3E`, with walking and fire). No visible entry appeared in
  `$E0..$F4` on any frame without a word. Both town worlds load rooms from the
  same area-pointer table (`$C4BD` offset 0), so this covers them. That
  equivalence was read from the source, not loaded in a world-2 run. They are
  written only while a word is
  live in town play. The word also yields any frame an enemy projectile
  (`$87..$8C`) exists. On a scene change the word is dropped without writing
  OAM, because the new scene may own `$E0`.
- **Tiles:** odd 8x16 tile bytes select the `$1000` table. In towns that table
  is 4K CHR bank 7, the town background bank, which native sprite 0 already
  uses for `$C5`. Twelve decorative BG pairs (`$80..$8C`, `$92`, `$94`,
  `$9C..$A0`) appeared in no town room's nametables in that census. They are
  replaced in bank 7 only. Letters are recolored at build time from the
  user's own ROM font (`$DA` + letter). `!` is authored in
  `assets/shout_glyphs.json`. The build checks a hash of each original pair
  before writing it (`SHOUT_PAIR_SHA256` in `tools/assets.py`).
  `tests/shout_follow.lua` also checks that the dialogue box and the pause
  menu never show those tiles. Palaces never select bank 6/7. The only other
  `SwapCHR #$06` path (`$D04D`, in the post-death sequence) queues HUD and
  palette macros. Its later screens were not traced and are untested.
- **Palette:** town sprite palette 2 (`$0F` black, `$16` red, `$36` pale),
  the same one the ash pile uses. The letters use `$36` with a 1-px black
  outline, which reads over sky and white brick.
- **Scanlines:** standing on the same floor, Barba's three head sprites share
  the word's 16 rows, which makes 8 sprites. A fireball crossing that band
  drops letters first, because `$E0+` has the lowest priority. This is
  cosmetic.
- **Subtitle:** the top-HUD subtitle is kept as the full line. It still appears
  and erases as before (`tests/shouts.lua`).

`tests/shout_follow.lua` checks that the word appears within 4 frames, tracks
the fleeing villager to within 1 px in the same frame through scrolling, and
expires. It also checks that the word hides offscreen, at a real doorway, on
ignition, on a scene change, through an Up conversation and in the pause menu.
Finally, it checks per-glyph clipping at both screen edges.

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
