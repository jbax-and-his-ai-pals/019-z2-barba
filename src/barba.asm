; Original Barba Edition routines. CPU addresses refer to the guarded source ROM.
.setcpu "6502"
.export BarbaOverworld, BarbaDisplay, BarbaHitbox, BarbaUpdate, BarbaInferno
.export LavaSurface, HitboxGateway

ROAR_TIMER = $05F0 ; cleared by the original $0500..$05FF reset loop; no original references

.segment "BANK0"

; Replaces the overworld renderer's LDX #$0E / LDY #$00 pair.
; Two even-numbered 8x16 tiles use the dedicated sprite pattern bank.
BarbaOverworld:
    ldx $0562
    lda OverworldBase,x
    pha
    lda $07A9
    beq @walking
    lda $12
    bne @animate
@walking:
    lda $7D
@animate:
    and #$08
    lsr
    sta $00
    pla
    clc
    adc $00
    sta $0201
    clc
    adc #$02
    sta $0205
    lda #$00
    sta $0202
    sta $0206
    ldx #$0E
    ldy #$00
    rts
OverworldBase:
    .byte 0, 0, 8, 0, 16, 0, 0, 0, 24

; Called through a fixed-bank gateway while enemies' PRG bank is mapped.
; Preserve the original vertical thrust collision shape and damage rules.
; Horizontal flame: 16x10 pixels, clipped at the screen edge.
BarbaHitbox:
    lda $80
    cmp #$08
    beq @vertical
    cmp #$09
    beq @vertical
    lda #$10
    sta $02
    lda $047E
    sec
    sbc #$08
    bcs @horizontal_x
    clc
    adc $02
    sta $02
    lda #$00
@horizontal_x:
    sta $00
    lda $0480
    clc
    adc #$03
    sta $01
    lda #$0A
    sta $03
    jmp @clip
@vertical:
    ldy #$00
    lda $047E
    cmp $CC
    bcs @offset
    iny
@offset:
    clc
    adc VerticalOffset,y
    sta $00
    lda #$0E
    sta $02
    lda $0480
    sta $01
    lda #$03
    sta $03
@clip:
    lda $00
    clc
    adc $02
    bcc @done
    lda $00
    eor #$FF
    sta $02
@done:
    rts
VerticalOffset:
    .byte $F8, $02

BarbaInferno:
    lda #$30
    sta ROAR_TIMER
    jmp $91E6 ; original Thunder effect, including Thunderbird interaction

; Update mouth-anchored breath and diagonal full-life volleys (breath.inc).
; The short roar borrows only noise,
; leaving both pulse melodies and triangle intact. Last frame mutes the noise
; override; the game's audio driver resumes control on the following frame.
BarbaUpdate:
    jsr BarbaProjectiles
    lda ROAR_TIMER
    beq @done
    dec ROAR_TIMER
    lda ROAR_TIMER
    lsr
    lsr
    tax
    lda RoarVolume,x
    sta $400C
    lda RoarPitch,x
    sta $400E
    lda #$08
    sta $400F
@done:
    rts
RoarVolume:
    .byte $30,$32,$34,$35,$36,$38,$39,$3A,$3C,$3D,$3F,$3B
RoarPitch:
    .byte $0F,$0F,$0E,$0F,$0D,$0F,$0E,$0C,$0F,$0D,$0B,$0E

.include "breath.inc"
.include "tall_player.inc"

.segment "LAVA"
; Only palace groups use this new path. Water outside palaces retains its
; exact original death state. Below-collision lets normal landing/jump code
; snap to the lava surface, preventing a fall below the level.
LavaSurface:
    lda $0707
    cmp #$03
    bcc @water
    lda $A7
    ora #$04
    sta $A7
    jmp $E12B
@water:
    lda #$01
    sta $E9
    lda #$10
    sta $050C
    inc $B5
    rts

.segment "GATEWAY"
; Swap helpers preserve X/Y. Return with the original area bank mapped.
HitboxGateway:
    jsr $FFC5
    jsr BarbaHitbox
    jmp $FFC9

.segment "TERRAIN"
; All four corner tiles are collected before swapping. The area's native
; predicate only changes A/Y, allowing one bank round-trip for the whole head.
TerrainBatch:
    jsr $FFC9
    ldx #$03
@corner:
    lda $04,x
    jsr $850C
    bcs @result
    dex
    bpl @corner
@result:
    php
    jsr $FFC5
    plp
    rts
