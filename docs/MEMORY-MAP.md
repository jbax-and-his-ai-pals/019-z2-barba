# Barba Edition Memory Map & Free Space

Volatile build-current ROM free-space counts and Barba Edition RAM/WRAM/OAM/CHR
allocations. Update this file (not `AGENTS.md`) when allocations or free-space
counts change, so the system-prompt prefix stays cache-stable.

For vanilla Zelda II RAM addresses, see
[`.tools/z2disassembly/ram-map.txt`](../.tools/z2disassembly/ram-map.txt).

## ROM banks & free space

Counts for the trail, title and fall changes describe sampled build `dc9c4a25a40a`.
Other counts refer to `27518df041f4` unless specified.
Use `build-report.json` and a successful link of your variant before allocating space.

| Bank | Region | Contents / Notes | Free |
| --- | --- | --- | --- |
| 0 | `$A89E-$A97D` (`BANK0_OW`) | `BarbaSplitBurnForest` + `BurnAbort` | 1 |
| 0 | `$AA40-$BF6F` (`BANK0`) | Core Barba code, including grounded crouch poses, trail sampler and floor anchors for the crouch and raised-head roar, elbow wiggle, player and Dark Barba trail dispatch, Lava Link entrance movement gate and shield impact dispatch. `$BF70-$BF96` item pickup helpers. Preserve mapper `$BF9D-$BFDF` (`$BFB1` live OW call). | 70 (Build #346) |
| 0 | `$BFE0-$BFF9` (`BANK0_TAIL`) | `BurnMapEndGuard` (before vectors) | 1 |
| 0 | `$81C1-$81E4`, `$97F1-$9814`, `$9847-$9877` | Reclaimed dead vanilla code (METEOR) | 0 / 1 / 0 |
| 1 | `$9EB9-$9FFF` (`BANK1`) | `geldarm.inc`, downstab torso, `DrawEncounterTrailSprites1` trail promotion ahead of enemies, `BarbaLivesText` | 16 (Build #355) |
| 2 | `$9F85-$9FA0` | Valley of Death Lizalfos breath check (hook `$977C`) | 0 |
| 2 | `$A933-$BF32` (`BANK2_SMOKE`) | `town_smoke.inc`: outdoor town chimney smoke; `title_lava.inc`: title lava CHR swap and floating lava-pixel/bubble particles; `ow_foliage.inc`: desynced overworld grass & forest nametable animation (`OwFoliageTick2`); `waldo_portal.inc`: `PortalTbl*` (`16` slots) + `ArcadeName00..10` (`Barba's Arcade`) | expanded `$0A00 -> $1600` (Build #373) |
| 3 | `$9134-$93FF` (`BANK3_PAD`) | `sage_basement.inc` (separate vanilla pad at `$8BB1-$90EF` `BANK3_DLG`, 2 B free) | 370 |
| 3 | `$9D0A-$9FFF` (`BANK3_SIGN`) | `sign.inc`, `TownDoorRender`, `TownOpenerGate`, `LateSplit`, `BarbaLivesDisplay`, `DeathTrailPrep3`, Waldo dialogue | 27 (`9966f68e8816`) |
| 3 | `$B803-$BF6F` (`TOWN`) | Town villagers, dialogue, combo | 10 |
| 4 | `$8EC3-$93FF` (`PALACE_ROAR`) | Dark Barba trail, crystal ceremony, Lava Link entrance, Ironknuckle shield rebounds, boss meters and Gooma weapon priority | 115 (`12ed5bd69207`) |
| 4 | `$A765-$A8FF` (raw pad) | Lava Link `$A765-$A7A8`, `HiddenJarHit` `$A7BF-$A7CF`, `CarockHit` `$A7D0-$A7E4` (boss death gated on `$22`), `BANK4_SPK4` (`OwSpkGraveMove4`) `$A7E5-$A803`, `CarockReflectDamage` `$A804-$A80E` (24 dmg; HP 48 at `$A943`, six HP per pip in `boss_meter.inc`) | `$A7B0-$A7BE`, `$A80F-$A8FF` |
| 5 | `$BDE0-$BF5F` (`BANK5`) | `dark_barba.inc`, `HiddenJarHit`, `DarkBarbaVictory` (hook `$9BAC`) | 0 (32 in current native-audio build) |
| 5 | `$8CEB-$8D4D` | Ending fireball cutscene patch | 2 |
| 5 | `$A54F-$A59D` (vanilla pad) | Title two-sprite jaw animation and frame tables (`$A58C` -> `$8705` body anim) | `$A59B-$A59D` |
| 5 | `$A59E-$A5E7` (vanilla pad) | Sampled title roar (`$A59E-$A5DD`) + `TitleShakeX5` (`$A5DE-$A5E4`) | `$A5E5-$A5E7` |
| 5 | `$A5E8-$A5F7` (vanilla pad) | Title lava shimmer stub (hook `$A682`, then native `$C032`) | `$A5F8-$A5FF` |
| 5 | `$84C2-$84FF`, `$8705-$871A`, `$8891-$889E`, `$BFE0-$BFF7` | Title Barba neck wiggle, tail wag, and 2nd-roar shake (`$FF` pads) | 2 / 0 / 1 / 0 / 1 / 2 |
| 6 | `$878C-$87CB` (`BANK6_OAM`) | Scene OAM priority, encounter trail, boss meter dispatch, and `OwFoliageHop6` | 4 (Build #346) |
| 6 | `$87CC-$88FF` (`PALACE_SHAKE`) | Lava Link entrance shake, `LagNmiInBank6` and the ending and pit-fall sprite extensions | 1 |
| 6 | `$8900-$8FFF` (vanilla pad) | `$8900-$89FF` `BANK6_CLOUD` (includes `ShoutOamPriority6`, 2 B free), `$8A00-$8BFF` pickup/celebration (`$9B73/$9B24`, 0 B free in `d4e161fea84f`), `$8C00-$8DAE` coordinator/ducking/laugh bank selection, `$8DB0-$8DFF` `BANK6_PAD` (`PageLo6`/`PageHi6` + `TownQuicksandChr6`, 1 B free), `$8E00-$8EFF` title duck table, `$8F00-$8F27` title duck helpers (`$810F/$8116`), `$8F28-$8F3E` one-shot laugh DMC enable, `$8F40-$8F65` title DAC ramp, `$8F70-$8FCB` VBlank overrun and laugh delay, `$8FD0-$8FF5` title DMC enable (`$8005`) | — |
| 6 | `$93E5-$9407` (`FALL_ROAR`) | Palace drop roar dispatch in sampled builds, reusing the native sweep | 0 |
| 6 | `$9DA8-$9FFF` (`BANK6_HAZE`) | Lava haze, cloud entrance detection and rendering, scenery CHR updates, `WaterBank6`, `TitleLavaChr6`, shout row layout tables | 0 (Build #346) |
| 6 | `$AC09-$BF6F` (`BANK6`) | `shouts.inc`, `combo.inc`, `scales.inc`, `scanline_irq.inc`, `EncounterTorsoHop6`, title tail, `DarkLinkFireCheck`, town/castle scorch, Waldo RAM snapshot and return, `RoarRestoreBank` | 8 (Build #359) |
| 6 | `$BFE0-$BFF9` (`LAIR_HUD_SHAKE`) | Lava Link entrance HUD scroll override, after the mapper stub | 5 (`dddb732f2677`) |
| 7 | `$D39A-$D3C9` (`LAVA`), `$FEAA-$FECF` (`GATEWAY`), `$FF4C-$FF6E` (`TERRAIN`) | Fixed bank allocations (`FarCall0`: 5 B/call, 6 B w/ RTS, see `docs/BUILD.md`). `LAVA` also contains the shield rebound bank switch. Never allocate live JMP operands `$FF4B` or `$E02C`. | 2 / 0 / 1 (`88ac352c576e`) |
| 7 | `$F400-$FD70` | Sampled roar (`$F400-$FC80`, 2,177 B) in combined PRG page 31. Page 15 carries five octave-up Game Over laughs starting at `$F400/$F700/$F840/$F9C0/$FA80`. Both pages contain the early cached-pad helper `$F3C1-$F3DF` and native hurt `$F300-$F3C0`. | Sample storage |

- **Fixed-bank guarded vanilla rewrites** (no new padding claimed): NMI prologue `$C091-$C0A7`, VBlank setup and IRQ continuation `$C108-$C131` (IRQ entry `$C110`), NMI tail `$C182-$C1B5` (mask helper `$C18E`, tail starts `$C19D`, RTI `$C1B5`), fast offscreen mask `$F27D-$F2D1` (`$F2D2` spare), block anim `$E0FC-$E109`/`$E23A-$E247`/`$E29C-$E29D`, enemy projectile update `$E3B9-$E3C8` (empty-slot helper `$E3C1`), empty enemy slot skip & direct dispatch `$D5DA-$D5F8` (`$D5F6-$D5F8` 3 B spare).
- The native OAM Y clear uses `$D24C-$D25D` with a shared entry at `$D24C`. `$D250` is inside the loop. The two-column sprite clip uses `$F1D7-$F1F3`. Both reuse guarded vanilla ranges.
- The shield overlap hook at `$E646` replaces the native fireball disintegration call. Rebounds reuse the projectile lifetime and fractional X velocity, with no new RAM.
- Saria room `$06` quicksand uses PPU attributes `$27F8-$27FB` (`$05` throughout) for its eight metatiles. The full-width update fits in the existing `BANK6_PAD` allocation.
- The Saria sandbar uses a size-preserving West Hyrule map edit at bank 1 `$9297-$92E0`. The bridge guard's warning fits in the existing bank 3 message at `$A7FE`. Playtest with `python tools/create_test_pack.py --set saria` or **Test Barba - Saria Quicksand.cmd** (F1 overworld, F2 guard).

## RAM, WRAM, OAM & CHR

- **Lava Link entrance state:** Locks the camera with `$0728 = 1`. At world X `$0188`, Lava Link's `$AF,x = $7F` holds Barba over the central platform while native jump state `$0479` runs. On landing or while transformed into WYRMLNG, `$0728 = 2` suspends player physics through the fixed-bank hook at `$D4F3` in Palace 6 room `$3A`. The landing beat sets `$AF,x = $65` and counts down to `$60`, starting the roar on the sixth update. After the roar, `$AF,x` counts down from `$5E` to `$40` for 30 frames. Then `$0728 = 1` resumes physics and keeps the camera locked until Barba collects the key.

- **RAM:** `$05EA`, `$05EB` (lava contact), `$05EC`/`$05ED` (SCALES cast latch / last injured timer), `$05EE` (sampled roar bits: 7 active, 6 full pending, 5 injury pitch tail, 4 victory draining/done, 3 raised-head pose, 2 hurt, 1 item roar, 0 shaft playback with bit 7 set or Game Over laugh delay), `$05EF` (legacy start timer), `$05F0-$05FF` (roar, breath, tall renderer, extra guard; `$05F8`/`$05FA` ending fireball state/X). Cleared by native reset.
- **WRAM** (don't touch collision/room/save regions elsewhere in `$6000-$7FFF`):
  - `$6340-$6351`: town chimney smoke (`SMOKE_RM`, `SMOKE_WLD`, `SMOKE_COUNT`, `SMOKE_X_LO`/`HI`/`Y`, `SMOKE_OAM_Y`, `SMOKE_TMP0`/`1`)
  - `$6352-$635A`: Dark Souls bottom boss bar (`--boss-meter souls`: `SOULS_ACTIVE`, `SOULS_PHASE`, `SOULS_BOSS_IDX`, `SOULS_RED_STEPS`, `SOULS_WHITE_STEPS`, `SOULS_HOLD_TIMER`, `SOULS_DRAWN_RED`/`WHT`, `SOULS_PREV_RED`)
  - `$6360-$63AF`: overworld desynced grass & forest nametable animation (`OW_FOL_HI`/`LO`/`TILE`/`SEQ`/`TMR` 12 slots, `OW_FOL_ACTIVE`/`WORLD`/`RNG`/`CURSOR`/`SKIP`/`RUN`/`Q_MODE`/`TMP0..2`/`Q_HI`/`Q_LO`/`Q_EXP`/`Q_NEW`/`Q_FL`/`Q_FR`/`Q_SLOT`/`Q_FSEQ`/`Q_GIDX`/`Q_FIDX`)
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
  - `$64D2/$64D3`: late raw pads cache (sampled audio)
  - `$64D4`: item pickup hold (`1` fanfare, `$80` roar/tail)
  - `$64D5`: MMC3 `$8000` bank-select shadow (saved/restored by `LagNmiBank6` / `LagNmiReturn`)
  - `$64D6-$64F8`, `$64FB-$64FD`: scanline IRQ and scenery state (`IRQ_STAGE`, `IRQ_COUNT`, `IRQ_LINES`, `IRQ_X`, `IRQ_CTRL`, `IRQ_MASK`, `ROOM_HAS_LAVA`, cache/temps, `OW_PARALLAX_LINE` `$64EE`, active liquid `R1` `$64EF`, `OW_HAS_GRASS` `$64F0`, `OW_HAS_WATER` `$64F1`, `CLOUD_DX_HI`/`COL`/`IDX`/`Y`/`WIDTH`/`ATTR`/`TILE` `$64F2-$64F8`, `CLOUD_DRIFT_SUB`/`X`/`NT` `$64FB-$64FD`)
  - `$64F9`: Game Over DMC bank state (`0` normal, `2` pending enable, `1` fetching) in the combined sampled build
  - `$64FA`: signed horizontal scroll offset for Lava Link's Palace 6 entrance roar. The last two offsets repeat through the roar's audio tail. Bank 6 applies the offset to the HUD and IRQ scroll and subtracts it from the OAM shadow X coordinates while `$0728 = 2`.
  - `$6500-$65FF`: OAM DMA shadow page (8x16 sprite tiles rebased to the swapped pattern tables, with native blank `$F5` cells hidden to avoid extra MMC3 A12 clocks)
- **OAM:** tall head `$04/$4C/$C4`; extra torso `$20/$24`; item celebration `$34/$40` (item) + `$20/$24` (upright torso during the roar); extra fireballs `$3C/$44/$48`; enemy projectiles `$28/$2C/$30`; fall-in-hole (`Game Mode $0F`, `BarbaFallDraw`) `$08..$2C` Barba + `$3C..$60` shadow in native OAM, extended to `$08..$38` and `$3C..$6C` respectively in DMA OAM; ending fireball `$40-$47`; shout word `$00,$28..$34,$40,$DC` (7 glyphs); overworld flame `$FC` (`$74/$84/$94`).
  - The sampled raised-head roar puts the bend in the lower center and rear body slots at foot height and refills the trail Y history there.
  - Gooma's ball and links use `$A0/$A4/$A8/$AC` in Palace 5 room `$29` and swap into `$28/$2C/$30/$34` in the DMA shadow during the fight.
  - The boss meter uses eight early free DMA-shadow entries after the player and Dark Barba trail edits. In Gooma's fight it starts at `$4C`, behind the weapon and fireballs. The former native meter entries `$02C0-$02DF` stay available to the sprite renderers.
  - During a villager shout, the DMA shadow puts Barba at `$6500..$6528` and the glyphs at `$652C..$6544`. Shout rows are 16 px apart and use at most five sprites each.
  - During a town combo, the counter uses offsets `$00/$28/$2C/$30` ahead of fireballs, most actors, and clouds.
  - The side-view trail takes four DMA shadow entries `$50-$5C` after Barba, fireballs, projectiles and encounter clouds. A visible occupant moves to the last free entry at `$60` or later. Player CHR pairs `$14/$3E` hold the turned torso, `$44/$30` the tip and `$34/$36` the elbow. Pair `$0A` holds the vertical drop-shaft tip. The third torso and tip use DMA entries `$30/$34/$38` for Barba and `$64/$68/$6C` for his shadow. The elbow uses the center and rear slots and lifts 1px while the delayed torso rides higher. Scratch `$08-$0B` holds four X coordinates and `$0C-$0F` holds four Y coordinates for the bank-1 pass.
- **CHR:** extended 1 KB banks: 128-133 + 254-255 Saria room `$07` quicksand R1, 134-145 side-view liquid ripples (`$02`/`$04`), 146-153 Saria room `$06` quicksand R1, 156-157 Dark Souls boss bar R1 (`--boss-meter souls`), 170-173 town bush R0 sway variants (`-1/+1px` from bank 28; `--boss-meter souls` also uses 170-173 as R5 odd-bank boss sprite remaps for Horsehead/Helmethead/Carock/Gooma), 158-205 palace liquid ripples (skipping unused `$0E` banks 170-173), 206-213 West grass, 214-227 flames, 228 palace clouds, 229 town clouds, 230-237 overworld water/swamp (`$6E`/`$6F`, R0; base CHR 31 R0 is 124/125, and CHR 31 R1 `$9E-$AF` holds the 6 grass + 12 forest canopy variants), 238-245 title lava (R0), 246-253 East grass (R0). Game Over black Link in bank 17 `$00-$31` (map `$801F-$80C8`); even sprite banks 0-24 reserve `$24` for Myu, use `$5C`, and (in `waldo_portal` builds, skipping `14`) hold the tall Waldo hat + puffball at `$5E`; overworld flame `$60/$62` and ambience particles `$D0-$E3` (bank 30); ending fireball `$E0/$E2`, `$E4/$E6` (bank 14); ash `$7E/$80` (bank 6 only); shout glyphs bank 7 `$32/$7E/$80,$84-$BE` + `H` (`$7C`) and combo glyphs bank 6 `$6C-$AE`; town scorch bank 7 `$AC/$A4`, `$C1/$C0`, `$A7/$C2`; dialogue `?` `$34`, apostrophe `$35`. **Bank 7 `$00-$27` are villager 8x16 sprites — never allocate there** (`TOWN_SPRITE_PAIRS` in `tools/assets.py` guards them; bank 7 has no free pair left).
- Player sprite pairs `$32/$54` hold the eight visible rows of the curved body below the full 16px head when Barba crouches on an open floor or under a low ceiling.
- Title CHR uses sprite bank 0 pairs `$EA/$EC/$F8/$FA/$FC/$FE` for Barba's two-column head. BG bank 1 tile `$67` is the opaque black sprite-zero target. R0 banks 238/240/242/244 animate title lava `$68-$6A`, the top-row 1px surface wave tiles `$5A-$5D`, and the forest-edge lava masks `$6D-$70`. R5 bank 154 maps title sprite bank 3 with tiny bubble and ember pairs (`$C0/$C2/$C4/$C6`, addressed as `$C1/$C3/$C5/$C7` in 8x16 OAM); `$48/$4C` shadow OAM slots host the two floating particle slots (with the inner cliff columns trimmed so particles stay ahead of the 8-sprite limit on scanlines `128–143`, reusing `$6400-$6413` on title/story).
