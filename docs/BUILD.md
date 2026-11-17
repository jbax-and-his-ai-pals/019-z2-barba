# Build and validation

Requires Python 3.10+ and the ca65/ld65 programs from [cc65](https://cc65.github.io/).
Portable Windows tools may be placed in `.tools/cc65/bin/`. No Python packages
are required. All paths below are relative to the repository root.

On Windows, `./tools/bootstrap.ps1 -WithEmulator` downloads portable cc65 and
Mesen into the ignored `.tools/` folder and verifies their SHA-256 checksums
before extraction. Omit `-WithEmulator` for just the assembler. The cc65 URL is
an upstream snapshot: if upstream replaces it, the locked checksum intentionally
fails. Install ca65/ld65 manually from the official project, or deliberately
review and update `tools/toolchain.json` for the new snapshot. Tools already on
PATH are supported; neither WSL nor a system-wide installation is required.

On Linux, install the `cc65` package with your distribution's package manager.

Place your source ROM at `roms/z2.nes`. The build requires SHA-256:

```text
ad8c0fbcf092bf84b48e69fd3964eea4ed91bfe62abc352943d537979782680c
```

The build will reject other dumps rather than guessing where to patch them.
The original is opened read-only. Never copy a modified ROM over it.
The default sampled voice also requires local PCM `roms/roar.wav` (reference
SHA-256 `9e5edb33f09969fe4603c8f4bbdb5311cb7396b4803ac5485f9ad8e65f11394f`).
Recordings and generated DPCM stay ignored. Use `--native-audio` for a build
without this local recording.

```powershell
python tools/build.py
python -m unittest discover -s tests -v
```

Main integration verification (2026-11-17): the default build, all 23 unit
tests, and fresh title_sample, game_over_audio, roar_gameplay, roar_controls,
death_continue, tall_geometry, combat, and look_up emulator scenarios pass.

Outputs:

- `build/barba.nes`: playable development ROM; original mapper, header and size.
- `build/barba.bps`: BPS1 patch with source, target, and patch checksums.
- `build/build-report.json`: source/output hashes, symbols and all changed ranges.
- `build/barba-sprites.png`: generated preview of the original pixel artwork.
- Assembly binaries, linker map, and debug symbols for development.

Relocated original overworld graphics use BPS source-copy references. Their
bytes are read from the user's original ROM when applying the patch, rather
than embedded as newly authored patch literals. No ROM is uploaded by the build.

Research graphics can be rendered with `python tools/inspect_chr.py`.
They stay in `build/` and must not be committed.

Legacy `--native-audio` Game-over audio (2026-11-17): `tools/game_over_audio.py` decodes the native
DPCM laughs, averages each pair of PCM levels and re-encodes at the unchanged
maximum DMC rate for one octave up and approximately half duration. The native
sequencer selects entries 2, 4, 5, 6, 7 at bank-6 `$917B`; actual starts remain
23 frames apart. Only samples and five pointer/length pairs change. First
laugh moves from `$F3C0` to `$F400` to preserve the shared hurt endpoint;
lengths are 225/161/193/129/129 bytes, inside existing laugh storage. No new
code, padding or RAM. Samples/table entries are hash/byte guarded; only the
recipe is tracked. The default sampled build uses the compact laugh layout
described below instead. Verify `tests/game_over_audio.lua` after generating Edge Scenarios;
use F1 natural death to hear all five laughs.

Game-over artwork uses `tools/game_over_art.py`: read the original Ganon
portrait macro at build time, narrow its torso to 44% width, and replace its
head with authored front-facing Link cap, ears and jaw shapes. The 80x96 bust
uses solid black (palette index 3), red eye slits and a mouthless thin split
collar (candidate C). The seven-pixel vertical red seam on the right side of
the neck and the stray left dot are filled black. The cap uses the softened
fold with a small notch above the right ear (final candidate 1). Fifty
deduplicated tiles replace Ganon in CHR bank
17 `$00-$31`; the guarded bank-0 `$801F-$80C8` nametable macro centers Link
below the existing text. Font, overworld terrain, palette, timing and continue
behavior stay native. No new RAM or ROM padding is used;
only the extraction recipe is committed. To inspect, lose the final life from
Core F1 and wait on GAME OVER before pressing Start.

Portrait expression candidates: `compile_game_over_link(source, expression)`
accepts `collar` (the original filled V), `grin` (a broad curved smile raised onto
the face) and `smirk` (an asymmetric smile with one raised corner). Both smile
variants leave the neck solid black and use 50 tiles within the same reserved
span. Compare local emulator captures in `build/game-over-candidates/`; the
normal build and checkpoint pack use the selected `thin_split` expression.

Collar-only alternatives are `deep_collar` (lowered V), `split_collar` (two
separate lapels) and `tunic_collar` (narrow laced opening). All keep the face
mouthless, with the red clothing starting at row 41 or 42, below the jaw at
row 35. They use 53/54/54 tiles, fitting the original `$00-$39` allocation.
Actual emulator captures and candidate ROMs are in `build/game-over-collars/`;
`comparison.png` shows enlarged face/upper-torso details from that candidate batch.

Thin collar batch: `thin_shallow`, `thin_v` and `thin_split` use single-pixel
red seams instead of filled neckline areas (51/52/50 tiles). The mouthless
face and all other portrait geometry are unchanged. Emulator captures and
candidate ROMs are in `build/game-over-thin-collars/`, with `comparison.png`.
The selected default is `thin_split`, with its right neck seam now filled black.

Cap/left-neck refinement batch: keyword options `cap='soft'` / `'tucked'`
round the right fold or shorten it further; `neck_mark='none'` / `'original'`
/ `'accent'` remove the left dot, retain it, or extend it to a three-pixel
diagonal seam. The selected defaults are `cap='soft', neck_mark='none'`.
Six combinations A-F use 49-51 tiles; actual emulator captures, candidate ROMs
and a labeled comparison are in `build/game-over-cap-candidates/`.

Right hat/ear join refinements use A (`cap='soft', neck_mark='none'`) as
the base. Keyword `ear_join` selects `notch` (1), `lower_ear` (2), `blend`
(3, filled join), or `round` (4); `original` preserves the base. All use
48-50 tiles. Actual emulator captures, ROMs and `comparison.png` are in
`build/game-over-ear-candidates/`. The final selected default is `ear_join='notch'`.

## Emulator checks

### Sampled roar audio

`python tools/build.py` uses local uncompressed PCM `roms/roar.wav` by default;
`--title-roar-wav PATH` overrides it. `--native-audio` restores the legacy
noise-roar/five-distinct-laugh build. `tools/roar_sample.py` trims boundary
silence, removes DC, chooses the highest NTSC DMC rate that fits without
changing duration, and emits `roar-reference.wav`, `roar-dpcm-preview.wav` and
`roar.dmc` beside the ROM. Only the conversion recipe is tracked;
keep recordings under ignored `roms/` and generated assets under `build/`.

The normal build reclaims native laugh sample data at fixed-bank `$F400-$FD70`
(2,417 bytes maximum, SHA-256 guarded); the hurt sample including its final
byte at `$F3C0` remains unchanged. The approved roar occupies `$F400-$FC80`
(2,177 bytes), unchanged. Four octave-up native waveforms now occupy 65 bytes
`$FC80-$FCC0`, 49 bytes `$FCC0-$FCF0`, 49 bytes `$FD00-$FD30`, and 49 bytes
`$FD40-$FD70`. Silent `$55` endpoints are shared with the roar's final byte
and between the first two waveforms; each byte still has exactly one guarded
overlay writer, and the builder verifies both shared bytes before writing.
The similar opening pair shares the first waveform at rate 6 with lengths
65/49 bytes; the final three use their own native samples, doubled in pitch,
at rates 6/10/10. Original fundamentals are about 270/260/235/205/195 Hz.
The shared opening pair approximates these as 540/540 Hz (the second is about
4% sharp); later voices preserve their individual native pitch and timbre.
Conversion decodes the original once, averages at twice playback speed, removes
DC, and reduces excursion according to RMS slew before DPCM encoding. This
avoids the previous double quantization and reduces low-rate slew distortion.
Volume follow-up (2026-11-17): the production targets now receive 4x gain for
the first three stored waveforms and 2x for the already stronger final waveform.
A forward/backward 1 kHz low-pass before gain frees DAC steps for audible body.
Actual decoded RMS rises about 8-12 dB over the first four-waveform revision;
hardware slew limits prevent a literal 4x increase everywhere. This trades
some treble detail for much stronger output. Sizes, pitches, and timing stay
unchanged. There is still a fidelity/volume compromise from the sample budget.
Native 23-frame spacing is unchanged. `$925A-$925E` calls `RoarNativeRate`;
all other native effects retain rate 15, including Lava Link hurt. No new RAM or
fixed-bank padding is used. Oversized replacement roars fail the packing check.

Game Over onset follow-up (2026-11-17): the initial laugh now waits 36 frames
(about 0.60 seconds), giving the introductory sound time before the laugh.
`RoarLaughDelay` uses 63 guarded bytes of bank-6 vanilla pad `$8F70-$8FAE`.
It latches the native `$E9` request in existing `$05EE` bit 0 while the `$0501`
Game Over timer counts from `$F0` to `$CC`; other audio channels continue.
Leaving Game Over clears the pending latch. It then enters the
native DMC driver, preserving all four 23-frame gaps. No new RAM, fixed-bank
space, sample changes, or gameplay-path work. `tests/game_over_audio.lua`
checks the extra 36-frame onset delay (37 frames from the request, including
the native one-frame audio handoff) separately from the spacing between laughs.

`python tools/game_over_audio.py` writes local A/B WAVs into `build/`:
`original-game-over-laughs.wav`, `game-over-octave-reference.wav` (ideal twice-speed
original), and `game-over-laugh-preview.wav` (actual packed data). These are raw
decoded DAC previews before NES mixing. Use Edge Scenarios F1 for the in-game
comparison and all five starts; F2 begins after the laugh has already started.

The existing title code allocation `$A59E-$A5E7` starts a one-shot at each full
jaw opening (first around frame 78, then every 256 frames). The title uses the
separate bank-6 `$8000` music driver, which normally disables DMC every frame.
A guarded hook at `$8005-$8009` calls a 35-byte conditional enable routine in
the end of annotated `Bank6__UNUSED_0`, `$8FD0-$8FF2`. It preserves
active DMC playback while title `ROAR_TIMER` is live, without restarting an
already completed sample. Leaving title mode clears the timer and stops DMC,
including Start pressed mid-roar. The jaw stays fully open throughout playback.
The title's first-roar pop is prevented by a 38-byte helper at `$8F40-$8F65`:
32 two-step DAC writes ease reset's zero to `$40` before the first opening.
The channel-enable helper now calls this routine and occupies 35 bytes through
`$8FF2`. The title regression checks the exact ramp and no DAC jump at playback.
Title music's own scratch stays untouched; gameplay state is described below.

Validate with `python tools/emulator_test.py tests/title_sample.lua`.
It checks actual DMC ROM reads, active playback,
repeated starts, return to silence and no roar writes to pulse/triangle/noise
registers, synchronized complete jaw art, and Start during a roar returning to
file select with DMC stopped. Converter unit tests exercise LSB-first delta
encoding, DAC settling, hardware length alignment, capacity and rate selection.

Producer recording (2026-11-17): `roar.mp3`, Game Over from the Famicom soundtrack,
copied locally into ignored `roms/roar.mp3` and decoded to `roms/roar.wav` using
FFmpeg from a local `imageio-ffmpeg` install under `build/audio-tools`. The
trimmed whole roar occupies 2,177 bytes at DMC rate 9 (11,186 Hz), 1.557 seconds,
with a 97-frame timer. No pitch/time change. Production ROM SHA-256 is
`22f98416c6732848b05129777e4b738e3d029be44e0c647448e8231e92206fc4`.
The approved pre-promotion roar bytes match production exactly.

Prominence revisions: sample DAC excursion first increased from 20 to 28 steps,
then to 34 for all sampled voice uses (21% above 28, about +1.7 dB before NES
mixing). During the roar,
the two title pulse channels use half their native volume nibble (about -6 dB),
retaining duty/envelope control bits. Normal envelopes continue to advance and
their original volume returns on the next write after the roar. Guarded title
volume hooks `$810F`/`$8116` call register/flag-preserving 20-byte helpers at
`$8F00-$8F27`, using a 256-byte table at `$8E00-$8EFF`, all within annotated
bank-6 UNUSED_0. Triangle, music pitches and tempos are untouched. The title
sample regression checks both ducked and restored volumes against native X.

Playtest: `play/Play Barba.cmd` opens the normal playable ROM. The older
Sampled Roar shortcuts now also use the normal ROM. Stay on the title: first roar
about 1.3 seconds after reset, then every 4.3 seconds. Listen for the original
wobble/rasp, intelligibility against music, volume and clicks; press Start
during a roar to check its cutoff. `build/roar-prototype/title-listening.wav`
is a 10-second actual Mesen audio capture; the standalone DPCM preview is a
decoded sample without the NES mixer/filters. Fidelity approval is a human
listening task. The normal gameplay pack is generated and installed using
`python tools/prepare_test_player.py`; use `play/Test Barba.cmd`.
F2 tests quiet attacks/hurt, F6 Lava
Link's original hurt sound, F9 the boss followed by gem completion. The optional
`--rom` is also supported by `create_test_pack.py`; manifests remain keyed by
the selected ROM hash and are reloaded/validated normally.

Gameplay additions (`src/sampled_roar.inc`, default `SAMPLED_ROAR` assembly):

- Gem victory voice starts immediately after the crystal-placement fanfare
  finishes (2026-11-17). Bank-4 `$9B4D` calls the 12-byte helper at
  `$A7E5-$A7F0`, preserving `STY $070C` and native life/magic refill. It queues
  `$48`: full voice plus gem pose. This bypasses XP/menu deferral and becomes
  `$88` during playback. The renderer holds looking-up frame 8, then returns
  to normal. `$9B83` retains its original save-bit update; final crystal
  removal/XP award cannot queue a second roar. Spell timing stays unchanged.
- Breath attacks use only their native fireball SFX; random attack roars were
  removed on 2026-11-17. SCALES and INFERNO casts still queue full voices.
- Player injury hook `$E314-$E319` uses the existing FarCall0 bridge to a
  bank-0 helper, replacing Link hurt while preserving native recoil setup.
  The 0.527-second prefix (extended from 0.344 seconds on 2026-11-17) ends near
  DAC midpoint and interrupts a full voice; the full roar remains 1.557 seconds.
  Injury-only playback now steps DMC rate 9->8->7->6->5 at audio ticks
  17/21/25/29, dropping about eight semitones and stretching playback to
  ~0.627 seconds. Bit 5 marks injury playback; `$05EF` supplies timing. Full
  voices keep rate 9. The hurt WAV preview includes these pitch steps.
  All sampled voice uses now share a 34-step DAC excursion (up from 28, about
  21% higher target amplitude); sample allocation, rate and full duration match.
  Pending gem victory survives it. Native `$E9=1` (Lava Link hurt) retains the
  original 193-byte `$F300` sample at rate 15, including its last byte `$F3C0`.
- Bank-6 pad `$8C00-$8DF1` (498 bytes) contains the audio coordinator, stable
  controller capture, gameplay pulse ducking and gem torso renderer helper.
  A 14-byte bank-0 call/hop maps the torso helper, which restores bank 0.
  Hook `$9010` owns only DMC
  scheduling; `$9031/$9038` halve pulse volumes while the roar is active and
  restore normal values afterward. Pitches, envelopes and tempo keep advancing.
- `$05EE` is request/active bits (7 active, 6 gem/spell, 5 injury pitch tail,
  3 gem looking-up pose, 2 hurt, 0 pending Game Over laugh), `$05EF`
  retains the legacy start timer, both cleared by native reset. `$64D2/$64D3` cache both raw pads.
  Repeated reads happen in the late audio tick, after the HUD split. Early
  polling hook `$D367-$D36B` uses a 31-byte helper at displaced laugh data
  `$F3C1-$F3DF`: during actual roar playback it returns the late cache (one
  frame of latency); otherwise it continues native polling. DMC status is
  checked as well as the active flag, so a pause/mute cannot trap the controls.
  The initial always-bridged reader delayed the HUD split and was removed.

The default build drops the old bank-0 noise envelope to make room for
cast and hurt requests (2 bank-0 bytes remain; bank3-sign has 250 free). No new
fixed-bank FF padding is claimed. Original Link hurt bytes remain untouched.
`roar_gameplay.lua` covers quiet attacks across all RNG buckets, native crystal/XP updates,
fanfare-end victory, short hurt priority, original Lava Link sample and melody
duck/restore. `roar_controls.lua` covers real-controller pause/resume mid-roar.
HUD timing has zero late splits; sampled volley 16,674 avg / 22,358 peak cycles,
0/900 lag. The usual gameplay/combat/spell/death/far-call regressions also pass.

Put portable [Mesen 2.1.1](https://github.com/SourMesen/Mesen2/releases/tag/2.1.1)
at `.tools/mesen/Mesen.exe`. The headless runner uses a local configuration in
that folder; Lua file access is enabled for checked-in test scripts to write
screenshots and reports into `build/`. Networking remains disabled.

```powershell
python tools/emulator_test.py tests/boot.lua --rom roms/z2.nes
python tools/emulator_test.py tests/gameplay.lua
python tools/emulator_test.py tests/combat.lua
python tools/emulator_test.py tests/palace.lua
python tools/emulator_test.py tests/routines.lua
python tools/emulator_test.py tests/breath_height.lua
```

The runner saves screenshots and logs locally. It does not open a GUI.
Emulator scenario coverage is documented separately from full-playthrough status.
Each run uses a fresh save directory under `build/` and explicitly connects an
NES controller, so unknown-ROM database defaults and existing player saves do
not affect the tests. Run scenarios sequentially: the portable emulator settings
and output directory are shared. Lua errors return failure and produce an
associated `*-error.txt` file. Native emulator logs are retained for diagnosis.

GitHub Actions runs ROM-free tests, assembles the custom code, validates the
art compiler, and checks that no ROMs/saves are tracked. Emulator scenarios
require the user's local ROM and are not run in public CI.

## Adding a cold bank-0 hook

Use the reusable bridge in `src/farcall.inc`:

```asm
; Call site and operand must remain mapped (fixed ROM, or test RAM).
    jsr FarCall0
    .word MyBank0Routine
; Resume here in the ACTUAL caller bank, with target A/X/Y/P.
```

1. Put the routine in BANK0 and end with RTS. Do not deliberately leave another
   bank mapped on return.
2. Add the 5-byte call at an instruction-aligned fixed-bank site or proven free
   space. A standalone returning gateway also needs RTS: **6 bytes**, plus the
   original 3-byte hook. Inside an existing gateway: **5 fixed bytes** per call,
   no per-target table entry.
3. Use only guarded overlay.prg/put writes with expected source bytes, covering
   complete original instructions. See FIXED-BANK-AUDIT.md. FF4B and E02C are
   live JMP operands, not padding.
4. Preserve the identity byte at CPU $8506 in every bank. Build guards check
   source and output identities. $0769 is the saved AREA bank, not a current-bank
   shadow; FFC9 is not a general restoration API. The native mapper is unchanged.
5. Run build, unit tests, farcall.lua, affected gameplay scenarios and perf_volley
   sequentially. Never convert EnemyFireGateway fast path or TerrainBatch to this
   slower generic ABI.

Common cost: **20 fixed bytes + 157 bank-0 bytes**, paid once. Incoming A/X/Y/P
and $00/$01 reach the target unchanged; target register/flag/scratch outputs
survive restoration. Hardware B/U status bits are not state. Stack-local frames
nest: budget 15 stack bytes at bridge peak (including caller JSR), plus target
stack use; 9 extra bytes remain live during the target versus ordinary JSR. No
persistent RAM is used. Use in existing serialized/NMI game logic; this does
not provide asynchronous interrupt/mapper arbitration.

Measured on real Mesen 6502/MMC1, excluding a 26-cycle target body including RTS,
the 5-byte call costs **474 - 15*b cycles**, with actual entry PRG bank b=0..7:
474 from bank0, 429 from bank3, 369 from bank7. Operand page crossing adds up to
2 cycles; target low byte $00 adds 6 for RTS-address borrow. Reserve **482 cycles**
worst case under this link layout, plus target work. Recheck branch/table page
costs after relinking. This ABI is for cold hooks, not per-enemy/projectile/terrain.

Current fixed padding free: **16 bytes**, formerly 11 (LAVA 5, GATEWAY 8,
TERRAIN 3). Bank0: 1169 free; bank3: 283. Only the original three proven spans
are used. Rollback: revert this branch commit and rebuild; no source ROM changes.

The emulator runner copies executable dependencies to build/mesen and writes
settings there, never into the shared .tools junction. Run scenarios sequentially.
No ROM, emulator binary, generated state or build output is tracked.
