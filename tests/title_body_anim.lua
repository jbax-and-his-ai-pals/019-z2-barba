-- Title screen Barba body & tail animation + 2nd-roar-only screen shake:
-- Rest pose keeps walk0 neck ($06/$08) and tail on the cliff ($9F).
-- No wiggle before or after roar: only during roars ($05F0 > 0, $12 & $08) does
-- the neck swap to walk1 ($10/$12) and the tail wag upward ($6544/$6568 = $9E).
-- Only the 2nd roar since reset ($05FA == 2) shakes the screen ($64FA = 0 or 2).
local function rd(a) return emu.read(a, emu.memType.nesDebug) end
local frame, errors = 0, 0
local restSeen, roarWag = 0, 0
local badState = 0
local shakeR1, shakeR2, shakeR3Plus = 0, 0, 0
local storySeen, backToTitle = false, false

local extra = {}

local function endFrame()
    frame = frame + 1
    local mode = rd(0x0736)
    if mode == 4 then storySeen = true elseif storySeen and mode == 3 then backToTitle = true end
    local shake = rd(0x64FA)
    local roar = rd(0x05F0)
    local count = rd(0x05FA)
    if mode >= 3 and shake ~= 0 then
        if count == 1 then shakeR1 = shakeR1 + 1
        elseif count == 2 and roar > 0 then shakeR2 = shakeR2 + 1
        else shakeR3Plus = shakeR3Plus + 1; extra[#extra+1] = string.format('f=%d m=%d c=%d r=%d s=%d', frame, mode, count, roar, shake) end
    end
    if mode == 3 and rd(0x021C) == 0x7F then
        local f12 = rd(0x12)
        local neckL, neckR = rd(0x0241), rd(0x0259)
        local nearTipY, farTipY = rd(0x0244), rd(0x6568)
        local wagging = (roar > 0 and (f12 & 0x08) ~= 0)
        if wagging then
            roarWag = roarWag + 1
            if neckL ~= 0x10 or neckR ~= 0x12 or nearTipY ~= 0x9E or farTipY ~= 0x9E then
                badState = badState + 1
            end
        else
            restSeen = restSeen + 1
            if neckL ~= 0x06 or neckR ~= 0x08 or nearTipY ~= 0x9F or farTipY ~= 0x9F then
                badState = badState + 1
            end
        end
    end
    if frame == 4700 then
        local f = assert(io.open(OUTPUT_DIR .. '/title-body-anim.txt', 'w'))
        local function check(ok, msg)
            f:write((ok and 'PASS ' or 'FAIL ') .. msg .. '\n')
            if not ok then errors = errors + 1 end
        end
        check(restSeen > 500, 'rest frames seen (' .. restSeen .. ')')
        check(roarWag > 50, 'roar neck swap and tail wag seen (' .. roarWag .. ')')
        check(badState == 0, 'no wiggle outside roar and all body/tail poses match (' .. badState .. ' bad)')
        check(shakeR1 == 0, '1st roar does not shake (' .. shakeR1 .. ')')
        check(shakeR2 > 10, '2nd roar shakes the screen (' .. shakeR2 .. ' nonzero frames)')
        check(storySeen and backToTitle, 'story scroll ran and returned to title')
        check(shakeR3Plus == 0, '3rd+ roars and post-story title never shake (' .. table.concat(extra, '; ') .. ')')
        f:write('RESULT ' .. (errors == 0 and 'PASS' or 'FAIL') .. '\n')
        f:close()
        local stop = emu.exit or emu.stop
        stop(errors == 0 and 0 or 1)
    end
end
emu.addEventCallback(endFrame, emu.eventType.endFrame)
