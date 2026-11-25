-- Standalone Mega Man 2 (NES 2.0 Mapper 176) portal adapter verification.
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local report = assert(io.open(OUTPUT_DIR .. '/mm2_standalone.txt', 'w'))
local errors = 0
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    if not cond then errors = errors + 1 end
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
local bootCount = 0
local nmiHookCount = 0
local origNmiCount = 0
local prgSwitchCount = 0
local ctrlCount = 0
local chr0Count = 0
local chr1Count = 0
local winHookCount = 0
local returnHookCount = 0
local restoreHits = 0
local phaseStart = 0
local triggerWin = false
local triggerBoot = false

emu.addMemoryCallback(function()
    if triggerBoot then
        triggerBoot = false
        write(0xA001, 0x80)
        write(0x5FF0, 0x21)
        write(0x5FF1, 0x00)
        write(0x5FF2, 0x00)
        emu.setState({['cpu.pc'] = 0xF450})
    elseif triggerWin then
        triggerWin = false
        emu.setState({['cpu.pc'] = 0xC25A})
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

emu.addMemoryCallback(function()
    bootCount = bootCount + 1
end, emu.callbackType.exec, 0xF450)

emu.addMemoryCallback(function()
    prgSwitchCount = prgSwitchCount + 1
end, emu.callbackType.exec, 0xF300)

emu.addMemoryCallback(function()
    ctrlCount = ctrlCount + 1
end, emu.callbackType.exec, 0xC05D)

emu.addMemoryCallback(function()
    chr0Count = chr0Count + 1
end, emu.callbackType.exec, 0xF320)

emu.addMemoryCallback(function()
    chr1Count = chr1Count + 1
end, emu.callbackType.exec, 0xF340)

emu.addMemoryCallback(function()
    nmiHookCount = nmiHookCount + 1
end, emu.callbackType.exec, 0xF380)

emu.addMemoryCallback(function()
    origNmiCount = origNmiCount + 1
end, emu.callbackType.exec, 0xCFF0)

emu.addMemoryCallback(function()
    winHookCount = winHookCount + 1
end, emu.callbackType.exec, 0xF3C0)

emu.addMemoryCallback(function()
    returnHookCount = returnHookCount + 1
end, emu.callbackType.exec, 0xF3E0)

emu.addMemoryCallback(function()
    if returnHookCount > 0 then
        restoreHits = restoreHits + 1
    end
end, emu.callbackType.exec, 0xFFD0)

emu.addEventCallback(function()
    if phase == 'start_select' then
        emu.setInput({start = true, select = true}, 0)
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if done then return end
    frame = frame + 1

    if phase == 'boot' then
        if frame == 80 then
            check(bootCount >= 1, 'MM2_BOOT ($F450) executed (' .. bootCount .. ')')
            check(nmiHookCount >= 60, 'MM2_NMI_HOOK ($F380) ticked (' .. nmiHookCount .. ')')
            check(origNmiCount >= 60, 'MM2 original NMI ($CFF0) ticked (' .. origNmiCount .. ')')
            check(prgSwitchCount >= 1, 'MM2_PRG_SWITCH ($F300) virtualized (' .. prgSwitchCount .. ')')
            check(ctrlCount >= 1, 'MM2_CTRL ($C05D) virtualized (' .. ctrlCount .. ')')
            check(chr0Count >= 1, 'MM2_CHR0 ($F320) virtualized (' .. chr0Count .. ')')
            check(chr1Count >= 1, 'MM2_CHR1 ($F340) virtualized (' .. chr1Count .. ')')
            check(read(0x07FF) == 0x3C, string.format('Debounce reached $3C (got $%02X)', read(0x07FF)))
            phase = 'start_select'
            phaseStart = frame
        end

    elseif phase == 'start_select' then
        emu.setInput({start = true, select = true}, 0)
        if restoreHits >= 1 then
            check(true, 'Start+Select jumped to MM2_RETURN -> $FFD0')
            check(read(0x648F) ~= 0x32, string.format('Start+Select did not set reward flag ($648F=$%02X)', read(0x648F)))
            emu.setInput({}, 0)
            nmiHookCount = 0
            origNmiCount = 0
            returnHookCount = 0
            restoreHits = 0
            winHookCount = 0
            phase = 'win_reset'
            phaseStart = frame
            triggerBoot = true
        elseif frame - phaseStart > 15 then
            check(false, 'Start+Select did not reach $FFD0 within 15 frames')
            finish()
        end

    elseif phase == 'win_reset' then
        if frame - phaseStart == 20 then
            -- Trigger stage clear ($C25A -> MM2_WIN_HOOK) via exec callback
            triggerWin = true
            phase = 'win_wait'
            phaseStart = frame
        end

    elseif phase == 'win_wait' then
        if restoreHits >= 1 then
            check(winHookCount >= 1, 'MM2_WIN_HOOK ($F3C0) executed (' .. winHookCount .. ')')
            check(true, 'Stage clear jumped to MM2_RETURN -> $FFD0')
            check(read(0x648F) == 0x32, string.format('Reward flag $648F == $32 in WRAM bank 0 (got $%02X)', read(0x648F)))
            finish()
        elseif frame - phaseStart > 15 then
            local st = emu.getState()
            check(false, string.format('Win hook did not reach $FFD0 within 15 frames (winHookCount=%d return=%d pc=$%04X)', winHookCount, returnHookCount, st['cpu.pc'] or 0))
            finish()
        end
    end
end, emu.eventType.endFrame)
