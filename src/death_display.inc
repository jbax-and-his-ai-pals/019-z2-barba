; Fatal-hit transition ($C9EE) now switches to Bank 0 and calls BarbaDisplay
; directly with $80 = #$0A, giving Barba his full 24x48 hurt body, terrain
; geometry, and encounter elbow/tail without extra bank-0 code.

.segment "BANK1"
.export BarbaLivesText
; Lives-remaining screen ($C3BE) builds PPU macros at $0302 so the player
; name (trailing spaces trimmed, ending at col 9) sits left of Barba's tail
; and "x N" (cols 22-24) sits right of Barba's snout on row 12 ($2180).
BarbaLivesText:
    ldy #$07
@trim:
    lda $07A1,y
    cmp #$F4                  ; trailing space?
    bne @found
    dey
    bpl @trim
@found:
    iny                       ; trimmed length L = 0..8
    sty $00
    ldx #$00
    lda $00
    beq @life_macro
    lda #$21
    sta $0302
    lda #$8A                  ; col 10 ($218A) - L (name ends at col 9)
    sec
    sbc $00
    sta $0303
    lda $00
    sta $0304
@copy_name:
    lda $07A1,x
    sta $0305,x
    inx
    cpx $00
    bcc @copy_name
    inx                       ; advance past macro 1's 3-byte header ($0302,x)
    inx
    inx
@life_macro:
    lda #$21
    sta $0302,x
    lda #$96                  ; col 22 ($2196): 'x', space, digit
    sta $0303,x
    lda #$03
    sta $0304,x
    lda #$FC                  ; 'x'
    sta $0305,x
    lda #$F4                  ; ' '
    sta $0306,x
    lda $0700
    clc
    adc #$D0
    sta $0307,x
    lda #$FF
    sta $0308,x
    rts

.segment "BANK3_SIGN"
.export BarbaLivesDisplay

; Lives-remaining screen ($C405) draws standing open-air 24x48 Barba via
; BarbaDisplayClearBody so he keeps his full body and NMI elbow/tail.
BarbaLivesDisplay:
    lda #$00
    sta $C8
    sta $13
    sta $11
    sta $90
    sta $048D
    sta $0754
    sta $0752
    sta LAVA_CONTACT
    lda #$40                  ; facing right ($9F = 1)
    sta DRAW_ATTR
    lda #$01
    sta GEOMETRY
    lda #$84                  ; center 16px midsection in cols 16-18 (4px margin each side)
    sta DRAW_LEFT
    lda #$4C                  ; shift down 12px so midsection aligns with text row ($60)
    sta DRAW_TOP
    lda #$1B                  ; standing idle pose (3*9)
    sta DRAW_FRAME
    lda #$F8
    sta $0204
    sta $024C
    sta $02C4
    sta $0220
    sta $0224
    ldx #$1B                  ; standing idle pose (3*9); $FFC5 preserves X
    lda #>(BarbaDisplayBody-1)
    pha
    lda #<(BarbaDisplayBody-1)
    pha
    jmp $FFC5                 ; SwapToPRG0 -> BarbaDisplayBody
