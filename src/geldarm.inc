; Geldarm (West Hyrule desert sand worm, enemy $20): a lethal hit no longer
; explodes it at full height. It keeps $B6 = 1 with HP 0 (the dying marker;
; spawn HP is never 0), sinks into the sand 2 px/frame while flashing and
; immune, and only then runs the native death ($E880) at ground level.
; Lives in bank 1's unused pad right after the Geldarm draw code.
GELDARM_SINK = 2

.segment "BANK1"
; Hooked at the routine entry ($9BB5: LDA $AF,X / BNE $9BEE).
GeldarmUpdate:
    lda $C2,x
    beq @dying
    lda $AF,x
    beq @move
    jmp $9BEE
@move:
    jmp $9BB9
@dying:
    lda $040E,x
    cmp #$04
    bcs @flash
    lda #$10                    ; keep flashing; nonzero also skips hit checks
    sta $040E,x
@flash:
    lda $2A,x
    clc
    adc #GELDARM_SINK
    bcs @dead
    cmp $81,x
    bcs @dead
    sta $2A,x
    jmp GeldarmHits             ; draw + checks; Link collision skipped (harmless)
@dead:
    lda $81,x
    sta $2A,x
    lda #$00
    sta $040E,x
    jmp $E880                   ; native death: explosion at the sand line

; Replaces JSR $DE40 at $9C3D (draw + projectile/sword/contact checks).
; Run it with HP parked at $7F so the native code can never kill the worm,
; then apply the damage it dealt; a lethal total starts the sink instead.
GeldarmHits:
    lda $C2,x
    pha
    lda #$7F
    sta $C2,x
    jsr $DE40
    ldx $10
    pla
    clc
    adc $C2,x                   ; old + (7F - damage) - 7F
    sec
    sbc #$7F
    beq @kill
    bcc @kill
    sta $C2,x
    rts
@kill:
    lda #$00
    sta $C2,x
    sta $AF,x
    rts
