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
; Seven consecutive OAM entries $DC..$F4. Natively enemy-projectile windows
; ($E0/$E8/$F0 in $D59B); town streets never fill them. Written only while
; a word is live in town play, yielding to any enemy projectile ($87..$8C).
SHOUT_OAM = $DC
SHOUT_WORD_TIME = $64

BarbaShouts:
    lda #>(BarbaShouts6-1)
    pha
    lda #<(BarbaShouts6-1)
    pha
    jmp SwapToBank6

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

.segment "BANK6"
BarbaShouts6:
    txa
    pha
    tya
    pha
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
    ; Glyphs sit in the lower half of each 8x16 pair: sprite Y = top - 32
    ; puts the letters at Y-24..Y-17, clear of Barba's 48px head so 7-glyph
    ; shouts don't hit the 8-sprites-per-scanline limit when Barba stands nearby.
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
    sta $02
    ; Centre over the 16 px body: left = x + 8 - 4 * length (signed).
    ldy SHOUT_WORD
    lda ShoutWordLength-1,y
    asl
    asl
    sta $03
    lda $01
    clc
    adc #$08
    bcc :+
    inc $02
:
    sec
    sbc $03
    sta $01
    lda $02
    sbc #$00
    sta $02
    lda ShoutWordStart-1,y
    tax
    lda #SHOUT_OAM+$1C
    sta $04
    ldy #SHOUT_OAM
@glyph:
    lda ShoutWordTiles,x
    beq @hide_rest              ; $00 ends phrases with <5 visible glyphs
    cmp #ShoutTile_Space
    beq @advance_x              ; spaces advance X without consuming an OAM slot
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
    iny
    iny
    iny
    iny
    cpy $04
    beq @word_done
@advance_x:
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
    lda #$F8
@hide_loop:
    sta $0200,y
    iny
    iny
    iny
    iny
    cpy $04
    bne @hide_loop
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
    ldx #72                     ; CastleShoutTiles offset in ShoutWordTiles
    lda #$3C
    sta $04
    ldy #$28                    ; higher priority than North Palace torches ($50..$5C)
    jmp @glyph

ShoutWordCancel:
    lda SHOUT_WORD
    beq ShoutWordDone
    lda #$00
    sta SHOUT_WORD
ShoutWordHide:
    ldy #SHOUT_OAM
    lda #SHOUT_OAM+$1C
    ldx SHOUT_SLOT
    bpl :+
    ldy #$28
    lda #$3C
:
    sta $04
    lda #$F8
:
    sta $0200,y
    iny
    iny
    iny
    iny
    cpy $04
    bne :-
ShoutWordDone:
    rts

; Fear phrases per shout word 1..9, up to seven visible glyphs plus optional space.
; ShoutWordTiles comes from shout_layout.inc: eight bytes per phrase, $FF space, $00 end.
ShoutTile_Space = $FF
ShoutWordLength:
    .byte 8, 8, 4, 6, 7, 5, 8, 3, 6
ShoutWordStart:
    .byte 0, 8, 16, 24, 32, 40, 48, 56, 64
ShoutWordTiles:
    .byte ShoutTile_O, ShoutTile_H, ShoutTile_Space, ShoutTile_S, ShoutTile_H, ShoutTile_I, ShoutTile_T, ShoutTile_Bang ; 1 OH SHIT!
    .byte ShoutTile_O, ShoutTile_H, ShoutTile_Space, ShoutTile_F, ShoutTile_U, ShoutTile_C, ShoutTile_K, ShoutTile_Bang ; 2 OH FUCK!
    .byte ShoutTile_R, ShoutTile_U, ShoutTile_N, ShoutTile_Bang, $00, $00, $00, $00                                     ; 3 RUN!
    .byte ShoutTile_O, ShoutTile_H, ShoutTile_Space, ShoutTile_N, ShoutTile_O, ShoutTile_Bang, $00, $00               ; 4 OH NO!
    .byte ShoutTile_O, ShoutTile_H, ShoutTile_Space, ShoutTile_G, ShoutTile_O, ShoutTile_D, ShoutTile_Bang, $00       ; 5 OH GOD!
    .byte ShoutTile_H, ShoutTile_E, ShoutTile_L, ShoutTile_P, ShoutTile_Bang, $00, $00, $00                           ; 6 HELP!
    .byte ShoutTile_S, ShoutTile_A, ShoutTile_V, ShoutTile_E, ShoutTile_Space, ShoutTile_M, ShoutTile_E, ShoutTile_Bang ; 7 SAVE ME!
    .byte ShoutTile_N, ShoutTile_O, ShoutTile_Bang, $00, $00, $00, $00, $00                                           ; 8 NO!
    .byte ShoutTile_B, ShoutTile_A, ShoutTile_R, ShoutTile_B, ShoutTile_A, ShoutTile_Bang, $00, $00                   ; 9 BARBA!
; 10: North Palace "OOPS..." (CHR bank 3 odd 8x16 sprite tiles, offset 72).
CastleShoutTiles:
    .byte $5F, $5F, $61, $63, $65, $00

.include "combo.inc"
