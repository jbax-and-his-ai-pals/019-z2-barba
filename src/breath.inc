; Five-shot diagonal dragon breath. Runs after the sprite-zero HUD split.
; Two native slots plus three backed slots preserve range at an even cadence.
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
    jsr BarbaExtraUpdate
    rts

; The same five-slot allocation path handles both initial and queued shots.
; Never index the native actor arrays with X >= 2: that aliases player state.
BarbaEmitOne:
    ldx #$01
@slot:
    lda $8D,x
    beq @native
    dex
    bpl @slot
    jmp BarbaExtraAllocate
@native:
    clc
    jsr $981B
    jmp BarbaPlaceNewFlame

; Frame-budget governor for queued shots (not the attack's first shot).
; Measured in tests/perf_volley.lua: vanilla peaks near 26.6k cycles with six
; enemies; each live shot adds ~1.2-1.7k, and lag began once enemies plus live
; shots reached seven. Carry set when another shot may spawn.
BarbaLoadOk:
    lda #$00
    sta $00
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
    inc $00
:
    dex
    bpl @native
    ldx #$00
@extra:
    lda $6400,x
    beq :+
    bmi :+
    inc $00
:
    txa
    clc
    adc #$10
    tax
    cpx #$30
    bcc @extra
    lda $00
    cmp #LOAD_LIMIT
    bcs @deny
    sec
    rts
@deny:
    clc
    rts
LOAD_LIMIT = 6

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
    jsr BarbaGeometry
    lda BREATH_GEOMETRY_FLAGS
    and #$01
    beq @done
    jsr BarbaEmitOne
    bcc @done
    jsr BarbaArmBurst
@done:
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
