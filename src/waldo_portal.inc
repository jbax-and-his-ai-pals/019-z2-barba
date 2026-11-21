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
        .else
            .error "Unsupported Waldo dialogue character"
        .endif
    .endrepeat
    .byte terminator
.endmacro

.segment "ITEM_ROAR"
.export BarbaWaldoPortal6, UpdateWaldoHatChr6

BarbaWaldoPortal6:
    lda $0707
    cmp #$01
    bne @clear_all
    lda $0736
    cmp #$0B
    bne @clear_all
@in_rauru:
    lda WALDO_ENTER_MSG
    bne @wait_enter_msg
    lda $074C
    bne @clear_deb
    lda $29
    cmp #$B0
    bne @clear_deb
    jsr CheckPortalDoor6
    bcs @on_door
    bcc @clear_deb
@on_door:
    lda PORTAL_DEBOUNCE
    bne @done
    lda #$01
    sta WALDO_ENTER_MSG
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
    rts

@wait_enter_msg:
    lda $074C
    bne @done
    lda #$00
    sta WALDO_ENTER_MSG
    jmp BarbaWaldoEnter6

@clear_all:
    lda #$00
    sta WALDO_ENTER_MSG
@clear_deb:
    lda #$00
    sta PORTAL_DEBOUNCE
@done:
    rts

; Swap MMC3 R2 ($1000-$13FF) to the Waldo-hat Barba CHR bank once Waldo is beaten.
UpdateWaldoHatChr6:
    lda WALDO_HAT
    cmp #WALDO_HAT_MAGIC
    bne @hat_done
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
    cmp #$05
    bcc @ret
    beq @ow
    lda #155
    .byte $2C
@ow:
    lda #156
    ldx #$02
    stx $64D5
    stx $8000
    sta $8001
@ret:
    lda #$06
    jmp $FFCC

.segment "BANK6"
.export BarbaWaldoRestore6

BarbaWaldoEnter6:
    sei
    lda #$00
    sta $4015
    sta $E000

    jsr BarbaMelt6

    lda #$00
    sta $2000
    sta $2001

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

    ; Clear Waldo portal state in WRAM bank 2
    lda #$A2
    sta $A001
    lda #$00
    sta $7FFF

    lda #>(PortalTramp3 - 1)
    pha
    lda #<(PortalTramp3 - 1)
    pha
    lda #$03
    jmp $FFCC

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

CheckPortalDoor6:
    jmp CheckPortalDoorBody6

PortalTblRoom: .byte $01, $05
PortalTblPage: .byte $01, $00
PortalTblXlo:  .byte $20, $90
PortalTblXhi:  .byte $30, $A0
PortalDoorHit:
    stx PORTAL_GAME
    jsr PollUpKey6
    beq @no_up
    sec
    rts
@no_up:
    clc
    rts

PollUpKey6:
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

.segment "ITEM_ROAR"
CheckPortalDoorBody6:
    ldx #$01
@chk:
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
    jmp PortalDoorHit
@next:
    dex
    bpl @chk
    clc
    rts

.segment "BANK3_PAD"
PortalTramp3:
    ldx #(PortalTrampEnd - PortalTramp - 1)
@copy_tramp:
    lda PortalTramp,x
    sta $0300,x
    dex
    bpl @copy_tramp
    pla
    beq @go
    jmp PatchF13TrampA
@go:
    jmp $0300

PatchF13TrampB:
    lda #$30
    sta $0310
    lda #$80
    sta $0320
    jmp $0300

PortalTramp:
    lda #$80
    sta $A001               ; unlock $5FF0-$5FF3
    lda #$01                ; [$0306] $03 for F13
    sta $5FF0               ; 256KB MMC3 mode
    lda #$10                ; [$030B] $08 for F13
    sta $5FF1               ; Waldo PRG (256..512KB)
    lda #$20                ; [$0310] $30 for F13
    sta $5FF2               ; Waldo CHR (256..512KB)
    lda #$06
    sta $8000
    lda #$00
    sta $8001               ; Map bank 0 at $8000 for F13 (Waldo Reset in $E000-$FFFF)
    jmp $E000               ; [$0320] $80 for F13
PortalTrampEnd:

.segment "BANK3_SIGN"
PatchF13TrampA:
    lda #$01
    sta $0306
    lda #$20
    sta $030B
    jmp PatchF13TrampB

.segment "BANK6"

BarbaWaldoRestore6:
    sei
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
    jsr PollUpKey6
    bne @wait_up_rel

    jsr BarbaWipeIn6

    bit $2002
@vwait:
    bit $2002
    bpl @vwait
    lda $FF
    sta $2000
    cli
    rts                     ; Resume NmiVblankSetup6 in bank 6; it swaps to PRG0

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
; Preserves $0000-$07FF and PPU VRAM so BarbaWaldoEnter6 can snapshot cleanly afterward.
BarbaMelt6:
    lda #$00
    sta MELT_DIR
    sta MELT_FRAME
    jmp BarbaMeltFrameLoop

; Top-down wavy horizontal wipe-in (30 frames, 0.5s) on return to Barba.
; Populates PPU OAM from $6500 before revealing the restored Rauru scene.
BarbaWipeIn6:
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
    beq @native
    lda #<WaldoEnterText
    ldy #>WaldoEnterText
    jmp TownSetNpcDialog
@native:
    lda #$00
    sta $05
    sta $048C
    jmp $B487

WaldoReturnText:
    TownLine "WELL THAT", $FD
    TownLine "WAS WEIRD.", $FF

WaldoEnterText:
    WaldoLine "SOMETHING'S", $FD
    WaldoLine "NOT", $FD
    WaldoLine "RIGHT...", $FF
