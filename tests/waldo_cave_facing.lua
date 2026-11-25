-- Verify that in Where's Barba? Bank 14 (Cave), walking down/up preserves Barba's
-- last horizontal facing (left/right) instead of switching left-right every 2 frames.
local mem = emu.memType.nesMemory
local function r(a) return emu.read(a, mem) end

local f = 0
local inp = {}
local done = false
local report = assert(io.open(OUTPUT_DIR .. '/waldo-cave-facing.txt', 'w'))
local allPass = true

local function finish(ok)
    if done then return end
    done = true
    report:write('RESULT ' .. (ok and 'PASS' or 'FAIL') .. '\n')
    report:close()
    emu.stop(ok and 0 or 1)
end

local function check(cond, msg)
    if done then return end
    if cond then
        report:write('PASS ' .. msg .. '\n')
    else
        report:write('FAIL ' .. msg .. '\n')
        allPass = false
    end
end

local function getBarbaFacing()
    local leftCount, rightCount = 0, 0
    for s = 0, 35 do
        local y = r(0x0700 + s * 4)
        if y < 0xEF then
            local attr = r(0x0702 + s * 4)
            if (attr & 0x40) ~= 0 then
                rightCount = rightCount + 1
            else
                leftCount = leftCount + 1
            end
        end
    end
    if leftCount == 36 and rightCount == 0 then return 'left' end
    if rightCount == 36 and leftCount == 0 then return 'right' end
    return string.format('mixed(L=%d,R=%d)', leftCount, rightCount)
end

local phase = 'boot'
local phaseFrame = 0
local searchStartFrame = 0
local caveSubFrame = 0

local lastVerticalA = nil
local dir10Frames = 0
local dir14Frames = 0
local vertLeftFrames = 0
local vertRightFrames = 0
local vertMismatch = 0

emu.addMemoryCallback(function()
    if phase == 'cave_test' and not done then
        local st = emu.getState()
        local a = st['cpu.a'] or 0
        if a >= 0x10 then
            lastVerticalA = a
            if a <= 0x13 then dir10Frames = dir10Frames + 1 else dir14Frames = dir14Frames + 1 end
        else
            lastVerticalA = nil
        end
    end
end, emu.callbackType.exec, 0x84FE)

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if done then return end
    f = f + 1
    inp = {}

    if phase == 'boot' then
        if f >= 120 and f <= 900 and f % 60 == 0 then
            inp = {start = true}
        end
        if r(0x7F00) == 1 then
            phase = 'search'
            searchStartFrame = f
        elseif f > 2000 then
            check(false, 'Timed out waiting to enter first search level')
            finish(false)
        end

    elseif phase == 'search' then
        if r(0x7F00) == 1 then
            local sf = f - searchStartFrame
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
        else
            searchStartFrame = f
            local lvl = r(0x0601)
            local facing = getBarbaFacing()
            if lvl == 2 and r(0x0790) < 0xEF and (facing == 'left' or facing == 'right') then
                phase = 'cave_wait'
                phaseFrame = f
            end
        end
        if f > 6000 then
            check(false, string.format('Timed out reaching Cave (level=%d, CROWD=%d)', r(0x0601), r(0x7F00)))
            finish(false)
        end

    elseif phase == 'cave_wait' then
        if f - phaseFrame >= 60 then
            phase = 'cave_test'
            caveSubFrame = 0
        end

    elseif phase == 'cave_test' then
        caveSubFrame = caveSubFrame + 1
        local facing = getBarbaFacing()
        local savedFacing = (r(0x7FD4) & 1) == 0 and 'left' or 'right'

        if lastVerticalA ~= nil then
            if facing == 'left' then vertLeftFrames = vertLeftFrames + 1
            elseif facing == 'right' then vertRightFrames = vertRightFrames + 1
            else vertMismatch = vertMismatch + 1 end
            if facing ~= savedFacing then
                vertMismatch = vertMismatch + 1
            end
            if vertLeftFrames == 12 then
                emu.write(0x7FD4, 1, mem)
            end
        end

        -- Walk in Cave to exercise vertical walking with both left and right facing
        if caveSubFrame <= 10 then
            inp = {left = true}
        elseif caveSubFrame <= 70 then
            inp = {down = true}
        elseif caveSubFrame <= 140 then
            inp = {up = true}
        elseif caveSubFrame <= 200 then
            inp = {down = true}
        else
            check(dir14Frames + dir10Frames >= 12, string.format('Observed vertical frames in Cave (10..13=%d, 14..17=%d)', dir10Frames, dir14Frames))
            check(vertLeftFrames >= 10, string.format('Observed vertical walking facing left (%d frames)', vertLeftFrames))
            check(vertRightFrames >= 10, string.format('Observed vertical walking facing right (%d frames)', vertRightFrames))
            check(vertMismatch == 0, string.format('Zero facing mismatches during vertical walking (%d)', vertMismatch))
            finish(allPass)
        end
    end
end, emu.eventType.endFrame)
