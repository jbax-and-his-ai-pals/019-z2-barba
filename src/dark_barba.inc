; Bank 5 helpers for Dark Link ("Dark Barba") 24x48 rendering and
; post-Dark-Link Triforce-hold height/position alignment.
.segment "BANK5"
.export DarkBarbaDraw, DarkBarbaTriforcePose, HiddenJarHit

DarkBarbaDraw:
    ldx #$08
    lda $13
    bne @loop
    lda #$02
    sta $0753
    jsr $EC02
    lda #$F8
    sta $026C
    sta $0270
    sta $0274
    lda $C9
    and #$F0
    beq :+
    rts
:
    lda $0252
    and #$FC           ; drop the native hurt flash's palette bits
    ora #$02           ; keep the shadow black, preserving priority and facing
    sta $02
    lda $81
    ldy $2A
    cpy #$A0
    bcs @pose_ok
    cmp #$06
    beq @air_sub2
    cmp #$07
    bne @pose_ok
@air_sub2:
    sbc #$02           ; carry is set from cmp #$06 or cmp #$07: $06/$07 -> $04/$05
@pose_ok:
    cmp #$0D
    bcc :+
    lda #$03
:   sta $00
    asl
    asl
    asl
    adc $00             ; A = pose * 9 (carry clear)
    sta $03             ; $03 = base index into DarkBarbaTiles
    ldx #$08
@loop:
    ldy @oam_off,x
    txa
    bit $02
    bvc @got_order
    lda @order_r,x
@got_order:
    clc
    adc $03
    stx $05
    tax
    lda DarkBarbaTiles,x
    ldx $05
    cmp #$F5
    beq @skip
    sta $0201,y
    lda $2A
    clc
    adc @row_y,x
    cmp #$20
    bcc @skip
    cmp #$F0
    bcs @skip
    sta $0200,y
    lda $CD
    clc
    adc @col_x,x
    bcs @skip
    sta $0203,y
    lda $02
    sta $0202,y
    bcc @next
@skip:
    lda #$F8
    sta $0200,y
@next:
    dex
    bpl @loop
    rts

@oam_off:
    .byte $6C, $70, $74, $50, $54, $58, $5C, $60, $64
@col_x:
    .byte $00, $08, $10, $00, $08, $10, $00, $08, $10
@row_y:
    .byte $F0, $F0, $F0, $00, $00, $00, $10, $10, $10
@order_r:
    .byte $02, $01, $00, $05, $04, $03, $08, $07, $06

DarkBarbaTiles:
.scope
DARK_BARBA_LAYOUT = 1
.include "tall_layout.inc"
.endscope

; Raise only the Triforce, leaving $2A at $B0 so the old man stays on the floor.
; $91 is enemy 0's rotating OAM base.
DarkBarbaTriforcePose:
.ifdef SAMPLED_ROAR
    lda #$03           ; stand until the renderer sees the victory roar
.else
    lda #$08
.endif
    sta $80
    inc $AF
    jsr $EF11
    ldy $91
    lda $0208,y
    sec
    sbc #$10
    sta $0208,y
    sta $020C,y
    rts

; Hooked at $A525 in Great Palace Hidden Red Jar ($A521).
HiddenJarHit:
    lda #$FF
    sta $C2,x
    jsr $E677
    lda $A8,x
    and #$20
    bne @done
    jmp $E48B
@done:
    rts

.ifdef SAMPLED_ROAR
.export DarkBarbaVictory
; Phase 7 holds the Triforce during the victory fanfare and the full roar.
DarkBarbaVictory:
    lda ROAR_REQUEST
    and #$18
    beq @fanfare
    eor #$10
    bne @hold
    sta ROAR_REQUEST
    jmp $9BBA          ; native transition into Zelda's awakening
@fanfare:
    lda $07FB          ; active music
    ora $EB            ; music request before the driver starts it
    bne @hold
    lda #$48           ; queue the full roar and raised-head pose
    sta ROAR_REQUEST
@hold:
    jmp $9BB1          ; draw the Triforce pose even if the native timer expires
.endif
