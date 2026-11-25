; Bank 4. Crystal and Lava Link each use a timer in their own enemy record.
.export RoarGemEnd, LavaLinkGate, LavaLinkIntro
.segment "PALACE_ROAR"

LAIR_PAUSE_BASE = $40 ; $AF,x below this holds the roar's shake phase
LAIR_PAUSE_FRAMES = 30
LAIR_LANDING_READY = $60 ; $AF,x after the landing countdown, waiting to start the roar
LAIR_LANDING_FRAMES = 6
LAIR_CENTER_X = $88   ; world $0188: Barba's 16 px body-center offset gives screen x $98
LAIR_CENTERED = $7F   ; $AF,x while holding X and waiting to land

; Called during the native crystal lock, after the placement fanfare.
RoarGemEnd:
    lda $04A0,x
    beq @fanfare
.ifdef SAMPLED_ROAR
    lda ROAR_REQUEST
    and #$18
    cmp #$10
    beq @finish
    and #$08
    beq @fanfare           ; a competing hurt sound interrupted the roar
    lda ROAR_REQUEST
    bpl @wait              ; wait for DMC playback; bit 7 stays set through the drain
.else
    lda ROAR_TIMER
    beq @finish
.endif
    tya
    pha
    ldy $04A0,x
    iny
    cpy #LairShakeEnd-LairShakeOffsets
    bcc :+
    ldy #LairShakeSustain-LairShakeOffsets
:
    tya
    sta $04A0,x
    lda LairShakeOffsets,y
    sta LAIR_SHAKE_X
    pla
    tay
@wait:
    rts
@finish:
    lda #0
    sta LAIR_SHAKE_X
.ifdef SAMPLED_ROAR
    sta ROAR_REQUEST
.endif
    ldy #0
    jmp $9B4C              ; native refill and XP sequence
@fanfare:
    lda $07FB
    bne @wait
    lda #0
    sta LAIR_SHAKE_X
    jsr PalaceStartRoar
    bcc @wait
    lda #1
    sta $04A0,x
    rts

; Lava Link's palette/hurt wrapper tails here in place of the shared
; native boss gate. Lock the camera when the boss page scrolls in.
LavaLinkGate:
    lda $0728
    bne @native
    lda $072A
    beq @native
    inc $0728
    lda #$FF
    sta $050D
    jmp $B23C            ; native early return from the boss update
@native:
    jmp $B20D

; Let Barba reach the middle platform, then hold X while the jump finishes.
; The native delay gate keeps Link submerged through the landing beat, roar and recovery.
LavaLinkIntro:
    lda $AF,x
    bpl :+
    jmp $B1DE
:
    cmp #LAIR_CENTERED
    beq @center
    cmp #0
    bne @playing
    lda $3B
    cmp #1
    bcc @hold
    bne @reached
    lda $4D
    cmp #LAIR_CENTER_X
    bcc @hold
@reached:
    lda #LAIR_CENTERED
    sta $AF,x
@center:
    lda #LAIR_CENTER_X
    sta $4D
    lda #1
    sta $3B
    lda #0
    sta $70
    lda $13              ; WYRMLNG flies and does not advance the jump state
    bne @freeze
    lda $0479            ; native jumping state (zero on a supporting surface)
    bne @hold
@freeze:
    lda #LAIR_LANDING_READY+LAIR_LANDING_FRAMES-1
    sta $AF,x
    lda #0
    sta LAIR_SHAKE_X
    lda #LAIR_CONTROL_LOCK
    sta $0728
    lda #$80
    sta $EB              ; stop the palace theme before the roar
    bne @hold
@start:
    lda #0
    sta LAIR_SHAKE_X
    jsr PalaceStartRoar
    bcc @hold
    lda #1
    sta $AF,x
    bne @hold
@playing:
    cmp #LAIR_PAUSE_BASE
    bcs @pause
.ifdef SAMPLED_ROAR
    lda ROAR_REQUEST
    and #$18
    cmp #$10
    beq @roarDone
    and #$08
    beq @start          ; a competing hurt sound interrupted the roar
    lda ROAR_REQUEST
    bpl @hold           ; wait for DMC playback; bit 7 stays set through the drain
.else
    lda ROAR_TIMER
    beq @roarDone
.endif
    lda $056B
    cmp #6
    bne @hold
    lda $0561
    cmp #$3A
    bne @hold
    tya
    pha
    ldy $AF,x
    iny
    cpy #LairShakeEnd-LairShakeOffsets
    bcc :+
    ldy #LairShakeSustain-LairShakeOffsets
:
    tya
    sta $AF,x
    lda LairShakeOffsets,y
    sta LAIR_SHAKE_X
    pla
    tay
@hold:
    lda #1
    sta $050D
@native:
    jmp $B1DE
@roarDone:
    lda #0
    sta LAIR_SHAKE_X
.ifdef SAMPLED_ROAR
    sta ROAR_REQUEST
.endif
    lda #LAIR_PAUSE_BASE+LAIR_PAUSE_FRAMES
    sta $AF,x
    bne @hold
@pause:
    cmp #LAIR_LANDING_READY
    beq @start
    dec $AF,x
    lda $AF,x
    cmp #LAIR_PAUSE_BASE
    bne @hold
    lda #$FF
    sta $AF,x
    lda #0
    sta $0504,x
    sta $050D
    dec $0728            ; resume player physics and retain the boss scroll lock
    lda #$08
    sta $EB              ; boss theme, before the native rise below
    jmp $B1DE

LairShakeOffsets:
    .byte 0,0,4,4,$FC,$FC,3,3,$FD,$FD,2,2,$FE,$FE
LairShakeSustain:
    .byte 1,1,$FF,$FF
LairShakeEnd:

PalaceStartRoar:
.ifdef SAMPLED_ROAR
    lda ROAR_REQUEST
    and #$C8
    bne @busy
    lda #$48
    sta ROAR_REQUEST
.else
    lda #$30
    sta ROAR_TIMER
.endif
    sec
    rts
.ifdef SAMPLED_ROAR
@busy:
    clc
    rts
.endif

.segment "BANK6"
; Allowed on the title screen, during the Palace 6 Lava Link entrance
; ($0728 = LAIR_CONTROL_LOCK), and during the crystal ceremony ($DE != 0).
LavaShakeOffset6:
    bit $0100
    bvc @read
    lda $0728
    cmp #LAIR_CONTROL_LOCK
    beq @read
    lda $DE
    bne @read
    lda #0
    rts
@read:
    lda LAIR_SHAKE_X
    rts

.segment "PALACE_SHAKE"
; Shift the room IRQ bands by LAIR_SHAKE_X, keeping the HUD steady at X=0.
ShakeLavaCamera6:
    ldx #0
    jsr LavaShakeOffset6
    beq @done
    bpl :+
    dex
:
    clc
    adc IRQ_X
    sta IRQ_X
    txa
    adc #0
    and #1
    tax
    eor IRQ_CTRL
    sta IRQ_CTRL
    lda $FF
    and #$FC
    bit LAIR_SHAKE_X
    bpl :+
    ora #$01
:
    sta $FF
    jmp ShakeLavaHud6
@done:
    rts

.segment "LAIR_HUD_SHAKE"
ShakeLavaHud6:
    sta $2000
    bit $2002
    lda LAIR_SHAKE_X
    sta $2005
    lda $FC
    sta $2005
    rts

.segment "PALACE_SHAKE"
; Move visible sprites opposite the scroll so their positions relative to
; the room stay fixed. Hide edge sprites whose X would otherwise wrap.
ShakeLavaOam6:
    jsr LavaShakeOffset6
    beq @done
    ldx #0
@sprite:
    lda $6500,x
    cmp #$F0
    bcs @next
    lda $6503,x
    sec
    sbc LAIR_SHAKE_X
    sta $6503,x
    bit LAIR_SHAKE_X
    bmi @right
    bcs @next
    bcc @hide
@right:
    bcc @next
@hide:
    lda #$F8
    sta $6500,x
@next:
    inx
    inx
    inx
    inx
    bne @sprite
@done:
    rts
