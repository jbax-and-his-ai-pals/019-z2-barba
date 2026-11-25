-- Standalone Wheel of Fortune (NES 2.0 Mapper 176) portal adapter verification.
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local report = assert(io.open(OUTPUT_DIR .. '/wheel_standalone.txt', 'w'))
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
local nmiHookCount = 0
local origNmiCount = 0
local setBankCount = 0
local ppuCtrlCount = 0
local sawNonZeroBank = false
local sawNtB = false
local winHookCount = 0
local restoreHits = 0
local phaseStart = 0
local triggerWin = false
local triggerBoot = false

emu.addMemoryCallback(function()
    if triggerBoot then
        triggerBoot = false
        write(0xA001, 0xA3)
        emu.setState({['cpu.pc'] = 0x7AE0})
    elseif triggerWin and (read(0x7FFD) & 0x03) == 0 then
        triggerWin = false
        emu.setState({['cpu.pc'] = 0xC988})
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

emu.addMemoryCallback(function()
    setBankCount = setBankCount + 1
    local a = emu.getState()['cpu.a']
    if (a & 0x03) ~= 0 then sawNonZeroBank = true end
    if (a & 0x10) ~= 0 then sawNtB = true end
end, emu.callbackType.exec, 0x7800)

emu.addMemoryCallback(function()
    ppuCtrlCount = ppuCtrlCount + 1
end, emu.callbackType.exec, 0x782A)

emu.addMemoryCallback(function()
    nmiHookCount = nmiHookCount + 1
end, emu.callbackType.exec, 0x7850)

emu.addMemoryCallback(function()
    origNmiCount = origNmiCount + 1
end, emu.callbackType.exec, 0x8B3A)

emu.addMemoryCallback(function()
    winHookCount = winHookCount + 1
end, emu.callbackType.exec, 0x78A0)

emu.addMemoryCallback(function()
    restoreHits = restoreHits + 1
end, emu.callbackType.exec, 0x80F0)

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
        if frame == 70 then
            check(nmiHookCount >= 60, 'WHEEL_NMI_HOOK ticked (' .. nmiHookCount .. ')')
            check(origNmiCount >= 60, 'Wheel original NMI ticked (' .. origNmiCount .. ')')
            check(read(0x7FFF) == 0x3C, string.format('Debounce reached $3C (got $%02X)', read(0x7FFF)))
            check(setBankCount >= 1 and sawNonZeroBank, '32KB bankswitch virtualized (count=' .. setBankCount .. ', nonZero=' .. tostring(sawNonZeroBank) .. ')')
            check(sawNtB, '1-screen NT B ($8000 bit 4) virtualized')
            check(ppuCtrlCount >= 1 and (read(0x7FFC) & 0x01) == 0, string.format('$2000 shadowing active (count=%d, $7FFC=$%02X)', ppuCtrlCount, read(0x7FFC)))
            phase = 'start_select'
            phaseStart = frame
        end

    elseif phase == 'start_select' then
        emu.setInput({start = true, select = true}, 0)
        if restoreHits >= 1 then
            check(true, 'Start+Select jumped to WHEEL_RETURN -> $80F0')
            check(read(0x648E) ~= 0x57, string.format('Start+Select did not set reward flag ($648E=$%02X)', read(0x648E)))
            emu.setInput({}, 0)
            nmiHookCount = 0
            origNmiCount = 0
            restoreHits = 0
            winHookCount = 0
            phase = 'win_reset'
            phaseStart = frame
            triggerBoot = true
        elseif frame - phaseStart > 15 then
            check(false, 'Start+Select did not reach $80F0 within 15 frames')
            finish()
        end

    elseif phase == 'win_reset' then
        if frame - phaseStart == 70 then
            check(nmiHookCount >= 60, 'Post-reset NMI ticked (' .. nmiHookCount .. ')')
            -- Trigger Bonus Round Win ($C988) in Bank 0 via exec callback
            triggerWin = true
            phase = 'win_wait'
            phaseStart = frame
        end

    elseif phase == 'win_wait' then
        if restoreHits >= 1 then
            check(winHookCount >= 1, 'WHEEL_WIN_HOOK ($78A0) executed (' .. winHookCount .. ')')
            check(true, 'Bonus Round win jumped to WHEEL_RETURN -> $80F0')
            check(read(0x648E) == 0x57, string.format('Reward flag $648E == $57 in WRAM bank 0 (got $%02X)', read(0x648E)))
            finish()
        elseif frame - phaseStart > 15 then
            check(false, 'Win hook did not reach $80F0 within 15 frames (winHookCount=' .. winHookCount .. ')')
            finish()
        end
    end
end, emu.eventType.endFrame)
