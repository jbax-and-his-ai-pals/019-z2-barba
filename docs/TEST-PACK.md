# Instant playtesting checkpoints

## Experimental Waldo portal

On `codex/waldo-portal`, build Barba with `python tools/build.py`, then open
**play/Test Barba - Waldo Portal.cmd**. With the US dump at `roms/waldo.nes`,
the launcher puts Barba on the Rauru doorstep. Press **Up** to enter. Play
*Where's Waldo?* through the Moon landing or press **Start + Select** (Enter
and Space) for a quick return. Barba resumes at the same position and scroll.

This prototype switches between two local ROMs in an isolated Mesen profile.
`python tools/waldo_portal.py --smoke` exercises the native door, starts Waldo's
first level, and verifies the shortcut return, including with Up held. The
report and Waldo screenshot are in `build/waldo-portal.txt` and `.png`.

For the palace victory roar, double-click **play/Test Barba - Gem Celebration.cmd**
and press **F1**. Barba starts beside the Palace 6 crystal statue, past the boss,
with the final gem still unplaced. Walk right: the native gem sequence plays its
fanfare, immediately followed by the roar with Barba looking up. Press F1 again
to repeat. This uses its own isolated `gem` profile and leaves Core F9 intact.
`tests/gem_checkpoint.lua` reloads this checkpoint and verifies placement,
fanfare, exactly one roar, raised head during playback and automatic pose release.
Prepare without opening Mesen: `./tools/launch.ps1 -TestPack -CheckpointSet gem -PrepareOnly`.

For game-over checks, double-click **play/Test Barba - Edge Scenarios.cmd**.
It rebuilds the ROM as needed and installs a separate `edges` test profile:

| Key | Checkpoint | What to test |
| --- | --- | --- |
| F1 | Last life, one hit from death | Palace 1 combat corridor, one life, one health unit and a nearby enemy. Leave the controls alone to reach GAME OVER in about four seconds. |
| F2 | Game Over portrait | Inspect black Link immediately. Press Start to continue; reload F2 to inspect again. |

The edge pack is regenerated for each ROM/recipe version. Generation reloads
both states, verifies natural enemy death from F1, and checks that F2 continues
to gameplay with three lives. Normal play saves and other checkpoint sets are
isolated. Generated files are in `build/test-pack/<ROM hash>/edges/`;
`play/Game Over Danger.mss` is also refreshed as a standalone copy of F1.
To prepare without opening an emulator:
`powershell -File tools/launch.ps1 -TestPack -CheckpointSet edges -PrepareOnly`.

On Windows, double-click **play/Test Barba.cmd**, or run:

```powershell
./tools/launch.ps1 -TestPack
```

The launcher rebuilds the current alpha, generates its checkpoints if needed,
and opens a separate Mesen test profile with the test ROM loaded. Press one of
these keys once the game appears; you do not need to start a file or play the intro.
Press the same key again at any time to restart that test and refill its meters.

| Key | Checkpoint | What to try |
| --- | --- | --- |
| F1 | Starting castle | Normal starting stats. Walk, turn, crouch, jump and attack. |
| F2 | Palace 1 combat corridor | Fight in both directions. Every health level has five diagonal fireballs; Fire-only enemies now take ordinary breath. |
| F3 | All spells and techniques | Safe castle, full health/magic, all spells and both thrusts. Press Space to cast Inferno. Use Enter for the spell menu or reload F3 to refill or leave the flying form. |
| F4 | Palace 6 lava ledge | Walk right into the lava, stop, move, jump and return. |
| F5 | Standing on lava | Already on the lava surface. Check for sinking and test jumps immediately. |
| F6 | Palace 6 boss encounter | Test the playable dragon against Lava Link in Palace 6. |
| F7 | Sea crossing in progress | Watch the dragon complete the normal raft route to East Hyrule. Reload F7 to repeat. |
| F8 | Rauru town street | Approach random outdoor wanderers, watch them flee, and test fireballs and town scorch/combo. |
| F9 | Before Palace 6 boss | Left edge of the boss room with level 8 attack/magic/life, all spells and full meters. Walk right to start the fight against Lava Link. |
| F10 | Great Palace final boss | Great Palace room $35 corridor before Thunderbird and Dark Link with max stats, all spells and full meters. Test `INFERNO`, Dark Link combat and ending progression. |

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

To regenerate manually: `python tools/create_test_pack.py --force`.
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

Open **Test Barba - Busy Areas.cmd** and press F1–F10 in Mesen. The set
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

Core remains the default. Use **Test Barba - Palaces.cmd**, **- Endgame.cmd**, **- Bosses.cmd**,
**- Towns and World.cmd**, or **- Tricky Movement.cmd** in play/ (all beside
Test Barba.cmd). Each opens its own isolated local profile and maps that set to F1-F10.
Unused F-keys do not point at another set's states. Script equivalent:

```powershell
./tools/launch.ps1 -TestPack -CheckpointSet palaces -PrepareOnly
```

Replace palaces with core, endgame, bosses, world or movement. Generation with
`python tools/create_test_pack.py --force` builds and validates **every** set,
then leaves Core selected. Add `--set world` to regenerate just one set.

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

### palaces

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

| Key | Where | Loadout | Look for |
| --- | --- | --- | --- |
| F1 | Palace 6 entrance (world 4, room $24, entry 0) | p6; keys 0 | Check movement, head clearance, combat and HUD. |
| F2 | Great Palace entrance (world 5, room $00, entry 0) | gp; keys 0 | Check movement, head clearance, combat and HUD. |
| F3 | Great Palace elevator (world 5, room $01, entry 0, x=112, y=160) | gp; keys 0 | Start on the native elevator. Hold Down to descend; Up to return. |
| F4 | Great Palace low tunnel (world 5, room $2C, entry 0, x=64, y=176) | gp; keys 0 | Walk through the 32-pixel-high lane; the raised head must fold under stone. |
| F5 | Before Thunderbird (world 5, room $35, entry 0) | gp; keys 0 | Check movement, head clearance, combat and HUD. |
| F6 | Before Dark Link (world 5, room $36, entry 0) | gp; keys 0 | Defeat Dark Link and watch the ending. As the curtain drops, look for the bright fireball with a flickering tail traveling down and right into Zelda, then disappearing as she turns to ash. |
| F7 | Palace 6 boss and crystal approach (world 4, room $3A, entry 0) | p6boss; keys 0 | Walk right to Lava Link; win normally and approach the crystal statue. |
| F8 | Valley of Death rock throwers (East Hyrule, world 0, room $02) | gp; keys 0 | Walk left toward the wall Lizalfos. Face it, jump and press Up+B while it leans out to throw. |

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
| F8 | Dark Link (Great Palace) | world 5, room $36, page 1 | gp |

Rooms match the boss scenarios in tests/ (horsehead.lua ... dark_link.lua). Dark Link's
intro freezes the player for ~340 frames, so F8 is captured at 590 frames, just as control
returns: the fight is already live. F9/F10 are unused.

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

| Key | Where | Loadout | Look for |
| --- | --- | --- | --- |
| F1 | Palace 6 lava ledge (world 4, room $33, entry 0) | p6boss; keys 0 | Walk onto lava, jump back, check native body and folded head. |
| F2 | Palace 1 low tunnel (world 3, room $03, entry 0, x=112, y=176) | p1boss; keys 0 | Walk and crouch under the ceiling. |
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

Thunderbird and Dark Link are safe **approaches**, not fabricated active-boss states.
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
Endgame has eight checkpoints and Movement has nine.

### Numeric feature and palette checks

Generation and reload share tests/checkpoint_features.lua: elevator object and
player Y attachment; stone above the raised head, clear body lane and grounded
floor; open-bottom gap beside a supported player. Controller and 120-frame checks
still apply. Movement F7 additionally replays the native drop and checks room $2D
and unchanged lives. Endgame F4 is GP $2C; Movement F2 is P1 $03, not GP $36.

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
