; Bank-8 town/sign/Error dialogue strings copied into ARCADE_DLG_BUF ($63C0-$63FF).
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

.segment "PORTAL_BANK"
CopyTownDlg8:
    pla
    asl
    tax
    lda TownDlgPtr8,x
    pha
    lda TownDlgPtr8+1,x
    tay
    pla
    jsr CopyDlgBuf8
    lda #$03
    jmp $FFCC

TownDlgPtr8:
    .word TownFearText, TownFearHide, TownFearLeaving, TownFearPlea
    .word TownFearBarbaAlert, TownFearBarbaLoose, TownFearBarbaSight, TownFearBarbaBurn
    .word TownWiseManText, TownHealerText, TownMagicText
    .word SignChar, SignBurned, SignAshPile, SignWhatLeft, SignDidThat, SignWasSign
    .word ErrorAshText

TownFearText:
    TownLine "OH SHIT!", $FD
    TownLine "BARBA'S IN", $FD
    TownLine "TOWN! RUN", $FD
    TownLine "FOR YOUR LIFE!", $FF
TownFearHide:
    TownLine "A REAL DRAGON!", $FD
    TownLine "QUICK! GET", $FD
    TownLine "INSIDE A", $FD
    TownLine "HOUSE NOW!", $FF
TownFearLeaving:
    TownLine "FUCK THAT!", $FD
    TownLine "I'M GETTING", $FD
    TownLine "OUT OF HERE!", $FF
TownFearPlea:
    TownLine "PLEASE DON'T", $FD
    TownLine "EAT ME! I", $FD
    TownLine "TASTE TERRIBLE", $FF
TownFearBarbaAlert:
    TownLine "IT'S BARBA!", $FD
    TownLine "LOCK YOUR", $FD
    TownLine "DOORS AND", $FD
    TownLine "GET INSIDE!", $FF
TownFearBarbaLoose:
    TownLine "BARBA IS LOOSE", $FD
    TownLine "IN THE TOWN!", $FD
    TownLine "SOMEBODY HELP!", $FF
TownFearBarbaSight:
    TownLine "NO WAY! IS", $FD
    TownLine "THAT REALLY", $FD
    TownLine "BARBA?!", $FF
TownFearBarbaBurn:
    TownLine "BARBA WILL", $FD
    TownLine "BURN THE WHOLE", $FD
    TownLine "TOWN DOWN!", $FD
    TownLine "RUN AWAY!", $FF
TownWiseManText:
    TownLine "TAKE THIS", $FD
    TownLine "MAGIC SPELL", $FD
    TownLine "AND SPARE", $FD
    TownLine "MY LIFE!", $FF
TownHealerText:
    TownLine "OH NO! DON'T", $FD
    TownLine "BURN ME! I CAN", $FD
    TownLine "HEAL YOUR", $FD
    TownLine "WOUNDS BARBA!", $FF
TownMagicText:
    TownLine "FILL YOUR", $FD
    TownLine "MAGIC BAR!", $FD
    TownLine "NOW PLEASE GO", $FD
    TownLine "IN PEACE!", $FF
SignChar:
    TownLine "COMPLETELY", $FD
    TownLine "CHARRED. YOU", $FD
    TownLine "CAN'T READ", $FD
    TownLine "A SINGLE WORD.", $FF
SignBurned:
    TownLine "WELL... YOU", $FD
    TownLine "BURNED THE", $FD
    TownLine "SIGN TO ASH.", $FF
SignAshPile:
    TownLine "WELCOME TO", $FD
    TownLine "THIS SMOKING", $FD
    TownLine "PILE OF ASH.", $FF
SignWhatLeft:
    TownLine "WELCOME TO", $FD
    TownLine "WHATEVER IS", $FD
    TownLine "LEFT OF IT.", $FF
SignDidThat:
    TownLine "THE SIGN IS", $FD
    TownLine "ASH NOW.", $FD
    TownLine "YOU DID THAT.", $FF
SignWasSign:
    TownLine "THIS USED TO", $FD
    TownLine "BE A SIGN.", $FD
    TownLine "THANKS BARBA.", $FF
ErrorAshText:
    TownLine "I AM", $FD
    TownLine "ERROR'S", $FD
    TownLine "ASH PILE.", $FF

.segment "TOWN"
