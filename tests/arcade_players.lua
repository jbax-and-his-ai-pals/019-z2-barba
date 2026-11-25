-- Verify Barba's Arcade ($1C) replaces the two Rauru NPCs with moving arcade players and arcade dialogue.
dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local report = assert(io.open(OUTPUT_DIR .. '/arcade-players.txt', 'w'))
local errors = 0
local done = false
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    report:flush()
    if not cond then errors = errors + 1 end
end
local function finish()
    if done then return end
    done = true
    report:write(errors == 0 and 'RESULT PASS\n' or 'RESULT FAIL\n')
    report:close()
    emu.stop(errors == 0 and 0 or 1)
end

local frame = 0
local phase = 'boot'
local phaseStart = 0
local seen = {}
local oldSeen = false
local p0Slot = nil
local p0StartX = nil
local p0Moved = false
local p0InBounds = true
local talkBtn = false

local function encodeLine(s)
    local out = {}
    for i = 1, #s do
        local c = s:sub(i, i)
        if c == ' ' then out[#out + 1] = 0xF4
        elseif c == '.' then out[#out + 1] = 0xCF
        elseif c == '!' then out[#out + 1] = 0x36
        else out[#out + 1] = string.byte(c) - string.byte('A') + 0xDA end
    end
    return out
end

emu.addEventCallback(function()
    if phase == 'boot' and frame < 1000 then
        emu.setInput(newGameInput(frame), 0)
    elseif phase == 'enter_arcade' then
        local ef = frame - phaseStart
        emu.setInput({up = (ef >= 10 and ef < 14)}, 0)
    elseif phase == 'scan_right' then
        emu.setInput({right = true}, 0)
    elseif phase == 'return_p0' then
        emu.setInput({left = true}, 0)
    elseif phase == 'approach_p0' then
        if p0Slot then
            local nx = read(0x4E + p0Slot)
            local bx = read(0x4D)
            local bp = read(0x3B)
            if bp > 0 or bx > nx + 6 then
                emu.setInput({left = true, b = talkBtn}, 0)
            elseif bx < nx - 6 then
                emu.setInput({right = true, b = talkBtn}, 0)
            else
                emu.setInput({b = talkBtn}, 0)
            end
        else
            emu.setInput({}, 0)
        end
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if done then return end
    frame = frame + 1

    if phase == 'boot' then
        if frame == 1000 then
            write(0x707, 1); write(0x706, 0); write(0x056B, 0); write(0x769, 3); write(0x561, 1)
            write(0x701, 0); write(0x75C, 1); write(0x704, 0); write(0x736, 0); write(0x73D, 0); write(0x726, 1)
            phase = 'load_rauru'
            phaseStart = frame
        end
    elseif phase == 'load_rauru' then
        if frame - phaseStart >= 60 and read(0x726) == 0 and read(0x736) == 11 then
            for s = 0, 5 do write(0xB6 + s, 0) end
            write(0x3B, 1); write(0x4D, 40); write(0x70, 0)
            phase = 'enter_arcade'
            phaseStart = frame
        end
    elseif phase == 'enter_arcade' then
        local ef = frame - phaseStart
        if ef > 30 and read(0x561) == 0x1C and read(0x736) == 11 and read(0x726) == 0 then
            check(true, 'Entered Barba Arcade room $1C')
            phase = 'observe_p0'
            phaseStart = frame
        elseif ef > 180 then
            check(false, 'Timed out entering Barba Arcade')
            finish()
        end
    elseif phase == 'observe_p0' then
        for s = 0, 5 do
            if read(0xB6 + s) == 1 then
                local k = read(0xA1 + s)
                seen[k] = true
                if k == 0x0E or k == 0x10 then oldSeen = true end
                if k == 0x1E then
                    p0Slot = s
                    local x = read(0x4E + s)
                    if not p0StartX then p0StartX = x end
                    if x ~= p0StartX then p0Moved = true end
                    if x < 0x20 or x > 0xD8 then p0InBounds = false end
                end
            end
        end
        if frame - phaseStart >= 80 then
            check(p0Slot ~= nil, 'Page 0 arcade player ($1E) spawned')
            check(p0Moved, string.format('Page 0 arcade player moved (start=%s)', tostring(p0StartX)))
            check(p0InBounds, 'Page 0 arcade player stayed within page bounds')
            phase = 'scan_right'
            phaseStart = frame
        end
    elseif phase == 'scan_right' then
        for s = 0, 5 do
            if read(0xB6 + s) == 1 then
                local k = read(0xA1 + s)
                seen[k] = true
                if k == 0x0E or k == 0x10 then oldSeen = true end
            end
        end
        if (read(0x3B) == 3 and read(0x4D) >= 0xB0) or (frame - phaseStart > 500) then
            check(not oldSeen, 'Old Rauru NPCs ($0E, $10) are gone')
            check(seen[0x1E] == true, 'Saw page 0 patron ($1E)')
            check(seen[0x1C] == true, 'Saw page 1 patron ($1C)')
            check(seen[0x19] == true, 'Saw page 2 patron ($19)')
            check(seen[0x1B] == true, 'Saw page 3 patron ($1B)')
            phase = 'return_p0'
            phaseStart = frame
        end
    elseif phase == 'return_p0' then
        if read(0x3B) == 0 and read(0x4D) <= 0x60 then
            p0Slot = nil
            for s = 0, 5 do
                if read(0xB6 + s) == 1 and read(0xA1 + s) == 0x1E then p0Slot = s end
            end
            phase = 'approach_p0'
            phaseStart = frame
        elseif frame - phaseStart > 500 then
            check(false, 'Timed out returning to page 0')
            finish()
        end
    elseif phase == 'approach_p0' then
        if p0Slot and read(0xB6 + p0Slot) == 1 then
            local dx = math.abs(read(0x4E + p0Slot) - read(0x4D))
            talkBtn = (read(0x3B) == 0 and dx <= 10 and (frame % 4 == 0))
        end
        if read(0x074C) == 2 and (read(0x0569) ~= 0 or read(0x056A) ~= 0) then
            local ptr = read(0x0569) + read(0x056A) * 256
            check(ptr == 0x63C0, string.format('Dialogue pointer is ARCADE_DLG_BUF ($%04X)', ptr))
            local expected = encodeLine('I LOVE THIS')
            local ok = true
            for i = 1, #expected do
                if read(0x63C0 + i - 1) ~= expected[i] then ok = false end
            end
            check(ok, 'Page 0 patron shows arcade-themed message')
            finish()
        elseif frame - phaseStart > 240 then
            check(false, 'Timed out talking to page 0 patron')
            finish()
        end
    end
end, emu.eventType.endFrame)
