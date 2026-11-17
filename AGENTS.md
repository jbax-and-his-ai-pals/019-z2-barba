# Barba Edition: agent quick start

Zelda II (NES, MMC1) ROM hack: the Palace 6 dragon **Barba is the player**. Read
this file first. Then read only the one doc for your task (table below). Don't
read whole docs or the disassembly up front; grep them.

## Commands (repo root; PowerShell or Git Bash)

```text
python tools/build.py                          # build/barba.nes + .bps; source ROM hash-guarded
python -m unittest discover -s tests           # ROM-free unit tests (fast)
python tools/emulator_test.py tests/<name>.lua # one Mesen scenario, headless. Run scenarios one at a time.
python tools/emulator_test.py tests/boot.lua --rom roms/z2.nes
python tools/create_test_pack.py --force       # F1-F10 human checkpoints for the current build
python tools/create_test_pack.py --set edges   # F1 last-life danger, F2 GAME OVER portrait
python tools/create_test_pack.py --set gem     # F1 beside Palace 6 gem; walk right for victory roar/look-up
python tools/create_test_pack.py --set items   # F1 beside Palace 1 Candle; walk left and hold a direction through the celebration
python tools/emulator_test.py tests/perf_volley.lua   # battle lag/CPU/sprites-per-line report
python tools/busy_rooms.py [--sets palaces,movement,world]  # lag + status-bar jitter over test-pack rooms (needs the pack)
```

- Results go to `build/<scenario>.txt` (PASS/FAIL lines plus RESULT). Errors go to `build/<scenario>-error.txt`.
- Each scenario has a 30 s timeout. For longer probes call `emulator_test.run(path, rom, timeout=N)`.
- The producer plays via `play/Play Barba.cmd` and uses checkpoints via `play/Test Barba.cmd`.
  Hand them a playable build (`play/barba.nes` + `build/barba.nes`) plus a regenerated test pack.
- Far-call regression: `python tools/emulator_test.py tests/farcall.lua` (all 8 banks, flags/registers, nesting, boundaries).
- Full suite: boot, gameplay, combat, palace, routines, tall_geometry, projectile_only, burst,
  extra_fire, left_fire, damage, hud_timing, breath_height, town, town_safety, shouts,
  shout_follow, doors, dialogue_speed, perf_volley, perf_lava, link_boss, dark_link,
  shield_enemies, title_roar, overworld_side, farcall, town_fire, town_combo,
  castle_zelda_burn, sign_burn, upstab, perf_upward, look_up, ending, scales, horsehead, helmethead, rebonack, carock,
  gooma, opener_far, lava_link_kill, stomp, geldarm, encounter_hazard, heal_door, spell_door, stab_blocks,
  swamp_submerge, town_nontown_burn, inferno, overworld_fire, forest_burn_limit, meteor, perf_meteor, death_continue, levelup_pane, wizzrobe, plus `state_pack` via create_test_pack.
  (`newgame.lua` and `checkpoint_features.lua` are shared helpers, not scenarios. Check each `build/<name>.txt`
  for FAIL lines and a fresh mtime, not just the exit code; some reports use hyphens, e.g. `perf-volley.txt`.)
  (`boss_fight.lua` is the shared fireball-only boss driver, not a scenario.)

## Hard rules

- `roms/z2.nes` (exact SHA-256 in docs/BUILD.md) is never modified. ROMs, `build/`, `.tools/`
  and saves are never committed. Never commit original game pixels or code. Art is
  extracted at build time (recipes only, e.g. `tools/boss_art.py`).
- Every ROM write in `tools/build.py` goes through `overlay.prg/put` with the **expected
  original bytes**. Overlapping writes are rejected. Keep it that way.
- Edit `tools/build.py` with the Edit tool. A failed Python `write_text` once truncated it.
  `git checkout` restores it.
- Lua strings: never emit a literal newline inside `'...'`. Use `\n` or `string.char(10)`.
  A Lua syntax error makes Mesen exit -1 with **no** error file.

## Layout

| Path | What |
| --- | --- |
| `src/barba.asm` | includes everything; overworld avatar, hitbox, lava, roar, fixed-bank gateways |
| `src/breath.inc` | five-shot volley scheduler, load governor (`BarbaLoadOk`), mouth placement, Inferno and METEOR |
| `src/extra_fire.inc` | 3 extra projectile records multiplexed through native slot 0; enemy/shield collision wrappers |
| `src/blocks.inc` | fireballs break glove-gated blocks |
| `src/geldarm.inc` | bank 1: desert worm sinks into the sand before its death explosion |
| `src/tall_player.inc`, `tall_layout.inc` | 24x48 boss-derived player renderer and head geometry |
| `src/death_display.inc` | fatal-hit silhouette with two full torso chunks |
| `src/dark_barba.inc` | bank 5 24x48 Dark Barba renderer and Triforce-hold pose |
| `src/town*.inc`, `shouts.inc`, `ash_layout.inc` | fleeing/burning villagers, panic dialogue and shouts |
| `src/sign.inc` | bank 3 pad: burned-sign mark and rotating burned-sign text |
| `src/late_split.inc` | bank 3 pad: `LateSplit`, redoes the status-bar/playfield split when NMI work overruns into the next vblank |
| `src/scales.inc` | SCALES (Shield): bank-6 hop to bank-3 `ScalesTick`; navy outline + sky-blue body, cast roar/decor flash, shielded-hit clang/flash |
| `tools/build.py` | assemble + guarded patch list (all hooks are listed here) |
| `tools/assets.py`, `assets/*.json` | sprite compilation; `tools/boss_art.py` extracts boss tiles |
| `tools/state_scenarios.lua` | builds the F-key checkpoints (scene list must match `create_test_pack.py` and `tests/state_pack.lua`) |
| `.tools/z2disassembly/src/prg*.asm` | annotated disassembly (grep by `$ADDR `); `ram-map.txt` |

## Free space and RAM in use (check before allocating)

- Default sampled roar (`roms/roar.wav`, override `--title-roar-wav`;
  `--native-audio` restores legacy): reclaims native laugh data `$F400-$FD70` in bank 7
  (2,417-byte maximum; hurt sample through `$F3C0` preserved), plus a 35-byte
  title DMC enable helper in bank-6 vanilla pad `$8FD0-$8FF2` and hook `$8005`.
  Title music ducking uses `$8E00-$8EFF` (256-byte volume table), `$8F00-$8F27`
  (two 20-byte helpers), and hooks `$810F`/`$8116`; pulse volume halves while
  roaring, normal envelopes continue. Sample DAC amplitude 34 (previously 28;
  initially 20), increased for all sampled voice uses on 2026-11-17.
  Gameplay coordinator/controller/pulse/rate helpers occupy bank 6 `$8C00-$8DA8`
  (425 bytes); the gem helper occupies bank 4 `$A7E5-$A803` (31 bytes). `$9B47`
  queues the roar at fanfare end and holds the ceremony until the roar drains.
  Native refill and its shared XP sound start afterward. Dark Barba's
  bank-5 `$9BAC` hook and `$BF3F-$BF5E` helper reuse the victory roar and
  wait for it to drain before Zelda's awakening. Early cached-pad
  helper uses displaced laugh bytes `$F3C1-$F3DF` (31 bytes), not new padding.
  First-title-pop DAC ramp uses bank 6 `$8F40-$8F65` (38 bytes).
  Initial Game Over laugh delay uses bank 6 `$8F70-$8FB3` (68 guarded pad bytes):
  latches `$E9` in `$05EE` bit 0 and waits 36 frames (~0.60 s) using native
  `$0501`; no new RAM. Pending latch clears outside Game Over.
  Inter-laugh spacing remains 23 frames. Gameplay path and sample bytes unchanged.
  Item pickup uses fixed hook `$E547` via FarCall0 and bank-0 helpers
  `$BF70-$BF96` (39 guarded bytes in the unused reset entry). Preserve mapper
  code at `$BF9D-$BFDF`, including the live overworld call at `$BFB1`.
  Qualifying items lock the standing pose and player input via `$9341/$9D96/$8DC3`.
  Bank-6 pickup logic, `$9B73/$9B24` hooks and shared celebration renderer occupy
  `$8A00-$8B3E` (319 guarded pad bytes). WRAM `$64D4` holds 1 during the
  pickup fanfare and `$80` through the roar and its buffered tail.
  Sampled RAM `$05EE` = request/active bits (7 active, 6 full voice pending,
  5 injury pitch tail, 4 victory draining or complete, 3 raised-head pose, 2 hurt, 1 item roar, 0 delayed Game Over laugh),
  `$05EF` = legacy start timer; WRAM `$64D2/$64D3` = stable raw pads
  captured after the HUD split (one-frame input latency only during playback).
  Default build bank0 has 2 free, bank3-sign 146 free (legacy native: 0/154).
  Random attack roars removed (2026-11-17); native fireball SFX retained.
  Latest normal sampled volley: 16,788 avg / 22,490 peak, 0/900 lag.
  Approved roar stays exactly 2,177 bytes `$F400-$FC80`; Game Over uses four
  octave-up native waveforms: 65 bytes `$FC80-$FCC0`, then 49 bytes each at
  `$FCC0`, `$FD00`, `$FD40` (last ends `$FD70`). Verified silent `$55` endpoints
  share the roar's final byte and first/second waveform boundary; one guarded
  writer per byte. Five starts use first/first/second/third/fourth, lengths
  65/49/49/49/49 and rates 6/6/6/10/10. Opening pair shares pitch (~4% sharp
  on laugh 2); later three retain their own native waveforms one octave up.
  Single-pass, DC-centered encoding: 1 kHz forward/backward low-pass, RMS-slew
  normalization, then 4x/4x/4x/2x target gains (decoded RMS +8-12 dB versus the
  first four-waveform revision); native 23-frame spacing. No size/RAM changes.
  `$925A-$925E` calls `RoarNativeRate`; all non-laugh
  native effects retain rate 15. No new fixed padding/RAM (2026-11-17).
  Legacy `--native-audio` leaves sampled bank-6 ranges unused and uses five
  octave-up DPCM waveforms, lengths 225/161/193/129/129. First laugh pointer moves
  `$F3C0` -> `$F400` to preserve hurt's final byte; native 23-frame spacing.
  No new ROM space or RAM. See docs/BUILD.md.
  Sampled Barba injury prefix extended 0.344 -> 0.527 seconds (2026-11-17),
  using the same sample bytes/allocation; full roar remains 1.557 seconds.
  Injury-only rate descent 9->8->7->6->5 at ticks 17/21/25/29 now stretches
  playback to ~0.627 seconds; no new RAM or sample bytes.

- ROM: bank 0 `$A89E-$A97D` (BANK0_OW; `BarbaSplitBurnForest` + `BurnAbort`; 1 free) + `$AA40-$BF6F` (BANK0; default sampled 2 free, legacy native 0 free) +
  reclaimed dead vanilla bank-0 code `$81C1-$81E4`, `$97F1-$9814`, `$9847-$9877` (METEOR; 0/1/0 free respectively; originals guarded) +
  bank 1 `$9EB9-$9FFF` (BANK1, vanilla pad after Geldarm draw code; `geldarm.inc`; 240 free) +
  `$BFE0-$BFF9` (BANK0_TAIL, vanilla pad before vectors; `BurnMapEndGuard`, 1 free), bank 3 `$9D0A-$9FFF` (BANK3_SIGN, vanilla pad `bank3_UNUSED_9D0A`; `sign.inc` + `TownOpenerGate` + `ScalesTick` + `LateSplit` + `BarbaDeathDisplay`, default sampled 146 free, legacy native 154 free; more vanilla pad untouched at `$8BB1-$90EF` and `$9134-$93FF`), bank 3 `$B803-$BF6F` (TOWN; 2 free), bank 6 `$BA00-$BF6F` (BANK6; `shouts.inc` + `combo.inc` + `ScalesHop`; 2 free), bank 5 `$BDE0-$BF5F` (BANK5; `dark_barba.inc` + `HiddenJarHit`; 33 free).
  Default sampled bank 5 also holds `DarkBarbaVictory` (1 free; legacy native 33 free).
  Bank 4 `$A765-$A8FF` is vanilla `$FF` pad patched by raw bytes in `build.py`: Lava Link helpers `$A765-$A7A8`,
  `HiddenJarHit` `$A7BF-$A7CF`, `CarockHit` `$A7D0-$A7E4` (shared with the P3/4/6 Wizzrobe tail `$AEB2`; boss death gated on `$22`);
  `$A7B0-$A7BE` and `$A804-$A8FF` free; default sampled gem helper uses `$A7E5-$A803`.
  Fixed bank 7: LAVA `$D39A-$D3C9` (0 free), GATEWAY `$FEAA-$FECF` (0 free),
  TERRAIN `$FF4C-$FF6E` (1 free). `FarCall0` provides cold bank-0
  hooks at 5 fixed bytes/call (6 with standalone RTS), 369-482 bridge cycles plus target work;
  see `docs/BUILD.md` for ABI/recipe and `docs/FIXED-BANK-AUDIT.md` for ownership/padding evidence.
  No new fixed-bank padding was claimed. Never allocate live JMP operands `$FF4B` or `$E02C`.
  Rewritten vanilla NMI/sprite code (guarded, 2026-11-16): prologue `$C091-$C0A7` (LateSplit trampoline at `$C09F`),
  tail `$C182-$C1B5` (tail now starts `$C19D`; RTI still `$C1B5`), fast offscreen mask `$F27D-$F2D1` (`$F2D2` spare).
  Block animation allocation (2026-11-16): same-size guarded rewrites `$E0FC-$E109`, `$E23A-$E247`, `$E29C-$E29D` defer brick/floor breaks when all five records are busy; no new space or RAM.
- RAM `$05EA`, `$05EB` (lava contact), `$05EC`/`$05ED` (SCALES cast latch / last injured timer), `$05F0-$05FF` (roar, breath, tall renderer, extra guard). Cleared by the native reset loop.
- Ending fireball uses bank 5 `$8CEB-$8D4D` (existing cutscene patch, 2 bytes free), `$05F8` (state), `$05FA` (X), and OAM `$0240-$0247`. CHR bank 14 pairs `$E0/$E2` (tail) and `$E4/$E6` (head) reuse the displaced ending Link art. Both sprites are hidden on impact.
- WRAM `$6400-$642F` extra projectile records; `$6440-$645F` scratch (`$6457` lazy-save flag,
  `$6458-$645F` geometry terrain cache, `$645C` EXTRA_LIVE); `$6460-$6469` shouts (`$6465` actor, `$6467` word, `$6468` timer, `$6469` cycle); `$646A` + `$6490-$64D0` town scorch ring (16-slot FIFO + head/page); `$646B` volley aim latch (0 forward / $40 upward); `$646C-$646F` + `$6488` town combo banner; `$6470-$6473` Inferno firestorm (`$6470` timer, `$6473` wave aim) and overworld flame (`$6471` timer, `$6472` dir); `$6474` METEOR dive state; `$64D1` `SIGN_PENDING` (sign board scorched, cleared with the ring). Actor byte `$04A0,x` = burned-sign line for sign readers `$21`/`$22` (native spawn clears it). Don't touch collision/room/save regions elsewhere in `$6000-$7FFF`.
- OAM in use: tall head `$04/$4C/$C4`, extra torso (downstab, celebrations and fatal-hit transition) `$20/$24`, extra fireballs `$3C/$44/$48`; enemy projectiles use `$28/$2C/$30`;
  item celebrations use `$34/$40` for the raised item and `$20/$24` for the raised-head torso only;
  victory roar lifts existing art 8px and overlaps its partial torso by 8px for two complete chunks (56px tall, feet anchored);
  town shout word `$DC-$F4` (7 glyphs, only while a word is live and no enemy projectile exists); overworld flame `$FC` (`$02FC-$02FF`).
- CHR: game-over front-facing black Link in bank 17 tiles `$00-$31` (narrowed source-Ganon torso + authored cap/ears/face, mouthless thin split collar, soft cap with right-ear notch, both stray neck marks filled black; bank-0 map `$801F-$80C8`, no new padding/RAM); player art in even sprite banks 0-24; overworld flame pairs `$60/$62` in dedicated overworld bank 30; ash `$7E/$80` **bank 6 only** (shared sprites elsewhere);
  shout glyphs in town BG bank 7 pairs `$32/$7E/$80,$84-$BE` (odd 8x16 bytes) plus `H` (`$7C`) and combo X/1-9/B in town sprite
  bank 6 pairs `$6C-$AE` (even bytes); town scorch art in bank 7 tiles `$AC/$A4` (flame top), `$C1/$C0` (char top),
  `$A7/$C2` (shared bottom); dialogue `?` `$34` and apostrophe `$35` (guarded post-build; text tiles must be `$00-$3F`/`$C0-$FC`). Bank 7 `$00-$27` are villager 8x16 sprites (a byte draws both tiles of its pair):
  never allocate there; `TOWN_SPRITE_PAIRS` in `tools/assets.py` guards them. Bank 7 has no free pair left.

## Performance facts (from tests/perf_volley.lua)

Latest (2026-11-16, block animation allocation fix): Palace 1 idle 13,618/13,682, volley 16,658/22,300, 0/900 lag.
Busiest test-pack rooms (`tools/busy_rooms.py`): P2 floor 24.5k avg / 28.5k worst, P5 before boss 22.9k/27.4k,
Old Kasuto 22.0k/29.0k, 0 lag. The native enemy pass (~9-12k) dominates; Barba's hooks are ~4-5k. Any overrun
that ends inside the next vblank is repaired by `LateSplit` (no status-bar jitter); a longer one still is not.

The game logic runs in NMI. Over about 29.7k cycles the next frame lags. Vanilla peaks near 26.6k
with 6 enemies. Palace 1 `perf_volley.lua` probe (with direct `BarbaExtraBlocks` and `BarbaLoadOk`
2-shot cap for `>= 2` enemies): idle avg/peak 15,980/16,204 cycles, volley 19,491/25,652 (2026-11-16,
fire-class breath, incl. per-frame `ScalesTick`), lag 0/300 idle and **0/900 volley**, `nearBudget(>27000)=0`. `perf_meteor.lua`
(same room, slam + volley every 90 frames): 17,353/19,142, 0/900 lag, 10 slams / 2 waves (`MeteorEmit`
uses `BarbaLoadOk`, throttling waves when an active volley already holds 2 shots in a busy room). Palace 3 room `$0D` (2 Ironknuckles
+ breakable blocks) drops from 28,095 avg / 30,049+ peak (4 lag frames) to 25,338 avg / 28,155
peak (0 lag frames). `BarbaDisplay` bypasses
`$EBF0` on normal frames (using `$F27D` + unrolled 9-sprite
draw) and `BarbaGeometry` caches `TerrainBatch` in `$6458-$645F`, cutting display cost from ~4.0k
to ~1.2k cycles/frame. `BarbaLoadOk` uses `LOAD_LIMIT = 7` and caps queued shots at 2 live shots
when 2+ enemies are active.

Audit resolution (2026-11-15): six-Bot METEOR + volley stress now runs at **0/900 lag**
(`maxLiveShots = 1`, peak `28,983` cycles), down from `160/900` lag, with `BarbaLoadOk` gating
`BarbaFireSpell` and `MeteorEmit`. All 9 audit findings in `docs/AUDIT-2026-11-15.md` (Thunderbird
Inferno softlock, METEOR load governor, Dark Barba tile table + shadow palette, hidden red jars,
checkpoint room/palette fixes, test failure propagation, town scorch page aliasing, refused forest
burn PPU cancel, and Geldarm stomp sink) are resolved and verified.

## Status and docs (read only what you need)

| Topic | Doc |
| --- | --- |
| What's verified / open | docs/STATUS.md |
| Breath, volley, tall sprite internals | docs/BREATH-IMPLEMENTATION.md |
| Towns, villagers, shouts | docs/TOWNS.md |
| Build/tooling, ROM research | docs/BUILD.md, docs/RESEARCH.md, docs/FIXED-BANK-AUDIT.md |
| Checkpoints | docs/TEST-PACK.md (F1-F9; F9 = before Palace 6 boss, max stats) |
| Archived plans & early design | docs/archive/ |

When you finish a task: update the one relevant doc plus STATUS.md, and keep this file's
memory map and perf facts current. Then hand the producer a short playtest: what changed, which F-key, what to look for.

Historical upstab branch performance: standard volley peak 30,158 (+39 versus 262501a), unchanged 1/900 lag;
lava peak 21,699 (+22), 0/300 lag. Current fresh-audit six-active-Bot `perf_upward`: 25,984 peak, 0/900 lag,
25 upward emissions. `BarbaSetThrusts` restores rising technique-gated
head-butt after block checks; `VOLLEY_SLOT` bit 6 up, bit 7 crouch, low 6 bits lifetime.
