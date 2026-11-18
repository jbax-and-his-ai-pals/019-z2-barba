# Barba Edition: agent quick start

Zelda II (NES, MMC1) ROM hack: the Palace 6 dragon **Barba is the player**. Read
this file first, then read only the one doc for your task (table at bottom). Don't
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
python tools/create_test_pack.py --set busy    # F1-F3 Palace 5 Magos; F4-F10 busy palace and town rooms
python tools/create_test_pack.py --set movement # F5 bridge water/clouds, F6 cave liquid, F10 grass scenery
python tools/emulator_test.py tests/perf_volley.lua   # battle lag/CPU/sprites-per-line report
python tools/busy_rooms.py [--sets busy]        # lag + status-bar jitter over test-pack rooms (needs the pack)
```

- Results go to `build/<scenario>.txt` (PASS/FAIL lines plus RESULT). Errors go to `build/<scenario>-error.txt`.
- Each scenario has a 30 s timeout. For longer probes call `emulator_test.run(path, rom, timeout=N)`.
- The producer plays via `play/Play Barba.cmd` and uses checkpoints via `play/Test Barba.cmd`.
  Hand them a playable build (`play/barba.nes` + `build/barba.nes`) plus a regenerated test pack.
- Far-call regression: `python tools/emulator_test.py tests/farcall.lua` (all 8 banks, flags/registers, nesting, boundaries).
- Darunia F6 encounter exit regression: run `tests/darunia_exit.lua` with the generated world pack's ROM. See `docs/TEST-PACK.md`.
- Full suite: `boot`, `gameplay`, `combat`, `palace`, `routines`, `tall_geometry`, `projectile_only`, `burst`,
  `extra_fire`, `left_fire`, `damage`, `hud_timing`, `breath_height`, `town`, `town_safety`, `shouts`,
  `shout_follow`, `doors`, `dialogue_speed`, `perf_volley`, `perf_lava`, `link_boss`, `dark_link`, `dark_wyrmling`,
  `shield_enemies`, `title_roar`, `overworld_side`, `scanline_irq`, `ow_clouds`, `farcall`, `town_fire`, `town_combo`,
  `castle_zelda_burn`, `sign_burn`, `upstab`, `perf_upward`, `look_up`, `ending`, `scales`, `horsehead`, `helmethead`, `rebonack`, `carock`, `carock_reflect`,
  `gooma`, `opener_far`, `lava_link_kill`, `stomp`, `geldarm`, `encounter_hazard`, `heal_door`, `spell_door`, `stab_blocks`,
  `swamp_submerge`, `town_nontown_burn`, `inferno`, `overworld_fire`, `forest_burn_limit`, `meteor`, `perf_meteor`, `death_continue`, `levelup_pane`, `wizzrobe`, `rock_lizalfos`, `roar_gameplay`, `roar_controls`, `title_sample`, `game_over_audio`, `item_roar`, plus `state_pack` via `create_test_pack`.
  (`newgame.lua`, `checkpoint_features.lua`, `boss_fight.lua` are shared helpers, not scenarios. Check each `build/<name>.txt`
  for FAIL lines and a fresh mtime, not just the exit code; some reports use hyphens, e.g. `perf-volley.txt`.)

## Hard rules

- `roms/z2.nes` (exact SHA-256 in `docs/BUILD.md`) is never modified. ROMs, `build/`, `.tools/`,
  and saves are never committed. Never commit original game pixels or code. Art is
  extracted at build time (recipes only, e.g. `tools/boss_art.py`).
- Every ROM write in `tools/build.py` goes through `overlay.prg/put` with the **expected
  original bytes**. Overlapping writes are rejected. Keep it that way.
- Edit `tools/build.py` with the Edit tool (a failed Python `write_text` once truncated it; `git checkout` restores it).
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
| `src/sampled_roar.inc` | sampled roar audio coordinator, item/gem/Dark Barba roar hooks (default; `--native-audio` disables) |
| `src/town*.inc`, `shouts.inc`, `ash_layout.inc` | fleeing/burning villagers, panic dialogue and shouts |
| `src/sign.inc` | bank 3 pad: burned-sign mark and rotating burned-sign text |
| `src/late_split.inc` | unused (superseded by MMC3 scanline IRQ HUD split) |
| `src/scanline_irq.inc` | MMC3 scanline IRQ engine: HUD split (line 31), encounter sky parallax, VBlank sprig sway on R0 and water/swamp/lava on R1 (`UpdateSceneryChr6`), letterbox, `$6500` OAM shadow |
| `src/scales.inc` | SCALES (Shield): bank-6 `ScalesTick` (from `BarbaShouts6`); navy outline + sky-blue body, cast roar/decor flash, shielded-hit clang/flash |
| `tools/build.py` | assemble + guarded patch list (all hooks are listed here) |
| `tools/assets.py`, `assets/*.json` | sprite compilation; `tools/boss_art.py` extracts boss tiles |
| `tools/state_scenarios.lua` | builds the F-key checkpoints (scene list must match `create_test_pack.py` and `tests/state_pack.lua`) |
| `.tools/z2disassembly/src/prg*.asm` | annotated disassembly (grep by `$ADDR `); `ram-map.txt` |

## Free space and RAM in use (check before allocating)

### ROM banks & free space (default sampled build; `--native-audio` in parens)

| Bank | Region | Contents / Notes | Free |
| --- | --- | --- | --- |
| 0 | `$A89E-$A97D` (`BANK0_OW`) | `BarbaSplitBurnForest` + `BurnAbort` | 1 |
| 0 | `$AA40-$BF6F` (`BANK0`) | Core Barba code; `$BF70-$BF96` item pickup helpers; preserve mapper `$BF9D-$BFDF` (`$BFB1` live OW call) | 420 |
| 0 | `$BFE0-$BFF9` (`BANK0_TAIL`) | `BurnMapEndGuard` (before vectors) | 1 |
| 0 | `$81C1-$81E4`, `$97F1-$9814`, `$9847-$9877` | Reclaimed dead vanilla code (METEOR) | 0 / 1 / 0 |
| 1 | `$9EB9-$9FFF` (`BANK1`) | `geldarm.inc` (after Geldarm draw code) | 240 |
| 2 | `$9F85-$9FA0` | Valley of Death Lizalfos breath check (hook `$977C`) | 0 |
| 3 | `$9D0A-$9FFF` (`BANK3_SIGN`) | `sign.inc`, `TownOpenerGate`, `LateSplit`, `BarbaDeathDisplay` (untouched vanilla pad at `$8BB1-$90EF`, `$9134-$93FF`) | 255 |
| 3 | `$B803-$BF6F` (`TOWN`) | Town villagers, dialogue, combo | 28 |
| 4 | `$A765-$A8FF` (raw pad) | Lava Link `$A765-$A7A8`, `HiddenJarHit` `$A7BF-$A7CF`, `CarockHit` `$A7D0-$A7E4` (boss death gated on `$22`), gem helper `$A7E5-$A803`, `CarockReflectDamage` `$A804-$A80E` (24 dmg; HP 48 at `$A943`, HUD scale at `$AE82`) | `$A7B0-$A7BE`, `$A80F-$A8FF` |
| 5 | `$BDE0-$BF5F` (`BANK5`) | `dark_barba.inc`, `HiddenJarHit`, `DarkBarbaVictory` (`$BF3B-$BF5A`, hook `$9BAC`) | 9 (41) |
| 5 | `$8CEB-$8D4D` | Ending fireball cutscene patch | 2 |
| 6 | `$AC09-$BF6F` (`BANK6`) | `shouts.inc`, `combo.inc`, `scales.inc`, `scanline_irq.inc`, `DarkLinkFireCheck`, town/castle scorch, `LagNmiInBank6` | 861 (874) |
| 6 | `$8A00-$8FFF` (vanilla pad) | Sampled audio: `$8A00-$8B3E` pickup/celebration (`$9B73/$9B24`), `$8C00-$8DA8` coordinator/ducking/rate, `$8E00-$8EFF` title duck table, `$8F00-$8F27` title duck helpers (`$810F/$8116`), `$8F40-$8F65` title DAC ramp, `$8F70-$8FB3` Game Over laugh delay, `$8FD0-$8FF2` title DMC enable (`$8005`) | â€” |
| 7 | `$D39A-$D3C9` (`LAVA`), `$FEAA-$FECF` (`GATEWAY`), `$FF4C-$FF6E` (`TERRAIN`) | Fixed bank allocations (`FarCall0`: 5 B/call, 6 B w/ RTS; see `docs/BUILD.md`). Never allocate live JMP operands `$FF4B` or `$E02C` | 0 / 0 / 1 |
| 7 | `$F400-$FD70` | Sampled roar (`$F400-$FC80`, 2,177 B) + 4 octave-up Game Over laughs (`$FC80-$FD70`, shared `$55` endpoints); `$F3C1-$F3DF` early cached-pad helper; hurt `$F300-$F3C0` preserved | 0 |

- **Fixed-bank guarded vanilla rewrites** (no new padding claimed): NMI prologue `$C091-$C0A7` (`LateSplit` trampoline `$C09F`), NMI tail `$C182-$C1B5` (tail starts `$C19D`, RTI `$C1B5`), fast offscreen mask `$F27D-$F2D1` (`$F2D2` spare), block anim `$E0FC-$E109`/`$E23A-$E247`/`$E29C-$E29D`, enemy projectile update `$E3B9-$E3C8` (empty-slot helper `$E3C1`), empty enemy slot skip & direct dispatch `$D5DA-$D5F8` (`$D5F6-$D5F8` 3 B spare).

### RAM, WRAM, OAM & CHR

- **RAM**: `$05EA`, `$05EB` (lava contact), `$05EC`/`$05ED` (SCALES cast latch / last injured timer), `$05EE` (sampled roar bits: 7 active, 6 full pending, 5 injury pitch tail, 4 victory draining/done, 3 raised-head pose, 2 hurt, 1 item roar, 0 Game Over laugh delay), `$05EF` (legacy start timer), `$05F0-$05FF` (roar, breath, tall renderer, extra guard; `$05F8`/`$05FA` ending fireball state/X). Cleared by native reset.
- **WRAM** (don't touch collision/room/save regions elsewhere in `$6000-$7FFF`):
  - `$6400-$642F`: extra projectile records
  - `$6440-$645F`: scratch (`$6457` lazy-save, `$6458-$645F` geometry terrain cache, `$645C` `EXTRA_LIVE`)
  - `$6460-$6469`: shouts (`$6465` actor, `$6467` word, `$6468` timer, `$6469` cycle)
  - `$646A`, `$6490-$64D0`: town scorch ring (16-slot FIFO + head/page); `$64D1` `SIGN_PENDING`; `$04A0,x` burned-sign line (`$21`/`$22`)
  - `$646B` volley aim latch (`0` forward / `$40` up); `$646C-$646F` + `$6488` town combo banner
  - `$6470-$6473`: Inferno timer/wave aim (`$6470`/`$6473`), overworld flame timer/dir (`$6471`/`$6472`); `$6474` METEOR dive state
  - `$64D2/$64D3`: late raw pads cache (sampled audio); `$64D4`: item pickup hold (`1` fanfare, `$80` roar/tail); `$64D5`: MMC3 `$8000` bank-select shadow (saved/restored by `LagNmiBank6` / `LagNmiReturn`)
  - `$64D6-$64F1`: scanline IRQ and scenery state (`IRQ_STAGE`, `IRQ_COUNT`, `IRQ_LINES`, `IRQ_X`, `IRQ_CTRL`, `IRQ_MASK`, `ROOM_HAS_LAVA`, cache/temps, `OW_PARALLAX_LINE` `$64EE`, active liquid `R1` `$64EF`, `OW_HAS_GRASS` `$64F0`, `OW_HAS_WATER` `$64F1`)
  - `$6500-$65FF`: OAM DMA shadow page (8x16 sprite tiles rebased to the swapped pattern tables, with native blank `$F5` cells hidden to avoid extra MMC3 A12 clocks)
- **OAM**: tall head `$04/$4C/$C4`; extra torso `$20/$24`; item celebration `$34/$40` (item) + `$20/$24` (torso); extra fireballs `$3C/$44/$48`; enemy projectiles `$28/$2C/$30`; fall-in-hole (`Game Mode $0F`, `BarbaFallDraw`) `$08..$2C` Barba + `$30..$54` shadow; ending fireball `$40-$47`; shout word `$DC-$F4` (7 glyphs); overworld flame `$FC` (`$74/$84/$94`).
- **CHR**: Game Over black Link in bank 17 `$00-$31` (map `$801F-$80C8`); even sprite banks 0-24 reserve `$24` for Myu and use `$5C`; overworld flame `$60/$62` (bank 30); ending fireball `$E0/$E2`, `$E4/$E6` (bank 14); ash `$7E/$80` (bank 6 only); shout glyphs bank 7 `$32/$7E/$80,$84-$BE` + `H` (`$7C`) and combo glyphs bank 6 `$6C-$AE`; town scorch bank 7 `$AC/$A4`, `$C1/$C0`, `$A7/$C2`; dialogue `?` `$34`, apostrophe `$35`. **Bank 7 `$00-$27` are villager 8x16 sprites â€” never allocate there** (`TOWN_SPRITE_PAIRS` in `tools/assets.py` guards them; bank 7 has no free pair left).

## Current performance baseline (`c8fcedb109c5`, MMC3 Checkpoint A)

Game logic runs in NMI; >~29.7k cycles lags the next frame (`LateSplit` repairs overruns ending inside vblank). `BarbaLoadOk` uses `LOAD_LIMIT = 7` and caps queued shots at 2 live shots when `>= 2` enemies are active (1 on 6-Bot METEOR stress). All benchmarks below run at **0 lag, 0 late splits, 0 HUD shifts**:
- `perf_volley.lua` (Palace 1): idle `12,063 avg / 12,126 peak`; volley `15,169 avg / 21,048 peak` (`0/900` lag, `nearBudget(>27000)=0`).
- `perf_meteor.lua` (Palace 1): `13,262 avg / 15,117 peak` (`0/900` lag, 10 slams / 2 waves; MMC1 baseline, re-verified pass on MMC3).
- `perf_upward.lua` (6 active Bots): idle `22,866 avg / 23,113 peak`; upward `24,149 avg / 24,834 peak` (MMC1 baseline). Build `3a0a52742da5`: idle `23,811 avg / 24,560 peak`; upward `25,142 avg / 26,486 peak`, with `0/900` lag and no frames above 27,000 cycles.
- `perf_lava.lua`: floor `15,800 avg / 16,573 peak`; lava `15,311 avg / 17,309 peak` (`0` lag; MMC1 baseline, re-verified pass on MMC3).
- `busy_rooms.py` (`--sets core,busy`, 480 frames/state): `old-kasuto` `28,492` work / `28,515` NMI max, `p2-crowded-floor` `28,213 / 28,236`, `p5-gooma-approach` `27,349 / 27,372`, `p3-ironknuckle-blocks` `24,391 / 24,414`.

## Status and docs (read only what you need)

| Topic | Doc |
| --- | --- |
| What's verified / open | `docs/STATUS.md` |
| Breath, volley, tall sprite internals | `docs/BREATH-IMPLEMENTATION.md` |
| Towns, villagers, shouts | `docs/TOWNS.md` |
| Build/tooling, sampled audio, cold hooks | `docs/BUILD.md`, `docs/RESEARCH.md`, `docs/FIXED-BANK-AUDIT.md` |
| Checkpoints | `docs/TEST-PACK.md` (F1-F9; F9 = before Palace 6 boss, max stats) |
| Archived plans, changelog, resolved audit | `docs/archive/`, `docs/AUDIT-2026-11-15.md` |

When you finish a task: update the one relevant doc plus `docs/STATUS.md`, and keep this file's
memory map and perf facts current. Then hand the producer a short playtest: what changed, which F-key, what to look for.
