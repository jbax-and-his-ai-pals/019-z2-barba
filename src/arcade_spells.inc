; 18-Spell System (8 Hyrule + 10 Arcade) & 2-Column Pause Menu
; Lives in BANK2_SMOKE (Bank 2) with minimal stubs in BANK0_SPELL (reclaimed $9C1A..$9D31).

ARCADE_ACTIVE_LO   = $6680 ; bits 0..7 = DECOY, AXE, DOUBLE, BARREL, STAR, LOCK, BLADE, LUCKY
ARCADE_ACTIVE_HI   = $6681 ; bits 0..1 = CLOCK, HEAVY
ARCADE_CLOCK_TMR   = $6682 ; CLOCK enemy/projectile freeze timer
ARCADE_LUCKY_CNT   = $6683 ; LUCKY remaining forced-drop kills (0..3)
ARCADE_DECOY_TMR   = $6684 ; DECOY active timer
ARCADE_DECOY_XLO   = $6685
ARCADE_DECOY_XHI   = $6686
ARCADE_DECOY_Y     = $6687
ARCADE_BARREL_TMR  = $6688 ; BARREL active timer
ARCADE_BARREL_XLO  = $6689
ARCADE_BARREL_XHI  = $668A
ARCADE_BARREL_Y    = $668B
ARCADE_BARREL_VX   = $668C
ARCADE_BARREL_VY   = $668D
ARCADE_LOCK_SLOT   = $668E ; LOCK target enemy slot (0..5, $FF = none)
ARCADE_STAR_TMR    = $668F ; STAR invincibility timer
ARCADE_AXE_TMR     = $6690 ; AXE projectile timer
ARCADE_AXE_XLO     = $6691
ARCADE_AXE_XHI     = $6692
ARCADE_AXE_Y       = $6693
ARCADE_AXE_VX      = $6694
ARCADE_AXE_VY      = $6695
ARCADE_AXE_YSUB    = $6696
SPELL_MENU_ACTIVE  = $6697 ; 1 while 2-column Spell Menu is open, 0 otherwise
SPELL_OLD_SEL      = $6698 ; previous $0749 cursor index for erase/draw
SPELL_GEAR_SEL     = $6699 ; 0 = Spells ($0749), 1..5 = Gear slot 0..4
BARBA_GEAR         = $648F ; bits 0..1=head (0 none, 1 hat, 2 mask, 3 helm), 4=tie, 5=belt, 7=init
SPELL_ROW_BUF0     = $66A0 ; 26 bytes ($66A0..$66B9)
SPELL_ROW_BUF1     = $66BA ; 26 bytes ($66BA..$66D3)

ARCADE_CLOCK_XY    = $66E6 ; 18 bytes ($66E6..$66F7): 6x (Xlo, Xhi, Y) for CLOCK freeze
SPELL_ATTR_BUF     = $6710 ; 42 bytes ($6710..$6739): 6 attr rows x 7 attr cols
SPELL_ATTR_TMP     = $673A ;  7 bytes ($673A..$6740): 1 attr row scratch for PPU emit

SPELL_BOX_METAS     = 13   ; 13 metatiles = 26 tiles wide
SPELL_BOX_TILES     = 26
SPELL_BOX_TILE_ROWS = 20   ; 20 tile rows (screen rows 6..25, 10 metatile rows)
SPELL_BOX_XOFF      = $28  ; 40 px from left edge of screen (aligns key items at cols 15..22)
SPELL_ATTR_COLS     = 7
SPELL_ATTR_ROWS     = 6

.export ArcadeSideViewInit0, ArcadeSpellHook0
.export SpellMenuInit0, LevelUpInit0, SpellMenuAttrSave0, SpellMenuDraw0
.export SpellMenuInput0, SpellMenuRestore0, SpellMenuDone0
.export ArcadeDoubleXp0, ArcadeLuckyDrop0, ArcadeHeavyDmg0

.segment "BANK0"

ArcadeSideViewInit0:
    sta $076F
    ldx #$07
    jsr CallBank2Spell0
    ldy #$00
    tya
    rts

ArcadeHeavyDmg0:
    txa
    pha
    tya
    pha
    stx $00
    sty $01
    jsr @call_bank2
    pla
    tay
    pla
    tax
    sec
    lda $01
    rts
@call_bank2:
    lda #>(ArcadeHeavyDmgBank2 - 1)
    pha
    lda #<(ArcadeHeavyDmgBank2 - 1)
    pha
    lda #$02
    jmp $FFCC

SpellMenuDone0:
    lda #$00
    sta SPELL_MENU_ACTIVE
    jmp $A338

.segment "BANK0_SPELL"

; Hooked at $8DC6 (A = $074C on entry, after ItemHoldSpell if sampled roar).
ArcadeSpellHook0:
    ora $0524
    ora $DE
    bne @skip_cast
    lda $F5
    and #$20
    beq @skip_cast
    ldy $0749
    cpy #$08
    bcs @arcade_cast
    jmp $8DDC               ; vanilla spell 0..7 cast (after $8DC9..$8DDB reclaim)
@arcade_cast:
    ldx #$00
    jsr CallBank2Spell0
@skip_cast:
    lda ARCADE_ACTIVE_LO
    and #$7B                ; ticking spells only (DECOY, AXE, BARREL, STAR, LOCK, BLADE)
    bne @do_tick
    lda ARCADE_ACTIVE_HI
    and #$01                ; ticking spell only (CLOCK)
    beq @done
@do_tick:
    ldx #$01
    jsr CallBank2Spell0
@done:
    jmp $8E1F               ; vanilla active ticks + RTS

.segment "BANK0_SPELL2"

SpellMenuDraw0:
    lda SPELL_MENU_ACTIVE
    bne @ours
    jmp $A2FE
@ours:
    ldx #$04
    jmp CallBank2Spell0

ArcadeDoubleXp0:
    ldx #$08
    .byte $2C               ; BIT abs (skip next 2 bytes)
ArcadeLuckyDrop0:
    ldx #$09
    jsr CallBank2Spell0
    lda $01
    rts

.segment "BANK0_SPELL3"

SpellMenuAttrSave0:
    lda SPELL_MENU_ACTIVE
    bne @ours
    jmp $A26B
@ours:
    ldx #$03
    jsr CallBank2Spell0
    inc $0524
    rts

.segment "BANK0_SPELL"

SpellMenuInit0:
    ldx #$02
    stx SPELL_MENU_ACTIVE
    .byte $2C               ; BIT $0AA2 skips LDX #$0A
LevelUpInit0:
    ldx #$0A
    jsr CallBank2Spell0
    jmp $A31C               ; $074F=$C0, $EE=$08, INC $0524, RTS

SpellMenuInput0:
    lda SPELL_MENU_ACTIVE
    bne @ours
    jmp $A1DD
@ours:
    lda $F8
    cmp #$88
    bne @not_save
    jmp $A1A5
@not_save:
    ldx #$05
    jsr CallBank2Spell0
    lda $F7
    sta $0744
    rts

SpellMenuRestore0:
    dec $0525
    bpl @do_row
    jmp $A267               ; INC $0524; RTS -> State 8
@do_row:
    lda $072C
    clc
    adc #SPELL_BOX_XOFF
    tax
    lda $072A
    adc #$00
    jsr $9AA8               ; bank0_unknown24 -> ($0E/$0F)
    txa
    lsr
    lsr
    lsr
    lsr
    tay
    lda $0525
    and #$FE
    asl
    asl
    asl
    adc #$10                ; box starts at tile row 6 (metatile row 1)
    jsr $A57E
    lda #$00
    sta $00                 ; tile dest offset (0, 2, ..., 24)
@meta_loop:
    lda ($0E),y
    sta $01                 ; current metatile
    iny
    tya
    and #$0F
    bne @no_pg
    lda #$D0
    clc
    jsr $A57E
    tya
    sec
    sbc #$10
    tay
@no_pg:
    lda $0E
    pha
    lda $0F
    pha
    tya
    pha
    lda $01
    asl
    rol
    rol
    asl
    and #$06
    tay
    jsr $DFDB
    lda $01
    asl
    asl
    tay
    ldx #$00
    jsr $C24F
    iny
    jsr $C24F
    ldx $00
    lda $053E
    sta SPELL_ROW_BUF0,x
    lda $053F
    sta SPELL_ROW_BUF0+1,x
    lda $054C
    sta SPELL_ROW_BUF1,x
    lda $054D
    sta SPELL_ROW_BUF1+1,x
    pla
    tay
    pla
    sta $0F
    pla
    sta $0E
    inx
    inx
    stx $00
    cpx #SPELL_BOX_TILES
    bcc @meta_loop
    ldx #$06
    jmp CallBank2Spell0

; X = index 0..6 into Bank2SpellHi/Lo; preserves A/Y via stack? (A/Y not preserved across SwapPRG)
CallBank2Spell0:
    lda Bank2SpellHi,x
    pha
    lda Bank2SpellLo,x
    pha
    lda #$01
    jmp $FFCC

Bank2SpellLo:
    .byte <(ArcadeCast2 - 1)
    .byte <(ArcadeTick2 - 1)
    .byte <(SpellMenuInit2 - 1)
    .byte <(SpellMenuAttrSave2 - 1)
    .byte <(SpellMenuDraw2 - 1)
    .byte <(SpellMenuInput2 - 1)
    .byte <(SpellMenuRestore2 - 1)
    .byte <(ArcadeSideViewInit2 - 1)
    .byte <(ArcadeDoubleXp2 - 1)
    .byte <(ArcadeLuckyDrop2 - 1)
    .byte <(LevelUpInit2 - 1)
Bank2SpellHi:
    .byte >(ArcadeCast2 - 1)
    .byte >(ArcadeTick2 - 1)
    .byte >(SpellMenuInit2 - 1)
    .byte >(SpellMenuAttrSave2 - 1)
    .byte >(SpellMenuDraw2 - 1)
    .byte >(SpellMenuInput2 - 1)
    .byte >(SpellMenuRestore2 - 1)
    .byte >(ArcadeSideViewInit2 - 1)
    .byte >(ArcadeDoubleXp2 - 1)
    .byte >(ArcadeLuckyDrop2 - 1)
    .byte >(LevelUpInit2 - 1)

.segment "BANK1_SPELLS"
; Populate Level-Up Pane template rows $789A..$7917 (9x14 bytes: $CC, 12x$F4, $CC;
; $D0 at $78C8, $78D6, $78E4), replacing vanilla $A347 copy from $9CB4..$9D31.
LevelUpInit2:
    ldx #$00
@row:
    lda #$CC
    sta $789A,x
    inx
    ldy #12
    lda #$F4
@mid:
    sta $789A,x
    inx
    dey
    bne @mid
    lda #$CC
    sta $789A,x
    inx
    cpx #(9 * 14)
    bcc @row
    lda #$D0
    sta $78C8
    sta $78D6
    sta $78E4
    jmp $FFC5

.segment "BANK1"
AxeSpinAttr:
    .byte $01, $41, $C1, $81 ; 0 -> 90 -> 180 -> 270 deg clockwise spin, palette 1

; Return A = axe CHR pair ($7E side-view, $FE towns) and Y = spinning OAM attr.
AxeSpriteSetup1:
    lda $12
    lsr
    lsr
    and #$03
    tax
    ldy AxeSpinAttr,x
    lda #$7E
    ldx $0707
    beq @done
    cpx #$03
    bcs @done
    lda #$FE
@done:
    rts

.segment "BANK1_TAIL"
ArcadeSideViewInit2:
    lda #$00
    ldx #$10
:   sta $6680,x
    dex
    bpl :-
    lda #$16
    sta $69D2
    lda #$27
    sta $69D8
    jmp $FFC5

.segment "BANK1_PAD2"
ArcadeDoubleXp2:
    lda ARCADE_ACTIVE_LO
    and #$04
    beq @norm
    asl $00
    bcc @norm
    inc $0775
@norm:
    lda $0776
    clc
    adc $00
    sta $01
    jmp $FFC5

.segment "BANK1_SPELLS"
; LUCKY: force next 3 enemy kills to drop Blue Magic Jar ($08) or 50-XP P-Bag ($10).
ArcadeLuckyDrop2:
    lda ARCADE_LUCKY_CNT
    beq @norm
    dec ARCADE_LUCKY_CNT
    and #$01
    bne @pbag
    lda #$08
    .byte $2C
@pbag:
    lda #$10
    ldx $10
    sta $048E,x
    lda #$00                ; != 6 so $E89F branches to $E8BF
    sta $01
    jmp $FFC5
@norm:
    ldx $10
    inc $05DE,x
    lda $05DE,x
    sta $01
    jmp $FFC5

.segment "BANK2_SMOKE"

; HEAVY: double attack/breath damage ($C2,x -= $E66C,y twice).
; Entry: $00 = enemy slot (X), $01 = damage table index (Y).
; Exit: $01 = clamped remaining HP (0 if dead or underflowed).
ArcadeHeavyDmgBank2:
    ldx $00
    ldy $01
    lda $C2,x
    sec
    sbc $E66C,y
    bcc @zero
    sta $01
    lda ARCADE_ACTIVE_HI
    and #$02
    beq @keep_first
    lda $01
    sec
    sbc $E66C,y
    bcs @store
@zero:
    lda #$00
    beq @store
@keep_first:
    lda $01
@store:
    sta $C2,x
    sta $01
    jmp $FFC5

.segment "BANK1"
; Active Arcade spells (1 = active, 0 = archived post-2.0: f13/AXE, smb/STAR, mm2/BLADE, zelda/CLOCK, mtpo/HEAVY)
ArcadeSpellActiveTbl:
    .byte 1, 0, 1, 1, 0, 1, 0, 1, 0, 0

ArcadeActiveCheck1:
    stx $0F
    tax
    lda ArcadeSpellActiveTbl,x
    bne @ok
    ldx $0F
    pla
    pla
    lda #$00
    rts
@ok:
    txa
    ldx $0F
    cmp #$00
    rts

.segment "BANK1_SPELLS"

; Check if spell Y (0..17) is owned. Returns A != 0 (Z=0) if owned, A = 0 (Z=1) if not.
; Preserves X and Y.
CheckSpellOwned2:
    cpy #$08
    bcs @arcade
    lda $077B,y
    rts
@arcade:
    tya
    sec
    sbc #$08
    jsr ArcadeActiveCheck1
    beq @waldo
    cmp #$06
    bcs @upper
    stx $0F
    tax
    lda $63B0,x             ; $63B1..$63B5 = f13, feud, dk, smb, duck
    ldx $0F
    jmp @chk_one
@upper:
    stx $0F
    tax
    lda $63B1,x             ; $63B7..$63BA = mm2, wheel, zelda, mtpo (X=6..9 -> $63B7..$63BA)
    ldx $0F
@chk_one:
    ora #$00
    bne @owned
    lda #$00
    rts
@waldo:
    lda $648B               ; WALDO_HAT
    cmp #$57
    beq @owned
    lda #$00
    rts
@owned:
    lda #$01
    rts

; Y = $0749 (8..17). Check ownership + magic cost, activate spell if affordable.
ArcadeCast2:
    iny
    cpy $074A
    bne :+
    jmp @done
:
    dey
    jsr CheckSpellOwned2
    bne :+
    jmp @done
:
    lda $0778               ; Magic Level (1..8)
    beq :+
    sec
    sbc #$01
    cmp #$08
    bcc :+
    lda #$07
:
    sta $00
    tya
    sec
    sbc #$08
    asl
    asl
    asl
    clc
    adc $00
    tax
    lda $0773               ; current magic
    sec
    sbc ArcadeSpellCostTbl,x
    bcs @afford
    cmp #$FF
    beq :+
    jmp @done
:
    lda #$00
@afford:
    sta $0773
    tya
    sec
    sbc #$08
    cmp #$08
    bcs @hi_bit
    tax
    lda SpellBitMask2,x
    ora ARCADE_ACTIVE_LO
    sta ARCADE_ACTIVE_LO
    jmp @cast_fx
@hi_bit:
    sec
    sbc #$08
    tax
    lda SpellBitMask2,x
    ora ARCADE_ACTIVE_HI
    sta ARCADE_ACTIVE_HI
@cast_fx:
    iny
    sty $074A               ; prevent re-cast in same room
    lda $074F
    ora #$80
    sta $074F
    lda #$20
    cpy #$0E
    bcc :+
    ora #$80                ; decor flash for higher-tier spells
:
    sta $074B
    lda #$04
    sta $EC                 ; magic cast SFX
    ; One-shot spell cast initialization (Y = spell + 1 = 9..18)
    cpy #$09                ; 8 = DECOY -> Y=9
    bne @chk_axe
    lda #$FF
    sta ARCADE_DECOY_TMR
    lda $4D
    sta ARCADE_DECOY_XLO
    lda $3B
    sta ARCADE_DECOY_XHI
    lda $29
    sta ARCADE_DECOY_Y
    jmp @done
@chk_axe:
    cpy #$0A                ; 9 = AXE -> Y=10
    bne @chk_barrel
    jsr LaunchAxe2
    jmp @done
@chk_barrel:
    cpy #$0C                ; 11 = BARREL -> Y=12
    bne @chk_lock
    lda #$80
    sta ARCADE_BARREL_TMR
    lda $4D
    sta ARCADE_BARREL_XLO
    lda $3B
    sta ARCADE_BARREL_XHI
    lda $29
    clc
    adc #$14
    sta ARCADE_BARREL_Y
    lda #$02
    ldx $9F
    cpx #$01
    beq :+
    lda #$FE
:
    sta ARCADE_BARREL_VX
    lda #$00
    sta ARCADE_BARREL_VY
    jmp @done
@chk_lock:
    cpy #$0E                ; 13 = LOCK -> Y=14
    bne @chk_lucky
    jsr AcquireLockTarget2
    jmp @done
@chk_lucky:
    cpy #$10                ; 15 = LUCKY -> Y=16
    bne @chk_clock
    lda #$03
    sta ARCADE_LUCKY_CNT
    jmp @done
@chk_clock:
    cpy #$11                ; 16 = CLOCK -> Y=17 ($11)
    bne @chk_star
    lda #$FF
    sta ARCADE_CLOCK_TMR
    ldx #$05
@snap_loop:
    lda $4E,x
    sta ARCADE_CLOCK_XY,x
    lda $3C,x
    sta ARCADE_CLOCK_XY+6,x
    lda $2A,x
    sta ARCADE_CLOCK_XY+12,x
    dex
    bpl @snap_loop
    bmi @done
@chk_star:
    cpy #$0D                ; 12 = STAR -> Y=13 ($0D)
    bne @done
    lda #$FF
    sta ARCADE_STAR_TMR
@done:
    jmp $FFC5

; Active per-frame tick for spells 8..17 (fast bitmask early-out per spell).
ArcadeTick2:
    lda ARCADE_ACTIVE_HI
    and #$01
    beq @clock_done
    lda ARCADE_CLOCK_TMR
    beq @clock_clr
    dec ARCADE_CLOCK_TMR
    bne @clock_step
@clock_clr:
    lda ARCADE_ACTIVE_HI
    and #$FE
    sta ARCADE_ACTIVE_HI
    jmp @clock_done
@clock_step:
    lda $0728
    bne @clock_done
    ldx #$05
@clk_loop:
    lda $B6,x
    cmp #$01
    bne @clk_next
    lda $040E,x
    bne @clk_next           ; allow hit knockback
    lda ARCADE_CLOCK_XY,x
    sta $4E,x
    lda ARCADE_CLOCK_XY+6,x
    sta $3C,x
    lda ARCADE_CLOCK_XY+12,x
    sta $2A,x
    lda #$00
    sta $71,x
    sta $057E,x
@clk_next:
    dex
    bpl @clk_loop
@clock_done:
    lda ARCADE_ACTIVE_LO
    and #$10
    bne :+
    jmp @star_done
:
    lda ARCADE_STAR_TMR
    beq @star_expire
    dec ARCADE_STAR_TMR
    bne @star_active
@star_expire:
    ; STAR expired: restore Barba's normal red/orange palette and clear active bit
    lda #$16
    sta $69D2
    lda #$27
    sta $69D8
    lda ARCADE_ACTIVE_LO
    and #$EF
    sta ARCADE_ACTIVE_LO
    jmp @star_done
@star_active:
    lda #$02
    sta $050C               ; contact invincibility
    lda $12
    lsr
    lsr
    and #$03
    tax
    lda StarLinePal2,x
    sta $69D2
    lda StarBodyPal2,x
    sta $69D8
    ; STAR touch-kill on non-boss enemies ($0728 == 0)
    lda $0728
    bne @star_done
    ldx #$05
@star_loop:
    ldy $B6,x
    dey
    bne @star_next
    lda $A1,x
    cmp #$02
    bcc @star_next
    cmp #$23
    beq @star_next
    asl
    tay
    lda $6E65,y
    ora $6E66,y
    beq @star_next
    ; Vertical overlap: |enemyY - playerY| < $24
    lda $2A,x
    sec
    sbc $29
    clc
    adc #$18
    cmp #$36
    bcs @star_next
    ; Horizontal overlap: |enemyX - playerX| < $18 (16-bit safe)
    lda $4E,x
    clc
    adc #$10
    tay
    lda $3C,x
    adc #$00
    pha
    tya
    sec
    sbc $4D
    tay
    pla
    sbc $3B
    bne @star_next
    tya
    cmp #$20
    bcs @star_next
    stx $10
    lda #$10
    sta $ED
    lda #$00
    sta $C2,x
    jsr $E880
    ldx $10
@star_next:
    dex
    bpl @star_loop
@star_done:
    lda ARCADE_ACTIVE_LO
    and #$40                ; BLADE active?
    beq @no_blade_pal
    lda ARCADE_STAR_TMR
    bne @no_blade_pal
    lda BARBA_GEAR
    and #$03
    cmp #$03                ; Mega Helmet equipped?
    bne @no_blade_pal
    lda #$12                ; Mega Man cobalt blue
    sta $69D2
    lda #$21                ; Mega Man cyan
    sta $69D8
@no_blade_pal:
    lda ARCADE_ACTIVE_LO
    and #$01
    beq :+
    jsr TickDecoy2
:
    lda ARCADE_ACTIVE_LO
    and #$02
    beq :+
    jsr TickAxe2
:
    lda ARCADE_ACTIVE_LO
    and #$08
    beq :+
    jsr TickBarrel2
:
    lda ARCADE_ACTIVE_LO
    and #$20
    beq :+
    jsr TickLock2
:
    lda ARCADE_ACTIVE_LO
    and #$40
    beq :+
    jsr TickBlade2
:
    jmp $FFC5

LaunchAxe2:
    lda #$3C
    sta ARCADE_AXE_TMR
    lda $4D
    sta ARCADE_AXE_XLO
    lda $3B
    sta ARCADE_AXE_XHI
    lda $29
    sta ARCADE_AXE_Y
    lda #$02
    ldx $9F
    cpx #$01
    beq :+
    lda #$FE
:
    sta ARCADE_AXE_VX
    lda #$FC                ; -4 px/frame initial upward arc
    sta ARCADE_AXE_VY
    lda #$00
    sta ARCADE_AXE_YSUB
    rts

AcquireLockTarget2:
    ldx #$05
@loop:
    lda $B6,x
    cmp #$01
    bne @next
    lda $A1,x
    cmp #$02
    bcc @next
    inx
    stx ARCADE_LOCK_SLOT
    rts
@next:
    dex
    bpl @loop
    lda #$00
    sta ARCADE_LOCK_SLOT
    rts

; Check overlap between ($00=Xlo, $01=Xhi, $02=Y) and enemy slot X (0..5).
; Returns Carry=1 on hit, Carry=0 on miss. Preserves X.
CheckBoxOverlap2:
    lda $B6,x
    cmp #$01
    bne @miss
    lda $040E,x
    bne @miss
    lda $A1,x
    cmp #$02
    bcc @miss
    cmp #$23
    beq @miss
    asl
    tay
    lda $6E65,y
    ora $6E66,y
    beq @miss
    ; |enemyY - $02| < 24
    lda $2A,x
    sec
    sbc $02
    clc
    adc #$10
    cmp #$24
    bcs @miss
    ; 16-bit |enemyX - ($00/$01)| < 20
    lda $4E,x
    clc
    adc #$10
    tay
    lda $3C,x
    adc #$00
    pha
    tya
    sec
    sbc $00
    tay
    pla
    sbc $01
    bne @miss
    tya
    cmp #$20
    bcs @miss
    sec
    rts
@miss:
    clc
    rts

; Deal A damage to enemy slot X (0..5), triggering $E880 death if HP <= 0.
; Preserves X.
HurtEnemyFromSpell2:
    sta $03
    lda #$30
    sta $040E,x
    lda #$10
    sta $ED
    lda $C2,x
    sec
    sbc $03
    beq @kill
    bcs @alive
@kill:
    lda #$00
    sta $C2,x
    stx $10
    jsr $E880
    ldx $10
    rts
@alive:
    sta $C2,x
    rts

; Draw 8x16 sprite at world ($00/$01, $02) into OAM $0200+X.
; Inputs: A = tile, Y = attr, X = OAM byte offset.
DrawScreenSprite2:
    pha
    lda $00
    sec
    sbc $072C
    sta $03                 ; screen X
    lda $01
    sbc $072A
    bne @hide
    lda $02
    sta $0200,x
    pla
    sta $0201,x
    tya
    sta $0202,x
    lda $03
    sta $0203,x
    rts
@hide:
    pla
    lda #$F8
    sta $0200,x
    rts

TickDecoy2:
    lda ARCADE_DECOY_TMR
    beq @clr_done
    dec ARCADE_DECOY_TMR
    bne @active
@clr_done:
    lda #$F8
    sta $02E0
    lda ARCADE_ACTIVE_LO
    and #$FE
    sta ARCADE_ACTIVE_LO
    rts
@active:
    lda ARCADE_DECOY_XLO
    sta $00
    lda ARCADE_DECOY_XHI
    sta $01
    lda ARCADE_DECOY_Y
    sta $02
    lda #$C9
    ldy #$01
    ldx #$E0
    jsr DrawScreenSprite2
    ldx #$05
@chk:
    jsr CheckBoxOverlap2
    bcs @detonate
    dex
    bpl @chk
@done:
    rts
@detonate:
    lda #$00
    sta ARCADE_DECOY_TMR
    lda #$F8
    sta $02E0
    lda ARCADE_ACTIVE_LO
    and #$FE
    sta ARCADE_ACTIVE_LO
    lda #$04
    sta $EC
    ldx #$05
@blast:
    jsr CheckBoxOverlap2
    bcc @bnext
    lda #$0C
    jsr HurtEnemyFromSpell2
@bnext:
    dex
    bpl @blast
    rts

TickAxe2:
    lda ARCADE_AXE_TMR
    bne @move
    lda $F5
    and #$40                ; B button launches new axe when ready
    bne :+
    rts
:
    jsr LaunchAxe2
@move:
    dec ARCADE_AXE_TMR
    bne @alive
    lda #$F8
    sta $02E4
    rts
@alive:
    ; X += VX (signed)
    lda ARCADE_AXE_VX
    bpl @pos_x
    clc
    adc ARCADE_AXE_XLO
    sta ARCADE_AXE_XLO
    bcs @y_step
    dec ARCADE_AXE_XHI
    jmp @y_step
@pos_x:
    clc
    adc ARCADE_AXE_XLO
    sta ARCADE_AXE_XLO
    bcc @y_step
    inc ARCADE_AXE_XHI
@y_step:
    lda ARCADE_AXE_Y
    clc
    adc ARCADE_AXE_VY
    sta ARCADE_AXE_Y
    lda ARCADE_AXE_YSUB
    clc
    adc #$40
    sta ARCADE_AXE_YSUB
    bcc @draw
    inc ARCADE_AXE_VY
@draw:
    lda ARCADE_AXE_XLO
    sta $00
    lda ARCADE_AXE_XHI
    sta $01
    lda ARCADE_AXE_Y
    sta $02
    jsr AxeSpriteSetup1
    ldx #$E4
    jsr DrawScreenSprite2
    ldx #$05
@hit:
    jsr CheckBoxOverlap2
    bcc @hnext
    lda #$08
    jsr HurtEnemyFromSpell2
@hnext:
    dex
    bpl @hit
@done:
    rts

TickBarrel2:
    lda ARCADE_BARREL_TMR
    beq @clr_done
    dec ARCADE_BARREL_TMR
    bne @alive
@clr_done:
    lda #$F8
    sta $02DC
    lda ARCADE_ACTIVE_LO
    and #$F7
    sta ARCADE_ACTIVE_LO
    rts
@alive:
    lda ARCADE_BARREL_VX
    bpl @pos_x
    clc
    adc ARCADE_BARREL_XLO
    sta ARCADE_BARREL_XLO
    bcs @draw
    dec ARCADE_BARREL_XHI
    jmp @draw
@pos_x:
    clc
    adc ARCADE_BARREL_XLO
    sta ARCADE_BARREL_XLO
    bcc @draw
    inc ARCADE_BARREL_XHI
@draw:
    lda ARCADE_BARREL_XLO
    sta $00
    lda ARCADE_BARREL_XHI
    sta $01
    lda ARCADE_BARREL_Y
    sta $02
    lda $12
    and #$0C
    asl
    asl
    asl
    asl
    ora #$01
    tay
    lda #$C9
    ldx #$DC
    jsr DrawScreenSprite2
    ldx #$05
@hit:
    jsr CheckBoxOverlap2
    bcc @hnext
    lda #$08
    jsr HurtEnemyFromSpell2
@hnext:
    dex
    bpl @hit
@done:
    rts

TickLock2:
    lda ARCADE_ACTIVE_LO
    and #$20
    beq @done
    ldx ARCADE_LOCK_SLOT
    beq @reacq
    dex
    lda $B6,x
    cmp #$01
    beq @have
@reacq:
    jsr AcquireLockTarget2
    ldx ARCADE_LOCK_SLOT
    beq @hide
    dex
@have:
    lda $4E,x
    sta $00
    lda $3C,x
    sta $01
    lda $2A,x
    sta $02
    ; Draw blinking crosshair when ($12 & 2) == 0
    lda $12
    and #$02
    bne @hide
    lda #$C9
    ldy #$01
    ldx #$E8
    jsr DrawScreenSprite2
    jmp @steer
@hide:
    lda #$F8
    sta $02E8
@steer:
    ldx ARCADE_LOCK_SLOT
    beq @done
    dex
    ; Steer active fireballs Y=0..1 toward locked enemy X ($4E,x) and Y ($2A,x)
    ldy #$01
@sloop:
    lda $8D,y
    cmp #$01
    bne @snext
    lda $5A,y
    cmp $4E,x
    beq @sy
    bcc @sright
    sec
    sbc #$02
    sta $5A,y
    jmp @sy
@sright:
    clc
    adc #$02
    sta $5A,y
@sy:
    lda $36,y
    cmp $2A,x
    beq @snext
    bcc @sdown
    sec
    sbc #$04
    sta $36,y
    jmp @snext
@sdown:
    clc
    adc #$04
    sta $36,y
@snext:
    dey
    bpl @sloop
@done:
    rts

TickBlade2:
    lda ARCADE_ACTIVE_LO
    and #$40
    beq @done
    ; 8-way D-pad steering on active fireballs (Y=0..1)
    ldy #$01
@bloop:
    lda $8D,y
    cmp #$01
    bne @bnext
    lda $F7
    and #$08                ; Up held
    beq @chk_dn
    lda $36,y
    sec
    sbc #$04
    sta $36,y
@chk_dn:
    lda $F7
    and #$04                ; Down held
    beq @bnext
    lda $36,y
    clc
    adc #$04
    sta $36,y
@bnext:
    dey
    bpl @bloop
@done:
    rts

StarLinePal2:
    .byte $16,$21,$2A,$14
StarBodyPal2:
    .byte $27,$37,$28,$24

.segment "BANK1"
; Ensure $0749 points to an owned spell (0..17) on menu open.
SpellMenuInit2:
    ldy $0749
    cpy #$12
    bcs @scan
    jsr CheckSpellOwned2
    bne @ok
@scan:
    ldy #$00
@loop:
    jsr CheckSpellOwned2
    bne @set
    iny
    cpy #$12
    bcc @loop
    ldy #$00
@set:
    sty $0749
@ok:
    lda $0749
    sta SPELL_OLD_SEL
    lda #$00
    sta SPELL_GEAR_SEL
    jmp $FFC5

.segment "BANK1_SPELLS"

; Compute left-edge metatile X ($01 = px & $F0, $00 = page), start col ($06 = 0..31),
; and nametable base ($07 = $20 or $24) for the 2-column pause box.
BoxOrigin2:
    lda $072C
    clc
    adc #SPELL_BOX_XOFF
    and #$F0
    sta $01
    lsr
    lsr
    lsr
    sta $06                 ; start col (0..31)
    lda $072A
    adc #$00
    sta $00
    and #$01
    asl
    asl
    clc
    adc #$20
    sta $07                 ; nt base ($20 or $24)
    rts

; Save 6x7 room attribute bytes covering the 13-metatile x 10-metatile box into SPELL_ATTR_BUF.
SpellMenuAttrSave2:
    ldx #(SPELL_ATTR_ROWS * SPELL_ATTR_COLS - 1)
    lda #$00
@clr:
    sta SPELL_ATTR_BUF,x
    dex
    bpl @clr
    lda $072C
    clc
    adc #SPELL_BOX_XOFF
    tax
    lda $072A
    adc #$00
    and #$03
    tay
    lda PageBaseLo2,y
    sta $0E
    lda PageBaseHi2,y
    sta $0F
    txa
    and #$E0
    lsr
    lsr
    lsr
    lsr
    tay
    ldx #$00
    lda #SPELL_ATTR_COLS
    sta $00
@col_loop:
    lda #$00
    sta $01
@half_loop:
    lda #$0C
    sta $02
@row_loop:
    jsr @store_bits
    tya
    clc
    adc #$10
    tay
    asl
    asl
    asl
    asl
    bcs @same_attr_row
    txa
    clc
    adc #SPELL_ATTR_COLS
    tax
@same_attr_row:
    dec $02
    bne @row_loop
    tya
    sec
    sbc #$BF
    tay
    and #$0F
    bne @no_screen_wrap
    lda $0E
    clc
    adc #$D0
    sta $0E
    bcc :+
    inc $0F
:
    tya
    sec
    sbc #$10
    tay
@no_screen_wrap:
    txa
    sec
    sbc #(SPELL_ATTR_ROWS * SPELL_ATTR_COLS)
    tax
    lda $01
    eor #$80
    sta $01
    bne @half_loop
    inx
    dec $00
    bne @col_loop
    jmp $FFC5

@store_bits:
    tya
    asl
    asl
    asl
    asl
    lda ($0E),y
    and #$C0
    bcs @bot_row
    asl
    rol
    rol
    bit $01
    bpl @or_attr
    asl
    asl
    jmp @or_attr
@bot_row:
    bit $01
    bmi @or_attr
    lsr
    lsr
@or_attr:
    ora SPELL_ATTR_BUF,x
    sta SPELL_ATTR_BUF,x
    rts

; Emit 1 attribute row (7 bytes) into $0363,y on even $0525 (0,2,...,18).
; Inputs: $0E = 0 (draw: mask box quadrants to palette 00), nonzero (restore room attr).
;         Y = current $0363 offset (updated on return).
SpellEmitAttrRow2:
    sty $0F
    lda $0525
    lsr
    clc
    adc #$01                ; mr = 1..10
    lsr                     ; A = ar (0..5), Carry = ar_half (0=top, 1=bot)
    sta $02
    lda #$00
    rol
    sta $03                 ; ar_half (0 or 1)
    lda $02
    asl
    asl
    asl
    clc
    adc #$C8
    sta $04                 ; PPU attr low base ($C8, $D0, $D8, $E0, $E8, $F0)
    ldy $02
    lda AttrRowOff7,y
    sta $09                 ; SPELL_ATTR_BUF row base (0, 7, ..., 35)
    lda $072C
    clc
    adc #SPELL_BOX_XOFF
    pha
    lda $072A
    adc #$00
    and #$01
    asl
    asl
    adc #$23
    sta $0A                 ; start_attr_nt ($23 or $27)
    pla
    pha
    and #$10
    sta $0B                 ; is_odd_scroll (0 or $10)
    pla
    lsr
    lsr
    lsr
    lsr
    lsr
    sta $0C                 ; start_attr_col (0..7)
    ldx #$00
    ldy $09
@attr_loop:
    lda #$0F
    sta $05                 ; bottom-half mask
    lda #$F0
    sta $06                 ; top-half mask
    lda $0B
    beq @even_scr
    cpx #$00
    bne @masks_ok
    lda #$3F
    sta $05
    lda #$F3
    bne @set_06
@even_scr:
    cpx #(SPELL_ATTR_COLS - 1)
    bne @masks_ok
    lda #$CF
    sta $05
    lda #$FC
@set_06:
    sta $06
@masks_ok:
    lda $0E
    bne @do_restore
    lda $03
    bne @draw_bot
    lda $06
    bne @apply_draw
@draw_bot:
    lda $05
@apply_draw:
    and SPELL_ATTR_BUF,y
    sta SPELL_ATTR_BUF,y
    jmp @store_tmp
@do_restore:
    lda $02
    beq @full_rest
    lda $03
    beq @full_rest
    lda SPELL_ATTR_BUF,y
    and $06
    jmp @store_tmp
@full_rest:
    lda SPELL_ATTR_BUF,y
@store_tmp:
    sta SPELL_ATTR_TMP,x
    iny
    inx
    cpx #SPELL_ATTR_COLS
    bcc @attr_loop
    ldy $0F
    lda #$08
    sec
    sbc $0C                 ; k = 8 - start_attr_col
    cmp #SPELL_ATTR_COLS
    bcc @split_attr
    lda $0A
    sta $0363,y
    iny
    lda $04
    ora $0C
    sta $0363,y
    iny
    lda #SPELL_ATTR_COLS
    sta $0363,y
    iny
    ldx #$00
@s_loop:
    lda SPELL_ATTR_TMP,x
    sta $0363,y
    iny
    inx
    cpx #SPELL_ATTR_COLS
    bcc @s_loop
    rts
@split_attr:
    sta $05                 ; chunk 1 count (1..6)
    lda $0A
    sta $0363,y
    iny
    lda $04
    ora $0C
    sta $0363,y
    iny
    lda $05
    sta $0363,y
    iny
    ldx #$00
@c1_loop:
    lda SPELL_ATTR_TMP,x
    sta $0363,y
    iny
    inx
    dec $05
    bne @c1_loop
    lda $0A
    eor #$04
    sta $0363,y
    iny
    lda $04
    sta $0363,y
    iny
    lda $0C
    sec
    sbc #$01
    sta $0363,y
    iny
@c2_loop:
    lda SPELL_ATTR_TMP,x
    sta $0363,y
    iny
    inx
    cpx #SPELL_ATTR_COLS
    bcc @c2_loop
    rts

; Build 26-tile row buffer at $66A0 (SPELL_ROW_BUF0) for tile row 0..19.
; Input: A = tile row (0..19).
BuildMenuTileRow2:
    cmp #$00
    beq @do_split
    cmp #$02
    beq @do_split
    cmp #$0D
    bne :+
@do_split:
    jmp @split_border
:
    cmp #$13
    bne :+
    jmp @bot_border
:
    cmp #$01
    bne :+
    jmp @header
:
    cmp #$0E
    bcc :+
    jmp @tray
:
    ; Spell row = A - 3 (0..9)
    sec
    sbc #$03
    sta $03                 ; row 0..9
    ldx #$00
    lda #$CC
    sta SPELL_ROW_BUF0,x
    inx
    ; Left column spell index = row (0..7; 8..9 blank)
    ldy $03
    cpy #$08
    bcs @left_blank
    jsr CheckSpellOwned2
    beq @left_blank
    lda #$F4
    cpy $0749
    bne :+
    lda #$FA
:
    sta SPELL_ROW_BUF0,x
    inx
    jsr CopyHyruleName7
    lda #$CF
    sta SPELL_ROW_BUF0,x
    inx
    ldy $03
    jsr GetSpellCostDisp2
    jsr FormatCost3
    jmp @mid_sep
@left_blank:
    lda #$F4
    ldy #12
@lbl:
    sta SPELL_ROW_BUF0,x
    inx
    dey
    bne @lbl
@mid_sep:
    lda #$CC
    sta SPELL_ROW_BUF0,x
    inx
    ; Right column spell index = row + 8 (8..17)
    lda $03
    clc
    adc #$08
    tay
    jsr CheckSpellOwned2
    beq @right_blank
    lda #$F4
    cpy $0749
    bne :+
    lda #$FA
:
    sta SPELL_ROW_BUF0,x
    inx
    tya
    sec
    sbc #$08
    tay
    jsr CopyArcadeName6
    lda #$CF
    sta SPELL_ROW_BUF0,x
    inx
    lda $03
    clc
    adc #$08
    tay
    jsr GetSpellCostDisp2
    jsr FormatCost3
    jmp @right_end
@right_blank:
    lda #$F4
    ldy #11
@rbl:
    sta SPELL_ROW_BUF0,x
    inx
    dey
    bne @rbl
@right_end:
    lda #$CC
    sta SPELL_ROW_BUF0,x
    rts

@split_border:
    ldx #$00
    lda #$CA
    sta SPELL_ROW_BUF0,x
    inx
    lda #$CB
    ldy #12
@sb1:
    sta SPELL_ROW_BUF0,x
    inx
    dey
    bne @sb1
    lda #$CA
    sta SPELL_ROW_BUF0,x
    inx
    lda #$CB
    ldy #11
@sb2:
    sta SPELL_ROW_BUF0,x
    inx
    dey
    bne @sb2
    lda #$CA
    sta SPELL_ROW_BUF0,x
    rts

@bot_border:
    ldx #$00
    lda #$CA
    sta SPELL_ROW_BUF0,x
    inx
    lda #$CB
    ldy #24
@bbl:
    sta SPELL_ROW_BUF0,x
    inx
    dey
    bne @bbl
    lda #$CA
    sta SPELL_ROW_BUF0,x
    rts

@header:
    ldx #$00
@hloop:
    lda MenuHeaderRow26,x
    sta SPELL_ROW_BUF0,x
    inx
    cpx #SPELL_BOX_TILES
    bcc @hloop
    rts

@tray:
    sta $03                 ; row 14..18 ($0E..$12)
    ldx #$00
    lda #$CC
    sta SPELL_ROW_BUF0,x
    inx
    lda #$F4
    ldy #24
@tfill:
    sta SPELL_ROW_BUF0,x
    inx
    dey
    bne @tfill
    lda #$CC
    sta SPELL_ROW_BUF0,x
    lda $03
    cmp #$0E
    bne @chk_15
    jmp DrawGearRow14_1
@chk_15:
    cmp #$0F
    bne @chk_17
    jmp DrawGearRow15_1
@chk_17:
    cmp #$11
    bne @tray_done
    lda #$96                ; Barba head
    sta SPELL_ROW_BUF0+2
    lda #$FC                ; x mark
    sta SPELL_ROW_BUF0+3
    lda $0700
    and #$0F
    ora #$D0
    sta SPELL_ROW_BUF0+4
    lda #$B9                ; Key icon
    sta SPELL_ROW_BUF0+6
    lda #$FC                ; x mark
    sta SPELL_ROW_BUF0+7
    lda $0793
    and #$0F
    ora #$D0
    sta SPELL_ROW_BUF0+8
    lda #$CD                ; Crystal icon
    sta SPELL_ROW_BUF0+10
    lda #$FC                ; x mark
    sta SPELL_ROW_BUF0+11
    lda $0794
    and #$0F
    ora #$D0
    sta SPELL_ROW_BUF0+12
@tray_done:
    rts

; Copy 7-char Hyrule spell name (Y = 0..7) into SPELL_ROW_BUF0,x..x+6. Advances X by 7.
CopyHyruleName7:
    sty $04
    tya
    asl
    asl
    asl
    sec
    sbc $04
    tay
    lda #$07
    sta $04
@loop:
    lda HyruleSpellNames,y
    sta SPELL_ROW_BUF0,x
    inx
    iny
    dec $04
    bne @loop
    rts

; Copy 6-char Arcade spell name (Y = 0..9) into SPELL_ROW_BUF0,x..x+5. Advances X by 6.
CopyArcadeName6:
    tya
    asl
    sta $04
    asl
    clc
    adc $04                 ; Y * 6
    tay
    lda #$06
    sta $04
@loop:
    lda ArcadeSpellNames,y
    sta SPELL_ROW_BUF0,x
    inx
    iny
    dec $04
    bne @loop
    rts

; Return displayed MP cost (raw >> 1) for spell Y (0..17) in A. Preserves X and Y.
GetSpellCostDisp2:
    sty $04
    lda $0778               ; Magic Level (1..8)
    beq :+
    sec
    sbc #$01
    cmp #$08
    bcc :+
    lda #$07
:
    sta $05
    tya
    asl
    asl
    asl
    clc
    adc $05
    tay
    lda HyruleSpellCostTbl,y
    lsr
    ldy $04
    rts

; Format A (0..127) into 3 tiles at SPELL_ROW_BUF0,x..x+2 with leading-zero dots ($CF). Advances X by 3.
FormatCost3:
    ldy #$00
    sty $04                 ; nonzero hundreds flag
    cmp #100
    bcc @lt100
    sec
    sbc #100
    inc $04
    ldy #$D1
    bne @put_h
@lt100:
    ldy #$CF
@put_h:
    pha
    tya
    sta SPELL_ROW_BUF0,x
    inx
    pla
    ldy #$00
@tens:
    cmp #10
    bcc @tens_done
    sbc #10
    iny
    bne @tens
@tens_done:
    pha
    tya
    bne @tens_digit
    lda $04
    bne @tens_digit
    lda #$CF
    bne @put_t
@tens_digit:
    tya
    ora #$D0
@put_t:
    sta SPELL_ROW_BUF0,x
    inx
    pla
    ora #$D0
    sta SPELL_ROW_BUF0,x
    inx
    rts

; Emit one 26-tile nametable row from SPELL_ROW_BUF0+$08 into $0363,Y.
; Inputs: $05 = tile row (6..25), $06 = start col (0..31), $07 = nametable base ($20 or $24)
;         $08 = start offset in SPELL_ROW_BUF0 (0 or 26), Y = $0362 offset.
EmitNtRow2:
    lda $05
    lsr
    lsr
    lsr
    clc
    adc $07
    sta $09                 ; nt_hi
    lda $05
    and #$07
    asl
    asl
    asl
    asl
    asl
    ora $06
    sta $0A                 ; nt_lo
    ; Check if col + 26 > 32
    lda #32
    sec
    sbc $06
    cmp #SPELL_BOX_TILES
    bcs @single
    ; Split: first chunk = A bytes, second chunk = 26 - A bytes
    sta $0B                 ; k
    lda $09
    sta $0363,y
    iny
    lda $0A
    sta $0363,y
    iny
    lda $0B
    sta $0363,y
    iny
    ldx $08
@c1:
    lda SPELL_ROW_BUF0,x
    sta $0363,y
    inx
    iny
    dec $0B
    bne @c1
    ; Second chunk at (nt_hi ^ $04), (nt_lo & $E0)
    lda $09
    eor #$04
    sta $0363,y
    iny
    lda $0A
    and #$E0
    sta $0363,y
    iny
    lda $06
    sec
    sbc #(32 - SPELL_BOX_TILES)
    sta $0B
    sta $0363,y
    iny
@c2:
    lda SPELL_ROW_BUF0,x
    sta $0363,y
    inx
    iny
    dec $0B
    bne @c2
    rts
@single:
    lda $09
    sta $0363,y
    iny
    lda $0A
    sta $0363,y
    iny
    lda #SPELL_BOX_TILES
    sta $0363,y
    iny
    ldx $08
    lda #SPELL_BOX_TILES
    sta $0B
@s1:
    lda SPELL_ROW_BUF0,x
    sta $0363,y
    inx
    iny
    dec $0B
    bne @s1
    rts

; Draw 1 tile row $0525 (0..19) of 2-column menu.
SpellMenuDraw2:
    jsr BoxOrigin2
    lda $0525
    jsr BuildMenuTileRow2
    lda $0525
    clc
    adc #$06                ; screen tile row (6..25)
    sta $05
    ldy $0362
    lda #$00
    sta $08
    jsr EmitNtRow2
    lda $0525
    lsr
    bcs @no_attr
    lda #$00
    sta $0E                 ; draw mode (mask to palette 00)
    jsr SpellEmitAttrRow2
@no_attr:
    lda #$FF
    sta $0363,y
    sty $0362
    lda #$01
    sta $0725
    inc $0525
    lda $0525
    cmp #SPELL_BOX_TILE_ROWS
    bcc :+
    inc $0524
:
    jmp $FFC5

; Restore 1 tile row $0525 (19..0) from SPELL_ROW_BUF0/1 prepared by SpellMenuRestore0.
SpellMenuRestore2:
    jsr BoxOrigin2
    lda $0525
    clc
    adc #$06
    sta $05
    lda $0525
    lsr
    lda #$00
    bcc :+
    lda #SPELL_BOX_TILES
:
    sta $08
    ldy $0362
    jsr EmitNtRow2
    lda $0525
    lsr
    bcs @no_attr
    lda #$01
    sta $0E                 ; restore mode
    jsr SpellEmitAttrRow2
@no_attr:
    lda #$FF
    sta $0363,y
    sty $0362
    lda #$01
    sta $0725
    jmp $FFC5

; Handle Start, Select (Gear toggle), Up/Down, Left/Right cursor in 2-column Spell Menu.
SpellMenuInput2:
    lda $0744
    and #$20
    sta $00
    lda $F7
    and #$20                ; Select edge toggles Spells <-> Gear
    beq @no_sel_edge
    cmp $00
    beq @no_sel_edge
    jmp GearToggleFocus1
@no_sel_edge:
    lda SPELL_GEAR_SEL
    beq @spells_mode
    jmp GearMenuInput1
@spells_mode:
    ; Check if any spell 0..17 is owned
    ldy #$00
@any:
    jsr CheckSpellOwned2
    bne @has_any
    iny
    cpy #$12
    bcc @any
    jmp @chk_start
@has_any:
    ; Check D-pad edge/repeat ($F7 = held, $0744 = prev)
    lda $F7
    and #$0F
    bne :+
    jmp @chk_start
:
    sta $00
    lda $0744
    and #$0F
    cmp $00
    bne @new_dir
    dec $0487
    beq :+
    jmp @chk_start
:
    lda #$07
    sta $0487
    bne @do_dir
@new_dir:
    lda #$10
    sta $0487
@do_dir:
    lda $00
    and #$0C                ; Up ($08) or Down ($04)
    beq @chk_lr
    and #$08
    bne @dir_up
    ; Down: wrap within active column (0..7 or 8..17)
    ldy $0749
    cpy #$08
    bcs @dn_r
@dn_l:
    iny
    cpy #$08
    bcc :+
    ldy #$00
:
    jsr CheckSpellOwned2
    beq @dn_l
    jmp @moved
@dn_r:
    iny
    cpy #$12
    bcc :+
    ldy #$08
:
    jsr CheckSpellOwned2
    beq @dn_r
    jmp @moved
@dir_up:
    ldy $0749
    cpy #$08
    bcs @up_r
@up_l:
    dey
    bpl :+
    ldy #$07
:
    jsr CheckSpellOwned2
    beq @up_l
    jmp @moved
@up_r:
    dey
    cpy #$08
    bcs :+
    ldy #$11
:
    jsr CheckSpellOwned2
    beq @up_r
    jmp @moved
@chk_lr:
    lda $00
    and #$03                ; Left ($02) or Right ($01)
    beq @chk_start
    ldy $0749
    cpy #$08
    bcs @in_right
    ; In left (0..7) -> move to right (8..15)
    tya
    clc
    adc #$08
    tay
    jmp @lr_scan
@in_right:
    ; In right (8..17) -> move to left (0..7, clamp 16..17 -> 7)
    cpy #$10
    bcc :+
    ldy #$0F
:
    tya
    sec
    sbc #$08
    tay
@lr_scan:
    jsr CheckSpellOwned2
    bne @moved
    ; Scan up/down in target column (0..7 or 8..17) if exact slot unowned
    sty $01
    lda $01
    cmp #$08
    bcs @scan_r
    ldy #$00
@sl:
    jsr CheckSpellOwned2
    bne @moved
    iny
    cpy #$08
    bcc @sl
    beq @chk_start
@scan_r:
    ldy #$08
@sr:
    jsr CheckSpellOwned2
    bne @moved
    iny
    cpy #$12
    bcc @sr
@no_dir:
    jmp @chk_start
@moved:
    cpy $0749
    beq @chk_start
    sty $0749
    lda #$10
    sta $EF                 ; cursor SFX
    ; Update old cursor -> $F4 and new cursor -> $FA via $0302
    jsr BoxOrigin2
    ldy #$00
    lda SPELL_OLD_SEL
    ldx #$F4
    jsr EmitCursorTile2
    lda $0749
    sta SPELL_OLD_SEL
    ldx #$FA
    jsr EmitCursorTile2
    lda #$FF
    sta $0302,y
@chk_start:
    lda $0744
    and #$10
    sta $00
    lda $F7
    and #$10
    beq @ret
    cmp $00
    beq @ret
    inc $0524
@ret:
    jmp $FFC5

; Write a 1-tile PPU update at $0302,y for spell A (0..17) with tile X ($F4 or $FA).
EmitCursorTile2:
    pha
    cmp #$08
    bcs @right_col
    ; Left col: col_off = 1, row = 9 + A
    clc
    adc #$09
    sta $05                 ; row
    lda #$01
    jmp EmitBoxColOk2
@right_col:
    ; Right col: col_off = 14 ($0E), row = 9 + (A - 8) = 1 + A
    clc
    adc #$01
    sta $05
    lda #$0E
    bne EmitBoxColOk2
EmitBoxTile2:
    pha
EmitBoxColOk2:
    clc
    adc $06
    cmp #32
    bcc @no_wrap
    sec
    sbc #32
    sta $03                 ; col (0..31)
    lda $07
    eor #$04
    sta $04                 ; nt_hi_base
    jmp @addr
@no_wrap:
    sta $03
    lda $07
    sta $04
@addr:
    lda $05
    lsr
    lsr
    lsr
    clc
    adc $04
    sta $0302,y
    iny
    lda $05
    and #$07
    asl
    asl
    asl
    asl
    asl
    ora $03
    sta $0302,y
    iny
    lda #$01
    sta $0302,y
    iny
    txa
    sta $0302,y
    iny
    pla
    rts

SpellBitMask2:
    .byte $01,$02,$04,$08,$10,$20,$40,$80

PageBaseLo2:
    .byte $00,$D0,$A0,$70
PageBaseHi2:
    .byte $60,$60,$61,$62
.segment "BANK1"
AttrRowOff7:
    .byte 0,7,14,21,28,35
.segment "BANK1_SPELLS"

; 8 Hyrule + 10 Arcade spells x 8 magic levels (cost in MP units; displayed = cost >> 1)
HyruleSpellCostTbl:
    .byte $40,$30,$30,$20,$20,$20,$20,$20 ; 0: SCALES
    .byte $60,$50,$40,$40,$28,$20,$18,$10 ; 1: JUMP
    .byte $8C,$8C,$78,$78,$64,$64,$64,$64 ; 2: LIFE
    .byte $A0,$A0,$78,$78,$50,$50,$50,$50 ; 3: WYRMLNG
    .byte $F0,$A0,$78,$3C,$20,$20,$20,$20 ; 4: METEOR
    .byte $F0,$F0,$A0,$60,$50,$40,$30,$20 ; 5: REFLECT
    .byte $F0,$E0,$C0,$A0,$60,$40,$30,$20 ; 6: SPELL
    .byte $F0,$F0,$F0,$F0,$F0,$F0,$C8,$80 ; 7: INFERNO
ArcadeSpellCostTbl:
    .byte 16,14,12,10, 8, 8, 6, 6  ; 8:  DECOY
    .byte 24,20,18,16,14,12,10, 8  ; 9:  AXE
    .byte 32,28,24,22,20,18,16,14  ; 10: DOUBLE
    .byte 32,28,24,20,18,16,14,12  ; 11: BARREL
    .byte 48,44,40,36,32,28,24,20  ; 12: STAR
    .byte 24,22,20,18,16,14,12,10  ; 13: LOCK
    .byte 40,36,32,28,24,22,20,18  ; 14: BLADE
    .byte 24,20,18,16,14,12,10, 8  ; 15: LUCKY
    .byte 56,52,48,44,40,36,32,28  ; 16: CLOCK
    .byte 48,44,40,36,32,28,24,20  ; 17: HEAVY

.segment "BANK1_SOULS"
MenuHeaderRow26:
    .byte $CC,$F4,$F4,$F4,$E1,$F2,$EB,$EE,$E5,$DE,$F4,$F4,$F4 ; |   HYRULE   
    .byte $CC,$F4,$F4,$DA,$EB,$DC,$DA,$DD,$DE,$F4,$F4,$F4,$CC ; |  ARCADE   |

.segment "BANK1_SPELLS"
; 8 x 7 = 56 bytes (Z2 uppercase $DA..$F3, dot leader $CF)
HyruleSpellNames:
    .byte $EC,$DC,$DA,$E5,$DE,$EC,$CF ; SCALES.
    .byte $E3,$EE,$E6,$E9,$CF,$CF,$CF ; JUMP...
    .byte $E5,$E2,$DF,$DE,$CF,$CF,$CF ; LIFE...
    .byte $F0,$F2,$EB,$E6,$E5,$E7,$E0 ; WYRMLNG
    .byte $E6,$DE,$ED,$DE,$E8,$EB,$CF ; METEOR.
    .byte $EB,$DE,$DF,$E5,$DE,$DC,$ED ; REFLECT
    .byte $EC,$E9,$DE,$E5,$E5,$CF,$CF ; SPELL..
    .byte $E2,$E7,$DF,$DE,$EB,$E7,$E8 ; INFERNO

; 10 x 6 = 60 bytes (Z2 uppercase $DA..$F3, dot leader $CF)
ArcadeSpellNames:
    .byte $DD,$DE,$DC,$E8,$F2,$CF ; DECOY.
    .byte $DA,$F1,$DE,$CF,$CF,$CF ; AXE...
    .byte $DD,$E8,$EE,$DB,$E5,$DE ; DOUBLE
    .byte $DB,$DA,$EB,$EB,$DE,$E5 ; BARREL
    .byte $EC,$ED,$DA,$EB,$CF,$CF ; STAR..
    .byte $E5,$E8,$DC,$E4,$CF,$CF ; LOCK..
    .byte $DB,$E5,$DA,$DD,$DE,$CF ; BLADE.
    .byte $E5,$EE,$DC,$E4,$F2,$CF ; LUCKY.
    .byte $DC,$E5,$E8,$DC,$E4,$CF ; CLOCK.
    .byte $E1,$DE,$DA,$EF,$F2,$CF ; HEAVY.

.segment "BANK1_SOULS"
GearSpellIdTbl: .byte 8, 9, 14, 11, 17
GearRowTbl:     .byte 14, 14, 14, 15, 15
GearCurColTbl:  .byte 2, 9, 17, 2, 9
GearBdgColTbl:  .byte 6, 14, 22, 6, 14
GearBitTbl:     .byte $01, $02, $03, $10, $20
GearNameTbl:
    .byte $E1,$DA,$ED,$F4 ; HAT
    .byte $E6,$DA,$EC,$E4 ; MASK
    .byte $E1,$DE,$E5,$E6 ; HELM
    .byte $ED,$E2,$DE,$F4 ; TIE
    .byte $DB,$DE,$E5,$ED ; BELT

.segment "BANK1_SPELLS"
; Return Z=0 if gear slot X (0..4) is equipped, Z=1 otherwise. Preserves X.
CheckGearEquipped1:
    lda BARBA_GEAR
    bmi @have
    lda $648B
    cmp #$57
    bne @no
    lda #$01
@have:
    cpx #$03
    bcs @body
    and #$03
    sec
    sbc #$01
    stx $0C
    cmp $0C
    beq @yes
@no:
    lda #$00
    rts
@body:
    and GearBitTbl,x
    rts
@yes:
    lda #$01
    rts

.segment "BANK1_SOULS"
DrawGearRow14_1:
    ldx #$00
    lda #$03
    bne DrawGearRange1
DrawGearRow15_1:
    ldx #$03
    lda #$05
DrawGearRange1:
    sta $02                 ; end slot (safe: SpellMenuDraw2 uses $05/$06/$07)
@loop:
    stx $00                 ; cur slot
    ldy GearSpellIdTbl,x
    jsr CheckSpellOwned2
    beq @next
    ldx $00
    ldy GearCurColTbl,x
    iny
    txa
    asl
    asl
    tax
    lda #$04
    sta $01                 ; char count
@name:
    lda GearNameTbl,x
    sta SPELL_ROW_BUF0,y
    inx
    iny
    dec $01
    bne @name
    ldx $00
    jsr CheckGearEquipped1
    beq @next
    ldy GearBdgColTbl,x
    lda #$F8
    sta SPELL_ROW_BUF0,y
@next:
    ldx $00
    inx
    cpx $02
    bcc @loop
    rts

; Emit tile X at gear slot A (0..4) cursor/badge (C=0 cursor, C=1 badge) into $0302,y.
EmitGearCell1:
    php
    stx $08
    tax
    lda GearRowTbl,x
    clc
    adc #$06
    sta $05
    plp
    bcc @cur
    lda GearBdgColTbl,x
    bcs @emit
@cur:
    lda GearCurColTbl,x
@emit:
    ldx $08
    jmp EmitBoxTile2

.segment "BANK1_GEAR"
GearToggleFocus1:
    jsr BoxOrigin2
    ldy #$00
    lda SPELL_GEAR_SEL
    bne @to_spells
    ldx #$00
@find:
    stx $0D
    ldy GearSpellIdTbl,x
    jsr CheckSpellOwned2
    bne @found
    ldx $0D
    inx
    cpx #$05
    bcc @find
    jmp $FFC5
@found:
    ldy #$00
    lda $0749
    ldx #$F4
    jsr EmitCursorTile2
    ldx $0D
    txa
    clc
    adc #$01
    sta SPELL_GEAR_SEL
    txa
    ldx #$FA
    clc
    jsr EmitGearCell1
@sfx_done:
    lda #$FF
    sta $0302,y
    lda #$10
    sta $EF
    jmp $FFC5
@to_spells:
    sec
    sbc #$01
    ldx #$F4
    clc
    jsr EmitGearCell1
    lda #$00
    sta SPELL_GEAR_SEL
    lda $0749
    ldx #$FA
    jsr EmitCursorTile2
    jmp @sfx_done

.segment "BANK1_GEAR"
GearMenuInput1:
    lda $F7
    and #$0F
    bne :+
    jmp GearCheckAB1
:
    sta $00
    lda $0744
    and #$0F
    cmp $00
    bne :+
    jmp GearCheckAB1
:
    lda $00
    and #$0A                ; Up or Left -> prev
    bne @prev
    lda #$01
    .byte $2C
@prev:
    lda #$FF
    sta $09                 ; step (+1 or -1)
    lda SPELL_GEAR_SEL
    sec
    sbc #$01
    sta $0D
@step:
    lda $0D
    clc
    adc $09
    bpl :+
    lda #$04
:
    cmp #$05
    bcc :+
    lda #$00
:
    sta $0D
    tax
    ldy GearSpellIdTbl,x
    jsr CheckSpellOwned2
    beq @step
    jsr BoxOrigin2
    ldy #$00
    lda SPELL_GEAR_SEL
    sec
    sbc #$01
    ldx #$F4
    clc
    jsr EmitGearCell1
    lda $0D
    clc
    adc #$01
    sta SPELL_GEAR_SEL
    lda $0D
    ldx #$FA
    clc
    jsr EmitGearCell1
    lda #$FF
    sta $0302,y
    lda #$10
    sta $EF
    jmp $FFC5

.segment "BANK1_SOULS"
GearCheckAB1:
    lda $F7
    and #$C0                ; A or B edge
    bne :+
    jmp @chk_start
:
    lda $0744
    and #$C0
    beq :+
    jmp @chk_start
:
    lda BARBA_GEAR
    bmi @inited
    lda $648B
    cmp #$57
    bne :+
    lda #$81
    .byte $2C
:
    lda #$80
@inited:
    sta $00
    lda SPELL_GEAR_SEL
    sec
    sbc #$01
    tax
    cpx #$03
    bcs @toggle_body
    lda $00
    and #$03
    cmp GearBitTbl,x
    bne @equip_head
    lda $00
    and #$FC
    jmp @store_gear
@equip_head:
    lda $00
    and #$FC
    ora GearBitTbl,x
    jmp @store_gear
@toggle_body:
    lda $00
    eor GearBitTbl,x
@store_gear:
    sta BARBA_GEAR
    jsr BoxOrigin2
    ldy #$00
    ldx #$00
@bdg_loop:
    stx $0D
    tya
    pha
    ldy GearSpellIdTbl,x
    jsr CheckSpellOwned2
    beq @bdg_skip
    ldx $0D
    jsr CheckGearEquipped1
    ldx #$F4
    beq :+
    ldx #$F8
:
    pla
    tay
    lda $0D
    sec
    jsr EmitGearCell1
    jmp @bdg_next
@bdg_skip:
    pla
    tay
@bdg_next:
    ldx $0D
    inx
    cpx #$05
    bcc @bdg_loop
    lda #$FF
    sta $0302,y
    lda #$10
    sta $EF
    jmp $FFC5
@chk_start:
    lda $0744
    and #$10
    sta $00
    lda $F7
    and #$10
    beq @ret
    cmp $00
    beq @ret
    inc $0524
@ret:
    jmp $FFC5
