; Overworld desert sand sparkle (Bank 3, BANK3_PAD).
; Draws up to 3 sparse, slow, per-tile glint sprites ($D0/$D2) over Desert
; ($04) tiles on the overworld ($0736 = 5), anchored to screen scroll ($FD/$FC).

OW_SPK_X      = $6430 ; 3 bytes: screen X (0..255)
OW_SPK_Y      = $6433 ; 3 bytes: screen Y ($20..$D7)
OW_SPK_TIMER  = $6436 ; 3 bytes: 0 = ready, 1..28 = visible, $80..$FF = cooldown
OW_SPK_PREV_X = $6439 ; 1 byte: previous $FD
OW_SPK_PREV_Y = $643A ; 1 byte: previous $FC
OW_SPK_PREV_W = $643B ; 1 byte: previous $0706 (continent/region)
OW_SPK_ACTIVE = $643C ; 1 byte: nonzero once prev scroll initialized
OW_SPK_DX     = $643D ; 1 byte: frame scroll delta X
OW_SPK_DY     = $643E ; 1 byte: frame scroll delta Y
OW_SPK_TMP    = $643F ; 1 byte: bit 7 = spawn tried this frame, bits 0..1 = slot
OW_SPK_KIND   = $648C ; 3 bytes: 0 = desert/grass glint, 1 = water, 2 = swamp, 3 = mtn/lava, 4 = graveyard wisp

.segment "BANK4_SPK"

OwSparkle4:
    lda $0726
    beq :+
OwSpkClearRet4:
    lda #$00
    sta OW_SPK_ACTIVE
    beq OwSpkRet4
:
    lda $074C
    bne OwSpkRet4
    lda OW_SPK_ACTIVE
    beq @init
    lda $0706
    cmp OW_SPK_PREV_W
    beq OwSpkScroll4
@init:
    lda $FD
    sta OW_SPK_PREV_X
    lda $FC
    sta OW_SPK_PREV_Y
    lda $0706
    sta OW_SPK_PREV_W
    lda #$01
    sta OW_SPK_ACTIVE
    lda #$E8
    sta OW_SPK_TIMER
    lda #$D0
    sta OW_SPK_TIMER+1
    lda #$B8
    sta OW_SPK_TIMER+2
OwSpkRet4:
    lda #$06
    jmp $FFCC

OwSpkScroll4:
    lda $FD
    sec
    sbc OW_SPK_PREV_X
    sta OW_SPK_DX
    lda $FD
    sta OW_SPK_PREV_X
    lda OW_SPK_DX
    jsr OwSpkCheckDelta4
@ow_spk_clear_bcs:
    bcs OwSpkClearRet4

    lda $FC
    sec
    sbc OW_SPK_PREV_Y
    sta OW_SPK_DY
    lda $FC
    sta OW_SPK_PREV_Y
    lda OW_SPK_DY
    ; Correct 240-scanline wrap ($EF <-> $00) before bounds check.
    cmp #$09
    bcc @dy_ok
    cmp #$20
    bcs :+
    sbc #$10            ; wrapped 239 -> 0: subtract 16
    sta OW_SPK_DY
    bcc @dy_ok
:   cmp #$E0
    bcc OwSpkClearRet4
    cmp #$F8
    bcs @dy_ok
    adc #$10            ; wrapped 0 -> 239: add 16
    sta OW_SPK_DY
@dy_ok:
    lda OW_SPK_DY
    jsr OwSpkCheckDelta4
    bcs @ow_spk_clear_bcs

    lda #$00
    sta OW_SPK_TMP        ; bit 7 = already attempted a spawn this frame
    ldy #$02
OwSpkLoop4:
    lda OW_SPK_TIMER,y
    beq OwSpkTrySpawn4
    bmi @cooldown
    jmp OwSpkActive4
@cooldown:
    lda OW_SPK_TIMER,y
    clc
    adc #$01
    sta OW_SPK_TIMER,y
OwSpkNext4:
    dey
    bpl OwSpkLoop4
    bmi OwSpkRet4

; Carry set if |A| > 8.
OwSpkCheckDelta4:
    cmp #$09
    bcc @delta_ok
    cmp #$F8
    bcs @delta_ok
    sec
    rts
@delta_ok:
    clc
    rts

OwSpkTrySpawn4:
    lda $7D             ; only spawn when tile-aligned
    bne OwSpkNext4
    bit OW_SPK_TMP
    bmi OwSpkNext4
    tya
    ora #$80
    sta OW_SPK_TMP
    jsr OwSparkleSpawn4
    bcs OwSpkNext4
    ; Spawn succeeded: fall through to draw on the first frame.
    jmp OwSpkActive4

.segment "BANK4_SPK"
; Render slot Y by OW_SPK_KIND,y into OAM slot X (runs in BANK4_SPK).
OwSpkDrawKind4:
    txa
    pha                 ; stack: oam_x
    lda OW_SPK_KIND,y
    cmp #$02
    bcc OwSpkNoRise4
    beq OwSpkSwampRise4
    cmp #$04
    bne @mtn_rise
    jmp OwSpkGraveMove4
@mtn_rise:
    lda #$03
    .byte $2C           ; BIT abs skips lda #$07
OwSpkSwampRise4:
    lda #$07
    and OW_SPK_TIMER,y
    bne OwSpkNoRise4
    lda OW_SPK_Y,y
    sec
    sbc #$01
    sta OW_SPK_Y,y
OwSpkNoRise4:
    ldx OW_SPK_KIND,y
    lda OW_SPK_TIMER,y
    cmp OwKindHi,x
    bcs @ph0
    cmp OwKindLo,x
    bcs @ph1
    lda OwKindTile2,x
    bne @put
@ph0:
    lda OwKindTile0,x
    bne @put
@ph1:
    lda OwKindTile1,x
@put:
    jmp OwSpkWriteOam4

.segment "BANK4_SPK2"
OwSpkActive4:
    lda OW_SPK_DX
    beq @no_dx
    bpl @dx_pos
    eor #$FF
    sec
    adc OW_SPK_X,y
    bcs @kill
    sta OW_SPK_X,y
    bcc @no_dx
@dx_pos:
    lda OW_SPK_X,y
    sec
    sbc OW_SPK_DX
    bcc @kill
    sta OW_SPK_X,y
@no_dx:
    lda OW_SPK_DY
    beq @no_dy
    bpl @dy_pos
    eor #$FF
    sec
    adc OW_SPK_Y,y
    bcs @kill
    sta OW_SPK_Y,y
    bcc @check_y
@dy_pos:
    lda OW_SPK_Y,y
    sec
    sbc OW_SPK_DY
    bcc @kill
    sta OW_SPK_Y,y
@check_y:
    cmp #$1E
    bcc @kill
    cmp #$D8
    bcs @kill
@no_dy:
    lda OW_SPK_TIMER,y
    sec
    sbc #$01
    sta OW_SPK_TIMER,y
    beq @finish_sparkle
    ; Find a free $65xx OAM slot scanning down from $FC.
    ldx #$FC
@find_oam:
    lda $6500,x
    cmp #$F0
    bcs @got_oam
    txa
    sec
    sbc #$04
    tax
    cmp #$20
    bcs @find_oam
    jmp OwSpkNext4
@got_oam:
    jmp OwSpkDrawKind4

@finish_sparkle:
@kill:
    ; Staggered cooldown: -48..-17 ($D0..$EF), or -112..-81 ($90..$AF) for graveyard.
    lda $051E
    eor OW_SPK_X,y
    and #$1F
    ldx OW_SPK_KIND,y
    cpx #$04
    beq @grave_cd
    ora #$D0
    .byte $2C
@grave_cd:
    ora #$90
    sta OW_SPK_TIMER,y
    jmp OwSpkNext4

; Reject candidate slot Y if within 48 px (both X and Y) of another active sparkle.
OwSpkDistCheck4:
    ldx #$02
@dist_loop:
    txa
    eor OW_SPK_TMP
    and #$03
    beq @dist_next
    lda OW_SPK_TIMER,x
    beq @dist_next
    bmi @dist_next
    lda OW_SPK_X,x
    sec
    sbc OW_SPK_X,y
    bcs :+
    eor #$FF
    adc #$01
:   cmp #48
    bcs @dist_next
    lda OW_SPK_Y,x
    sec
    sbc OW_SPK_Y,y
    bcs :+
    eor #$FF
    adc #$01
:   cmp #48
    bcc @too_close
@dist_next:
    dex
    bpl @dist_loop
    ldx OW_SPK_KIND,y
    lda OwKindDur,x
    sta OW_SPK_TIMER,y
    clc
    rts
@too_close:
    lda #$F8
    sta OW_SPK_TIMER,y
    sec
    rts

OwSpkWriteOam4:
    pha                 ; stack: tile, oam_x
    tsx
    lda $0102,x
    tax                 ; X = oam_x
    lda OW_SPK_Y,y
    sta $6500,x
    pla                 ; A = tile
    sta $6501,x
    pla                 ; drop oam_x
    lda OW_SPK_KIND,y
    cmp #$01
    beq @attr2
    lda #$00
    .byte $2C
@attr2:
    lda #$02
    sta $6502,x
    lda OW_SPK_X,y
    sta $6503,x
    jmp OwSpkNext4

OwKindTile0:
    .byte $D1, $D5, $D9, $D1, $E1
OwKindTile1:
    .byte $D3, $D7, $DB, $DD, $E3
OwKindTile2:
    .byte $D1, $D5, $D3, $DF, $E1

.segment "BANK4_SPK3"
; Pick a random visible tile around Link; if Desert ($04), populate slot Y
; and return with Carry clear. Otherwise set short cooldown and Carry set.
OwSparkleSpawn4:
    lda $051A
    eor $051F
    and #$0F
    cmp #$0F
    bne :+
    lda #$07
:   pha                 ; stack: dx+7 (0..14)
    clc
    adc $74
    sec
    sbc #$07
    bmi @fail_dx
    cmp #$40
    bcs @fail_dx
    clc
    adc #$01
    sta OW_SPK_X,y      ; temp: tx + 1

    lda $051D
    eor $0522
    eor $12
    and #$0F
    cmp #$0B
    bcc :+
    sbc #$0B
:   pha                 ; stack: dy+5 (0..10), dx+7
    clc
    adc $73
    sec
    sbc #$05
    bcc @fail_dy
    sec
    sbc #$1E
    bcc @fail_dy
    cmp #$4B
    bcs @fail_dy

    ; Lookup terrain at (tx, row=A) in $7C00 via $6000 row pointer table.
    asl
    tax                 ; X = row * 2
    lda $0E
    pha
    lda $0F
    pha                 ; stack: old0F, old0E, dy+5, dx+7
    lda $6000,x
    sta $0E
    lda $6001,x
    sta $0F
    lda OW_SPK_TMP
    and #$03
    tax                 ; X = slot (0..2)
    lda #$00
    sta OW_SPK_Y,x      ; temp: running RLE column
    tay
@rle:
    lda ($0E),y
    lsr
    lsr
    lsr
    lsr
    sec
    adc OW_SPK_Y,x
    sta OW_SPK_Y,x
    cmp OW_SPK_X,x
    bcs @rle_done
    iny
    bne @rle
@rle_done:
    lda ($0E),y
    and #$0F
    sta OW_SPK_X,x
    pla
    sta $0F
    pla
    sta $0E
    txa
    tay                 ; restore Y = slot (0..2)
    ldx OW_SPK_X,y
    lda OwTerrainKind,x
    bpl @has_kind
@not_sand:
    pla                 ; drop dy+5
@fail_dx:
    pla                 ; drop dx+7
    lda #$F8            ; short 8-frame retry cooldown
    sta OW_SPK_TIMER,y
    sec
    rts
@fail_dy:
    pla                 ; drop dy+5
    jmp @fail_dx

@has_kind:
    jsr OwSpkKind4
    ; Pick one of 8 offsets in the 16x16 metatile.
    lda $051C
    eor $051D
    and #$07
    tax
    pla                 ; dy+5 (0..10)
    asl
    asl
    asl
    asl
    clc
    adc #$1E
    clc
    adc OwSpkOffY,x
    sta OW_SPK_Y,y

    ; Compute screen X = (dx+7)*16 + $0F + ox ($10 - 1 center).
    pla                 ; dx+7 (0..14)
    asl
    asl
    asl
    asl
    clc
    adc #$0F
    clc
    adc OwSpkOffX,x
    sta OW_SPK_X,y

    jmp OwSpkDistCheck4

OwSpkOffX:
    .byte 5, 9, 6, 10, 4, 8, 2, 12
OwSpkOffY:
    .byte 0, 1, 11, 12, 6, 7, 4, 14
OwKindHi:
    .byte 21, 17, 30, 27, 36
OwKindLo:
    .byte 9, 7, 9, 13, 14

; Terrain ID (0..15) -> particle kind (0=glint, 1=water, 2=swamp, 3=ember, 4=graveyard, $FF=none).
OwTerrainKind:
    .byte $FF, $FF, $FF, $FF, $00, $FF, $FF, $02
    .byte $04, $FF, $03, $03, $01, $01, $03, $FF

.segment "BANK4_SPK4"
OwSpkGraveMove4:
    lda OW_SPK_TIMER,y
    and #$0F
    bne @grave_rise
    ldx #$01
    lda OW_SPK_TIMER,y
    and #$10
    beq @add
    ldx #$FF
@add:
    txa
    clc
    adc OW_SPK_X,y
    sta OW_SPK_X,y
@grave_rise:
    jmp OwSpkSwampRise4

.segment "BANK4_SPK"
OwKindDur:
    .byte 28, 24, 44, 40, 48

.segment "PALACE_ROAR"
OwSpkKind4:
    cpx #$0A
    bne :+
    ldx $0706
    bne :+
    lda #$02            ; West Hyrule Saria river: foul water bubbles, not lava embers
:
    sta OW_SPK_KIND,y
    rts
