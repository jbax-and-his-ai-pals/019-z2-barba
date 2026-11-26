window.TITLE_REVIEW_DATA = {
  "done_games": [
    {
      "id": "dk",
      "name": "Barba Kong",
      "note": "Title screen & arcade cabinet done."
    },
    {
      "id": "duck",
      "name": "Barba's Hunt",
      "note": "Title screen & forest sprites done."
    },
    {
      "id": "feud",
      "name": "Barba's Beef",
      "note": "Title, cast & ordinal rounds done."
    },
    {
      "id": "waldo",
      "name": "Where's Barba?",
      "note": "Title screen & crowd tagger done."
    }
  ],
  "jason_mask_lab": [
    {
      "id": "jmask_lab",
      "name": "Jason Mask Lab (Friday the 13th Intro)",
      "status": "prototype",
      "status_label": "Dedicated Mask R&D",
      "summary": "Fitting a round human hockey mask onto Barba\u2019s elongated 32x16 dragon head & snout.",
      "context_note": "4 mask geometry studies at 4x scale (white mask + crimson chevrons on Barba\u2019s head).",
      "current": [
        {
          "id": "f13_cur_mask",
          "label": "Vanilla Intro Mask (Frame 120)",
          "img": "previews/titles/f13_current_mask.png",
          "caption": "Vanilla blue Jason hockey mask"
        }
      ],
      "candidates": [
        {
          "id": "jmask_1",
          "label": "Study 1: Snout-Wrap Contoured Mask",
          "img": "previews/titles/jmask_1.png",
          "caption": "32x16 Barba dragon head at 4x scale."
        },
        {
          "id": "jmask_2",
          "label": "Study 2: Upper Visor (Exposed Snout & Jaw)",
          "img": "previews/titles/jmask_2.png",
          "caption": "32x16 Barba dragon head at 4x scale."
        },
        {
          "id": "jmask_3",
          "label": "Study 3: Roaring Open-Jaw + Hinged Mask",
          "img": "previews/titles/jmask_3.png",
          "caption": "32x16 Barba dragon head at 4x scale."
        },
        {
          "id": "jmask_4",
          "label": "Study 4: Full-Face Plate + Exposed Horns",
          "img": "previews/titles/jmask_4.png",
          "caption": "32x16 Barba dragon head at 4x scale."
        }
      ]
    }
  ],
  "games": [
    {
      "id": "f13",
      "name": "Friday the 13th: Camp Barba",
      "status": "prototype",
      "status_label": "CAMP BARBA + Left Barba",
      "summary": "Folded Candidate B\u2019s left-side Barba (now in vanilla Barba colors) with CAMP BARBA in the jagged F13 brush font striped with Barba\u2019s torso/head palette. Jason mask moved to its own Jason Mask Lab tab.",
      "context_note": "F13 uses 4KB CHR bank 7 for the blood-red logo ($C0..$FE) and sprite palettes for Barba.",
      "current": [
        {
          "id": "f13_cur_title",
          "label": "Current Title (Frame 420)",
          "img": "previews/titles/f13_current_title.png",
          "caption": "Vanilla FRIDAY THE 13TH logo"
        }
      ],
      "candidates": [
        {
          "id": "f13_cand_a",
          "label": "Candidate A: Attack Barba + Striped CAMP BARBA",
          "img": "previews/titles/f13_cand_a.png",
          "caption": "Left-side Barba in vanilla colors + CAMP BARBA in F13 brush font with Barba torso/head striping."
        },
        {
          "id": "f13_cand_b",
          "label": "Candidate B: Idle Barba + Gold-Band CAMP BARBA",
          "img": "previews/titles/f13_cand_b.png",
          "caption": "Idle Barba pose + alternate gold/crimson Barba palette striping on CAMP BARBA."
        }
      ]
    },
    {
      "id": "smb",
      "name": "Super Barba Bros.",
      "status": "fixed_needs_title",
      "status_label": "Ready for SUPER BARBA BROS. Sign",
      "summary": "BARBA now matches the exact condensed beveled font & style of BROS. Demo mode keeps tiny Wyrmling (it grows on mushroom/jar pickup). Note: the \"10\" + tile above Barba in the roar shot is SMB\u2019s \"1000\" floating score popup on the first grow-toggle frame.",
      "context_note": "B, R, and A glyphs sampled directly from BROS. / MARIO on the wooden title sign.",
      "current": [
        {
          "id": "smb_cur_title",
          "label": "Current Title (Demo Wyrmling)",
          "img": "previews/titles/smb_current_title.png",
          "caption": "Still says SUPER MARIO BROS."
        },
        {
          "id": "smb_fix_roar",
          "label": "Mushroom Roar Frame (1000 popup)",
          "img": "previews/titles/smb_fixed_roar.png",
          "caption": "Roaring on first grow frame (\"10\" is the 1000 score popup)"
        },
        {
          "id": "smb_fix_big",
          "label": "Full-Body Super Barba",
          "img": "previews/titles/smb_fixed_big.png",
          "caption": "Crisp 24x32 + trail Super Barba"
        }
      ],
      "candidates": [
        {
          "id": "smb_cand_a",
          "label": "Candidate A: SUPER BARBA BROS. Sign",
          "img": "previews/titles/smb_cand_a.png",
          "caption": "BARBA matched pixel-for-pixel to BROS. font, bevels, and 3D drop shadow; keeps tiny Barba in demo mode."
        }
      ]
    },
    {
      "id": "mtpo",
      "name": "Barba's Punch-Out!!",
      "status": "needs_rework",
      "status_label": "Needs Rework (Z2 Game Over Link)",
      "summary": "Rebuilt Link portrait from Zelda 2\u2019s Game Over Link silhouette + EVIL LINK matching MIKE TYSON positioning.",
      "context_note": "Uses game_over_art.compile_game_over_link() 80x96 silhouette inside the Title2 portrait frame.",
      "current": [
        {
          "id": "mtpo_cur_t2",
          "label": "Current Title2 (Evil Link)",
          "img": "previews/titles/mtpo_current_title2.png",
          "caption": "Rough Link portrait & blocky font"
        },
        {
          "id": "mtpo_zoom",
          "label": "Context: Current Link Portrait (2x)",
          "img": "previews/titles/mtpo_link_zoom.png",
          "caption": "Flat green silhouette needs Z2 Game Over detail"
        }
      ],
      "candidates": [
        {
          "id": "mtpo_cand_a",
          "label": "Candidate A: Z2 Game Over Link Silhouette + EVIL LINK",
          "img": "previews/titles/mtpo_cand_a.png",
          "caption": "Looming Z2 Game Over Link silhouette + EVIL LINK centered in MIKE TYSON position."
        }
      ]
    },
    {
      "id": "mm2",
      "name": "Mega Barba 2 (Barba Man 2)",
      "status": "discussion",
      "status_label": "Fixed Clipped A + 2 Rooftop Directions",
      "summary": "Fixed the missing top-right corner of the trailing A in MEGA BARBA II (tools/mm2_art.py). Two rooftop character directions below for iteration: full-body Barba with junction/tail vs Mega Man with Barba snout sticking out of the helmet.",
      "context_note": "Logo fix is already applied in tools/mm2_art.py; zoom below previews the unclipped A.",
      "current": [
        {
          "id": "mm2_cur",
          "label": "Current ROM Title (Clipped A)",
          "img": "previews/titles/mm2_current_title.png",
          "caption": "Pre-fix capture (trailing A top-right clipped)"
        },
        {
          "id": "mm2_zoom",
          "label": "Fixed Logo Zoom (Unclipped A)",
          "img": "previews/titles/mm2_logo_zoom.png",
          "caption": "Fixed in mm2_art.py: trailing A + shadow fully inside nametable span"
        }
      ],
      "candidates": [
        {
          "id": "mm2_cand_a",
          "label": "Candidate A: Full-Body Barba (Junction + Tail)",
          "img": "previews/titles/mm2_cand_a.png",
          "caption": "32x40 full-body Barba with neck junction and tail on the skyscraper rooftop."
        },
        {
          "id": "mm2_cand_b",
          "label": "Candidate B: Mega Man Helmet + Barba Snout",
          "img": "previews/titles/mm2_cand_b.png",
          "caption": "Mega Man armor & blue helmet with Barba\u2019s dragon snout poking out."
        }
      ]
    },
    {
      "id": "wheel",
      "name": "Wheel of Barba",
      "status": "align",
      "status_label": "Aligned: WHEEL OF BARBA",
      "summary": "Replaces FORTUNE with BARBA on both Screen 1 and the Screen 2 bottom wheel arc, preserving the exact fonts, colors, and curved wheel geometry.",
      "context_note": "Screen 1 keeps pink/white-outlined WHEEL \u2022 of \u2022 BARBA; Screen 2 curves BARBA along the bottom arc in grey/orange.",
      "current": [
        {
          "id": "wheel_cur_s1",
          "label": "Current Screen 1 (Splash)",
          "img": "previews/titles/wheel_current_s1.png",
          "caption": "WHEEL of FORTUNE / BARBA EDITION"
        },
        {
          "id": "wheel_cur_s2",
          "label": "Current Screen 2 (Big Wheel)",
          "img": "previews/titles/wheel_current_s2.png",
          "caption": "Still says FAMILY EDITION + WHEEL OF FORTUNE"
        }
      ],
      "candidates": [
        {
          "id": "wheel_cand_s1",
          "label": "Candidate Screen 1: WHEEL \u2022 of \u2022 BARBA",
          "img": "previews/titles/wheel_cand_s1.png",
          "caption": "Replaces FORTUNE with BARBA in the exact pink/white-outline font."
        },
        {
          "id": "wheel_cand_s2",
          "label": "Candidate Screen 2: Curved Bottom-Arc BARBA",
          "img": "previews/titles/wheel_cand_s2.png",
          "caption": "Replaces bottom-arc FORTUNE with curved BARBA in grey + orange outline + shadow."
        }
      ]
    },
    {
      "id": "zelda",
      "name": "The Legend of Barba (Zelda 1)",
      "status": "not_started",
      "status_label": "ZELDA-Matched Font + White-Foam Lava",
      "summary": "BARBA now matches ZELDA\u2019s chiseled serif font, warm brown fill, and 3D black shadow. Candidate B preserves the vanilla waterfall\u2019s bright white foam highlights inside the flowing lava.",
      "context_note": "Zelda 1 uses CHR-RAM; title tiles and waterfall palette patch cleanly in pack_zelda.py.",
      "current": [
        {
          "id": "zelda_cur",
          "label": "Current Title (Vanilla Z1)",
          "img": "previews/titles/zelda_current_title.png",
          "caption": "Unmodified THE LEGEND OF ZELDA"
        }
      ],
      "candidates": [
        {
          "id": "zelda_cand_a",
          "label": "Candidate A: THE LEGEND OF BARBA (ZELDA Font)",
          "img": "previews/titles/zelda_cand_a.png",
          "caption": "Chiseled brown+black BARBA matching ZELDA\u2019s look & feel."
        },
        {
          "id": "zelda_cand_b",
          "label": "Candidate B: Lava Falls (With White Foam)",
          "img": "previews/titles/zelda_cand_b.png",
          "caption": "Flowing Palace VI crimson/amber lava keeping the vanilla waterfall\u2019s white foam."
        }
      ]
    }
  ]
};
