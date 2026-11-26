# Mouth-anchored breath

`src/tall_player.inc` renders thirteen boss-derived 24x48 poses. Six original body
OAM slots hold the lower rows; three spare slots hold the head. The native
renderer retains item poses, invisibility and flying form. Extracted pixels
stay in local ignored outputs.

The sampled-audio renderer checks for a held item or active raised-head roar
in bank 0 before calling the bank-6 celebration renderer. The ordinary draw
also computes the palette and facing in one pass and keeps the pose index
in X for the tile reads. In the Palace 1 probe, the display call averaged
1,178 → 1,075 cycles during volleys. All 256 OAM bytes matched on every one
of the 1,200 measured idle and volley frames.

The body repeats the boss's narrow segmented neck without an added belly coil.
Vanilla reuses crouch frame 6 during ascent; the renderer selects a separate
full-body jump pose while airborne, leaving native animation and physics state
intact. Airborne low attacks also retain the whole body. A grounded crouch
uses a compact 24px pose with eight pixels of rounded elbow beneath the
head. Elevator contact also selects a compact pose. Boss-defeat shadows (`$DD18` ->
`BarbaBossShadow` in `src/tall_player.inc` via `FarCall0`) also draw all 9
`BarbaTallTiles` sprites into `$026C..$0274` + `$0250..$0264` with black palette 2
so the shadow beside Barba has two torso chunks. Similarly, Dark Barba
(`src/dark_barba.inc`, bank 5 `$9887`/`$99D0`) stands at 48px during the
pre-fight landing pause and keeps full two-torso height on ascending jumps and
airborne slashes.

The player tile allocator reserves sprite pair `$24` for the Myu. The native
draw mirrors that pair for one crawl frame and `$B0` for the other. Barba's
crouch art had overwritten `$24`; the revised layout fits by using the free
player pair `$5C`.

Elevator contact (`$0754 != 0`, set by the native enemy pass) also selects the
compact crouch/crouch-attack art and crouched mouth origin. This is a visual fold:
`$80`, `$17`, movement and the elevator's Up/Down controller stay native. Riding
up or down therefore keeps the head inside the shaft; leaving restores the
ordinary pose. `tall_geometry` checks both poses and mouth placement; `state_pack`
checks the pose during real elevator travel in both directions.

## Shared geometry

`BarbaGeometry` publishes the 8x16 fireball origin in `$05F2/$05F3` and
validity/tuck flags in `$05F6`. Body drawing and new fireball shots use this
geometry. Screen X is actor screen X +28 facing right, or -4 facing left.
Fireball Y is actor Y -12 standing, +4 folded, or +12 crouched. World projectile X
adds the 16-bit scroll with carry. Clipped origins suppress new shots.

Four head corners use the area's native solid-tile predicate through a
single batched bank round-trip at fixed-bank `$FF4C`. Under stone the head shifts down sixteen pixels and the
middle neck row disappears. When grounded on lava (`LAVA_CONTACT != 0`) or in
swamp water (`$0752 != 0`), `GEOMETRY` bit 2 (`$04`) shifts the head and upper
neck down sixteen pixels into the native box and omits the bottom row.
On open floors and under low ceilings, a grounded crouch or crouch attack
draws the full 16px head at the original crouch height. The eight visible
rows below it use the top of the encounter elbow through pairs `$32/$54`.
Their lower halves are transparent, so the pose still fits in 24px. Both
jaw poses mirror with facing and use the existing crouched fire origin.
The cropped bend anchors the horizontal torso
and tip nine pixels higher. The tallest trail column ends immediately
above the brick floor after the PPU's one-line sprite offset. This height
refills the delay buffer while crouched so a previous dip cannot carry the
pieces into the floor. `tall_geometry` checks both facings and jaw poses in
open and low-ceiling fixtures. Core F1 gives an open-floor playtest. Tricky
Movement F2 and Endgame F4 check the head, bend, and trail positions in DMA
OAM under native ceilings.
Movement and enemy-contact collision retain their native sizes: the extra
head height is visual and needs human review.

All native melee origins are hidden after rendering, including up/down thrusts.
There is no attached plume. Item-holding and Wyrmling drawing remain native.
The Wyrmling art (tiles `$68`/`$6A`, wings up / wings down) is the front-facing
`wyrmling` pair in `assets/barba.json`; the native draw never flips it, so the design
stays facing-neutral. The healing-fairy pickup shares these tiles.
`BarbaBlocks` samples each live fireball's center using the original glove-gated
block handler, restoring player pose and velocity so remote fireballs avoid
sword recoil or bouncing Barba. After restoring held thrusts via `BarbaSetThrusts`,
it also runs `$E1DD` for active downstab (`$80 == $09`, temporarily offset +5px
to `$29 + $21` for the tile check and restored to `$29 + $1C` afterwards) and
rising upstab (`$80 == $08`, `$29 - $08`).

Block-animation exhaustion (2026-11-16): vanilla's five records at `$041A-$043C`
used to overwrite slot 0 when full. Breath could abandon a block midway through
its visual erase after its collision tile was already cleared, leaving an
unhittable fragment. Guarded, same-size rewrites in fixed bank 7 at `$E23A` and
`$E0FC` now reserve a record via `$E292` before changing collision. `$E29C`
returns failure on exhaustion; both brick breaking and crumbling floors defer
until a record is free. No ROM padding or RAM is allocated. `combat.lua` checks
pool exhaustion, preservation of all five records, their final four-tile erase,
a successful later breath retry, and both crumbling-floor allocation outcomes.

## Five-shot volley at every health level

Every attack emits five forward/downward fireballs: two pixels horizontally and
two downward per update. Five logical slots now keep an exact eight-update cadence in both stances.
The original two slots and three backed slots retain full projectile range. The volley continues after the attack animation
without locking movement. Holding B does not restart it; B release and an idle
attack state (`$0400 == 0` or standing post-slash recovery `$0400 == 4`) are required before rearming.

- **Dark-cave envelope firelight & rounded glow halo (`src/cave_light.inc`, `src/scanline_irq.inc`, Build #767):** When
  in a West Hyrule / Death Mountain dark grotto without the Candle (`$0736 = $0B`, `$0707 = 0`,
  `$0785 = 0`, `($07AF & $38) = $08`), `CaveFireLightHop6` (`BANK6_HAZE`, called from
  `FinishBossOam6`) fast-returns with 0 bank switches while idle (`$8D | $8E | EXTRA_LIVE | CAVE_GLOW_ON | CAVE_PAL_PEND == 0`),
  and otherwise hops to `CaveFireLight1` (`BANK1_SOULS`) to:
  1. Check live fireball RAM (`$8D`, `$8E`, `$6400`, `$6410`, `$6420` in `1..$7F`, skipping extra slots when `EXTRA_LIVE == 0`)
     and place a rounded, stippled behind-BG (`$20`) Pal-2 (`$02`) OAM glow halo (`$87` from `CHR 00` `$86/$87`, rotating H/V-flip and `±1` px shimmer) in free DMA shadow
     slots (`CLOUD_OAM_START` down to `$60`) behind each live fireball (`$38/$40/$3C/$44/$48`).
  2. Drive a 10-step (`0..9`) envelope in `CAVE_GLOW_ON` (`$64FF`) toward a count-proportional target (`1→4`, `2→6`, `3→8`, `4-5→9` capped), igniting immediately to dim ember (`1`), swelling (`+1` / 3 frames) with top-end PRNG shimmer (`Disp 7..9`), descending (`-1` / 3 frames) as fireballs expire, and fading smoothly (`-1` / 2 frames) back to cold blue (`0`) when none remain.
  3. Queue `CAVE_PAL_PEND` (`$635F`) for VBlank direct palette writes (`CaveApplyPalHop6` → `CaveApplyPal2` in `BANK2_CAVE`, 4 × 18-byte palettes) and update `CAVE_LIGHT_DISP` (`$6741`) so `CaveEmph6` in `IrqSetup6` applies `$2001` emphasis (`$E0` dim / `$20` red tint / `$00` clean) below scanline 31.
     Verified by `tests/cave_light.lua`.

A full pool retries only until the 120-update burst deadline. Each projectile
has a 63-update maximum lifetime (`VOLLEY_LIFE = $3F`, 124 px horizontally) and
is cleared before its Y coordinate wraps. `BarbaLoadOk` caps live player shots
at 2 when `>= 4` enemies are active (and enforces `enemies + live_shots < 7`).
Menus, transitions, death and Wyrmling cancel queued shots. Health is never an
eligibility test. Breath is always fire class (`$05CA = 0`), so Fire-only enemies
take hits without a spell; flame class strictly dominates the native beam (`$D2`)
in bank 7 `$E6CB`. The old Fire slot is METEOR (see below).

In the Valley of Death, exposed rock-tossing Lizalfos (East Hyrule enemy
`$1D`, rooms `$02–$05`) take breath damage through the shared collision
check at `$E48B`. Bank 2's `$977C` hook uses 28 guarded pad bytes at
`$9F85–$9FA0` and checks the throw cycle (AI phase 3). A hit uses the
native hurtbox, HP and death sequence. `tests/rock_lizalfos.lua` drives a
jump and upward volley in room `$02` and verifies the kill and continued play.

State: `$05F1` deadline, `$05F7` spacing, `$05F8` latch, `$05FC/$05FD` projectile
lifetimes and `$05FE` pending-shot count. These locations have no original
references and are cleared by the native reset loop. `$05FF` guards the extra
pool. Three backed records at `$6400/$6410/$6420` and native-window scratch at
`$6440..$6456` use a gap outside collision buffers, room tables and save flags.
They reset on invalid scenes. The backed slots temporarily alias native slot 0
for movement, damage, shields and glove-gated blocks, then restore native state.
Collision wrappers skip inactive/distant shots to preserve frame headroom.

Extra fireballs use OAM `$3C/$44/$48`. The raised head moved to `$04/$4C/$C4` (avoiding `$F8`, which holds the native HUD magic partial-bar sprite),
avoiding the original enemy-projectile slots at `$28/$2C/$30`. During downstab
(`DRAW_FRAME == $51`), unused native sword/shield slots `$20/$24` draw a second
16x16 torso chunk (`$06/$08`) at `DRAW_TOP - $10` unless tucked or clipped by
the HUD/screen edges. Both torso chunks flip horizontally and vertically in place
during downstab: their two tile columns reverse and OAM attribute bits 6/7 toggle,
retaining palette. The turned head keeps its existing attributes.
The downstab-specific torso draw runs in bank 1 and restores bank 0 before
the rest of the player draw. The lag-frame NMI recognizes the bank 1
fingerprint if it interrupts this draw.
The sampled raised-head roar shares a pose across key-item pickups,
crystal placement, Lava Link's entrance and the Triforce hold.
`RoarGemTorso` lifts the head and neck 8px. The upright torso in
`$20/$24` overlaps the neck by 8px and meets the rounded bend at the
original feet height. The bend uses the lower center and rear body slots.
The shadow OAM pass refills the trail history there so the torso and tip
settle on the first roar frame. Facing mirrors the bend and tail.
Tucked, submerged and clipped poses bypass the extension.
`item_roar` checks the left-facing pose and `palace_roar` checks all six
crystals facing right. `link_boss` and `dark_link` check the two boss
ceremonies. Native shots and
their original OAM remain intact. Native enemy and shield entry hooks execute
through fixed-bank gateways and retain the original vulnerability routines.

For other poses, start with **Busy Areas F1** for upstab, downstab and airborne
hurt, **Core F1** for open crouch and the ordinary jump, and **Tricky
Movement F2** for the cropped bend under a low ceiling. The upstab, downstab
and hurt silhouettes have their own lower-row art. **Tricky
Movement F7** exercises the separate pit-fall pose for Barba and his
shadow. **Bosses F8** covers Dark Barba's separate trail renderer, and
**Edge Scenarios F1** can trigger the fatal-hit silhouette. The title cliff
and Zelda ending also place their trails independently.

The default side-view Barba has an elbow, one horizontal torso chunk and a
flick tip in North Palace, towns, palaces, caves, bridges and other encounters.
The same shape appears on the title cliff and in the ending, where it inherits
the body’s curtain priority. Dark Barba draws the torso and tip in his black
palette, in free OAM behind the fight’s actors and projectiles. The overworld
and raft side views show a compact curl within their 16px sprite width.
The art recipes in
`tools/assets.py` derive all three shapes from the original `$06/$08` torso:

- **Elbow corner** (`$34/$36`, 16x16): the torso swept a quarter turn around a
  pivot just outside the top-right corner (`ENCOUNTER_ELBOW`). The belly rides
  the outer arc and the spines thin out on the inner one. It replaces the
  center and rear bottom-body tiles and hides the old front seam.
- **Turned torso** (`$14/$3E`, 16x16): the torso turned 90 degrees
  counterclockwise so the spines point up, at full width, with its outline
  closed on the corner side.
- **Flick tip** (`$44/$30`, 16x16): `ENCOUNTER_TIP_PROFILE` tapers the top
  edge down and curls the end up. It tiles columns 10-12 of the turned torso,
  so the scale pattern carries through, with spines every third column.

Walking, hurt and look-up poses share the idle seam column to free
`$14/$3E/$44`. Two crouch-attack columns share existing pairs to free
`$34/$36`. The crouch-attack neck `$30` shows `$22` instead (16 pixels
differ) to free the far tip column. `tools/trail_candidates.py` writes a
local-only review sheet (`build/trail-candidates.html`) for trying other
corners, torsos and tips.

After `CopyOamShadow6` copies the live sprites, `DrawEncounterTorso` in bank 0
samples lower-body Y in `$6481-$6486`. The torso and tip follow at three
and six frames. The three walk poses add 0, −2 or +2 pixels before
sampling so the sway passes through both pieces. The sampling index
at `$6487` resets for hidden poses and scene transitions. X follows Barba's
current position and facing.
`DrawEncounterTrailSprites` passes the four X coordinates in `$08-$0B`
and their Y coordinates in `$0C-$0F`. A column that wraps off the screen
gets Y `$F8`. In standing, walking,
forward attack and full-height jump poses it swaps in the elbow and lifts
it 1px while the delayed torso rides higher.

The bank-1 pass writes the four columns to shadow OAM `$50-$5C`, behind
Barba, fireballs, projectiles and encounter clouds. Town shouts and Gooma’s
weapon receive their priority slots first. Visible occupants
move to free slots found from `$FC` down to `$60`. If the pass runs out
of slots, it skips the remaining trail columns. `tall_geometry` checks
the delay, join, clipping and full OAM handling. `ow_clouds` checks
both trail facings and sprite preservation in East grass.

### Second horizontal torso trial

The trial inserted a second 16px turned torso using the same two CHR
pairs. Its two extra columns brought the elbow and trail to eight
sprites on shared scanlines, before the player could fire or any enemy
could draw there. The new intermediate joint used the existing six-frame
sample ring, with the torso, second torso and tip following at two,
four and six frames.

| Build | Priority | Result |
| --- | --- | --- |
| `032e6b5abb38` | All six trail columns ahead of enemies | The producer could barely see Bits and Bots while grounded. In the West grass walk-and-fire trace, 454 of 1,071 grounded enemy columns fit on every covered scanline. |
| `7483ee3b9d96` | All six trail columns behind enemies and projectiles | The same trace rose to 1,066 of 1,071. With no controller input at F10, the second torso went 224 consecutive frames without a visible pixel and the tip went 416. |
| `95f9db389858` | Trail first every fourth encounter frame, enemies first on the other three | Both idle blackout streaks dropped to three frames and 906 of 1,071 enemy columns fit in the walk-and-fire trace. The producer still found the sustained tail flicker too strong. |

All three builds ran the same 2,814 sampled West and East grass gameplay
frames with zero lag or HUD shifts. The last variant peaked at 29,713
and 29,271 NMI cycles respectively, versus 29,338 and 29,136 for the
one-torso control `1633f7138573`. The first extra-chunk build also added
10 lag frames in Old Kasuto and two each on the Palace 2 crowded floor
and the Gooma approach in the opt-in Busy Areas trial. The rollout was
reverted after the stationary playtest.

To revisit, use Tricky Movement F10 with no input for 480 frames so
the Bits and Bots can gather. The idle trace skips the first 20 frames
and measures the longest run with no opaque CHR row surviving sprite
evaluation for each chunk. Then run the same walk-and-fire input through
F10 and Endgame F9 for enemy visibility, NMI cycles, lag and HUD shifts.
CPU savings could make more selective sprite placement affordable.
The hardware still evaluates at most eight sprites per scanline and
counts transparent rows within each 8x16 sprite, so the art or placement
must reduce shared sprite spans if priority changes alone still flicker
too much. A narrower one-column extension or a redraw that combines
existing columns would be worth testing before adding two full columns again.

### Connected torso playtest

The local comparison in `build/torso-flow-trial/` keeps the elbow, turned
torso and flick tip at their existing widths and sprite priority. The
Connected build carries the scale colors through the interior seams and
shortens the follow delays from three and six frames to two and four. The
Current build uses the regular art and timing. Both have matching Tricky
Movement checkpoints and separate portable Mesen profiles.

The producer liked the closer join in Connected and saw the Bits and Bots
flicker. High Profile uses Current's three- and six-frame delays, sprite
positions, and priority. It softens the seams and widens the painted join
between the torso and tip within the existing sprite tiles. Open
`play/Test Barba - Torso High Profile.cmd` and press F10. Stand still as the
Bits and Bots gather, then walk, reverse, and jump. Use
`play/Test Barba - Torso Current.cmd` as the control.

The automated F10 comparison sampled 1,556 gameplay frames per version,
starting at rest and then walking, jumping, and firing. The largest vertical
step between torso and tip fell from 15 to 10 px, and steps over 6 px fell
from 242 to 57 frames. Far-tip scanline clipping rose from 114 to 133 frames.
Both versions had zero lag frames, VBlank recoveries, and HUD shifts.
Geometry passed with the expected delay for each version, and the Connected
build passed the East Hyrule cloud and trail regression.

High Profile and Current produced identical shadow OAM for all 1,556
gameplay frames with the same F10 inputs. At least two visible rows of
contact between torso and tip rose from 1,533 to 1,554 frames. High
Profile also passed the unmodified geometry regression and checkpoint
reload validation.

The fatal-hit transition (`$C9EE`) switches to Bank 0 and calls `BarbaDisplay`
directly with `$80 = #$0A`, drawing the full 24x48 hurt pose across the
flashing background (`$076C == $02, $0736 == $03`). During NMI,
`EncounterTorsoFrom6` (`BANK3_DLG`) dispatches `$076C == #$02` through
`DeathTrailPrep3` (`BANK3_SIGN`), clearing `$048D`, `$0752`, `$0754`,
`LAVA_CONTACT`, and `$13` so `BarbaDisplay` and `DrawEncounterTorso` keep the
full black silhouette with its curved elbow (`$35/$37`) and horizontal tail
(`$15/$3F/$45/$31`) intact even if Barba died while flashing, crouched, or
submerged. `death_continue` verifies the 24x48 hurt pose and shadow-OAM
elbow/trail across both facings on every `$076C == $02, $0736 == $03` frame.

Drop-shaft falling (`Game Mode $0F`, bank 0 `$8FB7`) patches `$8FC9` to pose
`$09` and replaces both `$EC02` display calls (`$8FE3` for Barba's black shadow
and `$8FEE` for Barba) with `BarbaFallDraw` (`src/tall_player.inc`, `BANK0`).
After `$EC02` draws the two-row downward head, `BarbaFallDraw` draws two
inverted (`$C0`-flipped) `$06/$08` torso chunks at `head_Y - $10` and
`head_Y - $20` in OAM `$0218..$0227,y` (`$0208..$022F` for Barba,
`$023C..$0263` for his shadow), preserving palette/priority and clipping cleanly
against the top of the screen. The bank-6 shadow pass adds a third chunk at
`head_Y - $30` and the upward-pointing tip at `head_Y - $40`. The tip is
rotated and narrowed from the horizontal art in `tools/assets.py` and uses
pair `$0A`, which previously held four isolated seam pixels. Each actor's
tip reverses the torso's horizontal flip and points up. In DMA OAM, Barba
uses offsets `$08` through `$38` and his shadow uses `$3C` through `$6C`.
The lower OAM indexes give Barba priority wherever the sprites overlap.
Each row clips independently at the top edge. `tall_geometry` checks both
actors and facings in the native draw. `state_pack` checks the full DMA
sprite order and mirrored tips in the Palace 6 drop.

2026-11-16 sprite follow-up: odd-frame priority rotation now swaps only Barba's
outer head sprites. The lower body stays in `$0214-$021F`; the renderer no longer
exchanges it with `$02C8-$02D3` inside the rotating native enemy records. This
removes dragon art from enemy-owned records and is the candidate fix for the
producer's intermittent red ghost during downstab/busy palace combat. The exact
reported ghost has not been reproduced; human confirmation remains open.
`tall_geometry` seeds six live enemies and verifies all six sprites of the native
record survive standing, upstab and downstab drawing on odd frames. The upstab
and downstab fixtures also check that the player's hurt flash covers every visible
part of the pose.

2026-11-17 Dark Barba hurt flash. The native renderer could OR its injury
palette into the shadow's sprite attributes, selecting palette 3 when Dark
Barba took a hit. `DarkBarbaDraw` now preserves facing and priority from the
native attributes and sets the low bits to palette 2 on every visible shadow
sprite. `dark_link` checks the actual palette RAM colors during the entrance
and fight, including the former hurt-flash frames.

The title jaw tables now come from the compiled idle/windup/attack head rows.
The old open-jaw right column `$22` had become crouch art after tile allocation
changed; the correct shared horn column is `$04`. `title_roar` checks all three
complete jaws as well as the unchanged noise-channel roar.

## Ironknuckle shield rebounds

In palace bank 4, Ironknuckles (`$18–$1A`) can send a shield-blocked
downward fireball back at 3.5 pixels per frame. It rises 11 pixels, then
drops. It keeps its damage class, can hit a second enemy, and expires on
solid terrain during descent or after 17 movement updates. A second
shield contact uses the usual clang and disintegration.

The guarded `$E646` hook runs after the native shield overlap and clang.
The rebound puts the shot on the incoming side of the Ironknuckle's body,
clear of its hurtbox. The fractional X speed identifies the rebound
and routes backed shots through the native slot update. The arc reuses the
normal lifetime byte. Both projectile paths use the same hit rules.

`tests/shield_enemies.lua` checks high and low shield coverage and an
airborne shot that comes back to kill a Bot. In Busy Areas F4 before Gooma,
face left and breathe at the approaching Ironknuckle. Look for the fireball
to arc back to the right when you hear the clang.

## METEOR slam (spell slot 4)

Casting sets `$076F` bit 4, which lasts as vanilla Fire did (side-view init `$8CF4` clears it). `BarbaMeteorTick`
(after the HUD split, from `BarbaProjectiles`) starts a dive on mid-air `Down + B`
(`$F7` bit 2, `$F5` bit 6), cancels that attack's volley, and holds `$057D = 6`
until `$0479` clears. `MeteorLand` plays the stomp thud (`$ED |= $10`), a short
decor flash (`$074B = $84`) and emits two shots through the normal allocator with
`INFERNO_AIM = $C1/$C2`. Aim and `VOLLEY_SLOT` flags `$C0` (up + crouch, never
otherwise combined) mean a flat wave at `$29 + $12` with breath's 33-update life (63 held the 2-live-shot cap and throttled the next volley);
`BarbaStepSlotY` and the extra fast path skip Y movement for it. `METEOR_STATE`
is WRAM `$6474`, cleared on any non-gameplay frame.

Bank 0 had 3 free bytes, so METEOR reuses dead vanilla code: the Fire spell body
`$97F1-$9814` (`MeteorLand`), `Check_for_Fire_Spell` `$9847-$9877` (`BarbaMeteorTick`;
its only caller `$D50D` is the `BarbaUpdate` hook) and the raft-avatar tail
`$81C1-$81E4` after the `$81C0` RTS (`BarbaCancelBurst`/`BarbaArmBurst`). `build.py`
guards each full original range.

## HUD timing correction

The spell dispatcher runs before Zelda II's sprite-zero status/playfield split.
Repeated head probes there could make the scroll write arrive late. The spell
pointer now returns immediately, and all spawning runs through `BarbaProjectiles`
after that split. The renderer computes geometry once on ordinary frames; four
terrain corners share one bank round-trip instead of four.

In a 900-frame Palace 1 fixture, the old build's split reached line 42. The
new build stays at line 31 in idle, Fire idle, damaged-health Fire attacks and
full-health attacks with XP display updates. This addresses HUD scroll jitter;
the NES eight-sprites-per-line limit can still cause sprite flicker.

Gooma in Palace 5 draws the ball and chain into four room-specific OAM entries
at `$02A0-$02AF`, freeing his old ball entries for fireballs. While the fight
locks the camera and the ball is on screen, Bank 6 moves those four weapon
sprites ahead of the projectiles and Gooma's body in the DMA shadow. The
eight-sprite limit still applies to other sprites on crowded scanlines.
`tests/gooma.lua` checks the DMA order under load, then finishes the fight with
fireballs and checks the key and exit.

Existing movement, collisions, graphics, lifetime and sound use native handlers.
The volley borrows the boss's timed-fire idea while respecting the player's
native collision rules; it does not copy aimed enemy-projectile code.

## Validation

- `projectile_only.lua`: 16 real-loop health/Fire/facing/stance cases, exactly
  five shots each, muzzle alignment, direction, class and no attached melee.
- `burst.lua`: capacity, lifetime, deadline, held-input/rearm and cancellation.
- `extra_fire.lua`: native-window preservation, extra-slot damage/class, shield
  dispatch, movement/OAM and glove-gated blocks.
- `left_fire.lua`: left-facing shots near edges, across a world page, and with
  both original slots already occupied.
- `combat.lua`: glove-gated fireball brick breaking, restored player state,
  full animation pool / final erase / retry, and crumbling-floor allocation.
- `damage.lua`: real native Bot damage from ordinary and Fire-empowered shots
  in both directions.
- `shield_enemies.lua`: Orange Ironknuckle (`$18`) high/low shield blocking
  and crouching shallow-angle (`$29+$0A`, 0.5 px/frame) low-half hits.
- `gameplay.lua`, `tall_geometry.lua`, `routines.lua`: movement, jumps, ceilings,
  item/Fairy cleanup, disabled thrust collisions, lava and roar.
- `hud_timing.lua`: 900 Palace 1 frames with a stable line-31 split.
- `meteor.lua`: dive, fall cap, two flat fire-class floor waves at `$29+$12`,
  a floor Bot hit, and no dive without the spell.

East Hyrule forest room `$27` spawns Girobokku (`$15`). A headless run of
`f36b2013b860` recorded partial sprite clipping under the eight-sprites-per-line
limit. Every contact hit and kill sampled in that room had drawable eye sprites.
The nearby graveyard uses Moas (`$06`). The original Moa routine at `$DACF`
skips drawing in East Hyrule before the Palace 6 Cross (`$078A`), while contact
damage stays active. Toggling the Cross in graveyard room `$34` confirmed both
behaviors in Mesen.

Carock (Palace 4) has 48 HP and an eight-pip bar worth six HP per pip. An Attack 7
fireball deals 18 HP during his solid visible window (`$AF = $E0–$EF`). Face him
and crouch with Reflect active to return his low bolts for 24 HP each. The fight
takes three fireballs, two returned bolts, or two fireballs and one returned bolt
at Attack 7.

Remaining: shield/boss balance, projectile walls, vertical-technique redesign,
crowded-room sprite review and complete human playtesting.
