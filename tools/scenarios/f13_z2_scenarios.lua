-- Generate save states inside Friday the 13th inside Zelda II (build/barba.nes).
dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local function r(a) return emu.read(a, mem) end
local function w(a, v) emu.write(a, v, mem) end

local pendingCapture = nil
local triggerWin = false

local function saveStateAndShot(id)
    local data = emu.createSavestate()
    local f = assert(io.open(PACK_DIR .. '/' .. id .. '.mss', 'wb'))
    f:write(data)
    f:close()
    local png = emu.takeScreenshot()
    local pf = assert(io.open(PACK_DIR .. '/' .. id .. '.png', 'wb'))
    pf:write(png)
    pf:close()
end

emu.addMemoryCallback(function()
    if triggerWin then
        triggerWin = false
        w(0x0522, 2)
        emu.setState({['cpu.pc'] = 0x8E40})
        saveStateAndShot('f13-win-return')
    elseif pendingCapture then
        local id = pendingCapture
        pendingCapture = nil
        saveStateAndShot(id)
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

local frame = 0
local phase = 'setup'
local enterStart = 0
local f13Start = 0
local inp = {}

emu.addEventCallback(function()
    if phase == 'setup' then
        if frame < 1000 then
            emu.setInput(newGameInput(frame), 0)
        elseif frame >= 1100 and (r(0x3B) ~= 0 or r(0x4D) < 0x94) then
            emu.setInput({right = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'enter' then
        local ef = frame - enterStart
        emu.setInput({
            up = (ef >= 10 and ef < 15),
            b = (ef >= 250 and ef < 254),
        }, 0)
    elseif phase == 'f13' then
        emu.setInput(inp, 0)
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    if phase == 'setup' then
        if frame == 1000 then
            w(0x707, 1); w(0x706, 0); w(0x70A, 0); w(0x769, 3); w(0x561, 5)
            w(0x73, 36); w(0x74, 2); w(0x748, 0x2E); w(0x56B, 1)
            w(0x701, 0); w(0x75C, 0); w(0x704, 0); w(0x736, 0)
            w(0x73D, 0); w(0x726, 1)
        elseif frame > 1100 and r(0x3B) == 0 and r(0x4D) >= 0x94 then
            for slot = 0, 5 do w(0xB6 + slot, 0) end
            w(0x4D, 0x95); w(0x70, 0)
            pendingCapture = 'ruto-portal'
            phase = 'enter'
            enterStart = frame
        end
    elseif phase == 'enter' then
        local ef = frame - enterStart
        if ef > 250 and r(0xFFFA) == 0x40 and r(0xFFFB) == 0x78 then
            phase = 'f13'
            f13Start = frame
        elseif ef > 350 then
            error('Timed out entering F13 from Ruto door')
        end
    elseif phase == 'f13' then
        local ff = frame - f13Start
        inp = {}
        if ff == 100 then
            pendingCapture = 'f13-title'
        elseif ff >= 110 and ff < 115 then
            inp = {start = true}
        elseif ff >= 190 and ff < 195 then
            inp = {start = true}
        elseif ff == 250 then
            pendingCapture = 'f13-map'
        elseif ff >= 270 and ff < 275 then
            inp = {start = true}
        elseif ff == 690 then
            pendingCapture = 'f13-exterior'
        elseif ff >= 700 and ff < 710 then
            inp = {up = true}
        elseif ff == 760 then
            pendingCapture = 'f13-cabin'
        elseif ff == 780 then
            triggerWin = true
        elseif ff == 800 then
            emu.stop(0)
        end
    end
end, emu.eventType.endFrame)
