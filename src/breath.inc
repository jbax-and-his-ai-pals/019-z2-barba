; Barba's melee/Fire/full-life volley integration (BANK0).
; BarbaGeometry supplies the attached plume's top-left in screen space and
; bit 0 of its validity flags. Both shots sample that geometry at spawn time.
.export BarbaProjectiles, BarbaFireSpell, BarbaMuzzleScreen, BarbaSpellDeferred

BREATH_MUZZLE_X = $05F2
BREATH_MUZZLE_Y = $05F3
BREATH_GEOMETRY_FLAGS = $05F6
BREATH_BURST_DELAY = $05F7
BREATH_BURST_STATE = $05F8 ; 0 ready, 1 pending, 2 attempted until attack ends
VOLLEY_SLOT = $05FC ; two flags; non-Fire full-life projectiles
BREATH_MODE = $05FE ; 0 Fire spell, 1 full-life diagonal volley

; The spell dispatcher runs before the sprite-zero HUD split. Defer all
; emission/geometry until BarbaProjectiles, after that timing-critical split.
BarbaSpellDeferred:
    rts

; Replace the automatic straight sword beam with a bounded diagonal volley.
; Native update-only tail retains collision, disintegration and sound.
BarbaProjectiles:
    ; Full life restores the beam's original attack gate, now as dragon fire.
    ; The shared latch prevents repeated shots while an attack is held.
    jsr BarbaFireSpell
    jsr BarbaBurstAllowed
    bcc @cancel
    lda BREATH_MODE
    beq @attack
    jsr BarbaFullHealth
    bcc @cancel
@attack:
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
    jsr BarbaAdvanceVolley
    ; Native code ignores slot 1 at Attack 1-3. Update it once here so the
    ; two-shot burst works at every attack level, still with only two slots.
    lda $0777
    cmp #$04
    bcs @native_update
    ldx #$01
    jsr $9888
@native_update:
    jsr $9878
    txa
    pha
    ldx #$01
@draw:
    lda VOLLEY_SLOT,x
    beq @next
    lda $8D,x
    beq @next
    bmi @next
    ldy $9D,x
    lda #$84
    sta $0201,y
    lda $0202,y
    and #$C0
    ora #$01
    sta $0202,y
@next:
    dex
    bpl @draw
    pla
    tax
    rts

; Native player fire has horizontal motion only. Full-life fireballs descend
; two pixels per update before native movement/collision/drawing samples them.
BarbaAdvanceVolley:
    ldx #$01
@slot:
    lda VOLLEY_SLOT,x
    beq @next
    lda $8D,x
    beq @clear
    bmi @clear
    lda $36,x
    clc
    adc #$02
    bcs @kill
    cmp #$E0
    bcs @kill
    sta $36,x
    jmp @next
@kill:
    lda #$00
    sta $8D,x
@clear:
    lda #$00
    sta VOLLEY_SLOT,x
@next:
    dex
    bpl @slot
    rts

; Fire's first shot retains the original attack-animation/delay gate and
; allocator. A successful initial shot arms a single eight-frame follow-up.
BarbaFireSpell:
    jsr BarbaBurstAllowed
    bcc @done
    lda BREATH_BURST_STATE
    bne @done
    ; Avoid head probes/bank switches on every idle Fire-spell frame. These
    ; are the native first-shot gates and run again inside $97F1.
    lda $0400
    sec
    sbc #$01
    cmp $0495
    bne @done
    lda $050A
    cmp #$05
    bne @done
    lda #$00
    sta BREATH_MODE
    jsr BarbaFullHealth
    bcc :+
    inc BREATH_MODE
:
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
    jsr BarbaFullHealth
    bcs @yes
    lda $076F
    and #$10
    beq @no
@yes:
    sec
    rts
@no:
    clc
    rts

; Carry set only for the game's exact full-life value (containers*32 - 1).
BarbaFullHealth:
    lda $0784
    asl
    asl
    asl
    asl
    asl
    sec
    sbc #$01
    cmp $0774
    bne @no
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
    sta VOLLEY_SLOT,x
    lda BREATH_MODE
    beq @placed
    ; Without Fire, retain beam-class damage and its native timeout. Casting
    ; Fire empowers the same diagonal volley to hit Fire-only enemies.
    lda $076F
    and #$10
    bne :+
    lda #$D2
    sta $05CA,x
:
    lda #$01
    sta VOLLEY_SLOT,x
    ldy $6D,x
    lda VolleySpeed,y
    sta $7D,x
@placed:
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
VolleySpeed:
    .byte $00,$20,$E0
