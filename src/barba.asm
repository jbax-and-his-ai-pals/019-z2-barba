; Original Barba Edition routines. CPU addresses refer to the guarded source ROM.
.setcpu "6502"
.export BarbaOverworld, BarbaOverworldA, BarbaDisplay, BarbaUpdate, BarbaInferno, ThunderHit
.export OwTerrainPal0
.export LavaSurface, LavaLinkPlayerUpdate
.export EnemyFireGateway, ShieldFireGateway, ShieldReboundGateway, LagNmiInBank6, DmcPadRetry0

ROAR_TIMER = $05F0 ; cleared by the original $0500..$05FF reset loop; no original references
.ifdef SAMPLED_ROAR
ROAR_REQUEST = $05EE ; 7 playing, 6 full pending, 5 injury tail, 4 victory drain/done, 3 raised head, 2 hurt, 1 item, 0 shaft playback or Game Over delay
ITEM_HOLD = $64D4 ; 1 holding through pickup fanfare, $80 holding through roar
ROAR_COOLDOWN = $05EF ; start timer; drives injury pitch tail, attacks never roar
.endif
LAVA_CONTACT = $05EB ; 4-frame grace timer while supported by palace lava
INFERNO_TIMER = $6470 ; multi-wave Inferno firestorm countdown
OW_FIRE_TIMER = $6471 ; overworld flame breath sprite timer
OW_FIRE_DIR = $6472 ; overworld flame facing direction ($0562)
INFERNO_AIM = $6473 ; nonzero during Inferno wave emission (dir | volley flags)
LAIR_CONTROL_LOCK = 2 ; $0728 during the entrance, then 1 until the boss key
LAIR_SHAKE_X = $64FA   ; signed display scroll offset during the Lava Link entrance roar

.segment "BANK0"

; Replaces the overworld renderer's LDX #$0E / LDY #$00 pair.
; Two even-numbered 8x16 tiles use the dedicated sprite pattern bank.
BarbaOverworld:
    lda #>(BarbaOverworld2 - 1)
    pha
    lda #<(BarbaOverworld2 - 1)
    pha
    lda #$02
    jmp $FFCC

.segment "BANK2_SMOKE"
BarbaOverworld2:
    lda $0562
    jsr OwDirIdx2
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
    adc #$02
    sta $0205
    ldy #$00
    sty $0202
    sty $0206
    lda OW_FIRE_TIMER
    beq OwOverworldDone2
    dec OW_FIRE_TIMER
    bne :+
    lda #$F8
    sta $02FC
OwOverworldDone2:
    ldx #$0E
    jmp $FFC5
:
    jmp OwDrawFlame2

.segment "BANK2_CAVE"
OwDrawFlame2:
    lda OW_FIRE_DIR
    jsr OwDirIdx2
    lda OwFlameY,x
    sta $02FC
    lda OwFlameX,x
    sta $02FF
    lda OW_FIRE_TIMER
    and #$04
    lsr
    ora #$60
    sta $02FD
    sty $02FE           ; overworld Sprite Palette 0 ($16/$27/$30 fiery red/orange/white)
    jmp OwOverworldDone2
OwDirIdx2:
    ldx #$FF
:
    inx
    lsr
    bne :-
    rts
OverworldBase:
    .byte 0, 8, 16, 24
OwFlameX:
    .byte $94, $74, $84, $84
OwFlameY:
    .byte $6D, $6D, $7D, $5D

.segment "BANK0"

; Replaces LDA $87E3,X in bank 0's overworld attribute builders.
; West Hyrule ($0706=0) renders terrain $0A (Saria's foul river) with
; green palette 0 instead of East Hyrule's lava palette 1.
OwTerrainPal0:
    lda $87E3,x
    cpx #$0A
    bne @done
    ldx $0706
    bne @done
    txa                 ; A = 0 (green palette 0)
@done:
    rts

; Overworld B-button handler at $8518 (entered after $8512 verifies $F5 & $40 != 0):
; - B button: Dragon fire on Forest ($06), Town ($00), Palace ($02), or when no Flute ($0789==0);
;             otherwise plays Flute ($851D) on Spider/open ground when Flute is owned.
BarbaOverworldA:
BarbaOverworldB:
    jmp BarbaOverworldB_OW
BurnFireFx0:
    lda #$18
    sta OW_FIRE_TIMER
    lda $0562
    sta OW_FIRE_DIR
    lda $ED
    ora #$40            ; Barba fireball/roar SFX
    sta $ED
    rts
BurnAbort0:
    lda #$00
    sta $0301
    lda #$FF
    sta $0302
    rts
BurnAttrHop0:
    lda #>(OwAttrUpdate4 - 1)
    pha
    lda #<(OwAttrUpdate4 - 1)
    pha
    lda #$04
    jmp $FFCC
BurnAfterE024_0:
    lda $75             ; facing map Y (set by $84BF overworld2)
    sta $01
    lda $76             ; facing map X
    jsr $8A0D           ; resolve ($0E),y, $00, $03, $04 for facing tile ($76, $75)
    beq @kasuto_done    ; $DFD2 just revealed Hidden Kasuto ($00) -- keep Town
    jmp BarbaBurnTile0
@kasuto_done:
    rts

.segment "BANK0_OW"
BarbaOverworldB_OW:
    lda $0563
    beq @fire_react     ; Town ($00)
    cmp #$06            ; Forest
    beq @fire_burn
    cmp #$02            ; Palace
    beq @fire_react
    cmp #$0B            ; Mountain
    bne @not_mtn
    lda $07A0           ; NG+ active?
    bne @fire_burn
@not_mtn:
    lda $0789           ; Have Flute?
    beq @fire_fx_only
    jmp $851D           ; play Flute
@fire_fx_only:
    jmp BurnFireFx0
@fire_react:
    lda #$04            ; magic/rumble reaction SFX
    sta $EC
    jmp BurnFireFx0
@fire_burn:
    jsr BurnFireFx0
    jsr $E024           ; queue PPU macro ($6C plains) & set $00/$01/$7D=0
    jsr $DFD2           ; vanilla check (reveals Hidden Kasuto if Region 2, $3E, $33)
    jmp BurnAfterE024_0

.segment "BANK0"
BarbaInferno:
.ifdef SAMPLED_ROAR
    lda ROAR_REQUEST
    ora #$40
    sta ROAR_REQUEST
.endif
    lda #$31
    sta INFERNO_TIMER
    lda #$30
    sta ROAR_TIMER
    jmp $91E6 ; original Thunder effect, including Thunderbird interaction

; $D4F3: suspend player physics while the entrance runs. The rest of
; the frame still updates Lava Link, the roar, camera shake and rendering.
LavaLinkPlayerUpdate:
    lda $0728
    cmp #LAIR_CONTROL_LOCK
    bne @native
    jsr LavaLinkRoom
    bne @native
    lda #0
    sta $14             ; no player delta for the side-view scroll update
    rts
@native:
    jmp $903A

; Other bosses also use nonzero values in the native scroll lock.
LavaLinkRoom:
    lda $056B
    cmp #6
    bne @done
    lda $0561
    cmp #$3A
@done:
    rts

DmcPadRetry0:
    lda $F5
    sta $00
    jsr $D367
    lda $F5
    cmp $00
    bne DmcPadRetry0
    rts

; Hooked at $922A (JSR $E726 inside Thunder_Spell $91E6).
; Thunderbird ($22, the only enemy where $9228 sets Y = 1) needs its bank-5
; boss-death state ($6E3F = $FF, $B6,x = 1, $0504,x = $FF, $040E,x = $7F from $A3E1)
; when killed by Thunder, instead of generic death ($B6,x = 2) before $A359 runs.
ThunderHit:
    cpy #$01
    bne @normal
    bit $6E3F
    bmi @done
    jsr $E726
    lda #$01
    cmp $B6,x
    beq @done
    sta $B6,x
    lda #$FF
    sta $6E3F
    sta $0504,x
    lsr
    sta $040E,x
@done:
    rts
@normal:
    jmp $E726

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
    lsr LAVA_CONTACT
@roar:
.ifdef SAMPLED_ROAR
    lda #$00
    sta ROAR_TIMER
    rts

; Fixed-bank player injury hook preserves the native recoil argument.
BarbaHurtRoar:
    lda ROAR_REQUEST
    ora #$04
    sta ROAR_REQUEST
    lda #$01
    sta $00
    rts

.else
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
.endif

.include "breath.inc"
.include "extra_fire.inc"
.include "shield_rebound.inc"
.include "tall_player.inc"
.include "stomp.inc"
.include "blocks.inc"
.include "shouts.inc"
.include "town.inc"
.include "sign.inc"
.include "sage_basement.inc"
.include "ow_burn.inc"
.include "town_smoke.inc"
.include "title_lava.inc"
.include "ow_foliage.inc"
.include "scales.inc"
.include "splat.inc"
.include "farcall.inc"
.include "ra_telemetry.inc"
.include "scanline_irq.inc"
.include "cave_light.inc"
.include "death_display.inc"
.include "ending_fire.inc"
.include "palace_roar.inc"
.include "boss_meter.inc"
.ifdef SOULS_BOSS_METER
.include "souls_boss_bar.inc"
.endif
.include "ow_sparkle.inc"
.include "arcade_spells.inc"
.ifdef SAMPLED_ROAR
.include "sampled_roar.inc"
.endif

.segment "LAVA"
; Side-view encounters ($0707=0) and palaces ($0707>=3) use this surface path.
; Town groups ($0707=1,2) retain the original death state. Below-collision lets
; normal landing/jump code snap to the surface, preventing a fall below the level.
LavaSurface:
    jsr FarCall0
    .word LavaSurfaceBody
    bcc LavaRts
    jmp $E12B
LavaRts:
    rts

ShieldReboundGateway:
    jsr FarCall0
    .word ShieldReboundImpact
    bcc LavaRts
    pla
    pla
    jmp $E6F3

SwapToBank6:
    lda #$06
    jmp $FFCC

.segment "GATEWAY"
; Run native slot 0/1 collision in Bank 7 (0 bank switches); only swap to Bank 0
; for ExtraCollision when the enemy is active/hittable and EXTRA_LIVE != 0.
EnemyFireGateway:
    lda $B6,x
    cmp #$01
    bne @done
    lda $040E,x
    bne @done
    jsr $E496
    lda EXTRA_LIVE
    beq @done
    jsr $FFC5
    jsr BarbaEnemyFireOnly
    jmp $FFC9
@done:
    rts
ShieldFireGatewaySlow:
    jsr $FFC5
    jsr BarbaShieldFire
    jmp $FFC9

.segment "LAG_RET"
LagNmiReturn:
    pla
    sta $64D5
    sta $8000
    rts

.segment "TERRAIN"
; All four corner tiles are collected before swapping. The area's native
; predicate only changes A/Y, allowing one bank round-trip for the whole head.
TerrainBatch:
    jsr $FFC9
    ldx #$03
@corner:
    lda $04,x
    jsr $850C
    bcs NativeReturn0
    dex
    bpl @corner
NativeReturn0:
    php
    jsr $FFC5
    plp
    rts
ShieldFireGateway:
    lda EXTRA_LIVE
    beq @native
    jsr ShieldFireGatewaySlow
@native:
    jmp $E5BA

.segment "PALACE_SHAKE"
; Lag-frame NMI: run audio in bank 6, then restore the interrupted PRG bank
; (bank 0 or 1 by $8506 fingerprint, otherwise the area bank in $0769)
; and the interrupted MMC3 bank-select register ($64D5 -> $8000).
LagNmiInBank6:
.ifdef SOULS_BOSS_METER
    jsr LagSoulsBg6
.else
    jsr SplatSoundDriver6
.endif
    pla
    ldx #$00
    cmp #$F0
    beq @bank
    inx
    cmp #$7D
    beq @bank
    ldx $0769
@bank:
    pla
    tay
    lda #>($C070-1)
    pha
    lda #<($C070-1)
    pha
    tya
    pha
    lda #>(LagNmiReturn-1)
    pha
    lda #<(LagNmiReturn-1)
    pha
    txa
    jmp $FFCC

.include "dark_barba.inc"
.include "geldarm.inc"
.ifdef WALDO_PORTAL
.include "waldo_portal.inc"
.endif

.include "encounter_trail.inc"
