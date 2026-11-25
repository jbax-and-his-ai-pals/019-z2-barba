-- Save-state generator for standalone Wheel of Barba (play/standalone/wheel-barba.nes).
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
local savedMenu = false
local inp = {}

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if pendingStop and not pendingSave then emu.stop(0) return end
    frame = frame + 1
    inp = {}

    local nmi = read(0x000E) + read(0x000F) * 256
    local s52 = read(0x0052)

    if phase == 'title' then
        if frame == 60 then
            saveState('title')
            phase = 'nav_to_board'
            phaseStart = frame
        end

    elseif phase == 'nav_to_board' then
        if nmi ~= 0xB67C and nmi ~= 0xC216 and nmi ~= 0x917C then
            if frame >= 700 and (frame % 30) < 2 then inp = {start = true} end
        elseif nmi == 0xB67C then
            if s52 == 0x00 and not savedMenu then
                if phaseStart == 0 then phaseStart = frame end
                if frame >= phaseStart + 25 then
                    savedMenu = true
                    saveState('menu')
                end
            elseif s52 == 0x00 or s52 == 0x01 or s52 == 0x02 then
                if (frame % 30) < 2 then inp = {a = true} end
            elseif s52 == 0x03 or s52 == 0x04 or s52 == 0x05 then
                local step = math.floor(frame / 16) % 4
                if (frame % 16) < 2 then
                    if step == 0 or step == 2 then inp = {a = true} else inp = {left = true} end
                end
            end
        elseif nmi == 0x917C then
            phase = 'board'
            phaseStart = frame
        end

    elseif phase == 'board' then
        if frame == phaseStart + 40 then
            saveState('board')
            -- Trigger Barba walking across stage to unveil a letter
            write(0x009D, 0x12)
            write(0x00AC, 0x00)
            write(0x00B3, 0xA0)
            write(0x00B4, 0x09)
            write(0x00B0, 0x05)
            phase = 'barba_walk'
            phaseStart = frame
        end

    elseif phase == 'barba_walk' then
        if frame == phaseStart + 15 then
            saveState('barba_walk')
            pendingStop = true
        end
    end

    if frame > 4000 then
        emu.stop(1)
    end
end, emu.eventType.endFrame)
