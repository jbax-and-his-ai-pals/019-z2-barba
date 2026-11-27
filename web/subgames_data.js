window.BARBA_SUBGAMES_DATA = {
  "version": 1,
  "games": [
    {
      "id": "waldo",
      "tab_label": "Where's Waldo?",
      "name": "Where's Barba?",
      "original": "Where's Waldo? (THQ / Bethesda)",
      "summary": "Replaces Waldo with Barba across the postcard title, Skill Select Wyrmling cursor, Lava ticket, Overworld Map, fleeing/shouting crowds, The Subway (Barba, Link & Flame), and the Rocket Slots Moon ending.",
      "scenes": [
        {
          "id": "title",
          "title": "Postcard Title Screen",
          "description": "Replaces the Where's Waldo? postcard stamp and title banner with There's Barba!.",
          "w": 256,
          "h": 224,
          "frames": 48,
          "fps": 10,
          "vanilla": {
            "label": "Where's Waldo? Title",
            "img": "previews/subgames/waldo_title_vanilla.png"
          },
          "modded": {
            "label": "There's Barba! Postcard",
            "img": "previews/subgames/waldo_title_modded.png"
          }
        },
        {
          "id": "skill_select",
          "title": "Skill Select (Wyrmling Cursor)",
          "description": "Swaps the magnifying cursor on Skill Select with an animated 16x16 Wyrmling.",
          "w": 256,
          "h": 224,
          "frames": 32,
          "fps": 12,
          "vanilla": {
            "label": "Vanilla Skill Select",
            "img": "previews/subgames/waldo_skill_select_vanilla.png"
          },
          "modded": {
            "label": "Animated Wyrmling Cursor",
            "img": "previews/subgames/waldo_skill_select_modded.png"
          }
        },
        {
          "id": "moon_ticket",
          "title": "One Ticket to the Lava",
          "description": "Peeking Barba head above the Moon/Lava rocket ticket before Stage 1.",
          "w": 256,
          "h": 224,
          "frames": 24,
          "fps": 12,
          "vanilla": {
            "label": "Vanilla Moon Ticket",
            "img": "previews/subgames/waldo_moon_ticket_vanilla.png"
          },
          "modded": {
            "label": "One Ticket to the Lava",
            "img": "previews/subgames/waldo_moon_ticket_modded.png"
          }
        },
        {
          "id": "overworld_map",
          "title": "Overworld Map Walk",
          "description": "48x48 full-body Barba walking across the overworld map between stages.",
          "w": 256,
          "h": 224,
          "frames": 40,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla Waldo Map Walk",
            "img": "previews/subgames/waldo_overworld_map_vanilla.png"
          },
          "modded": {
            "label": "Full-Body Walking Barba",
            "img": "previews/subgames/waldo_overworld_map_modded.png"
          }
        },
        {
          "id": "train_station",
          "title": "Fleeing & Shouting Crowds",
          "description": "Crowd bystanders flee from hidden 16x16 Barba with panic shouts (BARBA!, RUN!, HELP!).",
          "w": 256,
          "h": 224,
          "frames": 48,
          "fps": 15,
          "vanilla": {
            "label": "Static Vanilla Crowd",
            "img": "previews/subgames/waldo_train_station_vanilla.png"
          },
          "modded": {
            "label": "Panic Shouts & Fleeing Crowd",
            "img": "previews/subgames/waldo_train_station_modded.png"
          }
        },
        {
          "id": "subway",
          "title": "The Subway",
          "description": "Replaces Waldo, Odlaw, and the Glasses in the Subway maze with Barba, Link, and a Barba Flame.",
          "w": 256,
          "h": 224,
          "frames": 24,
          "fps": 12,
          "vanilla": {
            "label": "Waldo, Odlaw & Glasses",
            "img": "previews/subgames/waldo_subway_vanilla.png"
          },
          "modded": {
            "label": "Barba, Link & Barba Flame",
            "img": "previews/subgames/waldo_subway_modded.png"
          }
        },
        {
          "id": "slots",
          "title": "Rocket Slots Jackpot",
          "description": "Spinning Rocket Slots reels locking onto three Barba portraits for the jackpot.",
          "w": 256,
          "h": 224,
          "frames": 96,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla Waldo Rocket Slots",
            "img": "previews/subgames/waldo_slots_vanilla.png"
          },
          "modded": {
            "label": "3-Barba Rocket Slots Jackpot",
            "img": "previews/subgames/waldo_slots_modded.png"
          }
        },
        {
          "id": "moon_ending",
          "title": "Moon Ending Celebration",
          "description": "Space-helmeted Barba leaps from the rocket onto the Moon, lands, and unleashes a screen-shaking roar.",
          "w": 256,
          "h": 224,
          "frames": 100,
          "fps": 12,
          "vanilla": {
            "label": "Vanilla Waldo Moon Ending",
            "img": "previews/subgames/waldo_moon_ending_vanilla.png"
          },
          "modded": {
            "label": "Barba Moon Jump, Landing & Roar",
            "img": "previews/subgames/waldo_moon_ending_modded.png"
          }
        }
      ]
    },
    {
      "id": "feud",
      "tab_label": "Family Feud",
      "name": "Barba's Beef",
      "original": "Family Feud (GameTek)",
      "summary": "Barba variants square off against Zelda II bosses, enemies, and townsfolk across randomized stage lineups, Face-Offs, ordinal FIRST-FIFTH FEUD floor banners, and Z2 trivia.",
      "scenes": [
        {
          "id": "title",
          "title": "Title Screen",
          "description": "Barba's Beef marquee replacing the vanilla Family Feud title screen.",
          "w": 256,
          "h": 224,
          "frames": 24,
          "fps": 12,
          "vanilla": {
            "label": "Vanilla Family Feud",
            "img": "previews/subgames/feud_title_vanilla.png"
          },
          "modded": {
            "label": "Barba's Beef Marquee",
            "img": "previews/subgames/feud_title_modded.png"
          }
        },
        {
          "id": "overview",
          "title": "Stage Overview & Ordinal Banner",
          "description": "All 10 randomized Barba & Zelda II contestants on stage with the FIRST FEUD stage-floor banner.",
          "w": 256,
          "h": 224,
          "frames": 32,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla Family Overview",
            "img": "previews/subgames/feud_overview_vanilla.png"
          },
          "modded": {
            "label": "Barba vs Z2 + FIRST FEUD",
            "img": "previews/subgames/feud_overview_modded.png"
          }
        },
        {
          "id": "faceoff",
          "title": "Face-Off Podium",
          "description": "Head-to-head buzzer podium pitting randomized Barba vs Zelda II contestants on Z2 survey questions.",
          "w": 256,
          "h": 224,
          "frames": 32,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla Face-Off",
            "img": "previews/subgames/feud_faceoff_vanilla.png"
          },
          "modded": {
            "label": "Barba vs Z2 Face-Off",
            "img": "previews/subgames/feud_faceoff_modded.png"
          }
        },
        {
          "id": "stage_barba",
          "title": "Barba Family Podium",
          "description": "Barba team podium with animated idle roars and head-wiggles during main rounds.",
          "w": 256,
          "h": 224,
          "frames": 32,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla Left Family",
            "img": "previews/subgames/feud_stage_barba_vanilla.png"
          },
          "modded": {
            "label": "Barba Family Podium",
            "img": "previews/subgames/feud_stage_barba_modded.png"
          }
        },
        {
          "id": "stage_z2",
          "title": "Zelda II Opposing Podium",
          "description": "Opposing Zelda II cast podium featuring full-height bosses, knights, and villagers.",
          "w": 256,
          "h": 224,
          "frames": 32,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla Right Family",
            "img": "previews/subgames/feud_stage_z2_vanilla.png"
          },
          "modded": {
            "label": "Zelda II Opposing Cast",
            "img": "previews/subgames/feud_stage_z2_modded.png"
          }
        },
        {
          "id": "fast_money",
          "title": "Fast Money Final Round",
          "description": "Blue-background Fast Money final round with Zelda II survey questions and Barba's portrait on the clock.",
          "w": 256,
          "h": 224,
          "frames": 32,
          "fps": 10,
          "vanilla": {
            "label": "Vanilla Fast Money",
            "img": "previews/subgames/feud_fast_money_vanilla.png"
          },
          "modded": {
            "label": "Z2 Fast Money & Barba",
            "img": "previews/subgames/feud_fast_money_modded.png"
          }
        },
        {
          "id": "lose_excuse",
          "title": "Lose Excuse Screen",
          "description": "End-of-game lose screen replacing vanilla's family obligations / tax considerations excuses with custom Zelda II reasons and opposing family names.",
          "w": 256,
          "h": 224,
          "frames": 16,
          "fps": 10,
          "vanilla": {
            "label": "Vanilla Lose Excuse",
            "img": "previews/subgames/feud_lose_excuse_vanilla.png"
          },
          "modded": {
            "label": "Zelda II Lose Excuse",
            "img": "previews/subgames/feud_lose_excuse_modded.png"
          }
        }
      ]
    },
    {
      "id": "dk",
      "tab_label": "Donkey Kong",
      "name": "Barba Kong",
      "original": "Donkey Kong (Nintendo)",
      "summary": "Lil' Barba climbs construction girders to rescue Princess Zelda from Big Bad Link, wielding Flame Fury dragon breath against Z2 Bits, Bubbles, Bombs, and Shields.",
      "scenes": [
        {
          "id": "title",
          "title": "Title Screen",
          "description": "Barba Kong title screen with animated fireball selector cursor.",
          "w": 256,
          "h": 224,
          "frames": 24,
          "fps": 12,
          "vanilla": {
            "label": "Vanilla Donkey Kong",
            "img": "previews/subgames/dk_title_vanilla.png"
          },
          "modded": {
            "label": "Barba Kong + Fireball Cursor",
            "img": "previews/subgames/dk_title_modded.png"
          }
        },
        {
          "id": "stage_25m",
          "title": "25m Girders (Big Bad Link & Zelda)",
          "description": "Lil' Barba at the base of 25m while Big Bad Link hurls hazards and Princess Zelda waits above.",
          "w": 256,
          "h": 224,
          "frames": 40,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla 25m (Mario & DK)",
            "img": "previews/subgames/dk_stage_25m_vanilla.png"
          },
          "modded": {
            "label": "Lil' Barba, Big Bad Link & Zelda",
            "img": "previews/subgames/dk_stage_25m_modded.png"
          }
        },
        {
          "id": "fury_25m",
          "title": "Flame Fury Breath",
          "description": "Hammer pickup transformed into alternating straight-forward and cone firebreath.",
          "w": 256,
          "h": 224,
          "frames": 40,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla Hammer Swing",
            "img": "previews/subgames/dk_fury_25m_vanilla.png"
          },
          "modded": {
            "label": "Flame Fury Firebreath",
            "img": "previews/subgames/dk_fury_25m_modded.png"
          }
        },
        {
          "id": "stage_75m",
          "title": "75m Elevators & Z2 Bombs",
          "description": "Elevator stage upgraded with Zelda II Shields and falling Bombs.",
          "w": 256,
          "h": 224,
          "frames": 32,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla 75m Springs",
            "img": "previews/subgames/dk_stage_75m_vanilla.png"
          },
          "modded": {
            "label": "Z2 Shields & Bombs",
            "img": "previews/subgames/dk_stage_75m_modded.png"
          }
        },
        {
          "id": "stage_100m",
          "title": "100m Rivets & Z2 Bubbles",
          "description": "Final rivets stage with Big Bad Link and hovering Zelda II Bubbles.",
          "w": 256,
          "h": 224,
          "frames": 32,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla 100m Fireballs",
            "img": "previews/subgames/dk_stage_100m_vanilla.png"
          },
          "modded": {
            "label": "Big Bad Link & Z2 Bubbles",
            "img": "previews/subgames/dk_stage_100m_modded.png"
          }
        }
      ]
    },
    {
      "id": "duck",
      "tab_label": "Duck Hunt",
      "name": "Villager Hunt (Barba's Hunt)",
      "original": "Duck Hunt (Nintendo)",
      "summary": "Zelda II forest, grass, and desert biomes replace the meadow while flying villagers, Octoroks, and Moas take flight\u2014plus smooth D-pad fireball bursts, Barba P-Bag catches, and Villainous Link laughs.",
      "scenes": [
        {
          "id": "title",
          "title": "Villager Hunt Title Screen",
          "description": "Custom Villager Hunt title banner and game selection menu.",
          "w": 256,
          "h": 224,
          "frames": 24,
          "fps": 12,
          "vanilla": {
            "label": "Vanilla Duck Hunt",
            "img": "previews/subgames/duck_title_vanilla.png"
          },
          "modded": {
            "label": "Villager Hunt Banner",
            "img": "previews/subgames/duck_title_modded.png"
          }
        },
        {
          "id": "barba_intro",
          "title": "Barba Forest Intro & Downstab",
          "description": "Full-body Barba trots across the Z2 forest clearing, sniffs, roars, and leaps down behind the bushes with the Z2 downstab pose.",
          "w": 256,
          "h": 224,
          "frames": 90,
          "fps": 12,
          "vanilla": {
            "label": "Vanilla Dog Sniff & Jump",
            "img": "previews/subgames/duck_barba_intro_vanilla.png"
          },
          "modded": {
            "label": "Barba Intro & Z2 Downstab",
            "img": "previews/subgames/duck_barba_intro_modded.png"
          }
        },
        {
          "id": "game_a_forest",
          "title": "Forest Clearing & Fireball Burst",
          "description": "A flying Great Palace Fokka soars past Z2 forest trunks while the D-pad smoothly tracks it and fires a fireball burst, compared against a vanilla Zapper shot.",
          "w": 256,
          "h": 224,
          "frames": 48,
          "fps": 20,
          "vanilla": {
            "label": "Vanilla Meadow & Zapper Shot",
            "img": "previews/subgames/duck_game_a_forest_vanilla.png"
          },
          "modded": {
            "label": "Smooth Aim & Fireball Burst (Fokka)",
            "img": "previews/subgames/duck_game_a_forest_modded.png"
          }
        },
        {
          "id": "barba_catch",
          "title": "Hit Catch: Barba & P-Bag",
          "description": "Scoring a hit brings out Barba popping up behind the bushes holding a Zelda II P-Bag in place of the vanilla dog holding a duck.",
          "w": 256,
          "h": 224,
          "frames": 36,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla Dog Holding Duck",
            "img": "previews/subgames/duck_barba_catch_vanilla.png"
          },
          "modded": {
            "label": "Barba Holding Z2 P-Bag",
            "img": "previews/subgames/duck_barba_catch_modded.png"
          }
        },
        {
          "id": "link_laugh",
          "title": "Miss Laugh: Villainous Link",
          "description": "Missing all shots lets the target escape and brings out Villainous Link popping up behind the bushes to laugh.",
          "w": 256,
          "h": 224,
          "frames": 42,
          "fps": 18,
          "vanilla": {
            "label": "Vanilla Dog Laugh",
            "img": "previews/subgames/duck_link_laugh_vanilla.png"
          },
          "modded": {
            "label": "Villainous Link Laugh",
            "img": "previews/subgames/duck_link_laugh_modded.png"
          }
        },
        {
          "id": "biomes",
          "title": "Biome Cycle: Grass, Desert & Forest",
          "description": "Round progression cycles through Zelda II Overworld Grass (Round 2), Desert (Round 3), and Forest (Round 4) scenery.",
          "w": 256,
          "h": 224,
          "frames": 162,
          "fps": 15,
          "vanilla": {
            "label": "Repeated Vanilla Meadow (R2-R4)",
            "img": "previews/subgames/duck_biomes_vanilla.png"
          },
          "modded": {
            "label": "Z2 Grass, Desert & Forest Cycle",
            "img": "previews/subgames/duck_biomes_modded.png"
          }
        },
        {
          "id": "game_c",
          "title": "Game C: Octoroks, Moas & Plates",
          "description": "Clay shooting replaced with flying Zelda II Octoroks, Moas, and Palace Plates.",
          "w": 256,
          "h": 224,
          "frames": 36,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla Clay Pigeons",
            "img": "previews/subgames/duck_game_c_vanilla.png"
          },
          "modded": {
            "label": "Octoroks, Moas & Palace Plates",
            "img": "previews/subgames/duck_game_c_modded.png"
          }
        }
      ]
    },
    {
      "id": "wheel",
      "tab_label": "Wheel of Fortune",
      "name": "Wheel of Barba",
      "original": "Wheel of Fortune (GameTek)",
      "summary": "Updates Screen 1 credits to BARBA EDITION and HYRULE PALACE STUDIOS, plus the setup board and main puzzle stage starring full-body Barba against Dark Link across Zelda II trivia puzzles.",
      "scenes": [
        {
          "id": "title",
          "title": "Title Credits Screen",
          "description": "Updates the Screen 1 logo to WHEEL OF BARBA and rewrites the credits to HYRULE PALACE STUDIOS, A UNIT OF PALACE VI DRAGON, and 1990 BARBA VS DARK LINK.",
          "w": 256,
          "h": 224,
          "frames": 64,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla Wheel of Fortune Credits",
            "img": "previews/subgames/wheel_title_vanilla.png"
          },
          "modded": {
            "label": "WHEEL OF BARBA Credits",
            "img": "previews/subgames/wheel_title_modded.png"
          }
        },
        {
          "id": "menu",
          "title": "Game Setup Menu",
          "description": "Setup board themed to WHEEL OF BARBA EDITION.",
          "w": 256,
          "h": 224,
          "frames": 24,
          "fps": 12,
          "vanilla": {
            "label": "Vanilla Setup Menu",
            "img": "previews/subgames/wheel_menu_vanilla.png"
          },
          "modded": {
            "label": "WHEEL OF BARBA EDITION",
            "img": "previews/subgames/wheel_menu_modded.png"
          }
        },
        {
          "id": "board",
          "title": "Main Puzzle Board (Barba & Dark Link)",
          "description": "Main board with full-body Barba host, DARK LINK contestant, and custom Zelda II puzzles.",
          "w": 256,
          "h": 224,
          "frames": 32,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla Board & Vanna",
            "img": "previews/subgames/wheel_board_vanilla.png"
          },
          "modded": {
            "label": "Barba, Dark Link & Z2 Puzzle",
            "img": "previews/subgames/wheel_board_modded.png"
          }
        },
        {
          "id": "barba_walk",
          "title": "Barba Unveiling Letters",
          "description": "Full-body Barba striding briskly across the puzzle stage to turn letters.",
          "w": 256,
          "h": 224,
          "frames": 32,
          "fps": 15,
          "vanilla": {
            "label": "Vanilla Hostess Walk",
            "img": "previews/subgames/wheel_barba_walk_vanilla.png"
          },
          "modded": {
            "label": "Full-Body Barba Walk",
            "img": "previews/subgames/wheel_barba_walk_modded.png"
          }
        }
      ]
    }
  ]
};
