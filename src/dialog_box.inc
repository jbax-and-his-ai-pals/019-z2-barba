; Parameterized town dialog box renderer, eraser, and attribute save/restore (Bank 3).
; Draws/erases 1 tile row per frame so PPU macro uploads stay well inside VBlank.

DLG_BOX_WIDTH     = 18                  ; even tile count (14 vanilla, 16=+2, 18=+4, 20=+6)
DLG_BOX_PAIRS     = 6                   ; metatile rows (5 vanilla=10 rows, 6=+2=12 rows)
DLG_BOX_ROWS      = DLG_BOX_PAIRS * 2   ; tile rows (12)
DLG_BOX_OFFSET_X  = $58                 ; pixel X from ScrollX ($78 vanilla, $68=+2, $58=+4, $48=+6)
DLG_METATILES     = DLG_BOX_WIDTH / 2
DLG_ATTR_COLS     = (DLG_BOX_WIDTH / 4) + 1
DLG_TEXT_OFFSET_X = DLG_BOX_OFFSET_X + $10
DLG_TEXT_COLS     = DLG_BOX_WIDTH - 4

DLG_ROW0          = $6600               ; DLG_BOX_WIDTH bytes
DLG_META          = $6630               ; DLG_METATILES bytes
DLG_ATTR          = $6640               ; 6 * DLG_ATTR_COLS bytes (30 bytes for 5 cols)

.segment "BANK3_DLG"
.export DlgDrawRows, DlgEraseRow, DlgSaveAttr

; R1 replacement ($B0D2): build 1 tile row of the dialog box and emit PPU macro.
DlgDrawRows:
    ldx #$00
    lda $0525
    beq @border
    cmp #(DLG_BOX_ROWS - 1)
    beq @border
    lda #$CC
    ldy #$F4
    bne @fill
@border:
    lda #$CA
    ldy #$CB
@fill:
    sta DLG_ROW0,x
    inx
    tya
    ldy #(DLG_BOX_WIDTH - 2)
@fill_mid:
    sta DLG_ROW0,x
    inx
    dey
    bne @fill_mid
    lda DLG_ROW0
    sta DLG_ROW0,x

    jsr DlgDraw1Row
    lda $0525
    lsr
    bcs @no_attr                        ; emit attributes on even rows (0,2,4,6,8,10)
    jsr DlgMaskAttr
@no_attr:
    jsr $B151                           ; end PPU macro
    inc $0525
    lda $0525
    cmp #DLG_BOX_ROWS
    bcc @done
    inc $0524
@done:
    rts

; R3 replacement ($B183): erase 1 tile row of the dialog box from room metatiles.
DlgEraseRow:
    dec $0525
    bpl @erase
    jmp $B107                           ; advance $0524
@erase:
    lda $072C
    clc
    adc #DLG_BOX_OFFSET_X
    tax
    lda $072A
    adc #$00
    jsr $B3E5                           ; set $0E/$0F for screen
    txa
    lsr
    lsr
    lsr
    lsr
    tay
    lda $0525
    and #$FE                            ; (metatile_row) * 2
    asl
    asl
    asl                                 ; metatile_row * 16 ($10), starting at row 0 (Y=32)
    jsr $B32A                           ; advance $0E/$0F by A
    ldx #$00
@read_meta:
    lda ($0E),y
    sta DLG_META,x
    iny
    tya
    and #$0F
    bne @same_screen
    lda #$D0
    clc
    jsr $B32A
    tya
    sec
    sbc #$10
    tay
@same_screen:
    inx
    cpx #DLG_METATILES
    bcc @read_meta

    lda #$00
    sta $00
    sta $01
@conv_loop:
    ldx $00
    lda DLG_META,x
    and #$C0
    asl
    rol
    rol
    asl
    tay
    jsr $DFE4                           ; set $0E/$0F for TSA table
    lda DLG_META,x
    asl
    asl
    ldy $0525
    lsr $0525                           ; test bit 0? preserve $0525: use PHA/PLA
    sty $0525
    pha
    tya
    and #$01
    sta $02                             ; 0 for even row (top tiles), 1 for odd row (bot tiles)
    pla
    clc
    adc $02
    tay
    ldx $01
    lda ($0E),y
    sta DLG_ROW0,x
    iny
    iny
    lda ($0E),y
    sta DLG_ROW0 + 1,x
    inx
    inx
    stx $01
    inc $00
    cpx #DLG_BOX_WIDTH
    bcc @conv_loop

    jsr DlgDraw1Row
    lda $0525
    lsr
    bcs @no_restore_attr                ; restore attributes on even rows (after both tile rows)
    jsr DlgInitAttrWalk
@restore_attr:
    jsr DlgAttrHeader
    lda DLG_ATTR,x
    jsr DlgAttrWrite
    bcc @restore_attr
@no_restore_attr:
    jmp $B151                           ; end PPU macro

; Draw 1 row from DLG_ROW0 into PPU macro buffer ($0363+). Leaves Y at macro end.
DlgDraw1Row:
    ldy $0362
    lda #$80
    lsr $0525
    bcc :+
    lda #$A0
:
    rol $0525                           ; restore $0525
    sta $07
    lda $072C
    clc
    adc #DLG_BOX_OFFSET_X
    and #$F0
    sta $01
    lda $072A
    adc #$00
    sta $00
    lda $01
    eor #$FF
    clc
    adc #$01
    lsr
    lsr
    lsr
    lsr
    beq @full
    cmp #DLG_METATILES
    bcc @part
@full:
    lda #DLG_METATILES
@part:
    sta $06
    lda #DLG_METATILES
    sta $03
    ldx #$00
@seg:
    lda #$00
    sta $04
    lda $0525
    lsr                                 ; metatile_row = $0525 >> 1
    asl
    asl
    asl
    asl
    asl
    rol $04
    asl
    rol $04
    clc
    adc $07
    sta $05
    lda $04
    adc #$00
    and #$03
    sta $04
    lda $01
    lsr
    lsr
    lsr
    adc $05
    sta $0364,y
    lda $00
    and #$01
    asl
    asl
    adc #$20
    adc $04
    sta $0363,y
    lda $06
    asl
    sta $0365,y
    iny
    iny
    iny
@tile:
    lda DLG_ROW0,x
    sta $0363,y
    inx
    lda DLG_ROW0,x
    sta $0364,y
    inx
    lda $01
    clc
    adc #$10
    sta $01
    bcc :+
    inc $00
:
    iny
    iny
    dec $03
    beq @ret
    dec $06
    bne @tile
    lda $03
    sta $06
    jmp @seg
@ret:
    rts

DlgMaskAttr:
    jsr DlgInitAttrWalk
@mask_loop:
    jsr DlgAttrHeader
    lda #$0F
    sta $05
    lda #$F0
    sta $06
    lda $072C
    clc
    adc #DLG_BOX_OFFSET_X
    and #$F0
    sta $07
    and #$E0
    cmp $07
    beq @even_scroll
    lda $04
    bne @apply_mask
    lda #$3F
    sta $05
    lda #$F3
    bne @store_06
@even_scroll:
    lda $04
    cmp #(DLG_ATTR_COLS - 1)
    bne @apply_mask
    lda #$CF
    sta $05
    lda #$FC
@store_06:
    sta $06
@apply_mask:
    lda $0525
    lsr                                 ; metatile_row = $0525 >> 1
    lsr
    lda $06
    bcc :+                              ; even metatile_row = top half of attr byte ($06)
    lda $05                             ; odd metatile_row = bottom half of attr byte ($05)
:
    and DLG_ATTR,x
    sta DLG_ATTR,x
    jsr DlgAttrWrite
    bcc @mask_loop
    rts

DlgInitAttrWalk:
    lda $072A
    sta $00
    lda $072C
    sta $01
    lda #$00
    sta $04
    rts

; Emit attr PPU macro header at Y and compute X = attr_row * DLG_ATTR_COLS + $04.
DlgAttrHeader:
    lda $01
    clc
    adc #DLG_BOX_OFFSET_X
    php
    lsr
    lsr
    lsr
    lsr
    lsr
    sta $03
    plp
    lda $00
    adc #$00
    and #$01
    asl
    asl
    adc #$23
    sta $0363,y
    lda $0525
    lsr                                 ; metatile_row = $0525 >> 1 (0..5)
    lsr                                 ; DLG_ATTR row = metatile_row >> 1 (0..2)
    sta $02
    asl
    asl
    asl
    adc #$C8                            ; PPU attr row = DLG_ATTR row + 1 ($C8, $D0, $D8)
    adc $03
    sta $0364,y
    lda #$01
    sta $0365,y
    lda $02
.if DLG_ATTR_COLS = 4
    asl
    asl
.elseif DLG_ATTR_COLS = 5
    asl
    asl
    adc $02
.elseif DLG_ATTR_COLS = 6
    asl
    adc $02
    asl
.else
    .error "Unsupported DLG_ATTR_COLS"
.endif
    adc $04
    tax
    rts

DlgAttrWrite:
    sta $0366,y
    iny
    iny
    iny
    iny
    lda $01
    clc
    adc #$20
    sta $01
    lda $00
    adc #$00
    sta $00
    inc $04
    lda $04
    cmp #DLG_ATTR_COLS
    rts

; R4 replacement ($B350): save room palette attributes into DLG_ATTR.
DlgSaveAttr:
    ldx #(6 * DLG_ATTR_COLS - 1)
    lda #$00
@clr:
    sta DLG_ATTR,x
    dex
    bpl @clr

    lda $072C
    clc
    adc #DLG_BOX_OFFSET_X
    tax
    lda $072A
    adc #$00
    jsr $B3E5
    txa
    and #$E0
    lsr
    lsr
    lsr
    lsr
    tay
    ldx #$00
    lda #DLG_ATTR_COLS
    sta $00
@col_loop:
    lda #$00
    sta $01
@half_loop:
    lda #$0C
    sta $02
@row_loop:
    jsr @store_bits
    tya
    clc
    adc #$10
    tay
    asl
    asl
    asl
    asl
    bcs @same_attr_row
    txa
    clc
    adc #DLG_ATTR_COLS
    tax
@same_attr_row:
    dec $02
    bne @row_loop

    tya
    sec
    sbc #$BF
    tay
    and #$0F
    bne @no_screen_wrap
    lda $0E
    clc
    adc #$D0
    sta $0E
    bcc :+
    inc $0F
:
    tya
    sec
    sbc #$10
    tay
@no_screen_wrap:
    txa
    sec
    sbc #(6 * DLG_ATTR_COLS)
    tax
    lda $01
    eor #$80
    sta $01
    bne @half_loop

    inx
    dec $00
    bne @col_loop
    jmp $B107                           ; advance $0524

@store_bits:
    tya
    asl
    asl
    asl
    asl
    lda ($0E),y
    and #$C0
    bcs @bot_row
    asl
    rol
    rol
    bit $01
    bpl @or_attr
    asl
    asl
    jmp @or_attr
@bot_row:
    bit $01
    bmi @or_attr
    lsr
    lsr
@or_attr:
    ora DLG_ATTR,x
    sta DLG_ATTR,x
    rts
