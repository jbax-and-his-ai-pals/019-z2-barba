; In-ROM Rauru <-> Where's Waldo? portal (enabled with -D WALDO_PORTAL=1).
; Runs on NES 2.0 Mapper 176 (FK23C):
;   PRG: 0..256KB Barba, 256..512KB Waldo
;   CHR: 0..256KB Barba, 256..512KB Waldo
;   WRAM ($A001): bank 0 = Barba, bank 1 = snapshot, bank 2 = Waldo

PORTAL_DEBOUNCE = $64F2

.segment "BANK6"
.export BarbaWaldoPortal6, BarbaWaldoRestore6

BarbaWaldoPortal6:
    lda $0707
    cmp #$01
    bne @clear_deb
    lda $0561
    cmp #$01
    bne @clear_deb
    lda $0736
    cmp #$0B
    bne @clear_deb
    lda $3B
    cmp #$01
    bne @clear_deb
    lda $29
    cmp #$B0
    bne @clear_deb
    lda $4D
    cmp #$20
    bcc @clear_deb
    cmp #$30
    bcs @clear_deb
    lda #$01
    sta $4016
    lda #$00
    sta $4016
    bit $4016               ; A
    bit $4016               ; B
    bit $4016               ; Select
    bit $4016               ; Start
    lda $4016               ; Up
    and #$01
    beq @clear_deb
    lda PORTAL_DEBOUNCE
    bne @done
    beq BarbaWaldoEnter6
@clear_deb:
    lda #$00
    sta PORTAL_DEBOUNCE
@done:
    rts

BarbaWaldoEnter6:
    sei
    lda #$00
    sta $2000
    sta $2001
    sta $4015
    sta $E000

    lda #$A1
    sta $A001
    tsx
    stx $7020

    ; Save 2KB internal RAM ($0000-$07FF -> $6000-$67FF)
    ldx #$00
@save_ram:
    lda $0000,x
    sta $6000,x
    lda $0100,x
    sta $6100,x
    lda $0200,x
    sta $6200,x
    lda $0300,x
    sta $6300,x
    lda $0400,x
    sta $6400,x
    lda $0500,x
    sta $6500,x
    lda $0600,x
    sta $6600,x
    lda $0700,x
    sta $6700,x
    inx
    bne @save_ram

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

    ; Clear Waldo portal state in WRAM bank 2
    lda #$A2
    sta $A001
    lda #$00
    sta $7FFD
    sta $7FFE
    sta $7FFF

    ; Copy RAM trampoline to $0300 and jump to Waldo
    ldx #(@tramp_end - @tramp - 1)
@copy_tramp:
    lda @tramp,x
    sta $0300,x
    dex
    bpl @copy_tramp
    jmp $0300

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

@tramp:
    lda #$80
    sta $A001               ; unlock $5FF0-$5FF3
    lda #$01
    sta $5FF0               ; 256KB MMC3 mode
    lda #$10
    sta $5FF1               ; Waldo PRG (256..512KB)
    lda #$20
    sta $5FF2               ; Waldo CHR (256..512KB)
    jmp $E000               ; Waldo Reset
@tramp_end:

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
@rest_ram:
    lda $6000,x
    sta $0000,x
    lda $6100,x
    sta $0100,x
    lda $6200,x
    sta $0200,x
    lda $6300,x
    sta $0300,x
    lda $6400,x
    sta $0400,x
    lda $6500,x
    sta $0500,x
    lda $6600,x
    sta $0600,x
    lda $6700,x
    sta $0700,x
    inx
    bne @rest_ram

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
    lda $F7
    and #$F7
    sta $F7
    lda $F5
    and #$F7
    sta $F5

@wait_up_rel:
    lda #$01
    sta $4016
    lda #$00
    sta $4016
    bit $4016
    bit $4016
    bit $4016
    bit $4016
    lda $4016
    and #$01
    bne @wait_up_rel

    bit $2002
@vwait:
    bit $2002
    bpl @vwait
    lda $FF
    sta $2000
    cli
    jmp $FFC5               ; SwapToPRG0 and RTS to BarbaUpdate

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
