; Nonblocking town screams in the unused top HUD row, above the sprite-0 split.
; Never touch the dialogue/movement-lock state. Native VBlank consumes packets.
; A short word ("RUN!", "FUCK!") also follows the shouting villager as
; sprites; see ShoutWord below and docs/TOWNS.md.
.export BarbaShouts
.include "shout_layout.inc"
SHOUT_READY = $05EA
SHOUT_TIMER = $6460
SHOUT_COOLDOWN = $6461
SHOUT_REQUEST = $6462
SHOUT_WORLD = $6463
SHOUT_ROOM = $6464
SHOUT_SLOT = $6465          ; actor slot X that raised the current shout
TALK_LATCH = $6466
SHOUT_WORD = $6467          ; 0 none, else word 1..8 drawn above SHOUT_SLOT
SHOUT_WORD_TIMER = $6468    ; frames left for the word
SHOUT_CYCLE = $6469         ; rotating offset so repeated shouts cycle phrases
; Seven OAM entries via ShoutOam ($00, $28, $2C, $30, $34, $40, $DC): low slots
; keep town shouts above clouds/villagers/fireballs; yielded to enemy projectiles.
SHOUT_WORD_TIME = $64

BarbaShouts:
    lda $070F
    ora $05EC           ; SCALES_SEEN
    bne @go6
    lda SHOUT_READY
    beq @go6
    lda $0707
    cmp SHOUT_WORLD
    bne @go6
    cmp #$00
    bne @not_castle
    lda $0706
    ora $0561
    beq @go6
    rts
@not_castle:
    cmp #$03
    bcc @go6
    cmp #$05
    bne @skip6
    lda $A1
    cmp #$23
    bne @skip6
@go6:
    lda #>(BarbaShouts6-1)
    pha
    lda #<(BarbaShouts6-1)
    pha
    jmp SwapToBank6
@skip6:
    rts

.segment "BANK6"
; Trigger Barba's "OOPS..." shout in North Palace when Zelda is scorched.
CastleZeldaShout:
    lda SHOUT_READY
    beq @done
    lda #$FF
    sta SHOUT_SLOT
    lda #$0A
    sta SHOUT_WORD
    lda #SHOUT_WORD_TIME
    sta SHOUT_WORD_TIMER
@done:
    rts

BarbaShouts6:
    txa
    pha
    tya
    pha
    jsr ScalesTick      ; SCALES cast/hit feedback (bank 6, src/scales.inc)
    jsr DarkLinkFireCheck
    lda SHOUT_READY
    cmp #$01
    beq @scene
    lda #$01
    sta SHOUT_READY
    jsr @reset
@scene:
    lda $0707
    cmp SHOUT_WORLD
    bne @changed
    lda $0561
    cmp SHOUT_ROOM
    beq @town
@changed:
    jsr @reset
@town:
    lda $0707
    cmp #$03
    bcs @done
    cmp #$00
    bne @mode
    lda $0706
    ora $0561
    bne @done
@mode:
    lda $0736
    cmp #$0B
    bne @busy
    lda $F7
    and #$08
    bne :+
    lda #$00
    sta TALK_LATCH
:
    lda $074C
    ora $DE
    ora $0726
    bne @busy
    lda $0707
    beq @run_shout
    jsr ComboTick
    bcc @run_shout
    lda #$00
    sta SHOUT_WORD
    beq @after_word
@run_shout:
    jsr ShoutWord
@after_word:
    lda SHOUT_COOLDOWN
    beq :+
    dec SHOUT_COOLDOWN
:
    lda SHOUT_REQUEST
    beq @done
    lda #$78
    sta SHOUT_COOLDOWN
    lda #$00
    sta SHOUT_REQUEST
    beq @done
@busy:
    ; Dialogue, menus and transitions. Talking skips the native OAM clear,
    ; so the word must leave OAM itself here instead of freezing on screen.
    jsr ShoutWordCancel
    jsr ComboHide
@done:
    pla
    tay
    pla
    tax
    jmp $FFC5
@reset:
    ; Scene change: drop the word. The native NMI already cleared last
    ; frame's sprites; never write OAM here, the new scene may own $E0.
    lda #$00
    sta SHOUT_WORD
    sta SHOUT_TIMER
    sta SHOUT_COOLDOWN
    sta SHOUT_REQUEST
    sta TALK_LATCH
    sta SHOUT_CYCLE
    lda $0707
    sta SHOUT_WORLD
    lda $0561
    sta SHOUT_ROOM
    jmp ComboReset

; Draw the live word above its villager in normal town play. Runs after the
; native actor loop ($D504) moved and drew this frame's actors, so the word
; uses the same positions as the villager's own sprites. X/Y are scratch.
ShoutWord:
    lda SHOUT_WORD
    bne @start
    rts
@cancel:
    jmp ShoutWordCancel
@hide:
    jmp ShoutWordHide
@start:
    ldx SHOUT_SLOT
    bpl :+
    jmp @player_shout
:
    ; Cancel for good when the slot stops being that living, fleeing or
    ; calm villager: door/offscreen despawn ($B6) or burn and ash ($AF).
    lda $B6,x
    cmp #$01
    bne @cancel
    lda $AF,x
    beq :+
    cmp #$80
    beq :+
    cmp #$82
    bne @cancel
:
    dec SHOUT_WORD_TIMER
    beq @cancel
    ; Yield the shared OAM window to any native enemy projectile.
    ldy #$05
:
    lda $0087,y
    bne @hide
    dey
    bpl :-
    ; Glyphs use the lower half of each 8x16 pair. Place the letters
    ; at villager Y-24..Y-17 to reduce overlap with Barba.
    lda $2A,x
    sec
    sbc #$20
    bcc @hide
    cmp #$20                    ; keep clear of the HUD above the split
    bcc @hide
    sta $00
    ; 16-bit screen X of the villager's left edge (same math as TownAsh).
    lda $4E,x
    sec
    sbc $072C
    sta $01
    lda $3C,x
    sbc $072A
    beq @onscreen
    ; Allow a villager up to 16 px past the left edge: its word still
    ; straddles the edge and each glyph is clipped below.
    cmp #$FF
    bne @hide           ; villager is offscreen
    lda $01
    cmp #$F0
    bcc @hide
    lda #$FF
@onscreen:
    sta $07
    lda $01
    sta $06
    ldy SHOUT_WORD
    ldx ShoutWordStart-1,y
    lda #$00
    sta $05
    lda ShoutTopLength-1,y
    beq @bottom_row
    sta $04
    lda $00
    sec
    sbc #$10                    ; separate the two 16-pixel sprite rows
    cmp #$20
    bcc @hide
    sta $00
    lda $04
    asl
    asl
    sec
    sbc #$08
    jsr @center_row
    jsr @glyph
    inx                         ; first tile of the bottom row
    lda $00
    clc
    adc #$10
    sta $00
    ldy SHOUT_WORD
@bottom_row:
    lda ShoutBottomInset-1,y
    jsr @center_row
    lda #$07
    sta $04
    bne @glyph
@center_row:
    ; A = 4 * width in tiles - 8, the inset from the villager's left edge.
    sta $03
    lda $06
    sec
    sbc $03
    sta $01
    lda $07
    sbc #$00
    sta $02
    rts
@glyph:
    lda ShoutWordTiles,x
    beq @hide_rest              ; $00 ends phrases with <7 visible glyphs
    ldy $05
    lda ShoutOam,y
    tay
    lda $02
    bne @blank                  ; clip each glyph off either screen edge
    lda $00
    sta $0200,y
    lda ShoutWordTiles,x
    sta $0201,y
    lda #ShoutGlyphPalette
    sta $0202,y
    lda $01
    sta $0203,y
    jmp @next
@blank:
    lda #$F8
    sta $0200,y
@next:
    inc $05
    lda $05
    cmp $04
    beq @word_done
    lda $01
    clc
    adc #$08
    sta $01
    bcc :+
    inc $02
:
    inx
    jmp @glyph
@hide_rest:
    ldy $05
    lda ShoutOam,y
    tay
    lda #$F8
    sta $0200,y
    inc $05
    lda $05
    cmp $04
    bne @hide_rest
@word_done:
    rts

@player_shout:
    dec SHOUT_WORD_TIMER
    beq ShoutWordCancel
    lda $29
    sec
    sbc #$24                    ; clear of Barba's horns (5 glyphs + 2 torches <= 8)
    bcc ShoutWordHide
    cmp #$20                    ; keep clear of the HUD above the split
    bcc ShoutWordHide
    sta $00
    lda $4D
    sec
    sbc $072C
    sta $01
    lda $3B
    sbc $072A
    beq @player_onscreen
    cmp #$FF
    bne ShoutWordHide
    lda $01
    cmp #$F0
    bcc ShoutWordHide
    lda #$FF
@player_onscreen:
    sta $02
    ; Center 5-char "OOPS..." (40 px) over Barba's 24 px head ($4D + 16 - 20 = $4D - 4).
    lda $01
    sec
    sbc #$04
    sta $01
    lda $02
    sbc #$00
    sta $02
    ldx #(CastleShoutTiles-ShoutWordTiles)
    lda #$06
    sta $04
    lda #$01                    ; indices 1..5 ($28,$2C,$30,$34,$40): above torches ($50..$5C)
    sta $05
    jmp @glyph

ShoutWordCancel:
    lda SHOUT_WORD
    beq ShoutWordDone
    lda #$00
    sta SHOUT_WORD
ShoutWordHide:
    ldy #$00
    lda #$07
    ldx SHOUT_SLOT
    bpl :+
    ldy #$01
    lda #$06
:
    sta $04
    lda #$F8
:
    ldx ShoutOam,y
    sta $0200,x
    iny
    cpy $04
    bne :-
ShoutWordDone:
    rts

ShoutOam:
    .byte $00, $28, $2C, $30, $34, $40, $DC

; Fear phrases per shout word 1..9, up to seven visible glyphs plus optional space.
.segment "BANK6_HAZE"
ShoutTopLength:
    .byte 2, 2, 0, 2, 2, 0, 4, 0, 0
ShoutBottomInset:
    .byte 12, 12, 8, 4, 8, 12, 4, 4, 8

.segment "BANK6"
; A split phrase lists its top row first. $00 ends the phrase.
ShoutWordStart:
    .byte ShoutOhShit-ShoutWordTiles, ShoutOhFuck-ShoutWordTiles, ShoutRun-ShoutWordTiles
    .byte ShoutOhNo-ShoutWordTiles, ShoutOhGod-ShoutWordTiles, ShoutHelp-ShoutWordTiles
    .byte ShoutSaveMe-ShoutWordTiles, ShoutNo-ShoutWordTiles, ShoutBarba-ShoutWordTiles
ShoutWordTiles:
ShoutOhShit:
    .byte ShoutTile_O, ShoutTile_H
    .byte ShoutTile_S, ShoutTile_H, ShoutTile_I, ShoutTile_T, ShoutTile_Bang, $00
ShoutOhFuck:
    .byte ShoutTile_O, ShoutTile_H
    .byte ShoutTile_F, ShoutTile_U, ShoutTile_C, ShoutTile_K, ShoutTile_Bang, $00
ShoutRun:
    .byte ShoutTile_R, ShoutTile_U, ShoutTile_N, ShoutTile_Bang, $00
ShoutOhNo:
    .byte ShoutTile_O, ShoutTile_H
    .byte ShoutTile_N, ShoutTile_O, ShoutTile_Bang, $00
ShoutOhGod:
    .byte ShoutTile_O, ShoutTile_H
    .byte ShoutTile_G, ShoutTile_O, ShoutTile_D, ShoutTile_Bang, $00
ShoutHelp:
    .byte ShoutTile_H, ShoutTile_E, ShoutTile_L, ShoutTile_P, ShoutTile_Bang, $00
ShoutSaveMe:
    .byte ShoutTile_S, ShoutTile_A, ShoutTile_V, ShoutTile_E
    .byte ShoutTile_M, ShoutTile_E, ShoutTile_Bang, $00
ShoutNo:
    .byte ShoutTile_N, ShoutTile_O, ShoutTile_Bang, $00
ShoutBarba:
    .byte ShoutTile_Ba, ShoutTile_R, ShoutTile_Ba, ShoutTile_Bang, $00
; 10: North Palace "OOPS..." (CHR bank 3 odd 8x16 sprite tiles, offset 72).
CastleShoutTiles:
    .byte $5F, $5F, $61, $63, $65, $00

.include "combo.inc"
