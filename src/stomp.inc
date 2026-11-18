; Pre-enemy-update hook: allows Barba to stomp-kill easy enemies
; (HP 1..16, excluding shielded palace enemies) when descending onto them,
; before enemy contact damage runs.
.export BarbaPreEnemy

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
    lda #$0A
    jsr StompDeltaX
    bcs @item_next
    cmp #$1B
    bcs @item_next
    stx $10
    jsr $E771
    ldx $10
@item_next:
    dex
    bpl @item_loop
StompRet:
    rts

BarbaPreEnemy:
    jsr $9925
BarbaStomp:
    lda $0736
    cmp #$0B
    bne StompRet
    lda $B5
    cmp #$01
    bne StompRet
    ldy $0707
    dey
    cpy #$02
    bcc StompRet
    jsr BarbaPickup
    ; No stomps while a boss fight holds the scroll lock ($0728, cleared by the boss key):
    ; the stomp kills via the generic $E880 death before the enemy update, which skips the
    ; boss-death handler (bank 4 $B1E9) that drops the key -> locked room, softlock.
    lda $0728
    bne StompRet
    lda $0479
    beq StompRet
    lda $057D
    bmi StompRet
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
    ldy $0707
    cpy #$03
    bcc @hp_check
    ; Palaces/Great Palace: shielded enemies ($18-$1A Iron Knuckle / Fokka,
    ; $1F Red Stalfos; $23 Blue Stalfos / Dark Link already skipped above).
    ; Carry is guaranteed set from cpy #$03 falling through.
    sbc #$18
    cmp #$03
    bcc @next
    cmp #$07
    beq @next
    ; $1D: Mago (P1/2/5) / Wizzrobe (P3/4/6) teleport and spend most of their
    ; cycle invisible and intangible; a stomp would kill an unseen enemy. No world
    ; check (bank 0 is full), so Great Palace $1D (Fokkeru) is unstompable too.
    cmp #$05
    beq @next
@hp_check:
    lda $C2,x
    beq @next
    cmp #$11
    bcs @next
    lda $29
    clc
    adc #$22
    bcs @next
    sec
    sbc $2A,x
    cmp #$1E
    bcs @next
    lda #$08
    jsr StompDeltaX
    bcs @next
    cmp #$21
    bcs @next
    ; Invisible bubble and rock generators have no drawing routine. Native
    ; death calls this pointer, so keep these slots active and spawning.
    lda $A1,x
    asl
    tay
    lda $6E65,y
    ora $6E66,y
    beq @next
    stx $10
    lda #$10
    sta $ED
    lda #$00
    sta $C2,x
    lda $0707
    ora $0706
    bne @kill_now
    lda $A1,x
    cmp #$20
    bne @kill_now
    lda #$00
    sta $AF,x
    beq @bounce
@kill_now:
    jsr $E880
@bounce:
    lda #$FC
    sta $057D
    lda #$01
    sta $0479
    rts
@next:
    dex
    bmi @done
    jmp @loop
@done:
    rts

; Input: A = left margin ($08 or $0A), X = enemy slot
; Output: Carry clear & A = dx if high byte == 0, else Carry set
StompDeltaX:
    clc
    adc $4E,x
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
    bne @out
    tya
    clc
    rts
@out:
    sec
    rts
