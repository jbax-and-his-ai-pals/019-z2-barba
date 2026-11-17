; Default sampled audio. All sample/code writes are guarded in build.py.
.include "sample-roar-params.inc"
.export RoarAudio, RoarGemEnd, BarbaHurtRoar
.export RoarPulse1, RoarPulse2
.export RoarNativeRate
.export RoarGemTorso
.segment "SAMPLED_ROAR"
RoarAudio:
    lda $0736
    cmp #$0B
    beq @game
    jmp RoarLaughDelay
@game:
    lda ROAR_COOLDOWN
    beq :+
    dec ROAR_COOLDOWN
:
    lda ROAR_REQUEST
    and #$04
    bne @hurt
    ; Lava Link's request is still native Link hurt (E9 bit 0). It has priority.
    lda $E9
    and #$01
    beq :+
    jmp @nativeHurt
:
    lda ROAR_REQUEST
    bpl :+
    jmp @active
:
    and #$40
    bne @gemWait
    ; Attacks never start a voice; only injury, spells and gem completion do.
    lda #$00
    sta ROAR_REQUEST
    jmp @native
@gemWait:
    ; Gem requests arrive exactly when the fanfare ends, before refill/XP.
    ; Spell requests retain their menu/tally deferral.
    lda ROAR_REQUEST
    and #$08
    bne @full
    lda $0755
    ora $0756
    ora $074C
    ora $0524
    ora $13
    beq :+
    rts
:
@full:
    lda ROAR_REQUEST
    and #$08
    ora #$80           ; bit 3 holds the gem's looking-up pose during playback
    sta ROAR_REQUEST
    ldx #ROAR_LENGTH
    bne @start
@hurt:
    lda ROAR_REQUEST
    and #$40
    ora #$A0           ; bit 5: injury-only downward pitch tail
    sta ROAR_REQUEST
    ldx #HURT_LENGTH
@start:
    ; The early fixed-bank input path will use these stable raw buttons during
    ; playback. Refresh them after the HUD split, avoiding a long early hook.
    lda $F7
    sta $64D2
    lda $F8
    sta $64D3
    lda #$00
    sta $07FA           ; retire any previous native DMC state
    lda #$FF
    sta ROAR_COOLDOWN
    lda #ROAR_RATE
    sta $4010
    lda #$D0
    sta $4012
    stx $4013
    lda #$40
    sta $4011
    lda #$0F
    sta $4015
    lda #$1F
    sta $4015
    rts
@active:
    jsr RoarReadPads
    lda ROAR_REQUEST
    and #$20
    beq @status
    ; Keep the attack of the grunt, then descend over its final portion.
    ; The existing start timer counts down from FF once per audio tick.
    ldx #ROAR_RATE
    lda ROAR_COOLDOWN
    cmp #$EF
    bcs @pitch
    dex
    cmp #$EB
    bcs @pitch
    dex
    cmp #$E7
    bcs @pitch
    dex
    cmp #$E3
    bcs @pitch
    dex
@pitch:
    stx $4010
@status:
    lda $4015
    and #$10
    bne @done
    lda ROAR_REQUEST
    and #$40
    sta ROAR_REQUEST
@native:
    jmp $920B
@nativeHurt:
    lda ROAR_REQUEST
    and #$40
    sta ROAR_REQUEST
    jmp $920B
@done:
    rts

; Re-read both controllers until two consecutive captures agree. DMC DMA can
; delete a serial controller bit on NTSC hardware. Reads are local and bounded
; in practice by the sample DMA spacing; stack owns the comparison bytes.
RoarReadPads:
    lda $F5
    pha
    lda $F6
    pha
    jsr @capture
@again:
    lda $F5
    pha
    lda $F6
    pha
    jsr @capture
    pla
    cmp $F6
    bne @retry
    pla
    cmp $F5
    bne @again
    lda $F5
    sta $64D2
    lda $F6
    sta $64D3
    pla
    sta $F6
    pla
    sta $F5
    rts
@retry:
    pla
    jmp @again
@capture:
    ldx #$01
    stx $4016
    dex
    stx $4016
    ldx #$08
@bit:
    lda $4016
    lsr
    rol $F5
    lda $4017
    lsr
    rol $F6
    dex
    bne @bit
    rts
; Gameplay music uses the same X=control/volume ABI as title music. Attenuate
; melodies while DMC owns the roar, preserving registers, flags and envelopes.
RoarPulse1:
    php
    pha
    lda ROAR_REQUEST
    bpl @normal
    lda $8E00,x
    jmp @store
@normal:
    txa
@store:
    sta $4000
    pla
    plp
    rts
RoarPulse2:
    php
    pha
    lda ROAR_REQUEST
    bpl @normal
    lda $8E00,x
    jmp @store
@normal:
    txa
@store:
    sta $4004
    pla
    plp
    rts

; Four distinct native waveforms retain the descending contour. The opening
; pair shares a prefix with different lengths; other native effects keep rate 15.
RoarNativeRate:
    lda $07FA
    cmp #$02
    beq @laugh
    lda #$0F
    bne @write
@laugh:
    lda @rates,y
@write:
    sta $4010
    rts
@rates:
    .byte 15,15,15,15,6,15,15,15,6,15,6,15,10,15,10,15

; Called from the player's bank-0 renderer. Extend the gem's raised-head pose to
; 56px: lift its three rows 8px and finish the existing half-segment with a
; normal torso chunk at the original feet, overlapping the matching top 8px.
; A frozen/menu frame may reuse OAM, so shift only freshly drawn coordinates.
RoarGemTorso:
    lda ROAR_REQUEST
    and #$88
    cmp #$88
    bne @done
    lda DRAW_FRAME
    cmp #$48
    bne @done
    lda GEOMETRY
    and #$06
    bne @done
    lda DRAW_LEFT
    cmp #$E8
    bcs @done
    lda DRAW_TOP
    cmp #$30
    bcc @done
    cmp $0204
    bne @done
    clc
    adc #$20
    cmp #$F0
    bcs @done
    sta $0220
    sta $0224
    ldy #$08
@lift:
    ldx @rows,y
    lda $0200,x
    sec
    sbc #$08
    sta $0200,x
    dey
    bpl @lift
    lda DRAW_ATTR
    sta $0222
    sta $0226
    ldx #$08
    ldy #$06
    lda DRAW_LEFT
    bit DRAW_ATTR
    bvs @place
    ldx #$06
    ldy #$08
    clc
    adc #$08
@place:
    sta $0223
    stx $0221
    clc
    adc #$08
    sta $0227
    sty $0225
@done:
    jmp $FFC5          ; restore bank 0 before returning to the player renderer
@rows:
    .byte $04,$4C,$C4,$08,$0C,$10,$14,$18,$1C

.segment "SAMPLE_GEM"
RoarGemEnd:
    sty $070C          ; original fanfare-end magic refill (Y = FF)
    lda ROAR_REQUEST
    ora #$48           ; once at fanfare end: full voice + gem pose
    sta ROAR_REQUEST
    rts

.segment "LAUGH_DELAY"
RoarLaughDelay:
    ; Hold the initial laugh request for 36 frames (~0.60 s). The native
    ; GAME OVER screen timer starts at F0; subsequent 23-frame gaps stay native.
    ; E9 is cleared by the native driver every frame, so latch its request in
    ; spare ROAR_REQUEST bit 0. Other sound channels keep running normally.
    lda $0736
    cmp #$04
    beq @gameOver
    lda #$00
    sta ROAR_REQUEST
    sta ROAR_COOLDOWN
    jmp $920B
@gameOver:
    lda $E9
    and #$02
    beq @waiting
    lda #$01
    sta ROAR_REQUEST
    lda $E9
    and #$FD
    sta $E9
@waiting:
    lda ROAR_REQUEST
    and #$01
    beq @native
    lda $0501
    cmp #$CD           ; F0 - 36 + 1: first allowed value is CC
    bcs @native
    lda #$00
    sta ROAR_REQUEST
    lda $E9
    ora #$02
    sta $E9
@native:
    jmp $920B
