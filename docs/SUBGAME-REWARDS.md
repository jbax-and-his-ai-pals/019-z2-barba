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

## 2. Equipped Cosmetic Gear & Additional Trophies (`BARBA_GEAR = $648F`)

- **Pause Menu Gear Bar (`src/arcade_spells.inc`)**: Inside the 2-column spell pause menu, pressing **Select** toggles focus between the spell grid and the bottom **Gear Bar** (`HAT`, `MASK`, `HELM` on row 14; `TIE`, `BELT` on row 16). Pressing **A** or **B** equips/toggles unlocked trophies (`$F8` heart badge), with `BARBA_GEAR` bit 7 (`$80`) marking explicit user configuration (when unset and `$648B == $57`, Waldo Hat defaults to active).
- **Friday the 13th → Hockey Mask (`$63B1 == 1`, head `2`)**: Swaps `R2` to extended CHR bank `181` (`sv_r2_mask`, white plate + dark eye/air holes + red chevrons over Barba's snout/face in `$02/$04`, `$1C`, `$20`, `$3A/$3C`) and steps `$4010` DMC rate down by 2 (`RoarSetRate6` in `src/sampled_roar.inc`) for a deeper, creepier roar.
- **Barba Man 2 → Mega Helmet (`$63B7 == 1`, head `3`)**: Draws a Palette 1 blue crest OAM sprite (`$78` non-town / `$F8` town -> `$79`/`$F9`) in `DrawExtraGear4` (`BANK4_GEAR` / `PALACE_ROAR`) and swaps Barba's palette (`$69D2 = $12`, `$69D8 = $21`) while `BLADE` (`ARCADE_ACTIVE_LO & $40`) is active.
- **Barba Kong → Red Necktie (`$63B3 == 1`, stackable bit `4`)**: Draws a necktie OAM sprite (`$7A` non-town / `$FA` town -> `$7B`/`$FB`) behind Barba's neck, flapping (`EOR #$40` + Y bob on `$12 & $04`) during jumps (`$0479 != 0`).
- **Barba's Punch-Out!! → Championship Belt (`$63BA == 1`, stackable bit `5`)**: Draws a gleaming gold-buckle belt OAM sprite (`$7C` non-town / `$FC` town -> `$7D`/`$FD`, flashing Palette 3 on `$12 & $1C == 0`) on Barba's lower torso (`+20px` standing, `+12px` crouching).

## 3. All-Screens Graphics Distribution Checklist

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
