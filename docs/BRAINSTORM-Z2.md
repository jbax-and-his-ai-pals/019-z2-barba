# Zelda II Base Game Hack — Post-2.0 Brainstorm & Complexity Phases

> **Scope Gate:** All items below are strictly **post-2.0** (do not start until Barba 2.0 ships and freezes).
> Across Rounds 1–7: **74 kept**, **3 maybe/revisit later**, **67 rejected**.
>
> Tags: **`[Playtest]`** = needs hands-on feel/balance tuning · **`[Write]`** = script/dialogue authoring · **`[Tabled]`** = intentionally deferred for careful creative thought.

---

## Locked Post-2.0 Design Decisions

- **Impact sparks & hitstop:** Sparks on all stone/shield hits; subtle 2–3 frame micro-hitstop on **charged shots and boss hits only**.
- **Spell quick-swap & quick-cast:** Plain `Select` still casts (vanilla muscle memory); hold `Select + Left/Right` (or `Up/Down`) to quick-cycle spells on the fly.
- **Charged fireball:** Hold `B` (~0.6 s) to charge for free; fires a larger **piercing** fireball (~1.5–2× damage, cuts through weak foes) with brief recovery so normal volleys remain optimal for sustained DPS.
- **Spell Mastery / Evolved Hyrule Spells:** Unlocks **automatically on NG+** (not at Magic Level 8) — tasteful, subtle upgrade, nothing overpowered.
- **Elemental crystal pedestal ceremony:** 6 distinct geometric/runic conduit shapes (one per palace) built from rearranged center-stripe BG tiles, lighting trail segments behind the crystal with rising elemental chime and color pulse.
- **Sleeping Zelda wake-up & 100% True Ending:** Full comedic re-staging of Zelda's wake-up reaction to Barba, plus a separate **100% True Ending** epilogue.
- **Options / Preferences menu:** Accessible from **both File Select and Pause**; defaults preserve vanilla difficulty (`Palace Continues OFF`, `Timer OFF`, `Quick-Swap ON`, `Sampled Roar ON`).
- **Boss phase shifts (including Lava Link & Dark Barba):** Tasteful & readable at 50% HP — brief flash/roar + 1 signature wrinkle per boss (tighter cadence, extra shot, Lava Link sword-beam/thrust, Dark Barba throne aura).
- **Cracked secret walls, burn secrets & Dragon Shrines reward pool:** Strictly major world/progression discoveries — e.g., hidden Sage with **Teleport**, hidden Arcade subgame, the sealed Superdungeon entrance (discoverable early, unsealed once conditions are met), or similar high-value finds. **No** filler pickups (no 1-UPs/refills/P-Bags), **no** key/seal/clue macguffins, **no** cosmetics.
- **Hyrule Map & Teleport fast-travel:** Learned from a hidden sage (behind an overworld secret or cracked wall). Dual-use: on the **Overworld**, open the Pause Hyrule Map and select a visited town to warp; in **side-view** (towns/caves/palaces), casting `TELEPORT` warps out to the overworld or opens the town warp picker.
- **Palace Room Minimap:** Floor-and-shaft schematic (Metroid/Castlevania style) — visited corridors as horizontal bars, vertical lines for elevator/drop shafts, blinking dot for Barba, plus subtle icons only for unexplored shaft branches and locked doors already walked past (never spoils cracked walls).
- **Subtle in-world clues:** Environmental & ultra-sparse — subtle visual tells (slightly scorched dead tree, hairline wall crack) plus only 2–3 cryptic one-liners across the whole game (classic Zelda II `"Bagu lives east of the river"` energy) — zero hand-holding.
- **Cosmetic unlocks:** Earned via **milestone & mastery feats** — clearing the campaign, NG+, Boss Rush medals (time/no-hit), and beating the Superdungeon (Arcade cosmetics remain on subgames).
- **Hidden optional endgame/NG+ Superdungeon:** Fixed-depth handcrafted brutal descent (6–8 escalating floors mixing palace themes + EX boss/enemy rooms), discoverable early, unsealed after Great Palace / NG+, culminating in the Super-Boss at the bottom.
- **Hidden Optional Super-Boss identity:** **`[Tabled]`** — intentionally deferred to think through carefully later.
- **Meta-modes & Hub placement:** **Split** — Practice Mode, Boss Rush, and Cutscene Gallery live in an Extras menu on Title/File Select, while Trophy Checklist & Boss Dossier are also viewable from Pause (plus optional in-world hidden doors for Dev Room / Superdungeon).

---

## Complexity-Ordered Phases (Post-2.0)

### Phase 0 — Post-2.0 Headroom & Persistence Prep *(Prerequisite)*
- Plan dedicated post-2.0 PRG/CHR headroom (beyond the tight 2.0 banks) and a clean SRAM/WRAM extension block for Options, Run Stats, Splits, Boss Rush medals, and Discovery/Trophy flags.

### Phase 1 — Quick Wins & Crisp Feel *(Lowest Complexity)*
Small, self-contained hooks with fast visual/audio payoff and minimal architectural risk:
- **Low-MP cast fizzle** — smoke puff + dry dragon cough when trying to cast without enough MP
- **Impact sparks & selective hitstop** — sparks on all stone/shield hits; subtle 2–3 frame micro-hitstop on charged shots and boss hits only
- **Heavy landing / stomp dust** — dust puffs + subtle thump on high drops / downstabs
- **Steam & sizzle on water** — steam puffs when fireballs hit water/swamps; Barba steams while wading
- **Lava bubbles & rising sparks** — sprite bubbles/embers over Palace 6 and Great Palace lava pits
- **False-wall & fake-floor shimmer** — subtle visual tell/ripple on fake walls and hidden drop pits
- **Locked door unlock flourish** — brief glowing keyhole dissolve / latch burst on unlock
- **Treasure-pedestal aura** — shimmer/glow on palace key-item pedestals before pickup
- **Secret-room chime** — faint audio cue on entering a room with a secret wall or shrine
- **Boss meter phase notch** — tiny divider pip on the boss HP bar *(prepares for Phase 6 boss phases)*
- **Palace-entrance continues (toggleable)** — Game Over inside a palace restarts at that palace's entrance (default `OFF`)

### Phase 2 — Atmosphere & Environmental Juice *(Low–Medium Complexity)*
CHR-bankswitching, palette, and sprite ambient layers building on our existing MMC3 IRQ/scenery engine:
- **Water reflections** — rippling reflections under bridges and across lakes
- **Regional weather & sky moods** — Death Mountain ash, Valley of Death lightning, crimson Great Palace sky
- **Palace-specific animated backdrops** — dripping water, drifting embers, or subtle per-palace wall life
- **Animated overworld landmarks** — smoking Death Mountain crater, glinting palace spires, coastline surf
- **Ocean-walk Boots atmosphere** — crashing waves, sea spray, and Palace 5 silhouette during the sea walk
- **Area & palace title cards** — brief stylized banner on entering towns, caves, and palaces
- **Title screen progression flair** — subtle title visual reward after beating the game / 100% clear
- **NG+ visual distinction** — veteran palette/trim accents and elevated Great Palace tone on NG+

### Phase 3 — Combat & Spell Upgrades *(Medium Complexity — `[Playtest]`)*
Core player feel, controls, and magic expression:
- **Spell quick-swap & vanilla cast** `[Playtest]` — plain `Select` casts; hold `Select + Left/Right` (or `Up/Down`) to cycle spells on the fly
- **Charged fireball** `[Playtest]` — hold `B` (~0.6 s) free charge for a larger piercing fireball (1.5–2× dmg, slices weak foes, brief recovery so normal volleys stay best for sustained DPS)
- **Wyrmling form polish** `[Playtest]` — snappier `WYRMLNG` flight feel + tiny ember trail
- **Vanilla spell visual upgrades** — crisp visual flair for `JUMP`, `LIFE`, `REFLECT`, and `SPELL`
- **Spell Mastery / Evolved Hyrule Spells** `[Playtest]` — unlocks automatically on **NG+** (not Magic Lv 8) as a tasteful, subtle upgrade

### Phase 4 — Iconic Setpieces & Cutscenes *(Medium Complexity)*
Signature Zelda II moments turned into memorable Barba Edition showpieces:
- **Elemental crystal pedestal ceremony** — 6 unique geometric/runic maze conduit routes (one per palace) built from rearranged center-stripe BG tiles, lighting trail segments with rising elemental chime & color pulse
- **Palace clear escape / collapse flair** — shaking walls, falling pebbles, or clearing sky after placing a crystal
- **Upgraded Great Palace barrier break** — dramatic 6-crystal seal-shattering sequence
- **Animated Raft crossing** — bobbing wave sailing sequence between West and East Hyrule
- **Flute / River Devil spectacle** — musical animation and rumble as the River Devil retreats
- **Sleeping Zelda wake-up overhaul** `[Write]` — full comedic re-staging of Zelda's wake-up reaction to Barba
- **Alternate / 100% True Ending** `[Write]` — separate bonus epilogue beat for 100% completion

### Phase 5 — HUD, Menus, Telemetry & QoL *(Medium–High Complexity)*
UI upgrades and player-facing systems that tie into the Phase 0 SRAM block:
- **Expressive HUD portrait** — tiny reactive Barba face on the status bar (snarls, low-HP sweat, wears gear)
- **HUD spell icon** — small icon for the currently queued spell
- **In-game Options / Preferences menu** — accessible from both File Select and Pause; vanilla-faithful defaults (`Palace Continues OFF`, `Timer OFF`, `Quick-Swap ON`, `Sampled Roar ON`)
- **Manual Barba palette picker** — pick unlocked Barba palettes directly alongside seeded shuffle
- **Upgraded File Select** — crystal progress, hearts/magic, equipped cosmetics, and clear badges per slot
- **Upgraded Level-Up screen** — next-level stat preview showing actual Attack/Magic/Life gains
- **Upgraded Game Over / Continue screen** — progress recap alongside Continue, Palace Restart, and Save
- **Built-in speedrun timer & splits + mid-run stats peek** — unobtrusive timer, per-palace splits, and pause-menu stat peek
- **End-credits run stats** — villagers toasted, forests burned, bosses felled, deaths, clear time, and splits

### Phase 6 — Boss Overhaul *(High Complexity — `[Playtest]`)*
Elevating every palace boss fight without breaking vanilla readability or zero-lag budgets:
- **Boss intro nameplates** — short dramatic standoff banner before each boss activates
- **Boss phase shifts** `[Playtest]` — at 50% HP, brief flash/roar and 1 readable signature wrinkle per boss
- **Custom boss arena framing + boss arena wear & tear** — room-specific decor plus scorch marks/chipped pillars accumulating mid-fight
- **Dramatic boss kill finish** — brief hit-freeze and cascading shatter/explosion burst
- **Upgraded enemy projectiles** — sharper sprites/trails for Wizzrobe beams, Carock bolts, and Thunderbird fire
- **Lava Link rivalry flair** `[Playtest]` — classic Link sword-beam/thrust callbacks and taunts in Palace 6
- **Dark Barba finale spectacle** `[Playtest]` — escalated final-boss atmosphere in the Great Palace throne room

### Phase 7 — Maps, World Secrets & Lore *(High Complexity — `[Playtest]` `[Write]`)*
Exploration, navigation, worldbuilding, and strictly high-value non-filler secrets:
- **In-game Hyrule map + Dual-use Teleport spell** `[Playtest]` — pause-screen overworld map; `TELEPORT` learned from a hidden sage (overworld map town-warp + side-view escape/town-warp)
- **Palace room minimap** — Metroid/Castlevania floor-and-shaft schematic showing visited corridors, elevator/drop shafts, blinking Barba dot, plus subtle icons only for unexplored shaft branches and already-seen locked doors
- **Cracked secret walls** — blastable masonry leading strictly to major discoveries (Teleport sage, Arcade subgame, sealed Superdungeon entrance, etc. — never filler pickups, keys/clues, or cosmetics)
- **Hidden Dragon Shrines / lore tablets + mini-trials** `[Playtest]` `[Write]` — secret rooms with light environmental trials tied to major discoveries/lore
- **Interactive overworld burn secrets** — suspicious landmarks (e.g., subtly scorched dead tree) hiding major discoveries
- **Destructible side-view props** `[Playtest]` — burnable palace tapestries, crumbling statues, ignitable rope bridges
- **Subtle in-world clues** `[Write]` — environmental visual tells + only 2–3 cryptic NES-style one-liners across the whole game (zero hand-holding)
- **Dynamic town dialogue** `[Write]` — townsfolk react to recent palace clears and deeds
- **Expanded "I AM ERROR", Bagu & River Man gag** `[Write]` — bonus secret dialogue chain tying all three to the Barba swap
- **Hidden dev / museum room** — Easter-egg room showcasing Barba gags, unused art, and credits cameos

### Phase 8 — Endgame Modes, Replay & Superdungeon *(Highest Complexity — `[Playtest]`)*
Major post-game modes, meta-progression hubs, and new dungeon/boss content:
- **Cosmetic unlocks** — milestone & mastery rewards (campaign clear, NG+, Boss Rush medals, Superdungeon clear; Arcade gear stays on subgames)
- **Extras menu (Title/File Select) + Pause Trophy/Dossier split** — Practice Mode, Boss Rush, and Cutscene Gallery on Title/File Select; Trophy Checklist & Boss Dossier also readable from Pause; optional in-world hidden doors for Dev Room / Superdungeon
- **Boss / room practice mode + one-button quick-retry** — jump straight into any boss or tough room without touching save progress
- **Boss Rush / Gauntlet + medals, best times & quick-retry** `[Playtest]` — back-to-back palace boss gauntlet with SRAM-saved times and no-hit badges
- **EX / Remixed Boss variants** `[Playtest]` — tougher second-tier boss patterns for Boss Rush EX and the Superdungeon
- **Trophy / secret checklist screen + Boss Dossier / Bestiary** `[Write]` — unified tracker for bosses, win/death stats, lore blurbs, secrets, and cosmetics
- **Cutscene / setpiece replay gallery** — re-watch unlocked endings, barrier breaks, and boss intros
- **Hidden optional endgame/NG+ superdungeon + super-boss** `[Playtest]` `[Tabled]` — fixed-depth handcrafted brutal descent (6–8 escalating floors mixing palace themes + EX rooms), discoverable early and unsealed after Great Palace / NG+, culminating in the optional super-boss *(super-boss identity tabled for dedicated creative thought later)*

### Parking Lot — Maybe / Separate Track
- **Elevator & shaft parallax** *(maybe)* — passing stone masonry, speed cues, and subtle rumble on palace lifts and long drops
- **Key item visual effects** *(maybe)* — Boots sea ripples, Cross Moa reveal pulse, Glove block-break sparks
- **Built-in remix / randomizer seed** *(yes, separate project later)* — lightweight item, enemy, or palette shuffle toggle on File Select

---

## Round-by-Round Archive: Kept

### Round 1
- **Charged fireball** — hold B briefly for a bigger, piercing or explosive blast
- **Steam & sizzle on water** — fireballs hitting water/swamps kick up steam puffs; Barba steams when wading
- **Regional weather & sky moods** — falling ash near Death Mountain, lightning flashes in Valley of Death, crimson sky approaching Great Palace
- **Palace-specific animated backdrops** — dripping cavern water, drifting embers, or distant parallax pillars per palace
- **Destructible side-view props** — burnable palace tapestries, crumbling statues, or ignitable rope bridges
- **Boss phase shifts** — brief rage roar, palette flash, and tighter attack cadence / new wrinkle at half HP
- **Dynamic town dialogue** — townsfolk react to your latest palace clear or infamous deeds
- **End-credits run stats** — villagers toasted, forests burned, bosses felled, deaths, and clear time
- **Boss Rush / Gauntlet** — hidden door or post-game mode to fight all palace bosses back-to-back
- **Expressive HUD portrait** — tiny reactive Barba face on the status bar (snarls when firing, sweats at low HP, wears equipped gear)

### Round 2
- **Spell quick-swap** — cycle equipped spell on the fly (e.g. `Select`) without opening the pause menu
- **Impact sparks** — distinct sparks on stone/shields (TBD on whether to pair with hitstop)
- **Heavy landing / stomp dust** — landing from high drops or downstabs kicks up dust clouds and a subtle ground thump
- **Animated overworld landmarks** — smoking Death Mountain crater, glinting palace spires, coastline surf
- **Cracked secret walls** — subtle weak masonry in palaces/caves that fireballs can blast open (reward: hidden subgames or meaningful goodies — not money/P-Bags, since money is useless in Zelda II)
- **Water reflections** — subtle rippling reflections beneath bridges and across lakes
- **In-game Hyrule map** — pause-screen map marking discovered towns, palaces, and shrines
- **Area & palace title cards** — brief stylized location banner when entering a town, cave, or palace
- **Boss intro nameplates** — short dramatic standoff banner before each palace boss activates
- **Palace clear escape / collapse flair** — shaking walls, falling pebbles, or clearing sky after placing a crystal
- **Palace-entrance continues** — optional Game Over restart at the current palace entrance instead of North Castle
- **Boss / room practice mode** — jump straight into any boss or tough room without touching your save
- **Cosmetic unlocks** — unlockable golden/ember Barba palettes, crown flair, etc. (TBD whether post-game or earned elsewhere)

### Round 3
- **Dramatic boss kill finish** — brief hit-freeze and cascading shatter/explosion burst when a palace boss falls
- **Palace room minimap** — pause-screen palace map showing visited rooms, locked doors, and boss room
- **Hidden dragon shrines / lore tablets** — secret rooms rewarding passive perks, cosmetics, or Barba/Hyrule lore
- **Interactive overworld burn secrets** — breathing fire on suspicious landmarks (dead trees, boulders, tombstones) reveals hidden tiles
- **Upgraded File Select** — display crystal progress, hearts/magic, equipped cosmetics, and clear badges per save slot
- **HUD spell icon** — tiny icon for the currently queued spell on the HUD
- **Upgraded Great Palace barrier break** — dramatic 6-crystal seal-shattering sequence when unlocking the Great Palace
- **Built-in speedrun timer & splits** — unobtrusive optional timer with per-palace splits feeding end-credits stats
- **Hidden optional super-boss** — one secret late-game/post-game fight tucked away in Hyrule
- **Trophy / secret checklist screen** — track bosses beaten, secrets found, and cosmetics unlocked

### Round 4
- **Animated Raft crossing** — brief sailing transition / bobbing waves across the sea between West and East Hyrule
- **Flute / River Devil spectacle** — upgraded musical animation and rumble as the River Devil retreats
- **Expanded "I AM ERROR", Bagu & River Man gag** — bonus secret dialogue chain / callback payoff tying Error, Bagu, River Man, and the Barba swap together
- **Sleeping Zelda wake-up overhaul** *(revisit/expand — already has some custom behavior)*
- **Alternate / 100% True Ending** — extra epilogue beat if you clear with all shrines, secrets, or Arcade games completed
- **Wyrmling form polish** — snappier `WYRMLNG` flight feel with tiny ember trail sprites
- **Dedicated quick-cast + quick-swap shortcut** — optional instant-cast binding for the queued spell paired with spell quick-swap
- **Elemental crystal pedestal ceremony** — distinct beam/seal flair per palace, with the crystal traveling a different cryptic blocky maze route per palace instead of straight up (backing graphics built from the center upward-stripe tiles rearranged into maze-shape conduits)
- **In-game Options / Preferences menu** — clean toggle screen on File Select/Pause for QoL options (palace continues, timer, quick-swap, audio)
- **Upgraded Level-Up screen** — clear next-level stat preview showing what Attack, Magic, and Life actually improve
- **Upgraded Game Over / Continue screen** — quick progress recap alongside Continue, Palace Restart, and Save
- **Hidden optional endgame/NG+ superdungeon** — brutal or endless/deep optional mini-palace challenge dungeon with the hidden super-boss at the bottom (pairs with Round 3's hidden optional super-boss)
- **Hidden dev / museum room** — secret Easter-egg room showcasing Barba gags, unused art, or credits cameos
- **NG+ visual distinction** — subtle veteran flair on NG+ (alternate palace trims or elevated Great Palace finale)

### Round 5
- **Custom boss arena framing** — signature visual touches per boss room (Carock's arcane runes, Rebonack's banners, Gooma's sea chains, Thunderbird's skylight)
- **Dark Barba finale spectacle** — visually escalated final battle atmosphere in the Great Palace throne room
- **False-wall & fake-floor shimmer** — subtle visual tell or ripple when passing through Zelda II's fake walls and hidden drop pits
- **Locked door unlock flourish** — brief glowing keyhole dissolve / latch burst instead of an instant tile pop
- **Vanilla spell visual upgrades** — crisp visual flair for Hyrule spells (`JUMP` air trail, `LIFE` rising heal sparkles, `REFLECT` prism sheen, `SPELL` cast wave)
- **One-button quick-retry** — instant restart in Boss Rush / Practice Mode without menu downtime

### Round 6
- **Lava Link rivalry flair** — classic Link-style flourishes in Palace 6 (sword-beam bursts, upward/downward thrust cues, heroic taunts)
- **Boss arena wear & tear** — scorch marks and chipped pillars accumulating as a boss fight escalates
- **Upgraded enemy projectiles** — sharper sprites and trails for Wizzrobe beams, Carock bolts, and Thunderbird fire
- **Map fast-travel** *(maybe via a Teleport spell)* — late-game warp between discovered towns/shrines from the Hyrule map
- **Lava bubbles & rising sparks** — animated sprite bubbles and floating embers over Palace 6 and Great Palace lava pits
- **Secret-room chime** — faint audio cue when entering a room that contains a cracked wall or hidden shrine
- **Treasure-pedestal aura** — palace item rooms (Candle, Glove, Raft, Boots, Flute, Cross) glow with a sacred pedestal shimmer before pickup
- **Manual Barba palette picker** — choose unlocked Barba color schemes directly in Options / Gear Bar (alongside seeded shuffle)
- **Boss Rush medals & best times** — SRAM-saved clear times and no-hit badges per boss / full gauntlet
- **Title screen progression flair** — subtle title-screen visual reward once you've beaten the game (or 100% cleared)
- **Cutscene / setpiece replay gallery** — re-watch unlocked endings, barrier breaks, and boss intros from the menu

### Round 7
- **EX / Remixed Boss variants** — tougher second-tier boss patterns reserved for the Superdungeon or unlocked Boss Rush EX
- **Low-MP cast fizzle** — tiny smoke puff + dry dragon cough when trying to cast a spell without enough MP
- **In-world clues for new secrets** *(tread carefully — keep subtle)* — cryptic hints in towns, signs, and shrines pointing organically toward cracked walls, burn secrets, and the superdungeon
- **Ocean-walk Boots atmosphere** — crashing waves, sea spray, and distant Ocean Palace silhouette while walking across the sea to Palace 5
- **Dragon Shrine mini-trials** — light Zelda-style triggers inside Hidden Dragon Shrines (lighting twin sconces, bouncing a shot, or clearing a short trial)
- **Minimap key & chest markers** *(refine what goes on the map)* — mark discovered locked doors, remaining keys, and treasure rooms on the Palace Room Minimap
- **Spell Mastery / Evolved Hyrule Spells** — clearing Dragon Shrines or NG+ unlocks subtle visual/functional upgrades to classic Hyrule spells
- **Boss meter phase notch** — tiny divider pip on the boss HP bar marking where the boss's Phase 2 shift triggers
- **Mid-run stats & splits peek** — check current run time, palace splits, and burn/death counters from the pause menu without waiting for credits
- **Boss Dossier / Bestiary entries** — unlockable short lore blurbs, sprites, and personal win/death records per boss inside the Trophy/Checklist screen

---

## Round-by-Round Archive: Maybe / Revisit Later

### Round 2
- **Elevator & shaft parallax** *(maybe)* — passing stone masonry, speed cues, and subtle rumble on palace lifts and long drops
- **Built-in remix / randomizer seed** *(yes, separate project later)* — lightweight item, enemy, or palette shuffle toggle on File Select

### Round 5
- **Key item visual effects** *(maybe)* — Boots leave shimmering ripples on sea tiles, Cross emits a subtle reveal pulse around Moas, Glove sparks on block breaks

---

## Round-by-Round Archive: Rejected

### Round 1
- Manual roar shockwave
- Wing-glide / slow-fall
- Fire-roll / ground-skimming flame
- Heat buildup / overdrive
- Light palace braziers & torches
- Overworld trail scars
- More bespoke enemy death animations
- Wandering Link ambush
- Enemy fear / reaction
- Overheated armor
- Town infamy / bounty system
- Barba's Dragon Hoard
- Reactive North Castle
- NG+ "Hero's Revenge" twist

### Round 2
- Timed projectile parry
- Midair breath recoil
- Overworld day/dusk/night cycle
- Per-palace music variants
- Custom attract-mode demo
- Sound test / Jukebox
- XP overflow carryover

### Round 3
- Parallax horizons
- Palace lighting & shadows
- Foreground depth props
- Heat-haze lava shimmer
- Crumbling bridge / falling hazard setpieces
- Secret shortcuts & warp caves
- Hidden palace mini-bosses
- Better secret pickups
- Themed room wipes
- Optional damage/hit feedback
- Item/spell get flourish
- Unlockable challenge modifiers

### Round 4
- Palace entrance statue flair
- Barba boulder-smash animation
- Overworld hidden-spot tells
- Town healer & sage mini-scenes
- File Select copy / rename / delete
- Quest / clue log
- Rare overworld sightings

### Round 5
- Thunderbird shield telegraph
- Ornate palace elevators
- Distinct town skylines & palettes
- Old Kasuto ruins atmosphere
- Expanded town signboards
- Per-sage spell learning scenes
- Overworld enemy silhouette variety
- Heart & Magic Container discovery fanfare
- Extra punchy DPCM / SFX accents
- Pause-menu Save & Quit
- Title screen secret codes

### Round 6
- Wall-slam knockback dust
- Multi-kill ping
- Animated Saria bridge sequence
- Animated overworld palace crumble
- Mid-palace boss-door shortcut
- Overworld-to-encounter snap transition
- Vertical ledge peek

### Round 7
- Boss-specific telegraph polish
- Surface-aware footstep & landing audio
- Elite knight duel flair
- Death Mountain & Maze Island landmarks
- Handcrafted rare encounter rooms
- Alternate Barba sprite styles
- Gear-specific micro-flourishes
- Emergency Wyrmling charm
