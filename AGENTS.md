# Barba Edition: agent quick start

Zelda II ROM hack starring the Palace 6 dragon **Barba** (a Barba/Link swap),
paired with a series of NES ROM-hack **subgames** accessible both through
in-game Zelda II portals/hooks and as standalone ROMs. Each subgame propagates
the Barba/Link swap trope thematically into another NES game—preserving the
guest game's core gameplay while bringing over Barba and selected art/audio/theme
elements from Zelda II. Migrating each subgame ROM to the best architecture
(e.g., MMC3 for scanline IRQs, CHR bankswitching, animations, and subtle polish
all over) is **strongly encouraged as part of ingestion**, just like we did
with Zelda II (see `docs/SUBGAME-INTAKE.md` and `docs/SUBGAME-REWARDS.md`).

The clean Zelda II source is USA PRG0 (MMC1). The combined development ROM is
NES 2.0 Mapper 176 and runs Zelda II in MMC3-compatible mode. Read this file
first, then the relevant doc below. Search the disassembly by address.

## Commands (repo root; PowerShell or Git Bash)

```text
python tools/build.py                          # combined build; inputs and checksums in docs/BUILD.md
python tools/build_history.py                  # raw CSV of successful numbered ROM builds
python -m unittest discover -s tests           # ROM-free unit tests (fast)
python tools/emulator_test.py tests/<name>.lua # one Mesen scenario, headless. Run scenarios one at a time.
python tools/emulator_test.py tests/boot.lua --rom roms/z2.nes
python tools/create_test_pack.py --force       # F1-F10 human checkpoints for the current build
python tools/create_test_pack.py --set edges   # F1 last-life danger, F2 GAME OVER portrait
python tools/create_test_pack.py --set gem     # F1 beside Palace 6 gem; walk right for the victory roar and floor pulse
python tools/emulator_test.py tests/palace_roar.lua # crystal floor pulse and tile restore in all six palaces
python tools/create_test_pack.py --set items   # F1 beside Palace 1 Candle; walk left and hold a direction through the celebration
python tools/create_test_pack.py --set busy    # F1-F3 Palace 5 Magos; F4-F10 busy palace and town rooms
python tools/create_test_pack.py --set movement # F5 bridge water/clouds, F6 cave liquid, F10 grass scenery
python tools/create_test_pack.py --set endgame  # F9 East Hyrule grass encounter
python tools/create_test_pack.py --set bosses   # F1–F8 palace boss checkpoints
python tools/emulator_test.py tests/boss_meter.lua # all eight boss meters, with current Bosses pack
python tools/emulator_test.py tests/perf_volley.lua   # battle lag/CPU/sprites-per-line report
python tools/busy_rooms.py [--sets busy]        # lag + status-bar jitter over test-pack rooms (needs the pack)
```

- Results go to `build/<scenario>.txt` (PASS/FAIL lines plus RESULT). Errors go to `build/<scenario>-error.txt`.
- The Barba ROM builder automatically numbers successful builds, including identical rebuilds and alternate outputs. The number is in `build-report.json`, and the checkout-local `.build-history.sqlite3` keeps the history across cleans of `build/`. Use `python tools/build_history.py` for raw CSV and `--release VERSION` when building a release candidate. See [build numbering](docs/BUILD.md#build-numbers-and-history).
- Each scenario has a 30 s timeout. For longer probes call `emulator_test.run(path, rom, timeout=N)`.
- The producer plays via `play/Play Barba.cmd` and uses checkpoints via `play/Test Barba.cmd`.
  Hand them a playable build (`play/barba.nes` + `build/barba.nes`) plus a regenerated test pack.
  `./tools/launch.ps1 -NoRebuild -TestPack -CheckpointSet <set>` uses the existing artifact.
- Far-call regression: `python tools/emulator_test.py tests/farcall.lua` (all 8 banks, flags/registers, nesting, boundaries).
- Game Over audio regression: generate the current `edges` pack, then run `python tools/emulator_test.py tests/game_over_audio.lua`.
- Shield rebound regression: run `python tools/emulator_test.py tests/shield_enemies.lua`. In Busy Areas F4, face left and fire at the approaching Ironknuckle to see the rebound.
- Palace drop audio and music restart regression: generate the current `movement` pack, then run `python tools/emulator_test.py tests/fall_roar.lua`.
- Waldo portal regressions: run `tests/waldo_in_rom.lua` for Start+Select and `tests/waldo_moon_return.lua` for the automatic Moon return. Regenerate the Waldo checkpoints with `python tools/create_waldo_z2_pack.py --force --prepare-only`.
- Darunia F6 encounter exit regression: run `tests/darunia_exit.lua` with the generated world pack's ROM. See `docs/TEST-PACK.md`.
- Full suite: `boot`, `gameplay`, `combat`, `palace`, `routines`, `tall_geometry`, `projectile_only`, `burst`,
  `extra_fire`, `left_fire`, `damage`, `hud_timing`, `breath_height`, `town`, `town_safety`, `shouts`,
  `shout_follow`, `doors`, `dialogue_speed`, `perf_volley`, `perf_lava`, `link_boss`, `dark_link`, `dark_wyrmling`,
  `shield_enemies`, `title_roar`, `overworld_side`, `scanline_irq`, `ow_clouds`, `farcall`, `town_fire`, `town_combo`,
  `castle_zelda_burn`, `sign_burn`, `upstab`, `perf_upward`, `look_up`, `ending`, `scales`, `horsehead`, `helmethead`, `rebonack`, `carock`, `carock_reflect`,
  `gooma`, `opener_far`, `lava_link_kill`, `stomp`, `geldarm`, `encounter_hazard`, `heal_door`, `spell_door`, `stab_blocks`,
  `swamp_submerge`, `town_nontown_burn`, `inferno`, `overworld_fire`, `overworld_water`, `forest_burn_limit`, `meteor`, `perf_meteor`, `death_continue`, `levelup_pane`, `wizzrobe`, `rock_lizalfos`, `roar_gameplay`, `roar_controls`, `title_sample`, `game_over_audio`, `item_roar`, `castle_flame_shimmer`, `palace_flame_shimmer`, `title_lava_shimmer`, `title_star`, `title_split`, `palace_clouds`, `error_ash`, `sage_basement`, `saria_quicksand`, plus `state_pack` via `create_test_pack`.
  Run `rauru_rogue_door` for the far-west Rauru nametable regression.
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
- `emu.getScreenBuffer()` is a 1-based Lua array: pixel (x, y) is `px[y*256+x+1]`.

## Layout

| Path | What |
| --- | --- |
| `src/barba.asm` | includes everything; overworld avatar, hitbox, lava, roar, fixed-bank gateways |
| `src/breath.inc` | five-shot volley scheduler, load governor (`BarbaLoadOk`), mouth placement, Inferno and METEOR |
| `src/extra_fire.inc` | 3 extra projectile records multiplexed through native slot 0; enemy/shield collision wrappers |
| `src/shield_rebound.inc` | Ironknuckle shield impact and bank-4 rebound arc, shared by native and backed fireballs |
| `src/blocks.inc` | fireballs break glove-gated blocks |
| `src/geldarm.inc` | bank 1: desert worm sinks into the sand before its death explosion |
| `src/tall_player.inc`, `tall_layout.inc` | 24x48 boss-derived player renderer and head geometry |
| `src/death_display.inc` | fatal-hit silhouette with two full torso chunks |
| `src/dark_barba.inc` | bank 5 24x48 Dark Barba renderer and Triforce-hold pose |
| `src/sampled_roar.inc` | sampled roar audio coordinator, item/gem/Dark Barba roar hooks (default; `--native-audio` disables) |
| `src/palace_roar.inc` | bank 4: crystal floor pulse and Lava Link's pre-fight roar, control lock and music cue. Bank 6 `PALACE_SHAKE` and `LAIR_HUD_SHAKE` shift the room, sprites and HUD together. |
| `src/boss_meter.inc` | bank 4: boss HP to eight shadow-OAM pips after the player and enemy sprite passes. Gooma weapon priority runs here too. |
| `src/town*.inc`, `shouts.inc`, `ash_layout.inc` | fleeing/burning villagers, panic dialogue and shouts |
| `src/sign.inc` | bank 3 pad: burned-sign mark and rotating burned-sign text |
| `src/sage_basement.inc` | bank 3 pad (`BANK3_PAD`): Rauru sage basement post-Shield `"WAIT."` + 5-box sequence |
| `src/late_split.inc` | unused (superseded by MMC3 scanline IRQ HUD split) |
| `src/scanline_irq.inc` | MMC3 scanline IRQ engine: HUD split (line 31), encounter and palace entrance cloud parallax, VBlank sprig sway on R0 and water/swamp/lava on R1 (`UpdateSceneryChr6`), letterbox, `$6500` OAM shadow |
| `src/scales.inc` | SCALES (Shield): bank-6 `ScalesTick` (from `BarbaShouts6`); navy outline + sky-blue body, cast roar/decor flash, shielded-hit clang/flash |
| `tools/build.py` | assemble + guarded patch list (all hooks are listed here) |
| `tools/assets.py`, `assets/*.json` | sprite compilation; `tools/boss_art.py` extracts boss tiles |
| `tools/state_scenarios.lua` | builds the F-key checkpoints (scene list must match `create_test_pack.py` and `tests/state_pack.lua`) |
| `.tools/z2disassembly/src/prg*.asm` | annotated disassembly (grep by `$ADDR `); `ram-map.txt` |

## Memory map, disassembly index, and perf logs (frozen prefix rule)

Keep `AGENTS.md` **strictly static** across builds so the system-prompt prefix
stays cached (Gemini 4 Hydrogen implicit cache requires a ≥ 4,096-token exact
prefix match). Never write build hashes, free-space counts, or NMI cycle logs
into this file.

- **ROM bank free space & Barba RAM/WRAM/OAM/CHR allocations:** read
  `docs/MEMORY-MAP.md` on demand before allocating space or editing hooks.
- **Vanilla Zelda II RAM:** read `.tools/z2disassembly/ram-map.txt` (immutable
  USA PRG0 reference).
- **Disassembly navigation:** look up `$ADDR`, label, and `StartLine–EndLine` in
  `docs/z2-bank-index.md` first, then read only the needed line range from
  `.tools/z2disassembly/src/prg*.asm`. Keep `prg*.asm` strictly read-only.
- **Performance baselines:** read/append `docs/PERF-LOG.md` (NMI >~29.7k cycles
  lags the next frame; `BarbaLoadOk` uses `LOAD_LIMIT = 7` and caps queued
  shots at 2 when `>= 2` enemies are active, 1 on 6-Bot METEOR stress).
- **Multi-turn session order:** read static references (`ram-map.txt`,
  `docs/z2-bank-index.md`, `prg*.asm` slices) *before* editing `src/*.inc` or
  running `tools/build.py` so everything prior to your first edit remains cached.

## Status and docs (read only what you need)

| Topic | Doc |
| --- | --- |
| What's verified / open | `docs/STATUS.md` |
| ROM free space & RAM/WRAM/OAM/CHR map | `docs/MEMORY-MAP.md` |
| Performance baselines & NMI logs | `docs/PERF-LOG.md` |
| Disassembly bank index (`$ADDR` → lines) | `docs/z2-bank-index.md` |
| Breath, volley, tall sprite internals | `docs/BREATH-IMPLEMENTATION.md` |
| Towns, villagers, shouts | `docs/TOWNS.md` |
| Build/tooling, sampled audio, cold hooks | `docs/BUILD.md`, `docs/RESEARCH.md`, `docs/FIXED-BANK-AUDIT.md` |
| Subgame portals, standalone hacks, rewards | `docs/SUBGAME-INTAKE.md`, `docs/SUBGAME-REWARDS.md` |
| Checkpoints | `docs/TEST-PACK.md` (Core F1–F10; F9 is Lava Link, F10 is the Great Palace approach) |
| Archived plans, changelog, resolved audit | `docs/archive/`, `docs/AUDIT-2026-11-15.md` |

When you finish a task: update the one relevant doc plus `docs/STATUS.md` (and
`docs/MEMORY-MAP.md` / `docs/PERF-LOG.md` if allocations or perf changed—never
`AGENTS.md`). Then hand the producer a short playtest: what changed, which
F-key, what to look for.
