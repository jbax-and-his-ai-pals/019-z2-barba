; Outdoor town chimney smoke (Bank 3, BANK3_PAD).
; Draws up to 2 behind-BG rising smoke puffs per visible chimney ($59/$5A) into
; the tail of $6500..$65FF, yielding whenever a scanline band already has 5+
; foreground sprites (or the combo banner is active near the top).

SMOKE_RM    = $6340
SMOKE_WLD   = $6341
SMOKE_COUNT = $6342
SMOKE_X_LO  = $6343         ; 4 bytes
SMOKE_X_HI  = $6347         ; 4 bytes
SMOKE_Y     = $634B         ; 4 bytes
SMOKE_OAM_Y = $634F
SMOKE_TMP0  = $6350         ; base screen X of current chimney
SMOKE_TMP1  = $6351         ; current puff Y
SMOKE_BANDS = $6700        ; 16 bytes: foreground OAM counts per 16px Y band ($0..$F)
SMOKE_IDX   = $08           ; ZP scratch (safe during FinishSceneOam6)
SMOKE_PUFF  = $09
SMOKE_LOAD  = $0A           ; nonzero once SMOKE_BANDS is built this frame

.segment "BANK3_PAD"
HopTownSmoke2:
    lda #>(DrawTownSmoke2-1)
    pha
    lda #<(DrawTownSmoke2-1)
    pha
    lda #$02
    jmp $FFCC

.segment "BANK2_SMOKE"

DrawTownSmoke2:
    lda $0736
    cmp #$0B
    bne @ret
    lda $0726
    bne @ret
    lda $074C
    cmp #$02
    bcs @ret
    lda $0707
    beq @ret
    cmp #$03
    bcs @ret
    lda $0561
    cmp #$19
    bcc @active
    cmp #$3C
    beq @active
@ret:
    lda #$06
    jmp $FFCC

@active:
    ; The chimney list is built during the room load (ScanTownSmoke2, mode 9).
    ; If the key doesn't match (a room reached without that load), draw no
    ; smoke rather than spend a frame on a gameplay-time scan.
    lda $0561
    cmp SMOKE_RM
    bne @stale
    jsr SmokeRoomKey2
    cmp SMOKE_WLD
    beq @draw_ready
@stale:
    jsr SmokeRoomKey2
    sta SMOKE_WLD
    lda $0561
    sta SMOKE_RM
    lda #$00
    sta SMOKE_COUNT
@draw_ready:
    lda SMOKE_COUNT
    bne :+
    jmp @ret
:
    lda #$00
    sta SMOKE_LOAD
    lda #$FC
    sta SMOKE_OAM_Y
    lda #$00
    sta SMOKE_IDX
@chimney_loop:
    ldx SMOKE_IDX
    cpx SMOKE_COUNT
    bcs @ret

    ; Screen X = SMOKE_X[i] - camX ($072C/$072A)
    lda SMOKE_X_LO,x
    sec
    sbc $072C
    sta SMOKE_TMP0
    lda SMOKE_X_HI,x
    sbc $072A
    beq :+
    jmp @next_chimney        ; off-screen horizontally
:

    lda #$00
    sta SMOKE_PUFF
@puff_loop:
    ldx SMOKE_IDX
    ; age = (($12 >> 1) + idx * 11 + puff * 16) & $1F
    lda $12
    lsr
    clc
    adc SmokePhaseOff3,x
    ldy SMOKE_PUFF
    beq :+
    clc
    adc #$10
:
    and #$1F
    tay                      ; Y = age (0..31)

    ; puffY = SMOKE_Y[idx] - age
    lda SMOKE_Y,x
    sec
    sbc SmokeAgeVal3,y
    bcc @puff_skip
    cmp #$24
    bcs :+
@puff_skip:
    jmp @next_puff
:
    sta SMOKE_TMP1           ; puffY

    ; puffX = baseScreenX + sway[age >> 2]
    tya
    lsr
    lsr
    tax
    lda SMOKE_TMP0
    clc
    adc SmokeSway3,x
    bcs @next_puff
    pha                      ; stack: puffX

    ; Select puff tile by age: <10 -> $8F, <22 -> $91, else $93
    lda #$8F
    cpy #$0A
    bcc @have_tile
    lda #$91
    cpy #$16
    bcc @have_tile
    lda #$93
@have_tile:
    pha                      ; stack: puffX, tile

    ; Anti-flicker yield: if combo banner is up and puff is in its Y band (< $48), skip.
    lda $646E                ; COMBO_TIER
    beq @check_load
    lda SMOKE_TMP1
    cmp #$48
    bcc @pop2_next

@check_load:
    lda SMOKE_LOAD
    bne :+
    jsr SmokeBuildBands2
:
    ; O(1) check: sum foreground sprites in bands [b-1, b, b+1] where b = puffY >> 4 (>= 2).
    lda SMOKE_TMP1
    lsr
    lsr
    lsr
    lsr
    tax
    lda SMOKE_BANDS-1,x
    clc
    adc SMOKE_BANDS,x
    adc SMOKE_BANDS+1,x
    cmp #$05
    bcs @pop2_next

    ; Find a free tail OAM slot from SMOKE_OAM_Y down to $68.
    ldy SMOKE_OAM_Y
@find_slot:
    cpy #$68
    bcc @pop2_next
    lda $6500,y
    cmp #$F0
    bcs @slot_ok
    dey
    dey
    dey
    dey
    bne @find_slot
@pop2_next:
    pla
    pla
    jmp @next_puff

@slot_ok:
    lda SMOKE_TMP1
    sta $6500,y
    pla
    sta $6501,y              ; tile ($8F/$91/$93)
    lda #$21                 ; behind BG + town sprite palette 1
    sta $6502,y
    pla
    sta $6503,y              ; X
    dey
    dey
    dey
    dey
    sty SMOKE_OAM_Y

@next_puff:
    inc SMOKE_PUFF
    lda SMOKE_PUFF
    cmp #$02
    bcs @next_chimney
    jmp @puff_loop
@next_chimney:
    inc SMOKE_IDX
    jmp @chimney_loop

; Foreground OAM histogram over $6500..$6564 (16px Y bands). Clobbers A/X/Y.
SmokeBuildBands2:
    lda #$01
    sta SMOKE_LOAD
    ldx #$0F
    lda #$00
@clr_bands:
    sta SMOKE_BANDS,x
    dex
    bpl @clr_bands
    ldy #$64
@count_fg:
    lda $6500,y
    cmp #$F0
    bcs @count_next
    lsr
    lsr
    lsr
    lsr
    tax
    inc SMOKE_BANDS,x
@count_next:
    dey
    dey
    dey
    dey
    bpl @count_fg
    rts

; Key A = ($0707 << 4) | $0706.
SmokeRoomKey2:
    lda $0707
    asl
    asl
    asl
    asl
    ora $0706
    rts

; Room-load entry (game mode 9, hopped from SetupEncounterScenery6): record
; the room key and scan the freshly decoded metatile map once, while the
; screen is still off. Returns to Bank 6.
ScanTownSmoke2:
    jsr SmokeRoomKey2
    sta SMOKE_WLD
    lda $0561
    sta SMOKE_RM
    jsr ScanTownChimneys3
    lda #$06
    jmp $FFCC

; Scan $6000-$633F across populated pages (0..min($D1,3)) for chimney metatiles
; ($59/$5A) with sky ($40) directly above (row >= 2).
ScanTownChimneys3:
    lda $00
    pha
    lda $01
    pha
    lda #$00
    sta SMOKE_COUNT
    ldx $D1
    cpx #$04
    bcc :+
    ldx #$03
:
@page_loop:
    lda SmokePageLo3,x
    sta $00
    lda SmokePageHi3,x
    sta $01
    ldy #$20                 ; start at row 2 so (y - $10) >= $10 and Y >= $40
@y_loop:
    lda ($00),y
    cmp #$59
    beq @found_chimney
    cmp #$5A
    bne @next_y
@found_chimney:
    tya
    sec
    sbc #$10
    tay
    lda ($00),y
    pha
    tya
    clc
    adc #$10
    tay
    pla
    cmp #$40                 ; require sky directly above the chimney
    bne @next_y

    ; Record chimney: X_lo = (col << 4) + 12, X_hi = page, Y = $18 + (row << 4)
    stx SMOKE_TMP0           ; save page
    tya
    and #$0F
    asl
    asl
    asl
    asl
    clc
    adc #$0C
    ldx SMOKE_COUNT
    sta SMOKE_X_LO,x
    lda SMOKE_TMP0
    sta SMOKE_X_HI,x
    tya
    and #$F0
    clc
    adc #$18
    sta SMOKE_Y,x
    inc SMOKE_COUNT
    lda SMOKE_COUNT
    cmp #$04
    bcs @scan_done
    ldx SMOKE_TMP0

    ; Skip right half of the 2-wide chimney if on the same row.
    tya
    and #$0F
    cmp #$0F
    beq @next_y
    iny
    lda ($00),y
    cmp #$59
    beq @next_y
    cmp #$5A
    beq @next_y
    dey
@next_y:
    iny
    cpy #$D0
    bcc @y_loop
    dex
    bpl @page_loop
@scan_done:
    pla
    sta $01
    pla
    sta $00
    rts

SmokePageLo3:
    .byte $00, $D0, $A0, $70
SmokePageHi3:
    .byte $60, $60, $61, $62
SmokePhaseOff3:
    .byte 0, 11, 22, 5
SmokeSway3:
    .byte 0, 1, 1, 2, 2, 3, 3, 4
SmokeAgeVal3:
    .byte 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
    .byte 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31
