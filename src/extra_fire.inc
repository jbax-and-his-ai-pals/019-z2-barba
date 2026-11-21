; Three backed projectiles multiplex native slot 0 without changing range.
; Record offsets: state,Y,Xlo,Xhi,vx,dir,actorCode,class,fraction,life,OAM.
.export BarbaExtraAllocate, BarbaExtraUpdate, BarbaExtraReset
.export BarbaEnemyFire, BarbaShieldFire, BarbaExtraBlocks, DarkLinkFireCheck
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
    txa
    pha
    jsr BarbaExtraReset
    lda #$01
    sta EXTRA_READY
    pla
    tax
@done:
    rts
BarbaExtraReset:
    lda #$00
    sta EXTRA_LIVE
    ldx #$20
:
    lda #$00
    sta EXTRA_BASE,x
    sta EXTRA_BASE+$09,x
    txa
    sec
    sbc #$10
    tax
    bpl :-
    lda #$00
    ldx #$21            ; SIGN_PENDING ($64D1) - SCORCH_TIME ($64B0)
@clear_scorch:
    sta $64B0,x
    dex
    bpl @clear_scorch
    rts

; Save slot 0 and its OAM window. The fourth sprite bytes are copied too:
; native disintegration and normal update both use $0238..$023B.
ExtraSaveZero:
    lda $0238
    sta EXTRA_SAVE+$0b
    lda $0239
    sta EXTRA_SAVE+$0c
    lda $023A
    sta EXTRA_SAVE+$0d
    lda $023B
    sta EXTRA_SAVE+$0e
    lda $009D
    sta EXTRA_SAVE+$0a
    ldy #$40
    bne ExtraStoreTen
ExtraRestoreZero:
    lda EXTRA_SAVE+$0b
    sta $0238
    lda EXTRA_SAVE+$0c
    sta $0239
    lda EXTRA_SAVE+$0d
    sta $023A
    lda EXTRA_SAVE+$0e
    sta $023B
    ldy #$40
    bne ExtraLoadAtY
ExtraLoadRecord:
    ldy EXTRA_INDEX
ExtraLoadAtY:
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
ExtraStoreTen:
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
    jsr BarbaExtraEnsure
    ; Idle fast path: with no backed record alive, only hide the extra OAM
    ; slots. Skips the slot-0 save/restore copies and stack frame on most frames.
    lda EXTRA_BASE
    ora EXTRA_BASE+$10
    ora EXTRA_BASE+$20
    bne @busy
    sta EXTRA_LIVE
    lda #$F8
    sta $023C
    sta $0244
    sta $0248
    rts
@busy:
    txa
    pha
    lda $10
    pha
    lda $CB
    pha
    lda $CF
    pha
    lda #$00
    sta EXTRA_KIND+$03
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
    ldx EXTRA_INDEX
    lda EXTRA_BASE,x
    bne :+
    jmp @next
:
    bpl :+
    jmp @slow_slot
:
    lda EXTRA_BASE+$04,x
    and #$0F
    beq :+
    jmp @slow_slot
:
    lda EXTRA_BASE+$07,x
    beq @fast_step_y
    cmp #$F2
    bne :+
    jmp @kill_slot
:
    clc
    adc #$01
    sta EXTRA_BASE+$07,x
@fast_step_y:
    dec EXTRA_BASE+$09,x
    lda EXTRA_BASE+$09,x
    and #$3F
    bne :+
    jmp @kill_slot
:
    lda EXTRA_BASE+$09,x
    and #$40
    bne @fast_up_y
    lda EXTRA_BASE+$09,x
    bpl @fast_steep_y
    and #$01
    beq @fast_move_x
    lda #$01
    bne @fast_add_y
@fast_steep_y:
    lda #$02
@fast_add_y:
    clc
    adc EXTRA_BASE+$01,x
    bcs @kill_slot_near
    cmp #$E0
    bcc :+
@kill_slot_near:
    jmp @kill_slot
:
    sta EXTRA_BASE+$01,x
    jmp @fast_move_x
@fast_up_y:
    lda EXTRA_BASE+$09,x
    bmi @fast_move_x    ; METEOR_WAVE ($C0): flat along the floor
    lda EXTRA_BASE+$01,x
    sec
    sbc #$03
    bcc @kill_slot_near
    cmp #$10
    bcc @kill_slot_near
    sta EXTRA_BASE+$01,x
@fast_move_x:
    lda EXTRA_BASE+$04,x
    lsr
    lsr
    lsr
    lsr
    cmp #$08
    bcc :+
    ora #$F0
:
    ldy #$00
    cmp #$00
    bpl :+
    dey
:
    clc
    adc EXTRA_BASE+$02,x
    sta EXTRA_BASE+$02,x
    tya
    adc EXTRA_BASE+$03,x
    sta EXTRA_BASE+$03,x
    lda EXTRA_BASE+$02,x
    sec
    sbc $072C
    tay
    lda EXTRA_BASE+$03,x
    sbc $072A
    bne @kill_slot
    cpy #$F8
    bcs @kill_slot
    lda EXTRA_BASE+$05,x
    lsr
    lda #$00
    ror
    ror
    sta $00
    lda $12
    asl
    asl
    asl
    asl
    asl
    and #$80
    ora $00
    ora #$01
    pha
    tya
    pha
    lda EXTRA_BASE+$0A,x
    tay
    pla
    sta $0203,y
    pla
    sta $0202,y
    lda #$84
    sta $0201,y
    lda EXTRA_BASE+$01,x
    sta $0200,y
    jmp @next
@kill_slot:
    lda #$00
    sta EXTRA_BASE,x
    sta EXTRA_BASE+$09,x
    jmp @next
@slow_slot:
    lda EXTRA_KIND+$03
    bne :+
    jsr ExtraSaveZero
    lda #$01
    sta EXTRA_KIND+$03
:
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
    lda EXTRA_KIND+$03
    beq :+
    jsr ExtraRestoreZero
:
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

; The shield test and its melee escape use fixed code and RAM. The extra
; return address lets $E654 discard it when a melee hit meets the shield.
NativeShieldFire:
    lda $C8
    asl
    jsr $E61A
    rts
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

; Tight broad phase in world space (-32 <= dx < +48, -32 <= dy < +64).
; Covers every native enemy and boss hurtbox while skipping distant enemies.
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
    cmp #$E0
    bcc @far
    bcs @y
@positive_x:
    lda EXTRA_DELTA
    cmp #$30
    bcs @far
@y:
    lda EXTRA_BASE+$01,y
    sec
    sbc $2A,x
    clc
    adc #$20
    cmp #$60
    bcs @far
    sec
    rts
@far:
    clc
    rts

; Read backed slot coordinates directly without aliasing native slot 0.
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
    beq @idle
    lda $80
    pha
    lda $047E
    pha
    lda $057D
    pha
    ldx #$00
@slot:
    lda EXTRA_BASE,x
    beq @next
    bmi @next
    lda EXTRA_BASE+$02,x
    sec
    sbc $072C
    sta $047E
    lda EXTRA_BASE+$03,x
    sbc $072A
    bne @next
    lda EXTRA_BASE+$01,x
    cmp #$20
    bcc @next
    cmp #$D8
    bcs @next
    clc
    adc #$05
    sta $0480
    txa
    pha
    lda $0707
    beq @castle_slot
    cmp #$03
    bcs @native_block
    bcc @town_burn
@castle_slot:
    lda $0561
    ora $0706
    beq @town_burn
@native_block:
    lda #$09
    sta $80
    jsr $E1DD
    jmp @slot_done
@town_burn:
    jsr BarbaTownBurn
@slot_done:
    pla
    tax
@next:
    txa
    clc
    adc #$10
    tax
    cmp #$30
    bcc @slot
    pla
    sta $057D
    pla
    sta $047E
    pla
    sta $80
    lda #$F8
    sta $0480
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

; Dark Link (Great Palace room $36, enemy $23 in slot 0) uses a custom sword-only
; collision handler (bank 5 $9A8D) and skips $E48B. Check native and extra
; fireball slots against Dark Link's body and apply the exact 1-HP sword-hit
; response ($0509/$050D knockback, $E9 SFX, $C2 == 0 death).
.segment "BANK6"
DarkLinkFireCheck:
    lda $0707
    cmp #$05
    bne @done_early
    lda $0736
    cmp #$0B
    bne @done_early
    lda $B6
    cmp #$01
    bne @done_early
    lda $A1
    cmp #$23
    bne @done_early
    lda $63
    beq @phase0
    cmp #$02
    beq @phase2
    cmp #$04
    beq @phase4
    cmp #$03
    bne @done_early
    lda $13
    beq @check_fire
    jsr DarkWyrmlingTick
@check_fire:
    lda $C2
    beq @done_early
    lda $0505
    ora $050D
    ora $0509
    bne @done_early
    jmp @scan
@phase0:
    lda $13
    beq @done_early
    lda $072A
    beq @done_early
    lda $A7
    ora #$04
    sta $A7
@done_early:
    rts
@phase2:
    lda $13
    beq @done_early
    jmp DarkWyrmlingDraw
@phase4:
    lda $13
    beq @done_early
    lda #$00
    sta $13
    lda $076F
    and #$F7
    sta $076F
    lda #$01
    sta $17
    lda $29
    cmp #$A0
    bcs @phase4_floor
    sta $0479           ; nonzero -> airborne until gravity reaches $A0
    lda $057D
    bpl @done_early
    lda #$00
    sta $057D
    rts
@phase4_floor:
    lda #$A0
    sta $29
    lda #$00
    sta $0479
    sta $057D
    rts
@scan:
    ldy #$01
@native:
    lda $8D,y
    beq @next_native
    bmi @next_native
    lda $5A,y
    sta $00
    lda $48,y
    sta $01
    lda $36,y
    jsr DarkLinkHitBox
    bcs @hit
@next_native:
    dey
    bpl @native
    lda EXTRA_LIVE
    beq @done
    ldy #$00
@extra:
    lda EXTRA_BASE+$00,y
    beq @next_extra
    bmi @next_extra
    lda EXTRA_BASE+$02,y
    sta $00
    lda EXTRA_BASE+$03,y
    sta $01
    lda EXTRA_BASE+$01,y
    jsr DarkLinkHitBox
    bcs @hit
@next_extra:
    tya
    clc
    adc #$10
    tay
    cmp #$30
    bcc @extra
@done:
    rts
@hit:
    ldx #$00
    ldy #$00
    sty $0401
    dey
    dec $C2
    beq @dead
    lda #$38
    sta $0509
    ldy #$18
@dead:
    sty $050D
    ldx #$05
    lda #$00
@clr_eproj:
    sta $87,x
    dex
    bpl @clr_eproj
    ldx #$00
    clc
    jsr $DC91
    lda DarkLinkKnockback,y
    sta $71
    lda #$FD
    sta $057E
    lda #$01
    sta $E9
    sta $62
    rts
DarkLinkHitBox:
    sta $02
    lda $00
    sec
    sbc $4E
    sta $03
    lda $01
    sbc $3C
    tax
    lda $13
    bne @wyrm_x
    lda $03
    clc
    adc #$04
    bcc @hi_ok
    inx
    bcs @hi_ok
@wyrm_x:
    lda $03
    clc
    adc #$FC            ; center hitbox on Dark Wyrmling sprite ($CD+$0C)
    bcs @hi_ok
    dex
@hi_ok:
    cpx #$00
    bne @miss
    cmp #$11
    bcs @miss
    lda $02
    sec
    sbc $2A
    sta $03
    lda $13
    bne @wyrm_y
    lda $03
    clc
    adc #$0A
    cmp #$24
    bcs @miss
    sec
    rts
@wyrm_y:
    lda $03
    clc
    adc #$04
    cmp #$1E
    bcs @miss
    sec
    rts
@miss:
    clc
    rts
DarkLinkKnockback:
    .byte $F6,$0A

DarkWyrmlingTick:
    lda #$00
    sta $0401
    sta $0506
    lda $C2
    beq @draw_only
    lda $050D
    beq @not_hurt
    lda $2A
    cmp #$98
    bcc @draw_only
    lda #$98
    sta $2A
    lda #$00
    sta $057E
@draw_only:
    jmp DarkWyrmlingDraw
@not_hurt:
    lda $0505
    beq @active
    lda #$00
    sta $71
    sta $057E
    sta $03E7
    jmp DarkWyrmlingDraw
@active:
    lda #$01
    sta $62
    lda #$00
    sta $03E7
    lda $2A
    cmp #$94
    bcc @alt_ok
    lda #$94
    sta $2A
@alt_ok:
    ; Centralized aerial target: midpoint of Player Y and $6E clamped to [$48..$8C],
    ; plus a +/- 8 px triangle-wave swoop so Dark Wyrmling never ceiling-camps.
    lda $29
    clc
    adc #$6E
    ror
    cmp #$48
    bcs :+
    lda #$48
:   cmp #$8C
    bcc :+
    lda #$8C
:   sta $00
    lda $12
    and #$3F
    cmp #$20
    bcc :+
    eor #$3F
:   lsr
    sec
    sbc #$08
    clc
    adc $00
    sec
    sbc $2A
    bpl @below
    cmp #$FE            ; diff < -2 -> fly up
    bcc @fly_up
    lda #$00
    beq @set_vy
@fly_up:
    lda #$FF
    bne @set_vy
@below:
    cmp #$03            ; diff >= 3 -> fly down
    bcs @fly_down
    lda #$00
    beq @set_vy
@fly_down:
    lda #$01
@set_vy:
    sta $057E
    lda $2A
    cmp #$38
    bcs :+
    lda #$01
    sta $057E
:   ldx #$00
    clc
    jsr $DC91           ; $60 = 1 (Link right) / 2 (Link left), $0F = lo(LinkX - BossX)
    lda $CD
    cmp #$34
    bcc @swoop_right
    cmp #$BC
    bcs @swoop_left
    lda $0F
    ldy $60
    cpy #$01
    beq @abs_ok
    eor #$FF
    clc
    adc #$01
@abs_ok:
    cmp #$24
    bcc @retreat
    cmp #$4C
    bcs @approach
    lda $CD             ; inside dueling range: drift toward arena center ($78)
    cmp #$78
    bcc @drift_right
    lda #$F8
    bne @set_vx
@drift_right:
    lda #$08
    bne @set_vx
@retreat:
    cpy #$01
    beq @move_left
    bne @move_right
@approach:
    cpy #$01
    beq @move_right
@move_left:
    lda #$EE
    .byte $2C
@move_right:
    lda #$12
    .byte $2C
@swoop_left:
    lda #$EA
    .byte $2C
@swoop_right:
    lda #$16
@set_vx:
    sta $71
    lda $12
    and #$1F
    bne DarkWyrmlingDraw
    lda $CD
    cmp #$14
    bcc DarkWyrmlingDraw
    cmp #$E4
    bcs DarkWyrmlingDraw
    lda #$00
    sta $10
    jsr $DBCE
    bcs DarkWyrmlingDraw
    lda #$03
    sta $87,y
    lda $30,y
    clc
    adc #$08
    sta $30,y
    lda $ED
    ora #$40
    sta $ED
DarkWyrmlingDraw:
    lda #$F8
    sta $0254
    sta $0258
    sta $025C
    sta $0260
    sta $0264
    sta $0268
    sta $026C
    sta $0270
    sta $0274
    lda $C9
    and #$F0
    bne @w_hide
    lda $CD
    clc
    adc #$0C
    bcs @w_hide
    sta $0253
    lda $12
    and #$38
    lsr
    lsr
    lsr
    eor #$04
    tay
    lda $2A
    clc
    adc #$08
    adc $EBB0,y
    cmp #$20
    bcc @w_hide
    cmp #$F0
    bcs @w_hide
    sta $0250
    lda $12
    and #$04
    lsr
    eor #$02
    ora #$68
    sta $0251
    lda #$02
    sta $0252
    rts
@w_hide:
    lda #$F8
    sta $0250
@w_done:
    rts
.segment "BANK0"
