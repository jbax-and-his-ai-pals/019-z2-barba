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
SHOUT_WORD = $6467          ; 0 none, else word 1..4 drawn above SHOUT_SLOT
SHOUT_WORD_TIMER = $6468    ; frames left for the word
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
    lda SHOUT_TIMER
    beq @packet
    dec SHOUT_TIMER
    bne @packet
    lda #$FF
    sta SHOUT_REQUEST
@packet:
    lda SHOUT_REQUEST
    beq @done
    lda $0725
    bne @done
    ; Twenty glyphs plus a three-byte header: never exceed 32 queued bytes.
    lda $0301
    cmp #$0A
    bcs @done
    jsr ShoutPacket
    lda SHOUT_REQUEST
    cmp #$FF
    beq :+
    lda #$64
    sta SHOUT_TIMER
    lda #$B4
    sta SHOUT_COOLDOWN
:
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
    lda $0707
    sta SHOUT_WORLD
    lda $0561
    sta SHOUT_ROOM
    rts

ShoutPacket:
    lda SHOUT_REQUEST
    sec
    sbc #$01
    asl
    asl
    sta $00
    asl
    asl
    clc
    adc $00
    tax
    ldy $0301
    lda #$20
    sta $0302,y
    lda #$06
    sta $0303,y
    lda #$14
    sta $0304,y
    lda #$14
    sta $00
@letter:
    lda SHOUT_REQUEST
    cmp #$FF
    beq @blank
    lda ShoutText,x
    jmp @put
@blank:
    lda #$F4
@put:
    sta $0305,y
    inx
    iny
    dec $00
    bne @letter
    lda #$FF
    sta $0305,y
    tya
    clc
    adc #$03
    sta $0301
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
    ; calm generated wanderer: door/offscreen despawn ($B6), burn and ash
    ; ($AF), or a different actor generated into the slot ($BC).
    lda $B6,x
    cmp #$01
    bne @cancel
    lda $BC,x
    cmp #$FF
    bne @cancel
    lda $AF,x
    beq :+
    cmp #$80
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
    beq @blank                  ; $00 pads words shorter than five
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
    lda $01
    clc
    adc #$08
    sta $01
    bcc :+
    inc $02
:
    inx
    iny
    iny
    iny
    iny
    cpy #SHOUT_OAM+$14
    bne @glyph
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

; Word per wandering type $19..$1C (SHOUT_REQUEST 1..4), at most five glyphs.
; ShoutWordTiles comes from shout_layout.inc: five tiles per word, $00 pad.
ShoutWordLength:
    .byte 5, 4, 5, 3
ShoutWordStart:
    .byte 0, 5, 10, 15
ShoutWordTiles:
    .byte ShoutTile_S, ShoutTile_H, ShoutTile_I, ShoutTile_T, ShoutTile_Bang ; $19
    .byte ShoutTile_R, ShoutTile_U, ShoutTile_N, ShoutTile_Bang, $00          ; $1A
    .byte ShoutTile_F, ShoutTile_U, ShoutTile_C, ShoutTile_K, ShoutTile_Bang ; $1B
    .byte ShoutTile_N, ShoutTile_O, ShoutTile_Bang, $00, $00                  ; $1C

.macro ShoutLine text
    .assert .strlen(text) <= 20, error, "Panic shout is too wide"
    .repeat .strlen(text), character
        .if .strat(text, character) = ' '
            .byte $F4
        .elseif .strat(text, character) = '.'
            .byte $CF
        .else
            .byte .strat(text, character)-'A'+$DA
        .endif
    .endrepeat
    .res 20-.strlen(text), $F4
.endmacro
ShoutText:
    ShoutLine "OH SHIT. BARBA. RUN."
    ShoutLine "A DRAGON. HIDE."
    ShoutLine "FUCK THAT. RUN."
    ShoutLine "PLEASE. NO FIRE."
