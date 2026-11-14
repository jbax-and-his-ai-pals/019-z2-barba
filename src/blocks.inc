; Reuse the native glove-gated breakable-block handler at each live fireball,
; never at Barba's body. This keeps block gates usable after retiring melee.
.export BarbaBlocks, BarbaNativeBlocks
BarbaBlocks:
    jsr BarbaNativeBlocks
    jmp BarbaExtraBlocks
BarbaNativeBlocks:
    lda $80
    pha
    lda $047E
    pha
    lda $057D
    pha
    ldx #$01
@slot:
    txa
    pha
    lda $8D,x
    beq @next
    bmi @next
    lda $5A,x
    sec
    sbc $072C
    sta $047E
    lda $48,x
    sbc $072A
    bne @next
    lda $36,x
    cmp #$20
    bcc @next
    cmp #$D8
    bcs @next
    clc
    adc #$05
    sta $0480
    ; Native down-tech branch uses the supplied world origin and avoids
    ; applying horizontal sword recoil to Barba on contact with stone.
    lda #$09
    sta $80
    jsr $E1DD
@next:
    pla
    tax
    dex
    bpl @slot
    pla
    sta $057D
    pla
    sta $047E
    pla
    sta $80
    lda #$F8
    sta $0480
    rts
