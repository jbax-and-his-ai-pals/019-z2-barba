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
VOLLEY_SLOT = $05FC ; two independent projectile lifetime counters (63 updates)
VOLLEY_LIFE = $3F ; 63 updates / 62 movement steps = 124 px
BREATH_UP = $646B ; volley aim latch: 0 forward, $40 upward
BREATH_REMAINING = $05FE ; pending shots, initially four after first allocation
METEOR_STATE = $6474 ; 0 idle, 1 diving (METEOR spell, slot 4 / $076F bit 4)
METEOR_WAVE = $C0 ; INFERNO_AIM / VOLLEY_SLOT flag pair: flat floor shockwave
METEOR_WAVE_LIFE = VOLLEY_LIFE ; 63 updates (124 px each way)
METEOR_WAVE_DY = $12 ; shockwave Y below the player's $29 (floor-level enemies)
METEOR_DIVE_VY = $06 ; forced fall speed while diving (6 px/frame)

; Spell dispatch precedes the timing-critical HUD split. Do not emit here.
BarbaSpellDeferred:
    rts

BarbaProjectiles:
    jsr BarbaBurstAllowed
    bcs @allowed
    lda #$00
    sta INFERNO_TIMER
    sta INFERNO_AIM
    sta METEOR_STATE
    jsr BarbaCancelBurst
    jsr BarbaExtraReset
    jmp @update
@allowed:
    jsr BarbaInfernoTick
    jsr BarbaMeteorTick
    lda BREATH_BURST_STATE
    cmp #$02
    bne @start
    ; B=$40 in held-controller state. Neither a held button nor another
    ; animation frame may turn the finite volley into an automatic stream.
    ; Treat $0400 == 4 (standing post-slash recovery) as idle so standing
    ; cancel-slashes can re-arm without moving first.
    lda $F7
    and #$40
    bne @update
    lda $0400
    beq @rearm
    cmp #$04
    bne @update
@rearm:
    lda #$00
    sta BREATH_BURST_STATE
@start:
    lda $0400
    ora $13
    beq :+
    jsr BarbaFireSpellAllowed
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
    lda $8D
    ora $8E
    beq @extra
    lda $0777
    cmp #$04
    bcs @native
    ldx #$01
    jsr $9888
@native:
    jsr $9878
@extra:
    jsr BarbaExtraUpdate
    lda VOLLEY_SLOT
    ora VOLLEY_SLOT+1
    ora EXTRA_LIVE
    beq @no_sfx
    jsr BarbaBreathSfx
@no_sfx:
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
    tya
    pha
    lda #$00
    sta $00
    sta $01
    tay
    ldx #$05
@enemy:
    lda $B6,x
    beq :+
    inc $00
:
    lda $87,x
    beq :+
    iny
:
    dex
    bpl @enemy
    tya
    lsr
    clc
    adc $00
    sta $00
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
    lda $01
    beq @allow
    lda $00
    cmp #$04
    bcc @total
    lda $01
    cmp #$02
    bcs @deny
@total:
    lda $00
    clc
    adc $01
    cmp #LOAD_LIMIT
    bcs @deny
@allow:
    sec
    .byte $24                   ; BIT zp skips CLC below; PLA/TAY keep Carry intact
@deny:
    clc
    pla
    tay
    rts
LOAD_LIMIT = 6

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
; Bits 6+7 together (METEOR_WAVE) fly flat along the floor.
; Carry set if still alive, clear if expired/clipped.
BarbaStepSlotY:
    lda $7D,x
    and #REBOUND_SPEED_BIT
    bne @rebound
    dec VOLLEY_SLOT,x
    lda VOLLEY_SLOT,x
    tay
    and #$3F
    beq @kill
    tya
    and #$40
    bne @up
    tya
    bpl @steep
    and #$01
    beq @alive
    bne @add_y
@steep:
    lda #$02
@add_y:
    clc
    adc $36,x
    cmp #$10
    bcc @kill
    cmp #$E0
    bcs @kill
    sta $36,x
    sec
    rts
@up:
    tya
    bmi @alive          ; METEOR_WAVE: flat
    lda #$FD            ; -3; underflow also fails the upper bound
    bne @add_y
@alive:
    sec
    rts
@kill:
    lda #$00
    sta $8D,x
    sta VOLLEY_SLOT,x
    clc
    rts
@rebound:
    clc
    jmp ShieldReboundBank4

; The initial shot alone uses the native attack/delay gate.
; Subsequent shots continue after the animation ends, without locking input.
BarbaFireSpell:
    jsr BarbaBurstAllowed
    bcs BarbaFireSpellAllowed
    rts
BarbaFireSpellAllowed:
    lda BREATH_BURST_STATE
    bne @done
    lda $13
    bne @wyrm
    lda $0400
    sec
    sbc #$01
    cmp $0495
    bne @done
    lda $050A
    cmp #$05
    bne @done
    beq @fire
@wyrm:
    lda $F5
    and #$40
    beq @done
    lda $5F
    beq :+
    cmp #$03
    bcs :+
    sta $9F
:
@fire:
    ; Consume this attack's gate even if its mouth or pool is unavailable.
    lda #$02
    sta BREATH_BURST_STATE
    lda #$00
    sta BREATH_UP
    lda $13
    bne @aimed
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
    jsr BarbaLoadOk
    bcc @arm
    jsr BarbaEmitOneCached
    bcc @done
    jsr BarbaBreathSfx
@arm:
    jmp BarbaArmBurst
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
    ora $DE
    bne @no
    lda $0728
    cmp #LAIR_CONTROL_LOCK
    bne :+
    jsr LavaLinkRoom
    beq @no
:
    lda $13
    beq @ok
    lda $0707
    cmp #$05
    bne @no
    lda $B6
    cmp #$01
    bne @no
    lda $A1
    cmp #$23
    bne @no
    lda $63
    cmp #$03
    bne @no
    lda $0505
    bne @no
    lda $5F
    beq @ok
    cmp #$03
    bcs @ok
    sta $9F
@ok:
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
    bne @geom_ok
    lda INFERNO_AIM
    bne :+
    jmp BarbaClipped
:
    lda #$50
    sta BREATH_MUZZLE_Y
@geom_ok:
    lda INFERNO_AIM
    cmp #METEOR_WAVE
    bcc @muzzle_y
    lda $29             ; METEOR shockwave hugs the floor, not the mouth
    clc
    adc #METEOR_WAVE_DY
    bcc @set_y
    jmp BarbaClipped
@muzzle_y:
    lda BREATH_MUZZLE_Y
    ldy BREATH_UP
    bne @up_y
    bit INFERNO_AIM
    bvc @set_y
@up_y:
    sec
    sbc #$0C ; folded or raised head top
    cmp #$10
    bcs @set_y
    ldy INFERNO_AIM
    beq BarbaClipped
    lda #$10
@set_y:
    sta $36,x
    lda BREATH_MUZZLE_X
    clc
    adc $072C
    sta $5A,x
    lda $072A
    adc #$00
    sta $48,x
    ; Dragon breath is always fire class ($05CA = 0): fire-only enemies are
    ; vulnerable without a spell, and slot 4 is the METEOR slam instead.
    ; Flame class strictly dominates the native beam ($D2) in bank 7 $E6CB.
    lda #$00
    sta $05CA,x
    lda INFERNO_AIM
    beq @normal_aim
    and #$03
    sta $6D,x
    lda INFERNO_AIM
    cmp #METEOR_WAVE
    bcc :+
    lda #(METEOR_WAVE | METEOR_WAVE_LIFE)
    bne @store_slot
:
    and #$40
    bne @up_life
    lda INFERNO_AIM
    and #$80
    ora #VOLLEY_LIFE
    bne @store_slot
@normal_aim:
    lda BREATH_UP
    bne @up_life
    lda #VOLLEY_LIFE
    ldy $13
    bne :+
    ldy $17
    bne :+
    ldy $0479
    bne :+
    ora #$80            ; grounded crouch: shallow 0.5 px/frame descent
:
@store_slot:
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

; Multi-wave Inferno firestorm: 4 waves at timer = $30, $20, $10, $00.
; Runs after the HUD split so projectile allocation never disturbs split timing.
BarbaInfernoTick:
    lda INFERNO_TIMER
    beq @done
    dec INFERNO_TIMER
    ldx INFERNO_TIMER
    txa
    and #$0F
    bne @done
    cpx #$10
    bne :+
    lda #$98
    sta $074B           ; extend decor palette flash through the firestorm
:
    ldy #$00
@emit_loop:
    sty $02
    jsr BarbaLoadOk
    bcc @stop
    ldy $02
    lda InfernoWaveDirs,y
    ldx INFERNO_TIMER
    cpx #$10
    beq @shallow
    cpx #$30
    bne @emit
@shallow:
    cmp #$40
    bcs @emit
    ora #$80
@emit:
    sta INFERNO_AIM
    jsr BarbaEmitOne
    ldy $02
    iny
    cpy #$04
    bcc @emit_loop
@stop:
    lda #$00
    sta INFERNO_AIM
@done:
    rts
InfernoWaveDirs:
    .byte $01, $02, $41, $42 ; R, L, up-R, up-L

; METEOR (slot 4, $076F bit 4; lasts like vanilla Fire until side-view init $8CF4 clears it).
; Airborne Down + B dives at the native fall cap; landing sends one flat
; floor shockwave each way. Runs after the HUD split, from BarbaProjectiles.
; Lives in the dead vanilla Check_for_Fire_Spell body ($9847-$9877, 49 bytes;
; its only caller, fixed-bank $D50D, is the BarbaUpdate hook).
.segment "FIRE_CHECK"
BarbaMeteorTick:
    lda $0479           ; airborne
    beq @ground
    lda METEOR_STATE
    bne @dive
    lda $076F
    and #$10
    beq @done
    lda $F7
    and #$04            ; Down held
    beq @done
    lda $F5
    and #$40            ; B pressed this frame
    beq @done
    inc METEOR_STATE
    jsr BarbaCancelBurst ; this B press is the slam, not a volley
@dive:
    lda #METEOR_DIVE_VY
    sta $057D
@done:
    rts
@ground:
    lsr METEOR_STATE
    bcc @done
    jmp MeteorLand

; Dead vanilla Fire spell body ($97F1-$9814, 36 bytes; its spell pointer is
; BarbaSpellDeferred and its other entry $97FA was only called from $985E).
.segment "FIRE_SPELL"
MeteorLand:
    lda $ED
    ora #$10            ; impact thud (the stomp-kill sound)
    sta $ED
    lda #$84            ; short decor flash
    sta $074B
    ldy #(METEOR_WAVE | $01)
    jsr MeteorEmit
    ldy #(METEOR_WAVE | $02)
MeteorEmit:
    jsr BarbaLoadOk
    bcc @done
    sty INFERNO_AIM
    jsr BarbaEmitOne
    lda #$00
    sta INFERNO_AIM
@done:
    rts

; Dead vanilla raft-avatar tail ($81C1-$81E4, 36 bytes): the "Sea crossing
; avatar" RTS at $81C0 skips it and only its own branch targets $81E4.
.segment "RAFT_TAIL"
BarbaCancelBurst:
    lda #$00
    sta BREATH_REMAINING
    sta BREATH_BURST_DELAY
    sta BURST_DEADLINE
    lda #$02
    bne BurstState
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
BurstState:
    sta BREATH_BURST_STATE
    rts
.segment "BANK0"
