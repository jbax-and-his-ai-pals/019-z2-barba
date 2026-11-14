; Barba's health-independent breath/projectile integration.
; Included in BANK0 by src/barba.asm.
;
; The mouth is derived from the same player state the spawn code reads in this
; frame (world X $4D/$3B, Y $29, facing $9F, shield/duck $17), so there is no
; one-frame lag from waiting for the renderer. Retune the four table entries
; when the playable sprite changes; tests read the mirrored screen position.
.export BarbaProjectiles, BarbaFireSpell, BarbaMuzzleScreen

BREATH_MUZZLE_X = $05F2 ; diagnostic mirror: screen X, left edge of 8x16 shot
BREATH_MUZZLE_Y = $05F3 ; diagnostic mirror: screen Y, top of 8x16 shot

; Offsets from the player's position to the top-left of an 8x16 fire sprite
; leaving the mouth. They match the attached breath sprite on the 16x32 alpha:
; right-facing flame starts at +$20, left-facing flame ends at the body edge.
; Index: facing $9F (1 right, 2 left). Signed, two's complement.
MuzzleOffsetX:
    .byte $00, $20, $F8
; Index: $17 (0 ducked, 1 standing).
MuzzleOffsetY:
    .byte $10, $00

; Native $9847 also spawns the full-health sword beam. Enter at the update-only
; tail instead: existing spell flames retain native motion, lifetime, enemy
; filtering, disintegration, graphics scheduling and the two-slot ceiling.
BarbaProjectiles:
    jmp $9878

; Replaces only the Fire spell's dispatch pointer at CPU $8E50. The original
; routine decides attack timing, available slots and attack-level slot count,
; and marks a newly allocated slot with exactly 1 (INC from 0).
BarbaFireSpell:
    lda $8D
    pha
    lda $8E
    pha
    jsr $97F1
    pla
    bne @slot_zero
    lda $8E
    cmp #$01
    bne @slot_zero
    ldx #$01
    jsr BarbaPlaceNewFlame
@slot_zero:
    pla
    bne @done
    lda $8D
    cmp #$01
    bne @done
    ldx #$00
    jsr BarbaPlaceNewFlame
@done:
    rts

; X = projectile slot. Preserves X.
BarbaPlaceNewFlame:
    ldy $17
    lda $29
    clc
    adc MuzzleOffsetY,y
    sta $36,x
    ldy $9F
    lda MuzzleOffsetX,y
    bmi @behind
    clc
    adc $4D
    sta $5A,x
    lda $3B
    adc #$00
    sta $48,x
    jmp @class
@behind:
    clc
    adc $4D
    sta $5A,x
    lda $3B
    adc #$FF
    sta $48,x
@class:
    ; Always a Fire-spell flame, never a full-health beam. Zero timeout keeps
    ; the native $84 fireball graphics and Fire-only enemy vulnerability.
    lda #$00
    sta $05CA,x
    rts

; Mirror the current mouth in screen space ($CC = player screen X) for tests
; and for future renderer use. Called during the per-frame projectile update.
BarbaMuzzleScreen:
    ldy $17
    lda $29
    clc
    adc MuzzleOffsetY,y
    sta BREATH_MUZZLE_Y
    ldy $9F
    lda $CC
    clc
    adc MuzzleOffsetX,y
    sta BREATH_MUZZLE_X
    rts
