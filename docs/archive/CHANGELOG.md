# Chronological changelog (archived)

Historical session-by-session development log moved from docs/STATUS.md and docs/TEST-PACK.md.
For the current build state, see [STATUS.md](../STATUS.md).

## Status log (through 2026-11-17)

2026-11-17 Drop-shaft 64px torpedo pose on `3b99bac7625f`. When falling through
palace drop shafts (`Game Mode $0F`, bank 0 `L8FB7`), patched `$8FC9` to
downstab pose `$09` and replaced both `$EC02` calls (`$8FE3` shadow, `$8FEE`
Barba) with `BarbaFallDraw` (`src/tall_player.inc`, `BANK0`, leaving `767` B
free in default `BANK0` and `779` B in `--native-audio`). Both Barba
(`$0208..$022F`) and his black shadow (`$0230..$0257`) now render the 2-row
downward-turned head plus two inverted (`$C0`-flipped) `$06/$08` torso chunks
above it (64px total, clipping cleanly at the top edge as they enter).
- Verification: `python tools/build.py` and `--native-audio` builds pass; all 23
  ROM-free unit tests, `tall_geometry.lua` (Barba & Shadow both facings + top
  clips), `death_continue.lua`, `upstab.lua`, and all 9 regenerated and
  validated test-pack sets (69 checkpoints, including 87 live `Game Mode $0F`
  frames in `p6-drop-shaft`) passed (`build/barba.nes` == `play/barba.nes`,
  SHA-256 `3b99bac7625f8d2ac2931a60c8bfab4e5b4bcaf5191dbb12a6abfe363632146f`).
  Playtest: `play/Test Barba - Tricky Movement.cmd` (`F7` Palace 6 drop-shaft
  edge, walk right into the gap to watch Barba and his shadow torpedo downward).

2026-11-17 Overworld flame centering on `41c85b1ae8a7`. Shifted `OwFlameX`
(`src/barba.asm`) by `+4` px (`$80/$90/$70` -> `$84/$94/$74`) so the 8x16
overworld flame sprite sits centered horizontally on the 16x16 target tile in
all directions instead of left-aligned. Added right- and left-facing `$02FF`
centering checks (`$94` / `$74`) to `tests/overworld_fire.lua` and visually
confirmed centered placement over the scorched forest tile in
`build/ow-tree-burn.png`.
- Verification: all 23 ROM-free unit tests, `overworld_fire.lua`,
  `forest_burn_limit.lua`, `overworld_side.lua`, and all 9 regenerated and
  validated test-pack sets (69 checkpoints) passed (`build/barba.nes` ==
  `play/barba.nes`, SHA-256
  `41c85b1ae8a7365e2e6181bcb4783eae04f46e439cca3881fe706b96130d64a6`).
  Playtest: `play/Test Barba.cmd` (`F1`, exit North Palace right, walk right/up
  to forest, face a tree and press `Left Shift` / B to verify the flame is
  centered over the burnt tile).

2026-11-17 Bank-6 co-processor & NMI optimization pass on `af17608cd5b0`.
Unlocked 3,575 untouched `$FF` bytes in bank 6 (`$AC09-$B9FF`) by expanding
`BANK6` (`$AC09-$BF6F`, 4,967 B total; **2,680 B free** in default sampled
build, **2,688 B free** in `--native-audio`), moved `ScalesTick`,
`DarkLinkFireCheck`, `CastleZeldaShout`, and the town/castle scorch engine
(`BarbaTownBurnBody`..`ScorchTiles`) into `BANK6`, shared `ExtraSaveZero`/
`ExtraRestoreZero` with `ExtraStoreRecord`/`ExtraLoadRecord`, added idle fast
paths (`BarbaShouts` non-town/unshielded skip, `BarbaExtraUpdate` deferred stack
save, `BarbaProjectiles` `$8D | $8E == 0` skip, removed redundant `@draw` loop,
removed duplicate `BarbaBurstAllowed`), skipped the right-edge `$EAE0/$EAE4`
lookup on same-page `BarbaGeometry` probes (`bcc @same_page`), and rewrote bank 7
`$D5DA-$D5F8` to skip `$F27D` on empty enemy slots (`$B6,X == 0`) and
direct-dispatch states 1/2/3 (`$D5F6-$D5F8` 3 bytes spare).
- Free space gained: `BANK0` grows from 4 B free to **873 B free** (885 B
  legacy), `BANK6` from 2 B to **2,680 B free**, and `BANK3_SIGN` from 146 B to
  **255 B free**.
- Benchmarks (`0` lag frames, `0` late splits, `0` HUD shifts everywhere):
  - `perf_volley.lua`: idle `11,971 avg / 12,035 peak` (was `12,950 / 13,014`),
    volley `15,045 avg / 20,894 peak` (was `15,929 / 21,631`).
  - `perf_meteor.lua`: `13,262 avg / 15,117 peak` (was `14,917 / 16,792`).
  - `perf_upward.lua` (6 active Bots): idle `22,866 avg / 23,113 peak`, upward
    `24,149 avg / 24,834 peak` (was `25,300 / 25,984`).
  - `perf_lava.lua`: floor `15,800 avg / 16,573 peak` (was `16,792 / 17,566`),
    lava `15,311 avg / 17,309 peak` (was `16,322 / 18,328`).
  - `busy_rooms.py` (default & `--sets busy`, 480 frames/state): `old-kasuto`
    `28,224` work / `28,247` NMI max (was `29,057`), `p2-crowded-floor`
    `27,848 / 27,871` (was `28,517`), `p5-gooma-approach` `26,743 / 26,766`
    (was `27,525`), `p3-ironknuckle-blocks` `24,000 / 24,023` (was `24,963`).
- Verification: all 23 ROM-free unit tests, all 67 standalone Mesen scenarios,
  all 9 regenerated test-pack sets (`state_pack.lua` validation), and both
  `busy_rooms.py` runs passed (`build/barba.nes` == `play/barba.nes`, SHA-256
  `af17608cd5b0337f2b847aa37a9efcd7fe85c077f926acc1326ef157494efeae`).
  Playtest: `play/Test Barba - Busy Areas.cmd` (`F4` Old Kasuto, `F5` Palace 2
  crowded floor, `F8` Gooma approach) and `play/Test Barba.cmd` (`F2` volley,
  `F3` spells/SCALES, `F9` Dark Barba).

2026-11-17 checkpoint placement fix on `9c0add7a0040`. Eight states across
Busy Areas, Palaces, and Tricky Movement now spawn on walkable ground near
center. The original F6 camera held Barba at the left edge as he walked.
Reload checks now verify both framing and rightward movement in these states.
[Horizontal placement audit](TEST-PACK.md#horizontal-placement-audit).

2026-11-17 regression pass on `9c0add7a0040`. All 23 ROM-free tests, 67
standalone Mesen scenarios and 69 checkpoint reloads passed. The routine
harness now checks the sampled Inferno request or legacy noise envelope as
appropriate and expects the current right-facing downstab tile order. It
passes on both audio builds. Rendered checks included all burned-sign
messages, technique lessons, BREATH, the ending and all 20 credit entries.
The Busy Areas probe now reports room-load NMI costs separately from
side-view gameplay. The longer run recorded zero gameplay lag or HUD shifts
over 23,338 measured side-view frames. Hardware sprite-limit flicker remains
visible in crowded scenes and in the top-tier combo banner.
[Test results and playtest keys](TEST-PACK.md#november-17-regression-pass).

2026-11-17 enemy projectile updates. Empty slots skip the offscreen mask.
Live shots use a shorter contact parity check. The P2 crowded-floor
stress peak fell from 30,157 to 29,682 cycles before HUD recovery and the
one lag frame disappeared. All ten Busy Areas rooms had zero lag and HUD
shifts. The Horsehead and Gooma approaches saved 397 and 564 cycles per
comparable update on average, with identical sprite output. Playtest with
`play/Test Barba - Busy Areas.cmd`, F8 for Guma hammers and F5 for the
crowded floor. [A/B replay details](TEST-PACK.md#overlapping-player-and-enemy-projectiles).
All 68 checkpoints were regenerated and reload-validated. The Busy Areas
probe reproduced the A/B timing with the new pack. All 23 unit tests and
the combat, damage, shield enemies, Wizzrobe, HUD timing, volley, METEOR
and town safety scenarios passed.

2026-11-17 busy palace performance profile. On build `59ee6701557a`, all
ten Busy Areas checkpoints had zero lag and HUD shifts. Palace 2 peaked at
29,004 cycles, with 13,776 in the enemy pass. Offscreen mask calls for empty
enemy projectile slots took 534 cycles on that frame. Palace 5 before Gooma
exceeded eight sprites on a scanline on 104 of 600 frames. See
[`TEST-PACK.md`](TEST-PACK.md#busy-palace-performance-profile) for the
profile and optimization candidates.

2026-11-17 projectile stress. In the 850-frame probe, Horsehead's approach
peaked at 25,635 cycles with two fireballs and four Guma hammers. The longer
Palace 2 run had one lag frame at 30,157 cycles before LateSplit, with zero
HUD shifts. Mixed-projectile frames exceeded the sprite limit 147 times
before Gooma. See [projectile stress results](TEST-PACK.md#overlapping-player-and-enemy-projectiles).

2026-11-17 Barba renderer. Ordinary frames skip the inactive celebration bank
switch and reuse the computed tile index. In Palace 1, volley frames now
average 16,684 CPU cycles (previously 16,788), peak at 22,376 (previously
22,490), and have 0/900 lag frames. The full sprite table matched on all
1,200 measured idle and volley frames. Each Busy Areas room saved 109–120 peak
cycles with zero lag and HUD shifts. Candle, gem and tall geometry passed,
including tall geometry in the legacy audio build. All 68 checkpoints were
regenerated and reload-validated. Open `play/Test Barba.cmd`, press F2, and
walk, turn, crouch and fire in both directions to check the neck animation
and clipping around the corridor.

2026-11-17 technique lessons. Mido teaches the wyrm dive and Darunia teaches
Barba to ram headfirst. Both lessons include the jump and direction inputs.
Open `play/Test Barba - Towns and World.cmd` and use F4 for Mido or F6 for
Darunia. Each checkpoint starts before its knight's first lesson. Mesen
verified both messages on screen and both technique unlocks.

2026-11-17 Myu crawl sprite. The player tile allocator now reserves `$24`
for one of the Myu's two frames and uses the spare player pair `$5C`.
In the West Hyrule cave, Mesen saw both frames and confirmed their pixels
match the source ROM. The previous build failed that check on `$24`.
Tall geometry, death and continue, Dark Barba, and the Palace 1 volley
passed, with 0/900 volley lag frames. All 68 checkpoints were regenerated
and validated.
Open `play/Test Barba - Tricky Movement.cmd`, press F9, and watch the
Myu on the right crawl. Crouch nearby to check Barba's pose.

2026-11-17 fatal-hit silhouette. Black Barba now has two full torso chunks
with the feet anchored. The transition lifts the head one row and fills the
gap with a full segment. Build/play ROM `2141a5dbe2ad`. Mesen verified both
facings, death and continue in both audio builds, and the natural fatal hit
from Edge Scenarios F1. Tall geometry and all 23 unit tests pass. All 57
checkpoints were regenerated and validated.
Open `play/Test Barba - Edge Scenarios.cmd`, press F1 and wait for the enemy
hit. Watch for two complete segments under the black head during the flash.

2026-11-17 key item celebrations. Equipment, quest pickups and Heart/Magic
Containers stay overhead through the native fanfare and the full head-tilt
roar. Standing uses its two full torso chunks. The raised-head pose uses
the gem overlap to complete its second chunk. Barba regains control after
the roar's buffered tail. Build/play ROM `1b742549e495`. The Candle, gem,
Dark Barba, roar, tall geometry and look-up scenarios pass, as do all 23
unit tests and 57 regenerated and reloaded checkpoints. Palace 1 volley
averages 16,788 cycles, peaks at 22,490 and has 0/900 lag.
Open `play/Test Barba - Key Items.cmd`, press F1, walk left into the Candle,
and watch for two torso chunks during both the fanfare and the roar.

2026-11-17 Dark Barba victory. The full sampled roar begins on the first
audio tick after the Triforce fanfare. Barba tilts his head back and rises
into the 56-pixel pose. Zelda's awakening starts as soon as the buffered
roar tail finishes. Build/play ROM `207318fb945d`. Mesen verifies the timing
and pose from a normal fireball win in `tests/dark_link.lua`. The ending,
gem, sampled roar and controller regressions pass, along with all 23 unit
tests and 56 regenerated and reloaded checkpoints.
Playtest in `play/Test Barba - Bosses.cmd` with F8.

2026-11-17 palace gem timing. The victory fanfare leads directly into the
full roar. Life and magic refill shares the XP tally sound, so the statue
waits for the buffered roar tail before starting refill. The native ceremony
then returns control and queues crystal XP. Build/play ROM `389f2f64c4dc`.
The Palace 6 gem regression reproduced the early refill blip on the previous
build and now confirms that the shared tally sound starts after the roar.
Movement lock, XP award, roar routine, pose and controller checks pass, along
with all 23 unit tests and 56 regenerated/reloaded checkpoints.
Palace 1 volley averages 16,769 cycles, peaks at 22,466 and has 0/900 lag.
Playtest in `play/Test Barba - Gem Celebration.cmd`. Press F1 and hold Right
at the statue. Listen for fanfare, then the full roar, then the tally sound.

2026-11-17 main integration verification: default build and all 23 ROM-free
unit tests pass. Fresh title_sample, game_over_audio, roar_gameplay,
roar_controls, death_continue, tall_geometry, combat, and look_up emulator
reports all end in RESULT PASS.

2026-11-17 Game Over laugh onset: wait 36 frames (~0.60 seconds) before the
first laugh so the introductory sound has more room. The four following gaps
remain exactly 23 frames. A 63-byte bank-6 helper uses the existing screen timer
and a spare bit in the existing voice-request byte for the pending request;
no new RAM or fixed-bank space. All loud laugh, Barba roar, and native hurt sample
bytes are unchanged. Build/play ROM `9894b8b6b063`. 23 unit tests pass.
Fresh emulator checks confirm the added 36-frame onset delay, all five laughs,
four 23-frame gaps, sampled gameplay audio and death/continue. All 56 checkpoints
regenerated/reloaded; Edge profile installed for playtesting.
Playtest: Edge Scenarios F1, wait for death; listen for the added pause before
the first laugh, followed by the familiar five-laugh rhythm. F1 repeats.

2026-11-17 louder Game Over laugh: low-pass at 1 kHz before boosting the four
waveforms' targets 4x/4x/4x/2x. Decoded RMS is about 8-12 dB above the previous
four-waveform build, with some loss of treble detail to the louder output.
Pitch, sample lengths, all 23-frame gaps, allocations, Barba roar, and native
hurt are unchanged. Build/play ROM `c06fd072b9b9`. 23 unit tests pass, including
encoded loudness/pitch and shared silent-byte checks. Fresh Game Over (all five
starts and four 23-frame gaps) and death/continue scenarios pass; all 56
checkpoints regenerated/reloaded and Edge profile installed.
Playtest: Edge Scenarios, F1, wait for death; F1 repeats. Updated preview:
`build/game-over-laugh-preview.wav`.

2026-11-17 Game Over laugh fidelity revision: replaced the two-waveform pitch
approximation with four native waveforms shifted up an octave. The final three
laughs now retain their own native timbres and pitches. The similar opening pair
shares the first waveform with different lengths (second pitch about 4% sharp).
Single-pass conversion removes DC and scales excursion to reduce low-rate DAC
slew distortion. Silent-byte sharing fits all four after the approved roar;
the roar's full 2,177 bytes and native hurt bytes remain identical. No new RAM,
fixed-bank padding, or runtime code size. Build/play ROM `d080781db1a5`.
23 unit tests, actual Game Over rate/address/length and all four 23-frame gaps,
title sample, sampled gameplay and death/continue checks pass. All 56 checkpoints
regenerated/reloaded. Local A/B WAVs: `python tools/game_over_audio.py`; see BUILD.
Playtest: `play/Test Barba - Edge Scenarios.cmd`, F1, wait for death and listen
to all five laughs. F1 repeats. The small sample budget still limits fidelity;
producer listening is needed to judge the improvement.

2026-11-17 gem torso seam correction: lift the look-up art 8px rather than
16px, overlapping its existing half-segment with the identical top half of
the added torso. The final 56px pose has two whole torso chunks without the
third partial chunk; feet stay anchored. ROM `42d216c886c2`: gem reload/native
celebration and torso alignment/guards pass; the eight overlapping art rows
match exactly. No size, allocation, RAM or performance-path changes.
All 22 unit tests and 56 regenerated/reloaded checkpoints pass; gem profile
refreshed. Reopen Gem Celebration, F1, walk right to inspect the corrected join.

2026-11-17 gem roar torso follow-up: the raised-head victory pose gains one
16x16 torso chunk, extending to 64px while keeping its feet anchored. Existing
sword/shield OAM slots and torso tiles are reused. Other poses are unchanged.
ROM `9780cd08a423`: native gem checkpoint sequence, torso facing/clipping,
geometry, look-up, audio coordinator, HUD and volley checks pass. Volley
16,769 avg / 22,466 peak, 0/900 lag; HUD zero late splits.
All 22 unit tests pass; all 56 checkpoints regenerated/reloaded, with the gem
profile installed for immediate playtesting. Build/play ROMs match.
Playtest: `play/Test Barba - Gem Celebration.cmd`, F1, walk right; inspect the
longer torso during the victory roar. F1 repeats.

2026-11-17 instant gem playtest: `play/Test Barba - Gem Celebration.cmd`, F1,
starts beside the Palace 6 statue past the boss, before placing the final gem.
Walk right to test; F1 repeats. Separate `gem` profile preserves other sets.
Generated/reloaded checkpoint and native end-to-end `gem_checkpoint` check pass:
walking triggers placement, fanfare, one roar with raised head, then pose release.

2026-11-17 palace gem celebration: the full roar now starts immediately after
the crystal-placement victory fanfare, before health/magic refill and XP tally.
Barba holds looking-up frame 8 while roaring, then returns to his normal pose.
Native refill, crystal removal, save flags and XP award remain intact; the
final gem step cannot trigger a second roar. Spell roar timing stays unchanged.
ROM `22f98416c673`: 22 unit tests and fresh roar_gameplay, tall_geometry,
look_up (including real playback/pose release), roar_controls, scales, inferno,
hud_timing and perf_volley pass. Volley 16,671 avg / 22,363 peak, 0/900 lag.
All 55 checkpoints regenerated and validated; build/play ROMs match.
Playtest: `play/Test Barba.cmd`, F9, defeat Lava Link and place the gem.
Listen for fanfare then immediate roar; watch Barba raise his head for the roar.

2026-11-17 approved sampled audio promoted to the normal build:
`python tools/build.py` now uses ignored local `roms/roar.wav` and installs
the approved voice in `build/barba.nes` and `play/barba.nes` (ROM `22f98416c673`).
Roar bytes match the approved experiment exactly: 1.557 seconds, rate 9,
34-step amplitude. No attack roars. Hit audio keeps the ~0.627-second descending
tail. Title, SCALES/INFERNO and gem victory retain the full voice.
Original ROM analysis confirms Ganon's laugh descends: approximate fundamentals
270/260/235/205/195 Hz, encoded in different samples while hardware rate stays 15.
Game Over now approximates that contour one octave up, rather than repeating
one note or alternating low/high. The first two native octave-up waveforms are
re-encoded at rate 6: 65 bytes `$FCC0-$FD00` and 49 bytes `$FD40-$FD70`.
Five starts use first/second/second/second/second at rates 6/6/5/4/3, retaining
native 23-frame spacing. Lower data rate gives finer descending pitch steps;
the later three notes approximate the original contour with the second waveform.
Native Link hurt remains untouched. All writes
are guarded; no extra fixed-bank padding or RAM. `--native-audio` retains the
legacy noise-roar/five-waveform build. Normal playtest: `play/Test Barba.cmd`,
F2 for quiet attacks and descending hurt, F3 for spells, F9 for boss/gem;
`play/Test Barba - Edge Scenarios.cmd`, F1 for all five laughs.
Promotion validation: 21 unit tests, 23 emulator scenarios (including actual Game
Over pitches/spacing, sampled gameplay/title/controls, spells, combat, damage,
death/continue, far-call, bosses and ending), and all 55 regenerated/reloaded
checkpoints pass. Build/play ROM and patch match; native hurt bytes and the
approved roar bytes match exactly. Latest volley 16,662 avg / 22,352 peak,
0/900 lag; METEOR 14,917 avg / 16,792 peak, 0/900 lag; HUD zero late splits.
Legacy `--native-audio` rebuild still matches `aecf65b52c82`.
Descending-contour correction: 22 unit tests plus fresh Game Over rate/spacing, sampled
gameplay/title and death/continue checks pass; all 55 checkpoints regenerated.
Raw original and new audio comparisons: `build/original-game-over-laughs.wav`
and `build/game-over-descending-preview.wav` (decoded DPCM, before NES mixing).

Earlier 2026-11-17 Link Game Over laugh revision (legacy `--native-audio`): raises all five native laughs
one octave, with shorter individual laughs and original 23-frame start
spacing. Hurt audio is preserved. No new ROM padding, code or RAM; conversion
recipe only, source bytes guarded. The separate sampled-roar experiment keeps
its existing allocation. Playtest: launch `play/Test Barba - Edge Scenarios.cmd`,
press F1 and wait for death; listen for five higher laughs at the familiar
rhythm. Reload F1 to repeat (F2 loads after the laugh has begun).
ROM `aecf65b52c82`: 21 unit tests, actual Game Over audio scenario (all five
sample addresses/shortened lengths and all four 23-frame gaps), and
death_continue pass. All 55 checkpoints regenerated/validated; Edge F1/F2
profile installed. Build/play ROMs match; entire native hurt sample unchanged.

2026-11-17 sampled Famicom roar gameplay (now normal): the producer-approved
1.557-second, 2,177-byte roar (11,186 Hz, 34-step DAC excursion) now also plays
after the palace gem's XP tally/level-up pane finishes. Random attack roars
removed on 2026-11-17; breath retains its native fireball sound.
Barba's enemy-hit sound uses a 0.527-second prefix (extended from 0.344 seconds),
with an injury-only downward pitch tail: rate 9->5 over four steps near its end.
Playback lasts ~0.627 seconds; full roars keep their original pitch and 1.557-second
duration. Injury interrupts a full roar.
Lava Link retains native Link hurt audio. SCALES/INFERNO use the sampled voice
in the normal build. Title and gameplay pulse melodies halve volume during a
roar; envelopes and tempo keep advancing. First-title-roar pop fixed by easing
the DAC to its midpoint in 32 two-step writes before the first opening.

`play/Test Barba - Sampled Roar.cmd` tests the title. The new
`play/Test Barba - Sampled Roar Checkpoints.cmd` uses its own version-matched
Core profile: F2 combat/hurt, F6 Lava Link hurt comparison, F9 boss then gem.
Latest sound revision raises all sampled voice uses from 28 to 34 DAC steps
(21% higher target amplitude), including title, hurt, spells and victory.
Approved pre-promotion experimental ROM `b394d8a50887`.
All 21 unit tests and fresh title/gameplay/controller audio scenarios pass.
Legacy native-audio baseline was `aecf65b52c82`.
Gameplay/control, title, gem/XP/menu, hurt priority, original Lava Link sample,
music duck/restore, SCALES, INFERNO, combat, death/continue and far-call checks
pass. Controller capture now runs after the HUD split during playback, with a
one-frame raw-button cache and a native-read fallback when DMC stops (including
pause). HUD timing passes with zero late splits; volley 16,674 avg / 22,358 peak,
0/900 lag. This allocation is now permanent, with the compact laugh after it.
Build details/memory ownership: BUILD.md, "Sampled roar audio". Earlier actual title audio:
`build/roar-prototype/title-listening-smooth-start.wav`; short raw sample preview:
`build/roar-prototype/roar-hurt-preview.wav`.

2026-11-16 edge-scenario launcher: `play/Test Barba - Edge Scenarios.cmd`
uses the normal rebuild, version-matched pack and isolated profile workflow.
F1 loads the last-life/one-health Palace 1 danger scene; F2 loads the actual
final GAME OVER portrait immediately. Both states are generated from the
current ROM, reloaded and checked: F1 reaches native GAME OVER in 218 frames;
F2 Start returns to gameplay with three lives. The standalone danger-state
copy is also refreshed. All 17 unit tests and launcher PrepareOnly pass;
F1/F2 slot files and bindings are installed in the `edges` profile.
All 55 checkpoints across seven sets regenerated and validated for unchanged
ROM `8910a0e152ef` (53 existing plus the two new edge states).
Playtest: launch Edge Scenarios, press F1 and wait, then F2 to inspect the
portrait directly; press Start to continue or reload either key to repeat.

2026-11-16 final game-over portrait approved: right-ear join candidate 1 is
now the default (`thin_split`, `cap='soft'`, `neck_mark='none'`,
`ear_join='notch'`). Softened cap, small right-ear notch, no left stray dot,
mouthless face, thin split collar and black right neck seam. Fifty CHR tiles,
same guarded map allocation, no new RAM or padding. Actual screen checked;
all 17 unit tests and death_continue pass. All 53 checkpoints regenerated and
reload-validated for ROM `8910a0e152ef`; build/play ROMs match.
Extra standalone state: `play/Game Over Danger.mss`, Palace 1 combat corridor,
one life and one health unit. Reload verified; native enemy contact reaches
GAME OVER without input after 218 frames (about four seconds). Health HUD is
refreshed before capture. Preview `build/game-over-danger.png`.
Playtest: load that state in Mesen with `play/barba.nes`, wait for GAME OVER,
inspect the final portrait, then press Start. Core F2 remains the normal
combat checkpoint with its regular test loadout.

2026-11-16 right hat/ear join candidates: using selected refinement A
(`cap='soft', neck_mark='none'`) as the base, four close variations adjust
only the right hat/ear join: 1 small notch, 2 lower ear tip, 3 filled join,
4 rounded edge (`ear_join='notch'/'lower_ear'/'blend'/'round'`). All rendered
and visually checked in Mesen, fitting 48-50 tiles; all 17 unit tests pass.
Candidate ROMs/screenshots and enlarged comparison are in
`build/game-over-ear-candidates/`. Default build/play ROM and checkpoints
remain `49e80365f5bf` pending the final join choice.
Playtest: compare captures 1-4; Core F1 still uses the preceding approved
portrait after losing all lives in the normal play build.

2026-11-16 cap/left-neck refinement candidates: six close variants combine
two softened right cap folds with three left-neck treatments. A/B/C use
`cap='soft'`; D/E/F use `cap='tucked'`. Within each row the left mark is
removed, retained as one dot, or extended to a three-pixel diagonal seam
(`neck_mark='none'/'original'/'accent'`). Mouthless face, thin split collar,
filled right neck seam and body are preserved. All six rendered and visually
checked in Mesen, with 49-51 tiles within the existing allocation; all 17 unit
tests pass. ROMs/screenshots and enlarged `comparison.png` are in
`build/game-over-cap-candidates/`. Default build/play ROM and 53-checkpoint
pack remain `49e80365f5bf`, pending choice.
Playtest: compare A-F in the actual GAME OVER captures; Core F1 retains the
approved portrait after losing all lives in the normal play build.

2026-11-16 selected game-over portrait: candidate C (`thin_split`) is now the
default, with a mouthless face and one-pixel split collar. Filled the seven-pixel
vertical red seam on the right side of the neck with black. All other portrait
details are preserved. Fifty CHR tiles (`$00-$31`, bank 17), same nametable
macro, no new RAM or padding. Screen visually checked; all 17 unit tests and
death_continue pass, including game-over continue and restored breath.
Screenshot comparison against C confirms exactly seven pixels changed, all
in the requested stripe. All 53 checkpoints regenerated and reload-validated
for ROM `49e80365f5bf`; play/build ROMs match.
Playtest: Core F1, lose all lives, check the thin split collar and black right
neck area on GAME OVER, then press Start to continue.

2026-11-16 thin collar candidates: replaced filled clothing cutouts with
one-pixel red seams for A shallow collar (`thin_shallow`), B V collar
(`thin_v`) and C split collar (`thin_split`). Face remains mouthless; the rest
of the portrait is unchanged. All three rendered and visually checked in
Mesen, using 51/52/50 tiles within the existing allocation. Candidate ROMs,
screenshots and enlarged comparison are in `build/game-over-thin-collars/`.
Default build/play ROM and checkpoints remain `b5b9c138bb05`, pending choice.
Playtest: compare the three GAME OVER captures; Core F1 still uses the current
default portrait after losing all lives.

2026-11-16 collar-only portrait candidates: three mouthless variations keep
the face black below the eyes and place the red clothing farther below the
jaw: A deep V (`deep_collar`), B split lapels (`split_collar`), C laced tunic
(`tunic_collar`). Cap, ears, eyes and body silhouette are preserved. All three
rendered and visually checked in Mesen; 53/54/54 tiles fit existing CHR space,
and all 17 unit tests pass. Candidate ROMs/screenshots and enlarged comparison
are in `build/game-over-collars/`. Default build/play ROM and checkpoints stay
at `b5b9c138bb05`, pending selection.
Playtest: compare the three actual GAME OVER captures; Core F1 remains the
current default portrait if losing all lives in the normal play build.

2026-11-16 game-over expression candidates: two close alternatives to the
approved portrait, changing only the red collar/neck mark into either a raised
evil grin or a crooked smirk. Both leave the neck black and preserve the rest
of the silhouette. Recipes are optional `grin` / `smirk` expressions in
`tools/game_over_art.py`; candidate ROMs and actual game-over screenshots are
in `build/game-over-candidates/`, including enlarged `comparison.png`.
Both render correctly in Mesen and fit the existing CHR/map allocation;
all 17 unit tests pass. Default build/play ROM and the 53-checkpoint pack
remain `b5b9c138bb05` (current collar expression), pending producer choice.
Playtest: Core F1 and final-life GAME OVER for the current version; use the
candidate screenshots to choose A (grin) or B (smirk).

2026-11-16 game-over portrait revision: front-facing black Link now replaces
the enlarged side-view sprite. Reuses Ganon's original torso at 44% width,
with authored human jaw, pointed ears, folded cap, red eye slits and V neckline.
The 80x96 bust occupies 52 deduplicated CHR tiles (`$00-$33`, bank 17) and
the same guarded nametable macro; no new RAM or padding. Rendered screen
checked; all 17 unit tests, death_continue and overworld_side pass.
All 53 checkpoints regenerated and reload-validated for ROM `b5b9c138bb05`;
play/build ROMs match.
Playtest: Core F1, lose all lives and inspect the front-facing portrait on
GAME OVER, then press Start to continue.

2026-11-16 game-over silhouette: replaced Ganon with solid black Link, using
the native standing sprite enlarged 3x (48x96) below GAME OVER / LINK KEEPS LAVA.
Build-time extraction only; no original pixels committed. Forty deduplicated
CHR tiles and the existing nametable macro are replaced, with no new RAM or
ROM padding. Visual screen check, all 17 unit tests, boot, overworld_side and
death_continue pass (including game-over continue and restored B volley).
All 53 checkpoints regenerated and reload-validated for ROM `95ada67d0b11`;
play/build ROMs match.
Playtest: Core F1, lose all lives, then check the black Link silhouette before
pressing Start to continue.

2026-11-16 half-broken blocks: reproduced native animation-slot exhaustion
overwriting a pending erase, leaving visible stone over an empty collision tile.
Brick breaking now reserves an animation record before clearing collision;
when all five records are busy, the block stays hittable for a later shot.
Crumbling floors honor the same allocation failure. Same-size guarded vanilla
rewrites only; no added RAM or ROM padding. All 17 unit tests, combat (including
five final erases and retry), extra_fire, stab_blocks, boot, meteor, hud_timing
and perf_volley pass. All 53 checkpoints regenerated and reload-validated for
ROM `6d7224cbf549`; play/build ROMs match.
Latest volley: 16,658 avg / 22,300 peak cycles, 0/900 lag.
Playtest: Movement F8 (Palace 2 breakable blocks), repeatedly breathe through
the 2x3 wall; every brick should disappear fully, with no persistent fragments.

2026-11-16 downstab torso: both neck chunks above the diving head now flip
horizontally and vertically in place in either facing direction. The head retains
its existing orientation.
All 17 unit tests, tall_geometry, stomp and hud_timing pass. All 53 checkpoints
regenerated and reload-validated for ROM `57fe119bb089`; play/build ROMs match.
Playtest: Core F3,
jump and hold Down while falling; turn both ways and check the horizontally and vertically flipped torso
segments above the head.

2026-11-16 title/elevator/ghost follow-up: title jaw graphics now follow the
compiled head layout (fixes stale `$22` crouch tile in the open jaw). Barba folds
into crouch/crouch-attack while riding an elevator, with matching breath origin
and native Up/Down controls. Player lower-body OAM no longer swaps with rotating
enemy records; this is a candidate fix for the reported red downstab/busy-room
ghost, whose exact appearance still needs producer confirmation. Unit tests and
title_roar, tall_geometry, routines, upstab, look_up, stab_blocks, meteor, damage,
dark_link, hud_timing, perf_volley, perf_upward, perf_meteor and town pass.
That build's volley: 16,657 avg / 22,308 peak, 0/900 lag; six-Bot upward: 25,300 avg /
25,984 peak, 0/900 lag, 25 upward shots. All 25 Palace/Movement/Endgame busy-room
probes report zero lag and zero status-bar jitter (500 frames per checkpoint;
transition time can inflate the raw NMI maximum). See BREATH-IMPLEMENTATION.md.

Playtest: title screen, wait for the jaw to open; Movement F3 or Endgame F3,
ride Down and Up while ducked, breathe, then step off; Palaces F10, jump/downstab
and breathe among enemies, watching for any red duplicate. All 53 checkpoints
regenerated and reload-validated for ROM `ba1c79a15e61`.

2026-11-15 audit findings resolved: all 9 findings and maintenance items from
[the 2026-11-15 audit](AUDIT-2026-11-15.md) plus the 2026-11-16 town trigger/respawn
follow-up are fixed and verified (ROM SHA-256
`92bfdbacfc66e1ce56902fba20a69b70716b5ae082b35c354fd2b253d855b5dc`), with all 17
unit tests, town/progression checks, and regenerated test-pack checkpoints passing.

2026-11-16: Wyrmling redrawn as a front-facing baby dragon (two flap frames, original
art in `assets/barba.json`). burst, tall_geometry, ending and boot pass; producer
approved the look.

2026-11-16: Overworld dragon redrawn as a mini Barba (croc snout, crest, back spikes,
banded belly, slim coil) in all directions; up/down now have real walk frames
(`front_step`/`back_step`: jaws chomp, neck sways). overworld_side, overworld_fire,
forest_burn_limit, encounter_hazard, gameplay and boot pass; awaiting producer playtest.

2026-11-16: Busy-room performance and status-bar jitter (awaiting producer playtest).
When a busy room's NMI work ran past the next vblank, that frame's NMI was lost
and the PPU drew the whole next frame with the playfield scroll still latched, so
the status bar slid sideways by the camera position. `LateSplit`
(`src/late_split.inc`, bank 3) catches overruns that end inside the missed vblank.
It puts the status bar back at scroll 0, waits for sprite 0 and redoes the native
playfield split, so the lag frame becomes a clean repeat; it restores the
interrupted bank by its `$8506` fingerprint. Separately, the native offscreen-column
mask (`$F27D`, run for every drawn object, about a third of the enemy pass) is now
one 16-bit subtraction instead of a 4-pass loop, which saves 3-4k cycles per busy
frame. Both live in rewritten vanilla fixed-bank code, with no padding claimed
(`docs/FIXED-BANK-AUDIT.md`). Probe: `python tools/busy_rooms.py`.


## Historical Busy Areas & placement profiles (2026-11-17)

### Busy palace performance profile

The 2026-11-17 sampled build (`59ee6701557a`) had zero lag and zero HUD shifts
across all ten Busy Areas checkpoints. The stress probe walks, turns, jumps
and fires with health and magic replenished. A second Mesen run timed CPU
sections from entry to return on the same inputs. The enemy pass includes
enemy AI, drawing, collisions, and enemy projectile updates.

| Checkpoint | Average / peak NMI cycles | Enemy pass at peak | Frames above eight sprites on a scanline |
| --- | ---: | ---: | ---: |
| F5 Palace 2 crowded floor | 24,599 / 29,004 | 13,776 | 15 / 600 |
| F6 Palace 3 Ironknuckles and blocks | 22,447 / 27,762 | 10,655 | 4 / 600 |
| F4 Palace 5 before Gooma | 22,908 / 27,525 | 12,242 | 104 / 600 |
| F1 Palace 5 two Magos | 16,998 / 21,369 | 8,880 | 40 / 555 |
| F7 Palace 6 Wizzrobe hall | 17,050 / 21,641 | 6,227 | 28 / 600 |

- Check the empty enemy projectile slots first. The native loop calls the
  offscreen mask at `$D574` before testing the projectile type at `$D579`.
  Across the five palace checkpoints, calls for empty slots took 510–600
  cycles per frame on average, including 534 cycles on the worst P2 frame.
  Those timings include the call and return. A gate would recover some of
  that cost after its own overhead. Before moving the check, trace later
  readers of the shared `$CA`/`$CE` results and scratch `$00`, including
  projectile spawn and despawn in the same frame.
- Skipping the SCALES bank round trip when both `$070F` and `$05EC` are clear
  is a smaller candidate. Unshielded calls through `ScalesHop` took about
  112 cycles before guard overhead. Keep the cast, hit response and first
  frame of palette restoration after Shield clears.
- Native column drawing also contributed to the worst frames. The scrolling
  tail from `$D545` took about 2,290 cycles on each peak frame in P2, P3 and
  the Gooma approach. Profile its PPU packet builder if the smaller gates
  leave too little headroom. Preserve the scroll and column upload schedule.

For a manual comparison, use F5 and jump and fire through the crowded floor
while watching the HUD. Use F4 to watch for sprite flicker as Ironknuckles
and projectiles overlap. CPU savings buy frame time. Sprite flicker needs a
separate look at which sprites share those scanlines.

### Overlapping player and enemy projectiles

An 850-frame run on the same build gave each checkpoint 20 warm-up frames.
The Horsehead approach (F8) contains the hammer-throwing Gumas. The Gooma
approach (F4) supplies another projectile-heavy fixture.

| Checkpoint | Peak with live projectiles from both sides | Crowded scanlines on mixed-projectile frames | Lag |
| --- | --- | ---: | ---: |
| F8 Horsehead approach | 25,635 cycles, two fireballs and four hammers. Enemy projectile updates took 3,516 cycles. | 32 / 775 frames | 0 |
| F5 P2 crowded floor | 30,157 cycles before HUD recovery, one fireball and two enemy shots | 25 / 719 frames | 1 |
| F4 Gooma approach | 27,884 cycles, two fireballs and three enemy shots | 147 / 505 frames | 0 |

LateSplit kept P2's HUD steady. The full NMI lasted 35,886 cycles because
recovery waited for the next sprite-0 split. The combat probes stayed within
the two-fireball cap and never used backed projectile slots. That makes extra-slot
collision work a lower priority for these specific rooms.

Build `0d55b1c120af` checks the slot type before entering the offscreen-mask
routine. Live shots and disappearing blades still run their usual updates.
The shorter player-contact gate retains the original slot/frame parity.
It also provides the bytes for the empty-slot check within the existing
fixed-bank code. The A/B used the same checkpoints and controller replay.

| Checkpoint | Peak work before recovery, old → new | Average cycles saved per comparable update |
| --- | ---: | ---: |
| F8 Horsehead approach | 25,612 → 25,355 | 397 |
| F5 P2 crowded floor | 30,157 → 29,682 | 564 |
| F4 Gooma approach | 27,861 → 27,532 | 564 |

All ten Busy Areas rooms showed zero lag and HUD shifts in the 850-frame
probe. The contact-gate call counts and all 256 sprite-table bytes matched
on comparable updates before the old build's lag. The expected scratch
differences were `$00`, `$CA` and `$CE`, which now retain the result from the last
actual mask call. The probe reports `workMax` before the recovery check and
`nmiMax` through RTI.

Use F8 with jumping and volleys to check hammer arcs, hit timing and
visibility. Use F5 for the crowded corridor and F4 to observe which
sprites drop out when threats overlap.

### November 17 regression pass

Build `9c0add7a0040` covers the sampled voices, item and gem ceremonies,
Game Over, ending, palette fixes, recent boss and enemy changes, and the
renderer and projectile optimizations. All 69 checkpoints across ten sets
were regenerated and reload-validated for this ROM.

Rendered checks covered file select, the BREATH pane, all six burned-sign
messages on each sign-reader type, both technique lessons, town shouts,
combo tiers 1, 2, 4 and 5, the Game Over portrait, Zelda's dialogue, all
20 credit entries and the replay prompt. Punctuation, digits and message
borders rendered as expected. The top-tier `GODLIKE!` banner alternated
between its flame pair and the last two characters on their shared
scanlines, as implemented by its existing OAM priority rotation.

In the 2,400-frame replay, Rauru's autoplay walked onto the overworld and
triggered the 520,387-cycle map load twice. The same loads occurred at the
same points in `0d55b1c120af` and `59ee6701557a`. The report now includes
those updates in `otherNmiMax`. Its `workMax` and `nmiMax` require steady
side-view play at both ends of the measured update.

The updated probe recorded zero lag or HUD shifts across 23,338 side-view
frames. Palace 2's crowded floor was closest to the limit at 29,705 cycles
through RTI. Rauru peaked at 25,461 in steady side view. The sprite limit
was exceeded on 1,564 of 2,138 Rauru frames, 1,023 of 2,247 Old Kasuto
frames and 253 of 2,380 Gooma approach frames. The maximum was 14 sprites
on a scanline in Old Kasuto and the two-Mago room.

For a manual spot check, use Busy Areas F4 to jump and fire through the
Gooma approach while watching projectiles and the HUD. Use Towns and World
F4 or F6 to read the Mido or Darunia lesson. Use Key Items F1 or Gem
Celebration F1 to see the raised-head pose and hear the fanfare-to-roar
handoff. Emulator checks verified sample timing and control recovery.

### Horizontal placement audit

The initial audit reloaded all 69 checkpoints for `9c0add7a0040`, all 77
slots in the installed test profiles, and the standalone Game Over Danger
state. On the 256-pixel screen, 23 of the 68 checkpoints with Barba visible put
his sprite midpoint within 16 pixels of x=128. Another 42 start left of
that band and three start to its right. The Game Over portrait has no
playable Barba. The first frame after reload confirms the same grouping.

In the original Busy Areas F6, holding Right moved Barba 94 pixels in
world coordinates while the camera kept him at the left edge. In F5, Right
moved him only one pixel before the wall. Both passed the earlier reload
check, which accepted any change in world X.

Busy Areas F4–F7, Palaces F10, and Tricky Movement F2, F4 and F8 now
place Barba on walkable ground near center. Reload validation checks the
initial screen position and requires net rightward progress while Barba
stays in the center of the view. For a manual check, load Busy Areas F6,
hold Right and breathe into the blocks. In Tricky Movement F8, turn left
to shoot the block wall. The drop-shaft checkpoint still begins beside
the gap so the native drop into the lower room can be tested directly.

All 69 regenerated checkpoints passed reload validation. A 620-frame
replay per Busy Areas slot logged zero lag or shifted HUD frames. The new
Palace 2 floor start peaked at 28,517 NMI cycles through RTI and the new
Palace 3 block start peaked at 24,963.

