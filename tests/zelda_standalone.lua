-- Standalone The Legend of Zelda: Barba Edition (NES 2.0 Mapper 176) verification.
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local report = assert(io.open(OUTPUT_DIR .. '/zelda_standalone.txt', 'w'))
local errors = 0
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    report:flush()
    if not cond then errors = errors + 1 end
end

local function saveScreenshot(name)
    local ok, png = pcall(emu.takeScreenshot)
    if ok and png then
        local f = assert(io.open(OUTPUT_DIR .. '/' .. name, 'wb'))
        f:write(png)
        f:close()
    end
end

local done = false
local function finish()
    if done then return end
    done = true
    report:write(errors == 0 and 'RESULT PASS\n' or 'RESULT FAIL\n')
    report:close()
    local stop = emu.exit or emu.stop
    stop(errors == 0 and 0 or 1)
end

local frame = 0
local phase = 'boot'
local phaseStart = 0

local bootCount = 0
local nmiHookCount = 0
local origNmiCount = 0
local prgSwitchCount = 0
local ctrlCount = 0
local seedHookCount = 0
local winHookCount = 0
local returnHookCount = 0
local restoreHits = 0
local sawDmcRoar = false
local sawRngSeedMatch = false

local triggerSeededBoot = false
local triggerWin = false
local inp = {}

local bushCheckHits = 0
local bushHitSamples = {}
emu.addMemoryCallback(function()
    if read(0x7FE8) == 10 then
        bushCheckHits = bushCheckHits + 1
    end
end, emu.callbackType.exec, 0xB46F)

local function handleTriggers()
    if triggerSeededBoot then
        triggerSeededBoot = false
        -- Pollute WRAM $6000-$77FF with stale bytes from another subgame
        write(0xA001, 0x83)
        write(0x6001, 0x5A)
        write(0x652A, 0x12)
        write(0x7000, 0x77)
        -- Write known 8-byte RNG seed to $7FF0-$7FF7 (simulating PortalTramp2)
        for i = 0, 7 do
            write(0x7FF0 + i, 0x11 * (i + 1))
        end
        write(0x7FFF, 0x00)
        write(0x5FF0, 0x21)
        write(0x5FF1, 0x00)
        write(0x5FF2, 0x00)
        write(0x8000, 0x06)
        write(0x8001, 0x00)
        emu.setState({['cpu.pc'] = 0x8000})
    elseif triggerWin then
        -- Map Z1 Bank 2 (R6=6, R7=7) and jump to Princess Zelda rescue ending end ($ABA8)
        triggerWin = false
        write(0x7FE8, 6)
        write(0x7FE9, 7)
        write(0x8000, 0x06)
        write(0x8001, 6)
        write(0x8000, 0x07)
        write(0x8001, 7)
        emu.setState({['cpu.pc'] = 0xABA8})
    end
end

emu.addMemoryCallback(function()
    nmiHookCount = nmiHookCount + 1
    handleTriggers()
end, emu.callbackType.exec, 0xFF58)

emu.addMemoryCallback(function()
    if read(0x7FE8) ~= 0 then return end
    bootCount = bootCount + 1
end, emu.callbackType.exec, 0x8000)

emu.addMemoryCallback(function()
    origNmiCount = origNmiCount + 1
end, emu.callbackType.exec, 0xE484)

emu.addMemoryCallback(function()
    prgSwitchCount = prgSwitchCount + 1
end, emu.callbackType.exec, 0xFFAC)

emu.addMemoryCallback(function()
    ctrlCount = ctrlCount + 1
end, emu.callbackType.exec, 0xFF98)

emu.addMemoryCallback(function()
    if read(0x7FE8) == 12 then
        seedHookCount = seedHookCount + 1
        local match = true
        for i = 0, 7 do
            if read(0x18 + i) ~= 0x11 * (i + 1) then match = false end
        end
        if match then sawRngSeedMatch = true end
    end
end, emu.callbackType.exec, 0xB8C2)

emu.addMemoryCallback(function()
    winHookCount = winHookCount + 1
end, emu.callbackType.exec, 0x7F06)

emu.addMemoryCallback(function()
    returnHookCount = returnHookCount + 1
end, emu.callbackType.exec, 0x7EE8)

emu.addMemoryCallback(function()
    if returnHookCount > 0 then
        restoreHits = restoreHits + 1
    end
    handleTriggers()
end, emu.callbackType.exec, 0xFFE4)

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if done then return end
    frame = frame + 1
    inp = {}

    if phase == 'boot' then
        if frame == 120 then
            check(nmiHookCount >= 60, 'ZELDA_NMI_HOOK ($FF58) ticked (' .. nmiHookCount .. ')')
            check(origNmiCount >= 60, 'Zelda original NMI ($E484) ticked (' .. origNmiCount .. ')')
            check(prgSwitchCount >= 1, 'MMC1 PRG virtualizer ($FFAC) called (' .. prgSwitchCount .. ')')
            check(read(0x7FFF) == 0x3C, string.format('Debounce reached $3C (got $%02X)', read(0x7FFF)))
            saveScreenshot('zelda-title.png')
            -- Now test seeded boot + stale WRAM clear
            phase = 'seeded_boot'
            phaseStart = frame
            triggerSeededBoot = true
        end

    elseif phase == 'seeded_boot' then
        if frame - phaseStart == 45 then
            check(sawRngSeedMatch, string.format('RNG $18-$1F seeded from $7FF0-$7FF7 ($18=$%02X $19=$%02X)', read(0x18), read(0x19)))
            check(read(0x652A) == 0xFF and read(0x7000) ~= 0x77,
                string.format('Stale WRAM $6000-$77FF wiped cleanly ($652A=$%02X, $7000=$%02X)', read(0x652A), read(0x7000)))
            phase = 'to_fileselect'
            phaseStart = frame
        end

    elseif phase == 'to_fileselect' then
        local dt = frame - phaseStart
        -- Press Start on Title screen to enter File Select
        if dt >= 10 and dt < 15 then inp = {start = true} end
        if read(0x12) == 0x01 and dt > 40 then
            saveScreenshot('zelda-fileselect.png')
            phase = 'register_select'
            phaseStart = frame
        elseif dt > 150 then
            check(false, string.format('Did not reach File Select ($12=$%02X, $13=$%02X)', read(0x12), read(0x13)))
            finish()
        end

    elseif phase == 'register_select' then
        local dt = frame - phaseStart
        if dt > 180 then
            check(false, string.format('Could not enter Register Name ($12=$%02X $13=$%02X $16=$%02X)', read(0x12), read(0x13), read(0x16)))
            finish()
        elseif read(0x12) == 0x01 then
            if read(0x16) ~= 0x03 then
                if (dt % 12) == 2 then inp = {select = true} end
            else
                if (dt % 12) == 6 then inp = {start = true} end
            end
        else
            -- Entered Register Your Name (or another mode)
            saveScreenshot('zelda-regname.png')
            phase = 'register_name'
            phaseStart = frame
        end

    elseif phase == 'register_name' then
        local dt = frame - phaseStart
        if dt > 180 then
            saveScreenshot('zelda-regname.png')
            check(false, string.format('Could not exit Register Name ($12=$%02X $13=$%02X $14=$%02X $15=$%02X $16=$%02X)', read(0x12), read(0x13), read(0x14), read(0x15), read(0x16)))
            finish()
        elseif read(0x12) ~= 0x01 then
            if read(0x13) >= 0x04 then
                if dt < 80 then
                    if dt == 65 then inp = {a = true} end
                elseif read(0x16) ~= 0x03 then
                    if (dt % 12) == 2 then inp = {select = true} end
                else
                    if (dt % 12) == 6 then inp = {start = true} end
                end
            end
        else
            phase = 'start_game'
            phaseStart = frame
        end

    elseif phase == 'start_game' then
        local dt = frame - phaseStart
        if read(0x12) == 0x01 and dt >= 30 and (dt % 16) == 2 then
            inp = {start = true}
        end
        if read(0x7FEC) > 0 and (read(0x4015) & 0x10) ~= 0 then
            sawDmcRoar = true
        end
        if read(0x12) == 0x05 and read(0x7FEA) >= 2 and read(0x7FEC) == 0 and dt > 60 then
            check(sawDmcRoar, 'Barba Game Start sampled roar played via DMC ($4015 bit 4)')
            saveScreenshot('zelda-start-hyrule.png')
            phase = 'test_fireball_bush'
            phaseStart = frame
        elseif dt > 420 then
            check(false, string.format('Timed out starting game ($12=$%02X, $13=$%02X, $16=$%02X, done=%d, tmr=%d, roar=%s)',
                read(0x12), read(0x13), read(0x16), read(0x7FEA), read(0x7FEC), tostring(sawDmcRoar)))
            finish()
        end

    elseif phase == 'test_fireball_bush' then
        local dt = frame - phaseStart
        if dt == 1 then
            -- Give Barba Sword ($0657=1) + full hearts so fireball breath fires cleanly
            write(0x0657, 1)
        end
        if read(0xEB) == 0x77 then
            inp = {right = true}
        elseif read(0xEB) == 0x78 and dt < 300 then
            -- Walk to (X=$40, Y=$8D) directly above the secret bush at ($40, $A0), face down ($98==$04), and breathe fire!
            local lx, ly = read(0x70), read(0x84)
            if lx < 0x3E then
                inp = {right = true}
            elseif lx > 0x42 then
                inp = {left = true}
            elseif ly > 0x94 then
                inp = {up = true}
            elseif ly < 0x88 then
                inp = {down = true}
            elseif read(0x98) ~= 0x04 then
                inp = {down = true}
            else
                if (dt % 24) < 4 then inp = {a = true} end
            end
        end
        if read(0xEB) == 0x78 and (read(0xAC + 0x0D) ~= 0 or read(0xAC + 0x0E) ~= 0) then
            if #bushHitSamples < 8 then
                bushHitSamples[#bushHitSamples+1] = string.format('AC:%02X/%02X/%02X@(%02X,%02X)&(%02X,%02X)',
                    read(0xAC+0x0D), read(0xAC+0x0E), read(0xAC+0x0F),
                    read(0x70+0x0D), read(0x84+0x0D), read(0x70+0x0E), read(0x84+0x0E))
            end
            if (dt % 20) == 2 then
                saveScreenshot('zelda-fireball.png')
            end
        end
        -- Check if Screen $78 secret opened (via current Overworld flag pointer $6BAF/$6BB0 + $78 bit 7)
        local secPtr = read(0x6BAF) + read(0x6BB0) * 256
        if read(0xEB) == 0x78 and secPtr >= 0x0600 and secPtr < 0x0800 and (read(secPtr + 0x78) & 0x80) ~= 0 then
            check(true, string.format('Barba firebreath/fireball ignited burnable bush on Screen $78 ($%04X+$78=$%02X)!',
                secPtr, read(secPtr + 0x78)))
            check(ctrlCount >= 1, 'MMC1 Control virtualizer ($FF98) called (' .. ctrlCount .. ')')
            saveScreenshot('zelda-bush-burned.png')
            phase = 'start_select'
            phaseStart = frame
        elseif dt > 340 then
            check(false, string.format('Bush did not ignite on Screen $%02X (X=$%02X Y=$%02X hits=%d ptr=$%04X val=$%02X)',
                read(0xEB), read(0x70), read(0x84), bushCheckHits, secPtr, read(secPtr + 0x78)))
            saveScreenshot('zelda-bush-fail.png')
            finish()
        end

    elseif phase == 'start_select' then
        inp = {start = true, select = true}
        if restoreHits >= 1 then
            check(true, 'Start+Select returned cleanly to $FFE4')
            check(read(0x63B9) ~= 0x5A, string.format('Start+Select did not set reward flag ($63B9=$%02X)', read(0x63B9)))
            returnHookCount = 0
            restoreHits = 0
            winHookCount = 0
            phase = 'win_reset'
            phaseStart = frame
            triggerSeededBoot = true
        elseif frame - phaseStart > 20 then
            check(false, 'Start+Select did not reach $FFE4 within 20 frames')
            finish()
        end

    elseif phase == 'win_reset' then
        if frame - phaseStart == 25 then
            -- Switch to Bank 2 (via Mode $01 File Select or wait until Bank 2 runs in NMI)
            triggerWin = true
            phase = 'win_wait'
            phaseStart = frame
        end

    elseif phase == 'win_wait' then
        if restoreHits >= 1 then
            check(winHookCount >= 1, 'ZELDA_WIN_HOOK ($7F06) executed (' .. winHookCount .. ')')
            check(read(0x63B9) == 0x5A, string.format('Reward flag $63B9 == $5A in WRAM bank 0 (got $%02X)', read(0x63B9)))
            finish()
        elseif frame - phaseStart > 30 then
            check(false, string.format('Win hook did not reach $FFE4 (win=%d ret=%d R6=%d)',
                winHookCount, returnHookCount, read(0x7FE8)))
            finish()
        end
    end
end, emu.eventType.endFrame)
