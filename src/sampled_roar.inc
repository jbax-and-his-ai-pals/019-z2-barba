; Default sampled audio. All sample/code writes are guarded in build.py.
.include "sample-roar-params.inc"
.export RoarAudio, BarbaHurtRoar
.export RoarPulse1, RoarPulse2
.export RoarNativeRate
.export RoarGemTorso
.export RoarItemFanfareStart, RoarItemFanfareEnd
.export ItemHoldPickup, ItemHoldPose, ItemHoldSpell
FALL_ROAR_ACTIVE = $81 ; active voice + bit 0 (reused outside Game Over)

.segment "FALL_ROAR"
; The native shaft setup at $C705 requests $EE bit 0 on entry to mode $0F.
; Keep ownership of DMC through the destination room load and until the full
; clip ends, even if normal gameplay has already resumed.
FallRoarAudio:
    lda ROAR_REQUEST
    cmp #FALL_ROAR_ACTIVE
    beq @active
    lda $0736
    cmp #$0B
    beq @game
    cmp #$0F
    bne @other
    lda $EE
    lsr
    bcc @other
    jmp RoarFallStart
@active:
    jmp RoarActive
@game:
    jmp RoarGameAudio
@other:
    jmp RoarLaughDelay

.segment "SAMPLED_ROAR"
RoarAudio:
.ifdef WALDO_PORTAL
    jsr RoarRestoreBank
.endif
    jmp FallRoarAudio
RoarFallStart:
    jsr $90B5          ; native fall cue's music and channel reset
    lda #FALL_ROAR_ACTIVE
    sta ROAR_REQUEST
    ldx #ROAR_LENGTH
    bne RoarStart
RoarGameAudio:
    lda ROAR_COOLDOWN
    beq :+
    dec ROAR_COOLDOWN
:
    lda ROAR_REQUEST
    and #$02
    beq :+
    ; The item ceremony owns DMC through its buffered tail.
    lda ROAR_REQUEST
    and #$04
    beq @itemPhase
    eor ROAR_REQUEST   ; recoil cannot replace an item roar already in progress
    sta ROAR_REQUEST
@itemPhase:
    bit ROAR_REQUEST
    bpl @full
    jmp RoarActive
:
    lda ROAR_REQUEST
    and #$04
    bne @hurt
    ; Lava Link's request is still native Link hurt (E9 bit 0). It has priority.
    lda $E9
    and #$01
    beq :+
    lda ROAR_REQUEST
    jmp RoarKeepPending
:
    lda ROAR_REQUEST
    bpl :+
    jmp RoarActive
:
    and #$40
    bne @fullWait
    ; Attacks never start a voice; only injury, spells and victories do.
    lda ROAR_REQUEST
    jmp RoarKeepPending ; bit 6 is clear, preserve only victory completion
@fullWait:
    ; Victory requests arrive as their fanfare ends.
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
    and #$0A           ; keep the raised-head pose and item marker
    ora #$80
    sta ROAR_REQUEST
    ldx #ROAR_LENGTH
    bne RoarStart
@hurt:
    lda ROAR_REQUEST
    and #$40
    ora #$A0           ; bit 5: injury-only downward pitch tail
    sta ROAR_REQUEST
    ldx #HURT_LENGTH
RoarStart:
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
.ifdef WALDO_PORTAL
    jsr RoarSetRate6
.else
    lda #ROAR_RATE
    sta $4010
.endif
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
RoarActive:
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
    bne RoarActiveDone
    lda ROAR_REQUEST
    cmp #$88
    beq @drain
    cmp #$8A
    bne @retire
@drain:
    ; DMC reports no bytes remaining before its buffered output finishes.
    ; Hold the pose and lock for one more audio tick.
    ora #$10
    sta ROAR_REQUEST
    rts
@retire:
    cmp #$9A
    bne :+
    lda #$00
    sta ITEM_HOLD
:
RoarKeepPending:
    and #$50           ; keep a queued full voice or completed victory
    sta ROAR_REQUEST
    jmp $920B
RoarActiveDone:
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
    jsr $8E00
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
    jsr $8E00
    jmp @store
@normal:
    txa
@store:
    sta $4004
    pla
    plp
    rts

.ifdef WALDO_PORTAL
LAUGH_BANK_STATE = $64F9 ; 0 = normal bank, 2 = ready to start, 1 = fetching
.endif

RoarNativeRate:
    lda $07FA
    cmp #$02
.ifdef WALDO_PORTAL
    bne @rate
    ; Select the sample bank before the native driver enables DMC DMA.
    jsr RoarSetBank
@rate:
    lda #$0F
    sta $4010
    rts

; Mapper 176 mode 2 uses PRG pages 14/15 at $C000-$FFFF. Mode 1 uses pages
; 30/31. Both map the same executable code and the same $8000/$A000 banks.
RoarSetBank:
    pha
    lda #$80
    sta $A001          ; unlock outer registers while keeping WRAM enabled
    pla
    sta $5FF0
    and #$02
    sta LAUGH_BANK_STATE
    lda #$A0
    sta $A001
    rts

.segment "LAUGH_BANK"
.export RoarNativeEnable
RoarNativeEnable:
    lda $07FA
    cmp #$02
    bne @enable
    ; Native audio polls $4015 for several frames. Once DMA has completed,
    ; another enable would replay the sample address from the normal roar bank.
    lda LAUGH_BANK_STATE
    cmp #$02
    bne @done
    dec LAUGH_BANK_STATE
@enable:
    lda #$1F
    sta $4015
@done:
    rts

.segment "BANK6"
.export RoarRestoreBank
RoarRestoreBank:
    lda LAUGH_BANK_STATE
    beq @done
    lda $4015
    and #$10
    bne @done          ; leave the bank mapped until the last byte is fetched
    lda #$01
    jmp RoarSetBank
@done:
    rts
.else
    ; Standalone MMC3 shares the opening waveform to fit its fixed bank.
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
.endif

.segment "ITEM_ROAR"
; Called from the player's bank-0 renderer. The standing item pose already
; has two full torso chunks. For the raised-head pose, lift the head and
; neck 8px. Bridge the neck to the foot-level bend with an overlapping
; upright torso row.
; A frozen/menu frame may reuse OAM, so shift only freshly drawn coordinates.
RoarGemTorso:
    lda ITEM_HOLD
    beq @victory
    jsr DrawHeldItem
@victory:
    lda ROAR_REQUEST
    and #$88
    cmp #$88
    bne @skip
    lda DRAW_FRAME
    cmp #$48
    beq @geometry
@skip:
    jmp $FFC5
@geometry:
    lda GEOMETRY
    and #$06
    bne @done
    lda DRAW_LEFT
    cmp #$E8
    bcs @done
    lda DRAW_TOP
    cmp #$30
    bcc @done
    cmp #$D0           ; the bend at DRAW_TOP + 32 must stay below $F0
    bcs @done
    cmp $0204
    bne @done
    clc
    adc #$10
    sta $0220
    sta $0224
    ldy #$05
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
    lda #(TRAIL_BEND_CENTER ^ $01)
    sta $0219
    lda #(TRAIL_BEND_BACK ^ $01)
    bit DRAW_ATTR
    bvs @right
    sta $021D
    ldx #$06
    ldy #$08
    lda DRAW_LEFT
    clc
    adc #$08
    bcc @place
@right:
    sta $0215
    ldx #$08
    ldy #$06
    lda DRAW_LEFT
@place:
    sta $0223
    stx $0221
    clc
    adc #$08
    sta $0227
    sty $0225
    lda ITEM_HOLD
    beq @done
    lda $0204
    jsr PlaceHeldItem
@done:
    jmp $FFC5          ; restore bank 0 before returning to the player renderer
@rows:
    .byte $04,$4C,$C4,$08,$0C,$10

; Keep the native item tiles, horizontal placement and palette. Move them from
; the native hold slots to the spare side-view records, above the taller head.
DrawHeldItem:
    jsr $ED21
    ldx #$03
@copy:
    lda $0220,x
    sta $0234,x
    lda $0224,x
    sta $0240,x
    dex
    bne @copy
    lda #$F8
    sta $0220
    sta $0224
    lda DRAW_TOP
PlaceHeldItem:
    sec
    sbc #$10
    bcc @hud
    cmp #$20
    bcs @place
@hud:
    lda #$20
@place:
    sta $0234
    sta $0240
    rts

; A track change can interrupt the fanfare. Once the roar starts, the native
; return to the background track must leave the hold in place.
RoarItemFanfareStart:
    sta $07FB          ; displaced track selection
    cmp #$10
    beq @done
    pha                ; the sequencer still needs the selected track in A
    lda ITEM_HOLD
    bmi @keep          ; background music resumes during the roar
    lda #$00
    sta ITEM_HOLD
@keep:
    pla
@done:
    rts

; The music sequencer reaches this hook when a track runs out of parts.
RoarItemFanfareEnd:
    lda ITEM_HOLD
    cmp #$01
    bne @resume
    lda $07FB
    cmp #$10
    bne @resume
    lda #$00
    sta ITEM_HOLD
    lda ROAR_REQUEST
    and #$18           ; leave a palace or ending ceremony's state alone
    bne @resume
    lda #$80
    sta ITEM_HOLD
    lda #$4A           ; full voice + raised head + no ceremony completion latch
    sta ROAR_REQUEST
@resume:
    lda $0707          ; displaced world load for native music restart
    rts

.segment "LAUGH_DELAY"
RoarLaughDelay:
    ; Hold the initial laugh request for 36 frames (~0.60 s). The native
    ; GAME OVER screen timer starts at F0; subsequent 23-frame gaps stay native.
    ; E9 is cleared by the native driver every frame, so latch its request in
    ; spare ROAR_REQUEST bit 0. Other sound channels keep running normally.
    lda #$00
    sta ITEM_HOLD
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

; Arm the hold during the actual pickup so even input on the next frame is
; locked. Ordinary keys, bags, jars and dolls retain their native behavior.
.segment "ITEM_ROAR"
ItemHoldPickupBody:
    lda $AF,x
    and #$7F
    sta $049D          ; displaced item presented above the player
    cmp #$08           ; permanent equipment (including the Magic Key)
    bcc @hold
    cmp #$0E
    bcc @done
    cmp #$10           ; Magic or Heart Container
    bcc @hold
    cmp #$13           ; Child, Trophy or Medicine
    bcc @done
    cmp #$16
    bcs @done
@hold:
    lda #$01
    sta ITEM_HOLD
    lda $29            ; align like the native item hold
    clc
    adc #$08
    and #$F0
    sta $29
    lda #$00
    sta $049C
    sta $0497
    lda #$01
    sta $17
    lda #$02
    sta $9F
    lda #$03           ; normal tall standing pose until the roar begins
    sta $80
@done:
    jmp $FFC5          ; restore bank 0 for the FarCall0 return

.segment "ITEM_HOLD"
ItemHoldPickup:
    lda #>(ItemHoldPickupBody-1)
    pha
    lda #<(ItemHoldPickupBody-1)
    pha
    lda #$06
    jmp $FFCC

ItemHoldPose:
    lda ITEM_HOLD
    bne @hold
    lda $049C          ; displaced native hold timer check
    jmp $9344
@hold:
    ldy #$03
    jmp $9364          ; native pose and facing store, then return

ItemHoldSpell:
    lda ITEM_HOLD
    bne ItemHoldReturn
    lda $074C          ; displaced spell casting check
    jmp $8DC6
ItemHoldReturn:
    rts
