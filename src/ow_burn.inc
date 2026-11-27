; Overworld Burn: Forest ($06) always, Mountain ($0B) on NG+ ($07A0 != 0).
;
; 1. RLE $04 merge/split/delete:
;    - BANK0_OW + BANK0_TAIL: BarbaOverworldB_OW + BarbaBurnTile0 (merge + dispatch)
;    - BANK2_OW + BANK2_OW2:  OwSplitShift2 (RLE split + right shift)
;    - BANK5_OW:              OwDeleteByte5 (1-tile run delete + left shift)
; 2. Live PPU attribute update (BANK4_OW + BANK4_OW2):
;    - OwAttrUpdate4: computes 32x32 attr byte for ($79,$7A) and appends to $0301.

.segment "BANK0_OW"

BarbaBurnTile0:
    sty $01             ; save original Y
    lda ($0E),y
    tax
    and #$0F
    sta $0C             ; $0C = original terrain ($06 or $0B)
    txa
    lsr
    lsr
    lsr
    lsr                 ; A = run_len - 1 (0..15)
    tax
    lda $03
    sec
    sbc $00
    sta $02             ; $02 = right_count
    txa
    sec
    sbc $02
    sta $03             ; $03 = left_count

    ; --- Try left merge ($03 == 0 && Y > 0) ---
    lda $03
    bne @try_right
    tya
    beq @try_right
    dey
    jsr @can_merge_y
    bcs @do_left_merge
    iny
@try_right:
    ; --- Try right merge ($02 == 0 && $00 < $40) ---
    lda $02
    bne @no_merge
    lda $00
    cmp #$40
    bcs @no_merge
    iny
    jsr @can_merge_y
    bcc @restore_y_nomerge
    dey
    lda $03             ; remaining = left_count (set Z after dey)
    jmp @finish_merge
@restore_y_nomerge:
    dey
    jmp @no_merge

@do_left_merge:
    iny
    lda $02             ; remaining = right_count
@finish_merge:
    beq @del_hop        ; remaining == 0 -> delete 1-tile run
    sec
    sbc #$01
    asl
    asl
    asl
    asl
    ora $0C
    sta ($0E),y
    jmp BurnAttrHop0

@can_merge_y:
    lda ($0E),y
    tax
    and #$0F
    cmp #$04
    bne @no_c
    txa
    and #$F0
    cmp #$F0
    beq @no_c
    txa
    clc
    adc #$10
    sta ($0E),y
    sec
    rts
@no_c:
    clc
    rts

@del_hop:
    lda #>(OwDeleteByte5 - 1)
    ldx #<(OwDeleteByte5 - 1)
    ldy #$05
    bne @hop_with_end

@no_merge:
    ldx #$00
    lda $03
    beq :+
    inx
:   lda $02
    beq :+
    inx
:   stx $05             ; $05 = insert (0, 1, or 2)
    bne @split_hop
    lda #$04
    sta ($0E),y
    jmp BurnAttrHop0

@split_hop:
    lda #>(OwSplitEntry2 - 1)
    ldx #<(OwSplitEntry2 - 1)
    ldy #$02
@hop_with_end:
    pha
    txa
    pha
    tya
    pha
    lda $6094
    sta $08
    lda $6095
    sta $09
    jsr BurnFindRow4aEnd0
    pla
    jmp $FFCC

.segment "BANK0_TAIL"
BurnFindRow4aEnd0:
    ldy #$00
    sty $0A
@f4a_loop:
    lda ($08),y
    lsr
    lsr
    lsr
    lsr
    sec
    adc $0A
    sta $0A
    cmp #$40
    bcs @f4a_done
    iny
    bne @f4a_loop
@f4a_done:
    rts

.segment "BANK2_OW3"
OwSplitEntry2:
    tya
    clc
    adc $08
    tay
    lda $09
    adc #$00
    sta $09
    cmp #$7F
    bcc @ok
    cpy #$F0
    bcc @ok
    lda #$00
    sta $0301
    lda #$FF
    sta $0302
    jmp $FFC5
@ok:
    tya
    clc
    adc $05
    lda $09
    adc #$00
    sta $0B             ; $0B = dst_hi
    jmp OwSplitShift2

.segment "BANK2_OW"
; Split RLE run: shift right by $05, update row pointers, write [left][$04][right],
; then hop to Bank 4 OwAttrUpdate4.
OwSplitShift2:
    lda #$00
    sta $08
    lda $05
    sta $0A
    lda $04
    asl
    tax
    inx
    inx
@inc_ptrs:
    cpx #$96
    bcs @shift_right
    lda $6000,x
    clc
    adc $05
    sta $6000,x
    bcc :+
    inc $6001,x
:   inx
    inx
    bne @inc_ptrs
@shift_right:
    lda $01
    clc
    adc $0E
    sta $06
    lda $0F
    adc #$00
    sta $07
    lda $09
    cmp $07
    beq @last_page
@page_loop:
    lda ($08),y
    sta ($0A),y
    tya
    beq @prev_page
    dey
    jmp @page_loop
@prev_page:
    dec $09
    dec $0B
    ldy #$FF
    lda $09
    cmp $07
    bne @page_loop
@last_page:
    cpy $06
    beq @write_runs
    lda ($08),y
    sta ($0A),y
    dey
    jmp @last_page
@write_runs:
    jmp OwSplitWrite2

.segment "BANK2_OW2"
OwSplitWrite2:
    ldy $01
    lda $03
    beq @write_burnt
    jsr @pack_orig
    iny
@write_burnt:
    lda #$04
    sta ($0E),y
    lda $02
    beq @to_attr
    iny
    jsr @pack_orig
@to_attr:
    lda #>(OwAttrUpdate4 - 1)
    pha
    lda #<(OwAttrUpdate4 - 1)
    pha
    lda #$04
    jmp $FFCC
@pack_orig:
    sec
    sbc #$01
    asl
    asl
    asl
    asl
    ora $0C
    sta ($0E),y
    rts

.segment "BANK5_OW"
; Entry: Y = row-$4A end index, $08/$09 = row-$4A base (from BurnFindRow4aEnd0).
OwDeleteByte5:
    tya
    clc
    adc $08
    sta $0A
    lda $09
    adc #$00
    sta $0B
    lda $04
    asl
    tax
    inx
    inx
@dec_ptrs:
    cpx #$96
    bcs @del_setup
    lda $6000,x
    sec
    sbc #$01
    sta $6000,x
    bcs :+
    dec $6001,x
:   inx
    inx
    bne @dec_ptrs
@del_setup:
    lda $01
    clc
    adc $0E
    sta $06
    lda $0F
    adc #$00
    sta $07
    lda $06
    clc
    adc #$01
    sta $08
    lda $07
    adc #$00
    sta $09
    ldy #$00
@del_loop:
    lda $06
    cmp $0A
    bne @del_copy
    lda $07
    cmp $0B
    beq @done_del
@del_copy:
    lda ($08),y
    sta ($06),y
    inc $06
    bne :+
    inc $07
:   inc $08
    bne @del_loop
    inc $09
    jmp @del_loop
@done_del:
    lda #>(OwAttrUpdate4 - 1)
    pha
    lda #<(OwAttrUpdate4 - 1)
    pha
    lda #$04
    jmp $FFCC

.segment "BANK4_OW2"
OwPalCodes4:
    .byte $02,$01,$02,$01,$03,$00,$00,$00
    .byte $01,$01,$01,$01,$03,$03,$01,$01

OwAttrSetup4:
    lda $79
    ora #$03
    sta $030C
    lda $7A
    and #$1F
    sta $02             ; tx
    lsr
    and #$01
    sta $03             ; quad_x
    lda $7A
    asl
    rol
    rol
    and #$01
    sta $06             ; quad_y
    lda $7A
    asl
    lda $79
    and #$03
    rol
    asl
    asl
    asl
    sta $07             ; attr_row << 3
    lda $02
    lsr
    lsr
    ora $07
    ora #$C0
    sta $030D
    rts

.segment "BANK4_OW"
OwAttrUpdate4:
    jsr OwAttrSetup4
    lda #$01
    sta $030E
    lda $76
    sec
    sbc $03
    sta $08             ; base_x = facing_map_x ($76) - quad_x
    lda $04
    sec
    sbc $06
    sta $09             ; base_row
    lda #$00
    sta $0A             ; packed attr_val
    ldx #$03            ; k = 3 (BR), 2 (BL), 1 (TR), 0 (TL)
@attr_quad_loop:
    stx $0B
    txa
    lsr
    clc
    adc $09
    cmp #$4B
    bcc @row_ok
    lda #$00
    beq @shift_pal
@row_ok:
    asl
    tay
    lda $6000,y
    sta $06
    lda $6001,y
    sta $07
    txa
    and #$01
    sec
    adc $08             ; 1-based target_x = base_x + col_off + 1
    sta $0C
    ldy #$00
    sty $0D
@dec_loop:
    lda ($06),y
    lsr
    lsr
    lsr
    lsr
    sec
    adc $0D
    sta $0D
    cmp $0C
    bcs @dec_found
    iny
    bne @dec_loop
@dec_found:
    lda ($06),y
    and #$0F
    tax
    lda OwPalCodes4,x
    cpx #$0A
    bne @shift_pal
    ldx $0706
    bne @shift_pal
    lda #$00
@shift_pal:
    asl $0A
    asl $0A
    ora $0A
    sta $0A
    ldx $0B
    dex
    bpl @attr_quad_loop
    sta $030F
    lda #$FF
    sta $0310
    lda #$0E
    sta $0301
    jmp $FFC5
