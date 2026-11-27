# Barba Edition Memory Map & Free Space

Volatile build-current ROM free-space counts and Barba Edition RAM/WRAM/OAM/CHR
allocations. Update this file (not `AGENTS.md`) when allocations or free-space
counts change, so the system-prompt prefix stays cache-stable.

For vanilla Zelda II RAM addresses, see
[`.tools/z2disassembly/ram-map.txt`](../.tools/z2disassembly/ram-map.txt).

## ROM banks & free space

Counts for the full ROM reflect Build #822 (`39628addb2dd`) via `build/barba.map` + `build/build-report.json` + `src/barba.cfg`.
Use `build-report.json` and a successful link of your variant before allocating space.

| Bank | Region | Contents / Notes | Free |
| --- | --- | --- | --- |
| 0 | `$A89E-$A97D` (`BANK0_OW`) | `BarbaOverworldB_OW`, `BarbaBurnTile0` (RLE `$04` merge/split dispatch) | 0 |
| 0 | `$AA40-$BF75` (`BANK0`) | Core Barba code (`DmcPadRetry0`, `ExtraShieldOne0`, `ShieldReboundBank4`, `SpellMenuDone0`, `BurnAfterE024_0`, `BarbaExtraUpdate`, etc.; `BarbaOverworld2` moved to Bank 2). Preserve mapper `$BF9D-$BFDF` (`$BFB1` live OW call). | 19 |
| 0 | `$BFE0-$BFF9` (`BANK0_TAIL`) | `BurnFindRow4aEnd0` (before vectors) | 3 |
| 0 | `$81C1-$81E4`, `$97F1-$9814`, `$9847-$9877` | Reclaimed dead vanilla code (METEOR) | 0 / 1 / 0 |
| 0 | `$9C1A-$9D31`, `$A347-$A35E`, `$8DC9-$8DDB` (`BANK0_SPELL..3`) | 2-column spell menu, `ArcadeSpellHook0` ticking bitmask fast-out & Level-Up State 1 (`$9D7D`) stubs | 5 / 0 / 2 |
| 1 | `$9EB9-$9FFF` (`BANK1`, `$84E7-$84FF` `BANK1_PAD2`, `$BFE0-$BFF9` `BANK1_TAIL`) | `geldarm.inc`, downstab torso, `BarbaLivesText`, `LevelUpInit2`, `AxeSpinAttr`/`AxeSpriteSetup1`, `SpellMenuInit2`, `AttrRowOff7`/`ItemsLabel5` | 53 / 0 / 3 |
| 1 | `$87C6-$889F` (`BANK1_GEAR`), `$93BB-$93FF` (`BANK1_GEAR2`) | Cosmetic Gear Bar menu navigation/focus (`GearToggleFocus1`, `GearMenuInput1`, `ArcadeSideViewInit2`, `ArcadeDoubleXp2`) | 0 / 22 |
| 1 | `$A933-$B233` (`BANK1_SOULS`) | `souls_boss_bar.inc` (`@queue_ppu` buffer-0 starvation yield, 4x-unrolled `RemapBossSpr1`), `DrawGearRow14_1`/`DrawGearRow15_1`/`GearCheckAB1`, `MenuHeaderRow26` | 58 |
| 1 | `$B234-$BF9C` (`BANK1_SPELLS`) | 18-spell system & 26×20 2-column pause menu (`ArcadeTick2` per-bit dispatch) + `CheckGearEquipped1` | 4 |
| 2 | `$87D3-$889F` (`BANK2_CAVE`) | `cave_light.inc`: `CaveApplyPal2` + `CaveLightPalettes`; overworld flame helpers (`OwDrawFlame2`, `OwDirIdx2`, `OverworldBase`/`OwFlameX`/`Y`) | 32 |
| 2 | `$9F85-$9FA0` | Valley of Death Lizalfos breath check (hook `$977C`) | 0 |
| 2 | `$93C9-$93FF` (`BANK2_OW3`), `$9FA1-$9FFF` (`BANK2_OW`), `$BF33-$BF6F` (`BANK2_OW2`) | `OwSplitEntry2`, `OwSplitShift2`, `OwSplitWrite2` (`src/ow_burn.inc`) | 10 / 2 / 16 |
| 2 | `$A933-$BF32` (`BANK2_SMOKE`) | `town_smoke.inc`, `title_lava.inc`, `ow_foliage.inc` (incl. `WaterBank2` R0 water ripple gated on `$076C == 1`), `ScanOwScenery2`, `BarbaOverworld2`, `CavePalTblOff`, `ArcadeNpcTick2` (`PORTAL_BANK` offload) | 2558 |
| 3 | `$9134-$92FF` (`BANK3_PAD`) | `sage_basement.inc`, Mini-Arcade & Bagu Cabin room layouts (separate vanilla pad at `$8BB1-$90EF` `BANK3_DLG`, 9 B free) | 34 (`BANK3_DLG` 9) |
| 3 | `$9D0A-$9FFF` (`BANK3_SIGN`) | `sign.inc`, `TownDoorRender`, `TownOpenerGate`, `LateSplit`, `BarbaLivesDisplay`, `DownstabWagAttr3`, `DeathTrailPrep3`, Waldo dialogue | 13 |
| 3 | `$B803-$BF6F` (`TOWN`) | Town villagers, dialogue, combo | 15 |
| 4 | `$8EC3-$93FF` (`PALACE_ROAR`) | Dark Barba trail (outer-tip crowd trim), crystal ceremony, Lava Link entrance, `ShieldRebound4` (`plp`), boss meters and Gooma weapon priority | 2 |
| 4 | `$83DC-$846F` (`BANK4_GEAR`) | Cosmetic trophy gear overlay helpers (`GearCheckY4`), `BossMeterRoom`, `DarkTrailTiles` | 2 |
| 4 | `$A765-$A8FF` (raw pad) & `$9EE0-$9FFF` / `$A539-$A63F` / `$A80F-$A8FF` / `$A7E5-$A803` (`BANK4_SPK..4`) | Lava Link `$A765-$A7A8`, `HiddenJarHit` `$A7BF-$A7CF`, `CarockHit` `$A7D0-$A7E4` (boss death gated on `$22`), `BANK4_SPK..4` (overworld ambient sparkles), `CarockReflectDamage` `$A804-$A80E` (24 dmg; HP 48 at `$A943`, six HP per pip in `boss_meter.inc`) | 2 / 2 / 0 / 2 (`BANK4_SPK..4`) |
| 4 | `$8817-$889F` (`BANK4_OW`), `$A3FB-$A43F` (`BANK4_OW2`) | `OwAttrUpdate4`, `OwPalCodes4`, `OwAttrSetup4`, `OwAttrFinish4` (`src/ow_burn.inc`) | 4 / 1 |
| 5 | `$BB15-$BB82` (`BANK5_OW`) | `OwDeleteByte5` (`src/ow_burn.inc`, 1-tile RLE `$04` merge delete) | 0 |
| 5 | `$BDE0-$BF5F` (`BANK5`, `$BF70-$BF9C` `BANK5_RESET`) | `dark_barba.inc`, `HiddenJarHit`, `DarkBarbaVictory` (hook `$9BAC`), `EndingPalFix5` | 34 / 4 |
| 5 | `$BBD5-$BBF4` (`BANK5_SPLAT`) | `GiantBotSplat5` (`src/splat.inc`, hook `$A180`) | 19 |
| 5 | `$8CEB-$8D4D` | Ending fireball cutscene patch (`ENDING_FIRE`) | 2 |
| 5 | `$A54F-$A59D` (vanilla pad) | Title two-sprite jaw animation and frame tables (`$A58C` -> `$8705` body anim) | `$A59B-$A59D` |
| 5 | `$A59E-$A5E7` (vanilla pad) | Sampled title roar (`$A59E-$A5DD`) + `TitleShakeX5` (`$A5DE-$A5E4`) | `$A5E5-$A5E7` |
| 5 | `$A5E8-$A5F7` (vanilla pad) | Title lava shimmer stub (hook `$A682`, then native `$C032`) | `$A5F8-$A5FF` |
| 5 | `$84C2-$84CF`, `$8705-$871A`, `$8891-$889E`, `$BFE0-$BFF7` | Title Barba neck wiggle (`BANK5_TITLE_PAD`), tail wag, and 2nd-roar shake (`$FF` pads) | 5 / 0 / 1 / 2 |
| 6 | `$878C-$87CB` (`BANK6_OAM`) | Scene OAM priority (`HeadMoveToY6`), `VblankMacroTbl6`, `OwFoliageHop6`, `CaveHaloDx`/`Dy` | 4 |
| 6 | `$87CC-$88FF` (`PALACE_SHAKE`) | Lava Link entrance shake, `LagNmiInBank6`, `DrawTrailFastSplit6`/`DrawTrailFastLoop6`, ending and pit-fall sprite extensions | 3 |
| 6 | `$8900-$8FFF` (vanilla pad) | `$8900-$89FF` `BANK6_CLOUD` (`IsSpriteCloudRoom6`, `CheckTrailFast4_6`, 6 B free), `$8A00-$8BFF` `ITEM_ROAR` (9 B free), `$8C00-$8DAF` `SAMPLED_ROAR` (5 B free), `$8DB0-$8DFF` `BANK6_PAD` (4 B free), `$8E10-$8EFF` `BANK6_EXTRA` (`RaTelemetryCheck6`/`Init6`, `ShoutOamPriority6`, `DrawExtendedFall6`, `DrawTrailFast6`, 1 B free), `$8F28-$8F3F` `LAUGH_BANK` (1 B free), `$8F66-$8F6F` `WALDO_HAT_1` (unused after inlining `UpdateWaldoHatChr6`, 10 B free), `$8F70-$8FCF` `LAUGH_DELAY` (4 B free), `$8F40-$8F65` title DAC ramp, `$8FD0-$8FF5` title DMC enable (`$8005`) | 6 / 9 / 5 / 4 / 1 / 1 / 10 / 4 |
| 6 | `$93E5-$9407` (`FALL_ROAR`) | Palace drop roar dispatch in sampled builds, reusing the native sweep | 0 |
| 6 | `$9DA8-$9FFF` (`BANK6_HAZE`) | Lava haze, `TownSmokeHop6`, scenery CHR updates, `TitleLavaChr6`, `ShoutSrc6` | 12 |
| 6 | `$AC09-$BF6F` (`BANK6`, `$BF76-$BF9C` `ITEM_HOLD`) | `shouts.inc`, `combo.inc`, `scales.inc`, `scanline_irq.inc`, unrolled `NmiRng6` + `CopyOamShadow6` (8×) + `HeadColumnFirst6` (`$C4` priority), behind-BG `DrawPalaceClouds6` before foreground tail, `DrawEncounterTrailSprites6`, `UpdateWaldoHatChr6`, title tail, `DarkLinkFireCheck`, town/castle scorch, `BarbaWaldoRestore6`, `RoarRestoreBank`, `BarbaWaldoPortal6` gateway | 22 / 0 |
| 6 | `$BFE0-$BFF9` (`LAIR_HUD_SHAKE`) | Lava Link entrance HUD scroll override, after the mapper stub | 4 |
| 8 | `$8000-$BFFF` (`PORTAL_BANK`) | PRG Bank 8 (`128..144 KB` in PRG): `waldo_portal.inc` portal tables, `DiscoverHyruleSpot8`, `CheckPortalDoor8`, `UpdateArcadeSigns8`, `ShowNonTownWinBox8`, `BarbaWipeIn8`/`BarbaMelt8`, context-aware `WinReturnText` | 12163 |
| 7 | `$D39A-$D3C9` (`LAVA`), `$E013-$E01A` (`LAG_RET`), `$FEAA-$FECF` (`GATEWAY`), `$FF4C-$FF6F` (`TERRAIN`) | Fixed bank allocations (`FarCall0`: 5 B/call, 6 B w/ RTS, see `docs/BUILD.md`). `LAVA` also contains `ShieldReboundGateway`; `LAG_RET` holds `LagNmiReturn`; `GATEWAY` holds `EnemyFireGateway` + `ShieldFireGatewaySlow`; `TERRAIN` holds `TerrainBatch` + `NativeReturn0` + `ShieldFireGateway` (`EXTRA_LIVE == 0` fast path). Never allocate live JMP operands `$FF4B` or `$E02C`. | 0 / 0 / 0 / 4 |
| 7 | `$F400-$FD70` | Sampled roar (`$F400-$FC80`, 2,177 B) in combined PRG page 31. Page 15 carries five octave-up Game Over laughs starting at `$F400/$F700/$F840/$F9C0/$FA80`. Both pages contain the early cached-pad helper `$F3C1-$F3DF` and native hurt `$F300-$F3C0`. | Sample storage |

- **Fixed-bank guarded vanilla rewrites** (no new padding claimed): NMI prologue `$C091-$C0A7`, VBlank setup and IRQ continuation `$C108-$C131` (IRQ entry `$C110`; `$C1CD-$C1CF` NOPed redundant `SwapToPRG0`), NMI tail `$C182-$C1B5` (mask helper `$C18E`, tail starts `$C19D`, RTI `$C1B5`), controller read `$D346-$D355` (single-read fast path when DMC `$4015 & $10 == 0`, falling back to `FarCall0(DmcPadRetry0)`), fast offscreen mask `$F27D-$F2D1` (`$F2D2` spare), block anim `$E0FC-$E109`/`$E23A-$E247`/`$E29C-$E29D`, enemy projectile update `$E3B9-$E3C8` (empty-slot helper `$E3C1`), empty enemy slot skip & direct dispatch `$D5DA-$D5F8` (`$D5F6-$D5F8` 3 B spare), Ironknuckle shield impact `$E62A` -> `ShieldFireGateway` and rebound `$E646` -> `ShieldReboundGateway`.
- The native OAM Y clear uses `$D24C-$D25D` with a shared entry at `$D24C`. `$D250` is inside the loop. The two-column sprite clip uses `$F1D7-$F1F3`. Both reuse guarded vanilla ranges.
- The shield overlap hook at `$E646` replaces the native fireball disintegration call. Rebounds reuse the projectile lifetime and fractional X velocity, with no new RAM.
- Saria room `$06` quicksand uses PPU attributes `$27F8-$27FB` (`$05` throughout) for its eight metatiles. The full-width update fits in the existing `BANK6_PAD` allocation.
- The Saria sandbar uses a size-preserving West Hyrule map edit at bank 1 `$9297-$92E0`. The bridge guard's warning fits in the existing bank 3 message at `$A7FE`. Playtest with `python tools/create_test_pack.py --set saria` or **Test Barba - Saria Quicksand.cmd** (F1 overworld, F2 guard).

## RAM, WRAM, OAM & CHR

- **Lava Link entrance state:** Locks the camera with `$0728 = 1`. At world X `$0188`, Lava Link's `$AF,x = $7F` holds Barba over the central platform while native jump state `$0479` runs. On landing or while transformed into WYRMLNG, `$0728 = 2` suspends player physics through the fixed-bank hook at `$D4F3` in Palace 6 room `$3A`. The landing beat sets `$AF,x = $65` and counts down to `$60`, starting the roar on the sixth update. After the roar, `$AF,x` counts down from `$5E` to `$40` for 30 frames. Then `$0728 = 1` resumes physics and keeps the camera locked until Barba collects the key.

- **RAM:** `$05EA`, `$05EB` (lava contact), `$05EC`/`$05ED` (SCALES cast latch / last injured timer), `$05EE` (sampled roar bits: 7 active, 6 full pending, 5 injury pitch tail, 4 victory draining/done, 3 raised-head pose, 2 hurt, 1 item roar, 0 shaft playback with bit 7 set or Game Over laugh delay), `$05EF` (legacy start timer), `$05F0-$05FF` (roar, breath, tall renderer, extra guard; `$05F8`/`$05FA` ending fireball state/X). Cleared by native reset.
- **WRAM** (don't touch collision/room/save regions elsewhere in `$6000-$7FFF`):
  - `$6340-$6351`: town chimney smoke (`SMOKE_RM`, `SMOKE_WLD`, `SMOKE_COUNT`, `SMOKE_X_LO`/`HI`/`Y`, `SMOKE_OAM_Y`, `SMOKE_TMP0`/`1`); `$6700-$670F` holds `SMOKE_BANDS` (16-byte foreground OAM Y histogram)
  - `$6352-$635D`: Dark Souls bottom boss bar (`--boss-meter souls`: `SOULS_ACTIVE`, `SOULS_PHASE`, `SOULS_BOSS_IDX`, `SOULS_RED_STEPS`, `SOULS_WHITE_STEPS`, `SOULS_HOLD_TIMER`, `SOULS_DRAWN_RED`/`WHT`, `SOULS_PREV_RED`, `SOULS_SAVED_BG`, `SOULS_BG_DIRTY`, `SOULS_BG_VALID`)
  - `$635E`: `SPLAT_TIMER` (14-frame countdown for Great Palace Giant Bot split splat SFX in `src/splat.inc`)
  - `$635F`: `CAVE_PAL_PEND` (bits `0..3`: pending dark-cave palette level+1 `1..10` applied directly in VBlank; bit `7`: Barba `$3F11..$3F13` refresh deferred while `$074B`/`$070F` is active)
  - `$6360-$63AF`: overworld desynced grass & forest nametable animation (`OW_FOL_HI`/`LO`/`TILE`/`SEQ`/`TMR` 12 slots, `OW_FOL_ACTIVE`/`WORLD`/`RNG`/`CURSOR`/`SKIP`/`RUN`/`Q_MODE`/`TMP0..2`/`Q_HI`/`Q_LO`/`Q_EXP`/`Q_NEW`/`Q_FL`/`Q_FR`/`Q_SLOT`/`Q_FSEQ`/`Q_GIDX`/`Q_FIDX`); `$6360-$6361` are reused as `ARCADE_SIGN_LO/HI` inside Barba's Arcade (`Rauru room $1C`)
  - `$63B0-$63BF`: `SUBGAME_REWARDS` (16-byte per-slot completion table for `waldo`..`mtpo`; note `$648B` keeps Waldo hat unlock alias)
  - `$63C0-$63FF`: `ARCADE_DLG_BUF` (64-byte dynamic `INSERT COIN / <SUBGAME> / PRESS B TO PLAY` text buffer for `CheckPortalDoor2`)
  - `$6400-$642F`: extra projectile records
  - `$6430-$643F`: overworld ambient sparkles (`OW_SPK_X`/`Y`/`TIMER`/`PREV_*`/`ACTIVE`/`DX`/`DY`/`TMP`)
  - `$6440-$645F`: scratch (`$6457` lazy-save, `$6458-$645F` geometry terrain cache, `$645C` `EXTRA_LIVE`)
  - `$6460-$6469`: shouts (`$6465` actor, `$6467` word, `$6468` timer, `$6469` cycle)
  - `$646A`, `$6490-$64D0`: town scorch ring (16-slot FIFO + head/page); `$64D1` `SIGN_PENDING`; `$04A0,x` burned-sign line (`$21`/`$22`)
  - `$646B`: volley aim latch (`0` forward / `$40` up)
  - `$646C-$646F`, `$6488`: town combo banner
  - `$6470-$6476`: Inferno timer/wave aim (`$6470`/`$6473`), overworld flame timer/dir (`$6471`/`$6472`), `$6474` METEOR dive state, `$6475/$6476` Rauru sage basement `SAGE_STATE`/`SAGE_BOX`
  - `$6477`: title lava shimmer dirty flag (restore R0 bank 4 after Start)
  - `$6478-$6480`: Waldo portal state (`PORTAL_DEBOUNCE..MELT_DIR`, `WALDO_RETURN_MSG` `$647E`, `WALDO_ENTER_MSG` `$647F`)
  - `$6481-$6487`: player trail Y history (six samples and next write index)
  - `$648C-$648E`: `OW_SPK_KIND` (overworld ambient particle kind per slot)
  - `$648F`: `BARBA_GEAR` (cosmetic trophy equipment: bits `0..1` head `0=none, 1=Waldo Hat, 2=Hockey Mask, 3=Mega Helmet`, bit `4` Red Necktie, bit `5` Championship Belt, bit `7` initialized)
  - `$64D2/$64D3`: late raw pads cache (sampled audio)
  - `$64D4`: item pickup hold (`1` fanfare, `$80` roar/tail)
  - `$64D5`: MMC3 `$8000` bank-select shadow (saved/restored by `LagNmiBank6` / `LagNmiReturn`)
  - `$64D6-$64F8`, `$64FB-$64FD`: scanline IRQ and scenery state (`IRQ_STAGE`, `IRQ_COUNT`, `IRQ_LINES`, `IRQ_X`, `IRQ_CTRL`, `IRQ_MASK`, `ROOM_HAS_LAVA`, cache/temps, `OW_PARALLAX_LINE` `$64EE`, active liquid `R1` `$64EF`, `OW_HAS_GRASS` `$64F0`, `OW_HAS_WATER` `$64F1`, `IS_CLOUD_ROOM` `$64F2` cached `IsSpriteCloudRoom6` result, `HALO_OAM_START` `$64F3` highest OAM slot below Barba's trail, `CLOUD_OAM_START`/`CLOUD_Y`/`CLOUD_WIDTH`/`CLOUD_ATTR`/`CLOUD_TILE` `$64F4-$64F8`, `CLOUD_DRIFT_SUB`/`X`/`NT` `$64FB-$64FD`)
  - `$64F9`: Game Over DMC bank state (`0` normal, `2` pending enable, `1` fetching) in the combined sampled build
  - `$64FA`: signed horizontal scroll offset for Lava Link's Palace 6 entrance roar. The last two offsets repeat through the roar's audio tail. Bank 6 applies the offset to the HUD and IRQ scroll and subtracts it from the OAM shadow X coordinates while `$0728 = 2`.
  - `$64FF`: `CAVE_GLOW_ON` (`0` = off, bits `0..3` = `Cur` `0..9`, bits `4..7` = `Tick` `0..3` for dark-cave firelight envelope in `src/cave_light.inc`; `$64FE` is `DOWNSTAB_ROWS`).
  - `$6741`: `CAVE_LIGHT_DISP` (bits `0..3` = last displayed dark-cave level `0..9`; bits `5..7` = `$2001` emphasis `$00/$20/$E0` applied below scanline 31 by `CaveEmph6`).
  - `$6800-$683F`: **Frozen RA Telemetry Block** (`src/ra_telemetry.inc`, WRAM Bank 0, inside the unused `$6742-$6957` hole; initialized by `RaTelemetryInit6` and kept live in VBlank by `RaTelemetryCheck6` without wiping persistent discovery/clear flags):
    - `$6800` `RA_MAGIC_0` = `$42` (`'B'`), `$6801` `RA_MAGIC_1` = `$32` (`'2'`), `$6802` `RA_VERSION` = `$01`
    - `$6803` `ACTIVE_GAME_ID`: `0` = Zelda II, `1` = `waldo`, `2` = `f13`, `3` = `feud`, `4` = `dk`, `5` = `smb`, `6` = `duck`, `7` = `mm2`, `8` = `wheel`, `9` = `zelda`, `10` = `mtpo`
    - `$6804` `RA_LAST_WIN_GAME` (last subgame won `1..10`, written by all 10 portal exit helpers on milestone win to trigger context-aware return celebration; `0` = Start+Select silent return / cleared), `$6805` `RA_SUBGAME_EVENT` (milestone/ending event code)
    - `$6806-$6807` `RA_DISCOVERY_LO/HI` (live persistent 10-spot discovery bitmask gating Rauru Barba's Arcade booths; bit 0 = `waldo` open from start, updated by `DiscoverHyruleSpot8`/`SetSlotDiscovered8`), `$6808-$6809` `RA_CLEAR_LO/HI`, `$680A-$680B` `RA_ALT_END_LO/HI` (persistent full-clear and alternate-ending bitmasks)
    - `$680C-$680F` `RA_Z2_FLAGS` (4 bytes reserved for Z2 campaign telemetry), `$6810-$683F` `RA_RESERVED` (48 bytes strictly reserved for Phase 7 RA)
  - `$6500-$65FF`: OAM DMA shadow page (8x16 sprite tiles rebased to the swapped pattern tables, with native blank `$F5` cells hidden to avoid extra MMC3 A12 clocks)
  - `$6680-$66F7`, `$6710-$6740`: 18-spell & 2-column pause menu state (`ARCADE_ACTIVE_LO/HI`, `CLOCK`/`LUCKY`/`DECOY`/`BARREL`/`LOCK`/`STAR`/`AXE` timers & coords, `SPELL_MENU_ACTIVE`, `SPELL_OLD_SEL`, `SPELL_GEAR_SEL` `$6699`, `SPELL_ROW_BUF0/1` `$66A0..$66D3`, `ARCADE_CLOCK_XY` `$66E6..$66F7`, `SPELL_ATTR_BUF` `$6710..$6739`, `SPELL_ATTR_TMP` `$673A..$6740`; Bank 1 `$B200-$BF6E` `BANK1_SPELLS`, Bank 1 `$87C6-$889F`/`$93BB-$93FF` `BANK1_GEAR`/`BANK1_GEAR2`, Bank 1 `$9EB9-$9FFF` `LevelUpInit2`, Bank 0 `$9C1A-$9D31`/`$A347-$A35E`/`$8DC9-$8DDB` `BANK0_SPELL..3`)
  - `$73E0-$73E8`: `BarbaArcadeEnemies` (9-byte room `$1C` enemy list staged by `ArcadeNpcTick2` in `BANK2_SMOKE`; pointed to by Bank 3 `$85D9`)
- **OAM:** tall head `$04/$4C/$C4`; extra torso `$20/$24`; item celebration `$34/$40` (item) + `$20/$24` (upright torso during the roar); extra fireballs `$3C/$44/$48`; enemy projectiles `$28/$2C/$30`; fall-in-hole (`Game Mode $0F`, `BarbaFallDraw`) `$08..$2C` Barba + `$3C..$60` shadow in native OAM, extended to `$08..$38` and `$3C..$6C` respectively in DMA OAM; ending fireball `$40-$47`; shout word `$00,$28..$34,$40,$DC` (7 glyphs); overworld flame `$FC` (`$74/$84/$94`).
  - The sampled raised-head roar puts the bend in the lower center and rear body slots at foot height and refills the trail Y history there.
  - Gooma's ball and links use `$A0/$A4/$A8/$AC` in Palace 5 room `$29` and swap into `$28/$2C/$30/$34` in the DMA shadow during the fight.
  - The boss meter uses eight early free DMA-shadow entries after the player and Dark Barba trail edits. In Gooma's fight it starts at `$4C`, behind the weapon and fireballs. The former native meter entries `$02C0-$02DF` stay available to the sprite renderers.
  - During a villager shout, the DMA shadow puts Barba at `$6500..$6528` and the glyphs at `$652C..$6544`. Shout rows are 16 px apart and use at most five sprites each.
  - During a town combo, the counter uses offsets `$00/$28/$2C/$30` ahead of fireballs, most actors, and clouds.
  - The side-view trail takes four DMA shadow entries `$50-$5C` after Barba, fireballs, projectiles and encounter clouds. A visible occupant moves to the last free entry at `$60` or later. Player CHR pairs `$14/$3E` hold the turned torso, `$44/$30` the tip and `$34/$36` the elbow. Pair `$0A` holds the vertical drop-shaft tip. The third torso and tip use DMA entries `$30/$34/$38` for Barba and `$64/$68/$6C` for his shadow. The elbow uses the center and rear slots and lifts 1px while the delayed torso rides higher. Scratch `$08-$0B` holds four X coordinates and `$0C-$0F` holds four Y coordinates for the bank-1 pass.
- **CHR:** extended 1 KB banks: 128-133 + 254-255 Saria room `$07` quicksand R1, 134-145 side-view liquid ripples (`$02`/`$04`), 146-153 Saria room `$06` quicksand R1, 156-157 Dark Souls boss bar R1 (`--boss-meter souls`), 170-173 town bush R0 sway variants (`-1/+1px` from bank 28; `--boss-meter souls` also uses 175-180 as R5 odd-bank boss sprite remaps for Horsehead/Helmethead/Rebonack/Carock/Gooma/Thunderbird), 158-205 palace liquid ripples (skipping unused `$0E` banks 170-173), 206-213 West grass, 214-227 flames, 228 palace clouds, 229 town clouds, 230-237 overworld water/swamp (`$6E`/`$6F`, R0; base CHR 31 R0 is 124/125, and CHR 31 R1 `$9E-$AF` holds the 6 grass + 12 forest canopy variants), 238-245 title lava (R0), 246-253 East grass (R0). Game Over black Link in bank 17 `$00-$31` (map `$801F-$80C8`); even sprite banks 0-24 reserve `$24` for Myu, use `$5C`, and (in `waldo_portal` builds, skipping `14`) hold the tall Waldo hat + puffball at `$5E`; overworld flame `$60/$62` and ambience particles `$D0-$E3` (bank 30); ending fireball `$E0/$E2`, `$E4/$E6` (bank 14); ash `$7E/$80` (bank 6 only); AXE spell Daira spinning axe `$7E` (non-town even banks `0..24` skipping `6`/`14`) and `$FE` (bank 6); shout glyphs bank 7 `$32/$7E/$80,$84-$BE` + `H` (`$7C`) and combo glyphs bank 6 `$66/$78-$7C/$94-$98/$AA-$B4` (XP score pairs `$60/$6C/$9C-$A6` and HUD partial-bar pairs `$6E/$70` stay vanilla); town scorch bank 7 `$AC/$A4`, `$C1/$C0`, `$A7/$C2`; dialogue `?` `$34`, apostrophe `$35`. **Bank 7 `$00-$27` are villager 8x16 sprites — never allocate there** (`TOWN_SPRITE_PAIRS` in `tools/assets.py` guards them; bank 7 has no free pair left).
- Player sprite pairs `$32/$54` hold the eight visible rows of the curved body below the full 16px head when Barba crouches on an open floor or under a low ceiling.
- Title CHR uses sprite bank 0 pairs `$EA/$EC/$F8/$FA/$FC/$FE` for Barba's two-column head. BG bank 1 tile `$67` is the opaque black sprite-zero target. R0 banks 238/240/242/244 animate title lava `$68-$6A`, the top-row 1px surface wave tiles `$5A-$5D`, and the forest-edge lava masks `$6D-$70`. R5 bank 154 maps title sprite bank 3 with tiny bubble and ember pairs (`$C0/$C2/$C4/$C6`, addressed as `$C1/$C3/$C5/$C7` in 8x16 OAM); `$48/$4C` shadow OAM slots host the two floating particle slots (with the inner cliff columns trimmed so particles stay ahead of the 8-sprite limit on scanlines `128–143`, reusing `$6400-$6413` on title/story).
