# Development alpha status

This is an initial playable implementation, not a completed total conversion.

The current player uses boss-derived 24x48 poses, a shared mouth position and a
five-shot diagonal volley at all health levels. Terrain and enemy-contact collision retain the
native body: the raised head is visual, not a newly enlarged hurtbox. Solid
ceilings fold the head into the original 32px height; crouch draws a 24px compact body over the native 16px physical lane.
The body now keeps the boss's narrow neck silhouette without the added belly
coil. Full-body jump rendering is checked during ascent and descent; grounded
crouching retains a short neck beneath the head.

## Verified locally

Validation performed with portable Mesen 2.1.1 and the exact source hash in
BUILD.md. Hardware sprite limits remain enabled.

| Check | Result and limits |
| --- | --- |
| Build integrity | Source hash enforced; all replacements guarded; overlapping writes rejected; original header/mapper/size preserved; source unchanged after build |
| Patch integrity | BPS output reconstructs the generated ROM exactly; wrong source and corrupted patch checksums rejected |
| ROM-free tool tests | Eight unit tests cover binary patch round trips, relocated source references, guards, overlaps, bank offsets and NES 2bpp encoding |
| New-game integration | Controller-driven name entry, castle gameplay, standing/crouched attack poses, jump, castle exit and overworld dragon renderer |
| Projectile-only attack | 16 real-game health/Fire/facing/stance cases each emit exactly five mouth-aligned diagonal fireballs with no melee/plume |
| Actual palace room | Test enters original Palace 6 room `$33` through the normal room loader, walks into lava, remains supported without sinking, jumps out and returns alive; 112 hazard contacts during the scenario |
| Block progression | Six CPU cases verify native glove-gated brick breaking at either projectile, no player-body block damage and restored player pose/speed |
| Hazard routine | All six world groups checked: palace groups gain support; other groups retain original water-death state |
| Roar routine | Inferno consumes the original Thunder state, starts the envelope, and reaches a zero-volume override after 48 updates |
| Human test pack | Eight native Mesen states generated for the exact build; every state reloads with a visible frame and survives 120 further frames; sea crossing completes on East Hyrule |
| Tall geometry and renderer | Four-corner native solid probes, lower head row, world-page crossing, edge rejection, ceiling folding, crouch and extra OAM cleanup pass controlled CPU checks |
| HUD split timing | 900 measured Palace 1 frames keep the split on line 31; previous build reached line 42. No upper-HUD scroll/address writes; native sprite-limit flicker remains possible |
| Bounded volley | Five logical slots keep exact eight-update spacing, preserve range, continue beyond attack animation and require release before rearming |
| Town safety | 1,041 actor/world/room/origin gate cases plus dialogue fallback checks; indoor and scripted actors are excluded |
| Town gameplay | Native Rauru generator, fleeing, real fireball burn/ash/expiry, scripted-walker survival, reachable held-Up dialogue and immediate refuge despawn without background edits |
| Left-facing and player doors | Busy-original-slot and world-page tests emit five shots; real doorway entry/return works with a nearby villager; F8 uses the correct street room |
| Passive panic text | Real PPU text appears within six frames without dialogue locks; automatically clears, preserves native queue prefixes and stays within 32 queued bytes |
| Panic dialogue speed | Holding Up catches a fleeing villager; protected-NPC delays and caller registers retain original behavior |
| Checkpoint XP regression | Upgraded states now recompute the next-level target; 50 XP stays in gameplay, 2,000 XP permits one attack upgrade and returns to gameplay afterward |

Combat and palace scenarios intentionally create controlled fixtures (enemy
positions or room entry and extra health). They exercise the original game
loop, collision and damage code but do not establish that normal progression
through every palace is complete. The routine harness is an isolated CPU check.

Screenshots and detailed reports are generated in the ignored `build/` folder.
Audio register/envelope validation is not a listening-quality review.

## Remaining work before a finished conversion

The ordered next steps and latest human feedback are in [ROADMAP.md](ROADMAP.md).

- Redesign vertical techniques around projectile-only combat; old thrust damage
  and bounce are retired. Glove-gated fireball block breaking is implemented.
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
