; Unreal Tournament-style running combo banner for town rampages.
; Lives in PRG bank 6 (called from BANK0 via ComboGateway).
; Uses WRAM $646C..$646F and $6488..$6489.
.segment "BANK6"
COMBO_ADD   = $646C         ; pending points added this frame (+3 kill, +1 building)
COMBO_PTS   = $646D         ; running combo score (saturates at $FF)
COMBO_TIER  = $646E         ; 0 none, 1 DOUBLE, 2 MULTI, 3 MEGA, 4 ULTRA, 5 MONSTER, 6 GODLIKE!
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
    ldx #$0B
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
    ; Compute tier from COMBO_PTS: <6 -> 0, 6..8 -> 1, 9..11 -> 2, ..., 21+ -> 6.
    lda COMBO_PTS
    ldx #$05
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
    stx $06                     ; 0-based tier index (0..5)
    ; Spacing: 8 px (tiers 1-2), 9 px (tiers 3-4), 10 px (tiers 5-6).
    lda ComboSpacing,x
    sta $03
    ; Palette: $02 pale (tiers 1-2), $01 fire (tiers 3-4), strobe $01/$02 (tiers 5-6).
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
    ; Angry shake: tiers 3-4 while COMBO_SLAM > 0 (±1), tiers 5-6 always (±1 / ±2).
    ldx $06
    cpx #$02
    bcc @no_shake
    cpx #$04
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
    cpx #$05
    bcc :+
    asl                         ; ±2 px on GODLIKE!
:
    clc
    adc $00
    sta $00
    lda ComboShake1+1,y
    cpx #$05
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
    ; Row 2 Y = Row 1 Y + 12.
    lda $00
    clc
    adc #$0C
    sta $00
    ldx $06
    cpx #$05
    beq @godlike_flames
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
    beq @hide_rest
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
@godlike_flames:
    ; Two animated flame sprites ($84) flanking below GODLIKE!
    lda $12
    and #$08
    asl
    asl
    asl
    ora #$01                    ; palette 1, H-flip every 8 frames
    sta $02
    ldx $04
    ldy ComboOam,x
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
    inx
    ldy ComboOam,x
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
    inx
    stx $04
@hide_rest:
    ldx $04
    lda #$F8
@hide_loop:
    cpx #$0C
    bcs @done
    ldy ComboOam,x
    sta $0200,y
    inx
    bne @hide_loop
@done:
    rts

ComboOam:
    .byte $DC, $E0, $E4, $E8, $EC, $F0, $F4, $FC, $28, $2C, $30, $34
ComboThresholds:
    .byte 6, 9, 12, 15, 18, 21
ComboSpacing:
    .byte 8, 8, 9, 9, 10, 10
ComboPalette:
    .byte $02, $02, $01, $01, $80, $80   ; bit 7 = strobe between $01 and $02
ComboShake1:
    .byte $FF, $01, $00, $FF, $01
ComboRow1X:
    .byte $68, $6C, $6F, $6A, $5E, $59
ComboRow2X:
    .byte $6C, $6C, $6A, $6A, $68, $00
ComboRow1Start:
    .byte 0, 7, 13, 18, 24, 32
ComboRow1Tiles:
    .byte ShoutTile_D, ShoutTile_O, ShoutTile_U, ShoutTile_B, ShoutTile_L, ShoutTile_E, $00           ; 0: DOUBLE
    .byte ShoutTile_M, ShoutTile_U, ShoutTile_L, ShoutTile_T, ShoutTile_I, $00                        ; 7: MULTI
    .byte ShoutTile_M, ShoutTile_E, ShoutTile_G, ShoutTile_A, $00                                     ; 13: MEGA
    .byte ShoutTile_U, ShoutTile_L, ShoutTile_T, ShoutTile_R, ShoutTile_A, $00                        ; 18: ULTRA
    .byte ShoutTile_M, ShoutTile_O, ShoutTile_N, ShoutTile_S, ShoutTile_T, ShoutTile_E, ShoutTile_R, $00 ; 24: MONSTER
    .byte ShoutTile_G, ShoutTile_O, ShoutTile_D, ShoutTile_L, ShoutTile_I, ShoutTile_K, ShoutTile_E, ShoutTile_Bang, $00 ; 32: GODLIKE!
ComboKillTiles:
    .byte ShoutTile_K, ShoutTile_I, ShoutTile_L, ShoutTile_L, ShoutTile_Bang, $00

.segment "BANK0"
