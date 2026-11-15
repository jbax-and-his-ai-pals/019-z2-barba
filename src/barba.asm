; Original Barba Edition routines. CPU addresses refer to the guarded source ROM.
.setcpu "6502"
.export BarbaOverworld, BarbaDisplay, BarbaUpdate, BarbaInferno
.export LavaSurface
.export EnemyFireGateway, ShieldFireGateway

ROAR_TIMER = $05F0 ; cleared by the original $0500..$05FF reset loop; no original references
LAVA_CONTACT = $05EB ; 4-frame grace timer while supported by palace lava

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
    jsr BarbaShouts
    lda LAVA_CONTACT
    beq @roar
    dec LAVA_CONTACT
    lda $0479
    beq @roar
    lda $057D
    bpl @roar
    cmp #$FB
    bcc @roar
    lda #$FA
    sta $057D
@roar:
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
.include "extra_fire.inc"
.include "tall_player.inc"
.include "stomp.inc"
.include "blocks.inc"
.include "shouts.inc"
.include "town.inc"
.include "farcall.inc"

.segment "LAVA"
; Only palace groups use this new path. Water outside palaces retains its
; exact original death state. Below-collision lets normal landing/jump code
; snap to the lava surface, preventing a fall below the level.
LavaSurface:
    jsr FarCall0
    .word LavaSurfaceBody
    bcc @water
    jmp $E12B
@water:
    rts

; Execute the original shield handler with its first three bytes restored.
; Player melee stays disabled, so its melee-only stack escape is unreachable.
NativeShieldFire:
    jsr $FFC9
    lda $C8
    asl
    jsr $E61A
    jmp NativeReturn0

.segment "GATEWAY"
; Fast path: with no backed shot alive, run the original E48B test in place
; (no bank switches). Original bytes at E48B were LDA $B6,X / CMP #$01;
; E48F continues with BNE/rts and the native two-slot loop.
EnemyFireGateway:
    lda EXTRA_LIVE
    bne @slow
    lda $B6,x
    cmp #$01
    jmp $E48F
@slow:
    jsr $FFC5
    jsr BarbaEnemyFire
    jmp $FFC9
ShieldFireGateway:
    jsr $FFC5
    jsr BarbaShieldFire
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

; Caller (BarbaEnemyFire, bank 0) has already required $B6,X = 1.
NativeEnemyFire:
    jsr $FFC9
    jsr $E491
NativeReturn0:
    php
    jsr $FFC5
    plp
    rts
