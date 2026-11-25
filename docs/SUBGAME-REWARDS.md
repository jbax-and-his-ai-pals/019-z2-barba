# Subgame Reward Transformations & All-Screens Graphics Checklist

Template for wiring a subgame completion reward (such as beating *Where's Waldo?* → Barba's Waldo hat & glasses) into permanent Zelda II visual/gameplay transformations, plus a distribution checklist of every screen and pose where Barba's graphics appear.

## 1. Subgame Reward Template

1. **WRAM reward flag (`$648B+`)**:
   - Allocate a persistent WRAM byte in the Barba WRAM bank (e.g., `WALDO_HAT = $648B`, `WALDO_HAT_MAGIC = $57` in [`src/waldo_portal.inc`](../src/waldo_portal.inc)).
   - Document the allocation in [`docs/MEMORY-MAP.md`](MEMORY-MAP.md).
2. **Subgame win hook (`tools/pack_*.py`)**:
   - Hook the subgame's victory/ending handler to switch WRAM to Barba's bank, write the magic value (`STA $648B`), restore the subgame's WRAM bank if needed, and transition back to Zelda II (e.g., `make_waldo_win_hook()` in [`tools/pack_waldo.py`](../tools/pack_waldo.py)).
3. **CHR bank swap in NMI (`Update*Chr6` → Bank 3)**:
   - During VBlank (`NmiVblankSetup6` in [`src/scanline_irq.inc`](../src/scanline_irq.inc)), check the reward flag and swap MMC3 `R2` (`$1000–$13FF`) or `R3` to the transformed 1 KB CHR variant (`155` side-view for Waldo hat; overworld `$0736 == $05` intentionally keeps vanilla `R2`).
   - Keep vanilla `R2` (`bank 0` / `bank 120`) untouched when the flag is unset.
4. **Extra OAM overlay (`FinishBossOam6` in Bank 6)**:
   - For accessories or extensions that exceed Barba's native `24×48` head tiles (like the 2-sprite floppy Waldo hat `$1D` + `$5F`), draw into `$6500–$65FF` OAM shadow during `FinishBossOam6` (after `CopySceneOam6` / `ShakeLavaOam6` / `ShoutOamPriority6` and before OAM DMA).
   - Scan **forward from `$20`** (`ldx #$20`) so player accessories stay ahead of villager shout glyphs (`$2C–$44`), villagers (`$60+`), clouds, and chimney smoke on shared scanlines.
   - If a 2nd tile pair is needed in `sv_r2` (`bank 155`), alias a redundant pose tile (e.g., `windup/hurt` `$1D` → `$03`) in `DrawWaldoHat6` so `$1C` is free only when the reward is active.

## 2. All-Screens Graphics Distribution Checklist

Whenever adding a new player transformation or visual accessory to Barba, audit **every** screen, pose, and special case below:

| Screen / Mode / Pose | Where handled | What to check |
| --- | --- | --- |
| **Side-view standard (`$0736 == $0B`)** | `BarbaDisplay` (`tall_player.inc`), `FinishBossOam6` | Idle, walk (`walk0/1/2`), jump, fall, `windup`, `attack`, `hurt`, `crouch`, `crouch-attack`, `up` (`$3B` head sits 5 px lower in `$3A/$3C`), and `down` (downstab). |
| **Villager shouts** | `ShoutOamPriority6` (`scanline_irq.inc`) | Swaps Barba's center head from `$654C` to `$6500`. Any OAM overlay must check `$654C`, `$6500`, and `$650C` (crouch) and scan forward from `$20` so shouts never drop the accessory. |
| **Corridor crouch** | `BarbaCorridorCrouch` (`tall_player.inc`) | Head sits in `$650C` instead of `$654C`. |
| **Item pickup / Gem / Lava Link roars** | `palace_roar.inc`, `sampled_roar.inc`, `ShakeLavaOam6` | Uses `pose 8` (`$3B` upturned head). `ShakeLavaOam6` shifts `$6500` X before `FinishSceneOam6`, so overlays reading `$6503,y` shake in sync automatically. |
| **Overworld (`$0736 == $05`)** | `UpdateWaldoHatChr3` | Intentionally keeps vanilla overworld Barba (too few pixels for a readable hat). |
| **Pit fall (`$0736 == $0F`)** | `BarbaFallDraw` (`tall_player.inc`), `DrawExtendedFall6` | `R2 = 155` applies `sv_r2` head tiles automatically; if OAM overlays are needed during pit fall, check `$0736 == $0F` too. |
| **Ending cutscene (`$076C == $04`)** | `tools/build.py` (`CHR 0E`) | `CHR 0E` uses `$5E`/`$62` for ending ash, so skip `$5F` OAM overlays when `$076C == $04` (`sv_r2` head tiles still show cuff + glasses). |
| **HUD split & Letterbox** | `scanline_irq.inc` | Clip any OAM overlay above scanline 32 (`Y < $20`) so it never pokes into the HUD. |
| **Title / File Select / 1-Up / Life & Game Over** | `tools/build.py` (`CHR 00` `$D0`, even banks `$A8`, bank 17) | Standalone title/file-select dolls and Game Over silhouettes live in separate CHR slots outside `R2` bank 155. |
