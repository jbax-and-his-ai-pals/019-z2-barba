-- Standalone Duck Hunt (NES 2.0 Mapper 176) portal adapter verification.
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local report = assert(io.open(OUTPUT_DIR .. '/duck_standalone.txt', 'w'))
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
local triggerWin = false

emu.addMemoryCallback(function()
    if triggerWin then
        triggerWin = false
        emu.setState({['cpu.pc'] = 0xD39B})
    end
end, emu.callbackType.exec, 0xC000, 0xFFFF)

emu.addMemoryCallback(function()
    nmiHookCount = nmiHookCount + 1
end, emu.callbackType.exec, 0x7840)

emu.addMemoryCallback(function()
    origNmiCount = origNmiCount + 1
end, emu.callbackType.exec, 0xC086)

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
            check(nmiHookCount >= 60, 'DUCK_NMI_HOOK ticked (' .. nmiHookCount .. ')')
            check(origNmiCount >= 60, 'Duck Hunt original NMI ticked (' .. origNmiCount .. ')')
            check(read(0x7FFF) == 0x3C, string.format('Debounce reached $3C (got $%02X)', read(0x7FFF)))
            check(read(0x0024) == 0x01, string.format('Title/attract mode active ($24=$%02X)', read(0x0024)))
            phase = 'start_select'
            phaseStart = frame
        end

    elseif phase == 'start_select' then
        emu.setInput({start = true, select = true}, 0)
        if restoreHits >= 1 then
            check(true, 'Start+Select jumped to DUCK_RETURN -> $80F0')
            check(read(0x648F) ~= 0x48, string.format('Start+Select did not set reward flag ($648F=$%02X)', read(0x648F)))
            check(read(0xD39B) == 0xA2 and read(0xD39C) == 0x02 and read(0xD39D) == 0xA4,
                'Standalone leaves $D39B unpatched so rounds continue instead of freezing at $80F0')
            finish()
        elseif frame - phaseStart > 15 then
            check(false, 'Start+Select did not reach $80F0 within 15 frames')
            finish()
        end
    end
end, emu.eventType.endFrame)
