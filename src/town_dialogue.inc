; Original panic dialogue. Native font supports capitals, spaces and periods.
; Keep lines within the existing dialogue box; $FD newline, $FF end.
.macro TownLine text, terminator
    .assert .strlen(text) <= 12, error, "Town dialogue line is too wide"
    .repeat .strlen(text), character
        .if .strat(text, character) = ' '
            .byte $F4
        .elseif .strat(text, character) = '.'
            .byte $CF
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
TownFearText:
    TownLine "OH SHIT.", $FD
    TownLine "IT IS BARBA.", $FD
    TownLine "RUN.", $FF
TownFearHide:
    TownLine "A DRAGON.", $FD
    TownLine "HIDE IN", $FD
    TownLine "THE HOUSES.", $FF
TownFearLeaving:
    TownLine "FUCK THAT.", $FD
    TownLine "I AM OUT", $FD
    TownLine "OF HERE.", $FF
TownFearPlea:
    TownLine "PLEASE", $FD
    TownLine "DO NOT", $FD
    TownLine "EAT ME.", $FF
