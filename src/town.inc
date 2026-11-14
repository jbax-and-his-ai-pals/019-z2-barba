; Town-only prototype. This module runs in PRG bank 3, not the bank 0 hooks.
; Install TownUpdate in ONLY routine-0 pointers for native types $19..$1C.
; Every mutation additionally requires a proven generator origin ($BC,x=$FF)
; and an explicit outdoor room. Scripted actors, including walking actors
; with these same type numbers, always tail-call the untouched native routine.
.segment "TOWN"
.export TownUpdate, TownEligible, TownOutdoorRooms, TownEnd, TownDialog, TownFearText, TownFearPointers

; Native generator $96E0 clears AF before initializing each new actor.
; We borrow that actor's state only after the positive provenance gate:
;   $00 normal; $01..$41 native door entry; $80 flee; $C0..$DF burning.
; No extra RAM, persistent quest flags, NPC types, or conversation pointers.

TownUpdate:
    jsr TownEligible
    bcs @eligible
@native:
    jmp $9878
@eligible:
    ; Let an already-started conversation finish using its original stack
    ; convention ($9A9B intentionally discards one native call frame).
    lda $05C3,x
    bne @native
    lda $AF,x
    cmp #$C0
    bcc :+
    jmp TownBurning
:
    cmp #$80
    beq @canHit
    cmp #$00
    bne TownDoor
@canHit:
    ; Up talks to a nearby frightened wanderer. B remains the fire attack.
    lda $F5
    and #$08
    beq @projectile
    jsr TownPlayerNearby
    bcc @projectile
    stx $048B
    lda #$00
    sta $AF,x
    jsr $9A33
    jmp $9A8A
@projectile:
    jsr TownProjectileHit
    bcc @unhit
    lda #$DF
    sta $AF,x
    lda #$00
    sta $71,x
    jmp TownBurning
@unhit:
    lda $AF,x
    bmi TownFlee
    jsr TownPlayerNearby
    bcc @native
    lda #$80
    sta $AF,x
    ; Pick one escape direction on panic. Do not oscillate when the player
    ; crosses the NPC. Native velocities use four fractional bits.
    lda $4E,x
    sec
    sbc $4D
    lda $3C,x
    sbc $3B
    lda #$20
    bcs @right
    lda #$E0
@right:
    sta $71,x

TownFlee:
    jsr $9A68                  ; original fractional movement and walk cycle
    ; Native townsfolk recognize a real closed doorway by collision tile $8B.
    ; Only enter a door actually under this actor; never manufacture a door
    ; pointer or edit a house/quest flag. No door in the escape path: run away.
    jsr $EA32
    lda $D9
    cmp #$8B
    bne @draw
    lda #$01
    sta $AF,x
    jsr $98A1                  ; native save collision pointer + door position
    jmp $9A8A
@draw:
    ; AF=$80 is custom; native drawing hides AF >= $40. Temporarily render
    ; the normal walking pose, then restore the fleeing state.
    lda #$00
    sta $AF,x
    jsr $9A8A                  ; native clipping, native OAM, native countdown
    ldx $10
    lda #$80
    sta $AF,x
    rts

TownDoor:
    ; The native door sequence opens, walks into the house, then closes.
    ; Finish at $41, immediately after the native $40 collision-door write.
    ; Do not let its later $70 phase reopen the house and bring the NPC back.
    jsr $9A8A
    ldx $10
    lda $AF,x
    jsr $98BC
    ldx $10
    lda $AF,x
    cmp #$41
    bne @done
    lda #$00
    sta $B6,x
@done:
    rts

TownBurning:
    dec $AF,x
    lda $AF,x
    cmp #$C0
    bne @draw
    lda #$00
    sta $B6,x
    rts
@draw:
    ; Reuse the NPC's original four 8x16 sprite slots, not extra OAM. Native
    ; drawing provides screen clipping and positions. Replace only tile and
    ; palette fields with the same flame tile used by the player's fireballs.
    lda $AF,x
    pha
    lda #$00
    sta $AF,x
    jsr $9A8A
    ldx $10
    pla
    sta $AF,x
    and #$08
    asl
    asl
    asl
    ora #$01
    sta $01
    ldy $91,x
    lda #$04
    sta $00
@flame:
    lda #$84
    sta $0201,y
    lda $01
    sta $0202,y
    tya
    clc
    adc #$04
    tay
    dec $00
    bne @flame
    rts

; Carry set iff this is a live, positively identified random outdoor walker.
; X is always preserved. The room table is audited from the verified source
; headers AND the presence of native generator type $23 in each enemy list.
TownEligible:
    lda $B6,x
    cmp #$01
    bne @no
    lda $BC,x
    cmp #$FF
    bne @no
    lda $A1,x
    cmp #$19
    bcc @no
    cmp #$1D
    bcs @no
    lda $0707
    cmp #$01
    beq @town
    cmp #$02
    bne @no
@town:
    ldy $0561
    cpy #$14
    bcs @no
    lda TownOutdoorRooms,y
    beq @no
    sec
    rts
@no:
    clc
    rts

TownOutdoorRooms:
    .byte 1,1,1,1,1,1,0,1,1,1,1,1,1,1,1,1,1,1,1,1

; Carry set when a native live player projectile overlaps this actor's body.
; Both slots and both page bytes are tested. Native projectile class (including
; Fire spell versus normal breath) does not change collision eligibility.
; Plumes, melee flags, spells, screen proximity, and enemy shots cannot burn.
TownProjectileHit:
    ldy #$01
@slot:
    lda $008D,y
    cmp #$01
    bne @next
    lda $005A,y
    sec
    sbc $4E,x
    sta $00
    lda $0048,y
    sbc $3C,x
    sta $01
    lda $00
    clc
    adc #$08
    sta $00
    lda $01
    adc #$00
    bne @next
    lda $00
    cmp #$20                  ; projectile width8 + NPC width24
    bcs @next
    lda $0036,y
    sec
    sbc $2A,x
    clc
    adc #$08
    cmp #$28                  ; projectile height8 + NPC height32
    bcs @next
    lda #$00
    sta $008D,y               ; consume this one player projectile
    sec
    rts
@next:
    dey
    bpl @slot
    clc
    rts

TownPlayerNearby:
    ; World-space distance, so actors across a scrolling page boundary work.
    ; Panic radius64 normally,112 during a player attack. Same vertical floor.
    lda $4E,x
    sec
    sbc $4D
    sta $00
    lda $3C,x
    sbc $3B
    sta $01
    ldy #$40
    lda $0400
    beq @radius
    ldy #$70
@radius:
    tya
    clc
    adc $00
    sta $00
    lda $01
    adc #$00
    bne @far
    tya
    asl
    cmp $00
    bcc @far
    lda $2A,x
    sec
    sbc $29
    clc
    adc #$30
    cmp #$60
    bcs @far
    sec
    rts
@far:
    clc
    rts
; The native dialogue index is in A. Only generated outdoor wanderers get a
; new pointer; all important/indoor actors resume the original selection code.
TownDialog:
    pha
    ldx $048B
    jsr TownEligible
    bcc @original
    pla
    lda $A1,x
    sec
    sbc #$19
    asl
    tay
    lda TownFearPointers,y
    sta $0569
    lda TownFearPointers+1,y
    sta $056A
    jmp $B614
@original:
    pla
    asl
    tay
    lda $0707
    jmp $B5FD
.include "town_dialogue.inc"
TownEnd:
