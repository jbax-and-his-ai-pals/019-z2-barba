; Frozen WRAM Bank 0 RetroAchievements Telemetry Block ($6800-$683F, 64 bytes).
; Lives inside the verified unused $6742-$6957 hole (neither vanilla Zelda II
; nor Barba Edition touches any byte here; preserved across reset and subgames).

RA_MAGIC_0       = $6800   ; $42 ('B')
RA_MAGIC_1       = $6801   ; $32 ('2')
RA_VERSION       = $6802   ; $01 (schema v1)
ACTIVE_GAME_ID   = $6803   ; 0=Zelda II, 1=waldo, 2=f13, 3=feud, 4=dk, 5=smb, 6=duck, 7=mm2, 8=wheel, 9=zelda, 10=mtpo
RA_LAST_WIN_GAME = $6804   ; last subgame won (1..10; 0=none/cleared)
RA_SUBGAME_EVENT = $6805   ; subgame milestone / ending event code
RA_DISCOVERY_LO  = $6806   ; Arcade booth discovery bitmask (slots 0..7)
RA_DISCOVERY_HI  = $6807   ; Arcade booth discovery bitmask (slots 8..15)
RA_CLEAR_LO      = $6808   ; Full-clear completion bitmask (slots 0..7)
RA_CLEAR_HI      = $6809   ; Full-clear completion bitmask (slots 8..15)
RA_ALT_END_LO    = $680A   ; Alternate-ending bitmask (slots 0..7)
RA_ALT_END_HI    = $680B   ; Alternate-ending bitmask (slots 8..15)
RA_Z2_FLAGS      = $680C   ; 4 bytes ($680C-$680F) reserved for Z2 campaign telemetry
RA_RESERVED      = $6810   ; 48 bytes ($6810-$683F) strictly reserved for Phase 7 RA

RA_MAGIC_BYTE_0  = $42
RA_MAGIC_BYTE_1  = $32
RA_SCHEMA_VER    = $01

.segment "BANK6_EXTRA"
; Fast VBlank check: if magic != "B2", initialize $6800-$683F. Preserves Y? (Clobbers A/X)
RaTelemetryCheck6:
    lda RA_MAGIC_0
    cmp #RA_MAGIC_BYTE_0
    bne RaTelemetryInit6
    lda RA_MAGIC_1
    cmp #RA_MAGIC_BYTE_1
    bne RaTelemetryInit6
    rts

; Title/boot telemetry initializer: ensures "B2\x01" header and ACTIVE_GAME_ID=0,
; preserving persistent discovery/clear flags if already initialized.
RaTelemetryInit6:
    lda RA_MAGIC_0
    cmp #RA_MAGIC_BYTE_0
    bne @cold_zero
    lda RA_MAGIC_1
    cmp #RA_MAGIC_BYTE_1
    beq @set_z2
@cold_zero:
    ldx #$3C
    lda #$00
@clr:
    sta ACTIVE_GAME_ID,x
    dex
    bpl @clr
    lda #RA_MAGIC_BYTE_0
    sta RA_MAGIC_0
    lda #RA_MAGIC_BYTE_1
    sta RA_MAGIC_1
    lda #RA_SCHEMA_VER
    sta RA_VERSION
    lda #$01
    sta RA_DISCOVERY_LO     ; slot 0 (Where's Barba?) is always open in Barba's Arcade
@set_z2:
    lda #$00
    sta ACTIVE_GAME_ID
    rts
