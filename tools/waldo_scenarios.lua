-- Generate a 10-slot Where's Barba? save-state pack (especially Slots + key scenes).
local mem = emu.memType.nesMemory
local function r(a) return emu.read(a, mem) end
local function w(a, v) emu.write(a, v, mem) end

local pendingCapture = nil
local pendingLoad = nil
local ticketState = nil

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

local phase = 'boot'
local f = 0

-- Phase 2 state (Slots + Castle)
local rightHeld, downHeld, pressA = false, false, false
local slotPhase = 'wait'
local leftHeld, aHeld = false, false
local aTimer = 0
local waitFrames = 0

emu.addEventCallback(function()
    if phase == 'boot' then
        if f == 180 or f == 240 or f == 300 or f == 360 or f == 460 then
            emu.setInput({start = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'cave' then
        if f == 40 then
            emu.setInput({start = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'subway' then
        if f == 10 or f == 11 then
            emu.setInput({a = true}, 0)
        elseif pressA then
            emu.setInput({a = true}, 0)
        elseif aHeld or leftHeld then
            emu.setInput({a = aHeld, left = leftHeld}, 0)
        else
            emu.setInput({right = rightHeld, down = downHeld}, 0)
        end
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

emu.addMemoryCallback(function()
    if pendingCapture then
        local id = pendingCapture
        pendingCapture = nil
        if id == '_ticket' then
            ticketState = emu.createSavestate()
        else
            saveStateAndShot(id)
        end
    elseif pendingLoad then
        local data = pendingLoad
        pendingLoad = nil
        emu.loadSavestate(data)
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

emu.addEventCallback(function()
    f = f + 1
    if phase == 'boot' then
        if f == 280 then
            pendingCapture = 'title'
        elseif f == 420 then
            pendingCapture = 'moon-ticket'
        elseif f == 1250 then
            pendingCapture = 'overworld-map'
        elseif f == 1450 then
            pendingCapture = 'train-station'
        elseif f == 1455 then
            local sf = assert(io.open(SUBWAY_STATE, 'rb'))
            pendingLoad = sf:read('*a')
            sf:close()
            phase = 'subway'
            f = 0
        end
    elseif phase == 'subway' then
        if f >= 760 and f < 1000 then
            local cx, cy = r(0x703), r(0x700)
            rightHeld = (cx < 132)
            downHeld = (cy < 80)
            if not rightHeld and not downHeld and f < 950 then
                pressA = (f % 15 == 0)
            else
                pressA = false
            end
        else
            rightHeld, downHeld, pressA = false, false, false
        end

        if f == 760 then
            pendingCapture = 'castle'
        elseif f == 1495 then
            pendingCapture = 'slots-ready'
        end

        if aTimer > 0 then
            aTimer = aTimer - 1
            aHeld = (aTimer > 0)
        else
            aHeld = false
        end
        leftHeld = false

        local hx = r(0x703)
        if f == 1500 then
            aTimer = 4
            slotPhase = 'wait_hand'
        elseif slotPhase == 'wait_hand' and hx == 172 then
            waitFrames = 40
            slotPhase = 'r3_delay'
        elseif slotPhase == 'r3_delay' then
            waitFrames = waitFrames - 1
            if waitFrames <= 0 then slotPhase = 'r3_aim' end
        elseif slotPhase == 'r3_aim' and r(0x238) == 1 then
            aTimer = 4
            waitFrames = 20
            slotPhase = 'r3_settle'
        elseif slotPhase == 'r3_settle' then
            waitFrames = waitFrames - 1
            if waitFrames <= 0 then slotPhase = 'move_r2' end
        elseif slotPhase == 'move_r2' then
            if hx > 112 then leftHeld = true else slotPhase = 'r2_aim' end
        elseif slotPhase == 'r2_aim' and r(0x228) == 1 then
            aTimer = 4
            waitFrames = 20
            slotPhase = 'r2_settle'
        elseif slotPhase == 'r2_settle' then
            waitFrames = waitFrames - 1
            if waitFrames <= 0 then
                pendingCapture = 'slots-two-barbas'
                slotPhase = 'move_r1'
            end
        elseif slotPhase == 'move_r1' then
            if hx > 48 then leftHeld = true else slotPhase = 'r1_aim' end
        elseif slotPhase == 'r1_aim' and r(0x218) == 1 then
            aTimer = 4
            waitFrames = 25
            slotPhase = 'jackpot_wait'
        elseif slotPhase == 'jackpot_wait' then
            waitFrames = waitFrames - 1
            if waitFrames == 0 then
                pendingCapture = 'slots-jackpot'
                slotPhase = 'moon_wait'
                waitFrames = 1200
            end
        elseif slotPhase == 'moon_wait' then
            waitFrames = waitFrames - 1
            if waitFrames == 0 then
                pendingCapture = 'moon-ending'
                slotPhase = 'finish'
                waitFrames = 10
            end
        elseif slotPhase == 'finish' then
            waitFrames = waitFrames - 1
            if waitFrames <= 0 then
                emu.stop(0)
            end
        end
    end
end, emu.eventType.endFrame)
