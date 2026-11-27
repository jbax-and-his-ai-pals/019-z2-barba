# Instant playtesting checkpoints

## Experimental Waldo portal

Build the combined ROM with `python tools/build.py` using the US dump at
`roms/waldo.nes` and the other [build inputs](BUILD.md). The output uses
NES 2.0 Mapper 176. In Rauru, press **Up** at the portal door and dismiss the
message with **B**. Play through the Moon landing or press **Start + Select**
(Enter and Space) to wave out of Waldo and wave back into Rauru. Barba resumes
at the same position and scroll. Press **B** to dismiss the return message.

For a 10-slot F1–F10 save-state pack **inside Waldo inside Zelda II** on the
combined `barba.nes`, double-click **play/cmd/Test Wheres Barba in Z2.cmd**
(or run `python tools/create_waldo_z2_pack.py --force`): F1–F8 cover Title Screen,
Moon Ticket, Overworld Map, Train Station, **Before Level 5: The Subway** (**F5**),
The Castle, and the two Slots stages (`slots-two-barbas` and `slots-jackpot`);
**F9** (`moon-ending`, ~27 s before return) and **F10** (`moon-return`, ~1 s
before return) let you test the automatic wavy transition back to Rauru in Zelda II.
**Start + Select** works from any slot. Try **F4** (Train Station), watch the
station wave out and Rauru wave in, then dismiss the return message with **B**.

For the default Barba silhouette, launch **play/Play Barba.cmd** and look at the
dragon on the title cliff. Start a file to see the same elbow, horizontal
torso and flicking tail in North Palace, or use **play/cmd/Test Core.cmd**, **F1**.
In **play/cmd/Test Tricky Movement.cmd**, load **F7** and walk right into
the Palace 6 shaft. Watch for three inverted torso sections and a tapered
tip above the downward-facing head as Barba and his shadow fall. Listen for
the music to cut as the shaft animation starts. Barba roars once, and the
palace theme starts in the lower room.

For the palace victory roar, double-click **play/cmd/Test Gem Celebration.cmd**
and press **F1**. Barba starts beside the Palace 6 crystal statue, past the boss,
with the final gem still unplaced. Walk right: the native gem sequence plays its
fanfare, immediately followed by the roar with Barba looking up. Watch the
floor brighten in pairs moving away from the statue and two patches of raised
stonework light in sequence. Press F1 again to repeat. This uses its own
isolated `gem` profile and leaves Core F9 intact.
`tests/gem_checkpoint.lua` reloads this checkpoint and verifies placement,
fanfare, exactly one roar, raised head during playback and automatic pose release.
Prepare without opening Mesen: `./tools/launch.ps1 -TestPack -CheckpointSet gem -PrepareOnly`.

To playtest the Lava Link entrance, load **Test Bosses F6** or **Test Core F9**
and jump right off the lava. Keep holding Right when the camera locks. Barba
stops horizontally at the center of the middle stone platform, a little to the
right of screen center. The jump continues vertically at its usual speed.
Barba lands and holds still for a brief beat before roaring. The HUD, Barba and
the room shake side to side together throughout the roar. Then the screen
settles for half a second while Barba holds position. When Lava Link rises,
Barba regains movement and the boss theme starts. Later rises follow his
regular attack cycle.
`tests/link_boss.lua` checks the entrance and `tests/palace_roar.lua` checks the
floor pulse in all six crystal rooms.

For game-over checks, double-click **play/cmd/Test Edge Scenarios.cmd**.
It rebuilds the ROM as needed and installs a separate `edges` test profile:

| Key | Checkpoint | What to test |
| --- | --- | --- |
| F1 | Last life, one hit from death | Palace 1 combat corridor, one life, one health unit and a nearby enemy. Leave the controls alone to reach GAME OVER in about four seconds. |
| F2 | Game Over portrait | Inspect black Link immediately. Press Start to continue; reload F2 to inspect again. |

The edge pack is regenerated for each ROM/recipe version. Generation reloads
both states, verifies natural enemy death from F1, and checks that F2 continues
to gameplay with three lives. Normal play saves and other checkpoint sets are
isolated. Generated files are in `build/test-pack/<ROM hash>/edges/`.
To prepare without opening an emulator:
`powershell -File tools/launch.ps1 -TestPack -CheckpointSet edges -PrepareOnly`.

On Windows, double-click **play/cmd/Test Core.cmd**, or run:

```powershell
./tools/launch.ps1 -TestPack
```

The launcher rebuilds the ROM, generates its checkpoints if needed, and opens
a separate Mesen test profile. When using a previously built ROM, run
`./tools/launch.ps1 -NoRebuild -TestPack` and add `-CheckpointSet <set>` for a
specific set. Press one of
these keys once the game appears; you do not need to start a file or play the intro.
Press the same key again at any time to restart that test and refill its meters.

| Key | Checkpoint | What to try |
| --- | --- | --- |
| F1 | Starting castle | Normal starting stats. Walk, turn, crouch, jump and attack. |
| F2 | Palace 1 combat corridor | Fight in both directions and try the five-shot volley at different health levels. |
| F3 | All 18 spells and techniques | Safe castle, full health/magic, all 18 spells (8 Hyrule + 10 Arcade) and both thrusts. Press Enter to browse both columns or Space to cast Inferno. Reload F3 to refill or leave the flying form. |
| F4 | Palace 6 lava ledge | Walk right into the lava, stop, move, jump and return. |
| F5 | Standing on lava | Already on the lava surface. Check for sinking and test jumps immediately. |
| F6 | Palace 6 boss encounter | Test the playable dragon against Lava Link in Palace 6. |
| F7 | Sea crossing in progress | Watch the dragon complete the normal raft route to East Hyrule. Reload F7 to repeat. |
| F8 | Rauru town street | Approach random outdoor wanderers, watch them flee, and test fireballs and town scorch/combo. |
| F9 | Before Palace 6 boss | Left edge of the boss room with level 8 attack/magic/life, all spells and full meters. Walk right to start the fight against Lava Link. |
| F10 | Great Palace approach | Great Palace room $35 corridor before Thunderbird and Dark Barba with max stats, all spells and full meters. Test `INFERNO`, the final battles, and ending progression. |

The checkpoint launchers open Mesen at 4× windowed scale. The arrows move,
**X** jumps, **Z** attacks, **Enter** starts/pauses, and **Space** is Select/cast.
State-load keys work independently of the game menu.
The upgraded states have nine lives, eight heart/magic containers, level 4 attack,
level 8 magic/life, all spells, both thrusts and traversal items. Damage and magic
consumption work normally: no invulnerability or unlimited-magic cheat runs.

## Isolation and compatibility

- Normal play saves and settings in `.tools/mesen-play/` are not modified.
- Test profiles are `build/mesen-scenarios/<set>/` (the shared `.tools/` is read-only). It does not reuse a running
  normal-play Mesen window.
- Test battery saves and states live under `build/test-pack/<ROM hash>/<set>/`.
  Generated master `.mss` files stay separate from the disposable F1-F10 slots.
- Launching the test pack restores the selected set's slots from their masters. Use
  **Save State to File** if you want to keep your own additional test checkpoint.
- Each pack records its exact ROM SHA-256. After a code/art change, the launcher
  creates a new pack for that build. Old states should not be mixed with a new ROM.
- These are constructed test fixtures, not an authentic completed-game save.
  Room entry and upgrades are injected during generation; ordinary game logic
  controls the resulting scene, enemies, damage, physics and crossing.
- All states are reloaded and checked in Mesen 2.1.1 before being marked
  ready. Screenshots, capture logs and reload validation remain alongside them.
- No state files, screenshots or test ROMs are committed to the public repository.

To regenerate manually against `build/barba.nes`, run
`python tools/create_test_pack.py --force`. Pass `--rom play/barba.nes` to
select an existing artifact explicitly.
To prepare everything without opening another window:
`./tools/launch.ps1 -TestPack -PrepareOnly`.

The first version's upgraded checkpoints had a stale next-level XP target and
could loop in the upgrade menu after a small XP gain. Corrected states recompute
that target from the ROM's level tables. Reload a freshly installed F2-F7 slot
to replace an old in-memory checkpoint; this fix does not change normal saves.

The town checkpoint now uses Rauru's normal street room rather than its
lookalike entrance copy. Load the newly prepared F8 state; old snapshots can
retain fake door tiles made by the retired villager animation.

## Busy Areas checkpoints

Open **play/cmd/Test Busy Areas.cmd** and press F1–F10 in Mesen. The set
combines rooms with high frame cost or heavy sprite overlap in the busy-room
probe with three Palace 5 Mago rooms for the red-duplicate playtest.

| Key | Checkpoint | What to try |
| --- | --- | --- |
| F1 | Palace 5 room 62, two Magos | Alternate upstab and downstab, then let a shot hit Barba in midair. |
| F2 | Palace 5 room 48, Mago and statue hall | Fight through the statues while the Mago teleports. |
| F3 | Palace 5 room 44, first Mago room | Watch the Mago appear, fire and vanish while Barba jumps. |
| F4 | Palace 5 before Gooma | Turn and fire with the Ironknuckles on screen. |
| F5 | Palace 2 crowded floor corridor | Jump and fire volleys through the crowd while watching the HUD. |
| F6 | Palace 3 Ironknuckles and breakable blocks | Start on the lower lane. Move right and breathe into the blocks. |
| F7 | Palace 6 Wizzrobe hall | Fight the Wizzrobe with other enemies and shots on screen. |
| F8 | Palace 1 before Horsehead | Fire through the enemy groups in the approach corridor. |
| F9 | Old Kasuto monster street | Turn and breathe through the Moas. Let one hit Barba in midair. |
| F10 | Rauru street crowd | Breathe through the crowd and watch panic, shout and scorch effects. |

Each load restores the room and loadout. Palace 5 has both thrust techniques.
On F1–F3, watch for dragon art away from Barba during the normal hurt flash.
To regenerate the set, run `python tools/create_test_pack.py --set busy --force`.
To repeat the automated stress run, use `python tools/busy_rooms.py --sets busy --frames 620`.

### Verified limits & placement

All 69 checkpoints across all sets are reload-validated and pass usy_rooms.py
with **0 lag, 0 late splits, and 0 HUD shifts** (old-kasuto 28,247 NMI max,
p2-crowded-floor 27,871, p5-gooma-approach 26,766, p3-ironknuckle-blocks 24,023).
Scanlines exceed 8 sprites in Rauru, Old Kasuto (max 14), and Gooma approach,
handled by odd-frame OAM priority rotation. For historical profiling logs, see
[CHANGELOG.md](archive/CHANGELOG.md#historical-busy-areas--placement-profiles-2026-11-17).

## Playthrough checkpoint sets

Core remains the default. Use **Test All Spells.cmd**, **Test Palaces.cmd**, **Test Endgame.cmd**, **Test Bosses.cmd**,
**Test Towns and World.cmd**, **Test Tricky Movement.cmd**, and the arcade/standalone launchers in `play/cmd/` (beside
`Test Core.cmd`).
Each opens its own isolated local profile and maps that set to F1-F10.
Unused F-keys do not point at another set's states. Script equivalent:

```powershell
./tools/launch.ps1 -TestPack -CheckpointSet palaces -PrepareOnly
```

Use `core`, `items`, `palaces`, `endgame`, `bosses`, `world`, `gem`, `busy`,
`movement`, `spells`, `fireballs`, `ngplus`, or `edges` as the set name. `python tools/create_test_pack.py --force`
generates and validates all standard sets from an existing ROM, then
leaves Core selected. Add `--set spells` to regenerate just one set.

### Assumed normal route (not a completed-game save)

Rauru/Scales -> Palace 1/Candle -> trophy/Ruto/Jump -> Saria/Life/mirror/Bagu ->
Death Mountain/Hammer -> Palace 2/Glove -> medicine/Mido/Fairy/Downward Thrust ->
Palace 3/Raft -> Nabooru/Fire -> rescue child/Darunia/Reflect/Upward Thrust ->
Maze Island/Palace 4/Boots -> Palace 5/Flute -> New Kasuto/Spell/Magic Key ->
Palace 6/Cross -> Old Kasuto/Inferno (Thunder) -> return to Palace 6 boss -> Great Palace.
This chooses the valid Hammer-before-Palace-2 detour; levels are explicit reasonable
route assumptions, not universal XP totals. Collect optional containers en route:
4/4 initially, 5/5 before Palace 2, 6/6 in the east, 8 magic/7 hearts before Palace 6,
and the final heart before Great Palace. New town checkpoints are **after** learning
their spell; palace entrances are **before** collecting that palace's item; pre-boss
checkpoints have it. The Palace 6 boss approach includes the Cross/Old Kasuto detour.

Every new checkpoint starts with three lives, zero XP, zero spare keys (the route
has spent its preceding keys), full native meters (containers * 32 - 1, per $CB18), and no active spell/cheat. The Magic Key
is present only after New Kasuto. Ordinary enemies can damage you before capture;
Old Kasuto may therefore begin below full health. Item/quest flags are injected once,
not replenished every frame. Room objects and enemy/item spawn history remain native
fresh-room data: these are progression fixtures, **not** claimed authentic battery saves.

### Loadout codes

A/M/L = attack/magic/life levels. M/H = magic/heart container counts.
Spells are the first N native spells in order: Scales, Jump, Life, Wyrmlng (Fairy),
Meteor (Fire), Reflect, Spell, Inferno (Thunder). D = Downward Thrust, U = Upward Thrust.
Quest flags: T trophy ($0798=$10), R mirror ($0799=$01), B Bagu ($079A bit $08),
M medicine ($079A bit $40), W water ($079B=$01), C rescued child ($079C=$20),
7 seven-container quest ($079D=$08). Unlisted quest bytes are zero.
Crystals are $078D-$0792, in palace order; $0794 is 6 minus placed. Keys $0793=0.

| Code | A/M/L | M/H | Spells | Items | Tech | Placed | Quest flags |
| --- | --- | --- | --- | --- | --- | --- | --- |
| p1 | 2/2/2 | 4/4 | 1 | none | none | 0 | none |
| p1boss | 3/2/3 | 4/4 | 1 | Candle | none | 0 | none |
| p2 | 3/3/3 | 5/5 | 3 | Candle, Hammer | none | 1 | T |
| p2boss | 4/3/4 | 5/5 | 3 | Candle, Glove, Hammer | none | 1 | T |
| p3 | 4/4/4 | 5/5 | 4 | Candle, Glove, Hammer | D | 2 | T, R, B, M |
| p3boss | 5/4/4 | 5/5 | 4 | Candle, Glove, Raft, Hammer | D | 2 | T, R, B, M |
| p4 | 5/5/5 | 6/6 | 6 | Candle, Glove, Raft, Hammer | D+U | 3 | T, R, B, M, W, C |
| p4boss | 7/5/5 | 6/6 | 6 | Candle, Glove, Raft, Boots, Hammer | D+U | 3 | T, R, B, M, W, C |
| p5 | 6/5/6 | 6/6 | 6 | Candle, Glove, Raft, Boots, Hammer | D+U | 4 | T, R, B, M, W, C |
| p5boss | 6/6/6 | 6/6 | 6 | Candle, Glove, Raft, Boots, Flute, Hammer | D+U | 4 | T, R, B, M, W, C |
| p6 | 7/6/7 | 8/7 | 7 | Candle, Glove, Raft, Boots, Flute, Hammer, Magic Key | D+U | 5 | T, R, B, M, W, C, 7 |
| p6boss | 7/7/7 | 8/7 | 8 | Candle, Glove, Raft, Boots, Flute, Cross, Hammer, Magic Key | D+U | 5 | T, R, B, M, W, C, 7 |
| gp | 8/7/8 | 8/8 | 8 | Candle, Glove, Raft, Boots, Flute, Cross, Hammer, Magic Key | D+U | 6 | T, R, B, M, W, C, 7 |
| start | 1/1/1 | 4/4 | 1 | none | none | 0 | none |
| ruto | 3/2/3 | 5/5 | 2 | Candle | none | 1 | T |
| saria | 3/3/3 | 5/5 | 3 | Candle | none | 1 | T, R, B |
| mido | 4/4/4 | 5/5 | 4 | Candle, Glove, Hammer | none | 2 | T, R, B, M |
| darunia | 5/5/5 | 6/6 | 6 | Candle, Glove, Raft, Hammer | D | 3 | T, R, B, M, W, C |
| nabooru | 5/4/5 | 6/6 | 5 | Candle, Glove, Raft, Hammer | D | 3 | T, R, B, M, W |
| all_spells | 7/8/8 | 8/8 | 8 (+10 Arcade) | Candle, Glove, Raft, Boots, Flute, Cross, Hammer, Magic Key | D+U | 4 | T, R, B, M, W |
| ngplus | 7/8/8 | 8/8 | 8 (+10 Arcade) | none (Flute in `ngplus_flute`) | D+U | 0 | none (`$07A0=1`) |

### ngplus

Launch **play/cmd/Test NG+.cmd** (`./tools/launch.ps1 -NoRebuild -TestPack -CheckpointSet ngplus`) for 8 New Game+ (`$07A0=1`) checkpoints (F1–F8):

| Key | Where | Focus |
| --- | --- | --- |
| F1 | West Hyrule NG+ overworld | Walk to any Mountain tile and press **B** to melt it into Desert (`$04`). |
| F2 | Death Mountain NG+ (with Flute) | Holds the Flute (`$0789=1`); face a Mountain tile and press **B** to verify mountain melting works even with the Flute. |
| F3 | Maze Island NG+ overworld | NG+ overworld mountain melting and East Hyrule routing. |
| F4 | Rauru town street (NG+) | Townsfolk, fireballs, and all 18 spells in NG+. |
| F5 | Palace 1 entrance (NG+) | Early palace with carried-over NG+ spells, levels, and techniques. |
| F6 | Palace 6 lava ledge (NG+) | Lava traversal, fireballs, and `WYRMLNG` in NG+. |
| F7 | Before Lava Link (NG+) | Jump right across the lava to trigger the Palace 6 boss fight. |
| F8 | Before Dark Barba (NG+) | Defeat Dark Barba to test the NG+ ending loop. |

### fireballs

Launch **play/cmd/Test Fireballs.cmd** (`./tools/launch.ps1 -NoRebuild -TestPack -CheckpointSet fireballs`) for 10 fireball-focused checkpoints (F1–F10) covering dark/lit caves, big ledges and bridges, elevated wall targets, breakable blocks, Ironknuckle rebounds, low ceilings, and crowded corridors:

| Key | Where | Focus |
| --- | --- | --- |
| F1 | West Hyrule dark grotto (no Candle) | Fireball glow halos, firelight palette flicker, and shots across the collapsing bridge. |
| F2 | West Hyrule Myu cave | Crouching fireballs, `METEOR` floor waves, and `BLADE` / `LOCK` in a lit cave. |
| F3 | West Hyrule water bridge | Full 124 px horizontal fireball range, 5-shot volley cadence, and `Up+B` upward shots. |
| F4 | Palace 6 lava ledge | Long-range fireballs across a wide lava gap, jumping shots, and `BLADE` 8-way steering. |
| F5 | Palace 6 drop-shaft high ledge | Long fireball trajectories from height and firing while falling. |
| F6 | Valley of Death wall ledges | `Up+B` upward-angled fireballs and `LOCK` homing shots against elevated Rock Lizalfos. |
| F7 | Palace 3 Ironknuckles & blocks | Glove block-breaking with fireballs, Ironknuckle shield rebound, and `HEAVY` / `AXE`. |
| F8 | Palace 1 low tunnel | Crouched vs. tucked-head fireball mouth height under a 32 px ceiling. |
| F9 | Palace 2 crowded corridor | 5-shot volley load governor and multi-target fireball hits. |
| F10 | Great Palace approach | Full volleys, `INFERNO`, `METEOR`, and `HEAVY` against late-game enemies. |

### spells

Launch **play/cmd/Test All Spells.cmd** (`./tools/launch.ps1 -NoRebuild -TestPack -CheckpointSet spells`) for 10 tailored rooms (F1–F10) with all 18 spells (8 Hyrule + 10 Arcade), all 8 key items, and Magic-8/Life-8 meters. Each slot pre-selects a fitting spell (press **Space** to cast immediately, or **Enter** to pick another):

| Key | Where | Pre-selected | Look for |
| --- | --- | --- | --- |
| F1 | Palace 2 Green Palace (world 3, room $14, entry 1) | `BARREL` | Inspect the 2-column pause menu over green bricks, or cast `BARREL`, `BLADE`, `STAR`, or `METEOR` down the crowded corridor. |
| F2 | Palace 3 Ironknuckles (world 4, room $0D, entry 1) | `HEAVY` | Test `HEAVY` (2× damage + shield bypass), `AXE`, `DECOY`, or `BLADE` against Ironknuckles and breakable blocks. |
| F3 | Palace 6 lava ledge (world 4, room $33, entry 0) | `WYRMLNG` | Cast `WYRMLNG` to fly over the lava, or `JUMP` to leap the gap. |
| F4 | Palace 5 two-Mago room (world 3, room $3E, entry 0) | `CLOCK` | Freeze both teleporting Magos with `CLOCK`, or switch to `LOCK` for homing fireballs. |
| F5 | Carock boss room (world 4, room $1C, entry 0) | `REFLECT` | Cast `REFLECT` and walk right to bounce Carock's bolts back, or test `SCALES` / `HEAVY`. |
| F6 | Palace 6 Wizzrobe hall (world 4, room $3C, entry 1) | `LOCK` | Track the phasing Wizzrobe with `LOCK`, or cast `DOUBLE` for 2× XP. |
| F7 | Old Kasuto Moa street (world 2, room $15, entry 1) | `INFERNO` | Clear the swarming Moas with `INFERNO`, or test `STAR`, `AXE`, `DOUBLE`, and `LUCKY`. |
| F8 | Palace 1 low-HP approach (world 3, room $0C, entry 0) | `LIFE` | Starts at low health (~2.5 hearts): cast `LIFE` to heal, or test `SCALES` and `LUCKY` ahead. |
| F9 | Great Palace Thunderbird (world 5, room $35, entry 0) | `METEOR` | Cast `METEOR` and walk right to fight Thunderbird, or test `INFERNO`, `AXE`, and `SPELL`. |
| F10 | Rauru town street (world 1, room $00, entry 1) | `DECOY` | Cast `DECOY` in town, `JUMP` onto roofs, or test `SPELL`, `METEOR`, and `INFERNO` around villagers. |

### palaces

Stand still at F1, F3, or F5 to see the western entrance clouds drift right to left.
At F7 on Maze Island and F9 at Palace 5, they drift left to right. Walk toward
the facade to see the clouds scroll more slowly than the building.

| Key | Where | Loadout | Look for |
| --- | --- | --- | --- |
| F1 | Palace 1 entrance (world 3, room $00, entry 0) | p1; keys 0 | Check movement, head clearance, combat and HUD. |
| F2 | Before Horsehead (world 3, room $0C, entry 0) | p1boss; keys 0 | Check movement, head clearance, combat and HUD. |
| F3 | Palace 2 entrance (world 3, room $0E, entry 0) | p2; keys 0 | Check movement, head clearance, combat and HUD. |
| F4 | Before Helmethead (world 3, room $21, entry 0) | p2boss; keys 0 | Check movement, head clearance, combat and HUD. |
| F5 | Palace 3 entrance (world 4, room $00, entry 0) | p3; keys 0 | Check movement, head clearance, combat and HUD. |
| F6 | Before Rebonack (world 4, room $0D, entry 0) | p3boss; keys 0 | Check movement, head clearance, combat and HUD. |
| F7 | Palace 4 entrance (world 4, room $0F, entry 0) | p4; keys 0 | Check movement, head clearance, combat and HUD. |
| F8 | Before Carock (world 4, room $1B, entry 0) | p4boss; keys 0 | Check movement, head clearance, combat and HUD. |
| F9 | Palace 5 entrance (world 3, room $23, entry 0) | p5; keys 0 | Check movement, head clearance, combat and HUD. |
| F10 | Before Gooma (world 3, room $28, entry 1) | p5boss; keys 0 | Check movement, head clearance, combat and HUD. |

### endgame

At F1 and F2, the clouds at Palace 6 and Great Palace drift left to right.

| Key | Where | Loadout | Look for |
| --- | --- | --- | --- |
| F1 | Palace 6 entrance (world 4, room $24, entry 0) | p6; keys 0 | Check movement, head clearance, combat and HUD. |
| F2 | Great Palace entrance (world 5, room $00, entry 0) | gp; keys 0 | Check movement, head clearance, combat and HUD. |
| F3 | Great Palace elevator (world 5, room $01, entry 0, x=112, y=160) | gp; keys 0 | Start on the native elevator. Hold Down to descend; Up to return. |
| F4 | Great Palace low tunnel (world 5, room $2C, entry 0, x=64, y=176) | gp; keys 0 | Hold Down in the 32-pixel-high lane. Check the full head and the horizontal pieces above the bricks. |
| F5 | Before Thunderbird (world 5, room $35, entry 0) | gp; keys 0 | Check movement, head clearance, combat and HUD. |
| F6 | Before Dark Barba (world 5, room $36, entry 0) | gp; keys 0 | Defeat Dark Barba and watch the ending. As the curtain drops, look for the bright fireball with a flickering tail traveling down and right into Zelda, then disappearing as she turns to ash. |
| F7 | Palace 6 boss and crystal approach (world 4, room $3A, entry 0) | p6boss; keys 0 | Walk right to Lava Link; win normally and approach the crystal statue. |
| F8 | Valley of Death rock throwers (East Hyrule, world 0, room $02) | gp; keys 0 | Walk left toward the wall Lizalfos. Face it, jump and press Up+B while it leans out to throw. |
| F9 | East Hyrule grass encounter (world 0, room $22, random battle entry) | gp; keys 0 | Walk right while firing, then turn back before the exit. Check that the ground scrolls steadily and the clouds stay whole. Stand still to see them drift right. |

### bosses

Every boss in order, one key each. Each starts at the left edge of the boss room
itself (no door to walk through) with that boss's pre-boss loadout. Reload the key to retry.

| Key | Boss | Room | Loadout |
| --- | --- | --- | --- |
| F1 | Horsehead (Palace 1) | world 3, room $0D, page 0 | p1boss |
| F2 | Helmethead (Palace 2) | world 3, room $22, page 0 | p2boss |
| F3 | Rebonack (Palace 3) | world 4, room $0E, page 0 | p3boss |
| F4 | Carock (Palace 4) | world 4, room $1C, page 0 | p4boss, Attack 7 with Reflect learned |
| F5 | Gooma (Palace 5) | world 3, room $29, page 0 | p5boss |
| F6 | Lava Link (Palace 6) | world 4, room $3A, page 0 | p6boss |
| F7 | Thunderbird (Great Palace) | world 5, room $35, page 0 | gp |
| F8 | Dark Barba (Great Palace) | world 5, room $36, page 1 | gp |

Rooms match the boss scenarios in tests/ (horsehead.lua ... dark_link.lua). Dark Link's
intro freezes the player for ~340 frames, so F8 is captured at 590 frames, just as control
returns: the fight is already live. F9/F10 are unused.

Watch the eight-pip meter at the left edge while jumping and firing. Red pips turn
white as the boss takes damage. In F3, the meter follows the knight after he is
unhorsed. In F4, it stays visible while Carock teleports. In F6, it appears as Lava
Link starts to rise after the entrance roar and pause. In F7, cast INFERNO to make
Thunderbird vulnerable. The meter clears on defeat.

With a current Bosses pack, run `python tools/emulator_test.py tests/boss_meter.lua`
to check the pips in hardware OAM and on screen during all eight fights.

### world

| Key | Where | Loadout | Look for |
| --- | --- | --- | --- |
| F1 | Rauru street (world 1, room $00, entry 1) | start; keys 0 | Check outdoor NPCs, doorways, palette and head clearance. |
| F2 | Ruto street (world 1, room $03, entry 1) | ruto; keys 0 | Check outdoor NPCs, doorways, palette and head clearance. |
| F3 | Saria street (world 1, room $06, entry 1) | saria; keys 0 | Check outdoor NPCs, doorways, palette and head clearance. |
| F4 | Mido street (world 1, room $09, entry 1) | mido; keys 0 | Find the knight and talk to him for the first downstab lesson. |
| F5 | Nabooru street (world 2, room $0C, entry 1) | nabooru; keys 0 | Check outdoor NPCs, doorways, palette and head clearance. |
| F6 | Darunia street (world 2, room $0F, entry 1) | darunia; keys 0 | Find the knight and talk to him for the first upstab lesson. |
| F7 | New Kasuto street (world 2, room $12, entry 1) | p6; keys 0 | Check outdoor NPCs, doorways, palette and head clearance. |
| F8 | Old Kasuto street (world 2, room $15, entry 1) | p6boss; keys 0 | Check outdoor NPCs, doorways, palette and head clearance. |
| F9 | Death Mountain entrance (overworld DM) | saria; keys 0 | Walk the native overworld; enter nearby caves or Palace 4. |
| F10 | Maze Island near Palace 4 (overworld Maze) | p4; keys 0 | Walk the native overworld; enter nearby caves or Palace 4. |

For the Darunia exit check, load F6 and leave town to the left. Enter the nearby
forced encounter with rising bubbles (East Hyrule, room `$06`). Leave through the
right exit, re-enter from that side, and walk left toward the nearest water.
Turn back and jump and downstab as you approach the right exit. Barba should
return to the East Hyrule overworld and the bubbles should keep spawning until
she leaves.

The automated check loads F6, walks out of town, and selects that native
encounter entry directly on the overworld. It verifies the first exit and the
return trip with the bubble generator active. Generate the world pack and use
the folder printed by the first command to locate its ROM.

```text
python tools/create_test_pack.py --set world
python tools/emulator_test.py tests/darunia_exit.lua --rom "<world pack folder>/barba-test.nes"
```

### movement

Load F5 or F10 and stand still to see West Hyrule's clouds drift from right to left.
For the reverse drift, load F8 in the Endgame pack and pause at the Valley of Death encounter.

| Key | Where | Loadout | Look for |
| --- | --- | --- | --- |
| F1 | Palace 6 lava ledge (world 4, room $33, entry 0) | p6boss; keys 0 | Walk onto lava, jump back, check native body and folded head. |
| F2 | Palace 1 low tunnel (world 3, room $03, entry 0, x=112, y=176) | p1boss; keys 0 | Crouch immediately and watch where the horizontal pieces meet the brick floor. |
| F3 | Palace 1 elevator shaft (world 3, room $01, entry 0, x=112, y=160) | p1; keys 0 | Start on the native elevator. Hold Down to descend; Up to return. |
| F4 | Palace 2 floor corridor (world 3, room $14, entry 1) | p2boss; keys 0 | Inspect floor and jump clearance. |
| F5 | West Hyrule water bridge (world 0, room $01, native right-hand entry) | saria; keys 0 | Walk left and compare cloud motion with the bridge. Watch the water shimmer below the deck. |
| F6 | Medicine cave collapsing bridge (world 0, room $0E, native left-hand entry) | p3; keys 0 | Cross the collapsing bridge and watch the liquid below it shimmer against the stationary cave walls. |
| F7 | Palace 6 drop-shaft edge (world 4, room $28, entry 1, x=300, y=176) | p6boss; keys 0 | Stand safely at the gap; jump across or fall to the lower room. This is not a lethal bottomless pit. |
| F8 | Palace 2 breakable blocks (world 3, room $1A, entry 1) | p2boss; keys 0 | Turn left and shoot through the 2x3 breakable block wall with the Glove. |
| F9 | West Hyrule Myu cave (world 0, room $10, entry 0) | ruto; keys 0 | Watch the Myu to the right through both crawl frames, then crouch nearby. |
| F10 | West Hyrule grass encounter (world 0, room $22, random battle entry) | saria; keys 0 | Watch the sprig tips sway into steady roots. Walk right, turn back, and pause to check for a one-frame jump between the clouds and the grass. |

### Evidence, omissions and limits

Room sources: read-only z2disassembly/src/prg4.asm area-pointer and connectivity
tables ($8523/$871B for palaces 1/2/5, $A000/$A1F8 for 3/4/6), prg5.asm
($8523/$871B for Great Palace), prg3.asm town pointers, and prg1/prg2 overworld
key-area tables. Loadout field meanings come from z2disassembly/ram-map.txt.
The checked-in tools/checkpoint_sets.json is the shared source for generation,
manifest descriptions and reload assertions; Core retains its original scene order.

The Thunderbird and Dark Barba checkpoints start on safe approaches before the fights activate.
Crystal placement and ending snapshots are omitted: no controller-driven boss defeat
and ending capture was established, and writing boss-death/cutscene state would fake
those milestones. The Palace 6 boss approach lets the producer pursue its crystal normally.
The two elevator states now start on the native platform (object $13, $0754=$10),
not in a corridor. One-time position edits at frame 80 are fixture entry placement,
not ongoing cheats. Reload validation rides down and up (Y 160 -> 178 -> 160).

**Lethal bottomless pit remains unverified.** Movement F7 is explicitly a native
Palace 6 drop-shaft, not the requested lethal pit: room $28 drops into $2D with
three lives unchanged. Its adjacent columns have no floor ($40 at Y 176/192;
native collision returns $40 below Y 208), but falling does not kill. Surveyed
palace gaps were floor transitions or shafts; lava/water are different hazards.
No death flag, collision tile, or game code was changed to fabricate a lethal pit.
A qualifying native lethal-pit location is still needed for that acceptance item.
Endgame has nine checkpoints and Movement has ten.

### Checkpoint exit investigation (November 19, 2026)

All ten packs for ROM `e2a1410f459e` passed their existing reload checks. A
separate Mesen input sweep tried left and right from 67 side-view states. It
reached 35 adjacent rooms and 34 overworld returns, recorded three life losses,
and reached the 620-frame limit on 62 attempts. Some routes require elevators,
jumps, combat, or other inputs beyond that sweep. It stopped at the first room
or overworld boundary and did not reproduce a CPU halt. The pack's regular
validation usually exercises short movement within the starting room.

All ten packs were also regenerated and passed reload checks on the play ROM
`46657414e2ee`. Focused runs repeated the Rauru, New Kasuto, Palace 4, and
both grass encounter results on that ROM.

| Checkpoint | Observed result | Native state to seed |
| --- | --- | --- |
| Core F8, Rauru | Right exit returned to the starting castle at West Hyrule `($17,$34)`. Setting `$0748=$2C` in the loaded state returned to Rauru at `($32,$58)` on the same walk. | Core's older setup inherits `$0748=$00` from the castle. It needs the native area ID for each town or palace. The Core palace fixtures also inherit `$00`, so their full exit routes still need tests. |
| Towns and World F7, New Kasuto | Left exit returned to East Hyrule `($00,$66)`. Setting `$0748=$31` returned to New Kasuto at `($3D,$51)`. | The generic town formula produces `$30`. The game uses `$31` for the hidden town. Re-entry still needs a test that exercises the town reveal. |
| Palaces F7, Palace 4 | Left exit selected overworld PRG bank 1. Setting `$070A=$02` selected bank 2. Both returned to `($3C,$3A)` and the region-1 map bytes match across the two banks. | The native loader uses `$070A` to distinguish the west-side and east-side routes through region 1. The Towns and World Maze Island checkpoint already sets it to East Hyrule. Follow-on routing from Palace 4 remains unverified. |
| Tricky Movement F10 and Endgame F9, grass encounters | Both exits used random encounter slot `$3E`. West returned to `($00,$20)` and East to `($00,$66)`. | The game derived slot `$3E` from the synthetic overworld coordinates. Each fixture needs a verified walkable grass origin in its own region. |
| Towns and World F2, Ruto | From directly seeded room `$03`, the right exit used unused West Hyrule entry `$2E` and returned to `($00,$66)`. Starting through the native area loader at entry `$2F` opened room `$05`. The tested left route passed through `$04`, and both routes returned to `($02,$24)`. | Preserve the native connector rooms and their exit directions. The area's normalized ID is already `$2E` on the native route, so correcting only that byte would miss the difference. |

The native area loader also chooses distinct Rauru entrance rooms. Entry
`$2C` from the overworld loads room `$3C`; entry `$2D` loads room `$02`.
The existing Core F8 starts in room `$00`. Setting its area ID corrects the
tested exit, and a full round trip still needs to exercise the connector.

Inventory and item history also diverge. Picking up the Candle with controller
input in Key Items F1 sets inventory `$0785` to 1 and changes Palace 1 room
`$08` item presence at `$0684` from `$FD` to `$7D`. Palaces F2 starts with
`$0785=1` and still has `$0684=$FD`. The game keeps this per-room history
separately from inventory, spells, quests, crystals, and loose keys. Progression
fixtures should record pickups and unlocked doors that the chosen route has
already passed. Interaction fixtures such as Key Items F1 need an explicit
pre-pickup state.

The Darunia F6 regression still passes with ROM `c3bac750d883`. With
`e2a1410f459e` and `46657414e2ee`, the first crossing exits alive to the expected East Hyrule
`($0A,$24)` with three lives, but X is `$3EF` and the test requires at least
`$3F0`. A diagnostic run that accepted that position and allowed more time
also completed the second return with the generator active on `e2a1410f459e`.
It missed the downstab, so the original crash trigger remains unverified.

Start the generator repair with native overworld area IDs and explicit encounter
origins. Load through the native overworld and area-entry routines where
possible, then place Barba in the desired room. For the repaired checkpoints,
validate the first adjacent room or overworld destination and a live re-entry
with controller input. Keep route-dependent pickup, door, and quest history
with each profile. When tracking an opcode report, record the ROM hash, F-key,
input sequence, PC and opcode at the failure, and the source and destination
world, region, and room.

To reproduce the current exits, open Core F8 and walk right, then open Towns
and World F7 and walk left. Both should reach the overworld and show the wrong
destinations listed above. The Palace 4 difference is visible in Mesen's
debugger through `$0769` after walking left from Palaces F7.

### Numeric feature and palette checks

Generation and reload share tests/checkpoint_features.lua: elevator object and
player Y attachment; stone above the raised head, clear body lane and grounded
floor; open-bottom gap beside a supported player. Controller and 120-frame checks
still apply. Movement F7 additionally checks the complete fall pose for both
actors, arrival in room `$2D` and unchanged lives. Endgame F4 is GP `$2C`.
Movement F2 is P1 `$03`.

Run python tools/check_checkpoint_palettes.py to compare the same World fixtures
on build/barba.nes and the untouched roms/z2.nes. Both 16-byte background palettes
match exactly: Darunia universal sky $13 (purple), Old Kasuto $02 (dark blue).
These are vanilla colors through this fixture; no palette-init or game fix was needed.

Every generated state has a PNG beside it. Automated reload tests check visible-frame
color diversity, expected room/world, all specified loadout fields, survival for 120
frames and (new sets) controller response; they do not prove artistic correctness.
**Visual sign-off is blocked in this run:** the image tool refused the worktree paths,
and no computer-control node was connected. PNGs require producer inspection; no
claim is made that the screenshots were viewed. Local details: build/CHECKPOINTS-REPORT.md.
