; Five-shot diagonal dragon breath. Runs after the sprite-zero HUD split.
; Two native slots are reused; movement stays free while the volley drains.
.export BarbaProjectiles, BarbaFireSpell, BarbaMuzzleScreen, BarbaSpellDeferred
.export BarbaVolleyPlaced
BREATH_MUZZLE_X = $05F2
BREATH_MUZZLE_Y = $05F3
BREATH_GEOMETRY_FLAGS = $05F6
BURST_DEADLINE = $05F1 ; finite 120-update lifetime, including blocked spawns
BREATH_BURST_DELAY = $05F7
BREATH_BURST_STATE = $05F8 ; 0 ready, 1 active, 2 wait for release/attack idle
VOLLEY_SLOT = $05FC ; two independent projectile lifetime counters (33 updates)
BREATH_REMAINING = $05FE ; pending shots, initially four after first allocation

; Spell dispatch precedes the timing-critical HUD split. Do not emit here.
BarbaSpellDeferred:
    rts

BarbaProjectiles:
    jsr BarbaBurstAllowed
    bcs @allowed
    jsr BarbaCancelBurst
    jmp @update
@allowed:
    lda BREATH_BURST_STATE
    cmp #$02
    bne @start
    ; B=$40 in held-controller state. Neither a held button nor another
    ; animation frame may turn the finite volley into an automatic stream.
    lda $F7
    and #$40
    ora $0400
    bne @update
    lda #$00
    sta BREATH_BURST_STATE
@start:
    jsr BarbaFireSpell
    lda BREATH_BURST_STATE
    cmp #$01
    bne @update
    dec BURST_DEADLINE
    beq @cancel
    lda BREATH_BURST_DELAY
    beq @find
    dec BREATH_BURST_DELAY
    bne @update
@find:
    ldx #$01
@slot:
    lda $8D,x
    beq @emit
    dex
    bpl @slot
    ; Retry a full pool next update, bounded by BURST_DEADLINE. Never restart
    ; the count or consume an unallocated shot.
    jmp @update
@emit:
    clc ; native allocator's first ADC requires a cleared carry
    jsr $981B
    jsr BarbaPlaceNewFlame
    bcc @update
    dec BREATH_REMAINING
    beq @cancel
    lda #$08
    sta BREATH_BURST_DELAY
    jmp @update
@cancel:
    jsr BarbaCancelBurst
@update:
    jsr BarbaAdvanceVolley
    lda $0777
    cmp #$04
    bcs @native
    ldx #$01
    jsr $9888
@native:
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

BarbaCancelBurst:
    lda #$00
    sta BREATH_REMAINING
    sta BREATH_BURST_DELAY
    sta BURST_DEADLINE
    lda #$02
    sta BREATH_BURST_STATE
    rts

; Both classes descend and expire identically. Fire changes vulnerability,
; not the lifetime, which guarantees that a two-slot pool can emit five shots.
BarbaAdvanceVolley:
    ldx #$01
@slot:
    lda VOLLEY_SLOT,x
    beq @next
    lda $8D,x
    beq @clear
    bmi @clear
    dec VOLLEY_SLOT,x
    beq @kill
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

; The initial shot alone uses the native attack/delay gate and allocator.
; Subsequent shots continue after the animation ends, without locking input.
BarbaFireSpell:
    jsr BarbaBurstAllowed
    bcc @done
    lda BREATH_BURST_STATE
    bne @done
    lda $0400
    sec
    sbc #$01
    cmp $0495
    bne @done
    lda $050A
    cmp #$05
    bne @done
    ; Consume this attack's gate even if its mouth or pool is unavailable.
    lda #$02
    sta BREATH_BURST_STATE
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
    lda #$04
    sta BREATH_REMAINING
    lda #$78
    sta BURST_DEADLINE
    lda #$01
    sta BREATH_BURST_STATE
    rts

; Health and the Fire spell never gate basic dragon breath.
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
    sec
    rts
@no:
    clc
    rts

; Fresh shared geometry per shot; X is the allocated native slot.
BarbaPlaceNewFlame:
    txa
    pha
    jsr BarbaGeometry
    pla
    tax
    lda BREATH_GEOMETRY_FLAGS
    and #$01
    beq BarbaClipped
    lda BREATH_MUZZLE_Y
    sta $36,x
    lda BREATH_MUZZLE_X
    clc
    adc $072C
    sta $5A,x
    lda $072A
    adc #$00
    sta $48,x
    lda #$00
    sta $05CA,x
    lda $076F
    and #$10
    bne :+
    lda #$D2
    sta $05CA,x
:
    lda #$21
    sta VOLLEY_SLOT,x
    ldy $6D,x
    lda VolleySpeed,y
    sta $7D,x
BarbaVolleyPlaced:
    sec ; exported callback point: X identifies a successfully placed shot
    rts
BarbaClipped:
    lda #$00
    sta $8D,x
    sta VOLLEY_SLOT,x
    clc
    rts
BarbaMuzzleScreen:
    jmp BarbaGeometry
VolleySpeed:
    .byte $00,$20,$E0
