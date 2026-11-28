# Barba Edition v2.0 Roadmap

Single living source of truth for bringing **Barba Edition** (Zelda II) and all **10 crossover subgames** to the **2.0** finish line.

---

## 1. Standing Orchestration & Chat Hygiene Rules

### Standing Delegation Rules (Producer-Approved)
- **Automatic tier downshift:** Use lighter models (`flash` / `flash_lite`) for routine codebase research, room/bank audits, test audits, and mechanical edits.
- **Parallelize independent work:** Run read-only audits in parallel, and fan out independent subgame work (e.g., `pack_zelda.py`, `pack_mm2.py`, `pack_mtpo.py`, `pack_wheel.py`) using isolated `share` workspaces when editing concurrently.
- **Keep shared-state work sequential:**
  - Never run multiple headless Mesen scenarios (`tools/emulator_test.py`) concurrently in the same checkout (`build/mesen` and output files are shared).
  - Serialize edits to core Zelda II assembly files (`src/*.inc`, `src/barba.cfg`, `tools/build.py`) so ROM bank allocations and WRAM maps do not collide.

### Chat & Documentation Hygiene
- **Scope per chat:** Target **1 conversation per major phase** (or 1 per heavy subgame in Phase 5, or `/teamwork` for multi-subgame sprints).
- **Never edit `AGENTS.md`:** Keep `AGENTS.md` strictly static for prompt-cache stability.
- **Phase-end handoff:** Before closing a phase, update this file (`docs/ROADMAP-2.0.md`) and [`docs/STATUS.md`](STATUS.md) (plus [`docs/MEMORY-MAP.md`](MEMORY-MAP.md) / [`docs/PERF-LOG.md`](PERF-LOG.md) if allocations or perf baselines changed), and provide a short starter prompt for the next conversation.

---

## 2. Locked 2.0 Architectural & Design Decisions

1. **Hybrid World Interleaving & Discovery:**
   - **Starter in Rauru:** *Where's Barba?* (`waldo` -> `DECOY`) is free and open immediately in **Barba's Arcade** (Rauru room `$1C`).
   - **Even Hyrule Distribution (Other 9 Subgames):** Distributed roughly evenly across Hyrule by progression tier (utility/fun spells early; powerhouses like `HEAVY`, `STAR`, `CLOCK` late), following the door rule: **occupy an existing house that contains nothing or only an unimportant NPC** (never displacing healers, sages, sword knights, or quest-item NPCs).
   - **Strange / Hidden Spots:** With 7 remaining Hyrule towns (Ruto, Saria, Mido, Nabooru, Darunia, New Kasuto, Old Kasuto), the remaining 2 slots may be hidden in strange/memorable spots across Hyrule. Audit all candidates and obtain producer sign-off on the exact 10-location map in Phase 3 before wiring.
   - **Arcade Hub Replay:** Discovering a subgame out in Hyrule flips a persistent discovery flag and powers on its booth in **Barba's Arcade (Rauru)** for anytime replay (undiscovered booths stay dark / `"OUT OF ORDER"`).

2. **Curated Milestones + Full Vanilla-Scope Playability:**
   - Every subgame defines **1–2 curated portal milestones** (brisk, rewarding unlock goals that grant its Zelda II spell + cosmetic gear and trigger the return celebration).
   - Every subgame remains **100% playable to full completion** (vanilla scope + all Barba hacks and alternate endings, such as Friday the 13th's Forest Coven endings), both as a standalone ROM and when replayed deeply from the Arcade.

3. **Two-Tier Mapper Architecture (Flagship FK23C + MMC3 Compatibility Layer):**
   - **Flagship Tier (`NES 2.0 Mapper 176` / FK23C):** Combined `barba.nes` (and flagship standalone FK23C builds where features benefit, such as `feud`'s dynamic CHR-RAM cast mixer) stays maximum quality with zero compromises.
   - **Compatibility Tier (`Mapper 4` / MMC3 — ALL 10 subgames + standalone Zelda II):** Maintained as a universal compatibility layer for older flashcarts, broad emulators, and standalone RetroAchievements. Functionally identical to flagship wherever hardware permits, with minimal documented tradeoffs only where MMC3 strictly requires them.

4. **Zelda II Core Quality Bar:**
   - **Zero lag, zero HUD shifts** across all rooms, crowded scenes, boss fights, and active Arcade spells.
   - **Vanilla Zelda II difficulty parity** overall: subgames may be snappier/easier than their vanilla NES counterparts, while the Zelda II campaign retains vanilla bite and Arcade spells feel tactical and rewarding without trivializing the game.
   - **Polished transitions & return UX:** Smooth wipe-in / wipe-out animations with clean APU mute across all 10 subgames, plus context-aware Zelda II return dialogue/celebration.

5. **RetroAchievements (Strictly Last — Post-ROM Freeze):**
   - **Standalone MMC3 sets:** Each subgame released standalone receives its own lower-level achievement set.
   - **Combined Zelda II Barba 2.0 set:** Covers the full Zelda II campaign **plus** all 10 Arcade subgames and their multiple endings (milestones, full clears, alternate endings, cosmetic gear, NG+ feats).
   - **Early Prep (Phase 1):** Reserve a frozen WRAM Bank 0 **RA Telemetry Block** + `ACTIVE_GAME_ID` (`0` = Z2, `1..10` = subgames) now so no code changes are required after freezing 2.0 ROM hashes in Phase 7.

---

## 3. Pre-Phase-1 Audit Findings (Known Bugs & Headroom)

1. **Critical — 9 of 10 subgame win hooks fail to unlock Arcade spells/gear in real play:**
   - `CheckSpellOwned2` ([`src/arcade_spells.inc`](../src/arcade_spells.inc#L428-L463)) checks `cmp #$01` on `$63B1..$63BA` (`$648B == $57` for Waldo).
   - `waldo` writes `$57` to `$648B` (works).
   - `f13` ([`tools/pack_f13.py`](../tools/pack_f13.py#L514-L515)) jumps to `F13_RETURN` on Day 3 clear (`$8E4A`) and **never writes `$63B1`**.
   - The remaining 8 subgames write ASCII magic bytes (`feud=$46`, `dk=$44`, `smb=$4D`, `duck=$48`, `mm2=$32`, `wheel=$57`, `zelda=$5A`, `mtpo=$4D`) — none equal `$01`. Checkpoint tests masked this by poking `$01` directly.
   - Also audit [`tools/pack_mtpo.py`](../tools/pack_mtpo.py#L574-L586) WRAM bank order (`$A001`) around writing `reward_addr`.
2. **Hardcoded Waldo return dialogue:** `WaldoDialogCheck` ([`src/waldo_portal.inc`](../src/waldo_portal.inc#L1449-L1456)) unconditionally shows `WaldoReturnText` on return from *any* subgame, whether won or exited via `Start+Select`.
3. **Missing enter/exit transitions on 8 of 10 subgames:** Only `waldo` and `f13` have wipe-in / melt-out transitions; `feud`, `dk`, `smb`, `duck`, `mm2`, `wheel`, `zelda`, and `mtpo` hard-cut to black on exit and cold-boot in.
4. **Tight Zelda II ROM bank headroom:** Per [`docs/MEMORY-MAP.md`](MEMORY-MAP.md), several segments are near zero bytes free (`BANK1_SPELLS`: 4 B, `BANK2_SMOKE`: 1 B, `BANK2_CAVE`: 1 B, `BANK5`: 0 B, `BANK6_OAM`: 1 B, `PALACE_SHAKE`: 1 B, `GATEWAY`/`TERRAIN`: 0/0 B). Compact/reorganize before adding Phase 2–4 features.
5. **Known test & perf residuals:**
   - `tests/ow_clouds.lua` (`east-grass` 2-mismatch note in [`docs/STATUS.md`](STATUS.md#L98)).
   - Lag pockets: `p2-crowded-floor` (8 lag / 4 HUD shifts in `busy_rooms.py`), `p1-horsehead-approach` (3 lag in `perf_stress.py`), `west-grass` (`29.7k` peak), and `Rebonack` max-fire (needs re-measurement post-Build #778).
   - `ArcadeTick2` unconditionally calls all 5 spell tick helpers every frame; needs a fast active-bitmask early-out and stress profiling.
6. **Zelda 1 roar gameplay freeze:** In [`tools/pack_zelda.py`](../tools/pack_zelda.py#L143-L157), `ZELDA_NMI_ROAR` (`roar_hold`) swaps `$C000-$DFFF` via PRG Mode 1 to play `roar.dmc` from Bank 18 and **halts gameplay for 97 frames** until DMC finishes.

---

## 4. MMC3 Compatibility Tradeoff Matrix (All 11 Games)

| Game | Orig Mapper | Combined (FK23C) | Standalone MMC3 Target | Tradeoff & 2.0 Action |
| --- | --- | --- | --- | --- |
| **Zelda II (Core)** | MMC1 | Mapper 176 | Mapper 4 (`barba-z2-mmc3.nes`) | Near-zero tradeoff: standalone MMC3 uses the compact 4-waveform Game Over laugh vs. FK23C's 5-distinct-laugh mirror. Maintain clean standalone MMC3 build target for pure Z2 + RA. |
| **Where's Barba? (`waldo`)** | MMC3 | Mapper 176 | Mapper 4 (**100% parity**) | Native MMC3. Zero tradeoffs. |
| **Friday the 13th (`f13`)** | CNROM | Mapper 176 | Mapper 4 (**100% parity**) | Already full MMC3 (64 KB PRG / CHR-ROM). Zero tradeoffs. |
| **Barba Kong (`dk`)** | NROM | Mapper 176 | Mapper 4 (**100% parity**) | Already full MMC3 (256 KB PRG / 32 KB CHR-ROM). Zero tradeoffs. |
| **Super Barba Bros. (`smb`)** | NROM | Mapper 176 | Mapper 4 (**100% parity**) | Already full MMC3 (256 KB PRG / 32 KB CHR-ROM). Zero tradeoffs. |
| **Barba's Hunt (`duck`)** | NROM | Mapper 176 | Mapper 4 (**100% parity**) | Already full MMC3 (256 KB PRG / 32 KB CHR-ROM). Zero tradeoffs. |
| **Barba's Punch-Out!! (`mtpo`)** | MMC2 | Mapper 176 | Mapper 4 (**100% parity, IRQ-sensitive**) | Identical code in both builds; replaces MMC2 `$FD/$FE` auto-latching with scanline IRQs (`V_MODE`). Audit all bouts, knockdowns, intermissions, and endings so zero splits tear. |
| **Barba Man 2 (`mm2`)** | MMC1 (8K CHR-RAM) | Mapper 176 (32K CHR-RAM) | Mapper 4 (**drop 32K -> 8K CHR-RAM**) | NES 2.0 Mapper 4 + 32 KB banked CHR-RAM fails on older carts/emulators that clamp MMC3 CHR-RAM to 8 KB. Drop standalone MMC3 to standard 8 KB CHR-RAM (iNES 1.0 compatible) unless upgraded to CHR-ROM. |
| **Legend of Barba (`zelda`)** | MMC1 (8K CHR-RAM) | Mapper 176 (32K CHR-RAM) | Mapper 4 (**drop 32K -> 8K CHR-RAM**) | Same 8 KB CHR-RAM compatibility fix for standalone MMC3 (or CHR-ROM if animated scenery is added). Fix 97-frame `roar_hold` freeze in both builds. |
| **Barba's Beef (`feud`)** | MMC1 (128K CHR-ROM) | FK23C hybrid CHR-ROM/RAM | Mapper 4 (`feud_mmc3.py`, 256K CHR-ROM) | Flagship keeps dynamic CHR-RAM mixer (random 5-from-13 × 5-from-30 casts); standalone MMC3 uses 18 curated lineups (all 43 characters) in 256 KB CHR-ROM. Keep puzzles, art, and audio synced across both. |
| **Wheel of Barba (`wheel`)** | AxROM (4×32K, CHR-RAM) | Mapper 176 (`$5FF1` 32K switch) | **New: Port to Mapper 4** | Already uses Vertical mirroring + `WHEEL_NT_XOR`. Relocate small per-bank `$E000-$FFFF` code/data from banks 1–3 into a shared fixed bank + WRAM + 8 KB CHR-RAM so Wheel runs on standard MMC3 too. |

---

## 5. Arcade Spell Balance Baseline (For Phase 4)

Current baseline in [`src/arcade_spells.inc`](../src/arcade_spells.inc#L2238-L2259) (displayed MP = `raw >> 1`, max MP = 128) paired with Barba's 5-shot `VOLLEY_LIFE = $3F` (124 px) breath ([`src/breath.inc`](../src/breath.inc#L12)):

- **`LUCKY` (`12 -> 4 MP`):** Forces 3 Blue Magic Jar / 50-XP P-Bag drops -> **infinite MP loop** (a single jar exceeds cast cost).
- **`HEAVY` (`24 -> 10 MP`):** Room-wide 2× breath/attack damage + Ironknuckle shield bypass, including bosses -> halves boss fights for less than `SCALES`.
- **`STAR` (`24 -> 10 MP`):** 4.25 s invincibility + instant touch-kill on non-boss enemies -> wipes palace halls for trivial MP.
- **`CLOCK` (`28 -> 14 MP`):** 4.25 s freeze on all non-boss enemies.
- **`AXE` (`12 -> 4 MP`):** Free 8-dmg spinning axe on every `B` press all room, stacking with 5-shot fireballs.
- **`LOCK` / `BLADE` (`12->5` / `20->9 MP`):** Full-room homing / 8-way fireball steering for minimal MP.
- **`DECOY` / `BARREL` / `DOUBLE` (`8->3` / `16->6` / `16->7 MP`):** Priced far below vanilla Hyrule spells (`SCALES` 32→16, `LIFE` 70→50, `INFERNO` 120→64).
- **Stacking:** Multiple Arcade buffs can currently be active simultaneously (`ARCADE_ACTIVE_LO` / `HI`) and all 10 cabinets currently sit in Rauru.

---

## 6. Seven-Phase Execution Plan

### Phase 1 — Harden & Prep
- [x] Unify reward unlock protocol across all 10 subgames (`$63B1..$63BA` + `$648B`), wire F13 Day 3 / Coven win to `$63B1`, audit MTPO WRAM bank order around `reward_addr`, and make `CheckSpellOwned2` non-zero tolerant.
- [x] Add automated end-to-end Lua verification in `barba.nes` (enter portal -> trigger win -> return to Z2 -> verify spell/gear unlock + persistence).
- [x] Fix `tests/ow_clouds.lua` (`east-grass`) and verify full existing Zelda II + subgame Lua suites pass cleanly.
- [x] Compact tight Zelda II ROM segments (`BANK1_SPELLS`, `BANK2_SMOKE`, `BANK5`, `BANK6`, fixed bank) to restore safe headroom.
- [x] Reserve a frozen WRAM Bank 0 **RA Telemetry Block** + `ACTIVE_GAME_ID` (`0` = Z2, `1..10` = subgames) and document in [`docs/MEMORY-MAP.md`](MEMORY-MAP.md).

### Phase 2 — Zero-Lag Performance & Flicker Pass
- [x] Re-run `perf_stress.py matrix` and max-fire boss overlays on Build #778+ (including `Rebonack`). *(Build #812 `94327a38247b`: 62/62 scenes `0` lag / `0` HUD shifts; `ovf-rebonack` `lag 44->0`, `hudBad 11->0`, `wallMax 33,907->29,643`.)*
- [x] Drive remaining lag & HUD shifts to `0` (`p2-crowded-floor`, `p1-horsehead-approach`, `west-grass` peak, any remaining boss spikes). *(Buffer-0 starvation yield in `SoulsBossBar1`, 4x-unrolled `RemapBossSpr1`, `$E62A`/`$E646`/`$D346`/`$C1CD` fixed-bank fast paths, WRAM metatile check in `BarbaBlockRun`, unrolled `NmiRng6` & `HeadMoveToY6`, `IS_CLOUD_ROOM` caching, and `BarbaLoadOk` enemy-shot discount drove all 62 matrix scenes and `ovf-rebonack` to `0` lag / `0` `hudBad`; `busy_rooms` passed 28/29 runs `0` lag with `0` `hudBad` everywhere.)*
- [x] Add fast bitmask early-out to `ArcadeTick2` and stress-profile all 10 Arcade spells in crowded rooms. *(`ArcadeSpellHook0` masks ticking bits `$7B`/`$01`, `ArcadeTick2` uses per-bit early-out + expiry clear; `tests/perf_arcade_spells.lua` `16/16 PASS` with `0` lag/late/HUD shifts and `tickHits=0` on idle/passive spells.)*
- [x] Audit/reduce crowded-line flicker (especially Barba's 3rd head column `$C4` and tail/cloud priority). *(Promoted `$C4` head priority in `HeadColumnFirst6`, drew behind-BG `DrawPalaceClouds6` before foreground tail via separate `CLOUD_OAM_START` / `HALO_OAM_START`, and trimmed outer trail tips `$0E/$0F = $F8` in non-town `>= 6`-sprite scanline crowds in `DrawEncounterTrailSprites6` and `DrawDarkTrail4`; `ovf-rebonack` `framesDrop` fell `45.0% -> 25.4%`.)*

### Phase 3 — Hybrid Hyrule Distribution & Portal Transitions *(Verified Build #820, `172c1fff999a`)*
- [x] Audit all Hyrule town empty/unimportant-NPC houses + 2 strange/hidden spots; get producer sign-off on the exact 10-location progression map. *(10-spot progression across Barba's Arcade `R$1C` [`waldo` open from start], Bagu's Cabin [`f13`], Mini-Arcades in Saria/Ruto/Mido/Darunia/Nabooru/New Kasuto [`feud`/`dk`/`duck`/`mm2`/`wheel`/`zelda`], Old Kasuto ruined interior [`mtpo`], and East Hyrule Ocean Island `EH $07` [`smb`].)*
- [x] Implement persistent discovery flags + powering on Rauru's **Barba's Arcade** booths (undiscovered booths show dark / `"OUT OF ORDER"`). *(`$6806-$6807` `RA_DISCOVERY_LO/HI`, `PORTAL_BANK` PRG Bank 8, `DiscoverHyruleSpot8`/`CheckPortalDoor8`, `UpdateArcadeSigns8` `" CLEAR!"` marquees.)*
- [x] Port smooth wipe-in / wipe-out transitions with clean APU mute to the remaining 8 subgames (`feud`, `dk`, `smb`, `duck`, `mm2`, `wheel`, `zelda`, `mtpo`). *(Unified 30-frame wavy transition & `$4015=0 / $4011=0 / $E000=0 / $4017=$40` APU mute in `tools/portal_transitions.py`, combined-only `enable_transitions=True` keeping standalone MMC3/compat builds untouched.)*
- [x] Replace hardcoded `WaldoReturnText` with context-aware return UX (celebration + unlock message on milestone win; silent clean return on `Start+Select`) and booth completion indicators. *(Per-game `$6804` `RA_LAST_WIN_GAME` celebration messages in towns, `ShowNonTownWinBox8` in `EH $07`, and silent clean return on `Start+Select`.)*

### Phase 4 — Balance Pass (Zelda II Parity + Arcade Spells + Milestones) *(Build #826, `50d47d9f9a4a`)*
- [x] Rebalance `ArcadeSpellCostTbl`, break `LUCKY` infinite MP, tune active spells (`DECOY`/`DOUBLE`/`BARREL`/`LOCK`/`LUCKY`), and implement single-active-Arcade-spell exclusivity (`ClearArcadeActive2` in `src/arcade_spells.inc`; `AXE`/`STAR`/`BLADE`/`CLOCK`/`HEAVY` archived post-2.0 in Build #825).
- [x] Revisit all Zelda II hack strings (`town_dialogue.inc`, `sign.inc`, `sage_basement.inc`, `waldo_portal.inc`, `build.py` in-place lines) for the expanded 14×4 message box and ensure a 1-character border of space on all four sides (top/left/bottom/right), including `ShowNonTownWinBox8`. *(Build #824 `51cf1b3fe838`: offloaded town/sign/Error strings to `PORTAL_BANK` via `CopyTownDlg8`/`LoadTownDlg3` -> `ARCADE_DLG_BUF`, expanded all panic/service/sign/portal strings to 14×4, restored vanilla `A STRANGER.` / `THE CASTLE.`, and expanded `ShowNonTownWinBox8` to 7×18 with 1-tile padding on all 4 sides.)*
- [ ] Playtest Palaces 1–6, Death Mountain, Valley of Death, and Great Palace to verify vanilla Zelda II difficulty parity. *(Automated boss/palace/combat/perf regressions pass on Build #826; human F-key playtest ready via `play/Test Barba.cmd`.)*
- [x] Define and tune 1–2 curated portal milestones per active subgame while guaranteeing 100% full-game playability (`waldo` Moon, `feud` Fast Money `$A964`, `dk` Loop 1 100m `$C8B3`, `duck` Round 1 `$D39B`, `wheel` Bonus Round `$C988`; standalone ROMs remain 100% playable).

### Phase 5 — Subgame 2.0 Polish (5 Active Crossovers: `waldo`, `feud`, `dk`, `duck`, `wheel`)
*(Note: `zelda`, `mm2`, `mtpo`, `smb`, and `f13` were archived to `archive/subgames/` in Build #825 for post-2.0.)*
- [ ] **Tier 1 (Wheel & Feud):** `wheel` (multi-screen title alignment, polish, 97-puzzle roster QA) & `feud` (final polish & MMC3 lineup QA).
- [ ] **Tier 2 (Final Shine & Title Sign-Off):** `waldo`, `dk`, `duck` (remaining title sign-offs, edge-case QA).

### Phase 6 — MMC3 Parity, QA & Release Packaging
- [ ] Port `wheel` from AxROM/FK23C to standard Mapper 4 (MMC3) standalone build.
- [ ] Verify standalone `barba-z2-mmc3.nes` and all 5 active `play/compat/nes/*-compat.nes` ROMs against flagship FK23C builds via automated Mesen tests.
- [ ] Finalize per-game `.bps` patches and public multi-ROM patcher packaging (zero third-party ROM literals in public patches).

### Phase 7 — RetroAchievements (Freeze & Ship)
- [ ] Freeze all 2.0 ROM hashes (standalone MMC3 ROMs + combined `barba.nes`) and RAM/WRAM maps.
- [ ] Build symbol-driven generator (`tools/ra_achievements.py`) reading `build-report.json` + frozen RA Telemetry Block.
- [ ] Author and headless-Mesen-verify: 10 standalone MMC3 subgame sets + standalone Z2 set + combined Zelda II Barba 2.0 multi-ending set.
