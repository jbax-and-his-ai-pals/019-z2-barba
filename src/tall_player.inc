.export BarbaSetThrusts
; The native actor keeps its proven 32px collision body. Extra head sprites
; fold into that body under stone; crouching occupies the native 16px lane.
GEO_CACHE_TILES = $6458 ; 4 bytes: $04..$07
GEO_CACHE_BANK = $645D  ; $0769
GEO_CACHE_WORLD = $645E ; $0707
GEO_CACHE_RES = $645F   ; $00 open, $02 tuck, $FF uncached
.export BarbaGeometry
DRAW_TOP = $05F4
DRAW_LEFT = $05F5
GEOMETRY = $05F6
DRAW_INDEX = $05F9
DRAW_FRAME = $05FA
DRAW_ATTR = $05FB

BarbaGeometry:
    txa
    pha
    tya
    pha
    lda #$00
    sta GEOMETRY
    lda $CC
    clc
    adc #$04
    sta DRAW_LEFT
    lda $29
    sec
    sbc #$10
    sta DRAW_TOP
    lda $13
    bne @to_done
    lda $80
    cmp #$0C
    bcc :+
@to_done:
    jmp @done
:
    ; Native elevator contact is set by the enemy pass before this renderer.
    ; Fold visually without taking Down away from the elevator controller.
    lda $0754
    bne @fold
    lda $17
    bne @standing
    ; A low shield in the air is not a grounded crouch. Match the full-body
    ; airborne drawing for both the attached flame and new Fire shots.
    lda $0479
    bne @standing
@fold:
    jmp @duck
@standing:
    ; When grounded on palace lava or swamp water ($0752 != 0), submerge the
    ; lower body: shift the head and upper neck down 16px into the native box
    ; and omit the bottom row.
    lda LAVA_CONTACT
    ora $0752
    beq @not_lava
    lda $0479
    bne @not_lava
    lda #$04
    sta GEOMETRY
    lda $29
    sta DRAW_TOP
    jmp @add_4
@not_lava:
    ; Check both edges of the raised head against the area's solid-tile
    ; predicate. Its bank switch lives in fixed ROM, never in swapped code.
    lda $29
    cmp #$30
    bcs :+
    jmp @tuck
:
    ; Top row ($29 - $30) and bottom row ($29 - $21)
    sec
    sbc #$30
    and #$F0
    sta $00
    lda $29
    sec
    sbc #$21
    and #$F0
    sta $01
    ; Left X ($4D + 4) -> probes 0 (top-left) and 2 (bottom-left)
    lda $4D
    clc
    adc #$04
    tax
    lda $3B
    adc #$00
    and #$03
    tay
    lda $EAE0,y
    sta $0E
    lda $EAE4,y
    sta $0F
    txa
    lsr
    lsr
    lsr
    lsr
    tax
    ora $00
    tay
    lda ($0E),y
    sta $04
    txa
    ora $01
    tay
    lda ($0E),y
    sta $06
    ; Right X ($4D + 27) -> probes 1 (top-right) and 3 (bottom-right)
    lda $4D
    clc
    adc #$1B
    tax
    lda $3B
    adc #$00
    and #$03
    tay
    lda $EAE0,y
    sta $0E
    lda $EAE4,y
    sta $0F
    txa
    lsr
    lsr
    lsr
    lsr
    tax
    ora $00
    tay
    lda ($0E),y
    sta $05
    txa
    ora $01
    tay
    lda ($0E),y
    sta $07
    lda GEO_CACHE_RES
    bmi @probe_miss
    lda $0769
    cmp GEO_CACHE_BANK
    bne @probe_miss
    lda $0707
    cmp GEO_CACHE_WORLD
    bne @probe_miss
    lda $04
    cmp GEO_CACHE_TILES
    bne @probe_miss
    lda $05
    cmp GEO_CACHE_TILES+1
    bne @probe_miss
    lda $06
    cmp GEO_CACHE_TILES+2
    bne @probe_miss
    lda $07
    cmp GEO_CACHE_TILES+3
    bne @probe_miss
    lda GEO_CACHE_RES
    bne @tuck
    beq @standing_open
@probe_miss:
    lda $04
    sta GEO_CACHE_TILES
    lda $05
    sta GEO_CACHE_TILES+1
    lda $06
    sta GEO_CACHE_TILES+2
    lda $07
    sta GEO_CACHE_TILES+3
    lda $0769
    sta GEO_CACHE_BANK
    lda $0707
    sta GEO_CACHE_WORLD
    jsr TerrainBatch
    bcs @cache_tuck
    lda #$00
    sta GEO_CACHE_RES
@standing_open:
    lda $29
    sec
    sbc #$0C
    bne @mouth_y
@cache_tuck:
    lda #$02
    sta GEO_CACHE_RES
@tuck:
    lda #$02
    sta GEOMETRY
@add_4:
    lda #$04
    .byte $2C
@duck:
    lda #$0A
    clc
    adc $29
@mouth_y:
    sta BREATH_MUZZLE_Y
    cmp #$20
    bcc @done
    cmp #$E0
    bcs @done
    lda $9F
    cmp #$01
    bne @left
    lda $CC
    clc
    adc #$1C
    bcs @done
    bcc @mouth_x
@left:
    lda $CC
    sec
    sbc #$04
    bcc @done
@mouth_x:
    sta BREATH_MUZZLE_X
    inc GEOMETRY
@done:
    pla
    tay
    pla
    tax
    rts

BarbaDisplay:
    lda #$F8
    sta $0204
    sta $024C
    sta $02C4
    lda $13
    ora $048D
    bne @fallback
    lda $80
    cmp #$0C
    bcc @fast_prep
@fallback:
    jsr $EBF0
    ; Keep only the gated rising head-butt and the existing downstab.
    jsr BarbaSetThrusts
    lda $80
    cmp #$0C
    bcs :+
    lda #$F8
    sta $0220
    sta $0224
:
    rts
@fast_prep:
    ldx #$00
    stx $11
    lda #$08
    sta $90
    ldy #$00
    jsr $F27D
    lda $CC
    sta $15
    jsr BarbaSetThrusts
    lda #$F8
    sta $0220
    sta $0224
    jsr BarbaGeometry
    lda $050C
    lsr
    ora $0752
    and #$03
    ldx $9F
    dex
    bne :+
    ora #$40
:
    sta DRAW_ATTR
    lda $0754
    beq @native_pose
    lda #$06
    ldx $0400
    beq @pose
    lda #$07
    bne @pose
@native_pose:
.ifdef SAMPLED_ROAR
    lda ROAR_REQUEST
    and #$88
    cmp #$88
    bne :+
    lda #$08           ; celebration roar: open jaw with the head raised
    bne @pose
:
.endif
    lda $80
    ; Vanilla reuses crouch frame 6 on ascent. Select an independent full-body
    ; jump pose without changing its physics, shield state or technique gates.
    ldx $0479
    beq @pose
    cmp #$06
    bne @air_attack
    lda #$0C
    bne @pose
@air_attack:
    cmp #$07
    bne @pose
    lda #$05
@pose:
    ; Pose 8 (rising with Up: head-butt or upward breath) keeps the tilted
    ; looking-up head. An airborne attack whose volley is latched upward shows
    ; it too, including while descending (vanilla pose 7 -> frame 5 above).
    ; The airborne windup looks up when the volley will latch upward
    ; (same Up + Upward-tech test as BarbaFireSpell), so the head never
    ; flicks forward before the shots rise.
    cmp #$04
    bne @not_windup
    ldx $0479
    beq @not_windup
    bit $0796
    beq @not_windup
    asl
    bit $F7
    bne @not_windup
    lsr
@not_windup:
    cmp #$05
    bne :+
    ldx $0479
    beq :+
    ldx BREATH_UP
    beq :+
    ldx BREATH_BURST_STATE
    beq :+
    lda #$08
:
    sta DRAW_FRAME
    asl
    asl
    asl
    clc
    adc DRAW_FRAME
.macro TALL_SPRITE tile_off, oam, col
    .local @skip
    lda BarbaTallTiles+tile_off,x
    cmp #$F5
    beq @skip
    sta oam+1
    sty oam+2
    lda DRAW_LEFT
    .if col <> 0
    clc
    adc #col
    bcs @skip
    .endif
    sta oam+3
    lda $00
    sta oam
@skip:
.endmacro

    tax
    stx DRAW_FRAME
    lda #$F8
    sta $0208
    sta $020C
    sta $0210
    sta $0214
    sta $0218
    sta $021C
    bit DRAW_ATTR
    bvc :+
    jmp @draw_right
:
    lda GEOMETRY
    and #$02
    sta $01
    ; Top row (0, 1, 2): DRAW_TOP (+ $10 if tucked)
    lda DRAW_TOP
    ldy $01
    beq :+
    clc
    adc #$10
    bcs @l_mid
:
    cmp #$20
    bcc @l_mid
    cmp #$F0
    bcs @l_mid
    sta $00
    ldy DRAW_ATTR
        TALL_SPRITE 0, $0204, 0
    TALL_SPRITE 1, $024C, 8
    TALL_SPRITE 2, $02C4, 16
@l_mid:
    lda $01
    bne @l_bot
    lda DRAW_TOP
    clc
    adc #$10
    bcs @l_bot
    cmp #$20
    bcc @l_bot
    cmp #$F0
    bcs @l_bot
    sta $00
    ldy DRAW_ATTR
    TALL_SPRITE 3, $0208, 0
    TALL_SPRITE 4, $020C, 8
    TALL_SPRITE 5, $0210, 16
@l_bot:
    lda GEOMETRY
    and #$04
    bne @done_draw
    lda DRAW_TOP
    clc
    adc #$20
    bcs @done_draw
    cmp #$20
    bcc @done_draw
    cmp #$F0
    bcs @done_draw
    sta $00
    ldy DRAW_ATTR
    TALL_SPRITE 6, $0214, 0
    TALL_SPRITE 7, $0218, 8
    TALL_SPRITE 8, $021C, 16
@done_draw:
    ; Downstab (pose 9, DRAW_FRAME == $51) adds a second torso chunk above
    ; Row 0 using the unused native sword/shield OAM slots ($0220/$0224).
    lda DRAW_FRAME
    cmp #$51
    bne @no_extra_torso
    ; Flip both neck chunks horizontally and vertically in place. The down
    ; layout and extra chunk reverse tile columns to match the horizontal flip.
    lda DRAW_ATTR
    eor #$C0
    sta $0206
    sta $024E
    sta $02C6
    lda GEOMETRY
    and #$06
    bne @no_extra_torso
    lda DRAW_TOP
    sec
    sbc #$10
    cmp #$20
    bcc @no_extra_torso
    cmp #$F0
    bcs @no_extra_torso
    sta $00
    ldx #$08
    ldy #$06
    lda DRAW_LEFT
    bit DRAW_ATTR
    bvc @extra_left
    ldx #$06
    ldy #$08
    bcc @extra_place
@extra_left:
    clc
    adc #$08
    bcs @no_extra_torso
@extra_place:
    sta $0223
    stx $0221
    ldx $00
    stx $0220
    ldx $0206
    stx $0222
    clc
    adc #$08
    bcs @no_extra_torso
    sta $0227
    sty $0225
    lda $00
    sta $0224
    stx $0226
@no_extra_torso:
.ifdef SAMPLED_ROAR
    ; Skip the mapper round trip unless there's an item or raised-head roar.
    lda ITEM_HOLD
    bne @celebration
    lda ROAR_REQUEST
    and #$88
    cmp #$88
    bne @no_celebration
@celebration:
    jsr RoarTorsoHop
@no_celebration:
.endif
    lda $12
    lsr
    bcc @no_rot
    lda $0707
    cmp #$01
    beq @no_rot
    cmp #$02
    beq @no_rot
    ; Alternate only our outer head tiles. Enemy records keep native ownership:
    ; never move their sprites into the player's record or leave dragon tiles
    ; inside a rotating enemy record.
    ldx #$03
@rot_head:
    lda $0204,x
    ldy $02C4,x
    sta $02C4,x
    tya
    sta $0204,x
    dex
    bpl @rot_head
@no_rot:
    rts

@draw_right:
    lda GEOMETRY
    and #$02
    sta $01
    lda DRAW_TOP
    ldy $01
    beq :+
    clc
    adc #$10
    bcs @r_mid
:
    cmp #$20
    bcc @r_mid
    cmp #$F0
    bcs @r_mid
    sta $00
    ldy DRAW_ATTR
        TALL_SPRITE 2, $0204, 0
    TALL_SPRITE 1, $024C, 8
    TALL_SPRITE 0, $02C4, 16
@r_mid:
    lda $01
    bne @r_bot
    lda DRAW_TOP
    clc
    adc #$10
    bcs @r_bot
    cmp #$20
    bcc @r_bot
    cmp #$F0
    bcs @r_bot
    sta $00
    ldy DRAW_ATTR
    TALL_SPRITE 5, $0208, 0
    TALL_SPRITE 4, $020C, 8
    TALL_SPRITE 3, $0210, 16
@r_bot:
    lda GEOMETRY
    and #$04
    bne @r_done
    lda DRAW_TOP
    clc
    adc #$20
    bcs @r_done
    cmp #$20
    bcc @r_done
    cmp #$F0
    bcs @r_done
    sta $00
    ldy DRAW_ATTR
    TALL_SPRITE 8, $0214, 0
    TALL_SPRITE 7, $0218, 8
    TALL_SPRITE 6, $021C, 16
@r_done:
    jmp @done_draw
.ifdef SAMPLED_ROAR
RoarTorsoHop:
    lda #>(RoarGemTorso-1)
    pha
    lda #<(RoarGemTorso-1)
    pha
    lda #$06
    jmp $FFCC
.endif
; No horizontal melee. Downstab sits under the feet; upward thrust uses the
; native head top, never the visually raised 48px head. Both are centered.
BarbaSetThrusts:
    lda $80
    cmp #$08
    beq @up
    cmp #$09
    bne @no_melee
    lda $29
    clc
    adc #$1C
    bcs @no_melee
    sta $0480
@center:
    lda $CC
    clc
    adc #$0B
    bcc :+
    lda #$FF
:
    sta $047E
    rts
@up:
    lda $0796
    and #$04
    beq @no_melee
    lda $0479
    beq @no_melee
    lda $057D
    bpl @no_melee
    lda $29
    sec
    sbc #$08 ; native head top minus reach, not tall art top
    bcc @no_melee
    sta $0480
    jmp @center
@no_melee:
    lda #$F8
    sta $0480
    rts
.include "tall_layout.inc"
