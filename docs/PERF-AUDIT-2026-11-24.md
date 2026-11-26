# Barba Edition performance audit, 2026-11-24

**Analyzed:** build #460, ROM `126adc4210e2` (HEAD `bf62382`; a fresh rebuild was byte-identical). Headless
Mesen 2. Nothing in the game was changed. The only repo additions are this report, `tools/perf_stress.py`
and `tests/perf_stress.lua` (the measuring tool), plus log entries in `PERF-LOG.md` and `STATUS.md`.

**How it was measured**

- **Aggressive autopilot on every side-view checkpoint.** All 64 side-view checkpoints in the Core, Busy Areas,
  Palaces, Endgame, Bosses, Movement and Towns sets: about 56 distinct rooms, since several sets share a room. Each
  ran 2-3 times with different input timing, for 360 frames per run (about 64,000 measured frames). The pilot
  breathes every 6 frames (the densest volley rhythm), jumps every ~46 frames, crouch-fires, up-fires while
  airborne, and walks into or backs off the nearest enemy.
- **Real boss fights.** The generic pilot never starts a boss fight; in the Bosses set it only walks the
  antechamber. Real fights were measured by riding the same instrumentation on the existing boss scenarios
  (`horsehead`, `helmethead`, `rebonack`, `carock`, `carock_reflect`, `gooma`, `link_boss`, `lava_link_kill`,
  `dark_link`), about 21,000 frames. Those scenarios clear other enemies and fire sparingly, so each was also run
  a second time with B forced every 6 frames ("max fire", about 38,000 frames). All the normal runs passed their
  own checks. Forced fire makes some fail by design.
- **Spell spam.** Inferno was re-cast every 2 seconds in five rooms.
- **Cycle profiler.** Every executed instruction is charged its 6502 cycles and mapped to a Barba label, a
  `build.py` patch or a vanilla disassembly label. The estimate stays within 1% of the measured NMI time.
- **Sprite-limit analysis.** The DMA shadow (`$6500`) is checked each frame against the NES limit of 8 sprites
  per scanline. It records which object lost lines, and whose sprites caused the overflow.
- **What-if experiments.** Small in-memory ROM patches measured the effect of candidate changes: no tail, a
  two-piece tail, no sprite clouds, town smoke restored, and the fire governor off. These patches change only the
  emulator's copy of the ROM, never a file.

**Budget:** game logic runs inside the NMI. Work longer than about 29,700 CPU cycles misses the next frame, which
slows the game and the music, and can shift the status bar for one frame.

**Not verified:** real hardware, a second emulator, and how the flicker reads to a human eye.

## Bottom line

1. **Lag is concentrated in two places: Old Kasuto, and Rebonack under max fire.**
   - Old Kasuto drops 7% of frames under aggressive play (74 of 1,080). The standard `busy_rooms.py` run drops 8%
     (37 of 461). Sprite clouds account for most of it: with them off, it drops 6 frames instead of 74.
   - The Rebonack fight with constant fire drops 8 frames in a burst, peaking at 39.6k cycles.
   - Every other boss fight stayed under budget even with constant fire.
2. **Fire is not what lags.** Each live shot costs about 1,100 cycles, and the governor holds shots to two whenever
   two or more enemies are on screen. With the governor off, the crowded rooms drop 20-28% of frames.
3. **A quarter to a third of the frame budget is fixed overhead.** About 7,500-9,700 cycles go to work done before
   and after the game logic. The biggest pieces are the OAM shadow copy (~1.8k), sprite clouds (up to 1.7k), bank
   switching (~1.3k), the tail (~0.8k) and a double controller read (~0.4k). The idle Palace 1 corridor has grown
   from 12.1k cycles to 14.2k across recent builds.
4. **Flicker is the bigger visible problem, and Barba's tail drives most of it.** In crowded rooms, 67-86% of
   frames lose sprite lines, with up to 18 sprites on one scanline. The tail's four sprites sit ahead of enemies
   at floor level. Removing only the tail cuts that rate to 2-7% in most rooms. Drawing it with two sprites
   roughly halves it.
5. **Town chimney smoke is broken and has a lag spike.** Since Build #330 the smoke draws only while Barba
   downstabs, and `tests/town_smoke.lua` fails. The first downstab in each town room runs a 15,000-cycle chimney
   scan. That drops a frame and jolts the status bar.

## 1. Where it lags

Aggressive autopilot, 1,080 measured frames per checkpoint unless noted. "Peak" includes dropped frames.
"Over 27k" counts frames within about 2,700 cycles of the limit.

| Checkpoint (F-key) | Dropped frames | Avg / p95 / peak cycles | Over 27k | Notes |
| --- | --- | --- | --- | --- |
| **Old Kasuto** (Busy F9, Towns F8) | **74** (busy_rooms: 37 of 461) | 25.5k / 30.6k / 44.2k | 285 | 5 Moas, town chaos, sprite clouds. Status bar jolts on 6 frames. |
| Palace 2 crowded floor (Busy F5, Movement F4) | 2 (busy_rooms: 13 of 460) | 25.4k / 27.4k / 30.3k | 115 | Enemy logic heavy. busy_rooms walks into the crowd. |
| Palace 5 before Gooma (Busy F4, Palaces F10) | 1 (busy_rooms: 6 of 460) | 23.4k / 27.1k / 30.5k | 62 | |
| Darunia, Nabooru, core town (Towns F6, F5; Core F8) | 1-2 each | 23.3-24.0k avg, peaks 37.8-43.6k | 6-17 | Each drop is the one-time chimney scan (section 4). |
| **Rebonack fight, max fire** (Bosses F3) | **8 of 2,766** | 20.5k / - / **39.6k** | 390 | Drops come in a burst late in the fight, with three enemy slots active. The 39.6k frame spends 3.8k swapping shot records through slot 0 for collisions, 2.5k on ~44 bank switches and 2.1k on the Souls bar remap. |
| Rebonack fight, scenario's own fire | 2 of 2,521 | 19.3k / - / 30.9k | 149 | |
| Lava Link (Bosses F6; real intro and fight) | 0-1 | 20.9-21.4k / - / 30.4k | 68-175 | |
| West grass (Movement F10) | 0 | 23.0k / 26.9k / 29.7k | 43 | 30 cycles from the limit at peak. |
| East grass (Endgame F9) | 0 | 20.7k / 25.8k / 29.1k | 8 | |
| Every other checkpoint | 0 | p95 at or under 26.5k | 0-24 | |

With max fire (up to 5 shots against the boss and 6 boss projectiles), the other boss fights stayed lag-free:
Horsehead peaked at 28.4k, Helmethead 28.6k, Gooma 27.5k, Carock 25.0k, Dark Barba 25.9k and Lava Link 29.4k
(222 frames over 27k). Inferno spam never lagged, because the governor gates its waves too; the Palace 2 floor
peaked at 29.7k. The overworld runs 6.7-11k cycles on average.

**What each thing costs.** These are marginal cycles per frame, from a regression over 63,000 frames within each
scene:

| Item | Cycles each |
| --- | --- |
| Live Barba shot | ~1,110 (about 500 to move it, 400 for its block/burn tile check, 200 for collisions) |
| Active enemy | ~1,650 |
| Enemy projectile | ~750 |
| Sampled roar playing | ~340 |

**The governor works.** `BarbaLoadOk` holds Barba to two live shots whenever two or more enemies are active. With
it patched off:

| Room | Dropped frames per 1,080 | Status bar jolts |
| --- | --- | --- |
| Palace 2 floor | 272 | 124 |
| Gooma approach | 216 | 107 |
| Old Kasuto | 305 | 174 |

Any cycles saved elsewhere can be spent loosening it.

## 2. Where the frame goes

**NMI phases.** Averages per frame. "Pre" is the vblank work, sound, controllers and setup. "Post" is the OAM
shadow copy, the priority pass, the tail and the clouds.

| Room | Pre | OAM clear | Game logic | Post | Fixed share |
| --- | --- | --- | --- | --- | --- |
| Palace 2 floor | 3.7k | 0.7k | 17.5k | 3.4k | 31% |
| Old Kasuto | 3.9k | 0.7k | 15.6k | 5.0k | 38% |
| West grass | 3.7k | 0.7k | 15.2k | 3.2k | 33% |
| Carock room | 3.7k | 0.7k | 9.6k | 3.2k | 44% |

**Subsystems in heavy frames.** Frames at or above 25,000 cycles (4,971 of them) average 27.5k cycles:

| Subsystem | Cycles | Share |
| --- | --- | --- |
| Vanilla Zelda II code (mostly enemies) | 14.2k | 51% |
| OAM shadow copy + priority (`CopyOamShadow6` alone ~2.0k) | 2.5k | 9% |
| Patched vanilla: OAM clear 0.7k, offscreen mask 0.9k, NMI tail | 2.3k | 8% |
| Town chaos: combo banner, burn, scorch, shouts | 1.6k | 6% |
| Bank switching (~22 `SwapPRG` calls at 58 cycles; only 4.5% redundant) | 1.4k | 5% |
| Body render + head geometry (`BarbaCeiling` 0.28k) | 1.2k | 4.5% |
| Fire | 1.1k | 4% |
| Sprite clouds (1.3-1.7k in rooms that have them) | 0.9k | 3.4% |
| Tail (trail) | 0.85k | 3% |
| Scenery CHR and IRQ setup | 0.6k | 2% |
| Sampled audio | 0.3k | 1% |

**Largest vanilla costs:** `Generic_Collision_Test_with_Level_Objects` (0.9-2.2k; ~22 calls at 95 cycles in a
heavy frame), object physics, enemy sprite assembly and contact boxes.

**Controller read:** vanilla reads both pads twice until they match (~460 cycles). During roars, `RoarReadPads`
adds another double read.

## 3. Flicker

**Crowded rooms**

| Room | Frames that lose lines | Lines lost per frame | Most sprites on a line | Enemy visibility toggles per second |
| --- | --- | --- | --- | --- |
| Palace 5 before Gooma | 84-86% | 27-34 | 18 | 53-67 |
| Palace 2 floor | 82% | 16 | 14 | 39 |
| Core combat (F2) | 72% | 13 | 14 | 38 |
| Palace 1 before Horsehead | 67% | 11 | 14 | 42 |
| East grass | 55% | 14 | 17 | 21 |

Boss fights reach 19-20 sprites on a line and lose lines on 17-36% of frames.

**Who causes the overflow.** The what-if runs below are the direct evidence. As supporting detail, this is the
share of lost lines that would disappear if one part of Barba's sprite set were removed. It is computed from each
frame's sprite list, so a displaced enemy sprite that uses palette 0 can be miscounted as tail.

| Room | All of Barba | Tail only | Body only | Fire only | Head side pieces |
| --- | --- | --- | --- | --- | --- |
| Palace 2 floor | 96% | **88%** | 77% | 14% | 0% |
| Gooma approach | 88% | 63% | 58% | 9% | 3% |
| Core combat | 97% | **91%** | 72% | 14% | 1% |
| Old Kasuto | 89% | 80% | 77% | 22% | 0% |
| West grass | 100% | 100% | 93% | 28% | 0% |
| Palace 1 entrance (Barba alone) | 100% | 100% | 98% | 97% | 0% |

**The tail is the main cause.** It occupies DMA entries `$50-$5C`, ahead of every enemy, on the floor rows where
enemies walk. That ordering follows your earlier call: "enemies flicker before clouds; clouds flicker before tail."
Barba's lower body and tail put up to 7 sprites on those rows, leaving one slot for enemies.

**Barba also flickers himself:**
- With 3-5 shots in flight, the tail tip loses lines on 20-28% of frames, because fireballs come first in OAM
  order.
- The head's third column is native OAM `$C4`, the last of Barba's entries. Near tall enemies it loses lines on
  13-16% of frames, so part of the head blinks.

**Tail options, measured.** Percent of frames that lose lines, current tail versus alternatives. The tail-last row
is a simulation from the same frames.

| | P2 floor | Gooma | P1 Horsehead | Old Kasuto | West grass | East grass | Combat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Current (tail ahead of enemies) | 82 | 84 | 67 | 50 | 34 | 55 | 72 |
| Two-piece tail (no tips) | 40 | 58 | 28 | 12 | 6 | 40 | 32 |
| No tail | 5 | 32 | 2 | 5 | 0 | 31 | 7 |
| Tail last: enemies lose lines | 13 | 39 | 15 | 11 | 0 | 32 | 7 |
| Tail last: tail itself loses lines | 72 | 61 | 52 | 39 | 34 | 37 | 69 |

The lost lines are zero-sum. Something on those rows has to blink, so the choice is which: the tail, the enemies,
or fewer tail pieces.

## 4. Bugs found

1. **Town chimney smoke is off.**
   - `DrawTownSmoke2` is reached only through `DrawDownstabTail3` (`@tail_ret: jmp HopTownSmoke2`).
   - Build #330 gated `DrawDownstabTailHop6` to downstab frames (`DRAW_FRAME == $51`), so smoke now draws only while
     Barba downstabs.
   - `tests/town_smoke.lua` with the Towns pack ROM fails: "Darunia detects chimneys (0)", no puffs, no rise.
     It passed on 11-22.
2. **The chimney scan costs a frame.** `ScanTownChimneys3` reads four pages of room data in one frame, about
   14,900 cycles.
   - It runs on the first smoke call in a room, which is currently the first downstab.
   - Peaks: 44.2k in Old Kasuto, 43.6k in Darunia, 42.4k in Nabooru, 37.8k in the core town.
   - Each one drops a frame and shifts the status bar.
3. **The rescan key is stored wrong.** When only the room changes, `DrawTownSmoke2@rescan` stores the room number
   into `SMOKE_WLD`. The next frame then mismatches and scans again: two dropped frames per room change.
4. **`SMOKE_BANDS` overlaps other WRAM.**
   - `SMOKE_BANDS` (`$635B-$636A`) overlaps the Souls bar's `SOULS_SAVED_BG`, `SOULS_BG_DIRTY` and `SOULS_BG_VALID`
     (`$635B-$635D`), and the first foliage slots (`OW_FOL_HI`, `$6360-$636A`).
   - It is latent. In four town runs with smoke forced on, the Souls dirty flag was never set. That needs a sprite
     in the top 32 lines during a smoke frame, and would recolor the town background.
5. **Several probe columns are stale.**
   - `busy_rooms.py` `workMax` is always 0. `NmiWorkEnd` (`$C1A2`) is only on the non-gameplay NMI tail; gameplay
     returns through `NmiRng6`'s `jmp $C1A5`.
   - The `extra`, `collisionCalls` and `blocks` columns in `perf_volley` and `perf_upward` read 0. Their exits assume
     the next exported label follows each routine.
   - The six-Bot `perf_upward` now has 268 of 900 firing frames over 27k, up from 13 on `4756353e62d0`. The peak is
     27,652, with no lag yet.
6. **Benign: a nested NMI.** When the work ends between `NmiRng6`'s `bit $2002` and `$C1AE`'s `STA $2000`, a fresh
   NMI fires immediately. It nests inside the old one (3 extra stack bytes), and it starts on time. Seen 1-4 times
   per 360 frames in Old Kasuto.

## 5. Recommendations, ranked by what you'll see

Savings are measured where marked. The rest are estimated from profiled routine costs. Nothing below has been
applied.

| # | Change | Gain | Risk / space |
| --- | --- | --- | --- |
| 1 | **Make sprite clouds cheap or conditional.** Cheapest: skip `DrawPalaceClouds6` while 4+ enemies or a combo are active, since clouds sit behind the BG and lose lines first anyway. Better: rewrite it with zero-page temps and precomputed tile/attribute bytes. | **Measured:** clouds off saves 1.3-1.7k/frame in every cloud room, and Old Kasuto drops fall 74 → 6. Rewrite estimate: ~1k. | Low. `BANK6_HAZE` has 0 bytes free, so code must move. |
| 2 | **Choose a tail flicker policy** (section 3). Cheapest change: draw two pieces when 3+ enemies are active; the piece loop bound is `CPY #$04` in `DrawEncounterTrailSprites1`. | **Measured:** halves lost-line frames in crowds and saves ~0.15k/frame. No tail saves ~0.3k. | Low. Your call on the look. |
| 3 | **Restore town smoke properly.** Hop only in outdoor towns (`$0707` = 1-2). Scan chimneys during the room load, or one page per frame. Fix the `SMOKE_WLD` store. Move `SMOKE_BANDS` to free WRAM. | Fixes bugs 1-4. **Measured cost to budget:** +0.25-0.4k/frame in most towns, +1.4k in Darunia (2 chimneys), and +0.24k in every other room if the old always-hop returns. | Low-medium. `BANK2_SMOKE` has room. |
| 4 | **Move the head's `$C4` column to an early shadow slot** in the priority pass. | Stops the head blinking (13-16% of frames near tall enemies). ~40 cycles. | Low. Bank 6 is nearly full (8 bytes). |
| 5 | **Check each shot's blocks/burn tiles every other frame.** Shots move at most 3 px per frame against 16 px tiles. | ~200 cycles per live shot per frame. | Low. A block breaks at most a frame later. |
| 5b | **Cheaper backed-shot collisions.** `ExtraCollision` copies an 11-byte shot record into native slot 0 and back for every nearby shot-enemy pair, for both the enemy and the shield check. Keep the loaded record when the next check needs the same one, or loop shots outside enemies. | Up to ~3k in big-hitbox fights; this is behind Rebonack's 39.6k max-fire frame. | Medium: touches collision. |
| 6 | **Single controller read synced to the OAM DMA** instead of read-until-match, also in `RoarReadPads`. | ~230 cycles/frame (more during roars). | Medium: timing-sensitive. Keep pad 2 for the Up+A save. |
| 7 | **Fewer far calls.** Co-locate the tail renderer and the per-frame town code with their callers (bank 0 → 1 → 0, bank 6 → 3 → 6, and so on). | ~0.25-0.45k/frame. | Medium: bank space. |
| 8 | **OAM shadow copy.** Unroll 4×, or for the big win DMA from `$0200` and do the tile rebase and priority in place. | ~0.18k unrolled, ~1.5k in place. | Unroll: low, needs ~60 bytes in bank 6. In place: high. |
| 9 | **Small caches.** `BarbaCeiling` keyed by tile coordinates; `IsSpriteCloudRoom6` once per frame instead of twice. | ~0.2k/frame. | Low. |
| 10 | **Spend the savings.** After 1, 3 and 5 land, consider a three-shot cap when two or three enemies are active. | Each extra shot costs ~1.1k. | Re-measure with the tool. |
| 11 | **Vanilla engine.** Cache per-enemy tile probes in `Generic_Collision_Test_with_Level_Objects` callers. | Up to ~1k in crowded rooms. | High: touches vanilla physics. Last. |

**Probe fixes** (trivial, not applied):
- Export `NmiWorkEnd` as the gameplay return (`$C1A5` with the Souls bar, `$C1A3` without).
- Point the `perf_*` sub-spans at real routine exits.

## 6. Questions for you

1. **Tail versus enemies.** In crowds, who blinks: the tail (tail last), the enemies (today), or a shorter tail when
   3+ enemies are active?
2. **Clouds.** Is it OK to drop the sprite clouds during busy fights, or should they stay and get the rewrite?
3. **Town smoke.** Restore it, at a cost of 0.25-1.4k cycles per town frame, or retire it?
4. **Reclaimed cycles.** Should they go to more fire (loosening the governor) or stay as headroom?

## 7. Reproduce

```text
python tools/create_test_pack.py --set busy        # also core, palaces, endgame, movement, world, bosses
python tools/perf_stress.py matrix                 # all side-view sets, profiled (~7 min)
python tools/perf_stress.py summary --tags "m-*"   # lag / cycles / flicker per checkpoint
python tools/perf_stress.py profile --tags "m-*" --kind heavy --buckets
python tools/perf_stress.py run --sets busy --patch notrail --tag wi-notrail      # what-if
python tools/perf_stress.py compare base:wi-base notrail:wi-notrail
python tools/perf_stress.py overlay rebonack link_boss lava_link_kill             # real boss fights
python tools/perf_stress.py overlay --fire 6 --profile rebonack                   # same, B every 6 frames
```

`create_test_pack.py` rewrites `build/test-pack/current.json`, which the Test Barba launcher reads. Regenerate your
preferred set last.
