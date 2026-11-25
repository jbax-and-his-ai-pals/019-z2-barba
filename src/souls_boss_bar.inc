; Dark Souls-style bottom boss health bar (Bank 4).
; Renders boss name above a 24-tile (192 px) horizontal bar at $2400 rows 0-2,
; displayed at scanline 215 via MMC3 IRQ + R1 CHR bank 156.
; On hit, the lost portion flashes white and drains smoothly right-to-left.

SOULS_ACTIVE      = $6352
SOULS_PHASE       = $6353
SOULS_BOSS_IDX    = $6354
SOULS_RED_STEPS   = $6355
SOULS_WHITE_STEPS = $6356
SOULS_HOLD_TIMER  = $6357
SOULS_DRAWN_RED   = $6358
SOULS_DRAWN_WHT   = $6359
SOULS_PREV_RED    = $635A

.segment "BANK1_SOULS"

; Input on stack (from DrawBossMeter4): HP (0 if dead, $FF if inactive); Y = boss index (0..7).
; Returns to Bank 6 via $FFCC.
SoulsBossBar1:
    pla
    cmp #$FF
    bne @active
    lda #$00
    sta SOULS_ACTIVE
    sta SOULS_PHASE
    jmp @return6

@active:
    sty SOULS_BOSS_IDX
    pha
    cpy #5
    bcs :+
    cpy #2
    beq :+
    jsr RemapBossSpr1
:
    pla
    cmp #$00
    beq @dead
    ldy SOULS_BOSS_IDX
    jsr ComputeSoulsSteps
    jmp @update_state
@dead:
    lda #$00
@update_state:
    sta SOULS_RED_STEPS
    lda SOULS_PHASE
    bne @running
    ; First frame of this boss fight: initialize state.
    lda SOULS_RED_STEPS
    sta SOULS_WHITE_STEPS
    sta SOULS_PREV_RED
    lda #$00
    sta SOULS_HOLD_TIMER
    lda #$FF
    sta SOULS_DRAWN_RED
    sta SOULS_DRAWN_WHT
    lda #$01
    sta SOULS_PHASE
    bne @queue_ppu

@running:
    ; Detect new damage -> trigger white hold timer.
    lda SOULS_RED_STEPS
    cmp SOULS_PREV_RED
    bcs @no_new_hit
    sta SOULS_PREV_RED
    lda #14
    sta SOULS_HOLD_TIMER
    bne @check_drain
@no_new_hit:
    sta SOULS_PREV_RED
@check_drain:
    lda SOULS_RED_STEPS
    cmp SOULS_WHITE_STEPS
    bcc @white_above
    ; Snaps up if healed or phase-reset.
    sta SOULS_WHITE_STEPS
    lda #$00
    sta SOULS_HOLD_TIMER
    beq @check_dead_done
@white_above:
    lda SOULS_HOLD_TIMER
    beq @shrink
    dec SOULS_HOLD_TIMER
    jmp @queue_ppu
@shrink:
    dec SOULS_WHITE_STEPS
@check_dead_done:
    lda SOULS_RED_STEPS
    ora SOULS_WHITE_STEPS
    bne @queue_ppu
    ; Boss dead and white drain finished: hide bar cleanly.
    lda #$00
    sta SOULS_ACTIVE
    sta SOULS_PHASE
@return6:
    lda #$06
    jmp $FFCC

@queue_ppu:
    lda $0725
    bne @ppu_busy_near
    lda $0362
    bne @ppu_busy_near
    lda SOULS_PHASE
    cmp #$01
    bne :+
    jmp @init_row0
:
    cmp #$02
    bne :+
    jmp @init_row1
:
    cmp #$03
    bne :+
    jmp @init_row2
:
    ; Phase 4 (live): redraw only the changed bar tiles [min_tile..max_tile].
    lda SOULS_RED_STEPS
    cmp SOULS_DRAWN_RED
    bne @redraw_bar
    lda SOULS_WHITE_STEPS
    cmp SOULS_DRAWN_WHT
    bne @redraw_bar
@ppu_busy_near:
    jmp @return6
@redraw_bar:
    ; Find first changed step = min(RED, DRAWN_RED) if red changed, else min(WHT, DRAWN_WHT).
    lda SOULS_RED_STEPS
    cmp SOULS_DRAWN_RED
    beq @only_white
    bcc :+
    lda SOULS_DRAWN_RED
:
    lsr
    lsr
    sta $04                  ; start_tile (0..23)
    jmp @find_end
@only_white:
    lda SOULS_WHITE_STEPS
    cmp SOULS_DRAWN_WHT
    bcc :+
    lda SOULS_DRAWN_WHT
:
    lsr
    lsr
    sta $04                  ; start_tile (0..23)
@find_end:
    ; Last changed step = max(WHT, DRAWN_WHT, RED, DRAWN_RED) - 1 (clamped >= 0).
    lda SOULS_WHITE_STEPS
    cmp SOULS_DRAWN_WHT
    bcs :+
    lda SOULS_DRAWN_WHT
:
    cmp SOULS_RED_STEPS
    bcs :+
    lda SOULS_RED_STEPS
:
    cmp SOULS_DRAWN_RED
    bcs :+
    lda SOULS_DRAWN_RED
:
    beq :+
    sec
    sbc #$01
:
    lsr
    lsr
    cmp #24
    bcc :+
    lda #23
:
    sta $05                  ; end_tile (0..23)
    ; Clamp start_tile <= 23 and start_tile <= end_tile.
    lda $04
    cmp #24
    bcc :+
    lda #23
    sta $04
:
    lda $05
    sec
    sbc $04
    bcs :+
    lda #$00
    sta $05
    beq @count_ready
:
    clc
    adc #$01
@count_ready:
    bne :+
    lda #$01
:
    sta $06                  ; count (1..24)
    lda #$24
    sta $0363
    lda #$24
    clc
    adc $04
    sta $0364
    lda $06
    sta $0365
    ldx #$00
    ldy $04                  ; current tile index
@partial_loop:
    ; tile_base = y * 4
    tya
    asl
    asl
    sta $07
    ; r = clamp(RED - tile_base, 0, 4)
    lda SOULS_RED_STEPS
    sec
    sbc $07
    bcs :+
    lda #$00
:
    cmp #$04
    bcc :+
    lda #$04
:
    sta $02
    ; total_fill = clamp(WHT - tile_base, 0, 4)
    lda SOULS_WHITE_STEPS
    sec
    sbc $07
    bcs :+
    lda #$00
:
    cmp #$04
    bcc :+
    lda #$04
:
    sec
    sbc $02
    bcs :+
    lda #$00
:
    sta $03                  ; w
    txa
    pha
    ldx $02
    lda SoulsRedBase,x
    clc
    adc $03
    adc #$94
    sta $02
    pla
    tax
    lda $02
    sta $0366,x
    inx
    iny
    dec $06
    bne @partial_loop
    lda #$FF
    sta $0366,x
    txa
    clc
    adc #$04
    sta $0362
    lda #$01
    sta $0725
    lda SOULS_RED_STEPS
    sta SOULS_DRAWN_RED
    lda SOULS_WHITE_STEPS
    sta SOULS_DRAWN_WHT
@ppu_busy:
    jmp @return6

@init_row0:
    lda #$24
    sta $0363
    lda #$00
    sta $0364
    lda #32
    sta $0365
    ldx #31
    lda #$80
:
    sta $0366,x
    dex
    bpl :-
    ; Copy boss name at column 3 ($0366 + 3 = $0369).
    ldy SOULS_BOSS_IDX
    lda SoulsNamePtrLo,y
    sta $00
    lda SoulsNamePtrHi,y
    sta $01
    ldy #$00
@name_loop:
    lda ($00),y
    beq @name_done
    sta $0369,y
    iny
    bne @name_loop
@name_done:
    lda #$FF
    sta $0366+32
    lda #36
    sta $0362
    lda #$01
    sta $0725
    lda #$02
    sta SOULS_PHASE
    jmp @return6

@init_row1:
    lda #$24
    sta $0363
    lda #$20
    sta $0364
    lda #32
    sta $0365
    lda #$80
    sta $0366
    sta $0367
    sta $0368
    lda #$92                 ; left endcap
    sta $0369
    ldx #$04
    jsr FillSoulsBarBuffer
    lda #$93                 ; right endcap
    sta $0366+28
    lda #$80
    sta $0366+29
    sta $0366+30
    sta $0366+31
    lda #$FF
    sta $0366+32
    lda #36
    sta $0362
    lda #$01
    sta $0725
    lda SOULS_RED_STEPS
    sta SOULS_DRAWN_RED
    lda SOULS_WHITE_STEPS
    sta SOULS_DRAWN_WHT
    lda #$03
    sta SOULS_PHASE
    jmp @return6

@init_row2:
    lda #$24
    sta $0363
    lda #$40
    sta $0364
    lda #32
    sta $0365
    ldx #31
    lda #$80
:
    sta $0366,x
    dex
    bpl :-
    lda #$FF
    sta $0366+32
    lda #36
    sta $0362
    lda #$01
    sta $0725
    lda #$04
    sta SOULS_PHASE
    lda #$01
    sta SOULS_ACTIVE
    jmp @return6

; Input: X = starting offset in $0366 (0 for $2424 redraw, 4 for $2420 full row).
; Writes 24 bar tiles based on SOULS_RED_STEPS and SOULS_WHITE_STEPS (0..96).
; Leaves X at X + 24.
FillSoulsBarBuffer:
    lda SOULS_RED_STEPS
    sta $00                  ; remaining red steps (0..96)
    lda SOULS_WHITE_STEPS
    sec
    sbc SOULS_RED_STEPS
    bcs :+
    lda #$00
:
    sta $01                  ; remaining white steps
    ldy #24
@tile_loop:
    ; Clamp red_in_tile = min(4, $00)
    lda $00
    cmp #$04
    bcc :+
    lda #$04
:
    sta $02                  ; r (0..4)
    lda $00
    sec
    sbc $02
    sta $00
    ; Available space in this tile = 4 - r
    lda #$04
    sec
    sbc $02
    cmp $01
    bcc :+
    lda $01
:
    sta $03                  ; w = min(4 - r, $01)
    lda $01
    sec
    sbc $03
    sta $01
    ; Tile = $94 + SoulsRedBase[r] + w
    txa
    pha
    ldx $02
    lda SoulsRedBase,x
    clc
    adc $03
    adc #$94
    sta $02
    pla
    tax
    lda $02
    sta $0366,x
    inx
    dey
    bne @tile_loop
    rts

SoulsRedBase:
    .byte 0, 5, 9, 12, 14

; Input: A = HP (>0), Y = boss index (0..7). Output: A = steps (1..96).
ComputeSoulsSteps:
    cpy #0
    beq @mul3
    cpy #1
    beq @mul2
    cpy #3
    beq @mul2
    cpy #2
    beq @mul4_div3
    cpy #4
    beq @mul2_div3
    cpy #7
    beq @mul12
    ; cpy #5 or #6 (MaxHP = 192 -> HP / 2)
    lsr
    bne @done
    lda #$01
@done:
    rts
@mul3:
    sta $00
    asl
    clc
    adc $00
    rts
@mul2:
    asl
    rts
@mul12:
    asl
    asl
    sta $00
    asl
    clc
    adc $00
    rts
@mul4_div3:
    ; HP * 4 / 3 (HP <= 72, so HP*4 <= 288 -> 16-bit)
    ldx #$00
    stx $01
    asl
    rol $01
    asl
    rol $01
    sta $00
    jmp @div3_16
@mul2_div3:
    ; HP * 2 / 3 (HP <= 144, so HP*2 <= 288 -> 16-bit)
    ldx #$00
    stx $01
    asl
    rol $01
    sta $00
@div3_16:
    ; Divide 16-bit ($01:$00) by 3, return quotient in A (clamped >= 1).
    ldx #$00
@div_loop:
    lda $00
    sec
    sbc #$03
    tay
    lda $01
    sbc #$00
    bcc @div_done
    sta $01
    sty $00
    inx
    bne @div_loop
@div_done:
    txa
    bne :+
    lda #$01
:
    rts

; Font tile IDs ($81..$91): A B C D E G H I K L M N O R S T U
.define SF_A $81
.define SF_B $82
.define SF_C $83
.define SF_D $84
.define SF_E $85
.define SF_G $86
.define SF_H $87
.define SF_I $88
.define SF_K $89
.define SF_L $8A
.define SF_M $8B
.define SF_N $8C
.define SF_O $8D
.define SF_R $8E
.define SF_S $8F
.define SF_T $90
.define SF_U $91
.define SF_SP $80

SoulsName0: .byte SF_H,SF_O,SF_R,SF_S,SF_E,SF_H,SF_E,SF_A,SF_D,0
SoulsName1: .byte SF_H,SF_E,SF_L,SF_M,SF_E,SF_T,SF_H,SF_E,SF_A,SF_D,0
SoulsName2: .byte SF_R,SF_E,SF_B,SF_O,SF_N,SF_A,SF_C,SF_K,0
SoulsName3: .byte SF_C,SF_A,SF_R,SF_O,SF_C,SF_K,0
SoulsName4: .byte SF_G,SF_O,SF_O,SF_M,SF_A,0
SoulsName5: .byte SF_B,SF_A,SF_R,SF_B,SF_A,0
SoulsName6: .byte SF_T,SF_H,SF_U,SF_N,SF_D,SF_E,SF_R,SF_B,SF_I,SF_R,SF_D,0
SoulsName7: .byte SF_D,SF_A,SF_R,SF_K,SF_SP,SF_B,SF_A,SF_R,SF_B,SF_A,0

SoulsNamePtrLo:
    .byte <SoulsName0,<SoulsName1,<SoulsName2,<SoulsName3
    .byte <SoulsName4,<SoulsName5,<SoulsName6,<SoulsName7
SoulsNamePtrHi:
    .byte >SoulsName0,>SoulsName1,>SoulsName2,>SoulsName3
    .byte >SoulsName4,>SoulsName5,>SoulsName6,>SoulsName7

; Remap $0000 (even) boss sprites for Horsehead (0), Helmethead (1), Carock (3),
; Gooma (4) to R5 extended banks 175..178 so all scanlines stay on A12=1.
RemapBossSpr1:
    tya
    pha
    lda BossSprR5Bank,y
    beq @done
    pha
    lda #$05
    sta $64D5
    sta $8000
    pla
    sta $8001
    ldx #$00
@loop:
    lda $6500,x
    cmp #$F0
    bcs @next
    lda $6501,x
    lsr
    bcs @next
    asl
    cmp #$08
    bcc @next
    cmp #$30
    bcs @gooma_hi
    clc
    adc #$B9
    sta $6501,x
    bne @next
@gooma_hi:
    cmp #$9E
    bcc @next
    cmp #$A4
    bcs @next
    clc
    adc #$4B
    sta $6501,x
@next:
    inx
    inx
    inx
    inx
    bne @loop
@done:
    pla
    tay
    rts

BossSprR5Bank:
    .byte 175, 176, 0, 177, 178
