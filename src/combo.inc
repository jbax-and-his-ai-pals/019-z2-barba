; Unreal Tournament-style running combo banner for town rampages.
; Lives in PRG bank 6 (called from BANK0 via ComboGateway).
; Uses WRAM $646C..$646F and $6488..$6489.
.segment "BANK6"
COMBO_ADD   = $646C         ; pending points added this frame (+3 kill, +1 building)
COMBO_PTS   = $646D         ; running combo score (saturates at $FF)
COMBO_TIER  = $646E         ; 0 none, 1 MULTI, 2 MEGA, 3 ULTRA, 4 MONSTER, 5 GODLIKE!
COMBO_TIMER = $646F         ; decay frames remaining
COMBO_SLAM  = $6488         ; tier-up slam/jitter animation counter
COMBO_DECAY_TIME = $B4      ; 180 frames (~3.0s) before combo dies
COMBO_BASE_Y     = $28      ; top row Y (clear of $20 HUD split)

ComboReset:
    lda #$00
    sta COMBO_ADD
    sta COMBO_PTS
    sta COMBO_TIER
    sta COMBO_TIMER
    sta COMBO_SLAM
    rts

ComboHide:
    ldx #$0F
    lda #$F8
@loop:
    ldy ComboOam,x
    sta $0200,y
    dex
    bpl @loop
    rts

; Called each frame in normal town play ($0707 = 1 or 2).
; Returns carry set if a combo banner is active (caller should skip ShoutWord).
ComboTick:
    lda COMBO_ADD
    beq @decay
    clc
    adc COMBO_PTS
    bcc :+
    lda #$FF
:
    sta COMBO_PTS
    lda #$00
    sta COMBO_ADD
    lda #COMBO_DECAY_TIME
    sta COMBO_TIMER
    ; Compute tier from COMBO_PTS: <12 -> 0, 12..23 -> 1, 24..39 -> 2, 40..59 -> 3, 60..84 -> 4, 85+ -> 5.
    lda COMBO_PTS
    ldx #$04
@tier_loop:
    cmp ComboThresholds,x
    bcs @got_tier
    dex
    bpl @tier_loop
    lda #$00
    beq @check_active
@got_tier:
    inx
    txa
    cmp COMBO_TIER
    beq @check_active
    bcc @check_active
    sta COMBO_TIER
    lda #$18
    sta COMBO_SLAM
    ; Punchy tier-up SFX (native block-break / hit channel).
    lda $ED
    ora #$10
    sta $ED
    bne @check_active
@decay:
    lda COMBO_TIMER
    beq @inactive
    dec COMBO_TIMER
    bne @check_active
    jsr ComboReset
    jsr ComboHide
@inactive:
    clc
    rts
@check_active:
    lda COMBO_TIER
    beq @inactive
    lda COMBO_SLAM
    beq :+
    dec COMBO_SLAM
:
    ; Blink during the last 45 frames (~0.75s) as a decay warning.
    lda COMBO_TIMER
    cmp #$2D
    bcs @draw
    and #$04
    bne @draw
    jsr ComboHide
    sec
    rts
@draw:
    jsr ComboDraw
    sec
    rts

ComboDraw:
    ldx COMBO_TIER
    dex
    stx $06                     ; 0-based tier index (0..4)
    ; Spacing: 8 px (tier 1), 9 px (tiers 2-3), 10 px (tiers 4-5).
    lda ComboSpacing,x
    sta $03
    ; Palette: $02 pale (tier 1), $01 fire (tiers 2-3), strobe $01/$02 (tiers 4-5).
    lda ComboPalette,x
    bpl :+
    lda $12
    and #$04
    lsr
    lsr
    clc
    adc #$01
:
    sta $02
    sta $08                     ; preserve text palette for counter (GODLIKE flames reuse $02)
    ; Base Y with tier-up drop-in slam (first 8 frames of COMBO_SLAM > 16).
    lda #COMBO_BASE_Y
    ldy COMBO_SLAM
    cpy #$11
    bcc :+
    sec
    sbc COMBO_SLAM
    clc
    adc #$10
:
    sta $00
    ; Angry shake: tiers 2-3 while COMBO_SLAM > 0 (±1), tiers 4-5 always (±1 / ±2).
    ldx $06
    cpx #$01
    bcc @no_shake
    cpx #$03
    bcs @hard_shake
    lda COMBO_SLAM
    beq @no_shake
@soft_shake:
    lda $12
    and #$03
    tay
    lda ComboShake1,y
    clc
    adc $00
    sta $00
    lda ComboShake1+1,y
    jmp @have_xshake
@hard_shake:
    lda $12
    and #$03
    tay
    lda ComboShake1,y
    cpx #$04
    bcc :+
    asl                         ; ±2 px on GODLIKE!
:
    clc
    adc $00
    sta $00
    lda ComboShake1+1,y
    cpx #$04
    bcc @have_xshake
    asl
    jmp @have_xshake
@no_shake:
    lda #$00
@have_xshake:
    sta $07                     ; X shake offset (signed)
    ; Draw Row 1.
    ldx $06
    lda ComboRow1X,x
    clc
    adc $07
    sta $01
    lda ComboRow1Start,x
    sta $05
    lda #$00
    sta $04                     ; OAM slot index 0..11
@row1_loop:
    ldx $05
    lda ComboRow1Tiles,x
    beq @row1_done
    ldx $04
    ldy ComboOam,x
    sta $0201,y
    lda $00
    sta $0200,y
    lda $02
    sta $0202,y
    lda $01
    sta $0203,y
    clc
    adc $03
    sta $01
    inc $04
    inc $05
    bne @row1_loop
@row1_done:
    ldx $06
    cpx #$04
    beq @godlike_flames
    ; Row 2 Y = Row 1 Y + 16 (disjoint from Row 1 8x16 scanlines to avoid >8-sprite dropout).
    lda $00
    clc
    adc #$10
    sta $00
    ; Draw "KILL!" on Row 2.
    lda ComboRow2X,x
    clc
    adc $07
    sta $01
    ldx #$00
    stx $05
@row2_loop:
    ldx $05
    lda ComboKillTiles,x
    beq @after_row2
    ldx $04
    ldy ComboOam,x
    sta $0201,y
    lda $00
    sta $0200,y
    lda $02
    sta $0202,y
    lda $01
    sta $0203,y
    clc
    adc $03
    sta $01
    inc $04
    inc $05
    bne @row2_loop
@after_row2:
    lda $00
    clc
    adc #$10                    ; Row 3 Y = Row 2 Y + $10
    sta $00
    bne @draw_counter
@godlike_flames:
    ; Two animated flame sprites ($84) flanking GODLIKE!, vertically centered on the text.
    ; Tile $84 has pixels in rows 5..12; shout glyphs sit in rows 7..15, so +3 aligns centers.
    lda $00
    clc
    adc #$03
    sta $00
    lda $12
    and #$08
    asl
    asl
    asl
    ora #$01                    ; palette 1, H-flip every 8 frames
    sta $02
    ; Alternate OAM priority between flames and the last two letters (E!) so all 10
    ; sprites stay visible under the NES 8-sprites-per-scanline limit.
    lda $12
    lsr
    bcc @flames_first
    ldx #$03
@copy_e:
    lda $02F4,x
    sta $0228,x
    lda $02FC,x
    sta $022C,x
    dex
    bpl @copy_e
    ldy #$F4
    lda #$FC
    bne @draw_flames
@flames_first:
    ldy #$28
    lda #$2C
@draw_flames:
    sta $05
    lda $00
    sta $0200,y
    lda #$84
    sta $0201,y
    lda $02
    sta $0202,y
    lda #$4F
    clc
    adc $07
    sta $0203,y
    ldy $05
    lda $00
    sta $0200,y
    lda #$84
    sta $0201,y
    lda $02
    eor #$40
    sta $0202,y
    lda #$A9
    clc
    adc $07
    sta $0203,y
    inc $04
    inc $04
    lda $00
    clc
    adc #$0D                    ; align counter to Row 1 Y + $10 (undo +$03 flame offset)
    sta $00
@draw_counter:
    ; Convert COMBO_PTS (1..255) to decimal: $09 = hundreds, $0A = tens, $05 = ones.
    lda COMBO_PTS
    ldx #$00
@hundreds:
    cmp #100
    bcc @tens_init
    sbc #100
    inx
    bne @hundreds
@tens_init:
    stx $09
    ldy #$00
@tens:
    cmp #10
    bcc @ones
    sbc #10
    iny
    bne @tens
@ones:
    sta $05
    sty $0A
    ; Center 2, 3, or 4 sprites (8 px each) around X=$80 + shake ($07).
    lda #$78
    ldx $09
    bne @four_chars
    cpy #$00
    beq @have_cx
    lda #$74
    bne @have_cx
@four_chars:
    lda #$70
@have_cx:
    clc
    adc $07
    sta $01
    lda #ShoutTile_X
    jsr @emit_counter_sprite
    ldx $09
    beq @maybe_tens
    lda ComboDigits,x
    jsr @emit_counter_sprite
    ldx $0A
    bpl @draw_tens              ; $0A is 0..9 (always non-negative)
@maybe_tens:
    ldx $0A
    beq @draw_ones
@draw_tens:
    lda ComboDigits,x
    jsr @emit_counter_sprite
@draw_ones:
    ldx $05
    lda ComboDigits,x
    jsr @emit_counter_sprite
@hide_rest:
    ldx $04
    lda #$F8
@hide_loop:
    cpx #$10
    bcs @done
    ldy ComboOam,x
    sta $0200,y
    inx
    bne @hide_loop
@done:
    rts
@emit_counter_sprite:
    ldx $04
    ldy ComboOam,x
    sta $0201,y
    lda $00
    sta $0200,y
    lda $08
    sta $0202,y
    lda $01
    sta $0203,y
    clc
    adc #$08
    sta $01
    inc $04
    rts

ComboOam:
    .byte $DC, $E0, $E4, $E8, $EC, $F0, $F4, $FC, $28, $2C, $30, $34, $D8, $C4, $AC, $94
ComboDigits:
    .byte ShoutTile_O, ShoutTile_1, ShoutTile_2, ShoutTile_3, ShoutTile_4
    .byte ShoutTile_5, ShoutTile_6, ShoutTile_7, ShoutTile_8, ShoutTile_9
ComboThresholds:
    .byte 12, 24, 40, 60, 85
ComboSpacing:
    .byte 8, 9, 9, 10, 10
ComboPalette:
    .byte $02, $01, $01, $80, $80   ; bit 7 = strobe between $01 and $02
ComboShake1:
    .byte $FF, $01, $00, $FF, $01
ComboRow1X:
    .byte $6C, $6F, $6A, $5E, $59
ComboRow2X:
    .byte $6C, $6A, $6A, $68, $00
ComboRow1Start:
    .byte 0, 6, 11, 17, 25
ComboRow1Tiles:
    .byte ShoutTile_M, ShoutTile_U, ShoutTile_L, ShoutTile_T, ShoutTile_I, $00                        ; 0: MULTI
    .byte ShoutTile_M, ShoutTile_E, ShoutTile_G, ShoutTile_A, $00                                     ; 6: MEGA
    .byte ShoutTile_U, ShoutTile_L, ShoutTile_T, ShoutTile_R, ShoutTile_A, $00                        ; 11: ULTRA
    .byte ShoutTile_M, ShoutTile_O, ShoutTile_N, ShoutTile_S, ShoutTile_T, ShoutTile_E, ShoutTile_R, $00 ; 17: MONSTER
    .byte ShoutTile_G, ShoutTile_O, ShoutTile_D, ShoutTile_L, ShoutTile_I, ShoutTile_K, ShoutTile_E, ShoutTile_Bang, $00 ; 25: GODLIKE!
ComboKillTiles:
    .byte ShoutTile_K, ShoutTile_I, ShoutTile_L, ShoutTile_L, ShoutTile_Bang, $00

.segment "BANK0"
