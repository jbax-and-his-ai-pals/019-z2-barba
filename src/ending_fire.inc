; Bank 5 cutscene, called after drawing Barba and Zelda.
.segment "ENDING_FIRE"

ENDING_FIRE_STATE = $05F8     ; 0 waiting, 1 in flight, 2 ash
ENDING_FIRE_X = $05FA         ; left edge of the two-sprite shot
ENDING_ASH = $8F6F

EndingFire:
    lda ENDING_FIRE_STATE
    bne @started
    lda $0761
    cmp #6                    ; curtain falling
    bne @done
    lda $27
    cmp #$22
    bne @done
    lda $28
    cmp #$A0                  ; curtain covers Barba's head
    bcc @done
    inc ENDING_FIRE_STATE
    lda #$67
    sta ENDING_FIRE_X
    lda $ED
    ora #$40
    sta $ED
@done:
    rts

@started:
    cmp #1
    bne @ash
    inc ENDING_FIRE_X
    lda ENDING_FIRE_X
    cmp #$79                  ; flame tip reached Zelda
    bcs @hit
    sta $0243
    adc #8                    ; CMP left carry clear
    sta $0247
    adc #$3B                  ; Y = left X + $43, one pixel down and right per frame
    sta $0240
    sta $0244

    and #$04                  ; alternate frames every four pixels
    lsr a
    ora #$E0                  ; tail: $E0 or $E2
    sta $0241
    ora #$04                  ; head: $E4 or $E6
    sta $0245
    lda #$20                  ; both halves behind the curtain, warm palette 0
    sta $0242
    sta $0246
    rts

@hit:
    inc ENDING_FIRE_STATE
@ash:
    jmp ENDING_ASH
