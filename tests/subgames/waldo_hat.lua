dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end
local function writeFile(name, data)
    local f = assert(io.open(OUTPUT_DIR .. '/' .. name, 'wb'))
    f:write(data)
    f:close()
end

local frame = 0
local phase = 'setup'
local phaseStart = 0
local currentInput = {}
local report = assert(io.open(OUTPUT_DIR .. '/waldo-hat.txt', 'w'))
local errors = 0
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    if not cond then errors = errors + 1 end
end

local function findHatOam(tile)
    tile = tile or 0x5F
    for i = 0x20, 0xFC, 4 do
        if read(0x6500 + i + 1) == tile and read(0x6500 + i) < 0xF0 then
            return read(0x6500 + i), read(0x6500 + i + 2), read(0x6500 + i + 3)
        end
    end
    return nil
end

local walkDeltas = {}
local airRiseDelta = nil
local airFallDelta = nil
local sawCrouch = false
local sawUp = false
local sawRightFlip = false

local sawHat6 = 0
local sawHatWrite6 = 0
local lastHatDiag = ''
emu.addMemoryCallback(function()
    sawHat6 = sawHat6 + 1
    if read(0x0736) == 0x0B and read(0x648B) == 0x57 then
        lastHatDiag = string.format('076C=%02X 654C=%02X 654D=%02X 05FA=%02X', read(0x076C), read(0x654C), read(0x654D), read(0x05FA))
    end
end, emu.callbackType.exec, LABELS.DrawWaldoHat6)
local writeFrames = {}
emu.addMemoryCallback(function()
    sawHatWrite6 = sawHatWrite6 + 1
    writeFrames[#writeFrames + 1] = frame
end, emu.callbackType.exec, LABELS.DrawWaldoHatWrite6)

emu.addEventCallback(function()
    if phase == 'setup' then
        emu.setInput(newGameInput(frame), 0)
    else
        emu.setInput(currentInput, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    currentInput = {}
    if phase == 'setup' then
        if frame == 1000 then
            write(0x707, 1); write(0x706, 0); write(0x769, 3); write(0x561, 1)
            write(0x701, 0); write(0x75C, 0); write(0x704, 0); write(0x736, 0)
            write(0x73D, 0); write(0x726, 1)
            write(0x648B, 0x57)
            phase = 'wait_rauru'
            phaseStart = frame
        end
    elseif phase == 'wait_rauru' then
        if read(0x0736) == 0x0B and read(0x0726) == 0 and read(0x654C) < 0xF0 and frame - phaseStart >= 160 then
            phase = 'idle'
            phaseStart = frame
        elseif frame - phaseStart > 360 then
            error(string.format('Timed out entering Rauru (0736=%02X 0726=%02X 3B=%02X 4D=%02X 29=%02X 654C=%02X 654D=%02X 654E=%02X 654F=%02X 648B=%02X)',
                read(0x0736), read(0x0726), read(0x3B), read(0x4D), read(0x29), read(0x654C), read(0x654D), read(0x654E), read(0x654F), read(0x648B)))
        end
    elseif phase == 'idle' then
        local elapsed = frame - phaseStart
        if elapsed == 6 then
            local fy = findHatOam(0x1D)
            local hy, ha, hx = findHatOam(0x5F)
            local headY = read(0x654C)
            check(fy ~= nil and hy ~= nil, '2-sprite hat ($1D + $5F) drawn in OAM')
            if hy then
                local d = headY - hy
                check(d >= 3 and d <= 7, string.format('Hat sits %dpx above head (headY=%d hatY=%d)', d, headY, hy))
            end
            writeFile('waldo-hat-idle.png', emu.takeScreenshot())
            phase = 'walk'
            phaseStart = frame
        end
    elseif phase == 'walk' then
        currentInput = {right = true}
        local elapsed = frame - phaseStart
        local hy, ha, hx = findHatOam()
        local headY = read(0x654C)
        if hy and headY < 0xF0 then
            walkDeltas[headY - hy] = true
            if math.floor(ha / 64) % 2 == 1 then sawRightFlip = true end
        end
        if elapsed == 12 then
            writeFile('waldo-hat-walk.png', emu.takeScreenshot())
        end
        if elapsed >= 24 then
            local count = 0
            for _ in pairs(walkDeltas) do count = count + 1 end
            check(count >= 2, string.format('Hat bobs vertically while walking (%d distinct offsets)', count))
            check(sawRightFlip, 'Hat H-flips when facing right')
            phase = 'jump'
            phaseStart = frame
        end
    elseif phase == 'jump' then
        local elapsed = frame - phaseStart
        if elapsed < 12 then currentInput = {a = true} end
        local hy = findHatOam()
        local headY = read(0x654C)
        local vy = read(0x057D)
        if hy and read(0x0479) ~= 0 and headY < 0xF0 then
            if vy >= 0x80 then airRiseDelta = headY - hy
            elseif vy > 0 and vy < 0x80 then airFallDelta = headY - hy end
        end
        if elapsed >= 34 and read(0x0479) == 0 then
            check(airRiseDelta ~= nil and airFallDelta ~= nil and airFallDelta > airRiseDelta,
                string.format('Hat lags on jump/fall (rise=%s fall=%s)', tostring(airRiseDelta), tostring(airFallDelta)))
            phase = 'crouch'
            phaseStart = frame
        end
    elseif phase == 'crouch' then
        currentInput = {down = true}
        local elapsed = frame - phaseStart
        if elapsed == 6 then
            local hy = findHatOam()
            local cy = read(0x650C)
            if hy and cy < 0xF0 then
                sawCrouch = (cy - hy >= 2 and cy - hy <= 7)
            end
            check(sawCrouch, 'Hat follows crouched head')
            writeFile('waldo-hat-crouch.png', emu.takeScreenshot())
            phase = 'up'
            phaseStart = frame
        end
    elseif phase == 'up' then
        write(0x0796, 0xFF)
        local elapsed = frame - phaseStart
        currentInput = {a = (elapsed < 8), up = true}
        local hy = findHatOam()
        local headY = read(0x654C)
        if hy and read(0x654D) == 0x3B and headY < 0xF0 then
            sawUp = (headY - hy >= -2 and headY - hy <= 2)
        end
        if elapsed >= 20 then
            check(sawUp, 'Hat sits on upturned head when looking up')
            report:write(errors == 0 and 'RESULT PASS\n' or 'RESULT FAIL\n')
            report:close()
            phase = 'done'
            stopScenario(errors == 0 and 0 or 1)
        end
    end
end, emu.eventType.endFrame)
