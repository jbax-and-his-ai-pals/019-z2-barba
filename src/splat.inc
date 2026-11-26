; Giant Bot ($1E) split splat SFX.
; Hooked from Bank 5 $A186 (Giant_Bot split into 5 Bots when $C2,x < $30)
; and ticked after the native Bank 6 sound driver ($9000).
SPLAT_TIMER = $635E
SPLAT_LEN   = 14

.segment "BANK5_SPLAT"
GiantBotSplat5:
    lda $C2,x
    cmp #$30
    bcs @done
    lda #SPLAT_LEN
    sta SPLAT_TIMER
    clc
@done:
    rts

.segment "SAMPLED_ROAR"
SplatSoundDriver6:
    jsr $9000
    jmp SplatCheck6

.segment "PALACE_SHAKE"
SplatCheck6:
    lda SPLAT_TIMER
    beq @done
    jmp SplatHop6
@done:
    rts

.segment "BANK6_PAD"
SplatHop6:
    lda #>(GiantBotSplatTick2 - 1)
    pha
    lda #<(GiantBotSplatTick2 - 1)
    pha
    lda #$02
    jmp $FFCC

.segment "BANK2_SMOKE"
GiantBotSplatTick2:
    dec SPLAT_TIMER
    beq @silence
    lda $EA                 ; global sound switch (0 = on)
    bne @silence
    ldx SPLAT_TIMER         ; X = 13 down to 1 (13 = first frame, 1 = last)
    txa
    clc
    adc #$32                ; volume $3F -> $33
    sta $400C
    lda SplatNoiseFreq-1,x
    sta $400E
    lda #$08
    sta $400F
    cpx #13
    beq @bloop1
    cpx #9
    beq @bloop2
    cpx #4
    bcc @pulse_off
    txa
    asl
    ora #$B0
    bne @set_vol4
@pulse_off:
    lda #$08
    sta $4005
    lda #$10
@set_vol4:
    sta $4004
@exit:
    lda #$06
    jmp $FFCC
@bloop1:
    ldy #$BF                ; 50% duty, const vol 15
    lda #$8A                ; hardware sweep down (fast)
    ldx #$80
    bne @pulse_write
@bloop2:
    ldy #$BB                ; second comical blub
    lda #$89                ; hardware sweep down
    ldx #$40
@pulse_write:
    sty $4004
    sta $4005
    stx $4006
    lda #$09
    sta $4007
    bne @exit
@silence:
    lda #$00
    sta SPLAT_TIMER
    lda #$10
    sta $400C
    bne @pulse_off

; Indexed by SPLAT_TIMER - 1 (0 = last frame, 12 = first frame).
SplatNoiseFreq:
    .byte $0F,$0F,$0F,$0E,$8E,$0D,$8D,$0C,$8C,$0B,$8A,$08,$06
