; JSR FarCall0 / .word target. Inline operand must live in fixed ROM.
; No bank shadow: $0769 is the AREA bank, not the currently mapped bank.
; $8506 has a distinct guarded byte in all eight original PRG banks.
; Everything except the 20-byte switch bridge lives in BANK0. Stack-local
; frames permit nesting; A/X/Y/P and $00/$01 reach the target unchanged.
.export FarCall0, FarCall0Return, FarCall0Dispatch, FarCall0Finish
.segment "LAVA"
FarCall0:
    php
    pha
    txa
    pha
    lda $8506
    pha
    jsr $FFC5
    jmp FarCall0Dispatch
FarCall0Return:
    jsr $FFCC
    pla
    plp
    rts

.segment "BANK0"
FarCall0Dispatch:
    tya
    pha
    lda $00
    pha
    lda $01
    pha
    tsx
    ; +1 old01, +2 old00, +3 Y, +4 fingerprint, +5 X, +6 A,
    ; +7 P, +8 return low, +9 return high.
    ldy #$07
@bank:
    lda FarCall0Banks,y
    cmp $0104,x
    beq @found
    dey
    bpl @bank
    ; Build guards make an unknown fingerprint unreachable.
    brk
@found:
    tya
    sta $0104,x
    lda $0108,x
    sta $00
    clc
    adc #$02
    sta $0108,x
    lda $0109,x
    sta $01
    adc #$00
    sta $0109,x
    lda #>(FarCall0Finish-1)
    pha
    lda #<(FarCall0Finish-1)
    pha
    ; Push target-1 high then low for RTS. Correct high on low-byte borrow.
    ldy #$02
    lda ($00),y
    pha
    dey
    lda ($00),y
    sec
    sbc #$01
    bcs :+
    dec a:$00FE,x ; force absolute,X: zero-page,X would wrap below stack
:
    pha
    lda $0101,x
    sta $01
    lda $0102,x
    sta $00
    lda $0103,x
    tay
    lda $0107,x
    pha
    lda $0106,x
    pha
    lda $0105,x
    tax
    pla
    plp
    rts
FarCall0Banks:
    .byte $F0,$7D,$60,$2E,$91,$2F,$00,$C9
FarCall0Finish:
    php
    pha
    txa
    pha
    tya
    pha
    tsx
    ; +1 outputY, +2 outputX, +3 outputA, +4 outputP;
    ; original frame begins at +5, caller return is +12/+13.
    lda $0108,x
    sta $0109,x
    lda $0102,x
    sta $0108,x
    lda $0103,x
    sta $010A,x
    lda $0104,x
    sta $010B,x
    lda $0101,x
    tay
    txa
    clc
    adc #$08
    tax
    txs
    lda $0100,x
    tax
    pla
    jmp FarCall0Return

; Move the cold hazard body out of the fixed bank. C retains the original
; CMP #3 result: palace goes to $E12B, water returns to the original caller.
LavaSurfaceBody:
    lda $0707
    cmp #$03
    bcc @water
    lda #$04
    sta LAVA_CONTACT
    lda $A7
    ora #$04
    sta $A7
    rts
@water:
    lda #$01
    sta $E9
    lda #$10
    sta $050C
    inc $B5
    rts
