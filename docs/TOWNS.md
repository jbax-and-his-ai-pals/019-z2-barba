# Town reactions and dialogue

Use Core F8 for Rauru, Towns and World F2 for Ruto's crowd and Error, and
Towns and World F3 for Saria's bridge hazards. The [checkpoint guide](TEST-PACK.md)
also covers the Rauru crossover and the Key Items F2 mirror handoff.

All live outdoor wandering villagers (`$10..$12`, `$19..$20`) can flee, shout, burn and retreat.
Eligibility (`TownEligible`) requires slot value 1, town world 1 or 2, and an outdoor street
room `$00..$13` except `$06`; origin `$BC` does not restrict eligibility. House-opening
villagers (`$13..$18`, including `$17` healer and `$18` magic-house openers) are excluded from
both `TownEligible` and `TownBurnable`: they keep their native `$97D4` door-emerge/door-open
behavior, stay invulnerable to fireballs, and talk on `B` (or `Up` via `TownCanTalk` /
`TownNativeTalk` at `$9A2C`) using `TownHealerText`, `TownMagicText`, or
native dialogue; when `$17`/`$18` are inside their open doorway (`$AF` `$40..$7F`),
entering (`$0736 == #$16`) jumps directly to `$99E6` so stale off-screen `$C9` never
blocks healing or magic restoration (`tests/heal_door.lua`). Single-area non-town and indoor NPCs (`$0A..$20` excluding `$0C` and `$13..$18`,
in world 1 or 2 rooms except North Palace `$3C`) are covered by `TownBurnable`: they do not flee
and retain their native or custom service dialogue (`$0F` wise-man), but ignite into temporary
ash when hit by a player fireball; `TownHide` clears the slot via `jsr $DD3D` so room-table
NPCs repopulate normally when leaving/re-entering. Invisible triggers (`$0C`, `$21..$22`, including Saria's Mirror and Nabooru's Water of Life Fountain) and North Palace (`$3C`,
handled separately) are excluded. Every
action rechecks eligibility in `src/town.inc`.

## Behavior

- The Mido knight teaches downstab with “JUMP AND HOLD / DOWN FOR A / WYRM DIVE!”.
  The Darunia knight teaches upstab with “JUMP. HOLD / UP TO RAM / HEADFIRST.”
  Both first-time lessons use their original bank-3 message slots (`$A99E` and
  `$ADBF`) and the native unlock and dialogue timing.
- The Saria mirror lady's post-mirror line (`$A656`) is patched in place to
  “OH MY GOD! / MY MIRROR! / FOLLOW ME.”
- Outdoor town rooms (`$0707=1,2`, matching `IsSpriteCloudRoom6`) sway the `$45` green bushes (`$4C-$4F` in 4KB CHR bank 7) on R0 during VBlank via `UpdateGrassPhase6` (`WindBank6` cycling `28, 28, 172, 172, 28, 28, 170, 170` with a 32-frame hold per pose). Only the upper 10 rows (`y=192..201`) lean gently `±1px`, leaving the lower belly and tapering base (`y=202..207`), signs, houses, and ground stationary across all West and East Hyrule villages (`tests/town_bush_sway.lua`).
- Saria Town's street rooms (`$0707=1`, `$056B=2`, `$0561=$06/$07/$08`) have rippling green foul water. `TownFoulWaterChr6` cycles R1 through `146, 148, 150, 152` across all three street rooms using BG palette 1 (`$22` sky, `$37` pale scum, `$2A` foul green, `$0F` shadow). Other town rooms restore base R1. Touching the foul water is lethal to Barba (`LavaSurfaceBody` in `src/farcall.inc`). `tests/saria_quicksand.lua` checks the green/scum/shadow palette across the full width after scrolling, all four ripple phases, lethal contact, and restoration of base R1 in Rauru.
- The bridge guard in Saria's house (room `$1E`) says "FOUL WATER! / LOCALS ONLY. / TURN BACK!" before Bagu's note, and the town sign reads "WELCOME TO / SARIA TOWN. / DON'T DRINK / THE WATER!". The note still selects the crossing dialogue and sets the bridge flag. On the West Hyrule overworld, `OwTerrainPal0` (`src/barba.asm`) renders Saria's terrain `$0A` river channel with green palette `0` (animated via `$6E`, distinct from ordinary blue water `$0C`), `OwSpkKind4` (`src/ow_sparkle.inc`) emits foul-water bubbles instead of lava embers, and `WestFoulWaterTerrain1` (`src/geldarm.inc`) keeps it unwalkable. Open **Test Barba - Saria Quicksand.cmd** (or `--set saria`). **F1** starts on the overworld beside the green foul-water river; **F2** starts beside the guard; **F3**/**F4** show the town bridges.
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
  drew a duplicate door one column left of the real doorway), and house-openers emerging from inside (`L97F5`, `$AF = $81`) recover their doorway from `($4E,x - L9740,y)` and `$3C,x` before `LEA32` probes an adjacent column. Villager panic
  animations defer PPU writes when the buffer is busy.
  The shared renderer at `$9950` checks the full world coordinate and the
  upper door metatile (`$8B`) before queuing any door redraw. The hardware
  reuses a nametable every two world pages, so a late close at Rauru `$0220`
  could draw over the grass at `$0020`. `tests/rauru_rogue_door.lua` forces
  that close and a close aimed directly at the grass, then checks that the
  visible real doorway still redraws. Villagers without a door run offscreen.
  House-opening villagers (`$13..$18`) that spawn hidden
  inside a closed door (`$AF = $80`, `Y = $A8`) stay hidden (`TownHideOAM`)
  rather than mistaking native `$80` for `TownFlee`. They emerge only when
  Barba is really within 96 px of them (`TownOpenerGate`, 16-bit distance):
  native `L97E1` reads `$C9`/`$CD` from whichever actor drew last, so a far
  opener could emerge and its door macro would paint a phantom closed door into
  the visible nametable (`tests/opener_far.lua`). `TownFlee` steps any
  villager above street level (`$2A < $B0`) down `+4` px every 16 frames to `$B0`.
- A live player fireball can ignite an eligible wanderer. A brief flame effect
  leaves a charcoal-and-ember pile for about two seconds before removal.
  Both effects reuse its original OAM slots. No extra sprites or quest
  flags are allocated. Ordinary room resets/generation can repopulate the town;
  casualties are not permanent.
- Hold Up while approaching an eligible wanderer for one of eight panicked messages, including
  “OH SHIT! / BARBA'S / HERE! RUN!”, “IT'S BARBA / EVERYONE / GO INSIDE!”,
  and “BARBA WILL / BURN US! / RUN AWAY!”. Different wandering types and frames
  select across the eight lines. B remains attack. Talking
  requires being within 48 pixels on the same floor, grounded and in normal
  play; it cannot interrupt an existing conversation or doorway transition.
  The button is latched until release, preventing repeated reopening. Panic
  dialogue uses a two-update initial delay and one-update letters/line breaks;
  important/indoor dialogue keeps its original timing.
  The native conversation engine handles text, cancellation and movement lock.
  The guarded dialogue hook preserves native selection for other NPCs, except
  the custom wise-man/healer/magic service lines (native timing retained).
  Message-box padding rule: the expanded town box (`src/dialog_box.inc`, 18×12
  tiles) fits up to 14 characters per line and 4 lines per box, leaving at least
  a 1-tile blank border on all four sides (1 top, 1 left, >= 1 right, >= 2
  bottom for 4-line messages). `TownLine` asserts `<= 14` and encodes A-Z,
  space, `.` (`$CF`), `!` (`$36`), `?` (`$34`) and an apostrophe (`$35`,
  original art in `TEXT_GLYPHS`, `tools/assets.py`). Text tiles must be in
  `$00-$3F` or `$C0-$FC` (the native engine draws byte = tile there).
  East message 36's five mid-dots (`$32`, now shout glyph D) are drawn as
  periods (`tools/build.py`). A post-build guard keeps the font, punctuation
  and box tiles vanilla in bank 7 and fails if any vanilla message byte leaves
  that set (the fire art had overwritten `?`, and shout D the mid-dot, until
  2026-11-16). Panic pointer selection uses `($12 XOR type) AND 7`, copying
  the selected string from `PORTAL_BANK` (Bank 8) into `ARCADE_DLG_BUF`
  (`$63C0`) via `LoadTownDlg3`/`CopyTownDlg8`.

Passive panic shouts are floating sprite words only: no top-HUD subtitle,
PPU text packet, input lock or pause. The global cooldown is 120 updates
(`SHOUT_COOLDOWN = $78`); each word lasts 100 updates.

### Shout word above the villager

The shouting villager carries a phrase drawn as 8x16 sprites above its head.
Phrases with "OH" and "SAVE ME!" use two independently centered rows, with
sprite Y values 16 px apart. "BARBA!" uses a tile that fits "BA" into a single
sprite. This keeps every phrase at five sprites per scanline or fewer. Type
and the `$6469` cycle select the phrase.
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
clear, so the cancel path hides the glyph entries itself. A burn-triggered
request therefore leaves no visible word. Up-to-talk is unchanged.

- **OAM** uses up to seven entries at offsets `$00,$28,$2C,$30,$34,$40,$DC`
  in `$0200-$02FF`. The word yields its shared slots while any enemy projectile
  (`$87..$8C`) exists. A scene change clears the word state and leaves sprite
  setup to the incoming scene. While a villager shout is active,
  `ShoutOamPriority6` in `src/scanline_irq.inc` keeps Barba's sprites in
  `$6500..$6528` and moves the glyphs to `$652C..$6544` for DMA. Barba
  covers the letters he crosses. The five-sprite text budget and Barba's
  three columns fit within the NES limit of eight sprites per scanline.
- **Tiles:** odd 8x16 tile bytes select the `$1000` table. In towns that table
  is 4K CHR bank 7, the town background bank, which native sprite 0 already
  uses for `$C5`. Even bytes select `$0000`, town sprite bank 6. An 8x16 byte
  `T` draws **both** tiles `T&$FE` and `T|1`, so a pair is free only if neither
  tile is town BG, no villager sprite byte selects it, and no menu pane draws it.
  Bank 7 `$00..$27` are villager sprites (River Guard `$01-$07`, Spear Knight
  `$09-$0F`, Fat Woman `$11-$1F`, indoor NPC `$21-$27` in rooms `$2E/$2F`); the
  build refuses to touch them (`TOWN_SPRITE_PAIRS`). Bank-7 glyph pairs: `$32`
  (D), `$7E` (V), `$80`, `$84..$8C`, `$92`, `$94`, `$9C..$A2`, `$A8`, `$AA`, `$BA..$BE`.
  Bank-6 glyph pairs (even bytes; unused Link-only and palace-item/elevator pairs in
  town sprite bank 6; overworld encounters map CHR = PRG bank x2, i.e. 2 or 4, at
  `$CD78`, and towns with Moas like Old Kasuto still drop XP so vanilla XP score
  pairs `$60`, `$6C`, and `$9C..$A6` stay intact via `TOWN_SPRITE_PAIRS[6]`):
  `$66` (X), `$6E/$70` (3/4), `$78/$7A` (1/2), `$7C` (H), `$94/$96/$98` (5/6/7),
  `$AA` (9), `$AC` (8), `$AE` (BA). Bank 7 has no free pair left. During a town combo
  banner (`COMBO_TIER != 0`), `DrawPalaceClouds6` yields the upper parallax cloud
  (`Y < $38`) and `COMBO_BASE_Y = $26` keeps `GODLIKE!` clear of `Y=56` clouds so
  every letter stays within the 8-sprite-per-scanline limit. These
  are replaced in their bank only. Letters are recolored at build time from the
  user's own ROM font (`$DA` + letter). `!` and `BA` are authored in
  `assets/shout_glyphs.json`. The build checks a hash of each original pair
  before writing it (`SHOUT_PAIR_SHA256` in `tools/assets.py`).
  `tests/shout_follow.lua` also checks that the dialogue box and the pause
  menu never show those tiles. Palaces never select bank 6/7. The only other
  `SwapCHR #$06` path (`$D04D`, in the post-death sequence) queues HUD and
  palette macros. Its later screens were not traced and are untested.
- **Palette:** town sprite palette 2 (`$0F` black, `$16` red, `$36` pale),
  the same one the ash pile uses. The letters use `$36` with a 1-px black
  outline, which reads over sky and white brick.
- **Subtitle:** retired. `tests/shouts.lua` checks that the former top-HUD
  subtitle span stays unchanged while the floating word appears.

`tests/shout_follow.lua` checks that the word appears within 4 frames, tracks
the fleeing villager to within 2 px in the same frame through scrolling, and
expires. It also checks that the word hides offscreen, at a real doorway (and
that the doorway's PPU tiles open and close), on ignition, on a scene change,
through an Up conversation and in the pause menu. It also checks per-glyph
clipping at both screen edges, then simulates the PPU's eight-sprite
evaluation on every line of a seven-glyph shout throughout a jump.

`src/shouts.inc` uses `$05EA` as a reset guard and `$6460..$6469` for
scene identity, cooldown, request, actor, Up latch, word, timer and cycle,
outside the backed projectile records. Shouts do not append to native PPU queues.

Ash uses generated-actor states `$A0..$BF`, two authored sprite pairs at
`$7E/$80`, and the town's charcoal/ember NPC palette. It draws only at the
original actor's feet. Most ash cannot talk, flee, be damaged again, or alter a
background tile, and expires after roughly two seconds; room reset still clears
actors normally. Error of Ruto (`$0707=1`, `$056B=1`, `$A1,x=$0E`) is the
exception: `ErrorAshCheck` (`src/sign.inc`) keeps his ash pile persistent until
the room reloads and lets `Up` or `B` open `"I AM / ASH PILE."` (`ErrorAshText`)
through `TownSetNpcDialog` while keeping the ash sprites visible. The art recipe
is `assets/ash.json`.

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
  goes into six town BG tiles in CHR bank 7: flame `$AC/$A4` over `$A7/$C2`, char
  `$C1/$C0` over the same `$A7/$C2` (the flame's lower half is the char's lower half
  since 2026-11-16, which handed `$34` back to the dialogue `?` and `$35` to the
  apostrophe; flame and `$C1` moved 2026-11-14 off `$02/$0E/$04/$16/$25`,
  which were halves of villager sprite pairs; `$35/$C2` moved 2026-11-15 off
  `$96/$B9` so the native pause/spell menu icons stay clean). Index 1 reads orange on brick and white on stone or
  bushes, index 2 brown or gray, index 3 black. The build hash-checks each
  original tile (`TOWN_FIRE_TILE_SHA256`) and that `ScorchTiles` matches the
  JSON, and that quadrants sharing a tile have identical art. Allocation evidence: none of the eight original picks is in a bank-3 town tile table,
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

### Burned signs

A town sign is two metatiles, board `$E3` over post `$E4` (bank-3 constructor
`$9C11`), plus an invisible talk actor: `$22` in world-1 rooms `$00-$06`, `$08`,
`$0C`, `$0E`, `$12`, or `$21` in rooms `$09`, `$0B`, `$0F`, `$11`, `$17`
(emulator census 2026-11-16: every sign room has exactly one reader; the quest
`$21` triggers in rooms `$0D`, `$1A`, `$1E` have no sign; `$0C` never shares a
room with a sign; room `$15` has a sign but no reader). When a fireball scorches the
**board**, reading the sign shows one of six burned lines instead of its native
text: the first read starts on a random line (frame counter `$12` mod 6 at burn
time, producer 2026-11-16) and each later read moves to the next (producer-picked lines, 2026-11-16):
`CHARRED. / YOU CAN'T / READ IT.`, `WELL. YOU / BURNED IT.`,
`WELCOME TO / THIS ASH / PILE.`, `WELCOME TO / WHAT IS / LEFT.`,
`SIGN IS / ASH. YOU / DID THAT.`, `THIS WAS / A SIGN.`

- **Mark:** `BarbaTownBurn` stores `$E3` in `SIGN_PENDING` (`$64D1`). `SignUpdate`
  (`src/sign.inc`, now the update pointer of `$21`/`$22` at `$94CF`/`$94D1`, then
  `jmp $9ABD`)
  copies it into the sign actor's `$04A0,x` when `SCORCH_ROOM == $0561`, and
  clears it. Native spawn (`$D6A8`) zeroes `$04A0,x` on every room load and no
  bank 0/3/7 code reads it, so the mark survives dialogue (which clears the
  scorch ring via `BarbaExtraReset`) and disappears with the char tiles when the
  room reloads. `SIGN_PENDING` is cleared with the ring (`BarbaScorchClear`
  covers `$64B0-$64D1`).
- **Text:** `SignUpdate` seeds `$04A0,x` with a random 1..6 on the first mark.
  `TownOriginalDialog` jumps to `SignDialog`; `$04A0,x` 1..6 picks the
  line and advances (6 wraps to 1), shown through `TownSetNpcDialog`. Text and
  code live in vanilla bank-3 pad `bank3_UNUSED_9D0A` (`BANK3_SIGN`, `$9D0A-$9FFF`).
- **Scroll:** The MMC3 HUD split restores the room's horizontal scroll on
  scanline 31 while town dialogue is open. This replaces the old sprite-0
  scroll write and keeps the sign, background, and dialogue box aligned.
- **Limits:** the post (`$E4`) alone does not count. A scorched board that
  scrolls far enough to be redrawn looks intact but keeps its burned text until
  the room reloads. The census loader returned the same data for `$0707 = 2`, so
  East Hyrule rooms are assumed to follow the same one-reader rule but were not
  separately verified.
- **Test:** `tests/sign_burn.lua`, two cases (Rauru entrance `$22`, room `$09`
  `$21`): native text before, mark on burn (start line 1-6), three reads rotate
  from it, the PPU receives the room scroll throughout scrolled dialogue, and
  native text returns after a room reload.

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
- **OAM & lifecycle.** The banner uses `$DC..$F4, $FC, $34, $64, $AC, $94`.
  The counter uses dedicated early offsets `$00/$28/$2C/$30` so it survives
  crowded scanlines. The `KILL!` row sits at `+$10` and the counter at
  `+$20` for tiers 1–4. On `GODLIKE!` the counter sits at `+$10` and the
  two flanking `$84` flames at `+$03` alternate OAM priority with `E!`.
  The combo suppresses villager `ShoutWord` while active, blinks during
  the final 45 frames, and hides on pause, dialogue, or scene change.
  The `X` and `1`–`9` counter glyphs are even bytes in town sprite bank 6 (see Tiles above); `0` reuses
  the letter `O` glyph (1 px taller than a native `0`) because no pair was left for it. Producer accepted this (2026-11-15).
- **Test.** `tests/town_combo.lua` verifies tier thresholds, counter digits,
  strobe and flames, pause hiding, decay blink, and expiry. It simulates
  sprite evaluation on crowded scanlines for `MULTI KILL!`, `ULTRA KILL!`,
  and a three-digit `GODLIKE!` counter.

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

## Rauru sage basement sequence (`src/sage_basement.inc`)

- In Rauru's sage basement (`$0707 = 1`, `$056B = 0`, `$0561 = $24`), once Barba
  learns Shield (`$077B != 0`) and the spell-learn flash/menu closes, walking
  past halfway toward the left exit (`page == 0` or `page == 1` with `X <= $40`;
  was `$58` before 2026-11-18) triggers a `"WAIT."` message box (`SAGE_STATE`
  `$6475` `2 -> 3`).
- Walking back to the sage (`+-40 px` on page 1, grounded) auto-starts the 5-box
  sequence with no button press, in the same visit or a later one (test walks
  straight back without leaving; it starts at about `X = 153`). The
  sequence is (`"UM..."` -> `"DO YOU / THINK A / SAGE..."` -> `"AND A / DRAGON..."`
  -> `"UM..."` -> `"NEVER / MIND..."`), after which `SAGE_STATE = 8` prevents it
  from ever triggering again.
- If the player leaves the basement without triggering the 5-box sequence,
  `SAGE_STATE` stays `3` so returning to the sage later still triggers it.
  Setting `$048C = 1` in `SageDialogCheck` keeps the custom boxes from
  re-triggering the Wise Man's spell-learn fanfare/menu. Verified by
  `tests/sage_basement.lua`.

## Chimney smoke (`src/town_smoke.inc`)

- Outdoor town rooms (`$0707 = 1, 2`; `$0561 < $19` or `$3C`) lazily scan
  `$6000-$633F` on room change for 2-wide chimney metatiles (`$59`/`$5A`) with
  sky (`$40`) directly above (East Hyrule towns: Nabooru, Darunia, New/Old
  Kasuto).
- `DrawTownSmoke2` (`BANK2_SMOKE` `$A933`, hopped via `HopTownSmoke2` from
  `DrawDownstabTail3`'s `@tail_ret`) draws up to 2 staggered behind-BG (`$21`)
  rising 8x16 puffs per chimney (`$8F`, `$91`, `$93` in `R4` bank `229`) into
  the tail of `$6500..$65FF` (`$65FC` down to `$6568`), so Barba, fireballs,
  combo banners, villagers, and shouts always keep OAM priority.
- To prevent crowding or flicker during busy moments, puffs yield when
  `COMBO_TIER != 0` near the banner (`Y < $48`) or when 5+ foreground sprites
  in `$6500..$6564` already overlap the puff's 16-scanline band. Verified by
  `tests/town_smoke.lua` on Darunia (`world/barba-test.nes`).
