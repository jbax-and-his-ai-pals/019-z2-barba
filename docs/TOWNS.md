# Reactive town prototype

All outdoor town villagers (`$19..$1C`, both randomly generated and scripted)
can flee, shout, burn, and retreat into houses. Eligibility requires: live
slot value 1, type `$19..$1C`, town world 1 or 2, and an explicit outdoor
street. Street rooms `$00..$13` except `$06` were checked against the source
headers and generator entries; all other rooms are excluded. Story-necessary
NPCs (`$0B..$18` wise men, healers, and house-opening NPCs; `$1D..$20`
quest-flag walkers; and all indoor actors) retain their normal behavior.

Four bank-3 first-stage pointers at `$94BF..$94C5` redirect types `$19..$1C`
to `src/town.inc`. Every action rechecks provenance; other NPC pointers remain
untouched. The code occupies verified filler starting at bank 3 `$B803`.

## Behavior

- Wanderers panic within 72 pixels, or 96 during an attack, on the same floor.
  `TownPickEscapeDir` picks the direction away from Barba toward the nearest
  doorway (`$8B` / `$91`) or room edge (`$69C4` / `$69C7+1`). They flee at
  0.875 pixels per update (`$0E`/`$F2`), so Barba (`1.5 px/update`) and
  fireballs (`2.0 px/update`) can catch them before they reach shelter, and
  despawn cleanly if they retreat `>= 16` px past the left edge or past the
  right edge.
- When reaching a real closed doorway (`$8B`) along that path, `TownDoor`
  derives the door's exact column and page from `$DC/$DD`, opens the door's
  PPU tiles (`$9946`/`$994A`), walks the villager inside (`$0C..$2B`), hides
  their sprites at `$2C`, and closes the door behind them (`$38..$40` via
  `$9946`/`$994E`) without altering collision RAM (`$6000..$633F`) or
  house/quest flags. PPU writes are skipped if the doorway has scrolled
  offscreen and deferred if the `$0302` PPU buffer is busy. Without a door
  they run offscreen.
- A live player fireball can ignite an eligible wanderer. A brief flame effect
  leaves a charcoal-and-ember pile for about two seconds before removal.
  Both effects reuse its original OAM slots. No extra sprites or quest
  flags are allocated. Ordinary room resets/generation can repopulate the town;
  casualties are not permanent.
- Hold Up while approaching an eligible wanderer for one of eight panicked messages, including
  “OH SHIT. / IT IS BARBA. / RUN.”, “IT IS BARBA. / EVERYONE / GET INSIDE.”,
  and “BARBA WILL / BURN US ALL. / RUN AWAY.”. Different wandering types and frames
  select across the eight lines. B remains attack. Talking
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
  uses for `$C5`. Nineteen decorative BG pairs (`$80..$8C`, `$92`, `$94`,
  `$9C..$A2`, `$A8..$AC`, `$BA..$BE`) appeared in no town room's nametables in that census. They are
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
the fleeing villager to within 2 px in the same frame through scrolling, and
expires. It also checks that the word hides offscreen, at a real doorway (and
that the doorway's PPU tiles open and close), on ignition, on a scene change,
through an Up conversation and in the pause menu. Finally, it checks per-glyph
clipping at both screen edges.

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

## Scorched buildings

Fireballs no longer delete town buildings. Each live fireball still samples the
16x16 metatile at its center through the native lookup (`$EAE8`, via
`BarbaTownBurn` in `src/blocks.inc`). Walls, roofs, windows, signs and bushes
qualify. Sky `$40`, ground `$50..$5F`, doorways `$89..$8C`/`$91` and clouds
`$C4..$C6` never do. The room's metatile buffer (`$6000+`, which is also its
collision) is never written. Instead the hit queues a 2x2 **flame** into the
nametable through the native PPU buffer (`$0362`, at most one 10-byte entry per
hit, skipped when the buffer is past `$28`). After `SCORCH_FLAME` (24) updates,
`BarbaScorchTick` rewrites the same spot as **char** with glowing embers.

- **State:** WRAM ring of eight entries: PPU address high/low `$6470/$6478` and
  timer `$6480`, plus `SCORCH_ROOM` `$646A`. The timer starts at `$FF`. Char is
  queued at `$E7`, and the entry frees at 0 (about 4 s), which also stops a slow
  fireball re-igniting the metatile it is crossing. With eight flames already
  burning, a new hit is skipped. A room change (`$0561`) or
  `BarbaExtraReset` clears the ring.
- **Lifetime:** marks live in the nametable only. They vanish when that column
  is redrawn (scrolling about two screens away) or the room reloads. The producer approved this as
  final (2026-11-14): no scorch or casualty persistence after leaving a town.
- **Art:** `assets/town_fire.json` (original 16x16 art, palette indices). It
  goes into eight town BG tiles in CHR bank 7: flame `$02/$0E/$04/$16`, char
  `$25/$A7/$96/$B9`. Index 1 reads orange on brick and white on stone or
  bushes, index 2 brown or gray, index 3 black. The build hash-checks each
  original tile (`TOWN_FIRE_TILE_SHA256`) and that `ScorchTiles` matches the
  JSON. Allocation evidence: none of the eight is in a bank-3 town tile table,
  and an emulator census of all 126 town rooms (worlds 1 and 2) found none in a
  nametable or odd sprite pair. Both worlds' towns map CHR 6/7.
- **Cost:** about 70 cycles per update for the idle ring scan in outdoor towns.
  No new OAM and no fixed-bank bytes (the tick rides the existing
  `BarbaBlocks` hook).
- **Test:** `tests/town_fire.lua` walks to the Rauru brick house and jump-attacks
  it. It checks that the metatiles are unchanged, flames appear and then become
  char, no tile is blanked to sky, and nothing else in the nametable changes.

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
