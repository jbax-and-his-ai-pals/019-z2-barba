; Town-only prototype. This module runs in PRG bank 3, not the bank 0 hooks.
; Install TownUpdate in ONLY routine-0 pointers for native types $19..$1C.
; Every mutation additionally requires a proven generator origin ($BC,x=$FF)
; and an explicit outdoor room. Scripted actors, including walking actors
; with these same type numbers, always tail-call the untouched native routine.
.segment "TOWN"
.export TownUpdate, TownEligible, TownOutdoorRooms, TownEnd, TownDialog, TownFearText, TownFearPointers, TownHide
.export TownFastDialogReady, TownLetterDelay, TownLineDelay, TownAsh
.include "ash_layout.inc"

; Native generator $96E0 clears AF before initializing each new actor.
; We borrow that actor's state only after the positive provenance gate:
;   $00 normal; $80 flee; $A0..$BF ashes; $C0..$DF burning.
; Old prototype door-entry states $01..$7F are immediately hidden on load.
; No extra per-NPC RAM or quest flags. Shared subtitle state is in shouts.inc.

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
    cmp #$A0
    bcc :+
    jmp TownAsh
:
    cmp #$80
    beq @canHit
    cmp #$00
    bne TownDoor
@canHit:
    ; Up talks to a nearby frightened wanderer. B remains the fire attack.
    lda TALK_LATCH
    bne @projectile
    lda $F7
    and #$08
    beq @projectile
    jsr TownCanTalk
    bcc @projectile
    stx $048B
    lda #$01
    sta TALK_LATCH
    lda #$00
    sta $AF,x
    jsr $9A33
    jmp $9A8A
@projectile:
    jsr TownProjectileHit
    bcc @unhit
    jsr TownRequestShout
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
    lda #$10
    bcs @right
    lda #$F0
@right:
    sta $71,x

TownFlee:
    jsr TownRequestShout
    jsr $9A68                  ; original fractional movement and walk cycle
    ; $8B is the native closed-door collision tile. Disappear when reaching
    ; this real doorway, without borrowing the scripted NPC door animation.
    ; Its entry animation assumes a door owner and can alter the wrong house
    ; when used by a generated walker. This path never edits background RAM,
    ; PPU commands, house/quest flags, or native door pointer fields.
    jsr $EA32
    lda $D9
    cmp #$8B
    bne @draw
    jmp TownHide
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
    ; Compatibility with a test state saved during the old door animation.
TownHide:
    lda #$00
    sta $B6,x
    sta $AF,x
    sta $71,x
    ldy $91,x
    lda #$04
    sta $00
@sprite:
    lda #$F8
    sta $0200,y
    tya
    clc
    adc #$04
    tay
    dec $00
    bne @sprite
    rts

TownBurning:
    dec $AF,x
    lda $AF,x
    cmp #$C0
    bne @draw
    lda #$BF
    sta $AF,x
    jmp TownAsh
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

; Charcoal and ember pile remains about two seconds. It is not a living NPC:
; no fleeing, conversations, further damage or background edits occur here.
TownAsh:
    lda $12
    and #$03
    bne @draw
    dec $AF,x
    lda $AF,x
    cmp #$A0
    bne @draw
    jmp TownHide
@draw:
    lda $4E,x
    sec
    sbc $072C
    sta $00
    lda $3C,x
    sbc $072A
    bne @hide
    lda $00
    cmp #$F0
    bcs @hide
    ldy $91,x
    lda #$F8
    sta $0208,y
    sta $020C,y
    lda $2A,x
    clc
    adc #$18
    sta $0200,y
    sta $0204,y
    lda #AshTileLeft
    sta $0201,y
    lda #AshTileRight
    sta $0205,y
    ; Town palette 2 supplies charcoal, glowing embers and pale flecks.
    lda #$02
    sta $0202,y
    sta $0206,y
    lda $00
    sta $0203,y
    clc
    adc #$08
    sta $0207,y
    rts
@hide:
    jmp TownHide

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
    lda $05FF
    cmp #$01
    bne @miss
    ldy #$20
@extra:
    lda $6400,y
    cmp #$01
    bne @extra_next
    lda $6402,y
    sec
    sbc $4E,x
    sta $00
    lda $6403,y
    sbc $3C,x
    sta $01
    lda $00
    clc
    adc #$08
    sta $00
    lda $01
    adc #$00
    bne @extra_next
    lda $00
    cmp #$20
    bcs @extra_next
    lda $6401,y
    sec
    sbc $2A,x
    clc
    adc #$08
    cmp #$28
    bcs @extra_next
    lda #$00
    sta $6400,y
    sec
    rts
@extra_next:
    tya
    sec
    sbc #$10
    tay
    bpl @extra
@miss:
    clc
    rts

; Do not steal Up from a doorway/transition, jumping or an existing dialogue.
; Holding Up while approaching is allowed, so fleeing targets are reachable.
TownCanTalk:
    lda $0736
    cmp #$0B
    bne @no
    lda $074C
    ora $DE
    ora $0726
    ora $0479
    bne @no
    lda $C8
    and #$06
    bne @no
    lda $4E,x
    sec
    sbc $4D
    sta $00
    lda $3C,x
    sbc $3B
    sta $01
    lda $00
    clc
    adc #$30
    sta $00
    lda $01
    adc #$00
    bne @no
    lda $00
    cmp #$61
    bcs @no
    lda $2A,x
    sec
    sbc $29
    clc
    adc #$10
    cmp #$21
    bcs @no
    sec
    rts
@no:
    clc
    rts

TownRequestShout:
    lda SHOUT_READY
    cmp #$01
    bne @done
    lda SHOUT_COOLDOWN
    ora SHOUT_REQUEST
    bne @done
    lda $4E,x
    sec
    sbc $072C
    sta $00
    lda $3C,x
    sbc $072A
    bne @done
    lda $00
    cmp #$F0
    bcs @done
    lda $A1,x
    sec
    sbc #$18
    sta SHOUT_REQUEST
@done:
    rts

TownPlayerNearby:
    ; World-space distance, so actors across a scrolling page boundary work.
    ; Panic radius48 normally,80 during a player attack. Same vertical floor.
    lda $4E,x
    sec
    sbc $4D
    sta $00
    lda $3C,x
    sbc $3B
    sta $01
    ldy #$30
    lda $0400
    beq @radius
    ldy #$50
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
    bcc TownOriginalDialog
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
    lda #$02
    sta $0566
    lda #$00
    sta $0489
    sta $048A
TownFastDialogReady:
    inc $0524
    rts
TownOriginalDialog:
    pla
    asl
    tay
    lda $0707
    jmp $B5FD

; Only generated outdoor wanderers get faster typewriting and line breaks.
TownLetterDelay:
    php
    txa
    pha
    tya
    pha
    ldx $048B
    jsr TownEligible
    lda #$05
    bcc :+
    lda #$01
:
    sta $0566
    pla
    tay
    pla
    tax
    plp
    lda $0566
    rts
TownLineDelay:
    php
    pha
    txa
    pha
    tya
    pha
    ldx $048B
    jsr TownEligible
    bcc @native
    lda #$01
    sta $0566
    jmp @restore
@native:
    pla
    tay
    tya
    pha
    sta $0566
@restore:
    pla
    tay
    pla
    tax
    pla
    plp
    rts
.include "town_dialogue.inc"
TownEnd:
