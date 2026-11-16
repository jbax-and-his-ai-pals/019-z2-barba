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
python tools/emulator_test.py tests/perf_volley.lua   # battle lag/CPU/sprites-per-line report
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
  castle_zelda_burn, sign_burn, upstab, perf_upward, look_up, ending, horsehead, helmethead, rebonack, carock,
  gooma, opener_far, lava_link_kill, stomp, geldarm, encounter_hazard, heal_door, spell_door, stab_blocks,
  swamp_submerge, town_nontown_burn, inferno, overworld_fire, forest_burn_limit, meteor, perf_meteor, death_continue, plus `state_pack` via create_test_pack.
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
| `src/dark_barba.inc` | bank 5 24x48 Dark Barba renderer and Triforce-hold pose |
| `src/town*.inc`, `shouts.inc`, `ash_layout.inc` | fleeing/burning villagers, panic dialogue and shouts |
| `src/sign.inc` | bank 3 pad: burned-sign mark and rotating burned-sign text |
| `tools/build.py` | assemble + guarded patch list (all hooks are listed here) |
| `tools/assets.py`, `assets/*.json` | sprite compilation; `tools/boss_art.py` extracts boss tiles |
| `tools/state_scenarios.lua` | builds the F-key checkpoints (scene list must match `create_test_pack.py` and `tests/state_pack.lua`) |
| `.tools/z2disassembly/src/prg*.asm` | annotated disassembly (grep by `$ADDR `); `ram-map.txt` |

## Free space and RAM in use (check before allocating)

- ROM: bank 0 `$A89E-$A97D` (BANK0_OW; `BarbaSplitBurnForest` + `BurnAbort`; 1 free) + `$AA40-$BF6F` (BANK0; 4 free) +
  reclaimed dead vanilla bank-0 code `$81C1-$81E4`, `$97F1-$9814`, `$9847-$9877` (METEOR; 0/1/0 free respectively; originals guarded) +
  bank 1 `$9EB9-$9FFF` (BANK1, vanilla pad after Geldarm draw code; `geldarm.inc`; 240 free) +
  `$BFE0-$BFF9` (BANK0_TAIL, vanilla pad before vectors; `BurnMapEndGuard`, 1 free), bank 3 `$9D0A-$9FFF` (BANK3_SIGN, vanilla pad `bank3_UNUSED_9D0A`; `sign.inc` + `TownOpenerGate`, 474 free; more vanilla pad untouched at `$8BB1-$90EF` and `$9134-$93FF`), bank 3 `$B803-$BF6F` (TOWN; 2 free), bank 6 `$BA00-$BF6F` (BANK6; `shouts.inc` + `combo.inc`; 16 free), bank 5 `$BDE0-$BF5F` (BANK5; `dark_barba.inc` + `HiddenJarHit`; 33 free).
  Bank 4 `$A765-$A8FF` is vanilla `$FF` pad patched by raw bytes in `build.py`: Lava Link helpers `$A765-$A7A8`,
  `CarockHit` `$A7B0-$A7BE`, `HiddenJarHit` `$A7BF-$A7CF`; `$A7D0-$A8FF` free.
  Fixed bank 7: LAVA `$D39A-$D3C9` (0 free), GATEWAY `$FEAA-$FECF` (0 free),
  TERRAIN `$FF4C-$FF6E` (1 free). `FarCall0` provides cold bank-0
  hooks at 5 fixed bytes/call (6 with standalone RTS), 369-482 bridge cycles plus target work;
  see `docs/BUILD.md` for ABI/recipe and `docs/FIXED-BANK-AUDIT.md` for ownership/padding evidence.
  No new fixed-bank padding was claimed. Never allocate live JMP operands `$FF4B` or `$E02C`.
- RAM `$05EA`, `$05EB` (lava contact), `$05F0-$05FF` (roar, breath, tall renderer, extra guard). Cleared by the native reset loop.
- WRAM `$6400-$642F` extra projectile records; `$6440-$645F` scratch (`$6457` lazy-save flag,
  `$6458-$645F` geometry terrain cache, `$645C` EXTRA_LIVE); `$6460-$6469` shouts (`$6465` actor, `$6467` word, `$6468` timer, `$6469` cycle); `$646A` + `$6490-$64D0` town scorch ring (16-slot FIFO + head/page); `$646B` volley aim latch (0 forward / $40 upward); `$646C-$646F` + `$6488` town combo banner; `$6470-$6473` Inferno firestorm (`$6470` timer, `$6473` wave aim) and overworld flame (`$6471` timer, `$6472` dir); `$6474` METEOR dive state; `$64D1` `SIGN_PENDING` (sign board scorched, cleared with the ring). Actor byte `$04A0,x` = burned-sign line for sign readers `$21`/`$22` (native spawn clears it). Don't touch collision/room/save regions elsewhere in `$6000-$7FFF`.
- OAM in use: tall head `$04/$4C/$C4`, extra fireballs `$3C/$44/$48`; enemy projectiles use `$28/$2C/$30`;
  town shout word `$DC-$F4` (7 glyphs, only while a word is live and no enemy projectile exists); overworld flame `$FC` (`$02FC-$02FF`).
- CHR: player art in even sprite banks 0-24; overworld flame pairs `$60/$62` in dedicated overworld bank 30; ash `$7E/$80` **bank 6 only** (shared sprites elsewhere);
  shout glyphs in town BG bank 7 pairs `$32/$7E/$80,$84-$BE` (odd 8x16 bytes) plus `H` (`$7C`) and combo X/1-9/B in town sprite
  bank 6 pairs `$6C-$AE` (even bytes); town scorch art in bank 7 tiles `$34/$A4/$AC/$C0` (flame) and
  `$C1/$35/$A7/$C2` (char). Bank 7 `$00-$27` are villager 8x16 sprites (a byte draws both tiles of its pair):
  never allocate there; `TOWN_SPRITE_PAIRS` in `tools/assets.py` guards them. Bank 7 has no free pair left.

## Performance facts (from tests/perf_volley.lua)

The game logic runs in NMI. Over about 29.7k cycles the next frame lags. Vanilla peaks near 26.6k
with 6 enemies. Palace 1 `perf_volley.lua` probe (with direct `BarbaExtraBlocks` and `BarbaLoadOk`
2-shot cap for `>= 2` enemies): idle avg/peak 15,862/16,086 cycles, volley 19,373/25,533 (2026-11-15,
fire-class breath), lag 0/300 idle and **0/900 volley**, `nearBudget(>27000)=0`. `perf_meteor.lua`
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
lava peak 21,699 (+22), 0/300 lag. Current fresh-audit six-active-Bot `perf_upward`: 28,829 peak, 0/900 lag,
25 upward emissions. `BarbaSetThrusts` restores rising technique-gated
head-butt after block checks; `VOLLEY_SLOT` bit 6 up, bit 7 crouch, low 6 bits lifetime.
