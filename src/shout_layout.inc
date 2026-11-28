; Villager shout-word glyphs. Sprite tile bytes for 8x16 mode: bit 0 set
; selects the $1000 pattern table, which in towns is 4K CHR bank 7 (the town
; BG table, like native sprite 0's $C5); even bytes select town sprite bank 6.
; tools/assets.py writes each glyph into pair (tile AND $FE) of that bank ONLY,
; from the user's ROM font. A byte draws BOTH tiles of its pair, so no pair may
; be town BG, a villager sprite, or a menu tile (audit: tools/assets.py).
ShoutTile_S = $81
ShoutTile_I = $85
ShoutTile_T = $87
ShoutTile_R = $89
ShoutTile_U = $8B
ShoutTile_N = $8D
ShoutTile_F = $93
ShoutTile_C = $95
ShoutTile_K = $9D
ShoutTile_O = $9F
ShoutTile_Bang = $A1
ShoutTile_M = $A3
ShoutTile_G = $A9
ShoutTile_A = $AB
ShoutTile_V = $7F
ShoutTile_E = $BB
ShoutTile_L = $BD
ShoutTile_P = $BF
; Even bytes: town sprite bank 6 ($0000 table), unused Link-only pairs. Bank 7
; has no free pairs left: $00-$27 are villager sprites (Fat Woman $11-$1F etc.).
; The counter draws digit 0 with ShoutTile_O to save a pair.
ShoutTile_B = $AE
ShoutTile_D = $B6
ShoutTile_H = $7C
ShoutTile_X = $66
ShoutTile_1 = $78
ShoutTile_2 = $7A
ShoutTile_3 = $B2
ShoutTile_4 = $B4
ShoutTile_5 = $94
ShoutTile_6 = $96
ShoutTile_7 = $98
ShoutTile_8 = $AC
ShoutTile_9 = $AA
; Town sprite palette 2 ($0F black, $16 red, $36 pale): letters use index 3,
; outline index 1. The same palette already draws the ash pile.
ShoutGlyphPalette = $02
