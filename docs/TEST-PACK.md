# Instant playtesting checkpoints

On Windows, double-click **Test Barba.cmd**, or run:

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
| F2 | Palace 1 combat corridor | An enemy is close by. Fight standing and crouched in both directions; below-full health prevents beams from hiding melee problems. |
| F3 | All spells and techniques | Safe castle, full health/magic, all spells and both thrusts. Inferno is selected: Left Shift casts it. Use Enter for the spell menu; reload F3 to refill or leave the flying form. |
| F4 | Palace 6 lava ledge | Walk right into the lava, stop, move, jump and return. |
| F5 | Standing on lava | Already on the lava surface. Check for sinking and test jumps immediately. |
| F6 | Palace 6 Barba encounter | Original Barba is above the lava. Test player/boss graphics, attacks and movement around the platforms. Ice Barba is not implemented. |
| F7 | Sea crossing in progress | Watch the dragon complete the normal raft route to East Hyrule. Reload F7 to repeat. |

Controls: arrows move, **X** jumps, **Z** attacks, **Enter** starts/pauses, and
**Left Shift** is Select/cast. State-load keys work independently of the game menu.
The upgraded states have nine lives, eight heart/magic containers, level 4 attack,
level 8 magic/life, all spells, both thrusts and traversal items. Damage and magic
consumption work normally: no invulnerability or unlimited-magic cheat runs.

## Isolation and compatibility

- Normal play saves and settings in `.tools/mesen-play/` are not modified.
- The test profile is `.tools/mesen-scenarios/`. It does not reuse a running
  normal-play Mesen window.
- Test battery saves and states live under `build/test-pack/<ROM hash>/`.
  Generated master `.mss` files stay separate from the disposable F1-F7 slots.
- Launching the test pack restores those seven slots from their masters. Use
  **Save State to File** if you want to keep your own additional test checkpoint.
- Each pack records its exact ROM SHA-256. After a code/art change, the launcher
  creates a new pack for that build. Old states should not be mixed with a new ROM.
- These are constructed test fixtures, not an authentic completed-game save.
  Room entry and upgrades are injected during generation; ordinary game logic
  controls the resulting scene, enemies, damage, physics and crossing.
- All seven states are reloaded and checked in Mesen 2.1.1 before being marked
  ready. Screenshots, capture logs and reload validation remain alongside them.
- No state files, screenshots or test ROMs are committed to the public repository.

To regenerate manually: `python tools/create_test_pack.py --force`.
To prepare everything without opening another window:
`./tools/launch.ps1 -TestPack -PrepareOnly`.

The first version's upgraded checkpoints had a stale next-level XP target and
could loop in the upgrade menu after a small XP gain. Corrected states recompute
that target from the ROM's level tables. Reload a freshly installed F2-F7 slot
to replace an old in-memory checkpoint; this fix does not change normal saves.
