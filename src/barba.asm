; Original Barba Edition routines. CPU addresses refer to the guarded source ROM.
.setcpu "6502"
.export BarbaOverworld, BarbaOverworldA, BarbaDisplay, BarbaUpdate, BarbaInferno, ThunderHit
.export LavaSurface
.export EnemyFireGateway, ShieldFireGateway, LagNmiBank6

ROAR_TIMER = $05F0 ; cleared by the original $0500..$05FF reset loop; no original references
.ifdef SAMPLED_ROAR
ROAR_REQUEST = $05EE ; bit 7 playing, bit 6 full pending, bit 5 injury tail, bit 4 victory draining/done, bit 3 raised head, bit 2 hurt, bit 1 item roar
ITEM_HOLD = $64D4 ; 1 holding through pickup fanfare, $80 holding through roar
ROAR_COOLDOWN = $05EF ; start timer; drives injury pitch tail, attacks never roar
.endif
LAVA_CONTACT = $05EB ; 4-frame grace timer while supported by palace lava
INFERNO_TIMER = $6470 ; multi-wave Inferno firestorm countdown
OW_FIRE_TIMER = $6471 ; overworld flame breath sprite timer
OW_FIRE_DIR = $6472 ; overworld flame facing direction ($0562)
INFERNO_AIM = $6473 ; nonzero during Inferno wave emission (dir | volley flags)

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
    adc #$02
    sta $0205
    lda #$00
    sta $0202
    sta $0206
    lda OW_FIRE_TIMER
    beq @ow_done
    dec OW_FIRE_TIMER
    bne @draw_flame
    lda #$F8
    sta $02FC
    bne @ow_done
@draw_flame:
    ldx OW_FIRE_DIR
    lda OwFlameY,x
    sta $02FC
    lda OwFlameX,x
    sta $02FF
    lda OW_FIRE_TIMER
    and #$04
    lsr
    ora #$60
    sta $02FD
    lda #$00            ; overworld Sprite Palette 0 ($16/$27/$30 fiery red/orange/white)
    sta $02FE
@ow_done:
    ldx #$0E
    ldy #$00
    rts
OverworldBase:
    .byte 0, 0, 8, 0, 16, 0, 0, 0, 24
OwFlameX:
    .byte $80, $90, $70, $80, $80, $80, $80, $80, $80
OwFlameY:
    .byte $6D, $6D, $6D, $6D, $7D, $6D, $6D, $6D, $5D

; Overworld B-button handler at $8518 (entered after $8512 verifies $F5 & $40 != 0):
; - B button: Dragon fire on Forest ($06), Town ($00), Palace ($02), or when no Flute ($0789==0);
;             otherwise plays Flute ($851D) on Spider/open ground when Flute is owned.
BarbaOverworldA:
BarbaOverworldB:
    lda $0563
    cmp #$06            ; Forest
    beq @fire_forest
    cmp #$00            ; Town
    beq @fire_react
    cmp #$02            ; Palace
    beq @fire_react
    lda $0789           ; Have Flute?
    beq @fire_fx
    jmp $851D           ; play Flute
@fire_react:
    lda #$04            ; magic/rumble reaction SFX
    sta $EC
@fire_fx:
    lda #$18
    sta OW_FIRE_TIMER
    lda $0562
    sta OW_FIRE_DIR
    lda $ED
    ora #$40            ; Barba fireball/roar SFX
    sta $ED
    rts
@fire_forest:
    jsr @fire_fx
    jsr $E024           ; queue PPU macro ($6C plains) & set $00/$01/$7D=0
    jsr $DFD2           ; vanilla check (reveals Hidden Kasuto if Region 2, $3E, $33)
    jmp BarbaSplitBurnForest

.segment "BANK0_OW"
; Split RLE run at ($0E),y for row $04 (0..$4A), 1-based X $00, run_end $03.
; Turns ONLY the single facing forest tile into Desert ($04) so neighboring trees survive battles/scrolling.
BarbaSplitBurnForest:
    lda ($0E),y
    cmp #$06
    bne @check_multi
    lda #$04            ; single-tile run ($06): no shift needed
    sta ($0E),y
@done:
    rts
@check_multi:
    and #$0F
    cmp #$06
    bne @done
@split:
    tya
    pha                 ; save Y (byte index in row)
    lda ($0E),y
    lsr
    lsr
    lsr
    lsr                 ; A = run_len - 1 (1..15)
    tax
    lda $03
    sec
    sbc $00
    sta $02             ; $02 = right_count
    txa
    sec
    sbc $02
    sta $03             ; $03 = left_count
    ldx #$00
    lda $03
    beq :+
    inx
:
    lda $02
    beq :+
    inx
:
    stx $05             ; $05 = insert (1 or 2)
    ; Find end byte of row $4A ($6094/$6095) BEFORE updating row pointers
    lda $6094
    sta $08
    lda $6095
    sta $09
    ldy #$00
    sty $0A
@find_end:
    lda ($08),y
    lsr
    lsr
    lsr
    lsr
    sec
    adc $0A
    sta $0A
    cmp #$40
    bcs @found_end
    iny
    bne @find_end
@found_end:
    jmp BurnMapEndGuard ; computes end_lo/end_hi; refuses a split that would overflow WRAM
BurnMapEndBack = *
    sta $0B             ; $0B = dst_hi
    lda #$00
    sta $08             ; $08 = 0 (page base)
    lda $05
    sta $0A             ; $0A = insert (1 or 2)
    ; Update row pointers $6000 + (row+1)*2 .. $6094
    lda $04
    asl
    tax
    inx
    inx
@ptr_loop:
    cpx #$96
    bcs @shift
    lda $6000,x
    clc
    adc $05
    sta $6000,x
    bcc :+
    inc $6001,x
:
    inx
    inx
    bne @ptr_loop
@shift:
    pla
    pha                 ; peek original row byte index
    clc
    adc $0E
    sta $06
    lda $0F
    adc #$00
    sta $07             ; $06/$07 = ($0E + Y) = stop_addr - 1
    lda $09
    cmp $07
    beq @last_page
@page_loop:
    lda ($08),y
    sta ($0A),y
    tya
    beq @prev_page
    dey
    jmp @page_loop
@prev_page:
    dec $09
    dec $0B
    ldy #$FF
    lda $09
    cmp $07
    bne @page_loop
@last_page:
    cpy $06
    beq @write_runs
    lda ($08),y
    sta ($0A),y
    dey
    jmp @last_page
@write_runs:
    pla
    tay                 ; restore Y
    lda $03             ; left_count
    beq @write_burnt
    jsr @pack_forest
    iny
@write_burnt:
    lda #$04
    sta ($0E),y
    lda $02             ; right_count
    beq @split_done
    iny
@pack_forest:
    sec
    sbc #$01
    asl
    asl
    asl
    asl
    ora #$06
    sta ($0E),y
@split_done:
    rts
BurnAbort:
    pla                 ; drop saved row index; map unchanged
    lda #$00
    sta $0301           ; cancel queued PPU macro byte count
    lda #$FF
    sta $0302           ; mark PPU macro buffer empty ($FF terminator)
    rts

.segment "BANK0_TAIL"
; Bank 0 pad $BFE0-$BFF9 (between the unused reset stub and the vectors).
; The overworld RLE map lives at $7C00 and ends near $7F20; each forest split
; grows it by up to 2 bytes. Past $7FFF the shift would write MMC1 registers,
; so once the map end reaches $7FF0 further splits are refused (the tree stays).
; Entry: Y = row-$4A end index, $08/$09 = row-$4A base, saved Y on the stack.
BurnMapEndGuard:
    tya
    clc
    adc $08
    tay                 ; Y = end_lo
    lda $09
    adc #$00
    sta $09             ; $09 = end_hi
    cmp #$7F
    bcc @ok
    cpy #$F0
    bcc @ok
    jmp BurnAbort
@ok:
    jmp BurnMapEndBack

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
    jsr DarkLinkFireCheck
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
.include "tall_player.inc"
.include "stomp.inc"
.include "blocks.inc"
.include "shouts.inc"
.include "town.inc"
.include "sign.inc"
.include "scales.inc"
.include "farcall.inc"
.include "late_split.inc"
.include "death_display.inc"
.include "ending_fire.inc"
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
    bcc @water
    jmp $E12B
@water:
    rts

; Execute the original shield handler with its first three bytes restored.
; SafeNativeShieldFire (bank 0) pushes NativeReturn0-1 so LE654's PLA/PLA
; stack escape returns through NativeReturn0 instead of mapping-less bank 0.
NativeShieldFire:
    jsr $FFC9
    lda $C8
    asl
    jsr $E61A
    jmp NativeReturn0

SwapToBank6:
    lda #$06
    jmp $FFCC

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
; Lag-frame NMI ($C065) pushed $8506 before entering here.
LagNmiBank6:
    lda #$06
    jsr $FFCC
    jmp LagNmiInBank6

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
    pha
    jsr $FFC5
    pla
    plp
    rts

.segment "BANK6"
; Lag-frame NMI: run audio driver in bank 6, then restore the actual
; interrupted bank (bank 0 if $8506 fingerprint == $F0, else area bank $0769).
LagNmiInBank6:
    jsr $9000
    pla
    cmp #$F0
    beq @bank0
    lda $0769
    .byte $2C
@bank0:
    lda #$00
    tax
    lda #>($C070-1)
    pha
    lda #<($C070-1)
    pha
    txa
    jmp $FFCC

.include "dark_barba.inc"
.include "geldarm.inc"
