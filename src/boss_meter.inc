; Draw from the enemy record after all native OAM writes, including Barba's
; third head column at $02C4 and the enemies' rotating sprite assignments.
.segment "PALACE_ROAR"
DrawBossMeter4:
    jsr DrawBossPips
    lda #$06
    jmp $FFCC

DrawBossPips:
    lda $0736
    cmp #$0B                 ; side-view gameplay
    bne @done
    lda $056B
    sec
    sbc #1
    cmp #7
    bcs @done
    tay
    lda $0561
    cmp BossMeterRoom,y
    beq @room
    cmp #$36                 ; Dark Barba, second Great Palace fight
    bne @done
    cpy #6
    bne @done
    lda $63
    cmp #3
    bne @done
    lda $0505                ; wait until the entrance pose finishes
    bne @done
    iny
@room:
    lda $0707
    cmp BossMeterWorld,y
    bne @done
    cpy #5
    bne :+
    jsr RemapLavaLinkOam4
:
    cpy #4
    bne :+
    ; The final swing can remain in OAM on the frame HP reaches zero.
    jsr PrioritizeGoomaWeapon
:
    ldx #5
@enemy:
    lda $B6,x
    cmp #1
    bne @next
    lda $A1,x
    cmp BossMeterEnemy,y
    bne @other
    cpy #2
    bne @found
    lda $81,x                ; Rebonack's riderless horse remains in the room
    beq @found
    bne @next
@other:
    cpy #2
    bne @next
    cmp #$0A                 ; dismounted Rebonack
    beq @found
@next:
    dex
    bpl @enemy
@done:
    rts
@found:
    cpy #5
    bne :+
    lda $AF,x
    bpl @done                ; Lava Link has yet to start rising
:
    cpy #6
    bne :+
    lda $0504,x
    bne @done                ; Thunderbird's entrance timer
:
    lda $C2,x
    beq @done
    cmp BossMeterMaxHP,y
    bcc :+
    bne @done                ; death can leave an unsigned HP underflow
:
    ; Round up so a living boss always has at least one filled pip.
    ldx #0
    clc
@divide:
    inx
    sbc BossMeterHPPerPip,y
    bcs @divide
    stx $00
    ; Use the earliest free sprites. Keep the gameplay sprites in their
    ; original order and leave room for two 8x16 cells per meter scanline.
    ldx #0
    cpy #4
    bne :+
    ldx #$4C                 ; keep Gooma's ball, links and fireballs ahead
:
    ldy #$70
@slot:
    lda $6500,x
    cmp #$F0
    bcc @advance
    tya
    sta $6500,x
    lda #$71                 ; empty pip, rebased to sprite pattern table
    dec $00
    bmi :+
    lda #$6F
:
    sta $6501,x
    lda #1
    sta $6502,x
    lda #$10
    sta $6503,x
    tya
    sec
    sbc #8
    tay
    cmp #$30
    beq @done
@advance:
    inx
    inx
    inx
    inx
    bne @slot
    rts

BossMeterRoom:     .byte $0D, $22, $0E, $1C, $29, $3A, $35, $36
BossMeterWorld:    .byte    3,   3,   4,   4,   3,   4,   5,   5
BossMeterEnemy:    .byte $20, $21, $20, $22, $21, $21, $22, $23
BossMeterHPPerPip: .byte    4,   6,   9,   6,  18,  24,  24,   1
BossMeterMaxHP:    .byte   32,  48,  72,  48, 144, 192, 192,   8

; Keep Gooma's ball and links ahead of the fireballs and the boss body.
PrioritizeGoomaWeapon:
    lda $65A0
    cmp #$F0
    bcs @done
    ldx #$0F
@swap:
    lda $6528,x
    pha
    lda $65A0,x
    sta $6528,x
    pla
    sta $65A0,x
    dex
    bpl @swap
@done:
    rts

; Move Lava Link's sprites from BG bank 25 ($0000) to R5 bank 154 ($1000) so
; sprite fetches stay on A12=1 and never clock the MMC3 scanline counter early.
RemapLavaLinkOam4:
    tya
    pha
    lda #$05
    sta $64D5
    sta $8000
    lda #154
    sta $8001
    ldx #$00
@oam:
    lda $6500,x
    cmp #$F0
    bcs @next
    lda $6501,x
    lsr
    bcs @next
    asl
    ldy #15
@find:
    cmp LavaLinkSrcTile,y
    beq @hit
    dey
    bpl @find
    bmi @next
@hit:
    lda LavaLinkDstTile,y
    sta $6501,x
@next:
    inx
    inx
    inx
    inx
    bne @oam
    pla
    tay
    rts

LavaLinkSrcTile:
    .byte $14, $16, $18, $1A, $1C, $22, $24, $26, $28, $2A, $2C, $2E, $A0, $A2, $52, $3C
LavaLinkDstTile:
    .byte $C1, $C3, $C5, $C7, $C9, $CB, $CD, $CF, $D1, $D3, $D5, $D7, $D9, $DB, $DD, $DF
