# Plan: upward fire ("upstab" for a dragon)

Status: **design approved, 2026-11-14.** Not implemented.

**Producer decisions (2026-11-14):** build both A (upward breath) and B (rising head-butt); column shape; Up+B fires
upward **airborne only**; both are **gated on the Upward Thrust tech**. The **(producer)** markers below were the questions; they are settled.

## Why

Barba attacks only with the five-shot diagonal volley, which goes forward and down. Nothing hits enemies
above, such as Deelers dropping from trees, Ache bats, Moas, palace flyers or anything perched on a ledge,
and Barba can't break ceiling bricks. Vanilla handled both with the upward thrust. Gemini restored downstab
as a centered hitbox under the body (`BarbaSetDownstab`, `src/tall_player.inc`), and stomp (`src/stomp.inc`)
covers weak enemies below. Upstab is the missing direction.

## What vanilla does (from `prg0.asm` `$9561-$959B`)

- Every airborne update writes the pose `$80`: `$06` normally, `$08` (Up Stab) if the **Upward tech**
  (`$0796 & $04`) is learned **and Up is held** (`$F7 & $08`), but only while ascending (`$057D` negative).
  Descending forces `$02`.
- Downstab (`$80 = $09`) overrides that when the Downward tech (`$0796 & $10`) is learned and Down is held (`$17 != 0`).
- So vanilla upthrust is a **held pose while rising**, not a B-press attack. Barba currently hides that melee origin
  (`$0480 = $F8`) like every other one except downstab.

## Proposed design

Two parts that share one gate (the Upward tech, which keeps vanilla progression):

### A. Upward breath: Up+B in the air fires the volley up

- **Trigger:** B pressed while airborne (`$0479 != 0`) with Up held and the Upward tech learned. Grounded Up+B stays
  vanilla for now: Up drives elevators, doors and talking **(producer: also allow it on the ground, away from elevators?)**.
- **Shape (recommended): a column.** The same five-shot scheduler and eight-update cadence, aimed up with a slight forward
  drift (`$7D,x` = `$10`/`$F0`, half the forward speed), so it reads as "breath up and ahead" and still works
  while Barba moves. Alternative: a three-shot fan (up-left, up, up-right) spawned together, which costs a CPU spike
  in one update and three slots at once **(producer)**.
- **Speed and lifetime:** 3 px per update upward for about 28 updates (about 84 px, roughly the head-to-HUD
  distance in palace rooms). Tune by feel.
- **Origin:** the top of the head, centered on the snout column. When the head is folded under a ceiling, it spawns
  at the folded head top, so a brick right above breaks at once (with the glove).
- **Feedback:** the same fireball sound once per attack (`BarbaBreathSfx`), and the open-jaw head during the attack.

### B. Rising head-butt: hold Up while jumping up (mirrors downstab)

- When `$80 == $08` (vanilla already sets it), keep a melee hitbox **above** the head instead of hiding it. It would be
  centered on the 24 px body, like `BarbaSetDownstab`, so a rising dragon hurts what it jumps into.
- Cheap: one more branch in `BarbaSetDownstab` (rename it `BarbaSetThrusts`). No new projectiles.
- Watch item: the tall head is visual while the physical body is native height, so the hitbox should sit at the
  *native* head top plus a little reach, not at the 48 px art top. Otherwise it hits things the player didn't touch.

**(producer)** Ship A only, B only, or both. The recommendation is both: A is the real attack, and B is a nearly free
mirror of downstab that makes vanilla's upthrust rooms and enemies behave sensibly.

## Implementation notes (where it goes)

All of it fits in **bank 0** (`BANK0`, about `$B80` free). It needs **no new fixed-bank hook**, so it doesn't
wait on the fixed-bank headroom run. It should still land after that branch merges, because both touch `src/breath.inc`.

| Piece | Where | Change |
| --- | --- | --- |
| Trigger and aim | `BarbaFireSpell` / `BarbaArmBurst` (`src/breath.inc`) | Latch `BREATH_UP` (a spare bit in an existing `$05Fx` byte, or `$6440+` scratch) at the first shot. It stays for the whole volley even if Up is released. |
| Slot direction | `BarbaPlaceNewFlameCached` | `VOLLEY_SLOT` bit 7 = shallow crouch drift and bits 0-5 = lifetime (`$21`). **Bit 6 is free:** set it for upward. `$7D,x` gets the half-speed table. |
| Y step | `BarbaStepSlotY` | Bit 6 set: subtract 3. Kill on borrow (carry clear) or Y < `$10`, mirroring the existing `>= $E0` wrap guard. The extra (backed) records alias native slot 0 and reuse this routine, so check `src/extra_fire.inc` `$05FC` paths. |
| Origin | `BarbaGeometry` (`src/tall_player.inc`) | Add an "up muzzle" Y/X next to `$05F2/$05F3`, or compute it from them (head top = muzzle Y - 12). |
| Head art | `src/tall_layout.inc`, `assets/barba.json` | Check which frame `$80 = $08` renders today. A real **looking-up, jaw-open head** needs new original art: NES sprites can't rotate, and vertical flips look wrong. Iterate on it in chat by eye. Until then, use the open-jaw attack head. |
| Head-butt | `BarbaSetDownstab` → `BarbaSetThrusts` | Add the `$80 == $08` branch: `$0480` = native head top - reach, `$047E` centered. |
| Bricks | `src/blocks.inc` | Nothing new: `BarbaBlocks` already samples each live fireball's center through the glove-gated native handler. Vanilla let a gloved upthrust break ceiling bricks too, so this adds no new sequence break. |

**Sprite budget:** an upward column shares scanlines only with whatever is above Barba, never with Barba's own
three-wide body rows, unlike the forward-down volley. So it should flicker *less* than the current volley. Keep
`BarbaLoadOk` / `LOAD_LIMIT` unchanged and measure.

## Tests

- New `tests/upstab.lua`:
  1. Upward tech set, airborne, Up+B: five shots, each with Y strictly decreasing, X drifting toward the facing side, no shots below the muzzle.
  2. Tech cleared: Up+B in the air gives the normal forward volley.
  3. Grounded Up+B (and on an elevator): vanilla behavior, no upward shots.
  4. Ceiling brick above: breaks with the glove, stays without it, and Barba's pose and velocity are unchanged.
  5. A shot reaching the top is cleared before Y wraps, so nothing reappears at the bottom.
  6. Head-butt (if B ships): an enemy fixture above a rising Barba takes damage, and nothing happens when descending.
- `perf_volley.lua` variant with upward volleys in the six-enemy fight: no new lag frames.
- Re-run `projectile_only`, `burst`, `extra_fire`, `left_fire`, `shield_enemies`, `link_boss` for regressions.

## Playtest checkpoint

F3 (all techniques, safe castle) is enough to feel the controls. Add one checkpoint with **Deelers or Aches plus a
gloved ceiling brick**, e.g. a forest encounter or a palace room with overhead blocks. The scene list must stay in
sync across `tools/state_scenarios.lua`, `tools/create_test_pack.py` and `tests/state_pack.lua`.

## Routing

Codex for parts A and B plus the tests, once `feat/fixed-bank-headroom` merges. The looking-up head art is done in
chat, iterating on screenshots.
