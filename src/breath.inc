; Barba's health-independent breath/projectile integration (BANK0).
; BarbaGeometry supplies the attached plume's top-left in screen space and
; bit 0 of its validity flags. Both shots sample that geometry at spawn time.
.export BarbaProjectiles, BarbaFireSpell, BarbaMuzzleScreen

BREATH_MUZZLE_X = $05F2
BREATH_MUZZLE_Y = $05F3
BREATH_GEOMETRY_FLAGS = $05F6
BREATH_BURST_DELAY = $05F7
BREATH_BURST_STATE = $05F8 ; 0 ready, 1 pending, 2 attempted until attack ends

; Native $9847 also creates the full-health sword beam. Its update-only tail
; retains Fire movement, vulnerability class, disintegration and sound.
BarbaProjectiles:
    jsr BarbaBurstAllowed
    bcc @cancel
    lda $0400
    beq @cancel
    lda BREATH_BURST_STATE
    cmp #$01
    bne @update
    dec BREATH_BURST_DELAY
    bne @update
    ; Exactly one attempt: a full pool consumes the follow-up, never retries.
    lda #$02
    sta BREATH_BURST_STATE
    ldx #$01
@find_slot:
    lda $8D,x
    beq @followup
    dex
    bpl @find_slot
    bmi @update
@followup:
    ; $981B uses ADC without CLC; no comparison carry may leak into spawn X.
    clc
    jsr $981B
    jsr BarbaPlaceNewFlame
    jmp @update
@cancel:
    lda #$00
    sta BREATH_BURST_DELAY
    sta BREATH_BURST_STATE
@update:
    ; Native code ignores slot 1 at Attack 1-3. Update it once here so the
    ; two-shot burst works at every attack level, still with only two slots.
    lda $0777
    cmp #$04
    bcs @native_update
    ldx #$01
    jsr $9888
@native_update:
    jmp $9878

; Fire's first shot retains the original attack-animation/delay gate and
; allocator. A successful initial shot arms a single eight-frame follow-up.
BarbaFireSpell:
    jsr BarbaBurstAllowed
    bcc @done
    lda BREATH_BURST_STATE
    bne @done
    jsr BarbaGeometry
    lda BREATH_GEOMETRY_FLAGS
    and #$01
    beq @done
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
    bcc @slot_zero
    jsr BarbaArmBurst
@slot_zero:
    pla
    bne @done
    lda $8D
    cmp #$01
    bne @done
    ldx #$00
    jsr BarbaPlaceNewFlame
    bcc @done
    jsr BarbaArmBurst
@done:
    rts

BarbaArmBurst:
    lda #$08
    sta BREATH_BURST_DELAY
    lda #$01
    sta BREATH_BURST_STATE
    rts

; Carry set only while a queued Fire attack is safe to continue. Scene fade,
; dialog/level-up, spell menu, death and wyrmling form all cancel the queue.
BarbaBurstAllowed:
    lda $0736
    cmp #$0B
    bne @no
    lda $B5
    cmp #$01
    bne @no
    lda $074C
    ora $0524
    ora $0726
    ora $13
    ora $DE
    bne @no
    lda $076F
    and #$10
    beq @no
    sec
    rts
@no:
    clc
    rts

; X = newly allocated projectile slot. Preserve X across shared geometry;
; invalidate a clipped spawn rather than letting its world coordinate wrap.
; Carry reports whether a projectile was placed.
BarbaPlaceNewFlame:
    txa
    pha
    jsr BarbaGeometry
    pla
    tax
    lda BREATH_GEOMETRY_FLAGS
    and #$01
    beq @clipped
    lda BREATH_MUZZLE_Y
    sta $36,x
    lda BREATH_MUZZLE_X
    clc
    adc $072C
    sta $5A,x
    lda $072A
    adc #$00
    sta $48,x
    ; Zero timeout means native Fire graphics and Fire-only vulnerability.
    lda #$00
    sta $05CA,x
    sec
    rts
@clipped:
    lda #$00
    sta $8D,x
    clc
    rts

; Compatibility entry used by the per-frame diagnostic mirror.
BarbaMuzzleScreen:
    jmp BarbaGeometry
