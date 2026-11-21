; Original panic dialogue. Font: capitals, space, period, '!', '?' and apostrophe.
; Max 14 chars per line and 4 lines, so a blank tile pads every border; $FD newline, $FF end.
.macro TownLine text, terminator
    .assert .strlen(text) <= 14, error, "Town dialogue line is too wide"
    .repeat .strlen(text), character
        .if .strat(text, character) = ' '
            .byte $F4
        .elseif .strat(text, character) = '.'
            .byte $CF
        .elseif .strat(text, character) = '!'
            .byte $36
        .elseif .strat(text, character) = $3F   ; '?' (vanilla font, bank-7 tile $34)
            .byte $34
        .elseif .strat(text, character) = $27   ; apostrophe (TEXT_GLYPHS, bank-7 tile $35)
            .byte $35
        .elseif .strat(text, character) >= 'A' .and .strat(text, character) <= 'Z'
            .byte .strat(text, character) - 'A' + $DA
        .else
            .error "Unsupported town dialogue character"
        .endif
    .endrepeat
    .byte terminator
.endmacro

TownFearPointers:
    .word TownFearText, TownFearHide, TownFearLeaving, TownFearPlea
    .word TownFearBarbaAlert, TownFearBarbaLoose, TownFearBarbaSight, TownFearBarbaBurn
TownFearText:
    TownLine "OH SHIT!", $FD
    TownLine "BARBA'S", $FD
    TownLine "HERE! RUN!", $FF
TownFearHide:
    TownLine "A DRAGON!", $FD
    TownLine "HIDE IN", $FD
    TownLine "A HOUSE!", $FF
TownFearLeaving:
    TownLine "FUCK THAT!", $FD
    TownLine "I'M OUT", $FD
    TownLine "OF HERE!", $FF
TownFearPlea:
    TownLine "PLEASE", $FD
    TownLine "DON'T", $FD
    TownLine "EAT ME!", $FF
TownFearBarbaAlert:
    TownLine "IT'S BARBA", $FD
    TownLine "EVERYONE", $FD
    TownLine "GO INSIDE!", $FF
TownFearBarbaLoose:
    TownLine "BARBA IS", $FD
    TownLine "IN TOWN!", $FD
    TownLine "HELP!", $FF
TownFearBarbaSight:
    TownLine "NO WAY!", $FD
    TownLine "THAT'S", $FD
    TownLine "BARBA!", $FF
TownFearBarbaBurn:
    TownLine "BARBA WILL", $FD
    TownLine "BURN US!", $FD
    TownLine "RUN AWAY!", $FF
TownWiseManText:
    TownLine "TAKE THIS", $FD
    TownLine "MAGIC AND", $FD
    TownLine "SPARE ME!", $FF
TownHealerText:
    TownLine "OH NO!", $FD
    TownLine "I CAN HEAL", $FD
    TownLine "YOU BARBA!", $FF
TownMagicText:
    TownLine "TAKE MY", $FD
    TownLine "MAGIC! GO", $FD
    TownLine "IN PEACE!", $FF
