-- Standalone Donkey Kong (NES 2.0 Mapper 176) portal adapter verification.
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local report = assert(io.open(OUTPUT_DIR .. '/dk_standalone.txt', 'w'))
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
local winHookCount = 0
local restoreHits = 0
local phaseStart = 0

emu.addMemoryCallback(function()
    nmiHookCount = nmiHookCount + 1
end, emu.callbackType.exec, 0x7840)

emu.addMemoryCallback(function()
    origNmiCount = origNmiCount + 1
end, emu.callbackType.exec, 0xC85F)

emu.addMemoryCallback(function()
    winHookCount = winHookCount + 1
end, emu.callbackType.exec, 0x7870)

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
            check(nmiHookCount >= 60, 'DK_NMI_HOOK ticked (' .. nmiHookCount .. ')')
            check(origNmiCount >= 60, 'DK original NMI ticked (' .. origNmiCount .. ')')
            check(read(0x7FFF) == 0x3C, string.format('Debounce reached $3C (got $%02X)', read(0x7FFF)))
            check(read(0x004E) == 0x01, string.format('Title/attract mode active ($4E=$%02X)', read(0x004E)))
            phase = 'start_select'
            phaseStart = frame
        end

    elseif phase == 'start_select' then
        emu.setInput({start = true, select = true}, 0)
        if restoreHits >= 1 then
            check(true, 'Start+Select jumped to DK_RETURN -> $80F0')
            check(read(0x648F) ~= 0x44, string.format('Start+Select did not set reward flag ($648F=$%02X)', read(0x648F)))
            emu.setInput({}, 0)
            nmiHookCount = 0
            origNmiCount = 0
            restoreHits = 0
            winHookCount = 0
            phase = 'win_reset'
            phaseStart = frame
            write(0xA001, 0xA3)
            emu.setState({['cpu.pc'] = 0x7AE0})
        elseif frame - phaseStart > 15 then
            check(false, 'Start+Select did not reach $80F0 within 15 frames')
            finish()
        end

    elseif phase == 'win_reset' then
        if frame - phaseStart == 70 then
            check(nmiHookCount >= 60, 'Post-reset NMI ticked (' .. nmiHookCount .. ')')
            -- Trigger 100m Pauline rescue cutscene completion ($C8B3)
            write(0x004E, 0x00)
            write(0x004F, 0x01)
            write(0x009A, 0x01)
            write(0x044F, 0x08)
            write(0x0450, 0x01)
            write(0x0043, 0x00)
            phase = 'win_wait'
            phaseStart = frame
        end

    elseif phase == 'win_wait' then
        if restoreHits >= 1 then
            check(winHookCount >= 1, 'DK_WIN_HOOK ($7870) executed (' .. winHookCount .. ')')
            check(true, '100m win jumped to DK_RETURN -> $80F0')
            check(read(0x648F) == 0x44, string.format('Reward flag $648F == $44 in WRAM bank 0 (got $%02X)', read(0x648F)))
            finish()
        elseif frame - phaseStart > 15 then
            check(false, 'Win hook did not reach $80F0 within 15 frames (winHookCount=' .. winHookCount .. ')')
            finish()
        end
    end
end, emu.eventType.endFrame)
