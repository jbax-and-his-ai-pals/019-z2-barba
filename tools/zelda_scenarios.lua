-- Save-state generator for standalone The Legend of Zelda: Barba Edition (play/standalone/zelda-barba.nes).
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

emu.addEventCallback(function()
    if pendingStop and not pendingSave then emu.stop(0) return end
    frame = frame + 1
    local dt = frame - phaseStart
    inp = {}

    if frame == 1 then
        for i = 0, 7 do write(0x7FF0 + i, 0x11 * (i + 1)) end
    end

    if phase == 'title' then
        if frame == 120 then
            saveState('title')
            phase = 'to_fileselect'
            phaseStart = frame
        end

    elseif phase == 'to_fileselect' then
        if dt >= 10 and dt < 15 then inp = {start = true} end
        if read(0x12) == 0x01 and dt > 40 then
            saveState('file_select')
            phase = 'register_select'
            phaseStart = frame
        elseif dt > 150 then
            emu.stop(1)
        end

    elseif phase == 'register_select' then
        if dt > 180 then
            emu.stop(1)
        elseif read(0x12) == 0x01 then
            if read(0x16) ~= 0x03 then
                if (dt % 12) == 2 then inp = {select = true} end
            else
                if (dt % 12) == 6 then inp = {start = true} end
            end
        else
            phase = 'register_name'
            phaseStart = frame
        end

    elseif phase == 'register_name' then
        if dt > 180 then
            emu.stop(1)
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
        if read(0x12) == 0x01 and dt >= 30 and (dt % 16) == 2 then
            inp = {start = true}
        end
        if read(0x12) == 0x05 and read(0x7FEA) >= 2 and read(0x7FEC) == 0 and dt > 60 then
            saveState('overworld_start')
            write(0x0657, 1)
            phase = 'to_burn_bush'
            phaseStart = frame
        elseif dt > 420 then
            emu.stop(1)
        end

    elseif phase == 'to_burn_bush' then
        if read(0xEB) == 0x77 then
            inp = {right = true}
        elseif read(0xEB) == 0x78 and dt < 300 then
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
                saveState('burn_bush')
                pendingStop = true
            end
        elseif dt > 340 then
            emu.stop(1)
        end
    end
end, emu.eventType.endFrame)
