; Reuse the native glove-gated breakable-block handler at each live fireball,
; never at Barba's body. This keeps block gates usable after retiring melee.
.export BarbaBlocks, BarbaNativeBlocks, BarbaBlockSlot
BarbaBlocks:
    lda $0707
    cmp #$03
    beq @done
    ; Outdoor town ($0707 = 1/2, $0706 = 0): advance scorch marks first.
    cmp #$01
    beq @town
    cmp #$02
    bne @blocks
@town:
    lda $0706
    bne @blocks
    jsr BarbaExtraEnsure
    jsr BarbaScorchTick
@blocks:
    jsr BarbaNativeBlocks
    lda $0707
    beq @done
    jmp BarbaExtraBlocks
@done:
    rts
BarbaNativeBlocks:
    lda $8D
    ora $8E
    bne :+
    rts
:
    lda $80
    pha
    lda $047E
    pha
    lda $057D
    pha
    ldx #$01
    jsr BarbaBlockSlot
    ldx #$00
    jsr BarbaBlockSlot
    pla
    sta $057D
    pla
    sta $047E
    pla
    sta $80
    lda #$F8
    sta $0480
    rts

; Check one projectile slot X against glove-gated breakable blocks.
; Caller must save/restore $80, $047E, $057D and reset $0480 = #$F8.
BarbaBlockSlot:
    lda $8D,x
    beq @done
    bmi @done
    lda $5A,x
    sec
    sbc $072C
    sta $047E
    lda $48,x
    sbc $072A
    bne @done
    lda $36,x
    cmp #$20
    bcc @done
    cmp #$D8
    bcs @done
    clc
    adc #$05
    sta $0480
    ; Native down-tech branch uses the supplied world origin and avoids
    ; applying horizontal sword recoil to Barba on contact with stone.
    lda $0707
    cmp #$01
    beq @check_town
    cmp #$02
    bne @native_block
@check_town:
    lda $0706
    beq BarbaTownBurn
@native_block:
    lda #$09
    sta $80
    jsr $E1DD
@done:
    rts

; Scorch outdoor town props, bushes, signs, walls, windows and roofs. Buildings
; stay intact: the room's metatile (collision) buffer is never written. Only the
; on-screen nametable gets a 2x2 flame, which turns to char SCORCH_FLAME updates
; later. Ground ($50..$5F), sky ($40), clouds ($C4..$C6), doorways ($89..$8C,
; $91) and anything below the street ($B0+ offsets) are never touched. Marks
; last until that column is redrawn (scrolling about two screens away, or
; leaving the room). Up to eight recent marks are tracked in WRAM so a slow
; fireball does not re-ignite the metatile it is still crossing.
SCORCH_ROOM = $646A        ; room ($0561) the ring belongs to
SCORCH_HI = $6470          ; 8 PPU address high bytes
SCORCH_LO = $6478          ; 8 PPU address low bytes
SCORCH_TIME = $6480        ; 8 timers: $FF at ignition, 0 = free
SCORCH_FLAME = $18         ; updates of flame before char
SCORCH_CHAR_AT = $FF - SCORCH_FLAME
BarbaTownBurn:
    lda $0480
    clc
    adc #$03
    sta $39
    lda $047E
    clc
    adc #$04
    adc $072C
    sta $5D
    lda $072A
    adc #$00
    sta $4B
    ldx #$10
    ldy #$1C
    jsr $EAE8
    ldy $02
    cpy #$B0
    bcs @skip
    cmp #$40
    beq @skip
    cmp #$91
    beq @skip
    cmp #$50
    bcc @check_door
    cmp #$60
    bcc @skip
@check_door:
    cmp #$89
    bcc @check_cloud
    cmp #$8D
    bcc @skip
@check_cloud:
    cmp #$C4
    bcc @burn
    cmp #$C7
    bcs @burn
@skip:
    rts
@burn:
    lda $0362
    cmp #$28
    bcs @skip
    ; PPU address of the metatile's top-left tile: $00 = high, $01 = low.
    lda $4B
    and #$01
    asl
    asl
    pha
    lda $39
    and #$F0
    sta $02
    lda $5D
    and #$F0
    sta $03
    lda #$08
    sta $00
    lda $02
    asl
    rol $00
    asl
    rol $00
    and #$E0
    sta $01
    lda $03
    lsr
    lsr
    lsr
    ora $01
    sta $01
    pla
    ora $00
    sta $00
    ; Already burning or recently charred: leave it.
    ldx #$07
@find:
    lda SCORCH_TIME,x
    beq @next_find
    lda SCORCH_LO,x
    cmp $01
    bne @next_find
    lda SCORCH_HI,x
    cmp $00
    beq @skip
@next_find:
    dex
    bpl @find
    ; Take a free entry, else the oldest one already past its flame stage.
    ldx #$07
@free:
    lda SCORCH_TIME,x
    beq @take
    dex
    bpl @free
    ldx #$07
@aged:
    lda SCORCH_TIME,x
    cmp #SCORCH_CHAR_AT
    bcc @take
    dex
    bpl @aged
    rts                     ; eight flames already burning: skip this one
@take:
    lda $00
    sta SCORCH_HI,x
    lda $01
    sta SCORCH_LO,x
    lda #$FF
    sta SCORCH_TIME,x
    lda #$04
    sta $ED
    ldy #$00
    ; fall through

; Queue a 2x2 tile write at $00/$01 from ScorchTiles,Y (two vertical columns).
ScorchQueue:
    ldx $0362
    lda $00
    sta $0363,x
    sta $0368,x
    lda $01
    sta $0364,x
    clc
    adc #$01
    sta $0369,x
    lda #$82
    sta $0365,x
    sta $036A,x
    lda ScorchTiles,y
    sta $0366,x
    lda ScorchTiles+1,y
    sta $0367,x
    lda ScorchTiles+2,y
    sta $036B,x
    lda ScorchTiles+3,y
    sta $036C,x
    lda #$FF
    sta $036D,x
    txa
    clc
    adc #$0A
    sta $0362
    lda #$01
    sta $0725
    rts

; Once per update in outdoor towns: turn finished flames into char and age
; entries out. A room change drops every entry (their addresses are stale).
BarbaScorchTick:
    lda $0561
    cmp SCORCH_ROOM
    beq ScorchRun
    sta SCORCH_ROOM
BarbaScorchClear:
    lda #$00
    ldx #$07
@clear:
    sta SCORCH_TIME,x
    dex
    bpl @clear
    rts
ScorchRun:
    ldx #$07
@entry:
    lda SCORCH_TIME,x
    beq @next
    dec SCORCH_TIME,x
    lda SCORCH_TIME,x
    cmp #SCORCH_CHAR_AT
    bne @next
    lda $0362
    cmp #$28
    bcc @char
    inc SCORCH_TIME,x       ; PPU queue full: retry next update
    bne @next
@char:
    lda SCORCH_HI,x
    sta $00
    lda SCORCH_LO,x
    sta $01
    txa
    pha
    ldy #$04
    jsr ScorchQueue
    pla
    tax
@next:
    dex
    bpl @entry
    rts

; Column order per stage: top-left, bottom-left, top-right, bottom-right.
; Tile ids must match assets/town_fire.json (checked by tools/assets.py).
ScorchTiles:
    .byte $02,$0E,$04,$16   ; flame
    .byte $25,$A7,$96,$B9   ; char
