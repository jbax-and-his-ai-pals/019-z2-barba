; Town-only prototype. This module runs in PRG bank 3, not the bank 0 hooks.
; Install TownUpdate in routine-0 pointers for villager/NPC types $09..$0A and $0D..$20.
; Every mutation requires an explicit outdoor room in world 1 or 2. Invisible triggers
; ($0C, $21..$23) and $0B always keep their native routines.
.segment "TOWN"
.export TownUpdate, TownEligible, TownBurnable, TownOutdoorRooms, TownEnd, TownDialog, TownFearText, TownFearPointers, TownHide
.export TownFastDialogReady, TownLetterDelay, TownLineDelay, TownAsh, TownDoorCoords, TownDoorEmerged, TownNativeTalk
.include "ash_layout.inc"

; Native generator $96E0 clears AF before initializing each new actor.
; We borrow that actor's state only after the positive provenance gate:
;   $00 normal; $01..$40 door entry; $80 flee; $A0..$BF ashes; $C0..$DF burning.
; No extra per-NPC RAM or quest flags. Shared subtitle state is in shouts.inc.

TownUpdate:
    jsr TownEligible
    bcc :+
    jmp @eligible
:
    lda $05C3,x
    bne @native
    lda $A1,x
    cmp #$13
    bcc @check_burnable
    cmp #$19
    bcs @check_burnable
    ; House-openers ($13..$18) outside on the street (AF == 0) talk on B
    ; (like vanilla) or held/pressed Up via TownCanTalk.
    ; Healer/Magic ($17..$18) inside doorway (AF $40..$7F) intercept mode $16
    ; to trigger native $99E6 heal/magic restore without stale $C9 blocking it.
    lda $AF,x
    beq @opener_outside
    bmi @native
    cmp #$40
    bcc @native
    lda $A1,x
    cmp #$17
    bcc @native
    lda $0736
    cmp #$16
    bne @native
    lda $4E,x
    sec
    sbc $4D
    clc
    adc #$20
    cmp #$40
    bcs @native
    stx $048B
    lda $A1,x
    jmp $99E6
@opener_outside:
    lda $F5
    and #$40
    bne @opener_talk
    lda TALK_LATCH
    bne @native
    lda $F7
    and #$08
    beq @native
@opener_talk:
    jsr TownCanTalk
    bcc @native
    stx $048B
    lda #$01
    sta TALK_LATCH
    jsr $9A33
    jmp $9A8A
@check_burnable:
    jsr TownBurnable
    bcc @native
    lda $AF,x
    cmp #$C0
    bcc :+
    jmp TownBurning
:
    cmp #$A0
    bcc :+
    jmp TownAsh
:
    jsr TownProjectileHit
    bcs @ignite
@native:
    lda $A1,x
    cmp #$09
    beq @native_19_20
    cmp #$0F
    beq @native_0F
    cmp #$13
    bcc @native_10_12
    cmp #$19
    bcc @native_13_18
@native_19_20:
    jmp $9878
@native_0F:
    jmp $97A9
@native_10_12:
    jmp $9793
@native_13_18:
    jmp $97D4
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
    beq @canHit
    jmp TownDoor
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
@ignite:
    lda COMBO_ADD
    clc
    adc #$03
    bcc :+
    lda #$FF
:
    sta COMBO_ADD
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
    bcs :+
    jmp @native
:
    lda #$80
    sta $AF,x
    jsr TownPickEscapeDir

TownFlee:
    lda $2A,x
    cmp #$B0
    bcs @on_ground
    lda $12
    and #$0F
    bne @on_ground
    lda $2A,x
    clc
    adc #$04
    sta $2A,x
@on_ground:
    lda $71,x
    beq :+
    jsr TownPickEscapeDir
:
    jsr TownRequestShout
    jsr $9A68                  ; original fractional movement and walk cycle
    ; Despawn once the villager retreated >=16 px past the left edge or past the right edge.
    lda $69C4
    sec
    sbc #$01
    cmp $3C,x
    beq @check_left_px
    lda $3C,x
    cmp $69C4
    bcc @edge_despawn
    cmp $69C7
    beq @in_bounds
    bcs @edge_despawn
    bcc @in_bounds
@check_left_px:
    lda $4E,x
    cmp #$F0
    bcc @edge_despawn
@in_bounds:
    ; $8B is the native closed-door collision tile. When reaching a real doorway,
    ; open its PPU tiles, walk the villager inside, then close the door behind
    ; them without altering collision RAM ($6000..$633F) or house/quest flags.
    jsr $EA32
    lda $D9
    cmp #$91
    beq @edge_despawn
    cmp #$8B
    bne @draw
    jsr TownDoorStart
    bcs @draw_door
@edge_despawn:
    jmp TownHide
@draw_door:
    jsr $9A8A
    ldx $10
    rts
@draw:
    ; AF=$80/$82 is custom; native drawing hides AF >= $40. Temporarily render
    ; the normal walking pose, then restore the fleeing state.
    lda $AF,x
    pha
    lda #$00
    sta $AF,x
    jsr $9A8A                  ; native clipping, native OAM, native countdown
    ldx $10
    pla
    sta $AF,x
    rts

; Always flee away from Barba ($0E right or $F2 left). On either side there
; is always a doorway ($8B) or room edge ($69C4/$69C7) to escape into.
TownPickEscapeDir:
    lda $4E,x
    sec
    sbc $4D
    lda $3C,x
    sbc $3B
    bvc :+
    eor #$80
:
    bmi @go_left
    lda #$0E
    .byte $2C
@go_left:
    lda #$F2
    sta $71,x
    rts

; Derive the exact door column and page from LEA32's collision pointer ($DC/$DD)
; so the PPU door macro always targets the real doorway, even across page seams.
TownDoorCoords:
    lda $DD
    sec
    sbc #$60
    bcc @bad
    cmp #$04
    bcs @bad
    sta $01
    lda $DC
    ldy #$00
@page_loop:
    cmp #$D0
    bcs @sub_page
    ldx $01
    beq @page_done
@sub_page:
    sec
    sbc #$D0
    bcs :+
    dec $01
:
    iny
    cpy #$04
    bcc @page_loop
@bad:
    ldx $10
    clc
    rts
@page_done:
    and #$0F
    asl
    asl
    asl
    asl
    ldx $10
TownDoorStore:
    sta $0599,x
    tya
    sta $059F,x
    sec
    rts

; House-openers emerging from inside a house (L97F5, AF=$81) had $4E,x offset
; by L9740,y before LEA32, so LEA32 can probe an adjacent column; recover their
; real doorway directly from ($4E,x - L9740,y) and $3C,x.
TownDoorEmerged:
    ldy $60,x
    lda $4E,x
    sec
    sbc $9740,y
    and #$F0
    ldy $3C,x
    jmp TownDoorStore

TownDoorStart:
    jsr TownDoorCoords
    bcs :+
    rts
:
    lda #$41
    sta $AF,x
    lda $71,x
    bmi @left
    lda #$08
    .byte $2C                  ; BIT abs, skips next 2 bytes
@left:
    lda #$F8
    sta $71,x
    sec
    rts

; Check whether the doorway at ($0599,x / $059F,x) is within the active nametable
; window ([-16, +256) from $072C/$072A) so scrolling never corrupts a wrapped page.
TownDoorOnScreen:
    lda $0599,x
    sec
    sbc $072C
    sta $00
    lda $059F,x
    sbc $072A
    beq @yes
    cmp #$FF
    bne @no
    lda $00
    cmp #$F0
    bcc @no
@yes:
    sec
    rts
@no:
    clc
    rts

; Queue a native door macro ($9946 half, $994A open, $994E closed).
; A = 0 ($9946), 1 ($994A), or 2 ($994E).
; Returns C=1 if the step should advance (queued or offscreen), C=0 if PPU buffer is busy.
TownDoorQueuePpu:
    pha
    jsr TownDoorOnScreen
    bcc @skip
    lda $0301
    cmp #$0F
    bcs @busy
    pla
    beq @half
    cmp #$01
    beq @open
    jsr $994E
    sec
    rts
@half:
    jsr $9946
    sec
    rts
@open:
    jsr $994A
    sec
    rts
@skip:
    pla
    sec
    rts
@busy:
    pla
    clc
    rts

TownDoor:
    lda $0736
    cmp #$0B
    beq :+
    jmp TownHide
:
    lda $074C
    ora $DE
    ora $0726
    bne @pause
    lda $AF,x
    cmp #$44
    beq @half_open
    cmp #$48
    beq @full_open
    cmp #$74
    beq @half_open
    cmp #$7C
    beq @full_close
    cmp #$68
    beq @enter_house
    bcc @outside
    ; $69..$73 or $75..$7B: inside house, waiting for door to close.
    inc $AF,x
@pause:
    rts
@outside:
    cmp #$48
    bcc @draw
    jsr $9A68
    lda $AF,x
    cmp #$54
    beq @step_up
    cmp #$64
    bne @draw
@step_up:
    lda $2A,x
    sec
    sbc #$04
    sta $2A,x
@draw:
    inc $AF,x
    jsr $9A8A
    ldx $10
    rts
@enter_house:
    inc $AF,x
    jmp TownHideOAM
@half_open:
    lda #$00
    beq @queue_and_advance
@full_open:
    lda #$01
@queue_and_advance:
    jsr TownDoorQueuePpu
    bcc @pause
    lda $AF,x
    cmp #$10
    bcc @draw
    inc $AF,x
    rts
@full_close:
    lda #$02
    jsr TownDoorQueuePpu
    bcc @pause
    jmp TownHide

TownHide:
    jsr $DD3D
    sta $AF,x
    sta $71,x
TownHideOAM:
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

; Carry set iff this is a live outdoor villager ($10..$12 or $19..$20 in world 1/2 outdoor room).
; Story-necessary NPCs ($0B..$0F, $13..$18 house-openers, $21..$24) and indoor actors are excluded.
TownEligible:
    lda $B6,x
    cmp #$01
    bne @no
    lda $A1,x
    cmp #$10
    bcc @no
    cmp #$13
    bcc @elig_world
    cmp #$19
    bcc @no
@elig_world:
    cmp #$21
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

; Carry set iff this is a live burnable person in world 1/2 (including
; single-area non-town places and indoor rooms, excluding North Palace $3C,
; house-openers $13..$18, and invisible triggers $0C/$21-$23).
TownBurnable:
    lda $B6,x
    cmp #$01
    bne @burn_no
    lda $0707
    cmp #$01
    beq @burn_world_ok
    cmp #$02
    bne @burn_no
@burn_world_ok:
    lda $0561
    cmp #$3C
    beq @burn_no
    lda $A1,x
    cmp #$0A
    bcc @burn_no
    cmp #$0C
    beq @burn_no
    cmp #$13
    bcc :+
    cmp #$19
    bcc @burn_no
:
    cmp #$21
    bcs @burn_no
    sec
    rts
@burn_no:
    clc
    rts

; Native $9A2C check: press B (like vanilla) or Up (outside open doorways)
; to talk to native NPCs/triggers ($0D..$18, $21 Mirror/Fountain, $22 signs, etc.).
TownNativeTalk:
    lda $F5
    and #$40
    bne @yes_talk
    lda $C8
    and #$06
    bne @no_talk
    lda $F5
    and #$08
    rts
@yes_talk:
    lda #$40
    rts
@no_talk:
    lda #$00
    rts

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
    and #$07
    clc
    adc SHOUT_CYCLE
    cmp #$09
    bcc :+
    sbc #$09
:
    clc
    adc #$01
    sta SHOUT_REQUEST
    ; The same villager also carries a short sprite word (shouts.inc).
    sta SHOUT_WORD
    inc SHOUT_CYCLE
    lda SHOUT_CYCLE
    cmp #$09
    bcc :+
    lda #$00
    sta SHOUT_CYCLE
:
    stx SHOUT_SLOT
    lda #SHOUT_WORD_TIME
    sta SHOUT_WORD_TIMER
@done:
    rts

TownPlayerNearby:
    ; World-space distance, so actors across a scrolling page boundary work.
    ; Panic radius 72 normally, 96 during a player attack. Same vertical floor.
    lda $4E,x
    sec
    sbc $4D
    sta $00
    lda $3C,x
    sbc $3B
    sta $01
    ldy #$48
    lda $0400
    beq @radius
    ldy #$60
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
    lda $12
    eor $A1,x
    and #$07
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
    ldy $A1,x
    cpy #$0F
    bne @check_healer
    ldy $05
    beq @native_dialog
    lda #<TownWiseManText
    ldy #>TownWiseManText
    jmp @set_npc_dialog
@check_healer:
    cpy #$17
    bne @check_magic
    lda #<TownHealerText
    ldy #>TownHealerText
    jmp @set_npc_dialog
@check_magic:
    cpy #$18
    bne @native_dialog
    lda #<TownMagicText
    ldy #>TownMagicText
@set_npc_dialog:
    sta $0569
    sty $056A
    lda #$2A
    sta $0566
    lda #$00
    sta $0489
    sta $048A
    jmp TownFastDialogReady
@native_dialog:
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
