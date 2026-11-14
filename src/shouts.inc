; Nonblocking town screams in the unused top HUD row, above the sprite-0 split.
; Never touch the dialogue/movement-lock state. Native VBlank consumes packets.
.export BarbaShouts
SHOUT_READY = $05EA
SHOUT_TIMER = $6460
SHOUT_COOLDOWN = $6461
SHOUT_REQUEST = $6462
SHOUT_WORLD = $6463
SHOUT_ROOM = $6464
TALK_LATCH = $6466

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
    bne @done
    lda $F7
    and #$08
    bne :+
    lda #$00
    sta TALK_LATCH
:
    lda $074C
    ora $DE
    ora $0726
    bne @done
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
@done:
    pla
    tay
    pla
    tax
    rts
@reset:
    lda #$00
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
