-- Generate a 10-slot save-state pack inside Where's Barba? inside Zelda II (barba.nes).
dofile(TEST_DIR .. '/newgame.lua')
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

local frame = 0
local phase = 'setup'
local enterStart = 0
local waldoStart = 0
local inp = {}
local stage = 'intro'
local sf = 0
local jumped = false
local waitFrames = 0
local aTimer = 0
local slotPhase = 'wait_hand'
local moonFrames = 0
local moonStarted = false

emu.addMemoryCallback(function()
    if pendingCapture then
        local id = pendingCapture
        pendingCapture = nil
        saveStateAndShot(id)
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

emu.addMemoryCallback(function()
    if phase == 'waldo' and not jumped then
        jumped = true
        w(0x0601, 5)
        emu.setState({['cpu.pc'] = 0xE193})
    end
end, emu.callbackType.exec, 0xE145)

emu.addEventCallback(function()
    if phase == 'setup' then
        if frame < 1000 then
            emu.setInput(newGameInput(frame), 0)
        elseif frame >= 1100 and (r(0x3B) < 1 or r(0x4D) < 0x26) then
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
    elseif phase == 'waldo' then
        emu.setInput(inp, 0)
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    if phase == 'setup' then
        if frame == 1000 then
            w(0x707, 1); w(0x706, 0); w(0x70A, 0); w(0x769, 3); w(0x561, 1)
            w(0x73, 54); w(0x74, 46); w(0x748, 0x2C)
            w(0x701, 0); w(0x75C, 0); w(0x704, 0); w(0x736, 0)
            w(0x73D, 0); w(0x726, 1)
        elseif frame > 1100 and r(0x3B) == 1 and r(0x4D) >= 0x26 then
            for slot = 0, 5 do w(0xB6 + slot, 0) end
            w(0x4D, 40); w(0x70, 0)
            phase = 'enter'
            enterStart = frame
        end
    elseif phase == 'enter' then
        local ef = frame - enterStart
        if ef > 250 and r(0xFFFA) == 0x03 and r(0xFFFB) == 0xF6 then
            phase = 'waldo'
            waldoStart = frame
        elseif ef > 350 then
            error('Timed out entering Waldo from Rauru door')
        end
    elseif phase == 'waldo' then
        local wf = frame - waldoStart
        inp = {}
        if stage == 'intro' then
            if wf == 100 or wf == 160 or wf == 220 or wf == 280 then
                inp = {start = true}
            end
            if wf == 60 then
                pendingCapture = 'title'
            elseif wf == 180 then
                pendingCapture = 'moon-ticket'
            elseif wf == 500 then
                pendingCapture = 'overworld-map'
            elseif wf == 1280 then
                pendingCapture = 'train-station'
                stage = 'find_train'
                sf = 0
            end
        elseif stage == 'find_train' then
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
            if jumped then
                stage = 'wait_castle'
                sf = 0
            elseif sf > 500 then
                error('Train station find timeout')
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
            if sf == 735 then
                pendingCapture = 'slots-ready'
            elseif sf == 740 then
                stage = 'play_slots'
                sf = 0
                aTimer = 4
                inp.a = true
                slotPhase = 'wait_hand'
            end
        elseif stage == 'play_slots' then
            sf = sf + 1
            if aTimer > 0 then
                aTimer = aTimer - 1
                inp.a = (aTimer > 0)
            end
            local hx = r(0x703)
            if slotPhase == 'wait_hand' and hx == 172 then
                waitFrames = 40
                slotPhase = 'r3_delay'
            elseif slotPhase == 'r3_delay' then
                waitFrames = waitFrames - 1
                if waitFrames <= 0 then slotPhase = 'r3_aim' end
            elseif slotPhase == 'r3_aim' and r(0x238) == 1 then
                aTimer = 4; waitFrames = 20; slotPhase = 'r3_settle'
            elseif slotPhase == 'r3_settle' then
                waitFrames = waitFrames - 1
                if waitFrames <= 0 then slotPhase = 'move_r2' end
            elseif slotPhase == 'move_r2' then
                if hx > 112 then inp.left = true else slotPhase = 'r2_aim' end
            elseif slotPhase == 'r2_aim' and r(0x228) == 1 then
                aTimer = 4; waitFrames = 20; slotPhase = 'r2_settle'
            elseif slotPhase == 'r2_settle' then
                waitFrames = waitFrames - 1
                if waitFrames <= 0 then
                    pendingCapture = 'slots-two-barbas'
                    slotPhase = 'move_r1'
                end
            elseif slotPhase == 'move_r1' then
                if hx > 48 then inp.left = true else slotPhase = 'r1_aim' end
            elseif slotPhase == 'r1_aim' and r(0x218) == 1 then
                aTimer = 4; waitFrames = 25; slotPhase = 'jackpot_wait'
            elseif slotPhase == 'jackpot_wait' then
                waitFrames = waitFrames - 1
                if waitFrames == 0 then
                    pendingCapture = 'slots-jackpot'
                    slotPhase = 'moon_wait'
                end
            elseif slotPhase == 'moon_wait' then
                if moonStarted or (r(0x00) == 0xA8 and r(0x34) == 0x1F and r(0x56) == 0x80) then
                    moonStarted = true
                    moonFrames = moonFrames + 1
                    if moonFrames == 30 then
                        pendingCapture = 'moon-ending'
                    elseif moonFrames == 1617 then
                        pendingCapture = 'moon-return'
                    elseif moonFrames == 1627 then
                        emu.stop(0)
                    end
                end
            end
        end
    end
end, emu.eventType.endFrame)
