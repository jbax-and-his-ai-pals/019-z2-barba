-- Save-state generator for standalone Barba's Punch-Out!! (play/standalone/mtpo-barba.nes).
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
local phase = 'boot'
local phaseStart = 0
local inp = {}
local titleFirst = nil
local tapeFirst = nil
local fightFrames = 0
local savedTitle = false
local savedTape = false

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if pendingStop and not pendingSave then emu.stop(0) return end
    frame = frame + 1
    local dt = frame - phaseStart
    inp = {}

    if frame == 1 then
        for i = 0, 7 do write(0x7FF0 + i, 0x37 + i * 17) end
    end

    if phase == 'boot' then
        if frame == 250 then
            saveState('intro')
            phase = 'to_fight'
            phaseStart = frame
        end

    elseif phase == 'to_fight' then
        if (dt % 40) < 4 then inp.start = true end
        local vmode = read(0x7F81)
        local ppu11 = read(0x11)
        if vmode == 1 and (ppu11 & 0x18) == 0x18 and not titleFirst then
            titleFirst = frame
        end
        if titleFirst and not savedTitle and frame >= titleFirst + 35 then
            savedTitle = true
            saveState('title')
        end
        if vmode == 3 and (ppu11 & 0x18) == 0x18 and not tapeFirst then
            tapeFirst = frame
        end
        if tapeFirst and not savedTape and frame >= tapeFirst + 35 then
            savedTape = true
            saveState('tape')
        end
        if read(0x1D) == 0 and (ppu11 & 0x18) == 0x18 and dt > 60 then
            phase = 'fight'
            phaseStart = frame
        elseif dt > 1300 then
            emu.stop(1)
        end

    elseif phase == 'fight' then
        local m51 = read(0x51)
        local cBarba = read(0x048D)
        if m51 == 0x00 or cBarba == 0x16 then
            fightFrames = fightFrames + 1
            if fightFrames == 25 then
                saveState('fight')
                pendingStop = true
            end
        elseif dt > 1300 then
            emu.stop(1)
        end
    end
end, emu.eventType.endFrame)
