; Dark cave firelight envelope + rounded fireball glow halo.
; CaveFireLightHop6 (Bank 6, BANK6_HAZE) gates on West Hyrule / Death Mountain
; side-view ($0736=$0B, $0707=0) without the Candle ($0785=0) under the dark
; grotto palette ($07AF & $38 == $08). Fast-returns in Bank 6 with 0 bank
; switches when idle; otherwise hops to CaveFireLight1 in BANK1_SOULS.
;
; 1. Glow halo: checks live fireball RAM ($8D, $8E, $6400, $6410, $6420) and
;    places a rounded, stippled behind-BG OAM halo ($87, Pal 2, rotating flip)
;    in free shadow slots (CLOUD_OAM_START down to $60) behind each live fireball.
; 2. Envelope lighting: computes target intensity 0..9 from live fireball count
;    (1->4, 2->6, 3->8, 4-5->9 capped), ignites immediately to dim ember (1),
;    swells (+1 / 3 frames) to crescendo with subtle top-end PRNG shimmer,
;    descends as fireballs expire, and fades smoothly (-1 / 2 frames) back to
;    cold blue (0) when no fireballs remain. Applies palettes directly in VBlank
;    (CaveApplyPalHop6 -> CaveApplyPal2) and $2001 emphasis below scanline 31
;    via CAVE_LIGHT_DISP ($6741).
CAVE_GLOW_ON    = $64FF         ; bits 0..3 = Cur (0..9), bits 4..7 = Tick (0..3)
CAVE_PAL_PEND   = $635F         ; bits 0..3 = pending level+1 (1..10), bit 7 = Barba defer
CAVE_LIGHT_DISP = $6741         ; bits 0..3 = Disp (0..9), bits 5..7 = $2001 emph ($00/$20/$E0)

.segment "BANK6_HAZE"

CaveFireLightHop6:
    lda $0736
    cmp #$0B
    bne @not_dark
    lda $0707
    ora $0785
    ora $0726
    bne @not_dark
    lda $07AF
    and #$38
    cmp #$08
    bne @not_dark
    lda $074C
    ora $0524
    bne @done
    lda $8D
    ora $8E
    ora EXTRA_LIVE
    ora CAVE_GLOW_ON
    ora CAVE_PAL_PEND
    beq @done
    lda #>(CaveFireLight1 - 1)
    pha
    lda #<(CaveFireLight1 - 1)
    pha
    lda #$01
    jmp $FFCC
@not_dark:
    lda #$00
    sta CAVE_GLOW_ON
    sta CAVE_PAL_PEND
    sta CAVE_LIGHT_DISP
@done:
    rts

CaveEmph6:
    lda CAVE_LIGHT_DISP
    and #$E0
    beq :+
    ora $FE
    sta IRQ_MASK
:
    rts

CaveApplyPalHop6:
    lda CAVE_PAL_PEND
    and #$0F
    cmp #$01
    bne :+
    lda OW_FOL_SKIP
    beq :+
    bpl @skip_pal
:   jsr @hop2
    jmp VblankHudReset6
@skip_pal:
    rts
@hop2:
    lda #>(CaveApplyPal2 - 1)
    pha
    lda #<(CaveApplyPal2 - 1)
    pha
    lda #$02
    jmp $FFCC

.segment "BANK1_SOULS"

CaveFireLight1:
    lda $12
    lsr
    lsr
    and #$03
    tay
    lda CaveHaloDx,y
    sta $00                     ; halo dx (-1 / 0 / +1)
    lda CaveHaloDy,y
    sta $01                     ; halo dy (-1 / 0 / +1)
    lda CaveHaloFlip,y
    sta $05                     ; rotating H/V-flip ($00/$40/$C0/$80)
    lda #$00
    sta $02                     ; live fireball count
    ldx HALO_OAM_START          ; scan below Barba's trail down to $60
    lda $8D
    beq :+
    bmi :+
    ldy #$38
    jsr CaveTryHalo1
:   lda $8E
    beq :+
    bmi :+
    ldy #$40
    jsr CaveTryHalo1
:   lda EXTRA_LIVE
    beq @after_halos
    lda $6400
    beq :+
    bmi :+
    ldy #$3C
    jsr CaveTryHalo1
:   lda $6410
    beq :+
    bmi :+
    ldy #$44
    jsr CaveTryHalo1
:   lda $6420
    beq @after_halos
    bmi @after_halos
    ldy #$48
    jsr CaveTryHalo1
@after_halos:
    ldx $02                     ; live fireball count (0..5)
    lda INFERNO_TIMER
    beq :+
    cpx #$04
    bcs :+
    ldx #$04
:   lda CaveCountToTarget,x
    sta $03                     ; Target (0..9)
    lda CAVE_GLOW_ON
    and #$0F
    sta $04                     ; Cur (0..9)
    lda CAVE_GLOW_ON
    lsr
    lsr
    lsr
    lsr
    tay                         ; Tick (0..3)
    lda $02
    beq @no_fb
    lda $04
    bne @chk_slew
    lda #$01                    ; immediate dim ember ignition on frame 0
    sta $04
    ldy #$00
    beq @store_env
@chk_slew:
    cmp $03
    beq @at_target
    bcc @ramp_up
    iny
    cpy #$03                    ; descend 1 step every 3 frames
    bcc @store_env
    dec $04
    ldy #$00
    beq @store_env
@ramp_up:
    iny
    cpy #$03                    ; swell 1 step every 3 frames
    bcc @store_env
    inc $04
    ldy #$00
    beq @store_env
@at_target:
    ldy #$00
    beq @store_env
@no_fb:
    lda $04
    beq @store_env
    iny
    cpy #$02                    ; smooth ember fadeout: -1 step every 2 frames
    bcc @store_env
    dec $04
    ldy #$00
@store_env:
    tya
    asl
    asl
    asl
    asl
    ora $04
    sta CAVE_GLOW_ON
    ; Top-end gentle shimmer when >=3 fireballs and Cur == 9:
    ; hold each state for >=8 frames, occasionally breathing 9 <-> 8 ($20 tint).
    lda $04
    cpx #$03
    bcc @no_flicker
    cmp #$09
    bcc @no_flicker
    lda $12
    and #$07
    beq @roll_flicker
    lda CAVE_LIGHT_DISP
    and #$0F
    cmp #$08
    bcs @no_flicker
@roll_flicker:
    lda $051A
    and #$03
    bne @flick_max
    lda #$08
    bne @no_flicker
@flick_max:
    lda #$09
@no_flicker:
    tax                         ; X = Disp (0..9)
    lda CAVE_LIGHT_DISP
    and #$0F
    sta $06                     ; prev Disp
    txa
    ora CaveLevelToEmph,x       ; Emph | Disp (Disp in 0..9)
    sta CAVE_LIGHT_DISP
    cpx $06
    bne @queue_disp
    lda CAVE_PAL_PEND
    bpl @done
    lda $074B
    ora $070F
    bne @done
@queue_disp:
    txa
    clc
    adc #$01                    ; pending = Disp + 1 (1..10)
    sta $06
    lda $074B
    ora $070F
    beq @set_pend
    lda $06
    ora #$80
    sta $06
@set_pend:
    lda $06
    sta CAVE_PAL_PEND
@done:
    lda #$06
    jmp $FFCC

CaveTryHalo1:
    inc $02
    lda $6501,y                 ; confirm fireball tile ($85) without touching X
    cmp #$85
    bne @done
    lda $6500,y                 ; fireball Y
    cmp #$F0
    bcs @done
    clc
    adc $01                     ; + dy
    cmp #$10
    bcc @done
    cmp #$F0
    bcs @done
    sta $03                     ; halo Y
    lda $6503,y                 ; fireball X
    cmp #$02
    bcc @done
    cmp #$FE
    bcs @done
    clc
    adc $00                     ; + dx
    sta $04                     ; halo X
@find_oam:
    cpx #$60
    bcc @done
    lda $6500,x
    cmp #$EF
    bcs @place
    txa
    sbc #$03                    ; C=0 from cmp #$EF -> subtracts 4
    tax
    bcs @find_oam
@place:
    jmp CavePlaceHalo1
@done:
    rts

.segment "BANK1_GEAR2"
CavePlaceHalo1:
    lda $03
    sta $6500,x
    lda #$87                    ; rounded dithered glow tile ($86/$87 in CHR 00)
    sta $6501,x
    lda #$22                    ; behind BG ($20) + Sprite Palette 2 ($02)
    eor $05                     ; rotating H/V-flip
    sta $6502,x
    lda $04
    sta $6503,x
    dex
    dex
    dex
    dex
    rts

.segment "BANK2_SMOKE"
; 4 palettes x 18 bytes = 72 bytes:
;   BG1(3), BG2(3), BG3(3), Pal2(3), Pal3(3), Pal0/Barba(3)
; Combined with $2001 emphasis ($E0/$20/$00) for 10 smooth levels (0..9):
;   Disp 0 -> Pal 0 ($00); Disp 1-3 -> Pal 1 ($E0/$20/$00);
;   Disp 4-6 -> Pal 2 ($E0/$20/$00); Disp 7-9 -> Pal 3 ($E0/$20/$00).
CaveLightPalettes:
    ; Pal 0 (Disp 0): Cold unlit cave
    .byte $12,$01,$0F, $0F,$0F,$0F, $0F,$0F,$0F
    .byte $0F,$0F,$0F, $0F,$0F,$0F, $01,$21,$11
    ; Pal 1 (Disp 1-3): First spark -> Dim/Warm Ember (zero blue)
    .byte $06,$07,$0F, $0F,$0F,$0F, $0F,$07,$0F
    .byte $0F,$06,$16, $0F,$07,$06, $07,$16,$06
    ; Pal 2 (Disp 4-6): Low -> Rising -> Warm Firelight
    .byte $16,$07,$06, $0F,$07,$06, $0F,$06,$16
    .byte $06,$16,$17, $0F,$07,$16, $07,$17,$16
    ; Pal 3 (Disp 7-9): Bright -> Strong -> Max Golden-Orange Crescendo
    .byte $27,$17,$07, $0F,$17,$07, $0F,$07,$27
    .byte $07,$17,$27, $0F,$07,$17, $07,$27,$16

CavePendToOff:
    .byte 0, 18, 18, 18, 36, 36, 36, 54, 54, 54

.segment "BANK2_CAVE"
CaveApplyPal2:
    lda CAVE_PAL_PEND
    and #$0F
    beq @clear_exit
    tax
    ldy CavePendToOff-1,x
    bit $2002
    lda #$05
    jsr @ppu_addr
    jsr @grp3_sep               ; $3F05..$3F07 + $0F
    jsr @grp3_sep               ; $3F09..$3F0B + $0F
    jsr @grp3                   ; $3F0D..$3F0F
    lda #$19
    jsr @ppu_addr
    jsr @grp3_sep               ; $3F19..$3F1B + $0F
    jsr @grp3                   ; $3F1D..$3F1F
    lda $074B
    ora $070F
    bne @skip_barba
    lda #$11
    jsr @ppu_addr
    jsr @grp3                   ; $3F11..$3F13
    lda #$00
    beq @reset_addr
@skip_barba:
    lda #$80
@reset_addr:
    ldx #$3F
    stx $2006
    ldx #$00
    stx $2006
    stx $2006
    stx $2006
    .byte $2C
@clear_exit:
    lda #$00
    sta CAVE_PAL_PEND
    lda #$06
    jmp $FFCC
@ppu_addr:
    ldx #$3F
    stx $2006
    sta $2006
    rts
@grp3_sep:
    jsr @grp3
    lda #$0F
    sta $2007
    rts
@grp3:
    ldx #$03
:   lda CaveLightPalettes,y
    sta $2007
    iny
    dex
    bne :-
    rts

.segment "BANK1_GEAR"
CaveHaloDx:
    .byte $FF, $01, $00, $00
CaveHaloDy:
    .byte $00, $00, $FF, $01

.segment "BANK1_GEAR2"
CaveHaloFlip:
    .byte $00, $40, $C0, $80
CaveCountToTarget:
    .byte $00, $04, $06, $08, $09, $09
CaveLevelToEmph:
    .byte $00, $E0, $20, $00, $E0, $20, $00, $E0, $20, $00

.segment "BANK0"
