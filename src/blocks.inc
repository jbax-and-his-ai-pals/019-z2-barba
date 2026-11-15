; Reuse the native glove-gated breakable-block handler at each live fireball,
; never at Barba's body. This keeps block gates usable after retiring melee.
.export BarbaBlocks, BarbaNativeBlocks, BarbaBlockSlot
BarbaBlocks:
    lda $0707
    cmp #$03
    beq @done
    jsr BarbaNativeBlocks
    lda $0707
    beq @done
    jsr BarbaExtraBlocks
@done:
    jmp BarbaSetThrusts ; restore held thrust after temporary projectile origins
BarbaNativeBlocks:
    lda $8D
    ora $8E
    bne :+
    rts
:
    lda $80
    pha
    lda $047E
    pha
    lda $057D
    pha
    ldx #$01
    jsr BarbaBlockSlot
    ldx #$00
    jsr BarbaBlockSlot
    pla
    sta $057D
    pla
    sta $047E
    pla
    sta $80
    lda #$F8
    sta $0480
    rts

; Check one projectile slot X against glove-gated breakable blocks.
; Caller must save/restore $80, $047E, $057D and reset $0480 = #$F8.
BarbaBlockSlot:
    lda $8D,x
    beq @done
    bmi @done
    lda $5A,x
    sec
    sbc $072C
    sta $047E
    lda $48,x
    sbc $072A
    bne @done
    lda $36,x
    cmp #$20
    bcc @done
    cmp #$D8
    bcs @done
    clc
    adc #$05
    sta $0480
    ; Native down-tech branch uses the supplied world origin and avoids
    ; applying horizontal sword recoil to Barba on contact with stone.
    lda $0707
    cmp #$01
    beq @check_town
    cmp #$02
    bne @native_block
@check_town:
    lda $0706
    beq BarbaTownBurn
@native_block:
    lda #$09
    sta $80
    jsr $E1DD
@done:
    rts

; Burn outdoor town props, bushes, signs, walls, windows and roofs to sky ($40),
; preserving ground ($50..$5F), clouds ($C4..$C6), and doorways ($89..$8C, $91).
BarbaTownBurn:
    lda $0480
    clc
    adc #$03
    sta $39
    lda $047E
    clc
    adc #$04
    adc $072C
    sta $5D
    lda $072A
    adc #$00
    sta $4B
    ldx #$10
    ldy #$1C
    jsr $EAE8
    ldy $02
    cpy #$B0
    bcs @skip
    cmp #$40
    beq @skip
    cmp #$91
    beq @skip
    cmp #$50
    bcc @check_door
    cmp #$60
    bcc @skip
@check_door:
    cmp #$89
    bcc @check_cloud
    cmp #$8D
    bcc @skip
@check_cloud:
    cmp #$C4
    bcc @burn
    cmp #$C7
    bcs @burn
@skip:
    rts
@burn:
    lda $0362
    cmp #$28
    bcs @done
    lda #$40
    sta ($0E),y
    lda #$04
    sta $ED
    lda $4B
    and #$01
    asl
    asl
    pha
    lda $39
    and #$F0
    sta $02
    lda $5D
    and #$F0
    sta $03
    lda #$08
    sta $00
    lda $02
    asl
    rol $00
    asl
    rol $00
    and #$E0
    sta $01
    lda $03
    lsr
    lsr
    lsr
    ora $01
    sta $01
    ldx $0362
    pla
    ora $00
    sta $0363,x
    sta $0368,x
    txa
    clc
    adc #$0A
    sta $0362
    lda $01
    sta $0364,x
    clc
    adc #$01
    sta $0369,x
    lda #$82
    sta $0365,x
    sta $036A,x
    lda #$F4
    sta $0366,x
    sta $0367,x
    sta $036B,x
    sta $036C,x
    lda #$FF
    sta $036D,x
    lda #$01
    sta $0725
@done:
    rts
