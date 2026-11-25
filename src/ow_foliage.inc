; Overworld independent grass & forest tile animation (Bank 2, BANK2_SMOKE).
; Animates individual grass ($6D -> $9E..$A3) and forest crown ($68 -> $A4..$A9,
; $6A -> $AA..$AF) tiles in CHR 31 R1 via VBlank nametable updates on 12
; independent WRAM slots (0..5 grass, 6..11 forest) with per-slot randomized
; sequences and frame intervals, completely decoupled from R0 water/swamp ripples.
;
; Split into two passes per NMI so VBlank only executes at most one short
; read-verify-write (~150-230 cycles, finishing well before scanline 261),
; while all timer math, RNG, and nametable coordinate staging run after sound.

OW_FOL_SLOTS     = 12
OW_FOL_GRASS_END = 6

OW_FOL_HI     = $6360   ; 12 bytes: PPU addr hi ($00 = free, else $20..$23/$28..$2B)
OW_FOL_LO     = $636C   ; 12 bytes: PPU addr lo
OW_FOL_TILE   = $6378   ; 12 bytes: expected current tile ID in VRAM
OW_FOL_SEQ    = $6384   ; 12 bytes: pattern*4 + step (0..39)
OW_FOL_TMR    = $6390   ; 12 bytes: frames remaining in current step
OW_FOL_ACTIVE = $639C   ; 1 byte: nonzero once cleared for current overworld
OW_FOL_WORLD  = $639D   ; 1 byte: last $0706
OW_FOL_RNG    = $639E   ; 1 byte: local LFSR
OW_FOL_CURSOR = $639F   ; 1 byte: rotating scan start index
OW_FOL_SKIP   = $63A0   ; 1 byte: $0302,x before NMI clear ($FF = no macro ran)
OW_FOL_RUN    = $63A1   ; 1 byte: 0 = VBlank PPU pass, 1 = post-sound logic pass
OW_FOL_Q_MODE = $63A2   ; 1 byte: 0=idle, 1=slot step, 2=spawn probe, $81..$84=result
OW_FOL_TMP0   = $63A3   ; 1 byte: nt_hi / temp
OW_FOL_TMP1   = $63A4   ; 1 byte: nt_lo / temp
OW_FOL_TMP2   = $63A5   ; 1 byte: loop counter / base temp
OW_FOL_Q_HI   = $63A6   ; 1 byte: queued PPU addr hi
OW_FOL_Q_LO   = $63A7   ; 1 byte: queued PPU addr lo
OW_FOL_Q_EXP  = $63A8   ; 1 byte: expected tile (mode 1) / matched base tile ($83)
OW_FOL_Q_NEW  = $63A9   ; 1 byte: new tile (mode 1) / grass tile (mode 2; 0=full)
OW_FOL_Q_FL   = $63AA   ; 1 byte: forest-L tile (mode 2; 0=full)
OW_FOL_Q_FR   = $63AB   ; 1 byte: forest-R tile (mode 2; 0=full)
OW_FOL_Q_SLOT = $63AC   ; 1 byte: slot index (mode 1) / grass seq (mode 2)
OW_FOL_Q_FSEQ = $63AD   ; 1 byte: forest-L seq (mode 2; +12 for forest-R)
OW_FOL_Q_GIDX = $63AE   ; 1 byte: preselected free grass slot (0..5)
OW_FOL_Q_FIDX = $63AF   ; 1 byte: preselected free forest slot (6..11)

PPU_CTRL_R    = $2000
PPU_STATUS_R  = $2002
PPU_SCROLL_R  = $2005
PPU_ADDR_R    = $2006
PPU_DATA_R    = $2007

.segment "BANK2_SMOKE"

OwFolNextRng2:
    lda OW_FOL_RNG
    bne :+
    lda #$A7
:
    asl
    bcc :+
    eor #$1D
:
    sta OW_FOL_RNG
    eor $051A
    eor $12
    rts

; Pick independent randomized duration in A for slot X (grass vs forest).
OwFolPickTimer2:
    jsr OwFolNextRng2
    cpx #OW_FOL_GRASS_END
    bcc @grass_tmr
    eor $051B
    and #$0F
    sta OW_FOL_TMP2
    jsr OwFolNextRng2
    and #$07
    clc
    adc OW_FOL_TMP2
    adc #10                 ; forest: 10..32 frames per step
    rts
@grass_tmr:
    eor $051C
    and #$1F
    clc
    adc #12                 ; grass: 12..43 frames per step
    rts

OwFolSetAddr2:
    bit PPU_STATUS_R
    lda OW_FOL_Q_HI
    sta PPU_ADDR_R
    lda OW_FOL_Q_LO
    sta PPU_ADDR_R
    rts

OwFoliageTick2:
    lda OW_FOL_RUN
    beq @vblank_pass
    lda #$00
    sta OW_FOL_RUN
    jsr OwFoliageLogic2
    lda #$06
    jmp $FFCC

; Fast VBlank pass: at most one VRAM read + one optional write, then restore scroll.
@vblank_pass:
    lda #$01
    sta OW_FOL_RUN
    lda OW_FOL_ACTIVE
    beq @vb_done
    lda $0706
    cmp OW_FOL_WORLD
    bne @vb_done
    lda $0524               ; pause/save routine
    ora $074C               ; dialog
    ora $0768               ; PPU effect
    ora $07AE               ; palette transfer
    bne @vb_done
    lda OW_FOL_SKIP
    cmp #$FF
    bne @vb_done
    lda OW_FOL_Q_MODE
    beq @vb_done
    cmp #$01
    beq @vb_slot
    cmp #$02
    beq @vb_spawn
@vb_done:
    lda #$06
    jmp $FFCC

@vb_slot:
    jsr OwFolSetAddr2
    lda PPU_DATA_R          ; dummy read
    lda PPU_DATA_R          ; current tile in VRAM
    cmp OW_FOL_Q_EXP
    beq @vb_slot_ok
    lda #$82                ; scrolled away or burned: drop slot
    bne @vb_finish_mode
@vb_slot_ok:
    jsr OwFolSetAddr2
    lda OW_FOL_Q_NEW
    sta PPU_DATA_R
    lda #$81                ; committed
    bne @vb_finish_mode

@vb_spawn:
    jsr OwFolSetAddr2
    lda PPU_DATA_R
    lda PPU_DATA_R
    cmp #$6D
    beq @sp_grass
    cmp #$68
    beq @sp_fl
    cmp #$6A
    beq @sp_fr
@sp_miss:
    lda #$84
    bne @vb_finish_mode
@sp_grass:
    ldy OW_FOL_Q_NEW
    beq @sp_miss
    bne @sp_hit
@sp_fl:
    ldy OW_FOL_Q_FL
    beq @sp_miss
    bne @sp_hit
@sp_fr:
    ldy OW_FOL_Q_FR
    beq @sp_miss
@sp_hit:
    sta OW_FOL_Q_EXP
    jsr OwFolSetAddr2
    sty PPU_DATA_R
    lda #$83
@vb_finish_mode:
    sta OW_FOL_Q_MODE
    lda $FF
    sta PPU_CTRL_R
    bit PPU_STATUS_R
    lda $FD
    sta PPU_SCROLL_R
    lda $FC
    sta PPU_SCROLL_R
    jmp @vb_done

; Consume last VBlank result when OW_FOL_Q_MODE != 0.
OwFolHandleResult2:
    bpl @pending
    cmp #$81
    beq @res_slot_ok
    cmp #$82
    beq @res_slot_drop
    cmp #$83
    beq @res_spawn_hit
@clear_mode:
    lda #$00                ; $84 = spawn miss
    sta OW_FOL_Q_MODE
    rts
@pending:
    ; VBlank skipped a pending spawn probe (macro/scroll ran): discard stale probe.
    cmp #$02
    beq @clear_mode
    rts

@res_slot_ok:
    ldx OW_FOL_Q_SLOT
    inc OW_FOL_SEQ,x
    ldy OW_FOL_SEQ,x
    lda FolSeqTiles,y
    beq @res_slot_drop
    sta OW_FOL_TILE,x
    jsr OwFolPickTimer2
    sta OW_FOL_TMR,x
    jmp @clear_mode
@res_slot_drop:
    ldx OW_FOL_Q_SLOT
    lda #$00
    sta OW_FOL_HI,x
    sta OW_FOL_Q_MODE
    rts

@res_spawn_hit:
    lda OW_FOL_Q_EXP
    cmp #$6D
    beq @commit_grass
    ldx OW_FOL_Q_FIDX
    lda OW_FOL_Q_FSEQ
    ldy OW_FOL_Q_EXP
    cpy #$68
    beq @got_f_seq
    clc
    adc #12                 ; forest-R patterns 7..9 = patterns 4..6 + 12 bytes
@got_f_seq:
    tay
    bne @commit_slot
@commit_grass:
    ldx OW_FOL_Q_GIDX
    ldy OW_FOL_Q_SLOT
@commit_slot:
    lda FolSeqTiles,y
    sta OW_FOL_TILE,x
    tya
    sta OW_FOL_SEQ,x
    lda OW_FOL_Q_HI
    sta OW_FOL_HI,x
    lda OW_FOL_Q_LO
    sta OW_FOL_LO,x
    jsr OwFolPickTimer2
    sta OW_FOL_TMR,x
    jmp @clear_mode

; Post-sound logic pass (runs outside VBlank; never touches PPU registers).
OwFoliageLogic2:
    lda $0524
    beq @not_paused
    lda #$00
    sta OW_FOL_ACTIVE
    sta OW_FOL_Q_MODE
    rts
@not_paused:
    lda OW_FOL_ACTIVE
    beq @clear_slots
    lda $0706
    cmp OW_FOL_WORLD
    beq @active_ok
@clear_slots:
    lda #$00
    ldx #OW_FOL_SLOTS - 1
@clr_loop:
    sta OW_FOL_HI,x
    dex
    bpl @clr_loop
    sta OW_FOL_Q_MODE
    lda $0706
    sta OW_FOL_WORLD
    lda #$01
    sta OW_FOL_ACTIVE
    lda $12
    eor $051A
    ora #$01
    sta OW_FOL_RNG
    rts

@active_ok:
    lda OW_FOL_Q_MODE
    beq @advance_timers
    jsr OwFolHandleResult2

@advance_timers:
    ; Rotate scan start by +5 mod 12 so no slot starves when >1 finish together.
    lda OW_FOL_CURSOR
    clc
    adc #$05
    cmp #OW_FOL_SLOTS
    bcc :+
    sbc #OW_FOL_SLOTS
:
    sta OW_FOL_CURSOR
    tax
    lda #OW_FOL_SLOTS
    sta OW_FOL_TMP2

@slot_loop:
    lda OW_FOL_HI,x
    beq @next_slot
    lda OW_FOL_TMR,x
    beq @slot_ready
    dec OW_FOL_TMR,x
    bne @next_slot
@slot_ready:
    lda OW_FOL_Q_MODE
    bne @next_slot          ; queue busy: keep TMR=0 for next frame
    stx OW_FOL_Q_SLOT
    lda OW_FOL_HI,x
    sta OW_FOL_Q_HI
    lda OW_FOL_LO,x
    sta OW_FOL_Q_LO
    lda OW_FOL_TILE,x
    sta OW_FOL_Q_EXP
    ldy OW_FOL_SEQ,x
    iny
    lda FolSeqTiles,y
    bne @stage_tile
    cpx #OW_FOL_GRASS_END
    bcc @base_grass
    cpy #(7 * 4)
    bcc @base_fl
    lda #$6A
    .byte $2C
@base_fl:
    lda #$68
    .byte $2C
@base_grass:
    lda #$6D
@stage_tile:
    sta OW_FOL_Q_NEW
    lda #$01
    sta OW_FOL_Q_MODE
@next_slot:
    inx
    cpx #OW_FOL_SLOTS
    bcc :+
    ldx #$00
:
    dec OW_FOL_TMP2
    bne @slot_loop

    lda OW_FOL_Q_MODE
    bne @done_logic
    lda $074C
    ora $0768
    bne @done_logic
    jmp OwFolPickSpawn2
@done_logic:
    rts

OwFolPickSpawn2:
    lda #$00
    sta OW_FOL_Q_NEW
    sta OW_FOL_Q_FL
    sta OW_FOL_Q_FR
    ldx #OW_FOL_GRASS_END - 1
@chk_g:
    lda OW_FOL_HI,x
    beq @has_g
    dex
    bpl @chk_g
    bmi @chk_f_start
@has_g:
    stx OW_FOL_Q_GIDX
    jsr OwFolNextRng2
    and #$03                ; grass pattern 0..3
    asl
    asl
    sta OW_FOL_Q_SLOT
    tay
    lda FolSeqTiles,y
    sta OW_FOL_Q_NEW

@chk_f_start:
    ldx #OW_FOL_SLOTS - 1
@chk_f:
    lda OW_FOL_HI,x
    beq @has_f
    dex
    cpx #OW_FOL_GRASS_END
    bcs @chk_f
    bcc @chk_any_free
@has_f:
    stx OW_FOL_Q_FIDX
    jsr OwFolNextRng2
    and #$03
    cmp #$03
    bcc :+
    sbc #$02                ; 0..2
:
    clc
    adc #$04                ; pattern base 4..6 (forest-L), +12 -> 7..9 (forest-R)
    asl
    asl
    sta OW_FOL_Q_FSEQ
    tay
    lda FolSeqTiles,y
    sta OW_FOL_Q_FL
    lda FolSeqTiles+12,y
    sta OW_FOL_Q_FR

@chk_any_free:
    lda OW_FOL_Q_NEW
    ora OW_FOL_Q_FL
    bne :+
    rts
:

    ; Pick random sx in 2..29 -> ppu_col in OW_FOL_TMP1.
    jsr OwFolNextRng2
    eor $051B
    and #$1F
    cmp #28
    bcc :+
    sbc #28
:
    clc
    adc #$02
    sta OW_FOL_TMP0
    lda $FD
    lsr
    lsr
    lsr
    clc
    adc OW_FOL_TMP0
    and #$1F
    sta OW_FOL_TMP1

    ; Pick random sy in 2..27 -> (OW_FOL_TMP0 = nt_hi, OW_FOL_TMP1 = nt_lo).
    jsr OwFolNextRng2
    eor $051C
    and #$1F
    cmp #26
    bcc :+
    sbc #26
:
    clc
    adc #$02
    sta OW_FOL_TMP0
    lda $FC
    lsr
    lsr
    lsr
    clc
    adc OW_FOL_TMP0         ; total_row (2..56)
    ldy #$00
    cmp #30
    bcc :+
    sbc #30
    ldy #$02
:
    sta OW_FOL_TMP0         ; local_row (0..29)
    tya
    eor $0747
    and #$02
    asl
    asl
    ora #$20
    sta OW_FOL_TMP2         ; $20 or $28
    lda OW_FOL_TMP0
    tay
    lsr
    lsr
    lsr
    ora OW_FOL_TMP2
    sta OW_FOL_TMP0         ; nt_hi
    tya
    and #$07
    asl
    asl
    asl
    asl
    asl
    ora OW_FOL_TMP1
    sta OW_FOL_TMP1         ; nt_lo

    ; Reject if this nametable cell is already active in any slot.
    ldx #OW_FOL_SLOTS - 1
@dup_loop:
    lda OW_FOL_HI,x
    cmp OW_FOL_TMP0
    bne @dup_next
    lda OW_FOL_LO,x
    cmp OW_FOL_TMP1
    beq @skip_spawn
@dup_next:
    dex
    bpl @dup_loop

    lda OW_FOL_TMP0
    sta OW_FOL_Q_HI
    lda OW_FOL_TMP1
    sta OW_FOL_Q_LO
    lda #$02
    sta OW_FOL_Q_MODE
@skip_spawn:
    rts

; 10 patterns x 4 bytes (0 terminates and reverts to base $6D / $68 / $6A).
FolSeqTiles:
    .byte $9E, $9F, $9E, $00    ; 0: grass gentle sway
    .byte $A0, $A1, $00, $00    ; 1: grass lower tuft flutter
    .byte $A2, $9E, $A3, $00    ; 2: grass cross breeze
    .byte $9F, $00, $00, $00    ; 3: grass quick tip twitch
    .byte $A4, $A5, $00, $00    ; 4: forest-TL upper crown rustle
    .byte $A6, $A7, $A4, $00    ; 5: forest-TL two-beat breeze
    .byte $A8, $A9, $00, $00    ; 6: forest-TL leaf sway
    .byte $AA, $AB, $00, $00    ; 7: forest-TR upper canopy rustle
    .byte $AC, $AD, $AA, $00    ; 8: forest-TR middle breeze
    .byte $AE, $AF, $00, $00    ; 9: forest-TR cross-canopy twitch
