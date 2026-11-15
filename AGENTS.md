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
- Full suite: boot, gameplay, combat, palace, routines, tall_geometry, projectile_only, burst,
  extra_fire, left_fire, damage, hud_timing, breath_height, town, town_safety, shouts,
  shout_queue, shout_follow, doors, dialogue_speed, town_fire, title_roar, perf_volley, plus `state_pack` via create_test_pack.

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
| `src/breath.inc` | five-shot volley scheduler, load governor (`BarbaLoadOk`), mouth placement |
| `src/extra_fire.inc` | 3 extra projectile records multiplexed through native slot 0; enemy/shield collision wrappers |
| `src/blocks.inc` | fireballs break glove-gated blocks |
| `src/tall_player.inc`, `tall_layout.inc` | 24x48 boss-derived player renderer and head geometry |
| `src/town*.inc`, `shouts.inc`, `ash_layout.inc` | fleeing/burning villagers, panic dialogue and shouts |
| `tools/build.py` | assemble + guarded patch list (all hooks are listed here) |
| `tools/assets.py`, `assets/*.json` | sprite compilation; `tools/boss_art.py` extracts boss tiles |
| `tools/state_scenarios.lua` | builds the F-key checkpoints (scene list must match `create_test_pack.py` and `tests/state_pack.lua`) |
| `.tools/z2disassembly/src/prg*.asm` | annotated disassembly (grep by `$ADDR `); `ram-map.txt` |

## Free space and RAM in use (check before allocating)

- ROM: bank 0 `$AA40-$BF6F` (BANK0; about $9B0 used), bank 3 `$B803-$BF6F` (TOWN),
  fixed bank 7: `$D39A` LAVA (5 bytes left), `$FEAA` GATEWAY (about 8 left), `$FF4C-$FF6F` TERRAIN (about 3 left).
  **The fixed bank is essentially full.** See `build/barba.map` for exact use.
- RAM `$05EA`, `$05EB` (lava contact), `$05F0-$05FF` (roar, breath, tall renderer, extra guard). Cleared by the native reset loop.
- WRAM `$6400-$642F` extra projectile records; `$6440-$645F` scratch (`$6457` lazy-save flag,
  `$6458-$645F` geometry terrain cache, `$645C` EXTRA_LIVE); `$6460-$6469` shouts (`$6465` actor, `$6467` word, `$6468` timer, `$6469` cycle); `$646A` + `$6470-$6487` town scorch ring. Don't touch collision/room/save regions elsewhere in `$6000-$7FFF`.
- OAM in use: tall head `$04/$4C/$F8`, extra fireballs `$3C/$44/$48`; enemy projectiles use `$28/$2C/$30`;
  town shout word `$E0-$F0` (only while a word is live and no enemy projectile exists).
- CHR: player art in even sprite banks 0-24; ash `$64/$66` **bank 6 only** (shared sprites elsewhere);
  shout glyphs in town BG bank 7 pairs `$80-$A0` (used as odd 8x16 sprite tiles); town scorch art in bank 7
  tiles `$02/$04/$0E/$16` (flame) and `$25/$96/$A7/$B9` (char).

## Performance facts (from tests/perf_volley.lua)

The game logic runs in NMI. Over about 29.7k cycles the next frame lags. Vanilla peaks near 26.6k
with 6 enemies. `BarbaDisplay` bypasses `$EBF0` on normal frames (using `$F27D` + unrolled 9-sprite
draw) and `BarbaGeometry` caches `TerrainBatch` in `$6458-$645F`, cutting display cost from ~4.0k
to ~1.2k cycles/frame. `BarbaLoadOk` uses `LOAD_LIMIT = 7` (allows 2 simultaneous shots in 6-enemy
overworld fights with 0 lag frames, max 28,941 cycles, and 4/900 lag frames in Palace 1 volley).

## Status and docs (read only what you need)

| Topic | Doc |
| --- | --- |
| What's verified / open | docs/STATUS.md, docs/ROADMAP.md |
| Breath, volley, tall sprite internals | docs/BREATH-IMPLEMENTATION.md |
| Towns, villagers, shouts | docs/TOWNS.md |
| Perf/flicker/shout follow-ups | docs/NEXT-PERF-AND-SHOUTS.md |
| Palace 6 "Lava Link" boss plan | docs/LINK-BOSS-PLAN.md |
| Upward fire / upstab design (draft) | docs/UPSTAB-FIRE-PLAN.md |
| Build/tooling, ROM research | docs/BUILD.md, docs/RESEARCH.md |
| Checkpoints | docs/TEST-PACK.md (F1-F9; F9 = before Palace 6 boss, max stats) |

When you finish a task: update the one relevant doc plus STATUS.md, and keep this file's
memory map and perf facts current. Then hand the producer a short playtest: what changed, which F-key, what to look for.
