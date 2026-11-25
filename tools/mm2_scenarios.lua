-- Save-state generator for standalone Barba Man 2 (play/standalone/mm2-barba.nes).
local mem = emu.memType.nesMemory
local ppu = emu.memType.nesPpuDebug
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end
local function readPpu(a) return emu.read(a, ppu) end

local pendingSave = nil
local pendingStop = false
local function saveState(name)
    pendingSave = name
end

emu.addMemoryCallback(function()
    if pendingSave then
        local name = pendingSave
        pendingSave = nil
        local data = emu.createSavestate()
        local f = assert(io.open(PACK_DIR .. '/' .. name .. '.mss', 'wb'))
        f:write(data)
        f:close()
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

local frame = 0
local phase = 'title'
local phaseStart = 0
local bossIntroRoarCount = 0
local triggerWilyReveal = false
local stageSelSettled = false
local inp = {}

emu.addMemoryCallback(function() bossIntroRoarCount = bossIntroRoarCount + 1 end, emu.callbackType.exec, 0xF4B0)

emu.addMemoryCallback(function()
    if triggerWilyReveal then
        triggerWilyReveal = false
        write(0x8000, 0x06); write(0x8001, 26)
        write(0x8000, 0x07); write(0x8001, 27)
        write(0x002A, 0x08)
        emu.setState({['cpu.pc'] = 0x9678})
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

local function nametableHas(seq)
    for addr = 0x2000, 0x23BF - #seq + 1 do
        local ok = true
        for i = 1, #seq do
            if readPpu(addr + i - 1) ~= seq[i] then ok = false break end
        end
        if ok then return true end
    end
    return false
end

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if pendingStop and not pendingSave then emu.stop(0) return end
    frame = frame + 1
    local dt = frame - phaseStart
    inp = {}

    if phase == 'title' then
        if frame == 30 then
            saveState('title')
            phase = 'to_stagesel'
            phaseStart = frame
        end

    elseif phase == 'to_stagesel' then
        if (frame % 16) < 4 then inp = {start = true} end
        if nametableHas({0x05, 0x16, 0x09, 0x0C}) and nametableHas({0x0C, 0x09, 0x0E, 0x0B}) then
            if not stageSelSettled then
                stageSelSettled = true
                phaseStart = frame
            elseif dt >= 20 then
                saveState('stage_select')
                phase = 'select_boss'
                phaseStart = frame
            end
        elseif dt > 400 then
            emu.stop(1)
        end

    elseif phase == 'select_boss' then
        if dt >= 4 and dt < 8 then inp = {right = true}
        elseif dt >= 12 and dt < 16 then inp = {start = true} end
        if bossIntroRoarCount >= 1 then
            phase = 'boss_intro'
            phaseStart = frame
        elseif dt > 120 then
            emu.stop(1)
        end

    elseif phase == 'boss_intro' then
        if dt == 30 then
            saveState('boss_intro')
        end
        if dt >= 45 and readPpu(0x3F11) == 0x16 and readPpu(0x3F12) == 0x27 and readPpu(0x3F13) == 0x30 then
            phase = 'gameplay'
            phaseStart = frame
        elseif dt > 400 then
            emu.stop(1)
        end

    elseif phase == 'gameplay' then
        if dt >= 45 and dt <= 65 then
            inp = {right = true}
        elseif dt == 75 then
            saveState('gameplay')
            triggerWilyReveal = true
            phase = 'wily_reveal'
            phaseStart = frame
        end

    elseif phase == 'wily_reveal' then
        if dt == 170 then
            saveState('wily_reveal')
            pendingStop = true
        end
    end
end, emu.eventType.endFrame)
