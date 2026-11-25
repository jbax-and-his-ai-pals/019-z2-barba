; Title screen lava CHR swap and floating lava-pixel / tiny-bubble particles (Bank 2).
; Runs in VBlank (TitleLavaChr2 -> R0/R5) and at the end of TitleEndNmi6
; (TitleLavaParticles2 -> OAM shadow slots $48/$4C, freed by trimming the
; two inner cliff columns at X=214/222 so scanlines 128..143 fit within 8 sprites).

TITLE_LAVA_DIRTY  = $6477
TITLE_PART_Y      = $6400   ; 4 bytes ($F8 = inactive/cooldown)
TITLE_PART_X      = $6404   ; 4 bytes
TITLE_PART_TIMER  = $6408   ; 4 bytes (active frames or cooldown frames)
TITLE_PART_KIND   = $640C   ; 4 bytes (bit 7: 0=lava pixel, 1=tiny bubble; bit 2: spawn Y; bit 1: wobble flip; bit 0: pal)
TITLE_PART_INIT   = $6410   ; 1 byte
TITLE_PART_RNG_LO = $6411   ; 1 byte (16-bit xorshift state)
TITLE_PART_RNG_HI = $6412   ; 1 byte
TITLE_PART_TMP    = $6413   ; 1 byte

.segment "BANK2_SMOKE"
.export TitleLavaChr2, TitleLavaParticles2

TitleWriteChr2:
    stx $64D5
    stx $8000
    sta $8001
    rts

TitleLavaChr2:
    bit $0100
    bvs @done
    lda $0726
    bne @restore
    lda $0736
    cmp #$03
    bcc @restore
    lda $12
    lsr
    lsr
    lsr
    and #$03
    tax
    lda @lava_bank,x
    ldx #$00
    jsr TitleWriteChr2
    lda #154
    ldx #$05
    jsr TitleWriteChr2
    lda #$01
    sta TITLE_LAVA_DIRTY
@done:
    lda #$05
    jmp $FFCC
@restore:
    lda TITLE_LAVA_DIRTY
    beq @done
    lda #$00
    sta TITLE_LAVA_DIRTY
    lda #$04
    ldx #$00
    jsr TitleWriteChr2
    lda #$03
    ldx #$05
    jsr TitleWriteChr2
    jmp @done
@lava_bank:
    .byte 238, 240, 242, 244

; Advance 16-bit xorshift (7, 9, 8) PRNG (period 65535) and return high byte in A.
; Preserves X and Y.
TitlePartNextRng2:
    lda TITLE_PART_RNG_HI
    lsr                     ; C = hi[0]
    lda TITLE_PART_RNG_LO
    ror                     ; A = (lo >> 1) | (hi[0] << 7), C = lo[0]
    eor TITLE_PART_RNG_HI
    sta TITLE_PART_RNG_HI
    lda #$00
    ror                     ; A = lo[0] << 7
    eor TITLE_PART_RNG_LO
    sta TITLE_PART_RNG_LO   ; s ^= s << 7
    lda TITLE_PART_RNG_HI
    lsr
    eor TITLE_PART_RNG_LO
    sta TITLE_PART_RNG_LO   ; s ^= s >> 9
    eor TITLE_PART_RNG_HI
    sta TITLE_PART_RNG_HI   ; s ^= s << 8
    rts

TitleLavaParticles2:
    bit $0100
    bvc :+
    jmp @off
:   lda $0726
    beq :+
    jmp @off
:   lda $0736
    cmp #$03
    bcs :+
    jmp @off
:   cmp #$05
    bcc :+
    jmp @off
:

    lda TITLE_PART_INIT
    bne @running
    lda #$01
    sta TITLE_PART_INIT
    lda $12
    eor #$5A
    sta TITLE_PART_RNG_LO
    lda $12
    asl
    eor #$A5
    ora #$01                ; ensure 16-bit PRNG seed is nonzero
    sta TITLE_PART_RNG_HI
    ldx #$01
@init_loop:
    lda #$F8
    sta TITLE_PART_Y,x
    lda TitlePartInitDelay,x
    sta TITLE_PART_TIMER,x
    dex
    bpl @init_loop

@running:
    jsr TitlePartNextRng2

    ldx #$01
@loop:
    ldy TitlePartOamOff,x
    lda TITLE_PART_Y,x
    cmp #$F8
    bne :+
    jmp @cooldown
:

    dec TITLE_PART_TIMER,x
    bne @active
    ; Despawn and draw an independent cooldown (4..35 frames).
    lda #$F8
    sta TITLE_PART_Y,x
    sta $6500,y
    jsr TitlePartNextRng2
    and #$1F
    clc
    adc #$04
    sta TITLE_PART_TIMER,x
    jmp @next

@active:
    lda TITLE_PART_TIMER,x
    and #$01
    bne @no_rise
    dec TITLE_PART_Y,x
@no_rise:
    lda TITLE_PART_TIMER,x
    and #$03
    bne @draw
    lda TITLE_PART_KIND,x
    and #$02
    asl
    eor TITLE_PART_TIMER,x
    and #$04
    beq @wobble_left
    inc TITLE_PART_X,x
    bne @draw
@wobble_left:
    dec TITLE_PART_X,x

@draw:
    lda TITLE_PART_Y,x
    sta $6500,y
    lda TITLE_PART_X,x
    sec
    sbc LAIR_SHAKE_X
    sta $6503,y
    lda TITLE_PART_KIND,x
    bmi @bubble
    ; Lava pixel: emerge bright at the lava line, then cool to orange and red.
    lda TITLE_PART_TIMER,x
    cmp #$0B
    bcc @cool_mid
    lda #$E9
    sta $6501,y
    lda TITLE_PART_KIND,x
    and #$01
    ora #$20
    sta $6502,y
    jmp @next
@cool_mid:
    cmp #$06
    bcc @cool_red
    lda #$C7
    sta $6501,y
    lda #$20
    sta $6502,y
    jmp @next
@cool_red:
    lda #$C7
    sta $6501,y
    lda #$21
    sta $6502,y
    jmp @next
@bubble:
    lda TITLE_PART_TIMER,x
    cmp #$04
    bcs :+
    lda #$C5
    bne @set_tile
:   cmp #$0B
    bcs :+
    lda #$C3
    bne @set_tile
:   lda #$C1
@set_tile:
    sta $6501,y
    lda TITLE_PART_KIND,x
    and #$01
    ora #$20
    sta $6502,y
    jmp @next

@cooldown:
    dec TITLE_PART_TIMER,x
    bne @hide
    ; Pick an open lava X across [8..109], [141..202], [215..218] (168 columns),
    ; keeping clear of Barba's head (116..139), col-26 split seam (208..215), and right cliff (224+).
    lda #$03
    sta TITLE_PART_TMP
@pick_x:
    jsr TitlePartNextRng2
    cmp #168
    bcc @have_x_idx
    dec TITLE_PART_TMP
    bpl @pick_x
    sec
    sbc #88                 ; bounded fallback (168..255 -> 80..167)
@have_x_idx:
    cmp #102
    bcc @left_lava
    cmp #164
    bcc @mid_lava
    adc #50                 ; carry set (164..167): +51 -> 215..218
    bne @set_x
@mid_lava:
    adc #39                 ; carry clear (102..163): +39 -> 141..202
    bne @set_x
@left_lava:
    adc #$08                ; carry clear (0..101): +8 -> 8..109
@set_x:
    sta TITLE_PART_X,x

    ; Independent active lifetime (12..25 frames, popping 5..12px up).
    jsr TitlePartNextRng2
    and #$0F
    cmp #14
    bcc :+
    sbc #$02
:   clc
    adc #12
    sta TITLE_PART_TIMER,x

    ; ~75% single-pixel emissions, ~25% tiny hollow bubbles; bit 1 = wobble dir, bit 2 = spawn Y.
    jsr TitlePartNextRng2
    sta TITLE_PART_TMP
    and #$03
    bne @pick_pixel
    lda TITLE_PART_TMP
    and #$07
    ora #$80
    bne @set_kind
@pick_pixel:
    lda TITLE_PART_TMP
    and #$07
@set_kind:
    sta TITLE_PART_KIND,x
    lsr
    lsr
    and #$01
    clc
    adc #$8C                ; spawn Y = $8C or $8D
    sta TITLE_PART_Y,x
    jmp @draw

@hide:
    lda #$F8
    sta $6500,y
@next:
    dex
    bmi @done
    jmp @loop

@off:
    lda #$00
    sta TITLE_PART_INIT
@done:
    lda #$05
    jmp $FFCC

TitlePartOamOff:
    .byte $48, $4C
TitlePartInitDelay:
    .byte 10, 45
