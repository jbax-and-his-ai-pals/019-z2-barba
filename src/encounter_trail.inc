; Bank 0 samples the body motion. Bank 1 borrows the existing Geldarm pad
; for the shadow OAM art and slot decisions.
.segment "BANK0"

ResetEncounterTrail:
    lda #$00
    sta TRAIL_INDEX
    rts

; Sample torso and tip motion for the bank-1 shadow OAM pass.
.export DrawEncounterTorso
DrawEncounterTorso:
    lda $13                   ; skip the native fairy/transform draw paths
    ora $048D
    bne ResetEncounterTrail
    lda $80
    cmp #$0C
    bcs ResetEncounterTrail
    lda DRAW_FRAME
    cmp #$51
    beq ResetEncounterTrail
    lda LAVA_CONTACT
    ora $0752
    beq @not_submerged
    ldy $0479
    beq ResetEncounterTrail
@not_submerged:
    ldy $6518                 ; center of the lower row; hidden when submerged
    cpy #$F0
    bcs ResetEncounterTrail
    jsr SampleWigglingTrail  ; $00 = torso Y, $03 = tip Y
    lda $00
    cmp #$20
    bcc @reject
    cmp #$F0
    bcs @reject
    lda $651A
    and #$DF                  ; keep the decoration visible over grass
    sta $01
    lda $651B
    bit $01
    bvs @facing_right
    clc
    adc #$10                  ; 24px after the left edge of the body
    bcc @place
@reject:
    rts
@facing_right:
    sec
    sbc #$18                  ; 16px before the left edge of the body
    bcc @reject
@place:
    cmp #$F8                  ; both columns must start within the screen
    bcs @reject
    sta $02                   ; left X
    bit $01
    bvs @tip_left
    adc #$10                  ; carry clear from CMP
    bcc @tip_x
    bcs @disable_tip
@tip_left:
    sec
    sbc #$08
    bcc @disable_tip
@tip_x:
    sta $07
    lda $03
    cmp #$20
    bcs DrawEncounterTrailSprites
@disable_tip:
    lda #$F8
    sta $03

DrawEncounterTrailSprites:
    ; Four pieces in priority order: near torso, outer torso, near tip, far
    ; tip. X in $08-$0B, Y in $0C-$0F (Y >= $F0 skips the piece).
    lda $00
    sta $0C
    sta $0D
    lda $03
    sta $0E
    sta $0F
    lda $07
    sta $0A
    lda $02
    bit $01
    bvs @torso_right
    sta $08                   ; facing left: the trail runs right
    clc
    adc #$08
    sta $09
    lda $07
    clc
    adc #$08                  ; far tip 8px further right
    bcc @far_x
    bcs @far_hidden
@torso_right:
    sta $09                   ; facing right: tiles mirror, near is on the right
    clc
    adc #$08
    sta $08
    lda $07
    sec
    sbc #$08
    bcs @far_x
@far_hidden:
    lda #$F8
    sta $0F                   ; the far column would wrap around the screen
@far_x:
    sta $0B
    lda DRAW_FRAME
    cmp #6*9                  ; keep the compact and downward head artwork
    bcc @bend
    cmp #10*9                 ; hurt pose keeps full-height torso
    beq @bend
    cmp #12*9                 ; full-height jump
    bne @far_call
@bend:
    lda #TRAIL_BEND_CENTER
    sta $6519
    ldx #$1C                  ; back column for left-facing Barba
    bit $01
    bvc :+
    ldx #$14
:
    lda #TRAIL_BEND_BACK
    sta $6501,x
    ; Wiggle: lift the bend 1px while the delayed torso rides higher, so the
    ; curve bobs with the trail. Only upward: a downward nudge would open a
    ; blank row under the upright torso. Keep its rows separate during a
    ; shout so the elbow and upper body don't compete with the glyphs.
    lda SHOUT_WORD
    bne @seam
    lda $00
    cmp $6518
    bcs @seam
    dec $6518
    dec $6500,x
@seam:
    txa
    eor #$08                  ; the opposite column only held the old seam
    tax
    lda #$F8
    sta $6500,x
@far_call:
    lda #>(DrawEncounterTrailSprites1-1)
    pha
    lda #<(DrawEncounterTrailSprites1-1)
    pha
    lda #$01
    jmp $FFCC

.segment "BANK1"
; Sprite priority on a crowded scanline: Barba, his fireballs, projectiles
; and clouds first, then the trail, then enemies. The trail takes the first
; four enemy entries ($50-$5C). A visible occupant moves to the last free
; entry, so enemies drop (and flicker through their native rotation) before
; the tail does. With no free entry left, the remaining pieces are skipped.
TRAIL_OAM = $50
DrawEncounterTrailSprites1:
    lda #$FC
    sta $05                   ; next free-entry candidate, from the end
    ldy #$00                  ; piece
    ldx #TRAIL_OAM
@piece:
    lda $000C,y
    cmp #$F0
    bcs @next_piece
    lda $6500,x
    cmp #$F0
    bcs @write
    sty $06
    ldy $05
@find:
    cpy #TRAIL_OAM+$10
    bcc @done                 ; no room to move the occupant
    lda $6500,y
    cmp #$F0
    bcs @found
    dey
    dey
    dey
    dey
    bne @find
@found:
    lda $6500,x
    sta $6500,y
    lda $6501,x
    sta $6501,y
    lda $6502,x
    sta $6502,y
    lda $6503,x
    sta $6503,y
    dey
    dey
    dey
    dey
    sty $05
    ldy $06
@write:
    lda $000C,y
    sta $6500,x
    lda $0008,y
    sta $6503,x
    lda TrailPieceTiles,y
    sta $6501,x
    lda $01
    sta $6502,x
@next_piece:
    inx
    inx
    inx
    inx
    iny
    cpy #$04
    bne @piece
@done:
    jmp $FFC5
TrailPieceTiles:
    .byte TRAIL_TORSO_LEFT, TRAIL_TORSO_RIGHT, TRAIL_TIP, TRAIL_TIP_FAR

.segment "BANK0"
EncounterTrailRefill:
    tya
    sta $00
    sta $03
    ldx #$06
:
    sta TRAIL_HISTORY-1,x
    dex
    bne :-
    inx
    stx TRAIL_INDEX
    rts
TrailHalfCycle:
    .byte 4, 5, 6, 1, 2, 3

; The rotated trail sways vertically across the same three poses as the
; upright torso. Sample the sway so the second joint gets it later too.
SampleWigglingTrail:
    lda $6519
.ifdef SAMPLED_ROAR
    cmp #TRAIL_BEND_CENTER
    beq @refill               ; the raised-head roar draws its own floor-level bend
.endif
    cmp #TRAIL_CORRIDOR_BEND
    bne @walk
    ; The bend uses eight visible rows. The turned torso uses all sixteen,
    ; including the row at OAM Y+16 after the PPU's one-line offset.
    ; Refill from the floor so delayed samples cannot bury either piece.
    tya
    sec
    sbc #$09
    tay
@refill:
    jmp EncounterTrailRefill
@walk:
    lda $80
    cmp #$01
    beq @up
    cmp #$02
    bne @sample
    iny
    iny
    bne @sample
@up:
    dey
    dey
@sample:
    jmp SampleEncounterTrail

.segment "PALACE_ROAR"
; Dark Barba has its own lower row and palette. Fill free shadow entries
; behind the fight's actors and fireballs, using the lower row for the join.
DrawDarkTrail4:
    lda $0707
    cmp #$05
    bne @exit
    lda $A1
    cmp #$23
    bne @exit
    lda $B6
    beq @exit
    lda $6560
    cmp #$20
    bcc @exit
    cmp #$F0
    bcc @body
@exit:
    jmp @done
@body:
    sta $00
    lda $6562
    sta $01
    lda #$08
    ldy #$64
    bit $01
    bvc :+
    lda #$F8
    ldy #$5C
:
    sta $03
    lda $6563
    bvs @right
    clc
    adc #$10
    bcc @place
    bcs @done
@right:
    sec
    sbc #$10
    bcc @done
@place:
    sta $02
    lda $6561                ; bend fits the idle, walk and standing attack rows
    cmp #$0D
    beq @bend
    cmp #$17
    beq @bend
    cmp #$07
    bne @draw
@bend:
    lda #TRAIL_BEND_CENTER
    sta $6561
    lda #TRAIL_BEND_BACK
    sta $6501,y
    tya
    eor #$38                 ; $5C <-> $64
    tay
    lda #$F8
    sta $6500,y
@draw:
    ldy #$00
    ldx #$FC
@find:
    lda $6500,x
    cmp #$F0
    bcc @next
    lda $00
    sta $6500,x
    lda DarkTrailTiles,y
    sta $6501,x
    lda $01
    sta $6502,x
    lda $02
    sta $6503,x
    iny
    cpy #$04
    beq @done
    clc
    adc $03
    sta $02
    bit $01
    bvs @next_right
    bcs @done
    bcc @next
@next_right:
    bcc @done
@next:
    dex
    dex
    dex
    dex
    cpx #$78
    bcs @find
@done:
    lda #>(DrawPlayerTrailReturn6-1)
    pha
    lda #<(DrawPlayerTrailReturn6-1)
    pha
    lda #$00
    jmp $FFCC

DarkTrailTiles:
    .byte TRAIL_TORSO_LEFT, TRAIL_TORSO_RIGHT, TRAIL_TIP, TRAIL_TIP_FAR
