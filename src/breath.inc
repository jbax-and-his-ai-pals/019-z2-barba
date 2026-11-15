; Five-shot forward/down or technique-gated upward dragon breath. Runs after the sprite-zero HUD split.
; Two native slots plus three backed slots preserve range at an even cadence.
.export BarbaProjectiles, BarbaFireSpell, BarbaMuzzleScreen, BarbaSpellDeferred
.export BarbaVolleyPlaced, BarbaStepSlotY
BREATH_MUZZLE_X = $05F2
BREATH_MUZZLE_Y = $05F3
BREATH_GEOMETRY_FLAGS = $05F6
BURST_DEADLINE = $05F1 ; finite 120-update lifetime, including blocked spawns
BREATH_BURST_DELAY = $05F7
BREATH_BURST_STATE = $05F8 ; 0 ready, 1 active, 2 wait for release/attack idle
VOLLEY_SLOT = $05FC ; two independent projectile lifetime counters (33 updates)
BREATH_UP = $6469 ; volley aim latch: 0 forward, $40 upward
BREATH_REMAINING = $05FE ; pending shots, initially four after first allocation

; Spell dispatch precedes the timing-critical HUD split. Do not emit here.
BarbaSpellDeferred:
    rts

BarbaProjectiles:
    jsr BarbaBurstAllowed
    bcs @allowed
    jsr BarbaCancelBurst
    jsr BarbaExtraReset
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
    lda $0400
    beq :+
    jsr BarbaFireSpell
:
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
    jsr BarbaLoadOk
    bcc @update ; busy room: hold this shot; the 120-update deadline still applies
    jsr BarbaEmitOne
    bcc @update
    dec BREATH_REMAINING
    beq @cancel
    lda #$08
    sta BREATH_BURST_DELAY
    jmp @update
@cancel:
    jsr BarbaCancelBurst
@update:
    lda VOLLEY_SLOT
    ora VOLLEY_SLOT+1
    beq @no_volley
    jsr BarbaAdvanceVolley
@no_volley:
    lda $0777
    cmp #$04
    bcs @native
    ldx #$01
    jsr $9888
@native:
    jsr $9878
    lda VOLLEY_SLOT
    ora VOLLEY_SLOT+1
    beq @extra
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
@extra:
    jsr BarbaExtraUpdate
    rts

; The same five-slot allocation path handles both initial and queued shots.
; Never index the native actor arrays with X >= 2: that aliases player state.
BarbaEmitOne:
    clc
    .byte $24                   ; BIT zp: skip SEC below
BarbaEmitOneCached:
    sec
    php
    ldx #$01
@slot:
    lda $8D,x
    beq @native
    dex
    bpl @slot
    plp
    jmp BarbaExtraAllocate
@native:
    clc
    jsr $981B
    plp
    bcc :+
    jmp BarbaPlaceNewFlameCached
:
    jmp BarbaPlaceNewFlame

; Frame-budget governor for queued shots (not the attack's first shot).
; Measured in tests/perf_volley.lua: vanilla peaks near 26.6k cycles with six
; enemies; each live shot adds ~1.2-1.7k, and lag began once enemies plus live
; shots reached seven. Carry set when another shot may spawn.
BarbaLoadOk:
    lda #$00
    sta $00
    sta $01
    ldx #$05
@enemy:
    lda $B6,x
    beq :+
    inc $00
:
    dex
    bpl @enemy
    ldx #$01
@native:
    lda $8D,x
    beq :+
    bmi :+
    inc $01
:
    dex
    bpl @native
    ldx #$00
@extra:
    lda $6400,x
    beq :+
    bmi :+
    inc $01
:
    txa
    clc
    adc #$10
    tax
    cpx #$30
    bcc @extra
    lda $00
    cmp #$02
    bcc @total
    lda $01
    cmp #$03
    bcs @deny
@total:
    lda $00
    clc
    adc $01
    cmp #LOAD_LIMIT
    bcs @deny
    sec
    rts
@deny:
    clc
    rts
LOAD_LIMIT = 7

BarbaCancelBurst:
    lda #$00
    sta BREATH_REMAINING
    sta BREATH_BURST_DELAY
    sta BURST_DEADLINE
    lda #$02
    sta BREATH_BURST_STATE
    rts

; Both damage classes share aim and expiry. Fire changes vulnerability,
; not the lifetime, which guarantees that a two-slot pool can emit five shots.
BarbaAdvanceVolley:
    ldx #$01
@slot:
    lda VOLLEY_SLOT,x
    beq @next
    lda $8D,x
    beq @clear
    bmi @clear
    jsr BarbaStepSlotY
    jmp @next
@clear:
    lda #$00
    sta VOLLEY_SLOT,x
@next:
    dex
    bpl @slot
    rts

; Advance slot X: low 6 bits lifetime, bit 6 upward (-3 px). Bit 7 selects
; crouched shallow descent (0.5 px/frame) so low fireballs clear high shields.
; Carry set if still alive, clear if expired/clipped.
BarbaStepSlotY:
    dec VOLLEY_SLOT,x
    lda VOLLEY_SLOT,x
    and #$3F
    beq @kill
    lda VOLLEY_SLOT,x
    and #$40
    bne @up
    lda VOLLEY_SLOT,x
    bpl @steep
    and #$01
    beq @alive
    bne @add_y
@steep:
    lda #$02
@add_y:
    clc
    adc $36,x
    bcs @kill
    cmp #$E0
    bcs @kill
    sta $36,x
    jmp @alive
@up:
    lda $36,x
    sec
    sbc #$03
    bcc @kill
    cmp #$10
    bcc @kill
    sta $36,x
@alive:
    sec
    rts
@kill:
    lda #$00
    sta $8D,x
    sta VOLLEY_SLOT,x
    clc
    rts

; The initial shot alone uses the native attack/delay gate.
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
    lda #$00
    sta BREATH_UP
    lda $0479
    beq @aimed
    lda $0796
    and #$04
    beq @aimed
    lda $F7
    and #$08
    beq @aimed
    lda #$40
    sta BREATH_UP
@aimed:
    jsr BarbaGeometry
    lda BREATH_GEOMETRY_FLAGS
    and #$01
    beq @done
    jsr BarbaEmitOneCached
    bcc @done
    jsr BarbaArmBurst
    jsr BarbaBreathSfx
@done:
    rts

; Trigger Zelda II's native Barba / Flame fireball sound ($ED bit 6) once per attack
; so five-shot volleys sound like vanilla Barba without re-triggering every shot.
BarbaBreathSfx:
    lda ROAR_TIMER
    bne @skip
    lda $ED
    ora #$40
    sta $ED
@skip:
    rts

BarbaArmBurst:
    ; Initial emission and scheduler run in the same update. Nine compensates
    ; for that first decrement, yielding eight full updates between all shots.
    lda #$09
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
BarbaPlaceNewFlameCached:
    lda BREATH_GEOMETRY_FLAGS
    and #$01
    beq BarbaClipped
    lda BREATH_MUZZLE_Y
    ldy BREATH_UP
    beq :+
    sec
    sbc #$0C ; folded or raised head top
    cmp #$10
    bcc BarbaClipped
:
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
    lda BREATH_UP
    bne @up_life
    lda #$21
    ldy $17
    bne :+
    ldy $0479
    bne :+
    ora #$80            ; grounded crouch: shallow 0.5 px/frame descent
:
    sta VOLLEY_SLOT,x
    ldy $6D,x
    lda VolleySpeed,y
    jmp @speed
@up_life:
    ora #$1C ; 28 updates
    sta VOLLEY_SLOT,x
    ldy $6D,x
    lda VolleyUpSpeed,y
@speed:
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
VolleyUpSpeed:
    .byte $00,$10,$F0
