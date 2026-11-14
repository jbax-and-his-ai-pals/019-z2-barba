; The native actor keeps its proven 32px collision body. Extra head sprites
; fold into that body under stone; crouching occupies the native 16px lane.
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
    beq :+
    jmp @done
:
    lda $80
    cmp #$0C
    bcc :+
    jmp @done
:
    lda $17
    bne @standing
    ; A low shield in the air is not a grounded crouch. Match the full-body
    ; airborne drawing for both the attached flame and new Fire shots.
    lda $0479
    bne @standing
    jmp @duck
@standing:
    ; Check both edges of the raised head against the area's solid-tile
    ; predicate. Its bank switch lives in fixed ROM, never in swapped code.
    lda $29
    cmp #$30
    bcc @tuck
    ldx #$00
@probe:
    lda $4D
    clc
    adc HeadProbeX,x
    sta $00
    lda $3B
    adc #$00
    and #$03
    tay
    lda $EAE0,y
    sta $0E
    lda $EAE4,y
    sta $0F
    lda $00
    lsr
    lsr
    lsr
    lsr
    sta $00
    lda $29
    sec
    sbc HeadProbeY,x
    and #$F0
    ora $00
    tay
    lda ($0E),y
    txa
    pha
    lda ($0E),y
    jsr TerrainGateway
    pla
    tax
    bcs @tuck
    inx
    cpx #$04
    bne @probe
    lda $29
    sec
    sbc #$0C
    jmp @mouth_y
@tuck:
    lda #$02
    sta GEOMETRY
    lda $29
    clc
    adc #$04
    jmp @mouth_y
@duck:
    lda $29
    clc
    adc #$14
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
    jmp @mouth_x
@left:
    lda $CC
    sec
    sbc #$04
    bcc @done
@mouth_x:
    sta BREATH_MUZZLE_X
    lda GEOMETRY
    ora #$01
    sta GEOMETRY
@done:
    pla
    tay
    pla
    tax
    rts
HeadProbeX:
    .byte 4, 27, 4, 27
HeadProbeY:
    .byte $30,$30,$21,$21

BarbaDisplay:
    lda #$F8
    sta $0224
    sta $0228
    sta $022C
    sta $0230
    jsr $EBF0
    lda $13
    beq :+
    rts
:
    lda $048D
    beq :+
    rts
:
    lda $80
    cmp #$0C
    bcc :+
    rts
:
    jsr BarbaGeometry
    lda $020A
    and #$43
    sta DRAW_ATTR
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
    sta DRAW_FRAME
    asl
    asl
    asl
    clc
    adc DRAW_FRAME
    sta DRAW_FRAME
    lda #$00
    sta DRAW_INDEX
@sprite:
    ldx DRAW_INDEX
    ldy TallOam,x
    lda #$F8
    sta $0200,y
    lda GEOMETRY
    and #$02
    beq @tile
    cpx #$03
    bcc @tile
    cpx #$06
    bcc @next
@tile:
    lda $9F
    cmp #$01
    bne @unflipped
    lda TallMirror,x
    tax
@unflipped:
    txa
    clc
    adc DRAW_FRAME
    tax
    lda BarbaTallTiles,x
    cmp #$F5
    beq @next
    sta $0201,y
    lda DRAW_ATTR
    sta $0202,y
    ldx DRAW_INDEX
    lda DRAW_LEFT
    clc
    adc TallColumn,x
    bcs @next
    sta $0203,y
    lda TallRow,x
    cpx #$03
    bcs @row
    pha
    lda GEOMETRY
    and #$02
    beq @top_normal
    pla
    clc
    adc #$10
    jmp @row
@top_normal:
    pla
@row:
    clc
    adc DRAW_TOP
    cmp #$20
    bcc @next
    cmp #$F0
    bcs @next
    sta $0200,y
@next:
    inc DRAW_INDEX
    lda DRAW_INDEX
    cmp #$09
    bne @sprite
    lda $80
    cmp #$05
    beq @flame
    cmp #$07
    bne @done
@flame:
    lda $0220
    cmp #$F8
    bcs @done
    lda GEOMETRY
    and #$01
    beq @hide_flame
    lda BREATH_MUZZLE_Y
    sta $0220
    sta $0224
    sta $0480
    lda BREATH_MUZZLE_X
    sta $0223
    sta $047E
    lda $9F
    cmp #$01
    bne @left
    lda BREATH_MUZZLE_X
    clc
    adc #$08
    sta $047E
    bcs @hide_tip
    jmp @tip
@left:
    lda BREATH_MUZZLE_X
    sec
    sbc #$08
    bcc @hide_tip
@tip:
    sta $0227
    lda #$50
    sta $0225
    lda DRAW_ATTR
    sta $0222
    sta $0226
@done:
    rts
@hide_flame:
    lda #$F8
    sta $0220
    sta $0480
@hide_tip:
    lda #$F8
    sta $0224
    rts
TallOam:
    .byte $28,$2C,$30,$08,$0C,$10,$14,$18,$1C
TallMirror:
    .byte 2,1,0,5,4,3,8,7,6
TallColumn:
    .byte 0,8,16,0,8,16,0,8,16
TallRow:
    .byte 0,0,0,16,16,16,32,32,32
.include "tall_layout.inc"
