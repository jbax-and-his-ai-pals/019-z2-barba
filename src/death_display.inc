.segment "BANK3_SIGN"
.export BarbaDeathDisplay
; The death transition draws its compact 32px pose through the native renderer.
; Move the head up one sprite row and fill the gap with one full torso strip.
; The native lower strip stays at the original feet position.
BarbaDeathDisplay:
    lda #$F8
    sta $0220
    sta $0224
    lda #$0A
    sta $80
    jsr $EBF0
    lda $13
    ora $048D
    bne @done
    ldx #$04
    lda #$06
    bit $020A
    bvc @torso
    ldx #$00
    lda #$08
@torso:
    ldy #$00
@column:
    sta $0221,y
    lda $0208,x
    sta $0220,y
    lda $020A,x
    sta $0222,y
    lda $020B,x
    sta $0223,y
    txa
    clc
    adc #$04
    tax
    lda $0221,y
    eor #$0E          ; swap torso tiles $06 and $08 for the second column
    iny
    iny
    iny
    iny
    cpy #$08
    bne @column
    ldx #$08
@head:
    lda $0208,x
    cmp #$F0
    bcs @next
    sec
    sbc #$10
    bcs :+
    lda #$F8
:
    sta $0208,x
@next:
    dex
    dex
    dex
    dex
    bpl @head
@done:
    jmp $FFC5          ; restore bank 0 for the death palette transfer
