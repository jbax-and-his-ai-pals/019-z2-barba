window.BARBA_FE_CATALOG = {
  "version": 1,
  "categories": [
    {
      "id": "barba_core",
      "title": "Barba Mode (Coupled Core)",
      "icon": "dragon"
    },
    {
      "id": "barba_options",
      "title": "Barba-Only Options & Tunables",
      "icon": "flame"
    },
    {
      "id": "world_presentation",
      "title": "World, Presentation & Crossover (Decoupled)",
      "icon": "map"
    },
    {
      "id": "randomizer",
      "title": "Randomizer & Pacing",
      "icon": "dice"
    }
  ],
  "flags": [
    {
      "id": "barba_protagonist",
      "code": "Bb",
      "category": "barba_core",
      "label": "Barba Mode: Link (Sword Slash) -> Barba (Firebreath Volley & Dragon Kit)",
      "type": "bool",
      "status": "built",
      "vanilla": false,
      "barba": true,
      "requires": [],
      "description": "Hard switch between Vanilla Link and Full Barba (24x48 dragon with diagonal firebreath volleys, dragon spells, and Barba-specific mechanics).",
      "preview": {
        "off": "previews/cap_vanilla_grass_attack.png",
        "off_w": 256,
        "off_h": 176,
        "off_label": "Link (Sword Slash)",
        "on": "previews/cap_barba_grass_attack.png",
        "on_w": 256,
        "on_h": 176,
        "on_label": "Barba (Firebreath Volley)",
        "frames": 84,
        "fps": 20
      }
    },
    {
      "id": "spell_scales",
      "code": "S1",
      "category": "barba_core",
      "label": "Shield -> SCALES",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Replaces Shield with SCALES: navy outline + sky-blue body, cast roar/decor flash, and shielded-hit clang.",
      "preview": {
        "off": "previews/cap_vanilla_spell_scales.png",
        "off_w": 256,
        "off_h": 176,
        "off_label": "Vanilla Shield",
        "on": "previews/cap_barba_spell_scales.png",
        "on_w": 256,
        "on_h": 176,
        "on_label": "SCALES",
        "frames": 48,
        "fps": 20
      }
    },
    {
      "id": "spell_wyrmling",
      "code": "S2",
      "category": "barba_core",
      "label": "Fairy -> WYRMLING",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Replaces Fairy with an 8x16 flying Wyrmling form.",
      "preview": {
        "off": "previews/cap_vanilla_spell_wyrmling.png",
        "off_w": 256,
        "off_h": 176,
        "off_label": "Vanilla Fairy",
        "on": "previews/cap_barba_spell_wyrmling.png",
        "on_w": 256,
        "on_h": 176,
        "on_label": "WYRMLING",
        "frames": 48,
        "fps": 20
      }
    },
    {
      "id": "spell_meteor",
      "code": "S3",
      "category": "barba_core",
      "label": "Fire -> METEOR",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Replaces Fire with an airborne Down+B dive slam that sends floor shockwaves crawling left and right.",
      "preview": {
        "off": "previews/cap_vanilla_spell_meteor.png",
        "off_w": 256,
        "off_h": 176,
        "off_label": "Vanilla Fire",
        "on": "previews/cap_barba_spell_meteor.png",
        "on_w": 256,
        "on_h": 176,
        "on_label": "METEOR",
        "frames": 104,
        "fps": 20
      }
    },
    {
      "id": "spell_inferno",
      "code": "S4",
      "category": "barba_core",
      "label": "Thunder -> INFERNO",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Replaces Thunder with a 4-wave 4-way firestorm (previewed at Thunderbird).",
      "preview": {
        "off": "previews/cap_vanilla_spell_inferno.png",
        "off_w": 256,
        "off_h": 176,
        "off_label": "Vanilla Thunder",
        "on": "previews/cap_barba_spell_inferno.png",
        "on_w": 256,
        "on_h": 176,
        "on_label": "INFERNO",
        "frames": 64,
        "fps": 20
      }
    },
    {
      "id": "upstab_breath",
      "code": "Wu",
      "category": "barba_core",
      "label": "Up-Thrust -> Upward Breath & Rising Head-Butt",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Technique-gated Up-Thrust (Up+B in air) fires upward diagonal firebreath volleys alongside a rising head-butt pose."
    },
    {
      "id": "downstab_stomp",
      "code": "Wd",
      "category": "barba_core",
      "label": "Down-Thrust -> Dive Stomp & Downstab Tail",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Technique-gated Down-Thrust (Down+B in air) stomps easy enemies (HP 1..16, excluding shielded foes and bosses) on descent, with a downstab tail pose and contact item pickup."
    },
    {
      "id": "ironknuckle_rebound",
      "code": "Ir",
      "category": "barba_core",
      "label": "Ironknuckle Shield Rebound",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Palace Ironknuckles bank downward firebreath off their shields toward other enemies.",
      "preview": {
        "off": "previews/cap_vanilla_ironknuckle_rebound.png",
        "off_w": 256,
        "off_h": 176,
        "off_label": "Vanilla Ironknuckle",
        "on": "previews/cap_barba_ironknuckle_rebound.png",
        "on_w": 256,
        "on_h": 176,
        "on_label": "Shield Rebound",
        "frames": 96,
        "fps": 20
      }
    },
    {
      "id": "glove_bricks",
      "code": "Gb",
      "category": "barba_core",
      "label": "Breath Breaks Glove Bricks",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Firebreath shatters glove-gated palace blocks once the Handy Glove is acquired."
    },
    {
      "id": "lava_wade",
      "code": "Lw",
      "category": "barba_core",
      "label": "Submerged Lava & Swamp Pose",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Draws Barba partially submerged when wading in lava or foul water."
    },
    {
      "id": "palace_roar_shake",
      "code": "Wp",
      "category": "barba_core",
      "label": "Palace Crystal & Lava Link Roar Shake",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Crystal floor pulse, Palace 6 drop roar, and Lava Link entrance camera/HUD shake.",
      "preview": {
        "off": "previews/cap_vanilla_palace_roar.png",
        "off_w": 256,
        "off_h": 176,
        "off_label": "Vanilla Crystal",
        "on": "previews/cap_barba_palace_roar.png",
        "on_w": 256,
        "on_h": 176,
        "on_label": "Crystal Pulse & Shake",
        "frames": 112,
        "fps": 20
      }
    },
    {
      "id": "rauru_sage_basement",
      "code": "Wr",
      "category": "barba_core",
      "label": "Rauru Sage Basement Sequence",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Adds the post-SCALES 'WAIT.' callout and 5-box dialogue with Rauru's sage."
    },
    {
      "id": "title_and_ending",
      "code": "Wt",
      "category": "barba_core",
      "label": "Title & Ending: Link -> Barba Cliff & Dark Barba",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Title screen dragon silhouette, lava shimmer, 2nd-roar shake, and Dark Barba Triforce ending.",
      "preview": {
        "off": "previews/cap_vanilla_title.png",
        "off_w": 256,
        "off_h": 144,
        "off_label": "Vanilla Title & Ending",
        "on": "previews/cap_barba_title.png",
        "on_w": 256,
        "on_h": 144,
        "on_label": "Barba Title & Ending",
        "frames": 64,
        "fps": 12
      }
    },
    {
      "id": "overworld_barba_trail",
      "code": "Wo",
      "category": "barba_core",
      "label": "Overworld Barba Avatar, Encounter Trail & Wyrmling",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Replaces Link's overworld sprite with Barba, adds a multi-segment trailing body in encounters, and swaps the wandering overworld Fairy for a Wyrmling."
    },
    {
      "id": "hud_and_death_polish",
      "code": "Wl",
      "category": "barba_core",
      "label": "Level-Up BREATH Pane & Fatal-Hit Silhouette",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Renames the level-up SWORD stat to BREATH with a fireball icon, and draws a custom 24x48 fatal-hit silhouette on death."
    },
    {
      "id": "cave_firelight",
      "code": "Wc",
      "category": "barba_core",
      "label": "Dark-Cave Envelope Firelight & Glow Halo",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "10-step fireball-driven ember/warm/golden-orange lighting in dark grottos without the Candle, $2001 emphasis below scanline 31, and a behind-BG glow halo around live fireballs."
    },
    {
      "id": "volley_count",
      "code": "Vc",
      "category": "barba_options",
      "label": "Volley Shot Count",
      "type": "int",
      "min": 1,
      "max": 5,
      "status": "planned",
      "vanilla": 1,
      "barba": 5,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Maximum simultaneous fireballs in a volley (Barba Edition uses 5 with BarbaLoadOk governor)."
    },
    {
      "id": "town_chaos",
      "code": "Tc",
      "category": "barba_options",
      "label": "Towns: Peaceful -> Chaos (Flee, Burn, Shouts & Combos)",
      "type": "bool",
      "status": "built",
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Barba-only town panic: villagers flee and burn with multi-row shouts and MULTI KILL / GODLIKE combo counters.",
      "preview": {
        "off": "previews/cap_vanilla_town_chaos.png",
        "off_w": 256,
        "off_h": 176,
        "off_label": "Peaceful Towns (Vanilla)",
        "on": "previews/cap_barba_town_chaos.png",
        "on_w": 256,
        "on_h": 176,
        "on_label": "Town Chaos (Flee & Burn)",
        "frames": 64,
        "fps": 20
      }
    },
    {
      "id": "error_ash_pile",
      "code": "We",
      "category": "barba_options",
      "label": "Error of Ruto Ash Pile",
      "type": "bool",
      "status": "built",
      "vanilla": false,
      "barba": true,
      "requires": [
        "town_chaos"
      ],
      "description": "Burning Error leaves an interactive ash pile ('I AM ASH PILE.')."
    },
    {
      "id": "burned_signs",
      "code": "Wn",
      "category": "barba_options",
      "label": "Burned Signs & Rotating Dialogue",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "Firebreath chars town and overworld signs with a scorched mark and rotating burned-sign messages."
    },
    {
      "id": "ngplus_mountain_melt",
      "code": "Nm",
      "category": "barba_options",
      "label": "NG+ Overworld Mountain Melting",
      "type": "bool",
      "status": "built",
      "coupled": true,
      "vanilla": false,
      "barba": true,
      "requires": [
        "barba_protagonist"
      ],
      "description": "On New Game+, pressing B on the overworld melts Mountain tiles into walkable Desert with live PPU attribute updates."
    },
    {
      "id": "scanline_scenery",
      "code": "Ws",
      "category": "world_presentation",
      "label": "Overworld & Encounter Scenery (IRQ Clouds, Foliage & Shimmer)",
      "type": "bool",
      "status": "built",
      "vanilla": false,
      "barba": true,
      "requires": [],
      "description": "Parallax clouds, swaying grass/sprigs, overworld foliage sway and desert/water sparkles, shimmering water/lava/flames, and rock-steady HUD split.",
      "preview": {
        "off": "previews/cap_vanilla_grass_walk.png",
        "off_w": 256,
        "off_h": 176,
        "off_label": "Vanilla Static Scenery",
        "on": "previews/cap_barba_grass_walk.png",
        "on_w": 256,
        "on_h": 176,
        "on_label": "IRQ Clouds & Overworld",
        "frames": 144,
        "fps": 20
      }
    },
    {
      "id": "enemy_polish",
      "code": "Wg",
      "category": "world_presentation",
      "label": "Geldarm Sand-Sink & Giant Bot Splat SFX",
      "type": "bool",
      "status": "built",
      "vanilla": false,
      "barba": true,
      "requires": [],
      "description": "Geldarm sinks into the desert sand before its death explosion, and Great Palace Giant Bot plays an APU splat when splitting into 5 small Bots."
    },
    {
      "id": "saria_foul_water",
      "code": "Wf",
      "category": "world_presentation",
      "label": "Saria River & Village Water: Blue Water -> Foul Water",
      "type": "bool",
      "status": "built",
      "vanilla": false,
      "barba": true,
      "requires": [
        "scanline_scenery"
      ],
      "description": "Replaces vanilla Saria's blue river and village water with animated green foul water and bridge guard warning.",
      "preview": {
        "off": "previews/cap_vanilla_saria_town.png",
        "off_w": 256,
        "off_h": 176,
        "off_label": "Vanilla Blue Water",
        "on": "previews/cap_barba_saria_town.png",
        "on_w": 256,
        "on_h": 176,
        "on_label": "Saria Foul Water",
        "frames": 64,
        "fps": 20
      }
    },
    {
      "id": "boss_meters",
      "code": "Wm",
      "category": "world_presentation",
      "label": "Boss Health Meter Style (Left 8-Pip / Dark Souls Bottom)",
      "type": "enum",
      "options": [
        "vanilla",
        "souls"
      ],
      "status": "toggleable",
      "vanilla": "vanilla",
      "barba": "souls",
      "requires": [],
      "description": "vanilla: Improved 8-pip left OAM meter (Gooma weapon priority, Lava Link A12 fix). souls: Full-width Dark Souls bottom bar with boss name above and white hit-flash drain.",
      "preview": {
        "off": "previews/cap_vanilla_boss_meter.png",
        "off_w": 256,
        "off_h": 208,
        "off_label": "Vanilla (8-Pip Left)",
        "on": "previews/cap_barba_boss_meter.png",
        "on_w": 256,
        "on_h": 208,
        "on_label": "Dark Souls Bottom Bar",
        "frames": 64,
        "fps": 20
      }
    },
    {
      "id": "crossover_portals",
      "code": "Tp",
      "category": "world_presentation",
      "label": "Crossover Portals (Barba's Arcade)",
      "type": "bool",
      "status": "toggleable",
      "vanilla": false,
      "barba": true,
      "requires": [],
      "description": "Enables the Rauru/Ruto portal doors into Barba's Arcade.",
      "preview": {
        "off": "previews/cap_vanilla_crossover_portals.png",
        "off_w": 256,
        "off_h": 176,
        "off_label": "Vanilla Town Door",
        "on": "previews/cap_barba_crossover_portals.png",
        "on_w": 256,
        "on_h": 176,
        "on_label": "Barba's Arcade",
        "frames": 96,
        "fps": 20
      }
    },
    {
      "id": "arcade_spells_and_gear",
      "code": "Ta",
      "category": "world_presentation",
      "label": "Arcade Spells, 2-Column Pause Menu & Cosmetic Gear Bar",
      "type": "bool",
      "status": "built",
      "vanilla": false,
      "barba": true,
      "requires": [
        "crossover_portals"
      ],
      "description": "Winning subgames in Barba's Arcade unlocks 11+ bonus spells in a 2-column pause menu and 5 stackable/swappable cosmetic trophies (HAT, MASK, HELM, TIE, BELT)."
    },
    {
      "id": "sampled_roar",
      "code": "Ar",
      "category": "world_presentation",
      "label": "Dragon Roar Audio: Native Noise -> Sampled DMC",
      "type": "bool",
      "status": "toggleable",
      "vanilla": false,
      "barba": true,
      "requires": [],
      "description": "Plays digitized dragon roar samples on title, item pickups, crystals, and boss intros.",
      "preview": {
        "on": "previews/roar_audio.png",
        "on_w": 56,
        "on_h": 28,
        "on_label": "DMC Roar Sample",
        "frames": 4,
        "fps": 6
      },
      "audio": {
        "off_synth": "noise_roar",
        "off_label": "Play Native Noise Roar",
        "on_wav": "previews/roar_sampled.wav",
        "on_label": "Play Sampled Roar",
        "pitch_control": true
      }
    },
    {
      "id": "game_over_portrait",
      "code": "Ap",
      "category": "world_presentation",
      "label": "Game Over Portrait: Vanilla Ganon -> Barba Link",
      "type": "bool",
      "status": "toggleable",
      "vanilla": false,
      "barba": true,
      "requires": [],
      "description": "Replaces Ganon's Game Over silhouette with the custom front-facing Link bust.",
      "preview": {
        "off": "previews/cap_vanilla_game_over.png",
        "off_w": 256,
        "off_h": 176,
        "off_label": "Vanilla Ganon",
        "on": "previews/cap_barba_game_over.png",
        "on_w": 256,
        "on_h": 176,
        "on_label": "Barba Link",
        "frames": 64,
        "fps": 15
      }
    },
    {
      "id": "game_over_laughs",
      "code": "Ag",
      "category": "world_presentation",
      "label": "Game Over Laughs: Ganon -> 5 Reworked Laughs",
      "type": "bool",
      "status": "toggleable",
      "vanilla": false,
      "barba": true,
      "requires": [],
      "description": "Replaces Ganon's 5-tick DPCM laugh sequence with five octave-up reworked Game Over laugh cues.",
      "audio": {
        "off_wav": "previews/ganon_laugh_seq.wav",
        "off_label": "Play Ganon 5-Laughs",
        "on_wav": "previews/link_laugh_seq.wav",
        "on_label": "Play Link 5-Laughs",
        "pitch_control": true
      }
    },
    {
      "id": "item_shuffle",
      "code": "Ri",
      "category": "randomizer",
      "label": "Key Item Shuffle",
      "type": "enum",
      "options": [
        "vanilla",
        "palaces",
        "full"
      ],
      "status": "planned",
      "vanilla": "vanilla",
      "barba": "vanilla",
      "requires": [],
      "description": "Shuffle palace key items (Candle, Glove, Raft, Boots, Flute, Cross, Hammer, Magic Key) across pedestals.",
      "preview": {
        "on": "previews/item_shuffle.png",
        "on_w": 32,
        "on_h": 32,
        "on_label": "Shuffled Pedestals",
        "frames": 4
      }
    },
    {
      "id": "spell_shuffle",
      "code": "Rs",
      "category": "randomizer",
      "label": "Town Spell Shuffle",
      "type": "bool",
      "status": "planned",
      "vanilla": false,
      "barba": false,
      "requires": [],
      "description": "Randomize which wise man teaches each spell across Hyrule's towns."
    },
    {
      "id": "boss_shuffle",
      "code": "Rb",
      "category": "randomizer",
      "label": "Palace Boss Shuffle",
      "type": "bool",
      "status": "planned",
      "vanilla": false,
      "barba": false,
      "requires": [],
      "description": "Shuffle palace guardians (Horsehead, Helmethead, Rebonack, Carock, Gooma, Lava Link)."
    },
    {
      "id": "portal_shuffle",
      "code": "Rp",
      "category": "randomizer",
      "label": "Portal Destination Shuffle",
      "type": "bool",
      "status": "planned",
      "vanilla": false,
      "barba": false,
      "requires": [
        "crossover_portals"
      ],
      "description": "Randomize which town doors host the 4-slot crossover portal table."
    },
    {
      "id": "xp_multiplier",
      "code": "Rx",
      "category": "randomizer",
      "label": "XP Gain Multiplier",
      "type": "enum",
      "options": [
        "1x",
        "2x",
        "4x"
      ],
      "status": "planned",
      "vanilla": "1x",
      "barba": "1x",
      "requires": [],
      "description": "Scale enemy XP drops for faster Free Enterprise-style pacing."
    },
    {
      "id": "open_great_palace",
      "code": "Ro",
      "category": "randomizer",
      "label": "Open Great Palace (Crystals Required)",
      "type": "int",
      "min": 0,
      "max": 6,
      "status": "planned",
      "vanilla": 6,
      "barba": 6,
      "requires": [],
      "description": "Number of palace crystals required to break the Great Palace barrier."
    },
    {
      "id": "palette_shuffle",
      "code": "Rc",
      "category": "randomizer",
      "label": "Seeded Palette Shuffle",
      "type": "bool",
      "status": "planned",
      "vanilla": false,
      "barba": false,
      "requires": [],
      "description": "Deterministically remix overworld, palace, and Barba scale palettes from the seed.",
      "preview": {
        "off": "previews/barba_hero.png",
        "off_w": 64,
        "off_h": 56,
        "off_label": "Classic Scales",
        "on": "previews/barba_palettes.png",
        "on_w": 64,
        "on_h": 56,
        "on_label": "Seeded Palettes",
        "frames": 4
      }
    }
  ],
  "presets": {
    "vanilla": {
      "values": {
        "barba_protagonist": false,
        "spell_scales": false,
        "spell_wyrmling": false,
        "spell_meteor": false,
        "spell_inferno": false,
        "upstab_breath": false,
        "downstab_stomp": false,
        "ironknuckle_rebound": false,
        "glove_bricks": false,
        "lava_wade": false,
        "palace_roar_shake": false,
        "rauru_sage_basement": false,
        "title_and_ending": false,
        "overworld_barba_trail": false,
        "hud_and_death_polish": false,
        "cave_firelight": false,
        "volley_count": 1,
        "town_chaos": false,
        "error_ash_pile": false,
        "burned_signs": false,
        "ngplus_mountain_melt": false,
        "scanline_scenery": false,
        "enemy_polish": false,
        "saria_foul_water": false,
        "boss_meters": "vanilla",
        "crossover_portals": false,
        "arcade_spells_and_gear": false,
        "sampled_roar": false,
        "game_over_portrait": false,
        "game_over_laughs": false,
        "item_shuffle": "vanilla",
        "spell_shuffle": false,
        "boss_shuffle": false,
        "portal_shuffle": false,
        "xp_multiplier": "1x",
        "open_great_palace": 6,
        "palette_shuffle": false
      },
      "flagstring": "BFE1|Vc1 Wm0 Ri0 Rx0 Ro6#BARBA2026"
    },
    "barba": {
      "values": {
        "barba_protagonist": true,
        "spell_scales": true,
        "spell_wyrmling": true,
        "spell_meteor": true,
        "spell_inferno": true,
        "upstab_breath": true,
        "downstab_stomp": true,
        "ironknuckle_rebound": true,
        "glove_bricks": true,
        "lava_wade": true,
        "palace_roar_shake": true,
        "rauru_sage_basement": true,
        "title_and_ending": true,
        "overworld_barba_trail": true,
        "hud_and_death_polish": true,
        "cave_firelight": true,
        "volley_count": 5,
        "town_chaos": true,
        "error_ash_pile": true,
        "burned_signs": true,
        "ngplus_mountain_melt": true,
        "scanline_scenery": true,
        "enemy_polish": true,
        "saria_foul_water": true,
        "boss_meters": "souls",
        "crossover_portals": true,
        "arcade_spells_and_gear": true,
        "sampled_roar": true,
        "game_over_portrait": true,
        "game_over_laughs": true,
        "item_shuffle": "vanilla",
        "spell_shuffle": false,
        "boss_shuffle": false,
        "portal_shuffle": false,
        "xp_multiplier": "1x",
        "open_great_palace": 6,
        "palette_shuffle": false
      },
      "flagstring": "BFE1|Bb S1 S2 S3 S4 Wu Wd Ir Gb Lw Wp Wr Wt Wo Wl Wc Vc5 Tc We Wn Nm Ws Wg Wf Wm1 Tp Ta Ar Ap Ag Ri0 Rx0 Ro6#BARBA2026"
    },
    "barba_lite": {
      "values": {
        "barba_protagonist": true,
        "spell_scales": true,
        "spell_wyrmling": true,
        "spell_meteor": true,
        "spell_inferno": true,
        "upstab_breath": true,
        "downstab_stomp": true,
        "ironknuckle_rebound": true,
        "glove_bricks": true,
        "lava_wade": true,
        "palace_roar_shake": true,
        "rauru_sage_basement": true,
        "title_and_ending": true,
        "overworld_barba_trail": true,
        "hud_and_death_polish": true,
        "cave_firelight": true,
        "volley_count": 5,
        "town_chaos": false,
        "error_ash_pile": false,
        "burned_signs": true,
        "ngplus_mountain_melt": true,
        "scanline_scenery": true,
        "enemy_polish": true,
        "saria_foul_water": true,
        "boss_meters": "souls",
        "crossover_portals": false,
        "arcade_spells_and_gear": false,
        "sampled_roar": true,
        "game_over_portrait": true,
        "game_over_laughs": true,
        "item_shuffle": "vanilla",
        "spell_shuffle": false,
        "boss_shuffle": false,
        "portal_shuffle": false,
        "xp_multiplier": "1x",
        "open_great_palace": 6,
        "palette_shuffle": false
      },
      "flagstring": "BFE1|Bb S1 S2 S3 S4 Wu Wd Ir Gb Lw Wp Wr Wt Wo Wl Wc Vc5 Wn Nm Ws Wg Wf Wm1 Ar Ap Ag Ri0 Rx0 Ro6#BARBA2026"
    },
    "chaos": {
      "values": {
        "barba_protagonist": true,
        "spell_scales": true,
        "spell_wyrmling": true,
        "spell_meteor": true,
        "spell_inferno": true,
        "upstab_breath": true,
        "downstab_stomp": true,
        "ironknuckle_rebound": true,
        "glove_bricks": true,
        "lava_wade": true,
        "palace_roar_shake": true,
        "rauru_sage_basement": true,
        "title_and_ending": true,
        "overworld_barba_trail": true,
        "hud_and_death_polish": true,
        "cave_firelight": true,
        "volley_count": 5,
        "town_chaos": true,
        "error_ash_pile": true,
        "burned_signs": true,
        "ngplus_mountain_melt": true,
        "scanline_scenery": true,
        "enemy_polish": true,
        "saria_foul_water": true,
        "boss_meters": "souls",
        "crossover_portals": true,
        "arcade_spells_and_gear": true,
        "sampled_roar": true,
        "game_over_portrait": true,
        "game_over_laughs": true,
        "item_shuffle": "full",
        "spell_shuffle": true,
        "boss_shuffle": true,
        "portal_shuffle": true,
        "xp_multiplier": "2x",
        "open_great_palace": 4,
        "palette_shuffle": true
      },
      "flagstring": "BFE1|Bb S1 S2 S3 S4 Wu Wd Ir Gb Lw Wp Wr Wt Wo Wl Wc Vc5 Tc We Wn Nm Ws Wg Wf Wm1 Tp Ta Ar Ap Ag Ri2 Rs Rb Rp Rx1 Ro4 Rc#BARBA2026"
    }
  }
};
