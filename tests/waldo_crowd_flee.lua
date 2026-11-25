-- Verify that in Where's Barba?, the crowd automatically flees from Barba
-- while Barba stays intact and clickable.
local mem = emu.memType.nesMemory
local function r(a) return emu.read(a, mem) end

local f = 0
local inp = {}
local started = false
local startFrame = 0
local initialDiffs = 0
local afterDiffs = 0
local checkedFlee = false
local initialLevel = 0
local foundFrame = 0

local function countCrowdTiles()
    local n = 0
    for i = 0, 1535 do
        if r(0x7800 + i) ~= r(0x7200 + i) then
            n = n + 1
        end
    end
    return n
end

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    f = f + 1
    inp = {}
    if not started then
        if f == 180 or f == 240 or f == 300 or f == 360 or f == 460 then
            inp = {start = true}
        end
        if r(0x7F00) == 1 then
            started = true
            startFrame = f
            initialLevel = r(0x0601)
            initialDiffs = countCrowdTiles()
        elseif f > 2000 then
            error('Timed out waiting for CROWD_ACTIVE == 1')
        end
    elseif not checkedFlee and f >= startFrame + 240 then
        checkedFlee = true
        afterDiffs = countCrowdTiles()
        if afterDiffs >= initialDiffs then
            error(string.format('Crowd did not flee: initial=%d after=%d', initialDiffs, afterDiffs))
        end
        local bx, by = r(0x718B), r(0x718C)
        for dy = 0, 1 do
            for dx = 0, 1 do
                local off = (by + dy) * 64 + (bx + dx)
                if r(0x7800 + off) ~= r(0x7200 + off) then
                    error(string.format('Barba tile overwritten at (%d,%d)', bx + dx, by + dy))
                end
            end
        end
    elseif checkedFlee then
        local sf = f - (startFrame + 240)
        local cx, cy = r(0x703), r(0x700)
        local scrollX = r(0x04) + (r(0x00) % 2) * 256
        local step = math.floor(sf / 12)
        local tx = r(0x718B) * 8 + 8 - scrollX + ((step % 3) - 1) * 4
        local ty = r(0x718C) * 8 + 32 + ((math.floor(step / 3) % 3) - 1) * 4
        if tx > 224 then tx = 224 elseif tx < 16 then tx = 16 end
        if cx < tx - 4 then inp.right = true elseif cx > tx + 4 then inp.left = true end
        if cy < ty - 4 then inp.down = true elseif cy > ty + 4 then inp.up = true end
        if not inp.right and not inp.left and not inp.down and not inp.up and (sf % 6 == 0) then
            inp.a = true
        end
        if foundFrame == 0 then
            if r(0x7190) == 1 or r(0x0601) ~= initialLevel then
                foundFrame = f
            elseif sf > 600 then
                error(string.format('Timed out clicking Barba cx=%d cy=%d tx=%d ty=%d', cx, cy, tx, ty))
            end
        else
            -- Wait until we return to the Overworld Map and CROWD_ACTIVE clears
            if r(0x7F00) == 0 and f >= foundFrame + 240 then
                local shot = io.open(OUTPUT_DIR .. '/waldo-map-after.png', 'wb')
                if shot then shot:write(emu.takeScreenshot()); shot:close() end
                local rep = assert(io.open(OUTPUT_DIR .. '/waldo-crowd-flee.txt', 'w'))
                rep:write(string.format('PASS initialDiffs=%d afterDiffs=%d\nPASS Barba intact and found (level %d -> %d)\nPASS Map screen returned with CROWD_ACTIVE=0\nRESULT PASS\n',
                    initialDiffs, afterDiffs, initialLevel, r(0x0601)))
                rep:close()
                emu.stop(0)
            elseif f > foundFrame + 700 then
                error(string.format('Timed out waiting for map return (CROWD_ACTIVE=%d)', r(0x7F00)))
            end
        end
    end
end, emu.eventType.endFrame)
