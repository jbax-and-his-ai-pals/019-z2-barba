-- Generate a 10-slot Where's Barba? save-state pack for play/wheres-barba.nes.
local mem = emu.memType.nesMemory
local function r(a) return emu.read(a, mem) end
local function w(a, v) emu.write(a, v, mem) end

local pendingCapture = nil

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

local f = 0
local stage = 'intro'
local sf = 0
local jumpToSubway = false
local subwayFrames = 0
local jumpToCastle = false
local inp = {}
local waitFrames = 0
local aTimer = 0
local slotPhase = 'wait_hand'

emu.addMemoryCallback(function()
    if jumpToSubway then
        jumpToSubway = false
        w(0x7F00, 0)
        w(0x7F02, 0)
        w(0x7F90, 0)
        w(0x0601, 5)
        w(0x0603, 0)
        emu.setState({['cpu.pc'] = 0xE185})
    elseif pendingCapture then
        local id = pendingCapture
        pendingCapture = nil
        saveStateAndShot(id)
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

emu.addMemoryCallback(function()
    if jumpToCastle and r(0x0705) == 0x78 and r(0x0709) == 0x79 then
        jumpToCastle = false
        w(0x0601, 5)
        emu.setState({['cpu.pc'] = 0xE193})
    end
end, emu.callbackType.exec, 0xA073)

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    f = f + 1
    inp = {}
    if stage == 'intro' then
        if f == 180 or f == 240 or f == 300 or f == 360 or f == 460 then
            inp = {start = true}
        end
        if f == 280 then
            pendingCapture = 'title'
        elseif f == 340 then
            pendingCapture = 'skill-select'
        elseif f == 420 then
            pendingCapture = 'moon-ticket'
        elseif f == 1250 then
            pendingCapture = 'overworld-map'
        elseif f == 1450 then
            pendingCapture = 'train-station'
        elseif f == 1460 then
            jumpToSubway = true
            stage = 'wait_subway'
            sf = 0
        end
    elseif stage == 'wait_subway' then
        sf = sf + 1
        if sf == 540 then
            pendingCapture = 'before-subway'
        elseif sf > 540 and r(0x0705) == 0x78 and r(0x0709) == 0x79 and r(0x00) == 0x88 then
            subwayFrames = subwayFrames + 1
            if subwayFrames == 30 then
                jumpToCastle = true
                stage = 'wait_castle'
                sf = 0
            end
        elseif sf > 900 then
            error('Timed out waiting to enter Subway level')
        end
    elseif stage == 'wait_castle' then
        sf = sf + 1
        if sf == 900 then
            pendingCapture = 'castle'
            stage = 'solve_castle'
            sf = 0
        end
    elseif stage == 'solve_castle' then
        sf = sf + 1
        local cx, cy = r(0x703), r(0x700)
        local scrollX = r(0x03) + (r(0x00) % 2) * 256
        local step = math.floor(sf / 12)
        local tx = r(0x718B) * 8 + 8 - scrollX + ((step % 3) - 1) * 4
        local ty = r(0x718C) * 8 + 32 + ((math.floor(step / 3) % 3) - 1) * 4
        if tx > 224 then tx = 224 elseif tx < 16 then tx = 16 end
        if cx < tx - 1 then inp.right = true elseif cx > tx + 1 then inp.left = true end
        if cy < ty - 1 then inp.down = true elseif cy > ty + 1 then inp.up = true end
        if not inp.right and not inp.left and not inp.down and not inp.up and (sf % 6 == 0) then
            inp.a = true
        end
        if r(0x0601) ~= 6 then
            stage = 'wait_slots'
            sf = 0
        elseif sf > 600 then
            error(string.format('Castle find timeout cx=%d cy=%d scrollX=%d tx=%d ty=%d b=(%d,%d)',
                cx, cy, scrollX, tx, ty, r(0x718B), r(0x718C)))
        end
    elseif stage == 'wait_slots' then
        sf = sf + 1
        if sf == 740 then
            stage = 'slots'
            sf = 0
        end
    elseif stage == 'slots' then
        sf = sf + 1
        if aTimer > 0 then
            aTimer = aTimer - 1
            inp.a = (aTimer > 0)
        end
        local hx = r(0x703)
        if sf == 5 then
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
            if hx > 112 then inp.left = true else slotPhase = 'r2_aim' end
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
            if hx > 48 then inp.left = true else slotPhase = 'r1_aim' end
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
