; Palace Ironknuckle bank shots. Only rebound speeds have a fractional
; component, so backed shots use the existing native-slot movement path.
REBOUND_SPEED_BIT = $08
REBOUND_RIGHT = $38    ; +3.5 pixels per frame
REBOUND_LEFT = $C8     ; -3.5 pixels per frame

.segment "BANK0"
ShieldReboundImpact:
    lda ARCADE_ACTIVE_HI
    and #$02                ; HEAVY spell bypasses shields
    beq @not_heavy
    pla
    pla
    jmp $E6F3
@not_heavy:
    lda $0769
    cmp #$04
    bne @native
    jmp ShieldReboundBank4
@native:
    jmp $E6E8

.segment "PALACE_ROAR"
ShieldRebound4:
    bcc ShieldReboundStep
    lda $A1,x
    cmp #$18
    bcc @clink
    cmp #$1B
    bcs @clink
    lda VOLLEY_SLOT,y
    beq @clink
    and #$40            ; upward breath and METEOR keep the native clang
    bne @clink
    lda $7D,y
    and #REBOUND_SPEED_BIT
    bne @clink          ; one rebound per shot
    jsr $E942           ; enemy body left and width in $04/$06
    ldy $11
    lda $7D,y
    bmi @right
    lda $04
    sec
    sbc #$07            ; leave the whole shot outside the body
    bcc @clink
    pha
    lda #REBOUND_LEFT
    sta $7D,y
    lda #$02
    bne @launch
@right:
    lda $04
    clc
    adc $06
    bcs @clink
    pha
    lda #REBOUND_RIGHT
    sta $7D,y
    lda #$01
@launch:
    sta $6D,y
    pla
    clc
    adc $072C
    sta $5A,y
    lda $072A
    adc #$00
    sta $48,y
    lda #$00
    sta $03E3,y
    lda #(ShieldReboundDyEnd-ShieldReboundDy+1)
    sta VOLLEY_SLOT,y
    jmp @restore_shield
@clink:
    jsr $E6E8
@restore_shield:
    jsr $E5BA           ; restore the shield rectangle for the next slot
    ldy $11
    jmp NativeReturn0

ShieldReboundStep:
    dec VOLLEY_SLOT,x
    beq @expire
    ldy VOLLEY_SLOT,x
    lda ShieldReboundDy-1,y
    clc
    adc $36,x
    cmp #$10
    bcc @expire
    cmp #$E0
    bcs @expire
    sta $36,x
    lda ShieldReboundDy-1,y
    bmi @alive
    ; Probe the flame's center against the palace terrain map.
    lda $5A,x
    clc
    adc #$04
    pha
    lda $48,x
    adc #$00
    and #$03
    tay
    lda $EAE4,y
    sta $0F
    pla
    lsr
    lsr
    lsr
    lsr
    clc
    adc $EAE0,y
    sta $0E
    lda $36,x
    clc
    adc #$05
    and #$F0
    cmp #$D0
    bcs @alive
    tay
    lda ($0E),y
    jsr $850C
    bcs @expire
@alive:
    sec
    jmp NativeReturn0
@expire:
    lda #$00
    sta $8D,x
    sta VOLLEY_SLOT,x
    clc
    jmp NativeReturn0

; Indexed by remaining life, so the shot reads the table from right to left.
ShieldReboundDy:
    .byte 4,4,3,3,3,2,2,1,1,0,0,$FF,$FF,$FE,$FE,$FE,$FD
ShieldReboundDyEnd:
.segment "BANK0"
