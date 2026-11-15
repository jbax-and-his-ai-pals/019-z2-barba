# Plan: Palace 6 boss becomes "Lava Link"

The original Barba boss rises from the lava as a dragon head on a long neck and
shoots flames. Since the player is now Barba, the boss becomes Link: Link's
face and sword rise out of the lava on an absurdly long neck/body and **breathe
sword beams** instead of fire. Not implemented; this is the design and build plan.

Checkpoint for testing: **F9 "Before Palace 6 boss"** (test pack): left edge of
room `$3A`, boss not yet risen, level 8 attack/magic/life, 8 hearts, 8 magic,
all spells. Walk right to start the fight. (F6 starts mid-fight.)

## What the original boss is made of (known)

| Part | Where | Notes |
| --- | --- | --- |
| Head art | 4 KiB CHR bank 25; 32x16 head from 8x16 pairs | closed `14/16/18/1A`, half `1C/22/24/26`, open `28/2A/2C/2E` (`tools/boss_art.py`) |
| Neck segments | CHR bank 25 pairs `A0/A2` | repeated stack, which is the "neck" rising from lava |
| Behavior | enemy code `$21`, state `$0499`, timer `$0504,X` | rise, hold, shoot, descend; fight code in bank 4 |
| Attack | bank 4 `$B180..$B1BC` | fires on alternate frames inside a timer window, gets a slot via `$9BE5`, **`LDA #$04` at `$B19A` = projectile type Flame**, velocity ×4, spawns 3 px above head |
| Projectile types | chart at bank 1 `$9718` | `04` Flame, `05` Spear, `06` Boomerang, `07` Axe; graphics/hitboxes come from per-area tables in `$6EAD/$6EB6/$6EC0` |
| Palette | sprite palette 1 in that room | Barba red/orange; Link needs green/skin/brown |

## Build steps (in order, each testable on F9)

1. **Sword-beam breath (smallest win).** Change the boss projectile type at bank 4
   `$B19B` from `04` to `05` (Spear). In palaces that's the Iron Knuckle thrown
   sword: it already has a sword graphic, a hitbox, and shield deflection. That's
   effectively "Link's sword beam", and the player's Scales spell blocks it
   like Link's shield did. Check:
   - whether the spear tile exists in the Palace 6 boss CHR bank; if not, copy the
     sword pair into a free tile of bank 25;
   - whether a ×4 velocity spear looks right; it may need ×2 (remove one `ASL`
     pair, carefully, since the bytes are shared);
   - spear direction/flip by `$66,X` facing.
   Also optional: flash or recolor it to look like a beam (alternate palette per
   frame, as the player's old beam did).
2. **Link's head instead of Barba's.** Build the 32x16 boss head from **original
   Link pixels in the user's ROM** (the player CHR in the *source* ROM, before our
   build overwrites it), extracted at build time and never committed, as
   `boss_art.py` does now:
   - closed state: Link's face/cap, widened to 32 px with the cap's point
     trailing back like the dragon's horns;
   - half/open states: face plus sword arm raised, then thrust forward (the
     "mouth" that emits beams);
   - Write into bank 25 at the head pair tiles above, with guarded writes.
3. **The giant neck.** Replace pairs `A0/A2` with a 16x16 repeating segment of
   Link's green tunic, a belt band every other segment, and an optional shield
   texture. The original stacking code draws the long body, so no code change.
4. **Palette.** Patch the room's boss sprite palette to Link colors (green tunic,
   skin, brown/outline). Find the palette load for room `$3A` (search the
   world-4 palette tables, like the player-palette rewrite in `build.py`). Check
   it doesn't recolor other Palace 6 enemies sharing palette 1.
5. **Name/text.** None needed in-fight. Optional: the palace's ending crystal text.
6. **Ice Barba overlap.** The roadmap had an "Ice Barba" recolor for this fight.
   Lava Link replaces that idea. Update ROADMAP/DESIGN once agreed.

## Tests to add

- `tests/link_boss.lua` from F9: walk right, wait for the rise; assert boss code
  `$21` present, at least one projectile of type `05` spawned during a shoot
  window, none of type `04`; shield (Scales) deflects one; boss still dies to
  player fireballs and the palace completes (crystal/elevator).
- Screenshot the head at closed/open and the full neck. Review by eye.
- Run the full suite and `create_test_pack.py --force`.

## Risks

- CHR bank 25 is shared by other content (check with `tools/inspect_chr.py`
  which rooms use bank 25 and whether pairs `14..2E`, `A0/A2` appear elsewhere).
- Spear graphics may come from a CHR bank the boss room doesn't map. Fallback:
  copy the sword tile into bank 25 and point that room's type-5 tile entry at it.
- Sprite-per-line load: a wide 32 px head plus beams plus the 24 px player plus
  lava may flicker more. Measure with `tests/perf_volley.lua` style
  per-scanline counts.

Effort guess: step 1 is under an hour with a test. Steps 2–4 are a focused
session with art iteration. The art is the long pole.

## Status: Implemented

- `tools/boss_art.py` (`compile_lava_link`) builds `CHR 25` head pairs (`14/16/18/1A`, `1C/22/24/26`, `28/2A/2C/2E`), green tunic neck (`A0/A2`), and sword beam (`52`) from `roms/z2.nes` `CHR 2` Link pixels at build time.
- `tools/build.py` patches bank 4 `$B19B` (`04` -> `05` Spear/sword beam), `$AABB` (`00` -> `01` palette), and hooks `$B11F` -> `$A765` to upload Sprite Palette 1 (`18 36 2A`) via `$0302` only during the Palace 6 boss encounter.
- `tests/link_boss.lua` passes (`sp_pal1=18 36 2A`, boss `$21` spawns, projectile `$05` spawns, no `$04`, Barba fireballs damage Lava Link).

## Revision 2026-11-14 (producer feedback: fewer segments, better head)

- **Real layout (measured from OAM):** the head is one 16x16 object (`$9A/$9C/$9E` → pairs `14/16`, `1C/22`,
  `28/2A`) drawn 16 px above and about 14 px in front of the top neck piece. Neck pieces are 16x16 (`A0/A2`), one every
  16 px, with a sway table at bank 4 `$B276`; the loop is at `$B290-$B302`. The old builder's 32x16 head assumption
  was wrong: only the left 16 px ever showed, which is why the stretched face looked broken.
- **Head:** original hand-drawn 16x16 Link faces (closed, small mouth, round shout) in `tools/boss_art.py`. No ROM
  pixels. The right-hand pairs of each state carry the neck strip, since they feed the top neck piece.
  The collar sweeps back to join the neck.
- **Neck stops at the lava:** bank 4 `$B294` counts pieces down to Y `$D0` instead of `$E8`. Below `$D0` it draws one
  piece instead of skipping the loop, which keeps `$049A` (head and beam X) current while the boss emerges.
  Fully risen: 5 pieces instead of 7 (10 neck sprites instead of 14). The button-down neck art is unchanged.
- `tests/link_boss.lua` now checks the neck has 1-5 pieces at the first beam and logs palette-1 OAM.

## Producer direction (2026-11-14)

Keep this fight as Barba's pattern wearing Link (rise, sword beams, sink). Beams at every health level, no weakening
phase, difficulty not a goal. Next: experiment with a shield mechanic, and play Link's hurt sound when Lava Link is hit.
