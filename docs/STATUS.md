# Barba Edition status

Current playable alpha. Built locally from `roms/z2.nes` via `python tools/build.py`.

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
Latest volley: 16,657 avg / 22,308 peak, 0/900 lag; six-Bot upward: 25,300 avg /
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

## Implemented features

- **Player (24x48 Barba)**: Boss-derived 24x48 side-view poses (`src/tall_player.inc`, `src/tall_layout.inc`), full-body jumps, compact 24px crouch, ceiling folding, partly submerged lava and swamp-water pose (`GEOMETRY` bit 2 via `LAVA_CONTACT` or `$0752`, `tests/swamp_submerge.lua`), 8x16 flying Wyrmling, and 16x16 overworld avatar. Terrain and enemy-contact hitboxes keep native dimensions. CHR allocation reserves `$4E`/`$50` (Ache/bat enemy frames) and `$5E`/`$62` (ending ash) so enemy sprites in caves/forests stay intact, plus `$60` (the XP "3" score digit, also the first digit of "30"; the down pose had overwritten it, 2026-11-15). The budget is full, so `tools/assets.py` reuses any allocated pair within 1 pixel (attack head = idle head, crouch-attack tail = crouch tail), freeing `$5C`. Tall head OAM moved from `$F8` to `$C4` (and town combo OAM `$C4` to `$64`) so Barba no longer clobbers the native HUD magic partial-bar sprite at `$02F8` (verified in `tests/hud_timing.lua`).
- **Attacks & techniques**:
  - Five-shot diagonal volley at all health levels (`src/breath.inc`, `src/extra_fire.inc`) with shared mouth placement, 8-update cadence, `LOAD_LIMIT = 7` governor, native Barba fireball SFX (`$ED |= $40`), and glove-gated brick breaking (`src/blocks.inc`, all palace groups `$0707 >= 3`). Standing post-slash recovery (`$0400 == 4`) with B released re-arms the volley so standing cancel-slashes fire without moving first.
  - Geldarm (West Hyrule sand worm, `$20`) hurtbox (`$E90E`, type 5) widened to `12x64` px (`$FE, $0C, $00, $40`) so standing, crouching, and extra-slot fireballs hit its body as well as its head. HP 8 -> 4 (bank 1 `$9441`; attack 1-2 = 2 hits, 3+ = 1 hit). A lethal hit from any source — including jump stomp in `BarbaStomp` (`src/stomp.inc`) — no longer explodes it at full height: `src/geldarm.inc` (bank-1 pad `$9EB9`, hooks `$9BB5`/`$9C3D`) keeps it alive at HP 0, flashing and immune, sinking into the sand 2 px/frame (~1/2 s), then runs the native death `$E880` at the sand line (`tests/geldarm.lua`).
  - Hidden Red Jars (`enemy $05`, Bank 4 Type A `$B83E`, Bank 4 Type B `$AF61`, Great Palace Bank 5 `$A521`) are hooked via `HiddenJarHit` (`$A7BF` in bank 4, `HiddenJarHit` in bank 5) so ordinary breath (native and extra slots) as well as melee reveals them.
  - Upward breath (airborne `Up+B` column) and rising head-butt (`Up` while ascending), both gated on Upward Thrust; rising head-butt breaks glove-gated overhead bricks via `BarbaBlocks` (`tests/stab_blocks.lua`).
  - Downstab (`Down` while airborne with Downward Thrust) with 64px visual double-torso pose, 18x12 centered foot hitbox (`BarbaSetThrusts`), and glove-gated floor brick breaking via `BarbaBlocks` (`tests/stab_blocks.lua`).
  - Easy-enemy jump stomp (`$C2` 1..16, full-body foot reach `$29 + $22 - $2A,x < $1E`, excluding shielded palace
    enemies `$18..$1A`, `$1F`, `$23`, verified by `tests/stomp.lua`) and touch item pickup (`src/stomp.inc`). No stomps during a boss fight's
    scroll lock (`$0728`): a stomp kill skipped the boss-death handler, so no key dropped (room softlock).
- **Lava & sea crossing**: Palace (`$0707 >= 3`) and outside-palace encounter (`$0707 == 0`) water/lava surface support with normal movement, crouching, jumping, submerged pose (`GEOMETRY` bit 2), and lava-launch boost (`$FA`) (`LavaSurfaceBody` in `src/farcall.inc`, `tests/encounter_hazard.lua`). Town water (`$0707 = 1, 2`) keeps vanilla death; raft route uses dragon sea-crossing sprite.
- **Towns, shouts & combo banner**:
  - Outdoor wandering villagers (`$10..$12`, `$19..$20`) flee at catchable speed, take refuge in open/closed doors, and burn into temporary ash (`src/town.inc`). House-opening villagers (`$13..$18`, including `$17` healer and `$18` magic-house openers) are excluded from `TownEligible` and `TownBurnable` so they stay invulnerable, keep their native `$97D4` door-emerge and `$54` door-opening behavior, talk on `B` (or `Up`) (`TownNativeTalk` at `$9A2C`, tested by `tests/spell_door.lua`), and trigger `$99E6` heal/magic restoration on entering (`$0736 == #$16`, `tests/heal_door.lua`). Single-area non-town and indoor NPCs (`$0A..$20` excluding `$0C`, `$13..$18`, and invisible triggers `$21..$22` such as Saria's Mirror and Nabooru's Water of Life Fountain, across world 1/2 rooms except North Palace `$3C`, via `TownBurnable`) stay put and keep their native/service dialogue on approach, burn into temporary ash on fireball hits, and clear their room-table spawn bit via `jsr $DD3D` in `TownHide` so re-entering repopulates them (`tests/town_nontown_burn.lua`).
  - Burned signs (2026-11-16): scorching a sign board makes it read one of six rotating burned lines until the room reloads (`src/sign.inc`, docs/TOWNS.md "Burned signs", `tests/sign_burn.lua`). Not yet playtested by the producer.
  - Holding `Up` near a fleeing villager triggers fast direct panic dialogue (`src/town_dialogue.inc`, `TownLine` asserted `<= 10` chars, max 3 lines, so a blank tile pads every border of the 14-tile box; panic lines use `!` and contractions via a new apostrophe glyph; vanilla `?` restored, dialogue glyphs guarded post-build).
  - Floating 7-OAM sprite shouts (`OH SHIT!`, `OH FUCK!`, `RUN!`, `OH NO!`, `OH GOD!`, `HELP!`, `SAVE ME!`, `NO!`, `BARBA!`) in `src/shouts.inc`.
  - Scorchable outdoor town props, buildings & street ground (`src/blocks.inc`) with animated lasting fires (16-slot FIFO ring, tracking `SCORCH_PAGE` against `$4B` so matching screen coordinates on different pages do not alias, 8-frame tongue-swap animation, ~10s flame duration or oldest-eviction to char, cleared on room exit) and Unreal Tournament-style running combo banner (`MULTI KILL!` .. `GODLIKE!` at 12/24/40/60/85 pts) with live `X<pts>` counter in `src/combo.inc`.
  - Sleeping Zelda in North Palace can be scorched with `"OOPS..."` shout.
- **Overworld dragon fire**: Pressing `B` on the overworld breathes an animated 8x16 flame (`$60/$62` in CHR bank 30) with dragon fire SFX (`$ED |= $40`), splits the WRAM RLE map (`BarbaSplitBurnForest`) so only the single facing forest tile (`$06` -> `$04` Desert/Plains) is scorched without affecting neighboring trees across battles/scrolling (while cancelling the PPU plains redraw via `BurnAbort` if `BurnMapEndGuard` refuses a split at the `$7FF0` map-capacity limit), reveals Hidden Kasuto without needing the Hammer, and triggers magic/rumble reactions (`$EC = $04`) when aimed at towns or palaces (`A` keeps Hammer on boulders; `B` plays Flute on Spiders/open ground once owned) (`src/barba.asm`, `tests/overworld_fire.lua`, `tests/forest_burn_limit.lua`).
- **Title, menus, bosses & ending**:
  - `BARBA I / THE ADVENTURE OF / BARBA` title screen with molten lava, animated roaring Barba, and scrolling story; Barba 1-Up dolls across all 13 even sprite banks (same 8x16 horned head-and-shoulders art as the File Select head, `compile_file_select_doll`; redrawn 2026-11-16 without teeth); dragon spell names (`SCALES`, `JUMP`, `LIFE`, `WYRMLNG`, `METEOR`, `REFLECT`, `SPELL`, `INFERNO`) with native noise-channel Inferno roar, extended decor flash, and 4-wave 4-way firestorm barrage (`BarbaInfernoTick` in `src/breath.inc`, `tests/inferno.lua`); post-flash palette restore (`$16/$27/$30`).
  - Level-up pane attack row reads `BREATH` (bank 0 `$9BE9`) and BG tile `$C9` (vanilla sword, all 13 odd BG banks) is an original fireball icon, so the attack row and File Select show fireballs (`tests/levelup_pane.lua`, 2026-11-16).
  - **SCALES** (Shield) feedback (2026-11-16): vanilla painted Barba's white belly red ($16), the colour Barba already is. Shielded Barba is now navy/sky blue/white: the white belly stays (`$30`, guarded byte `$8E8E`, still the `$070F` flag), sky-blue body (`$21`, `$69D8`) and navy outline (`$01`, `$69D2`), both set by `ScalesTick` and restored to red/orange with a 1-frame palette re-upload when the shield ends; damage halving unchanged. Producer picked this over gold belly, blue belly on orange body, red outline, and an all-blue mid-blue belly. `src/scales.inc` (bank-3 pad, reached each frame through a 14-byte bank-6 hop from `BarbaShouts6`) adds a dragon roar + 32-frame decor flash on cast, and the native shield clang + 8-frame palette flash whenever Barba takes a hit while shielded (`$050C` rising). `tests/scales.lua`; perf +~110 cycles/frame, 0 lag.
  - **METEOR** (2026-11-15) replaces the Fire spell (slot 4, `$076F` bit 4, lasts like vanilla Fire): mid-air
    `Down + B` dives at 6 px/frame (`$057D = 6`); landing thuds, flashes and sends one flat, fire-class
    floor shockwave each way gated through `BarbaLoadOk` (`METEOR_WAVE` = `$C0` flags, 33 updates like breath). Breath is now always fire class
    (`$05CA = 0`), so Fire-only enemies no longer need a spell; range stays 33 updates. Code lives in reclaimed
    dead vanilla bank-0 code (`$97F1`, `$9847`, `$81C1`; original bytes guarded). `tests/meteor.lua`.
  - Palace 6 boss converted to **Lava Link** (hand-drawn Link head/tunic in CHR 25, Sprite Palette 3, Spear/sword-beam breath, fireball damage).
  - **Dark Barba** ("Dark Link", 24x48 in `src/dark_barba.inc`, sharing `src/tall_layout.inc` directly and enforcing `$0753 = 2` shadow palette on entry) takes 1 HP fireball damage and yields the Triforce-hold pose (`tests/dark_link.lua`).
  - **Boss fireball coverage** (2026-11-15): all six palace bosses die to fireballs alone, with no thrust
    techniques, then drop the key that unlocks the room: `tests/horsehead.lua`, `helmethead.lua`, `rebonack.lua`
    (both phases), `carock.lua`, `gooma.lua`, `lava_link_kill.lua` (shared driver `tests/boss_fight.lua`).
    Carock was immune in vanilla (bank 4 `$B1E9` skips the hit check for `$22`; Reflect only); `CarockHit`
    (bank 4 `$A7D0`) adds the projectile/sword check in his visible window and runs the native boss death on a
    kill (a raw kill drew him into OAM 0 and hung the sprite-0 wait). Dark Link: `tests/dark_link.lua`.
    **Wizzrobe fix (2026-11-16):** that visible-window tail (`$AEB2`) is shared with the Palace 3/4/6 Wizzrobe
    (`$1D`, routine `$AE4F`). Until the fix, a Wizzrobe killed by breath also ran the boss death `$B1F6`: it
    came back to life (`$B6 = 1`, HP wrapped; seen in the emulator) and `$6E1D+$1D` became `$FF`, the boss flag
    the native death code reads (`$DCC4`, `$DE07`) to run the boss explosion and key drop (the key sequence is
    read from the code; the probes did not capture it on screen). `CarockHit` now calls `$B1F6` only for `$22`; Wizzrobes keep
    breath damage (vanilla had sword only) and die normally. The table reloads on each room load, so saves
    are unaffected. Barba's stomp also now skips palace `$1D` (P5 Mago / P6 Wizzrobe): it used to kill them
    during their invisible teleport phase. `tests/wizzrobe.lua`, `tests/stomp.lua`.
    Thunderbird keeps vanilla's rule (producer decision, 2026-11-15): immune until Inferno, then fireballs
    hurt it; `ThunderHit` (`$922A` hook in `src/barba.asm`) preserves Thunderbird's boss-death state (`$6E3F = $FF`) even when a second Inferno deals lethal native Thunder damage so the Key drops cleanly.
    Verified by one-off probes (2026-11-15): downstab on mounted Rebonack (unhorses `$20` into `$0A`) and Reflect vs Carock (reflected beams damage and kill `$22`).
  - **Ending sequence**: 24x48 Barba beside woken Zelda, custom wake-up dialogue, curtain-fall behind-curtain fireball toast finale turning Zelda to ash, 20-entry credits, and New Game+ (`$07A0 = 1`).

- **Boss checkpoint set** (2026-11-15): `play/Test Barba - Bosses.cmd` maps F1-F8 to the left edge of every boss room (Horsehead through Dark Link) with route-appropriate loadouts; all 8 reload-validated (`docs/TEST-PACK.md`).

## Performance & bank headroom

- `BarbaDisplay` fast path + `BarbaGeometry` terrain cache + `BarbaExtraUpdate` fast path + tightened `ExtraNearEnemy` + direct `BarbaExtraBlocks` + `BarbaLoadOk` 2-shot cap with `>= 2` enemies + odd-frame OAM priority rotation: Palace 1 `perf_volley.lua` achieves **0/900 lag frames** (idle avg 15,862 / peak 16,086 cycles; volley avg 19,373 / peak 25,533 cycles, 0 near-budget >27k frames). `perf_meteor.lua` passes with **0/900 lag** (`17,353` avg / `19,142` peak, `slams=10 wavesPlaced=2`), and the six-Bot METEOR + volley stress probe (`build/audit_perf_meteor_six.lua`) now achieves **0/900 lag** (`maxLiveShots = 1`, peak `28,983` cycles, down from `160/900` lag). Palace 3 room `$0D` (2 Ironknuckles + breakable blocks) previously measured **25,338 avg / 28,155 peak (0 lag frames)**, down from 28,095 avg / 30,049+ peak (4 lag frames).
- Busy rooms (2026-11-16, `tools/busy_rooms.py` autopilot over test-pack checkpoints): before the fixes, P2 floor
  (5 enemies) lagged 77/480 frames, P5 before boss 14/480 and Old Kasuto 5/480, and every lag frame shifted the
  status bar. With the fast `$F27D` mask, NMI averages / worsts are 24.5k/28.5k (P2 floor, was 28.1k/32.1k),
  22.9k/27.4k (P5, was 27.0k/31.4k) and 22.0k/29.0k (Old Kasuto, was 25.0k/31.8k), with 0 lag. Palace 1
  `perf_volley`: idle 13,766/13,990, volley 16,776/22,532, 0/900 lag. Known limit: an overrun longer than vblank
  (~2.27k cycles) ends after the pre-render line and still shows one shifted frame; none were seen after the mask fix.
- `FarCall0` cold-hook ABI in fixed bank 7 (`src/farcall.inc`) keeps fixed-bank padding free without hot-path bank-switch overhead.

## Final end-to-end review (2026-11-16)

These checks found no progression blocker and no bank or WRAM fault:

- the full suite, including `tests/death_continue.lua`
- a static cross-bank scan of the source and hooks
- a WRAM write-watch
- a death and game over → continue probe
- a check of the flute gates (Palace 6 call spot and River Devil)

Two cosmetic P3 limits are logged in [AUDIT-2026-11-15.md](AUDIT-2026-11-15.md#final-end-to-end-review-2026-11-16-rom-92bfdbac-unchanged): leftover fire for under 1 s after a respawn, and the scorch ring keyed only on room number.

## Remaining / open items

- Full end-to-end human playthrough across all palaces, spell unlocks, item gates, and ending.
- METEOR (2026-11-15, awaiting producer playtest): magic cost still uses vanilla Fire's table (`$8D9B`);
  slams are unlimited while the spell lasts. Retune after the feel check.
- Trailing torso (shelved 2026-11-15): the producer liked a lagged 16x16 segment behind the lower body (OAM `$20/$24`,
  Y from an 8-entry ring of past actor Y) "with minor adjustments", but reverted it for cost: +190 cycles/frame,
  volley over-8 frames 34 -> 224 of 900, Rebonack bot fight lag 28 -> 60. Patch (renderer compaction that frees
  ~250 bank-0 bytes, trail, test updates): `docs/archive/trailing-torso-prototype.patch`.
- Cross-check on a second accurate NES emulator / hardware-accurate MMC1 behavior.
- Audio listening pass on Inferno roar vs. music and transitions (and the SCALES cast roar / shielded-hit clang).
- Fireball range (producer decision pending, 2026-11-15): an uncommitted change raised volley lifetime from 33 to 63
  updates (64 px -> 124 px). Reverted before commit because the fireball-only Rebonack fight (`tests/rebonack.lua`)
  never finished: long-lived misses hold the 2-live-shot cap, so fire rate collapses. Longer range needs a fire-rate
  or cap rethink first. `VOLLEY_LIFE` in `src/breath.inc` is the knob.
- Fixed 2026-11-14: Fat Woman/River Guard/Knight/indoor-NPC villagers drew combo digits and flame art
  (glyphs and fire tiles sat on bank-7 villager sprite pairs).
- Fixed 2026-11-15:
  - Town pause menu burnt icons: moved town fire char tiles off `$96/$B9` to unused bank-7 tiles `$35/$C2` (enforced by `tests/shout_follow.lua`).
  - Town double-door visual bug: hooked native door entry (`$98AB`) to `TownDoorCoords` / `TownDoorEmerged` (`src/town.inc`) so calm/non-panicked villagers derive the door's exact column and page from `$DC/$DD` instead of `$4E,x + L9780,y` (which drew a duplicate closed door one column left of the real doorway), while house-openers emerging from inside (`L97F5`, `$AF=$81`) recover their doorway from `($4E,x - L9740,y)` and `$3C,x` because `LEA32` runs while `$4E,x` is offset (`tests/spell_door.lua`).
  - Magic container/town item sprite (`$83`) overlap: moved shout glyph `H` from bank-7 `$83` to unused bank-6 pair `$7C`.
  - Spell-teaching Wise Man frame (`$62/$64`, bank 6) overlap: moved town `ASH_TILES` from `$64/$66` to unused bank-6 pairs `$7E/$80` and guarded `$62/$64` in `TOWN_SPRITE_PAIRS`.
  - Overworld forest-burn overflow: each burned tree grows the WRAM RLE map (`$7C00..`, ends near `$7F20`) by up to
    2 bytes, so roughly 110-220 burns in one region would have shifted map bytes past `$7FFF` into MMC1 registers
    (crash/corruption; West Hyrule has 359 forest tiles). `BurnMapEndGuard` (bank 0 pad `$BFE0`) refuses splits once
    the map end reaches `$7FF0`; `BurnAbort` cancels the queued plains redraw so the tree stays visually and logically (`tests/forest_burn_limit.lua`).
  - Spell-house door softlock: excluded `$13..$18` house-openers from `TownEligible` and `TownBurnable` and hooked `$9A2C` (`TownNativeTalk`) + `TownUpdate` to talk on `B` (or `Up`) (`tests/spell_door.lua`).
  - Audit fixes (`AUDIT-2026-11-15.md`): `ThunderHit` prevents lethal Inferno softlock on exposed Thunderbird; `BarbaLoadOk` gates `BarbaFireSpell` and `MeteorEmit` (0/900 lag under 6-Bot METEOR stress); `DarkBarbaTiles` includes `src/tall_layout.inc` directly with `$0753 = 2` shadow palette; `HiddenJarHit` allows breath to reveal hidden red jars across banks 4/5; `BarbaTownBurn` compares `SCORCH_PAGE`; `BarbaStomp` routes Geldarm stomp kills through its sinking death (`tests/geldarm.lua`); Bosses F7 (`$35`) / Core F10 (`$35`) / Bosses F8 / `assets.py` metadata / test exit-status propagation (`dark_link`, `ending`, `link_boss`, `title_roar`, `perf_volley`, `perf_meteor`) fixed.
- Fixed 2026-11-16: Phantom closed door in open street (producer screenshot). Hidden house-openers (`$13..$18`, `$AF = $80`) decided to emerge from `$C9`/`$CD`, which belong to whichever actor drew last, so one could emerge while its doorway was pages away; its door macro then wrote into nametable (page & 1) over the visible street. `TownOpenerGate` (`src/town.inc`, placed in BANK3_SIGN) now also requires Barba to be within 96 px of the opener (16-bit) before native `$97D4` runs. Repro pre-fix: emerged at 223 px; post-fix 95 px (`tests/opener_far.lua`). Not yet playtested by the producer.

Historical design notes and completed implementation plans are archived in [docs/archive/](archive/).
