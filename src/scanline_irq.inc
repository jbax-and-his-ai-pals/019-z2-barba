; MMC3 Scanline IRQ engine & OAM shadow (Bank 6).
; Replaces Sprite-0 busy-wait + LateSplit with deterministic scanline IRQs:
;   1. Zero-jitter HUD split at scanline 30 (frees OAM slot 0 + ~1,600+ cycles).
;   2. Cloud parallax in Overworld side-view encounters ($0707=0).
;   3. Surface shimmer over encounter water and palace lava.
;   4. Bottom cinematic letterbox bar on Title roar, Dark Barba entrance, and Ending.

.export NmiVblankSetup6, CopyOamShadow6, TitleEndNmi6

IRQ_STAGE     = $64D6
IRQ_COUNT     = $64D7
IRQ_LINES     = $64D8   ; 4 bytes: latch0, delta1, delta2, delta3
IRQ_X         = $64DC   ; 4 bytes: $2005 X scroll per split
IRQ_CTRL      = $64E0   ; 4 bytes: $2000 nametable bit (0 or 1) per split
IRQ_MASK      = $64E4   ; 4 bytes: $2001 PPU_MASK per split
ROOM_HAS_LAVA = $64E8
LAST_LAVA_RM  = $64E9
LAST_LAVA_WLD = $64EA
IRQ_TMP0      = $64EB   ; prev scanline / temp
IRQ_TMP1      = $64EC   ; camX/2 low / temp
IRQ_TMP2      = $64ED   ; camX/2 nt  / temp
OW_PARALLAX_LINE = $64EE ; 0 = off, else sky/ground split scanline (16k+31)
LAVA_CHR_BANK = $64EF   ; last liquid R1 bank, for emulator checks
OW_HAS_GRASS = $64F0    ; qualifying row using the West Hyrule sprig art
OW_HAS_WATER  = $64F1

.segment "BANK6"

NmiVblankSetup6:
    ldy #$00
    ldx $0725
    beq @clear_buf
    iny
    cpx #$01
    beq @dec_macro
    iny
    lda #$00
    cpx #$02
    bne @done_macro
@dec_macro:
    dec $0725
@clear_buf:
    ldx @table0,y
    lda #$00
    sta $0301,x
    lda #$FF
    sta $0302,x
    lda $0725
@done_macro:
    sta $0725
    jsr IrqSetup6       ; arm MMC3 IRQ during VBlank (before sound driver!)
    jsr UpdateSceneryChr6
    jsr SetupEncounterScenery6
    jsr $9000           ; native sound driver (Bank 6)
    tsx
    lda $0104,x         ; clear I flag in saved NMI status byte so IRQs stay
    and #$FB            ; enabled after NMI returns to the main loop (RTI)
    sta $0104,x
    cli                 ; enable scanline IRQs for the frame
.ifdef WALDO_PORTAL
    jsr BarbaWaldoPortal6
.endif
    jmp $FFC5           ; SwapToPRG0
@table0:
    .byte $00, $61, $A2

; Copy $0200-$02FF -> $6500-$65FF, rebasing the 8x16 sprite tiles.
; Hide native blank cells ($F5) so they cannot fetch from $0000 between
; $1000 sprite fetches and give the MMC3 a second A12 clock on one scanline.
; Unrolled 4x for low per-frame NMI overhead (~16 iterations instead of 64).
CopyOamShadow6:
    ldx #$00
@loop:
    .repeat 4, i
    lda $0200 + i*4,x
    sta $6500 + i*4,x
    cmp #$F0
    bcs :++
    lda $0201 + i*4,x
    cmp #$F5
    bne :+
    lda #$F8
    sta $6500 + i*4,x
    bne :++
:
    eor #$01
    sta $6501 + i*4,x
    lda $0202 + i*4,x
    sta $6502 + i*4,x
    lda $0203 + i*4,x
    sta $6503 + i*4,x
:
    .endrep
    txa
    clc
    adc #$10
    tax
    beq @done
    jmp @loop
@done:
    rts

TitleEndNmi6:
    jsr CopyOamShadow6
    jsr IrqSetup6
    bit $2002
    tsx
    lda $0103,x         ; clear I flag in saved NMI status byte for title letterbox
    and #$FB
    sta $0103,x
    cli
    lda #$05
    jmp $FFCC           ; restore Bank 5 before returning to $A696

; Program IRQ_LINES/X/CTRL/MASK for the current frame and arm MMC3 if active.
IrqSetup6:
    sta $E000           ; ensure any stale IRQ is disabled/acked
    lda #$00
    sta IRQ_STAGE
    sta IRQ_COUNT

    ; Title screen ($0100 bit 6 = 0): letterbox during roar
    bit $0100
    bvc @check_title

    ; Ending ($0736 == $08, $076C == $03, $0726 == 0): letterbox
    lda $0736
    cmp #$08
    bne @check_sideview
    lda $076C
    cmp #$03
    bne @disarm
    lda $0726
    bne @disarm
    jmp @arm_letterbox_only

@check_title:
    lda $0726
    bne @disarm
    lda ROAR_TIMER
    bne @arm_letterbox_only
.ifdef SAMPLED_ROAR
    lda ROAR_REQUEST
    bmi @arm_letterbox_only
.endif
    rts

@disarm:
    rts

@arm_letterbox_only:
    lda #215
    sta IRQ_LINES
    lda $FD
    sta IRQ_X
    lda #$00
    sta IRQ_CTRL
    sta IRQ_MASK        ; $2001 = $00 (black bar scanlines 216..239)
    lda #$01
    sta IRQ_COUNT
    jmp @arm_stage0

@check_sideview:
    cmp #$0B
    bne @disarm
    lda $0726
    bne @disarm
    lda $074C
    cmp #$02
    bcc @setup_hud
    ; Town dialogue still needs the room scroll below the HUD. The MMC3 split
    ; replaces the native scroll write in the town dialogue routine ($B08F).
    lda $0707
    sbc #$01            ; carry set by CMP above
    cmp #$02
    bcs @disarm         ; only West and East Hyrule towns ($01/$02)

@setup_hud:
    ; Side-view split 0: HUD boundary at scanline 31.
    ldy #$00
    lda #31
    sta IRQ_LINES,y
    sta IRQ_TMP0        ; last programmed scanline = 31
    lda $FE
    sta IRQ_MASK,y

    lda $0707
    beq @encounter_setup
    cmp #$03
    bcc @single_hud_split
    jmp @palace_setup

@single_hud_split:
    ; Towns ($0707 = 1, 2): single HUD split.
    lda $FD
    sta IRQ_X,y
    lda $0746
    and #$01
    sta IRQ_CTRL,y
    iny
    jmp @check_dark_barba_letterbox

; Encounter sky moves at half camera speed.
@encounter_setup:
    lda OW_PARALLAX_LINE
    beq @encounter_ground
    jsr @compute_half_camx
    sta IRQ_X,y
    lda IRQ_TMP2
    sta IRQ_CTRL,y
    iny
    lda OW_PARALLAX_LINE
    jsr @set_delta_line
    lda $FE
    sta IRQ_MASK,y
@encounter_ground:
    jsr @full_camx
    jmp @finish_setup

; Palaces ($0707 >= 3):
;   31+:   full camX (preserves palace walls, curtains, doors, and bricks; lava animates via R1 CHR)
@palace_setup:
    jsr UpdateLavaRoomFlag6
    jsr @full_camx
    jmp @check_dark_barba_letterbox

@full_camx:
    lda $FD
    sta IRQ_X,y
    lda $0746
    and #$01
    sta IRQ_CTRL,y
    iny
    rts

@check_dark_barba_letterbox:
    lda $0707
    cmp #$05
    bne @finish_setup
    lda $B6
    cmp #$01
    bne @finish_setup
    lda $A1
    cmp #$23
    bne @finish_setup
    lda $0505           ; Dark Barba entrance pause timer
    bne @add_letterbox
    lda $63             ; Dark Barba phase < 3 (emergence)
    cmp #$03
    bcs @finish_setup
@add_letterbox:
    lda #215
    jsr @set_delta_line
    lda $FD
    sta IRQ_X,y
    lda $0746
    and #$01
    sta IRQ_CTRL,y
    lda #$00
    sta IRQ_MASK,y
    iny

@finish_setup:
    sty IRQ_COUNT
@arm_stage0:
    lda IRQ_LINES
    sta $C000
    sta $C001
    sta $E001
    rts

; Input: A = target scanline. Updates IRQ_LINES,y = target - IRQ_TMP0 - 1, IRQ_TMP0 = target.
@set_delta_line:
    tax
    sec
    sbc IRQ_TMP0
    sbc #$01
    sta IRQ_LINES,y
    stx IRQ_TMP0
    rts

; Compute camX/2 into IRQ_TMP1 (low) and IRQ_TMP2 (nt bit 0). Returns A = IRQ_TMP1.
@compute_half_camx:
    lda $072A
    lsr
    lda $FD
    ror
    sta IRQ_TMP1
    lda $072A
    lsr
    and #$01
    sta IRQ_TMP2
    lda IRQ_TMP1
    rts

; Compute cache key A = ($0707 << 4) | ($0706 & $0F).
RoomCacheKey6:
    lda $0707
    asl
    asl
    asl
    asl
    sta IRQ_TMP2
    lda $0706
    and #$0F
    ora IRQ_TMP2
    rts

; Mode 9 step 0: the metatile map is ready and the nametables haven't been drawn.
; Check only the area's populated pages ($D1 is the last page index).
SetupEncounterScenery6:
    lda $0736
    cmp #$09
    bne @exit
    lda $073D
    bne @exit
    lda #$00
    sta OW_PARALLAX_LINE
    sta OW_HAS_GRASS
    sta OW_HAS_WATER
    lda $0707
    bne @exit
    lda $0561
    bne @scan_map
    lda $0706           ; room 0 is North Castle only in West Hyrule
    bne @scan_map
@exit:
    rts

@scan_map:
    lda #$00
    sta IRQ_TMP1        ; start offset of the row being tested
    sta IRQ_TMP2        ; at least one completed sky row has a cloud
@count_sky_rows:
    ldx #$00           ; require sky/cloud tiles
    lda IRQ_TMP1
    jsr CheckSceneryRow6
    bcs @sky_ready
    tya
    sta IRQ_TMP1
    txa
    and #$80
    ora IRQ_TMP2
    sta IRQ_TMP2
    cpy #$A0
    bcc @count_sky_rows
@sky_ready:
    lda IRQ_TMP1
    beq @prune_start
    clc
    adc #31
    sta OW_PARALLAX_LINE
    lda IRQ_TMP2
    bne @prune_start
    ; The top row is empty sky. Give each page a small cloud with staggered X.
    .repeat 4, page
        lda #$C2
        sta $6000 + page*$D0 + ((3 + 5*page) .mod 11)
        lda #$C4
        sta $6001 + page*$D0 + ((3 + 5*page) .mod 11)
        .if page < 3
            lda $D1
            cmp #page+1
            bcc @prune_start
        .endif
    .endrep
@prune_start:
    lda IRQ_TMP1
    tay
    ; Remove clouds outside the safe band and check every remaining row for
    ; water/lava surfaces, including cave pools and bridge gaps.
@prune:
    .repeat 4, page
        lda $6000 + page*$D0,y
        cmp #$80
        beq :+
        cmp #$87
        beq :+
        cmp #$88
        bne :++
:
        sta OW_HAS_WATER
:
        cmp #$C2
        bcc :+
        cmp #$C5
        bcs :+
        lda #$40
        sta $6000 + page*$D0,y
:
        .if page < 3
            lda $D1
            cmp #page+1
            bcc @prune_next
        .endif
    .endrep
@prune_next:
    iny
    cpy #$D0
    bcs @check_grass_art
    jmp @prune

@check_grass_art:
    lda $076E
    and #$FE
    cmp #$02            ; East Hyrule uses different art at pattern $4E
    bne @no_grass
@find_grass:
    lda IRQ_TMP1
    ldx #$01
    jsr CheckSceneryRow6
    bcs @next_grass_row
    txa
    bmi @grass_found
@next_grass_row:
    lda IRQ_TMP1
    clc
    adc #$10
    sta IRQ_TMP1
    cmp #$C0
    bcc @find_grass
@no_grass:
    rts
@grass_found:
    lda #$01
    sta OW_HAS_GRASS
    rts

; A = row offset, X = 0 for sky/clouds or 1 for sky/sprigs. C clear iff the
; whole row matches. X bit 7 records a cloud/sprig, Y ends at the next row.
CheckSceneryRow6:
    tay
    clc
    adc #$10
    sta IRQ_TMP0
@column:
    .repeat 4, page
        lda $6000 + page*$D0,y
        jsr CheckSceneryTile6
        bcs @row_end
        .if page < 3
            lda $D1
            cmp #page+1
            bcc @next_column
        .endif
    .endrep
@next_column:
    iny
    cpy IRQ_TMP0
    bcc @column
    clc
@row_end:
    rts

CheckSceneryTile6:
    cmp #$40
    beq @match
    pha
    txa
    lsr
    pla
    bcs @sprig
    cmp #$C2
    bcc @miss
    cmp #$C5
    bcs @miss
    ldx #$80
    bne @match
@sprig:
    cmp #$8A            ; road/desert surface has transparent top tiles
    beq @match
    cmp #$81            ; single/double weed or grass sprig background
    bcc @miss
    cmp #$84
    bcs @miss
    ldx #$81
@match:
    clc
    rts
@miss:
    sec
    rts

; Detect if the current palace room contains lava metatiles ($8520 in area bank).
; Cached per (world, region, room) so it only scans 64 bytes once on room entry.
UpdateLavaRoomFlag6:
    lda $0561
    cmp LAST_LAVA_RM
    bne @rescan_lava
    jsr RoomCacheKey6
    cmp LAST_LAVA_WLD
    bne @rescan_lava
    rts
@rescan_lava:
    lda $0561
    sta LAST_LAVA_RM
    jsr RoomCacheKey6
    sta LAST_LAVA_WLD
    lda #$00
    sta ROOM_HAS_LAVA
    lda #$92            ; Bank 3 (Palaces 1/2/5) lava metatile
    ldx $0707
    cpx #$03
    beq @have_lava_id
    lda #$83            ; Bank 4/5 (Palaces 3/4/6 & Great Palace) lava metatile
@have_lava_id:
    ldx #$1F
@scan_row:
    cmp $60B0,x
    beq @found_lava
    cmp $6180,x
    beq @found_lava
    cmp $6250,x
    beq @found_lava
    cmp $6320,x
    beq @found_lava
    dex
    bpl @scan_row
    rts
@found_lava:
    lda #$01
    sta ROOM_HAS_LAVA
    rts

; Encounter water and palace lava share surface patterns $98/$99. Swap R1
; during VBlank so bridges, shorelines and walls on the same lines stay still.
UpdateSceneryChr6:
    lda $0736
    cmp #$0B
    bne @lava_chr_done
    lda $074C
    cmp #$02
    bcs @lava_chr_done
    lda $0726
    bne @lava_chr_done
    lda $0707
    beq @encounter_surfaces
    cmp #$03
    bcc @lava_chr_done
    lda $076E
    and #$FE
    cmp #$1A
    bcs @lava_chr_done
    ldx ROOM_HAS_LAVA
    jmp @check_surface
@encounter_surfaces:
    jsr UpdateGrassChr6
    lda $076E
    and #$FE
    cmp #$02
    beq :+
    cmp #$04
    bne @lava_chr_done
:
    ldx OW_HAS_WATER
@check_surface:
    beq @lava_chr_base
    lda $12
    lsr
    lsr
    and #$03
    beq @lava_chr_base
    tax
    lda $076E
    and #$FE
    lsr
    sta IRQ_TMP0
    asl
    clc
    adc IRQ_TMP0
    asl
    clc
    adc @lava_v_off,x
    ora #$80
    bne @lava_chr_write
@lava_chr_base:
    lda $076E
    and #$FE
    asl
    asl
    ora #$06
@lava_chr_write:
    ldx #$01
    stx $64D5
    stx $8000
    sta $8001
    sta LAVA_CHR_BANK       ; expose active R1 bank for test verification
@lava_chr_done:
    rts
@lava_v_off:
    .byte $00, $00, $02, $04

; Select a pre-bent tip tile during VBlank. The rest of R0, including the
; bottom halves of the sprigs, is identical in every phase.
UpdateGrassChr6:
    lda OW_HAS_GRASS
    beq @done
    lda $076E
    and #$FE
    cmp #$02
    bne @done
    lda $12
    lsr
    lsr
    lsr
    and #$07
    tax
    lda @wind_bank,x
    ldx #$00
    stx $64D5
    stx $8000
    sta $8001
@done:
    rts
@wind_bank:
    .byte 12, 206, 208, 206, 12, 210, 212, 210

.segment "BANK5"
.export TitleEndHook5
TitleEndHook5:
    lda #>(TitleEndNmi6 - 1)
    pha
    lda #<(TitleEndNmi6 - 1)
    pha
    jmp SwapToBank6
