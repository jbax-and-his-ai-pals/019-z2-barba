# Next session: battle slowdown/flicker and villager-anchored shouts

Prep notes written 2026-11-14 from the code at `067c7c2`. Nothing here is implemented
or measured yet. Hypotheses are labeled as hypotheses.

## 1. Fireball slowdown in battle: FIXED 2026-11-14

Measured with `tests/perf_volley.lua`: lag frames 137 -> 0 of 900. The cause wasn't the
per-pair collision guess below. It was (a) about 8 MMC1 bank switches per enemy per frame in
the collision gateways even with no extra shots, (b) idle save/restore copies, and (c) each
live shot's fixed ~1.2-1.7k cycles pushing busy rooms past ~29.7k. Fixes: fixed-bank fast
path when no backed shot is alive (`EXTRA_LIVE`), idle fast paths, and the `BarbaLoadOk`
governor (queued volley shots wait while enemies + live shots >= 6; the first shot is never
held). Alternate-frame collision thinning was tried, gave nothing measurable, and was reverted.
The notes below are the original pre-measurement prep.

### Original prep (historical)

Symptom (producer playtest): significant slowdown when the five-shot volley is out
in a room with enemies. On the NES that means the main loop overruns a frame
(lag frames), not just sprite flicker.

### Likely per-frame CPU costs (read from source)

- `BarbaExtraUpdate` (`src/extra_fire.inc:191`) runs **every frame**. Even with no
  backed shot alive it calls `BarbaExtraEnsure` and `ExtraSaveZero`/`ExtraRestoreZero`,
  which copy the native projectile window. Hypothesis: a cheap early exit when
  `EXTRA_BASE`, `+$10` and `+$20` are all empty removes most idle cost.
- For each live backed slot it does `ExtraLoadRecord`, native `$9888` (motion, wall
  test, graphics) and `ExtraStoreRecord`. That's roughly a full native projectile
  update per extra shot, plus the copy in and out.
- **Collision is the probable big one:** `BarbaEnemyFire`/`BarbaShieldFire`
  (`extra_fire.inc:285`) wrap the native enemy-vs-projectile helpers, which run per
  enemy. With backed shots alive each enemy aliases each backed slot into slot 0.
  That's up to about 6 enemies × 3 slots × (load + native check + restore) per
  frame. `ExtraNearEnemy` filters by the high byte and sign only, so "near" covers a
  whole 256 px page, and nearly every on-screen enemy pays the full aliasing cost.
- `BarbaGeometry` terrain probes (4 corners, one bank round trip) run once per frame
  plus once per spawn. That's smaller, but it adds up on spawn frames.
- In towns, `BarbaShouts` and the `town.inc` wanderer logic also run each frame.

### Measure first (cheap, before changing anything)

1. Add `tests/perf_volley.lua`. Load the F2 combat checkpoint (or the Palace 1
   fixture `hud_timing.lua` already builds), fire volleys for 600 frames, and count
   **lag frames**: frames where the game's main-loop entry did not execute. Use an
   `emu.addMemoryCallback` exec hook on the side-view frame routine (the
   `Hub_Update_Routine` call near bank 7 `$D4CE`) and compare against
   `endFrame` count.
2. Get a per-routine cycle breakdown: exec callbacks on entry/exit of
   `BarbaExtraUpdate`, `ExtraCollision`, `BarbaGeometry` and `BarbaProjectiles`
   (labels come from `build-report.json` via `LABELS` in the runner). Read the CPU
   cycle counter (`emu.getState()["cpu.cycleCount"]`) at each and sum per frame.
   About 29,780 cycles per frame is the whole budget.
3. Compare: no volley / native-only shots (2 slots) / full volley; 1 vs 4 enemies.

### Candidate fixes, cheapest first

- **Done 2026-11-14 (build `c99b8caa`):** `BarbaExtraUpdate` skips the slot-0 save/restore
  when no backed record is alive, and `ExtraCollision` saves slot 0 only once an
  enemy is actually near a backed shot (flag `$6457`). All 25 scenarios still pass.
  The lag effect is **not measured**; the producer should playtest in F2.
- Early exit in `BarbaExtraUpdate` and `ExtraCollision` when no backed slot is live.
- Tighten `ExtraNearEnemy` to a real box (for example |dx| < 24, |dy| < 24) before
  aliasing.
- Time-slice: check backed-slot collisions on alternate frames (slot parity vs
  frame counter `$12`). Shots move 2 px per update, so a 2-frame check stays
  within a 16 px enemy box.
- Run backed-slot motion without the full `$9888` call, since the volley already owns
  Y motion. Keep native `$9888` for the two real slots.
- Last resort, a design change for the producer: fewer extra shots (3 total), or a
  shorter lifetime (33 updates now).

## 2. Flicker in battle

Hypothesis: the NES 8-sprites-per-scanline limit. The tall player is 24 px wide
(3 sprites per line, 9 sprites total). Enemies are usually 2 or 3 wide. The
fireballs descend diagonally, so several share lines with the player's lower body
and with enemies. Zelda II's OAM rotation turns that overflow into flicker.

Measure: in the same perf scenario, count sprites per scanline from OAM each frame
(max and number of lines over 8). Mesen's sprite viewer also shows it.

Options: draw the 3 head sprites only when needed (they're above the body, so the
lines don't overlap and that doesn't help much). Narrow the body to 16 px during
volleys. Keep backed fireballs out of OAM slots that the rotation always drops.
Cap simultaneous on-screen shots at 3–4. Any choice of fewer shots is the
producer's decision.

## 3. Villager shouts near the speaker

Current: `src/shouts.inc` writes a 20-glyph line into the unused top HUD
nametable row (`$2006` row 0) through the VBlank queue. It's readable but not
attached to anyone.

### Option A (recommended): short sprite "speech" that follows the villager

- Show a 3–5 letter exclamation ("RUN!", "SHIT!", "FUCK!", "HELP!", "NO!")
  as 8x16 sprites just above the speaking villager. Reposition it each frame from
  that actor's `$4E/$3C` (X) and `$2A` (Y) minus scroll, so it **follows them** as
  they flee.
- Cost: needs letter tiles in **sprite** CHR. The font lives in the background
  pattern table, so copy about 10 glyphs into free sprite tiles of the town
  sprite banks (check budget like the ash tiles at `$64/$66`). 8x16 sprites mean
  one glyph per sprite with the letter in the top or bottom half.
- Scanline budget: a 5-letter word is 5 sprites on its row, plus at most a fleeing
  villager nearby. That's fine outside battle. Keep words at 5 letters or fewer
  and hide them when the villager is offscreen, burns, or enters a door.
- OAM: the villager's own slots plus a reserved block of 5 (find free town OAM
  like the ash work did). One shout at a time (keep the global cooldown).
- Keep the full HUD line as an optional subtitle, or drop it.

### Option B: write the line into the playfield nametable near the villager

Rejected unless the producer prefers it. It needs the room's background tiles to
restore afterward, attribute palette clashes, and nametable math under scrolling.
It can't follow a moving villager without heavy VBlank traffic.

### Option C: keep the HUD line but tag the speaker

Draw a small "!" sprite over the villager who shouted while the HUD line shows.
This is the cheapest fallback and needs just 1 sprite.

Implementation entry points: `BarbaShouts` already knows the request. It needs
to also record which actor slot `x` triggered it (in `town.inc`, where panic
starts). Then each frame (in town only) place the word's sprites relative to
that actor, and clear them on timer expiry or scene change.
Tests to extend: `tests/shouts.lua` (positions track the actor within one frame)
and `tests/town.lua` (cleanup on burn/door).
