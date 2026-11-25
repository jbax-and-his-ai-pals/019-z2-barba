-- Generate save states right in front of every active portal door in PORTAL_SLOTS.
-- Prepended by tools/create_portal_door_pack.py with PACK_DIR, TEST_DIR, and PORTAL_SLOTS.
dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local frame = 0
local idx = 1
local phase = 'boot'
local phaseStart = 0
local pendingCapture = nil

emu.addMemoryCallback(function()
    if pendingCapture then
        local slot = pendingCapture
        pendingCapture = nil
        local bytes = emu.createSavestate()
        local f = assert(io.open(PACK_DIR .. '/portal-' .. slot.id .. '.mss', 'wb'))
        f:write(bytes)
        f:close()
        idx = idx + 1
        if idx > #PORTAL_SLOTS then
            emu.stop(0)
        else
            phase = 'advance_next'
        end
    end
end, emu.callbackType.exec, 0xC000, 0xFFFF)

local function startWarp(slot)
    write(0x707, 1)
    write(0x706, slot.town)
    write(0x056B, slot.town)
    write(0x769, 3)
    write(0x561, slot.room)
    write(0x701, 0)
    write(0x75C, 0)
    write(0x704, 0)
    write(0x736, 0)
    write(0x73D, 0)
    write(0x726, 1)
    phase = 'load_room'
    phaseStart = frame
end

emu.addEventCallback(function()
    if phase == 'boot' then
        if frame < 1000 then
            emu.setInput(newGameInput(frame), 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'walk' then
        local slot = PORTAL_SLOTS[idx]
        local curPage = read(0x3B)
        local curX = read(0x4D)
        if curPage < slot.page or (curPage == slot.page and curX < slot.x - 4) then
            emu.setInput({right = true}, 0)
        elseif curPage > slot.page or (curPage == slot.page and curX > slot.x + 4) then
            emu.setInput({left = true}, 0)
        else
            emu.setInput({}, 0)
        end
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    if phase == 'boot' then
        if frame == 1000 then
            if #PORTAL_SLOTS == 0 then
                emu.stop(0)
                return
            end
            startWarp(PORTAL_SLOTS[idx])
        end
    elseif phase == 'load_room' then
        if frame - phaseStart >= 90 and read(0x736) == 0x0B then
            phase = 'walk'
            phaseStart = frame
        elseif frame - phaseStart > 400 then
            emu.stop(1)
        end
    elseif phase == 'walk' then
        local slot = PORTAL_SLOTS[idx]
        for s = 0, 5 do write(0xB6 + s, 0) end
        local curPage = read(0x3B)
        local curX = read(0x4D)
        if curPage == slot.page and curX >= slot.x - 4 and curX <= slot.x + 4 then
            write(0x4D, slot.x)
            write(0x70, 0)
            phase = 'settle'
            phaseStart = frame
        elseif frame - phaseStart > 900 then
            emu.stop(1)
        end
    elseif phase == 'settle' then
        for s = 0, 5 do write(0xB6 + s, 0) end
        if frame - phaseStart >= 8 and not pendingCapture then
            pendingCapture = PORTAL_SLOTS[idx]
            phase = 'capturing'
        end
    elseif phase == 'advance_next' then
        startWarp(PORTAL_SLOTS[idx])
    end
end, emu.eventType.endFrame)
