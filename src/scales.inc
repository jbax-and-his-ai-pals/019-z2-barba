; SCALES (vanilla Shield spell) feedback (producer, 2026-11-16).
; Vanilla Shield writes $16 (red) into sprite palette 0 colour 3 ($69DE) and
; uses the same byte as its active flag ($070F). Barba's colour 3 is the white
; belly, so build.py patches the cast colour to white ($30, unchanged) at $8E8E, and
; ScalesTick turns the outline navy and the orange body sky blue.
; (Producer picks, 2026-11-16: navy/sky/white over gold, blue-on-orange, red outline, all-blue.)
;
; Bank 0 has no room, so the cast/hit effects run once per frame from bank 3's
; pad: BarbaShouts6 (bank 6, runs from BarbaUpdate every frame) calls
; ScalesHop, which maps bank 3 and RTSes into ScalesTick; ScalesTick maps bank 6
; back and RTSes to BarbaShouts6. Both bank swaps go through fixed $FFCC.
;   - cast (first frame $070F is nonzero): dragon roar + 32-frame decor flash.
;   - blocked hit ($050C injured timer rises while shielded): native shield
;     clang ($EC bit 1) + 8-frame sprite palette flash (only if no flash is live).
SCALES_SEEN = $05EC ; nonzero once this Shield cast's fanfare has played
SCALES_HURT = $05ED ; last frame's $050C (injured timer) while shielded
SCALES_ROAR = $28   ; ROAR_TIMER frames (RoarVolume/RoarPitch index = timer/4)
; Shielded Barba: navy outline and sky-blue body (from the dark-cave palette)
; with the normal white belly.
SCALES_LINE_ON = $01
SCALES_LINE_OFF = $16 ; Barba's normal red (build.py flash-restore table $A9FA)
SCALES_BODY_ON = $21
SCALES_BODY_OFF = $27 ; Barba's normal orange (build.py flash-restore table $AA00)

.segment "BANK6"
ScalesHop:
    lda #>(ScalesTick-1)
    pha
    lda #<(ScalesTick-1)
    pha
    lda #$03
    jmp $FFCC

.segment "BANK3_SIGN"
ScalesTick:
    lda $070F
    bne @on
    lda SCALES_SEEN
    beq @off
    ; Shield just ended (side-view init cleared $070F): red outline and orange body back, and
    ; a 1-frame sprite flash re-uploads the palette (the native path only
    ; uploads while $074B is counting).
    lda #SCALES_LINE_OFF
    sta $69D2
    lda #SCALES_BODY_OFF
    sta $69D8
    lda $074B
    bne :+
    inc $074B
:
    lda #$00
@off:
    sta SCALES_SEEN
    sta SCALES_HURT
    beq @back
@on:
    lda SCALES_SEEN
    bne @hit
    inc SCALES_SEEN
    lda #SCALES_LINE_ON     ; outline colour 1 ($69D2 = palette y=4 slot)
    sta $69D2
    lda #SCALES_BODY_ON     ; body colour 2 ($69D8)
    sta $69D8
    lda #SCALES_ROAR
    sta ROAR_TIMER
.ifdef SAMPLED_ROAR
    lda ROAR_REQUEST
    ora #$40
    sta ROAR_REQUEST
.endif
    lda #$A0            ; decor flash (bit 7) for 32 frames, like the high spells
    sta $074B
@hit:
    lda SCALES_HURT
    cmp $050C           ; C clear when the injured timer rose this frame
    lda $050C
    sta SCALES_HURT
    bcs @back
    lda $EC
    ora #$02            ; native "blow hits shield" clang
    sta $EC
    lda $074B
    bne @back
    lda #$08            ; short Barba palette flash
    sta $074B
@back:
    lda #$06
    jmp $FFCC
