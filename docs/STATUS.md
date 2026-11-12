# Development alpha status

This is an initial playable implementation, not a completed total conversion.

## Verified locally

Validation performed with portable Mesen 2.1.1 and the exact source hash in
BUILD.md. Hardware sprite limits remain enabled.

| Check | Result and limits |
| --- | --- |
| Build integrity | Source hash enforced; all replacements guarded; overlapping writes rejected; original header/mapper/size preserved; source unchanged after build |
| Patch integrity | BPS output reconstructs the generated ROM exactly; wrong source and corrupted patch checksums rejected |
| ROM-free tool tests | Six unit tests cover binary patch round trips, relocated source references, guards, overlaps, bank offsets and NES 2bpp encoding |
| New-game integration | Controller-driven name entry, castle gameplay, standing/crouched attack poses, jump, castle exit and overworld dragon renderer |
| Enemy damage integration | Four controlled Bot fixtures take damage from horizontal flames: standing/crouched, left/right, below-full health with Fire inactive |
| Actual palace room | Test enters original Palace 6 room `$33` through the normal room loader, walks into lava, remains supported without sinking, jumps out and returns alive; 112 hazard contacts during the scenario |
| Banked hitbox routine | Six cases execute assembled 6502 code in Mesen, covering both sides, screen-edge clipping, original vertical boxes, enemy-bank restoration and X preservation |
| Hazard routine | All six world groups checked: palace groups gain support; other groups retain original water-death state |
| Roar routine | Inferno consumes the original Thunder state, starts the envelope, and reaches a zero-volume override after 48 updates |

Combat and palace scenarios intentionally create controlled fixtures (enemy
positions or room entry and extra health). They exercise the original game
loop, collision and damage code but do not establish that normal progression
through every palace is complete. The routine harness is an isolated CPU check.

Screenshots and detailed reports are generated in the ignored `build/` folder.
Audio register/envelope validation is not a listening-quality review.

## Remaining work before a finished conversion

- Design dedicated up/down flame poses and plume art; currently their original
  damage shapes, unlocks and bounce behavior remain with the dragon body.
- Give Palace 6's boss a distinct Ice Barba appearance and verify the encounter.
- Audit sprite states and CHR sharing in every town, palace, menu, ending and
  the Dark Link encounter; the current replacement covers 13 side-view sprite banks.
- Replace residual Link references, title and item/menu art where appropriate.
- Refine the lava pose to appear partly submerged, and audit all lava rooms,
  bottomless pits, water hazards, elevators, low tunnels and collapsing floors.
- Listen to and tune the roar with music, pause/unpause and scene transitions.
  Additional milestone triggers are not implemented yet.
- Test all spell unlocks, NPC/quest interactions, Reflect, bosses, blocks,
  projectile walls, save/load/continue and a complete playthrough.
- Cross-check another accurate emulator and original-style MMC1 hardware behavior.

No public ROM or finished release is provided in the repository. Build locally
from the required source ROM; the ROM and generated patches stay ignored.
