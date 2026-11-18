# Barba Edition status

**Experimental Waldo portal** on `codex/waldo-portal`. Single-ROM build
`play/barba-waldo.nes` (`python tools/pack_waldo.py`, NES 2.0 Mapper 176 / FK23C,
512 KB PRG / 512 KB CHR / 32 KB banked WRAM) packs Barba and Where's Waldo? into
one ROM with no Mesen ROM-switching or savestates (`tests/waldo_in_rom.lua` passes
Rauru doorstep → Waldo Train Station → exact Rauru return via `Start+Select` or
360-frame US Moon ending). The two-ROM Mesen prototype (`tools/waldo_portal.py`)
remains available. [Playtest instructions](TEST-PACK.md#experimental-waldo-portal)

Current playable alpha built from `roms/z2.nes` via `python tools/build.py` (SHA-256 `3a0a52742da576c6054acfb5dff2ae6f815ef91dac4f0bd58050f0b6b2dc280b`, Mapper 4 / MMC3, matching `play/barba.nes`).

For session-by-session history, see [docs/archive/CHANGELOG.md](archive/CHANGELOG.md). For the resolved November 15 audit, see [AUDIT-2026-11-15.md](AUDIT-2026-11-15.md).

## Verification snapshot

- **Build**: `python tools/build.py` (default sampled audio) and `--native-audio` both pass.
- **ROM-free unit tests**: 23/23 pass (`python -m unittest discover -s tests`).
- **Mesen launchers**: Play and checkpoint profiles open at 4× windowed scale with Space mapped to Select.
- **Town dialogue scroll**: Opening a sign in a scrolled town disabled the scanline-31 HUD split, shifting the room and clipping the dialogue box. The split now stays active during town dialogue. `tests/sign_burn.lua` checks the PPU scroll writes for both sign-reader types.
- **Darunia F6**: A stomp could kill the invisible bubble generator near the right exit of East Hyrule room `$06`. Its death animation jumped through an empty drawing pointer to `$0000`, where the CPU halted. Stomps now skip enemies with an empty drawing pointer. `tests/darunia_exit.lua` fails on `64cc80434b56` and passes on `c3bac750d883`, including re-entry, the left detour, a downstab, and a live return to East Hyrule. The world pack was regenerated for the fix.
- **Emulator scenarios & test packs**: the prior MMC3 verification covered all 67 Mesen scenarios and all 10 test-pack sets (69 checkpoints). `tools/busy_rooms.py --sets core,busy` recorded 0 lag, 0 late splits, and 0 HUD shifts. The Darunia fix was checked with the world pack, `darunia_exit`, `stomp`, `encounter_hazard`, and `perf_upward`.
- **Mapper & scanline IRQ (MMC3)**: iNES Mapper 4 (128 KB PRG / 256 KB CHR) with PRG mode 0 (`$C000-$FFFF` fixed), BG at `$0000` (R0/R1), and 8×16 sprites at `$1000` (R2–R5 via `$6500-$65FF` shadow OAM) so A12 clocks on every scanline. `src/scanline_irq.inc` provides the scanline-31 HUD split, releases OAM slot 0, clears the NMI-return I flag, and schedules the cinematic bars for the title roar, Dark Barba's entrance, and the ending.
- **Encounter scenery**. Room load checks the populated map pages for clear sky. The leading sky rows scroll at half camera speed from either entrance, including rooms with just one clear row. A clear band without clouds gets a small cloud per map page. Low clouds outside that band are removed. Low ceilings and dense canopies can leave no continuous sky band. West Hyrule sprig tips bend by up to two pixels via VBlank swaps of R0 pattern `$4E`. The bend tapers into fixed roots, and the ground scroll stays steady across the whole plant. East Hyrule uses different art at that tile index. Water, swamp, and lava surface metatiles use the same four VBlank CHR phases for patterns `$98/$99` in bridges, caves, and open encounters. The palace lava effect uses the same animation.
- **Grass encounter flicker**. A native blank sprite cell (`$F5`) could cause an extra MMC3 A12 clock between visible sprite fetches. This advanced the sky-to-ground split by up to four scanlines in the F10 checkpoint. The OAM copy now hides those cells. The `ow_clouds.lua` regression reproduced the early split on 20 of 20 frames before the fix and verified the programmed scanline on all 20 after it.
- `tests/ow_clouds.lua` also checks both bridge approaches, East Hyrule's room-$00 bridge, the medicine cave, the swamp, and all five sprig phases with fixed roots. The Movement pack puts the bridge, cave, and grass encounter on F5, F6, and F10.

## Implemented features

- **Player (24x48 Barba)**: Boss-derived 24x48 side-view poses (`src/tall_player.inc`, `src/tall_layout.inc`), full-body jumps, 24px crouch, ceiling folding, 64px downward torpedo fall-in-hole pose (`Game Mode $0F`, `BarbaFallDraw`), partly submerged lava/swamp pose (`GEOMETRY` bit 2), 8x16 flying Wyrmling, and 16x16 overworld avatar. Terrain/contact hitboxes keep native dimensions. CHR reserves `$4E/$50` (Ache), `$5E/$62` (ending ash), `$60` (XP digit `3`), and `$24` (Myu); tall head OAM is at `$C4` (preserving HUD magic bar at `$02F8`).
- **Attacks & techniques**:
  - **Five-shot diagonal volley** at all health levels (`src/breath.inc`, `src/extra_fire.inc`): fire-class (`$05CA = 0`), 8-update cadence, `LOAD_LIMIT = 7` governor, native fireball SFX (`$ED |= $40`), glove-gated brick breaking (`src/blocks.inc`, `$0707 >= 3`), and standing post-slash re-arm.
  - **Upward breath & rising head-butt**: airborne `Up+B` column and rising `Up` head-butt (both gated on Upward Thrust); head-butt breaks overhead blocks; `Up+B` kills Valley of Death wall Lizalfos (`tests/rock_lizalfos.lua`).
  - **Downstab**: airborne `Down` (gated on Downward Thrust) with 64px double-torso pose, 18x12 centered foot hitbox, and floor brick breaking.
  - **Jump stomp & touch pickup**: kills easy enemies (`$C2` 1..16, excluding shielded `$18..$1A/$1F/$23` and `$1D` Mago/Wizzrobe, disabled during boss scroll lock `$0728`) and picks up items on touch (`src/stomp.inc`).
  - **Geldarm & Hidden Red Jars**: Geldarm hurtbox widened to `12x64`, HP 8 -> 4, sinks 2 px/frame into sand on lethal hit (`src/geldarm.inc`). Hidden Red Jars (`$05`) reveal on breath hits (`HiddenJarHit` in banks 4/5).
- **Lava & sea crossing**: Palace (`$0707 >= 3`) and outside-palace encounter (`$0707 == 0`) water/lava surface support, crouch/jump, submerged pose, and `$FA` lava-launch boost (`LavaSurfaceBody` in `src/farcall.inc`). Town water keeps vanilla death; raft uses dragon sea-crossing sprite.
- **Towns, shouts & combo banner** ([TOWNS.md](TOWNS.md)):
  - Outdoor villagers (`$10..$12`, `$19..$20`) flee, enter doors, and burn into ash (`src/town.inc`). House-openers (`$13..$18`) stay invulnerable and talk on `B`/`Up` (`TownOpenerGate` requires <=96 px proximity before emerging). Non-town/indoor NPCs (`$0A..$20` excl. `$0C`, `$13..$18`, `$21..$22`) burn and repopulate on re-entry.
  - Fast panic dialogue on `Up` (`src/town_dialogue.inc`), 7-OAM sprite shouts (`src/shouts.inc`), scorchable props/buildings/streets (16-slot FIFO ring keyed on room + `$4B` page), rotating burned-sign text (`src/sign.inc`), UT-style combo banner (`src/combo.inc`), and scorchable sleeping Zelda (`"OOPS..."`).
- **Overworld dragon fire**: `B` breathes an 8x16 flame (`$60/$62` bank 30, centered `+4` px at `$74/$84/$94`), splits WRAM RLE map (`BarbaSplitBurnForest`) to burn single forest tiles (`$06` -> `$04`) with `$7FF0` overflow guard (`BurnMapEndGuard`/`BurnAbort`), reveals Hidden Kasuto, and rumbles towns/palaces. `A` keeps Hammer; `B` plays Flute on Spiders/open ground.
- **Title, audio, menus, bosses & ending**:
  - `BARBA I / THE ADVENTURE OF / BARBA` title with lava, roaring Barba, scrolling story, Barba 1-Up dolls, dragon spell names, `BREATH` level-up row, and fireball `$C9` icon.
  - **Sampled roar audio** (`roms/roar.wav`, `src/sampled_roar.inc`): title roar (with DAC ramp and pulse ducking), injury prefix (rate 9->5 descent), SCALES/INFERNO cast roars, item pickup & gem/Dark Barba victory roars, and four octave-up Game Over laughs (36-frame onset delay). `--native-audio` restores legacy audio.
  - **SCALES** (Shield): navy/sky-blue/white palette (`$01/$21/$30`), cast roar + 32-frame decor flash, shielded-hit clang + 8-frame flash (`src/scales.inc`).
  - **METEOR** (replaces Fire): airborne `Down+B` dive (`$057D = 6`) emitting two floor shockwaves gated by `BarbaLoadOk` (`src/breath.inc`).
  - **INFERNO** (replaces Thunder): noise roar, decor flash, 4-wave 4-way firestorm (`src/breath.inc`).
  - **Bosses**: All 6 palace bosses die to fireballs and drop keys (`CarockHit` 48 HP, 6/pip; `CarockReflectDamage` 24; `ThunderHit` preserves `$6E3F = $FF`). Palace 6 boss is **Lava Link**; Great Palace shadow is 24x48 **Dark Barba** (black palette preserved through hurt flashes, Triforce-hold pose). Casting `WYRMLNG` (`$13 != 0`) turns Dark Barba into a flying **Dark Wyrmling** (`$68`/`$6A` black silhouette, horizontal fireballs) while letting Player Wyrmling breathe horizontal volleys (`dark_wyrmling.lua`), reverting cleanly to 24x48 Barba on Phase 4 victory.
  - **Ending**: 24x48 Barba beside woken Zelda, custom dialogue, 16px animated fireball, ash, 20-entry credits, New Game+ (`$07A0 = 1`).
- **Test packs** ([TEST-PACK.md](TEST-PACK.md)): 9 F-key checkpoint sets (`create_test_pack.py`), including Bosses (F1-F8) and Busy Areas (F1-F10).

## Performance & bank headroom

- **NMI cycle budgets** (MMC3 ROM `c8fcedb109c5`, 0 lag / 0 late splits / 0 HUD shifts across all tests):
  - `perf_volley.lua` (Palace 1): idle `12,063 avg / 12,126 peak`; volley `15,169 avg / 21,048 peak`, `0/900` lag.
  - `perf_meteor.lua` (Palace 1): `13,262 avg / 15,117 peak`, `0/900` lag (MMC1 baseline; re-verified pass on MMC3).
  - `perf_upward.lua` (6 active Bots): idle `22,866 avg / 23,113 peak`; upward `24,149 avg / 24,834 peak`, `0/900` lag (MMC1 baseline; re-verified pass on MMC3).
  - `perf_lava.lua`: floor `15,800 avg / 16,573 peak`; lava `15,311 avg / 17,309 peak`, `0` lag (MMC1 baseline; re-verified pass on MMC3).
  - `busy_rooms.py` (`--sets core,busy`, 480 frames/state): `old-kasuto` `28,492` work / `28,515` NMI max, `p2-crowded-floor` `28,213 / 28,236`, `p5-gooma-approach` `27,349 / 27,372`, `p3-ironknuckle-blocks` `24,391 / 24,414`.
- **Bank headroom** (default sampled build): `BANK0` 435 B free, `BANK6` 1,180 B free, `BANK3_SIGN` 255 B free, `BANK1` 240 B free, `BANK5` 9 B free (`--native-audio`: 41 B), `TOWN` 28 B free, `BANK4` `$A7B0-$A7BE` and `$A80F-$A8FF` free.

## Remaining / open items

- Full end-to-end human playthrough across all palaces, spell unlocks, item gates, and ending.
- Producer playtest of **Burned signs**, **Phantom closed door gate** (`TownOpenerGate`), and **METEOR** magic cost/feel (currently uses vanilla Fire cost `$8D9B`; unlimited slams while active).
- Cross-check on a second accurate NES emulator / hardware-accurate MMC1 behavior.
- Audio listening pass on Inferno roar, SCALES cast/hit audio, and sampled roar transitions.
- **Fireball range** (decision pending): raising `VOLLEY_LIFE` in `src/breath.inc` from 33 to 63 updates (64 -> 124 px) broke fireball-only Rebonack because long-lived misses saturate the 2-live-shot cap; requires a cap/fire-rate rethink if desired.
- **Trailing torso** (shelved): lagged 16x16 segment behind lower body (`docs/archive/trailing-torso-prototype.patch`) reverted due to +190 cycles/frame and OAM scanline pressure.
- **Known cosmetic P3 limits**: leftover fire for <1s after respawn, and scorch ring keyed only on room number (see [AUDIT-2026-11-15.md](AUDIT-2026-11-15.md#final-end-to-end-review-2026-11-16-rom-92bfdbac-unchanged)).
