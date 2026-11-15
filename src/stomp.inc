; Pre-enemy-update hook: allows Barba to stomp-kill the weakest enemies
; (HP 1..4) when descending onto them, before enemy contact damage runs.
.export BarbaPreEnemy

BarbaPreEnemy:
    jsr $9925
    jmp BarbaStomp
StompRet:
    rts
BarbaStomp:
    lda $0736
    cmp #$0B
    bne StompRet
    lda $B5
    cmp #$01
    bne StompRet
    lda $0707
    cmp #$01
    beq StompRet
    cmp #$02
    beq StompRet
    jsr BarbaPickup
    ; No stomps while a boss fight holds the scroll lock ($0728, cleared by the boss key):
    ; the stomp kills via the generic $E880 death before the enemy update, which skips the
    ; boss-death handler (bank 4 $B1E9) that drops the key -> locked room, softlock.
    lda $0728
    bne StompRet
    lda $0479
    beq @done
    lda $057D
    bmi @done
    ldx #$05
@loop:
    lda $B6,x
    cmp #$01
    bne @next
    lda $040E,x
    bne @next
    lda $A1,x
    cmp #$02
    bcc @next
    cmp #$23
    beq @next
    lda $C2,x
    beq @next
    cmp #$05
    bcs @next
    lda $29
    clc
    adc #$14
    bcs @next
    sec
    sbc $2A,x
    cmp #$11
    bcs @next
    lda $4E,x
    sec
    sbc $4D
    tay
    lda $3C,x
    sbc $3B
    pha
    tya
    clc
    adc #$08
    tay
    pla
    adc #$00
    bne @next
    cpy #$21
    bcs @next
    stx $10
    lda #$10
    sta $ED
    lda #$00
    sta $C2,x
    jsr $E880
    lda #$FC
    sta $057D
    lda #$01
    sta $0479
    rts
@next:
    dex
    bpl @loop
@done:
    rts

; Allow Barba to pick up keys, jars, P-bags and 1-Ups ($08..$0D, $10..$11) by
; touching them instead of requiring a crouched/angled fireball hit.
BarbaPickup:
    ldx #$05
@item_loop:
    lda $B6,x
    cmp #$01
    bne @item_next
    lda $A1,x
    cmp #$01
    bne @item_next
    lda $AF,x
    and #$7F
    cmp #$08
    bcc @item_next
    cmp #$0E
    bcc @check_box
    cmp #$10
    beq @check_box
    cmp #$11
    bne @item_next
@check_box:
    lda $2A,x
    sec
    sbc $29
    clc
    adc #$08
    cmp #$28
    bcs @item_next
    lda $4E,x
    sec
    sbc $4D
    tay
    lda $3C,x
    sbc $3B
    pha
    tya
    clc
    adc #$0A
    tay
    pla
    adc #$00
    bne @item_next
    cpy #$1B
    bcs @item_next
    stx $10
    jsr $E771
    ldx $10
@item_next:
    dex
    bpl @item_loop
    rts
