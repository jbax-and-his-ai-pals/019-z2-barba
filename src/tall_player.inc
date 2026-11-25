.export BarbaDisplay, BarbaDisplayBody, BarbaSetThrusts, BarbaFallDraw, BarbaBossShadow
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
    beq @not_fairy
    lda $0707
    cmp #$05
    bne @to_done
    lda $B6
    cmp #$01
    bne @to_done
    lda $A1
    cmp #$23
    bne @to_done
    lda $63
    cmp #$03
    bne @to_done
    lda $0505
    beq @fold
@to_done:
    jmp @done
@not_fairy:
    lda $80
    cmp #$0C
    bcs @to_done
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
    jsr BarbaCeiling
    sta GEOMETRY
    bne @add_4
    lda $29
    sec
    sbc #$0C
    bne @mouth_y
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

; Return the standing ceiling fold flag in A.
BarbaCeiling:
    ; Check both edges of the raised head against the area's solid-tile
    ; predicate. Its bank switch lives in fixed ROM, never in swapped code.
    lda $29
    cmp #$30
    bcs :+
    lda #$02
    rts
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
    jsr @set_page_ptr
    jsr @probe_col
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
    bcc @same_page
    jsr @set_page_ptr
@same_page:
    jsr @probe_col
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
    rts
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
    beq @cache_result
@cache_tuck:
    lda #$02
@cache_result:
    sta GEO_CACHE_RES
    rts
@set_page_ptr:
    lda $3B
    adc #$00
    and #$03
    tay
    lda $EAE0,y
    sta $0E
    lda $EAE4,y
    sta $0F
    rts
@probe_col:
    txa
    lsr
    lsr
    lsr
    lsr
    tax
    ora $00
    tay
    lda ($0E),y
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
    cpx #6*9
    beq @crouch_bend
    cpx #7*9
    bne BarbaDisplayBody
@crouch_bend:
    lda $17
    ora $0479
    bne BarbaDisplayBody
    lda $29
    cmp #$30
    bcc BarbaDisplayBody
    ; Start the full 16px head at the original crouch horns. The cropped
    ; curve starts 16px later and ends at the original crouch feet.
    sbc #$08
    sta DRAW_TOP
    cpx #6*9
    beq @closed_head
    ldx #BarbaCorridorAttack-BarbaTallTiles
    bne BarbaDisplayBody
@closed_head:
    ldx #BarbaCorridorCrouch-BarbaTallTiles
BarbaDisplayBody:
    lda #$F8
    sta $0208
    sta $020C
    sta $0210
    sta $0214
    sta $0218
    sta $021C
    bit DRAW_ATTR
    bvc :+
    jmp BarbaDisplayRight
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
    bne BarbaDisplayDone
    lda DRAW_TOP
    clc
    adc #$20
    bcs BarbaDisplayDone
    cmp #$20
    bcc BarbaDisplayDone
    cmp #$F0
    bcs BarbaDisplayDone
    sta $00
    ldy DRAW_ATTR
    TALL_SPRITE 6, $0214, 0
    TALL_SPRITE 7, $0218, 8
    TALL_SPRITE 8, $021C, 16
BarbaDisplayDone:
    lda DRAW_FRAME
    cmp #$51
    bne @no_extra_torso
    jsr DownstabTorsoHop
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

DownstabTorsoHop:
    lda #>(DownstabTorso1-1)
    pha
    lda #<(DownstabTorso1-1)
    pha
    lda #$03
    jmp $FFCC

DownstabTerrain0:
    jsr TerrainBatch
    rol $00
    lda #$03
    jmp $FFCC

DOWNSTAB_ROWS = $64FE

.segment "BANK3_DLG"
; Pose 9 draws the 2nd torso chunk above row 0 in open air (BANK6_OAM/BANK3_DLG
; extends the 3rd chunk and wagging tip into free shadow OAM), or replaces
; row 0 with row 1 ($4A, $4C, $56) for a 24x32 head under a 2-tile tuck.
DownstabTorso1:
    lda #$00
    sta DOWNSTAB_ROWS
    lda GEOMETRY
    and #$02
    beq @open_air
    lda DRAW_TOP
    clc
    adc #$10
    bcs @done
    cmp #$20
    bcc @done
    cmp #$F0
    bcs @done
    sta $0204
    sta $024C
    sta $02C4
    lda DRAW_ATTR
    sta $0206
    sta $024E
    sta $02C6
    ldx #$4A
    ldy #$56
    bit DRAW_ATTR
    bvc @tuck_tiles
    ldx #$56
    ldy #$4A
@tuck_tiles:
    stx $0205
    lda #$4C
    sta $024D
    sty $02C5
    lda DRAW_LEFT
    sta $0207
    clc
    adc #$08
    bcs @hide_mid
    sta $024F
    adc #$08
    bcs @hide_right
    sta $02C7
@done:
    jmp $FFC5
@hide_mid:
    lda #$F8
    sta $024C
@hide_right:
    lda #$F8
    sta $02C4
    jmp $FFC5

@open_air:
    ; Flip Row 0 neck chunks horizontally and vertically in place.
    lda DRAW_ATTR
    eor #$C0
    sta $0206
    sta $024E
    sta $02C6
    lda GEOMETRY
    and #$04
    bne @open_ret_near
    ; Probe Y1 = DRAW_TOP - $10, Y2 = -$20, Y3 = -$30 so the tail collapses
    ; cleanly under any ceiling instead of clipping into roof stone.
    lda DRAW_TOP
    sec
    sbc #$10
    bcc @open_ret_near
    jsr DownstabProbeBand3
    bcc :+
@open_ret_near:
    jmp $FFC5
:
    lda #$01
    sta DOWNSTAB_ROWS
    lda DRAW_TOP
    sec
    sbc #$20
    bcc @draw_tip_y1
    jsr DownstabProbeBand3
    bcc @y2_clear
@draw_tip_y1:
    lda DRAW_TOP
    sec
    sbc #$10
    sta $00
    jsr @torso_x
    bcs @open_done
    lda $01
    clc
    adc #$04
    bcs @open_done
    sta $0223
    lda $00
    sta $0220
    lda #$0A
    sta $0221
    jsr DownstabWagAttr3
    sta $0222
    jmp $FFC5
@y2_clear:
    lda #$02
    sta DOWNSTAB_ROWS
    lda DRAW_TOP
    sec
    sbc #$30
    bcc @draw_chunk2
    jsr DownstabProbeBand3
    bcs @draw_chunk2
    inc DOWNSTAB_ROWS
@draw_chunk2:
    lda DRAW_TOP
    sec
    sbc #$10
    sta $00
    jsr @torso_x
    bcs @open_done
    lda $01
    sta $0223
    stx $0221
    lda $00
    sta $0220
    lda $0206
    sta $0222
    lda $01
    clc
    adc #$08
    bcs @open_done
    sta $0227
    sty $0225
    lda $00
    sta $0224
    lda $0206
    sta $0226
@open_done:
    jmp $FFC5

; Input: none. Output: C=0 valid ($01 = left X, X = left tile, Y = right tile).
@torso_x:
    ldx #$08
    ldy #$06
    lda DRAW_LEFT
    bit DRAW_ATTR
    bvc @tx_left
    ldx #$06
    ldy #$08
    clc
    bcc @tx_ok
@tx_left:
    clc
    adc #$08
    bcs @tx_ret
@tx_ok:
    sta $01
    clc
@tx_ret:
    rts

.segment "BANK3_SIGN"
; Input: A = screen Y of 16px band. Output: C=1 if offscreen/HUD or solid.
DownstabProbeBand3:
    cmp #$20
    bcc @band_solid
    cmp #$F0
    bcs @band_solid
    pha
    sec
    sbc #$20
    and #$F0
    sta $00
    pla
    sec
    sbc #$11
    and #$F0
    sta $01
    lda $4D
    clc
    adc #$04
    tax
    jsr DownstabBandPtr3
    jsr DownstabBandCol3
    sta $04
    txa
    ora $01
    tay
    lda ($0E),y
    sta $06
    lda $4D
    clc
    adc #$1B
    tax
    bcc @band_same
    jsr DownstabBandPtr3
@band_same:
    jsr DownstabBandCol3
    sta $05
    txa
    ora $01
    tay
    lda ($0E),y
    sta $07
    lda #$00
    sta $00
    lda #>(@after_probe - 1)
    pha
    lda #<(@after_probe - 1)
    pha
    lda #>(DownstabTerrain0 - 1)
    pha
    lda #<(DownstabTerrain0 - 1)
    pha
    jmp $FFC5
@after_probe:
    lsr $00
    rts
@band_solid:
    sec
    rts
.segment "BANK3_DLG"
DownstabBandPtr3:
    lda $3B
    adc #$00
    and #$03
    tay
    lda $EAE0,y
    sta $0E
    lda $EAE4,y
    sta $0F
    rts
DownstabBandCol3:
    txa
    lsr
    lsr
    lsr
    lsr
    tax
    ora $00
    tay
    lda ($0E),y
    rts
DownstabWagAttr3:
    lda $12
    and #$04
    beq :+
    lda #$40
:   eor DRAW_ATTR
    and #$7F
    rts

; Called from FinishSceneOam6 via Bank 3 hop. Return to Bank 6 via $FFCC.
DrawDownstabTail3:
    lda $0736
    cmp #$05
    bne :+
    lda #>(OwSparkle4-1)
    pha
    lda #<(OwSparkle4-1)
    pha
    lda #$04
    jmp $FFCC
:
    lda DRAW_FRAME
    cmp #$51
    bne @tail_early
    lda DOWNSTAB_ROWS
    cmp #$02
    bcc @tail_early
    lda $6520                 ; 2nd torso chunk Y (hidden when tucked/submerged/HUD)
    cmp #$F0
    bcs @tail_early
    sec
    sbc #$10
    bcc @tail_early
    cmp #$20
    bcc @tail_early
    sta $00
    ldx #$FC
    jsr @find_free
    bcc :+
@tail_early:
    jmp @tail_ret
:
    lda DOWNSTAB_ROWS
    cmp #$02
    beq @tip_at_00
    lda $00
    sta $6500,x
    lda $6521
    sta $6501,x
    lda $6522
    sta $6502,x
    lda $6523
    sta $6503,x
    lda $6524
    cmp #$F0
    bcs @tip
    jsr @next_free
    bcs @tail_ret
    lda $00
    sta $6500,x
    lda $6525
    sta $6501,x
    lda $6522
    sta $6502,x
    lda $6527
    sta $6503,x
@tip:
    lda $00
    sec
    sbc #$10
    bcc @tail_ret
    cmp #$20
    bcc @tail_ret
    sta $00
    jsr @next_free
    bcs @tail_ret
@tip_at_00:
    lda $6523
    clc
    adc #$04
    bcs @tail_ret
    sta $01
    lda $00
    sta $6500,x
    lda #FALL_TAIL_TILE
    sta $6501,x
    jsr DownstabWagAttr3
    sta $6502,x
    lda $01
    sta $6503,x
@tail_ret:
    jmp HopTownSmoke2

@next_free:
    txa
    sec
    sbc #$04
    bcc @none
    tax
@find_free:
    lda $6500,x
    cmp #$F0
    bcc @next_free
    clc
    rts
@none:
    sec
    rts

.segment "BANK3_DLG"
TRAIL_HISTORY = $6481       ; six lower-body Y samples, oldest overwritten next
TRAIL_INDEX   = $6487       ; 1..6, 0 means refill on the next visible frame
EncounterTorsoFrom6:
    lda $0726
    bne @reset
    lda $074C
    cmp #$03
    bcs @reset
    lda $0736
    cmp #$0B
    bne :+
    jmp EncounterDarkCheck3
:   cmp #$07                  ; lives-remaining -> gameplay transition frame
    beq @go_player
    sec
    sbc #$11                  ; $11 (lives) and $12 (lives -> North Palace)
    cmp #$02
    bcc @go_player
    ldx $076C
    cpx #$06
    beq @go_player
    cpx #$02
    bne @reset
    jmp DeathTrailPrep3
@go_player:
    jmp EncounterPlayerTrail3
@reset:
    jmp EncounterTrailReset3
.segment "BANK3_SIGN"
DeathTrailPrep3:
    lda #$00
    sta $048D
    sta $0752
    sta $0754
    sta LAVA_CONTACT
    sta $13
    beq EncounterPlayerTrail3
EncounterPlayerTrail3:
    lda #>(DrawPlayerTrailReturn6-1)
    pha
    lda #<(DrawPlayerTrailReturn6-1)
    pha
    jmp $FFC5
EncounterDarkCheck3:
    lda $0561
    cmp #$36
    bne EncounterPlayerTrail3
    lda #>(DrawDarkTrail4-1)
    pha
    lda #<(DrawDarkTrail4-1)
    pha
    lda #$04
    jmp $FFCC
.segment "TOWN"
EncounterTrailReset3:
    lda #$00
    sta TRAIL_INDEX
    jmp SwapToBank6

.segment "BANK0"
BarbaYInRange:
    cmp #$20
    bcc @out
    cmp #$F0
    bcs @out
    sta $00
    ldy DRAW_ATTR
    clc
    rts
@out:
    sec
    rts

BarbaDisplayRight:
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
    jsr BarbaYInRange
    bcs @r_mid
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
    jsr BarbaYInRange
    bcs @r_bot
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
    jsr BarbaYInRange
    bcs @r_done
    TALL_SPRITE 8, $0214, 0
    TALL_SPRITE 7, $0218, 8
    TALL_SPRITE 6, $021C, 16
@r_done:
    jmp BarbaDisplayDone

; Called from the Bank 3 hop after EncounterTorsoFrom6.
; Return through the fixed mapper routine to restore Bank 6.
DrawPlayerTrailReturn6:
    jsr DrawEncounterTorso
EncounterTorsoReturn6:
    jmp SwapToBank6

; Three frames behind Barba and a further three behind the torso. Refill
; after a transition or a displacement outside normal six-frame travel.
SampleEncounterTrail:
    ldx TRAIL_INDEX
    beq @refill
    cpx #$07
    bcs @refill
    tya
    sec
    sbc TRAIL_HISTORY-1,x
    clc
    adc #$30
    cmp #$61
    bcs @refill
    lda TRAIL_HISTORY-1,x
    sta $03
    tya
    sta TRAIL_HISTORY-1,x
    lda TrailHalfCycle-1,x
    tay
    lda TRAIL_HISTORY-1,y
    sta $00
    inx
    cpx #$07
    bne @save
    ldx #$01
@save:
    stx TRAIL_INDEX
    rts
@refill:
    jmp EncounterTrailRefill

.ifdef SAMPLED_ROAR
RoarTorsoHop:
    lda #>(RoarGemTorso-1)
    pha
    lda #<(RoarGemTorso-1)
    pha
    lda #$06
    jmp $FFCC
.endif
; Game Mode $0F (Fall in Hole Main) draws both the shadow ($91 = $3C) and
; Barba ($90 = $08) in pose $09. Extend the 2-row downward head from $EC02
; upward with two inverted $06/$08 torso chunks ($0218..$0227,y). The
; DMA shadow pass adds the third chunk and tapered tip after each actor.
BarbaFallDraw:
    jsr $EC02
    lda #$F8
    sta $0218,y
    sta $021C,y
    sta $0220,y
    sta $0224,y
    lda $0202,y
    eor #$C0
    sta $00             ; inverted torso attributes (keeps palette + priority)
    ldx #$08
    lda $0207,y         ; left-facing torso left column (head column 1)
    bit $00
    bvs @torso_x
    ldx #$06
    lda $0203,y         ; right-facing torso left column (head column 0)
@torso_x:
    sta $01
    clc
    adc #$08
    sta $02
    lda $0200,y         ; head row 0 Y
    cmp #$F0
    bcs @done
    sec
    sbc #$10
    bcc @done
    jsr @chunk          ; lower torso chunk at head_Y - $10
    sec
    sbc #$10
    bcc @done
@chunk:
    sta $0218,y
    sta $021C,y
    pha
    txa
    sta $0219,y
    eor #$0E            ; alternate $08 <-> $06 for the second column
    sta $021D,y
    lda $00
    sta $021A,y
    sta $021E,y
    lda $01
    sta $021B,y
    lda $02
    sta $021F,y
    tya
    clc
    adc #$08
    tay
    pla
@done:
    rts

; Boss-defeat shadow (LDCF5 at $DD18): $EC02 draws the native 32px shadow at
; $0250..$0264. Redraw all 9 tall-dragon sprites into $026C..$0274 + $0250..$0264
; with solid black palette 2, plus the lower-back bend and 4-sprite tail, so
; the shadow beside Barba is his full body.
BarbaBossShadow:
    stx $0753
    jsr $EC02
    lda #$F8
    sta $026C
    sta $0270
    sta $0274
    lda $C9
    and #$F0
    ora $13
    ora $048D
    beq :+
    rts
:
    lda #$02
    ldx $A0
    dex
    bne :+
    ora #$40
:   sta $02
    lda $0754
    beq @bs_native
    lda #$06
    ldx $0400
    beq @bs_pose
    lda #$07
    bne @bs_pose
@bs_native:
    lda $81
    ldx $0479
    beq @bs_pose
    cmp #$06
    bne @bs_air_atk
    lda #$0C
    bne @bs_pose
@bs_air_atk:
    cmp #$07
    bne @bs_pose
    lda #$05
@bs_pose:
    cmp #$0D
    bcc :+
    lda #$03
:   sta $00
    asl
    asl
    asl
    adc $00
    sta $03
    ldx #$08
@bs_loop:
    lda $02
    and #$40
    bne @bs_right
    txa
    bpl @bs_order
@bs_right:
    lda @bs_order_r,x
@bs_order:
    clc
    adc $03
    tay
    lda BarbaTallTiles,y
    ldy @bs_oam_off,x
    cmp #$F5
    beq @bs_skip
    sta $05
    lda $2A
    clc
    adc @bs_row_y,x
    cmp #$20
    bcc @bs_skip
    cmp #$F0
    bcs @bs_skip
    sta $0200,y
    lda $CD
    clc
    adc @bs_col_x,x
    bcs @bs_skip
    sta $0203,y
    lda $05
    sta $0201,y
    lda $02
    sta $0202,y
    bne @bs_next
@bs_skip:
    lda #$F8
    sta $0200,y
@bs_next:
    dex
    bpl @bs_loop
    lda #>(BarbaBossShadowTail2-1)
    pha
    lda #<(BarbaBossShadowTail2-1)
    pha
    lda #$02
    jmp $FFCC
@bs_done:
    rts
@bs_oam_off:
    .byte $6C, $70, $74, $50, $54, $58, $5C, $60, $64
@bs_col_x:
    .byte $00, $08, $10, $00, $08, $10, $00, $08, $10
@bs_row_y:
    .byte $F0, $F0, $F0, $00, $00, $00, $10, $10, $10
@bs_order_r:
    .byte $02, $01, $00, $05, $04, $03, $08, $07, $06

.segment "BANK2_SMOKE"
; Barba's bottom row + tail already uses 6 sprites on that scanline, leaving
; only 2 hardware slots before the NES 8-sprite limit. Stage all 6 bottom-row
; shadow sprites (bend_center, bend_back, and 4 tail pieces) and rotate which
; pair takes $0260/$0264 each frame so the full tail renders without dropping.
BarbaBossShadowTail2:
    lda $00
    cmp #$09
    bne :+
    jmp $FFC5
:
    lda $0260
    cmp #$F0
    bcc :+
    jmp $FFC5
:
    sta $05                     ; bottom-row Y
    lda $0263
    sta $06                     ; center X
    lda #$F8
    sta $025C                   ; clear both back-bottom slots; re-placed below
    sta $0264
    ; Build 6-entry table in $07..$0C (X) and use @bs_all_tiles (tiles).
    ; Entry 0: bend_center (or raw center tile if non-bend pose)
    lda $0261
    sta $0D                     ; entry 0 tile
    lda $06
    sta $07                     ; entry 0 X
    ; Entry 1: bend_back (or raw back tile if non-bend pose)
    lda #$F8
    sta $08                     ; entry 1 X ($F8 = skip)
    lda $00
    cmp #$06
    bcc @bs_bend
    cmp #$0A
    beq @bs_bend
    cmp #$0C
    bne @bs_raw_back
@bs_bend:
    lda #(TRAIL_BEND_CENTER ^ $01)
    sta $0D
    lda #(TRAIL_BEND_BACK ^ $01)
    sta $0E
    lda $06
    bit $02
    bvc @bs_bend_l
    sec
    sbc #$08
    bcc @bs_tail_x
    bcs @bs_set_back
@bs_bend_l:
    clc
    adc #$08
    bcs @bs_tail_x
@bs_set_back:
    sta $08
    bcc @bs_tail_x
    bcs @bs_tail_x
@bs_raw_back:
    ; Non-bend pose: keep raw back tile if any, or skip
    lda #$F8
    sta $08
@bs_tail_x:
    lda #$08
    bit $02
    bvc :+
    lda #$F8
:
    sta $03                     ; step (+8 or -8)
    lda $06
    bvs @bs_tail_r
    clc
    adc #$10
    bcc @bs_tail_fill
    lda #$F8
    bne @bs_tail_fill
@bs_tail_r:
    sec
    sbc #$10
    bcs @bs_tail_fill
    lda #$F8
@bs_tail_fill:
    ldy #$00
@bs_x_loop:
    sta $09,y
    cmp #$F8
    beq @bs_x_next
    clc
    adc $03
    bit $02
    bvs @bs_x_chk_r
    bcc @bs_x_next
    lda #$F8
    bne @bs_x_next
@bs_x_chk_r:
    bcs @bs_x_next
    lda #$F8
@bs_x_next:
    iny
    cpy #$04
    bne @bs_x_loop
    ; Rotate starting index by ($12 & 3) * 2 mod 6, or use a 4-phase pair table
    lda $12
    and #$03
    asl
    tax
    lda @bs_rot_a,x
    tay
    jsr @bs_write_slot_60
    inx
    lda @bs_rot_a,x
    tay
    jsr @bs_write_slot_64
    ; Write remaining 4 entries into free $0278..$02FC slots
    lda $12
    and #$03
    asl
    asl
    sta $03
    ldy #$00
    ldx #$FC
@bs_rem_loop:
    sty $04
    tya
    clc
    adc $03
    tay
    lda @bs_rem_tbl,y
    tay
    lda $07,y
    cmp #$F8
    beq @bs_rem_next
    sta $0F
@bs_find_free:
    lda $0200,x
    cmp #$F0
    bcs @bs_got_free
    dex
    dex
    dex
    dex
    cpx #$78
    bcs @bs_find_free
    jmp $FFC5
@bs_got_free:
    lda $05
    sta $0200,x
    jsr @bs_get_tile
    sta $0201,x
    lda $02
    sta $0202,x
    lda $0F
    sta $0203,x
    dex
    dex
    dex
    dex
@bs_rem_next:
    ldy $04
    iny
    cpy #$04
    bne @bs_rem_loop
@bs_tail_done:
    jmp $FFC5

@bs_write_slot_60:
    lda $07,y
    cmp #$F8
    bne :+
    sta $0260
    rts
:
    sta $0263
    lda $05
    sta $0260
    jsr @bs_get_tile
    sta $0261
    lda $02
    sta $0262
    rts

@bs_write_slot_64:
    lda $07,y
    cmp #$F8
    bne :+
    sta $0264
    rts
:
    sta $0267
    lda $05
    sta $0264
    jsr @bs_get_tile
    sta $0265
    lda $02
    sta $0266
    rts

@bs_get_tile:
    cpy #$02
    bcs :+
    lda $0D,y
    rts
:
    lda @bs_trail_tiles-2,y
    rts

@bs_rot_a:
    .byte 1, 5,  2, 3,  4, 5,  0, 1
@bs_rem_tbl:
    .byte 0, 2, 3, 4
    .byte 0, 1, 4, 5
    .byte 0, 1, 2, 3
    .byte 2, 3, 4, 5
@bs_trail_tiles:
    .byte TRAIL_TORSO_LEFT ^ $01, TRAIL_TORSO_RIGHT ^ $01, TRAIL_TIP ^ $01, TRAIL_TIP_FAR ^ $01
.segment "BANK0"

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
@center_y:
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
    jmp @center_y
@no_melee:
    lda #$F8
    sta $0480
    rts
.include "tall_layout.inc"
