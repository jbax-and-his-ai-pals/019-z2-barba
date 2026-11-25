-- Verify Friday the 13th Forest Coven endings:
--   Ending 3 (Debbie, $7C60=1): cliff levitation + pit drop -> "WELL THAT WAS WEIRD."
--   Ending 4 (Laura, $7C60=2): noodle eruption + tendril yank -> "WELL THAT WAS WEIRD."
local mem = emu.memType.nesMemory
local oam = emu.memType.nesSpriteRam
local function r(a) return emu.read(a, mem) end
local function w(a, v) emu.write(a, v, mem) end

local report = assert(io.open(OUTPUT_DIR .. '/f13-coven-endings.txt', 'w'))
local errors = 0
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    if not cond then errors = errors + 1 end
end

local f = 0
local inp = {}
local phase = 'boot'
local phaseStart = 0
local runIdx = 1  -- 1 = Debbie, 2 = Laura
local sawLift = false
local sawNoodles = false
local sawEndCard = false
local inForestState = nil
local pendingSave = false
local pendingLoad = false
local stopped = false

emu.addMemoryCallback(function()
    if pendingSave then
        pendingSave = false
        inForestState = emu.createSavestate()
    elseif pendingLoad then
        pendingLoad = false
        emu.loadSavestate(inForestState)
        w(0x0507, 3) -- Laura
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

local function finish()
    if stopped then return end
    stopped = true
    report:write(errors == 0 and 'RESULT PASS\n' or 'RESULT FAIL\n')
    report:close()
    emu.stop(errors == 0 and 0 or 1)
end

emu.addEventCallback(function()
    if stopped then return end
    f = f + 1
    inp = {}
    if phase == 'boot' then
        local dt = f - phaseStart
        if (dt >= 380 and dt < 385) or (dt >= 460 and dt < 465) then
            inp = {start = true}
        elseif dt == 520 then
            w(0x0507, 4) -- Debbie for deterministic road walk
        elseif dt >= 540 and dt < 545 then
            inp = {start = true}
        elseif dt == 950 then
            phase = 'walk_down'
            phaseStart = f
        end
    elseif phase == 'walk_down' then
        w(0x0528, 0x20)
        local dt = f - phaseStart
        if r(0x45) == 0x01 and r(0x44) >= 0xE0 then
            inp = ((dt % 10) < 7) and {down = true} or {right = true}
        else
            inp = {right = true}
        end
        if dt >= 790 and r(0x45) == 0x00 and r(0x4E) == 0x01 then
            phase = 'walk_up'
            phaseStart = f
        elseif (f - phaseStart) > 2400 then
            check(false, 'Timed out reaching south road (run ' .. runIdx .. ')')
            finish()
        end
    elseif phase == 'walk_up' then
        w(0x0528, 0x20)
        local dt = f - phaseStart
        if (r(0x45) == 0x03 and r(0x44) >= 0xD0) or (r(0x45) == 0x04 and r(0x44) <= 0x20) then
            inp = ((dt % 10) < 7) and {up = true} or {right = true}
        else
            inp = {right = true}
        end
        if dt > 1400 and r(0x45) == 0x00 then
            if runIdx == 1 then
                pendingSave = true
            else
                w(0x0507, 3)
            end
            phase = 'walk_trigger'
            phaseStart = f
        elseif dt > 2200 then
            check(false, 'Timed out entering forest (run ' .. runIdx .. ')')
            finish()
        end
    elseif phase == 'walk_trigger' then
        w(0x0528, 0x20)
        inp = {right = true}
        local flag = r(0x7C60)
        if flag ~= 0 then
            if runIdx == 1 then
                check(flag == 1, 'Debbie forest trigger sets $7C60=1 (' .. flag .. ')')
            else
                check(flag == 2, 'Laura forest trigger sets $7C60=2 (' .. flag .. ')')
            end
            phase = 'cutscene'
            phaseStart = f
        elseif (f - phaseStart) > 1200 then
            check(false, string.format('Timed out waiting for coven trigger (run %d: $38=%02X $C5=%02X $C9=%02X $45=%02X $44=%02X $4E=%02X)', runIdx, r(0x38), r(0xC5), r(0xC9), r(0x45), r(0x44), r(0x4E)))
            finish()
        end
    elseif phase == 'cutscene' then
        local dt = f - phaseStart
        if dt > 250 and dt < 620 then
            inp = {b = true, a = (dt % 35 == 0)}
        end
        if runIdx == 1 and dt >= 580 and dt <= 640 then
            local y0 = emu.read(0, oam)
            if y0 < 150 then sawLift = true end
        elseif runIdx == 2 and dt >= 580 and dt <= 660 then
            for i = 0, 252, 4 do
                local t = emu.read(i + 1, oam)
                if t >= 0x74 and t <= 0x77 and emu.read(i, oam) < 0xEF then
                    sawNoodles = true
                end
            end
        end
        if dt >= 760 and dt < 860 then
            sawEndCard = true
            inp = {start = (dt % 15 < 5)}
        elseif dt == 870 then
            if runIdx == 1 then
                check(sawLift, 'Debbie levitated above ground before cliff drop')
                check(sawEndCard, 'Debbie reached ending card')
                check(r(0x7C60) == 0, 'Pressing Start on ending card resets F13 ($7C60=0)')
                runIdx = 2
                sawEndCard = false
                pendingLoad = true
                phase = 'walk_trigger'
                phaseStart = f
            else
                check(sawNoodles, 'Laura grabbed by animated OAM noodle tendrils')
                check(sawEndCard, 'Laura reached ending card')
                finish()
            end
        end
    end
end, emu.eventType.endFrame)
