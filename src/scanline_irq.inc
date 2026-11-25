; MMC3 Scanline IRQ engine & OAM shadow (Bank 6).
; Replaces Sprite-0 busy-wait + LateSplit with deterministic scanline IRQs:
;   1. Zero-jitter HUD split at scanline 30 (frees OAM slot 0 + ~1,600+ cycles).
;   2. Cloud parallax in overworld side-view encounters and palace entrances.
;   3. Surface shimmer over encounter water, palace lava, and title lava (R0 CHR swaps).
;   4. Bottom cinematic letterbox bar on Title roar, Dark Barba entrance, and Ending.

.export NmiVblankSetup6, CopyOamShadow6, CopySceneOam6, TitleEndNmi6, NmiRng6

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
CLOUD_DRIFT_SUB = $64FB ; fractional subpixel accumulator for idle cloud drift
CLOUD_DRIFT_X   = $64FC ; cloud drift pixel offset (0..255)
CLOUD_DRIFT_NT  = $64FD ; cloud drift nametable bit (0..1)
CLOUD_DX_HI     = $64F2 ; palace cloud sprite 9th X bit
CLOUD_COL       = $64F3 ; current tile column within cloud
CLOUD_IDX       = $64F4 ; current cloud index
CLOUD_Y         = $64F5 ; current cloud OAM Y
CLOUD_WIDTH     = $64F6 ; current cloud width in 8x16 tiles
CLOUD_ATTR      = $64F7 ; cloud OAM attribute ($23 palace / $21 town)
CLOUD_TILE      = $64F8 ; cloud OAM left tile ($C1 palace / $F7 town)

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
    beq @dec_macro
    sta OW_FOL_SKIP
    bne @done_macro
@dec_macro:
    dec $0725
@clear_buf:
    ldx @table0,y
    lda $0302,x
    sta OW_FOL_SKIP
    lda #$00
    sta $0301,x
    lda #$FF
    sta $0302,x
    lda $0725
@done_macro:
    sta $0725
    jsr IrqSetup6       ; arm MMC3 IRQ during VBlank (before sound driver!)
.ifdef WALDO_PORTAL
    jsr UpdateWaldoHatChr6
.endif
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
    lda OW_FOL_RUN
    beq :+
    jsr OwFoliageHop6
:
    jmp $FFC5           ; SwapToPRG0
@table0:
    .byte $00, $61, $A2

; NMI RNG update in Bank 6, then copy OAM shadow and jump to SwapToPRG0 ($C1A3).
NmiRng6:
    inc $12
    ldx #$00
    ldy #$09
    lda $051A
    eor $051B
    lsr
    lsr
@rng:
    ror $051A,x
    inx
    dey
    bne @rng
    jsr CopySceneOam6
    jsr FinishSceneOam6
    ; If game logic finished inside the next VBlank ($2002 bit 7 set), reading
    ; $2002 clears the VBlank flag so $C1B1's STA $2000 does not fire a
    ; truncated mid-VBlank NMI that overruns into active rendering and corrupts
    ; vertical scroll. Reset the HUD scroll and re-arm the MMC3 IRQ so the
    ; repeated frame stays split and jitter-free.
    bit $2002
    bpl @exit_nmi
    jsr VblankOverrun6
@exit_nmi:
.ifdef SOULS_BOSS_METER
    jmp $C1A5
.else
    jmp $C1A3
.endif
.segment "LAUGH_DELAY"
VblankOverrun6:
    lda IRQ_COUNT
    beq @done
    lda #$00
    sta IRQ_STAGE
    jsr ArmStage0_6
    lda $0736
    cmp #$0B
    bne @done
    jmp VblankHudReset6
@done:
    rts
.segment "BANK6"
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
    jmp PrioritizeRoomOam6

; Reuse the OAM copy caller's return address through the fixed mapper code.
EncounterTorsoHop6:
    bit $0100                 ; title has its own Barba sprite table
    bvc @done
    lda #>(EncounterTorsoFrom6-1)
    pha
    lda #<(EncounterTorsoFrom6-1)
    pha
    lda #$03
    jmp $FFCC
@done:
    rts

.segment "BANK6_OAM"
PrioritizeRoomOam6:
    lda $0707
    bne :+
    jmp EncounterTorsoHop6
:
    jmp ShoutOamPriority6

FinishSceneOam6:
    jsr SariaTipPriority6
    jsr DrawDownstabTailHop6
    jsr DrawPalaceClouds6
    jmp FinishBossOam6

DrawDownstabTailHop6:
    lda $0736
    cmp #$05
    beq @hop
    lda DRAW_FRAME
    cmp #$51
    bne @done
@hop:
    lda #>(DrawDownstabTail3-1)
    pha
    lda #<(DrawDownstabTail3-1)
    pha
    lda #$03
    jmp $FFCC
@done:
    rts

.segment "BANK6"
TitleEndNmi6:
    jsr CopyOamShadow6
    lda $6560
    cmp #$9F
    bne @irq
    ; Mirror the near tail tip's Y ($6544: $9F rest, $9D wag) onto the far tip ($6568).
    ; The table sentinel leaves $68 free, immediately before the stars.
    lda $6544
    sta $6568
    lda #TRAIL_TIP_FAR
    sta $6569
    lda #$02
    sta $656A
    lda #$A4
    sta $656B
@irq:
    jsr ShakeLavaOam6
    jsr IrqSetup6
    bit $2002
    tsx
    lda $0103,x         ; clear I flag in saved NMI status byte for title letterbox
    and #$FB
    sta $0103,x
    cli
    lda #>(TitleLavaParticles2 - 1)
    pha
    lda #<(TitleLavaParticles2 - 1)
    pha
    lda #$02
    jmp $FFCC           ; update title lava particles, then restore Bank 5

.segment "PALACE_SHAKE"
CopySceneOam6:
    jsr CopyOamShadow6
    jsr ShakeLavaOam6
    lda $0736
    cmp #$0F
    beq DrawExtendedFall6
    lda $076C
    cmp #$04                  ; ending routine changes game mode between phases
    bne @done
    lda $6528
    cmp #$C0
    bne @done
    lda $6529
    cmp #TRAIL_BEND_CENTER
    bne @done
    ; Ending: use the elbow's Y and curtain priority. Both the fireball
    ; and Zelda keep their original OAM entries.
    ldx #$00
    ldy #$00
@ending:
    lda $6528
    sta $6548,x
    lda EndingTrailTiles,y
    sta $6549,x
    lda $652A
    sta $654A,x
    lda EndingTrailX,y
    sta $654B,x
    iny
    inx
    inx
    inx
    inx
    cpx #$10
    bne @ending
@done:
    rts

.segment "LAIR_HUD_SHAKE"
EndingTrailTiles:
    .byte TRAIL_TORSO_LEFT, TRAIL_TORSO_RIGHT, TRAIL_TIP, TRAIL_TIP_FAR
.segment "PALACE_SHAKE"
EndingTrailX:
    .byte $58, $50, $48, $40

DrawExtendedFall6:
    ; Finish Barba before the shadow starts at $3C so he wins overlaps.
    ldx #$30
    ldy #$08                  ; Barba's native fall sprites
    jsr @actor
    ldx #$64
    ldy #$3C                  ; shadow's native fall sprites
@actor:
    lda $6520,y               ; second torso chunk
    cmp #$F0
    bcs @done
    sec
    sbc #$10
    bcc @done
    sta $6500,x
    sta $6504,x
    lda $6521,y
    sta $6501,x
    eor #$0E
    sta $6505,x
    lda $6522,y
    sta $6502,x
    sta $6506,x
    lda $6523,y
    sta $6503,x
    clc
    adc #$08
    sta $6507,x
    lda $6500,x
    sec
    sbc #$10
    bcc @done
    sta $6508,x
    lda #FALL_TAIL_TILE
    sta $6509,x
    lda $6502,x
    eor #$C0                  ; mirror the upward tip across the torso center
    sta $650A,x
    lda $6503,x
    clc
    adc #$04
    sta $650B,x
@done:
    rts

.segment "BANK6"

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
    jmp ArmStage0_6

@check_title:
    lda $0726
    bne @disarm
    lda ROAR_TIMER
    bne @arm_letterbox_only
.ifdef SAMPLED_ROAR
    lda ROAR_REQUEST
    bmi @arm_letterbox_only
.endif
@disarm:
    rts

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
    bcs @palace_setup

@single_hud_split:
    ; Towns ($0707 = 1, 2): single HUD split + idle cloud drift in outdoor rooms.
    jsr IsSpriteCloudRoom6
    bne :+
    jsr AdvanceCloudDrift6
:
    lda $FD
    sta IRQ_X,y
    lda $0746
    and #$01
    sta IRQ_CTRL,y
    iny
    jmp CheckDarkBarbaLetterbox6

; Encounter sky moves at half camera speed plus a slow idle wind drift.
@encounter_setup:
    lda OW_PARALLAX_LINE
    beq @encounter_ground
    jsr AdvanceCloudDrift6
    jsr ComputeHalfCamx6
    sta IRQ_X,y
    lda IRQ_TMP2
    sta IRQ_CTRL,y
    iny
    lda OW_PARALLAX_LINE
    jsr SetDeltaLine6
    lda $FE
    sta IRQ_MASK,y
@encounter_ground:
    jsr FullCamx6
    jmp FinishSetup6

; Palaces ($0707 >= 3):
;   31+:   full camX (preserves palace walls, curtains, doors, and bricks; lava animates via R1 CHR)
;   207+ (when ROOM_HAS_LAVA != 0): warm red emphasis ($2001 bit 5) over the bottom lava rows (no X wobble)
@palace_setup:
    jsr IsSpriteCloudRoom6
    bne :+
    jsr AdvanceCloudDrift6
:
    jsr UpdateLavaRoomFlag6
    jsr FullCamx6
    jsr ShakeLavaCamera6
    jmp LavaHazeSetup6

FullCamx6:
    lda $FD
    sta IRQ_X,y
    lda $0746
    and #$01
    sta IRQ_CTRL,y
    iny
    rts

CheckDarkBarbaLetterbox6:
    lda $0707
    cmp #$05
.ifdef SOULS_BOSS_METER
    bne @souls_check
    lda $B6
    cmp #$01
    bne @souls_check
    lda $A1
    cmp #$23
    bne @souls_check
    lda $0505           ; Dark Barba entrance pause timer
    bne @add_letterbox
    lda $63             ; Dark Barba phase < 3 (emergence)
    cmp #$03
    bcs @souls_check
.else
    bne FinishSetup6
    lda $B6
    cmp #$01
    bne FinishSetup6
    lda $A1
    cmp #$23
    bne FinishSetup6
    lda $0505           ; Dark Barba entrance pause timer
    bne @add_letterbox
    lda $63             ; Dark Barba phase < 3 (emergence)
    cmp #$03
    bcs FinishSetup6
.endif
@add_letterbox:
    lda #212
    jsr SetDeltaLine6
    jsr FullCamx6
    lda #$00
    sta IRQ_MASK-1,y
.ifdef SOULS_BOSS_METER
    jmp FinishSetup6
@souls_check:
    jmp CheckSoulsBossIrq6
.endif

FinishSetup6:
    sty IRQ_COUNT
ArmStage0_6:
    lda IRQ_LINES
    sta $C000
    sta $C001
    sta $E001
    rts

; Input: A = target scanline. Updates IRQ_LINES,y = target - IRQ_TMP0 - 1, IRQ_TMP0 = target.
SetDeltaLine6:
    tax
    sec
    sbc IRQ_TMP0
    sbc #$01
    sta IRQ_LINES,y
    stx IRQ_TMP0
    rts

; Advance slow idle cloud drift (1/16 px per frame = ~3.75 px/s).
; Decreasing the sky scroll moves eastern clouds to the right.
AdvanceCloudDrift6:
    lda CLOUD_DRIFT_SUB
    clc
    adc #16
    sta CLOUD_DRIFT_SUB
    bcc @drift_done
    lda $0706
    cmp #$02            ; East Hyrule
    beq @drift_right
    cmp #$01            ; shared Death Mountain / Maze Island region
    bne @drift_left
    lda $0707
    bne @drift_right    ; Palace 4 on Maze Island
@drift_left:
    inc CLOUD_DRIFT_X
    bne @drift_done
    lda $D1
    beq @drift_done
@wrap:
    lda CLOUD_DRIFT_NT
    eor #$01
    sta CLOUD_DRIFT_NT
@drift_done:
    rts
@drift_right:
    ; Borrow into the nametable bit even on a one-page map so the sky
    ; scroll stays continuous as the offset goes from 0 to -1.
    dec CLOUD_DRIFT_X
    lda CLOUD_DRIFT_X
    cmp #$FF
    beq @wrap
    rts

; Compute (camX/2 + CLOUD_DRIFT) into IRQ_TMP1 (low) and IRQ_TMP2 (nt bit 0). Returns A = IRQ_TMP1.
ComputeHalfCamx6:
    lda $072A
    lsr
    sta IRQ_TMP2
    lda $FD
    ror
    clc
    adc CLOUD_DRIFT_X
    sta IRQ_TMP1
    lda IRQ_TMP2
    adc CLOUD_DRIFT_NT
    and #$01
    sta IRQ_TMP2
    lda IRQ_TMP1
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
    sta OW_FOL_ACTIVE
    sta CLOUD_DRIFT_SUB
    sta CLOUD_DRIFT_X
    sta CLOUD_DRIFT_NT
    lda $0707
    beq @check_ow
    jsr IsSpriteCloudRoom6
    bne @exit
    jmp StripPalaceClouds6
@check_ow:
    lda $0561
    bne @scan_map
    lda $0706           ; room 0 is North Castle only in West Hyrule
    bne @scan_map
@exit:
    rts

@scan_map:
    lda #$00
    sta IRQ_TMP1        ; start offset of the row being tested
@count_sky_rows:
    ldx #$00           ; require sky/cloud tiles
    lda IRQ_TMP1
    jsr CheckSceneryRow6
    bcs @sky_ready
    tya
    sta IRQ_TMP1
    cpy #$A0
    bcc @count_sky_rows
@sky_ready:
    lda IRQ_TMP1
    beq @prune_start
    clc
    adc #31
    sta OW_PARALLAX_LINE
@prune_start:
    lda $00
    pha
    lda $01
    pha
    ldx #$03
@page_loop:
    lda PageLo6,x
    sta $00
    lda PageHi6,x
    sta $01
    lda IRQ_TMP1
    beq @prune_page
    ; Ground scrolling streams columns from all four pages into two PPU
    ; nametables. Repeat the sky on matching page parity, including the
    ; padding pages, so those writes preserve the independently scrolling sky.
    ldy #$00
    lda #$40
@clear_sky:
    sta ($00),y
    iny
    cpy IRQ_TMP1
    bcc @clear_sky
    ; Stagger the two clouds across rows when at least two are clear.
    ldy #$02
    txa
    lsr
    bcc :+
    iny
:
    lda #$C2
    sta ($00),y
    iny
    lda #$C4
    sta ($00),y
    ldy #$0A
    lda IRQ_TMP1
    cmp #$20
    bcc :+
    ldy #$1A
:
    txa
    lsr
    bcs :+
    iny
:
    lda #$C2
    sta ($00),y
    iny
    lda #$C4
    sta ($00),y
    ; Remove clouds outside the safe band.
@prune_page:
    cpx $D1
    bcc :+
    bne @next_page
:
    ldy IRQ_TMP1
@prune_y:
    lda ($00),y
    jsr PruneEncounterTile6
    sta ($00),y
    iny
    cpy #$D0
    bcc @prune_y
@next_page:
    dex
    bpl @page_loop
    pla
    sta $01
    pla
    sta $00

@check_grass_art:
    lda $076E
    and #$FE
    cmp #$02
    beq @find_grass
    cmp #$04
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

.segment "BANK6_CLOUD"
; A = world ($0707). Returns Z set iff the room uses behind-BG sprite clouds:
; outdoor town rooms ($0707=1,2; $0561 < $19 or $3C) and outdoor palace rooms.
; Preserve X and Y.
IsSpriteCloudRoom6:
    cmp #$00
    beq @no_cloud
    cmp #$03
    bcc @town
    cmp #$04
    bcc @palaces_125
    beq @palaces_346
    lda $0561
    beq @yes_cloud              ; Great Palace entrance ($00)
    cmp #$3F
    beq @yes_cloud              ; Great Palace exit/rooftop ($3F)
    cmp #$37
    bcc @no_cloud
    cmp #$3D
    bcc @yes_cloud              ; Great Palace outdoor bridge ($37-$3C)
@no_cloud:
    lda #$01
    rts
@town:
    lda $0561
    cmp #$19
    bcc @yes_cloud
    cmp #$3C
    rts
@palaces_125:
    lda $0561
    beq @yes_cloud              ; Palace 1
    cmp #$0E                    ; Palace 2
    beq @yes_cloud
    cmp #$23                    ; Palace 5
    rts
@palaces_346:
    lda $0561
    beq @yes_cloud              ; Palace 3
    cmp #$06                    ; Palace 3 outdoor courtyard
    beq @yes_cloud
    cmp #$0F                    ; Palace 4
    beq @yes_cloud
    cmp #$24                    ; Palace 6
    rts
@yes_cloud:
    lda #$00
    rts
VblankHudReset6:
    lda $0726
    bne @done
    lda $FF
    and #$FC
    sta $FF
    sta $2000
    lda #$00
    sta $2005
    sta $2005
@done:
    rts
.segment "BANK6"

; Input: A = metatile ID. Returns A = $40 if stray cloud, else A unchanged.
PruneEncounterTile6:
    cmp #$C2
    bcc @done
    cmp #$C5
    bcs @done
    lda #$40
@done:
    rts

; A = row offset, X = 0 for sky/clouds or 1 for sky/sprigs. C clear iff the
; whole row matches. X bit 7 records a sprig, Y ends at the next row.
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
    rts
@sprig:
    cmp #$8A            ; road/desert surface has transparent top tiles
    beq @match
    cmp #$4B            ; East Hyrule tree trunk can stand on a grass row
    bne :+
    lda $0706
    cmp #$02
    beq @match
    bne @miss
:
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

.segment "BANK6_CLOUD"
; Strip static background cloud metatiles ($C2-$C4 in palaces, $C4-$C6 in towns)
; so behind-background parallax cloud sprites replace them cleanly.
StripPalaceClouds6:
    lda $00
    pha
    lda $01
    pha
    ldx #$C2
    ldy #$C5
    lda $0707
    cmp #$03
    bcs :+
    ldx #$C4
    ldy #$C7
:
    stx IRQ_TMP0
    sty IRQ_TMP1
    ldx $D1
    cpx #$04
    bcc :+
    ldx #$03
:
@page_loop:
    lda PageLo6,x
    sta $00
    lda PageHi6,x
    sta $01
    ldy #$D0
@y_loop:
    dey
    lda ($00),y
    cmp IRQ_TMP0
    bcc :+
    cmp IRQ_TMP1
    bcs :+
    lda #$40
    sta ($00),y
:
    tya
    bne @y_loop
    dex
    bpl @page_loop
    pla
    sta $01
    pla
    sta $00
    rts
PageLo6:
    .byte $00, $D0, $A0, $70
PageHi6:
    .byte $60, $60, $61, $62

; Compute cache key A = ($0707 << 4) | ($0706 & $0F).
RoomCacheKey6:
    lda $0707
    asl
    asl
    asl
    asl
    ora $0706
    rts

; Keep all of Barba at $6500-$6528, then the villager's glyphs at $652C-$6544.
; The NES resolves both overlapping sprite pixels and the scanline limit
; by OAM order. Swap complete entries to keep the displaced sprites visible.
ShoutOamPriority6:
    lda $6467               ; SHOUT_WORD
    beq @ret
    lda $6465               ; SHOUT_SLOT ($FF = player shout)
    bmi @ret
    ldx #$04
@swap_sprite:
    ldy @shout_src,x
    stx IRQ_TMP0
    lda @shout_dst,x
    tax
@swap_byte:
    lda $6500,x
    pha
    lda $6500,y
    sta $6500,x
    pla
    sta $6500,y
    inx
    iny
    txa
    and #$03                ; both offsets start on a four-byte sprite boundary
    bne @swap_byte
    ldx IRQ_TMP0
    dex
    bpl @swap_sprite
@ret:
    jmp EncounterTorsoHop6
@shout_src:
    .byte $DC, $C4, $28, $4C, $00
@shout_dst:
    .byte $44, $3C, $C4, $38, $4C

.segment "BANK6_HAZE"
; Draw behind-background parallax clouds on outdoor town and palace rooms.
; Runs right after CopyOamShadow6 so live sprites in $6500-$65FF are never overwritten.
DrawPalaceClouds6:
    lda $0736
    cmp #$0B
    bne @exit
    lda $0726
    bne @exit
    lda $074C
    cmp #$02
    bcs @exit
    lda $0707
    beq @exit
    jsr IsSpriteCloudRoom6
    beq @active
@exit:
    rts
@active:
    ldx #$23                    ; palace: behind BG + palette 3
    ldy #$C1                    ; palace: left=$C1, mid=$C3, right=$C5
    lda $0707
    cmp #$03
    bcs :+
    ldx #$21                    ; town: behind BG + palette 1
    ldy #$89                    ; town: left=$89, mid=$8B, right=$8D ($89 ^ $04 == $8D)
:
    txa
    ldx $0706
    beq :+
    ora #$40                    ; + H-flip ($40) on eastern continent
:
    sta CLOUD_ATTR
    sty CLOUD_TILE

    jsr ComputeHalfCamx6        ; IRQ_TMP1 = scrollX_lo, IRQ_TMP2 = scrollX_hi (0..1)
    ldy #$FC                    ; scan OAM shadow backward ($FC..$68) so clouds stay behind live sprites
    ldx #$00
    stx CLOUD_IDX
@cloud_loop:
    lda CLOUD_IDX
    asl
    asl
    tax
    lda @clouds,x               ; Y coordinate (0 = end of table)
    bne :+
    rts
:
    sta CLOUD_Y
    lda @clouds+3,x             ; width in 8x16 tiles (3 or 4)
    sta CLOUD_WIDTH
    lda @clouds+1,x             ; baseX_lo
    sec
    sbc IRQ_TMP1
    sta IRQ_TMP0                ; dx_lo
    lda @clouds+2,x             ; baseX_hi (0 or 1)
    sbc IRQ_TMP2
    and #$01
    sta CLOUD_DX_HI             ; dx_hi (0 = on-screen 0..255, 1 = off-screen 256..511)
    beq :+
    lda IRQ_TMP0
    cmp #$E8                    ; off-screen (256..487): cannot wrap onto screen in <= 32px
    bcs :+
    jmp @next_cloud
:
    lda #$00
    sta CLOUD_COL
@tile_loop:
    lda CLOUD_DX_HI
    bne @next_tile
@find_slot:
    cpy #$68
    bcc @done
    lda $6500,y
    cmp #$F0
    bcs @slot_ok
    dey
    dey
    dey
    dey
    bne @find_slot
@slot_ok:
    lda CLOUD_Y
    sta $6500,y
    ldx CLOUD_COL
    beq @left_tile
    inx
    cpx CLOUD_WIDTH
    beq @right_tile
    lda CLOUD_TILE              ; middle cloud puff
    clc
    adc #$02
    bne @write_tile
@left_tile:
    lda CLOUD_TILE              ; left cloud puff
    bne @check_flip
@right_tile:
    lda CLOUD_TILE              ; right cloud puff
    clc
    adc #$04
@check_flip:
    ldx $0706
    beq @write_tile
    eor #$04                    ; swap left/right puff when H-flipped
@write_tile:
    sta $6501,y
    lda CLOUD_ATTR              ; behind background ($20) + palette + H-flip ($40) on east
    sta $6502,y
    lda IRQ_TMP0
    sta $6503,y
    dey
    dey
    dey
    dey
@next_tile:
    lda IRQ_TMP0
    clc
    adc #$08
    sta IRQ_TMP0
    bcc :+
    lda CLOUD_DX_HI
    eor #$01
    sta CLOUD_DX_HI
:
    inc CLOUD_COL
    lda CLOUD_COL
    cmp CLOUD_WIDTH
    bcs @next_cloud
    jmp @tile_loop
@next_cloud:
    inc CLOUD_IDX
    jmp @cloud_loop
@done:
    rts
@clouds:
    .byte 56,  24, 0, 3         ; (X=24,  Y=57,  24px)
    .byte 39, 128, 0, 3         ; (X=128, Y=40,  24px)
    .byte 89, 224, 0, 3         ; (X=224, Y=90,  24px)
    .byte 72,  80, 1, 3         ; (X=336, Y=73,  24px)
    .byte 0

; Encounter water and palace lava share surface patterns $98/$99. Swap R1
; during VBlank so bridges, shorelines and walls on the same lines stay still.
UpdateSceneryChr6:
    lda $0726
    bne @exit_chr
    lda $0736
    cmp #$05
    beq @overworld_chr
    cmp #$0B
    bne @exit_chr
    lda $074C
    cmp #$02
    bcc @chr_active
@exit_chr:
    rts
@overworld_chr:
    jmp UpdateOverworldWaterChr6
@chr_active:
    jsr UpdateCastleFlameChr6
    lda $0707
    beq @encounter_surfaces
    jsr IsSpriteCloudRoom6
    bne :+
    ldx #$05
    lda #228                ; palace entrance cloud sprites ($C0-$C5) in R5
    ldy $0707
    cpy #$03
    bcs @set_cloud_chr
    ldx #$04
    lda #229                ; town outdoor cloud sprites ($88-$8D) in R4 (bank 6 $80-$BF)
@set_cloud_chr:
    jsr WriteChrReg6
    cpx #$04
    bne :+
    lda #$10
    jsr UpdateGrassPhase6
:
    lda $0707
    cmp #$03
    bcs :+
    jmp TownFoulWaterChr6
:
    lda $076E
    and #$FE
    cmp #$08
    beq SceneryChrBase6
    cmp #$0A
    bcc SceneryChrDone6
    cmp #$1A
    bcc @cycle_surface
    rts
@encounter_surfaces:
    jsr UpdateGrassChr6
    lda $076E
    and #$FE
    cmp #$02
    beq :+
    cmp #$04
    bne SceneryChrDone6
:
@cycle_surface:
    ; The variants differ only in liquid patterns $98/$99. Cycle even when
    ; the room cache misses a liquid tile, including submerged swamp fill.
    lda $12
    lsr
    lsr
    and #$03
    beq SceneryChrBase6
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
    adc SceneryLavaVOff6,x
    ora #$80
    bne SceneryChrWrite6
SceneryChrBase6:
    lda $076E
    and #$FE
    asl
    asl
    ora #$06
SceneryChrWrite6:
    ldx #$01
    jsr WriteChrReg6
    sta LAVA_CHR_BANK       ; expose active R1 bank for test verification
SceneryChrDone6:
    rts
SceneryLavaVOff6:
    .byte $00, $00, $02, $04
FoulWaterBanks6:
    .byte 146, 148, 150, 152

; Select a pre-bent tip tile during VBlank. The rest of R0, including the
; bottom halves of the sprigs, is identical in every phase.
; West Hyrule clouds drift right-to-left (lead left); East Hyrule drifts left-to-right (lead right).
UpdateGrassChr6:
    lda OW_HAS_GRASS
    beq DoneGrassChr6
    lda $076E
    and #$FE
    cmp #$02
    beq @west
    cmp #$04
    bne DoneGrassChr6
    lda #$08
    bne UpdateGrassPhase6
@west:
    lda #$00
UpdateGrassPhase6:
    sta IRQ_TMP0
    lda $12
    lsr
    lsr
    lsr
    lsr
    and #$07
    ora IRQ_TMP0
    tax
    lda WindBank6,x
    ldx #$00
    jmp WriteChrReg6
DoneGrassChr6:
    rts
WindBank6:
    .byte 12, 210, 212, 210, 12, 206, 208, 206
    .byte 20, 246, 248, 246, 20, 250, 252, 250
    .byte 28, 28, 172, 172, 28, 28, 170, 170

.segment "BANK6"
; Shimmer $52/$53 flame sprites in R3 during VBlank across North Palace
; ($0707=0, $0706=0, $0561=0, $076E=$02 -> bank 9) and palaces ($0707>=3,
; $076E in {$0A,$0C,$0E,$12,$14,$18} -> bank 9; $16 -> bank 89).
UpdateCastleFlameChr6:
    lda $0707
    bne @palace
    lda $0706
    ora $0561
    bne @done
    lda $076E
    and #$FE
    cmp #$02
    bne @done
    ldy #$00
    beq @apply
@palace:
    cmp #$03
    bcc @done
    lda $076E
    and #$FE
    cmp #$0A
    bcc @done
    cmp #$1A
    bcs @done
    cmp #$10
    beq @done
    ldy #$00
    cmp #$16
    bne @apply
    iny
@apply:
    lda $12
    lsr
    lsr
    and #$07
    beq @base
    clc
    adc @var_base,y
    bne @write
@base:
    lda @base_bank,y
@write:
    ldx #$03
    jmp WriteChrReg6
@done:
    rts
@base_bank:
    .byte 9, 89
@var_base:
    .byte 213, 220

.segment "BANK6_OAM"
OwFoliageHop6:
    lda #>(OwFoliageTick2 - 1)
    pha
    lda #<(OwFoliageTick2 - 1)
    pha
    lda #$02
    jmp $FFCC

.segment "BANK6"
; Gently ripple overworld water/lava tile $6E on R0 during VBlank ($0736 = 5).
; Base R0 is 1KB banks 124/125 (4KB bank 31); variants live in 230/232/234/236.
UpdateOverworldWaterChr6:
    lda $12
    lsr
    lsr
    lsr
    lsr
    and #$07
    tax
    lda WaterBank6,x
    ldx #$00
    jsr WriteChrReg6
    jmp OwFoliageHop6
WriteChrReg6:
    stx $64D5
    stx $8000
    sta $8001
    rts

.segment "BANK6_HAZE"
WaterBank6:
    .byte 124, 230, 232, 230, 124, 234, 236, 234

; Title lava shimmer: trampoline to Bank 2 (TitleLavaChr2) in VBlank so R0
; cycles across banks 238/240/242/244 and R5 maps bank 154 for tiny lava bubbles.
.export TitleLavaChr6
TitleLavaChr6:
    lda #>(TitleLavaChr2 - 1)
    pha
    lda #<(TitleLavaChr2 - 1)
    pha
    lda #$02
    jmp $FFCC

.segment "BANK6"
; Warm red emphasis ($2001 bit 5) over the bottom lava rows (scanline 207+)
; without altering X scroll so adjacent bricks and ledges stay rock-solid.
LavaHazeSetup6:
    lda ROOM_HAS_LAVA
    beq @done
    lda #207
    jsr SetDeltaLine6
    lda IRQ_X
    sta IRQ_X,y
    lda IRQ_CTRL
    sta IRQ_CTRL,y
    lda $FE
    ora #$20
    sta IRQ_MASK,y
    iny
@done:
    jmp CheckDarkBarbaLetterbox6
.segment "BANK6_PAD"
; All three Saria street rooms use the same native town graphics ($076E=$06).
; The $7F liquid metatile picks palette 1 as each nametable column is drawn.
TownFoulWaterChr6:
    lda $0707
    cmp #$01
    bne @not_saria
    lda $056B
    cmp #$02
    bne @not_saria
    lda $0561
    cmp #$06
    bcc @not_saria
    cmp #$09
    bcs @not_saria
    lda $12
    lsr
    lsr
    lsr
    and #$03
    tax
    lda FoulWaterBanks6,x
    jmp SceneryChrWrite6
@not_saria:
    jmp SceneryChrBase6

; In the Saria streets, put the last two tail sprites behind the villagers.
; The head, main body, and shout slots keep their existing priority.
.segment "BANK6"
SariaTipPriority6:
    lda $0707
    cmp #$01
    bne @done
    lda $0561
    cmp #$06
    bcc @done
    cmp #$09
    bcs @done
    lda $6559
    cmp #TRAIL_TIP
    bne @done
    jmp SwapSariaTips6
@done:
    rts

.segment "BANK6_PAD"
SwapSariaTips6:
    ldx #$07
@swap:
    lda $6558,x
    tay
    lda $65F8,x
    sta $6558,x
    tya
    sta $65F8,x
    dex
    bpl @swap
    rts

CheckP6GemOam6:
    lda $0707
    cmp #$04
    bne @done
    lda $056B
    cmp #$06
    bne @done
    jmp CheckP6Room3A_6
@done:
    rts

.segment "BANK6_HAZE"
CheckP6Room3A_6:
    lda $0561
    cmp #$3A
    bne :+
    jmp RunBossMeter4From6
:
    rts

.segment "BANK6"
FinishBossOam6:
.ifdef WALDO_PORTAL
    jsr DrawWaldoHat6
.endif
    lda $0728
    bne RunBossMeter4From6
    jmp CheckP6GemOam6
RunBossMeter4From6:
    ; The bank-4 pass runs after the player and Dark Barba trail edits.
    ; Its mapper return consumes our caller's address on the stack.
    lda #>(DrawBossMeter4-1)
    pha
    lda #<(DrawBossMeter4-1)
    pha
    lda #$04
    jmp $FFCC
.ifdef SOULS_BOSS_METER
.segment "BANK6_HAZE"
CheckSoulsBossIrq6:
    lda $0728
    beq @clear
    lda SOULS_ACTIVE
    beq @done
    lda #212
    jsr SetDeltaLine6
    lda #$00
    sta IRQ_X,y
    lda #$01
    sta IRQ_CTRL,y
    lda #$0F            ; bit 0 sentinel -> SoulsIrqSplit ($2001=$0E + R1=156 + $2400)
    sta IRQ_MASK,y
    iny
    bne @done
@clear:
    sta SOULS_ACTIVE
    sta SOULS_PHASE
@done:
    jmp FinishSetup6
.endif
.segment "BANK5"
.export TitleEndHook5
TitleEndHook5:
    lda #>(TitleEndNmi6 - 1)
    pha
    lda #<(TitleEndNmi6 - 1)
    pha
    jmp SwapToBank6
