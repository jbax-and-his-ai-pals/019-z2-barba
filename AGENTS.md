# Barba Edition: agent quick start

Zelda II ROM hack starring the Palace 6 dragon **Barba**. The clean source
is USA PRG0 (MMC1). The combined development ROM is NES 2.0 Mapper 176
and runs Zelda II in MMC3-compatible mode. Read this file first, then the
relevant doc below. Search the disassembly by address.

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

## Free space and RAM in use (check before allocating)

### ROM banks & free space

Counts for the trail, title and fall changes describe sampled build `dc9c4a25a40a`.
Other counts refer to `27518df041f4` unless specified.
Use the build report and a successful link of your variant before allocating space.

| Bank | Region | Contents / Notes | Free |
| --- | --- | --- | --- |
| 0 | `$A89E-$A97D` (`BANK0_OW`) | `BarbaSplitBurnForest` + `BurnAbort` | 1 |
| 0 | `$AA40-$BF6F` (`BANK0`) | Core Barba code, including grounded crouch poses, trail sampler and floor anchors for the crouch and raised-head roar, elbow wiggle, player and Dark Barba trail dispatch, Lava Link entrance movement gate and shield impact dispatch. `$BF70-$BF96` item pickup helpers. Preserve mapper `$BF9D-$BFDF` (`$BFB1` live OW call). | 4 (`88ac352c576e`) |
| 0 | `$BFE0-$BFF9` (`BANK0_TAIL`) | `BurnMapEndGuard` (before vectors) | 1 |
| 0 | `$81C1-$81E4`, `$97F1-$9814`, `$9847-$9877` | Reclaimed dead vanilla code (METEOR) | 0 / 1 / 0 |
| 1 | `$9EB9-$9FFF` (`BANK1`) | `geldarm.inc`, downstab torso, `DrawEncounterTrailSprites1` trail promotion ahead of enemies | 27 (`1ff0bc458103`) |
| 2 | `$9F85-$9FA0` | Valley of Death Lizalfos breath check (hook `$977C`) | 0 |
| 3 | `$9134-$93FF` (`BANK3_PAD`) | `sage_basement.inc` (separate vanilla pad at `$8BB1-$90EF`) | 370 |
| 3 | `$9D0A-$9FFF` (`BANK3_SIGN`) | `sign.inc`, `TownDoorRender`, `TownOpenerGate`, `LateSplit`, `BarbaDeathDisplay`, Waldo dialogue | 112 (`53bda4ca2e0d`) |
| 3 | `$B803-$BF6F` (`TOWN`) | Town villagers, dialogue, combo | 10 |
| 4 | `$8EC3-$93FF` (`PALACE_ROAR`) | Dark Barba trail, crystal ceremony, Lava Link entrance, Ironknuckle shield rebounds, boss meters and Gooma weapon priority | 115 (`12ed5bd69207`) |
| 4 | `$A765-$A8FF` (raw pad) | Lava Link `$A765-$A7A8`, `HiddenJarHit` `$A7BF-$A7CF`, `CarockHit` `$A7D0-$A7E4` (boss death gated on `$22`), `CarockReflectDamage` `$A804-$A80E` (24 dmg; HP 48 at `$A943`, six HP per pip in `boss_meter.inc`) | `$A7B0-$A7BE`, `$A7E5-$A803`, `$A80F-$A8FF` |
| 5 | `$BDE0-$BF5F` (`BANK5`) | `dark_barba.inc`, `HiddenJarHit`, `DarkBarbaVictory` (hook `$9BAC`) | 0 (32 in current native-audio build) |
| 5 | `$8CEB-$8D4D` | Ending fireball cutscene patch | 2 |
| 6 | `$AC09-$BF6F` (`BANK6`) | `shouts.inc`, `combo.inc`, `scales.inc`, `scanline_irq.inc`, `EncounterTorsoHop6`, title tail, `DarkLinkFireCheck`, town/castle scorch, Waldo RAM snapshot and return, `RoarRestoreBank` | 2 |
| 6 | `$9DA8-$9FFF` (`BANK6_HAZE`) | Lava haze, cloud entrance detection and rendering, scenery CHR updates, `TitleLavaChr6`, shout row layout tables | 3 |
| 6 | `$878C-$87CB` (`BANK6_OAM`) | Scene OAM priority, encounter trail and boss meter dispatch | 33 (`4756353e62d0`) |
| 6 | `$87CC-$88FF` (`PALACE_SHAKE`) | Lava Link entrance shake, `LagNmiInBank6` and the ending and pit-fall sprite extensions | 1 |
| 6 | `$BFE0-$BFF9` (`LAIR_HUD_SHAKE`) | Lava Link entrance HUD scroll override, after the mapper stub | 5 (`dddb732f2677`) |
| 6 | `$93E5-$9407` (`FALL_ROAR`) | Palace drop roar dispatch in sampled builds, reusing the native sweep | 0 |
| 5 | `$A5E8-$A5F7` (vanilla pad) | Title lava shimmer stub (hook `$A682`, then native `$C032`) | `$A5F8-$A5FF` |
| 5 | `$A54F-$A59D` (vanilla pad) | Title two-sprite jaw animation and frame tables | `$A59B-$A59D` |
| 6 | `$8900-$8FFF` (vanilla pad) | `$8900-$89FF` `BANK6_CLOUD` (includes `ShoutOamPriority6`, 2 B free), `$8A00-$8BFF` pickup/celebration (`$9B73/$9B24`, 0 B free in `d4e161fea84f`), `$8C00-$8DAE` coordinator/ducking/laugh bank selection, `$8DB0-$8DFF` `BANK6_PAD` (`PageLo6`/`PageHi6` + `TownQuicksandChr6`, 1 B free), `$8E00-$8EFF` title duck table, `$8F00-$8F27` title duck helpers (`$810F/$8116`), `$8F28-$8F3E` one-shot laugh DMC enable, `$8F40-$8F65` title DAC ramp, `$8F70-$8FCB` VBlank overrun and laugh delay, `$8FD0-$8FF5` title DMC enable (`$8005`) | — |
| 7 | `$D39A-$D3C9` (`LAVA`), `$FEAA-$FECF` (`GATEWAY`), `$FF4C-$FF6E` (`TERRAIN`) | Fixed bank allocations (`FarCall0`: 5 B/call, 6 B w/ RTS, see `docs/BUILD.md`). `LAVA` also contains the shield rebound bank switch. Never allocate live JMP operands `$FF4B` or `$E02C`. | 2 / 0 / 1 (`88ac352c576e`) |
| 7 | `$F400-$FD70` | Sampled roar (`$F400-$FC80`, 2,177 B) in combined PRG page 31. Page 15 carries five octave-up Game Over laughs starting at `$F400/$F700/$F840/$F9C0/$FA80`. Both pages contain the early cached-pad helper `$F3C1-$F3DF` and native hurt `$F300-$F3C0`. | Sample storage |

- **Fixed-bank guarded vanilla rewrites** (no new padding claimed): NMI prologue `$C091-$C0A7`, VBlank setup and IRQ continuation `$C108-$C131` (IRQ entry `$C110`), NMI tail `$C182-$C1B5` (mask helper `$C18E`, tail starts `$C19D`, RTI `$C1B5`), fast offscreen mask `$F27D-$F2D1` (`$F2D2` spare), block anim `$E0FC-$E109`/`$E23A-$E247`/`$E29C-$E29D`, enemy projectile update `$E3B9-$E3C8` (empty-slot helper `$E3C1`), empty enemy slot skip & direct dispatch `$D5DA-$D5F8` (`$D5F6-$D5F8` 3 B spare).
- The native OAM Y clear uses `$D24C-$D25D` with a shared entry at `$D24C`. `$D250` is inside the loop. The two-column sprite clip uses `$F1D7-$F1F3`. Both reuse guarded vanilla ranges.
- The shield overlap hook at `$E646` replaces the native fireball disintegration call. Rebounds reuse the projectile lifetime and fractional X velocity, with no new RAM.
- Saria room `$06` quicksand uses PPU attributes `$27F8-$27FB` (`$05` throughout) for its eight metatiles. The full-width update fits in the existing `BANK6_PAD` allocation.
- The Saria sandbar uses a size-preserving West Hyrule map edit at bank 1 `$9297-$92E0`. The bridge guard's warning fits in the existing bank 3 message at `$A7FE`. Playtest with `python tools/create_test_pack.py --set saria` or **Test Barba - Saria Quicksand.cmd** (F1 overworld, F2 guard).

### RAM, WRAM, OAM & CHR

- The Lava Link entrance locks the camera with `$0728 = 1`. At world X `$0188`, Lava Link's `$AF,x = $7F` holds Barba over the central platform while native jump state `$0479` runs. On landing or while transformed into WYRMLNG, `$0728 = 2` suspends player physics through the fixed-bank hook at `$D4F3` in Palace 6 room `$3A`. The landing beat sets `$AF,x = $65` and counts down to `$60`, starting the roar on the sixth update. After the roar, `$AF,x` counts down from `$5E` to `$40` for 30 frames. Then `$0728 = 1` resumes physics and keeps the camera locked until Barba collects the key.

- **RAM**: `$05EA`, `$05EB` (lava contact), `$05EC`/`$05ED` (SCALES cast latch / last injured timer), `$05EE` (sampled roar bits: 7 active, 6 full pending, 5 injury pitch tail, 4 victory draining/done, 3 raised-head pose, 2 hurt, 1 item roar, 0 shaft playback with bit 7 set or Game Over laugh delay), `$05EF` (legacy start timer), `$05F0-$05FF` (roar, breath, tall renderer, extra guard; `$05F8`/`$05FA` ending fireball state/X). Cleared by native reset.
- **WRAM** (don't touch collision/room/save regions elsewhere in `$6000-$7FFF`):
  - `$6400-$642F`: extra projectile records
  - `$6440-$645F`: scratch (`$6457` lazy-save, `$6458-$645F` geometry terrain cache, `$645C` `EXTRA_LIVE`)
  - `$6460-$6469`: shouts (`$6465` actor, `$6467` word, `$6468` timer, `$6469` cycle)
  - `$646A`, `$6490-$64D0`: town scorch ring (16-slot FIFO + head/page); `$64D1` `SIGN_PENDING`; `$04A0,x` burned-sign line (`$21`/`$22`)
  - `$646B` volley aim latch (`0` forward / `$40` up); `$646C-$646F` + `$6488` town combo banner
  - `$6477`: title lava shimmer dirty flag (restore R0 bank 4 after Start)
  - `$6470-$6476`: Inferno timer/wave aim (`$6470`/`$6473`), overworld flame timer/dir (`$6471`/`$6472`); `$6474` METEOR dive state; `$6475/$6476` Rauru sage basement `SAGE_STATE`/`SAGE_BOX`
  - `$6478-$6480`: Waldo portal state (`PORTAL_DEBOUNCE..MELT_DIR`, `WALDO_RETURN_MSG` `$647E`, `WALDO_ENTER_MSG` `$647F`)
  - `$6481-$6487`: player trail Y history (six samples and next write index)
  - `$64D2/$64D3`: late raw pads cache (sampled audio); `$64D4`: item pickup hold (`1` fanfare, `$80` roar/tail); `$64D5`: MMC3 `$8000` bank-select shadow (saved/restored by `LagNmiBank6` / `LagNmiReturn`)
  - `$64F9`: Game Over DMC bank state (`0` normal, `2` pending enable, `1` fetching) in the combined sampled build
  - `$64FA`: signed horizontal scroll offset for Lava Link's Palace 6 entrance roar. The last two offsets repeat through the roar's audio tail. Bank 6 applies the offset to the HUD and IRQ scroll and subtracts it from the OAM shadow X coordinates while `$0728 = 2`.
  - `$64D6-$64F8`, `$64FB-$64FD`: scanline IRQ and scenery state (`IRQ_STAGE`, `IRQ_COUNT`, `IRQ_LINES`, `IRQ_X`, `IRQ_CTRL`, `IRQ_MASK`, `ROOM_HAS_LAVA`, cache/temps, `OW_PARALLAX_LINE` `$64EE`, active liquid `R1` `$64EF`, `OW_HAS_GRASS` `$64F0`, `OW_HAS_WATER` `$64F1`, `CLOUD_DX_HI`/`COL`/`IDX`/`Y`/`WIDTH`/`ATTR`/`TILE` `$64F2-$64F8`, `CLOUD_DRIFT_SUB`/`X`/`NT` `$64FB-$64FD`)
  - `$6500-$65FF`: OAM DMA shadow page (8x16 sprite tiles rebased to the swapped pattern tables, with native blank `$F5` cells hidden to avoid extra MMC3 A12 clocks)
- **OAM**: tall head `$04/$4C/$C4`; extra torso `$20/$24`; item celebration `$34/$40` (item) + `$20/$24` (upright torso during the roar); extra fireballs `$3C/$44/$48`; enemy projectiles `$28/$2C/$30`; fall-in-hole (`Game Mode $0F`, `BarbaFallDraw`) `$08..$2C` Barba + `$3C..$60` shadow in native OAM, extended to `$08..$38` and `$3C..$6C` respectively in DMA OAM; ending fireball `$40-$47`; shout word `$00,$28..$34,$40,$DC` (7 glyphs); overworld flame `$FC` (`$74/$84/$94`).
  The sampled raised-head roar puts the bend in the lower center and rear body slots at foot height and refills the trail Y history there.
  Gooma's ball and links use `$A0/$A4/$A8/$AC` in Palace 5 room `$29` and swap into `$28/$2C/$30/$34` in the DMA shadow during the fight.
  The boss meter uses eight early free DMA-shadow entries after the player and Dark Barba trail edits. In Gooma's fight it starts at `$4C`, behind the weapon and fireballs. The former native meter entries `$02C0-$02DF` stay available to the sprite renderers.
  During a villager shout, the DMA shadow puts Barba at `$6500..$6528` and the glyphs at `$652C..$6544`. Shout rows are 16 px apart and use at most five sprites each.
  During a town combo, the counter uses offsets `$00/$28/$2C/$30` ahead of fireballs, most actors, and clouds.
  The side-view trail takes four DMA shadow entries `$50-$5C` after Barba, fireballs, projectiles and encounter clouds. A visible occupant moves to the last free entry at `$60` or later. Player CHR pairs `$14/$3E` hold the turned torso, `$44/$30` the tip and `$34/$36` the elbow. Pair `$0A` holds the vertical drop-shaft tip. The third torso and tip use DMA entries `$30/$34/$38` for Barba and `$64/$68/$6C` for his shadow. The elbow uses the center and rear slots and lifts 1px while the delayed torso rides higher. Scratch `$08-$0B` holds four X coordinates and `$0C-$0F` holds four Y coordinates for the bank-1 pass.
- **CHR**: extended 1 KB banks: 128-133 + 254-255 Saria room `$07` quicksand R1, 134-145 side-view liquid ripples (`$02`/`$04`), 146-153 Saria room `$06` quicksand R1, 158-205 palace liquid ripples, 206-213 West grass, 214-227 flames, 228 palace clouds, 229 town clouds, 230-237 overworld water, 238-245 title lava (R0), 246-253 East grass (R0); 0 free. Game Over black Link in bank 17 `$00-$31` (map `$801F-$80C8`); even sprite banks 0-24 reserve `$24` for Myu and use `$5C`; overworld flame `$60/$62` (bank 30); ending fireball `$E0/$E2`, `$E4/$E6` (bank 14); ash `$7E/$80` (bank 6 only); shout glyphs bank 7 `$32/$7E/$80,$84-$BE` + `H` (`$7C`) and combo glyphs bank 6 `$6C-$AE`; town scorch bank 7 `$AC/$A4`, `$C1/$C0`, `$A7/$C2`; dialogue `?` `$34`, apostrophe `$35`. **Bank 7 `$00-$27` are villager 8x16 sprites â€” never allocate there** (`TOWN_SPRITE_PAIRS` in `tools/assets.py` guards them; bank 7 has no free pair left).

Player sprite pairs `$32/$54` hold the eight visible rows of the curved body
below the full 16px head when Barba crouches on an open floor or under a low ceiling.

Title CHR uses sprite bank 0 pairs `$EA/$EC/$F8/$FA/$FC/$FE` for Barba's
two-column head. BG bank 1 tile `$67` is the opaque black sprite-zero target.
R0 banks 238/240/242/244 animate title lava `$68-$6A` and the forest-edge
lava masks `$6D-$70`.

## Performance baselines

OAM build `ed8056d42c47` saves 352 cycles on each measured native OAM clear.
Against `e69808fd18a1` on the same checkpoints, clear plus column clipping
lowered NMI peaks from 29,367 to 28,815 in West grass and 29,163 to 28,571
in East grass, with zero lag and HUD shifts. On Busy Areas checkpoints with
the trial trail, lag fell 38→30 in Old Kasuto, 7→4 on the Palace 2 crowded
floor and 12→3 on the Gooma approach. Old Kasuto still had one HUD shift.

Sampled build `b89eba77b414` recorded zero lag and no frames above 27,000
cycles in the 900-frame firing phases. Palace 1 volleys averaged 16,405 NMI
cycles and peaked at 21,618. Upward volleys with six active Bots averaged
25,436 and peaked at 26,445. The Core and Busy Areas probe recorded zero
late splits or HUD shifts, with lag in Old Kasuto (13 frames), the Palace 2
crowded floor (4), and the Gooma approach (1).

Game logic runs in NMI; >~29.7k cycles lags the next frame (`LateSplit` repairs overruns ending inside vblank). `BarbaLoadOk` uses `LOAD_LIMIT = 7` and caps queued shots at 2 live shots when `>= 2` enemies are active (1 on 6-Bot METEOR stress). All benchmarks below run at **0 lag, 0 late splits, 0 HUD shifts**:
- `perf_volley.lua` (Palace 1): idle `12,063 avg / 12,126 peak`; volley `15,169 avg / 21,048 peak` (`0/900` lag, `nearBudget(>27000)=0`). All-palace cloud build `2d40b69ecc96`, re-verified on directional cloud build `fd6de1641557`: idle `13,031 avg / 13,592 peak`; volley `16,357 avg / 21,570 peak`, with zero lag and zero frames above 27,000 cycles.
  East Hyrule grass fix build `0833e6644899`: idle `13,061 avg / 13,622 peak`; volley `16,386 avg / 21,600 peak`, with zero lag and zero frames above 27,000 cycles.
  Five-laugh combined build `022f24ad4c30`: idle `13,096 avg / 13,657 peak`; volley `16,422 avg / 21,635 peak`, with zero lag and no frames above 27,000 cycles.
  One-shot laugh build `46657414e2ee`: idle `13,080 avg / 13,641 peak`; volley `16,406 avg / 21,620 peak`, with zero lag and no frames above 27,000 cycles.
  Palace roar build `60ca27e2ea8f`: idle `13,078 avg / 13,639 peak`; volley `16,404 avg / 21,617 peak`, with zero lag and no frames above 27,000 cycles.
  Full-head corridor crouch build `a5a1a3604885`: idle `12,809 avg / 13,370 peak`; volley `16,063 avg / 21,282 peak`, with zero lag and no frames above 27,000 cycles.
- `perf_meteor.lua` (Palace 1): `13,262 avg / 15,117 peak` (`0/900` lag, 10 slams / 2 waves; MMC1 baseline, re-verified pass on MMC3).
- `perf_upward.lua` (6 active Bots): idle `22,866 avg / 23,113 peak`; upward `24,149 avg / 24,834 peak` (MMC1 baseline). Build `3a0a52742da5`: idle `23,811 avg / 24,560 peak`; upward `25,142 avg / 26,486 peak`, with `0/900` lag and no frames above 27,000 cycles.
  Lava Link entrance build `e1951d664b8a` averaged 24,170 idle and 25,498 firing, peaking at 24,530 and 26,505 cycles respectively. The firing phase recorded `0/900` lag.
- `perf_lava.lua`: floor `15,800 avg / 16,573 peak`; lava `15,311 avg / 17,309 peak` (`0` lag; MMC1 baseline, re-verified pass on MMC3).
- `busy_rooms.py` (`--sets core,busy`, 480 frames/state): `old-kasuto` `28,492` work / `28,515` NMI max, `p2-crowded-floor` `28,213 / 28,236`, `p5-gooma-approach` `27,349 / 27,372`, `p3-ironknuckle-blocks` `24,391 / 24,414`.
- Encounter trail build `8d22f92d7d1a`, compared with `46657414e2ee` from the same checkpoints. West grass peaks at `28,908` NMI cycles (+430) and East grass at `28,357` (+432), both with 0 lag frames and 0 HUD shifts over 460 sampled gameplay frames each. The medicine bridge and Myu cave also record 0 lag and 0 HUD shifts.
- Two-piece trail build `31abc7edf2ff` peaks at `29,140` NMI cycles in West grass (+232 from the single-piece trail) and `28,608` in East grass (+251). Both have 0 lag and 0 HUD shifts over 460 gameplay frames each. The medicine bridge, Myu cave and West water also record 0 lag and 0 HUD shifts.
- Wiggling trail build `60ca27e2ea8f` peaks at `29,154` and `28,623` in West and East grass, about 15 cycles over `5ff6e886a10f`. Both have 0 lag and 0 HUD shifts. Frames with any clipped scanline in the near torso column fell `68→32` in West grass and `152→125` in East grass (460 frames per fixture). The trail displaced no ordinary sprite in either trace.
- Trail-ahead-of-enemies build `1633f7138573` peaks at `29,338` and `29,136` in West and East grass (+19 and +347 from `27518df041f4`). Both have 0 lag and 0 HUD shifts over 460 frames each.
- Extra horizontal chunk build `032e6b5abb38` peaks at `29,557` in West grass (+219 from `1633f7138573`) and `29,344` in East grass (+208). Both have 0 lag and 0 HUD shifts over 1,275 and 1,539 gameplay frames. The 460-frame opt-in busy-room trials add 10 lag frames in Old Kasuto and two each on the Palace 2 crowded floor and Gooma approach.
- Enemy-priority build `7483ee3b9d96` peaks at `29,669` in West grass and `29,232` in East grass over the same 1,275 and 1,539 frames. Both have 0 lag, VBlank recoveries or HUD shifts. In West grass, grounded Bot and Bit columns with all scanlines within the eight-sprite limit rise from 454 to 1,066 of 1,071.
- Rotating trail priority build `95f9db389858` peaks at `29,713` in West grass and `29,271` in East grass over the same runs with 0 lag, VBlank recoveries or HUD shifts. In stationary F10 the longest opaque-row blackout drops from 224 frames to three for the outer torso and from 416 to three for the tip.
- The second torso was reverted after the producer's F10 playtest. Restored build `278787fe6a02` peaks at `29,368` and `29,167` in West and East grass over the same runs with 0 lag, VBlank recoveries or HUD shifts. See [Second horizontal torso trial](docs/BREATH-IMPLEMENTATION.md#second-horizontal-torso-trial) for the variants and revisit conditions.
- The crouched trail floor anchor build `5fc45aab1fe4` peaks at `28,846` in West grass and `28,602` in East grass with 0 lag, late splits or HUD shifts over 480 gameplay frames per fixture.
- Curved join build `27518df041f4` peaks at `29,319` and `28,789` in West and East grass (+165 and +166 from `af2076011c88`). Both have 0 lag and 0 HUD shifts over 460 frames each. Near trail clipping drops `32→26` and `125→97` respectively. The trace found zero ordinary sprites displaced by the trail.
- Default body build `dc9c4a25a40a` runs the Palace 1 volley and six-Bot upward volley with zero lag over 900 firing frames each. Peaks are 22,139 and 27,067 NMI cycles respectively. The 460-frame Busy Areas runs match the prior trail trial's 30/4/3 lag frames in Old Kasuto, Palace 2 crowded floor and Gooma approach, with one HUD shift in Old Kasuto.
- Foot-level roar trail build `d4e161fea84f` runs the same volleys with zero lag over 900 firing frames each. Peaks are 22,143 and 27,070 NMI cycles respectively.
- Open-floor crouch bend build `738c88a87d95` runs both volleys with zero lag over 900 firing frames each. Peaks are 22,145 and 27,073 NMI cycles respectively.
- Palace drop roar build `a127c2f02bdc` runs the 900-frame Palace 1 volley with zero lag and a peak of 22,165 NMI cycles.
- Full-screen Lava Link entrance shake builds `dddb732f2677` and `6c26d7b68dc0` run the 900-frame Palace 1 volley with zero lag and a peak of 22,219 NMI cycles.
- Post-roar pause build `08fabb83c7f1` matches the 900-frame Palace 1 volley result of zero lag and a peak of 22,219 NMI cycles.
- Boss meter build `4756353e62d0` records zero lag in both 900-frame firing phases. Palace 1 peaks at 22,240 NMI cycles. The six-Bot upward volley peaks at 27,163 cycles, with 13 frames above 27,000.
- Ironknuckle rebound build `88ac352c576e` records zero lag over 900 firing frames each in Palace 1 and the six-Bot upward volley. NMI peaks are 22,240 and 27,163 cycles.
- Lava Link landing beat build `12ed5bd69207` records zero lag over the 900-frame Palace 1 volley, with a 22,267-cycle NMI peak.

## Status and docs (read only what you need)

| Topic | Doc |
| --- | --- |
| What's verified / open | `docs/STATUS.md` |
| Breath, volley, tall sprite internals | `docs/BREATH-IMPLEMENTATION.md` |
| Towns, villagers, shouts | `docs/TOWNS.md` |
| Build/tooling, sampled audio, cold hooks | `docs/BUILD.md`, `docs/RESEARCH.md`, `docs/FIXED-BANK-AUDIT.md` |
| Checkpoints | `docs/TEST-PACK.md` (Core F1–F10; F9 is Lava Link, F10 is the Great Palace approach) |
| Archived plans, changelog, resolved audit | `docs/archive/`, `docs/AUDIT-2026-11-15.md` |

When you finish a task: update the one relevant doc plus `docs/STATUS.md`, and keep this file's
memory map and perf facts current. Then hand the producer a short playtest: what changed, which F-key, what to look for.
