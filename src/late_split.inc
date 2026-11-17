; Lag-frame status-bar fix (bank 3 pad, reached from the NMI tail).
;
; The native side-view frame writes the status-bar scroll at NMI entry, waits
; for sprite 0, writes the playfield scroll ($FD / $0746) and then runs all game
; logic. When that logic overruns into the next vblank, that vblank's NMI is
; lost and the PPU draws the whole next frame with the playfield scroll still
; latched, so the status bar slides sideways by the camera position.
;
; tools/build.py rewrites the NMI tail ($C19D) to test the vblank flag. On an
; overrun it pushes the $8506 bank fingerprint and enters here through the
; 6-byte trampoline at $C09F (JSR $FFCC with A=3, JMP LateSplit). We are then
; still inside the vblank we missed: redo the native split for this frame
; (status bar at scroll 0, wait for sprite 0, playfield scroll as $D4B7-$D4CB),
; then restore the interrupted bank and return to the native tail ($C1AB),
; which re-enables NMI. Game logic, RNG and OAM are untouched; the lag frame
; becomes a clean repeat of the previous picture.
.export LateSplit
.segment "BANK3_SIGN"
LateSplit:
    bit $2002
    bvc @restore            ; no sprite-0 hit last frame: no split to redo
    lda $0736
    cmp #$0B
    bne @restore            ; side view only
    lda $074C
    cmp #$02
    bcs @restore            ; native split is skipped for dialogue
    lda $0726
    bne @restore            ; black transition
    lda $FF
    and #$FC                ; status-bar nametable 0; bit 7 (NMI) stays clear
    sta $2000
    lda #$00
    sta $2005               ; write latch was reset by BIT $2002 above
    sta $2005
@clear:
    bit $2002               ; previous frame's hit stays set until pre-render
    bvs @clear
    ldx #$00
    ldy #$06                ; ~17k-cycle timeout (about 150 scanlines)
@wait:
    bit $2002
    bvs @split
    dex
    bne @wait
    dey
    bne @wait
@split:
    lda $FF
    ora $0746
    sta $FF
    ldx $FD
    ldy #$10
@delay:
    dey
    bne @delay
    sta $2000
    stx $2005
    sty $2005
@restore:
    pla                     ; $8506 fingerprint of the interrupted bank
    ldy #$07
@find:
    cmp LateSplitBanks,y
    beq @found
    dey
    bpl @find
    iny                     ; unreachable (build guards fingerprints): bank 0
@found:
    lda #>($C1AB-1)
    pha
    lda #<($C1AB-1)
    pha
    tya
    jmp $FFCC
LateSplitBanks:
    .byte $F0,$7D,$60,$2E,$91,$2F,$00,$C9
