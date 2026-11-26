; In-ROM Rauru <-> Where's Waldo? portal (enabled with -D WALDO_PORTAL=1).
; Runs on NES 2.0 Mapper 176 (FK23C):
;   PRG: 0..256KB Barba, 256..512KB Waldo
;   CHR: 0..256KB Barba, 256..512KB Waldo
;   WRAM ($A001): bank 0 = Barba, bank 1 = snapshot, bank 2 = Waldo

PORTAL_DEBOUNCE  = $6478
MELT_FRAME       = $6479
MELT_WIPE        = $647A
MELT_BAND        = $647B
MELT_NT          = $647C
MELT_BASE        = $647D
WALDO_RETURN_MSG = $647E
WALDO_ENTER_MSG  = $647F
MELT_DIR         = $6480
PORTAL_GAME      = $648A
WALDO_HAT        = $648B
WALDO_HAT_MAGIC  = $57
SUBGAME_REWARDS  = $63B0   ; 16 bytes ($63B0-$63BF): per-slot completion flags
ARCADE_DLG_BUF   = $63C0   ; 64 bytes ($63C0-$63FF): dynamic booth enter dialogue
ARCADE_SIGN_LO   = $6360   ; 1 byte: arcade door marquee drawn bitmask (slots 0..7)
ARCADE_SIGN_HI   = $6361   ; 1 byte: arcade door marquee drawn bitmask (slots 8..15)

.macro WaldoLine text, terminator
    .assert .strlen(text) <= 14, error, "Waldo dialogue line is too wide"
    .repeat .strlen(text), character
        .if .strat(text, character) = ' '
            .byte $F4
        .elseif .strat(text, character) = '.'
            .byte $CF
        .elseif .strat(text, character) = '!'
            .byte $36
        .elseif .strat(text, character) = $3F   ; '?' (vanilla font, bank-7 tile $34)
            .byte $34
        .elseif .strat(text, character) = $27   ; apostrophe (TEXT_GLYPHS, bank-7 tile $35)
            .byte $35
        .elseif .strat(text, character) >= 'A' .and .strat(text, character) <= 'Z'
            .byte .strat(text, character) - 'A' + $DA
        .elseif .strat(text, character) >= '0' .and .strat(text, character) <= '9'
            .byte .strat(text, character) - '0' + $D0
        .else
            .error "Unsupported Waldo dialogue character"
        .endif
    .endrepeat
    .byte terminator
.endmacro

.macro ArcadeSignLine text
    .assert .strlen(text) = 7, error, "Arcade sign line must be 7 chars"
    .repeat 7, character
        .if .strat(text, character) = ' '
            .byte $F4
        .elseif .strat(text, character) = '.'
            .byte $CF
        .elseif .strat(text, character) = '!'
            .byte $36
        .elseif .strat(text, character) = $3F
            .byte $34
        .elseif .strat(text, character) = $27
            .byte $35
        .elseif .strat(text, character) >= 'A' .and .strat(text, character) <= 'Z'
            .byte .strat(text, character) - 'A' + $DA
        .elseif .strat(text, character) >= '0' .and .strat(text, character) <= '9'
            .byte .strat(text, character) - '0' + $D0
        .else
            .error "Unsupported Arcade sign character"
        .endif
    .endrepeat
.endmacro

.segment "BANK6"
.export BarbaWaldoPortal6, UpdateWaldoHatChr6

BarbaWaldoPortal6:
    lda $0707
    cmp #$01
    bne @clear_quick
    lda $0736
    cmp #$0B
    bne @clear_quick
    lda #>(BarbaWaldoPortal2 - 1)
    pha
    lda #<(BarbaWaldoPortal2 - 1)
    pha
    lda #$02
    jmp $FFCC
@clear_quick:
    lda #$00
    sta WALDO_ENTER_MSG
    sta PORTAL_DEBOUNCE
    sta ARCADE_SIGN_LO
    sta ARCADE_SIGN_HI
    rts

.segment "BANK2_SMOKE"
BarbaWaldoPortal2:
    jsr ArcadeNpcTick2
    jsr UpdateArcadeSigns2
@in_rauru:
    lda WALDO_ENTER_MSG
    bne @wait_enter_msg
    lda $074C
    bne @clear_deb
    lda $29
    cmp #$B0
    bne @clear_deb
    jsr CheckPortalDoor2
    lda WALDO_ENTER_MSG
    beq @clear_deb
    jsr PollUpKey2
    beq @clear_enter_flag
@on_door:
    lda PORTAL_DEBOUNCE
    bne @clear_enter_flag
    lda #$02
    sta $074C               ; Dialog Type = Talking
    sta $DE                 ; Freeze player/actors
    lda #$00
    sta $0524               ; Dialog routine counter = 0
    sta $0525               ; Dialog routine delay = 0
    sta $0400               ; Clear slash/action frame
    lda #$03
    sta $80                 ; Stand pose
    lda $29
    and #$F0
    sta $29
    ldx #$05
@find_slot:
    lda $B6,x
    bne @next_slot
    lda $A1,x
    cmp #$0D
    beq @next_slot
    cmp #$0F
    bne @set_slot
@next_slot:
    dex
    bpl @find_slot
    ldx #$05
@set_slot:
    stx $048B
    jmp @done

@wait_enter_msg:
    lda $074C
    bne @done
    lda #$00
    sta WALDO_ENTER_MSG
    jmp BarbaWaldoEnter2

@clear_deb:
    lda #$00
    sta PORTAL_DEBOUNCE
@done:
    jsr ArcadeStageDlg2
    lda #$06
    jmp $FFCC
@clear_enter_flag:
    lda #$00
    sta WALDO_ENTER_MSG
    beq @done

.segment "BANK6"
; Return effective head gear in A: 0=None, 1=Waldo Hat, 2=Hockey Mask, 3=Mega Helmet.
GetEffectiveHead6:
    lda BARBA_GEAR
    bmi @explicit
    lda WALDO_HAT
    cmp #WALDO_HAT_MAGIC
    bne @none
    lda #$01
    rts
@none:
    lda #$00
    rts
@explicit:
    and #$03
    rts

; Swap MMC3 R2 ($1000-$13FF) to Waldo-hat (155) or Hockey-mask (181) CHR bank.
UpdateWaldoHatChr6:
    jsr GetEffectiveHead6
    cmp #$01
    beq @need_swap
    cmp #$02
    bne @hat_done
@need_swap:
    lda #>(UpdateWaldoHatChr3 - 1)
    pha
    jmp WaldoHatHop6
@hat_done:
    rts

.segment "WALDO_HAT_1"
WaldoHatHop6:
    lda #<(UpdateWaldoHatChr3 - 1)
    pha
    lda #$03
    jmp $FFCC

.segment "BANK3_PAD"
UpdateWaldoHatChr3:
    lda $0736
    cmp #$06
    bcc @ret
    lda BARBA_GEAR
    bpl @waldo
    and #$03
    cmp #$02
    bne @waldo
    lda #181
    bne @set_r2
@waldo:
    lda #155
@set_r2:
    ldx #$02
    stx $64D5
    stx $8000
    sta $8001
@ret:
    lda #$06
    jmp $FFCC

.segment "ITEM_ROAR"
; Draw Waldo hat ($1D + $5F) above Barba's head in side-view ($6500 OAM shadow) when equipped.
DrawWaldoHat6:
    jsr GetEffectiveHead6
    cmp #$01
    bne @done
    lda $0736
    cmp #$0B
    bne @done
    lda $076C
    cmp #$04                  ; ending cutscene uses $5E for ash in CHR 0E
    beq @done
    ldx #$02
@next_slot:
    ldy @head_slots,x
    lda $6500,y
    cmp #$F0
    bcs @skip_slot
    lda $6501,y
    cmp #$03                  ; normal head
    beq @have_head
    cmp #$1D                  ; windup / hurt
    beq @have_head
    cmp #$21                  ; attack
    beq @have_head
    cmp #$3B                  ; looking up
    beq @have_head
@skip_slot:
    dex
    bpl @next_slot
@done:
    rts
@head_slots:
    .byte $0C, $00, $4C
@have_head:
    cmp #$1D                  ; remap windup/hurt head to $03 so $1C/$1D holds the hat front
    bne :+
    lda #$03
    sta $6501,y
:
    sta $03                   ; save head tile ($03/$21/$3B)
    lda $6500,y
    sec
    sbc #$05                  ; 5px above head top (2-sprite floppy cornucopia + red puffball)
    bcc @done
    sta $00
    lda $03
    cmp #$3B                  ; looking up: head sits 5px lower in $3A/$3C
    bne @not_up_y
    lda $00
    clc
    adc #$05
    bcs @done
    sta $00
@not_up_y:
    lda $0479                 ; airborne: press down while rising, float up while falling
    beq @chk_hud
    lda $057D
    beq @chk_hud
    bmi @air_rise
    dec $00
    bne @chk_hud
@air_rise:
    inc $00
@chk_hud:
    lda $00
    cmp #$20                  ; keep below HUD split
    bcc @done
    cmp #$F0
    bcs @done
    lda #$04                  ; base X offset for front half ($1D) of 2-sprite hat
    ldx $03
    cpx #$3B                  ; looking up: lean 1px back
    beq @lean_back
    ldx $0479                 ; rising jump: press back 1px
    beq @chk_frame_x
    ldx $057D
    bmi @lean_back
@chk_frame_x:
    ldx DRAW_FRAME
    cpx #$24                  ; windup: lean 1px back
    beq @lean_back
    cpx #$09                  ; walk1: front +1px back (B1)
    beq @lean_back
    cpx #$2D                  ; attack: lunge 1px forward
    bne @apply_x
    lda #$03
    .byte $2C
@lean_back:
    lda #$05
@apply_x:
    sta $03
    jmp DrawWaldoHatWrite6

.segment "BANK6"
DrawWaldoHatWrite6:
    lda $6502,y               ; inherit head attr (H-flip, palette, hurt flash, priority)
    sta $02
    lda $6503,y
    bit $02
    bvs @facing_right
    clc
    adc $03
    bcs @ret_done
    sta $01                   ; front_X
    clc
    adc #$07                  ; back rest = front_X + 7 (1px overlap with B1)
    bcc @both
    lda #$FF
    bne @both
@facing_right:
    sec
    sbc $03
    bcc @ret_done
    sta $01                   ; front_X
    sec
    sbc #$07
    bcs @both
    lda #$FF
@both:
    pha                       ; save back_X
    ldx #$20                  ; high-priority OAM slot ahead of shouts/villagers/smoke
    lda #$1D                  ; front half ($1C ^ $01)
    jsr @place_sprite
    pla
    cmp #$FF
    beq @ret_done
    sta $01
    lda DRAW_FRAME
    cmp #$09                  ; walk1: back +1px more (+2 total)
    beq @shift_back
    cmp #$12                  ; walk2: back +1px + droop 1px
    beq @droop
    cmp #$36                  ; crouch: back +1px + droop 1px
    bne @draw_back
@droop:
    inc $00
@shift_back:
    bit $02
    bvs @sub_back
    inc $01
    beq @ret_done             ; wrapped past 255 -> offscreen
    bne @draw_back
@sub_back:
    lda $01
    beq @ret_done             ; would wrap below 0 -> offscreen
    dec $01
@draw_back:
    lda #$5F                  ; back half + puffball ($5E ^ $01)
@place_sprite:
    sta $03
@find_free:
    lda $6500,x
    cmp #$F0
    bcs @write_oam
    inx
    inx
    inx
    inx
    bne @find_free
@ret_done:
    rts
@write_oam:
    lda $00
    sta $6500,x
    lda $03
    sta $6501,x
    lda $02
    sta $6502,x
    lda $01
    sta $6503,x
    inx
    inx
    inx
    inx
    rts

.segment "BANK6_HAZE"
; Hockey Mask roar pitch: step DMC rate down 2 notches when Hockey Mask is equipped.
RoarSetRate6:
    jsr GetEffectiveHead6
    cmp #$02
    bne @normal
    lda #(ROAR_RATE - 2)
    .byte $2C
@normal:
    lda #ROAR_RATE
    sta $4010
    rts

.segment "BANK4_GEAR"
; Draw Mega Helmet crest ($47), Red Necktie ($49/$57), and Championship Belt ($59)
; in Bank 4 (called from DrawBossMeter4) while $0736 == $0B.
DrawExtraGear4:
    lda $0736
    cmp #$0B
    bne @done
    lda BARBA_GEAR
    and #$33
    beq @done
    ldx #$02
@next_slot:
    ldy @head_slots,x
    lda $6500,y
    cmp #$F0
    bcs @skip_slot
    lda $6501,y
    cmp #$03
    beq @have_head
    cmp #$1D
    beq @have_head
    cmp #$21
    beq @have_head
    cmp #$3B
    beq @have_head
@skip_slot:
    dex
    bpl @next_slot
@done:
    rts
@head_slots:
    .byte $0C, $00, $4C
@have_head:
    sty $04
    sta $05
    lda BARBA_GEAR
    and #$03
    cmp #$03
    bne @chk_tie
    ; Mega Helmet blue crest ($47, Palette 1)
    lda $6500,y
    sec
    sbc #$05
    bcc @chk_tie
    ldx $05
    cpx #$3B
    bne :+
    clc
    adc #$05
    bcs @chk_tie
:
    cmp #$20
    bcc @chk_tie
    cmp #$F0
    bcs @chk_tie
    sta $00
    lda $6502,y
    and #$FC
    ora #$01
    sta $02
    lda $6503,y
    bit $02
    bvs @helm_r
    clc
    adc #$04
    bcs @chk_tie
    bcc @helm_x
@helm_r:
    sec
    sbc #$04
    bcc @chk_tie
@helm_x:
    sta $01
    ldx #$20
    lda #$79
    jsr PlaceGearSprite4
@chk_tie:
    jmp DrawTie4

.segment "PALACE_ROAR"
DrawTie4:
    lda BARBA_GEAR
    and #$10
    beq @chk_belt
    ldy $04
    lda #$0C
    ldx $0479
    beq :+
    lda #$09
:
    clc
    adc $6500,y
    bcs @chk_belt
    cmp #$20
    bcc @chk_belt
    cmp #$F0
    bcs @chk_belt
    sta $00
    lda $6502,y
    cpx #$00
    beq :+
    ldx $12
    txa
    and #$04
    beq :+
    lda $6502,y
    eor #$40
    dec $00
    .byte $2C
:
    lda $6502,y
    sta $02
    lda $6503,y
    bit $02
    bvs @tie_r
    clc
    adc #$0A
    bcs @chk_belt
    bcc @tie_x
@tie_r:
    sec
    sbc #$0A
    bcc @chk_belt
@tie_x:
    sta $01
    ldx #$20
    lda #$7B
    jsr PlaceGearSprite4
@chk_belt:
DrawBelt4:
    lda BARBA_GEAR
    and #$20
    beq @done2
    ldy $04
    lda #$14
    cpy #$0C
    beq @crouch_y
    ldx DRAW_FRAME
    cpx #$36
    bne @add_y
@crouch_y:
    lda #$0C
@add_y:
    clc
    adc $6500,y
    bcs @done2
    cmp #$20
    bcc @done2
    cmp #$F0
    bcs @done2
    sta $00
    lda $12
    and #$1C
    bne @belt_pal0
    lda $6502,y
    and #$FC
    ora #$03
    .byte $2C
@belt_pal0:
    lda $6502,y
    sta $02
    lda $6503,y
    bit $02
    bvs @belt_r
    clc
    adc #$02
    bcs @done2
    bcc @belt_x
@belt_r:
    sec
    sbc #$02
    bcc @done2
@belt_x:
    sta $01
    ldx #$20
    lda #$7D                  ; Championship Belt ($7C non-town, $FC town)
    jmp PlaceGearSprite4
@done2:
    rts

PlaceGearSprite4:
    ldy $0707
    beq :+
    cpy #$03
    bcs :+
    ora #$80                  ; town bank 6 uses $F8/$FA/$FC
:
    sta $03
@find:
    lda $6500,x
    cmp #$F0
    bcs @put
    inx
    inx
    inx
    inx
    bne @find
    rts
@put:
    lda $00
    sta $6500,x
    lda $03
    sta $6501,x
    lda $02
    sta $6502,x
    lda $01
    sta $6503,x
    rts

.segment "BANK6"
.export BarbaWaldoRestore6

BarbaWaldoRestore6:
    sei
    lda #>(BarbaWaldoRestore2 - 1)
    pha
    lda #<(BarbaWaldoRestore2 - 1)
    pha
    lda #$02
    jmp $FFCC

.segment "BANK2_SMOKE"
BarbaWaldoEnter2:
    sei
    lda #$00
    sta $4015
    sta $E000

    jsr BarbaMelt2

    lda #$00
    sta $2000
    sta $2001

BarbaWaldoSaveAndLaunch2:
    ldy PORTAL_GAME
    lda #$A1
    sta $A001
    tsx
    stx $7020
    tya
    pha

    ; Save 2KB internal RAM ($0000-$07FF -> $6000-$67FF)
    ldx #$00
@save_zp:
    lda $00,x
    sta $6000,x
    inx
    bne @save_zp
    stx $00
    stx $02
    lda #$01
    sta $01
    lda #$61
    sta $03
    ldx #$07
    ldy #$00
@save_page:
    lda ($00),y
    sta ($02),y
    iny
    bne @save_page
    inc $01
    inc $03
    dex
    bne @save_page

    ; Save PPU nametables ($2000-$23FF -> $6800-$6BFF, $2400-$27FF -> $6C00-$6FFF)
    lda #$00
    jsr $FF9D
    bit $2002
    lda #$20
    ldx #$68
    jsr @save_nt_1k
    lda #$24
    ldx #$6C
    jsr @save_nt_1k

    ; Save PPU palettes ($3F00-$3F1F -> $7000-$701F)
    bit $2002
    lda #$3F
    sta $2006
    lda #$00
    sta $2006
    ldx #$00
@save_pal:
    lda $2007
    sta $7000,x
    inx
    cpx #$20
    bne @save_pal

    ; Clear PPU nametables ($2000-$27FF) so Waldo starts with a clean screen
    bit $2002
    lda #$20
    sta $2006
    lda #$00
    sta $2006
    ldx #$08
    ldy #$00
@clear_nt:
    sta $2007
    iny
    bne @clear_nt
    dex
    bne @clear_nt

    ; Clear portal state ($7FFF) in target WRAM bank happens in PortalTramp2
    jmp PortalTramp2

@save_nt_1k:
    sta $2006
    lda #$00
    sta $2006
    sta $00
    stx $01
    bit $2007               ; prime PPUDATA read buffer
    ldx #$04
    ldy #$00
@nt_read:
    lda $2007
    sta ($00),y
    iny
    bne @nt_read
    inc $01
    dex
    bne @nt_read
    rts

.segment "BANK2_SMOKE"
.export PortalCount, PortalTblTown, PortalTblRoom, PortalTblPage, PortalTblXlo, PortalTblXhi
MAX_PORTAL_SLOTS = 16
PortalCount:     .byte $02
PortalTblTown:   .res MAX_PORTAL_SLOTS, $00
PortalTblRoom:   .res MAX_PORTAL_SLOTS, $00
PortalTblPage:   .res MAX_PORTAL_SLOTS, $00
PortalTblXlo:    .res MAX_PORTAL_SLOTS, $00
PortalTblXhi:    .res MAX_PORTAL_SLOTS, $00

CheckPortalDoor2:
    lda #$00
    sta WALDO_ENTER_MSG
    ldx PortalCount
    beq @done
    dex
@chk:
    lda $056B
    cmp PortalTblTown,x
    bne @next
    lda $0561
    cmp PortalTblRoom,x
    bne @next
    lda $3B
    cmp PortalTblPage,x
    bne @next
    lda $4D
    cmp PortalTblXlo,x
    bcc @next
    cmp PortalTblXhi,x
    bcs @next
    stx PORTAL_GAME
    lda PortalTblNameLo,x
    sta $00
    lda PortalTblNameHi,x
    sta $01
    ldy #$00
@copy_name:
    lda ($00),y
    sta ARCADE_DLG_BUF,y
    cmp #$FF
    beq @copied
    iny
    cpy #$3F
    bcc @copy_name
    lda #$FF
    sta ARCADE_DLG_BUF,y
@copied:
    lda #$01
    sta WALDO_ENTER_MSG
    bne @done
@next:
    dex
    bpl @chk
@done:
    rts

PollUpKey2:
    lda #$01
    sta $4016
    lsr a
    sta $4016
    ldx #$04
@up_skip:
    bit $4016
    dex
    bne @up_skip
    lda $4016
    and #$01
    rts

.segment "BANK2_SMOKE"
.export PortalTblWram, PortalTbl5FF0, PortalTbl5FF1, PortalTbl5FF2, PortalTblR6
.export PortalTblBootLo, PortalTblBootHi, PortalTblNameLo, PortalTblNameHi
.export PortalTblSignLo, PortalTblSignHi
.export ArcadeName00, ArcadeName01, ArcadeName02, ArcadeName03
.export ArcadeName04, ArcadeName05, ArcadeName07
.export ArcadeName08, ArcadeName09, ArcadeName10
.export ArcadeSign00, ArcadeSign01, ArcadeSign02, ArcadeSign03
.export ArcadeSign04, ArcadeSign05, ArcadeSign07
.export ArcadeSign08, ArcadeSign09, ArcadeSign10
PortalTblWram:   .res MAX_PORTAL_SLOTS, $A3
PortalTbl5FF0:   .res MAX_PORTAL_SLOTS, $00
PortalTbl5FF1:   .res MAX_PORTAL_SLOTS, $00
PortalTbl5FF2:   .res MAX_PORTAL_SLOTS, $00
PortalTblR6:     .res MAX_PORTAL_SLOTS, $00
PortalTblBootLo: .res MAX_PORTAL_SLOTS, $00
PortalTblBootHi: .res MAX_PORTAL_SLOTS, $00
PortalTblNameLo: .byte <ArcadeName00, <ArcadeName01, <ArcadeName02, <ArcadeName03
                 .byte <ArcadeName04, <ArcadeName05, <ArcadeNameDefault, <ArcadeName07
                 .byte <ArcadeName08, <ArcadeName09, <ArcadeName10, <ArcadeNameDefault
                 .byte <ArcadeNameDefault, <ArcadeNameDefault, <ArcadeNameDefault, <ArcadeNameDefault
PortalTblNameHi: .byte >ArcadeName00, >ArcadeName01, >ArcadeName02, >ArcadeName03
                 .byte >ArcadeName04, >ArcadeName05, >ArcadeNameDefault, >ArcadeName07
                 .byte >ArcadeName08, >ArcadeName09, >ArcadeName10, >ArcadeNameDefault
                 .byte >ArcadeNameDefault, >ArcadeNameDefault, >ArcadeNameDefault, >ArcadeNameDefault
PortalTblSignLo: .byte <ArcadeSign00, <ArcadeSign01, <ArcadeSign02, <ArcadeSign03
                 .byte <ArcadeSign04, <ArcadeSign05, <ArcadeSignDefault, <ArcadeSign07
                 .byte <ArcadeSign08, <ArcadeSign09, <ArcadeSign10, <ArcadeSignDefault
                 .byte <ArcadeSignDefault, <ArcadeSignDefault, <ArcadeSignDefault, <ArcadeSignDefault
PortalTblSignHi: .byte >ArcadeSign00, >ArcadeSign01, >ArcadeSign02, >ArcadeSign03
                 .byte >ArcadeSign04, >ArcadeSign05, >ArcadeSignDefault, >ArcadeSign07
                 .byte >ArcadeSign08, >ArcadeSign09, >ArcadeSign10, >ArcadeSignDefault
                 .byte >ArcadeSignDefault, >ArcadeSignDefault, >ArcadeSignDefault, >ArcadeSignDefault

ArcadeSign00:
    ArcadeSignLine "WHERES "
    ArcadeSignLine "BARBA? "
ArcadeSign01:
    ArcadeSignLine "FRIDAY "
    ArcadeSignLine " 13TH  "
ArcadeSign02:
    ArcadeSignLine "BARBA'S"
    ArcadeSignLine " BEEF  "
ArcadeSign03:
    ArcadeSignLine " BARBA "
    ArcadeSignLine " KONG  "
ArcadeSign04:
    ArcadeSignLine " SUPER "
    ArcadeSignLine " BARBA "
ArcadeSign05:
    ArcadeSignLine "MONSTER"
    ArcadeSignLine " HUNT  "
ArcadeSign07:
    ArcadeSignLine " BARBA "
    ArcadeSignLine " MAN 2 "
ArcadeSign08:
    ArcadeSignLine " WHEEL "
    ArcadeSignLine " BARBA "
ArcadeSign09:
    ArcadeSignLine "LEGEND "
    ArcadeSignLine " BARBA "
ArcadeSign10:
    ArcadeSignLine " PUNCH "
    ArcadeSignLine " OUT!! "
ArcadeSignDefault:
    ArcadeSignLine "ARCADE "
    ArcadeSignLine " BOOTH "

SignBitMask:
    .byte $01, $02, $04, $08, $10, $20, $40, $80

UpdateArcadeSigns2:
    lda $056B
    bne @clear_all
    lda $0561
    cmp #$1C
    beq @in_arcade
@clear_all:
    lda #$00
    sta ARCADE_SIGN_LO
    sta ARCADE_SIGN_HI
    rts
@in_arcade:
    lda $074C
    ora $0301
    bne @early_done
    ldx PortalCount
    beq @early_done
    dex
@loop:
    lda PortalTblTown,x
    bne @next_hop
    lda PortalTblRoom,x
    cmp #$1C
    beq @in_room
@next_hop:
    jmp @next
@early_done:
    rts
@in_room:
    lda PortalTblXlo,x
    clc
    adc #$08
    and #$F0
    lsr a
    lsr a
    lsr a
    sec
    sbc #$03
    sta $02                 ; $02 = sign_col
    lda PortalTblPage,x
    sta $05
    lda $02
    asl a
    asl a
    asl a
    sta $04                 ; $05:$04 = sign_left
    clc
    adc #55
    sta $06
    lda $05
    adc #$00
    sta $07                 ; $07:$06 = sign_right
    lda $04
    cmp $072C
    lda $05
    sbc $072A
    bcs @check_right
    lda $06
    cmp $072C
    lda $07
    sbc $072A
    bcs @next_hop
    jsr @clear_bit
    jmp @next
@check_right:
    lda $06
    sec
    sbc $072C
    lda $07
    sbc $072A
    beq @ready
    lda $072A
    ora $072C
    bne @check_far_right
    lda PortalTblPage,x
    cmp #$02
    bcc @ready
@check_far_right:
    lda $04
    sec
    sbc $072C
    lda $05
    sbc $072A
    beq @next_hop
    jsr @clear_bit
    jmp @next
@ready:
    txa
    and #$07
    tay
    lda SignBitMask,y
    cpx #$08
    bcs @test_hi
    and ARCADE_SIGN_LO
    bne @next
    lda SignBitMask,y
    ora ARCADE_SIGN_LO
    sta ARCADE_SIGN_LO
    jmp @queue_sign
@test_hi:
    and ARCADE_SIGN_HI
    bne @next
    lda SignBitMask,y
    ora ARCADE_SIGN_HI
    sta ARCADE_SIGN_HI
@queue_sign:
    lda PortalTblPage,x
    and #$01
    asl a
    asl a
    ora #$22
    sta $0302
    sta $030C
    lda $02
    clc
    adc #$20
    sta $0303
    clc
    adc #$20
    sta $030D
    lda #$07
    sta $0304
    sta $030E
    lda PortalTblSignLo,x
    sta $00
    lda PortalTblSignHi,x
    sta $01
    ldy #$06
@copy_r1:
    lda ($00),y
    sta $0305,y
    dey
    bpl @copy_r1
    ldy #$0D
@copy_r2:
    lda ($00),y
    sta $0308,y
    dey
    cpy #$07
    bcs @copy_r2
    lda #$FF
    sta $0316
    lda #$14
    sta $0301
@done:
    rts
@next:
    dex
    bmi @done
    jmp @loop

@clear_bit:
    txa
    and #$07
    tay
    lda SignBitMask,y
    eor #$FF
    cpx #$08
    bcs @clr_hi
    and ARCADE_SIGN_LO
    sta ARCADE_SIGN_LO
    rts
@clr_hi:
    and ARCADE_SIGN_HI
    sta ARCADE_SIGN_HI
    rts

ArcadeName00:
    WaldoLine "INSERT COIN!", $FD
    WaldoLine "WHERES BARBA?", $FF
ArcadeName01:
    WaldoLine "INSERT COIN!", $FD
    WaldoLine "FRIDAY 13TH", $FF
ArcadeName02:
    WaldoLine "INSERT COIN!", $FD
    WaldoLine "BARBA'S BEEF", $FF
ArcadeName03:
    WaldoLine "INSERT COIN!", $FD
    WaldoLine "BARBA KONG", $FF
ArcadeName04:
    WaldoLine "INSERT COIN!", $FD
    WaldoLine "SUPER BARBA", $FF
ArcadeName05:
    WaldoLine "INSERT COIN!", $FD
    WaldoLine "MONSTER HUNT", $FF
ArcadeName07:
    WaldoLine "INSERT COIN!", $FD
    WaldoLine "BARBA MAN 2", $FF
ArcadeName08:
    WaldoLine "INSERT COIN!", $FD
    WaldoLine "WHEEL OF", $FD
    WaldoLine "BARBA", $FF
ArcadeName09:
    WaldoLine "INSERT COIN!", $FD
    WaldoLine "LEGEND OF", $FD
    WaldoLine "BARBA", $FF
ArcadeName10:
    WaldoLine "INSERT COIN!", $FD
    WaldoLine "BARBA", $FD
    WaldoLine "PUNCH OUT!!", $FF
ArcadeNameDefault:
    WaldoLine "SOMETHING'S", $FD
    WaldoLine "NOT", $FD
    WaldoLine "RIGHT...", $FF

PortalTramp2:
    pla
    tax                     ; X = portal slot index (0..MAX_PORTAL_SLOTS-1)
    lda PortalTblWram,x
    sta $A001
    lda #$00
    sta $7FFF
    ; Seed guest WRAM $7FF0..$7FF7 from Zelda II's RNG ($051A..$0521) + frame counter ($12).
    ldy #$07
@seed_rng:
    lda $051A,y
    eor $12
    sta $7FF0,y
    dey
    bpl @seed_rng
    lda $7FF0
    bne @seed_nz
    lda $12
    ora #$A5
    sta $7FF0
@seed_nz:
    ldy #(PortalTrampEnd - PortalTramp - 1)
@copy_tramp:
    lda PortalTramp,y
    sta $0300,y
    dey
    bpl @copy_tramp
    lda PortalTbl5FF0,x
    sta $0300 + (PortalTramp_5FF0 - PortalTramp) + 1
    lda PortalTbl5FF1,x
    sta $0300 + (PortalTramp_5FF1 - PortalTramp) + 1
    lda PortalTbl5FF2,x
    sta $0300 + (PortalTramp_5FF2 - PortalTramp) + 1
    lda PortalTblR6,x
    sta $0300 + (PortalTramp_R6 - PortalTramp) + 1
    lda PortalTblBootLo,x
    sta $0300 + (PortalTramp_Boot - PortalTramp) + 1
    lda PortalTblBootHi,x
    sta $0300 + (PortalTramp_Boot - PortalTramp) + 2
    jmp $0300

PortalTramp:
    lda #$80
    sta $A001               ; unlock $5FF0-$5FF3
PortalTramp_5FF0:
    lda #$01
    sta $5FF0
PortalTramp_5FF1:
    lda #$10
    sta $5FF1
PortalTramp_5FF2:
    lda #$20
    sta $5FF2
    lda #$06
    sta $8000
PortalTramp_R6:
    lda #$00
    sta $8001
PortalTramp_Boot:
    jmp $E000
PortalTrampEnd:

.segment "BANK2_SMOKE"

BarbaWaldoRestore2:
    lda #$00
    sta $2000
    sta $2001
    sta $4015
    sta $E000

    lda #$A1
    sta $A001               ; WRAM bank 1 = Barba snapshot

    ; Restore PPU nametables ($2000-$23FF and $2400-$27FF) with Vertical mirroring
    lda #$00
    jsr $FF9D
    bit $2002
    lda #$20
    ldx #$68
    jsr @rest_nt_1k
    lda #$24
    ldx #$6C
    jsr @rest_nt_1k

    ; Restore PPU palettes
    bit $2002
    lda #$3F
    sta $2006
    lda #$00
    sta $2006
    ldx #$00
@rest_pal:
    lda $7000,x
    sta $2007
    inx
    cpx #$20
    bne @rest_pal

    ; Restore 2KB internal RAM ($6000-$67FF -> $0000-$07FF)
    ldx #$00
    stx $00
    stx $02
    lda #$61
    sta $01
    lda #$01
    sta $03
    ldx #$07
    ldy #$00
@rest_page:
    lda ($00),y
    sta ($02),y
    iny
    bne @rest_page
    inc $01
    inc $03
    dex
    bne @rest_page
    ldx #$00
@rest_zp:
    lda $6000,x
    sta $00,x
    inx
    bne @rest_zp

    ldx $7020
    txs

    lda #$A0
    sta $A001               ; WRAM bank 0 = Barba + lock $5FF0-$5FF3

    lda #$00
    jsr $FF9D               ; Vertical mirroring ($2000/$2400)
    lda $076E
    jsr $FFB1               ; Restore CHR banks

    lda #$01
    sta PORTAL_DEBOUNCE
    sta WALDO_RETURN_MSG
    lda #$02
    sta $074C               ; Dialog Type = Talking
    sta $DE                 ; Lock movement while message box is open
    lda #$00
    sta $0400               ; Clear slash/breath frame
    sta $0524               ; Dialog routine counter = 0
    sta $0525               ; Dialog routine delay = 0
    lda #$03
    sta $80                 ; Barba standing pose
    lda #$05
    sta $048B               ; Safe slot (non-healer/non-wiseman)
    lda $F7
    and #$F7
    sta $F7
    lda $F5
    and #$F7
    sta $F5

@wait_up_rel:
    jsr PollUpKey2
    bne @wait_up_rel

    jsr BarbaWipeIn2

    bit $2002
@vwait:
    bit $2002
    bpl @vwait
    lda $FF
    sta $2000
    cli
    lda #$06
    jmp $FFCC               ; Resume NmiVblankSetup6 in bank 6; it swaps to PRG0

@rest_nt_1k:
    sta $2006
    lda #$00
    sta $2006
    sta $00
    stx $01
    ldx #$04
    ldy #$00
@nt_write:
    lda ($00),y
    sta $2007
    iny
    bne @nt_write
    inc $01
    dex
    bne @nt_write
    rts

; Bottom-up wavy horizontal melt + wipe away (30 frames, 0.5s).
; Preserves $0000-$07FF and PPU VRAM so BarbaWaldoSaveAndLaunch2 can snapshot cleanly afterward.
BarbaMelt2:
    lda #$00
    sta MELT_DIR
    sta MELT_FRAME
    jmp BarbaMeltFrameLoop

; Top-down wavy horizontal wipe-in (30 frames, 0.5s) on return to Barba.
; Populates PPU OAM from $6500 before revealing the restored Rauru scene.
BarbaWipeIn2:
    lda #$01
    sta MELT_DIR
    lda #29
    sta MELT_FRAME
    bit $2002
@oam_vb:
    bit $2002
    bpl @oam_vb
    lda #$00
    sta $2003
    lda #$65
    sta $4014
BarbaMeltFrameLoop:
    lda #30
    sec
    sbc MELT_FRAME
    sta MELT_WIPE

    bit $2002
@vb_wait:
    bit $2002
    bpl @vb_wait

    lda $FF
    and #$7C
    sta $2000
    bit $2002
    lda #$00
    sta $2006
    sta $2006
    sta $2005
    sta $2005
    lda $FE
    sta $2001

    ldx #21
@pre_sl:
    ldy #21
@pre_in:
    dey
    bne @pre_in
    nop
    dex
    bne @pre_sl

    lda #$00
    sta MELT_BAND
@band_loop:
    lda MELT_BAND
    cmp MELT_WIPE
    bcc @band_vis
    lda #$00
    sta $2001
    lda #$3F
    sta $2006
    lda #$07
    sta $2006
    jmp @next_frame

@band_vis:
    clc
    adc MELT_FRAME
    and #$0F
    tax
    lda @melt_wave,x
    ldx MELT_FRAME
    cpx #8
    bcc @scale_half
    cpx #16
    bcc @scale_done
    cpx #24
    bcc @scale_2x
    asl a
@scale_2x:
    asl a
    jmp @scale_done
@scale_half:
    cmp #$80
    ror a
@scale_done:
    tax                     ; X = signed shear
    lda $FF
    and #$7C
    sta MELT_NT
    lda MELT_BAND
    cmp #$04
    bcc @hud_band
    lda $0746
    and #$01
    ora MELT_NT
    sta MELT_NT
    lda $FD
    jmp @add_shear
@hud_band:
    lda #$00
@add_shear:
    sta MELT_BASE
    txa                     ; A = signed shear
    bmi @neg_shear
    clc
    adc MELT_BASE
    bcc @write_scroll
    tax
    lda MELT_NT
    eor #$01
    sta MELT_NT
    txa
    jmp @write_scroll
@neg_shear:
    clc
    adc MELT_BASE
    bcs @write_scroll
    tax
    lda MELT_NT
    eor #$01
    sta MELT_NT
    txa
@write_scroll:
    ldx MELT_NT
    stx $2000
    sta $2005
    lda #$00
    sta $2005

    ldy #158
@band_wait:
    dey
    bne @band_wait

    inc MELT_BAND
    lda MELT_BAND
    cmp #30
    bcs @next_frame
    jmp @band_loop

@next_frame:
    lda MELT_DIR
    bne @rev_next
    inc MELT_FRAME
    lda MELT_FRAME
    cmp #30
    bcs @melt_done
    jmp BarbaMeltFrameLoop
@rev_next:
    dec MELT_FRAME
    bmi @melt_done
    jmp BarbaMeltFrameLoop
@melt_done:
    rts

@melt_wave:
    .byte $00, $02, $04, $05, $06, $05, $04, $02
    .byte $00, $FE, $FC, $FB, $FA, $FB, $FC, $FE

.segment "BANK3_SIGN"
.export WaldoDialogCheck
WaldoDialogCheck:
    lda WALDO_RETURN_MSG
    beq @check_enter
    lda #$00
    sta WALDO_RETURN_MSG
    lda #<WaldoReturnText
    ldy #>WaldoReturnText
    jmp TownSetNpcDialog
@check_enter:
    lda WALDO_ENTER_MSG
    beq @check_arcade
    lda #<ARCADE_DLG_BUF
    ldy #>ARCADE_DLG_BUF
    jmp TownSetNpcDialog
@check_arcade:
    lda $0707
    cmp #$01
    bne @native
    lda $0561
    cmp #$1C
    bne @native
    lda #<ARCADE_DLG_BUF
    ldy #>ARCADE_DLG_BUF
    jmp TownSetNpcDialog
@native:
    lda #$00
    sta $05
    sta $048C
    jmp $B487

.segment "BANK2_SMOKE"
BarbaArcadeEnemies:
    .byte BarbaArcadeEnemiesEnd - BarbaArcadeEnemies
    .byte $75, $1E            ; Page 0, X=$50, Red Young Lad - Walking
    .byte $77, $40 | $1C      ; Page 1, X=$70, Blue Lady - Walking
    .byte $75, $80 | $19      ; Page 2, X=$50, Blue Lumberjack - Walking
    .byte $76, $C0 | $1B      ; Page 3, X=$60, Red Old Woman - Walking
BarbaArcadeEnemiesEnd:

ArcadeNpcTick2:
    lda $0561
    cmp #$1C
    beq @in_arcade
    ; Outside room $1C in Rauru/towns: stage BarbaArcadeEnemies in $73E0
    ; so room $1C enemy pointer ($85D9 -> $73E0) is ready before room entry.
    ldy #BarbaArcadeEnemiesEnd - BarbaArcadeEnemies - 1
@copy_enemies:
    lda BarbaArcadeEnemies,y
    sta $73E0,y
    dey
    bpl @copy_enemies
    rts
@in_arcade:
    lda $074C
    bne @done
    ldx #$05
@slot_loop:
    lda $B6,x
    cmp #$01
    bne @next_slot
    lda $AF,x
    ora $05C3,x
    bne @next_slot
    lda $A1,x
    cmp #$19
    bcc @next_slot
    cmp #$21
    bcs @next_slot
    ; Ensure non-zero X velocity.
    lda $71,x
    bne @check_bounds
    lda #$0C
    sta $71,x
    lda #$01
    sta $60,x
@check_bounds:
    ; Pace between X=$30 and X=$C8 on the patron's page.
    lda $4E,x
    cmp #$30
    bcs @check_right
    lda $71,x
    bpl @check_talk
    eor #$FF
    clc
    adc #$01
    sta $71,x
    lda #$01
    sta $60,x
    bne @check_talk
@check_right:
    cmp #$C8
    bcc @check_talk
    lda $71,x
    bmi @check_talk
    eor #$FF
    clc
    adc #$01
    sta $71,x
    lda #$02
    sta $60,x
@check_talk:
@next_slot:
    dex
    bpl @slot_loop
@done:
    rts

ArcadeStageDlg2:
    lda $0561
    cmp #$1C
    bne @dlg_done
    lda $074C
    ora WALDO_ENTER_MSG
    bne @dlg_done
    ldx #$05
@dlg_slot_loop:
    lda $B6,x
    cmp #$01
    bne @dlg_next_slot
    lda $AF,x
    ora $05C3,x
    bne @dlg_next_slot
    lda $A1,x
    cmp #$19
    bcc @dlg_next_slot
    cmp #$21
    bcs @dlg_next_slot
    lda $4E,x
    sec
    sbc $4D
    sta $00
    lda $3C,x
    sbc $3B
    sta $01
    lda $00
    clc
    adc #$20
    sta $00
    lda $01
    adc #$00
    bne @dlg_next_slot
    lda $00
    cmp #$40
    bcc @stage_dlg
@dlg_next_slot:
    dex
    bpl @dlg_slot_loop
@dlg_done:
    rts

@stage_dlg:
    lda $A1,x
    cmp #$1E
    bne @not_p0
    lda #<ArcadeDlg0
    ldy #>ArcadeDlg0
    jmp @copy_dlg
@not_p0:
    cmp #$1C
    bne @not_p1
    lda #<ArcadeDlg1
    ldy #>ArcadeDlg1
    jmp @copy_dlg
@not_p1:
    cmp #$19
    bne @not_p2
    lda #<ArcadeDlg2
    ldy #>ArcadeDlg2
    jmp @copy_dlg
@not_p2:
    cmp #$1B
    bne @dlg_done
    lda #<ArcadeDlg3
    ldy #>ArcadeDlg3
@copy_dlg:
    sta $00
    sty $01
    ldy #$00
@copy_dlg_loop:
    lda ($00),y
    sta ARCADE_DLG_BUF,y
    cmp #$FF
    beq @dlg_done
    iny
    cpy #$3F
    bcc @copy_dlg_loop
    rts

ArcadeDlg0:
    WaldoLine "I LOVE THIS", $FD
    WaldoLine "ARCADE! BEST", $FD
    WaldoLine "SPOT IN RAURU!", $FF
ArcadeDlg1:
    WaldoLine "ONE MORE GAME", $FD
    WaldoLine "AND I'LL BEAT", $FD
    WaldoLine "BARBA'S SCORE!", $FF
ArcadeDlg2:
    WaldoLine "SO MANY GREAT", $FD
    WaldoLine "CABINETS HERE!", $FD
    WaldoLine "I'M HOOKED!", $FF
ArcadeDlg3:
    WaldoLine "I SPENT ALL", $FD
    WaldoLine "MY RUPEES", $FD
    WaldoLine "PLAYING HERE!", $FF

WaldoReturnText:
    TownLine "WELL THAT", $FD
    TownLine "WAS WEIRD.", $FF

.segment "TOWN"
.export BarbaArcadeArea
; 4-page interior hall (Rauru room $1C) housing 11 arcade booths across pages 0..3.
BarbaArcadeArea:
    .byte @end - BarbaArcadeArea, $60, $18, $30
    ; Page 0: left exit to Rauru ($F0 $00), ceiling ($F1 $3E), brick wall ($50 $8E), booths 0..2
    .byte $F0, $00, $F1, $3E, $50, $8E, $84, $00, $84, $00, $84, $00
    ; Page 1: jump page 1 ($E1 $00), ceiling ($F0 $3F), wall ($50 $8F), booths 3..5
    .byte $E1, $00, $F0, $3F, $50, $8F, $82, $00, $85, $00, $85, $00
    ; Page 2: jump page 2 ($E2 $00), ceiling ($F0 $3F), wall ($50 $8F), booths 6..8
    .byte $E2, $00, $F0, $3F, $50, $8F, $82, $00, $85, $00, $85, $00
    ; Page 3: jump page 3 ($E3 $00), ceiling ($F0 $3F), wall ($50 $8F), booths 9..10, right exit to Rauru
    .byte $E3, $00, $F0, $3F, $50, $8F, $82, $00, $85, $00, $F6, $01
@end:
