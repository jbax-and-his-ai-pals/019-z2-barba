; Rauru sage basement post-Shield dialogue sequence (Bank 3, BANK3_SIGN).
; Uses WRAM $6475 (SAGE_STATE) and $6476 (SAGE_BOX):
;   SAGE_STATE:
;     0 = idle / Shield already owned before entering
;     1 = Shield not yet owned in Rauru basement; waiting for spell learn to finish
;     2 = Shield learned & unlocked; waiting for Barba to walk halfway left
;     3 = "WAIT" triggered; waiting for Barba to return to sage (persists across room exit)
;     4..7 = playing 5-box sequence ("UM..." -> ... -> "NEVERMIND...")
;     8 = sequence completed; never triggers again

SAGE_STATE = $6475
SAGE_BOX   = $6476

.segment "BANK3_PAD"
.export SageBasementTick, SageDialogCheck, SAGE_STATE, SAGE_BOX

SageBasementTick:
    lda $0707
    cmp #$01
    bne @done               ; West Hyrule towns only
    lda $056B
    bne @done               ; Town 0 (Rauru) only
    lda $0561
    cmp #$24
    bne @done               ; Rauru sage basement room ($24) only
    lda $AF,x
    bne @done               ; Ignore while burning/ash
    lda $077B
    bne @has_spell
    lda #$01
    sta SAGE_STATE
    lda #$00
    sta SAGE_BOX
@done:
    rts

@has_spell:
    lda SAGE_STATE
    beq @done
    cmp #$08
    bcs @done
    cmp #$01
    bne @check_wait
    ; Wait until spell-learn dialogue, flash, and spell menu all finish.
    lda $074C
    ora $0524
    ora $074B
    ora $DE
    bne @done
    lda #$02
    sta SAGE_STATE
    rts

@check_wait:
    cmp #$02
    bne @check_return
    lda $074C
    ora $0524
    ora $DE
    bne @done
    lda $3B                 ; Page 0 or page 1 X <= $40 (past halfway toward the left exit)
    beq @trigger_wait
    cmp #$01
    bne @done
    lda $4D
    cmp #$41
    bcs @done
@trigger_wait:
    lda #$01
    sta SAGE_BOX
    lda #$03
    sta SAGE_STATE
    bne @start_box

@check_return:
    cmp #$03
    bne @advance_seq
    lda $074C
    ora $0524
    ora $05C3,x
    ora $DE
    bne @done
    lda $0479
    bne @done               ; Wait until grounded
    lda $3B
    cmp $3C,x
    bne @done
    lda $4E,x
    sec
    sbc $4D
    clc
    adc #$28
    cmp #$50
    bcs @done
    lda #$02
    sta SAGE_BOX
    lda #$04
    sta SAGE_STATE
    bne @start_box

@advance_seq:
    ; SAGE_STATE is 4..7 while boxes 2..5 are open. When the current box closes,
    ; open the next box (3..6) and advance SAGE_STATE (5..8).
    lda $074C
    ora $0524
    ora $05C3,x
    beq :+
    rts
:
    lda SAGE_STATE
    clc
    adc #$01
    sta SAGE_STATE
    sec
    sbc #$02
    sta SAGE_BOX
@start_box:
    lda #$02
    sta $074C               ; Dialog Type = Talking
    sta $DE                 ; Lock movement
    inc $05C3,x
    lda #$00
    sta $0400
    lda #$03
    sta $80
    lda $29
    and #$F0
    sta $29
    stx $048B
    lda #$01
    sta $05A5,x             ; Prevent native L97A9 auto-talk on re-entry
    rts

SageDialogCheck:
    ldy SAGE_BOX
    beq @native_wise
    lda #$00
    sta SAGE_BOX
    lda #$01
    sta $048C               ; Skip Wise Man spell-learn fanfare/menu on box close
    dey
    tya
    asl
    tay
    lda SageDialogPointers,y
    pha
    lda SageDialogPointers+1,y
    tay
    pla
    jmp TownSetNpcDialog
@native_wise:
    ldy $05
    beq @native_index
    lda #$08
    jsr LoadTownDlg3
    jmp TownSetArcadeBuf
@native_index:
    jmp TownNativeIndex

SageDialogPointers:
    .word SageWaitText, SageUmText, SageThinkText, SageDragonText, SageUmText, SageNevermindText

SageWaitText:
    TownLine "WAIT.", $FF
SageUmText:
    TownLine "UM...", $FF
SageThinkText:
    TownLine "DO YOU THINK", $FD
    TownLine "A SAGE...", $FF
SageDragonText:
    TownLine "AND A FIRE", $FD
    TownLine "DRAGON...", $FF
SageNevermindText:
    TownLine "OH... NEVER", $FD
    TownLine "MIND...", $FF
