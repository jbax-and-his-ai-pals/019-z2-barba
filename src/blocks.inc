; Reuse the native glove-gated breakable-block handler at each live fireball,
; never at Barba's body. This keeps block gates usable after retiring melee.
.export BarbaBlocks, BarbaNativeBlocks, BarbaBlockSlot
BarbaBlocks:
    lda $0707
    beq @castle
    cmp #$03
    bcs @blocks
    ; Town ($0707 = 1/2) or North Palace ($0707 = 0, $0706 = 0, $0561 = 0):
    ; advance scorch marks first.
    bcc @town
@castle:
    lda $0561
    ora $0706
    bne @blocks
@town:
    jsr BarbaExtraEnsure
    jsr BarbaScorchTick
@blocks:
    jsr BarbaNativeBlocks
    lda EXTRA_LIVE
    beq @done
    lda $0707
    bne @extra
    lda $0706
    ora $0561
    bne @done
@extra:
    jsr BarbaExtraBlocks
@done:
    jsr BarbaSetThrusts ; restore held thrust after temporary projectile origins
    lda $0480
    cmp #$F8
    bcs @ret
    ldy $80
    cpy #$09
    bne @up_block
    pha
    adc #$05            ; carry is clear from cmp #$F8
    bcs @restore_down
    cmp #$F8
    bcs @restore_down
    sta $0480
    jsr $E1DD
@restore_down:
    pla
    sta $0480
@ret:
    rts
@up_block:
    jmp $E1DD
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
    beq @castle_slot
    cmp #$03
    bcs @native_block
    bcc BarbaTownBurn
@castle_slot:
    lda $0561
    ora $0706
    beq BarbaTownBurn
@native_block:
    lda #$09
    sta $80
    jsr $E1DD
@done:
    rts

; Scorch outdoor town props, bushes, signs, walls, windows, roofs and ground.
; Buildings and ground stay intact: the room's metatile (collision) buffer is
; never written. Only the on-screen nametable gets a 2x2 flame, which lasts up
; to SCORCH_TOWN_TIME*4 updates (~10s) or until evicted as the oldest of 16
; active fires, then turns to char. Sky ($40), clouds ($C4..$C6), doorways
; ($89..$8C, $91) and anything below the street ($C0+ offsets) are never
; touched. When a fireball flies through sky just above ground ($50..$5F), the
; ground below it ignites. Marks last until that column is redrawn or the room
; changes.
SCORCH_MAX = 16
SCORCH_MASK = SCORCH_MAX - 1
SCORCH_ROOM = $646A        ; room ($0561) the ring belongs to
SCORCH_HI = $6490          ; 16 PPU address high bytes
SCORCH_LO = $64A0          ; 16 PPU address low bytes
SCORCH_TIME = $64B0        ; 16 timers: 0 = free, >0 = active flame
SCORCH_HEAD = $64C0        ; next FIFO slot (0..15)
SCORCH_PAGE = $64C1        ; 16 world X high bytes (page 0..3)
SCORCH_TOWN_TIME = $96     ; 150 ticks * 4 updates = 600 updates (~10s)
SCORCH_PALACE_TIME = $18   ; 24 updates (~0.4s) for North Palace Zelda
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
    ldy $0707
    bne @town_filter
    ; North Palace: only sleeping Zelda ($4E head, $4F body) burns.
    cmp #$4E
    beq @burn
    cmp #$4F
    beq @burn
    rts
@town_filter:
    ldy $02
    cpy #$C0
    bcs @skip
    cmp #$40
    beq @check_ground_below
    cmp #$91
    beq @skip
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
@check_ground_below:
    lda $39
    clc
    adc #$10
    sta $39
    ldx #$10
    ldy #$1C
    jsr $EAE8
    ldy $02
    cpy #$C0
    bcs @skip
    cmp #$50
    bcc @skip
    cmp #$60
    bcs @skip
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
    lda #$08
    sta $00
    lda $39
    and #$F0
    asl
    rol $00
    asl
    rol $00
    and #$E0
    sta $01
    lda $5D
    and #$F0
    lsr
    lsr
    lsr
    ora $01
    sta $01
    pla
    ora $00
    sta $00
    ; Already burning: leave it.
    ldx #SCORCH_MAX-1
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
    ; Take a free slot from SCORCH_HEAD, else evict the oldest fire to char.
    ldx SCORCH_HEAD
    ldy #SCORCH_MAX
@free:
    lda SCORCH_TIME,x
    beq @take
    inx
    txa
    and #SCORCH_MASK
    tax
    dey
    bne @free
    lda $0362
    cmp #$1E
    bcc :+
    rts
:
    ldx SCORCH_HEAD
    jsr ScorchOnScreen
    bcc @take
    lda $00
    pha
    lda $01
    pha
    ldy #$04
    jsr ScorchQueueSlot
    pla
    sta $01
    pla
    sta $00
@take:
    lda $00
    sta SCORCH_HI,x
    lda $01
    sta SCORCH_LO,x
    lda $4B
    sta SCORCH_PAGE,x
    lda #SCORCH_TOWN_TIME
    ldy $0707
    bne :+
    lda #SCORCH_PALACE_TIME
:
    sta SCORCH_TIME,x
    inx
    txa
    and #SCORCH_MASK
    sta SCORCH_HEAD
    lda #$04
    sta $ED
    lda $0707
    beq @castle_scorch
    inc COMBO_ADD
    bne @queue_flame
@castle_scorch:
    jsr CastleZeldaShout
@queue_flame:
    ldy #$00
    ; fall through

; Queue a 2x2 tile write at $00/$01 from ScorchTiles,Y (two vertical columns).
ScorchQueue:
    lda $0707
    bne :+
    tya
    clc
    adc #$08
    tay
:
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

; Queue a 2x2 tile write for scorch slot X from ScorchTiles,Y, preserving X.
ScorchQueueSlot:
    lda SCORCH_HI,x
    sta $00
    lda SCORCH_LO,x
    sta $01
    txa
    pha
    jsr ScorchQueue
    pla
    tax
    rts

; Carry set if slot X's metatile is within [-16, +255] px of the camera ($072A/$072C).
; Clobbers A; preserves X, Y, $00, $01.
ScorchOnScreen:
    lda SCORCH_LO,x
    and #$1E
    asl
    asl
    asl
    sec
    sbc $072C
    pha
    lda SCORCH_PAGE,x
    sbc $072A
    beq @in_range
    cmp #$FF
    bne @offscreen
    pla
    cmp #$F0
    rts
@in_range:
    pla
    sec
    rts
@offscreen:
    pla
    clc
    rts

; Once per update in outdoor towns or North Palace: count down active flames
; and turn expired ones into char (if still on screen). A room change drops
; every entry (their addresses are stale).
BarbaScorchTick:
    lda $0561
    cmp SCORCH_ROOM
    beq ScorchRun
    sta SCORCH_ROOM
BarbaScorchClear:
    lda #$00
    sta SCORCH_HEAD
    ldx #SCORCH_MAX-1
@clear:
    sta SCORCH_TIME,x
    dex
    bpl @clear
    rts
ScorchRun:
    lda $0707
    beq @tick               ; North Palace: tick every update
    lda $12
    and #$03
    bne @anim               ; Towns: tick every 4th update (~10s for 150 ticks)
@tick:
    ldx #SCORCH_MAX-1
@entry:
    lda SCORCH_TIME,x
    beq @next
    dec SCORCH_TIME,x
    bne @next
    jsr ScorchOnScreen
    bcc @next
    lda $0362
    cmp #$28
    bcc @char
    inc SCORCH_TIME,x       ; PPU queue full: retry next tick
    bne @next
@char:
    ldy #$04
    jsr ScorchQueueSlot
@next:
    dex
    bpl @entry
    lda $0707
    bne @anim
    rts
@anim:
    lda $12
    tay
    and #$08
    asl
    sta $02                 ; $00 = flame A, $10 = flame B
    tya
    and #$07
    asl
    tax
    jsr ScorchAnimOne
    inx
ScorchAnimOne:
    lda SCORCH_TIME,x
    beq @skip_anim
    jsr ScorchOnScreen
    bcc @skip_anim
    lda $0362
    cmp #$28
    bcs @skip_anim
    ldy $02
    jsr ScorchQueueSlot
@skip_anim:
@anim_done:
    rts

; Column order per stage: top-left, bottom-left, top-right, bottom-right.
; Tile ids must match assets/town_fire.json (checked by tools/assets.py).
ScorchTiles:
    .byte $34,$AC,$A4,$C0   ; town flame A (CHR bank 7)
    .byte $C1,$A7,$35,$C2   ; town char (CHR bank 7)
    .byte $56,$57,$58,$59   ; North Palace flame (CHR bank 3)
    .byte $5A,$5B,$5C,$5D   ; North Palace char (CHR bank 3)
    .byte $A4,$C0,$34,$AC   ; town flame B (CHR bank 7, mirrored columns)
