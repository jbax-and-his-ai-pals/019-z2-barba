; Three backed projectiles multiplex native slot 0 without changing range.
; Record offsets: state,Y,Xlo,Xhi,vx,dir,actorCode,class,fraction,life,OAM.
.export BarbaExtraAllocate, BarbaExtraUpdate, BarbaExtraReset
.export BarbaEnemyFire, BarbaShieldFire, BarbaExtraBlocks
EXTRA_BASE = $6400
EXTRA_SAVE = $6440
EXTRA_INDEX = $6450
EXTRA_ENEMY_X = $6451
EXTRA_OLD10 = $6452
EXTRA_OLD8E = $6453
EXTRA_KIND = $6454
EXTRA_OLD11 = $6455
EXTRA_DELTA = $6456
EXTRA_LIVE = $645C ; nonzero while any backed record may be alive (fixed-bank fast path)
EXTRA_READY = $05FF

BarbaExtraEnsure:
    lda EXTRA_READY
    cmp #$01
    beq @done
    jsr BarbaExtraReset
    lda #$01
    sta EXTRA_READY
@done:
    rts
BarbaExtraReset:
    lda #$00
    sta EXTRA_LIVE
    sta EXTRA_BASE
    sta EXTRA_BASE+$10
    sta EXTRA_BASE+$20
    sta EXTRA_BASE+$09
    sta EXTRA_BASE+$19
    sta EXTRA_BASE+$29
    rts

; Save slot 0 and its OAM window. The fourth sprite bytes are copied too:
; native disintegration and normal update both use $0238..$023B.
ExtraSaveZero:
    lda $008D
    sta EXTRA_SAVE+$00
    lda $0036
    sta EXTRA_SAVE+$01
    lda $005A
    sta EXTRA_SAVE+$02
    lda $0048
    sta EXTRA_SAVE+$03
    lda $007D
    sta EXTRA_SAVE+$04
    lda $006D
    sta EXTRA_SAVE+$05
    lda $0026
    sta EXTRA_SAVE+$06
    lda $05CA
    sta EXTRA_SAVE+$07
    lda $03E3
    sta EXTRA_SAVE+$08
    lda $05FC
    sta EXTRA_SAVE+$09
    lda $009D
    sta EXTRA_SAVE+$0a
    lda $0238
    sta EXTRA_SAVE+$0b
    lda $0239
    sta EXTRA_SAVE+$0c
    lda $023A
    sta EXTRA_SAVE+$0d
    lda $023B
    sta EXTRA_SAVE+$0e
    rts
ExtraRestoreZero:
    lda EXTRA_SAVE+$00
    sta $008D
    lda EXTRA_SAVE+$01
    sta $0036
    lda EXTRA_SAVE+$02
    sta $005A
    lda EXTRA_SAVE+$03
    sta $0048
    lda EXTRA_SAVE+$04
    sta $007D
    lda EXTRA_SAVE+$05
    sta $006D
    lda EXTRA_SAVE+$06
    sta $0026
    lda EXTRA_SAVE+$07
    sta $05CA
    lda EXTRA_SAVE+$08
    sta $03E3
    lda EXTRA_SAVE+$09
    sta $05FC
    lda EXTRA_SAVE+$0a
    sta $009D
    lda EXTRA_SAVE+$0b
    sta $0238
    lda EXTRA_SAVE+$0c
    sta $0239
    lda EXTRA_SAVE+$0d
    sta $023A
    lda EXTRA_SAVE+$0e
    sta $023B
    rts
ExtraLoadRecord:
    ldy EXTRA_INDEX
    lda EXTRA_BASE+$00,y
    sta $008D
    lda EXTRA_BASE+$01,y
    sta $0036
    lda EXTRA_BASE+$02,y
    sta $005A
    lda EXTRA_BASE+$03,y
    sta $0048
    lda EXTRA_BASE+$04,y
    sta $007D
    lda EXTRA_BASE+$05,y
    sta $006D
    lda EXTRA_BASE+$06,y
    sta $0026
    lda EXTRA_BASE+$07,y
    sta $05CA
    lda EXTRA_BASE+$08,y
    sta $03E3
    lda EXTRA_BASE+$09,y
    sta $05FC
    lda EXTRA_BASE+$0a,y
    sta $009D
    rts
ExtraStoreRecord:
    ldy EXTRA_INDEX
    lda $008D
    sta EXTRA_BASE+$00,y
    lda $0036
    sta EXTRA_BASE+$01,y
    lda $005A
    sta EXTRA_BASE+$02,y
    lda $0048
    sta EXTRA_BASE+$03,y
    lda $007D
    sta EXTRA_BASE+$04,y
    lda $006D
    sta EXTRA_BASE+$05,y
    lda $0026
    sta EXTRA_BASE+$06,y
    lda $05CA
    sta EXTRA_BASE+$07,y
    lda $03E3
    sta EXTRA_BASE+$08,y
    lda $05FC
    sta EXTRA_BASE+$09,y
    ; Preserve the extra's own OAM address, never native window $38.
    lda EXTRA_INDEX
    lsr
    lsr
    lsr
    lsr
    tay
    lda ExtraOam,y
    ldy EXTRA_INDEX
    sta EXTRA_BASE+$0A,y
    rts

; Carry set only after a valid third/fourth/fifth slot was actually placed.
BarbaExtraAllocate:
    jsr BarbaExtraEnsure
    lda #$00
    sta EXTRA_INDEX
@find:
    ldy EXTRA_INDEX
    lda EXTRA_BASE,y
    beq @allocate
    lda EXTRA_INDEX
    clc
    adc #$10
    sta EXTRA_INDEX
    cmp #$30
    bcc @find
    clc
    rts
@allocate:
    jsr ExtraSaveZero
    lda #$00
    sta $8D
    ldx #$00
    clc
    jsr $981B
    jsr BarbaPlaceNewFlame
    php
    lda #$01
    sta EXTRA_LIVE
    jsr ExtraStoreRecord
    jsr ExtraRestoreZero
    plp
    rts

BarbaExtraUpdate:
    txa
    pha
    lda $10
    pha
    lda $CB
    pha
    lda $CF
    pha
    jsr BarbaExtraEnsure
    ; Idle fast path: with no backed record alive, only hide the extra OAM
    ; slots. Skips the slot-0 save/restore copies on most frames.
    lda EXTRA_BASE
    ora EXTRA_BASE+$10
    ora EXTRA_BASE+$20
    bne @busy
    lda #$F8
    ldy ExtraOam
    sta $0200,y
    ldy ExtraOam+1
    sta $0200,y
    ldy ExtraOam+2
    sta $0200,y
    lda #$00
    sta EXTRA_LIVE
    jmp @idle
@busy:
    jsr ExtraSaveZero
    lda #$00
    sta EXTRA_INDEX
@slot:
    lda EXTRA_INDEX
    lsr
    lsr
    lsr
    lsr
    tay
    lda ExtraOam,y
    tay
    lda #$F8
    sta $0200,y
    ldy EXTRA_INDEX
    lda EXTRA_BASE,y
    beq @next
    jsr ExtraLoadRecord
    lda $8D
    bmi @native
    ldx #$00
    jsr BarbaStepSlotY
    bcc @store
@native:
    ldx #$00
    jsr $9888
    lda $8D
    beq @store
    ; Copy the native sprite to its independent extra OAM slot.
    ldy EXTRA_INDEX
    lda EXTRA_BASE+$0A,y
    tay
    lda $0238
    sta $0200,y
    lda $0239
    sta $0201,y
    lda $023A
    sta $0202,y
    lda $023B
    sta $0203,y
    lda $8D
    bmi @store
    lda #$84
    sta $0201,y
    lda $0202,y
    and #$C0
    ora #$01
    sta $0202,y
@store:
    jsr ExtraStoreRecord
@next:
    lda EXTRA_INDEX
    clc
    adc #$10
    sta EXTRA_INDEX
    cmp #$30
    bcs :+
    jmp @slot
:
    jsr ExtraRestoreZero
    lda EXTRA_BASE
    ora EXTRA_BASE+$10
    ora EXTRA_BASE+$20
    sta EXTRA_LIVE
@idle:
    pla
    sta $CF
    pla
    sta $CB
    pla
    sta $10
    pla
    tax
    rts

; Root fixed helpers reconstruct the original entry prefixes and return in
; BANK0. Run originals once for the two real slots, then each backed slot.
BarbaEnemyFire:
    lda $B6,x
    cmp #$01
    bne :+
    jsr NativeEnemyFire
:
    php
    pha
    tya
    pha
    lda #$00
    jmp ExtraCollision
BarbaShieldFire:
    jsr NativeShieldFire
    php
    pha
    tya
    pha
    lda #$01
ExtraCollision:
    sta EXTRA_KIND
    stx EXTRA_ENEMY_X
    ; Most enemies never see a backed projectile. Return with the original
    ; helper's exact registers/flags before copying any native slot fields.
    lda EXTRA_READY
    cmp #$01
    bne @fast_return
    lda $B6,x
    cmp #$01
    bne @fast_return
    lda EXTRA_KIND
    bne @check_slots
    lda $040E,x
    bne @fast_return
@check_slots:
    lda EXTRA_BASE
    beq :+
    bpl @active
:
    lda EXTRA_BASE+$10
    beq :+
    bpl @active
:
    lda EXTRA_BASE+$20
    beq @fast_return
    bpl @active
@fast_return:
    pla
    tay
    pla
    plp
    rts
@active:
    lda $10
    sta EXTRA_OLD10
    lda $11
    sta EXTRA_OLD11
    lda $8E
    sta EXTRA_OLD8E
    jsr BarbaExtraEnsure
    ; Save slot 0 lazily: most enemies are far from every backed shot.
    lda #$00
    sta EXTRA_KIND+$03 ; $6457: 1 once slot 0 has been saved this call
    sta EXTRA_INDEX
@slot:
    ldy EXTRA_INDEX
    lda EXTRA_BASE,y
    beq @next
    bmi @next
    ldx EXTRA_ENEMY_X
    jsr ExtraNearEnemy
    bcc @next
    lda EXTRA_KIND+$03
    bne :+
    jsr ExtraSaveZero
    lda #$00
    sta $8E
    lda #$01
    sta EXTRA_KIND+$03
:
    jsr ExtraLoadRecord
    ldx EXTRA_ENEMY_X
    stx $10
    lda EXTRA_KIND
    bne @shield
    jsr NativeEnemyFire
    jmp @store
@shield:
    jsr NativeShieldFire
@store:
    jsr ExtraStoreRecord
@next:
    lda EXTRA_INDEX
    clc
    adc #$10
    sta EXTRA_INDEX
    cmp #$30
    bcc @slot
    lda EXTRA_KIND+$03
    beq :+
    jsr ExtraRestoreZero
:
    lda EXTRA_OLD8E
    sta $8E
    lda EXTRA_OLD10
    sta $10
    lda EXTRA_OLD11
    sta $11
    ldx EXTRA_ENEMY_X
    pla
    tay
    pla
    plp
    rts

; Conservative broad phase in world space. Actual native AABB/shield tests
; still decide contact; +/-128px covers the largest native boss hurtboxes.
; Y=record offset, X=enemy. Carry set when both axes can plausibly overlap.
ExtraNearEnemy:
    lda EXTRA_BASE+$02,y
    sec
    sbc $4E,x
    sta EXTRA_DELTA
    lda EXTRA_BASE+$03,y
    sbc $3C,x
    beq @positive_x
    cmp #$FF
    bne @far
    lda EXTRA_DELTA
    bpl @far
    jmp @y
@positive_x:
    lda EXTRA_DELTA
    bmi @far
@y:
    lda EXTRA_BASE+$01,y
    sec
    sbc $2A,x
    bcc @negative_y
    bmi @far
    sec
    rts
@negative_y:
    bpl @far
    sec
    rts
@far:
    clc
    rts

; Root's ordinary block loop already handles the real slots. Alias each
; backed slot once for exactly the same glove-gated collision behavior.
BarbaExtraBlocks:
    php
    pha
    txa
    pha
    tya
    pha
    jsr BarbaExtraEnsure
    lda EXTRA_BASE
    ora EXTRA_BASE+$10
    ora EXTRA_BASE+$20
    bne :+
    jmp @idle
:
    jsr ExtraSaveZero
    lda $80
    pha
    lda $047E
    pha
    lda $057D
    pha
    lda $10
    pha
    lda $8E
    pha
    lda #$00
    sta $8E
    sta EXTRA_INDEX
@slot:
    ldy EXTRA_INDEX
    lda EXTRA_BASE,y
    beq @next
    bmi @next
    jsr ExtraLoadRecord
    ldx #$00
    jsr BarbaBlockSlot
    jsr ExtraStoreRecord
@next:
    lda EXTRA_INDEX
    clc
    adc #$10
    sta EXTRA_INDEX
    cmp #$30
    bcc @slot
    pla
    sta $8E
    pla
    sta $10
    pla
    sta $057D
    pla
    sta $047E
    pla
    sta $80
    lda #$F8
    sta $0480
    jsr ExtraRestoreZero
@idle:
    pla
    tay
    pla
    tax
    pla
    plp
    rts
ExtraOam:
    .byte $3C,$44,$48
