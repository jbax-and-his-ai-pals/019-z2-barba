; Burned town signs (producer, 2026-11-16). Bank 3, vanilla pad bank3_UNUSED_9D0A.
; BarbaTownBurn (bank 0) sets SIGN_PENDING when a fireball scorches a sign board
; metatile ($E3). The sign's invisible talk actor ($22) copies it into its own
; $04A0,x: native spawn ($D6A8) clears that byte on every room load and no bank
; 0/3/7 code reads it, so the mark survives dialogue (which clears the scorch
; ring) and resets when the room reloads, just like the char tiles.
; $04A0,x: 0 = intact sign, 1..SIGN_LINES = next burned line to show.
.segment "BANK3_SIGN"
.export SignUpdate, SignDialog, SariaSignText

; Routine pointer for actors $21 and $22 (both were $9ABD, the native
; talk/offscreen routine). A 2026-11-16 census of world-1 town rooms found every
; sign room has exactly one reader: $22 (rooms $00-$06, $08, $0C, $0E, $12) or
; $21 ($09, $0B, $0F, $11, $17). The quest $21 triggers (Mirror/Fountain rooms
; $0D, $1A, $1E) have no sign, so a board burn can never mark them.
SignUpdate:
    lda SIGN_PENDING
    beq @native
    lda $0561
    cmp SCORCH_ROOM
    bne @native             ; stale from another room: the ring clears it
    lda #$00
    sta SIGN_PENDING
    lda $04A0,x
    bne @native             ; already burned: keep the rotation
    lda $12                 ; first read: random line 1..SIGN_LINES from the
@mod:                       ; frame counter at burn time (once per burn, <=42 loops)
    cmp #SIGN_LINES
    bcc :+
    sbc #SIGN_LINES         ; carry is set here
    bcs @mod
:
    adc #$01                ; carry clear: 0..5 -> 1..6
    sta $04A0,x
@native:
    jmp $9ABD

; Jumped to from TownOriginalDialog with X = talking actor and the native
; dialogue index on the stack. Not a burned sign: resume TownNativeDialog
; (which pulls the index). Burned: drop the index, advance the actor's line
; and show it through TownSetNpcDialog.
SignDialog:
    lda $A1,x
    cmp #$21                ; sign readers are $22 or (5 West rooms) $21
    bcc @no
    cmp #$23
    bcs @no
    ldy $04A0,x
    beq @no
    pla
    tya
    cmp #SIGN_LINES         ; after the last line, wrap to line 1
    bcc :+
    lda #$00
:
    clc
    adc #$01
    sta $04A0,x
    dey
    tya
    asl
    tay
    lda SignPointers,y
    pha
    lda SignPointers+1,y
    tay
    pla
    jmp TownSetNpcDialog
@no:
    jsr TownIsError
    bcc @native
    lda $AF,x
    cmp #$A0
    bcc @native
    pla
    lda #<ErrorAshText
    ldy #>ErrorAshText
    jmp TownSetNpcDialog
@native:
    jmp TownNativeDialog

SIGN_LINES = 6
SignPointers:
    .word SignChar, SignBurned, SignAshPile, SignWhatLeft, SignDidThat, SignWasSign
SignChar:
    TownLine "CHARRED.", $FD
    TownLine "YOU CAN'T", $FD
    TownLine "READ IT.", $FF
SignBurned:
    TownLine "WELL. YOU", $FD
    TownLine "BURNED IT.", $FF
SignAshPile:
    TownLine "WELCOME TO", $FD
    TownLine "THIS ASH", $FD
    TownLine "PILE.", $FF
SignWhatLeft:
    TownLine "WELCOME TO", $FD
    TownLine "WHAT IS", $FD
    TownLine "LEFT.", $FF
SignDidThat:
    TownLine "SIGN IS", $FD
    TownLine "ASH. YOU", $FD
    TownLine "DID THAT.", $FF
SignWasSign:
    TownLine "THIS WAS", $FD
    TownLine "A SIGN.", $FF

; Error of Ruto: world 1 ($0707=1), town 1 ($056B=1), actor $0E.
TownIsError:
    lda $0707
    cmp #$01
    bne @no
    lda $056B
    cmp #$01
    bne @no
    lda $A1,x
    cmp #$0E
    bne @no
    sec
    rts
@no:
    clc
    rts

; Keep Error's ash pile persistent in the room and allow talking to it.
ErrorAshCheck:
    jsr TownIsError
    bcc @not_error
    lda $05C3,x
    bne @keep
    lda $F5
    and #$40
    bne @try_talk
    lda TALK_LATCH
    bne @keep
    lda $F7
    and #$08
    beq @keep
@try_talk:
    jsr TownCanTalk
    bcc @keep
    stx $048B
    lda #$01
    sta TALK_LATCH
    jsr $9A33
@keep:
    sec
    rts
@not_error:
    clc
    rts

ErrorAshText:
    TownLine "I AM", $FD
    TownLine "ASH PILE.", $FF

.segment "BANK3_PAD"
SariaSignText:
    TownLine "WELCOME TO", $FD
    TownLine "SARIA.", $FD
    TownLine "DON'T DRINK", $FD
    TownLine "THE WATER.", $FF
