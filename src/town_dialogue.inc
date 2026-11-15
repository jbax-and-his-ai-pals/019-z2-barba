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
    .word TownFearBarbaAlert, TownFearBarbaLoose, TownFearBarbaSight, TownFearBarbaBurn
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
TownFearBarbaAlert:
    TownLine "IT IS BARBA.", $FD
    TownLine "EVERYONE", $FD
    TownLine "GET INSIDE.", $FF
TownFearBarbaLoose:
    TownLine "BARBA IS", $FD
    TownLine "LOOSE IN", $FD
    TownLine "TOWN. HELP.", $FF
TownFearBarbaSight:
    TownLine "NO WAY.", $FD
    TownLine "THAT IS", $FD
    TownLine "BARBA.", $FF
TownFearBarbaBurn:
    TownLine "BARBA WILL", $FD
    TownLine "BURN US ALL.", $FD
    TownLine "RUN AWAY.", $FF
TownWiseManText:
    TownLine "TAKE THIS", $FD
    TownLine "MAGIC AND", $FD
    TownLine "SPARE ME.", $FF
TownHealerText:
    TownLine "OH NO BARBA.", $FD
    TownLine "LET ME HEAL", $FD
    TownLine "YOUR SCALES.", $FF
TownMagicText:
    TownLine "TAKE MY", $FD
    TownLine "MAGIC BARBA.", $FD
    TownLine "GO IN PEACE.", $FF
