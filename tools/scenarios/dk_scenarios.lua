-- Save-state generator for standalone Barba Kong (play/standalone/dk-barba.nes).
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

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
local inp = {}

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

local function jumpStage(stageId)
    write(0x00A0, 0)
    write(0x009F, 0)
    write(0x0053, stageId)
    write(0x0043, 0x76)
    write(0x004E, 0)
    write(0x004F, 0)
    write(0x009A, 0)
end

emu.addEventCallback(function()
    if pendingStop and not pendingSave then emu.stop(0) return end
    frame = frame + 1
    inp = {}

    if phase == 'title' then
        if frame == 65 then
            saveState('title')
            phase = 'press_start'
            phaseStart = frame
        end

    elseif phase == 'press_start' then
        if frame - phaseStart < 6 then
            inp = {start = true}
        else
            phase = 'wait_25m'
            phaseStart = frame
        end

    elseif phase == 'wait_25m' then
        if read(0x004E) == 0 and read(0x004F) == 1 then
            phase = 'stage_25m'
            phaseStart = frame
        elseif frame - phaseStart > 600 then
            emu.stop(1)
        end

    elseif phase == 'stage_25m' then
        if frame - phaseStart == 100 then
            saveState('stage_25m')
            -- Activate Flame Fury (hammer) state
            write(0x00A0, 1)
            write(0x009F, 1)
            write(0x003F, 0x80)
            phase = 'fury_25m'
            phaseStart = frame
        end

    elseif phase == 'fury_25m' then
        if frame - phaseStart == 15 then
            saveState('fury_25m')
            jumpStage(2)
            phase = 'stage_50m'
            phaseStart = frame
        end

    elseif phase == 'stage_50m' then
        if frame - phaseStart == 100 then
            saveState('stage_50m')
            jumpStage(3)
            phase = 'stage_75m'
            phaseStart = frame
        end

    elseif phase == 'stage_75m' then
        if frame - phaseStart == 100 then
            saveState('stage_75m')
            jumpStage(4)
            phase = 'stage_100m'
            phaseStart = frame
        end

    elseif phase == 'stage_100m' then
        if frame - phaseStart == 100 then
            saveState('stage_100m')
            pendingStop = true
        end
    end
end, emu.eventType.endFrame)
