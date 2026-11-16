; Bank 5 helpers for Dark Link ("Dark Barba") 24x48 rendering and
; post-Dark-Link Triforce-hold height/position alignment.
.segment "BANK5"
.export DarkBarbaDraw, DarkBarbaTriforcePose, HiddenJarHit

DarkBarbaDraw:
    lda #$02
    sta $0753
    jsr $EC02
    lda #$F8
    sta $026C
    sta $0270
    sta $0274
    lda $C9
    and #$F0
    bne @done
    lda $0252
    sta $02             ; $02 = attribute byte (palette, priority, hflip)
    lda $81
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
    stx $04
    lda $02
    and #$40
    bne @right
    lda @order_l,x
    bpl @got_order
@right:
    lda @order_r,x
@got_order:
    clc
    adc $03
    tay
    lda DarkBarbaTiles,y
    cmp #$F5
    beq @skip
    sta $05
    ldx $04
    lda $2A
    clc
    adc @row_y,x
    cmp #$20
    bcc @skip
    cmp #$F0
    bcs @skip
    sta $06
    lda $CD
    clc
    adc @col_x,x
    bcs @skip
    sta $07
    ldy @oam_off,x
    lda $06
    sta $0200,y
    lda $05
    sta $0201,y
    lda $02
    sta $0202,y
    lda $07
    sta $0203,y
    jmp @next
@skip:
    ldx $04
    ldy @oam_off,x
    lda #$F8
    sta $0200,y
@next:
    ldx $04
    dex
    bpl @loop
@done:
    rts

@oam_off:
    .byte $6C, $70, $74, $50, $54, $58, $5C, $60, $64
@col_x:
    .byte $00, $08, $10, $00, $08, $10, $00, $08, $10
@row_y:
    .byte $F0, $F0, $F0, $00, $00, $00, $10, $10, $10
@order_l:
    .byte $00, $01, $02, $03, $04, $05, $06, $07, $08
@order_r:
    .byte $02, $01, $00, $05, $04, $03, $08, $07, $06

DarkBarbaTiles:
.scope
.include "tall_layout.inc"
.endscope

; Render 48px Barba looking up ($08) and raise only the Triforce 16px above his head
; (leaving $2A at $B0 so the old man stays on the floor; $91 is enemy 0's rotating OAM base).
DarkBarbaTriforcePose:
    lda #$08
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
