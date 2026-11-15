; Villager shout-word glyphs. Sprite tile bytes for 8x16 mode: bit 0 set
; selects the $1000 pattern table, which in towns is 4K CHR bank 7 (the town
; BG table, like native sprite 0's $C5). tools/assets.py writes each glyph
; into pair (tile AND $FE) of bank 7 ONLY, from the user's ROM font. Every
; pair was unused by all town rooms $00..$3E in a nametable census.
ShoutTile_S = $81
ShoutTile_H = $83
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
ShoutTile_W = $AB
ShoutTile_D = $AD
ShoutTile_E = $BB
ShoutTile_L = $BD
ShoutTile_P = $BF
; Town sprite palette 2 ($0F black, $16 red, $36 pale): letters use index 3,
; outline index 1. The same palette already draws the ash pile.
ShoutGlyphPalette = $02
