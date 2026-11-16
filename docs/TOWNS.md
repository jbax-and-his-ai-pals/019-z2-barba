# Reactive town prototype

All live outdoor wandering villagers (`$10..$12`, `$19..$20`) can flee, shout, burn and retreat.
Eligibility (`TownEligible`) requires slot value 1, town world 1 or 2, and an outdoor street
room `$00..$13` except `$06`; origin `$BC` does not restrict eligibility. House-opening
villagers (`$13..$18`, including `$17` healer and `$18` magic-house openers) are excluded from
both `TownEligible` and `TownBurnable`: they keep their native `$97D4` door-emerge/door-open
behavior, stay invulnerable to fireballs, and talk on `B` (or `Up` via `TownCanTalk` /
`TownNativeTalk` at `$9A2C`) using `TownHealerText`, `TownMagicText`, or
native dialogue; when `$17`/`$18` are inside their open doorway (`$AF` `$40..$7F`),
entering (`$0736 == #$16`) jumps directly to `$99E6` so stale off-screen `$C9` never
blocks healing or magic restoration (`tests/heal_door.lua`). Single-area non-town and indoor NPCs (`$0A..$21` excluding `$0C` and `$13..$18`,
in world 1 or 2 rooms except North Palace `$3C`) are covered by `TownBurnable`: they do not flee
and retain their native or custom service dialogue (`$0F` wise-man), but ignite into temporary
ash when hit by a player fireball. Invisible triggers (`$0C`, `$22`) and North Palace (`$3C`,
handled separately) are excluded. Leaving/re-entering repopulates the room normally. Every
action rechecks eligibility in `src/town.inc`.

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
  house/quest flags. Native door entry (`$98AB`) is also hooked to
  `TownDoorCoords` / `TownDoorEmerged` so calm/non-panicked villagers entering a door derive the
  exact column and page from `$DC/$DD` instead of `$4E,x + L9780,y` (which
  drew a duplicate door one column left of the real doorway), and house-openers emerging from inside (`L97F5`, `$AF = $81`) recover their doorway from `($4E,x - L9740,y)` and `$3C,x` before `LEA32` probes an adjacent column. PPU writes are skipped if the doorway has scrolled
  offscreen and deferred if the `$0302` PPU buffer is busy. Without a door
  they run offscreen. House-opening villagers (`$13..$18`) that spawn hidden
  inside a closed door (`$AF = $80`, `Y = $A8`) stay hidden (`TownHideOAM`)
  rather than mistaking native `$80` for `TownFlee`, and `TownFlee` steps any
  villager above street level (`$2A < $B0`) down `+4` px every 16 frames to `$B0`.
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
  The guarded dialogue hook preserves native selection for other NPCs, except
  the custom wise-man/healer/magic service lines (native timing retained).
  All `TownLine` strings in `src/town_dialogue.inc` are asserted `<= 11`
  characters so text (which starts at tile 2 of the 14-tile box) never
  overwrites the right border at tile 13.
  Panic pointer selection uses `($12 XOR type) AND 7`, not the old type-mod-4
  table.

Passive panic shouts are floating sprite words only: no top-HUD subtitle,
PPU text packet, input lock or pause. The global cooldown is 120 updates
(`SHOUT_COOLDOWN = $78`); each word lasts 100 updates.

### Shout word above the villager

The shouting villager carries a short word drawn as 8x16 sprites
2 px above its head. Eight phrases rotate: "SHIT!", "RUN!", "FUCK!", "OH NO",
"OMG!", "WTF!", "OH GOD", "HELP!". Type and `$6469` cycle select the phrase.
`TownRequestShout` records the actor slot (`$6465`), word
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
villager: doorway or offscreen despawn (`$B6`), burning or ash
(`$AF`), or an incompatible actor state. It is also cancelled on timer
expiry, on room or world change, and on any dialogue, menu or transition
(`$074C`, `$DE`, `$0726`, mode not `$0B`). Talking skips the native OAM
clear, so the cancel path hides the five entries itself. A burn-triggered
request therefore leaves no visible word. Up-to-talk is unchanged.

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
  uses for `$C5`. Even bytes select `$0000`, town sprite bank 6. An 8x16 byte
  `T` draws **both** tiles `T&$FE` and `T|1`, so a pair is free only if neither
  tile is town BG, no villager sprite byte selects it, and no menu pane draws it.
  Bank 7 `$00..$27` are villager sprites (River Guard `$01-$07`, Spear Knight
  `$09-$0F`, Fat Woman `$11-$1F`, indoor NPC `$21-$27` in rooms `$2E/$2F`); the
  build refuses to touch them (`TOWN_SPRITE_PAIRS`). Bank-7 glyph pairs: `$32`
  (D), `$7E` (V), `$80`, `$84..$8C`, `$92`, `$94`, `$9C..$A2`, `$A8`, `$AA`, `$BA..$BE`.
  Bank-6 glyph pairs (even bytes, unused Link-only art): `$6C` (X), `$78..$7A`, `$7C` (H),
  `$9C..$A6`, `$AA` (digits 1-9), `$AE` (B). Bank 7 has no free pair left. These
  are replaced in their bank only. Letters are recolored at build time from the
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
- **Subtitle:** retired. `tests/shouts.lua` checks that the former top-HUD
  subtitle span stays unchanged while the floating word appears.

`tests/shout_follow.lua` checks that the word appears within 4 frames, tracks
the fleeing villager to within 2 px in the same frame through scrolling, and
expires. It also checks that the word hides offscreen, at a real doorway (and
that the doorway's PPU tiles open and close), on ignition, on a scene change,
through an Up conversation and in the pause menu. Finally, it checks per-glyph
clipping at both screen edges.

`src/shouts.inc` uses `$05EA` as a reset guard and `$6460..$6469` for
scene identity, cooldown, request, actor, Up latch, word, timer and cycle,
outside the backed projectile records. Shouts do not append to native PPU queues.

Ash uses generated-actor states `$A0..$BF`, two authored sprite pairs at
`$7E/$80`, and the town's charcoal/ember NPC palette. It draws only at the
original actor's feet. Ash cannot talk, flee, be damaged again, or alter a
background tile. It expires after roughly two seconds; room reset still clears
actors normally. The art recipe is `assets/ash.json`.

The prototype borrows each generated actor's `$AF` state. The native generator
clears it on spawn. Conversations already in progress finish normally.

## Scorched buildings & ground fires

Fireballs no longer delete town buildings. Each live fireball samples the
16x16 metatile at its center through the native lookup (`$EAE8`, via
`BarbaTownBurn` in `src/blocks.inc`). Walls, roofs, windows, signs, bushes and
street ground (`$50..$5F`, `Y < $C0`) qualify; when a fireball passes through
sky (`$40`) just above ground (`Y + $10`), the ground metatile below it also
ignites. Sky `$40`, doorways `$89..$8C`/`$91`, clouds `$C4..$C6`, and sub-street
rows (`Y >= $C0`) never do. The room's metatile buffer (`$6000+`, which is also
its collision) is never written. Instead the hit queues a 2x2 **flame** into the
nametable through the native PPU buffer (`$0362`, skipped when the buffer is
past `$28`). In towns, flames stay lit for `SCORCH_TOWN_TIME * 4` = 600 updates
(~10 s) and animate every 8 frames (alternating `ScorchTiles` left/right
columns via `ScorchAnimOne`, 2 slots per frame) before `BarbaScorchTick`
rewrites the same spot as **char** with glowing embers (North Palace Zelda
keeps the short 24-update flame stage).

- **State:** 16-entry WRAM FIFO ring (`SCORCH_MAX = 16`): PPU address high/low
  `$6490/$64A0`, timer `$64B0`, head index `$64C0`, world page `$64C1`, plus
  `SCORCH_ROOM` `$646A`. When all 16 slots are burning, a new ignition evicts
  the oldest slot (`SCORCH_HEAD`) to **char** immediately (requiring `$0362 < $1E`)
  and reuses it. `ScorchOnScreen` skips PPU char writes for entries that have
  scrolled offscreen (`[-16, +255]` px from `$072A/$072C`) so nametable wraparound
  never corrupts later screens. A room change (`$0561`) or `BarbaExtraReset`
  clears the ring.
- **Lifetime:** marks live in the nametable only. They vanish when that column
  is redrawn (scrolling about two screens away) or the room reloads. The producer approved this as
  final (2026-11-14): no scorch or casualty persistence after leaving a town.
- **Art:** `assets/town_fire.json` (original 16x16 art, palette indices). It
  goes into eight town BG tiles in CHR bank 7: flame `$34/$AC/$A4/$C0`, char
  `$C1/$A7/$35/$C2` (flame and `$C1` moved 2026-11-14 off `$02/$0E/$04/$16/$25`,
  which were halves of villager sprite pairs; `$35/$C2` moved 2026-11-15 off
  `$96/$B9` so the native pause/spell menu icons stay clean). Index 1 reads orange on brick and white on stone or
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
  Both West Hyrule (`$0707 = 1`, `$0706 = 0`) and East Hyrule (`$0707 = 2`,
  `$0706 = 2`) towns scorch; `$0706 == 0` is only required for North Palace
  (`$0707 = 0`).

### North Palace sleeping princess scorch & Barba shout

- **Trigger:** In the starting palace (`$0707 = 0`, `$0706 = 0`, `$0561 = 0`),
  `BarbaBlocks`/`BarbaBlockSlot`/`BarbaTownBurn` (`src/blocks.inc`) allow live
  fireballs to scorch sleeping Zelda's metatiles (`$4E` head, `$4F` body) into
  2x2 flame and then char without altering collision/metatiles. Other North
  Palace metatiles are ignored.
- **Shout:** Igniting Zelda calls `CastleZeldaShout` (`src/shouts.inc`), which
  sets `SHOUT_SLOT = $FF`, `SHOUT_WORD = 10`, and `SHOUT_WORD_TIMER = $64`
  (100 updates) to float `"OOPS..."` (5 glyphs in OAM `$28..$38`, in front of
  the altar torches `$50..$5C`, zero dropped sprites) above Barba (`$29 - $24`). Leaving the room, pausing, or timer
  expiry cancels and hides it.
- **CHR bank 3:** Flame (`$56..$59`), char (`$5A..$5D`), and odd 8x16 shout
  glyphs (`O,P,S,...` in pairs `$5E..$64`, odd tiles `$5F..$65`) occupy
  previously all-zero tiles in CHR bank 3, hash-guarded in `tools/assets.py`.
- **Test:** `tests/castle_zelda_burn.lua` verifies flame -> char progression,
  unchanged metatiles/surrounding nametable, and the 5-glyph `"OOPS..."` shout.

## Rampage combo banner

- **Scoring (`src/combo.inc`, `src/town.inc`, `src/blocks.inc`):** Igniting an eligible
  villager adds `+3` (`COMBO_ADD` `$646C`) and scorching a fresh building metatile in a
  town adds `+1`, refreshing the 180-frame (~3.0 s) decay timer (`COMBO_TIMER` `$646F`).
- **Tiers:** `12` `MULTI KILL!`, `24` `MEGA KILL!`, `40` `ULTRA KILL!`, `60` `MONSTER KILL!`,
  `85+` `GODLIKE!`. (`DOUBLE KILL!` removed to reduce noise.)
- **Escalation:** Tier 1 uses 8 px spacing and pale palette 2; tiers 2–3 use 9 px
  spacing, fire palette 1, and tier-up jitter; tiers 4–5 use 10 px spacing, palette 1/2
  strobe, continuous `±1`/`±2 px` shake, and two flanking `$84` flame sprites on `GODLIKE!`.
  New tiers trigger `$ED |= $10` SFX and an 8-frame drop-in slam (`COMBO_SLAM` `$6488`).
- **OAM & lifecycle:** Uses 16 town-free OAM slots (`$DC..$F4, $FC, $28..$34, $D8, $64, $AC, $94`) on disjoint
  rows (`+$10` for `KILL!` on tiers 1–4; `+$20` for the centered `X<pts>` combo counter on tiers 1–4, or `+$10`
  directly under `GODLIKE!`, so 8x16 scanlines never overlap; on
  `GODLIKE!`, the two flanking `$84` flames sit at `+$03` to align vertically with the
  glyphs and alternate OAM priority with `E!` on odd frames under the 8-sprite limit),
  suppressing villager `ShoutWord` while active,
  blinking during the final 45 frames, and hiding on pause/dialogue/scene change.
  The `X` and `1`–`9` counter glyphs are even bytes in town sprite bank 6 (see Tiles above); `0` reuses
  the letter `O` glyph (1 px taller than a native `0`) because no pair was left for it. Producer accepted this (2026-11-15).
- **Test:** `tests/town_combo.lua` verifies `<12` inactivity, tiers 1/2/4/5, 2–3 digit `X<pts>` counters, strobe/flames, pause hiding,
  decay warning blink, and expiry cleanup.

## Validation and limits

`tests/town_safety.lua` checks type/origin eligibility, all 14 outdoor
types across both town worlds and all rooms, and all eight panic pointers,
plus native/custom-service dialogue cases, including indoor rooms, origins, protected types,
non-town worlds and inactive actors. `tests/town.lua` uses the native Rauru room
loader and generator, then controlled positions to verify fleeing, a real
player-fireball burn/ash/expiry, scripted-walker behavior, held-Up dialogue and closure and a
doorway despawn with unchanged collision tiles. `tests/doors.lua` enters an
actual open door with a nearby wanderer and exits back to the correct street.
F8 now loads actual Rauru street room `$01`. The earlier room `$00` was a
lookalike entrance copy without the normal interior routes. Regenerate/load
the new F8 state; old states can contain fake doors from the retired animation.

More towns, door layouts, simultaneous conversations, quest interactions and
healing services still need human playtesting. There is no reputation system,
persistent population loss or alternate quest progression.

`tests/shouts.lua` checks actor-owned floating OAM within six frames, player
movement without dialogue locks, word cleanup, the `$78` cooldown, an unchanged
top-HUD subtitle span and native queue budget. `tests/shout_follow.lua` covers
the replacement rendering/lifecycle in detail; the subtitle-only
`tests/shout_queue.lua` is retired. `tests/dialogue_speed.lua` checks fast
letters/line breaks for generated and scripted outdoor villagers, native
protected-NPC delays, and unchanged caller indexes/carry/accumulator behavior.
