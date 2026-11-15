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
; Five OAM entries $E0..$F0. Natively these are enemy-projectile windows
; (bases $E0/$E8/$F0 in the $D59B rotation); town streets never fill them.
; They are written only while a word is live in town play, and the word
; yields any frame an enemy projectile ($87..$8C) exists.
SHOUT_OAM = $E0
SHOUT_WORD_TIME = $64

BarbaShouts:
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
    cmp #$01
    beq @mode
    cmp #$02
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
    jsr ShoutWord
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
@done:
    pla
    tay
    pla
    tax
    rts
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
    rts

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
    ; Glyphs sit in the lower half of each 8x16 pair: sprite Y = top - 18
    ; puts the letters 2 px above the head, entirely clear of the body rows.
    lda $2A,x
    sec
    sbc #$12
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
    cpy #SHOUT_OAM+$14
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
    cpy #SHOUT_OAM+$14
    bne @hide_loop
@word_done:
    rts

ShoutWordCancel:
    lda SHOUT_WORD
    beq ShoutWordDone
    lda #$00
    sta SHOUT_WORD
ShoutWordHide:
    lda #$F8
    ldy #SHOUT_OAM
:
    sta $0200,y
    iny
    iny
    iny
    iny
    cpy #SHOUT_OAM+$14
    bne :-
ShoutWordDone:
    rts

; Fear phrases per shout word 1..8, up to five visible glyphs plus optional space.
; ShoutWordTiles comes from shout_layout.inc: six bytes per phrase, $FF space, $00 end.
ShoutTile_Space = $FF
ShoutWordLength:
    .byte 5, 4, 5, 5, 4, 4, 6, 5
ShoutWordStart:
    .byte 0, 6, 12, 18, 24, 30, 36, 42
ShoutWordTiles:
    .byte ShoutTile_S, ShoutTile_H, ShoutTile_I, ShoutTile_T, ShoutTile_Bang, $00             ; 1 SHIT!
    .byte ShoutTile_R, ShoutTile_U, ShoutTile_N, ShoutTile_Bang, $00, $00                     ; 2 RUN!
    .byte ShoutTile_F, ShoutTile_U, ShoutTile_C, ShoutTile_K, ShoutTile_Bang, $00             ; 3 FUCK!
    .byte ShoutTile_O, ShoutTile_H, ShoutTile_Space, ShoutTile_N, ShoutTile_O, $00            ; 4 OH NO
    .byte ShoutTile_O, ShoutTile_M, ShoutTile_G, ShoutTile_Bang, $00, $00                     ; 5 OMG!
    .byte ShoutTile_W, ShoutTile_T, ShoutTile_F, ShoutTile_Bang, $00, $00                     ; 6 WTF!
    .byte ShoutTile_O, ShoutTile_H, ShoutTile_Space, ShoutTile_G, ShoutTile_O, ShoutTile_D    ; 7 OH GOD
    .byte ShoutTile_H, ShoutTile_E, ShoutTile_L, ShoutTile_P, ShoutTile_Bang, $00             ; 8 HELP!
